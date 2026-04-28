"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Device, DeviceClaim } from "../../../lib/types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [claim, setClaim] = useState<DeviceClaim | null>(null);
  const [name, setName] = useState("");
  const [tz, setTz] = useState("Asia/Ho_Chi_Minh");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function reload() {
    api.get<Device[]>("/api/devices").then(setDevices).catch((e) => setError(e?.message));
  }
  useEffect(() => { reload(); }, []);

  async function createDevice(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const r = await api.post<DeviceClaim>("/api/devices", { name, timezone: tz });
      setClaim(r);
      setName("");
      reload();
    } catch (err: any) {
      setError(err?.message || "create failed");
    } finally {
      setBusy(false);
    }
  }

  async function verifyClaim(code: string) {
    setError("");
    try {
      await api.post("/api/devices/claim/verify", { code });
      setClaim(null);
      reload();
    } catch (err: any) {
      setError(err?.message || "verify failed");
    }
  }

  async function removeDevice(id: number) {
    if (!confirm("Disable this device?")) return;
    await api.delete(`/api/devices/${id}`);
    reload();
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Add a device</h2>
        <form onSubmit={createDevice} className="row" style={{ alignItems: "flex-end" }}>
          <label style={{ flex: 2 }}>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Front door K40" required />
          </label>
          <label style={{ flex: 1 }}>
            Timezone
            <input value={tz} onChange={(e) => setTz(e.target.value)} />
          </label>
          <button className="btn" type="submit" disabled={busy}>{busy ? "Creating…" : "Generate claim code"}</button>
        </form>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>

      {claim && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <h2>Claim code</h2>
          <p>On the ZKTeco device, set <strong>Cloud Server</strong> to the host below, then come back and verify:</p>
          <div className="grid cols-2">
            <div>
              <div className="muted">Cloud Server URL</div>
              <code className="kbd" style={{ fontSize: "1.1rem" }}>{claim.adms_setup.host}</code>
            </div>
            <div>
              <div className="muted">Or short URL</div>
              <code className="kbd" style={{ fontSize: "1.1rem" }}>atgo.io/{claim.device_code}</code>
            </div>
            <div>
              <div className="muted">Claim code</div>
              <code className="kbd" style={{ fontSize: "1.6rem", letterSpacing: "0.1em" }}>{claim.claim_code}</code>
            </div>
            <div>
              <div className="muted">Expires</div>
              <div>{new Date(claim.claim_expires_at).toLocaleString()}</div>
            </div>
          </div>
          <ol className="muted" style={{ marginTop: "1rem" }}>
            {claim.adms_setup.instructions.map((i, idx) => <li key={idx}>{i}</li>)}
          </ol>
          <div className="row" style={{ marginTop: "1rem" }}>
            <button className="btn" onClick={() => verifyClaim(claim.claim_code)}>Verify now</button>
            <button className="btn secondary" onClick={() => setClaim(null)}>Close</button>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Your devices</h3>
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Code</th><th>Serial</th><th>Status</th><th>Online</th><th>Pending cmds</th><th></th></tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td><span className="kbd">{d.device_code}</span></td>
                <td className="muted">{d.serial_number}</td>
                <td><span className={"badge " + (d.status === "active" ? "green" : "yellow")}>{d.status}</span></td>
                <td>{d.is_online ? <span className="badge green">online</span> : <span className="badge red">offline</span>}</td>
                <td>{d.pending_commands_count}</td>
                <td><button className="btn secondary" onClick={() => removeDevice(d.id)}>Disable</button></td>
              </tr>
            ))}
            {devices.length === 0 && (<tr><td colSpan={7} className="muted">No devices yet.</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
