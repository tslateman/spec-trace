Status: Draft

# Plan: Agent Context Overlay for Task Claims

## Context

Spec-trace already has an `agent_context` command. We want a thin overlay
layer that bundles task context (spec, related specs, recent results/drift,
optional Lore items) into a single artifact an agent can load at session
start.

## What to Do

### 1. Extend the context bundle command

Extend the existing management command:

```bash
python spectrace/manage.py agent_context <task_id> --format md
```

The command should:

- Load the task and its spec (Requirement)
- Build a small context bundle with:
  - Spec text and metadata
  - Related specs (parents/children)
  - Recent results or drift markers
  - Lore overlay output for the spec tags (optional, when Lore is present)

### 2. Define the bundle schema

Output must be stable and predictable for agents. Use a simple markdown
structure with headings:

```
# Agent Context Bundle

## Task
- id, title, status, done_when, scope_in, scope_out

## Spec
- external_id, title, status, priority, tags, source_file
- description

## Related Specs
- Parents
- Children

## Recent Evidence
- Latest verification run summary (if available)
- Drift warnings (if available)

## Lore (Optional)
- Tag matches and notes when Lore is installed
```

### 3. Provide a file output option

Add `--output <path>` to write the bundle to disk so a launcher can drop it
into a `.claude` overlay or an agent handoff file.

### 4. Keep it optional

If Lore is not available, the command should still succeed with a warning and
only include SpecTrace data.

If the task or spec cannot be found, exit with a non-zero status and a clear
error message.

## What NOT to Do

- Do not add a new database table.
- Do not change existing agent task commands.
- Do not call external services.

## Files to Modify

- `spectrace/requirements/management/commands/agent_context.py` -- extend
  existing command
- `spectrace/requirements/` (or equivalent) -- helper to assemble context
- `README.md` or `docs/agent-tasks.md` -- document the command

## Acceptance Criteria

- [ ] `agent_context` returns a readable markdown bundle
- [ ] `--output` writes the file with identical content
- [ ] Runs without Lore installed
- [ ] Returns non-zero exit code on missing task/spec

## Testing

```bash
python spectrace/manage.py agent_context REQ-AUTH-001 --format md
python spectrace/manage.py agent_context REQ-AUTH-001 --format md --output /tmp/context.md
```
