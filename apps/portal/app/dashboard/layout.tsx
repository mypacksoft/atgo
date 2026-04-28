"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken } from "../../lib/api";
import type { Tenant } from "../../lib/types";

const NAV: Array<[string, string]> = [
  ["/dashboard", "Overview"],
  ["/dashboard/devices", "Devices"],
  ["/dashboard/employees", "Employees"],
  ["/dashboard/branches", "Branches"],
  ["/dashboard/departments", "Departments"],
  ["/dashboard/attendance", "Attendance"],
  ["/dashboard/timesheet", "Timesheet"],
  ["/dashboard/sync", "Device Sync"],
  ["/dashboard/requests", "Requests"],
  ["/dashboard/domains", "Domains"],
  ["/dashboard/billing", "Billing"],
  ["/dashboard/api-keys", "API keys"],
  ["/dashboard/odoo", "Odoo"],
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get<Tenant>("/api/me/tenant")
      .then((t) => setTenant(t))
      .catch(() => router.replace("/login"))
      .finally(() => setLoaded(true));
  }, [router]);

  if (!loaded) return <div className="center">Loading…</div>;
  if (!tenant) return null;

  return (
    <main>
      <header className="nav">
        <strong style={{ color: "var(--accent)" }}>ATGO</strong>
        <span className="muted">{tenant.name}</span>
        {tenant.plan_id === "free" ? (
          <Link
            href="/dashboard/billing"
            className="badge red"
            style={{ textDecoration: "none", cursor: "pointer" }}
            title="You're on the free plan — click to upgrade"
          >
            free · upgrade →
          </Link>
        ) : (
          <span className="badge green">{tenant.plan_id}</span>
        )}
        <span className="right row">
          <span className="muted">{tenant.primary_domain || `${tenant.slug}.atgo.io`}</span>
          <button
            className="btn secondary"
            onClick={() => {
              clearToken("hr");
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </span>
      </header>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", minHeight: "calc(100vh - 56px)" }}>
        <nav style={{ borderRight: "1px solid var(--border)", padding: "1rem 0.5rem" }}>
          {NAV.map(([href, label]) => (
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
              {label}
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
