"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type E = { id: number; provider: string; event_type: string; signature_verified: boolean; processed_at: string | null; error_message: string | null; created_at: string };

export default function AdminBilling() {
  const [items, setItems] = useState<E[]>([]);
  const [provider, setProvider] = useState("");
  function load() {
    api.get<E[]>(`/api/admin/billing-events${provider ? `?provider=${provider}` : ""}`).then(setItems);
  }
  useEffect(load, []);  // eslint-disable-line

  return (
    <div className="grid">
      <div className="row">
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="">All providers</option>
          <option value="paddle">Paddle</option>
          <option value="vnpay">VNPay</option>
          <option value="razorpay">Razorpay</option>
          <option value="momo">MoMo</option>
        </select>
        <button className="btn" onClick={load}>Apply</button>
      </div>
      <div className="card">
        <table className="table">
          <thead><tr><th>ID</th><th>Provider</th><th>Type</th><th>Verified</th><th>Processed</th><th>Error</th><th>When</th></tr></thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id}>
                <td>{e.id}</td><td>{e.provider}</td><td>{e.event_type}</td>
                <td>{e.signature_verified ? <span className="badge green">yes</span> : <span className="badge red">no</span>}</td>
                <td>{e.processed_at ? new Date(e.processed_at).toLocaleString() : <span className="badge yellow">pending</span>}</td>
                <td className="muted">{e.error_message || "—"}</td>
                <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {items.length === 0 && (<tr><td colSpan={7} className="muted">No events.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
