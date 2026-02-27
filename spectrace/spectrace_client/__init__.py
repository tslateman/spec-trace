"""SpecTrace In-App Validation SDK.

This SDK enables engineers to add "Test Connection" validation buttons with 5 lines
of code to validate real integration configurations and report results to SpecTrace.

Usage:
    from spectrace_client import verify_requirement, ValidationRun

    @verify_requirement("REQ-PMS-OPERA-001", name="Opera PMS Connection")
    def verify_opera_connection(hotel, validation_run: ValidationRun):
        validation_run.step("config", passed=True, details="Config found")
        validation_run.step("auth", passed=False, error_message="Login failed")
        return validation_run.result
"""

# Core validation components
# Django admin helpers
from .admin import create_validation_action
from .client import ValidationClient
from .context import ValidationRun
from .decorators import verify_requirement

# Exceptions
from .exceptions import SpecTraceAPIError, ValidationConfigError

# Feature flags
from .feature_flags import (
    extract_feature_flags,
    get_django_feature_flags,
    get_env_feature_flags,
    get_model_feature_flags,
    with_feature_flags,
)

# Data models
from .models import ValidationResult, ValidationStatus, ValidationStep

__all__ = [
    # Core
    "ValidationClient",
    "ValidationRun",
    "verify_requirement",
    # Models
    "ValidationResult",
    "ValidationStatus",
    "ValidationStep",
    # Admin
    "create_validation_action",
    # Exceptions
    "SpecTraceAPIError",
    "ValidationConfigError",
    # Feature flags
    "extract_feature_flags",
    "get_django_feature_flags",
    "get_env_feature_flags",
    "get_model_feature_flags",
    "with_feature_flags",
]

__version__ = "0.1.0"
