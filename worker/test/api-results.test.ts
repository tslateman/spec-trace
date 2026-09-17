import { SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { conflictLogs, inAppValidations } from "../src/db/schema";
import {
  db,
  get,
  insertConflict,
  insertLink,
  insertRequirement,
  insertTestRun,
  insertValidation,
  insertValidationResult,
  insertValidationRun,
  jsonOf,
  post,
  resetDatabase,
} from "./fixtures";

beforeEach(resetDatabase);

describe("GET /results/conflicts/ [REQ-RSLT-001]", () => {
  it("lists newest first with pagination meta", async () => {
    const a = await insertRequirement({ externalId: "REQ-A" });
    const b = await insertRequirement({ externalId: "REQ-B" });
    const c = await insertRequirement({ externalId: "REQ-C" });
    const older = await insertConflict(a.id, b.id, "2026-01-01 00:00:00");
    const newer = await insertConflict(b.id, c.id, "2026-01-02 00:00:00");

    const body = await jsonOf(get("/results/conflicts/?per_page=1"));
    expect(body).toEqual({
      data: [
        {
          id: newer.id,
          requirement_a: "REQ-B",
          requirement_b: "REQ-C",
          pattern: "timing_conflict",
          confidence: "high",
          resolved: false,
          resolution_reason: "unspecified",
          times_detected: 1,
          last_seen_at: "2026-01-02T00:00:00+00:00",
          created_at: "2026-01-02T00:00:00+00:00",
        },
      ],
      meta: { page: 1, per_page: 1, total: 2, total_pages: 2, has_next: true, has_prev: false },
    });

    const filtered = await jsonOf(get("/results/conflicts/?requirement_id=REQ-A"));
    expect(filtered.data.map((row: { id: number }) => row.id)).toEqual([older.id]);
  });

  it("rejects a non-integer per_page", async () => {
    const res = await get("/results/conflicts/?per_page=lots");
    expect(res.status).toBe(400);
    expect(await jsonOf(res)).toEqual({
      error: { code: "invalid_query_param", message: "Invalid per_page parameter" },
    });
  });
});

describe("conflict detail and resolve [REQ-RSLT-003][REQ-RSLT-004]", () => {
  it("returns full detail, resolves once, and refuses a second resolution", async () => {
    const a = await insertRequirement({ externalId: "REQ-A", title: "Alpha" });
    const b = await insertRequirement({ externalId: "REQ-B", title: "Beta" });
    const conflict = await insertConflict(a.id, b.id, "2026-01-01 00:00:00");

    const detail = await jsonOf(get(`/results/conflicts/${conflict.id}`));
    expect(detail.data).toEqual({
      id: conflict.id,
      requirement_a: "REQ-A",
      requirement_b: "REQ-B",
      requirement_a_title: "Alpha",
      requirement_b_title: "Beta",
      pattern: "timing_conflict",
      confidence: "high",
      details: { ratio: 5 },
      resolved: false,
      resolved_at: null,
      resolution_notes: "",
      resolution_reason: "unspecified",
      times_detected: 1,
      last_seen_at: "2026-01-01T00:00:00+00:00",
      created_at: "2026-01-01T00:00:00+00:00",
    });

    const resolved = await post(`/results/conflicts/${conflict.id}/resolve`, { resolution_notes: "duplicate" });
    expect(resolved.status).toBe(200);
    const resolvedBody = await jsonOf(resolved);
    expect(resolvedBody.data.conflict_id).toBe(conflict.id);
    expect(resolvedBody.data.resolved_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/);
    expect(resolvedBody.data.resolution_reason).toBe("unspecified");

    const after = await jsonOf(get(`/results/conflicts/${conflict.id}`));
    expect(after.data.resolved).toBe(true);
    expect(after.data.resolution_notes).toBe("duplicate");
    expect(after.data.resolution_reason).toBe("unspecified");

    const again = await post(`/results/conflicts/${conflict.id}/resolve`, {});
    expect(again.status).toBe(400);
    expect((await jsonOf(again)).error.code).toBe("invalid_state");
  });

  it("returns 404 for an unknown conflict", async () => {
    expect((await get("/results/conflicts/999")).status).toBe(404);
    expect((await post("/results/conflicts/999/resolve", {})).status).toBe(404);
  });

  it.each(["false_positive", "fixed", "accepted", "wont_fix"] as const)(
    "persists and returns resolution_reason %s",
    async (reason) => {
      const a = await insertRequirement({ externalId: "REQ-A" });
      const b = await insertRequirement({ externalId: "REQ-B" });
      const conflict = await insertConflict(a.id, b.id, "2026-01-01 00:00:00");

      const resolved = await post(`/results/conflicts/${conflict.id}/resolve`, { resolution_reason: reason });
      expect(resolved.status).toBe(200);
      expect((await jsonOf(resolved)).data.resolution_reason).toBe(reason);

      const after = await jsonOf(get(`/results/conflicts/${conflict.id}`));
      expect(after.data.resolution_reason).toBe(reason);
    },
  );

  it("rejects a bogus resolution_reason without mutating the row", async () => {
    const a = await insertRequirement({ externalId: "REQ-A" });
    const b = await insertRequirement({ externalId: "REQ-B" });
    const conflict = await insertConflict(a.id, b.id, "2026-01-01 00:00:00");

    const res = await post(`/results/conflicts/${conflict.id}/resolve`, { resolution_reason: "bogus" });
    expect(res.status).toBe(400);
    expect((await jsonOf(res)).error.code).toBe("invalid_reason");

    const after = await jsonOf(get(`/results/conflicts/${conflict.id}`));
    expect(after.data.resolved).toBe(false);
    expect(after.data.resolution_reason).toBe("unspecified");
  });
});

describe("GET /results/conflicts/counts [REQ-RSLT-001]", () => {
  it("computes global counts across confidence and resolution reason", async () => {
    const a = await insertRequirement({ externalId: "REQ-A" });
    const b = await insertRequirement({ externalId: "REQ-B" });
    const c = await insertRequirement({ externalId: "REQ-C" });
    const d = await insertRequirement({ externalId: "REQ-D" });

    await insertConflict(a.id, b.id, "2026-01-01 00:00:00");
    const medium = await insertConflict(b.id, c.id, "2026-01-02 00:00:00");
    await db.update(conflictLogs).set({ confidence: "medium" }).where(eq(conflictLogs.id, medium.id));
    const low = await insertConflict(c.id, d.id, "2026-01-03 00:00:00");
    await db.update(conflictLogs).set({ confidence: "low" }).where(eq(conflictLogs.id, low.id));
    const resolvedFalsePositive = await insertConflict(a.id, c.id, "2026-01-04 00:00:00");
    const resolvedOther = await insertConflict(a.id, d.id, "2026-01-05 00:00:00");

    await post(`/results/conflicts/${resolvedFalsePositive.id}/resolve`, { resolution_reason: "false_positive" });
    await post(`/results/conflicts/${resolvedOther.id}/resolve`, { resolution_reason: "fixed" });

    const body = await jsonOf(get("/results/conflicts/counts"));
    expect(body.data).toEqual({
      open: 3,
      open_high: 1,
      open_medium: 1,
      open_low: 1,
      resolved: 2,
      false_positive: 1,
    });
  });
});

describe("POST /results/conflicts/detect [REQ-RSLT-002]", () => {
  it("logs structured conflicts once and skips them on the next run", async () => {
    await insertRequirement({ externalId: "REQ-FAST", component: "Lock", timing: "within 1 second" });
    await insertRequirement({ externalId: "REQ-SLOW", component: "lock", timing: "within 10 seconds" });
    await insertRequirement({
      externalId: "REQ-SHOW",
      component: "battery",
      condition: "battery_level < 20",
      response: "show the warning",
    });
    await insertRequirement({
      externalId: "REQ-HIDE",
      component: "battery",
      condition: "battery_level < 10",
      response: "hide the warning",
    });

    const first = await jsonOf(post("/results/conflicts/detect", {}));
    expect(first.data).toEqual({ conflicts_found: 3, logged: 3, skipped_existing: 0 });

    const second = await jsonOf(post("/results/conflicts/detect", {}));
    expect(second.data).toEqual({ conflicts_found: 3, logged: 0, skipped_existing: 3 });

    const patterns = (await jsonOf(get("/results/conflicts/"))).data.map((row: { pattern: string }) => row.pattern);
    expect(patterns.sort()).toEqual(["condition_overlap", "response_contradiction", "timing_conflict"]);
  });

  it("leaves structured detection out when asked", async () => {
    await insertRequirement({ component: "lock", timing: "1s" });
    await insertRequirement({ component: "lock", timing: "10s" });
    const body = await jsonOf(post("/results/conflicts/detect", { include_structured: false }));
    expect(body.data).toEqual({ conflicts_found: 0, logged: 0, skipped_existing: 0 });
  });

  it("rejects a malformed body", async () => {
    const res = await SELF.fetch("http://spectrace/api/v1/results/conflicts/detect", {
      method: "POST",
      headers: { "X-API-Key": "test-key" },
      body: "{nope",
    });
    expect(res.status).toBe(400);
    expect((await jsonOf(res)).error.code).toBe("invalid_json");
  });
});

describe("POST /results/test-runs/", () => {
  it("stores a run, links results to requirements, and drives test-verified status", async () => {
    const t1 = await insertRequirement({ externalId: "REQ-T1", verificationMethod: "test" });
    const t2 = await insertRequirement({ externalId: "REQ-T2", verificationMethod: "test" });
    await insertLink(t1.id, "tests/test_a.py::test_ok");
    await insertLink(t2.id, "tests/test_b.py::test_bad");

    const res = await post("/results/test-runs/", {
      source_file: "test_results.xml",
      git_sha: "abc123",
      git_branch: "main",
      update_verification_status: true,
      results: [
        { test_nodeid: "tests/test_a.py::test_ok", status: "passed", requirement_ids: ["REQ-T1"] },
        { test_nodeid: "tests/test_b.py::test_bad", status: "failed", requirement_ids: ["REQ-T2"] },
        { test_nodeid: "tests/test_c.py::test_free", status: "passed", requirement_ids: ["REQ-NONE"] },
      ],
    });
    expect(res.status).toBe(200);
    const body = await jsonOf(res);
    expect(body).toMatchObject({ success: true, imported: 3, linked: 2, passed: 2, failed: 1 });

    expect((await jsonOf(get("/specs/REQ-T1/status/"))).data.verification_status).toBe("passing");
    expect((await jsonOf(get("/specs/REQ-T2/status/"))).data.verification_status).toBe("failing");

    const context = await jsonOf(get("/specs/REQ-T2/context"));
    expect(context.data.test_results).toEqual([{ test_nodeid: "tests/test_b.py::test_bad", last_status: "failed" }]);

    const latest = await jsonOf(get("/results/test-runs/latest/"));
    expect(latest.test_run).toMatchObject({
      source_file: "test_results.xml",
      git_sha: "abc123",
      git_branch: "main",
      total_tests: 3,
    });
  });

  it("rejects a body with no source_file", async () => {
    const res = await post("/results/test-runs/", { results: [] });
    expect(res.status).toBe(400);
    expect((await jsonOf(res)).error).toContain("source_file");
  });
});

describe("POST /results/enforcement/", () => {
  it("records a run, creates validations, and reports counts", async () => {
    await insertRequirement({ externalId: "REQ-E1", verificationMethod: "inapp" });
    await insertRequirement({ externalId: "REQ-E2" });

    const res = await post("/results/enforcement/", {
      source: "product",
      update_verification_status: true,
      validations: [
        {
          requirement_id: "REQ-E1",
          name: "Verify login",
          status: "success",
          checked_at: "2026-03-01T12:00:00Z",
          steps: [{ name: "open", passed: true }],
          context: { vendor: "Opera" },
        },
        { requirement_id: "REQ-E2", name: "Verify logout", status: "degraded" },
        { requirement_id: "REQ-NONE", name: "Orphan", status: "success" },
      ],
    });
    expect(res.status).toBe(200);
    expect(await jsonOf(res)).toEqual({
      success: true,
      imported: 2,
      skipped: 1,
      created_validations: 2,
      successful: 1,
      failed: 1,
    });

    const status = await jsonOf(get("/specs/REQ-E1/status/"));
    expect(status.data.verification_status).toBe("passing");
    expect(status.data.latest_result.checked_at).toBe("2026-03-01T12:00:00.000000+00:00");
    const failing = await jsonOf(get("/specs/REQ-E2/status/"));
    expect(failing.data.verification_status).toBe("failing");
  });

  it("rejects a body without validations", async () => {
    const res = await post("/results/enforcement/", { source: "product", validations: [] });
    expect(res.status).toBe(400);
    expect(await jsonOf(res)).toEqual({ success: false, error: "No validations in request" });
  });
});

describe("enforcement run reads", () => {
  async function seedTwoRuns() {
    const req = await insertRequirement({ externalId: "REQ-R1" });
    const validation = await insertValidation(req.id, "Verify login", "Opera");
    const first = await insertValidationRun("2026-01-01 00:00:00", "nightly");
    const second = await insertValidationRun("2026-01-02 00:00:00", "manual");
    await insertValidationResult(first.id, validation.id, "failure", "2026-01-01 00:00:00", [
      { name: "open", passed: false },
    ]);
    await insertValidationResult(second.id, validation.id, "success", "2026-01-02 00:00:00", [
      { name: "open", passed: true },
    ]);
    return { first, second, validation };
  }

  it("lists runs newest first with pagination", async () => {
    const { first, second } = await seedTwoRuns();
    const body = await jsonOf(get("/results/enforcement-runs/?per_page=1"));
    expect(body).toEqual({
      data: [
        {
          id: second.id,
          source: "manual",
          imported_at: "2026-01-02T00:00:00+00:00",
          total_validations: 1,
          successful: 1,
          failed: 0,
        },
      ],
      meta: { page: 1, per_page: 1, total: 2, total_pages: 2, has_next: true, has_prev: false },
    });
    const failed = await jsonOf(get("/results/enforcement-runs/?status=failure"));
    expect(failed.data.map((run: { id: number }) => run.id)).toEqual([first.id]);
  });

  it("[REQ-RSLT-005] serves the latest run with its pass rate", async () => {
    const { second } = await seedTwoRuns();
    const body = await jsonOf(get("/results/enforcement-runs/latest/"));
    expect(body.data).toEqual({
      run_id: second.id,
      source: "manual",
      imported_at: "2026-01-02T00:00:00+00:00",
      pass_rate: 100,
      total: 1,
      passed: 1,
      failed: 0,
    });
    const filtered = await jsonOf(get("/results/enforcement-runs/latest/?source=NIGHT"));
    expect(filtered.data.source).toBe("nightly");
    expect((await get("/results/enforcement-runs/latest/?source=none")).status).toBe(404);
  });

  it("returns detail and steps for a run", async () => {
    const { second, validation } = await seedTwoRuns();
    const detail = await jsonOf(get(`/results/enforcement-runs/${second.id}/`));
    expect(detail.results).toEqual([
      expect.objectContaining({
        validation_id: validation.id,
        validation_name: "Verify login",
        requirement_id: "REQ-R1",
        vendor: "Opera",
        status: "success",
        step_count: 1,
        steps_passed: 1,
      }),
    ]);
    const steps = await jsonOf(get(`/results/enforcement-runs/${second.id}/steps/`));
    expect(steps.run_id).toBe(second.id);
    expect(steps.results[0].steps).toEqual([{ name: "open", passed: true }]);
    expect((await get("/results/enforcement-runs/999/")).status).toBe(404);
  });

  it("[REQ-RSLT-006] diffs a run against its predecessor", async () => {
    const { first, second } = await seedTwoRuns();
    const noPredecessor = await get(`/results/enforcement-runs/${first.id}/diff/`);
    expect(noPredecessor.status).toBe(409);
    expect((await jsonOf(noPredecessor)).error.code).toBe("no_predecessor");

    const body = await jsonOf(get(`/results/enforcement-runs/${second.id}/diff/`));
    expect(body.data).toEqual({
      compared_to: { id: first.id, source: "nightly", imported_at: "2026-01-01T00:00:00+00:00" },
      summary: { improved: 1, regressed: 0, unchanged: 0, new: 0, removed: 0 },
      changes: [
        {
          requirement_id: "REQ-R1",
          validation_name: "Verify login",
          vendor: "Opera",
          status_a: "failure",
          status_b: "success",
          change_type: "improved",
        },
      ],
    });
  });
});

describe("GET /results/vendor-coverage/", () => {
  it("reports pass rate, regressions, and feature flags across vendors, including one with no results", async () => {
    const reqA1 = await insertRequirement({ externalId: "REQ-V1" });
    const reqA2 = await insertRequirement({ externalId: "REQ-V2" });
    const reqB1 = await insertRequirement({ externalId: "REQ-V3" });
    const valA1 = await insertValidation(reqA1.id, "Verify charge", "Stripe");
    const valA2 = await insertValidation(reqA2.id, "Verify refund", "Stripe");
    await insertValidation(reqB1.id, "Verify sms", "Twilio");

    await db
      .update(inAppValidations)
      .set({ featureFlags: { beta_checkout: true } })
      .where(eq(inAppValidations.id, valA1.id));
    await db
      .update(inAppValidations)
      .set({ featureFlags: { beta_checkout: true, new_ui: true } })
      .where(eq(inAppValidations.id, valA2.id));

    const run1 = await insertValidationRun("2026-01-01 00:00:00", "nightly");
    const run2 = await insertValidationRun("2026-01-02 00:00:00", "nightly");
    await insertValidationResult(run1.id, valA1.id, "success", "2026-01-01 00:00:00");
    await insertValidationResult(run2.id, valA1.id, "failure", "2026-01-02 00:00:00");
    await insertValidationResult(run1.id, valA2.id, "success", "2026-01-01 00:00:00");

    const body = await jsonOf(get("/results/vendor-coverage/"));
    expect(body.data).toEqual({
      project: "spectrace",
      vendors: [
        {
          name: "Stripe",
          total: 2,
          passing: 1,
          failing: 1,
          not_run: 0,
          pass_rate: 50,
          regressions: [{ name: "Verify charge", regressed_at: "2026-01-02T00:00:00+00:00", run_id: run2.id }],
          common_flags: [
            { flag: "beta_checkout", count: 2 },
            { flag: "new_ui", count: 1 },
          ],
        },
        {
          name: "Twilio",
          total: 1,
          passing: 0,
          failing: 0,
          not_run: 1,
          pass_rate: 0,
          regressions: [],
          common_flags: [],
        },
      ],
      all_flags: ["beta_checkout", "new_ui"],
      total_vendors: 2,
      total_validations: 3,
    });
  });

  it("scopes vendors to the requested project", async () => {
    const inSpectrace = await insertRequirement({ externalId: "REQ-P1", project: "spectrace" });
    const inOther = await insertRequirement({ externalId: "REQ-P2", project: "other" });
    await insertValidation(inSpectrace.id, "Verify a", "VendorA");
    await insertValidation(inOther.id, "Verify b", "VendorB");

    const spectrace = await jsonOf(get("/results/vendor-coverage/?project=spectrace"));
    expect(spectrace.data.vendors.map((vendor: { name: string }) => vendor.name)).toEqual(["VendorA"]);

    const other = await jsonOf(get("/results/vendor-coverage/?project=other"));
    expect(other.data.project).toBe("other");
    expect(other.data.vendors.map((vendor: { name: string }) => vendor.name)).toEqual(["VendorB"]);
  });
});

describe("GET /results/test-runs/latest/", () => {
  it("returns null when nothing has been imported", async () => {
    expect(await jsonOf(get("/results/test-runs/latest/"))).toEqual({ test_run: null });
  });

  it("summarises the newest run and honours since", async () => {
    await insertTestRun("2026-01-01 00:00:00", ["t::a"]);
    const latest = await insertTestRun("2026-01-02 00:00:00", ["t::a", "t::b"], "failed");
    const body = await jsonOf(get("/results/test-runs/latest/"));
    expect(body.test_run).toEqual({
      id: latest.id,
      imported_at: "2026-01-02T00:00:00+00:00",
      source_file: "junit.xml",
      git_sha: "abc123",
      git_branch: "main",
      workflow_name: "ci",
      workflow_run_id: null,
      repository: "tslater/spec-trace",
      total_tests: 2,
      passed: 0,
      failed: 2,
      errors: 0,
      skipped: 0,
    });
    expect((await get("/results/test-runs/latest/?since=2026-01-03T00:00:00Z")).status).toBe(204);
    expect((await get("/results/test-runs/latest/?since=yesterday")).status).toBe(400);
  });
});
