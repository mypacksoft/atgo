"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../../lib/api";

type AdminUser = {
  id: number;
  email: string;
  full_name: string | null;
  is_super_admin: boolean;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  workspace_count: number;
  primary_tenant_id: number | null;
  primary_tenant_slug: string | null;
  primary_tenant_plan: string | null;
};

const PLAN_BADGE: Record<string, string> = {
  free:     "red",
  starter:  "yellow",
  business: "green",
  scale:    "green",
  hr_pro:   "green",
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [q, setQ] = useState("");
  const [superOnly, setSuperOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (superOnly) params.set("super_only", "true");
      const data = await api.get<AdminUser[]>(`/api/admin/users?${params}`);
      setUsers(data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function promote(id: number) {
    await api.post(`/api/admin/users/${id}/promote`);
    load();
  }
  async function demote(id: number) {
    if (!confirm("Demote this user from super-admin?")) return;
    try { await api.post(`/api/admin/users/${id}/demote`); load(); }
    catch (e: any) { alert(e?.message || "demote failed"); }
  }
  async function setActive(id: number, is_active: boolean) {
    await api.post(`/api/admin/users/${id}/set-active`, { is_active });
    load();
  }
  async function resetPassword(id: number) {
    const np = prompt("New password (>=8 chars):");
    if (!np || np.length < 8) return;
    try { await api.post(`/api/admin/users/${id}/reset-password`, { new_password: np });
          alert("Password reset."); }
    catch (e: any) { alert(e?.message || "reset failed"); }
  }

  return (
    <div className="grid">
      <h1>Users</h1>

      <div className="card">
        <div className="row">
          <input placeholder="Search email or name…" value={q} onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && load()} style={{ flex: 1 }} />
          <label className="row" style={{ gap: "0.4rem" }}>
            <input type="checkbox" checked={superOnly} onChange={(e) => setSuperOnly(e.target.checked)} />
            Super admins only
          </label>
          <button className="btn" onClick={load} disabled={loading}>Search</button>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>ID</th><th>Email</th><th>Name</th><th>Role</th><th>Status</th>
            <th>Workspace</th><th>Plan</th><th>Last login</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.email}</td>
              <td>{u.full_name || <span className="muted">—</span>}</td>
              <td>{u.is_super_admin
                ? <span className="badge red">super-admin</span>
                : <span className="badge">tenant user</span>}</td>
              <td>{u.is_active
                ? <span className="badge green">active</span>
                : <span className="badge">disabled</span>}</td>
              <td>
                {u.primary_tenant_slug ? (
                  <Link href={`/admin/tenants/${u.primary_tenant_id}`}>
                    <code className="kbd">{u.primary_tenant_slug}</code>
                  </Link>
                ) : <span className="muted">—</span>}
                {u.workspace_count > 1 && (
                  <span className="muted" style={{ fontSize: "0.75rem" }}> +{u.workspace_count - 1}</span>
                )}
              </td>
              <td>
                {u.primary_tenant_plan ? (
                  <span className="row" style={{ gap: "0.3rem", alignItems: "center" }}>
                    <span className={"badge " + (PLAN_BADGE[u.primary_tenant_plan] ?? "")}>
                      {u.primary_tenant_plan}
                    </span>
                    {u.primary_tenant_plan === "free" && u.primary_tenant_id && (
                      <Link
                        href={`/admin/tenants/${u.primary_tenant_id}`}
                        className="badge"
                        style={{
                          textDecoration: "none",
                          background: "var(--accent)",
                          color: "white",
                          fontSize: "0.7rem",
                        }}
                        title="Free tier — upgrade in tenant detail"
                      >
                        upgrade →
                      </Link>
                    )}
                  </span>
                ) : <span className="muted">—</span>}
              </td>
              <td className="muted">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}</td>
              <td className="row" style={{ gap: "0.3rem", flexWrap: "wrap" }}>
                {!u.is_super_admin && (
                  <button className="btn secondary" onClick={() => promote(u.id)}>Promote</button>
                )}
                {u.is_super_admin && (
                  <button className="btn secondary" onClick={() => demote(u.id)}>Demote</button>
                )}
                <button className="btn secondary" onClick={() => resetPassword(u.id)}>Reset pwd</button>
                <button className="btn secondary"
                        onClick={() => setActive(u.id, !u.is_active)}>
                  {u.is_active ? "Disable" : "Enable"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {users.length === 0 && !loading && <p className="muted">No users.</p>}
    </div>
  );
}
