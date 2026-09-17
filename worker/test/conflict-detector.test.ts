import { eq } from "drizzle-orm";
import { beforeEach, describe, expect, it } from "vitest";
import {
  detectAllStructuredConflicts,
  detectResponseContradictions,
  detectTimingConflicts,
  logConflicts,
} from "../src/api/v1/queries/conflict-detector";
import { conflictLogs } from "../src/db/schema";
import { db, insertRequirement, resetDatabase } from "./fixtures";

beforeEach(resetDatabase);

describe("detectResponseContradictions", () => {
  it("does not fire across two different components", async () => {
    await insertRequirement({ component: "Alpha", condition: "user clicks button", response: "show the banner" });
    await insertRequirement({ component: "Beta", condition: "user clicks button", response: "hide the banner" });

    expect(await detectResponseContradictions(db)).toEqual([]);
  });

  it("does not report an antonym contradiction with no shared object", async () => {
    await insertRequirement({ component: "Alpha", condition: "user clicks button", response: "show the banner" });
    await insertRequirement({ component: "Alpha", condition: "user clicks button", response: "hide the debug panel" });

    expect(await detectResponseContradictions(db)).toEqual([]);
  });

  it("reports an antonym contradiction with the shared object recorded", async () => {
    await insertRequirement({ component: "Alpha", condition: "user clicks button", response: "show the banner" });
    await insertRequirement({ component: "Alpha", condition: "user clicks button", response: "hide the banner" });

    const conflicts = await detectResponseContradictions(db);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].confidence).toBe("high");
    expect(conflicts[0].details).toMatchObject({
      component: "alpha",
      contradiction_type: "antonym",
      shared_object: "banner",
    });
  });
});

describe("detectTimingConflicts", () => {
  it("does not report timing pairs below the ratio floor", async () => {
    await insertRequirement({ component: "Lock", timing: "10 seconds" });
    await insertRequirement({ component: "Lock", timing: "15 seconds" });

    expect(await detectTimingConflicts(db)).toEqual([]);
  });

  it("reports timing pairs above the ratio floor at the right confidence", async () => {
    await insertRequirement({ component: "Door", timing: "1 seconds" });
    await insertRequirement({ component: "Door", timing: "3 seconds" });

    const conflicts = await detectTimingConflicts(db);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].confidence).toBe("medium");
    expect(conflicts[0].details).toMatchObject({ ratio: 3 });
  });
});

describe("logConflicts recurrence bookkeeping", () => {
  async function seedTimingConflict() {
    await insertRequirement({ component: "Vault", timing: "1 seconds" });
    await insertRequirement({ component: "Vault", timing: "10 seconds" });
  }

  it("creates no second row on an unchanged corpus, and bumps times_detected and last_seen_at", async () => {
    await seedTimingConflict();

    const first = await logConflicts(db, await detectAllStructuredConflicts(db));
    expect(first).toEqual({ createdCount: 1, skippedCount: 0 });

    const afterFirst = await db.query.conflictLogs.findFirst({ where: eq(conflictLogs.pattern, "timing_conflict") });
    expect(afterFirst?.timesDetected).toBe(1);
    expect(afterFirst?.lastSeenAt).toBe(afterFirst?.createdAt);

    const second = await logConflicts(db, await detectAllStructuredConflicts(db));
    expect(second).toEqual({ createdCount: 0, skippedCount: 1 });

    const rows = await db.select().from(conflictLogs).where(eq(conflictLogs.pattern, "timing_conflict"));
    expect(rows).toHaveLength(1);
    expect(rows[0].timesDetected).toBe(2);
    expect(rows[0].lastSeenAt).not.toBeNull();
    expect(rows[0].lastSeenAt! >= afterFirst!.lastSeenAt!).toBe(true);
  });

  it("logs a fresh row when the evidence recurs after the earlier conflict was resolved", async () => {
    await seedTimingConflict();

    await logConflicts(db, await detectAllStructuredConflicts(db));
    const existing = await db.query.conflictLogs.findFirst({ where: eq(conflictLogs.pattern, "timing_conflict") });
    await db.update(conflictLogs).set({ resolved: true }).where(eq(conflictLogs.id, existing!.id));

    const result = await logConflicts(db, await detectAllStructuredConflicts(db));
    expect(result).toEqual({ createdCount: 1, skippedCount: 0 });

    const rows = await db.select().from(conflictLogs).where(eq(conflictLogs.pattern, "timing_conflict"));
    expect(rows).toHaveLength(2);
  });
});
