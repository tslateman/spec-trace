# API Contract — SpecTrace v1

Updated 2026-09-11 against `plans/openapi-worker.yaml` (SpecTrace Worker API 1.0.0), the frozen v1 contract the Cloudflare Worker serves.

This contract catalogs the 43 operations the Worker serves, maps each to the Django URL it succeeds, and records how the retiring Django server treats its old URLs until they are removed.

### Versioning

Every operation lives under `/api/v1/`, grouped into `/api/v1/specs/`, `/api/v1/tasks/`, `/api/v1/results/`, and `/api/v1/integrations/`. One path sits outside the version prefix: `GET /health`, which pings D1 and needs no key.

The Worker serves nothing under the unversioned `/api/` surface and does not host Swagger UI or `/api/openapi.json`; the contract lives in the repository as `plans/openapi-worker.yaml`. The Django server still answers its retired URLs with redirects during its sunset window. See §3. See `docs/api-naming-conventions.md` §6 for the versioning rationale.

---

## 1. Endpoint Mapping Table

Every operation the Worker serves, with its `operationId` from the contract and the Django URL it succeeds. "Same path" means the Django server served the operation at this `/api/v1/` path already. "New in v1" means the Worker introduced it.

| #   | Method | `/api/v1/` path                                    | `operationId`                               | Django predecessor                     |
| --- | ------ | -------------------------------------------------- | ------------------------------------------- | -------------------------------------- |
| 1   | GET    | `/api/v1/specs/`                                   | `api-v1-specs_get`                          | Same path                              |
| 2   | PUT    | `/api/v1/specs/`                                   | `api-v1-specs_put`                          | New in v1                              |
| 3   | GET    | `/api/v1/specs/coverage/`                          | `api-v1-specs-coverage_get`                 | Same path                              |
| 4   | GET    | `/api/v1/specs/drift/`                             | `api-v1-specs-drift_get`                    | Same path                              |
| 5   | GET    | `/api/v1/specs/impact/`                            | `api-v1-specs-impact_get`                   | Same path                              |
| 6   | GET    | `/api/v1/specs/{external_id}/context`              | `api-v1-specs-context_get`                  | Same path                              |
| 7   | GET    | `/api/v1/specs/{external_id}/status/`              | `api-v1-specs-status_get`                   | `/api/requirement/{id}/status/`        |
| 8   | GET    | `/api/v1/tasks/`                                   | `api-v1-tasks-list_get`                     | Same path                              |
| 9   | POST   | `/api/v1/tasks/`                                   | `api-v1-tasks-create_post`                  | New in v1                              |
| 10  | POST   | `/api/v1/tasks/agents/register/`                   | `api-v1-tasks-agents-register_post`         | Same path                              |
| 11  | GET    | `/api/v1/tasks/flow-runs/running/`                 | `api-v1-tasks-flow-runs-running_get`        | `/api/flow-runs/running/`              |
| 12  | GET    | `/api/v1/tasks/outcomes`                           | `api-v1-tasks-outcomes_get`                 | New in v1                              |
| 13  | POST   | `/api/v1/tasks/outcomes/ack`                       | `api-v1-tasks-outcomes-ack_post`            | New in v1                              |
| 14  | POST   | `/api/v1/tasks/{task_id}/approve-spec`             | `api-v1-tasks-approve-spec_post`            | New in v1                              |
| 15  | POST   | `/api/v1/tasks/{task_id}/intent-validations`       | `api-v1-tasks-intent-validations_post`      | New in v1                              |
| 16  | POST   | `/api/v1/tasks/{task_id}/claim`                    | `api-v1-tasks-claim_post`                   | Same path                              |
| 17  | POST   | `/api/v1/tasks/{task_id}/start`                    | `api-v1-tasks-start_post`                   | Same path                              |
| 18  | POST   | `/api/v1/tasks/{task_id}/complete`                 | `api-v1-tasks-complete_post`                | Same path                              |
| 19  | POST   | `/api/v1/tasks/{task_id}/submit`                   | `api-v1-tasks-submit_post`                  | Same path                              |
| 20  | POST   | `/api/v1/tasks/{task_id}/review`                   | `api-v1-tasks-review_post`                  | Same path                              |
| 21  | POST   | `/api/v1/tasks/{task_id}/merge`                    | `api-v1-tasks-merge_post`                   | Same path                              |
| 22  | POST   | `/api/v1/tasks/{task_id}/release`                  | `api-v1-tasks-release_post`                 | Same path                              |
| 23  | POST   | `/api/v1/results/enforcement/`                     | `api-v1-results-enforcement_post`           | `/api/validation/result/`              |
| 24  | GET    | `/api/v1/results/enforcement-runs/`                | `api-v1-results-enforcement-runs_get`       | `/api/validation-runs/`                |
| 25  | GET    | `/api/v1/results/enforcement-runs/latest/`         | `api-v1-enforcement-runs-latest_get`        | Same path                              |
| 26  | GET    | `/api/v1/results/enforcement-runs/{run_id}/`       | `api-v1-results-enforcement-run-detail_get` | `/api/validation-runs/{run_id}/`       |
| 27  | GET    | `/api/v1/results/enforcement-runs/{run_id}/diff/`  | `api-v1-enforcement-run-diff_get`           | Same path                              |
| 28  | GET    | `/api/v1/results/enforcement-runs/{run_id}/steps/` | `api-v1-results-enforcement-run-steps_get`  | `/api/validation-runs/{run_id}/steps/` |
| 29  | GET    | `/api/v1/results/vendor-coverage/`                 | `api-v1-results-vendor-coverage_get`        | Same path                              |
| 30  | GET    | `/api/v1/results/test-runs/latest/`                | `api-v1-results-test-runs-latest_get`       | `/api/test-runs/latest/`               |
| 31  | POST   | `/api/v1/results/test-runs/`                       | `api-v1-results-test-runs_post`             | Same path                              |
| 32  | POST   | `/api/v1/results/impact/`                          | `api-v1-results-impact_post`                | New in v1                              |
| 33  | POST   | `/api/v1/results/drift/`                           | `api-v1-results-drift_post`                 | New in v1                              |
| 34  | GET    | `/api/v1/results/conflicts/`                       | `api-v1-results-conflicts_get`              | `/api/conflicts/`                      |
| 35  | POST   | `/api/v1/results/conflicts/detect`                 | `api-v1-results-conflicts-detect_post`      | `/api/conflicts/detect/`               |
| 36  | GET    | `/api/v1/results/conflicts/{conflict_id}`          | `api-v1-results-conflict-detail_get`        | `/api/conflicts/{id}/`                 |
| 37  | POST   | `/api/v1/results/conflicts/{conflict_id}/resolve`  | `api-v1-results-conflict-resolve_post`      | `/api/conflicts/{id}/resolve/`         |
| 38  | POST   | `/api/v1/integrations/slo/status/`                 | `api-v1-integrations-slo-status_post`       | `/api/slo/status/`                     |

The contract spells rows 6, 12, 13, 14 through 22, and 35 through 37 without a trailing slash. The Worker's router treats a path with and without the slash as the same route, so either spelling reaches the handler; the Django server answered the slashed spelling with 404, so clients that must work against both should copy the contract's spelling.

---

## 2. Endpoint Catalog

The shipped surface, by group. Descriptions come from the contract's operation summaries.

**Auth model:** every `/api/v1/` operation requires the API key. The Worker mounts the key check as middleware on `/api/*` before it mounts the v1 router, so no route under `/api/` bypasses it; the contract declares the same key as the document-wide security requirement. Send the key as `X-API-Key`, or as `Authorization: Bearer <key>` or `Authorization: Api-Key <key>`. A missing or wrong key returns 401 with an `error` envelope whose `code` is `unauthorized`. The key is the `SPECTRACE_API_KEY` Worker secret. When the secret is unset, the middleware throws before any handler runs, so every `/api/*` request fails with 500 and nothing is served unauthenticated.

**Envelope:** operations that the contract defines inline return `{ "data": ... }`, with `"meta"` beside it on paged lists. The Response Schema column names the component inside `data`. Operations carried over from the Django server with their own top-level component (`ValidationResultResponse`, `ValidationRunsPage`, `SLOStatusResponse`, and their kin) return that component bare. Errors return `{ "error": { "code", "message", "details"? } }`.

**Project selection:** the specs and results reads take `?project=`, defaulting to the deployment's `SPECTRACE_PROJECT`. An ambiguous default returns 400 with `details.projects` listing the candidates.

### `/api/v1/specs/` — Contract Surface

Answers "what does the spec say?" `spectrace push` writes the requirement tree here; agents and dashboards read requirements, coverage, drift, and impact. The drift and impact reads serve the report last pushed to `/api/v1/results/`; the Worker computes neither.

| Method | URL                                   | Description                                                   | Auth    | Request Schema    | Response Schema                               |
| ------ | ------------------------------------- | ------------------------------------------------------------- | ------- | ----------------- | --------------------------------------------- |
| GET    | `/api/v1/specs/`                      | Page one project's requirements in tree order                 | API key | —                 | `data: RequirementPage`, `meta: PagePosition` |
| PUT    | `/api/v1/specs/`                      | Replace one project's requirement tree, test links, and flows | API key | `SpecPushRequest` | `data: SpecPushResult`                        |
| GET    | `/api/v1/specs/coverage/`             | Coverage metrics and stale requirements for one project       | API key | —                 | `data: CoverageReport`                        |
| GET    | `/api/v1/specs/drift/`                | The last pushed drift report                                  | API key | —                 | `data: StoredDriftReport`                     |
| GET    | `/api/v1/specs/impact/`               | The last pushed impact report                                 | API key | —                 | `data: StoredImpactReport`                    |
| GET    | `/api/v1/specs/{external_id}/context` | Surrounding context for one requirement (no slash)            | API key | —                 | `data: SpecContext`                           |
| GET    | `/api/v1/specs/{external_id}/status/` | Verification status for one requirement                       | API key | —                 | `data: SpecStatus`                            |

`GET /api/v1/specs/` filters on `status`, `verification_status`, `risk_level`, `tags`, and `parent_id`. `PUT /api/v1/specs/` upserts by `external_id`; with `replace` the payload is the whole project and omitted rows are deleted.

### `/api/v1/tasks/` — Agent Surface

Task listing, agent registration, the claim-to-merge lifecycle, flow orchestration, and the outcome outbox that `spectrace lore sync` drains.

| Method | URL                                          | Description                                | Auth    | Request Schema            | Response Schema                                           |
| ------ | -------------------------------------------- | ------------------------------------------ | ------- | ------------------------- | --------------------------------------------------------- |
| GET    | `/api/v1/tasks/`                             | List agent tasks                           | API key | —                         | `data: TaskSummary[]`, `meta: PagePosition`               |
| POST   | `/api/v1/tasks/`                             | Create a draft task                        | API key | `CreateTaskRequest`       | `data: TaskDraft`                                         |
| POST   | `/api/v1/tasks/agents/register/`             | Register or update an agent                | API key | `RegisterAgentRequest`    | `data: Agent`                                             |
| GET    | `/api/v1/tasks/flow-runs/running/`           | Get running flow runs                      | API key | —                         | `RunningFlowRunsResponse`                                 |
| GET    | `/api/v1/tasks/outcomes`                     | Read the Lore outbox (no slash)            | API key | —                         | `data: TaskOutcome[]`, `meta: CursorPage`                 |
| POST   | `/api/v1/tasks/outcomes/ack`                 | Mark outcomes drained (no slash)           | API key | `OutcomesAckRequest`      | `data: OutcomesAckResult`                                 |
| POST   | `/api/v1/tasks/{task_id}/approve-spec`       | Approve a draft's spec (no slash)          | API key | `ApproveSpecRequest`      | `data: TransitionResult` plus `reviewer_id`               |
| POST   | `/api/v1/tasks/{task_id}/intent-validations` | Record an intent validation (no slash)     | API key | `IntentValidationRequest` | `data: IntentValidation`                                  |
| POST   | `/api/v1/tasks/{task_id}/claim`              | Claim a task and take a lease (no slash)   | API key | `ClaimRequest`            | `data: TransitionResult` plus `lease_expires`, `agent_id` |
| POST   | `/api/v1/tasks/{task_id}/start`              | Start a claimed task (no slash)            | API key | `AgentActionRequest`      | `data: TransitionResult`                                  |
| POST   | `/api/v1/tasks/{task_id}/complete`           | Submit a task for review (no slash)        | API key | `CompleteRequest`         | `data: TransitionResult` plus `commit_sha`                |
| POST   | `/api/v1/tasks/{task_id}/submit`             | Alias of `complete` (no slash)             | API key | `CompleteRequest`         | `data: TransitionResult` plus `commit_sha`                |
| POST   | `/api/v1/tasks/{task_id}/review`             | Review a submitted task (no slash)         | API key | `ReviewRequest`           | `data: TransitionResult`                                  |
| POST   | `/api/v1/tasks/{task_id}/merge`              | Mark an approved task merged (no slash)    | API key | —                         | `data: TransitionResult`                                  |
| POST   | `/api/v1/tasks/{task_id}/release`            | Release a task back to the pool (no slash) | API key | `ReleaseRequest`          | `data: TransitionResult`                                  |

Only a PLANNER agent creates a task, and it lands in `draft`. `approve-spec` takes `reviewer_id` and optional `feedback`; a REVIEWER agent moves the task to `unclaimed`, and the ledger refuses with `SPEC_INCOMPLETE` until the task names requirements, `scope_in`, and `done_when`. `claim` takes `agent_id` and an optional `lease_minutes` in the JSON body. `intent-validations` takes `validator_id`, `commit_sha`, and three scores; `passed` defaults to every score reaching 70, and the Worker refuses the agent that claimed the task with `SELF_INTENT_NOT_ALLOWED`. `complete` and `submit` take `agent_id` and `commit_sha`; only the claiming agent may submit, and the commit's latest intent validation must exist and pass, else `INTENT_NOT_VALIDATED` or `INTENT_FAILED`. Lifecycle transitions that the task's state forbids return 409. `GET /api/v1/tasks/outcomes` takes `since`, the last cursor the reader acknowledged.

### `/api/v1/results/` — Evidence Surface

The product pushes enforcement evidence here, CI pushes JUnit test runs, and the CLI pushes impact and drift reports. Dashboards read enforcement history, vendor coverage, test runs, and conflict data.

| Method | URL                                                | Description                                        | Auth    | Request Schema            | Response Schema                                 |
| ------ | -------------------------------------------------- | -------------------------------------------------- | ------- | ------------------------- | ----------------------------------------------- |
| POST   | `/api/v1/results/enforcement/`                     | Submit verification results                        | API key | `ValidationResultRequest` | `ValidationResultResponse`                      |
| GET    | `/api/v1/results/enforcement-runs/`                | List verification runs                             | API key | —                         | `ValidationRunsPage`                            |
| GET    | `/api/v1/results/enforcement-runs/latest/`         | The most recent enforcement run                    | API key | —                         | `data: LatestEnforcementRun`                    |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/`       | Get verification run detail                        | API key | —                         | `ValidationRunDetailResponse`                   |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/diff/`  | Compare a run against its predecessor              | API key | —                         | `data: EnforcementRunDiff`                      |
| GET    | `/api/v1/results/enforcement-runs/{run_id}/steps/` | Get verification run steps                         | API key | —                         | `ValidationRunStepsResponse`                    |
| GET    | `/api/v1/results/vendor-coverage/`                 | Verification coverage grouped by vendor            | API key | —                         | `data: VendorCoverageReport`                    |
| GET    | `/api/v1/results/test-runs/latest/`                | Get latest test run                                | API key | —                         | `LatestTestRunResponse`                         |
| POST   | `/api/v1/results/test-runs/`                       | Store a JUnit test run                             | API key | `TestRunPush`             | `TestRunPushResponse`                           |
| POST   | `/api/v1/results/impact/`                          | Store an impact report (201)                       | API key | `ImpactReport`            | `data: StoredReportReceipt`                     |
| POST   | `/api/v1/results/drift/`                           | Store a drift report (201)                         | API key | `DriftReport`             | `data: StoredReportReceipt`                     |
| GET    | `/api/v1/results/conflicts/`                       | List detected conflicts                            | API key | —                         | `data: ConflictSummary[]`, `meta: PagePosition` |
| POST   | `/api/v1/results/conflicts/detect`                 | Run conflict detection over stored runs (no slash) | API key | `DetectConflictsRequest`  | `data: DetectConflictsResult`                   |
| GET    | `/api/v1/results/conflicts/{conflict_id}`          | Conflict detail (no slash)                         | API key | —                         | `data: ConflictDetail`                          |
| POST   | `/api/v1/results/conflicts/{conflict_id}/resolve`  | Resolve a conflict (no slash)                      | API key | `ResolveConflictRequest`  | `data: { conflict_id, resolved_at }`            |

Schema names still read "Validation" because the contract keeps the Django component names so clients survive the move. The URLs say "enforcement". See §4.

### `/api/v1/integrations/` — External System Hooks

SLO pushes from observability platforms. The Linear and GitHub webhook integrations stayed on the Django server. See §3.

| Method | URL                                | Description       | Auth    | Request Schema     | Response Schema     |
| ------ | ---------------------------------- | ----------------- | ------- | ------------------ | ------------------- |
| POST   | `/api/v1/integrations/slo/status/` | Update SLO status | API key | `SLOStatusRequest` | `SLOStatusResponse` |

---

## 3. Deprecation Strategy

### Routes the Worker Does Not Serve

These Django routes have no Worker successor. A client that calls them against the Worker gets 401 without a key and 404 with one.

| Method | Django URL                                     | Purpose                            | Status on the Worker                               |
| ------ | ---------------------------------------------- | ---------------------------------- | -------------------------------------------------- |
| GET    | `/api/openapi.json`                            | OpenAPI 3.0 spec (JSON)            | Not served; read `plans/openapi-worker.yaml`       |
| GET    | `/api/docs/`                                   | Swagger UI                         | Not served                                         |
| POST   | `/api/v1/integrations/linear/test-connection/` | Test Linear integration connection | Not served                                         |
| GET    | `/api/v1/integrations/linear/health/`          | Check Linear integration health    | Not served                                         |
| POST   | `/api/v1/integrations/webhooks/github/`        | Receive GitHub webhook events      | Not served; `/api/webhooks/github/` alias likewise |

The rest of this section describes the Django server's redirects from its retired unversioned URLs during the dual-serve window. The Worker serves no retired URL.

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
- Schema names still read "Validation" (`ValidationResultRequest`, `ValidationRunsPage`). Renaming them to "Enforcement" is proposed, not shipped — the rename changes the published OpenAPI component names, so it waits for `/api/v2/`.

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

| CLI Command                                 | Management Command         | Shipped API endpoint                                                      | Proposed API endpoint              |
| ------------------------------------------- | -------------------------- | ------------------------------------------------------------------------- | ---------------------------------- |
| `spectrace coverage`                        | `spec_coverage`            | GET `/api/v1/specs/coverage/`                                             | —                                  |
| `spectrace impact <base> <head>`            | `impact_analysis`          | POST `/api/v1/results/impact/` (push), GET `/api/v1/specs/impact/` (read) | —                                  |
| `spectrace conflicts`                       | `detect_conflicts`         | POST `/api/v1/results/conflicts/detect`                                   | —                                  |
| `spectrace drift`                           | `detect_drift`             | POST `/api/v1/results/drift/` (push), GET `/api/v1/specs/drift/` (read)   | —                                  |
| `spectrace tasks list`                      | —                          | GET `/api/v1/tasks/`                                                      | —                                  |
| `spectrace tasks claim <task_id>`           | —                          | POST `/api/v1/tasks/{task_id}/claim`                                      | —                                  |
| `spectrace tasks complete <task_id>`        | —                          | POST `/api/v1/tasks/{task_id}/complete`                                   | —                                  |
| `spectrace tasks context <task_id>`         | —                          | `/api/v1/tasks/{task_id}/context`                                         | —                                  |
| `spectrace risks`                           | `detect_integration_risks` | —                                                                         | `/api/v1/specs/integration-risks/` |
| `spectrace invariants`                      | `check_invariants`         | —                                                                         | `/api/v1/specs/invariants/`        |
| `spectrace validate <links_file>`           | `validate_links`           | —                                                                         | `/api/v1/specs/validate-links/`    |
| `spectrace tasks register`                  | —                          | POST `/api/v1/tasks/agents/register/`                                     | —                                  |
| `spectrace tasks create <task_id>`          | —                          | POST `/api/v1/tasks/`                                                     | —                                  |
| `spectrace tasks approve-spec <task_id>`    | —                          | POST `/api/v1/tasks/{task_id}/approve-spec`                               | —                                  |
| `spectrace tasks validate-intent <task_id>` | —                          | POST `/api/v1/tasks/{task_id}/intent-validations`                         | —                                  |
| `spectrace tasks start <task_id>`           | —                          | POST `/api/v1/tasks/{task_id}/start`                                      | —                                  |
| `spectrace tasks review <task_id>`          | —                          | POST `/api/v1/tasks/{task_id}/review`                                     | —                                  |
| `spectrace tasks merge <task_id>`           | —                          | POST `/api/v1/tasks/{task_id}/merge`                                      | —                                  |
| `spectrace tasks release <task_id>`         | —                          | POST `/api/v1/tasks/{task_id}/release`                                    | —                                  |
| `python manage.py expire_leases`            | `expire_leases`            | — (the ledger's lease alarm calls `release`)                              | —                                  |
| `spectrace demo`                            | `demo_impact`              | —                                                                         | (web UI only, no API planned)      |

**Summary:** 21 CLI commands. Sixteen have an API equivalent today. Four have a proposed endpoint for a future phase, and `spectrace demo` stays web-only. Every `spectrace tasks` command calls the Worker directly and has no management command; `create`, `approve-spec`, `validate-intent`, and `release` arrived with the Worker. `spectrace push` (`PUT /api/v1/specs/`) and `spectrace lore sync` (`GET /api/v1/tasks/outcomes`, `POST /api/v1/tasks/outcomes/ack`) likewise have no management command. `expire_leases` runs through `python manage.py` only and retires with the Django server.

`POST /api/v1/tasks/{task_id}/submit` aliases `/complete` and is named after the retired `spectrace agent submit` command; `spectrace tasks complete` calls `/complete`. Both take the command's `--agent` and `--commit-sha` as `agent_id` and `commit_sha` in the JSON body.

`GET /api/v1/specs/{external_id}/context` returns spec context keyed by requirement ID. It has no CLI counterpart, and it does not replace `spectrace tasks context <task_id>`, which resolves a task first.
