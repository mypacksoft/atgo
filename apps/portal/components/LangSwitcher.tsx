"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { LOCALE_LABELS, SUPPORTED_LOCALES, type Locale } from "../i18n/config";

export default function LangSwitcher({ compact = false }: { compact?: boolean }) {
  const current = useLocale() as Locale;
  const t = useTranslations("lang");
  const [open, setOpen] = useState(false);

  function pick(code: Locale) {
    document.cookie = `atgo_locale=${code}; path=/; max-age=31536000; SameSite=Lax`;
    // Sync server-side preference if logged in (best-effort, ignore failure).
    fetch("/api/me/locale", {
      method: "POST",
      headers: { "Content-Type": "application/json",
                 ...(typeof window !== "undefined" && localStorage.getItem("atgo_token")
                     ? { Authorization: `Bearer ${localStorage.getItem("atgo_token")}` }
                     : {}) },
      body: JSON.stringify({ locale: code }),
    }).catch(() => {});
    window.location.reload();
  }

  const label = LOCALE_LABELS[current];

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        className="btn secondary"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("switcherLabel")}
        title={t("switcherLabel")}
        style={{ padding: "0.35rem 0.6rem", fontSize: "0.85rem" }}
      >
        <span style={{ marginRight: "0.4rem" }}>{label?.flag ?? "🌐"}</span>
        {compact ? current : (label?.native ?? current)}
        <span style={{ marginLeft: "0.4rem", opacity: 0.6 }}>▾</span>
      </button>

      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{ position: "fixed", inset: 0, zIndex: 80 }}
          />
          <div
            role="menu"
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              right: 0,
              minWidth: 220,
              maxHeight: 360,
              overflowY: "auto",
              padding: "0.3rem",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--panel)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
              zIndex: 90,
            }}
          >
            {SUPPORTED_LOCALES.map((code) => {
              const lab = LOCALE_LABELS[code];
              const active = code === current;
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => pick(code)}
                  style={{
                    display: "flex", width: "100%",
                    alignItems: "center", gap: "0.6rem",
                    padding: "0.45rem 0.6rem",
                    border: "none", textAlign: "left",
                    background: active ? "var(--panel-2)" : "transparent",
                    color: "var(--text)", borderRadius: 4, cursor: "pointer",
                    fontSize: "0.85rem",
                  }}
                >
                  <span style={{ width: 22, textAlign: "center" }}>{lab.flag}</span>
                  <span style={{ flex: 1 }}>{lab.native}</span>
                  <span style={{ opacity: 0.5, fontSize: "0.7rem" }}>{code}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
