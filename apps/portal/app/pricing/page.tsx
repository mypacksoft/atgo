"use client";
import { useEffect, useState } from "react";
import type { PricingResponse } from "../../lib/types";
import { api } from "../../lib/api";

export default function PricingPage() {
  const [country, setCountry] = useState("");
  const [data, setData] = useState<PricingResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const url = country ? `/api/billing/pricing?country=${country}` : `/api/billing/pricing`;
    api.get<PricingResponse>(url).then(setData).catch((e) => setError(e?.message || "error"));
  }, [country]);

  function fmt(amount: number, currency: string) {
    if (currency === "VND") return new Intl.NumberFormat("vi-VN").format(amount) + " ₫";
    if (currency === "INR") return "₹" + (amount / 100).toFixed(2);
    return "$" + (amount / 100).toFixed(2);
  }

  return (
    <main>
      <header className="nav">
        <a href="/"><strong>ATGO</strong></a>
        <span className="right row">
          <a href="/login">Sign in</a>
          <a href="/signup" className="btn" style={{ color: "white" }}>Start free</a>
        </span>
      </header>
      <section className="content">
        <h1>Pricing</h1>
        <p className="muted">Free for 1 device. Unlimited employees on every plan.</p>
        <label className="muted" style={{ display: "block", marginTop: "1rem" }}>
          Show prices for:&nbsp;
          <select value={country} onChange={(e) => setCountry(e.target.value)} style={{ width: 240, display: "inline-block" }}>
            <option value="">Auto detect</option>
            <option value="VN">Vietnam (VND)</option>
            <option value="IN">India (INR)</option>
            <option value="DEFAULT">Other (USD)</option>
          </select>
        </label>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}

        {data && (
          <div className="grid cols-3" style={{ marginTop: "1.5rem" }}>
            {[
              { id: "free",     name: "Free",     desc: "1 device. Forever.", price: 0 },
              ...data.plans.map((p) => ({ id: p.plan_id, name: p.name, desc: "", price: p.amount_local })),
            ].map((p) => (
              <div className="card" key={p.id}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h2 style={{ marginBottom: 0 }}>{p.name}</h2>
                  {p.id === "business" && <span className="badge blue">Popular</span>}
                </div>
                <p style={{ fontSize: "1.6rem", margin: "0.5rem 0" }}>
                  {p.price === 0 ? "Free" : fmt(p.price, data.currency)}
                  {p.price > 0 && <small className="muted" style={{ fontSize: "0.9rem" }}> /mo</small>}
                </p>
                <ul className="muted" style={{ paddingLeft: "1.1rem", lineHeight: 1.7 }}>
                  {p.id === "free" && (<>
                    <li>1 ZKTeco device</li>
                    <li>Unlimited employees</li>
                    <li>30-day log history</li>
                    <li>Basic Odoo sync</li>
                  </>)}
                  {p.id === "starter" && (<>
                    <li>3 ZKTeco devices</li>
                    <li>60-day log history</li>
                    <li>Email support</li>
                  </>)}
                  {p.id === "business" && (<>
                    <li>10 devices</li>
                    <li>180-day history</li>
                    <li>1 custom domain</li>
                    <li>Multi-device employee sync</li>
                  </>)}
                  {p.id === "scale" && (<>
                    <li>25 devices</li>
                    <li>1-year history</li>
                    <li>3 custom domains</li>
                    <li>Multi-branch dashboard</li>
                  </>)}
                  {p.id === "hr_pro" && (<>
                    <li>25 devices</li>
                    <li>5 custom domains</li>
                    <li>Cloudflare auto-DNS</li>
                    <li>Shift management & advanced rules</li>
                  </>)}
                </ul>
                <div style={{ marginTop: "1rem" }}>
                  <a className="btn" href="/signup" style={{ color: "white", display: "inline-block", padding: "0.55rem 1rem", borderRadius: 6 }}>
                    {p.id === "free" ? "Start free" : "Upgrade"}
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="muted" style={{ marginTop: "1.5rem" }}>
          Detected country: <strong>{data?.country}</strong> · Currency: <strong>{data?.currency}</strong>{" "}
          · Default provider: <strong>{data?.default_provider}</strong>
        </p>
      </section>
    </main>
  );
}
