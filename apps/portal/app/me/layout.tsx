import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "ATGO — My attendance",
  description: "Employee self-service portal",
  manifest: "/manifest.webmanifest",
};
export default function MeLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
