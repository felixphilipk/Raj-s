import type { NextConfig } from 'next';

const backendUrl = process.env.BACKEND_INTERNAL_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'http://backend:8000');
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${backendUrl}/:path*` }];
  },
};
export default nextConfig;
