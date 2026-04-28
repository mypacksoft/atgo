"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Ev = { id: number; tenant_id: number | null; kind: string; severity: string; message: string | null; ip_address: string | null; created_at: string };

export default function AdminSecurity() {
  const [items, setItems] = useState<Ev[]>([]);
  const [kind, setKind] = useState("");
  function load() { api.get<Ev[]>(`/api/admin/security-events${kind ? `?kind=${kind}` : ""}`).then(setItems); }
  useEffect(load, []);  // eslint-disable-line

  async function block() {
    const ip = prompt("IP to block:") || "";
    if (!ip) return;
    const reason = prompt("Reason:") || "abuse";
    const m = prompt("Minutes (blank = forever):") || "";
    await api.post("/api/admin/blocked-ips", { ip_address: ip, reason, minutes: m ? parseInt(m) : null });
    alert("Blocked.");
  }

  return (
    <div className="grid">
      <div className="row">
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          <option value="failed_login">Failed login</option>
          <option value="abuse">Abuse</option>
          <option value="admin_action">Admin action</option>
        </select>
        <button className="btn" onClick={load}>Apply</button>
        <button className="btn danger" onClick={block} style={{ marginLeft: "auto" }}>Block IP</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>When</th><th>Kind</th><th>Severity</th><th>Tenant</th><th>IP</th><th>Message</th></tr></thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id}>
                <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                <td>{e.kind}</td>
                <td><span className={"badge " + (e.severity === "critical" || e.severity === "alert" ? "red" : e.severity === "warn" ? "yellow" : "blue")}>{e.severity}</span></td>
                <td>{e.tenant_id ?? "—"}</td>
                <td className="muted">{e.ip_address || "—"}</td>
                <td>{e.message || "—"}</td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={6} className="muted">No events.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
