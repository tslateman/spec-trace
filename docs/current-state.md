# Current State

> SpecTrace: Requirements traceability for Python projects
> Last updated: 2026-02-01

## What Exists

SpecTrace is a working Django application that connects markdown specs to pytest tests and displays verification status in a dashboard.

**Shipped milestones:**
- v1: Core foundation (spec parsing, test linking, status computation)
- v2: Traceability matrix data layer
- v3: Integration health checks (Linear API diagnostics)
- v4: SDK (5-line validation buttons for engineers)
- v6: Impact analysis (git diff → affected tests)
- v7: UI polish (dark mode, OpenAPI docs, filtering)
- v8: Agent task pipeline (blackboard architecture for agent coordination)

**Current capabilities:**
- Parse markdown specs with YAML frontmatter into hierarchical requirements
- Link tests via `@pytest.mark.requirement("REQ-001")`
- Compute verification status (passing/failing/untested)
- Import JUnit XML results
- Detect impact of spec changes on tests
- REST API + OpenAPI 3.1 documentation at `/api/docs/`
- SDK for in-app validation buttons
- Linear integration health monitoring
- Agent task coordination with state machine and lease management
- Invariant checking for data consistency

## Directory Structure

```
spectrace/
├── requirements/           # Core Django app
│   ├── management/commands/    # CLI commands
│   │   ├── parse_specs.py          # Import markdown specs
│   │   ├── extract_links.py        # Find test→requirement links
│   │   ├── impact_analysis.py      # Git diff → affected tests
│   │   ├── agent_*.py              # Agent task pipeline (7 commands)
│   │   └── check_invariants.py     # Validate data consistency
│   ├── services/
│   │   ├── agent_tasks.py          # Task state machine (claim→start→submit→review→merge)
│   │   └── impact_analyzer.py      # Spec change detection
│   ├── flows/                  # Sync flow engine
│   ├── openapi/                # OpenAPI spec generation from msgspec
│   ├── invariants.py           # 11 invariant checks (INV-A through INV-K)
│   ├── health.py               # Integration health checks
│   └── tests/                  # 265+ passing tests
├── spectrace_client/       # SDK Django app
│   ├── client.py               # SpectTraceClient context manager
│   ├── decorators.py           # @with_feature_flags
│   └── examples/               # PMS, mobile key integrations
├── docs/                   # User-facing documentation
│   └── principles.md           # Requirements specification guide
└── specs/                  # Example spec files

.planning/
├── milestones/             # Roadmaps and requirements per version
├── phases/                 # Execution history (CONTEXT, PLAN, VERIFICATION)
└── research/               # Domain research and architecture notes
```

## Agent Task Pipeline

The agent coordination system is implemented with a blackboard architecture. See **[docs/agent-tasks.md](agent-tasks.md)** for complete documentation.

**State machine:**
```
DRAFT → UNCLAIMED → CLAIMED → IN_PROGRESS → READY_FOR_REVIEW → APPROVED → MERGED
                ↑                                    ↓
                └────── CHANGES_REQUESTED ←──────────┘
```

**CLI commands:**
```bash
python manage.py agent_register <name> --role planner|coder|reviewer
python manage.py agent_tasks [--status unclaimed]
python manage.py agent_claim <task_id> --agent <agent_id> [--lease-minutes 30]
python manage.py agent_start <task_id> --agent <agent_id>
python manage.py agent_submit <task_id> --agent <agent_id> --commit-sha <sha>
python manage.py agent_review <task_id> --reviewer <id> --decision approved|changes_requested
python manage.py agent_merge <task_id>
python manage.py expire_leases [--dry-run]
```

**Invariants (11 checks):**
- INV-A through INV-F: verification status, SLO breaches, flow completion
- INV-G through INV-K: agent task integrity (claims, leases, history, reviews, self-review)
- Run via `python manage.py check_invariants [--check INV-K] [--format json]`

## What's In Progress

**Agent workflow integration** — Another session is working on integrating the task pipeline with Claude Code. The philosophy document outlines agent-first documentation principles. Remaining work:
- How agents consume CONTEXT.md files
- Phase execution lifecycle hooks
- Automatic invariant checks on merge

## Open Questions (from philosophy.md)

These questions are answered by how SpecTrace operates in practice:

| Question | Current Answer |
|----------|----------------|
| Workstream granularity | Per-subsystem, 1-2 days per milestone |
| Design iteration flow | CONTEXT → RESEARCH → PLAN → VERIFY → amend PLAN |
| CONTEXT.md size | ~1-2 KB; details in RESEARCH.md |
| CONTEXT versioning | Git history + timestamps in VERIFICATION |
| SPEC vs CONTEXT | Separate: SPEC = product reqs, CONTEXT = phase metadata |
| Validation evolution | Fixed must_haves; evidence accumulates |
| Tooling | Django CLI + git + Makefile (agent workflow in progress) |

## Quick Reference

```bash
# Run the app
make install && make migrate && make run

# Run tests
make test

# Import specs and compute status
python spectrace/manage.py parse_specs specs/
python spectrace/manage.py extract_links --output links.json
pytest --junitxml=test_results.xml
python spectrace/manage.py import_results test_results.xml --links links.json

# Impact analysis
python spectrace/manage.py impact_analysis HEAD~5 HEAD

# Agent task workflow (see docs/agent-tasks.md)
python spectrace/manage.py agent_register coder-1 --role coder
python spectrace/manage.py agent_tasks --status unclaimed
python spectrace/manage.py agent_claim task-001 --agent coder-1
python spectrace/manage.py agent_start task-001 --agent coder-1
python spectrace/manage.py agent_submit task-001 --agent coder-1 --commit-sha abc123
python spectrace/manage.py check_invariants         # Validate consistency
python spectrace/manage.py consolidate              # Update docs + run invariants

# View dashboard
open http://localhost:8000/admin/
```

## Next Steps

1. **Agent workflow** — Define execution lifecycle for Claude Code agents (in progress)
2. **CI webhooks** — Receive test results from CI pipeline (deferred from v7)
3. **Historical trends** — Coverage trends chart (deferred from v7)
