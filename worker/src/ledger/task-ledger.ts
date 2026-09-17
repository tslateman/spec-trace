import { DurableObject } from "cloudflare:workers";
import { and, count, desc, eq, inArray, ne } from "drizzle-orm";
import { type Database, database } from "../db/client";
import {
  agents,
  agentTaskDependsOn,
  agentTaskHistory,
  agentTaskRequirements,
  agentTaskReviews,
  agentTasks,
  intentValidationResults,
  taskOutcomes,
} from "../db/schema";
import type { Env } from "../env";
import { linkedTestRun, unmetRequirements } from "./linked-tests";
import {
  assertTransition,
  DECISION_STATUS,
  type DoneWhenResult,
  type OutcomePayload,
  type ReviewInput,
  type TaskStatus,
  type Transition,
  TransitionError,
  type TransitionResult,
} from "./state-machine";

type TaskRow = typeof agentTasks.$inferSelect;
type AgentRow = typeof agents.$inferSelect;

const ACTIVE_STATUSES: TaskStatus[] = ["claimed", "in_progress"];

export class TaskLedger extends DurableObject<Env> {
  private readonly db: Database;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.db = database(env.DB);
  }

  claim(taskId: string, agentId: string, leaseMinutes: number): Promise<Transition> {
    return this.transition(async () => {
      const agent = await this.agent(agentId);
      const task = await this.task(taskId);
      if (agent.role !== "coder") {
        throw new TransitionError(
          `Agent '${agentId}' with role '${agent.role}' cannot claim tasks. Only CODER agents can claim tasks.`,
          "ROLE_NOT_ALLOWED",
        );
      }
      const current = await this.currentTaskOf(agent);
      if (current && current.externalId !== taskId) {
        throw new TransitionError(
          `Agent '${agentId}' already has task '${current.externalId}' in progress`,
          "AGENT_BUSY",
        );
      }
      assertTransition(task.status as TaskStatus, "claimed");
      const unmerged = await this.unmergedDependencies(task);
      if (unmerged.length > 0) {
        throw new TransitionError(
          `Task '${taskId}' has unmerged dependencies: [${unmerged.map((d) => `'${d}'`).join(", ")}]`,
          "DEPENDENCIES_NOT_MET",
        );
      }

      const now = new Date();
      const leaseExpires = new Date(now.getTime() + leaseMinutes * 60_000).toISOString();
      await this.updateTask(task, {
        status: "claimed",
        claimedById: agent.id,
        claimedAt: now.toISOString(),
        leaseExpires,
      });
      await this.logHistory(task, agent, "CLAIMED", "claimed", { lease_minutes: leaseMinutes });
      await this.db.update(agents).set({ lastHeartbeat: now.toISOString() }).where(eq(agents.id, agent.id));
      await this.scheduleLeaseAlarm();

      return this.result(task, "claimed", `Task claimed by ${agentId}`, {
        lease_expires: leaseExpires,
        agent_id: agentId,
      });
    });
  }

  start(taskId: string, agentId: string): Promise<Transition> {
    return this.transition(async () => {
      const agent = await this.agent(agentId);
      const task = await this.task(taskId);
      await this.assertOwner(task, agent);
      assertTransition(task.status as TaskStatus, "in_progress");
      await this.updateTask(task, { status: "in_progress" });
      await this.logHistory(task, agent, "STARTED", "in_progress");
      return this.result(task, "in_progress", `Task started by ${agentId}`);
    });
  }

  approveSpec(taskId: string, reviewerId: string, feedback: string): Promise<Transition> {
    return this.transition(async () => {
      const reviewer = await this.agent(reviewerId);
      const task = await this.task(taskId);
      if (reviewer.role !== "reviewer") {
        throw new TransitionError(
          `Agent '${reviewerId}' with role '${reviewer.role}' cannot approve specs. Only REVIEWER agents can approve.`,
          "ROLE_NOT_ALLOWED",
        );
      }
      if (task.status !== "draft") {
        throw new TransitionError(`Task '${taskId}' is not a draft (status: ${task.status})`, "NOT_DRAFT");
      }
      const missing = await this.missingSpecParts(task);
      if (missing.length > 0) {
        throw new TransitionError(
          `Task '${taskId}' cannot leave draft until its spec names ${missing.join(", ")}`,
          "SPEC_INCOMPLETE",
        );
      }
      assertTransition(task.status, "unclaimed");
      await this.updateTask(task, { status: "unclaimed" });
      await this.logHistory(task, reviewer, "SPEC_APPROVED", "unclaimed", { feedback });
      return this.result(task, "unclaimed", `Spec approved by ${reviewerId}`, { reviewer_id: reviewerId });
    });
  }

  rejectSpec(taskId: string, reviewerId: string, reason: string): Promise<Transition> {
    return this.transition(async () => {
      const reviewer = await this.agent(reviewerId);
      const task = await this.task(taskId);
      if (reviewer.role !== "reviewer") {
        throw new TransitionError(
          `Agent '${reviewerId}' with role '${reviewer.role}' cannot reject specs. Only REVIEWER agents can reject.`,
          "ROLE_NOT_ALLOWED",
        );
      }
      if (task.status !== "draft") {
        throw new TransitionError(`Task '${taskId}' is not a draft (status: ${task.status})`, "NOT_DRAFT");
      }
      assertTransition(task.status, "abandoned");
      await this.updateTask(task, { status: "abandoned" });
      await this.logHistory(task, reviewer, "SPEC_REJECTED", "abandoned", { reason });
      await this.recordOutcome(task, "abandoned", null, reason);
      return this.result(task, "abandoned", `Spec rejected by ${reviewerId}`, { reviewer_id: reviewerId, reason });
    });
  }

  submitForReview(taskId: string, agentId: string, commitSha: string, branch: string): Promise<Transition> {
    return this.transition(async () => {
      const agent = await this.agent(agentId);
      const task = await this.task(taskId);
      await this.assertOwner(task, agent);
      assertTransition(task.status as TaskStatus, "ready_for_review");
      await this.assertIntentValidated(task, commitSha);
      const branchName = branch === "" ? task.branchName : branch;
      await this.updateTask(task, { status: "ready_for_review", commitSha, branchName });
      await this.logHistory(task, agent, "SUBMITTED_FOR_REVIEW", "ready_for_review", {
        commit_sha: commitSha,
        branch: branchName,
      });
      return this.result(task, "ready_for_review", `Task submitted for review with commit ${commitSha.slice(0, 7)}`, {
        commit_sha: commitSha,
        branch: branchName,
      });
    });
  }

  review(taskId: string, input: ReviewInput): Promise<Transition> {
    return this.transition(async () => {
      const reviewer = await this.agent(input.reviewer_id);
      const task = await this.task(taskId);
      if (reviewer.role !== "reviewer") {
        throw new TransitionError(
          `Agent '${input.reviewer_id}' with role '${reviewer.role}' cannot review tasks. Only REVIEWER agents can review.`,
          "ROLE_NOT_ALLOWED",
        );
      }
      if (task.claimedById === reviewer.id) {
        throw new TransitionError(
          `Reviewer '${input.reviewer_id}' cannot review their own work`,
          "SELF_REVIEW_NOT_ALLOWED",
        );
      }
      if (task.status !== "ready_for_review") {
        throw new TransitionError(
          `Task '${taskId}' is not ready for review (status: ${task.status})`,
          "NOT_READY_FOR_REVIEW",
        );
      }
      let toStatus = DECISION_STATUS[input.decision];
      assertTransition(task.status, toStatus);
      if (input.decision === "approved") {
        await this.assertLinkedTestsPassed(task);
      }

      const [review] = await this.db
        .insert(agentTaskReviews)
        .values({
          taskId: task.id,
          reviewerId: reviewer.id,
          decision: input.decision,
          commitSha: task.commitSha,
          doneWhenResults: input.done_when_results,
          feedback: input.feedback,
          blockingIssues: input.blocking_issues,
          suggestions: input.suggestions,
          createdAt: new Date().toISOString(),
        })
        .returning({ id: agentTaskReviews.id });

      let attemptCount = task.attemptCount;
      if (input.decision === "changes_requested") {
        attemptCount += 1;
        if (attemptCount >= task.maxAttempts) {
          toStatus = "abandoned";
        }
      }
      await this.updateTask(task, { status: toStatus, attemptCount });
      await this.logHistory(task, reviewer, `REVIEWED_${input.decision.toUpperCase()}`, toStatus, {
        review_id: review.id,
        decision: input.decision,
        attempt_count: attemptCount,
      });
      if (toStatus === "abandoned") {
        await this.recordOutcome({ ...task, attemptCount }, "abandoned", input.done_when_results, input.feedback);
      }

      let message = `Task ${input.decision} by ${input.reviewer_id}`;
      if (toStatus === "abandoned" && input.decision === "changes_requested") {
        message += ` (abandoned after ${attemptCount} attempts)`;
      }
      return this.result(task, toStatus, message, {
        decision: input.decision,
        review_id: review.id,
        attempt_count: attemptCount,
      });
    });
  }

  merge(taskId: string, mergeSha: string, branchHeadSha: string): Promise<Transition> {
    return this.transition(async () => {
      const task = await this.task(taskId);
      if (task.status !== "approved") {
        throw new TransitionError(`Task '${taskId}' is not approved (status: ${task.status})`, "NOT_APPROVED");
      }
      if (branchHeadSha !== task.commitSha) {
        throw new TransitionError(
          `Branch '${task.branchName}' is at ${branchHeadSha.slice(0, 7)}; review read ${task.commitSha.slice(0, 7)}`,
          "BRANCH_DRIFTED",
        );
      }
      await this.updateTask(task, { status: "merged", mergeSha });
      await this.logHistory(task, null, "MERGED", "merged", { merge_sha: mergeSha, branch: task.branchName });
      const latestReview = await this.db.query.agentTaskReviews.findFirst({
        where: eq(agentTaskReviews.taskId, task.id),
        orderBy: desc(agentTaskReviews.createdAt),
      });
      await this.recordOutcome(
        { ...task, mergeSha },
        "merged",
        (latestReview?.doneWhenResults as DoneWhenResult[] | undefined) ?? null,
        null,
      );
      return this.result(task, "merged", `Task merged as ${mergeSha.slice(0, 7)}`, {
        merge_sha: mergeSha,
        branch: task.branchName,
      });
    });
  }

  release(taskId: string, reason: string): Promise<Transition> {
    return this.transition(async () => {
      const task = await this.task(taskId);
      const result = await this.releaseClaimed(task, reason);
      await this.scheduleLeaseAlarm();
      return result;
    });
  }

  async alarm(): Promise<void> {
    await this.ctx.blockConcurrencyWhile(async () => {
      const now = Date.now();
      const claimed = await this.db.select().from(agentTasks).where(eq(agentTasks.status, "claimed"));
      for (const task of claimed) {
        if (task.leaseExpires !== null && Date.parse(task.leaseExpires) < now) {
          await this.releaseClaimed(task, "lease_expired");
        }
      }
      await this.scheduleLeaseAlarm();
    });
  }

  private transition(run: () => Promise<TransitionResult>): Promise<Transition> {
    return this.ctx.blockConcurrencyWhile(async () => {
      try {
        return { ok: true, result: await run() };
      } catch (error) {
        if (error instanceof TransitionError) {
          return { ok: false, code: error.code, message: error.message };
        }
        throw error;
      }
    });
  }

  private async releaseClaimed(task: TaskRow, reason: string): Promise<TransitionResult> {
    if (task.status !== "claimed") {
      throw new TransitionError(`Task '${task.externalId}' is not claimed (status: ${task.status})`, "NOT_CLAIMED");
    }
    const previousAgent =
      task.claimedById === null
        ? null
        : await this.db.query.agents.findFirst({ where: eq(agents.id, task.claimedById) });
    await this.updateTask(task, { status: "unclaimed", claimedById: null, claimedAt: null, leaseExpires: null });
    await this.logHistory(task, previousAgent ?? null, "RELEASED", "unclaimed", { reason });
    return this.result(task, "unclaimed", `Task released (${reason})`, { reason });
  }

  private async scheduleLeaseAlarm(): Promise<void> {
    const leases = await this.db
      .select({ leaseExpires: agentTasks.leaseExpires })
      .from(agentTasks)
      .where(eq(agentTasks.status, "claimed"));
    const times = leases.flatMap((row) => (row.leaseExpires === null ? [] : [Date.parse(row.leaseExpires)]));
    if (times.length === 0) {
      await this.ctx.storage.deleteAlarm();
      return;
    }
    await this.ctx.storage.setAlarm(Math.min(...times));
  }

  private async recordOutcome(
    task: TaskRow,
    status: OutcomePayload["status"],
    doneWhenResults: DoneWhenResult[] | null,
    reason: string | null,
  ) {
    const now = new Date().toISOString();
    const payload: OutcomePayload = {
      task_id: task.externalId,
      title: task.title,
      status,
      done_when_results: doneWhenResults,
      reason,
      commit_sha: task.commitSha,
      branch: task.branchName,
      merge_sha: task.mergeSha,
      attempt_count: task.attemptCount,
      max_attempts: task.maxAttempts,
      occurred_at: now,
      task_created_at: task.createdAt,
    };
    await this.db.insert(taskOutcomes).values({
      project: this.env.SPECTRACE_PROJECT,
      taskExternalId: task.externalId,
      status,
      payload,
      createdAt: now,
    });
  }

  private async agent(agentId: string): Promise<AgentRow> {
    const agent = await this.db.query.agents.findFirst({ where: eq(agents.agentId, agentId) });
    if (!agent) {
      throw new TransitionError(`Agent '${agentId}' not found`, "AGENT_NOT_FOUND");
    }
    if (!agent.isActive) {
      throw new TransitionError(`Agent '${agentId}' is inactive`, "AGENT_INACTIVE");
    }
    return agent;
  }

  private async task(taskId: string): Promise<TaskRow> {
    const task = await this.db.query.agentTasks.findFirst({ where: eq(agentTasks.externalId, taskId) });
    if (!task) {
      throw new TransitionError(`Task '${taskId}' not found`, "TASK_NOT_FOUND");
    }
    return task;
  }

  private async assertOwner(task: TaskRow, agent: AgentRow): Promise<void> {
    if (task.claimedById === agent.id) {
      return;
    }
    const owner =
      task.claimedById === null
        ? null
        : await this.db.query.agents.findFirst({ where: eq(agents.id, task.claimedById) });
    throw new TransitionError(
      `Task '${task.externalId}' is claimed by ${owner?.agentId ?? "no one"}, not ${agent.agentId}`,
      "NOT_OWNER",
    );
  }

  private currentTaskOf(agent: AgentRow) {
    return this.db.query.agentTasks.findFirst({
      where: and(eq(agentTasks.claimedById, agent.id), inArray(agentTasks.status, ACTIVE_STATUSES)),
    });
  }

  private async missingSpecParts(task: TaskRow): Promise<string[]> {
    const [{ linked }] = await this.db
      .select({ linked: count() })
      .from(agentTaskRequirements)
      .where(eq(agentTaskRequirements.agenttaskId, task.id));
    const parts: [string, boolean][] = [
      ["requirements", linked > 0],
      ["scope_in", Array.isArray(task.scopeIn) && task.scopeIn.length > 0],
      ["done_when", Array.isArray(task.doneWhen) && task.doneWhen.length > 0],
    ];
    return parts.filter(([, present]) => !present).map(([name]) => name);
  }

  private async assertIntentValidated(task: TaskRow, commitSha: string): Promise<void> {
    const latest = await this.db.query.intentValidationResults.findFirst({
      where: and(eq(intentValidationResults.taskId, task.id), eq(intentValidationResults.commitSha, commitSha)),
      orderBy: desc(intentValidationResults.id),
    });
    if (!latest) {
      throw new TransitionError(
        `Commit ${commitSha.slice(0, 7)} on task '${task.externalId}' has no intent validation`,
        "INTENT_NOT_VALIDATED",
      );
    }
    if (!latest.passed) {
      const reasons = (latest.failureReasons as string[]).join("; ");
      throw new TransitionError(
        `Commit ${commitSha.slice(0, 7)} on task '${task.externalId}' failed intent validation: ${reasons}`,
        "INTENT_FAILED",
      );
    }
  }

  private async assertLinkedTestsPassed(task: TaskRow): Promise<void> {
    const run = await linkedTestRun(this.db, task);
    if (run.status === "passing") return;
    throw new TransitionError(
      `Task '${task.externalId}' has no passing linked test run at commit ${task.commitSha.slice(0, 7)}: ` +
        unmetRequirements(run).join("; "),
      "LINKED_TESTS_NOT_PASSING",
    );
  }

  private async unmergedDependencies(task: TaskRow): Promise<string[]> {
    const rows = await this.db
      .select({ externalId: agentTasks.externalId })
      .from(agentTaskDependsOn)
      .innerJoin(agentTasks, eq(agentTaskDependsOn.toAgenttaskId, agentTasks.id))
      .where(and(eq(agentTaskDependsOn.fromAgenttaskId, task.id), ne(agentTasks.status, "merged")));
    return rows.map((row) => row.externalId);
  }

  private async updateTask(task: TaskRow, changes: Partial<typeof agentTasks.$inferInsert>): Promise<void> {
    await this.db
      .update(agentTasks)
      .set({ ...changes, updatedAt: new Date().toISOString() })
      .where(eq(agentTasks.id, task.id));
  }

  private async logHistory(
    task: TaskRow,
    agent: AgentRow | null,
    action: string,
    toStatus: TaskStatus,
    details: Record<string, unknown> = {},
  ): Promise<void> {
    await this.db.insert(agentTaskHistory).values({
      taskId: task.id,
      agentId: agent?.id ?? null,
      action,
      fromStatus: task.status,
      toStatus,
      details,
      timestamp: new Date().toISOString(),
    });
  }

  private result(
    task: TaskRow,
    toStatus: TaskStatus,
    message: string,
    details: Record<string, unknown> = {},
  ): TransitionResult {
    return {
      success: true,
      task_id: task.externalId,
      from_status: task.status as TaskStatus,
      to_status: toStatus,
      message,
      ...details,
    };
  }
}
