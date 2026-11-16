#!/usr/bin/env bash
# Says whether a change touches code, for .github/workflows/ci.yml.
#
#   scripts/ci_changes.sh EVENT BASE HEAD   prints code=true or code=false
#
# Documentation is everything below; any other file counts as code and runs the full CI.
# When in doubt (a manual run, a new branch, a diff that fails) it says code=true.
# The guides and docs/images are read by tests/test_guide_pictures.py, which CI still runs
# for a documentation-only change.
set -u

DOCS='^(docs/|site/|\.claude/|LICENSE$|scripts/build_site\.sh$|\.github/workflows/pages\.yml$)|\.md$'

event=${1:-}
base=${2:-}
head=${3:-}

full() {
  echo "code=true"
  echo "Running the full CI: $1" >&2
  exit 0
}

case "$event" in
  pull_request | push) ;;
  *) full "started by $event" ;;
esac
if [ -z "$base" ] || [ -z "$head" ] || [ "$base" = "0000000000000000000000000000000000000000" ]; then
  full "no earlier commit to compare with"
fi

range="$base...$head"
[ "$event" = push ] && range="$base..$head"
if ! changed=$(git diff --name-only "$range"); then
  full "could not compare $range"
fi
[ -n "$changed" ] || full "no files changed"

code=$(printf '%s\n' "$changed" | grep -Ev "$DOCS" || true)
if [ -n "$code" ]; then
  full "code changed: $(printf '%s' "$code" | head -5 | tr '\n' ' ')"
fi
echo "code=false"
echo "Documentation only:" >&2
printf '  %s\n' "$changed" >&2
