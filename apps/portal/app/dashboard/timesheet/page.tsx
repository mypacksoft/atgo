"use client";
/* Bảng chấm công — Phuc Hao-style grid: employee × day, value = worked hours.
   Plus per-employee detail drilldown + Excel export. */
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";
import type { TimesheetRow } from "../../../lib/types";

const fmtHours = (mins: number | null | undefined) =>
  mins == null ? "" : (mins / 60).toFixed(0);

function isoDay(s: string): number {
  return parseInt(s.slice(8, 10), 10);
}

export default function TimesheetPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [rows, setRows] = useState<TimesheetRow[]>([]);
  const [view, setView] = useState<"grid" | "detail">("grid");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setRows(await api.get<TimesheetRow[]>(`/api/attendance/timesheet?year=${year}&month=${month}`));
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [year, month]);

  function downloadXlsx() {
    const token = typeof window !== "undefined" ? localStorage.getItem("atgo_token") : null;
    fetch(`/api/attendance/timesheet.xlsx?year=${year}&month=${month}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.blob())
      .then((b) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `timesheet-${year}-${String(month).padStart(2, "0")}.xlsx`;
        a.click();
      });
  }

  // Days in month
  const daysInMonth = useMemo(() => new Date(year, month, 0).getDate(), [year, month]);
  const days = useMemo(() => Array.from({ length: daysInMonth }, (_, i) => i + 1), [daysInMonth]);

  // Pivot: employee_id → { day → minutes }, plus metadata
  type Pivot = {
    employee_id: number;
    employee_code: string;
    full_name: string;
    days: Record<number, TimesheetRow>;
    total_minutes: number;
  };
  const pivots = useMemo<Pivot[]>(() => {
    const map = new Map<number, Pivot>();
    for (const r of rows) {
      let p = map.get(r.employee_id);
      if (!p) {
        p = {
          employee_id: r.employee_id,
          employee_code: r.employee_code,
          full_name: r.full_name,
          days: {},
          total_minutes: 0,
        };
        map.set(r.employee_id, p);
      }
      const d = isoDay(r.work_date);
      p.days[d] = r;
      p.total_minutes += r.worked_minutes ?? 0;
    }
    return Array.from(map.values()).sort((a, b) => a.employee_code.localeCompare(b.employee_code));
  }, [rows]);

  function shiftMonth(delta: number) {
    let y = year, m = month + delta;
    if (m > 12) { m = 1; y++; } if (m < 1) { m = 12; y--; }
    setYear(y); setMonth(m);
  }

  return (
    <div className="grid">
      <div className="card">
        <h2 style={{ margin: "0 0 0.5rem 0" }}>Bảng chấm công</h2>
        <div className="row" style={{ alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
          <button className="btn secondary" onClick={() => shiftMonth(-1)}>‹</button>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>Tháng {m}</option>
            ))}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button className="btn secondary" onClick={() => shiftMonth(1)}>›</button>
          <span style={{ flex: 1 }}/>
          <div className="row" style={{ gap: "0.3rem" }}>
            <button className={"btn " + (view === "grid" ? "" : "secondary")} onClick={() => setView("grid")}>Grid</button>
            <button className={"btn " + (view === "detail" ? "" : "secondary")} onClick={() => setView("detail")}>Detail</button>
          </div>
          <button className="btn" onClick={downloadXlsx}>📥 Excel</button>
        </div>
      </div>

      {loading && !rows.length && <div className="muted">Loading…</div>}

      {/* Grid view: hours per day */}
      {view === "grid" && (
        <div className="card" style={{ overflowX: "auto", padding: 0 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ background: "var(--panel-2)" }}>
                <th style={{ padding: "0.5rem", textAlign: "left", position: "sticky", left: 0, background: "var(--panel-2)", zIndex: 2, minWidth: 60 }}>Mã chấm công</th>
                <th style={{ padding: "0.5rem", textAlign: "left", position: "sticky", left: 60, background: "var(--panel-2)", zIndex: 2, minWidth: 200 }}>Họ tên</th>
                {days.map((d) => {
                  const dt = new Date(year, month - 1, d);
                  const dow = dt.getDay();
                  const weekend = dow === 0 || dow === 6;
                  return (
                    <th key={d} style={{
                      padding: "0.3rem 0.2rem",
                      minWidth: 32, textAlign: "center",
                      color: weekend ? "var(--muted)" : undefined,
                      fontWeight: 500,
                    }}>{d}</th>
                  );
                })}
                <th style={{ padding: "0.4rem", textAlign: "right", minWidth: 60, background: "var(--panel-2)" }}>Total h</th>
              </tr>
            </thead>
            <tbody>
              {pivots.map((p) => (
                <tr key={p.employee_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "0.4rem 0.5rem", position: "sticky", left: 0, background: "var(--panel)", zIndex: 1 }}>
                    <code className="kbd">{p.employee_code}</code>
                  </td>
                  <td style={{ padding: "0.4rem 0.5rem", position: "sticky", left: 60, background: "var(--panel)", zIndex: 1, fontWeight: 500 }}>
                    {p.full_name}
                  </td>
                  {days.map((d) => {
                    const cell = p.days[d];
                    const dt = new Date(year, month - 1, d);
                    const dow = dt.getDay();
                    const weekend = dow === 0 || dow === 6;
                    if (!cell) {
                      return (
                        <td key={d} style={{
                          padding: "0.3rem 0", textAlign: "center",
                          color: weekend ? "var(--muted)" : "var(--danger)",
                          fontSize: "0.8rem",
                        }}>{weekend ? "—" : "0"}</td>
                      );
                    }
                    const hours = fmtHours(cell.worked_minutes);
                    const missing = cell.status === "missing_checkout";
                    return (
                      <td key={d}
                          title={`${cell.first_check_in ? new Date(cell.first_check_in).toLocaleTimeString() : "—"} → ${cell.last_check_out ? new Date(cell.last_check_out).toLocaleTimeString() : "—"} (${cell.total_punches} punches)`}
                          style={{
                            padding: "0.3rem 0", textAlign: "center",
                            background: missing ? "rgba(217,119,6,0.18)" : weekend ? "rgba(148,163,184,0.08)" : undefined,
                            color: missing ? "var(--warn)" : weekend ? "var(--muted)" : undefined,
                          }}>
                        {hours || "0"}
                      </td>
                    );
                  })}
                  <td style={{ padding: "0.4rem", textAlign: "right", fontWeight: 600 }}>
                    {fmtHours(p.total_minutes)}
                  </td>
                </tr>
              ))}
              {pivots.length === 0 && (
                <tr><td colSpan={daysInMonth + 3} className="muted" style={{ padding: "1rem", textAlign: "center" }}>
                  Không có dữ liệu cho tháng này.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail view: expandable per employee */}
      {view === "detail" && (
        <div className="card">
          {pivots.map((p) => (
            <details key={p.employee_code} style={{ marginBottom: "0.75rem" }}>
              <summary>
                <strong>{p.full_name}</strong>
                <span className="muted"> — {p.employee_code} — {fmtHours(p.total_minutes)}h tháng</span>
              </summary>
              <table className="table">
                <thead><tr><th>Ngày</th><th>Vào</th><th>Ra</th><th>Lượt</th><th>Phút</th><th>Trạng thái</th></tr></thead>
                <tbody>
                  {Object.values(p.days).map((r, i) => (
                    <tr key={i}>
                      <td>{r.work_date}</td>
                      <td>{r.first_check_in ? new Date(r.first_check_in).toLocaleTimeString() : "—"}</td>
                      <td>{r.last_check_out ? new Date(r.last_check_out).toLocaleTimeString() : "—"}</td>
                      <td>{r.total_punches}</td>
                      <td>{r.worked_minutes ?? "—"}</td>
                      <td>
                        <span className={"badge " +
                          (r.status === "present" ? "green"
                            : r.status === "missing_checkout" ? "yellow" : "red")}>
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ))}
          {pivots.length === 0 && <p className="muted">Không có dữ liệu.</p>}
        </div>
      )}
    </div>
  );
}
