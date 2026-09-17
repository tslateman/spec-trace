import { describe, expect, it } from "vitest";
import {
  applyConflictFilters,
  clearConflictFilters,
  hasActiveConflictFilters,
  parseConflictFilters,
} from "../src/client/lib/conflict-filters";

describe("conflict filters", () => {
  it("builds a query string from filter state", () => {
    const params = applyConflictFilters(new URLSearchParams(), {
      confidence: "high",
      pattern: "timing_conflict",
      resolved: "open",
    });
    expect(params.toString()).toBe("confidence=high&pattern=timing_conflict&resolved=open");
  });

  it("round-trips state through URLSearchParams", () => {
    const filters = { confidence: "medium", pattern: "condition_overlap", resolved: "resolved" } as const;
    const params = applyConflictFilters(new URLSearchParams(), filters);
    expect(parseConflictFilters(params)).toEqual(filters);
  });

  it("resets to page 1 when a filter changes", () => {
    const current = new URLSearchParams("page=4&per_page=50");
    const next = applyConflictFilters(current, { confidence: "low" });
    expect(next.has("page")).toBe(false);
    expect(next.get("per_page")).toBe("50");
  });

  it("omits empty filters entirely", () => {
    const params = applyConflictFilters(new URLSearchParams(), { confidence: "high" });
    expect(params.has("pattern")).toBe(false);
    expect(params.has("resolved")).toBe(false);
    expect(params.toString()).toBe("confidence=high");
  });

  it("clears an unset filter that was previously applied", () => {
    const withFilter = applyConflictFilters(new URLSearchParams(), { confidence: "high" });
    const cleared = applyConflictFilters(withFilter, {});
    expect(cleared.toString()).toBe("");
  });

  it("ignores a value outside the allowed set", () => {
    const params = new URLSearchParams("confidence=extreme&pattern=timing_conflict&resolved=maybe");
    expect(parseConflictFilters(params)).toEqual({ pattern: "timing_conflict" });
  });

  it("clears all filters and the page while keeping other params", () => {
    const params = new URLSearchParams("confidence=high&pattern=timing_conflict&resolved=open&page=3&per_page=25");
    const cleared = clearConflictFilters(params);
    expect(cleared.toString()).toBe("per_page=25");
  });

  it("reports whether any filter is active", () => {
    expect(hasActiveConflictFilters({})).toBe(false);
    expect(hasActiveConflictFilters({ resolved: "open" })).toBe(true);
  });
});
