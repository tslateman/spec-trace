import { SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { agentTaskHistory, taskGateRefusals, taskOutcomes } from "../src/db/schema";
import {
  api,
  db,
  expectBadRequest,
  expectTransitionError,
  readTask,
  resetLedgerTables,
  seedAgent,
  seedRequirement,
  seedTask,
  seedTaskRequirement,
} from "./ledger-fixtures";

beforeEach(resetLedgerTables);

async function factoryReport() {
  const res = await SELF.fetch("http://spectrace/api/v1/reports/factory", { headers: { "X-API-Key": "test-key" } });
  return (await res.json()) as { data: { refusals: { code: string; count: number }[] } };
}

async function completeDraft(externalId = "task-1") {
  const task = await seedTask(externalId, {
    status: "draft",
    doneWhen: ["pytest exits 0"],
    scopeIn: ["spectrace/auth/"],
  });
  const requirement = await seedRequirement("REQ-AUTH-001");
  await seedTaskRequirement(task.id, requirement.id);
  return task;
}

describe("POST /tasks/{id}/reject-spec", () => {
  it("abandons the draft and keeps the reviewer's reason on the history row", async () => {
    const reviewer = await seedAgent("reviewer-a", "reviewer");
    await completeDraft();

    const res = await api("/task-1/reject-spec", {
      body: { reviewer_id: "reviewer-a", reason: "scope_in names no file the coder can open" },
    });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      from_status: "draft",
      to_status: "abandoned",
      reviewer_id: "reviewer-a",
      reason: "scope_in names no file the coder can open",
      message: "Spec rejected by reviewer-a",
    });
    expect(await readTask("task-1")).toMatchObject({ status: "abandoned" });
    const [history] = await db().select().from(agentTaskHistory);
    expect(history).toMatchObject({
      action: "SPEC_REJECTED",
      agentId: reviewer.id,
      fromStatus: "draft",
      toStatus: "abandoned",
      details: { reason: "scope_in names no file the coder can open" },
    });
  });

  it("carries the reason into the Lore outbox, where the next task reads it", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await completeDraft();

    await api("/task-1/reject-spec", { body: { reviewer_id: "reviewer-a", reason: "done_when is untestable" } });

    const [outcome] = await db().select().from(taskOutcomes);
    expect(outcome).toMatchObject({ taskExternalId: "task-1", status: "abandoned" });
    expect(outcome.payload).toMatchObject({ status: "abandoned", reason: "done_when is untestable" });
  });

  it("demands a reason", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await completeDraft();

    const res = await api("/task-1/reject-spec", { body: { reviewer_id: "reviewer-a" } });

    expectBadRequest(res, "missing_field");
    expect(res.json.error?.message).toBe("reviewer_id and reason are required");
    expect(await readTask("task-1")).toMatchObject({ status: "draft" });
  });

  it("refuses a task that has already left draft", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "unclaimed" });

    const res = await api("/task-1/reject-spec", { body: { reviewer_id: "reviewer-a", reason: "too late" } });

    expectTransitionError(res, "NOT_DRAFT");
    expect(await readTask("task-1")).toMatchObject({ status: "unclaimed" });
  });

  it("refuses a coder as rejecter", async () => {
    await seedAgent("coder-a", "coder");
    await completeDraft();

    const res = await api("/task-1/reject-spec", { body: { reviewer_id: "coder-a", reason: "nope" } });

    expectTransitionError(res, "ROLE_NOT_ALLOWED");
  });
});

describe("the ledger keeps every refusal it hands back", () => {
  it("stores the gate code, the message, and the operation that was refused", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "draft" });

    await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });

    const [refusal] = await db().select().from(taskGateRefusals);
    expect(refusal).toMatchObject({
      taskExternalId: "task-1",
      operation: "POST /api/v1/tasks/:task_id/approve-spec",
      code: "SPEC_INCOMPLETE",
      message: "Task 'task-1' cannot leave draft until its spec names requirements, scope_in, done_when",
    });
  });

  it("stores a refusal for every gate, not only the spec gate", async () => {
    await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "draft" });
    await seedTask("task-2", { status: "ready_for_review" });

    await api("/task-1/claim", { body: { agent_id: "coder-a" } });
    await api("/task-2/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234" } });
    await api("/nothing-here/start", { body: { agent_id: "coder-a" } });

    const codes = await db().select({ code: taskGateRefusals.code }).from(taskGateRefusals);
    expect(codes.map((row) => row.code).sort()).toEqual(["INVALID_TRANSITION", "NOT_APPROVED", "TASK_NOT_FOUND"]);
  });

  it("writes nothing when the transition succeeds", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await completeDraft();

    await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });

    expect(await db().select().from(taskGateRefusals)).toEqual([]);
  });

  it("counts a stored refusal in the factory report", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "draft" });
    await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });

    const report = await factoryReport();

    expect(report.data.refusals).toEqual([{ code: "SPEC_INCOMPLETE", count: 1 }]);
  });

  it("keeps the refusal after the task is deleted from the report window", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "draft" });
    await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });

    await db()
      .update(taskGateRefusals)
      .set({ createdAt: "2024-01-01T00:00:00.000Z" })
      .where(eq(taskGateRefusals.code, "SPEC_INCOMPLETE"));
    const report = await factoryReport();

    expect(report.data.refusals).toEqual([]);
    expect(await db().select().from(taskGateRefusals)).toHaveLength(1);
  });
});
