"""Tests that each project diffs at its own refs, and that a missing ref fails loudly."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.management.commands.code_impact_analysis import parse_project_refs
from requirements.services.impact_analyzer import (
    ImpactAnalyzer,
    RefPair,
    ref_labels,
    resolve_ref_pairs,
)

ANALYZER = "requirements.management.commands.code_impact_analysis.ImpactAnalyzer"


@pytest.fixture
def two_roots(tmp_path):
    """Two project roots, each with a map of its own."""
    roots = {}
    for name, module in (("lore", "src/lore/reader.py"), ("praxis", "src/praxis/writer.py")):
        root = tmp_path / name
        root.mkdir()
        (root / "spectrace-map.yaml").write_text(
            yaml.dump(
                {
                    "project": name,
                    "modules": {module: {"requirements": [f"REQ-{name.upper()}-001"]}},
                }
            )
        )
        roots[name] = root
    return roots


def git_answers(diffs: dict[str, str]):
    """Answer each root's git diff from `diffs`, and every git log with no history."""

    def run(argv, **kwargs):
        if argv[:2] == ["git", "diff"]:
            return MagicMock(stdout=diffs[Path(kwargs["cwd"]).name])
        return MagicMock(stdout="")

    return run


def diff_calls(mock_run):
    return [call for call in mock_run.call_args_list if call.args[0][:2] == ["git", "diff"]]


class TestResolveRefPairs:
    def test_resolve_ref_pairs__gives_every_root_the_shared_pair(self):
        pairs = resolve_ref_pairs(["lore", "praxis"], RefPair("main", "HEAD"), None)

        assert pairs == {"lore": RefPair("main", "HEAD"), "praxis": RefPair("main", "HEAD")}

    def test_resolve_ref_pairs__gives_each_root_its_own_pair(self):
        per_project = {"lore": RefPair("main", "HEAD"), "praxis": RefPair("v1", "v2")}

        assert resolve_ref_pairs(["lore", "praxis"], None, per_project) == per_project

    def test_resolve_ref_pairs__raises_when_a_root_goes_unnamed(self):
        with pytest.raises(ValueError, match="No refs given for praxis"):
            resolve_ref_pairs(["lore", "praxis"], None, {"lore": RefPair("main", "HEAD")})

    def test_resolve_ref_pairs__raises_when_refs_name_an_unknown_project(self):
        per_project = {"lore": RefPair("main", "HEAD"), "geordi": RefPair("main", "HEAD")}

        with pytest.raises(ValueError, match="Refs name geordi"):
            resolve_ref_pairs(["lore"], None, per_project)

    def test_resolve_ref_pairs__raises_when_both_forms_arrive(self):
        with pytest.raises(ValueError, match="not both"):
            resolve_ref_pairs(["lore"], RefPair("main", "HEAD"), {"lore": RefPair("v1", "v2")})

    def test_resolve_ref_pairs__raises_when_neither_form_arrives(self):
        with pytest.raises(ValueError, match="Name the refs to diff"):
            resolve_ref_pairs(["lore"], None, None)


class TestRefLabels:
    def test_ref_labels__reports_bare_refs_when_every_project_shares_them(self):
        shared = {"lore": RefPair("main", "HEAD"), "praxis": RefPair("main", "HEAD")}

        assert ref_labels(shared) == ("main", "HEAD")

    def test_ref_labels__tags_each_ref_with_its_project_when_they_differ(self):
        pairs = {"lore": RefPair("main", "HEAD"), "praxis": RefPair("v1", "v2")}

        assert ref_labels(pairs) == ("lore=main, praxis=v1", "lore=HEAD, praxis=v2")


class TestParseProjectRefs:
    def test_parse_project_refs__maps_names_to_ref_pairs(self):
        pairs = parse_project_refs("lore=main..HEAD,praxis=v1..v2")

        assert pairs == {"lore": RefPair("main", "HEAD"), "praxis": RefPair("v1", "v2")}

    def test_parse_project_refs__rejects_an_entry_without_a_project(self):
        with pytest.raises(CommandError, match="Expected name=base..head entries"):
            parse_project_refs("main..HEAD")

    def test_parse_project_refs__rejects_an_entry_without_a_range(self):
        with pytest.raises(CommandError, match="Separate the two refs"):
            parse_project_refs("lore=HEAD")

    def test_parse_project_refs__rejects_an_entry_with_an_empty_ref(self):
        with pytest.raises(CommandError, match="Name a base and a head ref"):
            parse_project_refs("lore=..HEAD")

    def test_parse_project_refs__rejects_an_empty_value(self):
        with pytest.raises(CommandError, match="named no projects"):
            parse_project_refs(",,")


@pytest.mark.django_db
class TestCodeAnalyzeRefPerProject:
    def test_code_analyze__diffs_each_project_at_its_own_refs(self, two_roots):
        project_refs = {"lore": RefPair("main", "HEAD"), "praxis": RefPair("v1", "v2")}

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.side_effect = git_answers({"lore": "src/lore/reader.py\n", "praxis": ""})
            result = ImpactAnalyzer().code_analyze(
                project_roots=two_roots, project_refs=project_refs
            )

        argv_by_root = {
            Path(call.kwargs["cwd"]).name: call.args[0] for call in diff_calls(mock_run)
        }
        assert argv_by_root["lore"] == ["git", "diff", "--name-only", "main", "HEAD", "--"]
        assert argv_by_root["praxis"] == ["git", "diff", "--name-only", "v1", "v2", "--"]
        assert result.changed_files == {"lore": ["src/lore/reader.py"]}

    def test_code_analyze__diffs_every_project_at_a_shared_pair(self, two_roots):
        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.side_effect = git_answers({"lore": "", "praxis": ""})
            ImpactAnalyzer().code_analyze("main", "HEAD", project_roots=two_roots)

        assert all(
            call.args[0] == ["git", "diff", "--name-only", "main", "HEAD", "--"]
            for call in diff_calls(mock_run)
        )

    def test_code_analyze__raises_naming_the_project_root_and_ref_a_repository_lacks(
        self, two_roots
    ):
        def run(argv, **kwargs):
            if Path(kwargs["cwd"]).name == "praxis" and argv[:2] == ["git", "diff"]:
                raise subprocess.CalledProcessError(
                    128, "git", stderr="fatal: bad revision 'spectrace-only'"
                )
            return MagicMock(stdout="")

        project_refs = {
            "lore": RefPair("main", "HEAD"),
            "praxis": RefPair("spectrace-only", "HEAD"),
        }
        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.side_effect = run
            with pytest.raises(ValueError) as failure:
                ImpactAnalyzer().code_analyze(project_roots=two_roots, project_refs=project_refs)

        message = str(failure.value)
        assert "'praxis'" in message
        assert str(two_roots["praxis"]) in message
        assert "spectrace-only" in message

    def test_code_analyze__raises_when_a_project_root_gets_no_refs(self, two_roots):
        with pytest.raises(ValueError, match="No refs given for praxis"):
            ImpactAnalyzer().code_analyze(
                project_roots=two_roots, project_refs={"lore": RefPair("main", "HEAD")}
            )

    def test_code_analyze__raises_when_both_ref_forms_arrive(self, two_roots):
        with pytest.raises(ValueError, match="not both"):
            ImpactAnalyzer().code_analyze(
                "main",
                "HEAD",
                project_roots=two_roots,
                project_refs={
                    "lore": RefPair("main", "HEAD"),
                    "praxis": RefPair("v1", "v2"),
                },
            )

    def test_code_analyze__raises_when_no_refs_arrive(self, two_roots):
        with pytest.raises(ValueError, match="Name the refs to diff"):
            ImpactAnalyzer().code_analyze(project_roots=two_roots)


class TestCommandRefPerProject:
    def test_handle__passes_a_ref_pair_per_project_to_the_analyzer(self, two_roots):
        roots = ",".join(f"{name}={root}" for name, root in two_roots.items())

        with patch(ANALYZER, autospec=True) as analyzer:
            call_command(
                "code_impact_analysis",
                project_roots=roots,
                project_refs="lore=main..HEAD,praxis=v1..v2",
            )

        kwargs = analyzer.return_value.code_analyze.call_args.kwargs
        assert kwargs["project_refs"] == {
            "lore": RefPair("main", "HEAD"),
            "praxis": RefPair("v1", "v2"),
        }
        assert analyzer.return_value.code_analyze.call_args.args == (None, None)

    def test_handle__keeps_the_positional_single_root_form(self):
        with patch(ANALYZER, autospec=True) as analyzer:
            call_command("code_impact_analysis", "base", "head")

        call = analyzer.return_value.code_analyze.call_args
        assert call.args == ("base", "head")
        assert call.kwargs["project_refs"] is None

    def test_handle__reports_a_mixed_ref_form_as_a_command_error(self, two_roots):
        roots = ",".join(f"{name}={root}" for name, root in two_roots.items())

        with pytest.raises(CommandError, match="not both"):
            call_command(
                "code_impact_analysis",
                "base",
                "head",
                project_roots=roots,
                project_refs="lore=main..HEAD,praxis=v1..v2",
            )

    def test_handle__labels_the_report_with_each_projects_refs(self, two_roots, capsys):
        roots = ",".join(f"{name}={root}" for name, root in two_roots.items())

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.side_effect = git_answers({"lore": "", "praxis": ""})
            call_command(
                "code_impact_analysis",
                project_roots=roots,
                project_refs="lore=main..HEAD,praxis=v1..v2",
            )

        assert "lore=main, praxis=v1 .. lore=HEAD, praxis=v2" in capsys.readouterr().out
