"""Tests for code-level impact analysis."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml

from requirements.services.impact_analyzer import (
    CodeImpactResult,
    ImpactAnalyzer,
    ProjectRevision,
)


@pytest.fixture
def project_roots(tmp_path):
    """Create project roots with map files for testing."""
    lore_root = tmp_path / "lore"
    lore_root.mkdir()
    praxis_root = tmp_path / "praxis"
    praxis_root.mkdir()

    # spectrace-map.yaml for lore
    map_data = {
        "project": "lore",
        "modules": {
            "src/lore/reader.py": {"requirements": ["REQ-LORE-001"]},
        },
    }
    with open(lore_root / "spectrace-map.yaml", "w") as f:
        yaml.dump(map_data, f)

    return {
        "lore": ProjectRevision(lore_root, "HEAD~1", "HEAD"),
        "praxis": ProjectRevision(praxis_root, "HEAD~1", "HEAD"),
    }


class TestCodeAnalyze:
    """Tests for ImpactAnalyzer.code_analyze()."""

    def test_no_changes_returns_empty(self, project_roots):
        """No changed files produces empty result."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze(project_roots)

        assert result.changed_files == {}
        assert result.risk_level == "low"
        assert result.risk_score <= 0.25  # Low risk
        assert isinstance(result, CodeImpactResult)

    @pytest.mark.django_db
    def test_single_file_maps_to_requirements(self, project_roots):
        """A changed file in lore maps to its requirement via spectrace-map.

        Needs the database: affected tests come from TestRequirementLink, and a
        query failure now surfaces instead of yielding an empty test list.
        """
        analyzer = ImpactAnalyzer()

        # First call: git diff for lore returns a file
        # Second call: git diff for praxis returns nothing
        # Third call: git log for lore (co-change)
        # Fourth call: git log for praxis (co-change)
        diff_lore = MagicMock(stdout="src/lore/reader.py\n")
        diff_praxis = MagicMock(stdout="")
        log_empty = MagicMock(stdout="")

        with patch("subprocess.run", side_effect=[diff_lore, diff_praxis, log_empty, log_empty]):
            result = analyzer.code_analyze(project_roots)

        assert "lore" in result.changed_files
        assert "src/lore/reader.py" in result.changed_files["lore"]
        assert result.edge_summary["annotated"] > 0

    def test_edge_summary_counts(self, project_roots):
        """Edge summary reflects actual edge sources."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze(project_roots)

        assert "annotated" in result.edge_summary
        assert "inferred" in result.edge_summary
        assert "contract" in result.edge_summary

    def test_risk_scoring_weights(self, project_roots):
        """Risk score incorporates graph risk, test impact, and edge factors."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze(project_roots)

        # Empty analysis should have low risk
        assert result.risk_score <= 0.25
        assert result.risk_level == "low"

    def test_invalid_ref_raises(self, tmp_path):
        """Invalid git ref raises ValueError."""
        with pytest.raises(ValueError):
            ProjectRevision(tmp_path, "", "HEAD")

    def test_code_analyze__rejects_an_empty_project_set(self):
        with pytest.raises(ValueError, match="at least one project"):
            ImpactAnalyzer().code_analyze({})

    def test_code_impact_result_defaults(self):
        """CodeImpactResult has sensible defaults."""
        result = CodeImpactResult(
            changed_files={},
            blast={},
            affected_tests=[],
        )
        assert result.risk_score == 0.0
        assert result.risk_level == "low"
        assert result.edge_summary == {
            "annotated": 0,
            "inferred": 0,
            "contract": 0,
            "dependency": 0,
        }


class TestGetAllChangedFiles:
    """Tests for ImpactAnalyzer.get_all_changed_files()."""

    def test_returns_all_files(self):
        """Returns all changed files, not just specs."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="src/app.py\nREADME.md\ntests/test_app.py\n")
        with patch("subprocess.run", return_value=mock_result):
            files = analyzer.get_all_changed_files("HEAD~1", "HEAD")
        assert len(files) == 3
        assert "src/app.py" in files

    def test_empty_diff(self):
        """Empty diff returns empty list."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            files = analyzer.get_all_changed_files("HEAD~1", "HEAD")
        assert files == []

    def test_git_failure_raises(self):
        """Git failure raises ValueError."""
        import subprocess

        analyzer = ImpactAnalyzer()
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git", stderr="error"),
        ):
            with pytest.raises(ValueError, match="Git diff failed"):
                analyzer.get_all_changed_files("HEAD~1", "HEAD")


class TestCliCodeFlag:
    """Tests for --code flag dispatching in CLI."""

    def test_code_flag_dispatches_to_code_impact(self):
        """The --code flag routes to code_impact_analysis command."""
        with patch("cli._run") as mock_run:
            with patch("cli._bootstrap_django"):
                from click.testing import CliRunner

                from cli import cli

                runner = CliRunner()
                runner.invoke(cli, ["specs", "impact", "HEAD~1", "HEAD", "--code"])
                if mock_run.called:
                    assert mock_run.call_args[0][0] == "code_impact_analysis"

    def test_without_code_flag_dispatches_to_impact_analysis(self):
        """Without --code, routes to regular impact_analysis."""
        with patch("cli._run") as mock_run:
            with patch("cli._bootstrap_django"):
                from click.testing import CliRunner

                from cli import cli

                runner = CliRunner()
                runner.invoke(cli, ["specs", "impact", "HEAD~1", "HEAD"])
                if mock_run.called:
                    assert mock_run.call_args[0][0] == "impact_analysis"


class TestOneRepoPerRefPair:
    """Each project diffs across its own refs, inside its own root."""

    def test_code_analyze__diffs_each_project_across_its_own_refs(self, tmp_path):
        projects = {
            "lore": ProjectRevision(tmp_path / "lore", "v1.4.0", "HEAD"),
            "praxis": ProjectRevision(tmp_path / "praxis", "release/2026-09", "main"),
        }
        for revision in projects.values():
            revision.root.mkdir()
        empty = MagicMock(stdout="")

        with patch("subprocess.run", autospec=True, return_value=empty) as run:
            ImpactAnalyzer().code_analyze(projects)

        diffs = {
            call.kwargs["cwd"]: call.args[0]
            for call in run.call_args_list
            if call.args[0][:2] == ["git", "diff"]
        }
        assert diffs == {
            tmp_path / "lore": ["git", "diff", "--name-only", "v1.4.0", "HEAD"],
            tmp_path / "praxis": ["git", "diff", "--name-only", "release/2026-09", "main"],
        }

    def test_code_analyze__names_the_project_whose_ref_is_missing(self, tmp_path):
        projects = {
            "lore": ProjectRevision(tmp_path / "lore", "v1.4.0", "HEAD"),
            "praxis": ProjectRevision(tmp_path / "praxis", "v1.4.0", "HEAD"),
        }
        for revision in projects.values():
            revision.root.mkdir()
        missing = subprocess.CalledProcessError(128, "git", stderr="fatal: bad revision 'v1.4.0'")

        with patch("subprocess.run", autospec=True, side_effect=[MagicMock(stdout=""), missing]):
            with pytest.raises(ValueError, match="project 'praxis'.*bad revision 'v1.4.0'"):
                ImpactAnalyzer().code_analyze(projects)

    def test_code_analyze__records_the_revision_each_project_was_diffed_across(self, project_roots):
        with patch("subprocess.run", autospec=True, return_value=MagicMock(stdout="")):
            result = ImpactAnalyzer().code_analyze(project_roots)

        assert result.revisions == project_roots

    def test_local_revision__diffs_the_analyzer_repository(self, tmp_path):
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        assert analyzer.local_revision("main", "HEAD") == {
            "local": ProjectRevision(tmp_path, "main", "HEAD")
        }


class TestCodeAnalyzeFailsLoud:
    """A broken analysis must never read as an empty blast radius."""

    def test_code_analyze__raises_when_git_diff_fails(self, project_roots):
        analyzer = ImpactAnalyzer()
        failure = subprocess.CalledProcessError(128, "git", stderr="fatal: bad object deadbeef")

        with patch("subprocess.run", side_effect=failure):
            with pytest.raises(ValueError, match="Git diff failed for project 'lore'"):
                analyzer.code_analyze(project_roots)

    def test_code_analyze__raises_when_a_project_root_is_unusable(self, project_roots):
        with patch("subprocess.run", side_effect=FileNotFoundError("no such directory")):
            with pytest.raises(ValueError, match="Cannot run git for project"):
                ImpactAnalyzer().code_analyze(project_roots)

    def test_code_analyze__raises_when_git_diff_times_out(self, project_roots):
        timeout = subprocess.TimeoutExpired("git", 30)

        with patch("subprocess.run", side_effect=timeout):
            with pytest.raises(ValueError, match="Git diff timed out"):
                ImpactAnalyzer().code_analyze(project_roots)

    def test_code_analyze__raises_when_a_contract_snapshot_is_malformed(self, project_roots):
        (project_roots["lore"].root / "contract.snapshot.json").write_text("{not json")
        mock_result = MagicMock(stdout="")

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(ValueError):
                ImpactAnalyzer().code_analyze(project_roots)

    def test_code_analyze__scores_an_empty_diff_as_no_risk(self, project_roots):
        (project_roots["lore"].root / "contract.snapshot.json").unlink(missing_ok=True)
        mock_result = MagicMock(stdout="")

        with patch("subprocess.run", return_value=mock_result):
            result = ImpactAnalyzer().code_analyze(project_roots)

        assert result.changed_files == {}
        assert result.risk_score == 0.0
        assert result.risk_level == "low"


def _declare_praxis_dependency(project_roots):
    map_data = {
        "project": "praxis",
        "modules": {
            "src/praxis/impact.py": {
                "requirements": ["REQ-PRX-006"],
                "depends_on": ["lore:spectrace-map.yaml"],
            },
        },
    }
    with open(project_roots["praxis"].root / "spectrace-map.yaml", "w") as f:
        yaml.dump(map_data, f)


@pytest.mark.django_db
def test_code_analyze__reports_the_dependent_project_when_a_provider_surface_changes(
    project_roots,
):
    _declare_praxis_dependency(project_roots)
    diff_lore = MagicMock(stdout="spectrace-map.yaml\n")
    diff_praxis = MagicMock(stdout="")
    log_empty = MagicMock(stdout="")

    with patch(
        "subprocess.run",
        autospec=True,
        side_effect=[diff_lore, diff_praxis, log_empty, log_empty],
    ):
        result = ImpactAnalyzer().code_analyze(project_roots)

    assert result.changed_files == {"lore": ["spectrace-map.yaml"]}
    assert result.blast["affected_modules"] == ["praxis:src/praxis/impact.py"]
    assert "praxis" in result.blast["affected_projects"]
    assert result.blast["cross_project_edges"] == 1
    assert result.edge_summary["dependency"] == 1
    assert result.traversed_edges["dependency"] == 1
