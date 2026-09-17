import { SELF } from "cloudflare:test";
import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import { corpusEntries, corpusEntryVersions } from "../src/db/schema";
import { db, headers, resetDatabase } from "./fixtures";

beforeEach(async () => {
  await db.delete(corpusEntryVersions);
  await db.delete(corpusEntries);
  await resetDatabase();
});

function put(body: unknown) {
  return SELF.fetch("http://spectrace/api/v1/corpus/entries/", {
    method: "PUT",
    headers,
    body: JSON.stringify(body),
  });
}

async function data(res: Response) {
  return ((await res.json()) as { data: Record<string, number> }).data;
}

async function message(res: Response) {
  return ((await res.json()) as { error: { message: string; code: string } }).error;
}

const entry = {
  external_id: "DEC-IAM-001",
  kind: "decision",
  title: "SAML and OIDC only",
  owner: "identity",
  status: "active",
  version: 1,
  body: "We federate through SAML and OIDC.",
  content_hash: "hash-v1",
  applies_to: { tags: ["identity"], components: [], paths: [], requirement_ids: [] },
  checks: [{ id: "risk-classified", assert: { field: "risk_level" } }],
  retired_checks: [],
  enforcement: "advisory",
  effective_date: "2026-01-08",
  supersedes: null,
  source_file: "corpus/identity/sso.md",
};

describe("PUT /api/v1/corpus/entries/", () => {
  it("creates the entry and its first version", async () => {
    const result = await data(await put({ entries: [entry] }));

    expect(result).toEqual({ entries_created: 1, versions_created: 1, versions_unchanged: 0 });
    const stored = await db.query.corpusEntries.findFirst({
      where: eq(corpusEntries.externalId, entry.external_id),
    });
    expect(stored?.owner).toBe("identity");
  });

  it("counts an unchanged version rather than rewriting it", async () => {
    await put({ entries: [entry] });

    const result = await data(await put({ entries: [entry] }));

    expect(result).toEqual({ entries_created: 0, versions_created: 0, versions_unchanged: 1 });
    const versions = await db.select().from(corpusEntryVersions);
    expect(versions).toHaveLength(1);
  });

  it("refuses content that changed without a version bump", async () => {
    await put({ entries: [entry] });

    const res = await put({ entries: [{ ...entry, body: "Rewritten.", content_hash: "hash-v1b" }] });

    expect(res.status).toBe(400);
    const error = await message(res);
    expect(error.message).toContain("changed without a version bump");
    expect(error.message).toContain("Bump `version`");
  });

  it("records a new version alongside the old one", async () => {
    await put({ entries: [entry] });

    const result = await data(await put({ entries: [{ ...entry, version: 2, content_hash: "hash-v2" }] }));

    expect(result).toEqual({ entries_created: 0, versions_created: 1, versions_unchanged: 0 });
    const versions = await db.select().from(corpusEntryVersions);
    expect(versions.map((row) => row.version).sort()).toEqual([1, 2]);
  });

  it("refuses a version that drops a check id and declares nothing", async () => {
    await put({ entries: [entry] });

    const res = await put({
      entries: [{ ...entry, version: 2, content_hash: "hash-v2", checks: [] }],
    });

    expect(res.status).toBe(400);
    expect((await message(res)).message).toContain("drops check 'risk-classified'");
  });

  it("accepts a dropped check the document retires", async () => {
    await put({ entries: [entry] });

    const result = await data(
      await put({
        entries: [
          {
            ...entry,
            version: 2,
            content_hash: "hash-v2",
            checks: [],
            retired_checks: ["risk-classified"],
          },
        ],
      }),
    );

    expect(result.versions_created).toBe(1);
  });

  it("accepts a renamed check and refuses a rename of an id the predecessor lacks", async () => {
    await put({ entries: [entry] });

    const renamed = await data(
      await put({
        entries: [
          {
            ...entry,
            version: 2,
            content_hash: "hash-v2",
            checks: [{ id: "risk-named", assert: {}, renamed_from: "risk-classified" }],
          },
        ],
      }),
    );
    expect(renamed.versions_created).toBe(1);

    const res = await put({
      entries: [
        {
          ...entry,
          version: 3,
          content_hash: "hash-v3",
          checks: [{ id: "other", assert: {}, renamed_from: "never-existed" }],
          retired_checks: ["risk-named"],
        },
      ],
    });
    expect(res.status).toBe(400);
    expect((await message(res)).message).toContain("does not define");
  });

  it("links supersedes to a version in the same payload", async () => {
    await put({ entries: [entry] });

    await put({
      entries: [{ ...entry, version: 2, content_hash: "hash-v2", supersedes: "DEC-IAM-001@1" }],
    });

    const versions = await db.select().from(corpusEntryVersions);
    const second = versions.find((row) => row.version === 2);
    const first = versions.find((row) => row.version === 1);
    expect(second?.supersedesId).toBe(first?.id);
  });

  it("refuses supersedes naming a version nobody holds", async () => {
    const res = await put({ entries: [{ ...entry, supersedes: "DEC-GHOST-001@4" }] });

    expect(res.status).toBe(400);
    expect((await message(res)).message).toContain("does not exist");
  });

  it("refuses a payload that is not a list of parsed entries", async () => {
    const res = await put({ entries: [{ external_id: "DEC-1" }] });

    expect(res.status).toBe(400);
    expect((await message(res)).code).toBe("validation_error");
  });
});
