"""Webhook signature verification for each payment provider.

These helpers return True/False; they never raise. Each provider's spec:

  - Paddle: HMAC-SHA256 of raw body, key = `PADDLE_PUBLIC_KEY` (Notification
    secret) — `Paddle-Signature: ts=...;h1=...` header
  - VNPay (server-to-server return): MD5 hash of sorted query string + secret
    — but webhook style (IPN): `vnp_SecureHash` over sorted alphabetical params
    using HMAC-SHA512 with TMN secret
  - Razorpay: HMAC-SHA256 of raw body using webhook secret — `X-Razorpay-Signature`
  - MoMo: HMAC-SHA256 of canonical params with partner secret

For MVP we wire signatures correctly so future providers slot in cleanly,
but mark verified=False if env vars are missing.
"""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl

from ..config import get_settings

settings = get_settings()


def verify_paddle(raw: bytes, headers: dict) -> bool:
    sig = headers.get("paddle-signature") or headers.get("Paddle-Signature")
    secret = settings.PADDLE_PUBLIC_KEY  # actually Notification secret
    if not sig or not secret:
        return False
    parts = dict(p.split("=", 1) for p in sig.split(";") if "=" in p)
    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False
    payload = f"{ts}:".encode() + raw
    mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, h1)


def verify_razorpay(raw: bytes, headers: dict) -> bool:
    sig = headers.get("x-razorpay-signature")
    secret = settings.RAZORPAY_KEY_SECRET
    if not sig or not secret:
        return False
    mac = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig)


def verify_vnpay(query: str | bytes) -> bool:
    """VNPay IPN: every param except `vnp_SecureHash` and
    `vnp_SecureHashType`, sorted, joined `k=v&k=v`, HMAC-SHA512 with secret."""
    if isinstance(query, bytes):
        query = query.decode("utf-8", errors="replace")
    secret = settings.VNPAY_HASH_SECRET
    if not secret:
        return False
    params = dict(parse_qsl(query, keep_blank_values=True))
    sig = params.pop("vnp_SecureHash", None)
    params.pop("vnp_SecureHashType", None)
    if not sig:
        return False
    canonical = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    mac = hmac.new(secret.encode(), canonical.encode(), hashlib.sha512).hexdigest()
    return hmac.compare_digest(mac.lower(), sig.lower())


def verify_momo(raw: bytes, headers: dict) -> bool:
    """MoMo posts JSON with a `signature` field; recompute HMAC-SHA256
    over canonical fields. Stub for now — config not in settings."""
    return False
