import { env, SELF } from "cloudflare:test";
import { database } from "../src/db/client";
import {
  conflictLogs,
  corpusEntries,
  corpusEntryVersions,
  corpusSnapshots,
  coverageSnapshots,
  driftReports,
  impactReports,
  inAppValidationResults,
  inAppValidationRuns,
  inAppValidations,
  requirementDependsOn,
  requirements,
  reviewCoverage,
  reviewFindings,
  sloRequirements,
  slos,
  specReviews,
  testRequirementLinks,
  testResultRequirements,
  testResults,
  testRuns,
} from "../src/db/schema";

export const db = database(env.DB);

const tablesInDeletionOrder = [
  inAppValidationResults,
  inAppValidationRuns,
  inAppValidations,
  testRequirementLinks,
  testResultRequirements,
  testResults,
  testRuns,
  conflictLogs,
  sloRequirements,
  slos,
  reviewCoverage,
  reviewFindings,
  specReviews,
  corpusEntryVersions,
  corpusEntries,
  corpusSnapshots,
  requirementDependsOn,
  coverageSnapshots,
  driftReports,
  impactReports,
  requirements,
];

export async function resetDatabase() {
  for (const table of tablesInDeletionOrder) await db.delete(table);
}

export const headers = { "X-API-Key": "test-key", "Content-Type": "application/json" };

export function get(path: string) {
  return SELF.fetch(`http://spectrace/api/v1${path}`, { headers });
}

export async function jsonOf(response: Response | Promise<Response>): Promise<any> {
  return (await response).json();
}

export function post(path: string, body?: unknown) {
  return SELF.fetch(`http://spectrace/api/v1${path}`, {
    method: "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

let pathCounter = 0;

export async function insertRequirement(overrides: Partial<typeof requirements.$inferInsert> = {}) {
  pathCounter += 1;
  const [row] = await db
    .insert(requirements)
    .values({
      path: String(pathCounter).padStart(4, "0"),
      depth: 1,
      numchild: 0,
      externalId: `REQ-${pathCounter}`,
      title: `Requirement ${pathCounter}`,
      description: "",
      tags: [],
      priority: "medium",
      status: "active",
      sourceFile: "specs/auth.md",
      createdAt: "2026-01-01 00:00:00",
      updatedAt: "2026-01-01 00:00:00",
      verificationStatus: "untested",
      sloStatus: "not_linked",
      verificationMethod: "unspecified",
      component: "",
      condition: "",
      response: "",
      scope: "",
      structureCompleteness: 0,
      timing: "",
      riskLevel: "low",
      project: "spectrace",
      ...overrides,
    })
    .returning();
  return row;
}

export async function insertTestRun(importedAt: string, nodeids: string[], status = "passed") {
  const [run] = await db
    .insert(testRuns)
    .values({
      importedAt,
      sourceFile: "junit.xml",
      ciJobUrl: "",
      gitBranch: "main",
      gitSha: "abc123",
      repository: "tslater/spec-trace",
      workflowName: "ci",
      workflowRunId: null,
    })
    .returning();
  for (const nodeid of nodeids) {
    await db.insert(testResults).values({
      testNodeid: nodeid,
      classname: "tests",
      name: nodeid,
      time: 0.1,
      status,
      message: "",
      testRunId: run.id,
    });
  }
  return run;
}

export async function insertLink(
  requirementId: number,
  testNodeid: string,
  lastStatus = "passed",
  lastRunAt: string | null = null,
) {
  const [row] = await db
    .insert(testRequirementLinks)
    .values({
      testNodeid,
      lastStatus,
      lastRunAt,
      needsReview: false,
      reviewReason: "",
      createdAt: "2026-01-01 00:00:00",
      updatedAt: "2026-01-01 00:00:00",
      requirementId,
    })
    .returning();
  return row;
}

export async function insertDependency(fromRequirementId: number, toRequirementId: number) {
  await db.insert(requirementDependsOn).values({ fromRequirementId, toRequirementId });
}

export async function insertValidationRun(importedAt: string, source = "product") {
  const [row] = await db.insert(inAppValidationRuns).values({ importedAt, source }).returning();
  return row;
}

export async function insertValidation(requirementId: number, name = "Verify login", vendor = "") {
  const [row] = await db
    .insert(inAppValidations)
    .values({ requirementId, name, endpoint: "", vendor, featureFlags: {} })
    .returning();
  return row;
}

export async function insertValidationResult(
  validationRunId: number,
  validationId: number,
  status: string,
  checkedAt: string,
  steps: unknown[] = [],
) {
  const [row] = await db
    .insert(inAppValidationResults)
    .values({ validationRunId, validationId, status, message: `${status} message`, checkedAt, steps, context: {} })
    .returning();
  return row;
}

export async function insertConflict(requirementAId: number, requirementBId: number, createdAt: string) {
  const [row] = await db
    .insert(conflictLogs)
    .values({
      requirementAId,
      requirementBId,
      pattern: "timing_conflict",
      confidence: "high",
      details: { ratio: 5 },
      resolved: false,
      resolvedAt: null,
      resolutionNotes: "",
      createdAt,
      updatedAt: createdAt,
    })
    .returning();
  return row;
}

export async function insertSlo(name: string, requirementIds: number[]) {
  const [row] = await db
    .insert(slos)
    .values({
      name,
      displayName: name,
      description: "",
      service: "api",
      target: 0.999,
      timeWindow: "30d",
      budgetingMethod: "occurrences",
      status: "not_linked",
      currentValue: null,
      errorBudgetRemaining: null,
      lastUpdated: null,
      sourceFile: "",
      createdAt: "2026-01-01 00:00:00",
      updatedAt: "2026-01-01 00:00:00",
    })
    .returning();
  for (const requirementId of requirementIds) {
    await db.insert(sloRequirements).values({ sloId: row.id, requirementId });
  }
  return row;
}

export async function insertCorpusSnapshot(snapshotHash: string) {
  const [row] = await db
    .insert(corpusSnapshots)
    .values({ snapshotHash, entryVersionHashes: [], createdAt: "2026-01-01 00:00:00" })
    .returning();
  return row;
}

export async function insertCorpusEntryVersion(externalId: string, overrides: { title?: string; kind?: string } = {}) {
  const [entry] = await db
    .insert(corpusEntries)
    .values({
      externalId,
      kind: overrides.kind ?? "policy",
      title: overrides.title ?? `Entry ${externalId}`,
      owner: "platform",
      status: "active",
      sourceFile: "corpus/policy.md",
      createdAt: "2026-01-01 00:00:00",
      updatedAt: "2026-01-01 00:00:00",
    })
    .returning();
  const [version] = await db
    .insert(corpusEntryVersions)
    .values({
      version: 1,
      body: "",
      contentHash: `hash-${externalId}`,
      appliesTo: [],
      checks: [],
      effectiveDate: null,
      sourceFile: "corpus/policy.md",
      createdAt: "2026-01-01 00:00:00",
      entryId: entry.id,
      enforcement: "required",
    })
    .returning();
  return { entry, version };
}

export async function insertSpecReview(
  requirementId: number,
  snapshotId: number,
  overrides: Partial<typeof specReviews.$inferInsert> = {},
) {
  const [row] = await db
    .insert(specReviews)
    .values({
      specFile: "specs/auth.md",
      reviewer: "reviewer-a",
      outcome: "approved",
      createdAt: "2026-01-01 00:00:00",
      requirementId,
      snapshotId,
      ...overrides,
    })
    .returning();
  return row;
}

export async function insertReviewCoverage(
  reviewId: number,
  entryVersionId: number,
  overrides: Partial<typeof reviewCoverage.$inferInsert> = {},
) {
  const [row] = await db
    .insert(reviewCoverage)
    .values({
      matchedBy: ["keyword"],
      cited: true,
      entryVersionId,
      reviewId,
      enforcement: "required",
      ...overrides,
    })
    .returning();
  return row;
}

export async function insertReviewFinding(
  reviewId: number,
  entryVersionId: number,
  overrides: Partial<typeof reviewFindings.$inferInsert> = {},
) {
  const [row] = await db
    .insert(reviewFindings)
    .values({
      findingType: "missing_citation",
      checkId: "check-1",
      detail: "Missing citation for policy",
      createdAt: "2026-01-01 00:00:00",
      entryVersionId,
      reviewId,
      enforcement: "required",
      ...overrides,
    })
    .returning();
  return row;
}
