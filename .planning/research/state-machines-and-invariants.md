# State Machines and Invariants

This document captures the implicit state machines and invariants in SpecTrace, inspired by TLA+ formal methods thinking.

## Background: TLA+ Wisdom

Leslie Lamport's key insight: **"For proving correctness of concurrent algorithms there's one basic method that works — proving an invariant."**

Amazon's practical approach (from their [formal methods paper](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf)): Write prose first, then incrementally formalize only the parts that matter. They call it "Debugging Designs" — not formal verification.

**We apply the TLA+ mindset without the tooling.** The state machines here are simple enough that prose documentation + runtime assertions provide most of the benefit without the ~2 week learning curve.

---

## State Machines

### 1. Requirement Verification Status

```
States: { 'passing', 'failing', 'untested' }

Transitions:
  untested → passing   (first test passes)
  untested → failing   (first test fails)
  passing  → failing   (any linked test fails)
  failing  → passing   (all linked tests now pass)
  passing  → untested  (all tests unlinked)
  failing  → untested  (all tests unlinked)
```

**Computation Logic** (`requirements/status.py`):
- No linked tests → `'untested'`
- Any test failed/errored → `'failing'`
- All tests passed → `'passing'`
- All tests skipped → `'untested'`

**Trigger**: `update_all_verification_statuses(test_run)` after test import.

### 2. SLO Status

```
States: { 'met', 'at_risk', 'breached', 'not_linked' }

Transitions:
  not_linked → met        (SLO linked, target met)
  not_linked → at_risk    (SLO linked, approaching breach)
  not_linked → breached   (SLO linked, already breached)
  met        → at_risk    (error budget depleting)
  at_risk    → breached   (error budget exhausted)
  breached   → at_risk    (partial recovery)
  at_risk    → met        (full recovery)
  *          → not_linked (all SLOs unlinked)
```

**Computation**: Worst status across all linked SLOs wins.

**Trigger**: `update_all_slo_statuses()` after SLO data refresh.

### 3. Test-Requirement Link Status

```
States: { 'passed', 'failed', 'error', 'skipped', 'unknown' }

Side effect on transition:
  passed → failed|error  ⟹  needs_review = True
```

**Trigger**: `update_test_requirement_links(test_run)` during import.

### 4. In-App Validation Status

```
States: { 'success', 'failure', 'unknown', 'not_run' }

Regression detection:
  results[-2].status == 'success' AND results[-1].status == 'failure'
  ⟹ is_regression = True, regressed_at = now()
```

### 5. Verification Flow Run

```
States: { 'running', 'passed', 'failed' }

Lifecycle:
  Initial: 'running' (completed_at = NULL)
  Final:   'passed' | 'failed' (completed_at = timestamp)
```

---

## Invariants

These conditions should **always** hold after any state transition.

### INV-A: Verification Status Consistency

```
∀ req:
  req.verification_status == compute_verification_status(req, latest_run)
```

After any test import, the stored status must match the computed status.

### INV-B: SLO Override

```
∀ req:
  req.slo_status == 'breached' ⟹ req.verification_status == 'failing'
```

A breached SLO forces the requirement to failing status, regardless of test results.

### INV-C: Cascade Delete Integrity

```
When parent deleted, no orphan children remain:
  - TestRun deleted      → all TestResult deleted
  - InAppValidationRun   → all InAppValidationResult deleted
  - VerificationFlow     → all VerificationFlowRun deleted
  - Requirement deleted  → all TestRequirementLink deleted
                        → all InAppValidation deleted
                        → all ConflictLog deleted
```

### INV-D: Link Uniqueness

```
∀ (test_nodeid, requirement):
  |TestRequirementLink| ≤ 1
```

At most one link record per (test, requirement) pair. Enforced by `unique_together`.

### INV-E: Status Change Review Flag

```
∀ link:
  link.last_status changed from 'passed' to ('failed' | 'error')
  ⟹ link.needs_review == True
```

Regressions automatically flag for review.

### INV-F: Flow Run Completion

```
∀ flow_run:
  flow_run.completed_at != NULL ⟺ flow_run.status ∈ {'passed', 'failed'}
```

A run is complete iff it has a completion timestamp.

### INV-G: Step Order Uniqueness

```
∀ flow_run:
  ∀ step_order ∈ [0..n]:
    |VerificationFlowStep(flow_run, step_order)| == 1
```

Each flow run has exactly one step at each position. Enforced by `unique_together`.

---

## Potential Violations

Known scenarios where invariants could be violated:

1. **Partial Import**: `update_all_verification_statuses()` processes requirements sequentially. If interrupted, some requirements have stale status.

2. **External DB Modification**: Direct SQL updates bypass the status computation triggers.

3. **Flaky Test Masking**: INV-E only flags `passed → failed`. A test that goes `failed → passed → failed` doesn't re-flag on the second failure.

4. **Stale Latest Result**: `InAppValidation.latest_result` is a cached property. Within a single request, it won't reflect new results added after first access.

---

## Practical Application

### Option 1: Runtime Assertions (Low Effort)

Add assertions at state transition points:

```python
def update_all_verification_statuses(test_run):
    for req in requirements:
        old_status = req.verification_status
        new_status = compute_verification_status(req, test_run)
        req.verification_status = new_status
        req.save()

        # INV-B: SLO override
        if req.slo_status == 'breached':
            assert req.verification_status == 'failing', \
                f"INV-B violated: {req.external_id} breached but {req.verification_status}"
```

### Option 2: Invariant Check Command (Medium Effort)

```bash
python manage.py check_invariants --fix
```

Scans all records, reports violations, optionally repairs.

### Option 3: Property-Based Testing (Medium Effort)

Use Hypothesis to fuzz state transitions:

```python
@given(test_results=st.lists(st.sampled_from(['passed', 'failed', 'skipped'])))
def test_verification_status_invariant(test_results):
    # Create requirement with these test results
    # Assert INV-A holds
```

---

## References

- [TLA+ in Practice and Theory - Part 1](https://pron.github.io/posts/tlaplus_part1) — Core concepts
- [Use of Formal Methods at Amazon Web Services](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf) — Practical adoption
- [The pragmatic magic of semi-formal methods](https://antithesis.com/blog/2025/semi_formal_proofs/) — Middle ground between informal and formal
