import { describe, expect, it } from "vitest";
import { collapse, expand, flattenTree } from "../src/client/lib/requirement-tree";
import type { RequirementSummary } from "../src/shared/spectrace";

function requirement(externalId: string, depth: number): RequirementSummary {
  return {
    external_id: externalId,
    title: externalId,
    description: "",
    path: "",
    depth,
    numchild: 0,
    tags: [],
    priority: "medium",
    status: "active",
    verification_status: "untested",
    verification_method: "test",
    risk_level: "low",
    source_file: "specs/a.md",
    descendants: { total: 0, passing: 0, failing: 0, untested: 0, highest_risk: "unclassified" },
  };
}

const root = requirement("REQ-A", 1);
const other = requirement("REQ-B", 1);
const kid = requirement("REQ-A-1", 2);
const grandkid = requirement("REQ-A-1-1", 3);

describe("flattenTree", () => {
  it("lists roots alone when nothing is expanded", () => {
    expect(flattenTree([root, other], {})).toEqual([
      { requirement: root, level: 0, expanded: false },
      { requirement: other, level: 0, expanded: false },
    ]);
  });

  it("interleaves expanded children beneath their parent at the next level", () => {
    const expanded = expand(expand({}, "REQ-A", [kid]), "REQ-A-1", [grandkid]);

    expect(flattenTree([root, other], expanded).map((row) => [row.requirement.external_id, row.level])).toEqual([
      ["REQ-A", 0],
      ["REQ-A-1", 1],
      ["REQ-A-1-1", 2],
      ["REQ-B", 0],
    ]);
  });

  it("hides a collapsed subtree but remembers how it was expanded", () => {
    const expanded = expand(expand({}, "REQ-A", [kid]), "REQ-A-1", [grandkid]);
    const collapsed = collapse(expanded, "REQ-A");

    expect(flattenTree([root], collapsed).map((row) => row.requirement.external_id)).toEqual(["REQ-A"]);
    expect(flattenTree([root], expand(collapsed, "REQ-A", [kid])).map((row) => row.requirement.external_id)).toEqual([
      "REQ-A",
      "REQ-A-1",
      "REQ-A-1-1",
    ]);
  });
});
