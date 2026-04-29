/* Marketing landing — atgo.io. */
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import LangSwitcher from "../components/LangSwitcher";

export default async function LandingPage() {
  const t = await getTranslations();

  return (
    <main>
      <header className="nav">
        <strong>{t("brand.name")}</strong>
        <span className="muted">{t("brand.tagline")}</span>
        <span className="right row">
          <LangSwitcher />
          <Link href="/pricing">{t("nav.pricing")}</Link>
          <Link href="/login">{t("nav.signIn")}</Link>
          <Link href="/signup" className="btn" style={{ padding: "0.45rem 0.9rem", color: "white", display: "inline-block" }}>
            {t("landing.ctaPrimary")}
          </Link>
        </span>
      </header>

      <section className="content" style={{ paddingTop: "4rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "2.6rem", lineHeight: 1.1 }}>
          {t("landing.headline")}
        </h1>
        <p className="muted" style={{ fontSize: "1.15rem", maxWidth: 760, margin: "1rem auto" }}>
          {t("landing.sub")}
        </p>
        <div className="row" style={{ justifyContent: "center", marginTop: "1.5rem" }}>
          <Link href="/signup" className="btn" style={{ color: "white", padding: "0.75rem 1.4rem", borderRadius: 8, display: "inline-block" }}>
            {t("landing.ctaPrimary")}
          </Link>
          <Link href="/pricing" className="btn secondary" style={{ padding: "0.75rem 1.4rem", borderRadius: 8, display: "inline-block" }}>
            {t("landing.ctaSecondary")}
          </Link>
        </div>
      </section>

      <section className="content">
        <div className="grid cols-3" style={{ marginTop: "3rem" }}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div className="card" key={i}>
              <h3>{t(`landing.feature${i}Title` as any)}</h3>
              <p className="muted">{t(`landing.feature${i}` as any)}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="content muted" style={{ borderTop: "1px solid var(--border)", paddingTop: "1rem", marginTop: "3rem" }}>
        © {new Date().getFullYear()} ATGO.
      </footer>
    </main>
  );
}
