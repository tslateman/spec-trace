import { SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { verificationFlowRuns, verificationFlowSteps, verificationFlows } from "../src/db/schema";
import { db, headers, resetDatabase } from "./fixtures";

beforeEach(async () => {
  await db.delete(verificationFlowSteps);
  await db.delete(verificationFlowRuns);
  await db.delete(verificationFlows);
  await resetDatabase();
});

function post(body: unknown) {
  return SELF.fetch("http://spectrace/api/v1/flows/runs/", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

async function data(res: Response) {
  return ((await res.json()) as { data: Record<string, unknown> }).data;
}

async function seedFlow(name: string) {
  const [row] = await db
    .insert(verificationFlows)
    .values({ name, displayName: name, description: "", steps: [], version: 1, syncedAt: null })
    .returning({ id: verificationFlows.id });
  return row.id;
}

const record = {
  flow_name: "linear-connection",
  status: "passed",
  source: "cli",
  context: { workspace: "acme" },
  started_at: "2026-09-16 11:00:00",
  completed_at: "2026-09-16 11:00:04",
  steps: [
    {
      step_order: 0,
      name: "configuration",
      passed: true,
      details: "key present",
      error_message: "",
      response_status: null,
      response_body: "",
      started_at: "2026-09-16 11:00:00",
      completed_at: "2026-09-16 11:00:01",
    },
    {
      step_order: 1,
      name: "authentication",
      passed: true,
      details: "",
      error_message: "",
      response_status: 200,
      response_body: "{}",
      started_at: "2026-09-16 11:00:01",
      completed_at: "2026-09-16 11:00:04",
    },
  ],
};

describe("POST /api/v1/flows/runs/", () => {
  it("stores the run against its flow and returns 201", async () => {
    const flowId = await seedFlow("linear-connection");

    const res = await post(record);

    expect(res.status).toBe(201);
    expect(await data(res)).toEqual({
      run_id: expect.any(Number),
      flow: "linear-connection",
      status: "passed",
      steps: 2,
    });
    const runs = await db.select().from(verificationFlowRuns);
    expect(runs).toHaveLength(1);
    expect(runs[0].flowId).toBe(flowId);
    expect(runs[0].context).toEqual({ workspace: "acme" });
  });

  it("keeps the timestamps the runner observed", async () => {
    await seedFlow("linear-connection");

    await post(record);

    const [run] = await db.select().from(verificationFlowRuns);
    expect(run.startedAt).toBe("2026-09-16 11:00:00");
    expect(run.completedAt).toBe("2026-09-16 11:00:04");
  });

  it("stores each step in order with its response detail", async () => {
    await seedFlow("linear-connection");

    await post({ ...record, steps: [record.steps[1], record.steps[0]] });

    const steps = await db.select().from(verificationFlowSteps);
    const ordered = steps.sort((a, b) => a.stepOrder - b.stepOrder);
    expect(ordered.map((s) => s.name)).toEqual(["configuration", "authentication"]);
    expect(ordered[1].responseStatus).toBe(200);
    expect(ordered[0].responseStatus).toBeNull();
  });

  it("records a failed run and its error message", async () => {
    await seedFlow("linear-connection");

    const failing = {
      ...record,
      status: "failed",
      steps: [{ ...record.steps[0], passed: false, error_message: "HTTP 401" }],
    };
    const result = await data(await post(failing));

    expect(result.status).toBe("failed");
    const [step] = await db.select().from(verificationFlowSteps);
    expect(step.passed).toBe(false);
    expect(step.errorMessage).toBe("HTTP 401");
  });

  it("refuses a run naming a flow the store lacks", async () => {
    const res = await post(record);

    expect(res.status).toBe(400);
    const error = ((await res.json()) as { error: { message: string } }).error;
    expect(error.message).toContain("is not stored");
    expect(error.message).toContain("spectrace push --flows");
    expect(await db.select().from(verificationFlowRuns)).toHaveLength(0);
  });

  it("refuses a run whose steps are not step records", async () => {
    await seedFlow("linear-connection");

    const res = await post({ ...record, steps: [{ name: "nameless" }] });

    expect(res.status).toBe(400);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("validation_error");
  });

  it("accepts a run with no steps", async () => {
    await seedFlow("linear-connection");

    const result = await data(await post({ ...record, steps: [] }));

    expect(result.steps).toBe(0);
  });
});
