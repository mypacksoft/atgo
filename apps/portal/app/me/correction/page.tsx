"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Row = {
  id: number; work_date: string;
  requested_check_in: string | null; requested_check_out: string | null;
  reason: string; status: string; review_notes: string | null;
};

export default function MyCorrection() {
  const [rows, setRows] = useState<Row[]>([]);
  const [form, setForm] = useState({ work_date: "", check_in: "", check_out: "", reason: "" });
  const [msg, setMsg] = useState("");

  function reload() { api.get<Row[]>("/api/employee/correction-requests", "emp").then(setRows); }
  useEffect(reload, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setMsg("");
    try {
      await api.post("/api/employee/correction-requests", {
        work_date: form.work_date,
        requested_check_in: form.check_in ? new Date(`${form.work_date}T${form.check_in}`).toISOString() : null,
        requested_check_out: form.check_out ? new Date(`${form.work_date}T${form.check_out}`).toISOString() : null,
        reason: form.reason,
      }, "emp");
      setForm({ work_date: "", check_in: "", check_out: "", reason: "" });
      setMsg("Submitted ✓");
      reload();
    } catch (err: any) { setMsg(err?.message || "failed"); }
  }

  return (
    <main style={{ maxWidth: 540, margin: "0 auto", padding: "1rem" }}>
      <a href="/me">← Back</a>
      <h2>Correction requests</h2>
      <div className="card">
        <form onSubmit={submit} className="grid">
          <input type="date" value={form.work_date} onChange={(e) => setForm({ ...form, work_date: e.target.value })} required />
          <div className="grid cols-2">
            <input type="time" placeholder="Check in" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} />
            <input type="time" placeholder="Check out" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} />
          </div>
          <textarea rows={3} placeholder="Reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required />
          <button className="btn">Submit</button>
          {msg && <div className="muted">{msg}</div>}
        </form>
      </div>
      <h3>My past requests</h3>
      <table className="table">
        <thead><tr><th>Date</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.work_date}</td>
              <td><span className={"badge " + (r.status === "approved" ? "green" : r.status === "rejected" ? "red" : "yellow")}>{r.status}</span></td>
              <td className="muted">{r.review_notes || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
