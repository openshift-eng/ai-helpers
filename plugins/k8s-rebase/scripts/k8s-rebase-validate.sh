#!/bin/bash
# k8s-rebase-validate.sh — Collect and categorize validation errors
#
# Runs build, lint, and test for all modules. Captures output to logs.
# Parses logs to extract actionable errors. Writes categorized summary.
#
# Usage: k8s-rebase-validate.sh [--quick|--no-test|--full|--test-only PKG...]
#   --quick      Build + vet only (~1 min)
#   --no-test    Build + vet + lint, no tests (~5 min)
#   --full       All checks + privileged tests as root (~25 min)
#   --test-only  Run tests for specified packages only (for parallel agents)
#   default      All checks except privileged tests (~15 min)
#
# --test-only handles auto-containerization, feature gate exports,
# and output capture — subagents should use it instead of raw go test.
# Example: k8s-rebase-validate.sh --test-only ./pkg/ovn/... ./pkg/util/...
#
# Exit codes: 0 = all validation passes (no errors)
#             1 = errors found (see $REBASE_TMP/summary.txt)

set -uo pipefail

MODE="default"
TEST_ONLY_PKGS=""
[[ "${1:-}" == "--quick" ]] && MODE="quick"
[[ "${1:-}" == "--no-test" ]] && MODE="no-test"
[[ "${1:-}" == "--full" ]] && MODE="full"
TEST_ONLY_EXTRA=""
if [[ "${1:-}" == "--test-only" ]]; then
  MODE="test-only"
  shift
  # Separate packages from go test flags. Once we see a -flag, treat
  # everything from that point as extra args (flags + their values).
  in_flags=false
  for arg in "$@"; do
    if [[ "$arg" == -* ]]; then
      in_flags=true
    fi
    if $in_flags; then
      TEST_ONLY_EXTRA="$TEST_ONLY_EXTRA $arg"
    else
      TEST_ONLY_PKGS="$TEST_ONLY_PKGS $arg"
    fi
  done
  TEST_ONLY_PKGS="${TEST_ONLY_PKGS# }"
  TEST_ONLY_EXTRA="${TEST_ONLY_EXTRA# }"
  [[ -z "$TEST_ONLY_PKGS" ]] && { echo "ERROR: --test-only requires package arguments" >&2; exit 1; }
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
REBASE_TMP="$REPO_ROOT/.rebase-tmp"
mkdir -p "$REBASE_TMP"
grep -qF '.rebase-tmp' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.rebase-tmp/' >> "$REPO_ROOT/.git/info/exclude"

# Guard: refuse to run on master/main — validate must run on the rebase branch.
_current_branch=$(git branch --show-current 2>/dev/null || true)
if [[ "$_current_branch" == "master" || "$_current_branch" == "main" ]]; then
  echo "ERROR: Validate is running on '$_current_branch', not the rebase branch."
  if [[ -f "$REPO_ROOT/.rebase-tmp/branch-name" ]]; then
    echo "The rebase branch is: $(cat "$REPO_ROOT/.rebase-tmp/branch-name")"
    echo "Run: git checkout $(cat "$REPO_ROOT/.rebase-tmp/branch-name")"
  fi
  exit 1
fi

# Auto-containerize if local Go is too old for the repo's go.mod
cd "$REPO_ROOT" || exit 1
REQUIRED_GO=""
for gm in go-controller/go.mod go.mod; do
  [[ -f "$gm" ]] && REQUIRED_GO=$(grep "^go " "$gm" | awk '{print $2}') && break
done
CURRENT_GO=$(go env GOVERSION 2>/dev/null | sed 's/go//' || echo "0.0")
if [[ -n "$REQUIRED_GO" ]] && [[ "${K8S_REBASE_IN_CONTAINER:-}" != "1" ]]; then
  REQ_MINOR=$(echo "$REQUIRED_GO" | cut -d. -f2)
  CUR_MINOR=$(echo "$CURRENT_GO" | cut -d. -f2)
  if [[ "$CUR_MINOR" -lt "$REQ_MINOR" ]] 2>/dev/null; then
    CONTAINER_RT=""
    command -v podman &>/dev/null && CONTAINER_RT=podman
    [[ -z "$CONTAINER_RT" ]] && command -v docker &>/dev/null && CONTAINER_RT=docker
    if [[ -n "$CONTAINER_RT" ]]; then
      GO_IMAGE="docker.io/library/golang:${REQUIRED_GO}"
      echo ":: Go $CURRENT_GO < $REQUIRED_GO — re-running validate inside $GO_IMAGE"
      SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
      USERNS_FLAG=""
      [[ "$CONTAINER_RT" == "podman" ]] && [[ "$MODE" != "full" ]] && USERNS_FLAG="--userns=keep-id"
      MODE_FLAG=""
      [[ "$MODE" != "default" ]] && MODE_FLAG="--$MODE"
      PRIV_FLAG=""
      [[ "$MODE" == "full" ]] && PRIV_FLAG="--privileged"
      EXTRA_ARGS=""
      [[ "$MODE" == "test-only" ]] && EXTRA_ARGS="$TEST_ONLY_PKGS $TEST_ONLY_EXTRA"
      exec $CONTAINER_RT run --rm \
        --security-opt label=disable \
        $PRIV_FLAG \
        $USERNS_FLAG \
        -v "$REPO_ROOT:$REPO_ROOT" \
        -v "$(dirname "$SCRIPT_PATH"):$(dirname "$SCRIPT_PATH"):ro" \
        -w "$REPO_ROOT" \
        -e K8S_REBASE_IN_CONTAINER=1 \
        "$GO_IMAGE" \
        bash "$SCRIPT_PATH" $MODE_FLAG $EXTRA_ARGS
    fi
  fi
fi

export GOWORK=off
SUMMARY="$REBASE_TMP/summary.txt"
ERRORS_FOUND=0
VALIDATION_TIMEOUT="${VALIDATION_TIMEOUT:-25m}"
LINT_TIMEOUT="${LINT_TIMEOUT:-30m}"

: > "$SUMMARY"

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
    curl -sL https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 -o /tmp/jq 2>/dev/null \
      && echo "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5  /tmp/jq" | sha256sum -c --quiet 2>/dev/null \
      && chmod +x /tmp/jq && export PATH="/tmp:$PATH"
  fi
fi

run_validation() {
  local name="$1"
  local logfile="$REBASE_TMP/${name}.log"
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
  local rc=0
  timeout "$step_timeout" bash -c "$*" > "$logfile" 2>&1 || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    echo "  PASS"
    return 0
  elif [[ "$rc" -eq 124 ]]; then
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
  lint_errors=$(grep -E "\.go:[0-9]+:[0-9]+:.*(SA[0-9]+|staticcheck|lostcancel|gci|inline:|nilness:|govet|errcheck|gosimple|ineffassign|typecheck|unused)" "$logfile" 2>/dev/null | grep -v "^#" || true)
  vet_errors=$(grep -E ":[0-9]+:[0-9]+:.*(non-constant format string|format %|has arguments but no formatting directives|deprecated|call needs [0-9]+ args but has)" "$logfile" 2>/dev/null | grep -v "^#" || true)
  test_failures=$(grep -E "^--- FAIL:|^FAIL\t" "$logfile" 2>/dev/null || true)

  if [[ -n "$build_errors" ]]; then
    echo "## BUILD ERRORS ($category)" >> "$SUMMARY"
    echo "$build_errors" >> "$SUMMARY"
    if echo "$build_errors" | grep -q "does not implement.*SharedIndexInformer\|vendor.*does not implement" 2>/dev/null; then
      echo "" >> "$SUMMARY"
      echo "NOTE: Vendored dependency missing a new interface method." >> "$SUMMARY"
      echo "Patching vendor directly will fail verify-deps CI." >> "$SUMMARY"
      echo "Options: (1) bump the dep with go get @latest, (2) use a" >> "$SUMMARY"
      echo "go.mod replace to a fork, (3) patch vendor and accept CI failure." >> "$SUMMARY"
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
    echo "## UNCLASSIFIED FAILURE ($category)" >> "$SUMMARY"
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
  echo "Packages: $TEST_ONLY_PKGS"

  # Find primary module
  local PRIMARY_MOD=""
  for candidate in go-controller .; do
    [[ -f "$candidate/go.mod" ]] && PRIMARY_MOD="$candidate" && break
  done
  [[ -z "$PRIMARY_MOD" ]] && PRIMARY_MOD=$(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | head -1)

  # Export feature gate env vars
  local TEST_GO_SH
  TEST_GO_SH=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
  if [[ -n "$TEST_GO_SH" ]]; then
    while IFS='=' read -r _key _val; do
      [[ "$_key" =~ ^export\ KUBE_FEATURE_[A-Za-z0-9_]+$ ]] && export "${_key#export }=$_val"
    done < <(grep "^export KUBE_FEATURE_" "$TEST_GO_SH")
  fi

  local VENDOR_FLAG=""
  [[ -d "$PRIMARY_MOD/vendor" ]] && VENDOR_FLAG="-mod vendor"

  # Strip module dir prefix from package paths if present
  # (agent may pass ./go-controller/pkg/ovn/... instead of ./pkg/ovn/...)
  if [[ "$PRIMARY_MOD" != "." ]]; then
    local cleaned=""
    for pkg in $TEST_ONLY_PKGS; do
      pkg="${pkg#./${PRIMARY_MOD}/}"   # strip ./go-controller/
      pkg="${pkg#${PRIMARY_MOD}/}"     # strip go-controller/
      [[ "$pkg" != ./* ]] && pkg="./$pkg"
      cleaned="$cleaned $pkg"
    done
    TEST_ONLY_PKGS="${cleaned# }"
  fi

  # Filter out root_pkgs (need CAP_NET_ADMIN, always fail unprivileged)
  local test_go_sh
  test_go_sh=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" 2>/dev/null | head -1)
  if [[ -n "$test_go_sh" ]]; then
    local root_pkgs_pattern
    root_pkgs_pattern=$(sed -n '/root_pkgs=(/,/)/p' "$test_go_sh" | grep -oE 'pkg/[^"]+' | tr '\n' '|' || true)
    if [[ -n "$root_pkgs_pattern" ]]; then
      local filtered=""
      for pkg in $TEST_ONLY_PKGS; do
        if echo "$pkg" | grep -qE "^\./(${root_pkgs_pattern%|})"; then
          echo ":: Skipping root_pkg $pkg (needs CAP_NET_ADMIN)"
        else
          filtered="$filtered $pkg"
        fi
      done
      TEST_ONLY_PKGS="${filtered# }"
      [[ -z "$TEST_ONLY_PKGS" ]] && { echo "All packages are root_pkgs — nothing to test unprivileged"; exit 0; }
    fi
  fi

  # Determine timeout — 60m for packages over 30k test lines, 30m otherwise
  local TEST_TIMEOUT="30m"
  local TOTAL_LINES=0
  for pkg in $TEST_ONLY_PKGS; do
    local pkg_dir="${PRIMARY_MOD}/${pkg#./}"
    pkg_dir="${pkg_dir%/...}"
    if [[ -d "$pkg_dir" ]]; then
      local lines
      lines=$(find "$pkg_dir" -name "*_test.go" -not -path "*/vendor/*" -exec cat {} + 2>/dev/null | wc -l)
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

  # Use PID + random suffix so parallel agents (especially containers
  # where PID is always 1) don't clobber each other
  local LOG_NAME="test-only-$$-$(date +%s)"
  local step_failed=0
  run_validation "$LOG_NAME" "cd $PRIMARY_MOD && go test $VENDOR_FLAG -count=1 -timeout $TEST_TIMEOUT $TEST_ONLY_EXTRA $TEST_ONLY_PKGS" || step_failed=1

  if [[ "$step_failed" -eq 1 ]]; then
    echo ""
    echo "FAIL — see $REBASE_TMP/${LOG_NAME}.log"
    tail -30 "$REBASE_TMP/${LOG_NAME}.log"
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

echo "━━━━ Build Validation ━━━━"
echo ""

step_failed=0

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
    run_validation "${mod_name}-build" "make -C $mod_dir" || step_failed=1
    categorize_errors "$REBASE_TMP/${mod_name}-build.log" "$mod_name build" "$step_failed"

    step_failed=0
    lint_target=""
    grep -q "^lint:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && lint_target="lint"
    [[ -z "$lint_target" ]] && grep -q "^golangci-lint:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && lint_target="golangci-lint"
    if [[ "$MODE" != "quick" ]] && [[ -n "$lint_target" ]]; then
      if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
        # Inside a container — make lint often needs nested containers
        # (e.g., hack/lint.sh runs golangci-lint in its own container).
        # Run golangci-lint directly instead.
        command -v golangci-lint &>/dev/null || go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest 2>/dev/null
        if command -v golangci-lint &>/dev/null; then
          vendor_flag=""
          [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && vendor_flag="--modules-download-mode=vendor"
          run_validation "${mod_name}-lint" "cd $mod_dir && golangci-lint run --verbose --max-same-issues 0 $vendor_flag --timeout=15m0s" || step_failed=1
        else
          echo "  WARNING: golangci-lint not available — skipping lint"
        fi
      else
        run_validation "${mod_name}-lint" "make -C $mod_dir $lint_target" || {
          if grep -qE "Go language version.*lower than the targeted|failed to install golangci-lint" "$REBASE_TMP/${mod_name}-lint.log" 2>/dev/null; then
            echo "  NOTE: lint version incompatible, installing latest via go install..."
            go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest 2>/dev/null
            if command -v golangci-lint &>/dev/null; then
              vendor_flag=""
              [[ -d "$REPO_ROOT/$mod_dir/vendor" ]] && vendor_flag="--modules-download-mode=vendor"
              run_validation "${mod_name}-lint" "cd $mod_dir && golangci-lint run --verbose --max-same-issues 0 $vendor_flag --timeout=15m0s" || step_failed=1
            else
              step_failed=1
            fi
          else
            step_failed=1
          fi
        }
      fi
      categorize_errors "$REBASE_TMP/${mod_name}-lint.log" "$mod_name lint" "$step_failed"
    fi

    step_failed=0
    test_target=""
    for _tt in test test-unit check; do
      grep -q "^${_tt}:" "$REPO_ROOT/$mod_dir/Makefile" 2>/dev/null && test_target="$_tt" && break
    done
    if [[ "$MODE" != "quick" ]] && [[ "$MODE" != "no-test" ]] && [[ -n "$test_target" ]]; then
      # Try make test first; if it needs sudo (common for network namespace tests),
      # fall back to go test without -race for non-privileged packages.
      # Source feature gate env vars from test-go.sh so fake clientsets work.
      run_validation "${mod_name}-test" "make -C $mod_dir $test_target" || {
        step_failed=1
        if grep -q "sudo" "$REBASE_TMP/${mod_name}-test.log" 2>/dev/null; then
          echo "  NOTE: make test needs sudo/privileged container for some packages"
          GATE_EXPORTS=""
          TEST_GO_SH=$(find "$REPO_ROOT" -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
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
          MERGE_BASE=$(git -C "$REPO_ROOT" merge-base HEAD master 2>/dev/null || git -C "$REPO_ROOT" merge-base HEAD main 2>/dev/null || echo "HEAD~20")
          VENDOR_CHANGED=$(git -C "$REPO_ROOT" diff --name-only "$MERGE_BASE"..HEAD -- "${mod_dir}/vendor/" 2>/dev/null | head -1 || true)
          TEST_PKGS=""
          if [[ -n "$VENDOR_CHANGED" ]]; then
            echo "  Vendor changed — testing all non-privileged packages..."
            while IFS= read -r pkg; do
              [[ -z "$pkg" ]] && continue
              if [[ -n "$ROOT_PKGS" ]] && echo "$pkg" | grep -qE "^(${ROOT_PKGS%|})$"; then
                echo "  Skipping privileged: $pkg"
                continue
              fi
              TEST_PKGS+=" ./${pkg}/..."
            done < <(cd "$REPO_ROOT/$mod_dir" && find . -name "*_test.go" -not -path "*/vendor/*" -exec dirname {} \; | sed 's|^\./||' | sort -u)
          else
            echo "  Testing changed non-privileged packages only..."
            CHANGED_PKGS=$(git -C "$REPO_ROOT" diff --name-only "$MERGE_BASE"..HEAD -- "${mod_dir}/" 2>/dev/null | grep '\.go$' | grep -v vendor | grep -v "_test.go" | sed "s|${mod_dir}/||;s|/[^/]*$||" | sort -u || true)
            for pkg in $CHANGED_PKGS; do
              if [[ -n "$ROOT_PKGS" ]] && echo "$pkg" | grep -qE "^(${ROOT_PKGS%|})$"; then
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
            if run_validation "${mod_name}-test" "${GATE_EXPORTS} cd $mod_dir && go test -mod vendor -timeout ${VALIDATION_TIMEOUT} ${TEST_PKGS} -count=1"; then
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
done < <(find . -name "go.mod" -not -path "*/vendor/*" | sort)

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
    run_validation "${mod_name}-test-vet" "cd $mod_dir && GOMAXPROCS=${GOMAXPROCS:-2} go test -run='^$' -count=1 ./..." || step_failed=1
    categorize_errors "$REBASE_TMP/${mod_name}-test-vet.log" "$mod_name test-vet" "$step_failed"
  done < <(find . -name "go.mod" -not -path "*/vendor/*" | sort)
fi

if [[ "$MODE" != "quick" ]]; then
# ── CI parity checks ────────────────────────────────────────────────
# Run the same checks CI runs beyond build/lint/vet/test.
# These are quick and catch issues the per-module checks miss.

echo ""
echo "━━━━ CI Parity Checks ━━━━"
echo ""

# Find the primary module (the one with a Makefile and these targets)
for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" | sort); do
  ci_dir=$(dirname "$gomod" | sed 's|^\./||')
  [[ -f "$REPO_ROOT/$ci_dir/Makefile" ]] || continue

  if grep -q "^gofmt:" "$REPO_ROOT/$ci_dir/Makefile" 2>/dev/null; then
    step_failed=0
    run_validation "${ci_dir##*/}-gofmt" "make -C $ci_dir gofmt" || step_failed=1
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

SKIP_MERGE_BASE=$(git -C "$REPO_ROOT" merge-base HEAD master 2>/dev/null \
  || git -C "$REPO_ROOT" merge-base HEAD main 2>/dev/null \
  || echo "HEAD~20")

SKIP_HITS=$(git -C "$REPO_ROOT" diff "$SKIP_MERGE_BASE"..HEAD -- '*.go' ':!vendor/' \
  | grep -E '^\+.*\bt\.Skip[f]?\s*\(|^\+.*\bginkgo\.Skip[f]?\s*\(|^\+.*\be2eskipper\.Skip[f]?\s*\(|^\+.*\bskipper\.Skip[f]?\s*\(' \
  || true)

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

  for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" | sort); do
    mod_dir=$(dirname "$gomod" | sed 's|^\./||')
    TEST_GO_SH=$(find "$REPO_ROOT/$mod_dir" -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
    [[ -n "$TEST_GO_SH" ]] || continue

    GATE_EXPORTS=$(grep "^export KUBE_FEATURE_" "$TEST_GO_SH" | tr '\n' '; ')
    PRIV_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' | sort -u)
    [[ -z "$PRIV_PKGS" ]] && continue

    # In --full mode, the container runs as root (no --userns=keep-id)
    if [[ "$(id -u)" != "0" ]]; then
      echo "  NOTE: Privileged tests need root — run with --full flag"
      echo "  (--full disables --userns=keep-id so the container runs as root)"
    else
      # We ARE root — run privileged tests directly
      if ! command -v sudo &>/dev/null; then
        printf '#!/bin/sh\nwhile [ "${1#-}" != "$1" ]; do shift; done\nexec "$@"\n' > /usr/local/bin/sudo
        chmod +x /usr/local/bin/sudo
      fi
      for pkg in $PRIV_PKGS; do
        # Skip packages whose directories no longer exist (stale root_pkgs entries)
        if [[ ! -d "$REPO_ROOT/$mod_dir/$pkg" ]]; then
          echo "  Skipping stale: $pkg (directory does not exist)"
          continue
        fi
        step_failed=0
        run_validation "priv-${pkg##*/}" "${GATE_EXPORTS} cd $mod_dir && go test -mod vendor -count=1 -timeout 5m ./$pkg/..." || step_failed=1
        if [[ "$step_failed" -eq 1 ]]; then
          echo "## PRIVILEGED TEST FAILURE ($pkg)" >> "$SUMMARY"
          tail -10 "$REBASE_TMP/priv-${pkg##*/}.log" >> "$SUMMARY"
          echo "" >> "$SUMMARY"
          ERRORS_FOUND=1
        fi
      done
    fi
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
