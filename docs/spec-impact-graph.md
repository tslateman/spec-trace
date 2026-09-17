# Spec: Impact Graph

## Problem

Changes reach users before anyone understands the blast radius. Investigation
starts at the support ticket, not the diff. SpecTrace can analyze spec file
changes but has no code → requirement mapping, and no cross-project dependency
awareness.

## Goal

Before a change ships, know what it affects and what might break — across the
entire ecosystem, at module level.

## Success Criteria

- `spectrace specs impact --code <base> <head>` returns affected specs, tests,
  and cross-project dependents for any diff of the local repository
- `--project-roots name=path,...` with `--project-refs name=base..head,...`
  diffs several repositories, each across its own refs, since one ref rarely
  names the same commit in two repositories
- Cross-project edges (Lore → Praxis, Lore → Geordi, etc.) are tracked and
  diffed like contracts
- Risk score accounts for code changes, not just spec file changes
- CI gate runs on every PR; high-risk changes require explicit acknowledgment
- Coverage: all five ecosystem projects (Lore, Praxis, Geordi, SpecTrace,
  fleets)

## Scope

### In scope

- Code module → requirement mapping via annotations and git history inference
- Cross-project contract discovery and change detection (OpenAPI-style)
- Extension of existing `spectrace specs impact` to accept code diffs
- Risk scoring that incorporates code-side blast radius
- CLI output suitable for CI (exit codes, markdown PR comments)
- Informed-consent gate (warn, don't block) with path to hard gate on high risk

### Out of scope

- Production telemetry or runtime tracing
- Automated rollback
- Function-level granularity (module-level is the unit)
- Auto-remediation or fix suggestions

## Approach

### Three mapping sources, one graph

1. **Code annotations** — `spectrace-map.yaml` at each project root maps
   modules to requirement IDs. One file per project, language-agnostic.
   Authoritative source for code → requirement edges.

   ```yaml
   # spectrace-map.yaml
   project: praxis
   modules:
     src/praxis/synthesis.py:
       requirements: [REQ-SYNTH-001, REQ-CONTEXT-002]
     src/praxis/lore.py:
       requirements: [REQ-LORE-READ-001]
     src/praxis/spectrace.py:
       requirements: [REQ-PRX-004]
       depends_on:
         - spectrace:db/requirements_requirement
         - spectrace:enum/requirements_requirement.status
   ```

   Graph nodes carry the project their map declares, so `praxis:tests/conftest.py`
   and `spectrace:tests/conftest.py` are two nodes, and a change to one project's
   module never reaches the other project's requirements.

   A module's optional `depends_on` list names the surfaces it reads from other
   projects, each as `{provider}:{surface}`: the same node id a provider's
   contract edge starts from. Each entry becomes a dependency edge
   (`source: "dependency"`, weight 1.0) from the module node to the provider's
   surface node, so a change to `spectrace:spectrace-map.yaml` walks to
   `praxis:src/praxis/impact.py` and reports Praxis as an affected project.
   `map_validate` rejects an entry that is not a string or lacks the
   `project:surface` shape. Readers that predate the key ignore it.

   A surface reachable from a diff is one whose name is a file path in the
   provider's repo, such as `spectrace-map.yaml` or `flows/example-api-check.yaml`.
   A `db/` or `enum/` surface names a table or column no changed file maps to
   yet, so declaring it records the dependency without making it walkable.

2. **Git inference** — correlate files that change alongside spec changes over
   commit history. Three co-occurrences within 30 days to trust an edge (Rule
   of Three). Inferred edges carry `source: "git-inferred"` and decay after 90
   days without reinforcement. Annotated edges carry `source: "annotated"`.

3. **Cross-project contracts** — each project generates a
   `contract.snapshot.json` describing its public surfaces (data formats, CLI
   args, file schemas). Diff snapshots between refs to detect breaking changes
   and surface affected dependents. A contract edge runs from
   `{project}:{surface}` to `{surface}`; dependency edges from other projects'
   maps end at the same `{project}:{surface}` node.

   ```json
   {
     "project": "lore",
     "version": "1.0",
     "surfaces": {
       "journal/decisions": {
         "format": "jsonl",
         "fields": [
           "id",
           "timestamp",
           "decision",
           "rationale",
           "outcome",
           "tags"
         ],
         "required": ["id", "timestamp", "decision"]
       },
       "cli/lore-decide": {
         "format": "cli",
         "args": ["--decision", "--rationale", "--tags"]
       }
     }
   }
   ```

### Builds on existing SpecTrace infrastructure

- Extends `ImpactAnalyzer` service with code-side expansion
- Reuses `DependencyValidator` for transitive chain computation
- Reuses risk scoring formula, adds code-change weight factors
- Reuses output formatters (text, JSON, markdown)
- Populates Lore's `registry/data/relationships.yaml` with discovered edges

### CI integration

- `spectrace specs impact --code <base> <head>` — CLI command; multi-repo
  runs pair `--project-roots` with `--project-refs`
- `cross_project_edges` counts the traversed edges whose two nodes carry
  different project prefixes; only dependency edges qualify today
- Exit code 0 (low/medium) or 1 (high/critical) for gate behavior
- `--format markdown` for PR comment output
- The hard gate arrives by dropping `continue-on-error` from the CI step;
  the CLI carries no flag for it

### Bootstrap

1. Run git inference across all five projects. Seed the graph with candidate
   edges (`source: "git-inferred"`).
2. Generate `contract.snapshot.json` for each project. Store cross-project
   dependency edges.
3. `spectrace-map.yaml` starts empty per project. Confirmed inferred edges
   upgrade to annotated as you review them. Unconfirmed edges decay after 90
   days.
