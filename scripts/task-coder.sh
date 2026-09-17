#!/bin/bash
# Coder for `spectrace tasks run`: reads the task's context bundle on stdin and
# runs one claude -p session in the current worktree. Prints the coder's summary.
set -euo pipefail

prompt=$(python3 "$(dirname "$0")/task_prompt.py" coder)

claude -p "$prompt" \
  --append-system-prompt "You are the coder for one SpecTrace task. The current directory is a git worktree on the task's branch. Change only what the task's scope allows. Make every done-when criterion true and keep the linked tests passing. Do not commit; the runner commits for you. Finish by printing one paragraph naming the files you changed and why." \
  --permission-mode acceptEdits \
  --allowedTools "Read,Edit,Write,Glob,Grep,Bash(pytest *),Bash(python *),Bash(ruff *),Bash(git diff*),Bash(git status*),Bash(ls*)" \
  --max-turns "${SPECTRACE_CODER_MAX_TURNS:-40}"
