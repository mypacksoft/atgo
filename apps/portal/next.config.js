/** @type {import('next').NextConfig} */
const apiBase = process.env.INTERNAL_API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

module.exports = {
  reactStrictMode: true,
  output: "standalone",
  experimental: { typedRoutes: false },
  async rewrites() {
    // Forward API + ADMS calls from the same Next host through to FastAPI.
    // This means {slug}.atgo.io/api/... goes through Caddy -> portal -> rewrite -> api.
    return [
      { source: "/api/:path*",   destination: `${apiBase}/api/:path*` },
      { source: "/iclock/:path*", destination: `${apiBase}/iclock/:path*` },
    ];
  },
};
