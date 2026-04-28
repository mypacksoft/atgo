"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Department } from "../../../lib/types";

export default function DepartmentsPage() {
  const [items, setItems] = useState<Department[]>([]);
  const [form, setForm] = useState({ code: "", name: "", parent_id: "" });
  const [error, setError] = useState("");

  function reload() { api.get<Department[]>("/api/departments").then(setItems); }
  useEffect(reload, []);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.post("/api/departments", {
        code: form.code, name: form.name,
        parent_id: form.parent_id ? parseInt(form.parent_id) : null,
        is_active: true,
      });
      setForm({ code: "", name: "", parent_id: "" });
      reload();
    } catch (err: any) { setError(err?.message); }
  }
  async function del(id: number) { await api.delete(`/api/departments/${id}`); reload(); }

  return (
    <div className="grid">
      <div className="card">
        <h2>Add department</h2>
        <form onSubmit={add} className="row">
          <input placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <select value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })}>
            <option value="">— Parent (optional) —</option>
            {items.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button className="btn">Add</button>
        </form>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>Code</th><th>Name</th><th>Parent</th><th></th></tr></thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td>{d.code}</td><td>{d.name}</td>
                <td className="muted">{d.parent_id ? items.find((x) => x.id === d.parent_id)?.name : "—"}</td>
                <td><button className="btn secondary" onClick={() => del(d.id)}>Delete</button></td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={4} className="muted">No departments yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
