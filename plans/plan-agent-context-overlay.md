Status: Draft

# Plan: Agent Context Overlay for Task Claims

## Context

Spec-trace already has an `agent_context` command. We want a thin overlay
layer that bundles task context (specs, related specs, recent results/drift,
optional Lore items) into a single artifact an agent can load at session
start.

## What to Do

### 1. Extend the context bundle command

Extend the existing management command:

```bash
python spectrace/manage.py agent_context <task_id> --format md
```

The command should:

- Load the task and its linked specs (Requirements)
- Build a small context bundle with:
  - Task details
  - Linked specs text and metadata
  - Related specs (parents/children for each linked spec)
  - Recent results or drift markers
  - Lore overlay output for the spec tags (optional, when Lore is present)

### 2. Define the bundle schema

Output must be stable and predictable for agents. Use a simple markdown
structure with headings. Since a task can have multiple specs, repeat the spec section for each:

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
- Status: {req.status}
- Priority: {req.priority}
- Tags: {req.tags}
- Source: {req.source_file}

{req.description}

#### Related Specs
- Parents: ...
- Children: ...

#### Recent Evidence
- Latest verification run summary (if available)
- Drift warnings (if available)

#### Lore (Optional)
- Tag matches and notes when Lore is installed
```

### 3. Provide a file output option

Add `--output <path>` to write the bundle to disk so a launcher can drop it
into a `.claude` overlay or an agent handoff file.

### 4. Keep it optional

If Lore is not available, the command should still succeed with a warning and
only include SpecTrace data.

If the task cannot be found, exit with a non-zero status and a clear
error message.

## What NOT to Do

- Do not add a new database table.
- Do not change existing agent task commands.
- Do not call external services.

## Files to Modify

- `spectrace/requirements/management/commands/agent_context.py` -- extend
  existing command
- `spectrace/cli.py` -- Move the `context` command from the `specs` group to the `tasks` group, as it takes a `task_id`
- `README.md` or `docs/agent-tasks.md` -- document the command

## Acceptance Criteria

- [ ] `agent_context` returns a readable markdown bundle matching the new schema
- [ ] `--output` writes the file with identical content
- [ ] Runs without Lore installed
- [ ] Returns non-zero exit code on missing task
- [ ] CLI command `st tasks context <task_id>` works correctly

## Testing

```bash
python spectrace/manage.py agent_context TASK-001 --format md
python spectrace/manage.py agent_context TASK-001 --format md --output /tmp/context.md
```
