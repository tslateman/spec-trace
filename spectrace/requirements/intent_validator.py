"""Logic for evaluating and recording intent-to-execution validation."""

from typing import Any, Dict

from requirements.models import AgentTask, IntentValidationResult


class ValidationError(Exception):
    """Raised when validation data is invalid or cannot be processed."""

    pass


def record_validation(
    task_id: str, commit_sha: str, eval_data: Dict[str, Any]
) -> IntentValidationResult:
    """Record an intent validation result from an external LLM evaluation.

    Args:
        task_id: The external ID of the task being validated
        commit_sha: The commit SHA or diff hash evaluated
        eval_data: Structured JSON output from the LLM evaluation

    Returns:
        The created IntentValidationResult record

    Raises:
        ValidationError: If the task is not found or evaluation data is invalid
    """
    try:
        task = AgentTask.objects.get(external_id=task_id)
    except AgentTask.DoesNotExist:
        raise ValidationError(f"Task not found: {task_id}")

    # Extract scores, handling string or int formats
    try:
        strategic_score = int(eval_data.get("strategic_score", 0))
        opportunity_score = int(eval_data.get("opportunity_score", 0))
        drift_score = int(eval_data.get("drift_score", 0))
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid score format in evaluation data: {e}")

    # Determine pass/fail based on thresholds (all scores must be >= 70)
    passed = strategic_score >= 70 and opportunity_score >= 70 and drift_score >= 70

    # Allow override from the eval data if provided explicitly
    if "passed" in eval_data:
        passed_raw = eval_data["passed"]
        if isinstance(passed_raw, bool):
            passed = passed_raw
        elif isinstance(passed_raw, str):
            passed = passed_raw.lower() == "true"

    # Extract failure reasons
    failure_reasons = eval_data.get("failure_reasons", [])
    if not isinstance(failure_reasons, list):
        failure_reasons = [str(failure_reasons)]

    # Create the record
    result = IntentValidationResult.objects.create(
        task=task,
        commit_sha=commit_sha,
        strategic_score=strategic_score,
        opportunity_score=opportunity_score,
        drift_score=drift_score,
        passed=passed,
        failure_reasons=failure_reasons,
    )

    return result
