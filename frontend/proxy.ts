/**
 * Next.js proxy (the file convention that replaced middleware in Next 16). Runs server-side before every request.
 *
 * Injects the X-API-Key header on all /api/* requests so the key
 * is never exposed in the browser bundle. The rewrite in next.config.mjs
 * then forwards the modified request (including the header) to FastAPI.
 *
 * Set GEMS_API_KEY in frontend/.env.local (no NEXT_PUBLIC_ prefix — server only).
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const apiKey = process.env.GEMS_API_KEY;

  if (!apiKey) {
    // No key configured — pass through and let the backend return 401.
    return NextResponse.next();
  }

  const headers = new Headers(request.headers);
  headers.set("X-API-Key", apiKey);

  return NextResponse.next({ request: { headers } });
}

export const config = {
  // Only run on routes that proxy to the backend.
  matcher: "/api/:path*",
};
