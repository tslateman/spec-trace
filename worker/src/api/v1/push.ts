import type { Context } from "hono";
import { Hono } from "hono";
import { database } from "../../db/client";
import { coverageSnapshots, driftReports, impactReports } from "../../db/schema";
import type { Env } from "../../env";
import { failure, success } from "../envelope";
import { type CorpusEntryUpsert, CorpusPushRefusal, pushCorpusEntries } from "./queries/corpus-push";
import { newestSnapshot, snapshotJson } from "./queries/coverage-snapshots";
import { type FlowRunRecord, pushFlowRun, UnknownFlow } from "./queries/flow-run-push";
import { InvalidJsonBody, jsonBody } from "./queries/request";
import { pushSlos, type SloUpsert } from "./queries/slo-push";
import {
  type FlowUpsert,
  InvalidRiskLevel,
  pushSpecs,
  type RequirementUpsert,
  type SpecPushBody,
  type TestLinkUpsert,
} from "./queries/spec-push";
import { updateAllSloStatuses } from "./queries/statuses";
import { isoformat, parseDatetime, storedFrom, storedNow } from "./queries/time";

export const push = new Hono<{ Bindings: Env }>();

push.put("/specs", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  const parsed = parseSpecPushBody(body);
  if (typeof parsed === "string") return failure(c, parsed, "validation_error");
  try {
    return success(c, await pushSpecs(database(c.env.DB), parsed));
  } catch (error) {
    if (error instanceof InvalidRiskLevel) return failure(c, error.message, "validation_error");
    throw error;
  }
});

push.put("/slos", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  if (!isListOf(body.slos, isSloUpsert)) {
    return failure(c, "Expected `slos` to be a list of SLOs with name and source_file", "validation_error");
  }
  const db = database(c.env.DB);
  const result = await pushSlos(db, body.slos);
  await updateAllSloStatuses(db);
  return success(c, result);
});

push.put("/corpus/entries", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  if (!isListOf(body.entries, isCorpusEntryUpsert)) {
    return failure(c, "Expected `entries` to be a list of parsed corpus entries", "validation_error");
  }
  try {
    return success(c, await pushCorpusEntries(database(c.env.DB), body.entries));
  } catch (error) {
    if (error instanceof CorpusPushRefusal) return failure(c, error.message, "validation_error");
    throw error;
  }
});

push.post("/flows/runs", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  if (!isFlowRunRecord(body)) {
    return failure(
      c,
      "Expected a flow run with flow_name, status, source, started_at, and a list of steps",
      "validation_error",
    );
  }
  try {
    return success(c, await pushFlowRun(database(c.env.DB), body), undefined, 201);
  } catch (error) {
    if (error instanceof UnknownFlow) return failure(c, error.message, "validation_error");
    throw error;
  }
});

push.post("/results/impact", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  const missing = missingStrings(body, ["project", "base", "head", "generated_at"]);
  if (missing) return failure(c, missing, "validation_error");
  const storedAt = storedNow();
  await database(c.env.DB)
    .insert(impactReports)
    .values({
      project: body.project as string,
      baseRef: body.base as string,
      headRef: body.head as string,
      payload: { ...body, stored_at: isoformat(storedAt) },
      createdAt: storedAt,
    });
  return success(c, receipt(body, storedAt), undefined, 201);
});

push.post("/results/drift", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  const missing = missingStrings(body, ["project", "generated_at"]);
  if (missing) return failure(c, missing, "validation_error");
  const storedAt = storedNow();
  await database(c.env.DB)
    .insert(driftReports)
    .values({
      project: body.project as string,
      payload: { ...body, stored_at: isoformat(storedAt) },
      createdAt: storedAt,
    });
  return success(c, receipt(body, storedAt), undefined, 201);
});

push.post("/results/coverage", async (c) => {
  const body = await parsedBody(c);
  if (body instanceof Response) return body;
  const missing =
    missingStrings(body, ["project", "commit_sha", "git_branch", "generated_at"]) ??
    missingNumbers(body, [
      "specification_rate",
      "structure_rate",
      "verification_rate",
      "total",
      "non_draft",
      "passing",
    ]);
  if (missing) return failure(c, missing, "validation_error");
  const generatedAt = parseDatetime(body.generated_at as string);
  if (!generatedAt) return failure(c, "Expected `generated_at` to be a datetime", "validation_error");

  const db = database(c.env.DB);
  const project = body.project as string;
  const previous = await newestSnapshot(db, project);
  const storedAt = storedNow();
  await db.insert(coverageSnapshots).values({
    project,
    commitSha: body.commit_sha as string,
    gitBranch: body.git_branch as string,
    specificationRate: body.specification_rate as number,
    structureRate: body.structure_rate as number,
    verificationRate: body.verification_rate as number,
    total: body.total as number,
    nonDraft: body.non_draft as number,
    passing: body.passing as number,
    generatedAt: storedFrom(generatedAt),
    createdAt: storedAt,
  });
  return success(c, { ...receipt(body, storedAt), previous: previous ? snapshotJson(previous) : null }, undefined, 201);
});

async function parsedBody(c: Context): Promise<Record<string, unknown> | Response> {
  try {
    return await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return failure(c, `Invalid JSON: ${error.message}`, "invalid_json");
  }
}

function receipt(body: Record<string, unknown>, storedAt: string) {
  return { project: body.project, generated_at: body.generated_at, stored_at: isoformat(storedAt) };
}

function missingStrings(body: Record<string, unknown>, keys: string[]): string | undefined {
  const missing = keys.filter((key) => typeof body[key] !== "string");
  return missing.length === 0 ? undefined : `Expected string fields: ${missing.join(", ")}`;
}

function missingNumbers(body: Record<string, unknown>, keys: string[]): string | undefined {
  const missing = keys.filter((key) => typeof body[key] !== "number" || !Number.isFinite(body[key]));
  return missing.length === 0 ? undefined : `Expected number fields: ${missing.join(", ")}`;
}

function parseSpecPushBody(body: Record<string, unknown>): SpecPushBody | string {
  if (typeof body.project !== "string" || body.project === "") return "Expected `project` to be a non-empty string";
  const replace = body.replace ?? false;
  if (typeof replace !== "boolean") return "Expected `replace` to be a boolean";
  if (!isListOf(body.requirements, isRequirementUpsert)) {
    return "Expected `requirements` to be a list of requirements with external_id, title, and source_file";
  }
  if (!isListOf(body.links, isTestLinkUpsert)) {
    return "Expected `links` to be a list of links with test_nodeid and requirement_id";
  }
  if (!isListOf(body.flows, isFlowUpsert)) {
    return "Expected `flows` to be a list of flows with name, display_name, and at least one step";
  }
  return { project: body.project, replace, requirements: body.requirements, links: body.links, flows: body.flows };
}

function isListOf<T>(value: unknown, guard: (item: unknown) => item is T): value is T[] {
  return Array.isArray(value) && value.every(guard);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRequirementUpsert(item: unknown): item is RequirementUpsert {
  return (
    isRecord(item) &&
    typeof item.external_id === "string" &&
    typeof item.title === "string" &&
    typeof item.source_file === "string"
  );
}

function isTestLinkUpsert(item: unknown): item is TestLinkUpsert {
  return isRecord(item) && typeof item.test_nodeid === "string" && typeof item.requirement_id === "string";
}

function isFlowUpsert(item: unknown): item is FlowUpsert {
  return (
    isRecord(item) &&
    typeof item.name === "string" &&
    typeof item.display_name === "string" &&
    Array.isArray(item.steps) &&
    item.steps.length > 0 &&
    item.steps.every((step) => isRecord(step) && typeof step.name === "string" && typeof step.display_name === "string")
  );
}

function isSloUpsert(item: unknown): item is SloUpsert {
  return isRecord(item) && typeof item.name === "string" && typeof item.source_file === "string";
}

function isCorpusEntryUpsert(item: unknown): item is CorpusEntryUpsert {
  return (
    isRecord(item) &&
    typeof item.external_id === "string" &&
    typeof item.version === "number" &&
    typeof item.content_hash === "string" &&
    typeof item.source_file === "string" &&
    Array.isArray(item.checks)
  );
}

function isFlowRunRecord(body: Record<string, unknown>): body is Record<string, unknown> & FlowRunRecord {
  return (
    typeof body.flow_name === "string" &&
    typeof body.status === "string" &&
    typeof body.source === "string" &&
    typeof body.started_at === "string" &&
    Array.isArray(body.steps) &&
    body.steps.every(
      (step) =>
        isRecord(step) &&
        typeof step.step_order === "number" &&
        typeof step.name === "string" &&
        typeof step.passed === "boolean" &&
        typeof step.started_at === "string" &&
        typeof step.completed_at === "string",
    )
  );
}
