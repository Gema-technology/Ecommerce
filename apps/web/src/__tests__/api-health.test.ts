import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";
import { GET } from "@/app/api/v1/health/route";

describe("GET /api/v1/health", () => {
  it("returns the FastAPI liveness contract", async () => {
    const response = await GET();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/json");
    await expect(response.json()).resolves.toEqual({
      status: "ok",
      service: "gema-api",
    });
  });

  it("proxies every other /api path after Next.js routes", async () => {
    const rewrites = await nextConfig.rewrites?.();

    expect(rewrites).toEqual({
      fallback: [
        {
          source: "/api/:path*",
          destination: expect.stringMatching(/\/api\/:path\*$/),
        },
      ],
    });
  });
});
