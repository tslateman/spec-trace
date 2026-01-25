"""Convert msgspec Structs to JSON Schema for OpenAPI spec generation."""

from typing import Any

import msgspec
from msgspec import Struct

from .introspection import EndpointInfo


def struct_to_json_schema(struct_type: type[Struct]) -> tuple[str, dict[str, Any]]:
    """Convert a msgspec Struct to OpenAPI 3.1 JSON Schema.

    Args:
        struct_type: The msgspec Struct class to convert.

    Returns:
        Tuple of (schema_name, schema_definition)
    """
    # Use msgspec's built-in schema generation
    schema = msgspec.json.schema(struct_type)

    # The schema name is the class name
    schema_name = struct_type.__name__

    # Clean up schema for OpenAPI 3.1 compatibility
    # msgspec generates JSON Schema compatible output, but we may need minor adjustments
    schema = _clean_schema_for_openapi(schema)

    return schema_name, schema


def _clean_schema_for_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean up a JSON Schema for OpenAPI 3.1 compatibility.

    OpenAPI 3.1 uses JSON Schema draft 2020-12, which msgspec targets,
    so minimal changes are needed.
    """
    # Remove $schema if present (OpenAPI has its own schema declaration)
    schema.pop("$schema", None)

    return schema


def _extract_component_refs(
    schema: dict[str, Any],
    defs: dict[str, Any],
) -> dict[str, Any]:
    """Extract $defs from a schema and return them as separate components.

    msgspec generates schemas with $defs for nested types. We need to extract
    these and reference them properly in OpenAPI's components/schemas.
    """
    components: dict[str, Any] = {}

    if "$defs" in defs:
        for name, definition in defs["$defs"].items():
            components[name] = _clean_schema_for_openapi(definition)

    return components


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
            name, schema = struct_to_json_schema(endpoint.request_schema)

            # Extract and add $defs as separate components
            if "$defs" in schema:
                for def_name, definition in schema["$defs"].items():
                    if def_name not in schemas:
                        schemas[def_name] = _clean_schema_for_openapi(definition)
                # Remove $defs from main schema and use $ref instead
                del schema["$defs"]

            schemas[name] = schema

        # Process response schema
        if endpoint.response_schema and endpoint.response_schema not in seen_types:
            seen_types.add(endpoint.response_schema)
            name, schema = struct_to_json_schema(endpoint.response_schema)

            # Extract and add $defs as separate components
            if "$defs" in schema:
                for def_name, definition in schema["$defs"].items():
                    if def_name not in schemas:
                        schemas[def_name] = _clean_schema_for_openapi(definition)
                del schema["$defs"]

            schemas[name] = schema

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
