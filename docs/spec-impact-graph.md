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

- `spectrace impact --code <base>..<head>` returns affected specs, tests, and
  cross-project dependents for any diff
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
   ```

   Graph nodes carry the project their map declares, so `praxis:tests/conftest.py`
   and `spectrace:tests/conftest.py` are two nodes, and a change to one project's
   module never reaches the other project's requirements.

2. **Git inference** — correlate files that change alongside spec changes over
   commit history. Three co-occurrences within 30 days to trust an edge (Rule
   of Three). Inferred edges carry `source: "git-inferred"` and decay after 90
   days without reinforcement. Annotated edges carry `source: "annotated"`.

3. **Cross-project contracts** — each project generates a
   `contract.snapshot.json` describing its public surfaces (data formats, CLI
   args, file schemas). Diff snapshots between refs to detect breaking changes
   and surface affected dependents.

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

4. **Declared dependencies** — a module names the surfaces it reads from
   another project. The declaration sits beside the code that creates the
   coupling, in the map that project already owns.

   ```yaml
   # praxis/spectrace-map.yaml
   project: praxis
   modules:
     src/praxis/spectrace.py:
       requirements: [REQ-PRX-004]
       depends_on:
         - spectrace:db/requirements_requirement
         - spectrace:enum/requirements_requirement.risk_level
   ```

   Each entry names a project and one surface that project publishes. A
   declaration naming a loaded project that publishes no such surface raises
   `UnknownSurfaceError`; one that names no project raises
   `MalformedDependencyError`. A declaration whose provider was absent from the
   run is reported under "Dependencies Not Analysed" rather than dropped.

   Dependency edges run provider to consumer and are the only directed edges in
   the graph: a change to a SpecTrace table reaches the Praxis module that reads
   it, and a change to that Praxis module reports nothing in SpecTrace.

### Surfaces name what a consumer can depend on

`contract.snapshot.json` records four kinds of surface. A JSONL or YAML surface
is named after the file that holds it, so its node and that file's node are the
same node. The others name the file that defines them, and a contract edge
joins the two.

| Prefix  | Surface                                    | Defined by         |
| ------- | ------------------------------------------ | ------------------ |
| none    | `flows/linear-connection.yaml`             | the file itself    |
| `cli/`  | `cli/spectrace`                            | `pyproject.toml`   |
| `db/`   | `db/requirements_requirement`              | the model's module |
| `enum/` | `enum/requirements_requirement.risk_level` | the model's module |

Database surfaces come from the Django models whose source files live under the
project root. A consumer reading the database couples to column names and to the
stored strings behind a field's choices, so each becomes a surface a map can
name — renaming a choice value breaks a reader without changing a column.

### Builds on existing SpecTrace infrastructure

- Extends `ImpactAnalyzer` service with code-side expansion
- Reuses `DependencyValidator` for transitive chain computation
- Reuses risk scoring formula, adds code-change weight factors
- Reuses output formatters (text, JSON, markdown)
- Populates Lore's `registry/data/relationships.yaml` with discovered edges

### CI integration

- `spectrace impact --code <base>..<head>` — CLI command
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
