import type { DriftIssue } from "../../shared/spectrace";

const FIX_BY_TYPE: Record<string, string> = {
  unknown_requirement: "Add this requirement to a spec, or correct the id in the test marker.",
  no_coverage: "Mark a test with this requirement id.",
  unmarked_test: "Add a spec marker to this test file.",
  stale_link: "Rerun the tests, or drop the link to the deleted test.",
  orphan_requirement: "Mark a test with this requirement id.",
  wide_parent: "Split this requirement into sub-requirements.",
  long_untested: "Write a test for this requirement, or retire it.",
  spec_drift: "Rerun the tests against the edited spec.",
  high_risk_no_tests: "Write and mark a test for this requirement.",
  high_risk_failing_tests: "Fix the failing tests.",
  high_risk_no_slo: "Link an SLO to this requirement.",
  pr_impacts_failing_high_risk: "Fix the failing tests before merging.",
  pr_impacts_untested_high_risk: "Write a test before merging.",
};

/**
 * Returns the requirement id an issue is about, or undefined when it is about a file.
 * Issues carrying a `path` use `id` for that path, so only those without one identify a requirement.
 */
export function requirementIdOf(issue: DriftIssue): string | undefined {
  if (issue.requirement_id) return issue.requirement_id;
  return issue.path ? undefined : issue.id;
}

export function fileOf(issue: DriftIssue): string | undefined {
  return issue.path ?? issue.source_file;
}

export function fixHintFor(type: string): string | undefined {
  return FIX_BY_TYPE[type];
}

/** Groups issues by type, largest group first. */
export function groupIssuesByType(issues: DriftIssue[]): [string, DriftIssue[]][] {
  const groups = new Map<string, DriftIssue[]>();
  for (const issue of issues) {
    const group = groups.get(issue.type);
    if (group) group.push(issue);
    else groups.set(issue.type, [issue]);
  }
  return [...groups].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
}
