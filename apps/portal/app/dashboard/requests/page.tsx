"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Correction = {
  id: number; employee_code: string; full_name: string; work_date: string;
  requested_check_in: string | null; requested_check_out: string | null;
  reason: string; status: string; created_at: string;
};
type Leave = {
  id: number; employee_code: string; full_name: string; leave_type: string;
  start_date: string; end_date: string; half_day: boolean; reason: string | null;
  status: string; created_at: string;
};

export default function RequestsPage() {
  const [tab, setTab] = useState<"correction" | "leave">("correction");
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);

  function reload() {
    api.get<Correction[]>("/api/hr/correction-requests?status=pending").then(setCorrections);
    api.get<Leave[]>("/api/hr/leave-requests?status=pending").then(setLeaves);
  }
  useEffect(reload, []);

  async function review(kind: "correction" | "leave", id: number, decision: "approved" | "rejected") {
    const notes = prompt(`Notes for ${decision}:`) || "";
    const path = kind === "correction" ? "correction-requests" : "leave-requests";
    await api.post(`/api/hr/${path}/${id}/review`, { decision, notes });
    reload();
  }

  return (
    <div className="grid">
      <div className="row">
        <button className={"btn " + (tab === "correction" ? "" : "secondary")} onClick={() => setTab("correction")}>
          Corrections ({corrections.length})
        </button>
        <button className={"btn " + (tab === "leave" ? "" : "secondary")} onClick={() => setTab("leave")}>
          Leave ({leaves.length})
        </button>
      </div>

      {tab === "correction" && (
        <div className="card">
          <table className="table">
            <thead><tr><th>Employee</th><th>Date</th><th>Requested</th><th>Reason</th><th>Submitted</th><th></th></tr></thead>
            <tbody>
              {corrections.map((c) => (
                <tr key={c.id}>
                  <td>{c.full_name} <span className="muted">({c.employee_code})</span></td>
                  <td>{c.work_date}</td>
                  <td>
                    {c.requested_check_in && <div>In: {new Date(c.requested_check_in).toLocaleTimeString()}</div>}
                    {c.requested_check_out && <div>Out: {new Date(c.requested_check_out).toLocaleTimeString()}</div>}
                  </td>
                  <td>{c.reason}</td>
                  <td className="muted">{new Date(c.created_at).toLocaleString()}</td>
                  <td className="row">
                    <button className="btn" onClick={() => review("correction", c.id, "approved")}>Approve</button>
                    <button className="btn secondary" onClick={() => review("correction", c.id, "rejected")}>Reject</button>
                  </td>
                </tr>
              ))}
              {corrections.length === 0 && (<tr><td colSpan={6} className="muted">No pending corrections.</td></tr>)}
            </tbody>
          </table>
        </div>
      )}

      {tab === "leave" && (
        <div className="card">
          <table className="table">
            <thead><tr><th>Employee</th><th>Type</th><th>From</th><th>To</th><th>Reason</th><th></th></tr></thead>
            <tbody>
              {leaves.map((l) => (
                <tr key={l.id}>
                  <td>{l.full_name} <span className="muted">({l.employee_code})</span></td>
                  <td>{l.leave_type}{l.half_day ? " (½)" : ""}</td>
                  <td>{l.start_date}</td>
                  <td>{l.end_date}</td>
                  <td>{l.reason || "—"}</td>
                  <td className="row">
                    <button className="btn" onClick={() => review("leave", l.id, "approved")}>Approve</button>
                    <button className="btn secondary" onClick={() => review("leave", l.id, "rejected")}>Reject</button>
                  </td>
                </tr>
              ))}
              {leaves.length === 0 && (<tr><td colSpan={6} className="muted">No pending leave.</td></tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
