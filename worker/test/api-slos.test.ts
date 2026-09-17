import { SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { requirements, sloRequirements, slos } from "../src/db/schema";
import { db, headers, resetDatabase } from "./fixtures";

beforeEach(async () => {
  await db.delete(sloRequirements);
  await db.delete(slos);
  await resetDatabase();
});

function put(body: unknown) {
  return SELF.fetch("http://spectrace/api/v1/slos/", { method: "PUT", headers, body: JSON.stringify(body) });
}

async function data(res: Response) {
  return ((await res.json()) as { data: { created: number; updated: number; unresolved: string[] } }).data;
}

const definition = {
  name: "checkout-availability",
  display_name: "Checkout availability",
  description: "Checkout answers",
  service: "checkout",
  target: 99.9,
  time_window: "28d",
  budgeting_method: "Occurrences",
  source_file: "slos/checkout.yaml",
};

async function seedRequirement(externalId: string) {
  const now = new Date().toISOString();
  const [row] = await db
    .insert(requirements)
    .values({
      externalId,
      project: "spectrace",
      title: externalId,
      description: "",
      sourceFile: "specs/a.md",
      path: externalId,
      depth: 1,
      numchild: 0,
      tags: [],
      priority: "",
      status: "active",
      verificationMethod: "unspecified",
      verificationStatus: "untested",
      sloStatus: "not_linked",
      riskLevel: "unclassified",
      structureCompleteness: 0,
      scope: "",
      condition: "",
      component: "",
      timing: "",
      response: "",
      createdAt: now,
      updatedAt: now,
    })
    .returning({ id: requirements.id });
  return row.id;
}

describe("PUT /api/v1/slos/", () => {
  it("creates an SLO and starts it unlinked", async () => {
    const result = await data(await put({ slos: [definition] }));

    expect(result).toEqual({ created: 1, updated: 0, unresolved: [] });
    const stored = await db.query.slos.findFirst({ where: eq(slos.name, definition.name) });
    expect(stored?.target).toBe(99.9);
    expect(stored?.status).toBe("not_linked");
    expect(stored?.currentValue).toBeNull();
  });

  it("links the requirements it names and reports the ones it cannot resolve", async () => {
    const requirementId = await seedRequirement("REQ-CHECKOUT-001");

    const result = await data(
      await put({ slos: [{ ...definition, requirement_ids: ["REQ-CHECKOUT-001", "REQ-GHOST-999"] }] }),
    );

    expect(result.unresolved).toEqual(["REQ-GHOST-999"]);
    const links = await db.select().from(sloRequirements);
    expect(links).toHaveLength(1);
    expect(links[0].requirementId).toBe(requirementId);
  });

  it("keeps the status an observability push wrote when the definition changes", async () => {
    await put({ slos: [definition] });
    await db
      .update(slos)
      .set({ status: "breached", currentValue: 98.1, errorBudgetRemaining: -0.4, lastUpdated: "2026-09-16 05:00:00" })
      .where(eq(slos.name, definition.name));

    const result = await data(await put({ slos: [{ ...definition, target: 99.95 }] }));

    expect(result).toEqual({ created: 0, updated: 1, unresolved: [] });
    const stored = await db.query.slos.findFirst({ where: eq(slos.name, definition.name) });
    expect(stored?.target).toBe(99.95);
    expect(stored?.status).toBe("breached");
    expect(stored?.currentValue).toBe(98.1);
    expect(stored?.errorBudgetRemaining).toBe(-0.4);
  });

  it("replaces the link set rather than adding to it", async () => {
    await seedRequirement("REQ-CHECKOUT-001");
    await seedRequirement("REQ-CHECKOUT-002");
    await put({ slos: [{ ...definition, requirement_ids: ["REQ-CHECKOUT-001", "REQ-CHECKOUT-002"] }] });

    await put({ slos: [{ ...definition, requirement_ids: ["REQ-CHECKOUT-002"] }] });

    const links = await db.select().from(sloRequirements);
    expect(links).toHaveLength(1);
  });

  it("recomputes the linked requirement's slo_status", async () => {
    await seedRequirement("REQ-CHECKOUT-001");
    await put({ slos: [definition] });
    await db.update(slos).set({ status: "breached" }).where(eq(slos.name, definition.name));

    await put({ slos: [{ ...definition, requirement_ids: ["REQ-CHECKOUT-001"] }] });

    const stored = await db.query.requirements.findFirst({
      where: eq(requirements.externalId, "REQ-CHECKOUT-001"),
    });
    expect(stored?.sloStatus).toBe("breached");
  });

  it("refuses a payload whose slos are not a list of named documents", async () => {
    const res = await put({ slos: [{ display_name: "nameless" }] });

    expect(res.status).toBe(400);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("validation_error");
  });
});
