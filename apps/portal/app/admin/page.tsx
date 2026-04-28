"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

type Overview = {
  tenants_by_plan: { plan_id: string; n: number }[];
  tenants: { active: number; suspended: number; total: number };
  users: { active: number; total: number; super_admins: number };
  devices: { online: number; active: number; pending: number; total: number };
  logs_30d: number;
  logs_24h: number;
  pending_custom_domains: number;
  mrr_usd: number;
  arr_usd: number;
  arpa_usd: number;
  paid_subscriptions: number;
  growth: { new_7d: number; new_30d: number };
  recent_signups: { id: number; slug: string; name: string; plan_id: string; created_at: string }[];
};

const fmtUsd = (n: number) => `$${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (s: string) => new Date(s).toLocaleString();

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="card">
      <div className="muted" style={{ fontSize: "0.85rem" }}>{label}</div>
      <h2 style={{ fontSize: "2rem", margin: "0.3rem 0" }}>{value}</h2>
      {sub && <div className="muted" style={{ fontSize: "0.8rem" }}>{sub}</div>}
    </div>
  );
}

export default function AdminOverview() {
  const [data, setData] = useState<Overview | null>(null);
  useEffect(() => { api.get<Overview>("/api/admin/overview").then(setData); }, []);
  if (!data) return <div className="muted">Loading…</div>;

  return (
    <div className="grid">
      <h1>Overview</h1>

      <div className="grid cols-3">
        <Stat label="MRR (USD)" value={fmtUsd(data.mrr_usd)}
              sub={`${data.paid_subscriptions} paid · ARPA ${fmtUsd(data.arpa_usd)}`}/>
        <Stat label="ARR (USD)" value={fmtUsd(data.arr_usd)} sub="Annualised" />
        <Stat label="Tenants"
              value={`${data.tenants?.active ?? 0} / ${data.tenants?.total ?? 0}`}
              sub={`+${data.growth?.new_7d ?? 0} (7d) · +${data.growth?.new_30d ?? 0} (30d) · ${data.tenants?.suspended ?? 0} suspended`}/>
      </div>

      <div className="grid cols-3">
        <Stat label="Devices online"
              value={`${data.devices?.online ?? 0} / ${data.devices?.active ?? 0}`}
              sub={`${data.devices?.pending ?? 0} pending claim · ${data.devices?.total ?? 0} total`}/>
        <Stat label="Attendance logs"
              value={(data.logs_24h ?? 0).toLocaleString()}
              sub={`24h · ${(data.logs_30d ?? 0).toLocaleString()} (30d)`}/>
        <Stat label="Pending domains"
              value={data.pending_custom_domains ?? 0}
              sub={<Link href="/admin/disputes">Open queue</Link>}/>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Tenants by plan</h3>
          <table className="table">
            <thead><tr><th>Plan</th><th>Tenants</th></tr></thead>
            <tbody>
              {data.tenants_by_plan?.map((p) => (
                <tr key={p.plan_id}><td>{p.plan_id}</td><td>{p.n}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Recent signups</h3>
          <table className="table">
            <thead><tr><th>Slug</th><th>Plan</th><th>Created</th></tr></thead>
            <tbody>
              {data.recent_signups?.map((t) => (
                <tr key={t.id}>
                  <td><Link href={`/admin/tenants/${t.id}`}>{t.slug}</Link> <span className="muted">— {t.name}</span></td>
                  <td><span className="badge">{t.plan_id}</span></td>
                  <td className="muted">{fmtDate(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Users</h3>
        <p className="muted">
          {data.users?.active ?? 0} active · {data.users?.super_admins ?? 0} super admins · {data.users?.total ?? 0} total
        </p>
        <Link href="/admin/users" className="btn secondary">Manage users</Link>
      </div>
    </div>
  );
}
