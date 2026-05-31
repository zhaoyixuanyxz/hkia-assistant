import type { NextConfig } from "next";
import path from "path";

import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1"],
};

export default withNextIntl(nextConfig);
