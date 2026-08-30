"""Tests for the CI impact gate: exit codes, project roots, and PR comments."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from django.core.management import call_command
from django.core.management.base import CommandError

from cli import cli
from requirements.management.commands.code_impact_analysis import parse_project_roots
from requirements.services.github_comment import CommentResult
from requirements.services.impact_analyzer import CodeImpactResult


def make_result(risk_level, risk_score=0.5):
    return CodeImpactResult(
        changed_files={"local": ["a.py"]},
        blast={
            "affected_requirements": ["REQ-A-001"],
            "affected_modules": ["a.py"],
            "affected_projects": ["local"],
        },
        affected_tests=["tests/test_a.py::test_a"],
        risk_score=risk_score,
        risk_level=risk_level,
    )


def run_gate(risk_level, **options):
    with patch(
        "requirements.management.commands.code_impact_analysis.ImpactAnalyzer",
        autospec=True,
    ) as analyzer:
        analyzer.return_value.code_analyze.return_value = make_result(risk_level)
        call_command("code_impact_analysis", "base", "head", **options)


class TestParseProjectRoots:
    def test_parse_project_roots__maps_names_to_paths(self, tmp_path):
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta").mkdir()

        roots = parse_project_roots(f"alpha={tmp_path / 'alpha'},beta={tmp_path / 'beta'}")

        assert roots == {"alpha": tmp_path / "alpha", "beta": tmp_path / "beta"}

    def test_parse_project_roots__rejects_a_bare_path(self, tmp_path):
        with pytest.raises(CommandError, match="Expected name=path pairs"):
            parse_project_roots(str(tmp_path))

    def test_parse_project_roots__rejects_a_root_that_is_not_a_directory(self, tmp_path):
        with pytest.raises(CommandError, match="is not a directory"):
            parse_project_roots(f"alpha={tmp_path / 'absent'}")

    def test_parse_project_roots__rejects_an_empty_value(self):
        with pytest.raises(CommandError, match="named no projects"):
            parse_project_roots(",,")


class TestGateExitCodes:
    def test_handle__exits_zero_on_low_risk(self):
        run_gate("low")

    def test_handle__exits_zero_on_medium_risk(self):
        run_gate("medium")

    def test_handle__exits_one_on_high_risk(self):
        with pytest.raises(SystemExit) as exit_info:
            run_gate("high")
        assert exit_info.value.code == 1

    def test_handle__exits_one_on_critical_risk(self):
        with pytest.raises(SystemExit) as exit_info:
            run_gate("critical")
        assert exit_info.value.code == 1

    def test_handle__reports_a_git_failure_as_a_command_error(self):
        with patch(
            "requirements.management.commands.code_impact_analysis.ImpactAnalyzer",
            autospec=True,
        ) as analyzer:
            analyzer.return_value.code_analyze.side_effect = ValueError("Git diff failed for x")
            with pytest.raises(CommandError, match="Git diff failed"):
                call_command("code_impact_analysis", "base", "head")


class TestGateOutput:
    def test_handle__writes_the_marked_report_to_the_output_file(self, tmp_path):
        report = tmp_path / "impact.md"

        with pytest.raises(SystemExit):
            run_gate("critical", format="markdown", output=str(report))

        body = report.read_text()
        assert body.startswith("<!-- spectrace-impact-gate risk=critical -->")
        assert "**Risk:** CRITICAL" in body

    def test_handle__accepts_md_as_an_alias_for_markdown(self, tmp_path):
        report = tmp_path / "impact.md"

        run_gate("low", format="md", output=str(report))

        assert report.read_text().startswith("<!-- spectrace-impact-gate risk=low -->")

    def test_handle__writes_json_with_a_risk_level(self, tmp_path):
        report = tmp_path / "impact.json"

        run_gate("low", format="json", output=str(report))

        assert json.loads(report.read_text())["risk_level"] == "low"


class TestPostImpactComment:
    def test_handle__upserts_the_report_body(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=high -->\nbody\n")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")

        with patch(
            "requirements.management.commands.post_impact_comment.upsert_pr_comment",
            autospec=True,
        ) as upsert:
            upsert.return_value = CommentResult("updated", 7, "https://gh/c/7")
            call_command(
                "post_impact_comment",
                body_file=str(report),
                repo="o/r",
                pr=42,
            )

        assert upsert.call_args.kwargs["repo"] == "o/r"
        assert upsert.call_args.kwargs["pr_number"] == 42
        assert upsert.call_args.kwargs["body"] == report.read_text()

    def test_handle__refuses_a_report_without_the_gate_marker(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("## Code Impact Analysis\nNo code files changed.\n")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")

        with pytest.raises(CommandError, match="the analysis never finished"):
            call_command("post_impact_comment", body_file=str(report), repo="o/r", pr=42)

    def test_handle__refuses_a_missing_report(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")

        with pytest.raises(CommandError, match="Did the analysis step run"):
            call_command(
                "post_impact_comment",
                body_file=str(tmp_path / "absent.md"),
                repo="o/r",
                pr=42,
            )

    def test_handle__requires_a_token(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=low -->\nbody\n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        with pytest.raises(CommandError, match="Set GITHUB_TOKEN"):
            call_command("post_impact_comment", body_file=str(report), repo="o/r", pr=42)

    def test_handle__requires_a_repository(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=low -->\nbody\n")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        with pytest.raises(CommandError, match="set GITHUB_REPOSITORY"):
            call_command("post_impact_comment", body_file=str(report), pr=42)

    def test_handle__reads_the_pull_request_number_from_the_event_payload(
        self, tmp_path, monkeypatch
    ):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=low -->\nbody\n")
        event = tmp_path / "event.json"
        event.write_text(json.dumps({"pull_request": {"number": 314}}))
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))

        with patch(
            "requirements.management.commands.post_impact_comment.upsert_pr_comment",
            autospec=True,
        ) as upsert:
            upsert.return_value = CommentResult("created", 1, "https://gh/c/1")
            call_command("post_impact_comment", body_file=str(report))

        assert upsert.call_args.kwargs["pr_number"] == 314

    def test_handle__rejects_an_event_payload_without_a_pull_request(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=low -->\nbody\n")
        event = tmp_path / "event.json"
        event.write_text(json.dumps({"push": {}}))
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))

        with pytest.raises(CommandError, match="carries no pull_request number"):
            call_command("post_impact_comment", body_file=str(report))

    def test_handle__skips_github_on_a_dry_run(self, tmp_path, monkeypatch):
        report = tmp_path / "impact.md"
        report.write_text("<!-- spectrace-impact-gate risk=low -->\nbody\n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        with patch(
            "requirements.management.commands.post_impact_comment.upsert_pr_comment",
            autospec=True,
        ) as upsert:
            call_command(
                "post_impact_comment",
                body_file=str(report),
                repo="o/r",
                pr=42,
                dry_run=True,
            )

        upsert.assert_not_called()


class TestCliOptions:
    def test_impact__passes_format_and_output_to_the_gate(self):
        with patch("cli._run", autospec=True) as run, patch("cli._bootstrap_django", autospec=True):
            runner = CliRunner()
            runner.invoke(
                cli,
                [
                    "specs",
                    "impact",
                    "base",
                    "head",
                    "--code",
                    "--format",
                    "markdown",
                    "--output",
                    "impact.md",
                ],
            )

        assert run.call_args[0][0] == "code_impact_analysis"
        assert run.call_args.kwargs["format"] == "markdown"
        assert run.call_args.kwargs["output"] == "impact.md"

    def test_impact__narrows_markdown_to_md_for_spec_only_analysis(self):
        with patch("cli._run", autospec=True) as run, patch("cli._bootstrap_django", autospec=True):
            runner = CliRunner()
            runner.invoke(cli, ["specs", "impact", "base", "head", "--format", "markdown"])

        assert run.call_args[0][0] == "impact_analysis"
        assert run.call_args.kwargs["format"] == "md"
