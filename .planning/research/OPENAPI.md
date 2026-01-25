# OpenAPI Documentation for Django APIs

**Project:** SpecTrace
**Researched:** 2026-01-25
**Context:** Django 5.2 with plain Django views (JsonResponse), NOT using Django REST Framework

## Executive Summary

SpecTrace has ~10 API endpoints implemented as plain Django function-based views with `JsonResponse`. The main options for adding OpenAPI documentation are:

1. **Django Ninja** (Recommended) - Modern, lightweight, built-in OpenAPI
2. **Manual OpenAPI YAML + Static Docs** - Lowest effort, no code changes
3. **Add DRF + drf-spectacular** - Most powerful, but heavy dependency
4. **Djagger** - Designed for plain Django, but inactive project

**Recommendation: Django Ninja** for new endpoints, with optional **Manual YAML** for documenting existing endpoints during transition.

---

## Tool Comparison

| Tool | OpenAPI Support | Works with Plain Django | Integration Effort | Maintenance | Confidence |
|------|----------------|------------------------|-------------------|-------------|------------|
| **Django Ninja** | 3.1 (automatic) | Requires rewrite to Ninja syntax | Medium | Active (v1.5.3) | HIGH |
| **Manual YAML** | 3.0/3.1 | Yes, no code changes | Low | Manual updates | HIGH |
| **drf-spectacular** | 3.0/3.1 | No (requires DRF) | High (add DRF) | Active (v0.29.0) | HIGH |
| **Djagger** | 3.0 | Yes (pydantic schemas) | Medium | Inactive since 2022 | LOW |
| **apispec** | 3.0/3.1 | Possible but no Django plugin | High | Active (v6.9.0) | MEDIUM |

---

## Option 1: Django Ninja (Recommended)

### What It Is

Django Ninja is a FastAPI-inspired framework for building APIs with Django. It uses Python type hints and Pydantic for automatic request/response validation and **generates OpenAPI docs automatically**.

### Why Recommended

- **Automatic OpenAPI**: No manual schema maintenance
- **Type-safe**: Pydantic validation catches errors at runtime
- **Incremental adoption**: Can run alongside existing Django views
- **Active project**: v1.5.3 released, active development
- **Lightweight**: No need to add to INSTALLED_APPS
- **Django integration**: Uses Django ORM, auth, middleware

### Integration Approach

Django Ninja can be added **alongside** existing plain Django views:

```python
# spectrace/api.py (new file)
from ninja import NinjaAPI, Schema
from typing import List, Optional

api = NinjaAPI(
    title="SpecTrace API",
    version="1.0.0",
    description="API for validation runs and integrations"
)

# Define schemas with Pydantic
class ValidationRunOut(Schema):
    id: int
    source: str
    imported_at: str
    total_validations: int
    successful: int
    failed: int

class PaginationOut(Schema):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

class ValidationRunListOut(Schema):
    runs: List[ValidationRunOut]
    pagination: PaginationOut

# Endpoint with automatic OpenAPI
@api.get("/validation-runs", response=ValidationRunListOut)
def list_validation_runs(
    request,
    page: int = 1,
    per_page: int = 20,
    requirement_id: Optional[str] = None,
    vendor: Optional[str] = None,
):
    """List validation runs with filtering and pagination."""
    # ... implementation
    pass
```

```python
# spectrace/spectrace/urls.py
from django.urls import path
from spectrace.api import api

urlpatterns = [
    # Existing plain Django views (keep working)
    path('api/slo/status/', api_views.update_slo_status),

    # New Django Ninja API with docs
    path('api/v2/', api.urls),  # Docs at /api/v2/docs
]
```

### Migration Strategy

1. **Phase 1**: Add Django Ninja at `/api/v2/` with automatic docs
2. **Phase 2**: Migrate existing endpoints one-by-one to Ninja
3. **Phase 3**: Remove old `/api/` endpoints when clients upgraded

### Effort Estimate

| Task | Effort |
|------|--------|
| Add django-ninja dependency | 5 min |
| Create schema definitions | 2-3 hours |
| Migrate 10 endpoints | 4-6 hours |
| **Total** | **1 day** |

### Installation

```bash
uv add django-ninja
```

### Documentation URLs

- Swagger UI: `/api/v2/docs`
- OpenAPI JSON: `/api/v2/openapi.json`

---

## Option 2: Manual OpenAPI YAML + Static Docs

### What It Is

Write OpenAPI spec by hand in YAML, serve Swagger UI and ReDoc using CDN-based static HTML templates.

### Why Consider It

- **Zero code changes** to existing views
- **Immediate documentation** without migration
- **No new dependencies** (just static files)
- **Full control** over documentation

### How It Works

1. Create `openapi.yaml` manually
2. Serve it from Django static files
3. Add HTML templates for Swagger UI / ReDoc

### Implementation

**1. Create OpenAPI spec:**

```yaml
# spectrace/static/openapi.yaml
openapi: 3.1.0
info:
  title: SpecTrace API
  version: 1.0.0
  description: API for validation runs and integrations

servers:
  - url: /api

paths:
  /validation-runs/:
    get:
      summary: List validation runs
      operationId: listValidationRuns
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: per_page
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationRunList'

components:
  schemas:
    ValidationRunList:
      type: object
      properties:
        runs:
          type: array
          items:
            $ref: '#/components/schemas/ValidationRun'
        pagination:
          $ref: '#/components/schemas/Pagination'
```

**2. Create Swagger UI template:**

```html
<!-- templates/api/swagger.html -->
<!DOCTYPE html>
<html>
<head>
    <title>SpecTrace API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: "{% url 'openapi-schema' %}",
            dom_id: '#swagger-ui',
        });
    </script>
</body>
</html>
```

**3. Create ReDoc template:**

```html
<!-- templates/api/redoc.html -->
<!DOCTYPE html>
<html>
<head>
    <title>SpecTrace API Reference</title>
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
    <redoc spec-url="{% url 'openapi-schema' %}"></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
```

**4. Add URLs:**

```python
# urls.py
from django.views.generic import TemplateView
from django.views.static import serve
import os

urlpatterns = [
    # ... existing urls

    # OpenAPI schema
    path('api/openapi.yaml', serve, {
        'document_root': os.path.join(settings.BASE_DIR, 'static'),
        'path': 'openapi.yaml'
    }, name='openapi-schema'),

    # Documentation UIs
    path('api/docs/', TemplateView.as_view(template_name='api/swagger.html'), name='api-docs'),
    path('api/redoc/', TemplateView.as_view(template_name='api/redoc.html'), name='api-redoc'),
]
```

### Pros

- No code changes required
- Works immediately
- Can document as-is before migrating

### Cons

- **Manual maintenance**: Schema can drift from code
- **No validation**: Mistakes in YAML go unnoticed
- **Duplication**: Schema info lives outside code

### Effort Estimate

| Task | Effort |
|------|--------|
| Write OpenAPI YAML for 10 endpoints | 3-4 hours |
| Create templates | 30 min |
| Add URL routes | 15 min |
| **Total** | **4-5 hours** |

---

## Option 3: Add DRF + drf-spectacular

### What It Is

Add Django REST Framework and drf-spectacular to get automatic, powerful OpenAPI generation.

### Why NOT Recommended for SpecTrace

- **Heavy dependency**: DRF is 15K+ lines, overkill for simple JsonResponse views
- **Requires rewrite**: Views must become DRF ViewSets/APIViews
- **Complexity**: DRF has serializers, permissions, authentication, throttling - features not needed
- **Steeper learning curve** than Django Ninja

### When to Choose DRF + drf-spectacular

- Building a new, complex API from scratch
- Need advanced features: nested routers, permissions, versioning
- Team already knows DRF
- Want extensive ecosystem (filters, pagination, etc.)

### If You Choose This Path

```bash
uv add djangorestframework drf-spectacular
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rest_framework',
    'drf_spectacular',
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'SpecTrace API',
    'VERSION': '1.0.0',
}
```

```python
# urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema')),
]
```

### Effort Estimate

| Task | Effort |
|------|--------|
| Add dependencies | 10 min |
| Configure DRF/spectacular | 30 min |
| Rewrite 10 views to DRF | 1-2 days |
| Create serializers | 4-6 hours |
| **Total** | **2-3 days** |

---

## Option 4: Djagger (NOT Recommended)

### What It Is

OpenAPI generator for plain Django views using Pydantic schemas.

### Why NOT Recommended

- **Inactive project**: Last release October 2022 (v1.1.4)
- **Low adoption**: ~243 weekly downloads
- **Risk**: May not work with Django 5.2 or modern Pydantic v2
- **No maintenance**: Security/compatibility issues unlikely to be fixed

### Confidence Level: LOW

Do not use for production projects.

---

## Recommendation Summary

### For SpecTrace Specifically

**Recommended approach: Django Ninja**

Rationale:
1. **Modern and maintained**: Active development, v1.5.3
2. **Right-sized**: Lighter than DRF, more than manual YAML
3. **Automatic docs**: No manual schema maintenance
4. **Incremental**: Can migrate endpoints gradually
5. **Type-safe**: Pydantic catches errors early
6. **FastAPI-like**: If team knows FastAPI, minimal learning curve

### Suggested Implementation Plan

| Phase | Action | Effort |
|-------|--------|--------|
| 1 | Add django-ninja, create `/api/v2/` with Ninja | 2 hours |
| 2 | Migrate `list_validation_runs` as proof-of-concept | 1 hour |
| 3 | Add pydantic schemas for all response types | 2-3 hours |
| 4 | Migrate remaining 9 endpoints | 4-5 hours |
| 5 | Deprecate `/api/` routes, redirect to `/api/v2/` | 30 min |
| **Total** | | **~1 day** |

### Alternative: Quick Win with Manual YAML

If you need docs **today** without code changes:

1. Write `openapi.yaml` for current endpoints (4 hours)
2. Serve Swagger UI via CDN template (30 min)
3. Plan Django Ninja migration for later

This gives immediate documentation while planning the proper solution.

---

## Sources

### Official Documentation
- [Django Ninja](https://django-ninja.dev/) - Official documentation
- [drf-spectacular](https://drf-spectacular.readthedocs.io/) - OpenAPI for DRF
- [DRF Schemas](https://www.django-rest-framework.org/api-guide/schemas/) - DRF schema documentation
- [ReDoc](https://redocly.com/docs/redoc) - ReDoc documentation

### Comparisons and Analysis
- [DRF vs Django Ninja](https://www.loopwerk.io/articles/2024/drf-vs-ninja/) - Detailed comparison
- [drf-spectacular vs django-ninja](https://www.libhunt.com/compare-drf-spectacular-vs-django-ninja) - LibHunt comparison
- [Django blog: Why need 3rd party app](https://www.djangoproject.com/weblog/2025/may/22/why-need-3rd-party-app-rest-api-with-django/) - Django official guidance

### GitHub Repositories
- [Django Ninja](https://github.com/vitalik/django-ninja) - 7.9k stars
- [drf-spectacular](https://github.com/tfranzel/drf-spectacular) - 2.4k stars
- [Djagger](https://github.com/royhzq/djagger) - Inactive

### Package Versions (as of 2026-01-25)
- django-ninja: 1.5.3
- drf-spectacular: 0.29.0
- djagger: 1.1.4 (last release 2022-10-31)
- apispec: 6.9.0
