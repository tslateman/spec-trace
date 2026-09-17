"""Tests for the map_validate management command."""

import json
from io import StringIO

import yaml
from django.core.management import call_command


def _write_map(root, modules):
    with open(root / "spectrace-map.yaml", "w") as f:
        yaml.dump({"project": "praxis", "modules": modules}, f)


def _validate(root):
    out = StringIO()
    call_command(
        "map_validate",
        "--project-root",
        str(root),
        "--project-name",
        "praxis",
        "--format",
        "json",
        stdout=out,
    )
    return json.loads(out.getvalue())


def test_map_validate__accepts_a_module_that_depends_on_another_projects_surface(tmp_path):
    _write_map(
        tmp_path,
        {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": ["spectrace:db/requirements_requirement"],
            }
        },
    )

    report = _validate(tmp_path)

    assert report["valid"] is True
    assert report["errors"] == []


def test_map_validate__rejects_a_dependency_without_a_provider_prefix(tmp_path):
    _write_map(
        tmp_path,
        {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": ["db/requirements_requirement"],
            }
        },
    )

    report = _validate(tmp_path)

    assert report["valid"] is False
    assert report["errors"] == [
        "Module 'src/praxis/spectrace.py': dependency 'db/requirements_requirement'"
        " must name a provider and a surface as 'project:surface'"
    ]


def test_map_validate__counts_dependencies_in_the_text_report(tmp_path):
    _write_map(
        tmp_path,
        {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": ["spectrace:db/requirements_requirement"],
            }
        },
    )
    out = StringIO()

    call_command(
        "map_validate", "--project-root", str(tmp_path), "--project-name", "praxis", stdout=out
    )

    assert "  Dependencies: 1" in out.getvalue()
