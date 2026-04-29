import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";

import { isRtl } from "../i18n/config";
import "./globals.css";

export const metadata: Metadata = {
  title: "ATGO — Cloud Attendance for ZKTeco",
  description:
    "Free online attendance system for ZKTeco devices. No static IP, no port forwarding, no local server. Odoo integration included.",
  manifest: "/manifest.webmanifest",
};

export const viewport = {
  themeColor: "#0e1117",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  const dir = isRtl(locale) ? "rtl" : "ltr";

  return (
    <html lang={locale} dir={dir}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
