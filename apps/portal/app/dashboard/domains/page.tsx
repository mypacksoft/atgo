"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { DomainRow, Tenant } from "../../../lib/types";

export default function DomainsPage() {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [domains, setDomains] = useState<DomainRow[]>([]);
  const [domainInput, setDomainInput] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState<DomainRow | null>(null);

  function reload() {
    api.get<Tenant>("/api/me/tenant").then(setTenant).catch(() => {});
    api.get<DomainRow[]>("/api/domains").then((rows) => {
      setDomains(rows);
      const firstPending = rows.find((d) => d.domain_type === "custom_domain" && d.status === "pending");
      if (firstPending) setPending(firstPending);
    });
  }
  useEffect(reload, []);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setError(""); setSuccess("");
    try {
      const newD = await api.post<DomainRow>("/api/domains", { domain: domainInput });
      setDomainInput("");
      setPending(newD);
      reload();
    } catch (err: any) {
      if (err.status === 402) setError("This requires Business plan or above. Upgrade in Billing.");
      else setError(err?.message || "add failed");
    }
  }

  async function verify(id: number) {
    setError(""); setSuccess("");
    try {
      const updated = await api.post<DomainRow>(`/api/domains/${id}/verify`);
      if (updated.status === "verified" || updated.status === "active") {
        setSuccess("Domain verified ✓ — SSL provisions on the next request to your domain.");
        setPending(null);
      } else {
        setError(`DNS check did not pass yet. Status: ${updated.status}. Try again in a minute.`);
      }
      reload();
    } catch (err: any) {
      setError(err?.message || "verify failed");
    }
  }

  async function setPrimary(id: number) {
    setError(""); setSuccess("");
    try {
      await api.post(`/api/domains/${id}/set-primary`);
      setSuccess("Primary domain updated.");
      reload();
    } catch (err: any) { setError(err?.message || ""); }
  }

  async function remove(id: number) {
    if (!confirm("Remove this domain?")) return;
    await api.delete(`/api/domains/${id}`);
    if (pending?.id === id) setPending(null);
    reload();
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN || "atgo.io";
  const cnameTarget = pending?.cname_target || `cname.${baseDomain}`;

  return (
    <div className="grid">
      <div className="card">
        <h2>Workspace URL</h2>
        <p>Default: <code className="kbd">{tenant?.primary_domain || `${tenant?.slug}.${baseDomain}`}</code></p>
        <p className="muted">Always available — cannot be removed even if you downgrade.</p>
      </div>

      <div className="card">
        <h2>Custom domain</h2>
        <p className="muted">
          Point your own domain at ATGO so employees see <code>attendance.yourcompany.com</code>
          instead of <code>{tenant?.slug}.{baseDomain}</code>. Available on Business plan and above.
        </p>

        <form onSubmit={add} className="row" style={{ marginTop: "1rem" }}>
          <input
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            placeholder="attendance.yourcompany.com"
            required
            style={{ flex: 1 }}
          />
          <button className="btn" type="submit">Add domain</button>
        </form>
        {error && <div className="errbox" style={{ marginTop: "1rem" }}>{error}</div>}
        {success && <div className="okbox" style={{ marginTop: "1rem" }}>{success}</div>}
      </div>

      {/* DNS wizard for the most-recently-added pending domain */}
      {pending && (
        <div className="card" style={{ borderLeft: "4px solid var(--accent)" }}>
          <h3 style={{ marginTop: 0 }}>
            Step-by-step: <code className="kbd">{pending.domain}</code>
          </h3>
          <p className="muted">
            Add the records below at your DNS provider (Cloudflare, GoDaddy, Namecheap, Route53…).
            DNS usually propagates in 5–30 minutes.
          </p>

          <ol style={{ lineHeight: 1.7, paddingLeft: "1.2rem" }}>
            <li>
              <strong>CNAME record</strong> (required)
              <table className="table" style={{ marginTop: "0.5rem" }}>
                <thead><tr><th>Type</th><th>Name / Host</th><th>Value / Target</th><th>TTL</th></tr></thead>
                <tbody>
                  <tr>
                    <td><code>CNAME</code></td>
                    <td>
                      <code>{pending.domain}</code>
                      <button className="btn secondary" style={{ marginLeft: "0.5rem", padding: "0.15rem 0.5rem", fontSize: "0.7rem" }} onClick={() => copy(pending.domain)}>copy</button>
                    </td>
                    <td>
                      <code>{cnameTarget}</code>
                      <button className="btn secondary" style={{ marginLeft: "0.5rem", padding: "0.15rem 0.5rem", fontSize: "0.7rem" }} onClick={() => copy(cnameTarget)}>copy</button>
                    </td>
                    <td>300</td>
                  </tr>
                </tbody>
              </table>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                Note: most DNS providers want the <em>subdomain part only</em>
                (e.g. <code>attendance</code>), not the full hostname.
              </p>
            </li>

            {pending.txt_record_name && (
              <li style={{ marginTop: "1rem" }}>
                <strong>TXT record</strong> (verification token)
                <table className="table" style={{ marginTop: "0.5rem" }}>
                  <thead><tr><th>Type</th><th>Name</th><th>Value</th><th>TTL</th></tr></thead>
                  <tbody>
                    <tr>
                      <td><code>TXT</code></td>
                      <td>
                        <code>{pending.txt_record_name}</code>
                        <button className="btn secondary" style={{ marginLeft: "0.5rem", padding: "0.15rem 0.5rem", fontSize: "0.7rem" }} onClick={() => copy(pending.txt_record_name!)}>copy</button>
                      </td>
                      <td>
                        <code>{pending.txt_record_value}</code>
                        <button className="btn secondary" style={{ marginLeft: "0.5rem", padding: "0.15rem 0.5rem", fontSize: "0.7rem" }} onClick={() => copy(pending.txt_record_value!)}>copy</button>
                      </td>
                      <td>300</td>
                    </tr>
                  </tbody>
                </table>
              </li>
            )}

            <li style={{ marginTop: "1rem" }}>
              <strong>Verify</strong>
              <p className="muted" style={{ fontSize: "0.85rem", margin: "0.3rem 0" }}>
                Once the records resolve, click verify. ATGO checks DNS, then provisions a free SSL certificate via Let's Encrypt automatically.
              </p>
              <button className="btn" onClick={() => verify(pending.id)}>Verify DNS now</button>
            </li>
          </ol>

          {pending.expires_at && (
            <p className="muted" style={{ fontSize: "0.8rem" }}>
              ⏱ This pending domain expires <strong>{new Date(pending.expires_at).toLocaleString()}</strong>.
              Verify before that or it will be released.
            </p>
          )}
        </div>
      )}

      <div className="card">
        <h3>Your domains</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Domain</th><th>Status</th><th>SSL</th><th>Primary</th><th>Added</th><th></th>
            </tr>
          </thead>
          <tbody>
            {domains.filter((d) => d.domain_type === "custom_domain").map((d) => (
              <tr key={d.id}>
                <td><code className="kbd">{d.domain}</code></td>
                <td>
                  <span className={"badge " +
                    (d.status === "active" ? "green"
                      : d.status === "verified" ? "green"
                      : d.status === "pending" ? "yellow"
                      : "red")}>
                    {d.status}
                  </span>
                </td>
                <td className="muted">{d.ssl_status}</td>
                <td>{d.is_primary ? <span className="badge green">primary</span> : <span className="muted">—</span>}</td>
                <td className="muted">{d.verified_at ? new Date(d.verified_at).toLocaleDateString() : "—"}</td>
                <td className="row" style={{ gap: "0.3rem", flexWrap: "wrap" }}>
                  {d.status === "pending" && (
                    <>
                      <button className="btn" onClick={() => setPending(d)}>Show DNS instructions</button>
                      <button className="btn secondary" onClick={() => verify(d.id)}>Re-verify</button>
                    </>
                  )}
                  {(d.status === "verified" || d.status === "active") && !d.is_primary && (
                    <button className="btn secondary" onClick={() => setPrimary(d.id)}>Make primary</button>
                  )}
                  <button className="btn secondary" onClick={() => remove(d.id)}>Remove</button>
                </td>
              </tr>
            ))}
            {domains.filter((d) => d.domain_type === "custom_domain").length === 0 && (
              <tr><td colSpan={6} className="muted">No custom domains yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ background: "var(--panel-2)" }}>
        <h3>How it works</h3>
        <ol className="muted" style={{ lineHeight: 1.7, paddingLeft: "1.2rem" }}>
          <li>You add the domain here. ATGO creates a pending record with a CNAME target + TXT verification token.</li>
          <li>You add a CNAME at your DNS provider pointing to <code>cname.{baseDomain}</code>.</li>
          <li>You click <strong>Verify</strong>. ATGO checks DNS — if the CNAME resolves correctly, status becomes <code>verified</code>.</li>
          <li>The first time someone visits your domain in a browser, ATGO's edge proxy auto-provisions a free Let's Encrypt SSL certificate (takes a few seconds).</li>
          <li>Set the domain as <strong>primary</strong> and your default URL in invites/emails switches to your custom domain.</li>
        </ol>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Downgrades: if you go below Business, the custom domain becomes <code>restricted</code> for 30 days
          (still resolves, banner asks to upgrade) before being released.
        </p>
      </div>
    </div>
  );
}
