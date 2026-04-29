"use client";
/* Attendance dashboard — Odoo-style P/A/L/H/W matrix.
   Replicates the look of the second screenshot. */
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";

type Cell = { day: number; status: "P" | "A" | "L" | "H" | "W" | "-"; punches: number };
type Row = {
  employee_id: number;
  employee_code: string;
  full_name: string;
  department: string | null;
  device_pin: string;
  cells: Cell[];
  summary: { P: number; A: number; L: number; H: number; W: number };
};
type Resp = {
  year: number;
  month: number;
  days_in_month: number;
  work_week_days: number;
  holidays: string[];
  rows: Row[];
};

const STATUS_COLOR: Record<Cell["status"], string> = {
  P: "#16a34a",  // green
  A: "#dc2626",  // red
  L: "#7c3aed",  // purple
  H: "#0ea5e9",  // sky
  W: "#94a3b8",  // slate
  "-": "transparent",
};

function dayName(year: number, month: number, day: number) {
  const d = new Date(year, month - 1, day);
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()];
}

export default function AttendanceDashboardPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await api.get<Resp>(`/api/attendance/dashboard?year=${year}&month=${month}`));
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [year, month]);

  function shiftMonth(delta: number) {
    let y = year, m = month + delta;
    if (m > 12) { m = 1; y++; }
    if (m < 1)  { m = 12; y--; }
    setYear(y); setMonth(m);
  }

  const days = useMemo(() => {
    if (!data) return [];
    return Array.from({ length: data.days_in_month }, (_, i) => i + 1);
  }, [data]);

  return (
    <div className="grid">
      <div className="card">
        <div className="row" style={{ alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
          <h2 style={{ margin: 0 }}>Attendance / Leave Dashboard</h2>
          <div className="row" style={{ gap: "0.4rem", alignItems: "center" }}>
            <button className="btn secondary" onClick={() => shiftMonth(-1)}>‹</button>
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{new Date(2000, m - 1, 1).toLocaleString("en", { month: "long" })}</option>
              ))}
            </select>
            <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {[year - 2, year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="btn secondary" onClick={() => shiftMonth(1)}>›</button>
          </div>
        </div>

        <div className="row" style={{ gap: "1rem", marginTop: "0.8rem", flexWrap: "wrap" }}>
          <Legend code="P" label="Present" />
          <Legend code="A" label="Absent" />
          <Legend code="L" label="Leave" />
          <Legend code="H" label="Holiday" />
          <Legend code="W" label="Weekend" />
        </div>
      </div>

      {loading && !data && <div className="muted">Loading…</div>}

      {data && (
        <div className="card" style={{ overflowX: "auto", padding: 0 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ background: "var(--panel-2)" }}>
                <th style={{ padding: "0.6rem", textAlign: "left", position: "sticky", left: 0, background: "var(--panel-2)", zIndex: 2, minWidth: 220 }}>
                  Employee
                </th>
                {days.map((d) => {
                  const dn = dayName(data.year, data.month, d);
                  const isWeekend = dn === "Sat" || dn === "Sun";
                  return (
                    <th key={d} style={{
                      padding: "0.4rem 0.2rem",
                      minWidth: 28, textAlign: "center",
                      color: isWeekend ? "var(--muted)" : "var(--text)",
                      fontWeight: 500,
                    }}>
                      <div style={{ fontSize: "0.7rem", lineHeight: 1 }}>{dn}</div>
                      <div>{d}</div>
                    </th>
                  );
                })}
                <th style={{ padding: "0.4rem", textAlign: "right", minWidth: 70 }}>P</th>
                <th style={{ padding: "0.4rem", textAlign: "right", minWidth: 50 }}>A</th>
                <th style={{ padding: "0.4rem", textAlign: "right", minWidth: 50 }}>L</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.employee_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{
                    padding: "0.5rem 0.6rem", position: "sticky", left: 0,
                    background: "var(--panel)", zIndex: 1,
                  }}>
                    <div><strong>{r.full_name}</strong></div>
                    <div className="muted" style={{ fontSize: "0.75rem" }}>
                      {r.department ?? "—"} · PIN {r.device_pin}
                    </div>
                    <div style={{ marginTop: "0.2rem", display: "flex", gap: "0.25rem" }}>
                      <SummaryPill code="P" n={r.summary.P}/>
                      <SummaryPill code="A" n={r.summary.A}/>
                      <SummaryPill code="L" n={r.summary.L}/>
                      <SummaryPill code="H" n={r.summary.H}/>
                    </div>
                  </td>
                  {r.cells.map((c) => (
                    <td key={c.day} style={{ padding: "2px", textAlign: "center" }}>
                      <CellBox c={c} />
                    </td>
                  ))}
                  <td style={{ padding: "0.4rem", textAlign: "right", color: STATUS_COLOR.P }}>{r.summary.P}</td>
                  <td style={{ padding: "0.4rem", textAlign: "right", color: STATUS_COLOR.A }}>{r.summary.A}</td>
                  <td style={{ padding: "0.4rem", textAlign: "right", color: STATUS_COLOR.L }}>{r.summary.L}</td>
                </tr>
              ))}
              {data.rows.length === 0 && (
                <tr><td colSpan={data.days_in_month + 4} className="muted" style={{ padding: "1rem" }}>
                  No employees in scope for this month.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Legend({ code, label }: { code: Cell["status"]; label: string }) {
  return (
    <span className="row" style={{ gap: "0.3rem", alignItems: "center" }}>
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 24, height: 24, borderRadius: 4, fontWeight: 600, fontSize: "0.7rem",
        border: `1.5px solid ${STATUS_COLOR[code]}`,
        color: STATUS_COLOR[code], background: "transparent",
      }}>{code}</span>
      <span style={{ fontSize: "0.85rem" }}>{label}</span>
    </span>
  );
}

function SummaryPill({ code, n }: { code: Cell["status"]; n: number }) {
  if (n === 0) return null;
  return (
    <span style={{
      fontSize: "0.65rem", padding: "0.05rem 0.3rem", borderRadius: 3,
      background: STATUS_COLOR[code], color: "white", fontWeight: 600,
    }}>{code}-{n}</span>
  );
}

function CellBox({ c }: { c: Cell }) {
  if (c.status === "-") {
    return <span style={{ color: "var(--muted)" }}>·</span>;
  }
  return (
    <span
      title={c.punches ? `${c.punches} punches` : ""}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 24, height: 24, borderRadius: 4, fontSize: "0.65rem", fontWeight: 700,
        border: `1.5px solid ${STATUS_COLOR[c.status]}`,
        color: STATUS_COLOR[c.status], background: "transparent",
      }}
    >
      {c.status}
    </span>
  );
}
