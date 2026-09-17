import { and, desc, eq, lt } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { corpusEntries, corpusEntryVersions } from "../../../db/schema";
import { storedNow } from "./time";

export interface CorpusCheck {
  id: string;
  assert: unknown;
  renamed_from?: string;
}

export interface CorpusEntryUpsert {
  external_id: string;
  kind: string;
  title: string;
  owner: string;
  status: string;
  version: number;
  body: string;
  content_hash: string;
  applies_to: unknown;
  checks: CorpusCheck[];
  retired_checks?: string[];
  enforcement: string;
  effective_date: string | null;
  supersedes: string | null;
  source_file: string;
}

export interface CorpusPushResult {
  entries_created: number;
  versions_created: number;
  versions_unchanged: number;
}

export class CorpusPushRefusal extends Error {}

const SUPERSEDES = /^(?<entryId>[A-Za-z0-9._-]+)@(?<version>\d+)$/;

function rendered(ids: string[]): string {
  return ids.map((id) => `'${id}'`).join(", ");
}

export function validateCheckLineage(
  entry: CorpusEntryUpsert,
  previousVersion: number,
  previousChecks: CorpusCheck[],
): void {
  const entryId = entry.external_id;
  const version = entry.version;
  const previousIds = new Set(previousChecks.map((check) => check.id));
  const currentIds = new Set(entry.checks.map((check) => check.id));
  const renames = new Map<string, string>();
  for (const check of entry.checks) {
    if (check.renamed_from !== undefined) renames.set(check.renamed_from, check.id);
  }
  const retired = new Set(entry.retired_checks ?? []);

  for (const [oldId, newId] of [...renames].sort(([a], [b]) => a.localeCompare(b))) {
    if (!previousIds.has(oldId)) {
      throw new CorpusPushRefusal(
        `${entryId} version ${version}: check '${newId}' declares renamed_from '${oldId}', which version ${previousVersion} does not define`,
      );
    }
    if (currentIds.has(oldId)) {
      throw new CorpusPushRefusal(
        `${entryId} version ${version}: check '${newId}' declares renamed_from '${oldId}', which this version still defines as a check of its own`,
      );
    }
  }

  const unknownRetired = [...retired].filter((id) => !previousIds.has(id)).sort();
  if (unknownRetired.length > 0) {
    throw new CorpusPushRefusal(
      `${entryId} version ${version}: retired_checks names ${rendered(unknownRetired)}, which version ${previousVersion} does not define`,
    );
  }

  const undeclared = [...previousIds]
    .filter((id) => !currentIds.has(id) && !renames.has(id) && !retired.has(id))
    .sort();
  if (undeclared.length === 0) return;

  const renamedTo = new Set(renames.values());
  const added = [...currentIds].filter((id) => !previousIds.has(id) && !renamedTo.has(id)).sort();
  if (added.length > 0) {
    throw new CorpusPushRefusal(
      `${entryId} version ${version} drops check ${rendered(undeclared)} while adding ${rendered(added)}. Findings cite ${entryId}#${undeclared[0]} without a version, so declare \`renamed_from: ${undeclared[0]}\` on check '${added[0]}', or list ${rendered(undeclared)} under \`retired_checks\`.`,
    );
  }

  throw new CorpusPushRefusal(
    `${entryId} version ${version} drops check ${rendered(undeclared)}, which version ${previousVersion} defines, and declares nothing. Findings cite ${entryId}#${undeclared[0]} without a version, so list ${rendered(undeclared)} under \`retired_checks\`, or declare \`renamed_from: ${undeclared[0]}\` on the replacing check.`,
  );
}

export async function pushCorpusEntries(db: Database, payload: CorpusEntryUpsert[]): Promise<CorpusPushResult> {
  const result: CorpusPushResult = { entries_created: 0, versions_created: 0, versions_unchanged: 0 };
  const versionIds = new Map<string, number>();

  for (const upsert of payload) {
    const now = storedNow();
    const definition = {
      kind: upsert.kind,
      title: upsert.title,
      owner: upsert.owner,
      status: upsert.status,
      sourceFile: upsert.source_file,
    };

    const existing = await db.query.corpusEntries.findFirst({
      where: eq(corpusEntries.externalId, upsert.external_id),
    });
    let entryId: number;
    if (existing) {
      await db
        .update(corpusEntries)
        .set({ ...definition, updatedAt: now })
        .where(eq(corpusEntries.id, existing.id));
      entryId = existing.id;
    } else {
      const [row] = await db
        .insert(corpusEntries)
        .values({ externalId: upsert.external_id, ...definition, createdAt: now, updatedAt: now })
        .returning({ id: corpusEntries.id });
      entryId = row.id;
      result.entries_created += 1;
    }

    const [previous] = await db
      .select()
      .from(corpusEntryVersions)
      .where(and(eq(corpusEntryVersions.entryId, entryId), lt(corpusEntryVersions.version, upsert.version)))
      .orderBy(desc(corpusEntryVersions.version))
      .limit(1);
    if (previous) validateCheckLineage(upsert, previous.version, previous.checks as CorpusCheck[]);

    const stored = await db.query.corpusEntryVersions.findFirst({
      where: and(eq(corpusEntryVersions.entryId, entryId), eq(corpusEntryVersions.version, upsert.version)),
    });
    if (!stored) {
      const [row] = await db
        .insert(corpusEntryVersions)
        .values({
          entryId,
          version: upsert.version,
          body: upsert.body,
          contentHash: upsert.content_hash,
          appliesTo: upsert.applies_to,
          checks: upsert.checks,
          enforcement: upsert.enforcement,
          effectiveDate: upsert.effective_date,
          sourceFile: upsert.source_file,
          createdAt: now,
        })
        .returning({ id: corpusEntryVersions.id });
      versionIds.set(`${upsert.external_id}@${upsert.version}`, row.id);
      result.versions_created += 1;
    } else if (stored.contentHash !== upsert.content_hash) {
      throw new CorpusPushRefusal(
        `${upsert.external_id} version ${upsert.version} changed without a version bump. Stored hash ${stored.contentHash}, incoming hash ${upsert.content_hash} from ${upsert.source_file}. Bump \`version\` to record the new content.`,
      );
    } else {
      versionIds.set(`${upsert.external_id}@${upsert.version}`, stored.id);
      result.versions_unchanged += 1;
    }
  }

  await resolveSupersedes(db, payload, versionIds);
  return result;
}

async function resolveSupersedes(
  db: Database,
  payload: CorpusEntryUpsert[],
  versionIds: Map<string, number>,
): Promise<void> {
  for (const upsert of payload) {
    if (upsert.supersedes === null) continue;
    const match = SUPERSEDES.exec(upsert.supersedes);
    if (!match?.groups) {
      throw new CorpusPushRefusal(
        `${upsert.external_id}: supersedes '${upsert.supersedes}' is not in ENTRY-ID@VERSION form`,
      );
    }
    const key = `${match.groups.entryId}@${match.groups.version}`;
    let targetId = versionIds.get(key);
    if (targetId === undefined) {
      const [target] = await db
        .select({ id: corpusEntryVersions.id })
        .from(corpusEntryVersions)
        .innerJoin(corpusEntries, eq(corpusEntries.id, corpusEntryVersions.entryId))
        .where(
          and(
            eq(corpusEntries.externalId, match.groups.entryId),
            eq(corpusEntryVersions.version, Number(match.groups.version)),
          ),
        );
      targetId = target?.id;
    }
    if (targetId === undefined) {
      throw new CorpusPushRefusal(
        `${upsert.external_id}: supersedes '${upsert.supersedes}' names a version that does not exist in the corpus or the database`,
      );
    }
    const versionId = versionIds.get(`${upsert.external_id}@${upsert.version}`);
    await db
      .update(corpusEntryVersions)
      .set({ supersedesId: targetId })
      .where(eq(corpusEntryVersions.id, versionId as number));
  }
}
