import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

describe("GET /health", () => {
  it("reports the database reachable and the project name", async () => {
    const response = await SELF.fetch("http://spectrace/health");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true, project: "spectrace" });
  });
});
