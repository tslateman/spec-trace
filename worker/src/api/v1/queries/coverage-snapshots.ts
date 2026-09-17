import { desc, eq } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { coverageSnapshots } from "../../../db/schema";
import { isoformat } from "./time";

export type CoverageSnapshotRow = typeof coverageSnapshots.$inferSelect;

export function snapshotJson(row: CoverageSnapshotRow) {
  return {
    commit_sha: row.commitSha,
    git_branch: row.gitBranch,
    generated_at: isoformat(row.generatedAt),
    stored_at: isoformat(row.createdAt),
    specification_rate: row.specificationRate,
    structure_rate: row.structureRate,
    verification_rate: row.verificationRate,
    total: row.total,
    non_draft: row.nonDraft,
    passing: row.passing,
  };
}

export function newestSnapshot(db: Database, project: string) {
  return db.query.coverageSnapshots.findFirst({
    where: eq(coverageSnapshots.project, project),
    orderBy: [desc(coverageSnapshots.generatedAt), desc(coverageSnapshots.id)],
  });
}

export async function snapshotSeries(db: Database, project: string, limit: number): Promise<CoverageSnapshotRow[]> {
  const rows = await db
    .select()
    .from(coverageSnapshots)
    .where(eq(coverageSnapshots.project, project))
    .orderBy(desc(coverageSnapshots.generatedAt), desc(coverageSnapshots.id))
    .limit(limit);
  return rows.reverse();
}
