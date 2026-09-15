"""Verify AGENTS.md's OpenCode plugin docs match the real opencode.json.

Guards against docs/agents-md-micode-plugin-drift: AGENTS.md lists a
"micode" plugin and shows a config block including it, but the actual
~/.config/opencode/opencode.json does not load that plugin.
"""

import json
import re
from pathlib import Path

import pytest

AGENTS_MD = Path(__file__).resolve().parents[2] / "AGENTS.md"
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"


def _extract_config_block_plugins():
    text = AGENTS_MD.read_text()
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    assert match, "AGENTS.md has no fenced json config block"
    config = json.loads(match.group(1))
    return config["plugin"]


def _plugin_base_name(entry):
    if entry.startswith("@"):
        rest = entry[1:].rsplit("@", 1)[0]
        return f"@{rest}"
    return entry.split("@")[0]


@pytest.mark.skipif(
    not OPENCODE_CONFIG.exists(), reason="opencode.json not present on this machine"
)
def test_agents_md_config_block_matches_real_opencode_json():
    documented = [_plugin_base_name(p) for p in _extract_config_block_plugins()]
    real = json.loads(OPENCODE_CONFIG.read_text())
    actual = [_plugin_base_name(p) for p in real["plugin"]]
    assert documented == actual


def test_agents_md_has_no_micode_references():
    text = AGENTS_MD.read_text()
    assert "micode" not in text.lower()
