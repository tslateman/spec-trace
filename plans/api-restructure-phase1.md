Status: Draft

# Plan: API Restructure Phase 1 -- Contract Definition

## Context

Phase 1 of the
[spec-trace API Restructure](~/dev/council/initiatives/spec-trace-api.md)
initiative. This phase produces a specification document -- no implementation
changes.

spec-trace's API surface grew around its data model (validations, runs,
conflicts) rather than what consumers need to do. Three audiences (agents, CI
pipelines, humans) navigate a single flat namespace. The word "validation"
appears in endpoints meaning schema validation, spec enforcement, and result
verification interchangeably.

Phase 1 defines the URL structure, resource naming, and request/response shapes
for four audience-oriented API groups:

| Group                | Audience         | Pattern     |
| -------------------- | ---------------- | ----------- |
| `/api/specs/`        | All              | Read-heavy  |
| `/api/tasks/`        | Agents           | Read-write  |
| `/api/results/`      | CI, agents       | Write-heavy |
| `/api/integrations/` | External systems | Config      |

## What to Do

### 1. Inventory all existing endpoints

Read these files and catalog every endpoint with its HTTP method, URL pattern,
authentication requirement, and current OpenAPI tag:

- `spectrace/requirements/urls.py` -- all URL patterns (lines 144-200 for API,
  lines 44-118 for web UI, lines 121-141 for webhooks)
- `spectrace/requirements/api.py` -- all 14 API view functions and their
  decorators
- `spectrace/requirements/webhooks.py` -- GitHub webhook endpoint
- `spectrace/requirements/openapi/views.py` -- OpenAPI spec + Swagger UI
  endpoints
- `spectrace/cli.py` -- 18 CLI commands (10 top-level, 8 under `agent`
  subgroup)

Current REST API endpoints (14 core + 3 infrastructure):

| #   | Method | Current URL                                 | View Function              | Auth | Tag             |
| --- | ------ | ------------------------------------------- | -------------------------- | ---- | --------------- |
| 1   | POST   | `/api/slo/status/`                          | `update_slo_status`        | Yes  | SLO             |
| 2   | POST   | `/api/validation/result/`                   | `submit_validation_result` | Yes  | Validation      |
| 3   | GET    | `/api/requirement/<id>/status/`             | `get_requirement_status`   | No   | Requirements    |
| 4   | POST   | `/api/integrations/linear/test-connection/` | `test_linear_connection`   | Yes  | Integrations    |
| 5   | GET    | `/api/integrations/linear/health/`          | `get_linear_health`        | No   | Integrations    |
| 6   | GET    | `/api/validation-runs/`                     | `list_validation_runs`     | No   | Validation Runs |
| 7   | GET    | `/api/validation-runs/<id>/`                | `get_validation_run`       | No   | Validation Runs |
| 8   | GET    | `/api/validation-runs/<id>/steps/`          | `get_validation_run_steps` | No   | Validation Runs |
| 9   | GET    | `/api/flow-runs/running/`                   | `get_running_flow_runs`    | No   | Flows           |
| 10  | GET    | `/api/test-runs/latest/`                    | `get_latest_test_run`      | No   | Test Runs       |
| 11  | GET    | `/api/conflicts/`                           | `list_conflicts`           | No   | Conflicts       |
| 12  | POST   | `/api/conflicts/detect/`                    | `detect_conflicts`         | Yes  | Conflicts       |
| 13  | GET    | `/api/conflicts/<id>/`                      | `get_conflict`             | No   | Conflicts       |
| 14  | POST   | `/api/conflicts/<id>/resolve/`              | `resolve_conflict`         | Yes  | Conflicts       |
| 15  | POST   | `/api/webhooks/github/`                     | `github_webhook`           | HMAC | (none)          |
| 16  | GET    | `/api/openapi.json`                         | `openapi_spec`             | No   | (infra)         |
| 17  | GET    | `/api/docs/`                                | `swagger_ui`               | No   | (infra)         |

### 2. Map each endpoint to a new group

Assign every endpoint to one of the four groups. Document the mapping in a table
with old URL, new URL, and rationale for the grouping.

Use the initiative's recommended structure as the starting point:

- **`/api/specs/`** -- read-heavy contract surface. Requirements, coverage,
  drift, impact.
- **`/api/tasks/`** -- agent read-write surface. Pending tasks, claim,
  complete, flow runs.
- **`/api/results/`** -- evidence surface. Validation submissions, test runs,
  conflict detection, conflict resolution.
- **`/api/integrations/`** -- external system hooks. Linear, GitHub webhooks,
  SLO status.

Endpoints that do not fit cleanly into one group need explicit justification.

### 3. Replace ambiguous "validation" with specific terms

The word "validation" currently means three different things:

| Current usage              | Actual meaning                        | Replacement term |
| -------------------------- | ------------------------------------- | ---------------- |
| `submit_validation_result` | Product reports whether code matches  | **enforcement**  |
| `list_validation_runs`     | History of enforcement batches        | **enforcement**  |
| `validate_links` (CLI)     | Schema check on test-requirement YAML | **schema-check** |
| `InAppValidation` (model)  | Runtime enforcement of a spec         | **enforcement**  |
| Validation run steps       | Granular enforcement evidence         | **verification** |

For each occurrence, propose the specific replacement term. Do NOT rename models
or database tables -- this is URL and documentation vocabulary only.

### 4. Produce the endpoint mapping document

Create `docs/api-contract.md` containing:

1. **Endpoint mapping table** -- old URL to new URL, one row per endpoint
2. **New endpoint catalog** -- grouped by the four API groups, with HTTP method,
   URL, description, auth requirement, request/response shape references
3. **Deprecation strategy** -- how old URLs redirect to new ones (HTTP 301 with
   `Deprecation` header, sunset date)
4. **"Validation" disambiguation glossary** -- the three terms and where each
   applies

### 5. Define naming conventions

Document these conventions in `docs/api-naming-conventions.md`:

- **Singular vs plural**: collections use plural (`/api/specs/`), individual
  resources use singular ID (`/api/specs/:id`)
- **Verb placement**: verbs appear as sub-resources of the noun they act on
  (`/api/tasks/:id/claim`, not `/api/claim-task/:id`)
- **Query parameters**: filtering uses `?field=value`, pagination uses
  `?page=N&per_page=N`, time ranges use `?since=ISO8601&until=ISO8601`
- **Response envelope**: top-level key matches the resource name (`{"specs":
[...]}`, `{"task": {...}}`), pagination metadata in `"pagination"` key
- **Error format**: `{"error": "message", "code": "MACHINE_READABLE"}` with
  appropriate HTTP status codes
- **Versioning**: URL prefix (`/api/v1/`) vs header -- make a recommendation
  with rationale

## What NOT to Do

- Do NOT modify any Python source files. This phase produces documents only.
- Do NOT change database models, migrations, or table names.
- Do NOT alter existing URL patterns or add new endpoints.
- Do NOT break existing API consumers -- no URLs change in this phase.
- Do NOT design request/response schemas in detail. Map the structure; leave
  schema design for Phase 2+.
- Do NOT rename `InAppValidation` or other model classes. Vocabulary changes
  apply to URLs and documentation only.
- Do NOT add API versioning infrastructure. Recommend a strategy; implement
  later.

## Files to Create

- `docs/api-contract.md` -- endpoint mapping, new catalog, deprecation strategy,
  validation glossary
- `docs/api-naming-conventions.md` -- naming rules for all future API work

## Files to Read (not modify)

- `spectrace/requirements/urls.py` -- current URL patterns
- `spectrace/requirements/api.py` -- current API view functions
- `spectrace/requirements/webhooks.py` -- webhook endpoint
- `spectrace/requirements/openapi/views.py` -- OpenAPI infrastructure
- `spectrace/requirements/openapi/schemas.py` -- current response schemas
- `spectrace/requirements/openapi/decorators.py` -- `@validate_request` metadata
- `spectrace/requirements/openapi/introspection.py` -- endpoint discovery
- `spectrace/cli.py` -- CLI command surface
- `spectrace/requirements/views.py` -- web UI view functions
- `spectrace/requirements/models.py` -- model names (to avoid renaming)

## Acceptance Criteria

- [ ] Every existing API endpoint (14 core + webhook + OpenAPI infra) maps to
      exactly one new endpoint in the contract document
- [ ] "Validation" replaced with specific terms per context (schema-check,
      enforcement, verification) throughout the contract document
- [ ] Naming conventions document covers singular/plural, verb placement, query
      params, response envelope, error format, and versioning
- [ ] Deprecation strategy defines redirect behavior, header format, and sunset
      timeline
- [ ] CLI commands listed with their corresponding API endpoint (where one
      exists) to enable Phase 5 alignment
- [ ] Contract document reviewed by Mainstay for stability
- [ ] Contract document reviewed by Ambassador for discoverability

## Testing

No code changes means no automated tests. Verify the plan was followed by
checking:

```bash
# Both documents exist
test -f docs/api-contract.md && echo "contract: ok" || echo "contract: MISSING"
test -f docs/api-naming-conventions.md && echo "naming: ok" || echo "naming: MISSING"
```

```bash
# Every current API endpoint appears in the mapping table
grep -c '|' docs/api-contract.md
# Should show at least 17 table rows (14 core + webhook + 2 infra)
```

```bash
# "validation" does not appear as an endpoint name in the new catalog
# (only in the old-to-new mapping and the disambiguation glossary)
grep -c '/api/.*validation' docs/api-contract.md
# Non-zero only in the "old URL" column, never in the "new URL" column
```

```bash
# Naming conventions document covers all required topics
for topic in "singular" "plural" "verb" "query" "pagination" "envelope" \
             "error" "versioning"; do
  grep -qi "$topic" docs/api-naming-conventions.md && \
    echo "$topic: ok" || echo "$topic: MISSING"
done
```

Manual review: have Mainstay and Ambassador read the contract document and
confirm it meets their criteria from the initiative.
