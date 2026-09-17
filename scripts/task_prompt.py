"""Prompts for the claude-backed coder and scorer that `spectrace tasks run` drives.

Usage: `python3 task_prompt.py coder < bundle.json` or `python3 task_prompt.py scorer < payload.json`.
"""

import json
import sys


def task_brief(task: dict, with_sources: bool) -> list[str]:
    lines = [f"# Task {task['task_id']}: {task['title']}", "", task.get("description", ""), ""]
    lines += ["## Done when"] + [f"- {item}" for item in task.get("done_when", [])]
    lines += ["", "## Scope in"] + [f"- {item}" for item in task.get("scope_in", [])]
    lines += ["", "## Scope out"] + [f"- {item}" for item in task.get("scope_out", [])]
    lines += ["", "## Requirements"]
    for req in task.get("requirements", []):
        lines += [f"### {req['external_id']}: {req['title']}", req.get("description", "")]
        if with_sources:
            lines.append(f"Source: {req.get('source_file', '')}")
            tests = [result["test_nodeid"] for result in req.get("test_results", [])]
            if tests:
                lines += ["Linked tests:"] + [f"- {test}" for test in tests]
        lines.append("")
    return lines


def coder_prompt(bundle: dict) -> str:
    return "\n".join(task_brief(bundle, with_sources=True))


def scorer_prompt(payload: dict) -> str:
    lines = task_brief(payload["task"], with_sources=False)
    lines += [f"## Diff for commit {payload['commit_sha']}", "", "```diff", payload["diff"], "```"]
    return "\n".join(lines)


def verdict_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    return json.dumps(json.loads(text[start : end + 1]))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "coder":
        print(coder_prompt(json.load(sys.stdin)))
    elif mode == "scorer":
        print(scorer_prompt(json.load(sys.stdin)))
    elif mode == "verdict":
        print(verdict_json(sys.stdin.read()))
    else:
        raise SystemExit(f"unknown mode {mode!r}")
