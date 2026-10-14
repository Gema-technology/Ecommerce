import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

function loadRootEnv(): void {
  const envPath = path.resolve(__dirname, "../../.env");
  if (!existsSync(envPath)) return;

  const content = readFileSync(envPath, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

loadRootEnv();

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

/**
 * When opening the Next.js dev server from a phone via LAN IP
 * (e.g. http://192.168.1.116:3000), Next blocks /_next/* assets unless
 * that host is listed here — buttons/overlays then appear "dead".
 */
function allowedDevOriginsFromEnv(): string[] {
  const raw = process.env.CORS_ORIGINS ?? process.env.ALLOWED_DEV_ORIGINS ?? "";
  const hosts = new Set<string>();

  for (const part of raw.split(",")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    try {
      const url = new URL(trimmed);
      hosts.add(url.hostname);
      if (url.host) hosts.add(url.host);
    } catch {
      hosts.add(trimmed.replace(/^https?:\/\//, ""));
    }
  }

  return [...hosts];
}

const allowedDevOrigins = allowedDevOriginsFromEnv();

const nextConfig: NextConfig = {
  // Required for the slim Docker runtime image (apps/web/Dockerfile).
  output: "standalone",
  ...(allowedDevOrigins.length
    ? { allowedDevOrigins }
    : {}),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
