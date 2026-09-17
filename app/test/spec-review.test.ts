import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { formatDuration, formatWeek, seriesColor } from "../src/client/components/charts";
import type { AppEnv } from "../src/server/env";
import { spectraceRoute } from "../src/server/routes/spectrace";

function reviewerApp(login: string) {
  const fetch = vi.fn<(url: URL, init: RequestInit) => Promise<Response>>(async () =>
    Response.json({ data: { task_id: "T-1", from_status: "draft", to_status: "unclaimed", message: "ok" } }),
  );
  const env = {
    SPECTRACE_URL: "https://upstream.test",
    SPECTRACE_API_KEY: "dashboard-key",
    SPECTRACE: { fetch } as unknown as Fetcher,
  } as AppEnv["Bindings"];
  const app = new Hono<AppEnv>()
    .use("*", async (c, next) => {
      c.set("login", login);
      await next();
    })
    .route("/api/spectrace", spectraceRoute);
  return { app, fetch, env };
}

function sentBody(fetch: ReturnType<typeof reviewerApp>["fetch"]): Record<string, unknown> {
  return JSON.parse(fetch.mock.calls[0][1].body as string);
}

function post(app: Hono<AppEnv>, path: string, body: unknown, env: AppEnv["Bindings"]) {
  return app.request(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    env,
  );
}

describe("the dashboard signs a spec decision with the session login", () => {
  it("approves as the logged-in reviewer, ignoring a reviewer_id from the browser", async () => {
    const { app, fetch, env } = reviewerApp("tslateman");

    const res = await post(app, "/api/spectrace/tasks/T-1/approve-spec", { reviewer_id: "somebody-else" }, env);

    expect(res.status).toBe(200);
    expect(fetch.mock.calls[0][0].pathname).toBe("/api/v1/tasks/T-1/approve-spec");
    expect(sentBody(fetch)).toEqual({ reviewer_id: "tslateman", feedback: "" });
  });

  it("carries the rejection reason upstream", async () => {
    const { app, fetch, env } = reviewerApp("tslateman");

    await post(app, "/api/spectrace/tasks/T-2/reject-spec", { reason: "scope_in names no file" }, env);

    expect(sentBody(fetch)).toEqual({ reviewer_id: "tslateman", reason: "scope_in names no file" });
  });

  it("registers the session login as a reviewer agent", async () => {
    const { app, fetch, env } = reviewerApp("tslateman");

    await post(app, "/api/spectrace/reviewer", {}, env);

    expect(fetch.mock.calls[0][0].pathname).toBe("/api/v1/tasks/agents/register/");
    expect(sentBody(fetch)).toEqual({ agent_id: "tslateman", role: "reviewer" });
  });

  it("forwards the weeks window to the factory report", async () => {
    const { app, fetch, env } = reviewerApp("tslateman");

    await app.request("/api/spectrace/reports/factory?weeks=26", {}, env);

    expect(fetch.mock.calls[0][0].toString()).toBe("https://upstream.test/api/v1/reports/factory?weeks=26");
  });
});

describe("chart formatting", () => {
  it("scales a duration to the unit a reader can hold", () => {
    expect(formatDuration(42)).toBe("42s");
    expect(formatDuration(600)).toBe("10m");
    expect(formatDuration(9000)).toBe("2.5h");
    expect(formatDuration(259200)).toBe("3.0d");
  });

  it("labels a week by its Monday in UTC", () => {
    expect(formatWeek("2026-09-14")).toBe("Sep 14");
  });

  it("hands out the categorical slots in a fixed order", () => {
    expect([seriesColor(0), seriesColor(1), seriesColor(2)]).toEqual([
      "var(--series-1)",
      "var(--series-2)",
      "var(--series-3)",
    ]);
  });
});
