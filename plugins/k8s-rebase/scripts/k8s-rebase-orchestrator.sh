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
GATES_ROOT="$PLUGIN_ROOT/gates"

STEP_DIRS=("step1-rebase" "step2-compilation" "step3-autofix" "step4-verification")
STEP_COUNT=${#STEP_DIRS[@]}

info() { echo "[orchestrator] $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 2; }

# --- State management ---

state_file() { echo "$1/.rebase-tmp/state.json"; }

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
    grep -o '"current_step": *[0-9]*' "$sf" | grep -o '[0-9]*' || true
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
  [[ -f "$rpt" ]] && grep -qE '^VERDICT: (PASS|FAIL|SKIP|INCONCLUSIVE)' "$rpt"
}

report_is_fresh() {
  local rpt="$1" repo="$2"
  [[ -f "$rpt" ]] || return 1
  local rpt_sha
  rpt_sha=$(awk '/^HEAD: /{print $2}' "$rpt" 2>/dev/null)
  if [[ -z "$rpt_sha" ]]; then
    return 1
  fi
  local cur_sha
  cur_sha=$(git -C "$repo" rev-parse HEAD 2>/dev/null)
  [[ "$rpt_sha" == "$cur_sha" ]]
}

# --- Subcommands ---

cmd_init() {
  local repo="${1:?Usage: $0 init <repo-path> <version>}"
  local version="${2:?Usage: $0 init <repo-path> <version>}"
  repo=$(cd "$repo" && pwd)

  local sf
  sf=$(state_file "$repo")
  local step
  if [[ -f "$sf" ]]; then
    step=$(get_step "$repo")
    info "Resuming at step $step (state.json exists)"
    echo "ORCHESTRATOR_INIT: RESUME"
    # .crash has no HEAD stamp — freshness cannot invalidate a stale one.
    # Clean on both FRESH and RESUME or a prior-run crash reads as current.
    rm -f "$repo/.rebase-tmp/gates/"*.crash 2>/dev/null || true
    # .evidence files are NOT cleared on RESUME. Each evidence file embeds
    # "HEAD: <sha>" (written by gate-script-lib.sh _write_evidence). Subagents
    # MUST verify the HEAD sha matches git rev-parse HEAD before trusting
    # evidence. A companion re-run overwrites evidence atomically (tmp→mv),
    # so only gates that crashed without writing new evidence carry stale data.
  else
    mkdir -p "$repo/.rebase-tmp/gates"
    rm -f "$repo/.rebase-tmp/gates/"*.report   2>/dev/null || true
    rm -f "$repo/.rebase-tmp/gates/"*.crash    2>/dev/null || true
    rm -f "$repo/.rebase-tmp/gates/"*.evidence 2>/dev/null || true
    # Stale advance-attempts counter survives re-init and triggers premature
    # force-advance (cmd_advance fires at attempts≥3).  Cleared on FRESH only:
    # on RESUME the prior count is still meaningful — a gate that failed N times
    # before the session ended has not become easier to pass.
    rm -f "$repo/.rebase-tmp/.advance-attempts-step"* 2>/dev/null || true
    rm -f "$repo/.rebase-tmp/status/INCOMPLETE"        2>/dev/null || true
    write_state "$repo" 1 "$version"
    info "Fresh start for $version"
    echo "ORCHESTRATOR_INIT: FRESH"
  fi

  touch "$repo/.rebase-tmp/.session-active"

  step=$(get_step "$repo")
  local step_dir
  step_dir=$(step_dir_name "$step")
  local expected
  expected=$(count_gate_mds "$step_dir")
  echo "STEP: $step"
  echo "STEP_NAME: $step_dir"
  echo "STEP_FILE: steps/${step_dir}.md"
  echo "GATES_DIR: $GATES_ROOT/$step_dir"
  echo "GATES_EXPECTED: $expected"
}

cmd_gates() {
  local repo="${1:?Usage: $0 gates <repo-path> [step]}"
  repo=$(cd "$repo" && pwd)
  local step="${2:-$(get_step "$repo")}"
  [[ -z "$step" ]] && die "No step specified and no state.json in $repo — run: $0 init <repo-path> <version>"

  local sd
  sd=$(step_dir_name "$step")
  [[ -z "$sd" ]] && die "Invalid step: $step — valid steps are 1-$STEP_COUNT (1=rebase, 2=compilation, 3=autofix, 4=verification)"

  local resolved=0 pending=0

  # Outer timeout: build-vet loops per module (2 tools × GATE_TIMEOUT × modules).
  # Compute once before the gate loop — module count is repo-level, not per-gate.
  local _mods; _mods=$(find "$repo" -name go.mod -not -path '*/vendor/*' -not -path '*/.claude/*' 2>/dev/null | wc -l)
  (( _mods < 1 )) && _mods=1
  local GATE_OUTER_TIMEOUT=$(( 2 * ${GATE_TIMEOUT:-300} * _mods ))
  # Note: ((n++)) exits 1 under set -e when n is 0 before the increment
  # (post-increment returns the old value, which is falsy). The '|| true'
  # on every counter increment prevents that spurious exit.

  while IFS= read -r gate_md; do
    [[ -z "$gate_md" ]] && continue
    local gate_name
    gate_name=$(basename "$gate_md" .md)
    local companion="${gate_md%.md}.sh"
    local rpt
    rpt=$(report_path "$repo" "$sd" "$gate_name")

    # 1. Cache hit — fresh verdict already on disk.
    if [[ -f "$rpt" ]] && report_has_verdict "$rpt" && report_is_fresh "$rpt" "$repo"; then
      local verdict
      verdict=$(awk '/^VERDICT:/{print $2}' "$rpt")
      echo "EXISTING: $gate_name $verdict"
      ((resolved++)) || true
      continue
    fi

    # 2. Run companion exactly once. Companion writes its own .evidence file;
    #    for filter/verdict gates it may also write a .report directly.
    local crash_path
    crash_path=$(report_path "$repo" "$sd" "$gate_name")
    crash_path="${crash_path%.report}.crash"
    local rc=0
    if [[ -f "$crash_path" ]]; then
      echo "PENDING: $gate_name (companion previously crashed — deferring to subagent)"
      ((pending++)) || true
      continue
    fi
    if [[ -x "$companion" ]]; then
      info "Running companion: $(basename "$companion")"
      timeout "$GATE_OUTER_TIMEOUT" bash "$companion" "$repo" 2>&1 || rc=$?
      # rc≥124: timeout (SIGTERM→companion saw exit 0 so _gate_trap wrote nothing)
      # or signal-kill (SIGKILL→no trap). Write the crash breadcrumb here.
      if (( rc >= 124 )); then
        printf 'CRASH: exit %s (orchestrator-detected kill)\n' "$rc" > "$crash_path"
        echo "PENDING: $gate_name (companion crashed — deferring to subagent)"
        ((pending++)) || true
        continue
      fi
    fi

    # 3. Companion wrote a fresh verdict? (filter/verdict clean-path only)
    if [[ -f "$rpt" ]] && report_has_verdict "$rpt" && report_is_fresh "$rpt" "$repo"; then
      local verdict
      verdict=$(awk '/^VERDICT:/{print $2}' "$rpt")
      echo "RESOLVED: $gate_name $verdict (companion)"
      ((resolved++)) || true
      continue
    fi

    # 4. Evidence file is on disk; subagent reads it by convention.
    #    Gates with no companion land here too (no .evidence; subagent judges
    #    from scratch).
    echo "PENDING: $gate_name"
    ((pending++)) || true
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

  local step_dir
  step_dir=$(step_dir_name "$step")
  [[ -z "$step_dir" ]] && die "Invalid step: $step — valid steps are 1-$STEP_COUNT (1=rebase, 2=compilation, 3=autofix, 4=verification)"

  local missing=() stale=() failing=()

  while IFS= read -r gate_md; do
    [[ -z "$gate_md" ]] && continue
    local gate_name
    gate_name=$(basename "$gate_md" .md)
    local report_file
    report_file=$(report_path "$repo" "$step_dir" "$gate_name")

    if [[ ! -f "$report_file" ]]; then
      missing+=("$step_dir/$gate_name")
      continue
    fi

    if ! report_has_verdict "$report_file"; then
      missing+=("$step_dir/$gate_name (no verdict)")
      continue
    fi

    if ! report_is_fresh "$report_file" "$repo"; then
      stale+=("$step_dir/$gate_name")
      continue
    fi

    if ! report_has_pass "$report_file"; then
      failing+=("$step_dir/$gate_name")
    fi
  done < <(list_gate_files "$step_dir")

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

  # Track blocked-advance attempts; force-advance when threshold is reached
  local -r FORCE_ADVANCE_THRESHOLD=3
  local attempts_file="$repo/.rebase-tmp/.advance-attempts-step${step}"
  # Default to 1 on first blocked call (no file yet); subsequent calls increment
  # the persisted value, so call-3 produces attempts=3 and fires force-advance.
  local attempts=1
  if [[ -f "$attempts_file" ]]; then
    attempts=$(( $(cat "$attempts_file") + 1 ))
  fi
  echo "$attempts" > "$attempts_file"

  if [[ "$attempts" -ge "$FORCE_ADVANCE_THRESHOLD" ]]; then
    # Threshold met: advance unconditionally and record what was unresolved.
    # The attempts file is removed so the next step starts with a clean counter.
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
    return 2
  fi

  echo "BLOCKED: step $step"
  echo "ADVANCE_ATTEMPTS: $attempts/$FORCE_ADVANCE_THRESHOLD"
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
    local incomplete_file="$repo/.rebase-tmp/status/INCOMPLETE"
    if [[ -f "$incomplete_file" ]]; then
      echo "WARNING: state reconstructed from disk; a prior force-advance was recorded:"
      cat "$incomplete_file"
      echo ""
    fi
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
      elif ! report_is_fresh "$rpt" "$repo"; then
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
      local gate_name
      gate_name=$(basename "$gate_md" .md)
      local rpt
      rpt=$(report_path "$repo" "$sd" "$gate_name")
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
