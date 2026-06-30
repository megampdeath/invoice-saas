/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_BASE_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  // Note: do NOT set output: "standalone" on Vercel — it's only for Docker
  // self-hosting. Vercel builds Next.js natively.
  async rewrites() {
    // Proxy /api/* to the backend in ALL environments (not just dev).
    //
    // Why in production too: the invoice file-preview URL is served by the
    // backend with Content-Disposition: inline, but the backend is on a
    // different origin than the frontend. Chrome will NOT render a
    // cross-origin PDF inside an <iframe> — it force-downloads or shows blank.
    // By routing /api/* through this same-origin rewrite, the preview URL
    // becomes same-origin to the page, so <iframe src="/api/.../file"> renders
    // the PDF natively in the browser's PDF viewer.
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
module.exports = nextConfig;
