import { env } from "cloudflare:test";
import { Validator } from "@cfworker/json-schema";
import { beforeEach, describe, expect, it } from "vitest";
import app from "../src/index";
import {
  get,
  insertConflict,
  insertRequirement,
  insertValidation,
  insertValidationResult,
  insertValidationRun,
  resetDatabase,
} from "./fixtures";

beforeEach(resetDatabase);

const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

function operationKey(method: string, path: string): string {
  const shape = path
    .replace(/:[A-Za-z_]+(\{[^}]*\})?/g, "{}")
    .replace(/\{[^}]+\}/g, "{}")
    .replace(/\/$/, "");
  return `${method.toUpperCase()} ${shape}`;
}

function servedOperations(): string[] {
  return app.routes
    .filter((route) => HTTP_METHODS.includes(route.method) && route.path.startsWith("/api/v1/"))
    .map((route) => operationKey(route.method, route.path));
}

function contractOperations(): string[] {
  return Object.entries(env.CONTRACT.paths).flatMap(([path, operations]) =>
    Object.keys(operations)
      .filter((method) => HTTP_METHODS.includes(method.toUpperCase()))
      .map((method) => operationKey(method, path)),
  );
}

const LIST_ENDPOINTS = [
  { path: "/specs/", contractPath: "/api/v1/specs/" },
  { path: "/tasks/", contractPath: "/api/v1/tasks/" },
  { path: "/results/conflicts/", contractPath: "/api/v1/results/conflicts/" },
  { path: "/results/enforcement-runs/", contractPath: "/api/v1/results/enforcement-runs/" },
];

function responseSchema(contractPath: string): object {
  const operation = env.CONTRACT.paths[contractPath]?.get;
  if (!operation) throw new Error(`${contractPath} has no GET in plans/openapi-worker.yaml`);
  const schema = operation.responses["200"]?.content?.["application/json"]?.schema;
  if (!schema) throw new Error(`${contractPath} declares no 200 application/json schema`);
  return schema as object;
}

function validate(schema: object, body: unknown) {
  const rooted = { ...schema, components: env.CONTRACT.components };
  return new Validator(rooted, "2020-12", false).validate(body);
}

async function seedOneOfEverything() {
  const a = await insertRequirement({ externalId: "REQ-A" });
  const b = await insertRequirement({ externalId: "REQ-B" });
  await insertConflict(a.id, b.id, "2026-01-01 00:00:00");
  const run = await insertValidationRun("2026-01-01 00:00:00");
  const validation = await insertValidation(a.id);
  await insertValidationResult(run.id, validation.id, "pass", "2026-01-01 00:00:00");
}

describe("the Worker serves exactly the operations plans/openapi-worker.yaml names", () => {
  it("names no operation the Worker does not serve, and serves none the contract omits", () => {
    const served = [...new Set(servedOperations())].sort();
    const promised = [...new Set(contractOperations())].sort();

    expect(served).toEqual(promised);
  });
});

describe("the Worker answers what plans/openapi-worker.yaml promises", () => {
  it.each(LIST_ENDPOINTS)("$path matches its declared 200 schema", async ({ path, contractPath }) => {
    await seedOneOfEverything();

    const body = await (await get(path)).json();
    const result = validate(responseSchema(contractPath), body);

    expect(result.errors).toEqual([]);
    expect(result.valid).toBe(true);
  });

  it.each(LIST_ENDPOINTS)("$path pages with the shared page/per_page contract", async ({ path }) => {
    await seedOneOfEverything();

    const body = (await (await get(`${path}?page=1&per_page=1`)).json()) as { meta: Record<string, unknown> };

    expect(Object.keys(body.meta).sort()).toEqual(["has_next", "has_prev", "page", "per_page", "total", "total_pages"]);
    expect(body.meta.per_page).toBe(1);
  });

  it.each(LIST_ENDPOINTS)("$path rejects a non-integer per_page", async ({ path }) => {
    const res = await get(`${path}?per_page=lots`);

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: { code: "invalid_query_param", message: "Invalid per_page parameter" },
    });
  });
});
