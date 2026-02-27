# v10: Spec as Interface

> The bottleneck shifted from generation to verification. SpecTrace becomes the
> layer between human intent and machine execution.

## Problem

AI agents generate code fast. Review can't keep up. The root cause isn't slow
review — it's that agents work from vague tickets instead of structured specs.
Every ambiguous input multiplies into ambiguous output. SpecTrace already
connects specs to tests. v10 makes specs the interface agents work from and
the standard verification runs against.

Three gaps, in order of leverage:

1. Agents don't receive specs as context when claiming tasks
2. Nobody measures how much of the system is specified vs. unspecified
3. No detection when multiple changes jointly violate a spec's invariants

## Phases

### Phase 1: Spec-as-Context

When an agent claims a task, assemble the relevant specs into its working
context. The agent receives: requirement description, acceptance criteria
(`done_when`), linked test outcomes, dependent requirements, and FRET
structured fields if populated.

**Concrete deliverable:** `agent_context <task_id>` management command that
outputs a structured context document for a given task. Includes:

- Task description and `done_when` criteria
- All linked requirements with current verification status
- Requirement dependency tree (treebeard ancestors + dependents)
- Linked test results (last run status, test node IDs)
- Scope boundaries (`scope_in`, `scope_out`)

**Format:** Markdown document suitable for prompt injection. Parseable by
agents, readable by humans.

**What this replaces:** Agents currently work from task description alone. The
spec context gives them invariants, not just instructions.

**Acceptance criteria:**

- [ ] `agent_context` command outputs markdown for any AgentTask
- [ ] Output includes requirement verification status
- [ ] Output includes `done_when` as checkable criteria
- [ ] Output includes dependency tree (what this requirement affects)
- [ ] Test: round-trip — create task, link requirements, verify context output
- [ ] Test: task with no linked requirements produces minimal valid output

### Phase 2: Spec Coverage Metrics

Make specification debt visible. Track what percentage of the system is
specified, structured, and verified.

**Concrete deliverable:** `spec_coverage` management command and dashboard
summary.

Three metrics:

| Metric             | Definition                                             | Source                          |
| ------------------ | ------------------------------------------------------ | ------------------------------- |
| Specification rate | Requirements with status != draft / total requirements | Requirement.status              |
| Structure rate     | Avg `structure_completeness` across requirements       | Requirement FRET fields         |
| Verification rate  | Requirements with passing tests / total requirements   | Requirement.verification_status |

**Dashboard integration:** Summary card on admin index showing three rates
as percentages with trend indicators (up/down/flat vs. last import).

**What this enables:** Teams can track spec debt the way they track code
coverage. "We have 40% spec coverage" is actionable. "We have spec debt"
is not.

**Acceptance criteria:**

- [ ] `spec_coverage` command outputs three rates
- [ ] `spec_coverage --format json` for CI integration
- [ ] Dashboard card shows three rates on admin index
- [ ] Trend comparison against previous snapshot (store in JSON or DB)
- [ ] Test: empty DB returns 0% across all metrics
- [ ] Test: known fixture returns expected percentages

### Phase 3: Integration Conflict Detection

Detect when multiple in-flight changes affect the same requirements. Surface
conflicts before they compound.

**Concrete deliverable:** `detect_integration_risks` management command.

**Input:** List of agent tasks in `in_progress` or `ready_for_review` status.

**Detection rules:**

1. **Overlapping requirements.** Two tasks linked to the same requirement.
   Risk: semantic merge conflict.
2. **Dependency chain.** Task A modifies a requirement that Task B depends on.
   Risk: cascading invalidation.
3. **Scope overlap.** Two tasks with intersecting `scope_in` paths.
   Risk: file-level merge conflict.

**Output:** Risk report listing each conflict with:

- Affected tasks (IDs, titles, assignees)
- Shared requirements or dependency path
- Risk level (high: same requirement, medium: dependency chain, low: scope overlap)
- Recommendation (review together, sequence, or accept)

**What this enables:** Integration review as a distinct step. Before merging
a batch of agent work, run `detect_integration_risks` to find the intersections
that need a human holding the whole picture.

**Acceptance criteria:**

- [ ] Command detects overlapping requirements across active tasks
- [ ] Command detects dependency chain conflicts
- [ ] Command detects scope overlap
- [ ] Output includes risk level and recommendation
- [ ] `--format json` for programmatic consumption
- [ ] Test: two tasks sharing a requirement → flagged
- [ ] Test: two tasks with no overlap → clean report
- [ ] Test: dependency chain A→B detected

## What This Is Not

- Not a CI webhook integration (deferred, still relevant)
- Not historical coverage trends (Phase 2 snapshots enable this later)
- Not agent execution automation (v10 assembles context; execution is the
  agent's responsibility)
- Not a replacement for human review (v10 focuses review, not eliminates it)

## Dependencies

- Agent task pipeline (v8) — task model, state machine, requirement links
- FRET structured fields (v5) — `structure_completeness` metric
- Impact analysis (v6) — scope overlap detection reuses `impact_analyzer`

## Success Criteria

v10 is complete when:

1. An agent claiming a task receives its full spec context in one command
2. A team can answer "what percentage of our system is specified?" with a number
3. A reviewer can see which in-flight tasks conflict before merging any of them
