import { asc, count, desc, eq, sql } from "drizzle-orm";
import { Hono } from "hono";
import { database } from "../../db/client";
import {
  driftReports,
  impactReports,
  inAppValidationResults,
  inAppValidations,
  requirements,
  testRequirementLinks,
} from "../../db/schema";
import type { Env } from "../../env";
import { failure, success } from "../envelope";
import { pageMeta, pageRequest, positiveInt } from "../pagination";
import { snapshotJson, snapshotSeries } from "./queries/coverage-snapshots";
import {
  AmbiguousProjectError,
  ancestorsOf,
  type DescendantRollup,
  dependencyExternalIds,
  descendantRollups,
  emptyRollup,
  externalIdsInProject,
  projectNames,
  requirementByExternalId,
  requirementPage,
  resolveProject,
} from "./queries/requirements";
import { latestTestRun, nodeidsInRun } from "./queries/test-runs";
import { isoformat } from "./queries/time";
import { stepsPassed, type ValidationStep } from "./queries/validation-runs";

export const specs = new Hono<{ Bindings: Env }>();

const fretFields = ["scope", "condition", "component", "timing", "response"] as const;

function tagList(raw: string | undefined): string[] | undefined {
  const tags = (raw ?? "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  return tags.length > 0 ? tags : undefined;
}

specs.get("/", async (c) => {
  const db = database(c.env.DB);
  let project: string;
  try {
    project = resolveProject(c.req.query("project"), await projectNames(db), c.env.SPECTRACE_PROJECT);
  } catch (error) {
    if (!(error instanceof AmbiguousProjectError)) throw error;
    return failure(c, `${error.message} Pass ?project=`, "ambiguous_project", 400, { projects: error.projects });
  }

  const request = pageRequest(c);
  const parentId = c.req.query("parent_id");
  const { rows, total } = await requirementPage(
    db,
    {
      project,
      status: c.req.query("status"),
      verificationStatus: c.req.query("verification_status"),
      riskLevel: c.req.query("risk_level"),
      tags: tagList(c.req.query("tags")),
      parentId,
      maxDepth: positiveInt(c.req.query("max_depth"), 0, MAX_DEPTH, "max_depth"),
      attention: c.req.query("attention") === "1",
    },
    request.page,
    request.perPage,
  );
  const rollups = await descendantRollups(db, project, rows);
  const scope = parentId ? await scopeOf(db, parentId) : undefined;

  return success(
    c,
    {
      project,
      ...(scope ? { scope } : {}),
      requirements: rows.map((row) => ({
        external_id: row.externalId,
        title: row.title,
        description: row.description,
        path: row.path,
        depth: row.depth,
        numchild: row.numchild,
        tags: row.tags,
        priority: row.priority,
        status: row.status,
        verification_status: row.verificationStatus,
        verification_method: row.verificationMethod,
        risk_level: row.riskLevel,
        source_file: row.sourceFile,
        descendants: descendantSummary(rollups.get(row.id) ?? emptyRollup),
      })),
    },
    pageMeta(request, total),
  );
});

const MAX_DEPTH = 100;

async function scopeOf(db: ReturnType<typeof database>, externalId: string) {
  const requirement = await requirementByExternalId(db, externalId);
  if (!requirement) return undefined;
  const ancestors = await ancestorsOf(db, requirement);
  return {
    external_id: requirement.externalId,
    title: requirement.title,
    ancestors: ancestors.map((row) => ({ external_id: row.externalId, title: row.title })),
  };
}

function descendantSummary(rollup: DescendantRollup) {
  return {
    total: rollup.total,
    passing: rollup.passing,
    failing: rollup.failing,
    untested: rollup.untested,
    highest_risk: rollup.highestRisk,
  };
}

specs.get("/coverage", async (c) => {
  const db = database(c.env.DB);
  let project: string;
  try {
    project = resolveProject(c.req.query("project"), await projectNames(db), c.env.SPECTRACE_PROJECT);
  } catch (error) {
    if (!(error instanceof AmbiguousProjectError)) throw error;
    return failure(c, `${error.message} Pass ?project=`, "ambiguous_project", 400, { projects: error.projects });
  }

  const statusCount = (column: typeof requirements.verificationStatus, value: string) =>
    count(sql`case when ${column} = ${value} then 1 end`);
  const [metrics] = await db
    .select({
      total: count(),
      nonDraft: count(sql`case when ${requirements.status} != 'draft' then 1 end`),
      passing: statusCount(requirements.verificationStatus, "passing"),
      failing: statusCount(requirements.verificationStatus, "failing"),
      untested: statusCount(requirements.verificationStatus, "untested"),
    })
    .from(requirements)
    .where(eq(requirements.project, project));

  const stale = await staleRequirementIds(db, project);

  return success(c, {
    project,
    metrics: {
      total: metrics.total,
      non_draft: metrics.nonDraft,
      passing: metrics.passing,
      failing: metrics.failing,
      untested: metrics.untested,
      stale: stale.length,
    },
    stale_requirements: stale,
  });
});

const MAX_TREND_POINTS = 500;

specs.get("/coverage/trend", async (c) => {
  const db = database(c.env.DB);
  let project: string;
  try {
    project = resolveProject(c.req.query("project"), await projectNames(db), c.env.SPECTRACE_PROJECT);
  } catch (error) {
    if (!(error instanceof AmbiguousProjectError)) throw error;
    return failure(c, `${error.message} Pass ?project=`, "ambiguous_project", 400, { projects: error.projects });
  }

  const limit = positiveInt(c.req.query("limit"), 100, MAX_TREND_POINTS, "limit");
  const rows = await snapshotSeries(db, project, limit);
  return success(c, { project, snapshots: rows.map(snapshotJson) });
});

type DriftPayload = { warnings?: { type: string; affected_requirements?: string[] }[] };

async function staleRequirementIds(db: ReturnType<typeof database>, project: string): Promise<string[]> {
  const latestRun = await latestTestRun(db);
  if (!latestRun) return [];
  const recent = await nodeidsInRun(db, latestRun.id);
  const links = await db
    .select({ nodeid: testRequirementLinks.testNodeid, externalId: requirements.externalId })
    .from(testRequirementLinks)
    .innerJoin(requirements, eq(requirements.id, testRequirementLinks.requirementId));
  const candidates = new Set(links.filter((link) => !recent.has(link.nodeid)).map((link) => link.externalId));
  const drift = await newestDriftReport(db, project);
  for (const warning of (drift?.payload as DriftPayload | undefined)?.warnings ?? []) {
    if (warning.type !== "spec_drift") continue;
    for (const externalId of warning.affected_requirements ?? []) candidates.add(externalId);
  }
  return (await externalIdsInProject(db, project, candidates)).sort();
}

function newestDriftReport(db: ReturnType<typeof database>, project: string) {
  return db.query.driftReports.findFirst({
    where: eq(driftReports.project, project),
    orderBy: [desc(driftReports.createdAt), desc(driftReports.id)],
  });
}

specs.get("/drift", async (c) => {
  const project = c.req.query("project") ?? c.env.SPECTRACE_PROJECT;
  const report = await newestDriftReport(database(c.env.DB), project);
  if (!report) return failure(c, `No drift report for project ${project}`, "not_found", 404);
  return success(c, report.payload);
});

specs.get("/impact", async (c) => {
  const project = c.req.query("project") ?? c.env.SPECTRACE_PROJECT;
  const report = await database(c.env.DB).query.impactReports.findFirst({
    where: eq(impactReports.project, project),
    orderBy: [desc(impactReports.createdAt), desc(impactReports.id)],
  });
  if (!report) return failure(c, `No impact report for project ${project}`, "not_found", 404);
  return success(c, report.payload);
});

specs.get("/:externalId/context", async (c) => {
  const db = database(c.env.DB);
  const externalId = c.req.param("externalId");
  const requirement = await requirementByExternalId(db, externalId);
  if (!requirement) return failure(c, `Spec not found for ${externalId}`, "not_found", 404);

  const links = await db
    .select({ testNodeid: testRequirementLinks.testNodeid, lastStatus: testRequirementLinks.lastStatus })
    .from(testRequirementLinks)
    .where(eq(testRequirementLinks.requirementId, requirement.id))
    .orderBy(asc(testRequirementLinks.testNodeid));
  const { dependsOn, dependedBy } = await dependencyExternalIds(db, requirement.id);

  const fret = Object.fromEntries(
    fretFields.filter((field) => requirement[field]).map((field) => [field, requirement[field]]),
  );

  return success(c, {
    external_id: requirement.externalId,
    title: requirement.title,
    description: requirement.description,
    tags: requirement.tags,
    status: requirement.status,
    verification_status: requirement.verificationStatus,
    priority: requirement.priority,
    test_results: links.map((link) => ({ test_nodeid: link.testNodeid, last_status: link.lastStatus })),
    depends_on: dependsOn,
    depended_by: dependedBy,
    ...(Object.keys(fret).length ? { fret } : {}),
  });
});

specs.get("/:externalId/status", async (c) => {
  const db = database(c.env.DB);
  const externalId = c.req.param("externalId");
  const requirement = await requirementByExternalId(db, externalId);
  if (!requirement) return failure(c, `Requirement ${externalId} not found`, "not_found", 404);

  const validation = await db.query.inAppValidations.findFirst({
    where: eq(inAppValidations.requirementId, requirement.id),
    orderBy: [asc(inAppValidations.name), asc(inAppValidations.id)],
  });
  const data: Record<string, unknown> = {
    external_id: requirement.externalId,
    title: requirement.title,
    verification_status: requirement.verificationStatus,
    last_checked: null,
    latest_result: null,
    regression: { is_regression: false },
  };
  if (!validation) return success(c, data);

  const [latest, previous] = await db
    .select()
    .from(inAppValidationResults)
    .where(eq(inAppValidationResults.validationId, validation.id))
    .orderBy(desc(inAppValidationResults.checkedAt), asc(inAppValidationResults.id))
    .limit(2);
  if (latest) {
    const steps = latest.steps as ValidationStep[];
    data.last_checked = isoformat(latest.checkedAt);
    data.latest_result = {
      status: latest.status,
      message: latest.message,
      checked_at: isoformat(latest.checkedAt),
      steps_passed: stepsPassed(steps),
      steps_failed: steps.length - stepsPassed(steps),
    };
  }
  if (latest && previous) {
    const isRegression = previous.status === "success" && latest.status === "failure";
    data.regression = {
      is_regression: isRegression,
      previous_status: previous.status,
      regressed_at: isRegression ? isoformat(latest.checkedAt) : null,
    };
  }
  return success(c, data);
});
