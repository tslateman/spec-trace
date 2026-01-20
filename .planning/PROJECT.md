# SpecTrace

## What This Is

A requirements traceability system that connects product specs to verified code. Specs live in the codebase as markdown files, pytest tests are annotated with requirement IDs, and a Django dashboard shows PMs, engineers, and QA which requirements are actually verified by passing tests.

## Core Value

PMs can see, at any moment, which requirements are verified by passing tests — eliminating the gap between "what we think we built" and "what we actually built."

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Specs stored as hierarchical markdown in codebase (specs/feature/requirement.md)
- [ ] pytest decorator/marker to annotate tests with requirement IDs
- [ ] Parser extracts requirements from spec files
- [ ] Parser extracts requirement annotations from test files
- [ ] Test runner captures pass/fail status per requirement
- [ ] Django web dashboard displays requirement status
- [ ] Dashboard shows coverage: which requirements have tests, which don't
- [ ] Dashboard shows verification: which requirements have passing tests
- [ ] PMs can browse requirements by feature area
- [ ] Engineers can see which requirements need test coverage

### Out of Scope

- Notion/Linear sync — specs live in codebase, not external tools
- Multi-repo aggregation — single repo for v1
- Real-time test watching — batch/CI updates for v1
- Test generation — system tracks, doesn't write tests
- Formal verification — "verified" means passing tests, not mathematical proof

## Context

**The problem today:**
- Specs are scattered across Slack, Notion, Linear, meetings, and tribal knowledge
- Engineers piece together requirements from fragments, often guessing
- Tests exist but may verify incorrect behavior because the "correct" behavior was never clearly defined
- No way to answer "is requirement X implemented and working?"

**Existing tooling:**
- Notion for some documentation (inconsistent)
- Linear for tickets (ephemeral, not spec)
- GitHub for code/PRs
- pytest for testing

**Key insight:**
Specs must live in the codebase to be the source of truth. External docs drift. Code-adjacent specs are versioned, reviewable, and can't diverge from reality.

## Constraints

- **Self-hosted**: Cannot use external SaaS; must run on internal infrastructure
- **Tech stack**: Django (Python) for web app, pytest for test integration
- **Single repo**: v1 targets one repository; multi-repo is future scope
- **Collaborative specs**: PMs and engineers refine specs together; neither owns alone

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Specs in codebase, not Notion | Version control, no drift, reviewable changes | — Pending |
| Markdown format | Human-readable, easy for PMs to write/review | — Pending |
| pytest annotations | Native to existing test workflow | — Pending |
| Django for dashboard | Stays in Python ecosystem, team familiarity | — Pending |

---
*Last updated: 2026-01-19 after initialization*
