"""msgspec Struct definitions for SpecTrace API request/response schemas."""

from typing import Annotated

from msgspec import Meta, Struct

from requirements.constants import (
    MAX_ENDPOINT_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_NAME_LENGTH,
    MAX_REQUIREMENT_ID_LENGTH,
    MAX_SLOS_PER_REQUEST,
    MAX_SOURCE_LENGTH,
    MAX_STATUS_LENGTH,
    MAX_STEPS_PER_VALIDATION,
    MAX_URL_LENGTH,
    MAX_VALIDATIONS_PER_REQUEST,
    MAX_VENDOR_LENGTH,
)


# === SLO Status ===


class SLOStatusItem(Struct):
    """Individual SLO status update."""

    name: Annotated[str, Meta(max_length=MAX_NAME_LENGTH)]
    status: Annotated[str, Meta(max_length=MAX_STATUS_LENGTH)]  # met, at_risk, breached
    current_value: float | None = None
    error_budget_remaining: float | None = None


class SLOStatusRequest(Struct):
    """Request body for POST /api/slo/status/."""

    slos: Annotated[list[SLOStatusItem], Meta(max_length=MAX_SLOS_PER_REQUEST)]
    update_verification_status: bool = False


class SLOStatusResponse(Struct):
    """Response for POST /api/slo/status/."""

    success: bool
    updated: int
    not_found: int
    requirement_status: dict[str, int]


# === Validation Result ===


class ValidationStep(Struct):
    """Individual validation step result."""

    name: Annotated[str, Meta(max_length=MAX_NAME_LENGTH)]
    passed: bool
    details: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None


class ValidationItem(Struct, kw_only=True):
    """Individual validation result in a submission."""

    requirement_id: Annotated[str, Meta(max_length=MAX_REQUIREMENT_ID_LENGTH)]
    name: Annotated[str, Meta(max_length=MAX_NAME_LENGTH)]
    status: Annotated[
        str, Meta(max_length=MAX_STATUS_LENGTH)
    ]  # success, failure, unknown
    message: Annotated[str, Meta(max_length=MAX_MESSAGE_LENGTH)] = ""
    endpoint: Annotated[str, Meta(max_length=MAX_ENDPOINT_LENGTH)] = ""
    checked_at: str | None = None
    steps: Annotated[
        list[ValidationStep], Meta(max_length=MAX_STEPS_PER_VALIDATION)
    ] = []
    context: dict | None = None  # Flexible dict to preserve all context fields


class ValidationResultRequest(Struct):
    """Request body for POST /api/validation/result/."""

    source: Annotated[str, Meta(max_length=MAX_SOURCE_LENGTH)]
    validations: Annotated[
        list[ValidationItem], Meta(max_length=MAX_VALIDATIONS_PER_REQUEST)
    ]
    update_verification_status: bool = False


class ValidationResultResponse(Struct):
    """Response for POST /api/validation/result/."""

    success: bool
    imported: int
    skipped: int
    created_validations: int
    successful: int
    failed: int


# === Requirement Status ===


class RequirementStatusResponse(Struct):
    """Response for GET /api/requirement/{external_id}/status/."""

    external_id: str
    title: str
    verification_method: str
    verification_status: str
    slo_status: str
    test_status: str
    inapp_status: str
    linked_tests: int
    linked_slos: int
    linked_validations: int


# === Linear Integration ===


class LinearTestRequest(Struct, kw_only=True):
    """Request body for POST /api/integrations/linear/test-connection/."""

    api_key: str | None = None
    workspace: str | None = None
    team: str | None = None


class HealthCheck(Struct):
    """Individual health check result."""

    name: Annotated[str, Meta(max_length=MAX_NAME_LENGTH)]
    passed: bool
    details: str | None = None
    error_message: str | None = None
    timestamp: str | None = None


class LinearTestResponse(Struct, kw_only=True):
    """Response for POST /api/integrations/linear/test-connection/."""

    success: bool
    message: str
    status: str  # healthy, degraded, unhealthy
    checks: list[HealthCheck] | None = None
    error_details: str | None = None
    cached: bool = False


class LinearHealthResponse(Struct, kw_only=True):
    """Response for GET /api/integrations/linear/health/."""

    success: bool
    message: str
    status: str  # healthy, degraded, unhealthy, unknown
    checks: list[HealthCheck] | None = None
    error_details: str | None = None
    cached: bool = False
    cache_remaining_seconds: int | None = None


# === Validation Runs ===


class PaginationInfo(Struct):
    """Pagination metadata."""

    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ValidationRunSummary(Struct):
    """Summary of a validation run."""

    id: int
    source: str
    imported_at: str
    total_validations: int
    successful: int
    failed: int


class ValidationRunsResponse(Struct):
    """Response for GET /api/validation-runs/."""

    runs: list[ValidationRunSummary]
    pagination: PaginationInfo


class ValidationRunResult(Struct):
    """Individual result in a validation run detail."""

    id: int
    validation_id: int
    validation_name: str
    requirement_id: str
    vendor: str
    status: str
    message: str
    checked_at: str
    step_count: int
    steps_passed: int


class ValidationRunDetailResponse(Struct):
    """Response for GET /api/validation-runs/{id}/."""

    id: int
    source: str
    imported_at: str
    total_validations: int
    successful: int
    failed: int
    results: list[ValidationRunResult]


class StepResult(Struct):
    """Result with step-level detail."""

    result_id: int
    validation_name: str
    requirement_id: str
    status: str
    steps: list[ValidationStep]
    context: dict


class ValidationRunStepsResponse(Struct):
    """Response for GET /api/validation-runs/{id}/steps/."""

    run_id: int
    results: list[StepResult]


# === Conflicts ===


class ConflictSummary(Struct):
    """Summary of a conflict between two requirements."""

    id: int
    requirement_a: str  # external_id
    requirement_b: str  # external_id
    pattern: str  # mutual_exclusion, condition_overlap, timing_conflict, response_contradiction
    confidence: str  # high, medium, low
    resolved: bool
    created_at: str


class ConflictDetail(Struct, kw_only=True):
    """Full conflict detail."""

    id: int
    requirement_a: str
    requirement_b: str
    requirement_a_title: str
    requirement_b_title: str
    pattern: str
    confidence: str
    details: dict
    resolved: bool
    resolved_at: str | None = None
    resolution_notes: str = ""
    created_at: str


class ConflictListResponse(Struct):
    """Response for GET /api/conflicts/."""

    conflicts: list[ConflictSummary]
    pagination: PaginationInfo


class ConflictDetailResponse(Struct):
    """Response for GET /api/conflicts/{id}/."""

    conflict: ConflictDetail


class ConflictDetectRequest(Struct, kw_only=True):
    """Request body for POST /api/conflicts/detect/."""

    min_runs: int = 10
    min_overlap: int = 5
    include_structured: bool = True


class ConflictDetectResponse(Struct):
    """Response for POST /api/conflicts/detect/."""

    success: bool
    conflicts_found: int
    logged: int
    skipped_existing: int


class ConflictResolveRequest(Struct):
    """Request body for POST /api/conflicts/{id}/resolve/."""

    resolution_notes: Annotated[str, Meta(max_length=MAX_MESSAGE_LENGTH)]


class ConflictResolveResponse(Struct):
    """Response for POST /api/conflicts/{id}/resolve/."""

    success: bool
    conflict_id: int
    resolved_at: str


# === Error Response ===


class ErrorResponse(Struct):
    """Standard error response."""

    success: bool = False
    error: str = ""


# === Flow Runs ===


class FlowRunStep(Struct):
    id: int
    flow_name: str
    flow_display_name: str
    started_at: str
    total_steps: int
    completed_steps: int
    current_step: str | None
    current_step_order: int | None


class RunningFlowRunsResponse(Struct):
    runs: list[FlowRunStep]


# === Test Runs ===


class TestRunSummary(Struct):
    id: int
    imported_at: str
    source_file: str | None = None
    git_sha: str | None = None
    git_branch: str | None = None
    workflow_name: str | None = None
    workflow_run_id: str | None = None
    repository: str | None = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0


class LatestTestRunResponse(Struct):
    test_run: TestRunSummary | None
