import { runDurableObjectAlarm, runInDurableObject } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { agentTaskHistory, taskOutcomes } from "../src/db/schema";
import {
  api,
  db,
  expectBadRequest,
  expectTransitionError,
  ledgerStub,
  readTask,
  resetLedgerTables,
  seedAgent,
  seedLinkedTestRun,
  seedRequirement,
  seedTask,
  seedTaskRequirement,
} from "./ledger-fixtures";

beforeEach(resetLedgerTables);

const PAST = "2026-01-01T00:00:00.000Z";
const FUTURE = "2099-01-01T00:00:00.000Z";

async function scheduledAlarm() {
  return runInDurableObject(ledgerStub(), (_instance, state) => state.storage.getAlarm());
}

async function armAlarm() {
  await runInDurableObject(ledgerStub(), (_instance, state) => state.storage.setAlarm(Date.now() + 60_000));
}

describe("TaskLedger claims", () => {
  it("[REQ-TASK-002] claim grants exactly one of two concurrent claims", async () => {
    await seedAgent("coder-a", "coder");
    await seedAgent("coder-b", "coder");
    await seedTask("task-1");

    const [a, b] = await Promise.all([
      api("/task-1/claim", { body: { agent_id: "coder-a" } }),
      api("/task-1/claim", { body: { agent_id: "coder-b" } }),
    ]);

    expect([a.status, b.status].sort()).toEqual([200, 409]);
    expectTransitionError(a.status === 409 ? a : b, "INVALID_TRANSITION");

    const task = await readTask("task-1");
    expect(task?.status).toBe("claimed");
    const winner = a.status === 200 ? "coder-a" : "coder-b";
    const winnerRow = await db().query.agents.findFirst({
      where: (agents, { eq }) => eq(agents.agentId, winner),
    });
    expect(task?.claimedById).toBe(winnerRow?.id);
    const history = await db().select().from(agentTaskHistory).where(eq(agentTaskHistory.taskId, task!.id));
    expect(history).toHaveLength(1);
  });

  it("claim schedules the lease alarm at lease_expires", async () => {
    await seedAgent("coder-a", "coder");
    await seedTask("task-1");
    const before = Date.now();

    const res = await api("/task-1/claim", { body: { agent_id: "coder-a", lease_minutes: 5 } });

    expect(res.status).toBe(200);
    const alarm = await scheduledAlarm();
    expect(alarm).toBe(Date.parse(res.json.data.lease_expires));
    expect(alarm).toBeGreaterThanOrEqual(before + 5 * 60_000);
  });
});

describe("TaskLedger lease alarm", () => {
  it("alarm releases lapsed leases and reschedules for the next lease", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const other = await seedAgent("coder-b", "coder");
    await seedTask("lapsed", { status: "claimed", claimedById: coder.id, leaseExpires: PAST });
    await seedTask("live", { status: "claimed", claimedById: other.id, leaseExpires: FUTURE });
    await armAlarm();

    expect(await runDurableObjectAlarm(ledgerStub())).toBe(true);

    const lapsed = await readTask("lapsed");
    expect(lapsed).toMatchObject({ status: "unclaimed", claimedById: null, claimedAt: null, leaseExpires: null });
    const live = await readTask("live");
    expect(live).toMatchObject({ status: "claimed", claimedById: other.id });

    const history = await db().select().from(agentTaskHistory).where(eq(agentTaskHistory.taskId, lapsed!.id));
    expect(history).toHaveLength(1);
    expect(history[0]).toMatchObject({
      action: "RELEASED",
      fromStatus: "claimed",
      toStatus: "unclaimed",
      agentId: coder.id,
      details: { reason: "lease_expired" },
    });
    expect(await scheduledAlarm()).toBe(Date.parse(FUTURE));
  });

  it("alarm clears itself when no claimed task remains", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("lapsed", { status: "claimed", claimedById: coder.id, leaseExpires: PAST });
    await armAlarm();

    await runDurableObjectAlarm(ledgerStub());

    expect((await readTask("lapsed"))?.status).toBe("unclaimed");
    expect(await scheduledAlarm()).toBeNull();
  });

  it("alarm leaves in_progress tasks alone", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("working", { status: "in_progress", claimedById: coder.id, leaseExpires: PAST });
    await armAlarm();

    await runDurableObjectAlarm(ledgerStub());

    expect((await readTask("working"))?.status).toBe("in_progress");
  });
});

describe("TaskLedger outbox", () => {
  async function approvedTask(externalId: string) {
    const coder = await seedAgent(`coder-${externalId}`, "coder");
    await seedAgent(`reviewer-${externalId}`, "reviewer");
    const task = await seedTask(externalId, {
      status: "ready_for_review",
      claimedById: coder.id,
      branchName: `task/${externalId}`,
      commitSha: "abc1234def",
    });
    const requirement = await seedRequirement(`REQ-${externalId}`);
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "abc1234def");
    await api(`/${externalId}/review`, {
      body: {
        reviewer_id: `reviewer-${externalId}`,
        decision: "approved",
        done_when_results: [{ criterion: "tests pass", passed: true }],
      },
    });
  }

  it("merge writes an outcome that drains through outcomes and ack", async () => {
    await approvedTask("task-1");

    const merge = await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });
    expect(merge.status).toBe(200);
    expect(merge.json.data).toMatchObject({ from_status: "approved", to_status: "merged" });

    const pending = await api("/outcomes");
    expect(pending.status).toBe(200);
    expect(pending.json.data).toHaveLength(1);
    expect(pending.json.data[0]).toEqual({
      cursor: expect.stringMatching(/^\d+$/),
      task_id: "task-1",
      title: "Title of task-1",
      status: "merged",
      done_when_results: [{ criterion: "tests pass", passed: true }],
      reason: null,
      commit_sha: "abc1234def",
      branch: "task/task-1",
      merge_sha: "99f0011",
      attempt_count: 0,
      max_attempts: 2,
      occurred_at: expect.any(String),
      task_created_at: "2026-01-01T00:00:00.000Z",
      drained: false,
    });
    expect(pending.json.meta).toEqual({ limit: 50, next_cursor: null });
    const cursor = pending.json.data[0].cursor as string;

    const ack = await api("/outcomes/ack", { body: { cursor } });
    expect(ack.status).toBe(200);
    expect(ack.json.data).toEqual({ cursor, drained: 1 });
    const [row] = await db().select().from(taskOutcomes);
    expect(row.drainedAt).not.toBeNull();

    expect((await api(`/outcomes?since=${cursor}`)).json.data).toEqual([]);
    expect((await api("/outcomes")).json.data).toEqual([]);
    expect((await api("/outcomes/ack", { body: { cursor } })).json.data).toEqual({ cursor, drained: 0 });
  });

  it("outcomes pages by cursor and keeps drained rows readable with since", async () => {
    await approvedTask("task-1");
    await approvedTask("task-2");
    await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });
    await api("/task-2/merge", { body: { merge_sha: "99f0022", branch_head_sha: "abc1234def" } });

    const first = await api("/outcomes?limit=1");
    expect(first.json.data.map((row: { task_id: string }) => row.task_id)).toEqual(["task-1"]);
    expect(first.json.meta).toEqual({ limit: 1, next_cursor: first.json.data[0].cursor });

    await api("/outcomes/ack", { body: { cursor: first.json.meta?.next_cursor } });

    const rest = await api("/outcomes");
    expect(rest.json.data.map((row: { task_id: string }) => row.task_id)).toEqual(["task-2"]);
    const replay = await api("/outcomes?since=0");
    expect(replay.json.data.map((row: { task_id: string; drained: boolean }) => [row.task_id, row.drained])).toEqual([
      ["task-1", true],
      ["task-2", false],
    ]);
  });

  it("merge records null done_when_results when the task was never reviewed", async () => {
    await seedTask("task-1", { status: "approved", commitSha: "abc1234def" });
    await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });
    const res = await api("/outcomes");
    expect(res.json.data[0]).toMatchObject({
      task_id: "task-1",
      done_when_results: null,
      branch: "",
      merge_sha: "99f0011",
    });
  });

  it("review writes an abandoned outcome when attempts run out", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, attemptCount: 1, maxAttempts: 2 });

    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "changes_requested" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      to_status: "abandoned",
      attempt_count: 2,
      message: "Task changes_requested by reviewer-a (abandoned after 2 attempts)",
    });
    const [outcome] = await db().select().from(taskOutcomes);
    expect(outcome).toMatchObject({ taskExternalId: "task-1", status: "abandoned" });
    expect(outcome.payload).toMatchObject({ status: "abandoned", attempt_count: 2, max_attempts: 2 });
  });

  it("outcomes rejects a non-numeric since", async () => {
    expectBadRequest(await api("/outcomes?since=abc"), "missing_field");
  });
});
