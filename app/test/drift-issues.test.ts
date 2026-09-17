import { describe, expect, it } from "vitest";
import { fileOf, fixHintFor, groupIssuesByType, requirementIdOf } from "../src/client/lib/drift-issues";
import type { DriftIssue } from "../src/shared/spectrace";

const ORPHAN: DriftIssue = {
  type: "orphan_requirement",
  id: "REQ-IAM-002",
  title: "Role-Based Access Control (RBAC)",
  source_file: "specs/identity/rbac.md",
  message: "Active requirement has no test coverage and no children",
};

const UNMARKED: DriftIssue = {
  type: "unmarked_test",
  id: "spectrace/tests/test_cli.py",
  message: "Test file has no spec markers",
  path: "spectrace/tests/test_cli.py",
};

const STALE_LINK: DriftIssue = {
  type: "stale_link",
  id: "spectrace/tests/test_cli.py::test_run:REQ-IAM-002",
  message: "Link references test not in latest run",
  test_nodeid: "spectrace/tests/test_cli.py::test_run",
  requirement_id: "REQ-IAM-002",
};

describe("requirementIdOf", () => {
  it("returns the requirement id an orphan_requirement carries in id", () => {
    expect(requirementIdOf(ORPHAN)).toBe("REQ-IAM-002");
  });

  it("returns undefined for unmarked_test, whose id is a file path", () => {
    expect(requirementIdOf(UNMARKED)).toBeUndefined();
  });

  it("prefers the explicit requirement_id of a stale_link over its composite id", () => {
    expect(requirementIdOf(STALE_LINK)).toBe("REQ-IAM-002");
  });
});

describe("fileOf", () => {
  it("reads source_file for a requirement issue", () => {
    expect(fileOf(ORPHAN)).toBe("specs/identity/rbac.md");
  });

  it("reads path for a test file issue", () => {
    expect(fileOf(UNMARKED)).toBe("spectrace/tests/test_cli.py");
  });
});

describe("fixHintFor", () => {
  it("names the fix for every type the validator emits", () => {
    for (const type of [
      "unknown_requirement",
      "no_coverage",
      "unmarked_test",
      "stale_link",
      "orphan_requirement",
      "wide_parent",
      "long_untested",
      "spec_drift",
      "high_risk_no_tests",
      "high_risk_failing_tests",
      "high_risk_no_slo",
      "pr_impacts_failing_high_risk",
      "pr_impacts_untested_high_risk",
    ]) {
      expect(fixHintFor(type), type).toBeTruthy();
    }
  });
});

describe("groupIssuesByType", () => {
  it("puts the largest group first and keeps every issue", () => {
    const issues = [ORPHAN, ...Array.from({ length: 69 }, () => UNMARKED)];
    const groups = groupIssuesByType(issues);

    expect(groups.map(([type, group]) => [type, group.length])).toEqual([
      ["unmarked_test", 69],
      ["orphan_requirement", 1],
    ]);
    expect(groups.reduce((total, [, group]) => total + group.length, 0)).toBe(70);
  });
});
