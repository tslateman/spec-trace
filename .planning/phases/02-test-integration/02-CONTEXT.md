# Phase 2: Test Integration - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

pytest plugin that lets developers annotate tests with requirement IDs using markers, plus a CLI command to extract those links. Tests can link to multiple requirements, and multiple tests can link to the same requirement. Verification status computation is Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Decorator design
- Use native pytest marker: `@pytest.mark.requirement("REQ-01", "REQ-02")`
- Multiple requirements as multiple args in one decorator
- Optional `reason` kwarg: `@pytest.mark.requirement("REQ-01", reason="tests login flow")`
- Validate at test collection time: warn on unknown REQ IDs (don't fail)

### Link extraction
- Separate CLI command: `python manage.py extract_links`
- Use pytest's collection mechanism for test discovery (respects pytest.ini, conftest)
- Output JSON file (not direct DB update) — separate import step
- Verbose flag: `-v` shows each test->requirement mapping, summary by default

### Claude's Discretion
- JSON schema for extracted links
- Where JSON file is written (stdout, temp, or specified path)
- How pytest collection is invoked programmatically
- Error handling for invalid REQ IDs (warn format, continue behavior)
- Test metadata to include (file path, function name, class, etc.)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-test-integration*
*Context gathered: 2026-01-20*
