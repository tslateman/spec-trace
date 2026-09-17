import { eq, inArray, or } from "drizzle-orm";
import type { Database } from "../../../db/client";
import {
  inAppValidationResults,
  inAppValidations,
  requirementDependsOn,
  requirements,
  testRequirementLinks,
  testResultRequirements,
  verificationFlowRequirements,
  verificationFlowRuns,
  verificationFlowSteps,
  verificationFlows,
} from "../../../db/schema";
import { chunked, runBatch, type Statement, selectChunked } from "./batching";
import { storedNow } from "./time";
import { MaterializedPathTree, type Placement, type TreeNode } from "./tree";

export interface RequirementUpsert {
  external_id: string;
  title: string;
  source_file: string;
  description?: string;
  tags?: string[];
  priority?: string;
  status?: string;
  risk_level?: string | null;
  parent_id?: string | null;
  verification_method?: string | null;
  scope?: string;
  condition?: string;
  component?: string;
  timing?: string;
  response?: string;
  depends_on?: string[];
}

export interface TestLinkUpsert {
  test_nodeid: string;
  requirement_id: string;
}

export interface FlowStepDefinition {
  name: string;
  display_name: string;
  description?: string;
  type?: string;
  handler?: string;
  config?: Record<string, unknown>;
}

export interface FlowUpsert {
  name: string;
  display_name: string;
  steps: FlowStepDefinition[];
  description?: string;
  version?: number;
  source_file?: string;
  requirements?: string[];
}

export interface SpecPushBody {
  project: string;
  replace: boolean;
  requirements: RequirementUpsert[];
  links: TestLinkUpsert[];
  flows: FlowUpsert[];
}

export interface UpsertCounts {
  created: number;
  updated: number;
  deleted: number;
}

export interface Unresolved {
  kind: "parent_id" | "depends_on" | "link" | "flow";
  source: string;
  ref: string;
}

export interface SpecPushResult {
  project: string;
  requirements: UpsertCounts;
  links: UpsertCounts;
  flows: UpsertCounts;
  unresolved: Unresolved[];
}

export class InvalidRiskLevel extends Error {}

interface StoredNode extends TreeNode {
  id: number | undefined;
  project: string;
}

type Resolve = (externalId: string) => number | undefined;

const riskLevels = ["unclassified", "low", "medium", "high", "critical"];
const verificationMethods = ["unspecified", "test", "inapp", "both"];

export async function pushSpecs(db: Database, body: SpecPushBody): Promise<SpecPushResult> {
  const now = storedNow();
  const unresolved: Unresolved[] = [];
  const tree = new MaterializedPathTree<StoredNode>(await storedNodes(db));
  const requirementCounts = await syncRequirements(db, tree, body, now, unresolved);
  const resolve: Resolve = (externalId) => tree.get(externalId)?.id;
  await syncDependencies(db, body.requirements, resolve, unresolved);
  const linkCounts = await syncLinks(db, tree, body, resolve, now, unresolved);
  const flowCounts = await syncFlows(db, body, resolve, now, unresolved);
  return { project: body.project, requirements: requirementCounts, links: linkCounts, flows: flowCounts, unresolved };
}

async function storedNodes(db: Database): Promise<StoredNode[]> {
  return db
    .select({
      id: requirements.id,
      externalId: requirements.externalId,
      project: requirements.project,
      path: requirements.path,
      depth: requirements.depth,
      numchild: requirements.numchild,
    })
    .from(requirements);
}

async function syncRequirements(
  db: Database,
  tree: MaterializedPathTree<StoredNode>,
  body: SpecPushBody,
  now: string,
  unresolved: Unresolved[],
): Promise<UpsertCounts> {
  const snapshot = new Map(tree.all().map((node) => [node, placementOf(node)]));
  const payloadIds = new Set(body.requirements.map((upsert) => upsert.external_id));
  const deleted = body.replace ? await deleteOmittedRequirements(db, tree, body.project, payloadIds) : 0;
  const inserted: StoredNode[] = [];
  let updated = 0;
  for (const { upsert, parentId } of parentsFirst(body.requirements, tree, unresolved)) {
    const existing = tree.get(upsert.external_id);
    if (existing === undefined) {
      inserted.push(tree.insert({ id: undefined, externalId: upsert.external_id, project: body.project }, parentId));
      continue;
    }
    updated += 1;
    existing.project = body.project;
    const currentParent = tree.parentOf(existing)?.externalId ?? null;
    if (currentParent !== parentId) tree.move(existing.externalId, parentId);
  }
  await writeTree(db, tree, snapshot, body, inserted, now);
  return { created: inserted.length, updated, deleted };
}

function placementOf(node: StoredNode): Placement {
  return { path: node.path, depth: node.depth, numchild: node.numchild };
}

interface PlacedUpsert {
  upsert: RequirementUpsert;
  parentId: string | null;
}

function parentsFirst(
  upserts: RequirementUpsert[],
  tree: MaterializedPathTree<StoredNode>,
  unresolved: Unresolved[],
): PlacedUpsert[] {
  const inPayload = new Set(upserts.map((upsert) => upsert.external_id));
  const placed = new Set(
    tree
      .all()
      .map((node) => node.externalId)
      .filter((id) => !inPayload.has(id)),
  );
  const ordered: PlacedUpsert[] = [];
  let pending = upserts;
  while (pending.length > 0) {
    const ready = pending.filter((upsert) => upsert.parent_id == null || placed.has(upsert.parent_id));
    const batch = ready.length > 0 ? ready.map(withParent) : [orphaned(pending[0], unresolved)];
    for (const item of batch) {
      ordered.push(item);
      placed.add(item.upsert.external_id);
    }
    const taken = new Set(batch.map((item) => item.upsert));
    pending = pending.filter((upsert) => !taken.has(upsert));
  }
  return ordered;
}

function withParent(upsert: RequirementUpsert): PlacedUpsert {
  return { upsert, parentId: upsert.parent_id ?? null };
}

function orphaned(upsert: RequirementUpsert, unresolved: Unresolved[]): PlacedUpsert {
  unresolved.push({ kind: "parent_id", source: upsert.external_id, ref: upsert.parent_id as string });
  return { upsert, parentId: null };
}

async function deleteOmittedRequirements(
  db: Database,
  tree: MaterializedPathTree<StoredNode>,
  project: string,
  payloadIds: Set<string>,
): Promise<number> {
  const omitted = tree.all().filter((node) => node.project === project && !payloadIds.has(node.externalId));
  const removed: StoredNode[] = [];
  for (const node of omitted) {
    if (tree.get(node.externalId)) removed.push(...tree.remove(node.externalId));
  }
  const ids = removed.map((node) => node.id as number);
  const validationIds = (
    await selectChunked(ids, (chunk) =>
      db
        .select({ id: inAppValidations.id })
        .from(inAppValidations)
        .where(inArray(inAppValidations.requirementId, chunk)),
    )
  ).map((row) => row.id);
  await runBatch(db, [
    ...chunked(ids).map((chunk) =>
      db
        .delete(requirementDependsOn)
        .where(
          or(
            inArray(requirementDependsOn.fromRequirementId, chunk),
            inArray(requirementDependsOn.toRequirementId, chunk),
          ),
        ),
    ),
    ...chunked(ids).map((chunk) =>
      db.delete(testRequirementLinks).where(inArray(testRequirementLinks.requirementId, chunk)),
    ),
    ...chunked(ids).map((chunk) =>
      db.delete(testResultRequirements).where(inArray(testResultRequirements.requirementId, chunk)),
    ),
    ...chunked(validationIds).map((chunk) =>
      db.delete(inAppValidationResults).where(inArray(inAppValidationResults.validationId, chunk)),
    ),
    ...chunked(validationIds).map((chunk) => db.delete(inAppValidations).where(inArray(inAppValidations.id, chunk))),
    ...chunked(ids).map((chunk) =>
      db.delete(verificationFlowRequirements).where(inArray(verificationFlowRequirements.requirementId, chunk)),
    ),
    ...chunked(ids).map((chunk) => db.delete(requirements).where(inArray(requirements.id, chunk))),
  ]);
  return ids.length;
}

async function writeTree(
  db: Database,
  tree: MaterializedPathTree<StoredNode>,
  snapshot: Map<StoredNode, Placement>,
  body: SpecPushBody,
  inserted: StoredNode[],
  now: string,
): Promise<void> {
  const upsertOf = new Map(body.requirements.map((upsert) => [upsert.external_id, upsert]));
  const stored = tree.all().filter((node) => node.id !== undefined);
  const moved = stored.filter((node) => (snapshot.get(node) as Placement).path !== node.path);
  const statements: Statement[] = moved.map((node) =>
    db
      .update(requirements)
      .set({ path: `~${node.id}` })
      .where(eq(requirements.id, node.id as number)),
  );
  for (const node of stored) {
    const upsert = upsertOf.get(node.externalId);
    if (upsert === undefined && samePlacement(snapshot.get(node) as Placement, node)) continue;
    const fields = upsert ? { ...requirementFields(upsert), project: body.project, updatedAt: now } : {};
    statements.push(
      db
        .update(requirements)
        .set({ ...placementOf(node), ...fields })
        .where(eq(requirements.id, node.id as number)),
    );
  }
  for (const node of inserted) {
    statements.push(
      db
        .insert(requirements)
        .values({
          ...requirementFields(upsertOf.get(node.externalId) as RequirementUpsert),
          ...placementOf(node),
          externalId: node.externalId,
          project: body.project,
          createdAt: now,
          updatedAt: now,
          verificationStatus: "untested",
          sloStatus: "not_linked",
        })
        .returning({ id: requirements.id }),
    );
  }
  const results = await runBatch(db, statements);
  const insertResults = results.slice(results.length - inserted.length) as Array<Array<{ id: number }>>;
  inserted.forEach((node, index) => {
    node.id = insertResults[index][0].id;
  });
}

function samePlacement(before: Placement, node: StoredNode): boolean {
  return before.path === node.path && before.depth === node.depth && before.numchild === node.numchild;
}

function requirementFields(upsert: RequirementUpsert) {
  const structured = {
    scope: upsert.scope ?? "",
    condition: upsert.condition ?? "",
    component: upsert.component ?? "",
    timing: upsert.timing ?? "",
    response: upsert.response ?? "",
  };
  return {
    title: upsert.title,
    description: upsert.description ?? "",
    tags: upsert.tags ?? [],
    priority: upsert.priority ?? "",
    status: upsert.status ?? "draft",
    riskLevel: resolveRiskLevel(upsert),
    sourceFile: upsert.source_file,
    verificationMethod: normalizeVerificationMethod(upsert.verification_method),
    ...structured,
    structureCompleteness: structureCompleteness(Object.values(structured)),
  };
}

function resolveRiskLevel(upsert: RequirementUpsert): string {
  const value = upsert.risk_level;
  if (value == null) return "unclassified";
  if (!riskLevels.includes(value)) {
    throw new InvalidRiskLevel(
      `${upsert.source_file || "requirement data"}: risk_level '${value}' is not a RiskLevel. Use one of: ${riskLevels.join(", ")}`,
    );
  }
  return value;
}

function normalizeVerificationMethod(value: string | null | undefined): string {
  return value != null && verificationMethods.includes(value) ? value : "unspecified";
}

function structureCompleteness(fields: string[]): number {
  return fields.filter((field) => field.trim() !== "").length / fields.length;
}

async function syncDependencies(
  db: Database,
  upserts: RequirementUpsert[],
  resolve: Resolve,
  unresolved: Unresolved[],
): Promise<void> {
  const fromIds = upserts.map((upsert) => resolve(upsert.external_id) as number);
  const existing = await selectChunked(fromIds, (chunk) =>
    db
      .select({
        id: requirementDependsOn.id,
        from: requirementDependsOn.fromRequirementId,
        to: requirementDependsOn.toRequirementId,
      })
      .from(requirementDependsOn)
      .where(inArray(requirementDependsOn.fromRequirementId, chunk)),
  );
  const existingKeys = new Set(existing.map((edge) => `${edge.from}:${edge.to}`));
  const desired = new Set<string>();
  const inserts: Array<typeof requirementDependsOn.$inferInsert> = [];
  for (const upsert of upserts) {
    const from = resolve(upsert.external_id) as number;
    for (const ref of upsert.depends_on ?? []) {
      const to = resolve(ref);
      if (to === undefined) {
        unresolved.push({ kind: "depends_on", source: upsert.external_id, ref });
        continue;
      }
      desired.add(`${from}:${to}`);
      if (!existingKeys.has(`${from}:${to}`)) inserts.push({ fromRequirementId: from, toRequirementId: to });
    }
  }
  const stale = existing.filter((edge) => !desired.has(`${edge.from}:${edge.to}`)).map((edge) => edge.id);
  await runBatch(db, [
    ...chunked(stale).map((chunk) => db.delete(requirementDependsOn).where(inArray(requirementDependsOn.id, chunk))),
    ...chunked(inserts, 40).map((chunk) => db.insert(requirementDependsOn).values(chunk)),
  ]);
}

function linkKey(testNodeid: string, requirementId: number): string {
  return `${requirementId}\u0000${testNodeid}`;
}

async function syncLinks(
  db: Database,
  tree: MaterializedPathTree<StoredNode>,
  body: SpecPushBody,
  resolve: Resolve,
  now: string,
  unresolved: Unresolved[],
): Promise<UpsertCounts> {
  const projectIds = new Set(
    tree
      .all()
      .filter((node) => node.project === body.project)
      .map((node) => node.id as number),
  );
  const desired = new Map<string, { testNodeid: string; requirementId: number }>();
  for (const link of body.links) {
    const requirementId = resolve(link.requirement_id);
    if (requirementId === undefined) {
      unresolved.push({ kind: "link", source: link.test_nodeid, ref: link.requirement_id });
      continue;
    }
    desired.set(linkKey(link.test_nodeid, requirementId), { testNodeid: link.test_nodeid, requirementId });
  }
  const scopeIds = [...new Set([...projectIds, ...[...desired.values()].map((link) => link.requirementId)])];
  const existing = await selectChunked(scopeIds, (chunk) =>
    db
      .select({
        id: testRequirementLinks.id,
        testNodeid: testRequirementLinks.testNodeid,
        requirementId: testRequirementLinks.requirementId,
      })
      .from(testRequirementLinks)
      .where(inArray(testRequirementLinks.requirementId, chunk)),
  );
  const existingByKey = new Map(existing.map((link) => [linkKey(link.testNodeid, link.requirementId), link.id]));
  const created = [...desired.entries()].filter(([key]) => !existingByKey.has(key)).map(([, link]) => link);
  const updatedIds = [...desired.keys()]
    .filter((key) => existingByKey.has(key))
    .map((key) => existingByKey.get(key) as number);
  const deletedIds = body.replace
    ? existing
        .filter(
          (link) => projectIds.has(link.requirementId) && !desired.has(linkKey(link.testNodeid, link.requirementId)),
        )
        .map((link) => link.id)
    : [];
  const rows = created.map((link) => ({
    ...link,
    lastStatus: "unknown",
    lastRunAt: null,
    needsReview: true,
    reviewReason: "new link",
    createdAt: now,
    updatedAt: now,
  }));
  await runBatch(db, [
    ...chunked(deletedIds).map((chunk) =>
      db.delete(testRequirementLinks).where(inArray(testRequirementLinks.id, chunk)),
    ),
    ...chunked(updatedIds).map((chunk) =>
      db
        .update(testRequirementLinks)
        .set({ needsReview: false, reviewReason: "", updatedAt: now })
        .where(inArray(testRequirementLinks.id, chunk)),
    ),
    ...chunked(rows, 10).map((chunk) => db.insert(testRequirementLinks).values(chunk)),
  ]);
  return { created: created.length, updated: updatedIds.length, deleted: deletedIds.length };
}

async function syncFlows(
  db: Database,
  body: SpecPushBody,
  resolve: Resolve,
  now: string,
  unresolved: Unresolved[],
): Promise<UpsertCounts> {
  const stored = await db.select({ id: verificationFlows.id, name: verificationFlows.name }).from(verificationFlows);
  const idByName = new Map(stored.map((flow) => [flow.name, flow.id]));
  let created = 0;
  let updated = 0;
  for (const flow of body.flows) {
    const values = {
      displayName: flow.display_name,
      description: flow.description ?? "",
      steps: stepsWithMetadata(flow),
      version: flow.version ?? 1,
      syncedAt: now,
    };
    const id = idByName.get(flow.name);
    if (id === undefined) {
      const [row] = await db
        .insert(verificationFlows)
        .values({ name: flow.name, ...values })
        .returning({ id: verificationFlows.id });
      idByName.set(flow.name, row.id);
      created += 1;
    } else {
      await db.update(verificationFlows).set(values).where(eq(verificationFlows.id, id));
      updated += 1;
    }
  }
  await syncFlowRequirements(db, body.flows, idByName, resolve, unresolved);
  const payloadNames = new Set(body.flows.map((flow) => flow.name));
  const omitted = body.replace ? stored.filter((flow) => !payloadNames.has(flow.name)).map((flow) => flow.id) : [];
  await deleteFlows(db, omitted);
  return { created, updated, deleted: omitted.length };
}

function stepsWithMetadata(flow: FlowUpsert): unknown[] {
  const steps = flow.steps.map((step) => ({
    name: step.name,
    handler: step.handler ?? "",
    display_name: step.display_name,
    description: step.description ?? "",
    type: step.type ?? "handler",
    config: step.config ?? {},
  }));
  return [{ _metadata: { source_file: flow.source_file ?? "" } }, ...steps];
}

async function syncFlowRequirements(
  db: Database,
  flows: FlowUpsert[],
  idByName: Map<string, number>,
  resolve: Resolve,
  unresolved: Unresolved[],
): Promise<void> {
  const flowIds = flows.map((flow) => idByName.get(flow.name) as number);
  const existing = await selectChunked(flowIds, (chunk) =>
    db
      .select({
        id: verificationFlowRequirements.id,
        flowId: verificationFlowRequirements.verificationflowId,
        requirementId: verificationFlowRequirements.requirementId,
      })
      .from(verificationFlowRequirements)
      .where(inArray(verificationFlowRequirements.verificationflowId, chunk)),
  );
  const existingKeys = new Set(existing.map((row) => `${row.flowId}:${row.requirementId}`));
  const desired = new Set<string>();
  const inserts: Array<typeof verificationFlowRequirements.$inferInsert> = [];
  for (const flow of flows) {
    const flowId = idByName.get(flow.name) as number;
    for (const ref of flow.requirements ?? []) {
      const requirementId = resolve(ref);
      if (requirementId === undefined) {
        unresolved.push({ kind: "flow", source: flow.name, ref });
        continue;
      }
      desired.add(`${flowId}:${requirementId}`);
      if (!existingKeys.has(`${flowId}:${requirementId}`)) {
        inserts.push({ verificationflowId: flowId, requirementId });
      }
    }
  }
  const stale = existing.filter((row) => !desired.has(`${row.flowId}:${row.requirementId}`)).map((row) => row.id);
  await runBatch(db, [
    ...chunked(stale).map((chunk) =>
      db.delete(verificationFlowRequirements).where(inArray(verificationFlowRequirements.id, chunk)),
    ),
    ...chunked(inserts, 40).map((chunk) => db.insert(verificationFlowRequirements).values(chunk)),
  ]);
}

async function deleteFlows(db: Database, flowIds: number[]): Promise<void> {
  const runs = await selectChunked(flowIds, (chunk) =>
    db
      .select({ id: verificationFlowRuns.id })
      .from(verificationFlowRuns)
      .where(inArray(verificationFlowRuns.flowId, chunk)),
  );
  const runIds = runs.map((run) => run.id);
  await runBatch(db, [
    ...chunked(runIds).map((chunk) =>
      db.delete(verificationFlowSteps).where(inArray(verificationFlowSteps.flowRunId, chunk)),
    ),
    ...chunked(runIds).map((chunk) => db.delete(verificationFlowRuns).where(inArray(verificationFlowRuns.id, chunk))),
    ...chunked(flowIds).map((chunk) =>
      db.delete(verificationFlowRequirements).where(inArray(verificationFlowRequirements.verificationflowId, chunk)),
    ),
    ...chunked(flowIds).map((chunk) => db.delete(verificationFlows).where(inArray(verificationFlows.id, chunk))),
  ]);
}
