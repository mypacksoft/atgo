"""Geo-aware pricing + payment provider router.

GET  /api/billing/pricing         -> current country's plans + providers
GET  /api/billing/subscription    -> tenant's current subscription
POST /api/billing/checkout        -> create checkout session via right provider
POST /api/billing/webhook/{prov}  -> provider webhooks (paddle, vnpay, razorpay)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from ..constants import PRICING_MATRIX
from ..deps import db_session, get_client_country, tenant_session
from ..schemas import PricingPlanOut, PricingResponse

router = APIRouter()


PLAN_NAMES = {
    "free":     "Free",
    "starter":  "Starter",
    "business": "Business",
    "scale":    "Scale",
    "hr_pro":   "HR Pro",
}


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(request: Request, country: str | None = None):
    """Return geo-localized pricing.

    Country resolution order:
      1. ?country=XX query (user override)
      2. cf-ipcountry header (Cloudflare)
      3. DEFAULT (USD via Paddle)
    """
    cc = (country or get_client_country(request) or "DEFAULT").upper()
    cfg = PRICING_MATRIX.get(cc, PRICING_MATRIX["DEFAULT"])

    plans = [
        PricingPlanOut(
            plan_id=pid,
            name=PLAN_NAMES.get(pid, pid.title()),
            amount_local=amount,
            currency=cfg["currency"],
            tax_inclusive=cfg["tax_inclusive"],
        )
        for pid, amount in cfg["plans"].items()
    ]

    return PricingResponse(
        country=cc,
        currency=cfg["currency"],
        providers=cfg["providers"],
        default_provider=cfg["default_provider"],
        tax_inclusive=cfg["tax_inclusive"],
        plans=plans,
    )


class CheckoutRequest(BaseModel):
    plan_id: str
    payment_method: str | None = None       # 'paddle' | 'vnpay' | 'momo' | 'razorpay'
    country: str | None = None
    return_url: str | None = None


class CheckoutResponse(BaseModel):
    provider: str
    checkout_url: str | None = None
    provider_payload: dict | None = None
    instructions: str | None = None


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(payload: CheckoutRequest, request: Request,
                          ctx=Depends(tenant_session)):
    session, tenant = ctx

    if payload.plan_id == "free":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "free plan needs no checkout")
    if payload.plan_id not in PLAN_NAMES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown plan")

    cc = (payload.country or get_client_country(request) or "DEFAULT").upper()
    cfg = PRICING_MATRIX.get(cc, PRICING_MATRIX["DEFAULT"])
    method = payload.payment_method or cfg["default_provider"]

    if method not in cfg["providers"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"payment method '{method}' not available in {cc}; use one of {cfg['providers']}",
        )

    if payload.plan_id not in cfg["plans"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "plan not available in this country")

    amount = cfg["plans"][payload.plan_id]
    currency = cfg["currency"]

    # MVP stubs — real provider SDK calls go here. Each provider returns its
    # own session/order shape. We return a uniform response.
    if method == "paddle":
        return CheckoutResponse(
            provider="paddle",
            checkout_url=f"https://checkout.paddle.com/checkout/custom/{tenant.id}-{payload.plan_id}",
            provider_payload={"amount": amount, "currency": currency},
            instructions="Hosted checkout. VAT calculated by Paddle.",
        )
    if method == "vnpay":
        return CheckoutResponse(
            provider="vnpay",
            checkout_url=f"https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?tenant={tenant.id}",
            provider_payload={"amount": amount, "currency": "VND"},
            instructions="Chuyển hướng tới VNPay. Hỗ trợ thẻ ATM, QR, Visa/Master.",
        )
    if method == "momo":
        return CheckoutResponse(
            provider="momo",
            checkout_url=f"https://test-payment.momo.vn/v2/gateway/api/create?tenant={tenant.id}",
            provider_payload={"amount": amount, "currency": "VND"},
            instructions="Quét QR MoMo để thanh toán.",
        )
    if method == "razorpay":
        return CheckoutResponse(
            provider="razorpay",
            provider_payload={
                "key": "rzp_test_xxx",
                "amount": amount,
                "currency": "INR",
                "order_id": f"order_{tenant.id}_{payload.plan_id}",
            },
            instructions="Use Razorpay Web Checkout in the frontend with this order_id.",
        )

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported payment method")


@router.get("/subscription")
async def get_subscription(ctx=Depends(tenant_session)):
    session, tenant = ctx
    res = await session.execute(
        text(
            "SELECT s.*, p.name AS plan_name, p.device_limit, p.allow_custom_domain, "
            "p.custom_domain_limit "
            "FROM subscriptions s JOIN plans p ON p.id = s.plan_id "
            "WHERE s.tenant_id = :tid"
        ),
        {"tid": tenant.id},
    )
    row = res.mappings().first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no subscription")
    return dict(row)


@router.post("/webhook/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def webhook(provider: str, request: Request, session=Depends(db_session)):
    """Generic webhook intake — verify signature, persist raw, queue for async
    processing. We deliberately return 202 fast; processing happens on a worker.
    """
    from ..services.billing_verify import (
        verify_paddle, verify_razorpay, verify_vnpay, verify_momo,
    )

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if provider == "paddle":
        verified = verify_paddle(body, headers)
        event_type = headers.get("paddle-event") or "unknown"
    elif provider == "razorpay":
        verified = verify_razorpay(body, headers)
        event_type = headers.get("x-razorpay-event-id") or "unknown"
    elif provider == "vnpay":
        verified = verify_vnpay(body)
        event_type = "ipn"
    elif provider == "momo":
        verified = verify_momo(body, headers)
        event_type = "ipn"
    else:
        verified = False
        event_type = "unknown"

    payload_text = body.decode("utf-8", errors="replace") or "{}"
    if not payload_text.lstrip().startswith(("{", "[")):
        import json as _json
        payload_text = _json.dumps({"raw": payload_text})

    await session.execute(
        text(
            "INSERT INTO billing_events "
            "(provider, event_type, raw_payload, signature_verified) "
            "VALUES (:p, :et, CAST(:payload AS jsonb), :v)"
        ),
        {"p": provider, "et": event_type, "payload": payload_text, "v": verified},
    )
    if not verified:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "signature failed")
    return {"received": True}
