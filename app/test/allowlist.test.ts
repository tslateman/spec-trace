import { describe, expect, it } from "vitest";
import { allowedLogins, isAllowed } from "../src/server/auth/allowlist";

describe("allowedLogins", () => {
  it("throws when ALLOWED_LOGINS is unset", () => {
    expect(() => allowedLogins(undefined)).toThrow("ALLOWED_LOGINS is not configured");
    expect(() => allowedLogins("")).toThrow("ALLOWED_LOGINS is not configured");
  });

  it("trims, lowercases, and drops empty entries", () => {
    expect(allowedLogins(" Alice, bob ,,CAROL,")).toEqual(["alice", "bob", "carol"]);
  });
});

describe("isAllowed", () => {
  it("matches logins regardless of case", () => {
    expect(isAllowed("alice,bob", "ALICE")).toBe(true);
    expect(isAllowed("alice,bob", "Bob")).toBe(true);
  });

  it("rejects a login outside the list", () => {
    expect(isAllowed("alice,bob", "mallory")).toBe(false);
  });
});
