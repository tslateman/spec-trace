"""Reading JUnit test cases, with no database attached."""

from junitparser import Error, Failure, Skipped

__all__ = ["case_nodeid", "case_outcome", "normalize_nodeid"]


def case_outcome(case) -> tuple[str, str]:
    """Return the pytest status and message of a JUnit test case."""
    # Determine status from result list
    # Default: no result element = passed
    status = "passed"
    message = ""

    if case.result:
        for result in case.result:
            if isinstance(result, Failure):
                status = "failed"
                message = result.message or ""
                break
            elif isinstance(result, Error):
                status = "error"
                message = result.message or ""
                break
            elif isinstance(result, Skipped):
                status = "skipped"
                message = result.message or ""
    return status, message


def case_nodeid(case) -> str:
    """Return the pytest nodeid of a JUnit test case."""
    # Build nodeid from classname and name
    # pytest format: classname is "tests.test_module" or file path
    return f"{case.classname}::{case.name}" if case.classname else case.name


def normalize_nodeid(nodeid: str) -> str:
    """Normalize a test nodeid to a canonical format.

    JUnit XML uses dotted class paths (spectrace.tests.test_example::test_func)
    while extract_links uses file paths (spectrace/tests/test_example.py::test_func).

    This normalizes to the file path format.

    Args:
        nodeid: Test nodeid in either format.

    Returns:
        Normalized nodeid in file path format.
    """
    if "::" in nodeid:
        path_part, test_part = nodeid.split("::", 1)
    else:
        path_part = nodeid
        test_part = ""

    # If path part has dots and no slashes, convert to file path
    if "." in path_part and "/" not in path_part and not path_part.endswith(".py"):
        # Convert dotted path to file path:
        # spectrace.tests.test_example -> spectrace/tests/test_example.py
        segments = path_part.split(".")
        module_depth = next(
            (i for i, segment in enumerate(segments) if segment[:1].isupper()),
            len(segments),
        )
        path_part = "/".join(segments[:module_depth]) + ".py"
        test_part = "::".join([*segments[module_depth:], *([test_part] if test_part else [])])

    if test_part:
        return f"{path_part}::{test_part}"
    return path_part
