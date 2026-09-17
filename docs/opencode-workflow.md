# OpenCode workflow

Plugin setup and session-continuity practices for working on SpecTrace in
OpenCode. Moved out of `AGENTS.md`, which now carries only what an agent
needs at the point of work: architecture, boundaries, commands, style, and
known anti-patterns.

## OpenCode Plugin Setup

This project uses OpenCode with the following plugins for enhanced workflow capabilities:

### Installed Plugins

1. **@openspoon/subtask2** - Command orchestration with parallel execution and chaining
2. **@plannotator/opencode** - Visual plan review with team collaboration
3. **@franlol/opencode-md-table-formatter** - Clean up markdown tables from LLMs
4. **@zenobius/opencode-skillful** - Lazy-loaded skills system
5. **micode** - Brainstorm → Plan → Implement workflow with session continuity

### Plugin Configuration

Location: `~/.config/opencode/opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "@openspoon/subtask2@latest",
    "@plannotator/opencode@latest",
    "@franlol/opencode-md-table-formatter@0.0.3",
    "@zenobius/opencode-skillful@latest",
    "micode"
  ]
}
```

### Key Plugin Commands

**subtask2 orchestration:**

- Use `return:` in command frontmatter to chain prompts or commands
- Use `parallel:` to run multiple subtasks concurrently
- Use `$TURN[n]` to inject previous conversation context
- Use `{model:provider/model-id}` for inline model overrides

**plannotator visual review:**

- `/plannotator` - Open visual plan review UI in browser
- `/plannotator-review` - Review git diffs with inline annotations
- Annotate, approve, or request changes visually

**opencode-skillful:**

- `skill_find "keyword"` - Search for relevant skills
- `skill_use "skill_name"` - Load skill into chat context
- `skill_resource skill_name="..." relative_path="..."` - Read skill resources

**micode workflow:**

- `/init` - Initialize project docs (ARCHITECTURE.md, CODE_STYLE.md)
- `/ledger` - Create/update session continuity ledger
- `/search` - Search past plans and ledgers

### CLI Tools Installed

- **plannotator**: `~/.local/bin/plannotator` - Plan review integration

## Knowledge Management & Session Continuity

### Philosophy

- **Manual notes in .planning/** for decisions and project state
- **/ledger command** for end-of-session context capture
- **opencode-skillful** for reusable patterns and expertise
- **Guidelines over enforcement** - use structure when it helps

### Session Continuity Practices

#### Using /ledger Command

**When to create a ledger:**

- End of coding session
- Before context switching to another project
- After completing significant milestones
- When you need to pause work for extended period

**What to capture:**

- What was accomplished this session
- Decisions made and why
- Current blockers or open questions
- What to resume next session
- Links to relevant .planning/ docs

**Output location:** `thoughts/ledgers/CONTINUITY_{session}.md`

#### Manual Notes in .planning/

Continue using existing structure:

- `STATE.md` - Update after each plan completion
- `PROJECT.md` - Log key decisions in decisions table
- `phases/` - Per-phase context and plans
- `research/` - Research artifacts and evaluations

**Relationship to /ledger:**

- Ledgers are session-oriented (what happened today)
- .planning/ docs are project-oriented (overall state)
- Reference ledgers from STATE.md when decisions span sessions

### Organizing Knowledge with opencode-skillful

**Optional directory:** `~/.config/opencode/skills/`

**When to create skills:**

- You solve a problem more than once
- Pattern is reusable across features
- External expertise needs to be captured (library docs, best practices)
- Onboarding new team members to patterns

**Skill commands:**

- `skill_find "django testing"` - Search for relevant skills
- `skill_use "experts/django-patterns"` - Load into context
- `skill_resource skill_name="..." relative_path="resources/examples.py"` - Read files

### Preventing Truth Decay

Truth Decay = Requirements/decisions degrade as code evolves without updates

**Project-Level Prevention** (SpecTrace's mission):

- Specs in version control (specs/)
- Test markers link code to requirements (@pytest.mark.requirement)
- Dashboard shows verification status

**Development-Level Prevention** (Your workflow):

1. **Decision Logging**: Update PROJECT.md decisions table when making architectural choices
2. **Session Ledgers**: Run /ledger before ending sessions to capture context
3. **Linking**: Reference requirement IDs in commit messages, ledgers, and .planning/ docs
4. **Review**: Periodically review STATE.md and ledgers to refresh context

### Workflow Patterns (Guidelines, Not Rules)

#### Starting New Feature

1. Check STATE.md for current project position
2. Review relevant past ledgers: `skill_find "continuity"` or manual search
3. Create phase planning doc in .planning/phases/{phase}/
4. Start work

#### During Development

- Update STATE.md decisions as you make them
- Use skill_find when encountering solved problems
- Create new skills when patterns emerge

#### Ending Session

1. Run `/ledger` to capture session context
2. Update STATE.md with progress/metrics
3. Commit work with descriptive messages
4. Note resume point in ledger

#### Multi-Session Features

- Reference previous ledgers at session start
- Keep STATE.md current position updated
- Link ledgers together with "Previous: CONTINUITY_20260120.md" references

### Integration with Other Plugins

**subtask2 + ledger:**

- Use $TURN[n] to reference past decisions from ledgers
- Chain commands: research → plan → implement → ledger

**plannotator + ledger:**

- Create ledger after plan review sessions
- Capture review feedback in ledger

**skillful + ledger:**

- Note in ledger when new skills are created
- Reference skills used during session
