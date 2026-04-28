import type { Metadata } from "next";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
