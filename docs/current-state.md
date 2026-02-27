# Current State

> SpecTrace: Requirements traceability for Python projects
> Last updated: 2026-02-27

## What Exists

SpecTrace is a Django 5.2 application that connects markdown specs to pytest
tests and displays verification status in a dashboard. Public repo:
`tslateman/spec-trace`.

**Shipped milestones:**

- v1: Core foundation (spec parsing, test linking, status computation)
- v2: Traceability matrix data layer
- v3: Integration health checks (Linear API diagnostics)
- v4: SDK (5-line validation buttons for engineers)
- v5: FRET structured fields (scope, condition, component, timing, response)
- v6: Impact analysis (git diff -> affected tests)
- v7: UI polish (dark mode, OpenAPI docs, filtering)
- v8: Agent task pipeline (blackboard architecture for agent coordination)
- v9: Conflict detection, OpenAPI completeness, onboarding guide

**Infrastructure (added Feb 2026):**

- CI pipeline: test (gate) + lint (gate) via GitHub Actions
- Ruff linter + formatter: 0 errors, line-length 100
- `spectrace` CLI wrapping Django management commands
- 536 passing tests across spectrace, tests/, spectrace-flows/

**Current capabilities:**

- Parse markdown specs with YAML frontmatter into hierarchical requirements
- Link tests via `@pytest.mark.requirement("REQ-001")`
- Compute verification status (passing/failing/untested)
- Import JUnit XML results
- Detect impact of spec changes on tests
- REST API (14 endpoints) + OpenAPI 3.1 documentation at `/api/docs/`
- Security schemes (API key + bearer auth) and query parameter docs in spec
- SDK for in-app validation buttons
- Linear integration health monitoring
- Agent task coordination with state machine and lease management
- Invariant checking for data consistency (11 checks, INV-A through INV-K)
- Conflict detection with mutual exclusion and structured field analysis
- Verification flows (YAML-defined, pluggable executors)

## Directory Structure

```
spectrace/
├── requirements/              # Core Django app
│   ├── models.py                  # 22 models (1,430 lines)
│   ├── api.py                     # 14 REST API endpoints
│   ├── management/commands/       # 30 CLI commands
│   │   ├── parse_specs.py             # Import markdown specs
│   │   ├── extract_links.py           # Find test->requirement links
│   │   ├── impact_analysis.py         # Git diff -> affected tests
│   │   ├── detect_conflicts.py        # Mutual exclusion detection
│   │   ├── detect_drift.py            # Stale link detection
│   │   ├── agent_*.py                 # Agent task pipeline (7 commands)
│   │   ├── check_invariants.py        # Validate data consistency
│   │   └── consolidate.py             # Update docs + run invariants
│   ├── services/
│   │   ├── agent_tasks.py             # Task state machine
│   │   ├── conflict_detector.py       # Integration conflict detection
│   │   ├── impact_analyzer.py         # Spec change detection
│   │   └── linear_reporter.py         # Linear issue reporting
│   ├── flows/                     # Verification flow engine (Django layer)
│   ├── openapi/                   # OpenAPI 3.1 spec generation (msgspec)
│   ├── invariants.py              # 11 invariant checks
│   ├── health.py                  # Integration health checks
│   └── tests/                     # 500+ tests
├── spectrace_client/          # SDK Django app
│   ├── client.py                  # SpectTraceClient context manager
│   ├── decorators.py              # @with_feature_flags
│   └── examples/                  # PMS, mobile key integrations
├── cli.py                     # Click CLI (thin wrapper)
└── conftest.py                # pytest fixtures

spectrace-flows/               # Standalone verification flow engine
├── spectrace_flows/
│   ├── engine.py                  # SequentialFlowEngine
│   ├── parser.py                  # Flow YAML parsing
│   ├── executors/                 # api_call, assertion, wait
│   └── storage.py                 # Abstract storage interface
└── tests/

specs/                         # Example spec files
flows/                         # YAML flow definitions
examples/document-pipeline/    # Full working example with SLOs
docs/                          # User-facing documentation
scripts/                       # Demo and setup scripts
```

## Agent Task Pipeline

Blackboard architecture for agent coordination. See
**[docs/agent-tasks.md](agent-tasks.md)** for complete documentation.

**State machine:**

```
DRAFT -> UNCLAIMED -> CLAIMED -> IN_PROGRESS -> READY_FOR_REVIEW -> APPROVED -> MERGED
                 ^                                     |
                 +------ CHANGES_REQUESTED <-----------+
```

**CLI commands:**

```bash
spectrace agent-register <name> --role planner|coder|reviewer
spectrace agent-tasks [--status unclaimed]
spectrace agent-claim <task_id> --agent <agent_id> [--lease-minutes 30]
spectrace agent-start <task_id> --agent <agent_id>
spectrace agent-submit <task_id> --agent <agent_id> --commit-sha <sha>
spectrace agent-review <task_id> --reviewer <id> --decision approved|changes_requested
spectrace agent-merge <task_id>
spectrace expire-leases [--dry-run]
```

## Quick Reference

```bash
# Setup
make install-dev && make migrate && make setup

# Run
make run                                      # Start dev server
make test                                     # Run tests (excludes demo markers)
make check                                    # lint + format + test (matches CI)

# Import specs and compute status
spectrace parse-specs specs/
spectrace extract-links --output links.json
pytest --junitxml=test_results.xml
spectrace import-results test_results.xml --links links.json

# Impact analysis
spectrace impact-analysis HEAD~5 HEAD

# Agent task workflow
spectrace agent-register coder-1 --role coder
spectrace agent-tasks --status unclaimed
spectrace agent-claim task-001 --agent coder-1
spectrace check-invariants                    # Validate consistency
spectrace consolidate                         # Update docs + run invariants

# View dashboard
open http://localhost:8000/admin/
```

## Next Steps

1. **v10: Spec as Interface** -- Three phases making specs the interface agents
   work from. See [milestone-v10.md](milestone-v10.md).
   - Phase 1: `agent_context` command (spec context for agents)
   - Phase 2: `spec_coverage` metrics (specification, structure, verification rates)
   - Phase 3: `detect_integration_risks` (cross-task conflict detection)
2. **CI webhooks** -- Receive test results directly from CI pipeline (deferred)
3. **Historical trends** -- Coverage trends chart (deferred)
