"""Pattern extraction service for extracting structured fields from free-form text.

Uses regex patterns to extract FRET-inspired structured fields from
unstructured text like Linear issue descriptions.
"""
import re
from typing import TypedDict


class StructuredFields(TypedDict, total=False):
    """Extracted structured fields from text."""
    scope: str
    condition: str
    component: str
    timing: str
    response: str


# Patterns for extracting structured fields from free-form text
# These are best-effort patterns that work for common phrasings
EXTRACTION_PATTERNS = {
    # Scope: when does this requirement apply?
    # Matches: "in active_session", "during checkout", "while logged in"
    'scope': [
        r'(?:in|during|while)\s+([a-z][a-z0-9_]*(?:[-_][a-z0-9_]+)*(?:\s+(?:mode|state|phase|session|flow))?)',
        r'(?:when\s+in)\s+([a-z][a-z0-9_]*(?:[-_][a-z0-9_]+)*)',
    ],

    # Condition: what triggers the behavior?
    # Matches: "when battery < 10", "if user is logged in", "whenever timeout occurs"
    'condition': [
        r'(?:when|if|whenever)\s+(.+?)(?:\.|,|then|the system|shall|should|must|will|$)',
        r'(?:given\s+that)\s+(.+?)(?:\.|,|then|$)',
    ],

    # Component: what system owns this?
    # Matches: "the warning_system should", "in the auth_service"
    'component': [
        r'(?:the|in|by)\s+([a-z][a-z0-9_]*(?:[-_][a-z0-9_]+)*)\s+(?:should|shall|must|will|component|service|system|module)',
        r'([a-z][a-z0-9_]*(?:[-_][a-z0-9_]+)*)\s+(?:component|service|system|module)\s+(?:should|shall|must|will)',
    ],

    # Timing: performance constraint?
    # Matches: "within 2 seconds", "in 500ms", "after 1 minute"
    'timing': [
        r'(?:within|in|after|under)\s+(\d+\s*(?:seconds?|s|ms|milliseconds?|minutes?|m))',
        r'(?:response\s+time|latency)\s*(?:of|:)?\s*(\d+\s*(?:seconds?|s|ms|milliseconds?|minutes?|m))',
        r'(\d+\s*(?:seconds?|s|ms|milliseconds?|minutes?|m))\s+(?:timeout|deadline|limit)',
    ],

    # Response: what must happen?
    # Matches: "shall display warning", "should send notification", "must log error"
    'response': [
        r'(?:shall|should|must|will)\s+(.+?)(?:\.|$)',
        r'(?:the\s+system|it)\s+(?:shall|should|must|will)\s+(.+?)(?:\.|$)',
    ],
}


def extract_structured_fields(text: str) -> StructuredFields:
    """Extract structured fields from free-form text.

    Best-effort extraction using regex patterns. Returns empty strings
    for fields that couldn't be extracted.

    Args:
        text: Free-form text (e.g., Linear issue description)

    Returns:
        StructuredFields dict with extracted values (empty string if not found)
    """
    if not text:
        return {}

    result: StructuredFields = {}

    for field, patterns in EXTRACTION_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                # Clean up the extracted value
                extracted = _clean_extracted_value(extracted, field)
                if extracted:
                    result[field] = extracted  # type: ignore[literal-required]
                    break  # Use first match

    return result


def _clean_extracted_value(value: str, field: str) -> str:
    """Clean up extracted value based on field type.

    Args:
        value: Raw extracted value
        field: Field name (scope, condition, component, timing, response)

    Returns:
        Cleaned value
    """
    if not value:
        return ''

    # Remove trailing punctuation
    value = value.rstrip('.,;:')

    # For component, normalize to snake_case
    if field == 'component':
        value = re.sub(r'[\s-]+', '_', value.lower())
        # Remove any remaining non-identifier characters
        value = re.sub(r'[^a-z0-9_]', '', value)

    # For timing, normalize format
    elif field == 'timing':
        # Ensure consistent format like "2 seconds" or "500ms"
        value = value.lower().strip()
        # Add "within" prefix if not present
        if not value.startswith(('within', 'in', 'under', 'after')):
            value = f"within {value}"

    # For condition and response, capitalize first letter
    elif field in ('condition', 'response'):
        if value and value[0].islower():
            value = value[0].upper() + value[1:]

    return value


def extract_from_markdown(text: str) -> StructuredFields:
    """Extract structured fields from markdown-formatted text.

    Handles common markdown patterns like:
    - **Condition:** some condition
    - ## Timing: 2 seconds
    - * Component: warning_system

    Args:
        text: Markdown-formatted text

    Returns:
        StructuredFields dict with extracted values
    """
    if not text:
        return {}

    result: StructuredFields = {}

    # Pattern for labeled sections in markdown
    # Matches: "**Scope:** value", "## Condition: value", "- Timing: value"
    labeled_pattern = r'(?:\*\*|#+|-|\*)\s*(scope|condition|component|timing|response)\s*[:\*]+\s*(.+?)(?:\n|$)'

    for match in re.finditer(labeled_pattern, text, re.IGNORECASE):
        field = match.group(1).lower()
        value = match.group(2).strip()

        if field in EXTRACTION_PATTERNS and value:
            cleaned = _clean_extracted_value(value, field)
            if cleaned:
                result[field] = cleaned  # type: ignore[literal-required]

    # If markdown extraction didn't find anything, try free-form extraction
    if not result:
        result = extract_structured_fields(text)

    return result


def merge_structured_fields(
    base: StructuredFields,
    override: StructuredFields,
) -> StructuredFields:
    """Merge two structured field dicts, with override taking precedence.

    Only non-empty values from override will replace base values.

    Args:
        base: Base structured fields
        override: Override structured fields (takes precedence)

    Returns:
        Merged StructuredFields
    """
    result = dict(base)

    for key, value in override.items():
        if value:  # Only override if non-empty
            result[key] = value

    return result  # type: ignore[return-value]
