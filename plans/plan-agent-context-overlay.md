Status: Complete

# Plan: Agent Context Overlay for Task Claims

## Context

Spec-trace already has an `agent_context` command. We want a thin overlay
layer that bundles task context (specs, related specs, recent results/drift,
optional Lore items) into a single artifact an agent can load at session
start.

## Decisions

| Question                   | Answer                                                                       |
| -------------------------- | ---------------------------------------------------------------------------- |
| Related specs relationship | Tree hierarchy (treebeard parent/children), not dependency graph             |
| Drift detection            | Run inline, include full results                                             |
| Test results               | Include full list (not summarized)                                           |
| Format flag values         | Keep existing `text\|json` (no `md`)                                         |
| Lore query construction    | Tags + title combined into one query                                         |
| Lore call granularity      | Single combined query per task (not per requirement)                         |
| Lore CLI discovery         | `LORE_CLI` env var → `PATH` lookup → skip with warning                       |
| Lore timeout               | 30 seconds                                                                   |
| CLI group move             | `st specs context` → `st tasks context`; remove old, no deprecation redirect |

## What to Do

### 1. Extend the context bundle command

Extend the existing management command:

```bash
python spectrace/manage.py agent_context <task_id> --format text
```

The command should:

- Load the task and its linked specs (Requirements)
- Build a context bundle with:
  - Task details (title, status, done_when, scope_in, scope_out)
  - Linked specs text and metadata
  - Tree hierarchy for each linked spec (treebeard parent/children)
  - Full test results per spec (test nodeid + last_status)
  - Inline drift detection results
  - Lore overlay (optional, when Lore CLI is available)

### 2. Define the bundle schema

Output must be stable and predictable for agents. Use a simple markdown
structure with headings. Since a task can have multiple specs, repeat the
spec section for each:

```
# Agent Context Bundle

## Task: {task.title}
- ID: {task.external_id}
- Status: {task.status}
- Done When: ...
- Scope In: ...
- Scope Out: ...

## Linked Specs

### Spec: {req.title}
- ID: {req.external_id}
- Status: {req.verification_status}
- Priority: {req.priority}
- Tags: {req.tags}
- Source: {req.source_file}
- FRET: scope=..., condition=..., component=..., timing=..., response=...

{req.description}

#### Tree Hierarchy
- Parent: {parent.external_id}: {parent.title}
- Children:
  - {child.external_id}: {child.title}

#### Test Results
- {test_nodeid}: {last_status}
- {test_nodeid}: {last_status}

#### Drift
- {drift detection output, inline}

## Lore Context (Optional)
{Combined lore overlay output for all linked specs}
```

### 3. Lore overlay interface

Build a single query from all linked requirements' tags and titles:

```python
# Collect tags and titles from all linked requirements
tags = set()
titles = []
for req in task.requirements.all():
    tags.update(req.tags or [])
    titles.append(req.title)

query = " ".join(sorted(tags) + titles)
```

Shell out to Lore CLI:

```python
import shutil, subprocess

def _find_lore_cli():
    """LORE_CLI env var → PATH lookup → None."""
    env_path = os.environ.get("LORE_CLI")
    if env_path and os.path.isfile(env_path):
        return env_path
    path_hit = shutil.which("lore")
    if path_hit:
        return path_hit
    return None

def _lore_overlay(query, project="spec-trace", limit=10):
    cli = _find_lore_cli()
    if not cli:
        return None  # caller emits warning
    try:
        result = subprocess.run(
            [cli, "overlay", "--query", query, "--project", project,
             "--limit", str(limit), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None
```

### 4. Provide a file output option

Add `--output <path>` to write the bundle to disk so a launcher can drop it
into a `.claude` overlay or an agent handoff file.

### 5. Move CLI command

- Add `context` to the `tasks` group: `st tasks context <task_id>`
- Remove `st specs context` (no deprecation redirect)
- Remove the existing deprecated top-level `context` command

### 6. Keep it optional

If Lore CLI is not found, the command succeeds with a warning on stderr and
only includes SpecTrace data.

If the task cannot be found, exit with a non-zero status and a clear error
message.

## What NOT to Do

- Do not add a new database table.
- Do not change existing agent task commands (claim, release, etc.).
- Do not call external services (Lore CLI is local).
- Do not use the dependency graph (`depends_on`/`depended_by`). Use tree
  hierarchy only. If a graph view is needed later, do an architectural review
  first.

## Files to Modify

- `spectrace/requirements/management/commands/agent_context.py` — extend
  existing command with tree hierarchy, drift, Lore overlay, `--output`
- `spectrace/cli.py` — move `context` from `specs` group to `tasks` group,
  remove old `specs context` and deprecated top-level `context`
- `docs/agent-tasks.md` — document the command

## Acceptance Criteria

- [ ] `agent_context` returns a readable markdown bundle matching the schema
- [ ] Bundle includes tree hierarchy (parent/children) for each linked spec
- [ ] Bundle includes full test results per spec
- [ ] Bundle includes inline drift detection results
- [ ] Lore overlay included when CLI is available
- [ ] Lore section omitted with stderr warning when CLI is missing
- [ ] `--output` writes the file with identical content
- [ ] Returns non-zero exit code on missing task
- [ ] CLI command `st tasks context <task_id>` works
- [ ] `st specs context` removed
- [ ] 30-second timeout on Lore subprocess

## Testing

```bash
# Basic output
python spectrace/manage.py agent_context TASK-001 --format text

# JSON output
python spectrace/manage.py agent_context TASK-001 --format json

# File output
python spectrace/manage.py agent_context TASK-001 --output /tmp/context.md

# Without Lore (unset LORE_CLI, ensure lore not on PATH)
LORE_CLI="" PATH="/usr/bin" python spectrace/manage.py agent_context TASK-001

# Missing task
python spectrace/manage.py agent_context NONEXISTENT-999
```
