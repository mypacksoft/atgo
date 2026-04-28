"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Employee, Branch, Department } from "../../../lib/types";

export default function EmployeesPage() {
  const [emps, setEmps] = useState<Employee[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ employee_code: "", device_pin: "", full_name: "", email: "", phone: "", branch_id: "", department_id: "" });

  function reload() {
    Promise.all([
      api.get<Employee[]>("/api/employees"),
      api.get<Branch[]>("/api/branches"),
      api.get<Department[]>("/api/departments"),
    ]).then(([e, b, d]) => { setEmps(e); setBranches(b); setDepts(d); });
  }
  useEffect(() => { reload(); }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await api.post("/api/employees", {
        employee_code: form.employee_code,
        device_pin: form.device_pin,
        full_name: form.full_name,
        email: form.email || null,
        phone: form.phone || null,
        branch_id: form.branch_id ? parseInt(form.branch_id) : null,
        department_id: form.department_id ? parseInt(form.department_id) : null,
      });
      setForm({ employee_code: "", device_pin: "", full_name: "", email: "", phone: "", branch_id: "", department_id: "" });
      reload();
    } catch (err: any) {
      setError(err?.message || "create failed");
    } finally { setBusy(false); }
  }

  async function invite(eid: number) {
    try {
      const r = await api.post<{ invite_url: string; expires_at: string }>(`/api/hr/employees/${eid}/invite`);
      prompt("Invite link (copy & send):", r.invite_url);
    } catch (err: any) {
      alert(err?.message || "invite failed");
    }
  }

  async function disable(eid: number) {
    if (!confirm("Set inactive?")) return;
    await api.delete(`/api/employees/${eid}`);
    reload();
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Add employee</h2>
        <form onSubmit={add} className="grid cols-3">
          <input placeholder="Employee code" value={form.employee_code} onChange={(e) => setForm({ ...form, employee_code: e.target.value })} required />
          <input placeholder="Device PIN" value={form.device_pin} onChange={(e) => setForm({ ...form, device_pin: e.target.value })} required />
          <input placeholder="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          <input placeholder="Email (optional, for self-service)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <select value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })}>
            <option value="">— Branch —</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
            <option value="">— Department —</option>
            {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button className="btn" disabled={busy}>{busy ? "Adding…" : "Add"}</button>
        </form>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr><th>Code</th><th>PIN</th><th>Name</th><th>Email</th><th>Active</th><th></th></tr>
          </thead>
          <tbody>
            {emps.map((e) => (
              <tr key={e.id}>
                <td>{e.employee_code}</td>
                <td><span className="kbd">{e.device_pin}</span></td>
                <td>{e.full_name}</td>
                <td className="muted">{e.email || "—"}</td>
                <td>{e.is_active ? <span className="badge green">yes</span> : <span className="badge red">no</span>}</td>
                <td className="row">
                  <button className="btn secondary" onClick={() => invite(e.id)}>Invite</button>
                  <button className="btn secondary" onClick={() => disable(e.id)}>Disable</button>
                </td>
              </tr>
            ))}
            {emps.length === 0 && (<tr><td colSpan={6} className="muted">No employees yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
