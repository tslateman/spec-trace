import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const FIXED_VERSION = [0, 45, 2] as const;

function parseVersion(version: string): [number, number, number] {
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) throw new Error(`Unparseable version: ${version}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function isAtLeast(actual: [number, number, number], minimum: readonly [number, number, number]): boolean {
  for (let i = 0; i < 3; i++) {
    if (actual[i] > minimum[i]) return true;
    if (actual[i] < minimum[i]) return false;
  }
  return true;
}

describe("drizzle-orm dependency", () => {
  const { declared, resolved } = env.DEPENDENCY_VERSIONS["drizzle-orm"];

  it("declares a version range that excludes the GHSA-gpj5-g38j-94v9 SQL injection", () => {
    const declaredVersion = parseVersion(declared.replace(/^[\^~]/, ""));
    expect(isAtLeast(declaredVersion, FIXED_VERSION)).toBe(true);
  });

  it("resolves drizzle-orm to a patched version in the lockfile", () => {
    expect(isAtLeast(parseVersion(resolved), FIXED_VERSION)).toBe(true);
  });
});
