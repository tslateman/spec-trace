"""Payloads for the Worker's push endpoints, built from specs, flows, and links on disk."""

import json
from dataclasses import asdict
from pathlib import Path

from django.utils import timezone

from requirements.flows.parser import YAMLFlowParser
from requirements.parser import SpecParser
from requirements.projects import default_project
from requirements.services.impact_analyzer import ImpactResult
from requirements.services.link_records import requirement_ids_of
from requirements.services.map_reader import project_for_path
from requirements.services.name_tags import junit_links
from requirements.validator import DriftResult


def project_of(spec_dirs: list[Path]) -> str:
    """Name the project the spec directories belong to.

    The nearest spectrace-map.yaml above any directory wins; this installation's
    own project is the fallback.
    """
    for spec_dir in spec_dirs:
        project = project_for_path(spec_dir)
        if project:
            return project
    return default_project()


def requirement_payload(spec_dirs: list[Path]) -> list[dict]:
    """Parse every spec directory into the flat requirement list PUT /specs/ takes."""
    parser = SpecParser()
    return [
        requirement for spec_dir in spec_dirs for requirement in parser.parse_directory(spec_dir)
    ]


def link_payload(links_file: Path) -> list[dict]:
    """Flatten a links file into {test_nodeid, requirement_id} pairs.

    Accepts extract_links JSON, or a JUnit XML report whose case names carry
    `[REQ-X]` tags.
    """
    if links_file.suffix.lower() == ".xml":
        return junit_links(links_file)
    data = json.loads(links_file.read_text())
    return [
        {"test_nodeid": link["test_nodeid"], "requirement_id": requirement_id}
        for link in data.get("links", [])
        for requirement_id in requirement_ids_of(link)
    ]


def flow_payload(flows_path: Path) -> list[dict]:
    """Parse one flow YAML file or a directory of them into FlowUpsert dicts."""
    parser = YAMLFlowParser()
    if flows_path.is_file():
        flow = parser.parse_file(flows_path)
        flows = [flow] if flow is not None else []
    else:
        flows = parser.parse_directory(flows_path)
    return [asdict(flow) for flow in flows]


def impact_report(result: ImpactResult, base_ref: str, head_ref: str, project: str) -> dict:
    """Wrap an ImpactAnalyzer result with the provenance POST /results/impact/ requires."""
    return {
        "project": project,
        "base": base_ref,
        "head": head_ref,
        "generated_at": timezone.now().isoformat(),
        "changed_requirements": result.changed_requirements,
        "affected_tests": result.affected_tests,
        "hierarchy_expansion": result.hierarchy_expansion,
        "dependency_expansion": result.dependency_expansion,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
    }


def coverage_snapshot(metrics: dict, commit_sha: str, git_branch: str) -> dict:
    """Wrap a coverage_metrics result with the provenance POST /results/coverage/ requires."""
    return {
        **metrics,
        "commit_sha": commit_sha,
        "git_branch": git_branch,
        "generated_at": timezone.now().isoformat(),
    }


def drift_report(result: DriftResult, project: str) -> dict:
    """Wrap a detect_all_drift result with the provenance POST /results/drift/ requires."""
    return {"project": project, "generated_at": timezone.now().isoformat(), **result.to_dict()}


def slo_payload(slos_dir: Path) -> list[dict]:
    """Parse every OpenSLO document in a directory into the list PUT /slos/ takes.

    The parser yields `target` as a Decimal for the ORM's sake; JSON needs a float.
    """
    from requirements.services.openslo_docs import OpenSLOParser

    return [
        {**slo, "target": float(slo["target"]) if slo["target"] is not None else None}
        for slo in OpenSLOParser().parse_directory(slos_dir)
    ]


def corpus_payload(corpus_dir: Path) -> list[dict]:
    """Parse every corpus document in a directory into the list PUT /corpus/entries/ takes.

    The parser yields `effective_date` as a date for the ORM's sake; JSON needs a string.
    """
    from requirements.services.corpus_documents import parse_corpus_directory

    return [
        {
            **entry,
            "effective_date": entry["effective_date"].isoformat()
            if entry["effective_date"]
            else None,
        }
        for entry in parse_corpus_directory(corpus_dir)
    ]
