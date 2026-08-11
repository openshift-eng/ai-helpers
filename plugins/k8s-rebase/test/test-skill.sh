#!/bin/bash
# test-skill.sh — Test the k8s-rebase skill by running it blind (without
# patterns doc or autofix functions) and verifying the results are correct.
#
# Use via Makefile:  cd plugins/k8s-rebase && make help

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="${PLUGIN_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-$(cd "$PLUGIN_DIR/../.." 2>/dev/null && pwd || echo /tmp)/.work/test-harness}"
REPOS_DIR="${REPOS_DIR:-$SCRIPT_DIR/.repos}"
_repos_parent="$(cd "$(dirname "$REPOS_DIR")" 2>/dev/null && pwd)"
[[ -z "$_repos_parent" ]] && { echo "ERROR: Cannot resolve REPOS_DIR: parent dir '$(dirname "$REPOS_DIR")' does not exist" >&2; exit 1; }
REPOS_DIR="$_repos_parent/$(basename "$REPOS_DIR")"
PERMISSION_MODE="${PERMISSION_MODE:-bypassPermissions}"
# Model for court analysis — set explicitly so court doesn't fall back to
# an unavailable model (e.g. Opus 5 on Vertex) and produce no output.
# Override with COURT_MODEL=<model> if needed.
COURT_MODEL="${COURT_MODEL:-claude-sonnet-4-6}"
CONFIG_FILE="$(cd "$(dirname "${CONFIG_FILE:-$SCRIPT_DIR/config.yaml}")" && pwd)/$(basename "${CONFIG_FILE:-$SCRIPT_DIR/config.yaml}")"
_MAX_CONCURRENT_FROM_ENV="${MAX_CONCURRENT:-}"
MAX_CONCURRENT="${MAX_CONCURRENT:-2}"
# INFO_GATES — space-separated list of BARE gate names (no step prefix).
# Gates in this list are counted as SKIP rather than FAIL when their verdict
# is not PASS.  They are matched against report filenames after stripping the
# leading stepN- prefix (e.g. step4-dep-cve-check -> dep-cve-check).
# Update this list whenever a new advisory-only gate is added to gates/step*/.
INFO_GATES="dep-cve-check skill-improvement commit-messages maintainer-review"

# ── Utilities ──────────────────────────────────────────────────────────

info()  { echo ":: $*" >&2; }
warn()  { echo "WARNING: $*" >&2; }
error() { echo "ERROR: $*" >&2; }
die()   { error "$@"; exit 1; }
repo_short() { local p="${1%/}"; echo "${p/#$REPOS_DIR\//}"; }
repo_key() { repo_short "$1" | tr '/' '_'; }
running_key() { echo "${1:?version}_$(repo_key "${2:?repo}")"; }
repo_key_from_running() { echo "${2#"${1:?version}"_}"; }

_latest_result_line() {
  # results.tsv cols: 1=ts 2=ver 3=spec 4=repo 5=verdict 6=detail
  # Returns the most recent line for this repo+version with spec all* or none.
  local short="$1" ver="$2" tsv="$3"
  awk -F'\t' -v r="$short" -v v="$ver" '$4==r && $2==v && ($3~/^all/ || $3=="none")' "$tsv" | tail -1
}

_ensure_repo() {
  local name="$1"
  local dest="$REPOS_DIR/$name"
  if [[ -d "$dest/.git" ]]; then
    git -C "$dest" rev-parse HEAD &>/dev/null && return 0
    warn "Removing broken clone: $dest"
    rm -rf "$dest"
  fi
  info "Cloning $name (this may take a few minutes)..."
  mkdir -p "$(dirname "$dest")"
  if ! git clone --single-branch --no-tags "https://github.com/${name}.git" "$dest" 2>&1 | tail -1 >&2; then
    error "Clone failed: $name"
    rm -rf "$dest"
    return 1
  fi
  info "Cloned $name"
}

_done_key() { local s="${2//[:\/\ ]/_}"; echo "${1}_${s}_$3"; }

_worktree_info() {
  _WT_PATH="" _WT_BRANCH=""
  local _wt_line
  _wt_line=$(git -C "$1" worktree list 2>/dev/null | grep '\.claude/worktrees' | tail -1)
  [[ -z "$_wt_line" ]] && return 1
  _WT_PATH="${_wt_line%% *}"
  [[ "$_wt_line" =~ \[([^]]+)\] ]] && _WT_BRANCH="${BASH_REMATCH[1]/ locked/}"
}

# Collect gate report directories from ALL worktrees (+ main repo).
# Sets _GATE_DIRS array.  Fixes false negatives when reports are split
# across two worktrees (e.g. 1 report in wt-A + 32 in wt-B = 33 total).
_collect_gate_dirs() {
  _GATE_DIRS=()
  local _repo="$1"
  [[ -d "$_repo/.rebase-tmp/gates" ]] && _GATE_DIRS+=("$_repo/.rebase-tmp/gates")
  while IFS= read -r _wt_line; do
    local _wtp; _wtp="${_wt_line%% *}"
    [[ -d "$_wtp/.rebase-tmp/gates" ]] && _GATE_DIRS+=("$_wtp/.rebase-tmp/gates")
  done < <(git -C "$_repo" worktree list 2>/dev/null | grep -F '.claude/worktrees')
}

# Tally gate reports across one or more directories.
# Accepts variadic args: _tally_gates dir1 [dir2 ...]
# When the same gate name exists in multiple dirs, the newest file wins.
_tally_gates() {
  local _gt=0 _gfail=0 _gs=0 _gfail_names=""
  # Collect all gate files, dedup by gate name (newest wins)
  local -A _gate_files=()
  for _gdir in "$@"; do
    [[ -d "$_gdir" ]] || continue
    for _gf_file in "$_gdir"/*.report; do
      [[ -f "$_gf_file" ]] || continue
      local _gn=$(basename "$_gf_file" .report)
      if [[ -z "${_gate_files[$_gn]+x}" ]]; then
        _gate_files[$_gn]="$_gf_file"
      else
        local _old_ts=$(stat -c '%Y' "${_gate_files[$_gn]}" 2>/dev/null || echo 0)
        local _new_ts=$(stat -c '%Y' "$_gf_file" 2>/dev/null || echo 0)
        [[ "$_new_ts" -gt "$_old_ts" ]] && _gate_files[$_gn]="$_gf_file"
      fi
    done
  done
  # Stale-report detection: cache branch-tip timestamp per gate dir
  local -A _tip_cache=()
  for _gn in "${!_gate_files[@]}"; do
    local _gf_file="${_gate_files[$_gn]}"
    _gt=$((_gt + 1))
    local _gdir="${_gf_file%/*}"
    if [[ -z "${_tip_cache[$_gdir]+x}" ]]; then
      local _repo_root="${_gdir%/.rebase-tmp/gates}"
      local _ts=0
      if [[ -d "$_repo_root/.git" || -f "$_repo_root/.git" ]]; then
        _ts=$(git -C "$_repo_root" log -1 --format='%ct' 2>/dev/null || echo 0)
      fi
      _tip_cache[$_gdir]="$_ts"
    fi
    local _branch_tip_ts="${_tip_cache[$_gdir]}"
    local _gv=$(grep -iE '^(VERDICT|STATUS|RESULT):' "$_gf_file" 2>/dev/null | head -1)
    _gv="${_gv^^}"
    # If the AI wrote PASS but the companion evidence says SKIP, honour the evidence.
    local _ev_file="${_gf_file%.report}.evidence"
    if [[ "$_gv" == *PASS* && -f "$_ev_file" ]] && grep -qiE '^SUMMARY:[[:space:]]*SKIP:' "$_ev_file"; then
      _gv="SKIP:"
    fi
    if [[ "$_gv" == *SKIP* || " $INFO_GATES " == *" ${_gn#step?-} "* ]]; then
      _gs=$((_gs + 1))
    elif [[ "$_gv" == *PASS* ]]; then
      : # counted in _gt
    else
      # FAIL or missing verdict — check if report predates the branch tip
      if _is_stale_fail "$_gf_file" "$_branch_tip_ts"; then
        _gs=$((_gs + 1))
      else
        _gfail=$((_gfail + 1))
        _gfail_names="${_gfail_names:+$_gfail_names,}${_gn}"
      fi
    fi
  done
  echo "$_gt $_gfail $_gs $_gfail_names"
}

_is_stale_fail() {
  local _file="$1" _tip_ts="$2"
  local _rts; _rts=$(stat -c '%Y' "$_file" 2>/dev/null || echo 0)
  [[ "$_rts" -gt 0 && "$_tip_ts" -gt "$_rts" ]]
}

# EXPECTED_GATES is computed at load time by counting every .md in the gates tree.
# It self-updates when gate .md files are added or removed — no manual change needed.
# WARNING: do NOT add README.md or other non-gate .md files under gates/ — every
# .md found by this find increments the expected count and will cause gate-complete
# checks to wait for a report that never arrives.
EXPECTED_GATES=$(find "$PLUGIN_DIR/gates" -name '*.md' 2>/dev/null | wc -l)
[[ "$EXPECTED_GATES" -lt 1 ]] && die "Gates directory missing or empty — cannot determine expected gate count"

# _check_evidence_paths performs forward-only checking: each .sh companion must
# have a matching .md with the correct EVIDENCE path.
# The REVERSE check (orphaned EVIDENCE blocks in .md without a companion .sh)
# is only in test/assert-evidence-paths.sh, which is run separately.
# These two are NOT redundant — they cover complementary failure modes.
_check_evidence_paths() {
  local companions=0 markers=0 mismatches=0
  for _sh in "$PLUGIN_DIR/gates"/step*/*.sh; do
    [[ -f "$_sh" ]] || continue
    companions=$(( companions + 1 ))
    local _dir_name; _dir_name=$(basename "$(dirname "$_sh")")
    local _step_prefix="${_dir_name%%-*}"
    local _gate_name; _gate_name=$(basename "$_sh" .sh)
    local _expected_path="${_step_prefix}-${_gate_name}.evidence"
    local _md="${_sh%.sh}.md"
    if [[ ! -f "$_md" ]]; then
      warn "evidence-path check: no gate .md for companion $_sh"
      mismatches=$(( mismatches + 1 ))
      continue
    fi
    if ! grep -qF "EVIDENCE (read before judging):" "$_md"; then
      warn "evidence-path check: missing EVIDENCE block in $(basename "$_md")"
      mismatches=$(( mismatches + 1 ))
    elif ! grep -q "$_expected_path" "$_md"; then
      warn "evidence-path check: wrong evidence path in $(basename "$_md") (expected $_expected_path)"
      mismatches=$(( mismatches + 1 ))
    else
      markers=$(( markers + 1 ))
    fi
  done
  if [[ "$mismatches" -gt 0 ]]; then
    warn "evidence-path check: $markers/$companions companions have correct EVIDENCE blocks ($mismatches mismatches)"
  fi
}

# Load config from YAML
_config_val() { yq ".repos.\"$1\".${2} // \"\"" "$CONFIG_FILE"; }

_resolve_known_good() {
  local name="$1" repo_dir="$2"
  local _rk="${name//\//\_}"
  local _ver="${VERSION//./_}"
  local _cache="$PLUGIN_DIR/test/.matrix-state/known_good_resolved_${_rk}_${_ver}"
  if [[ -f "$_cache" ]]; then
    local _cached=$(cat "$_cache")
    git -C "$repo_dir" rev-parse --verify "$_cached" &>/dev/null && echo "$_cached" && return 0
  fi
  local kg=$(yq ".repos.\"$name\".known_good // \"\"" "$CONFIG_FILE")
  [[ -z "$kg" || "$kg" == "null" ]] && return 1
  local resolved=""
  # Plain-string path: $kg is a local branch or tag name.  $resolved stays a
  # mutable ref — the caller's git-diff always compares against the branch's
  # current HEAD.  The cache avoids repeated yq + rev-parse overhead but does
  # not freeze a commit.
  # URL+ref path: resolves FETCH_HEAD to a full SHA → cache is immutable.
  if ! yq -e ".repos.\"$name\".known_good.url" "$CONFIG_FILE" &>/dev/null; then
    git -C "$repo_dir" rev-parse --verify "$kg" &>/dev/null || return 1
    resolved="$kg"
  else
    local url ref
    url=$(yq ".repos.\"$name\".known_good.url" "$CONFIG_FILE")
    ref=$(yq ".repos.\"$name\".known_good.ref" "$CONFIG_FILE")
    [[ -z "$url" || "$url" == "null" || -z "$ref" || "$ref" == "null" ]] && return 1
    git -C "$repo_dir" fetch "$url" "$ref" &>/dev/null \
      || { warn "Could not fetch known-good $ref from $url"; return 1; }
    resolved=$(git -C "$repo_dir" rev-parse FETCH_HEAD)
  fi
  mkdir -p "$(dirname "$_cache")"
  echo "$resolved" > "$_cache"
  echo "$resolved"
}

_load_config() {
  command -v yq &>/dev/null || die "yq required — install from https://github.com/mikefarah/yq"
  [[ -f "$CONFIG_FILE" ]] || die "Config not found: $CONFIG_FILE"
  VERSION=$(yq '.version' "$CONFIG_FILE")
  [[ -z "$VERSION" || "$VERSION" == "null" ]] && die "version not set in $CONFIG_FILE"
  local _mc=$(yq '.max_concurrent // ""' "$CONFIG_FILE")
  if [[ -n "${_MAX_CONCURRENT_FROM_ENV}" ]]; then
    MAX_CONCURRENT="$_MAX_CONCURRENT_FROM_ENV"
  elif [[ -n "$_mc" && "$_mc" != "null" ]]; then
    MAX_CONCURRENT="$_mc"
  fi
  DEFAULT_REPOS=()
  while IFS= read -r repo_short; do
    [[ -n "$repo_short" ]] && DEFAULT_REPOS+=("$REPOS_DIR/$repo_short")
  done < <(yq '.repos | keys | .[]' "$CONFIG_FILE")
  [[ ${#DEFAULT_REPOS[@]} -gt 0 ]] || die "No repos configured in $CONFIG_FILE — 'repos' key is missing or empty"
  # Validate from_commit SHAs exist in repos
  for _repo_name in $(yq '.repos | keys | .[]' "$CONFIG_FILE"); do
    local fc=$(_config_val "$_repo_name" "from_commit")
    if [[ -n "$fc" && -d "$REPOS_DIR/$_repo_name" ]]; then
      if ! git -C "$REPOS_DIR/$_repo_name" rev-parse --verify "$fc^{commit}" &>/dev/null; then
        local _actual=$(git -C "$REPOS_DIR/$_repo_name" rev-parse "${fc:0:12}" 2>/dev/null)
        if [[ -n "$_actual" && "$_actual" != "$fc" ]]; then
          die "$_repo_name: from_commit SHA mismatch — config has $fc but repo resolves ${fc:0:12} to $_actual"
        else
          warn "$_repo_name: from_commit $fc not found locally (may need git fetch)"
        fi
      fi
    fi
  done
}
_load_config

_repo_k8s_version() {
  local repo="$1" ref="${2:-origin/$(git -C "$1" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')}"
  [[ "$ref" == "origin/" ]] && ref="origin/main"
  git -C "$repo" rev-parse --verify "$ref" &>/dev/null || ref="origin/master"
  local ver=$(git -C "$repo" show "${ref}:go.mod" 2>/dev/null | grep 'k8s.io/api ' | grep -oE 'v[0-9.]+' | head -1)
  if [[ -z "$ver" ]]; then
    ver=$(git -C "$repo" ls-tree -r --name-only "$ref" 2>/dev/null \
      | grep '/go.mod$' | head -1 \
      | xargs -I{} git -C "$repo" show "${ref}:{}" 2>/dev/null \
      | grep 'k8s.io/api ' | grep -oE 'v[0-9.]+' | head -1)
  fi
  echo "$ver"
}

_set_worktree_base() {
  local repo="$1" mode="${2:-head}" p="$repo/.claude/settings.json"
  if [[ "$mode" == "remove" ]]; then
    rm -f "$p"
  else
    mkdir -p "$repo/.claude"
    jq -n --arg m "$mode" '{"worktree":{"baseRef":$m}}' > "$p"
  fi
}

_session_alive() {
  local sid="$1"
  [[ -z "$sid" ]] && return 1
  build_session_cache
  echo "$_SESSION_CACHE" | while IFS=$'\t' read -r _cwd _st _el _pid _sid _rest; do
    [[ "$_sid" == "$sid"* ]] && [[ "$_st" == "working" ]] && echo "yes" && break
    # NOTE: 'working' is the only live state reported by `claude agents --json`.
    # If the claude CLI adds new active states (e.g. 'thinking'), update this check.
  done | grep -q yes
}

resolve_repo() {
  local r="${1%/}"
  [[ -z "$r" ]] && return 1
  # Prefer $REPOS_DIR/ expansion for short names (avoids CWD-relative false hits)
  [[ -d "$REPOS_DIR/$r" ]] && { echo "$REPOS_DIR/$r"; return 0; }
  [[ -d "$r" ]] && { (cd "$r" && pwd); return 0; }
  return 1
}

default_branch() {
  local b
  b=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
  [[ -z "$b" ]] && b="main"
  git rev-parse --verify "$b" &>/dev/null \
    || git rev-parse --verify "origin/$b" &>/dev/null \
    || b="master"
  echo "$b"
}

# ── Session Management ─────────────────────────────────────────────────

_SESSION_CACHE=""
_SESSION_CACHE_AGE=0

_SESSION_PARSER=$(cat <<'PYEOF'
import json, sys, time
try:
    data = json.load(sys.stdin)
    if not isinstance(data, list): sys.exit(0)
except (json.JSONDecodeError, ValueError): sys.exit(0)
now = time.time() * 1000
for s in data:
    try:
        cwd = s.get('cwd', '')
        raw_state = s.get('state')
        raw_status = s.get('status')
        if raw_state == 'working' and raw_status == 'done':
            st = raw_status  # state='working'+status='done' means the agent finished; promote to 'done' so session_for_repo skips it
        else:
            st = raw_state or raw_status or '?'
        pid = s.get('pid') or '0'
        full_sid = s.get('sessionId', '?')
        sid = s.get('id') or full_sid[:8]
        started = s.get('startedAt', 0)
        try:
            elapsed = max(0, int((now - started) / 60000)) if started else 0
        except TypeError:
            elapsed = 0  # startedAt was not a number (e.g. ISO string); treat as unknown
        # done is done — don't remap to idle even if PID lingers
        print(f'{cwd}\t{st}\t{elapsed}\t{pid}\t{sid}\t{full_sid}')
    except (TypeError, ValueError): pass
PYEOF
)

build_session_cache() {
  local now=$(date +%s)
  [[ $((now - _SESSION_CACHE_AGE)) -lt 5 ]] && return 0
  command -v claude &>/dev/null || { _SESSION_CACHE_AGE=$now; return 0; }
  _SESSION_CACHE=$(claude agents --json 2>/dev/null \
    | python3 -c "$_SESSION_PARSER" 2>/dev/null || true)
  _SESSION_CACHE_AGE=$now
}


session_for_repo() {
  local repo="$1" short
  short=$(repo_short "$repo")
  local match=""
  while IFS=$'\t' read -r cwd state elapsed pid _rest; do
    [[ "$cwd" == *"/${short}/"* || "$cwd" == *"/${short}" ]] || continue
    [[ "$state" != "working" ]] && continue
    [[ "$pid" == "0" ]] && continue
    kill -0 "$pid" 2>/dev/null || continue
    if [[ "$cwd" == *"/.claude/worktrees/"* && ! -d "$cwd" ]]; then
      continue
    fi
    match="$cwd	$state	$elapsed	$pid	$_rest"  # no break: last match wins when multiple sessions share the repo
  done <<< "$_SESSION_CACHE"
  [[ -n "$match" ]] && echo "$match"
}

# ── Session Commands ───────────────────────────────────────────────────

find_newest_branch() {
  local repo="$1" version="${2:-}"
  (cd "$repo" 2>/dev/null || return 1
  # Phase 1: active worktrees (bump or worktree-k8s-rebase branches)
  local wt_line
  if [[ -n "$version" ]]; then
    wt_line=$(git worktree list 2>/dev/null | grep '\.claude/worktrees' | grep -E "bump${version%.*}|k8s-rebase-${version}" | tail -1)
  else
    wt_line=$(git worktree list 2>/dev/null | grep '\.claude/worktrees' | tail -1)
  fi
  if [[ -n "$wt_line" ]]; then
    local wt_branch
    [[ "$wt_line" =~ \[([^]]+)\] ]] && wt_branch="${BASH_REMATCH[1]/ locked/}" || wt_branch=""
    [[ -n "$wt_branch" ]] && { echo "$wt_branch"; return 0; }
  fi
  # Phase 2: bump branches
  local pattern='bump'
  [[ -n "$version" ]] && pattern="bump${version%.*}"
  local result
  result=$(LC_ALL=C git branch --no-color | grep "$pattern" | sed 's/^[* +]*//' | sort -V | tail -1)
  [[ -n "$result" ]] && { echo "$result"; return 0; }
  # Phase 3: Claude Code worktree branches (worktree-k8s-rebase-<version>*)
  # k8s-rebase.sh creates bump branches inside worktrees, but retries can
  # delete the bump branch while the worktree branch retains the commits.
  # Pick the branch with the most commits ahead of the default branch.
  if [[ -n "$version" ]]; then
    local _db
    _db=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
    : "${_db:=main}"
    git rev-parse --verify "$_db" &>/dev/null || _db="master"
    LC_ALL=C git branch --no-color | sed 's/^[* +]*//' \
      | grep "worktree-k8s-rebase-${version}" \
      | while read -r _b; do
          _c=$(git rev-list --count "${_db}".."$_b" 2>/dev/null || echo 0)
          [[ "$_c" -gt 0 ]] && echo "$_c $_b"
        done | sort -n | tail -1 | awk '{print $2}'
  fi)
}

reset_to_default() {
  local repo="$1"
  cd "$repo" || { error "Cannot cd to $repo"; return 1; }
  [[ -n "$(git status --porcelain 2>/dev/null)" ]] && { error "Uncommitted changes in $repo — commit or stash them first, then retry"; return 1; }
  local default_br
  default_br=$(default_branch)
  git checkout "$default_br" &>/dev/null || { error "Cannot checkout $default_br in $repo — resolve any conflicts or detached HEAD state, then retry"; return 1; }
  git pull --ff-only &>/dev/null || warn "$(repo_short "$repo"): pull --ff-only failed — rebase will start from local HEAD"
  info "$(repo_short "$repo") -> $default_br @ $(git rev-parse --short HEAD)"
}

remove_worktrees() {
  local repo="$1" version="${2:-}"
  cd "$repo" 2>/dev/null || return 1
  local wt_lines default_br
  wt_lines=$(git worktree list 2>/dev/null | grep '\.claude/worktrees' || true)
  local ver_prefix=""
  [[ -n "$version" ]] && ver_prefix="bump${version%.*}-"
  if [[ -n "$wt_lines" ]]; then
  default_br=$(default_branch)
  while IFS= read -r line; do
    local wt_path wt_branch commit_count=0
    wt_path="${line%% *}"
    [[ "$line" =~ \[([^]]+)\] ]] && wt_branch="${BASH_REMATCH[1]/ locked/}" || wt_branch=""
    # Version-scoped: skip worktrees that belong to a different version
    [[ -n "$ver_prefix" && -n "$wt_branch" && "$wt_branch" != "${ver_prefix}"* ]] && continue
    [[ -n "$wt_branch" ]] && commit_count=$(git rev-list --count "$default_br".."$wt_branch" 2>/dev/null || echo 0)
    git worktree unlock "$wt_path" 2>/dev/null || true
    git worktree remove "$wt_path" --force 2>/dev/null \
      || { chmod -R u+w "$wt_path" 2>/dev/null || true; rm -rf "$wt_path" 2>/dev/null; git worktree prune 2>/dev/null; } \
      || { warn "Could not remove worktree: $wt_path"; continue; }
    if [[ "$commit_count" -gt 0 ]]; then
      info "Removed worktree (branch $wt_branch preserved, $commit_count commits)"
    fi
  done <<< "$wt_lines"
  fi
  # Sweep orphaned worktree directories that git lost track of
  # (e.g., after ENOSPC corrupts git's worktree metadata).
  # Safe: only called from cmd_run (before launch) and cmd_clean.
  if [[ -d "$repo/.claude/worktrees" ]]; then
    for orphan in "$repo/.claude/worktrees"/*/; do
      [[ -d "$orphan" ]] || continue
      local orphan_name
      orphan_name=$(basename "$orphan")
      # Version-scoped: skip orphan dirs that belong to a different version
      [[ -n "$ver_prefix" && "$orphan_name" != "${ver_prefix}"* ]] && continue
      # Go module cache files are read-only; chmod before removal.
      chmod -R u+w "$orphan" 2>/dev/null || true
      if rm -rf "$orphan"; then
        info "Removed orphaned worktree dir: $orphan_name"
      else
        warn "Could not remove orphaned worktree dir: $orphan_name"
      fi
    done
  fi
}

cmd_run() {
  command -v claude &>/dev/null || die "claude CLI not found — install it and ensure it is on PATH (see https://claude.ai/code)"
  local version="$1"; shift
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Version must be X.Y.Z"
  local from_commit=""
  local repos=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --from-commit) shift; from_commit="${1:-}" ;;
      *) repos+=("$1") ;;
    esac; shift
  done
  [[ ${#repos[@]} -eq 0 ]] && repos=("${DEFAULT_REPOS[@]}")
  mkdir -p "$RESULTS_DIR" || die "Cannot create $RESULTS_DIR"

  # Enforce concurrency limit (skip when called from cmd_test_all which has its own tracking)
  if [[ -z "${_SKIP_CONCURRENCY_CHECK:-}" ]]; then
    local _running_dir="$PLUGIN_DIR/test/.matrix-state/running"
    if [[ -d "$_running_dir" ]]; then
      local _active_count=0
      for _rf in "$_running_dir"/*; do
        [[ -f "$_rf" ]] || continue
        local _run_sid=$(cut -f3 "$_rf" 2>/dev/null)
        if ! _session_alive "$_run_sid"; then
          [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true
          rm -f "$_rf"
        else
          _active_count=$((_active_count + 1))
        fi
      done
      if [[ $((_active_count + ${#repos[@]})) -gt "$MAX_CONCURRENT" ]]; then
        local _avail=$((MAX_CONCURRENT - _active_count))
        [[ "$_avail" -le 0 ]] && { error "Already at max ($MAX_CONCURRENT concurrent). Stop a session first: make stop"; return 1; }
        warn "$_active_count already running, launching only $_avail of ${#repos[@]} (max $MAX_CONCURRENT — set in config.yaml)"
        repos=("${repos[@]:0:$_avail}")
      fi
    fi
  fi

  local launched=0
  build_session_cache
  for repo in "${repos[@]}"; do
    local repo_input="$repo"
    _ensure_repo "$(repo_short "$repo_input")"
    repo=$(resolve_repo "$repo") || { warn "Not found: $repo_input — check the repo name matches config.yaml, or run make clone-all to clone missing repos"; continue; }
    local short existing_session
    short=$(repo_short "$repo")
    existing_session=$(session_for_repo "$repo")
    if [[ -n "$existing_session" ]]; then
      warn "Active session on $short — stop it first"
      continue
    fi
    remove_worktrees "$repo"
    # Clean up stale bump branches from prior runs for this version
    local _bump_prefix="bump${version%.*}"
    while IFS= read -r _old_branch; do
      git -C "$repo" branch -D "$_old_branch" 2>/dev/null \
        && info "Deleted stale branch: $_old_branch"
    done < <(git -C "$repo" branch --no-color | sed 's/^[* +]*//' | grep "^${_bump_prefix}")
    # Clear all stale state from prior runs (state.json, .session-active,
    # gate reports, advance counters). Live run data is in the worktree,
    # not the main repo — nothing is lost.
    rm -rf "$repo/.rebase-tmp" 2>/dev/null || true
    if [[ -n "$from_commit" ]]; then
      cd "$repo" || { warn "Skipping $short"; continue; }
      git rev-parse --verify "$from_commit" &>/dev/null || { warn "Commit not found: $from_commit"; continue; }
      local _db=$(default_branch)
      # Switch off any stale _test-from-* branch BEFORE deleting it; git refuses
      # to delete the currently-checked-out branch.
      local _cur_branch=$(git branch --show-current 2>/dev/null)
      [[ "$_cur_branch" == _test-from-* ]] && { git checkout -f "$_db" &>/dev/null || true; }
      git clean -fd &>/dev/null || true
      git fetch origin --no-tags &>/dev/null || true
      git branch -D "_test-from-${from_commit:0:8}" &>/dev/null || true
      git switch -c "_test-from-${from_commit:0:8}" "$from_commit" &>/dev/null \
        || git checkout -b "_test-from-${from_commit:0:8}" "$from_commit" &>/dev/null \
        || {
          if ! git rev-parse --verify "${from_commit}^{tree}" &>/dev/null; then
            warn "$short: tree for $from_commit unreadable (try: git -C $repo repack -a -d)"
          else
            warn "$short: checkout failed for ${from_commit:0:12}"
          fi
          continue
        }
      info "$short -> ${from_commit:0:8} (historical)"
      _set_worktree_base "$repo" head
    else
      reset_to_default "$repo" || { warn "Skipping $short"; continue; }
    fi
    local session_output session_id
    local _prompt="/k8s-rebase:k8s-rebase $version"
    if [[ -n "$from_commit" ]]; then
      _prompt="IMPORTANT: Do NOT switch to master/main. You are on a test branch at a historical commit. Work from HEAD as-is. The worktree.baseRef is set to 'head' so your worktree will branch from the current commit.
/k8s-rebase:k8s-rebase $version"
    fi
    local _model=$(_config_val "$short" "model")
    local _model_args=()
    [[ -n "$_model" && "$_model" != "null" ]] && _model_args=(--model "$_model")
    session_output=$(claude --bg \
      "${_model_args[@]}" \
      --plugin-dir "$PLUGIN_DIR" \
      --permission-mode "$PERMISSION_MODE" \
      "$_prompt" \
      --disallowed-tools 'Bash(git push *),Bash(*git push*),Bash(git -c *push*),Bash(*send-pack*),Bash(gh pr create *),Bash(*gh pr create*),Bash(*gh api*repos*pulls*),Bash(sleep *)' \
      2>/dev/null)
    session_id=$(echo "$session_output" | grep 'backgrounded' | grep -oE '[a-f0-9]{8,}' | head -1)
    : "${session_id:=unknown}"
    [[ "$session_id" == "unknown" ]] && { error "Failed to launch $short"; continue; }
    info "Launched $short -> $session_id"
    local _rk=$(running_key "$version" "$repo")
    echo "$session_id" > "$PLUGIN_DIR/test/.matrix-state/.session_id_$_rk" \
      || { error "Failed to persist session ID for $short (session $session_id is orphaned — stop it manually with: claude stop $session_id)"; continue; }
    launched=$((launched + 1))
  done
  [[ "$launched" -gt 0 ]] || { warn "No sessions launched"; return 1; }
}

cmd_stop() {
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && die "Usage: make stop"
  local stop_all=false
  [[ "${targets[0]}" == "--all" ]] && { stop_all=true; targets=(); }

  # Read session IDs from running files (no session cache needed)
  local state_dir="$PLUGIN_DIR/test/.matrix-state/running"
  [[ ! -d "$state_dir" ]] && { info "No active sessions"; return 0; }
  local killed=0
  for running_file in "$state_dir"/*; do
    [[ -f "$running_file" ]] || continue
    local repo_key=$(basename "$running_file")
    local raw; raw=$(cat "$running_file")
    local sid; sid=$(cut -f3 <<< "$raw")
    if [[ -z "$sid" ]]; then rm -f "$running_file"; continue; fi
    local _fv; _fv=$(cut -f4 <<< "$raw")
    repo_key=$(repo_key_from_running "$_fv" "$repo_key")
    local short="${repo_key//_//}"
    local should_stop=false
    if $stop_all; then
      should_stop=true
    else
      for t in "${targets[@]}"; do
        [[ "$short" == *"$t"* || "$sid" == "$t"* ]] && { should_stop=true; break; }
      done
    fi
    if $should_stop; then
      claude stop "$sid" 2>/dev/null || true
      rm -f "$running_file"
      info "Stopped $short"
      killed=$((killed + 1))
    fi
  done
  # Phase 2: fallback to session cache for zombie sessions with no running file
  if [[ "$killed" -eq 0 ]] || $stop_all; then
    _SESSION_CACHE_AGE=0  # force refresh after Phase 1 stops
    build_session_cache
    while IFS=$'\t' read -r _cwd _state _elapsed _pid _sid _rest; do
      [[ "$_cwd" == *"$REPOS_DIR"* ]] || continue
      local _repo="${_cwd#*$REPOS_DIR/}"; _repo="${_repo%%/.claude/*}"; _repo="${_repo%%/}"
      local _should_stop=false
      if $stop_all; then _should_stop=true
      else for t in "${targets[@]}"; do [[ "$_repo" == *"$t"* || "$_sid" == "$t"* ]] && { _should_stop=true; break; }; done; fi
      if $_should_stop; then
        claude stop "$_sid" 2>/dev/null || true
        info "Stopped $_repo ($_sid) [from session cache]"
        killed=$((killed + 1))
      fi
    done <<< "$_SESSION_CACHE"
  fi
  [[ "$killed" -eq 0 ]] && info "No active sessions"
}

cmd_clean() {
  local repos=()
  local version=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version) shift; version="${1:-}" ;;
      *) repos+=("$1") ;;
    esac; shift
  done
  [[ ${#repos[@]} -eq 0 ]] && repos=("${DEFAULT_REPOS[@]}")
  if [[ -n "$version" && ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    warn "clean: --version must be X.Y.Z (got: $version) — ignoring version filter"
    version=""
  fi
  local _ver_u=""
  [[ -n "$version" ]] && _ver_u="${version//./_}"
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  local running_dir="$state_dir/running"
  local cleaned_keys=()
  for repo in "${repos[@]}"; do
    repo=$(resolve_repo "$repo") || continue
    local _ck=$(repo_key "$repo")
    local short=$(repo_short "$repo")
    # Stop any active sessions for this repo before cleaning
    if [[ -d "$running_dir" ]]; then
      for rf in "$running_dir"/*"_${_ck}"; do
        [[ -f "$rf" ]] || continue
        # Version-scoped: skip sessions from other versions
        [[ -n "$version" && "$(basename "$rf")" != "${version}_${_ck}" ]] && continue
        local _sid=$(cut -f3 "$rf" 2>/dev/null)
        if [[ -n "$_sid" ]]; then
          claude stop "$_sid" 2>/dev/null || true
          info "Stopped session on $short"
        fi
        rm -f "$rf"
      done
    fi
    cleaned_keys+=("$_ck")
    cd "$repo" || continue
    git worktree prune 2>/dev/null || true
    remove_worktrees "$repo" "$version"
    rm -rf "$repo/.rebase-tmp" 2>/dev/null || true
    # Recover to default branch first (so we can delete temp branches)
    local _cur=$(git branch --show-current 2>/dev/null)
    [[ -z "$_cur" || "$_cur" == _test-from-* ]] && { local _db=$(default_branch); git checkout "$_db" 2>/dev/null || true; }
    _set_worktree_base "$repo" remove
    for tb in $(git branch --no-color | tr -d ' *' | grep '^_test-from-'); do
      git branch -D "$tb" 2>/dev/null || true
    done
  done
  if command -v podman &>/dev/null; then
    local pruned=0
    while IFS= read -r cid; do
      podman rm "$cid" &>/dev/null && pruned=$((pruned + 1))
    done < <(podman ps -a --filter status=exited --filter name=k8s-rebase --format '{{.ID}}' 2>/dev/null)
    [[ "$pruned" -gt 0 ]] && info "Pruned $pruned containers"
  fi
  for _ck in "${cleaned_keys[@]}"; do
    if [[ -n "$version" ]]; then
      rm -f "$state_dir/done/${version}_"*"_${_ck}" 2>/dev/null
      rm -rf "$state_dir/court/${version}_${_ck}" 2>/dev/null
      rm -f "$state_dir/running/${version}_${_ck}" 2>/dev/null
      rm -f "$state_dir/.session_id_${version}_${_ck}" 2>/dev/null
      rm -f "$state_dir/known_good_resolved_${_ck}_${_ver_u}" 2>/dev/null
    else
      rm -f "$state_dir/done/"*"_${_ck}" 2>/dev/null
      rm -rf "$state_dir/court/"*"_${_ck}" 2>/dev/null
      rm -f "$state_dir/running/"*"_${_ck}" 2>/dev/null
      rm -f "$state_dir/.session_id_"*"_${_ck}" 2>/dev/null
      rm -f "$state_dir/known_good_resolved_${_ck}_"* 2>/dev/null
    fi
  done
  [[ ${#cleaned_keys[@]} -gt 0 ]] && info "Cleared done/court/running state for ${#cleaned_keys[@]} repos"
  return 0
}

# ── Mutation ───────────────────────────────────────────────────────────

# TAG_TO_PATTERN: maps an autofix tag (the suffix in fix_<tag>) to the ### heading
# of the pattern section it exercises in docs/k8s-rebase-patterns.md.
# Multiple tags may share one heading — they all exercise the same pattern section,
# so pattern:<any of them> removes the same block.
declare -A TAG_TO_PATTERN=(
  [xexp]="golang.org/x/exp" [reflect_ptr]="Deprecated stdlib/apimachinery symbols"
  [fieldsv1]="Deprecated stdlib/apimachinery symbols" [klog_v2]="Deprecated stdlib/apimachinery symbols"
  [eventf]="Deprecated stdlib/apimachinery symbols" [imports]="Deprecated stdlib/apimachinery symbols"
  [bounding_dirs]="Deprecated stdlib/apimachinery symbols" [addtoscheme]="AddToScheme"
  [mocks]="Deprecated stdlib/apimachinery symbols" [crd_int64_validation]="Deprecated stdlib/apimachinery symbols"
  [kind_image]="Transitive dependency" [kind_version]="Transitive dependency"
  [version_refs]="Deprecated stdlib/apimachinery symbols"
  [docs_version]="Deprecated stdlib/apimachinery symbols"
  [go_version]="Deprecated stdlib/apimachinery symbols" [lint_version]="golangci-lint"
)

# mutate_plugin SPEC [SPEC...] -> prints dest path to stdout
#
# Creates a timestamped copy of PLUGIN_DIR, then disables the named
# autofix functions and/or pattern sections so the agent cannot rely on them.
# Callers must capture the printed path; never pass 'none' here (cmd_test strips it).
mutate_plugin() {
  local label="mutated-$(date +%s)"
  local dest="$RESULTS_DIR/$label"
  mkdir -p "$RESULTS_DIR" 2>/dev/null || true
  command -v rsync &>/dev/null || die "rsync required"
  rsync -a --exclude test/.repos --exclude test/.matrix-state "$PLUGIN_DIR/" "$dest/" || die "Cannot copy plugin to $dest"

  # Deduplicate and expand specs. has_all_patterns / has_all_fns suppress
  # individual pattern:/fn: specs that are already covered by all-patterns/all-fns.
  local has_all_patterns=false has_all_fns=false
  local -A seen_specs=()
  local specs=()
  for spec in "$@"; do
    [[ -n "${seen_specs[$spec]+x}" ]] && continue
    seen_specs[$spec]=1
    case "$spec" in
      all) has_all_patterns=true; has_all_fns=true; specs+=(all-patterns all-fns) ;;
      all-patterns) has_all_patterns=true; specs+=("$spec") ;;
      all-fns) has_all_fns=true; specs+=("$spec") ;;
      pattern:*) $has_all_patterns || specs+=("$spec") ;;
      fn:*) $has_all_fns || specs+=("$spec") ;;
      *) rm -rf "$dest"; die "Unknown spec: $spec" ;;
    esac
  done

  for spec in "${specs[@]}"; do
    case "$spec" in
      pattern:*)
        local key="${spec#pattern:}"
        local heading="${TAG_TO_PATTERN[$key]:-}"
        [[ -z "$heading" ]] && { rm -rf "$dest"; die "Unknown pattern: $key"; }
        local pfile="$dest/docs/k8s-rebase-patterns.md"
        # Remove the markdown section that starts with 'hdr' and ends at the next ### heading.
        awk -v hdr="### $heading" '/^### / && index($0, hdr) == 1 { skip=1; next } /^### / && skip { skip=0 } skip { next } { print }' \
          "$pfile" > "$pfile.tmp" && mv "$pfile.tmp" "$pfile"
        info "Removed pattern: $heading" ;;
      fn:*)
        local ftag="${spec#fn:}" afile="$dest/scripts/k8s-rebase-autofix.sh"
        grep -q "^fix_${ftag}()" "$afile" 2>/dev/null || { rm -rf "$dest"; die "Function fix_${ftag}() not found"; }
        awk -v fn="fix_${ftag}" '$0 ~ "^"fn"\\(\\)" { print $0; print "  return 0"; skip=1; next } skip && /^\}/ { print; skip=0; next } skip { next } { print }' \
          "$afile" > "$afile.tmp" && mv "$afile.tmp" "$afile"
        info "Neutered: fix_${ftag}()" ;;
      all-patterns)
        sed -i '/^## Pattern Table/,$ d' "$dest/docs/k8s-rebase-patterns.md" ;;
      all-fns)
        local afile="$dest/scripts/k8s-rebase-autofix.sh"
        awk '/^fix_[a-z0-9_]+\(\)/ && !/fix_uncommitted/ { print $0; print "  return 0"; skip=1; next } skip && /^\}/ { print; skip=0; next } skip { next } { print }' \
          "$afile" > "$afile.tmp" && mv "$afile.tmp" "$afile" ;;
    esac
  done

  local skillfile="$dest/skills/k8s-rebase/SKILL.md"
  [[ -f "$skillfile" ]] && {
    sed -i "s|find \"\$HOME/.claude\" \"\$HOME\" -maxdepth 7 -name \"k8s-rebase-autofix.sh\"[^)]*)|echo \"$dest/scripts/k8s-rebase-autofix.sh\")|" "$skillfile"
    sed -i "s|find \"\$HOME/.claude\" \"\$HOME\" -maxdepth 7 -name \"k8s-rebase-patterns.md\"[^)]*)|echo \"$dest/docs/k8s-rebase-patterns.md\")|" "$skillfile"
  }
  bash -n "$dest/scripts/k8s-rebase-autofix.sh" || { rm -rf "$dest"; die "Mutation produced invalid bash"; }
  echo "$dest"
}

# ── Test Execution ─────────────────────────────────────────────────────

_repo_from_key() {
  local key="$1"
  local org="${key%%_*}" name="${key#*_}"
  local path="$REPOS_DIR/$org/$name"
  [[ -d "$path" ]] && { echo "$path"; return 0; }
  return 1
}

cmd_test() {
  local version="$VERSION" specs=() repos=() from_commit=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version) shift; version="${1:-}"; [[ -z "$version" ]] && die "--version needs value" ;;
      --from-commit) shift; from_commit="${1:-}"; [[ -z "$from_commit" ]] && die "--from-commit needs value" ;;
      none|pattern:*|fn:*|all-patterns|all-fns|all) specs+=("$1") ;;
      *) repos+=("$1") ;;
    esac; shift
  done
  [[ ${#specs[@]} -eq 0 ]] && die "No spec (use: all, fn:<tag>, pattern:<key>)"
  [[ ${#repos[@]} -eq 0 ]] && die "No repo path"
  [[ -n "$from_commit" && ${#repos[@]} -gt 1 ]] && die "--from-commit requires exactly one repo"

  _check_evidence_paths

  # Mutate the plugin once — all repos in this invocation share the same spec.
  local mutated
  if [[ "${specs[*]}" == "none" ]]; then
    mutated="$PLUGIN_DIR"
    info "Mode: full skill (patterns + autofix enabled)"
  elif [[ " ${specs[*]} " == *" none "* ]]; then
    die "Cannot mix 'none' with other specs"
  else
    mutated=$(mutate_plugin "${specs[@]}") || exit 1
    if [[ "${specs[*]}" == *"all-patterns"*"all-fns"* || "${specs[*]}" == "all" ]]; then
      info "Mode: blind (patterns doc + autofix functions disabled)"
    else
      info "Mode: mutated (${specs[*]})"
    fi
  fi

  local _state_dir="$PLUGIN_DIR/test/.matrix-state"
  local _failures=0
  mkdir -p "$mutated/test/.matrix-state"

  for repo_input in "${repos[@]}"; do
    _ensure_repo "$(repo_short "$repo_input")"
    local repo
    repo=$(resolve_repo "$repo_input") || { error "Not found: $repo_input — check the repo name matches config.yaml, or run make clone-all to clone missing repos"; continue; }

    # Read from_commit from config when not passed via CLI (per-repo)
    local _from_commit="$from_commit"
    if [[ -z "$_from_commit" ]]; then
      _from_commit=$(_config_val "$(repo_short "$repo")" "from_commit")
    fi

    info "── Test: ${specs[*]} on $(repo_short "$repo") ──"

    local _repo_key _running_key _done_key
    _repo_key=$(repo_key "$repo")
    _running_key=$(running_key "$version" "$repo")
    _done_key=$(_done_key "$version" "${specs[*]}" "$_repo_key")
    mkdir -p "$_state_dir/running" "$_state_dir/done"
    rm -f "$_state_dir/done/$_done_key"
    rm -f "$_state_dir/court/${version}_${_repo_key}"

    # Clean stale worktree branches
    git -C "$repo" worktree prune 2>/dev/null || true

    if ! (PLUGIN_DIR="$mutated" cmd_run "$version" "$repo" ${_from_commit:+--from-commit "$_from_commit"}); then
      if [[ -n "$_from_commit" ]]; then
        local _db; _db=$(git -C "$repo" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
        : "${_db:=main}"
        git -C "$repo" checkout "$_db" 2>/dev/null || true
        git -C "$repo" branch -D "_test-from-${_from_commit:0:8}" 2>/dev/null || true
        _set_worktree_base "$repo" remove
      fi
      error "Launch failed for $(repo_short "$repo")"
      _failures=$((_failures + 1)); continue
    fi

    local _sid
    _sid=$(cat "$mutated/test/.matrix-state/.session_id_$_running_key" 2>/dev/null)
    [[ -n "$_sid" ]] && printf '%s\t%s\t%s\t%s\n' "${specs[*]}" "$(date +%s)" "$_sid" "$version" > "$_state_dir/running/$_running_key"
    rm -f "$mutated/test/.matrix-state/.session_id_$_running_key" 2>/dev/null
    if [[ -z "${_SKIP_CONCURRENCY_CHECK:-}" ]]; then
      info "$(repo_short "$repo") running — 'make watch' to monitor, 'make results' when done"
    fi
  done
  [[ "$_failures" -gt 0 ]] && return 1
  return 0
}

cmd_test_all() {
  local spec="${1:-none}"; shift || true
  local version="$VERSION"
  [[ "${1:-}" == "--version" ]] && { shift; version="${1:-$VERSION}"; shift; }
  local launched=0 active=0
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  # Sort repos by least recently tested (oldest first, untested first)
  local tsv="$state_dir/results.tsv"
  local sorted_repos=()
  while IFS= read -r repo; do
    sorted_repos+=("$repo")
  done < <(for repo in "${DEFAULT_REPOS[@]}"; do
    [[ -d "$repo" ]] || continue
    local short=$(repo_short "$repo")
    local last_ts=$(awk -F'\t' -v r="$short" '$4==r && ($3~/^all/ || $3=="none") {ts=$1} END{print ts}' "$tsv" 2>/dev/null)
    echo "${last_ts:-0000}	$repo"
  done | sort | cut -f2)
  [[ ${#sorted_repos[@]} -eq 0 ]] && sorted_repos=("${DEFAULT_REPOS[@]}")
  # Count already-running repos toward the limit; clean stale files now
  # so they do not inflate 'active' before the launch loop.
  for repo in "${sorted_repos[@]}"; do
    [[ -d "$repo" ]] || continue
    local _rk=$(running_key "$version" "$repo")
    if [[ -f "$state_dir/running/$_rk" ]]; then
      local _pre_sid=$(cut -f3 "$state_dir/running/$_rk" 2>/dev/null)
      if ! _session_alive "$_pre_sid"; then
        [[ -n "$_pre_sid" ]] && claude stop "$_pre_sid" 2>/dev/null || true
        rm -f "$state_dir/running/$_rk"
      else
        active=$((active + 1))
      fi
    fi
  done
  for repo in "${sorted_repos[@]}"; do
    _ensure_repo "$(repo_short "$repo")"
    [[ -d "$repo" ]] || continue
    local _rk=$(running_key "$version" "$repo")
    if [[ -f "$state_dir/running/$_rk" ]]; then
      local _run_sid=$(cut -f3 "$state_dir/running/$_rk" 2>/dev/null)
      if _session_alive "$_run_sid"; then
        info "SKIP $(repo_short "$repo") (already running)"
        continue
      else
        claude stop "$_run_sid" 2>/dev/null || true
        rm -f "$state_dir/running/$_rk"
        active=$((active - 1))
      fi
    fi
    local _done_key=$(_done_key "$version" "$spec" "$(repo_key "$repo")")
    [[ -f "$state_dir/done/$_done_key" ]] && { info "SKIP $(repo_short "$repo") (already tested)"; continue; }
    local _fc=$(_config_val "$(repo_short "$repo")" "from_commit")
    local _fc_args=()
    [[ -n "$_fc" ]] && _fc_args=(--from-commit "$_fc")
    # Skip repos already at target version with no from-commit set
    if [[ ${#_fc_args[@]} -eq 0 ]]; then
      local _cur_ver=$(_repo_k8s_version "$repo")
      if [[ "$_cur_ver" == "v0.${version#*.}" || "$_cur_ver" == "v$version" ]]; then
        warn "SKIP $(repo_short "$repo") (already at $_cur_ver — use: make set-from-commit repo=$(repo_short "$repo") commit=<sha>)"
        continue
      fi
    fi
    if [[ $((active + launched)) -ge "$MAX_CONCURRENT" ]]; then
      info "SKIP $(repo_short "$repo") (max $MAX_CONCURRENT concurrent — run make test again when slots free)"
      continue
    fi
    _SKIP_CONCURRENCY_CHECK=1 cmd_test "$spec" "$repo" --version "$version" "${_fc_args[@]}" && launched=$((launched + 1))
  done
  info "Launched: $launched ($active already active)"

  # Phase 2: wait for all sessions, record results, launch remaining repos
  trap 'info "Interrupted — sessions still running in background"; exit 130' INT TERM
  while [[ -n "$(ls -A "$state_dir/running" 2>/dev/null)" ]]; do
    sleep 60
    # Check each running session — record if done, clear if dead
    local _any_done=false
    for _rf in "$state_dir/running"/*; do
      [[ -f "$_rf" ]] || continue
      local _sid_check=$(cut -f3 "$_rf" 2>/dev/null)
      _session_alive "$_sid_check" || _any_done=true
    done
    if $_any_done; then
      _SESSION_CACHE_AGE=0
      auto_record
      for _rf in "$state_dir/running"/*; do
        [[ -f "$_rf" ]] || continue
        local _sid_check=$(cut -f3 "$_rf" 2>/dev/null)
        _session_alive "$_sid_check" || { [[ -n "$_sid_check" ]] && claude stop "$_sid_check" 2>/dev/null || true; rm -f "$_rf"; }
      done
    fi
    # Re-count active and launch newly-eligible repos into freed slots
    active=0
    for repo in "${sorted_repos[@]}"; do
      [[ -d "$repo" ]] || continue
      local _rk=$(running_key "$version" "$repo")
      [[ -f "$state_dir/running/$_rk" ]] && active=$((active + 1))
    done
    for repo in "${sorted_repos[@]}"; do
      [[ -d "$repo" ]] || continue
      local _rk=$(running_key "$version" "$repo")
      [[ -f "$state_dir/running/$_rk" ]] && continue
      local _done_key=$(_done_key "$version" "$spec" "$(repo_key "$repo")")
      [[ -f "$state_dir/done/$_done_key" ]] && continue
      local _fc=$(_config_val "$(repo_short "$repo")" "from_commit")
      local _fc_args=()
      [[ -n "$_fc" ]] && _fc_args=(--from-commit "$_fc")
      if [[ ${#_fc_args[@]} -eq 0 ]]; then
        local _cur_ver=$(_repo_k8s_version "$repo")
        [[ "$_cur_ver" == "v0.${version#*.}" || "$_cur_ver" == "v$version" ]] && continue
      fi
      [[ "$active" -ge "$MAX_CONCURRENT" ]] && break
      _SKIP_CONCURRENCY_CHECK=1 cmd_test "$spec" "$repo" --version "$version" "${_fc_args[@]}" && { active=$((active + 1)); info "Launched $(repo_short "$repo") (slot freed)"; }
    done
  done
  trap - INT TERM
  cmd_results
}

# ── Recording ──────────────────────────────────────────────────────────

_do_record_one() {
  local repo="$1" repo_key="$2" spec="$3" state_dir="$4" launch_epoch="${5:-0}" _rec_version="${6:-$VERSION}"
  local short=$(repo_short "$repo")

  local default_br
  default_br=$(git -C "$repo" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
  : "${default_br:=main}"
  git -C "$repo" rev-parse --verify "$default_br" &>/dev/null \
    || git -C "$repo" rev-parse --verify "origin/$default_br" &>/dev/null \
    || default_br="master"

  local result_branch="" wt_path=""
  _worktree_info "$repo" || true
  result_branch="$_WT_BRANCH" wt_path="$_WT_PATH"
  [[ -n "$wt_path" && ! -d "$wt_path" ]] && { git -C "$repo" worktree prune 2>/dev/null; }
  if [[ -z "$result_branch" ]]; then
    _bp="bump${_rec_version%.*}"
    result_branch=$(LC_ALL=C git -C "$repo" branch --no-color | grep "$_bp" | sed 's/^[* +]*//' | sort -V | tail -1)
  fi
  # Fallback: Claude Code worktree branches (worktree-k8s-rebase-<version>*)
  # k8s-rebase.sh creates bump branches inside worktrees, but retries can
  # delete the bump branch while the worktree branch retains the commits.
  # Pick the branch with the most commits ahead of the default branch.
  if [[ -z "$result_branch" ]]; then
    result_branch=$(LC_ALL=C git -C "$repo" branch --no-color | sed 's/^[* +]*//' \
      | grep "worktree-k8s-rebase-${_rec_version}" \
      | while read -r _b; do
          _c=$(git -C "$repo" rev-list --count "${default_br}".."$_b" 2>/dev/null || echo 0)
          [[ "$_c" -gt 0 ]] && echo "$_c $_b"
        done | sort -n | tail -1 | awk '{print $2}')
  fi
  [[ -z "$result_branch" ]] && { echo "no branch found"; return 1; }

  if [[ "$launch_epoch" -gt 0 ]]; then
    local branch_tip_epoch
    branch_tip_epoch=$(git -C "$repo" log -1 --format='%ct' "$result_branch" 2>/dev/null)
    [[ "$branch_tip_epoch" -gt 0 && "$branch_tip_epoch" -lt "$launch_epoch" ]] && { echo "stale branch"; return 1; }
  fi

  local commits=$(git -C "$repo" rev-list --count "$default_br".."$result_branch" 2>/dev/null || echo 0)
  [[ "$commits" -eq 0 ]] && { echo "no commits (no-op)"; return 1; }

  # Gate tally — every gate must produce a report, all must pass
  local verdict="FAIL"
  local gtotal=0 gfail=0 gskip=0
  _collect_gate_dirs "$repo"
  if [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
    read -r gtotal gfail gskip gfail_names <<< "$(_tally_gates "${_GATE_DIRS[@]}")"
    # Reduce expected count for missing informational gates
    local _missing_info=0
    for _ig in $INFO_GATES; do
      local _found=false
      for _gd in "${_GATE_DIRS[@]}"; do
        for f in "$_gd"/*"${_ig}"*; do [[ -f "$f" ]] && { _found=true; break 2; }; done
      done
      $_found || _missing_info=$((_missing_info + 1))
    done
    [[ "$gtotal" -ge $((EXPECTED_GATES - _missing_info)) && "$gfail" -eq 0 ]] && verdict="PASS"
  fi

  # Known-good diff (informational — does not affect verdict)
  # Use the version-appropriate config so INFW/other repos without known_good
  # in an older version don't accidentally inherit the known_good from a newer config.
  local kg_hunks="" kg_vendor="" kg_branch=""
  local _saved_cf="$CONFIG_FILE" _saved_ver="$VERSION"
  local _ver_cf="${PLUGIN_DIR}/test/config-${_rec_version%.*}.yaml"
  if [[ -f "$_ver_cf" ]]; then CONFIG_FILE="$_ver_cf"; VERSION="$_rec_version"; fi
  kg_branch=$(_resolve_known_good "$short" "$repo")
  CONFIG_FILE="$_saved_cf"; VERSION="$_saved_ver"
  if [[ -n "$kg_branch" ]]; then
    local kg_diff_all=$(git -C "$repo" diff "$result_branch" "$kg_branch" -- . ':!.rebase-tmp' 2>/dev/null | grep -c '^@@' || true)
    local kg_diff_nv=$(git -C "$repo" diff "$result_branch" "$kg_branch" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
    kg_hunks="$kg_diff_nv"
    [[ "$kg_diff_all" -gt "$kg_diff_nv" ]] && kg_vendor="$((kg_diff_all - kg_diff_nv))"
  fi

  local _prel_sid="${7:-}"    # session ID written to .prel sentinel for post-session update check
  local update_mode="${8:-}"  # "update" = bypass done_key guard; append corrected row only

  # Build human-readable detail
  local detail=""
  local _gate_suffix=""
  [[ "$gskip" -gt 0 ]] && _gate_suffix=", ${gskip} skipped"
  if [[ "$gtotal" -eq 0 ]]; then
    echo "infra: no gates ran — not recording FAIL (session stays retriable)"
    return 2
  elif [[ "$gtotal" -lt "$EXPECTED_GATES" ]]; then
    local _gmiss_names="" _gcrash_names=""
    for _gmd in "$PLUGIN_DIR/gates"/step*/*.md; do
      [[ -f "$_gmd" ]] || continue
      local _gdir_name=$(basename "$(dirname "$_gmd")")
      local _gstep="${_gdir_name%%-*}"
      local _gbase=$(basename "$_gmd" .md)
      local _gexpected="${_gstep}-${_gbase}"
      local _found_gate=false _found_crash=false
      for _gd in "${_GATE_DIRS[@]}"; do
        [[ -f "$_gd/${_gexpected}.report" ]] && { _found_gate=true; break; }
        [[ -f "$_gd/${_gexpected}.crash"  ]] && _found_crash=true
      done
      if ! $_found_gate; then
        if $_found_crash; then
          _gcrash_names="${_gcrash_names:+$_gcrash_names, }${_gexpected}(crashed)"
        else
          _gmiss_names="${_gmiss_names:+$_gmiss_names, }${_gexpected}"
        fi
      fi
    done
    local _crash_suffix=""
    [[ -n "$_gcrash_names" ]] && _crash_suffix=", crashed: ${_gcrash_names}"
    detail="missing $((EXPECTED_GATES - gtotal)) of $EXPECTED_GATES gates [${_gmiss_names}]${_crash_suffix}"
    [[ "$gfail" -gt 0 ]] && detail="$detail, $gfail failed [${gfail_names//,/, }]"
    [[ "$gskip" -gt 0 ]] && detail="$detail$_gate_suffix"
  elif [[ "$gfail" -gt 0 ]]; then
    detail="$gfail gate(s) failed [${gfail_names//,/, }]${_gate_suffix}"
  elif [[ -n "$kg_hunks" ]]; then
    if [[ "$kg_hunks" -eq 0 && -z "$kg_vendor" ]]; then
      detail="identical to known-good"
    elif [[ "$kg_hunks" -eq 0 ]]; then
      detail="matches known-good (vendor-only diff)"
    else
      detail="${kg_hunks} code hunks from known-good"
      [[ -n "$kg_vendor" ]] && detail="$detail (+${kg_vendor} vendor)"
    fi
  else
    detail="all gates pass (no known-good set)"
  fi
  local ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local done_key=$(_done_key "$_rec_version" "$spec" "$repo_key")
  mkdir -p "$state_dir/done"
  if [[ -f "$state_dir/done/$done_key" ]]; then
    [[ "$update_mode" != "update" ]] && { echo "already recorded (done_key exists)"; return 0; }
    # update mode: session finished with new commits after gate-complete recording.
    # Append corrected row. Don't re-touch done_key or clear court.
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$_rec_version" "$spec" "$short" "$verdict" "$detail" >> "$state_dir/results.tsv"
    printf '%-20s %-42s %-8s %s (updated)' "$spec" "$short" "$verdict" "$detail"
    return 0
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$_rec_version" "$spec" "$short" "$verdict" "$detail" >> "$state_dir/results.tsv"
  touch "$state_dir/done/$done_key"
  # Write prel sentinel so auto_record can append a corrected row when the session
  # finishes with new commits after gate-complete recording.
  # Fields: sid, recorded_sha, version, spec, repo_key (all needed for update).
  if [[ -n "$_prel_sid" ]]; then
    local _prel_bn; _prel_bn=$(cat "$repo/.rebase-tmp/branch-name" 2>/dev/null)
    [[ -z "$_prel_bn" && -n "$_WT_PATH" ]] && _prel_bn=$(cat "$_WT_PATH/.rebase-tmp/branch-name" 2>/dev/null)
    local _prel_sha; _prel_sha=$(echo "$_prel_bn" | xargs -I{} git -C "$repo" log -1 --format='%H' {} 2>/dev/null || echo "")
    [[ -n "$_prel_sha" ]] && printf '%s\t%s\t%s\t%s\t%s\n' \
      "$_prel_sid" "$_prel_sha" "$_rec_version" "$spec" "$repo_key" \
      > "$state_dir/done/${done_key}.prel"
  fi
  rm -f "$state_dir/running/${_rec_version}_${repo_key}"
  rm -f "$state_dir/court/${_rec_version}_${repo_key}"
  printf '%-20s %-42s %-8s %s' "$spec" "$short" "$verdict" "$detail"
}

auto_record() {
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  local running_dir="$state_dir/running"
  local recorded=0

  # Main running-file loop — guarded (skip if no active sessions)

  for running_file in "$running_dir"/*; do
    [[ -f "$running_file" ]] || continue
    local _file_key; _file_key=$(basename "$running_file")
    local spec launch_epoch _run_sid _run_version
    IFS=$'\t' read -r spec launch_epoch _run_sid _run_version < "$running_file"
    [[ "$launch_epoch" =~ ^[0-9]+$ ]] || launch_epoch=0
    : "${_run_version:=$VERSION}"
    local repo_key; repo_key=$(repo_key_from_running "$_run_version" "$_file_key")
    [[ -z "$spec" ]] && { [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true; rm -f "$running_file"; continue; }

    local repo
    repo=$(_repo_from_key "$repo_key") || true
    [[ -z "$repo" || ! -d "$repo" ]] && continue
    local short=$(repo_short "$repo")
    local done_key=$(_done_key "$_run_version" "$spec" "$repo_key")
    [[ -f "$state_dir/done/$done_key" ]] && { [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true; rm -f "$running_file"; continue; }

    local _session_dead=false
    if _session_alive "$_run_sid"; then
      # Session still running — check if gates are complete (scan all worktrees)
      _collect_gate_dirs "$repo"
      local _report_count=0
      if [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
        local -A _seen_reports=()
        for _gd in "${_GATE_DIRS[@]}"; do
          for _gf in "$_gd"/*.report; do
            [[ -f "$_gf" ]] || continue
            _seen_reports[$(basename "$_gf" .report)]=1
          done
        done
        _report_count=${#_seen_reports[@]}
      fi
      # _report_count counts unique .report basenames; EXPECTED_GATES counts .md files.
      # If an INFO gate never runs and produces no .report, this check will not pass
      # until the session dies and the dead-session path records the result.
      if [[ "$_report_count" -ge "$EXPECTED_GATES" ]]; then
        info "Gate-complete: $spec on $short ($_report_count/$EXPECTED_GATES gates)"
      else
        continue
      fi
    else
      _session_dead=true
    fi

    local result
    if result=$(_do_record_one "$repo" "$repo_key" "$spec" "$state_dir" "$launch_epoch" "$_run_version" "$_run_sid"); then
      [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true
      recorded=$((recorded + 1))
      info "Recorded: $result"
    elif $_session_dead; then
      local _fail_detail="${result:-session ended without result}"
      local ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$_run_version" "$spec" "$short" "FAIL" "$_fail_detail" >> "$state_dir/results.tsv"
      mkdir -p "$state_dir/done"
      touch "$state_dir/done/$done_key"
      [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true
      rm -f "$running_file"
      recorded=$((recorded + 1))
      warn "Recorded FAIL for $short ($_fail_detail)"
    else
      # live session but _do_record_one failed (no branch, stale branch)
      warn "Record deferred for $short: ${result:-no branch found} (session alive, will retry)"
    fi
  done

  # Prel scan runs unconditionally — needed even when running_dir is empty,
  # because the session that wrote the sentinel may have already finished.
  # Scan .prel sentinel files written at gate-complete. When the session later
  # finishes with new commits (e.g. lint fixes after gates), append a corrected row.
  # Each .prel file stores: sid TAB recorded_sha TAB version TAB spec TAB repo_key
  for _pf in "$state_dir/done"/*.prel; do
    [[ -f "$_pf" ]] || continue
    local _psid _psha _pver _psp _prk
    IFS=$'\t' read -r _psid _psha _pver _psp _prk < "$_pf"
    [[ -z "$_psid" || -z "$_psha" || -z "$_prk" ]] && { rm -f "$_pf"; continue; }
    # Only update when session is confirmed dead
    _session_alive "$_psid" 2>/dev/null && continue
    local _prepo; _prepo=$(_repo_from_key "$_prk") || true
    [[ -z "$_prepo" ]] && { rm -f "$_pf"; continue; }
    # branch-name may be in the worktree (worktree-based sessions), not main repo
    local _bn; _bn=$(cat "$_prepo/.rebase-tmp/branch-name" 2>/dev/null)
    if [[ -z "$_bn" ]]; then
      _worktree_info "$_prepo" || true
      [[ -n "$_WT_PATH" ]] && _bn=$(cat "$_WT_PATH/.rebase-tmp/branch-name" 2>/dev/null)
    fi
    [[ -z "$_bn" ]] && { rm -f "$_pf"; continue; }
    local _cur_sha; _cur_sha=$(git -C "$_prepo" log -1 --format='%H' "$_bn" 2>/dev/null || echo "")
    if [[ -n "$_cur_sha" && "$_cur_sha" != "$_psha" ]]; then
      local _upd
      if _upd=$(_do_record_one "$_prepo" "$_prk" "$_psp" "$state_dir" "0" "$_pver" "" update); then
        recorded=$((recorded + 1))
        info "Updated (branch advanced after gate-complete): $_upd"
      fi
    fi
    rm -f "$_pf"
  done

  [[ "$recorded" -gt 0 ]] && info "$recorded result(s) recorded"
}

# ── Adversarial Court ──────────────────────────────────────────────────

cmd_court() {
  [[ $# -lt 3 ]] && die "Usage: make court repo=<repo>"
  local result_branch="$1" known_good="$2" repo="$3"
  # Short label for concurrent-court output — prefixed on every progress line
  # so interleaved output from parallel courts is always identifiable.
  local _log_prefix; _log_prefix="[$(repo_short "$repo") $VERSION]"

  cd "$repo" || { error "$_log_prefix Cannot cd to $repo"; return 1; }
  git rev-parse --verify "$result_branch" &>/dev/null || { error "$_log_prefix Branch not found: $result_branch"; return 1; }
  git rev-parse --verify "$known_good" &>/dev/null || { error "$_log_prefix Branch not found: $known_good"; return 1; }

  # Court exclusions. Vendor is generated; go.sum is pure resolver output
  # (module hashes) that the court criteria explicitly cannot act on — a
  # version delta is only a regression if the DIFF proves an API is absent,
  # which hashes never show. go.sum is also ~half the byte weight of a large
  # rebase diff (e.g. ovn-kubernetes: 292KB -> 150KB, ~211K -> ~100K tokens).
  # Cutting it removes noise the briefs speculated on and leaves headroom below
  # the context window (a full diff measures close to it, and the model's output
  # reservation eats into the limit). go.mod is kept — version pins are signal.
  # packages/ = dependency metadata cache (LICENSE/NOTICE files), like vendor but
  # for package listings; mocks/ = mockery-generated files — neither needs review.
  local court_excludes=(':!.rebase-tmp' ':(exclude,glob)**/vendor/**' ':(exclude,glob)**/go.sum' ':(exclude,glob)**/packages/**' ':(exclude,glob)**/mocks/**')
  local diff_nv=$(git diff "$known_good" "$result_branch" -- . "${court_excludes[@]}" 2>/dev/null)
  [[ -z "$diff_nv" ]] && { info "$_log_prefix PASS: identical (non-vendor)"; return 0; }

  local diff_bytes=${#diff_nv}
  # Backstop only. ~1.4 bytes/token for dense diffs, so 250 KB ≈ 180K tokens;
  # past that the court prompt risks the context window. Real diffs (go.sum
  # excluded) run ~150-185 KB, so this rarely fires.
  if [[ "$diff_bytes" -gt 250000 ]]; then
    error "$_log_prefix INCONCLUSIVE: diff too large for court (${diff_bytes} bytes — max 250000)"
    return 2
  fi
  local hunks; hunks=$(grep -c '^@@' <<< "$diff_nv" || true)
  local diff_stat=$(git diff --stat "$known_good" "$result_branch" -- . "${court_excludes[@]}" 2>/dev/null)
  info "$_log_prefix Diff: $hunks non-vendor hunks, go.sum excluded (${diff_bytes} bytes)"

  local direction="DIFF DIRECTION: 'git diff known_good result'.
'-' lines are in KNOWN-GOOD but not result (things the result may be MISSING).
'+' lines are in RESULT but not known-good (things the result ADDED or CHANGED).
Example: if the result bumped k8s to 1.35 and the known-good has 1.34,
you will see '-1.34' '+1.35' — the '+' shows what the result produced.
'deleted file' = exists in known-good but not result (result REMOVED it).
'new file' = exists in result but not known-good (result ADDED it).
NOTE: vendor/ and go.sum are omitted from this DIFF (generated/resolver
output). Do not treat their absence as 'unchanged'; judge dependency
questions from go.mod version pins, not from go.sum hashes."
  local criteria="
PASS/FAIL CRITERIA: PASS means the result is a valid, correct k8s rebase.
FAIL means it has a data-correctness regression that would break compilation,
tests, or runtime behavior.
Differences that are NOT regressions (vote PASS or ABSTAIN, not FAIL):
- Style choices (import ordering, variable naming, comment wording)
- Dependency version drift in non-k8s dependencies (newer or older
  versions of ANY non-k8s dep, whether direct or indirect). The rebase
  bumps k8s.io/* deps and runs go mod tidy/vendor; resulting versions
  of non-k8s deps are whatever the resolver selects. A version
  difference is NOT a regression unless the diff shows code calling an
  API that provably does not exist at the resolved version — and that
  proof must come from the diff itself, not speculation.
- k8s.io/* package minor-version splits (e.g. k8s.io/api at v0.36.2
  while k8s.io/kubernetes is at v1.35.3) caused by MVS: openshift/api
  and controller-runtime commonly force k8s.io/api and k8s.io/client-go
  to a newer minor. This is normal and acceptable. Do NOT FAIL on a
  version split alone — it is only a regression if the diff shows code
  calling an API that does not exist in the vendored package. To verify,
  run: git show RESULT_REF:vendor/PKG/FILE.go | grep 'func FunctionName'
  — if the function exists in vendor at the pinned version, no regression.
- K8S_VERSION or KIND version patch-level differences between go.mod
  and CI/test tooling (e.g., v1.34.0 vs v1.34.1) — CI workflows
  typically override these defaults.
- Extra fixes the result made that the known-good didn't
- Fixes in known-good that the result lacks, IF the result still
  compiles and passes vet without them (scope differences, not bugs)
- Different but equally valid API migration paths (e.g., AddToScheme
  vs Install — both work if the vendored package exports both)
- OWNERS/reviewers file differences
- go.mod module path differences between forks and upstream (in
  require or replace blocks, e.g. ovn-org/X vs ovn-kubernetes/X)
REBASE-SCOPE CHECK (mandatory before claiming FAIL): Verify the issue
was INTRODUCED by the rebase, not pre-existing in the base branch. Run:
  git diff BASE_REF..RESULT_REF -- <file>  (use the actual SHA values shown at BASE_REF: and RESULT_REF: above)
If the file shows no diff, the difference with known-good existed before
the rebase started — it is pre-existing, vote PASS on that claim.
A difference is a REGRESSION only if the rebase INTRODUCES a problem
that did NOT exist on the base branch — specifically a build failure,
test failure, or runtime behavioral change (wrong types, broken wire
format, dropped functionality). If the same issue exists on the base
branch before the rebase, it is PRE-EXISTING and EQUIVALENT — vote
PASS, not FAIL, regardless of severity. Functionality present in the
known-good but absent from both the result AND the base branch is a
scope difference, not dropped functionality.

EVIDENCE CONSTRAINT: Do not fabricate file contents or claim code
exists that is not shown in the provided DIFF. If referencing files
outside the DIFF, state it as a concern to verify, not as established fact.
COMMIT MESSAGE CONSTRAINT: Commit subject lines are NOT evidence of code
changes. Do not assert a file was modified because its topic appears in a
commit subject line. You MUST use git show to confirm actual file content
before claiming a change exists.
VERIFICATION CONSTRAINT: Each distinct claim you use to support FAIL must
have its own VERIFIED: line showing a git show BASE_REF:<file> scope check.
A VERIFIED: line at the result branch confirms the diff is accurate but does
NOT satisfy this requirement — the check must be at BASE_REF to confirm the
issue was introduced by the rebase, not pre-existing. If you make three
claims, you need three BASE_REF-scoped VERIFIED: lines. A claim without a
BASE_REF VERIFIED: line cannot contribute to a FAIL verdict — it can only be
flagged as a concern."
  local _base_ref
  _base_ref=$(git merge-base "$known_good" "$result_branch" 2>/dev/null || echo "$known_good")
  local logs=$(git log --oneline "$_base_ref".."$result_branch" 2>/dev/null | head -15)
  local context="$direction
$criteria

BASE_REF: $_base_ref
RESULT_REF: $result_branch

DIFF (non-vendor):
$diff_nv

COMMITS: $logs
FILES: $diff_stat"

  local _court_dir="$PLUGIN_DIR/test/.matrix-state/court"
  local cdir="$_court_dir/$(date +%s)_$(repo_key "$repo")"
  mkdir -p "$cdir"

  # Phase A gives prosecution and defense the full $context (diff + commit history +
  # file summary). Phases B and C re-assemble the prompt from parts and omit $logs
  # and $diff_stat — judge and jury work from the diff alone to stay within limits.
  local _pros_prompt="$context

You are the PROSECUTION. Argue these are REGRESSIONS. Cite files and lines."
  local _def_prompt="$context

You are the DEFENSE. Argue these are EQUIVALENT or IMPROVEMENTS. Cite files and lines."

  info "$_log_prefix Phase A: Prosecution + Defense..."
  timeout 600 claude -p --strict-mcp-config --model "$COURT_MODEL" --permission-mode "$PERMISSION_MODE" --output-format text <<<"$_pros_prompt" > "$cdir/pros.txt" 2>"$cdir/pros.err" &
  local pid_pros=$!
  timeout 600 claude -p --strict-mcp-config --model "$COURT_MODEL" --permission-mode "$PERMISSION_MODE" --output-format text <<<"$_def_prompt" > "$cdir/def.txt" 2>"$cdir/def.err" &
  local pid_def=$!
  wait "$pid_pros" "$pid_def" 2>/dev/null || true

  # Retry helper: retry a phase if it failed with a transient error
  # ("Execution error" = claude CLI crash; "Warning:" only = model fallback with no content)
  _court_phase_ok() {
    local f="$1"
    local content; content=$(grep -v '^Warning:' "$f" 2>/dev/null | grep -v '^Execution error' || true)
    [[ ${#content} -ge 200 ]]
  }
  _court_retry() {
    local f="$1" errf="$2" prompt="$3" role="$4"
    shift 4
    if ! _court_phase_ok "$f"; then
      info "$_log_prefix   Retrying $role (transient error: $(head -1 "$f" 2>/dev/null | cut -c1-60))..."
      timeout 600 claude -p --strict-mcp-config --model "$COURT_MODEL" \
        --permission-mode "$PERMISSION_MODE" --output-format text "$@" <<<"$prompt" > "$f" 2>"$errf" || true
    fi
  }
  _court_retry "$cdir/pros.txt" "$cdir/pros.err" "$_pros_prompt" "prosecution"
  _court_retry "$cdir/def.txt" "$cdir/def.err" "$_def_prompt" "defense"

  local pros def
  pros=$(grep -v '^Warning:' "$cdir/pros.txt" 2>/dev/null | grep -v '^Execution error' || true)
  def=$(grep -v '^Warning:' "$cdir/def.txt" 2>/dev/null | grep -v '^Execution error' || true)
  if [[ ${#pros} -lt 200 || ${#def} -lt 200 ]]; then
    error "$_log_prefix Prosecution/defense too short (${#pros}/${#def} bytes — $(tail -1 "$cdir/pros.err" 2>/dev/null) / $(tail -1 "$cdir/def.err" 2>/dev/null))"
    return 2
  fi

  info "$_log_prefix Phase B: Judge..."
  local _judge_prompt
  _judge_prompt=$(cat <<EOF_JUDGE
$direction
$criteria

PROSECUTION:
$pros

DEFENSE:
$def

DIFF:
$diff_nv

NOTE: You have no tools and cannot determine whether a difference is
pre-existing on the base branch. For any prosecution claim where you
cannot confirm the issue was INTRODUCED by the rebase (not pre-existing),
mark it: SCOPE: unverifiable — jurors must run BASE_REF scope check.
Do not strike scope-unverifiable claims; flag them for juror verification.
Fact-check only. Strike claims not supported by the provided DIFF. Do NOT include any VERDICT line. Any VERDICT line in your output will be removed.
EOF_JUDGE
)
  timeout 600 claude -p --strict-mcp-config --model "$COURT_MODEL" --permission-mode "$PERMISSION_MODE" \
    --output-format text <<<"$_judge_prompt" 2>"$cdir/judge.err" | grep -v '^Warning:' > "$cdir/judge.txt" || true
  _court_retry "$cdir/judge.txt" "$cdir/judge.err" "$_judge_prompt" "judge"
  if ! _court_phase_ok "$cdir/judge.txt"; then
    warn "$_log_prefix Judge produced no output — jurors will proceed without fact-check"
  fi
  local judge
  judge=$(grep -iv '^\s*verdict\s*:' "$cdir/judge.txt" 2>/dev/null || true)
  echo "$judge" > "$cdir/judge.txt"

  info "$_log_prefix Phase C: Jury (parallel)..."
  local _juror_prompt
  _juror_prompt=$(cat <<EOF_JUROR_PROMPT
REPO: $repo
BASE_REF: $_base_ref
RESULT_REF: $result_branch

$direction
$criteria

TOOLS: You may run git show <ref>:<path> and git diff <ref1> <ref2> -- <path> to verify claims.
Do NOT run git checkout, git reset, git push, git commit, or any write operation.
For every claim you use to support FAIL, use git show to check the actual file at BASE_REF.

DIFF:
$diff_nv

PROSECUTION:
$pros

DEFENSE:
$def

JUDGE:
$judge

REQUIREMENT: For each claim you use to support FAIL, you MUST run:
  git show <BASE_REF>:<file>
(using the actual BASE_REF SHA shown above) to determine scope:
- Issue IS found at BASE_REF: pre-existing before rebase — vote PASS on that claim.
- File NOT found at BASE_REF (git show fails): file was added by the rebase —
  scope confirmed, evaluate the claim on its merits.
- File exists at BASE_REF but lacks the issue: scope confirmed, evaluate on merits.
Include a VERIFIED: line at BASE_REF for each FAIL claim. A FAIL verdict
without a BASE_REF scope check for each supporting claim is invalid.

Output format:
VERIFIED: <file>@<BASE_REF> — <finding>  (one line per FAIL claim — must show BASE_REF scope check)
VERDICT: PASS, FAIL, or ABSTAIN. One sentence. Use ABSTAIN only if you cannot determine whether the difference is a regression even after running git show.
EOF_JUROR_PROMPT
  )
  for j in 1 2 3; do
    <<<"$_juror_prompt" timeout 600 claude -p --strict-mcp-config --model "$COURT_MODEL" --permission-mode "$PERMISSION_MODE" --output-format text \
      --allowedTools "Bash(git show *),Bash(git diff *),Bash(git log *),Read" \
      > "$cdir/juror-$j.txt" 2>"$cdir/juror-$j.err" &
  done
  wait 2>/dev/null || true

  # Retry empty jurors once — mirrors prosecution/defense retry pattern
  for j in 1 2 3; do
    _court_retry "$cdir/juror-$j.txt" "$cdir/juror-$j.err" "$_juror_prompt" "juror-$j" \
      --allowedTools "Bash(git show *),Bash(git diff *),Bash(git log *),Read"
  done

  local empty_jurors=0
  for j in 1 2 3; do
    if [[ ! -s "$cdir/juror-$j.txt" ]] || grep -qx 'Execution error' "$cdir/juror-$j.txt" 2>/dev/null; then
      warn "$_log_prefix Juror $j produced no output ($(tail -1 "$cdir/juror-$j.err" 2>/dev/null))"
      empty_jurors=$((empty_jurors + 1))
    fi
  done

  local pass=0 fail=0
  for j in 1 2 3; do
    local jv=$(grep -ioE 'VERDICT:[* ]*(PASS|FAIL|ABSTAIN)' "$cdir/juror-$j.txt" 2>/dev/null | grep -ioE 'PASS|FAIL|ABSTAIN' | tail -1)
    jv="${jv^^}"
    case "$jv" in "PASS") pass=$((pass+1)); info "$_log_prefix   Juror $j: PASS";; "FAIL") fail=$((fail+1)); info "$_log_prefix   Juror $j: FAIL";; *) info "$_log_prefix   Juror $j: ABSTAIN";; esac
  done

  info "$_log_prefix Jury: $pass PASS, $fail FAIL"

  # Helper: show key findings from FAIL jurors to avoid transcript hunting
  _show_fail_reasons() {
    info "$_log_prefix Transcript: $cdir"
    for j in 1 2 3; do
      local jv; jv=$(grep -ioE 'VERDICT:[* ]*(PASS|FAIL|ABSTAIN)' "$cdir/juror-$j.txt" 2>/dev/null \
                     | grep -ioE 'PASS|FAIL|ABSTAIN' | tail -1)
      [[ "${jv^^}" != "FAIL" ]] && continue
      local verdict_text; verdict_text=$(grep -m1 'VERDICT:' "$cdir/juror-$j.txt" 2>/dev/null \
                                         | sed 's/^VERDICT:[* ]*//')
      local verified_text; verified_text=$(grep 'VERIFIED:' "$cdir/juror-$j.txt" 2>/dev/null \
                                           | tail -1 | sed 's/^VERIFIED:[[:space:]]*//')
      info "$_log_prefix   Juror $j: $verdict_text"
      [[ -n "$verified_text" ]] && info "$_log_prefix   Evidence: $verified_text"
    done
  }

  if [[ "$empty_jurors" -gt 1 ]]; then
    error "$_log_prefix INCONCLUSIVE (majority juror failure: $empty_jurors empty)"
    info "$_log_prefix Transcript: $cdir — check juror-*.err for details"
    return 2
  fi
  if [[ "$pass" -eq "$fail" && "$empty_jurors" -gt 0 ]]; then
    error "$_log_prefix INCONCLUSIVE (tied $pass-$fail with $empty_jurors empty juror(s))"
    _show_fail_reasons
    return 2
  fi
  local total=$((pass + fail))
  local abstaining_nonempty=$(( 3 - pass - fail - empty_jurors ))
  if [[ "$total" -lt 2 ]]; then
      error "$_log_prefix INCONCLUSIVE (no quorum — $pass pass, $fail fail, $abstaining_nonempty non-empty-abstain, $empty_jurors empty)"
      info "$_log_prefix Transcript: $cdir"
      return 2
  fi
  if [[ "$pass" -gt "$fail" ]]; then
    info "$_log_prefix VERDICT: PASS ($pass-$fail)"
    return 0
  fi
  if [[ "$pass" -eq "$fail" ]]; then
    error "$_log_prefix INCONCLUSIVE (tied $pass-$fail)"
    _show_fail_reasons
    return 2
  fi
  error "$_log_prefix VERDICT: FAIL ($fail-$pass)"
  _show_fail_reasons
  return 1
}

cmd_court_all() {
  local all_versions=false
  while [[ $# -gt 0 ]]; do
    case "$1" in --all-versions) all_versions=true ;; esac; shift
  done

  auto_record

  local tsv="$PLUGIN_DIR/test/.matrix-state/results.tsv"
  [[ ! -f "$tsv" ]] && { echo "No results yet. Run: make test"; return 0; }

  local saved_config="$CONFIG_FILE"
  local configs=()
  if $all_versions; then
    for cfg in "$PLUGIN_DIR/test"/config-[0-9]*.yaml; do
      [[ -f "$cfg" ]] && configs+=("$cfg")
    done
  else
    configs+=("$CONFIG_FILE")
  fi

  local run=0 passed=0 failed=0 errors=0 skipped=0
  for cfg in "${configs[@]}"; do
    CONFIG_FILE="$cfg"; _load_config
    local _court_pids=() _court_files=() _court_shorts=()
    # Court uses no worktrees, no disk space, no go builds — only API calls.
    # Natural limit is API rate limits, not system resources. Default: all repos at once.
    local max_court_concurrent=${MAX_COURT_CONCURRENT:-${#DEFAULT_REPOS[@]}}
    for repo in "${DEFAULT_REPOS[@]}"; do
      local short=$(repo_short "$repo")
      local _rk=$(repo_key "$repo")
      local _court_file="$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
      # Skip repos already courted (PASS/FAIL); retry INCONCLUSIVE.
      [[ -f "$_court_file" ]] && [[ "$(cat "$_court_file" 2>/dev/null)" != "INCONCLUSIVE" ]] && continue
      local latest_line=$(_latest_result_line "$short" "$VERSION" "$tsv")
      [[ -z "$latest_line" ]] && continue  # no matrix result yet
      local verdict=$(echo "$latest_line" | cut -f5)
      # Court only PASS rebases — no point reviewing a known-FAIL run.
      [[ "$verdict" != "PASS" ]] && continue
      # Rebase still in progress — let it finish before courting.
      [[ -f "$PLUGIN_DIR/test/.matrix-state/running/${VERSION}_$_rk" ]] && { skipped=$((skipped + 1)); continue; }

      repo=$(resolve_repo "$short" 2>/dev/null) || { warn "$short ($VERSION): cannot resolve"; skipped=$((skipped + 1)); continue; }
      cd "$repo" || { warn "$short ($VERSION): cannot cd"; skipped=$((skipped + 1)); continue; }
      local kg=$(_resolve_known_good "$short" "$repo")
      [[ -z "$kg" ]] && { warn "$short ($VERSION): no known-good configured"; skipped=$((skipped + 1)); continue; }
      local branch=$(find_newest_branch "$repo" "$VERSION")
      if [[ -z "$branch" ]]; then
        # If verdict is INCONCLUSIVE and the result branch is gone (cleaned after PASS),
        # clear the verdict so make results shows "pending" and re-courts on next test run.
        if [[ "$(cat "$_court_file" 2>/dev/null)" == "INCONCLUSIVE" ]]; then
          rm -f "$_court_file"
          warn "$short ($VERSION): INCONCLUSIVE verdict cleared (result branch gone — will re-court after next test run)"
        else
          warn "$short ($VERSION): no result branch found"
        fi
        skipped=$((skipped + 1)); continue
      fi

      # Throttle: wait for a slot if at concurrency limit
      while [[ ${#_court_pids[@]} -ge $max_court_concurrent ]]; do
        local _new_pids=()
        for _pid in "${_court_pids[@]}"; do
          kill -0 "$_pid" 2>/dev/null && _new_pids+=("$_pid")
        done
        _court_pids=("${_new_pids[@]}")
        [[ ${#_court_pids[@]} -ge $max_court_concurrent ]] && sleep 5
      done

      run=$((run + 1))
      info "Court $run: $short ($VERSION)"
      (
        if cmd_court "$branch" "$kg" "$repo"; then
          _verdict="PASS"
        else
          local _rc=$?
          case $_rc in
            1) _verdict="FAIL" ;;
            *) _verdict="INCONCLUSIVE" ;;
          esac
        fi
        mkdir -p "$(dirname "$_court_file")"
        echo "$_verdict" > "$_court_file"
        # Clean the worktree after PASS to prevent disk accumulation
        [[ "$_verdict" == "PASS" ]] && remove_worktrees "$repo" "$VERSION" 2>/dev/null || true
      ) &
      _court_pids+=($!)
      _court_files+=("$_court_file")
      _court_shorts+=("$short")
    done

    if [[ ${#_court_pids[@]} -gt 0 ]]; then
      wait "${_court_pids[@]}" 2>/dev/null || true
      for _idx in "${!_court_files[@]}"; do
        local _cf="${_court_files[$_idx]}" _cs="${_court_shorts[$_idx]}"
        if [[ -f "$_cf" ]]; then
          local _v=$(cat "$_cf")
          case "$_v" in
            PASS) passed=$((passed + 1)); info "$_cs ($VERSION): PASS" ;;
            FAIL) failed=$((failed + 1)); warn "$_cs ($VERSION): FAIL" ;;
            *) errors=$((errors + 1)); warn "$_cs ($VERSION): INCONCLUSIVE" ;;
          esac
        else
          errors=$((errors + 1)); warn "$_cs ($VERSION): ERROR (no verdict)"
        fi
      done
    fi
  done

  CONFIG_FILE="$saved_config"
  _load_config

  echo ""
  if [[ "$run" -eq 0 && "$skipped" -eq 0 ]]; then
    echo "No pending court reviews."
    return 0
  fi
  echo "Court complete: $passed passed, $failed failed, $errors errors, $skipped skipped (of $((run + skipped)) pending)"

  # Show transcript paths for non-PASS outcomes so users can dig into details
  if [[ "$((failed + errors))" -gt 0 ]]; then
    local _court_dir="$PLUGIN_DIR/test/.matrix-state/court"
    echo ""
    echo "Non-PASS transcripts (most recent per repo):"
    for _idx in "${!_court_files[@]}"; do
      _cf="${_court_files[$_idx]}" _cs="${_court_shorts[$_idx]}"
      local _v; _v=$(cat "$_cf" 2>/dev/null || echo "ERROR")
      [[ "$_v" == "PASS" ]] && continue
      # Find the most recent court transcript dir for this repo
      local _rk; _rk="${_cs//\//\_}"
      local _tdir; _tdir=$(ls -td "$_court_dir"/*"_${_rk}" 2>/dev/null | head -1)
      if [[ -n "$_tdir" ]]; then
        echo "  [$_v] $_cs ($VERSION): $_tdir"
        # Show key reason from most recent FAIL juror
        for j in 1 2 3; do
          local jv; jv=$(grep -ioE 'VERDICT:[* ]*(PASS|FAIL)' "$_tdir/juror-$j.txt" 2>/dev/null \
                         | grep -ioE 'PASS|FAIL' | tail -1)
          [[ "${jv^^}" != "FAIL" ]] && continue
          local vt; vt=$(grep -m1 'VERDICT:' "$_tdir/juror-$j.txt" 2>/dev/null | sed 's/^VERDICT:[* ]*//')
          echo "    Juror $j: $vt"
          break  # Show first FAIL juror only for brevity
        done
      else
        echo "  [$_v] $_cs ($VERSION)"
      fi
    done
  fi
}

# ── Watch ──────────────────────────────────────────────────────────────

cmd_watch() {
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  _SESSION_CACHE_AGE=0
  build_session_cache
  local active=0
  local -a _watch_rows=()
  for running_file in "$state_dir/running"/*; do
    [[ -f "$running_file" ]] || continue
    active=$((active + 1))
    local _running_key=$(basename "$running_file")
    local _raw=$(cat "$running_file")
    local _file_spec _f2 _sid _file_version  # _f2 is field 2 of the running file; read to advance IFS position, not used
    IFS=$'\t' read -r _file_spec _f2 _sid _file_version _ <<< "$_raw"
    local _bare_rk=$(repo_key_from_running "$_file_version" "$_running_key")
    local short="${_bare_rk//_//}"
    local repo="$REPOS_DIR/$short"
    [[ -d "$repo" ]] || continue
    local session_state="gone"
    if [[ -n "$_sid" ]]; then
      local _found_state
      _found_state=$(echo "$_SESSION_CACHE" | while IFS=$'\t' read -r _cwd _st _el _pid _s _rest; do
        [[ "$_s" == "$_sid"* ]] && echo "$_st" && break  # prefix match: running file stores a truncated session ID
      done)
      [[ -n "$_found_state" ]] && session_state="$_found_state"
    fi
    _worktree_info "$repo" || true
    local wt="$_WT_PATH" _branch="$_WT_BRANCH"
    # Fallback: session running in main repo (no .claude/worktrees entry — either no
    # from_commit, or detached HEAD after _test-from-* checkout). Treat main repo as
    # "wt" so gate count + phase display still work. Read branch from branch-name file
    # (written by the skill at init) rather than git branch --show-current, which
    # returns empty in detached HEAD.
    if [[ -z "$wt" && "$session_state" == "working" && -d "$repo/.rebase-tmp" ]]; then
      wt="$repo"
      _branch=$(cat "$repo/.rebase-tmp/branch-name" 2>/dev/null)
      [[ -z "$_branch" ]] && _branch=$(git -C "$repo" branch --show-current 2>/dev/null)
    fi
    local gc=0 gf=0 gs=0 commit_msg="-" diff_info="-"
    if [[ -n "$wt" ]]; then
      local _db=$(git -C "$repo" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
      : "${_db:=main}"
      if [[ -n "$_branch" ]]; then
        local n_commits=$(git -C "$repo" rev-list --count "$_db".."$_branch" 2>/dev/null || echo 0)
        [[ "$n_commits" -gt 0 ]] && commit_msg=$(git -C "$wt" log --format="%s" -1 "$_branch" 2>/dev/null | head -c 28)
      fi
      _collect_gate_dirs "$repo"
      if [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
        read -r gc gf gs _gfn <<< "$(_tally_gates "${_GATE_DIRS[@]}")"
      fi
    fi
    # Use version-appropriate config to avoid cross-version known_good mismatch.
    # Must also set VERSION since _resolve_known_good uses it for the cache key.
    local _saved_cf_watch="$CONFIG_FILE" _saved_ver_watch="$VERSION"
    local _ver_cf_watch="${PLUGIN_DIR}/test/config-${_file_version%.*}.yaml"
    if [[ -f "$_ver_cf_watch" ]]; then
      CONFIG_FILE="$_ver_cf_watch"
      VERSION="$_file_version"
    fi
    local kg=$(_resolve_known_good "$short" "$repo")
    CONFIG_FILE="$_saved_cf_watch"
    VERSION="$_saved_ver_watch"
    if [[ -n "$kg" && -n "$wt" && -n "$_branch" ]]; then
      # Count changed hunks (each '@@...@@' header = one hunk). nv excludes vendor; nv_all includes it.
      local nv=$(git -C "$repo" diff "$_branch" "$kg" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
      local nv_all=$(git -C "$repo" diff "$_branch" "$kg" -- . ':!.rebase-tmp' 2>/dev/null | grep -c '^@@' || true)
      diff_info="${nv} code"
      [[ "$nv_all" -gt "$nv" ]] && diff_info="$diff_info (+$((nv_all - nv)) vendor)"
    fi
    # Show "needs-court" when session is done, gates complete, no done file yet
    if [[ "$session_state" == "done" || "$session_state" == "gone" ]]; then
      local _done_key=$(_done_key "$_file_version" "$_file_spec" "$_bare_rk")
      if [[ "$gc" -ge "$EXPECTED_GATES" && ! -f "$state_dir/done/$_done_key" ]]; then
        session_state="needs-court"
      fi
    fi
    # Replace "working" with the current phase + time since last activity.
    # Phase from current_step: 1=rebase 2=compile 3=autofix 4=verify 5=finishing.
    # Time is minutes since the most recent file write in .rebase-tmp/ —
    # this reflects actual agent activity, not just when the step started.
    # Use: phase means what the step covers; time tells you if it's stalled.
    if [[ -n "$wt" && "$session_state" == "working" ]]; then
      local _step; _step=$(grep '"current_step"' "$wt/.rebase-tmp/state.json" 2>/dev/null | grep -oE '[0-9]+' | head -1)
      if [[ -n "$_step" ]]; then
        local _phase
        case "$_step" in
          1) _phase="rebase" ;;   2) _phase="compile" ;;
          3) _phase="autofix" ;;  4) _phase="verify" ;;
          5) _phase="finishing" ;; *) _phase="step$_step" ;;
        esac
        # Time since last file activity in .rebase-tmp/ top-level files only.
        # -maxdepth 1 excludes all subdirectories (gates/, and any others).
        local _last_ts; _last_ts=$(find "$wt/.rebase-tmp" -maxdepth 2 -type f \
          -not -path '*/gates/*' \
          -exec stat -c '%Y' {} \; 2>/dev/null | sort -rn | head -1)
        if [[ -n "$_last_ts" && "$_last_ts" -gt 0 ]]; then
          local _idle=$(( ($(date +%s) - _last_ts) / 60 ))
          [[ "$_idle" -gt 0 ]] && _phase="${_phase} ${_idle}m"
        fi
        session_state="$_phase"
      fi
    fi
    local gate_str="${gc}/${EXPECTED_GATES}"
    local _gsuffix=""
    [[ "$gf" -gt 0 ]] && _gsuffix="${gf}F"
    [[ "$gs" -gt 0 ]] && _gsuffix="${_gsuffix:+${_gsuffix},}${gs}S"
    [[ -n "$_gsuffix" ]] && gate_str="${gate_str} (${_gsuffix})"
    # Truncate repo name at 40 chars to prevent table blowout
    local _short_r="$short"
    [[ "${#_short_r}" -gt 40 ]] && _short_r="${_short_r:0:39}…"
    _watch_rows+=("$_short_r"$'\t'"${_file_version:-?}"$'\t'"${_file_spec:-?}"$'\t'"$session_state"$'\t'"$gate_str"$'\t'"$commit_msg"$'\t'"$diff_info")
  done
  if [[ "$active" -le 0 ]]; then echo "(no active tests)"; return 0; fi
  # Compute dynamic column widths from actual data + header minimums
  local w_r=4 w_v=3 w_sp=4 w_st=6 w_g=5 w_c=13 w_d=13
  for _wr in "${_watch_rows[@]}"; do
    local _r _v _sp _st _g _c _d
    IFS=$'\t' read -r _r _v _sp _st _g _c _d <<< "$_wr"
    [[ ${#_r}  -gt $w_r  ]] && w_r=${#_r}
    [[ ${#_v}  -gt $w_v  ]] && w_v=${#_v}
    [[ ${#_sp} -gt $w_sp ]] && w_sp=${#_sp}
    [[ ${#_st} -gt $w_st ]] && w_st=${#_st}
    [[ ${#_g}  -gt $w_g  ]] && w_g=${#_g}
    [[ ${#_c}  -gt $w_c  ]] && w_c=${#_c}
    [[ ${#_d}  -gt $w_d  ]] && w_d=${#_d}
  done
  local _hfmt="%-${w_r}s  %-${w_v}s  %-${w_sp}s  %-${w_st}s  %-${w_g}s  %-${w_c}s  %s\n"
  local _dfmt="%-${w_r}s  %-${w_v}s  %-${w_sp}s  %-${w_st}s  %-${w_g}s  %-${w_c}s  %-${w_d}s\n"
  local _sep_r; _sep_r=$(printf '%*s' $w_r  '' | tr ' ' '-')
  local _sep_v; _sep_v=$(printf '%*s' $w_v  '' | tr ' ' '-')
  local _sep_sp; _sep_sp=$(printf '%*s' $w_sp '' | tr ' ' '-')
  local _sep_st; _sep_st=$(printf '%*s' $w_st '' | tr ' ' '-')
  local _sep_g; _sep_g=$(printf '%*s' $w_g  '' | tr ' ' '-')
  local _sep_c; _sep_c=$(printf '%*s' $w_c  '' | tr ' ' '-')
  local _sep_d; _sep_d=$(printf '%*s' $w_d  '' | tr ' ' '-')
  printf "$_hfmt" "REPO" "VER" "SPEC" "STATUS" "GATES" "LATEST COMMIT" "VS KNOWN-GOOD"
  printf "$_dfmt" "$_sep_r" "$_sep_v" "$_sep_sp" "$_sep_st" "$_sep_g" "$_sep_c" "$_sep_d"
  for _wr in "${_watch_rows[@]}"; do
    IFS=$'\t' read -r _r _v _sp _st _g _c _d <<< "$_wr"
    printf "$_dfmt" "$_r" "$_v" "$_sp" "$_st" "$_g" "$_c" "$_d"
  done
  return 0
}

# ── Results Display ────────────────────────────────────────────────────

cmd_results() {
  local repo="" court=false all_versions=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --court) court=true ;;
      --all-versions) all_versions=true ;;
      *) repo="$1" ;;
    esac; shift
  done

  auto_record
  if [[ -n "$repo" ]]; then
    _results_one "$repo" "$court"
  elif $all_versions; then
    _results_all_versions
  else
    _results_for_version
  fi
}

_results_one() {
  local repo="$1" court="${2:-false}"
  local repo_input="$repo"
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input — check the repo name matches config.yaml, or run make clone-all to clone missing repos"
  local short=$(repo_short "$repo")
  cd "$repo" || die "Cannot cd to $repo"
  _worktree_info "$repo" || true
  local wt="$_WT_PATH"
  _collect_gate_dirs "$repo"
  local wt_in_progress=false
  [[ -n "$wt" && ${#_GATE_DIRS[@]} -eq 0 ]] && wt_in_progress=true

  echo "── $short ──"
  if $wt_in_progress; then
    echo "Run in progress (worktree exists, gates not yet written)"
  elif [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
    local total=0 gfail=0 gskip=0 _gfn=""
    read -r total gfail gskip _gfn <<< "$(_tally_gates "${_GATE_DIRS[@]}")"
    # _gfn (comma-separated failing gate names from _tally_gates) is not used here.
    # Failing gates are re-discovered by scanning .report files below, which also
    # provides the DETAILS: body needed for display.
    local _skip_note=""
    [[ "$gskip" -gt 0 ]] && _skip_note=", $gskip skipped"
    if [[ "$total" -ge "$EXPECTED_GATES" && "$gfail" -eq 0 ]]; then
      echo "Gates: all $total pass${_skip_note}"
    elif [[ "$gfail" -gt 0 ]]; then
      echo "Gates: $gfail FAILED ($total/$EXPECTED_GATES complete${_skip_note})"
    else
      echo "Gates: $total/$EXPECTED_GATES complete (in progress${_skip_note})"
    fi
    # Collect deduped gate files across all worktrees (newest wins per gate name)
    local -A _rgate_files=()
    for _gd in "${_GATE_DIRS[@]}"; do
      for f in "$_gd"/*.report; do
        [[ -f "$f" ]] || continue
        local _gn=$(basename "$f" .report)
        if [[ -z "${_rgate_files[$_gn]+x}" ]]; then
          _rgate_files[$_gn]="$f"
        else
          local _old_ts=$(stat -c '%Y' "${_rgate_files[$_gn]}" 2>/dev/null || echo 0)
          local _new_ts=$(stat -c '%Y' "$f" 2>/dev/null || echo 0)
          [[ "$_new_ts" -gt "$_old_ts" ]] && _rgate_files[$_gn]="$f"
        fi
      done
    done
    for _gn in "${!_rgate_files[@]}"; do
      local f="${_rgate_files[$_gn]}"
      local v=$(grep -iE '^(VERDICT|STATUS|RESULT):' "$f" 2>/dev/null | head -1)
      v="${v^^}"
      [[ "$v" != *"FAIL"* ]] && continue
      [[ " $INFO_GATES " == *" ${_gn#step?-} "* ]] && continue
      local _gdir="${f%/*}"
      local _repo_root="${_gdir%/.rebase-tmp/gates}"
      local _branch_tip_ts=0
      if [[ -d "$_repo_root/.git" || -f "$_repo_root/.git" ]]; then
        _branch_tip_ts=$(git -C "$_repo_root" log -1 --format='%ct' 2>/dev/null || echo 0)
      fi
      _is_stale_fail "$f" "$_branch_tip_ts" && continue
      echo ""
      echo "FAILED: $_gn"
      # Indent every line after the DETAILS: header so it reads as a sub-block.
      awk '/^DETAILS:/{d=1; print; next} d{print "  "$0; next} {print}' "$f"
    done
  else
    echo "Gates: none (no reports found)"
  fi

  # Derive version from TSV's latest entry to avoid cross-version known_good contamination
  local _tsv_ver="$VERSION"
  local _tsv_latest; _tsv_latest=$(_latest_result_line "$short" "$VERSION" "$PLUGIN_DIR/test/.matrix-state/results.tsv" 2>/dev/null)
  [[ -z "$_tsv_latest" ]] && _tsv_latest=$(awk -F'\t' -v r="$short" '$4==r' "$PLUGIN_DIR/test/.matrix-state/results.tsv" 2>/dev/null | tail -1)
  [[ -n "$_tsv_latest" ]] && _tsv_ver=$(echo "$_tsv_latest" | cut -f2)
  local _saved_cf_ro="$CONFIG_FILE" _saved_ver_ro="$VERSION"
  local _ver_cf_ro="${PLUGIN_DIR}/test/config-${_tsv_ver%.*}.yaml"
  if [[ -f "$_ver_cf_ro" ]]; then CONFIG_FILE="$_ver_cf_ro"; VERSION="$_tsv_ver"; fi
  local kg=$(_resolve_known_good "$short" "$repo")
  CONFIG_FILE="$_saved_cf_ro"; VERSION="$_saved_ver_ro"
  if [[ -n "$kg" ]]; then
    local branch=$(find_newest_branch "$repo" "$_tsv_ver")
    if [[ -n "$branch" ]]; then
      local nv=$(git diff "$branch" "$kg" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
      echo ""
      if [[ "$nv" -eq 0 ]]; then
        echo "Diff vs known-good ${kg:0:12}: identical (non-vendor)"
      else
        echo "Diff vs known-good ${kg:0:12}: $nv code hunks differ"
      fi
      # --court: run cmd_court and persist verdict to .matrix-state/court/ for use
      # by _results_for_version. exit 0=PASS, exit 1=FAIL, exit 2+=infra error (not recorded).
      if [[ "$court" == "true" ]]; then
        local _court_verdict=""
        if cmd_court "$branch" "$kg" "$repo"; then
          _court_verdict="PASS"
        else
          local _exit=$?
          # exit 1 = FAIL verdict; exit 2+ = infrastructure error (don't record)
          [[ $_exit -eq 1 ]] && _court_verdict="FAIL"
        fi
        if [[ -n "$_court_verdict" ]]; then
          mkdir -p "$PLUGIN_DIR/test/.matrix-state/court"
          echo "$_court_verdict" > "$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$(repo_key "$repo")"
        fi
      fi
    fi
  fi

  echo ""
  echo "Recent results:"
  # Field 4 is the short repo name (cols: 1=ts 2=ver 3=spec 4=repo 5=verdict 6=detail).
  # Intentionally not version-filtered: shows the last 5 entries across all versions.
  awk -F'\t' -v r="$short" '$4==r' "$PLUGIN_DIR/test/.matrix-state/results.tsv" 2>/dev/null | tail -5 | while IFS=$'\t' read -r ts ver spec _r verdict detail; do
    printf "  %-22s %-8s %-8s %s\n" "$ts" "$ver" "$verdict" "$detail"
  done
}

_results_for_version() {
  local tsv="$PLUGIN_DIR/test/.matrix-state/results.tsv"
  if [[ ! -f "$tsv" ]]; then echo "No results yet. Run: make test"; return 0; fi

  local all_pass=true
  local -a _res_rows=()
  for repo in "${DEFAULT_REPOS[@]}"; do
    local short=$(repo_short "$repo")
    local _rk=$(repo_key "$repo")
    local latest_line=$(_latest_result_line "$short" "$VERSION" "$tsv")
    if [[ -n "$latest_line" ]]; then
      local ts=$(echo "$latest_line" | cut -f1 | sed 's/T/ /;s/Z//')
      local verdict=$(echo "$latest_line" | cut -f5)
      local detail=$(echo "$latest_line" | cut -f6)
      local court_result="-"
      local _court_file="$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
      if [[ -f "$_court_file" ]]; then
        court_result=$(cat "$_court_file")
      elif [[ "$verdict" == "PASS" ]]; then
        local _kg=$(yq ".repos.\"$short\".known_good // \"\"" "$CONFIG_FILE" 2>/dev/null)
        if [[ -z "$_kg" || "$_kg" == "null" ]]; then
          court_result="N/A"
        else
          court_result="pending"
        fi
      fi
      if [[ "$(_config_val "$short" "expected_fail")" == "true" && "$verdict" != "PASS" ]]; then
        verdict="XFAIL"
      elif [[ "$verdict" != "PASS" ]]; then
        all_pass=false
      elif [[ "$court_result" == "FAIL" ]]; then
        all_pass=false
      fi
      _res_rows+=("$short"$'\t'"$verdict"$'\t'"$court_result"$'\t'"$ts"$'\t'"$detail")
    else
      [[ "$(_config_val "$short" "expected_fail")" != "true" ]] && all_pass=false
      local _reason="not tested"
      local _resolved=$(resolve_repo "$short" 2>/dev/null)
      if [[ -n "$_resolved" ]]; then
        local _ver=$(_repo_k8s_version "$_resolved")
        if [[ "$_ver" == "v0.${VERSION#*.}" || "$_ver" == "v$VERSION" ]] && [[ -z "$(_config_val "$short" "from_commit")" ]]; then
          _reason="already at $_ver — set from-commit to test"
        fi
      fi
      _res_rows+=("$short"$'\t'"-"$'\t'"-"$'\t'""$'\t'"$_reason")
    fi
  done
  # Dynamic column widths from actual data + header minimums
  local w_rr=4 w_vd=7 w_ct=5 w_ts=8
  for _rr in "${_res_rows[@]}"; do
    local _r _v _ct _ts _dt
    IFS=$'\t' read -r _r _v _ct _ts _dt <<< "$_rr"
    [[ ${#_r}  -gt $w_rr ]] && w_rr=${#_r}
    [[ ${#_v}  -gt $w_vd ]] && w_vd=${#_v}
    [[ ${#_ct} -gt $w_ct ]] && w_ct=${#_ct}
    [[ ${#_ts} -gt $w_ts ]] && w_ts=${#_ts}
  done
  local _rfmt="%-${w_rr}s  %-${w_vd}s  %-${w_ct}s  %-${w_ts}s  %s\n"
  printf "$_rfmt" "REPO" "VERDICT" "COURT" "LAST RUN" "DETAIL"
  printf "$_rfmt" "$(printf '%*s' $w_rr '' | tr ' ' '-')" \
                  "$(printf '%*s' $w_vd '' | tr ' ' '-')" \
                  "$(printf '%*s' $w_ct '' | tr ' ' '-')" \
                  "$(printf '%*s' $w_ts '' | tr ' ' '-')" "------"
  for _rr in "${_res_rows[@]}"; do
    local _r _v _ct _ts _dt
    IFS=$'\t' read -r _r _v _ct _ts _dt <<< "$_rr"
    printf "$_rfmt" "$_r" "$_v" "$_ct" "$_ts" "$_dt"
  done

  echo ""
  if $all_pass; then echo "OVERALL: PASS"; return 0; else echo "OVERALL: FAIL"; return 1; fi
}

_results_all_versions() {
  local tsv="$PLUGIN_DIR/test/.matrix-state/results.tsv"
  [[ ! -f "$tsv" ]] && { echo "No results yet. Run: make test"; return 0; }

  local saved_config="$CONFIG_FILE"
  local versions_pass=0 versions_total=0 first=true

  for cfg in "$PLUGIN_DIR/test"/config-[0-9]*.yaml; do
    [[ -f "$cfg" ]] || continue
    CONFIG_FILE="$cfg"
    _load_config

    $first || echo ""
    first=false
    echo "── $VERSION ──"
    if _results_for_version; then
      versions_pass=$((versions_pass + 1))
    fi
    versions_total=$((versions_total + 1))
  done

  CONFIG_FILE="$saved_config"
  _load_config

  echo ""
  if [[ "$versions_total" -eq 0 ]]; then
    echo "No config files found in test/"
  else
    echo "SUMMARY: $versions_pass of $versions_total versions PASS"
  fi
}

# ── Configuration ──────────────────────────────────────────────────────

cmd_set_known_good() {
  local repo="" ref="" url=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url) shift; url="${1:-}"; [[ -z "$url" ]] && die "--url needs value" ;;
      *) [[ -z "$repo" ]] && repo="$1" || ref="$1" ;;
    esac; shift
  done
  [[ -z "$repo" || -z "$ref" ]] && die "Usage: set-known-good <repo> <ref> [--url <url>]"
  local repo_input="$repo"
  _ensure_repo "$(repo_short "$repo_input")"
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input — check the repo name matches config.yaml, or run make clone-all to clone missing repos"
  local short=$(repo_short "$repo")

  if [[ -n "$url" ]]; then
    yq -i ".repos.\"$short\".known_good = {\"url\": \"$url\", \"ref\": \"$ref\"}" "$CONFIG_FILE"
    info "Set known-good for $short: $ref (from $url)"
  else
    cd "$repo" || die "Cannot cd to $repo"
    local resolved
    resolved=$(git rev-parse --verify "$ref" 2>/dev/null) || die "Ref not found: $ref"
    [[ "$ref" =~ ^[0-9a-fA-F]{6,40}$ ]] && ref="$resolved"
    yq -i ".repos.\"$short\".known_good = \"$ref\"" "$CONFIG_FILE"
    info "Set known-good for $short: $ref"
  fi
}

# ── Matrix ────────────────────────────────────────────────────────────

cmd_matrix() {
  local spec="${1:-none}"; shift || true
  local max_retries=2

  # Discover all versioned configs
  local configs=()
  for cfg in "$PLUGIN_DIR/test"/config-[0-9]*.yaml; do
    [[ -f "$cfg" ]] && configs+=("$cfg")
  done
  [[ ${#configs[@]} -eq 0 ]] && die "No config-*.yaml files found in $PLUGIN_DIR/test/"

  local saved_config="$CONFIG_FILE"
  local versions_pass=0 versions_fail=0 versions_total=0
  local matrix_start=$(date +%s)

  info "Matrix: ${#configs[@]} versions, spec=$spec, max_retries=$max_retries"

  for cfg in "${configs[@]}"; do
    CONFIG_FILE="$cfg"
    _load_config
    versions_total=$((versions_total + 1))

    local version_start=$(date +%s)
    info "================================================================"
    info "MATRIX [$versions_total/${#configs[@]}]: $VERSION (spec=$spec)"
    info "================================================================"

    # Phase 1: Run all repos for this version
    info "Phase 1: test-all (spec=$spec)..."
    cmd_test_all "$spec"

    # Phase 2: Court all repos that passed gates
    info "Phase 2: court-all..."
    cmd_court_all

    # Phase 3: Identify failures and retry
    local retry=0
    while [[ "$retry" -lt "$max_retries" ]]; do
      local tsv="$PLUGIN_DIR/test/.matrix-state/results.tsv"
      local failed_repos=() court_only_repos=()
      for repo in "${DEFAULT_REPOS[@]}"; do
        local short=$(repo_short "$repo")
        local _rk=$(repo_key "$repo")

        [[ "$(_config_val "$short" "expected_fail")" == "true" ]] && continue

        local latest_line=$(_latest_result_line "$short" "$VERSION" "$tsv")
        [[ -z "$latest_line" ]] && continue

        local verdict=$(echo "$latest_line" | cut -f5)
        if [[ "$verdict" == "FAIL" ]]; then
          failed_repos+=("$repo")
          continue
        fi

        # Gate-PASS but court-INCONCLUSIVE: court-only retry (no full re-test)
        local _court_file="$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
        if [[ -f "$_court_file" ]]; then
          local _cv=$(cat "$_court_file")
          if [[ "$_cv" == "INCONCLUSIVE" ]]; then
            court_only_repos+=("$repo")
          elif [[ "$_cv" == "FAIL" ]]; then
            failed_repos+=("$repo")
          fi
        fi
      done

      [[ ${#failed_repos[@]} -eq 0 && ${#court_only_repos[@]} -eq 0 ]] && break

      retry=$((retry + 1))

      # Court-only retries (fast: ~5 min per repo)
      if [[ ${#court_only_repos[@]} -gt 0 ]]; then
        info "Phase 3: Retry $retry/$max_retries — ${#court_only_repos[@]} court-only repos"
        for repo in "${court_only_repos[@]}"; do
          local _rk=$(repo_key "$repo")
          info "  Court retry: $(repo_short "$repo")"
          rm -f "$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
        done
        info "Retry $retry: court-all (court-only)..."
        cmd_court_all
      fi

      # Full retries (slow: 30-90 min per repo)
      if [[ ${#failed_repos[@]} -gt 0 ]]; then
        info "Phase 3: Retry $retry/$max_retries — ${#failed_repos[@]} gate-failed repos"
        for repo in "${failed_repos[@]}"; do
          local short=$(repo_short "$repo")
          local _rk=$(repo_key "$repo")
          info "  Retrying: $short"

          local _done_key=$(_done_key "$VERSION" "$spec" "$_rk")
          rm -f "$PLUGIN_DIR/test/.matrix-state/done/$_done_key"
          rm -f "$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
          cmd_clean "$repo" 2>/dev/null || true
        done

        info "Retry $retry: test-all..."
        cmd_test_all "$spec"

        info "Retry $retry: court-all..."
        cmd_court_all
      fi
    done

    # Version summary
    local version_elapsed=$(( $(date +%s) - version_start ))
    local version_min=$((version_elapsed / 60))
    info ""
    info "── $VERSION complete (${version_min}m) ──"
    if _results_for_version; then
      versions_pass=$((versions_pass + 1))
    else
      versions_fail=$((versions_fail + 1))
    fi
  done

  # Restore original config
  CONFIG_FILE="$saved_config"
  _load_config

  # Final summary across all versions
  local matrix_elapsed=$(( $(date +%s) - matrix_start ))
  local matrix_hours=$((matrix_elapsed / 3600))
  local matrix_min=$(( (matrix_elapsed % 3600) / 60 ))
  info ""
  info "================================================================"
  info "MATRIX COMPLETE"
  info "================================================================"
  cmd_results --all-versions
  echo ""
  echo "Time: ${matrix_hours}h ${matrix_min}m"
  echo "Versions: $versions_pass of $versions_total PASS"
  [[ "$versions_fail" -eq 0 ]]
}

cmd_set_from_commit() {
  [[ $# -lt 2 ]] && die "Usage: set-from-commit <repo> <commit>"
  local repo="$1" commit="$2"
  local repo_input="$repo"
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input — check the repo name matches config.yaml, or run make clone-all to clone missing repos"
  cd "$repo" || die "Cannot cd to $repo"
  local full_sha
  full_sha=$(git rev-parse --verify "$commit" 2>/dev/null) || die "Commit not found: $commit"
  local short=$(repo_short "$repo")
  yq -i ".repos.\"$short\".from_commit = \"$full_sha\"" "$CONFIG_FILE"
  info "Set from-commit for $short: ${full_sha:0:12}"
}

# ── Main Dispatch ──────────────────────────────────────────────────────

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args...]

Commands:
  matrix [spec]                     Full pipeline: all versions x all repos with retries
  test-all [--version X.Y.Z]        Run core suite (all 6 repos, batches of $MAX_CONCURRENT)
  court-all [--all-versions]        Run adversarial court on all pending repos
  test <spec> <repo> [<repo>...] [--version]    Run specific test case(s)
  results [repo] [--court] [--all-versions]  Show results (all versions by default via make)
  set-known-good <repo> <ref> [--url <url>]  Set known-good reference
  set-from-commit <repo> <commit>   Set pre-merge commit for historical testing
  stop [repo...|--all]              Stop running test sessions
  clean [--version X.Y.Z] [repos...]  Cleanup worktrees and state (all versions or one)

Specs: all, all-fns, all-patterns, fn:<tag>, pattern:<key>
Tags: $(echo "${!TAG_TO_PATTERN[@]}" | tr ' ' ', ')

Repos accept full paths or short names (openshift/multus-cni, ovn-org/ovn-kubernetes).

Examples:
  $(basename "$0") test-all
  $(basename "$0") test all openshift/multus-cni
  $(basename "$0") results
  $(basename "$0") results openshift/multus-cni --court
  $(basename "$0") set-known-good openshift/multus-cni d801f0f40708
  $(basename "$0") set-known-good openshift/multus-cni bump1.36 --url https://github.com/user/fork.git
EOF
  exit 0
}

[[ $# -eq 0 ]] && usage

COMMAND="$1"; shift
case "$COMMAND" in
  matrix)         cmd_matrix "$@" ;;
  test-all)       cmd_test_all "$@" ;;
  court-all)      cmd_court_all "$@" ;;
  test)           cmd_test "$@" ;;
  watch)          cmd_watch "$@" ;;
  results)        cmd_results "$@" ;;
  set-known-good)   cmd_set_known_good "$@" ;;
  set-from-commit)  cmd_set_from_commit "$@" ;;
  stop)             cmd_stop "$@" ;;
  clean)          cmd_clean "$@" ;;
  -h|--help|help) usage ;;
  *)              die "Unknown command: $COMMAND (try --help)" ;;
esac
