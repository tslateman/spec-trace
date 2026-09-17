import { asc, count, desc, eq, gt, lt, type SQL, sql } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { inAppValidationResults, inAppValidationRuns, inAppValidations, requirements } from "../../../db/schema";

export type ValidationRun = typeof inAppValidationRuns.$inferSelect;
export type ValidationStep = { passed?: boolean } & Record<string, unknown>;

export function stepsPassed(steps: ValidationStep[]): number {
  return steps.filter((step) => step.passed).length;
}

const successCount = count(sql`case when ${inAppValidationResults.status} = 'success' then 1 end`);
const failureCount = count(sql`case when ${inAppValidationResults.status} = 'failure' then 1 end`);

export function runSummaries(db: Database, where: SQL | undefined, limit: number, offset: number) {
  return db
    .select({
      id: inAppValidationRuns.id,
      source: inAppValidationRuns.source,
      importedAt: inAppValidationRuns.importedAt,
      total: count(inAppValidationResults.id),
      success: successCount,
      failure: failureCount,
    })
    .from(inAppValidationRuns)
    .leftJoin(inAppValidationResults, eq(inAppValidationResults.validationRunId, inAppValidationRuns.id))
    .where(where)
    .groupBy(inAppValidationRuns.id)
    .orderBy(desc(inAppValidationRuns.importedAt), desc(inAppValidationRuns.id))
    .limit(limit)
    .offset(offset);
}

export async function countRuns(db: Database, where: SQL | undefined): Promise<number> {
  const [row] = await db.select({ total: count() }).from(inAppValidationRuns).where(where);
  return row.total;
}

export function validationRunById(db: Database, runId: number) {
  return db.query.inAppValidationRuns.findFirst({ where: eq(inAppValidationRuns.id, runId) });
}

export async function runCounts(db: Database, runId: number) {
  const [row] = await db
    .select({ total: count(), success: successCount, failure: failureCount })
    .from(inAppValidationResults)
    .where(eq(inAppValidationResults.validationRunId, runId));
  return row;
}

export function runResults(db: Database, runId: number) {
  return db
    .select({
      id: inAppValidationResults.id,
      validationId: inAppValidations.id,
      validationName: inAppValidations.name,
      requirementId: requirements.externalId,
      vendor: inAppValidations.vendor,
      status: inAppValidationResults.status,
      message: inAppValidationResults.message,
      checkedAt: inAppValidationResults.checkedAt,
      steps: inAppValidationResults.steps,
      context: inAppValidationResults.context,
    })
    .from(inAppValidationResults)
    .innerJoin(inAppValidations, eq(inAppValidations.id, inAppValidationResults.validationId))
    .innerJoin(requirements, eq(requirements.id, inAppValidations.requirementId))
    .where(eq(inAppValidationResults.validationRunId, runId))
    .orderBy(desc(inAppValidationResults.checkedAt), asc(inAppValidationResults.id));
}

export function previousRun(db: Database, run: ValidationRun) {
  return db.query.inAppValidationRuns.findFirst({
    where: lt(inAppValidationRuns.importedAt, run.importedAt),
    orderBy: [desc(inAppValidationRuns.importedAt), desc(inAppValidationRuns.id)],
  });
}

export function nextRun(db: Database, run: ValidationRun) {
  return db.query.inAppValidationRuns.findFirst({
    where: gt(inAppValidationRuns.importedAt, run.importedAt),
    orderBy: [asc(inAppValidationRuns.importedAt), asc(inAppValidationRuns.id)],
  });
}

type ChangeType = "regressed" | "improved" | "new" | "removed" | "unchanged";

const changeOrder: Record<ChangeType, number> = { regressed: 0, improved: 1, new: 2, removed: 3, unchanged: 4 };

function classify(statusA: string | null, statusB: string | null): ChangeType {
  if (statusA === null) return "new";
  if (statusB === null) return "removed";
  if (statusA === statusB) return "unchanged";
  if (statusA === "failure" && statusB === "success") return "improved";
  if (statusA === "success" && statusB === "failure") return "regressed";
  return "unchanged";
}

function compareStrings(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

export async function buildRunComparison(db: Database, runA: ValidationRun, runB: ValidationRun) {
  const resultsA = new Map((await runResults(db, runA.id)).map((row) => [row.validationId, row]));
  const resultsB = new Map((await runResults(db, runB.id)).map((row) => [row.validationId, row]));
  const validationIds = new Set([...resultsA.keys(), ...resultsB.keys()]);
  const summary: Record<ChangeType, number> = { improved: 0, regressed: 0, unchanged: 0, new: 0, removed: 0 };

  const changes = [...validationIds].map((validationId) => {
    const resultA = resultsA.get(validationId);
    const resultB = resultsB.get(validationId);
    const validation = (resultB ?? resultA) as NonNullable<typeof resultA>;
    const statusA = resultA?.status ?? null;
    const statusB = resultB?.status ?? null;
    const changeType = classify(statusA, statusB);
    summary[changeType] += 1;
    return {
      validation_name: validation.validationName,
      vendor: validation.vendor || "Unassigned",
      requirement_id: validation.requirementId,
      status_a: statusA,
      status_b: statusB,
      change_type: changeType,
    };
  });

  changes.sort(
    (a, b) =>
      changeOrder[a.change_type] - changeOrder[b.change_type] ||
      compareStrings(a.vendor, b.vendor) ||
      compareStrings(a.validation_name, b.validation_name),
  );

  return { runA, runB, changes, summary };
}
