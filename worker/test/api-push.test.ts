import { SELF } from "cloudflare:test";
import { asc } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import {
  driftReports,
  impactReports,
  requirementDependsOn,
  requirements,
  testRequirementLinks,
  verificationFlowRequirements,
  verificationFlows,
} from "../src/db/schema";
import { db, headers, post, resetDatabase } from "./fixtures";

beforeEach(async () => {
  await db.delete(verificationFlowRequirements);
  await db.delete(verificationFlows);
  await resetDatabase();
});

function put(path: string, body: unknown) {
  return SELF.fetch(`http://spectrace/api/v1${path}`, { method: "PUT", headers, body: JSON.stringify(body) });
}

async function json(res: Response) {
  return (await res.json()) as { data: Record<string, unknown> & { requirements?: unknown }; error: { code: string } };
}

const root = { external_id: "REQ-B", title: "Root B", source_file: "specs/b.md" };
const otherRoot = { external_id: "REQ-A", title: "Root A", source_file: "specs/a.md", risk_level: "high" };
const child = {
  external_id: "REQ-B-1",
  title: "Child",
  source_file: "specs/b.md",
  parent_id: "REQ-B",
  depends_on: ["REQ-A"],
  scope: "checkout",
  response: "charges the card",
  verification_method: "test",
};
const link = { test_nodeid: "tests/test_b.py::test_child", requirement_id: "REQ-B-1" };
const flow = {
  name: "checkout",
  display_name: "Checkout",
  description: "Buy a thing",
  source_file: "flows/checkout.yaml",
  requirements: ["REQ-B-1"],
  steps: [{ name: "load", display_name: "Load", handler: "flows.load" }],
};
const payload = { project: "spectrace", requirements: [root, child, otherRoot], links: [link], flows: [flow] };

async function storedTree() {
  return db
    .select({
      externalId: requirements.externalId,
      path: requirements.path,
      depth: requirements.depth,
      numchild: requirements.numchild,
    })
    .from(requirements)
    .orderBy(asc(requirements.path));
}

describe("PUT /specs/", () => {
  it("builds the tree, edges, links, and flows from an empty store", async () => {
    const res = await put("/specs/", payload);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      data: {
        project: "spectrace",
        requirements: { created: 3, updated: 0, deleted: 0 },
        links: { created: 1, updated: 0, deleted: 0 },
        flows: { created: 1, updated: 0, deleted: 0 },
        unresolved: [],
      },
    });

    expect(await storedTree()).toEqual([
      { externalId: "REQ-A", path: "0001", depth: 1, numchild: 0 },
      { externalId: "REQ-B", path: "0002", depth: 1, numchild: 1 },
      { externalId: "REQ-B-1", path: "00020001", depth: 2, numchild: 0 },
    ]);

    const rows = await db.select().from(requirements).orderBy(asc(requirements.path));
    expect(rows[0]).toMatchObject({ riskLevel: "high", status: "draft", verificationMethod: "unspecified", tags: [] });
    expect(rows[2]).toMatchObject({
      verificationMethod: "test",
      structureCompleteness: 0.4,
      verificationStatus: "untested",
      sloStatus: "not_linked",
      project: "spectrace",
    });

    const edges = await db.select().from(requirementDependsOn);
    expect(edges).toEqual([{ id: edges[0].id, fromRequirementId: rows[2].id, toRequirementId: rows[0].id }]);

    const [storedLink] = await db.select().from(testRequirementLinks);
    expect(storedLink).toMatchObject({
      testNodeid: link.test_nodeid,
      requirementId: rows[2].id,
      lastStatus: "unknown",
      lastRunAt: null,
      needsReview: true,
      reviewReason: "new link",
    });

    const [storedFlow] = await db.select().from(verificationFlows);
    expect(storedFlow).toMatchObject({
      name: "checkout",
      displayName: "Checkout",
      description: "Buy a thing",
      version: 1,
    });
    expect(storedFlow.steps).toEqual([
      { _metadata: { source_file: "flows/checkout.yaml" } },
      { name: "load", handler: "flows.load", display_name: "Load", description: "", type: "handler", config: {} },
    ]);
    const flowLinks = await db.select().from(verificationFlowRequirements);
    expect(flowLinks).toMatchObject([{ verificationflowId: storedFlow.id, requirementId: rows[2].id }]);
  });

  it("updates in place on a second push and clears review flags on links", async () => {
    await put("/specs/", payload);
    const before = await storedTree();

    const res = await put("/specs/", { ...payload, requirements: [{ ...root, title: "Renamed" }, child, otherRoot] });
    expect(await res.json()).toEqual({
      data: {
        project: "spectrace",
        requirements: { created: 0, updated: 3, deleted: 0 },
        links: { created: 0, updated: 1, deleted: 0 },
        flows: { created: 0, updated: 1, deleted: 0 },
        unresolved: [],
      },
    });
    expect(await storedTree()).toEqual(before);
    const titles = (await db.select({ title: requirements.title }).from(requirements)).map((row) => row.title);
    expect(titles).toContain("Renamed");
    const [storedLink] = await db.select().from(testRequirementLinks);
    expect(storedLink).toMatchObject({ needsReview: false, reviewReason: "" });
    expect(await db.select().from(requirementDependsOn)).toHaveLength(1);
  });

  it("inserts siblings in external_id order and shifts later subtrees right", async () => {
    await put("/specs/", payload);
    const res = await put("/specs/", {
      project: "other",
      requirements: [{ external_id: "REQ-0", title: "Zero", source_file: "specs/zero.md" }],
      links: [],
      flows: [],
    });
    expect(res.status).toBe(200);
    expect(await storedTree()).toEqual([
      { externalId: "REQ-0", path: "0001", depth: 1, numchild: 0 },
      { externalId: "REQ-A", path: "0002", depth: 1, numchild: 0 },
      { externalId: "REQ-B", path: "0003", depth: 1, numchild: 1 },
      { externalId: "REQ-B-1", path: "00030001", depth: 2, numchild: 0 },
    ]);
  });

  it("moves a requirement whose parent changed, with its subtree", async () => {
    const grandchild = {
      external_id: "REQ-B-1-1",
      title: "Grandchild",
      source_file: "specs/b.md",
      parent_id: "REQ-B-1",
    };
    await put("/specs/", { ...payload, requirements: [root, child, otherRoot, grandchild] });

    await put("/specs/", {
      ...payload,
      requirements: [root, { ...child, parent_id: "REQ-A" }, otherRoot, grandchild],
    });
    expect(await storedTree()).toEqual([
      { externalId: "REQ-A", path: "0001", depth: 1, numchild: 1 },
      { externalId: "REQ-B-1", path: "00010001", depth: 2, numchild: 1 },
      { externalId: "REQ-B-1-1", path: "000100010001", depth: 3, numchild: 0 },
      { externalId: "REQ-B", path: "0002", depth: 1, numchild: 0 },
    ]);
  });

  it("keeps omitted rows unless replace is true", async () => {
    await put("/specs/", payload);

    const kept = await put("/specs/", { project: "spectrace", requirements: [otherRoot], links: [], flows: [] });
    expect((await json(kept)).data.requirements).toEqual({ created: 0, updated: 1, deleted: 0 });
    expect(await storedTree()).toHaveLength(3);

    const replaced = await put("/specs/", {
      project: "spectrace",
      replace: true,
      requirements: [otherRoot],
      links: [],
      flows: [],
    });
    expect(await replaced.json()).toEqual({
      data: {
        project: "spectrace",
        requirements: { created: 0, updated: 1, deleted: 2 },
        links: { created: 0, updated: 0, deleted: 0 },
        flows: { created: 0, updated: 0, deleted: 1 },
        unresolved: [],
      },
    });
    expect(await storedTree()).toEqual([{ externalId: "REQ-A", path: "0001", depth: 1, numchild: 0 }]);
    expect(await db.select().from(requirementDependsOn)).toEqual([]);
    expect(await db.select().from(testRequirementLinks)).toEqual([]);
    expect(await db.select().from(verificationFlows)).toEqual([]);
    expect(await db.select().from(verificationFlowRequirements)).toEqual([]);
  });

  it("leaves other projects alone when replacing", async () => {
    await put("/specs/", payload);
    await put("/specs/", {
      project: "other",
      replace: true,
      requirements: [{ external_id: "REQ-0", title: "Zero", source_file: "specs/zero.md", depends_on: ["REQ-A"] }],
      links: [{ test_nodeid: "tests/test_zero.py::test_a", requirement_id: "REQ-A" }],
      flows: [],
    });
    expect(await storedTree()).toHaveLength(4);
    expect(await db.select().from(testRequirementLinks)).toHaveLength(2);
    expect(await db.select().from(requirementDependsOn)).toHaveLength(2);
  });

  it("drops references that resolve nowhere and lists them", async () => {
    const res = await put("/specs/", {
      project: "spectrace",
      requirements: [
        {
          external_id: "REQ-X",
          title: "Orphan",
          source_file: "specs/x.md",
          parent_id: "REQ-MISSING",
          depends_on: ["REQ-NOPE"],
        },
      ],
      links: [{ test_nodeid: "tests/test_x.py::test_x", requirement_id: "REQ-GONE" }],
      flows: [{ ...flow, requirements: ["REQ-LOST"] }],
    });
    expect(await res.json()).toEqual({
      data: {
        project: "spectrace",
        requirements: { created: 1, updated: 0, deleted: 0 },
        links: { created: 0, updated: 0, deleted: 0 },
        flows: { created: 1, updated: 0, deleted: 0 },
        unresolved: [
          { kind: "parent_id", source: "REQ-X", ref: "REQ-MISSING" },
          { kind: "depends_on", source: "REQ-X", ref: "REQ-NOPE" },
          { kind: "link", source: "tests/test_x.py::test_x", ref: "REQ-GONE" },
          { kind: "flow", source: "checkout", ref: "REQ-LOST" },
        ],
      },
    });
    expect(await storedTree()).toEqual([{ externalId: "REQ-X", path: "0001", depth: 1, numchild: 0 }]);
  });

  it("rejects an unknown risk level", async () => {
    const res = await put("/specs/", {
      project: "spectrace",
      requirements: [{ external_id: "REQ-R", title: "Risky", source_file: "specs/r.md", risk_level: "extreme" }],
      links: [],
      flows: [],
    });
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: {
        code: "validation_error",
        message:
          "specs/r.md: risk_level 'extreme' is not a RiskLevel. Use one of: unclassified, low, medium, high, critical",
      },
    });
    expect(await storedTree()).toEqual([]);
  });

  it("rejects a malformed body", async () => {
    const res = await put("/specs/", {
      project: "spectrace",
      requirements: [{ title: "No id" }],
      links: [],
      flows: [],
    });
    expect(res.status).toBe(400);
    expect((await json(res)).error.code).toBe("validation_error");
  });
});

describe("POST /results/impact/ and /results/drift/", () => {
  const impact = {
    project: "spectrace",
    base: "main",
    head: "feature",
    generated_at: "2026-08-31T12:00:00+00:00",
    changed_requirements: ["REQ-A"],
    affected_tests: ["tests/test_a.py::test_a"],
    hierarchy_expansion: {},
    dependency_expansion: {},
    risk_score: 0.2,
    risk_level: "low",
  };
  const drift = {
    project: "spectrace",
    generated_at: "2026-08-31T12:00:00+00:00",
    errors: [],
    warnings: [{ type: "spec_drift", id: "REQ-A", message: "changed" }],
    summary: { items_checked: 1, errors: 0, warnings: 1 },
  };

  it("stores an impact report and returns a receipt", async () => {
    const res = await post("/results/impact/", impact);
    expect(res.status).toBe(201);
    const { data } = await json(res);
    expect(data).toMatchObject({ project: "spectrace", generated_at: impact.generated_at });
    const [row] = await db.select().from(impactReports);
    expect(row).toMatchObject({ project: "spectrace", baseRef: "main", headRef: "feature" });
    expect(row.payload).toEqual({ ...impact, stored_at: data.stored_at });
  });

  it("stores a drift report and returns a receipt", async () => {
    const res = await post("/results/drift/", drift);
    expect(res.status).toBe(201);
    const { data } = await json(res);
    const [row] = await db.select().from(driftReports);
    expect(row.payload).toEqual({ ...drift, stored_at: data.stored_at });
  });

  it("rejects a report without provenance", async () => {
    const res = await post("/results/impact/", { changed_requirements: [] });
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({
      error: { code: "validation_error", message: "Expected string fields: project, base, head, generated_at" },
    });
  });
});

describe("PUT /specs/ with replace, against stored results", () => {
  it("removes a requirement whose test results and validations still reference it", async () => {
    const both = [root, { external_id: "REQ-GONE", title: "Gone", source_file: "specs/b.md" }];
    await put("/specs/", { project: "spectrace", requirements: both, links: [], flows: [] });
    await post("/results/test-runs/", {
      source_file: "junit.xml",
      results: [{ test_nodeid: "tests/test_gone.py::test_x", status: "passed", requirement_ids: ["REQ-GONE"] }],
    });
    await post("/results/enforcement/", {
      source: "product",
      validations: [{ requirement_id: "REQ-GONE", name: "Verify", status: "success" }],
    });

    const res = await put("/specs/", {
      project: "spectrace",
      replace: true,
      requirements: [root],
      links: [],
      flows: [],
    });

    expect(res.status).toBe(200);
    expect((await json(res)).data.requirements).toMatchObject({ deleted: 1 });
    const remaining = await db.select({ externalId: requirements.externalId }).from(requirements);
    expect(remaining.map((row) => row.externalId)).toEqual(["REQ-B"]);
  });
});
