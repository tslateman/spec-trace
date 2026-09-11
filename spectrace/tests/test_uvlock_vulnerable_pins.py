"""Guards uv.lock against pins behind known security fixes.

Each entry is the lowest version that clears the CVEs osv-scanner reported
against the previously committed lock (see PYSEC-2026-52 for Django,
GHSA-g6cj-pr64-35w5 for cryptography, and the rest of the osv.dev table in
the uvlock-vulnerable-pins finding).
"""

import tomllib
from pathlib import Path

import pytest
from packaging.version import Version

LOCKFILE = Path(__file__).resolve().parents[2] / "uv.lock"

MINIMUM_FIXED_VERSIONS = {
    "django": "5.2.14",
    "cryptography": "50.0.0",
    "pyjwt": "2.13.0",
    "sqlparse": "0.6.0",
    "urllib3": "2.7.0",
    "idna": "3.15",
    "pygments": "2.20.0",
    "requests": "2.33.0",
    "pytest": "9.0.3",
}


def locked_versions():
    data = tomllib.loads(LOCKFILE.read_text())
    return {pkg["name"]: pkg["version"] for pkg in data["package"]}


@pytest.mark.parametrize("package,minimum", sorted(MINIMUM_FIXED_VERSIONS.items()))
def test_lockfile_pins_patched_version(package, minimum):
    versions = locked_versions()
    assert package in versions, f"{package} is no longer in uv.lock"
    assert Version(versions[package]) >= Version(minimum), (
        f"uv.lock pins {package} {versions[package]}, below the patched {minimum}"
    )
