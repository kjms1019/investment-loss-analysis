import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // web/ 를 트레이싱 루트로 고정 (루트 package-lock 와의 혼동 방지)
  outputFileTracingRoot: __dirname,
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
