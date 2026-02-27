# API Naming Conventions

Conventions for spec-trace REST API endpoints. All endpoints live under `/api/`.

## 1. Singular vs Plural

Use **plural nouns** for collection endpoints. Use the **singular resource ID** to address one item.

| Pattern                                      | Meaning                 |
| -------------------------------------------- | ----------------------- |
| `GET /api/results/conflicts/`                | List all conflicts      |
| `GET /api/results/conflicts/:id/`            | Get one conflict        |
| `GET /api/results/enforcement-runs/`         | List enforcement runs   |
| `GET /api/results/enforcement-runs/:run_id/` | Get one enforcement run |

Exceptions exist for singleton resources that represent a single current state:

| Pattern                              | Meaning                     |
| ------------------------------------ | --------------------------- |
| `GET /api/results/test-runs/latest/` | The most recent test run    |
| `GET /api/tasks/flow-runs/running/`  | Currently running flow runs |

## 2. Verb Placement

Place verbs as **sub-resources of the noun they act on**. The noun comes first; the action nests beneath it.

```
# Correct — verb is a sub-resource of the noun
POST /api/results/conflicts/detect/
POST /api/results/conflicts/:id/resolve/
POST /api/integrations/linear/test-connection/

# Wrong — verb leads, noun follows
POST /api/detect-conflicts/
POST /api/resolve-conflict/:id/
```

Standard CRUD operations rely on HTTP methods, not URL verbs:

| Operation | Method | URL                           |
| --------- | ------ | ----------------------------- |
| List      | GET    | `/api/results/conflicts/`     |
| Read      | GET    | `/api/results/conflicts/:id/` |
| Create    | POST   | `/api/results/conflicts/`     |
| Update    | PUT    | `/api/results/conflicts/:id/` |
| Delete    | DELETE | `/api/results/conflicts/:id/` |

Reserve URL verbs for actions that go beyond CRUD — `detect`, `resolve`, `test-connection`.

## 3. Query Parameters

### Filtering

Filter by field name directly:

```
GET /api/results/conflicts/?confidence=high
GET /api/results/conflicts/?resolved=true
GET /api/results/conflicts/?requirement_id=REQ-042
GET /api/results/enforcement-runs/?vendor=stripe&status=fail
```

Combine filters with `&`. All filters apply as AND conditions.

### Pagination

Use `page` and `per_page`:

```
GET /api/results/conflicts/?page=2&per_page=25
GET /api/results/enforcement-runs/?page=1&per_page=50
```

Defaults: `page=1`, `per_page=25`. Maximum `per_page` is 100.

### Time Ranges

Use ISO 8601 timestamps:

```
GET /api/results/test-runs/latest/?since=2026-02-01T00:00:00Z
GET /api/results/enforcement-runs/?start_date=2026-02-01&end_date=2026-02-28
```

Parameter names follow the resource's domain:

- `since` for "newer than" filters (polling use case)
- `start_date` / `end_date` for date-range filters

## 4. Response Envelope

### Collections

The top-level key matches the **plural resource name**. Pagination metadata sits in a separate `pagination` key.

```json
{
  "conflicts": [
    { "id": 1, "pattern": "mutual_exclusion", "confidence": "high" },
    { "id": 2, "pattern": "resource_contention", "confidence": "medium" }
  ],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 42,
    "total_pages": 2,
    "has_next": true,
    "has_prev": false
  }
}
```

Pagination fields:

| Field         | Type    | Meaning                        |
| ------------- | ------- | ------------------------------ |
| `page`        | integer | Current page number            |
| `per_page`    | integer | Items per page                 |
| `total`       | integer | Total matching items           |
| `total_pages` | integer | Total pages available          |
| `has_next`    | boolean | Whether a next page exists     |
| `has_prev`    | boolean | Whether a previous page exists |

### Single Resources

Wrap the resource in a key matching its **singular name**:

```json
{
  "conflict": {
    "id": 1,
    "requirement_a": "REQ-001",
    "requirement_b": "REQ-002",
    "pattern": "mutual_exclusion",
    "confidence": "high",
    "resolved": false
  }
}
```

```json
{
  "test_run": {
    "id": 5,
    "imported_at": "2026-02-27T14:30:00Z",
    "total_tests": 312,
    "passed": 308,
    "failed": 4
  }
}
```

### Action Responses

Action endpoints return `success` plus operation-specific counts:

```json
{
  "success": true,
  "conflicts_found": 7,
  "logged": 5,
  "skipped_existing": 2
}
```

## 5. Error Format

Return `error` with a human-readable message and an appropriate HTTP status code.

```json
{ "error": "Conflict not found" }
```

For structured errors, add a machine-readable `code`:

```json
{
  "error": "Authentication required. Provide API key via Authorization or X-API-Key header.",
  "code": "AUTH_REQUIRED"
}
```

For validation errors with field-level detail:

```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "fields": {
    "slos": "No SLOs in request"
  }
}
```

### Status Codes

| Code | Meaning                        | Example                          |
| ---- | ------------------------------ | -------------------------------- |
| 200  | Success                        | GET, POST actions                |
| 204  | Success, no content            | No new test runs since timestamp |
| 400  | Bad request / validation error | Missing required fields          |
| 401  | Authentication required        | Missing or invalid API key       |
| 404  | Resource not found             | Unknown conflict ID              |
| 429  | Rate limited                   | Too many requests                |

## 6. Versioning

**Recommendation: Use URL prefix versioning (`/api/v1/`).** Deferred to a later phase — the current restructure uses unversioned `/api/` paths. When versioning ships, all endpoints move under `/api/v1/` and unversioned paths redirect.

```
/api/v1/results/conflicts/
/api/v1/results/enforcement-runs/
/api/v1/results/test-runs/latest/
```

### Rationale

- **Explicit.** The version is visible in every URL — no hidden headers to inspect.
- **Cacheable.** HTTP caches, CDNs, and proxies route on URL path. Header-based versioning breaks cache keys or requires Vary headers.
- **Debuggable.** Browser address bars, curl commands, and log files all show the version. Header-based versions hide in request metadata.
- **Tooling-friendly.** OpenAPI specs, Swagger UI, and API clients handle path-based versioning natively. Header-based versioning requires custom configuration.

Header-based versioning (`Accept: application/vnd.spectrace.v1+json`) keeps URLs clean but adds friction at every layer that touches the request. URL prefixing trades URL aesthetics for operational simplicity — a worthwhile trade for an internal API.

### Migration Path

1. Add `/api/v1/` routes alongside existing `/api/` routes
2. Redirect `/api/` to `/api/v1/` for backward compatibility
3. New breaking changes go to `/api/v2/`
