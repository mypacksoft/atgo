"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "../../../lib/api";

type AuditRow = {
  id: number;
  tenant_id: number | null;
  tenant_slug: string | null;
  actor_user_id: number | null;
  actor_email: string | null;
  actor_type: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: any;
  ip_address: string | null;
  created_at: string;
};

export default function AdminAuditPage() {
  const sp = useSearchParams();
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [tenantId, setTenantId] = useState(sp.get("tenant_id") || "");
  const [action, setAction] = useState("");
  const [actorId, setActorId] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (tenantId) params.set("tenant_id", tenantId);
    if (action) params.set("action", action);
    if (actorId) params.set("actor_user_id", actorId);
    setRows(await api.get<AuditRow[]>(`/api/admin/audit-logs?${params}`));
  }
  useEffect(() => { load(); }, []);

  return (
    <div className="grid">
      <h1>Audit log</h1>
      <p className="muted">Every super-admin action is recorded here. Use the filters to narrow down.</p>

      <div className="card">
        <div className="row">
          <input placeholder="Tenant ID" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
          <input placeholder="Action contains…" value={action} onChange={(e) => setAction(e.target.value)} />
          <input placeholder="Actor user ID" value={actorId} onChange={(e) => setActorId(e.target.value)} />
          <button className="btn" onClick={load}>Filter</button>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>When</th><th>Actor</th><th>Action</th><th>Resource</th>
            <th>Tenant</th><th>IP</th><th>Metadata</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
              <td>{r.actor_email ?? r.actor_type}</td>
              <td><code>{r.action}</code></td>
              <td className="muted">
                {r.resource_type}{r.resource_id ? `:${r.resource_id}` : ""}
              </td>
              <td>{r.tenant_slug
                ? <Link href={`/admin/tenants/${r.tenant_id}`}>{r.tenant_slug}</Link>
                : <span className="muted">—</span>}</td>
              <td className="muted">{r.ip_address ?? "—"}</td>
              <td><code style={{ fontSize: "0.75rem" }}>
                {r.metadata && Object.keys(r.metadata).length
                  ? JSON.stringify(r.metadata) : "—"}
              </code></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="muted">No audit entries.</p>}
    </div>
  );
}
