import { SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { requirements, slos } from "../src/db/schema";
import { db, get, insertRequirement, insertSlo, jsonOf, post, resetDatabase } from "./fixtures";

beforeEach(resetDatabase);

describe("POST /integrations/slo/status/", () => {
  it("updates named SLOs and recomputes requirement SLO status", async () => {
    const linked = await insertRequirement({ externalId: "REQ-SLO", verificationMethod: "test" });
    await insertRequirement({ externalId: "REQ-FREE" });
    await insertSlo("api-availability", [linked.id]);

    const res = await post("/integrations/slo/status/", {
      update_verification_status: true,
      slos: [
        { name: "api-availability", status: "breached", current_value: 0.98, error_budget_remaining: -0.1 },
        { name: "unknown-slo", status: "met" },
      ],
    });
    expect(res.status).toBe(200);
    expect(await jsonOf(res)).toEqual({
      success: true,
      updated: 1,
      not_found: 1,
      requirement_status: { met: 0, at_risk: 0, breached: 1, not_linked: 1 },
    });

    const slo = await db.query.slos.findFirst({ where: eq(slos.name, "api-availability") });
    expect(slo).toMatchObject({ status: "breached", currentValue: 0.98, errorBudgetRemaining: -0.1 });
    expect(slo?.lastUpdated).not.toBeNull();

    const requirement = await db.query.requirements.findFirst({ where: eq(requirements.id, linked.id) });
    expect(requirement).toMatchObject({ sloStatus: "breached", verificationStatus: "failing" });
    expect((await jsonOf(get("/specs/REQ-FREE/status/"))).data.verification_status).toBe("untested");
  });

  it("rejects an empty SLO list", async () => {
    const res = await post("/integrations/slo/status/", { slos: [] });
    expect(res.status).toBe(400);
    expect(await jsonOf(res)).toEqual({ success: false, error: "No SLOs in request" });
  });

  it("rejects a request without a JSON body", async () => {
    const res = await SELF.fetch("http://spectrace/api/v1/integrations/slo/status/", {
      method: "POST",
      headers: { "X-API-Key": "test-key" },
    });
    expect(res.status).toBe(400);
    expect(await jsonOf(res)).toEqual({ success: false, error: "No data provided" });
  });
});

describe("GET /integrations/slo/status", () => {
  it("lists SLOs with their linked requirements", async () => {
    const linked = await insertRequirement({ externalId: "REQ-SLO" });
    const slo = await insertSlo("api-availability", [linked.id]);

    const body = await jsonOf(get("/integrations/slo/status"));
    expect(body).toEqual({
      data: [
        {
          name: "api-availability",
          display_name: "api-availability",
          service: "api",
          target: 0.999,
          time_window: "30d",
          budgeting_method: "occurrences",
          status: "not_linked",
          current_value: null,
          error_budget_remaining: null,
          last_updated: null,
          requirement_ids: ["REQ-SLO"],
        },
      ],
    });
    expect(slo.name).toBe("api-availability");
  });
});
