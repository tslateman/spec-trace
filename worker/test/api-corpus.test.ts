import { beforeEach, describe, expect, it } from "vitest";
import {
  get,
  insertCorpusEntryVersion,
  insertCorpusSnapshot,
  insertRequirement,
  insertReviewCoverage,
  insertReviewFinding,
  insertSpecReview,
  jsonOf,
  resetDatabase,
} from "./fixtures";

beforeEach(resetDatabase);

describe("GET /corpus/reviews/", () => {
  it("lists newest first with pagination meta", async () => {
    const req = await insertRequirement({ externalId: "REQ-A" });
    const snapshot = await insertCorpusSnapshot("snap-1");
    const older = await insertSpecReview(req.id, snapshot.id, { createdAt: "2026-01-01 00:00:00" });
    const newer = await insertSpecReview(req.id, snapshot.id, { createdAt: "2026-01-02 00:00:00" });

    const body = await jsonOf(get("/corpus/reviews/?per_page=1"));
    expect(body).toEqual({
      data: [
        {
          id: newer.id,
          requirement_id: "REQ-A",
          spec_file: "specs/auth.md",
          reviewer: "reviewer-a",
          outcome: "approved",
          created_at: "2026-01-02T00:00:00+00:00",
          snapshot_hash: "snap-1",
          coverage_count: 0,
          findings_count: 0,
        },
      ],
      meta: { page: 1, per_page: 1, total: 2, total_pages: 2, has_next: true, has_prev: false },
    });

    const filtered = await jsonOf(get("/corpus/reviews/"));
    expect(filtered.data.map((row: { id: number }) => row.id)).toEqual([newer.id, older.id]);
  });

  it("filters by outcome and reviewer", async () => {
    const req = await insertRequirement({ externalId: "REQ-A" });
    const snapshot = await insertCorpusSnapshot("snap-1");
    const rejected = await insertSpecReview(req.id, snapshot.id, {
      outcome: "rejected",
      reviewer: "reviewer-b",
      createdAt: "2026-01-01 00:00:00",
    });
    await insertSpecReview(req.id, snapshot.id, {
      outcome: "approved",
      reviewer: "reviewer-a",
      createdAt: "2026-01-02 00:00:00",
    });

    const byOutcome = await jsonOf(get("/corpus/reviews/?outcome=rejected"));
    expect(byOutcome.data.map((row: { id: number }) => row.id)).toEqual([rejected.id]);

    const byReviewer = await jsonOf(get("/corpus/reviews/?reviewer=reviewer-b"));
    expect(byReviewer.data.map((row: { id: number }) => row.id)).toEqual([rejected.id]);
  });

  it("counts coverage and findings per review", async () => {
    const req = await insertRequirement({ externalId: "REQ-A" });
    const snapshot = await insertCorpusSnapshot("snap-1");
    const review = await insertSpecReview(req.id, snapshot.id);
    const { version } = await insertCorpusEntryVersion("ENTRY-1");
    await insertReviewCoverage(review.id, version.id);
    await insertReviewFinding(review.id, version.id);
    await insertReviewFinding(review.id, version.id, { checkId: "check-2" });

    const body = await jsonOf(get("/corpus/reviews/"));
    expect(body.data[0]).toMatchObject({ coverage_count: 1, findings_count: 2 });
  });
});

describe("GET /corpus/reviews/:id/", () => {
  it("returns detail with nested coverage and findings", async () => {
    const req = await insertRequirement({ externalId: "REQ-A" });
    const snapshot = await insertCorpusSnapshot("snap-1");
    const review = await insertSpecReview(req.id, snapshot.id);
    const { version } = await insertCorpusEntryVersion("ENTRY-1", { title: "Data Retention", kind: "policy" });
    await insertReviewCoverage(review.id, version.id, { cited: true, matchedBy: ["keyword", "regex"] });
    await insertReviewFinding(review.id, version.id, { detail: "No citation found" });

    const body = await jsonOf(get(`/corpus/reviews/${review.id}/`));
    expect(body).toEqual({
      data: {
        id: review.id,
        requirement_id: "REQ-A",
        spec_file: "specs/auth.md",
        reviewer: "reviewer-a",
        outcome: "approved",
        created_at: "2026-01-01T00:00:00+00:00",
        snapshot_hash: "snap-1",
        coverage: [
          {
            matched_by: ["keyword", "regex"],
            cited: true,
            entry_version_id: version.id,
            enforcement: "required",
            entry_title: "Data Retention",
            entry_kind: "policy",
          },
        ],
        findings: [
          {
            finding_type: "missing_citation",
            check_id: "check-1",
            detail: "No citation found",
            enforcement: "required",
          },
        ],
      },
    });
  });

  it("404s on a missing review", async () => {
    const res = await get("/corpus/reviews/999999/");
    expect(res.status).toBe(404);
    expect(await jsonOf(res)).toEqual({ error: { code: "not_found", message: "Review not found" } });
  });
});
