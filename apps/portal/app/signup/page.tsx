"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "../../lib/api";
import type { TokenPair } from "../../lib/types";

const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN || "atgo.io";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [slug, setSlug] = useState("");
  const [country, setCountry] = useState("VN");
  const [slugStatus, setSlugStatus] = useState<{ ok: boolean | null; msg: string }>({ ok: null, msg: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Debounced slug check
  useEffect(() => {
    const s = slug.toLowerCase().trim();
    if (s.length < 3) {
      setSlugStatus({ ok: null, msg: "" });
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await api.get<{ available: boolean; message: string }>(
          `/api/workspaces/check-slug?slug=${encodeURIComponent(s)}`,
        );
        setSlugStatus({ ok: r.available, msg: r.message });
      } catch {
        setSlugStatus({ ok: null, msg: "" });
      }
    }, 350);
    return () => clearTimeout(t);
  }, [slug]);

  const workspaceUrl = useMemo(
    () => (slug ? `https://${slug}.${baseDomain}` : `https://yourcompany.${baseDomain}`),
    [slug],
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (slugStatus.ok === false) return setError(slugStatus.msg);
    setSubmitting(true);
    try {
      const r = await api.post<TokenPair>("/api/auth/signup", {
        email,
        password,
        full_name: fullName,
        company_name: companyName,
        workspace_slug: slug,
        country,
      });
      setToken("hr", r.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.message || "Signup failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="center">
      <div className="card" style={{ width: "min(480px, 92vw)" }}>
        <h1>Create your workspace</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Free forever for 1 device. Unlimited employees.
        </p>
        <form onSubmit={onSubmit} className="grid" style={{ marginTop: "1rem" }}>
          <label>
            Your name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label>
            Work email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
          </label>
          <label>
            Company name
            <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
          </label>
          <label>
            Workspace URL
            <div className="row" style={{ gap: 0 }}>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="yourcompany"
                style={{ borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
                required
              />
              <span
                style={{
                  border: "1px solid var(--border)",
                  borderLeft: 0,
                  background: "var(--panel-2)",
                  padding: "0.55rem 0.75rem",
                  borderTopRightRadius: 6,
                  borderBottomRightRadius: 6,
                }}
              >
                .{baseDomain}
              </span>
            </div>
            <small className="muted">Will be: {workspaceUrl}</small>
            {slugStatus.ok === true && <small style={{ color: "var(--accent-2)" }}>✓ {slugStatus.msg}</small>}
            {slugStatus.ok === false && <small style={{ color: "var(--danger)" }}>✗ {slugStatus.msg}</small>}
          </label>
          <label>
            Country (for billing)
            <select value={country} onChange={(e) => setCountry(e.target.value)}>
              <option value="VN">Vietnam (VND, VNPay)</option>
              <option value="IN">India (INR, Razorpay)</option>
              <option value="">Other (USD, Paddle)</option>
            </select>
          </label>
          {error && <div className="errbox">{error}</div>}
          <button className="btn" type="submit" disabled={submitting || slugStatus.ok === false}>
            {submitting ? "Creating…" : "Create workspace"}
          </button>
          <p className="muted" style={{ textAlign: "center", margin: 0 }}>
            Already have an account? <a href="/login">Sign in</a>
          </p>
        </form>
      </div>
    </div>
  );
}
