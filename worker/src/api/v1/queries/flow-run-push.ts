import { eq } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { verificationFlowRuns, verificationFlowSteps, verificationFlows } from "../../../db/schema";

export interface FlowStepRecord {
  step_order: number;
  name: string;
  passed: boolean;
  details?: string;
  error_message?: string;
  response_status?: number | null;
  response_body?: string;
  started_at: string;
  completed_at: string;
}

export interface FlowRunRecord {
  flow_name: string;
  status: string;
  source: string;
  context?: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  steps: FlowStepRecord[];
}

export interface FlowRunPushResult {
  run_id: number;
  flow: string;
  status: string;
  steps: number;
}

export class UnknownFlow extends Error {}

export async function pushFlowRun(db: Database, record: FlowRunRecord): Promise<FlowRunPushResult> {
  const flow = await db.query.verificationFlows.findFirst({
    where: eq(verificationFlows.name, record.flow_name),
  });
  if (!flow) {
    throw new UnknownFlow(
      `Flow '${record.flow_name}' is not stored. Push the flow definition with \`spectrace push --flows\` before its runs.`,
    );
  }

  const [run] = await db
    .insert(verificationFlowRuns)
    .values({
      flowId: flow.id,
      status: record.status,
      source: record.source,
      context: record.context ?? {},
      startedAt: record.started_at,
      completedAt: record.completed_at,
    })
    .returning({ id: verificationFlowRuns.id });

  const steps = [...record.steps].sort((a, b) => a.step_order - b.step_order);
  if (steps.length > 0) {
    await db.insert(verificationFlowSteps).values(
      steps.map((step) => ({
        flowRunId: run.id,
        stepOrder: step.step_order,
        name: step.name,
        passed: step.passed,
        details: step.details ?? "",
        errorMessage: step.error_message ?? "",
        responseStatus: step.response_status ?? null,
        responseBody: step.response_body ?? "",
        startedAt: step.started_at,
        completedAt: step.completed_at,
      })),
    );
  }

  return { run_id: run.id, flow: flow.name, status: record.status, steps: steps.length };
}
