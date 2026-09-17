import { Hono } from "hono";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearSession, issueSession, readSession } from "../src/server/auth/session";
import type { AppEnv } from "../src/server/env";

const env = { SESSION_SECRET: "test-secret-long-enough-for-hmac" } as AppEnv["Bindings"];

const app = new Hono<AppEnv>()
  .post("/login", async (c) => {
    await issueSession(c, c.req.query("login") ?? "");
    return c.body(null, 204);
  })
  .get("/me", async (c) => c.json({ login: await readSession(c) }))
  .post("/logout", (c) => {
    clearSession(c);
    return c.body(null, 204);
  });

async function login(user: string): Promise<string> {
  const res = await app.request(`/login?login=${user}`, { method: "POST" }, env);
  const setCookie = res.headers.get("set-cookie");
  if (!setCookie) throw new Error("login set no cookie");
  return setCookie.split(";")[0];
}

async function whoAmI(cookie: string): Promise<string | null> {
  const res = await app.request("/me", { headers: { cookie } }, env);
  return ((await res.json()) as { login: string | null }).login;
}

describe("session cookie", () => {
  beforeEach(() => vi.useFakeTimers({ now: new Date("2026-09-11T00:00:00Z") }));
  afterEach(() => vi.useRealTimers());

  it("issues a signed, http-only, secure cookie", async () => {
    const res = await app.request("/login?login=alice", { method: "POST" }, env);
    const setCookie = res.headers.get("set-cookie") ?? "";

    expect(setCookie).toMatch(/^spectrace_session=/);
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Secure");
    expect(setCookie).toContain("SameSite=Lax");
  });

  it("reads the login back from the cookie it issued", async () => {
    expect(await whoAmI(await login("alice"))).toBe("alice");
  });

  it("keeps a login that contains a colon", async () => {
    expect(await whoAmI(await login("org:alice"))).toBe("org:alice");
  });

  it("rejects a cookie whose payload was altered", async () => {
    const cookie = await login("alice");
    const forged = cookie.replace("alice", "admin");

    expect(await whoAmI(forged)).toBeNull();
  });

  it("rejects a cookie signed with another secret", async () => {
    const cookie = await login("alice");
    const otherEnv = { SESSION_SECRET: "a-different-secret" } as AppEnv["Bindings"];
    const res = await app.request("/me", { headers: { cookie } }, otherEnv);

    expect(((await res.json()) as { login: string | null }).login).toBeNull();
  });

  it("expires after seven days", async () => {
    const cookie = await login("alice");

    vi.setSystemTime(new Date("2026-09-17T23:59:59Z"));
    expect(await whoAmI(cookie)).toBe("alice");

    vi.setSystemTime(new Date("2026-09-18T00:00:01Z"));
    expect(await whoAmI(cookie)).toBeNull();
  });

  it("clears the cookie on logout", async () => {
    const res = await app.request("/logout", { method: "POST" }, env);

    expect(res.headers.get("set-cookie")).toMatch(/^spectrace_session=;.*Max-Age=0/);
  });
});
