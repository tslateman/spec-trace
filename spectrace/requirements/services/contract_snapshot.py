"""Contract snapshots — introspect project data surfaces for change detection."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ContractChange:
    """A detected change between two contract snapshots."""

    surface: str
    change_type: str  # "field_removed", "field_added", "surface_removed", "surface_added"
    breaking: bool
    field: str = ""
    detail: str = ""

    def to_edges(self) -> list:
        """Convert breaking changes to high-weight contract edges."""
        from .impact_graph import EdgeSource, GraphEdge

        if not self.breaking:
            return []

        return [
            GraphEdge(
                source_id=self.surface,
                target_id=f"contract:{self.surface}:{self.field or 'surface'}",
                source=EdgeSource.CONTRACT,
                weight=0.8 if self.field else 1.0,
                project="",
            )
        ]


class ContractSnapshot:
    """Snapshot of a project's public data surfaces."""

    def __init__(self, project: str, version: str, surfaces: dict):
        self.project = project
        self.version = version
        self.surfaces = surfaces  # surface_name -> {format, fields, required, args, ...}

    @classmethod
    def generate(cls, project_root: Path, project_name: str) -> "ContractSnapshot":
        """Introspect data files to produce a contract snapshot.

        Scans for:
        - JSONL files: extracts field names from first 10 records
        - YAML files: extracts top-level and nested keys
        - CLI entry points: extracts from pyproject.toml [project.scripts]
        """
        surfaces: dict[str, dict] = {}

        # Scan for JSONL data files
        for jsonl_file in project_root.rglob("*.jsonl"):
            # Skip hidden dirs and node_modules
            if any(part.startswith(".") for part in jsonl_file.parts):
                continue

            rel_path = str(jsonl_file.relative_to(project_root))
            fields = _extract_jsonl_fields(jsonl_file)
            if fields:
                surfaces[rel_path] = {
                    "format": "jsonl",
                    "fields": sorted(fields),
                }

        # Scan for YAML data files
        for yaml_ext in ("*.yaml", "*.yml"):
            for yaml_file in project_root.rglob(yaml_ext):
                if any(part.startswith(".") for part in yaml_file.parts):
                    continue

                rel_path = str(yaml_file.relative_to(project_root))
                keys = _extract_yaml_keys(yaml_file)
                if keys:
                    surfaces[rel_path] = {
                        "format": "yaml",
                        "fields": sorted(keys),
                    }

        # Extract CLI entry points from pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            cli_surfaces = _extract_cli_surfaces(pyproject)
            surfaces.update(cli_surfaces)

        return cls(
            project=project_name,
            version="1.0",
            surfaces=surfaces,
        )

    def save(self, path: Path) -> None:
        """Save snapshot to JSON file."""
        data = {
            "project": self.project,
            "version": self.version,
            "surfaces": self.surfaces,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path: Path) -> "ContractSnapshot":
        """Load snapshot from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(
            project=data.get("project", ""),
            version=data.get("version", "1.0"),
            surfaces=data.get("surfaces", {}),
        )


class ContractDiffer:
    """Diff two contract snapshots to detect changes."""

    def diff(self, old: ContractSnapshot, new: ContractSnapshot) -> list[ContractChange]:
        """Detect changes between old and new snapshots.

        Change types:
        - surface_removed: breaking (a whole data surface disappeared)
        - surface_added: non-breaking
        - field_removed: breaking (consumers may depend on the field)
        - field_added: non-breaking
        """
        changes: list[ContractChange] = []

        old_surfaces = set(old.surfaces.keys())
        new_surfaces = set(new.surfaces.keys())

        # Removed surfaces (breaking)
        for surface in sorted(old_surfaces - new_surfaces):
            changes.append(
                ContractChange(
                    surface=surface,
                    change_type="surface_removed",
                    breaking=True,
                    detail=f"Surface '{surface}' was removed",
                )
            )

        # Added surfaces (non-breaking)
        for surface in sorted(new_surfaces - old_surfaces):
            changes.append(
                ContractChange(
                    surface=surface,
                    change_type="surface_added",
                    breaking=False,
                    detail=f"Surface '{surface}' was added",
                )
            )

        # Shared surfaces — compare fields
        for surface in sorted(old_surfaces & new_surfaces):
            old_fields = set(old.surfaces[surface].get("fields", []))
            new_fields = set(new.surfaces[surface].get("fields", []))

            for field_name in sorted(old_fields - new_fields):
                changes.append(
                    ContractChange(
                        surface=surface,
                        change_type="field_removed",
                        breaking=True,
                        field=field_name,
                        detail=f"Field '{field_name}' removed from '{surface}'",
                    )
                )

            for field_name in sorted(new_fields - old_fields):
                changes.append(
                    ContractChange(
                        surface=surface,
                        change_type="field_added",
                        breaking=False,
                        field=field_name,
                        detail=f"Field '{field_name}' added to '{surface}'",
                    )
                )

        return changes


def _extract_jsonl_fields(path: Path, max_records: int = 10) -> list[str]:
    """Extract field names from first N records of a JSONL file."""
    fields: set[str] = set()
    try:
        with open(path) as f:
            for i, line in enumerate(f):
                if i >= max_records:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        fields.update(record.keys())
                except json.JSONDecodeError:
                    continue
    except (OSError, UnicodeDecodeError):
        pass
    return sorted(fields)


def _extract_yaml_keys(path: Path) -> list[str]:
    """Extract top-level keys from a YAML file."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return sorted(data.keys())
    except (yaml.YAMLError, OSError):
        pass
    return []


def _extract_cli_surfaces(pyproject_path: Path) -> dict:
    """Extract CLI entry points from pyproject.toml."""
    surfaces = {}
    try:
        content = pyproject_path.read_text()
        # Simple TOML parsing for [project.scripts] section
        # We use a basic approach since tomllib isn't always available
        in_scripts = False
        for line in content.split("\n"):
            line = line.strip()
            if line == "[project.scripts]":
                in_scripts = True
                continue
            if in_scripts:
                if line.startswith("["):
                    break
                if "=" in line:
                    name = line.split("=")[0].strip()
                    entry = line.split("=")[1].strip().strip('"').strip("'")
                    surfaces[f"cli/{name}"] = {
                        "format": "cli",
                        "entry_point": entry,
                    }
    except OSError:
        pass
    return surfaces
