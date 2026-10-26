/** @type {import('next').NextConfig} */
const nextConfig = {
  // The Dockerfile copies .next/standalone, so build the self-contained server.
  output: "standalone",
  // Keep /api/gems/ as is. Without this Next redirects it to /api/gems, the backend
  // then redirects /gems to /gems/ on its own origin, and the browser follows that
  // redirect straight to the backend without the key the proxy adds: a 401 for every list.
  skipTrailingSlashRedirect: true,
  experimental: {
    // The /api rewrite is a proxy that gives up after 30 seconds by default. Comparisons and
    // test runs wait for every answer, which takes minutes on a model running on this PC, so the
    // UI showed HTTP 500 while the backend was still working. Allow 15 minutes.
    proxyTimeout: 15 * 60 * 1000,
  },
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the frontend
    // never needs to hard-code the backend URL in production.
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      // The slashed form first, so /api/gems/ reaches the backend as /gems/ and not as /gems
      // (which the backend would redirect to its own origin, losing the key the proxy adds).
      { source: "/api/:path*/", destination: `${backendUrl}/:path*/` },
      { source: "/api/:path*", destination: `${backendUrl}/:path*` },
    ];
  },
};

export default nextConfig;
