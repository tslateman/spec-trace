export const confidenceValues = ["high", "medium", "low"] as const;
export type ConfidenceFilter = (typeof confidenceValues)[number];

export const patternValues = [
  "mutual_exclusion",
  "condition_overlap",
  "timing_conflict",
  "response_contradiction",
] as const;
export type PatternFilterValue = (typeof patternValues)[number];

export const resolvedValues = ["open", "resolved"] as const;
export type ResolvedFilter = (typeof resolvedValues)[number];

export interface ConflictFilters {
  confidence?: ConfidenceFilter;
  pattern?: PatternFilterValue;
  resolved?: ResolvedFilter;
}

const FILTER_KEYS = ["confidence", "pattern", "resolved"] as const;

function isConfidence(value: string | null): value is ConfidenceFilter {
  return confidenceValues.includes(value as ConfidenceFilter);
}

function isPattern(value: string | null): value is PatternFilterValue {
  return patternValues.includes(value as PatternFilterValue);
}

function isResolved(value: string | null): value is ResolvedFilter {
  return resolvedValues.includes(value as ResolvedFilter);
}

export function parseConflictFilters(params: URLSearchParams): ConflictFilters {
  const filters: ConflictFilters = {};
  const confidence = params.get("confidence");
  if (isConfidence(confidence)) filters.confidence = confidence;
  const pattern = params.get("pattern");
  if (isPattern(pattern)) filters.pattern = pattern;
  const resolved = params.get("resolved");
  if (isResolved(resolved)) filters.resolved = resolved;
  return filters;
}

export function applyConflictFilters(params: URLSearchParams, filters: ConflictFilters): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete("page");
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value) next.set(key, value);
    else next.delete(key);
  }
  return next;
}

export function clearConflictFilters(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const key of FILTER_KEYS) next.delete(key);
  next.delete("page");
  return next;
}

export function hasActiveConflictFilters(filters: ConflictFilters): boolean {
  return FILTER_KEYS.some((key) => Boolean(filters[key]));
}
