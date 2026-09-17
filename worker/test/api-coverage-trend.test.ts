import { beforeEach, describe, expect, it } from "vitest";
import { coverageSnapshots } from "../src/db/schema";
import { db, get, insertRequirement, jsonOf, post, resetDatabase } from "./fixtures";

beforeEach(resetDatabase);

const measurement = {
  commit_sha: "aaaa111",
  git_branch: "main",
  generated_at: "2026-09-01T12:00:00+00:00",
  specification_rate: 0.6,
  structure_rate: 0.4,
  verification_rate: 0.4,
  total: 5,
  non_draft: 3,
  passing: 2,
};

function push(overrides: Record<string, unknown> = {}) {
  return post("/results/coverage/", { project: "spectrace", ...measurement, ...overrides });
}

describe("POST /results/coverage/", () => {
  it("stores the snapshot and reports no predecessor on the first run", async () => {
    const res = await push();

    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({
      data: {
        project: "spectrace",
        generated_at: "2026-09-01T12:00:00+00:00",
        stored_at: expect.any(String),
        previous: null,
      },
    });
    const rows = await db.select().from(coverageSnapshots);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      project: "spectrace",
      commitSha: "aaaa111",
      gitBranch: "main",
      specificationRate: 0.6,
      structureRate: 0.4,
      verificationRate: 0.4,
      total: 5,
      nonDraft: 3,
      passing: 2,
      generatedAt: "2026-09-01 12:00:00.000000",
    });
  });

  it("returns the snapshot stored before it, so the caller sees the change", async () => {
    await push();

    const second = await push({
      commit_sha: "bbbb222",
      generated_at: "2026-09-02T12:00:00+00:00",
      verification_rate: 0.8,
      passing: 4,
    });

    const body = await jsonOf(second);
    expect(body.data.previous).toEqual({
      commit_sha: "aaaa111",
      git_branch: "main",
      generated_at: "2026-09-01T12:00:00.000000+00:00",
      stored_at: expect.any(String),
      specification_rate: 0.6,
      structure_rate: 0.4,
      verification_rate: 0.4,
      total: 5,
      non_draft: 3,
      passing: 2,
    });
  });

  it("keeps each project's series apart", async () => {
    await push();

    const other = await push({ project: "other", commit_sha: "cccc333" });

    expect((await jsonOf(other)).data.previous).toBeNull();
  });

  it("refuses a body whose rates are not numbers", async () => {
    const res = await push({ verification_rate: "lots" });

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: { code: "validation_error", message: "Expected number fields: verification_rate" },
    });
  });

  it("refuses a generated_at that is not a datetime", async () => {
    const res = await push({ generated_at: "yesterday" });

    expect(res.status).toBe(400);
    expect((await jsonOf(res)).error.message).toBe("Expected `generated_at` to be a datetime");
  });
});

describe("GET /specs/coverage/trend", () => {
  it("serves an empty series before any run", async () => {
    await insertRequirement();

    expect(await jsonOf(get("/specs/coverage/trend"))).toEqual({
      data: { project: "spectrace", snapshots: [] },
    });
  });

  it("serves the project's snapshots oldest first", async () => {
    await push({ commit_sha: "bbbb222", generated_at: "2026-09-02T12:00:00+00:00" });
    await push({ commit_sha: "aaaa111", generated_at: "2026-09-01T12:00:00+00:00" });
    await push({ project: "other", commit_sha: "zzzz999" });

    const body = await jsonOf(get("/specs/coverage/trend?project=spectrace"));

    expect(body.data.snapshots.map((snapshot: { commit_sha: string }) => snapshot.commit_sha)).toEqual([
      "aaaa111",
      "bbbb222",
    ]);
    expect(body.data.snapshots[0].generated_at).toBe("2026-09-01T12:00:00.000000+00:00");
  });

  it("keeps the most recent runs when limit cuts the series", async () => {
    for (const day of ["01", "02", "03"]) {
      await push({ commit_sha: `sha${day}`, generated_at: `2026-09-${day}T12:00:00+00:00` });
    }

    const body = await jsonOf(get("/specs/coverage/trend?project=spectrace&limit=2"));

    expect(body.data.snapshots.map((snapshot: { commit_sha: string }) => snapshot.commit_sha)).toEqual([
      "sha02",
      "sha03",
    ]);
  });

  it("rejects a non-integer limit", async () => {
    const res = await get("/specs/coverage/trend?limit=all");

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: { code: "invalid_query_param", message: "Invalid limit parameter" },
    });
  });
});
