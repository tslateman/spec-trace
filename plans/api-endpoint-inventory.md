# API Endpoint Inventory

This document maps the existing `spec-trace` REST endpoints (from `api_urlpatterns` and `webhook_urlpatterns`) and agent-facing CLI commands (`agent_*.py`) to the new API group structure defined in `plans/spec-trace-api.md`.

The ambiguous term "validation" has been systematically replaced with context-specific terminology (e.g., "verification" for test results).

## 1. /api/specs/ (The contract surface)

_Endpoints for reading spec data, context, and coverage._

| Current Route / Command                     | New Endpoint                           | Method | Context / Notes                                                       |
| :------------------------------------------ | :------------------------------------- | :----- | :-------------------------------------------------------------------- |
| `api/requirement/<str:external_id>/status/` | `/api/specs/<str:external_id>/status`  | GET    | Consolidates 'requirement' to 'specs' naming                          |
| `agent_context` (CLI command)               | `/api/specs/<str:external_id>/context` | GET    | Returns surrounding spec context an agent needs (related specs, gaps) |

## 2. /api/tasks/ (The agent surface)

_Endpoints for agent workflow, discovery, and execution._

| Current Route / Command        | New Endpoint                   | Method | Context / Notes                                                       |
| :----------------------------- | :----------------------------- | :----- | :-------------------------------------------------------------------- |
| `agent_tasks` (CLI command)    | `/api/tasks/`                  | GET    | Provides listing; use `?status=pending` for unclaimed                 |
| `agent_claim` (CLI command)    | `/api/tasks/<str:id>/claim`    | POST   | Claim an unclaimed task                                               |
| `agent_start` (CLI command)    | `/api/tasks/<str:id>/start`    | POST   | Transition task to in-progress                                        |
| `agent_submit` (CLI command)   | `/api/tasks/<str:id>/complete` | POST   | Submit work for review (Aligns with API plan `/complete` terminology) |
| `agent_review` (CLI command)   | `/api/tasks/<str:id>/review`   | POST   | Submit review (approve, request changes, reject)                      |
| `agent_merge` (CLI command)    | `/api/tasks/<str:id>/merge`    | POST   | Mark approved task as merged                                          |
| `agent_register` (CLI command) | `/api/tasks/agents/register`   | POST   | Register or update agent identity                                     |

## 3. /api/results/ (The evidence surface)

_Endpoints for CI pipelines and agents to post evidence, coverage, and detect drift/conflicts._

| Current Route / Command                    | New Endpoint                                        | Method | Context / Notes                                              |
| :----------------------------------------- | :-------------------------------------------------- | :----- | :----------------------------------------------------------- |
| `api/validation/result/`                   | `/api/results/verification/`                        | POST   | "validation" -> "verification" (test passing results)        |
| `api/validation-runs/`                     | `/api/results/verification-runs/`                   | GET    | "validation" -> "verification" (list test verification runs) |
| `api/validation-runs/<int:run_id>/`        | `/api/results/verification-runs/<int:run_id>`       | GET    | Get test verification run details                            |
| `api/validation-runs/<int:run_id>/steps/`  | `/api/results/verification-runs/<int:run_id>/steps` | GET    | Get test verification run steps                              |
| `api/slo/status/`                          | `/api/results/slo-status/`                          | POST   | Update SLO status from observability platform                |
| `api/flow-runs/running/`                   | `/api/results/flow-runs/running`                    | GET    | Running flow state                                           |
| `api/test-runs/latest/`                    | `/api/results/test-runs/latest`                     | GET    | Latest CI test run data                                      |
| `api/conflicts/`                           | `/api/results/conflicts`                            | GET    | Surfaces contradictions                                      |
| `api/conflicts/detect/`                    | `/api/results/conflicts/detect`                     | POST   | Trigger conflict detection manually                          |
| `api/conflicts/<int:conflict_id>/`         | `/api/results/conflicts/<int:conflict_id>`          | GET    | Get conflict detail                                          |
| `api/conflicts/<int:conflict_id>/resolve/` | `/api/results/conflicts/<int:conflict_id>/resolve`  | POST   | Resolve a conflict                                           |

## 4. /api/integrations/ (External system hooks)

_Endpoints for configuring and reacting to external systems._

| Current Route / Command                    | New Endpoint                                | Method | Context / Notes           |
| :----------------------------------------- | :------------------------------------------ | :----- | :------------------------ |
| `api/integrations/linear/test-connection/` | `/api/integrations/linear/test-connection/` | POST   | Test external connection  |
| `api/integrations/linear/health/`          | `/api/integrations/linear/health/`          | GET    | Get integration health    |
| `api/webhooks/github/`                     | `/api/integrations/webhooks/github/`        | POST   | GitHub webhook entrypoint |

## System / Root Endpoints

_Endpoints for documentation and schemas (Unchanged mapping)._

| Current Route / Command | New Endpoint        | Method | Context / Notes       |
| :---------------------- | :------------------ | :----- | :-------------------- |
| `api/openapi.json`      | `/api/openapi.json` | GET    | OpenAPI specification |
| `api/docs/`             | `/api/docs/`        | GET    | Swagger UI            |

## Deprecation Strategy

As the API transitions to the new `/api/v1/` structure, a formal deprecation strategy ensures backward compatibility for existing scripts, agents, and external systems relying on the legacy endpoints.

1. **HTTP Redirects:** Whenever feasible, deprecated GET endpoints should return a `301 Moved Permanently` or `308 Permanent Redirect` pointing to the new `v1` endpoint. Clients that follow redirects will transparently succeed.
2. **HTTP 410 Gone:** When a direct mapping is not possible, or when a mutating endpoint (POST/PUT/DELETE) is deprecated and redirects are unsafe, the old endpoint must return a `410 Gone`.
3. **Deprecation Headers:** Both redirects (301/308) and `410 Gone` responses must include the standard HTTP `Deprecation` header (e.g., `Deprecation: @1672531200` to indicate when it was deprecated) and a `Link` header pointing to the new alternative:
   ```http
   Link: <https://api.spectrace.com/api/v1/specs/>; rel="alternate"
   ```
4. **Sunset Timeline:** Old endpoints should remain active and return deprecation warnings for at least 6 months before being fully removed from the codebase.
