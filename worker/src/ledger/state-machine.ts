export const TASK_STATUSES = [
  "draft",
  "unclaimed",
  "claimed",
  "in_progress",
  "ready_for_review",
  "changes_requested",
  "approved",
  "merged",
  "blocked",
  "abandoned",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const ALLOWED_TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
  draft: ["unclaimed", "abandoned"],
  unclaimed: ["claimed", "blocked"],
  claimed: ["in_progress", "unclaimed"],
  in_progress: ["ready_for_review", "blocked"],
  ready_for_review: ["approved", "changes_requested"],
  changes_requested: ["ready_for_review", "abandoned"],
  approved: ["merged"],
  blocked: ["unclaimed", "abandoned"],
  merged: [],
  abandoned: [],
};

export const AGENT_ROLES = ["planner", "coder", "reviewer"] as const;
export type AgentRole = (typeof AGENT_ROLES)[number];

export const REVIEW_DECISIONS = ["approved", "changes_requested", "rejected"] as const;
export type ReviewDecision = (typeof REVIEW_DECISIONS)[number];

export const DECISION_STATUS: Record<ReviewDecision, TaskStatus> = {
  approved: "approved",
  changes_requested: "changes_requested",
  rejected: "abandoned",
};

export type TransitionCode =
  | "INVALID_TRANSITION"
  | "AGENT_NOT_FOUND"
  | "AGENT_INACTIVE"
  | "TASK_NOT_FOUND"
  | "ROLE_NOT_ALLOWED"
  | "AGENT_BUSY"
  | "DEPENDENCIES_NOT_MET"
  | "NOT_OWNER"
  | "SELF_REVIEW_NOT_ALLOWED"
  | "SELF_INTENT_NOT_ALLOWED"
  | "BRANCH_DRIFTED"
  | "NOT_READY_FOR_REVIEW"
  | "NOT_APPROVED"
  | "NOT_CLAIMED"
  | "NOT_DRAFT"
  | "SPEC_INCOMPLETE"
  | "INTENT_NOT_VALIDATED"
  | "INTENT_FAILED"
  | "LINKED_TESTS_NOT_PASSING";

export class TransitionError extends Error {
  constructor(
    message: string,
    readonly code: TransitionCode,
  ) {
    super(message);
    this.name = "TransitionError";
  }
}

export interface TransitionResult {
  success: true;
  task_id: string;
  from_status: TaskStatus;
  to_status: TaskStatus;
  message: string;
  [detail: string]: unknown;
}

export type Transition = { ok: true; result: TransitionResult } | { ok: false; code: TransitionCode; message: string };

export function assertTransition(from: TaskStatus, to: TaskStatus): void {
  const allowed = ALLOWED_TRANSITIONS[from];
  if (!allowed.includes(to)) {
    throw new TransitionError(
      `Cannot transition from '${from}' to '${to}'. Allowed: [${allowed.map((s) => `'${s}'`).join(", ")}]`,
      "INVALID_TRANSITION",
    );
  }
}

export interface DoneWhenResult {
  criterion: string;
  passed: boolean;
  notes?: string;
}

export interface ReviewInput {
  reviewer_id: string;
  decision: ReviewDecision;
  feedback: string;
  done_when_results: DoneWhenResult[];
  blocking_issues: string[];
  suggestions: string[];
}

export interface OutcomePayload {
  task_id: string;
  title: string;
  status: "merged" | "abandoned";
  done_when_results: DoneWhenResult[] | null;
  reason: string | null;
  commit_sha: string;
  branch: string;
  merge_sha: string;
  attempt_count: number;
  max_attempts: number;
  occurred_at: string;
  task_created_at: string;
}

export const INTENT_PASS_THRESHOLD = 70;

export interface IntentScores {
  strategic_score: number;
  opportunity_score: number;
  drift_score: number;
}

export function intentPassed(scores: IntentScores): boolean {
  return Object.values(scores).every((score) => score >= INTENT_PASS_THRESHOLD);
}
