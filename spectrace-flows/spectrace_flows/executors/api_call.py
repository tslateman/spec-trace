"""HTTP request executor for api_call steps.

Executes HTTP requests and verifies status codes.
Stores JSON response in context for assertion steps.
"""

import requests

from spectrace_flows.types import VerificationCheck


def execute_api_call_step(
    step_def: dict, context: dict
) -> tuple[VerificationCheck, dict]:
    """Execute an HTTP request and verify the status code.

    Config options (from step_def):
        url: Request URL (required). If starts with '/', uses context['base_url'] as prefix.
        method: HTTP method (default: 'GET')
        expected_status: Expected HTTP status code (default: 200)
        headers: Request headers to merge with context['headers']
        body: Request body (for POST/PUT/PATCH)
        timeout: Request timeout in seconds (default: 30)

    Updates context:
        last_response: JSON response body (or {} if not JSON)

    Args:
        step_def: Step definition with api_call config
        context: Execution context with optional base_url, headers

    Returns:
        Tuple of (VerificationCheck, context_updates)
    """
    step_name = step_def.get("name", "api_call")
    config = step_def.get("config", {})

    # Extract config
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    expected_status = config.get("expected_status", 200)
    step_headers = config.get("headers", {})
    body = config.get("body")
    timeout = config.get("timeout", 30)

    # Build full URL
    if url.startswith("/"):
        base_url = context.get("base_url", "")
        url = f"{base_url.rstrip('/')}{url}"

    # Merge headers (context headers + step headers, step takes precedence)
    merged_headers = {**context.get("headers", {}), **step_headers}

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=merged_headers,
            json=body if body else None,
            timeout=timeout,
        )

        # Try to parse JSON response
        try:
            response_json = response.json()
        except (ValueError, requests.JSONDecodeError):
            response_json = {}

        # Truncate response body for storage
        response_body = response.text
        if len(response_body) > 1000:
            response_body = response_body[:1000] + "... [truncated]"

        # Check status code
        if response.status_code == expected_status:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=True,
                    details=f"{method} {url} returned {response.status_code}",
                    response_status=response.status_code,
                    response_body=response_body,
                ),
                {"last_response": response_json},
            )
        else:
            return (
                VerificationCheck(
                    name=step_name,
                    passed=False,
                    error_message=f"Expected status {expected_status}, got {response.status_code}",
                    response_status=response.status_code,
                    response_body=response_body,
                ),
                {"last_response": response_json},
            )

    except requests.Timeout:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Request timed out after {timeout} seconds",
            ),
            {},
        )

    except requests.ConnectionError as e:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Connection error: {e}",
            ),
            {},
        )

    except requests.RequestException as e:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Request error: {type(e).__name__}: {e}",
            ),
            {},
        )
