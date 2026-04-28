"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type D = { id: number; normalized_domain: string; claimed_by_tenant: number | null; requesting_email: string; evidence: string | null; status: string; created_at: string };

export default function AdminDisputes() {
  const [items, setItems] = useState<D[]>([]);
  function load() { api.get<D[]>("/api/admin/domain-disputes").then(setItems); }
  useEffect(load, []);

  async function release() {
    const domain = prompt("Domain to release (normalized):") || "";
    if (!domain) return;
    const reason = prompt("Reason:") || "admin override";
    await api.post("/api/admin/domains/release", { normalized_domain: domain, reason });
    alert("Released.");
    load();
  }

  return (
    <div className="grid">
      <div className="row">
        <button className="btn" onClick={release}>Release a domain</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>Domain</th><th>Claimed by</th><th>Requested by</th><th>Status</th><th>When</th></tr></thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td><code className="kbd">{d.normalized_domain}</code></td>
                <td>{d.claimed_by_tenant ?? "—"}</td>
                <td>{d.requesting_email}</td>
                <td>{d.status}</td>
                <td className="muted">{new Date(d.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={5} className="muted">No disputes.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
