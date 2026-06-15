#!/bin/bash
# post-requirements-source-resolve.sh
#
# PostToolUse hook (Write|Edit): after the requirements step writes its
# step-result.json, automatically run resolve_source.py to discover
# and sync source repos into the workflow progress file, then un-defer (or
# skip) source-dependent steps.
#
# This makes post-requirements source resolution deterministic — the LLM
# no longer needs to remember to re-run source sync.
#
# Exit codes: always 0 (hooks must not block the LLM).
# All diagnostic output goes to stderr.

set -u

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.file // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Fast bail: only trigger on requirements step-result.json
case "$FILE_PATH" in
  */requirements/step-result.json) ;;
  *) exit 0 ;;
esac

BASE_PATH="${FILE_PATH%/requirements/step-result.json}"

if [ ! -d "$BASE_PATH" ]; then
  exit 0
fi

# Idempotency: skip if already resolved
STAMP="${BASE_PATH}/requirements/.source-resolved"
if [ -f "$STAMP" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MARKER="${PROJECT_DIR}/.agent_workspace/.active-workflow"
PROGRESS_FILE=""

# Prefer the active workflow marker so variant workflows resolve the correct file.
if [ -f "$MARKER" ]; then
  CANDIDATE=$(jq -r '.progress_file // empty' "$MARKER" 2>/dev/null)
  if [ -n "$CANDIDATE" ]; then
    case "$CANDIDATE" in
      /*) CANDIDATE_ABS="$CANDIDATE" ;;
      *) CANDIDATE_ABS="${PROJECT_DIR}/$CANDIDATE" ;;
    esac
    case "$CANDIDATE_ABS" in
      "$BASE_PATH"/workflow/*)
        if [ -f "$CANDIDATE_ABS" ]; then
          PROGRESS_FILE="$CANDIDATE_ABS"
        fi
        ;;
    esac
  fi
fi

if [ -z "$PROGRESS_FILE" ]; then
  shopt -s nullglob
  PROGRESS_FILES=("${BASE_PATH}"/workflow/*.json)
  shopt -u nullglob

  if [ ${#PROGRESS_FILES[@]} -eq 0 ]; then
    exit 0
  fi

  if [ ${#PROGRESS_FILES[@]} -gt 1 ]; then
    echo "post-requirements-source-resolve: multiple progress files found for $BASE_PATH; active marker missing or ambiguous" >&2
    exit 0
  fi

  PROGRESS_FILE="${PROGRESS_FILES[0]}"
fi

# Bail if source is already set (was provided explicitly or resolved pre-flight)
SOURCE_SET=$(jq -r '.options.source.repo_path // empty' "$PROGRESS_FILE" 2>/dev/null)
if [ -n "$SOURCE_SET" ]; then
  touch "$STAMP"
  exit 0
fi

# Read plugin root from conf file
CONF_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/docs-orchestrator.conf"
if [ ! -f "$CONF_FILE" ]; then
  echo "post-requirements-source-resolve: no conf file at $CONF_FILE" >&2
  exit 0
fi

# shellcheck source=/dev/null
source "$CONF_FILE"

if [ -z "${PLUGIN_ROOT:-}" ]; then
  echo "post-requirements-source-resolve: PLUGIN_ROOT not set in $CONF_FILE" >&2
  exit 0
fi

RESOLVE_SCRIPT="${PLUGIN_ROOT}/skills/docs-orchestrator/scripts/resolve_source.py"
if [ ! -f "$RESOLVE_SCRIPT" ]; then
  echo "post-requirements-source-resolve: resolve_source.py not found at $RESOLVE_SCRIPT" >&2
  exit 0
fi

echo "post-requirements-source-resolve: requirements completed, resolving source repos..." >&2

RESULT_FILE=$(mktemp)
trap 'rm -f "$RESULT_FILE"' EXIT

RESOLVE_ARGS=(
  --base-path "$BASE_PATH"
  --progress-file "$PROGRESS_FILE"
  --scan-requirements
  --skip-deferred-on-no-source
)

python3 "$RESOLVE_SCRIPT" "${RESOLVE_ARGS[@]}" > "$RESULT_FILE" 2>&2
RESOLVE_EXIT=$?

if [ "$RESOLVE_EXIT" -eq 0 ]; then
  REPO_PATH=$(jq -r '.repo_path // empty' "$RESULT_FILE" 2>/dev/null)
  if [ -n "$REPO_PATH" ]; then
    echo "post-requirements-source-resolve: source resolved to $REPO_PATH — deferred steps now pending" >&2
  fi

elif [ "$RESOLVE_EXIT" -eq 2 ]; then
  echo "post-requirements-source-resolve: no source repo discovered — deferred steps skipped" >&2

else
  # Error — leave state unchanged
  echo "post-requirements-source-resolve: resolve_source.py failed (exit $RESOLVE_EXIT), leaving state unchanged" >&2
fi

# Write stamp regardless of outcome (prevent re-runs)
touch "$STAMP"

exit 0
