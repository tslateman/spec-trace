import type { BatchItem } from "drizzle-orm/batch";
import type { Database } from "../../../db/client";

export type Statement = BatchItem<"sqlite">;

export const parameterLimit = 90;

export function chunked<T>(items: T[], size = parameterLimit): T[][] {
  const chunks: T[][] = [];
  for (let start = 0; start < items.length; start += size) chunks.push(items.slice(start, start + size));
  return chunks;
}

export async function selectChunked<K, T>(keys: K[], query: (chunk: K[]) => Promise<T[]>): Promise<T[]> {
  const rows: T[] = [];
  for (const chunk of chunked(keys)) rows.push(...(await query(chunk)));
  return rows;
}

export async function runBatch(db: Database, statements: Statement[]): Promise<unknown[]> {
  if (statements.length === 0) return [];
  return db.batch(statements as [Statement, ...Statement[]]);
}
