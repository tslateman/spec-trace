import { beforeEach, describe, expect, it } from "vitest";
import { driftReports, impactReports } from "../src/db/schema";
import {
  db,
  get,
  insertDependency,
  insertLink,
  insertRequirement,
  insertTestRun,
  insertValidation,
  insertValidationResult,
  insertValidationRun,
  jsonOf,
  resetDatabase,
} from "./fixtures";

beforeEach(resetDatabase);

describe("GET /specs/", () => {
  it("pages requirements in tree order with filters and meta", async () => {
    await insertRequirement({ externalId: "REQ-B", path: "0002", verificationStatus: "failing" });
    await insertRequirement({ externalId: "REQ-A", path: "0001", verificationStatus: "passing" });
    await insertRequirement({ externalId: "REQ-C", path: "0003", verificationStatus: "passing" });

    const first = await jsonOf(await get("/specs/?per_page=2"));
    expect(first.data.project).toBe("spectrace");
    expect(first.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-A", "REQ-B"]);
    expect(first.meta).toEqual({
      page: 1,
      per_page: 2,
      total: 3,
      total_pages: 2,
      has_next: true,
      has_prev: false,
    });

    const second = await jsonOf(await get("/specs/?per_page=2&page=2"));
    expect(second.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-C"]);
    expect(second.meta.has_next).toBe(false);
    expect(second.meta.has_prev).toBe(true);
  });

  it("filters by verification status", async () => {
    await insertRequirement({ externalId: "REQ-PASS", verificationStatus: "passing" });
    await insertRequirement({ externalId: "REQ-FAIL", verificationStatus: "failing" });

    const body = await jsonOf(await get("/specs/?verification_status=failing"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-FAIL"]);
    expect(body.meta.total).toBe(1);
  });

  it("filters by tag", async () => {
    await insertRequirement({ externalId: "REQ-AUTH", tags: ["auth", "core"] });
    await insertRequirement({ externalId: "REQ-BILL", tags: ["billing"] });

    const body = await jsonOf(await get("/specs/?tags=auth"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-AUTH"]);
  });

  it("returns only descendants of parent_id", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", path: "0001", depth: 1, numchild: 2 });
    await insertRequirement({ externalId: "REQ-KID-1", path: "00010001", depth: 2 });
    await insertRequirement({ externalId: "REQ-KID-2", path: "00010002", depth: 2 });
    await insertRequirement({ externalId: "REQ-OTHER", path: "0002", depth: 1 });

    const body = await jsonOf(await get("/specs/?parent_id=REQ-ROOT"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual([
      "REQ-KID-1",
      "REQ-KID-2",
    ]);
  });

  it("returns an empty page when parent_id names no requirement", async () => {
    await insertRequirement({ externalId: "REQ-ONLY" });

    const body = await jsonOf(await get("/specs/?parent_id=REQ-MISSING"));
    expect(body.data.requirements).toEqual([]);
    expect(body.meta.total).toBe(0);
  });

  it("limits the page to the roots when max_depth is 1", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", path: "0001", depth: 1, numchild: 1 });
    await insertRequirement({ externalId: "REQ-KID", path: "00010001", depth: 2, numchild: 1 });
    await insertRequirement({ externalId: "REQ-GRANDKID", path: "000100010001", depth: 3 });
    await insertRequirement({ externalId: "REQ-OTHER", path: "0002", depth: 1 });

    const body = await jsonOf(await get("/specs/?max_depth=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual([
      "REQ-ROOT",
      "REQ-OTHER",
    ]);
    expect(body.meta.total).toBe(2);
  });

  it("counts max_depth from the parent when parent_id scopes the page", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", path: "0001", depth: 1, numchild: 1 });
    await insertRequirement({ externalId: "REQ-KID", path: "00010001", depth: 2, numchild: 1 });
    await insertRequirement({ externalId: "REQ-GRANDKID", path: "000100010001", depth: 3 });

    const body = await jsonOf(await get("/specs/?parent_id=REQ-ROOT&max_depth=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-KID"]);
  });

  it("rejects a non-numeric max_depth", async () => {
    const res = await get("/specs/?max_depth=deep");
    expect(res.status).toBe(400);
    expect((await jsonOf(res)).error.code).toBe("invalid_query_param");
  });

  it("rolls up each subtree by verification status and highest risk", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", path: "0001", depth: 1, numchild: 2, riskLevel: "low" });
    await insertRequirement({
      externalId: "REQ-KID-1",
      path: "00010001",
      depth: 2,
      numchild: 1,
      verificationStatus: "passing",
      riskLevel: "medium",
    });
    await insertRequirement({
      externalId: "REQ-GRANDKID",
      path: "000100010001",
      depth: 3,
      verificationStatus: "failing",
      riskLevel: "critical",
    });
    await insertRequirement({
      externalId: "REQ-KID-2",
      path: "00010002",
      depth: 2,
      verificationStatus: "untested",
      riskLevel: "high",
    });
    await insertRequirement({ externalId: "REQ-LEAF", path: "0002", depth: 1, riskLevel: "high" });

    const body = await jsonOf(await get("/specs/?max_depth=1"));
    const byId = Object.fromEntries(
      body.data.requirements.map((r: { external_id: string; descendants: unknown }) => [r.external_id, r.descendants]),
    );
    expect(byId["REQ-ROOT"]).toEqual({ total: 3, passing: 1, failing: 1, untested: 1, highest_risk: "critical" });
    expect(byId["REQ-LEAF"]).toEqual({ total: 0, passing: 0, failing: 0, untested: 0, highest_risk: "unclassified" });
  });

  it("keeps only requirements that need attention", async () => {
    await insertRequirement({ externalId: "REQ-FINE", verificationStatus: "passing", riskLevel: "low" });
    await insertRequirement({ externalId: "REQ-UNTESTED", verificationStatus: "untested", riskLevel: "low" });
    await insertRequirement({ externalId: "REQ-FAILING", verificationStatus: "failing", riskLevel: "medium" });

    const body = await jsonOf(await get("/specs/?attention=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual([
      "REQ-UNTESTED",
      "REQ-FAILING",
    ]);
  });

  it("drops passing requirements from attention however risky they are", async () => {
    await insertRequirement({ externalId: "REQ-RISKY", verificationStatus: "passing", riskLevel: "high" });
    await insertRequirement({ externalId: "REQ-DIRE", verificationStatus: "passing", riskLevel: "critical" });
    await insertRequirement({ externalId: "REQ-RISKY-FAILING", verificationStatus: "failing", riskLevel: "high" });
    await insertRequirement({
      externalId: "REQ-RISKY-UNTESTED",
      verificationStatus: "untested",
      riskLevel: "critical",
    });

    const body = await jsonOf(await get("/specs/?attention=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual([
      "REQ-RISKY-FAILING",
      "REQ-RISKY-UNTESTED",
    ]);
    expect(body.meta.total).toBe(2);
  });

  it("drops untested grouping parents whose descendants all pass", async () => {
    await insertRequirement({ externalId: "REQ-SETTLED", path: "0001", depth: 1, numchild: 1 });
    await insertRequirement({
      externalId: "REQ-SETTLED-KID",
      path: "00010001",
      depth: 2,
      verificationStatus: "passing",
    });
    await insertRequirement({ externalId: "REQ-UNSETTLED", path: "0002", depth: 1, numchild: 1 });
    await insertRequirement({
      externalId: "REQ-UNSETTLED-KID",
      path: "00020001",
      depth: 2,
      verificationStatus: "failing",
    });
    await insertRequirement({ externalId: "REQ-LONE", path: "0003", depth: 1, verificationStatus: "untested" });

    const body = await jsonOf(await get("/specs/?attention=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual([
      "REQ-UNSETTLED",
      "REQ-UNSETTLED-KID",
      "REQ-LONE",
    ]);
  });

  it("keeps a parent that claims children no requirement row supplies", async () => {
    await insertRequirement({ externalId: "REQ-ORPHANED", path: "0001", depth: 1, numchild: 2 });

    const body = await jsonOf(await get("/specs/?attention=1"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-ORPHANED"]);
  });

  it("describes the parent_id scope with its ancestors, root first", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", title: "Root", path: "0001", depth: 1, numchild: 1 });
    await insertRequirement({ externalId: "REQ-KID", title: "Kid", path: "00010001", depth: 2, numchild: 1 });
    await insertRequirement({ externalId: "REQ-GRANDKID", title: "Grandkid", path: "000100010001", depth: 3 });

    const body = await jsonOf(await get("/specs/?parent_id=REQ-KID"));
    expect(body.data.scope).toEqual({
      external_id: "REQ-KID",
      title: "Kid",
      ancestors: [{ external_id: "REQ-ROOT", title: "Root" }],
    });
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-GRANDKID"]);
  });

  it("omits the scope when parent_id names no requirement or is absent", async () => {
    await insertRequirement({ externalId: "REQ-ONLY" });

    expect((await jsonOf(await get("/specs/"))).data.scope).toBeUndefined();
    expect((await jsonOf(await get("/specs/?parent_id=REQ-MISSING"))).data.scope).toBeUndefined();
  });

  it("keeps a rollup inside the listed project", async () => {
    await insertRequirement({ externalId: "REQ-ROOT", path: "0001", depth: 1, numchild: 2 });
    await insertRequirement({ externalId: "REQ-MINE", path: "00010001", depth: 2, verificationStatus: "passing" });
    await insertRequirement({
      externalId: "REQ-THEIRS",
      path: "00010002",
      depth: 2,
      project: "other",
      verificationStatus: "failing",
    });

    const body = await jsonOf(await get("/specs/?project=spectrace&max_depth=1"));
    expect(body.data.requirements[0].descendants).toEqual({
      total: 1,
      passing: 1,
      failing: 0,
      untested: 0,
      highest_risk: "low",
    });
  });

  it("excludes requirements from other projects", async () => {
    await insertRequirement({ externalId: "REQ-MINE", project: "spectrace" });
    await insertRequirement({ externalId: "REQ-THEIRS", project: "other" });

    const body = await jsonOf(await get("/specs/?project=spectrace"));
    expect(body.data.requirements.map((r: { external_id: string }) => r.external_id)).toEqual(["REQ-MINE"]);
  });

  it("caps per_page at 100", async () => {
    await insertRequirement({ externalId: "REQ-CAP" });

    const body = await jsonOf(await get("/specs/?per_page=500"));
    expect(body.meta.per_page).toBe(100);
  });
});

describe("GET /specs/{id}/context [REQ-SPEC-001]", () => {
  it("returns the requirement with links, dependencies, and fret fields", async () => {
    const upstream = await insertRequirement({ externalId: "REQ-UP" });
    const req = await insertRequirement({
      externalId: "REQ-CTX",
      tags: ["auth"],
      scope: "all users",
      response: "show the dashboard",
    });
    const downstream = await insertRequirement({ externalId: "REQ-DOWN" });
    await insertDependency(req.id, upstream.id);
    await insertDependency(downstream.id, req.id);
    await insertLink(req.id, "tests/test_b.py::test_two", "failed");
    await insertLink(req.id, "tests/test_a.py::test_one");

    const res = await get("/specs/REQ-CTX/context");
    expect(res.status).toBe(200);
    expect(await jsonOf(res)).toEqual({
      data: {
        external_id: "REQ-CTX",
        title: req.title,
        description: "",
        tags: ["auth"],
        status: "active",
        verification_status: "untested",
        priority: "medium",
        test_results: [
          { test_nodeid: "tests/test_a.py::test_one", last_status: "passed" },
          { test_nodeid: "tests/test_b.py::test_two", last_status: "failed" },
        ],
        depends_on: ["REQ-UP"],
        depended_by: ["REQ-DOWN"],
        fret: { scope: "all users", response: "show the dashboard" },
      },
    });
  });

  it("omits fret when every structured field is empty", async () => {
    await insertRequirement({ externalId: "REQ-BARE" });
    const body = await jsonOf(get("/specs/REQ-BARE/context"));
    expect(body.data).not.toHaveProperty("fret");
  });

  it("returns the not_found envelope for an unknown id", async () => {
    const res = await get("/specs/REQ-NOPE/context");
    expect(res.status).toBe(404);
    expect(await jsonOf(res)).toEqual({ error: { code: "not_found", message: "Spec not found for REQ-NOPE" } });
  });
});

describe("GET /specs/{id}/status/ [REQ-SPEC-005]", () => {
  it("reports empty validation state when nothing has been checked", async () => {
    const req = await insertRequirement({ externalId: "REQ-S1", title: "Login" });
    const res = await get("/specs/REQ-S1/status/");
    expect(await jsonOf(res)).toEqual({
      data: {
        external_id: "REQ-S1",
        title: req.title,
        verification_status: "untested",
        last_checked: null,
        latest_result: null,
        regression: { is_regression: false },
      },
    });
  });

  it("detects a regression from the two newest results", async () => {
    const req = await insertRequirement({ externalId: "REQ-S2" });
    const validation = await insertValidation(req.id);
    const run = await insertValidationRun("2026-02-01 10:00:00");
    await insertValidationResult(run.id, validation.id, "success", "2026-02-01 09:00:00.000001");
    await insertValidationResult(run.id, validation.id, "failure", "2026-02-01 10:00:00.500000", [
      { name: "open", passed: true },
      { name: "submit", passed: false },
    ]);

    const body = await jsonOf(get("/specs/REQ-S2/status"));
    expect(body.data.last_checked).toBe("2026-02-01T10:00:00.500000+00:00");
    expect(body.data.latest_result).toEqual({
      status: "failure",
      message: "failure message",
      checked_at: "2026-02-01T10:00:00.500000+00:00",
      steps_passed: 1,
      steps_failed: 1,
    });
    expect(body.data.regression).toEqual({
      is_regression: true,
      previous_status: "success",
      regressed_at: "2026-02-01T10:00:00.500000+00:00",
    });
  });

  it("returns 404 for an unknown requirement", async () => {
    const res = await get("/specs/REQ-MISSING/status/");
    expect(res.status).toBe(404);
    expect((await jsonOf(res)).error.message).toBe("Requirement REQ-MISSING not found");
  });
});

describe("GET /specs/coverage/ [REQ-SPEC-002]", () => {
  it("counts the project and names requirements whose tests left the latest run", async () => {
    const stale = await insertRequirement({ externalId: "REQ-STALE", verificationStatus: "passing" });
    const fresh = await insertRequirement({ externalId: "REQ-FRESH", verificationStatus: "failing" });
    await insertRequirement({ externalId: "REQ-DRAFT", status: "draft" });
    await insertRequirement({ externalId: "REQ-OTHER", project: "other" });
    await insertLink(stale.id, "tests/test_old.py::test_gone");
    await insertLink(fresh.id, "tests/test_new.py::test_here");
    await insertTestRun("2026-01-01 00:00:00", ["tests/test_old.py::test_gone", "tests/test_new.py::test_here"]);
    await insertTestRun("2026-01-02 00:00:00", ["tests/test_new.py::test_here"]);

    const res = await get("/specs/coverage/");
    expect(await jsonOf(res)).toEqual({
      data: {
        project: "spectrace",
        metrics: { total: 3, non_draft: 2, passing: 1, failing: 1, untested: 1, stale: 1 },
        stale_requirements: ["REQ-STALE"],
      },
    });
  });

  it("adds requirements the newest drift report flags as spec drift", async () => {
    await insertRequirement({ externalId: "REQ-DRIFTED" });
    await insertTestRun("2026-01-01 00:00:00", []);
    await db.insert(driftReports).values({
      project: "spectrace",
      payload: { warnings: [{ type: "spec_drift", affected_requirements: ["REQ-DRIFTED", "REQ-ELSEWHERE"] }] },
      createdAt: "2026-01-03 00:00:00",
    });
    const body = await jsonOf(get("/specs/coverage"));
    expect(body.data.stale_requirements).toEqual(["REQ-DRIFTED"]);
  });

  it("asks for a project when several are stored and none is installed", async () => {
    await insertRequirement({ project: "alpha" });
    await insertRequirement({ project: "beta" });
    const res = await get("/specs/coverage/");
    expect(res.status).toBe(400);
    const body = await jsonOf(res);
    expect(body.error.code).toBe("ambiguous_project");
    expect(body.error.details).toEqual({ projects: ["alpha", "beta"] });

    const chosen = await jsonOf(get("/specs/coverage/?project=beta"));
    expect(chosen.data.project).toBe("beta");
    expect(chosen.data.metrics.total).toBe(1);
  });
});

describe("GET /specs/drift/ and /specs/impact/ [REQ-SPEC-003][REQ-SPEC-004]", () => {
  it("returns 404 envelopes when no report has been pushed", async () => {
    const drift = await get("/specs/drift/");
    expect(drift.status).toBe(404);
    expect((await jsonOf(drift)).error.code).toBe("not_found");
    const impact = await get("/specs/impact/");
    expect(impact.status).toBe(404);
  });

  it("serves the newest pushed report for the project", async () => {
    await db
      .insert(driftReports)
      .values({ project: "spectrace", payload: { summary: 1 }, createdAt: "2026-01-01 00:00:00" });
    await db
      .insert(driftReports)
      .values({ project: "spectrace", payload: { summary: 2 }, createdAt: "2026-01-02 00:00:00" });
    await db.insert(impactReports).values({
      project: "spectrace",
      baseRef: "main",
      headRef: "feature",
      payload: { risk_level: "low" },
      createdAt: "2026-01-02 00:00:00",
    });
    expect(await jsonOf(get("/specs/drift/"))).toEqual({ data: { summary: 2 } });
    expect(await jsonOf(get("/specs/impact/"))).toEqual({ data: { risk_level: "low" } });
  });
});
