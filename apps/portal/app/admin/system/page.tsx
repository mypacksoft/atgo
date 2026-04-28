"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Stats = {
  row_counts: { t: string; n: number }[];
  database: { size: string; size_bytes: number };
  largest_tables: { name: string; size: string; size_bytes: number }[];
  postgres_version: string;
};

export default function AdminSystemPage() {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => { api.get<Stats>("/api/admin/system/stats").then(setS); }, []);

  if (!s) return <div className="muted">Loading…</div>;

  return (
    <div className="grid">
      <h1>System</h1>
      <div className="card">
        <h3>Database</h3>
        <p>PostgreSQL <strong>{s.postgres_version}</strong> · total size <strong>{s.database?.size}</strong></p>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Row counts</h3>
          <table className="table">
            <thead><tr><th>Table</th><th style={{ textAlign: "right" }}>Rows</th></tr></thead>
            <tbody>
              {s.row_counts?.map((r) => (
                <tr key={r.t}>
                  <td>{r.t}</td>
                  <td style={{ textAlign: "right" }}>{Number(r.n).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>Largest tables</h3>
          <table className="table">
            <thead><tr><th>Name</th><th style={{ textAlign: "right" }}>Size</th></tr></thead>
            <tbody>
              {s.largest_tables?.map((r) => (
                <tr key={r.name}>
                  <td>{r.name}</td>
                  <td style={{ textAlign: "right" }}>{r.size}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
