/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_BASE_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // In dev, proxy /api/* to the local backend so the browser can use same-origin
  // calls. In production the frontend calls NEXT_PUBLIC_BACKEND_BASE_URL directly.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
module.exports = nextConfig;