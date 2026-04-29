/**
 * next-intl getRequestConfig — runs server-side per request, picks the
 * locale + loads its messages.
 */
import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  negotiateLocale,
  type Locale,
} from "./config";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const fromCookie = cookieStore.get("atgo_locale")?.value;
  const fromHeader = (await headers()).get("accept-language");

  const locale: Locale =
    (fromCookie && isSupportedLocale(fromCookie) && fromCookie) ||
    negotiateLocale(fromHeader) ||
    DEFAULT_LOCALE;

  // Load EN as base + locale-specific override (graceful fallback for partial translations)
  const en = (await import(`./messages/en.json`)).default;
  let messages = en;
  if (locale !== "en") {
    try {
      const localeMsgs = (await import(`./messages/${locale}.json`)).default;
      messages = deepMerge(en, localeMsgs);
    } catch {
      // Fall back to EN if locale file missing
      messages = en;
    }
  }

  return { locale, messages };
});

function deepMerge<T extends Record<string, any>>(base: T, override: any): T {
  const out: Record<string, any> = { ...base };
  for (const k of Object.keys(override ?? {})) {
    const v = override[k];
    if (v !== null && typeof v === "object" && !Array.isArray(v) &&
        out[k] !== null && typeof out[k] === "object" && !Array.isArray(out[k])) {
      out[k] = deepMerge(out[k], v);
    } else if (v !== undefined && v !== "") {
      out[k] = v;
    }
  }
  return out as T;
}
