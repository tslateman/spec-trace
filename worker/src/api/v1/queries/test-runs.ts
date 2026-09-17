import { count, desc, eq, sql } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { testResults, testRuns } from "../../../db/schema";

export function latestTestRun(db: Database) {
  return db.query.testRuns.findFirst({ orderBy: [desc(testRuns.importedAt), desc(testRuns.id)] });
}

export async function testRunCounts(db: Database, runId: number) {
  const statusCount = (status: string) => count(sql`case when ${testResults.status} = ${status} then 1 end`);
  const [row] = await db
    .select({
      total: count(),
      passed: statusCount("passed"),
      failed: statusCount("failed"),
      errors: statusCount("error"),
      skipped: statusCount("skipped"),
    })
    .from(testResults)
    .where(eq(testResults.testRunId, runId));
  return row;
}

export async function nodeidsInRun(db: Database, runId: number): Promise<Set<string>> {
  const rows = await db
    .select({ nodeid: testResults.testNodeid })
    .from(testResults)
    .where(eq(testResults.testRunId, runId));
  return new Set(rows.map((row) => row.nodeid));
}
