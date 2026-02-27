# spec-trace API Restructure

Redesign spec-trace's API surface around consumer need, not implementation
domain.

**Accountable:** Mainstay (contract stability), Ambassador (API discoverability)

**Status:** Completed

## Scope

| API Restructure Is                                    | API Restructure Isn't                        |
| ----------------------------------------------------- | -------------------------------------------- |
| Reorganizing endpoints by audience                    | Rewriting the application                    |
| Defining a stable contract for agents and CI          | Adding new features to spec-trace            |
| Naming and URL structure redesign                     | Changing the underlying data model           |
| Making "validation" mean one thing per context        | Removing existing functionality              |
| Aligning CLI commands and dashboard navigation to API | Building a new CLI or dashboard from scratch |

## Problem

spec-trace's API surface (26 REST endpoints, 23 web UI routes, 40+ CLI commands)
grew organically. Endpoints organize by data model -- specs, validations, runs
-- rather than by what consumers need to do.

Three audiences navigate a single flat structure:

| Audience     | Primary need                           | Current friction                            |
| ------------ | -------------------------------------- | ------------------------------------------- |
| Agents       | Read specs, claim tasks, post results  | No task-oriented endpoints                  |
| CI pipelines | Run validations, report coverage       | "Validation" means three different things   |
| Humans       | Browse specs, review drift, see impact | Dashboard navigation mirrors implementation |

The word "validation" appears in endpoints meaning: schema validation (is the
spec well-formed?), spec enforcement (does the code match the spec?), and result
verification (did the test pass?). Agents cannot distinguish these without
reading documentation.

## Recommended Structure

Four audience-oriented API groups replace the current flat namespace:

| Group                | Audience         | Pattern     | Purpose               |
| -------------------- | ---------------- | ----------- | --------------------- |
| `/api/specs/`        | All              | Read-heavy  | The contract surface  |
| `/api/tasks/`        | Agents           | Read-write  | The agent surface     |
| `/api/results/`      | CI, agents       | Write-heavy | The evidence surface  |
| `/api/integrations/` | External systems | Config      | External system hooks |

Key endpoints per group:

- **`/api/specs/`** -- `GET /api/specs/:id`, `GET /api/specs/:id/context`,
  `GET /api/specs/coverage`, `GET /api/specs/drift`, `GET /api/specs/impact`
- **`/api/tasks/`** -- `GET /api/tasks/pending`, `POST /api/tasks/:id/claim`,
  `POST /api/tasks/:id/complete`
- **`/api/results/`** -- `POST /api/results/`, `GET /api/results/conflicts`,
  `GET /api/results/:specId/history`
- **`/api/integrations/`** -- `GET /api/integrations/`,
  `POST /api/integrations/webhooks`

## Phases

### Phase 1: API contract definition

Define the URL structure, resource naming, and request/response shapes. No
implementation -- produce a specification document.

**Deliverables:**

- OpenAPI spec or equivalent contract document
- Endpoint inventory mapping old endpoints to new groups
- Naming conventions document (singular vs plural, verb placement, query params)

**Acceptance criteria:**

- [ ] Every existing endpoint maps to exactly one new endpoint
- [ ] "Validation" replaced with specific terms per context (schema-check,

      enforcement, verification)

- [ ] Contract document reviewed by Mainstay for stability
- [ ] Contract document reviewed by Ambassador for discoverability

### Phase 2: Agent-facing endpoints

Implement `/api/tasks/` and `/api/specs/context` -- the minimum surface agents
need to read specs, claim work, and report completion.

**Deliverables:**

- `/api/tasks/pending`, `/api/tasks/:id/claim`, `/api/tasks/:id/complete`
- `/api/specs/:id/context` -- returns spec with surrounding context an agent
  needs (related specs, recent results, coverage gaps)

**Acceptance criteria:**

- [ ] An agent can discover, claim, execute, and complete a task using only

      `/api/tasks/` and `/api/specs/` endpoints

- [ ] `/api/specs/context` returns sufficient context for agent execution

      without additional lookups

- [ ] Old agent-relevant endpoints return deprecation headers pointing to new

      locations

### Phase 3: Enforcement endpoints

Implement `/api/specs/coverage` and `/api/specs/drift` -- the endpoints CI
pipelines and agents need to detect spec violations.

**Deliverables:**

- `/api/specs/coverage` -- which specs have passing results, which are stale
- `/api/specs/drift` -- which specs diverge from their implementation

**Acceptance criteria:**

- [ ] CI pipeline can query coverage and drift in a single request per endpoint
- [ ] Drift detection returns actionable diffs, not boolean pass/fail
- [ ] Coverage endpoint distinguishes "never tested" from "tested but stale"

### Phase 4: Impact analysis maturation

Implement `/api/specs/impact` and `/api/results/conflicts` -- the endpoints that
answer "what breaks if I change this?"

**Deliverables:**

- `/api/specs/impact` -- given a spec or code change, returns affected specs
- `/api/results/conflicts` -- surfaces contradictory results across specs

**Acceptance criteria:**

- [ ] Impact query accepts a file path or spec ID and returns the dependency

      graph of affected specs

- [ ] Conflict detection surfaces contradictions automatically, not on manual

      trigger

- [ ] Results include confidence scores or evidence links

### Phase 5: UX polish

Align CLI commands and dashboard navigation to the new API groups. The machine
works; make it legible to humans.

**Deliverables:**

- CLI command groups mirror API groups (`st specs`, `st tasks`, `st results`)
- Dashboard navigation reflects the four-group structure
- Help text and error messages use the new vocabulary consistently

**Acceptance criteria:**

- [ ] CLI `--help` output reflects the four API groups
- [ ] Dashboard navigation matches API group names
- [ ] No CLI command or UI label uses the ambiguous term "validation"
- [ ] Old CLI commands print deprecation notices pointing to new equivalents

## Council Input

| Seat       | Question                                                             |
| ---------- | -------------------------------------------------------------------- |
| Mainstay   | Does the four-group structure hold under future feature growth?      |
| Ambassador | Can a new consumer discover the right endpoint within 30 seconds?    |
| Critic     | Is this restructure premature before agent integration proves value? |

## Dependencies

None external. This initiative is the root of the dependency chain:

```text
API contract (Phase 1)
    ├── Agent integration (Phase 2)
    ├── Enforcement (Phase 3)
    ├── Impact analysis (Phase 4)
    └── UX polish (Phase 5)
```

## Related

- [Agent Optimization](agent-optimization.md) -- agent-facing endpoint design
  benefits from the context injection model
- [Agent Framework Study](agent-framework-study.md) -- framework patterns inform
  the task-claiming API design

## History

| Date       | Action                                                   |
| ---------- | -------------------------------------------------------- |
| 2026-02-27 | Initiative created from /ia interview on API findability |
