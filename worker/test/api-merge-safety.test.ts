import { beforeEach, describe, expect, it } from "vitest";
import { conflictLogs, driftReports, impactReports } from "../src/db/schema";
import { db, get, insertRequirement, jsonOf, resetDatabase } from "./fixtures";

beforeEach(resetDatabase);

async function insertImpact(riskLevel: string, createdAt = "2026-01-01 00:00:00") {
  await db.insert(impactReports).values({
    project: "spectrace",
    baseRef: "main",
    headRef: "feature",
    payload: {
      project: "spectrace",
      base: "main",
      head: "feature",
      generated_at: "2026-01-01T00:00:00Z",
      changed_requirements: [],
      affected_tests: [],
      risk_score: 1,
      risk_level: riskLevel,
    },
    createdAt,
  });
}

async function insertDrift(errors: unknown[], warnings: unknown[], createdAt = "2026-01-01 00:00:00") {
  await db.insert(driftReports).values({
    project: "spectrace",
    payload: {
      project: "spectrace",
      generated_at: "2026-01-01T00:00:00Z",
      errors,
      warnings,
      summary: {},
    },
    createdAt,
  });
}

async function insertConflictWithConfidence(confidence: string) {
  const a = await insertRequirement({ externalId: `REQ-${confidence}-A` });
  const b = await insertRequirement({ externalId: `REQ-${confidence}-B` });
  await db.insert(conflictLogs).values({
    requirementAId: a.id,
    requirementBId: b.id,
    pattern: "timing_conflict",
    confidence,
    details: {},
    resolved: false,
    resolvedAt: null,
    resolutionNotes: "",
    createdAt: "2026-01-01 00:00:00",
    updatedAt: "2026-01-01 00:00:00",
  });
}

describe("GET /results/merge-safety", () => {
  it("is safe when nothing is pushed and no conflicts are open", async () => {
    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data).toEqual({
      generated_at: expect.any(String),
      verdict: "safe",
      impact: null,
      drift: null,
      conflicts: { open_count: 0, items: [] },
    });
  });

  it("is safe with a clean impact and drift report", async () => {
    await insertImpact("low");
    await insertDrift([], []);

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("safe");
    expect(body.data.impact.risk_level).toBe("low");
    expect(body.data.drift.errors).toEqual([]);
  });

  it("needs review when drift has warnings but no conflicts or errors", async () => {
    await insertDrift([], [{ type: "spec_drift", message: "stale link" }]);

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("needs_review");
  });

  it("needs review when an open conflict exists at medium confidence", async () => {
    await insertConflictWithConfidence("medium");

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("needs_review");
    expect(body.data.conflicts.open_count).toBe(1);
    expect(body.data.conflicts.items[0]).toMatchObject({ confidence: "medium", resolved: false });
  });

  it("needs review when impact risk is high", async () => {
    await insertImpact("high");

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("needs_review");
  });

  it("is blocked by a high-confidence unresolved conflict", async () => {
    await insertConflictWithConfidence("high");

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("blocked");
  });

  it("is blocked by drift errors even without conflicts", async () => {
    await insertDrift([{ type: "broken_link", message: "missing test" }], []);

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("blocked");
  });

  it("excludes resolved conflicts from the open list and count", async () => {
    const a = await insertRequirement({ externalId: "REQ-RESOLVED-A" });
    const b = await insertRequirement({ externalId: "REQ-RESOLVED-B" });
    await db.insert(conflictLogs).values({
      requirementAId: a.id,
      requirementBId: b.id,
      pattern: "timing_conflict",
      confidence: "high",
      details: {},
      resolved: true,
      resolvedAt: "2026-01-01 00:00:00",
      resolutionNotes: "fine",
      createdAt: "2026-01-01 00:00:00",
      updatedAt: "2026-01-01 00:00:00",
    });

    const body = await jsonOf(get("/results/merge-safety"));
    expect(body.data.verdict).toBe("safe");
    expect(body.data.conflicts).toEqual({ open_count: 0, items: [] });
  });
});
