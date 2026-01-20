# Feature Landscape: Requirements Traceability System

**Domain:** Requirements Traceability / Spec Management
**Researched:** 2026-01-19
**Confidence:** HIGH (verified via multiple authoritative sources)

## Context: SpecTrace Positioning

SpecTrace occupies a unique niche: **code-native requirements management for developer-centric teams**. Unlike enterprise tools (IBM DOORS, Jama Connect) that treat requirements as separate from code, or spreadsheets that lack traceability, SpecTrace stores specs as hierarchical markdown in the codebase with pytest-based verification.

This positioning informs feature priorities: features must serve PMs, Engineers, and QA while maintaining the code-native philosophy.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Unique Requirement IDs** | Foundation for all traceability; every RTM tool has this | Low | Format: REQ-001, hierarchical: REQ-001.1 |
| **Requirement Hierarchy** | Users expect parent/child decomposition (5-7 children max per parent) | Medium | Markdown nested headers map naturally to hierarchy |
| **Test-to-Requirement Linking** | Core value proposition; pytest decorators are the mechanism | Medium | `@pytest.mark.requirement("REQ-001")` pattern |
| **Verification Status Display** | "Is this requirement verified?" is the primary question | Low | Pass/Fail/Untested per requirement |
| **Coverage Metrics** | % of requirements with passing tests; table stakes for any RTM | Low | Simple calculation from test results |
| **Basic Traceability Matrix** | Shows requirement-to-test mapping; fundamental to the domain | Medium | Grid view: requirements vs. tests |
| **Requirement Text Storage** | Users must be able to read what the requirement actually says | Low | Markdown content with metadata |
| **Search & Filter** | Finding requirements by ID, text, status, or tag | Medium | Essential for any dataset beyond ~20 items |
| **Test Execution History** | "Did this pass before? When did it start failing?" | Medium | Track pass/fail over time |
| **Dashboard Summary** | At-a-glance health: total requirements, % verified, failures | Low | Single-page overview for PMs |

### Table Stakes Rationale

These features appear in every requirements management tool surveyed: Jama Connect, IBM DOORS, SpiraTeam, Doorstop, Modern Requirements, and Polarion. Users migrating from spreadsheets or other tools will expect these capabilities. The pytest decorator approach (`@pytest.mark.requirement`) is validated by existing tools like pytest-doorstop.

**Sources:**
- [Inflectra - Best Requirements Traceability Software 2026](https://www.inflectra.com/tools/requirements-management/10-best-requirements-traceability-tools)
- [Doorstop - Requirements Management Using Version Control](https://github.com/doorstop-dev/doorstop)
- [pytest-doorstop - pytest plugin for test-requirement linking](https://pypi.org/project/pytest-doorstop/)

---

## Differentiators

Features that set SpecTrace apart. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Markdown-Native Specs** | Specs live in repo, version-controlled with code; no separate database | Low | Core differentiator vs. enterprise tools |
| **Git Integration for Spec History** | Spec changes tracked via git, not custom versioning | Low | Leverage existing git workflow |
| **Real-Time Verification Status** | Dashboard updates as CI runs; live traceability | High | Webhook from CI or polling |
| **Coverage Gap Highlighting** | Visual indicator of requirements without tests | Medium | Critical for QA prioritization |
| **Impact Analysis** | "Which tests verify this changed requirement?" | Medium | When spec changes, show affected tests |
| **Requirement Status Workflow** | Draft -> Review -> Approved states | Medium | Lightweight workflow without enterprise overhead |
| **Multi-Stakeholder Views** | PM sees coverage %, Engineer sees failing tests, QA sees gaps | Medium | Role-appropriate dashboards |
| **Bidirectional Traceability** | Navigate requirement->tests AND test->requirements | Medium | Supports debugging and auditing |
| **Bulk Import/Export** | Import from existing docs, export for reporting | Medium | CSV, Markdown, possibly ReqIF |
| **CI Integration Hooks** | Auto-update status from pytest runs | High | Core automation loop |
| **Requirement Tagging/Categorization** | Group by feature area, priority, release | Low | Enables filtering and reporting |
| **Historical Coverage Trends** | Coverage % over time; are we improving? | Medium | Time-series visualization |

### Key Differentiators for SpecTrace

1. **Code-Native Philosophy**: Unlike Jama/DOORS where requirements live in separate systems, SpecTrace specs are markdown files in the repo. This appeals to developer-centric teams who want everything in git.

2. **pytest-First Design**: Direct integration with pytest via decorators. No separate test management layer - tests ARE the verification.

3. **Lightweight Over Enterprise**: No electronic signatures, no formal approval workflows, no regulated-industry compliance (initially). This is for teams who want traceability without overhead.

**Sources:**
- [Doorstop - Text-Based Requirements Management](https://www.researchgate.net/publication/276044183_Doorstop_Text-Based_Requirements_Management_Using_Version_Control)
- [GitHub Blog - Spec-Driven Development with Markdown](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-using-markdown-as-a-programming-language-when-building-with-ai/)
- [Teamscale - Test Gap Analysis](https://teamscale.com/features/test-gap-analysis)

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full ALM/PLM Suite** | Scope creep; enterprise tools already do this poorly | Stay focused on traceability. Integrate with Jira/Linear for task management. |
| **Built-in Test Execution** | Reinventing pytest/CI; massive complexity | Consume test results from pytest/CI. Don't run tests. |
| **Electronic Signatures** | Regulated industry feature; complex legal requirements (21 CFR Part 11) | Add only if explicitly targeting regulated industries (Phase 2+) |
| **Complex Approval Workflows** | Enterprise overhead; delays adoption | Simple status workflow (Draft/Approved) or none initially |
| **Formal Review Process** | Heavyweight process users will bypass | Lightweight commenting/flagging instead |
| **Custom Requirement Attributes** | Configuration complexity; users get lost | Fixed, opinionated schema. Add flexibility later if demanded. |
| **Multiple Requirement Types** | Feature/Bug/Story/Epic confusion | Requirements only. Integrate with issue trackers for other types. |
| **Real-Time Collaboration Editing** | Google Docs complexity; git handles this | Specs edited in IDE, synced via git |
| **Offline Mode** | Complexity for web dashboard; low value | Dashboard requires connectivity; specs are files (inherently offline) |
| **AI Requirement Generation** | Gimmick; requirements need human judgment | Maybe explore later, but not core |
| **ReqIF Import/Export** | Enterprise standard few users need | Support CSV/Markdown first; ReqIF only if enterprise demand materializes |
| **Variant/Configuration Management** | Automotive/aerospace complexity | Single product variant initially |

### Anti-Feature Rationale

The requirements management space is littered with bloated enterprise tools. Jama Connect, IBM DOORS, and Polarion have feature lists that intimidate small teams. SpecTrace's opportunity is to be the "requirements traceability that developers actually want to use."

**Key insight from research:** "Attempts to try and achieve live traceability with Jira or Jira plugins break down quickly as the complexity of approvals, versioning, change impact analysis, baselines and variant management overwhelm a task management approach." (Jama Software)

The solution is NOT to build all those features. It's to build the minimal traceability that works for teams not in regulated industries.

**Sources:**
- [Jama Software - Why Jira Isn't Enough](https://www.jamasoftware.com/datasheet/jama-connect-integration-jira-datasheet/)
- [Ambysoft - Change Prevention Anti-Pattern](https://ambysoft.com/essays/changeprevention.html)

---

## Feature Dependencies

```
Requirement IDs
    |
    +-- Requirement Hierarchy (needs IDs)
    |
    +-- Test-to-Requirement Linking (needs IDs)
            |
            +-- Verification Status (needs linking)
            |       |
            |       +-- Coverage Metrics (needs status)
            |       |
            |       +-- Coverage Gap Highlighting (needs status)
            |       |
            |       +-- Dashboard Summary (needs metrics)
            |
            +-- Traceability Matrix (needs linking)
            |
            +-- Bidirectional Traceability (needs linking)
            |
            +-- Impact Analysis (needs linking + spec change detection)

CI Integration
    |
    +-- Real-Time Verification Status (needs CI data)
    |
    +-- Historical Coverage Trends (needs CI history)

Markdown Parsing
    |
    +-- Requirement Text Storage (needs parsing)
    |
    +-- Requirement Hierarchy (needs parsing)
    |
    +-- Git Integration (needs file-based specs)
```

### Critical Path

1. **Requirement ID schema** - Everything depends on this
2. **Markdown parsing** - Extract requirements from files
3. **pytest decorator** - Link tests to requirements
4. **Test result ingestion** - Know what passed/failed
5. **Dashboard display** - Show the data

---

## MVP Recommendation

For MVP, prioritize:

### Must Have (Table Stakes)
1. **Requirement IDs + Hierarchy** - Parse markdown specs with IDs
2. **Test-to-Requirement Linking** - pytest decorator implementation
3. **Verification Status** - Pass/Fail/Untested per requirement
4. **Coverage Metrics** - % verified calculation
5. **Basic Dashboard** - Single page showing requirements and status

### Should Have (Key Differentiators)
6. **Traceability Matrix View** - Grid of requirements vs. tests
7. **Coverage Gap Highlighting** - Untested requirements stand out
8. **Search & Filter** - Find requirements quickly

### Defer to Post-MVP
- **Real-time CI integration** - Polling or manual refresh acceptable for MVP
- **Historical trends** - Store history, visualize later
- **Impact analysis** - Valuable but complex
- **Import/Export** - Manual spec creation acceptable initially
- **Multi-stakeholder views** - Single view serves all users for MVP
- **Requirement workflow states** - Implicit (has passing test = verified)

### MVP Success Criteria

A PM can:
1. View all requirements extracted from markdown specs
2. See which requirements have passing tests (green), failing tests (red), or no tests (gray)
3. See overall coverage percentage
4. Click on a requirement to see linked tests
5. Click on a test to see linked requirements

---

## Competitive Landscape Summary

| Tool | Position | SpecTrace Advantage |
|------|----------|---------------------|
| **IBM DOORS** | Enterprise, complex, expensive | Lightweight, code-native, affordable |
| **Jama Connect** | Enterprise, Live Traceability | pytest-native, no separate tool |
| **SpiraTeam** | Mid-market, full ALM | Focused on traceability only |
| **Doorstop** | Code-native, YAML-based | Web dashboard (Doorstop is CLI), pytest integration |
| **Spreadsheets** | Simple, manual | Automated verification, dashboard |
| **Jira + plugins** | Task-centric, limited traceability | Purpose-built for requirements |

### SpecTrace's Niche

**For teams that:**
- Store specs in their codebase (not Confluence/Google Docs)
- Use pytest for testing
- Want traceability without enterprise complexity
- Have PMs who want visibility without learning new tools
- Are NOT in regulated industries (no 21 CFR Part 11, no DO-178C)

---

## Sources

### High Confidence (Official Documentation/Tools)
- [Doorstop GitHub](https://github.com/doorstop-dev/doorstop)
- [pytest-doorstop PyPI](https://pypi.org/project/pytest-doorstop/)
- [Jama Software - Requirements Traceability](https://www.jamasoftware.com/requirements-management-guide/requirements-traceability/)

### Medium Confidence (Industry Analysis)
- [Inflectra - Best Requirements Traceability Software 2026](https://www.inflectra.com/tools/requirements-management/10-best-requirements-traceability-tools)
- [Digital Project Manager - Requirements Management Tools 2026](https://thedigitalprojectmanager.com/tools/requirements-management-tools/)
- [Ketryx - Ultimate Guide to RTM](https://www.ketryx.com/blog/the-ultimate-guide-to-requirements-traceability-matrix-rtm)
- [Teamscale - Test Gap Analysis](https://teamscale.com/features/test-gap-analysis)
- [aqua cloud - Requirements Coverage Analysis](https://aqua-cloud.io/how-to-analyse-test-coverage/)

### Lower Confidence (General Patterns)
- [Requirements Gathering Anti-patterns - Simplicable](https://management.simplicable.com/management/new/8-requirements-gathering-anti-patterns)
- [Ambysoft - Change Prevention Anti-Pattern](https://ambysoft.com/essays/changeprevention.html)
