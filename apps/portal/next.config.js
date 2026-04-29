/** @type {import('next').NextConfig} */
const createNextIntlPlugin = require("next-intl/plugin");
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const apiBase = process.env.INTERNAL_API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

module.exports = withNextIntl({
  reactStrictMode: true,
  output: "standalone",
  experimental: { typedRoutes: false },
  async rewrites() {
    return [
      { source: "/api/:path*",   destination: `${apiBase}/api/:path*` },
      { source: "/iclock/:path*", destination: `${apiBase}/iclock/:path*` },
    ];
  },
});
