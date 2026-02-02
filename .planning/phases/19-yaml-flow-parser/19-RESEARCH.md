# Phase 19: YAML Flow Parser - Research

**Researched:** 2026-02-02
**Domain:** YAML parsing, schema validation, Django management commands
**Confidence:** HIGH

## Summary

This phase adds YAML-based flow definitions as an alternative to the existing Python code-defined flows. The codebase already has extensive patterns for YAML parsing (OpenSLO), markdown parsing (SpecParser), and flow execution (VerificationFlow models). The implementation should follow established patterns while adding schema validation using dataclasses.

The existing `VerificationFlow`, `VerificationFlowRun`, and `VerificationFlowStep` models already support the required structure. The YAML parser will parse flow files into the same `FlowDef` and `FlowStepDef` dataclasses used by code-defined flows, enabling a unified execution path.

**Primary recommendation:** Use PyYAML (already in dependencies) with dataclass-based validation. Follow the OpenSLOParser pattern for file parsing, the SpecParser pattern for directory handling, and sync flows using the existing `sync_flows_to_db()` mechanism.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | 6.0+ | YAML parsing | Already in pyproject.toml, used by OpenSLOParser |
| dataclasses | stdlib | Schema validation | Consistent with FlowDef, FlowStepDef, VerificationCheck patterns |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| msgspec | 0.19+ | Fast validation | Already in deps, use for API schemas only (not file parsing) |
| python-frontmatter | 1.1+ | YAML frontmatter | Already used by SpecParser, not needed for pure YAML |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclasses | msgspec.Struct | msgspec is faster but dataclasses match existing FlowDef pattern |
| dataclasses | Pydantic | Pydantic is heavier, not in deps, dataclasses already work |
| yaml.safe_load | ruamel.yaml | ruamel preserves formatting for round-trip, not needed for read-only |

**Installation:**
```bash
# No new packages needed - PyYAML already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/
├── requirements/
│   ├── flows/
│   │   ├── __init__.py
│   │   ├── definitions.py      # Existing: FlowDef, FlowStepDef, REGISTERED_FLOWS
│   │   ├── engine.py           # Existing: SequentialFlowEngine
│   │   ├── sync.py             # Existing: sync_flows_to_db()
│   │   ├── parser.py           # NEW: FlowParser class
│   │   └── handlers/
│   │       └── ...
│   └── management/
│       └── commands/
│           └── parse_flows.py  # NEW: Management command
flows/                          # NEW: YAML flow files directory (project root)
├── linear-connection.yaml
└── example-flow.yaml
```

### Pattern 1: Parser Class (Follow OpenSLOParser)
**What:** Dedicated parser class with parse_file() and parse_directory() methods
**When to use:** Always for file-based parsing
**Example:**
```python
# Source: Based on spectrace/requirements/openslo.py pattern
class FlowParser:
    """Parser for verification flow YAML files."""

    FILE_PATTERNS = ('**/*.yaml', '**/*.yml')

    def parse_file(self, file_path: Path) -> FlowDef | None:
        """Parse a single flow YAML file."""
        with open(file_path) as f:
            doc = yaml.safe_load(f)

        if not doc:
            return None

        return self._parse_flow_doc(doc, file_path)

    def _parse_flow_doc(self, doc: dict, file_path: Path) -> FlowDef:
        """Convert YAML dict to FlowDef dataclass."""
        steps = [
            FlowStepDef(
                name=step['name'],
                handler=step['handler'],
                display_name=step.get('display_name', step['name']),
                description=step.get('description', ''),
            )
            for step in doc.get('steps', [])
        ]

        return FlowDef(
            name=doc['id'],
            display_name=doc.get('title', doc['id']),
            description=doc.get('description', ''),
            steps=steps,
            version=doc.get('version', 1),
        )

    def parse_directory(self, flows_dir: Path) -> list[FlowDef]:
        """Parse all YAML files in directory."""
        flows = []
        for pattern in self.FILE_PATTERNS:
            for yaml_file in sorted(flows_dir.glob(pattern)):
                try:
                    flow = self.parse_file(yaml_file)
                    if flow:
                        flows.append(flow)
                except Exception as e:
                    print(f"Warning: Failed to parse {yaml_file}: {e}")
        return flows
```

### Pattern 2: Management Command (Follow BaseImportCommand)
**What:** Django management command using existing base class
**When to use:** For CLI-driven imports
**Example:**
```python
# Source: Based on spectrace/requirements/management/commands/import_slos.py
class Command(BaseImportCommand):
    help = 'Parse flow definitions from YAML files'
    path_argument_name = 'flows_dir'
    path_argument_help = 'Path to directory containing flow YAML files'

    def do_import(self, path: Path, options: dict):
        parser = FlowParser()
        flows = parser.parse_directory(path)

        if not flows:
            self.stdout.write(self.style.WARNING("No flow files found"))
            return

        if options['dry_run']:
            for flow in flows:
                self.stdout.write(f"  - {flow.name}: {len(flow.steps)} steps")
            return

        # Sync to database using existing mechanism
        from requirements.flows.sync import sync_yaml_flows_to_db
        result = sync_yaml_flows_to_db(flows, clear_existing=options['clear'])
        self.stdout.write(self.style.SUCCESS(f"Synced {len(result)} flows"))
```

### Pattern 3: Unified Registry (Extend REGISTERED_FLOWS)
**What:** Merge YAML-parsed flows with code-defined flows
**When to use:** When both sources need to coexist
**Example:**
```python
# In flows/definitions.py
def get_all_flows() -> list[FlowDef]:
    """Get all flows from both code and YAML sources."""
    all_flows = list(REGISTERED_FLOWS)  # Code-defined

    # Add YAML-defined flows
    from requirements.flows.parser import FlowParser
    from django.conf import settings

    flows_dir = Path(settings.BASE_DIR).parent / 'flows'
    if flows_dir.exists():
        parser = FlowParser()
        yaml_flows = parser.parse_directory(flows_dir)
        all_flows.extend(yaml_flows)

    return all_flows
```

### Anti-Patterns to Avoid
- **Parsing in sync.py:** Keep parsing separate from sync; sync only operates on FlowDef objects
- **Using msgspec for file parsing:** Reserve msgspec for API request/response validation; use yaml.safe_load + dataclasses for file parsing
- **Hardcoding flows directory:** Use settings or command argument, not hardcoded path
- **Ignoring existing FlowDef:** Do NOT create a parallel data structure; reuse FlowDef/FlowStepDef

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom tokenizer | `yaml.safe_load()` | Security (safe_load prevents code execution), well-tested |
| Schema validation | Manual dict checking | dataclass with type hints | Automatic validation, IDE support |
| Flow sync | New ORM logic | `sync_flows_to_db()` pattern | Already handles update_or_create, versioning |
| Command structure | Raw BaseCommand | `BaseImportCommand` | --dry-run, --clear, path validation already implemented |
| Step execution | New engine | `SequentialFlowEngine` | Already handles context passing, early-exit, error recording |

**Key insight:** The entire flow execution pipeline already exists. This phase only adds a new source for FlowDef objects (YAML files instead of Python code).

## Common Pitfalls

### Pitfall 1: Breaking Code-Defined Flows
**What goes wrong:** YAML parser replaces REGISTERED_FLOWS entirely
**Why it happens:** Assumption that YAML replaces code
**How to avoid:** Merge sources: YAML flows supplement, not replace code-defined flows
**Warning signs:** LINEAR_CONNECTION_FLOW stops working after YAML parser added

### Pitfall 2: Inconsistent Handler Paths
**What goes wrong:** YAML files use different handler path format than code
**Why it happens:** No clear documentation of handler path format
**How to avoid:** Validate handler paths on parse; document format in YAML schema
**Warning signs:** "Handler error: ImportError" at runtime

### Pitfall 3: Missing Source Tracking
**What goes wrong:** Can't tell if a VerificationFlow came from YAML or code
**Why it happens:** Not storing source_file in the database
**How to avoid:** Add source_file tracking to VerificationFlow model or flow metadata
**Warning signs:** Unable to debug which file defined a broken flow

### Pitfall 4: Version Mismatch on Re-sync
**What goes wrong:** Database has version 2, YAML has version 1, gets overwritten
**Why it happens:** YAML files don't require version bumps
**How to avoid:** Either enforce version in YAML or use content-based change detection
**Warning signs:** Flow behavior changes unexpectedly after unrelated edit

## Code Examples

Verified patterns from the existing codebase:

### YAML Schema (Recommended)
```yaml
# flows/example-flow.yaml
# FLOW-02: id, title, steps[], requirement links
# FLOW-03: Each step has name, type, config

id: example-api-check
title: Example API Connection Check
description: Verify API connectivity with sequential checks
version: 1

# Requirement links (optional)
requirements:
  - REQ-API-001
  - REQ-API-002

steps:
  - name: config
    type: api_call  # or: assertion, wait
    display_name: Configuration Check
    description: Validate API configuration
    handler: requirements.flows.handlers.example.check_configuration
    config:
      required_keys:
        - API_KEY
        - API_URL

  - name: auth
    type: api_call
    display_name: Authentication Check
    handler: requirements.flows.handlers.example.check_authentication
    config:
      endpoint: /api/auth/verify

  - name: permissions
    type: assertion
    display_name: Permissions Check
    handler: requirements.flows.handlers.example.check_permissions
```

### Dataclass Schema (Extends Existing)
```python
# Source: spectrace/requirements/flows/definitions.py (extended)
from dataclasses import dataclass, field
from typing import Literal

StepType = Literal['api_call', 'assertion', 'wait']

@dataclass
class FlowStepDef:
    """Definition of a single step within a verification flow."""
    name: str
    handler: str
    display_name: str
    description: str = ""
    type: StepType = 'api_call'  # NEW: step type (FLOW-03)
    config: dict = field(default_factory=dict)  # NEW: step config (FLOW-03)


@dataclass
class FlowDef:
    """Definition of a complete verification flow."""
    name: str
    display_name: str
    description: str
    steps: list[FlowStepDef] = field(default_factory=list)
    version: int = 1
    requirements: list[str] = field(default_factory=list)  # NEW: requirement links (FLOW-02)
    source_file: str = ""  # NEW: track YAML source
```

### Parser Validation
```python
# Source: Based on spectrace/requirements/openslo.py validation pattern
def _validate_flow_doc(self, doc: dict, file_path: Path) -> list[str]:
    """Validate flow document structure, return list of errors."""
    errors = []

    # Required fields (FLOW-02)
    if 'id' not in doc:
        errors.append(f"{file_path}: Missing required 'id' field")

    if 'steps' not in doc or not isinstance(doc.get('steps'), list):
        errors.append(f"{file_path}: Missing or invalid 'steps' field")

    # Validate each step (FLOW-03)
    for i, step in enumerate(doc.get('steps', [])):
        if 'name' not in step:
            errors.append(f"{file_path}: Step {i} missing 'name'")
        if 'handler' not in step:
            errors.append(f"{file_path}: Step {i} missing 'handler'")

        step_type = step.get('type', 'api_call')
        if step_type not in ('api_call', 'assertion', 'wait'):
            errors.append(f"{file_path}: Step {i} invalid type '{step_type}'")

    return errors
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Code-only flow definitions | Code + YAML sources | This phase | YAML enables non-developer flow authoring |
| Implicit handler discovery | Explicit handler paths | Existing | Handler must be importable dotted path |

**Deprecated/outdated:**
- None identified - flow system is new

## Open Questions

Things that couldn't be fully resolved:

1. **flows/ directory location**
   - What we know: SpecParser uses `specs/`, OpenSLO uses arbitrary path via command arg
   - What's unclear: Should flows/ be at project root or inside spectrace/?
   - Recommendation: Project root (`flows/`) matching `specs/` convention; pass via command arg

2. **Requirement linking mechanism**
   - What we know: Requirements exist in DB with external_id, YAML can reference them
   - What's unclear: Should we validate requirement IDs exist on parse or sync?
   - Recommendation: Validate on sync (like OpenSLO does with requirements), warn on missing

3. **Admin UI writes YAML files (prior decision)**
   - What we know: Decision says "Admin UI writes directly to YAML files"
   - What's unclear: Is this in scope for Phase 19 or future phase?
   - Recommendation: Phase 19 focuses on parser/sync; Admin YAML editing is separate phase

## Sources

### Primary (HIGH confidence)
- `/Users/tslater/dev/spec-trace/spectrace/requirements/flows/definitions.py` - Existing FlowDef, FlowStepDef dataclasses
- `/Users/tslater/dev/spec-trace/spectrace/requirements/flows/engine.py` - SequentialFlowEngine
- `/Users/tslater/dev/spec-trace/spectrace/requirements/flows/sync.py` - sync_flows_to_db pattern
- `/Users/tslater/dev/spec-trace/spectrace/requirements/openslo.py` - OpenSLOParser YAML parsing pattern
- `/Users/tslater/dev/spec-trace/spectrace/requirements/parser.py` - SpecParser directory parsing pattern
- `/Users/tslater/dev/spec-trace/spectrace/requirements/management/commands/base.py` - BaseImportCommand
- `/Users/tslater/dev/spec-trace/spectrace/requirements/models.py` - VerificationFlow, VerificationFlowRun, VerificationFlowStep
- `/Users/tslater/dev/spec-trace/pyproject.toml` - PyYAML 6.0+, msgspec 0.19+ dependencies

### Secondary (MEDIUM confidence)
- Existing test patterns in `/Users/tslater/dev/spec-trace/spectrace/requirements/tests/test_flows.py`

### Tertiary (LOW confidence)
- None - all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in pyproject.toml
- Architecture: HIGH - Patterns directly copied from existing OpenSLOParser, SpecParser
- Pitfalls: MEDIUM - Inferred from codebase structure, no production experience

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (stable domain, 30 days)
