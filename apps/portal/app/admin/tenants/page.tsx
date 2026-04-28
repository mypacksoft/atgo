"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";

type T = {
  id: number; slug: string; name: string; plan_id: string;
  is_active: boolean; suspended_at: string | null;
  device_count: number; employee_count: number; created_at: string;
};

export default function AdminTenants() {
  const [items, setItems] = useState<T[]>([]);
  const [q, setQ] = useState("");

  function reload() {
    const url = q ? `/api/admin/tenants?q=${encodeURIComponent(q)}` : "/api/admin/tenants";
    api.get<T[]>(url).then(setItems);
  }
  useEffect(reload, []);  // eslint-disable-line

  async function suspend(id: number) {
    const reason = prompt("Reason:") || "abuse";
    await api.post(`/api/admin/tenants/${id}/suspend`, { reason });
    reload();
  }
  async function unsuspend(id: number) {
    await api.post(`/api/admin/tenants/${id}/unsuspend`);
    reload();
  }

  return (
    <div className="grid">
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search slug or name" style={{ flex: 1 }} />
        <button className="btn" onClick={reload}>Search</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>ID</th><th>Slug</th><th>Name</th><th>Plan</th><th>Devices</th><th>Employees</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td><Link href={`/admin/tenants/${t.id}`}><code className="kbd">{t.slug}</code></Link></td>
                <td><Link href={`/admin/tenants/${t.id}`}>{t.name}</Link></td>
                <td>{t.plan_id}</td>
                <td>{t.device_count}</td>
                <td>{t.employee_count}</td>
                <td>{t.is_active ? <span className="badge green">active</span> : <span className="badge red">suspended</span>}</td>
                <td>
                  {t.is_active
                    ? <button className="btn secondary" onClick={() => suspend(t.id)}>Suspend</button>
                    : <button className="btn" onClick={() => unsuspend(t.id)}>Unsuspend</button>}
                </td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={8} className="muted">No tenants.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
