import { asc, eq, inArray } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { agentTaskRequirements, agentTasks, requirements, testRequirementLinks } from "../../../db/schema";
import { latestTestRun, nodeidsInRun } from "./test-runs";
import { isoformat } from "./time";
import { parentPathOf } from "./tree";

const fretFields = ["scope", "condition", "component", "timing", "response"] as const;

export interface DriftIssue {
  type: string;
  id: string;
  message: string;
  [detail: string]: unknown;
}

export interface DriftSection {
  errors: DriftIssue[];
  warnings: DriftIssue[];
  summary: { items_checked: number; errors: number; warnings: number };
}

function section(errors: DriftIssue[], warnings: DriftIssue[], itemsChecked: number): DriftSection {
  return {
    errors,
    warnings,
    summary: { items_checked: itemsChecked, errors: errors.length, warnings: warnings.length },
  };
}

export async function staleLinks(db: Database): Promise<DriftSection> {
  const run = await latestTestRun(db);
  if (!run) return section([], [], 0);

  const ran = await nodeidsInRun(db, run.id);
  const links = await db
    .select({
      testNodeid: testRequirementLinks.testNodeid,
      lastStatus: testRequirementLinks.lastStatus,
      lastRunAt: testRequirementLinks.lastRunAt,
      requirementExternalId: requirements.externalId,
    })
    .from(testRequirementLinks)
    .innerJoin(requirements, eq(testRequirementLinks.requirementId, requirements.id))
    .orderBy(asc(testRequirementLinks.testNodeid));

  const errors = links
    .filter((link) => !ran.has(link.testNodeid))
    .map((link) => ({
      type: "stale_link",
      id: `${link.testNodeid}:${link.requirementExternalId}`,
      message: "Link references test not in latest run",
      test_nodeid: link.testNodeid,
      requirement_id: link.requirementExternalId,
      last_status: link.lastStatus,
      last_run_at: link.lastRunAt === null ? null : isoformat(link.lastRunAt),
    }));
  return section(errors, [], links.length);
}

export async function orphanRequirements(db: Database): Promise<DriftSection> {
  const active = await db
    .select({
      id: requirements.id,
      externalId: requirements.externalId,
      title: requirements.title,
      sourceFile: requirements.sourceFile,
      numchild: requirements.numchild,
    })
    .from(requirements)
    .where(eq(requirements.status, "active"))
    .orderBy(asc(requirements.externalId));

  const leaves = active.filter((requirement) => requirement.numchild === 0);
  const linked = await linkedRequirementIds(
    db,
    leaves.map((leaf) => leaf.id),
  );

  const warnings = leaves
    .filter((leaf) => !linked.has(leaf.id))
    .map((leaf) => ({
      type: "orphan_requirement",
      id: leaf.externalId,
      message: "Active requirement has no test coverage and no children",
      title: leaf.title,
      source_file: leaf.sourceFile,
    }));
  return section([], warnings, active.length);
}

async function linkedRequirementIds(db: Database, requirementIds: number[]): Promise<Set<number>> {
  if (requirementIds.length === 0) return new Set();
  const rows = await db
    .selectDistinct({ requirementId: testRequirementLinks.requirementId })
    .from(testRequirementLinks)
    .where(inArray(testRequirementLinks.requirementId, requirementIds));
  return new Set(rows.map((row) => row.requirementId));
}

async function treeOf(db: Database, requirement: { id: number; path: string; numchild: number }) {
  const parentPath = parentPathOf(requirement.path);
  const kin = await db
    .select({ externalId: requirements.externalId, title: requirements.title, path: requirements.path })
    .from(requirements)
    .orderBy(asc(requirements.externalId));

  const tree: Record<string, unknown> = {};
  const parent = parentPath === "" ? undefined : kin.find((node) => node.path === parentPath);
  if (parent) tree.parent = { external_id: parent.externalId, title: parent.title };

  const children = kin.filter((node) => node.path !== requirement.path && parentPathOf(node.path) === requirement.path);
  if (children.length > 0) {
    tree.children = children.map((child) => ({ external_id: child.externalId, title: child.title }));
  }
  return tree;
}

export async function taskContext(db: Database, taskExternalId: string) {
  const task = await db.query.agentTasks.findFirst({ where: eq(agentTasks.externalId, taskExternalId) });
  if (!task) return null;

  const linked = await db
    .select({
      id: requirements.id,
      path: requirements.path,
      numchild: requirements.numchild,
      externalId: requirements.externalId,
      title: requirements.title,
      description: requirements.description,
      verificationStatus: requirements.verificationStatus,
      priority: requirements.priority,
      tags: requirements.tags,
      sourceFile: requirements.sourceFile,
      scope: requirements.scope,
      condition: requirements.condition,
      component: requirements.component,
      timing: requirements.timing,
      response: requirements.response,
    })
    .from(agentTaskRequirements)
    .innerJoin(requirements, eq(agentTaskRequirements.requirementId, requirements.id))
    .where(eq(agentTaskRequirements.agenttaskId, task.id))
    .orderBy(asc(requirements.externalId));

  const bundled = [];
  for (const requirement of linked) {
    const links = await db
      .select({ testNodeid: testRequirementLinks.testNodeid, lastStatus: testRequirementLinks.lastStatus })
      .from(testRequirementLinks)
      .where(eq(testRequirementLinks.requirementId, requirement.id))
      .orderBy(asc(testRequirementLinks.testNodeid));
    const fret = Object.fromEntries(
      fretFields.filter((field) => requirement[field]).map((field) => [field, requirement[field]]),
    );

    bundled.push({
      external_id: requirement.externalId,
      title: requirement.title,
      description: requirement.description,
      verification_status: requirement.verificationStatus,
      priority: requirement.priority,
      tags: requirement.tags,
      source_file: requirement.sourceFile,
      test_results: links.map((link) => ({ test_nodeid: link.testNodeid, last_status: link.lastStatus })),
      tree: await treeOf(db, requirement),
      ...(Object.keys(fret).length ? { fret } : {}),
    });
  }

  return {
    task_id: task.externalId,
    title: task.title,
    description: task.description,
    status: task.status,
    done_when: task.doneWhen,
    scope_in: task.scopeIn,
    scope_out: task.scopeOut,
    spec_ref: task.specRef,
    requirements: bundled,
    drift: {
      stale_links: await staleLinks(db),
      orphan_requirements: await orphanRequirements(db),
    },
  };
}
