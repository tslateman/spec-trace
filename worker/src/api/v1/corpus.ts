import { and, desc, eq, inArray, type SQL, sql } from "drizzle-orm";
import { Hono } from "hono";
import { type Database, database } from "../../db/client";
import {
  corpusEntries,
  corpusEntryVersions,
  corpusSnapshots,
  requirements,
  reviewCoverage,
  reviewFindings,
  specReviews,
} from "../../db/schema";
import type { Env } from "../../env";
import { failure, success } from "../envelope";
import { clampedOffset, pageMeta, pageRequest } from "../pagination";
import { isoformat } from "./queries/time";

export const corpus = new Hono<{ Bindings: Env }>();

corpus.get("/reviews", async (c) => {
  const request = pageRequest(c);
  const db = database(c.env.DB);
  const where = reviewFilters(c.req.query());
  const [{ total }] = await db.select({ total: sql<number>`count(*)` }).from(specReviews).where(where);
  const rows = await db
    .select({
      id: specReviews.id,
      specFile: specReviews.specFile,
      reviewer: specReviews.reviewer,
      outcome: specReviews.outcome,
      createdAt: specReviews.createdAt,
      requirementExternalId: requirements.externalId,
      snapshotHash: corpusSnapshots.snapshotHash,
    })
    .from(specReviews)
    .innerJoin(requirements, eq(requirements.id, specReviews.requirementId))
    .innerJoin(corpusSnapshots, eq(corpusSnapshots.id, specReviews.snapshotId))
    .where(where)
    .orderBy(desc(specReviews.createdAt), desc(specReviews.id))
    .limit(request.perPage)
    .offset(clampedOffset(request, total));

  const counts = await reviewCounts(
    db,
    rows.map((row) => row.id),
  );

  return success(
    c,
    rows.map((row) => ({
      id: row.id,
      requirement_id: row.requirementExternalId,
      spec_file: row.specFile,
      reviewer: row.reviewer,
      outcome: row.outcome,
      created_at: isoformat(row.createdAt),
      snapshot_hash: row.snapshotHash,
      coverage_count: counts.coverage.get(row.id) ?? 0,
      findings_count: counts.findings.get(row.id) ?? 0,
    })),
    pageMeta(request, total),
  );
});

function reviewFilters(query: Record<string, string>): SQL | undefined {
  const conditions: SQL[] = [];
  if (query.outcome) conditions.push(eq(specReviews.outcome, query.outcome));
  if (query.reviewer) conditions.push(eq(specReviews.reviewer, query.reviewer));
  return conditions.length ? and(...conditions) : undefined;
}

async function reviewCounts(
  db: Database,
  reviewIds: number[],
): Promise<{ coverage: Map<number, number>; findings: Map<number, number> }> {
  if (reviewIds.length === 0) return { coverage: new Map(), findings: new Map() };
  const [coverageRows, findingsRows] = await Promise.all([
    db
      .select({ reviewId: reviewCoverage.reviewId, count: sql<number>`count(*)` })
      .from(reviewCoverage)
      .where(inArray(reviewCoverage.reviewId, reviewIds))
      .groupBy(reviewCoverage.reviewId),
    db
      .select({ reviewId: reviewFindings.reviewId, count: sql<number>`count(*)` })
      .from(reviewFindings)
      .where(inArray(reviewFindings.reviewId, reviewIds))
      .groupBy(reviewFindings.reviewId),
  ]);
  return {
    coverage: new Map(coverageRows.map((row) => [row.reviewId, row.count])),
    findings: new Map(findingsRows.map((row) => [row.reviewId, row.count])),
  };
}

corpus.get("/reviews/:id{[0-9]+}", async (c) => {
  const db = database(c.env.DB);
  const id = Number(c.req.param("id"));
  const review = await db.query.specReviews.findFirst({
    where: eq(specReviews.id, id),
    with: { requirement: true, snapshot: true },
  });
  if (!review) return failure(c, "Review not found", "not_found", 404);

  const [coverageRows, findingsRows] = await Promise.all([
    db
      .select({
        matchedBy: reviewCoverage.matchedBy,
        cited: reviewCoverage.cited,
        entryVersionId: reviewCoverage.entryVersionId,
        enforcement: reviewCoverage.enforcement,
        entryTitle: corpusEntries.title,
        entryKind: corpusEntries.kind,
      })
      .from(reviewCoverage)
      .innerJoin(corpusEntryVersions, eq(corpusEntryVersions.id, reviewCoverage.entryVersionId))
      .innerJoin(corpusEntries, eq(corpusEntries.id, corpusEntryVersions.entryId))
      .where(eq(reviewCoverage.reviewId, id)),
    db
      .select({
        findingType: reviewFindings.findingType,
        checkId: reviewFindings.checkId,
        detail: reviewFindings.detail,
        enforcement: reviewFindings.enforcement,
      })
      .from(reviewFindings)
      .where(eq(reviewFindings.reviewId, id)),
  ]);

  return success(c, {
    id: review.id,
    requirement_id: review.requirement.externalId,
    spec_file: review.specFile,
    reviewer: review.reviewer,
    outcome: review.outcome,
    created_at: isoformat(review.createdAt),
    snapshot_hash: review.snapshot.snapshotHash,
    coverage: coverageRows.map((row) => ({
      matched_by: row.matchedBy,
      cited: row.cited,
      entry_version_id: row.entryVersionId,
      enforcement: row.enforcement,
      entry_title: row.entryTitle,
      entry_kind: row.entryKind,
    })),
    findings: findingsRows.map((row) => ({
      finding_type: row.findingType,
      check_id: row.checkId,
      detail: row.detail,
      enforcement: row.enforcement,
    })),
  });
});
