"""Decorator for API endpoints with schema validation and OpenAPI metadata."""

from functools import wraps
from typing import Any, Callable, TypeVar

import msgspec
from django.http import HttpRequest, JsonResponse

F = TypeVar("F", bound=Callable[..., Any])


def validate_request(
    *,
    request_schema: type[msgspec.Struct] | None = None,
    response_schema: type[msgspec.Struct] | None = None,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    methods: list[str] | None = None,
    requires_auth: bool = False,
    query_parameters: list[dict] | None = None,
) -> Callable[[F], F]:
    """Decorator for API endpoints with schema validation and OpenAPI metadata.

    Args:
        request_schema: msgspec Struct type for validating request body (POST/PUT/PATCH).
        response_schema: msgspec Struct type for documenting response body.
        tags: OpenAPI tags for categorizing the endpoint.
        summary: Short description for the endpoint.
        description: Longer description for the endpoint (uses docstring if not provided).
        methods: HTTP methods this endpoint accepts (for OpenAPI docs).

    Example:
        @validate_request(
            request_schema=SLOStatusRequest,
            response_schema=SLOStatusResponse,
            tags=["SLO"],
            summary="Update SLO status",
            methods=["POST"],
        )
        def update_slo_status(request, data: SLOStatusRequest | None = None):
            ...
    """

    def decorator(view_func: F) -> F:
        # Store metadata for OpenAPI generation
        view_func._openapi_request_schema = request_schema  # type: ignore[attr-defined]
        view_func._openapi_response_schema = response_schema  # type: ignore[attr-defined]
        view_func._openapi_tags = tags or []  # type: ignore[attr-defined]
        view_func._openapi_summary = summary  # type: ignore[attr-defined]
        view_func._openapi_description = description  # type: ignore[attr-defined]
        view_func._openapi_methods = methods  # type: ignore[attr-defined]
        view_func._openapi_requires_auth = requires_auth  # type: ignore[attr-defined]
        view_func._openapi_query_parameters = query_parameters or []  # type: ignore[attr-defined]

        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            data = None

            # Validate request body for POST/PUT/PATCH methods
            if request_schema and request.method in ("POST", "PUT", "PATCH"):
                # Only parse JSON if content type indicates JSON and body is not empty
                content_type = request.content_type or ""
                if "application/json" in content_type and request.body:
                    try:
                        data = msgspec.json.decode(request.body, type=request_schema)
                    except msgspec.DecodeError as e:
                        return JsonResponse(
                            {"success": False, "error": f"Invalid JSON: {e}"},
                            status=400,
                        )
                    except msgspec.ValidationError as e:
                        return JsonResponse(
                            {"success": False, "error": f"Invalid JSON: {e}"},
                            status=400,
                        )

            # Pass the validated data to the view
            kwargs["data"] = data
            return view_func(request, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_openapi_metadata(view_func: Callable[..., Any]) -> dict[str, Any]:
    """Extract OpenAPI metadata from a decorated view function.

    Returns:
        Dict containing request_schema, response_schema, tags, summary, description, and methods.
    """
    return {
        "request_schema": getattr(view_func, "_openapi_request_schema", None),
        "response_schema": getattr(view_func, "_openapi_response_schema", None),
        "tags": getattr(view_func, "_openapi_tags", []),
        "summary": getattr(view_func, "_openapi_summary", None),
        "description": getattr(view_func, "_openapi_description", None),
        "methods": getattr(view_func, "_openapi_methods", None),
        "requires_auth": getattr(view_func, "_openapi_requires_auth", False),
        "query_parameters": getattr(view_func, "_openapi_query_parameters", []),
    }
