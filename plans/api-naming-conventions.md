# SpecTrace API Naming Conventions

This document defines the REST API naming conventions for SpecTrace. It ensures a consistent, predictable, and discoverable contract across the four primary API groups: `/api/specs/`, `/api/tasks/`, `/api/results/`, and `/api/integrations/`.

## Resource Naming: Plural vs. Singular

Always use plural nouns for resource collections in the URL path. This maintains a consistent hierarchy where an ID refers to a specific instance within that collection.

- **Correct:** `/api/specs/`, `/api/specs/:id`
- **Incorrect:** `/api/spec/`, `/api/spec/:id`

This rule applies to all nested resources as well.

- **Correct:** `/api/specs/:id/comments/`
- **Incorrect:** `/api/specs/:id/comment/`

## Verbs in URLs vs. HTTP Methods

Use standard HTTP methods (GET, POST, PUT, PATCH, DELETE) to indicate CRUD (Create, Read, Update, Delete) operations. Do not put CRUD verbs in the URL.

- **Correct:** `POST /api/specs/` (creates a spec)
- **Incorrect:** `POST /api/specs/create` or `GET /api/specs/create`

### State Transitions

When an operation triggers a specific state transition or business logic process that doesn't cleanly map to CRUD, use a verb at the end of the URL path. Always use the `POST` method for these actions to indicate that they mutate state.

- **Correct:** `POST /api/tasks/:id/claim` (transitions task to claimed state)
- **Correct:** `POST /api/tasks/:id/complete` (transitions task to completed state)
- **Incorrect:** `PATCH /api/tasks/:id/claim` (use POST for verb endpoints)
- **Incorrect:** `POST /api/tasks/claim/:id` (verb must be the final segment)

## Standard Query Parameters

Use standard query parameters across all collection endpoints to ensure a consistent experience for pagination, filtering, and sorting.

### Pagination

Use limit-offset pagination for programmatic access and agent consumption.

- `limit`: The maximum number of items to return (default: 50, max: 100).
- `offset`: The number of items to skip before starting to collect the result set (default: 0).

Example: `GET /api/specs/?limit=20&offset=40`

### Filtering

Filter collections using exact field names as query parameters. For multiple values, repeat the parameter.

- `status=active` (exact match)
- `tags=auth&tags=security` (matches either tag)

### Sorting

Use the `sort` parameter with a comma-separated list of fields. Prefix the field name with a minus sign (`-`) for descending order.

- `sort=created_at` (ascending by creation date)
- `sort=-priority,title` (descending by priority, then ascending by title)

## Response Envelopes

To maintain a consistent parsing experience, all API responses should use a standard envelope structure. Rather than returning raw arrays or objects at the root level, responses must be wrapped in a consistent top-level JSON object.

- **Success Responses:** Wrap the primary payload in a `data` key. For paginated collections, include a `meta` key for pagination details.
  ```json
  {
    "data": [ ... ],
    "meta": {
      "limit": 20,
      "offset": 0,
      "total": 150
    }
  }
  ```
- **Single Item Responses:** Also wrap the single resource in a `data` key.
  ```json
  {
    "data": { "id": "REQ-001", "title": "..." }
  }
  ```

## Standard Error Formats

When an API request fails, the response must adhere to a standardized error format, loosely inspired by RFC 7807 (Problem Details for HTTP APIs). This ensures clients can programmatically handle errors predictably.

All error responses (4xx and 5xx) should return a JSON object with an `error` key containing the following standard fields:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "The provided spec markdown contains invalid YAML frontmatter.",
    "details": [
      {
        "field": "priority",
        "issue": "Must be one of: low, medium, high."
      }
    ]
  }
}
```

- `code`: A stable, machine-readable string identifying the error type.
- `message`: A human-readable description of the error.
- `details`: (Optional) An array of specific validation issues, particularly useful for 400 Bad Request responses.

## Versioning Strategy

To ensure long-term stability and prevent breaking changes for consumers, the SpecTrace API employs a URL-based versioning strategy.

- **Prefix:** All API endpoints must be prefixed with their major version number (e.g., `/api/v1/`).
- **Scope:** Versioning applies at the API level. A breaking change to any core resource will necessitate a bump to `/api/v2/`.
- **Internal APIs:** Even for internal or early-stage development, the `/v1/` prefix must be used to establish the pattern and ensure a seamless transition when the API is eventually exposed to external agents or integrations.

## The Vocabulary of "Validation"

The term "validation" previously served multiple conflicting purposes. To provide clear meaning to agents and CI pipelines, the API strictly replaces "validation" with three specific terms based on context:

1.  **Schema-check**: Determines if a spec is well-formed.
    - _Usage:_ Use when verifying markdown frontmatter, YAML syntax, or required spec fields.
    - _Example endpoint:_ `POST /api/specs/schema-check`
2.  **Enforcement**: Determines if the codebase matches the spec.
    - _Usage:_ Use when analyzing drift or verifying that code implements documented requirements.
    - _Example endpoint:_ `GET /api/specs/drift` (replaces previous validation terminology)
3.  **Verification**: Determines if a test passed.
    - _Usage:_ Use when dealing with CI pipeline execution results or agent test reports.
    - _Example endpoints:_ `POST /api/results/` (recording verification outcomes)

Do not use the word "validation" in any endpoint path, query parameter, or JSON response payload.
