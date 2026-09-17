import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import {
  agents,
  agentTaskHistory,
  agentTaskRequirements,
  agentTaskReviews,
  intentValidationResults,
  verificationFlowRuns,
  verificationFlowSteps,
  verificationFlows,
} from "../src/db/schema";
import {
  api,
  db,
  expectBadRequest,
  expectNotFound,
  expectTransitionError,
  readTask,
  resetLedgerTables,
  seedAgent,
  seedDependency,
  seedIntent,
  seedLink,
  seedLinkedTestRun,
  seedRequirement,
  seedTask,
  seedTaskRequirement,
  seedTestRun,
} from "./ledger-fixtures";

beforeEach(resetLedgerTables);

describe("GET /tasks/ [REQ-TASK-001]", () => {
  it("list returns tasks newest first with the pagination meta", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("old", { createdAt: "2026-01-01T00:00:00.000Z" });
    await seedTask("new", { status: "claimed", claimedById: coder.id, createdAt: "2026-02-01T00:00:00.000Z" });

    const res = await api("/");

    expect(res.status).toBe(200);
    expect(res.json.meta).toEqual({
      page: 1,
      per_page: 50,
      total: 2,
      total_pages: 1,
      has_next: false,
      has_prev: false,
    });
    expect(res.json.data.map((t: { id: string }) => t.id)).toEqual(["new", "old"]);
    expect(res.json.data[0]).toEqual({
      id: "new",
      title: "Title of new",
      description: "",
      status: "claimed",
      claimed_by: "coder-a",
      sprint: null,
      lease_expires: null,
      attempt_count: 0,
      created_at: "2026-02-01T00:00:00.000Z",
      commit_sha: "",
      test_run: null,
    });
  });

  it("list reports the linked test run at each submitted task's commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc1234" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    const run = await seedLinkedTestRun(requirement.id, "abc1234");

    const res = await api("/");

    expect(res.json.data[0].test_run).toEqual({
      commit_sha: "abc1234",
      status: "passing",
      run_ids: [run.id],
      imported_at: "2026-02-01T00:00:00+00:00",
      passed: 1,
      failed: 0,
      requirements: [{ requirement_id: "REQ-A", passed: 1, failed: 0 }],
    });
  });

  it("list reports a missing run when nothing tested the submitted commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc1234" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "0ldc0de");

    const res = await api("/");

    expect(res.json.data[0].test_run).toMatchObject({ status: "missing", run_ids: [], passed: 0, failed: 0 });
  });

  it("list filters by status and honours sort and paging", async () => {
    await seedTask("a", { createdAt: "2026-01-01T00:00:00.000Z" });
    await seedTask("b", { createdAt: "2026-01-02T00:00:00.000Z" });
    await seedTask("c", { status: "merged", createdAt: "2026-01-03T00:00:00.000Z" });

    const res = await api("/?status=unclaimed&sort=created_at&per_page=1&page=2");

    expect(res.json.meta).toEqual({ page: 2, per_page: 1, total: 2, total_pages: 2, has_next: false, has_prev: true });
    expect(res.json.data.map((t: { id: string }) => t.id)).toEqual(["b"]);
  });

  it("list rejects a non-integer per_page", async () => {
    expectBadRequest(await api("/?per_page=ten"), "invalid_query_param");
  });
});

describe("POST /tasks/agents/register/", () => {
  it("register creates an agent and re-registration updates its role", async () => {
    const created = await api("/agents/register/", {
      body: { agent_id: "agent-1", role: "coder", config: { model: "x" } },
    });
    expect(created.status).toBe(200);
    expect(created.json.data).toEqual({ agent_id: "agent-1", role: "coder", is_active: true });

    const updated = await api("/agents/register/", { body: { agent_id: "agent-1", role: "reviewer" } });
    expect(updated.json.data).toEqual({ agent_id: "agent-1", role: "reviewer", is_active: true });
    const rows = await db().select().from(agents);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ role: "reviewer", config: {} });
    expect(rows[0].lastHeartbeat).not.toBeNull();
  });

  it("register rejects an unknown role", async () => {
    expectBadRequest(
      await api("/agents/register/", { body: { agent_id: "agent-1", role: "manager" } }),
      "missing_field",
    );
  });

  it("register rejects malformed JSON", async () => {
    expectBadRequest(await api("/agents/register/", { method: "POST", rawBody: "{not json" }), "invalid_json");
  });
});

describe("POST /tasks/", () => {
  const draft = {
    agent_id: "planner-a",
    task_id: "task-auth-001",
    title: "Lock out after five failed logins",
    description: "Count failures per account, not per IP.",
    requirements: ["REQ-AUTH-001"],
    done_when: ["pytest tests/test_auth.py -k lockout exits 0"],
    scope_in: ["spectrace/auth/"],
    scope_out: ["spectrace/notifications/"],
    spec_ref: "specs/auth.md#REQ-AUTH-001",
  };

  it("create records a draft task linked to its requirements", async () => {
    await seedAgent("planner-a", "planner");
    const requirement = await seedRequirement("REQ-AUTH-001");

    const res = await api("/", { body: draft });

    expect(res.status).toBe(201);
    expect(res.json.data).toMatchObject({
      id: "task-auth-001",
      status: "draft",
      requirements: ["REQ-AUTH-001"],
      done_when: draft.done_when,
      scope_in: draft.scope_in,
      scope_out: draft.scope_out,
      spec_ref: draft.spec_ref,
      max_attempts: 2,
    });
    const task = await readTask("task-auth-001");
    expect(task).toMatchObject({ status: "draft", title: draft.title, doneWhen: draft.done_when });
    const [link] = await db().select().from(agentTaskRequirements);
    expect(link).toMatchObject({ agenttaskId: task?.id, requirementId: requirement.id });
  });

  it("create rejects an agent that is not a planner", async () => {
    await seedAgent("planner-a", "coder");
    await seedRequirement("REQ-AUTH-001");
    const res = await api("/", { body: draft });
    expectTransitionError(res, "ROLE_NOT_ALLOWED");
  });

  it("create returns 404 for an unknown agent or requirement", async () => {
    expectNotFound(await api("/", { body: draft }), "AGENT_NOT_FOUND");
    await seedAgent("planner-a", "planner");
    expectNotFound(await api("/", { body: draft }), "REQUIREMENT_NOT_FOUND");
  });

  it("create refuses a task id that already exists", async () => {
    await seedAgent("planner-a", "planner");
    await seedTask("task-auth-001");
    const res = await api("/", { body: { ...draft, requirements: [] } });
    expect(res.status).toBe(409);
    expect(res.json.error).toMatchObject({ code: "conflict", details: { reason: "TASK_EXISTS" } });
  });

  it("create requires task_id, title, and agent_id, and lists of strings elsewhere", async () => {
    const missing = await api("/", { body: { task_id: "task-1" } });
    expectBadRequest(missing, "missing_field");
    const malformed = await api("/", { body: { ...draft, done_when: "tests pass" } });
    expectBadRequest(malformed, "invalid_field");
    expect(malformed.json.error?.message).toBe("done_when must be a list of non-empty strings");
  });
});

describe("POST /tasks/{id}/approve-spec", () => {
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

  it("approve-spec moves a complete draft to unclaimed and records who approved it", async () => {
    const reviewer = await seedAgent("reviewer-a", "reviewer");
    await completeDraft();

    const res = await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a", feedback: "Scope is tight" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      from_status: "draft",
      to_status: "unclaimed",
      reviewer_id: "reviewer-a",
      message: "Spec approved by reviewer-a",
    });
    expect(await readTask("task-1")).toMatchObject({ status: "unclaimed" });
    const [history] = await db().select().from(agentTaskHistory);
    expect(history).toMatchObject({
      action: "SPEC_APPROVED",
      agentId: reviewer.id,
      fromStatus: "draft",
      toStatus: "unclaimed",
      details: { feedback: "Scope is tight" },
    });
  });

  it("approve-spec refuses a draft whose spec lacks requirements, scope, or done_when", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "draft" });

    const res = await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });

    expectTransitionError(res, "SPEC_INCOMPLETE");
    expect(res.json.error?.message).toBe(
      "Task 'task-1' cannot leave draft until its spec names requirements, scope_in, done_when",
    );
    expect(await readTask("task-1")).toMatchObject({ status: "draft" });
  });

  it("approve-spec refuses a task that is not a draft", async () => {
    await seedAgent("reviewer-a", "reviewer");
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "claimed", claimedById: coder.id });
    const res = await api("/task-1/approve-spec", { body: { reviewer_id: "reviewer-a" } });
    expectTransitionError(res, "NOT_DRAFT");
    expect(await readTask("task-1")).toMatchObject({ status: "claimed" });
  });

  it("approve-spec rejects a coder as approver", async () => {
    await seedAgent("coder-a", "coder");
    await completeDraft();
    const res = await api("/task-1/approve-spec", { body: { reviewer_id: "coder-a" } });
    expectTransitionError(res, "ROLE_NOT_ALLOWED");
  });

  it("approve-spec requires reviewer_id", async () => {
    const res = await api("/task-1/approve-spec", { body: {} });
    expectBadRequest(res, "missing_field");
  });
});

describe("POST /tasks/{id}/intent-validations", () => {
  it("records a validation and passes when every score reaches 70", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("scorer-a", "reviewer");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });

    const res = await api("/task-1/intent-validations", {
      body: {
        validator_id: "scorer-a",
        commit_sha: "abcdef0123",
        strategic_score: 70,
        opportunity_score: 85,
        drift_score: 100,
      },
    });

    expect(res.status).toBe(201);
    expect(res.json.data).toMatchObject({
      task_id: "task-1",
      commit_sha: "abcdef0123",
      strategic_score: 70,
      passed: true,
      failure_reasons: [],
    });
    const [row] = await db().select().from(intentValidationResults);
    expect(row).toMatchObject({ taskId: task.id, commitSha: "abcdef0123", passed: true });
  });

  it("refuses a validation from the agent that claimed the task", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "in_progress", claimedById: coder.id });

    const res = await api("/task-1/intent-validations", {
      body: {
        validator_id: "coder-a",
        commit_sha: "abcdef0123",
        strategic_score: 90,
        opportunity_score: 90,
        drift_score: 90,
      },
    });

    expectTransitionError(res, "SELF_INTENT_NOT_ALLOWED");
    expect(res.json.error?.message).toBe("Agent 'coder-a' claimed task 'task-1' and cannot score its own intent");
    expect(await db().select().from(intentValidationResults)).toEqual([]);
  });

  it("records a validation from an agent that never claimed the task", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("scorer-a", "reviewer");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });

    const res = await api("/task-1/intent-validations", {
      body: {
        validator_id: "scorer-a",
        commit_sha: "abcdef0123",
        strategic_score: 90,
        opportunity_score: 90,
        drift_score: 90,
      },
    });

    expect(res.status).toBe(201);
    expect(res.json.data).toMatchObject({ task_id: "task-1", commit_sha: "abcdef0123", passed: true });
    const [row] = await db().select().from(intentValidationResults);
    expect(row).toMatchObject({ taskId: task.id, passed: true });
  });

  it("fails when a score falls under 70 and honours an explicit verdict", async () => {
    await seedAgent("scorer-a", "reviewer");
    await seedTask("task-1", { status: "in_progress" });
    const computed = await api("/task-1/intent-validations", {
      body: {
        validator_id: "scorer-a",
        commit_sha: "abc",
        strategic_score: 69,
        opportunity_score: 90,
        drift_score: 90,
        failure_reasons: ["Tests encode the misread spec"],
      },
    });
    expect(computed.json.data).toMatchObject({ passed: false, failure_reasons: ["Tests encode the misread spec"] });

    const explicit = await api("/task-1/intent-validations", {
      body: {
        validator_id: "scorer-a",
        commit_sha: "abc",
        strategic_score: 90,
        opportunity_score: 90,
        drift_score: 90,
        passed: false,
      },
    });
    expect(explicit.json.data).toMatchObject({ passed: false });
  });

  it("returns 404 for an unknown task and 400 for a score outside 0 to 100", async () => {
    await seedAgent("scorer-a", "reviewer");
    const body = {
      validator_id: "scorer-a",
      commit_sha: "abc",
      strategic_score: 90,
      opportunity_score: 90,
      drift_score: 90,
    };
    expectNotFound(await api("/task-9/intent-validations", { body }), "TASK_NOT_FOUND");
    await seedTask("task-1", { status: "in_progress" });
    const res = await api("/task-1/intent-validations", { body: { ...body, drift_score: 101 } });
    expectBadRequest(res, "invalid_field");
    expect(res.json.error?.message).toBe("drift_score must be an integer from 0 to 100");
  });

  it("returns 404 for an unknown validator and 400 when none is named", async () => {
    await seedTask("task-1", { status: "in_progress" });
    const body = { commit_sha: "abc", strategic_score: 90, opportunity_score: 90, drift_score: 90 };

    expectNotFound(
      await api("/task-1/intent-validations", { body: { ...body, validator_id: "ghost" } }),
      "AGENT_NOT_FOUND",
    );
    expectBadRequest(await api("/task-1/intent-validations", { body }), "missing_field");
  });
});

describe("POST /tasks/{id}/claim [REQ-TASK-002]", () => {
  it("claim moves an unclaimed task to claimed with a lease", async () => {
    await seedAgent("coder-a", "coder");
    await seedTask("task-1");

    const res = await api("/task-1/claim", { body: { agent_id: "coder-a", lease_minutes: 10 } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      success: true,
      task_id: "task-1",
      from_status: "unclaimed",
      to_status: "claimed",
      message: "Task claimed by coder-a",
      agent_id: "coder-a",
    });
    const task = await readTask("task-1");
    expect(task?.status).toBe("claimed");
    expect(task?.leaseExpires).toBe(res.json.data.lease_expires);
    const agent = await db().query.agents.findFirst({ where: eq(agents.agentId, "coder-a") });
    expect(agent?.lastHeartbeat).not.toBeNull();
  });

  it("claim returns 404 for an unknown task", async () => {
    await seedAgent("coder-a", "coder");
    const res = await api("/nope/claim", { body: { agent_id: "coder-a" } });
    expectNotFound(res, "TASK_NOT_FOUND");
    expect(res.json.error?.message).toBe("Task 'nope' not found");
  });

  it("claim returns 404 for an unknown agent", async () => {
    await seedTask("task-1");
    expectNotFound(await api("/task-1/claim", { body: { agent_id: "ghost" } }), "AGENT_NOT_FOUND");
  });

  it("claim rejects an inactive agent", async () => {
    await seedAgent("coder-a", "coder", false);
    await seedTask("task-1");
    expectTransitionError(await api("/task-1/claim", { body: { agent_id: "coder-a" } }), "AGENT_INACTIVE");
  });

  it("claim rejects a reviewer", async () => {
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1");
    expectTransitionError(await api("/task-1/claim", { body: { agent_id: "reviewer-a" } }), "ROLE_NOT_ALLOWED");
  });

  it("claim rejects a busy agent", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("busy", { status: "in_progress", claimedById: coder.id });
    await seedTask("task-1");
    expectTransitionError(await api("/task-1/claim", { body: { agent_id: "coder-a" } }), "AGENT_BUSY");
  });

  it("claim rejects a task with unmerged dependencies", async () => {
    await seedAgent("coder-a", "coder");
    const dependency = await seedTask("dep", { status: "approved" });
    const task = await seedTask("task-1");
    await seedDependency(task.id, dependency.id);
    const res = await api("/task-1/claim", { body: { agent_id: "coder-a" } });
    expectTransitionError(res, "DEPENDENCIES_NOT_MET");
    expect(res.json.error?.message).toContain("'dep'");
  });

  it("claim requires agent_id", async () => {
    const res = await api("/task-1/claim", { body: {} });
    expectBadRequest(res, "missing_field");
    expect(res.json.error?.message).toBe("agent_id is required");
  });

  it("claim rejects a lease shorter than a minute", async () => {
    expectBadRequest(await api("/task-1/claim", { body: { agent_id: "coder-a", lease_minutes: 0 } }), "invalid_field");
  });
});

describe("POST /tasks/{id}/start", () => {
  it("start moves a claimed task to in_progress", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "claimed", claimedById: coder.id });

    const res = await api("/task-1/start", { body: { agent_id: "coder-a" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toEqual({
      success: true,
      task_id: "task-1",
      from_status: "claimed",
      to_status: "in_progress",
      message: "Task started by coder-a",
    });
    expect((await readTask("task-1"))?.status).toBe("in_progress");
  });

  it("start rejects an agent that does not own the task", async () => {
    const owner = await seedAgent("coder-a", "coder");
    await seedAgent("coder-b", "coder");
    await seedTask("task-1", { status: "claimed", claimedById: owner.id });
    const res = await api("/task-1/start", { body: { agent_id: "coder-b" } });
    expectTransitionError(res, "NOT_OWNER");
    expect(res.json.error?.message).toBe("Task 'task-1' is claimed by coder-a, not coder-b");
  });

  it("start rejects a task that is already in progress", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    expectTransitionError(await api("/task-1/start", { body: { agent_id: "coder-a" } }), "INVALID_TRANSITION");
  });
});

describe("POST /tasks/{id}/complete [REQ-TASK-003]", () => {
  it("complete moves an in_progress task to ready_for_review with the commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    await seedIntent(task.id, "abcdef0123", true);

    const res = await api("/task-1/complete", { body: { agent_id: "coder-a", commit_sha: "abcdef0123" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      to_status: "ready_for_review",
      commit_sha: "abcdef0123",
      message: "Task submitted for review with commit abcdef0",
    });
    expect(await readTask("task-1")).toMatchObject({ status: "ready_for_review", commitSha: "abcdef0123" });
  });

  it("complete records the branch the commit sits on", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    await seedIntent(task.id, "abcdef0123", true);

    const res = await api("/task-1/complete", {
      body: { agent_id: "coder-a", commit_sha: "abcdef0123", branch: "task/task-1" },
    });

    expect(res.json.data).toMatchObject({ branch: "task/task-1" });
    expect(await readTask("task-1")).toMatchObject({ branchName: "task/task-1" });
  });

  it("complete keeps the recorded branch when the resubmission names none", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", {
      status: "changes_requested",
      claimedById: coder.id,
      branchName: "task/task-1",
    });
    await seedIntent(task.id, "1234567890", true);

    await api("/task-1/submit", { body: { agent_id: "coder-a", commit_sha: "1234567890" } });

    expect(await readTask("task-1")).toMatchObject({ branchName: "task/task-1" });
  });

  it("submit is an alias that resubmits a changes_requested task", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "changes_requested", claimedById: coder.id });
    await seedIntent(task.id, "1234567890", true);
    const res = await api("/task-1/submit", { body: { agent_id: "coder-a", commit_sha: "1234567890" } });
    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({ from_status: "changes_requested", to_status: "ready_for_review" });
  });

  it("complete refuses a commit with no intent validation", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    await seedIntent(task.id, "someothersha", true);

    const res = await api("/task-1/complete", { body: { agent_id: "coder-a", commit_sha: "abcdef0123" } });

    expectTransitionError(res, "INTENT_NOT_VALIDATED");
    expect(res.json.error?.message).toBe("Commit abcdef0 on task 'task-1' has no intent validation");
    expect(await readTask("task-1")).toMatchObject({ status: "in_progress", commitSha: "" });
  });

  it("complete refuses a commit whose latest intent validation failed", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    await seedIntent(task.id, "abcdef0123", true);
    await seedIntent(task.id, "abcdef0123", false, ["Tests encode the misread spec"]);

    const res = await api("/task-1/complete", { body: { agent_id: "coder-a", commit_sha: "abcdef0123" } });

    expectTransitionError(res, "INTENT_FAILED");
    expect(res.json.error?.message).toBe(
      "Commit abcdef0 on task 'task-1' failed intent validation: Tests encode the misread spec",
    );
  });

  it("complete accepts a commit once a later intent validation passes", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const task = await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    await seedIntent(task.id, "abcdef0123", false, ["Drift"]);
    await seedIntent(task.id, "abcdef0123", true);

    const res = await api("/task-1/complete", { body: { agent_id: "coder-a", commit_sha: "abcdef0123" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({ to_status: "ready_for_review" });
  });

  it("complete rejects a task that was only claimed", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "claimed", claimedById: coder.id });
    const res = await api("/task-1/complete", { body: { agent_id: "coder-a", commit_sha: "abcdef0123" } });
    expectTransitionError(res, "INVALID_TRANSITION");
  });

  it("complete requires agent_id and commit_sha", async () => {
    const res = await api("/task-1/complete", { body: { agent_id: "coder-a" } });
    expectBadRequest(res, "missing_field");
    expect(res.json.error?.message).toBe("agent_id and commit_sha are required");
  });
});

describe("POST /tasks/{id}/review", () => {
  it("review approves a ready task and stores the review", async () => {
    const coder = await seedAgent("coder-a", "coder");
    const reviewer = await seedAgent("reviewer-a", "reviewer");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "abc");

    const res = await api("/task-1/review", {
      body: {
        reviewer_id: "reviewer-a",
        decision: "approved",
        feedback: "Ship it",
        done_when_results: [{ criterion: "tests pass", passed: true }],
        suggestions: ["rename foo"],
      },
    });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      to_status: "approved",
      decision: "approved",
      attempt_count: 0,
      message: "Task approved by reviewer-a",
    });
    const [review] = await db().select().from(agentTaskReviews);
    expect(review).toMatchObject({
      reviewerId: reviewer.id,
      decision: "approved",
      commitSha: "abc",
      feedback: "Ship it",
      doneWhenResults: [{ criterion: "tests pass", passed: true }],
      blockingIssues: [],
      suggestions: ["rename foo"],
    });
    expect(res.json.data.review_id).toBe(review.id);
    const [history] = await db().select().from(agentTaskHistory);
    expect(history).toMatchObject({
      action: "REVIEWED_APPROVED",
      details: { review_id: review.id, decision: "approved" },
    });
  });

  it("review counts an attempt when requesting changes", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, maxAttempts: 3 });

    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "changes_requested" } });

    expect(res.json.data).toMatchObject({ to_status: "changes_requested", attempt_count: 1 });
    expect(await readTask("task-1")).toMatchObject({ status: "changes_requested", attemptCount: 1 });
  });

  it("review refuses a rejected decision because the state machine has no ready_for_review to abandoned edge", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id });
    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "rejected" } });
    expectTransitionError(res, "INVALID_TRANSITION");
    expect((await readTask("task-1"))?.status).toBe("ready_for_review");
  });

  it("review rejects a coder as reviewer", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("coder-b", "coder");
    await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id });
    const res = await api("/task-1/review", { body: { reviewer_id: "coder-b", decision: "approved" } });
    expectTransitionError(res, "ROLE_NOT_ALLOWED");
  });

  it("review rejects self review", async () => {
    const reviewer = await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "ready_for_review", claimedById: reviewer.id });
    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "approved" } });
    expectTransitionError(res, "SELF_REVIEW_NOT_ALLOWED");
  });

  it("review rejects a task that is not ready", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    await seedTask("task-1", { status: "in_progress", claimedById: coder.id });
    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "approved" } });
    expectTransitionError(res, "NOT_READY_FOR_REVIEW");
  });

  it("review refuses to approve a task whose requirements lack a passing run at the submitted commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc1234" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "0ldc0de");

    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "approved" } });

    expectTransitionError(res, "LINKED_TESTS_NOT_PASSING");
    expect(res.json.error?.message).toContain("REQ-A has no result");
    expect((await readTask("task-1"))?.status).toBe("ready_for_review");
    expect(await db().select().from(agentTaskReviews)).toEqual([]);
  });

  it("review approves when every requirement has a passing run at the submitted commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc1234" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "abc1234");

    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "approved" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({ to_status: "approved", decision: "approved" });
    expect((await readTask("task-1"))?.status).toBe("approved");
  });

  it("review refuses to approve when a linked test failed at the submitted commit", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedAgent("reviewer-a", "reviewer");
    const task = await seedTask("task-1", { status: "ready_for_review", claimedById: coder.id, commitSha: "abc1234" });
    const requirement = await seedRequirement("REQ-A");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLinkedTestRun(requirement.id, "abc1234", "failed");

    const res = await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "approved" } });

    expectTransitionError(res, "LINKED_TESTS_NOT_PASSING");
    expect(res.json.error?.message).toContain("REQ-A failed 1 of 1");
  });

  it("review rejects an unknown decision", async () => {
    expectBadRequest(
      await api("/task-1/review", { body: { reviewer_id: "reviewer-a", decision: "maybe" } }),
      "missing_field",
    );
  });
});

describe("POST /tasks/{id}/merge", () => {
  const MERGED = { status: "approved" as const, branchName: "task/task-1", commitSha: "abc1234def" };

  it("merge records the merge sha on the task with a system history row", async () => {
    await seedTask("task-1", MERGED);

    const res = await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toEqual({
      success: true,
      task_id: "task-1",
      from_status: "approved",
      to_status: "merged",
      message: "Task merged as 99f0011",
      merge_sha: "99f0011",
      branch: "task/task-1",
    });
    expect(await readTask("task-1")).toMatchObject({ status: "merged", mergeSha: "99f0011" });
    const [history] = await db().select().from(agentTaskHistory);
    expect(history).toMatchObject({
      action: "MERGED",
      agentId: null,
      fromStatus: "approved",
      toStatus: "merged",
      details: { merge_sha: "99f0011", branch: "task/task-1" },
    });
  });

  it("[REQ-TASK-011] merge refuses a branch that drifted from the reviewed commit", async () => {
    await seedTask("task-1", MERGED);

    const res = await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "deadbee" } });

    expectTransitionError(res, "BRANCH_DRIFTED");
    expect(res.json.error?.message).toBe("Branch 'task/task-1' is at deadbee; review read abc1234");
    expect(await readTask("task-1")).toMatchObject({ status: "approved", mergeSha: "" });
  });

  it("merge refuses a body that names no merge sha", async () => {
    await seedTask("task-1", MERGED);
    expectBadRequest(await api("/task-1/merge", { body: { branch_head_sha: "abc1234def" } }), "missing_field");
    expect(await readTask("task-1")).toMatchObject({ status: "approved" });
  });

  it("merge rejects a task that is not approved", async () => {
    await seedTask("task-1", { status: "ready_for_review" });
    const res = await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });
    expectTransitionError(res, "NOT_APPROVED");
    expect(res.json.error?.message).toBe("Task 'task-1' is not approved (status: ready_for_review)");
  });
});

describe("GET /tasks/{id}", () => {
  it("reads back the branch and merge sha the ledger recorded", async () => {
    await seedTask("task-1", { status: "approved", branchName: "task/task-1", commitSha: "abc1234def" });

    await api("/task-1/merge", { body: { merge_sha: "99f0011", branch_head_sha: "abc1234def" } });
    const res = await api("/task-1");

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      id: "task-1",
      status: "merged",
      branch: "task/task-1",
      commit_sha: "abc1234def",
      merge_sha: "99f0011",
      claimed_by: null,
    });
  });

  it("answers 404 for a task the ledger does not hold", async () => {
    expectNotFound(await api("/nobody"), "TASK_NOT_FOUND");
  });
});

describe("POST /tasks/{id}/release", () => {
  it("release returns a claimed task to unclaimed", async () => {
    const coder = await seedAgent("coder-a", "coder");
    await seedTask("task-1", { status: "claimed", claimedById: coder.id, leaseExpires: "2099-01-01T00:00:00.000Z" });

    const res = await api("/task-1/release", { body: { reason: "operator" } });

    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      to_status: "unclaimed",
      reason: "operator",
      message: "Task released (operator)",
    });
    expect(await readTask("task-1")).toMatchObject({ status: "unclaimed", claimedById: null, leaseExpires: null });
    const [history] = await db().select().from(agentTaskHistory);
    expect(history).toMatchObject({ action: "RELEASED", agentId: coder.id, details: { reason: "operator" } });
  });

  it("release rejects a task that is not claimed", async () => {
    await seedTask("task-1");
    expectTransitionError(await api("/task-1/release", { body: {} }), "NOT_CLAIMED");
  });
});

describe("GET /tasks/flow-runs/running/", () => {
  it("running lists running flow runs with step progress", async () => {
    const [flow] = await db()
      .insert(verificationFlows)
      .values({ name: "checkout", displayName: "Checkout", description: "", steps: [], version: 1 })
      .returning();
    const [run] = await db()
      .insert(verificationFlowRuns)
      .values({
        flowId: flow.id,
        status: "running",
        context: {},
        source: "test",
        startedAt: "2026-01-01T00:00:00.000Z",
      })
      .returning();
    await db().insert(verificationFlowRuns).values({
      flowId: flow.id,
      status: "passed",
      context: {},
      source: "test",
      startedAt: "2026-01-01T00:00:00.000Z",
    });
    await db().insert(verificationFlowSteps).values({
      flowRunId: run.id,
      stepOrder: 1,
      name: "login",
      passed: true,
      details: "",
      errorMessage: "",
      responseBody: "",
      startedAt: "2026-01-01T00:00:00.000Z",
      completedAt: "2026-01-01T00:00:01.000Z",
    });

    const res = await api("/flow-runs/running/");

    expect(res.status).toBe(200);
    expect(res.json.data).toEqual({
      runs: [
        {
          id: run.id,
          flow_name: "checkout",
          flow_display_name: "Checkout",
          started_at: "2026-01-01T00:00:00.000Z",
          total_steps: 1,
          completed_steps: 1,
          current_step: null,
          current_step_order: null,
        },
      ],
    });
  });
});

describe("GET /tasks/{id}/context [REQ-TASK-004]", () => {
  it("bundles the task, its specs, their tree and tests, and live drift", async () => {
    await seedRequirement("REQ-AUTH", { path: "0001", numchild: 1 });
    const child = await seedRequirement("REQ-AUTH-001", {
      path: "00010001",
      depth: 2,
      title: "Lock the account",
      description: "Five failures locks it.",
      tags: ["auth", "security"],
      priority: "high",
      verificationStatus: "passing",
      sourceFile: "specs/auth/login.md",
      component: "Lock",
      timing: "within 1 second",
    });
    const task = await seedTask("task-1", {
      status: "unclaimed",
      doneWhen: ["pytest -k lockout exits 0"],
      scopeIn: ["spectrace/auth/lockout.py"],
    });
    await seedTaskRequirement(task.id, child.id);
    await seedTestRun("2026-01-02 00:00:00", ["tests/test_auth.py::test_lockout"]);
    await seedLink(child.id, "tests/test_auth.py::test_lockout", "passed", "2026-01-02 00:00:00");

    const { status, json } = await api("/task-1/context");

    expect(status).toBe(200);
    expect(json.data).toMatchObject({
      task_id: "task-1",
      title: "Title of task-1",
      status: "unclaimed",
      done_when: ["pytest -k lockout exits 0"],
      scope_in: ["spectrace/auth/lockout.py"],
      scope_out: [],
    });
    expect(json.data.requirements).toEqual([
      {
        external_id: "REQ-AUTH-001",
        title: "Lock the account",
        description: "Five failures locks it.",
        verification_status: "passing",
        priority: "high",
        tags: ["auth", "security"],
        source_file: "specs/auth/login.md",
        test_results: [{ test_nodeid: "tests/test_auth.py::test_lockout", last_status: "passed" }],
        tree: { parent: { external_id: "REQ-AUTH", title: "REQ-AUTH" } },
        fret: { component: "Lock", timing: "within 1 second" },
      },
    ]);
    expect(json.data.drift.stale_links.summary).toEqual({ items_checked: 1, errors: 0, warnings: 0 });
  });

  it("names the children of a parent requirement", async () => {
    const parent = await seedRequirement("REQ-AUTH", { path: "0001", numchild: 2 });
    await seedRequirement("REQ-AUTH-001", { path: "00010001", depth: 2, title: "Login" });
    await seedRequirement("REQ-AUTH-002", { path: "00010002", depth: 2, title: "Logout" });
    const task = await seedTask("task-2");
    await seedTaskRequirement(task.id, parent.id);

    const { json } = await api("/task-2/context");

    expect(json.data.requirements[0].tree).toEqual({
      children: [
        { external_id: "REQ-AUTH-001", title: "Login" },
        { external_id: "REQ-AUTH-002", title: "Logout" },
      ],
    });
  });

  it("reports a link whose test left the latest run as a stale_link error", async () => {
    const requirement = await seedRequirement("REQ-1");
    const task = await seedTask("task-3");
    await seedTaskRequirement(task.id, requirement.id);
    await seedTestRun("2026-01-02 00:00:00", ["tests/test_kept.py::test_kept"]);
    await seedLink(requirement.id, "tests/test_kept.py::test_kept");
    await seedLink(requirement.id, "tests/test_gone.py::test_gone", "failed", "2026-01-01 00:00:00");

    const { json } = await api("/task-3/context");

    expect(json.data.drift.stale_links.errors).toEqual([
      {
        type: "stale_link",
        id: "tests/test_gone.py::test_gone:REQ-1",
        message: "Link references test not in latest run",
        test_nodeid: "tests/test_gone.py::test_gone",
        requirement_id: "REQ-1",
        last_status: "failed",
        last_run_at: "2026-01-01T00:00:00+00:00",
      },
    ]);
    expect(json.data.drift.stale_links.summary).toEqual({ items_checked: 2, errors: 1, warnings: 0 });
  });

  it("warns on an active leaf requirement no test covers, and spares the covered and the parents", async () => {
    await seedRequirement("REQ-P", { path: "0001", numchild: 1 });
    const covered = await seedRequirement("REQ-COVERED", { path: "0002" });
    await seedRequirement("REQ-ORPHAN", { path: "00010001", depth: 2, title: "Uncovered" });
    await seedRequirement("REQ-RETIRED", { path: "0003", status: "deprecated" });
    const task = await seedTask("task-4");
    await seedTaskRequirement(task.id, covered.id);
    await seedTestRun("2026-01-02 00:00:00", ["tests/test_covered.py::test_covered"]);
    await seedLink(covered.id, "tests/test_covered.py::test_covered");

    const { json } = await api("/task-4/context");

    expect(json.data.drift.orphan_requirements.warnings).toEqual([
      {
        type: "orphan_requirement",
        id: "REQ-ORPHAN",
        message: "Active requirement has no test coverage and no children",
        title: "Uncovered",
        source_file: "specs/auth.md",
      },
    ]);
    expect(json.data.drift.orphan_requirements.summary.items_checked).toBe(3);
  });

  it("returns empty drift sections when no test run exists", async () => {
    const requirement = await seedRequirement("REQ-1");
    const task = await seedTask("task-5");
    await seedTaskRequirement(task.id, requirement.id);
    await seedLink(requirement.id, "tests/test_one.py::test_one");

    const { json } = await api("/task-5/context");

    expect(json.data.drift.stale_links).toEqual({
      errors: [],
      warnings: [],
      summary: { items_checked: 0, errors: 0, warnings: 0 },
    });
  });

  it("bundles a task that links no requirement", async () => {
    await seedTask("task-6");

    const { status, json } = await api("/task-6/context");

    expect(status).toBe(200);
    expect(json.data.requirements).toEqual([]);
  });

  it("answers 404 for a task the ledger has never seen", async () => {
    const { status, json } = await api("/task-missing/context");

    expect(status).toBe(404);
    expect(json.error).toEqual({ code: "not_found", message: "Task not found: task-missing" });
  });
});
