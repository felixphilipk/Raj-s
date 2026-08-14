import type { NextConfig } from 'next';

const backendUrl = process.env.BACKEND_INTERNAL_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');
const nextConfig: NextConfig = {
  async rewrites() {
    // `backend` is a Docker Compose-only hostname. Never emit it into a
    // Vercel deployment, where it produces DNS_HOSTNAME_NOT_FOUND.
    return backendUrl ? [{ source: '/api/:path*', destination: `${backendUrl}/:path*` }] : [];
  },
};
export default nextConfig;
