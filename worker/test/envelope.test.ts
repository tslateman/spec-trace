import { Hono } from "hono";
import { describe, expect, it } from "vitest";
import { failure, success } from "../src/api/envelope";

const app = new Hono()
  .get("/plain", (c) => success(c, [1, 2]))
  .get("/meta", (c) => success(c, { a: 1 }, { count: 1 }, 201))
  .get("/error", (c) => failure(c, "Missing field", "validation_error", 422, { field: "title" }))
  .get("/error-bare", (c) => failure(c, "Nope"));

describe("success", () => {
  it("wraps data and omits meta when absent", async () => {
    expect(await (await app.request("/plain")).json()).toEqual({ data: [1, 2] });
  });

  it("includes meta and honours the status", async () => {
    const res = await app.request("/meta");
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({ data: { a: 1 }, meta: { count: 1 } });
  });
});

describe("failure", () => {
  it("nests code, message, and details under error", async () => {
    const res = await app.request("/error");
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({
      error: { code: "validation_error", message: "Missing field", details: { field: "title" } },
    });
  });

  it("defaults to bad_request 400 without details", async () => {
    const res = await app.request("/error-bare");
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: { code: "bad_request", message: "Nope" } });
  });
});
