/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_BASE_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  // Note: do NOT set output: "standalone" on Vercel — it's only for Docker
  // self-hosting. Vercel builds Next.js natively.
  // In dev, proxy /api/* to the local backend. In production the frontend calls
  // NEXT_PUBLIC_BACKEND_BASE_URL directly.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
module.exports = nextConfig;
