"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, setToken } from "../../../../lib/api";

type Detail = {
  id: number;
  slug: string;
  name: string;
  plan_id: string;
  is_active: boolean;
  suspended_at: string | null;
  suspension_reason: string | null;
  billing_country: string | null;
  default_timezone: string;
  primary_domain: string | null;
  created_at: string;
  members: { id: number; email: string; full_name: string | null; role: string }[];
  stats: {
    devices_total: number; devices_online: number;
    employees: number; logs_30d: number; custom_domains: number;
  };
  subscription: any;
  domains: { id: number; domain: string; status: string; ssl_status: string;
             domain_type: string; is_primary: boolean }[];
};

const PLANS = ["free", "starter", "business", "scale", "hr_pro"];

export default function TenantDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [t, setT] = useState<Detail | null>(null);

  async function load() {
    const data = await api.get<Detail>(`/api/admin/tenants/${id}`);
    setT(data);
  }
  useEffect(() => { load(); }, [id]);

  async function changePlan(plan_id: string) {
    if (!confirm(`Move ${t?.slug} to plan "${plan_id}"?`)) return;
    await api.post(`/api/admin/tenants/${id}/change-plan`, { plan_id });
    load();
  }
  async function suspend() {
    const reason = prompt("Reason for suspension:") || "no reason";
    await api.post(`/api/admin/tenants/${id}/suspend`, { reason });
    load();
  }
  async function unsuspend() {
    await api.post(`/api/admin/tenants/${id}/unsuspend`);
    load();
  }
  async function impersonate() {
    if (!confirm(`Impersonate ${t?.slug}? This is audited.`)) return;
    const r = await api.post<{ access_token: string; tenant_slug: string }>(
      `/api/admin/tenants/${id}/impersonate`
    );
    setToken("hr", r.access_token);
    const port = window.location.port ? `:${window.location.port}` : "";
    const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN || "atgo.io";
    window.location.href = `${window.location.protocol}//${r.tenant_slug}.${baseDomain}${port}/dashboard`;
  }

  if (!t) return <div className="muted">Loading…</div>;

  return (
    <div className="grid">
      <div className="row" style={{ alignItems: "baseline" }}>
        <Link href="/admin/tenants" className="muted">← Tenants</Link>
        <h1 style={{ margin: 0 }}>{t.name}</h1>
        <span className="muted">{t.slug}.atgo.io</span>
        {t.is_active
          ? <span className="badge green">active</span>
          : <span className="badge red">suspended</span>}
      </div>

      <div className="row" style={{ flexWrap: "wrap" }}>
        {t.is_active
          ? <button className="btn secondary" onClick={suspend}>Suspend</button>
          : <button className="btn" onClick={unsuspend}>Unsuspend</button>}
        <button className="btn secondary" onClick={impersonate}>Impersonate (audited)</button>
        <a className="btn secondary" href={`/admin/audit?tenant_id=${t.id}`}>Audit log</a>
      </div>

      {t.suspension_reason && (
        <div className="errbox">
          Suspension reason: {t.suspension_reason}
          {t.suspended_at && <> · since {new Date(t.suspended_at).toLocaleString()}</>}
        </div>
      )}

      <div className="grid cols-3">
        <div className="card">
          <h3>Devices</h3>
          <p>{t.stats?.devices_online}/{t.stats?.devices_total} online</p>
        </div>
        <div className="card">
          <h3>Employees</h3>
          <p>{t.stats?.employees}</p>
        </div>
        <div className="card">
          <h3>Logs (30d)</h3>
          <p>{(t.stats?.logs_30d ?? 0).toLocaleString()}</p>
        </div>
      </div>

      <div className="card">
        <h3>Plan & subscription</h3>
        <div className="row" style={{ marginBottom: "0.5rem" }}>
          <span>Current: <strong>{t.plan_id}</strong></span>
          <span className="muted">
            {t.subscription?.status} · {t.subscription?.payment_provider || "no provider"}
            {t.subscription?.currency && ` · ${t.subscription.currency} ${t.subscription.amount_local ?? "—"}`}
          </span>
        </div>
        <div className="row" style={{ flexWrap: "wrap" }}>
          {PLANS.map((p) => (
            <button key={p} className="btn secondary" disabled={p === t.plan_id}
                    onClick={() => changePlan(p)}>{p}</button>
          ))}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Members</h3>
          <table className="table">
            <thead><tr><th>Email</th><th>Role</th></tr></thead>
            <tbody>
              {t.members?.map((m) => (
                <tr key={m.id}>
                  <td>{m.email} {m.full_name && <span className="muted">({m.full_name})</span>}</td>
                  <td><span className="badge">{m.role}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Domains</h3>
          <table className="table">
            <thead><tr><th>Domain</th><th>Type</th><th>Status</th></tr></thead>
            <tbody>
              {t.domains?.map((d) => (
                <tr key={d.id}>
                  <td>{d.domain} {d.is_primary && <span className="badge green">primary</span>}</td>
                  <td className="muted">{d.domain_type.replace("_", " ")}</td>
                  <td><span className="badge">{d.status}</span> <span className="muted">SSL {d.ssl_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
