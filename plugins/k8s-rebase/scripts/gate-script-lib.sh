#!/bin/bash
# gate-script-lib.sh — Shared boilerplate for gate companion scripts.
#
# Source this from companion scripts:
#   source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
#   init_gate "$@"
#   ... your checks ...
#   finish_gate "$NEW_ISSUES" "summary" ["detail1" "detail2" ...]
#
# Provides: REPO, BASE, GATE_NAME, WRITE_REPORT, init_gate, base_has, finish_gate
# Conventions: exit 0 for "nothing to check." Exit 1 for infra failures only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRITE_REPORT="$SCRIPT_DIR/write-gate-report.sh"

_gate_trap() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && -n "${REPO:-}" && -n "${GATE_NAME:-}" ]]; then
    bash "$WRITE_REPORT" "$REPO" "$GATE_NAME" FAIL 1 \
      "Companion script crashed (exit $exit_code)" \
      "Script: ${BASH_SOURCE[1]:-unknown}" \
      "Last command exit code: $exit_code"
  fi
}
trap _gate_trap EXIT

init_gate() {
  REPO="${1:?Usage: $0 <repo-path>}"
  cd "$REPO" || exit 1

  GATE_NAME=$(basename "${BASH_SOURCE[1]}" .sh)
  local step_dir
  step_dir=$(basename "$(dirname "${BASH_SOURCE[1]}")")
  local step_prefix
  step_prefix=$(echo "$step_dir" | grep -oE '^step[0-9]+')
  GATE_NAME="${step_prefix}-${GATE_NAME}"

  BASE=$(git merge-base HEAD main 2>/dev/null \
      || git merge-base HEAD master 2>/dev/null \
      || echo "")
  if [[ -z "$BASE" ]]; then
    echo "NO_BASE: cannot determine merge base — skipping pre-existing filter"
  fi

  NEW_ISSUES=0
}

base_file_has() {
  local file="$1" pattern="$2"
  [[ -z "$BASE" ]] && return 1
  git show "$BASE:$file" 2>/dev/null | grep -qF "$pattern" 2>/dev/null
}

finish_gate() {
  local issues="${1:?Missing issue count}"
  local summary="${2:-"$issues issues found"}"
  shift 2 2>/dev/null || true

  local verdict="PASS"
  [[ "$issues" -gt 0 ]] && verdict=""

  if [[ "$verdict" == "PASS" ]]; then
    bash "$WRITE_REPORT" "$REPO" "$GATE_NAME" PASS 0 "$summary" "$@"
    echo "RESOLVED: $GATE_NAME PASS (companion script)"
  else
    echo "NEW_ISSUES=$issues"
    echo "PENDING: $GATE_NAME ($issues issues need AI judgment)"
    for detail in "$@"; do
      echo "  $detail"
    done
  fi

  trap - EXIT
  exit 0
}
