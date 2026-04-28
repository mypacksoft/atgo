"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Device, Employee } from "../../../lib/types";

type CommandRow = {
  id: number; device_id: number; command_type: string; status: string;
  attempt_count: number; delivered_at: string | null; completed_at: string | null;
  return_code: number | null; created_at: string; expires_at: string;
};

export default function SyncPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [emps, setEmps] = useState<Employee[]>([]);
  const [pickDev, setPickDev] = useState<Set<number>>(new Set());
  const [pickEmp, setPickEmp] = useState<Set<number>>(new Set());
  const [action, setAction] = useState<"upsert" | "disable" | "delete">("upsert");
  const [cmds, setCmds] = useState<CommandRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  function reload() {
    api.get<Device[]>("/api/devices").then(setDevices);
    api.get<Employee[]>("/api/employees").then(setEmps);
    api.get<CommandRow[]>("/api/sync/commands?limit=50").then(setCmds);
  }
  useEffect(reload, []);

  async function enqueue() {
    setBusy(true); setMsg("");
    try {
      const r = await api.post<{ queued: number }>("/api/sync/enqueue", {
        device_ids: Array.from(pickDev),
        employee_ids: pickEmp.size ? Array.from(pickEmp) : null,
        action,
      });
      setMsg(`Queued ${r.queued} command(s).`);
      setPickDev(new Set()); setPickEmp(new Set());
      reload();
    } catch (err: any) { setMsg(err?.message || "failed"); }
    finally { setBusy(false); }
  }

  function toggle(s: Set<number>, v: number, set: (s: Set<number>) => void) {
    const n = new Set(s); if (n.has(v)) n.delete(v); else n.add(v); set(n);
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Multi-device employee sync</h2>
        <p className="muted">Push employee records to one or more ZKTeco devices. Biometric data never leaves your devices.</p>
        <div className="grid cols-2">
          <div>
            <h4>Devices</h4>
            {devices.map((d) => (
              <label key={d.id} style={{ display: "block" }}>
                <input type="checkbox" checked={pickDev.has(d.id)} onChange={() => toggle(pickDev, d.id, setPickDev)} />{" "}
                {d.name} <span className="kbd">{d.device_code}</span>{" "}
                {d.is_online ? <span className="badge green">online</span> : <span className="badge red">offline</span>}
              </label>
            ))}
          </div>
          <div>
            <h4>Employees ({pickEmp.size > 0 ? pickEmp.size + " selected" : "all active"})</h4>
            <div style={{ maxHeight: 300, overflow: "auto", border: "1px solid var(--border)", borderRadius: 6, padding: "0.5rem" }}>
              {emps.map((e) => (
                <label key={e.id} style={{ display: "block" }}>
                  <input type="checkbox" checked={pickEmp.has(e.id)} onChange={() => toggle(pickEmp, e.id, setPickEmp)} />{" "}
                  {e.full_name} <span className="muted">({e.employee_code} / PIN {e.device_pin})</span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="row" style={{ marginTop: "1rem" }}>
          <select value={action} onChange={(e) => setAction(e.target.value as any)} style={{ width: 160 }}>
            <option value="upsert">Add / update</option>
            <option value="disable">Disable</option>
            <option value="delete">Delete</option>
          </select>
          <button className="btn" disabled={busy || pickDev.size === 0} onClick={enqueue}>
            {busy ? "Queueing…" : "Enqueue commands"}
          </button>
          {msg && <span className="muted">{msg}</span>}
        </div>
      </div>

      <div className="card">
        <h3>Recent commands</h3>
        <table className="table">
          <thead><tr><th>ID</th><th>Device</th><th>Type</th><th>Status</th><th>Attempts</th><th>Created</th></tr></thead>
          <tbody>
            {cmds.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td>{devices.find((d) => d.id === c.device_id)?.name || c.device_id}</td>
                <td>{c.command_type}</td>
                <td><span className={"badge " + (c.status === "done" ? "green" : c.status === "failed" ? "red" : "yellow")}>{c.status}</span></td>
                <td>{c.attempt_count}</td>
                <td className="muted">{new Date(c.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {cmds.length === 0 && (<tr><td colSpan={6} className="muted">No commands yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
