"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken } from "../../lib/api";
import type { User } from "../../lib/types";

const NAV: Array<[string, string]> = [
  ["/admin", "Overview"],
  ["/admin/tenants", "Tenants"],
  ["/admin/users", "Users"],
  ["/admin/subscriptions", "Subscriptions"],
  ["/admin/plans", "Plans"],
  ["/admin/devices", "Devices"],
  ["/admin/billing-events", "Billing events"],
  ["/admin/audit", "Audit log"],
  ["/admin/security", "Security"],
  ["/admin/disputes", "Domain disputes"],
  ["/admin/system", "System"],
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // The admin overview gate checks is_super_admin; if not, the API will 403.
    api.get<{ tenants_by_plan: any[] }>("/api/admin/overview")
      .then(() => setUser({ id: 0, email: "", full_name: "admin", is_super_admin: true } as User))
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!user) return <div className="center">Loading…</div>;

  return (
    <main>
      <header className="nav">
        <strong style={{ color: "var(--danger)" }}>ATGO Admin</strong>
        <span className="badge red">super-admin</span>
        <span className="right">
          <button className="btn secondary" onClick={() => { clearToken("hr"); router.push("/login"); }}>Sign out</button>
        </span>
      </header>
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr" }}>
        <nav style={{ borderRight: "1px solid var(--border)", padding: "1rem 0.5rem" }}>
          {NAV.map(([href, label]) => (
            <Link key={href} href={href} style={{
              display: "block", padding: "0.5rem 0.75rem", borderRadius: 6,
              background: pathname === href ? "var(--panel-2)" : "transparent",
              color: "var(--text)",
            }}>{label}</Link>
          ))}
        </nav>
        <section className="content" style={{ padding: "1.25rem 1.5rem", maxWidth: "none" }}>{children}</section>
      </div>
    </main>
  );
}
