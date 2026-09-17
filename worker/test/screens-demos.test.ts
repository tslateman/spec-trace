import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

async function fetchDemo(path: string) {
  return SELF.fetch(`http://spectrace${path}`, { redirect: "manual" });
}

describe("public demo page", () => {
  it("serves without a session or an API key", async () => {
    const response = await fetchDemo("/demo/");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/html");
  });

  it("explains the three steps and shows a requirement with its test", async () => {
    const body = await (await fetchDemo("/demo/")).text();
    expect(body).toContain("Write the requirement");
    expect(body).toContain("Link a test to it");
    expect(body).toContain("Push results from CI");
    expect(body).toContain("REQ-AUTH-001");
    expect(body).toContain("@pytest.mark.verifies(");
    expect(body).toContain("test_expired_session_redirects_to_login");
  });

  it("lists the CLI demos and leaves out the ones that only open a URL", async () => {
    const body = await (await fetchDemo("/demo/")).text();
    expect(body).toContain("just demo");
    expect(body).toContain("python scripts/demo_pipeline.py");
    expect(body).not.toContain("open http://localhost:8000/demo/");
  });

  it("emits the stylesheet unescaped, since a browser will not decode entities in a style element", async () => {
    const body = await (await fetchDemo("/demo/")).text();
    const styles = body.slice(body.indexOf("<style>"), body.indexOf("</style>"));

    expect(styles).toContain('"Segoe UI"');
    expect(styles).not.toContain("&quot;");
    expect(styles).not.toContain("&amp;");
  });

  it("points at the dashboard named by DASHBOARD_URL", async () => {
    const body = await (await fetchDemo("/demo/")).text();
    expect(body).toContain('href="https://spectrace-app.spectrace.workers.dev"');
  });

  it("sends the site root to the demo page, not to the sign-in", async () => {
    const response = await fetchDemo("/");
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("/demo/");
  });

  it("keeps the retired demo screens public by sending them to /demo/", async () => {
    for (const path of ["/demo/spectrace-overview/", "/demo/qa-ecosystem/"]) {
      const response = await fetchDemo(path);
      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe("/demo/");
    }
  });
});
