import { describe, expect, it } from "vitest";
import { summarizeEvidence } from "../src/client/lib/conflict-evidence";

describe("summarizeEvidence", () => {
  it("summarizes mutual_exclusion with run tallies and a percent inverse ratio", () => {
    const summary = summarizeEvidence("mutual_exclusion", {
      both_passed: 0,
      a_passed_b_failed: 7,
      a_failed_b_passed: 1,
      both_failed: 2,
      inverse_ratio: 0.8,
    });
    expect(summary.verdict).toBe("Across 10 shared runs, the two requirements inverted 80% of the time.");
    expect(summary.facts).toEqual([
      { label: "Both passed", value: "0" },
      { label: "A passed, B failed", value: "7" },
      { label: "A failed, B passed", value: "1" },
      { label: "Both failed", value: "2" },
      { label: "Inverse ratio", value: "80%" },
    ]);
  });

  it("formats a fractional inverse_ratio to a rounded percent", () => {
    const summary = summarizeEvidence("mutual_exclusion", {
      both_passed: 0,
      a_passed_b_failed: 5,
      a_failed_b_passed: 0,
      both_failed: 1,
      inverse_ratio: 0.8333333,
    });
    expect(summary.facts.at(-1)).toEqual({ label: "Inverse ratio", value: "83%" });
  });

  it("says ranges intersect for a condition_overlap range_overlap", () => {
    const summary = summarizeEvidence("condition_overlap", {
      component: "brake_controller",
      condition_a: "speed > 40",
      condition_b: "speed < 60",
      common_variables: ["speed"],
      overlap_type: "range_overlap",
      thresholds_a: [40],
      thresholds_b: [60],
    });
    expect(summary.verdict).toBe("On brake_controller, the numeric ranges in both conditions actually intersect.");
    expect(summary.facts).toEqual([
      { label: "Component", value: "brake_controller" },
      { label: "Condition A", value: "speed > 40" },
      { label: "Condition B", value: "speed < 60" },
      { label: "Shared variables", value: "speed" },
      { label: "Overlap type", value: "range_overlap" },
      { label: "Thresholds A", value: "40" },
      { label: "Thresholds B", value: "60" },
    ]);
  });

  it("says only a shared variable matches for a condition_overlap variable_overlap", () => {
    const summary = summarizeEvidence("condition_overlap", {
      component: "brake_controller",
      condition_a: "speed > 90",
      condition_b: "speed < 10",
      common_variables: ["speed"],
      overlap_type: "variable_overlap",
      thresholds_a: [90],
      thresholds_b: [10],
    });
    expect(summary.verdict).toBe(
      "On brake_controller, both conditions share a variable, but their numeric ranges do not overlap.",
    );
  });

  it("states the gap in plain terms for timing_conflict, naming the tighter timing first", () => {
    const summary = summarizeEvidence("timing_conflict", {
      component: "alert_panel",
      timing_a: "within 2 seconds",
      timing_b: "within 200ms",
      seconds_a: 2,
      seconds_b: 0.2,
      ratio: 9.999999999,
    });
    expect(summary.verdict).toBe("within 200ms is 10x tighter than within 2 seconds, on the same alert_panel.");
    expect(summary.facts).toEqual([
      { label: "Component", value: "alert_panel" },
      { label: "Timing A", value: "within 2 seconds" },
      { label: "Timing B", value: "within 200ms" },
      { label: "Seconds A", value: "2" },
      { label: "Seconds B", value: "0.2" },
      { label: "Ratio", value: "10x" },
    ]);
  });

  it("names the antonym pair and shared object for response_contradiction", () => {
    const summary = summarizeEvidence("response_contradiction", {
      component: "status_light",
      condition_a: "when connection is lost",
      condition_b: "when connection is lost",
      response_a: "the system shall show the warning banner",
      response_b: "the system shall hide the warning banner",
      contradiction_type: "antonym",
      antonym_pair: ["show", "hide"],
      shared_object: "banner",
    });
    expect(summary.verdict).toBe(
      'Under similar conditions, one response says "show" and the other says "hide" the same banner.',
    );
    expect(summary.facts).toEqual([
      { label: "Component", value: "status_light" },
      { label: "Condition A", value: "when connection is lost" },
      { label: "Condition B", value: "when connection is lost" },
      { label: "Response A", value: "the system shall show the warning banner" },
      { label: "Response B", value: "the system shall hide the warning banner" },
      { label: "Contradiction type", value: "antonym" },
      { label: "Antonym pair", value: "show / hide" },
      { label: "Shared object", value: "banner" },
    ]);
  });

  it("omits antonym_pair and shared_object facts when absent, for a partial_overlap contradiction", () => {
    const summary = summarizeEvidence("response_contradiction", {
      component: "status_light",
      condition_a: "when connection is lost",
      condition_b: "when connection drops",
      response_a: "the system shall log the event and notify the operator",
      response_b: "the system shall log the event only",
      contradiction_type: "partial_overlap",
      common_words: ["log", "the", "event"],
    });
    expect(summary.facts).toEqual([
      { label: "Component", value: "status_light" },
      { label: "Condition A", value: "when connection is lost" },
      { label: "Condition B", value: "when connection drops" },
      { label: "Response A", value: "the system shall log the event and notify the operator" },
      { label: "Response B", value: "the system shall log the event only" },
      { label: "Contradiction type", value: "partial_overlap" },
    ]);
    expect(summary.verdict).toBe(
      "Under similar conditions, the two responses use overlapping words but point in different directions.",
    );
  });

  it("falls back to raw key/value pairs for an unknown pattern", () => {
    const summary = summarizeEvidence("temporal_paradox", { foo: "bar", count: 3 });
    expect(summary.verdict).toBe("Unrecognized conflict pattern; showing raw evidence fields.");
    expect(summary.facts).toEqual([
      { label: "foo", value: "bar" },
      { label: "count", value: "3" },
    ]);
  });
});
