# API Contract — SpecTrace v1

This contract describes SpecTrace's REST API. It maps every retired URL to its `/api/v1/` successor, catalogs the shipped surface by group, and specifies how the retired URLs behave until they are removed.

### Versioning

Every endpoint lives under `/api/v1/`, grouped into `/api/v1/specs/`, `/api/v1/tasks/`, `/api/v1/results/`, and `/api/v1/integrations/`. Two infrastructure paths stay unversioned because they describe the whole surface: `/api/openapi.json` and `/api/docs/`.

The unversioned `/api/` surface is retired. Each old path answers with a redirect to its successor — see §3. See `docs/api-naming-conventions.md` §6 for the versioning rationale.

---

## 1. Endpoint Mapping Table

Every retired URL with its `/api/v1/` successor and the status the old path returns today.

| #   | Method | Retired URL                                 | `/api/v1/` successor                               | Status     |
| --- | ------ | ------------------------------------------- | -------------------------------------------------- | ---------- |
| 1   | POST   | `/api/slo/status/`                          | `/api/v1/integrations/slo/status/`                 | 308        |
| 2   | POST   | `/api/validation/result/`                   | `/api/v1/results/enforcement/`                     | 308        |
| 3   | GET    | `/api/requirement/{id}/status/`             | `/api/v1/specs/{id}/status/`                       | 301        |
| 4   | POST   | `/api/integrations/linear/test-connection/` | `/api/v1/integrations/linear/test-connection/`     | 308        |
| 5   | GET    | `/api/integrations/linear/health/`          | `/api/v1/integrations/linear/health/`              | 301        |
| 6   | GET    | `/api/validation-runs/`                     | `/api/v1/results/enforcement-runs/`                | 301        |
| 7   | GET    | `/api/validation-runs/{run_id}/`            | `/api/v1/results/enforcement-runs/{run_id}/`       | 301        |
| 8   | GET    | `/api/validation-runs/{run_id}/steps/`      | `/api/v1/results/enforcement-runs/{run_id}/steps/` | 301        |
| 9   | GET    | `/api/flow-runs/running/`                   | `/api/v1/tasks/flow-runs/running/`                 | 301        |
| 10  | GET    | `/api/test-runs/latest/`                    | `/api/v1/results/test-runs/latest/`                | 301        |
| 11  | GET    | `/api/conflicts/`                           | `/api/v1/results/conflicts/`                       | 301        |
| 12  | POST   | `/api/conflicts/detect/`                    | `/api/v1/results/conflicts/detect`                 | 308        |
| 13  | GET    | `/api/conflicts/{id}/`                      | `/api/v1/results/conflicts/{id}`                   | 301        |
| 14  | POST   | `/api/conflicts/{id}/resolve/`              | `/api/v1/results/conflicts/{id}/resolve`           | 308        |
| 15  | POST   | `/api/webhooks/github/`                     | `/api/v1/integrations/webhooks/github/`            | Live alias |
| 16  | GET    | `/api/openapi.json`                         | unchanged                                          | Serves     |
| 17  | GET    | `/api/docs/`                                | unchanged                                          | Serves     |

The status column reports what the method in that row receives. Each redirect picks 301 or 308 from the request method, not from the route — see §3.

Rows 12, 13, and 14 have **no trailing slash** on the successor. Copy them exactly; a trailing slash returns 404.

Row 15 serves the retired path with the same view as its successor rather than redirecting. GitHub does not follow redirects on webhook delivery, so a 308 would be recorded as a failed delivery and the payload dropped. The alias becomes a redirect once the GitHub App's webhook URL points at `/api/v1/integrations/webhooks/github/`.

---

## 2. Endpoint Catalog

The shipped surface, by group. Paths without a trailing slash are marked; copy those exactly.

**Auth model:** three endpoints require an API key — `POST /api/v1/integrations/slo/status/`, `POST /api/v1/results/enforcement/`, and `POST /api/v1/integrations/linear/test-connection/`. These accept data from systems outside the deployment, so they authenticate the sender. Everything else is open, including the writes under `/api/v1/tasks/` and `/api/v1/results/conflicts/`, which agents inside the deployment call. Set `SPECTRACE_API_KEY` to enforce the key; leaving it unset bypasses the check and logs a warning.

### `/api/v1/specs/` — Contract Surface

Read-only endpoints that answer "what does the spec say?" Agents and dashboards read these for requirements, coverage, drift, and impact.

| Method | URL                                   | Description                                                           | Auth | Response Schema |
| ------ | ------------------------------------- | --------------------------------------------------------------------- | ---- | --------------- |
| GET    | `/api/v1/specs/coverage/`             | Coverage metrics and stale requirements for one project (`?project=`) | None | `data` / `meta` |
| GET    | `/api/v1/specs/drift/`                | Drift detections                                                      | None | `data` / `meta` |
| GET    | `/api/v1/specs/impact/`               | Dependency graph of affected specs                                    | None | `data` / `meta` |
| GET    | `/api/v1/specs/{external_id}/context` | Surrounding context for one requirement (no slash)                    | None | `data` / `meta` |
| GET    | `/api/v1/specs/{external_id}/status/` | Verification status for one requirement                               | None | `data` / `meta` |

### `/api/v1/tasks/` — Agent Surface

Task listing, the claim/complete lifecycle, and flow orchestration.

| Method | URL                                | Description                              | Auth | Response Schema           |
| ------ | ---------------------------------- | ---------------------------------------- | ---- | ------------------------- |
| GET    | `/api/v1/tasks/`                   | List agent tasks                         | None | `data` / `meta`           |
| GET    | `/api/v1/tasks/flow-runs/running/` | List currently running flow executions   | None | `RunningFlowRunsResponse` |
| POST   | `/api/v1/tasks/{task_id}/claim`    | Claim a task and take a lease (no slash) | None | `data` / `meta`           |
| POST   | `/api/v1/tasks/{task_id}/complete` | Complete a claimed task (no slash)       | None | `data` / `meta`           |

`claim` takes `agent_id` and an optional `lease_minutes` (default 30) in the JSON body.

### `/api/v1/results/` — Evidence Surface

External systems push enforcement evidence here. Dashboards read enforcement history, test runs, and conflict data.

| Method | URL                                                | Description                              | Auth    | Request Schema            | Response Schema               |
| ------ | -------------------------------------------------- | ---------------------------------------- | ------- | ------------------------- | ----------------------------- |
| POST   | `/api/v1/results/enforcement/`                     | Submit enforcement evidence from product | API key | `ValidationResultRequest` | `ValidationResultResponse`    |
| GET    | `/api/v1/results/enforcement-runs/`                | List enforcement run history             | None    | —                         | `ValidationRunsResponse`      |
| GET    | `/api/v1/results/enforcement-runs/latest/`         | Most recent enforcement run              | None    | —                         | `data` / `meta`               |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/`       | Single enforcement run detail            | None    | —                         | `ValidationRunDetailResponse` |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/diff/`  | Compare a run against its predecessor    | None    | —                         | `data` / `meta`               |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/steps/` | Step-level verification evidence         | None    | —                         | `ValidationRunStepsResponse`  |
| GET    | `/api/v1/results/test-runs/latest/`                | Latest CI/CD test run                    | None    | —                         | `LatestTestRunResponse`       |
| GET    | `/api/v1/results/conflicts/`                       | List detected conflicts                  | None    | —                         | `data` / `meta`               |
| POST   | `/api/v1/results/conflicts/detect`                 | Run conflict detection (no slash)        | None    | —                         | `data` / `meta`               |
| GET    | `/api/v1/results/conflicts/{id}`                   | Conflict detail (no slash)               | None    | —                         | `data` / `meta`               |
| POST   | `/api/v1/results/conflicts/{id}/resolve`           | Resolve a conflict (no slash)            | None    | —                         | `data` / `meta`               |

Schema names still read "Validation" because the Django models and their serializers keep those names. The URLs say "enforcement" — see §4.

### `/api/v1/integrations/` — External System Hooks

Webhook receivers, health checks, and SLO pushes from observability platforms.

| Method | URL                                            | Description                             | Auth                  | Request Schema      | Response Schema        |
| ------ | ---------------------------------------------- | --------------------------------------- | --------------------- | ------------------- | ---------------------- |
| POST   | `/api/v1/integrations/slo/status/`             | Push SLO status from observability tool | API key               | `SLOStatusRequest`  | `SLOStatusResponse`    |
| POST   | `/api/v1/integrations/linear/test-connection/` | Test Linear integration connection      | API key               | `LinearTestRequest` | `LinearTestResponse`   |
| GET    | `/api/v1/integrations/linear/health/`          | Check Linear integration health         | None                  | —                   | `LinearHealthResponse` |
| POST   | `/api/v1/integrations/webhooks/github/`        | Receive GitHub webhook events           | HMAC-SHA256 signature | (GitHub event body) | —                      |

The webhook routes register only when `jwt` is importable and `GITHUB_WEBHOOK_SECRET` is set. Without both, neither the `/api/v1/` path nor its legacy alias exists, and the OpenAPI spec omits them.

### Infrastructure (unversioned)

| Method | URL                 | Description             | Auth |
| ------ | ------------------- | ----------------------- | ---- |
| GET    | `/api/openapi.json` | OpenAPI 3.0 spec (JSON) | None |
| GET    | `/api/docs/`        | Swagger UI              | None |

---

## 3. Deprecation Strategy

### Redirect Behavior

Each retired URL redirects to its `/api/v1/` successor. The status depends on the **request method**, not on the route: safe methods (GET, HEAD, OPTIONS) get **301 Moved Permanently**; every other method gets **308 Permanent Redirect**, which preserves the method and request body.

| Request method     | Redirect code | Reason                           |
| ------------------ | ------------- | -------------------------------- |
| GET, HEAD, OPTIONS | 301           | Method preservation guaranteed   |
| POST, PUT, DELETE  | 308           | Prevents method downgrade to GET |

Deciding per request means a route that serves both GET and POST answers each caller correctly.

Query strings pass through to the successor URL. Path captures pass through as keyword arguments, so a legacy route and its successor name their captures identically.

**GET example:**

```http
HTTP/1.1 301 Moved Permanently
Location: /api/v1/specs/REQ-042/status/
Deprecation: true
Link: </api/v1/specs/REQ-042/status/>; rel="successor-version"
Sunset: Sat, 28 Nov 2026 00:00:00 GMT
Content-Type: application/json

{"message": "This endpoint has moved to /api/v1/specs/REQ-042/status/", "code": "ENDPOINT_MOVED"}
```

**POST example:**

```http
HTTP/1.1 308 Permanent Redirect
Location: /api/v1/results/enforcement/
Deprecation: true
Link: </api/v1/results/enforcement/>; rel="successor-version"
Sunset: Sat, 28 Nov 2026 00:00:00 GMT
Content-Type: application/json

{"message": "This endpoint has moved to /api/v1/results/enforcement/", "code": "ENDPOINT_MOVED"}
```

Redirect bodies use `message` (not `error`) because a redirect is not an error. The `error` key is reserved for 4xx/5xx responses per the naming conventions.

### The GitHub Webhook Exception

`POST /api/webhooks/github/` serves the webhook view directly instead of redirecting. GitHub does not follow redirects on webhook delivery: a 308 shows up in the App's delivery log as a failure, and the payload is dropped without reaching SpecTrace.

Point the GitHub App's webhook URL at `/api/v1/integrations/webhooks/github/`. Once no deliveries arrive on the old path, replace the alias with a redirect.

The alias stays out of the OpenAPI spec, so the spec describes one surface.

### Headers

Every redirect from a retired URL carries four headers:

| Header        | Format                        | Example                                                   |
| ------------- | ----------------------------- | --------------------------------------------------------- |
| `Deprecation` | `true` (per RFC 8594)         | `true`                                                    |
| `Link`        | Successor URL with rel        | `</api/v1/results/enforcement/>; rel="successor-version"` |
| `Sunset`      | HTTP-date (RFC 7231 §7.1.1.1) | `Sat, 28 Nov 2026 00:00:00 GMT`                           |
| `Location`    | Successor URL path            | `/api/v1/results/enforcement/`                            |

The webhook alias carries none of these — it returns whatever the webhook view returns.

### Known Consumers

The API currently serves three consumer types:

1. **SpecTrace agents** — claim tasks, submit enforcement results, run conflict detection
2. **CI pipelines** — push test results, query enforcement run history
3. **SpecTrace dashboard** — reads requirement status, conflict data, flow run status

GitHub is the one external sender, and it reaches the webhook alias rather than a redirect. Every other consumer is internal. The 90-day sunset window is conservative for an internal API but leaves margin for any undiscovered caller.

### Timeline

| Phase          | Duration     | Dates                   | Retired URL behavior                        |
| -------------- | ------------ | ----------------------- | ------------------------------------------- |
| **Dual-serve** | 90 days      | 2026-08-30 → 2026-11-28 | 301/308 redirect + `Deprecation` + `Sunset` |
| **Sunset**     | After day 90 | 2026-11-29 onward       | 410 Gone + JSON error body                  |

The sunset date lives in one place — `LEGACY_API_SUNSET` in `spectrace/requirements/api_redirects.py`. Change it there and every redirect follows.

### Dual-Serve Phase Details

During the 90-day transition:

1. **`/api/v1/` URLs** serve requests directly. No deprecation headers.
2. **Retired URLs** redirect to the successor. Safe methods get 301, everything else 308. Query strings and request bodies pass through unchanged.
3. **Monitoring** tracks hit counts on retired URLs. If traffic drops to zero before sunset, the routes can be removed early.

### After Sunset

Retired URLs return **410 Gone** with a JSON body:

```http
HTTP/1.1 410 Gone
Content-Type: application/json

{"error": "This endpoint was removed on 2026-11-29. Use /api/v1/results/enforcement/ instead.", "code": "ENDPOINT_REMOVED"}
```

---

## 4. "Validation" Disambiguation Glossary

The codebase uses "validation" for four distinct concepts. This glossary assigns each a precise term.

### Terms

**Enforcement** — Runtime behavior matching. The product reports whether running code matches the spec. Appears in: `submit_validation_result`, `InAppValidation*` models, enforcement runs.

- API URLs use "enforcement": `/api/v1/results/enforcement/`, `/api/v1/results/enforcement-runs/`
- Django models keep their current names (`InAppValidation`, `InAppValidationRun`, `InAppValidationResult`)
- Schema names still read "Validation" (`ValidationResultRequest`, `ValidationRunsResponse`). Renaming them to "Enforcement" is proposed, not shipped — the rename changes the published OpenAPI component names, so it waits for `/api/v2/`.

**Verification** — Step-level evidence within an enforcement run. Each step proves one aspect of the spec holds (or fails). Appears in: `get_validation_run_steps`, step-level data.

- API URLs use "steps" under enforcement runs: `/api/v1/results/enforcement-runs/{run_id}/steps/`
- Shipped schema names read `ValidationStep` and `ValidationRunStepsResponse`. "Verification" is the proposed rename, deferred with the rest.

**Schema-check** — Static validation that YAML link files are well-formed. Checks structure and references, not runtime behavior. Appears in: `validate_links` CLI command.

- CLI keeps `spectrace validate` — "validate my links file" reads naturally
- Proposed API URL: `/api/v1/specs/validate-links/` (not shipped)
- Concept name in docs: "schema-check"

**Input validation** — HTTP request body, path parameter, and format checking. Standard web framework concern. Appears in: `@validate_request`, `validate_flow_path`, `validate_git_ref`.

- No rename needed. "Validate" is the correct term for input checking.
- These stay as-is in the codebase.

### Quick Reference

| Term                 | Definition                                  | API term         | Example URL                                    |
| -------------------- | ------------------------------------------- | ---------------- | ---------------------------------------------- |
| **Enforcement**      | Runtime code-matches-spec checks            | `enforcement`    | `/api/v1/results/enforcement/`                 |
| **Verification**     | Step-level evidence within enforcement runs | `steps`          | `/api/v1/results/enforcement-runs/{id}/steps/` |
| **Schema-check**     | Static YAML link file structure validation  | `validate-links` | `/api/v1/specs/validate-links/` (not shipped)  |
| **Input validation** | HTTP request/path format checking           | `validate`       | (decorator, not an endpoint)                   |

### CLI-to-API Mapping

Every CLI command with its API endpoint, shipped or proposed.

| CLI Command                        | Management Command         | Shipped API endpoint                    | Proposed API endpoint              |
| ---------------------------------- | -------------------------- | --------------------------------------- | ---------------------------------- |
| `spectrace coverage`               | `spec_coverage`            | GET `/api/v1/specs/coverage/`           | —                                  |
| `spectrace impact <base> <head>`   | `impact_analysis`          | GET `/api/v1/specs/impact/`             | —                                  |
| `spectrace conflicts`              | `detect_conflicts`         | POST `/api/v1/results/conflicts/detect` | —                                  |
| `spectrace drift`                  | `detect_drift`             | GET `/api/v1/specs/drift/`              | —                                  |
| `spectrace agent tasks`            | `agent_tasks`              | GET `/api/v1/tasks/`                    | —                                  |
| `spectrace agent claim <task_id>`  | `agent_claim`              | POST `/api/v1/tasks/{task_id}/claim`    | —                                  |
| `spectrace agent submit <task_id>` | `agent_submit`             | POST `/api/v1/tasks/{task_id}/complete` | —                                  |
| `spectrace context <task_id>`      | `agent_context`            | —                                       | `/api/v1/tasks/{task_id}/context/` |
| `spectrace risks`                  | `detect_integration_risks` | —                                       | `/api/v1/specs/integration-risks/` |
| `spectrace invariants`             | `check_invariants`         | —                                       | `/api/v1/specs/invariants/`        |
| `spectrace validate <links_file>`  | `validate_links`           | —                                       | `/api/v1/specs/validate-links/`    |
| `spectrace agent register`         | `agent_register`           | —                                       | `/api/v1/tasks/agents/register/`   |
| `spectrace agent start <task_id>`  | `agent_start`              | —                                       | `/api/v1/tasks/{task_id}/start/`   |
| `spectrace agent review <task_id>` | `agent_review`             | —                                       | `/api/v1/tasks/{task_id}/review/`  |
| `spectrace agent merge <task_id>`  | `agent_merge`              | —                                       | `/api/v1/tasks/{task_id}/merge/`   |
| `spectrace agent expire-leases`    | `expire_leases`            | —                                       | `/api/v1/tasks/leases/expire/`     |
| `spectrace demo`                   | `demo_impact`              | —                                       | (web UI only, no API planned)      |

**Summary:** 17 CLI commands. Seven have an API equivalent today. Nine have a proposed endpoint for a future phase, and `spectrace demo` stays web-only.

`spectrace agent submit` and `POST /api/v1/tasks/{task_id}/complete` both call `submit_for_review`; the endpoint takes the command's `--agent` and `--commit-sha` as `agent_id` and `commit_sha` in the JSON body.

`GET /api/v1/specs/{external_id}/context` returns spec context keyed by requirement ID. It has no CLI counterpart, and it does not replace `spectrace context <task_id>`, which resolves a task first.
