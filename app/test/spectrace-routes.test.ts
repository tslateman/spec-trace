import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { parse } from "yaml";
import contractText from "../../plans/openapi-worker.yaml?raw";
import type { AppEnv } from "../src/server/env";
import { spectraceRoute } from "../src/server/routes/spectrace";

const app = new Hono<AppEnv>().route("/api/spectrace", spectraceRoute);

function upstream(response: () => Response) {
  const fetch = vi.fn<(url: URL, init: RequestInit) => Promise<Response>>(async () => response());
  const env = {
    SPECTRACE_URL: "https://upstream.test",
    SPECTRACE_API_KEY: "dashboard-key",
    SPECTRACE: { fetch } as unknown as Fetcher,
  } as AppEnv["Bindings"];
  return { fetch, env };
}

function calledUrl(fetch: ReturnType<typeof upstream>["fetch"]): URL {
  return fetch.mock.calls[0][0];
}

function contractPaths(method: string): Set<string> {
  const contract = parse(contractText) as { paths: Record<string, Record<string, unknown>> };
  return new Set(
    Object.entries(contract.paths)
      .filter(([, operations]) => method.toLowerCase() in operations)
      .map(([contractPath]) => shape(contractPath)),
  );
}

function shape(pathname: string): string {
  return pathname
    .replace(/\{[^}]+\}/g, "{}")
    .replace(/\/1(?=\/|$)/g, "/{}")
    .replace(/\/$/, "");
}

describe("the dashboard relays to the Worker", () => {
  it("forwards the query string and the API key", async () => {
    const { fetch, env } = upstream(() => Response.json({ data: [], meta: {} }));

    const res = await app.request("/api/spectrace/requirements?page=2&per_page=10", {}, env);

    expect(res.status).toBe(200);
    expect(calledUrl(fetch).toString()).toBe("https://upstream.test/api/v1/specs/?page=2&per_page=10");
    expect(fetch.mock.calls[0][1].headers).toEqual({ "X-API-Key": "dashboard-key" });
  });

  it("passes the upstream status and body through", async () => {
    const body = { error: { code: "not_found", message: "no such requirement" } };
    const { env } = upstream(() => Response.json(body, { status: 404 }));

    const res = await app.request("/api/spectrace/requirements/REQ-404/status", {}, env);

    expect(res.status).toBe(404);
    expect(await res.json()).toEqual(body);
  });

  it("passes an empty 204 through without reading a body", async () => {
    const { env } = upstream(() => new Response(null, { status: 204 }));

    const res = await app.request("/api/spectrace/test-runs/latest", {}, env);

    expect(res.status).toBe(204);
  });

  it("encodes path parameters before building the upstream path", async () => {
    const { fetch, env } = upstream(() => Response.json({}));

    await app.request("/api/spectrace/requirements/REQ%2F1/context", {}, env);

    expect(calledUrl(fetch).pathname).toBe("/api/v1/specs/REQ%2F1/context");
  });

  it("forwards the method and body when resolving a conflict", async () => {
    const { fetch, env } = upstream(() => Response.json({ data: { conflict_id: 1, resolved_at: "2026-01-01" } }));

    const res = await app.request(
      "/api/spectrace/conflicts/1/resolve",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolution_notes: "duplicate" }),
      },
      env,
    );

    expect(res.status).toBe(200);
    expect(calledUrl(fetch).pathname).toBe("/api/v1/results/conflicts/1/resolve");
    expect(fetch.mock.calls[0][1].method).toBe("POST");
    expect(fetch.mock.calls[0][1].headers).toEqual({
      "X-API-Key": "dashboard-key",
      "Content-Type": "application/json",
    });
    expect(fetch.mock.calls[0][1].body).toBe(JSON.stringify({ resolution_notes: "duplicate" }));
  });
});

describe("every relayed path is in plans/openapi-worker.yaml", () => {
  const routes = spectraceRoute.routes.filter((route) => route.method === "GET" || route.method === "POST");

  it.each(routes.map((route) => [route.method, route.path]))("%s %s", async (method, routePath) => {
    const { fetch, env } = upstream(() => Response.json({}));

    await app.request(
      `/api/spectrace${routePath.replace(/:[A-Za-z]+/g, "1")}`,
      method === "POST" ? { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" } : {},
      env,
    );

    expect(contractPaths(method)).toContain(shape(calledUrl(fetch).pathname));
  });
});
