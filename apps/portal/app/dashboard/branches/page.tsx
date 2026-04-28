"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Branch } from "../../../lib/types";

export default function BranchesPage() {
  const [items, setItems] = useState<Branch[]>([]);
  const [form, setForm] = useState({ code: "", name: "", timezone: "", address: "" });
  const [error, setError] = useState("");

  function reload() {
    api.get<Branch[]>("/api/branches").then(setItems);
  }
  useEffect(reload, []);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.post("/api/branches", { ...form, is_active: true });
      setForm({ code: "", name: "", timezone: "", address: "" });
      reload();
    } catch (err: any) { setError(err?.message); }
  }
  async function del(id: number) { await api.delete(`/api/branches/${id}`); reload(); }

  return (
    <div className="grid">
      <div className="card">
        <h2>Add branch</h2>
        <form onSubmit={add} className="grid cols-3">
          <input placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input placeholder="Timezone (e.g. Asia/Ho_Chi_Minh)" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          <input placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} style={{ gridColumn: "span 2" }} />
          <button className="btn">Add</button>
        </form>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>Code</th><th>Name</th><th>TZ</th><th>Address</th><th></th></tr></thead>
          <tbody>
            {items.map((b) => (
              <tr key={b.id}>
                <td>{b.code}</td><td>{b.name}</td>
                <td className="muted">{b.timezone || "—"}</td>
                <td className="muted">{b.address || "—"}</td>
                <td><button className="btn secondary" onClick={() => del(b.id)}>Delete</button></td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={5} className="muted">No branches yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
