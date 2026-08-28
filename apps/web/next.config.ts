import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async rewrites() {
    const apiBase = process.env.API_GATEWAY_URL || 'http://localhost:8000'
    return [
      { source: '/api/:path*', destination: `${apiBase}/:path*` },
    ]
  },
}

export default nextConfig
