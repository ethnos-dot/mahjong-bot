import type { NextConfig } from "next";

// Static export so the Mini App can be hosted on GitHub Pages (or any static
// host). Set NEXT_PUBLIC_BASE_PATH when serving from a sub-path, e.g. a
// project Pages site at /mahjong-web.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  trailingSlash: true,
};

export default nextConfig;
