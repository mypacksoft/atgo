"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { api, setToken } from "../../lib/api";
import type { TokenPair } from "../../lib/types";
import LangSwitcher from "../../components/LangSwitcher";

export default function LoginPage() {
  const router = useRouter();
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const r = await api.post<TokenPair>("/api/auth/login", { email, password });
      setToken("hr", r.access_token);

      // Super-admin: redirect to admin portal regardless of tenant.
      if (r.user?.is_super_admin) {
        const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN || "atgo.io";
        if (typeof window !== "undefined" && !window.location.host.startsWith("admin.")) {
          const port = window.location.port ? `:${window.location.port}` : "";
          window.location.href = `${window.location.protocol}//admin.${baseDomain}${port}/admin`;
          return;
        }
        router.push("/admin");
        return;
      }

      // Tenant member: jump to tenant subdomain if not already there.
      const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN || "atgo.io";
      if (r.tenant && typeof window !== "undefined" && !window.location.host.startsWith(r.tenant.slug + ".")) {
        const port = window.location.port ? `:${window.location.port}` : "";
        window.location.href = `${window.location.protocol}//${r.tenant.slug}.${baseDomain}${port}/dashboard`;
        return;
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="center">
      <div className="card" style={{ width: "min(420px, 92vw)" }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
          <h1 style={{ margin: 0 }}>{t("auth.signInTitle")}</h1>
          <LangSwitcher compact />
        </div>
        <form onSubmit={onSubmit} className="grid" style={{ marginTop: "1rem" }}>
          <label>
            {t("common.email")}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            {t("common.password")}
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <div className="errbox">{error}</div>}
          <button className="btn" type="submit" disabled={submitting}>
            {submitting ? t("common.loading") : t("auth.signInTitle")}
          </button>
          <p className="muted" style={{ textAlign: "center", margin: 0 }}>
            {t("auth.newHere")} <a href="/signup">{t("auth.createWorkspace")}</a>
          </p>
        </form>
      </div>
    </div>
  );
}
