import { eq, inArray } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { requirements, sloRequirements, slos } from "../../../db/schema";
import { storedNow } from "./time";

export interface SloUpsert {
  name: string;
  display_name?: string;
  description?: string;
  service?: string;
  target?: number | null;
  time_window?: string;
  budgeting_method?: string;
  source_file: string;
  requirement_ids?: string[];
}

export interface SloPushResult {
  created: number;
  updated: number;
  unresolved: string[];
}

const UNLINKED = "not_linked";

function definition(upsert: SloUpsert) {
  return {
    displayName: upsert.display_name ?? upsert.name,
    description: upsert.description ?? "",
    service: upsert.service ?? "",
    target: upsert.target ?? null,
    timeWindow: upsert.time_window ?? "",
    budgetingMethod: upsert.budgeting_method ?? "",
    sourceFile: upsert.source_file,
  };
}

export async function pushSlos(db: Database, payload: SloUpsert[]): Promise<SloPushResult> {
  const named = [...new Set(payload.flatMap((upsert) => upsert.requirement_ids ?? []))];
  const resolved = new Map<string, number>();
  if (named.length > 0) {
    const rows = await db
      .select({ id: requirements.id, externalId: requirements.externalId })
      .from(requirements)
      .where(inArray(requirements.externalId, named));
    for (const row of rows) resolved.set(row.externalId, row.id);
  }

  let created = 0;
  let updated = 0;
  for (const upsert of payload) {
    const now = storedNow();
    const existing = await db.query.slos.findFirst({ where: eq(slos.name, upsert.name) });
    let sloId: number;
    if (existing) {
      await db
        .update(slos)
        .set({ ...definition(upsert), updatedAt: now })
        .where(eq(slos.id, existing.id));
      sloId = existing.id;
      updated += 1;
    } else {
      const [row] = await db
        .insert(slos)
        .values({
          name: upsert.name,
          ...definition(upsert),
          status: UNLINKED,
          currentValue: null,
          errorBudgetRemaining: null,
          lastUpdated: null,
          createdAt: now,
          updatedAt: now,
        })
        .returning({ id: slos.id });
      sloId = row.id;
      created += 1;
    }

    await db.delete(sloRequirements).where(eq(sloRequirements.sloId, sloId));
    const links = (upsert.requirement_ids ?? [])
      .map((externalId) => resolved.get(externalId))
      .filter((id): id is number => id !== undefined)
      .map((requirementId) => ({ sloId, requirementId }));
    if (links.length > 0) await db.insert(sloRequirements).values(links);
  }

  return { created, updated, unresolved: named.filter((externalId) => !resolved.has(externalId)) };
}
