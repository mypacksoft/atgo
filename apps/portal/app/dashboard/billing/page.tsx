"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";
import type { PricingResponse } from "../../../lib/types";

type Sub = {
  plan_id: string;
  plan_name: string;
  status: string;
  device_limit: number | null;
  allow_custom_domain: boolean;
  custom_domain_limit: number;
  current_period_end: string | null;
  payment_provider: string | null;
};

const PLAN_HIGHLIGHTS: Record<string, string[]> = {
  free:     ["1 device", "30-day log retention", "100k logs/mo", "No custom domain"],
  starter:  ["Up to 3 devices", "60-day retention", "500k logs/mo", "Email support"],
  business: ["Up to 10 devices", "180-day retention", "2M logs/mo", "1 custom domain", "Advanced dashboard"],
  scale:    ["Up to 25 devices", "1-year retention", "5M logs/mo", "3 custom domains", "Multi-branch"],
  hr_pro:   ["Up to 25 devices", "Advanced rules", "Shift management", "5 custom domains", "Auto DNS", "Payroll export"],
};

function formatPrice(amount: number, currency: string) {
  if (currency === "VND") return new Intl.NumberFormat("vi-VN").format(amount) + " ₫";
  if (currency === "INR") return "₹" + (amount / 100).toFixed(2);
  return "$" + (amount / 100).toFixed(2);
}

const PROVIDER_LABEL: Record<string, string> = {
  paddle:   "💳 Card / Apple Pay / SEPA — via Paddle",
  vnpay:    "💳 ATM/Visa/MC + 🟦 QR — via VNPay",
  momo:     "📱 MoMo wallet",
  razorpay: "💳 UPI / Netbanking / Card — via Razorpay",
};

export default function BillingPage() {
  const [sub, setSub] = useState<Sub | null>(null);
  const [pricing, setPricing] = useState<PricingResponse | null>(null);
  const [error, setError] = useState("");
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [methodOverride, setMethodOverride] = useState<string>("");

  useEffect(() => {
    api.get<Sub>("/api/billing/subscription").then(setSub).catch(() => setSub(null));
    api.get<PricingResponse>("/api/billing/pricing").then(setPricing);
  }, []);

  const isFree = (sub?.plan_id ?? "free") === "free";

  const sortedPlans = useMemo(() => {
    if (!pricing) return [];
    const order = ["starter", "business", "scale", "hr_pro"];
    return [...pricing.plans].sort((a, b) => order.indexOf(a.plan_id) - order.indexOf(b.plan_id));
  }, [pricing]);

  async function checkout(plan_id: string) {
    setError("");
    setLoadingPlan(plan_id);
    try {
      const body: any = { plan_id };
      if (methodOverride) body.payment_method = methodOverride;
      const r = await api.post<{ checkout_url?: string; provider: string; instructions?: string }>(
        "/api/billing/checkout", body,
      );
      if (r.checkout_url) {
        window.location.href = r.checkout_url;
      } else {
        alert(`Provider: ${r.provider}\n\n${r.instructions ?? "Frontend SDK required (e.g. Razorpay)."}`);
      }
    } catch (err: any) {
      setError(err?.message || "checkout failed");
    } finally {
      setLoadingPlan(null);
    }
  }

  return (
    <div className="grid">
      {/* Banner — only when on free */}
      {isFree && (
        <div
          className="card"
          style={{
            borderLeft: "4px solid var(--accent)",
            background: "linear-gradient(135deg, rgba(99,102,241,0.10), rgba(168,85,247,0.05))",
          }}
        >
          <h2 style={{ margin: "0 0 0.4rem 0" }}>Get more out of ATGO</h2>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            You're on the <span className="badge red">Free</span> plan.
            Upgrade to add more devices, attach a custom domain, store logs longer,
            and unlock HR features.
          </p>
        </div>
      )}

      {/* Current plan */}
      <div className="card">
        <h2>Current plan</h2>
        {sub ? (
          <div className="grid cols-3">
            <div><div className="muted">Plan</div>
                 <strong>{sub.plan_name || sub.plan_id}</strong>{" "}
                 {isFree && <span className="badge red">free</span>}</div>
            <div><div className="muted">Status</div>
                 <span className={"badge " + (sub.status === "active" ? "green" : "")}>{sub.status}</span></div>
            <div><div className="muted">Device limit</div>{sub.device_limit ?? "Unlimited"}</div>
            <div><div className="muted">Custom domains</div>
                 {sub.allow_custom_domain ? sub.custom_domain_limit : "Not included"}</div>
            <div><div className="muted">Renews</div>
                 {sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}</div>
            <div><div className="muted">Provider</div>{sub.payment_provider || "—"}</div>
          </div>
        ) : <p className="muted">Free plan</p>}
      </div>

      {/* Upgrade plans */}
      {pricing && (
        <div className="card">
          <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap" }}>
            <h3 style={{ margin: 0 }}>
              {isFree ? "Upgrade your plan" : "Change your plan"}
              {" "}<span className="muted" style={{ fontWeight: 400, fontSize: "0.85rem" }}>
                ({pricing.country} · {pricing.currency})
              </span>
            </h3>
            <div className="row" style={{ gap: "0.4rem" }}>
              <span className="muted" style={{ fontSize: "0.85rem" }}>Pay with:</span>
              <select value={methodOverride} onChange={(e) => setMethodOverride(e.target.value)}>
                <option value="">{pricing.default_provider} (default)</option>
                {pricing.providers.filter((m) => m !== pricing.default_provider).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {pricing.tax_inclusive
              ? "Prices include VAT. E-invoice issued on payment."
              : "Tax calculated at checkout."}
          </p>

          <div className="grid cols-2" style={{ marginTop: "1rem" }}>
            {sortedPlans.map((p) => {
              const isCurrent = sub?.plan_id === p.plan_id;
              const featured = p.plan_id === "business";
              return (
                <div
                  key={p.plan_id}
                  className="card"
                  style={{
                    background: "var(--panel-2)",
                    borderColor: featured ? "var(--accent)" : undefined,
                    borderWidth: featured ? 2 : 1,
                    position: "relative",
                  }}
                >
                  {featured && (
                    <span
                      className="badge"
                      style={{
                        position: "absolute", top: -10, left: 16,
                        background: "var(--accent)", color: "white",
                      }}
                    >
                      Most popular
                    </span>
                  )}
                  <div className="row" style={{ alignItems: "baseline" }}>
                    <h3 style={{ margin: 0 }}>{p.name}</h3>
                    {isCurrent && <span className="badge green">current</span>}
                  </div>
                  <p style={{ fontSize: "1.6rem", margin: "0.5rem 0", fontWeight: 600 }}>
                    {formatPrice(p.amount_local, pricing.currency)}
                    <small className="muted" style={{ fontWeight: 400 }}> /mo</small>
                  </p>
                  <ul className="muted" style={{ paddingLeft: "1rem", lineHeight: 1.6, fontSize: "0.9rem" }}>
                    {(PLAN_HIGHLIGHTS[p.plan_id] ?? []).map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ul>
                  <button
                    className={"btn " + (featured ? "" : "secondary")}
                    onClick={() => checkout(p.plan_id)}
                    disabled={isCurrent || loadingPlan === p.plan_id}
                    style={{ marginTop: "0.8rem", width: "100%" }}
                  >
                    {isCurrent
                      ? "Current plan"
                      : loadingPlan === p.plan_id
                      ? "Redirecting…"
                      : isFree ? `Upgrade to ${p.name}` : `Switch to ${p.name}`}
                  </button>
                </div>
              );
            })}
          </div>

          <p className="muted" style={{ fontSize: "0.8rem", marginTop: "1rem" }}>
            {PROVIDER_LABEL[methodOverride || pricing.default_provider] ?? ""}
            {" "}· Cancel anytime. Annual discount available on request.
          </p>
        </div>
      )}

      {error && <div className="errbox">{error}</div>}
    </div>
  );
}
