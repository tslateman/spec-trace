"""Client for submitting validation results to SpecTrace API."""

import logging
import os

import requests
from django.conf import settings

from .models import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)


class ValidationClient:
    """Client for submitting validation results to SpecTrace API.

    Reads configuration from environment variables or Django settings:
    - SPECTRACE_URL / settings.SPECTRACE['API_URL']
    - SPECTRACE_API_KEY / settings.SPECTRACE['API_KEY']
    - SPECTRACE_ENABLED / settings.SPECTRACE['ENABLED']

    Best-effort submission: Logs warnings on failure but doesn't raise exceptions.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        enabled: bool = True,
        timeout: int = 10,
    ):
        """Initialize validation client.

        Args:
            api_url: SpecTrace API base URL
            api_key: Optional API key for authentication
            enabled: Whether to actually submit validations
            timeout: Request timeout in seconds
        """
        self.api_url = (api_url or self._get_default_url()).rstrip("/")
        self.api_key = api_key
        self.enabled = enabled
        self.timeout = timeout
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    @classmethod
    def from_settings(cls) -> "ValidationClient":
        """Create client from Django settings and environment variables.

        Environment variables take precedence over Django settings.
        """
        # Check environment variables first
        api_url = os.environ.get("SPECTRACE_URL")
        api_key = os.environ.get("SPECTRACE_API_KEY")
        enabled_str = os.environ.get("SPECTRACE_ENABLED", "true").lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        # Override with Django settings if present
        if hasattr(settings, "SPECTRACE"):
            config = settings.SPECTRACE
            api_url = config.get("API_URL", api_url)
            api_key = config.get("API_KEY", api_key)
            enabled = config.get("ENABLED", enabled)

        return cls(
            api_url=api_url,
            api_key=api_key,
            enabled=enabled,
        )

    def _get_default_url(self) -> str:
        """Get default API URL from environment or fallback."""
        return os.environ.get("SPECTRACE_URL", "http://localhost:8000")

    def submit_validation(self, result: ValidationResult) -> bool:
        """Submit validation result to SpecTrace.

        Best-effort submission: logs error but doesn't raise on failure.

        Args:
            result: ValidationResult to submit

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug(
                "SpecTrace client disabled, skipping validation submission for %s",
                result.requirement_id,
            )
            return True

        try:
            url = f"{self.api_url}/api/v1/results/enforcement/"
            payload = {
                "source": "spectrace-client",
                "validations": [result.to_dict()],
            }

            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            logger.info(
                "Submitted validation for %s: %s",
                result.requirement_id,
                result.overall_status.value,
            )
            return True

        except requests.RequestException as e:
            # Log warning but don't fail the validation
            logger.warning(
                "Failed to submit validation to SpecTrace for %s: %s",
                result.requirement_id,
                e,
                exc_info=True,
            )
            return False

    def submit_validation_dict(
        self,
        requirement_id: str,
        name: str,
        status: str,
        message: str = "",
        context: dict | None = None,
    ) -> bool:
        """Submit simple validation without steps (convenience method).

        Args:
            requirement_id: Requirement ID (e.g., "REQ-PMS-OPERA-001")
            name: Human-readable validation name
            status: Status string ("success", "failure", "degraded", "error")
            message: Optional status message
            context: Optional context dict (hotel_id, vendor, etc.)

        Returns:
            True if successful, False otherwise
        """
        result = ValidationResult(
            requirement_id=requirement_id,
            name=name,
            status=ValidationStatus(status),
            message=message,
            context=context or {},
        )
        return self.submit_validation(result)
