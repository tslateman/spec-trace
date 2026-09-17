import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { median, weekStart } from "../src/api/v1/queries/factory-report";
import {
  agentTaskHistory,
  intentValidationResults,
  taskGateRefusals,
  testResultRequirements,
  testResults,
  testRuns,
} from "../src/db/schema";
import {
  db,
  resetLedgerTables,
  seedRequirement,
  seedTask,
  seedTaskRequirement,
  type TaskSeed,
} from "./ledger-fixtures";

beforeEach(resetLedgerTables);

const DAY_MS = 24 * 60 * 60 * 1000;

function daysAgo(days: number): string {
  return new Date(Date.now() - days * DAY_MS).toISOString();
}

async function seedHistory(
  taskId: number,
  fromStatus: string,
  toStatus: string,
  timestamp: string,
  action = toStatus.toUpperCase(),
) {
  await db()
    .insert(agentTaskHistory)
    .values({ taskId, agentId: null, action, fromStatus, toStatus, details: {}, timestamp });
}

function totalOf(data: { throughput: Record<string, number>[] }, field: string): number {
  return data.throughput.reduce((total, week) => total + week[field], 0);
}

async function seedRefusal(taskExternalId: string, code: string, createdAt: string) {
  await db()
    .insert(taskGateRefusals)
    .values({
      project: env.SPECTRACE_PROJECT,
      taskExternalId,
      operation: "POST /api/v1/tasks/:task_id/claim",
      code,
      message: `Refused with ${code}`,
      createdAt,
    });
}

async function seedFailingRun(requirementId: number, importedAt: string) {
  const [run] = await db()
    .insert(testRuns)
    .values({
      importedAt,
      sourceFile: "junit.xml",
      ciJobUrl: "",
      gitBranch: "main",
      gitSha: "deadbee",
      repository: "tslater/spec-trace",
      workflowName: "ci",
      workflowRunId: null,
    })
    .returning();
  const [result] = await db()
    .insert(testResults)
    .values({
      testNodeid: "tests/test_thing.py::test_thing",
      classname: "tests",
      name: "test_thing",
      time: 0.1,
      status: "failed",
      message: "assert False",
      testRunId: run.id,
    })
    .returning();
  await db().insert(testResultRequirements).values({ testresultId: result.id, requirementId });
}

async function seedTerminalTask(externalId: string, seed: TaskSeed, toStatus: string, at: string) {
  const task = await seedTask(externalId, { ...seed, createdAt: seed.createdAt ?? at });
  await seedHistory(task.id, "approved", toStatus, at);
  return task;
}

function report(query = "") {
  return SELF.fetch(`http://spectrace/api/v1/reports/factory${query}`, { headers: { "X-API-Key": "test-key" } });
}

async function factory(query = "") {
  const res = await report(query);
  const body = (await res.json()) as { data: any };
  return body.data;
}

describe("weekStart and median", () => {
  it("snaps every day of a week back to its Monday", () => {
    const monday = Date.parse("2026-09-14T00:00:00Z");
    const days = [0, 1, 2, 3, 4, 5, 6].map((offset) => weekStart(monday + offset * DAY_MS));

    expect(new Set(days)).toEqual(new Set(["2026-09-14"]));
    expect(weekStart(monday - DAY_MS)).toBe("2026-09-07");
  });

  it("averages the middle pair on an even count", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 3, 2])).toBe(2.5);
  });
});

describe("GET /reports/factory", () => {
  it("buckets tasks into the week each one ended", async () => {
    await seedTerminalTask("recent-merge", {}, "merged", daysAgo(1));
    await seedTerminalTask("old-merge", {}, "merged", daysAgo(21));
    await seedTerminalTask("recent-abandon", {}, "abandoned", daysAgo(1));

    const data = await factory();

    expect(data.weeks).toHaveLength(12);
    expect(data.throughput).toHaveLength(12);
    expect(totalOf(data, "merged")).toBe(2);
    expect(totalOf(data, "abandoned_at_review")).toBe(1);
    const busy = data.throughput.filter((week: { merged: number }) => week.merged > 0);
    expect(busy).toHaveLength(2);
    expect(data.throughput[data.throughput.length - 1]).toMatchObject({ merged: 1, abandoned_at_review: 1 });
  });

  it("separates a draft refused at spec review from work refused after a claim", async () => {
    const rejected = await seedTask("rejected", { createdAt: daysAgo(3) });
    await seedHistory(rejected.id, "draft", "abandoned", daysAgo(3), "SPEC_REJECTED");
    await seedTerminalTask("burned-out", {}, "abandoned", daysAgo(2));

    const data = await factory();

    expect(totalOf(data, "rejected_at_spec")).toBe(1);
    expect(totalOf(data, "abandoned_at_review")).toBe(1);
  });

  it("drops a task that ended before the window", async () => {
    await seedTerminalTask("ancient", {}, "merged", daysAgo(200));

    const data = await factory();

    expect(totalOf(data, "merged")).toBe(0);
  });

  it("counts refusals by gate code, commonest first", async () => {
    await seedRefusal("t-1", "SPEC_INCOMPLETE", daysAgo(1));
    await seedRefusal("t-2", "SPEC_INCOMPLETE", daysAgo(2));
    await seedRefusal("t-3", "AGENT_BUSY", daysAgo(3));
    await seedRefusal("t-4", "INTENT_FAILED", daysAgo(200));

    const data = await factory();

    expect(data.refusals).toEqual([
      { code: "SPEC_INCOMPLETE", count: 2 },
      { code: "AGENT_BUSY", count: 1 },
    ]);
  });

  it("reports the median seconds a task spent in each state it left", async () => {
    const created = "2026-09-01T00:00:00.000Z";
    const first = await seedTask("timed-a", { createdAt: created });
    await seedHistory(first.id, "draft", "unclaimed", "2026-09-01T00:00:10.000Z");
    await seedHistory(first.id, "unclaimed", "claimed", "2026-09-01T00:01:10.000Z");
    const second = await seedTask("timed-b", { createdAt: created });
    await seedHistory(second.id, "draft", "unclaimed", "2026-09-01T00:00:30.000Z");

    const data = await factory("?weeks=52");

    expect(data.state_durations).toEqual([
      { status: "draft", median_seconds: 20, samples: 2 },
      { status: "unclaimed", median_seconds: 60, samples: 1 },
    ]);
  });

  it("returns the intent score series oldest first", async () => {
    const task = await seedTask("scored");
    await db()
      .insert(intentValidationResults)
      .values([
        {
          taskId: task.id,
          commitSha: "aaa1111",
          strategicScore: 80,
          opportunityScore: 75,
          driftScore: 90,
          passed: true,
          failureReasons: [],
          createdAt: daysAgo(5),
        },
        {
          taskId: task.id,
          commitSha: "bbb2222",
          strategicScore: 40,
          opportunityScore: 95,
          driftScore: 88,
          passed: false,
          failureReasons: ["strategic_score below 70"],
          createdAt: daysAgo(2),
        },
      ]);

    const data = await factory();

    expect(data.intent_scores.map((point: { commit_sha: string }) => point.commit_sha)).toEqual(["aaa1111", "bbb2222"]);
    expect(data.intent_scores[1]).toMatchObject({ task_id: "scored", strategic: 40, drift: 88, passed: false });
  });

  it("counts a merged task whose linked test failed in a later run", async () => {
    const requirement = await seedRequirement("REQ-LOOP-1");
    const task = await seedTerminalTask("regressed", {}, "merged", daysAgo(5));
    await seedTaskRequirement(task.id, requirement.id);
    await seedFailingRun(requirement.id, daysAgo(1));

    const data = await factory();
    const total = data.regressions.reduce((sum: number, week: { failed_later: number }) => sum + week.failed_later, 0);

    expect(total).toBe(1);
  });

  it("ignores a linked failure that predates the merge", async () => {
    const requirement = await seedRequirement("REQ-LOOP-2");
    const task = await seedTerminalTask("clean", {}, "merged", daysAgo(2));
    await seedTaskRequirement(task.id, requirement.id);
    await seedFailingRun(requirement.id, daysAgo(9));

    const data = await factory();
    const total = data.regressions.reduce((sum: number, week: { failed_later: number }) => sum + week.failed_later, 0);

    expect(total).toBe(0);
  });

  it("rejects a non-integer weeks parameter", async () => {
    const res = await report("?weeks=lots");

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: { code: "invalid_query_param", message: "Invalid weeks parameter" } });
  });
});
