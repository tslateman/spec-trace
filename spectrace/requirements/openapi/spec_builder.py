"""Build complete OpenAPI 3.1 specification from extracted endpoints."""

from typing import Any

from .introspection import EndpointInfo, extract_api_endpoints
from .schema_generator import collect_schemas_from_endpoints, get_schema_ref
from .schemas import ErrorResponse


def _build_operation(
    endpoint: EndpointInfo,
    method: str,
) -> dict[str, Any]:
    """Build an OpenAPI operation object for an endpoint/method combination."""
    operation: dict[str, Any] = {}

    # Add tags
    if endpoint.tags:
        operation["tags"] = endpoint.tags

    # Add summary
    if endpoint.summary:
        operation["summary"] = endpoint.summary
    elif endpoint.name:
        # Generate a summary from the name
        operation["summary"] = endpoint.name.replace("-", " ").replace("_", " ").title()

    # Add description
    if endpoint.description:
        # Clean up docstring formatting
        lines = endpoint.description.split("\n")
        # Take only the first paragraph (up to first blank line)
        description_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                break
            description_lines.append(stripped)
        if description_lines:
            operation["description"] = " ".join(description_lines)

    # Add operationId
    if endpoint.name:
        operation["operationId"] = f"{endpoint.name}_{method}"

    # Add path parameters
    if endpoint.path_parameters:
        operation["parameters"] = endpoint.path_parameters.copy()

    # Add request body for POST/PUT/PATCH
    if method in ("post", "put", "patch") and endpoint.request_schema:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": get_schema_ref(endpoint.request_schema),
                }
            },
        }

    # Add responses
    operation["responses"] = _build_responses(endpoint)

    return operation


def _build_responses(endpoint: EndpointInfo) -> dict[str, Any]:
    """Build the responses object for an endpoint."""
    responses: dict[str, Any] = {}

    # Success response
    if endpoint.response_schema:
        responses["200"] = {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": get_schema_ref(endpoint.response_schema),
                }
            },
        }
    else:
        responses["200"] = {
            "description": "Successful response",
        }

    # Error responses
    responses["400"] = {
        "description": "Bad request - invalid input",
        "content": {
            "application/json": {
                "schema": get_schema_ref(ErrorResponse),
            }
        },
    }

    responses["404"] = {
        "description": "Resource not found",
        "content": {
            "application/json": {
                "schema": get_schema_ref(ErrorResponse),
            }
        },
    }

    return responses


def _build_paths(endpoints: list[EndpointInfo]) -> dict[str, Any]:
    """Build the paths object from a list of endpoints."""
    paths: dict[str, Any] = {}

    for endpoint in endpoints:
        path_item: dict[str, Any] = {}

        for method in endpoint.http_methods:
            method_lower = method.lower()
            path_item[method_lower] = _build_operation(endpoint, method_lower)

        paths[endpoint.path] = path_item

    return paths


def build_openapi_spec(
    title: str = "SpecTrace API",
    version: str = "1.0.0",
    description: str | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Build a complete OpenAPI 3.1 specification.

    Args:
        title: API title.
        version: API version.
        description: API description.
        server_url: Base URL for the API (optional).

    Returns:
        Complete OpenAPI 3.1 specification as a dict.
    """
    # Extract endpoints from URL configuration
    endpoints = extract_api_endpoints(prefix="api/")

    # Collect all schemas
    schemas = collect_schemas_from_endpoints(endpoints)

    # Add ErrorResponse schema if not already present
    if "ErrorResponse" not in schemas:
        from msgspec import json as msgspec_json

        error_schema = msgspec_json.schema(ErrorResponse)
        error_schema.pop("$schema", None)
        schemas["ErrorResponse"] = error_schema

    # Build the spec
    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": version,
        },
        "paths": _build_paths(endpoints),
        "components": {
            "schemas": schemas,
        },
    }

    # Add optional description
    if description:
        spec["info"]["description"] = description

    # Add servers if provided
    if server_url:
        spec["servers"] = [{"url": server_url}]

    # Add tags for organization
    spec["tags"] = _collect_tags(endpoints)

    return spec


def _collect_tags(endpoints: list[EndpointInfo]) -> list[dict[str, str]]:
    """Collect unique tags from all endpoints."""
    seen_tags: set[str] = set()
    tags: list[dict[str, str]] = []

    for endpoint in endpoints:
        for tag in endpoint.tags:
            if tag not in seen_tags:
                seen_tags.add(tag)
                tags.append({"name": tag})

    return tags
