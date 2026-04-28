"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { ApiKeyRow } from "../../../lib/types";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [name, setName] = useState("Odoo plugin");
  const [shown, setShown] = useState<string | null>(null);
  const [error, setError] = useState("");

  function reload() { api.get<ApiKeyRow[]>("/api/api-keys").then(setKeys); }
  useEffect(reload, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const r = await api.post<{ full_key: string }>("/api/api-keys", { name });
      setShown(r.full_key);
      setName("Odoo plugin");
      reload();
    } catch (err: any) { setError(err?.message); }
  }
  async function revoke(id: number) {
    if (!confirm("Revoke this key?")) return;
    await api.delete(`/api/api-keys/${id}`);
    reload();
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Create API key</h2>
        <form onSubmit={create} className="row">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" required style={{ flex: 1 }} />
          <button className="btn">Create</button>
        </form>
        {shown && (
          <div className="okbox" style={{ marginTop: "1rem" }}>
            <strong>Copy this key now</strong> — it won't be shown again:
            <pre style={{ overflow: "auto" }}>{shown}</pre>
            <button className="btn secondary" onClick={() => navigator.clipboard.writeText(shown)}>Copy</button>{" "}
            <button className="btn secondary" onClick={() => setShown(null)}>Dismiss</button>
          </div>
        )}
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>Name</th><th>Prefix</th><th>Last used</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td><code className="kbd">{k.prefix}…</code></td>
                <td className="muted">{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}</td>
                <td>{k.revoked_at ? <span className="badge red">revoked</span> : <span className="badge green">active</span>}</td>
                <td>{!k.revoked_at && <button className="btn secondary" onClick={() => revoke(k.id)}>Revoke</button>}</td>
              </tr>
            ))}
            {keys.length === 0 && (<tr><td colSpan={5} className="muted">No API keys yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
