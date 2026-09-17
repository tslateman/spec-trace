#!/bin/bash
# Scorer for `spectrace tasks run`: reads {task, commit_sha, diff} on stdin,
# asks claude -p to judge the diff against the task with no coder context, and
# prints the intent scores as JSON.
set -euo pipefail

prompt=$(python3 "$(dirname "$0")/task_prompt.py" scorer)

claude -p "$prompt" \
  --append-system-prompt 'You judge whether one commit honors the task it claims to implement. Use no tools; the diff above is the whole evidence. Score three things from 0 to 100: strategic_score, how well the change serves the task and its requirements; opportunity_score, how much of the done-when list the change actually completes; drift_score, 100 when every hunk stays inside scope_in and outside scope_out, lower for each hunk that strays. Answer with one JSON object only, no prose and no code fence: {"strategic_score": int, "opportunity_score": int, "drift_score": int, "failure_reasons": [string]}. failure_reasons is empty when every score is 70 or above.' \
  --max-turns 1 \
| python3 "$(dirname "$0")/task_prompt.py" verdict
