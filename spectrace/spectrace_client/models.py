"""Core data models for SpecTrace validation SDK.

These are dataclasses (not Django models) used for structuring
validation results before submitting to SpecTrace API.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ValidationStatus(str, Enum):
    """Status of a validation run."""
    SUCCESS = "success"
    DEGRADED = "degraded"  # Some steps passed, some failed
    FAILURE = "failure"
    ERROR = "error"  # Unexpected exception during validation


@dataclass
class ValidationStep:
    """Single step within a validation run.
    
    Represents one check in a multi-step validation (e.g., "authentication",
    "permissions", "connectivity").
    """
    name: str
    passed: bool
    details: str = ""
    error_message: str = ""
    duration_ms: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for API submission."""
        return {
            "name": self.name,
            "passed": self.passed,
            "details": self.details,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of a complete validation run.
    
    Contains overall status, individual steps, and context for debugging.
    """
    requirement_id: str
    name: str
    status: ValidationStatus
    steps: list[ValidationStep] = field(default_factory=list)
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    
    @property
    def overall_status(self) -> ValidationStatus:
        """Compute overall status from individual steps.
        
        Logic:
        - No steps: use self.status
        - All steps passed: SUCCESS
        - All steps failed: FAILURE
        - Mixed: DEGRADED
        """
        if not self.steps:
            return self.status
        
        passed_count = sum(1 for s in self.steps if s.passed)
        failed_count = len(self.steps) - passed_count
        
        if failed_count == 0:
            return ValidationStatus.SUCCESS
        elif passed_count > 0:
            return ValidationStatus.DEGRADED
        else:
            return ValidationStatus.FAILURE
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for API submission."""
        return {
            "requirement_id": self.requirement_id,
            "name": self.name,
            "status": self.overall_status.value,
            "message": self.message,
            "steps": [step.to_dict() for step in self.steps],
            "context": self.context,
            "checked_at": self.timestamp.isoformat(),
        }
