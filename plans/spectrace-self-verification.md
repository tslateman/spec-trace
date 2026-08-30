Status: Implemented

# Plan: SpecTrace verifies SpecTrace

## Problem

`.github/workflows/ci.yml` runs three jobs: Test, Lint, and Changelog. It never
runs `validate_links`, the CI drift detector SpecTrace ships.

Running the gates by hand against the development database today:

```
corpus_drift --strict   → "0 of 0 reviews stale"
validate_links --strict → "0 links checked, 9 warnings"
```

The nine warnings name demo requirements — `REQ-BILL-001`, `REQ-IAM-001`,
`REQ-WRK-002` — from the B2B SaaS corpus in `specs/`. The only
`@pytest.mark.requirement` markers in the repository are nine sample ones in
`spectrace/tests/test_example.py`. Across 1031 test functions, 45 management
commands, and 14 `/api/v1/` endpoints, no requirement describes SpecTrace
itself.

Wiring the existing gates into CI today would produce a green check over demo
data.

## Goal

Give SpecTrace requirements of its own for the core traceability loop and the
API v1 surface, link them to real tests, and gate them in CI before v11 ships.

## Success criteria

- A new CI job fails on a broken requirement link and passes on a clean tree
- `validate_links` reports 0 errors against SpecTrace's own spec tree
- Every requirement in the new tree is either linked to a test or visibly
  unverified
- The core loop and the 14 `/api/v1/` endpoints each carry a requirement
- The gate is green on `main` before `v11` is tagged

## Scope

**In scope**

- 23 requirements in a treebeard hierarchy: 4 parents (core loop, tasks,
  specs, results) over 19 children — one per loop stage and one per
  `/api/v1/` endpoint
- A new spec tree at `meta/specs/`, separate from `specs/`
- `@pytest.mark.requirement` markers on the tests covering those requirements
- A fourth CI job, beside Test, Lint, and Changelog, running `migrate` →
  `parse_specs` (both trees) → `extract_links --path spectrace` →
  `validate_links --check-high-risk`
- Errors fail the build; coverage warnings print and pass
- `risk_level: high` on the core loop and its parent, `medium` on the API v1
  surface, with `validate_links --check-high-risk` enabled

**Out of scope**

- Marking all 1031 test functions
- `corpus_drift --strict`, which moves to ROADMAP item 7
- Seeding `spectrace-map.yaml` or the impact graph (item 3)
- Moving or fixing the demo specs, including their nine coverage warnings
- Coverage trend snapshots (item 6)

## Approach

Author top-down. Write what SpecTrace promises, then locate the tests that
verify each promise. Gaps surface as unverified requirements. Deriving
requirements from the 1031 existing tests would produce specs that restate
them, and passing would prove nothing.

`validate_links` takes a links file and queries `Requirement`, so the CI job
needs `migrate`, `parse_specs`, and `extract_links` ahead of it. Both spec trees
parse into one database; demo warnings appear in the report and pass.

SpecTrace's specs live under `meta/`, a container reserved for
SpecTrace-about-SpecTrace: `meta/specs/` now, `meta/corpus/` when item 7
authors standards for SpecTrace's own domain. The demo trees — `specs/`,
`corpus/`, `flows/` — stay where they are.

`extract_links --path` defaults to `tests`, which from `spectrace/` resolves to
the nine demo markers in `test_example.py` — the reason the pipeline has only
ever seen demo data. Pointing it at `spectrace` covers both
`requirements/tests/`, where every test for the 23 requirements lives, and the
demo markers, whose links then resolve and clear the nine standing warnings.
`spectrace-flows/tests/` stays out: one file, no markers, and flows are not in
this scope.

`risk_level` supplies the teeth. `validate_high_risk_requirements()` errors
when a critical or high requirement has no linked test or has a failing one,
and only warns when no SLO is linked — harmless here, since SpecTrace defines
no SLOs for itself. The five loop stages must therefore stay green; the
endpoints stay advisory until someone raises them.

The hierarchy is not incidental. SpecTrace stores requirements in a treebeard
tree and the dashboard renders it, so parent/child specs exercise the feature
rather than only the link table.

The gate runs as its own job rather than as steps inside Test, so a red check
reports that a requirement lost its test rather than that a test broke. The
cost is a duplicate dependency install.

`corpus_drift` leaves this plan because it cannot assert anything here. Corpus
entries scope through `applies_to.paths` — `DEC-IAM-002` matches
`specs/identity/**` and `specs/workspaces/**` — so no existing entry would ever
match a SpecTrace spec. Making that gate real requires a corpus for SpecTrace's
own domain, which is item 7's work.

## What implementation found

Writing the specs surfaced three defects the demo data had hidden.

**`parse_specs` attached children to the wrong parent.** `parser.py` called
`add_child()` on parent instances cached in a dict. treebeard derives a child's
path from the parent's stored path and numchild, which a cached instance loses
as soon as a sibling is added. Parsing `meta/specs/` on a fresh database put
`REQ-RSLT-001` under `REQ-CORE-000` and then crashed on
`UNIQUE constraint failed: requirements_requirement.path`. The demo specs never
triggered it because each demo parent has exactly one child. Fixed by reloading
the parent before `add_child`.

**`import_test_links` ignored everything `extract_links` writes.** The command
read `linear_issue_ids`, the key the pytest plugin emits. `extract_links` emits
`requirement_id`. Every run reported `Created 0 new links` and exited 0, so
`TestRequirementLink` stayed empty and the high-risk check saw no linked tests
anywhere. Fixed to accept both shapes, and to raise when links resolve to no
requirement rather than reporting zero as success.

**Two core stages had no tests.** Nothing referenced `extract_links` or
`RequirementCollector`, and `import_junit_xml` appeared only as a mock target
string. `test_core_loop.py` now covers both, plus the loop end to end.

The high-risk check reads `TestRequirementLink` rather than the links file, so
it is only accurate against a database built in the same run. CI builds one from
scratch; a developer running it against a working database can see stale links
pass.

## Decisions

Settled 2026-08-30. Rationale sits in Approach above.

| Question       | Decision                                                      |
| -------------- | ------------------------------------------------------------- |
| Spec tree home | `meta/specs/`, with `meta/corpus/` reserved for item 7        |
| CI shape       | A fourth job beside Test, Lint, and Changelog                 |
| Granularity    | 23 requirements: 4 parents over 19 children                   |
| Risk           | Core loop `high`, API v1 `medium`, `--check-high-risk` on     |
| Scan path      | `extract_links --path spectrace`; `spectrace-flows/` excluded |
