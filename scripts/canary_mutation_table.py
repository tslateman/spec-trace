"""Prove the canary dies. Disables one detection at a time and reports what broke.

Run from the repo root: `.venv/bin/python scripts/canary_mutation_table.py`.
Each mutation is applied to a source file, the canary suite runs, the file is
restored, and the failing test ids are printed as a markdown table.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKS = REPO_ROOT / "spectrace/requirements/services/corpus_checks.py"
MATCHER = REPO_ROOT / "spectrace/requirements/services/corpus_matcher.py"
PARSER = REPO_ROOT / "spectrace/requirements/services/corpus_parser.py"
REVIEW = REPO_ROOT / "spectrace/requirements/services/corpus_review.py"
CANARY = "spectrace/requirements/tests/test_corpus_canary.py"

MUTATIONS = [
    (
        "unaddressed_obligation: never raised",
        CHECKS,
        "        for item in highest.values()\n        if item.entry_id not in cited_entry_ids\n",
        "        for item in highest.values()\n        if False\n",
    ),
    (
        "stale_citation: superseded version accepted",
        CHECKS,
        "        elif citation.version < item.version:",
        "        elif False:",
    ),
    (
        "orphan_citation: never raised",
        CHECKS,
        "        if item is None:\n            findings.append(",
        "        if item is None:\n            _ = (",
    ),
    (
        "unmet_check: checks never evaluated",
        CHECKS,
        ") -> list[Finding]:\n    cited_entry_ids = {citation.entry_id for citation in citations}",
        ") -> list[Finding]:\n    return []\n    cited_entry_ids = "
        "{citation.entry_id for citation in citations}",
    ),
    (
        "conflicting_obligations: contradictions ignored",
        CHECKS,
        "def _conflict_findings(applicable: Sequence[ApplicableVersion]) -> list[Finding]:\n"
        "    findings = []",
        "def _conflict_findings(applicable: Sequence[ApplicableVersion]) -> list[Finding]:\n"
        "    return []\n    findings = []",
    ),
    (
        "version bump: every version applies at once",
        MATCHER,
        "        held = highest.get(version.entry.external_id)\n"
        "        if held is None or version.version > held.version:\n"
        "            highest[version.entry.external_id] = version",
        '        key = f"{version.entry.external_id}@{version.version}"\n'
        "        held = highest.get(key)\n"
        "        if held is None or version.version > held.version:\n"
        "            highest[key] = version",
    ),
    (
        "unstored version: citation above the newest accepted",
        REVIEW,
        "    parsed_citations = parse_citations(citations)\n"
        "    assert_citations_within_corpus(parsed_citations)\n",
        "    parsed_citations = parse_citations(citations)\n",
    ),
    (
        "check-id lineage: undeclared rename accepted",
        PARSER,
        '    entry_id = data["external_id"]\n    version = data["version"]',
        '    return\n    entry_id = data["external_id"]\n    version = data["version"]',
    ),
]


def failing_tests(output: str) -> list[str]:
    return sorted(set(re.findall(r"^FAILED (\S+)", output, re.MULTILINE)))


def run_canary() -> tuple[int, str]:
    result = subprocess.run(
        [".venv/bin/python", "-m", "pytest", CANARY, "-q", "--no-header", "-p", "no:randomly"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    baseline_code, baseline_output = run_canary()
    if baseline_code != 0:
        sys.stdout.write(f"canary is red before any mutation:\n{baseline_output}\n")
        return 1

    rows = []
    for name, path, old, new in MUTATIONS:
        original = path.read_text()
        if original.count(old) != 1:
            sys.stdout.write(f"mutation '{name}' does not apply cleanly to {path.name}\n")
            return 1
        path.write_text(original.replace(old, new))
        code, output = run_canary()
        path.write_text(original)
        rows.append((name, code, failing_tests(output)))

    restored_code, restored_output = run_canary()
    if restored_code != 0:
        sys.stdout.write(f"canary stayed red after restoring sources:\n{restored_output}\n")
        return 1

    sys.stdout.write("| Mutation | Canary | Assertions that broke |\n|---|---|---|\n")
    for name, code, failures in rows:
        verdict = "red" if code != 0 else "GREEN - canary blind"
        names = "<br>".join(item.split("::")[-1] for item in failures) or "none"
        sys.stdout.write(f"| {name} | {verdict} | {names} |\n")

    return 0 if all(code != 0 for _, code, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
