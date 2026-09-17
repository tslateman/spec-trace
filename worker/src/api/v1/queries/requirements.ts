import {
  and,
  asc,
  count,
  eq,
  exists,
  gt,
  inArray,
  like,
  lte,
  max,
  ne,
  not,
  notExists,
  or,
  type SQL,
  sql,
} from "drizzle-orm";
import { alias } from "drizzle-orm/sqlite-core";
import type { Database } from "../../../db/client";
import { requirementDependsOn, requirements } from "../../../db/schema";
import { selectChunked } from "./batching";
import { parentPathOf } from "./tree";

export type Requirement = typeof requirements.$inferSelect;

export function requirementByExternalId(db: Database, externalId: string) {
  return db.query.requirements.findFirst({ where: eq(requirements.externalId, externalId) });
}

export async function requirementsByExternalId(db: Database, externalIds: string[]): Promise<Map<string, Requirement>> {
  const rows = await selectChunked(externalIds, (chunk) =>
    db.select().from(requirements).where(inArray(requirements.externalId, chunk)),
  );
  return new Map(rows.map((row) => [row.externalId, row]));
}

export function requirementsByPath(db: Database) {
  return db.select().from(requirements).orderBy(asc(requirements.path));
}

export type RequirementFilters = {
  project: string;
  status?: string;
  verificationStatus?: string;
  riskLevel?: string;
  tags?: string[];
  parentId?: string;
  maxDepth?: number;
  attention?: boolean;
};

export type DescendantRollup = {
  total: number;
  passing: number;
  failing: number;
  untested: number;
  highestRisk: string;
};

const RISK_RANKS = ["unclassified", "low", "medium", "high", "critical"];

export const emptyRollup: DescendantRollup = {
  total: 0,
  passing: 0,
  failing: 0,
  untested: 0,
  highestRisk: RISK_RANKS[0],
};

const escapeLike = (value: string) => value.replace(/[\\%_]/g, (char) => `\\${char}`);

function groupingParentWhoseDescendantsAllPass(db: Database): SQL {
  const descendant = alias(requirements, "attention_descendant");
  const descendantsOfRow = (...narrowing: SQL[]) =>
    db
      .select({ present: sql`1` })
      .from(descendant)
      .where(
        and(
          sql`${descendant.path} like ${requirements.path} || '%'`,
          ne(descendant.path, requirements.path),
          eq(descendant.project, requirements.project),
          ...narrowing,
        ),
      );
  return and(
    eq(requirements.verificationStatus, "untested"),
    exists(descendantsOfRow()),
    notExists(descendantsOfRow(ne(descendant.verificationStatus, "passing"))),
  ) as SQL;
}

function needsAttention(db: Database): SQL {
  return and(ne(requirements.verificationStatus, "passing"), not(groupingParentWhoseDescendantsAllPass(db))) as SQL;
}

async function requirementWhere(db: Database, filters: RequirementFilters): Promise<SQL | undefined> {
  const conditions: SQL[] = [eq(requirements.project, filters.project)];
  if (filters.status) conditions.push(eq(requirements.status, filters.status));
  if (filters.verificationStatus) conditions.push(eq(requirements.verificationStatus, filters.verificationStatus));
  if (filters.riskLevel) conditions.push(eq(requirements.riskLevel, filters.riskLevel));
  if (filters.attention) conditions.push(needsAttention(db));
  if (filters.tags?.length) {
    conditions.push(
      or(...filters.tags.map((tag) => sql`${requirements.tags} like ${`%${escapeLike(tag)}%`} escape '\\'`)) as SQL,
    );
  }
  let scopeDepth = 0;
  if (filters.parentId) {
    const parent = await db.query.requirements.findFirst({
      columns: { path: true, depth: true },
      where: eq(requirements.externalId, filters.parentId),
    });
    if (!parent) return sql`0 = 1`;
    conditions.push(like(requirements.path, `${parent.path}%`), gt(requirements.depth, parent.depth));
    scopeDepth = parent.depth;
  }
  if (filters.maxDepth) conditions.push(lte(requirements.depth, scopeDepth + filters.maxDepth));
  return and(...conditions);
}

export async function descendantRollups(
  db: Database,
  project: string,
  parents: Pick<Requirement, "id" | "numchild">[],
): Promise<Map<number, DescendantRollup>> {
  const ids = parents.filter((row) => row.numchild > 0).map((row) => row.id);
  const parent = alias(requirements, "parent");
  const descendant = alias(requirements, "descendant");
  const statusCount = (value: string) => count(sql`case when ${descendant.verificationStatus} = ${value} then 1 end`);
  const riskRank = sql<number>`case ${descendant.riskLevel} ${sql.join(
    RISK_RANKS.map((level, rank) => sql`when ${level} then ${rank}`),
    sql` `,
  )} else 0 end`;
  const rows = await selectChunked(ids, (chunk) =>
    db
      .select({
        id: parent.id,
        total: count(descendant.id),
        passing: statusCount("passing"),
        failing: statusCount("failing"),
        untested: statusCount("untested"),
        riskRank: sql<number>`coalesce(${max(riskRank)}, 0)`,
      })
      .from(parent)
      .innerJoin(
        descendant,
        and(
          sql`${descendant.path} like ${parent.path} || '%'`,
          ne(descendant.path, parent.path),
          eq(descendant.project, project),
        ),
      )
      .where(inArray(parent.id, chunk))
      .groupBy(parent.id),
  );
  return new Map(
    rows.map((row) => [
      row.id,
      {
        total: row.total,
        passing: row.passing,
        failing: row.failing,
        untested: row.untested,
        highestRisk: RISK_RANKS[row.riskRank],
      },
    ]),
  );
}

export async function requirementPage(db: Database, filters: RequirementFilters, page: number, perPage: number) {
  const where = await requirementWhere(db, filters);
  const [{ total }] = await db.select({ total: count() }).from(requirements).where(where);
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const currentPage = Math.min(page, totalPages);
  const rows = await db
    .select()
    .from(requirements)
    .where(where)
    .orderBy(asc(requirements.path))
    .limit(perPage)
    .offset((currentPage - 1) * perPage);
  return { rows, total, totalPages, page: currentPage };
}

export async function projectNames(db: Database): Promise<string[]> {
  const rows = await db
    .selectDistinct({ project: requirements.project })
    .from(requirements)
    .orderBy(asc(requirements.project));
  return rows.map((row) => row.project);
}

export class AmbiguousProjectError extends Error {
  constructor(readonly projects: string[]) {
    super(`The database holds requirements for several projects (${projects.join(", ")}). Name one to report on.`);
  }
}

export function resolveProject(requested: string | undefined, stored: string[], installed: string): string {
  if (requested) return requested;
  if (stored.includes(installed)) return installed;
  if (stored.length === 1) return stored[0];
  if (stored.length === 0) return installed;
  throw new AmbiguousProjectError([...stored].sort());
}

export async function dependencyExternalIds(db: Database, requirementId: number) {
  const dependsOn = await db
    .select({ externalId: requirements.externalId })
    .from(requirementDependsOn)
    .innerJoin(requirements, eq(requirements.id, requirementDependsOn.toRequirementId))
    .where(eq(requirementDependsOn.fromRequirementId, requirementId))
    .orderBy(asc(requirements.externalId));
  const dependedBy = await db
    .select({ externalId: requirements.externalId })
    .from(requirementDependsOn)
    .innerJoin(requirements, eq(requirements.id, requirementDependsOn.fromRequirementId))
    .where(eq(requirementDependsOn.toRequirementId, requirementId))
    .orderBy(asc(requirements.externalId));
  return {
    dependsOn: dependsOn.map((row) => row.externalId),
    dependedBy: dependedBy.map((row) => row.externalId),
  };
}

export async function externalIdsInProject(db: Database, project: string, candidates: Iterable<string>) {
  const ids = [...candidates];
  if (ids.length === 0) return [];
  const rows = await db
    .select({ externalId: requirements.externalId })
    .from(requirements)
    .where(and(eq(requirements.project, project), inArray(requirements.externalId, ids)));
  return rows.map((row) => row.externalId);
}

export async function ancestorsOf(db: Database, requirement: Pick<Requirement, "path">) {
  const paths: string[] = [];
  for (let path = parentPathOf(requirement.path); path; path = parentPathOf(path)) paths.push(path);
  if (paths.length === 0) return [];
  return db
    .select({ externalId: requirements.externalId, title: requirements.title })
    .from(requirements)
    .where(inArray(requirements.path, paths))
    .orderBy(asc(requirements.depth));
}
