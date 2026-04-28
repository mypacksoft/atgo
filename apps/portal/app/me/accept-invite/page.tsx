"use client";
import { useEffect, useState } from "react";
import { api, setToken } from "../../../lib/api";

export default function AcceptInvite() {
  const [token, setTokenInput] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const u = new URL(window.location.href);
    const t = u.searchParams.get("token");
    if (t) setTokenInput(t);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const r = await api.post<{ access_token: string }>(
        "/api/employee/accept-invite",
        { invite_token: token, password },
      );
      setToken("emp", r.access_token);
      window.location.href = "/me";
    } catch (err: any) {
      setError(err?.message || "invite accept failed");
    }
  }

  return (
    <div className="center">
      <div className="card" style={{ width: "min(380px, 92vw)" }}>
        <h2>Set your password</h2>
        <form onSubmit={submit} className="grid">
          <input value={token} onChange={(e) => setTokenInput(e.target.value)} placeholder="Invite token" required />
          <input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Choose a password" required />
          {error && <div className="errbox">{error}</div>}
          <button className="btn">Activate account</button>
        </form>
      </div>
    </div>
  );
}
