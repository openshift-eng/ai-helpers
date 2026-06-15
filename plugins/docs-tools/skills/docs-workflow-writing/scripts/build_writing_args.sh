#!/usr/bin/env bash
# Build resolved arguments for the docs-workflow-writing skill.
#
# Handles argument parsing, mode determination, input validation,
# directory creation, and path computation.  Emits a JSON object
# on stdout that the SKILL.md dispatcher uses to select the right
# prompt template and invoke the docs-writer subagent.
#
# Usage:
#   build_writing_args.sh <ticket> --base-path <path> \
#       [--format adoc|mkdocs] [--draft] [--repo <path>] \
#       [--repo-path <path>] [--fix-from <path>]
#
# Requires: jq

set -euo pipefail

# --- Argument parsing ---
TICKET=""
BASE_PATH=""
FORMAT="adoc"
DRAFT=false
DOCS_REPO_PATH=""
SOURCE_REPO=""
ADDITIONAL_REPOS=()
FIX_FROM=""

require_arg() {
  local opt="$1"
  local val="${2:-}"
  if [[ -z "$val" || "$val" == -* ]]; then
    echo "ERROR: ${opt} requires a value." >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-path)
      require_arg "$1" "${2:-}"
      BASE_PATH="$2"
      shift 2
      ;;
    --format)
      require_arg "$1" "${2:-}"
      FORMAT="$2"
      shift 2
      ;;
    --draft)
      DRAFT=true
      shift
      ;;
    --repo)
      require_arg "$1" "${2:-}"
      if [[ -z "$SOURCE_REPO" ]]; then
        SOURCE_REPO="$2"
      else
        ADDITIONAL_REPOS+=("$2")
      fi
      shift 2
      ;;
    --repo-path)
      require_arg "$1" "${2:-}"
      DOCS_REPO_PATH="$2"
      shift 2
      ;;
    --fix-from)
      require_arg "$1" "${2:-}"
      FIX_FROM="$2"
      shift 2
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
      exit 1
      ;;
    *)
      if [[ -z "$TICKET" ]]; then
        TICKET="$1"
      else
        echo "ERROR: Unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

# --- Validate required args ---
if [[ -z "$TICKET" ]]; then
  echo "ERROR: Ticket ID is required as the first positional argument." >&2
  exit 1
fi

if [[ -z "$BASE_PATH" ]]; then
  echo "ERROR: --base-path is required." >&2
  exit 1
fi

if [[ "$FORMAT" != "adoc" && "$FORMAT" != "mkdocs" ]]; then
  echo "ERROR: --format must be 'adoc' or 'mkdocs', got '${FORMAT}'." >&2
  exit 1
fi

# --- Compute paths ---
INPUT_FILE="${BASE_PATH}/planning/plan.md"
CODE_ANALYSIS_DIR="${BASE_PATH}/code-analysis"
PR_ANALYSIS_DIR="${BASE_PATH}/pr-analysis"
OUTPUT_DIR="${BASE_PATH}/writing"
OUTPUT_FILE="${OUTPUT_DIR}/_index.md"

# --- Check for code-learner analysis ---
if [[ -d "$CODE_ANALYSIS_DIR" && -f "$CODE_ANALYSIS_DIR/ONBOARDING.md" ]]; then
  HAS_CODE_ANALYSIS=true
else
  HAS_CODE_ANALYSIS=false
  CODE_ANALYSIS_DIR=""
fi

# --- Check for additional code-learner analyses ---
ADDITIONAL_CODE_ANALYSIS_DIRS=()
for repo in "${ADDITIONAL_REPOS[@]}"; do
  repo_name="$(basename "$repo")"
  add_analysis_dir="${BASE_PATH}/code-analysis-${repo_name}"
  if [[ -d "$add_analysis_dir" && -f "$add_analysis_dir/ONBOARDING.md" ]]; then
    ADDITIONAL_CODE_ANALYSIS_DIRS+=("$add_analysis_dir")
  fi
done

# --- Check for PR analysis ---
if [[ -d "$PR_ANALYSIS_DIR" ]] && ls "$PR_ANALYSIS_DIR"/PR-*-ANALYSIS.md &>/dev/null; then
  HAS_PR_ANALYSIS=true
else
  HAS_PR_ANALYSIS=false
  PR_ANALYSIS_DIR=""
fi

# --- Validate source repo if provided ---
if [[ -n "$SOURCE_REPO" && ! -d "$SOURCE_REPO" ]]; then
  echo "WARNING: Source repo path not found: ${SOURCE_REPO}. Ignoring --repo." >&2
  SOURCE_REPO=""
fi

# --- Validate additional repos ---
VALID_ADDITIONAL_REPOS=()
for repo in "${ADDITIONAL_REPOS[@]}"; do
  if [[ -d "$repo" ]]; then
    VALID_ADDITIONAL_REPOS+=("$repo")
  else
    echo "WARNING: Additional repo path not found: ${repo}. Skipping." >&2
  fi
done
ADDITIONAL_REPOS=("${VALID_ADDITIONAL_REPOS[@]}")

# --- Determine mode ---
MODE=""
if [[ -n "$FIX_FROM" ]]; then
  MODE="fix"
elif [[ -n "$DOCS_REPO_PATH" ]]; then
  MODE="update-in-place"
  if [[ "$DRAFT" == true ]]; then
    echo "WARNING: --draft ignored because --repo-path takes precedence." >&2
  fi
elif [[ "$DRAFT" == true ]]; then
  MODE="draft"
else
  MODE="update-in-place"
fi

# --- Validate inputs ---
if [[ "$MODE" != "fix" && ! -f "$INPUT_FILE" ]]; then
  echo "ERROR: Plan file not found: ${INPUT_FILE}" >&2
  exit 1
fi

if [[ "$MODE" == "fix" && ! -f "$FIX_FROM" ]]; then
  echo "ERROR: Review file not found: ${FIX_FROM}" >&2
  exit 1
fi

if [[ -n "$DOCS_REPO_PATH" && ! -d "$DOCS_REPO_PATH" ]]; then
  echo "ERROR: Repo path not found or not a directory: ${DOCS_REPO_PATH}" >&2
  exit 1
fi

# --- Create output directory ---
mkdir -p "$OUTPUT_DIR"

# --- Determine verify_output ---
if [[ "$MODE" == "fix" ]]; then
  VERIFY=false
else
  VERIFY=true
fi

# --- Build JSON arrays for additional repos ---
if [[ ${#ADDITIONAL_REPOS[@]} -gt 0 ]]; then
  ADDITIONAL_REPOS_JSON="$(printf '%s\n' "${ADDITIONAL_REPOS[@]}" | jq -R . | jq -s .)"
else
  ADDITIONAL_REPOS_JSON="[]"
fi
if [[ ${#ADDITIONAL_CODE_ANALYSIS_DIRS[@]} -gt 0 ]]; then
  ADDITIONAL_ANALYSIS_JSON="$(printf '%s\n' "${ADDITIONAL_CODE_ANALYSIS_DIRS[@]}" | jq -R . | jq -s .)"
else
  ADDITIONAL_ANALYSIS_JSON="[]"
fi

# --- Emit JSON ---
jq -n \
  --arg mode              "$MODE" \
  --arg ticket            "$TICKET" \
  --arg format            "$FORMAT" \
  --arg input_file        "$INPUT_FILE" \
  --arg code_analysis_dir "$CODE_ANALYSIS_DIR" \
  --argjson has_code_analysis "$HAS_CODE_ANALYSIS" \
  --arg pr_analysis_dir   "$PR_ANALYSIS_DIR" \
  --argjson has_pr_analysis "$HAS_PR_ANALYSIS" \
  --arg output_dir          "$OUTPUT_DIR" \
  --arg output_file         "$OUTPUT_FILE" \
  --arg docs_repo_path      "$DOCS_REPO_PATH" \
  --arg source_repo_path    "$SOURCE_REPO" \
  --arg fix_from            "$FIX_FROM" \
  --argjson verify          "$VERIFY" \
  --argjson additional_repo_paths "$ADDITIONAL_REPOS_JSON" \
  --argjson additional_code_analysis_dirs "$ADDITIONAL_ANALYSIS_JSON" \
  '{
    mode:              $mode,
    ticket:            $ticket,
    format:            $format,
    input_file:        $input_file,
    code_analysis_dir: (if $code_analysis_dir == "" then null else $code_analysis_dir end),
    has_code_analysis: $has_code_analysis,
    pr_analysis_dir:   (if $pr_analysis_dir == "" then null else $pr_analysis_dir end),
    has_pr_analysis:   $has_pr_analysis,
    output_dir:        $output_dir,
    output_file:       $output_file,
    docs_repo_path:    (if $docs_repo_path == "" then null else $docs_repo_path end),
    source_repo_path:  (if $source_repo_path == "" then null else $source_repo_path end),
    additional_repo_paths: $additional_repo_paths,
    additional_code_analysis_dirs: $additional_code_analysis_dirs,
    fix_from:          (if $fix_from == "" then null else $fix_from end),
    verify_output:     $verify
  }'
