import { describe, expect, it } from "vitest";
import { change, percent, polyline, trendPoints } from "../src/client/lib/coverage-trend";
import type { CoverageSnapshot } from "../src/shared/spectrace";

function snapshot(overrides: Partial<CoverageSnapshot>): CoverageSnapshot {
  return {
    commit_sha: "aaaa111bbbb",
    git_branch: "main",
    generated_at: "2026-09-01T12:00:00.000000+00:00",
    stored_at: "2026-09-01T12:00:01.000000+00:00",
    specification_rate: 0.5,
    structure_rate: 0.5,
    verification_rate: 0.5,
    total: 4,
    non_draft: 2,
    passing: 2,
    ...overrides,
  };
}

describe("trendPoints", () => {
  it("spreads the series across the width and inverts the rate into screen space", () => {
    const points = trendPoints(
      [
        snapshot({ verification_rate: 0 }),
        snapshot({ verification_rate: 0.5, stored_at: "2026-09-02T12:00:01.000000+00:00" }),
        snapshot({ verification_rate: 1, stored_at: "2026-09-03T12:00:01.000000+00:00" }),
      ],
      "verification_rate",
      600,
      160,
    );

    expect(points.map((point) => [point.x, point.y])).toEqual([
      [0, 160],
      [300, 80],
      [600, 0],
    ]);
  });

  it("centres a lone snapshot instead of dividing by zero", () => {
    const points = trendPoints([snapshot({ verification_rate: 0.25 })], "verification_rate", 600, 160);

    expect(points).toHaveLength(1);
    expect(points[0].x).toBe(300);
    expect(points[0].y).toBe(120);
  });

  it("clamps a rate outside 0 to 1 onto the plot", () => {
    const points = trendPoints([snapshot({ structure_rate: 1.4 })], "structure_rate", 600, 160);

    expect(points[0].y).toBe(0);
  });
});

describe("polyline", () => {
  it("renders the points as SVG coordinate pairs", () => {
    const points = trendPoints([snapshot({}), snapshot({ specification_rate: 1 })], "specification_rate", 600, 160);

    expect(polyline(points)).toBe("0,80 600,0");
  });
});

describe("change", () => {
  it("reports the move against the snapshot before the latest, in points", () => {
    const series = [snapshot({ verification_rate: 0.25 }), snapshot({ verification_rate: 0.5 })];

    expect(change(series, "verification_rate")).toBe("+25.0 pts");
  });

  it("names a drop with its sign", () => {
    const series = [snapshot({ verification_rate: 0.5 }), snapshot({ verification_rate: 0.4 })];

    expect(change(series, "verification_rate")).toBe("-10.0 pts");
  });

  it("calls an unmoved rate unchanged", () => {
    expect(change([snapshot({}), snapshot({})], "structure_rate")).toBe("unchanged");
  });

  it("reports no change for a lone snapshot", () => {
    expect(change([snapshot({})], "structure_rate")).toBeNull();
  });
});

describe("percent", () => {
  it("renders a rate to one decimal", () => {
    expect(percent(0.4)).toBe("40.0%");
  });
});
