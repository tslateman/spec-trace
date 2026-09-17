import { and, asc, desc, eq, gt, gte, inArray, lte, or, type SQL, sql } from "drizzle-orm";
import { Hono } from "hono";
import { type Database, database } from "../../db/client";
import {
  conflictLogs,
  driftReports,
  impactReports,
  inAppValidationResults,
  inAppValidationRuns,
  inAppValidations,
  requirements,
  testRequirementLinks,
  testResultRequirements,
  testResults,
  testRuns,
} from "../../db/schema";
import type { Env } from "../../env";
import { failure, success } from "../envelope";
import { clampedOffset, pageMeta, pageRequest } from "../pagination";
import { chunked, runBatch, type Statement, selectChunked } from "./queries/batching";
import { detectAllStructuredConflicts, detectMutualExclusion, logConflicts } from "./queries/conflict-detector";
import { InvalidJsonBody, isJsonRequest, jsonBody } from "./queries/request";
import { AmbiguousProjectError, projectNames, requirementsByExternalId, resolveProject } from "./queries/requirements";
import { updateAllUnifiedStatuses } from "./queries/statuses";
import { latestTestRun, testRunCounts } from "./queries/test-runs";
import { isoformat, parseDatetime, roundHalfEven, storedFrom, storedNow } from "./queries/time";
import {
  buildRunComparison,
  countRuns,
  previousRun,
  runCounts,
  runResults,
  runSummaries,
  stepsPassed,
  type ValidationStep,
  validationRunById,
} from "./queries/validation-runs";
import { vendorCoverage } from "./queries/vendor-coverage";

export const results = new Hono<{ Bindings: Env }>();

const conflictConfidences = ["high", "medium", "low"];
const resolutionReasons = ["false_positive", "fixed", "accepted", "wont_fix"] as const;
type ResolutionReason = (typeof resolutionReasons)[number];

results.get("/conflicts", async (c) => {
  const request = pageRequest(c);
  const db = database(c.env.DB);
  const where = conflictFilters(db, c.req.query());
  const [{ total }] = await db.select({ total: sql<number>`count(*)` }).from(conflictLogs).where(where);
  const rows = await db
    .select({
      id: conflictLogs.id,
      pattern: conflictLogs.pattern,
      confidence: conflictLogs.confidence,
      resolved: conflictLogs.resolved,
      resolutionReason: conflictLogs.resolutionReason,
      timesDetected: conflictLogs.timesDetected,
      lastSeenAt: conflictLogs.lastSeenAt,
      createdAt: conflictLogs.createdAt,
      requirementAId: conflictLogs.requirementAId,
      requirementBId: conflictLogs.requirementBId,
    })
    .from(conflictLogs)
    .where(where)
    .orderBy(desc(conflictLogs.createdAt), desc(conflictLogs.id))
    .limit(request.perPage)
    .offset(clampedOffset(request, total));
  const externalIds = await externalIdsById(
    db,
    rows.flatMap((row) => [row.requirementAId, row.requirementBId]),
  );

  return success(
    c,
    rows.map((row) => conflictSummary(row, externalIds)),
    pageMeta(request, total),
  );
});

results.get("/conflicts/counts", async (c) => {
  return success(c, await conflictCounts(database(c.env.DB)));
});

function conflictSummary(
  row: {
    id: number;
    pattern: string;
    confidence: string;
    resolved: boolean;
    resolutionReason: string;
    timesDetected: number;
    lastSeenAt: string | null;
    createdAt: string;
    requirementAId: number;
    requirementBId: number;
  },
  externalIds: Map<number, string>,
) {
  return {
    id: row.id,
    requirement_a: externalIds.get(row.requirementAId),
    requirement_b: externalIds.get(row.requirementBId),
    pattern: row.pattern,
    confidence: row.confidence,
    resolved: row.resolved,
    resolution_reason: row.resolutionReason,
    times_detected: row.timesDetected,
    last_seen_at: isoformat(row.lastSeenAt ?? row.createdAt),
    created_at: isoformat(row.createdAt),
  };
}

async function conflictCounts(db: Database) {
  const [row] = await db
    .select({
      open: sql<number>`sum(case when ${conflictLogs.resolved} = 0 then 1 else 0 end)`,
      openHigh: sql<number>`sum(case when ${conflictLogs.resolved} = 0 and ${conflictLogs.confidence} = 'high' then 1 else 0 end)`,
      openMedium: sql<number>`sum(case when ${conflictLogs.resolved} = 0 and ${conflictLogs.confidence} = 'medium' then 1 else 0 end)`,
      openLow: sql<number>`sum(case when ${conflictLogs.resolved} = 0 and ${conflictLogs.confidence} = 'low' then 1 else 0 end)`,
      resolved: sql<number>`sum(case when ${conflictLogs.resolved} = 1 then 1 else 0 end)`,
      falsePositive: sql<number>`sum(case when ${conflictLogs.resolved} = 1 and ${conflictLogs.resolutionReason} = 'false_positive' then 1 else 0 end)`,
    })
    .from(conflictLogs);
  return {
    open: row.open ?? 0,
    open_high: row.openHigh ?? 0,
    open_medium: row.openMedium ?? 0,
    open_low: row.openLow ?? 0,
    resolved: row.resolved ?? 0,
    false_positive: row.falsePositive ?? 0,
  };
}

function conflictFilters(db: Database, query: Record<string, string>): SQL | undefined {
  const conditions: SQL[] = [];
  if (query.confidence && conflictConfidences.includes(query.confidence)) {
    conditions.push(eq(conflictLogs.confidence, query.confidence));
  }
  if (query.pattern) conditions.push(eq(conflictLogs.pattern, query.pattern));
  if (query.resolved) conditions.push(eq(conflictLogs.resolved, query.resolved.toLowerCase() === "true"));
  if (query.requirement_id) {
    const matching = db
      .select({ id: requirements.id })
      .from(requirements)
      .where(eq(requirements.externalId, query.requirement_id));
    conditions.push(
      or(inArray(conflictLogs.requirementAId, matching), inArray(conflictLogs.requirementBId, matching)) as SQL,
    );
  }
  return conditions.length ? and(...conditions) : undefined;
}

async function externalIdsById(db: Database, ids: number[]): Promise<Map<number, string>> {
  if (ids.length === 0) return new Map();
  const rows = await db
    .select({ id: requirements.id, externalId: requirements.externalId })
    .from(requirements)
    .where(inArray(requirements.id, ids));
  return new Map(rows.map((row) => [row.id, row.externalId]));
}

results.post("/conflicts/detect", async (c) => {
  let body: Record<string, unknown>;
  try {
    body = await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return failure(c, "Invalid JSON body", "invalid_json");
  }
  const db = database(c.env.DB);
  const options = {
    minRuns: typeof body.min_runs === "number" ? body.min_runs : 10,
    minOverlap: typeof body.min_overlap === "number" ? body.min_overlap : 5,
  };
  const conflicts = await detectMutualExclusion(db, options);
  if (body.include_structured !== false) conflicts.push(...(await detectAllStructuredConflicts(db)));
  const logged = await logConflicts(db, conflicts);
  return success(c, {
    conflicts_found: conflicts.length,
    logged: logged.createdCount,
    skipped_existing: logged.skippedCount,
  });
});

async function conflictById(db: Database, id: number) {
  return db.query.conflictLogs.findFirst({
    where: eq(conflictLogs.id, id),
    with: { requirementA: true, requirementB: true },
  });
}

results.get("/conflicts/:id{[0-9]+}", async (c) => {
  const conflict = await conflictById(database(c.env.DB), Number(c.req.param("id")));
  if (!conflict) return failure(c, "Conflict not found", "not_found", 404);
  return success(c, {
    id: conflict.id,
    requirement_a: conflict.requirementA.externalId,
    requirement_b: conflict.requirementB.externalId,
    requirement_a_title: conflict.requirementA.title,
    requirement_b_title: conflict.requirementB.title,
    pattern: conflict.pattern,
    confidence: conflict.confidence,
    details: conflict.details,
    resolved: conflict.resolved,
    resolved_at: conflict.resolvedAt ? isoformat(conflict.resolvedAt) : null,
    resolution_notes: conflict.resolutionNotes,
    resolution_reason: conflict.resolutionReason,
    times_detected: conflict.timesDetected,
    last_seen_at: isoformat(conflict.lastSeenAt ?? conflict.createdAt),
    created_at: isoformat(conflict.createdAt),
  });
});

function isResolutionReason(value: unknown): value is ResolutionReason {
  return typeof value === "string" && (resolutionReasons as readonly string[]).includes(value);
}

results.post("/conflicts/:id{[0-9]+}/resolve", async (c) => {
  let body: Record<string, unknown>;
  try {
    body = await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return failure(c, "Invalid JSON body", "invalid_json");
  }
  if (body.resolution_reason !== undefined && !isResolutionReason(body.resolution_reason)) {
    return failure(c, `resolution_reason must be one of: ${resolutionReasons.join(", ")}`, "invalid_reason");
  }
  const db = database(c.env.DB);
  const id = Number(c.req.param("id"));
  const conflict = await db.query.conflictLogs.findFirst({ where: eq(conflictLogs.id, id) });
  if (!conflict) return failure(c, "Conflict not found", "not_found", 404);
  if (conflict.resolved) return failure(c, "Conflict already resolved", "invalid_state");

  const now = storedNow();
  const resolutionReason = isResolutionReason(body.resolution_reason) ? body.resolution_reason : "unspecified";
  await db
    .update(conflictLogs)
    .set({
      resolved: true,
      resolvedAt: now,
      resolutionNotes: typeof body.resolution_notes === "string" ? body.resolution_notes : "",
      resolutionReason,
      updatedAt: now,
    })
    .where(eq(conflictLogs.id, id));
  return success(c, { conflict_id: id, resolved_at: isoformat(now), resolution_reason: resolutionReason });
});

type DriftPayload = { errors?: unknown[]; warnings?: unknown[] };
type ImpactPayload = { risk_level?: string };

results.get("/merge-safety", async (c) => {
  const db = database(c.env.DB);
  const project = c.req.query("project") ?? c.env.SPECTRACE_PROJECT;

  const impactReport = await db.query.impactReports.findFirst({
    where: eq(impactReports.project, project),
    orderBy: [desc(impactReports.createdAt), desc(impactReports.id)],
  });
  const driftReport = await db.query.driftReports.findFirst({
    where: eq(driftReports.project, project),
    orderBy: [desc(driftReports.createdAt), desc(driftReports.id)],
  });

  const unresolvedWhere = conflictFilters(db, { resolved: "false" }) as SQL;
  const [{ total: openCount }] = await db
    .select({ total: sql<number>`count(*)` })
    .from(conflictLogs)
    .where(unresolvedWhere);
  const [{ total: highConfidenceOpenCount }] = await db
    .select({ total: sql<number>`count(*)` })
    .from(conflictLogs)
    .where(and(unresolvedWhere, eq(conflictLogs.confidence, "high")));
  const conflictRows = await db
    .select({
      id: conflictLogs.id,
      pattern: conflictLogs.pattern,
      confidence: conflictLogs.confidence,
      resolved: conflictLogs.resolved,
      createdAt: conflictLogs.createdAt,
      requirementAId: conflictLogs.requirementAId,
      requirementBId: conflictLogs.requirementBId,
    })
    .from(conflictLogs)
    .where(unresolvedWhere)
    .orderBy(desc(conflictLogs.createdAt), desc(conflictLogs.id))
    .limit(50);
  const externalIds = await externalIdsById(
    db,
    conflictRows.flatMap((row) => [row.requirementAId, row.requirementBId]),
  );
  const conflictItems = conflictRows.map((row) => ({
    id: row.id,
    requirement_a: externalIds.get(row.requirementAId),
    requirement_b: externalIds.get(row.requirementBId),
    pattern: row.pattern,
    confidence: row.confidence,
    resolved: row.resolved,
    created_at: isoformat(row.createdAt),
  }));

  const driftPayload = driftReport?.payload as DriftPayload | undefined;
  const impactPayload = impactReport?.payload as ImpactPayload | undefined;
  const driftHasErrors = (driftPayload?.errors?.length ?? 0) > 0;
  const driftHasWarnings = (driftPayload?.warnings?.length ?? 0) > 0;
  const impactRiskHigh = impactPayload?.risk_level === "high" || impactPayload?.risk_level === "critical";

  const verdict =
    highConfidenceOpenCount > 0 || driftHasErrors
      ? "blocked"
      : openCount > 0 || driftHasWarnings || impactRiskHigh
        ? "needs_review"
        : "safe";

  return success(c, {
    generated_at: isoformat(storedNow()),
    verdict,
    impact: impactReport?.payload ?? null,
    drift: driftReport?.payload ?? null,
    conflicts: { open_count: openCount, items: conflictItems },
  });
});

interface ValidationItem {
  requirement_id: string;
  name: string;
  status: string;
  message?: string;
  endpoint?: string;
  checked_at?: string | null;
  steps?: {
    name: string;
    passed: boolean;
    details?: string | null;
    error_message?: string | null;
    duration_ms?: number | null;
  }[];
  context?: Record<string, unknown> | null;
}

function rejected(message: string) {
  return { success: false, error: message };
}

function isValidationItem(item: unknown): item is ValidationItem {
  const candidate = item as Partial<ValidationItem>;
  return (
    typeof candidate?.requirement_id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.status === "string"
  );
}

const resultStatuses: Record<string, string> = { success: "success", failure: "failure", degraded: "failure" };

results.post("/enforcement", async (c) => {
  if (!isJsonRequest(c)) return c.json(rejected("No data provided"), 400);
  let body: Record<string, unknown>;
  try {
    body = await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return c.json(rejected(`Invalid JSON: ${error.message}`), 400);
  }
  if (Object.keys(body).length === 0) return c.json(rejected("No data provided"), 400);
  if (typeof body.source !== "string")
    return c.json(rejected("Invalid JSON: Object missing required field `source`"), 400);
  if (!Array.isArray(body.validations) || !body.validations.every(isValidationItem)) {
    return c.json(rejected("Invalid JSON: Expected `validations` to be a list of validation items"), 400);
  }
  if (body.validations.length === 0) return c.json(rejected("No validations in request"), 400);

  const db = database(c.env.DB);
  const items = body.validations;
  const found = await requirementsByExternalId(db, [...new Set(items.map((item) => item.requirement_id))]);
  const linked = items.flatMap((item) => {
    const requirement = found.get(item.requirement_id);
    return requirement ? [{ item, requirementId: requirement.id }] : [];
  });

  const [run] = await db
    .insert(inAppValidationRuns)
    .values({ source: body.source, importedAt: storedNow() })
    .returning({ id: inAppValidationRuns.id });

  const { validationIds, createdValidations } = await syncValidations(db, linked);

  const tally = { successful: 0, failed: 0 };
  const resultRows = linked.map(({ item, requirementId }) => {
    const status = resultStatuses[item.status.toLowerCase()] ?? "unknown";
    if (status === "success") tally.successful += 1;
    if (status === "failure") tally.failed += 1;
    return {
      validationRunId: run.id,
      validationId: validationIds.get(requirementId) as number,
      status,
      message: item.message ?? "",
      checkedAt: storedFrom((item.checked_at && parseDatetime(item.checked_at)) || new Date()),
      steps: (item.steps ?? []).map((step) => ({
        name: step.name,
        passed: step.passed,
        details: step.details ?? null,
        error_message: step.error_message ?? null,
        duration_ms: step.duration_ms ?? null,
      })),
      context: item.context ?? {},
    };
  });
  await runBatch(
    db,
    chunked(resultRows, 10).map((chunk) => db.insert(inAppValidationResults).values(chunk)),
  );

  if (body.update_verification_status === true) await updateAllUnifiedStatuses(db);

  return c.json({
    success: true,
    imported: linked.length,
    skipped: items.length - linked.length,
    created_validations: createdValidations,
    successful: tally.successful,
    failed: tally.failed,
  });
});

interface LinkedValidation {
  item: ValidationItem;
  requirementId: number;
}

async function syncValidations(
  db: Database,
  linked: LinkedValidation[],
): Promise<{ validationIds: Map<number, number>; createdValidations: number }> {
  const requirementIds = [...new Set(linked.map((entry) => entry.requirementId))];
  const rows = await selectChunked(requirementIds, (chunk) =>
    db
      .select()
      .from(inAppValidations)
      .where(inArray(inAppValidations.requirementId, chunk))
      .orderBy(asc(inAppValidations.name), asc(inAppValidations.id)),
  );

  const existing = new Map<number, (typeof rows)[number]>();
  for (const row of rows) if (!existing.has(row.requirementId)) existing.set(row.requirementId, row);

  const validationIds = new Map<number, number>();
  const updates: Statement[] = [];
  const creations: LinkedValidation[] = [];
  for (const requirementId of requirementIds) {
    const entries = linked.filter((entry) => entry.requirementId === requirementId);
    const fields = mergedFields(entries);
    const row = existing.get(requirementId);
    if (!row) {
      creations.push(entries[0]);
      continue;
    }
    validationIds.set(requirementId, row.id);
    updates.push(db.update(inAppValidations).set(fields).where(eq(inAppValidations.id, row.id)));
  }

  for (const entry of creations) {
    const fields = mergedFields(linked.filter((other) => other.requirementId === entry.requirementId));
    const [created] = await db
      .insert(inAppValidations)
      .values({
        requirementId: entry.requirementId,
        name: fields.name ?? `Validation for ${entry.item.requirement_id}`,
        endpoint: entry.item.endpoint ?? "",
        vendor: fields.vendor ?? "",
        featureFlags: fields.featureFlags ?? {},
      })
      .returning({ id: inAppValidations.id });
    validationIds.set(entry.requirementId, created.id);
  }

  await runBatch(db, updates);
  return { validationIds, createdValidations: creations.length };
}

function mergedFields(entries: LinkedValidation[]) {
  const fields: { name?: string; vendor?: string; featureFlags?: Record<string, unknown> } = {};
  for (const { item } of entries) {
    const context = item.context ?? {};
    const vendor = typeof context.vendor === "string" ? context.vendor : "";
    const featureFlags = (context.feature_flags as Record<string, unknown> | undefined) || {};
    if (item.name) fields.name = item.name;
    if (vendor) fields.vendor = vendor;
    if (Object.keys(featureFlags).length) fields.featureFlags = featureFlags;
  }
  return fields;
}

results.get("/enforcement-runs", async (c) => {
  const request = pageRequest(c);
  const db = database(c.env.DB);
  const where = runFilters(db, c.req.query());
  const total = await countRuns(db, where);
  const runs = await runSummaries(db, where, request.perPage, clampedOffset(request, total));

  return success(
    c,
    runs.map((run) => ({
      id: run.id,
      source: run.source,
      imported_at: isoformat(run.importedAt),
      total_validations: run.total,
      successful: run.success,
      failed: run.failure,
    })),
    pageMeta(request, total),
  );
});

function runFilters(db: Database, query: Record<string, string>): SQL | undefined {
  const conditions: SQL[] = [];
  const runsWithResults = (condition: SQL) =>
    inArray(
      inAppValidationRuns.id,
      db
        .select({ id: inAppValidationResults.validationRunId })
        .from(inAppValidationResults)
        .innerJoin(inAppValidations, eq(inAppValidations.id, inAppValidationResults.validationId))
        .innerJoin(requirements, eq(requirements.id, inAppValidations.requirementId))
        .where(condition),
    );
  if (query.requirement_id) conditions.push(runsWithResults(eq(requirements.externalId, query.requirement_id)));
  if (query.vendor) conditions.push(runsWithResults(eq(inAppValidations.vendor, query.vendor)));
  if (query.status) conditions.push(runsWithResults(eq(inAppValidationResults.status, query.status)));
  const start = query.start_date && parseDatetime(query.start_date);
  if (start) conditions.push(gte(inAppValidationRuns.importedAt, storedFrom(start)));
  const end = query.end_date && parseDatetime(query.end_date);
  if (end) conditions.push(lte(inAppValidationRuns.importedAt, storedFrom(end)));
  return conditions.length ? and(...conditions) : undefined;
}

function escapeLike(value: string): string {
  return value.replace(/[\\%_]/g, (char) => `\\${char}`);
}

results.get("/enforcement-runs/latest", async (c) => {
  const db = database(c.env.DB);
  const source = c.req.query("source");
  const where = source ? sql`${inAppValidationRuns.source} like ${`%${escapeLike(source)}%`} escape '\\'` : undefined;
  const [run] = await runSummaries(db, where, 1, 0);
  if (!run) return failure(c, "No enforcement runs found", "not_found", 404);
  return success(c, {
    run_id: run.id,
    source: run.source,
    imported_at: isoformat(run.importedAt),
    pass_rate: run.total > 0 ? roundHalfEven((run.success / run.total) * 100, 1) : 0,
    total: run.total,
    passed: run.success,
    failed: run.failure,
  });
});

results.get("/enforcement-runs/:id{[0-9]+}", async (c) => {
  const db = database(c.env.DB);
  const run = await validationRunById(db, Number(c.req.param("id")));
  if (!run) return c.json({ error: "Verification run not found" }, 404);
  const counts = await runCounts(db, run.id);
  const rows = await runResults(db, run.id);
  return c.json({
    id: run.id,
    source: run.source,
    imported_at: isoformat(run.importedAt),
    total_validations: counts.total,
    successful: counts.success,
    failed: counts.failure,
    results: rows.map((row) => ({
      id: row.id,
      validation_id: row.validationId,
      validation_name: row.validationName,
      requirement_id: row.requirementId,
      vendor: row.vendor,
      status: row.status,
      message: row.message,
      checked_at: isoformat(row.checkedAt),
      step_count: (row.steps as ValidationStep[]).length,
      steps_passed: stepsPassed(row.steps as ValidationStep[]),
    })),
  });
});

results.get("/enforcement-runs/:id{[0-9]+}/diff", async (c) => {
  const db = database(c.env.DB);
  const run = await validationRunById(db, Number(c.req.param("id")));
  if (!run) return failure(c, "Run not found", "not_found", 404);
  const previous = await previousRun(db, run);
  if (!previous) return failure(c, "No previous run to compare against", "no_predecessor", 409);
  const comparison = await buildRunComparison(db, previous, run);
  return success(c, {
    compared_to: {
      id: comparison.runA.id,
      source: comparison.runA.source,
      imported_at: isoformat(comparison.runA.importedAt),
    },
    summary: comparison.summary,
    changes: comparison.changes.map((change) => ({
      requirement_id: change.requirement_id,
      validation_name: change.validation_name,
      vendor: change.vendor,
      status_a: change.status_a,
      status_b: change.status_b,
      change_type: change.change_type,
    })),
  });
});

results.get("/enforcement-runs/:id{[0-9]+}/steps", async (c) => {
  const db = database(c.env.DB);
  const run = await validationRunById(db, Number(c.req.param("id")));
  if (!run) return c.json({ error: "Verification run not found" }, 404);
  const resultId = c.req.query("result_id");
  const rows = (await runResults(db, run.id)).filter((row) => !resultId || String(row.id) === resultId);
  return c.json({
    run_id: run.id,
    results: rows.map((row) => ({
      result_id: row.id,
      validation_name: row.validationName,
      requirement_id: row.requirementId,
      status: row.status,
      steps: row.steps,
      context: row.context,
    })),
  });
});

results.get("/vendor-coverage", async (c) => {
  const db = database(c.env.DB);
  let project: string;
  try {
    project = resolveProject(c.req.query("project"), await projectNames(db), c.env.SPECTRACE_PROJECT);
  } catch (error) {
    if (!(error instanceof AmbiguousProjectError)) throw error;
    return failure(c, `${error.message} Pass ?project=`, "ambiguous_project", 400, { projects: error.projects });
  }

  const report = await vendorCoverage(db, project);
  return success(c, { project, ...report });
});

interface TestResultItem {
  test_nodeid: string;
  status: string;
  classname?: string;
  name?: string;
  time?: number;
  message?: string;
  requirement_ids?: string[];
}

function isTestResultItem(item: unknown): item is TestResultItem {
  const candidate = item as Partial<TestResultItem>;
  return typeof candidate?.test_nodeid === "string" && typeof candidate.status === "string";
}

results.post("/test-runs", async (c) => {
  if (!isJsonRequest(c)) return c.json(rejected("No data provided"), 400);
  let body: Record<string, unknown>;
  try {
    body = await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return c.json(rejected(`Invalid JSON: ${error.message}`), 400);
  }
  if (typeof body.source_file !== "string") {
    return c.json(rejected("Invalid JSON: Object missing required field `source_file`"), 400);
  }
  if (!Array.isArray(body.results) || !body.results.every(isTestResultItem)) {
    return c.json(rejected("Invalid JSON: Expected `results` to be a list of test results"), 400);
  }

  const db = database(c.env.DB);
  const items = body.results;
  const externalIds = [...new Set(items.flatMap((item) => item.requirement_ids ?? []))];
  const found = await requirementsByExternalId(db, externalIds);

  const importedAt = storedNow();
  const [run] = await db
    .insert(testRuns)
    .values({
      importedAt,
      sourceFile: body.source_file,
      ciJobUrl: text(body.ci_job_url),
      finishedAt: null,
      gitBranch: text(body.git_branch),
      gitSha: text(body.git_sha),
      startedAt: null,
      repository: text(body.repository),
      workflowName: text(body.workflow_name),
      workflowRunId: typeof body.workflow_run_id === "number" ? body.workflow_run_id : null,
    })
    .returning({ id: testRuns.id });

  const inserted = await Promise.all(
    chunked(
      items.map((item) => ({
        testNodeid: item.test_nodeid,
        classname: item.classname ?? "",
        name: item.name ?? item.test_nodeid,
        time: item.time ?? 0,
        status: item.status,
        message: item.message ?? "",
        testRunId: run.id,
      })),
      10,
    ).map((chunk) => db.insert(testResults).values(chunk).returning({ id: testResults.id })),
  );
  const resultIds = inserted.flat().map((row) => row.id);

  const memberships = items.flatMap((item, index) =>
    [...new Set(item.requirement_ids ?? [])].flatMap((externalId) => {
      const requirement = found.get(externalId);
      return requirement ? [{ testresultId: resultIds[index], requirementId: requirement.id }] : [];
    }),
  );
  await runBatch(
    db,
    chunked(memberships, 40).map((chunk) => db.insert(testResultRequirements).values(chunk)),
  );

  await refreshLinkStatuses(db, items, importedAt);

  if (body.update_verification_status === true) await updateAllUnifiedStatuses(db);

  const counts = await testRunCounts(db, run.id);
  return c.json({
    success: true,
    run_id: run.id,
    imported: items.length,
    linked: memberships.length,
    passed: counts.passed,
    failed: counts.failed,
    errors: counts.errors,
    skipped: counts.skipped,
  });
});

async function refreshLinkStatuses(db: Database, items: TestResultItem[], importedAt: string): Promise<void> {
  const statusByNodeid = new Map(items.map((item) => [item.test_nodeid, item.status]));
  const links = await selectChunked([...statusByNodeid.keys()], (chunk) =>
    db
      .select({
        id: testRequirementLinks.id,
        testNodeid: testRequirementLinks.testNodeid,
        lastStatus: testRequirementLinks.lastStatus,
      })
      .from(testRequirementLinks)
      .where(inArray(testRequirementLinks.testNodeid, chunk)),
  );
  const updates = links.flatMap((link) => {
    const status = statusByNodeid.get(link.testNodeid);
    if (status === undefined) return [];
    const regressed = link.lastStatus === "passed" && (status === "failed" || status === "error");
    return [
      db
        .update(testRequirementLinks)
        .set({
          lastStatus: status,
          lastRunAt: importedAt,
          updatedAt: importedAt,
          ...(regressed ? { needsReview: true, reviewReason: `status changed: ${link.lastStatus} -> ${status}` } : {}),
        })
        .where(eq(testRequirementLinks.id, link.id)),
    ];
  });
  await runBatch(db, updates);
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

results.get("/test-runs/latest", async (c) => {
  const db = database(c.env.DB);
  const since = c.req.query("since");
  const repo = c.req.query("repo");
  const conditions: SQL[] = [];
  if (repo) conditions.push(eq(testRuns.repository, repo));
  if (since) {
    const sinceDate = parseDatetime(since);
    if (!sinceDate) return c.json({ error: "Invalid since parameter" }, 400);
    conditions.push(gt(testRuns.importedAt, storedFrom(sinceDate)));
  }
  const latest = conditions.length
    ? await db.query.testRuns.findFirst({
        where: and(...conditions),
        orderBy: [desc(testRuns.importedAt), desc(testRuns.id)],
      })
    : await latestTestRun(db);
  if (!latest) return since ? c.body(null, 204) : c.json({ test_run: null });

  const counts = await testRunCounts(db, latest.id);
  return c.json({
    test_run: {
      id: latest.id,
      imported_at: isoformat(latest.importedAt),
      source_file: latest.sourceFile,
      git_sha: latest.gitSha,
      git_branch: latest.gitBranch,
      workflow_name: latest.workflowName,
      workflow_run_id: latest.workflowRunId,
      repository: latest.repository,
      total_tests: counts.total,
      passed: counts.passed,
      failed: counts.failed,
      errors: counts.errors,
      skipped: counts.skipped,
    },
  });
});
