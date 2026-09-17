"""`meta/corpus/` against `meta/specs/`, the specs SpecTrace writes about itself.

Corpus entries scope through `applies_to`, and an entry whose patterns reach no
spec produces silence rather than a warning. These tests seed a database from
the two `meta/` trees a clone gets and assert the binding holds: every SpecTrace
requirement surfaces an obligation, every applicable obligation is cited, and
every check those citations carry passes.

A rescope that unbinds an entry turns them red. So does a spec that drops a
`complies_with` line, and so does a version bump the specs have not caught up
with.
"""

import io
from pathlib import Path

import pytest
from django.core.management import call_command

from requirements.models import Requirement, ReviewFinding, SpecReview
from requirements.parser import SpecParser
from requirements.services.corpus_parser import CorpusParser

REPO_ROOT = Path(__file__).resolve().parents[3]

META_CORPUS_DIR = Path("meta/corpus")
META_SPECS_DIR = Path("meta/specs")
META_SPEC_FILES = [
    "meta/specs/api-results.md",
    "meta/specs/api-specs.md",
    "meta/specs/api-tasks.md",
    "meta/specs/core-loop.md",
    "meta/specs/prune-screen-exports.md",
]


@pytest.fixture
def meta_clone(db, monkeypatch):
    """A database holding exactly what `meta/corpus/` and `meta/specs/` declare on disk."""
    monkeypatch.chdir(REPO_ROOT)
    CorpusParser().import_to_database(META_CORPUS_DIR)
    SpecParser().import_to_database(META_SPECS_DIR)


def review_every_meta_spec():
    """Record a review of each SpecTrace spec, ignoring the exit code."""
    for spec_file in META_SPEC_FILES:
        try:
            call_command("corpus_review", spec_file, stdout=io.StringIO())
        except SystemExit:
            pass


class TestMetaCorpusBinding:
    """The `applies_to.paths` globs that reach SpecTrace's own specs."""

    def test_corpus_review__surfaces_an_entry_for_every_spectrace_requirement(self, meta_clone):
        review_every_meta_spec()

        surfaced = {
            review.requirement.external_id: review.coverage.count()
            for review in SpecReview.objects.select_related("requirement")
        }
        expected = set(
            Requirement.objects.filter(source_file__startswith="meta/specs/").values_list(
                "external_id", flat=True
            )
        )

        assert set(surfaced) == expected
        assert [name for name, count in surfaced.items() if count == 0] == []

    def test_corpus_review__reports_no_finding_against_a_spectrace_spec(self, meta_clone):
        review_every_meta_spec()

        assert [finding.detail for finding in ReviewFinding.objects.all()] == []
