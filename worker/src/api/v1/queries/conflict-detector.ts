import { and, desc, eq, inArray, ne, or } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { conflictLogs, requirements, testRequirementLinks, testRuns } from "../../../db/schema";
import { type Requirement, requirementsByPath } from "./requirements";
import { storedNow } from "./time";

export type Confidence = "high" | "medium" | "low";

export interface ConflictResult {
  requirementAId: number;
  requirementBId: number;
  requirementAExternalId: string;
  requirementBExternalId: string;
  pattern: string;
  confidence: Confidence;
  runsAnalyzed: number;
  details: Record<string, unknown>;
}

export interface DetectorOptions {
  minRuns: number;
  minOverlap: number;
}

function* pairs<T>(items: T[]): Generator<[T, T]> {
  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) yield [items[i], items[j]];
  }
}

function groupByComponent(rows: Requirement[]): Map<string, Requirement[]> {
  const groups = new Map<string, Requirement[]>();
  for (const row of rows) {
    const component = row.component.toLowerCase().trim();
    groups.set(component, [...(groups.get(component) ?? []), row]);
  }
  return groups;
}

function conflictBetween(
  a: Requirement,
  b: Requirement,
  pattern: string,
  confidence: Confidence,
  details: Record<string, unknown>,
): ConflictResult {
  return {
    requirementAId: a.id,
    requirementBId: b.id,
    requirementAExternalId: a.externalId,
    requirementBExternalId: b.externalId,
    pattern,
    confidence,
    runsAnalyzed: 0,
    details,
  };
}

function aggregateRunStatus(linkStatuses: string[]): string {
  if (linkStatuses.some((status) => status === "failed" || status === "error")) return "failed";
  if (linkStatuses.every((status) => status === "skipped")) return "skipped";
  if (linkStatuses.some((status) => status === "passed")) return "passed";
  return "unknown";
}

async function runRequirementStatuses(db: Database, importedAt: string): Promise<Map<number, string>> {
  const links = await db
    .select({ requirementId: testRequirementLinks.requirementId, status: testRequirementLinks.lastStatus })
    .from(testRequirementLinks)
    .where(eq(testRequirementLinks.lastRunAt, importedAt));
  const byRequirement = new Map<number, string[]>();
  for (const link of links) {
    byRequirement.set(link.requirementId, [...(byRequirement.get(link.requirementId) ?? []), link.status]);
  }
  return new Map([...byRequirement].map(([requirementId, statuses]) => [requirementId, aggregateRunStatus(statuses)]));
}

function mutualExclusionBetween(reqA: number, reqB: number, runStatuses: Map<number, string>[], minOverlap: number) {
  let bothTested = 0;
  let bothPassed = 0;
  let aPassedBFailed = 0;
  let aFailedBPassed = 0;
  let bothFailed = 0;
  for (const statuses of runStatuses) {
    const statusA = statuses.get(reqA);
    const statusB = statuses.get(reqB);
    if (statusA === undefined || statusB === undefined) continue;
    bothTested += 1;
    if (statusA === "passed" && statusB === "passed") bothPassed += 1;
    else if (statusA === "passed" && statusB === "failed") aPassedBFailed += 1;
    else if (statusA === "failed" && statusB === "passed") aFailedBPassed += 1;
    else if (statusA === "failed" && statusB === "failed") bothFailed += 1;
  }
  if (bothTested < minOverlap || bothPassed > 0) return undefined;
  const inverseRuns = aPassedBFailed + aFailedBPassed;
  if (inverseRuns === 0) return undefined;
  const inverseRatio = inverseRuns / bothTested;
  const confidence: Confidence =
    inverseRatio >= 0.8 && bothTested >= 10 ? "high" : inverseRatio >= 0.5 && bothTested >= 5 ? "medium" : "low";
  return {
    confidence,
    runsAnalyzed: bothTested,
    details: {
      both_passed: bothPassed,
      a_passed_b_failed: aPassedBFailed,
      a_failed_b_passed: aFailedBPassed,
      both_failed: bothFailed,
      inverse_ratio: inverseRatio,
    },
  };
}

export async function detectMutualExclusion(db: Database, options: DetectorOptions): Promise<ConflictResult[]> {
  const runs = await db
    .select({ importedAt: testRuns.importedAt })
    .from(testRuns)
    .orderBy(desc(testRuns.importedAt), desc(testRuns.id))
    .limit(options.minRuns * 2);
  if (runs.length < options.minRuns) return [];

  const runStatuses = await Promise.all(runs.map((run) => runRequirementStatuses(db, run.importedAt)));
  const linked = await db
    .selectDistinct({ requirementId: testRequirementLinks.requirementId })
    .from(testRequirementLinks);
  const requirementIds = linked.map((row) => row.requirementId).sort((a, b) => a - b);
  const byId = new Map(
    (
      await db
        .select()
        .from(requirements)
        .where(inArray(requirements.id, requirementIds.length ? requirementIds : [-1]))
    ).map((row) => [row.id, row]),
  );

  const conflicts: ConflictResult[] = [];
  for (const [reqA, reqB] of pairs(requirementIds)) {
    const match = mutualExclusionBetween(reqA, reqB, runStatuses, options.minOverlap);
    const a = byId.get(reqA);
    const b = byId.get(reqB);
    if (!match || !a || !b) continue;
    conflicts.push({
      ...conflictBetween(a, b, "mutual_exclusion", match.confidence, match.details),
      runsAnalyzed: match.runsAnalyzed,
    });
  }
  return conflicts;
}

const variablePattern = /([a-z_][a-z0-9_]*)\s*[<>=!]+/g;
const thresholdPattern = /[<>=!]+\s*(\d+(?:\.\d+)?)/g;
const wordPattern = /[a-z_][a-z0-9_]*/g;

function matches(pattern: RegExp, text: string): string[] {
  return [...text.matchAll(pattern)].map((match) => match[1] ?? match[0]);
}

function intersect(a: Set<string>, b: Set<string>): string[] {
  return [...a].filter((item) => b.has(item));
}

function conditionOverlap(a: Requirement, b: Requirement) {
  const condA = a.condition.toLowerCase();
  const condB = b.condition.toLowerCase();
  const commonVariables = intersect(new Set(matches(variablePattern, condA)), new Set(matches(variablePattern, condB)));
  if (commonVariables.length === 0) return undefined;
  const thresholdsA = matches(thresholdPattern, condA).map(Number);
  const thresholdsB = matches(thresholdPattern, condB).map(Number);
  let overlapType = "variable_overlap";
  if (thresholdsA.length && thresholdsB.length) {
    const rangesIntersect =
      Math.max(...thresholdsA) >= Math.min(...thresholdsB) && Math.max(...thresholdsB) >= Math.min(...thresholdsA);
    if (rangesIntersect) overlapType = "range_overlap";
  }
  return {
    common_variables: commonVariables,
    overlap_type: overlapType,
    thresholds_a: thresholdsA,
    thresholds_b: thresholdsB,
  };
}

function conditionConfidence(overlap: ReturnType<typeof conditionOverlap>): Confidence {
  if (overlap?.overlap_type === "range_overlap") return "high";
  if ((overlap?.common_variables.length ?? 0) > 1) return "medium";
  return "low";
}

export async function detectConditionOverlap(db: Database): Promise<ConflictResult[]> {
  const rows = (await requirementsByPath(db)).filter((row) => row.component !== "" && row.condition !== "");
  if (rows.length < 2) return [];
  const conflicts: ConflictResult[] = [];
  for (const [component, group] of groupByComponent(rows)) {
    for (const [a, b] of pairs(group)) {
      const overlap = conditionOverlap(a, b);
      if (!overlap) continue;
      conflicts.push(
        conflictBetween(a, b, "condition_overlap", conditionConfidence(overlap), {
          component,
          condition_a: a.condition,
          condition_b: b.condition,
          ...overlap,
        }),
      );
    }
  }
  return conflicts;
}

const timingPattern = /(\d+(?:\.\d+)?)\s*(seconds?|s|ms|milliseconds?|minutes?|m)/;

export function parseTiming(timing: string): number | undefined {
  const match = timingPattern.exec(timing.toLowerCase().trim());
  if (!match) return undefined;
  const value = Number(match[1]);
  const unit = match[2];
  if (unit === "ms" || unit === "millisecond" || unit === "milliseconds") return value / 1000;
  if (unit === "m" || unit === "minute" || unit === "minutes") return value * 60;
  return value;
}

const minTimingConflictRatio = 2;

function timingConfidence(ratio: number): Confidence {
  return ratio >= 5 ? "high" : ratio >= 2 ? "medium" : "low";
}

export async function detectTimingConflicts(db: Database): Promise<ConflictResult[]> {
  const rows = (await requirementsByPath(db)).filter((row) => row.component !== "" && row.timing !== "");
  if (rows.length < 2) return [];
  const conflicts: ConflictResult[] = [];
  for (const [component, group] of groupByComponent(rows)) {
    for (const [a, b] of pairs(group)) {
      const secondsA = parseTiming(a.timing);
      const secondsB = parseTiming(b.timing);
      if (secondsA === undefined || secondsB === undefined || secondsA === secondsB) continue;
      const smaller = Math.min(secondsA, secondsB);
      const ratio = smaller > 0 ? Math.max(secondsA, secondsB) / smaller : 10;
      if (ratio < minTimingConflictRatio) continue;
      conflicts.push(
        conflictBetween(a, b, "timing_conflict", timingConfidence(ratio), {
          component,
          timing_a: a.timing,
          timing_b: b.timing,
          seconds_a: secondsA,
          seconds_b: secondsB,
          ratio,
        }),
      );
    }
  }
  return conflicts;
}

function conditionsSimilar(condA: string, condB: string): boolean {
  const wordsA = new Set(matches(wordPattern, condA.toLowerCase()));
  const wordsB = new Set(matches(wordPattern, condB.toLowerCase()));
  if (wordsA.size === 0 || wordsB.size === 0) return false;
  return intersect(wordsA, wordsB).length >= Math.min(wordsA.size, wordsB.size) * 0.5;
}

const antonymPairs: [string, string][] = [
  ["show", "hide"],
  ["display", "hide"],
  ["enable", "disable"],
  ["start", "stop"],
  ["allow", "deny"],
  ["accept", "reject"],
  ["open", "close"],
  ["lock", "unlock"],
  ["activate", "deactivate"],
  ["on", "off"],
];

const stopwords = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "but",
  "if",
  "then",
  "of",
  "to",
  "in",
  "on",
  "at",
  "for",
  "with",
  "is",
  "are",
  "be",
  "will",
  "shall",
  "should",
  "must",
  "can",
]);

function setsEqual(a: Set<string>, b: Set<string>): boolean {
  return a.size === b.size && [...a].every((item) => b.has(item));
}

function sharedObject(wordsA: Set<string>, wordsB: Set<string>, antonymPair: [string, string]): string | undefined {
  const excluded = new Set([...antonymPair, ...stopwords]);
  return intersect(wordsA, wordsB).find((word) => !excluded.has(word));
}

function responseContradiction(responseA: string, responseB: string) {
  const respA = responseA.toLowerCase();
  const respB = responseB.toLowerCase();
  const wordsA = new Set(matches(wordPattern, respA));
  const wordsB = new Set(matches(wordPattern, respB));
  for (const [wordA, wordB] of antonymPairs) {
    if ((respA.includes(wordA) && respB.includes(wordB)) || (respA.includes(wordB) && respB.includes(wordA))) {
      const object = sharedObject(wordsA, wordsB, [wordA, wordB]);
      if (!object) continue;
      return {
        contradiction_type: "antonym",
        antonym_pair: [wordA, wordB],
        shared_object: object,
        confidence: "high" as Confidence,
      };
    }
  }
  const common = intersect(wordsA, wordsB);
  if (!setsEqual(wordsA, wordsB) && common.length >= 2) {
    return { contradiction_type: "partial_overlap", common_words: common, confidence: "low" as Confidence };
  }
  return undefined;
}

export async function detectResponseContradictions(db: Database): Promise<ConflictResult[]> {
  const rows = (await requirementsByPath(db)).filter(
    (row) => row.component !== "" && row.condition !== "" && row.response !== "",
  );
  if (rows.length < 2) return [];
  const conflicts: ConflictResult[] = [];
  for (const [component, group] of groupByComponent(rows)) {
    for (const [a, b] of pairs(group)) {
      if (!conditionsSimilar(a.condition, b.condition)) continue;
      const contradiction = responseContradiction(a.response, b.response);
      if (!contradiction) continue;
      conflicts.push(
        conflictBetween(a, b, "response_contradiction", contradiction.confidence, {
          component,
          condition_a: a.condition,
          condition_b: b.condition,
          response_a: a.response,
          response_b: b.response,
          ...contradiction,
        }),
      );
    }
  }
  return conflicts;
}

export async function detectAllStructuredConflicts(db: Database): Promise<ConflictResult[]> {
  return [
    ...(await detectConditionOverlap(db)),
    ...(await detectTimingConflicts(db)),
    ...(await detectResponseContradictions(db)),
  ];
}

async function findUnresolvedConflict(db: Database, conflict: ConflictResult) {
  return db.query.conflictLogs.findFirst({
    where: and(
      or(
        and(
          eq(conflictLogs.requirementAId, conflict.requirementAId),
          eq(conflictLogs.requirementBId, conflict.requirementBId),
        ),
        and(
          eq(conflictLogs.requirementAId, conflict.requirementBId),
          eq(conflictLogs.requirementBId, conflict.requirementAId),
        ),
      ),
      eq(conflictLogs.pattern, conflict.pattern),
      ne(conflictLogs.resolved, true),
    ),
  });
}

export async function logConflicts(db: Database, conflicts: ConflictResult[]) {
  let createdCount = 0;
  let skippedCount = 0;
  for (const conflict of conflicts) {
    const existing = await findUnresolvedConflict(db, conflict);
    const now = storedNow();
    if (existing) {
      await db
        .update(conflictLogs)
        .set({ lastSeenAt: now, timesDetected: existing.timesDetected + 1, updatedAt: now })
        .where(eq(conflictLogs.id, existing.id));
      skippedCount += 1;
      continue;
    }
    await db.insert(conflictLogs).values({
      requirementAId: conflict.requirementAId,
      requirementBId: conflict.requirementBId,
      pattern: conflict.pattern,
      confidence: conflict.confidence,
      details: conflict.details,
      resolved: false,
      resolvedAt: null,
      resolutionNotes: "",
      lastSeenAt: now,
      timesDetected: 1,
      createdAt: now,
      updatedAt: now,
    });
    createdCount += 1;
  }
  return { createdCount, skippedCount };
}
