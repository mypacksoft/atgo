"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { api, clearToken } from "../../lib/api";
import LangSwitcher from "../../components/LangSwitcher";
import type { Tenant } from "../../lib/types";

/** href + i18n key under the `nav.*` namespace. */
const NAV: Array<[string, string]> = [
  ["/dashboard",                 "overview"],
  ["/dashboard/devices",         "devices"],
  ["/dashboard/employees",       "employees"],
  ["/dashboard/branches",        "branches"],
  ["/dashboard/departments",     "departments"],
  ["/dashboard/attendance",      "attendance"],
  ["/dashboard/presence",        "presence"],
  ["/dashboard/dashboard-grid",  "dashboard"],
  ["/dashboard/timesheet",       "timesheet"],
  ["/dashboard/sync",            "sync"],
  ["/dashboard/requests",        "requests"],
  ["/dashboard/domains",         "domains"],
  ["/dashboard/billing",         "billing"],
  ["/dashboard/api-keys",        "apiKeys"],
  ["/dashboard/odoo",            "odoo"],
  ["/dashboard/settings",        "settings"],
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get<Tenant>("/api/me/tenant")
      .then((tnt) => setTenant(tnt))
      .catch(() => router.replace("/login"))
      .finally(() => setLoaded(true));
  }, [router]);

  if (!loaded) return <div className="center">{t("common.loading")}</div>;
  if (!tenant) return null;

  return (
    <main>
      <header className="nav">
        <strong style={{ color: "var(--accent)" }}>{t("brand.name")}</strong>
        <span className="muted">{tenant.name}</span>
        {tenant.plan_id === "free" ? (
          <Link
            href="/dashboard/billing"
            className="badge red"
            style={{ textDecoration: "none", cursor: "pointer" }}
            title={t("billing.freeBanner")}
          >
            free · {t("pricing.upgrade")} →
          </Link>
        ) : (
          <span className="badge green">{tenant.plan_id}</span>
        )}
        <span className="right row">
          <LangSwitcher compact />
          <span className="muted">{tenant.primary_domain || `${tenant.slug}.atgo.io`}</span>
          <button
            className="btn secondary"
            onClick={() => {
              clearToken("hr");
              router.push("/login");
            }}
          >
            {t("nav.signOut")}
          </button>
        </span>
      </header>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "calc(100vh - 56px)" }}>
        <nav style={{ borderRight: "1px solid var(--border)", padding: "1rem 0.5rem" }}>
          {NAV.map(([href, key]) => (
            <Link
              key={href}
              href={href}
              className={pathname === href ? "active" : ""}
              style={{
                display: "block",
                padding: "0.5rem 0.85rem",
                borderRadius: 6,
                margin: "0.1rem 0",
                background: pathname === href ? "var(--panel-2)" : "transparent",
                color: "var(--text)",
              }}
            >
              {t(`nav.${key}` as any)}
            </Link>
          ))}
        </nav>
        <section className="content" style={{ padding: "1.25rem 1.5rem", maxWidth: "none" }}>
          {children}
        </section>
      </div>
    </main>
  );
}
