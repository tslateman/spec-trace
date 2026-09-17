import { and, asc, count, desc, eq, gte, inArray } from "drizzle-orm";
import type { Database } from "../../../db/client";
import {
  agentTaskHistory,
  agentTaskRequirements,
  agentTasks,
  intentValidationResults,
  taskGateRefusals,
  testResultRequirements,
  testResults,
  testRuns,
} from "../../../db/schema";
import { TASK_STATUSES } from "../../../ledger/state-machine";
import { parseDatetime } from "./time";

const TERMINAL_STATUSES = ["merged", "abandoned"] as const;
const SPEC_REJECTION = "SPEC_REJECTED";
const FAILING_STATUSES = ["failed", "error"];
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export interface ThroughputWeek {
  week: string;
  merged: number;
  rejected_at_spec: number;
  abandoned_at_review: number;
}

export interface RefusalCount {
  code: string;
  count: number;
}

export interface StateDuration {
  status: string;
  median_seconds: number;
  samples: number;
}

export interface IntentScorePoint {
  task_id: string;
  commit_sha: string;
  created_at: string;
  strategic: number;
  opportunity: number;
  drift: number;
  passed: boolean;
}

export interface RegressionWeek {
  week: string;
  merged: number;
  failed_later: number;
}

export interface FactoryReport {
  since: string;
  weeks: string[];
  throughput: ThroughputWeek[];
  refusals: RefusalCount[];
  state_durations: StateDuration[];
  intent_scores: IntentScorePoint[];
  regressions: RegressionWeek[];
}

function epochOf(stored: string): number {
  const parsed = parseDatetime(stored);
  if (!parsed) throw new Error(`Unparseable timestamp in the ledger: ${stored}`);
  return parsed.getTime();
}

export function weekStart(at: number): string {
  const day = new Date(at);
  const midnight = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate());
  const mondayOffset = (new Date(midnight).getUTCDay() + 6) % 7;
  return new Date(midnight - mondayOffset * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

export function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function weeksFrom(sinceWeek: string, now: number): string[] {
  const weeks: string[] = [];
  for (let at = Date.parse(`${sinceWeek}T00:00:00Z`); at <= now; at += WEEK_MS) {
    weeks.push(weekStart(at));
  }
  return weeks;
}

async function terminalTransitions(db: Database, since: number) {
  const rows = await db
    .select({
      taskId: agentTaskHistory.taskId,
      externalId: agentTasks.externalId,
      action: agentTaskHistory.action,
      toStatus: agentTaskHistory.toStatus,
      timestamp: agentTaskHistory.timestamp,
    })
    .from(agentTaskHistory)
    .innerJoin(agentTasks, eq(agentTaskHistory.taskId, agentTasks.id))
    .where(inArray(agentTaskHistory.toStatus, [...TERMINAL_STATUSES]))
    .orderBy(asc(agentTaskHistory.timestamp));
  return rows.map((row) => ({ ...row, at: epochOf(row.timestamp) })).filter((row) => row.at >= since);
}

async function refusalsByCode(db: Database, project: string, sinceIso: string): Promise<RefusalCount[]> {
  return db
    .select({ code: taskGateRefusals.code, count: count() })
    .from(taskGateRefusals)
    .where(and(eq(taskGateRefusals.project, project), gte(taskGateRefusals.createdAt, sinceIso)))
    .groupBy(taskGateRefusals.code)
    .orderBy(desc(count()), asc(taskGateRefusals.code));
}

async function medianTimePerState(db: Database, since: number): Promise<StateDuration[]> {
  const rows = await db
    .select({
      taskId: agentTaskHistory.taskId,
      fromStatus: agentTaskHistory.fromStatus,
      timestamp: agentTaskHistory.timestamp,
      taskCreatedAt: agentTasks.createdAt,
    })
    .from(agentTaskHistory)
    .innerJoin(agentTasks, eq(agentTaskHistory.taskId, agentTasks.id))
    .orderBy(asc(agentTaskHistory.taskId), asc(agentTaskHistory.timestamp));

  const durations = new Map<string, number[]>();
  let currentTask = 0;
  let enteredAt = 0;
  for (const row of rows) {
    if (row.taskId !== currentTask) {
      currentTask = row.taskId;
      enteredAt = epochOf(row.taskCreatedAt);
    }
    const leftAt = epochOf(row.timestamp);
    if (leftAt >= since) {
      const seen = durations.get(row.fromStatus) ?? [];
      seen.push((leftAt - enteredAt) / 1000);
      durations.set(row.fromStatus, seen);
    }
    enteredAt = leftAt;
  }

  return TASK_STATUSES.flatMap((status) => {
    const seconds = durations.get(status);
    return seconds ? [{ status, median_seconds: median(seconds), samples: seconds.length }] : [];
  });
}

async function intentScores(db: Database, since: number): Promise<IntentScorePoint[]> {
  const rows = await db
    .select({
      task_id: agentTasks.externalId,
      commit_sha: intentValidationResults.commitSha,
      created_at: intentValidationResults.createdAt,
      strategic: intentValidationResults.strategicScore,
      opportunity: intentValidationResults.opportunityScore,
      drift: intentValidationResults.driftScore,
      passed: intentValidationResults.passed,
    })
    .from(intentValidationResults)
    .innerJoin(agentTasks, eq(intentValidationResults.taskId, agentTasks.id))
    .orderBy(asc(intentValidationResults.createdAt), asc(intentValidationResults.id));
  return rows.filter((row) => epochOf(row.created_at) >= since);
}

async function tasksFailingAfterMerge(db: Database, merged: { taskId: number; at: number }[]): Promise<Set<number>> {
  if (merged.length === 0) return new Set();
  const rows = await db
    .select({ taskId: agentTaskRequirements.agenttaskId, importedAt: testRuns.importedAt })
    .from(testResults)
    .innerJoin(testRuns, eq(testResults.testRunId, testRuns.id))
    .innerJoin(testResultRequirements, eq(testResultRequirements.testresultId, testResults.id))
    .innerJoin(agentTaskRequirements, eq(agentTaskRequirements.requirementId, testResultRequirements.requirementId))
    .where(
      and(
        inArray(
          agentTaskRequirements.agenttaskId,
          merged.map((task) => task.taskId),
        ),
        inArray(testResults.status, FAILING_STATUSES),
      ),
    );

  const mergedAt = new Map(merged.map((task) => [task.taskId, task.at]));
  const regressed = new Set<number>();
  for (const row of rows) {
    const at = mergedAt.get(row.taskId);
    if (at !== undefined && epochOf(row.importedAt) > at) regressed.add(row.taskId);
  }
  return regressed;
}

export async function factoryReport(db: Database, project: string, weeks: number): Promise<FactoryReport> {
  const now = Date.now();
  const sinceWeek = weekStart(now - (weeks - 1) * WEEK_MS);
  const since = Date.parse(`${sinceWeek}T00:00:00Z`);
  const week = weeksFrom(sinceWeek, now);

  const terminal = await terminalTransitions(db, since);
  const merged = terminal.filter((row) => row.toStatus === "merged");
  const regressed = await tasksFailingAfterMerge(db, merged);

  const abandoned = terminal.filter((row) => row.toStatus === "abandoned");
  const throughput = week.map((start) => {
    const endedThisWeek = (row: { at: number }) => weekStart(row.at) === start;
    const abandonedThisWeek = abandoned.filter(endedThisWeek);
    return {
      week: start,
      merged: merged.filter(endedThisWeek).length,
      rejected_at_spec: abandonedThisWeek.filter((row) => row.action === SPEC_REJECTION).length,
      abandoned_at_review: abandonedThisWeek.filter((row) => row.action !== SPEC_REJECTION).length,
    };
  });
  const regressions = week.map((start) => {
    const inWeek = merged.filter((row) => weekStart(row.at) === start);
    return {
      week: start,
      merged: inWeek.length,
      failed_later: inWeek.filter((row) => regressed.has(row.taskId)).length,
    };
  });

  return {
    since: sinceWeek,
    weeks: week,
    throughput,
    refusals: await refusalsByCode(db, project, new Date(since).toISOString()),
    state_durations: await medianTimePerState(db, since),
    intent_scores: await intentScores(db, since),
    regressions,
  };
}
