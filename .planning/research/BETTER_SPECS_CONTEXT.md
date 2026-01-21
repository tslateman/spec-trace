# Better Specs Context

**Source:** Canary Internal Research (Jan 2026)
**Relevance:** HIGH - spec-trace implements core Better Specs concepts

## Connection to Better Specs Initiative

SpecTrace directly addresses the "Knowledge-Execution Gap" identified in Canary's Better Specs initiative. The core problem:

> Specifications drift from implementation over time. Without explicit traceability, organizations cannot answer: "Is this requirement implemented and verified?"

### The Traceability Pipeline

Better Specs defines a three-stage traceability pipeline:

```
Spec → Test → SLO
  ↑       ↑      ↑
  │       │      └── Production behavior matches spec (future)
  │       └────────── Test verifies spec behavior (Phase 2-3)
  └────────────────── Spec defines expected behavior (Phase 1)
```

**SpecTrace scope:** Phases 1-3 implement `Spec → Test` traceability. The `Test → SLO` stage (production verification) is future scope, potentially via OpenSLO integration.

## Key Concepts from Better Specs

### 1. Truth Decay

> Requirements start accurate but degrade over time as code evolves without spec updates.

**Implication for SpecTrace:** The dashboard must surface "orphan" tests (tests not linked to requirements) and "stale" specs (specs without passing tests). Phase 3 dashboard should make decay visible.

### 2. Decision Amnesia

> Teams forget why decisions were made, leading to repeated debates and contradictory implementations.

**Implication for SpecTrace:** Spec markdown should support rationale capture (why, not just what). Consider `## Rationale` section in spec format.

### 3. The Knowledge-Execution Gap

> The distance between documented intent and actual behavior grows as organizations scale.

**Implication for SpecTrace:** This is the core problem. Closing the gap requires:
- Specs in codebase (not external docs)
- Tests explicitly linked to specs
- Dashboard showing verification status
- CI integration to keep status current

## Testing Infrastructure Patterns

Canary's Testing Infrastructure design introduced patterns relevant to SpecTrace:

### Environment/Scenario Pattern

```
Environment = Configuration snapshot (what exists)
Scenario = Environment + Actions + Expected state
```

**Potential application:** SpecTrace could adopt similar composable patterns:
- **RequirementSet:** Collection of related requirements (like Environment)
- **VerificationScenario:** RequirementSet + Test suite + Expected coverage

### Drift Detection

Testing Infrastructure includes "drift detection" - comparing expected state (spec) vs actual state (model/code).

**Direct parallel:** SpecTrace's core function is drift detection between:
- Expected: Spec says behavior X is required
- Actual: Tests verify behavior X passes/fails

### Composable Scenarios

Testing Infrastructure emphasizes building complex scenarios from simple primitives. SpecTrace should follow this:
- Atomic requirements (single verifiable behavior)
- Composed features (collection of requirements)
- Test suites verify at both levels

## Relevant Patterns for Implementation

### Pattern: Explicit vs Implicit Dependencies

From Hyrum's Law research: "All observable behaviors will be depended on."

**For SpecTrace:** Test-to-requirement links must be explicit (pytest markers), not inferred. Inference breaks when code changes.

### Pattern: Shift Left

> Find problems earlier in the workflow to reduce costs.

**For SpecTrace:**
- Spec validation during PR (are new tests linked to requirements?)
- Coverage gaps visible before merge
- Requirement completeness checked early

### Pattern: The Beyoncé Rule

> "If you liked it, you should have put a test on it."

**For SpecTrace:** Dashboard should prominently display requirements without linked tests. Make absence of verification visible and uncomfortable.

## Future Integration Opportunities

### OpenSLO Integration (Test → SLO)

Better Specs vision extends beyond test verification to production behavior. OpenSLO provides:
- Declarative SLO definitions (YAML)
- Metric-based verification
- Integration with observability platforms

**Future phase concept:**
```yaml
# slos/auth-latency.yaml
apiVersion: openslo/v1
kind: SLO
spec:
  service: auth-service
  indicator:
    ratioMetric:
      good:
        metricSource: prometheus
        query: http_request_duration_seconds{endpoint="/login"} < 0.5
  objectives:
    - target: 0.99
  links:
    requirements:
      - REQ-AUTH-001  # Link to SpecTrace requirement
```

This would complete the pipeline: Spec → Test → SLO → Production.

### factory_boy for Test Data

Testing Infrastructure uses structured test data generation. For SpecTrace integration tests, consider:
- factory_boy for creating Requirement/Test fixtures
- Composable factories matching Environment/Scenario pattern

## Summary: How This Informs SpecTrace

| Better Specs Concept | SpecTrace Implementation |
|---------------------|-------------------------|
| Knowledge-Execution Gap | Core problem solved |
| Truth Decay | Dashboard surfaces orphans/staleness |
| Decision Amnesia | Rationale in spec format |
| Spec → Test | Phase 2 pytest integration |
| Drift Detection | Coverage status computation |
| Explicit Dependencies | Pytest markers (not comments) |
| Shift Left | CI integration for early feedback |
| Beyoncé Rule | Prominent coverage gap display |

## References

- Notion: Better Specs main doc
- Notion: Kiosk Testing Infrastructure Technical Design V1
- Notion: Step Framework & Open Source Alternatives Analysis
- Research: Software Engineering at Google (Hyrum's Law, Beyoncé Rule)

---
*Context documented: 2026-01-20*
*Source: Canary Better Specs initiative research*
