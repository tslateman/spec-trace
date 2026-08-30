"""Redirects from the retired unversioned API surface to `/api/v1/`.

Register `redirect_to_v1("api-v1-...")` in place of a legacy view to answer the
old path with a redirect that carries RFC 8594 deprecation headers. Use
`legacy_alias` only where the caller cannot follow a redirect.
"""

import json
from functools import wraps

from django.http import HttpResponsePermanentRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

LEGACY_API_SUNSET = "Sat, 28 Nov 2026 00:00:00 GMT"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def redirect_to_v1(v1_url_name):
    """Return a view redirecting a legacy path to the named `/api/v1/` route.

    Path captures pass through as keyword arguments to `reverse`, so the legacy
    and v1 routes must name their captures identically.
    """

    @csrf_exempt
    def redirect_view(request, **kwargs):
        location = reverse(v1_url_name, kwargs=kwargs)
        query_string = request.META.get("QUERY_STRING", "")
        if query_string:
            location = f"{location}?{query_string}"

        body = json.dumps(
            {
                "message": f"This endpoint has moved to {location}",
                "code": "ENDPOINT_MOVED",
            }
        )
        response = HttpResponsePermanentRedirect(
            location,
            preserve_request=request.method not in SAFE_METHODS,
            content=body,
            content_type="application/json",
        )
        response["Deprecation"] = "true"
        response["Link"] = f'<{location}>; rel="successor-version"'
        response["Sunset"] = LEGACY_API_SUNSET
        return response

    redirect_view.is_legacy_route = True
    return redirect_view


def legacy_alias(view_func):
    """Serve a legacy path with the same view as its v1 route.

    Reserved for senders that ignore redirects, such as GitHub webhook
    deliveries. The alias stays out of the OpenAPI spec so the spec describes
    one surface.
    """

    @csrf_exempt
    @wraps(view_func)
    def alias_view(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    alias_view.is_legacy_route = True
    return alias_view
