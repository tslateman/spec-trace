"""Custom exceptions for SpecTrace client SDK."""


class SpecTraceAPIError(Exception):
    """Raised when SpecTrace API request fails."""

    pass


class ValidationConfigError(Exception):
    """Raised when SDK configuration is invalid."""

    pass
