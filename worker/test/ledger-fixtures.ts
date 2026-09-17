import { env, runInDurableObject, SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { expect } from "vitest";
import { database } from "../src/db/client";
import {
  agents,
  agentTaskDependsOn,
  agentTaskHistory,
  agentTaskRequirements,
  agentTaskReviews,
  agentTasks,
  intentValidationResults,
  requirements,
  taskGateRefusals,
  taskOutcomes,
  testRequirementLinks,
  testResultRequirements,
  testResults,
  testRuns,
  verificationFlowRuns,
  verificationFlowSteps,
  verificationFlows,
} from "../src/db/schema";
import type { AgentRole, TaskStatus } from "../src/ledger/state-machine";

export const db = () => database(env.DB);

export const ledgerStub = () => env.TASK_LEDGER.get(env.TASK_LEDGER.idFromName(env.SPECTRACE_PROJECT));

export async function resetLedgerTables() {
  const tables = [
    agentTaskHistory,
    agentTaskReviews,
    agentTaskDependsOn,
    agentTaskRequirements,
    intentValidationResults,
    taskGateRefusals,
    taskOutcomes,
    agentTasks,
    agents,
    testRequirementLinks,
    testResultRequirements,
    testResults,
    testRuns,
    requirements,
    verificationFlowSteps,
    verificationFlowRuns,
    verificationFlows,
  ];
  for (const table of tables) {
    await db().delete(table);
  }
  await runInDurableObject(ledgerStub(), (_instance, state) => state.storage.deleteAlarm());
}

export async function seedAgent(agentId: string, role: AgentRole, isActive = true) {
  const [agent] = await db()
    .insert(agents)
    .values({ agentId, role, isActive, config: {}, registeredAt: "2026-01-01T00:00:00.000Z" })
    .returning();
  return agent;
}

export interface TaskSeed {
  status?: TaskStatus;
  doneWhen?: string[];
  scopeIn?: string[];
  claimedById?: number | null;
  leaseExpires?: string | null;
  branchName?: string;
  commitSha?: string;
  mergeSha?: string;
  attemptCount?: number;
  maxAttempts?: number;
  createdAt?: string;
}

export async function seedTask(externalId: string, seed: TaskSeed = {}) {
  const [task] = await db()
    .insert(agentTasks)
    .values({
      externalId,
      title: `Title of ${externalId}`,
      description: "",
      status: seed.status ?? "unclaimed",
      claimedById: seed.claimedById ?? null,
      claimedAt: seed.claimedById ? "2026-01-01T00:00:00.000Z" : null,
      leaseExpires: seed.leaseExpires ?? null,
      doneWhen: seed.doneWhen ?? [],
      scopeIn: seed.scopeIn ?? [],
      scopeOut: [],
      specRef: "",
      worktreePath: "",
      branchName: seed.branchName ?? "",
      commitSha: seed.commitSha ?? "",
      mergeSha: seed.mergeSha ?? "",
      attemptCount: seed.attemptCount ?? 0,
      maxAttempts: seed.maxAttempts ?? 2,
      createdAt: seed.createdAt ?? "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
    })
    .returning();
  return task;
}

export async function seedRequirement(externalId: string, overrides: Partial<typeof requirements.$inferInsert> = {}) {
  const [row] = await db()
    .insert(requirements)
    .values({
      path: externalId,
      depth: 1,
      numchild: 0,
      externalId,
      title: externalId,
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

export async function seedLink(
  requirementId: number,
  testNodeid: string,
  lastStatus = "passed",
  lastRunAt: string | null = null,
) {
  await db().insert(testRequirementLinks).values({
    testNodeid,
    lastStatus,
    lastRunAt,
    needsReview: false,
    reviewReason: "",
    createdAt: "2026-01-01 00:00:00",
    updatedAt: "2026-01-01 00:00:00",
    requirementId,
  });
}

export async function seedTestRun(importedAt: string, nodeids: string[]) {
  const [run] = await db()
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
    await db().insert(testResults).values({
      testNodeid: nodeid,
      classname: "tests",
      name: nodeid,
      time: 0.1,
      status: "passed",
      message: "",
      testRunId: run.id,
    });
  }
  return run;
}

export async function seedLinkedTestRun(
  requirementId: number,
  gitSha: string,
  status = "passed",
  nodeid = "tests/test_auth.py::test_login",
) {
  const [run] = await db()
    .insert(testRuns)
    .values({
      importedAt: "2026-02-01 00:00:00",
      sourceFile: "junit.xml",
      ciJobUrl: "",
      gitBranch: "task/task-1",
      gitSha,
      repository: "tslater/spec-trace",
      workflowName: "task-runner",
      workflowRunId: null,
    })
    .returning();
  const [result] = await db()
    .insert(testResults)
    .values({ testNodeid: nodeid, classname: "tests", name: nodeid, time: 0.1, status, message: "", testRunId: run.id })
    .returning();
  await db().insert(testResultRequirements).values({ testresultId: result.id, requirementId });
  return run;
}

export async function seedTaskRequirement(taskId: number, requirementId: number) {
  await db().insert(agentTaskRequirements).values({ agenttaskId: taskId, requirementId });
}

export async function seedIntent(taskId: number, commitSha: string, passed: boolean, failureReasons: string[] = []) {
  await db()
    .insert(intentValidationResults)
    .values({
      taskId,
      commitSha,
      strategicScore: passed ? 90 : 40,
      opportunityScore: 90,
      driftScore: 90,
      passed,
      failureReasons,
      createdAt: "2026-01-01T00:00:00.000Z",
    });
}

export async function seedDependency(taskId: number, dependsOnId: number) {
  await db().insert(agentTaskDependsOn).values({ fromAgenttaskId: taskId, toAgenttaskId: dependsOnId });
}

export function readTask(externalId: string) {
  return db().query.agentTasks.findFirst({ where: eq(agentTasks.externalId, externalId) });
}

export async function api(path: string, init: { method?: string; body?: unknown; rawBody?: string } = {}) {
  const body = init.rawBody ?? (init.body === undefined ? undefined : JSON.stringify(init.body));
  const res = await SELF.fetch(`http://spectrace/api/v1/tasks${path}`, {
    method: init.method ?? (body === undefined ? "GET" : "POST"),
    headers: { "X-API-Key": "test-key", "Content-Type": "application/json" },
    body,
  });
  return { status: res.status, json: (await res.json()) as Envelope };
}

interface Envelope {
  data?: any;
  meta?: Record<string, unknown>;
  error?: { code: string; message: string; details?: { reason?: string } };
}

export function expectTransitionError(res: { status: number; json: Envelope }, reason: string) {
  expect(res.status).toBe(409);
  expect(res.json.error?.code).toBe("transition_error");
  expect(res.json.error?.details?.reason).toBe(reason);
}

export function expectNotFound(res: { status: number; json: Envelope }, reason: string) {
  expect(res.status).toBe(404);
  expect(res.json.error?.code).toBe("not_found");
  expect(res.json.error?.details?.reason).toBe(reason);
}

export function expectBadRequest(res: { status: number; json: Envelope }, code: string) {
  expect(res.status).toBe(400);
  expect(res.json.error?.code).toBe(code);
}
