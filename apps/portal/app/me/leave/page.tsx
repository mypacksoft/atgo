"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Row = {
  id: number; leave_type: string; start_date: string; end_date: string;
  half_day: boolean; reason: string | null; status: string;
};

export default function MyLeave() {
  const [rows, setRows] = useState<Row[]>([]);
  const [form, setForm] = useState({ leave_type: "annual", start_date: "", end_date: "", half_day: false, reason: "" });
  const [msg, setMsg] = useState("");

  function reload() { api.get<Row[]>("/api/employee/leave-requests", "emp").then(setRows); }
  useEffect(reload, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setMsg("");
    try {
      await api.post("/api/employee/leave-requests", form, "emp");
      setForm({ leave_type: "annual", start_date: "", end_date: "", half_day: false, reason: "" });
      setMsg("Submitted ✓");
      reload();
    } catch (err: any) { setMsg(err?.message || "failed"); }
  }

  return (
    <main style={{ maxWidth: 540, margin: "0 auto", padding: "1rem" }}>
      <a href="/me">← Back</a>
      <h2>Leave requests</h2>
      <div className="card">
        <form onSubmit={submit} className="grid">
          <select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
            <option value="annual">Annual</option>
            <option value="sick">Sick</option>
            <option value="unpaid">Unpaid</option>
            <option value="other">Other</option>
          </select>
          <div className="grid cols-2">
            <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} required />
            <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} required />
          </div>
          <label className="row"><input type="checkbox" checked={form.half_day} onChange={(e) => setForm({ ...form, half_day: e.target.checked })} /> Half day</label>
          <textarea rows={3} placeholder="Reason (optional)" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          <button className="btn">Submit</button>
          {msg && <div className="muted">{msg}</div>}
        </form>
      </div>
      <h3>My requests</h3>
      <table className="table">
        <thead><tr><th>Type</th><th>Dates</th><th>Status</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.leave_type}{r.half_day ? " (½)" : ""}</td>
              <td>{r.start_date} → {r.end_date}</td>
              <td><span className={"badge " + (r.status === "approved" ? "green" : r.status === "rejected" ? "red" : "yellow")}>{r.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
