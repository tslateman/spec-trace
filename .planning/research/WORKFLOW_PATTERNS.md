# Workflow Pattern Research

**Researched:** 2026-01-20
**Relevance:** MEDIUM - Future dashboard/CI state management

## Summary

Research into Python/Django FSM and workflow libraries for potential use in:
- CI run state management (pending → running → complete → processed)
- Requirement lifecycle states (draft → active → deprecated)
- Dashboard wizard flows (future multi-step features)

## Libraries Evaluated

### FSM Libraries

| Library | Type | Best For |
|---------|------|----------|
| transitions | Object-oriented FSM | Complex state machines with callbacks |
| python-statemachine | Class-based FSM | Type-safe state machines |
| django-fsm-2 | Model field FSM | Simple Django model state tracking |
| viewflow.fsm | Enum descriptor | Lightweight model states |

### Workflow Engines

| Library | Type | Best For |
|---------|------|----------|
| django-river | Runtime-configurable | Admin-defined workflows |
| viewflow | BPMN-style | Complex multi-step processes |

## Recommendation for SpecTrace

**For CI Run states:** Use simple Django field with choices. The state machine is trivial:
```
pending → running → complete → processed
                  ↓
               failed
```

No library needed - overkill for simple linear progression.

**For future wizard flows:** Consider viewflow.fsm if needed. Lightweight, no database overhead.

**Avoid:** django-river (runtime configuration complexity) and full BPMN engines (scope creep).

## Key Insight

From Step Framework analysis: "Linear progressions don't need FSM libraries."

SpecTrace verification status is not a state machine - it's computed from test results:
- No tests linked → `UNTESTED`
- All tests pass → `PASSING`
- Any test fails → `FAILING`

This is a pure function, not stateful. Keep it that way.

---
*Researched: 2026-01-20*
