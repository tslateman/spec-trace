"""The documented walkthrough, re-run on a fresh database seeded from the files.

`docs/corpus-review.md` shows command output. Those blocks were captured in a
developer checkout whose `db.sqlite3` held an entry version no corpus file
declares, so a clone running the same commands saw something else and nothing
said so.

Every test here seeds a fresh database from the `corpus/` and `specs/` files a
clone gets, runs the documented command, and compares against the block the
documentation prints. The documentation is the fixture: an output block edited
away from what the tool does turns these tests red, and so does a seed-data
change the documentation has not caught up with.

One thing is normalized away and only one: review timestamps. The corpus
snapshot hash is not volatile — it hashes the corpus file content — so it is
asserted exactly as written.
"""

import io
import re
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command

from requirements.models import CorpusEntryVersion, Requirement, RiskLevel
from requirements.parser import SpecParser
from requirements.services.corpus_parser import CorpusParser

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_DOC = REPO_ROOT / "docs" / "corpus-review.md"

CORPUS_DIR = Path("corpus")
SPECS_DIR = Path("specs")
TENANT_ISOLATION_SPEC = "specs/platform/tenant_isolation.md"
INVOICING_SPEC = "specs/billing/invoicing.md"
SUBSCRIPTIONS_SPEC = "specs/billing/subscriptions.md"
LEGACY_ENTRY_FILE = "corpus/billing/metering-source-legacy.md"

FENCE_PATTERN = re.compile(r"^```[a-z]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:\+\d{2}:\d{2})?")


@pytest.fixture
def repo_root(db, monkeypatch):
    """Run from the repository root, the directory every documented command assumes."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture
def fresh_clone(repo_root):
    """A database holding exactly what `corpus/` and `specs/` declare on disk.

    The relative paths matter: `parse_specs specs/` stores relative
    `source_file` values, which is what the `paths` scope rules glob against.
    """
    CorpusParser().import_to_database(CORPUS_DIR)
    SpecParser().import_to_database(SPECS_DIR)


def documented_block(first_line: str) -> str:
    """The fenced block in `docs/corpus-review.md` that opens with this line."""
    blocks = [
        block.strip()
        for block in FENCE_PATTERN.findall(REVIEW_DOC.read_text())
        if block.strip().startswith(first_line)
    ]
    assert len(blocks) == 1, f"expected one documented block starting {first_line!r}"
    return normalized(blocks[0])


def normalized(text: str) -> str:
    """Command output with review timestamps replaced by a fixed marker."""
    return TIMESTAMP_PATTERN.sub("<timestamp>", text.strip())


def run_command(name: str, *args) -> str:
    """Run a management command and return its stdout, ignoring the exit code."""
    out = io.StringIO()
    try:
        call_command(name, *args, stdout=out)
    except SystemExit:
        pass
    return normalized(out.getvalue())


def snapshot_line(text: str) -> str:
    """The `Snapshot: <hash>` line of a review output block."""
    lines = [line for line in text.splitlines() if line.startswith("Snapshot: ")]
    assert len(lines) == 1
    return lines[0]


class TestDocumentedReviewWalkthrough:
    """Each documented block, against the command that claims to produce it."""

    def test_corpus_review__reproduces_the_documented_tenant_isolation_output(self, fresh_clone):
        """The blocking walkthrough, from files alone."""
        expected = documented_block("Review of REQ-PLAT-001")

        assert run_command("corpus_review", TENANT_ISOLATION_SPEC) == expected

    def test_corpus_review__reproduces_the_documented_invoicing_output(self, fresh_clone):
        """The advisory walkthrough, including the finding-free cited entry."""
        expected = documented_block("Review of REQ-BILL-002")

        assert run_command("corpus_review", INVOICING_SPEC) == expected

    def test_corpus_coverage__reproduces_the_documented_ledger_output(self, fresh_clone):
        """The audit ledger the documentation prints after reviewing invoicing."""
        run_command("corpus_review", INVOICING_SPEC)
        expected = documented_block("REQ-BILL-002:")

        assert (
            run_command("corpus_coverage", "--requirement", "REQ-BILL-002", "--format", "text")
            == expected
        )

    def test_corpus_drift__reproduces_the_documented_unmoved_corpus_output(self, fresh_clone):
        """A corpus that has not moved since the reviews ran reports so."""
        run_command("corpus_review", TENANT_ISOLATION_SPEC)
        run_command("corpus_review", INVOICING_SPEC)
        expected = documented_block("Corpus snapshot: 74ac5e6694ba\n\n✓ No stale reviews")

        assert run_command("corpus_drift", "--format", "text") == expected

    def test_corpus_drift__reproduces_the_documented_staged_supersession_output(
        self, repo_root, tmp_path
    ):
        """The documented two-step import, which stages a corpus move from files alone."""
        staged = tmp_path / "corpus-legacy" / "billing"
        staged.mkdir(parents=True)
        shutil.copy(LEGACY_ENTRY_FILE, staged)
        SpecParser().import_to_database(SPECS_DIR)

        call_command("parse_corpus", str(tmp_path / "corpus-legacy"), stdout=io.StringIO())
        run_command("corpus_review", SUBSCRIPTIONS_SPEC)
        call_command("parse_corpus", str(CORPUS_DIR), stdout=io.StringIO())
        expected = documented_block("Corpus snapshot: 74ac5e6694ba\n\nStale reviews (1):")

        assert run_command("corpus_drift", "--format", "text") == expected


class TestDocumentedWalkthroughNeedsNoDatabaseHistory:
    """The failure that started this: output depending on a version no file declares."""

    def test_import_to_database__holds_one_version_per_entry_from_the_corpus_files(
        self, fresh_clone
    ):
        """One file per entry at its current version, so a clone holds one version each."""
        versions = sorted(CorpusEntryVersion.objects.values_list("entry__external_id", "version"))

        assert versions == [
            ("COM-BILL-001", 1),
            ("COM-PLAT-001", 2),
            ("DEC-BILL-001", 1),
            ("DEC-BILL-002", 1),
            ("DEC-IAM-001", 2),
            ("DEC-IAM-002", 1),
            ("STD-SEC-001", 4),
            ("STD-SEC-002", 1),
        ]

    def test_corpus_review__records_the_documented_snapshot_hash_from_files_alone(
        self, fresh_clone
    ):
        """The hash the documentation prints is the hash a clone computes."""
        output = run_command("corpus_review", INVOICING_SPEC)

        assert snapshot_line(output) == snapshot_line(documented_block("Review of REQ-BILL-002"))

    def test_corpus_review__reports_a_citation_below_the_newest_version_as_stale(self, fresh_clone):
        """No corpus file declares STD-SEC-001@3 and the documented finding still fires."""
        assert not CorpusEntryVersion.objects.filter(
            entry__external_id="STD-SEC-001", version=3
        ).exists()

        output = run_command("corpus_review", TENANT_ISOLATION_SPEC)

        assert "spec cites STD-SEC-001@3; version 4 is the applicable one" in output


class TestAuthoredRiskLevelReachesTheReview:
    """The seed spec that classifies its risk, and the check that now passes."""

    def test_import_to_database__stores_the_risk_level_the_seed_spec_declares(self, fresh_clone):
        """`risk_level: high` in frontmatter lands on the row the checks read."""
        requirement = Requirement.objects.get(external_id="REQ-BILL-002")

        assert requirement.risk_level == RiskLevel.HIGH

    def test_import_to_database__leaves_a_silent_spec_unclassified(self, fresh_clone):
        """A spec stating no risk level keeps the default, and its checks still fault."""
        requirement = Requirement.objects.get(external_id="REQ-PLAT-001")

        assert requirement.risk_level == RiskLevel.UNCLASSIFIED

    def test_corpus_review__leaves_the_cited_entry_free_of_findings(self, fresh_clone):
        """DEC-BILL-002 is cited, applies, and faults nothing — the contrast row."""
        output = run_command("corpus_review", INVOICING_SPEC)

        assert "DEC-BILL-002@1 [cited]" in output
        assert "DEC-BILL-002#" not in output
