import { describe, expect, it } from "vitest";
import detectorSource from "../../worker/src/api/v1/queries/conflict-detector.ts?raw";
import { conflictPatterns } from "../src/client/lib/conflict-patterns";

const emitted = new Set(
  [...detectorSource.matchAll(/conflictBetween\(\s*\w+,\s*\w+,\s*"([a-z_]+)"/g)].map((m) => m[1]),
);
const documented = new Set(conflictPatterns.map((entry) => entry.pattern));

describe("conflict pattern guide", () => {
  it("finds the patterns the detector emits", () => {
    expect(emitted.size).toBeGreaterThan(0);
  });

  it("explains every pattern the detector can log", () => {
    expect([...emitted].filter((pattern) => !documented.has(pattern))).toEqual([]);
  });

  it("documents no pattern the detector never logs", () => {
    expect([...documented].filter((pattern) => !emitted.has(pattern))).toEqual([]);
  });

  it("gives every pattern a confidence rule for each level", () => {
    for (const entry of conflictPatterns) {
      expect(entry.high, entry.pattern).not.toBe("");
      expect(entry.medium, entry.pattern).not.toBe("");
      expect(entry.low, entry.pattern).not.toBe("");
    }
  });
});
