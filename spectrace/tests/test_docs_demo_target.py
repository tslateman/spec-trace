"""Tests that README-documented `make` alternatives run the script they claim to."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _makefile_recipe(target: str) -> str:
    makefile = (REPO_ROOT / "Makefile").read_text()
    match = re.search(rf"^{re.escape(target)}:.*\n((?:\t.*\n?)+)", makefile, re.MULTILINE)
    assert match, f"Makefile has no target named {target!r}"
    return match.group(1)


def test_document_pipeline_demo_alternative_matches_makefile_target():
    readme = (REPO_ROOT / "README.md").read_text()
    match = re.search(
        r"Run the demo:\s*```bash\s*make (\S+)\s*# or: python (\S+)\s*```",
        readme,
    )
    assert match, "README's Document Pipeline 'Run the demo' block has an unexpected shape"

    make_target, alt_script = match.group(1), match.group(2)
    recipe = _makefile_recipe(make_target)

    assert alt_script in recipe, (
        f"`make {make_target}` does not run {alt_script} "
        f"(recipe: {recipe.strip()!r}); README documents them as equivalent"
    )
