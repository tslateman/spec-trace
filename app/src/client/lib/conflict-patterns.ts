export interface ConflictPattern {
  pattern: string;
  label: string;
  source: string;
  compares: string;
  flagsWhen: string;
  high: string;
  medium: string;
  low: string;
}

export const conflictPatterns: ConflictPattern[] = [
  {
    pattern: "mutual_exclusion",
    label: "Mutual exclusion",
    source: "Test history",
    compares: "The pass/fail record of each requirement's linked tests across recent runs",
    flagsWhen: "The two never pass in the same run, and at least one run passed one while failing the other",
    high: "80% or more of shared runs invert, over 10 or more shared runs",
    medium: "50% or more invert, over 5 or more shared runs",
    low: "Fewer shared runs, or a weaker inversion rate",
  },
  {
    pattern: "condition_overlap",
    label: "Condition overlap",
    source: "Spec fields",
    compares: "The condition field of every pair of requirements naming the same component",
    flagsWhen: "Both conditions test the same variable",
    high: "Their numeric thresholds cover overlapping ranges",
    medium: "More than one variable in common",
    low: "One variable in common",
  },
  {
    pattern: "timing_conflict",
    label: "Timing conflict",
    source: "Spec fields",
    compares: "The timing field of every pair of requirements naming the same component",
    flagsWhen: "One component carries two different deadlines",
    high: "The deadlines differ by 5x or more",
    medium: "They differ by 2x to 5x",
    low: "They differ by less than 2x",
  },
  {
    pattern: "response_contradiction",
    label: "Response contradiction",
    source: "Spec fields",
    compares: "The response field of every pair whose conditions share at least half their words",
    flagsWhen: "The responses pull in opposite directions",
    high: "The responses hold an antonym pair, such as show and hide, or enable and disable",
    medium: "—",
    low: "The responses share two or more words but differ",
  },
];
