"""msgspec Struct definitions for SpecTrace API request/response schemas."""

from msgspec import Struct


# === SLO Status ===

class SLOStatusItem(Struct):
    """Individual SLO status update."""

    name: str
    status: str  # met, at_risk, breached
    current_value: float | None = None
    error_budget_remaining: float | None = None


class SLOStatusRequest(Struct):
    """Request body for POST /api/slo/status/."""

    slos: list[SLOStatusItem]
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

    name: str
    passed: bool
    details: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None


class ValidationItem(Struct, kw_only=True):
    """Individual validation result in a submission."""

    requirement_id: str
    name: str
    status: str  # success, failure, unknown
    message: str = ""
    endpoint: str = ""
    checked_at: str | None = None
    steps: list[ValidationStep] = []
    context: dict | None = None  # Flexible dict to preserve all context fields


class ValidationResultRequest(Struct):
    """Request body for POST /api/validation/result/."""

    source: str
    validations: list[ValidationItem]
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

    name: str
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


# === Error Response ===

class ErrorResponse(Struct):
    """Standard error response."""

    success: bool = False
    error: str = ""
