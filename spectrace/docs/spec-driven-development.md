# Spec-Driven Development

> Specs guide implementation. Agents execute. Tests verify.

---

## The Premise

When LLM agents become primary implementers, documentation serves a different purpose. Traditional approaches—design docs, RFCs, tickets—optimize for human coordination: building consensus, preserving institutional knowledge, persuading stakeholders.

Spec-driven development inverts this. Specifications become **executable context**:

- Agents have no memory between sessions—everything must be explicit
- Agents can't infer from incomplete information—precision matters
- Agents can't "read the room"—ambiguity causes wrong choices
- Code is cheap; design is the bottleneck

Teams still need alignment. Stakeholders still need persuading. But the *implementation layer* shifts from human programmers to agents guided by precise specifications.

The question becomes: **What documentation helps agents implement correctly?**

---

## The Core Insight

> The spec is the source of truth. Everything else derives from it.

Specs aren't just documentation—they're executable context injected into an agent's context window. This means:

- **Length matters** — Context windows are finite
- **Currency matters** — Agents can't infer "this was superseded"
- **Precision matters** — Ambiguity = agent makes wrong choices
- **Self-containment matters** — Agents can't ask clarifying questions mid-task

---

## Document Architecture

### Always Loaded

**CLAUDE.md** (project root)
- Testing patterns, naming conventions
- Architecture principles
- What NOT to do
- Concise—every word costs context tokens

**docs/about-spectrace.md**
- What SpecTrace is
- Core capabilities
- How pieces connect
- CLI commands reference

### Loaded Per-Task

**.planning/** (GSD workflow)
- PROJECT.md — North star, current milestone
- roadmap.md — Phases and their status
- phases/{n}/PLAN.md — Detailed task breakdown
- phases/{n}/RESEARCH.md — Context gathered before planning

**Relevant source files**
- Agent reads what it needs to modify
- Guided by PLAN.md file lists

---

## The GSD Workflow

SpecTrace uses the GSD (Get Stuff Done) plugin for structured agent-driven development:

```
/gsd:new-project     → Deep context gathering, PROJECT.md
        ↓
/gsd:new-milestone   → Define milestone scope, requirements
        ↓
/gsd:plan-phase      → Research → Plan → Verify loop
        ↓
/gsd:execute-phase   → Agents implement toward validation
        ↓
/gsd:verify-work     → Conversational UAT
        ↓
/gsd:audit-milestone → Check against original intent
```

### Why This Works

1. **Research before planning** — Agent explores codebase, gathers context
2. **Plans are verified** — Checker agent validates plan achieves goal
3. **Execution is atomic** — Each task commits independently
4. **Verification is explicit** — Not "did tasks complete" but "did we achieve the goal"

---

## Document Types

### PROJECT.md
North star. What SpecTrace is becoming.

```markdown
# Project: SpecTrace

## Vision
Requirements traceability for Python teams.

## Current Milestone
v0.9: Invariant Checks + Drift Prevention

## Success Criteria
- `check_invariants` catches status inconsistencies
- `detect_drift` finds stale links and orphan requirements
- Both commands have CI-friendly JSON output
```

### roadmap.md
Phases within current milestone. Status tracking.

```markdown
# Roadmap: v0.9

## Phase 1: Fix INV-B Bug ✅
## Phase 2: Create Invariants Module ✅
## Phase 3: check_invariants Command ✅
## Phase 4: Extend Drift Detection ✅
## Phase 5: detect_drift Command ✅
```

### PLAN.md (per phase)
Detailed task breakdown. What agent implements.

```markdown
# Phase 4: Extend Drift Detection

## Goal
Add drift detection for stale links, orphan requirements, spec file changes.

## Tasks
1. Add DriftResult dataclass
2. Implement detect_stale_links()
3. Implement detect_orphan_requirements()
4. Implement detect_spec_drift()
5. Add tests for all functions

## Files to Modify
- requirements/validator.py
- requirements/tests/test_drift_detection.py

## Validation
- All new tests pass
- Existing tests still pass
- Functions handle edge cases (no test runs, empty directories)
```

### RESEARCH.md (per phase)
Context gathered before planning. Disposable after plan created.

```markdown
# Research: Phase 4

## Existing Code
- validator.py has ValidationResult, validate_links()
- Uses ValidationIssue dataclass with type, id, message, details

## Patterns to Follow
- Return dataclass with errors/warnings lists
- to_dict() method for JSON serialization
- Consolidate duplicate errors

## Open Questions
- Should stale links be errors or warnings? → Errors (they indicate real problems)
```

---

## The Human's Role

When agents implement, humans shift focus:

1. **Architecture** — System shape, module boundaries
2. **Constraint definition** — Invariants, what must be true
3. **Validation** — Did agent produce correct work?
4. **Context curation** — What does agent need to succeed?

On teams, these responsibilities distribute naturally. Architects define constraints. PMs curate requirements. Engineers validate output and refine context. The agent becomes a shared tool that any team member can direct—given the right documentation.

### Context Engineering

An agent's context window is finite. You're curating what goes in:

- Too little context → Agent makes wrong assumptions
- Too much context → Agent gets confused, exceeds limits
- Wrong context → Agent solves wrong problem

The skill is knowing what context an agent needs for THIS task.

---

## SpecTrace-Specific Patterns

### Domain Model Awareness

Agents need to understand:

```
Requirement (hierarchical, django-treebeard)
    ├── TestRequirementLink (many-to-many with tests)
    ├── TestResult (from pytest runs)
    ├── InAppValidation (runtime checks)
    └── SLO (service level objectives)

verification_status = f(test_results, inapp_validations, slo_status, verification_method)
```

### Invariants

Always true. Agent must never violate:

- **INV-A**: Stored status matches computed status
- **INV-B**: Breached SLO → failing status (override)
- **INV-D**: Unique links per (test, requirement) pair
- **INV-E**: Failed test → needs_review flag set
- **INV-F**: Flow completion state consistent with timestamp

### Testing Patterns

From CLAUDE.md:

```python
# Naming: test_{method}__{expected_behavior}
def test_compute_status__returns_failing_when_any_test_fails():
    ...

# Always use autospec
@patch("requirements.services.api.requests.post", autospec=True)
def test_submit__calls_api(mock_post):
    ...

# pytest functional style, not unittest.TestCase
```

### Management Commands

Django management command pattern:

```python
class Command(BaseCommand):
    help = "Description"

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['text', 'json'])
        parser.add_argument('--fix', action='store_true')

    def handle(self, *args, **options):
        # Implementation
        if options['format'] == 'json':
            self.stdout.write(json.dumps(result))
        else:
            # Human-readable output
```

---

## Anti-Patterns

### What Breaks Spec-Driven Development

**Vague requirements**
- Bad: "Improve the status computation"
- Good: "compute_unified_verification_status should check SLO status and return 'failing' if breached"

**Missing context**
- Bad: "Add drift detection" (agent doesn't know what drift means here)
- Good: "Add detection for: stale links (test deleted but link remains), orphan requirements (no tests, no children)"

**Implicit knowledge**
- Bad: Assuming agent knows django-treebeard API
- Good: "Use Requirement.add_root() and req.add_child() for tree operations"

**Overloaded tasks**
- Bad: "Implement the entire invariant checking system"
- Good: Phase into discrete tasks with clear validation criteria

---

## The Feedback Loop

```
┌─────────────────────────────────────────────────┐
│                    TEAM                          │
│  • Reviews agent output                          │
│  • Updates PLAN.md with learnings                │
│  • Promotes patterns to CLAUDE.md                │
│  • Advances to next phase                        │
│  • Refines specs based on what agents get wrong  │
└─────────────────────────────────────────────────┘
          ↑                            │
          │                            ↓
   ┌──────┴──────┐            ┌────────┴────────┐
   │   OUTPUT    │            │     CONTEXT     │
   │  (code +    │            │  (docs loaded   │
   │   tests)    │            │   into agent)   │
   └──────┬──────┘            └────────┬────────┘
          ↑                            │
          │                            ↓
          └────────────────────────────┘
                      AGENT
                (spawns, reads docs,
                 implements toward
                 validation criteria,
                 terminates)
```

When agents consistently misimplement something, that's signal. Either the spec is ambiguous or the context is incomplete. The team improves documentation, and future agent runs succeed.

---

## Practical Workflow

### Starting a New Feature

```bash
# 1. Create milestone if needed
/gsd:new-milestone

# 2. Plan the phase (research → plan → verify)
/gsd:plan-phase 1

# 3. Execute (agent implements)
/gsd:execute-phase 1

# 4. Verify (conversational UAT)
/gsd:verify-work

# 5. Commit
/commit
```

### Mid-Feature Adjustments

When agent output reveals a design flaw:

1. Stop execution
2. Update PLAN.md with new understanding
3. Re-run /gsd:plan-phase if needed
4. Continue execution

### Knowledge Consolidation

After completing a milestone:

1. Update about-spectrace.md if capabilities changed
2. Update CLAUDE.md if new patterns emerged
3. Archive .planning/ or reset for next milestone

---

## SpecTrace Eating Its Own Dogfood

SpecTrace tracks whether requirements are verified—regardless of who implements them. This matters in spec-driven development: agents don't remember what they built last session, but the traceability matrix shows verification status objectively. The spec is the source of truth.

We use SpecTrace on itself:

```markdown
# specs/invariants/inv-b-slo-override.md
---
id: INV-B
title: Breached SLO Forces Failing Status
priority: high
status: active
verification_method: test
component: status_computation
---

When a requirement has slo_status = 'breached',
verification_status must be 'failing' regardless
of test results or in-app validations.
```

```python
@pytest.mark.requirement("INV-B")
def test_compute_status__returns_failing_when_slo_breached():
    req = create_requirement(slo_status=SLOStatus.BREACHED)
    # Even with passing tests...
    create_passing_test_result(req)

    status = compute_unified_verification_status(req)

    assert status == 'failing'
```

The traceability matrix then shows INV-B linked to its test.

---

## Summary

| Traditional | Spec-Driven |
|-------------|-------------|
| Design docs convince stakeholders | Specs guide agents; design docs align teams |
| Tickets track work | Specs define goals with validation criteria |
| Code review catches bugs | Invariant tests catch violations automatically |
| Tribal knowledge fills gaps | Explicit patterns in CLAUDE.md and specs |
| History accumulates in ADRs | Current truth in living specs |

Humans architect and validate. Specs define intent. Agents implement. Tests verify. SpecTrace tracks the links between specs and verification—the spec is the source of truth.
