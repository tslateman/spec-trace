"""Health check utilities for external integrations."""


def _sanitize_response(response_text: str, max_length: int = 500) -> str:
    """Sanitize API response by removing credentials and truncating.

    Removes:
    - Linear API keys (lin_api_...)
    - Bearer tokens
    - Authorization header values

    Args:
        response_text: Raw response body
        max_length: Maximum length of sanitized response

    Returns:
        Sanitized response string safe for logging/storage
    """
    import re

    # Truncate first to limit processing
    sanitized = response_text[:max_length]

    # Remove API key patterns (lin_api_...)
    sanitized = re.sub(r'lin_api_[A-Za-z0-9_-]+', '[REDACTED]', sanitized)

    # Remove bearer tokens
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_.-]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)

    # Remove authorization headers in JSON
    sanitized = re.sub(r'"authorization":\s*"[^"]*"', '"authorization": "[REDACTED]"', sanitized, flags=re.IGNORECASE)

    if len(response_text) > max_length:
        sanitized += '... [truncated]'

    return sanitized
