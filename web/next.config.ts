import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  output: "export",
  // basePath は arvex.jp が取れたら外す
  basePath: isProd ? "/arvex" : "",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
