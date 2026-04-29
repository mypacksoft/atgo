/**
 * Locale configuration for ATGO portal.
 *
 * Strategy:
 *   - URL stays free of locale prefix (cleaner URLs, fewer rewrites for tenant subdomains).
 *   - Locale chosen via cookie `atgo_locale`; falls back to Accept-Language header,
 *     then to default English.
 *   - Logged-in users have `users.locale` synced from this cookie via /api/me/locale.
 */

export const SUPPORTED_LOCALES = [
  "en", "vi",
  "zh-CN", "zh-TW",
  "id", "th", "ms", "fil",
  "hi", "ar",
  "es", "pt-BR",
  "ru", "tr", "fr",
] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_LABELS: Record<Locale, { name: string; native: string; flag: string }> = {
  "en":    { name: "English",    native: "English",     flag: "🇺🇸" },
  "vi":    { name: "Vietnamese", native: "Tiếng Việt",  flag: "🇻🇳" },
  "zh-CN": { name: "Chinese",    native: "简体中文",     flag: "🇨🇳" },
  "zh-TW": { name: "Traditional",native: "繁體中文",     flag: "🇹🇼" },
  "id":    { name: "Indonesian", native: "Bahasa Indonesia", flag: "🇮🇩" },
  "th":    { name: "Thai",       native: "ภาษาไทย",     flag: "🇹🇭" },
  "ms":    { name: "Malay",      native: "Bahasa Melayu", flag: "🇲🇾" },
  "fil":   { name: "Filipino",   native: "Filipino",     flag: "🇵🇭" },
  "hi":    { name: "Hindi",      native: "हिन्दी",       flag: "🇮🇳" },
  "ar":    { name: "Arabic",     native: "العربية",      flag: "🇦🇪" },
  "es":    { name: "Spanish",    native: "Español",      flag: "🇪🇸" },
  "pt-BR": { name: "Portuguese", native: "Português (BR)", flag: "🇧🇷" },
  "ru":    { name: "Russian",    native: "Русский",      flag: "🇷🇺" },
  "tr":    { name: "Turkish",    native: "Türkçe",       flag: "🇹🇷" },
  "fr":    { name: "French",     native: "Français",     flag: "🇫🇷" },
};

/** Locales that use right-to-left text direction. */
export const RTL_LOCALES: ReadonlySet<Locale> = new Set(["ar"]);

export function isRtl(locale: string): boolean {
  return RTL_LOCALES.has(locale as Locale);
}

export function isSupportedLocale(value: string): value is Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

/** Pick the best matching locale from a comma-separated Accept-Language. */
export function negotiateLocale(acceptLanguage: string | null | undefined): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const tags = acceptLanguage.split(",").map((s) => {
    const [tag, q] = s.trim().split(";q=");
    return { tag: tag.trim(), q: q ? parseFloat(q) : 1 };
  }).sort((a, b) => b.q - a.q);

  for (const { tag } of tags) {
    if (isSupportedLocale(tag)) return tag;
    // Try language-only match: "zh-HK" -> "zh-CN" if available
    const lang = tag.split("-")[0].toLowerCase();
    const partial = SUPPORTED_LOCALES.find((l) => l.toLowerCase().startsWith(lang));
    if (partial) return partial;
  }
  return DEFAULT_LOCALE;
}
