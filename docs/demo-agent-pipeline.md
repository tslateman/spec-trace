# Demo Script: From Spec to Verified

**Duration:** ~4 minutes
**Audience:** Engineering leads, PMs interested in agent-assisted development
**Setup:** Terminal + browser with SpecTrace dashboard open

---

## Opening (30s)

> "SpecTrace answers one question: which requirements are verified by passing tests? Today I'll show how agents can safely implement specs while maintaining that guarantee."

Show dashboard with a few verified requirements and one unverified.

---

## Act 1: The Spec (45s)

Open a spec file:

```bash
cat specs/examples/room-upgrade.md
```

> "Here's a requirement written by a PM. Plain markdown with a unique ID. Right now the dashboard shows it red — no tests verify this behavior."

Show dashboard filtering to `REQ-UPGRADE-001` — unverified status.

---

## Act 2: Agent Claims Work (1min)

```bash
# Register an agent (one-time setup)
./manage.py agent_register upgrade-agent

# What work is available?
./manage.py agent_tasks
```

> "The agent sees available requirements. It claims one — this creates a lease so no other agent works on the same thing."

```bash
./manage.py agent_claim REQ-UPGRADE-001 --agent upgrade-agent

# Start work (creates a worktree branch)
./manage.py agent_start REQ-UPGRADE-001
```

> "Now the agent has an isolated branch. It can write code without affecting main."

---

## Act 3: Implementation (30s — fast forward)

> "I'll skip the implementation — the agent writes models, services, and tests. The key point: it references the requirement ID in test docstrings."

Show a test file briefly:

```python
def test_upgrade_request__creates_pending_upgrade():
    """Verifies REQ-UPGRADE-001: Guest can request room upgrade."""
    ...
```

```bash
./manage.py agent_submit REQ-UPGRADE-001
```

> "Agent submits. Now the guardrails kick in."

---

## Act 4: Invariant Checks (1min)

```bash
./manage.py check_invariants
```

> "This is the gate. Before any merge, we verify:"

Point to output as it runs:

- **All specs have valid IDs** — no orphaned requirements
- **All test links resolve** — no broken REQ references
- **Tests pass** — implementation actually works
- **No regressions** — existing verified requirements stay green

> "If any check fails, the merge is blocked. Agents can't break what's already working."

---

## Act 5: Review & Merge (30s)

```bash
# Human review (shows diff, affected requirements)
./manage.py agent_review REQ-UPGRADE-001

# Merge to main
./manage.py agent_merge REQ-UPGRADE-001
```

> "Review shows exactly which requirements this change affects. Merge brings it to main and auto-runs consolidate to clean up branches."

---

## Act 6: The Payoff (30s)

Refresh dashboard. Filter to `REQ-UPGRADE-001`.

> "Green. The PM wrote a spec this morning. An agent implemented it. And now — without asking anyone — they can see it's verified."

> "That's SpecTrace: specs as source of truth, agents as safe implementers, dashboard as the single pane of glass."

---

## Q&A Prompts

If time permits, anticipate questions:

- **"What if two agents claim the same thing?"** — Leases prevent conflicts. `expire_leases` handles abandoned work.
- **"Can humans use this workflow?"** — Yes, same commands. Agents and humans are interchangeable.
- **"What about partial implementations?"** — Submit only when tests pass. Invariants catch incomplete work.

---

## Pre-Demo Checklist

- [ ] Fresh database with seed data (3-4 verified reqs, 1 unverified)
- [ ] `specs/examples/room-upgrade.md` exists with `REQ-UPGRADE-001`
- [ ] No agents registered (clean `agent_register` demo)
- [ ] Dashboard open at `/admin/requirements/`
- [ ] Terminal font size increased for visibility
