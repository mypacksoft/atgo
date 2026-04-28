"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { TimesheetRow } from "../../../lib/types";

export default function MyTimesheet() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [rows, setRows] = useState<TimesheetRow[]>([]);

  useEffect(() => {
    api.get<TimesheetRow[]>(`/api/employee/timesheet?year=${year}&month=${month}`, "emp").then(setRows);
  }, [year, month]);

  return (
    <main style={{ maxWidth: 540, margin: "0 auto", padding: "1rem" }}>
      <a href="/me">← Back</a>
      <h2>My timesheet</h2>
      <div className="row">
        <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value))} style={{ width: 100 }} />
        <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(parseInt(e.target.value))} style={{ width: 80 }} />
      </div>
      <table className="table" style={{ marginTop: "1rem" }}>
        <thead><tr><th>Date</th><th>In</th><th>Out</th><th>Hours</th><th></th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.work_date}</td>
              <td>{r.first_check_in ? new Date(r.first_check_in).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</td>
              <td>{r.last_check_out ? new Date(r.last_check_out).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</td>
              <td>{r.worked_minutes ? Math.round(r.worked_minutes / 60 * 10) / 10 + "h" : "—"}</td>
              <td><span className={"badge " + (r.status === "present" ? "green" : r.status === "missing_checkout" ? "yellow" : "red")}>{r.status}</span></td>
            </tr>
          ))}
          {rows.length === 0 && (<tr><td colSpan={5} className="muted">No data.</td></tr>)}
        </tbody>
      </table>
    </main>
  );
}
