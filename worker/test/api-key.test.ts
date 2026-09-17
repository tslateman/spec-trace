import { Hono } from "hono";
import { describe, expect, it } from "vitest";
import { requireApiKey } from "../src/api/api-key";
import { success } from "../src/api/envelope";
import type { Env } from "../src/env";

const guarded = new Hono<{ Bindings: Env }>()
  .use("/api/*", requireApiKey)
  .get("/api/v1/ping", (c) => success(c, { pong: true }));

const env = { SPECTRACE_API_KEY: "secret" } as unknown as Env;

describe("requireApiKey", () => {
  it("accepts a Bearer token", async () => {
    const res = await guarded.request("/api/v1/ping", { headers: { Authorization: "Bearer secret" } }, env);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ data: { pong: true } });
  });

  it("accepts an Api-Key scheme", async () => {
    const res = await guarded.request("/api/v1/ping", { headers: { Authorization: "Api-Key secret" } }, env);
    expect(res.status).toBe(200);
  });

  it("accepts X-API-Key", async () => {
    const res = await guarded.request("/api/v1/ping", { headers: { "X-API-Key": "secret" } }, env);
    expect(res.status).toBe(200);
  });

  it("rejects a wrong key with the error envelope", async () => {
    const res = await guarded.request("/api/v1/ping", { headers: { "X-API-Key": "nope" } }, env);
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({
      error: { code: "unauthorized", message: "Invalid or missing API key" },
    });
  });

  it("rejects a missing key", async () => {
    const res = await guarded.request("/api/v1/ping", {}, env);
    expect(res.status).toBe(401);
  });

  it("fails loudly when no key is configured", async () => {
    const res = await guarded.request("/api/v1/ping", { headers: { "X-API-Key": "secret" } }, {} as unknown as Env);
    expect(res.status).toBe(500);
  });
});
