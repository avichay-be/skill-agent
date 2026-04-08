#!/bin/bash
# PostToolUse hook: after a git push, watch the CI pipeline and report status.
# Receives JSON on stdin with tool_input.command.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only act on git push commands
if ! echo "$COMMAND" | grep -qE '(^|\s|&&|\|)git\s+push'; then
  exit 0
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ -z "$BRANCH" ]; then
  echo "Could not determine current branch." >&2
  exit 0
fi

# Wait briefly for GitHub to register the new run
sleep 5

# Get the latest run ID for this branch
RUN_ID=$(gh run list --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || echo "")
if [ -z "$RUN_ID" ]; then
  echo "No CI run found for branch '$BRANCH'." >&2
  exit 0
fi

echo "Watching CI pipeline (run $RUN_ID) on branch '$BRANCH'..."

# Watch the run, capture output
OUTPUT=$(gh run watch "$RUN_ID" --exit-status 2>&1) && STATUS=0 || STATUS=$?

if [ $STATUS -eq 0 ]; then
  echo "CI pipeline PASSED (run $RUN_ID)"
else
  # Get failed step logs for context
  FAILED_LOG=$(gh run view "$RUN_ID" --log-failed 2>&1 | tail -20)
  echo "CI pipeline FAILED (run $RUN_ID)"
  echo ""
  echo "Failed step output:"
  echo "$FAILED_LOG"
  exit 2
fi
