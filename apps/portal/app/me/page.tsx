"use client";
import { useEffect, useState } from "react";
import { api, clearToken } from "../../lib/api";

type Today = {
  work_date: string;
  first_check_in: string | null;
  last_check_out: string | null;
  total_punches: number;
  worked_minutes: number | null;
  status: string;
};
type Me = {
  employee_id: number;
  employee_code: string;
  full_name: string;
  email: string | null;
};

export default function MeHome() {
  const [me, setMe] = useState<Me | null>(null);
  const [today, setToday] = useState<Today | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Me>("/api/employee/me", "emp"),
      api.get<Today>("/api/employee/attendance/today", "emp"),
    ])
      .then(([m, t]) => { setMe(m); setToday(t); })
      .catch(() => { window.location.href = "/me/login"; });
  }, []);

  if (!me || !today) return null;
  const hours = today.worked_minutes ? Math.floor(today.worked_minutes / 60) + "h " + (today.worked_minutes % 60) + "m" : "—";

  return (
    <main style={{ maxWidth: 540, margin: "0 auto", padding: "1rem" }}>
      <header className="row" style={{ justifyContent: "space-between", padding: "0.5rem 0" }}>
        <div>
          <h2 style={{ margin: 0 }}>Hi, {me.full_name.split(" ")[0]}</h2>
          <small className="muted">{me.employee_code} · {me.email || "no email on file"}</small>
        </div>
        <button className="btn secondary" onClick={() => { clearToken("emp"); window.location.href = "/me/login"; }}>
          Sign out
        </button>
      </header>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Today</h3>
        <p className="muted" style={{ marginTop: 0 }}>{today.work_date}</p>
        <div className="grid cols-2">
          <div><div className="muted">First in</div><strong>{today.first_check_in ? new Date(today.first_check_in).toLocaleTimeString() : "—"}</strong></div>
          <div><div className="muted">Last out</div><strong>{today.last_check_out ? new Date(today.last_check_out).toLocaleTimeString() : "—"}</strong></div>
          <div><div className="muted">Punches</div><strong>{today.total_punches}</strong></div>
          <div><div className="muted">Worked</div><strong>{hours}</strong></div>
        </div>
        <div style={{ marginTop: "0.75rem" }}>
          <span className={"badge " + (today.status === "present" ? "green" : today.status === "missing_checkout" ? "yellow" : "red")}>
            {today.status}
          </span>
        </div>
      </div>

      <div className="row" style={{ marginTop: "1rem", justifyContent: "space-around" }}>
        <a href="/me/timesheet" className="btn secondary">Monthly</a>
        <a href="/me/correction" className="btn secondary">Correction</a>
        <a href="/me/leave" className="btn secondary">Leave</a>
      </div>

      {error && <div className="errbox">{error}</div>}
    </main>
  );
}
