"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Device, Employee, Tenant } from "../../lib/types";

export default function DashboardOverview() {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [emps, setEmps] = useState<Employee[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Tenant>("/api/me/tenant").catch(() => null),
      api.get<Device[]>("/api/devices"),
      api.get<Employee[]>("/api/employees"),
    ])
      .then(([t, d, e]) => { setTenant(t); setDevices(d); setEmps(e); })
      .catch((e) => setError(e?.message || "load failed"));
  }, []);

  const online = devices.filter((d) => d.is_online).length;
  const active = emps.filter((e) => e.is_active).length;
  const isFree = tenant?.plan_id === "free";
  const deviceLimit = 1;

  return (
    <div className="grid">
      {error && <div className="errbox">{error}</div>}

      {isFree && (
        <div
          className="card"
          style={{
            borderLeft: "4px solid var(--accent)",
            background: "linear-gradient(135deg, rgba(99,102,241,0.10), rgba(168,85,247,0.05))",
          }}
        >
          <div className="row" style={{ alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 280 }}>
              <h3 style={{ margin: "0 0 0.4rem 0" }}>
                You're on the <span className="badge red">Free</span> plan
              </h3>
              <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
                Free includes <strong>1 device</strong>, 30-day log retention, and 100k logs/month.
                Upgrade to add more devices, custom domains, advanced rules, and longer retention.
              </p>
              <p className="muted" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
                Currently using <strong>{devices.length}</strong> / {deviceLimit} devices ·
                {" "}<strong>{active}</strong> employees ·
                {" "}<strong>{online}</strong> online now.
              </p>
            </div>
            <div className="row" style={{ flexShrink: 0 }}>
              <Link href="/dashboard/billing" className="btn">
                See plans
              </Link>
              <Link href="/dashboard/billing" className="btn secondary">
                Upgrade now
              </Link>
            </div>
          </div>
        </div>
      )}
      <div className="grid cols-3">
        <div className="card">
          <div className="muted">Devices</div>
          <h2 style={{ fontSize: "2rem" }}>{devices.length}</h2>
          <span className="badge green">{online} online</span>
        </div>
        <div className="card">
          <div className="muted">Active employees</div>
          <h2 style={{ fontSize: "2rem" }}>{active}</h2>
          <span className="muted">{emps.length} total</span>
        </div>
        <div className="card">
          <div className="muted">Quick start</div>
          <ol style={{ paddingLeft: "1.1rem", lineHeight: 1.7 }}>
            <li><a href="/dashboard/devices">Add a device</a></li>
            <li><a href="/dashboard/employees">Add employees</a></li>
            <li><a href="/dashboard/odoo">Connect Odoo</a></li>
          </ol>
        </div>
      </div>

      <div className="card">
        <h3>Devices</h3>
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Code</th><th>Serial</th><th>Status</th><th>Online</th><th>Last seen</th></tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td><span className="kbd">{d.device_code}</span></td>
                <td className="muted">{d.serial_number}</td>
                <td><span className={"badge " + (d.status === "active" ? "green" : "yellow")}>{d.status}</span></td>
                <td><span className={"badge " + (d.is_online ? "green" : "red")}>{d.is_online ? "yes" : "no"}</span></td>
                <td className="muted">{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
            {devices.length === 0 && (<tr><td colSpan={6} className="muted">No devices yet. <a href="/dashboard/devices">Add one →</a></td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
