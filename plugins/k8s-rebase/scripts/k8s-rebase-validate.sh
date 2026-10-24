#!/bin/bash
# k8s-rebase-validate.sh — Collect and categorize validation errors
#
# Runs build, lint, and test for all modules. Captures output to logs.
# Parses logs to extract actionable errors. Writes categorized summary.
#
# Usage: k8s-rebase-validate.sh [--quick|--no-test|--full|--test-only [--module DIR] PKG...]
#   Flags are mutually exclusive — only the first argument is inspected.
#   --quick      Build + vet only (~1 min)
#   --no-test    Build + vet + lint, no tests (~5 min)
#   --full       All checks + privileged tests as root (~25 min)
#   --test-only  Run tests for specified packages only (for parallel agents)
#                --module DIR selects a repo-relative module (default: primary).
#                Packages requiring CAP_NET_ADMIN (root_pkgs in hack/test-go.sh)
#                are automatically excluded; container runs without --privileged
#   default      All checks except privileged tests (~15 min)
#
# --test-only handles auto-containerization, feature gate exports,
# and output capture — subagents should use it instead of raw go test.
# Example: k8s-rebase-validate.sh --test-only ./pkg/ovn/... ./pkg/util/...
#
# Exit codes: 0 = all validation passes (no errors)
#             1 = errors found (see $REBASE_TMP/summary.txt)

set -uo pipefail

VALIDATE_ARGS=("$@")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="default"
TEST_ONLY_MODULE=""
TEST_ONLY_PKGS=()
[[ "${1:-}" == "--quick" ]] && MODE="quick"
[[ "${1:-}" == "--no-test" ]] && MODE="no-test"
[[ "${1:-}" == "--full" ]] && MODE="full"
TEST_ONLY_EXTRA=()
if [[ "${1:-}" == "--test-only" ]]; then
  MODE="test-only"
  shift
  if [[ "${1:-}" == "--module" ]]; then
    [[ -n "${2:-}" && "$2" != -* ]] || { echo "ERROR: --module requires a repo-relative directory" >&2; exit 1; }
    TEST_ONLY_MODULE="$2"
    shift 2
  fi
  # Separate packages from go test flags. Once we see a -flag, treat
  # everything from that point as extra args (flags + their values).
  in_flags=false
  for arg in "$@"; do
    if [[ "$arg" == -* ]]; then
      in_flags=true
    fi
    if $in_flags; then
      TEST_ONLY_EXTRA+=("$arg")
    else
      TEST_ONLY_PKGS+=("$arg")
    fi
  done
  [[ "${#TEST_ONLY_PKGS[@]}" -eq 0 ]] && { echo "ERROR: --test-only requires package arguments" >&2; exit 1; }
fi
# Reject unknown flags — unrecognized $1 silently falls through to default mode
if [[ -n "${1:-}" ]] && [[ "${1:-}" == --* ]] && [[ "$MODE" == "default" ]]; then
  echo "ERROR: Unknown flag: $1" >&2
  echo "Usage: k8s-rebase-validate.sh [--quick|--no-test|--full|--test-only [--module DIR] PKG...]" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
REBASE_TMP="$REPO_ROOT/.rebase-tmp"
mkdir -p "$REBASE_TMP"
GIT_DIR_RESOLVED="$(git rev-parse --git-dir 2>/dev/null)"
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || echo "$GIT_DIR_RESOLVED")"
mkdir -p "$GIT_COMMON_DIR/info"
grep -qF '.rebase-tmp' "$GIT_COMMON_DIR/info/exclude" 2>/dev/null || echo '.rebase-tmp/' >> "$GIT_COMMON_DIR/info/exclude"

# Guard: refuse to run on master/main — validate must run on the rebase branch.
_current_branch=$(git branch --show-current 2>/dev/null || true)
if [[ "$_current_branch" == "master" || "$_current_branch" == "main" ]]; then
  echo "ERROR: Validate is running on '$_current_branch', not the rebase branch."
  if [[ -f "$REPO_ROOT/.rebase-tmp/branch-name" ]]; then
    _branch=$(<"$REPO_ROOT/.rebase-tmp/branch-name")
    echo "The rebase branch is: $_branch"
    echo "Run: git checkout $_branch"
  fi
  exit 1
fi

# Auto-containerize for an older Go toolchain or --full without root.
cd "$REPO_ROOT" || exit 1
PRIMARY_MOD=""
if [[ "$MODE" == "test-only" ]]; then
  if [[ -n "$TEST_ONLY_MODULE" ]]; then
    [[ "$TEST_ONLY_MODULE" != /* ]] || { echo "ERROR: --module must be repo-relative" >&2; exit 1; }
    _module_path=$(cd "$TEST_ONLY_MODULE" 2>/dev/null && pwd -P) || {
      echo "ERROR: Module directory does not exist: $TEST_ONLY_MODULE" >&2; exit 1;
    }
    _repo_path=$(pwd -P)
    if [[ "$_module_path" == "$_repo_path" ]]; then
      PRIMARY_MOD=.
    elif [[ "$_module_path" == "$_repo_path/"* ]]; then
      PRIMARY_MOD="${_module_path#"$_repo_path/"}"
    else
      echo "ERROR: --module must remain inside the repository" >&2; exit 1
    fi
  else
    for candidate in go-controller .; do
      [[ -f "$candidate/go.mod" ]] && PRIMARY_MOD="$candidate" && break
    done
    [[ -z "$PRIMARY_MOD" ]] && PRIMARY_MOD=$(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" -exec dirname {} \; | sort | head -1)
    PRIMARY_MOD="${PRIMARY_MOD#./}"
  fi
  [[ -n "$PRIMARY_MOD" && -f "$PRIMARY_MOD/go.mod" ]] || {
    echo "ERROR: No go.mod in selected test module: ${PRIMARY_MOD:-<none>}" >&2; exit 1;
  }
fi
REQUIRED_GO=""
GO_MOD_CANDIDATES=(go-controller/go.mod go.mod)
[[ "$MODE" == "test-only" ]] && GO_MOD_CANDIDATES=("$PRIMARY_MOD/go.mod")
for gm in "${GO_MOD_CANDIDATES[@]}"; do
  [[ -f "$gm" ]] && REQUIRED_GO=$(grep "^go " "$gm" | awk '{print $2}') && break
done
CURRENT_GO=$(go env GOVERSION 2>/dev/null | sed 's/go//' || echo "0.0")
NEEDS_PRIVILEGED_CONTAINER=false
[[ "$MODE" == "full" && "$(id -u)" != "0" ]] && NEEDS_PRIVILEGED_CONTAINER=true
if [[ -n "$REQUIRED_GO" || "$NEEDS_PRIVILEGED_CONTAINER" == true ]] && [[ "${K8S_REBASE_IN_CONTAINER:-}" != "1" ]]; then
  REQ_MINOR=$(cut -d. -f2 <<< "${REQUIRED_GO:-0.0}")
  CUR_MINOR=$(cut -d. -f2 <<< "$CURRENT_GO")
  if [[ "$NEEDS_PRIVILEGED_CONTAINER" == true ]] || [[ "$CUR_MINOR" -lt "$REQ_MINOR" ]] 2>/dev/null; then
    CONTAINER_RT=""
    command -v podman &>/dev/null && CONTAINER_RT=podman
    [[ -z "$CONTAINER_RT" ]] && command -v docker &>/dev/null && CONTAINER_RT=docker
    if [[ -n "$CONTAINER_RT" ]]; then
      GO_IMAGE="docker.io/library/golang:${REQUIRED_GO:-${CURRENT_GO%%-*}}"
      if [[ "$NEEDS_PRIVILEGED_CONTAINER" == true ]]; then
        echo ":: --full requires root — re-running validate inside $GO_IMAGE"
      else
        echo ":: Go $CURRENT_GO < $REQUIRED_GO — re-running validate inside $GO_IMAGE"
      fi
      SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
      USERNS_FLAG=""
      [[ "$CONTAINER_RT" == "podman" ]] && [[ "$MODE" != "full" ]] && USERNS_FLAG="--userns=keep-id"
      PRIV_FLAG=""
      [[ "$MODE" == "full" ]] && PRIV_FLAG="--privileged"
      GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)"
      WORKTREE_MOUNT=""
      if [[ -n "$GIT_COMMON_DIR" ]] && [[ "$GIT_COMMON_DIR" != ".git" ]] && [[ "$GIT_COMMON_DIR" != "$REPO_ROOT/.git" ]]; then
        WORKTREE_MOUNT="-v $(dirname "$GIT_COMMON_DIR"):$(dirname "$GIT_COMMON_DIR")"
      fi
      # Mount the host Go module cache to avoid ENOSPC in the container's
      # overlay filesystem and to reuse already-downloaded modules.
      HOST_GOMODCACHE="$(go env GOMODCACHE 2>/dev/null || echo "${GOPATH:-$HOME/go}/pkg/mod")"
      GOMODCACHE_MOUNT=""
      if [[ -n "$HOST_GOMODCACHE" ]]; then
        mkdir -p "$HOST_GOMODCACHE"
        GOMODCACHE_MOUNT="-v $HOST_GOMODCACHE:$HOST_GOMODCACHE"
      fi
      CACHE_ARGS=()
      HOST_GOCACHE="$(go env GOCACHE 2>/dev/null || true)"
      if [[ -n "$HOST_GOCACHE" && "$HOST_GOCACHE" != off ]]; then
        mkdir -p "$HOST_GOCACHE"
        CACHE_ARGS=(-v "$HOST_GOCACHE:$HOST_GOCACHE" -e "GOCACHE=$HOST_GOCACHE")
      fi
      RESOURCE_ARGS=()
      # Preserve caller limits across the host/container boundary. The Go
      # memory limit is soft; an explicit container bound is independent.
      for _limit in GOMEMLIMIT VALIDATION_TIMEOUT LINT_TIMEOUT; do
        [[ -n "${!_limit:-}" ]] && RESOURCE_ARGS+=(-e "${_limit}=${!_limit}")
      done
      [[ -n "${K8S_REBASE_CONTAINER_MEMORY:-}" ]] && \
        RESOURCE_ARGS+=(--memory "$K8S_REBASE_CONTAINER_MEMORY")
      [[ -n "${K8S_REBASE_CONTAINER_MEMORY_SWAP:-}" ]] && \
        RESOURCE_ARGS+=(--memory-swap "$K8S_REBASE_CONTAINER_MEMORY_SWAP")
      [[ -n "${K8S_REBASE_CONTAINER_CPUS:-}" ]] && \
        RESOURCE_ARGS+=(--cpus "$K8S_REBASE_CONTAINER_CPUS")
      TEMP_ARGS=()
      if [[ -n "${TMPDIR:-}" ]]; then
        HOST_TMPDIR=$(cd "$TMPDIR" && pwd -P) || {
          echo "ERROR: TMPDIR must be an existing directory: $TMPDIR" >&2
          exit 1
        }
        # Keep scratch on the caller's filesystem while leaving room for
        # Unix socket names within the platform's short sun_path limit.
        TEMP_ARGS=(-v "$HOST_TMPDIR:/task-tmp" -e TMPDIR=/task-tmp)
      fi
      exec $CONTAINER_RT run --rm \
        --security-opt label=disable \
        $PRIV_FLAG \
        $USERNS_FLAG \
        -v "$REPO_ROOT:$REPO_ROOT" \
        $WORKTREE_MOUNT \
        $GOMODCACHE_MOUNT \
        "${CACHE_ARGS[@]}" \
        "${RESOURCE_ARGS[@]}" \
        "${TEMP_ARGS[@]}" \
        -v "$(dirname "$SCRIPT_PATH"):$(dirname "$SCRIPT_PATH"):ro" \
        -w "$REPO_ROOT" \
        -e K8S_REBASE_IN_CONTAINER=1 \
        -e GOMODCACHE="$HOST_GOMODCACHE" \
        -e GOMAXPROCS="${GOMAXPROCS:-2}" \
        -e GOFLAGS="${GOFLAGS:--p=2}" \
        "$GO_IMAGE" \
        bash "$SCRIPT_PATH" "${VALIDATE_ARGS[@]}"
    fi
  fi
fi

export GOWORK=off
SUMMARY="$REBASE_TMP/summary.txt"
ERRORS_FOUND=0
VALIDATION_TIMEOUT="${VALIDATION_TIMEOUT:-25m}"
LINT_TIMEOUT="${LINT_TIMEOUT:-30m}"

# Container setup: install missing tools needed by CI checks
if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=safe.directory
  export GIT_CONFIG_VALUE_0="$REPO_ROOT"
  # Sudo shim: when running as root, test scripts that invoke sudo
  # work transparently without installing the sudo package
  if [[ "$(id -u)" == "0" ]] && ! command -v sudo &>/dev/null; then
    printf '#!/bin/sh\nwhile [ "${1#-}" != "$1" ]; do shift; done\nexec "$@"\n' > /usr/local/bin/sudo
    chmod +x /usr/local/bin/sudo
  fi
  # jq: needed by verify-third-party-licenses
  if ! command -v jq &>/dev/null; then
    curl -fsSL --connect-timeout 10 --max-time 45 https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 -o /tmp/jq 2>/dev/null \
      && echo "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5  /tmp/jq" | sha256sum -c --quiet 2>/dev/null \
      && chmod +x /tmp/jq && export PATH="/tmp:$PATH"
  fi
fi

run_validation() {
  local name="$1"
  local logfile="$REBASE_TMP/${name}.log"
  # Test-only callers already reserved this exact filename with mktemp.
  [[ "$MODE" == test-only ]] && logfile="$REBASE_TMP/$name"
  shift

  local step_timeout="$VALIDATION_TIMEOUT"
  [[ "$name" == *-lint ]] && step_timeout="$LINT_TIMEOUT"
  # Shell timeout 2m longer than Go test timeout so Go can dump
  # goroutine stacks before being killed
  if [[ "$name" == *-test || "$name" == test-only-* ]]; then
    local mins="${step_timeout%m}"
    step_timeout="$((mins + 2))m"
  fi

  echo ":: Running: $name (timeout: $step_timeout)"
  local attempt command_head
  attempt=$(mktemp -d "$REBASE_TMP/validation-XXXXXX") || return 1
  command_head=$(git rev-parse HEAD) || return 1
  git status --porcelain=v1 > "$attempt/worktree-before.txt" || return 1
  {
    printf 'HEAD: %s\n' "$command_head"
    printf 'CWD: %s\nCOMMAND: %s\n' "$PWD" "$*"
    printf 'TIMEOUT: %s\nLOG: %s\n' "$step_timeout" "$logfile"
  } > "$attempt/command.txt" || return 1
  local rc=0
  timeout --kill-after=60s "$step_timeout" bash -c "$*" > "$logfile" 2>&1 || rc=$?
  printf 'EXIT_STATUS: %s\n' "$rc" >> "$attempt/command.txt" || return 1
  command_head=$(git rev-parse HEAD) || return 1
  printf 'HEAD_AFTER: %s\n' "$command_head" >> "$attempt/command.txt" || return 1
  git status --porcelain=v1 > "$attempt/worktree-after.txt" || return 1
  cp -- "$logfile" "$attempt/output.log" || return 1
  echo "  Retained command evidence: $attempt"
  if [[ "$rc" -eq 0 ]]; then
    echo "  PASS"
    return 0
  elif [[ "$rc" -eq 124 ]] || [[ "$rc" -eq 137 ]]; then
    echo "  TIMEOUT after $step_timeout (see $logfile)"
    echo "" >> "$logfile"
    echo "TIMEOUT: command did not complete within $step_timeout" >> "$logfile"
    return 1
  else
    echo "  FAIL (see $logfile)"
    return 1
  fi
}

categorize_errors() {
  local logfile="$1"
  local category="$2"
  local step_failed="${3:-0}"

  local build_errors lint_errors vet_errors test_failures
  build_errors=$(grep -E ":[0-9]+:[0-9]+: .*(undefined|cannot use|cannot convert|too many arguments|too few arguments|not enough arguments|unknown field|has no field or method|imported and not used|declared (and|but) not used|multiple-value .* in single-value context)" "$logfile" 2>/dev/null || true)
  lint_errors=$(grep -E "\.go:[0-9]+:[0-9]+:.*\([a-zA-Z][a-zA-Z0-9_-]+\)$" "$logfile" 2>/dev/null | grep -v "^#" || true)
  vet_errors=$(grep -E ":[0-9]+:[0-9]+:.*(non-constant format string|format %|has arguments but no formatting directives|call needs [0-9]+ args but has|the cancel function returned by)" "$logfile" 2>/dev/null | grep -v "^#" || true)
  test_failures=$(grep -E "^--- FAIL:|^FAIL\t" "$logfile" 2>/dev/null || true)

  if [[ -n "$build_errors" ]]; then
    echo "## BUILD ERRORS ($category)" >> "$SUMMARY"
    echo "$build_errors" >> "$SUMMARY"
    if grep -qE "does not implement.*SharedIndexInformer|vendor.*does not implement" <<< "$build_errors" 2>/dev/null; then
      echo "" >> "$SUMMARY"
      echo "NOTE: Vendored dependency missing a new interface method." >> "$SUMMARY"
      echo "Select a compatible dependency version and use the repair helper in the affected module:" >> "$SUMMARY"
      echo 'bash "$PLUGIN_ROOT/scripts/k8s-rebase-depfix.sh" <module>@<version>' >> "$SUMMARY"
      echo "If a reviewed fork replace is needed, use the helper's --sync mode after adding it." >> "$SUMMARY"
      echo "The helper synchronizes module/vendor files; verify Kubernetes pins afterward." >> "$SUMMARY"
      echo "Do not patch vendor directly; verify-deps CI regenerates it." >> "$SUMMARY"
    fi
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi

  if [[ -n "$lint_errors" ]]; then
    echo "## LINT ERRORS ($category)" >> "$SUMMARY"
    echo "$lint_errors" >> "$SUMMARY"
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi

  if [[ -n "$vet_errors" ]]; then
    echo "## VET ERRORS ($category)" >> "$SUMMARY"
    echo "$vet_errors" >> "$SUMMARY"
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi

  if [[ -n "$test_failures" ]]; then
    local priv_errors
    priv_errors=$(grep -cE "permission denied|operation not permitted" "$logfile" 2>/dev/null || true)
    if [[ "$priv_errors" -gt 0 ]]; then
      echo "## TEST FAILURES ($category) — ${priv_errors} privilege errors detected" >> "$SUMMARY"
      echo "$test_failures" >> "$SUMMARY"
      echo "Some failures may need CAP_NET_ADMIN. Compare with default branch to confirm pre-existing." >> "$SUMMARY"
    else
      echo "## TEST FAILURES ($category)" >> "$SUMMARY"
      echo "$test_failures" >> "$SUMMARY"
    fi
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi

  local timeout_errors
  timeout_errors=$(grep -E "^TIMEOUT:" "$logfile" 2>/dev/null || true)
  if [[ -n "$timeout_errors" ]]; then
    echo "## TIMEOUT ($category)" >> "$SUMMARY"
    echo "$timeout_errors" >> "$SUMMARY"
    echo "Possible causes: feature gate causing test hang, resource exhaustion, resource leak" >> "$SUMMARY"
    echo "If tests hang, check GATE_DEPS in k8s-rebase-autofix.sh — a new gate may need adding" >> "$SUMMARY"
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi

  if [[ "$step_failed" -eq 1 ]] && [[ -z "$build_errors" ]] && [[ -z "$lint_errors" ]] && [[ -z "$vet_errors" ]] && [[ -z "$test_failures" ]] && [[ -z "$timeout_errors" ]]; then
    echo "## UNCLASSIFIED FAILURE ($category) — step failed; no known error pattern matched; last 10 log lines follow" >> "$SUMMARY"
    tail -10 "$logfile" >> "$SUMMARY"
    echo "" >> "$SUMMARY"
    ERRORS_FOUND=1
  fi
}

cd "$REPO_ROOT" || exit 1

# ── --test-only: run tests for specific packages and exit ───────────
run_test_only() {
  echo "━━━━ Testing specified packages ━━━━"
  echo ""
  echo "Module: $PRIMARY_MOD"
  echo "Packages: ${TEST_ONLY_PKGS[*]}"

  # Prefer module-local test configuration. Other modules may still need the
  # repository's feature gates, but must not inherit its root-package list.
  local root_test_go_sh=""
  [[ -f "$PRIMARY_MOD/hack/test-go.sh" ]] && root_test_go_sh="$PRIMARY_MOD/hack/test-go.sh"
  local TEST_GO_SH
  TEST_GO_SH="$root_test_go_sh"
  [[ -z "$TEST_GO_SH" ]] && TEST_GO_SH=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" 2>/dev/null | head -1)
  if [[ -n "$TEST_GO_SH" ]]; then
    while IFS='=' read -r _key _val; do
      [[ "$_key" =~ ^export\ KUBE_FEATURE_[A-Za-z0-9_]+$ ]] && export "${_key#export }=$_val"
    done < <(grep "^export KUBE_FEATURE_" "$TEST_GO_SH")
  fi

  local VENDOR_FLAGS=()
  [[ -d "$PRIMARY_MOD/vendor" ]] && VENDOR_FLAGS=(-mod=vendor)

  # Strip module dir prefix from package paths if present
  # (agent may pass ./go-controller/pkg/ovn/... instead of ./pkg/ovn/...)
  if [[ "$PRIMARY_MOD" != "." ]]; then
    local cleaned=()
    for pkg in "${TEST_ONLY_PKGS[@]}"; do
      pkg="${pkg#./"${PRIMARY_MOD}"/}"   # strip ./go-controller/
      pkg="${pkg#"${PRIMARY_MOD}"/}"     # strip go-controller/
      [[ "$pkg" != ./* ]] && pkg="./$pkg"
      cleaned+=("$pkg")
    done
    TEST_ONLY_PKGS=("${cleaned[@]}")
  fi

  # Reserve a log before package expansion so failed discovery and exclusions
  # also have independent evidence. Full validation owns summary.txt.
  local LOG_NAME
  LOG_NAME=$(mktemp "$REBASE_TMP/test-only-XXXXXX") || exit 1
  chmod +rw "$LOG_NAME" || exit 1
  LOG_NAME=${LOG_NAME##*/}

  # root_pkgs is an exact package list, not a list of privileged subtrees.
  # Expand wildcard requests first so ./... cannot include a root package,
  # while an unlisted child of a root package can still run.
  if [[ -n "$root_test_go_sh" ]]; then
    local root_pkgs
    root_pkgs=$(sed -n '/root_pkgs=(/,/)/p' "$root_test_go_sh" | grep -oE 'pkg/[^"]+' || true)
    if [[ -n "$root_pkgs" ]]; then
      local expanded=() filtered=() directories directory module_path
      module_path=$(cd "$PRIMARY_MOD" && pwd -P) || exit 1
      for pkg in "${TEST_ONLY_PKGS[@]}"; do
        if [[ "$pkg" == *...* ]]; then
          if ! directories=$(cd "$PRIMARY_MOD" && go list "${VENDOR_FLAGS[@]}" -f '{{.Dir}}' "$pkg" 2>> "$REBASE_TMP/$LOG_NAME"); then
            echo "FAIL — package expansion failed (see $REBASE_TMP/$LOG_NAME)"
            cat "$REBASE_TMP/$LOG_NAME"
            exit 1
          fi
          [[ -n "$directories" ]] || { echo "FAIL — no packages matched $pkg" | tee -a "$REBASE_TMP/$LOG_NAME"; exit 1; }
          while IFS= read -r directory; do
            if [[ "$directory" == "$module_path" ]]; then
              expanded+=(.)
            elif [[ "$directory" == "$module_path/"* ]]; then
              expanded+=("./${directory#"$module_path/"}")
            else
              echo "FAIL — package outside selected module: $directory" | tee -a "$REBASE_TMP/$LOG_NAME"
              exit 1
            fi
          done <<< "$directories"
        else
          expanded+=("$pkg")
        fi
      done
      for pkg in "${expanded[@]}"; do
        if grep -Fxq -- "${pkg#./}" <<< "$root_pkgs"; then
          echo ":: Skipping root_pkg $pkg (needs CAP_NET_ADMIN)"
        else
          filtered+=("$pkg")
        fi
      done
      TEST_ONLY_PKGS=("${filtered[@]}")
      if [[ "${#TEST_ONLY_PKGS[@]}" -eq 0 ]]; then
        echo "SKIP — all packages are root_pkgs; no tests ran" | tee -a "$REBASE_TMP/$LOG_NAME"
        exit 0
      fi
    fi
  fi

  # Determine timeout — 60m for packages over 30k test lines, 30m otherwise
  local TEST_TIMEOUT="30m"
  local TOTAL_LINES=0
  for pkg in "${TEST_ONLY_PKGS[@]}"; do
    local pkg_dir="${PRIMARY_MOD}/${pkg#./}"
    pkg_dir="${pkg_dir%/...}"
    if [[ -d "$pkg_dir" ]]; then
      local lines
      lines=$(find "$pkg_dir" -name "*_test.go" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" -exec cat {} + 2>/dev/null | wc -l)
      TOTAL_LINES=$((TOTAL_LINES + lines))
    fi
  done
  (( TOTAL_LINES > 30000 )) && TEST_TIMEOUT="60m"
  # Limit compiler parallelism for large suites to reduce memory pressure.
  # Default GOMAXPROCS uses all CPUs, which can cause 5GB+ RAM spikes
  # during compilation. GOMAXPROCS=2 reduces the spike to ~1GB.
  if (( TOTAL_LINES > 30000 )); then
    export GOMAXPROCS="${GOMAXPROCS:-2}"
    echo "Test lines: ~$TOTAL_LINES (timeout: $TEST_TIMEOUT, GOMAXPROCS=$GOMAXPROCS)"
  else
    echo "Test lines: ~$TOTAL_LINES (timeout: $TEST_TIMEOUT)"
  fi

  # Match outer timeout to Go test timeout so the container isn't killed early
  VALIDATION_TIMEOUT="$TEST_TIMEOUT"

  local test_command module_command
  printf -v module_command '%q' "$PRIMARY_MOD"
  printf -v test_command '%q ' go test "${VENDOR_FLAGS[@]}" -count=1 -timeout "$TEST_TIMEOUT" "${TEST_ONLY_EXTRA[@]}" "${TEST_ONLY_PKGS[@]}"
  local step_failed=0
  run_validation "$LOG_NAME" "cd $module_command && $test_command" || step_failed=1

  if [[ "$step_failed" -eq 1 ]]; then
    echo ""
    echo "FAIL — see $REBASE_TMP/$LOG_NAME"
    tail -30 "$REBASE_TMP/$LOG_NAME"
    exit 1
  else
    echo ""
    echo "PASS — all specified packages"
    exit 0
  fi
}

if [[ "$MODE" == "test-only" ]]; then
  run_test_only
fi

# Only full validation owns the shared summary; test workers own their logs.
: > "$SUMMARY"

echo "━━━━ Build Validation ━━━━"
echo ""

step_failed=0

# Shared helper: run golangci-lint directly (no container).
# Reads mod_dir, mod_name, and step_failed from the enclosing scope.
_run_lint_direct() {
  local vendor_flag=""
  [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && vendor_flag="--modules-download-mode=vendor"
  run_validation "${mod_name}-lint" "cd $mod_dir && golangci-lint run --verbose --max-same-issues 0 $vendor_flag --timeout=15m0s" || step_failed=1
}

# Auto-detect modules and validate each one
while IFS= read -r gomod; do
  mod_dir=$(dirname "$gomod" | sed 's|^\./||')
  mod_name=$(basename "$mod_dir")
  [[ "$mod_dir" == "." ]] && mod_name="root"

  # Skip modules with gitignored vendor dirs — their vendor may be
  # stale and produce false build/vet/lint errors
  if [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && git check-ignore -q "$REPO_ROOT/$mod_dir/vendor" 2>/dev/null; then
    echo ":: Skipping $mod_dir (vendor is gitignored)"
    continue
  fi

  # Try make first (if Makefile exists), fall back to go build
  step_failed=0
  if [[ -f "$REPO_ROOT/$mod_dir/Makefile" ]]; then
    # A repository's default target may update dependencies or print help.
    # Prefer its explicit build entrypoint when declared in this Makefile.
    build_target=()
    grep -qE '^build[[:space:]]*:' "$REPO_ROOT/$mod_dir/Makefile" && build_target=(build)
    printf -v build_command '%q ' make -C "$mod_dir" "${build_target[@]}"
    run_validation "${mod_name}-build" "$build_command" || step_failed=1
    categorize_errors "$REBASE_TMP/${mod_name}-build.log" "$mod_name build" "$step_failed"

    step_failed=0
    lint_target=""
    grep -q "^lint:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && lint_target="lint"
    [[ -z "$lint_target" ]] && grep -q "^golangci-lint:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && lint_target="golangci-lint"
    # --quick skips lint (see usage comment; build+vet only)
    if [[ "$MODE" != "quick" ]] && [[ -n "$lint_target" ]]; then
      if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
        # Inside a container — make lint often needs nested containers
        # (e.g., hack/lint.sh runs golangci-lint in its own container).
        # Run golangci-lint directly instead.
        command -v golangci-lint &>/dev/null || go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest 2>/dev/null
        if command -v golangci-lint &>/dev/null; then
          _run_lint_direct
        else
          echo "  WARNING: golangci-lint not available — skipping lint"
        fi
      else
        run_validation "${mod_name}-lint" "make -C $mod_dir $lint_target" || {
          _lint_log="$REBASE_TMP/${mod_name}-lint.log"
          if grep -qE "Go language version.*lower than the targeted|failed to install golangci-lint" "$_lint_log" 2>/dev/null; then
            echo "  NOTE: lint version incompatible, installing latest via go install..."
            go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest 2>/dev/null
            if command -v golangci-lint &>/dev/null; then
              _run_lint_direct
            else
              step_failed=1
            fi
          elif grep -qE "short-name resolution|cannot prompt without a TTY|Error[: ]125|linter can only be run within a container" "$_lint_log" 2>/dev/null; then
            echo "  NOTE: make lint container pull failed — running golangci-lint directly..."
            command -v golangci-lint &>/dev/null || go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest 2>/dev/null
            if command -v golangci-lint &>/dev/null; then
              _run_lint_direct
            else
              echo "  WARNING: golangci-lint not available and container pull failed — skipping lint"
            step_failed=1
            fi
          else
            step_failed=1
          fi
        }
      fi
      categorize_errors "$REBASE_TMP/${mod_name}-lint.log" "$mod_name lint" "$step_failed"
    elif [[ "$MODE" != "quick" ]]; then
      echo ":: SKIP lint ($mod_dir): no Makefile lint target; no linter executed"
    fi

    step_failed=0
    test_target=""
    for _tt in test test-unit check; do
      grep -q "^${_tt}:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && test_target="$_tt" && break
    done
    # --quick skips tests; --no-test also skips tests (see usage comment)
    if [[ "$MODE" != "quick" ]] && [[ "$MODE" != "no-test" ]] && [[ -n "$test_target" ]]; then
      # Try make test first; if it needs sudo (common for network namespace tests),
      # fall back to go test without -race for non-privileged packages.
      # Source feature gate env vars from test-go.sh so fake clientsets work.
      run_validation "${mod_name}-test" "make -C $mod_dir $test_target" || {
        step_failed=1
        if grep -q "sudo" "$REBASE_TMP/${mod_name}-test.log" 2>/dev/null; then
          echo "  NOTE: make test needs sudo/privileged container for some packages"
          GATE_EXPORTS=""
          TEST_GO_SH=$(find "$REPO_ROOT" -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" | head -1)
          if [[ -n "$TEST_GO_SH" ]]; then
            GATE_EXPORTS=$(grep "^export KUBE_FEATURE_" "$TEST_GO_SH" | tr '\n' '; ')
          fi
          # Find privileged packages from test-go.sh root_pkgs array
          ROOT_PKGS=""
          if [[ -n "$TEST_GO_SH" ]]; then
            ROOT_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' | sort -u | tr '\n' '|')
          fi
          # When vendor/ changed (k8s rebase), test ALL non-privileged
          # packages — vendored dep changes affect all consumers, not
          # just packages with source changes.
          if MERGE_BASE=$(bash "$SCRIPT_DIR/resolve-rebase-base.sh" "$REPO_ROOT"); then
            VENDOR_CHANGED=$(git -C "$REPO_ROOT" diff --name-only "$MERGE_BASE"..HEAD -- "${mod_dir}/vendor/" 2>/dev/null | head -1 || true)
          else
            echo "  Baseline unavailable — testing all non-privileged packages; attribution unresolved"
            VENDOR_CHANGED=unknown
          fi
          _vendor_flag=""
          [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && _vendor_flag="-mod vendor"
          TEST_PKGS=""
          if [[ -n "$VENDOR_CHANGED" ]]; then
            echo "  Vendor changed — testing all non-privileged packages..."
            while IFS= read -r pkg; do
              [[ -z "$pkg" ]] && continue
              if [[ -n "$ROOT_PKGS" ]] && [[ "$pkg" =~ ^(${ROOT_PKGS%|})$ ]]; then
                echo "  Skipping privileged: $pkg"
                continue
              fi
              TEST_PKGS+=" ./${pkg}/..."
            done < <(cd "$REPO_ROOT/$mod_dir" && find . -name "*_test.go" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" -exec dirname {} \; | sed 's|^\./||' | sort -u)
          else
            echo "  Testing changed non-privileged packages only..."
            CHANGED_PKGS=$(git -C "$REPO_ROOT" diff --name-only "$MERGE_BASE"..HEAD -- "${mod_dir}/" 2>/dev/null | grep '\.go$' | grep -v vendor | grep -v "_test.go" | sed "s|${mod_dir}/||;s|/[^/]*$||" | sort -u || true)
            for pkg in $CHANGED_PKGS; do
              if [[ -n "$ROOT_PKGS" ]] && [[ "$pkg" =~ ^(${ROOT_PKGS%|})$ ]]; then
                echo "  Skipping privileged: $pkg"
                continue
              fi
              if find "$REPO_ROOT/$mod_dir/$pkg" -name "*_test.go" -maxdepth 1 2>/dev/null | grep -q .; then
                TEST_PKGS+=" ./${pkg}/..."
              fi
            done
          fi
          if [[ -n "$TEST_PKGS" ]]; then
            echo "  Testing:$TEST_PKGS"
            if run_validation "${mod_name}-test" "${GATE_EXPORTS} cd $mod_dir && GOMAXPROCS=\${GOMAXPROCS:-2} go test $_vendor_flag -timeout ${VALIDATION_TIMEOUT} ${TEST_PKGS} -count=1"; then
              step_failed=0
            fi
          else
            echo "  No non-privileged test packages found"
          fi
        else
          step_failed=1
        fi
      }
      categorize_errors "$REBASE_TMP/${mod_name}-test.log" "$mod_name test" "$step_failed"
    fi
  else
    run_validation "${mod_name}-build" "cd $mod_dir && go build ./..." || step_failed=1
    categorize_errors "$REBASE_TMP/${mod_name}-build.log" "$mod_name build" "$step_failed"
  fi

  # go vet: fast, catches most issues. Always run.
  step_failed=0
  run_validation "${mod_name}-vet" "cd $mod_dir && go vet ./..." || step_failed=1
  categorize_errors "$REBASE_TMP/${mod_name}-vet.log" "$mod_name vet" "$step_failed"
done < <(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" | sort)

# Stricter vet via go test (compiles test binaries, catches Eventf
# format/arg mismatches that go vet misses). Skip in --quick mode
# because test binary compilation is slow (~3 min for large repos).
if [[ "$MODE" != "quick" ]]; then
  while IFS= read -r gomod; do
    [[ -z "$gomod" ]] && continue
    mod_dir=$(dirname "$gomod")
    # Skip modules with gitignored vendor (e.g., test/e2e)
    if [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && git check-ignore -q "$REPO_ROOT/$mod_dir/vendor" 2>/dev/null; then
      continue
    fi
    mod_name=$(basename "$mod_dir")
    [[ "$mod_name" == "." ]] && mod_name=$(basename "$REPO_ROOT")
    step_failed=0
    _tv_vendor=""
    [[ -d "$mod_dir/vendor" ]] && _tv_vendor="-mod vendor"
    run_validation "${mod_name}-test-vet" "cd $mod_dir && GOMAXPROCS=${GOMAXPROCS:-2} go test $_tv_vendor -run='^$' -count=1 ./..." || step_failed=1
    categorize_errors "$REBASE_TMP/${mod_name}-test-vet.log" "$mod_name test-vet" "$step_failed"
  done < <(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" | sort)
fi

if [[ "$MODE" != "quick" ]]; then
# ── CI parity checks ────────────────────────────────────────────────
# Run the same checks CI runs beyond build/lint/vet/test.
# These are quick and catch issues the per-module checks miss.

echo ""
echo "━━━━ CI Parity Checks ━━━━"
echo ""

# Find the primary module (the one with a Makefile and these targets)
for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" | sort); do
  ci_dir=$(dirname "$gomod" | sed 's|^\./||')
  [[ -f "$REPO_ROOT/$ci_dir/Makefile" ]] || continue

  if grep -q "^gofmt:" "$REPO_ROOT/$ci_dir/Makefile" 2>/dev/null; then
    step_failed=0
    run_validation "${ci_dir##*/}-gofmt" "make -C $ci_dir gofmt" || step_failed=1
    if [[ "$step_failed" -eq 1 ]]; then
      # Container path failure in worktrees (same pattern as lint fallback).
      # The make gofmt target mounts the parent dir of worktrees, so
      # hack/verify-gofmt.sh is not found at the expected path inside the container.
      if grep -qE "not found.*OCI|executable.*not found|No such file.*Error 127|Error[: ]+125|short-name resolution|cannot prompt without a TTY" \
          "$REBASE_TMP/${ci_dir##*/}-gofmt.log" 2>/dev/null; then
        echo "  NOTE: make gofmt container failed — running gofmt directly..."
        step_failed=0
        if command -v gofmt &>/dev/null; then
          _gofmt_unformatted=$(cd "$REPO_ROOT/$ci_dir" && \
            gofmt -l . 2>/dev/null | grep -v vendor/ | grep -v '.cache/' | head -20 || true)
          if [[ -n "$_gofmt_unformatted" ]]; then
            printf 'NOTE: container unavailable — direct gofmt\nUnformatted files:\n' \
              > "$REBASE_TMP/${ci_dir##*/}-gofmt.log"
            echo "$_gofmt_unformatted" >> "$REBASE_TMP/${ci_dir##*/}-gofmt.log"
            step_failed=1
          fi
        else
          echo "  WARNING: gofmt not available and container failed — skipping gofmt check"
        fi
      fi
    fi
    if [[ "$step_failed" -eq 1 ]]; then
      echo "## GOFMT ERRORS ($ci_dir)" >> "$SUMMARY"
      tail -10 "$REBASE_TMP/${ci_dir##*/}-gofmt.log" >> "$SUMMARY"
      echo "" >> "$SUMMARY"
      ERRORS_FOUND=1
    fi
  fi

  if grep -q "^verify-go-mod-vendor:" "$REPO_ROOT/$ci_dir/Makefile" 2>/dev/null; then
    step_failed=0
    run_validation "${ci_dir##*/}-vendor" "make -C $ci_dir verify-go-mod-vendor" || step_failed=1
    if [[ "$step_failed" -eq 1 ]]; then
      echo "## VENDOR VERIFICATION ERRORS ($ci_dir)" >> "$SUMMARY"
      if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
        echo "NOTE: vendor mismatch in container may be a false positive (different Go cache)." >> "$SUMMARY"
        echo "Verify on host: make -C $ci_dir verify-go-mod-vendor" >> "$SUMMARY"
      fi
      tail -10 "$REBASE_TMP/${ci_dir##*/}-vendor.log" >> "$SUMMARY"
      echo "" >> "$SUMMARY"
      ERRORS_FOUND=1
    fi
  fi

  if grep -q "^windows:" "$REPO_ROOT/$ci_dir/Makefile" 2>/dev/null; then
    step_failed=0
    run_validation "${ci_dir##*/}-windows" "make -C $ci_dir windows" || step_failed=1
    if [[ "$step_failed" -eq 1 ]]; then
      echo "## WINDOWS BUILD ERRORS ($ci_dir)" >> "$SUMMARY"
      tail -10 "$REBASE_TMP/${ci_dir##*/}-windows.log" >> "$SUMMARY"
      echo "" >> "$SUMMARY"
      ERRORS_FOUND=1
    fi
  fi

  if grep -q "^verify-third-party-licenses:" "$REPO_ROOT/$ci_dir/Makefile" 2>/dev/null; then
    step_failed=0
    run_validation "${ci_dir##*/}-licenses" "make -C $ci_dir verify-third-party-licenses" || step_failed=1
    if [[ "$step_failed" -eq 1 ]]; then
      echo "## LICENSE VERIFICATION ERRORS ($ci_dir)" >> "$SUMMARY"
      tail -10 "$REBASE_TMP/${ci_dir##*/}-licenses.log" >> "$SUMMARY"
      echo "" >> "$SUMMARY"
      ERRORS_FOUND=1
    fi
  fi
done

fi # end MODE != quick

# ── Test skip detection ─────────────────────────────────────────────
# Agents must never add test skips during a rebase (SKILL.md rule).
# Diff-based: only flags newly added skip calls, not pre-existing ones.

SKIP_HITS=""
if SKIP_MERGE_BASE=$(bash "$SCRIPT_DIR/resolve-rebase-base.sh" "$REPO_ROOT"); then
  SKIP_HITS=$(git -C "$REPO_ROOT" diff "$SKIP_MERGE_BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' \
    | grep -E '^\+.*\bt\.Skip[f]?\s*\(|^\+.*\bginkgo\.Skip[f]?\s*\(|^\+.*\be2eskipper\.Skip[f]?\s*\(|^\+.*\bskipper\.Skip[f]?\s*\(' \
    || true)
else
  echo "## INCONCLUSIVE TEST SKIP CHECK — rebase baseline unavailable" >> "$SUMMARY"
  ERRORS_FOUND=1
fi

if [[ -n "$SKIP_HITS" ]]; then
  echo ""
  echo "━━━━ Test Skip Detection ━━━━"
  echo ""
  echo "  FAIL — new test skips detected in branch diff"
  {
    echo "## TEST SKIPS ADDED (rebase policy violation)"
    echo "Never add test skips to make CI green. Fix the root cause."
    echo ""
    echo "$SKIP_HITS"
    echo ""
  } >> "$SUMMARY"
  ERRORS_FOUND=1
fi

# ── Privileged tests (--full only) ──────────────────────────────────
if [[ "$MODE" == "full" ]]; then
  echo ""
  echo "━━━━ Privileged Tests ━━━━"
  echo ""

  for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" -not -path "*/.claude/*" | sort); do
    mod_dir=$(dirname "$gomod" | sed 's|^\./||')
    TEST_GO_SH=$(find "$REPO_ROOT/$mod_dir" -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" -not -path "*/.rebase-tmp/*" -not -path "*/.git/*" | head -1)
    [[ -n "$TEST_GO_SH" ]] || continue

    GATE_EXPORTS=$(grep "^export KUBE_FEATURE_" "$TEST_GO_SH" | tr '\n' '; ')
    PRIV_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' | sort -u)
    [[ -z "$PRIV_PKGS" ]] && continue

    _priv_vendor_flag=""
    [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && _priv_vendor_flag="-mod vendor"
    for pkg in $PRIV_PKGS; do
      # Skip packages whose directories no longer exist (stale root_pkgs entries)
      if [[ ! -d "$REPO_ROOT/$mod_dir/$pkg" ]]; then
        echo "  Skipping stale: $pkg (directory does not exist)"
        continue
      fi
      # A missing runtime or an unexpectedly nonroot container must not turn
      # requested but unexecuted privileged coverage into a successful --full.
      if [[ "$(id -u)" != "0" ]]; then
        echo "  INCONCLUSIVE: privileged tests did not run: $mod_dir/$pkg (not root)"
        {
          echo "## INCONCLUSIVE PRIVILEGED TESTS ($mod_dir/$pkg)"
          echo "--full requested this package, but validation is not running as root."
          echo "Run in a working root container with the required capabilities."
          echo ""
        } >> "$SUMMARY"
        ERRORS_FOUND=1
        continue
      fi
      if ! command -v sudo &>/dev/null; then
        printf '#!/bin/sh\nwhile [ "${1#-}" != "$1" ]; do shift; done\nexec "$@"\n' > /usr/local/bin/sudo
        chmod +x /usr/local/bin/sudo
      fi
      step_failed=0
      run_validation "priv-${pkg##*/}" "${GATE_EXPORTS} cd $mod_dir && GOMAXPROCS=\${GOMAXPROCS:-2} go test $_priv_vendor_flag -count=1 -timeout 5m ./$pkg/..." || step_failed=1
      if [[ "$step_failed" -eq 1 ]]; then
        echo "## PRIVILEGED TEST FAILURE ($pkg)" >> "$SUMMARY"
        tail -10 "$REBASE_TMP/priv-${pkg##*/}.log" >> "$SUMMARY"
        echo "" >> "$SUMMARY"
        ERRORS_FOUND=1
      fi
    done
  done
fi

cd "$REPO_ROOT" 2>/dev/null || true

echo ""
if [[ "$ERRORS_FOUND" -eq 0 ]]; then
  echo "All validation passes. No fixups needed."
  exit 0
else
  echo "Errors found. Summary: $SUMMARY"
  echo ""
  cat "$SUMMARY"
  exit 1
fi
