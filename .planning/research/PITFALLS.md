# Domain Pitfalls: Requirements Traceability Systems

**Project:** SpecTrace
**Domain:** Requirements traceability with markdown specs, pytest decorators, Django dashboard
**Researched:** 2026-01-19
**Confidence:** HIGH (multiple sources, domain-specific patterns verified)

---

## Critical Pitfalls

Mistakes that cause rewrites, project failure, or fundamental trust erosion.

---

### Pitfall 1: Hierarchical ID Fragility (The Renumber Cascade)

**What goes wrong:** Using outline-style hierarchical requirement IDs (REQ-1.2.3) that embed position in the hierarchy. When requirements are reordered, moved, or deleted, all downstream IDs shift, breaking every test decorator reference and dashboard link.

**Why it happens:** Outline numbering feels natural from Word/Google Docs. Teams assume "REQ-1.2.3" is stable. They don't realize position-based IDs are fundamentally unstable in evolving specifications.

**Consequences:**
- Mass broken references after any spec restructure
- Engineers lose trust in the system
- Manual ID fixup becomes a recurring maintenance burden
- History becomes meaningless ("REQ-1.2" used to mean something different)

**Warning signs:**
- Spec authors want to "reorganize" or "clean up" the hierarchy
- Tests reference IDs like `@spec("REQ-1.2.3")` with positional meaning
- Discussions about "what happened to REQ-4.x?"

**Prevention:**
- Use **immutable, sequential IDs** that never change: `SPEC-0042`
- Hierarchy lives in folder/file structure and metadata, NOT in the ID
- Generate IDs automatically on creation, never manually assigned
- Consider GUIDs for internal references, human IDs for display only

**Detection:**
- Grep for positional-looking IDs in decorators: `@spec(".*\.\d+\.\d+.*")`
- Count ID references that 404 in the dashboard

**Phase to address:** Phase 1 (Core Schema). This is foundational - get it wrong and you rebuild everything.

**Sources:**
- [Sparx Systems: Requirements Naming and Numbering](https://sparxsystems.com/enterprise_architect_user_guide/15.2/model_domains/requirements_naming_and_numbering.html)
- [Digital Solution Architecture: A frequent mistake when naming ID references](https://www.digital-solution-architecture.com/blog/2021-07-13/A-frequent-mistake-when-naming-ID-references.php)

---

### Pitfall 2: Specification Drift (The Lying Docs Problem)

**What goes wrong:** Markdown specs in the codebase become out of sync with actual system behavior. Tests pass, dashboard shows green, but the specs describe a system that no longer exists.

**Why it happens:**
- Specs and code live together but evolve separately
- "Update docs" checkbox in PRs gets checked reflexively without actual updates
- Engineers change behavior but not specs; PMs write specs but don't validate against code
- No automated validation that specs match implementation

**Consequences:**
- PMs make decisions based on outdated specs
- New engineers implement against stale requirements
- Compliance/audit failures when specs don't match reality
- Trust erosion: "Nobody reads the specs anyway"

**Warning signs:**
- Specs reference features that were never built or were deprecated
- PR reviews don't include spec reviewers
- Engineers say "I didn't know that spec existed"
- Specs haven't been modified in months while code changed weekly

**Prevention:**
- **Bi-directional traceability enforcement:** Every test must link to a spec; every spec should have linked tests
- **Orphan detection:** Dashboard surfaces untested specs AND unlinked tests
- **Spec modification triggers:** Changes to related code should prompt spec review
- **Include spec owners in code review** for relevant paths
- **Version spec+code together:** Spec changes and code changes in same PR when related

**Detection:**
- Last-modified dates: specs unchanged while code paths changed
- Coverage gaps: specs with zero linked tests
- Orphan tests: tests that don't reference any valid spec ID

**Phase to address:** Phase 2 (Parsing/Linking) for detection; ongoing enforcement in CI/CD

**Sources:**
- [DocsAlot: Documentation Rots. Here's How to Stop It](https://docsalot.dev/blog/documentation-rots-heres-how-to-stop-it)
- [Gaudion: What is Documentation Drift and How to Avoid It?](https://gaudion.dev/blog/documentation-drift)

---

### Pitfall 3: False Confidence from Green Dashboards

**What goes wrong:** Dashboard shows "85% requirements verified" but this metric is meaningless or misleading. Tests exist and pass but don't actually verify the requirement's behavior.

**Why it happens:**
- Teams optimize for metrics, not quality (Goodhart's Law)
- A test that mentions a requirement ID isn't the same as a test that verifies it
- Assertion-free tests still "pass" and link to requirements
- Shallow tests cover the happy path but miss edge cases and failure modes

**Consequences:**
- PMs believe features are verified when they're not
- Defects slip to production because coverage numbers lied
- Teams become cynical about traceability ("it's just compliance theater")
- Auditors get suspicious when "verified" requirements have production bugs

**Warning signs:**
- High coverage percentage but production bugs in "verified" requirements
- Tests that touch requirement code but assert nothing meaningful
- All tests pass in seconds (suspiciously fast for claimed coverage)
- Coverage jumps dramatically after "add traceability" sprint

**Prevention:**
- **Distinguish "linked" from "verified":** A test is linked (references the spec); verification is a human judgment that the test adequately covers the requirement
- **Require manual verification sign-off** for high-risk requirements
- **Surface test quality signals:** Test duration, assertion count, mutation score if available
- **Track requirement-to-bug correlation:** If "verified" requirements have bugs, surface this
- **Don't make coverage percentage the KPI;** make it a diagnostic tool

**Detection:**
- Audit sample of "verified" requirements: do the tests actually test the requirement?
- Compare coverage claims to production defect rate
- Check for tests with zero or trivial assertions

**Phase to address:** Phase 3 (Dashboard) for display; establish norms early that coverage != verification

**Sources:**
- [HackerNoon: Misleading Test Coverage and How to Avoid False Confidence](https://hackernoon.com/misleading-test-coverage-and-how-to-avoid-false-confidence)
- [Qt: Why Code Coverage Metrics Can Be Misleading](https://www.qt.io/quality-assurance/blog/why-code-coverage-metrics-can-be-misleading-and-how-coco-code-coverage-tool-makes-them-meaningful)
- [ThinkingLabs: The Fallacy of the 100% Code Coverage](https://thinkinglabs.io/articles/2022/03/19/the-fallacy-of-the-100-code-coverage.html)

---

### Pitfall 4: Test Result Sync Race Conditions

**What goes wrong:** Dashboard shows stale or incorrect test results. A test passes in CI but dashboard shows failure (or vice versa). Results from different CI runs get interleaved incorrectly.

**Why it happens:**
- Django database transactions and Celery tasks race
- CI pushes results before transaction commits
- Multiple CI runs (different branches, reruns) write to same requirement status
- Database replicas serve stale reads

**Consequences:**
- PMs lose trust: "The dashboard said it passed but CI failed"
- Engineers dismiss dashboard as unreliable
- Debugging becomes harder (which result is real?)
- Audit trail becomes unreliable

**Warning signs:**
- Dashboard status doesn't match recent CI run
- "Refresh the page and it changes" reports
- Status flapping between pass/fail without code changes
- Results from old CI runs appearing after new runs

**Prevention:**
- **Use `transaction.on_commit()`** for any task that writes test results
- **Idempotent result updates:** Include CI run ID, timestamp; only update if newer
- **Optimistic locking:** Detect and reject stale writes
- **Event sourcing for results:** Store all results, derive current status
- **Reconciliation job:** Periodically validate dashboard matches source of truth (CI)

**Detection:**
- Compare dashboard status to CI API for same commit
- Log write timestamps and detect out-of-order writes
- Alert on results that flip without corresponding CI activity

**Phase to address:** Phase 3 (Dashboard/CI Integration). Design the result ingestion carefully from the start.

**Sources:**
- [Adam Johnson: Common Celery Issues on Django Projects](https://adamj.eu/tech/2020/02/03/common-celery-issues-on-django-projects/)
- [TestDriven: Working with Celery and Django Database Transactions](https://testdriven.io/blog/celery-database-transactions/)
- [Vinta Software: Advanced Celery for Django](https://www.vintasoftware.com/blog/guide-django-celery-tasks)

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or user friction.

---

### Pitfall 5: Manual Traceability Becomes a Burden

**What goes wrong:** Developers must manually add `@spec("SPEC-XXX")` decorators to every test. This becomes tedious, error-prone, and gets skipped. Traceability degrades over time as new tests are added without decorators.

**Why it happens:**
- Extra step in test-writing workflow
- No enforcement mechanism
- Developers don't know which spec ID to use
- Copy-paste of wrong spec IDs

**Consequences:**
- Incomplete traceability (many tests unlinked)
- Wrong spec IDs (test claims to verify requirement it doesn't)
- Developer resentment ("busywork")
- Coverage numbers meaningless if half the tests aren't linked

**Warning signs:**
- New tests consistently missing decorators
- Decorators added in bulk "traceability cleanup" sprints
- Same spec ID used everywhere (copy-paste)
- Developers asking "what spec ID should I use?"

**Prevention:**
- **Pre-commit hook or CI check:** Fail if test lacks spec decorator
- **Autocomplete/IDE integration:** Help developers find the right spec
- **Spec suggestion:** Analyze test name/path to suggest likely specs
- **Make it required from day one;** retrofitting is harder
- **Keep spec IDs visible:** In PR template, linked from code

**Detection:**
- Count tests without decorators over time (should be zero or trending down)
- Audit decorator accuracy: does the test actually relate to the spec?

**Phase to address:** Phase 2 (pytest integration). Make the decorator ergonomic and enforced.

**Sources:**
- [Springer: Requirements Traceability Literature Review](https://link.springer.com/article/10.1007/s00766-023-00412-z) - "inadequate maintenance of trace information"
- [Sodius Willert: Requirements Traceability](https://www.sodiuswillert.com/en/blog/implementing-requirements-traceability-in-systems-software-engineering)

---

### Pitfall 6: PM-Engineer Workflow Mismatch

**What goes wrong:** PMs write specs in a format engineers can't use; engineers annotate tests in a way PMs can't understand. The system becomes two disconnected worlds with a dashboard in between.

**Why it happens:**
- PMs think in features and user stories; engineers think in functions and modules
- Spec granularity doesn't match test granularity
- PMs don't review test-spec links; engineers don't review spec changes
- Tool doesn't bridge the vocabulary gap

**Consequences:**
- Specs too high-level to trace meaningfully
- Tests too low-level to map to business requirements
- Dashboard shows links but nobody trusts them
- "We have traceability" but no real communication

**Warning signs:**
- PMs never look at the dashboard
- Engineers add decorators without reading the spec
- Spec IDs are "just for compliance"
- Disconnect: PM says "feature X is incomplete" but dashboard shows 100%

**Prevention:**
- **Collaborative spec writing:** Engineers and PMs write/review specs together
- **Match granularity:** Specs should be testable; tests should map to business value
- **Spec templates:** Guide PMs to write at the right level
- **Dashboard shows context both roles understand:** Not just IDs but feature names, descriptions
- **Regular calibration:** PM and engineer review a few links together monthly

**Detection:**
- Survey: Do PMs use the dashboard? Do they trust it?
- Check: Can an engineer explain what a random spec ID means?
- Measure: Correlation between PM satisfaction and coverage numbers

**Phase to address:** Phase 1 (Schema/Format design) and Phase 4 (Collaborative workflow)

**Sources:**
- [Atlassian: Are your project management tools causing friction?](https://www.atlassian.com/blog/jira/are-your-project-management-tools-causing-friction)
- [Aha: PM and Engineers Collaboration](https://www.aha.io/roadmapping/guide/product-management/work-with-engineers)

---

### Pitfall 7: Merge Conflict Hell with Markdown Specs

**What goes wrong:** Multiple people edit specs simultaneously. Git merge conflicts in markdown become frequent and messy. Spec editing becomes a bottleneck.

**Why it happens:**
- PMs not familiar with Git conflict resolution
- Large monolithic spec files (one file = many conflicts)
- No branching workflow for spec changes
- Simultaneous editing without coordination

**Consequences:**
- Corrupted specs from bad merge resolution
- Spec editing becomes PM-blocking (needs engineer to resolve conflicts)
- People avoid updating specs to avoid conflicts
- Specs diverge across branches

**Warning signs:**
- Spec files with merge conflict markers committed
- PMs asking engineers to "fix the spec merge"
- Long-lived spec branches that can't be merged
- One person becomes the "spec gatekeeper"

**Prevention:**
- **Granular spec files:** One requirement per file, or small coherent groups
- **Clear ownership:** Assign spec sections to specific authors
- **Branching workflow:** Spec changes go through PRs with review
- **Edit coordination:** Use GitHub/GitLab assignment to signal "I'm editing this"
- **User-friendly conflict resolution:** Consider tooling that helps PMs resolve conflicts
- **Web-based editing option:** Dashboard allows editing with auto-commit (for simple changes)

**Detection:**
- Git history: frequency of merge commits in spec files
- Search for conflict markers in committed files
- Count spec PRs that needed force-push or rebase

**Phase to address:** Phase 1 (File structure) and Phase 4 (Collaborative workflow)

**Sources:**
- [Atlassian: Git Merge Conflicts](https://www.atlassian.com/git/tutorials/using-branches/merge-conflicts)
- [Markdown Best Practices](https://www.markdownlang.com/advanced/best-practices.html)

---

### Pitfall 8: Dashboard Performance Degradation

**What goes wrong:** Dashboard becomes slow as test history accumulates. Page loads take seconds, then tens of seconds. Users stop using it.

**Why it happens:**
- COUNT(*) queries for pagination with millions of test results
- Loading full history when only recent results needed
- No caching strategy
- ORM generates inefficient queries (N+1 problems)

**Consequences:**
- Users abandon the dashboard
- Traceability system becomes "that slow thing nobody uses"
- Server costs spike
- Reports timeout during critical demos

**Warning signs:**
- Page load time increasing week over week
- Database CPU spikes when dashboard accessed
- Users report "it worked yesterday but now it's slow"
- Queries in slow query log

**Prevention:**
- **Cursor-based pagination** (not offset-based) for large result sets
- **Denormalize current status:** Store latest result separately from history
- **Aggressive caching:** Cache requirement status, invalidate on new results
- **Query optimization:** Use `select_related`, `prefetch_related`, raw SQL where needed
- **Archival strategy:** Move old results to cold storage, keep recent results hot
- **Load testing:** Test with 10x expected data volume before launch

**Detection:**
- Monitor page load times (p50, p95, p99)
- Alert on query duration > threshold
- Track database size growth rate

**Phase to address:** Phase 3 (Dashboard). Design for scale from the start; hard to retrofit.

**Sources:**
- [Haki Benita: Optimizing the Django Admin Paginator](https://hakibenita.com/optimizing-the-django-admin-paginator)
- [LoadForge: Django Performance Best Practices](https://loadforge.com/guides/the-ultimate-guide-to-django-performance-best-practices-for-scaling-and-optimization)

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable with moderate effort.

---

### Pitfall 9: Markdown Flavor Inconsistency

**What goes wrong:** Specs use different markdown flavors or features. Some render correctly in GitHub, some in VS Code, some break in the dashboard. Tables, code blocks, and links behave differently.

**Prevention:**
- Standardize on **GitHub Flavored Markdown (GFM)**
- Use markdownlint in CI to enforce consistency
- Document which features are supported
- Test rendering in all target environments

**Phase to address:** Phase 1 (Spec format definition)

---

### Pitfall 10: Pytest Fixture Magic Interferes with Decorators

**What goes wrong:** Pytest's fixture injection doesn't play well with custom decorators. IDE can't navigate from decorator to spec. Type checkers complain. Refactoring breaks links.

**Prevention:**
- Use `pytest.mark` for spec linkage (native, well-supported)
- Provide IDE plugin or stubs for autocomplete
- Document the pattern clearly
- Test decorator behavior in CI

**Phase to address:** Phase 2 (pytest integration)

**Sources:**
- [pytest documentation: Working with custom markers](https://docs.pytest.org/en/7.1.x/example/markers.html)
- [GitHub Discussion: Why doesn't pytest use decorators?](https://github.com/pytest-dev/pytest/discussions/10783)

---

### Pitfall 11: Orphan Specs and Tests

**What goes wrong:** Requirements get deleted but tests still reference them. Tests get deleted but specs still expect them. Dashboard shows 404s or "no tests" for valid specs.

**Prevention:**
- **Bi-directional link validation in CI:** Fail build if test references nonexistent spec
- **Dashboard surfaces orphans:** Show specs with no tests, tests with invalid specs
- **Archive, don't delete:** Mark specs as deprecated rather than removing

**Phase to address:** Phase 2 (Link validation), Phase 3 (Dashboard orphan view)

---

### Pitfall 12: Over-Granular or Under-Granular Specs

**What goes wrong:**
- Over-granular: 500 specs for a simple feature. Every test links to something but it's meaningless.
- Under-granular: 10 specs total. Every test links to "REQ-MAIN" which covers everything.

**Prevention:**
- Define granularity guidelines: "A spec should be verifiable by 1-5 tests"
- Review spec structure periodically
- Dashboard metrics on tests-per-spec distribution (flag outliers)

**Phase to address:** Phase 1 (Spec writing guidelines), ongoing governance

---

## Phase-Specific Warnings

| Phase | Primary Pitfall Risk | Mitigation |
|-------|---------------------|------------|
| Phase 1: Schema & Format | Hierarchical ID fragility, Markdown flavor inconsistency, Granularity mismatch | Design immutable IDs, standardize on GFM, define granularity guidelines |
| Phase 2: Parsing & Linking | Manual traceability burden, Orphan detection gaps | Enforce decorators in CI, build bidirectional validation |
| Phase 3: Dashboard & CI | False confidence metrics, Race conditions, Performance degradation | Design for honest reporting, use transaction.on_commit, plan for scale |
| Phase 4: Collaboration | PM-Engineer mismatch, Merge conflicts | Enable web editing, granular files, collaborative spec review |
| Ongoing Operations | Specification drift | Automated drift detection, regular calibration reviews |

---

## Pre-Implementation Checklist

Before building, validate these decisions:

- [ ] **ID scheme:** Are IDs immutable and position-independent?
- [ ] **Granularity:** Are specs at a testable level?
- [ ] **File structure:** Are specs granular enough to avoid merge conflicts?
- [ ] **Enforcement:** Will CI fail on missing/invalid decorators?
- [ ] **Dashboard honesty:** Will metrics distinguish "linked" from "verified"?
- [ ] **Scale plan:** How will dashboard perform with 100K test results?
- [ ] **Sync reliability:** How will race conditions be prevented?
- [ ] **Drift detection:** How will spec-code drift be surfaced?

---

## Sources Summary

**Requirements Traceability:**
- [Springer: Requirements Traceability Literature Review](https://link.springer.com/article/10.1007/s00766-023-00412-z)
- [Sodius Willert: Requirements Traceability](https://www.sodiuswillert.com/en/blog/implementing-requirements-traceability-in-systems-software-engineering)
- [Perforce: Requirements Traceability Matrix](https://www.perforce.com/resources/alm/requirements-traceability-matrix)

**Documentation and Drift:**
- [DocsAlot: Documentation Rots](https://docsalot.dev/blog/documentation-rots-heres-how-to-stop-it)
- [Gaudion: Documentation Drift](https://gaudion.dev/blog/documentation-drift)

**Testing Metrics:**
- [HackerNoon: Misleading Test Coverage](https://hackernoon.com/misleading-test-coverage-and-how-to-avoid-false-confidence)
- [ThinkingLabs: Fallacy of 100% Coverage](https://thinkinglabs.io/articles/2022/03/19/the-fallacy-of-the-100-code-coverage.html)

**Django Performance:**
- [Haki Benita: Django Admin Paginator](https://hakibenita.com/optimizing-the-django-admin-paginator)
- [Adam Johnson: Common Celery Issues](https://adamj.eu/tech/2020/02/03/common-celery-issues-on-django-projects/)

**Collaboration:**
- [Atlassian: Git Merge Conflicts](https://www.atlassian.com/git/tutorials/using-branches/merge-conflicts)
- [Aha: PM-Engineer Collaboration](https://www.aha.io/roadmapping/guide/product-management/work-with-engineers)
