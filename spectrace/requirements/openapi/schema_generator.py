"""Convert msgspec Structs to JSON Schema for OpenAPI spec generation."""

from typing import Any

import msgspec
from msgspec import Struct

from .introspection import EndpointInfo


def _convert_refs(obj: Any) -> Any:
    """Recursively convert $ref paths from $defs to components/schemas format.

    Converts: #/$defs/SchemaName -> #/components/schemas/SchemaName
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str) and value.startswith("#/$defs/"):
                # Convert $defs reference to components/schemas reference
                schema_name = value.replace("#/$defs/", "")
                result[key] = f"#/components/schemas/{schema_name}"
            else:
                result[key] = _convert_refs(value)
        return result
    elif isinstance(obj, list):
        return [_convert_refs(item) for item in obj]
    else:
        return obj


def struct_to_json_schema(
    struct_type: type[Struct],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a msgspec Struct to OpenAPI 3.1 JSON Schema.

    Args:
        struct_type: The msgspec Struct class to convert.

    Returns:
        Tuple of (main_schema, additional_schemas_dict)
        - main_schema: The schema for the struct itself
        - additional_schemas_dict: Any nested schemas that should be added to components
    """
    # Use msgspec's built-in schema generation
    raw_schema = msgspec.json.schema(struct_type)

    # Remove $schema if present
    raw_schema.pop("$schema", None)

    # Extract $defs (nested type definitions)
    defs = raw_schema.pop("$defs", {})

    # The main schema might be just a $ref to the actual definition
    # In that case, get the actual schema from $defs
    if "$ref" in raw_schema and raw_schema["$ref"].startswith("#/$defs/"):
        ref_name = raw_schema["$ref"].replace("#/$defs/", "")
        main_schema = defs.pop(ref_name, raw_schema)
    else:
        main_schema = raw_schema

    # Convert all $ref paths in main schema and defs
    main_schema = _convert_refs(main_schema)
    additional_schemas = {name: _convert_refs(schema) for name, schema in defs.items()}

    return main_schema, additional_schemas


def collect_schemas_from_endpoints(
    endpoints: list[EndpointInfo],
) -> dict[str, dict[str, Any]]:
    """Collect all unique schemas from a list of endpoints.

    Args:
        endpoints: List of EndpointInfo objects.

    Returns:
        Dict mapping schema names to their JSON Schema definitions.
    """
    schemas: dict[str, dict[str, Any]] = {}
    seen_types: set[type] = set()

    for endpoint in endpoints:
        # Process request schema
        if endpoint.request_schema and endpoint.request_schema not in seen_types:
            seen_types.add(endpoint.request_schema)
            main_schema, additional = struct_to_json_schema(endpoint.request_schema)

            # Add additional schemas first (dependencies)
            for name, schema in additional.items():
                if name not in schemas:
                    schemas[name] = schema

            # Add main schema
            schemas[endpoint.request_schema.__name__] = main_schema

        # Process response schema
        if endpoint.response_schema and endpoint.response_schema not in seen_types:
            seen_types.add(endpoint.response_schema)
            main_schema, additional = struct_to_json_schema(endpoint.response_schema)

            # Add additional schemas first (dependencies)
            for name, schema in additional.items():
                if name not in schemas:
                    schemas[name] = schema

            # Add main schema
            schemas[endpoint.response_schema.__name__] = main_schema

    return schemas


def get_schema_ref(struct_type: type[Struct] | None) -> dict[str, Any] | None:
    """Get a $ref to a schema in components/schemas.

    Args:
        struct_type: The msgspec Struct class.

    Returns:
        Dict with $ref, or None if struct_type is None.
    """
    if struct_type is None:
        return None

    return {"$ref": f"#/components/schemas/{struct_type.__name__}"}
