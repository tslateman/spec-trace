# API Naming Conventions

Conventions for spec-trace REST API endpoints. All endpoints live under `/api/v1/`. See §6 for the versioning scheme and the redirects that serve the retired unversioned paths.

## 1. Singular vs Plural

Use **plural nouns** for collection endpoints. Use the **singular resource ID** to address one item.

| Pattern                                         | Meaning                 |
| ----------------------------------------------- | ----------------------- |
| `GET /api/v1/results/conflicts/`                | List all conflicts      |
| `GET /api/v1/results/conflicts/:id`             | Get one conflict        |
| `GET /api/v1/results/enforcement-runs/`         | List enforcement runs   |
| `GET /api/v1/results/enforcement-runs/:run_id/` | Get one enforcement run |

Exceptions exist for singleton resources that represent a single current state:

| Pattern                                 | Meaning                     |
| --------------------------------------- | --------------------------- |
| `GET /api/v1/results/test-runs/latest/` | The most recent test run    |
| `GET /api/v1/tasks/flow-runs/running/`  | Currently running flow runs |

### Trailing Slashes

Most paths end with a trailing slash. Six do not:

```
POST /api/v1/results/conflicts/detect
GET  /api/v1/results/conflicts/:id
POST /api/v1/results/conflicts/:id/resolve
GET  /api/v1/specs/:external_id/context
POST /api/v1/tasks/:task_id/claim
POST /api/v1/tasks/:task_id/complete
```

Copy these six exactly. Adding a trailing slash returns 404 — Django matches the
registered pattern literally, and no slashed variant is registered. New routes
should take the trailing slash to match the majority.

## 2. Verb Placement

Place verbs as **sub-resources of the noun they act on**. The noun comes first; the action nests beneath it.

```
# Correct — verb is a sub-resource of the noun
POST /api/v1/results/conflicts/detect
POST /api/v1/results/conflicts/:id/resolve
POST /api/v1/integrations/linear/test-connection/

# Wrong — verb leads, noun follows
POST /api/v1/detect-conflicts/
POST /api/v1/resolve-conflict/:id/
```

Standard CRUD operations rely on HTTP methods, not URL verbs:

| Operation | Method | URL                             | Ships today |
| --------- | ------ | ------------------------------- | ----------- |
| List      | GET    | `/api/v1/results/conflicts/`    | Yes         |
| Read      | GET    | `/api/v1/results/conflicts/:id` | Yes         |
| Create    | POST   | `/api/v1/results/conflicts/`    | No          |
| Update    | PUT    | `/api/v1/results/conflicts/:id` | No          |
| Delete    | DELETE | `/api/v1/results/conflicts/:id` | No          |

Conflicts arrive from detection, so the API exposes List and Read. The Create,
Update, and Delete rows show the shape a future writable collection takes.

Reserve URL verbs for actions that go beyond CRUD — `detect`, `resolve`, `test-connection`.

## 3. Query Parameters

### Filtering

Filter by field name directly:

```
GET /api/v1/results/conflicts/?confidence=high
GET /api/v1/results/conflicts/?resolved=true
GET /api/v1/results/enforcement-runs/?requirement_id=REQ-042
GET /api/v1/results/enforcement-runs/?vendor=stripe&status=fail
```

Combine filters with `&`. All filters apply as AND conditions.

### Pagination

Two schemes ship today, one per endpoint family.

`page` and `per_page` on the enforcement-run and test-run endpoints:

```
GET /api/v1/results/enforcement-runs/?page=1&per_page=50
```

Defaults: `page=1`, `per_page=20`. Maximum `per_page` is 100.

`limit` and `offset` on the endpoints served by `api_v1.py` — conflicts, tasks,
and the specs surface:

```
GET /api/v1/results/conflicts/?limit=25&offset=50
GET /api/v1/tasks/?limit=10
```

Defaults: `offset=0`, and `limit=25` on conflicts, `limit=50` on tasks. Both
cap `limit` at 100.

New endpoints take `limit` and `offset`. Converging the older family is tracked
separately — changing its parameters breaks callers, so it waits for `/api/v2/`.

### Time Ranges

Use ISO 8601 timestamps:

```
GET /api/v1/results/test-runs/latest/?since=2026-02-01T00:00:00Z
GET /api/v1/results/enforcement-runs/?start_date=2026-02-01&end_date=2026-02-28
```

Parameter names follow the resource's domain:

- `since` for "newer than" filters (polling use case)
- `start_date` / `end_date` for date-range filters

## 4. Response Envelope

### Collections

Collections use one of two envelopes, matching the two pagination schemes in §3.

The enforcement-run and test-run endpoints name the top-level key after the
plural resource and put pagination metadata in a separate `pagination` key:

```json
{
  "runs": [
    { "id": 13, "source": "production-app", "successful": 8, "failed": 0 },
    { "id": 12, "source": "ci://nightly", "successful": 5, "failed": 2 }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

The conflicts, tasks, and specs endpoints return `data` with a `meta` block:

```json
{
  "data": [
    { "id": 1, "pattern": "mutual_exclusion", "confidence": "high" },
    { "id": 2, "pattern": "resource_contention", "confidence": "medium" }
  ],
  "meta": { "limit": 25, "offset": 0, "total": 42 }
}
```

New endpoints use `data` and `meta`. The named-key envelope predates it and
stays until `/api/v2/`, because renaming a top-level key breaks every caller.

Pagination fields in the `pagination` block:

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

Every error returns `error` with a human-readable message and an appropriate
HTTP status code. The two endpoint families wrap it differently, matching the
split in §3 and §4.

The conflicts, tasks, and specs endpoints nest a `code` and `message`:

```json
{ "error": { "code": "not_found", "message": "Conflict not found" } }
```

New endpoints use this form. The enforcement-run and test-run endpoints return
a flat string, optionally alongside a sibling `code`:

```json
{ "error": "Verification run not found" }
```

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

Converging the flat form on the nested one changes a response body every caller
parses, so it waits for `/api/v2/`.

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

The API uses URL prefix versioning. Every endpoint lives under `/api/v1/`:

```
/api/v1/results/conflicts/
/api/v1/results/enforcement-runs/
/api/v1/results/test-runs/latest/
```

Two infrastructure paths stay unversioned, since they describe the whole
surface rather than belonging to a version: `/api/openapi.json` and `/api/docs/`.

### Rationale

- **Explicit.** The version is visible in every URL — no hidden headers to inspect.
- **Cacheable.** HTTP caches, CDNs, and proxies route on URL path. Header-based versioning breaks cache keys or requires Vary headers.
- **Debuggable.** Browser address bars, curl commands, and log files all show the version. Header-based versions hide in request metadata.
- **Tooling-friendly.** OpenAPI specs, Swagger UI, and API clients handle path-based versioning natively. Header-based versioning requires custom configuration.

Header-based versioning (`Accept: application/vnd.spectrace.v1+json`) keeps URLs clean but adds friction at every layer that touches the request. URL prefixing trades URL aesthetics for operational simplicity — a worthwhile trade for an internal API.

### Migration Path

The unversioned surface is retired. Each old `/api/` path answers with a
redirect to its `/api/v1/` successor, carrying `Deprecation`, `Link`, and
`Sunset` headers. The redirects are removed after the sunset date. See
`docs/api-contract.md` §3 for the path-by-path mapping, the status codes, and
the timeline.

Breaking changes go to `/api/v2/`. Additive changes — new endpoints, new
optional fields, new query parameters — stay in `/api/v1/`.
