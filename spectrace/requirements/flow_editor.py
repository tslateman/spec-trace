"""Flow editor service for Admin UI YAML file management.

Provides functions to list, load, and save flow YAML files while preserving
comments and formatting. Used by the Admin UI to enable non-developer editing
of verification flows.
"""

from pathlib import Path

from django.conf import settings
from ruamel.yaml import YAML

from requirements.flows.definitions import FlowDef
from requirements.flows.parser import FlowParseError, YAMLFlowParser


class FlowEditorError(Exception):
    """Error in flow editor operations."""

    pass


# Flows directory at project root
FLOWS_DIR = Path(settings.BASE_DIR).parent / "flows"


def validate_flow_path(file_path: str) -> Path:
    """Validate and resolve a flow file path.

    Args:
        file_path: Relative path like 'linear-connection.yaml'

    Returns:
        Resolved absolute Path within FLOWS_DIR

    Raises:
        PermissionError: If path escapes FLOWS_DIR (path traversal)
        ValueError: If path doesn't end with .yaml or .yml
    """
    # Check extension first
    if not (file_path.endswith(".yaml") or file_path.endswith(".yml")):
        raise ValueError(f"File must have .yaml or .yml extension: {file_path}")

    # Resolve against FLOWS_DIR
    resolved = (FLOWS_DIR / file_path).resolve()

    # Security: ensure path is within FLOWS_DIR
    try:
        resolved.relative_to(FLOWS_DIR.resolve())
    except ValueError:
        raise PermissionError(f"Path traversal blocked: {file_path}")

    return resolved


def get_flow_files() -> list[dict]:
    """List all flow YAML files with metadata.

    Scans FLOWS_DIR for .yaml and .yml files, parsing each to extract
    metadata. Invalid files are included with error messages.

    Returns:
        List of dicts with keys:
        - path: Relative path from FLOWS_DIR
        - name: Flow ID (if valid)
        - title: Flow title (if valid)
        - valid: Boolean indicating parse success
        - error: Error message (if invalid)
        - step_count: Number of steps (if valid)
    """
    if not FLOWS_DIR.exists():
        return []

    parser = YAMLFlowParser()
    results = []

    for pattern in parser.FILE_PATTERNS:
        for yaml_file in sorted(FLOWS_DIR.glob(pattern)):
            rel_path = yaml_file.relative_to(FLOWS_DIR)

            try:
                flow: FlowDef | None = parser.parse_file(yaml_file)
                if flow:
                    results.append(
                        {
                            "path": str(rel_path),
                            "name": flow.name,
                            "title": flow.display_name,
                            "valid": True,
                            "error": None,
                            "step_count": len(flow.steps),
                        }
                    )
                # Skip non-flow files (parse_file returns None)
            except FlowParseError as e:
                results.append(
                    {
                        "path": str(rel_path),
                        "name": None,
                        "title": None,
                        "valid": False,
                        "error": e.message,
                        "step_count": 0,
                    }
                )

    return results


def load_flow_for_editing(file_path: str) -> dict:
    """Load a flow YAML file for form editing.

    Uses ruamel.yaml to preserve comments when the file is later saved.

    Args:
        file_path: Relative path like 'linear-connection.yaml'

    Returns:
        Raw dict from YAML (not FlowDef) for form editing

    Raises:
        PermissionError: If path traversal attempted
        ValueError: If not a YAML file
        FileNotFoundError: If file doesn't exist
    """
    resolved = validate_flow_path(file_path)

    yaml = YAML()
    yaml.preserve_quotes = True

    with open(resolved) as f:
        return dict(yaml.load(f))


def save_flow(file_path: str, data: dict) -> None:
    """Save a flow YAML file, preserving comments if file exists.

    Validates the content before saving using YAMLFlowParser.

    Args:
        file_path: Relative path like 'linear-connection.yaml'
        data: Flow data dict to save

    Raises:
        PermissionError: If path traversal attempted
        ValueError: If not a YAML file
        FlowParseError: If data fails validation
    """
    resolved = validate_flow_path(file_path)

    # Validate content before writing
    parser = YAMLFlowParser()
    parser._validate_and_build_flow(data, resolved)

    # Configure YAML writer for readable output
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    # If file exists, load it to preserve comments
    if resolved.exists():
        with open(resolved) as f:
            existing = yaml.load(f)
        # Update existing data to preserve comments
        existing.update(data)
        data = existing

    with open(resolved, "w") as f:
        yaml.dump(data, f)
