/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: { unoptimized: true },
  experimental: { missingSuspenseWithCSRBailout: false },
}

module.exports = nextConfig
