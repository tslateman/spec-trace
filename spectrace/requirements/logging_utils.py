"""Structured logging utilities."""

import logging
from contextvars import ContextVar

# Request correlation ID stored as a context variable
# This allows the ID to be automatically available in async contexts
request_id: ContextVar[str] = ContextVar("request_id", default="")


class StructuredAdapter(logging.LoggerAdapter):
    """Adds structured context to log records.

    Automatically includes request_id from the context variable,
    making it easy to correlate logs across a request lifecycle.
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["request_id"] = request_id.get("")
        if self.extra:
            extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> StructuredAdapter:
    """Get a structured logger for a module.

    Usage:
        from requirements.logging_utils import get_logger
        logger = get_logger(__name__)

        # Logs will include request_id automatically
        logger.info("Processing validation", extra={'validation_id': 123})

    Args:
        name: Module name (typically __name__)

    Returns:
        StructuredAdapter wrapping the module's logger
    """
    return StructuredAdapter(logging.getLogger(name), {})
