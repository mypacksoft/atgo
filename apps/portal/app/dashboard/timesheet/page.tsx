"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { TimesheetRow } from "../../../lib/types";

export default function TimesheetPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [rows, setRows] = useState<TimesheetRow[]>([]);

  useEffect(() => {
    api.get<TimesheetRow[]>(`/api/attendance/timesheet?year=${year}&month=${month}`).then(setRows);
  }, [year, month]);

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

  // Group rows by employee
  const byEmp = rows.reduce<Record<string, { name: string; code: string; rows: TimesheetRow[] }>>((acc, r) => {
    const k = String(r.employee_id);
    acc[k] ??= { name: r.full_name, code: r.employee_code, rows: [] };
    acc[k].rows.push(r);
    return acc;
  }, {});

  return (
    <div className="grid">
      <div className="card row">
        <label>Year <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value))} style={{ width: 100 }} /></label>
        <label>Month <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(parseInt(e.target.value))} style={{ width: 80 }} /></label>
        <button className="btn" onClick={downloadXlsx}>Download Excel</button>
      </div>
      <div className="card">
        {Object.values(byEmp).map((e) => (
          <details key={e.code} style={{ marginBottom: "0.75rem" }}>
            <summary><strong>{e.name}</strong> <span className="muted">({e.code})</span></summary>
            <table className="table">
              <thead><tr><th>Date</th><th>First in</th><th>Last out</th><th>Punches</th><th>Worked min</th><th>Status</th></tr></thead>
              <tbody>
                {e.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.work_date}</td>
                    <td>{r.first_check_in ? new Date(r.first_check_in).toLocaleTimeString() : "—"}</td>
                    <td>{r.last_check_out ? new Date(r.last_check_out).toLocaleTimeString() : "—"}</td>
                    <td>{r.total_punches}</td>
                    <td>{r.worked_minutes ?? "—"}</td>
                    <td><span className={"badge " + (r.status === "present" ? "green" : r.status === "missing_checkout" ? "yellow" : "red")}>{r.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ))}
        {rows.length === 0 && <p className="muted">No data for this month.</p>}
      </div>
    </div>
  );
}
