# OpenAPI Spec Completeness

## Context

SpecTrace has a custom OpenAPI 3.1 generator built on msgspec Structs. The
`@validate_request` decorator attaches schema metadata to views, and
`introspection.py` walks Django URL patterns to build the spec at runtime.

**What works:** 12 of 14 API endpoints have response schemas. Swagger UI serves
at `/api/docs/`. Spec at `/api/openapi.json` supports JSON and YAML.

**Five gaps remain:**

1. Two endpoints lack `@validate_request` -- invisible in the spec
2. No security scheme -- consumers can't see how to authenticate
3. GET query parameters undocumented -- list/filter endpoints accept 15+ params
   but Swagger UI shows none
4. No response examples in schemas
5. Spec rebuilt on every request -- no caching

## What to Do

### 1. Add response schemas for undocumented endpoints

File: `spectrace/requirements/openapi/schemas.py`

Add two response Structs:

```python
class FlowRunStep(msgspec.Struct):
    id: int
    flow_name: str
    flow_display_name: str
    started_at: str
    total_steps: int
    completed_steps: int
    current_step: str | None
    current_step_order: int | None

class RunningFlowRunsResponse(msgspec.Struct):
    runs: list[FlowRunStep]

class TestRunSummary(msgspec.Struct):
    id: int
    imported_at: str
    source_file: str | None = None
    git_sha: str | None = None
    git_branch: str | None = None
    workflow_name: str | None = None
    workflow_run_id: str | None = None
    repository: str | None = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0

class LatestTestRunResponse(msgspec.Struct):
    test_run: TestRunSummary | None
```

File: `spectrace/requirements/api.py`

Decorate the two endpoints:

```python
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    response_schema=RunningFlowRunsResponse,
    tags=["Flows"],
    summary="Get running flow runs",
    methods=["GET"],
)
def get_running_flow_runs(request, data=None):
```

```python
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    response_schema=LatestTestRunResponse,
    tags=["Test Runs"],
    summary="Get latest test run",
    methods=["GET"],
)
def get_latest_test_run(request, data=None):
```

Add `data=None` parameter to both function signatures (the decorator passes it).

### 2. Add security scheme to spec builder

File: `spectrace/requirements/openapi/spec_builder.py`

In `build_openapi_spec()`, add a `securitySchemes` component and a global
`security` entry:

```python
spec["components"]["securitySchemes"] = {
    "apiKeyHeader": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API key via X-API-Key header",
    },
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "description": "API key via Authorization: Bearer <key>",
    },
}
```

Do NOT add a global `security` field -- not all endpoints require auth. Instead,
mark auth per-endpoint.

File: `spectrace/requirements/openapi/decorators.py`

Add a `requires_auth: bool = False` parameter to `@validate_request`. Store it
as `_openapi_requires_auth` on the view function.

File: `spectrace/requirements/openapi/introspection.py`

Add `requires_auth: bool = False` to `EndpointInfo`. Read it from metadata in
`extract_api_endpoints()`.

File: `spectrace/requirements/openapi/spec_builder.py`

In `_build_operation()`, if `endpoint.requires_auth`:

```python
if endpoint.requires_auth:
    operation["security"] = [
        {"apiKeyHeader": []},
        {"bearerAuth": []},
    ]
```

File: `spectrace/requirements/api.py`

Add `requires_auth=True` to the four endpoints that use `@require_api_key`:
`update_slo_status`, `submit_validation_result`, `test_linear_connection`,
`detect_conflicts`, `resolve_conflict`.

### 3. Add query parameter documentation

File: `spectrace/requirements/openapi/decorators.py`

Add a `query_parameters: list[dict] | None = None` parameter to
`@validate_request`. Store as `_openapi_query_parameters`.

File: `spectrace/requirements/openapi/introspection.py`

Add `query_parameters: list[dict]` to `EndpointInfo`. Read from metadata.

File: `spectrace/requirements/openapi/spec_builder.py`

In `_build_operation()`, merge query parameters with path parameters:

```python
all_params = (endpoint.path_parameters or []) + (endpoint.query_parameters or [])
if all_params:
    operation["parameters"] = all_params
```

File: `spectrace/requirements/api.py`

Add `query_parameters` to endpoints that accept them:

```python
# list_validation_runs
query_parameters=[
    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 100}},
    {"name": "requirement_id", "in": "query", "schema": {"type": "string"}},
    {"name": "vendor", "in": "query", "schema": {"type": "string"}},
    {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["pass", "fail", "error", "skip"]}},
    {"name": "start_date", "in": "query", "schema": {"type": "string", "format": "date"}},
    {"name": "end_date", "in": "query", "schema": {"type": "string", "format": "date"}},
]

# get_validation_run_steps
query_parameters=[
    {"name": "result_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter steps by validation result"},
]

# get_latest_test_run
query_parameters=[
    {"name": "since", "in": "query", "schema": {"type": "string", "format": "date-time"}, "description": "Only return run newer than this timestamp"},
    {"name": "repo", "in": "query", "schema": {"type": "string"}, "description": "Filter by repository (e.g., owner/repo)"},
]

# list_conflicts
query_parameters=[
    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 25, "maximum": 100}},
    {"name": "confidence", "in": "query", "schema": {"type": "string", "enum": ["high", "medium", "low"]}},
    {"name": "pattern", "in": "query", "schema": {"type": "string"}},
    {"name": "resolved", "in": "query", "schema": {"type": "boolean"}},
    {"name": "requirement_id", "in": "query", "schema": {"type": "string"}},
]
```

### 4. Cache the spec

File: `spectrace/requirements/openapi/views.py`

Wrap `openapi_spec` with Django's `cache_page`:

```python
from django.views.decorators.cache import cache_page

@cache_page(300)  # 5 minutes
def openapi_spec(request):
    ...
```

The spec changes only on deployment, not per-request. Five minutes is safe.

## What NOT to Do

- Do NOT add response examples yet -- schemas are sufficient for Swagger UI
  "Try it out" and examples require maintaining sample data that drifts
- Do NOT add webhooks to the spec -- CI webhooks are a separate future milestone
- Do NOT refactor the decorator into multiple decorators -- one decorator with
  optional params keeps the API surface consistent
- Do NOT add pagination schemas as reusable components -- each endpoint has
  slightly different filter params, shared pagination would be premature
- Do NOT add `description` fields to every query parameter unless the name
  is not self-explanatory (page, per_page, status are obvious)

## Files to Modify

| File                                              | Change                                                                                      |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `spectrace/requirements/openapi/schemas.py`       | Add 4 Structs (FlowRunStep, RunningFlowRunsResponse, TestRunSummary, LatestTestRunResponse) |
| `spectrace/requirements/openapi/decorators.py`    | Add `requires_auth` and `query_parameters` params                                           |
| `spectrace/requirements/openapi/introspection.py` | Add `requires_auth` and `query_parameters` to EndpointInfo                                  |
| `spectrace/requirements/openapi/spec_builder.py`  | Security schemes, query param merging, per-endpoint auth                                    |
| `spectrace/requirements/openapi/views.py`         | Cache spec for 5 minutes                                                                    |
| `spectrace/requirements/api.py`                   | Decorate 2 endpoints, add auth/query metadata to existing decorators                        |

## Acceptance Criteria

1. `GET /api/openapi.json` includes all 14 API endpoints (currently 12)
2. Swagger UI shows "Authorize" button with both apiKey and bearer options
3. Authenticated endpoints display lock icon in Swagger UI
4. `list_validation_runs`, `list_conflicts`, `get_latest_test_run`, and
   `get_validation_run_steps` show query parameters in Swagger UI
5. `make test` passes -- no regressions
6. Second request to `/api/openapi.json` returns cached response (verify via
   Django debug toolbar or response timing)

## Testing

Run existing test suite to verify no regressions:

```bash
make test
```

Manually verify Swagger UI:

```bash
make run
open http://localhost:8000/api/docs/
```

Check spec completeness:

```bash
curl -s http://localhost:8000/api/openapi.json | python -m json.tool | grep -c '"/'
# Should show 14 paths (was 12)
```

Verify security schemes present:

```bash
curl -s http://localhost:8000/api/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
schemes = spec.get('components', {}).get('securitySchemes', {})
print(f'Security schemes: {list(schemes.keys())}')
# Should print: Security schemes: ['apiKeyHeader', 'bearerAuth']
"
```
