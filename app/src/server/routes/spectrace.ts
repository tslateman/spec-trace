import { type Context, Hono } from "hono";
import type { AppEnv } from "../env";

type AppContext = Context<AppEnv>;

async function relay(c: AppContext, upstreamPath: string, method = "GET") {
  const url = new URL(upstreamPath, c.env.SPECTRACE_URL);
  for (const [key, value] of Object.entries(c.req.query())) {
    url.searchParams.set(key, value);
  }
  const headers: Record<string, string> = { "X-API-Key": c.env.SPECTRACE_API_KEY };
  let body: string | undefined;
  if (method !== "GET") {
    body = await c.req.text();
    headers["Content-Type"] = "application/json";
  }
  const res = await c.env.SPECTRACE.fetch(url, { method, headers, body });
  if (res.status === 204) return c.body(null, 204);
  return c.json(await res.json(), res.status as 200);
}

async function relayAs(c: AppContext, upstreamPath: string, body: unknown) {
  const url = new URL(upstreamPath, c.env.SPECTRACE_URL);
  const res = await c.env.SPECTRACE.fetch(url, {
    method: "POST",
    headers: { "X-API-Key": c.env.SPECTRACE_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return c.json(await res.json(), res.status as 200);
}

async function reason(c: AppContext, field: string): Promise<string> {
  const body = (await c.req.json()) as Record<string, unknown>;
  const value = body[field];
  return typeof value === "string" ? value : "";
}

export const spectraceRoute = new Hono<AppEnv>()
  .get("/coverage", (c) => relay(c, "/api/v1/specs/coverage/"))
  .get("/coverage/trend", (c) => relay(c, "/api/v1/specs/coverage/trend"))
  .get("/test-runs/latest", (c) => relay(c, "/api/v1/results/test-runs/latest/"))
  .get("/validation-runs", (c) => relay(c, "/api/v1/results/enforcement-runs/"))
  .get("/tasks", (c) => relay(c, "/api/v1/tasks/"))
  .get("/requirements", (c) => relay(c, "/api/v1/specs/"))
  .get("/requirements/:externalId/context", (c) =>
    relay(c, `/api/v1/specs/${encodeURIComponent(c.req.param("externalId"))}/context`),
  )
  .get("/requirements/:externalId/status", (c) =>
    relay(c, `/api/v1/specs/${encodeURIComponent(c.req.param("externalId"))}/status/`),
  )
  .get("/validation-runs/:id", (c) =>
    relay(c, `/api/v1/results/enforcement-runs/${encodeURIComponent(c.req.param("id"))}/`),
  )
  .get("/validation-runs/:id/steps", (c) =>
    relay(c, `/api/v1/results/enforcement-runs/${encodeURIComponent(c.req.param("id"))}/steps/`),
  )
  .get("/validation-runs/:id/diff", (c) =>
    relay(c, `/api/v1/results/enforcement-runs/${encodeURIComponent(c.req.param("id"))}/diff/`),
  )
  .get("/vendor-coverage", (c) => relay(c, "/api/v1/results/vendor-coverage/"))
  .get("/conflicts", (c) => relay(c, "/api/v1/results/conflicts/"))
  .get("/conflicts/counts", (c) => relay(c, "/api/v1/results/conflicts/counts"))
  .get("/conflicts/:id", (c) => relay(c, `/api/v1/results/conflicts/${encodeURIComponent(c.req.param("id"))}`))
  .get("/impact", (c) => relay(c, "/api/v1/specs/impact/"))
  .get("/drift", (c) => relay(c, "/api/v1/specs/drift/"))
  .get("/flow-runs/running", (c) => relay(c, "/api/v1/tasks/flow-runs/running/"))
  .get("/merge-safety", (c) => relay(c, "/api/v1/results/merge-safety"))
  .post("/conflicts/detect", (c) => relay(c, "/api/v1/results/conflicts/detect", "POST"))
  .post("/conflicts/:id/resolve", (c) =>
    relay(c, `/api/v1/results/conflicts/${encodeURIComponent(c.req.param("id"))}/resolve`, "POST"),
  )
  .get("/corpus/reviews", (c) => relay(c, "/api/v1/corpus/reviews/"))
  .get("/corpus/reviews/:id", (c) => relay(c, `/api/v1/corpus/reviews/${encodeURIComponent(c.req.param("id"))}/`))
  .get("/slo-status", (c) => relay(c, "/api/v1/integrations/slo/status"))
  .get("/reports/factory", (c) => relay(c, "/api/v1/reports/factory"))
  .post("/reviewer", (c) =>
    relayAs(c, "/api/v1/tasks/agents/register/", { agent_id: c.get("login"), role: "reviewer" }),
  )
  .post("/tasks/:taskId/approve-spec", async (c) =>
    relayAs(c, `/api/v1/tasks/${encodeURIComponent(c.req.param("taskId"))}/approve-spec`, {
      reviewer_id: c.get("login"),
      feedback: await reason(c, "feedback"),
    }),
  )
  .post("/tasks/:taskId/reject-spec", async (c) =>
    relayAs(c, `/api/v1/tasks/${encodeURIComponent(c.req.param("taskId"))}/reject-spec`, {
      reviewer_id: c.get("login"),
      reason: await reason(c, "reason"),
    }),
  );
