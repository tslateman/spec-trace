import { Hono } from "hono";
import type { Env } from "../env";

type RedirectContext = { env: Env; req: { url: string } };

const MOVED: Record<string, string> = {
  "/getting-started": "/getting-started",
  "/admin/about": "/about",
  "/admin/matrix": "/specs",
  "/admin/matrix/export": "/specs",
  "/admin/high-risk": "/high-risk",
  "/admin/impact-analysis": "/impact",
  "/admin/spec-syntax": "/spec-syntax",
  "/admin/vendor-coverage": "/vendor-coverage",
  "/admin/validation-runs": "/runs",
  "/admin/validation-runs/compare": "/runs",
};

function dashboardUrl(c: RedirectContext, target: string): string {
  const destination = new URL(target, c.env.DASHBOARD_URL);
  destination.search = new URL(c.req.url).search;
  return destination.toString();
}

export const screenRedirects = new Hono<{ Bindings: Env }>();

for (const [from, to] of Object.entries(MOVED)) {
  screenRedirects.get(from, (c) => c.redirect(dashboardUrl(c, to), 302));
}

screenRedirects.get("/admin/requirement/:externalId", (c) =>
  c.redirect(dashboardUrl(c, `/specs/${encodeURIComponent(c.req.param("externalId"))}`), 302),
);

screenRedirects.get("/admin/validation-runs/:runId{[0-9]+}", (c) =>
  c.redirect(dashboardUrl(c, `/runs/${c.req.param("runId")}`), 302),
);

screenRedirects.get("/admin/validation-runs/:runId{[0-9]+}/steps", (c) =>
  c.redirect(dashboardUrl(c, `/runs/${c.req.param("runId")}`), 302),
);
