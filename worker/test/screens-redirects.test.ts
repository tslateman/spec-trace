import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const DASHBOARD = "https://spectrace-app.spectrace.workers.dev";

async function locationOf(path: string): Promise<{ status: number; location: string | null }> {
  const response = await SELF.fetch(`http://spectrace${path}`, { redirect: "manual" });
  return { status: response.status, location: response.headers.get("location") };
}

describe("screen redirects", () => {
  it.each([
    ["/getting-started/", "/getting-started"],
    ["/admin/about/", "/about"],
    ["/admin/matrix/", "/specs"],
    ["/admin/matrix/export/", "/specs"],
    ["/admin/high-risk/", "/high-risk"],
    ["/admin/impact-analysis/", "/impact"],
    ["/admin/spec-syntax/", "/spec-syntax"],
    ["/admin/vendor-coverage/", "/vendor-coverage"],
    ["/admin/validation-runs/", "/runs"],
    ["/admin/validation-runs/compare/", "/runs"],
  ])("sends %s to the dashboard at %s", async (from, to) => {
    const { status, location } = await locationOf(from);
    expect(status).toBe(302);
    expect(location).toBe(`${DASHBOARD}${to}`);
  });

  it("redirects without the trailing slash too", async () => {
    const { status, location } = await locationOf("/admin/matrix");
    expect(status).toBe(302);
    expect(location).toBe(`${DASHBOARD}/specs`);
  });

  it("carries the query string across", async () => {
    const { location } = await locationOf("/admin/matrix/?verification_status=failing&page=2");
    expect(location).toBe(`${DASHBOARD}/specs?verification_status=failing&page=2`);
  });

  it("sends a requirement to its dashboard page", async () => {
    const { status, location } = await locationOf("/admin/requirement/REQ-AUTH-001/");
    expect(status).toBe(302);
    expect(location).toBe(`${DASHBOARD}/specs/REQ-AUTH-001`);
  });

  it("escapes a requirement id that needs it", async () => {
    const { location } = await locationOf("/admin/requirement/REQ%2FA%201/");
    expect(location).toBe(`${DASHBOARD}/specs/REQ%2FA%201`);
  });

  it("sends a validation run and its steps to the run page", async () => {
    expect((await locationOf("/admin/validation-runs/42/")).location).toBe(`${DASHBOARD}/runs/42`);
    expect((await locationOf("/admin/validation-runs/42/steps/")).location).toBe(`${DASHBOARD}/runs/42`);
  });

  it("retires the flow screens", async () => {
    for (const path of [
      "/admin/flow-status/",
      "/admin/flow-status/live/",
      "/admin/flow-status/live.json",
      "/admin/flow-status/run/7/",
      "/admin/flow-status/nightly/",
      "/admin/matrix/updates.json",
    ]) {
      expect((await locationOf(path)).status).toBe(404);
    }
  });

  it("leaves the API alone", async () => {
    const response = await SELF.fetch("http://spectrace/api/v1/specs/coverage/", {
      headers: { "x-api-key": "test-key" },
      redirect: "manual",
    });
    expect(response.status).toBe(200);
  });
});
