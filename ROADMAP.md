# Roadmap

What SpecTrace does next, in priority order. This file is the authority for
open work. `.planning/STATE.md` tracks the current position,
`.planning/MILESTONES.md` archives shipped milestones, and
[CHANGELOG.md](CHANGELOG.md) records what landed. When those disagree with this
file about what comes next, this file wins.

Last reviewed: 2026-08-30.

## Now

### 1. Retire the unversioned API

`/api/v1/` and the original `/api/` paths both serve traffic. Nine legacy
endpoints — SLO status, validation result, requirement status, Linear health,
validation runs — never moved. `docs/api-naming-conventions.md` §6 already
decided the outcome: everything under `/api/v1/`, unversioned paths redirect.

**Done when:** every endpoint answers under `/api/v1/`, legacy paths redirect,
and the OpenAPI spec lists one surface.

### 2. Bootstrap the impact graph

`map_init`, `map_validate`, `map_promote`, `code_impact_analysis`, and
`generate_contract` all exist. No `spectrace-map.yaml` exists in any project, so
the code → requirement graph is empty and `code_impact_analysis` has nothing to
walk. The tooling shipped; the data never got seeded.

Run git inference across the ecosystem projects, review the candidate edges,
promote the ones that hold, and generate contract snapshots.

**Done when:** `spectrace impact --code <base>..<head>` returns affected specs
and tests for a real diff in at least two projects, and the CI gate posts a
markdown comment on PRs.

## Next

### 3. Wire the intent validator into the submit path

One agent writes the code and the tests from the same reading of the spec. A
misread spec produces tests that encode the misreading and pass. `validate_intent`
checks execution against stated intent, and it runs only when someone asks it to;
`agent_submit.py` never calls it.

**Done when:** `agent_submit` runs `validate_intent` and records the verdict on the
task, and a task whose tests pass against the wrong intent fails to submit.

### 4. Coverage trend snapshots

`spec_coverage` reports today's numbers and forgets them. `CorpusSnapshot`
stores corpus versions; nothing stores coverage over time. Deferred out of v10
Phase 2 and still the blocker under the trends chart.

**Done when:** a snapshot model records each `spec_coverage` run, the command
reports change against the previous snapshot, and the dashboard charts the
series.

### 5. Grow the corpus beyond four domains

`corpus/` holds billing, identity, platform, and security. Coverage claims are
worth what the corpus covers. Decide which standards, decisions, and
commitments belong in it next, so a moved standard fails a build instead of
aging quietly.

This item also owns `corpus drift --strict` in CI. Corpus entries scope through
`applies_to.paths`, so none match a SpecTrace spec until a corpus for
SpecTrace's own domain lands in `meta/corpus/`.

**Done when:** the corpus covers the domains the specs actually touch, and CI
fails on a stale review.

### 6. Refresh the planning record

`docs/current-state.md` was last updated 2026-02-27 and describes the project as
of v10. `.planning/MILESTONES.md` stops at v9. `.planning/STATE.md` stops at
2026-02-28. All three describe a project six months younger than the one in the
repository, and item 2 above exists because the docs and the code disagreed.

**Done when:** `consolidate` regenerates `current-state.md` from the live
database, and STATE.md and MILESTONES.md carry the milestone this roadmap's
"Now" section produces.

## Later

- **Tag the three milestones that never shipped one.** `v0.2.0`, `v0.5.0`, and
  `v0.10.0` have CHANGELOG sections and no tag. Placing them means finding the
  commit each milestone ended on; `.planning/MILESTONES.md` records a git range
  for some, and stops at v9.

- **CI webhooks for test results.** The GitHub webhook handler exists for
  events; JUnit results still arrive through `import_results`. Receiving them
  directly closes the loop.
- **Flow scenarios against real integrations.** The Scenario DSL runs flows;
  vendor scenarios are still demo data.

## Not doing

Decided against, with the reasoning, so these stop coming back:

- **Automated rollback or fix suggestions.** The gate informs; humans decide.
- **Function-level impact granularity.** Module level is the unit. Finer
  granularity multiplies the graph without changing the decision it supports.
- **Judging whether a spec honors an obligation.** A rule engine asserts
  coverage. Reviewers judge. See `docs/corpus-review.md`.
- **Collecting production telemetry.** SpecTrace reads git, specs, and test
  results. Observability platforms push SLO status in through
  `update_slo_status` and `POST /api/slo/status/`; SpecTrace consumes what
  Datadog, groundcover, and New Relic emit and instruments nothing itself. See
  the Scope section of [README.md](README.md).
