# OpenCode Plugins vs Claude Code GSD: Comprehensive Comparison

**Date**: 2026-01-20  
**Purpose**: Compare workflow capabilities between OpenCode plugins and Claude Code's Get Shit Done (GSD)

---

## Executive Summary

**OpenCode Stack (4 plugins)** provides workflow orchestration through composable plugins with different specializations, while **GSD (Claude Code)** is a single integrated system with comprehensive project lifecycle management.

### Quick Verdict

| Aspect | OpenCode Plugins | Claude Code GSD |
|--------|------------------|-----------------|
| **Philosophy** | Modular, compose-your-own workflow | Opinionated, integrated system |
| **Best For** | Flexible teams, custom workflows | Solo devs, structured delivery |
| **Complexity** | Higher (4 plugins to coordinate) | Lower (one system, clear path) |
| **Lifecycle Coverage** | Partial (requires composition) | Complete (new-project → ship) |
| **Team Features** | Strong (plannotator collaboration) | Weak (single-user focused) |
| **Context Management** | Manual ($TURN[n]) | Automatic (XML, STATE.md) |

---

## Feature Matrix

### Project Lifecycle Management

| Feature | OpenCode (subtask2 + plannotator + skillful) | GSD (Claude Code) |
|---------|----------------------------------------------|-------------------|
| **Project Initialization** | ❌ None | ✅ `/gsd:new-project` (questions → research → requirements → roadmap) |
| **Milestone Tracking** | ❌ None | ✅ `/gsd:new-milestone` (versioned releases) |
| **Phase Management** | ⚠️ Manual via subtask2 | ✅ Built-in (`/gsd:add-phase`, `/gsd:insert-phase`) |
| **Requirements Tracing** | ❌ None | ✅ Automatic (REQUIREMENTS.md, phase mapping) |
| **Progress Tracking** | ❌ None | ✅ `/gsd:progress` (where am I, what's next) |
| **State Persistence** | ⚠️ Manual (skills ledgers) | ✅ STATE.md (decisions, blockers, session memory) |

**Winner**: **GSD** - Comprehensive project lifecycle from inception to completion

---

### Workflow Orchestration

| Feature | subtask2 | GSD |
|---------|----------|-----|
| **Multi-step workflows** | ✅ `return:` chaining | ✅ Built-in phase execution |
| **Parallel execution** | ✅ `parallel:` (needs PR) | ✅ Native (research, planning, execution) |
| **Command composition** | ✅ `/cmd \|\| args` | ⚠️ Fixed commands, less flexible |
| **Context injection** | ✅ `$TURN[n]` syntax | ✅ Automatic via planning files |
| **Model selection** | ✅ `{model:...}` inline | ⚠️ Via config only |
| **Conditional logic** | ❌ None | ❌ None |
| **Error recovery** | ⚠️ Manual | ✅ `/gsd:verify-work` + auto-debug |

**Winner**: **subtask2** for flexibility, **GSD** for reliability

---

### Planning & Design

| Feature | OpenCode Stack | GSD |
|---------|----------------|-----|
| **Brainstorming** | ⚠️ Manual prompts | ✅ `/gsd:new-project` (questions agent) |
| **Research agents** | ⚠️ Via subtask2 parallel | ✅ Built-in (stack, features, architecture, pitfalls) |
| **Visual plan review** | ✅ plannotator UI | ❌ Terminal only |
| **Team collaboration** | ✅ plannotator sharing | ❌ Single-user |
| **Plan verification** | ✅ plannotator approve/reject | ✅ Plan checker agent |
| **Implementation decisions** | ❌ Ad-hoc | ✅ `/gsd:discuss-phase` (structured Q&A) |
| **Plan context injection** | ⚠️ Manual | ✅ Automatic (PLAN.md, CONTEXT.md) |

**Winner**: **plannotator** for team collaboration, **GSD** for structured decision capture

---

### Context Management

| Feature | OpenCode Stack | GSD |
|---------|----------------|-----|
| **Context size limits** | ❌ Manual management | ✅ 2-3 plans per phase, size-limited |
| **Fresh context per task** | ❌ Same session | ✅ Subagents with 200k tokens each |
| **Context degradation** | ⚠️ Risk of "context rot" | ✅ Solved (fresh executors) |
| **Session continuity** | ⚠️ micode ledgers (not in stack) | ✅ STATE.md, SUMMARY.md |
| **Context format** | ⚠️ Markdown/JSON | ✅ XML (Claude-optimized) |
| **Historical reference** | ✅ `$TURN[n]` | ✅ Automatic git history |

**Winner**: **GSD** - Purpose-built to prevent context degradation

---

### Execution & Verification

| Feature | OpenCode Stack | GSD |
|---------|----------------|-----|
| **Atomic tasks** | ⚠️ Manual task definition | ✅ XML-structured tasks (2-3 min each) |
| **Atomic commits** | ❌ None | ✅ One commit per task automatically |
| **Parallel implementation** | ⚠️ Via subtask2 | ✅ Plan waves (independent tasks) |
| **Verification built-in** | ❌ None | ✅ Verifier agent per phase |
| **User acceptance testing** | ❌ None | ✅ `/gsd:verify-work` (manual UAT) |
| **Auto-debugging** | ❌ None | ✅ Debugger agents on failures |
| **Git integration** | ❌ Manual | ✅ Conventional commits, tags |

**Winner**: **GSD** - Comprehensive verification and error recovery

---

### Team Collaboration

| Feature | OpenCode Stack | GSD |
|---------|----------------|-----|
| **Visual plan review** | ✅ plannotator browser UI | ❌ Terminal only |
| **Inline annotations** | ✅ plannotator (pen, arrows) | ❌ None |
| **Code review UI** | ✅ `/plannotator-review` | ❌ None |
| **Plan sharing** | ✅ Private/public links | ❌ None |
| **Stakeholder approval** | ✅ Approve/reject flow | ❌ None |
| **Note-taking integration** | ✅ Obsidian, Bear auto-save | ❌ None |
| **Multi-user coordination** | ✅ Team sharing | ❌ Single-user only |

**Winner**: **OpenCode (plannotator)** - Built for team collaboration

---

### Knowledge Management

| Feature | OpenCode Stack | GSD |
|---------|----------------|-----|
| **Skills system** | ✅ opencode-skillful (lazy-loaded) | ❌ None |
| **Skill discovery** | ✅ `skill_find` by keyword | ❌ None |
| **On-demand loading** | ✅ Only load what you need | ❌ N/A |
| **Resource access** | ✅ `skill_resource` (templates, guides) | ❌ None |
| **Codebase intelligence** | ❌ None | ✅ `/gsd:map-codebase` (patterns, conventions) |
| **Project context** | ❌ None | ✅ PROJECT.md, ARCHITECTURE.md |
| **Research artifacts** | ❌ None | ✅ `.planning/research/` |

**Winner**: **Tie** - Different approaches (skills vs project context)

---

## Architectural Comparison

### GSD Architecture (Claude Code)

```
┌─────────────────────────────────────────────────────┐
│ Lifecycle Management (Milestones, Phases, State)   │
├─────────────────────────────────────────────────────┤
│ Context Engineering Layer                           │
│ - PROJECT.md (vision, always loaded)                │
│ - REQUIREMENTS.md (scoped v1/v2/out-of-scope)       │
│ - ROADMAP.md (phases, completion tracking)          │
│ - STATE.md (decisions, blockers, position)          │
│ - research/ (ecosystem knowledge)                   │
│ - PLAN.md (XML tasks, 2-3 min each)                 │
│ - SUMMARY.md (what happened, committed history)     │
├─────────────────────────────────────────────────────┤
│ Multi-Agent Orchestration                           │
│ - Thin orchestrators spawn specialized agents       │
│ - Fresh 200k context per executor                   │
│ - Parallel waves for independent tasks              │
│ - Verifier + debugger agents                        │
├─────────────────────────────────────────────────────┤
│ Execution Engine                                    │
│ - XML-structured tasks                              │
│ - Atomic git commits per task                       │
│ - Built-in verification                             │
│ - Auto-debugging on failures                        │
└─────────────────────────────────────────────────────┘
```

### OpenCode Plugin Stack Architecture

```
┌─────────────────────────────────────────────────────┐
│ User Composition Layer (You Build Workflows)        │
│ - Create custom commands                            │
│ - Combine plugins via frontmatter                   │
│ - Define return chains manually                     │
├─────────────────────────────────────────────────────┤
│ Plugin Layer (4 Independent Systems)                │
│ ┌─────────────────┬─────────────────────────────┐   │
│ │ subtask2        │ plannotator                 │   │
│ │ - return:       │ - Browser UI                │   │
│ │ - parallel:     │ - Team sharing              │   │
│ │ - $TURN[n]      │ - Annotations               │   │
│ └─────────────────┴─────────────────────────────┘   │
│ ┌─────────────────┬─────────────────────────────┐   │
│ │ skillful        │ md-table-formatter          │   │
│ │ - skill_find    │ - Auto-cleanup              │   │
│ │ - skill_use     │ - Passive                   │   │
│ │ - skill_resource│                             │   │
│ └─────────────────┴─────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│ OpenCode Core (Tool System)                         │
│ - Command frontmatter                               │
│ - Subtask spawning                                  │
│ - Message injection                                 │
└─────────────────────────────────────────────────────┘
```

**Key Difference**: GSD is **vertically integrated** (all layers work together), OpenCode is **horizontally composable** (you wire plugins together).

---

## Use Case Scenarios

### Scenario 1: Build a New Feature from Scratch

#### Using OpenCode Stack

```bash
# Manual workflow composition required
1. Create custom command: /plan-and-build
   ---
   subtask: true
   parallel: /research-patterns, /check-codebase
   return:
     - Create implementation plan
     - /plannotator
     - /implement-if-approved
   ---
   
2. Agent creates plan → Opens plannotator UI
3. You annotate visually, approve
4. Agent implements (same context window)
5. Manual verification, no UAT flow
```

**Pros**: Visual review, team collaboration, flexible  
**Cons**: Manual wiring, same context, no verification system

#### Using GSD

```bash
1. /gsd:new-project
   - Answers questions about your idea
   - Spawns 4 parallel research agents
   - Generates requirements + roadmap
   - You approve roadmap

2. /gsd:discuss-phase 1
   - Agent asks about implementation preferences
   - Captures decisions in CONTEXT.md

3. /gsd:plan-phase 1
   - Researches patterns (guided by CONTEXT)
   - Creates 2-3 atomic task plans
   - Plan checker verifies against goals

4. /gsd:execute-phase 1
   - Spawns fresh executors (200k each)
   - Parallel waves, atomic commits
   - Verifier checks against phase goals

5. /gsd:verify-work 1
   - Manual UAT with testable deliverables
   - Auto-creates fix plans if failures
```

**Pros**: Structured, fresh context, verification, UAT  
**Cons**: Terminal only, no visual review, single-user

---

### Scenario 2: Collaborate with Team on Complex Plan

#### Using OpenCode Stack (plannotator)

```bash
1. Agent creates plan
2. /plannotator
3. Opens browser UI:
   - Annotate with pen/arrow/circle
   - Add comments per section
   - Share link with team (private/public)
4. Team reviews asynchronously
5. You consolidate feedback
6. Approve or request changes
7. Agent proceeds with same context
```

**Pros**: Visual, async team collaboration, annotations  
**Cons**: No built-in implementation workflow

#### Using GSD

```bash
# Not designed for this
1. Agent creates PLAN.md
2. You read in terminal
3. Manual copy-paste to Slack/Notion
4. Team comments in separate tool
5. You manually relay feedback to agent
6. Agent revises plan in same session
```

**Pros**: Plan is verified automatically  
**Cons**: Terminal only, no sharing, no visual tools

**Winner**: **OpenCode (plannotator)** by a wide margin

---

### Scenario 3: Maintain Context Across Long Project

#### Using OpenCode Stack (skillful ledgers)

```bash
# Not in your current stack, would need micode
1. Work on feature
2. End of day: /ledger
3. Creates CONTINUITY_{session}.md
4. Next day: Agent reads ledger
5. Continues work (manual prompt engineering)
```

**Pros**: Session continuity via ledgers  
**Cons**: Not automatic, requires micode (not installed)

#### Using GSD

```bash
1. Work on phase 1
2. Context fills up → fresh executors spawn
3. Each task: SUMMARY.md created
4. STATE.md updated with decisions
5. Next session: Agent reads STATE.md automatically
6. /gsd:progress shows exactly where you are
```

**Pros**: Automatic state management, no prompting  
**Cons**: None (built-in)

**Winner**: **GSD** - Purpose-built for long projects

---

## Workflow Philosophy Comparison

### OpenCode Stack Philosophy

**"Compose your workflow from specialized tools"**

- **Modular**: Each plugin does one thing well
- **Flexible**: Wire plugins together however you want
- **Learn-as-you-go**: Start simple, add complexity
- **Team-friendly**: plannotator built for collaboration
- **Knowledge-driven**: Skills loaded on-demand

**Ideal for**: Teams with custom processes, visual thinkers, collaborative workflows

---

### GSD Philosophy

**"Enforce a proven workflow that prevents common failures"**

- **Opinionated**: One right way to do things
- **Integrated**: All pieces work together seamlessly
- **Context-aware**: Prevents context rot by design
- **Verification-first**: Check work at every phase
- **Solo-optimized**: Built for individual developers

**Ideal for**: Solo developers, structured delivery, high-quality consistency

---

## Missing Features Analysis

### What GSD Has That OpenCode Stack Lacks

1. **Milestone & Phase Management**
   - No equivalent in OpenCode plugins
   - Would need custom commands + manual tracking

2. **Automatic Context Management**
   - subtask2 helps, but not automatic
   - Risk of context degradation in long sessions

3. **Requirements Tracing**
   - No plugin tracks requirements → phases → tests
   - Manual documentation required

4. **Built-in Verification**
   - No automatic plan checking
   - No UAT workflow with fix generation

5. **Codebase Intelligence**
   - No `/gsd:map-codebase` equivalent
   - Would need manual analysis prompts

6. **Fresh Context Per Task**
   - subtask2 spawns subagents but same context window
   - GSD's executors get fresh 200k tokens each

### What OpenCode Stack Has That GSD Lacks

1. **Visual Plan Review**
   - plannotator browser UI with annotations
   - GSD is terminal-only

2. **Team Collaboration**
   - plannotator sharing, async review
   - GSD is single-user focused

3. **Skills System**
   - opencode-skillful: lazy-load prompts on-demand
   - GSD has no skill/knowledge library

4. **Model Selection Flexibility**
   - subtask2: `{model:...}` inline per command
   - GSD: config-based only

5. **Command Composition**
   - subtask2: build complex workflows from commands
   - GSD: fixed command set

6. **Code Review UI**
   - `/plannotator-review` for git diffs
   - GSD has no visual diff review

---

## Performance & Efficiency

### Context Token Usage

| System | Tokens per Session | Why |
|--------|-------------------|-----|
| **OpenCode Stack** | High (single session) | All plugins, skills, history in one context |
| **GSD** | Low (fresh spawns) | Executors get fresh 200k, main session stays lean |

### Execution Speed

| System | Speed | Why |
|--------|-------|-----|
| **OpenCode Stack** | Moderate | Parallel via subtask2 (needs PR merge) |
| **GSD** | Fast | Native parallel waves, fresh contexts |

### Quality Consistency

| System | Consistency | Why |
|--------|-------------|-----|
| **OpenCode Stack** | Variable | Depends on context management |
| **GSD** | High | Fresh executors prevent degradation |

---

## Learning Curve

### OpenCode Stack

**Time to Productivity**: 2-3 days

```
Day 1: Learn subtask2 syntax (return, parallel, $TURN)
Day 2: Learn plannotator workflow (annotate, approve)
Day 3: Learn opencode-skillful (find, use, resource)
Day 4+: Build custom commands, integrate plugins
```

**Complexity**: High - 4 plugins, different syntaxes, manual composition

### GSD

**Time to Productivity**: 2-4 hours

```
Hour 1: Run /gsd:new-project, understand flow
Hour 2: Try /gsd:discuss-phase, see CONTEXT.md
Hour 3: Run /gsd:plan-phase, inspect PLAN.md
Hour 4: Execute /gsd:execute-phase, watch it work
```

**Complexity**: Low - Linear workflow, clear commands, automatic

---

## Cost Analysis (API Tokens)

### Small Feature (500 LOC)

| System | Estimated Tokens | Why |
|--------|-----------------|-----|
| **OpenCode Stack** | ~150k-200k | Single session, context accumulation |
| **GSD** | ~100k-120k | Fresh executors, efficient context |

### Large Project (5000 LOC)

| System | Estimated Tokens | Why |
|--------|-----------------|-----|
| **OpenCode Stack** | ~800k-1.2M | Context rot, rework, inefficiency |
| **GSD** | ~400k-600k | Fresh contexts prevent degradation |

**Savings**: GSD can be 40-50% cheaper on large projects

---

## Real-World Fit Analysis

### You Should Use OpenCode Stack If:

✅ You work in a team (2-5 people)  
✅ Stakeholder approval is required  
✅ You prefer visual tools over terminal  
✅ You want flexible, composable workflows  
✅ You have custom processes to maintain  
✅ Collaboration > solo efficiency  

### You Should Use GSD If:

✅ You're a solo developer  
✅ You want proven, structured workflow  
✅ Context quality matters more than flexibility  
✅ You build medium-to-large features (weeks)  
✅ You want hands-off verification  
✅ Efficiency > collaboration tools  

---

## Hybrid Approach: Best of Both Worlds?

**Can you use both?**

Not directly (different platforms), but you can **learn from each**:

### Port GSD Concepts to OpenCode

```bash
# Create OpenCode commands inspired by GSD

# 1. new-project.md (mimic /gsd:new-project)
---
subtask: true
parallel: /research-stack, /research-features
return:
  - Create requirements document
  - Generate roadmap
---
Ask questions about the project until you understand it completely...

# 2. plan-phase.md (mimic /gsd:plan-phase)
---
subtask: true
return:
  - Break plan into 2-3 atomic tasks
  - Each task should take 2-3 minutes
  - Create PLAN.md with XML structure
---
Research patterns, then create implementation plan...

# 3. execute-phase.md (use subtask2 + plannotator)
---
subtask: true
parallel: /implement-task-1, /implement-task-2
return:
  - /plannotator-review
  - Verify deliverables
---
Execute all tasks, create atomic commits per task...
```

**Result**: GSD-inspired workflow on OpenCode, with visual collaboration

---

## Final Verdict

### For SpecTrace Project Specifically

Given your context:
- Small team (2-5)
- Medium features (days)
- Intermediate technical comfort
- Want orchestration + collaboration

**Recommendation**: **Stick with OpenCode Stack**

**Why**:
1. You already have it installed and configured
2. plannotator is valuable for team collaboration
3. subtask2 gives you orchestration power you need
4. SpecTrace features are medium-sized (not weeks-long)
5. You're building a traceability system - visual review fits the domain

**When to Consider GSD**:
- If you were solo dev
- If building massive features (weeks)
- If context rot becomes a problem
- If you switch to Claude Code anyway

---

## Summary Table

| Criterion | OpenCode Stack | GSD | Winner |
|-----------|----------------|-----|--------|
| **Lifecycle Management** | ❌ | ✅✅✅ | GSD |
| **Context Engineering** | ⚠️ | ✅✅✅ | GSD |
| **Team Collaboration** | ✅✅✅ | ❌ | OpenCode |
| **Visual Tools** | ✅✅✅ | ❌ | OpenCode |
| **Workflow Flexibility** | ✅✅✅ | ⚠️ | OpenCode |
| **Verification System** | ❌ | ✅✅✅ | GSD |
| **Learning Curve** | ⚠️ | ✅✅ | GSD |
| **Token Efficiency** | ⚠️ | ✅✅✅ | GSD |
| **Skills/Knowledge** | ✅✅ | ❌ | OpenCode |
| **Solo Developer** | ⚠️ | ✅✅✅ | GSD |
| **Small Team** | ✅✅✅ | ❌ | OpenCode |

**Overall Winner**: **Depends on your team size and workflow needs**

- **Solo dev building large projects**: **GSD**
- **Small team with collaboration needs**: **OpenCode Stack**

---

**Last Updated**: 2026-01-20  
**Your Choice**: OpenCode Stack (subtask2 + plannotator + skillful + md-table-formatter)
