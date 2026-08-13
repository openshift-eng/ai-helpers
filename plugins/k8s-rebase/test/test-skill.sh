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
REPOS_DIR="${REPOS_DIR%/}"
PERMISSION_MODE="${PERMISSION_MODE:-bypassPermissions}"
CONFIG_FILE="$(cd "$(dirname "${CONFIG_FILE:-$SCRIPT_DIR/config.yaml}")" && pwd)/$(basename "${CONFIG_FILE:-$SCRIPT_DIR/config.yaml}")"
_MAX_CONCURRENT_FROM_ENV="${MAX_CONCURRENT:-}"
MAX_CONCURRENT="${MAX_CONCURRENT:-3}"
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
  _WT_PATH=$(echo "$_wt_line" | awk '{print $1}')
  _WT_BRANCH=$(echo "$_wt_line" | grep -oE '\[.+\]' | tr -d '[]' | sed 's/ locked//')
}

# Collect gate report directories from ALL worktrees (+ main repo).
# Sets _GATE_DIRS array.  Fixes false negatives when reports are split
# across two worktrees (e.g. 1 report in wt-A + 32 in wt-B = 33 total).
_collect_gate_dirs() {
  _GATE_DIRS=()
  local _repo="$1"
  [[ -d "$_repo/.rebase-tmp/gates" ]] && _GATE_DIRS+=("$_repo/.rebase-tmp/gates")
  while IFS= read -r _wt_line; do
    [[ -z "$_wt_line" ]] && continue
    local _wtp; _wtp=$(echo "$_wt_line" | awk '{print $1}')
    [[ -d "$_wtp/.rebase-tmp/gates" ]] && _GATE_DIRS+=("$_wtp/.rebase-tmp/gates")
  done < <(git -C "$_repo" worktree list 2>/dev/null | grep '\.claude/worktrees')
}

# Tally gate reports across one or more directories.
# Accepts variadic args: _tally_gates dir1 [dir2 ...]
# When the same gate name exists in multiple dirs, the newest file wins.
_tally_gates() {
  local _gt=0 _gf=0 _gs=0 _gfail_names=""
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
    if [[ "$_gv" == *SKIP* || " $INFO_GATES " == *" ${_gn#step?-} "* ]]; then
      _gs=$((_gs + 1))
    elif [[ "$_gv" == *PASS* ]]; then
      : # counted in _gt
    else
      # FAIL or missing verdict — check if report predates the branch tip
      if _is_stale_fail "$_gf_file" "$_branch_tip_ts"; then
        _gs=$((_gs + 1))
      else
        _gf=$((_gf + 1))
        _gfail_names="${_gfail_names:+$_gfail_names,}${_gn}"
      fi
    fi
  done
  echo "$_gt $_gf $_gs $_gfail_names"
}

_is_stale_fail() {
  local _file="$1" _tip_ts="$2"
  [[ "$_tip_ts" -le 0 ]] && return 1
  local _rts; _rts=$(stat -c '%Y' "$_file" 2>/dev/null || echo 0)
  [[ "$_rts" -gt 0 && "$_tip_ts" -gt "$_rts" ]]
}

EXPECTED_GATES=$(find "$PLUGIN_DIR/gates" -name '*.md' 2>/dev/null | wc -l)
[[ "$EXPECTED_GATES" -lt 1 ]] && EXPECTED_GATES=33

# Load config from YAML
_config_val() { yq ".repos.\"$1\".${2} // \"\"" "$CONFIG_FILE"; }

_resolve_known_good() {
  local name="$1" repo_dir="$2"
  local _rk=$(echo "$name" | tr '/' '_')
  local _ver=$(echo "$VERSION" | tr '.' '_')
  local _cache="$PLUGIN_DIR/test/.matrix-state/known_good_resolved_${_rk}_${_ver}"
  if [[ -f "$_cache" ]]; then
    local _cached=$(cat "$_cache")
    git -C "$repo_dir" rev-parse --verify "$_cached" &>/dev/null && echo "$_cached" && return 0
  fi
  local kg=$(yq ".repos.\"$name\".known_good // \"\"" "$CONFIG_FILE")
  [[ -z "$kg" || "$kg" == "null" ]] && return 1
  local resolved=""
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
  if [[ -n "$_mc" && "$_mc" != "null" ]]; then
    MAX_CONCURRENT="${_MAX_CONCURRENT_FROM_ENV:-$_mc}"
  fi
  DEFAULT_REPOS=()
  while IFS= read -r repo_short; do
    [[ -n "$repo_short" ]] && DEFAULT_REPOS+=("$REPOS_DIR/$repo_short")
  done < <(yq '.repos | keys | .[]' "$CONFIG_FILE")
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
import json, sys, time, os
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
            st = raw_status  # idle means between-turns (bg tasks may be running); only 'done' is terminal
        else:
            st = raw_state or raw_status or '?'
        pid = s.get('pid') or '0'
        full_sid = s.get('sessionId', '?')
        sid = s.get('id') or full_sid[:8]
        started = s.get('startedAt', 0)
        elapsed = max(0, int((now - started) / 60000)) if started else 0
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
    [[ -z "$cwd" ]] && continue
    [[ "$cwd" == *"/${short}/"* || "$cwd" == *"/${short}" ]] || continue
    [[ "$state" != "working" ]] && continue
    [[ -z "$pid" || "$pid" == "0" ]] && continue
    kill -0 "$pid" 2>/dev/null || continue
    if [[ "$cwd" == *"/.claude/worktrees/"* && ! -d "$cwd" ]]; then
      continue
    fi
    match="$cwd	$state	$elapsed	$pid	$_rest"
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
    wt_branch=$(echo "$wt_line" | grep -oE '\[.+\]' | tr -d '[]' | sed 's/ locked//')
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
  [[ -n "$(git status --porcelain 2>/dev/null)" ]] && { error "Uncommitted changes in $repo"; return 1; }
  local default_br
  default_br=$(default_branch)
  git checkout "$default_br" &>/dev/null || { error "Cannot checkout $default_br"; return 1; }
  git pull --ff-only &>/dev/null || true
  info "$(repo_short "$repo") -> $default_br @ $(git rev-parse --short HEAD)"
}

remove_worktrees() {
  local repo="$1"
  cd "$repo" 2>/dev/null || return 1
  local wt_lines default_br
  wt_lines=$(git worktree list 2>/dev/null | grep '\.claude/worktrees' || true)
  [[ -z "$wt_lines" ]] && return 0
  default_br=$(default_branch)
  while IFS= read -r line; do
    local wt_path wt_branch commit_count=0
    wt_path=$(echo "$line" | awk '{print $1}')
    wt_branch=$(echo "$line" | grep -oE '\[.+\]' | tr -d '[]' | sed 's/ locked//')
    [[ -n "$wt_branch" ]] && commit_count=$(git rev-list --count "$default_br".."$wt_branch" 2>/dev/null || echo 0)
    git worktree unlock "$wt_path" 2>/dev/null || true
    git worktree remove "$wt_path" --force 2>/dev/null \
      || { rm -rf "$wt_path" 2>/dev/null; git worktree prune 2>/dev/null; } \
      || { warn "Could not remove worktree: $wt_path"; continue; }
    if [[ "$commit_count" -gt 0 ]]; then
      info "Removed worktree (branch $wt_branch preserved, $commit_count commits)"
    else
      info "Removed worktree (branch $wt_branch kept)"
    fi
  done <<< "$wt_lines"
  # Sweep orphaned worktree directories that git lost track of
  # (e.g., after ENOSPC corrupts git's worktree metadata).
  # Safe: only called from cmd_run (before launch) and cmd_clean.
  if [[ -d "$repo/.claude/worktrees" ]]; then
    for orphan in "$repo/.claude/worktrees"/*/; do
      [[ -d "$orphan" ]] || continue
      if rm -rf "$orphan"; then
        info "Removed orphaned worktree dir: $(basename "$orphan")"
      else
        warn "Could not remove orphaned worktree dir: $(basename "$orphan")"
      fi
    done
  fi
}

cmd_run() {
  command -v claude &>/dev/null || die "claude CLI not found"
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
        if [[ -z "$_run_sid" ]] || ! _session_alive "$_run_sid"; then
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
    repo=$(resolve_repo "$repo") || { warn "Not found: $repo_input"; continue; }
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
      [[ -z "$_old_branch" ]] && continue
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
      git checkout -f "$_db" &>/dev/null || true
      git clean -fd &>/dev/null || true
      git fetch origin --no-tags &>/dev/null || true
      git branch -D "_test-from-${from_commit:0:8}" &>/dev/null || true
      # If repo is checked out on a stale _test-from-* branch, switch away first
      local _cur_branch=$(git branch --show-current 2>/dev/null)
      [[ "$_cur_branch" == _test-from-* ]] && git checkout -f "$_db" &>/dev/null || true
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
    echo "$session_id" > "$PLUGIN_DIR/test/.matrix-state/.session_id_$_rk" 2>/dev/null
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
    local raw=$(cat "$running_file")
    local sid=$(echo "$raw" | cut -f3)
    [[ -z "$sid" ]] && continue
    local _fv=$(echo "$raw" | cut -f4)
    repo_key=$(repo_key_from_running "$_fv" "$repo_key")
    local short=$(echo "$repo_key" | tr '_' '/')
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
    build_session_cache
    while IFS=$'\t' read -r _cwd _state _elapsed _pid _sid _rest; do
      [[ -z "$_cwd" ]] && continue
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
  local repos=("$@")
  [[ ${#repos[@]} -eq 0 ]] && repos=("${DEFAULT_REPOS[@]}")
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
    remove_worktrees "$repo"
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
      [[ -z "$cid" ]] && continue
      podman rm "$cid" &>/dev/null && pruned=$((pruned + 1))
    done < <(podman ps -a --filter status=exited --filter name=k8s-rebase --format '{{.ID}}' 2>/dev/null)
    [[ "$pruned" -gt 0 ]] && info "Pruned $pruned containers"
  fi
  if [[ -d "$RESULTS_DIR" ]]; then
    local old_mutated=$(find "$RESULTS_DIR" -maxdepth 1 -name 'mutated-*' -type d 2>/dev/null | wc -l)
    [[ "$old_mutated" -gt 0 ]] && { rm -rf "$RESULTS_DIR"/mutated-* 2>/dev/null; info "Cleaned $old_mutated mutated dirs"; }
  fi
  for _ck in "${cleaned_keys[@]}"; do
    rm -f "$state_dir/done/"*"_${_ck}" 2>/dev/null
    rm -rf "$state_dir/court/"*"_${_ck}" 2>/dev/null
    rm -f "$state_dir/running/"*"_${_ck}" 2>/dev/null
  done
  [[ ${#cleaned_keys[@]} -gt 0 ]] && info "Cleared done/court/running state for ${#cleaned_keys[@]} repos"
  rm -f "$state_dir"/.session_id_* "$state_dir"/from_commit_* "$state_dir"/known_good_* "$state_dir"/expected_fail_* 2>/dev/null
  return 0
}

# ── Mutation ───────────────────────────────────────────────────────────

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

mutate_plugin() {
  local label="mutated-$(date +%s)"
  local dest="$RESULTS_DIR/$label"
  mkdir -p "$RESULTS_DIR" 2>/dev/null || true
  command -v rsync &>/dev/null || die "rsync required"
  rsync -a --exclude test/.repos --exclude test/.matrix-state "$PLUGIN_DIR/" "$dest/" || die "Cannot copy plugin to $dest"

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
  local version="$VERSION" specs=() repo="" from_commit=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version) shift; version="${1:-}"; [[ -z "$version" ]] && die "--version needs value" ;;
      --from-commit) shift; from_commit="${1:-}"; [[ -z "$from_commit" ]] && die "--from-commit needs value" ;;
      none|pattern:*|fn:*|all-patterns|all-fns|all) specs+=("$1") ;;
      *) repo="$1" ;;
    esac; shift
  done
  [[ ${#specs[@]} -eq 0 ]] && die "No spec (use: all, fn:<tag>, pattern:<key>)"
  [[ -z "$repo" ]] && die "No repo path"
  local repo_input="$repo"
  _ensure_repo "$(repo_short "$repo_input")"
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input"

  # Read from_commit from config if not passed via CLI
  if [[ -z "$from_commit" ]]; then
    from_commit=$(_config_val "$(repo_short "$repo")" "from_commit")
  fi

  info "── Test: ${specs[*]} on $(repo_short "$repo") ──"
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

  # Clean stale worktree branches
  (cd "$repo" && git worktree prune 2>/dev/null || true)

  # Track in running state
  local _state_dir="$PLUGIN_DIR/test/.matrix-state"
  local _repo_key
  _repo_key=$(repo_key "$repo")
  local _running_key=$(running_key "$version" "$repo")
  mkdir -p "$_state_dir/running" "$_state_dir/done"
  # Remove old done file so auto_record can re-record this test
  local _done_key=$(_done_key "$version" "${specs[*]}" "$_repo_key")
  [[ -f "$_state_dir/done/$_done_key" ]] && rm -f "$_state_dir/done/$_done_key"
  rm -f "$_state_dir/court/${version}_${_repo_key}"
  # Launch via session run (subshell to scope PLUGIN_DIR to the mutated copy)
  mkdir -p "$mutated/test/.matrix-state"
  if ! (PLUGIN_DIR="$mutated" cmd_run "$version" "$repo" ${from_commit:+--from-commit "$from_commit"}); then
    # Recover repo from temp branch and settings override if from_commit was used
    if [[ -n "$from_commit" && -d "$repo" ]]; then
      local _db; _db=$(git -C "$repo" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
      : "${_db:=main}"
      git -C "$repo" checkout "$_db" 2>/dev/null || true
      git -C "$repo" branch -D "_test-from-${from_commit:0:8}" 2>/dev/null || true
      _set_worktree_base "$repo" remove
    fi
    error "Launch failed for $(repo_short "$repo")"; return 1
  fi
  # Append session ID to running file for reliable stop
  local _sid=$(cat "$mutated/test/.matrix-state/.session_id_$_running_key" 2>/dev/null)
  [[ -n "$_sid" ]] && printf '%s\t%s\t%s\t%s\n' "${specs[*]}" "$(date +%s)" "$_sid" "$version" > "$_state_dir/running/$_running_key"
  rm -f "$mutated/test/.matrix-state/.session_id_$_running_key" 2>/dev/null
  if [[ -z "${_SKIP_CONCURRENCY_CHECK:-}" ]]; then
    info "$(repo_short "$repo") running — 'make watch' to monitor, 'make results' when done"
  fi
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
  # Count already-running repos toward the limit
  for repo in "${sorted_repos[@]}"; do
    [[ -d "$repo" ]] || continue
    local _rk=$(running_key "$version" "$repo")
    [[ -f "$state_dir/running/$_rk" ]] && active=$((active + 1))
  done
  for repo in "${sorted_repos[@]}"; do
    _ensure_repo "$(repo_short "$repo")"
    [[ -d "$repo" ]] || continue
    local _rk=$(running_key "$version" "$repo")
    if [[ -f "$state_dir/running/$_rk" ]]; then
      local _run_sid=$(cut -f3 "$state_dir/running/$_rk" 2>/dev/null)
      if [[ -z "$_run_sid" ]]; then
        rm -f "$state_dir/running/$_rk"
        active=$((active - 1))
      elif _session_alive "$_run_sid"; then
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
  [[ -n "$wt_path" && ! -d "$wt_path" ]] && { git -C "$repo" worktree prune 2>/dev/null; wt_path=""; }
  if [[ -z "$result_branch" ]]; then
    local _bp='bump'
    [[ -n "$_rec_version" ]] && _bp="bump${_rec_version%.*}"
    result_branch=$(LC_ALL=C git -C "$repo" branch --no-color | grep "$_bp" | sed 's/^[* +]*//' | sort -V | tail -1)
  fi
  # Fallback: Claude Code worktree branches (worktree-k8s-rebase-<version>*)
  # k8s-rebase.sh creates bump branches inside worktrees, but retries can
  # delete the bump branch while the worktree branch retains the commits.
  # Pick the branch with the most commits ahead of the default branch.
  if [[ -z "$result_branch" && -n "$_rec_version" ]]; then
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
    : "${branch_tip_epoch:=0}"
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
  local kg_hunks="" kg_vendor="" kg_branch=""
  kg_branch=$(_resolve_known_good "$short" "$repo")
  if [[ -n "$kg_branch" ]]; then
    local kg_diff_all=$(git -C "$repo" diff "$result_branch" "$kg_branch" -- . ':!.rebase-tmp' 2>/dev/null | grep -c '^@@' || true)
    local kg_diff_nv=$(git -C "$repo" diff "$result_branch" "$kg_branch" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
    kg_hunks="$kg_diff_nv"
    [[ "$kg_diff_all" -gt "$kg_diff_nv" ]] && kg_vendor="$((kg_diff_all - kg_diff_nv))"
  fi

  # Build human-readable detail
  local detail=""
  local _gate_suffix=""
  [[ "$gskip" -gt 0 ]] && _gate_suffix=", ${gskip} skipped"
  if [[ "$gtotal" -eq 0 ]]; then
    detail="no gates ran (bug)"
  elif [[ "$gtotal" -lt "$EXPECTED_GATES" ]]; then
    local _gmiss_names=""
    for _gmd in "$PLUGIN_DIR/gates"/step*/*.md; do
      [[ -f "$_gmd" ]] || continue
      local _gdir_name=$(basename "$(dirname "$_gmd")")
      local _gstep="${_gdir_name%%-*}"
      local _gbase=$(basename "$_gmd" .md)
      local _gexpected="${_gstep}-${_gbase}"
      local _found_gate=false
      for _gd in "${_GATE_DIRS[@]}"; do
        [[ -f "$_gd/${_gexpected}.report" ]] && { _found_gate=true; break; }
      done
      if ! $_found_gate; then
        _gmiss_names="${_gmiss_names:+$_gmiss_names, }${_gexpected}"
      fi
    done
    detail="missing $((EXPECTED_GATES - gtotal)) of $EXPECTED_GATES gates [${_gmiss_names}]"
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
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$_rec_version" "$spec" "$short" "$verdict" "$detail" >> "$state_dir/results.tsv"
  touch "$state_dir/done/$done_key"
  rm -f "$state_dir/running/${_rec_version}_${repo_key}"
  rm -f "$state_dir/court/${_rec_version}_${repo_key}"
  printf '%-20s %-42s %-8s %s' "$spec" "$short" "$verdict" "$detail"
}

auto_record() {
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  local running_dir="$state_dir/running"
  if [[ ! -d "$running_dir" ]] || [[ -z "$(ls -A "$running_dir" 2>/dev/null)" ]]; then return 0; fi

  local recorded=0

  for running_file in "$running_dir"/*; do
    [[ -f "$running_file" ]] || continue
    local repo_key=$(basename "$running_file")
    local _raw=$(cat "$running_file")
    local spec=$(echo "$_raw" | cut -f1)
    local launch_epoch=$(echo "$_raw" | cut -f2)
    [[ "$launch_epoch" =~ ^[0-9]+$ ]] || launch_epoch=0
    local _run_sid=$(echo "$_raw" | cut -f3)
    local _run_version=$(echo "$_raw" | cut -f4)
    : "${_run_version:=$VERSION}"
    repo_key=$(repo_key_from_running "$_run_version" "$repo_key")
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
      local _gc=0
      if [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
        local -A _gc_seen=()
        for _gd in "${_GATE_DIRS[@]}"; do
          for _gf in "$_gd"/*.report; do
            [[ -f "$_gf" ]] || continue
            _gc_seen[$(basename "$_gf" .report)]=1
          done
        done
        _gc=${#_gc_seen[@]}
      fi
      if [[ "$_gc" -ge "$EXPECTED_GATES" ]]; then
        info "Gate-complete: $spec on $short ($_gc/$EXPECTED_GATES gates)"
      else
        continue
      fi
    else
      _session_dead=true
    fi

    local result
    if result=$(_do_record_one "$repo" "$repo_key" "$spec" "$state_dir" "$launch_epoch" "$_run_version"); then
      [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true
      recorded=$((recorded + 1))
      info "Recorded: $result"
    elif $_session_dead; then
      local _fail_detail="${result:-session ended without result}"
      local ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$_run_version" "$spec" "$short" "FAIL" "$_fail_detail" >> "$state_dir/results.tsv"
      local _done_key=$(_done_key "$_run_version" "$spec" "$repo_key")
      mkdir -p "$state_dir/done"
      touch "$state_dir/done/$_done_key"
      [[ -n "$_run_sid" ]] && claude stop "$_run_sid" 2>/dev/null || true
      rm -f "$running_file"
      recorded=$((recorded + 1))
      warn "Recorded FAIL for $short ($_fail_detail)"
    fi
  done
  [[ "$recorded" -gt 0 ]] && info "$recorded result(s) recorded"
}

# ── Adversarial Court ──────────────────────────────────────────────────

cmd_court() {
  [[ $# -lt 3 ]] && die "Usage: make court repo=<repo>"
  local result_branch="$1" known_good="$2" repo="$3"

  cd "$repo" || { error "Cannot cd to $repo"; return 1; }
  git rev-parse --verify "$result_branch" &>/dev/null || { error "Branch not found: $result_branch"; return 1; }
  git rev-parse --verify "$known_good" &>/dev/null || { error "Branch not found: $known_good"; return 1; }

  local diff_nv=$(git diff "$known_good" "$result_branch" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null)
  [[ -z "$diff_nv" ]] && { info "PASS: identical (non-vendor)"; return 0; }

  local diff_bytes=${#diff_nv}
  if [[ "$diff_bytes" -gt 600000 ]]; then
    error "INCONCLUSIVE: diff too large (${diff_bytes} bytes — max 600000)"
    return 2
  fi
  local hunks=$(echo "$diff_nv" | grep -c '^@@' || true)
  local diff_stat=$(git diff --stat "$known_good" "$result_branch" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null)
  info "Diff: $hunks non-vendor hunks (${diff_bytes} bytes)"

  local direction="DIFF DIRECTION: 'git diff known_good result'.
'-' lines are in KNOWN-GOOD but not result (things the result may be MISSING).
'+' lines are in RESULT but not known-good (things the result ADDED or CHANGED).
Example: if the result bumped k8s to 1.35 and the known-good has 1.34,
you will see '-1.34' '+1.35' — the '+' shows what the result produced.
'deleted file' = exists in known-good but not result (result REMOVED it).
'new file' = exists in result but not known-good (result ADDED it)."
  local preexisting="
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
outside the DIFF, state it as a concern to verify, not as established fact."
  local logs=$(git log --oneline "$(git merge-base "$result_branch" "$known_good" 2>/dev/null || echo "$known_good")".."$result_branch" 2>/dev/null | head -15)
  local context="$direction
$preexisting

DIFF (non-vendor):
$diff_nv

COMMITS: $logs
FILES: $diff_stat"

  local _court_dir="$PLUGIN_DIR/test/.matrix-state/court"
  mkdir -p "$_court_dir" 2>/dev/null
  local cdir="$_court_dir/$(date +%s)_$(repo_key "$repo")"
  mkdir -p "$cdir"

  info "Phase A: Prosecution + Defense..."
  cat <<EOF_PROS | timeout 600 claude -p --permission-mode "$PERMISSION_MODE" --output-format text > "$cdir/pros.txt" 2>"$cdir/pros.err" &
$context

You are the PROSECUTION. Argue these are REGRESSIONS. Cite files and lines.
EOF_PROS
  local p1=$!
  cat <<EOF_DEF | timeout 600 claude -p --permission-mode "$PERMISSION_MODE" --output-format text > "$cdir/def.txt" 2>"$cdir/def.err" &
$context

You are the DEFENSE. Argue these are EQUIVALENT or IMPROVEMENTS. Cite files and lines.
EOF_DEF
  local p2=$!
  wait "$p1" "$p2" 2>/dev/null || true
  local pros=$(cat "$cdir/pros.txt") def=$(cat "$cdir/def.txt")
  if [[ ${#pros} -lt 200 || ${#def} -lt 200 ]]; then
    error "Prosecution/defense too short (${#pros}/${#def} bytes — $(tail -1 "$cdir/pros.err" 2>/dev/null) / $(tail -1 "$cdir/def.err" 2>/dev/null))"
    return 2
  fi

  info "Phase B: Judge..."
  local judge
  judge=$(cat <<EOF_JUDGE | timeout 600 claude -p --permission-mode "$PERMISSION_MODE" --output-format text 2>"$cdir/judge.err"
$direction
$preexisting

PROSECUTION:
$pros

DEFENSE:
$def

DIFF:
$diff_nv

Fact-check only. Strike unsupported claims. No verdict.
EOF_JUDGE
  ) || true
  echo "$judge" > "$cdir/judge.txt"

  info "Phase C: Jury (parallel)..."
  for j in 1 2 3; do
    cat <<EOF_JURY | timeout 600 claude -p --permission-mode "$PERMISSION_MODE" --output-format text \
      --allowedTools "Bash(git show *),Bash(git diff *),Bash(git log *),Read" \
      > "$cdir/juror-$j.txt" 2>"$cdir/juror-$j.err" &
REPO: $repo
BASE_REF: $(git merge-base "$known_good" "$result_branch" 2>/dev/null || echo "$known_good")
RESULT_REF: $result_branch

$direction
$preexisting

TOOLS: You may run git show <ref>:<path> and git diff <ref1> <ref2> -- <path> to verify claims.
Do NOT run git checkout, git reset, git push, git commit, or any write operation.
Where prosecution and defense disagree, use git show to check the actual file at BASE_REF.

DIFF:
$diff_nv

PROSECUTION:
$pros

DEFENSE:
$def

JUDGE:
$judge

REQUIREMENT: Before rendering your verdict, you MUST use at least one
tool (git show, git diff, or Read) to independently verify one claim
from the prosecution or defense. Include a VERIFIED: line citing the
file:line and what you found. Verdicts without a VERIFIED line are
invalid.

Output format:
VERIFIED: <file>@<ref> — <finding>  (one or more lines — REQUIRED)
VERDICT: PASS or FAIL. One sentence.
EOF_JURY
  done
  wait 2>/dev/null || true

  local empty_jurors=0
  for j in 1 2 3; do
    if [[ ! -s "$cdir/juror-$j.txt" ]] || grep -qx 'Execution error' "$cdir/juror-$j.txt" 2>/dev/null; then
      warn "Juror $j produced no output ($(cat "$cdir/juror-$j.err" 2>/dev/null | tail -1))"
      empty_jurors=$((empty_jurors + 1))
    fi
  done

  local pass=0 fail=0
  for j in 1 2 3; do
    local jv=$(grep -ioE 'VERDICT:[* ]*(PASS|FAIL)' "$cdir/juror-$j.txt" 2>/dev/null | grep -ioE 'PASS|FAIL' | tail -1)
    jv="${jv^^}"
    case "$jv" in "PASS") pass=$((pass+1)); info "  Juror $j: PASS";; "FAIL") fail=$((fail+1)); info "  Juror $j: FAIL";; *) info "  Juror $j: ABSTAIN";; esac
  done

  info "Jury: $pass PASS, $fail FAIL"
  if [[ "$empty_jurors" -gt 1 ]]; then
    error "INCONCLUSIVE (majority juror failure: $empty_jurors empty)"; return 2
  fi
  if [[ "$pass" -eq "$fail" && "$empty_jurors" -gt 0 ]]; then
    error "INCONCLUSIVE (tied $pass-$fail with $empty_jurors empty juror(s))"; return 2
  fi
  local total=$((pass + fail))
  if [[ "$total" -lt 2 ]]; then
    if [[ "$pass" -gt 0 && "$fail" -eq 0 ]]; then
      info "PASS (no regression found — $pass pass, $fail fail, $((3-total)) abstain)"
      return 0
    else
      error "INCONCLUSIVE (no quorum — $pass pass, $fail fail, $((3-total)) abstain)"; return 2
    fi
  fi
  [[ "$pass" -gt "$fail" ]] && { info "VERDICT: PASS ($pass-$fail)"; return 0; }
  if [[ "$pass" -eq "$fail" ]]; then
    error "INCONCLUSIVE (tied $pass-$fail)"; return 2
  fi
  error "VERDICT: FAIL ($fail-$pass)"; return 1
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
    local max_court_concurrent=${MAX_COURT_CONCURRENT:-2}
    for repo in "${DEFAULT_REPOS[@]}"; do
      local short=$(repo_short "$repo")
      local _rk=$(repo_key "$repo")
      local _court_file="$PLUGIN_DIR/test/.matrix-state/court/${VERSION}_$_rk"
      [[ -f "$_court_file" ]] && [[ "$(cat "$_court_file" 2>/dev/null)" != "INCONCLUSIVE" ]] && continue
      local latest_line=$(awk -F'\t' -v r="$short" -v v="$VERSION" '$4==r && $2==v && ($3~/^all/ || $3=="none")' "$tsv" | tail -1)
      [[ -z "$latest_line" ]] && continue
      local verdict=$(echo "$latest_line" | cut -f5)
      [[ "$verdict" != "PASS" ]] && continue
      [[ -f "$PLUGIN_DIR/test/.matrix-state/running/${VERSION}_$_rk" ]] && { skipped=$((skipped + 1)); continue; }

      repo=$(resolve_repo "$short" 2>/dev/null) || { warn "$short ($VERSION): cannot resolve"; skipped=$((skipped + 1)); continue; }
      cd "$repo" || { warn "$short ($VERSION): cannot cd"; skipped=$((skipped + 1)); continue; }
      local kg=$(_resolve_known_good "$short" "$repo")
      [[ -z "$kg" ]] && { warn "$short ($VERSION): no known-good configured"; skipped=$((skipped + 1)); continue; }
      local branch=$(find_newest_branch "$repo" "$VERSION")
      [[ -z "$branch" ]] && { warn "$short ($VERSION): no result branch found"; skipped=$((skipped + 1)); continue; }

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
        local _verdict=""
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
      ) &
      _court_pids+=($!)
      _court_files+=("$_court_file")
      _court_shorts+=("$short")
    done

    if [[ ${#_court_pids[@]} -gt 0 ]]; then
      wait "${_court_pids[@]}" 2>/dev/null || true
      for _ci in "${!_court_files[@]}"; do
        local _cf="${_court_files[$_ci]}" _cs="${_court_shorts[$_ci]}"
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
  else
    echo "Court complete: $passed passed, $failed failed, $errors errors, $skipped skipped (of $((run + skipped)) pending)"
  fi
}

# ── Watch ──────────────────────────────────────────────────────────────

cmd_watch() {
  local state_dir="$PLUGIN_DIR/test/.matrix-state"
  _SESSION_CACHE_AGE=0
  build_session_cache
  printf "%-42s %-10s %-8s %-32s %s\n" "REPO" "SESSION" "GATES" "LATEST COMMIT" "VS KNOWN-GOOD"
  printf "%-42s %-10s %-8s %-32s %s\n" "----" "-------" "-----" "-------------" "-------------"
  local active=0
  for running_file in "$state_dir/running"/*; do
    [[ -f "$running_file" ]] || continue
    active=$((active + 1))
    local _rk=$(basename "$running_file")
    local _raw=$(cat "$running_file")
    local _file_version=$(echo "$_raw" | cut -f4)
    local _bare_rk=$(repo_key_from_running "$_file_version" "$_rk")
    local short=$(echo "$_bare_rk" | tr '_' '/')
    local repo="$REPOS_DIR/$short"
    [[ -d "$repo" ]] || continue
    local _sid=$(echo "$_raw" | cut -f3)
    local session_state="gone"
    if [[ -n "$_sid" ]]; then
      local _found_state
      _found_state=$(echo "$_SESSION_CACHE" | while IFS=$'\t' read -r _cwd _st _el _pid _s _rest; do
        [[ "$_s" == "$_sid"* ]] && echo "$_st" && break
      done)
      [[ -n "$_found_state" ]] && session_state="$_found_state"
    fi
    _worktree_info "$repo" || true
    local wt="$_WT_PATH" _branch="$_WT_BRANCH"
    local gc=0 gf=0 gs=0 commit_msg="-" diff_info="-"
    if [[ -n "$wt" ]]; then
      local _db=$(git -C "$repo" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
      : "${_db:=main}"
      if [[ -n "$_branch" ]]; then
        local n_commits=$(git -C "$repo" rev-list --count "$_db".."$_branch" 2>/dev/null || echo 0)
        [[ "$n_commits" -gt 0 ]] && commit_msg=$(git -C "$wt" log --format="%s" -1 "$_branch" 2>/dev/null | head -c 30)
      fi
      _collect_gate_dirs "$repo"
      if [[ ${#_GATE_DIRS[@]} -gt 0 ]]; then
        read -r gc gf gs <<< "$(_tally_gates "${_GATE_DIRS[@]}")"
      fi
    fi
    local kg=$(_resolve_known_good "$short" "$repo")
    if [[ -n "$kg" && -n "$wt" && -n "$_branch" ]]; then
      local nv=$(git -C "$repo" diff "$_branch" "$kg" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
      local nv_all=$(git -C "$repo" diff "$_branch" "$kg" -- . ':!.rebase-tmp' 2>/dev/null | grep -c '^@@' || true)
      diff_info="${nv} code"
      [[ "$nv_all" -gt "$nv" ]] && diff_info="$diff_info (+$((nv_all - nv)) vendor)"
    fi
    # Show "needs-court" when session is done, gates complete, no done file yet
    if [[ "$session_state" == "done" || "$session_state" == "gone" ]]; then
      local _done_key=$(_done_key "$(echo "$_raw" | cut -f4)" "${_raw%%	*}" "$_bare_rk")
      if [[ "$gc" -ge "$EXPECTED_GATES" && ! -f "$state_dir/done/$_done_key" ]]; then
        session_state="needs-court"
      fi
    fi
    local gate_str="${gc}/${EXPECTED_GATES}"
    local _gsuffix=""
    [[ "$gf" -gt 0 ]] && _gsuffix="${gf}F"
    [[ "$gs" -gt 0 ]] && _gsuffix="${_gsuffix:+${_gsuffix},}${gs}S"
    [[ -n "$_gsuffix" ]] && gate_str="${gate_str} (${_gsuffix})"
    printf "%-42s %-10s %-8s %-32s %s\n" "$short" "$session_state" "$gate_str" "$commit_msg" "$diff_info"
  done
  [[ "$active" -le 0 ]] && echo "(no active tests)"
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
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input"
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
    local total=0 gfail=0 gskip=0
    read -r total gfail gskip <<< "$(_tally_gates "${_GATE_DIRS[@]}")"
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
      awk '/^DETAILS:/{d=1; print; next} d{print "  "$0; next} {print}' "$f"
    done
  else
    echo "Gates: none (no reports found)"
  fi

  local kg=$(_resolve_known_good "$short" "$repo")
  if [[ -n "$kg" ]]; then
    local branch=$(find_newest_branch "$repo" "$VERSION")
    if [[ -n "$branch" ]]; then
      local nv=$(git diff "$branch" "$kg" -- . ':!.rebase-tmp' ':(exclude,glob)**/vendor/**' 2>/dev/null | grep -c '^@@' || true)
      echo ""
      if [[ "$nv" -eq 0 ]]; then
        echo "Diff vs known-good ${kg:0:12}: identical (non-vendor)"
      else
        echo "Diff vs known-good ${kg:0:12}: $nv code hunks differ"
      fi
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
  awk -F'\t' -v r="$short" '$4==r' "$PLUGIN_DIR/test/.matrix-state/results.tsv" 2>/dev/null | tail -5 | while IFS=$'\t' read -r ts ver spec r verdict detail; do
    printf "  %-22s %-8s %-8s %s\n" "$ts" "$ver" "$verdict" "$detail"
  done
}

_results_for_version() {
  local tsv="$PLUGIN_DIR/test/.matrix-state/results.tsv"
  if [[ ! -f "$tsv" ]]; then echo "No results yet. Run: make test"; return 0; fi

  printf "%-45s %-8s %-8s %-20s %s\n" "REPO" "VERDICT" "COURT" "LAST RUN" "DETAIL"
  printf "%-45s %-8s %-8s %-20s %s\n" "----" "-------" "-----" "--------" "------"
  local all_pass=true
  for repo in "${DEFAULT_REPOS[@]}"; do
    local short=$(repo_short "$repo")
    local _rk=$(repo_key "$repo")
    local latest_line=$(awk -F'\t' -v r="$short" -v v="$VERSION" '$4==r && $2==v && ($3~/^all/ || $3=="none")' "$tsv" | tail -1)
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
      fi
      printf "%-45s %-8s %-8s %-20s %s\n" "$short" "$verdict" "$court_result" "$ts" "$detail"
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
      printf "%-45s %-8s %-8s %-20s %s\n" "$short" "-" "-" "" "$_reason"
    fi
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
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input"
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

        local latest_line=$(awk -F'\t' -v r="$short" -v v="$VERSION" \
          '$4==r && $2==v && ($3~/^all/ || $3=="none")' "$tsv" | tail -1)
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
      info ""

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
  repo=$(resolve_repo "$repo") || die "Not found: $repo_input"
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
  test <spec> <repo> [--version]    Run specific test case
  results [repo] [--court] [--all-versions]  Show results (all versions by default via make)
  set-known-good <repo> <ref> [--url <url>]  Set known-good reference
  set-from-commit <repo> <commit>   Set pre-merge commit for historical testing
  stop [repo...|--all]              Stop running test sessions
  clean [repos...]                  Cleanup worktrees and containers

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
