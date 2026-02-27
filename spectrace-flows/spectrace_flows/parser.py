"""YAML flow parser for importing verification flow definitions.

Enables verification flows to be defined in YAML files instead of Python code,
supporting version control and non-developer editing while maintaining type
safety through dataclass validation.
"""

from pathlib import Path
from typing import Any

import yaml

from .definitions import FlowDef, FlowStepDef


class FlowParseError(Exception):
    """Error parsing a flow YAML file.

    Raised when a YAML file appears to be a flow definition (has 'id' and 'steps')
    but contains schema errors that prevent valid parsing.
    """

    def __init__(self, file_path: Path, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(f"{file_path}: {message}")


class YAMLFlowParser:
    """Parser for verification flow YAML files.

    YAML Schema:
        id: flow-id                   # Required: unique flow identifier
        title: Flow Title              # Required: human-readable name
        description: Optional desc     # Optional: flow description
        version: 1                     # Optional: defaults to 1
        requirements:                  # Optional: linked requirement IDs
          - REQ-XXX
        steps:                         # Required: list of step definitions
          - name: step_name            # Required: step identifier
            type: handler              # Optional: handler|api_call|assertion|wait
            display_name: Step Title   # Required: human-readable name
            description: Optional      # Optional: step description
            handler: dotted.path       # Required if type=handler
            config:                    # Optional: type-specific config
              key: value

    Example:
        id: linear-connection
        title: Linear Connection Verification
        description: Verify Linear API connection
        version: 1
        requirements: []
        steps:
          - name: config
            type: handler
            display_name: Configuration Check
            handler: spectrace_flows.handlers.linear.check_configuration
    """

    FILE_PATTERNS = ("**/*.yaml", "**/*.yml")

    REQUIRED_FIELDS = {"id", "title", "steps"}
    REQUIRED_STEP_FIELDS = {"name", "display_name"}
    VALID_STEP_TYPES = {"handler", "api_call", "assertion", "wait"}

    def parse_file(self, file_path: Path) -> FlowDef | None:
        """Parse a single flow YAML file.

        Args:
            file_path: Path to the YAML file

        Returns:
            FlowDef if valid flow file, None if not a flow file

        Raises:
            FlowParseError: If file is a flow but has schema errors
        """
        with open(file_path) as f:
            content = f.read()

        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse YAML {file_path}: {e}")
            return None

        if not doc or not isinstance(doc, dict):
            return None

        # Check if this looks like a flow file (has 'id' and 'steps')
        has_id = "id" in doc
        has_steps = "steps" in doc

        if not has_id and not has_steps:
            # Not a flow file - silently skip
            return None

        if has_id != has_steps:
            # Partial match - likely malformed flow
            missing = "steps" if has_id else "id"
            raise FlowParseError(file_path, f"Missing required field: {missing}")

        return self._validate_and_build_flow(doc, file_path)

    def _validate_and_build_flow(self, doc: dict[str, Any], file_path: Path) -> FlowDef:
        """Validate document and build FlowDef.

        Args:
            doc: Parsed YAML document
            file_path: Source file path for error messages

        Returns:
            Validated FlowDef

        Raises:
            FlowParseError: If validation fails
        """
        # Check required fields
        missing_fields = self.REQUIRED_FIELDS - set(doc.keys())
        if missing_fields:
            raise FlowParseError(file_path, f"Missing required fields: {sorted(missing_fields)}")

        # Validate steps is a list
        steps_data = doc["steps"]
        if not isinstance(steps_data, list):
            raise FlowParseError(file_path, "Field 'steps' must be a list")

        if not steps_data:
            raise FlowParseError(file_path, "Flow must have at least one step")

        # Build steps
        steps = []
        for i, step_data in enumerate(steps_data):
            if not isinstance(step_data, dict):
                raise FlowParseError(file_path, f"Step {i + 1} must be a mapping")
            steps.append(self._build_step(step_data, file_path, i + 1))

        # Build FlowDef
        requirements = doc.get("requirements", [])
        if requirements is None:
            requirements = []
        if not isinstance(requirements, list):
            raise FlowParseError(file_path, "Field 'requirements' must be a list")

        return FlowDef(
            name=doc["id"],
            display_name=doc["title"],
            description=doc.get("description", ""),
            steps=steps,
            version=doc.get("version", 1),
            requirements=[str(r) for r in requirements],
            source_file=str(file_path),
        )

    def _build_step(self, step_data: dict[str, Any], file_path: Path, step_num: int) -> FlowStepDef:
        """Build a FlowStepDef from step dict.

        Args:
            step_data: Step definition dict
            file_path: Source file for error messages
            step_num: Step number (1-indexed) for error messages

        Returns:
            Validated FlowStepDef

        Raises:
            FlowParseError: If validation fails
        """
        # Check required step fields
        missing = self.REQUIRED_STEP_FIELDS - set(step_data.keys())
        if missing:
            raise FlowParseError(file_path, f"Step {step_num} missing fields: {sorted(missing)}")

        # Validate step type
        step_type = step_data.get("type", "handler")
        if step_type not in self.VALID_STEP_TYPES:
            raise FlowParseError(
                file_path,
                f"Step {step_num} has invalid type '{step_type}'. "
                f"Valid types: {sorted(self.VALID_STEP_TYPES)}",
            )

        # Handler required for type='handler'
        handler = step_data.get("handler", "")
        if step_type == "handler" and not handler:
            raise FlowParseError(
                file_path, f"Step {step_num} (type=handler) requires 'handler' field"
            )

        # Config is optional, defaults to empty dict
        config = step_data.get("config", {})
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise FlowParseError(file_path, f"Step {step_num} 'config' must be a mapping")

        return FlowStepDef(
            name=step_data["name"],
            handler=handler,
            display_name=step_data["display_name"],
            description=step_data.get("description", ""),
            type=step_type,
            config=config,
        )

    def parse_directory(self, flows_dir: Path) -> list[FlowDef]:
        """Parse all YAML files in directory recursively.

        Args:
            flows_dir: Path to flows directory

        Returns:
            List of FlowDef from all valid files
        """
        flows = []
        for pattern in self.FILE_PATTERNS:
            for yaml_file in sorted(flows_dir.glob(pattern)):
                try:
                    flow = self.parse_file(yaml_file)
                    if flow:
                        flows.append(flow)
                except FlowParseError:
                    # Re-raise parse errors (schema violations)
                    raise
                except Exception as e:
                    print(f"Warning: Failed to parse {yaml_file}: {e}")
        return flows
