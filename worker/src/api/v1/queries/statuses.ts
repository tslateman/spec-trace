import { asc, desc, eq } from "drizzle-orm";
import type { Database } from "../../../db/client";
import {
  inAppValidationResults,
  inAppValidations,
  requirements,
  sloRequirements,
  slos,
  testResultRequirements,
  testResults,
} from "../../../db/schema";
import { runBatch, type Statement } from "./batching";
import { type Requirement, requirementsByPath } from "./requirements";

type VerificationStatus = "passing" | "failing" | "untested";
type SloStatus = "met" | "at_risk" | "breached" | "not_linked";

function groupBy<T>(rows: T[], key: (row: T) => number): Map<number, T[]> {
  const groups = new Map<number, T[]>();
  for (const row of rows) {
    const group = groups.get(key(row)) ?? [];
    group.push(row);
    groups.set(key(row), group);
  }
  return groups;
}

async function testStatusesByRequirement(db: Database) {
  const rows = await db
    .select({ requirementId: testResultRequirements.requirementId, status: testResults.status })
    .from(testResultRequirements)
    .innerJoin(testResults, eq(testResults.id, testResultRequirements.testresultId));
  return groupBy(rows, (row) => row.requirementId);
}

async function validationStatusesByRequirement(db: Database) {
  const validations = await db
    .select({ id: inAppValidations.id, requirementId: inAppValidations.requirementId })
    .from(inAppValidations);
  const results = await db
    .select({ validationId: inAppValidationResults.validationId, status: inAppValidationResults.status })
    .from(inAppValidationResults)
    .orderBy(desc(inAppValidationResults.checkedAt), asc(inAppValidationResults.id));
  const latest = new Map<number, string>();
  for (const result of results) {
    if (!latest.has(result.validationId)) latest.set(result.validationId, result.status);
  }
  const statuses = validations.map((validation) => ({
    requirementId: validation.requirementId,
    status: latest.get(validation.id) ?? "not_run",
  }));
  return groupBy(statuses, (row) => row.requirementId);
}

function computeTestStatus(statuses: string[]): VerificationStatus {
  if (statuses.length === 0) return "untested";
  if (statuses.includes("failed") || statuses.includes("error")) return "failing";
  if (statuses.every((status) => status === "passed")) return "passing";
  return "untested";
}

function computeInappStatus(statuses: string[]): VerificationStatus {
  if (statuses.length === 0) return "untested";
  if (statuses.includes("failure")) return "failing";
  if (statuses.every((status) => status === "success")) return "passing";
  return "untested";
}

function combineByMethod(method: string, test: VerificationStatus, inapp: VerificationStatus): VerificationStatus {
  if (method === "test") return test;
  if (method === "inapp") return inapp;
  if (method === "both") {
    if (test === "failing" || inapp === "failing") return "failing";
    if (test === "passing" && inapp === "passing") return "passing";
    return "untested";
  }
  if (test !== "untested") return test;
  return inapp;
}

function computeSloStatus(statuses: string[]): SloStatus {
  if (statuses.length === 0) return "not_linked";
  if (statuses.includes("breached")) return "breached";
  if (statuses.includes("at_risk")) return "at_risk";
  if (statuses.every((status) => status === "met")) return "met";
  return "not_linked";
}

async function updateAllStatuses<S extends string>(
  db: Database,
  field: "verificationStatus" | "sloStatus",
  keys: readonly S[],
  compute: (requirement: Requirement) => S,
): Promise<Record<S, number>> {
  const counts = Object.fromEntries(keys.map((key) => [key, 0])) as Record<S, number>;
  const updates: Statement[] = [];
  for (const requirement of await requirementsByPath(db)) {
    const status = compute(requirement);
    if (requirement[field] !== status) {
      updates.push(
        db
          .update(requirements)
          .set({ [field]: status })
          .where(eq(requirements.id, requirement.id)),
      );
    }
    counts[status] += 1;
  }
  await runBatch(db, updates);
  return counts;
}

export async function updateAllSloStatuses(db: Database) {
  const rows = await db
    .select({ requirementId: sloRequirements.requirementId, status: slos.status })
    .from(sloRequirements)
    .innerJoin(slos, eq(slos.id, sloRequirements.sloId));
  const byRequirement = groupBy(rows, (row) => row.requirementId);
  return updateAllStatuses(db, "sloStatus", ["met", "at_risk", "breached", "not_linked"] as const, (requirement) =>
    computeSloStatus((byRequirement.get(requirement.id) ?? []).map((row) => row.status)),
  );
}

export async function updateAllUnifiedStatuses(db: Database) {
  const tests = await testStatusesByRequirement(db);
  const validations = await validationStatusesByRequirement(db);
  return updateAllStatuses(db, "verificationStatus", ["passing", "failing", "untested"] as const, (requirement) => {
    if (requirement.sloStatus === "breached") return "failing";
    const test = computeTestStatus((tests.get(requirement.id) ?? []).map((row) => row.status));
    const inapp = computeInappStatus((validations.get(requirement.id) ?? []).map((row) => row.status));
    return combineByMethod(requirement.verificationMethod, test, inapp);
  });
}
