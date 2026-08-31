# Roadmap

What SpecTrace does next, in priority order. This file is the authority for
open work. `.planning/STATE.md` tracks the current position,
`.planning/MILESTONES.md` archives shipped milestones, and
[CHANGELOG.md](CHANGELOG.md) records what landed. When those disagree with this
file about what comes next, this file wins.

Last reviewed: 2026-08-31.

## Now

### 1. Express cross-project dependencies in the graph

`spectrace impact --code` walks code to requirements inside one project. It
cannot answer the question the impact graph exists to answer: what does a
change here break over there.

The obstacle is the model, not the data. With maps loaded for two projects the
graph shares zero nodes between them, so `cross_project_edges` is always 0.
Contract edges run `{project}:{surface}` to `{surface}` and never reach a
module node, and no edge type says "project A depends on project B's surface".
Praxis really does depend on SpecTrace -- `src/praxis/spectrace.py` reads its
SQLite tables -- and the graph cannot represent it.

Seeding more projects will not fix this. The edge model needs the dependency
relation first.

**Done when:** a change to a SpecTrace surface reports Praxis as an affected
dependent, and `cross_project_edges` is non-zero for a real diff.

### 2. Address one repo per ref pair

`code_analyze` runs `git diff base head` in every project root with the same
refs. A ref that exists in one repo and not another yields nothing for the
second. The `<base>..<head>` signature assumes a monorepo this ecosystem is
not.

**Done when:** a multi-project analysis takes a ref per project, and a ref
missing from one project fails loudly instead of reporting that project clean.

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

- **Route the GitHub webhook, then retire its legacy path.** Two things hold
  here. `webhook_urlpatterns` never reaches `ROOT_URLCONF` --
  `spectrace/spectrace/urls.py` adds only the admin and API patterns, so the
  handler has never served a request in the bundled project. And
  `/api/webhooks/github/` stays a live alias rather than a redirect, because
  GitHub records a redirected delivery as a failure and drops the payload.
  Route the handler first; flip the alias to `redirect_to_v1` once the GitHub
  App points at `/api/v1/integrations/webhooks/github/`.

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
  `update_slo_status` and `POST /api/v1/integrations/slo/status/`; SpecTrace consumes what
  Datadog, groundcover, and New Relic emit and instruments nothing itself. See
  the Scope section of [README.md](README.md).
