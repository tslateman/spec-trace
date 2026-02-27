"""Custom middleware for request handling."""

import uuid

from django.http import JsonResponse

from .constants import MAX_REQUEST_BODY_SIZE
from .logging_utils import request_id


class RequestSizeLimitMiddleware:
    """Reject requests with bodies larger than configured limit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
                if size > MAX_REQUEST_BODY_SIZE:
                    max_mb = MAX_REQUEST_BODY_SIZE // 1024 // 1024
                    return JsonResponse(
                        {"error": f"Request body too large (max {max_mb}MB)"},
                        status=413,
                    )
            except ValueError:
                pass
        return self.get_response(request)


class RequestIDMiddleware:
    """Add unique request ID for log correlation.

    Reads X-Request-ID header if present (for tracing across services),
    otherwise generates a short UUID. Sets the ID in a context variable
    for use by structured logging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request_id.set(rid)
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        return response
