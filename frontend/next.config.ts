import type { NextConfig } from "next";

// Where the Next.js server forwards /api/* requests. The browser only ever
// talks to the frontend's own origin, so the backend needs no CORS setup.
const apiUrl = process.env.DRIFTKING_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The floating dev badge sits on top of the graph legend. Compile and
  // runtime errors are still shown.
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
