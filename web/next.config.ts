import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` emits a self-contained server bundle for the Docker image.
  // Vercel ignores it, so it is safe to leave on for both deployment paths.
  output: "standalone",

  // The Dockerfile builds from the repository root so METHODOLOGY.md is in
  // scope; tell Next where its own root is so it does not warn about the
  // inferred workspace root.
  outputFileTracingRoot: process.cwd(),

  // Next 16 no longer runs ESLint during `next build` and removed the `eslint`
  // config key, so linting is its own CI step: `npm run lint`.
};

export default nextConfig;
