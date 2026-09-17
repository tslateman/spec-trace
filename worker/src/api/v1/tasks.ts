import { and, asc, count, desc, eq, gt, inArray, isNull, lte } from "drizzle-orm";
import { type Context, Hono } from "hono";
import { type Database, database } from "../../db/client";
import {
  agentSprints,
  agents,
  agentTaskRequirements,
  agentTasks,
  intentValidationResults,
  requirements,
  taskOutcomes,
  verificationFlowRuns,
  verificationFlowSteps,
  verificationFlows,
} from "../../db/schema";
import type { Env } from "../../env";
import { type LinkedTestRun, linkedTestRuns } from "../../ledger/linked-tests";
import {
  AGENT_ROLES,
  type AgentRole,
  type IntentScores,
  intentPassed,
  type OutcomePayload,
  REVIEW_DECISIONS,
  type ReviewDecision,
  type Transition,
  type TransitionCode,
} from "../../ledger/state-machine";
import { failure, success } from "../envelope";
import { clampedOffset, pageMeta, pageRequest } from "../pagination";
import { recordGateRefusal } from "./queries/gate-refusals";
import { taskContext } from "./queries/task-context";
import { isoformat } from "./queries/time";

type AppContext = Context<{ Bindings: Env }>;

const NOT_FOUND_REASONS: TransitionCode[] = ["TASK_NOT_FOUND", "AGENT_NOT_FOUND"];

const SORT_COLUMNS = {
  id: agentTasks.id,
  external_id: agentTasks.externalId,
  title: agentTasks.title,
  status: agentTasks.status,
  claimed_at: agentTasks.claimedAt,
  lease_expires: agentTasks.leaseExpires,
  attempt_count: agentTasks.attemptCount,
  created_at: agentTasks.createdAt,
  updated_at: agentTasks.updatedAt,
};

const MAX_LIMIT = 100;

class BadRequest extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "BadRequest";
  }
}

function rejected(c: AppContext, code: string, message: string) {
  return c.json({ error: { code, message } }, 400);
}

function ledger(c: AppContext) {
  return c.env.TASK_LEDGER.get(c.env.TASK_LEDGER.idFromName(c.env.SPECTRACE_PROJECT));
}

async function transitioned(c: AppContext, transition: Transition) {
  if (transition.ok) {
    return success(c, transition.result);
  }
  await recordGateRefusal(database(c.env.DB), {
    project: c.env.SPECTRACE_PROJECT,
    taskExternalId: c.req.param().task_id,
    operation: `${c.req.method} ${c.req.routePath}`,
    code: transition.code,
    message: transition.message,
  });
  const details = { reason: transition.code };
  return NOT_FOUND_REASONS.includes(transition.code)
    ? failure(c, transition.message, "not_found", 404, details)
    : failure(c, transition.message, "transition_error", 409, details);
}

async function jsonBody(c: AppContext): Promise<Record<string, unknown>> {
  const text = await c.req.text();
  if (text === "") {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new BadRequest("invalid_json", "Invalid JSON body");
  }
}

function requiredString(body: Record<string, unknown>, ...fields: string[]): string[] {
  const values = fields.map((field) => body[field]);
  if (values.some((value) => typeof value !== "string" || value === "")) {
    throw new BadRequest("missing_field", `${fields.join(" and ")} ${fields.length === 1 ? "is" : "are"} required`);
  }
  return values as string[];
}

function stringList(body: Record<string, unknown>, field: string): string[] {
  const value = body[field] ?? [];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || item === "")) {
    throw new BadRequest("invalid_field", `${field} must be a list of non-empty strings`);
  }
  return value as string[];
}

function optionalString(body: Record<string, unknown>, field: string): string {
  const value = body[field] ?? "";
  if (typeof value !== "string") {
    throw new BadRequest("invalid_field", `${field} must be a string`);
  }
  return value;
}

function positiveInteger(body: Record<string, unknown>, field: string, fallback: number): number {
  const value = body[field] ?? fallback;
  if (!Number.isInteger(value) || (value as number) < 1) {
    throw new BadRequest("invalid_field", `${field} must be a positive integer`);
  }
  return value as number;
}

function score(body: Record<string, unknown>, field: string): number {
  const value = body[field];
  if (!Number.isInteger(value) || (value as number) < 0 || (value as number) > 100) {
    throw new BadRequest("invalid_field", `${field} must be an integer from 0 to 100`);
  }
  return value as number;
}

function integerQuery(c: AppContext, name: string, fallback: number): number {
  const raw = c.req.query(name);
  if (raw === undefined) {
    return fallback;
  }
  const value = Number(raw);
  if (!Number.isInteger(value)) {
    throw new BadRequest("invalid_query_param", `Invalid ${name} parameter`);
  }
  return value;
}

function pageLimit(c: AppContext): number {
  return Math.min(integerQuery(c, "limit", 50), MAX_LIMIT);
}

function cursorValue(raw: unknown, field: string): number {
  if (typeof raw !== "string" || !/^\d+$/.test(raw)) {
    throw new BadRequest("missing_field", `${field} must be an outcome cursor`);
  }
  return Number(raw);
}

function orderings(sort: string) {
  return sort.split(",").flatMap((field) => {
    const descending = field.startsWith("-");
    const name = descending ? field.slice(1) : field;
    if (!(name in SORT_COLUMNS)) {
      return [];
    }
    const column = SORT_COLUMNS[name as keyof typeof SORT_COLUMNS];
    return [descending ? desc(column) : asc(column)];
  });
}

function outcomeView(row: typeof taskOutcomes.$inferSelect) {
  return { cursor: String(row.id), ...(row.payload as OutcomePayload), drained: row.drainedAt !== null };
}

export const tasks = new Hono<{ Bindings: Env }>();

tasks.onError((error, c) => {
  if (error instanceof BadRequest) {
    return rejected(c, error.code, error.message);
  }
  throw error;
});

tasks.get("/", async (c) => {
  const request = pageRequest(c, 50);
  const status = c.req.query("status");
  const where = status ? eq(agentTasks.status, status) : undefined;
  const db = database(c.env.DB);

  const [{ total }] = await db.select({ total: count() }).from(agentTasks).where(where);
  const rows = await db
    .select({
      taskId: agentTasks.id,
      id: agentTasks.externalId,
      title: agentTasks.title,
      description: agentTasks.description,
      status: agentTasks.status,
      claimed_by: agents.agentId,
      sprint: agentSprints.name,
      lease_expires: agentTasks.leaseExpires,
      attempt_count: agentTasks.attemptCount,
      created_at: agentTasks.createdAt,
      commit_sha: agentTasks.commitSha,
    })
    .from(agentTasks)
    .leftJoin(agents, eq(agentTasks.claimedById, agents.id))
    .leftJoin(agentSprints, eq(agentTasks.sprintId, agentSprints.id))
    .where(where)
    .orderBy(...orderings(c.req.query("sort") ?? "-created_at"))
    .limit(request.perPage)
    .offset(clampedOffset(request, total));
  const runs = await testRunsByTask(db, rows);

  return success(
    c,
    rows.map(({ taskId, ...row }) => ({ ...row, test_run: runs.get(taskId) ?? null })),
    pageMeta(request, total),
  );
});

async function testRunsByTask(
  db: Database,
  rows: { taskId: number; commit_sha: string }[],
): Promise<Map<number, LinkedTestRun>> {
  const submitted = rows
    .filter((row) => row.commit_sha !== "")
    .map((row) => ({ id: row.taskId, commitSha: row.commit_sha }));
  const runs = await linkedTestRuns(db, submitted);
  return new Map(submitted.map((task, index) => [task.id, testRunView(runs[index])]));
}

function testRunView(run: LinkedTestRun): LinkedTestRun {
  return { ...run, imported_at: run.imported_at === null ? null : isoformat(run.imported_at) };
}

tasks.post("/", async (c) => {
  const body = await jsonBody(c);
  const [taskId, title, agentId] = requiredString(body, "task_id", "title", "agent_id");
  const description = optionalString(body, "description");
  const specRef = optionalString(body, "spec_ref");
  const requirementIds = stringList(body, "requirements");
  const doneWhen = stringList(body, "done_when");
  const scopeIn = stringList(body, "scope_in");
  const scopeOut = stringList(body, "scope_out");
  const maxAttempts = positiveInteger(body, "max_attempts", 2);
  const db = database(c.env.DB);

  const planner = await db.query.agents.findFirst({ where: eq(agents.agentId, agentId) });
  if (!planner) {
    return failure(c, `Agent '${agentId}' not found`, "not_found", 404, { reason: "AGENT_NOT_FOUND" });
  }
  if (planner.role !== "planner") {
    return failure(
      c,
      `Agent '${agentId}' with role '${planner.role}' cannot create tasks. Only PLANNER agents can create tasks.`,
      "transition_error",
      409,
      { reason: "ROLE_NOT_ALLOWED" },
    );
  }
  const linked =
    requirementIds.length === 0
      ? []
      : await db
          .select({ id: requirements.id, externalId: requirements.externalId })
          .from(requirements)
          .where(inArray(requirements.externalId, requirementIds));
  const unknown = requirementIds.filter((id) => !linked.some((row) => row.externalId === id));
  if (unknown.length > 0) {
    return failure(c, `Unknown requirements: ${unknown.join(", ")}`, "not_found", 404, {
      reason: "REQUIREMENT_NOT_FOUND",
    });
  }
  const existing = await db.query.agentTasks.findFirst({ where: eq(agentTasks.externalId, taskId) });
  if (existing) {
    return failure(c, `Task '${taskId}' already exists`, "conflict", 409, { reason: "TASK_EXISTS" });
  }

  const now = new Date().toISOString();
  const [task] = await db
    .insert(agentTasks)
    .values({
      externalId: taskId,
      title,
      description,
      status: "draft",
      doneWhen,
      scopeIn,
      scopeOut,
      specRef,
      worktreePath: "",
      branchName: "",
      commitSha: "",
      attemptCount: 0,
      maxAttempts,
      createdAt: now,
      updatedAt: now,
    })
    .returning({ id: agentTasks.id });
  if (linked.length > 0) {
    await db
      .insert(agentTaskRequirements)
      .values(linked.map((row) => ({ agenttaskId: task.id, requirementId: row.id })));
  }
  return success(
    c,
    {
      id: taskId,
      title,
      description,
      status: "draft",
      requirements: linked.map((row) => row.externalId),
      done_when: doneWhen,
      scope_in: scopeIn,
      scope_out: scopeOut,
      spec_ref: specRef,
      max_attempts: maxAttempts,
      created_at: now,
    },
    undefined,
    201,
  );
});

tasks.post("/agents/register", async (c) => {
  const body = await jsonBody(c);
  const [agentId] = requiredString(body, "agent_id");
  const role = body.role;
  if (!AGENT_ROLES.includes(role as AgentRole)) {
    throw new BadRequest("missing_field", `role must be one of ${AGENT_ROLES.join(", ")}`);
  }
  const now = new Date().toISOString();
  const config = body.config ?? {};
  const [agent] = await database(c.env.DB)
    .insert(agents)
    .values({ agentId, role: role as AgentRole, isActive: true, config, lastHeartbeat: now, registeredAt: now })
    .onConflictDoUpdate({
      target: agents.agentId,
      set: { role: role as AgentRole, isActive: true, config, lastHeartbeat: now },
    })
    .returning({ agent_id: agents.agentId, role: agents.role, is_active: agents.isActive });
  return success(c, agent);
});

tasks.get("/flow-runs/running", async (c) => {
  const db = database(c.env.DB);
  const runs = await db
    .select({
      id: verificationFlowRuns.id,
      flow_name: verificationFlows.name,
      flow_display_name: verificationFlows.displayName,
      started_at: verificationFlowRuns.startedAt,
    })
    .from(verificationFlowRuns)
    .innerJoin(verificationFlows, eq(verificationFlowRuns.flowId, verificationFlows.id))
    .where(eq(verificationFlowRuns.status, "running"))
    .orderBy(desc(verificationFlowRuns.startedAt));

  const data = [];
  for (const run of runs) {
    const steps = await db
      .select({
        name: verificationFlowSteps.name,
        stepOrder: verificationFlowSteps.stepOrder,
        completedAt: verificationFlowSteps.completedAt,
      })
      .from(verificationFlowSteps)
      .where(eq(verificationFlowSteps.flowRunId, run.id))
      .orderBy(asc(verificationFlowSteps.stepOrder));
    const current = steps.find((step) => !step.completedAt);
    data.push({
      ...run,
      total_steps: steps.length,
      completed_steps: steps.filter((step) => step.completedAt).length,
      current_step: current?.name ?? null,
      current_step_order: current?.stepOrder ?? null,
    });
  }
  return success(c, { runs: data });
});

tasks.get("/outcomes", async (c) => {
  const limit = pageLimit(c);
  const since = c.req.query("since");
  const where = since === undefined ? isNull(taskOutcomes.drainedAt) : gt(taskOutcomes.id, cursorValue(since, "since"));
  const rows = await database(c.env.DB)
    .select()
    .from(taskOutcomes)
    .where(where)
    .orderBy(asc(taskOutcomes.id))
    .limit(limit + 1);
  const page = rows.slice(0, limit).map(outcomeView);
  const nextCursor = rows.length > limit ? page[page.length - 1].cursor : null;
  return success(c, page, { limit, next_cursor: nextCursor });
});

tasks.post("/outcomes/ack", async (c) => {
  const body = await jsonBody(c);
  const cursor = cursorValue(body.cursor, "cursor");
  const drained = await database(c.env.DB)
    .update(taskOutcomes)
    .set({ drainedAt: new Date().toISOString() })
    .where(and(lte(taskOutcomes.id, cursor), isNull(taskOutcomes.drainedAt)))
    .returning({ id: taskOutcomes.id });
  return success(c, { cursor: String(cursor), drained: drained.length });
});

tasks.get("/:task_id", async (c) => {
  const taskId = c.req.param("task_id");
  const db = database(c.env.DB);
  const task = await db.query.agentTasks.findFirst({ where: eq(agentTasks.externalId, taskId) });
  if (!task) {
    return failure(c, `Task '${taskId}' not found`, "not_found", 404, { reason: "TASK_NOT_FOUND" });
  }
  const owner =
    task.claimedById === null ? null : await db.query.agents.findFirst({ where: eq(agents.id, task.claimedById) });
  return success(c, {
    id: task.externalId,
    title: task.title,
    description: task.description,
    status: task.status,
    claimed_by: owner?.agentId ?? null,
    done_when: task.doneWhen,
    scope_in: task.scopeIn,
    scope_out: task.scopeOut,
    spec_ref: task.specRef,
    branch: task.branchName,
    commit_sha: task.commitSha,
    merge_sha: task.mergeSha,
    attempt_count: task.attemptCount,
    max_attempts: task.maxAttempts,
    lease_expires: task.leaseExpires,
    claimed_at: task.claimedAt,
    created_at: task.createdAt,
    updated_at: task.updatedAt,
  });
});

tasks.get("/:task_id/context", async (c) => {
  const taskId = c.req.param("task_id");
  const context = await taskContext(database(c.env.DB), taskId);
  if (!context) return failure(c, `Task not found: ${taskId}`, "not_found", 404);
  return success(c, context);
});

tasks.post("/:task_id/approve-spec", async (c) => {
  const body = await jsonBody(c);
  const [reviewerId] = requiredString(body, "reviewer_id");
  const feedback = optionalString(body, "feedback");
  return transitioned(c, await ledger(c).approveSpec(c.req.param("task_id"), reviewerId, feedback));
});

tasks.post("/:task_id/reject-spec", async (c) => {
  const body = await jsonBody(c);
  const [reviewerId, reason] = requiredString(body, "reviewer_id", "reason");
  return transitioned(c, await ledger(c).rejectSpec(c.req.param("task_id"), reviewerId, reason));
});

tasks.post("/:task_id/intent-validations", async (c) => {
  const body = await jsonBody(c);
  const [commitSha, validatorId] = requiredString(body, "commit_sha", "validator_id");
  const scores: IntentScores = {
    strategic_score: score(body, "strategic_score"),
    opportunity_score: score(body, "opportunity_score"),
    drift_score: score(body, "drift_score"),
  };
  if (body.passed !== undefined && typeof body.passed !== "boolean") {
    throw new BadRequest("invalid_field", "passed must be a boolean");
  }
  const passed = typeof body.passed === "boolean" ? body.passed : intentPassed(scores);
  const failureReasons = stringList(body, "failure_reasons");
  const taskId = c.req.param("task_id");
  const db = database(c.env.DB);
  const task = await db.query.agentTasks.findFirst({ where: eq(agentTasks.externalId, taskId) });
  if (!task) {
    return failure(c, `Task '${taskId}' not found`, "not_found", 404, { reason: "TASK_NOT_FOUND" });
  }
  const validator = await db.query.agents.findFirst({ where: eq(agents.agentId, validatorId) });
  if (!validator) {
    return failure(c, `Agent '${validatorId}' not found`, "not_found", 404, { reason: "AGENT_NOT_FOUND" });
  }
  if (task.claimedById === validator.id) {
    return failure(
      c,
      `Agent '${validatorId}' claimed task '${taskId}' and cannot score its own intent`,
      "transition_error",
      409,
      { reason: "SELF_INTENT_NOT_ALLOWED" },
    );
  }
  const now = new Date().toISOString();
  await db.insert(intentValidationResults).values({
    taskId: task.id,
    commitSha,
    strategicScore: scores.strategic_score,
    opportunityScore: scores.opportunity_score,
    driftScore: scores.drift_score,
    passed,
    failureReasons,
    createdAt: now,
  });
  return success(
    c,
    { task_id: taskId, commit_sha: commitSha, ...scores, passed, failure_reasons: failureReasons, created_at: now },
    undefined,
    201,
  );
});

tasks.post("/:task_id/claim", async (c) => {
  const body = await jsonBody(c);
  const [agentId] = requiredString(body, "agent_id");
  const leaseMinutes = body.lease_minutes ?? 30;
  if (!Number.isInteger(leaseMinutes) || (leaseMinutes as number) < 1) {
    throw new BadRequest("invalid_field", "lease_minutes must be a positive integer");
  }
  return transitioned(c, await ledger(c).claim(c.req.param("task_id"), agentId, leaseMinutes as number));
});

tasks.post("/:task_id/start", async (c) => {
  const body = await jsonBody(c);
  const [agentId] = requiredString(body, "agent_id");
  return transitioned(c, await ledger(c).start(c.req.param("task_id"), agentId));
});

async function submitForReview(c: AppContext, taskId: string) {
  const body = await jsonBody(c);
  const [agentId, commitSha] = requiredString(body, "agent_id", "commit_sha");
  const branch = optionalString(body, "branch");
  return transitioned(c, await ledger(c).submitForReview(taskId, agentId, commitSha, branch));
}

tasks.post("/:task_id/complete", (c) => submitForReview(c, c.req.param("task_id")));
tasks.post("/:task_id/submit", (c) => submitForReview(c, c.req.param("task_id")));

tasks.post("/:task_id/review", async (c) => {
  const body = await jsonBody(c);
  const [reviewerId] = requiredString(body, "reviewer_id");
  const decision = body.decision;
  if (!REVIEW_DECISIONS.includes(decision as ReviewDecision)) {
    throw new BadRequest("missing_field", `decision must be one of ${REVIEW_DECISIONS.join(", ")}`);
  }
  const transition = await ledger(c).review(c.req.param("task_id"), {
    reviewer_id: reviewerId,
    decision: decision as ReviewDecision,
    feedback: typeof body.feedback === "string" ? body.feedback : "",
    done_when_results: Array.isArray(body.done_when_results) ? body.done_when_results : [],
    blocking_issues: Array.isArray(body.blocking_issues) ? body.blocking_issues : [],
    suggestions: Array.isArray(body.suggestions) ? body.suggestions : [],
  });
  return transitioned(c, transition);
});

tasks.post("/:task_id/merge", async (c) => {
  const body = await jsonBody(c);
  const [mergeSha, branchHeadSha] = requiredString(body, "merge_sha", "branch_head_sha");
  return transitioned(c, await ledger(c).merge(c.req.param("task_id"), mergeSha, branchHeadSha));
});

tasks.post("/:task_id/release", async (c) => {
  const body = await jsonBody(c);
  const reason = typeof body.reason === "string" && body.reason !== "" ? body.reason : "manual";
  return transitioned(c, await ledger(c).release(c.req.param("task_id"), reason));
});
