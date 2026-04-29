"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type PresenceRow = {
  employee_id: number;
  employee_code: string;
  full_name: string;
  device_pin: string;
  device_name: string | null;
  device_code: string | null;
  department_name: string | null;
  last_in_at: string;
};

function elapsed(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function PresencePage() {
  const [rows, setRows] = useState<PresenceRow[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try { setRows(await api.get<PresenceRow[]>("/api/attendance/presence")); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="grid">
      <div className="card">
        <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Nhân viên hiện diện</h2>
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            {rows.length} đang làm việc · auto-refresh 30s
          </span>
        </div>
        <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
          Danh sách nhân viên đã chấm công vào nhưng chưa chấm công ra.
        </p>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Mã NV</th>
              <th>Họ tên</th>
              <th>Phòng ban</th>
              <th>PIN</th>
              <th>Vào lúc</th>
              <th style={{ textAlign: "right" }}>Thời gian</th>
              <th>Máy chấm công</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.employee_id}>
                <td><code className="kbd">{r.employee_code}</code></td>
                <td><strong>{r.full_name}</strong></td>
                <td className="muted">{r.department_name ?? "—"}</td>
                <td><code className="kbd">{r.device_pin}</code></td>
                <td className="muted">{new Date(r.last_in_at).toLocaleString()}</td>
                <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  <span className="badge green">{elapsed(r.last_in_at)}</span>
                </td>
                <td className="muted">{r.device_name ?? "—"}{r.device_code ? ` (${r.device_code})` : ""}</td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr><td colSpan={7} className="muted" style={{ padding: "1rem", textAlign: "center" }}>
                Không có nhân viên nào đang làm việc.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
