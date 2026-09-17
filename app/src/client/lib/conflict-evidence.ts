export interface EvidenceFact {
  label: string;
  value: string;
}

export interface EvidenceSummary {
  verdict: string;
  facts: EvidenceFact[];
}

function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

function formatRatio(ratio: number): string {
  return `${Math.round(ratio * 10) / 10}x`.replace(/\.0x$/, "x");
}

function summarizeMutualExclusion(details: Record<string, unknown>): EvidenceSummary {
  const bothPassed = Number(details.both_passed);
  const aPassedBFailed = Number(details.a_passed_b_failed);
  const aFailedBPassed = Number(details.a_failed_b_passed);
  const bothFailed = Number(details.both_failed);
  const inverseRatio = Number(details.inverse_ratio);
  const runsAnalyzed = bothPassed + aPassedBFailed + aFailedBPassed + bothFailed;
  return {
    verdict: `Across ${runsAnalyzed} shared runs, the two requirements inverted ${formatPercent(inverseRatio)} of the time.`,
    facts: [
      { label: "Both passed", value: String(bothPassed) },
      { label: "A passed, B failed", value: String(aPassedBFailed) },
      { label: "A failed, B passed", value: String(aFailedBPassed) },
      { label: "Both failed", value: String(bothFailed) },
      { label: "Inverse ratio", value: formatPercent(inverseRatio) },
    ],
  };
}

function summarizeConditionOverlap(details: Record<string, unknown>): EvidenceSummary {
  const component = String(details.component);
  const conditionA = String(details.condition_a);
  const conditionB = String(details.condition_b);
  const commonVariables = (details.common_variables as string[]).join(", ");
  const overlapType = String(details.overlap_type);
  const thresholdsA = (details.thresholds_a as number[]).join(", ");
  const thresholdsB = (details.thresholds_b as number[]).join(", ");
  const verdict =
    overlapType === "range_overlap"
      ? `On ${component}, the numeric ranges in both conditions actually intersect.`
      : `On ${component}, both conditions share a variable, but their numeric ranges do not overlap.`;
  return {
    verdict,
    facts: [
      { label: "Component", value: component },
      { label: "Condition A", value: conditionA },
      { label: "Condition B", value: conditionB },
      { label: "Shared variables", value: commonVariables },
      { label: "Overlap type", value: overlapType },
      { label: "Thresholds A", value: thresholdsA },
      { label: "Thresholds B", value: thresholdsB },
    ],
  };
}

function summarizeTimingConflict(details: Record<string, unknown>): EvidenceSummary {
  const component = String(details.component);
  const timingA = String(details.timing_a);
  const timingB = String(details.timing_b);
  const secondsA = Number(details.seconds_a);
  const secondsB = Number(details.seconds_b);
  const ratio = Number(details.ratio);
  const tighter = secondsA < secondsB ? timingA : timingB;
  const looser = secondsA < secondsB ? timingB : timingA;
  return {
    verdict: `${tighter} is ${formatRatio(ratio)} tighter than ${looser}, on the same ${component}.`,
    facts: [
      { label: "Component", value: component },
      { label: "Timing A", value: timingA },
      { label: "Timing B", value: timingB },
      { label: "Seconds A", value: String(secondsA) },
      { label: "Seconds B", value: String(secondsB) },
      { label: "Ratio", value: formatRatio(ratio) },
    ],
  };
}

function summarizeResponseContradiction(details: Record<string, unknown>): EvidenceSummary {
  const component = String(details.component);
  const conditionA = String(details.condition_a);
  const conditionB = String(details.condition_b);
  const responseA = String(details.response_a);
  const responseB = String(details.response_b);
  const contradictionType = String(details.contradiction_type);
  const antonymPair = details.antonym_pair as string[] | undefined;
  const sharedObject = details.shared_object as string | undefined;

  const facts: EvidenceFact[] = [
    { label: "Component", value: component },
    { label: "Condition A", value: conditionA },
    { label: "Condition B", value: conditionB },
    { label: "Response A", value: responseA },
    { label: "Response B", value: responseB },
    { label: "Contradiction type", value: contradictionType },
  ];
  if (antonymPair) facts.push({ label: "Antonym pair", value: antonymPair.join(" / ") });
  if (sharedObject) facts.push({ label: "Shared object", value: sharedObject });

  const verdict =
    antonymPair && sharedObject
      ? `Under similar conditions, one response says "${antonymPair[0]}" and the other says "${antonymPair[1]}" the same ${sharedObject}.`
      : `Under similar conditions, the two responses use overlapping words but point in different directions.`;

  return { verdict, facts };
}

function summarizeUnknown(details: Record<string, unknown>): EvidenceSummary {
  return {
    verdict: "Unrecognized conflict pattern; showing raw evidence fields.",
    facts: Object.entries(details).map(([label, value]) => ({ label, value: String(value) })),
  };
}

export function summarizeEvidence(pattern: string, details: Record<string, unknown>): EvidenceSummary {
  switch (pattern) {
    case "mutual_exclusion":
      return summarizeMutualExclusion(details);
    case "condition_overlap":
      return summarizeConditionOverlap(details);
    case "timing_conflict":
      return summarizeTimingConflict(details);
    case "response_contradiction":
      return summarizeResponseContradiction(details);
    default:
      return summarizeUnknown(details);
  }
}
