"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";

type Sub = {
  id: number;
  tenant_id: number;
  tenant_slug: string;
  tenant_name: string;
  plan_id: string;
  plan_name: string;
  status: string;
  payment_provider: string | null;
  currency: string | null;
  amount_local: number | null;
  monthly_price_usd_cents: number;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
  created_at: string;
};

const STATUS_COLOR: Record<string, string> = {
  active:    "green",
  trialing:  "",
  past_due:  "red",
  cancelled: "",
  expired:   "red",
};

export default function AdminSubscriptions() {
  const [subs, setSubs] = useState<Sub[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [planFilter, setPlanFilter] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status_filter", statusFilter);
    if (planFilter) params.set("plan_id", planFilter);
    setSubs(await api.get<Sub[]>(`/api/admin/subscriptions?${params}`));
  }
  useEffect(() => { load(); }, [statusFilter, planFilter]);

  return (
    <div className="grid">
      <h1>Subscriptions</h1>

      <div className="row">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="trialing">Trialing</option>
          <option value="past_due">Past due</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
        </select>
        <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}>
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="starter">Starter</option>
          <option value="business">Business</option>
          <option value="scale">Scale</option>
          <option value="hr_pro">HR Pro</option>
        </select>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>ID</th><th>Tenant</th><th>Plan</th><th>Status</th>
            <th>Provider</th><th>Amount</th><th>Period end</th><th>Created</th>
          </tr>
        </thead>
        <tbody>
          {subs.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td><Link href={`/admin/tenants/${s.tenant_id}`}>{s.tenant_slug}</Link>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>{s.tenant_name}</div></td>
              <td><span className="badge">{s.plan_id}</span></td>
              <td><span className={`badge ${STATUS_COLOR[s.status] ?? ""}`}>{s.status}</span>
                  {s.cancel_at_period_end && <div className="muted" style={{ fontSize: "0.75rem" }}>cancels at period end</div>}</td>
              <td className="muted">{s.payment_provider ?? "—"}</td>
              <td>{s.amount_local != null
                ? `${s.amount_local.toLocaleString()} ${s.currency ?? ""}`
                : <span className="muted">—</span>}</td>
              <td className="muted">{s.current_period_end ? new Date(s.current_period_end).toLocaleDateString() : "—"}</td>
              <td className="muted">{new Date(s.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {subs.length === 0 && <p className="muted">No subscriptions match these filters.</p>}
    </div>
  );
}
