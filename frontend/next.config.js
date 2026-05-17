/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",

  // API calls to /api/* are proxied to the FastAPI backend (internal docker network).
  // In production this routing is handled by cloudflared ingress rules.
  // In local dev you may use Next.js rewrites below if needed.
  // rewrites: async () => [
  //   { source: "/api/:path*", destination: "http://dhanradar-fastapi:8000/api/:path*" },
  // ],
};

module.exports = nextConfig;
