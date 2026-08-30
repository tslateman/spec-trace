"""URL pattern introspection for extracting API endpoint information."""

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import msgspec
from django.urls import URLPattern, URLResolver, get_resolver

from .decorators import get_openapi_metadata


@dataclass
class EndpointInfo:
    """Information about an API endpoint for OpenAPI generation."""

    path: str
    http_methods: list[str]
    name: str
    view_func: Callable[..., Any]
    request_schema: type[msgspec.Struct] | None = None
    response_schema: type[msgspec.Struct] | None = None
    tags: list[str] = field(default_factory=list)
    summary: str | None = None
    description: str | None = None
    path_parameters: list[dict[str, Any]] = field(default_factory=list)
    requires_auth: bool = False
    query_parameters: list[dict[str, Any]] = field(default_factory=list)


def _convert_django_path_to_openapi(path: str) -> tuple[str, list[dict[str, Any]]]:
    """Convert Django URL path to OpenAPI path format and extract parameters.

    Django: /api/v1/specs/<str:external_id>/status/
    OpenAPI: /api/v1/specs/{external_id}/status/

    Returns:
        Tuple of (openapi_path, path_parameters)
    """
    path_parameters: list[dict[str, Any]] = []

    # Pattern for Django path converters: <type:name> or <name>
    pattern = re.compile(r"<(?:(\w+):)?(\w+)>")

    def replace_param(match: re.Match[str]) -> str:
        param_type = match.group(1) or "str"
        param_name = match.group(2)

        # Map Django types to OpenAPI types
        type_mapping = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "slug": {"type": "string"},
            "uuid": {"type": "string", "format": "uuid"},
            "path": {"type": "string"},
        }

        param_schema = type_mapping.get(param_type, {"type": "string"})
        path_parameters.append(
            {
                "name": param_name,
                "in": "path",
                "required": True,
                "schema": param_schema,
            }
        )

        return f"{{{param_name}}}"

    openapi_path = pattern.sub(replace_param, path)
    return openapi_path, path_parameters


def _get_allowed_methods(view_func: Callable[..., Any]) -> list[str]:
    """Extract allowed HTTP methods from a view function.

    Looks for require_http_methods decorator or checks for method handlers.
    """
    # Check for allowed_methods attribute (set by require_http_methods)
    if hasattr(view_func, "allowed_methods"):
        return [m.lower() for m in view_func.allowed_methods]

    # Check wrapped function
    if hasattr(view_func, "__wrapped__"):
        return _get_allowed_methods(view_func.__wrapped__)

    # Default to GET if nothing found
    return ["get"]


def _walk_url_patterns(
    patterns: list[URLPattern | URLResolver],
    prefix: str = "",
) -> list[tuple[str, URLPattern]]:
    """Recursively walk URL patterns and collect all patterns with their full paths."""
    results = []

    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            # Recurse into included URL configs
            nested_prefix = prefix + str(pattern.pattern)
            results.extend(_walk_url_patterns(pattern.url_patterns, nested_prefix))
        elif isinstance(pattern, URLPattern):
            full_path = prefix + str(pattern.pattern)
            results.append((full_path, pattern))

    return results


def extract_api_endpoints(prefix: str = "api/") -> list[EndpointInfo]:
    """Extract all API endpoints with their schemas and metadata.

    Args:
        prefix: URL prefix to filter for API endpoints.

    Returns:
        List of EndpointInfo objects for all matching endpoints.
    """
    resolver = get_resolver()
    all_patterns = _walk_url_patterns(resolver.url_patterns)

    endpoints: list[EndpointInfo] = []

    for path, pattern in all_patterns:
        # Filter by prefix
        if not path.startswith(prefix):
            continue

        # Skip the openapi endpoint itself
        if "openapi" in path.lower():
            continue

        # Get the view function
        view_func = pattern.callback
        if view_func is None:
            continue

        if getattr(view_func, "is_legacy_route", False):
            continue

        # Unwrap decorators to find the actual view
        actual_view = view_func
        while hasattr(actual_view, "__wrapped__"):
            actual_view = actual_view.__wrapped__

        # Get OpenAPI metadata from the decorator
        metadata = get_openapi_metadata(view_func)

        # Get HTTP methods (from metadata or try to detect)
        http_methods = metadata.get("methods") or _get_allowed_methods(view_func)

        # Convert path to OpenAPI format
        openapi_path, path_params = _convert_django_path_to_openapi("/" + path)

        # Extract docstring as description if not provided
        description = metadata["description"]
        if description is None and actual_view.__doc__:
            description = actual_view.__doc__.strip()

        endpoints.append(
            EndpointInfo(
                path=openapi_path,
                http_methods=http_methods,
                name=pattern.name or "",
                view_func=view_func,
                request_schema=metadata["request_schema"],
                response_schema=metadata["response_schema"],
                tags=metadata["tags"],
                summary=metadata["summary"],
                description=description,
                path_parameters=path_params,
                requires_auth=metadata.get("requires_auth", False),
                query_parameters=metadata.get("query_parameters", []),
            )
        )

    return endpoints
