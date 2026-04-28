"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type D = {
  id: number; name: string; serial_number: string; device_code: string;
  status: string; is_online: boolean; tenant_slug: string; last_seen_at: string | null;
};
export default function AdminDevices() {
  const [items, setItems] = useState<D[]>([]);
  const [sn, setSn] = useState(""); const [code, setCode] = useState("");
  function load() {
    const params = new URLSearchParams();
    if (sn) params.set("sn", sn); if (code) params.set("code", code);
    api.get<D[]>(`/api/admin/devices?${params}`).then(setItems);
  }
  useEffect(load, []);  // eslint-disable-line
  return (
    <div className="grid">
      <div className="row">
        <input placeholder="Serial number" value={sn} onChange={(e) => setSn(e.target.value)} />
        <input placeholder="Device code" value={code} onChange={(e) => setCode(e.target.value)} />
        <button className="btn" onClick={load}>Search</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>ID</th><th>Tenant</th><th>Name</th><th>Code</th><th>Serial</th><th>Status</th><th>Online</th><th>Last seen</th></tr></thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td><td><code className="kbd">{d.tenant_slug}</code></td>
                <td>{d.name}</td><td><code className="kbd">{d.device_code}</code></td>
                <td className="muted">{d.serial_number}</td>
                <td><span className={"badge " + (d.status === "active" ? "green" : "yellow")}>{d.status}</span></td>
                <td>{d.is_online ? "✅" : "—"}</td>
                <td className="muted">{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={8} className="muted">No devices.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
