import { and, eq, inArray, ne } from "drizzle-orm";
import type { Database } from "../db/client";
import {
  agentTaskRequirements,
  agentTasks,
  requirements,
  testResultRequirements,
  testResults,
  testRuns,
} from "../db/schema";

export interface RequirementTestOutcome {
  requirement_id: string;
  passed: number;
  failed: number;
}

export type LinkedTestStatus = "passing" | "failing" | "missing";

export interface LinkedTestRun {
  commit_sha: string;
  status: LinkedTestStatus;
  run_ids: number[];
  imported_at: string | null;
  passed: number;
  failed: number;
  requirements: RequirementTestOutcome[];
}

export interface TaskCommit {
  id: number;
  commitSha: string;
}

interface LinkedRow {
  taskId: number;
  requirementId: string;
}

interface ResultRow extends LinkedRow {
  status: string;
  runId: number;
  importedAt: string;
}

export async function linkedTestRuns(db: Database, tasks: TaskCommit[]): Promise<LinkedTestRun[]> {
  if (tasks.length === 0) return [];
  const taskIds = tasks.map((task) => task.id);
  const linked = await db
    .select({ taskId: agentTaskRequirements.agenttaskId, requirementId: requirements.externalId })
    .from(agentTaskRequirements)
    .innerJoin(requirements, eq(requirements.id, agentTaskRequirements.requirementId))
    .where(inArray(agentTaskRequirements.agenttaskId, taskIds));
  const results = await db
    .select({
      taskId: agentTasks.id,
      requirementId: requirements.externalId,
      status: testResults.status,
      runId: testRuns.id,
      importedAt: testRuns.importedAt,
    })
    .from(agentTasks)
    .innerJoin(agentTaskRequirements, eq(agentTaskRequirements.agenttaskId, agentTasks.id))
    .innerJoin(requirements, eq(requirements.id, agentTaskRequirements.requirementId))
    .innerJoin(testResultRequirements, eq(testResultRequirements.requirementId, requirements.id))
    .innerJoin(testResults, eq(testResults.id, testResultRequirements.testresultId))
    .innerJoin(testRuns, and(eq(testRuns.id, testResults.testRunId), eq(testRuns.gitSha, agentTasks.commitSha)))
    .where(and(inArray(agentTasks.id, taskIds), ne(agentTasks.commitSha, "")));
  return tasks.map((task) => summarize(task, linked, results));
}

export async function linkedTestRun(db: Database, task: TaskCommit): Promise<LinkedTestRun> {
  const [run] = await linkedTestRuns(db, [task]);
  return run;
}

export function unmetRequirements(run: LinkedTestRun): string[] {
  if (run.requirements.length === 0) return ["it links no requirement"];
  return run.requirements
    .filter((outcome) => outcome.failed > 0 || outcome.passed === 0)
    .map((outcome) =>
      outcome.passed + outcome.failed === 0
        ? `${outcome.requirement_id} has no result`
        : `${outcome.requirement_id} failed ${outcome.failed} of ${outcome.passed + outcome.failed}`,
    );
}

function summarize(task: TaskCommit, linked: LinkedRow[], results: ResultRow[]): LinkedTestRun {
  const ran = results.filter((row) => row.taskId === task.id);
  const outcomes = linked
    .filter((row) => row.taskId === task.id)
    .map((row) => {
      const forRequirement = ran.filter((result) => result.requirementId === row.requirementId);
      const passed = forRequirement.filter((result) => result.status === "passed").length;
      return { requirement_id: row.requirementId, passed, failed: forRequirement.length - passed };
    });
  const failed = outcomes.reduce((total, outcome) => total + outcome.failed, 0);
  const covered = outcomes.length > 0 && outcomes.every((outcome) => outcome.passed + outcome.failed > 0);
  return {
    commit_sha: task.commitSha,
    status: failed > 0 ? "failing" : covered ? "passing" : "missing",
    run_ids: [...new Set(ran.map((row) => row.runId))].sort((a, b) => a - b),
    imported_at: ran.map((row) => row.importedAt).sort()[ran.length - 1] ?? null,
    passed: outcomes.reduce((total, outcome) => total + outcome.passed, 0),
    failed,
    requirements: outcomes,
  };
}
