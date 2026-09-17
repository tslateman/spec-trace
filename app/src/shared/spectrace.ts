export interface CoverageMetrics {
  total: number;
  non_draft: number;
  passing: number;
  failing: number;
  untested: number;
  stale: number;
}

export interface CoverageReport {
  data: {
    project: string;
    metrics: CoverageMetrics;
    stale_requirements: string[];
  };
}

export interface ValidationRun {
  id: number;
  source: string;
  imported_at: string | null;
  total_validations: number;
  successful: number;
  failed: number;
}

export interface ValidationRunsPage {
  data: ValidationRun[];
  meta: PagePosition;
}

export interface TaskTestRunRequirement {
  requirement_id: string;
  passed: number;
  failed: number;
}

export interface TaskTestRun {
  commit_sha: string;
  status: "passing" | "failing" | "missing";
  run_ids: number[];
  imported_at: string | null;
  passed: number;
  failed: number;
  requirements: TaskTestRunRequirement[];
}

export interface AgentTask {
  id: string;
  title: string;
  status: string;
  claimed_by: string | null;
  sprint: string | null;
  attempt_count: number;
  created_at: string;
  commit_sha: string;
  test_run: TaskTestRun | null;
}

export interface AgentTasksPage {
  data: AgentTask[];
  meta: PagePosition;
}

export interface RequirementSummary {
  external_id: string;
  title: string;
  description: string;
  path: string;
  depth: number;
  numchild: number;
  tags: string[];
  priority: string;
  status: string;
  verification_status: string;
  verification_method: string;
  risk_level: string;
  source_file: string;
  descendants: DescendantRollup;
}

export interface DescendantRollup {
  total: number;
  passing: number;
  failing: number;
  untested: number;
  highest_risk: string;
}

export interface PagePosition {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface RequirementCrumb {
  external_id: string;
  title: string;
}

export interface RequirementScope extends RequirementCrumb {
  ancestors: RequirementCrumb[];
}

export interface RequirementsPage {
  data: { project: string; scope?: RequirementScope; requirements: RequirementSummary[] };
  meta: PagePosition;
}

export interface RequirementContext {
  data: {
    external_id: string;
    title: string;
    description: string;
    tags: string[];
    status: string;
    verification_status: string;
    priority: string;
    test_results: { test_nodeid: string; last_status: string }[];
    depends_on: string[];
    depended_by: string[];
    fret?: Record<string, string>;
  };
}

export interface RequirementStatus {
  data: {
    external_id: string;
    title: string;
    verification_status: string;
    last_checked: string | null;
    latest_result: {
      status: string;
      message: string;
      checked_at: string;
      steps_passed: number;
      steps_failed: number;
    } | null;
    regression: { is_regression: boolean; previous_status?: string; regressed_at?: string | null };
  };
}

export interface ValidationRunResult {
  id: number;
  validation_id: number;
  validation_name: string;
  requirement_id: string;
  vendor: string;
  status: string;
  message: string;
  checked_at: string;
  step_count: number;
  steps_passed: number;
}

export interface ValidationRunDetail {
  id: number;
  source: string;
  imported_at: string;
  total_validations: number;
  successful: number;
  failed: number;
  results: ValidationRunResult[];
}

export interface ValidationStep {
  name: string;
  passed: boolean;
  details?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
}

export interface ValidationRunSteps {
  run_id: number;
  results: {
    result_id: number;
    validation_name: string;
    requirement_id: string;
    status: string;
    steps: ValidationStep[];
    context: unknown;
  }[];
}

export interface ValidationRunDiff {
  data: {
    compared_to: { id: number; source: string; imported_at: string };
    summary: Record<string, number>;
    changes: {
      requirement_id: string;
      validation_name: string;
      vendor: string;
      status_a: string;
      status_b: string;
      change_type: string;
    }[];
  };
}

export const resolutionReasons = ["false_positive", "fixed", "accepted", "wont_fix"] as const;

export type ResolutionReason = (typeof resolutionReasons)[number] | "unspecified";

export interface ConflictSummary {
  id: number;
  requirement_a: string;
  requirement_b: string;
  pattern: string;
  confidence: string;
  resolved: boolean;
  resolution_reason: ResolutionReason;
  times_detected: number;
  last_seen_at: string;
  created_at: string;
}

export interface ConflictsPage {
  data: ConflictSummary[];
  meta: PagePosition;
}

export interface ConflictCountsResponse {
  data: ConflictCounts;
}

export interface ConflictCounts {
  open: number;
  open_high: number;
  open_medium: number;
  open_low: number;
  resolved: number;
  false_positive: number;
}

export interface MutualExclusionDetails {
  both_passed: number;
  a_passed_b_failed: number;
  a_failed_b_passed: number;
  both_failed: number;
  inverse_ratio: number;
}

export interface ConditionOverlapDetails {
  component: string;
  condition_a: string;
  condition_b: string;
  common_variables: string[];
  overlap_type: string;
  thresholds_a: number[];
  thresholds_b: number[];
}

export interface TimingConflictDetails {
  component: string;
  timing_a: string;
  timing_b: string;
  seconds_a: number;
  seconds_b: number;
  ratio: number;
}

export interface ResponseContradictionDetails {
  component: string;
  condition_a: string;
  condition_b: string;
  response_a: string;
  response_b: string;
  contradiction_type: string;
  antonym_pair?: string[];
  common_words?: string[];
  shared_object?: string;
}

export type ConflictEvidence =
  | { pattern: "mutual_exclusion"; details: MutualExclusionDetails }
  | { pattern: "condition_overlap"; details: ConditionOverlapDetails }
  | { pattern: "timing_conflict"; details: TimingConflictDetails }
  | { pattern: "response_contradiction"; details: ResponseContradictionDetails };

export interface ConflictDetailResponse {
  data: {
    id: number;
    requirement_a: string;
    requirement_b: string;
    requirement_a_title: string;
    requirement_b_title: string;
    pattern: string;
    confidence: string;
    details: Record<string, unknown>;
    resolved: boolean;
    resolved_at: string | null;
    resolution_notes: string;
    resolution_reason: ResolutionReason;
    times_detected: number;
    last_seen_at: string;
    created_at: string;
  };
}

export interface ImpactReportResponse {
  data: {
    project: string;
    base: string;
    head: string;
    generated_at: string;
    changed_requirements: string[];
    affected_tests: string[];
    risk_score: number;
    risk_level: string;
    code?: {
      changed_files?: unknown;
      affected_tests?: string[];
      risk_score?: number;
      risk_level?: string;
      blast?: {
        directly_changed?: string[];
        affected_requirements?: string[];
        affected_modules?: string[];
        affected_projects?: string[];
        cross_project_edges?: number;
        graph_risk_score?: number;
        graph_risk_level?: string;
      };
      edge_summary?: { annotated: number; inferred: number; contract: number };
      traversed_edges?: { annotated: number; inferred: number; contract: number };
    };
  };
}

export interface DriftIssue {
  type: string;
  id?: string;
  message: string;
  test_nodeid?: string;
  requirement_id?: string;
  title?: string;
  source_file?: string;
  path?: string;
}

export interface DriftReportResponse {
  data: {
    project: string;
    generated_at: string;
    errors: DriftIssue[];
    warnings: DriftIssue[];
    summary: Record<string, number>;
  };
}

export interface DetectConflictsResult {
  data: {
    conflicts_found: number;
    logged: number;
    skipped_existing: number;
  };
}

export interface MergeSafetyConflictItem {
  id: number;
  requirement_a: string;
  requirement_b: string;
  pattern: string;
  confidence: string;
  resolved: boolean;
  created_at: string;
}

export interface MergeSafetyResponse {
  data: {
    generated_at: string;
    verdict: "safe" | "needs_review" | "blocked";
    impact: ImpactReportResponse["data"] | null;
    drift: DriftReportResponse["data"] | null;
    conflicts: {
      open_count: number;
      items: MergeSafetyConflictItem[];
    };
  };
}

export interface RunningFlowRuns {
  data: {
    runs: {
      id: number;
      flow_name: string;
      flow_display_name: string;
      started_at: string;
      total_steps: number;
      completed_steps: number;
      current_step: string | null;
      current_step_order: number | null;
    }[];
  };
}

export interface LatestTestRun {
  test_run: {
    id: number;
    imported_at: string;
    source_file: string;
    git_sha: string;
    git_branch: string;
    workflow_name: string;
    workflow_run_id: string;
    repository: string;
    total_tests: number;
    passed: number;
    failed: number;
    errors: number;
    skipped: number;
  } | null;
}

export interface CorpusReviewSummary {
  id: number;
  requirement_id: string;
  spec_file: string;
  reviewer: string;
  outcome: string;
  created_at: string;
  snapshot_hash: string;
  coverage_count: number;
  findings_count: number;
}

export interface CorpusReviewsResponse {
  data: CorpusReviewSummary[];
  meta: PagePosition;
}

export interface CorpusReviewCoverage {
  matched_by: string[];
  cited: boolean;
  entry_version_id: number;
  enforcement: string;
  entry_title: string;
  entry_kind: string;
}

export interface CorpusReviewFinding {
  finding_type: string;
  check_id: string;
  detail: string;
  enforcement: string;
}

export interface CorpusReviewDetail extends CorpusReviewSummary {
  coverage: CorpusReviewCoverage[];
  findings: CorpusReviewFinding[];
}

export interface SloStatus {
  name: string;
  display_name: string;
  service: string;
  target: number | null;
  time_window: string;
  budgeting_method: string;
  status: string;
  current_value: number | null;
  error_budget_remaining: number | null;
  last_updated: string | null;
  requirement_ids: string[];
}

export interface VendorCoverageReport {
  data: {
    project: string;
    vendors: {
      name: string;
      total: number;
      passing: number;
      failing: number;
      not_run: number;
      pass_rate: number;
      regressions: { name: string; regressed_at: string; run_id: number }[];
      common_flags: { flag: string; count: number }[];
    }[];
    all_flags: string[];
    total_vendors: number;
    total_validations: number;
  };
}

export interface CoverageSnapshot {
  commit_sha: string;
  git_branch: string;
  generated_at: string;
  stored_at: string;
  specification_rate: number;
  structure_rate: number;
  verification_rate: number;
  total: number;
  non_draft: number;
  passing: number;
}

export interface CoverageTrend {
  data: {
    project: string;
    snapshots: CoverageSnapshot[];
  };
}

export interface ThroughputWeek {
  week: string;
  merged: number;
  rejected_at_spec: number;
  abandoned_at_review: number;
}

export interface RefusalCount {
  code: string;
  count: number;
}

export interface StateDuration {
  status: string;
  median_seconds: number;
  samples: number;
}

export interface IntentScorePoint {
  task_id: string;
  commit_sha: string;
  created_at: string;
  strategic: number;
  opportunity: number;
  drift: number;
  passed: boolean;
}

export interface RegressionWeek {
  week: string;
  merged: number;
  failed_later: number;
}

export interface FactoryReport {
  since: string;
  weeks: string[];
  throughput: ThroughputWeek[];
  refusals: RefusalCount[];
  state_durations: StateDuration[];
  intent_scores: IntentScorePoint[];
  regressions: RegressionWeek[];
}

export interface FactoryReportResponse {
  data: FactoryReport;
}

export interface SpecDecisionResult {
  data: {
    task_id: string;
    from_status: string;
    to_status: string;
    message: string;
  };
}
