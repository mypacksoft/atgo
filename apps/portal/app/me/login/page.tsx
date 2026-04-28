"use client";
import { useState } from "react";
import { api, setToken } from "../../../lib/api";

export default function EmployeeLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // Workspace slug = first label of host
  const slug = (typeof window !== "undefined")
    ? window.location.host.split(".")[0]
    : "";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const r = await api.post<{ access_token: string }>(
        "/api/employee/login",
        { email, password, workspace_slug: slug },
      );
      setToken("emp", r.access_token);
      window.location.href = "/me";
    } catch (err: any) {
      setError(err?.message || "login failed");
    }
  }

  return (
    <div className="center">
      <div className="card" style={{ width: "min(380px, 92vw)" }}>
        <h2>Employee sign in</h2>
        <p className="muted" style={{ marginTop: 0 }}>Workspace: <code className="kbd">{slug}</code></p>
        <form onSubmit={onSubmit} className="grid">
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {error && <div className="errbox">{error}</div>}
          <button className="btn">Sign in</button>
          <p className="muted" style={{ textAlign: "center", margin: 0 }}>
            Got an invite? <a href="/me/accept-invite">Accept invite</a>
          </p>
        </form>
      </div>
    </div>
  );
}
