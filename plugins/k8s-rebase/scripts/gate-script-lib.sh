#!/bin/bash
# gate-script-lib.sh — Shared boilerplate for gate companion scripts.
#
# Source this from companion scripts:
#   source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
#   init_gate "$@"
#   ... your checks ...
#   finish_evidence "N-word summary" ["detail1" "detail2" ...]
#
# Provides: REPO, BASE, GATE_NAME, NEW_ISSUES, WRITE_REPORT, inc, init_gate, base_file_has,
#           finish_evidence
# Conventions: exit 0 always (crash writes .crash, not a verdict).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRITE_REPORT="$SCRIPT_DIR/write-gate-report.sh"

inc() {
  # Safe counter: 0→1 returns rc=1 under set -e without this guard.
  local var="${1:-NEW_ISSUES}"
  printf -v "$var" '%d' "$(( ${!var:-0} + 1 ))"
}

_gate_trap() {
  # Nonzero exit → .crash breadcrumb, NO verdict. Gate falls through to
  # PENDING → subagent, same as a companion-less gate. SIGTERM (exit 0)
  # and SIGKILL (no trap) are handled by the orchestrator; this covers
  # ordinary nonzero exits only.
  local exit_code=$?
  [[ $exit_code -eq 0 ]] && return 0
  if [[ -n "${REPO:-}" && -n "${GATE_NAME:-}" ]]; then
    mkdir -p "$REPO/.rebase-tmp/gates"
    printf 'CRASH: exit %s at %s\n' "$exit_code" "${BASH_SOURCE[1]:-unknown}" \
      > "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash"
  fi
  echo "CRASH: ${GATE_NAME:-?} (exit $exit_code) — no report; deferring to subagent"
}
trap _gate_trap EXIT

init_gate() {
  REPO="${1:?Usage: $0 <repo-path>}"
  cd "$REPO" || exit 1

  GATE_NAME=$(basename "${BASH_SOURCE[1]}" .sh)
  local step_dir
  step_dir=$(basename "$(dirname "${BASH_SOURCE[1]}")")
  local step_prefix
  step_prefix=$(grep -oE '^step[0-9]+' <<< "$step_dir" || true)
  GATE_NAME="${step_prefix}-${GATE_NAME}"
  # Clear any stale crash breadcrumb from a prior failed run so a successful
  # re-run does not leave misleading state alongside the fresh evidence file.
  rm -f "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash" 2>/dev/null || true

  BASE=$(git merge-base HEAD main 2>/dev/null \
      || git merge-base HEAD master 2>/dev/null \
      || git merge-base HEAD origin/main 2>/dev/null \
      || git merge-base HEAD origin/master 2>/dev/null \
      || git merge-base HEAD FETCH_HEAD 2>/dev/null \
      || echo "")
  if [[ -z "$BASE" ]]; then
    echo "NO_BASE: cannot determine merge base — skipping pre-existing filter"
  fi

  NEW_ISSUES=0
}

base_file_has() {
  local file="$1" pattern="$2"
  [[ -z "$BASE" ]] && return 1
  git show "$BASE:$file" 2>/dev/null | grep -qF "$pattern"
}

_head_sha() { git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown; }

_write_evidence() {
  local summary="$1"; shift
  mkdir -p "$REPO/.rebase-tmp/gates"
  local evidence_path="$REPO/.rebase-tmp/gates/${GATE_NAME}.evidence"
  { echo "HEAD: $(_head_sha)"; echo "SUMMARY: $summary"; printf '%s\n' "$@"; } \
    | tee "$evidence_path.tmp"
  mv "$evidence_path.tmp" "$evidence_path"
  echo "PENDING: $GATE_NAME"; echo "EVIDENCE: $evidence_path"
}

finish_evidence() {
  local summary="${1:-}"; shift 2>/dev/null || true
  _write_evidence "$summary" "$@"
  trap - EXIT; exit 0
}
