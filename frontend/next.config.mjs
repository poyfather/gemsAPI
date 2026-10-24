/** @type {import('next').NextConfig} */
const nextConfig = {
  // The Dockerfile copies .next/standalone, so build the self-contained server.
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the frontend
    // never needs to hard-code the backend URL in production.
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
