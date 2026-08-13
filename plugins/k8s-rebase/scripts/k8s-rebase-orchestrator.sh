#!/bin/bash
# k8s-rebase-orchestrator.sh — State machine + gate runner for k8s-rebase.
#
# Unified script that enforces step ordering, runs companion gate scripts,
# and provides status for the Stop hook and test harness.
#
# Usage:
#   k8s-rebase-orchestrator.sh init   <repo-path> <version>
#   k8s-rebase-orchestrator.sh gates  <repo-path> [<step>]
#   k8s-rebase-orchestrator.sh advance <repo-path>
#   k8s-rebase-orchestrator.sh status <repo-path>
#
# Exit codes: 0=success, 1=blocked (normal), 2=usage error, 3+=internal error

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WRITE_REPORT="$PLUGIN_ROOT/scripts/write-gate-report.sh"
GATES_ROOT="$PLUGIN_ROOT/gates"

STEP_DIRS=("step1-rebase" "step2-compilation" "step3-autofix" "step4-verification")
STEP_COUNT=${#STEP_DIRS[@]}

info() { echo "[orchestrator] $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 2; }

# --- State management ---

state_file() { echo "$1/.rebase-tmp/state.json"; }

read_state() {
  local sf
  sf=$(state_file "$1")
  if [[ -f "$sf" ]]; then
    cat "$sf"
  else
    echo "{}"
  fi
}

get_version() {
  local sf
  sf=$(state_file "$1")
  [[ -f "$sf" ]] && grep -o '"version": *"[^"]*"' "$sf" | sed 's/.*"\([^"]*\)"/\1/' || echo ""
}

write_state() {
  local repo="$1" step="$2" version="${3:-$(get_version "$repo")}"
  local sf
  sf=$(state_file "$repo")
  mkdir -p "$(dirname "$sf")"
  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  cat > "${sf}.tmp" <<JSONEOF
{
  "repo": "$repo",
  "version": "$version",
  "current_step": $step,
  "updated_at": "$now"
}
JSONEOF
  mv "${sf}.tmp" "$sf"
}

get_step() {
  local repo="$1"
  local sf
  sf=$(state_file "$repo")
  if [[ -f "$sf" ]]; then
    grep -o '"current_step": *[0-9]*' "$sf" | grep -o '[0-9]*'
  else
    echo ""
  fi
}

# --- Gate helpers ---

step_dir_name() {
  local step_num="$1"
  if [[ "$step_num" -ge 1 && "$step_num" -le "$STEP_COUNT" ]]; then
    echo "${STEP_DIRS[$((step_num - 1))]}"
  else
    echo ""
  fi
}

count_gate_mds() {
  local gate_dir="$GATES_ROOT/$1"
  [[ -d "$gate_dir" ]] || { echo 0; return; }
  find "$gate_dir" -maxdepth 1 -name '*.md' -type f | wc -l
}

count_reports() {
  local repo="$1" step_dir_prefix="$2"
  local report_dir="$repo/.rebase-tmp/gates"
  [[ -d "$report_dir" ]] || { echo 0; return; }
  find "$report_dir" -maxdepth 1 -name "${step_dir_prefix%-*}-*.report" -type f | wc -l
}

list_gate_files() {
  local gate_dir="$GATES_ROOT/$1"
  [[ -d "$gate_dir" ]] || return
  find "$gate_dir" -maxdepth 1 -name '*.md' -type f | sort
}

report_path() {
  local repo="$1" step_dir="$2" gate_name="$3"
  local prefix="${step_dir%-*}"
  echo "$repo/.rebase-tmp/gates/${prefix}-${gate_name}.report"
}

report_has_pass() {
  local rpt="$1"
  [[ -f "$rpt" ]] && grep -q '^VERDICT: PASS' "$rpt"
}

report_has_verdict() {
  local rpt="$1"
  [[ -f "$rpt" ]] && grep -qE '^VERDICT: (PASS|FAIL|SKIP)' "$rpt"
}

report_is_fresh() {
  local rpt="$1" repo="$2"
  [[ -f "$rpt" ]] || return 1
  local rpt_sha
  rpt_sha=$(grep '^HEAD: ' "$rpt" 2>/dev/null | awk '{print $2}')
  if [[ -z "$rpt_sha" ]]; then
    return 1
  fi
  local cur_sha
  cur_sha=$(cd "$repo" && git rev-parse HEAD 2>/dev/null)
  [[ "$rpt_sha" == "$cur_sha" ]]
}

# --- Subcommands ---

cmd_init() {
  local repo="${1:?Usage: $0 init <repo-path> <version>}"
  local version="${2:?Usage: $0 init <repo-path> <version>}"
  repo=$(cd "$repo" && pwd)

  local sf
  sf=$(state_file "$repo")
  if [[ -f "$sf" ]]; then
    local step
    step=$(get_step "$repo")
    info "Resuming at step $step (state.json exists)"
    echo "ORCHESTRATOR_INIT: RESUME"
  else
    mkdir -p "$repo/.rebase-tmp/gates"
    rm -f "$repo/.rebase-tmp/gates/"*.report 2>/dev/null || true
    write_state "$repo" 1 "$version"
    info "Fresh start for $version"
    echo "ORCHESTRATOR_INIT: FRESH"
  fi

  touch "$repo/.rebase-tmp/.session-active"

  local step
  step=$(get_step "$repo")
  local sd
  sd=$(step_dir_name "$step")
  local expected
  expected=$(count_gate_mds "$sd")
  echo "STEP: $step"
  echo "STEP_NAME: $sd"
  echo "STEP_FILE: steps/${sd}.md"
  echo "GATES_DIR: $GATES_ROOT/$sd"
  echo "GATES_EXPECTED: $expected"
}

cmd_gates() {
  local repo="${1:?Usage: $0 gates <repo-path> [step]}"
  repo=$(cd "$repo" && pwd)
  local step="${2:-$(get_step "$repo")}"
  [[ -z "$step" ]] && die "No step specified and no state.json"

  local sd
  sd=$(step_dir_name "$step")
  [[ -z "$sd" ]] && die "Invalid step: $step"

  local resolved=0 pending=0

  while IFS= read -r gate_md; do
    [[ -z "$gate_md" ]] && continue
    local gate_name
    gate_name=$(basename "$gate_md" .md)
    local companion="${gate_md%.md}.sh"
    local rpt
    rpt=$(report_path "$repo" "$sd" "$gate_name")

    if [[ -f "$rpt" ]] && report_has_verdict "$rpt" && report_is_fresh "$rpt" "$repo"; then
      local verdict
      verdict=$(grep '^VERDICT:' "$rpt" | awk '{print $2}')
      echo "EXISTING: $gate_name $verdict"
      ((resolved++)) || true
      continue
    fi

    if [[ -x "$companion" ]]; then
      info "Running companion: $(basename "$companion")"
      local output
      if output=$(timeout "${GATE_TIMEOUT:-300}" bash "$companion" "$repo" 2>&1); then
        if echo "$output" | grep -q 'NEW_ISSUES=0'; then
          echo "RESOLVED: $gate_name PASS (companion script)"
          ((resolved++)) || true
          continue
        fi
      fi
      echo "$output"
      echo "PENDING: $gate_name (companion found issues)"
      ((pending++)) || true
    else
      echo "PENDING: $gate_name (no companion script)"
      ((pending++)) || true
    fi
  done < <(list_gate_files "$sd")

  echo "---"
  echo "RESOLVED: $resolved"
  echo "PENDING: $pending"
  [[ "$pending" -gt 0 ]] && return 1
  return 0
}

cmd_advance() {
  local repo="${1:?Usage: $0 advance <repo-path>}"
  repo=$(cd "$repo" && pwd)
  local step
  step=$(get_step "$repo")
  [[ -z "$step" ]] && die "No state.json — run init first"

  local sd
  sd=$(step_dir_name "$step")
  [[ -z "$sd" ]] && die "Invalid step: $step"

  local missing=() stale=() failing=()

  while IFS= read -r gate_md; do
    [[ -z "$gate_md" ]] && continue
    local gate_name
    gate_name=$(basename "$gate_md" .md)
    local rpt
    rpt=$(report_path "$repo" "$sd" "$gate_name")

    if [[ ! -f "$rpt" ]]; then
      missing+=("$sd/$gate_name")
      continue
    fi

    if ! report_has_verdict "$rpt"; then
      missing+=("$sd/$gate_name (no verdict)")
      continue
    fi

    if ! report_is_fresh "$rpt" "$repo"; then
      stale+=("$sd/$gate_name")
      continue
    fi

    if ! report_has_pass "$rpt"; then
      failing+=("$sd/$gate_name")
    fi
  done < <(list_gate_files "$sd")

  local total_issues=$(( ${#missing[@]} + ${#stale[@]} + ${#failing[@]} ))

  if [[ "$total_issues" -eq 0 ]]; then
    local next_step=$((step + 1))
    if [[ "$next_step" -gt "$STEP_COUNT" ]]; then
      write_state "$repo" "$((STEP_COUNT + 1))"
      echo "DONE: all steps complete"
      return 0
    fi
    write_state "$repo" "$next_step"
    local next_sd
    next_sd=$(step_dir_name "$next_step")
    echo "STEP_COMPLETE: $step"
    echo "STEP: $next_step"
    echo "STEP_NAME: $next_sd"
    echo "STEP_FILE: steps/${next_sd}.md"
    return 0
  fi

  # Count advance attempts
  local attempts_file="$repo/.rebase-tmp/.advance-attempts-step${step}"
  local attempts=1
  if [[ -f "$attempts_file" ]]; then
    attempts=$(( $(cat "$attempts_file") + 1 ))
  fi
  echo "$attempts" > "$attempts_file"

  if [[ "$attempts" -ge 3 ]]; then
    info "Force-advancing after $attempts attempts"
    local next_step=$((step + 1))
    if [[ "$next_step" -gt "$STEP_COUNT" ]]; then
      write_state "$repo" "$((STEP_COUNT + 1))"
    else
      write_state "$repo" "$next_step"
    fi
    rm -f "$attempts_file"

    mkdir -p "$repo/.rebase-tmp/status"
    {
      echo "INCOMPLETE: step $step force-advanced after $attempts attempts"
      echo "MISSING: ${missing[*]:-none}"
      echo "STALE: ${stale[*]:-none}"
      echo "FAILING: ${failing[*]:-none}"
      echo "TIMESTAMP: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$repo/.rebase-tmp/status/INCOMPLETE"

    echo "FORCE_ADVANCE: step $step (after $attempts attempts)"
    echo "WARNING: ${#missing[@]} missing, ${#stale[@]} stale, ${#failing[@]} failing"
    return 0
  fi

  echo "BLOCKED: step $step"
  echo "ADVANCE_ATTEMPTS: $attempts/3"
  [[ ${#missing[@]} -gt 0 ]] && echo "MISSING: ${missing[*]}"
  [[ ${#stale[@]} -gt 0 ]] && echo "STALE: ${stale[*]}"
  [[ ${#failing[@]} -gt 0 ]] && echo "FAILING: ${failing[*]}"

  echo ""
  echo "Run these gates:"
  for g in "${missing[@]}" "${stale[@]}" "${failing[@]}"; do
    echo "  $GATES_ROOT/${g}.md"
  done
  return 1
}

cmd_status() {
  local repo="${1:?Usage: $0 status <repo-path>}"
  repo=$(cd "$repo" && pwd)

  local step
  step=$(get_step "$repo")

  if [[ -z "$step" ]]; then
    step=$(reconstruct_step "$repo")
  fi

  if [[ "$step" -gt "$STEP_COUNT" ]]; then
    echo "STATE: done"
    echo "DONE: true"
    return 0
  fi

  printf "%-25s %s  %s  %s  %s\n" "STEP" "EXPECTED" "PASS" "FAIL" "MISSING"
  for i in $(seq 1 "$STEP_COUNT"); do
    local sd
    sd=$(step_dir_name "$i")
    local expected
    expected=$(count_gate_mds "$sd")
    local pass=0 fail=0 miss=0

    while IFS= read -r gate_md; do
      [[ -z "$gate_md" ]] && continue
      local gate_name
      gate_name=$(basename "$gate_md" .md)
      local rpt
      rpt=$(report_path "$repo" "$sd" "$gate_name")

      if [[ ! -f "$rpt" ]] || ! report_has_verdict "$rpt"; then
        ((miss++)) || true
      elif report_has_pass "$rpt"; then
        ((pass++)) || true
      else
        ((fail++)) || true
      fi
    done < <(list_gate_files "$sd")

    local marker=""
    [[ "$i" -eq "$step" ]] && marker=" ← current"
    printf "%-25s %8d  %4d  %4d  %7d%s\n" "$sd" "$expected" "$pass" "$fail" "$miss" "$marker"
  done

  echo ""
  echo "CURRENT: $step"
  echo "STEP_NAME: $(step_dir_name "$step")"
  echo "STEP_FILE: steps/$(step_dir_name "$step").md"
  echo "DONE: false"
}

reconstruct_step() {
  local repo="$1"
  for i in $(seq 1 "$STEP_COUNT"); do
    local sd
    sd=$(step_dir_name "$i")
    # Count PASS reports only — FAIL reports don't mean the step is done
    local pass_count=0
    while IFS= read -r gate_md; do
      [[ -z "$gate_md" ]] && continue
      local gn
      gn=$(basename "$gate_md" .md)
      local rpt
      rpt=$(report_path "$repo" "$sd" "$gn")
      [[ -f "$rpt" ]] && report_has_pass "$rpt" && ((pass_count++)) || true
    done < <(list_gate_files "$sd")
    local expected
    expected=$(count_gate_mds "$sd")
    if [[ "$pass_count" -lt "$expected" ]]; then
      echo "$i"
      return
    fi
  done
  echo "$((STEP_COUNT + 1))"
}

# --- Main ---

cmd="${1:-}"
shift || true

case "$cmd" in
  init)    cmd_init "$@" ;;
  gates)   cmd_gates "$@" ;;
  advance) cmd_advance "$@" ;;
  status)  cmd_status "$@" ;;
  *)       die "Usage: $0 {init|gates|advance|status} <repo-path> [args...]" ;;
esac
