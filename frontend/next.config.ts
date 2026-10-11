import type { NextConfig } from "next";

/**
 * Next.js configuration.
 *
 * API routing:
 *   - Default: browser calls /api/* on the same origin; Next.js rewrites those
 *     requests to BACKEND_URL (server-side). No CORS is needed and no backend
 *     address is exposed to the browser.
 *   - If NEXT_PUBLIC_API_BASE_URL is set at build time, the browser calls that
 *     origin directly (the backend must then allow this origin via CORS_ORIGINS).
 *
 * Rewrites are fixed at build time: change BACKEND_URL, then redeploy.
 */
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const directApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    if (directApi) {
      return [];
    }
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
