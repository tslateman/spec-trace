# API Contract — SpecTrace v1

This contract defines the endpoint restructure for SpecTrace's REST API. It maps every existing endpoint to its new URL, catalogs the new API surface by group, and specifies the deprecation strategy for old URLs.

### Versioning

This contract uses unversioned URLs (`/api/specs/`, `/api/results/`, etc.). URL prefix versioning (`/api/v1/`) is deferred to a later phase. When versioning ships, all endpoints will move under `/api/v1/` and unversioned `/api/` paths will redirect to `/api/v1/`. See `docs/api-naming-conventions.md` §6 for the versioning strategy.

---

## 1. Endpoint Mapping Table

All 17 existing endpoints with their new URLs. Endpoints move into four domain groups: `/api/specs/`, `/api/tasks/`, `/api/results/`, `/api/integrations/`. Infrastructure endpoints stay unchanged.

| #   | Method | Old URL                                     | New URL                                         | Group        |
| --- | ------ | ------------------------------------------- | ----------------------------------------------- | ------------ |
| 1   | POST   | `/api/slo/status/`                          | `/api/integrations/slo/status/`                 | Integrations |
| 2   | POST   | `/api/validation/result/`                   | `/api/results/enforcement/`                     | Results      |
| 3   | GET    | `/api/requirement/{id}/status/`             | `/api/specs/{id}/status/`                       | Specs        |
| 4   | POST   | `/api/integrations/linear/test-connection/` | `/api/integrations/linear/test-connection/`     | Integrations |
| 5   | GET    | `/api/integrations/linear/health/`          | `/api/integrations/linear/health/`              | Integrations |
| 6   | GET    | `/api/validation-runs/`                     | `/api/results/enforcement-runs/`                | Results      |
| 7   | GET    | `/api/validation-runs/{run_id}/`            | `/api/results/enforcement-runs/{run_id}/`       | Results      |
| 8   | GET    | `/api/validation-runs/{run_id}/steps/`      | `/api/results/enforcement-runs/{run_id}/steps/` | Results      |
| 9   | GET    | `/api/flow-runs/running/`                   | `/api/tasks/flow-runs/running/`                 | Tasks        |
| 10  | GET    | `/api/test-runs/latest/`                    | `/api/results/test-runs/latest/`                | Results      |
| 11  | GET    | `/api/conflicts/`                           | `/api/results/conflicts/`                       | Results      |
| 12  | POST   | `/api/conflicts/detect/`                    | `/api/results/conflicts/detect/`                | Results      |
| 13  | GET    | `/api/conflicts/{id}/`                      | `/api/results/conflicts/{id}/`                  | Results      |
| 14  | POST   | `/api/conflicts/{id}/resolve/`              | `/api/results/conflicts/{id}/resolve/`          | Results      |
| 15  | POST   | `/api/webhooks/github/`                     | `/api/integrations/webhooks/github/`            | Integrations |
| 16  | GET    | `/api/openapi.json`                         | `/api/openapi.json`                             | Infra        |
| 17  | GET    | `/api/docs/`                                | `/api/docs/`                                    | Infra        |

---

## 2. New Endpoint Catalog

### `/api/specs/` — Contract Surface

Read-heavy endpoints that answer "what does the spec say?" Agents and dashboards read these to understand requirements, coverage, and drift.

| Method | URL                       | Description                           | Auth | Request Schema | Response Schema             |
| ------ | ------------------------- | ------------------------------------- | ---- | -------------- | --------------------------- |
| GET    | `/api/specs/{id}/status/` | Get requirement status by external ID | None | —              | `RequirementStatusResponse` |

### `/api/tasks/` — Agent Surface

Agent registration, task lifecycle, lease management, and flow orchestration.

| Method | URL                             | Description                             | Auth | Request Schema | Response Schema               |
| ------ | ------------------------------- | --------------------------------------- | ---- | -------------- | ----------------------------- |
| GET    | `/api/tasks/{task_id}/context/` | Get full spec context for an agent task | None | —              | (see `agent_context` command) |
| GET    | `/api/tasks/flow-runs/running/` | List currently running flow executions  | None | —              | `RunningFlowRunsResponse`     |

### `/api/results/` — Evidence Surface

External systems push enforcement evidence here. Dashboards read enforcement history, test runs, and conflict data.

**Auth model:** Read endpoints (GET) require no authentication — conflict and enforcement data is non-sensitive operational state. Write endpoints (POST) require an API key because they mutate data: submitting evidence, triggering detection, or resolving conflicts.

| Method | URL                                             | Description                              | Auth    | Request Schema             | Response Schema                |
| ------ | ----------------------------------------------- | ---------------------------------------- | ------- | -------------------------- | ------------------------------ |
| POST   | `/api/results/enforcement/`                     | Submit enforcement evidence from product | API key | `EnforcementResultRequest` | `EnforcementResultResponse`    |
| GET    | `/api/results/enforcement-runs/`                | List enforcement run history             | None    | —                          | `EnforcementRunsResponse`      |
| GET    | `/api/results/enforcement-runs/{run_id}/`       | Get single enforcement run detail        | None    | —                          | `EnforcementRunDetailResponse` |
| GET    | `/api/results/enforcement-runs/{run_id}/steps/` | Get step-level verification evidence     | None    | —                          | `VerificationStepsResponse`    |
| GET    | `/api/results/test-runs/latest/`                | Get latest CI/CD test run                | None    | —                          | `LatestTestRunResponse`        |
| GET    | `/api/results/conflicts/`                       | List detected conflicts                  | None    | —                          | `ConflictListResponse`         |
| POST   | `/api/results/conflicts/detect/`                | Run conflict detection                   | API key | `ConflictDetectRequest`    | `ConflictDetectResponse`       |
| GET    | `/api/results/conflicts/{id}/`                  | Get conflict detail                      | None    | —                          | `ConflictDetailResponse`       |
| POST   | `/api/results/conflicts/{id}/resolve/`          | Resolve a conflict                       | API key | `ConflictResolveRequest`   | `ConflictResolveResponse`      |

### `/api/integrations/` — External System Hooks

Webhook receivers, health checks, and SLO pushes from observability platforms.

| Method | URL                                         | Description                             | Auth                  | Request Schema      | Response Schema        |
| ------ | ------------------------------------------- | --------------------------------------- | --------------------- | ------------------- | ---------------------- |
| POST   | `/api/integrations/slo/status/`             | Push SLO status from observability tool | API key               | `SLOStatusRequest`  | `SLOStatusResponse`    |
| POST   | `/api/integrations/linear/test-connection/` | Test Linear integration connection      | API key               | `LinearTestRequest` | `LinearTestResponse`   |
| GET    | `/api/integrations/linear/health/`          | Check Linear integration health         | None                  | —                   | `LinearHealthResponse` |
| POST   | `/api/integrations/webhooks/github/`        | Receive GitHub webhook events           | HMAC-SHA256 signature | (GitHub event body) | —                      |

### Infrastructure (unchanged)

| Method | URL                 | Description             | Auth |
| ------ | ------------------- | ----------------------- | ---- |
| GET    | `/api/openapi.json` | OpenAPI 3.0 spec (JSON) | None |
| GET    | `/api/docs/`        | Swagger UI              | None |

---

## 3. Deprecation Strategy

### Redirect Behavior

Old URLs redirect to new URLs. GET endpoints return **301 (Moved Permanently)**. POST endpoints return **308 (Permanent Redirect)** to preserve the HTTP method and request body.

| Method | Redirect Code | Reason                           |
| ------ | ------------- | -------------------------------- |
| GET    | 301           | Method preservation guaranteed   |
| POST   | 308           | Prevents method downgrade to GET |

**GET example:**

```http
HTTP/1.1 301 Moved Permanently
Location: /api/specs/REQ-042/status/
Deprecation: true
Link: </api/specs/REQ-042/status/>; rel="successor-version"
Sunset: Sat, 13 Jun 2026 00:00:00 GMT
Content-Type: application/json

{"message": "This endpoint has moved to /api/specs/REQ-042/status/", "code": "ENDPOINT_MOVED"}
```

**POST example:**

```http
HTTP/1.1 308 Permanent Redirect
Location: /api/results/enforcement/
Deprecation: true
Link: </api/results/enforcement/>; rel="successor-version"
Sunset: Sat, 13 Jun 2026 00:00:00 GMT
Content-Type: application/json

{"message": "This endpoint has moved to /api/results/enforcement/", "code": "ENDPOINT_MOVED"}
```

Redirect bodies use `message` (not `error`) because a redirect is not an error. The `error` key is reserved for 4xx/5xx responses per the naming conventions.

### Headers

Every response from an old URL includes three headers:

| Header        | Format                        | Example                                                |
| ------------- | ----------------------------- | ------------------------------------------------------ |
| `Deprecation` | `true` (per RFC 8594)         | `true`                                                 |
| `Link`        | Successor URL with rel        | `</api/results/enforcement/>; rel="successor-version"` |
| `Sunset`      | HTTP-date (RFC 7231 §7.1.1.1) | `Sat, 13 Jun 2026 00:00:00 GMT`                        |
| `Location`    | New URL path                  | `/api/results/enforcement/`                            |

### Known Consumers

The API currently serves three consumer types:

1. **SpecTrace agents** — claim tasks, submit enforcement results, run conflict detection
2. **CI pipelines** — push test results, query enforcement run history
3. **SpecTrace dashboard** — reads requirement status, conflict data, flow run status

All consumers are internal. No external third-party integrations exist today. The 90-day sunset window is conservative for an internal-only API but provides margin for any undiscovered consumers.

### Timeline

| Phase          | Duration     | Dates                   | Old URL Behavior                            |
| -------------- | ------------ | ----------------------- | ------------------------------------------- |
| **Dual-serve** | 90 days      | 2026-03-15 → 2026-06-13 | 301/308 redirect + `Deprecation` + `Sunset` |
| **Sunset**     | After day 90 | 2026-06-14 onward       | 410 Gone + JSON error body                  |

### Dual-Serve Phase Details

During the 90-day transition:

1. **New URLs** serve requests directly. No deprecation headers.
2. **Old URLs** redirect to the corresponding new URL. GET returns 301; POST returns 308. Query parameters and request bodies pass through unchanged.
3. **Monitoring** tracks hit counts on old URLs. If traffic drops to zero before sunset, the old routes can be removed early.

### After Sunset

Old URLs return **410 Gone** with a JSON body:

```http
HTTP/1.1 410 Gone
Content-Type: application/json

{"error": "This endpoint was removed on 2026-06-14. Use /api/results/enforcement/ instead.", "code": "ENDPOINT_REMOVED"}
```

---

## 4. "Validation" Disambiguation Glossary

The codebase uses "validation" for four distinct concepts. This glossary assigns each a precise term.

### Terms

**Enforcement** — Runtime behavior matching. The product reports whether running code matches the spec. Appears in: `submit_validation_result`, `InAppValidation*` models, enforcement runs.

- API URLs use "enforcement": `/api/results/enforcement/`, `/api/results/enforcement-runs/`
- Schema names use "Enforcement": `EnforcementResultRequest`, `EnforcementRunsResponse`
- Django models keep their current names (`InAppValidation`, `InAppValidationRun`, `InAppValidationResult`). The API layer maps to "enforcement" at the serialization boundary.

**Verification** — Step-level evidence within an enforcement run. Each step proves one aspect of the spec holds (or fails). Appears in: `get_validation_run_steps`, step-level data.

- API URLs use "steps" under enforcement runs: `/api/results/enforcement-runs/{run_id}/steps/`
- Schema names use "Verification": `VerificationStep`, `VerificationStepsResponse`

**Schema-check** — Static validation that YAML link files are well-formed. Checks structure and references, not runtime behavior. Appears in: `validate_links` CLI command.

- CLI keeps `spectrace validate` — "validate my links file" reads naturally
- Proposed API URL: `/api/specs/validate-links/`
- Concept name in docs: "schema-check"

**Input validation** — HTTP request body, path parameter, and format checking. Standard web framework concern. Appears in: `@validate_request`, `validate_flow_path`, `validate_git_ref`.

- No rename needed. "Validate" is the correct term for input checking.
- These stay as-is in the codebase.

### Quick Reference

| Term                 | Definition                                  | API term         | Example URL                                 |
| -------------------- | ------------------------------------------- | ---------------- | ------------------------------------------- |
| **Enforcement**      | Runtime code-matches-spec checks            | `enforcement`    | `/api/results/enforcement/`                 |
| **Verification**     | Step-level evidence within enforcement runs | `steps`          | `/api/results/enforcement-runs/{id}/steps/` |
| **Schema-check**     | Static YAML link file structure validation  | `validate-links` | `/api/specs/validate-links/`                |
| **Input validation** | HTTP request/path format checking           | `validate`       | (decorator, not an endpoint)                |

### CLI-to-API Mapping

Every CLI command with its current and proposed API endpoint.

| CLI Command                        | Management Command         | Current API Endpoint          | Proposed API Endpoint                 |
| ---------------------------------- | -------------------------- | ----------------------------- | ------------------------------------- |
| `spectrace context <task_id>`      | `agent_context`            | —                             | `/api/tasks/{task_id}/context/`       |
| `spectrace coverage`               | `spec_coverage`            | —                             | `/api/specs/coverage/`                |
| `spectrace risks`                  | `detect_integration_risks` | —                             | `/api/specs/integration-risks/`       |
| `spectrace demo`                   | `demo_impact`              | —                             | (web UI only, no API planned)         |
| `spectrace impact <base> <head>`   | `impact_analysis`          | — (web UI POST exists)        | `/api/specs/impact/`                  |
| `spectrace conflicts`              | `detect_conflicts`         | POST `/api/conflicts/detect/` | POST `/api/results/conflicts/detect/` |
| `spectrace drift`                  | `detect_drift`             | —                             | `/api/specs/drift/`                   |
| `spectrace invariants`             | `check_invariants`         | —                             | `/api/specs/invariants/`              |
| `spectrace validate <links_file>`  | `validate_links`           | —                             | `/api/specs/validate-links/`          |
| `spectrace agent register`         | `agent_register`           | —                             | `/api/tasks/agents/register/`         |
| `spectrace agent tasks`            | `agent_tasks`              | —                             | `/api/tasks/`                         |
| `spectrace agent claim <task_id>`  | `agent_claim`              | —                             | `/api/tasks/{task_id}/claim/`         |
| `spectrace agent start <task_id>`  | `agent_start`              | —                             | `/api/tasks/{task_id}/start/`         |
| `spectrace agent submit <task_id>` | `agent_submit`             | —                             | `/api/tasks/{task_id}/submit/`        |
| `spectrace agent review <task_id>` | `agent_review`             | —                             | `/api/tasks/{task_id}/review/`        |
| `spectrace agent merge <task_id>`  | `agent_merge`              | —                             | `/api/tasks/{task_id}/merge/`         |
| `spectrace agent expire-leases`    | `expire_leases`            | —                             | `/api/tasks/leases/expire/`           |

**Summary:** 17 CLI commands map to API endpoints. 1 has a direct API equivalent today (`spectrace conflicts` → POST `/api/conflicts/detect/`). 16 are CLI-only, with proposed endpoints for future phases.
