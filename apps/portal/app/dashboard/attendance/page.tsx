"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { AttendanceLog } from "../../../lib/types";

export default function AttendancePage() {
  const [logs, setLogs] = useState<AttendanceLog[]>([]);
  const [from, setFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10);
  });
  const [to, setTo] = useState(() => new Date().toISOString().slice(0, 10));

  function load() {
    api.get<AttendanceLog[]>(`/api/attendance/logs?from=${from}&to=${to}&limit=500`).then(setLogs);
  }
  useEffect(load, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="grid">
      <div className="card row">
        <label>From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <button className="btn" onClick={load}>Apply</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>Time</th><th>PIN</th><th>Employee</th><th>State</th><th>Verify</th></tr></thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td>{new Date(l.punched_at).toLocaleString()}</td>
                <td><span className="kbd">{l.device_pin}</span></td>
                <td>{l.employee_id ? `#${l.employee_id}` : <span className="badge yellow">unmapped</span>}</td>
                <td>{l.punch_state ?? "—"}</td>
                <td>{l.verify_type ?? "—"}</td>
              </tr>
            ))}
            {logs.length === 0 && (<tr><td colSpan={5} className="muted">No logs in range.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
