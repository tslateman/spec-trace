#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

block=$(awk '/^Run the demo:/{found=1} found && /^```/{n++; if(n==2) exit} found && n==1 && !/^```/' README.md)

scripts=""
while IFS= read -r line; do
  case "$line" in
    "just "*)
      recipe=${line#just }
      script=$(awk -v r="$recipe" '$0 == r":" {getline; print $NF; exit}' justfile)
      ;;
    "# or: python "*)
      script=${line#\# or: python }
      ;;
    "python "*)
      script=${line#python }
      ;;
    *)
      continue
      ;;
  esac
  scripts="$scripts $script"
done <<EOF_BLOCK
$block
EOF_BLOCK

set -- $scripts
if [ "$#" -eq 0 ]; then
  echo "FAIL: found no commands in the README's 'Run the demo:' block" >&2
  exit 1
fi

first="$1"
for s in "$@"; do
  if [ "$s" != "$first" ]; then
    echo "FAIL: README's 'Run the demo:' block documents commands that run different scripts: $scripts" >&2
    exit 1
  fi
done

echo "OK: all documented demo commands run the same script ($first)"
