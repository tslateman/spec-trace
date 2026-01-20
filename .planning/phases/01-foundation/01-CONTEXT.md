# Phase 1: Foundation - Context

**Gathered:** 2026-01-19
**Status:** Ready for planning

<domain>
## Phase Boundary

System can parse markdown specs from specs/ directory and store requirements with unique IDs, parent/child hierarchy, and category tags. This phase establishes the data model and import pipeline — no UI, no test linking yet.

</domain>

<decisions>
## Implementation Decisions

### Spec file format
- Requirement ID lives in YAML frontmatter (`id: REQ-XXX`)
- Support both single-requirement files and multi-requirement files
- Parser should handle either pattern gracefully

### Claude's Discretion
- Other frontmatter fields (title, tags, parent, etc.) — pick sensible defaults
- Body structure — choose between free prose or light sections
- Hierarchy inference — can use folder structure, frontmatter parent refs, or heading nesting
- ID format details (prefix conventions, numbering scheme)
- Tag/category schema design

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key constraint is that IDs must be in frontmatter for clean parsing.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-01-19*
