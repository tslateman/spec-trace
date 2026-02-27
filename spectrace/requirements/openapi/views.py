"""Views for serving the OpenAPI specification."""

import yaml
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods

from .spec_builder import build_openapi_spec


@require_http_methods(["GET"])
@cache_page(300)
def openapi_spec(request: HttpRequest) -> HttpResponse:
    """Serve the OpenAPI 3.1 specification.

    GET /api/openapi.json

    Supports content negotiation:
    - Accept: application/json (default) -> JSON response
    - Accept: application/yaml or text/yaml -> YAML response

    Query parameters:
    - format: 'json' or 'yaml' (overrides Accept header)
    """
    spec = build_openapi_spec(
        title="SpecTrace API",
        version="1.0.0",
        description="API for requirements traceability, connecting specs to verified tests.",
    )

    # Check for format query parameter (takes precedence)
    format_param = request.GET.get("format", "").lower()

    # Check Accept header
    accept_header = request.headers.get("Accept", "application/json")

    # Determine output format
    use_yaml = format_param == "yaml" or (
        format_param != "json" and ("yaml" in accept_header or "text/yaml" in accept_header)
    )

    if use_yaml:
        yaml_content = yaml.dump(spec, default_flow_style=False, allow_unicode=True)
        return HttpResponse(yaml_content, content_type="application/yaml")

    return JsonResponse(spec, json_dumps_params={"indent": 2})


@require_http_methods(["GET"])
def swagger_ui(request: HttpRequest) -> HttpResponse:
    """Serve a simple Swagger UI page.

    GET /api/docs/

    Returns an HTML page that loads Swagger UI and points it to the OpenAPI spec.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpecTrace API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        html { box-sizing: border-box; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .swagger-ui .topbar { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true
            });
        };
    </script>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")
