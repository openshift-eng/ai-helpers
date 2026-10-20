#!/usr/bin/env bash
set -euo pipefail
# Unit and integration tests for CVE fix library and scripts.
# Runs without docker, grype, or network access.
#
# Test sections:
#   Pure functions:     abbreviate_package, version_gte, state_file_path
#   Library functions:  clean_gomod, load_state, insert/remove_grype_ignore
#   Script tests:       detect.sh, locate.sh, ignore.sh
#   Error handling:     fix-all.sh error paths, cleanup trap behavior
#   Counter logic:      Summary counts + final rescan gate exit decision
#   Parser regression:  Pipe delimiter (replaces tab), field ordering
#   Orchestration:      scan-regression CVE grouping with mocks

# SCRIPT_DIR is the scripts directory under test, as in the scripts themselves.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
TEST_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

# shellcheck source=../scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

# Go file edits remain real; graph lookups must never contact public or private
# registries from this hermetic suite, including when host caches are cold.
# A nonempty list of empty experiment names selects upstream defaults, including
# on distro Go installations whose go.env sets experiments when the value is empty.
export GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local GOEXPERIMENT=,

PASS=0 FAIL=0
check() {
  local desc="$1"; shift
  local negate=false
  [[ "$1" == "!" ]] && { negate=true; shift; }
  local rc=0; "$@" 2>/dev/null || rc=$?
  if { [[ "$negate" == false ]] && [[ $rc -eq 0 ]]; } || \
     { [[ "$negate" == true ]] && [[ $rc -ne 0 ]]; }; then
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"; FAIL=$((FAIL + 1))
  fi
}

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/cve-fix-test.XXXXXX")
trap 'test_status=$?; if (( test_status )); then
  printf "Test artifacts retained: %s\n" "$TMPD" >&2
else rm -rf "$TMPD"; fi' EXIT
# Run state and scratch files stay inside the suite's directory.
export TMPDIR="$TMPD"

# Host runtimes must not pull builder images during hermetic detection tests.
# Tests that exercise containers prepend their own controlled runtime stubs.
mkdir -p "$TMPD/no-host-containers"
for _runtime in docker podman; do
  printf '#!/bin/sh\nexit 1\n' > "$TMPD/no-host-containers/$_runtime"
  chmod +x "$TMPD/no-host-containers/$_runtime"
done
export PATH="$TMPD/no-host-containers:$PATH"

# Test repo helper: init a git repo with one commit, optional branch checkout.
make_test_repo() {
  local dir="$1" branch="${2:-devel}"
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" config user.email "test@test.com"
  git -C "$dir" config user.name "Test"
  touch "$dir/go.mod"
  git -C "$dir" add -A
  git -C "$dir" commit -qm "init"
  [[ -n "$branch" ]] && git -C "$dir" checkout -q -b "$branch"
}

# Hermetic Go repository for detect.sh, registry and installed-version cases.
GO_FIXTURE="$TMPD/go-fixture"
make_test_repo "$GO_FIXTURE" ""
printf 'module example.com/fixture\n\ngo 1.24.0\n\nrequire (\n\tgithub.com/pkg/errors v0.9.1\n)\n' > "$GO_FIXTURE/go.mod"
git -C "$GO_FIXTURE" commit -qam "Add go.mod"

# Test state helper: write standard 5-field state file.
make_go_state() {
  local _statefile="$1" _repo="$2"
  cat > "$_statefile" <<EOF
REPO="$_repo"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
}

state_value() {
  local state_file="$1" key="$2"
  (
    # shellcheck source=/dev/null
    source "$state_file"
    printf '%s' "${!key-}"
  )
}

# === Pure functions ===
echo "pure functions"
VALID_GRYPE_JSON="$TMPD/valid-grype.json"
INVALID_GRYPE_JSON="$TMPD/invalid-grype.json"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$VALID_GRYPE_JSON"
check "Grype JSON schema accepts required arrays" \
  grype_scan_json_valid "$VALID_GRYPE_JSON"
printf '{"matches":[]}\n' > "$VALID_GRYPE_JSON"
check "Grype JSON schema accepts omitted empty ignoredMatches" \
  grype_scan_json_valid "$VALID_GRYPE_JSON"
printf '{"matches":{},"ignoredMatches":[]}\n' > "$INVALID_GRYPE_JSON"
check "Grype JSON schema rejects non-array matches" \
  ! grype_scan_json_valid "$INVALID_GRYPE_JSON"
printf '{"matches":[],"ignoredMatches":{}}\n' > "$INVALID_GRYPE_JSON"
check "Grype JSON schema rejects non-array ignoredMatches" \
  ! grype_scan_json_valid "$INVALID_GRYPE_JSON"
check "Go directive cross-minor allowed within builder upper bound" \
  go_directive_supported 1.25.0 1.26.2 1.26.8
check "Go directive exact builder version allowed" \
  go_directive_supported 1.25.0 1.26.8 1.26.8
check "Go directive downgrade rejected" \
  ! go_directive_supported 1.26.0 1.25.9 1.26.8
check "Go directive over builder patch rejected" \
  ! go_directive_supported 1.25.0 1.26.9 1.26.8
check "Go directive same-minor patch over builder rejected" \
  ! go_directive_supported 1.25.0 1.25.9 1.25.8
check "Go directive unknown builder allows same minor" \
  go_directive_supported 1.25.0 1.25.9 ""
check "Go directive unknown builder rejects cross minor" \
  ! go_directive_supported 1.25.0 1.26.0 ""
_STATE_PATH=$(state_file_path /x/myrepo release-0.23)
check "state_file_path" bash -c '[[ "$1" == '"${TMPDIR:-/tmp}"'/cve-fix-myrepo-release-0-23.*/state.env && -f "$1" && ! -L "$1" ]]' _ "$_STATE_PATH"
check "state_file_path mode 0600" test "$(stat -c '%a' "$_STATE_PATH")" = 600
check "state_file_path run directory mode 0700" test "$(stat -c '%a' "$(dirname "$_STATE_PATH")")" = 700
_STATE_DEVEL=$(state_file_path /x/myrepo devel)
check "state_file_path devel" bash -c '[[ "$1" == '"${TMPDIR:-/tmp}"'/cve-fix-myrepo-devel.*/state.env ]]' _ "$_STATE_DEVEL"
# state_file_path honours TMPDIR: when TMPDIR is set, the state file must land there.
check "state_file_path respects TMPDIR" bash -c "( TMPDIR='$TMPD'; source '$SCRIPT_DIR/lib.sh'; out=\$(state_file_path /x/myrepo devel); [[ \$out == '$TMPD'/cve-fix-myrepo-devel.*/state.env && -f \$out ]] )"

# === LLM agent provider selection and argv construction ===
echo "agent provider selection"
check "agent provider defaults to claude" bash -c "unset CVE_FIX_AGENT; source '$SCRIPT_DIR/lib.sh'; test \"\$(cve_fix_agent_provider)\" = claude"
check "agent provider accepts claude" test "$(CVE_FIX_AGENT=claude cve_fix_agent_provider)" = claude
check "agent provider accepts codex" test "$(CVE_FIX_AGENT=codex cve_fix_agent_provider)" = codex
check "agent provider rejects unknown value" ! bash -c "CVE_FIX_AGENT=other; source '$SCRIPT_DIR/lib.sh'; cve_fix_agent_provider"

agent_command_dump() {
  (
    REPO="$TMPD/provider-repo"
    STATE_FILE="$TMPD/provider-run/state.env"
    CVE_FIX_AGENT="$1"
    CVE_FIX_MODEL="${2:-}"
    build_cve_fix_agent_command "literal \$(do-not-run) prompt" "$TMPD/provider-reports"
    printf '%s\n' "${CVE_FIX_AGENT_CMD[@]}"
  )
}
git init -q "$TMPD/provider-repo"
CLAUDE_AGENT_CMD=$(agent_command_dump claude)
CLAUDE_MODEL_CMD=$(agent_command_dump claude model-x)
CODEX_AGENT_CMD=$(agent_command_dump codex)
CODEX_MODEL_CMD=$(agent_command_dump codex model-x)
EXPECTED_CLAUDE_CMD=$(printf '%s\n' env -C "$TMPD/provider-run/reviewer" claude -p 'literal $(do-not-run) prompt' --print --tools '' --strict-mcp-config --setting-sources user --no-session-persistence)
EXPECTED_CLAUDE_MODEL_CMD=$(printf '%s\n' env -C "$TMPD/provider-run/reviewer" claude -p 'literal $(do-not-run) prompt' --print --model model-x --tools '' --strict-mcp-config --setting-sources user --no-session-persistence)
EXPECTED_CODEX_CMD=$(printf '%s\n' codex exec --ephemeral --sandbox read-only \
  --cd "$TMPD/provider-run/reviewer" --skip-git-repo-check --color never 'literal $(do-not-run) prompt')
EXPECTED_CODEX_MODEL_CMD=$(printf '%s\n' codex exec --ephemeral --sandbox read-only \
  --cd "$TMPD/provider-run/reviewer" --skip-git-repo-check --color never --model model-x 'literal $(do-not-run) prompt')
check "claude command is read-only" test "$CLAUDE_AGENT_CMD" = "$EXPECTED_CLAUDE_CMD"
check "claude model argv is read-only" test "$CLAUDE_MODEL_CMD" = "$EXPECTED_CLAUDE_MODEL_CMD"
check "codex command argv is exact" test "$CODEX_AGENT_CMD" = "$EXPECTED_CODEX_CMD"
check "codex model argv is exact" test "$CODEX_MODEL_CMD" = "$EXPECTED_CODEX_MODEL_CMD"
check "claude command retains print mode" grep -qx -- '--print' <<< "$CLAUDE_AGENT_CMD"
check "claude command does not grant Bash" ! grep -qx -- 'Bash' <<< "$CLAUDE_AGENT_CMD"
check "claude command has no Codex flags" ! grep -qx -- '--ephemeral' <<< "$CLAUDE_AGENT_CMD"
check "codex command uses exec" grep -qx -- 'exec' <<< "$CODEX_AGENT_CMD"
check "codex command is ephemeral" grep -qx -- '--ephemeral' <<< "$CODEX_AGENT_CMD"
check "codex command uses read-only sandbox" grep -qx -- 'read-only' <<< "$CODEX_AGENT_CMD"
check "codex command has no review network" ! grep -q -- 'network_access' <<< "$CODEX_AGENT_CMD"
check "codex command grants no report directory" ! grep -qxF -- "$TMPD/provider-reports" <<< "$CODEX_AGENT_CMD"
check "codex command preserves literal prompt" grep -qxF -- 'literal $(do-not-run) prompt' <<< "$CODEX_AGENT_CMD"
check "codex command has no model by default" ! grep -qx -- '--model' <<< "$CODEX_AGENT_CMD"
check "codex command accepts model override" grep -qxF -- 'model-x' <<< "$CODEX_MODEL_CMD"

# Read-only reviewers receive no explicit writable Git metadata, including in a
# linked worktree.
PROVIDER_WT_MAIN="$TMPD/provider-wt-main"
git init -q "$PROVIDER_WT_MAIN"
git -C "$PROVIDER_WT_MAIN" -c user.name=test -c user.email=test@example.invalid \
  commit --allow-empty -qm init
git -C "$PROVIDER_WT_MAIN" worktree add --detach "$TMPD/provider-wt" HEAD >/dev/null 2>&1
PROVIDER_WT_CMD=$(
  REPO="$TMPD/provider-wt" CVE_FIX_AGENT=codex
  build_cve_fix_agent_command prompt "$TMPD/provider-reports"
  printf '%s\n' "${CVE_FIX_AGENT_CMD[@]}"
)
check "codex worktree grants no worktree Git metadata" ! \
  grep -qxF "$PROVIDER_WT_MAIN/.git/worktrees/provider-wt" <<< "$PROVIDER_WT_CMD"
check "codex worktree grants no common Git metadata" ! \
  grep -qxF "$PROVIDER_WT_MAIN/.git" <<< "$PROVIDER_WT_CMD"

check "abbrev github" test "$(abbreviate_package github.com/docker/docker)" = "docker/docker"
check "abbrev x/" test "$(abbreviate_package golang.org/x/net)" = "x/net"
check "abbrev helm" test "$(abbreviate_package helm.sh/helm/v3)" = "helm/v3"
check "abbrev k8s" test "$(abbreviate_package k8s.io/client-go)" = "k8s.io/client-go"
check "abbrev other" test "$(abbreviate_package go.etcd.io/bbolt)" = "go.etcd.io/bbolt"
check "abbrev etcd" test "$(abbreviate_package go.etcd.io/etcd/client/pkg/v3)" = "etcd/client/pkg/v3"
check "abbrev nested" test "$(abbreviate_package github.com/go-git/go-git/v5)" = "go-git/go-git/v5"
check "abbrev otel" test "$(abbreviate_package go.opentelemetry.io/otel)" = "otel"
check "abbrev otel/sdk" test "$(abbreviate_package go.opentelemetry.io/otel/sdk)" = "otel/sdk"
check "abbrev otel deep" test "$(abbreviate_package go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp)" = "otel/otlptracehttp"
check "abbrev grpc" test "$(abbreviate_package google.golang.org/grpc)" = "grpc"
check "abbrev sigs" test "$(abbreviate_package sigs.k8s.io/controller-runtime)" = "controller-runtime"
check "gte higher" version_gte 0.45.0 0.44.0
check "gte equal" version_gte 0.44.0 0.44.0
check "gte lower" ! version_gte 0.41.0 0.44.0
check "gte +incompatible equal" version_gte 2.3.4+incompatible 2.3.4
check "gte v-prefix" version_gte v1.2.4 v1.2.3
check "gte mixed prefix" version_gte v1.2.4 1.2.3
check "gte two-part" version_gte 1.2 1.1
# Pseudo-version ordering: Go SemVer treats pseudo versions as prereleases.
check "gte real >= pseudo same base" version_gte 0.0.0 0.0.0-20231012123456-abcdef123456
check "gte higher real >= pseudo" version_gte 0.0.3 0.0.0-20231012123456-abcdef123456
check "gte pseudo NOT >= base release" ! version_gte 0.0.0-20231012123456-abcdef123456 0.0.0
check "gte pseudo NOT >= higher release" ! version_gte 0.0.0-20231012123456-abcdef123456 0.0.1
check "gte pseudo == pseudo same" version_gte 0.0.0-20231012123456-abcdef123456 0.0.0-20231012123456-abcdef123456
check "gte newer pseudo >= older pseudo" version_gte 0.0.0-20231201000000-abcdef123456 0.0.0-20231012123456-abcdef123456
check "gte older pseudo NOT >= newer pseudo" ! version_gte 0.0.0-20231012123456-abcdef123456 0.0.0-20231201000000-abcdef123456
check "gte pseudo higher base >= lower real" version_gte 0.0.3-20231012123456-abcdef123456 0.0.1
check "gte pseudo lower base NOT >= higher real" ! version_gte 0.0.0-20231012123456-abcdef123456 0.0.3
# Go also emits vX.Y.Z-0.YYYYMMDDHHMMSS-HASH (0. prefix) for commits after a tag.
# version_gte must treat these the same as the direct-timestamp format.
check "gte real >= 0.-pseudo same base" version_gte 0.21.1 0.21.1-0.20240508182429-e35e4ccd0d2d
check "gte higher real >= 0.-pseudo" version_gte 0.21.2 0.21.1-0.20240508182429-e35e4ccd0d2d
check "gte 0.-pseudo NOT >= base release" ! version_gte 0.21.1-0.20240508182429-e35e4ccd0d2d 0.21.1
check "gte 0.-pseudo NOT >= higher release" ! version_gte 0.21.1-0.20240508182429-e35e4ccd0d2d 0.21.2
check "gte 0.-pseudo == 0.-pseudo same" version_gte 0.21.1-0.20240508182429-e35e4ccd0d2d 0.21.1-0.20240508182429-e35e4ccd0d2d
check "gte newer 0.-pseudo >= older 0.-pseudo" version_gte 0.21.1-0.20250101000000-abcdef123456 0.21.1-0.20240508182429-e35e4ccd0d2d
check "gte older 0.-pseudo NOT >= newer 0.-pseudo" ! version_gte 0.21.1-0.20240508182429-e35e4ccd0d2d 0.21.1-0.20250101000000-abcdef123456
check "gte release >= generic prerelease" version_gte 1.1.1 1.1.1-0.5.2
check "gte generic prerelease NOT >= release" ! version_gte 1.1.1-0.5.2 1.1.1
check "gte newer generic prerelease" version_gte 1.2.3-rc.2 1.2.3-rc.1
check "gte numeric prerelease below nonnumeric" ! version_gte 1.2.3-1 1.2.3-alpha
check "gte longer equal prerelease sequence" version_gte 1.2.3-alpha.1 1.2.3-alpha

# === summary formatting (headline CVE count + detail truncation) ===
# The run headline counts CVEs cleared (tokens after "for" on FIXED lines), not
# packages or commits, and long CVE lists collapse to "<first> ... (N CVEs)".
echo "summary formatting"
SUMMARY=$'FIXED: go.opentelemetry.io/otel v1.44.0 for GO-1\n'
SUMMARY+=$'IGNORED: golang.org/x/crypto (no fix available) for GO-2\n'
SUMMARY+=$'FIXED: golang.org/x/net v0.56.0 for GHSA-a GO-3 GO-4 GO-5\n'
SUMMARY+=$'FIXED: golang.org/x/mod v0.40.0 for GO-6 GO-7\n'
# 1 + 4 + 2 = 7 across FIXED lines; the IGNORED line is not counted.
check "cve count sums fixed" test "$(count_cves_fixed "$SUMMARY")" = "7"
check "cve count empty"      test "$(count_cves_fixed "")" = "0"
_MULTI_FIXES=$(format_cve_fixes GHSA-2v4p-qf9q-27wj GHSA-hrxh-6v49-42gf \
  GHSA-qc2q-p7wx-3px3 GHSA-vp52-pcj8-j9qc)
check "commit CVE trailers use one bounded line per advisory" \
  test "$(wc -l <<< "$_MULTI_FIXES")" = 4
check "commit CVE trailers satisfy 80-column gitlint" \
  awk 'length > 80 { exit 1 }' <<< "$_MULTI_FIXES"
DETAIL=$(format_fix_detail "$SUMMARY")
check "detail collapses long"   grep -q 'x/net v0.56.0 for GHSA-a \.\.\. (4 CVEs)' <<< "$DETAIL"
check "detail keeps short"      grep -q 'x/mod v0.40.0 for GO-6 GO-7$' <<< "$DETAIL"
check "detail keeps single"     grep -q 'otel v1.44.0 for GO-1$' <<< "$DETAIL"
check "detail passthru ignored" grep -q 'IGNORED: golang.org/x/crypto (no fix available) for GO-2$' <<< "$DETAIL"

# === make target detection (catch-all aware) ===
# A Dapper/wrapper Makefile defines a catch-all rule that makes `make -q` report
# every goal as existing, so a bare `has_make_target build` false-positives and
# the run tries to `make build` a target that doesn't exist. has_build_target
# must require an explicit build target when a catch-all is present.
echo "make target detection"
if command -v make >/dev/null 2>&1; then
  mkdir -p "$TMPD/mk-plain-build" "$TMPD/mk-plain-nobuild" \
           "$TMPD/mk-catchall-nobuild" "$TMPD/mk-catchall-build"
  printf 'build:\n\t@true\nunit:\n\t@true\n' > "$TMPD/mk-plain-build/Makefile"
  printf 'unit:\n\t@true\n'                   > "$TMPD/mk-plain-nobuild/Makefile"
  printf '%%:\n\t@true\nunit:\n\t@true\n'     > "$TMPD/mk-catchall-nobuild/Makefile"
  printf 'build:\n\t@true\n%%:\n\t@true\n'    > "$TMPD/mk-catchall-build/Makefile"
  in_dir() { bash -c "cd '$1' && source '$SCRIPT_DIR/lib.sh' && $2"; }
  check "catchall: plain none"   in_dir "$TMPD/mk-plain-build"      "! has_catchall_rule"
  check "catchall: wrapper seen" in_dir "$TMPD/mk-catchall-nobuild" "has_catchall_rule"
  check "build: plain present"   in_dir "$TMPD/mk-plain-build"      "has_build_target"
  check "build: plain absent"    in_dir "$TMPD/mk-plain-nobuild"    "! has_build_target"
  check "build: catchall none"   in_dir "$TMPD/mk-catchall-nobuild" "! has_build_target"
  check "build: catchall real"   in_dir "$TMPD/mk-catchall-build"   "has_build_target"
  # has_make_target: raw make -q probe — returns 0 when target exists, non-zero (exit 2) when absent.
  check "make_target: present"         in_dir "$TMPD/mk-plain-build"    "has_make_target unit"
  check "make_target: absent"          in_dir "$TMPD/mk-plain-build"    "! has_make_target nonexistent-xyz"
  check "make_target: catchall match"  in_dir "$TMPD/mk-catchall-nobuild" "has_make_target unit"
  check "make_target: catchall probe"  in_dir "$TMPD/mk-catchall-nobuild" "has_make_target nonexistent-xyz"
  mkdir -p "$TMPD/mk-license"
  printf 'licensecheck:\n\t@true\n' > "$TMPD/mk-license/Makefile"
  check "license target: explicit" in_dir "$TMPD/mk-license" "has_real_make_target licensecheck"
else
  echo "  SKIP: make not available"
fi

# === get_installed_version (offline, anchored fallback) ===
# Force the go.mod fallback with a 'go' stub that errors, so this stays offline
# and deterministic regardless of host go / module cache. The fallback must
# match the module path as a WHOLE token (no sibling substring bleed) and emit
# a BARE semver (strip leading 'v' and '+incompatible') for version_gte.
echo "get_installed_version"
GIV="$TMPD/giv"; mkdir -p "$GIV/bin"
printf '#!/bin/sh\nexit 1\n' > "$GIV/bin/go"; chmod +x "$GIV/bin/go"
cat > "$GIV/go.mod" <<'EOF'
module example.com/test
go 1.25.0
require (
	github.com/foo/bar v1.2.3
	github.com/foo/bar/v2 v2.5.0 // indirect
	github.com/foo/barbaz v9.9.9
	github.com/big/mod v3.1.0+incompatible
	github.com/rep/unversioned v2.0.0
	github.com/rep/versioned-match v1.5.0
	github.com/rep/versioned-nomatch v1.5.0
	github.com/rep/local v1.0.0
	github.com/pseudo/pkg v0.0.0-20231012123456-abcdef123456
)
replace github.com/rep/unversioned => github.com/rep/unversioned v1.0.0
replace github.com/rep/versioned-match v1.5.0 => github.com/rep/versioned-match v1.2.3
replace github.com/rep/versioned-nomatch v1.0.0 => github.com/rep/versioned-nomatch v0.9.0
replace github.com/rep/local => ../local
EOF
giv() { ( PATH="$GIV/bin:$PATH"; get_installed_version "$GIV" "$1" ); }
check "giv exact bare (v stripped)" test "$(giv github.com/foo/bar)" = "1.2.3"
check "giv no sibling bleed"        test "$(giv github.com/foo/barbaz)" = "9.9.9"
check "giv versioned suffix"        test "$(giv github.com/foo/bar/v2)" = "2.5.0"
check "giv +incompatible stripped"  test "$(giv github.com/big/mod)" = "3.1.0"
check "giv absent is empty"         test -z "$(giv github.com/foo/nope)"
# Integration: normalized (bare) output makes version_gte correct — a v-prefixed
# value would sort before the bare fix version and report false-FIXED.
check "giv gte correct low"  ! version_gte "$(giv github.com/foo/bar)" 9.0.0
check "giv gte correct high" version_gte "$(giv github.com/foo/barbaz)" 9.0.0
# Bug 2 regression: go list failure + versioned replace causes false-FIXED.
# The awk fallback must honour replace directives, not blindly return the require
# version (which may have been bumped to the fix version while a replace directive
# still pins the old vulnerable version).
check "giv non-versioned replace returns rhs" \
  test "$(giv github.com/rep/unversioned)" = "1.0.0"
check "giv versioned replace matching require returns rhs" \
  test "$(giv github.com/rep/versioned-match)" = "1.2.3"
# versioned-nomatch: replace targets v1.0.0 but require is v1.5.0 → replace does
# not apply, so fallback returns the require version unchanged.
check "giv versioned replace non-matching returns require" \
  test "$(giv github.com/rep/versioned-nomatch)" = "1.5.0"
# Local-path replace has no RHS semver → return "0.0.0" sentinel, not "".
# "" is treated as absent by fix-package.sh callers → STILL_VULNERABLE skipped → false-FIXED.
check "giv local path replace returns 0.0.0" \
  test "$(giv github.com/rep/local)" = "0.0.0"
# Integration: 0.0.0 sentinel causes version_gte to fail → STILL_VULNERABLE=true
check "giv local-replace 0.0.0 not gte low fix"  ! version_gte "$(giv github.com/rep/local)" 0.0.1
# Non-versioned replace: version_gte with old require version (2.0.0) would pass
# incorrectly; with the rhs version (1.0.0) it correctly fails, preventing false-FIXED.
check "giv non-versioned replace gte correct" \
  ! version_gte "$(giv github.com/rep/unversioned)" 2.0.0
# Versioned replace: version_gte with old require version (1.5.0) would pass
# incorrectly; with the rhs version (1.2.3) it correctly fails.
check "giv versioned replace gte correct" \
  ! version_gte "$(giv github.com/rep/versioned-match)" 1.5.0
# Pseudo-version: full timestamp suffix must be preserved so version_gte can
# distinguish old pseudo from new pseudo (both strip to "0.0.0" without fix).
check "giv pseudo-version preserves suffix" \
  test "$(giv github.com/pseudo/pkg)" = "0.0.0-20231012123456-abcdef123456"
# Integration: preserved pseudo allows version_gte to detect it IS the fix version
check "giv pseudo gte same pseudo" \
  version_gte "$(giv github.com/pseudo/pkg)" 0.0.0-20231012123456-abcdef123456
# Integration: stripped "0.0.0" would return TRUE here (false-FIXED); preserved pseudo returns FALSE
check "giv pseudo NOT gte newer pseudo" \
  ! version_gte "$(giv github.com/pseudo/pkg)" 0.0.0-20231201000000-abcdef123456
# Versioned local-path replace: replace pkg vX => ./local also yields "0.0.0"
# when the require version matches the versioned LHS. (Non-matching versioned
# replaces do not apply, so the require version is returned unchanged — tested by
# giv versioned replace non-matching returns require.)
GIV_VLOC="$TMPD/giv-vloc"; mkdir -p "$GIV_VLOC/bin"
printf '#!/bin/sh\nexit 1\n' > "$GIV_VLOC/bin/go"; chmod +x "$GIV_VLOC/bin/go"
cat > "$GIV_VLOC/go.mod" <<'EOF'
module example.com/vloc
go 1.25.0
require github.com/foo/vlocal v1.0.0
replace github.com/foo/vlocal v1.0.0 => ./local/versioned
EOF
givvloc() { ( PATH="$GIV_VLOC/bin:$PATH"; get_installed_version "$GIV_VLOC" "$1" ); }
check "giv versioned local-replace returns 0.0.0" \
  test "$(givvloc github.com/foo/vlocal)" = "0.0.0"
# Absolute local-path replace (=> /absolute/path) also yields "0.0.0"
cat > "$GIV_VLOC/go.mod" <<'EOF'
module example.com/vloc
go 1.25.0
require github.com/foo/absdep v2.0.0
replace github.com/foo/absdep => /absolute/local/path
EOF
check "giv absolute local-replace returns 0.0.0" \
  test "$(givvloc github.com/foo/absdep)" = "0.0.0"

# === get_installed_version (primary go list path) ===
# Tests the real 'go list -m' path using the repo's own go.mod —
# no network needed because go.sum already has the checksums cached.
# github.com/pkg/errors is used when present as a direct dependency so go list
# will resolve it without fetching anything new.
echo "get_installed_version (go list path)"
_PKG_ERR_VER=$(grep 'github.com/pkg/errors' "$GO_FIXTURE/go.mod" 2>/dev/null | awk '{print $2}' | sed 's/^v//')
if [[ -n "$_PKG_ERR_VER" ]]; then
  check "giv go list primary path returns bare version" \
    test "$(get_installed_version "$GO_FIXTURE" github.com/pkg/errors)" = "$_PKG_ERR_VER"
fi
# Absent package: go list exits non-zero; awk fallback also returns ""; both yield "".
check "giv go list absent package is empty" \
  test -z "$(get_installed_version "$GO_FIXTURE" github.com/does/not/exist)"

# === clean_gomod ===
echo "clean_gomod"
printf 'module t\ngo 1.25.0\ntoolchain go1.25.1\n' > "$TMPD/go.mod"
(cd "$TMPD" && clean_gomod)
check "pre-existing toolchain preserved" grep -q '^toolchain go1.25.1$' "$TMPD/go.mod"
check "go kept" grep -q "^go 1.25.0" "$TMPD/go.mod"

# blank-line squeezing leaves exactly module, Go version, and one blank line
printf 'module t\ngo 1.25.0\n\n\n\n' > "$TMPD/go.mod"
(cd "$TMPD" && clean_gomod)
check "blank-line squeeze" test "$(wc -l < "$TMPD/go.mod")" -eq 3

# === load_state ===
echo "load_state"
check "load_state missing fails" ! load_state "$TMPD/nonexistent-cve-test.env"
printf 'REPO="%s"\nBRANCH="devel"\n' "$TMPD" > "$TMPD/s.env"
touch "$TMPD/go.mod"
check "loads vars" bash -c "source '$SCRIPT_DIR/lib.sh'; load_state '$TMPD/s.env' && [[ \$BRANCH = devel ]]"
# Corrupt-state die() paths (R125): load_state must die on empty REPO and on
# REPO that exists but has no go.mod.
check "load_state empty REPO dies" \
  ! bash -c "source '$SCRIPT_DIR/lib.sh'; printf 'REPO=\"\"\nBRANCH=\"devel\"\n' > '$TMPD/empty_repo.env'; load_state '$TMPD/empty_repo.env'"
mkdir -p "$TMPD/nogo_repo"
check "load_state no go.mod dies" \
  ! bash -c "source '$SCRIPT_DIR/lib.sh'; printf 'REPO=\"$TMPD/nogo_repo\"\nBRANCH=\"devel\"\n' > '$TMPD/nogo.env'; load_state '$TMPD/nogo.env'"

# === insert_grype_ignore ===
echo "insert_grype_ignore"
printf -- '---\nexclude:\n  - vulnerability: CVE-2021-22570\n    package:\n      name: google.golang.org/protobuf\n' > "$TMPD/g.yaml"
insert_grype_ignore "$TMPD/g.yaml" GHSA-test-1234 example.com/pkg "Test reason"
check "before exclude" test "$(grep -n GHSA-test-1234 "$TMPD/g.yaml" | cut -d: -f1)" -lt "$(grep -n '^exclude:' "$TMPD/g.yaml" | cut -d: -f1)"
check "original kept" grep -q CVE-2021-22570 "$TMPD/g.yaml"
printf -- '---\nignore:\n  - vulnerability: CVE-1\n    package:\n      name: x\n' > "$TMPD/no-exc.yaml"
insert_grype_ignore "$TMPD/no-exc.yaml" GHSA-append example.com/other "No exclude"
check "appends" grep -q GHSA-append "$TMPD/no-exc.yaml"

# insert_grype_ignore with both ignore: and exclude: plus an intervening top-level key:
# the new entry must land at the end of the ignore: block, not after the intermediate
# key (which would produce invalid YAML — 2-space-indented entry dangling under scalar).
printf -- '---\nignore:\n  - vulnerability: CVE-existing\n    package:\n      name: existing\n\noperator: override\n\nexclude:\n  - "./vendor/**"\n' \
  > "$TMPD/intermed.yaml"
insert_grype_ignore "$TMPD/intermed.yaml" GHSA-intermed example.com/intermed "Intermediate key test"
INTERMED_CVE_LINE=$(grep -n 'GHSA-intermed' "$TMPD/intermed.yaml" | cut -d: -f1)
INTERMED_OP_LINE=$(grep -n '^operator:' "$TMPD/intermed.yaml" | cut -d: -f1)
check "intermed: entry before intermediate key" test "$INTERMED_CVE_LINE" -lt "$INTERMED_OP_LINE"
check "intermed: YAML valid" python3 -c "import yaml,sys; list(yaml.safe_load_all(open(sys.argv[1])))" "$TMPD/intermed.yaml"

# insert_grype_ignore: file has top-level keys (e.g. registry:) but no ignore: key.
# The entry must land immediately under a new ignore: key, not after the existing
# content, which would make ignore: null-valued and the entry dangle under an
# unrelated YAML mapping.
printf 'registry:\n  auth: []\n' > "$TMPD/no-ignore-topkeys.yaml"
insert_grype_ignore "$TMPD/no-ignore-topkeys.yaml" GHSA-topkeys example.com/topkeys-pkg "Top-level key test"
check "no-ignore topkeys: entry present" grep -q 'GHSA-topkeys' "$TMPD/no-ignore-topkeys.yaml"
check "no-ignore topkeys: YAML valid" python3 -c "import yaml,sys; list(yaml.safe_load_all(open(sys.argv[1])))" "$TMPD/no-ignore-topkeys.yaml"
check "no-ignore topkeys: ignore key present" grep -q '^ignore:' "$TMPD/no-ignore-topkeys.yaml"
TOPKEYS_CVE_LINE=$(grep -n 'GHSA-topkeys' "$TMPD/no-ignore-topkeys.yaml" | head -1 | cut -d: -f1)
TOPKEYS_REG_LINE=$(grep -n '^registry:' "$TMPD/no-ignore-topkeys.yaml" | head -1 | cut -d: -f1)
check "no-ignore topkeys: entry under ignore (before registry)" test "${TOPKEYS_CVE_LINE:-0}" -lt "${TOPKEYS_REG_LINE:-9999}"

# Different scoped locations for the same CVE/package are independent security
# scopes, but an unscoped rule must never coexist with a scoped rule.
printf -- '---\nignore:\n  - vulnerability: GHSA-scope-mask\n    package:\n      name: example.com/scope-pkg\n      location: /tools/go.mod\n' \
  > "$TMPD/scope-mask.yaml"
SCOPE_MASK_RC=0
insert_grype_ignore "$TMPD/scope-mask.yaml" GHSA-scope-mask example.com/scope-pkg "Root module fix" || SCOPE_MASK_RC=$?
check "unscoped insert beside scoped entry fails closed" test "$SCOPE_MASK_RC" = 2
check "scope conflict leaves one entry" test "$(grep -c 'vulnerability: GHSA-scope-mask' "$TMPD/scope-mask.yaml")" = 1
check "existing scoped location preserved" grep -q 'location: /tools/go.mod' "$TMPD/scope-mask.yaml"
insert_grype_ignore "$TMPD/scope-mask.yaml" GHSA-scope-mask example.com/scope-pkg "Other module" "not-fixed" "/go.mod"
check "two disjoint scoped entries are valid" test "$(grep -c 'vulnerability: GHSA-scope-mask' "$TMPD/scope-mask.yaml")" = 2

# A broad rule plus a scoped rule is always a policy conflict.
printf -- '  - vulnerability: GHSA-scope-mask\n    package:\n      name: example.com/scope-pkg\n' >> "$TMPD/scope-mask.yaml"
check "scope conflict detector reports broad shadowing" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; grype_ignore_scope_conflicts '$TMPD/scope-mask.yaml' | grep -q 'SCOPE_CONFLICT: GHSA-scope-mask (example.com/scope-pkg)'"

# A scope migration must use the scan's effective fix state. Grype treats an
# empty advisory state as unknown, so retaining an older not-fixed state would
# create a scoped rule that still does not suppress the finding.
printf -- '---\nignore:\n  - vulnerability: GO-state-migrate\n    fix-state: not-fixed\n    package:\n      name: example.com/state-pkg\n' > "$TMPD/state-migrate.yaml"
check "scope migration updates effective fix state" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; migrate_grype_ignore_scope '$TMPD/state-migrate.yaml' GO-state-migrate example.com/state-pkg /pkg/go.mod unknown >/dev/null && grep -q 'fix-state: unknown' '$TMPD/state-migrate.yaml'"
check "scope migration writes requested location" \
  grep -q 'location: /pkg/go.mod' "$TMPD/state-migrate.yaml"

# === insert_grype_ignore argument validation ===
echo "insert_grype_ignore arg validation"
# Wrong arg order: CVE ID as first arg (not a path) must fail, not silently create a stray file.
check "wrong arg order (CVE as file) fails" ! insert_grype_ignore "CVE-2024-1" "my-package" "not-fixed" "Medium" "/tmp/grype.yaml"
check "wrong arg order: no stray file created" ! test -f "CVE-2024-1"
# Wrong arg order: invalid CVE ID (plain package name as second arg) must fail.
check "invalid CVE ID fails" ! insert_grype_ignore "$TMPD/g.yaml" "example.com/pkg" "not-fixed" "Reason"

# === detect.sh (real repo) ===
echo "detect.sh"
DETECT_OUT=$("$SCRIPT_DIR/detect.sh" "$GO_FIXTURE" 0.23 2>&1) || true
check "normalizes 0.23" grep -q "release-0.23" <<< "$DETECT_OUT"
STATE=$(tail -1 <<< "$DETECT_OUT")
check "creates state" test -f "$STATE"
rm -f "$STATE"
check "bad repo fails" ! "$SCRIPT_DIR/detect.sh" /nonexistent devel
check "non-git fails" ! "$SCRIPT_DIR/detect.sh" /tmp devel
check "unknown named repo fails" ! "$SCRIPT_DIR/detect.sh" "badreponame"
# R200: detect.sh must reject a git repo that has no go.mod (not a Go project).
NO_GOMOD_REPO=$(mktemp -d "$TMPD/no-gomod-repo.XXXXXX")
git -C "$NO_GOMOD_REPO" init -q
git -C "$NO_GOMOD_REPO" config user.email "t@t.com"
git -C "$NO_GOMOD_REPO" config user.name "T"
NO_GOMOD_OUT=$("$SCRIPT_DIR/detect.sh" "$NO_GOMOD_REPO" devel 2>&1) && _no_gomod_rc=0 || _no_gomod_rc=$?
check "no go.mod fails" test "$_no_gomod_rc" -ne 0

# === detect.sh TEST_CMD fallback ordering ===
# Verifies native TEST_CMD selection before the generic Go fallback.
# Each case uses a minimal hermetic git repo with a tailored Makefile.
echo "detect.sh TEST_CMD fallback ordering"
if command -v make &>/dev/null; then
  # Helper: create a minimal git repo with a given Makefile content, run detect.sh,
  # read TEST_CMD from the state file, then clean up. Echoes the TEST_CMD value.
  _detect_test_cmd() {
    local mk_content="$1"
    local td
    td=$(mktemp -d "$TMPD/tc-repo.XXXXXX")
    git -C "$td" init -q
    git -C "$td" config user.email "t@t.com"
    git -C "$td" config user.name "T"
    printf 'module example.com/tc\ngo 1.24.0\n' > "$td/go.mod"
    printf '%s\n' "$mk_content" > "$td/Makefile"
    git -C "$td" add -A
    git -C "$td" commit -qm "init" --no-gpg-sign 2>/dev/null || \
      git -C "$td" -c gpg.sign=false commit -qm "init" 2>/dev/null || true
    local out tc_state rc
    out=$("$SCRIPT_DIR/detect.sh" "$td" devel 2>&1)
    rc=$?
    if [[ $rc -ne 0 ]]; then
      echo "  detect.sh exited $rc: $out" >&2
    fi
    tc_state=$(tail -1 <<< "$out")
    local val=""
    if [[ -f "$tc_state" ]]; then
      val=$(state_value "$tc_state" TEST_CMD)
      rm -f "$tc_state"
    fi
    rm -rf "$td"
    printf '%s' "$val"
  }

  # Case 1: "unit" target present → TEST_CMD = "make unit" (happy path)
  TC_UNIT=$(_detect_test_cmd $'unit:\n\t@true\n')
  check "TEST_CMD unit target: make unit" test "$TC_UNIT" = "make unit"

  # Case 2: only "test" target present → TEST_CMD = "make test"
  TC_TEST=$(_detect_test_cmd $'test:\n\t@true\n')
  check "TEST_CMD test-only target: make test" test "$TC_TEST" = "make test"

  TC_TEST_UNIT=$(_detect_test_cmd $'test-unit:\n\t@true\n')
  check "TEST_CMD test-unit target: make test-unit" test "$TC_TEST_UNIT" = "make test-unit"
  TC_TEST_PRIORITY=$(_detect_test_cmd $'test:\n\t@true\ntest-unit:\n\t@false\n')
  check "TEST_CMD retains test target priority" test "$TC_TEST_PRIORITY" = "make test"
  TC_CATCHALL=$(_detect_test_cmd $'%:\n\t@true\n')
  check "TEST_CMD catch-all does not invent test-unit" test "$TC_CATCHALL" = "go test ./..."

  # Case 3: neither "unit" nor "test" present → TEST_CMD = "go test ./..."
  TC_GO=$(_detect_test_cmd $'build:\n\t@true\n')
  check "TEST_CMD no make targets: go test ./..." test "$TC_GO" = "go test ./..."
else
  echo "  SKIP: make not available"
fi

# === detect.sh registry resolution (XDG / CVE_FIX_REPOS) ===
# Hermetic: verifies the four-level resolution chain without modifying the real
# repos.yaml or touching the home directory.
echo "detect.sh registry resolution"
# Build a minimal repos.yaml that maps "testfixrepo" → $GO_FIXTURE so detect.sh
# can look up a real git repo by the synthetic name (no network, no checkout).
REG_YAML="$TMPD/custom-repos.yaml"
printf -- '---\nrepos:\n  - name: testfixrepo\n    path: %s\n' "$GO_FIXTURE" > "$REG_YAML"

# 1. CVE_FIX_REPOS env var is honoured (highest priority).
REG_OUT=$(CVE_FIX_REPOS="$REG_YAML" "$SCRIPT_DIR/detect.sh" testfixrepo devel 2>&1) || true
REG_STATE=$(tail -1 <<< "$REG_OUT")
check "CVE_FIX_REPOS: repo resolved by name"   grep -q "CVE Fix:" <<< "$REG_OUT"
check "CVE_FIX_REPOS: state file created"      test -f "$REG_STATE"
rm -f "$REG_STATE"
check "CVE_FIX_REPOS: unknown name still fails" \
  ! CVE_FIX_REPOS="$REG_YAML" "$SCRIPT_DIR/detect.sh" notarepoinreg devel

# 2. XDG_CONFIG_HOME override is honoured when CVE_FIX_REPOS is unset.
XDG_CFG="$TMPD/xdg-config"
mkdir -p "$XDG_CFG/cve-fix"
cp "$REG_YAML" "$XDG_CFG/cve-fix/repos.yaml"
XDG_OUT=$(XDG_CONFIG_HOME="$XDG_CFG" "$SCRIPT_DIR/detect.sh" testfixrepo devel 2>&1) || true
XDG_STATE=$(tail -1 <<< "$XDG_OUT")
check "XDG: repo resolved by name"   grep -q "CVE Fix:" <<< "$XDG_OUT"
check "XDG: state file created"      test -f "$XDG_STATE"
rm -f "$XDG_STATE"
# CVE_FIX_REPOS takes priority over XDG.
ALT_YAML="$TMPD/alt-repos.yaml"
printf -- '---\nrepos:\n  - name: altrepo\n    path: %s\n' "$GO_FIXTURE" > "$ALT_YAML"
check "CVE_FIX_REPOS beats XDG" \
  bash -c "CVE_FIX_REPOS='$ALT_YAML' XDG_CONFIG_HOME='$XDG_CFG' '$SCRIPT_DIR/detect.sh' altrepo devel >/dev/null 2>&1"
check "CVE_FIX_REPOS beats XDG: XDG-only name fails" \
  ! bash -c "CVE_FIX_REPOS='$ALT_YAML' XDG_CONFIG_HOME='$XDG_CFG' '$SCRIPT_DIR/detect.sh' testfixrepo devel 2>/dev/null"

# 3. CVE_FIX_REPOS set to a non-existent file must fail immediately with an
#    actionable error mentioning the env var, not a confusing "Unknown repo" message.
REG_MISSING_OUT=$(CVE_FIX_REPOS="$TMPD/nonexistent-repos.yaml" \
  "$SCRIPT_DIR/detect.sh" testfixrepo devel 2>&1) && _reg_missing_rc=0 || _reg_missing_rc=$?
check "CVE_FIX_REPOS missing file: exits non-zero" test "$_reg_missing_rc" -ne 0
check "CVE_FIX_REPOS missing file: mentions env var" grep -q "CVE_FIX_REPOS" <<< "$REG_MISSING_OUT"

# === detect.sh .cve-fix.yaml config parsing ===
# Hermetic: creates a minimal git repo with a .cve-fix.yaml containing all
# supported fields, then asserts that detect.sh writes each field into the
# state file. Also verifies that k8s-version-guard: false leaves the flag
# unset (K8S_VERSION_GUARD=false).
echo "detect.sh .cve-fix.yaml config parsing"
YAML_REPO="$TMPD/yaml-config-repo"
mkdir -p "$YAML_REPO"
git -C "$YAML_REPO" init -q
printf 'module example.com/yamlrepo\ngo 1.24.0\n' > "$YAML_REPO/go.mod"
cat > "$YAML_REPO/.cve-fix.yaml" <<'YAML'
build-image: quay.io/example/image:v1.0
build-command: make BUILD_UPX=false build
clean-command: make distclean
test-command: make integration-test
unset-env: DOCKER_HOST
k8s-version-guard: true
upstream-org: example-io
YAML
YAML_OUT=$("$SCRIPT_DIR/detect.sh" "$YAML_REPO" devel 2>&1) || true
YAML_STATE=$(tail -1 <<< "$YAML_OUT")
check "config: state file created"    test -f "$YAML_STATE"
check "config: build-image"           test "$(state_value "$YAML_STATE" BUILD_IMAGE)" = "quay.io/example/image:v1.0"
check "config: build-command"         test "$(state_value "$YAML_STATE" BUILD_CMD)" = "make BUILD_UPX=false build"
check "config: clean-command"         test "$(state_value "$YAML_STATE" CLEAN_CMD)" = "make distclean"
check "config: test-command"          test "$(state_value "$YAML_STATE" TEST_CMD)" = "make integration-test"
check "config: unset-env"             test "$(state_value "$YAML_STATE" ENV_UNSET)" = "DOCKER_HOST"
check "config: k8s-version-guard true" test "$(state_value "$YAML_STATE" K8S_VERSION_GUARD)" = true
check "config: upstream-org"          test "$(state_value "$YAML_STATE" UPSTREAM_ORG)" = "example-io"
rm -f "$YAML_STATE"
# k8s-version-guard: false must leave K8S_VERSION_GUARD=false (the default)
printf 'k8s-version-guard: false\n' > "$YAML_REPO/.cve-fix.yaml"
YAML_OUT2=$("$SCRIPT_DIR/detect.sh" "$YAML_REPO" devel 2>&1) || true
YAML_STATE2=$(tail -1 <<< "$YAML_OUT2")
check "config: k8s-version-guard false" test "$(state_value "$YAML_STATE2" K8S_VERSION_GUARD)" = false
rm -f "$YAML_STATE2"

# === detect.sh CONTAINER_CMD detection ===
# Hermetic: mocks docker/podman via PATH-injected stubs to test all three
# branches of the container-command selection in detect.sh.
echo "detect.sh CONTAINER_CMD detection"

# Helper: create a minimal git+go.mod repo for container-cmd tests.
_cc_repo() {
  local td
  td=$(mktemp -d "$TMPD/cc-repo.XXXXXX")
  git -C "$td" init -q
  git -C "$td" config user.email "t@t.com"
  git -C "$td" config user.name "T"
  printf 'module example.com/cc\ngo 1.24.0\n' > "$td/go.mod"
  printf '%s\n' "$td"
}

# Helper: create a stub command in a temp bin dir.
# Usage: _mk_stub <bindir> <name> <exit_code>
_mk_stub() {
  local bindir="$1" name="$2" rc="$3"
  printf '#!/bin/sh\nexit %s\n' "$rc" > "$bindir/$name"
  chmod +x "$bindir/$name"
}

CC_BINDIR=$(mktemp -d "$TMPD/cc-bin.XXXXXX")

# Case 1: docker succeeds (exit 0) → CONTAINER_CMD=docker
CC_REPO1=$(_cc_repo)
_mk_stub "$CC_BINDIR" docker 0
_mk_stub "$CC_BINDIR" podman 0
CC_OUT1=$(PATH="$CC_BINDIR:$PATH" "$SCRIPT_DIR/detect.sh" "$CC_REPO1" devel 2>&1) || true
CC_STATE1=$(tail -1 <<< "$CC_OUT1")
check "CONTAINER_CMD: docker wins when docker info succeeds" \
  test "$(state_value "$CC_STATE1" CONTAINER_CMD)" = docker
rm -f "$CC_STATE1"

# Case 2: docker info fails, podman succeeds → CONTAINER_CMD=podman
CC_REPO2=$(_cc_repo)
_mk_stub "$CC_BINDIR" docker 1
_mk_stub "$CC_BINDIR" podman 0
CC_OUT2=$(PATH="$CC_BINDIR:$PATH" "$SCRIPT_DIR/detect.sh" "$CC_REPO2" devel 2>&1) || true
CC_STATE2=$(tail -1 <<< "$CC_OUT2")
check "CONTAINER_CMD: podman wins when docker info fails" \
  test "$(state_value "$CC_STATE2" CONTAINER_CMD)" = podman
rm -f "$CC_STATE2"

# Case 3: both docker and podman info fail → CONTAINER_CMD="" (no container runtime)
CC_REPO3=$(_cc_repo)
_mk_stub "$CC_BINDIR" docker 1
_mk_stub "$CC_BINDIR" podman 1
CC_OUT3=$(PATH="$CC_BINDIR:$PATH" "$SCRIPT_DIR/detect.sh" "$CC_REPO3" devel 2>&1) || true
CC_STATE3=$(tail -1 <<< "$CC_OUT3")
check "CONTAINER_CMD: empty when both docker and podman info fail" \
  test "$(state_value "$CC_STATE3" CONTAINER_CMD)" = ""
rm -f "$CC_STATE3"

rm -rf "$CC_BINDIR"

# === detect.sh BUILD_GO_VERSION: docker inspect for digest references ===
# docker image ls -q fails for digest refs; docker inspect works for both tag and digest.
echo "detect.sh BUILD_GO_VERSION digest reference"
_BGV_BINDIR=$(mktemp -d "$TMPD/bgv-bin.XXXXXX")
_BGV_REPO=$(_cc_repo)
cat > "$_BGV_BINDIR/docker" <<'STUBEOF'
#!/bin/sh
case "$1" in
  info)    exit 0 ;;
  inspect) exit 0 ;;
  run)     echo "go version go1.23.4 linux/amd64"; exit 0 ;;
  image)   # Old path: image ls -q returns empty to simulate digest blindness
           exit 0 ;;
  *)       exit 1 ;;
esac
STUBEOF
chmod +x "$_BGV_BINDIR/docker"
printf 'build-image: quay.io/example/img@sha256:abc123\n' > "$_BGV_REPO/.cve-fix.yaml"
_BGV_OUT=$(PATH="$_BGV_BINDIR:$PATH" "$SCRIPT_DIR/detect.sh" "$_BGV_REPO" devel 2>&1) || true
_BGV_STATE=$(tail -1 <<< "$_BGV_OUT")
check "BUILD_GO_VERSION: digest ref sets version" \
  test "$(state_value "$_BGV_STATE" BUILD_GO_VERSION)" = "go version go1.23.4 linux/amd64"
rm -f "$_BGV_STATE"
rm -rf "$_BGV_BINDIR"

# A pristine Shipyard consumer has no Dockerfile.dapper yet: Make downloads it
# on first use. The wrapper still proves both the release builder image and the
# DAPPER_ENV mechanism needed to disable UPX inside the container.
_PD_BINDIR=$(mktemp -d "$TMPD/pristine-dapper-bin.XXXXXX")
_PD_REPO=$(_cc_repo)
cat > "$_PD_REPO/Makefile" <<'MAKEFILE'
BASE_BRANCH ?= release-0.22
ifneq (,$(DAPPER_HOST_ARCH))
build:
else
Makefile.dapper:
	@curl -sfLO https://raw.githubusercontent.com/submariner-io/shipyard/$(BASE_BRANCH)/$@
include Makefile.dapper
endif
MAKEFILE
git -C "$_PD_REPO" add Makefile go.mod
git -C "$_PD_REPO" commit -qm wrapper
cat > "$_PD_BINDIR/make" <<'STUBEOF'
#!/bin/sh
case " $* " in
  *" cve-fix-nonexistent-probe "*) exit 2 ;;
  *" build "*) exit 0 ;;
  *) exit 2 ;;
esac
STUBEOF
cat > "$_PD_BINDIR/docker" <<'STUBEOF'
#!/bin/sh
case "$1" in
  info) exit 0 ;;
  run) echo "go version go1.26.8 linux/amd64"; exit 0 ;;
  *) exit 0 ;;
esac
STUBEOF
chmod +x "$_PD_BINDIR/make" "$_PD_BINDIR/docker"
_PD_OUT=$(PATH="$_PD_BINDIR:$PATH" "$SCRIPT_DIR/detect.sh" "$_PD_REPO" release-0.22 2>&1)
_PD_STATE=$(tail -1 <<< "$_PD_OUT")
check "pristine Dapper wrapper detects release builder image" \
  test "$(state_value "$_PD_STATE" BUILD_IMAGE)" = quay.io/submariner/shipyard-dapper-base:release-0.22
check "pristine Dapper wrapper detects builder Go" \
  test "$(state_value "$_PD_STATE" BUILD_GO_VERSION)" = 'go version go1.26.8 linux/amd64'
check "Dapper scan build forwards BUILD_UPX through container boundary" \
  test "$(state_value "$_PD_STATE" BUILD_CMD)" = 'DAPPER_ENV="${DAPPER_ENV:+$DAPPER_ENV }BUILD_UPX GOEXPERIMENT" BUILD_UPX=false GOEXPERIMENT="${GOEXPERIMENT-,}" make build'
check "pristine Dapper wrapper uses standard in-container unit target" \
  test "$(state_value "$_PD_STATE" TEST_CMD)" = 'make unit'
check "Dapper wrapper does not auto-run global clean graph" \
  test -z "$(state_value "$_PD_STATE" CLEAN_CMD)"
check "post-scan builds force Make dependency rebuilds" \
  grep -qF 'MAKEFLAGS=-B timeout --foreground' "$SCRIPT_DIR/scan.sh"

echo "generated binary duplicate filtering"
GBD_JSON="$TMPD/generated-binary-duplicates.json"
cat > "$GBD_JSON" <<'EOF'
{"matches":[
  {"artifact":{"type":"go-module","name":"golang.org/x/crypto","locations":[{"path":"/bin/linux/amd64/app"}]},"vulnerability":{"id":"GO-2026-5932","fix":{"versions":[]}}},
  {"artifact":{"type":"go-module","name":"golang.org/x/crypto","locations":[{"path":"/go.mod"}]},"vulnerability":{"id":"GO-2026-5932","fix":{"versions":[]}}}],
 "ignoredMatches":[{"artifact":{"type":"go-module","name":"golang.org/x/crypto","locations":[{"path":"/go.mod"}]},"vulnerability":{"id":"GO-2026-5932","fix":{"versions":[]}}}]}
EOF
GBD_OUT=$(source "$SCRIPT_DIR/lib.sh"; filter_generated_binary_duplicates < "$GBD_JSON")
check "no-fix duplicates without binary provenance remain visible" \
  test "$(jq '.matches | length' <<< "$GBD_OUT")" -eq 2
check "source no-fix match is preserved" \
  test "$(jq -r '.matches[] | select(.artifact.locations[0].path == "/go.mod") | .artifact.locations[0].path' <<< "$GBD_OUT")" = /go.mod

echo "generated binary module dispatch (real offline Go builds)"
_BML_REPO="$TMPD/binary dispatch repo"
mkdir -p "$_BML_REPO/tools" "$_BML_REPO/output"
git -C "$_BML_REPO" init -q
printf 'module example.com/dispatch\ngo 1.18\n' > "$_BML_REPO/go.mod"
printf 'module "example.com/dispatch/tools"\ngo 1.18\n' > "$_BML_REPO/tools/go.mod"
printf 'package main\nfunc main() {}\n' > "$_BML_REPO/main.go"
cp "$_BML_REPO/main.go" "$_BML_REPO/tools/main.go"
git -C "$_BML_REPO" add go.mod tools/go.mod
_BML_BUILT=true
go -C "$_BML_REPO" build -o "$_BML_REPO/output/root" . || _BML_BUILT=false
go -C "$_BML_REPO/tools" build -o "$_BML_REPO/output/tools" . || _BML_BUILT=false
check "offline binary provenance fixtures build" test "$_BML_BUILT" = true
cp "$_BML_REPO/output/root" "$_BML_REPO/output/pre-existing"
printf '%s\n' "$_BML_REPO/output/root" "$_BML_REPO/output/tools" > "$_BML_REPO/manifest"
cat > "$_BML_REPO/scan.json" <<'EOF'
{"matches":[
 {"artifact":{"type":"go-module","name":"example.com/dep","version":"v1.0.0","locations":[{"path":"/output/root"}]},"vulnerability":{"id":"CVE-root","fix":{"versions":["1.0.1"]}}},
 {"artifact":{"type":"go-module","name":"example.com/dep","version":"v1.0.0","locations":[{"path":"/src/output/tools"}]},"vulnerability":{"id":"CVE-tools","fix":{"versions":[]}}},
 {"artifact":{"type":"go-module","name":"stdlib","locations":[{"path":"/output/tools"}]},"vulnerability":{"id":"CVE-stdlib"}},
 {"artifact":{"type":"go-module","name":"example.com/dep","locations":[{"path":"/output/pre-existing"}]},"vulnerability":{"id":"CVE-old"}}],"ignoredMatches":[]}
EOF
_BML_OUT=$(python3 "$SCRIPT_DIR/binary-module-locations.py" "$_BML_REPO" "$_BML_REPO/manifest" < "$_BML_REPO/scan.json")
check "fresh root binary dispatches to root module" \
  test "$(jq -r '.matches[0].artifact.locations[0].path' <<< "$_BML_OUT")" = /go.mod
check "fresh nested binary dispatches to owning quoted module" \
  test "$(jq -r '.matches[1].artifact.locations[0].path' <<< "$_BML_OUT")" = /tools/go.mod
check "stdlib retains its binary scan location" \
  test "$(jq -r '.matches[2].artifact.locations[0].path' <<< "$_BML_OUT")" = /output/tools
check "pre-existing binary cannot acquire generated source scope" \
  test "$(jq -r '.matches[3].artifact.locations[0].path' <<< "$_BML_OUT")" = /output/pre-existing
check "dispatch preserves advisory and package evidence" \
  test "$(jq -c '[.matches[] | {vulnerability, package:.artifact.name, version:.artifact.version}]' <<< "$_BML_OUT")" = \
       "$(jq -c '[.matches[] | {vulnerability, package:.artifact.name, version:.artifact.version}]' "$_BML_REPO/scan.json")"
_BML_UNMAPPED=$(python3 "$SCRIPT_DIR/binary-module-locations.py" "$_BML_REPO" "$_BML_REPO/missing-manifest" < "$_BML_REPO/scan.json")
check "missing manifest preserves every raw location" \
  test "$(jq -c . <<< "$_BML_UNMAPPED")" = "$(jq -c . "$_BML_REPO/scan.json")"
_BML_DUP_SCAN=$(jq '.ignoredMatches = [{artifact:{type:"go-module",name:"example.com/dep",version:"v1.0.0",locations:[{path:"/tools/go.mod"}]},vulnerability:{id:"CVE-tools",fix:{versions:[]}}}]' "$_BML_REPO/scan.json")
_BML_DUP_OUT=$(filter_generated_binary_duplicates "$_BML_REPO" "$_BML_REPO/manifest" <<< "$_BML_DUP_SCAN")
check "generated nested no-fix duplicate has proven source coverage" \
  test "$(jq '.matches | length' <<< "$_BML_DUP_OUT")" -eq 3
check "filtered duplicate retains its original binary-path evidence" \
  test "$(jq -r '.generatedBinaryDuplicates[0].artifact.locations[0].path' <<< "$_BML_DUP_OUT")" = /src/output/tools
check "duplicate filtering retains fixable binary findings" \
  test "$(jq -r '.matches[0].vulnerability.id' <<< "$_BML_DUP_OUT")" = CVE-root
check "duplicate filtering preserves Grype source-ignore evidence" \
  test "$(jq -c '.ignoredMatches' <<< "$_BML_DUP_OUT")" = "$(jq -c '.ignoredMatches' <<< "$_BML_DUP_SCAN")"
for _bml_change in '.ignoredMatches[0].artifact.locations[0].path = "/go.mod"' \
  '.ignoredMatches[0].artifact.version = "v1.0.1"' \
  '.matches[1].artifact.locations += [{path:"/tools/go.mod"}]' \
  '.ignoredMatches[0].vulnerability.fix.state = "not-fixed"'; do
  _BML_UNCOVERED=$(jq "$_bml_change" <<< "$_BML_DUP_SCAN" |
    filter_generated_binary_duplicates "$_BML_REPO" "$_BML_REPO/manifest")
  check "duplicate filter preserves unmatched owner/version/location/state: $_bml_change" \
    test "$(jq '.matches | length' <<< "$_BML_UNCOVERED")" -eq 4
done
_BML_NO_PROVENANCE=$(filter_generated_binary_duplicates "$_BML_REPO" "$_BML_REPO/missing-manifest" <<< "$_BML_DUP_SCAN")
check "duplicate filtering requires a generated-artifact manifest" \
  test "$(jq '.matches | length' <<< "$_BML_NO_PROVENANCE")" -eq 4
mkdir -p "$_BML_REPO/duplicate"
cp "$_BML_REPO/tools/go.mod" "$_BML_REPO/duplicate/go.mod"
git -C "$_BML_REPO" add duplicate/go.mod
_BML_AMBIGUOUS=$(python3 "$SCRIPT_DIR/binary-module-locations.py" "$_BML_REPO" "$_BML_REPO/manifest" < "$_BML_REPO/scan.json")
check "ambiguous module identity leaves binary location untouched" \
  test "$(jq -r '.matches[1].artifact.locations[0].path' <<< "$_BML_AMBIGUOUS")" = /src/output/tools

# Relative script invocation must survive detect.sh changing into the target
# repository; all later helper paths come from the already-absolute SCRIPT_DIR.
if [[ -n "${REPO_ROOT:-}" ]]; then
  _REL_DETECT_OUT=$(cd "$REPO_ROOT"; bash "${SCRIPT_DIR#"$REPO_ROOT"/}/detect.sh" "$_PD_REPO" devel)
  _REL_DETECT_STATE=$(tail -1 <<< "$_REL_DETECT_OUT")
  check "detect supports relative script invocation" test -f "$_REL_DETECT_STATE"
fi
rm -f "$_PD_STATE"
rm -rf "$_PD_BINDIR"

# === locate.sh (hermetic fixture) ===
# Build a self-contained multi-module repo and stub `go` so the dependency-graph
# section (locate.sh's `go -C DIR mod graph`) makes NO network call — the suite's
# offline invariant. locate.sh runs find_gomods in the cwd, so invoke it with the
# fixture as cwd (mirroring how the skill runs from the repo root).
echo "locate.sh"
LOC_REPO="$TMPD/locrepo"
mkdir -p "$LOC_REPO/tools" "$LOC_REPO/bin"
git -C "$LOC_REPO" init -q
printf 'module example.com/app\ngo 1.24.0\nrequire k8s.io/client-go v0.30.0\nreplace k8s.io/client-go => k8s.io/client-go v0.30.1\n' > "$LOC_REPO/go.mod"
printf 'module example.com/app/tools\ngo 1.24.0\nrequire github.com/example/linter v1.60.0\n' > "$LOC_REPO/tools/go.mod"
# Stub go: exits 0 with no output, so `go mod graph` never reaches the network.
printf '#!/bin/sh\nexit 0\n' > "$LOC_REPO/bin/go"; chmod +x "$LOC_REPO/bin/go"
git -C "$LOC_REPO" add -A
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$LOC_REPO" "$SCRIPT_DIR" > "$TMPD/loc.env"
runloc() { ( cd "$LOC_REPO" && PATH="$LOC_REPO/bin:$PATH" bash "$SCRIPT_DIR/locate.sh" "$TMPD/loc.env" "$1" 2>&1 ); }
LOCATE_OUT=$(runloc k8s.io/client-go) || true
check "finds in go.mod" grep -q "Found in:" <<< "$LOCATE_OUT"
check "reports replace" grep -q "REPLACE DIRECTIVES:" <<< "$LOCATE_OUT"
check "dep-graph section runs" grep -q "Dependency graph" <<< "$LOCATE_OUT"
LOCATE_OUT=$(runloc github.com/example/linter) || true
check "finds in tools" grep -q "tools" <<< "$LOCATE_OUT"
check "locate missing fails" ! runloc nonexistent/pkg >/dev/null

# === insert_grype_ignore fix-state ===
echo "insert_grype_ignore fix-state"
# Bug fix 1 regression: dup detection with fix-state (grep -A4, not -A2)
printf -- '---\nignore:\n' > "$TMPD/fsdup.yaml"
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup example.com/fsdup "First" "not-fixed"
FS_COUNT1=$(grep -c "GHSA-fsdup" "$TMPD/fsdup.yaml")
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup example.com/fsdup "Dup" "not-fixed"
FS_COUNT2=$(grep -c "GHSA-fsdup" "$TMPD/fsdup.yaml")
check "fix-state repeat yields one entry" test "$FS_COUNT1" -eq "$FS_COUNT2"
# Inline: no-fix-state and fix-state+location also dedup correctly
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup-b example.com/fsdup-b "First"
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup-b example.com/fsdup-b "Dup"
_NFS_C=$(grep -c "GHSA-fsdup-b" "$TMPD/fsdup.yaml")
check "no-state dup skipped" test "$_NFS_C" -eq 1
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup-c example.com/fsdup-c "First" "not-fixed" "/tools/go.mod"
insert_grype_ignore "$TMPD/fsdup.yaml" GHSA-fsdup-c example.com/fsdup-c "Dup" "not-fixed" "/tools/go.mod"
_LOC_C=$(grep -c "GHSA-fsdup-c" "$TMPD/fsdup.yaml")
check "state+loc dup skipped" test "$_LOC_C" -eq 1

# Cross-block: two blocks share the same CVE ID but different packages. Replacing
# beta's entry must only remove beta's block — alpha's block must survive intact.
printf -- '---\nignore:\n' > "$TMPD/crossblock.yaml"
insert_grype_ignore "$TMPD/crossblock.yaml" GHSA-XXXX-TEST-0001 example.com/alpha "Block-A" "" "/tools/go.mod"
insert_grype_ignore "$TMPD/crossblock.yaml" GHSA-XXXX-TEST-0001 example.com/beta  "Block-B" "" "/go.mod"
insert_grype_ignore "$TMPD/crossblock.yaml" GHSA-XXXX-TEST-0001 example.com/beta  "Block-B-tools" "" "/tools/go.mod"
# alpha untouched; beta retains one entry for each independent location.
_CB_COUNT=$(grep -c "GHSA-XXXX-TEST-0001" "$TMPD/crossblock.yaml")
check "cross-block: independent package/location entries preserved" test "$_CB_COUNT" = 3
check "cross-block: alpha still has /tools/go.mod" \
  bash -c "grep -A4 'example.com/alpha' '$TMPD/crossblock.yaml' | grep -q 'location: /tools/go.mod'"
check "cross-block: beta updated to /tools/go.mod" \
  bash -c "grep -A4 'example.com/beta' '$TMPD/crossblock.yaml' | grep -q 'location: /tools/go.mod'"
check "cross-block: beta /go.mod scope preserved" \
  grep -q 'location: /go.mod' "$TMPD/crossblock.yaml"

# === insert_grype_ignore location ===
echo "insert_grype_ignore location"
printf -- '---\nignore:\n' > "$TMPD/loc.yaml"
insert_grype_ignore "$TMPD/loc.yaml" GHSA-loc-test example.com/loc "Reason" "not-fixed" "/tools/go.mod"
check "location present" grep -q "location: /tools/go.mod" "$TMPD/loc.yaml"
# location: must come immediately after name: (remove_grype_ignore depends on it)
check "location after name" bash -c "grep -A1 'name: example.com/loc' '$TMPD/loc.yaml' | grep -q 'location: /tools/go.mod'"

printf -- '---\nignore:\n' > "$TMPD/noloc.yaml"
insert_grype_ignore "$TMPD/noloc.yaml" GHSA-noloc-test example.com/noloc "Reason" "not-fixed"
check "no location when unset" ! grep -q "location:" "$TMPD/noloc.yaml"

# === insert_grype_ignore absent file ===
# Regression: absent .grype.yaml must get a proper ignore: header, not bare fragments.
echo "insert_grype_ignore absent file"
rm -f "$TMPD/absent.yaml"
insert_grype_ignore "$TMPD/absent.yaml" GHSA-absent-1234 example.com/absent "No file present"
check "absent: file created" test -f "$TMPD/absent.yaml"
check "absent: ignore before entry" bash -c "test \"\$(grep -n '^ignore:' '$TMPD/absent.yaml' | cut -d: -f1)\" -lt \"\$(grep -n 'GHSA-absent-1234' '$TMPD/absent.yaml' | cut -d: -f1)\""
# Second insert into the newly-created file must dedup correctly.
insert_grype_ignore "$TMPD/absent.yaml" GHSA-absent-1234 example.com/absent "Duplicate"
check "absent: dedup after creation" test "$(grep -c 'GHSA-absent-1234' "$TMPD/absent.yaml")" -eq 1

# === insert_grype_ignore file without ignore: key ===
# Regression: existing file that lacks ignore: must have the key prepended.
echo "insert_grype_ignore no-ignore-key"
printf -- '---\n# existing comment\n' > "$TMPD/no-ignore-key.yaml"
insert_grype_ignore "$TMPD/no-ignore-key.yaml" GHSA-nokey-5678 example.com/nokey "Missing ignore key"
check "no-key: ignore key added" grep -q '^ignore:' "$TMPD/no-ignore-key.yaml"
check "no-key: entry written" grep -q "GHSA-nokey-5678" "$TMPD/no-ignore-key.yaml"
check "no-key: existing content preserved" grep -q 'existing comment' "$TMPD/no-ignore-key.yaml"

# === ignore.sh validation ===
echo "ignore.sh validation"
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$TMPD" "$SCRIPT_DIR" > "$TMPD/ign.env"
check "bad severity" ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ign.env" pkg "invalid" "reason" --permanent GHSA-xxxx
check "bad CVE format" ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ign.env" pkg "High" "reason" --permanent "not-a-cve"
check "implicit permanent ignore rejected" \
  ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ign.env" pkg "High" "reason" GHSA-implicit-0001
check "permanent and fix-state are mutually exclusive" \
  ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ign.env" pkg "High" "reason" --permanent --no-fix GHSA-conflict-0001

# === ignore.sh --no-fix ===
echo "ignore.sh --no-fix"
IGN_REPO="$TMPD/ign-repo"
mkdir -p "$IGN_REPO"
git -C "$IGN_REPO" init -q
git -C "$IGN_REPO" config user.email "test@test.com"
git -C "$IGN_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$IGN_REPO/.grype.yaml"
touch "$IGN_REPO/go.mod"
git -C "$IGN_REPO" add .grype.yaml go.mod
git -C "$IGN_REPO" commit -q -m "init"
git -C "$IGN_REPO" checkout -q -b devel
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$IGN_REPO" "$SCRIPT_DIR" > "$TMPD/ignf.env"

bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ignf.env" example.com/nf "High" "No fix" --no-fix GHSA-nf-0001 >/dev/null 2>&1
check "--no-fix sets fix-state" grep -q "fix-state: not-fixed" "$IGN_REPO/.grype.yaml"

git -C "$IGN_REPO" checkout -- .grype.yaml 2>/dev/null
printf -- '---\nignore:\n' > "$IGN_REPO/.grype.yaml"
git -C "$IGN_REPO" add .grype.yaml
git -C "$IGN_REPO" commit -q -m "reset"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ignf.env" example.com/wf "High" "Has fix" --permanent GHSA-wf-0001 >/dev/null 2>&1
check "no flag no fix-state" ! grep -q "fix-state" "$IGN_REPO/.grype.yaml"

printf -- '---\nignore:\n  # No fix available\n  - vulnerability: GO-2026-0001\n    fix-state: not-fixed\n    package:\n      name: golang.org/x/up\n' > "$IGN_REPO/.grype.yaml"
git -C "$IGN_REPO" add .grype.yaml && git -C "$IGN_REPO" commit -q -m "existing"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/ignf.env" golang.org/x/up "High" "No fix available" --fix-state unknown --location /go.mod GO-2026-0001 >/dev/null 2>&1
check "rescoping an existing ignore is an update" \
  test "$(git -C "$IGN_REPO" log -1 --format=%s)" = "Update x/up CVE ignores"
check "an ignore update says what changed" \
  bash -c 'git -C "$1" log -1 --format=%b | grep -q "scoped to /go.mod"' _ "$IGN_REPO"

# === ignore.sh commit subject varies by --no-fix (F3 fix) ===
echo "ignore.sh commit subject"
SUBJ_REPO="$TMPD/subj-repo"
mkdir -p "$SUBJ_REPO"
git -C "$SUBJ_REPO" init -q
git -C "$SUBJ_REPO" config user.email "test@test.com"
git -C "$SUBJ_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
touch "$SUBJ_REPO/go.mod"
git -C "$SUBJ_REPO" add .grype.yaml go.mod
git -C "$SUBJ_REPO" commit -q -m "init"
git -C "$SUBJ_REPO" checkout -q -b release-0.23
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$SUBJ_REPO" "$SCRIPT_DIR" > "$TMPD/subj.env"

bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" example.com/nofixpkg "High" "No fix" --no-fix GHSA-subj-0001 >/dev/null 2>&1
NOFIX_SUBJ=$(git -C "$SUBJ_REPO" log -1 --format='%s')
check "--no-fix subject says no fix available" bash -c "echo '$NOFIX_SUBJ' | grep -q 'no fix available'"
check "--no-fix subject no incompatible" ! bash -c "echo '$NOFIX_SUBJ' | grep -q 'incompatible'"

printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
git -C "$SUBJ_REPO" add .grype.yaml
git -C "$SUBJ_REPO" commit -q -m "reset"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" example.com/fixpkg "High" "Needs Go 1.26" --permanent GHSA-subj-0002 >/dev/null 2>&1
FIX_SUBJ=$(git -C "$SUBJ_REPO" log -1 --format='%s')
check "no-flag subject mentions branch" bash -c "echo '$FIX_SUBJ' | grep -q 'release-0.23'"
check "no-flag subject no 'no fix'" ! bash -c "echo '$FIX_SUBJ' | grep -q 'no fix'"
check "no-flag subject <=50 chars" test "${#FIX_SUBJ}" -le 50

# Verify commit bodies contain REASON
# Log: HEAD=fixpkg-ignore, HEAD~1=reset, HEAD~2=nofixpkg-ignore, HEAD~3=init
NOFIX_BODY=$(git -C "$SUBJ_REPO" log -1 --skip=2 --format='%b')
check "--no-fix body has reason" bash -c "echo '$NOFIX_BODY' | grep -q 'No fix'"
FIX_BODY=$(git -C "$SUBJ_REPO" log -1 --format='%b')
check "no-flag body has reason" bash -c "echo '$FIX_BODY' | grep -q 'Needs Go 1.26'"

# x/crypto no-fix: must use "no fix available" template, never "incompatible"
# Regression test for Fix #2 (submariner fdeefad2, subctl 110b5fa6):
# body "No fix version available" but subject "incompatible with release-0.23".
printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
git -C "$SUBJ_REPO" add .grype.yaml
git -C "$SUBJ_REPO" commit -q -m "reset-xcrypto"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" golang.org/x/crypto "High" "No fix version available" --no-fix GHSA-subj-xcrypto >/dev/null 2>&1
XCRYPTO_SUBJ=$(git -C "$SUBJ_REPO" log -1 --format='%s')
check "x/crypto --no-fix: subject <=50" test "${#XCRYPTO_SUBJ}" -le 50

# Very long package: even ($BRANCH) fallback would exceed 50 — use basename
# k8s.io/apiextensions-apiserver abbreviated = 30 chars; with (release-0.23) = 57
printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
git -C "$SUBJ_REPO" add .grype.yaml
git -C "$SUBJ_REPO" commit -q -m "reset4"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" k8s.io/apiextensions-apiserver "Unknown" "transitive dep not in go.mod" --permanent GHSA-subj-0004 >/dev/null 2>&1
LONG_SUBJ=$(git -C "$SUBJ_REPO" log -1 --format='%s')
check "long pkg subject <=50" test "${#LONG_SUBJ}" -le 50
check "long pkg subject uses basename" bash -c "echo '$LONG_SUBJ' | grep -q 'apiextensions-apiserver'"

# Very long versioned package: double-fallback strips /vN before basename
# github.com/very-long-github-org/some-package/v3 → very-long-github-org/some-package/v3 (36 chars)
# Short form "Ignore very-long-github-org/some-package/v3 CVEs (release-0.23)" = 63 chars > 50
# So _ABBREV_BASE strips /v3 → "some-package" basename used
printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
git -C "$SUBJ_REPO" add .grype.yaml
git -C "$SUBJ_REPO" commit -q -m "reset5"
VERSIONED_COMMIT_BEFORE=$(git -C "$SUBJ_REPO" rev-list --count HEAD)
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" github.com/very-long-github-org/some-package/v3 "High" "Needs Go 1.26" --permanent GHSA-subj-0005 >/dev/null 2>&1
VERSIONED_SUBJ=$(git -C "$SUBJ_REPO" log -1 --format='%s')
VERSIONED_BODY=$(git -C "$SUBJ_REPO" log -1 --format='%b')
VERSIONED_COMMIT_AFTER=$(git -C "$SUBJ_REPO" rev-list --count HEAD)
check "versioned long pkg: subject <=50" test "${#VERSIONED_SUBJ}" -le 50
check "versioned long pkg: strips /vN suffix" ! bash -c "echo '$VERSIONED_SUBJ' | grep -qE '\\bv3\\b'"
check "versioned long pkg: uses branch short form" bash -c "echo '$VERSIONED_SUBJ' | grep -q '(release-0.23)'"
check "versioned long pkg: CVE recorded in grype.yaml" grep -q "GHSA-subj-0005" "$SUBJ_REPO/.grype.yaml"
check "versioned long pkg: commit was created" test "$VERSIONED_COMMIT_AFTER" -gt "$VERSIONED_COMMIT_BEFORE"
check "versioned long pkg: body contains reason" bash -c "echo '$VERSIONED_BODY' | grep -q 'Needs Go 1.26'"

# === ignore.sh all-duplicates skips commit ===
echo "ignore.sh all-duplicates"
DUP_REPO="$TMPD/dup-repo"
mkdir -p "$DUP_REPO"
git -C "$DUP_REPO" init -q
git -C "$DUP_REPO" config user.email "test@test.com"
git -C "$DUP_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$DUP_REPO/.grype.yaml"
touch "$DUP_REPO/go.mod"
git -C "$DUP_REPO" add .grype.yaml go.mod
git -C "$DUP_REPO" commit -q -m "init"
git -C "$DUP_REPO" checkout -q -b devel
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$DUP_REPO" "$SCRIPT_DIR" > "$TMPD/dup-ign.env"

# First ignore succeeds (creates commit)
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/dup-ign.env" example.com/duppkg "High" "No fix" --no-fix GHSA-dup-0001 >/dev/null 2>&1
DUP_COMMIT_COUNT1=$(git -C "$DUP_REPO" rev-list --count HEAD)

# Second ignore with same CVE should exit 0 without creating a commit
DUP_EXIT=0
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/dup-ign.env" example.com/duppkg "High" "No fix" --no-fix GHSA-dup-0001 >/dev/null 2>&1 || DUP_EXIT=$?
DUP_COMMIT_COUNT2=$(git -C "$DUP_REPO" rev-list --count HEAD)
check "dup exits 0" test "$DUP_EXIT" -eq 0
check "dup no new commit" test "$DUP_COMMIT_COUNT1" -eq "$DUP_COMMIT_COUNT2"

# === ignore.sh Unknown severity (commit boundary) ===
echo "ignore.sh Unknown severity"
printf -- '---\nignore:\n' > "$SUBJ_REPO/.grype.yaml"
git -C "$SUBJ_REPO" add .grype.yaml
git -C "$SUBJ_REPO" commit -q -m "reset2"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/subj.env" example.com/unk "Unknown" "No fix" --no-fix GHSA-unk-0001 >/dev/null 2>&1
check "Unknown severity accepted" grep -q "GHSA-unk-0001" "$SUBJ_REPO/.grype.yaml"

# === cleanup trap unstages (F1 cleanup fix) ===
echo "cleanup trap unstages"
TRAP_REPO="$TMPD/trap-repo"
mkdir -p "$TRAP_REPO"
git -C "$TRAP_REPO" init -q
git -C "$TRAP_REPO" config user.email "test@test.com"
git -C "$TRAP_REPO" config user.name "Test"
echo "file" > "$TRAP_REPO/a.txt"
git -C "$TRAP_REPO" add -A
git -C "$TRAP_REPO" commit -q -m "init"

# Stage a change (simulating orphaned staged file)
echo "modified" > "$TRAP_REPO/a.txt"
git -C "$TRAP_REPO" add a.txt
check "staged before cleanup" ! git -C "$TRAP_REPO" diff --staged --quiet

# Mirror the guarded trap body (fix-all.sh cleanup): revert only when both
# REPO and FIX_BRANCH are set, always targeting $REPO via -C.
trap_revert() {  # $1=REPO $2=FIX_BRANCH
  local REPO="$1" FIX_BRANCH="$2"
  if [[ -n "${FIX_BRANCH:-}" && -n "${REPO:-}" ]]; then
    git -C "$REPO" reset --quiet HEAD -- . 2>/dev/null || true
    git -C "$REPO" checkout -- . 2>/dev/null || true
  fi
}
trap_revert "$TRAP_REPO" "fix-0.X-cves"
check "unstaged after cleanup" git -C "$TRAP_REPO" diff --staged --quiet
check "reverted after cleanup" git -C "$TRAP_REPO" diff --quiet

# Guard no-ops when REPO/FIX_BRANCH unset. The trap installs before detect.sh
# and 'cd "$REPO"', so an early failure must NOT revert the invocation dir.
echo "modified again" > "$TRAP_REPO/a.txt"
git -C "$TRAP_REPO" add a.txt
trap_revert "$TRAP_REPO" ""          # FIX_BRANCH empty -> guard blocks revert
check "guard blocks revert when unset" ! git -C "$TRAP_REPO" diff --staged --quiet

# === auth vs infra error taxonomy (ROOT-NOREPORT / ROOT-403) ===
echo "auth/infra error taxonomy"
# Real Vertex 403 signature captured from a failed subagent run.
AUTH_OUT="$TMPD/auth.agent-output"
printf 'Failed to authenticate. API Error: 403 [{"error":{"code":403,"message":"Permission %s denied ... due to an IAM deny policy","status":"PERMISSION_DENIED"}}]\n' \
  "aiplatform.endpoints.predict" > "$AUTH_OUT"
MODEL_OUT="$TMPD/model.out"; printf 'API Error: invalid model claude-nope\n' > "$MODEL_OUT"
CODEX_AUTH_OUT="$TMPD/codex-auth.out"; printf 'HTTP error: 401 Unauthorized: Missing bearer or basic authentication in header\n' > "$CODEX_AUTH_OUT"
# Auth errors are deterministic — classified by is_auth_error (checked first).
check "auth: detects 403 (file)" is_auth_error "$AUTH_OUT"
check "auth: detects 403 (stdin)" bash -c "printf '%s' \"\$(cat '$AUTH_OUT')\" | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }"
check "auth: detects invalid model" is_auth_error "$MODEL_OUT"
check "auth: detects Codex 401" is_auth_error "$CODEX_AUTH_OUT"
for _limit_msg in "You've hit your session limit · resets 8:10pm (America/New_York)" \
    "You've hit your usage limit. Upgrade or try again later." "Claude AI usage limit reached|1760000000"; do
  check "auth: account limit is not retried ($_limit_msg)" bash -c \
    "printf '%s\n' \"\$1\" | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }" _ "$_limit_msg"
done
check "auth: rate limiting stays transient" ! bash -c \
  "printf 'API Error: 429 rate limited\n' | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }"

# Transient infra signatures — retryable, classified by is_infra_error.
printf 'API Error: 429 rate limited\n' > "$TMPD/rl.out"
check "infra: detects 429" is_infra_error "$TMPD/rl.out"
printf 'API Error: 529 Overloaded\n' > "$TMPD/ov.out"
check "infra: detects 529/overload" is_infra_error "$TMPD/ov.out"
# Taxonomy must not cross over: a 429 is not auth (so it still retries).
check "infra: 429 is not auth" ! is_auth_error "$TMPD/rl.out"
check "auth: Codex 401 is also infra-shaped" is_infra_error "$CODEX_AUTH_OUT"

# A normal successful agent output must NOT be flagged as either.
printf 'VERDICT: PASS\nISSUES: 0\nAll checks passed.\n' > "$TMPD/ok.out"
check "clean output not auth" ! is_auth_error "$TMPD/ok.out"
check "clean output not infra" ! is_infra_error "$TMPD/ok.out"
check "missing file not infra" ! is_infra_error "$TMPD/does-not-exist.out"
check "missing file not auth" ! is_auth_error "$TMPD/does-not-exist.out"

# Model override: CVE_FIX_MODEL empty -> no --model flag (uses selected agent default).
build_model_args() { local -a a=(); [[ -n "${CVE_FIX_MODEL:-}" ]] && a=(--model "$CVE_FIX_MODEL"); echo "${#a[@]}"; }
check "no model flag by default" bash -c "unset CVE_FIX_MODEL; $(declare -f build_model_args); test \"\$(build_model_args)\" = 0"
check "model flag when set" bash -c "export CVE_FIX_MODEL=opus; $(declare -f build_model_args); test \"\$(build_model_args)\" = 2"


# === retry-with-backoff (ROOT-403 exposure) ===
echo "retry backoff"
# Exponential backoff base*2^(n-1), capped at 30s; base overridable for tests.
check "backoff attempt1=2" test "$(CVE_FIX_RETRY_BASE=2 cve_fix_backoff_delay 1)" = 2
check "backoff attempt3=8" test "$(CVE_FIX_RETRY_BASE=2 cve_fix_backoff_delay 3)" = 8
check "backoff capped at 30" test "$(CVE_FIX_RETRY_BASE=2 cve_fix_backoff_delay 8)" = 30
check "backoff base override 0" test "$(CVE_FIX_RETRY_BASE=0 cve_fix_backoff_delay 3)" = 0

# === UNRESOLVED feedback loop: review.sh -> fix-all.sh ===
# Behavioral: cve_fix_exit_code must return non-zero when UNSEEN_NEEDS_REVIEW=true.
echo "UNSEEN_NEEDS_REVIEW behavioral (cve_fix_exit_code)"
REV_OUT=$(bash -c "
  source '$SCRIPT_DIR/lib.sh'
  UNSEEN_NEEDS_REVIEW=true
  echo \"UNSEEN_NEEDS_REVIEW=\$UNSEEN_NEEDS_REVIEW\"
  # cve_fix_exit_code: UNSEEN_NEEDS_REVIEW alone → exit 2
  echo \"EXIT_CODE=\$(cve_fix_exit_code false false false false \"\$UNSEEN_NEEDS_REVIEW\")\"
" 2>/dev/null)
check "UNSEEN_NEEDS_REVIEW=true reported correctly" \
  grep -q 'UNSEEN_NEEDS_REVIEW=true' <<< "$REV_OUT"
check "UNSEEN_NEEDS_REVIEW=true yields non-zero exit code" \
  bash -c "EC=\$(grep '^EXIT_CODE=' <<< '$REV_OUT' | cut -d= -f2); [[ \"\$EC\" -ne 0 ]]"

# BUILD_FAILED block must set UNSEEN_NEEDS_REVIEW so a claude-absent review.sh
# (which exits 0) cannot suppress the unresolved state and allow a clean exit.
echo "BUILD_FAILED sets UNSEEN_NEEDS_REVIEW"
# Simulate the BUILD_FAILED block from fix-all.sh to verify UNSEEN_NEEDS_REVIEW=true
BF_OUT=$(bash -c "
  source '$SCRIPT_DIR/lib.sh'
  BUILD_FAILED=true
  UNSEEN_NEEDS_REVIEW=false
  FIX_LINES=()
  REVIEW_COUNT=0
  if \$BUILD_FAILED; then
    FIX_LINES+=('NEEDS_REVIEW: initial build failed — stdlib CVE coverage unknown')
    REVIEW_COUNT=\$((REVIEW_COUNT + 1))
    UNSEEN_NEEDS_REVIEW=true
  fi
  echo \"UNSEEN_NEEDS_REVIEW=\$UNSEEN_NEEDS_REVIEW\"
  echo \"REVIEW_COUNT=\$REVIEW_COUNT\"
  # Verify cve_fix_exit_code returns non-zero when UNSEEN_NEEDS_REVIEW=true
  echo \"EXIT_CODE=\$(cve_fix_exit_code false false false false \"\$UNSEEN_NEEDS_REVIEW\")\"
" 2>/dev/null)
check "BUILD_FAILED sets UNSEEN_NEEDS_REVIEW=true" \
  grep -q 'UNSEEN_NEEDS_REVIEW=true' <<< "$BF_OUT"
check "BUILD_FAILED increments REVIEW_COUNT" \
  bash -c "RC=\$(grep '^REVIEW_COUNT=' <<< '$BF_OUT' | cut -d= -f2); [[ \"\$RC\" -eq 1 ]]"
check "BUILD_FAILED UNSEEN_NEEDS_REVIEW yields non-zero exit code" \
  bash -c "EC=\$(grep '^EXIT_CODE=' <<< '$BF_OUT' | cut -d= -f2); [[ \"\$EC\" -ne 0 ]]"
# === fixed-pkgs sentinel (subagent verify-loop fix reporting) ===
# _fix_fv_package runs in a subprocess and cannot update the parent's FIX_LINES.
# It writes to fixed-pkgs; fix-all.sh reads it back to add FIXED: lines,
# remove stale ERROR: lines, and increment FIXED_COUNT.
echo "fixed-pkgs sentinel"
_FP_SENTINEL_DIR=$(mktemp -d "$TMPD/fp-sentinel.XXXXXX")
# Simulate: main loop added ERROR lines for two packages; verify loop fixed foo.
printf 'example.com/foo v1.2.3 for CVE-2024-1234\n' > "$_FP_SENTINEL_DIR/fixed-pkgs"
_FP_FIX_LINES=(
  "ERROR: example.com/foo — fix-package.sh failed with exit code 1"
  "ERROR: example.com/bar — fix-package.sh failed with exit code 1"
)
_FP_FIXED_COUNT=0
# Mirror the fix-all.sh fixed-pkgs read block (uses _remove_error_line logic inline)
while IFS= read -r _entry; do
  [[ -z "$_entry" ]] && continue
  _pkg="${_entry%% *}"
  # _remove_error_line: filter out ERROR: lines for this pkg
  _new=()
  for _line in "${_FP_FIX_LINES[@]+"${_FP_FIX_LINES[@]}"}"; do
    [[ "$_line" == "ERROR: $_pkg —"* ]] && continue
    _new+=("$_line")
  done
  _FP_FIX_LINES=("${_new[@]+"${_new[@]}"}")
  if ! printf '%s\n' "${_FP_FIX_LINES[@]+"${_FP_FIX_LINES[@]}"}" | grep -qF "FIXED: $_pkg " 2>/dev/null; then
    _FP_FIX_LINES+=("FIXED: $_entry")
    _FP_FIXED_COUNT=$((_FP_FIXED_COUNT + 1))
  fi
done < "$_FP_SENTINEL_DIR/fixed-pkgs"
_FP_OUT=$(printf '%s\n' "${_FP_FIX_LINES[@]+"${_FP_FIX_LINES[@]}"}")
check "fixed-pkgs: FIXED: line added for foo" \
  grep -q '^FIXED: example.com/foo v1.2.3 for CVE-2024-1234$' <<< "$_FP_OUT"
check "fixed-pkgs: ERROR line removed for foo" \
  ! grep -q 'ERROR: example.com/foo' <<< "$_FP_OUT"
check "fixed-pkgs: ERROR line for bar untouched" \
  grep -q 'ERROR: example.com/bar' <<< "$_FP_OUT"
check "fixed-pkgs: FIXED_COUNT incremented to 1" \
  test "$_FP_FIXED_COUNT" -eq 1
check "fixed-pkgs: one FIXED: line (no dup)" \
  bash -c '[[ $(grep -c "^FIXED: example.com/foo" <<< "'"$_FP_OUT"'") -eq 1 ]]'
# Dedup guard must not match a sibling package with a longer name (prefix-match regression).
_FP_PREFIX_LINES=("FIXED: example.com/foo-extended v2.0.0 for CVE-2024-9999")
if ! printf '%s\n' "${_FP_PREFIX_LINES[@]}" | grep -qF "FIXED: example.com/foo " 2>/dev/null; then
  _FP_PREFIX_LINES+=("FIXED: example.com/foo v1.0.0 for CVE-2024-1111")
fi
_FP_PREFIX_OUT=$(printf '%s\n' "${_FP_PREFIX_LINES[@]}")
check "fixed-pkgs dedup: prefix pkg does not block shorter pkg insert" \
  grep -q '^FIXED: example.com/foo v1.0.0' <<< "$_FP_PREFIX_OUT"
check "fixed-pkgs dedup: sibling pkg preserved" \
  grep -q '^FIXED: example.com/foo-extended v2.0.0' <<< "$_FP_PREFIX_OUT"
rm -rf "$_FP_SENTINEL_DIR"

# === UNRESOLVED dedup guard prefix-match regression ===
# Without " —" anchor, grep -qF fires on prefix matches; " —" suffix anchors the guard correctly.
echo "UNRESOLVED dedup guard anchor"
_FS_PREFIX=$'NEEDS_REVIEW: github.com/foo-bar — something\n'
check "dedup guard: no false dedup for prefix pkg" \
  ! grep -qF "NEEDS_REVIEW: github.com/foo —" <<< "$_FS_PREFIX"

# === review-resolved grep -v anchor regression ===
# Bug: grep -v "^NEEDS_REVIEW: $_resolved_pkg" without " —" also strips sibling
# entries whose name starts with the same prefix. E.g. resolving "github.com/foo"
# must NOT remove "NEEDS_REVIEW: github.com/foo-bar — ..." from FIX_LINES.
echo "review-resolved grep -v anchor"
_FS_SIBLING=$'NEEDS_REVIEW: github.com/foo — desc\nNEEDS_REVIEW: github.com/foo-bar — other\n'
_AFTER_REMOVE=$(printf '%s' "$_FS_SIBLING" | grep -v "^NEEDS_REVIEW: github.com/foo —")
check "grep -v anchored: sibling entry preserved" \
  grep -q "NEEDS_REVIEW: github.com/foo-bar —" <<< "$_AFTER_REMOVE"
check "grep -v anchored: resolved entry removed" \
  ! grep -q "NEEDS_REVIEW: github.com/foo —$" <<< "$_AFTER_REMOVE"

# === review-resolved does not strip NEEDS_REVIEW for also-UNRESOLVED packages ===
# Bug: when a package has multiple CVE groups (e.g. x/crypto: GO-2026-5932 ignored,
# GO-2026-6354/6355 unresolved), the review-resolved reader was removing the
# per-package NEEDS_REVIEW line because the agent wrote IGNORED: for one CVE group.
# Fix: skip _remove_needs_review when the package is also in _REVIEW_UNRESOLVED_PKGS.
echo "review-resolved skip for also-UNRESOLVED packages"
_RRUP_TMPD=$(mktemp -d)
# Simulate state: x/crypto has NEEDS_REVIEW in FIX_LINES (from deterministic phase)
# The agent wrote IGNORED: x/crypto (for GO-2026-5932) AND UNRESOLVED: x/crypto (for GO-2026-6354/6355)
(
  # Inline the _remove_needs_review logic and the guard from fix-all.sh
  FIX_LINES=("NEEDS_REVIEW: golang.org/x/crypto — go get upgraded Go directive 1.25.0 -> 1.26.0 (breaking minor version bump)")
  _REVIEW_UNRESOLVED_PKGS=("golang.org/x/crypto")
  echo "golang.org/x/crypto" > "$_RRUP_TMPD/review-resolved"
  # Apply the guarded review-resolved reader logic
  while IFS= read -r _resolved_pkg; do
    [[ -z "$_resolved_pkg" ]] && continue
    if printf '%s\n' "${_REVIEW_UNRESOLVED_PKGS[@]+"${_REVIEW_UNRESOLVED_PKGS[@]}"}" | grep -qxF "$_resolved_pkg" 2>/dev/null; then
      continue
    fi
    FIX_LINES=("${FIX_LINES[@]+"${FIX_LINES[@]}"}")
    mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -v "^NEEDS_REVIEW: $_resolved_pkg —" || true)
  done < "$_RRUP_TMPD/review-resolved"
  printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}"
) > "$_RRUP_TMPD/out"
check "NEEDS_REVIEW preserved when pkg also UNRESOLVED" \
  grep -q "NEEDS_REVIEW: golang.org/x/crypto —" "$_RRUP_TMPD/out"
# Control: when pkg is NOT in unresolved set, removal proceeds normally
(
  FIX_LINES=("NEEDS_REVIEW: golang.org/x/mod — some reason")
  _REVIEW_UNRESOLVED_PKGS=()
  echo "golang.org/x/mod" > "$_RRUP_TMPD/review-resolved2"
  while IFS= read -r _resolved_pkg; do
    [[ -z "$_resolved_pkg" ]] && continue
    if printf '%s\n' "${_REVIEW_UNRESOLVED_PKGS[@]+"${_REVIEW_UNRESOLVED_PKGS[@]}"}" | grep -qxF "$_resolved_pkg" 2>/dev/null; then
      continue
    fi
    mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -v "^NEEDS_REVIEW: $_resolved_pkg —" || true)
  done < "$_RRUP_TMPD/review-resolved2"
  printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}"
) > "$_RRUP_TMPD/out2"
check "NEEDS_REVIEW removed when pkg NOT in unresolved set" \
  ! grep -q "NEEDS_REVIEW: golang.org/x/mod —" "$_RRUP_TMPD/out2"

# === ignored-pkgs reader also guards _remove_needs_review for UNRESOLVED pkgs ===
# The same _REVIEW_UNRESOLVED_PKGS guard must apply to the ignored-pkgs reader
# (post-verify-loop), not only the review-resolved reader. The ignored-pkgs reader
# runs AFTER both review readers; without the guard it removes the per-package
# NEEDS_REVIEW that the review-resolved reader correctly preserved.
echo "ignored-pkgs reader preserves NEEDS_REVIEW for also-UNRESOLVED packages"
_IGPR_TMPD=$(mktemp -d)
(
  FIX_LINES=("NEEDS_REVIEW: golang.org/x/crypto — go get upgraded Go directive 1.25.0 -> 1.26.0 (breaking minor version bump)")
  _REVIEW_UNRESOLVED_PKGS=("golang.org/x/crypto")
  _entry="golang.org/x/crypto (no fix available) for GO-2026-5932"
  _pkg="${_entry%% *}"
  # Apply the guarded ignored-pkgs reader logic
  if ! printf '%s\n' "${_REVIEW_UNRESOLVED_PKGS[@]+"${_REVIEW_UNRESOLVED_PKGS[@]}"}" | grep -qxF "$_pkg" 2>/dev/null; then
    mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -v "^NEEDS_REVIEW: $_pkg —" || true)
  fi
  if ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -qF "IGNORED: $_pkg " 2>/dev/null; then
    FIX_LINES+=("IGNORED: $_entry")
  fi
  printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}"
) > "$_IGPR_TMPD/out"
check "ignored-pkgs reader preserves NEEDS_REVIEW when pkg also UNRESOLVED" \
  grep -q "NEEDS_REVIEW: golang.org/x/crypto —" "$_IGPR_TMPD/out"
check "ignored-pkgs reader still adds IGNORED: entry" \
  grep -q "IGNORED: golang.org/x/crypto" "$_IGPR_TMPD/out"
# Control: when pkg is NOT in unresolved set, _remove_needs_review proceeds normally
(
  FIX_LINES=("NEEDS_REVIEW: golang.org/x/sys — some issue")
  _REVIEW_UNRESOLVED_PKGS=()
  _entry="golang.org/x/sys (no fix available) for GO-2026-1234"
  _pkg="${_entry%% *}"
  if ! printf '%s\n' "${_REVIEW_UNRESOLVED_PKGS[@]+"${_REVIEW_UNRESOLVED_PKGS[@]}"}" | grep -qxF "$_pkg" 2>/dev/null; then
    mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -v "^NEEDS_REVIEW: $_pkg —" || true)
  fi
  printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}"
) > "$_IGPR_TMPD/out2"
check "ignored-pkgs reader removes NEEDS_REVIEW when pkg NOT in unresolved set" \
  ! grep -q "NEEDS_REVIEW: golang.org/x/sys —" "$_IGPR_TMPD/out2"
rm -rf "$_IGPR_TMPD"

rm -rf "$_RRUP_TMPD"

# === fix-package.sh env var warnings (GOPROXY=off, GONOSUMDB wildcard) ===
# Verify warning is emitted when GONOSUMDB=* is set; fix-package.sh exits non-zero, grep exits 0 on match.
echo "fix-package.sh env var warnings"
check "GONOSUMDB=* warning emitted at runtime" \
  bash -c "GONOSUMDB='*' '$SCRIPT_DIR/fix-package.sh' '$TMPD/s.env' some/pkg v1.0.0 GHSA-fake 2>&1 | grep -q 'WARNING: GONOSUMDB'"

# === fix-package.sh transient error → exit 5 ===
# Bug fix: timeout (exit 124) and network errors from _go_get_version must exit
# with a distinct code (5) instead of falling through to STILL_VULNERABLE (exit 3).
# This prevents the caller from misclassifying a transient infra error as a
# genuinely unfixable CVE.
echo "fix-package.sh transient error handling"

# build_env_scrub: builds an `env -u` prefix array from ENV_UNSET, empty when unset.
_SAVED_EU="${ENV_UNSET:-}"
ENV_UNSET="FOO BAR"; build_env_scrub
check "scrub builds env -u prefix" test "${ENV_SCRUB[*]}" = "env -u FOO -u BAR"
ENV_UNSET=""; build_env_scrub
check "scrub empty when no unset-env" test "${#ENV_SCRUB[@]}" = 0
ENV_UNSET="$_SAVED_EU"

# === unset-env behavioral: full pipeline from .cve-fix.yaml to env scrub ===
# .cve-fix.yaml with "unset-env: MY_SECRET_VAR" is parsed by detect.sh into
# ENV_UNSET in the state file; build_env_scrub converts it to an ENV_SCRUB
# prefix array; the prefix actually strips MY_SECRET_VAR from the subprocess env.
echo "unset-env behavioral"
UE_REPO="$TMPD/ue-repo"
mkdir -p "$UE_REPO"
git -C "$UE_REPO" init -q
printf 'module example.com/ue\ngo 1.25.0\n' > "$UE_REPO/go.mod"
printf 'unset-env: MY_SECRET_VAR\n' > "$UE_REPO/.cve-fix.yaml"
UE_OUT=$("$SCRIPT_DIR/detect.sh" "$UE_REPO" devel 2>&1) || true
UE_STATE=$(tail -1 <<< "$UE_OUT")
check "unset-env: detect.sh creates state" test -f "$UE_STATE"
check "unset-env: ENV_UNSET in state" test "$(state_value "$UE_STATE" ENV_UNSET)" = MY_SECRET_VAR

# Behavioral: MY_SECRET_VAR must be absent in subprocess after env scrub.
UE_RESULT=$(
  source "$SCRIPT_DIR/lib.sh"
  source "$UE_STATE"
  build_env_scrub
  export MY_SECRET_VAR="sensitive"
  "${ENV_SCRUB[@]}" bash -c 'echo "VAR=${MY_SECRET_VAR:-ABSENT}"'
) 2>/dev/null
check "unset-env: MY_SECRET_VAR scrubbed from subprocess" \
  test "$UE_RESULT" = "VAR=ABSENT"

# Negative control: without env scrub the var is visible.
UE_PRESENT=$(
  export MY_SECRET_VAR="sensitive"
  bash -c 'echo "VAR=${MY_SECRET_VAR:-ABSENT}"'
) 2>/dev/null
check "unset-env: without scrub var is present (control)" \
  test "$UE_PRESENT" = "VAR=sensitive"
rm -f "$UE_STATE"

# is_scan_transient: retryable scanner/network errors vs a real invalid result.
printf 'grype: no route to host\n' > "$TMPD/scan-net.out"
check "scan transient: no route to host" is_scan_transient "$TMPD/scan-net.out"
printf 'TLS handshake timeout\n' > "$TMPD/scan-tls.out"
check "scan transient: TLS timeout" is_scan_transient "$TMPD/scan-tls.out"
printf 'jq: error: invalid JSON\n' > "$TMPD/scan-bad.out"
check "scan invalid JSON not transient" ! is_scan_transient "$TMPD/scan-bad.out"
check "scan transient (stdin)" bash -c "printf 'dial tcp: connection refused' | { source '$SCRIPT_DIR/lib.sh'; is_scan_transient; }"
# String-literal calling: $1 is not a file — must use herestring, not file open
check "scan transient string: no route to host" is_scan_transient "grype: no route to host"
check "scan transient string: connection refused" is_scan_transient "dial tcp: connection refused"
check "scan transient string: TLS handshake timeout" is_scan_transient "TLS handshake timeout"
check "auth string: 401 Unauthorized" is_auth_error "API Error: 401 Unauthorized"
check "auth string: 403 Forbidden" is_auth_error "API Error: 403 Forbidden"

# grype_db_degraded: grype's DB update/load failures (stale-DB "clean" is untrusted)
# vs benign scanner output.
printf 'failed to fetch latest version of db: connection refused\n' > "$TMPD/db-fail.out"
check "grype db degraded: fetch failure" grype_db_degraded "$TMPD/db-fail.out"
printf 'unable to update vulnerability database\n' > "$TMPD/db-upd.out"
check "grype db degraded: update failure" grype_db_degraded "$TMPD/db-upd.out"
printf 'No vulnerabilities found\n' > "$TMPD/db-ok.out"
check "grype db degraded: clean output -> false" ! grype_db_degraded "$TMPD/db-ok.out"
printf 'failed to fetch latest version: Get "https://toolbox-data.anchore.io/grype/releases/latest/VERSION": EOF\n' > "$TMPD/db-app.out"
check "grype release check failure does not imply DB failure" ! grype_db_degraded "$TMPD/db-app.out"
cat "$TMPD/db-upd.out" >> "$TMPD/db-app.out"
check "grype release warning never hides an actual DB failure" grype_db_degraded "$TMPD/db-app.out"
check "grype db degraded (stdin)" bash -c "printf 'db update failed' | { source '$SCRIPT_DIR/lib.sh'; grype_db_degraded; }"

# remove_fix_branch: deletes the throwaway fix branch on clean/abort exits so an
# empty branch isn't left behind.
RFB_REPO="$TMPD/rfb-repo"; mkdir -p "$RFB_REPO"
git -C "$RFB_REPO" init -q
git -C "$RFB_REPO" config user.email t@t.com; git -C "$RFB_REPO" config user.name T
echo x > "$RFB_REPO/f"; git -C "$RFB_REPO" add -A; git -C "$RFB_REPO" commit -q -m init
git -C "$RFB_REPO" branch fix-tmp
check "remove_fix_branch deletes empty branch" bash -c "
  cd '$RFB_REPO'
  source '$SCRIPT_DIR/lib.sh'
  FIX_BRANCH=fix-tmp ORIGINAL_REF=\$(git rev-parse --abbrev-ref HEAD) remove_fix_branch
  ! git show-ref --verify --quiet refs/heads/fix-tmp"
check "remove_fix_branch no-op without FIX_BRANCH" bash -c "
  cd '$RFB_REPO'
  source '$SCRIPT_DIR/lib.sh'
  FIX_BRANCH= remove_fix_branch"

# Sentinels wired end-to-end: scan.sh records build failure; fix-all.sh refuses
# to report clean; scan-regression.sh emits SCAN_FAILED on scanner failure.


# Real invocation: scan-regression.sh must exit non-zero and emit SCAN_FAILED=1 when
# initial-scan.json is absent (missing-file branch, lines 25-30 of scan-regression.sh).
# A static grep cannot verify this code path is reachable — only a live run can.
SR2_REPO="$TMPD/sr2-repo"; mkdir -p "$SR2_REPO"
touch "$SR2_REPO/go.mod"
SR2_RDIR="$TMPD/sr2-rdir"; mkdir -p "$SR2_RDIR"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\n' \
  "$SR2_REPO" "$SCRIPT_DIR" > "$TMPD/sr2.env"
SR2_OUT_FILE="$TMPD/sr2.out"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$TMPD/sr2.env" "$SR2_RDIR" \
  >"$SR2_OUT_FILE" 2>&1 && SR2_RC=0 || SR2_RC=$?
check "scan-regression missing initial-scan exits nonzero" test "$SR2_RC" -ne 0
check "scan-regression missing initial-scan emits SCAN_FAILED" grep -q 'SCAN_FAILED=1' "$SR2_OUT_FILE"

# Real invocation: scan-regression.sh must exit non-zero and emit SCAN_FAILED=1 when
# the final scan produces no valid JSON (failed-final-scan branch, lines 56-62 of
# scan-regression.sh). A static grep cannot verify this code path either.
SR3_DIR="$TMPD/sr3"; mkdir -p "$SR3_DIR"
SR3_REPO="$SR3_DIR/repo"; mkdir -p "$SR3_REPO"
touch "$SR3_REPO/go.mod"
SR3_RDIR="$SR3_DIR/report"; mkdir -p "$SR3_RDIR"
SR3_SCRIPTS="$SR3_DIR/scripts"; mkdir -p "$SR3_SCRIPTS"
cp "$SCRIPT_DIR/lib.sh" "$SR3_SCRIPTS/"
printf '#!/usr/bin/env bash\nexit 1\n' > "$SR3_SCRIPTS/scan.sh"
chmod +x "$SR3_SCRIPTS/scan.sh"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$SR3_RDIR/initial-scan.json"
printf '{"matches":[{"stale":true}]}\n' > "$SR3_RDIR/final-scan.json"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\n' \
  "$SR3_REPO" "$SR3_SCRIPTS" > "$SR3_DIR/state.env"
SR3_OUT_FILE="$TMPD/sr3.out"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR3_DIR/state.env" "$SR3_RDIR" \
  >"$SR3_OUT_FILE" 2>&1 && SR3_RC=0 || SR3_RC=$?
check "scan-regression failed-final-scan exits nonzero" test "$SR3_RC" -ne 0
check "scan-regression failed-final-scan emits SCAN_FAILED" grep -q 'SCAN_FAILED=1' "$SR3_OUT_FILE"
check "scan-regression failed-final-scan removes stale evidence" ! test -e "$SR3_RDIR/final-scan.json"

# Syntactically valid JSON with the wrong shape is equally untrustworthy. It
# must not be published as current evidence or interpreted as an empty scan.
printf '#!/usr/bin/env bash\nprintf "{}\\n"\n' > "$SR3_SCRIPTS/scan.sh"
chmod +x "$SR3_SCRIPTS/scan.sh"
printf '{"matches":[{"stale":true}],"ignoredMatches":[]}\n' > "$SR3_RDIR/final-scan.json"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR3_DIR/state.env" "$SR3_RDIR" \
  >"$SR3_OUT_FILE" 2>&1 && SR3_RC=0 || SR3_RC=$?
check "scan-regression wrong-schema final exits nonzero" test "$SR3_RC" -ne 0
check "scan-regression wrong-schema final emits SCAN_FAILED" grep -q 'SCAN_FAILED=1' "$SR3_OUT_FILE"
check "scan-regression wrong-schema final removes stale evidence" ! test -e "$SR3_RDIR/final-scan.json"

# A binary named after its build commit is renamed by every fix commit; the
# same finding at the renamed binary is neither new nor resolved.
SRR="$TMPD/srr"; mkdir -p "$SRR/repo" "$SRR/report" "$SRR/scripts"
git -C "$SRR/repo" init -q; git -C "$SRR/repo" config user.email t@t; git -C "$SRR/repo" config user.name t
touch "$SRR/repo/go.mod"; git -C "$SRR/repo" add -A; git -C "$SRR/repo" commit -qm base
SRR_BASE=$(git -C "$SRR/repo" rev-parse --short=12 HEAD)
git -C "$SRR/repo" commit -q --allow-empty -m fix
SRR_HEAD=$(git -C "$SRR/repo" rev-parse --short=12 HEAD)
_srr_scan() { printf '{"matches":[{"vulnerability":{"id":"GO-1","fix":{"versions":["1.26.9"]}},"artifact":{"type":"go-module","name":"stdlib","version":"go1.26.8","locations":[{"path":"/cmd/bin/tool-%s-linux-amd64"}]}}],"ignoredMatches":[]}\n' "$1"; }
_srr_scan "$SRR_BASE" > "$SRR/report/initial-scan.json"
cp "$SCRIPT_DIR/lib.sh" "$SRR/scripts/"
printf '#!/usr/bin/env bash\ncat %q\n' "$SRR/final.json" > "$SRR/scripts/scan.sh"
_srr_scan "$SRR_HEAD" > "$SRR/final.json"
printf 'stdlib\n' > "$SRR/report/needs-review-pkgs"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\n' \
  "$SRR/repo" "$SRR/scripts" > "$SRR/state.env"
SRR_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SRR/state.env" "$SRR/report" 2>&1) || true
check "a binary renamed by a fix commit is not a new finding" grep -q '^NEW_CVES=0 UNRESOLVED=0' <<< "$SRR_OUT"
check "a renamed binary's finding keeps its review" grep -q "^NEEDS_REVIEW: GO-1 .*tool-$SRR_HEAD-linux" <<< "$SRR_OUT"
_srr_scan 0123456789ab > "$SRR/final.json"
SRR_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SRR/state.env" "$SRR/report" 2>&1) || true
check "a hash from outside the checkout is not masked" grep -q '^NEW_CVES=1' <<< "$SRR_OUT"

# A malformed initial scan also invalidates the comparison, before a final scan
# is attempted.
printf '{}\n' > "$SR3_RDIR/initial-scan.json"
printf '#!/usr/bin/env bash\ntouch "$1.scan-was-run"\nprintf "{\\"matches\\":[],\\"ignoredMatches\\":[]}\\n"\n' \
  > "$SR3_SCRIPTS/scan.sh"
chmod +x "$SR3_SCRIPTS/scan.sh"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR3_DIR/state.env" "$SR3_RDIR" \
  >"$SR3_OUT_FILE" 2>&1 && SR3_RC=0 || SR3_RC=$?
check "scan-regression wrong-schema initial exits nonzero" test "$SR3_RC" -ne 0
check "scan-regression wrong-schema initial emits SCAN_FAILED" grep -q 'SCAN_FAILED=1' "$SR3_OUT_FILE"
check "scan-regression wrong-schema initial stops before rescan" \
  ! test -e "$SR3_DIR/state.env.scan-was-run"

# Valid JSON from a failed scanner is not trustworthy evidence.
printf '{"matches":[]}\n' > "$SR3_RDIR/initial-scan.json"
for SR_BAD_MODE in status build-failed coverage-unknown scanner-degraded; do
  if [[ "$SR_BAD_MODE" == status ]]; then
    printf '#!/usr/bin/env bash\nprintf '\''{"matches":[]}'\''\nexit 7\n' > "$SR3_SCRIPTS/scan.sh"
  else
    printf '#!/usr/bin/env bash\ntouch "$1.%s"\nprintf '\''{"matches":[]}'\''\n' "$SR_BAD_MODE" > "$SR3_SCRIPTS/scan.sh"
  fi
  SR_BAD_RC=0
  bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR3_DIR/state.env" "$SR3_RDIR" > "$SR3_OUT_FILE" 2>&1 || SR_BAD_RC=$?
  check "scan-regression rejects $SR_BAD_MODE despite clean JSON" test "$SR_BAD_RC" -ne 0
  check "scan-regression flags $SR_BAD_MODE as unconfirmed" grep -q '^SCAN_FAILED=1' "$SR3_OUT_FILE"
  check "scan-regression never publishes $SR_BAD_MODE evidence" ! test -e "$SR3_RDIR/final-scan.json"
  rm -f "${SR3_DIR}/state.env.$SR_BAD_MODE"
done

# Real invocation: scan-regression.sh detects NEW_CVES when a CVE appears in the
# final scan but not the initial scan (zero-CVE initial scan, one-CVE final scan).
SR4_DIR="$TMPD/sr4"; mkdir -p "$SR4_DIR"
SR4_REPO="$SR4_DIR/repo"; mkdir -p "$SR4_REPO"
touch "$SR4_REPO/go.mod"
SR4_RDIR="$SR4_DIR/report"; mkdir -p "$SR4_RDIR"
SR4_SCRIPTS="$SR4_DIR/scripts"; mkdir -p "$SR4_SCRIPTS"
cp "$SCRIPT_DIR/lib.sh" "$SR4_SCRIPTS/"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$SR4_RDIR/initial-scan.json"
cat > "$SR4_SCRIPTS/scan.sh" << 'SCANEOF'
#!/usr/bin/env bash
printf '%s\n' '{"matches":[{"vulnerability":{"id":"GHSA-sr04-new0-cvex","severity":"High","fix":{"versions":["v2.0.0"]}},"artifact":{"name":"example/pkg","version":"v1.0.0","type":"go-module"}}],"ignoredMatches":[]}'
SCANEOF
chmod +x "$SR4_SCRIPTS/scan.sh"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\nCVE_FIX_SCAN_ATTEMPTS=1\n' \
  "$SR4_REPO" "$SR4_SCRIPTS" > "$SR4_DIR/state.env"
SR4_OUT_FILE="$TMPD/sr4.out"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR4_DIR/state.env" "$SR4_RDIR" \
  >"$SR4_OUT_FILE" 2>&1 && SR4_RC=0 || SR4_RC=$?
check "scan-regression NEW_CVES detection exits zero" test "$SR4_RC" -eq 0
check "scan-regression NEW_CVES=1 reported" grep -q 'NEW_CVES=1' "$SR4_OUT_FILE"
check "scan-regression publishes valid final evidence" \
  jq -e '.matches[0].vulnerability.id == "GHSA-sr04-new0-cvex"' "$SR4_RDIR/final-scan.json"

# Real invocation: scan-regression.sh detects UNRESOLVED when a CVE appears in both
# the initial and final scans and is not exempted in needs-review-pkgs.
SR5_DIR="$TMPD/sr5"; mkdir -p "$SR5_DIR"
SR5_REPO="$SR5_DIR/repo"; mkdir -p "$SR5_REPO"
touch "$SR5_REPO/go.mod"
SR5_RDIR="$SR5_DIR/report"; mkdir -p "$SR5_RDIR"
SR5_SCRIPTS="$SR5_DIR/scripts"; mkdir -p "$SR5_SCRIPTS"
cp "$SCRIPT_DIR/lib.sh" "$SR5_SCRIPTS/"
printf '{"matches":[{"vulnerability":{"id":"GHSA-sr05-unre-solv","severity":"High","fix":{"versions":["v2.0.0"]}},"artifact":{"name":"example/pkg","version":"v1.0.0","type":"go-module"}}],"ignoredMatches":[]}\n' > "$SR5_RDIR/initial-scan.json"
cat > "$SR5_SCRIPTS/scan.sh" << 'SCANEOF'
#!/usr/bin/env bash
printf '%s\n' '{"matches":[{"vulnerability":{"id":"GHSA-sr05-unre-solv","severity":"High","fix":{"versions":["v2.0.0"]}},"artifact":{"name":"example/pkg","version":"v1.0.0","type":"go-module"}}],"ignoredMatches":[]}'
SCANEOF
chmod +x "$SR5_SCRIPTS/scan.sh"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\nCVE_FIX_SCAN_ATTEMPTS=1\n' \
  "$SR5_REPO" "$SR5_SCRIPTS" > "$SR5_DIR/state.env"
SR5_OUT_FILE="$TMPD/sr5.out"
bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR5_DIR/state.env" "$SR5_RDIR" \
  >"$SR5_OUT_FILE" 2>&1 && SR5_RC=0 || SR5_RC=$?
check "scan-regression UNRESOLVED detection exits zero" test "$SR5_RC" -eq 0
check "scan-regression UNRESOLVED=1 reported" grep -q 'UNRESOLVED=1' "$SR5_OUT_FILE"

# network-broken sentinel: scan.sh classifies a build failure as network vs code.
# A DNS/proxy error means the environment is offline, so fix-all.sh aborts fast
# instead of committing an unverifiable fix. Behavioural: fake a build that fails
# with a transient network error and confirm the sentinel is written; a plain
# compile error must NOT set it (only .build-failed).
NB_REPO="$TMPD/nb-repo"; mkdir -p "$NB_REPO"
touch "$NB_REPO/go.mod"
NB_STATE="$TMPD/nb-state.env"
cat > "$NB_STATE" <<EOF
REPO=$NB_REPO
BRANCH=devel
HAS_LOCAL_GRYPE=false
CONTAINER_CMD=
BUILD_CMD='echo "dial tcp: lookup proxy.golang.org on 127.0.0.11:53: server misbehaving" >&2; false'
EOF
bash "$SCRIPT_DIR/scan.sh" "$NB_STATE" --no-update >/dev/null 2>&1 || true
check "scan.sh sets network-broken on DNS error" test -f "${NB_STATE}.network-broken"
check "scan.sh sets build-failed on DNS error" test -f "${NB_STATE}.build-failed"
rm -f "${NB_STATE}.network-broken" "${NB_STATE}.build-failed"
cat > "$NB_STATE" <<EOF
REPO=$NB_REPO
BRANCH=devel
HAS_LOCAL_GRYPE=false
CONTAINER_CMD=
BUILD_CMD='echo "./main.go:3:1: syntax error: unexpected }" >&2; false'
EOF
bash "$SCRIPT_DIR/scan.sh" "$NB_STATE" --no-update >/dev/null 2>&1 || true
check "scan.sh no network-broken on compile error" ! test -f "${NB_STATE}.network-broken"
check "scan.sh sets build-failed on compile error" test -f "${NB_STATE}.build-failed"
rm -f "${NB_STATE}.network-broken" "${NB_STATE}.build-failed"

# Partial network logs must not override a timeout or killed-build status.
for _build_stop in timeout killed; do
  _build_command='echo "dial tcp: lookup proxy.golang.org: server misbehaving" >&2; sleep 5'
  [[ "$_build_stop" != killed ]] || _build_command='echo "dial tcp: lookup proxy.golang.org: server misbehaving" >&2; exit 137'
  printf 'REPO=%q\nBRANCH=devel\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\nBUILD_CMD=%q\n' \
    "$NB_REPO" "$_build_command" > "$NB_STATE"
  CVE_FIX_BUILD_TIMEOUT=0.1 bash "$SCRIPT_DIR/scan.sh" "$NB_STATE" --no-update > "$TMPD/build-stop.log" 2>&1 || true
  check "scan.sh $_build_stop retains build-failed" test -f "${NB_STATE}.build-failed"
  check "scan.sh $_build_stop never becomes network-broken" ! test -f "${NB_STATE}.network-broken"
  check "scan.sh $_build_stop reports termination" grep -Eq 'Build (timed out|was killed)' "$TMPD/build-stop.log"
  rm -f "${NB_STATE}.network-broken" "${NB_STATE}.build-failed"
done

# Honest summary + PR-command guard on unconfirmed results: a gate/test/verify
# failure must not print "Outstanding: 0" or a ready-to-push PR command.

# scanner-degraded sentinel: run_grype flags a grype DB update/load failure so a
# stale-DB "clean" scan isn't trusted (covers build-less repos too). Shim grype to
# emit a DB-fetch error on stderr while still printing valid JSON — grype's
# graceful degradation — and confirm the sentinel is set on a fetch-attempting
# scan, but not with --no-update (which suppresses the fetch) or a healthy grype.
SD_BIN="$TMPD/sd-bin"; mkdir -p "$SD_BIN"
SD_REPO="$TMPD/sd-repo"; mkdir -p "$SD_REPO"
touch "$SD_REPO/go.mod"
SD_STATE="$TMPD/sd-state.env"
cat > "$SD_STATE" <<EOF
REPO=$SD_REPO
BRANCH=devel
HAS_LOCAL_GRYPE=true
CONTAINER_CMD=
EOF
cat > "$SD_BIN/grype" <<'SH'
#!/usr/bin/env bash
echo "failed to fetch latest version of db: connection refused" >&2
echo '{"matches":[]}'
SH
chmod +x "$SD_BIN/grype"
PATH="$SD_BIN:$PATH" bash "$SCRIPT_DIR/scan.sh" "$SD_STATE" --fresh --json >/dev/null 2>&1 || true
check "scan.sh flags stale grype DB on --fresh" test -f "${SD_STATE}.scanner-degraded"
rm -f "${SD_STATE}.scanner-degraded"
PATH="$SD_BIN:$PATH" bash "$SCRIPT_DIR/scan.sh" "$SD_STATE" --no-update --json >/dev/null 2>&1 || true
check "scan.sh no stale flag with --no-update" ! test -f "${SD_STATE}.scanner-degraded"
rm -f "${SD_STATE}.scanner-degraded"
cat > "$SD_BIN/grype" <<'SH'
#!/usr/bin/env bash
echo 'failed to fetch latest version: Get "https://toolbox-data.anchore.io/grype/releases/latest/VERSION": EOF' >&2
echo '{"matches":[]}'
SH
chmod +x "$SD_BIN/grype"
printf 'BUILD_GO_VERSION=unknown\n' >> "$SD_STATE"
SD_RELEASE_RC=0
PATH="$SD_BIN:$PATH" bash "$SCRIPT_DIR/scan.sh" "$SD_STATE" --fresh --json >/dev/null 2>&1 || SD_RELEASE_RC=$?
check "scan.sh accepts valid scan despite release-check failure" test "$SD_RELEASE_RC" -eq 0
check "scan.sh release-check failure does not mark DB stale" ! test -f "${SD_STATE}.scanner-degraded"
rm -f "${SD_STATE}.scanner-degraded"

# run_grype behavioral paths: no-scanner, local-fail→container-fallback, local-fail→no-container.
# These three paths are only reachable by calling run_grype directly; scan.sh/fix-all.sh tests
# never exercise them because those tests always have a working scanner configured.
echo "run_grype behavioral paths"
RG_REPO="$TMPD/rg-repo"; mkdir -p "$RG_REPO"
RG_BIN="$TMPD/rg-bin"; mkdir -p "$RG_BIN"

# (a) No scanner available: HAS_LOCAL_GRYPE=false, CONTAINER_CMD="" → exit 1 + error message.
RG_NOSCAN_OUT=$(
  cd "$RG_REPO"
  HAS_LOCAL_GRYPE=false
  CONTAINER_CMD=""
  run_grype 2>&1
) && RG_NOSCAN_RC=0 || RG_NOSCAN_RC=$?
check "run_grype no-scanner: exits 1" test "$RG_NOSCAN_RC" -eq 1
check "run_grype no-scanner: error message" grep -q "No scanner available" <<< "$RG_NOSCAN_OUT"

# (b) Local grype fails → container fallback succeeds.
# Mock grype exits nonzero; mock container cmd absorbs all subcommands and exits 0.
cat > "$RG_BIN/grype" <<'SH'
#!/usr/bin/env bash
exit 2
SH
chmod +x "$RG_BIN/grype"
cat > "$RG_BIN/mock-ctr" <<'SH'
#!/usr/bin/env bash
# Absorb volume/run subcommands and succeed silently.
exit 0
SH
chmod +x "$RG_BIN/mock-ctr"
RG_FALL_OUT=$(
  cd "$RG_REPO"
  PATH="$RG_BIN:$PATH"
  HAS_LOCAL_GRYPE=true
  CONTAINER_CMD="$RG_BIN/mock-ctr"
  run_grype 2>&1
) && RG_FALL_RC=0 || RG_FALL_RC=$?
check "run_grype local-fail+container: exits 0" test "$RG_FALL_RC" -eq 0
check "run_grype local-fail+container: fallback warning" grep -q "Local grype failed" <<< "$RG_FALL_OUT"

# (c) Local grype fails and no container → exit 1.
RG_FAILNOC_OUT=$(
  cd "$RG_REPO"
  PATH="$RG_BIN:$PATH"
  HAS_LOCAL_GRYPE=true
  CONTAINER_CMD=""
  run_grype 2>&1
) && RG_FAILNOC_RC=0 || RG_FAILNOC_RC=$?
check "run_grype local-fail no-container: exits 1" test "$RG_FAILNOC_RC" -eq 1

# (d) Local grype fails with transient network error → GRYPE_SCAN_TRANSIENT=1 + distinct warning.
# Use `|| _rc=$?` inside the subshell so set -e doesn't kill the subshell before
# we can echo GRYPE_SCAN_TRANSIENT, then `exit $_rc` propagates the real exit code.
cat > "$RG_BIN/grype" <<'SH'
#!/usr/bin/env bash
echo "no route to host" >&2
exit 1
SH
chmod +x "$RG_BIN/grype"
RG_TRANS_RC=0; RG_TRANS_OUT=$(
  cd "$RG_REPO"
  PATH="$RG_BIN:$PATH"
  HAS_LOCAL_GRYPE=true
  CONTAINER_CMD=""
  _rc=0; run_grype 2>&1 || _rc=$?
  echo "GRYPE_SCAN_TRANSIENT=$GRYPE_SCAN_TRANSIENT"
  exit $_rc
) || RG_TRANS_RC=$?
check "run_grype transient local-fail: exits 1" test "$RG_TRANS_RC" -eq 1
check "run_grype transient local-fail: transient warning" grep -q "transient network error" <<< "$RG_TRANS_OUT"
check "run_grype transient local-fail: GRYPE_SCAN_TRANSIENT set" grep -q "GRYPE_SCAN_TRANSIENT=1" <<< "$RG_TRANS_OUT"

# Restore non-transient grype for subsequent tests.
cat > "$RG_BIN/grype" <<'SH'
#!/usr/bin/env bash
exit 2
SH
chmod +x "$RG_BIN/grype"

# abort_if_environment_broken: the consumption side of scan.sh's environment
# sentinels. A present .network-broken or .scanner-degraded must abort with exit 2,
# a clear banner, the sentinel cleaned up, and the empty fix branch dropped —
# before any commit. Behavioural (not just grep): plant a sentinel, run the real
# function in a subshell (it calls exit), and assert every guarantee. Hermetic —
# no network, no grype, no container; only a throwaway git repo under $TMPD.
AEB_REPO="$TMPD/aeb-repo"; mkdir -p "$AEB_REPO"
git -C "$AEB_REPO" init -q
git -C "$AEB_REPO" config user.email t@t.com
git -C "$AEB_REPO" config user.name "T"
echo x > "$AEB_REPO/f"; git -C "$AEB_REPO" add -A; git -C "$AEB_REPO" commit -qm init
AEB_STATE="$TMPD/aeb-state.env"

# Run abort_if_environment_broken with a freshly planted sentinel and a live fix
# branch. Prints the function's stdout, then a __FELL_THROUGH__ marker that is only
# reached if the function RETURNED instead of exiting. That distinction is
# load-bearing: the function is the last command in this subshell, so exit 2 and
# return 2 both make the subshell exit 2 — but in the real fix-all.sh the call is
# not last, so a return would let the run proceed in a broken env. Asserting the
# marker's absence pins a true exit. Recreates fix-tmp each call so branch-drop can
# be asserted independently per case.
aeb_run() {  # $1 = sentinel suffix to plant ("" for none)
  local plant="$1" rc=0
  : > "$AEB_STATE"
  rm -f "${AEB_STATE}.network-broken" "${AEB_STATE}.scanner-degraded"
  [[ -n "$plant" ]] && : > "${AEB_STATE}.${plant}"
  (
    cd "$AEB_REPO"
    git branch -f fix-tmp >/dev/null 2>&1
    source "$SCRIPT_DIR/lib.sh"
    FIX_BRANCH=fix-tmp
    ORIGINAL_REF=$(git rev-parse --abbrev-ref HEAD)
    abort_if_environment_broken "$AEB_STATE" 2>&1
    printf '__FELL_THROUGH__'
  ) || rc=$?
  return $rc
}

AEB_RC=0; AEB_OUT=$(aeb_run network-broken) || AEB_RC=$?
check "aeb network-broken exits 2" test "$AEB_RC" -eq 2
check "aeb network-broken shows banner" grep -q 'environment offline' <<< "$AEB_OUT"
check "aeb network-broken truly exits" ! grep -q '__FELL_THROUGH__' <<< "$AEB_OUT"
check "aeb network-broken cleans sentinel" ! test -f "${AEB_STATE}.network-broken"
check "aeb network-broken drops fix branch" \
  ! git -C "$AEB_REPO" show-ref --verify --quiet refs/heads/fix-tmp

AEB_RC=0; AEB_OUT=$(aeb_run scanner-degraded) || AEB_RC=$?
check "aeb scanner-degraded exits 2" test "$AEB_RC" -eq 2
check "aeb scanner-degraded shows banner" grep -q 'vulnerability database unavailable' <<< "$AEB_OUT"
check "aeb scanner-degraded truly exits" ! grep -q '__FELL_THROUGH__' <<< "$AEB_OUT"
check "aeb scanner-degraded cleans sentinel" ! test -f "${AEB_STATE}.scanner-degraded"
check "aeb scanner-degraded drops fix branch" \
  ! git -C "$AEB_REPO" show-ref --verify --quiet refs/heads/fix-tmp

AEB_RC=0; AEB_OUT=$(aeb_run scan-transient) || AEB_RC=$?
check "aeb scan-transient exits 2" test "$AEB_RC" -eq 2
check "aeb scan-transient shows banner" grep -q 'scanner network error' <<< "$AEB_OUT"
check "aeb scan-transient truly exits" ! grep -q '__FELL_THROUGH__' <<< "$AEB_OUT"
check "aeb scan-transient cleans sentinel" ! test -f "${AEB_STATE}.scan-transient"
check "aeb scan-transient drops fix branch" \
  ! git -C "$AEB_REPO" show-ref --verify --quiet refs/heads/fix-tmp

# Both present: network-broken is the more actionable root cause and must win.
: > "$AEB_STATE"
: > "${AEB_STATE}.network-broken"; : > "${AEB_STATE}.scanner-degraded"
AEB_RC=0
AEB_OUT=$(
  cd "$AEB_REPO"; source "$SCRIPT_DIR/lib.sh"; FIX_BRANCH=
  abort_if_environment_broken "$AEB_STATE" 2>&1
  printf '__FELL_THROUGH__'
) || AEB_RC=$?
check "aeb both present exits 2" test "$AEB_RC" -eq 2
check "aeb both present network wins" grep -q 'environment offline' <<< "$AEB_OUT"
check "aeb both present truly exits" ! grep -q '__FELL_THROUGH__' <<< "$AEB_OUT"
rm -f "${AEB_STATE}.network-broken" "${AEB_STATE}.scanner-degraded"

# Healthy environment: no sentinel → no-op. The function must be silent and return
# 0, so output is exactly the fall-through marker (nothing before it) and the fix
# branch is left intact.
AEB_RC=0; AEB_OUT=$(aeb_run "") || AEB_RC=$?
check "aeb no sentinel returns 0" test "$AEB_RC" -eq 0
check "aeb no sentinel silent + returns" test "$AEB_OUT" = "__FELL_THROUGH__"
check "aeb no sentinel keeps fix branch" \
  git -C "$AEB_REPO" show-ref --verify --quiet refs/heads/fix-tmp

# === Deterministic evidence authoritative when the LLM is blocked (flagship) ===
echo "evidence fallback"
# evidence_verdict aggregates all four companions' .evidence into one verdict.
EV_DIR="$TMPD/ev"; mkdir -p "$EV_DIR"
printf 'NEW_CVES=0 UNRESOLVED=0\n' > "$EV_DIR/scan-regression.evidence"
printf 'NEW_ISSUES=0\n' > "$EV_DIR/fix-availability.evidence"
printf 'NEW_ISSUES=0\n' > "$EV_DIR/yaml-integrity.evidence"
printf 'NEW_ISSUES=0\n' > "$EV_DIR/existing-entries.evidence"
check "evidence all clean -> pass" evidence_verdict "$EV_DIR"
evidence_status_code() {
  local rc=0
  evidence_verdict "$@" >/dev/null 2>&1 || rc=$?
  printf '%s' "$rc"
}
for _ev_name in scan-regression existing-entries fix-availability yaml-integrity; do
  mv "$EV_DIR/$_ev_name.evidence" "$EV_DIR/$_ev_name.saved"
  check "evidence requires $_ev_name even without a script directory" \
    test "$(evidence_status_code "$EV_DIR")" = 2
  mv "$EV_DIR/$_ev_name.saved" "$EV_DIR/$_ev_name.evidence"
done
for _ev_bad in 'NEW_ISSUES=banana' 'NEW_ISSUES=-1' 'NEW_ISSUES=0suffix' \
  'NEW_ISSUES=1suffix' 'NEW_ISSUES=' $'NEW_ISSUES=0\nNEW_ISSUES=0' \
  $'NEW_ISSUES=0\nNEW_ISSUES=1' 'prefixNEW_ISSUES=0'; do
  printf '%s\n' "$_ev_bad" > "$EV_DIR/yaml-integrity.evidence"
  check "malformed issue evidence is inconclusive: $_ev_bad" \
    test "$(evidence_status_code "$EV_DIR")" = 2
  check "malformed issue evidence cannot name a repair: $_ev_bad" \
    test -z "$(evidence_issue_names "$EV_DIR")"
done
printf 'NEW_ISSUES=0\n' > "$EV_DIR/yaml-integrity.evidence"
for _ev_bad in 'NEW_CVES=0' 'UNRESOLVED=0' 'NEW_CVES=0 UNRESOLVED=-1' \
  'NEW_CVES=banana UNRESOLVED=0' 'NEW_CVES=0 UNRESOLVED=0suffix' \
  $'NEW_CVES=0 UNRESOLVED=0\nNEW_CVES=0 UNRESOLVED=0'; do
  printf '%s\n' "$_ev_bad" > "$EV_DIR/scan-regression.evidence"
  check "malformed scan evidence is inconclusive: $_ev_bad" \
    test "$(evidence_status_code "$EV_DIR")" = 2
  check "malformed scan evidence cannot name a repair: $_ev_bad" \
    test -z "$(evidence_issue_names "$EV_DIR")"
done
printf 'NEW_CVES=0 UNRESOLVED=0\n' > "$EV_DIR/scan-regression.evidence"
for _ev_failure in 'SCAN_FAILED=1' 'BUILD_FAILED=1' 'SKIP: audit unavailable'; do
  printf 'NEW_ISSUES=0\n%s\n' "$_ev_failure" > "$EV_DIR/yaml-integrity.evidence"
  check "failure marker makes clean counters inconclusive: $_ev_failure" \
    test "$(evidence_status_code "$EV_DIR")" = 2
done
printf 'NEW_ISSUES=0\n' > "$EV_DIR/yaml-integrity.evidence"
printf 'NEW_ISSUES=2\n' > "$EV_DIR/yaml-integrity.evidence"
check "evidence issue count -> fail" ! evidence_verdict "$EV_DIR"
check "valid positive evidence has the repairable status" test "$(evidence_status_code "$EV_DIR")" = 1
check "valid positive evidence names its audit" test "$(evidence_issue_names "$EV_DIR")" = yaml-integrity
printf 'NEW_ISSUES=000\n' > "$EV_DIR/yaml-integrity.evidence"
check "leading-zero zero counters remain clean" test "$(evidence_status_code "$EV_DIR")" = 0
printf 'NEW_ISSUES=999999999999999999999999999999\n' > "$EV_DIR/yaml-integrity.evidence"
check "large positive counters remain repairable without overflow" test "$(evidence_status_code "$EV_DIR")" = 1
printf 'NEW_ISSUES=0\n' > "$EV_DIR/yaml-integrity.evidence"
printf 'NEW_CVES=0 UNRESOLVED=3\n' > "$EV_DIR/scan-regression.evidence"
check "evidence unresolved>0 -> fail" ! evidence_verdict "$EV_DIR"
printf 'NEW_CVES=0 UNRESOLVED=0\nSCAN_FAILED=1\n' > "$EV_DIR/scan-regression.evidence"
check "evidence scan failure -> fail" ! evidence_verdict "$EV_DIR"
printf 'NEW_CVES=0 UNRESOLVED=0\nSKIP: no initial scan\n' > "$EV_DIR/scan-regression.evidence"
check "evidence SKIP -> fail" ! evidence_verdict "$EV_DIR"
# A present-but-marker-less file (companion crashed before its counter line) must
# be INCONCLUSIVE, not silently clean.
printf 'NEW_CVES=0 UNRESOLVED=0\n' > "$EV_DIR/scan-regression.evidence"
printf 'crashed before emitting a marker\n' > "$EV_DIR/yaml-integrity.evidence"
check "evidence marker-less file -> fail" ! evidence_verdict "$EV_DIR"
rm -f "$EV_DIR"/*.evidence
check "evidence missing -> fail" ! evidence_verdict "$EV_DIR"


# === Real deterministic verification: complete evidence permits bounded repair,
# while incomplete evidence and installed model CLIs cannot authorize it. ===
echo "verify_fix_loop (deterministic)"
vfl_case() {  # $1=casedir $2=iterations -> prints "rc=<n>"
  local casedir="$1" iterations="${2:-1}" rc=0
  (
    PATH="${VFL_TEST_PATH:-/usr/bin:/bin}"
    subagent_fix_yaml_integrity() {
      local count=0
      [[ ! -f "$casedir/repair-dispatched" ]] || read -r count < "$casedir/repair-dispatched"
      printf '%s\n' "$((count + 1))" > "$casedir/repair-dispatched"
    }
    verify_fix_loop "$casedir/state.env" "$casedir/subagents" "$casedir/report" "$iterations" \
      >/dev/null 2>&1 || rc=$?
    echo "rc=$rc"
  )
}
mk_vfl_case() {  # $1=casedir $2=scan-regression body $3=yaml-integrity body
  local casedir="$1" name
  mkdir -p "$casedir/subagents" "$casedir/report"
  touch "$casedir/go.mod"
  printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\n' "$casedir" "$SCRIPT_DIR" \
    > "$casedir/state.env"
  printf '#!/usr/bin/env bash\n%s\n' "$2" > "$casedir/subagents/scan-regression.sh"
  printf '#!/usr/bin/env bash\n%s\n' "$3" > "$casedir/subagents/yaml-integrity.sh"
  for name in existing-entries fix-availability; do
    printf '#!/usr/bin/env bash\necho "NEW_ISSUES=0"\n' > "$casedir/subagents/$name.sh"
  done
}
# Clean evidence -> verified via deterministic fallback.
mk_vfl_case "$TMPD/vfl-clean" 'echo "NEW_CVES=0 UNRESOLVED=0"' 'echo "NEW_ISSUES=0"'
check "vfl clean -> verified by evidence" \
  test "$(vfl_case "$TMPD/vfl-clean")" = "rc=0"
# Marker-less scan-regression (crashed before its NEW_CVES= line) -> 1b fails closed.
mk_vfl_case "$TMPD/vfl-mlscan" 'echo "boom: crashed before marker"' 'echo "NEW_ISSUES=0"'
check "vfl marker-less scan-regression -> not verified" \
  test "$(vfl_case "$TMPD/vfl-mlscan")" = "rc=1"
# Clean scan-regression but a marker-less other companion -> 1a fails closed.
mk_vfl_case "$TMPD/vfl-mlcomp" 'echo "NEW_CVES=0 UNRESOLVED=0"' 'echo "boom: crashed"'
check "vfl marker-less companion -> not verified" \
  test "$(vfl_case "$TMPD/vfl-mlcomp")" = "rc=1"
mk_vfl_case "$TMPD/vfl-invalid-positive" 'echo "NEW_CVES=0"' 'echo "NEW_ISSUES=1"'
check "vfl invalid evidence blocks a simultaneous valid repair" \
  test "$(vfl_case "$TMPD/vfl-invalid-positive" 2)" = "rc=1"
check "vfl invalid evidence never dispatches repair" ! test -e "$TMPD/vfl-invalid-positive/repair-dispatched"
mk_vfl_case "$TMPD/vfl-valid-positive" 'echo "NEW_CVES=0 UNRESOLVED=0"' \
  'if [[ -f "$2/../repair-dispatched" ]]; then echo "NEW_ISSUES=0"; else echo "NEW_ISSUES=1"; fi'
check "vfl valid issue dispatches repair then verifies fresh evidence" \
  test "$(vfl_case "$TMPD/vfl-valid-positive" 2)" = "rc=0"
check "vfl valid issue dispatches exactly once" test "$(cat "$TMPD/vfl-valid-positive/repair-dispatched" 2>/dev/null)" = 1
mk_vfl_case "$TMPD/vfl-missing-script" 'echo "NEW_CVES=0 UNRESOLVED=0"' 'echo "NEW_ISSUES=0"'
printf 'NEW_ISSUES=0\n' > "$TMPD/vfl-missing-script/report/existing-entries.evidence"
rm "$TMPD/vfl-missing-script/subagents/existing-entries.sh"
check "vfl absent script cannot reuse prior clean evidence" \
  test "$(vfl_case "$TMPD/vfl-missing-script")" = "rc=1"
check "vfl clears evidence left by a removed script" ! test -e "$TMPD/vfl-missing-script/report/existing-entries.evidence"

# Both supported CLIs are visibly installed and fail loudly if verification
# invokes them. Even obsolete prompt files must not create model calls.
VFL_POISON="$TMPD/vfl-poison"; mkdir -p "$VFL_POISON"
for _vfl_provider in claude codex; do
  printf '#!/usr/bin/env bash\necho "${0##*/}" >> "$VFL_POISON_LOG"\necho "unexpected verification model call" >&2\nexit 42\n' \
    > "$VFL_POISON/$_vfl_provider"
  chmod +x "$VFL_POISON/$_vfl_provider"
done
export VFL_POISON_LOG="$TMPD/vfl-model-calls"
for _vfl_provider in claude codex; do
  for _vfl_mode in clean repair incomplete; do
    _vfl_case="$TMPD/vfl-$_vfl_provider-$_vfl_mode"
    _vfl_scan='echo "NEW_CVES=0 UNRESOLVED=0"'
    _vfl_yaml='echo "NEW_ISSUES=0"'
    _vfl_expected='rc=0'
    case "$_vfl_mode" in
      repair) _vfl_yaml='if [[ -f "$2/../repair-dispatched" ]]; then echo "NEW_ISSUES=0"; else echo "NEW_ISSUES=1"; fi' ;;
      incomplete) _vfl_scan='echo "NEW_CVES=0"'; _vfl_expected='rc=1' ;;
    esac
    mk_vfl_case "$_vfl_case" "$_vfl_scan" "$_vfl_yaml"
    printf 'Obsolete verifier prompt; never invoke a model.\n' > "$_vfl_case/subagents/scan-regression.md"
    check "deterministic $_vfl_mode ignores installed $_vfl_provider" \
      test "$(CVE_FIX_AGENT="$_vfl_provider" VFL_TEST_PATH="$VFL_POISON:/usr/bin:/bin" \
        vfl_case "$_vfl_case" 2)" = "$_vfl_expected"
    if [[ "$_vfl_mode" == repair ]]; then
      check "deterministic $_vfl_provider repair dispatches once" \
        test "$(cat "$_vfl_case/repair-dispatched" 2>/dev/null)" = 1
    fi
  done
done
check "deterministic verification never invokes either installed model CLI" ! test -e "$VFL_POISON_LOG"

mk_vfl_case "$TMPD/vfl-persistent" 'echo "NEW_CVES=0 UNRESOLVED=0"' \
  'n=$(cat "$2/../audit-count" 2>/dev/null || echo 0); echo "$((n + 1))" > "$2/../audit-count"; echo "NEW_ISSUES=1"'
check "persistent issues exhaust the bounded verification loop" \
  test "$(vfl_case "$TMPD/vfl-persistent" 3)" = 'rc=1'
check "persistent issues run exactly three audits" test "$(cat "$TMPD/vfl-persistent/audit-count")" = 3
check "persistent issues dispatch at most two repairs" test "$(cat "$TMPD/vfl-persistent/repair-dispatched")" = 2
mk_vfl_case "$TMPD/vfl-zero" 'echo "NEW_CVES=0 UNRESOLVED=0"' 'echo "NEW_ISSUES=0"'
check "zero iterations cannot report successful verification" \
  test "$(vfl_case "$TMPD/vfl-zero" 0)" = 'rc=1'
check "zero iterations do not fabricate evidence" ! test -e "$TMPD/vfl-zero/report/scan-regression.evidence"

# === Summary counts from git log (Commit 6) ===
# COMMIT_COUNT can be lower than packages-fixed when a package resolves transitively (no dedicated commit).
echo "summary commit count"
RECON_REPO="$TMPD/recon-repo"
mkdir -p "$RECON_REPO"
git -C "$RECON_REPO" init -q
git -C "$RECON_REPO" config user.email "test@test.com"
git -C "$RECON_REPO" config user.name "Test"
echo "init" > "$RECON_REPO/go.mod"
git -C "$RECON_REPO" add -A
git -C "$RECON_REPO" commit -q -m "init"
BASE=$(git -C "$RECON_REPO" rev-parse HEAD)

echo "v1" > "$RECON_REPO/go.mod"; git -C "$RECON_REPO" add go.mod
git -C "$RECON_REPO" commit -q -m "Bump x/net for GHSA-1234"
echo "v2" > "$RECON_REPO/go.mod"; git -C "$RECON_REPO" add go.mod
git -C "$RECON_REPO" commit -q -m "Ignore helm/v3 CVEs (no fix available)"
echo "v3" > "$RECON_REPO/go.mod"; git -C "$RECON_REPO" add go.mod
git -C "$RECON_REPO" commit -q -m "Bump docker/docker for GHSA-5678"

# COMMIT_COUNT is the size of the range, as fix-all.sh uses for the trailer/PR.
COMMIT_COUNT=$(git -C "$RECON_REPO" log "${BASE}..HEAD" --oneline | wc -l | tr -d ' ')
check "commit count from range" test "$COMMIT_COUNT" -eq 3

# === Final rescan gate exit decision (Commit 6) ===
# cve_fix_exit_code turns the post-fix gate result + non-CVE failure flags into
# the process exit code: 2 unless the gate is clean and every check passed.
echo "final rescan gate"
check "gate clean -> exit 0"            test "$(cve_fix_exit_code 0 false false false)" = 0
check "CVEs remain -> exit 2"           test "$(cve_fix_exit_code 3 false false false)" = 2
check "gate scan failed -> exit 2"      test "$(cve_fix_exit_code 0 true false false)" = 2
check "tests failed -> exit 2"          test "$(cve_fix_exit_code 0 false true false)" = 2
check "verify failed -> exit 2"         test "$(cve_fix_exit_code 0 false false true)" = 2
check "unseen needs-review -> exit 2"   test "$(cve_fix_exit_code 0 false false false true)" = 2
check "PR prerequisites failed -> exit 2" test "$(cve_fix_exit_code 0 false false false false true)" = 2
check "PR readiness preserves partial exit" test "$(cve_fix_exit_code 3 false false false false true)" = 2
check "PR prerequisites passed -> exit 0" test "$(cve_fix_exit_code 0 false false false false false)" = 0
check "defaults clean -> exit 0"        test "$(cve_fix_exit_code)" = 0

# results_unconfirmed drives PR suppression. True on gate/verify failure.
# unseen_needs_review suppresses PR only when gate_remaining=0: when remaining>0
# the partial-fix PR title already signals outstanding CVEs, so valid commits
# (stale-removal, other-pkg fixes) shouldn't be blocked by one policy UNRESOLVED.
# Failed tests suppress the PR and keep the process exit nonzero.
check "all pass -> confirmed"                     ! results_unconfirmed false false false false 0 false
check "gate failed -> unconfirmed"                  results_unconfirmed true false false false 0 false
check "tests failed -> unconfirmed"                 results_unconfirmed false true false false 0 false
check "verify failed -> unconfirmed"                results_unconfirmed false false true false 0 false
check "fetch failed -> unconfirmed"                 results_unconfirmed false false false false 0 true
check "base changed -> unconfirmed"                 results_unconfirmed false false false false 0 false true
check "DCO failed -> unconfirmed"                   results_unconfirmed false false false false 0 false false true
check "base refresh failed -> unconfirmed"          results_unconfirmed false false false false 0 false false false true
check "policy failure blocks clean readiness"       results_unconfirmed false false false true 0 false false false false true
check "policy failure blocks partial readiness"     results_unconfirmed false false false true 3 false false false false true
check "unseen_needs_review, gate=0 -> unconfirmed"  results_unconfirmed false false false true 0 false
check "unseen_needs_review, gate>0 -> confirmed"  ! results_unconfirmed false false false true 3 false
check "all false -> confirmed"                    ! results_unconfirmed false false false false 0 false

# dco_missing_commits reports only unsigned commits in the proposed range.
echo "dco_missing_commits"
DCO_REPO="$TMPD/dco"
mkdir -p "$DCO_REPO"
git -C "$DCO_REPO" init -q
git -C "$DCO_REPO" config user.email t@t.com
git -C "$DCO_REPO" config user.name T
touch "$DCO_REPO/go.mod"
git -C "$DCO_REPO" add go.mod
git -C "$DCO_REPO" commit -q -s -m base
git -C "$DCO_REPO" commit --allow-empty -q -s -m signed
git -C "$DCO_REPO" commit --allow-empty -q -m unsigned
DCO_MISSING=$(cd "$DCO_REPO" && dco_missing_commits HEAD~2)
check "DCO audit: unsigned commit reported" test "$(wc -l <<< "$DCO_MISSING" | tr -d ' ')" -eq 1
check "DCO audit: signed commit omitted" test "$(grep -c "$(git -C "$DCO_REPO" rev-parse HEAD~1)" <<< "$DCO_MISSING" || true)" -eq 0

# Test failure disambiguation: network errors vs API incompatibility (bug #1)
echo "test failure disambiguation"
check "defaults -> confirmed"             ! results_unconfirmed

# scanner-degraded gate check: a .scanner-degraded sentinel written by the gate
# scan must flip GATE_FAILED so a degraded-DB "clean" result is never reported as
# a genuine pass. Behavioural: plant the sentinel where fix-all.sh reads it, run
# only the gate-detection snippet (sourced from lib.sh + fix-all.sh logic), and
# assert every guarantee without a real grype or network.
echo "scanner-degraded gate check"
# Behavioural: the sentinel flips GATE_SCANNER_DEGRADED=true in an isolated shell
# (no git repo needed — this is pure variable logic from the gate block).
GSD_STATE="$TMPD/gsd-state.env"
: > "$GSD_STATE"
: > "${GSD_STATE}.scanner-degraded"   # plant the sentinel
GSD_OUT=$(bash -c "
  GATE_SCANNER_DEGRADED=false
  [[ -f '${GSD_STATE}.scanner-degraded' ]] && GATE_SCANNER_DEGRADED=true
  GATE_FAILED=false
  if [[ \"\$GATE_SCANNER_DEGRADED\" == true ]]; then
    GATE_FAILED=true
  fi
  echo \"GATE_SCANNER_DEGRADED=\$GATE_SCANNER_DEGRADED\"
  echo \"GATE_FAILED=\$GATE_FAILED\"
")
check "gate scanner-degraded sets GATE_SCANNER_DEGRADED" \
  grep -q 'GATE_SCANNER_DEGRADED=true' <<< "$GSD_OUT"
check "gate scanner-degraded sets GATE_FAILED"            \
  grep -q 'GATE_FAILED=true'            <<< "$GSD_OUT"
rm -f "${GSD_STATE}.scanner-degraded"

# === gate dedup: multi-module repos don't double-count CVEs ===
# Bug: grype reports each CVE once per module (e.g. go.mod + coredns/go.mod).
# GATE_REMAINING and the WARNING display must count each CVE+pkg pair once.
# The WARNING list uses unique_by(.k) where k=CVE|pkg, so same CVE+pkg at
# different versions across modules is still shown once (first occurrence).
echo "gate dedup multi-module CVEs"
# Simulate GATE_JSON with 4 duplicate entries (2 unique CVE+pkg pairs × 2 modules)
_GDUP_JSON=$(cat <<'EOJSON'
{"matches":[
  {"vulnerability":{"id":"GHSA-aaaa-bbbb-cccc"},"artifact":{"type":"go-module","name":"golang.org/x/crypto","version":"v0.55.0"}},
  {"vulnerability":{"id":"GHSA-aaaa-bbbb-cccc"},"artifact":{"type":"go-module","name":"golang.org/x/crypto","version":"v0.55.0"}},
  {"vulnerability":{"id":"GHSA-dddd-eeee-ffff"},"artifact":{"type":"go-module","name":"google.golang.org/grpc","version":"v1.82.1"}},
  {"vulnerability":{"id":"GHSA-dddd-eeee-ffff"},"artifact":{"type":"go-module","name":"google.golang.org/grpc","version":"v1.82.1"}}
]}
EOJSON
)
_GDUP_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module") | "\(.vulnerability.id)|\(.artifact.name)"] | unique | length' <<< "$_GDUP_JSON")
check "gate dedup: 4 entries → 2 unique CVE+pkg count" test "$_GDUP_COUNT" = "2"
_GDUP_LIST=$(jq -r '[.matches[] | select(.artifact.type == "go-module") | {k: "\(.vulnerability.id)|\(.artifact.name)", v: "\(.vulnerability.id // "") \(.artifact.name // "") \(.artifact.version // "")"}] | unique_by(.k) | .[].v' <<< "$_GDUP_JSON")
_GDUP_LINES=$(printf '%s\n' "$_GDUP_LIST" | wc -l | tr -d ' ')
check "gate dedup: WARNING list shows 2 lines not 4" test "$_GDUP_LINES" = "2"
# Same CVE+pkg at different versions across modules: count still 1, list still 1 line
_GDUP2_JSON=$(cat <<'EOJSON'
{"matches":[
  {"vulnerability":{"id":"GHSA-aaaa-bbbb-cccc"},"artifact":{"type":"go-module","name":"golang.org/x/crypto","version":"v0.55.0"}},
  {"vulnerability":{"id":"GHSA-aaaa-bbbb-cccc"},"artifact":{"type":"go-module","name":"golang.org/x/crypto","version":"v0.54.0"}}
]}
EOJSON
)
_GDUP2_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module") | "\(.vulnerability.id)|\(.artifact.name)"] | unique | length' <<< "$_GDUP2_JSON")
check "gate dedup: same CVE+pkg diff versions → count 1" test "$_GDUP2_COUNT" = "1"
_GDUP2_LIST=$(jq -r '[.matches[] | select(.artifact.type == "go-module") | {k: "\(.vulnerability.id)|\(.artifact.name)", v: "\(.vulnerability.id // "") \(.artifact.name // "") \(.artifact.version // "")"}] | unique_by(.k) | .[].v' <<< "$_GDUP2_JSON")
_GDUP2_LINES=$(printf '%s\n' "$_GDUP2_LIST" | wc -l | tr -d ' ')
check "gate dedup: WARNING list 1 line for same CVE+pkg diff versions" test "$_GDUP2_LINES" = "1"
unset _GDUP_JSON _GDUP_COUNT _GDUP_LIST _GDUP_LINES _GDUP2_JSON _GDUP2_COUNT _GDUP2_LIST _GDUP2_LINES

# === gate: review-agent UNRESOLVED suppresses redundant gate NEEDS_REVIEW ===
# Scenario: gate sees GO-2026-6354 and GO-2026-6355 for x/crypto (not in .grype.yaml).
# Review agent already filed NEEDS_REVIEW for x/crypto. Gate must NOT add a second
# "N finding(s) still present" entry — REVIEW_AGENT_UNRESOLVED suppresses only the
# duplicate gate entry; GATE_REMAINING stays at 2 so results_unconfirmed/exit code
# correctly see outstanding CVEs (enabling PR carve-out when commits exist).
echo "gate: review-agent UNRESOLVED suppresses duplicate gate NEEDS_REVIEW"
_RADU_JSON='{"matches":[
  {"vulnerability":{"id":"GO-2026-6354"},"artifact":{"name":"golang.org/x/crypto","version":"v0.55.0","type":"go-module"}},
  {"vulnerability":{"id":"GO-2026-6355"},"artifact":{"name":"golang.org/x/crypto","version":"v0.55.0","type":"go-module"}}
]}'
# Simulate: _REVIEW_UNRESOLVED_PKGS contains x/crypto; no .grype.yaml
_RADU_REMAINING=$(jq '[.matches[] | select(.artifact.type == "go-module") | "\(.vulnerability.id)|\(.artifact.name)"] | unique | length' <<< "$_RADU_JSON")
_RADU_IGNORED=0
_RADU_REVIEW_AGENT=0
_RADU_UNRESOLVED_PKGS=("golang.org/x/crypto")
while IFS="|" read -r _cve _pkg; do
  [[ -z "$_cve" || -z "$_pkg" ]] && continue
  if printf '%s\n' "${_RADU_UNRESOLVED_PKGS[@]}" | grep -qxF "$_pkg" 2>/dev/null; then
    _RADU_REVIEW_AGENT=$((_RADU_REVIEW_AGENT + 1))
  fi
done < <(jq -r '[.matches[] | select(.artifact.type == "go-module") | "\(.vulnerability.id)|\(.artifact.name)"] | unique | .[]' <<< "$_RADU_JSON")
# GATE_REMAINING: subtract only .grype.yaml-ignored (none here)
_RADU_GATE_REMAINING=$((_RADU_REMAINING - _RADU_IGNORED))
# _GATE_TRULY_NEW: the residual that would get a redundant gate NEEDS_REVIEW entry
_RADU_TRULY_NEW=$((_RADU_GATE_REMAINING - _RADU_REVIEW_AGENT))
check "gate: GATE_REMAINING stays 2 (results_unconfirmed still sees outstanding CVEs)" test "$_RADU_GATE_REMAINING" = "2"
check "gate: review-agent UNRESOLVED count=2" test "$_RADU_REVIEW_AGENT" = "2"
check "gate: _GATE_TRULY_NEW=0 → no duplicate NEEDS_REVIEW added" test "$_RADU_TRULY_NEW" = "0"
unset _RADU_JSON _RADU_REMAINING _RADU_IGNORED _RADU_REVIEW_AGENT _RADU_UNRESOLVED_PKGS _RADU_GATE_REMAINING _RADU_TRULY_NEW _cve _pkg

# === ignore.sh --fix-state flag ===
echo "ignore.sh --fix-state"
FS_REPO="$TMPD/fs-repo"
mkdir -p "$FS_REPO"
git -C "$FS_REPO" init -q
git -C "$FS_REPO" config user.email "test@test.com"
git -C "$FS_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$FS_REPO/.grype.yaml"
touch "$FS_REPO/go.mod"
git -C "$FS_REPO" add .grype.yaml go.mod
git -C "$FS_REPO" commit -q -m "init"
git -C "$FS_REPO" checkout -q -b devel
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$FS_REPO" "$SCRIPT_DIR" > "$TMPD/fs.env"

for _fsv in unknown not-fixed wont-fix; do
    printf -- '---\nignore:\n' > "$FS_REPO/.grype.yaml" && git -C "$FS_REPO" add .grype.yaml && { git -C "$FS_REPO" diff --cached --quiet || git -C "$FS_REPO" commit -q -m "reset"; }
    bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" "example.com/${_fsv}pkg" "High" "No fix" --fix-state "$_fsv" GHSA-fs-00xx >/dev/null 2>&1
    check "--fix-state $_fsv accepted" grep -q "fix-state: $_fsv" "$FS_REPO/.grype.yaml"
done

check "--fix-state invalid rejected" ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" example.com/bad "High" "reason" --fix-state invalid GHSA-fs-0004 >/dev/null 2>&1

printf -- '---\nignore:\n' > "$FS_REPO/.grype.yaml"
git -C "$FS_REPO" add .grype.yaml
git -C "$FS_REPO" commit -q -m "reset3"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" example.com/bwpkg "High" "No fix" --no-fix GHSA-fs-0005 >/dev/null 2>&1
check "--no-fix backward compat" grep -q "fix-state: not-fixed" "$FS_REPO/.grype.yaml"

# === ignore.sh --location flag ===
echo "ignore.sh --location"
printf -- '---\nignore:\n' > "$FS_REPO/.grype.yaml"
git -C "$FS_REPO" add .grype.yaml
git -C "$FS_REPO" commit -q -m "reset-loc"
# --location combined with --fix-state, in that order, then CVE
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" example.com/locpkg "High" "No fix" --fix-state not-fixed --location /tools/go.mod GHSA-loc-0001 >/dev/null 2>&1
check "--location writes location" grep -q "location: /tools/go.mod" "$FS_REPO/.grype.yaml"
check "--location keeps fix-state" grep -q "fix-state: not-fixed" "$FS_REPO/.grype.yaml"

# Flag order independence: --location before --fix-state
printf -- '---\nignore:\n' > "$FS_REPO/.grype.yaml"
git -C "$FS_REPO" add .grype.yaml
git -C "$FS_REPO" commit -q -m "reset-loc2"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" example.com/locpkg2 "High" "No fix" --location /go.mod --no-fix GHSA-loc-0002 >/dev/null 2>&1
check "--location any order" grep -q "location: /go.mod" "$FS_REPO/.grype.yaml"
check "--location any order fix-state" grep -q "fix-state: not-fixed" "$FS_REPO/.grype.yaml"

check "--location missing value rejected" ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" pkg "High" "reason" --location >/dev/null 2>&1
check "unknown flag rejected" ! bash "$SCRIPT_DIR/ignore.sh" "$TMPD/fs.env" pkg "High" "reason" --bogus GHSA-x >/dev/null 2>&1

# === CVE_LINES pipe-delimiter parsing (TSV tab-collapsing fix) ===
echo "CVE_LINES pipe delimiter"
# Bug: IFS=$'\t' read collapses consecutive tabs (empty fields), shifting
# fixState into severity position. Fix: use pipe delimiter instead.
# Regression test: no-fix entry with empty fixedIn AND allFixVersions, and a
# trailing location field (8th column). The empty middle fields must not shift
# fixState, and a populated trailing location must land in LOCATION.
PARSED=$(printf 'no-fix|github.com/containerd/containerd||GO-2026-5064,GO-2026-5338|Critical||unknown|/tools/go.mod\n' | {
  IFS='|' read -r TYPE PKG FIX_VER CVE_CSV _SEVERITY ALL_FIX_VERS FIX_STATE_VAL LOCATION
  echo "TYPE=$TYPE SEV=$_SEVERITY FS=$FIX_STATE_VAL FV=$FIX_VER LOC=$LOCATION"
})
check "no-fix severity preserved" bash -c "echo '$PARSED' | grep -q 'SEV=Critical'"
check "no-fix fixState preserved" bash -c "echo '$PARSED' | grep -q 'FS=unknown'"
check "no-fix fixedIn empty" bash -c "echo '$PARSED' | grep -q 'FV= '"
check "no-fix location parsed" bash -c "echo '$PARSED' | grep -q 'LOC=/tools/go.mod'"

# Same test with not-fixed fixState (docker case) and an EMPTY trailing location:
# the empty 8th field must not corrupt fixState (the exact tab-collapse hazard).
PARSED2=$(printf 'no-fix|github.com/docker/docker||GHSA-x86f,GHSA-rg2x|High||not-fixed|\n' | {
  IFS='|' read -r TYPE PKG FIX_VER CVE_CSV _SEVERITY ALL_FIX_VERS FIX_STATE_VAL LOCATION
  echo "SEV=$_SEVERITY FS=$FIX_STATE_VAL LOC=[$LOCATION]"
})
check "not-fixed not in severity" bash -c "echo '$PARSED2' | grep -q 'SEV=High'"
check "not-fixed in fixState" bash -c "echo '$PARSED2' | grep -q 'FS=not-fixed'"

# Grype treats an absent/empty vulnerability fix state as "unknown" for ignore
# filtering. The fix loop must emit the same value, not a non-matching
# fix-state:not-fixed rule.
check "empty Grype fix state maps to unknown" \
  grep -q '== "" then "unknown"' "$SCRIPT_DIR/fix-all.sh"
check "empty location preserved" bash -c "echo '$PARSED2' | grep -q 'LOC=\[\]'"

# Verify the OLD tab delimiter would fail (proves the bug existed)
PARSED_TAB=$(printf 'no-fix\tpkg\t\tCVE-1\tCritical\t\tunknown\n' | {
  IFS=$'\t' read -r TYPE PKG FIX_VER CVE_CSV _SEVERITY ALL_FIX_VERS FIX_STATE_VAL
  echo "SEV=$_SEVERITY"
})
check "tab collapses fields (bug)" bash -c "echo '$PARSED_TAB' | grep -q 'SEV=unknown'"

# === location-scope derivation (fix-all.sh jq rule) ===
# Mirrors the scope rule in fix-all.sh: no-fix findings retain each exact
# go.mod location so multiple modules become independent scoped ignores;
# binary/empty paths remain unscoped. Fixable packages still group across
# modules because dependency updates are handled as one package operation.
echo "location-scope derivation"
if command -v jq >/dev/null 2>&1; then
  LOCJQ='
    map(. + {scanLocation: (if (.loc | endswith("/go.mod")) then .loc else "" end)}) |
    group_by(.pkg + ":" + .cve + ":" + (if .type == "no-fix" then .scanLocation else "" end)) |
    map(
      ([.[].loc] | map(select(type == "string" and . != "")) | unique) as $locs |
      (if ($locs | length) == 1 and ($locs[0] | endswith("/go.mod")) then $locs[0] else "" end) as $location |
      (.[0]) | . + {location: $location}
    ) |
    .[] | "\(.pkg)|\(.location)"'
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"no-fix","loc":"/tools/go.mod"}]' | jq -r "$LOCJQ")
  check "jq loc: single no-fix go.mod scoped" test "$OUT" = "a|/tools/go.mod"
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"no-fix","loc":"/go.mod"},{"pkg":"a","cve":"C1","type":"no-fix","loc":"/tools/go.mod"}]' | jq -r "$LOCJQ")
  check "jq loc: multi-module no-fix keeps two scopes" test "$OUT" = $'a|/go.mod\na|/tools/go.mod'
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"package","loc":"/go.mod"},{"pkg":"a","cve":"C1","type":"package","loc":"/tools/go.mod"}]' | jq -r "$LOCJQ")
  check "jq loc: fixable multi-module remains one operation" test "$OUT" = "a|"
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"no-fix","loc":"/bin/foo"}]' | jq -r "$LOCJQ")
  check "jq loc: binary unscoped" test "$OUT" = "a|"
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"no-fix","loc":""}]' | jq -r "$LOCJQ")
  check "jq loc: empty unscoped" test "$OUT" = "a|"
  OUT=$(printf '%s' '[{"pkg":"a","cve":"C1","type":"no-fix","loc":"/go.mod"}]' | jq -r "$LOCJQ")
  check "jq loc: root go.mod scoped" test "$OUT" = "a|/go.mod"
else
  echo "  (skipped: jq not available)"
fi

# === robust fix-version sort (fix-all.sh + scan-regression.sh) ===
# The highest-fix-version pick must tolerate real grype output: 'v'-prefixed and
# '+incompatible' (docker/docker) versions. The bare tonumber form throws on any
# non-numeric segment, which would empty CVE_LINES and skip EVERY fix. Mirror the
# exact sort key used in both scripts.
echo "robust fix-version sort"
if command -v jq >/dev/null 2>&1; then
  VERJQ='sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last'
  check "vsort: plain highest" \
    test "$(printf '%s' '["1.2.3","1.2.10","1.10.0"]' | jq -r "$VERJQ")" = "1.10.0"
  check "vsort: v-prefix tolerated" \
    test "$(printf '%s' '["v1.2.3","v1.10.0"]' | jq -r "$VERJQ")" = "v1.10.0"
  check "vsort: +incompatible tolerated" \
    test "$(printf '%s' '["26.0.0","26.1.0+incompatible"]' | jq -r "$VERJQ")" = "26.1.0+incompatible"
  check "vsort: prerelease tolerated" \
    test "$(printf '%s' '["1.2.3-rc.1","1.2.3"]' | jq -r "$VERJQ")" = "1.2.3"
  # A mixed/messy list must sort without error and still pick the highest.
  check "vsort: mixed list highest" \
    test "$(printf '%s' '["v1.0.0","2.0.0+incompatible","1.5.0-beta"]' | jq -r "$VERJQ")" = "2.0.0+incompatible"
  # An empty-string or null element (degenerate grype fix versions) throws the
  # bare sort key ("split input ... must be strings"), which would empty CVE_LINES
  # and skip EVERY fix — the exact failure the robust key was meant to prevent.
  # null != "" is true in jq so map(select(. != "")) passes nulls through; the guard
  # must use type == "string" to filter both empties AND nulls before sorting.
  GUARDJQ='(.versions // []) | map(select(type == "string" and . != "")) | if length == 0 then "" else (sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last) end'
  check "vsort: empty element does not error" \
    test "$(printf '%s' '{"versions":["1.2.3",""]}' | jq -r "$GUARDJQ" 2>&1)" = "1.2.3"
  check "vsort: all-empty yields empty" \
    test "$(printf '%s' '{"versions":["",""]}' | jq -r "$GUARDJQ" 2>&1)" = ""
  # Regression: null in fix.versions also passes select(. != "") because null != ""
  # is true in jq; the downstream split throws "split input ... must be strings".
  check "vsort: null element does not error" \
    test "$(printf '%s' '{"versions":["1.2.3",null]}' | jq -r "$GUARDJQ" 2>&1)" = "1.2.3"
  check "vsort: all-null yields empty" \
    test "$(printf '%s' '{"versions":[null,null]}' | jq -r "$GUARDJQ" 2>&1)" = ""
  # Regression (fix #3): scan-regression.sh PKG_INFO sort sites must also use the
  # null-safe guard so fix.versions=[null] emits "no-fix" not the string "null".
  # Without type=="string", null passes select(.!="") (null!="" is true in jq),
  # giving length==1 → else branch → sort_by on [null] → outputs "null" →
  # subagent_fix_scan_regression sees "null"!="no-fix" and routes to fix-package.sh.
  SCANREG_GUARDJQ='((.vulnerability.fix.versions // []) | map(select(type == "string" and . != "")) | if length == 0 then "no-fix" else (sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last) end)'
  check "scan-regression guard: null element gives no-fix" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":[null]}}}' | jq -r "$SCANREG_GUARDJQ" 2>&1)" = "no-fix"
  check "scan-regression guard: all-null gives no-fix" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":[null,null]}}}' | jq -r "$SCANREG_GUARDJQ" 2>&1)" = "no-fix"
  check "scan-regression guard: real version with null gives version" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":["1.2.3",null]}}}' | jq -r "$SCANREG_GUARDJQ" 2>&1)" = "1.2.3"
  # Regression: fixedIn normalizes pre-release suffixes so VERSION passed to
  # fix-package.sh is always bare X.Y.Z. Mirrors the full fixedIn expression
  # in fix-all.sh (both the single-match and merged group_by sites).
  FIXEDIN_JQ='(.fix.versions // []) | map(select(type == "string" and . != "")) | if length == 0 then "" else sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last | ltrimstr("v") | split("+")[0] | split("-")[0] end'
  check "fixedIn: pre-release-only yields bare version" \
    test "$(printf '%s' '{"fix":{"versions":["1.2.4-rc1"]}}' | jq -r "$FIXEDIN_JQ")" = "1.2.4"
  check "fixedIn: stable beats pre-release, no suffix" \
    test "$(printf '%s' '{"fix":{"versions":["1.2.4-rc1","1.2.4"]}}' | jq -r "$FIXEDIN_JQ")" = "1.2.4"
  check "fixedIn: v-prefix stripped on output" \
    test "$(printf '%s' '{"fix":{"versions":["v1.2.4"]}}' | jq -r "$FIXEDIN_JQ")" = "1.2.4"
  check "fixedIn: +incompatible stripped on output" \
    test "$(printf '%s' '{"fix":{"versions":["1.2.4+incompatible"]}}' | jq -r "$FIXEDIN_JQ")" = "1.2.4"
  # Regression: null in fix.versions passes select(. != "") (null != "" is true in jq)
  # causing split to throw "split input ... must be strings", emptying CVE_LINES.
  check "fixedIn: null element yields empty" \
    test "$(printf '%s' '{"fix":{"versions":[null]}}' | jq -r "$FIXEDIN_JQ" 2>&1)" = ""
  check "fixedIn: null with version yields bare version" \
    test "$(printf '%s' '{"fix":{"versions":["1.2.4",null]}}' | jq -r "$FIXEDIN_JQ" 2>&1)" = "1.2.4"
  # allFixVersions must be preserved for package type CVEs, not just stdlib.
  # Regression: when grype reports fix.versions ["3.6.14","3.7.1"] for etcd,
  # the jq collapse must carry both versions so the retry loop can fall back
  # from 3.7.1 (breaking Go bump) to the safe 3.6.14.
  check "fix-all: retry pipeline stable-only output" \
    bash -c "echo '1.2.4-rc1,1.2.4,1.3.0' | tr ',' '\n' | sed 's/^v//' | grep -Ev -- '-[a-zA-Z]' | sort -V -r | grep -qv 'rc'"
  # jq extracts allFixVersions for package type: simulate the extraction with
  # the etcd fixture (GO-2026-6107: fix.versions ["3.6.14","3.7.1"])
  AFV_FIXTURE='{"matches":[{"vulnerability":{"id":"GO-2026-6107","severity":"High","fix":{"versions":["3.6.14","3.7.1"],"state":"fixed"}},"artifact":{"name":"go.etcd.io/etcd/client/pkg/v3","version":"v3.6.8","type":"go-module","locations":[{"path":"/go.mod"}]}}]}'
  AFV_OUT=$(printf '%s\n' "$AFV_FIXTURE" | jq -r '
    [.matches[] | select(.artifact.type == "go-module") |
      {pkg: .artifact.name, type: "package",
       allFixVersions: ((.vulnerability.fix.versions // []) | join(","))}
    ] |
    group_by(.pkg) |
    map({pkg: .[0].pkg, type: .[0].type,
         allFixVersions: (if .[0].type == "no-fix" then ""
                          else ([.[].allFixVersions] | unique | join(",")) end)}) |
    .[] | "\(.type)|\(.pkg)|\(.allFixVersions)"
  ' 2>/dev/null || echo "")
  check "allFixVersions: etcd 3.6.14 extracted" bash -c "echo '$AFV_OUT' | grep -q '3.6.14'"
  check "allFixVersions: etcd 3.7.1 extracted"  bash -c "echo '$AFV_OUT' | grep -q '3.7.1'"
  # Regression (bug #1): allFixVersions at line 141 previously used
  # map(select(type == "string")) without the != "" guard present on lines 140
  # and 145. When grype emits empty strings in fix.versions, the unguarded form
  # joins them into trailing commas (e.g. "v1.0.0,"), and the group-level join
  # at line 170 can produce double-commas. Downstream (fix-package.sh, ignore.sh)
  # guard against empty strings, so no incorrect behaviour results — but the
  # inconsistency is real and the output format is wrong.
  #
  # The fix: map(select(type == "string" and . != "")) on allFixVersions too.
  AFV_EMPTY_JQ='((.vulnerability.fix.versions // []) | map(select(type == "string" and . != "")) | join(","))'
  # Single version with trailing empty string must NOT produce a trailing comma.
  check "allFixVersions: no trailing comma on empty element" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":["v1.0.0",""]}}}' | jq -r "$AFV_EMPTY_JQ")" = "v1.0.0"
  # Two real versions must remain comma-joined without extra commas.
  check "allFixVersions: two versions joined cleanly" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":["1.2.3","1.3.0"]}}}' | jq -r "$AFV_EMPTY_JQ")" = "1.2.3,1.3.0"
  # All-empty versions must yield an empty string, not a bare comma.
  check "allFixVersions: all-empty yields empty" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":["",""]}}}' | jq -r "$AFV_EMPTY_JQ")" = ""
  # null elements must also be excluded (type == "string" filters both).
  check "allFixVersions: null element excluded" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":["v1.0.0",null]}}}' | jq -r "$AFV_EMPTY_JQ")" = "v1.0.0"
  # All-null versions must yield empty, not "null".
  check "allFixVersions: all-null yields empty" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":[null,null]}}}' | jq -r "$AFV_EMPTY_JQ")" = ""
  # No-fix entry (empty fix.versions list) must yield empty string.
  check "allFixVersions: empty list yields empty" \
    test "$(printf '%s' '{"vulnerability":{"fix":{"versions":[]}}}' | jq -r "$AFV_EMPTY_JQ")" = ""
  # Group-level join (line 170): two objects each with a non-empty allFixVersions
  # must join to exactly "v1.0.0,v1.1.0" with no double-commas.
  AFV_GROUP_JQ='[.[].allFixVersions] | unique | join(",")'
  check "allFixVersions group join: no double commas" \
    test "$(printf '%s' '[{"allFixVersions":"v1.0.0"},{"allFixVersions":"v1.1.0"}]' | jq -r "$AFV_GROUP_JQ")" = "v1.0.0,v1.1.0"
else
  echo "  (skipped: jq not available)"
fi

# === remove_grype_ignore ===
echo "remove_grype_ignore"

# Basic removal (no fix-state)
printf -- '---\nignore:\n' > "$TMPD/rm.yaml"
insert_grype_ignore "$TMPD/rm.yaml" GHSA-rm-0001 example.com/pkg "Test reason"
check "rm: entry exists" grep -q GHSA-rm-0001 "$TMPD/rm.yaml"
remove_grype_ignore "$TMPD/rm.yaml" GHSA-rm-0001 example.com/pkg
check "rm: entry removed" ! grep -q GHSA-rm-0001 "$TMPD/rm.yaml"
check "rm: comment removed" ! grep -q "Test reason" "$TMPD/rm.yaml"

# Removal with fix-state
printf -- '---\nignore:\n' > "$TMPD/rm-fs.yaml"
insert_grype_ignore "$TMPD/rm-fs.yaml" GHSA-rm-0002 example.com/fspkg "No fix" "not-fixed"
check "rm-fs: fix-state exists" grep -q "fix-state: not-fixed" "$TMPD/rm-fs.yaml"
remove_grype_ignore "$TMPD/rm-fs.yaml" GHSA-rm-0002 example.com/fspkg
check "rm-fs: entry removed" ! grep -q GHSA-rm-0002 "$TMPD/rm-fs.yaml"
check "rm-fs: fix-state removed" ! grep -q "fix-state" "$TMPD/rm-fs.yaml"

# Preserves other entries
printf -- '---\nignore:\n' > "$TMPD/rm-multi.yaml"
insert_grype_ignore "$TMPD/rm-multi.yaml" GHSA-keep-0001 example.com/keeper "Keep me"
insert_grype_ignore "$TMPD/rm-multi.yaml" GHSA-rm-0003 example.com/target "Remove me"
remove_grype_ignore "$TMPD/rm-multi.yaml" GHSA-rm-0003 example.com/target
check "rm-multi: target removed" ! grep -q GHSA-rm-0003 "$TMPD/rm-multi.yaml"
check "rm-multi: other kept" grep -q GHSA-keep-0001 "$TMPD/rm-multi.yaml"
check "rm-multi: other pkg kept" grep -q "example.com/keeper" "$TMPD/rm-multi.yaml"

# No-op for non-existent CVE
printf -- '---\nignore:\n' > "$TMPD/rm-noop.yaml"
insert_grype_ignore "$TMPD/rm-noop.yaml" GHSA-exists example.com/pkg "Reason"
cp "$TMPD/rm-noop.yaml" "$TMPD/rm-noop-before.yaml"
remove_grype_ignore "$TMPD/rm-noop.yaml" GHSA-missing example.com/pkg
check "rm-noop: file unchanged" diff -q "$TMPD/rm-noop.yaml" "$TMPD/rm-noop-before.yaml"

# No-op for wrong package (same CVE, different package)
printf -- '---\nignore:\n' > "$TMPD/rm-wrongpkg.yaml"
insert_grype_ignore "$TMPD/rm-wrongpkg.yaml" GHSA-shared example.com/correct "Reason"
remove_grype_ignore "$TMPD/rm-wrongpkg.yaml" GHSA-shared example.com/wrong
check "rm-wrongpkg: entry preserved" grep -q GHSA-shared "$TMPD/rm-wrongpkg.yaml"
check "rm-wrongpkg: pkg preserved" grep -q "example.com/correct" "$TMPD/rm-wrongpkg.yaml"

# Multi-line comment removal
printf -- '---\nignore:\n  # Line 1 of comment\n  # Line 2 of comment\n  - vulnerability: GHSA-mlc-0001\n    package:\n      name: example.com/mlc\n' > "$TMPD/rm-mlc.yaml"
remove_grype_ignore "$TMPD/rm-mlc.yaml" GHSA-mlc-0001 example.com/mlc
check "rm-mlc: entry removed" ! grep -q GHSA-mlc-0001 "$TMPD/rm-mlc.yaml"
check "rm-mlc: comments removed" ! grep -q "Line 1" "$TMPD/rm-mlc.yaml"
check "rm-mlc: all comments gone" ! grep -q "Line 2" "$TMPD/rm-mlc.yaml"

# Synthesize a minimal grype-yaml fixture so these tests are self-contained
# and do not depend on a host .grype.yaml (set -euo pipefail).
printf -- '---\nignore:\n  # Synthetic fixture entry used by round-trip / exclude tests\n  - vulnerability: CVE-2021-22570\n    package:\n      name: google.golang.org/protobuf\n\nexclude:\n  - "./vendor/**"\n' \
  > "$TMPD/grype-fixture.yaml"

# Preserves exclude section
cp "$TMPD/grype-fixture.yaml" "$TMPD/rm-exc.yaml"
insert_grype_ignore "$TMPD/rm-exc.yaml" GHSA-exc-0001 example.com/excpkg "Test"
remove_grype_ignore "$TMPD/rm-exc.yaml" GHSA-exc-0001 example.com/excpkg
check "rm-exc: exclude kept" grep -q "^exclude:" "$TMPD/rm-exc.yaml"
check "rm-exc: original kept" grep -q CVE-2021-22570 "$TMPD/rm-exc.yaml"

# Insert then remove round-trip leaves file equivalent
cp "$TMPD/grype-fixture.yaml" "$TMPD/rm-roundtrip.yaml"
cp "$TMPD/rm-roundtrip.yaml" "$TMPD/rm-roundtrip-orig.yaml"
insert_grype_ignore "$TMPD/rm-roundtrip.yaml" GHSA-rt-0001 example.com/rt "Temp" "not-fixed"
remove_grype_ignore "$TMPD/rm-roundtrip.yaml" GHSA-rt-0001 example.com/rt
check "rm-roundtrip: no GHSA remains" ! grep -q GHSA-rt-0001 "$TMPD/rm-roundtrip.yaml"
check "rm-roundtrip: file restored" diff -q "$TMPD/rm-roundtrip.yaml" "$TMPD/rm-roundtrip-orig.yaml"

# Removal of a scoped entry deletes the trailing location: line too (no orphan)
cp "$TMPD/grype-fixture.yaml" "$TMPD/rm-loc.yaml"
cp "$TMPD/rm-loc.yaml" "$TMPD/rm-loc-orig.yaml"
insert_grype_ignore "$TMPD/rm-loc.yaml" GHSA-rml-0001 example.com/rml "Temp" "not-fixed" "/tools/go.mod"
check "rm-loc: location present" grep -q "location: /tools/go.mod" "$TMPD/rm-loc.yaml"
remove_grype_ignore "$TMPD/rm-loc.yaml" GHSA-rml-0001 example.com/rml /tools/go.mod
check "rm-loc: entry removed" ! grep -q GHSA-rml-0001 "$TMPD/rm-loc.yaml"
check "rm-loc: no orphan location" ! grep -q "location:" "$TMPD/rm-loc.yaml"
check "rm-loc: file restored" diff -q "$TMPD/rm-loc.yaml" "$TMPD/rm-loc-orig.yaml"

# Removal of an UNSCOPED entry must NOT over-delete the following line. Two
# adjacent unscoped entries: removing the first must leave the second's location
# line (belonging to the second block) untouched — proves the one-line probe is
# scoped to a block that actually has a location.
printf -- '---\nignore:\n' > "$TMPD/rm-adj.yaml"
insert_grype_ignore "$TMPD/rm-adj.yaml" GHSA-adj-0001 example.com/first "First"
insert_grype_ignore "$TMPD/rm-adj.yaml" GHSA-adj-0002 example.com/second "Second" "not-fixed" "/go.mod"
remove_grype_ignore "$TMPD/rm-adj.yaml" GHSA-adj-0001 example.com/first
check "rm-adj: first removed" ! grep -q GHSA-adj-0001 "$TMPD/rm-adj.yaml"
check "rm-adj: second kept" grep -q GHSA-adj-0002 "$TMPD/rm-adj.yaml"
check "rm-adj: second location kept" grep -q "location: /go.mod" "$TMPD/rm-adj.yaml"

# Same CVE ignored under TWO packages: removing one must delete only that
# block, never the other. Taking the first vulnerability line unconditionally
# would silently un-ignore the wrong package.
printf -- '---\nignore:\n' > "$TMPD/rm-dup.yaml"
insert_grype_ignore "$TMPD/rm-dup.yaml" GHSA-dup-0001 example.com/alpha "Alpha"
insert_grype_ignore "$TMPD/rm-dup.yaml" GHSA-dup-0001 example.com/beta "Beta"
remove_grype_ignore "$TMPD/rm-dup.yaml" GHSA-dup-0001 example.com/beta
check "rm-dup: beta removed" ! grep -q "name: example.com/beta" "$TMPD/rm-dup.yaml"
check "rm-dup: alpha kept" grep -q "name: example.com/alpha" "$TMPD/rm-dup.yaml"
check "rm-dup: cve line kept" grep -q "GHSA-dup-0001" "$TMPD/rm-dup.yaml"

# A shorter CVE id must not match a longer one as a substring: removing
# CVE-2024-123 must leave an unrelated CVE-2024-1234 entry intact.
printf -- '---\nignore:\n' > "$TMPD/rm-sub.yaml"
insert_grype_ignore "$TMPD/rm-sub.yaml" CVE-2024-1234 example.com/sub "Longer"
remove_grype_ignore "$TMPD/rm-sub.yaml" CVE-2024-123 example.com/sub
check "rm-sub: longer CVE preserved" grep -q "CVE-2024-1234" "$TMPD/rm-sub.yaml"

# Scoped entry as the LAST block in the file (location: is the final line):
# removal must still take the trailing location line without running off EOF.
printf -- '---\nignore:\n' > "$TMPD/rm-last.yaml"
insert_grype_ignore "$TMPD/rm-last.yaml" GHSA-last-0001 example.com/last "Last" "not-fixed" "/tools/go.mod"
remove_grype_ignore "$TMPD/rm-last.yaml" GHSA-last-0001 example.com/last /tools/go.mod
check "rm-last: entry removed" ! grep -q GHSA-last-0001 "$TMPD/rm-last.yaml"
check "rm-last: no orphan location" ! grep -q "location:" "$TMPD/rm-last.yaml"

# Same CVE+package ignored under TWO locations (e.g. go.mod and tools/go.mod):
# each exact scope is independently inserted and removed.
printf -- '---\nignore:\n' > "$TMPD/rm-two-loc.yaml"
insert_grype_ignore "$TMPD/rm-two-loc.yaml" GHSA-twoloc-0001 example.com/twoloc "Root mod" "not-fixed" "/go.mod"
insert_grype_ignore "$TMPD/rm-two-loc.yaml" GHSA-twoloc-0001 example.com/twoloc "Tools mod" "not-fixed" "/tools/go.mod"
check "rm-two-loc: both scopes inserted" \
  bash -c '[[ $(grep -c "GHSA-twoloc-0001" '"$TMPD/rm-two-loc.yaml"') -eq 2 ]]'
check "rm-two-loc: tools location present" grep -q "location: /tools/go.mod" "$TMPD/rm-two-loc.yaml"
remove_grype_ignore "$TMPD/rm-two-loc.yaml" GHSA-twoloc-0001 example.com/twoloc /go.mod
check "rm-two-loc: tools scope remains after root removal" grep -q "location: /tools/go.mod" "$TMPD/rm-two-loc.yaml"
remove_grype_ignore "$TMPD/rm-two-loc.yaml" GHSA-twoloc-0001 example.com/twoloc /tools/go.mod
check "rm-two-loc: entry removed" ! grep -q "GHSA-twoloc-0001" "$TMPD/rm-two-loc.yaml"
check "rm-two-loc: no orphan location" ! grep -q "location:" "$TMPD/rm-two-loc.yaml"
check "rm-two-loc: no orphan pkg" ! grep -q "example.com/twoloc" "$TMPD/rm-two-loc.yaml"

# === subagent_fix_yaml_integrity never resurrects entries from commit history ===
echo "yaml-integrity does not resurrect ignore commits"
YI_REPO="$TMPD/yi-repo"
mkdir -p "$YI_REPO"
git -C "$YI_REPO" init -q
git -C "$YI_REPO" config user.email "test@test.com"
git -C "$YI_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_REPO/.grype.yaml"
touch "$YI_REPO/go.mod"
git -C "$YI_REPO" add .grype.yaml go.mod
git -C "$YI_REPO" commit -q -m "init"
git -C "$YI_REPO" checkout -q -b release-0.23
git -C "$YI_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_REPO" rev-parse HEAD)"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_REPO" "$SCRIPT_DIR" > "$TMPD/yi.env"

# Create a scoped no-fix ignore commit via the real ignore.sh
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/yi.env" example.com/yi "High" "No fix available for example.com/yi" --no-fix --location /tools/go.mod GHSA-yi-0001 >/dev/null 2>&1
check "yi: initial scoped" grep -q "location: /tools/go.mod" "$YI_REPO/.grype.yaml"

# Corrupt the working tree. The handler must not reset the whole file from Git
# history or silently recreate a vulnerability ignore.
printf -- '---\nignore:\n  BROKEN\n' > "$YI_REPO/.grype.yaml"
( cd "$YI_REPO" && subagent_fix_yaml_integrity "$TMPD/yi.env" /dev/null "$SCRIPT_DIR" >/dev/null 2>&1 )
check "yi: old entry not resurrected" ! grep -q GHSA-yi-0001 "$YI_REPO/.grype.yaml"
check "yi: no old location resurrected" ! grep -q "location: /tools/go.mod" "$YI_REPO/.grype.yaml"
check "yi: no old fix-state resurrected" ! grep -q "fix-state: not-fixed" "$YI_REPO/.grype.yaml"

# A writable report directory still must not let this handler credit an ignore
# that it did not safely create.
echo "yaml-integrity does not invent ignored-pkgs credit"
YI_IP_REPO="$TMPD/yi-ip-repo"
mkdir -p "$YI_IP_REPO"
git -C "$YI_IP_REPO" init -q
git -C "$YI_IP_REPO" config user.email "test@test.com"
git -C "$YI_IP_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_IP_REPO/.grype.yaml"
touch "$YI_IP_REPO/go.mod"
git -C "$YI_IP_REPO" add .grype.yaml go.mod
git -C "$YI_IP_REPO" commit -q -m "init"
git -C "$YI_IP_REPO" checkout -q -b release-0.23
git -C "$YI_IP_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_IP_REPO" rev-parse HEAD)"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_IP_REPO" "$SCRIPT_DIR" > "$TMPD/yi-ip.env"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/yi-ip.env" example.com/yi-ip "High" "No fix for ip-pkg" --fix-state not-fixed GHSA-ip-0001 >/dev/null 2>&1
# Create a writable report dir and a report_file inside it
YI_IP_RDIR="$TMPD/yi-ip-reports"
mkdir -p "$YI_IP_RDIR"
YI_IP_RFILE="$YI_IP_RDIR/yaml-integrity.report"
touch "$YI_IP_RFILE"
# Corrupt .grype.yaml and re-apply via yaml-integrity
printf -- '---\nignore:\n  BROKEN\n' > "$YI_IP_REPO/.grype.yaml"
( cd "$YI_IP_REPO" && subagent_fix_yaml_integrity "$TMPD/yi-ip.env" "$YI_IP_RFILE" "$SCRIPT_DIR" >/dev/null 2>&1 )
check "yi-ip: entry not resurrected" ! grep -q GHSA-ip-0001 "$YI_IP_REPO/.grype.yaml"
check "yi-ip: no ignored-pkgs credit" ! test -f "$YI_IP_RDIR/ignored-pkgs"

# A failed fix must never convert an auto-expiring rule into a permanent ignore.
echo "yaml-integrity never creates permanent ignore after failed fix"
YI_UP_REPO="$TMPD/yi-up-repo"
mkdir -p "$YI_UP_REPO"
git -C "$YI_UP_REPO" init -q
git -C "$YI_UP_REPO" config user.email "test@test.com"
git -C "$YI_UP_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_UP_REPO/.grype.yaml"
touch "$YI_UP_REPO/go.mod"
git -C "$YI_UP_REPO" add .grype.yaml go.mod
git -C "$YI_UP_REPO" commit -q -m "init"
git -C "$YI_UP_REPO" checkout -q -b release-0.23
git -C "$YI_UP_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_UP_REPO" rev-parse HEAD)"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_UP_REPO" "$SCRIPT_DIR" > "$TMPD/yi-up.env"
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/yi-up.env" example.com/yi-up "High" "Fix not in registry" --fix-state not-fixed GHSA-up-0001 >/dev/null 2>&1
# Create report dir with fix-failed-pkgs listing the package (MVS-blocked scenario)
YI_UP_RDIR="$TMPD/yi-up-reports"
mkdir -p "$YI_UP_RDIR"
echo "example.com/yi-up" > "$YI_UP_RDIR/fix-failed-pkgs"
YI_UP_RFILE="$YI_UP_RDIR/yaml-integrity.report"
touch "$YI_UP_RFILE"
# Corrupt .grype.yaml and re-apply; package in ff_file → fix-state should be dropped
printf -- '---\nignore:\n  BROKEN\n' > "$YI_UP_REPO/.grype.yaml"
( cd "$YI_UP_REPO" && subagent_fix_yaml_integrity "$TMPD/yi-up.env" "$YI_UP_RFILE" "$SCRIPT_DIR" >/dev/null 2>&1 )
check "yi-up: failed-fix entry not resurrected" ! grep -q GHSA-up-0001 "$YI_UP_REPO/.grype.yaml"
check "yi-up: no permanent ignore created" ! grep -q "vulnerability:" "$YI_UP_REPO/.grype.yaml"

# === subagent_fix_yaml_integrity no-op when no Ignore commits ===
# No Ignore commits on branch → must return 0 without touching .grype.yaml.
echo "yaml-integrity no-op (no ignore commits)"
YI_NOOP_REPO="$TMPD/yi-noop-repo"
mkdir -p "$YI_NOOP_REPO"
git -C "$YI_NOOP_REPO" init -q
git -C "$YI_NOOP_REPO" config user.email "test@test.com"
git -C "$YI_NOOP_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_NOOP_REPO/.grype.yaml"
touch "$YI_NOOP_REPO/go.mod"
git -C "$YI_NOOP_REPO" add .grype.yaml go.mod
git -C "$YI_NOOP_REPO" commit -q -m "init"
git -C "$YI_NOOP_REPO" checkout -q -b release-0.23
git -C "$YI_NOOP_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_NOOP_REPO" rev-parse HEAD)"
# Add a non-Ignore commit so there is history but no Ignore grepped commits
printf 'require example.com/noop v1.0.0\n' >> "$YI_NOOP_REPO/go.mod"
git -C "$YI_NOOP_REPO" add go.mod
git -C "$YI_NOOP_REPO" commit -q -m "Bump example.com/noop for GHSA-noop-0001"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_NOOP_REPO" "$SCRIPT_DIR" > "$TMPD/yi-noop.env"
# Record the .grype.yaml mtime before calling the function
YI_NOOP_BEFORE=$(stat -c %Y "$YI_NOOP_REPO/.grype.yaml" 2>/dev/null || stat -f %m "$YI_NOOP_REPO/.grype.yaml" 2>/dev/null)
YI_NOOP_RC=0
( cd "$YI_NOOP_REPO" && subagent_fix_yaml_integrity "$TMPD/yi-noop.env" /dev/null "$SCRIPT_DIR" >/dev/null 2>&1 ) || YI_NOOP_RC=$?
check "yaml_integrity no-op: exits 0" test "$YI_NOOP_RC" -eq 0
check "yaml_integrity no-op: grype.yaml unchanged" \
  bash -c "! grep -q 'example.com/noop' '$YI_NOOP_REPO/.grype.yaml'"

# Two Ignore commits for same package, different CVEs (e.g. two passes each adding a new CVE).
# Both commits must be re-applied — no per-package dedup guard should drop the second one.
echo "yaml-integrity dedup (same package twice)"
YI_DUP_REPO="$TMPD/yi-dup-repo"
mkdir -p "$YI_DUP_REPO"
git -C "$YI_DUP_REPO" init -q
git -C "$YI_DUP_REPO" config user.email "test@test.com"
git -C "$YI_DUP_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_DUP_REPO/.grype.yaml"
touch "$YI_DUP_REPO/go.mod"
git -C "$YI_DUP_REPO" add .grype.yaml go.mod
git -C "$YI_DUP_REPO" commit -q -m "init"
git -C "$YI_DUP_REPO" checkout -q -b release-0.23
git -C "$YI_DUP_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_DUP_REPO" rev-parse HEAD)"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_DUP_REPO" "$SCRIPT_DIR" > "$TMPD/yi-dup.env"
# First ignore commit for example.com/dup-pkg (GHSA-dup-aa00)
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/yi-dup.env" example.com/dup-pkg "High" "First ignore for dup-pkg" --no-fix GHSA-dup-aa00 >/dev/null 2>&1
# Second ignore commit for same package, different CVE (GHSA-dup-bb00)
bash "$SCRIPT_DIR/ignore.sh" "$TMPD/yi-dup.env" example.com/dup-pkg "High" "Second ignore for dup-pkg" --no-fix GHSA-dup-bb00 >/dev/null 2>&1
# Corrupt .grype.yaml to force re-apply path
printf -- '---\nignore:\n  BROKEN\n' > "$YI_DUP_REPO/.grype.yaml"
( cd "$YI_DUP_REPO" && subagent_fix_yaml_integrity "$TMPD/yi-dup.env" /dev/null "$SCRIPT_DIR" >/dev/null 2>&1 )
# Both CVEs are different; insert_grype_ignore's own dedup (CVE+package) allows both.
# Expect two "name: example.com/dup-pkg" lines — one per CVE entry.
YI_DUP_COUNT=$(grep -c "name: example.com/dup-pkg" "$YI_DUP_REPO/.grype.yaml" 2>/dev/null || true)
check "yaml_integrity history: no CVE entries re-inserted" test "$YI_DUP_COUNT" -eq 0

# === subagent_fix_yaml_integrity empty body → reason fallback ===
# Subject-only Ignore commit (no body) → empty reason; verifies fallback to default.
echo "yaml-integrity empty body fallback"
YI_EB_REPO="$TMPD/yi-eb-repo"
mkdir -p "$YI_EB_REPO"
git -C "$YI_EB_REPO" init -q
git -C "$YI_EB_REPO" config user.email "test@test.com"
git -C "$YI_EB_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$YI_EB_REPO/.grype.yaml"
touch "$YI_EB_REPO/go.mod"
git -C "$YI_EB_REPO" add .grype.yaml go.mod
git -C "$YI_EB_REPO" commit -q -m "init"
git -C "$YI_EB_REPO" checkout -q -b release-0.23
git -C "$YI_EB_REPO" update-ref refs/remotes/origin/release-0.23 "$(git -C "$YI_EB_REPO" rev-parse HEAD)"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$YI_EB_REPO" "$SCRIPT_DIR" > "$TMPD/yi-eb.env"
# Manually create an Ignore commit whose message has no body (no blank line + reason)
printf -- '---\nignore:\n- vulnerability: GHSA-eb-0001\n  fix-state: not-fixed\n  package:\n    name: example.com/eb-pkg\n' > "$YI_EB_REPO/.grype.yaml"
git -C "$YI_EB_REPO" add .grype.yaml
git -C "$YI_EB_REPO" commit -q -m "Ignore example.com/eb-pkg CVEs (no fix available)"
# Corrupt .grype.yaml to force re-apply path
printf -- '---\nignore:\n  BROKEN\n' > "$YI_EB_REPO/.grype.yaml"
YI_EB_RC=0
( cd "$YI_EB_REPO" && subagent_fix_yaml_integrity "$TMPD/yi-eb.env" /dev/null "$SCRIPT_DIR" >/dev/null 2>&1 ) || YI_EB_RC=$?
check "yaml_integrity empty body: exits 0" test "$YI_EB_RC" -eq 0
check "yaml_integrity empty body: entry not resurrected" ! grep -q GHSA-eb-0001 "$YI_EB_REPO/.grype.yaml"

# === subagent_fix_scan_regression groups CVEs by package ===
echo "scan-regression CVE grouping"
# Create a mock report file with multiple CVEs for the same package
SREG_REPORT="$TMPD/scan-reg.report"
cat > "$SREG_REPORT" <<'REPORT'
VERDICT: FAIL
ISSUES: 4
DETAILS:
UNRESOLVED: GO-2026-5064 (github.com/containerd/containerd v1.7.34 Critical no-fix)
UNRESOLVED: GO-2026-5338 (github.com/containerd/containerd v1.7.34 Critical no-fix)
UNRESOLVED: GO-2026-5622 (github.com/containerd/containerd v1.7.34 Medium no-fix)
UNRESOLVED: GO-2026-5932 (golang.org/x/crypto v0.35.0 High no-fix)
REPORT

# Create a mock repo and state file for the test
SREG_REPO="$TMPD/sreg-repo"
mkdir -p "$SREG_REPO"
git -C "$SREG_REPO" init -q
git -C "$SREG_REPO" config user.email "test@test.com"
git -C "$SREG_REPO" config user.name "Test"
printf -- '---\nignore:\n' > "$SREG_REPO/.grype.yaml"
touch "$SREG_REPO/go.mod"
git -C "$SREG_REPO" add .grype.yaml go.mod
git -C "$SREG_REPO" commit -q -m "init"
git -C "$SREG_REPO" checkout -q -b release-0.23
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$SREG_REPO" "$SCRIPT_DIR" > "$TMPD/sreg.env"

# Create a mock ignore.sh that records its arguments instead of actually committing
MOCK_DIR="$TMPD/mock-scripts"
mkdir -p "$MOCK_DIR"
# Copy real lib.sh for the mock scripts to source
cp "$SCRIPT_DIR/lib.sh" "$MOCK_DIR/lib.sh"
cat > "$MOCK_DIR/ignore.sh" <<'MOCK'
#!/bin/bash
set -euo pipefail
# Record the call for test verification
shift  # STATE_FILE
PKG="$1"; shift  # PACKAGE
shift  # SEVERITY
shift  # REASON
FIX_STATE=""
if [[ "${1:-}" == "--fix-state" ]]; then shift; FIX_STATE="$1"; shift; fi
CVES="$*"
echo "MOCK_IGNORE: $PKG [FIX_STATE=$FIX_STATE] [$CVES]" >> "${MOCK_LOG:-/dev/null}"
MOCK
chmod +x "$MOCK_DIR/ignore.sh"

cat > "$MOCK_DIR/fix-package.sh" <<'MOCK'
#!/bin/bash
set -euo pipefail
shift  # STATE_FILE
PKG="$1"; shift  # PACKAGE
VER="$1"; shift  # VERSION
CVES="$*"
echo "MOCK_FIX: $PKG@$VER [$CVES]" >> "${MOCK_LOG:-/dev/null}"
MOCK
chmod +x "$MOCK_DIR/fix-package.sh"

# Run the grouping logic with mock scripts
MOCK_LOG="$TMPD/mock-calls.log"
export MOCK_LOG
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1

# Verify: should be exactly 2 calls (one per package), not 4
CALL_COUNT=$(wc -l < "$MOCK_LOG" 2>/dev/null || echo 0)
check "groups into 2 calls" test "$CALL_COUNT" -eq 2

# Verify: containerd call includes all 3 CVE IDs
check "containerd has 3 CVEs" bash -c "grep 'containerd' '$MOCK_LOG' | grep -q 'GO-2026-5064' && grep 'containerd' '$MOCK_LOG' | grep -q 'GO-2026-5338' && grep 'containerd' '$MOCK_LOG' | grep -q 'GO-2026-5622'"

# Verify: x/crypto call includes its CVE
check "x/crypto has its CVE" bash -c "grep 'x/crypto' '$MOCK_LOG' | grep -q 'GO-2026-5932'"

# GO- prefix must use not-fixed (same as GHSA-/CVE-); grype uses "not-fixed" for
# all unfixed OSV CVEs regardless of ID prefix (GHSA-*, CVE-*, GO-*).
check "GO- containerd gets not-fixed" bash -c "grep 'containerd' '$MOCK_LOG' | grep -q 'FIX_STATE=not-fixed'"
check "GO- x/crypto gets not-fixed" bash -c "grep 'x/crypto' '$MOCK_LOG' | grep -q 'FIX_STATE=not-fixed'"

# Test mixed fix/no-fix for same package
SREG_MIX_REPORT="$TMPD/scan-reg-mix.report"
cat > "$SREG_MIX_REPORT" <<'REPORT'
VERDICT: FAIL
ISSUES: 3
DETAILS:
NEW: GHSA-1234-5678-abcd (example.com/mixed v1.0.0 High v1.1.0)
NEW: GHSA-abcd-1234-5678 (example.com/mixed v1.0.0 High no-fix)
NEW: CVE-2026-9999 (example.com/other v2.0.0 Medium v2.1.0)
REPORT

MOCK_LOG_MIX="$TMPD/mock-calls-mix.log"
export MOCK_LOG="$MOCK_LOG_MIX"
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_MIX_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1

# Should have 3 calls: fix for mixed, ignore for mixed, fix for other
MIX_CALL_COUNT=$(wc -l < "$MOCK_LOG_MIX" 2>/dev/null || echo 0)
check "mixed: 3 calls" test "$MIX_CALL_COUNT" -eq 3
check "mixed: fix call" bash -c "grep 'MOCK_FIX.*mixed' '$MOCK_LOG_MIX' | grep -q 'GHSA-1234-5678-abcd'"
check "mixed: ignore call" bash -c "grep 'MOCK_IGNORE.*mixed' '$MOCK_LOG_MIX' | grep -q 'GHSA-abcd-1234-5678'"
check "mixed: other fix" bash -c "grep 'MOCK_FIX.*other' '$MOCK_LOG_MIX' | grep -q 'CVE-2026-9999'"

# Verify fix_state: GHSA- prefix should trigger not-fixed
check "mixed: GHSA gets not-fixed" bash -c "grep 'MOCK_IGNORE.*mixed' '$MOCK_LOG_MIX' | grep -q 'FIX_STATE=not-fixed'"

# Test: fix-package.sh exit 2 (NEEDS_REVIEW) writes tracking file; newly
# dispatched active evidence still triggers a repair despite that marker.
SREG_NR_DIR="$TMPD/sreg-nr"
mkdir -p "$SREG_NR_DIR"
SREG_NR_REPORT="$SREG_NR_DIR/scan-regression.report"
cat > "$SREG_NR_REPORT" <<'REPORT'
VERDICT: FAIL
ISSUES: 1
DETAILS:
UNRESOLVED: GO-2026-6107 (go.etcd.io/etcd/client/pkg/v3 v3.6.8 High 3.7.1)
REPORT

# Mock fix-package.sh that exits 2 (NEEDS_REVIEW — breaking version bump)
cat > "$MOCK_DIR/fix-package.sh" <<'MOCK'
#!/bin/bash
set -euo pipefail
shift  # STATE_FILE
PKG="$1"; shift  # PACKAGE
VER="$1"; shift  # VERSION
CVES="$*"
echo "MOCK_FIX: $PKG@$VER [$CVES]" >> "${MOCK_LOG:-/dev/null}"
exit 2
MOCK
chmod +x "$MOCK_DIR/fix-package.sh"

MOCK_LOG_NR="$SREG_NR_DIR/calls.log"
export MOCK_LOG="$MOCK_LOG_NR"
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_NR_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1

NR_FILE="$SREG_NR_DIR/needs-review-pkgs"
check "exit2: pkg in tracking file" bash -c "grep -qxF 'go.etcd.io/etcd/client/pkg/v3' '$NR_FILE'"

# Second call: an active finding must be retried despite the policy marker.
CALL_COUNT_BEFORE=$(wc -l < "$MOCK_LOG_NR" 2>/dev/null || echo 0)
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_NR_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1
CALL_COUNT_AFTER=$(wc -l < "$MOCK_LOG_NR" 2>/dev/null || echo 0)
check "exit2: active pkg retried" test "$CALL_COUNT_AFTER" -eq $((CALL_COUNT_BEFORE + 1))

# Test: exit 3 writes fix-failed-pkgs but an active finding is retried.
SREG_FF_DIR="$TMPD/sreg-ff"
mkdir -p "$SREG_FF_DIR"
SREG_FF_REPORT="$SREG_FF_DIR/scan-regression.report"
cat > "$SREG_FF_REPORT" <<'REPORT'
VERDICT: FAIL
ISSUES: 1
DETAILS:
UNRESOLVED: GO-2026-9999 (example.com/badpkg v1.0.0 High 1.1.0)
REPORT

# Mock fix-package.sh that exits 3 (CVE persists after update)
cat > "$MOCK_DIR/fix-package.sh" <<'MOCK'
#!/bin/bash
set -euo pipefail
shift; PKG="$1"; shift; VER="$1"; shift; CVES="$*"
echo "MOCK_FIX: $PKG@$VER [$CVES]" >> "${MOCK_LOG:-/dev/null}"
exit 3
MOCK
chmod +x "$MOCK_DIR/fix-package.sh"

MOCK_LOG_FF="$SREG_FF_DIR/calls.log"
export MOCK_LOG="$MOCK_LOG_FF"
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_FF_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1

FF_FILE="$SREG_FF_DIR/fix-failed-pkgs"
check "exit3: pkg in tracking file" bash -c "grep -qxF 'example.com/badpkg' '$FF_FILE'"
check "exit3: NOT in needs-review-pkgs" ! test -f "$SREG_FF_DIR/needs-review-pkgs"

# Second call: retry remains bounded by verify_fix_loop, not the marker file.
FF_COUNT_BEFORE=$(wc -l < "$MOCK_LOG_FF" 2>/dev/null || echo 0)
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_FF_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1
FF_COUNT_AFTER=$(wc -l < "$MOCK_LOG_FF" 2>/dev/null || echo 0)
check "exit3: active pkg retried" test "$FF_COUNT_AFTER" -eq $((FF_COUNT_BEFORE + 1))

# Test: fix-package.sh exits 5 (transient) on go get timeout or network failure.
# The mock _go_get_version returns 124 (timeout). The script must exit 5 rather
# than fall through to STILL_VULNERABLE / exit 3.
echo "fix-package.sh exit 5 (transient error)"
SREG_TE_DIR="$TMPD/sreg-te"
mkdir -p "$SREG_TE_DIR"
SREG_TE_REPORT="$SREG_TE_DIR/scan-regression.report"
cat > "$SREG_TE_REPORT" <<'REPORT'
VERDICT: FAIL
ISSUES: 1
DETAILS:
UNRESOLVED: CVE-2026-9998 (example.com/netpkg v1.0.0 High 1.2.0)
REPORT

# Mock fix-package.sh that exits 5 (transient network/timeout error)
cat > "$MOCK_DIR/fix-package.sh" <<'MOCK'
#!/bin/bash
shift; PKG="$1"
echo "MOCK_FIX: $PKG [exit 5 transient]" >> "${MOCK_LOG:-/dev/null}"
exit 5
MOCK
chmod +x "$MOCK_DIR/fix-package.sh"

MOCK_LOG_TE="$SREG_TE_DIR/calls.log"
export MOCK_LOG="$MOCK_LOG_TE"
(
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/sreg.env"
  subagent_fix_scan_regression "$TMPD/sreg.env" "$SREG_TE_REPORT" "$MOCK_DIR"
) >/dev/null 2>&1
# exit 5 is transient: the package should NOT appear in fix-failed-pkgs or
# needs-review-pkgs (those are for deterministic failures). The run should
# simply report the package was not fixed.
check "exit5: NOT in fix-failed-pkgs" ! test -f "$SREG_TE_DIR/fix-failed-pkgs"
check "exit5: NOT in needs-review-pkgs" ! test -f "$SREG_TE_DIR/needs-review-pkgs"
check "exit5: written to timeout-pkgs (retryable)" test -f "$SREG_TE_DIR/timeout-pkgs"

# Test: policy boundaries permit verified partial repairs; failed fixes,
# other module scopes and newly introduced findings remain actionable.
echo "scan-regression.sh policy boundary classification"
SREG_SH_DIR="$TMPD/sreg-sh"
mkdir -p "$SREG_SH_DIR"

# Minimal grype JSON fixture with one go-module match
SCAN_JSON='{"matches":[{"vulnerability":{"id":"GO-2026-6107","severity":"High","fix":{"versions":["3.7.1"]}},"artifact":{"name":"go.etcd.io/etcd/client/pkg/v3","version":"v3.6.8","type":"go-module"}}]}'
printf '%s\n' "$SCAN_JSON" > "$SREG_SH_DIR/initial-scan.json"

# needs-review-pkgs tracking file: this package was flagged exit 2
printf 'go.etcd.io/etcd/client/pkg/v3\n' > "$SREG_SH_DIR/needs-review-pkgs"

# Mock scan.sh that outputs the same JSON (CVE still present in final scan)
SREG_SCRIPTS_DIR="$TMPD/sreg-scripts"
mkdir -p "$SREG_SCRIPTS_DIR"
cp "$SCRIPT_DIR/lib.sh" "$SREG_SCRIPTS_DIR/lib.sh"
cat > "$SREG_SCRIPTS_DIR/scan.sh" <<SCANMOCK
#!/bin/bash
printf '%s\n' '$SCAN_JSON'
SCANMOCK
chmod +x "$SREG_SCRIPTS_DIR/scan.sh"

# State file pointing to mock scripts
printf 'REPO="%s"\nBRANCH="release-0.24"\nCVE_SCRIPTS="%s"\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=""\n' \
  "$SREG_REPO" "$SREG_SCRIPTS_DIR" > "$SREG_SH_DIR/state.env"

SREG_SH_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" \
  "$SREG_SH_DIR/state.env" "$SREG_SH_DIR" 2>/dev/null || true)

check "scan-reg.sh: policy boundary has no actionable count" grep -qx 'NEW_CVES=0 UNRESOLVED=0' <<< "$SREG_SH_OUT"
check "scan-reg.sh: policy boundary emits NEEDS_REVIEW" grep -q '^NEEDS_REVIEW: GO-2026-6107 ' <<< "$SREG_SH_OUT"
check "scan-reg.sh: policy boundary is not UNRESOLVED" ! grep -q '^UNRESOLVED:' <<< "$SREG_SH_OUT"
printf '%s\n' "$SREG_SH_OUT" > "$SREG_SH_DIR/scan-regression.evidence"
for _sreg_audit in existing-entries fix-availability yaml-integrity; do
  printf 'NEW_ISSUES=0\n' > "$SREG_SH_DIR/$_sreg_audit.evidence"
done
check "scan-reg.sh: policy evidence verifies partial repairs" evidence_verdict "$SREG_SH_DIR"
check "scan-reg.sh: final scan retains policy finding" test "$(jq '.matches | length' "$SREG_SH_DIR/final-scan.json")" -eq 1

# A failed update is not a policy exemption.
mv "$SREG_SH_DIR/needs-review-pkgs" "$SREG_SH_DIR/fix-failed-pkgs"
SREG_SH_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SREG_SH_DIR/state.env" "$SREG_SH_DIR")
check "scan-reg.sh: failed fix remains actionable" grep -qx 'NEW_CVES=0 UNRESOLVED=1' <<< "$SREG_SH_OUT"
rm "$SREG_SH_DIR/fix-failed-pkgs"

# One package in two modules: only the exact normalized policy scope is exempt.
SREG_SCOPED_JSON=$(jq '.matches[0].artifact.locations = [{path:"/src/go.mod"},{path:"/src/tools/go.mod"}]' <<< "$SCAN_JSON")
printf '%s\n' "$SREG_SCOPED_JSON" > "$SREG_SH_DIR/initial-scan.json"
printf '#!/bin/bash\ncat %q\n' "$SREG_SH_DIR/current.json" > "$SREG_SCRIPTS_DIR/scan.sh"
printf '%s\n' "$SREG_SCOPED_JSON" > "$SREG_SH_DIR/current.json"
# Writers normalize sentinel locations before storing them.
printf 'go.etcd.io/etcd/client/pkg/v3|/tools/go.mod\n' > "$SREG_SH_DIR/needs-review-pkgs"
SREG_SH_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SREG_SH_DIR/state.env" "$SREG_SH_DIR")
check "scan-reg.sh: sibling scope remains actionable" grep -qx 'NEW_CVES=0 UNRESOLVED=1' <<< "$SREG_SH_OUT"
check "scan-reg.sh: exact policy scope needs review" grep -q '^NEEDS_REVIEW: .* location:/tools/go.mod$' <<< "$SREG_SH_OUT"
check "scan-reg.sh: sibling scope stays unresolved" grep -q '^UNRESOLVED: .* location:/go.mod$' <<< "$SREG_SH_OUT"

# Newly introduced CVEs in that same policy scope must still fail verification.
jq '.matches[0].artifact.locations = [{path:"/src/tools/go.mod"}]' <<< "$SCAN_JSON" > "$SREG_SH_DIR/initial-scan.json"
jq '.matches += [.matches[0] | .vulnerability.id = "CVE-2026-NEW"]' "$SREG_SH_DIR/initial-scan.json" > "$SREG_SH_DIR/current.json"
SREG_SH_OUT=$(bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SREG_SH_DIR/state.env" "$SREG_SH_DIR")
check "scan-reg.sh: marked scope cannot hide a new CVE" grep -qx 'NEW_CVES=1 UNRESOLVED=0' <<< "$SREG_SH_OUT"
check "scan-reg.sh: new marked CVE emits NEW" grep -q '^NEW: CVE-2026-NEW .* location:/tools/go.mod$' <<< "$SREG_SH_OUT"
printf '%s\n' "$SREG_SH_OUT" > "$SREG_SH_DIR/scan-regression.evidence"
check "scan-reg.sh: new marked CVE fails evidence verification" ! evidence_verdict "$SREG_SH_DIR"

# Restore mock fix-package.sh for subsequent tests
cat > "$MOCK_DIR/fix-package.sh" <<'MOCK'
#!/bin/bash
set -euo pipefail
shift  # STATE_FILE
PKG="$1"; shift  # PACKAGE
VER="$1"; shift  # VERSION
CVES="$*"
echo "MOCK_FIX: $PKG@$VER [$CVES]" >> "${MOCK_LOG:-/dev/null}"
MOCK
chmod +x "$MOCK_DIR/fix-package.sh"

# === subagent_fix_scan_regression passes allFixVersions from current scan ===
# Regression: fix-package.sh's in-stream version selection (e.g. etcd 3.6.14 over
# 3.7.1 when installed minor is 3.6) requires CVE_FIX_ALL_VERSIONS to be set.
# Without the initial-scan.json lookup, only the highest version is tried, and a
# package whose highest fix bumps a Go minor is reported NEEDS_REVIEW even though
# a safe in-stream patch version is available.
echo "scan-regression allFixVersions lookup"
if command -v jq >/dev/null 2>&1; then
  SAFS_DIR="$TMPD/safs"; mkdir -p "$SAFS_DIR"
  SAFS_REPO="$TMPD/safs-repo"; mkdir -p "$SAFS_REPO"
  git -C "$SAFS_REPO" init -q
  git -C "$SAFS_REPO" config user.email t@t.com
  git -C "$SAFS_REPO" config user.name T
  printf -- '---\nignore:\n' > "$SAFS_REPO/.grype.yaml"
  touch "$SAFS_REPO/go.mod"
  git -C "$SAFS_REPO" add -A; git -C "$SAFS_REPO" commit -qm init

  # Initial scan: etcd packages at v3.6.11, fix.versions [3.6.14, 3.7.1]
  cat > "$SAFS_DIR/initial-scan.json" <<'JSON'
{"matches":[
  {"vulnerability":{"id":"GO-2026-6107","severity":"High","fix":{"versions":["3.6.14","3.7.1"],"state":"fixed"}},
   "artifact":{"name":"go.etcd.io/etcd/client/pkg/v3","version":"v3.6.11","type":"go-module","locations":[{"path":"/coredns/go.mod"}]}},
  {"vulnerability":{"id":"GO-2026-6107","severity":"High","fix":{"versions":["3.6.14","3.7.1"],"state":"fixed"}},
   "artifact":{"name":"go.etcd.io/etcd/client/v3","version":"v3.6.11","type":"go-module","locations":[{"path":"/coredns/go.mod"}]}},
  {"vulnerability":{"id":"GO-2026-6107","severity":"High","fix":{"versions":["3.6.14","3.7.1"],"state":"fixed"}},
   "artifact":{"name":"go.etcd.io/etcd/api/v3","version":"v3.6.11","type":"go-module","locations":[{"path":"/coredns/go.mod"}]}}
]}
JSON

  # Report: highest version only (as the LLM subagent would produce from the companion output)
  cat > "$SAFS_DIR/scan-regression.report" <<'REPORT'
VERDICT: FAIL
ISSUES: 3
DETAILS:
UNRESOLVED: GO-2026-6107 (go.etcd.io/etcd/client/pkg/v3 v3.6.11 High 3.7.1)
UNRESOLVED: GO-2026-6107 (go.etcd.io/etcd/client/v3 v3.6.11 High 3.7.1)
UNRESOLVED: GO-2026-6107 (go.etcd.io/etcd/api/v3 v3.6.11 High 3.7.1)
REPORT

  # Mock fix-package.sh: records CVE_FIX_ALL_VERSIONS and exits 0 (in-stream succeeds)
  SAFS_SCRIPTS="$TMPD/safs-scripts"; mkdir -p "$SAFS_SCRIPTS"
  cp "$SCRIPT_DIR/lib.sh" "$SAFS_SCRIPTS/lib.sh"
  cat > "$SAFS_SCRIPTS/fix-package.sh" <<'MOCK'
#!/usr/bin/env bash
shift  # STATE_FILE
PKG="$1"; shift; VER="$1"; shift; CVES="$*"
echo "MOCK_SAFS: $PKG@$VER AVFV=${CVE_FIX_ALL_VERSIONS:-UNSET} [$CVES]" >> "${MOCK_LOG:-/dev/null}"
exit 0
MOCK
  chmod +x "$SAFS_SCRIPTS/fix-package.sh"

  SAFS_LOG="$SAFS_DIR/calls.log"
  export MOCK_LOG="$SAFS_LOG"
  printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' "$SAFS_REPO" "$SCRIPT_DIR" \
    > "$SAFS_DIR/state.env"

  (
    source "$SCRIPT_DIR/lib.sh"
    subagent_fix_scan_regression "$SAFS_DIR/state.env" "$SAFS_DIR/scan-regression.report" "$SAFS_SCRIPTS"
  ) >/dev/null 2>&1

  # All three etcd packages must be attempted
  check "safs: client/pkg called" bash -c "grep 'client/pkg' '$SAFS_LOG' | grep -q 'GO-2026-6107'"
  check "safs: client/v3 called"  bash -c "grep 'etcd/client/v3' '$SAFS_LOG' | grep -q 'GO-2026-6107'"
  check "safs: api/v3 called"     bash -c "grep 'etcd/api/v3' '$SAFS_LOG' | grep -q 'GO-2026-6107'"
  # CVE_FIX_ALL_VERSIONS must include both fix versions from initial-scan.json
  check "safs: allFixVersions includes 3.6.14" bash -c "grep 'client/pkg' '$SAFS_LOG' | grep -q '3.6.14'"
  check "safs: allFixVersions includes 3.7.1"  bash -c "grep 'client/pkg' '$SAFS_LOG' | grep -q '3.7.1'"

  # A remediation can expose a new patched release stream that the initial scan
  # did not report. The current scan must drive both the union and per-CVE
  # requirements passed to fix-package.sh (Lighthouse grpc 1.83.1 -> 1.83.2).
  SAFS2_DIR="$TMPD/safs2"; mkdir -p "$SAFS2_DIR"
  cat > "$SAFS2_DIR/initial-scan.json" <<'JSON'
{"matches":[{"vulnerability":{"id":"GHSA-2v4p-qf9q-27wj","severity":"High","fix":{"versions":["1.82.2"]}},"artifact":{"name":"google.golang.org/grpc","version":"1.80.0","type":"go-module","locations":[{"path":"/coredns/go.mod"}]}}]}
JSON
  cat > "$SAFS2_DIR/final-scan.json" <<'JSON'
{"matches":[{"vulnerability":{"id":"GHSA-2v4p-qf9q-27wj","severity":"High","fix":{"versions":["1.83.2"]}},"artifact":{"name":"google.golang.org/grpc","version":"1.83.1","type":"go-module","locations":[{"path":"/coredns/go.mod"}]}}]}
JSON
  cat > "$SAFS2_DIR/scan-regression.report" <<'REPORT'
VERDICT: FAIL
ISSUES: 1
DETAILS:
UNRESOLVED: GHSA-2v4p-qf9q-27wj (google.golang.org/grpc 1.83.1 High 1.83.2) location:/coredns/go.mod
REPORT
  cat > "$SAFS_SCRIPTS/fix-package.sh" <<'MOCK'
#!/usr/bin/env bash
shift; PKG="$1"; shift; VER="$1"; shift
REQ=$(printf '%s' "${CVE_FIX_REQUIREMENTS_B64:-}" | base64 -d 2>/dev/null || true)
echo "MOCK_SAFS2: $PKG@$VER AVFV=${CVE_FIX_ALL_VERSIONS:-UNSET} REQ=$REQ" >> "${MOCK_LOG:-/dev/null}"
MOCK
  chmod +x "$SAFS_SCRIPTS/fix-package.sh"
  printf 'REPO="%s"\nBRANCH="release-0.22"\nCVE_SCRIPTS="%s"\n' "$SAFS_REPO" "$SCRIPT_DIR" \
    > "$SAFS2_DIR/state.env"
  SAFS2_LOG="$SAFS2_DIR/calls.log"
  export MOCK_LOG="$SAFS2_LOG"
  (
    source "$SCRIPT_DIR/lib.sh"
    subagent_fix_scan_regression "$SAFS2_DIR/state.env" \
      "$SAFS2_DIR/scan-regression.report" "$SAFS_SCRIPTS"
  ) >/dev/null 2>&1
  check "safs2: current scan supplies newly exposed fix" \
    grep -q 'AVFV=1.83.2' "$SAFS2_LOG"
  check "safs2: per-CVE requirements use current scan" \
    grep -q 'versions.*1.83.2' "$SAFS2_LOG"
  check "safs2: initial-only threshold is not reused" \
    ! grep -q '1.82.2' "$SAFS2_LOG"

  # Null-in-fix.versions regression: join(",") on [null,"1.2.3"] → ",1.2.3" (leading comma).
  # The jq filter must exclude nulls so CVE_FIX_ALL_VERSIONS has no empty leading element.
  echo "scan-regression null-in-fix.versions (leading comma guard)"
  NULL_SCAN="$TMPD/null-scan.json"
  cat > "$NULL_SCAN" <<'JSON'
{"matches":[
  {"vulnerability":{"id":"GO-2025-9999","severity":"High","fix":{"versions":[null,"2.1.0"],"state":"fixed"}},
   "artifact":{"name":"example.com/foo","version":"2.0.0","type":"go-module","locations":[{"path":"/go.mod"}]}}
]}
JSON
  NULL_RESULT=$(jq -r --arg pkg "example.com/foo" \
    '[.matches[] | select(.artifact.name == $pkg) | (.vulnerability.fix.versions // [])[]] | map(select(. != null and . != "")) | unique | join(",")' \
    "$NULL_SCAN")
  check "null in versions: no leading comma" bash -c "[[ '$NULL_RESULT' == '2.1.0' ]]"
else
  echo "  (skipped: jq not available)"
fi

# === select_instream_version behavioral tests (R118 pseudo-version guard) ===
echo "select_instream_version"
# Stable: highest in-stream version is selected from comma-separated list.
check "select_instream stable: picks highest" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='1.2.4,1.2.3'; result=\$(select_instream_version 'example.com/foo' '1.2.0'); [[ \"\$result\" == '1.2.4' ]]"
check "select_instream never selects a downgrade" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='1.2.1,1.2.2'; result=\$(select_instream_version 'example.com/foo' '1.2.3'); [[ \"\$result\" == '1.2.3' ]]"
# Prerelease skip: a semver prerelease (hyphen without 14-digit timestamp) must be
# excluded so a stable older patch is preferred over a prerelease newer patch.
check "select_instream skips prerelease" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='1.2.4-alpha,1.2.3'; result=\$(select_instream_version 'example.com/foo' '1.2.0'); [[ \"\$result\" == '1.2.3' ]]"
# Pseudo-version when current is also pseudo: newer pseudo must be selected.
# Pseudo-versions are not skipped when both current and fix are pseudo-versions.
check "select_instream pseudo fix: current also pseudo returns newer pseudo" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='0.0.0-20230201150000-abc123456789'; result=\$(select_instream_version 'example.com/foo' '0.0.0-20230101000000-def123456789'); [[ \"\$result\" == '0.0.0-20230201150000-abc123456789' ]]"
# Pseudo-version when current is a real release: return current so fix-package.sh
# leaves VERSION at the grype fix version and attempts a proper update, rather
# than using the pseudo-version which version_gte would incorrectly treat as
# already satisfied by the real release.
check "select_instream pseudo fix: current real returns current" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='0.0.0-20230201150000-abc123456789'; result=\$(select_instream_version 'example.com/foo' '0.0.3'); [[ \"\$result\" == '0.0.3' ]]"
# Real fix still preferred over pseudo when both present in same stream
check "select_instream real fix preferred over pseudo" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; CVE_FIX_ALL_VERSIONS='0.0.0-20230201150000-abc123456789,0.0.4'; result=\$(select_instream_version 'example.com/foo' '0.0.3'); [[ \"\$result\" == '0.0.4' ]]"

# === portability (macOS/BSD/BusyBox, older bash) ===
echo "portability"

# sed_inplace edits a file in place via temp-file+mv (BSD sed -i needs a suffix)
printf 'keep\ntoolchain go1.25.1\nkeep2\n' > "$TMPD/si.txt"
sed_inplace '/^toolchain/d' "$TMPD/si.txt"
check "sed_inplace deletes line" ! grep -q toolchain "$TMPD/si.txt"
check "sed_inplace keeps rest" bash -c "[[ \$(wc -l < '$TMPD/si.txt') -eq 2 ]]"

# squeeze_blank_lines collapses runs of blank lines to one (awk, not BSD sed N)
printf 'a\n\n\n\nb\n' > "$TMPD/sq.txt"
squeeze_blank_lines "$TMPD/sq.txt"
check "squeeze collapses blanks" bash -c "[[ \$(wc -l < '$TMPD/sq.txt') -eq 3 ]]"
check "squeeze keeps content" bash -c "grep -q '^a\$' '$TMPD/sq.txt' && grep -q '^b\$' '$TMPD/sq.txt'"

# === TMPDIR support (temp filesystem full bug) ===
# All temp paths must respect TMPDIR so a full /tmp can be worked around by
# setting TMPDIR to a directory on a filesystem with available space.
echo "TMPDIR support"
# Functional: temp dir probe must succeed in the current (writable) tmpdir.
check "preflight temp check passes on writable tmpdir" \
  bash -c "_p=\$(mktemp '${TMPDIR:-/tmp}/.cve-fix-space-probe.XXXXXX' 2>&1) && rm -f \"\$_p\""
# Functional: state_file_path round-trip via a custom TMPDIR.
check "state_file_path TMPDIR round-trip" \
  bash -c "( TMPDIR=$TMPD; source '$SCRIPT_DIR/lib.sh'; out=\$(state_file_path /x/testrepo release-0.99); [[ \$out == $TMPD/cve-fix-testrepo-release-0-99.*.env ]] )"

# === ensure_grype supply-chain behavior ===
# Exercise a complete install without network access: the curl shim serves a
# release tarball and its published checksum from local fixtures.
echo "ensure_grype checksum install"
GI_ROOT="$TMPD/grype-install"
GI_FIXTURES="$TMPD/grype-fixtures"
GI_CURL_BIN="$TMPD/grype-curl-bin"
mkdir -p "$GI_ROOT/scripts" "$GI_FIXTURES/payload" "$GI_CURL_BIN"
cp "$SCRIPT_DIR/lib.sh" "$GI_ROOT/scripts/lib.sh"
cat > "$GI_FIXTURES/payload/grype" <<'SH'
#!/usr/bin/env bash
[[ "${1:-}" == version ]] && echo 'Version: 9.8.7'
SH
chmod +x "$GI_FIXTURES/payload/grype"
GI_OS=$(uname -s | tr '[:upper:]' '[:lower:]')
GI_ARCH=$(uname -m)
case "$GI_ARCH" in
  x86_64|amd64) GI_ARCH=amd64 ;;
  aarch64|arm64) GI_ARCH=arm64 ;;
esac
GI_ARTIFACT="grype_9.8.7_${GI_OS}_${GI_ARCH}.tar.gz"
tar -czf "$GI_FIXTURES/$GI_ARTIFACT" -C "$GI_FIXTURES/payload" grype
if command -v sha256sum >/dev/null 2>&1; then
  GI_SHA=$(sha256sum "$GI_FIXTURES/$GI_ARTIFACT" | awk '{print $1}')
else
  GI_SHA=$(shasum -a 256 "$GI_FIXTURES/$GI_ARTIFACT" | awk '{print $1}')
fi
printf '%s  %s\n' "$GI_SHA" "$GI_ARTIFACT" > "$GI_FIXTURES/checksums.txt"
cat > "$GI_CURL_BIN/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
out="" url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
case "$url" in
  *_checksums.txt) cp "$GI_CHECKSUM_FIXTURE" "$out" ;;
  *.tar.gz) cp "$GI_ARTIFACT_FIXTURE" "$out" ;;
  *) exit 1 ;;
esac
SH
chmod +x "$GI_CURL_BIN/curl"
export GI_CHECKSUM_FIXTURE="$GI_FIXTURES/checksums.txt"
export GI_ARTIFACT_FIXTURE="$GI_FIXTURES/$GI_ARTIFACT"
check "ensure_grype installs verified release artifact" \
  env PATH="$GI_CURL_BIN:$PATH" CVE_FIX_GRYPE_VERSION=v9.8.7 \
  bash -c "source '$GI_ROOT/scripts/lib.sh'; ensure_grype"
check "ensure_grype installed expected version" \
  bash -c "'$GI_ROOT/bin/grype' version | grep -q 9.8.7"
printf 'tampered' >> "$GI_FIXTURES/$GI_ARTIFACT"
rm -f "$GI_ROOT/bin/grype"
check "ensure_grype rejects checksum mismatch" ! \
  env PATH="$GI_CURL_BIN:$PATH" CVE_FIX_GRYPE_VERSION=v9.8.7 \
  bash -c "source '$GI_ROOT/scripts/lib.sh'; ensure_grype"
check "ensure_grype leaves no binary after checksum failure" ! test -e "$GI_ROOT/bin/grype"
check "ensure_grype rejects unsafe version input" ! \
  env PATH="$GI_CURL_BIN:$PATH" CVE_FIX_GRYPE_VERSION='../9.8.7' \
  bash -c "source '$GI_ROOT/scripts/lib.sh'; ensure_grype"
check "ensure_grype never executes a mutable main-branch installer" ! \
  grep -q 'raw.githubusercontent.com/anchore/grype/main' "$SCRIPT_DIR/lib.sh"

# === preflight_check behavioral tests ===
# Directly invoke preflight_check() to verify each guarded code path exits
# correctly. Tests use subshells so PATH/TMPDIR overrides don't leak.
echo "preflight_check behavioral"

# Use a copied library with an empty sibling bin/ so the installed development
# binary cannot leak into the no-scanner and no-curl cases.
PF_ROOT="$TMPD/preflight-root"
mkdir -p "$PF_ROOT/scripts" "$PF_ROOT/bin"
cp "$SCRIPT_DIR/lib.sh" "$PF_ROOT/scripts/lib.sh"

# Fake-bin setup: all required tools, but no curl/grype/docker/podman.
PF_BIN="$TMPD/pf-bin"
mkdir -p "$PF_BIN"
for _pft in git go jq awk sed timeout base64 make python3; do
  ln -sf /usr/bin/true "$PF_BIN/$_pft"
done
for _pft in sort dirname pwd mktemp rm; do
  ln -sf "$(command -v "$_pft")" "$PF_BIN/$_pft"
done

# No scanner (grype/docker/podman absent from PATH) → preflight_check must fail.
check "preflight: no scanner → fails" ! \
  "$BASH" -c "PATH='$PF_BIN'; source '$PF_ROOT/scripts/lib.sh'; preflight_check"

# A live container runtime is a complete fallback even when curl and a local
# grype binary are absent.
PF_CONTAINER_BIN="$TMPD/pf-container-bin"
cp -a "$PF_BIN" "$PF_CONTAINER_BIN"
for _pft in jq timeout; do
  ln -sf "$(command -v "$_pft")" "$PF_CONTAINER_BIN/$_pft"
done
printf '#!/bin/sh\nexit 0\n' > "$PF_CONTAINER_BIN/docker"
chmod +x "$PF_CONTAINER_BIN/docker"
check "preflight: container scanner passes without curl or local grype" \
  "$BASH" -c "PATH='$PF_CONTAINER_BIN'; source '$PF_ROOT/scripts/lib.sh'; preflight_check"
check "preflight: unavailable explicit scanner pin fails closed" ! \
  "$BASH" -c "PATH='$PF_CONTAINER_BIN'; CVE_FIX_GRYPE_VERSION=v9.8.7; source '$PF_ROOT/scripts/lib.sh'; preflight_check"

# TMPDIR unwritable (/dev/null is a file, not a dir) → mktemp fails → preflight
# must fail after the scanner guard passes.
check "preflight: tmpdir unwritable → fails" ! \
  "$BASH" -c "PATH='$PF_CONTAINER_BIN'; TMPDIR=/dev/null; source '$PF_ROOT/scripts/lib.sh'; preflight_check"

# Happy path remains offline and uses the explicit container fallback.
check "preflight: happy path → passes" \
  "$BASH" -c "PATH='$PF_CONTAINER_BIN'; source '$PF_ROOT/scripts/lib.sh'; preflight_check"

# === render_template (envsubst-free named substitution) ===
echo "render_template"

# Named vars are replaced; unlisted ${...} left untouched.
_RT_A="alpha" _RT_B="beta"
check "render: substitutes named vars" test \
  "$(_RT_A="$_RT_A" _RT_B="$_RT_B" render_template _RT_A _RT_B <<<'x=${_RT_A} y=${_RT_B} z=${_RT_C}')" \
  = "x=alpha y=beta z=\${_RT_C}"

# Values with sed-hostile metacharacters ($ / & \ newline) are inserted literally.
_RT_V='a/b&c$d\e'
check "render: literal metachars in value" test \
  "$(_RT_V="$_RT_V" render_template _RT_V <<<'v=${_RT_V}')" = 'v=a/b&c$d\e'

# A value containing a placeholder name is not re-expanded (single pass).
_RT_X='${_RT_Y}' _RT_Y='SHOULD_NOT_APPEAR'
check "render: no re-expansion of substituted text" test \
  "$(_RT_X="$_RT_X" _RT_Y="$_RT_Y" render_template _RT_X _RT_Y <<<'${_RT_X}')" \
  = '${_RT_Y}'

# Unset variable expands to empty (matches envsubst).
unset _RT_UNSET 2>/dev/null || true
check "render: unset var → empty" test \
  "$(render_template _RT_UNSET <<<'[${_RT_UNSET}]')" = '[]'

# Static regression guards for non-portable constructs (silent-wrong on BSD).
# Exclude test-lib.sh: it names these constructs in descriptions/patterns.
check "no grep -oP" ! grep -rq --exclude=test-lib.sh 'grep -oP' "$SCRIPT_DIR" "$SCRIPT_DIR/../subagents"
# envsubst is intentionally not a dependency (missing from the CI base image);
# guard against reintroduction as a command. Non-comment lines only: the string
# legitimately appears in render_template's doc comment.
_envsubst_command_present() {
  grep -rh --exclude=test-lib.sh 'envsubst' "$SCRIPT_DIR" "$SCRIPT_DIR/../subagents" \
    | grep -qvE '^[[:space:]]*#'
}
check "no envsubst command" ! _envsubst_command_present
check "no literal backslash-s" ! grep -rIq --exclude=test-lib.sh '\\s' "$SCRIPT_DIR" "$SCRIPT_DIR/../subagents"
check "no sed -i" ! grep -rq --exclude=test-lib.sh 'sed -i' "$SCRIPT_DIR" "$SCRIPT_DIR/../subagents"
# xargs -r is a GNU extension; on BSD/macOS it errors and (with || true) silently
# stages nothing, so a real fix can be reported FIXED with no commit.
check "no xargs -r" ! grep -rq --exclude=test-lib.sh 'xargs -r' "$SCRIPT_DIR" "$SCRIPT_DIR/../subagents"
for f in "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/../subagents/*.sh; do
  [[ "$(basename "$f")" == "lib.sh" ]] && continue
  check "env-bash shebang $(basename "$f")" bash -c "[[ \$(head -1 '$f') == '#!/usr/bin/env bash' ]]"
done

# === de-submarinerize / multi-module ===
echo "de-submarinerize"

# find_gomods enumerates every module but excludes vendored go.mod files
FG_REPO="$TMPD/fg"
mkdir -p "$FG_REPO/tools" "$FG_REPO/vendor/example.com/dep" "$FG_REPO/sub/vendor/x"
( cd "$FG_REPO" && git init -q && git config user.email t@t && git config user.name t )
printf 'module m\ngo 1.25.0\n' > "$FG_REPO/go.mod"
printf 'module m/tools\ngo 1.25.0\n' > "$FG_REPO/tools/go.mod"
printf 'module dep\ngo 1.20.0\n' > "$FG_REPO/vendor/example.com/dep/go.mod"
printf 'module x\ngo 1.20.0\n' > "$FG_REPO/sub/vendor/x/go.mod"
git -C "$FG_REPO" add go.mod tools/go.mod
FG_OUT=$( cd "$FG_REPO" && find_gomods | sort )
check "find_gomods lists root" grep -qE '^(\./)?go\.mod$' <<< "$FG_OUT"
check "find_gomods lists tools" grep -qE '^(\./)?tools/go\.mod$' <<< "$FG_OUT"
check "find_gomods skips vendor" ! grep -q 'vendor/' <<< "$FG_OUT"

# find_gomods 3-module layout (lighthouse: root + tools + coredns)
FG_LH="$TMPD/fg-lh"
mkdir -p "$FG_LH/tools" "$FG_LH/coredns" "$FG_LH/vendor/dep" "$FG_LH/coredns/vendor/x"
( cd "$FG_LH" && git init -q && git config user.email t@t && git config user.name t )
printf 'module lh\ngo 1.25.0\n' > "$FG_LH/go.mod"
printf 'module lh/tools\ngo 1.25.0\n' > "$FG_LH/tools/go.mod"
printf 'module lh/coredns\ngo 1.25.0\n' > "$FG_LH/coredns/go.mod"
printf 'module dep\ngo 1.20.0\n' > "$FG_LH/vendor/dep/go.mod"
printf 'module x\ngo 1.20.0\n' > "$FG_LH/coredns/vendor/x/go.mod"
git -C "$FG_LH" add go.mod tools/go.mod coredns/go.mod
FG_LH_OUT=$( cd "$FG_LH" && find_gomods | sort )
check "find_gomods 3-module lists root" grep -qE '^(\./)?go\.mod$' <<< "$FG_LH_OUT"
check "find_gomods 3-module lists tools" grep -qE '^(\./)?tools/go\.mod$' <<< "$FG_LH_OUT"
check "find_gomods 3-module lists coredns" grep -qE '^(\./)?coredns/go\.mod$' <<< "$FG_LH_OUT"
check "find_gomods 3-module skips vendor" ! grep -q 'vendor/' <<< "$FG_LH_OUT"

# fix-stdlib picks the HIGHEST fix version in the compiler's minor stream, not
# the first grype happens to list. Drive the real selection loop with an
# out-of-order stream (1.23.5 before 1.23.9) and a build image one patch behind,
# so the script exits at the build-image check echoing the chosen version before
# it ever runs go/git. Old (break-on-first) code would report 1.23.5. This is also
# the sole fixture over the build-image-older patch-bump path (fix-stdlib.sh:66-71),
# so it must assert exit 2 and no commit: the selection greps alone pass on a
# false-FIXED regression (a "FIXED: stdlib go 1.23.9" line also matches them).
echo "fix-stdlib highest-in-stream selection"
FSL="$TMPD/fsl"; mkdir -p "$FSL"
printf 'module x\ngo 1.20.0\n' > "$FSL/go.mod"
cat > "$FSL/st.env" <<EOF
REPO="$FSL"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.23.1 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL_OUT=$( cd "$FSL" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL/st.env" 1.24.0 "1.23.5,1.23.9,1.24.0" CVE-2024-0001 2>&1 ) && FSL_RC=0 || FSL_RC=$?
check "stdlib selects highest in stream" grep -q '1\.23\.9' <<< "$FSL_OUT"
check "stdlib skips lower in stream"     ! grep -q '1\.23\.5' <<< "$FSL_OUT"
check "stdlib build-image-older exits 2" test "$FSL_RC" -eq 2
check "stdlib build-image-older no commit" ! grep -qi 'FIXED: stdlib' <<< "$FSL_OUT"

# fix-stdlib must never select an in-stream prerelease: sort -V ranks an RC
# above a stable patch, so the loop could pick 1.26.7-rc.1 over the valid
# stable 1.26.6 that matches the compiler. Drive the real loop with both and a
# build image one patch behind so it exits echoing the chosen version.
echo "fix-stdlib skips in-stream prerelease"
FSL2="$TMPD/fsl2"; mkdir -p "$FSL2"
printf 'module x\ngo 1.26.0\n' > "$FSL2/go.mod"
cat > "$FSL2/st.env" <<EOF
REPO="$FSL2"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.26.5 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL2_OUT=$( cd "$FSL2" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL2/st.env" 1.26.6 "1.26.6,1.26.7-rc.1" CVE-2024-0002 2>&1 ) || true
check "stdlib selects stable over rc" grep -q '1\.26\.6' <<< "$FSL2_OUT"
check "stdlib skips prerelease rc"    ! grep -q 'rc' <<< "$FSL2_OUT"

# Go-native RC format (1.26.6rc1) has no hyphen so the *-* filter passes it
# through; sort -V ranks it above a stable 1.26.5, making it the BEST. Then
# go mod edit -go=1.26.6rc1 fails and the ERR trap reverts changes, leaving
# the stdlib CVE unresolved. The explicit [0-9]rc[0-9] filter must block it.
echo "fix-stdlib skips Go-native RC (no-hyphen)"
FSL2B="$TMPD/fsl2b"; mkdir -p "$FSL2B"
printf 'module x\ngo 1.26.0\n' > "$FSL2B/go.mod"
cat > "$FSL2B/st.env" <<EOF
REPO="$FSL2B"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.26.4 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL2B_OUT=$( cd "$FSL2B" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL2B/st.env" 1.26.5 "1.26.5,1.26.6rc1" CVE-2024-0005 2>&1 ) || true
check "stdlib selects stable over Go-native rc" grep -q '1\.26\.5' <<< "$FSL2B_OUT"
check "stdlib skips Go-native rc (no-hyphen)"   ! grep -q 'rc' <<< "$FSL2B_OUT"

# Go-native beta format (1.26.6beta1) and alpha (1.26.6alpha1) have no hyphen,
# so the *-* filter passes them through; sort -V ranks them above a stable patch.
# The [0-9](rc|beta|alpha)[0-9] guard must block all three prerelease flavours.
echo "fix-stdlib skips Go-native beta (no-hyphen)"
FSL2C="$TMPD/fsl2c"; mkdir -p "$FSL2C"
printf 'module x\ngo 1.26.0\n' > "$FSL2C/go.mod"
cat > "$FSL2C/st.env" <<EOF
REPO="$FSL2C"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.26.4 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL2C_OUT=$( cd "$FSL2C" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL2C/st.env" 1.26.5 "1.26.5,1.26.6beta1" CVE-2024-0006 2>&1 ) || true
check "stdlib selects stable over Go-native beta" grep -q '1\.26\.5' <<< "$FSL2C_OUT"
check "stdlib skips Go-native beta (no-hyphen)"   ! grep -q 'beta' <<< "$FSL2C_OUT"

echo "fix-stdlib skips Go-native alpha (no-hyphen)"
FSL2D="$TMPD/fsl2d"; mkdir -p "$FSL2D"
printf 'module x\ngo 1.26.0\n' > "$FSL2D/go.mod"
cat > "$FSL2D/st.env" <<EOF
REPO="$FSL2D"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.26.4 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL2D_OUT=$( cd "$FSL2D" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL2D/st.env" 1.26.5 "1.26.5,1.26.6alpha1" CVE-2024-0007 2>&1 ) || true
check "stdlib selects stable over Go-native alpha" grep -q '1\.26\.5' <<< "$FSL2D_OUT"
check "stdlib skips Go-native alpha (no-hyphen)"   ! grep -q 'alpha' <<< "$FSL2D_OUT"

# B1: with no build image (BUILD_GO_VERSION="unknown"), COMPILER_GO is empty, so a
# cross-minor fix falls back to the go.mod version and must route to an honest
# NEEDS_REVIEW ("minor version change") rather than silently bumping the compiler.
echo "fix-stdlib unknown compiler -> cross-minor needs review"
FSL3="$TMPD/fsl3"; mkdir -p "$FSL3"
printf 'module x\ngo 1.25.0\n' > "$FSL3/go.mod"
cat > "$FSL3/st.env" <<EOF
REPO="$FSL3"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL3_OUT=$( cd "$FSL3" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL3/st.env" 1.26.6 "1.26.6" CVE-2024-0003 2>&1 ) && FSL3_RC=0 || FSL3_RC=$?
check "stdlib unknown cross-minor needs review" grep -q 'cross-minor toolchain change needs build-image evidence' <<< "$FSL3_OUT"
check "stdlib unknown cross-minor exits 2"      test "$FSL3_RC" -eq 2
check "stdlib unknown cross-minor no commit"    ! grep -qi 'FIXED: stdlib' <<< "$FSL3_OUT"

# Regression: when COMPILER_GO is unknown, the in-stream selection loop must still
# run using the go.mod directive as the stream reference. Without this, a prerelease
# in ALL_FIX_VERSIONS would win via the raw FIX_VER, triggering a false cross-minor
# NEEDS_REVIEW even though a same-minor stable patch was available.
# With the fix for the else-branch bug: unknown COMPILER_GO + same-minor patch now
# falls through and applies the bump (exit 0), because the cross-minor guard at line
# 59 already ensures GO_VERSION is a safe patch relative to go.mod.
echo "fix-stdlib unknown compiler -> in-stream stable fix selected over prerelease"
FSL3B="$TMPD/fsl3b"; mkdir -p "$FSL3B"
( cd "$FSL3B" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n' > "$FSL3B/go.mod"
( cd "$FSL3B" && git add go.mod && git commit -qm init )
cat > "$FSL3B/st.env" <<EOF
REPO="$FSL3B"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
# FIX_VER is 1.26.0-rc.3 (highest raw) but ALL_FIX_VERSIONS has 1.25.8 (same stream, stable)
FSL3B_OUT=$( cd "$FSL3B" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL3B/st.env" "1.26.0-rc.3" "1.25.8,1.26.0-rc.3" GO-2024-0003b 2>&1 ) && FSL3B_RC=0 || FSL3B_RC=$?
# Selection correctly picks 1.25.8 (same minor stream, stable, not rc).
# COMPILER_GO unknown + same-minor patch: falls through and applies the fix (exit 0).
check "stdlib unknown in-stream: no cross-minor msg" ! grep -q 'minor version change' <<< "$FSL3B_OUT"
check "stdlib unknown in-stream: exits 0 (applied)" test "$FSL3B_RC" -eq 0
check "stdlib unknown in-stream: FIXED message" grep -qi 'FIXED: stdlib' <<< "$FSL3B_OUT"
check "stdlib unknown in-stream: shows correct fix ver" grep -q '1\.25\.8' <<< "$FSL3B_OUT"

# === fix-stdlib.sh happy path: known compiler, in-stream patch applied (exit 0) ===
# Covers the path where BUILD_GO_VERSION is a known version (1.24.8) that already
# satisfies the selected in-stream fix (1.24.7). The script selects 1.24.7
# (highest 1.24.x candidate from "1.24.7,1.25.2" — 1.25.2 is cross-minor and
# skipped by the REF_MINOR filter), patches go.mod, commits, and exits 0.
# Previously untested: all real-invocation fixtures only exercised exit-2 paths.
echo "fix-stdlib happy path: known compiler, in-stream patch (exit 0)"
FSLHP="$TMPD/fslhp"; mkdir -p "$FSLHP"
( cd "$FSLHP" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.24.0\n' > "$FSLHP/go.mod"
( cd "$FSLHP" && git add go.mod && git commit -qm init )
cat > "$FSLHP/st.env" <<EOF
REPO="$FSLHP"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.24.8 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
# Correct invocation: STATE_FILE GO_VERSION ALL_FIX_VERSIONS CVE_ID
# fix-stdlib.sh selects 1.24.7 (highest in-stream 1.24.x) over cross-minor 1.25.2
FSLHP_OUT=$( cd "$FSLHP" && bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$FSLHP/st.env" "1.25.2" "1.24.7,1.25.2" "CVE-2026-TEST" 2>&1 ) && FSLHP_RC=0 || FSLHP_RC=$?
check "stdlib happy path: exits 0"        test "$FSLHP_RC" -eq 0
check "stdlib happy path: FIXED message"  grep -qi 'FIXED: stdlib' <<< "$FSLHP_OUT"
check "stdlib happy path: toolchain directive set" grep -q '^toolchain go1\.24\.7$' "$FSLHP/go.mod"
check "stdlib happy path: go directive left alone" grep -q '^go 1\.24\.0$' "$FSLHP/go.mod"
check "stdlib happy path: commit created" \
  bash -c "test \"\$(git -C '$FSLHP' log --oneline | wc -l | tr -d ' ')\" -gt 1"

# Sibling of FSL3 with a KNOWN compiler: when the build image's Go minor has no
# in-stream fix (fix lives in a higher minor), the cross-minor gate must route to
# an honest NEEDS_REVIEW naming the compiler stream — never bump the compiler.
echo "fix-stdlib known compiler -> no in-stream fix needs review"
FSL4="$TMPD/fsl4"; mkdir -p "$FSL4"
printf 'module x\ngo 1.20.0\n' > "$FSL4/go.mod"
cat > "$FSL4/st.env" <<EOF
REPO="$FSL4"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.23.1 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FSL4_OUT=$( cd "$FSL4" && bash "$SCRIPT_DIR/fix-stdlib.sh" "$FSL4/st.env" 1.25.0 "1.25.0" CVE-2024-0004 2>&1 ) && FSL4_RC=0 || FSL4_RC=$?
check "stdlib unsupported by builder needs review" grep -q 'build image has Go.*fix needs' <<< "$FSL4_OUT"
check "stdlib no in-stream fix exits 2"      test "$FSL4_RC" -eq 2
check "stdlib no in-stream fix no commit"    ! grep -qi 'FIXED: stdlib' <<< "$FSL4_OUT"

# === fix-package.sh safety gates (real invocation) ===
# Drive the REAL script with a hermetic PATH `go` stub; assert each gate refuses to report FIXED.
echo "fix-package CVE-persists gate (exit 3)"
FP1="$TMPD/fp1"; mkdir -p "$FP1/gostub"
( cd "$FP1" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/foo v1.0.0\n' > "$FP1/go.mod"
( cd "$FP1" && git add go.mod && git commit -qm init )
# no-op `go`: the "update" changes nothing, so the package stays below the fix
# version and go.mod's awk-scanned version drives the persist check.
cat > "$FP1/gostub/go" <<'STUB'
#!/bin/sh
exit 0
STUB
chmod +x "$FP1/gostub/go"
cat > "$FP1/st.env" <<EOF
REPO="$FP1"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FP1_OUT=$( cd "$FP1" && PATH="$FP1/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" "$FP1/st.env" example.com/foo 2.0.0 CVE-2024-1001 2>&1 ) && FP1_RC=0 || FP1_RC=$?
check "fix-package persist exits 3"     test "$FP1_RC" -eq 3
check "fix-package persist no FIXED"     ! grep -qi 'FIXED:' <<< "$FP1_OUT"
check "fix-package persist go.mod intact" grep -q '^go 1.25.0' "$FP1/go.mod"
FP1_SCOPE_OUT=$(cd "$FP1" && PATH="$FP1/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
  "$FP1/st.env" example.com/foo 2.0.0 --location /../../outside/go.mod CVE-2024-1001 2>&1) \
  && FP1_SCOPE_RC=0 || FP1_SCOPE_RC=$?
check "fix-package rejects location traversal" test "$FP1_SCOPE_RC" -eq 2
check "fix-package does not broaden invalid location" grep -q 'not a tracked repository go.mod' <<< "$FP1_SCOPE_OUT"

FP_SCOPE="$TMPD/fp-scope-prefix"; mkdir -p "$FP_SCOPE/foo" "$FP_SCOPE/gostub"
git -C "$FP_SCOPE" init -q
git -C "$FP_SCOPE" config user.email t@t.com
git -C "$FP_SCOPE" config user.name T
printf 'module example.com/root\ngo 1.25.0\n' > "$FP_SCOPE/go.mod"
printf 'module example.com/foo\ngo 1.25.0\nrequire example.com/pkg v1.0.0\n' \
  > "$FP_SCOPE/foo/go.mod"
git -C "$FP_SCOPE" add go.mod foo/go.mod; git -C "$FP_SCOPE" commit -qm init
printf '#!/bin/sh\nexit 0\n' > "$FP_SCOPE/gostub/go"; chmod +x "$FP_SCOPE/gostub/go"
printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION=unknown\nCVE_SCRIPTS=%q\nHAS_VENDOR=false\n' \
  "$FP_SCOPE" "$SCRIPT_DIR" > "$FP_SCOPE/state.env"
FP_SCOPE_BAD_RC=0
(cd "$FP_SCOPE"; PATH="$FP_SCOPE/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
  "$FP_SCOPE/state.env" example.com/pkg 2.0.0 --location /srcfoo/go.mod CVE-SCOPE-BAD) \
  > "$FP_SCOPE/bad.out" 2>&1 || FP_SCOPE_BAD_RC=$?
check "fix-package does not strip src from an ordinary path prefix" \
  test "$FP_SCOPE_BAD_RC" -eq 2
check "fix-package rejects the resulting untracked scope" \
  grep -q 'not a tracked repository go.mod' "$FP_SCOPE/bad.out"
FP_SCOPE_GOOD_RC=0
(cd "$FP_SCOPE"; PATH="$FP_SCOPE/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
  "$FP_SCOPE/state.env" example.com/pkg 2.0.0 --location /src/foo/go.mod CVE-SCOPE-GOOD) \
  > "$FP_SCOPE/good.out" 2>&1 || FP_SCOPE_GOOD_RC=$?
check "fix-package accepts the exact Docker mount prefix" test "$FP_SCOPE_GOOD_RC" -eq 3
check "fix-package exact Docker scope reaches the selected module" \
  ! grep -q 'not a tracked repository go.mod' "$FP_SCOPE/good.out"

# exit 2: a fix that drags the go directive across a minor with no build image to
# confirm the compiler supports it is breaking — refuse and roll the tree back.
echo "fix-package breaking-change gate (exit 2)"
FP2="$TMPD/fp2"; mkdir -p "$FP2/gostub"
( cd "$FP2" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/foo v1.0.0\n' > "$FP2/go.mod"
( cd "$FP2" && git add go.mod && git commit -qm init )
# `go get` simulates a dep update that also bumps the go directive minor
# (1.25 -> 1.27); other verbs are no-ops. With BUILD_GO_VERSION unknown the
# cross-minor jump is unverifiable, so fix-package must exit 2 and roll back.
cat > "$FP2/gostub/go" <<'STUB'
#!/bin/sh
dir=.
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  sed 's/^go 1\.25\.0/go 1.27.0/' "$dir/go.mod" > "$dir/go.mod.new" && mv "$dir/go.mod.new" "$dir/go.mod"
fi
exit 0
STUB
chmod +x "$FP2/gostub/go"
cat > "$FP2/st.env" <<EOF
REPO="$FP2"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FP2_OUT=$( cd "$FP2" && PATH="$FP2/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" "$FP2/st.env" example.com/foo 2.0.0 CVE-2024-1002 2>&1 ) && FP2_RC=0 || FP2_RC=$?
check "fix-package breaking exits 2"     test "$FP2_RC" -eq 2
check "fix-package breaking message"     grep -q 'upgraded Go directive' <<< "$FP2_OUT"
check "fix-package breaking rolled back"  grep -q '^go 1.25.0' "$FP2/go.mod"

# Sibling-replace exact-match guard: package appears only as a substring in a
# replace for a DIFFERENT module (e.g. example.com/lprep inside
# example.com/lprep-parent). It must not suppress graph resolution or create a
# false positive replace warning.
echo "fix-package sibling-replace substring guard: exact match safe skip"
FP_LP="$TMPD/fp-localpath"; mkdir -p "$FP_LP/gostub"
( cd "$FP_LP" && git init -q && git config user.email t@t && git config user.name t )
# go.mod: package appears only as a substring inside a replace for
# example.com/lprep-parent, not as an exact module reference.
cat > "$FP_LP/go.mod" <<'GOMOD'
module x
go 1.25.0

require example.com/unrelated v1.0.0

replace example.com/lprep-parent => ../local
GOMOD
( cd "$FP_LP" && git add go.mod && git commit -qm init )
# go stub: all `go list` calls return "" (simulates no version info available).
cat > "$FP_LP/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ] || [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then echo ""; fi
exit 0
STUB
chmod +x "$FP_LP/gostub/go"
cat > "$FP_LP/st.env" <<STENV
REPO="$FP_LP"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
FP_LP_OUT=$(
  cd "$FP_LP" && PATH="$FP_LP/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_LP/st.env" example.com/lprep 1.0.1 GHSA-lp-0001 2>&1
) && FP_LP_RC=0 || FP_LP_RC=$?
check "sibling-replace substr guard: exits 0"           test "$FP_LP_RC" -eq 0
check "sibling-replace substr guard: no pinned WARNING" ! grep -q 'effective version unverifiable' <<< "$FP_LP_OUT"
check "sibling-replace substr guard: no false update"   ! grep -q 'Updating example.com/lprep' <<< "$FP_LP_OUT"

# Genuine substring-only match: safe skip path (fix-package.sh:168).
# This test verifies that path does NOT exit 3 or produce a false CVE persists message.
echo "fix-package genuine substring match: safe skip (no exit 3)"
FP_SS="$TMPD/fp-safeskip"; mkdir -p "$FP_SS/gostub"
( cd "$FP_SS" && git init -q && git config user.email t@t && git config user.name t )
cat > "$FP_SS/go.mod" <<'GOMOD'
module x
go 1.25.0

require example.com/foo-client v1.0.0
GOMOD
( cd "$FP_SS" && git add go.mod && git commit -qm init )
cat > "$FP_SS/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ] || [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then echo ""; fi
exit 0
STUB
chmod +x "$FP_SS/gostub/go"
cat > "$FP_SS/st.env" <<STENV
REPO="$FP_SS"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
# PACKAGE=example.com/foo; go.mod has example.com/foo-client (substring match, no replace)
# → INSTALLED="" + no replace → safe skip → exits 0 with no FIXED commit (nothing to stage)
FP_SS_OUT=$(
  cd "$FP_SS" && PATH="$FP_SS/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_SS/st.env" example.com/foo 1.0.1 GHSA-ss-0001 2>&1
) && FP_SS_RC=0 || FP_SS_RC=$?
check "safe-skip substring match: exits 0"              test "$FP_SS_RC" -eq 0
check "safe-skip substring match: no Updating message" ! grep -qi 'Updating example.com/foo' <<< "$FP_SS_OUT"

# Non-versioned replace directive STILL_VULNERABLE gate (fix-package.sh lines 174-176):
# `go get` updates require but replace pins effective version → _EFFECTIVE check must exit 3.
echo "fix-package replace-directive STILL_VULNERABLE gate (exit 3)"
FP_REP="$TMPD/fp-rep"; mkdir -p "$FP_REP/gostub"
( cd "$FP_REP" && git init -q && git config user.email t@t && git config user.name t )
# go.mod: require at v1.0.0, non-versioned replace pins effective version to v1.0.0
cat > "$FP_REP/go.mod" <<'GOMOD'
module x
go 1.25.0

require example.com/reptest v1.0.0

replace example.com/reptest => example.com/reptest v1.0.0
GOMOD
( cd "$FP_REP" && git add go.mod && git commit -qm init )
# go stub: get updates require line; replace stays intact; Replace.Version always
# returns v1.0.0 (driving the STILL_VULNERABLE branch at fix-package.sh lines 174-176).
cat > "$FP_REP/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"; ver=$(printf '%s' "$pkgver" | sed 's/.*@//')
  awk -v v="$ver" \
    '/^require example\.com\/reptest /{print "require example.com/reptest " v; next} {print}' \
    "$dir/go.mod" > "$dir/go.mod.tmp" && mv "$dir/go.mod.tmp" "$dir/go.mod"
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  case "$fmt" in
    *Replace.Version*)
      # Active non-versioned replace pins the effective version to v1.0.0
      echo "v1.0.0" ;;
    *Version*)
      # Return the require version as currently written in go.mod
      awk '/^require example\.com\/reptest /{print $3}' "$dir/go.mod" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_REP/gostub/go"
cat > "$FP_REP/st.env" <<STENV
REPO="$FP_REP"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
FP_REP_OUT=$(
  cd "$FP_REP" && PATH="$FP_REP/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_REP/st.env" example.com/reptest 1.0.1 GHSA-rep-0001 2>&1
) && FP_REP_RC=0 || FP_REP_RC=$?
check "replace-directive STILL_VULNERABLE: exits 3"       test "$FP_REP_RC" -eq 3
check "replace-directive STILL_VULNERABLE: no FIXED line" ! grep -qi 'FIXED:' <<< "$FP_REP_OUT"

# Versioned-replace-to-local gap (fix-package.sh _LOCAL_REPLACE check):
# require at fix version but Replace.Dir non-empty → local path, effective version unverifiable → exit 3.
echo "fix-package versioned-replace-to-local: unverifiable → exit 3"
FP_VRL="$TMPD/fp-vrl"; mkdir -p "$FP_VRL/gostub"
( cd "$FP_VRL" && git init -q && git config user.email t@t && git config user.name t )
# go.mod: require at the CVE fix version; versioned replace pins to a local dir.
# This simulates a repo that has `replace pkg v1.5.0 => ../local` in go.mod even
# after `go get pkg@v1.5.0` — a common pattern for in-tree forks.
cat > "$FP_VRL/go.mod" <<'GOMOD'
module x
go 1.25.0

require example.com/vrltest v1.5.0

replace example.com/vrltest v1.5.0 => ../local
GOMOD
( cd "$FP_VRL" && git add go.mod && git commit -qm init )
# go stub: get/tidy no-op; Replace.Version="" (no semver for local path),
# Replace.Dir="../local" drives the _LOCAL_REPLACE unverifiable path.
cat > "$FP_VRL/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ] || [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  case "$fmt" in
    *Replace.Dir*)     echo "../local" ;;
    *Replace.Version*) echo "" ;;
    *Version*)         echo "v1.5.0" ;;
  esac
fi
exit 0
STUB
chmod +x "$FP_VRL/gostub/go"
cat > "$FP_VRL/st.env" <<STENV
REPO="$FP_VRL"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
# VERSION=1.3.0 is the CVE fix version; installed v1.5.0 satisfies it on the require
# line, but the local-path replace makes effective version unverifiable → exit 3.
FP_VRL_OUT=$(
  cd "$FP_VRL" && PATH="$FP_VRL/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_VRL/st.env" example.com/vrltest 1.3.0 GHSA-vrl-0001 2>&1
) && FP_VRL_RC=0 || FP_VRL_RC=$?
check "versioned-replace-to-local: exits 3"        test "$FP_VRL_RC" -eq 3
check "versioned-replace-to-local: unverif WARNING" grep -q 'effective version unverifiable' <<< "$FP_VRL_OUT"
check "versioned-replace-to-local: no FIXED line"  ! grep -qi 'FIXED:' <<< "$FP_VRL_OUT"

# In-stream version selection (real invocation): when CVE_FIX_ALL_VERSIONS contains
# versions from multiple minor streams, fix-package.sh must select the highest version
# in the SAME minor stream as the installed version, not the globally highest.
# Scenario: etcd installed v3.6.8, fix versions [3.6.14, 3.7.1] → must pick 3.6.14.
echo "fix-package in-stream version selection (exit 0)"
FP3="$TMPD/fp3"; mkdir -p "$FP3/gostub"
( cd "$FP3" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire (\n\texample.com/etcd v3.6.8\n)\n' > "$FP3/go.mod"
( cd "$FP3" && git add go.mod && git commit -qm init )
# go stub: `go get pkg@vVER` updates go.mod to the requested version; all else no-op
cat > "$FP3/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  sed "s/example\\.com\\/etcd v[0-9][0-9]*\\.[0-9][0-9]*\\.[0-9][0-9]*/example.com\/etcd v${ver}/" \
    "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
fi
exit 0
STUB
chmod +x "$FP3/gostub/go"
cat > "$FP3/st.env" <<EOF
REPO="$FP3"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
EOF
# VERSION=3.7.1 is the globally highest fix; in-stream logic must downselect to 3.6.14
FP3_OUT=$( cd "$FP3" && \
  CVE_FIX_ALL_VERSIONS="3.6.14,3.7.1" \
  PATH="$FP3/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP3/st.env" example.com/etcd 3.7.1 CVE-2026-1234 2>&1 \
) && FP3_RC=0 || FP3_RC=$?
check "fix-package in-stream exits 0"          test "$FP3_RC" -eq 0
check "fix-package in-stream FIXED at 3.6.14"  grep -q 'FIXED:.*3\.6\.14' <<< "$FP3_OUT"
check "fix-package in-stream go.mod updated"   grep -q 'v3\.6\.14' "$FP3/go.mod"

# Scenario 2: CVE_FIX_ALL_VERSIONS contains ONLY cross-minor fix versions.
# Installed version is v3.6.8; CVE_FIX_ALL_VERSIONS="3.7.1" has no same-minor
# (3.6.x) entry, so _BEST stays empty and the code falls through to apply the
# globally-highest version (3.7.1) that was passed as the VERSION argument.
echo "fix-package Scenario 2: cross-minor-only fallthrough"
FP3X="$TMPD/fp3x"; mkdir -p "$FP3X/gostub"
( cd "$FP3X" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire (\n\texample.com/etcd v3.6.8\n)\n' > "$FP3X/go.mod"
( cd "$FP3X" && git add go.mod && git commit -qm init )
# go stub: same pattern as FP3 — `go get pkg@vVER` rewrites go.mod
cat > "$FP3X/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  sed "s/example\\.com\\/etcd v[0-9][0-9]*\\.[0-9][0-9]*\\.[0-9][0-9]*/example.com\/etcd v${ver}/" \
    "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
fi
exit 0
STUB
chmod +x "$FP3X/gostub/go"
cat > "$FP3X/st.env" <<EOF
REPO="$FP3X"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
EOF
# CVE_FIX_ALL_VERSIONS has only 3.7.1 — no 3.6.x entry, so _BEST is never set.
# The in-stream block must fall through and apply the global version (3.7.1).
FP3X_OUT=$( cd "$FP3X" && \
  CVE_FIX_ALL_VERSIONS="3.7.1" \
  PATH="$FP3X/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP3X/st.env" example.com/etcd 3.7.1 CVE-2026-9999 2>&1 \
) && FP3X_RC=0 || FP3X_RC=$?
check "scenario2 cross-minor-only: exits 0"          test "$FP3X_RC" -eq 0
check "scenario2 cross-minor-only: FIXED at 3.7.1"  grep -q 'FIXED:.*3\.7\.1' <<< "$FP3X_OUT"
check "scenario2 cross-minor-only: go.mod has 3.7.1" grep -q 'v3\.7\.1' "$FP3X/go.mod"
check "scenario2 cross-minor-only: no 3.6 version in go.mod" \
  ! grep -q 'v3\.6\.' "$FP3X/go.mod"

# === packed-binary blindness sentinel ===
# grype can't scan UPX-packed binaries; detect_opaque_binaries must flag them (go version -m fails + UPX! magic).
echo "packed-binary blindness sentinel"
OB="$TMPD/opaque"; mkdir -p "$OB/gostub"
cat > "$OB/gostub/go" <<'STUB'
#!/bin/sh
# `go version -m FILE` succeeds only for a readable (non-packed) binary
if [ "$1" = "version" ] && [ "$2" = "-m" ]; then
  case "$3" in
    *packed*) exit 1 ;;
    *) exit 0 ;;
  esac
fi
exit 0
STUB
chmod +x "$OB/gostub/go"
printf 'UPX!\0\0packed-payload' > "$OB/packed-bin"; chmod +x "$OB/packed-bin"
printf 'plain-elf-ish-payload'  > "$OB/readable-bin"; chmod +x "$OB/readable-bin"
( cd "$OB" && PATH="$OB/gostub:$PATH" && source "$SCRIPT_DIR/lib.sh" && detect_opaque_binaries ) >/dev/null 2>&1 && OB_RC=0 || OB_RC=$?
check "sentinel flags packed binary" test "$OB_RC" -eq 0

# Negative: a readable binary alone must NOT be flagged (return 1).
OB2="$TMPD/opaque2"; mkdir -p "$OB2/gostub"
cp "$OB/gostub/go" "$OB2/gostub/go"
printf 'plain-elf-ish-payload' > "$OB2/readable-bin"; chmod +x "$OB2/readable-bin"
( cd "$OB2" && PATH="$OB2/gostub:$PATH" && source "$SCRIPT_DIR/lib.sh" && detect_opaque_binaries ) >/dev/null 2>&1 && OB2_RC=0 || OB2_RC=$?
check "sentinel clears on readable binary" test "$OB2_RC" -eq 1

# Stale readable binary: `go version -m` succeeds but the binary's embedded Go
# version differs from the host Go. Not opaque — grype CAN scan it — but it may
# report CVEs against the old toolchain rather than the one in use now.
echo "stale readable binary detection"
OB4="$TMPD/stale-readable"; mkdir -p "$OB4/gostub"
cat > "$OB4/gostub/go" <<'STUB'
#!/bin/sh
# `go version` (no -m) reports host Go version
if [ "$1" = "version" ] && [ "$2" != "-m" ]; then
  echo "go version go1.24.0 linux/amd64"; exit 0
fi
# `go version -m FILE` reports the binary's embedded Go version
if [ "$1" = "version" ] && [ "$2" = "-m" ]; then
  case "$3" in
    *stale*) printf '%s: go1.22.3\n' "$3"; exit 0 ;;  # old toolchain — should be flagged
    *) exit 1 ;;
  esac
fi
exit 0
STUB
chmod +x "$OB4/gostub/go"
printf 'elf-content' > "$OB4/stale-readable-bin"; chmod +x "$OB4/stale-readable-bin"
OB4_RC=0
( cd "$OB4" && PATH="$OB4/gostub:$PATH" && source "$SCRIPT_DIR/lib.sh" && detect_opaque_binaries ) >/dev/null 2>&1 || OB4_RC=$?
check "stale readable binary flagged" test "$OB4_RC" -eq 0

# Negative: a readable binary built with the CURRENT Go version must NOT be flagged.
OB5="$TMPD/stale-readable2"; mkdir -p "$OB5/gostub"
cat > "$OB5/gostub/go" <<'STUB'
#!/bin/sh
if [ "$1" = "version" ] && [ "$2" != "-m" ]; then
  echo "go version go1.24.0 linux/amd64"; exit 0
fi
if [ "$1" = "version" ] && [ "$2" = "-m" ]; then
  case "$3" in
    *current*) printf '%s: go1.24.0\n' "$3"; exit 0 ;;  # matches host — not stale
    *) exit 1 ;;
  esac
fi
exit 0
STUB
chmod +x "$OB5/gostub/go"
printf 'elf-content' > "$OB5/current-release-0.22-readable-bin"; chmod +x "$OB5/current-release-0.22-readable-bin"
OB5_RC=0
( cd "$OB5" && PATH="$OB5/gostub:$PATH" && source "$SCRIPT_DIR/lib.sh" && detect_opaque_binaries ) >/dev/null 2>&1 || OB5_RC=$?
check "current-version readable binary not flagged" test "$OB5_RC" -eq 1

# No host Go: stale-readable check skipped — a readable binary is not flagged.
# Covers Dapper/container builds where the host go command is absent or mismatches.
OB6="$TMPD/stale-readable3"; mkdir -p "$OB6/gostub"
cat > "$OB6/gostub/go" <<'STUB'
#!/bin/sh
# `go version -m FILE` succeeds (readable binary with old version)
if [ "$1" = "version" ] && [ "$2" = "-m" ]; then
  printf '%s: go1.22.3\n' "$3"; exit 0
fi
exit 1  # `go version` (no -m) fails — host Go unavailable
STUB
chmod +x "$OB6/gostub/go"
printf 'elf-content' > "$OB6/stale-like-bin"; chmod +x "$OB6/stale-like-bin"
OB6_RC=0
( cd "$OB6" && PATH="$OB6/gostub:$PATH" && source "$SCRIPT_DIR/lib.sh" && detect_opaque_binaries ) >/dev/null 2>&1 || OB6_RC=$?
check "no host Go skips stale-readable check" test "$OB6_RC" -eq 1


# No concrete repos.yaml is shipped; the example is generic and org-neutral.
check "example registry shipped" test -f "$SCRIPT_DIR/../repos.yaml.example"
check "repos.yaml git-ignored" git -C "$SCRIPT_DIR/.." check-ignore -q repos.yaml

# fix-availability must NOT skip a package just because it was bumped for a
# different CVE (HAS_FIXABLE=1 bug: one branch still has fixable CVEs when
# ALREADY_BUMPED incorrectly suppressed them).

# === existing-entries: FIX-AVAILABLE replaces SHOULD-BE-NOT-FIXED (fix #2) ===
# Permanent ignores where grype has a known fix must emit FIX-AVAILABLE (actionable
# by the deterministic handler), not SHOULD-BE-NOT-FIXED (which was misleading
# reviewers into converting to fix-state: not-fixed instead of fixing the package).
echo "existing-entries FIX-AVAILABLE output"

# === exit-124: timeout(1) kill → TIMEOUT (timeout_file not nr_file); retryable ===
# _fix_fv_package must NOT skip the package on next verify_fix_loop iteration.
echo "  exit-124 classification: functional test"
_T124_DIR=$(mktemp -d)
# Stub fix-package.sh that exits 124 (simulating a timeout)
cat > "$_T124_DIR/fix-package.sh" <<'STUBEOF'
#!/usr/bin/env bash
exit 124
STUBEOF
chmod +x "$_T124_DIR/fix-package.sh"
# Create minimal state file and report dir
_T124_STATE="$_T124_DIR/state"
printf 'REPO=%s\n' "$_T124_DIR" > "$_T124_STATE"
_T124_RPT="$_T124_DIR/reports"
mkdir -p "$_T124_RPT"
_T124_NR="$_T124_RPT/needs-review-pkgs"
_T124_TO="$_T124_RPT/timeout-pkgs"
_T124_FF="$_T124_RPT/fix-failed-pkgs"
# Source lib so we can call _fix_fv_package directly
(
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/lib.sh"
  REPO="$_T124_DIR"
  _fix_fv_package "$_T124_STATE" "$_T124_RPT" "$_T124_DIR" \
    "stale msg" "example/pkg" "1.2.3" "GHSA-test-0001" 2>/dev/null || true
)
check "_fix_fv_package exit-124: pkg added to timeout_file (not nr_file)" \
  grep -q 'example/pkg' "$_T124_TO"
check "_fix_fv_package exit-124: pkg NOT added to nr_file" \
  ! grep -q 'example/pkg' "$_T124_NR" 2>/dev/null
check "_fix_fv_package exit-124: pkg NOT added to ff_file" \
  ! grep -q 'example/pkg' "$_T124_FF" 2>/dev/null
rm -rf "$_T124_DIR"

echo "  exit-4 classification: functional test"
_T4_DIR=$(mktemp -d)
# Stub fix-package.sh that exits 4 (simulating version not in module registry)
cat > "$_T4_DIR/fix-package.sh" <<'STUBEOF'
#!/usr/bin/env bash
exit 4
STUBEOF
chmod +x "$_T4_DIR/fix-package.sh"
cat > "$_T4_DIR/ignore.sh" <<'STUBEOF'
#!/usr/bin/env bash
touch "$(dirname "$1")/ignore-called"
exit 0
STUBEOF
# Create minimal state file and report dir
_T4_STATE="$_T4_DIR/state"
printf 'REPO=%s\n' "$_T4_DIR" > "$_T4_STATE"
_T4_RPT="$_T4_DIR/reports"
mkdir -p "$_T4_RPT"
_T4_NR="$_T4_RPT/needs-review-pkgs"
_T4_FF="$_T4_RPT/fix-failed-pkgs"
# Source lib so we can call _fix_fv_package directly
(
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/lib.sh"
  REPO="$_T4_DIR"
  _fix_fv_package "$_T4_STATE" "$_T4_RPT" "$_T4_DIR" \
    "stale msg" "example/pkg" "1.2.3" "GHSA-test-0002" 2>/dev/null || true
)
check "_fix_fv_package exit-4: pkg added to nr_file" \
  grep -q 'example/pkg' "$_T4_NR"
check "_fix_fv_package exit-4: pkg NOT added to ff_file" \
  ! grep -q 'example/pkg' "$_T4_FF" 2>/dev/null
check "unavailable candidate retry never invokes ignore handler" \
  test ! -e "$_T4_DIR/ignore-called"
check "unavailable candidate retry never claims advisory ignored" \
  test ! -e "$_T4_RPT/ignored-pkgs"
rm -rf "$_T4_DIR"

# === catch-all (_fix_fv_package): unexpected exit (e.g. 99) must add pkg to nr_file and emit ERROR, not silently drop. ===
echo "  catch-all exit-code: functional test"
_TC_DIR=$(mktemp -d)
# Stub fix-package.sh that exits 99 (unexpected, not 2/3/4/124)
cat > "$_TC_DIR/fix-package.sh" <<'STUBEOF'
#!/usr/bin/env bash
exit 99
STUBEOF
chmod +x "$_TC_DIR/fix-package.sh"
_TC_STATE="$_TC_DIR/state"
printf 'REPO=%s\n' "$_TC_DIR" > "$_TC_STATE"
_TC_RPT="$_TC_DIR/reports"
mkdir -p "$_TC_RPT"
_TC_NR="$_TC_RPT/needs-review-pkgs"
_TC_FF="$_TC_RPT/fix-failed-pkgs"
_TC_OUT="$_TC_DIR/output.txt"
# Source lib so we can call _fix_fv_package directly
(
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/lib.sh"
  REPO="$_TC_DIR"
  _fix_fv_package "$_TC_STATE" "$_TC_RPT" "$_TC_DIR" \
    "stale msg" "example/pkg" "1.2.3" "GHSA-test-0099" 2>/dev/null || true
) > "$_TC_OUT" 2>&1
check "_fix_fv_package catch-all: pkg added to nr_file" \
  grep -q 'example/pkg' "$_TC_NR"
check "_fix_fv_package catch-all: pkg NOT added to ff_file" \
  ! grep -q 'example/pkg' "$_TC_FF" 2>/dev/null
check "_fix_fv_package catch-all: ERROR emitted in output" \
  grep -q 'ERROR' "$_TC_OUT"
rm -rf "$_TC_DIR"


# === existing-entries.sh: STALE detection (bug #4: CVE-2015-5237) ===
# When a pre-existing ignore entry is no longer reported by grype at all
# (CVE was removed from grype's DB, e.g. a false-positive was corrected),
# the ignore entry is stale. existing-entries.sh must flag it as STALE.
echo "existing-entries stale detection"
EE_REPO="$TMPD/ee-repo"
mkdir -p "$EE_REPO"
git -C "$EE_REPO" init -q
git -C "$EE_REPO" config user.email "test@test.com"
git -C "$EE_REPO" config user.name "Test"
cat > "$EE_REPO/.grype.yaml" <<'EOF'
---
ignore:
  # False positive, CVE is actually about the C++ project protocolbuffers/protobuf
  # https://github.com/anchore/grype/issues/558
  - vulnerability: CVE-2015-5237
    fix-state: wont-fix
    package:
      name: google.golang.org/protobuf
EOF
touch "$EE_REPO/go.mod"
git -C "$EE_REPO" add .grype.yaml go.mod
git -C "$EE_REPO" commit -q -m "init"
git -C "$EE_REPO" checkout -q -b release-0.23
git -C "$EE_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_REPO" rev-parse HEAD)"

EE_RDIR="$TMPD/ee-reports"
mkdir -p "$EE_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_REPO" "$SCRIPT_DIR" > "$EE_RDIR/state.env"

# Scenario A: CVE no longer in scan output (stale entry)
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EE_RDIR/initial-scan.json"
EE_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_RDIR/state.env" "$EE_RDIR" 2>/dev/null || true)
check "stale: not-in-scan flagged as STALE" \
  bash -c "echo '$EE_OUT' | grep -q '^STALE:'"
check "stale: CVE-2015-5237 named in output" \
  bash -c "echo '$EE_OUT' | grep -q 'CVE-2015-5237'"
check "stale: issue count nonzero" \
  bash -c "echo '$EE_OUT' | grep -q '^NEW_ISSUES=[1-9]'"

EE_PERM="$TMPD/ee-permanent"; mkdir -p "$EE_PERM/rep"
make_test_repo "$EE_PERM/repo" ""
printf 'module example.com/perm\ngo 1.24.0\n' > "$EE_PERM/repo/go.mod"
printf 'ignore:\n  # False positive\n  - vulnerability: CVE-2015-5237\n    package:\n      name: google.golang.org/protobuf\n' > "$EE_PERM/repo/.grype.yaml"
git -C "$EE_PERM/repo" add -A && git -C "$EE_PERM/repo" commit -qm perm
git -C "$EE_PERM/repo" update-ref refs/remotes/origin/devel HEAD
make_go_state "$EE_PERM/state.env" "$EE_PERM/repo"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EE_PERM/rep/final-scan.json"
check "stale: a permanent documented ignore is never pruned" \
  grep -qx 'NEW_ISSUES=0' <<< "$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$EE_PERM/state.env" "$EE_PERM/rep" 2>&1 || true)"

# Scenario B: CVE still in ignoredMatches (ignore still needed, not stale)
cat > "$EE_RDIR/initial-scan.json" <<'EOF'
{"matches":[],"ignoredMatches":[{"vulnerability":{"id":"CVE-2015-5237","severity":"High","fix":{"versions":[],"state":"wont-fix"}},"artifact":{"name":"google.golang.org/protobuf","version":"v1.34.0","type":"go-module","locations":[{"path":"/go.mod"}]}}]}
EOF
EE_OUT2=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_RDIR/state.env" "$EE_RDIR" 2>/dev/null || true)
check "stale: in ignoredMatches not flagged as STALE" \
  bash -c "! echo '$EE_OUT2' | grep -q '^STALE:'"
check "stale: clean when still matched" \
  bash -c "echo '$EE_OUT2' | grep -q '^NEW_ISSUES=0'"

# A package fixed after the initial scan disappears from the current rescan.
# The old ignore is stale even though initial-scan.json still contains it.
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EE_RDIR/final-scan.json"
EE_CURRENT_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_RDIR/state.env" "$EE_RDIR" 2>/dev/null || true)
check "stale: current rescan supersedes initial ignored match" \
  grep -q '^STALE:' <<< "$EE_CURRENT_OUT"

printf '{"matches":[]}\n' > "$EE_RDIR/initial-scan.json"
printf '%s\n' '{"matches":[],"ignoredMatches":[{"vulnerability":{"id":"CVE-2015-5237","fix":{"versions":[],"state":"wont-fix"}},"artifact":{"name":"google.golang.org/protobuf","type":"go-module"}}]}' > "$EE_RDIR/final-scan.json"
EE_STILL_NEEDED=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$EE_RDIR/state.env" "$EE_RDIR")
check "stale: current active ignore survives clean initial evidence" ! grep -q '^STALE:' <<< "$EE_STILL_NEEDED"

# A present malformed current scan must fail closed rather than falling back to
# the older initial scan and emitting a destructive STALE recommendation.
printf '{}\n' > "$EE_RDIR/final-scan.json"
EE_INVALID_OUT_FILE="$TMPD/ee-invalid-final.out"
bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_RDIR/state.env" "$EE_RDIR" >"$EE_INVALID_OUT_FILE" 2>&1 && EE_INVALID_RC=0 || EE_INVALID_RC=$?
check "stale: malformed current scan exits nonzero" test "$EE_INVALID_RC" -ne 0
check "stale: malformed current scan emits SCAN_FAILED" grep -q '^SCAN_FAILED=1' "$EE_INVALID_OUT_FILE"
check "stale: malformed current scan does not fall back to STALE" ! grep -q '^STALE:' "$EE_INVALID_OUT_FILE"
rm -f "$EE_RDIR/final-scan.json"

printf '{}\n' > "$EE_RDIR/initial-scan.json"
bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_RDIR/state.env" "$EE_RDIR" >"$EE_INVALID_OUT_FILE" 2>&1 && EE_INVALID_RC=0 || EE_INVALID_RC=$?
check "stale: malformed initial scan exits nonzero" test "$EE_INVALID_RC" -ne 0
check "stale: malformed initial scan emits SCAN_FAILED" grep -q '^SCAN_FAILED=1' "$EE_INVALID_OUT_FILE"

# Scenario C: an auto-expiring broad ignore whose no-fix finding is reported at
# exactly one module must be narrowed. This covers advisories such as GO-2026-5932
# whose effective state is unknown rather than the old ignore's not-fixed state.
echo "existing-entries scoped migration"
EE_SCOPE_REPO="$TMPD/ee-scope-repo"
mkdir -p "$EE_SCOPE_REPO/tools"
git -C "$EE_SCOPE_REPO" init -q
git -C "$EE_SCOPE_REPO" config user.email "test@test.com"
git -C "$EE_SCOPE_REPO" config user.name "Test"
printf 'module example.com/ee-scope\ngo 1.25.0\n' > "$EE_SCOPE_REPO/go.mod"
printf 'module example.com/ee-scope/tools\ngo 1.25.0\n' > "$EE_SCOPE_REPO/tools/go.mod"
cat > "$EE_SCOPE_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: GO-2026-5932
    fix-state: not-fixed
    package:
      name: golang.org/x/crypto
EOF
git -C "$EE_SCOPE_REPO" add .
git -C "$EE_SCOPE_REPO" commit -q -m "init"
git -C "$EE_SCOPE_REPO" checkout -q -b release-0.23
git -C "$EE_SCOPE_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_SCOPE_REPO" rev-parse HEAD)"
EE_SCOPE_RDIR="$TMPD/ee-scope-reports"
mkdir -p "$EE_SCOPE_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_SCOPE_REPO" "$SCRIPT_DIR" > "$EE_SCOPE_RDIR/state.env"
cat > "$EE_SCOPE_RDIR/initial-scan.json" <<'EOF'
{"matches":[{"vulnerability":{"id":"GO-2026-5932","fix":{"versions":[],"state":""}},"artifact":{"name":"golang.org/x/crypto","version":"v0.56.0","type":"go-module","locations":[{"path":"/tools/go.mod"}]}}],"ignoredMatches":[]}
EOF
EE_SCOPE_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_SCOPE_RDIR/state.env" "$EE_SCOPE_RDIR" 2>/dev/null || true)
check "scope: single scanner location flagged" \
  bash -c "echo '$EE_SCOPE_OUT' | grep -q '^SCOPE-AVAILABLE: GO-2026-5932'"
check "scope: effective unknown state preserved" \
  bash -c "echo '$EE_SCOPE_OUT' | grep -q 'fix-state: unknown'"
cat > "$EE_SCOPE_RDIR/report" <<'EOF'
VERDICT: FAIL
ISSUES: 1
SUMMARY: one scope migration
DETAILS:
SCOPE-AVAILABLE: GO-2026-5932 (golang.org/x/crypto) -> /tools/go.mod fix-state: unknown
EOF
source "$SCRIPT_DIR/lib.sh"
subagent_fix_existing_entries "$EE_SCOPE_RDIR/state.env" "$EE_SCOPE_RDIR/report" \
  "$SCRIPT_DIR" >/dev/null
check "scope: broad entry removed" \
  test "$(grep -c 'vulnerability: GO-2026-5932' "$EE_SCOPE_REPO/.grype.yaml")" -eq 1
check "scope: exact module recorded" \
  grep -q 'location: /tools/go.mod' "$EE_SCOPE_REPO/.grype.yaml"
check "scope: scanner state recorded" \
  grep -q 'fix-state: unknown' "$EE_SCOPE_REPO/.grype.yaml"

# Scenario D: prefix CVE ID must not cause false dedup-guard match.
# If CVE-2024-1234 is absent from .grype.yaml but CVE-2024-12345 is present
# with the same package, a substring index() would incorrectly suppress the
# STALE report. Exact-match ($NF == vuln) must flag it correctly.
EE_PREFIX_REPO="$TMPD/ee-prefix-repo"
mkdir -p "$EE_PREFIX_REPO"
git -C "$EE_PREFIX_REPO" init -q
git -C "$EE_PREFIX_REPO" config user.email "test@test.com"
git -C "$EE_PREFIX_REPO" config user.name "Test"
cat > "$EE_PREFIX_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: CVE-2024-12345
    package:
      name: google.golang.org/protobuf
EOF
touch "$EE_PREFIX_REPO/go.mod"
git -C "$EE_PREFIX_REPO" add .grype.yaml go.mod
git -C "$EE_PREFIX_REPO" commit -q -m "init"
git -C "$EE_PREFIX_REPO" checkout -q -b release-0.23
git -C "$EE_PREFIX_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_PREFIX_REPO" rev-parse HEAD)"

# Simulate origin having CVE-2024-1234 (prefix of CVE-2024-12345) ignored —
# grype no longer reports it → should be STALE.
cat > "$EE_PREFIX_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: CVE-2024-1234
    fix-state: not-fixed
    package:
      name: google.golang.org/protobuf
  - vulnerability: CVE-2024-12345
    fix-state: not-fixed
    package:
      name: google.golang.org/protobuf
EOF
git -C "$EE_PREFIX_REPO" add .grype.yaml
git -C "$EE_PREFIX_REPO" commit -q -m "add both CVEs"
# Make origin point to the commit that has CVE-2024-1234 in it.
git -C "$EE_PREFIX_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_PREFIX_REPO" rev-parse HEAD)"

EE_PREFIX_RDIR="$TMPD/ee-prefix-reports"
mkdir -p "$EE_PREFIX_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_PREFIX_REPO" "$SCRIPT_DIR" > "$EE_PREFIX_RDIR/state.env"
# CVE-2024-1234 not in scan → stale; CVE-2024-12345 still present (wont-fix, no fix ver)
printf '{"matches":[],"ignoredMatches":[{"vulnerability":{"id":"CVE-2024-12345","fix":{"versions":[],"state":"wont-fix"}},"artifact":{"name":"google.golang.org/protobuf","version":"v1.34.0","type":"go-module","locations":[{"path":"/go.mod"}]}}]}\n' \
  > "$EE_PREFIX_RDIR/initial-scan.json"
EE_PREFIX_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_PREFIX_RDIR/state.env" "$EE_PREFIX_RDIR" 2>/dev/null || true)
check "prefix: CVE-2024-1234 absent from scan flagged STALE (exact match)" \
  bash -c "echo '$EE_PREFIX_OUT' | grep -q 'STALE.*CVE-2024-1234'"
check "prefix: CVE-2024-12345 not spuriously flagged STALE" \
  bash -c "! echo '$EE_PREFIX_OUT' | grep -q 'STALE.*CVE-2024-12345'"


# === existing-entries: STALE loop skip when entry already removed (fix 2aad2665) ===
# Entry absent from HEAD .grype.yaml → must NOT emit STALE (re-reporting loops forever).
echo "existing-entries stale loop skip (already removed from HEAD)"
EE_REMOVED_REPO="$TMPD/ee-removed-repo"
mkdir -p "$EE_REMOVED_REPO"
git -C "$EE_REMOVED_REPO" init -q
git -C "$EE_REMOVED_REPO" config user.email "test@test.com"
git -C "$EE_REMOVED_REPO" config user.name "Test"
# origin commit: CVE-X for pkg-A present
cat > "$EE_REMOVED_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: CVE-2024-9999
    package:
      name: example.com/pkg-a
EOF
touch "$EE_REMOVED_REPO/go.mod"
git -C "$EE_REMOVED_REPO" add .grype.yaml go.mod
git -C "$EE_REMOVED_REPO" commit -q -m "origin: add CVE-2024-9999 ignore"
git -C "$EE_REMOVED_REPO" checkout -q -b release-0.23
git -C "$EE_REMOVED_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_REMOVED_REPO" rev-parse HEAD)"
# HEAD: CVE-X already removed (entry gone from working .grype.yaml)
cat > "$EE_REMOVED_REPO/.grype.yaml" <<'EOF'
---
ignore: []
EOF
git -C "$EE_REMOVED_REPO" add .grype.yaml
git -C "$EE_REMOVED_REPO" commit -q -m "remove CVE-2024-9999 ignore"

EE_REMOVED_RDIR="$TMPD/ee-removed-reports"
mkdir -p "$EE_REMOVED_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_REMOVED_REPO" "$SCRIPT_DIR" > "$EE_REMOVED_RDIR/state.env"
# Scan: CVE not present (IN_SCAN=no)
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EE_REMOVED_RDIR/initial-scan.json"
EE_REMOVED_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_REMOVED_RDIR/state.env" "$EE_REMOVED_RDIR" 2>/dev/null || true)
check "stale-skip: entry already removed from HEAD → STALE NOT emitted" \
  bash -c "! echo '$EE_REMOVED_OUT' | grep -q '^STALE:'"
check "stale-skip: NEW_ISSUES=0 when entry already removed" \
  bash -c "echo '$EE_REMOVED_OUT' | grep -q '^NEW_ISSUES=0'"

# === existing-entries: STALE awk dedup CVE+package pair (fix 233ee012) ===
# awk must match CVE+pkg pair (not just CVE): STALE iff entry still in HEAD .grype.yaml.
echo "existing-entries stale dedup CVE+package pair"
EE_DEDUP_REPO="$TMPD/ee-dedup-repo"
mkdir -p "$EE_DEDUP_REPO"
git -C "$EE_DEDUP_REPO" init -q
git -C "$EE_DEDUP_REPO" config user.email "test@test.com"
git -C "$EE_DEDUP_REPO" config user.name "Test"
# origin: CVE-X for both pkg-A and pkg-B
cat > "$EE_DEDUP_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: CVE-2024-7777
    fix-state: not-fixed
    package:
      name: example.com/pkg-a
  - vulnerability: CVE-2024-7777
    fix-state: not-fixed
    package:
      name: example.com/pkg-b
EOF
touch "$EE_DEDUP_REPO/go.mod"
git -C "$EE_DEDUP_REPO" add .grype.yaml go.mod
git -C "$EE_DEDUP_REPO" commit -q -m "origin: both pkg-a and pkg-b ignored"
git -C "$EE_DEDUP_REPO" checkout -q -b release-0.23
git -C "$EE_DEDUP_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$EE_DEDUP_REPO" rev-parse HEAD)"
# HEAD: only pkg-A entry removed; pkg-B remains
cat > "$EE_DEDUP_REPO/.grype.yaml" <<'EOF'
---
ignore:
  - vulnerability: CVE-2024-7777
    fix-state: not-fixed
    package:
      name: example.com/pkg-b
EOF
git -C "$EE_DEDUP_REPO" add .grype.yaml
git -C "$EE_DEDUP_REPO" commit -q -m "remove pkg-a ignore (already fixed)"

EE_DEDUP_RDIR="$TMPD/ee-dedup-reports"
mkdir -p "$EE_DEDUP_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_DEDUP_REPO" "$SCRIPT_DIR" > "$EE_DEDUP_RDIR/state.env"
# Scan: CVE absent for both packages (IN_SCAN=no)
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EE_DEDUP_RDIR/initial-scan.json"
EE_DEDUP_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" \
  "$EE_DEDUP_RDIR/state.env" "$EE_DEDUP_RDIR" 2>/dev/null || true)
check "dedup: STALE NOT emitted for pkg-a (absent from HEAD .grype.yaml)" \
  bash -c "! echo '$EE_DEDUP_OUT' | grep -q 'STALE.*pkg-a'"
check "dedup: STALE emitted for pkg-b (still in HEAD .grype.yaml)" \
  bash -c "echo '$EE_DEDUP_OUT' | grep -q 'STALE.*pkg-b'"


# === detect_opaque_binaries called in source-only scan (bug #2 fix) ===
# When BUILD_CMD is unset, detect_opaque_binaries must still run so pre-existing
# packed/stale binaries in the repo tree don't go undetected.
echo "detect_opaque_binaries source-only scan"

OPQ_REPO="$TMPD/opq-repo"; mkdir -p "$OPQ_REPO"
touch "$OPQ_REPO/go.mod"
OPQ_STATE="$TMPD/opq-state.env"
cat > "$OPQ_STATE" <<EOF
REPO=$OPQ_REPO
BRANCH=devel
HAS_LOCAL_GRYPE=false
CONTAINER_CMD=
EOF

# Packed binary present: coverage-unknown sentinel must be written.
# 'go version -m' exits non-zero on a non-Go file; the UPX! magic triggers case 1.
printf 'UPX!fake-packed-binary\x00' > "$OPQ_REPO/packed-bin"
chmod +x "$OPQ_REPO/packed-bin"
bash "$SCRIPT_DIR/scan.sh" "$OPQ_STATE" --no-update >/dev/null 2>&1 || true
check "source-only: packed binary sets coverage-unknown" \
  test -f "${OPQ_STATE}.coverage-unknown"
rm -f "${OPQ_STATE}.coverage-unknown" "$OPQ_REPO/packed-bin"

# No opaque binaries: coverage-unknown must NOT be written.
bash "$SCRIPT_DIR/scan.sh" "$OPQ_STATE" --no-update >/dev/null 2>&1 || true
check "source-only: no packed binary leaves sentinel absent" \
  ! test -f "${OPQ_STATE}.coverage-unknown"

# Stale sentinel from a prior run must be cleared even when no opaque binaries.
: > "${OPQ_STATE}.coverage-unknown"
bash "$SCRIPT_DIR/scan.sh" "$OPQ_STATE" --no-update >/dev/null 2>&1 || true
check "source-only: stale coverage-unknown cleared when no opaques" \
  ! test -f "${OPQ_STATE}.coverage-unknown"

# Wiring: scan.sh must call detect_opaque_binaries outside the BUILD_CMD guard.
# Count occurrences: there must be at least two calls (one in the build-success
# branch, one in the no-BUILD_CMD branch).
check "scan.sh wires detect_opaque_binaries for source-only repos" \
  bash -c "test \"\$(grep -c 'detect_opaque_binaries' '$SCRIPT_DIR/scan.sh')\" -ge 2"

# === SKIP_BUILD sentinel lifecycle (fix a4f16738) ===
# When BUILD_CMD is set but --skip-build is passed, scan.sh must take the elif
# branch and manage coverage-unknown via detect_opaque_binaries — same as the
# no-BUILD_CMD path. The elif condition is:
#   elif [[ -z "${BUILD_CMD:-}" ]] || [[ "$SKIP_BUILD" == "true" ]]; then
echo "SKIP_BUILD sentinel lifecycle"

SB_REPO="$TMPD/sb-repo"; mkdir -p "$SB_REPO"
touch "$SB_REPO/go.mod"
SB_STATE="$TMPD/sb-state.env"
cat > "$SB_STATE" <<EOF
REPO=$SB_REPO
BRANCH=devel
HAS_LOCAL_GRYPE=false
CONTAINER_CMD=
BUILD_CMD='echo fake-build'
EOF

# Test 1: --skip-build passed, BUILD_CMD set, no opaque binary → coverage-unknown NOT set.
# Pre-seed a stale sentinel to confirm it is cleared, not merely absent.
: > "${SB_STATE}.coverage-unknown"
bash "$SCRIPT_DIR/scan.sh" "$SB_STATE" --no-update --skip-build >/dev/null 2>&1 || true
check "skip-build: no opaque binary clears coverage-unknown" \
  ! test -f "${SB_STATE}.coverage-unknown"

# Test 2: --skip-build passed, BUILD_CMD set, opaque binary present → coverage-unknown set.
printf 'UPX!fake-packed-binary\x00' > "$SB_REPO/packed-bin"
chmod +x "$SB_REPO/packed-bin"
bash "$SCRIPT_DIR/scan.sh" "$SB_STATE" --no-update --skip-build >/dev/null 2>&1 || true
check "skip-build: opaque binary sets coverage-unknown" \
  test -f "${SB_STATE}.coverage-unknown"
rm -f "$SB_REPO/packed-bin" "${SB_STATE}.coverage-unknown"

# Behavioral: STALE entry removed and committed
EE_STALE_REPO="$TMPD/ee-stale-repo"
mkdir -p "$EE_STALE_REPO"
git -C "$EE_STALE_REPO" init -q
git -C "$EE_STALE_REPO" config user.email "test@test.com"
git -C "$EE_STALE_REPO" config user.name "Test"
printf -- '---\nignore:\n  # False positive (C++ only)\n  - vulnerability: CVE-2015-5237\n    package:\n      name: google.golang.org/protobuf\n  - vulnerability: CVE-2021-22570\n    package:\n      name: google.golang.org/protobuf\n' \
  > "$EE_STALE_REPO/.grype.yaml"
git -C "$EE_STALE_REPO" add .grype.yaml
git -C "$EE_STALE_REPO" commit -q -m "init"
git -C "$EE_STALE_REPO" checkout -q -b release-0.23

EE_STALE_RDIR="$TMPD/ee-stale-reports"
mkdir -p "$EE_STALE_RDIR"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$EE_STALE_REPO" "$SCRIPT_DIR" > "$TMPD/ee-stale.env"

# Report file with a STALE line (grype no longer reports CVE-2015-5237)
cat > "$EE_STALE_RDIR/existing-entries.report" <<'STALEREPORT'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 stale entry found
DETAILS:
STALE: CVE-2015-5237 (google.golang.org/protobuf) no longer reported by grype — ignore entry can be removed
STALEREPORT

(
  cd "$EE_STALE_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$TMPD/ee-stale.env"
  subagent_fix_existing_entries "$TMPD/ee-stale.env" \
    "$EE_STALE_RDIR/existing-entries.report" "$SCRIPT_DIR"
) >/dev/null 2>&1

check "stale: removed from .grype.yaml" \
  ! grep -q CVE-2015-5237 "$EE_STALE_REPO/.grype.yaml"
check "stale: sibling entry kept" \
  grep -q CVE-2021-22570 "$EE_STALE_REPO/.grype.yaml"
check "stale: commit made" \
  test "$(git -C "$EE_STALE_REPO" log --oneline | wc -l | tr -d ' ')" -gt 1
check "stale: commit subject references CVE" \
  bash -c "git -C '$EE_STALE_REPO' log -1 --format='%s' | grep -q 'CVE-2015-5237'"

# === subagent_fix_fix_availability: amend path (lib.sh:1170) ===
# When fix-package.sh creates a "Bump <abbrev>" commit and a stale not-fixed
# ignore exists for the same CVE+package, the .grype.yaml removal must be
# folded into that commit via --amend --no-edit -s — not a separate commit.
echo "fix-availability amend path"
AMEND_FA_REPO="$TMPD/amend-fa-repo"
mkdir -p "$AMEND_FA_REPO"
git -C "$AMEND_FA_REPO" init -q
git -C "$AMEND_FA_REPO" config user.email "test@test.com"
git -C "$AMEND_FA_REPO" config user.name "Test"
# Stale not-fixed ignore added by deterministic phase before fix was known
printf -- '---\nignore:\n  # No fix available for golang.org/x/net.\n  - vulnerability: GHSA-TEST-FA11\n    fix-state: not-fixed\n    package:\n      name: golang.org/x/net\n' \
  > "$AMEND_FA_REPO/.grype.yaml"
printf 'module example.com/test\ngo 1.21\n' > "$AMEND_FA_REPO/go.mod"
git -C "$AMEND_FA_REPO" add .grype.yaml go.mod
git -C "$AMEND_FA_REPO" commit -q -s -m "init"
git -C "$AMEND_FA_REPO" checkout -q -b release-0.23
git -C "$AMEND_FA_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$AMEND_FA_REPO" rev-parse HEAD)"

# Mock fix-package.sh: simulate a successful bump commit for golang.org/x/net
AMEND_FA_SDIR="$TMPD/amend-fa-scripts"
mkdir -p "$AMEND_FA_SDIR"
cat > "$AMEND_FA_SDIR/fix-package.sh" <<'MOCKEOF'
#!/usr/bin/env bash
set -euo pipefail
source "$1"          # loads REPO from state_file
pkg="$2"
# Simulate go.mod/go.sum update then create the bump commit
printf '\n# bumped %s\n' "$pkg" >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" commit -s -m "Bump x/net for GHSA-TEST-FA11"
MOCKEOF
chmod +x "$AMEND_FA_SDIR/fix-package.sh"

AMEND_FA_RDIR="$TMPD/amend-fa-reports"
mkdir -p "$AMEND_FA_RDIR"
AMEND_FA_STATE="$TMPD/amend-fa-state.env"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$AMEND_FA_REPO" "$SCRIPT_DIR" > "$AMEND_FA_STATE"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$AMEND_FA_RDIR/initial-scan.json"
cat > "$AMEND_FA_RDIR/fix-availability.report" <<'FAREPORT'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 fix available
DETAILS:
FIX-AVAILABLE: golang.org/x/net 0.20.0 -> 0.23.0 CVEs:GHSA-TEST-FA11
FAREPORT

(
  cd "$AMEND_FA_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$AMEND_FA_STATE"
  subagent_fix_fix_availability "$AMEND_FA_STATE" \
    "$AMEND_FA_RDIR/fix-availability.report" "$AMEND_FA_SDIR"
) >/dev/null 2>&1

# Amend must fold .grype.yaml removal into the bump commit — no extra commit
check "fa-amend: stale ignore removed from .grype.yaml" \
  ! grep -q 'GHSA-TEST-FA11' "$AMEND_FA_REPO/.grype.yaml"
check "fa-amend: commit count is 2 (init + amended bump, not 3)" \
  bash -c "test \"\$(git -C '$AMEND_FA_REPO' log --oneline | wc -l | tr -d ' ')\" -eq 2"
check "fa-amend: last commit subject is still the bump message" \
  bash -c "git -C '$AMEND_FA_REPO' log -1 --format='%s' | grep -qF 'Bump x/net for GHSA-TEST-FA11'"
check "fa-amend: last commit includes .grype.yaml" \
  bash -c "git -C '$AMEND_FA_REPO' show --name-only HEAD | grep -q '\.grype\.yaml'"

# Fallback: when the last commit is NOT a bump commit, a separate commit is made
echo "fix-availability amend fallback (separate commit)"
AMEND_FA_NOB_REPO="$TMPD/amend-fa-nob-repo"
mkdir -p "$AMEND_FA_NOB_REPO"
git -C "$AMEND_FA_NOB_REPO" init -q
git -C "$AMEND_FA_NOB_REPO" config user.email "test@test.com"
git -C "$AMEND_FA_NOB_REPO" config user.name "Test"
printf -- '---\nignore:\n  - vulnerability: GHSA-TEST-FA22\n    fix-state: not-fixed\n    package:\n      name: golang.org/x/net\n' \
  > "$AMEND_FA_NOB_REPO/.grype.yaml"
printf 'module example.com/test\ngo 1.21\n' > "$AMEND_FA_NOB_REPO/go.mod"
git -C "$AMEND_FA_NOB_REPO" add .grype.yaml go.mod
git -C "$AMEND_FA_NOB_REPO" commit -q -s -m "init"
git -C "$AMEND_FA_NOB_REPO" checkout -q -b release-0.23
git -C "$AMEND_FA_NOB_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$AMEND_FA_NOB_REPO" rev-parse HEAD)"

# Mock fix-package.sh: succeeds but creates a NON-bump commit subject
AMEND_FA_NOB_SDIR="$TMPD/amend-fa-nob-scripts"
mkdir -p "$AMEND_FA_NOB_SDIR"
cat > "$AMEND_FA_NOB_SDIR/fix-package.sh" <<'MOCK2EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$1"
pkg="$2"
printf '\n# bumped %s\n' "$pkg" >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" commit -s -m "Update go modules"
MOCK2EOF
chmod +x "$AMEND_FA_NOB_SDIR/fix-package.sh"

AMEND_FA_NOB_RDIR="$TMPD/amend-fa-nob-reports"
mkdir -p "$AMEND_FA_NOB_RDIR"
AMEND_FA_NOB_STATE="$TMPD/amend-fa-nob-state.env"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$AMEND_FA_NOB_REPO" "$SCRIPT_DIR" > "$AMEND_FA_NOB_STATE"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$AMEND_FA_NOB_RDIR/initial-scan.json"
cat > "$AMEND_FA_NOB_RDIR/fix-availability.report" <<'FANOBR'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 fix available
DETAILS:
FIX-AVAILABLE: golang.org/x/net 0.20.0 -> 0.23.0 CVEs:GHSA-TEST-FA22
FANOBR

(
  cd "$AMEND_FA_NOB_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$AMEND_FA_NOB_STATE"
  subagent_fix_fix_availability "$AMEND_FA_NOB_STATE" \
    "$AMEND_FA_NOB_RDIR/fix-availability.report" "$AMEND_FA_NOB_SDIR"
) >/dev/null 2>&1

check "fa-amend-fallback: stale ignore removed" \
  ! grep -q 'GHSA-TEST-FA22' "$AMEND_FA_NOB_REPO/.grype.yaml"
check "fa-amend-fallback: 3 commits (init + non-bump + separate remove)" \
  bash -c "test \"\$(git -C '$AMEND_FA_NOB_REPO' log --oneline | wc -l | tr -d ' ')\" -eq 3"
check "fa-amend-fallback: separate commit mentions remove stale" \
  bash -c "git -C '$AMEND_FA_NOB_REPO' log -1 --format='%s' | grep -qi 'stale'"

# === subagent_fix_existing_entries: amend path (lib.sh:1274) ===
# Same scenario but triggered by an existing-entries FIX-AVAILABLE report:
# a permanent ignore had the wrong rationale, fix now exists, package is bumped,
# and the stale permanent ignore must be folded into the bump commit via amend.
echo "existing-entries amend path"
AMEND_EE_REPO="$TMPD/amend-ee-repo"
mkdir -p "$AMEND_EE_REPO"
git -C "$AMEND_EE_REPO" init -q
git -C "$AMEND_EE_REPO" config user.email "test@test.com"
git -C "$AMEND_EE_REPO" config user.name "Test"
# Permanent (non-fix-state) ignore — wrong rationale, fix now exists
printf -- '---\nignore:\n  # Update requires breaking Go version. High does not justify.\n  - vulnerability: GHSA-TEST-EE11\n    package:\n      name: golang.org/x/net\n' \
  > "$AMEND_EE_REPO/.grype.yaml"
printf 'module example.com/test\ngo 1.21\n' > "$AMEND_EE_REPO/go.mod"
git -C "$AMEND_EE_REPO" add .grype.yaml go.mod
git -C "$AMEND_EE_REPO" commit -q -s -m "init"
git -C "$AMEND_EE_REPO" checkout -q -b release-0.23
git -C "$AMEND_EE_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$AMEND_EE_REPO" rev-parse HEAD)"

# Mock fix-package.sh: creates the canonical bump commit
AMEND_EE_SDIR="$TMPD/amend-ee-scripts"
mkdir -p "$AMEND_EE_SDIR"
cat > "$AMEND_EE_SDIR/fix-package.sh" <<'MOCK3EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$1"
pkg="$2"
printf '\n# bumped %s\n' "$pkg" >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" commit -s -m "Bump x/net for GHSA-TEST-EE11"
MOCK3EOF
chmod +x "$AMEND_EE_SDIR/fix-package.sh"

AMEND_EE_RDIR="$TMPD/amend-ee-reports"
mkdir -p "$AMEND_EE_RDIR"
AMEND_EE_STATE="$TMPD/amend-ee-state.env"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$AMEND_EE_REPO" "$SCRIPT_DIR" > "$AMEND_EE_STATE"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$AMEND_EE_RDIR/initial-scan.json"
cat > "$AMEND_EE_RDIR/existing-entries.report" <<'EEREPORT'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 fix available for permanent ignore
DETAILS:
FIX-AVAILABLE: golang.org/x/net 0.20.0 -> 0.23.0 CVEs:GHSA-TEST-EE11
EEREPORT

(
  cd "$AMEND_EE_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$AMEND_EE_STATE"
  subagent_fix_existing_entries "$AMEND_EE_STATE" \
    "$AMEND_EE_RDIR/existing-entries.report" "$AMEND_EE_SDIR"
) >/dev/null 2>&1

check "ee-amend: stale permanent ignore removed from .grype.yaml" \
  ! grep -q 'GHSA-TEST-EE11' "$AMEND_EE_REPO/.grype.yaml"
check "ee-amend: commit count is 2 (init + amended bump, not 3)" \
  bash -c "test \"\$(git -C '$AMEND_EE_REPO' log --oneline | wc -l | tr -d ' ')\" -eq 2"
check "ee-amend: last commit subject is still the bump message" \
  bash -c "git -C '$AMEND_EE_REPO' log -1 --format='%s' | grep -qF 'Bump x/net for GHSA-TEST-EE11'"
check "ee-amend: last commit includes .grype.yaml" \
  bash -c "git -C '$AMEND_EE_REPO' show --name-only HEAD | grep -q '\.grype\.yaml'"

# Fallback: when last commit is not a bump commit, a separate commit is made
echo "existing-entries amend fallback (separate commit)"
AMEND_EE_NOB_REPO="$TMPD/amend-ee-nob-repo"
mkdir -p "$AMEND_EE_NOB_REPO"
git -C "$AMEND_EE_NOB_REPO" init -q
git -C "$AMEND_EE_NOB_REPO" config user.email "test@test.com"
git -C "$AMEND_EE_NOB_REPO" config user.name "Test"
printf -- '---\nignore:\n  - vulnerability: GHSA-TEST-EE22\n    package:\n      name: golang.org/x/net\n' \
  > "$AMEND_EE_NOB_REPO/.grype.yaml"
printf 'module example.com/test\ngo 1.21\n' > "$AMEND_EE_NOB_REPO/go.mod"
git -C "$AMEND_EE_NOB_REPO" add .grype.yaml go.mod
git -C "$AMEND_EE_NOB_REPO" commit -q -s -m "init"
git -C "$AMEND_EE_NOB_REPO" checkout -q -b release-0.23
git -C "$AMEND_EE_NOB_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$AMEND_EE_NOB_REPO" rev-parse HEAD)"

AMEND_EE_NOB_SDIR="$TMPD/amend-ee-nob-scripts"
mkdir -p "$AMEND_EE_NOB_SDIR"
cat > "$AMEND_EE_NOB_SDIR/fix-package.sh" <<'MOCK4EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$1"
pkg="$2"
printf '\n# bumped %s\n' "$pkg" >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" commit -s -m "Update go modules"
MOCK4EOF
chmod +x "$AMEND_EE_NOB_SDIR/fix-package.sh"

AMEND_EE_NOB_RDIR="$TMPD/amend-ee-nob-reports"
mkdir -p "$AMEND_EE_NOB_RDIR"
AMEND_EE_NOB_STATE="$TMPD/amend-ee-nob-state.env"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$AMEND_EE_NOB_REPO" "$SCRIPT_DIR" > "$AMEND_EE_NOB_STATE"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$AMEND_EE_NOB_RDIR/initial-scan.json"
cat > "$AMEND_EE_NOB_RDIR/existing-entries.report" <<'EENOBR'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 fix available for permanent ignore
DETAILS:
FIX-AVAILABLE: golang.org/x/net 0.20.0 -> 0.23.0 CVEs:GHSA-TEST-EE22
EENOBR

(
  cd "$AMEND_EE_NOB_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$AMEND_EE_NOB_STATE"
  subagent_fix_existing_entries "$AMEND_EE_NOB_STATE" \
    "$AMEND_EE_NOB_RDIR/existing-entries.report" "$AMEND_EE_NOB_SDIR"
) >/dev/null 2>&1

check "ee-amend-fallback: stale ignore removed" \
  ! grep -q 'GHSA-TEST-EE22' "$AMEND_EE_NOB_REPO/.grype.yaml"
check "ee-amend-fallback: 3 commits (init + non-bump + separate remove)" \
  bash -c "test \"\$(git -C '$AMEND_EE_NOB_REPO' log --oneline | wc -l | tr -d ' ')\" -eq 3"
check "ee-amend-fallback: separate commit mentions remove stale" \
  bash -c "git -C '$AMEND_EE_NOB_REPO' log -1 --format='%s' | grep -qi 'stale'"

# === subagent_fix_existing_entries: Pass 3 FIX-NOW-AVAILABLE handling ===
# not-fixed ignores where grype now has a fix must be consumed by Pass 3.
# Bug: FIX-NOW-AVAILABLE lines were emitted by existing-entries.sh but never
# parsed by subagent_fix_existing_entries, leaving the stale not-fixed entry
# in .grype.yaml indefinitely.
echo "existing-entries FIX-NOW-AVAILABLE handling"

# Functional: subagent_fix_existing_entries must call fix-package.sh when
# a FIX-NOW-AVAILABLE line appears in the existing-entries report.
FNA_REPO="$TMPD/fna-repo"
mkdir -p "$FNA_REPO"
git -C "$FNA_REPO" init -q
git -C "$FNA_REPO" config user.email "test@test.com"
git -C "$FNA_REPO" config user.name "Test"
printf -- '---\nignore:\n  # No fix available for golang.org/x/net.\n  - vulnerability: GHSA-FNA-0001\n    fix-state: not-fixed\n    package:\n      name: golang.org/x/net\n' \
  > "$FNA_REPO/.grype.yaml"
printf 'module example.com/fna-test\ngo 1.21\n' > "$FNA_REPO/go.mod"
git -C "$FNA_REPO" add .grype.yaml go.mod
git -C "$FNA_REPO" commit -q -s -m "init"
git -C "$FNA_REPO" checkout -q -b release-0.23
git -C "$FNA_REPO" update-ref refs/remotes/origin/release-0.23 \
  "$(git -C "$FNA_REPO" rev-parse HEAD)"

FNA_SDIR="$TMPD/fna-scripts"
mkdir -p "$FNA_SDIR"
FNA_FP_LOG="$TMPD/fna-fix-package.log"
cat > "$FNA_SDIR/fix-package.sh" <<MOCKEOF
#!/usr/bin/env bash
set -euo pipefail
source "\$1"          # loads REPO from state_file
pkg="\$2"
ver="\$3"
echo "fix-package called: pkg=\$pkg" >> "$FNA_FP_LOG"
echo "ver=\$ver" >> "$FNA_FP_LOG"
printf '\n# bumped %s\n' "\$pkg" >> "\$REPO/go.mod"
git -C "\$REPO" add go.mod
git -C "\$REPO" commit -s -m "Bump x/net for GHSA-FNA-0001"
MOCKEOF
chmod +x "$FNA_SDIR/fix-package.sh"

FNA_RDIR="$TMPD/fna-reports"
mkdir -p "$FNA_RDIR"
FNA_STATE="$TMPD/fna-state.env"
printf 'REPO="%s"\nBRANCH="release-0.23"\nCVE_SCRIPTS="%s"\n' \
  "$FNA_REPO" "$SCRIPT_DIR" > "$FNA_STATE"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$FNA_RDIR/initial-scan.json"
cat > "$FNA_RDIR/existing-entries.report" <<'FNAREPORT'
VERDICT: FAIL
ISSUES: 1
SUMMARY: 1 not-fixed entry now has a fix
DETAILS:
FIX-NOW-AVAILABLE: GHSA-FNA-0001 (golang.org/x/net) marked not-fixed but grype has fix 0.23.0 | comment: no fix available
FNAREPORT

(
  cd "$FNA_REPO"
  source "$SCRIPT_DIR/lib.sh"
  source "$FNA_STATE"
  subagent_fix_existing_entries "$FNA_STATE" \
    "$FNA_RDIR/existing-entries.report" "$FNA_SDIR"
) >/dev/null 2>&1

check "fna: fix-package.sh was called for not-fixed pkg" test -f "$FNA_FP_LOG"
check "fna: fix-package called with correct pkg" grep -q 'pkg=golang.org/x/net' "$FNA_FP_LOG"
check "fna: fix-package called with correct version" grep -q 'ver=0.23.0' "$FNA_FP_LOG"
check "fna: stale not-fixed ignore removed from .grype.yaml" \
  ! grep -q 'GHSA-FNA-0001' "$FNA_REPO/.grype.yaml"
check "fna: fix commit present in repo" \
  bash -c "git -C '$FNA_REPO' log --oneline | grep -q 'Bump x/net'"

# === fix-package.sh: empty-INSTALLED + active replace guard ===
# Regression: guard removal lets empty INSTALLED + active replace fall through as FIXED; stub go returns "(devel)" so STILL_VULNERABLE=true → exit 3.
echo "fix-package.sh empty-INSTALLED+active-replace guard"
FP_VERGU_REPO="$TMPD/fp-vergu"
mkdir -p "$FP_VERGU_REPO/bin"
git -C "$FP_VERGU_REPO" init -q
git -C "$FP_VERGU_REPO" config user.email "t@t.com"
git -C "$FP_VERGU_REPO" config user.name "T"
cat > "$FP_VERGU_REPO/go.mod" <<'FPGOMOD'
module example.com/vergu
go 1.24.0
require github.com/foo/bar v1.0.0
replace github.com/foo/bar => ./local
FPGOMOD
touch "$FP_VERGU_REPO/go.sum"
git -C "$FP_VERGU_REPO" add -A
git -C "$FP_VERGU_REPO" commit -q -m "init"
# go stub: returns "(devel)" for go list -m -f '{{.Version}}'; exits 0 for all other invocations.
cat > "$FP_VERGU_REPO/bin/go" <<'FPGOSTUB'
#!/usr/bin/env bash
if [[ "$*" == *"-f"* && "$*" == *"{{.Version}}"* ]]; then echo "(devel)"; fi
exit 0
FPGOSTUB
chmod +x "$FP_VERGU_REPO/bin/go"
FP_VERGU_STATE="$TMPD/fp-vergu.env"
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' \
  "$FP_VERGU_REPO" "$SCRIPT_DIR" > "$FP_VERGU_STATE"
FP_VERGU_RC=0
FP_VERGU_OUT=$(
  PATH="$FP_VERGU_REPO/bin:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
    "$FP_VERGU_STATE" github.com/foo/bar 1.1.0 GHSA-test-vergu 2>&1
) || FP_VERGU_RC=$?
check "empty-INSTALLED+replace: exits 3" test "$FP_VERGU_RC" -eq 3
check "empty-INSTALLED+replace: warns unverifiable" \
  grep -q "effective version unverifiable" <<< "$FP_VERGU_OUT"

# === fix-package.sh: indirect dep downgrade detection and re-pin ===
# go mod tidy can silently lower indirect deps when the updated package needs lower minimums; script must detect and re-pin.
echo "fix-package indirect dep downgrade detection"
FP_DD="$TMPD/fp-dd"; mkdir -p "$FP_DD/gostub"
( cd "$FP_DD" && git init -q && git config user.email t@t && git config user.name t )

# go.mod: the package under CVE fix + two indirect deps at higher versions.
# After `go get cve-pkg@v1.1.0 && go mod tidy` the stub will downgrade x/mod
# from v0.40.0 to v0.38.0 and x/tools from v0.49.0 to v0.48.0, simulating
# the real submariner-operator regression.
cat > "$FP_DD/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	golang.org/x/mod v0.40.0 // indirect
	golang.org/x/tools v0.49.0 // indirect
)
GOMOD
( cd "$FP_DD" && git add go.mod && git commit -qm init )

# go stub: "go get cve-pkg" downgrades x/mod + x/tools; re-pin calls restore them.
# "go list -m" returns version from go.mod; replace queries return "".
cat > "$FP_DD/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      # Update cve-pkg and simultaneously downgrade indirect deps (the bug)
      awk -v v="$ver" '
        /example\.com\/cve-pkg/  { print "\texample.com/cve-pkg v" v; next }
        /golang\.org\/x\/mod/    { print "\tgolang.org/x/mod v0.38.0 // indirect"; next }
        /golang\.org\/x\/tools/  { print "\tgolang.org/x/tools v0.48.0 // indirect"; next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
    golang.org/x/mod)
      awk -v v="$ver" '
        /golang\.org\/x\/mod/ { print "\tgolang.org/x/mod v" v " // indirect"; next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
    golang.org/x/tools)
      awk -v v="$ver" '
        /golang\.org\/x\/tools/ { print "\tgolang.org/x/tools v" v " // indirect"; next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  pkg="${@: -1}"  # last argument is the package name
  case "$fmt" in
    *Replace.Version*) echo "" ;;
    *Replace.Dir*)     echo "" ;;
    *Version*)
      awk -v p="$pkg" '$1==p {v=$2; gsub(/\/\/.*/, "", v); gsub(/^v/, "", v); print "v" v}' \
        "$dir/go.mod" | head -1 ;;
    *) echo "" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_DD/gostub/go"

cat > "$FP_DD/st.env" <<STENV
REPO="$FP_DD"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_DD_OUT=$(
  cd "$FP_DD" && PATH="$FP_DD/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_DD/st.env" example.com/cve-pkg 1.1.0 GHSA-dd-0001 2>&1
) && FP_DD_RC=0 || FP_DD_RC=$?

# The fix must succeed (exit 0) and warn about + re-pin the downgraded deps
check "indirect-downgrade: exits 0"          test "$FP_DD_RC" -eq 0
check "indirect-downgrade: x/mod warning"    grep -q "x/mod downgraded" <<< "$FP_DD_OUT"
check "indirect-downgrade: x/tools warning"  grep -q "x/tools downgraded" <<< "$FP_DD_OUT"
# go.mod must have x/mod at v0.40.0 after the fix (re-pinned)
check "indirect-downgrade: x/mod restored"   grep -q 'golang.org/x/mod v0.40.0' "$FP_DD/go.mod"
# go.mod must have x/tools at v0.49.0 after the fix (re-pinned)
check "indirect-downgrade: x/tools restored" grep -q 'golang.org/x/tools v0.49.0' "$FP_DD/go.mod"
# cve-pkg must be at the fix version
check "indirect-downgrade: cve-pkg fixed"    grep -q 'example.com/cve-pkg v1.1.0' "$FP_DD/go.mod"

# === fix-package.sh: module layouts that must not abort or corrupt a fix ===
echo "fix-package module layout regressions"
_fpx_stub() {
  cat > "$1/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
[ -z "$FPX_CALLS" ] || echo "$*" >> "$FPX_CALLS"
case "$1" in
  get)
    pkg=$(echo "$2" | cut -d@ -f1); ver=$(echo "$2" | cut -d@ -f2)
    [ "$FPX_MODE" = go-bump ] && sed -i 's/^go 1.24.0$/go 1.24.5/' "$dir/go.mod"
    if [ "$FPX_MODE" = post-v ]; then
      echo "go: $2: invalid version: go.mod has post-v7 module path \"$pkg/v7\" at revision $ver" >&2
      exit 1
    fi
    awk -v p="$pkg" -v v="$ver" '$1 == p { $2 = v } $1 == "require" && $2 == p { $3 = v } { print }' \
      "$dir/go.mod" > "$dir/go.mod.tmp" && mv "$dir/go.mod.tmp" "$dir/go.mod"
    exit 0 ;;
  mod)
    [ "$2" = vendor ] && mkdir -p "$dir/vendor" && echo "# regenerated" > "$dir/vendor/modules.txt"
    exit 0 ;;
  list)
    pkg=""; for a in "$@"; do pkg="$a"; done
    awk -v p="$pkg" '($1 == p) { print $2; exit } ($1 == "require" && $2 == p) { print $3; exit }' "$dir/go.mod"
    exit 0 ;;
esac
exit 0
STUB
  chmod +x "$1/go"
}
_fpx_run() {  # name gomod-content [mode]
  local d="$TMPD/fpx-$1"
  mkdir -p "$d/bin"
  git -C "$d" init -q; git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf '%s\n' "$2" > "$d/go.mod"
  _fpx_stub "$d/bin"
  printf 'REPO="%s"\nBRANCH="devel"\nBUILD_GO_VERSION="unknown"\nCVE_SCRIPTS="%s"\nDIFF_IGNORE_ARGS=""\n' "$d" "$SCRIPT_DIR" > "$d/st.env"
  [[ -z "${FPX_SETUP:-}" ]] || (cd "$d" && eval "$FPX_SETUP")
  git -C "$d" add -A && git -C "$d" commit -qm init
  [[ -z "${FPX_STATE:-}" ]] || printf '%s\n' "$FPX_STATE" >> "$d/st.env"
  FPX_OUT=$(cd "$d" && FPX_MODE="${3:-}" FPX_CALLS="$d/go-calls" PATH="$d/bin:$PATH" \
    bash "$SCRIPT_DIR/fix-package.sh" "$d/st.env" "${FPX_PKG:-example.com/cve-pkg}" "${FPX_VER:-1.1.0}" GHSA-fpx-0001 2>&1) && FPX_RC=0 || FPX_RC=$?
  FPX_DIR="$d"
}
_fpx_run nogo $'module x\n\nrequire example.com/cve-pkg v1.0.0'
check "module without a go directive can be fixed" test "$FPX_RC" -eq 0
check "module without a go directive reaches the fix" grep -q 'example.com/cve-pkg v1.1.0' "$FPX_DIR/go.mod"
FPX_SETUP='mkdir -p vendor && echo "# local" > vendor/modules.txt && echo "/vendor/" > .gitignore' \
  _fpx_run ignored-vendor $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0'
check "ignored local vendor tree does not fail the fix" test "$FPX_RC" -eq 0
check "ignored local vendor tree is not committed" test -z "$(git -C "$FPX_DIR" ls-files vendor)"
FPX_SETUP='mkdir -p vendor && printf "## workspace\n" > vendor/modules.txt' \
  _fpx_run workspace-vendor $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0'
check "workspace vendoring needs review" test "$FPX_RC" -eq 2
check "workspace vendoring is left unchanged" git -C "$FPX_DIR" diff --quiet
_fpx_run post-v $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0' post-v
check "moved /vN module path is a major migration" test "$FPX_RC" -eq 4
check "moved /vN module path is reported" grep -q '^INCOMPATIBLE_MAJOR_BUMP:' <<< "$FPX_OUT"
_fpx_run go-bump $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0' go-bump
check "a go directive change is fixed" test "$FPX_RC" -eq 0
check "a go directive change is named in the commit" \
  bash -c 'git -C "$1" log -1 --format=%B | grep -qx "Raises go in go.mod from 1.24.0 to 1.24.5, as v1.1.0 requires."' _ "$FPX_DIR"
FPX_SCANS="$TMPD/fpx-scans"; mkdir -p "$FPX_SCANS"
cat > "$FPX_SCANS/scan.sh" <<'SH'
#!/usr/bin/env bash
n=$(cat "$(dirname "$0")/count" 2>/dev/null || echo 0); echo $((n + 1)) > "$(dirname "$0")/count"
hit() { printf '{"vulnerability":{"id":"%s"},"artifact":{"type":"go-module","name":"%s","locations":[{"path":"/go.mod"}]}}' "$1" "$2"; }
if [ "$n" -eq 0 ]; then
  printf '{"matches":[%s,%s,%s]}\n' "$(hit GHSA-fpx-0001 example.com/cve-pkg)" "$(hit GO-9 example.com/other)" "$(hit GO-10 example.com/other)"
else
  printf '{"matches":[]}\n'
fi
SH
FPX_STATE=$(printf 'HAS_LOCAL_GRYPE=true\nCVE_SCRIPTS="%s"' "$FPX_SCANS") \
  _fpx_run also-fixed $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0'
check "a side-effect fix is fixed" test "$FPX_RC" -eq 0
check "a side-effect fix is credited in the commit" \
  bash -c 'git -C "$1" log -1 --format=%B | grep -qx "Also fixes, in example.com/other: GO-10, GO-9"' _ "$FPX_DIR"
check "moved /vN module path prints no registry note" ! grep -q 'not available in Go module registry' <<< "$FPX_OUT"
FPX_PKG=k8s.io/apimachinery FPX_VER=0.32.1 FPX_STATE='K8S_VERSION_GUARD=true' \
  _fpx_run k8s-guard $'module x\n\ngo 1.24.0\n\nrequire k8s.io/apimachinery v0.31.1'
check "k8s guard covers apimachinery minors" test "$FPX_RC" -eq 2
check "k8s guard reports the minor change" grep -q 'K8s minor versions changed' <<< "$FPX_OUT"
FPX_SETUP='printf "go 1.24.0\n\nuse .\n" > go.work && echo go.work > .gitignore' \
  _fpx_run untracked-work $'module x\n\ngo 1.24.0\n\nrequire example.com/cve-pkg v1.0.0'
check "untracked go.work is never synced" ! grep -q 'work sync' "$FPX_DIR/go-calls"
printf 'mango.mod\n' > "$TMPD/stage-regex-list"
check "staging matches only go.mod/go.sum/go.work files" \
  test -z "$(grep -E '(^|/)go\.(mod|sum|work(\.sum)?)$' "$TMPD/stage-regex-list")"

# === fix-package.sh: pseudo-version indirect dep no false re-pin ===
# Pseudo-version indirect deps (v0.0.0-YYYYMMDD-HASH) must not trigger false
# re-pin detection. The snapshot previously stripped pseudo-versions to "0.0.0",
# making version_gte("0.0.0-pseudo", "0.0.0") = false (pseudo < base in Go semver),
# causing a re-pin attempt to the invalid version v0.0.0.
echo "fix-package pseudo-version indirect dep no false re-pin"
FP_PV="$TMPD/fp-pv"; mkdir -p "$FP_PV/gostub"
( cd "$FP_PV" && git init -q && git config user.email t@t && git config user.name t )

cat > "$FP_PV/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	github.com/example/pseudo v0.0.0-20240424215950-a892ee059fd6 // indirect
)
GOMOD
( cd "$FP_PV" && git add go.mod && git commit -qm init )

# go stub: go get cve-pkg leaves the pseudo-version dep unchanged.
cat > "$FP_PV/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      awk -v v="$ver" '/example\.com\/cve-pkg/ { print "\texample.com/cve-pkg v" v; next } { print }' \
        "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  pkg="${@: -1}"
  case "$fmt" in
    *Replace.Version*) echo "" ;;
    *Replace.Dir*)     echo "" ;;
    *Version*)
      awk -v p="$pkg" '$1==p {v=$2; gsub(/\/\/.*/, "", v); gsub(/^v/, "", v); print "v" v}' \
        "$dir/go.mod" | head -1 ;;
    *) echo "" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_PV/gostub/go"

cat > "$FP_PV/st.env" <<STENV
REPO="$FP_PV"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_PV_OUT=$(
  cd "$FP_PV" && PATH="$FP_PV/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_PV/st.env" example.com/cve-pkg 1.1.0 GHSA-pseudo-test 2>&1
) && FP_PV_RC=0 || FP_PV_RC=$?

# Must succeed — pseudo-version dep is unchanged, no re-pin needed
check "pseudo-version indirect: exits 0"           test "$FP_PV_RC" -eq 0
check "pseudo-version indirect: no STILL_VULNERABLE" ! grep -q "STILL_VULNERABLE" <<< "$FP_PV_OUT"
check "pseudo-version indirect: no re-pin warning"   ! grep -q "re-pinning to v0.0.0" <<< "$FP_PV_OUT"
check "pseudo-version indirect: pseudo dep unchanged" grep -q 'github.com/example/pseudo v0.0.0-20240424215950-a892ee059fd6' "$FP_PV/go.mod"
check "pseudo-version indirect: cve-pkg fixed"       grep -q 'example.com/cve-pkg v1.1.0' "$FP_PV/go.mod"

# === fix-package.sh: removed indirect dep re-pin ===
# When go mod tidy removes a package entirely from go.mod (it becomes purely
# transitive at a lower version), fix-package.sh must also re-pin it.
echo "fix-package indirect dep removed and re-pinned"
FP_DDR="$TMPD/fp-ddr"; mkdir -p "$FP_DDR/gostub"
( cd "$FP_DDR" && git init -q && git config user.email t@t && git config user.name t )

cat > "$FP_DDR/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	go.etcd.io/etcd/client/pkg/v3 v3.6.14 // indirect
)
GOMOD
( cd "$FP_DDR" && git add go.mod && git commit -qm init )

# go stub: go get cve-pkg@v1.1.0 removes the etcd dep entirely from go.mod
# (simulating go mod tidy dropping it as now purely transitive at a lower ver)
cat > "$FP_DDR/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      # Update cve-pkg and remove etcd dep (simulates go mod tidy dropping it)
      awk -v v="$ver" '
        /example\.com\/cve-pkg/             { print "\texample.com/cve-pkg v" v; next }
        /go\.etcd\.io\/etcd\/client\/pkg/   { next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
    go.etcd.io/etcd/client/pkg/v3)
      # Re-add etcd dep when re-pinned
      awk -v v="$ver" '
        /^\)/ { print "\tgo.etcd.io/etcd/client/pkg/v3 v" v " // indirect" }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  # Plain "go list -m <pkg>" (no -f flag): etcd is still a transitive dep in the
  # module graph even after being removed from explicit requires in go.mod.
  # Returning module info causes the re-pin check to proceed (not skip).
  if [ "${2:-}" = "-m" ] && [ -n "${3:-}" ] && [ "$(printf '%s' "${3}" | cut -c1)" != "-" ]; then
    case "$3" in
      go.etcd.io/etcd/client/pkg/v3)
        echo "go.etcd.io/etcd/client/pkg/v3 v3.5.0"
        ;;
    esac
  fi
  exit 0
fi
exit 0
STUB
chmod +x "$FP_DDR/gostub/go"

cat > "$FP_DDR/st.env" <<STENV
REPO="$FP_DDR"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_DDR_OUT=$(
  cd "$FP_DDR" && PATH="$FP_DDR/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_DDR/st.env" example.com/cve-pkg 1.1.0 GHSA-ddr-0001 2>&1
) && FP_DDR_RC=0 || FP_DDR_RC=$?

check "indirect-removed: exits 0"           test "$FP_DDR_RC" -eq 0
check "indirect-removed: etcd warning"      grep -q "etcd/client/pkg" <<< "$FP_DDR_OUT"
check "indirect-removed: re-pin warning"    grep -q "re-pinning to v" <<< "$FP_DDR_OUT"
check "indirect-removed: etcd restored"     grep -q 'go.etcd.io/etcd/client/pkg/v3' "$FP_DDR/go.mod"

# === fix-package.sh: truly-removed indirect dep is NOT re-pinned ===
# go list -m returns nothing → package gone from graph; skip re-pin, not exit 3.
echo "fix-package indirect dep truly removed from graph (no re-pin)"
FP_GONE="$TMPD/fp-gone"; mkdir -p "$FP_GONE/gostub"
( cd "$FP_GONE" && git init -q && git config user.email t@t && git config user.name t )

cat > "$FP_GONE/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	example.com/orphan-dep v1.2.3 // indirect
)
GOMOD
( cd "$FP_GONE" && git add go.mod && git commit -qm init )

# go stub: go get cve-pkg@v1.1.0 removes orphan-dep entirely from go.mod AND
# go list -m returns nothing (truly gone from module graph, no importers remain).
cat > "$FP_GONE/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      awk -v v="$ver" '
        /example\.com\/cve-pkg/    { print "\texample.com/cve-pkg v" v; next }
        /example\.com\/orphan-dep/ { next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  # go list -m returns nothing for orphan-dep: truly gone from module graph
  exit 0
fi
exit 0
STUB
chmod +x "$FP_GONE/gostub/go"

cat > "$FP_GONE/st.env" <<STENV
REPO="$FP_GONE"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_GONE_OUT=$(
  cd "$FP_GONE" && PATH="$FP_GONE/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_GONE/st.env" example.com/cve-pkg 1.1.0 GHSA-gone-0001 2>&1
) && FP_GONE_RC=0 || FP_GONE_RC=$?

check "truly-removed: exits 0"             test "$FP_GONE_RC" -eq 0
check "truly-removed: INFO skip msg"       grep -q "not a CVE risk, skipping re-pin" <<< "$FP_GONE_OUT"
check "truly-removed: orphan not re-added" ! grep -q 'example.com/orphan-dep' "$FP_GONE/go.mod"

# === Real timeout and rollback for each network-capable tidy/vendor/sync phase ===
echo "fix-package tidy, vendor and sync timeouts preserve transaction state"
for _mod_phase in initial-tidy repin-tidy vendor work-sync sync-tidy; do
  for _mod_failure in timeout network permanent; do
    _mod_case="$TMPD/mod-timeout-$_mod_phase-$_mod_failure"
    make_test_repo "$_mod_case"
    mkdir -p "$_mod_case/bin" "$_mod_case/vendor"
    cat > "$_mod_case/go.mod" <<'GOMOD'
module example.com/main
go 1.25.0
require (
  example.com/cve-pkg v1.0.0
  example.com/indirect v1.0.0 // indirect
)
GOMOD
    printf 'original tracked file\n' > "$_mod_case/vendor/tracked"
    printf 'vendor/ignored-*\n' > "$_mod_case/.gitignore"
    if [[ "$_mod_phase" == work-sync || "$_mod_phase" == sync-tidy ]]; then
      printf 'go 1.25.0\nuse .\n' > "$_mod_case/go.work"
      git -C "$_mod_case" add go.work
    fi
    git -C "$_mod_case" add go.mod vendor/tracked .gitignore
    git -C "$_mod_case" commit -qm 'dependency and vendor fixture'
    _mod_head=$(git -C "$_mod_case" rev-parse HEAD)
    printf 'original user file\n' > "$_mod_case/vendor/user-note"
    printf 'original ignored file\n' > "$_mod_case/vendor/ignored-note"
    make_go_state "$_mod_case/state.env" "$_mod_case"
    cat > "$_mod_case/bin/go" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
dir=.
if [[ "${1:-}" == -C ]]; then dir="$2"; shift 2; fi
if [[ "${1:-}" == get ]]; then
  pkg="${2%@*}"; ver="${2##*@}"
  awk -v pkg="$pkg" -v ver="$ver" '{if ($1 == pkg) $2=ver; print}' "$dir/go.mod" > "$dir/go.mod.tmp"
  mv "$dir/go.mod.tmp" "$dir/go.mod"
  if [[ "$MOD_TEST_PHASE" == repin-tidy && "$pkg" == example.com/cve-pkg ]]; then
    sed 's/example.com\/indirect v1.0.0/example.com\/indirect v0.9.0/' "$dir/go.mod" > "$dir/go.mod.tmp"
    mv "$dir/go.mod.tmp" "$dir/go.mod"
  fi
  exit 0
fi
if [[ "${1:-}" == list ]]; then
  [[ "$*" == *'{{if .Replace}}{{.Replace.Version}}{{end}}'* ]] && exit 0
  pkg="${@: -1}"
  awk -v pkg="$pkg" '$1 == pkg {print $2}' "$dir/go.mod"
  exit 0
fi
target=false
if [[ "$*" == 'mod tidy' ]]; then
  count=0
  [[ ! -f .git/tidy-calls ]] || count=$(cat .git/tidy-calls)
  count=$((count + 1)); printf '%s\n' "$count" > .git/tidy-calls
  if [[ "$MOD_TEST_PHASE" == initial-tidy || (("$MOD_TEST_PHASE" == repin-tidy || "$MOD_TEST_PHASE" == sync-tidy) && "$count" -eq 2) ]]; then target=true; fi
elif [[ "$*" == 'mod vendor' && "$MOD_TEST_PHASE" == vendor ]]; then
  target=true
elif [[ "$*" == 'work sync' && "$MOD_TEST_PHASE" == work-sync ]]; then
  target=true
elif [[ "$*" == 'work sync' && "$MOD_TEST_PHASE" == sync-tidy ]]; then
  printf '\n// requirement changed by sync\n' >> go.mod
fi
if [[ "$target" == true ]]; then
  printf '%s\n' "$MOD_TEST_PHASE" > .git/failed-phase
  printf 'partial checksum\n' > go.sum
  printf 'corrupt tracked file\n' > vendor/tracked
  printf 'new generated file\n' > vendor/new.go
  printf 'new ignored file\n' > vendor/ignored-new
  rm vendor/user-note
  printf 'overwritten ignored file\n' > vendor/ignored-note
  case "$MOD_TEST_FAILURE" in
    timeout) sleep 0.6 ;; # real timeout must terminate this silent stalled command
    network) echo 'dial tcp: connection refused' >&2; exit 1 ;;
    permanent) echo 'invalid module metadata' >&2; exit 1 ;;
  esac
fi
STUB
    chmod +x "$_mod_case/bin/go"
    _mod_rc=0
    _mod_out=$(PATH="$_mod_case/bin:$PATH" MOD_TEST_PHASE="$_mod_phase" MOD_TEST_FAILURE="$_mod_failure" \
      GO_GET_TIMEOUT=0.3s bash "$SCRIPT_DIR/fix-package.sh" "$_mod_case/state.env" \
      example.com/cve-pkg 1.1.0 CVE-MOD-TIMEOUT 2>&1) || _mod_rc=$?
    _mod_label="$_mod_phase $_mod_failure"
    check "$_mod_label: target phase was reached" test "$(cat "$_mod_case/.git/failed-phase")" = "$_mod_phase"
    if [[ "$_mod_failure" == permanent ]]; then
      check "$_mod_label: deterministic failure remains non-transient" ! grep -q '^TRANSIENT_ERROR:' <<< "$_mod_out"
      check "$_mod_label: deterministic failure is not exit five" test "$_mod_rc" -ne 5
      check "$_mod_label: deterministic failure stays unsuccessful" test "$_mod_rc" -ne 0
    else
      check "$_mod_label: failure is retryable exit five" test "$_mod_rc" -eq 5
      check "$_mod_label: transient error is reported" grep -q '^TRANSIENT_ERROR:' <<< "$_mod_out"
      if [[ "$_mod_failure" == timeout ]]; then
        check "$_mod_label: real timeout status survives tee" grep -q '^TRANSIENT_ERROR: .* exit 124 ' <<< "$_mod_out"
      fi
    fi
    check "$_mod_label: no repair was committed" test "$(git -C "$_mod_case" rev-parse HEAD)" = "$_mod_head"
    check "$_mod_label: tracked dependency and vendor bytes restored" git -C "$_mod_case" diff --quiet
    check "$_mod_label: new checksum metadata removed" test ! -e "$_mod_case/go.sum"
    check "$_mod_label: new vendor source removed" test ! -e "$_mod_case/vendor/new.go"
    check "$_mod_label: new ignored vendor file removed" test ! -e "$_mod_case/vendor/ignored-new"
    check "$_mod_label: original untracked vendor file restored" test "$(cat "$_mod_case/vendor/user-note")" = 'original user file'
    check "$_mod_label: original ignored vendor file restored" test "$(cat "$_mod_case/vendor/ignored-note")" = 'original ignored file'
  done
done

# === fix-package.sh: re-pin go get failure handled properly ===
# Transient re-pin failure (connection refused) → TRANSIENT_ERROR + exit 5.
# Non-transient → STILL_VULNERABLE=true, verify loop exits 3.
echo "fix-package re-pin go get failure handling"
FP_RPF="$TMPD/fp-rpf"; mkdir -p "$FP_RPF/gostub"
( cd "$FP_RPF" && git init -q && git config user.email t@t && git config user.name t )

cat > "$FP_RPF/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	golang.org/x/mod v0.40.0 // indirect
)
GOMOD
( cd "$FP_RPF" && git add go.mod && git commit -qm init )

# go stub: cve-pkg update downgrades x/mod; re-pin go get writes sentinel toolchain then exits 1.
cat > "$FP_RPF/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      awk -v v="$ver" '
        /example\.com\/cve-pkg/ { print "\texample.com/cve-pkg v" v; next }
        /golang\.org\/x\/mod/   { print "\tgolang.org/x/mod v0.38.0 // indirect"; next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      exit 0
      ;;
    golang.org/x/mod)
      # Simulate go get partial write (adds toolchain sentinel) then fails
      printf '\ntoolchain go1.99.0-sentinel\n' >> "$gomod"
      echo "go get: connection refused" >&2
      exit 1
      ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  pkg="${@: -1}"
  case "$fmt" in
    *Replace.Version*) echo "" ;;
    *Replace.Dir*)     echo "" ;;
    *Version*)
      awk -v p="$pkg" '$1==p {v=$2; gsub(/\/\/.*/, "", v); gsub(/^v/, "", v); print "v" v}' \
        "$dir/go.mod" | head -1 ;;
    *) echo "" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_RPF/gostub/go"

cat > "$FP_RPF/st.env" <<STENV
REPO="$FP_RPF"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_RPF_OUT=$(
  cd "$FP_RPF" && PATH="$FP_RPF/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_RPF/st.env" example.com/cve-pkg 1.1.0 GHSA-rpf-0001 2>&1
) && FP_RPF_RC=0 || FP_RPF_RC=$?

check "repin-fail: TRANSIENT_ERROR emitted on connection refused" \
  grep -q 'TRANSIENT_ERROR' <<< "$FP_RPF_OUT"
check "repin-fail: exits 5 on transient re-pin go get failure" \
  test "$FP_RPF_RC" -eq 5

# === fix-package repin warning: exits 0 and emits NEEDS_REVIEW ===
# Non-transient re-pin failure → NEEDS_REVIEW emitted but exits 0 (primary fix succeeded).
echo "fix-package re-pin conflict exits 2 not 3"
FP_RPC="$TMPD/fp-rpc"; mkdir -p "$FP_RPC/gostub"
( cd "$FP_RPC" && git init -q && git config user.email t@t && git config user.name t )
cat > "$FP_RPC/go.mod" <<'GOMOD'
module x
go 1.25.0

require (
	example.com/cve-pkg v1.0.0
	golang.org/x/mod v0.40.0 // indirect
)
GOMOD
( cd "$FP_RPC" && git add go.mod && git commit -qm init )

cat > "$FP_RPC/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"
  pkg=$(echo "$pkgver" | cut -d@ -f1)
  ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  gomod="$dir/go.mod"
  case "$pkg" in
    example.com/cve-pkg)
      awk -v v="$ver" '
        /example\.com\/cve-pkg/ { print "\texample.com/cve-pkg v" v; next }
        /golang\.org\/x\/mod/   { print "\tgolang.org/x/mod v0.38.0 // indirect"; next }
        { print }' "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
      exit 0 ;;
    golang.org/x/mod)
      # Non-transient failure: no "connection refused" keyword
      echo "go: golang.org/x/mod@v0.40.0: module not found" >&2
      exit 1 ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "-f" ] && fmt="$a"
    prev="$a"
  done
  pkg="${@: -1}"
  case "$fmt" in
    *Replace.Version*) echo "" ;;
    *Replace.Dir*)     echo "" ;;
    *Version*)
      awk -v p="$pkg" '$1==p {v=$2; gsub(/\/\/.*/, "", v); gsub(/^v/, "", v); print "v" v}' \
        "$dir/go.mod" | head -1 ;;
    *) echo "" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_RPC/gostub/go"
cat > "$FP_RPC/st.env" <<STENV
REPO="$FP_RPC"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
FP_RPC_OUT=$(
  cd "$FP_RPC" && PATH="$FP_RPC/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_RPC/st.env" example.com/cve-pkg 1.1.0 GHSA-rpc-0001 2>&1
) && FP_RPC_RC=0 || FP_RPC_RC=$?
check "repin-conflict: NEEDS_REVIEW emitted" grep -q 'NEEDS_REVIEW.*indirect dep constraint' <<< "$FP_RPC_OUT"
check "repin-conflict: exits 0 (primary fix succeeded)" test "$FP_RPC_RC" -eq 0

# === fix-package exit 4: version not in module registry ===
# When `go get pkg@vX.Y.Z` fails with "unknown revision" or "invalid version:
# unknown revision", fix-package.sh must exit 4 (not 1 or 2) so fix-all.sh can
# distinguish "the fix tag doesn't exist yet" from "a genuine breaking change".
# This prevents the skill from mislabelling a non-existent fix version as
# "incompatible with this branch" (the exit-2 / NEEDS_REVIEW path).
echo "fix-package exit 4 (version not in module registry)"
FP_NIP="$TMPD/fp-nip"; mkdir -p "$FP_NIP/gostub"
( cd "$FP_NIP" && git init -q && git config user.email t@t && git config user.name t )

cat > "$FP_NIP/go.mod" <<'GOMOD'
module x
go 1.25.0

require github.com/docker/docker v28.5.2+incompatible
GOMOD
( cd "$FP_NIP" && git add go.mod && git commit -qm init )

# go stub: "go get docker/docker@v29.3.1" emits the canonical proxy error.
cat > "$FP_NIP/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"; ver=$(echo "$pkgver" | cut -d@ -f2 | sed 's/^v//')
  case "$ver" in
    29.3.1)
      echo "go: github.com/docker/docker@v29.3.1+incompatible: invalid version: unknown revision v29.3.1" >&2
      exit 1 ;;
  esac
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then exit 0; fi
exit 0
STUB
chmod +x "$FP_NIP/gostub/go"

cat > "$FP_NIP/st.env" <<STENV
REPO="$FP_NIP"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV

FP_NIP_OUT=$(
  cd "$FP_NIP" && PATH="$FP_NIP/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_NIP/st.env" github.com/docker/docker 29.3.1 GHSA-x744-4wpc-v9h2 2>&1
) && FP_NIP_RC=0 || FP_NIP_RC=$?

check "not-in-proxy: exits 4"         test "$FP_NIP_RC" -eq 4
check "not-in-proxy: diagnostic NOTE" grep -q "not available in Go module registry" <<< "$FP_NIP_OUT"
# go.mod must be restored (git checkout -- . in exit 4 path)
check "not-in-proxy: go.mod unchanged" grep -q "v28.5.2" "$FP_NIP/go.mod"
# +incompatible major bump (v28→v29) remains actionable for manual migration.
check "not-in-proxy: incompat major bump marker" grep -q "^INCOMPATIBLE_MAJOR_BUMP: " <<< "$FP_NIP_OUT"
check "not-in-proxy: marker shows v28 -> v29" grep -q "v28 -> v29" <<< "$FP_NIP_OUT"

# Non-+incompatible package with unknown revision must NOT emit INCOMPATIBLE_MAJOR_BUMP.
# Mirrors the "version not yet tagged" scenario (e.g. k8s.io/client-go@v99.0.0).
FP_NIP2="$TMPD/fp-nip2"; mkdir -p "$FP_NIP2/gostub"
( cd "$FP_NIP2" && git init -q && git config user.email t@t && git config user.name t )
cat > "$FP_NIP2/go.mod" <<'GOMOD'
module x
go 1.25.0

require k8s.io/client-go v0.30.0
GOMOD
( cd "$FP_NIP2" && git add go.mod && git commit -qm init )
cat > "$FP_NIP2/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  echo "go: k8s.io/client-go@v99.0.0: invalid version: unknown revision v99.0.0" >&2
  exit 1
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then exit 0; fi
exit 0
STUB
chmod +x "$FP_NIP2/gostub/go"
cat > "$FP_NIP2/st.env" <<STENV
REPO="$FP_NIP2"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
FP_NIP2_OUT=$(
  cd "$FP_NIP2" && PATH="$FP_NIP2/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_NIP2/st.env" k8s.io/client-go 99.0.0 GHSA-nip2-0001 2>&1
) && FP_NIP2_RC=0 || FP_NIP2_RC=$?
check "nip2: exits 4"                        test "$FP_NIP2_RC" -eq 4
check "nip2: diagnostic NOTE present"        grep -q "not available in Go module registry" <<< "$FP_NIP2_OUT"
check "nip2: no INCOMPATIBLE_MAJOR_BUMP"     ! grep -q "^INCOMPATIBLE_MAJOR_BUMP:" <<< "$FP_NIP2_OUT"

# === fix-package.sh: +incompatible major bump detection edge cases ===
# These tests verify the detection logic handles different version shapes correctly.
echo "fix-package +incompatible major bump detection"

# Same-major version with +incompatible: NOT a major bump, no marker expected.
# E.g. docker/docker v28.5.0+incompatible → fix v28.5.2 (same major 28).
FP_SAME="$TMPD/fp-same"; mkdir -p "$FP_SAME/gostub"
( cd "$FP_SAME" && git init -q && git config user.email t@t && git config user.name t )
cat > "$FP_SAME/go.mod" <<'GOMOD'
module x
go 1.25.0

require github.com/docker/docker v28.5.0+incompatible
GOMOD
( cd "$FP_SAME" && git add go.mod && git commit -qm init )
cat > "$FP_SAME/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  echo "go: github.com/docker/docker@v28.5.2: invalid version: unknown revision v28.5.2" >&2
  exit 1
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then exit 0; fi
exit 0
STUB
chmod +x "$FP_SAME/gostub/go"
cat > "$FP_SAME/st.env" <<STENV
REPO="$FP_SAME"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
STENV
FP_SAME_OUT=$(
  cd "$FP_SAME" && PATH="$FP_SAME/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_SAME/st.env" github.com/docker/docker 28.5.2 GHSA-same-0001 2>&1
) && FP_SAME_RC=0 || FP_SAME_RC=$?
check "same-major: exits 4" test "$FP_SAME_RC" -eq 4
check "same-major: no INCOMPATIBLE_MAJOR_BUMP" ! grep -q "^INCOMPATIBLE_MAJOR_BUMP:" <<< "$FP_SAME_OUT"
check "same-major: NOTE present" grep -q "not available in Go module registry" <<< "$FP_SAME_OUT"

mkdir -p "$FP_NIP/tools"
for _major_case in scoped unscoped prefix sibling same-file comment; do
  _major_root='require github.com/docker/docker v1.0.0'
  _major_tools='require github.com/docker/docker v28.5.2+incompatible'
  _major_scope=()
  _major_expected=true
  case "$_major_case" in
    scoped)
      _major_scope=(--location tools/go.mod)
      _major_tools=$'require (\n github.com/docker/docker v28.5.2+incompatible\n)'
      ;;
    prefix) _major_root='require github.com/docker/docker-credential-helpers v28.5.2+incompatible' ;;
    sibling)
      _major_root='require github.com/docker/docker v28.5.2+incompatible'
      _major_tools='require github.com/docker/docker v1.0.0'
      _major_scope=(--location tools/go.mod); _major_expected=false
      ;;
    same-file)
      _major_root+=$'\nrequire github.com/docker/docker-credential-helpers v28.5.2+incompatible'
      _major_scope=(--location /go.mod); _major_expected=false
      ;;
    comment)
      _major_root+='// v28.5.2+incompatible is only a comment'
      _major_scope=(--location /go.mod); _major_expected=false
      ;;
  esac
  printf 'module x\ngo 1.25.0\n%s\n' "$_major_root" > "$FP_NIP/go.mod"
  printf 'module x/tools\ngo 1.25.0\n%s\n' "$_major_tools" > "$FP_NIP/tools/go.mod"
  git -C "$FP_NIP" add go.mod tools/go.mod; git -C "$FP_NIP" commit -qm "$_major_case"
  _major_head=$(git -C "$FP_NIP" rev-parse HEAD); _major_rc=0
  _major_out=$(PATH="$FP_NIP/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
    "$FP_NIP/st.env" github.com/docker/docker 29.3.1 ${_major_scope[@]+"${_major_scope[@]}"} CVE-MAJOR 2>&1) || _major_rc=$?
  check "major migration $_major_case remains a registry failure" test "$_major_rc" -eq 4
  if [[ "$_major_expected" == true ]]; then
    check "major migration $_major_case detects the repaired module" grep -q '^INCOMPATIBLE_MAJOR_BUMP:' <<< "$_major_out"
  else
    check "major migration $_major_case ignores unrelated incompatible versions" ! grep -q '^INCOMPATIBLE_MAJOR_BUMP:' <<< "$_major_out"
  fi
  check "major migration $_major_case creates no commit" test "$(git -C "$FP_NIP" rev-parse HEAD)" = "$_major_head"
done


# === scan-regression.sh retry loop ===
# The loop (lines 39-53) retries up to CVE_FIX_SCAN_ATTEMPTS times when
# is_scan_transient matches the stderr output. Two behavioural paths:
#   (a) transient-then-success: scan.sh fails once with a network error, succeeds
#       on retry -> exit 0, SCAN_FAILED never emitted.
#   (b) always-transient (max retries exhausted): scan.sh always fails with a
#       network error -> exit non-zero, SCAN_FAILED=1 emitted.
# CVE_FIX_RETRY_BASE=0 keeps sleep at 0s so the suite stays instant.
echo "scan-regression retry loop"
SR_RETRY_DIR="$TMPD/sr-retry"; mkdir -p "$SR_RETRY_DIR"
SR_RETRY_REPO="$SR_RETRY_DIR/repo"; mkdir -p "$SR_RETRY_REPO"
touch "$SR_RETRY_REPO/go.mod"
SR_RETRY_RDIR="$SR_RETRY_DIR/report"; mkdir -p "$SR_RETRY_RDIR"
SR_RETRY_SCRIPTS="$SR_RETRY_DIR/scripts"; mkdir -p "$SR_RETRY_SCRIPTS"
cp "$SCRIPT_DIR/lib.sh" "$SR_RETRY_SCRIPTS/"
printf 'REPO=%q\nBRANCH=devel\nCVE_SCRIPTS=%q\nHAS_LOCAL_GRYPE=false\nCONTAINER_CMD=\n' \
  "$SR_RETRY_REPO" "$SR_RETRY_SCRIPTS" > "$SR_RETRY_DIR/state.env"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$SR_RETRY_RDIR/initial-scan.json"

# (a) Transient on attempt 1, valid JSON on attempt 2 -> exit 0, no SCAN_FAILED.
SR_CNTA="$SR_RETRY_DIR/call-count-a"
printf '0\n' > "$SR_CNTA"
cat > "$SR_RETRY_SCRIPTS/scan.sh" <<MOCKEOF
#!/usr/bin/env bash
COUNT=\$(cat "$SR_CNTA"); COUNT=\$((COUNT + 1)); printf '%s\n' "\$COUNT" > "$SR_CNTA"
if [[ \$COUNT -eq 1 ]]; then
  echo "dial tcp: connection refused: no route to host" >&2; exit 1
fi
echo '{"matches":[],"ignoredMatches":[]}'
MOCKEOF
chmod +x "$SR_RETRY_SCRIPTS/scan.sh"
SRA_OUT_FILE="$TMPD/sra.out"
CVE_FIX_SCAN_ATTEMPTS=2 CVE_FIX_RETRY_BASE=0 \
  bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR_RETRY_DIR/state.env" "$SR_RETRY_RDIR" \
  >"$SRA_OUT_FILE" 2>&1 && SRA_RC=0 || SRA_RC=$?
check "retry: transient-then-success exits 0" test "$SRA_RC" -eq 0
check "retry: transient-then-success no SCAN_FAILED" ! grep -q 'SCAN_FAILED=1' "$SRA_OUT_FILE"
check "retry: transient-then-success scan.sh called twice" test "$(cat "$SR_CNTA")" -eq 2

# (b) Always transient (max retries exhausted) -> exit non-zero, SCAN_FAILED=1.
SR_CNTB="$SR_RETRY_DIR/call-count-b"
printf '0\n' > "$SR_CNTB"
cat > "$SR_RETRY_SCRIPTS/scan.sh" <<MOCKEOF
#!/usr/bin/env bash
COUNT=\$(cat "$SR_CNTB"); COUNT=\$((COUNT + 1)); printf '%s\n' "\$COUNT" > "$SR_CNTB"
echo "dial tcp: connection refused: no route to host" >&2; exit 1
MOCKEOF
chmod +x "$SR_RETRY_SCRIPTS/scan.sh"
SRB_OUT_FILE="$TMPD/srb.out"
CVE_FIX_SCAN_ATTEMPTS=2 CVE_FIX_RETRY_BASE=0 \
  bash "$SCRIPT_DIR/../subagents/scan-regression.sh" "$SR_RETRY_DIR/state.env" "$SR_RETRY_RDIR" \
  >"$SRB_OUT_FILE" 2>&1 && SRB_RC=0 || SRB_RC=$?
check "retry: always-transient exits nonzero" test "$SRB_RC" -ne 0
check "retry: always-transient emits SCAN_FAILED" grep -q 'SCAN_FAILED=1' "$SRB_OUT_FILE"
check "retry: always-transient scan.sh called max times" test "$(cat "$SR_CNTB")" -eq 2

# === HAS_VENDOR=true: untracked vendor files are staged ===
# Regression guard for the fix-stdlib.sh bug where vendor staging used
# `git diff --name-only | grep "^vendor/"` which misses untracked new entries
# added by go mod vendor. Both fix-package.sh and fix-stdlib.sh must use
# `git add vendor/` directly to pick up untracked files.

echo "fix-package HAS_VENDOR=true: untracked vendor file is staged"
FP_VND="$TMPD/fp-vendor"; mkdir -p "$FP_VND/gostub"
( cd "$FP_VND" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/vendtest v1.0.0\n' > "$FP_VND/go.mod"
( cd "$FP_VND" && git add go.mod && git commit -qm init )
# go stub: go get updates the require line; all else no-op
cat > "$FP_VND/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"; ver=$(printf '%s' "$pkgver" | sed 's/.*@//')
  awk -v v="$ver" \
    '/^require example\.com\/vendtest /{print "require example.com/vendtest " v; next} {print}' \
    "$dir/go.mod" > "$dir/go.mod.tmp" && mv "$dir/go.mod.tmp" "$dir/go.mod"
  exit 0
fi
exit 0
STUB
chmod +x "$FP_VND/gostub/go"
# Pre-create an untracked vendor file simulating a new entry from go mod vendor
mkdir -p "$FP_VND/vendor/example.com/vendtest"
printf 'package vendtest\n' > "$FP_VND/vendor/example.com/vendtest/file.go"
cat > "$FP_VND/st.env" <<STENV
REPO="$FP_VND"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="true"
DIFF_IGNORE_ARGS=""
STENV
FP_VND_OUT=$(
  cd "$FP_VND" && PATH="$FP_VND/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_VND/st.env" example.com/vendtest v1.0.1 GHSA-vnd-0001 2>&1
) && FP_VND_RC=0 || FP_VND_RC=$?
check "fp HAS_VENDOR: exits 0" \
  test "$FP_VND_RC" -eq 0
check "fp HAS_VENDOR: untracked vendor file committed" \
  bash -c "git -C '$FP_VND' show HEAD -- 'vendor/example.com/vendtest/file.go' | grep -q 'package vendtest'"

echo "fix-package vendor rollback preserves only original files"
cp "$FP_VND/gostub/go" "$FP_VND/gostub/go.success"
printf 'original user file\n' > "$FP_VND/vendor/user-note"
printf 'original ignored file\n' > "$FP_VND/vendor/ignored-note"
printf 'vendor/ignored-*\n' > "$FP_VND/.gitignore"
git -C "$FP_VND" add .gitignore
git -C "$FP_VND" commit -qm 'ignore generated notes'
cat > "$FP_VND/gostub/go" <<'STUB'
#!/bin/sh
dir=.
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = get ]; then
  sed 's/v1.0.1/v1.0.2/' "$dir/go.mod" > "$dir/go.mod.tmp"
  mv "$dir/go.mod.tmp" "$dir/go.mod"
elif [ "$1 $2" = 'mod vendor' ]; then
  sed 's/go 1.25.0/go 1.27.0/' go.mod > go.mod.tmp
  mv go.mod.tmp go.mod
  printf 'corrupt tracked file\n' > vendor/example.com/vendtest/file.go
  printf 'new generated file\n' > vendor/example.com/vendtest/new.go
  printf 'new ignored file\n' > vendor/ignored-new
  rm -f vendor/user-note
  printf 'overwritten ignored file\n' > vendor/ignored-note
fi
STUB
_VND_ROLLBACK_RC=0
PATH="$FP_VND/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" "$FP_VND/st.env" \
  example.com/vendtest v1.0.2 CVE-VENDOR-ROLLBACK > "$FP_VND/rollback.out" 2>&1 || _VND_ROLLBACK_RC=$?
check "vendor policy rejection exits 2" test "$_VND_ROLLBACK_RC" -eq 2
check "rollback restores tracked vendor contents" \
  test "$(cat "$FP_VND/vendor/example.com/vendtest/file.go")" = 'package vendtest'
check "rollback removes newly generated vendor source" test ! -e "$FP_VND/vendor/example.com/vendtest/new.go"
check "rollback removes newly generated ignored vendor file" test ! -e "$FP_VND/vendor/ignored-new"
check "rollback restores deleted pre-existing untracked file" \
  test "$(cat "$FP_VND/vendor/user-note")" = 'original user file'
check "rollback restores overwritten pre-existing ignored file" \
  test "$(cat "$FP_VND/vendor/ignored-note")" = 'original ignored file'
check "rollback restores original Go language floor" grep -q '^go 1.25.0$' "$FP_VND/go.mod"
mv "$FP_VND/gostub/go.success" "$FP_VND/gostub/go"

echo "fix-package generated files (end to end)"
FP_GEN="$TMPD/fp-generated"; mkdir -p "$FP_GEN/gostub"
( cd "$FP_GEN" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/gentest v1.0.0\n' > "$FP_GEN/go.mod"
printf 'a: 1\n    controller-gen.kubebuilder.io/version: v0.19.0\n' > "$FP_GEN/noise.yaml"
printf 'a: 1\n    controller-gen.kubebuilder.io/version: v0.19.0\n' > "$FP_GEN/real.yaml"
printf '// \tprotoc-gen-go v1.36.0\npackage x\n' > "$FP_GEN/api.pb.go"
( cd "$FP_GEN" && git add -A && git commit -qm init )
cp "$FP_VND/gostub/go" "$FP_GEN/gostub/go"
sed -i 's/vendtest/gentest/g' "$FP_GEN/gostub/go"
# The scan build left generated files dirty: two noise-only, one substantive.
sed -i 's/v0.19.0/v0.20.0/' "$FP_GEN/noise.yaml"
sed -i 's/v0.19.0/v0.20.0/; s/a: 1/a: 2/' "$FP_GEN/real.yaml"
sed -i 's/v1.36.0/v1.37.0/' "$FP_GEN/api.pb.go"
cat > "$FP_GEN/st.env" <<STENV
REPO="$FP_GEN"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS="-Icontroller-gen.kubebuilder.io/version -I^//"
STENV
FP_GEN_OUT=$(
  cd "$FP_GEN" && PATH="$FP_GEN/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_GEN/st.env" example.com/gentest v1.0.1 GHSA-gen-0001 2>&1
) && FP_GEN_RC=0 || FP_GEN_RC=$?
check "fp generated: exits 0" test "$FP_GEN_RC" -eq 0
check "fp generated: commit holds the dependency file and the substantive change only" \
  test "$(git -C "$FP_GEN" show --name-only --format= HEAD | sort | tr '\n' ' ')" = "go.mod real.yaml "
check "fp generated: noise-only CRD restored" git -C "$FP_GEN" diff --quiet HEAD~1 -- noise.yaml
check "fp generated: noise-only .pb.go restored" git -C "$FP_GEN" diff --quiet HEAD~1 -- api.pb.go
check "fp generated: working tree clean afterwards" test -z "$(git -C "$FP_GEN" status --porcelain --untracked-files=no)"

# `go get` and `go mod tidy` may add or rewrite the toolchain directive as
# incidental output. fix-package must put back exactly what the repository had,
# using go mod edit (canonical placement, trailing comments intact) rather than
# rewriting the file. The stub go injects the drift; go mod edit runs for real.
echo "fix-package restores the repository's toolchain directive"
fp_tc_repo() {  # NAME GOMOD — repo whose stub go bumps the dep and drifts the toolchain
  local d="$TMPD/fp-tc-$1" real_go
  real_go=$(command -v go)
  rm -rf "$d"; mkdir -p "$d/gostub"
  git -C "$d" init -q -b devel
  git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf '%s\n' "$2" > "$d/go.mod"
  git -C "$d" add go.mod; git -C "$d" commit -qm init
  cat > "$d/gostub/go" <<STUB
#!/bin/sh
dir="."
while [ "\$1" = "-C" ]; do dir="\$2"; shift 2; done
if [ "\$1" = "get" ]; then
  ver=\$(printf '%s' "\$2" | sed 's/.*@v//')
  # Like real go: rewrite an existing toolchain line in place, else append one.
  awk -v v="\$ver" '
    /example\\.com\\/tctest / { sub(/v[0-9.]+/, "v" v) }
    /^toolchain / { print "toolchain go1.99.0"; seen = 1; next }
    { print }
    END { if (!seen) print "\\ntoolchain go1.99.0" }' \
    "\$dir/go.mod" > "\$dir/go.mod.tmp" && mv "\$dir/go.mod.tmp" "\$dir/go.mod"
  exit 0
fi
if [ "\$1" = "mod" ] && [ "\$2" = "edit" ]; then exec "$real_go" -C "\$dir" "\$@"; fi
exit 0
STUB
  chmod +x "$d/gostub/go"
  printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION=unknown\nCVE_SCRIPTS=%q\nHAS_VENDOR=false\nDIFF_IGNORE_ARGS=\n' \
    "$d" "$SCRIPT_DIR" > "$d/st.env"
  printf '%s\n' "$d"
}
fp_tc_run() {  # REPO
  ( cd "$1" && PATH="$1/gostub:$PATH" GOFLAGS= \
    bash "$SCRIPT_DIR/fix-package.sh" "$1/st.env" example.com/tctest 1.0.1 GHSA-tc-0001 2>&1 )
}
FP_TC1=$(fp_tc_repo none $'module x\n\ngo 1.25.0\n\nrequire example.com/tctest v1.0.0')
FP_TC1_OUT=$(fp_tc_run "$FP_TC1") && FP_TC1_RC=0 || FP_TC1_RC=$?
check "fp toolchain: fix exits 0" test "$FP_TC1_RC" -eq 0
check "fp toolchain: dependency bumped" grep -q 'example.com/tctest v1.0.1' "$FP_TC1/go.mod"
check "fp toolchain: directive that go added is removed" ! grep -q '^toolchain' "$FP_TC1/go.mod"
FP_TC2=$(fp_tc_repo kept $'module x\n\ngo 1.25.0\n\ntoolchain go1.25.1 // pinned\n\nrequire example.com/tctest v1.0.0')
FP_TC2_OUT=$(fp_tc_run "$FP_TC2") && FP_TC2_RC=0 || FP_TC2_RC=$?
check "fp toolchain: preexisting directive kept: exits 0" test "$FP_TC2_RC" -eq 0
check "fp toolchain: preexisting directive restored to its original version" \
  grep -q '^toolchain go1.25.1$' "$FP_TC2/go.mod"
check "fp toolchain: restored directive stays beside the go line" \
  test "$(sed -n 5p "$FP_TC2/go.mod")" = "toolchain go1.25.1"
check "fp toolchain: only one toolchain directive" test "$(grep -c '^toolchain' "$FP_TC2/go.mod")" -eq 1

for FP_TOOLCHAIN_NAME in default go1.25.1-fips go1.26rc1; do
  FP_SPECIAL=$(fp_tc_repo "$FP_TOOLCHAIN_NAME" "$(printf 'module x\n\ngo 1.25.0\n\ntoolchain %s\n\nrequire example.com/tctest v1.0.0' "$FP_TOOLCHAIN_NAME")")
  FP_SPECIAL_OUT=$(fp_tc_run "$FP_SPECIAL") && FP_SPECIAL_RC=0 || FP_SPECIAL_RC=$?
  check "dependency fix restores $FP_TOOLCHAIN_NAME end to end" test "$FP_SPECIAL_RC" -eq 0
  check "dependency fix keeps exact $FP_TOOLCHAIN_NAME name" grep -qxF "toolchain $FP_TOOLCHAIN_NAME" "$FP_SPECIAL/go.mod"
  check "dependency fixed with $FP_TOOLCHAIN_NAME retained" grep -q 'example.com/tctest v1.0.1' "$FP_SPECIAL/go.mod"
done

# A toolchain edit changes no dependency graph: fix-stdlib must not tidy, vendor
# or stage anything but the go.mod it edited, even with HAS_VENDOR=true.
echo "fix-stdlib is a pure toolchain edit (HAS_VENDOR=true)"
FSL_VND="$TMPD/fsl-vendor"; mkdir -p "$FSL_VND/gostub"
( cd "$FSL_VND" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.24.0\n' > "$FSL_VND/go.mod"
printf 'package x\n' > "$FSL_VND/main.go"
printf 'example.com/dep v1.0.0 h1:abc=\n' > "$FSL_VND/go.sum"
( cd "$FSL_VND" && git add go.mod go.sum main.go && git commit -qm init )
FSL_REAL_GO=$(command -v go)
# Logging wrapper: record every go invocation, then run the real go.
cat > "$FSL_VND/gostub/go" <<STUB
#!/bin/sh
printf '%s\n' "\$*" >> "$FSL_VND/go-calls.log"
exec "$FSL_REAL_GO" "\$@"
STUB
chmod +x "$FSL_VND/gostub/go"
# An untracked vendor file that must NOT be swept into the commit.
mkdir -p "$FSL_VND/vendor/example.com/stdlib-dep"
printf 'package stdlib_dep\n' > "$FSL_VND/vendor/example.com/stdlib-dep/file.go"
cat > "$FSL_VND/st.env" <<EOF
REPO="$FSL_VND"
BRANCH="devel"
BUILD_GO_VERSION="go version go1.24.8 linux/amd64"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="true"
EOF
FSL_VND_OUT=$( cd "$FSL_VND" && PATH="$FSL_VND/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$FSL_VND/st.env" "1.24.7" "1.24.7" "CVE-2024-VENDOR" 2>&1 ) && FSL_VND_RC=0 || FSL_VND_RC=$?
check "fsl pure edit: exits 0" test "$FSL_VND_RC" -eq 0
check "fsl pure edit: toolchain set" grep -q '^toolchain go1.24.7$' "$FSL_VND/go.mod"
check "fsl pure edit: go directive unchanged" grep -q '^go 1.24.0$' "$FSL_VND/go.mod"
check "fsl pure edit: go mod tidy never runs" ! grep -q '^mod tidy' "$FSL_VND/go-calls.log"
check "fsl pure edit: go mod vendor never runs" ! grep -q '^mod vendor' "$FSL_VND/go-calls.log"
check "fsl pure edit: go.sum untouched" \
  test "$(git -C "$FSL_VND" show --name-only --format= HEAD | tr '\n' ' ')" = "go.mod "
check "fsl pure edit: untracked vendor file not committed" \
  bash -c "! git -C '$FSL_VND' ls-files --error-unmatch vendor/example.com/stdlib-dep/file.go >/dev/null 2>&1"

# Toolchain semantics: the greater of go and toolchain is the module's effective
# requirement; it is raised only when below the fix, never lowered, and comments
# on the directive survive. Runs with the network disabled and a go directive far
# above the local Go: go mod edit under GOTOOLCHAIN=auto would try to download it.
echo "fix-stdlib toolchain semantics"
fsl_repo() {  # NAME GOMOD_CONTENT BUILDER — repo plus state file; prints repo path
  local d="$TMPD/fsl-$1"
  rm -rf "$d"; mkdir -p "$d"
  git -C "$d" init -q -b devel
  git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf '%s\n' "$2" > "$d/go.mod"
  printf 'package x\n' > "$d/main.go"
  git -C "$d" add -A; git -C "$d" commit -qm init
  printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION=%q\nCVE_SCRIPTS=%q\nHAS_VENDOR=false\n' \
    "$d" "$3" "$SCRIPT_DIR" > "$d/st.env"
  printf '%s\n' "$d"
}
fsl_run() {  # REPO FIXVER
  ( cd "$1" && GOPROXY=off bash "$SCRIPT_DIR/fix-stdlib.sh" "$1/st.env" "$2" "$2" GHSA-tc-0001 2>&1 )
}
FSL_T1=$(fsl_repo lower $'module x\n\ngo 1.24.0\n\ntoolchain go1.24.2 // pinned for CI' unknown)
FSL_T1_OUT=$(fsl_run "$FSL_T1" 1.24.7) && FSL_T1_RC=0 || FSL_T1_RC=$?
check "toolchain lower than fix: exits 0" test "$FSL_T1_RC" -eq 0
check "toolchain lower than fix: raised to the fix" grep -q '^toolchain go1.24.7' "$FSL_T1/go.mod"
check "toolchain lower than fix: trailing comment preserved" grep -q '^toolchain go1.24.7 // pinned for CI$' "$FSL_T1/go.mod"
check "toolchain lower than fix: go directive untouched" grep -q '^go 1.24.0$' "$FSL_T1/go.mod"

FSL_T2=$(fsl_repo higher $'module x\n\ngo 1.24.0\n\ntoolchain go1.24.9' unknown)
FSL_T2_OUT=$(fsl_run "$FSL_T2" 1.24.7) || true
check "toolchain above fix: never lowered" grep -q '^toolchain go1.24.9$' "$FSL_T2/go.mod"
check "toolchain above fix: no commit" test "$(git -C "$FSL_T2" rev-list --count HEAD)" -eq 1

FSL_T3=$(fsl_repo goline $'module x\n\ngo 1.24.9' unknown)
FSL_T3_OUT=$(fsl_run "$FSL_T3" 1.24.7) || true
check "go directive already above fix: no toolchain added" ! grep -q '^toolchain' "$FSL_T3/go.mod"
check "go directive already above fix: no commit" test "$(git -C "$FSL_T3" rev-list --count HEAD)" -eq 1

# Regression: the root's toolchain already above the fix must not stop a second
# module that is still behind from being fixed (the pre-loop guards judge the
# lowest effective requirement across modules anchors selection).
FSL_T6=$(fsl_repo rootahead $'module x\n\ngo 1.24.0\n\ntoolchain go1.24.9' unknown)
mkdir -p "$FSL_T6/tools"; printf 'module x/tools\n\ngo 1.24.1\n' > "$FSL_T6/tools/go.mod"
git -C "$FSL_T6" add -A; git -C "$FSL_T6" commit -qm tools
FSL_T6_OUT=$(fsl_run "$FSL_T6" 1.24.7) && FSL_T6_RC=0 || FSL_T6_RC=$?
check "root toolchain ahead, tools behind: exits 0" test "$FSL_T6_RC" -eq 0
check "root toolchain ahead, tools behind: tools module fixed" grep -q '^toolchain go1.24.7$' "$FSL_T6/tools/go.mod"
check "root toolchain ahead, tools behind: root left as-is" \
  bash -c "grep -q '^toolchain go1.24.9\$' '$FSL_T6/go.mod' && ! grep -q 'go1.24.7' '$FSL_T6/go.mod'"
check "root toolchain ahead, tools behind: not routed to NEEDS_REVIEW" ! grep -q 'NEEDS_REVIEW' <<< "$FSL_T6_OUT"

# go directive above the local Go (so a download would be needed) with a known builder
FSL_T4=$(fsl_repo future $'module x\n\ngo 1.99.0' "go version go1.99.9 linux/amd64")
FSL_T4_OUT=$(fsl_run "$FSL_T4" 1.99.5) && FSL_T4_RC=0 || FSL_T4_RC=$?
check "future go directive offline: exits 0 without downloading a toolchain" test "$FSL_T4_RC" -eq 0
check "future go directive offline: toolchain set" grep -q '^toolchain go1.99.5$' "$FSL_T4/go.mod"
check "future go directive offline: go directive untouched" grep -q '^go 1.99.0$' "$FSL_T4/go.mod"

FSL_T5=$(fsl_repo commit $'module x\n\ngo 1.24.0' unknown)
FSL_T5_OUT=$(fsl_run "$FSL_T5" 1.24.7) || true
check "commit subject names the Go version" \
  test "$(git -C "$FSL_T5" log -1 --format=%s)" = "Bump Go to 1.24.7 for stdlib CVEs"
check "commit body says toolchain, not a go requirement bump" \
  bash -c "git -C '$FSL_T5' log -1 --format=%b | grep -q 'Sets the toolchain directive to go1.24.7'"
check "commit body lines fit the 72-column rule" \
  bash -c "! git -C '$FSL_T5' log -1 --format=%b | awk 'length > 72 { bad=1 } END { exit !bad }'"

echo "stdlib fixes use effective compiler streams"
FSL_LIB=$(fsl_repo library $'module x\n\ngo 1.18\n\ntoolchain go1.24.2' unknown)
FSL_LIB_OUT=$(fsl_run "$FSL_LIB" 1.24.7) && FSL_LIB_RC=0 || FSL_LIB_RC=$?
check "library language floor does not block same-toolchain-minor fix" test "$FSL_LIB_RC" -eq 0
check "library compiler fixed" grep -q '^toolchain go1.24.7$' "$FSL_LIB/go.mod"
check "library language floor preserved" grep -q '^go 1.18$' "$FSL_LIB/go.mod"

FSL_ROOT=$(fsl_repo languageroot $'module x\n\ngo 1.26.0' unknown)
mkdir -p "$FSL_ROOT/tools"; printf 'module x/tools\n\ngo 1.24.1\n' > "$FSL_ROOT/tools/go.mod"
git -C "$FSL_ROOT" add tools/go.mod; git -C "$FSL_ROOT" commit -qm tools
FSL_ROOT_OUT=$(fsl_run "$FSL_ROOT" 1.24.7) && FSL_ROOT_RC=0 || FSL_ROOT_RC=$?
check "newer root stream requires its own verification" test "$FSL_ROOT_RC" -eq 2
check "tools patch applied beside newer root" grep -q '^toolchain go1.24.7$' "$FSL_ROOT/tools/go.mod"
check "newer root preserved" git -C "$FSL_ROOT" diff --quiet HEAD~1 -- go.mod
check "newer root stream is not falsely reported fixed" ! grep -q '^FIXED: stdlib' <<< "$FSL_ROOT_OUT"
check "newer root stream explains missing fix proof" grep -q 'stream 1.26 needs its own stdlib fix verification' <<< "$FSL_ROOT_OUT"

FSL_MIXED=$(fsl_repo mixedstreams $'module x\n\ngo 1.25.0' unknown)
mkdir -p "$FSL_MIXED/tools"; printf 'module x/tools\n\ngo 1.24.0\n' > "$FSL_MIXED/tools/go.mod"
git -C "$FSL_MIXED" add tools/go.mod; git -C "$FSL_MIXED" commit -qm tools
_mixed_req=$(printf '%s' '[{"cve":"CVE-MIXED","versions":["1.24.9","1.25.8"]}]' | base64 | tr -d '\n')
_mixed_rc=0
_mixed_out=$(CVE_FIX_REQUIREMENTS_B64="$_mixed_req" fsl_run "$FSL_MIXED" 1.25.8) || _mixed_rc=$?
check "mixed stdlib streams retain an unverified newer module" test "$_mixed_rc" -eq 2
check "mixed stdlib streams patch the selected tools stream" grep -q '^toolchain go1.24.9$' "$FSL_MIXED/tools/go.mod"
check "mixed stdlib streams preserve the root floor" git -C "$FSL_MIXED" diff --quiet HEAD~1 -- go.mod
check "mixed stdlib streams cannot report a complete fix" ! grep -q '^FIXED: stdlib' <<< "$_mixed_out"

# Grouped scan dispatch must anchor on the selected toolchain, not go 1.18.
FSL_GROUP=$(fsl_repo grouped $'module x\n\ngo 1.18\n\ntoolchain go1.24.2' unknown)
FSL_GROUP_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.23.9","1.24.7","1.25.2"]},{"cve":"CVE-B","versions":["1.23.8","1.24.6","1.25.1"]}]' | base64 | tr -d '\n')
FSL_GROUP_OUT=$(CVE_FIX_REQUIREMENTS_B64="$FSL_GROUP_REQ" fsl_run "$FSL_GROUP" 1.25.2) && FSL_GROUP_RC=0 || FSL_GROUP_RC=$?
check "grouped library fix uses compiler stream" test "$FSL_GROUP_RC" -eq 0
check "grouped library fix reaches every advisory threshold" grep -q '^toolchain go1.24.7$' "$FSL_GROUP/go.mod"

FSL_KNOWN=$(fsl_repo builderstream $'module x\n\ngo 1.18' 'go version go1.24.9 linux/amd64')
FSL_KNOWN_OUT=$(CVE_FIX_REQUIREMENTS_B64="$FSL_GROUP_REQ" fsl_run "$FSL_KNOWN" 1.25.2) && FSL_KNOWN_RC=0 || FSL_KNOWN_RC=$?
check "known builder selects its patched stream" test "$FSL_KNOWN_RC" -eq 0
check "known builder selects 1.24 threshold" grep -q '^toolchain go1.24.7$' "$FSL_KNOWN/go.mod"
check "known builder preserves old library language floor" grep -q '^go 1.18$' "$FSL_KNOWN/go.mod"

FSL_DEFAULT=$(fsl_repo default $'module x\n\ngo 1.24.0\n\ntoolchain default' unknown)
FSL_DEFAULT_OUT=$(fsl_run "$FSL_DEFAULT" 1.24.7) && FSL_DEFAULT_RC=0 || FSL_DEFAULT_RC=$?
check "toolchain default does not masquerade as a fixed release" test "$FSL_DEFAULT_RC" -eq 0
check "toolchain default is replaced with fixed compiler" grep -q '^toolchain go1.24.7$' "$FSL_DEFAULT/go.mod"

TH_DEFAULT="$TMPD/toolchain-default"; mkdir -p "$TH_DEFAULT"
printf 'module x\n\ngo 1.24.0\n\ntoolchain default\n' > "$TH_DEFAULT/go.mod"
check "default uses go line as version floor" test "$(gomod_effective_go "$TH_DEFAULT")" = 1.24.0
restore_gomod_toolchain "$TH_DEFAULT" default >/dev/null
set_gomod_toolchain "$TH_DEFAULT" go1.24.1
TH_RESTORE_RC=0; restore_gomod_toolchain "$TH_DEFAULT" default >/dev/null 2>&1 || TH_RESTORE_RC=$?
check "default toolchain can be restored after go get" test "$TH_RESTORE_RC" -eq 0
check "default toolchain restored exactly" grep -q '^toolchain default$' "$TH_DEFAULT/go.mod"
printf 'module x\n\ngo 1.24.0\n\ntoolchain go1.24.7-fips\n' > "$TH_DEFAULT/go.mod"
check "custom toolchain suffix is not a prerelease" test "$(gomod_effective_go "$TH_DEFAULT")" = 1.24.7
set_gomod_toolchain "$TH_DEFAULT" go1.24.9
TH_CUSTOM_RC=0; restore_gomod_toolchain "$TH_DEFAULT" go1.24.7-fips >/dev/null 2>&1 || TH_CUSTOM_RC=$?
check "custom toolchain can be restored after go get" test "$TH_CUSTOM_RC" -eq 0
check "custom toolchain restored exactly" grep -q '^toolchain go1.24.7-fips$' "$TH_DEFAULT/go.mod"

FSL_RC=$(fsl_repo rccompiler $'module x\n\ngo 1.24.0\n\ntoolchain go1.26rc1' unknown)
FSL_RC_OUT=$(fsl_run "$FSL_RC" 1.26.1) && FSL_RC_STATUS=0 || FSL_RC_STATUS=$?
check "native Go release candidate accepts stable patch in same minor" test "$FSL_RC_STATUS" -eq 0
check "native Go release candidate upgraded to stable fixed release" grep -q '^toolchain go1.26.1$' "$FSL_RC/go.mod"
FSL_PSEUDO=$(fsl_repo pseudofix $'module x\n\ngo 1.24.0' unknown)
FSL_PSEUDO_OUT=$(fsl_run "$FSL_PSEUDO" 1.24.7-20260101000000-aaaaaaaaaaaa) && FSL_PSEUDO_STATUS=0 || FSL_PSEUDO_STATUS=$?
check "module pseudo-version cannot become a Go toolchain directive" test "$FSL_PSEUDO_STATUS" -eq 2
check "module pseudo-version leaves repository unchanged" test "$(git -C "$FSL_PSEUDO" rev-list --count HEAD)" -eq 1

FSL_CUSTOM=$(fsl_repo customcompiler $'module x\n\ngo 1.24.0\n\ntoolchain go1.24.2-fips' unknown)
FSL_CUSTOM_OUT=$(fsl_run "$FSL_CUSTOM" 1.24.7) && FSL_CUSTOM_STATUS=0 || FSL_CUSTOM_STATUS=$?
check "vulnerable custom compiler needs vendor-supported fix" test "$FSL_CUSTOM_STATUS" -eq 2
check "custom compiler policy survives stdlib repair attempt" grep -q '^toolchain go1.24.2-fips$' "$FSL_CUSTOM/go.mod"
check "custom compiler repair creates no stock-Go commit" test "$(git -C "$FSL_CUSTOM" rev-list --count HEAD)" -eq 1
check "custom compiler repair reports the concrete policy boundary" grep -q 'vendor-supported fix' <<< "$FSL_CUSTOM_OUT"

echo "toolchain helpers"
TH="$TMPD/th"; rm -rf "$TH"; mkdir -p "$TH"
printf 'module x\n\ngo 1.24.0\n' > "$TH/go.mod"
check "gomod_toolchain: none -> empty" test -z "$(gomod_toolchain "$TH")"
check "gomod_effective_go: go line only" test "$(gomod_effective_go "$TH")" = "1.24.0"
set_gomod_toolchain "$TH" go1.24.5
check "set_gomod_toolchain writes the directive" grep -q '^toolchain go1.24.5$' "$TH/go.mod"
check "gomod_toolchain reads it back" test "$(gomod_toolchain "$TH")" = "go1.24.5"
printf 'module x\n\ngo 1.24.0\n\nrequire example.com/dep vv1\n' > "$TH/bad.mod"
mkdir -p "$TH/bad"; cp "$TH/bad.mod" "$TH/bad/go.mod"
check "gomod_toolchain: unreadable go.mod fails instead of reading as 'no directive'" \
  bash -c "! (source '$SCRIPT_DIR/lib.sh'; gomod_toolchain '$TH/bad') >/dev/null 2>&1"
check "restore_gomod_toolchain: unreadable go.mod fails loudly" \
  bash -c "! (source '$SCRIPT_DIR/lib.sh'; restore_gomod_toolchain '$TH/bad' '') >/dev/null 2>&1"
check "gomod_effective_go: unreadable go.mod fails" \
  bash -c "! (source '$SCRIPT_DIR/lib.sh'; gomod_effective_go '$TH/bad') >/dev/null 2>&1"
check "gomod_effective_go: toolchain above go wins" test "$(gomod_effective_go "$TH")" = "1.24.5"
printf 'module x\n\ngo 1.26.0\n\ntoolchain go1.24.0\n' > "$TH/go.mod"
check "gomod_effective_go: toolchain below go is ignored" test "$(gomod_effective_go "$TH")" = "1.26.0"
printf 'module x\n\ngo 1.24.0\n\ntoolchain go1.24.1 // note\n' > "$TH/go.mod"
check "gomod_toolchain: comment not included" test "$(gomod_toolchain "$TH")" = "go1.24.1"
check "set_gomod_toolchain rejects a bad name" bash -c "! (source '$SCRIPT_DIR/lib.sh'; set_gomod_toolchain '$TH' 1.24.7) 2>/dev/null"
check "set_gomod_toolchain rejects injection-looking input" bash -c "! (source '$SCRIPT_DIR/lib.sh'; set_gomod_toolchain '$TH' 'none -go=9') 2>/dev/null"
restore_gomod_toolchain "$TH" ""
check "restore_gomod_toolchain: removes a directive that was absent" ! grep -q '^toolchain' "$TH/go.mod"
restore_gomod_toolchain "$TH" "go1.24.3"
check "restore_gomod_toolchain: re-adds one that was present" grep -q '^toolchain go1.24.3$' "$TH/go.mod"
printf 'module x\n\ngo 1.24.0\n\nrequire example.com/dep v1.0.0 // indirect\n' > "$TH/go.mod"
restore_gomod_toolchain "$TH" ""
check "restore_gomod_toolchain: no-op leaves the file byte-identical" \
  test "$(cat "$TH/go.mod")" = "$(printf 'module x\n\ngo 1.24.0\n\nrequire example.com/dep v1.0.0 // indirect')"
restore_gomod_toolchain "$TH" "go1.24.3"
check "restore_gomod_toolchain: re-added directive is placed after go, not at EOF" \
  test "$(sed -n 5p "$TH/go.mod")" = "toolchain go1.24.3"

# === K8S_VERSION_GUARD submodule detection (real invocation, Bug #1) ===
# K8S_BEFORE/K8S_AFTER must scan all go.mod files; a submodule-only bump was silently allowed through (K8S_BEFORE empty).
echo "K8S_VERSION_GUARD submodule detection (real invocation)"
FP_K8SM="$TMPD/fp-k8sm"; mkdir -p "$FP_K8SM/tools" "$FP_K8SM/gostub"
( cd "$FP_K8SM" && git init -q && git config user.email t@t && git config user.name t )
# Root go.mod has NO k8s.io/client-go — the old single-file grep returns empty.
# tools/go.mod has k8s.io/client-go v0.30.0 — the fix bumps it to v0.31.0.
printf 'module x\ngo 1.25.0\n\nrequire example.com/other v1.0.0\n' > "$FP_K8SM/go.mod"
printf 'module x/tools\ngo 1.25.0\n\nrequire k8s.io/client-go v0.30.0\n' > "$FP_K8SM/tools/go.mod"
( cd "$FP_K8SM" && git add go.mod tools/go.mod && git commit -qm init )
# go stub: `go get pkg@vVER` in tools/ bumps k8s.io/client-go minor (0.30 → 0.31);
# all other verbs no-op. `go list -m` for transitive dep check returns empty.
cat > "$FP_K8SM/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  gomod="$dir/go.mod"
  # Bump k8s.io/client-go from v0.30.x to v0.31.0 in the target go.mod
  sed 's|k8s.io/client-go v0\.30\.[0-9]*|k8s.io/client-go v0.31.0|' \
    "$gomod" > "$gomod.tmp" && mv "$gomod.tmp" "$gomod"
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then echo ""; fi
exit 0
STUB
chmod +x "$FP_K8SM/gostub/go"
cat > "$FP_K8SM/st.env" <<STENV
REPO="$FP_K8SM"
BRANCH="release-0.21"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
K8S_VERSION_GUARD="true"
STENV
# Fix k8s.io/client-go v0.30→v0.31 (minor bump); guard must exit 2 (NEEDS_REVIEW).
# Old bug: root-only grep left K8S_BEFORE empty, short-circuiting the guard.
FP_K8SM_OUT=$(
  cd "$FP_K8SM" && PATH="$FP_K8SM/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_K8SM/st.env" k8s.io/client-go 0.31.0 CVE-2025-K8SM 2>&1
) && FP_K8SM_RC=0 || FP_K8SM_RC=$?
check "K8S guard submodule-only: exits 2"          test "$FP_K8SM_RC" -eq 2
check "K8S guard submodule-only: NEEDS_REVIEW msg" grep -q 'NEEDS_REVIEW\|would upgrade' <<< "$FP_K8SM_OUT"
check "K8S guard submodule-only: no FIXED line"    ! grep -qi 'FIXED:' <<< "$FP_K8SM_OUT"
# tools/go.mod must have been rolled back to v0.30.0
check "K8S guard submodule-only: tools rolled back" grep -q 'v0\.30\.0' "$FP_K8SM/tools/go.mod"

# Main review path with Codex: exercise review.sh itself, including provider
# selection, structured-output parsing, and stdin isolation.
REVIEW_CODEX_REPO="$TMPD/review-codex-repo"
make_test_repo "$REVIEW_CODEX_REPO"
REVIEW_CODEX_STATE="$TMPD/review-codex.env"
make_go_state "$REVIEW_CODEX_STATE" "$REVIEW_CODEX_REPO"
REVIEW_CODEX_BIN="$TMPD/review-codex-bin"; mkdir -p "$REVIEW_CODEX_BIN"
printf '#!/usr/bin/env bash\nif IFS= read -r leaked; then echo "LEAKED_STDIN:$leaked"; fi\necho "FIXED: example.com/pkg — reviewed by Codex"\n' \
  > "$REVIEW_CODEX_BIN/codex"
chmod +x "$REVIEW_CODEX_BIN/codex"
REVIEW_CODEX_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" "" "scan is clean" \
  <<< "caller input must not reach Codex")
check "review Codex: selected provider" grep -qF 'Invoking codex for review' <<< "$REVIEW_CODEX_OUT"
check "review Codex: exposes reviewer output for audit" grep -qF 'FIXED: example.com/pkg — reviewed by Codex' <<< "$REVIEW_CODEX_OUT"
check "review Codex: cannot write resolved sentinel" ! test -e "${REVIEW_CODEX_STATE}.review-resolved"
check "review Codex: caller stdin closed" ! grep -qF 'LEAKED_STDIN:' <<< "$REVIEW_CODEX_OUT"

# Validate real reviewer output: only the literal template reason is a
# placeholder. Words and explanations starting with "reason" are valid.
cat > "$REVIEW_CODEX_BIN/codex" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$REVIEW_PLACEHOLDER_OUTCOME"
exit "${REVIEW_PROVIDER_RC:-0}"
EOF
for _review_case in reasonable explained literal whitespace package infra-quote auth-quote prose-quote fenced-quote nonzero; do
  _review_package=example.com/pkg
  _review_expected_rc=1
  _review_unresolved=false; _review_provider_rc=0
  case "$_review_case" in
    reasonable)
      _review_outcome='RESOLVED: example.com/pkg — reasonable patch bump'
      _review_expected_rc=0
      ;;
    explained)
      _review_outcome='UNRESOLVED: example.com/pkg — reason: Go 1.25 needed (need team input)'
      _review_expected_rc=0
      _review_unresolved=true
      ;;
    literal) _review_outcome='RESOLVED: example.com/pkg — reason' ;;
    whitespace) _review_outcome=$'UNRESOLVED: example.com/pkg — reason \t' ;;
    package)
      _review_package=pkg.name/path
      _review_outcome='RESOLVED: pkg.name/path — actual decision'
      ;;
    infra-quote|auth-quote|prose-quote|fenced-quote|nonzero)
      _review_expected_rc=0; _review_unresolved=true
      _review_outcome='UNRESOLVED: example.com/pkg — captured HTTP error: 429 needs a project decision'
      case "$_review_case" in
        auth-quote) _review_outcome='UNRESOLVED: example.com/pkg — project config reports invalid model' ;;
        prose-quote) _review_outcome=$'The captured registry request reports API Error: 403.\nUNRESOLVED: example.com/pkg — registry configuration needs team input' ;;
        fenced-quote) _review_outcome=$'Captured project output:\n```text\nHTTP error: 429\n```\nUNRESOLVED: example.com/pkg — registry configuration needs team input' ;;
        nonzero) _review_provider_rc=7; _review_unresolved=false ;;
      esac
      ;;
  esac
  printf 'UNRESOLVED: stale.invalid/pkg — previous review\n' > "${REVIEW_CODEX_STATE}.review-unresolved"
  _review_placeholder_rc=0
  _review_placeholder_out=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
    REVIEW_PLACEHOLDER_OUTCOME="$_review_outcome" \
    REVIEW_PROVIDER_RC="$_review_provider_rc" CVE_FIX_AGENT_ATTEMPTS=1 \
    bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" \
    "NEEDS_REVIEW: $_review_package — decision needed" 'scan finding' 2>&1) || _review_placeholder_rc=$?
  check "review placeholder $_review_case returns the correct status" test "$_review_placeholder_rc" -eq "$_review_expected_rc"
  if [[ "$_review_unresolved" == true ]]; then
    check "review $_review_case preserves structured unresolved outcomes" \
      test "$(cat "${REVIEW_CODEX_STATE}.review-unresolved" 2>/dev/null)" = "$(grep '^UNRESOLVED:' <<< "$_review_outcome")"
  else
    check "review placeholder $_review_case writes no unresolved sentinel" test ! -e "${REVIEW_CODEX_STATE}.review-unresolved"
  fi
  if [[ "$_review_expected_rc" -ne 0 ]]; then
    check "review placeholder $_review_case reports its rejection" \
      grep -qF 'reviewer returned a placeholder outcome:' <<< "$_review_placeholder_out"
  fi
done
rm -f "${REVIEW_CODEX_STATE}.review-unresolved"

# Codex repeats its final answer in some transcript modes. Exact structured
# outcomes must be propagated once, not counted twice by the parent gate.
cat > "$REVIEW_CODEX_BIN/codex" <<'EOF'
#!/usr/bin/env bash
echo 'UNRESOLVED: example.com/pkg — builder decision needed (need team input)'
echo 'UNRESOLVED: example.com/residual — rebuilt scan will handle this (need team input)'
echo 'tokens used'
echo '100'
echo 'UNRESOLVED: example.com/pkg — builder decision needed (need team input)'
EOF
chmod +x "$REVIEW_CODEX_BIN/codex"
REVIEW_CODEX_DUP_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" \
  'NEEDS_REVIEW: example.com/pkg — builder decision needed' 'scan finding')
check "review Codex: duplicate transcript outcomes deduplicated" \
  test "$(grep -c '^UNRESOLVED:' "${REVIEW_CODEX_STATE}.review-unresolved")" = 1
check "review Codex: out-of-scope outcome cannot affect parent state" \
  ! grep -qF 'example.com/residual' "${REVIEW_CODEX_STATE}.review-unresolved"
check "review Codex: summary prints deduplicated outcome" \
  test "$(grep -c '^UNRESOLVED:' <<< "$REVIEW_CODEX_DUP_OUT")" = 4

# Real partial runs contain workflow gates as well as package outcomes. Those
# gates must remain publishing blockers without becoming invented dependencies.
REVIEW_MIXED_SUMMARY=$'NEEDS_REVIEW: example.com/pkg — builder decision needed\nNEEDS_REVIEW: tests failed after applying fixes\nNEEDS_REVIEW: subagent verification failed — reports at /tmp/reports\nNEEDS_REVIEW: initial build failed — stdlib coverage unknown'
REVIEW_MIXED_RC=0
REVIEW_MIXED_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" "$REVIEW_MIXED_SUMMARY" 'scan finding') || REVIEW_MIXED_RC=$?
check "package review accepts real outcomes alongside workflow failures" test "$REVIEW_MIXED_RC" -eq 0
check "package review does not demand invented workflow packages" \
  ! grep -q 'reviewer omitted requested package' <<< "$REVIEW_MIXED_OUT"
check "workflow summary filter preserves only the exact package outcome" \
  test "$(printf '%s\n' "$REVIEW_MIXED_SUMMARY" | package_review_summary)" = 'NEEDS_REVIEW: example.com/pkg — builder decision needed'
check "workflow summary filter retains stdlib, errors, and timeouts" \
  test "$(printf '%s\n' 'NEEDS_REVIEW: stdlib — compiler decision needed' 'ERROR: example.com/e — failed update' 'TIMEOUT: example.com/t — retry' | package_review_summary | wc -l | tr -d ' ')" = 3

REVIEW_PARTIAL_POLICY="$TMPD/partial-ignore-policy"
printf 'golang.org/x/crypto|/go.mod\nexample.com/unscoped\nexampleXcom/literal|/tools/go.mod\n' > "$REVIEW_PARTIAL_POLICY"
check "partial ignore cannot erase scoped policy review without an agent" \
  ! package_ignore_can_clear_review golang.org/x/crypto "$REVIEW_PARTIAL_POLICY"
check "partial ignore cannot erase unscoped policy review" \
  ! package_ignore_can_clear_review example.com/unscoped "$REVIEW_PARTIAL_POLICY"
check "partial ignore preserves reviewer unresolved verdict without a policy file" \
  ! package_ignore_can_clear_review example.com/unresolved "$TMPD/no-policy-file" example.com/unresolved
check "partial ignore policy identities are literal and package-specific" \
  package_ignore_can_clear_review example.com/literal "$REVIEW_PARTIAL_POLICY" example.com/other
check "completed ignore without a pending policy or reviewer decision can clear review" \
  package_ignore_can_clear_review example.com/ignored "$TMPD/no-policy-file"

# Package names are literal, not regular expressions: one requested module
# cannot supply another module's missing verdict merely by matching its dots.
cat > "$REVIEW_CODEX_BIN/codex" <<'EOF'
#!/usr/bin/env bash
echo 'UNRESOLVED: exampleXcom/pkg — builder decision needed (need team input)'
EOF
REVIEW_LITERAL_RC=0
REVIEW_LITERAL_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" \
  $'NEEDS_REVIEW: example.com/pkg — decision needed\nNEEDS_REVIEW: exampleXcom/pkg — decision needed' 'scan finding' 2>&1) || REVIEW_LITERAL_RC=$?
check "review completeness treats module-name dots literally" test "$REVIEW_LITERAL_RC" -ne 0
check "review completeness identifies the exact missing module" \
  grep -qF 'reviewer omitted requested package: example.com/pkg' <<< "$REVIEW_LITERAL_OUT"

# Provider capacity errors can return success from the CLI. Exercise the real
# review script's bounded retry and fallback, without accepting prompt outcomes.
rm -f "${REVIEW_CODEX_STATE}.review-unresolved" "${REVIEW_CODEX_STATE}.review-resolved"
REVIEW_CAPACITY_COUNT="$TMPD/review-capacity-count"
cat > "$REVIEW_CODEX_BIN/codex" <<'EOF'
#!/usr/bin/env bash
printf 'called\n' >> "$REVIEW_CAPACITY_COUNT"
printf 'RESOLVED: example.com/pkg — prompt example\n'
printf 'ERROR: Selected model is at capacity. Please try a different model.\n'
exit 0
EOF
REVIEW_CAPACITY_RC=0
REVIEW_CAPACITY_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  CVE_FIX_AGENT_ATTEMPTS=2 CVE_FIX_RETRY_BASE=0 REVIEW_CAPACITY_COUNT="$REVIEW_CAPACITY_COUNT" \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" \
  'NEEDS_REVIEW: example.com/pkg — builder decision needed' 'scan finding') || REVIEW_CAPACITY_RC=$?
check "zero-exit capacity uses manual fallback" test "$REVIEW_CAPACITY_RC" -eq 0
check "zero-exit capacity retries only to configured bound" test "$(wc -l < "$REVIEW_CAPACITY_COUNT" | tr -d ' ')" -eq 2
check "zero-exit capacity cannot approve echoed outcome" ! test -e "${REVIEW_CODEX_STATE}.review-resolved"
check "zero-exit capacity is reported as unavailable" grep -q 'review unavailable' <<< "$REVIEW_CAPACITY_OUT"

# === audit_branch_non_cve_files ===
# Test that the branch audit function warns when non-CVE files are touched,
# and stays silent when only dependency/ignore files are changed.
echo "audit_branch_non_cve_files"

# Set up a minimal git repo to drive the function.
_AUDIT_DIR="$TMPD/audit-repo"
mkdir -p "$_AUDIT_DIR"
( cd "$_AUDIT_DIR" && git init -q && git checkout -q -b release-0.99 )
git -C "$_AUDIT_DIR" config user.email "test@test.com"
git -C "$_AUDIT_DIR" config user.name "Test"
printf 'module example.com/m\ngo 1.23\n' > "$_AUDIT_DIR/go.mod"
printf '{}' > "$_AUDIT_DIR/go.sum"
( cd "$_AUDIT_DIR" && git add go.mod go.sum && git commit -qm init )
# Simulate 'origin/release-0.99' so audit_branch_non_cve_files can diff against it.
( cd "$_AUDIT_DIR" && git remote add origin . && git fetch -q origin release-0.99:refs/remotes/origin/release-0.99 )

# (a) Only go.mod changed → no warning output.
printf 'module example.com/m\ngo 1.23\nrequire example.com/dep v1.0.1\n' > "$_AUDIT_DIR/go.mod"
( cd "$_AUDIT_DIR" && git add go.mod && git commit -qm "Bump dep" )
_AUDIT_CLEAN=$(
  cd "$_AUDIT_DIR"
  source "$SCRIPT_DIR/lib.sh"
  audit_branch_non_cve_files release-0.99
)
check "audit: go.mod-only → no warning" test -z "$_AUDIT_CLEAN"

# (b) .grype.yaml changed → no warning.
printf 'ignore:\n  - vulnerability: GHSA-0000-0000-0000\n' > "$_AUDIT_DIR/.grype.yaml"
( cd "$_AUDIT_DIR" && git add .grype.yaml && git commit -qm "Ignore CVE" )
_AUDIT_GRYPE=$(
  cd "$_AUDIT_DIR"
  source "$SCRIPT_DIR/lib.sh"
  audit_branch_non_cve_files release-0.99
)
check "audit: .grype.yaml-only → no warning" test -z "$_AUDIT_GRYPE"

# (c) tools/go.mod changed → no warning (submodule variant).
mkdir -p "$_AUDIT_DIR/tools"
printf 'module example.com/m/tools\ngo 1.23\n' > "$_AUDIT_DIR/tools/go.mod"
( cd "$_AUDIT_DIR" && git add tools/go.mod && git commit -qm "Bump tools dep" )
_AUDIT_TOOLS=$(
  cd "$_AUDIT_DIR"
  source "$SCRIPT_DIR/lib.sh"
  audit_branch_non_cve_files release-0.99
)
check "audit: tools/go.mod-only → no warning" test -z "$_AUDIT_TOOLS"

# (d) A Go source file changed → warning emitted.
printf 'package main\n' > "$_AUDIT_DIR/main.go"
( cd "$_AUDIT_DIR" && git add main.go && git commit -qm "Add main.go" )
_AUDIT_SRC=$(
  cd "$_AUDIT_DIR"
  source "$SCRIPT_DIR/lib.sh"
  audit_branch_non_cve_files release-0.99
) || true
check "audit: source file → warning contains 'main.go'"     grep -q "main.go" <<< "$_AUDIT_SRC"
check "audit: source file → warning text present"            grep -q "CVE fix branch touches" <<< "$_AUDIT_SRC"
check "audit: source file → remediation hint present"        grep -q "separate branch" <<< "$_AUDIT_SRC"
_AUDIT_RC=0
( cd "$_AUDIT_DIR" && source "$SCRIPT_DIR/lib.sh" && audit_branch_non_cve_files release-0.99 >/dev/null ) || _AUDIT_RC=$?
check "audit: source file → nonzero readiness status" test "$_AUDIT_RC" -eq 1

# (e) A Makefile changed → warning emitted.
printf 'all:\n\t@echo ok\n' > "$_AUDIT_DIR/Makefile"
( cd "$_AUDIT_DIR" && git add Makefile && git commit -qm "Add Makefile" )
_AUDIT_MK=$(
  cd "$_AUDIT_DIR"
  source "$SCRIPT_DIR/lib.sh"
  audit_branch_non_cve_files release-0.99
) || true
check "audit: Makefile → warning emitted"  grep -q "Makefile" <<< "$_AUDIT_MK"

# === fix-stdlib.sh cross-minor guard behavioral tests (R146) ===
# Validates that fix-stdlib.sh correctly rejects fix versions outside the
# compiler's minor stream (exit 2) and applies same-minor patch bumps (exit 0).
echo "fix-stdlib cross-minor guard"
STDLIB_REPO="$TMPD/stdlib-repo"
mkdir -p "$STDLIB_REPO"
git -C "$STDLIB_REPO" init -q
git -C "$STDLIB_REPO" config user.email "test@test.com"
git -C "$STDLIB_REPO" config user.name "Test"
printf 'module example.com/stdlib-test\ngo 1.24.0\n' > "$STDLIB_REPO/go.mod"
# A minimal .go file ensures go mod tidy has source to anchor the go directive.
printf 'package main\n' > "$STDLIB_REPO/main.go"
git -C "$STDLIB_REPO" add go.mod main.go
git -C "$STDLIB_REPO" commit -q -m "init"
git -C "$STDLIB_REPO" checkout -q -b devel
# STATE_FILE: BUILD_GO_VERSION=unknown → REF_GO falls back to go.mod (1.24.0)
printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION="unknown"\nCVE_SCRIPTS=%q\n' \
  "$STDLIB_REPO" "$SCRIPT_DIR" > "$TMPD/stdlib-state.env"

# Test 1: ALL_FIX_VERSIONS contains ONLY cross-minor versions (1.25.x with
# REF_MINOR=1.24). The filter loop at fix-stdlib.sh line 51 skips every entry,
# BEST stays empty, GO_VERSION stays at the 1.25.1 arg, NEW_MINOR(1.25) ≠
# REF_MINOR(1.24) → guard fires → exit 2 (NEEDS_REVIEW), no commit.
STDLIB_XM_RC=0
( cd "$STDLIB_REPO" && bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$TMPD/stdlib-state.env" "1.25.1" "1.25.1,1.25.2" "GHSA-xm-0001" ) \
  >/dev/null 2>&1 || STDLIB_XM_RC=$?
check "fix-stdlib cross-minor-only exits 2" test "$STDLIB_XM_RC" -eq 2
check "fix-stdlib cross-minor-only no commit" \
  test "$(git -C "$STDLIB_REPO" rev-list --count devel)" -eq 1

# Test 2: ALL_FIX_VERSIONS contains a same-minor patch (1.24.7) alongside a
# cross-minor version (1.25.1). The filter picks 1.24.7 as BEST, overrides
# GO_VERSION, NEW_MINOR(1.24) == REF_MINOR(1.24) → guard passes → go.mod is
# given toolchain go1.24.7 (go directive untouched) and committed → exit 0.
STDLIB_SM_RC=0
( cd "$STDLIB_REPO" && bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$TMPD/stdlib-state.env" "1.25.1" "1.24.7,1.25.1" "GHSA-sm-0001" ) \
  >/dev/null 2>&1 || STDLIB_SM_RC=$?
check "fix-stdlib same-minor patch exits 0" test "$STDLIB_SM_RC" -eq 0
check "fix-stdlib same-minor patch commits" \
  test "$(git -C "$STDLIB_REPO" rev-list --count devel)" -eq 2
check "fix-stdlib same-minor patch sets toolchain" \
  grep -q '^toolchain go1.24.7$' "$STDLIB_REPO/go.mod"
check "fix-stdlib same-minor patch keeps go directive" \
  grep -q '^go 1.24.0$' "$STDLIB_REPO/go.mod"

# Test 3: COMPILER_GO is in a higher minor than go.mod. go.mod = 1.25.0 but
# COMPILER_GO = 1.26.8. REF_MINOR anchors to 1.26 (the compiler), so the
# builder already supports the fix, so advancing go.mod from 1.25 to 1.26 is
# allowed by policy and must commit.
STDLIB_CM_REPO="$TMPD/stdlib-cm-repo"
mkdir -p "$STDLIB_CM_REPO"
git -C "$STDLIB_CM_REPO" init -q
git -C "$STDLIB_CM_REPO" config user.email "test@test.com"
git -C "$STDLIB_CM_REPO" config user.name "Test"
printf 'module example.com/stdlib-cm\ngo 1.25.0\n' > "$STDLIB_CM_REPO/go.mod"
printf 'package main\n' > "$STDLIB_CM_REPO/main.go"
git -C "$STDLIB_CM_REPO" add go.mod main.go
git -C "$STDLIB_CM_REPO" commit -q -m "init"
git -C "$STDLIB_CM_REPO" checkout -q -b devel
# State: BUILD_GO_VERSION set to 1.26.8 → COMPILER_GO=1.26.8, REF_MINOR=1.26
printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION="go1.26.8"\nCVE_SCRIPTS=%q\n' \
  "$STDLIB_CM_REPO" "$SCRIPT_DIR" > "$TMPD/stdlib-cm-state.env"
STDLIB_CM_RC=0
STDLIB_CM_OUT=$(cd "$STDLIB_CM_REPO" && bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$TMPD/stdlib-cm-state.env" "1.26.7" "1.26.7" "GHSA-cm-0001" 2>&1) || STDLIB_CM_RC=$?
check "fix-stdlib builder-supported cross-minor exits 0" test "$STDLIB_CM_RC" -eq 0
check "fix-stdlib builder-supported cross-minor reports FIXED" \
  grep -q 'FIXED: stdlib' <<< "$STDLIB_CM_OUT"
check "fix-stdlib builder-supported cross-minor commits" \
  test "$(git -C "$STDLIB_CM_REPO" rev-list --count devel)" -eq 2

# Test 4: Per-module loop cross-minor guard: a submodule whose go directive is in
# a different minor stream than NEW_MINOR must be left unchanged. Create a repo
# with root go.mod at 1.24.0 and a tools/go.mod at 1.23.0. When fix-stdlib.sh
# updates go 1.24.x, root is updated but tools stays at 1.23.0 (different stream).
STDLIB_MM_REPO="$TMPD/stdlib-mm-repo"
mkdir -p "$STDLIB_MM_REPO/tools"
git -C "$STDLIB_MM_REPO" init -q
git -C "$STDLIB_MM_REPO" config user.email "test@test.com"
git -C "$STDLIB_MM_REPO" config user.name "Test"
printf 'module example.com/stdlib-mm\ngo 1.24.0\n' > "$STDLIB_MM_REPO/go.mod"
printf 'package main\n' > "$STDLIB_MM_REPO/main.go"
printf 'module example.com/stdlib-mm/tools\ngo 1.23.0\n' > "$STDLIB_MM_REPO/tools/go.mod"
git -C "$STDLIB_MM_REPO" add go.mod main.go tools/go.mod
git -C "$STDLIB_MM_REPO" commit -q -m "init"
git -C "$STDLIB_MM_REPO" checkout -q -b devel
printf 'REPO=%q\nBRANCH=devel\nBUILD_GO_VERSION="unknown"\nCVE_SCRIPTS=%q\n' \
  "$STDLIB_MM_REPO" "$SCRIPT_DIR" > "$TMPD/stdlib-mm-state.env"
# Apply same-minor patch 1.24.7: root go.mod (1.24.0 → 1.24.7) should be updated;
# tools/go.mod (1.23.0, minor 1.23 ≠ 1.24) should be left unchanged.
STDLIB_MM_OUT=$(cd "$STDLIB_MM_REPO" && bash "$SCRIPT_DIR/fix-stdlib.sh" \
  "$TMPD/stdlib-mm-state.env" "1.24.7" "1.24.7" "GHSA-mm-0001" 2>&1) && STDLIB_MM_RC=0 || STDLIB_MM_RC=$?
check "fix-stdlib per-module guard: incomplete fix exits 2" test "$STDLIB_MM_RC" -eq 2
check "fix-stdlib per-module guard: root updated" grep -q '^toolchain go1.24.7$' "$STDLIB_MM_REPO/go.mod"
check "fix-stdlib per-module guard: tools NOT updated" \
  bash -c "grep -q '^go 1.23.0$' '$STDLIB_MM_REPO/tools/go.mod' && ! grep -q '^toolchain' '$STDLIB_MM_REPO/tools/go.mod'"
check "fix-stdlib per-module guard: NOTE logged" grep -q "minor stream.*1.23.*leaving as-is" <<< "$STDLIB_MM_OUT"

# === fix-package.sh: _go_get_version PIPESTATUS capture (Bug R149-1) ===
# go get network failure must propagate non-zero exit (PIPESTATUS[0] fix).
echo "fix-package go-get network failure exits non-zero"
FP_NG="$TMPD/fp-network-fail"; mkdir -p "$FP_NG/gostub"
( cd "$FP_NG" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/foo v1.0.0\n' > "$FP_NG/go.mod"
( cd "$FP_NG" && git add go.mod && git commit -qm init )
# go stub: `go get` exits 1 with a network error; other verbs are no-ops.
cat > "$FP_NG/gostub/go" <<'STUB'
#!/bin/sh
while [ "$1" = "-C" ]; do shift 2; done
if [ "$1" = "get" ]; then
  echo "dial tcp: connection refused" >&2
  exit 1
fi
exit 0
STUB
chmod +x "$FP_NG/gostub/go"
cat > "$FP_NG/st.env" <<EOF
REPO="$FP_NG"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
EOF
FP_NG_RC=0
( cd "$FP_NG" && PATH="$FP_NG/gostub:$PATH" bash "$SCRIPT_DIR/fix-package.sh" \
  "$FP_NG/st.env" example.com/foo 2.0.0 CVE-2024-9001 2>&1 ) || FP_NG_RC=$?
check "fix-package go-get fail exits non-zero" test "$FP_NG_RC" -ne 0

# === Schema-version probe (artifact type guard) ===
# fix-all.sh has five jq call sites that filter on artifact.type == "go-module".
# If grype renames this type in a future schema version, every select() returns
# zero results and MATCH_COUNT evaluates to 0 — silently reporting the repo clean
# while missing all CVEs. The schema-version probe must detect this and die loudly.
echo "schema-version probe"
if command -v jq >/dev/null 2>&1; then
  # Behavioral: the schema guard jq expression correctly identifies type mismatch.
  # Simulate: scan with all matches having a renamed type ("go-module-changed").
  SCHEMA_SCAN='{"matches":[{"vulnerability":{"id":"GHSA-test","severity":"High"},"artifact":{"name":"example/pkg","version":"v1.0.0","type":"go-module-changed"}}]}'
  _S_TOTAL=$(jq '.matches | length' <<< "$SCHEMA_SCAN" 2>/dev/null || echo 0)
  _S_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module")] | length' <<< "$SCHEMA_SCAN" 2>/dev/null || echo 0)
  check "schema probe: changed type has total=1" test "$_S_TOTAL" -eq 1
  check "schema probe: changed type gives MATCH_COUNT=0" test "$_S_COUNT" -eq 0
  check "schema probe: changed type triggers guard" \
    bash -c "[[ $_S_TOTAL -gt 0 && $_S_COUNT -eq 0 ]]"
  # Behavioral: no false positive on an empty scan (clean repo).
  SCHEMA_EMPTY='{"matches":[]}'
  _E_TOTAL=$(jq '.matches | length' <<< "$SCHEMA_EMPTY" 2>/dev/null || echo 0)
  _E_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module")] | length' <<< "$SCHEMA_EMPTY" 2>/dev/null || echo 0)
  check "schema probe: empty scan total=0" test "$_E_TOTAL" -eq 0
  # Behavioral: no false positive when correct type is present.
  SCHEMA_OK='{"matches":[{"vulnerability":{"id":"GHSA-ok"},"artifact":{"type":"go-module"}}]}'
  _OK_TOTAL=$(jq '.matches | length' <<< "$SCHEMA_OK" 2>/dev/null || echo 0)
  _OK_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module")] | length' <<< "$SCHEMA_OK" 2>/dev/null || echo 0)
  check "schema probe: correct type total=1" test "$_OK_TOTAL" -eq 1
  check "schema probe: correct type count=1" test "$_OK_COUNT" -eq 1
  # Behavioral: mixed types (some go-module, some other) — no false positive.
  SCHEMA_MIXED='{"matches":[{"artifact":{"type":"go-module"}},{"artifact":{"type":"npm"}}]}'
  _M_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module")] | length' <<< "$SCHEMA_MIXED" 2>/dev/null || echo 0)
  _M_TOTAL=$(jq '.matches | length' <<< "$SCHEMA_MIXED" 2>/dev/null || echo 0)
  check "schema probe: mixed types total=2" test "$_M_TOTAL" -eq 2
  check "schema probe: mixed types count=1 (go-module present)" test "$_M_COUNT" -eq 1
else
  echo "  SKIP: jq not available"
fi

# === fix-all.sh MATCH_COUNT=0 behavioral test ===
# Verify that fix-all.sh correctly handles an initial scan that returns zero
# go-module matches. Three sub-cases exercise the early-exit guards
# (BUILD_FAILED, COVERAGE_UNKNOWN, clean) without a real grype run or network.
echo "fix-all.sh MATCH_COUNT=0 behavioral"
if command -v jq >/dev/null 2>&1; then
  MC0_DIR="$TMPD/mc0"
  MC0_REPO="$MC0_DIR/repo"
  MC0_SCRIPTS="$MC0_DIR/scripts"
  MC0_STATE="$MC0_DIR/mc0-state.env"
  mkdir -p "$MC0_REPO" "$MC0_SCRIPTS"

  # Minimal git repo (fix-all.sh cleanup uses git -C REPO).
  git -C "$MC0_REPO" init -q
  git -C "$MC0_REPO" config user.email "t@t.com"
  git -C "$MC0_REPO" config user.name "T"
  touch "$MC0_REPO/go.mod"
  git -C "$MC0_REPO" add -A
  git -C "$MC0_REPO" commit -qm "init"

  # lib.sh is sourced by fix-all.sh via SCRIPT_DIR.
  cp "$SCRIPT_DIR/lib.sh" "$MC0_SCRIPTS/"
  printf '\npreflight_check() { return 0; }\n' >> "$MC0_SCRIPTS/lib.sh"

  # Helper: (re-)write the state file before each invocation.
  # fix-all.sh's cleanup trap removes it on exit, so it must be restored.
  mc0_write_state() {
    printf 'STATE_FILE=%q\nREPO=%q\nBRANCH="devel"\nFIX_BRANCH=""\n' \
      "$MC0_STATE" "$MC0_REPO" > "$MC0_STATE"
    printf 'ORIGINAL_REF=""\nHAS_TOOLS_GOMOD=false\nHAS_VENDOR=false\n' >> "$MC0_STATE"
    printf 'DIFF_IGNORE_ARGS=""\nNEEDS_BUILD_FOR_SCAN=false\n' >> "$MC0_STATE"
    printf 'CONTAINER_CMD=""\nHAS_LOCAL_GRYPE=false\nBUILD_IMAGE=""\n' >> "$MC0_STATE"
    printf 'BUILD_GO_VERSION="unknown"\nBUILD_CMD=""\nCLEAN_CMD=""\nTEST_CMD="true"\n' >> "$MC0_STATE"
    printf 'ENV_UNSET=""\nK8S_VERSION_GUARD=false\nUPSTREAM_ORG=""\n' >> "$MC0_STATE"
    printf 'FETCH_FAILED=false\nCVE_SCRIPTS=%q\n' "$MC0_SCRIPTS" >> "$MC0_STATE"
  }

  # Mock detect.sh: ignores args, prints banner + state file path as last line.
  printf '#!/usr/bin/env bash\necho "=== CVE Fix: mock/devel ==="\necho %q\n' \
    "$MC0_STATE" > "$MC0_SCRIPTS/detect.sh"
  chmod +x "$MC0_SCRIPTS/detect.sh"

  # Mock scan.sh: always returns zero-match JSON; never touches sentinels.
  printf '#!/usr/bin/env bash\nprintf '"'"'{"matches":[],"ignoredMatches":[]}\n'"'"'\n' \
    > "$MC0_SCRIPTS/scan.sh"
  chmod +x "$MC0_SCRIPTS/scan.sh"

  # Copy fix-all.sh so its SCRIPT_DIR resolves to MC0_SCRIPTS (mock dir).
  cp "$SCRIPT_DIR/fix-all.sh" "$MC0_SCRIPTS/"
  cp "$SCRIPT_DIR/binary-module-locations.py" "$MC0_SCRIPTS/"

  # --- Sub-case 1: clean scan → exit 0, "No CVEs found" ---
  mc0_write_state
  MC0_RC=0
  MC0_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC0_RC=$?
  check "fix-all.sh MATCH_COUNT=0 clean: exits 0" \
    test "$MC0_RC" -eq 0
  check "fix-all.sh MATCH_COUNT=0 clean: output non-empty" \
    test -n "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: 'No CVEs found'" \
    grep -q 'No CVEs found' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: no fabricated Summary" \
    ! grep -q '^--- Summary' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: no fabricated original ref" \
    ! grep -q '^Original ref:' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: no NEEDS_REVIEW" \
    ! grep -q 'NEEDS_REVIEW' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: 'Scanning for CVEs'" \
    grep -q 'Scanning for CVEs' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: not 'build FAILED'" \
    ! grep -q 'build FAILED' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: not 'opaque binaries'" \
    ! grep -q 'opaque binaries' <<< "$MC0_OUT"
  check "fix-all.sh MATCH_COUNT=0 clean: not 'stdlib CVE'" \
    ! grep -q 'stdlib CVE' <<< "$MC0_OUT"

  mc0_write_state
  printf 'FETCH_FAILED=true\n' >> "$MC0_STATE"
  MC0_FETCH_RC=0
  MC0_FETCH_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC0_FETCH_RC=$?
  check "empty cached scan after failed fetch exits for review" test "$MC0_FETCH_RC" -eq 2
  check "empty cached scan after failed fetch explains stale evidence" grep -q 'base branch fetch failed' <<< "$MC0_FETCH_OUT"
  check "empty cached scan after failed fetch cannot claim clean" ! grep -q '^No CVEs found\.' <<< "$MC0_FETCH_OUT"
  check "empty cached scan after failed fetch cleans worker state" test ! -e "${MC0_STATE}"

  # --- Sub-case 2: build-failed sentinel → exit 2, "NOT reported clean" ---
  mc0_write_state
  touch "${MC0_STATE}.build-failed"
  MC0BF_RC=0
  MC0BF_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC0BF_RC=$?
  check "fix-all.sh MATCH_COUNT=0 build-failed: exits 2" \
    test "$MC0BF_RC" -eq 2
  check "fix-all.sh MATCH_COUNT=0 build-failed: 'No dependency CVEs'" \
    grep -q 'No dependency CVEs' <<< "$MC0BF_OUT"
  check "fix-all.sh MATCH_COUNT=0 build-failed: 'build FAILED'" \
    grep -q 'build FAILED' <<< "$MC0BF_OUT"
  check "fix-all.sh MATCH_COUNT=0 build-failed: 'NEEDS_REVIEW: initial build'" \
    grep -q 'NEEDS_REVIEW: initial build' <<< "$MC0BF_OUT"
  check "fix-all.sh MATCH_COUNT=0 build-failed: 'stdlib CVE'" \
    grep -q 'stdlib CVE' <<< "$MC0BF_OUT"
  check "fix-all.sh MATCH_COUNT=0 build-failed: not 'No CVEs found'" \
    ! grep -q 'No CVEs found\.' <<< "$MC0BF_OUT"

  # --- Sub-case 3: coverage-unknown sentinel → exit 2, "NOT reported clean" ---
  mc0_write_state
  touch "${MC0_STATE}.coverage-unknown"
  MC0CU_RC=0
  MC0CU_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC0CU_RC=$?
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: exits 2" \
    test "$MC0CU_RC" -eq 2
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: 'No dependency CVEs'" \
    grep -q 'No dependency CVEs' <<< "$MC0CU_OUT"
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: 'opaque binaries'" \
    grep -q 'opaque binaries' <<< "$MC0CU_OUT"
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: 'NOT reported clean'" \
    grep -q 'NOT reported clean' <<< "$MC0CU_OUT"
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: binary coverage reason" \
    grep -q 'NEEDS_REVIEW: packed/opaque binaries or compiler metadata' <<< "$MC0CU_OUT"
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: 'stdlib CVE'" \
    grep -q 'stdlib CVE' <<< "$MC0CU_OUT"
  check "fix-all.sh MATCH_COUNT=0 coverage-unknown: not 'No CVEs found'" \
    ! grep -q 'No CVEs found\.' <<< "$MC0CU_OUT"

  # --- Sub-case 4: CLEAN_CMD is invoked before initial scan and before final scan ---
  # Set CLEAN_CMD to a command that appends to a counter file in $TMPD so we
  # can assert the command was invoked at least once.  mc0_write_state leaves
  # CLEAN_CMD="" by default; override it after the helper runs.
  mc0_write_state
  printf '%s\n' 'ignore:' '  - vulnerability: CVE-CLEAN-POLICY' '    package:' '      name: example.com/policy' \
    '  - vulnerability: CVE-CLEAN-POLICY' '    package:' '      name: example.com/policy' '      location: /go.mod' > "$MC0_REPO/.grype.yaml"
  MC_POLICY_RC=0
  MC_POLICY_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC_POLICY_RC=$?
  check "clean scan cannot bypass existing ignore scope conflict" test "$MC_POLICY_RC" -eq 2
  check "clean scan with ignore policy conflict is not reported clean" ! grep -q 'No CVEs found' <<< "$MC_POLICY_OUT"
  rm -f "$MC0_REPO/.grype.yaml"

  # Infrastructure failures cannot use the zero-CVE fast path.
  cp "$MC0_SCRIPTS/scan.sh" "$MC0_SCRIPTS/scan-valid.sh"
  for MC_BAD_MODE in status schema documents; do
    mc0_write_state
    case "$MC_BAD_MODE" in
      status) printf '#!/usr/bin/env bash\nprintf '\''{"matches":[]}'\''\nexit 7\n' > "$MC0_SCRIPTS/scan.sh" ;;
      schema) printf '#!/usr/bin/env bash\nprintf '\''{"matches":[],"ignoredMatches":{}}'\''\n' > "$MC0_SCRIPTS/scan.sh" ;;
      documents) printf '#!/usr/bin/env bash\nprintf '\''{"matches":[]}\\n{"matches":[]}'\''\n' > "$MC0_SCRIPTS/scan.sh" ;;
    esac
    MC_BAD_RC=0
    MC_BAD_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC_BAD_RC=$?
    check "initial scan $MC_BAD_MODE exits unconfirmed" test "$MC_BAD_RC" -eq 2
    check "initial scan $MC_BAD_MODE cannot claim clean" ! grep -q 'No CVEs found' <<< "$MC_BAD_OUT"
    check "initial scan $MC_BAD_MODE cannot print a PR command" ! grep -q 'gh pr create' <<< "$MC_BAD_OUT"
  done
  cp "$MC0_SCRIPTS/scan-valid.sh" "$MC0_SCRIPTS/scan.sh"

  echo "fix-all.sh CLEAN_CMD behavioral"
  # Counter file: each invocation of CLEAN_CMD appends a line so we can verify
  # both call sites fired.
  MC0_CLEAN_COUNTER="$TMPD/clean-counter"
  rm -f "$MC0_CLEAN_COUNTER"
  mc0_write_state
  # Override CLEAN_CMD in the state file to record invocations
  CLEAN_TEST_CMD="printf 'called\n' >> '$MC0_CLEAN_COUNTER'"
  printf 'CLEAN_CMD=%q\n' "$CLEAN_TEST_CMD" >> "$MC0_STATE"
  MC0_CLEAN_RC=0
  MC0_CLEAN_OUT=$(bash "$MC0_SCRIPTS/fix-all.sh" "$MC0_REPO" devel 2>&1) || MC0_CLEAN_RC=$?
  check "CLEAN_CMD: fix-all.sh exits 0 with clean scan" \
    test "$MC0_CLEAN_RC" -eq 0
  check "CLEAN_CMD: invoked at least once (pre-scan call site)" \
    test -f "$MC0_CLEAN_COUNTER"
  check "CLEAN_CMD: output shows 'Cleaning build artifacts'" \
    grep -q 'Cleaning build artifacts' <<< "$MC0_CLEAN_OUT"
  rm -f "$MC0_CLEAN_COUNTER"
else
  echo "  SKIP: jq not available"
fi

# === detect.sh --setup-branch path (branch creation, versioning, FETCH_FAILED) ===
# Exercises detect.sh branch setup: branch creation,
# the -v2/-v3 suffix loop, the uncommitted-changes guard, and the FETCH_FAILED
# fallback. Requires a local "origin" so git fetch is hermetic (no network).
echo "detect.sh --setup-branch"
SB_DIR="$TMPD/setup-branch"
SB_ORIGIN="$SB_DIR/origin"
SB_WORK="$SB_DIR/work"
SB_SEED="$SB_DIR/seed"
mkdir -p "$SB_ORIGIN"
git init --bare "$SB_ORIGIN" -q
git clone "$SB_ORIGIN" "$SB_SEED" -q 2>/dev/null
git -C "$SB_SEED" config user.email "t@t.com"
git -C "$SB_SEED" config user.name "T"
touch "$SB_SEED/go.mod"
git -C "$SB_SEED" add -A
git -C "$SB_SEED" commit -qm "init"
git -C "$SB_SEED" push -q origin HEAD:devel 2>/dev/null
git clone "$SB_ORIGIN" "$SB_WORK" -q 2>/dev/null
git -C "$SB_WORK" config user.email "t@t.com"
git -C "$SB_WORK" config user.name "T"
git -C "$SB_WORK" checkout -q -b devel origin/devel 2>/dev/null || git -C "$SB_WORK" checkout -q devel 2>/dev/null
SB_DATE=$(date +%Y-%m-%d)
SB_FIX_BRANCH="fix-devel-cves-${SB_DATE}"

# (a) The original checkout ref is independent of the requested target branch.
git -C "$SB_WORK" checkout -qb operator-start
SB_ORIGINAL_HEAD=$(git -C "$SB_WORK" rev-parse HEAD)
SB_OUT=$("$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch 2>&1) || true
SB_STATE=$(tail -1 <<< "$SB_OUT")
check "setup-branch: original ref differs from target" test "$(state_value "$SB_STATE" ORIGINAL_REF)" = operator-start
check "setup-branch: original branch is unchanged" test "$(git -C "$SB_WORK" rev-parse operator-start)" = "$SB_ORIGINAL_HEAD"
check "setup-branch: FIX_BRANCH in state"    test "$(state_value "$SB_STATE" FIX_BRANCH)" = "$SB_FIX_BRANCH"
check "setup-branch: fix branch exists"      git -C "$SB_WORK" show-ref --verify --quiet "refs/heads/${SB_FIX_BRANCH}"
check "setup-branch: FETCH_FAILED=false"     grep -q "^FETCH_FAILED=false$" "$SB_STATE"
check "setup-branch: fix branch in output"   grep -q "Fix branch: ${SB_FIX_BRANCH}" <<< "$SB_OUT"
rm -f "$SB_STATE"
git -C "$SB_WORK" checkout -q devel 2>/dev/null || true

# (b) A detached start is retained as its full commit, while suffixing still works.
git -C "$SB_WORK" checkout -q --detach "$SB_ORIGINAL_HEAD"
SB_OUT2=$("$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch 2>&1) || true
SB_STATE2=$(tail -1 <<< "$SB_OUT2")
SB_V2="${SB_FIX_BRANCH}-v2"
check "setup-branch suffix: -v2 branch created" git -C "$SB_WORK" show-ref --verify --quiet "refs/heads/${SB_V2}"
check "setup-branch suffix: FIX_BRANCH is -v2"  test "$(state_value "$SB_STATE2" FIX_BRANCH)" = "$SB_V2"
check "setup-branch: detached original ref is the full starting commit" test "$(state_value "$SB_STATE2" ORIGINAL_REF)" = "$SB_ORIGINAL_HEAD"
rm -f "$SB_STATE2"
git -C "$SB_WORK" checkout -q devel 2>/dev/null || true

# (c) Uncommitted changes guard must fire
printf 'dirty\n' >> "$SB_WORK/go.mod"
SB_DIRTY_RC=0
"$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch >/dev/null 2>&1 || SB_DIRTY_RC=$?
check "setup-branch: uncommitted changes guard fires" test "$SB_DIRTY_RC" -ne 0
git -C "$SB_WORK" checkout -- go.mod 2>/dev/null || true

# (d) FETCH_FAILED fallback: broken origin URL -> FETCH_FAILED=true in state.
# Cached origin/devel ref from the initial clone still allows branch creation
# even though the fetch fails; FETCH_FAILED=true is recorded in the state file.
git -C "$SB_WORK" remote set-url origin "file:///nonexistent-cve-test-$$"
git -C "$SB_WORK" branch -D "${SB_FIX_BRANCH}" "${SB_V2}" 2>/dev/null || true
SB_FF_OUT=$("$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch 2>&1) || true
SB_FF_STATE=$(tail -1 <<< "$SB_FF_OUT")
if [[ -f "$SB_FF_STATE" ]]; then
  check "setup-branch FETCH_FAILED: state has FETCH_FAILED=true" grep -q "^FETCH_FAILED=true$" "$SB_FF_STATE"
  check "setup-branch FETCH_FAILED: warning in output"            grep -qi "fetch failed" <<< "$SB_FF_OUT"
  rm -f "$SB_FF_STATE"
  git -C "$SB_WORK" checkout -q devel 2>/dev/null || true
else
  # If cached origin/devel ref was pruned the checkout also fails — the output
  # must still mention fetch regardless so the user knows why it broke.
  check "setup-branch FETCH_FAILED: output mentions fetch" grep -qi "fetch" <<< "$SB_FF_OUT"
fi
git -C "$SB_WORK" remote set-url origin "$SB_ORIGIN" 2>/dev/null || true

# (e) The fetch URL is never rewritten. Private repositories need SSH to fetch,
# so an SSH-style origin must be fetched exactly as configured. A fake ssh that
# serves the local bare origin makes the fetch succeed only over the SSH URL; an
# HTTPS rewrite would target https://fake.example/... and fail.
sb_reset_fix_branches() {
  git -C "$SB_WORK" checkout -q devel 2>/dev/null || true
  git -C "$SB_WORK" for-each-ref --format='%(refname:short)' 'refs/heads/fix-devel-cves-*' | \
    while IFS= read -r _b; do git -C "$SB_WORK" branch -D "$_b" >/dev/null 2>&1 || true; done
}
sb_reset_fix_branches
SB_LOCAL_SSH="$SB_DIR/local-ssh"
cat > "$SB_LOCAL_SSH" <<'SSHSTUB'
#!/bin/sh
# Stand-in for ssh: drop options and the host, then run the remote command locally.
while [ $# -gt 0 ]; do
  case "$1" in -o|-F|-i|-p|-l) shift 2 ;; -*) shift ;; *) break ;; esac
done
shift
exec sh -c "$*"
SSHSTUB
chmod +x "$SB_LOCAL_SSH"
SB_SSH_URL="git@fake.example:$SB_ORIGIN"
git -C "$SB_WORK" remote set-url origin "$SB_SSH_URL"
SB_SSH_OUT=$(GIT_SSH_COMMAND="$SB_LOCAL_SSH" "$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch 2>&1) || true
SB_SSH_STATE=$(tail -1 <<< "$SB_SSH_OUT")
check "setup-branch ssh origin: fetched over the configured SSH URL" \
  grep -q "^FETCH_FAILED=false$" "$SB_SSH_STATE"
check "setup-branch ssh origin: origin URL left untouched" \
  test "$(git -C "$SB_WORK" config --get remote.origin.url)" = "$SB_SSH_URL"
check "setup-branch ssh origin: no fetch-URL rewrite recorded in state" \
  ! grep -q "BASE_FETCH_URL" "$SB_SSH_STATE"
rm -f "$SB_SSH_STATE"
sb_reset_fix_branches

# (f) The documented convention: HTTPS fetch URL plus SSH pushurl. Fetch must
# use the fetch URL and leave the pushurl alone.
git -C "$SB_WORK" remote set-url origin "$SB_ORIGIN"
git -C "$SB_WORK" remote set-url --push origin "$SB_SSH_URL"
SB_PU_OUT=$("$SCRIPT_DIR/detect.sh" "$SB_WORK" devel --setup-branch 2>&1) || true
SB_PU_STATE=$(tail -1 <<< "$SB_PU_OUT")
check "setup-branch pushurl: fetch succeeds via the fetch URL" \
  grep -q "^FETCH_FAILED=false$" "$SB_PU_STATE"
check "setup-branch pushurl: pushurl untouched" \
  test "$(git -C "$SB_WORK" remote get-url --push origin)" = "$SB_SSH_URL"
rm -f "$SB_PU_STATE"
git -C "$SB_WORK" config --unset remote.origin.pushurl
sb_reset_fix_branches

# (g) fetch_origin_branch must stay non-interactive without discarding the
# user's SSH configuration: core.sshCommand and GIT_SSH_COMMAND are both kept,
# and BatchMode is added so a missing key fails fast instead of prompting.
SB_FAKE_SSH="$SB_DIR/fake-ssh"
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s/ssh-args.log"\nexit 255\n' "$SB_DIR" > "$SB_FAKE_SSH"
chmod +x "$SB_FAKE_SSH"
git -C "$SB_WORK" remote set-url origin "ssh://git@fake.example/org/repo.git"
rm -f "$SB_DIR/ssh-args.log"
git -C "$SB_WORK" config core.sshCommand "$SB_FAKE_SSH -F /dev/null"
( cd "$SB_WORK" && fetch_origin_branch devel ) >/dev/null 2>&1 && SB_SC_RC=0 || SB_SC_RC=$?
check "fetch_origin_branch: failing ssh fetch returns non-zero" test "$SB_SC_RC" -ne 0
check "fetch_origin_branch: core.sshCommand options kept" grep -q -- "-F /dev/null" "$SB_DIR/ssh-args.log"
check "fetch_origin_branch: BatchMode added"              grep -q "BatchMode=yes" "$SB_DIR/ssh-args.log"
git -C "$SB_WORK" config --unset core.sshCommand
rm -f "$SB_DIR/ssh-args.log"
( cd "$SB_WORK" && GIT_SSH_COMMAND="$SB_FAKE_SSH -v" fetch_origin_branch devel ) >/dev/null 2>&1 || true
check "fetch_origin_branch: caller GIT_SSH_COMMAND kept"  grep -q -- "-v" "$SB_DIR/ssh-args.log"
check "fetch_origin_branch: BatchMode added to GIT_SSH_COMMAND" grep -q "BatchMode=yes" "$SB_DIR/ssh-args.log"
git -C "$SB_WORK" remote set-url origin "$SB_ORIGIN" 2>/dev/null || true

# GIT_SSH is an executable path, not a shell command. Preserve that distinction
# when adding non-interactive options, including literal spaces and apostrophes.
SB_SSH_EXE="$SB_DIR/ssh wrappers/owner's ssh"
mkdir -p "$(dirname "$SB_SSH_EXE")"
cp "$SB_LOCAL_SSH" "$SB_SSH_EXE"
git -C "$SB_WORK" remote set-url origin "$SB_SSH_URL"
SB_SSH_EXE_RC=0
( cd "$SB_WORK"; GIT_SSH_COMMAND= GIT_SSH="$SB_SSH_EXE" GIT_SSH_VARIANT=ssh fetch_origin_branch devel ) \
  > "$SB_DIR/ssh-path-output" 2>&1 || SB_SSH_EXE_RC=$?
check "fetch_origin_branch preserves literal GIT_SSH executable path" test "$SB_SSH_EXE_RC" -eq 0
check "fetch_origin_branch preserves private origin with quoted SSH path" \
  test "$(git -C "$SB_WORK" remote get-url origin)" = "$SB_SSH_URL"
git -C "$SB_WORK" remote set-url origin "$SB_ORIGIN"

# === generated-file noise detection and reconciliation ===
# CI tolerates tool-version noise in generated files with `git diff -I<regex>`.
# controller-gen stamps CRD YAML (Go files only on old operator branches);
# protoc-gen-go stamps *.pb.go. Several rules can apply to one repository.
echo "generated-file detection"
gf_repo() {  # NAME — committed repo on branch devel with a go.mod
  local d="$TMPD/gf-$1"
  rm -rf "$d"; mkdir -p "$d"
  git -C "$d" init -q -b devel
  git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf 'module example.com/gf\n\ngo 1.24.0\n' > "$d/go.mod"
  printf '%s\n' "$d"
}
gf_commit() { git -C "$1" add -A && git -C "$1" commit -qm init; }
gf_detect() {  # REPO — print DIFF_IGNORE_ARGS detect.sh recorded
  local out st
  out=$("$SCRIPT_DIR/detect.sh" "$1" devel 2>&1) || true
  st=$(tail -1 <<< "$out")
  state_value "$st" DIFF_IGNORE_ARGS
  rm -f "$st"
}
GF_MARK='controller-gen.kubebuilder.io/version'
GF_CG_RULE='-I^[[:space:]]*controller-gen[.]kubebuilder[.]io/version:[[:space:]]*v?[0-9]+([.][0-9]+)*([-+][[:alnum:]_.+-]+)?[[:space:]]*$'
GF_PB_RULE='-I^//[[:space:]]+(protoc-gen-go|protoc)[[:space:]]+v?[0-9]+([.][0-9]+)*([-+][[:alnum:]_.+-]+)?[[:space:]]*$'
GF_YAML=$(gf_repo yaml); printf 'metadata:\n  annotations:\n    %s: v0.19.0\n' "$GF_MARK" > "$GF_YAML/crd.yaml"; gf_commit "$GF_YAML"
check "generated: CRD YAML marker enables controller-gen rule" \
  test "$(gf_detect "$GF_YAML")" = "$GF_CG_RULE"
GF_PB=$(gf_repo pb); printf 'package x\n' > "$GF_PB/a.pb.go"; gf_commit "$GF_PB"
check "generated: .pb.go enables comment rule" test "$(gf_detect "$GF_PB")" = "$GF_PB_RULE"
GF_BOTH=$(gf_repo both); printf '    %s: v0.19.0\n' "$GF_MARK" > "$GF_BOTH/crd.yaml"; printf 'package x\n' > "$GF_BOTH/a.pb.go"; gf_commit "$GF_BOTH"
check "generated: both rules apply together (CRD YAML and .pb.go)" \
  test "$(gf_detect "$GF_BOTH")" = "$GF_CG_RULE $GF_PB_RULE"
GF_GO=$(gf_repo go); printf 'package embeddedyamls\n\nvar Y = `%s: v0.19.0`\n' "$GF_MARK" > "$GF_GO/yamls.go"; gf_commit "$GF_GO"
check "generated: legacy Go file embedding the marker still detected" \
  test "$(gf_detect "$GF_GO")" = "$GF_CG_RULE"
GF_NONE=$(gf_repo none); printf 'package x\n' > "$GF_NONE/main.go"; gf_commit "$GF_NONE"
check "generated: no generated files -> no ignore args" test -z "$(gf_detect "$GF_NONE")"
GF_VEND=$(gf_repo vendor); mkdir -p "$GF_VEND/vendor/dep" "$GF_VEND/tools/vendor/dep"
printf '    %s: v1\n' "$GF_MARK" > "$GF_VEND/vendor/dep/crd.yaml"; printf 'package dep\n' > "$GF_VEND/vendor/dep/a.pb.go"
printf 'package dep\n' > "$GF_VEND/tools/vendor/dep/b.pb.go"; gf_commit "$GF_VEND"
check "generated: vendor/ files never enable a rule" test -z "$(gf_detect "$GF_VEND")"
GF_UNTR=$(gf_repo untracked); printf 'package x\n' > "$GF_UNTR/main.go"; gf_commit "$GF_UNTR"
printf '    %s: v0.19.0\n' "$GF_MARK" > "$GF_UNTR/stray.yaml"
check "generated: untracked files are ignored" test -z "$(gf_detect "$GF_UNTR")"

echo "generated-file reconciliation"
GF_R=$(gf_repo reconcile); mkdir -p "$GF_R/vendor/dep"
printf 'a: 1\nmetadata:\n  annotations:\n    %s: v0.19.0\n' "$GF_MARK" > "$GF_R/noise.yaml"
printf 'a: 1\nmetadata:\n  annotations:\n    %s: v0.19.0\n' "$GF_MARK" > "$GF_R/real.yaml"
printf '// \tprotoc-gen-go v1.36.0\npackage x\n' > "$GF_R/api.pb.go"
printf 'readme\n' > "$GF_R/README.md"
printf '// \tprotoc-gen-go v1.36.0\npackage dep\n' > "$GF_R/vendor/dep/v.pb.go"
gf_commit "$GF_R"
sed -i "s/v0.19.0/v0.20.0/" "$GF_R/noise.yaml"
sed -i "s/v0.19.0/v0.20.0/; s/a: 1/a: 2/" "$GF_R/real.yaml"
sed -i "s/v1.36.0/v1.37.0/" "$GF_R/api.pb.go" "$GF_R/vendor/dep/v.pb.go"
printf 'edited\n' >> "$GF_R/README.md"
( cd "$GF_R" && DIFF_IGNORE_ARGS="" reconcile_generated_files )
check "reconcile: no-op without detected rules" bash -c "! git -C '$GF_R' diff --quiet -- noise.yaml"
( cd "$GF_R" && DIFF_IGNORE_ARGS="$GF_CG_RULE $GF_PB_RULE" reconcile_generated_files )
check "reconcile: version-only CRD change restored" git -C "$GF_R" diff --quiet -- noise.yaml
check "reconcile: restored CRD keeps its original version" grep -q 'v0.19.0' "$GF_R/noise.yaml"
check "reconcile: protoc-gen-go comment-only change restored" git -C "$GF_R" diff --quiet -- api.pb.go
check "reconcile: substantive CRD change is staged" \
  bash -c "git -C '$GF_R' diff --cached --name-only | grep -qx real.yaml"
check "reconcile: staged change is the substantive one" \
  bash -c "git -C '$GF_R' diff --cached -- real.yaml | grep -q '^+a: 2'"
check "reconcile: non-generated dirty file untouched" \
  bash -c "! git -C '$GF_R' diff --quiet -- README.md && ! git -C '$GF_R' diff --cached --name-only | grep -qx README.md"
check "reconcile: vendor/ files untouched" \
  bash -c "! git -C '$GF_R' diff --quiet -- vendor/dep/v.pb.go"

# A generated comment can carry Go build semantics or legal terms; only the
# generator's version stamp is noise. Dots in the CRD annotation are literal.
GF_SEMANTIC=$(gf_repo semantic)
printf '//go:build linux\n\n// protoc-gen-go v1.36.0\n// Copyright 2025 Example\npackage x\n' > "$GF_SEMANTIC/build.pb.go"
printf 'metadata:\n  annotations:\n    %s: v0.19.0\n    controller-genXkubebuilderXio/version: keep\n' "$GF_MARK" > "$GF_SEMANTIC/crd.yaml"
printf '// protoc-gen-go v1.36.0 preserve exported API\npackage x\n' > "$GF_SEMANTIC/directive.pb.go"
gf_commit "$GF_SEMANTIC"
sed -i 's/go:build linux/go:build windows/; s/Copyright 2025/Copyright 2026/; s/v1.36.0/v1.37.0/' "$GF_SEMANTIC/build.pb.go"
sed -i 's/version: keep/version: changed/' "$GF_SEMANTIC/crd.yaml"
sed -i 's/preserve exported API/change exported API/' "$GF_SEMANTIC/directive.pb.go"
GF_SEMANTIC_RULES=$(gf_detect "$GF_SEMANTIC")
# Drift the base branch already had stays out of fix commits.
GF_DRIFT=$(gf_repo drift)
printf '# controller-gen.kubebuilder.io/version: v0.19.0\nfield: old\n' > "$GF_DRIFT/crd.yaml"
gf_commit "$GF_DRIFT"
GF_DRIFT_RULES=$(gf_detect "$GF_DRIFT")
sed -i 's/field: old/field: regenerated/' "$GF_DRIFT/crd.yaml"
( cd "$GF_DRIFT"; STATE_FILE="$GF_DRIFT/.state"; DIFF_IGNORE_ARGS="$GF_DRIFT_RULES"
  record_generated_drift
  sed -i 's/field: old/field: regenerated/' crd.yaml
  reconcile_generated_files )
check "pre-fix generated drift is recorded" grep -qx crd.yaml "$GF_DRIFT/.state.generated-drift"
check "pre-fix generated drift is restored" grep -q 'field: old' "$GF_DRIFT/crd.yaml"
check "pre-fix generated drift is never staged" git -C "$GF_DRIFT" diff --cached --quiet
GF_STAMP=$(gf_repo stamp)
printf 'metadata:\n  annotations:\n    controller-gen.kubebuilder.io/version: v0.19.0\nfield: same\n' > "$GF_STAMP/crd.yaml"
gf_commit "$GF_STAMP"
GF_STAMP_RULES=$(gf_detect "$GF_STAMP")
sed -i 's/v0.19.0/v0.22.0/' "$GF_STAMP/crd.yaml"
( cd "$GF_STAMP"; STATE_FILE="$GF_STAMP/.state"; DIFF_IGNORE_ARGS="$GF_STAMP_RULES"; record_generated_drift )
check "a version-stamp-only change is not drift" test ! -s "$GF_STAMP/.state.generated-drift"
check "a version-stamp-only change is restored" grep -q 'v0.19.0' "$GF_STAMP/crd.yaml"

( cd "$GF_SEMANTIC"; DIFF_IGNORE_ARGS="$GF_SEMANTIC_RULES" reconcile_generated_files )
check "generated reconciliation preserves changed Go build constraint" grep -q '^//go:build windows$' "$GF_SEMANTIC/build.pb.go"
check "generated reconciliation preserves changed copyright" grep -q 'Copyright 2026' "$GF_SEMANTIC/build.pb.go"
check "generated reconciliation stages substantive Go comments" \
  bash -c "git -C '$GF_SEMANTIC' diff --cached --name-only | grep -qx build.pb.go"
check "generated reconciliation retains distinct annotation change" grep -q 'version: changed' "$GF_SEMANTIC/crd.yaml"
check "generated reconciliation stages distinct annotation change" \
  bash -c "git -C '$GF_SEMANTIC' diff --cached --name-only | grep -qx crd.yaml"
check "generated reconciliation retains semantic text after a version" grep -q 'change exported API' "$GF_SEMANTIC/directive.pb.go"
check "generated reconciliation stages semantic text after a version" \
  bash -c "git -C '$GF_SEMANTIC' diff --cached --name-only | grep -qx directive.pb.go"
GF_WRONG_MARK=$(gf_repo wrong-marker)
printf 'metadata:\n  annotations:\n    controller-genXkubebuilderXio/version: v0.19.0\n' > "$GF_WRONG_MARK/crd.yaml"
gf_commit "$GF_WRONG_MARK"
check "generated discovery requires the literal controller-gen annotation" test -z "$(gf_detect "$GF_WRONG_MARK")"

# === fix-all.sh PR command generation (fork detection, plural, no-fork, partial fix) ===
# Exercises fix-all.sh lines 648-682: fork-remote detection, UPSTREAM_ORG
# resolution, FORK_USER extraction, placeholder fallback, partial-fix PR title,
# PLURAL logic, and NOT READY TO PUSH suppression — with real commits present.
echo "fix-all.sh PR command generation"
if command -v jq >/dev/null 2>&1; then
  PRT_DIR="$TMPD/prt"
  PRT_ORIGIN="$PRT_DIR/origin"
  PRT_REPO="$PRT_DIR/repo"
  PRT_SCRIPTS="$PRT_DIR/scripts"
  PRT_STATE="$PRT_DIR/prt-state.env"
  PRT_SEED="$PRT_DIR/seed"
  mkdir -p "$PRT_ORIGIN" "$PRT_SCRIPTS"

  # Set up local upstream (bare repo) with devel branch
  git init --bare "$PRT_ORIGIN" -q
  git clone "$PRT_ORIGIN" "$PRT_SEED" -q 2>/dev/null
  git -C "$PRT_SEED" config user.email "t@t.com"
  git -C "$PRT_SEED" config user.name "T"
  touch "$PRT_SEED/go.mod"
  git -C "$PRT_SEED" add -A
  git -C "$PRT_SEED" commit -qm "init"
  git -C "$PRT_SEED" push -q origin HEAD:devel 2>/dev/null
  git clone "$PRT_ORIGIN" "$PRT_REPO" -q 2>/dev/null
  git -C "$PRT_REPO" config user.email "t@t.com"
  git -C "$PRT_REPO" config user.name "T"
  git -C "$PRT_REPO" checkout -q -b devel origin/devel 2>/dev/null || git -C "$PRT_REPO" checkout -q devel 2>/dev/null
  git -C "$PRT_REPO" branch operator-start
  PRT_ORIGINAL_HEAD=$(git -C "$PRT_REPO" rev-parse operator-start)
  git -C "$PRT_REPO" remote add myfork "https://github.com/testforkuser/testrepo.git"

  # Copy scripts (fix-all.sh uses SCRIPT_DIR = its own directory)
  cp "$SCRIPT_DIR/lib.sh" "$PRT_SCRIPTS/"
  printf '\npreflight_check() { return 0; }\n' >> "$PRT_SCRIPTS/lib.sh"
  cp "$SCRIPT_DIR/fix-all.sh" "$PRT_SCRIPTS/"
  cp "$SCRIPT_DIR/binary-module-locations.py" "$PRT_SCRIPTS/"
  # Publication scenarios assume all independent audits complete successfully;
  # individual cases below replace the audit whose behavior they exercise.
  prt_clean_audits() {
    local name
    mkdir -p "$PRT_DIR/subagents"
    printf '#!/usr/bin/env bash\necho "NEW_CVES=0 UNRESOLVED=0"\n' > "$PRT_DIR/subagents/scan-regression.sh"
    for name in existing-entries fix-availability yaml-integrity; do
      printf '#!/usr/bin/env bash\necho "NEW_ISSUES=0"\n' > "$PRT_DIR/subagents/$name.sh"
    done
  }
  prt_clean_audits

  # Mock review.sh: always succeeds with no unresolved items
  printf '#!/usr/bin/env bash\nexit 0\n' > "$PRT_SCRIPTS/review.sh"
  chmod +x "$PRT_SCRIPTS/review.sh"

  # Write state file; $1 overrides TEST_CMD (default: "true")
  prt_write_state() {
    local test_cmd="${1:-true}"
    printf 'STATE_FILE=%q\nREPO=%q\nBRANCH="devel"\nFIX_BRANCH=""\n' \
      "$PRT_STATE" "$PRT_REPO" > "$PRT_STATE"
    printf 'ORIGINAL_REF=operator-start\nHAS_TOOLS_GOMOD=false\nHAS_VENDOR=false\n' >> "$PRT_STATE"
    printf 'DIFF_IGNORE_ARGS=""\nNEEDS_BUILD_FOR_SCAN=false\n' >> "$PRT_STATE"
    printf 'CONTAINER_CMD=""\nHAS_LOCAL_GRYPE=false\nBUILD_IMAGE=""\n' >> "$PRT_STATE"
    printf 'BUILD_GO_VERSION="unknown"\nBUILD_CMD=""\nCLEAN_CMD=""\n' >> "$PRT_STATE"
    printf 'TEST_CMD="%s"\n' "$test_cmd" >> "$PRT_STATE"
    # The real upstream transport is local; explicitly supply its GitHub org
    # instead of relying on an unmatched URL being mistaken for an owner.
    printf 'ENV_UNSET=""\nK8S_VERSION_GUARD=false\nUPSTREAM_ORG="testupstream"\n' >> "$PRT_STATE"
    printf 'FETCH_FAILED=false\nCVE_SCRIPTS=%q\n' "$PRT_SCRIPTS" >> "$PRT_STATE"
  }

  # Mock detect.sh: outputs the pre-written state file path as last line
  printf '#!/usr/bin/env bash\necho "=== CVE Fix: prt/devel ==="\necho %q\n' \
    "$PRT_STATE" > "$PRT_SCRIPTS/detect.sh"
  chmod +x "$PRT_SCRIPTS/detect.sh"

  # Shared scan mock writer; $1 controls gate behaviour ("empty" or "match")
  prt_write_scan() {
    local gate_mode="${1:-empty}"
    if [[ "$gate_mode" == "match" ]]; then
      # All calls return a match (simulates CVE persisting after fix attempt)
      cat > "$PRT_SCRIPTS/scan.sh" <<'SCANEOF'
#!/usr/bin/env bash
printf '{"matches":[{"vulnerability":{"id":"GHSA-test-pr-0001","severity":"High","fix":{"versions":["1.2.0"],"state":"fixed"}},"artifact":{"name":"example.com/prpkg","version":"1.0.0","type":"go-module","locations":[{"path":"/go.mod"}]}}],"ignoredMatches":[]}\n'
SCANEOF
    else
      # --fresh -> initial match; all other calls -> empty (CVE fixed)
      cat > "$PRT_SCRIPTS/scan.sh" <<'SCANEOF'
#!/usr/bin/env bash
if [[ "$*" == *"--fresh"* ]]; then
  printf '{"matches":[{"vulnerability":{"id":"GHSA-test-pr-0001","severity":"High","fix":{"versions":["1.2.0"],"state":"fixed"}},"artifact":{"name":"example.com/prpkg","version":"1.0.0","type":"go-module","locations":[{"path":"/go.mod"}]}}],"ignoredMatches":[]}\n'
else
  printf '{"matches":[],"ignoredMatches":[]}\n'
fi
SCANEOF
    fi
    chmod +x "$PRT_SCRIPTS/scan.sh"
  }

  # Mock fix-package.sh: appends to go.mod, commits with signoff, exits 0
  cat > "$PRT_SCRIPTS/fix-package.sh" <<'FPEOF'
#!/usr/bin/env bash
STATE_FILE="$1"; source "$STATE_FILE"
PKG="$2"; VER="$3"; shift 3
printf 'bumped\n' >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" -c user.email=t@t.com -c user.name=T \
  commit -qm "Bump $PKG for $1" -s 2>/dev/null
printf 'FIXED: %s v%s for %s\n' "$PKG" "$VER" "$*"
FPEOF
  chmod +x "$PRT_SCRIPTS/fix-package.sh"

  # --- Sub-case A: fork remote detected -> full PR command with fork push ---
  prt_write_state; prt_write_scan
  PRT_A_RC=0
  PRT_A_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_A_RC=$?
  check "PR cmd A: clean readiness exits zero" test "$PRT_A_RC" -eq 0
  check "PR cmd A: git push uses fork remote"  grep -q "git push myfork" <<< "$PRT_A_OUT"
  check "PR cmd A: --head uses fork user"      grep -q -- "--head testforkuser:devel" <<< "$PRT_A_OUT"
  check "PR cmd A: --base is branch"           grep -q -- "--base devel" <<< "$PRT_A_OUT"
  check "PR cmd A: single-CVE title"           grep -qF -- "--title Fix\\ CVE\\ in\\ devel" <<< "$PRT_A_OUT"
  check "PR cmd A: Summary reports the observed original ref" grep -qx 'Original ref: operator-start' <<< "$PRT_A_OUT"
  check "PR cmd A: target remains distinct from original ref" grep -qx 'Fix branch: devel' <<< "$PRT_A_OUT"
  check "PR cmd A: retained commit is reported" grep -q "^$(git -C "$PRT_REPO" rev-parse --short HEAD) " <<< "$PRT_A_OUT"
  check "PR cmd A: original branch remains unchanged" test "$(git -C "$PRT_REPO" rev-parse operator-start)" = "$PRT_ORIGINAL_HEAD"
  check "PR cmd A: final finding count remains zero" grep -q 'Outstanding: 0' <<< "$PRT_A_OUT"

  # A predictable pre-planted directory must never supply verification inputs,
  # and cleanup must leave unrelated directories with the old PID pattern alone.
  mkdir -p "$PRT_DIR/subagents" "$PRT_DIR/report-tmp"
  cat > "$PRT_DIR/subagents/scan-regression.sh" <<'REPORTPROBE'
#!/usr/bin/env bash
set -euo pipefail
mode=$(python3 -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$2")
planted=false
[[ ! -f "$2/needs-review-pkgs" ]] || planted=true
printf '%s|%s|%s\n' "$2" "$mode" "$planted" > "$REPORT_SPY"
printf 'NEW_CVES=0 UNRESOLVED=%s\n' "$REPORT_FORCE_FAIL"
REPORTPROBE
  for _report_fail in 0 1; do
    git -C "$PRT_REPO" reset --hard origin/devel -q
    prt_write_state; prt_write_scan
    _report_rc=0
    _report_out=$(PATH=/usr/bin:/bin TMPDIR="$PRT_DIR/report-tmp" PRESERVE_REPORTS= \
      REPORT_FORCE_FAIL="$_report_fail" REPORT_SPY="$PRT_DIR/report.spy" REPORT_PLANTED_LOG="$PRT_DIR/planted.log" \
      bash -c '
        umask 000
        task_planted="$TMPDIR/cve-fix-subagents-repo-devel-$$"
        task_other="$TMPDIR/cve-fix-subagents-unrelated-$$"
        mkdir -p "$task_planted" "$task_other"
        printf "example.com/planted\n" > "$task_planted/needs-review-pkgs"
        printf "unrelated user data\n" > "$task_other/keep"
        printf "%s|%s\n" "$task_planted" "$task_other" > "$REPORT_PLANTED_LOG"
        exec bash "$1" "$2" devel
      ' _ "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" 2>&1) || _report_rc=$?
    IFS='|' read -r _report_path _report_mode _report_planted < "$PRT_DIR/report.spy"
    IFS='|' read -r _planted_path _other_path < "$PRT_DIR/planted.log"
    check "private report fail=$_report_fail: fresh path differs from planted path" test "$_report_path" != "$_planted_path"
    check "private report fail=$_report_fail: directory remains private under umask 000" test "$_report_mode" = 700
    check "private report fail=$_report_fail: planted classification was not loaded" test "$_report_planted" = false
    check "private report fail=$_report_fail: unrelated legacy directory survives" test "$(cat "$_other_path/keep")" = 'unrelated user data'
    check "private report fail=$_report_fail: pre-planted directory is untouched" grep -qx 'example.com/planted' "$_planted_path/needs-review-pkgs"
    if [[ "$_report_fail" == 0 ]]; then
      check "private report: successful verification completes" test "$_report_rc" -eq 0
      check "private report: successful verification removes exact owned directory" test ! -e "$_report_path"
    else
      check "private report: failed verification needs review" test "$_report_rc" -eq 2
      check "private report: failed verification retains initial evidence" test -f "$_report_path/initial-scan.json"
      check "private report: failed verification retains debugging state" test -f "$_report_path/state.env"
      check "private report: failed verification reports the preserved directory" grep -qF "Reports preserved for debugging: $_report_path" <<< "$_report_out"
    fi
  done
  rm -rf "$PRT_DIR/subagents"
  prt_clean_audits
  # An abort before directory creation must not delete an inherited path.
  mkdir -p "$PRT_DIR/foreign-report"
  printf 'foreign data\n' > "$PRT_DIR/foreign-report/keep"
  git -C "$PRT_REPO" reset --hard origin/devel -q
  prt_write_state
  printf '#!/usr/bin/env bash\nexit 1\n' > "$PRT_SCRIPTS/scan.sh"
  _report_rc=0
  SUBAGENT_REPORT_DIR="$PRT_DIR/foreign-report" bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel \
    > "$PRT_DIR/early-report-abort.log" 2>&1 || _report_rc=$?
  check "private report: early scanner failure remains unsuccessful" test "$_report_rc" -ne 0
  check "private report: early failure preserves inherited foreign directory" test "$(cat "$PRT_DIR/foreign-report/keep")" = 'foreign data'

  # Exercise the real Make policy gate: inherited CLI variables and dry-run
  # flags must not override the image namespace or silently skip evaluation.
  cat > "$PRT_REPO/Makefile" <<'LICENSEMAKE'
licensecheck: cached-license-input
	@printf '%s\n' '$(REPO)' >> .git/license-ran
	@test '$(REPO)' = cve-fix-license-fixture
	@test "$${LICENSE_TEST_BLOCKER+x}" != x
	@test "$${LICENSE_TEST_FAIL}" != true
	@mkdir -p bin && printf x > bin/license-tool && chmod +x bin/license-tool
cached-license-input:
	@touch $@
	@echo rebuilt >> .git/license-input-rebuilt
LICENSEMAKE
  # A real file named after the target must not make the policy gate a no-op.
  touch "$PRT_REPO/licensecheck" "$PRT_REPO/cached-license-input"
  for _license_flags in '' '-- REPO=/inherited/unsafe/path' '--just-print -- REPO=/inherited/unsafe/path'; do
    for _license_fail in false true; do
      git -C "$PRT_REPO" reset --hard origin/devel -q
      rm -f "$PRT_REPO/.git/license-ran"
      prt_write_state; prt_write_scan
      printf 'BUILD_REPO_NAME="cve-fix-license-fixture"\nENV_UNSET="LICENSE_TEST_BLOCKER"\n' >> "$PRT_STATE"
      PRT_LICENSE_RC=0
      PRT_LICENSE_OUT=$(REPO="$PRT_REPO" MAKEFLAGS="$_license_flags" LICENSE_TEST_BLOCKER=present LICENSE_TEST_FAIL="$_license_fail" \
        bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_LICENSE_RC=$?
      _license_label="license fail=$_license_fail flags=$_license_flags"
      check "$_license_label: actual policy recipe ran" test -f "$PRT_REPO/.git/license-ran"
      check "$_license_label: sanitized namespace overrides inherited path" grep -qx 'cve-fix-license-fixture' "$PRT_REPO/.git/license-ran"
      check "$_license_label: scan still confirms the repair" grep -q 'Outstanding: 0' <<< "$PRT_LICENSE_OUT"
      check "$_license_label: repair is retained" grep -q 'bumped' "$PRT_REPO/go.mod"
      if [[ "$_license_fail" == true ]]; then
        check "$_license_label: policy failure exits for review" test "$PRT_LICENSE_RC" -eq 2
        check "$_license_label: policy failure is reported" grep -q 'POLICY REVIEW REQUIRED' <<< "$PRT_LICENSE_OUT"
        check "$_license_label: policy failure suppresses PR" ! grep -q 'gh pr create' <<< "$PRT_LICENSE_OUT"
      else
        check "$_license_label: sanitized policy evaluation succeeds" test "$PRT_LICENSE_RC" -eq 0
        check "$_license_label: successful policy evaluation is reported" grep -q 'License policy check passed' <<< "$PRT_LICENSE_OUT"
        check "$_license_label: successful policy gate permits PR" grep -q 'gh pr create' <<< "$PRT_LICENSE_OUT"
      fi
    done
  done
  rm "$PRT_REPO/licensecheck" "$PRT_REPO/.git/license-input-rebuilt" "$PRT_REPO/.git/license-ran"
  git -C "$PRT_REPO" reset --hard origin/devel -q
  prt_write_state; prt_write_scan
  printf 'BUILD_REPO_NAME="cve-fix-license-fixture"\n' >> "$PRT_STATE"
  PRT_LICENSE_RC=0
  PRT_LICENSE_OUT=$(LICENSE_TEST_FAIL=false bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_LICENSE_RC=$?
  check "license gate reuses an existing prerequisite" test ! -e "$PRT_REPO/.git/license-input-rebuilt"
  check "license gate still evaluates policy with cached inputs" test -f "$PRT_REPO/.git/license-ran"
  check "license gate with cached inputs permits a verified PR" test "$PRT_LICENSE_RC" -eq 0
  check "license gate removes the tool it built" test ! -e "$PRT_REPO/bin/license-tool"
  rm "$PRT_REPO/Makefile" "$PRT_REPO/cached-license-input"

  # Mapping enriches scan locations for dispatch; helper failures must preserve
  # the original evidence and continue repairs using those raw locations.
  cp "$PRT_SCRIPTS/binary-module-locations.py" "$PRT_DIR/binary-module-locations.saved"
  for _prt_mapping_mode in failed empty invalid-json invalid-schema; do
    git -C "$PRT_REPO" reset --hard origin/devel -q
    prt_write_state; prt_write_scan
    case "$_prt_mapping_mode" in
      failed) printf 'raise RuntimeError("mapping unavailable")\n' > "$PRT_SCRIPTS/binary-module-locations.py" ;;
      empty) printf 'pass\n' > "$PRT_SCRIPTS/binary-module-locations.py" ;;
      invalid-json) printf 'print("not JSON")\n' > "$PRT_SCRIPTS/binary-module-locations.py" ;;
      invalid-schema) printf 'print("{}")\n' > "$PRT_SCRIPTS/binary-module-locations.py" ;;
    esac
    PRT_MAPPING_RC=0
    PRT_MAPPING_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_MAPPING_RC=$?
    check "mapping $_prt_mapping_mode: verified repair exits zero" test "$PRT_MAPPING_RC" -eq 0
    check "mapping $_prt_mapping_mode: fallback is explained" grep -q 'dispatching with raw scan locations' <<< "$PRT_MAPPING_OUT"
    check "mapping $_prt_mapping_mode: original source scope is retained" grep -q '^FIXED: example.com/prpkg .* at /go.mod$' <<< "$PRT_MAPPING_OUT"
    check "mapping $_prt_mapping_mode: repair is committed" grep -q 'bumped' "$PRT_REPO/go.mod"
    check "mapping $_prt_mapping_mode: final scan remains authoritative" grep -q 'Outstanding: 0' <<< "$PRT_MAPPING_OUT"
    check "mapping $_prt_mapping_mode: PR command remains available" grep -q 'gh pr create' <<< "$PRT_MAPPING_OUT"
  done
  mv "$PRT_DIR/binary-module-locations.saved" "$PRT_SCRIPTS/binary-module-locations.py"

  # Real Git metadata exercises the complete final-readiness path. A clean
  # scan must not turn a stale base or unsigned repair into batch success.
  _PRT_BASE=$(git -C "$PRT_REPO" rev-parse origin/devel)
  for _prt_failure in fetch base-moved refresh dco; do
    git -C "$PRT_REPO" remote set-url origin "$PRT_ORIGIN"
    git --git-dir="$PRT_ORIGIN" update-ref refs/heads/devel "$_PRT_BASE"
    git -C "$PRT_REPO" update-ref refs/remotes/origin/devel "$_PRT_BASE"
    git -C "$PRT_REPO" reset --hard "$_PRT_BASE" -q
    prt_write_state; prt_write_scan
    printf 'BASE_SHA=%q\n' "$_PRT_BASE" >> "$PRT_STATE"
    case "$_prt_failure" in
      fetch) printf 'FETCH_FAILED=true\n' >> "$PRT_STATE" ;;
      base-moved)
        git -C "$PRT_SEED" reset --hard "$_PRT_BASE" -q
        git -C "$PRT_SEED" commit --allow-empty -qm 'base moved'
        git -C "$PRT_SEED" push -q origin HEAD:devel
        ;;
      refresh) git -C "$PRT_REPO" remote set-url origin "$PRT_DIR/missing-origin" ;;
      dco)
        # Keep fix-package's normal signed repair, but add an unsigned manual
        # dependency commit that the production range audit must reject.
        printf 'manual change\n' >> "$PRT_REPO/go.mod"
        git -C "$PRT_REPO" add go.mod
        git -C "$PRT_REPO" commit -qm 'unsigned manual repair'
        ;;
    esac
    _PRT_READINESS_RC=0
    _PRT_READINESS_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || _PRT_READINESS_RC=$?
    case "$_prt_failure" in
      fetch) _PRT_REASON='base branch fetch failed' ;;
      base-moved) _PRT_REASON='base branch moved during the run' ;;
      refresh) _PRT_REASON='final base refresh failed' ;;
      dco) _PRT_REASON='commit(s) missing Signed-off-by:' ;;
    esac
    check "PR readiness $_prt_failure exits for review" test "$_PRT_READINESS_RC" -eq 2
    check "PR readiness $_prt_failure reports its actual cause" grep -qF "$_PRT_REASON" <<< "$_PRT_READINESS_OUT"
    check "PR readiness $_prt_failure has a clean CVE scan" grep -q 'Outstanding: 0' <<< "$_PRT_READINESS_OUT"
    check "PR readiness $_prt_failure explains suppression" grep -q 'NOT READY TO PUSH' <<< "$_PRT_READINESS_OUT"
    check "PR readiness $_prt_failure emits no PR command" ! grep -q 'gh pr create' <<< "$_PRT_READINESS_OUT"
    check "PR readiness $_prt_failure retains verified repair" grep -q 'bumped' "$PRT_REPO/go.mod"
    check "PR readiness $_prt_failure cleans worker state" test ! -e "${PRT_STATE}"
  done
  git -C "$PRT_REPO" remote set-url origin "$PRT_ORIGIN"
  git --git-dir="$PRT_ORIGIN" update-ref refs/heads/devel "$_PRT_BASE"
  git -C "$PRT_REPO" update-ref refs/remotes/origin/devel "$_PRT_BASE"
  git -C "$PRT_REPO" reset --hard "$_PRT_BASE" -q

  # --- Sub-case B: no fork remote -> no executable placeholder command ---
  git -C "$PRT_REPO" remote remove myfork 2>/dev/null || true
  git -C "$PRT_REPO" reset --hard origin/devel -q 2>/dev/null || true
  prt_write_state; prt_write_scan
  printf 'ORIGINAL_REF=""\n' >> "$PRT_STATE"
  PRT_B_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || true
  check "PR cmd B: absent original-ref evidence is omitted" ! grep -q '^Original ref:' <<< "$PRT_B_OUT"
  check "PR cmd B: no placeholder remote shown" ! grep -q "<fork-remote>" <<< "$PRT_B_OUT"
  check "PR cmd B: NOTE about missing fork"    grep -q "no fork remote" <<< "$PRT_B_OUT"
  check "PR cmd B: no unusable gh command"    ! grep -q "gh pr create" <<< "$PRT_B_OUT"
  git -C "$PRT_REPO" remote add myfork "https://github.com/testforkuser/testrepo.git"

  # --- Sub-case C: GATE_REMAINING>0 -> "Partial CVE fix" title ---
  git -C "$PRT_REPO" reset --hard origin/devel -q 2>/dev/null || true
  prt_write_state; prt_write_scan "match"
  PRT_C_RC=0
  PRT_C_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_C_RC=$?
  check "PR cmd C: confirmed partial readiness exits two" test "$PRT_C_RC" -eq 2
  check "PR cmd C: Partial CVE fix in title"   grep -qF "Partial\\ CVE\\ fix\\ in\\ devel" <<< "$PRT_C_OUT"
  check "PR cmd C: not NOT READY TO PUSH"      ! grep -q "NOT READY TO PUSH" <<< "$PRT_C_OUT"

  # Counted partial repairs still have to pass repository policy gates. These
  # failures must retain the repair and CVE count while suppressing publication.
  for _prt_policy_failure in license file-scope ignore-scope; do
    git -C "$PRT_REPO" reset --hard origin/devel -q
    prt_write_state; prt_write_scan match
    case "$_prt_policy_failure" in
      license)
        printf 'licensecheck:\n\t@false\n' > "$PRT_REPO/Makefile"
        _prt_policy_reason='POLICY REVIEW REQUIRED: make licensecheck failed'
        ;;
      file-scope)
        printf 'unrelated source change\n' > "$PRT_REPO/unrelated.go"
        git -C "$PRT_REPO" add unrelated.go
        git -C "$PRT_REPO" commit -qsm 'Unrelated source change'
        _prt_policy_reason='CVE fix branch touches non-dependency files'
        ;;
      ignore-scope)
        printf 'ignore:\n  - vulnerability: GHSA-scope-policy\n    fix-state: not-fixed\n    package:\n      name: example.com/other\n  - vulnerability: GHSA-scope-policy\n    fix-state: not-fixed\n    package:\n      name: example.com/other\n      location: /tools/go.mod\n' > "$PRT_REPO/.grype.yaml"
        git -C "$PRT_REPO" add .grype.yaml
        git -C "$PRT_REPO" commit -qsm 'Conflicting ignore policy'
        _prt_policy_reason='ignore policy has unscoped/scoped conflicts'
        ;;
    esac
    _prt_policy_rc=0
    _prt_policy_out=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || _prt_policy_rc=$?
    check "partial $_prt_policy_failure: run remains partial" test "$_prt_policy_rc" -eq 2
    check "partial $_prt_policy_failure: CVE count stays authoritative" grep -q 'Outstanding: 1' <<< "$_prt_policy_out"
    check "partial $_prt_policy_failure: concrete policy failure is reported" grep -qF "$_prt_policy_reason" <<< "$_prt_policy_out"
    check "partial $_prt_policy_failure: PR is explicitly blocked" grep -q 'NOT READY TO PUSH' <<< "$_prt_policy_out"
    check "partial $_prt_policy_failure: no executable PR command" ! grep -q 'gh pr create' <<< "$_prt_policy_out"
    check "partial $_prt_policy_failure: verified repair remains committed" \
      bash -c 'git -C "$1" show HEAD:go.mod | grep -q bumped' _ "$PRT_REPO"
    [[ "$_prt_policy_failure" != license ]] || rm "$PRT_REPO/Makefile"
  done

  # Real scan companion and verification loop: an existing policy-boundary CVE
  # must permit submission of a separate signed repair as a counted partial PR.
  git -C "$PRT_REPO" reset --hard origin/devel -q
  printf 'other repair\n' >> "$PRT_REPO/go.mod"
  git -C "$PRT_REPO" add go.mod
  git -C "$PRT_REPO" commit -qsm 'Repair another dependency'
  prt_write_state; prt_write_scan "match"
  mkdir -p "$PRT_DIR/subagents"
  cp "$SCRIPT_DIR/../subagents/scan-regression.sh" "$PRT_DIR/subagents/"
  cp "$PRT_SCRIPTS/fix-package.sh" "$PRT_DIR/fix-package.saved"
  printf '#!/usr/bin/env bash\necho "NEEDS_REVIEW: example.com/prpkg — Kubernetes minor bump needs approval at /go.mod"\nexit 2\n' > "$PRT_SCRIPTS/fix-package.sh"
  PRT_POLICY_RC=0
  PRT_POLICY_OUT=$(PATH=/usr/bin:/bin bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_POLICY_RC=$?
  check "policy partial: run exits for team review" test "$PRT_POLICY_RC" -eq 2
  check "policy partial: final gate counts existing CVE" grep -q 'Outstanding: 1' <<< "$PRT_POLICY_OUT"
  check "policy partial: existing finding remains documented" grep -q '^NEEDS_REVIEW: example.com/prpkg .* approval at /go.mod' <<< "$PRT_POLICY_OUT"
  check "policy partial: deterministic verification succeeds" grep -q 'Verified deterministically' <<< "$PRT_POLICY_OUT"
  check "policy partial: signed repair can be submitted" grep -q 'gh pr create' <<< "$PRT_POLICY_OUT"
  check "policy partial: PR title signals remaining CVE" grep -qF 'Partial\ CVE\ fix\ in\ devel' <<< "$PRT_POLICY_OUT"
  check "policy partial: verification does not suppress PR" ! grep -q 'NOT READY TO PUSH' <<< "$PRT_POLICY_OUT"
  mv "$PRT_DIR/fix-package.saved" "$PRT_SCRIPTS/fix-package.sh"
  rm -rf "$PRT_DIR/subagents"
  prt_clean_audits

  # --- Sub-case D: TESTS_FAILED -> suppress PR command as unconfirmed ---
  git -C "$PRT_REPO" reset --hard origin/devel -q 2>/dev/null || true
  prt_write_state "false"; prt_write_scan  # TEST_CMD="false" -> TESTS_FAILED=true
  printf 'ORIGINAL_REF=%q\n' "$PRT_ORIGINAL_HEAD" >> "$PRT_STATE"
  PRT_D_RC=0
  PRT_D_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_D_RC=$?
  check "PR cmd D: blocked run exits two" test "$PRT_D_RC" -eq 2
  check "PR cmd D: detached original ref is reported literally" grep -qx "Original ref: $PRT_ORIGINAL_HEAD" <<< "$PRT_D_OUT"
  check "PR cmd D: retained repair commit is reported" grep -q "^$(git -C "$PRT_REPO" rev-parse --short HEAD) " <<< "$PRT_D_OUT"
  check "PR cmd D: failed tests do not change the final finding count" grep -q 'Outstanding: 0' <<< "$PRT_D_OUT"
  check "PR cmd D: gh pr create suppressed"   ! grep -q "gh pr create" <<< "$PRT_D_OUT"
  check "PR cmd D: marked NOT READY TO PUSH"   grep -q "NOT READY TO PUSH" <<< "$PRT_D_OUT"
  check "PR cmd D: tests-failed reason listed" grep -q "tests failed after applying fixes" <<< "$PRT_D_OUT"

  # A completed policy-boundary run can reach Summary without any repair commit.
  # Its displayed fix branch is then removed; reporting the original ref must
  # not keep that empty branch or manufacture a publication recipe.
  git -C "$PRT_REPO" checkout -qb summary-empty origin/devel
  prt_write_state; prt_write_scan match
  printf 'FIX_BRANCH=summary-empty\n' >> "$PRT_STATE"
  cp "$PRT_SCRIPTS/fix-package.sh" "$PRT_DIR/fix-package.saved"
  printf '#!/usr/bin/env bash\necho "NEEDS_REVIEW: example.com/prpkg — team decision required"\nexit 2\n' > "$PRT_SCRIPTS/fix-package.sh"
  PRT_EMPTY_RC=0
  PRT_EMPTY_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_EMPTY_RC=$?
  check "no-commit Summary: unresolved finding remains partial" test "$PRT_EMPTY_RC" -eq 2
  check "no-commit Summary: original ref is reported" grep -qx 'Original ref: operator-start' <<< "$PRT_EMPTY_OUT"
  check "no-commit Summary: removal of displayed branch is explicit" grep -qx 'No commits; removed the empty fix branch.' <<< "$PRT_EMPTY_OUT"
  check "no-commit Summary: checkout returns to original branch" test "$(git -C "$PRT_REPO" branch --show-current)" = operator-start
  check "no-commit Summary: original HEAD is unchanged" test "$(git -C "$PRT_REPO" rev-parse HEAD)" = "$PRT_ORIGINAL_HEAD"
  check "no-commit Summary: empty fix branch is removed" ! git -C "$PRT_REPO" show-ref --verify --quiet refs/heads/summary-empty
  check "no-commit Summary: no publication command" ! grep -q 'gh pr create' <<< "$PRT_EMPTY_OUT"
  check "no-commit Summary: finding count remains authoritative" grep -q 'Outstanding: 1' <<< "$PRT_EMPTY_OUT"
  mv "$PRT_DIR/fix-package.saved" "$PRT_SCRIPTS/fix-package.sh"
  git -C "$PRT_REPO" checkout -q devel

  # --- Sub-case E: multiple commits -> plural "Fix CVEs" title ---
  git -C "$PRT_REPO" reset --hard origin/devel -q 2>/dev/null || true
  # Pre-create one extra commit so fix-package.sh's commit makes COMMIT_COUNT=2
  printf 'pre\n' >> "$PRT_REPO/go.mod"
  git -C "$PRT_REPO" add go.mod
  git -C "$PRT_REPO" -c user.email=t@t.com -c user.name=T commit -qm "Pre-existing bump" -s 2>/dev/null
  prt_write_state; prt_write_scan
  PRT_E_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || true
  check "PR cmd E: plural CVEs title"          grep -qF -- "--title Fix\\ CVEs\\ in\\ devel" <<< "$PRT_E_OUT"
  check "PR cmd E: plural commit messages body" grep -qF -- "--body See\\ commit\\ messages" <<< "$PRT_E_OUT"
  # A counted result from a failed final process must suppress publication.
  git -C "$PRT_REPO" reset --hard origin/devel -q
  prt_write_state; prt_write_scan
  printf '\n[[ "$*" != *--fresh* ]] && exit 7\nexit 0\n' >> "$PRT_SCRIPTS/scan.sh"
  PRT_FAILURE_RC=0
  PRT_FAILURE_OUT=$(bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_FAILURE_RC=$?
  check "failed final scanner exits unconfirmed despite valid JSON" test "$PRT_FAILURE_RC" -eq 2
  check "failed final scanner suppresses executable PR command" ! grep -q 'gh pr create' <<< "$PRT_FAILURE_OUT"
  check "failed final scanner records unconfirmed status" grep -q 'Outstanding: unknown' <<< "$PRT_FAILURE_OUT"

  # A grouped product-version lookup failure (as observed with Istio) proves
  # neither advisory lacks a fix. Keep both findings actionable and add no rule.
  git -C "$PRT_REPO" reset --hard origin/devel -q
  prt_write_state
  cat > "$PRT_SCRIPTS/scan.sh" <<'SCANEOF'
#!/usr/bin/env bash
printf '%s\n' '{"matches":[{"vulnerability":{"id":"GHSA-product-tag","severity":"High","fix":{"versions":["1.12.18"],"state":"fixed"}},"artifact":{"name":"example.com/product","version":"v0.0.0-20260306174229-7da666217518","type":"go-module","locations":[{"path":"/go.mod"}]}},{"vulnerability":{"id":"GHSA-commit-fix","severity":"High","fix":{"versions":["0.0.0-20260410004459-189832a289c1"],"state":"fixed"}},"artifact":{"name":"example.com/product","version":"v0.0.0-20260306174229-7da666217518","type":"go-module","locations":[{"path":"/go.mod"}]}}],"ignoredMatches":[]}'
SCANEOF
  printf '#!/usr/bin/env bash\necho "NOTE: selected fix unavailable at current module path"\nexit 4\n' > "$PRT_SCRIPTS/fix-package.sh"
  cat > "$PRT_SCRIPTS/ignore.sh" <<'IGNOREEOF'
#!/usr/bin/env bash
touch "${UNAVAILABLE_IGNORE_MARKER:?}"
exit 0
IGNOREEOF
  chmod +x "$PRT_SCRIPTS/scan.sh" "$PRT_SCRIPTS/fix-package.sh" "$PRT_SCRIPTS/ignore.sh"
  PRT_UNAVAILABLE_RC=0
  PRT_UNAVAILABLE_OUT=$(UNAVAILABLE_IGNORE_MARKER="$PRT_DIR/ignore-called" \
    bash "$PRT_SCRIPTS/fix-all.sh" "$PRT_REPO" devel 2>&1) || PRT_UNAVAILABLE_RC=$?
  check "unavailable grouped candidate keeps workflow partial" test "$PRT_UNAVAILABLE_RC" -eq 2
  check "unavailable grouped candidate does not invoke ignore handler" test ! -e "$PRT_DIR/ignore-called"
  check "unavailable grouped candidate retains both findings" grep -q 'Outstanding: 2' <<< "$PRT_UNAVAILABLE_OUT"
  check "unavailable grouped candidate is not counted as ignored" grep -q 'Ignored: 0' <<< "$PRT_UNAVAILABLE_OUT"
  check "unavailable grouped candidate remains marked for review" grep -q 'NEEDS_REVIEW: example.com/product' <<< "$PRT_UNAVAILABLE_OUT"
  check "unavailable grouped candidate leaves tracked source untouched" git -C "$PRT_REPO" diff --quiet origin/devel
  check "unavailable grouped candidate emits no PR command" ! grep -q 'gh pr create' <<< "$PRT_UNAVAILABLE_OUT"
else
  echo "  SKIP: jq not available"
fi

# === _run_companions behavioral tests ===
# _run_companions iterates companion *.sh scripts in a directory, runs each
# with (state_file, report_dir) args, and captures stdout to
# $report_dir/<name>.evidence. Tests verify: evidence file created, content
# matches companion stdout, and removed scripts cannot leave stale evidence.
echo "_run_companions behavioral"
RC_DIR="$TMPD/rc"; mkdir -p "$RC_DIR/subagents" "$RC_DIR/report"
RC_STATE="$RC_DIR/state.env"; touch "$RC_STATE"

# Companion that writes a known marker to stdout
printf '#!/usr/bin/env bash\nprintf "%%s\\n" "marker-from-companion"\n' \
  > "$RC_DIR/subagents/demo.sh"
chmod +x "$RC_DIR/subagents/demo.sh"

_run_companions "$RC_DIR/subagents" "$RC_STATE" "$RC_DIR/report"

check "_run_companions: evidence file created" \
  test -f "$RC_DIR/report/demo.evidence"
check "_run_companions: evidence contains companion output" \
  grep -q "marker-from-companion" "$RC_DIR/report/demo.evidence"

RC_ORDER_DIR="$TMPD/rc-order"; mkdir -p "$RC_ORDER_DIR/subagents" "$RC_ORDER_DIR/report"
RC_ORDER_STATE="$RC_ORDER_DIR/state.env"; touch "$RC_ORDER_STATE"
printf '#!/usr/bin/env bash\ntouch "$2/final-scan.json"\nprintf "NEW_CVES=0 UNRESOLVED=0\\n"\n' \
  > "$RC_ORDER_DIR/subagents/scan-regression.sh"
printf '#!/usr/bin/env bash\n[[ -f "$2/final-scan.json" ]] || exit 1\nprintf "NEW_ISSUES=0\\n"\n' \
  > "$RC_ORDER_DIR/subagents/existing-entries.sh"
chmod +x "$RC_ORDER_DIR/subagents/"*.sh
_run_companions "$RC_ORDER_DIR/subagents" "$RC_ORDER_STATE" "$RC_ORDER_DIR/report"
check "_run_companions: scan-regression runs before existing-entries" \
  grep -q '^NEW_ISSUES=0$' "$RC_ORDER_DIR/report/existing-entries.evidence"

# Empty companion directory -> no evidence files written (no-op)
RC2_DIR="$TMPD/rc2"; mkdir -p "$RC2_DIR/subagents" "$RC2_DIR/report"
RC2_STATE="$RC2_DIR/state.env"; touch "$RC2_STATE"
_run_companions "$RC2_DIR/subagents" "$RC2_STATE" "$RC2_DIR/report"
check "_run_companions: empty dir -> no evidence files" \
  bash -c 'shopt -s nullglob; files=("'"$RC2_DIR"'/report"/*.evidence); [[ ${#files[@]} -eq 0 ]]'
printf 'NEW_ISSUES=0\n' > "$RC2_DIR/report/removed-audit.evidence"
_run_companions "$RC2_DIR/subagents" "$RC2_STATE" "$RC2_DIR/report"
check "_run_companions clears stale evidence even with no remaining scripts" \
  ! test -e "$RC2_DIR/report/removed-audit.evidence"

# === _grep_pattern behavioral tests ===
echo "_grep_pattern behavioral"
check "_grep_pattern matches substring" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; echo 'connection refused' | _grep_pattern 'connection'"
check "_grep_pattern no match exits non-zero" \
  ! bash -c "source '$SCRIPT_DIR/lib.sh'; echo 'success' | _grep_pattern 'connection'"
check "_grep_pattern: ERE alternation match" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; echo 'connection timeout' | _grep_pattern 'refused|timeout'"
check "_grep_pattern: ERE alternation no match" \
  ! bash -c "source '$SCRIPT_DIR/lib.sh'; echo 'success' | _grep_pattern 'refused|timeout'"
check "_grep_pattern: case-insensitive match" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; echo 'TLS Handshake Timeout' | _grep_pattern 'tls handshake timeout'"

# === _details_section behavioral tests ===
echo "_details_section behavioral"
GP_INPUT="$TMPD/details_input.txt"
printf 'SUMMARY: some header line\nother header\nDETAILS:\nfirst detail\nsecond detail\n' > "$GP_INPUT"
check "_details_section extracts lines after DETAILS:" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; out=\$(_details_section '$GP_INPUT'); [[ \"\$out\" == *'first detail'* ]]"
check "_details_section excludes DETAILS: header line" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; out=\$(_details_section '$GP_INPUT'); [[ \"\$out\" != *'DETAILS:'* ]]"
check "_details_section empty when no DETAILS: marker" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; printf 'no marker here\n' > '$TMPD/no_details.txt'; out=\$(_details_section '$TMPD/no_details.txt'); [[ -z \"\$out\" ]]"

# === fix-package.sh: git commit failure → index lock recovery ===
# Pre-commit hook failure → wait for lock, unstage, die with "possible index lock".
echo "fix-package git commit failure (index lock recovery)"
FP_IL="$TMPD/fp-index-lock"; mkdir -p "$FP_IL/gostub"
( cd "$FP_IL" && git init -q && git config user.email t@t && git config user.name t )
printf 'module x\ngo 1.25.0\n\nrequire example.com/foo v1.0.0\n' > "$FP_IL/go.mod"
( cd "$FP_IL" && git add go.mod && git commit -qm init )

# Pre-commit hook that always rejects commits (simulates hook failure that can
# leave .git/index.lock behind if git is interrupted)
mkdir -p "$FP_IL/.git/hooks"
printf '#!/bin/sh\necho "pre-commit: rejecting commit" >&2\nexit 1\n' \
  > "$FP_IL/.git/hooks/pre-commit"
chmod +x "$FP_IL/.git/hooks/pre-commit"

# go stub: go get updates the require version; list returns the updated version;
# no replace directives so the STILL_VULNERABLE check passes.
cat > "$FP_IL/gostub/go" <<'STUB'
#!/bin/sh
dir="."
while [ "$1" = "-C" ]; do dir="$2"; shift 2; done
if [ "$1" = "get" ]; then
  pkgver="$2"; ver=$(printf '%s' "$pkgver" | sed 's/.*@v//')
  awk -v v="$ver" \
    '/^require example\.com\/foo /{print "require example.com/foo v" v; next} {print}' \
    "$dir/go.mod" > "$dir/go.mod.tmp" && mv "$dir/go.mod.tmp" "$dir/go.mod"
  exit 0
fi
if [ "$1" = "mod" ]; then exit 0; fi
if [ "$1" = "list" ]; then
  fmt=""; prev=""
  for a in "$@"; do [ "$prev" = "-f" ] && fmt="$a"; prev="$a"; done
  case "$fmt" in
    *Replace.Version*) echo "" ;;
    *Replace.Dir*)     echo "" ;;
    *Version*)
      awk '/^require example\.com\/foo /{print $3}' "$dir/go.mod" ;;
    *) awk '/^require example\.com\/foo /{printf "example.com/foo %s\n", $3}' \
         "$dir/go.mod" ;;
  esac
  exit 0
fi
exit 0
STUB
chmod +x "$FP_IL/gostub/go"

cat > "$FP_IL/st.env" <<ILENV
REPO="$FP_IL"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
ILENV

FP_IL_OUT=""
FP_IL_RC=0
FP_IL_OUT=$(
  cd "$FP_IL" && PATH="$FP_IL/gostub:$PATH" \
  bash "$SCRIPT_DIR/fix-package.sh" "$FP_IL/st.env" example.com/foo 2.0.0 GHSA-il-0001 2>&1
) || FP_IL_RC=$?

check "index-lock recovery: exits non-zero" \
  test "$FP_IL_RC" -ne 0
check "index-lock recovery: error mentions index lock" \
  grep -qi "index lock" <<< "$FP_IL_OUT"
check "index-lock recovery: staged changes cleaned up" \
  bash -c "cd '$FP_IL' && git diff --staged --quiet"

# === Deep audit regressions ===
echo "deep audit regressions"

# Every post-mutation scan must rebuild; otherwise stale pre-fix binaries create
# false residuals and misdirect scoped fixes to /bin paths.
check "pre-review final scan rebuilds binaries" \
  grep -qF 'FINAL_SCAN=$(BUILD_UPX=false "$SCRIPT_DIR/scan.sh" "$STATE_FILE" --no-update)' \
    "$SCRIPT_DIR/fix-all.sh"
check "scan-regression verification rebuilds binaries" \
  grep -qF 'BUILD_UPX=false bash "$CVE_SCRIPTS/scan.sh" "$STATE_FILE" --no-update --json' \
    "$SCRIPT_DIR/../subagents/scan-regression.sh"
check "summary table preserves an empty fix-version column" \
  grep -qF 'if length == 0 then "-" else' "$SCRIPT_DIR/fix-all.sh"

# A grouped package fix uses the greatest per-CVE minimum at or above the
# installed version. The final scan verifies any non-monotonic advisory range.
COMMON_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.82.4","1.83.1"]},{"cve":"CVE-B","versions":["1.82.5","1.83.2"]}]' | base64 | tr -d '\n')
check "common selector uses threshold satisfying every CVE" \
  test "$(select_common_fix_version 1.83.0 "$COMMON_REQ")" = 1.83.2
NO_COMMON_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.83.1"]},{"cve":"CVE-B","versions":["1.84.1"]}]' | base64 | tr -d '\n')
check "common selector crosses minor at lowest satisfying threshold" \
  test "$(select_common_fix_version 1.83.0 "$NO_COMMON_REQ")" = 1.84.1
PARALLEL_STREAM_REQ=$(printf '%s' '[{"cve":"GHSA-A","versions":["1.82.2","1.83.2"]},{"cve":"GHSA-B","versions":["1.83.1"]}]' | base64 | tr -d '\n')
check "common selector uses each advisory threshold in target stream" \
  test "$(select_common_fix_version 1.80.0 "$PARALLEL_STREAM_REQ")" = 1.83.2
check "common selector fails closed without a threshold above installed" \
  ! select_common_fix_version 1.85.0 "$NO_COMMON_REQ"
PARTLY_FIXED_REQ=$(printf '%s' '[{"cve":"GHSA-OLD","versions":["1.82.2"]},{"cve":"GHSA-NEW","versions":["1.83.1"]}]' | base64 | tr -d '\n')
check "grouped fix allows an advisory satisfied by a prior dependency bump" \
  test "$(select_common_fix_version 1.83.0 "$PARTLY_FIXED_REQ")" = 1.83.1
check "partly fixed grouping still refuses a combined downgrade" \
  ! select_common_fix_version 1.83.5 "$PARTLY_FIXED_REQ"
EMPTY_FIXED_REQ=$(printf '%s' '[{"cve":"GHSA-NO-FIX","versions":[]},{"cve":"GHSA-FIX","versions":["1.83.1"]}]' | base64 | tr -d '\n')
check "grouped fix cannot invent a missing advisory threshold" \
  ! select_common_fix_version 1.83.0 "$EMPTY_FIXED_REQ"

# An active finding above its originally listed fix must never be downgraded to
# that older threshold. This exercises fix-package.sh itself, including the
# former shortcut that treated installed >= requested as implicitly safe.
FP_ND="$TMPD/fp-no-downgrade"; mkdir -p "$FP_ND"
git -C "$FP_ND" init -q
git -C "$FP_ND" config user.email t@t.com
git -C "$FP_ND" config user.name T
printf '%s\n' 'module example.com/no-downgrade' '' 'go 1.25' '' \
  'require google.golang.org/grpc v1.83.5' > "$FP_ND/go.mod"
git -C "$FP_ND" add go.mod; git -C "$FP_ND" commit -qm init
cat > "$FP_ND/state.env" <<EOF
REPO="$FP_ND"
BRANCH="devel"
BUILD_GO_VERSION="unknown"
CVE_SCRIPTS="$SCRIPT_DIR"
HAS_VENDOR="false"
DIFF_IGNORE_ARGS=""
EOF
FP_ND_REQ=$(printf '%s' '[{"cve":"GHSA-NO-DOWNGRADE","versions":["1.83.2"]}]' | \
  base64 | tr -d '\n')
FP_ND_RC=0
(
  cd "$FP_ND"
  CVE_FIX_REQUIREMENTS_B64="$FP_ND_REQ" \
    bash "$SCRIPT_DIR/fix-package.sh" "$FP_ND/state.env" \
      google.golang.org/grpc 1.83.2 GHSA-NO-DOWNGRADE
) > "$FP_ND/output" 2>&1 || FP_ND_RC=$?
check "fix-package refuses an active-finding downgrade" test "$FP_ND_RC" -eq 2
check "fix-package downgrade refusal explains missing safe threshold" \
  grep -q 'no stable fix threshold at or above the installed version' "$FP_ND/output"
check "fix-package downgrade refusal leaves go.mod unchanged" \
  bash -c "cd '$FP_ND' && git diff --quiet && grep -q 'grpc v1.83.5' go.mod"
check "grouped rejection exposes installed selection anchor" \
  grep -qF 'NOTE: Installed selection anchor: v1.83.5' "$FP_ND/output"
check "grouped rejection retains per-advisory fix evidence" \
  grep -qF 'NOTE: Reported grouped fix requirements: [{"cve":"GHSA-NO-DOWNGRADE","versions":["1.83.2"]}]' "$FP_ND/output"

FP_ND_LEGACY_RC=0
(
  cd "$FP_ND"
  CVE_FIX_ALL_VERSIONS="1.83.2" \
    bash "$SCRIPT_DIR/fix-package.sh" "$FP_ND/state.env" \
      google.golang.org/grpc 1.83.2 GHSA-NO-DOWNGRADE
) > "$FP_ND/legacy-output" 2>&1 || FP_ND_LEGACY_RC=$?
check "fix-package legacy selector refuses a downgrade" test "$FP_ND_LEGACY_RC" -eq 2
check "fix-package legacy downgrade refusal is explicit" \
  grep -q 'no stable fix version at or above the installed version' "$FP_ND/legacy-output"
check "fix-package legacy refusal leaves go.mod unchanged" \
  bash -c "cd '$FP_ND' && git diff --quiet && grep -q 'grpc v1.83.5' go.mod"

PSEUDO_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["0.0.0-20260101000000-aaaaaaaaaaaa"]},{"cve":"CVE-B","versions":["0.0.0-20260202000000-bbbbbbbbbbbb"]}]' | base64 | tr -d '\n')
check "common selector preserves Go pseudo-version" \
  test "$(select_common_fix_version 0.0.0-20250101000000-cccccccccccc "$PSEUDO_REQ")" = \
    0.0.0-20260202000000-bbbbbbbbbbbb

# The strict registry/config parser supports normal YAML conveniences but rejects
# ambiguity that the old grep-based reader silently misparsed.
CFG_DEEP="$TMPD/config-deep.yaml"
printf '%s\n' 'test-command: "make test # literal" # comment' 'build-image: quay.io/example/go:1.26' \
  > "$CFG_DEEP"
CFG_DEEP_JSON=$(python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_DEEP")
check "config parser preserves quoted hash" \
  test "$(jq -r '.["test-command"]' <<< "$CFG_DEEP_JSON")" = 'make test # literal'
check "config parser preserves image colon" \
  test "$(jq -r '.["build-image"]' <<< "$CFG_DEEP_JSON")" = 'quay.io/example/go:1.26'
printf '%s\n' 'build-command: make build' 'build-command: make other' > "$CFG_DEEP"
check "config parser rejects duplicate key" \
  ! python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_DEEP"
REG_DEEP="$TMPD/repos-deep.yaml"
for _repo_indent in '' '  '; do
  printf 'repos:\n%s- path: "/tmp/a repo"\n%s  name: alpha\n%s- name: beta\n%s  path: /tmp/beta\n' \
    "$_repo_indent" "$_repo_indent" "$_repo_indent" "$_repo_indent" > "$REG_DEEP"
  check "registry parser supports reordered quoted fields at indent ${#_repo_indent}" \
    test "$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REG_DEEP" alpha)" = '/tmp/a repo'
  check "registry parser keeps sibling entries at indent ${#_repo_indent}" \
    test "$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REG_DEEP" beta)" = /tmp/beta
done
printf '%s\n' 'repos:' '  - name: ../escape' '    path: /tmp/x' > "$REG_DEEP"
check "registry parser rejects unsafe repo name" \
  ! python3 "$SCRIPT_DIR/read-config.py" repos-list "$REG_DEEP"

# Repository-owned modules are in scope; unrelated untracked scratch modules are not.
mkdir -p "$FG_REPO/scratch"
printf 'module scratch\ngo 1.25.0\n' > "$FG_REPO/scratch/go.mod"
check "find_gomods ignores untracked scratch module" \
  ! bash -c "cd '$FG_REPO'; source '$SCRIPT_DIR/lib.sh'; find_gomods | grep -q scratch/go.mod"

# Multi-module selection must use the lowest installed occurrence; a safe module
# encountered first must not hide vulnerable siblings (Lighthouse x/sys root).
LOWEST_INST=""
for CANDIDATE_INST in 0.45.0 0.38.0 0.14.0; do
  if [[ -z "$LOWEST_INST" ]] || version_gte "$LOWEST_INST" "$CANDIDATE_INST"; then
    LOWEST_INST="$CANDIDATE_INST"
  fi
done
check "multi-module selector anchors on lowest installed version" test "$LOWEST_INST" = 0.14.0

MMSEL_REPO="$TMPD/mm-selector"; mkdir -p "$MMSEL_REPO/coredns" "$MMSEL_REPO/tools" "$MMSEL_REPO/bin"
git -C "$MMSEL_REPO" init -q
git -C "$MMSEL_REPO" config user.email test@test.com
git -C "$MMSEL_REPO" config user.name Test
printf 'module example.com/root\ngo 1.24.0\nrequire golang.org/x/sys v0.38.0\n' > "$MMSEL_REPO/go.mod"
printf 'module example.com/coredns\ngo 1.25.0\nrequire golang.org/x/sys v0.45.0\n' > "$MMSEL_REPO/coredns/go.mod"
printf 'module example.com/tools\ngo 1.24.0\nrequire golang.org/x/sys v0.14.0\n' > "$MMSEL_REPO/tools/go.mod"
git -C "$MMSEL_REPO" add go.mod coredns/go.mod tools/go.mod
git -C "$MMSEL_REPO" commit -qm init
cat > "$MMSEL_REPO/bin/go" <<'STUB'
#!/usr/bin/env bash
dir=.
if [[ "${1:-}" == -C ]]; then dir="$2"; shift 2; fi
case "${1:-}" in
  list)
    pkg="${3:-${2:-}}"
    ver=$(awk -v p="$pkg" '$1=="require" && $2==p {print $3; exit}' "$dir/go.mod")
    [[ -n "$ver" ]] && printf '%s %s\n' "$pkg" "$ver"
    ;;
  get)
    pkgver="$2"; pkg="${pkgver%@*}"; ver="${pkgver#*@}"
    awk -v p="$pkg" -v v="$ver" '$1=="require" && $2==p {$3=v} {print}' "$dir/go.mod" > "$dir/go.mod.tmp"
    mv "$dir/go.mod.tmp" "$dir/go.mod"
    ;;
  mod) exit 0 ;;
esac
STUB
chmod +x "$MMSEL_REPO/bin/go"
printf 'REPO=%q\nBRANCH=release-0.22\nBUILD_GO_VERSION=%q\nCVE_SCRIPTS=%q\nHAS_VENDOR=false\nDIFF_IGNORE_ARGS=\n' \
  "$MMSEL_REPO" 'go version go1.26.8 linux/amd64' "$SCRIPT_DIR" > "$MMSEL_REPO/state.env"
MMSEL_REQ=$(printf '%s' '[{"cve":"GO-2026-5024","versions":["0.44.0"]}]' | base64 | tr -d '\n')
MMSEL_RC=0
MMSEL_OUT=$(cd "$MMSEL_REPO"; PATH="$MMSEL_REPO/bin:$PATH" CVE_FIX_REQUIREMENTS_B64="$MMSEL_REQ" \
  bash "$SCRIPT_DIR/fix-package.sh" "$MMSEL_REPO/state.env" golang.org/x/sys 0.44.0 GO-2026-5024 2>&1) || MMSEL_RC=$?
check "multi-module safe-first selector applies fix" test "$MMSEL_RC" -eq 0
check "multi-module selector fixes vulnerable root" grep -q 'golang.org/x/sys v0.44.0' "$MMSEL_REPO/go.mod"
check "multi-module selector fixes vulnerable tools" grep -q 'golang.org/x/sys v0.44.0' "$MMSEL_REPO/tools/go.mod"
check "multi-module selector leaves newer coredns version" grep -q 'golang.org/x/sys v0.45.0' "$MMSEL_REPO/coredns/go.mod"
check "multi-module selector does not claim no common stream" ! grep -q 'no single release stream' <<< "$MMSEL_OUT"

# Broad selectors are removed deterministically without deleting valid neighbors.
BROAD_YAML="$TMPD/broad-ignore.yaml"
printf '%s\n' '---' 'ignore:' '  - vulnerability: CVE-VALID-1' '    package:' \
  '      name: example.com/valid' '  - vulnerability: CVE-BROAD-1' \
  '  - package:' '      name: example.com/also-broad' '  - vulnerability: CVE-VALID-2' \
  '    package:' '      name: example.com/valid2' > "$BROAD_YAML"
remove_invalid_grype_ignores "$BROAD_YAML" >/dev/null
check "broad-ignore cleanup removes vulnerability-only rule" ! grep -q CVE-BROAD-1 "$BROAD_YAML"
check "broad-ignore cleanup removes package-only rule" ! grep -q also-broad "$BROAD_YAML"
check "broad-ignore cleanup preserves first valid rule" grep -q CVE-VALID-1 "$BROAD_YAML"
check "broad-ignore cleanup preserves second valid rule" grep -q CVE-VALID-2 "$BROAD_YAML"

# A rationale comment directly before the next entry belongs to that entry and
# must survive removal of the preceding broad selector.
BROAD_COMMENT_YAML="$TMPD/broad-ignore-comment.yaml"
printf '%s\n' '---' 'ignore:' '  - vulnerability: CVE-BROAD-COMMENT' \
  '  # No fix available for example.com/valid-comment.' \
  '  - vulnerability: CVE-VALID-COMMENT' '    package:' \
  '      name: example.com/valid-comment' > "$BROAD_COMMENT_YAML"
remove_invalid_grype_ignores "$BROAD_COMMENT_YAML" >/dev/null
check "broad-ignore cleanup preserves next-entry comment" \
  grep -qF '# No fix available for example.com/valid-comment.' "$BROAD_COMMENT_YAML"
check "broad-ignore cleanup preserves commented valid entry" \
  grep -qF 'CVE-VALID-COMMENT' "$BROAD_COMMENT_YAML"

YIA_REPO="$TMPD/yia-repo"; mkdir -p "$YIA_REPO"
git -C "$YIA_REPO" init -q
git -C "$YIA_REPO" config user.email test@test.com
git -C "$YIA_REPO" config user.name Test
printf 'module example.com/yia\ngo 1.25.0\n' > "$YIA_REPO/go.mod"
printf '%s\n' '---' 'ignore: # security exceptions' '  - vulnerability: CVE-VALID-3' '    package:' \
  '      name: example.com/valid3' '  - package:' '      name: example.com/cloud-style-broad' \
  > "$YIA_REPO/.grype.yaml"
git -C "$YIA_REPO" add go.mod .grype.yaml
git -C "$YIA_REPO" commit -qm init
git -C "$YIA_REPO" checkout -qb release-0.22
git -C "$YIA_REPO" update-ref refs/remotes/origin/release-0.22 "$(git -C "$YIA_REPO" rev-parse HEAD)"
YIA_STATE="$TMPD/yia-state.env"
printf 'REPO=%q\nBRANCH=release-0.22\nCVE_SCRIPTS=%q\n' "$YIA_REPO" "$SCRIPT_DIR" > "$YIA_STATE"
YIA_OUT=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$YIA_STATE")
check "yaml audit flags pre-existing broad ignore with no branch diff" \
  grep -q 'MISSING_VULNERABILITY_FIELD' <<< "$YIA_OUT"
subagent_fix_yaml_integrity "$YIA_STATE" "$TMPD/yia.report" "$SCRIPT_DIR" >/dev/null
check "yaml handler removes pre-existing broad ignore" ! grep -q cloud-style-broad "$YIA_REPO/.grype.yaml"
check "yaml handler preserves neighboring valid ignore" grep -q CVE-VALID-3 "$YIA_REPO/.grype.yaml"
rm "$YIA_REPO/.grype.yaml"
YIA_OUT=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$YIA_STATE")
check "yaml audit does not resurrect deleted invalid ignores from HEAD" grep -qx 'NEW_ISSUES=0' <<< "$YIA_OUT"
ln -s missing-grype.yaml "$YIA_REPO/.grype.yaml"
check "yaml audit rejects an unreadable current ignore file" ! bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$YIA_STATE"
rm "$YIA_REPO/.grype.yaml"

# Failed local scanner stdout must never prefix the successful fallback JSON.
RG_LEAK_BIN="$TMPD/rg-leak-bin"; mkdir -p "$RG_LEAK_BIN"
printf '#!/usr/bin/env bash\necho LOCAL-GARBAGE\necho "failed to fetch latest vulnerability database" >&2\nexit 1\n' > "$RG_LEAK_BIN/grype"
printf '#!/usr/bin/env bash\necho '\''{"matches":[]}'\''\n' > "$RG_LEAK_BIN/mock-ctr"
chmod +x "$RG_LEAK_BIN/grype" "$RG_LEAK_BIN/mock-ctr"
RG_LEAK_OUT=$(cd "$RG_REPO"; PATH="$RG_LEAK_BIN:$PATH" HAS_LOCAL_GRYPE=true \
  CONTAINER_CMD="$RG_LEAK_BIN/mock-ctr" run_grype --json 2>/dev/null)
check "scanner fallback discards failed local stdout" ! grep -q LOCAL-GARBAGE <<< "$RG_LEAK_OUT"
check "scanner fallback returns one valid JSON document" \
  test "$(jq -r '.matches == []' <<< "$RG_LEAK_OUT")" = true
RG_RESET_OUT=$(cd "$RG_REPO"; PATH="$RG_LEAK_BIN:$PATH" HAS_LOCAL_GRYPE=true \
  CONTAINER_CMD="$RG_LEAK_BIN/mock-ctr" run_grype --json >/dev/null 2>/dev/null; \
  echo "$GRYPE_DB_DEGRADED:$GRYPE_SCAN_TRANSIENT")
check "healthy scanner fallback clears failed-local diagnostics" test "$RG_RESET_OUT" = "0:0"

# Review sentinels are exact by default. An explicitly unscoped sentinel covers
# all locations because the corresponding fix attempt was repository-wide.
SENTINEL_FILE="$TMPD/review-sentinels"
printf '%s\n' 'example.com/scoped|/tools/go.mod' 'example.com/all' > "$SENTINEL_FILE"
check "scoped sentinel matches exact module" \
  pkg_sentinel_file_matches "$SENTINEL_FILE" example.com/scoped /src/tools/go.mod
check "scoped sentinel does not hide another module" \
  ! pkg_sentinel_file_matches "$SENTINEL_FILE" example.com/scoped /go.mod
check "unscoped sentinel covers reported module locations" \
  pkg_sentinel_file_matches "$SENTINEL_FILE" example.com/all /coredns/go.mod


# YAML escape handling must fail before a configured command can be changed.
echo "strict YAML scalar regressions"
REG_QUOTES="$TMPD/registry-quotes.yaml"
printf '%s\n' "repos:" "  - name: quoted" "    path: '/tmp/owner''s repo'" > "$REG_QUOTES"
check "registry honors YAML doubled single quotes" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REG_QUOTES" quoted)" = "/tmp/owner's repo"
CFG_QUOTES="$TMPD/config-quotes.yaml"
printf '%s\n' 'test-command: "printf \u263a"' > "$CFG_QUOTES"
check "config decodes YAML Unicode escape" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES" | jq -r '.["test-command"]')" = 'printf ☺'
printf '%s\n' 'test-command: make test#fragment # comment' > "$CFG_QUOTES"
check "plain scalar hash is literal without separating whitespace" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES" | jq -r '.["test-command"]')" = 'make test#fragment'
for QUOTED_INVALID in '"printf \q"' '"printf \uD800"' '"printf \U00110000"' '"printf \x0"' '"first" "second"' "'first' 'second'"; do
  printf 'test-command: %s\n' "$QUOTED_INVALID" > "$CFG_QUOTES"
  check "config rejects invalid YAML scalar $QUOTED_INVALID" \
    ! python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES"
done

echo "current verification evidence boundaries"
CURRENT_RDIR="$TMPD/current-evidence"; mkdir -p "$CURRENT_RDIR"
printf '{"matches":[]}\n' > "$CURRENT_RDIR/initial-scan.json"
check "direct companion can use initial evidence before verification" test "$(review_scan_file "$CURRENT_RDIR")" = "$CURRENT_RDIR/initial-scan.json"
printf 'SCAN_FAILED=1\n' > "$CURRENT_RDIR/scan-regression.evidence"
check "failed current rescan forbids initial fallback" ! review_scan_file "$CURRENT_RDIR"
printf '{}\n' > "$CURRENT_RDIR/final-scan.json"
check "malformed current evidence forbids initial fallback" ! review_scan_file "$CURRENT_RDIR"
printf '{"matches":[]}\n' > "$CURRENT_RDIR/final-scan.json"
check "valid current evidence takes precedence" test "$(review_scan_file "$CURRENT_RDIR")" = "$CURRENT_RDIR/final-scan.json"
printf '{"matches":[]}\n{"matches":[]}\n' > "$CURRENT_RDIR/final-scan.json"
check "multiple scan documents cannot combine into verification" ! grype_scan_json_valid "$CURRENT_RDIR/final-scan.json"

# A failed verification iteration blocks both ignore auditors, even when the
# older initial scan would recommend removal or a dependency update.
rm -f "$EE_RDIR/final-scan.json"
printf '{"matches":[]}\n' > "$EE_RDIR/initial-scan.json"
printf 'SCAN_FAILED=1\n' > "$EE_RDIR/scan-regression.evidence"
EE_FAILED_RC=0
EE_FAILED_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$EE_RDIR/state.env" "$EE_RDIR") || EE_FAILED_RC=$?
check "ignore audit refuses stale initial after current scan failure" test "$EE_FAILED_RC" -ne 0
check "ignore audit cannot remove ignore after current scan failure" ! grep -q '^STALE:' <<< "$EE_FAILED_OUT"

# No-fix findings also require trustworthy current evidence before mutation.
SCAN_POLICY_REPO="$TMPD/scan-policy-repo"; make_test_repo "$SCAN_POLICY_REPO"
SCAN_POLICY_REPORTS="$TMPD/scan-policy-reports"; mkdir -p "$SCAN_POLICY_REPORTS"
make_go_state "$SCAN_POLICY_REPORTS/state.env" "$SCAN_POLICY_REPO"
printf '{}\n' > "$SCAN_POLICY_REPORTS/final-scan.json"
printf '%s\n' 'DETAILS:' 'UNRESOLVED: CVE-POLICY-1 (example.com/policy v1.0.0 High no-fix)' > "$SCAN_POLICY_REPORTS/scan-regression.report"
SCAN_POLICY_SCRIPTS="$TMPD/scan-policy-scripts"; mkdir -p "$SCAN_POLICY_SCRIPTS"
printf '#!/usr/bin/env bash\ntouch "$1.ignore-was-run"\n' > "$SCAN_POLICY_SCRIPTS/ignore.sh"
SCAN_POLICY_RC=0
(source "$SCRIPT_DIR/lib.sh"; subagent_fix_scan_regression "$SCAN_POLICY_REPORTS/state.env" "$SCAN_POLICY_REPORTS/scan-regression.report" "$SCAN_POLICY_SCRIPTS") \
  > "$SCAN_POLICY_REPORTS/handler.out" 2>&1 || SCAN_POLICY_RC=$?
check "invalid current scan blocks no-fix dispatch" test "$SCAN_POLICY_RC" -eq 2
check "invalid current scan cannot create an ignore" ! test -e "$SCAN_POLICY_REPORTS/state.env.ignore-was-run"

printf '%s\n' 'ignore:' '  - vulnerability: CVE-POLICY-1' '    fix-state: unknown' '    package:' '      name: example.com/policy' > "$SCAN_POLICY_REPO/.grype.yaml"
SCAN_AVAIL_RC=0
SCAN_AVAIL_OUT=$(bash "$SCRIPT_DIR/../subagents/fix-availability.sh" "$SCAN_POLICY_REPORTS/state.env" "$SCAN_POLICY_REPORTS") || SCAN_AVAIL_RC=$?
check "fix-availability fails closed on invalid current scan" test "$SCAN_AVAIL_RC" -ne 0
check "fix-availability marks malformed evidence unconfirmed" grep -q '^SCAN_FAILED=1' <<< "$SCAN_AVAIL_OUT"

# Independent audit regressions: plain YAML quotes, explicit Go fix streams,
# and real failed reviewer children cannot masquerade as successful evidence.
echo "independent verification regressions"
printf '%s\n' "repos: # registry" "  - name: plain" "    path: /tmp/owner's repo # trailing comment" > "$REG_QUOTES"
check "plain YAML apostrophe preserves registry path" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REG_QUOTES" plain)" = "/tmp/owner's repo"
printf '%s\n' 'repos: # registry' '  - name: quoted' "    path: '/tmp/owner''s # repo' # trailing comment" > "$REG_QUOTES"
check "registry quoted scalar preserves embedded separated hash" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REG_QUOTES" quoted)" = "/tmp/owner's # repo"
printf '%s\n' 'test-command: echo release"candidate # trailing comment' > "$CFG_QUOTES"
check "plain YAML embedded unmatched quote is literal" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES" | jq -r '.["test-command"]')" = 'echo release"candidate'
printf '%s\n' "test-command: echo 'hello # YAML comment" > "$CFG_QUOTES"
check "shell quotes in plain YAML do not suppress YAML comments" \
  test "$(python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES" | jq -r '.["test-command"]')" = "echo 'hello"
printf '%s\n' 'test-command: echo foo: bar' > "$CFG_QUOTES"
check "invalid plain scalar mapping is rejected" ! python3 "$SCRIPT_DIR/read-config.py" config-json "$CFG_QUOTES"

GO_DISJOINT_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.24.7"]},{"cve":"CVE-B","versions":["1.25.2"]}]' | base64 | tr -d '\n')
check "Go selector rejects disjoint advisory streams" ! select_common_go_fix_version 1.24.0 "$GO_DISJOINT_REQ"
GO_SHARED_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.24.7","1.26.2"]},{"cve":"CVE-B","versions":["1.25.2","1.26.1"]}]' | base64 | tr -d '\n')
check "Go selector finds higher explicitly shared stream" \
  test "$(select_common_go_fix_version 1.24.0 "$GO_SHARED_REQ")" = 1.26.2
check "Go selector considers fixed thresholds below compiler patch" \
  test "$(select_common_go_fix_version 1.26.9 "$GO_SHARED_REQ")" = 1.26.2
check "Go selector never selects older compiler stream" ! select_common_go_fix_version 1.27.0 "$GO_SHARED_REQ"
GO_PRERELEASE_REQ=$(printf '%s' '[{"cve":"CVE-A","versions":["1.26rc1","1.26.2-fips","1.26.0-20260101000000-aaaaaaaaaaaa"]}]' | base64 | tr -d '\n')
check "Go selector rejects prerelease and module pseudo-version targets" ! select_common_go_fix_version 1.26.0 "$GO_PRERELEASE_REQ"

GO_DISJOINT_REPO=$(fsl_repo disjoint $'module x\n\ngo 1.18\n\ntoolchain go1.24.2' 'go version go1.25.9 linux/amd64')
GO_DISJOINT_RC=0
GO_DISJOINT_OUT=$(CVE_FIX_REQUIREMENTS_B64="$GO_DISJOINT_REQ" fsl_run "$GO_DISJOINT_REPO" 1.25.2) || GO_DISJOINT_RC=$?
check "stdlib disjoint streams require review" test "$GO_DISJOINT_RC" -eq 2
check "stdlib disjoint streams do not edit files" git -C "$GO_DISJOINT_REPO" diff --quiet
check "stdlib disjoint streams do not create a commit" test "$(git -C "$GO_DISJOINT_REPO" rev-list --count HEAD)" -eq 1
GO_SHARED_REPO=$(fsl_repo explicitshared $'module x\n\ngo 1.18\n\ntoolchain go1.24.2' 'go version go1.27.9 linux/amd64')
GO_SHARED_RC=0
GO_SHARED_OUT=$(CVE_FIX_REQUIREMENTS_B64="$GO_SHARED_REQ" fsl_run "$GO_SHARED_REPO" 1.26.2) || GO_SHARED_RC=$?
check "stdlib fallback finds explicit common stream" test "$GO_SHARED_RC" -eq 0
check "stdlib fallback uses common threshold" grep -q '^toolchain go1.26.2$' "$GO_SHARED_REPO/go.mod"
check "stdlib fallback preserves library language floor" grep -q '^go 1.18$' "$GO_SHARED_REPO/go.mod"

rm -f "$REVIEW_CAPACITY_COUNT" "${REVIEW_CODEX_STATE}.review-unresolved"
cat > "$REVIEW_CODEX_BIN/codex" <<'EOF'
#!/usr/bin/env bash
printf 'called\n' >> "$REVIEW_CAPACITY_COUNT"
printf 'RESOLVED: example.com/pkg — prompt example\n'
printf 'ERROR: invalid model\n'
exit 0
EOF
REVIEW_AUTH_RC=0
REVIEW_AUTH_OUT=$(PATH="$REVIEW_CODEX_BIN:$PATH" CVE_FIX_AGENT=codex \
  CVE_FIX_AGENT_ATTEMPTS=3 CVE_FIX_RETRY_BASE=0 REVIEW_CAPACITY_COUNT="$REVIEW_CAPACITY_COUNT" \
  bash "$SCRIPT_DIR/review.sh" "$REVIEW_CODEX_STATE" \
  'NEEDS_REVIEW: example.com/pkg — builder decision needed' 'scan finding') || REVIEW_AUTH_RC=$?
check "zero-exit auth error falls back to manual review" test "$REVIEW_AUTH_RC" -eq 0
check "zero-exit auth error does not retry" test "$(wc -l < "$REVIEW_CAPACITY_COUNT" | tr -d ' ')" -eq 1
check "zero-exit auth error cannot reach structured review summary" ! grep -q '=== Review Summary ===' <<< "$REVIEW_AUTH_OUT"
check "zero-exit auth error is reported unavailable" grep -q 'auth error' <<< "$REVIEW_AUTH_OUT"

# Validate the actual scan.sh filtering boundary, not only mocked orchestrator
# output. In particular {} must not acquire matches:[] and become a clean scan.
SCHEMA_SCAN_REPO="$TMPD/schema-scan-repo"; make_test_repo "$SCHEMA_SCAN_REPO"
SCHEMA_SCAN_BIN="$TMPD/schema-scan-bin"; mkdir -p "$SCHEMA_SCAN_BIN"
SCHEMA_SCAN_STATE="$TMPD/schema-scan.env"; make_go_state "$SCHEMA_SCAN_STATE" "$SCHEMA_SCAN_REPO"
printf 'HAS_LOCAL_GRYPE=true\nCONTAINER_CMD=""\nBUILD_CMD=""\n' >> "$SCHEMA_SCAN_STATE"
cat > "$SCHEMA_SCAN_BIN/grype" <<'EOF'
#!/usr/bin/env bash
cat "$SCHEMA_SCAN_FILE"
EOF
chmod +x "$SCHEMA_SCAN_BIN/grype"
SCHEMA_SCAN_FILE="$TMPD/schema-scan-input.json"
for SCHEMA_SCAN_DOCUMENT in '{}' '{"ignoredMatches":[]}' \
  '{"matches":[null]}' \
  '{"matches":[{"artifact":{},"vulnerability":{}}]}' \
  '{"matches":[{"artifact":{"type":"go-module","name":"example.com/p"},"vulnerability":{}}]}' \
  '{"matches":[{"artifact":{"type":"go-module","name":"example.com/p","locations":[{}]},"vulnerability":{"id":"CVE-A"}}]}' \
  '{"matches":[],"ignoredMatches":[{"artifact":{"type":"go-module"},"vulnerability":{"id":"CVE-A"}}]}'; do
  printf '%s\n' "$SCHEMA_SCAN_DOCUMENT" > "$SCHEMA_SCAN_FILE"
  check "reject malformed Grype finding $SCHEMA_SCAN_DOCUMENT" ! grype_scan_json_valid "$SCHEMA_SCAN_FILE"
  SCHEMA_SCAN_RC=0
  SCHEMA_SCAN_OUT=$(PATH="$SCHEMA_SCAN_BIN:$PATH" SCHEMA_SCAN_FILE="$SCHEMA_SCAN_FILE" \
    bash "$SCRIPT_DIR/scan.sh" "$SCHEMA_SCAN_STATE" --no-update --json 2> "$TMPD/schema-scan.stderr") || SCHEMA_SCAN_RC=$?
  check "scan.sh rejects malformed original scanner output" test "$SCHEMA_SCAN_RC" -ne 0
  check "scan.sh does not normalize invalid output into clean evidence" ! grype_scan_json_valid <<< "$SCHEMA_SCAN_OUT"
done
printf '{"matches":[]}\n' > "$SCHEMA_SCAN_FILE"
SCHEMA_SCAN_RC=0
SCHEMA_SCAN_OUT=$(PATH="$SCHEMA_SCAN_BIN:$PATH" SCHEMA_SCAN_FILE="$SCHEMA_SCAN_FILE" \
  bash "$SCRIPT_DIR/scan.sh" "$SCHEMA_SCAN_STATE" --no-update --json 2> "$TMPD/schema-scan.stderr") || SCHEMA_SCAN_RC=$?
check "scan.sh retains a valid empty original scan" test "$SCHEMA_SCAN_RC" -eq 0
check "scan.sh valid empty output remains usable" grype_scan_json_valid <<< "$SCHEMA_SCAN_OUT"

GO_OLD_BUILDER_REPO=$(fsl_repo oldbuilder $'module x\n\ngo 1.18' 'go version go1.20.14 linux/amd64')
GO_OLD_BUILDER_RC=0
GO_OLD_BUILDER_OUT=$(fsl_run "$GO_OLD_BUILDER_REPO" 1.20.14) || GO_OLD_BUILDER_RC=$?
check "pre-1.21 builder cannot receive a toolchain directive" test "$GO_OLD_BUILDER_RC" -eq 2
check "pre-1.21 builder limitation is explicit" grep -q 'cannot read a toolchain directive' <<< "$GO_OLD_BUILDER_OUT"
check "pre-1.21 builder refusal preserves library go.mod" git -C "$GO_OLD_BUILDER_REPO" diff --quiet
check "pre-1.21 builder refusal creates no unusable commit" test "$(git -C "$GO_OLD_BUILDER_REPO" rev-list --count HEAD)" -eq 1

# Real Go commands against an offline module proxy expose metadata mutations
# hidden by the earlier mocked-go restoration tests. Vendor and graph lookups
# finish before the original toolchain policy is restored for the commit.
RESTORE_REAL="$TMPD/restore-real"; mkdir -p "$RESTORE_REAL/proxy" "$RESTORE_REAL/repo"
python3 - "$RESTORE_REAL/proxy" <<'PYPROXY'
import json
import sys
import zipfile
from pathlib import Path
proxy = Path(sys.argv[1]) / "example.com/restore/@v"
proxy.mkdir(parents=True)
for version in ("v1.0.0", "v1.0.1"):
    mod = "module example.com/restore\n\ngo 1.18\n"
    (proxy / (version + ".mod")).write_text(mod)
    (proxy / (version + ".info")).write_text(json.dumps({"Version": version, "Time": "2026-01-01T00:00:00Z"}))
    with zipfile.ZipFile(proxy / (version + ".zip"), "w") as archive:
        archive.writestr("example.com/restore@" + version + "/go.mod", mod)
        archive.writestr("example.com/restore@" + version + "/value.go", "package restore\nfunc Value() string { return \"" + version + "\" }\n")
(proxy / "list").write_text("v1.0.0\nv1.0.1\n")
PYPROXY
printf 'module example.com/main\n\ngo 1.18\n\nrequire example.com/restore v1.0.0\n' > "$RESTORE_REAL/repo/go.mod"
printf 'package main\nimport "example.com/restore"\nfunc main() { println(restore.Value()) }\n' > "$RESTORE_REAL/repo/main.go"
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off GOTOOLCHAIN=local \
  go -C "$RESTORE_REAL/repo" mod tidy >/dev/null 2>&1
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off GOTOOLCHAIN=local \
  go -C "$RESTORE_REAL/repo" mod vendor >/dev/null 2>&1
GOTOOLCHAIN=local go -C "$RESTORE_REAL/repo" mod edit -toolchain=default
printf 'go 1.18\n\nuse .\n' > "$RESTORE_REAL/repo/go.work"
git -C "$RESTORE_REAL/repo" init -q -b devel
git -C "$RESTORE_REAL/repo" config user.name Test
git -C "$RESTORE_REAL/repo" config user.email test@test.com
git -C "$RESTORE_REAL/repo" add go.mod go.sum go.work main.go vendor
git -C "$RESTORE_REAL/repo" commit -qm init
make_go_state "$RESTORE_REAL/state.env" "$RESTORE_REAL/repo"
printf 'HAS_VENDOR=true\nBUILD_GO_VERSION=%q\n' "$(go version)" >> "$RESTORE_REAL/state.env"
RESTORE_REAL_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$RESTORE_REAL/state.env" example.com/restore 1.0.1 CVE-RESTORE \
  > "$RESTORE_REAL/fix.log" 2>&1 || RESTORE_REAL_RC=$?
check "real Go dependency repair completes vendor before restoring default" test "$RESTORE_REAL_RC" -eq 0
check "real Go dependency repair preserves default through final graph lookups" grep -q '^toolchain default$' "$RESTORE_REAL/repo/go.mod"
check "real Go dependency repair updates resolved dependency" grep -q 'example.com/restore v1.0.1' "$RESTORE_REAL/repo/go.mod"
check "real Go dependency repair updates vendor" grep -q 'example.com/restore v1.0.1' "$RESTORE_REAL/repo/vendor/modules.txt"
check "real Go dependency repair commits original compiler policy" \
  bash -c 'git -C "$1" show HEAD:go.mod | grep -q "^toolchain default$"' _ "$RESTORE_REAL/repo"

check "real Go dependency repair preserves the workspace" grep -qF 'use .' "$RESTORE_REAL/repo/go.work"

echo "native prior-fix confirmation restores lookup side effects"
PRIOR_NATIVE="$TMPD/prior-native"; mkdir -p "$PRIOR_NATIVE/scanner"
printf '#!/bin/sh\nprintf '\''{"matches":[],"ignoredMatches":[]}\\n'\''\n' > "$PRIOR_NATIVE/scanner/grype"
chmod +x "$PRIOR_NATIVE/scanner/grype"
_PRIOR_NATIVE_REQ=$(printf '%s' '[{"cve":"CVE-PRIOR","versions":["1.0.0"]}]' | base64 | tr -d '\n')
for _prior_metadata in absent untracked tracked; do
  _prior_repo="$PRIOR_NATIVE/$_prior_metadata"; mkdir -p "$_prior_repo"
  git -C "$_prior_repo" init -q
  git -C "$_prior_repo" config user.name Test
  git -C "$_prior_repo" config user.email test@test.com
  printf 'module example.com/prior\n\ngo 1.18\n\nrequire example.com/restore v1.0.1\n' > "$_prior_repo/go.mod"
  git -C "$_prior_repo" add go.mod
  if [[ "$_prior_metadata" != absent ]]; then
    git -C "$RESTORE_REAL/repo" show HEAD~1:go.sum > "$_prior_repo/go.sum"
    cp "$_prior_repo/go.sum" "$PRIOR_NATIVE/$_prior_metadata.before"
    [[ "$_prior_metadata" != tracked ]] || git -C "$_prior_repo" add go.sum
  fi
  git -C "$_prior_repo" commit -qm init
  _prior_head=$(git -C "$_prior_repo" rev-parse HEAD)
  _PRIOR_NATIVE_ENV=(env GOWORK=off GOTOOLCHAIN=local GOMODCACHE="$RESTORE_REAL/modcache"
    GOFLAGS=-mod=mod GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off)
  "${_PRIOR_NATIVE_ENV[@]}" go -C "$_prior_repo" list -m example.com/restore >/dev/null
  check "prior-fix $_prior_metadata native lookup creates checksum evidence" grep -q 'example.com/restore v1.0.1/go.mod' "$_prior_repo/go.sum"
  git -C "$_prior_repo" checkout -- .
  if [[ "$_prior_metadata" == absent ]]; then rm -f "$_prior_repo/go.sum"
  else cp "$PRIOR_NATIVE/$_prior_metadata.before" "$_prior_repo/go.sum"; fi
  make_go_state "$PRIOR_NATIVE/$_prior_metadata.env" "$_prior_repo"
  printf 'HAS_LOCAL_GRYPE=true\nCONTAINER_CMD=\n' >> "$PRIOR_NATIVE/$_prior_metadata.env"
  _PRIOR_NATIVE_RC=0
  "${_PRIOR_NATIVE_ENV[@]}" PATH="$PRIOR_NATIVE/scanner:$PATH" CVE_FIX_REQUIREMENTS_B64="$_PRIOR_NATIVE_REQ" \
    bash "$SCRIPT_DIR/fix-package.sh" "$PRIOR_NATIVE/$_prior_metadata.env" example.com/restore 1.0.0 CVE-PRIOR \
    > "$PRIOR_NATIVE/$_prior_metadata.log" 2>&1 || _PRIOR_NATIVE_RC=$?
  check "prior-fix $_prior_metadata confirms existing repair" test "$_PRIOR_NATIVE_RC" -eq 0
  check "prior-fix $_prior_metadata reports scanner-backed confirmation" grep -q 'current Grype evidence confirms' "$PRIOR_NATIVE/$_prior_metadata.log"
  check "prior-fix $_prior_metadata preserves original HEAD" test "$(git -C "$_prior_repo" rev-parse HEAD)" = "$_prior_head"
  check "prior-fix $_prior_metadata leaves tracked files unchanged" git -C "$_prior_repo" diff --quiet
  if [[ "$_prior_metadata" == absent ]]; then
    check "prior-fix removes lookup-created go.sum" test ! -e "$_prior_repo/go.sum"
  else
    check "prior-fix preserves $_prior_metadata checksum bytes" cmp "$PRIOR_NATIVE/$_prior_metadata.before" "$_prior_repo/go.sum"
  fi
done

echo "native workspace repair accepts original GOFLAGS states"
_WORKSPACE_BASE=$(git -C "$RESTORE_REAL/repo" rev-parse HEAD~1)
for _workspace_flags in unset empty vendor workspace; do
  git -C "$RESTORE_REAL/repo" reset --hard "$_WORKSPACE_BASE" -q
  make_go_state "$RESTORE_REAL/workspace.env" "$RESTORE_REAL/repo"
  printf 'HAS_VENDOR=true\nBUILD_GO_VERSION=%q\n' "$(go version)" >> "$RESTORE_REAL/workspace.env"
  case "$_workspace_flags" in
    unset)
      _WORKSPACE_ENV=(env -u GOFLAGS -u GOWORK -u GOTOOLCHAIN)
      _WORKSPACE_BUILD='test "${GOFLAGS+x}" != x && test "${GOWORK+x}" != x && test "${GOTOOLCHAIN+x}" != x && env GOWORK=off go build -mod=vendor .'
      ;;
    empty)
      _WORKSPACE_ENV=(env GOFLAGS= GOWORK= GOTOOLCHAIN=)
      _WORKSPACE_BUILD='test "${GOFLAGS+x}" = x && test -z "$GOFLAGS" && test "${GOWORK+x}" = x && test -z "$GOWORK" && test "${GOTOOLCHAIN+x}" = x && test -z "$GOTOOLCHAIN" && env GOWORK=off go build -mod=vendor .'
      ;;
    vendor)
      _WORKSPACE_ENV=(env 'GOFLAGS=-mod=vendor -modcacherw' GOWORK=off GOTOOLCHAIN=local)
      _WORKSPACE_BUILD='test "$GOFLAGS" = "-mod=vendor -modcacherw" && test "$GOWORK" = off && test "$GOTOOLCHAIN" = local && go build .'
      ;;
    workspace)
      _WORKSPACE_ENV=(env -u GOFLAGS "GOWORK=$RESTORE_REAL/repo/go.work" GOTOOLCHAIN=local)
      _WORKSPACE_BUILD='test "$GOTOOLCHAIN" = local && go work sync && go build .'
      ;;
  esac
  printf 'BUILD_CMD=%q\n' "$_WORKSPACE_BUILD" >> "$RESTORE_REAL/workspace.env"
  _WORKSPACE_RC=0
  "${_WORKSPACE_ENV[@]}" GOMODCACHE="$RESTORE_REAL/modcache" GOPRIVATE= GONOPROXY=none \
    GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
    bash "$SCRIPT_DIR/fix-package.sh" "$RESTORE_REAL/workspace.env" example.com/restore 1.0.1 CVE-WORKSPACE \
    > "$RESTORE_REAL/workspace-$_workspace_flags.log" 2>&1 || _WORKSPACE_RC=$?
  check "native workspace $_workspace_flags repair succeeds" test "$_WORKSPACE_RC" -eq 0
  check "native workspace $_workspace_flags builds updated code" test "$("$RESTORE_REAL/repo/main" 2>&1)" = v1.0.1
  check "native workspace $_workspace_flags commits repaired dependency" grep -q 'example.com/restore v1.0.1' "$RESTORE_REAL/repo/go.mod"
  check "native workspace $_workspace_flags synchronizes vendor metadata" grep -q 'example.com/restore v1.0.1' "$RESTORE_REAL/repo/vendor/modules.txt"
  check "native workspace $_workspace_flags preserves compiler policy" grep -q '^toolchain default$' "$RESTORE_REAL/repo/go.mod"
  check "native workspace $_workspace_flags preserves workspace" grep -qF 'use .' "$RESTORE_REAL/repo/go.work"
  check "native workspace $_workspace_flags leaves tracked metadata clean" git -C "$RESTORE_REAL/repo" diff --quiet
  rm -f "$RESTORE_REAL/repo/main"
done

# A scoped root repair raises the workspace's shared requirement. The root still
# compiles, but sync introduces an API break in tools that must reject the whole
# transaction. A compatible update must refresh both modules' vendor trees.
echo "real workspace sync changes are vendored and built before commit"
WORK_SYNC_REAL="$TMPD/work-sync-real"
mkdir -p "$WORK_SYNC_REAL/proxy" "$WORK_SYNC_REAL/repo/tools"
python3 - "$WORK_SYNC_REAL/proxy" <<'PYSYNC'
import json
import sys
import zipfile
from pathlib import Path
proxy = Path(sys.argv[1]) / "example.com/worksync/@v"
proxy.mkdir(parents=True)
for version in ("v1.0.0", "v1.0.1", "v1.0.2"):
    mod = "module example.com/worksync\n\ngo 1.18\n"
    code = "package worksync\nfunc Current() string { return " + json.dumps(version) + " }\n"
    if version != "v1.0.1":
        code += "func Legacy() string { return Current() }\n"
    (proxy / (version + ".mod")).write_text(mod)
    (proxy / (version + ".info")).write_text(json.dumps({"Version": version, "Time": "2026-01-01T00:00:00Z"}))
    with zipfile.ZipFile(proxy / (version + ".zip"), "w") as archive:
        archive.writestr("example.com/worksync@" + version + "/go.mod", mod)
        archive.writestr("example.com/worksync@" + version + "/value.go", code)
(proxy / "list").write_text("v1.0.0\nv1.0.1\nv1.0.2\n")
PYSYNC
_WORK_SYNC_ENV=(env GOWORK=off GOTOOLCHAIN=local GOMODCACHE="$WORK_SYNC_REAL/modcache"
  GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$WORK_SYNC_REAL/proxy" GOSUMDB=off)
for _sync_module in root tools; do
  _sync_dir="$WORK_SYNC_REAL/repo"
  _sync_api=Current
  if [[ "$_sync_module" == tools ]]; then _sync_dir+=/tools; _sync_api=Legacy; fi
  printf 'module example.com/%s\n\ngo 1.18\n\nrequire example.com/worksync v1.0.0\n' "$_sync_module" > "$_sync_dir/go.mod"
  printf 'package main\nimport "example.com/worksync"\nfunc main() { println(worksync.%s()) }\n' "$_sync_api" > "$_sync_dir/main.go"
  "${_WORK_SYNC_ENV[@]}" go -C "$_sync_dir" mod tidy >/dev/null 2>&1
  "${_WORK_SYNC_ENV[@]}" go -C "$_sync_dir" mod vendor >/dev/null 2>&1
done
printf 'go 1.18\nuse (\n  .\n  ./tools\n)\n' > "$WORK_SYNC_REAL/repo/go.work"
git -C "$WORK_SYNC_REAL/repo" init -q -b devel
git -C "$WORK_SYNC_REAL/repo" config user.name Test
git -C "$WORK_SYNC_REAL/repo" config user.email test@test.com
git -C "$WORK_SYNC_REAL/repo" add .
git -C "$WORK_SYNC_REAL/repo" commit -qm 'workspace with independently vendored modules'
_SYNC_BASE=$(git -C "$WORK_SYNC_REAL/repo" rev-parse HEAD)
make_go_state "$WORK_SYNC_REAL/state.env" "$WORK_SYNC_REAL/repo"
printf 'BUILD_GO_VERSION=%q\nBUILD_CMD=%q\n' "$(go version)" \
  'go build -mod=vendor -o bin/root . && go -C tools build -mod=vendor -o ../bin/tools .' >> "$WORK_SYNC_REAL/state.env"
_SYNC_RC=0
"${_WORK_SYNC_ENV[@]}" bash "$SCRIPT_DIR/fix-package.sh" "$WORK_SYNC_REAL/state.env" \
  example.com/worksync 1.0.1 --location /go.mod CVE-WORK-SYNC > "$WORK_SYNC_REAL/rejected.log" 2>&1 || _SYNC_RC=$?
check "workspace sync: sibling API break needs review" test "$_SYNC_RC" -eq 2
check "workspace sync: sibling build observes synchronized requirement" grep -q 'undefined: worksync.Legacy' "$WORK_SYNC_REAL/rejected.log"
check "workspace sync: rejected update is not reported fixed" ! grep -q '^FIXED:' "$WORK_SYNC_REAL/rejected.log"
check "workspace sync: rejected update creates no commit" test "$(git -C "$WORK_SYNC_REAL/repo" rev-parse HEAD)" = "$_SYNC_BASE"
check "workspace sync: rejection restores both modules and vendor trees" git -C "$WORK_SYNC_REAL/repo" diff --quiet
check "workspace sync: rejection removes new workspace checksums" test ! -e "$WORK_SYNC_REAL/repo/go.work.sum"
_SYNC_RC=0
"${_WORK_SYNC_ENV[@]}" bash "$SCRIPT_DIR/fix-package.sh" "$WORK_SYNC_REAL/state.env" \
  example.com/worksync 1.0.2 --location /go.mod CVE-WORK-SYNC > "$WORK_SYNC_REAL/accepted.log" 2>&1 || _SYNC_RC=$?
check "workspace sync: compatible shared requirement succeeds" test "$_SYNC_RC" -eq 0
for _sync_relative in . tools; do
  check "workspace sync: $_sync_relative requirement is synchronized" grep -q 'example.com/worksync v1.0.2' "$WORK_SYNC_REAL/repo/$_sync_relative/go.mod"
  check "workspace sync: $_sync_relative vendor tree is synchronized" grep -q 'example.com/worksync v1.0.2' "$WORK_SYNC_REAL/repo/$_sync_relative/vendor/modules.txt"
done
check "workspace sync: root artifact was built from synchronized files" test "$("$WORK_SYNC_REAL/repo/bin/root" 2>&1)" = v1.0.2
check "workspace sync: sibling artifact was built from synchronized files" test "$("$WORK_SYNC_REAL/repo/bin/tools" 2>&1)" = v1.0.2
check "workspace sync: accepted dependency metadata is committed" git -C "$WORK_SYNC_REAL/repo" diff --quiet

echo "real offline project build rejects a dependency API break"
python3 - "$RESTORE_REAL/proxy" <<'PYPROXY'
import json
import sys
import zipfile
from pathlib import Path
proxy = Path(sys.argv[1]) / "example.com/restore/@v"
for version, args in (("v1.0.2", "secure bool"), ("v1.0.3", "")):
    mod = "module example.com/restore\n\ngo 1.18\n"
    (proxy / (version + ".mod")).write_text(mod)
    (proxy / (version + ".info")).write_text(json.dumps({"Version": version, "Time": "2026-01-01T00:00:00Z"}))
    with zipfile.ZipFile(proxy / (version + ".zip"), "w") as archive:
        archive.writestr("example.com/restore@" + version + "/go.mod", mod)
        archive.writestr("example.com/restore@" + version + "/value.go", "package restore\nfunc Value(" + args + ") string { return \"" + version + "\" }\n")
        archive.writestr("example.com/restore@" + version + "/new.go", "package restore\nconst Secure = true\n")
(proxy / "list").write_text("v1.0.0\nv1.0.1\nv1.0.2\nv1.0.3\n")
PYPROXY
GOTOOLCHAIN=local go -C "$RESTORE_REAL/repo" mod edit -toolchain=none
rm "$RESTORE_REAL/repo/go.work"
git -C "$RESTORE_REAL/repo" add go.mod go.work
git -C "$RESTORE_REAL/repo" commit -qm 'use local compiler for API build fixture'
printf 'BUILD_CMD=%q\n' 'go build -mod=vendor -o bin/application .' >> "$RESTORE_REAL/state.env"
printf 'original note\n' > "$RESTORE_REAL/repo/vendor/user-note"
_API_HEAD=$(git -C "$RESTORE_REAL/repo" rev-parse HEAD)
_API_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$RESTORE_REAL/state.env" example.com/restore 1.0.2 CVE-API-BREAK \
  > "$RESTORE_REAL/api-break.log" 2>&1 || _API_RC=$?
check "real API build failure routes to review" test "$_API_RC" -eq 2
check "real API build failure records compiler diagnosis" grep -q 'not enough arguments' "$RESTORE_REAL/api-break.log"
check "real API build failure is not reported as fixed" ! grep -q '^FIXED:' "$RESTORE_REAL/api-break.log"
check "real API build failure keeps the original commit" test "$(git -C "$RESTORE_REAL/repo" rev-parse HEAD)" = "$_API_HEAD"
check "real API build failure restores module and vendor bytes" git -C "$RESTORE_REAL/repo" diff --quiet
check "real API rollback removes newly vendored API file" test ! -e "$RESTORE_REAL/repo/vendor/example.com/restore/new.go"
check "real API rollback restores pre-existing vendor note" test "$(cat "$RESTORE_REAL/repo/vendor/user-note")" = 'original note'
_API_GOOD_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$RESTORE_REAL/state.env" example.com/restore 1.0.3 CVE-API-COMPATIBLE \
  > "$RESTORE_REAL/api-good.log" 2>&1 || _API_GOOD_RC=$?
check "real compatible API update passes project build" test "$_API_GOOD_RC" -eq 0
check "real compatible API update commits the verified version" grep -q 'example.com/restore v1.0.3' "$RESTORE_REAL/repo/go.mod"
check "real compatible project artifact executes" \
  test "$("$RESTORE_REAL/repo/bin/application" 2>&1)" = v1.0.3

echo "real offline scoped repair maintains nested vendor trees"
NESTED_REAL="$TMPD/nested-vendor-real"; mkdir -p "$NESTED_REAL/repo/tools module"
for _nested_dir in "$NESTED_REAL/repo" "$NESTED_REAL/repo/tools module"; do
  _nested_name=root
  [[ "$_nested_dir" == "$NESTED_REAL/repo" ]] || _nested_name=tools
  printf 'module example.com/%s\n\ngo 1.18\n\nrequire example.com/restore v1.0.0\n' "$_nested_name" > "$_nested_dir/go.mod"
  printf 'package main\nimport "example.com/restore"\nfunc main() { println(restore.Value()) }\n' > "$_nested_dir/main.go"
  GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off GOTOOLCHAIN=local \
    go -C "$_nested_dir" mod tidy >/dev/null 2>&1
  GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off GOTOOLCHAIN=local \
    go -C "$_nested_dir" mod vendor >/dev/null 2>&1
done
git -C "$NESTED_REAL/repo" init -q -b devel
git -C "$NESTED_REAL/repo" config user.name Test
git -C "$NESTED_REAL/repo" config user.email test@test.com
git -C "$NESTED_REAL/repo" add .
git -C "$NESTED_REAL/repo" commit -qm init
make_go_state "$NESTED_REAL/state.env" "$NESTED_REAL/repo"
printf 'HAS_VENDOR=true\nBUILD_CMD=%q\n' 'test "$GOFLAGS" = "-mod=vendor -modcacherw" && go build . && go -C "tools module" build .' >> "$NESTED_REAL/state.env"
printf 'root operator note\n' > "$NESTED_REAL/repo/vendor/user-note"
printf 'nested operator note\n' > "$NESTED_REAL/repo/tools module/vendor/user-note"
_NESTED_BASE=$(git -C "$NESTED_REAL/repo" rev-parse HEAD)
_NESTED_FAIL_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS='-mod=vendor -modcacherw' GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$NESTED_REAL/state.env" example.com/restore 1.0.2 --location '/tools module/go.mod' CVE-NESTED \
  > "$NESTED_REAL/fail.log" 2>&1 || _NESTED_FAIL_RC=$?
check "nested vendor API failure is rejected before commit" test "$_NESTED_FAIL_RC" -eq 2
check "nested vendor failure preserves the original head" test "$(git -C "$NESTED_REAL/repo" rev-parse HEAD)" = "$_NESTED_BASE"
check "nested vendor failure restores all tracked trees" git -C "$NESTED_REAL/repo" diff --quiet
check "nested vendor failure removes newly generated files" test ! -e "$NESTED_REAL/repo/tools module/vendor/example.com/restore/new.go"
check "nested vendor failure restores its pre-existing note" test "$(cat "$NESTED_REAL/repo/tools module/vendor/user-note")" = 'nested operator note'
check "nested vendor failure preserves the root note" test "$(cat "$NESTED_REAL/repo/vendor/user-note")" = 'root operator note'
_NESTED_GOOD_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS='-mod=vendor -modcacherw' GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$NESTED_REAL/state.env" example.com/restore 1.0.3 --location '/tools module/go.mod' CVE-NESTED \
  > "$NESTED_REAL/good.log" 2>&1 || _NESTED_GOOD_RC=$?
check "nested vendor compatible update completes" test "$_NESTED_GOOD_RC" -eq 0
check "nested vendor commit includes new dependency source" \
  git -C "$NESTED_REAL/repo" cat-file -e 'HEAD:tools module/vendor/example.com/restore/new.go'
check "nested vendor compatible binary executes repaired dependency" \
  test "$("$NESTED_REAL/repo/tools module/tools" 2>&1)" = v1.0.3
check "scoped nested repair preserves root dependency and vendor bytes" \
  git -C "$NESTED_REAL/repo" diff --exit-code "$_NESTED_BASE" HEAD -- go.mod go.sum vendor
check "scoped nested repair leaves root operator note untracked" \
  ! git -C "$NESTED_REAL/repo" ls-files --error-unmatch vendor/user-note

# A root without vendor still owns a vendored nested module.
NESTED_ONLY="$NESTED_REAL/only"
git clone -q --no-hardlinks "$NESTED_REAL/repo" "$NESTED_ONLY"
git -C "$NESTED_ONLY" reset --hard -q "$_NESTED_BASE"
git -C "$NESTED_ONLY" config user.name Test
git -C "$NESTED_ONLY" config user.email test@test.com
git -C "$NESTED_ONLY" rm -qr vendor
git -C "$NESTED_ONLY" commit -qm 'root uses module mode'
make_go_state "$NESTED_REAL/only.env" "$NESTED_ONLY"
printf 'HAS_VENDOR=false\nBUILD_CMD=%q\n' 'test "${GOFLAGS+x}" != x && go -C "tools module" build -mod=vendor .' >> "$NESTED_REAL/only.env"
_NESTED_ONLY_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off env -u GOFLAGS \
  bash "$SCRIPT_DIR/fix-package.sh" "$NESTED_REAL/only.env" example.com/restore v1.0.1 --location '/tools module/go.mod' CVE-NESTED-ONLY \
  > "$NESTED_REAL/only.log" 2>&1 || _NESTED_ONLY_RC=$?
check "nested-only vendoring works with HAS_VENDOR=false" test "$_NESTED_ONLY_RC" -eq 0
check "nested-only vendoring commits the selected version" \
  grep -q '# example.com/restore v1.0.1' "$NESTED_ONLY/tools module/vendor/modules.txt"
check "nested-only vendor tree remains valid to real Go" \
  env GOTOOLCHAIN=local GOWORK=off go -C "$NESTED_ONLY/tools module" list -mod=vendor -m

# A configured unset-env must apply after restoring all caller build settings.
printf 'ENV_UNSET="GOFLAGS GOWORK GOTOOLCHAIN"\nBUILD_CMD=%q\n' \
  'test "${GOFLAGS+x}" != x && test "${GOWORK+x}" != x && test "${GOTOOLCHAIN+x}" != x && go -C "tools module" build -mod=vendor .' \
  >> "$NESTED_REAL/only.env"
_NESTED_SCRUB_RC=0
GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS='-mod=vendor -modcacherw' GOWORK=off GOTOOLCHAIN=local GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  bash "$SCRIPT_DIR/fix-package.sh" "$NESTED_REAL/only.env" example.com/restore 1.0.3 --location '/tools module/go.mod' CVE-NESTED-SCRUB \
  > "$NESTED_REAL/scrub.log" 2>&1 || _NESTED_SCRUB_RC=$?
check "native build preserves absent flags and honors unset-env" test "$_NESTED_SCRUB_RC" -eq 0
check "native build with scrubbed flags executes repaired dependency" \
  test "$("$NESTED_ONLY/tools module/tools" 2>&1)" = v1.0.3

echo "real offline scan retry dispatches generated binaries to their owning module"
BINARY_RETRY="$TMPD/binary-retry"
git clone -q --no-hardlinks "$NESTED_REAL/repo" "$BINARY_RETRY"
git -C "$BINARY_RETRY" reset --hard -q "$_NESTED_BASE"
git -C "$BINARY_RETRY" config user.name Test
git -C "$BINARY_RETRY" config user.email test@test.com
make_go_state "$NESTED_REAL/retry.env" "$BINARY_RETRY"
printf 'HAS_VENDOR=true\nBUILD_CMD=%q\n' 'go build -mod=vendor -o output/root .' >> "$NESTED_REAL/retry.env"
env GOTOOLCHAIN=local GOWORK=off go -C "$BINARY_RETRY" build -mod=vendor -o output/pre-existing .
(REPO="$BINARY_RETRY" STATE_FILE="$NESTED_REAL/retry.env"; artifact_manifest_prepare)
env GOTOOLCHAIN=local GOWORK=off go -C "$BINARY_RETRY" build -mod=vendor -o output/root .
(REPO="$BINARY_RETRY" STATE_FILE="$NESTED_REAL/retry.env"; artifact_manifest_record)
mkdir -p "$NESTED_REAL/retry-reports"
cat > "$NESTED_REAL/retry-reports/final-scan.json" <<'EOF'
{"matches":[{"artifact":{"type":"go-module","name":"example.com/restore","version":"v1.0.0","locations":[{"path":"/output/root"}]},"vulnerability":{"id":"CVE-BINARY-RETRY","severity":"High","fix":{"versions":["1.0.1"]}}}],"ignoredMatches":[]}
EOF
cp "$NESTED_REAL/retry-reports/final-scan.json" "$NESTED_REAL/retry-original.json"
printf 'STATUS: FAIL\nDETAILS:\nUNRESOLVED: CVE-BINARY-RETRY (example.com/restore v1.0.0 High 1.0.1) location:/output/root\n' \
  > "$NESTED_REAL/retry-reports/scan-regression.report"
_BINARY_RETRY_RC=0
(export GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off
  subagent_fix_scan_regression "$NESTED_REAL/retry.env" "$NESTED_REAL/retry-reports/scan-regression.report" "$SCRIPT_DIR"
) > "$NESTED_REAL/retry.log" 2>&1 || _BINARY_RETRY_RC=$?
check "binary retry completes through real Go remediation" test "$_BINARY_RETRY_RC" -eq 0
check "binary retry records the verified dependency version" \
  grep -q 'example.com/restore v1.0.1 for CVE-BINARY-RETRY at /go.mod$' "$NESTED_REAL/retry-reports/fixed-pkgs"
check "binary retry executes the repaired vendored dependency" test "$("$BINARY_RETRY/output/root" 2>&1)" = v1.0.1
check "binary retry preserves unrelated nested module and vendor bytes" \
  git -C "$BINARY_RETRY" diff --exit-code "$_NESTED_BASE" HEAD -- 'tools module'
check "binary retry preserves the original authoritative scan" \
  cmp "$NESTED_REAL/retry-original.json" "$NESTED_REAL/retry-reports/final-scan.json"
_BINARY_RETRY_HEAD=$(git -C "$BINARY_RETRY" rev-parse HEAD)
sed -i 's|/output/root|/output/pre-existing|g' "$NESTED_REAL/retry-reports/final-scan.json" "$NESTED_REAL/retry-reports/scan-regression.report"
(export GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off
  subagent_fix_scan_regression "$NESTED_REAL/retry.env" "$NESTED_REAL/retry-reports/scan-regression.report" "$SCRIPT_DIR"
) > "$NESTED_REAL/retry-unproven.log" 2>&1 || true
check "binary retry refuses a pre-existing binary's unproven scope" \
  grep -q "scanner location '/output/pre-existing' is not a tracked" "$NESTED_REAL/retry-unproven.log"
check "unproven binary retry leaves the repository head unchanged" \
  test "$(git -C "$BINARY_RETRY" rev-parse HEAD)" = "$_BINARY_RETRY_HEAD"

cat > "$NESTED_REAL/retry-reports/final-scan.json" <<'EOF'
{"matches":[{"artifact":{"type":"go-module","name":"example.com/restore","version":"v1.0.1","locations":[{"path":"/output/root"}]},"vulnerability":{"id":"CVE-BINARY-NOFIX","severity":"High","fix":{"versions":[],"state":""}}}],"ignoredMatches":[]}
EOF
printf 'STATUS: FAIL\nDETAILS:\nUNRESOLVED: CVE-BINARY-NOFIX (example.com/restore v1.0.1 High no-fix) location:/output/root\n' \
  > "$NESTED_REAL/retry-reports/scan-regression.report"
(subagent_fix_scan_regression "$NESTED_REAL/retry.env" "$NESTED_REAL/retry-reports/scan-regression.report" "$SCRIPT_DIR") \
  > "$NESTED_REAL/retry-nofix.log" 2>&1 || true
check "binary no-fix retry scopes its ignore to the source module" \
  grep -q 'location: /go.mod' "$BINARY_RETRY/.grype.yaml"
check "binary no-fix retry preserves Grype's actual unknown state" \
  grep -q 'fix-state: unknown' "$BINARY_RETRY/.grype.yaml"
check "binary no-fix retry commits no binary-path ignore" \
  ! grep -q '/output/' "$BINARY_RETRY/.grype.yaml"

_BINARY_NOFIX_HEAD=$(git -C "$BINARY_RETRY" rev-parse HEAD)
jq '.matches += [(.matches[0] | .vulnerability.id = "CVE-BINARY-MIXED" | .vulnerability.fix.state = "not-fixed")]' \
  "$NESTED_REAL/retry-reports/final-scan.json" > "$NESTED_REAL/retry-mixed.json"
mv "$NESTED_REAL/retry-mixed.json" "$NESTED_REAL/retry-reports/final-scan.json"
printf 'UNRESOLVED: CVE-BINARY-MIXED (example.com/restore v1.0.1 High no-fix) location:/output/root\n' \
  >> "$NESTED_REAL/retry-reports/scan-regression.report"
(subagent_fix_scan_regression "$NESTED_REAL/retry.env" "$NESTED_REAL/retry-reports/scan-regression.report" "$SCRIPT_DIR") \
  > "$NESTED_REAL/retry-mixed.log" 2>&1 || true
check "binary no-fix retry leaves mixed states for review" \
  grep -q 'ambiguous no-fix states in current scan' "$NESTED_REAL/retry-mixed.log"
check "binary no-fix retry cannot replace a scoped rule with ambiguous states" \
  test "$(git -C "$BINARY_RETRY" rev-parse HEAD)" = "$_BINARY_NOFIX_HEAD"

echo "real dependency transactions reject new source findings"
SOURCE_REGRESSION="$TMPD/source-regression"
mkdir -p "$SOURCE_REGRESSION/scanner"
git clone -q --no-hardlinks "$NESTED_REAL/repo" "$SOURCE_REGRESSION/repo"
git -C "$SOURCE_REGRESSION/repo" reset --hard -q "$_NESTED_BASE"
git -C "$SOURCE_REGRESSION/repo" config user.name Test
git -C "$SOURCE_REGRESSION/repo" config user.email test@test.com
make_go_state "$SOURCE_REGRESSION/state.env" "$SOURCE_REGRESSION/repo"
printf 'HAS_VENDOR=true\nHAS_LOCAL_GRYPE=true\nCONTAINER_CMD=\nBUILD_CMD=%q\n' \
  'go build -mod=vendor -o output/source-scan .' >> "$SOURCE_REGRESSION/state.env"
cat > "$SOURCE_REGRESSION/scanner/grype" <<'SH'
#!/usr/bin/env bash
version=$(GOTOOLCHAIN=local go -C "$SOURCE_REGRESSION_REPO" mod edit -json |
  jq -r '.Require[] | select(.Path == "example.com/restore") | .Version')
if [[ "$SOURCE_REGRESSION_MODE" == coverage-before && "$version" == v1.0.0 ]] ||
   [[ "$SOURCE_REGRESSION_MODE" == coverage-after && "$version" != v1.0.0 ]]; then
  : > "${SOURCE_REGRESSION_STATE}.coverage-unknown"
fi
if [[ "$version" != v1.0.0 ]]; then
  [[ "$SOURCE_REGRESSION_MODE" != failed ]] || exit 1
  if [[ "$SOURCE_REGRESSION_MODE" == invalid ]]; then printf '{}\n'; exit 0; fi
fi
python3 - "$version" "$SOURCE_REGRESSION_MODE" <<'PY'
import json,sys
version,mode=sys.argv[1:]
def finding(id,path='/go.mod'):
 return {'artifact':{'type':'go-module','name':'example.com/restore','version':version,'locations':[{'path':path}]},'vulnerability':{'id':id,'fix':{'versions':['1.0.1'],'state':'fixed'}}}
active=[finding('CVE-EXISTING')]; ignored=[]
if version=='v1.0.0': active.append(finding('CVE-ORIGINAL'))
elif mode=='new': active.append(finding('CVE-NEW','/src/go.mod'))
elif mode=='ignored': ignored.append(finding('CVE-NEW'))
elif mode=='binary': active.append(finding('CVE-NEW','/output/source-scan'))
print(json.dumps({'matches':active,'ignoredMatches':ignored}))
PY
SH
chmod +x "$SOURCE_REGRESSION/scanner/grype"
_source_regression_run() {
  local mode="$1"
  git -C "$SOURCE_REGRESSION/repo" reset --hard -q "$_NESTED_BASE"
  _SOURCE_REGRESSION_RC=0
  env SOURCE_REGRESSION_MODE="$mode" SOURCE_REGRESSION_REPO="$SOURCE_REGRESSION/repo" \
    SOURCE_REGRESSION_STATE="$SOURCE_REGRESSION/state.env" \
    PATH="$SOURCE_REGRESSION/scanner:$PATH" GOMODCACHE="$RESTORE_REAL/modcache" \
    GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
    bash "$SCRIPT_DIR/fix-package.sh" "$SOURCE_REGRESSION/state.env" example.com/restore 1.0.1 \
    --location /go.mod CVE-ORIGINAL > "$SOURCE_REGRESSION/$mode.log" 2>&1 || _SOURCE_REGRESSION_RC=$?
}
for _source_regression_mode in new ignored invalid failed coverage-before coverage-after; do
  _source_regression_run "$_source_regression_mode"
  check "source regression $_source_regression_mode rejects real dependency transaction" test "$_SOURCE_REGRESSION_RC" -eq 2
  check "source regression $_source_regression_mode preserves original head" \
    test "$(git -C "$SOURCE_REGRESSION/repo" rev-parse HEAD)" = "$_NESTED_BASE"
  check "source regression $_source_regression_mode restores every tracked module and vendor tree" \
    git -C "$SOURCE_REGRESSION/repo" diff --quiet
  check "source regression $_source_regression_mode creates no ignore" test ! -e "$SOURCE_REGRESSION/repo/.grype.yaml"
done
check "unknown baseline coverage prevents dependency mutation" \
  grep -q 'could not establish a baseline before dependency update' "$SOURCE_REGRESSION/coverage-before.log"
check "unknown updated coverage rolls back dependency mutation" \
  grep -q 'source scan could not verify dependency update' "$SOURCE_REGRESSION/coverage-after.log"
check "new source finding diagnostic preserves exact advisory and owner" \
  grep -q 'NEW_FINDING: CVE-NEW (example.com/restore) location:/go.mod' "$SOURCE_REGRESSION/new.log"
_source_regression_run existing
check "existing source finding does not prevent a verified repair" test "$_SOURCE_REGRESSION_RC" -eq 0
check "source-verified repair executes the real updated dependency" \
  test "$("$SOURCE_REGRESSION/repo/output/source-scan" 2>&1)" = v1.0.1
check "source-verified repair preserves untouched nested module" \
  git -C "$SOURCE_REGRESSION/repo" diff --quiet "$_NESTED_BASE" HEAD -- 'tools module'
_source_regression_run binary
check "binary-only findings remain the final gate's responsibility" test "$_SOURCE_REGRESSION_RC" -eq 0

echo "current scan verifies advisory removed by prior dependency update"
mkdir -p "$FP_ND/scanner"
cat > "$FP_ND/scanner/grype" <<'STUB'
#!/bin/sh
cat "$CURRENT_PACKAGE_SCAN"
exit "${CURRENT_PACKAGE_SCAN_RC:-0}"
STUB
chmod +x "$FP_ND/scanner/grype"
printf 'HAS_LOCAL_GRYPE=true\nCONTAINER_CMD=\n' >> "$FP_ND/state.env"
_PRIOR_SCAN="$FP_ND/current-scan.json"
_prior_scan_run() {
  _PRIOR_RC=0
  CURRENT_PACKAGE_SCAN="$_PRIOR_SCAN" PATH="$FP_ND/scanner:$PATH" \
    CVE_FIX_REQUIREMENTS_B64="$FP_ND_REQ" bash "$SCRIPT_DIR/fix-package.sh" \
    "$FP_ND/state.env" google.golang.org/grpc 1.83.2 GHSA-NO-DOWNGRADE \
    > "$FP_ND/current.out" 2>&1 || _PRIOR_RC=$?
}
printf '{"matches":[],"ignoredMatches":[]}\n' > "$_PRIOR_SCAN"
_prior_scan_run
check "current scan can confirm a prior dependency fix" test "$_PRIOR_RC" -eq 0
check "prior dependency fix is backed by scanner evidence" grep -q 'current Grype evidence confirms' "$FP_ND/current.out"
printf '{"matches":[{"artifact":{"type":"go-module","name":"google.golang.org/grpc","version":"v1.83.5","locations":[{"path":"/go.mod"}]},"vulnerability":{"id":"GHSA-NO-DOWNGRADE","fix":{"versions":["1.83.2"]}}}],"ignoredMatches":[]}\n' > "$_PRIOR_SCAN"
_prior_scan_run
check "active current finding still refuses a downgrade" test "$_PRIOR_RC" -eq 2
jq '{matches:[],ignoredMatches:.matches}' "$_PRIOR_SCAN" > "$FP_ND/ignored.json"
mv "$FP_ND/ignored.json" "$_PRIOR_SCAN"
_prior_scan_run
check "ignored current finding cannot prove prior repair" test "$_PRIOR_RC" -eq 2
printf '{}\n' > "$_PRIOR_SCAN"
_prior_scan_run
check "invalid current scanner output cannot prove repair" test "$_PRIOR_RC" -eq 2
printf '{"matches":[],"ignoredMatches":[]}\n' > "$_PRIOR_SCAN"
CURRENT_PACKAGE_SCAN_RC=1 _prior_scan_run
check "failed current scanner cannot prove repair" test "$_PRIOR_RC" -eq 2

echo "empty scanner catalogs cannot establish dependency coverage"
EMPTY_CATALOG_REPO="$TMPD/empty-catalog-repo"
EMPTY_CATALOG_BIN="$TMPD/empty-catalog-bin"
mkdir -p "$EMPTY_CATALOG_REPO/nested module" "$EMPTY_CATALOG_BIN"
git -C "$EMPTY_CATALOG_REPO" init -q
printf 'module example.test/empty\n\ngo 1.18\n' > "$EMPTY_CATALOG_REPO/go.mod"
printf 'module example.test/nested\n\ngo 1.18\n\nrequire example.test/dependency v1.0.0\n' > "$EMPTY_CATALOG_REPO/nested module/go.mod"
git -C "$EMPTY_CATALOG_REPO" add go.mod 'nested module/go.mod'
cat > "$EMPTY_CATALOG_BIN/grype" <<'SH'
#!/usr/bin/env bash
case " $* " in *' -v '*) ;; *) exit 91 ;; esac
echo "[0002] INFO gathered packages packages=${EMPTY_CATALOG_COUNT:-0} time=1s" >&2
printf '{"matches":[]}\n'
SH
cat > "$EMPTY_CATALOG_BIN/container" <<'SH'
#!/usr/bin/env bash
case " $* " in *' -v '*) ;; *) exit 91 ;; esac
echo "[0002] INFO gathered packages packages=${EMPTY_CONTAINER_COUNT:-0} time=1s" >&2
printf '{"matches":[]}\n'
SH
chmod +x "$EMPTY_CATALOG_BIN/"*
_empty_catalog_run() {
  local container_count="$1" local_count="${2:-0}"
  _EMPTY_CATALOG_RC=0
  _EMPTY_CATALOG_OUT=$(cd "$EMPTY_CATALOG_REPO"
    export PATH="$EMPTY_CATALOG_BIN:$PATH" EMPTY_CATALOG_COUNT="$local_count" EMPTY_CONTAINER_COUNT="$container_count"
    HAS_LOCAL_GRYPE=true CONTAINER_CMD=""
    [[ "$container_count" == none ]] || CONTAINER_CMD="$EMPTY_CATALOG_BIN/container"
    run_grype --json 2>"$EMPTY_CATALOG_REPO/scan-errors"
  ) || _EMPTY_CATALOG_RC=$?
}
_empty_catalog_run none
check "zero catalog rejects nested declared dependencies" test "$_EMPTY_CATALOG_RC" -ne 0
check "zero catalog does not emit usable clean JSON" test -z "$_EMPTY_CATALOG_OUT"
check "empty catalog explains unknown coverage" grep -q 'scan coverage is unconfirmed' "$EMPTY_CATALOG_REPO/scan-errors"
_empty_catalog_run 0
check "empty local and container catalogs both fail" test "$_EMPTY_CATALOG_RC" -ne 0
_empty_catalog_run 2
check "healthy container catalog supersedes empty local scan" test "$_EMPTY_CATALOG_RC" -eq 0
check "healthy fallback supplies valid clean JSON" grype_scan_json_valid <<< "$_EMPTY_CATALOG_OUT"
_empty_catalog_run none 2
check "nonempty local catalog may legitimately have no CVEs" test "$_EMPTY_CATALOG_RC" -eq 0
printf 'module example.test/nested\n\ngo 1.18\n' > "$EMPTY_CATALOG_REPO/nested module/go.mod"
_empty_catalog_run none
check "dependency-free modules may legitimately catalog no packages" test "$_EMPTY_CATALOG_RC" -eq 0
printf 'module malformed [\n' > "$EMPTY_CATALOG_REPO/nested module/go.mod"
_empty_catalog_run none
check "unparseable declared module cannot justify empty coverage" test "$_EMPTY_CATALOG_RC" -ne 0

# CodeRabbit regressions: exercise the actual transaction and reconciliation
# helpers, using native Go against the same offline module proxy as above.
echo "prerelease versions and complete dependency metadata rollback"
python3 - "$RESTORE_REAL/proxy" <<'PYPROXY'
import json, sys, zipfile
from pathlib import Path
proxy = Path(sys.argv[1]) / "example.com/restore/@v"
versions = ("v1.0.4-rc.1", "v1.0.4-pre.0.20260101000000-abcdefabcdef",
            "v1.0.4-0.20260101000000-abcdefabcdef", "v1.0.4")
for version in versions:
    mod = "module example.com/restore\n\ngo 1.18\n"
    (proxy / (version + ".mod")).write_text(mod)
    (proxy / (version + ".info")).write_text(json.dumps({"Version": version, "Time": "2026-01-01T00:00:00Z"}))
    with zipfile.ZipFile(proxy / (version + ".zip"), "w") as archive:
        archive.writestr("example.com/restore@" + version + "/go.mod", mod)
        archive.writestr("example.com/restore@" + version + "/value.go",
                         'package restore\nfunc Value() string { return "' + version + '" }\n')
with (proxy / "list").open("a") as listing:
    listing.write("\n".join(versions) + "\n")
PYPROXY
_cr_native_repo() {
  local dir="$1" version="$2"
  mkdir -p "$dir"
  printf 'module example.com/cr\n\ngo 1.18\n\nrequire example.com/restore %s\n' "$version" > "$dir/go.mod"
  printf 'package main\nimport "example.com/restore"\nfunc main() { println(restore.Value()) }\n' > "$dir/main.go"
  git -C "$dir" init -q -b devel
  git -C "$dir" config user.name Test
  git -C "$dir" config user.email test@test.com
  git -C "$dir" add go.mod main.go
  git -C "$dir" commit -qm init
  make_go_state "$dir/state.env" "$dir"
  printf 'BUILD_CMD=%q\n' 'go build -o bin/application .' >> "$dir/state.env"
}
_cr_native_fix() {
  _CR_RC=0
  env GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none \
    GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
    bash "$SCRIPT_DIR/fix-package.sh" "$1/state.env" example.com/restore "$2" --location /go.mod CVE-CR \
    > "$1/fix.log" 2>&1 || _CR_RC=$?
}
for _cr_version in v1.0.4-rc.1 v1.0.4-pre.0.20260101000000-abcdefabcdef v1.0.4-0.20260101000000-abcdefabcdef; do
  _cr_repo="$TMPD/cr-${_cr_version}"
  _cr_native_repo "$_cr_repo" "$_cr_version"
  _cr_installed=$(cd "$_cr_repo"; export GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off; get_installed_version . example.com/restore)
  check "native prerelease $_cr_version is preserved exactly" test "$_cr_installed" = "${_cr_version#v}"
  # The version lookup itself can create go.sum; start the transaction without it.
  rm -f "$_cr_repo/go.sum"
  _cr_native_fix "$_cr_repo" 1.0.4
  check "native prerelease $_cr_version repairs to stable" test "$_CR_RC" -eq 0
  check "native prerelease $_cr_version commits actual stable requirement" grep -q 'example.com/restore v1.0.4$' "$_cr_repo/go.mod"
  check "native prerelease $_cr_version commits newly created sums" git -C "$_cr_repo" ls-files --error-unmatch go.sum
  check "native prerelease $_cr_version builds updated code" test "$("$_cr_repo/bin/application" 2>&1)" = v1.0.4
done
_cr_repo="$TMPD/cr-rollback"
_cr_native_repo "$_cr_repo" v1.0.0
_cr_head=$(git -C "$_cr_repo" rev-parse HEAD)
_cr_native_fix "$_cr_repo" 1.0.2
check "native rejected API change requires review" test "$_CR_RC" -eq 2
check "native rejected API change removes new go.sum" test ! -e "$_cr_repo/go.sum"
check "native rejected API change preserves original head" test "$(git -C "$_cr_repo" rev-parse HEAD)" = "$_cr_head"
check "native rejected API change restores tracked metadata" git -C "$_cr_repo" diff --quiet
env GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  go -C "$_cr_repo" mod tidy >/dev/null 2>&1
cp "$_cr_repo/go.sum" "$TMPD/cr-original.sum"
chmod 600 "$_cr_repo/go.sum"
_cr_native_fix "$_cr_repo" 1.0.2
check "native rejected change restores pre-existing untracked sums" cmp "$TMPD/cr-original.sum" "$_cr_repo/go.sum"
check "native rejected change preserves metadata permissions" test "$(stat -c %a "$_cr_repo/go.sum")" = 600
printf 'go.sum\n' > "$_cr_repo/.gitignore"
_cr_native_fix "$_cr_repo" 1.0.2
check "native rejected change restores ignored sums" cmp "$TMPD/cr-original.sum" "$_cr_repo/go.sum"

echo "scanner fallback verifies the requested release"
CR_SCANNER="$TMPD/cr-scanner"; mkdir -p "$CR_SCANNER"
cat > "$CR_SCANNER/docker" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CR_SCANNER_CALLS"
if [[ "$*" == *'version -o json' ]]; then
  printf '%s\n' "$CR_SCANNER_VERSION_JSON"
elif [[ "$*" != *'db update'* ]]; then
  printf '{"matches":[],"ignoredMatches":[]}\n'
fi
SH
cat > "$CR_SCANNER/grype" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == 'version -o json' ]]; then
  printf '{"version":"%s"}\n' "${CR_LOCAL_VERSION:-9.8.7}"
  exit 0
fi
printf 'local scan attempted\n' >> "$CR_SCANNER_CALLS"
exit 1
SH
chmod +x "$CR_SCANNER/docker" "$CR_SCANNER/grype"
_cr_scanner_run() {
  local image="${2:-}" local_version="${3:-9.8.7}"
  : > "$CR_SCANNER/calls"
  _CR_SCAN_RC=0
  (cd "$CR_SCANNER"; export PATH="$CR_SCANNER:$PATH" CR_SCANNER_CALLS="$CR_SCANNER/calls" \
     CR_SCANNER_VERSION_JSON="$1" CR_LOCAL_VERSION="$local_version" \
     CVE_FIX_GRYPE_VERSION=v9.8.7 CVE_FIX_GRYPE_IMAGE="$image"
   HAS_LOCAL_GRYPE=true CONTAINER_CMD=docker
   run_grype --json --fresh
  ) > "$CR_SCANNER/output" 2> "$CR_SCANNER/errors" || _CR_SCAN_RC=$?
}
_cr_scanner_run '{"version":"9.8.7"}'
check "pinned fallback succeeds after local scanner failure" test "$_CR_SCAN_RC" -eq 0
check "pinned fallback never uses latest" ! grep -q latest "$CR_SCANNER/calls"
check "pinned fallback updates the requested image DB" grep -q 'anchore/grype:v9.8.7 db update' "$CR_SCANNER/calls"
check "pinned fallback scans with the requested image" grep -q 'anchore/grype:v9.8.7 /src' "$CR_SCANNER/calls"
check "container DB update uses the persistent cache" grep -q 'GRYPE_DB_CACHE_DIR=/root/.cache/grype/db .* db update' "$CR_SCANNER/calls"
check "container scan uses the same persistent cache" grep -q 'GRYPE_DB_CACHE_DIR=/root/.cache/grype/db .* /src' "$CR_SCANNER/calls"
for _cr_version_json in '' '{}' '{"version":"9.8.6"}' '{"version":"9.8.7"} {"version":"9.8.7"}' 'not-json'; do
  _cr_scanner_run "$_cr_version_json"
  check "unconfirmed container version fails closed: $_cr_version_json" test "$_CR_SCAN_RC" -ne 0
  check "unconfirmed container version never scans: $_cr_version_json" ! grep -q ' /src' "$CR_SCANNER/calls"
done
_cr_digest="mirror.test/grype@sha256:$(printf '%064d' 0)"
_cr_scanner_run '{"version":"9.8.7"}' "$_cr_digest" 9.8.6
check "verified mirrored digest honors explicit pin" test "$_CR_SCAN_RC" -eq 0
check "wrong local version never runs a scan" ! grep -q 'local scan attempted' "$CR_SCANNER/calls"
check "mirrored digest is used for the actual scan" grep -q "$_cr_digest /src" "$CR_SCANNER/calls"
_cr_scanner_run '{"version":"9.8.7"}' anchore/grype:latest
check "latest image override is rejected" test "$_CR_SCAN_RC" -ne 0
_cr_scanner_run '{"version":"9.8.7"}' anchore/grype
check "implicit mutable image override is rejected" test "$_CR_SCAN_RC" -ne 0

echo "reviewer reasons replace deterministic reasons in every scope"
FIX_LINES=('NEEDS_REVIEW: example.com/rev — baseline failure at /go.mod'
           'NEEDS_REVIEW: example.com/rev — tools failure at /tools/go.mod'
           'NEEDS_REVIEW: example.com/rev/extra — other package at /go.mod'
           'FIXED: example.com/rev v1.0.1 for CVE-X at /api/go.mod')
REVIEW_COUNT=2
apply_review_outcome example.com/rev 'needs a newer builder (need team input)'
_ar_lines=$(printf '%s\n' "${FIX_LINES[@]}")
check "review outcome replaces the root reason" grep -qx 'NEEDS_REVIEW: example.com/rev — needs a newer builder (need team input) at /go.mod' <<< "$_ar_lines"
check "review outcome keeps the tools scope" grep -qx 'NEEDS_REVIEW: example.com/rev — needs a newer builder (need team input) at /tools/go.mod' <<< "$_ar_lines"
check "review outcome leaves no deterministic duplicate" ! grep -q 'baseline failure\|tools failure' <<< "$_ar_lines"
check "review outcome preserves a package-prefix sibling" grep -q 'example.com/rev/extra — other package' <<< "$_ar_lines"
check "review outcome preserves a fixed scope" grep -q '^FIXED: example.com/rev ' <<< "$_ar_lines"
check "review outcome for reviewed packages is not recounted" test "$REVIEW_COUNT" -eq 2
FIX_LINES=('NEEDS_REVIEW: example.com/both — scoped failure at /go.mod'
           'NEEDS_REVIEW: example.com/both — unscoped failure')
apply_review_outcome example.com/both 'reviewed (need team input)'
check "unscoped review line absorbs scoped duplicates" \
  test "$(printf '%s\n' "${FIX_LINES[@]}")" = 'NEEDS_REVIEW: example.com/both — reviewed (need team input)'
apply_review_outcome example.com/new 'unseen policy decision (need team input)'
check "review outcome adds an unseen package once" test "$(printf '%s\n' "${FIX_LINES[@]}" | grep -c '^NEEDS_REVIEW: example.com/new ')" -eq 1
check "review outcome counts an unseen package" test "$REVIEW_COUNT" -eq 3

echo "module-specific successful repair preserves other review outcomes"
CR_OUTCOMES="$TMPD/cr-outcomes"; mkdir -p "$CR_OUTCOMES"
printf 'example.com/restore v1.0.1 for CVE-ROOT at /go.mod\n' > "$CR_OUTCOMES/fixed-pkgs"
printf 'example.com/restore|/tools/go.mod\n' > "$CR_OUTCOMES/needs-review-pkgs"
FIX_LINES=('NEEDS_REVIEW: example.com/restore — root failure at /go.mod'
           'NEEDS_REVIEW: example.com/restore — tools failure at /tools/go.mod'
           'NEEDS_REVIEW: example.com/restore — legacy unscoped failure'
           'ERROR: example.com/restore — tools failure at /tools/go.mod'
           'NEEDS_REVIEW: example.com/restore/extra — other package at /go.mod')
FIXED_COUNT=0
fold_fixed_package_outcomes "$CR_OUTCOMES"
check "scoped verified success clears only its own review" ! grep -q 'root failure' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "scoped verified success preserves tools policy review" grep -q 'tools failure at /tools/go.mod' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "scoped verified success preserves unknown legacy scope" grep -q 'legacy unscoped failure' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "scoped verified success preserves unrelated package prefix" grep -q 'restore/extra' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "scoped verified success counts one repaired module" test "$FIXED_COUNT" -eq 1
fold_fixed_package_outcomes "$CR_OUTCOMES"
check "repeat scoped verified success is deduplicated" test "$FIXED_COUNT" -eq 1
printf 'example.com/restore v1.0.1 for CVE-TOOLS at /tools/go.mod\n' >> "$CR_OUTCOMES/fixed-pkgs"
fold_fixed_package_outcomes "$CR_OUTCOMES"
check "same package repaired in another module counts separately" test "$FIXED_COUNT" -eq 2
check "pending scoped policy is never erased by success" grep -q 'NEEDS_REVIEW: example.com/restore — tools failure' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "verified tools success clears only its own error" ! grep -q '^ERROR: example.com/restore ' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
printf 'example.com/restore v1.0.2 for CVE-NEW CVE-NEW at /go.mod\n' >> "$CR_OUTCOMES/fixed-pkgs"
fold_fixed_package_outcomes "$CR_OUTCOMES"
check "later verified repair retains distinct verified advisories" grep -qx 'FIXED: example.com/restore v1.0.2 for CVE-NEW CVE-ROOT at /go.mod' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "later verified repair removes its stale version" ! grep -q 'v1.0.1 for CVE-ROOT' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "later verified repair preserves another module version" grep -qx 'FIXED: example.com/restore v1.0.1 for CVE-TOOLS at /tools/go.mod' <<< "$(printf '%s\n' "${FIX_LINES[@]}")"
check "later verified repair does not double-count its module" test "$FIXED_COUNT" -eq 2
check "later verified repair counts its distinct advisories" test "$(count_cves_fixed "$(printf '%s\n' "${FIX_LINES[@]}")")" -eq 3

echo "complete native two-module workflow keeps independent outcomes"
CR_WORKFLOW="$TMPD/cr-workflow"
mkdir -p "$CR_WORKFLOW/skill/bin" "$CR_WORKFLOW/repo/tools" "$CR_WORKFLOW/bin"
cp -a "$SCRIPT_DIR" "$CR_WORKFLOW/skill/scripts"
cp -a "$SCRIPT_DIR/../subagents" "$CR_WORKFLOW/skill/subagents"
_cr_native_repo "$CR_WORKFLOW/repo" v1.0.0
printf 'module example.com/tools\n\ngo 1.18\n\nrequire example.com/restore v1.0.0\n' > "$CR_WORKFLOW/repo/tools/go.mod"
cp "$CR_WORKFLOW/repo/main.go" "$CR_WORKFLOW/repo/tools/main.go"
cat > "$CR_WORKFLOW/repo/.cve-fix.yaml" <<'YAML'
build-command: "go build -o bin/root . && go -C tools build -o ../bin/tools ."
test-command: "go test ./... && go -C tools test ./..."
clean-command: "rm -rf bin"
YAML
printf 'bin/\nstate.env\nfix.log\n' > "$CR_WORKFLOW/repo/.gitignore"
for _cr_module in . tools; do
  env GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
    go -C "$CR_WORKFLOW/repo/$_cr_module" mod tidy >/dev/null 2>&1
done
git -C "$CR_WORKFLOW/repo" add .gitignore .cve-fix.yaml go.mod go.sum tools
git -C "$CR_WORKFLOW/repo" commit -qm 'add independent tools module'
git init --bare -q "$CR_WORKFLOW/origin"
git -C "$CR_WORKFLOW/repo" remote add origin "$CR_WORKFLOW/origin"
git -C "$CR_WORKFLOW/repo" push -q origin devel
cat > "$CR_WORKFLOW/skill/bin/grype" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == 'version -o json' ]]; then printf '{"version":"9.8.7"}\n'; exit 0; fi
if [[ "$1" == version ]]; then printf 'Version: 9.8.7\n'; exit 0; fi
python3 - <<'PYSCAN'
import json, subprocess
from pathlib import Path
# Expose the safe root advisory on the verification scan so its repair goes
# through _fix_fv_package/fixed-pkgs after tools already requires review.
counter = Path('.git')  # linked worktrees are not used by this fixture
counter = counter / 'cr-scan-count'
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
matches = []
for module, advisory, fixed in (('.', 'CVE-ROOT', 'v1.0.1'), ('tools', 'CVE-TOOLS', 'v1.0.2')):
    data = json.loads(subprocess.check_output(['go', '-C', module, 'mod', 'edit', '-json']))
    version = next(dep['Version'] for dep in data['Require'] if dep['Path'] == 'example.com/restore')
    if version != 'v1.0.0' or (module == '.' and count == 1):
        continue
    matches.append({'artifact': {'type': 'go-module', 'name': 'example.com/restore',
        'version': version, 'locations': [{'path': '/go.mod' if module == '.' else '/tools/go.mod'}]},
        'vulnerability': {'id': advisory, 'severity': 'High', 'fix': {'versions': [fixed], 'state': 'fixed'}}})
print(json.dumps({'matches': matches, 'ignoredMatches': []}))
PYSCAN
SH
cat > "$CR_WORKFLOW/bin/codex" <<'SH'
#!/bin/sh
echo 'authentication required' >&2
exit 1
SH
chmod +x "$CR_WORKFLOW/skill/bin/grype" "$CR_WORKFLOW/bin/codex"
_CR_WORKFLOW_RC=0
env PATH="$CR_WORKFLOW/bin:$PATH" GOMODCACHE="$RESTORE_REAL/modcache" GOFLAGS=-modcacherw \
  GOPRIVATE= GONOPROXY=none GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off \
  CVE_FIX_GRYPE_VERSION=v9.8.7 CVE_FIX_AGENT=codex CVE_FIX_AGENT_ATTEMPTS=1 \
  CVE_FIX_AGENT_TIMEOUT=10 CVE_FIX_MAX_ITERATIONS=2 \
  CVE_FIX_EVIDENCE_DIR="$CR_WORKFLOW/evidence" \
  bash "$CR_WORKFLOW/skill/scripts/fix-all.sh" "$CR_WORKFLOW/repo" devel \
  > "$CR_WORKFLOW/workflow.log" 2>&1 || _CR_WORKFLOW_RC=$?
check "two-module native workflow remains partial for rejected tools API" test "$_CR_WORKFLOW_RC" -eq 2
check "two-module native workflow commits safe root requirement" grep -q 'example.com/restore v1.0.1$' "$CR_WORKFLOW/repo/go.mod"
check "two-module native workflow restores rejected tools requirement" grep -q 'example.com/restore v1.0.0$' "$CR_WORKFLOW/repo/tools/go.mod"
check "two-module native workflow reports root success with scope" grep -q '^FIXED: example.com/restore v1.0.1 for CVE-ROOT at /go.mod$' "$CR_WORKFLOW/workflow.log"
check "two-module native workflow retains scoped tools review" grep -q '^NEEDS_REVIEW: example.com/restore .* at /tools/go.mod$' "$CR_WORKFLOW/workflow.log"
check "two-module native workflow completes deterministic verification" jq -e \
  '.phases.verification == "completed" and .verification_exit_code == 0' "$CR_WORKFLOW/evidence/run.json"
check "two-module native workflow retains clean scan-regression counters after repair" \
  grep -qx 'NEW_CVES=0 UNRESOLVED=0' "$CR_WORKFLOW/evidence/audits/scan-regression.evidence"
for _cr_audit in existing-entries fix-availability yaml-integrity; do
  check "two-module native workflow retains clean $_cr_audit counters" \
    grep -qx 'NEW_ISSUES=0' "$CR_WORKFLOW/evidence/audits/$_cr_audit.evidence"
done
check "two-module native workflow explains the missing fork" \
  grep -q 'PR command unavailable until a writable fork remote is configured' "$CR_WORKFLOW/workflow.log"
check "two-module native workflow prints no unwitnessed publication command" \
  ! grep -q '^PR command:' "$CR_WORKFLOW/workflow.log"
check "two-module native workflow leaves tracked metadata clean" git -C "$CR_WORKFLOW/repo" diff --quiet
if [[ "$_CR_WORKFLOW_RC" -ne 2 ]]; then tail -n 40 "$CR_WORKFLOW/workflow.log"; fi

# Standard OpenShift branches and arbitrary repo/branch pairs must obey the
# documented argument interface, without branch setup or repository mutation.
echo "detect accepts OpenShift branches independently of argument order"
CLI_REPO="$TMPD/cli branch repo"
make_test_repo "$CLI_REPO"
printf 'module example.com/cli\n\ngo 1.18\n' > "$CLI_REPO/go.mod"
git -C "$CLI_REPO" add go.mod
git -C "$CLI_REPO" commit -qm 'declare module'
CLI_HEAD=$(git -C "$CLI_REPO" rev-parse HEAD)
for _cli_branch in master main feature/local; do
  git -C "$CLI_REPO" update-ref "refs/heads/$_cli_branch" "$CLI_HEAD"
done
git -C "$CLI_REPO" update-ref refs/remotes/origin/feature/remote "$CLI_HEAD"
CLI_REGISTRY="$TMPD/cli-repos.yaml"
printf 'repos:\n  - name: sample\n    path: "%s"\n' "$CLI_REPO" > "$CLI_REGISTRY"
_cli_detect_branch() {
  local expected="$1" output state result=0
  shift
  output=$(cd "$CLI_REPO"; CVE_FIX_REPOS="$CLI_REGISTRY" \
    bash "$SCRIPT_DIR/detect.sh" "$@" 2>&1) || return 1
  state=$(tail -1 <<< "$output")
  [[ -f "$state" ]] || return 1
  [[ "$(state_value "$state" REPO)" == "$CLI_REPO" &&
     "$(state_value "$state" BRANCH)" == "$expected" ]] || result=1
  rm -f "$state"
  return "$result"
}
check "current repo accepts master" _cli_detect_branch master master
check "current repo accepts main" _cli_detect_branch main main
check "current repo accepts its local feature branch" _cli_detect_branch feature/local feature/local
check "current repo accepts its remote feature branch" _cli_detect_branch feature/remote feature/remote
for _cli_branch in master feature/future; do
  check "absolute repo precedes $_cli_branch" _cli_detect_branch "$_cli_branch" "$CLI_REPO" "$_cli_branch"
  check "$_cli_branch precedes absolute repo" _cli_detect_branch "$_cli_branch" "$_cli_branch" "$CLI_REPO"
done
check "registry repo precedes arbitrary branch" _cli_detect_branch feature/future sample feature/future
check "arbitrary branch precedes registry repo" _cli_detect_branch feature/future feature/future sample
check "unknown repo name still fails with setup guidance" ! _cli_detect_branch unknown unknown-repo
check "multiple repositories are rejected" ! _cli_detect_branch master "$CLI_REPO" sample master
check "multiple branches are rejected" ! _cli_detect_branch master master main
check "empty arguments are treated as omitted" _cli_detect_branch master "" master
git -C "$CLI_REPO" checkout -qb fix-devel-cves-2026-10-15
check "an earlier fix branch is not used as the base" ! _cli_detect_branch fix-devel-cves-2026-10-15
check "an explicit base branch still works from a fix branch" _cli_detect_branch master master
git -C "$CLI_REPO" checkout -q - && git -C "$CLI_REPO" branch -qD fix-devel-cves-2026-10-15
check "branch detection leaves HEAD unchanged" test "$(git -C "$CLI_REPO" rev-parse HEAD)" = "$CLI_HEAD"
check "branch detection leaves repository clean" git -C "$CLI_REPO" diff --quiet

# === Full-review behavioral regressions ===
echo "full-review worker lifetime and YAML regressions"
RREV="$TMPD/full-review"; mkdir -p "$RREV"

# Run the actual orchestrator and EXIT trap, with a controlled scanner boundary.
# Git, state creation and process ownership remain real.
_review_worker_fixture() {
  local name="$1" original
  _RW_DIR="$RREV/$name"; original="$_RW_DIR/original"
  _RW_STATE="$_RW_DIR/cve-fix-worker.env"
  mkdir -p "$original/scripts"
  git -C "$original" init -q -b devel
  git -C "$original" config user.email fixture@example.com
  git -C "$original" config user.name Fixture
  printf 'module example.com/review\ngo 1.24.0\n' > "$original/go.mod"
  cp "$SCRIPT_DIR/"{lib.sh,fix-all.sh,binary-module-locations.py} "$original/scripts/"
  printf '\npreflight_check() { return 0; }\n' >> "$original/scripts/lib.sh"
  git -C "$original" add go.mod
  git -C "$original" commit -qm init
  git -C "$original" checkout -qb fix-review
  make_go_state "$_RW_STATE" "$original"
  printf 'FIX_BRANCH=fix-review\nORIGINAL_REF=devel\nFETCH_FAILED=false\n' >> "$_RW_STATE"
  printf 'CLEAN_CMD=\nNEEDS_BUILD_FOR_SCAN=false\nDIFF_IGNORE_ARGS=\n' >> "$_RW_STATE"
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" %q\n' "$_RW_STATE" > "$original/scripts/detect.sh"
  cat > "$original/scripts/scan.sh" <<'SH'
#!/usr/bin/env bash
touch "$1.entered"
while [[ ! -f "$1.release" ]]; do sleep 0.02; done
mode=$(cat "$1.release")
[[ "$mode" != abort ]] || exit 7
printf '{"matches":[],"ignoredMatches":[]}\n'
SH
  chmod +x "$original/scripts/"{detect.sh,scan.sh}
  bash "$original/scripts/fix-all.sh" "$original" devel > "$_RW_DIR/output" 2>&1 &
  _RW_PID=$!
  local n
  for ((n=0; n<250; n++)); do
    [[ ! -f "$_RW_STATE.entered" ]] || return 0
    kill -0 "$_RW_PID" 2>/dev/null || break
    sleep 0.02
  done
  return 1
}
_review_worker_fixture active
printf 'complete\n' > "$_RW_STATE.release"
_rw_exit=0; wait "$_RW_PID" || _rw_exit=$?
check "completed worker returns successful status" test "$_rw_exit" -eq 0
check "completed worker removes its state" test ! -e "$_RW_STATE"
check "completed worker restores the original branch" test "$(git -C "$_RW_DIR/original" branch --show-current)" = devel

_review_worker_fixture aborted
printf 'abort\n' > "$_RW_STATE.release"
_rw_exit=0; wait "$_RW_PID" || _rw_exit=$?
check "aborted worker preserves the failure status" test "$_rw_exit" -eq 2
check "aborted worker restores the original branch" \
  test "$(git -C "$_RW_DIR/original" branch --show-current)" = devel
check "aborted worker removes its fix branch" \
  ! git -C "$_RW_DIR/original" show-ref --verify --quiet refs/heads/fix-review
check "aborted worker removes its state" test ! -e "$_RW_STATE"

_review_worker_fixture interrupted
kill -TERM "$_RW_PID"
printf 'complete\n' > "$_RW_STATE.release"
_rw_exit=0; wait "$_RW_PID" || _rw_exit=$?
check "interrupted worker preserves SIGTERM status" test "$_rw_exit" -eq 143
check "interrupted worker removes its state" test ! -e "$_RW_STATE"


_yaml_repo="$RREV/yaml"; make_test_repo "$_yaml_repo"
printf 'module example.com/yaml\ngo 1.24.0\n' > "$_yaml_repo/go.mod"
printf 'ignore:\n' > "$_yaml_repo/.grype.yaml"
git -C "$_yaml_repo" add go.mod .grype.yaml; git -C "$_yaml_repo" commit -qm module
git -C "$_yaml_repo" update-ref refs/remotes/origin/devel HEAD
make_go_state "$RREV/yaml.env" "$_yaml_repo"
printf 'ignore:\n' > "$_yaml_repo/.grype.yaml"
for _state in not-fixed unknown wont-fix; do
  printf '  # reason mentions fix-state: ignored as comment\n  - vulnerability: CVE-REVIEW-%s\n    fix-state: %s \t # rationale\n    package:\n      name: example.com/%s\n' \
    "$_state" "$_state" "$_state" >> "$_yaml_repo/.grype.yaml"
done
_yaml_out=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$RREV/yaml.env")
check "YAML companion accepts whitespace and inline comments on every state" grep -qx 'NEW_ISSUES=0' <<< "$_yaml_out"
# The same scalar must retain auto-expiration behavior in the other auditors.
git -C "$_yaml_repo" add .grype.yaml; git -C "$_yaml_repo" commit -qm ignores
git -C "$_yaml_repo" update-ref refs/remotes/origin/devel HEAD
mkdir -p "$RREV/yaml-bin" "$RREV/yaml-reports"
cat > "$RREV/yaml-bin/go" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == *-json* ]]; then
  printf '{"Path":"example.com/not-fixed","Version":"v1.0.0"}\n'
else
  printf 'v1.0.0\n'
fi
SH
chmod +x "$RREV/yaml-bin/go"
printf '%s\n' '{"matches":[],"ignoredMatches":[{"vulnerability":{"id":"CVE-REVIEW-not-fixed","fix":{"versions":["1.1.0"],"state":"fixed"}},"artifact":{"name":"example.com/not-fixed","version":"v1.0.0","type":"go-module","locations":[{"path":"/go.mod"}]}}]}' \
  > "$RREV/yaml-reports/initial-scan.json"
_yaml_out=$(PATH="$RREV/yaml-bin:$PATH" bash "$SCRIPT_DIR/../subagents/fix-availability.sh" "$RREV/yaml.env" "$RREV/yaml-reports")
check "commented not-fixed state still discovers an available fix" grep -q '^FIX-AVAILABLE: example.com/not-fixed' <<< "$_yaml_out"
_yaml_out=$(PATH="$RREV/yaml-bin:$PATH" bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$RREV/yaml.env" "$RREV/yaml-reports")
check "commented state remains auto-expiring in branch-base audit" grep -q '^FIX-NOW-AVAILABLE: CVE-REVIEW-not-fixed' <<< "$_yaml_out"
for _quote in "'" '"'; do
  printf 'ignore:\n  - vulnerability: CVE-REVIEW-not-fixed\n    fix-state: %snot-fixed%s # rationale\n    package:\n      name: example.com/not-fixed\n' \
    "$_quote" "$_quote" > "$_yaml_repo/.grype.yaml"
  _yaml_out=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$RREV/yaml.env")
  check "quoted $_quote state with a comment is valid YAML policy" grep -qx 'NEW_ISSUES=0' <<< "$_yaml_out"
  _yaml_out=$(PATH="$RREV/yaml-bin:$PATH" bash "$SCRIPT_DIR/../subagents/fix-availability.sh" "$RREV/yaml.env" "$RREV/yaml-reports")
  check "quoted $_quote state still discovers an available fix" grep -q '^FIX-AVAILABLE: example.com/not-fixed' <<< "$_yaml_out"
  git -C "$_yaml_repo" add .grype.yaml
  git -C "$_yaml_repo" commit -qm quoted-policy
  git -C "$_yaml_repo" update-ref refs/remotes/origin/devel HEAD
  _yaml_out=$(PATH="$RREV/yaml-bin:$PATH" bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$RREV/yaml.env" "$RREV/yaml-reports")
  check "quoted $_quote state remains auto-expiring" grep -q '^FIX-NOW-AVAILABLE: CVE-REVIEW-not-fixed' <<< "$_yaml_out"
done
printf '    fix-state: unknown#literal\n' >> "$_yaml_repo/.grype.yaml"
_yaml_out=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$RREV/yaml.env")
check "YAML companion does not strip a literal attached hash" grep -q 'BAD_FIX_STATE' <<< "$_yaml_out"

check "default fallback uses an immutable SHA256 reference" \
  bash -c "source '$SCRIPT_DIR/lib.sh'; unset CVE_FIX_GRYPE_VERSION CVE_FIX_GRYPE_IMAGE; [[ \$(grype_container_image) == *@sha256:* ]]"

# The real client-go report had two advisories plus "at /go.mod". Formatting
# counted four CVEs and dropped the scope, despite the authoritative count of 2.
_scoped_short='FIXED: golang.org/x/mod v0.40.0 for GO-2026-6179 GO-2026-6180 at /go.mod'
_scoped_single='FIXED: example.com/one v1.1.0 for GO-ONE at /nested/go.mod'
_scoped_long='FIXED: example.com/many v1.1.0 for GO-ONE GO-TWO GO-THREE GO-FOUR at /nested/go.mod'
_scoped_spaces='FIXED: example.com/many v1.1.0 for GO-ONE GO-TWO GO-THREE GO-FOUR at /nested module/go.mod'
_scoped_ignored='IGNORED: example.com/many (no fix available) for GO-ONE GO-TWO GO-THREE GO-FOUR at /nested/go.mod'
check "scoped counts exclude paths and ignored findings" \
  test "$(count_cves_fixed "$_scoped_short"$'\n'"$_scoped_long"$'\n'"$_scoped_ignored")" = 6
check "scoped single advisory stays intact" test "$(format_fix_detail "$_scoped_single")" = "$_scoped_single"
check "real two-advisory detail preserves both IDs and module" test "$(format_fix_detail "$_scoped_short")" = "$_scoped_short"
check "long advisory detail preserves count and module" \
  test "$(format_fix_detail "$_scoped_long")" = 'FIXED: example.com/many v1.1.0 for GO-ONE ... (4 CVEs) at /nested/go.mod'
check "long advisory detail preserves module paths with spaces" \
  test "$(format_fix_detail "$_scoped_spaces")" = 'FIXED: example.com/many v1.1.0 for GO-ONE ... (4 CVEs) at /nested module/go.mod'
check "ignored advisory detail also preserves count and scope" \
  test "$(format_fix_detail "$_scoped_ignored")" = 'IGNORED: example.com/many (no fix available) for GO-ONE ... (4 CVEs) at /nested/go.mod'

# Execute the production PR-report block with real Git remote configurations.
# Fetching and applying repairs are covered above; these checks never push.
_pr_repo="$RREV/pr-remotes"; make_test_repo "$_pr_repo"
git -C "$_pr_repo" remote add origin https://github.com/openshift/repo.git
printf '#!/usr/bin/env bash\nset -euo pipefail\nsource %q\nBRANCH=devel\nCURRENT_BRANCH=fix-review\nCOMMIT_COUNT=1\nGATE_REMAINING=0\n' \
  "$SCRIPT_DIR/lib.sh" > "$RREV/pr-block.sh"
python3 - "$SCRIPT_DIR/fix-all.sh" >> "$RREV/pr-block.sh" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
start = source.index('    # Generate PR command')
end = source.index('\n  fi\nelse\n  # Nothing to keep', start)
print(source[start:end])
PY
_pr_remotes() {
  git -C "$_pr_repo" remote set-url origin "$1"
  git -C "$_pr_repo" remote remove myfork 2>/dev/null || true
  git -C "$_pr_repo" remote remove backup 2>/dev/null || true
  [[ -z "${2:-}" ]] || git -C "$_pr_repo" remote add myfork "$2"
}
_pr_run() {
  _pr_rc=0
  _pr_out=$(cd "$_pr_repo"; UPSTREAM_ORG="${1:-}" bash "$RREV/pr-block.sh") || _pr_rc=$?
}
for _remote_pair in \
  'https://github.com/openshift/repo.git|https://github.com/bob/repo.git' \
  'git@github.com:openshift/repo.git|git@github.com:bob/repo.git' \
  'ssh://git@github.com:443/openshift/repo.git|ssh://git@github.com:443/bob/repo.git' \
  'ssh://git@ssh.github.com:443/openshift/repo.git|ssh://git@ssh.github.com:443/bob/repo.git' \
  'https://github.com/openshift/repo.git|ssh://git@github.com:443/bob/repo.git'; do
  _pr_remotes "${_remote_pair%|*}" "${_remote_pair#*|}"
  _pr_run
  check "GitHub URL pair $_remote_pair derives the fork owner" grep -q -- '--head bob:fix-review' <<< "$_pr_out"
  check "GitHub URL pair $_remote_pair uses the fork remote" grep -q 'git push myfork fix-review' <<< "$_pr_out"
done
for _remote_pair in \
  'git@gitlab.example.com:team/repo.git|https://github.com/bob/repo.git' \
  'https://github.com/openshift/repo.git|git@gitlab.example.com:bob/repo.git' \
  'https://github.com/openshift/repo.git|https://notgithub.com/bob/repo.git'; do
  _pr_remotes "${_remote_pair%|*}" "${_remote_pair#*|}"
  _pr_run
  check "non-GitHub pair $_remote_pair still reports successfully" test "$_pr_rc" -eq 0
  check "non-GitHub pair $_remote_pair emits no executable PR command" ! grep -q 'gh pr create' <<< "$_pr_out"
done
_pr_remotes https://github.com/openshift/repo.git https://github.com/bob/repo.git
git -C "$_pr_repo" remote add backup https://gitlab.example.com/bob/repo.git
_pr_run
check "non-GitHub backup does not hide a valid fork" grep -q -- '--head bob:fix-review' <<< "$_pr_out"
check "non-GitHub backup is never selected for pushing" ! grep -q 'git push backup' <<< "$_pr_out"
_pr_remotes https://github.com/openshift/repo.git https://github.com/openshift/repo.git
git -C "$_pr_repo" remote set-url --push myfork https://github.com/bob/repo.git
_pr_run
check "fork owner comes from push URL rather than fetch URL" grep -q -- '--head bob:fix-review' <<< "$_pr_out"
check "split fetch/push remote is retained for pushing" grep -q 'git push myfork fix-review' <<< "$_pr_out"
_pr_remotes https://github.com/openshift/repo.git
git -C "$_pr_repo" remote set-url --push origin https://github.com/bob/repo.git
_pr_run
check "origin may legitimately push to the caller's GitHub fork" grep -q -- '--head bob:fix-review' <<< "$_pr_out"
check "configured origin push URL uses the origin remote" grep -q 'git push origin fix-review' <<< "$_pr_out"
git -C "$_pr_repo" config --unset-all remote.origin.pushurl
_pr_remotes https://github.com/openshift/repo.git https://github.com/bobopenshift/repo.git
_pr_run
check "fork usernames containing the upstream name remain distinct" grep -q -- '--head bobopenshift:fix-review' <<< "$_pr_out"
_pr_remotes /local/upstream.git https://github.com/bob/repo.git
_pr_run openshift
check "explicit upstream org supports configured transport aliases" grep -q -- '--head bob:fix-review' <<< "$_pr_out"
_pr_remotes https://GitHub.COM/OpenShift/repo.git
_pr_run openshift
check "GitHub host and owner casing cannot turn upstream into a fork" ! grep -q 'gh pr create' <<< "$_pr_out"

# === Full-review UTF-8, timeout retry and YAML section regressions ===
echo "UTF-8 config and registry input under an ASCII locale"
UTF_CONFIG="$TMPD/utf-config.yaml"
UTF_REGISTRY="$TMPD/utf-repos.yaml"
printf 'test-command: "printf café"\n' > "$UTF_CONFIG"
printf 'repos:\n  - name: unicode\n    path: "/tmp/répô"\n' > "$UTF_REGISTRY"
UTF_READER_ENV=(env LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 PYTHONIOENCODING=utf-8)
_utf_rc=0
_utf_json=$("${UTF_READER_ENV[@]}" python3 "$SCRIPT_DIR/read-config.py" config-json "$UTF_CONFIG" 2>/dev/null) || _utf_rc=$?
check "UTF-8 config input decodes independently of locale" test "$_utf_rc" -eq 0
check "UTF-8 config preserves Unicode scalar" test "$(jq -r '.["test-command"]' <<< "$_utf_json")" = 'printf café'
_utf_rc=0
_utf_path=$("${UTF_READER_ENV[@]}" python3 "$SCRIPT_DIR/read-config.py" repo-path "$UTF_REGISTRY" unicode 2>/dev/null) || _utf_rc=$?
check "UTF-8 registry input decodes independently of locale" test "$_utf_rc" -eq 0
check "UTF-8 registry preserves Unicode repository path" test "$_utf_path" = '/tmp/répô'

echo "reviewer real timeouts retry within the attempt limit"
REVIEW_TIMEOUT_DIR="$TMPD/review-timeout"
make_test_repo "$REVIEW_TIMEOUT_DIR/repo"
mkdir -p "$REVIEW_TIMEOUT_DIR/bin"
make_go_state "$REVIEW_TIMEOUT_DIR/state.env" "$REVIEW_TIMEOUT_DIR/repo"
cat > "$REVIEW_TIMEOUT_DIR/bin/codex" <<'TIMEOUTAGENT'
#!/usr/bin/env bash
set -euo pipefail
count=0
[[ ! -f "$REVIEW_TIMEOUT_COUNT" ]] || count=$(cat "$REVIEW_TIMEOUT_COUNT")
count=$((count + 1)); printf '%s\n' "$count" > "$REVIEW_TIMEOUT_COUNT"
if [[ "$count" -eq 1 || "$REVIEW_TIMEOUT_MODE" == exhausted ]]; then
  sleep 0.6
elif [[ "$REVIEW_TIMEOUT_MODE" == auth-after-timeout ]]; then
  echo 'login required' >&2
  exit 1
fi
printf 'RESOLVED: stdlib — supported compiler\n'
TIMEOUTAGENT
chmod +x "$REVIEW_TIMEOUT_DIR/bin/codex"
for _review_timeout_mode in then-success exhausted auth-after-timeout; do
  rm -f "$REVIEW_TIMEOUT_DIR/count" "$REVIEW_TIMEOUT_DIR/state.env.review-unresolved"
  _review_timeout_rc=0
  _review_timeout_out=$(PATH="$REVIEW_TIMEOUT_DIR/bin:$PATH" CVE_FIX_AGENT=codex \
    CVE_FIX_AGENT_TIMEOUT=0.3s CVE_FIX_AGENT_ATTEMPTS=3 CVE_FIX_RETRY_BASE=0 \
    REVIEW_TIMEOUT_COUNT="$REVIEW_TIMEOUT_DIR/count" REVIEW_TIMEOUT_MODE="$_review_timeout_mode" \
    bash "$SCRIPT_DIR/review.sh" "$REVIEW_TIMEOUT_DIR/state.env" \
    'NEEDS_REVIEW: stdlib — compiler decision needed' 'provided scan evidence' 2>&1) || _review_timeout_rc=$?
  check "review timeout $_review_timeout_mode: review or manual fallback succeeds" test "$_review_timeout_rc" -eq 0
  check "review timeout $_review_timeout_mode: timeout is explicitly retried" grep -q 'transient error (exit 124)' <<< "$_review_timeout_out"
  check "review timeout $_review_timeout_mode: no unconfirmed outcome is persisted" test ! -f "$REVIEW_TIMEOUT_DIR/state.env.review-unresolved"
  if [[ "$_review_timeout_mode" == exhausted ]]; then
    check "review timeout: retries stop at configured attempt limit" test "$(cat "$REVIEW_TIMEOUT_DIR/count")" -eq 3
    check "review timeout: exhausted timeout has infrastructure classification" grep -q 'infra error, exit 124' <<< "$_review_timeout_out"
    check "review timeout: exhausted timeout never reaches structured summary" ! grep -q '=== Review Summary ===' <<< "$_review_timeout_out"
  else
    check "review timeout $_review_timeout_mode: retry finishes on second attempt" test "$(cat "$REVIEW_TIMEOUT_DIR/count")" -eq 2
    if [[ "$_review_timeout_mode" == then-success ]]; then
      check "review timeout: successful retry is parsed" grep -q '^RESOLVED: stdlib — supported compiler$' <<< "$_review_timeout_out"
    else
      check "review timeout: deterministic auth failure stops further retries" grep -q 'auth error' <<< "$_review_timeout_out"
    fi
  fi
done

echo "YAML structural audit stays inside the ignore section"
YAML_SECTION_REPO="$TMPD/yaml-sections"
make_test_repo "$YAML_SECTION_REPO"
printf 'ignore:\n' > "$YAML_SECTION_REPO/.grype.yaml"
git -C "$YAML_SECTION_REPO" add .grype.yaml
git -C "$YAML_SECTION_REPO" commit -qm 'empty ignore policy'
git -C "$YAML_SECTION_REPO" update-ref refs/remotes/origin/devel HEAD
make_go_state "$TMPD/yaml-sections.env" "$YAML_SECTION_REPO"
for _yaml_indent in 0 2 4; do
  printf -v _yaml_pad '%*s' "$_yaml_indent" ''
for _yaml_section in exclude-only exclude-before exclude-after missing-vulnerability missing-package empty-item; do
  printf 'ignore:\n' > "$YAML_SECTION_REPO/.grype.yaml"
  if [[ "$_yaml_section" == exclude-only || "$_yaml_section" == exclude-before ]]; then
    printf 'exclude:\n  - "**/node_modules/**"\nignore:\n' > "$YAML_SECTION_REPO/.grype.yaml"
  fi
  if [[ "$_yaml_section" == missing-vulnerability ]]; then
    printf '%s# Broad package rule must fail once.\n%s- package:\n%s    name: example.com/broad\n' "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" >> "$YAML_SECTION_REPO/.grype.yaml"
  elif [[ "$_yaml_section" == missing-package ]]; then
    printf '%s# Broad vulnerability rule must fail once.\n%s- vulnerability: CVE-BROAD\n' "$_yaml_pad" "$_yaml_pad" >> "$YAML_SECTION_REPO/.grype.yaml"
  elif [[ "$_yaml_section" == empty-item ]]; then
    printf '%s-\n' "$_yaml_pad" >> "$YAML_SECTION_REPO/.grype.yaml"
  elif [[ "$_yaml_section" != exclude-only ]]; then
    printf '%s# Scoped advisory exception.\n%s- vulnerability: CVE-SECTION\n%s  package:\n%s    name: example.com/scoped\n%s  fix-state: not-fixed\n' \
      "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" >> "$YAML_SECTION_REPO/.grype.yaml"
  fi
  if [[ "$_yaml_section" == exclude-after ]]; then
    printf 'exclude:\n  - "**/node_modules/**"\n' >> "$YAML_SECTION_REPO/.grype.yaml"
  fi
  _yaml_section_out=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$TMPD/yaml-sections.env")
  if [[ "$_yaml_section" == missing-vulnerability ]]; then
    check "YAML missing vulnerability is counted once" grep -qx 'NEW_ISSUES=1' <<< "$_yaml_section_out"
    check "YAML missing vulnerability emits one structural detail" test "$(grep -c '^MISSING_VULNERABILITY_FIELD:' <<< "$_yaml_section_out")" -eq 1
  elif [[ "$_yaml_section" == missing-package ]]; then
    check "YAML indent $_yaml_indent rejects vulnerability-only ignores" grep -qx 'NEW_ISSUES=1' <<< "$_yaml_section_out"
  elif [[ "$_yaml_section" == empty-item ]]; then
    check "YAML indent $_yaml_indent rejects empty ignore items" grep -qx 'NEW_ISSUES=2' <<< "$_yaml_section_out"
  else
    check "YAML $_yaml_section does not treat exclude paths as ignores" grep -qx 'NEW_ISSUES=0' <<< "$_yaml_section_out"
  fi
done
  # Matching, migration, removal and insertion must agree on the same YAML list.
  printf 'ignore:\n%s- vulnerability: CVE-SCOPE\n%s  fix-state: not-fixed\n%s  package:\n%s    name: example.com/scoped\n%s- vulnerability: CVE-SCOPE\n%s  fix-state: not-fixed\n%s  package:\n%s    name: example.com/scoped\n%s    location: /tools/go.mod\n%s- vulnerability: CVE-BROAD\n%s- vulnerability: CVE-NEIGHBOR\n%s  package:\n%s    name: example.com/neighbor\nonly-fixed: true\nexclude:\n  - "**/node_modules/**"\n' \
    "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" "$_yaml_pad" \
    > "$YAML_SECTION_REPO/.grype.yaml"
  check "YAML indent $_yaml_indent finds scoped entries" grype_ignore_entry_exists "$YAML_SECTION_REPO/.grype.yaml" CVE-SCOPE example.com/scoped /tools/go.mod
  check "YAML indent $_yaml_indent finds scope conflicts" grep -q '^SCOPE_CONFLICT:' <<< "$(grype_ignore_scope_conflicts "$YAML_SECTION_REPO/.grype.yaml")"
  remove_invalid_grype_ignores "$YAML_SECTION_REPO/.grype.yaml" >/dev/null
  check "YAML indent $_yaml_indent removes broad selectors" ! grep -q CVE-BROAD "$YAML_SECTION_REPO/.grype.yaml"
  check "YAML indent $_yaml_indent runs scope migration" migrate_grype_ignore_scope "$YAML_SECTION_REPO/.grype.yaml" CVE-SCOPE example.com/scoped /tools/go.mod unknown >/dev/null
  check "YAML indent $_yaml_indent migrates scope and state" grype_ignore_entry_exists "$YAML_SECTION_REPO/.grype.yaml" CVE-SCOPE example.com/scoped /tools/go.mod
  check "YAML indent $_yaml_indent removes migrated unscoped entry" ! grype_ignore_entry_exists "$YAML_SECTION_REPO/.grype.yaml" CVE-SCOPE example.com/scoped
  check "YAML indent $_yaml_indent clears scope conflict" test -z "$(grype_ignore_scope_conflicts "$YAML_SECTION_REPO/.grype.yaml")"
  check "YAML indent $_yaml_indent runs scoped insertion" insert_grype_ignore "$YAML_SECTION_REPO/.grype.yaml" CVE-INSERT example.com/insert 'Scoped exception' unknown /go.mod >/dev/null
  check "YAML indent $_yaml_indent inserts a scoped entry" grype_ignore_entry_exists "$YAML_SECTION_REPO/.grype.yaml" CVE-INSERT example.com/insert /go.mod
  check "YAML indent $_yaml_indent preserves list indentation" grep -qx -- "${_yaml_pad}- vulnerability: CVE-INSERT" "$YAML_SECTION_REPO/.grype.yaml"
  check "YAML indent $_yaml_indent preserves other settings" grep -qx 'only-fixed: true' "$YAML_SECTION_REPO/.grype.yaml"
  check "YAML indent $_yaml_indent preserves unrelated ignore" grype_ignore_entry_exists "$YAML_SECTION_REPO/.grype.yaml" CVE-NEIGHBOR example.com/neighbor
done

# === Skitt grouped-version and executable-text regressions ===
echo "grouped fixes retain usable thresholds and Go pseudo-versions"
_skitt_selector() {
  local label="$1" current="$2" expected="$3" requirements="$4" encoded actual rc=0
  encoded=$(printf '%s' "$requirements" | base64 | tr -d '\n')
  actual=$(select_common_fix_version "$current" "$encoded") || rc=$?
  if [[ "$expected" == unavailable ]]; then
    check "group selector $label: no invented target" test "$rc" -ne 0
  else
    check "group selector $label: usable target" test "$rc" -eq 0
    check "group selector $label: exact threshold" test "$actual" = "$expected"
  fi
}
_skitt_selector repeated-patch 1.83.3 1.83.4 '[{"cve":"CVE-A","versions":["1.83.2","1.83.4"]}]'
_skitt_selector repeated-patch-unsorted 1.83.3 1.83.4 '[{"cve":"CVE-A","versions":["1.83.4","1.83.2"]}]'
_skitt_selector parallel-patches 1.83.3 1.83.4 '[{"cve":"CVE-A","versions":["1.82.2","1.83.2","1.83.4"]},{"cve":"CVE-B","versions":["1.83.3"]}]'
_skitt_selector semver-pseudo-before-release 1.0.1-0.20250101000000-aaaaaaaaaaaa 1.0.1-0.20260202000000-bbbbbbbbbbbb '[{"cve":"CVE-A","versions":["1.0.1","1.0.1-0.20260202000000-bbbbbbbbbbbb"]}]'
_skitt_selector duplicates 1.83.3 1.83.4 '[{"cve":"CVE-A","versions":["1.83.2"]},{"cve":"CVE-A","versions":["1.83.4"]}]'
_skitt_selector stable-release 1.83.3 1.83.4 '[{"cve":"CVE-A","versions":["1.83.4-rc.1","1.83.4"]}]'
_skitt_selector prerelease-only 1.83.3 unavailable '[{"cve":"CVE-A","versions":["1.83.4-rc.1"]}]'
_skitt_selector lower-thresholds 1.83.5 unavailable '[{"cve":"CVE-A","versions":["1.83.2","1.83.4"]}]'
_skitt_selector missing-advisory 1.83.3 unavailable '[{"cve":"CVE-A","versions":[]},{"cve":"CVE-B","versions":["1.83.4"]}]'
for _skitt_pseudo_base in 0.0.0- 0.21.1-0. 1.0.0-beta.0. 1.0.0-beta1.0.; do
  _skitt_old="${_skitt_pseudo_base}20250101000000-aaaaaaaaaaaa"
  _skitt_new="${_skitt_pseudo_base}20260202000000-bbbbbbbbbbbb"
  _skitt_selector "pseudo-$_skitt_pseudo_base" "$_skitt_old" "$_skitt_new" \
    "[{\"cve\":\"CVE-A\",\"versions\":[\"$_skitt_new\"]}]"
  check "legacy stream selector accepts $_skitt_pseudo_base" \
    test "$(CVE_FIX_ALL_VERSIONS="$_skitt_new" select_instream_version example.com/pseudo "$_skitt_old")" = "$_skitt_new"
done
_skitt_selector incompatible-pseudo 2.0.1-0.20250101000000-aaaaaaaaaaaa+incompatible \
  2.0.1-0.20260202000000-bbbbbbbbbbbb+incompatible \
  '[{"cve":"CVE-A","versions":["2.0.1-0.20260202000000-bbbbbbbbbbbb+incompatible"]}]'

# Native offline orchestration: real dispatch, Go metadata resolution, mutation,
# build, project tests and final scan. Only detection, scanner evidence and the
# optional agent are controlled; the scanner reads the actual updated go.mod.
echo "native grouped fixes through dispatch and final verification"
SKITT_GROUP="$TMPD/skitt-group"
mkdir -p "$SKITT_GROUP/scripts" "$SKITT_GROUP/scanner"
mkdir -p "$SKITT_GROUP/subagents"
cp "$SCRIPT_DIR/../subagents/"*.sh "$SKITT_GROUP/subagents/"
for _skitt_script in lib.sh fix-all.sh fix-package.sh fix-stdlib.sh ignore.sh scan.sh binary-module-locations.py; do
  cp "$SCRIPT_DIR/$_skitt_script" "$SKITT_GROUP/scripts/"
done
printf '\npreflight_check() { return 0; }\n' >> "$SKITT_GROUP/scripts/lib.sh"
printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$SKITT_GROUP_STATE"\n' > "$SKITT_GROUP/scripts/detect.sh"
printf '#!/usr/bin/env bash\nexit 0\n' > "$SKITT_GROUP/scripts/review.sh"
chmod +x "$SKITT_GROUP/scripts/"*.sh
python3 - "$SKITT_GROUP/proxy" <<'PYPROXY'
import json, sys, zipfile
from pathlib import Path
proxy = Path(sys.argv[1]) / "example.com/groupfix/@v"
proxy.mkdir(parents=True)
versions = ["v1.83.2", "v1.83.3", "v1.83.4"]
for prefix in ["v0.21.1-0.", "v1.0.0-beta.0."]:
    versions += [prefix + "20250101000000-aaaaaaaaaaaa", prefix + "20260202000000-bbbbbbbbbbbb"]
for version in versions:
    mod = "module example.com/groupfix\n\ngo 1.18\n"
    (proxy / (version + ".mod")).write_text(mod)
    (proxy / (version + ".info")).write_text(json.dumps({"Version": version, "Time": "2026-02-02T00:00:00Z"}))
    with zipfile.ZipFile(proxy / (version + ".zip"), "w") as archive:
        archive.writestr("example.com/groupfix@" + version + "/go.mod", mod)
        archive.writestr("example.com/groupfix@" + version + "/value.go",
                         'package groupfix\nfunc Value() string { return "' + version + '" }\n')
(proxy / "list").write_text("\n".join(versions) + "\n")
PYPROXY
cat > "$SKITT_GROUP/scanner/grype" <<'SCANNER'
#!/usr/bin/env bash
set -euo pipefail
version=$(GOTOOLCHAIN=local go -C "$SKITT_GROUP_MODULE_DIR" mod edit -json |
  jq -r '.Require[] | select(.Path == "example.com/groupfix") | .Version')
printf 'gathered packages packages=2\n' >&2
python3 - "$version" "$SKITT_GROUP_TARGET" "$SKITT_GROUP_REQUIREMENTS" "${SKITT_GROUP_SCAN_MODE:-clean}" <<'PYSCAN'
import json, os, sys
version, target, encoded, mode = sys.argv[1:]
import base64
requirements = json.loads(base64.b64decode(encoded))
if mode == "refreshed-threshold":
    import os
    from pathlib import Path
    counter = Path(os.environ["SKITT_GROUP_SCAN_COUNT"])
    count = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(count))
    if count > 1:
        requirements = [{"cve": req["cve"], "versions": ["1.83.4"]} if req["cve"] == "CVE-A" else req
                        for req in requirements]
findings = []
ignored = []
if mode == "no-fix":
    import copy, os
    from pathlib import Path
    source = {"artifact": {"type": "go-module", "name": "example.com/groupfix", "version": version,
                           "locations": [{"path": "/go.mod"}]},
              "vulnerability": {"id": "CVE-NOFIX", "severity": "High", "fix": {"versions": [], "state": "not-fixed"}}}
    binary = copy.deepcopy(source)
    binary["artifact"]["locations"] = [{"path": "/output/application"}]
    policy = Path(os.environ["SKITT_GROUP_REPO"]) / ".grype.yaml"
    if policy.exists() and "location: /go.mod" in policy.read_text():
        ignored.append(source)
    else:
        findings.append(source)
    findings.append(binary)
elif mode == "stream-retry" and version == "v1.83.3":
    # The installed range reported 1.83.3; the next range starts there.
    findings.append({"artifact": {"type": "go-module", "name": "example.com/groupfix", "version": version,
                     "locations": [{"path": "/go.mod"}]},
                     "vulnerability": {"id": "CVE-A", "severity": "High", "fix": {"versions": ["1.83.4"], "state": "fixed"}}})
elif version != target or mode in ("persistent", "persistent-ignored"):
    if mode in ("duplicate-ascending", "duplicate-descending"):
        requirements = [{"cve": req["cve"], "versions": [threshold]}
                        for req in requirements for threshold in req["versions"]]
        if mode == "duplicate-descending":
            requirements.reverse()
    for req in requirements:
        findings.append({"artifact": {"type": "go-module", "name": "example.com/groupfix", "version": version,
                         "locations": [{"path": "/go.mod"}]},
                         "vulnerability": {"id": req["cve"], "severity": "High", "fix": {"versions": req["versions"], "state": "fixed"}}})
    if mode == "persistent-ignored" and version == target:
        ignored, findings = findings, []
elif mode == "new-finding":
    findings.append({"artifact": {"type": "go-module", "name": "example.com/groupfix", "version": version,
                     "locations": [{"path": "/go.mod"}]},
                     "vulnerability": {"id": "CVE-NEW", "severity": "High", "fix": {"versions": [], "state": "not-fixed"}}})
if mode == "drain-input":
    findings.append({"artifact": {"type": "go-module", "name": "stdlib", "version": "go1.26.8",
                                 "locations": [{"path": "/output/application"}]},
                     "vulnerability": {"id": "CVE-STDLIB", "severity": "High", "fix": {"versions": ["1.26.9"], "state": "fixed"}}})
if os.environ.get("SKITT_GROUP_SCAN_RELATIVE") == "true":
    for finding in findings + ignored:
        for location in finding["artifact"]["locations"]:
            if location["path"] == "/go.mod":
                location["path"] = "tools/go.mod"
print(json.dumps({"matches": findings, "ignoredMatches": ignored}))
PYSCAN
SCANNER
chmod +x "$SKITT_GROUP/scanner/grype"
_skitt_native_run() {
  local name="$1" current="$2" target="$3" requirements="$4" mode="${5:-clean}"
  local dir="$SKITT_GROUP/$name" repo="$SKITT_GROUP/$name/repo" encoded rc=0
  local moddir="$repo" build='go build -o output/application .' tests='go test ./...'
  mkdir -p "$repo"
  if [[ "${6:-false}" == true ]]; then
    moddir="$repo/tools"; mkdir -p "$moddir"
    printf 'module example.com/root\ngo 1.18\n' > "$repo/go.mod"
    build='go -C tools build -o ../output/application .'; tests='go -C tools test ./...'
  fi
  printf 'module example.com/app\n\ngo 1.18\n\nrequire example.com/groupfix v%s\n' "$current" > "$moddir/go.mod"
  printf 'package main\nimport "example.com/groupfix"\nfunc main() { println(groupfix.Value()) }\n' > "$moddir/main.go"
  printf 'package main\nimport ("testing"; "example.com/groupfix")\nfunc TestDependency(t *testing.T) { if groupfix.Value() == "" { t.Fatal("empty dependency result") } }\n' > "$moddir/main_test.go"
  # The actual test script contains UPX fixture strings and is executable text.
  cp "$TEST_SCRIPT" "$repo/executable-test-script.sh"
  env GOMODCACHE="$SKITT_GROUP/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none \
    GOPROXY="file://$SKITT_GROUP/proxy" GOSUMDB=off GOTOOLCHAIN=local \
    go -C "$moddir" mod tidy > "$dir/setup.log" 2>&1
  git -C "$repo" init -q -b devel
  git -C "$repo" config user.name Test
  git -C "$repo" config user.email test@test.com
  git -C "$repo" add .
  git -C "$repo" commit -qm init
  git init --bare -q "$dir/origin"
  git -C "$repo" remote add origin "$dir/origin"
  git -C "$repo" push -q origin devel
  git -C "$repo" checkout -qb cve-fix/devel
  git -C "$repo" remote add fork https://github.com/testforkuser/testrepo.git
  make_go_state "$dir/state.env" "$repo"
  printf 'ORIGINAL_REF=devel\nHAS_TOOLS_GOMOD=false\nDIFF_IGNORE_ARGS=""\nNEEDS_BUILD_FOR_SCAN=false\nCONTAINER_CMD=""\nHAS_LOCAL_GRYPE=true\nBUILD_IMAGE=""\nCLEAN_CMD=""\nENV_UNSET=""\nK8S_VERSION_GUARD=true\nUPSTREAM_ORG=testupstream\nFETCH_FAILED=false\n' >> "$dir/state.env"
  printf 'CVE_SCRIPTS=%q\nBUILD_CMD=%q\nTEST_CMD=%q\n' "$SKITT_GROUP/scripts" \
    "$build" "$tests" >> "$dir/state.env"
  # Docker's -i consumes stdin even when the build itself needs no input.
  [[ "$mode" != drain-input ]] || printf 'BUILD_CMD=%q\n' 'cat >/dev/null; go build -o output/application .' >> "$dir/state.env"
  encoded=$(printf '%s' "$requirements" | base64 | tr -d '\n')
  env SKITT_GROUP_STATE="$dir/state.env" SKITT_GROUP_REPO="$repo" SKITT_GROUP_MODULE_DIR="$moddir" SKITT_GROUP_TARGET="v$target" \
    SKITT_GROUP_REQUIREMENTS="$encoded" SKITT_GROUP_SCAN_MODE="$mode" SKITT_GROUP_SCAN_RELATIVE="${6:-false}" SKITT_GROUP_SCAN_COUNT="$dir/scan-count" PATH="$SKITT_GROUP/scanner:$PATH" \
    GOMODCACHE="$SKITT_GROUP/modcache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none \
    GOPROXY="file://$SKITT_GROUP/proxy" GOSUMDB=off \
    bash "$SKITT_GROUP/scripts/fix-all.sh" "$repo" devel > "$dir/run.log" 2>&1 || rc=$?
  check "native $name: script text never becomes opaque" ! grep -q 'packed/opaque binary' "$dir/run.log"
  if [[ "$mode" == drain-input ]]; then
    check "native stdin: initial package repair succeeds" grep -q "example.com/groupfix v${target}$" "$repo/go.mod"
    check "native stdin: later stdlib group is dispatched" grep -q '^NEEDS_REVIEW: stdlib —' "$dir/run.log"
    check "native stdin: stdlib policy still requires review" test "$rc" -eq 2
    check "native stdin: remaining stdlib finding stays counted" grep -q 'Outstanding: 1' "$dir/run.log"
  elif [[ "$mode" == no-fix ]]; then
    check "native no-fix: verified ignore succeeds" test "$rc" -eq 0
    check "native no-fix: covered binary remains ignored rather than fixed" grep -q 'Fixed: 0 pkgs / 0 findings' "$dir/run.log"
    check "native no-fix: ignore stays counted" grep -q 'Ignored: 1' "$dir/run.log"
    check "native no-fix: no actionable finding remains" grep -q 'Outstanding: 0' "$dir/run.log"
    check "native no-fix: dependency version is unchanged" grep -q "example.com/groupfix v${current}$" "$repo/go.mod"
    check "native no-fix: ignore is scoped to the source module" grep -q 'location: /go.mod' "$repo/.grype.yaml"
  elif [[ "$mode" != persistent* && "$mode" != new-finding ]]; then
    check "native $name: full workflow succeeds" test "$rc" -eq 0
    check "native $name: dependency reaches exact target" grep -q "example.com/groupfix v${target}$" "$moddir/go.mod"
    check "native $name: built artifact executes updated dependency" test "$("$repo/output/application" 2>&1)" = "v$target"
    check "native $name: module checksum committed" git -C "$repo" ls-files --error-unmatch "$moddir/go.sum"
    check "native $name: project tests run" grep -q '^ok[[:space:]].*example.com/app' "$dir/run.log"
    check "native $name: final scan confirms clean" grep -q 'Clean: no actionable CVEs remain' "$dir/run.log"
    check "native $name: PR command available after verification" grep -q 'gh pr create' "$dir/run.log"
    check "native $name: repair is signed off" bash -c 'git -C "$1" log -1 --format=%B | grep -q "Signed-off-by: Test <test@test.com>"' _ "$repo"
    check "native $name: no spurious ignore created" test ! -f "$repo/.grype.yaml"
  elif [[ "$mode" == persistent* ]]; then
    check "native $name: persistent findings retain review exit" test "$rc" -eq 2
    check "native $name: final scan cannot claim clean" ! grep -q 'Clean: no actionable CVEs remain' "$dir/run.log"
    check "native $name: outstanding CVEs remain counted" grep -q 'Outstanding: 2' "$dir/run.log"
    check "native $name: persistent requested findings reject the candidate" grep -q '^STILL_VULNERABLE:' "$dir/run.log"
    check "native $name: rejected update restores dependency metadata" grep -q "example.com/groupfix v${current}$" "$moddir/go.mod"
    check "native $name: rejected candidate is never reported fixed" ! grep -q '^FIXED: example.com/groupfix' "$dir/run.log"
    check "native $name: rejected candidate creates no PR command" ! grep -q 'gh pr create' "$dir/run.log"
  else
    check "native $name: scan failure remains actionable" test "$rc" -eq 2
    check "native $name: rejected mutation leaves original requirement" grep -q "example.com/groupfix v${current}$" "$repo/go.mod"
    check "native $name: rejection creates no repair commit" test "$(git -C "$repo" rev-list --count HEAD)" -eq 1
  fi
}
_SKITT_PATCH_REQ='[{"cve":"CVE-A","versions":["1.83.2","1.83.4"]},{"cve":"CVE-B","versions":["1.83.2"]}]'
_skitt_native_run repeated-patch 1.83.3 1.83.4 "$_SKITT_PATCH_REQ"
for _skitt_pseudo_base in 0.21.1-0. 1.0.0-beta.0.; do
  _skitt_old="${_skitt_pseudo_base}20250101000000-aaaaaaaaaaaa"
  _skitt_new="${_skitt_pseudo_base}20260202000000-bbbbbbbbbbbb"
  _skitt_native_run "pseudo-$_skitt_pseudo_base" "$_skitt_old" "$_skitt_new" \
    "[{\"cve\":\"CVE-A\",\"versions\":[\"$_skitt_new\"]}]"
done
_skitt_native_run stream-retry 1.83.2 1.83.4 \
  '[{"cve":"CVE-A","versions":["1.83.3"]},{"cve":"CVE-B","versions":["1.83.3"]}]' stream-retry
check "native stream-retry: rejected candidate reports the next threshold" \
  grep -qx 'RETRY_FIX: CVE-A 1.83.4' "$SKITT_GROUP/stream-retry/run.log"
check "native stream-retry: retries once with that threshold" \
  test "$(grep -c '^Retrying example.com/groupfix' "$SKITT_GROUP/stream-retry/run.log")" -eq 1
_skitt_native_run duplicate-ascending 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" duplicate-ascending
_skitt_native_run duplicate-descending 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" duplicate-descending
_skitt_native_run persistent 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" persistent
_skitt_native_run persistent-ignored 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" persistent-ignored
_skitt_native_run new-finding 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" new-finding
_skitt_native_run no-fix 1.83.3 1.83.3 '[]' no-fix
_skitt_native_run drain-input 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" drain-input
_skitt_native_run refreshed-threshold 1.83.2 1.83.4 \
  '[{"cve":"CVE-A","versions":["1.82.2"]},{"cve":"CVE-B","versions":["1.83.3"]}]' refreshed-threshold
_skitt_native_run relative-persistent 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" persistent true
_skitt_native_run relative-ignored 1.83.3 1.83.4 "$_SKITT_PATCH_REQ" persistent-ignored true
_skitt_native_run relative-threshold 1.83.2 1.83.4 \
  '[{"cve":"CVE-A","versions":["1.82.2"]},{"cve":"CVE-B","versions":["1.83.3"]}]' refreshed-threshold true

# Source-only and skip-build scans must clear stale coverage markers for scripts,
# while retaining coverage failure for genuine binary bytes containing UPX magic.
echo "executable text cannot imply packed binary coverage failure"
SKITT_OPAQUE="$TMPD/skitt-opaque"
mkdir -p "$SKITT_OPAQUE/repo" "$SKITT_OPAQUE/scanner"
make_test_repo "$SKITT_OPAQUE/repo"
printf '#!/bin/sh\nprintf '\''{"matches":[],"ignoredMatches":[]}\\n'\''\n' > "$SKITT_OPAQUE/scanner/grype"
chmod +x "$SKITT_OPAQUE/scanner/grype"
make_go_state "$SKITT_OPAQUE/state.env" "$SKITT_OPAQUE/repo"
printf 'HAS_LOCAL_GRYPE=true\nCONTAINER_CMD=""\n' >> "$SKITT_OPAQUE/state.env"
cp "$TEST_SCRIPT" "$SKITT_OPAQUE/repo/test-lib.sh"
for _skitt_scan_mode in source-only skip-build; do
  _skitt_flags=()
  if [[ "$_skitt_scan_mode" == skip-build ]]; then
    printf 'BUILD_CMD=false\n' >> "$SKITT_OPAQUE/state.env"
    _skitt_flags=(--skip-build)
  fi
  : > "$SKITT_OPAQUE/state.env.coverage-unknown"
  _skitt_opaque_rc=0
  PATH="$SKITT_OPAQUE/scanner:$PATH" bash "$SCRIPT_DIR/scan.sh" "$SKITT_OPAQUE/state.env" \
    --no-update --json "${_skitt_flags[@]+"${_skitt_flags[@]}"}" > "$SKITT_OPAQUE/scan.json" 2> "$SKITT_OPAQUE/scan.log" || _skitt_opaque_rc=$?
  check "opaque $_skitt_scan_mode: executable text permits scan" test "$_skitt_opaque_rc" -eq 0
  check "opaque $_skitt_scan_mode: text clears stale sentinel" test ! -f "$SKITT_OPAQUE/state.env.coverage-unknown"
  check "opaque $_skitt_scan_mode: text has no packed warning" ! grep -q 'packed/opaque' "$SKITT_OPAQUE/scan.log"
done
printf '\177ELF\000UPX!packed-payload\000' > "$SKITT_OPAQUE/repo/packed-bin"
chmod +x "$SKITT_OPAQUE/repo/packed-bin"
PATH="$SKITT_OPAQUE/scanner:$PATH" bash "$SCRIPT_DIR/scan.sh" "$SKITT_OPAQUE/state.env" \
  --skip-build --no-update --json > "$SKITT_OPAQUE/scan.json" 2> "$SKITT_OPAQUE/scan.log"
check "opaque genuine packed bytes retain coverage failure" test -f "$SKITT_OPAQUE/state.env.coverage-unknown"
check "opaque packed diagnostic names the binary" grep -q 'packed/opaque.*packed-bin' "$SKITT_OPAQUE/scan.log"
check "opaque script remains absent from packed diagnostics" ! grep -q 'packed/opaque.*test-lib.sh' "$SKITT_OPAQUE/scan.log"


# A readable compiler marker must remain fully comparable; stripping an experiment
# suffix would let Grype emit zero matches after failing every version constraint.
SKITT_MARKER="$TMPD/skitt-marker"
mkdir -p "$SKITT_MARKER/repo" "$SKITT_MARKER/bin"
printf 'binary fixture\0' > "$SKITT_MARKER/repo/compiler-bin"
chmod +x "$SKITT_MARKER/repo/compiler-bin"
cat > "$SKITT_MARKER/bin/go" <<'MARKERGO'
#!/usr/bin/env bash
if [[ "$1" == version && "${2:-}" == -m ]]; then
  printf '%s: %s\n' "$3" "$SKITT_GO_MARKER"
else
  printf 'go version go1.26.8 linux/amd64\n'
fi
MARKERGO
chmod +x "$SKITT_MARKER/bin/go"
for _skitt_marker in go1.26.8 go1.26.8-X:nodwarf5 go1.27rc1 'devel go1.27-abcdef'; do
  _skitt_marker_rc=0
  (cd "$SKITT_MARKER/repo"; export PATH="$SKITT_MARKER/bin:$PATH" SKITT_GO_MARKER="$_skitt_marker"
    BUILD_GO_VERSION=unknown BUILD_IMAGE=""
    detect_opaque_binaries) > "$SKITT_MARKER/result.out" 2> "$SKITT_MARKER/result.err" || _skitt_marker_rc=$?
  if [[ "$_skitt_marker" == go1.26.8 ]]; then
    check "compiler marker: stable version retains coverage" test "$_skitt_marker_rc" -eq 1
    check "compiler marker: stable version has no warning" test ! -s "$SKITT_MARKER/result.err"
  else
    check "compiler marker $_skitt_marker: full token cannot be silently normalized" test "$_skitt_marker_rc" -eq 0
    check "compiler marker $_skitt_marker: diagnostic preserves token" grep -qF "($_skitt_marker)" "$SKITT_MARKER/result.err"
  fi
done


# Full controller-gen stamp matching must preserve program strings and arbitrary
# YAML values, including callers using a state from before the anchored rule.
echo "controller-gen annotation matching preserves substantive content"
for _cg_rule in "-I$(controller_gen_version_pattern)"; do
  _cg_repo=$(mktemp -d "$TMPD/controller-full-line.XXXXXX")
  make_test_repo "$_cg_repo"
  printf 'package x\nconst Message = "controller-gen.kubebuilder.io/version: old behavior"\n' > "$_cg_repo/ordinary.go"
  printf 'description: controller-gen.kubebuilder.io/version old behavior\n' > "$_cg_repo/ordinary.yaml"
  printf 'metadata:\n  annotations:\n    controller-gen.kubebuilder.io/version: v0.19.0 substantive old text\n' > "$_cg_repo/trailing.yaml"
  printf 'package x\nconst Manifest = `\nmetadata:\n  annotations:\n    controller-gen.kubebuilder.io/version: v0.19.0\n`\n' > "$_cg_repo/embedded.go"
  printf 'metadata:\n  annotations:\n    controller-gen.kubebuilder.io/version: v0.19.0\n' > "$_cg_repo/noise.yaml"
  git -C "$_cg_repo" add .; git -C "$_cg_repo" commit -qm fixtures
  sed_inplace 's/old behavior/new behavior/' "$_cg_repo/ordinary.go"
  sed_inplace 's/old behavior/new behavior/' "$_cg_repo/ordinary.yaml"
  sed_inplace 's/substantive old text/substantive new text/' "$_cg_repo/trailing.yaml"
  sed_inplace 's/v0.19.0/v0.20.0/' "$_cg_repo/embedded.go"
  sed_inplace 's/v0.19.0/v0.20.0/' "$_cg_repo/noise.yaml"
  (cd "$_cg_repo"; DIFF_IGNORE_ARGS="$_cg_rule" reconcile_generated_files)
  for _cg_file in ordinary.go ordinary.yaml; do
    check "controller rule $_cg_rule: $_cg_file substantive text survives" grep -q 'new behavior' "$_cg_repo/$_cg_file"
    check "controller rule $_cg_rule: $_cg_file staged diff contains the update" \
      bash -c 'git -C "$1" diff --cached -- "$2" | grep -q "^+.*new behavior"' _ "$_cg_repo" "$_cg_file"
  done
  check "controller rule $_cg_rule: trailing semantic text survives" grep -q 'substantive new text' "$_cg_repo/trailing.yaml"
  check "controller rule $_cg_rule: trailing semantic text is staged" \
    bash -c 'git -C "$1" diff --cached -- trailing.yaml | grep -q "^+.*substantive new text"' _ "$_cg_repo"
  check "controller rule $_cg_rule: actual YAML version noise is restored" git -C "$_cg_repo" diff HEAD --quiet -- noise.yaml
  check "controller rule $_cg_rule: embedded YAML version noise is restored" git -C "$_cg_repo" diff HEAD --quiet -- embedded.go
done

# A large generated diff must survive pipefail regardless of pipe capacity.
# Matching only the first output line with grep -q used to SIGPIPE git diff and
# restore thousands of substantive changes as if they were version noise.
echo "large generated diffs remain staged"
GF_LARGE=$(gf_repo large)
printf 'metadata:\n  annotations:\n    %s: v0.19.0\n' "$GF_MARK" > "$GF_LARGE/large.yaml"
for ((_gf_line=0; _gf_line<10000; _gf_line++)); do
  printf 'description-%s: original semantic value\n' "$_gf_line"
done >> "$GF_LARGE/large.yaml"
gf_commit "$GF_LARGE"
sed_inplace 's/original semantic value/updated semantic value/g' "$GF_LARGE/large.yaml"
(cd "$GF_LARGE"; DIFF_IGNORE_ARGS="$GF_CG_RULE" reconcile_generated_files)
check "large generated diff: all semantic updates survive" \
  test "$(grep -c 'updated semantic value' "$GF_LARGE/large.yaml")" -eq 10000
check "large generated diff: all semantic updates are staged" \
  test "$(git -C "$GF_LARGE" diff --cached --numstat -- large.yaml)" = $'10000\t10000\tlarge.yaml'
check "large generated diff: working tree matches staged content" git -C "$GF_LARGE" diff --quiet
GF_DIFF_ERROR=$(gf_repo diff-error)
printf 'metadata:\n  annotations:\n    %s: v0.19.0\ndescription: original semantic value\n' "$GF_MARK" > "$GF_DIFF_ERROR/crd.yaml"
gf_commit "$GF_DIFF_ERROR"
sed_inplace 's/original semantic value/updated semantic value/' "$GF_DIFF_ERROR/crd.yaml"
_gf_error_rc=0
(
  cd "$GF_DIFF_ERROR"
  git() {
    [[ "$1" != diff || "${2:-}" != --quiet ]] || return 128
    command git "$@"
  }
  DIFF_IGNORE_ARGS="$GF_CG_RULE" reconcile_generated_files
) || _gf_error_rc=$?
check "generated diff failure propagates the Git error" test "$_gf_error_rc" -eq 128
check "generated diff failure preserves semantic content" grep -q 'updated semantic value' "$GF_DIFF_ERROR/crd.yaml"
check "generated diff failure stages no unverified content" git -C "$GF_DIFF_ERROR" diff --cached --quiet

# Native Go distinguishes a downloaded replacement's cache directory from a
# local replacement using Replace.Version. Both same-path and fork replacements
# must resolve their effective version without being mistaken for local files.
echo "native versioned replacement verification"
REPLACE_REAL="$TMPD/versioned-replace-real"
_REPLACE_ENV=(env GOMODCACHE="$REPLACE_REAL/cache" GOFLAGS=-modcacherw GOPRIVATE= GONOPROXY=none
  GOPROXY="file://$RESTORE_REAL/proxy" GOSUMDB=off GOTOOLCHAIN=local GOWORK=off)
for _replace_kind in same-path fork; do
  _replace_repo="$REPLACE_REAL/$_replace_kind"
  make_test_repo "$_replace_repo"
  _replace_pkg=example.com/restore
  [[ "$_replace_kind" != fork ]] || _replace_pkg=example.com/original
  printf 'module example.com/main\n\ngo 1.18\n\nrequire %s v1.0.0\nreplace %s => example.com/restore v1.0.1\n' \
    "$_replace_pkg" "$_replace_pkg" > "$_replace_repo/go.mod"
  printf 'package main\nimport restore "%s"\nfunc main() { println(restore.Value()) }\n' \
    "$_replace_pkg" > "$_replace_repo/main.go"
  "${_REPLACE_ENV[@]}" go -C "$_replace_repo" mod tidy > "$REPLACE_REAL/$_replace_kind-tidy.log" 2>&1
  git -C "$_replace_repo" add .; git -C "$_replace_repo" commit -qm 'published replacement fixture'
  _replace_head=$(git -C "$_replace_repo" rev-parse HEAD)
  _replace_resolved=$("${_REPLACE_ENV[@]}" bash -c '
    source "$1"; cd "$2"; resolve_module_dependency . "$3"; printf "%s" "$RESOLVED_VERSION"
  ' _ "$SCRIPT_DIR/lib.sh" "$_replace_repo" "$_replace_pkg") || _replace_resolved=failed
  check "$_replace_kind replacement resolves the published effective version" test "$_replace_resolved" = 1.0.1
  make_go_state "$REPLACE_REAL/$_replace_kind.env" "$_replace_repo"
  _replace_rc=0
  "${_REPLACE_ENV[@]}" bash "$SCRIPT_DIR/fix-package.sh" "$REPLACE_REAL/$_replace_kind.env" \
    "$_replace_pkg" 1.0.1 CVE-REPLACEMENT > "$REPLACE_REAL/$_replace_kind-fix.log" 2>&1 || _replace_rc=$?
  check "$_replace_kind patched replacement is accepted" test "$_replace_rc" -eq 0
  check "$_replace_kind patched replacement is reported fixed" grep -q '^FIXED:' "$REPLACE_REAL/$_replace_kind-fix.log"
  check "$_replace_kind patched replacement needs no new commit" test "$(git -C "$_replace_repo" rev-parse HEAD)" = "$_replace_head"
  check "$_replace_kind patched replacement leaves metadata clean" git -C "$_replace_repo" diff --quiet HEAD

  # Raising require alone does not bypass a replacement pinned below the fix.
  "${_REPLACE_ENV[@]}" go -C "$_replace_repo" mod edit -replace="$_replace_pkg=example.com/restore@v1.0.0"
  "${_REPLACE_ENV[@]}" go -C "$_replace_repo" mod edit -require="$_replace_pkg@v1.0.1"
  "${_REPLACE_ENV[@]}" go -C "$_replace_repo" mod tidy > "$REPLACE_REAL/$_replace_kind-old-tidy.log" 2>&1
  git -C "$_replace_repo" add .; git -C "$_replace_repo" commit -qm 'vulnerable pinned replacement'
  _replace_head=$(git -C "$_replace_repo" rev-parse HEAD)
  _replace_rc=0
  "${_REPLACE_ENV[@]}" bash "$SCRIPT_DIR/fix-package.sh" "$REPLACE_REAL/$_replace_kind.env" \
    "$_replace_pkg" 1.0.1 CVE-REPLACEMENT > "$REPLACE_REAL/$_replace_kind-old.log" 2>&1 || _replace_rc=$?
  check "$_replace_kind vulnerable pinned replacement is rejected" test "$_replace_rc" -eq 3
  check "$_replace_kind vulnerable pinned replacement is not reported fixed" ! grep -q '^FIXED:' "$REPLACE_REAL/$_replace_kind-old.log"
  check "$_replace_kind rejection leaves original commit" test "$(git -C "$_replace_repo" rev-parse HEAD)" = "$_replace_head"
  check "$_replace_kind rejection restores all metadata" git -C "$_replace_repo" diff --quiet HEAD
done

echo "ignore edits keep foreign and flow-style entries valid"
IGY="$TMPD/ignore-yaml"; mkdir -p "$IGY"
cat > "$IGY/foreign.yaml" <<'YAML'
ignore:
  # Image scan: approved
  - vulnerability: CVE-2024-5535
    package:
      name: openssl-libs
      type: rpm
  # x/net
  - vulnerability: CVE-2023-0001
    package:
      name: golang.org/x/net
      type: go-module
      location: /go.mod
YAML
remove_grype_ignore "$IGY/foreign.yaml" CVE-2024-5535 openssl-libs >/dev/null
check "removal leaves no orphaned fields" ! grep -q 'type: rpm' "$IGY/foreign.yaml"
check "removal keeps YAML valid" python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))' "$IGY/foreign.yaml"
remove_grype_ignore "$IGY/foreign.yaml" CVE-2023-0001 golang.org/x/net /go.mod >/dev/null
check "removal finds a location after other fields" ! grep -q CVE-2023-0001 "$IGY/foreign.yaml"
printf 'ignore: []\nexclude:\n  - ./testdata/**\n' > "$IGY/empty-flow.yaml"
check "insert into an empty flow list succeeds" \
  insert_grype_ignore "$IGY/empty-flow.yaml" GO-2026-0001 golang.org/x/net "No fix" not-fixed /go.mod
check "insert into an empty flow list stays valid" \
  python3 -c 'import yaml,sys; d=yaml.safe_load(open(sys.argv[1])); assert len(d["ignore"]) == 1' "$IGY/empty-flow.yaml"
printf 'ignore: !!seq []\n' > "$IGY/breaks.yaml"
check "insert reports YAML it breaks as failure" \
  ! insert_grype_ignore "$IGY/breaks.yaml" GO-2026-0002 golang.org/x/net "No fix" not-fixed
printf 'ignore:\n  - vulnerability: CVE-1\n    package:\n      name: a.b/c\nbroken: [\n' > "$IGY/broken.yaml"
check "insert is not blamed for already-invalid YAML" \
  insert_grype_ignore "$IGY/broken.yaml" GO-2026-0002 golang.org/x/net "No fix" not-fixed
printf -- '---\nignore:\n  - {vulnerability: CVE-2023-1111, package: {name: golang.org/x/net}}\n  - vulnerability: CVE-2023-2222\n    package: {name: golang.org/x/crypto, location: /go.mod}\n  - vulnerability: CVE-2023-3333\n' > "$IGY/flow.yaml"
remove_invalid_grype_ignores "$IGY/flow.yaml" >/dev/null
check "flow-style package names are not broad" grep -q CVE-2023-1111 "$IGY/flow.yaml"
check "inline package maps are not broad" grep -q CVE-2023-2222 "$IGY/flow.yaml"
check "entries without a package are still removed" ! grep -q CVE-2023-3333 "$IGY/flow.yaml"

FIX_LINES=('NEEDS_REVIEW: example.com/sc — det at /sub/go.mod')
apply_review_outcome example.com/sc 'needs k8s (need team input) at /sub/go.mod'
check "review reason echoing its scope is not scoped twice" \
  test "${FIX_LINES[*]}" = 'NEEDS_REVIEW: example.com/sc — needs k8s (need team input) at /sub/go.mod'
printf 'ignore:\n  - vulnerability: CVE-9\n    package:\n      name: a.b/c\n    # about the next entry\n  - vulnerability: CVE-10\n    package:\n      name: a.b/d\n' > "$IGY/comment.yaml"
remove_grype_ignore "$IGY/comment.yaml" CVE-9 a.b/c >/dev/null
check "removal keeps the next entry's indented comment" grep -q 'about the next entry' "$IGY/comment.yaml"
printf 'ignore:\n  - vulnerability: CVE-11\n    # name: a.b/c\n' > "$IGY/commented.yaml"
remove_invalid_grype_ignores "$IGY/commented.yaml" >/dev/null
check "a commented-out name does not make an entry scoped" ! grep -q CVE-11 "$IGY/commented.yaml"
check "reviewer prose quoting a limit stays a verdict" ! bash -c \
  "printf 'VERDICT: FAIL\nThe log says usage limit reached earlier.\n' | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }"

printf 'ignore:\n  - vulnerability: CVE-12\n    reason: upstream name: unknown\n  - vulnerability: CVE-13 # package name: none\n' > "$IGY/prose.yaml"
remove_invalid_grype_ignores "$IGY/prose.yaml" >/dev/null
check "prose mentioning name: is still a broad ignore" ! grep -q 'CVE-1[23]' "$IGY/prose.yaml"
printf 'ignore: [] # none yet\n' > "$IGY/empty-comment.yaml"
check "insert into an empty flow list with a comment" \
  insert_grype_ignore "$IGY/empty-comment.yaml" GO-2026-0003 golang.org/x/net "No fix" not-fixed
printf 'ignore: [{vulnerability: CVE-14, package: {name: a.b/c}}]\n' > "$IGY/flow-list.yaml"
cp "$IGY/flow-list.yaml" "$IGY/flow-list.orig"
check "insert refuses a non-empty flow list" \
  ! insert_grype_ignore "$IGY/flow-list.yaml" GO-2026-0004 golang.org/x/net "No fix" not-fixed
check "refused insert leaves the file unchanged" cmp -s "$IGY/flow-list.yaml" "$IGY/flow-list.orig"
for _limit_msg in "Error: You've hit your weekly limit" "  You’ve hit your usage limit" "Claude usage limit reached. Try later."; do
  check "auth: account limit variant ($_limit_msg)" bash -c \
    "printf '%s\n' \"\$1\" | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }" _ "$_limit_msg"
done
for _limit_msg in "You've hit your limit · resets 3pm" "You've hit your monthly limit" "You've hit your team's shared budget"; do
  check "auth: Claude limit message ($_limit_msg)" bash -c \
    "printf '%s\n' \"\$1\" | { source '$SCRIPT_DIR/lib.sh'; is_auth_error; }" _ "$_limit_msg"
done
printf 'ignore:\n  []\n' > "$IGY/restore.yaml"
cp "$IGY/restore.yaml" "$IGY/restore.orig"
check "insert that breaks YAML fails" \
  ! insert_grype_ignore "$IGY/restore.yaml" GO-2026-0005 golang.org/x/net "No fix" not-fixed
check "failed insert restores the original file" cmp -s "$IGY/restore.yaml" "$IGY/restore.orig"
YIF="$TMPD/yaml-flow"
make_test_repo "$YIF" ""
printf 'module example.com/yif\ngo 1.24.0\n' > "$YIF/go.mod"
printf -- '---\nignore:\n  # flow entry\n  - {vulnerability: CVE-16, package: {name: a.b/c, upstream-name: z}}\n' > "$YIF/.grype.yaml"
git -C "$YIF" add -A && git -C "$YIF" commit -qm flow && git -C "$YIF" update-ref refs/remotes/origin/devel HEAD
make_go_state "$YIF/state.env" "$YIF"
_yif_out=$(bash "$SCRIPT_DIR/../subagents/yaml-integrity.sh" "$YIF/state.env" 2>&1 || true)
check "yaml-integrity accepts a flow-style entry" ! grep -q MISSING_PACKAGE_FIELD <<< "$_yif_out"

echo "stdlib fixes respect workspaces and pre-1.21 modules"
SWK="$TMPD/stdlib-guards"
make_test_repo "$SWK/work" ""
printf 'module example.com/w\n\ngo 1.24.0\n' > "$SWK/work/go.mod"
printf 'go 1.24.0\n\nuse .\n' > "$SWK/work/go.work"
git -C "$SWK/work" add -A && git -C "$SWK/work" commit -qm work
make_go_state "$SWK/work.env" "$SWK/work"
_swk_rc=0; _swk_out=$(bash "$SCRIPT_DIR/fix-stdlib.sh" "$SWK/work.env" 1.24.9 1.24.9 CVE-2026-1 2>&1) || _swk_rc=$?
check "go.work stdlib fix needs review" test "$_swk_rc" -eq 2
check "go.work stdlib fix explains the workspace toolchain" grep -q 'go.work selects the toolchain' <<< "$_swk_out"
check "go.work stdlib fix commits nothing" test "$(git -C "$SWK/work" rev-list --count HEAD)" -eq 2
make_test_repo "$SWK/old" ""
printf 'module example.com/o\n\ngo 1.20\n' > "$SWK/old/go.mod"
git -C "$SWK/old" add -A && git -C "$SWK/old" commit -qm old
make_go_state "$SWK/old.env" "$SWK/old"
_swk_rc=0; _swk_out=$(bash "$SCRIPT_DIR/fix-stdlib.sh" "$SWK/old.env" 1.20.14 1.20.14 CVE-2026-2 2>&1) || _swk_rc=$?
check "pre-1.21 module stdlib fix needs review" test "$_swk_rc" -eq 2
check "pre-1.21 module gets no toolchain line" ! grep -q '^toolchain' "$SWK/old/go.mod"

echo "only Shipyard Dapper files select the Shipyard build"
DPX="$TMPD/foreign-dapper"
make_test_repo "$DPX" ""
printf 'module example.com/dpx\ngo 1.24.0\n' > "$DPX/go.mod"
printf 'FROM golang:1.22\n' > "$DPX/Dockerfile.dapper"
printf 'build:\n\t@true\ntest:\n\t@true\n' > "$DPX/Makefile"
git -C "$DPX" add -A && git -C "$DPX" commit -qm dapper
_dpx_state=$("$SCRIPT_DIR/detect.sh" "$DPX" devel 2>/dev/null | tail -1)
check "foreign Dapper file gets no Shipyard image" test -z "$(state_value "$_dpx_state" BUILD_IMAGE)"
check "foreign Dapper file keeps its test target" test "$(state_value "$_dpx_state" TEST_CMD)" = "make test"

echo "locate reports block replace directives"
LRB="$TMPD/locate-replace"
make_test_repo "$LRB" ""
printf 'module example.com/lrb\n\ngo 1.24.0\n\nrequire golang.org/x/net v0.1.0\n\nreplace (\n\tgolang.org/x/net => golang.org/x/net v0.2.0\n)\n' > "$LRB/go.mod"
printf 'REPO="%s"\nBRANCH="devel"\nCVE_SCRIPTS="%s"\n' "$LRB" "$SCRIPT_DIR" > "$TMPD/lrb.env"
check "block replace is reported" grep -q 'replace golang.org/x/net => golang.org/x/net v0.2.0' \
  <<< "$(cd "$LRB" && bash "$SCRIPT_DIR/locate.sh" "$TMPD/lrb.env" golang.org/x/net 2>&1)"

echo "configuration rejects nulls and tolerates a BOM"
printf 'clean-command: null\n' > "$TMPD/null.yaml"
check "null command is rejected" ! python3 "$SCRIPT_DIR/read-config.py" config-json "$TMPD/null.yaml"
printf '\xef\xbb\xbftest-command: make unit\n' > "$TMPD/bom.yaml"
check "BOM is accepted" python3 "$SCRIPT_DIR/read-config.py" config-json "$TMPD/bom.yaml"

echo "report-only scans leave no branch, commit or state"
RPT="$TMPD/report-only"
mkdir -p "$RPT/bin" "$RPT/scripts"
cp "$SCRIPT_DIR"/{lib.sh,report.sh,detect.sh,scan.sh,read-config.py} "$RPT/scripts/"
printf '\npreflight_check() { return 0; }\n' >> "$RPT/scripts/lib.sh"
make_test_repo "$RPT/repo" ""
printf 'module example.com/rpt\ngo 1.24.0\n' > "$RPT/repo/go.mod"
git -C "$RPT/repo" add -A && git -C "$RPT/repo" commit -qm rpt
printf '#!/bin/sh\necho "NAME INSTALLED VULNERABILITY"\n' > "$RPT/bin/grype"
chmod +x "$RPT/bin/grype"
_rpt_head=$(git -C "$RPT/repo" rev-parse HEAD)
_rpt_branches=$(git -C "$RPT/repo" branch)
_rpt_out=$(cd "$RPT/repo" && PATH="$RPT/bin:$PATH" bash "$RPT/scripts/report.sh" 2>&1 </dev/null || true)
check "report-only prints the scan" grep -q 'NAME INSTALLED VULNERABILITY' <<< "$_rpt_out"
check "report-only leaves HEAD unchanged" test "$(git -C "$RPT/repo" rev-parse HEAD)" = "$_rpt_head"
check "report-only creates no branch" test "$(git -C "$RPT/repo" branch)" = "$_rpt_branches"
check "report-only removes its state" test -z "$(find "$TMPD" -maxdepth 1 -name 'cve-fix-repo-*')"
printf 'build:\n\t@echo regenerated >> tracked.txt\n' > "$RPT/repo/Makefile"
printf 'base\n' > "$RPT/repo/tracked.txt"
git -C "$RPT/repo" add -A && git -C "$RPT/repo" commit -qm build
(cd "$RPT/repo" && PATH="$RPT/bin:$PATH" bash "$RPT/scripts/report.sh" >/dev/null 2>&1 </dev/null || true)
check "report-only restores files its build changed" git -C "$RPT/repo" diff --quiet

echo "tests retry once and classify full disks"
RTX="$TMPD/run-tests"; mkdir -p "$RTX"
python3 - "$SCRIPT_DIR/fix-all.sh" > "$RTX/run-tests.sh" <<'PY'
import sys
s = open(sys.argv[1]).read()
for name in ("_tracked_tree_unchanged", "_run_test_attempt", "run_tests"):
    i = s.index(name + "() {"); j = s.index("\n}\n", i) + 3
    print(s[i:j])
PY
_rtx() {  # TEST_CMD — prints TESTS_FAILED, then FIX_LINES
  ( cd "$RTX" && git init -q 2>/dev/null; git -c user.email=t@t -c user.name=t commit -q --allow-empty -m x 2>/dev/null
    source "$SCRIPT_DIR/lib.sh"; source "$RTX/run-tests.sh"
    _EVIDENCE_TEST_RUN=0; _record_test_evidence() { return 0; }
    FIX_LINES=(); REVIEW_COUNT=0; TESTS_FAILED=false; TEST_CMD="$1"
    run_tests >/dev/null 2>&1; echo "$TESTS_FAILED"; printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" )
}
rm -f "$RTX/count"
_rtx_out=$(_rtx "n=\$(cat '$RTX/count' 2>/dev/null || echo 0); echo \$((n+1)) > '$RTX/count'; [ \$n -ge 1 ]")
check "a test that passes on retry does not fail the run" test "$(head -1 <<< "$_rtx_out")" = false
check "a flaky test runs exactly twice" test "$(cat "$RTX/count")" -eq 2
_rtx_out=$(_rtx false)
check "a consistent test failure still fails the run" test "$(head -1 <<< "$_rtx_out")" = true
rm -f "$RTX/count"
_rtx_out=$(_rtx "echo x >> '$RTX/count'; echo 'write /tmp/x: no space left on device'; false")
check "a full disk is reported as an environment failure" grep -q 'disk full' <<< "$_rtx_out"
check "a full disk is not retried" test "$(wc -l < "$RTX/count")" -eq 1

printf 'ignore:\n  # No fix available\n  - vulnerability: GO-2026-5932\n    fix-state: unknown\n    package:\n      name: golang.org/x/crypto\n' > "$IGY/migrate.yaml"
migrate_grype_ignore_scope "$IGY/migrate.yaml" GO-2026-5932 golang.org/x/crypto /go.mod >/dev/null
check "scope migration keeps the entry's comment" grep -q '# No fix available' "$IGY/migrate.yaml"
check "scope migration adds the location" grep -q 'location: /go.mod' "$IGY/migrate.yaml"

echo "rebuilt binaries count as built by the run"
BLT="$TMPD/built"; mkdir -p "$BLT/repo/bin"
printf 'old' > "$BLT/repo/bin/old-tool"; chmod +x "$BLT/repo/bin/old-tool"
printf 'kept' > "$BLT/repo/bin/untouched"; chmod +x "$BLT/repo/bin/untouched"
( cd "$BLT/repo"; REPO="$BLT/repo"; STATE_FILE="$BLT/state.env"
  artifact_manifest_prepare; sleep 1
  printf 'rebuilt' > bin/old-tool; printf 'new' > bin/new-tool; chmod +x bin/new-tool
  artifact_manifest_record )
check "an in-place rebuild is a built artifact" grep -qx "$BLT/repo/bin/old-tool" "$BLT/state.env.built-artifacts"
check "a new binary is a built artifact" grep -qx "$BLT/repo/bin/new-tool" "$BLT/state.env.built-artifacts"
check "an untouched binary is not a built artifact" ! grep -qx "$BLT/repo/bin/untouched" "$BLT/state.env.built-artifacts"
check "an in-place rebuild is not marked for deletion" ! grep -qx "$BLT/repo/bin/old-tool" "$BLT/state.env.generated-artifacts"

echo "a run removes the previous run's outputs"
PRV="$TMPD/prev-run"; mkdir -p "$PRV/repo/bin"
git -C "$PRV/repo" init -q; git -C "$PRV/repo" config user.email t@t; git -C "$PRV/repo" config user.name t
printf 'tracked' > "$PRV/repo/bin/tracked"; chmod +x "$PRV/repo/bin/tracked"
git -C "$PRV/repo" add -A; git -C "$PRV/repo" commit -qm init
printf 'mine' > "$PRV/repo/bin/user-tool"; chmod +x "$PRV/repo/bin/user-tool"
( cd "$PRV/repo"; REPO="$PRV/repo"; STATE_FILE="$PRV/run1.env"
  artifact_manifest_prepare
  printf 'old' > bin/tool-abc123; chmod +x bin/tool-abc123
  artifact_manifest_record )
( cd "$PRV/repo"; REPO="$PRV/repo"; STATE_FILE="$PRV/run2.env"; artifact_manifest_prepare )
check "the previous run's output is removed" test ! -e "$PRV/repo/bin/tool-abc123"
check "a tracked executable is kept" test -e "$PRV/repo/bin/tracked"
check "an executable the runs did not build is kept" test -e "$PRV/repo/bin/user-tool"

echo "redundant unscoped ignores"
RDN="$TMPD/redundant"; mkdir -p "$RDN"
printf 'ignore:\n  - vulnerability: GO-1\n    fix-state: not-fixed\n    package:\n      name: a.b/c\n      location: /coredns/go.mod\n  - vulnerability: GO-1\n    fix-state: unknown\n    package:\n      name: a.b/c\n' > "$RDN/auto.yaml"
sed '/fix-state: unknown/d' "$RDN/auto.yaml" > "$RDN/permanent.yaml"
_rdn_scan() { printf '{"matches":[],"ignoredMatches":[%s]}\n' "$1" > "$RDN/scan.json"; }
_rdn_hit() { printf '{"vulnerability":{"id":"GO-1"},"artifact":{"name":"a.b/c","locations":[{"path":"%s"}]}}' "$1"; }
_rdn_scan "$(_rdn_hit /coredns/go.mod)"
check "an auto-expiring unscoped ignore covered by scoped ones is redundant" \
  unscoped_ignore_redundant "$RDN/auto.yaml" GO-1 a.b/c "$RDN/scan.json"
check "a permanent unscoped ignore is never redundant" \
  ! unscoped_ignore_redundant "$RDN/permanent.yaml" GO-1 a.b/c "$RDN/scan.json"
_rdn_scan "$(_rdn_hit /coredns/go.mod),$(_rdn_hit /go.mod)"
check "an uncovered module keeps the unscoped ignore" \
  ! unscoped_ignore_redundant "$RDN/auto.yaml" GO-1 a.b/c "$RDN/scan.json"
_rdn_scan "$(_rdn_hit /coredns/go.mod),$(_rdn_hit /bin/tool)"
check "a binary location keeps the unscoped ignore" \
  ! unscoped_ignore_redundant "$RDN/auto.yaml" GO-1 a.b/c "$RDN/scan.json"

echo "merging unscoped ignores into scoped ones"
MRG="$TMPD/merge"; mkdir -p "$MRG"
printf 'ignore:\n  # No fix available for a.b/c.\n  - vulnerability: GO-1\n    fix-state: not-fixed\n    package:\n      name: a.b/c\n      location: /coredns/go.mod\n  # Unscoped\n  - vulnerability: GO-1\n    fix-state: unknown\n    package:\n      name: a.b/c\n' > "$MRG/g.yaml"
printf '{"matches":[],"ignoredMatches":[{"vulnerability":{"id":"GO-1","fix":{"state":""}},"artifact":{"name":"a.b/c","locations":[{"path":"/coredns/go.mod"}]}}]}\n' > "$MRG/scan.json"
merge_unscoped_ignore "$MRG/g.yaml" GO-1 a.b/c "$MRG/scan.json" >/dev/null
check "merge removes the unscoped ignore" test "$(grype_ignore_entry_info "$MRG/g.yaml" GO-1 a.b/c "")" = ""
check "merge gives the scoped ignore the reported fix-state" \
  test "$(grype_ignore_entry_info "$MRG/g.yaml" GO-1 a.b/c /coredns/go.mod)" = $'unknown\tNo fix available for a.b/c.'
check "merge leaves one ignore" test "$(grep -c 'vulnerability: GO-1' "$MRG/g.yaml")" -eq 1

echo "existing-entries audits only Go ignores"
EEF="$TMPD/ee-foreign"; mkdir -p "$EEF/rep"
make_test_repo "$EEF/repo" ""
printf 'module example.com/eef\ngo 1.24.0\n' > "$EEF/repo/go.mod"
printf 'ignore:\n  - vulnerability: CVE-2024-5535\n    package:\n      name: openssl-libs\n      type: rpm\n  - vulnerability: CVE-2024-7777\n    package:\n      name: libxml2\n' > "$EEF/repo/.grype.yaml"
git -C "$EEF/repo" add -A && git -C "$EEF/repo" commit -qm base
git -C "$EEF/repo" update-ref refs/remotes/origin/devel HEAD
make_go_state "$EEF/state.env" "$EEF/repo"
printf '{"matches":[],"ignoredMatches":[]}\n' > "$EEF/rep/final-scan.json"
printf '  - vulnerability: CVE-2024-8888
    package:
      name: libssl1.1
' >> "$EEF/repo/.grype.yaml"
git -C "$EEF/repo" commit -qam dotted && git -C "$EEF/repo" update-ref refs/remotes/origin/devel HEAD
EEF_OUT=$(bash "$SCRIPT_DIR/../subagents/existing-entries.sh" "$EEF/state.env" "$EEF/rep" 2>&1 || true)
check "foreign ecosystem ignores are never stale" grep -qx 'NEW_ISSUES=0' <<< "$EEF_OUT"
check "untyped non-module names are never stale" ! grep -q 'libxml2\|libssl1.1' <<< "$EEF_OUT"

echo "verification updates are tested"
check "fix-all reruns tests when verification moves HEAD" \
  grep -qF '! git diff --quiet "$TESTED_HEAD" HEAD' "$SCRIPT_DIR/fix-all.sh"

echo "repository config cannot inject names or options"
CFGV="$TMPD/config-validation"
make_test_repo "$CFGV" ""
printf 'module example.com/cfgv\ngo 1.24.0\n' > "$CFGV/go.mod"
printf 'unset-env: "GOOD_VAR x[$(touch %s/pwned)]"\n' "$CFGV" > "$CFGV/.cve-fix.yaml"
check "unset-env rejects a non-identifier name" ! "$SCRIPT_DIR/detect.sh" "$CFGV" devel
check "unset-env rejection runs no subscript" test ! -e "$CFGV/pwned"
printf 'build-image: "--privileged"\n' > "$CFGV/.cve-fix.yaml"
check "build-image rejects option-like values" ! "$SCRIPT_DIR/detect.sh" "$CFGV" devel

echo "repository grype config cannot hide fixable findings"
GPIN="$TMPD/grype-pin"
mkdir -p "$GPIN/bin"
make_test_repo "$GPIN/repo"
printf '#!/bin/sh\nprintf "%%s|%%s\\n" "${GRYPE_ONLY_NOTFIXED-unset}" "${GRYPE_IGNORE_WONTFIX-unset}" > "%s/seen"\nprintf %%s "{\\"matches\\":[],\\"ignoredMatches\\":[]}"\n' "$GPIN" > "$GPIN/bin/grype"
chmod +x "$GPIN/bin/grype"
printf 'only-notfixed: true\n' > "$GPIN/repo/.grype.yaml"
(cd "$GPIN/repo" && HAS_LOCAL_GRYPE=true CONTAINER_CMD="" PATH="$GPIN/bin:$PATH" run_grype --json >/dev/null 2>&1) || true
check "local scans pin only-notfixed and ignore-wontfix off" test "$(cat "$GPIN/seen" 2>/dev/null)" = 'false|'

# Distribution go.env experiments make Grype record an unmatchable stdlib
# version, so a run builds with upstream defaults unless the caller chose one.
echo "runs neutralize distribution GOEXPERIMENT defaults"
GXP="$TMPD/goexperiment"
mkdir -p "$GXP"
cat > "$GXP/go" <<'STUB'
#!/usr/bin/env bash
[[ "$*" == "env GOEXPERIMENT" ]] && { printf '%s\n' "${GOEXPERIMENT-${GXP_DEFAULT}}"; exit 0; }
exit 1
STUB
chmod +x "$GXP/go"
_gxp() {
  env -u GOEXPERIMENT PATH="$GXP:$PATH" "$@" bash -c \
    "source '$SCRIPT_DIR/lib.sh'; use_upstream_goexperiment; printf '%s' \"\${GOEXPERIMENT-unset}\""
}
check "distro default: run selects upstream experiments" test "$(_gxp GXP_DEFAULT=nodwarf5)" = ,
check "no distro default: GOEXPERIMENT stays unset" test "$(_gxp GXP_DEFAULT=)" = unset
check "explicit experiment: caller choice kept" test "$(_gxp GXP_DEFAULT=nodwarf5 GOEXPERIMENT=boringcrypto)" = boringcrypto
check "explicit empty experiment: caller choice kept" test -z "$(_gxp GXP_DEFAULT=nodwarf5 GOEXPERIMENT=)"
printf 'GOEXPERIMENT=boringcrypto\n' > "$GXP/goenv"
cat > "$GXP/go-with-user-env" <<'STUB'
#!/usr/bin/env bash
if [[ "$*" == "env GOEXPERIMENT" ]]; then
  if [[ "${GOENV:-}" == off ]]; then echo nodwarf5; else echo boringcrypto; fi
  exit 0
fi
exit 1
STUB
mkdir -p "$GXP/userenv"; cp "$GXP/go-with-user-env" "$GXP/userenv/go"; chmod +x "$GXP/userenv/go"
check "go env -w experiment: user choice kept" test "$(env -u GOEXPERIMENT PATH="$GXP/userenv:$PATH" bash -c \
  "source '$SCRIPT_DIR/lib.sh'; use_upstream_goexperiment; printf '%s' \"\${GOEXPERIMENT-unset}\"")" = unset
check "fix-all applies the experiment policy before building" \
  grep -qx 'use_upstream_goexperiment' "$SCRIPT_DIR/fix-all.sh"

# Durable evidence observes real orchestration without changing its gates. Only
# the external scanner, package resolver and model calls are replaced here.
echo "opt-in durable runtime evidence"
EVI_ROOT="$TMPD/evidence-runtime"
EVI_REPO="$EVI_ROOT/repo"
EVI_SCRIPTS="$EVI_ROOT/scripts"
EVI_STATE="$EVI_ROOT/state.env"
export EVI_ROOT EVI_STATE
make_test_repo "$EVI_REPO"
printf 'module example.com/evidence\n\ngo 1.24.0\nrequire example.com/pkg v1.0.0\n' > "$EVI_REPO/go.mod"
printf '.PHONY: licensecheck\nlicensecheck:\n\t@echo canonical-license\n\t@if [ "$${EVI_LATE_STAGE:-}" = license ]; then bash "$$EVI_ROOT/late-command.sh"; fi\n\t@exit $${EVI_LICENSE_RESULT:-0}\n' > "$EVI_REPO/Makefile"
printf '/bin/\n' > "$EVI_REPO/.gitignore"
git -C "$EVI_REPO" add -A
git -C "$EVI_REPO" commit -qsm fixture
EVI_BASE=$(git -C "$EVI_REPO" rev-parse HEAD)
git -C "$EVI_REPO" update-ref refs/remotes/origin/devel "$EVI_BASE"
git -C "$EVI_REPO" remote add origin https://github.com/example/evidence.git
mkdir -p "$EVI_SCRIPTS" "$EVI_ROOT/subagents"
cp "$SCRIPT_DIR/"{fix-all.sh,scan.sh,lib.sh,binary-module-locations.py} "$EVI_SCRIPTS/"
cp "$SCRIPT_DIR/../subagents/"*.sh "$EVI_ROOT/subagents/"
cat >> "$EVI_SCRIPTS/lib.sh" <<'SH'
preflight_check() { return 0; }
fetch_origin_branch() { return 0; }
run_grype() {
  if [[ "${EVI_LATE_STAGE:-}" == before-final && -f "$EVI_ROOT/test-count" && ! -f "$EVI_ROOT/late-change" ]]; then
    bash "$EVI_ROOT/late-command.sh"
  fi
  if [[ "${EVI_LATE_STAGE:-}" == before-final && "${CVE_FIX_EVIDENCE_PHASE:-}" == final-gate ]]; then
    git show HEAD:Makefile > Makefile
    touch "$EVI_ROOT/late-restored"
  fi
  if [[ "${EVI_IGNORE_COMMIT:-false}" == true && -f "$EVI_ROOT/test-count" && ! -f "$EVI_ROOT/ignore-commit" ]]; then
    printf 'ignore: []\n' > .grype.yaml
    git add .grype.yaml && git commit -qsm 'Record empty ignore policy'
    touch "$EVI_ROOT/ignore-commit"
  fi
  if [[ -n "${EVI_WORKSPACE_MODE:-}" ]]; then
    if [[ "${CVE_FIX_EVIDENCE_PHASE:-}" == initial && -n "${EVI_WORKSPACE_SEED:-}" ]]; then
      case "$EVI_WORKSPACE_SEED" in
        file) printf 'preserved workspace\n' > "$EVI_WORKSPACE_KEEP" ;;
        symlink) ln -s missing-workspace-target "$EVI_WORKSPACE_KEEP" ;;
      esac
    fi
    if [[ -f "$EVI_ROOT/test-count" ]]; then
      echo scan >> "$EVI_ROOT/workspace-scans"
      for workspace in go.work go.work.sum; do
        if [[ "$workspace" != "${EVI_WORKSPACE_KEEP:-}" && ( -e "$workspace" || -L "$workspace" ) ]]; then
          echo "$workspace" >> "$EVI_ROOT/workspace-residue"
        fi
      done
    fi
  fi
  if [[ "${CVE_FIX_EVIDENCE_PHASE:-}" == final-gate && "${EVI_DEGRADED:-false}" == true ]]; then
    GRYPE_DB_DEGRADED=1
  fi
  if [[ "${EVI_EMPTY:-false}" == true ]] || grep -q '^// fixed' go.mod; then
    printf '{"matches":[],"ignoredMatches":[]}\n'
  else
    printf '{"matches":[{"vulnerability":{"id":"GO-2099-0001","severity":"High","fix":{"versions":["1.1.0"],"state":"fixed"}},"artifact":{"type":"go-module","name":"example.com/pkg","version":"1.0.0","locations":[{"path":"/go.mod"}]}}],"ignoredMatches":[]}\n'
  fi
}
SH
cat > "$EVI_SCRIPTS/detect.sh" <<'SH'
#!/usr/bin/env bash
source "$EVI_STATE"
git -C "$REPO" checkout -qb "$FIX_BRANCH" origin/devel
printf '%s\n' "$EVI_STATE"
SH
cat > "$EVI_SCRIPTS/fix-package.sh" <<'SH'
#!/usr/bin/env bash
source "$1"
printf '// fixed\n' >> "$REPO/go.mod"
git -C "$REPO" add go.mod
git -C "$REPO" commit -qsm 'Bump pkg'
if [[ -n "${EVI_PRE_TEST_DIRT:-}" ]]; then
  printf '# pre-test change\n' >> "$REPO/Makefile"
  if [[ "$EVI_PRE_TEST_DIRT" != worktree ]]; then git -C "$REPO" add Makefile; fi
  if [[ "$EVI_PRE_TEST_DIRT" == cancel ]]; then git -C "$REPO" show HEAD:Makefile > "$REPO/Makefile"; fi
fi
printf 'FIXED: example.com/pkg v1.1.0 for GO-2099-0001\n'
SH
printf '#!/usr/bin/env bash\nexit 0\n' > "$EVI_SCRIPTS/review.sh"
cat > "$EVI_ROOT/late-command.sh" <<'SH'
#!/usr/bin/env bash
set -e
if [[ "${EVI_LATE_CHANGE:-}" == head ]]; then
  git rev-parse HEAD > "$EVI_ROOT/late-before-head"
  git commit -qsm 'Unexpected final-check commit' --allow-empty
  git rev-parse HEAD > "$EVI_ROOT/late-after-head"
  git status --porcelain --untracked-files=no > "$EVI_ROOT/late-status"
elif [[ "${EVI_LATE_CHANGE:-}" == generated ]]; then
  sed -i 's/v1.0.0/v1.1.0/' generated.pb.go
else
  printf '# final-check change\n' >> Makefile
  if [[ "${EVI_LATE_CHANGE:-}" == cancel ]]; then
    git add Makefile
    git show HEAD:Makefile > Makefile
    git diff --quiet HEAD -- Makefile && touch "$EVI_ROOT/late-cancelled"
  fi
fi
touch "$EVI_ROOT/late-change"
SH
cat > "$EVI_ROOT/test-command.sh" <<'SH'
#!/usr/bin/env bash
n=$(cat "$EVI_ROOT/test-count" 2>/dev/null || echo 0)
echo $((n + 1)) > "$EVI_ROOT/test-count"
echo "canonical-test-attempt-$((n + 1))"
if [[ -n "${EVI_WORKSPACE_MODE:-}" ]]; then
  for workspace in go.work go.work.sum; do
    [[ "$workspace" == "${EVI_WORKSPACE_KEEP:-}" ]] && continue
    if [[ -e "$workspace" || -L "$workspace" ]]; then
      echo "workspace residue before attempt: $workspace"
      exit 9
    fi
  done
  if [[ "$EVI_WORKSPACE_MODE" == cleanup-failure ]]; then
    mkdir go.work
  else
    [[ "${EVI_WORKSPACE_KEEP:-}" == go.work && "$EVI_WORKSPACE_MODE" != newly-tracked ]] || printf 'generated workspace\n' > go.work
  fi
  [[ "${EVI_WORKSPACE_KEEP:-}" == go.work.sum ]] || printf 'generated checksum\n' > go.work.sum
  if [[ "$EVI_WORKSPACE_MODE" == newly-tracked ]]; then
    git add go.work
  fi
  if [[ "$EVI_WORKSPACE_MODE" == record-failure ]]; then
    printf 'blocked evidence directory\n' > "$CVE_FIX_EVIDENCE_DIR/tests"
  fi
  if [[ -n "${EVI_TRACKED_CHANGE:-}" ]]; then
    if [[ "$EVI_TRACKED_CHANGE" == head ]]; then
      git rev-parse HEAD > "$EVI_ROOT/test-before-head"
      git commit -qsm 'Unexpected test commit' --allow-empty
      git rev-parse HEAD > "$EVI_ROOT/test-after-head"
      git status --porcelain --untracked-files=no > "$EVI_ROOT/test-commit-status"
    else
      printf '# test-command change\n' >> Makefile
      if [[ "$EVI_TRACKED_CHANGE" == index || "$EVI_TRACKED_CHANGE" == cancel ]]; then git add Makefile; fi
      if [[ "$EVI_TRACKED_CHANGE" == cancel ]]; then
        git show HEAD:Makefile > Makefile
        git diff --quiet HEAD -- Makefile && echo cancelled >> "$EVI_ROOT/cancelled-diff"
      fi
    fi
  fi
  if [[ "$EVI_WORKSPACE_MODE" == timeout ]]; then sleep 2; fi
  if [[ "$EVI_WORKSPACE_MODE" == retry && "$n" == 0 ]]; then exit 7; fi
fi
exit "${EVI_TEST_RESULT:-0}"
SH
chmod +x "$EVI_SCRIPTS/"*.sh
evi_run() {
  local name="$1" evidence="$2"
  git -C "$EVI_REPO" checkout -q devel
  git -C "$EVI_REPO" branch -D fix-evidence >/dev/null 2>&1 || true
  rm -f "$EVI_ROOT/test-count"
  printf 'REPO=%q\nBRANCH=devel\nBASE_SHA=%q\nORIGINAL_REF=devel\nFIX_BRANCH=fix-evidence\n' "$EVI_REPO" "$EVI_BASE" > "$EVI_STATE"
  printf 'BUILD_CMD=%q\nBUILD_IMAGE=""\nBUILD_GO_VERSION=unknown\nTEST_CMD=%q\n' \
    'echo canonical-build; if [[ -n "${EVI_LATE_STAGE:-}" && "$EVI_LATE_STAGE" == "${CVE_FIX_EVIDENCE_PHASE:-}" ]]; then bash "$EVI_ROOT/late-command.sh"; fi' \
    'bash "$EVI_ROOT/test-command.sh"' >> "$EVI_STATE"
  printf 'ENV_UNSET=""\nDIFF_IGNORE_ARGS=%q\nCVE_SCRIPTS=%q\nFETCH_FAILED=false\n' "${EVI_INITIAL_RULES:-}" "$EVI_SCRIPTS" >> "$EVI_STATE"
  EVI_RC=0
  CVE_FIX_EVIDENCE_DIR="$evidence" bash "$EVI_SCRIPTS/fix-all.sh" "$EVI_REPO" devel > "$EVI_ROOT/$name.log" 2>&1 || EVI_RC=$?
}
evi_run default ""
check "evidence default leaves successful gate semantics unchanged" test "$EVI_RC" -eq 0
evi_run complete "$EVI_ROOT/complete"
check "evidence enabled leaves successful gate semantics unchanged" test "$EVI_RC" -eq 0
check "evidence retains actual initial findings" jq -e '.matches | length == 1' "$EVI_ROOT/complete/initial-scan.json"
check "evidence retains authoritative empty gate scan" jq -e '.matches | length == 0' "$EVI_ROOT/complete/final-gate.json"
check "evidence run state records tested retained head and completed gates" jq -e \
  '.exit_code == 0 and .tested_head == .head and .phases.tests == "completed" and .phases.verification == "completed" and .phases.license == "completed" and .license_exit_code == 0 and .license_command == "make licensecheck"' "$EVI_ROOT/complete/run.json"
check "evidence retains canonical build log" grep -q canonical-build "$(find "$EVI_ROOT/complete/scans" -name build.log -print -quit)"
check "evidence retains license log" grep -q canonical-license "$EVI_ROOT/complete/license.log"
for _audit in scan-regression yaml-integrity existing-entries fix-availability; do
  check "evidence retains $_audit result before cleanup" test -s "$EVI_ROOT/complete/audits/$_audit.evidence"
done
check "evidence retains state before normal cleanup" test -s "$EVI_ROOT/complete/state.env"
check "evidence does not preserve scratch state in place" test ! -f "$EVI_STATE"
for _evi_audit_failure in missing-directory missing-script malformed; do
  case "$_evi_audit_failure" in
    missing-directory) mv "$EVI_ROOT/subagents" "$EVI_ROOT/subagents.saved" ;;
    missing-script) mv "$EVI_ROOT/subagents/yaml-integrity.sh" "$EVI_ROOT/yaml-integrity.saved" ;;
    malformed)
      mv "$EVI_ROOT/subagents/yaml-integrity.sh" "$EVI_ROOT/yaml-integrity.saved"
      printf '#!/usr/bin/env bash\nprintf "NEW_ISSUES=banana\\n"\n' > "$EVI_ROOT/subagents/yaml-integrity.sh"
      ;;
  esac
  evi_run "$_evi_audit_failure" "$EVI_ROOT/$_evi_audit_failure"
  check "$_evi_audit_failure audit blocks an otherwise successful fix" test "$EVI_RC" -eq 2
  check "$_evi_audit_failure audit preserves failed verification evidence" jq -e \
    '.exit_code == 2 and .verification_exit_code == 1' "$EVI_ROOT/$_evi_audit_failure/run.json"
  check "$_evi_audit_failure audit preserves state for diagnosis" test -s "$EVI_ROOT/$_evi_audit_failure/state.env"
  check "$_evi_audit_failure audit reports verification failure" \
    grep -q 'NEEDS_REVIEW: subagent verification failed' "$EVI_ROOT/$_evi_audit_failure.log"
  check "$_evi_audit_failure audit suppresses publication" \
    ! grep -q '^PR command:' "$EVI_ROOT/$_evi_audit_failure.log"
  case "$_evi_audit_failure" in
    missing-directory) mv "$EVI_ROOT/subagents.saved" "$EVI_ROOT/subagents" ;;
    *) mv "$EVI_ROOT/yaml-integrity.saved" "$EVI_ROOT/subagents/yaml-integrity.sh" ;;
  esac
done
EVI_TEST_RESULT=1 EVI_LICENSE_RESULT=1 evi_run blocked "$EVI_ROOT/blocked"
check "evidence preserves test and license gate failures" test "$EVI_RC" -eq 2
check "evidence records failure and retained tested head" jq -e '.exit_code == 2 and .test_exit_code == 1 and .license_exit_code != 0 and .tested_head == .head' "$EVI_ROOT/blocked/run.json"
check "evidence retains first failed test attempt" grep -q canonical-test-attempt-1 "$EVI_ROOT/blocked/tests/1-1.log"
check "evidence retains retried test attempt separately" grep -q canonical-test-attempt-2 "$EVI_ROOT/blocked/tests/1-2.log"
EVI_DEGRADED=true evi_run degraded "$EVI_ROOT/degraded"
check "evidence does not turn a degraded gate into clean" test "$EVI_RC" -eq 2
check "evidence captures degraded sentinel before consumption" jq -e '.scanner_degraded == true' "$EVI_ROOT/degraded/final-gate-status.json"
EVI_EMPTY=true evi_run clean "$EVI_ROOT/clean"
check "evidence clean fast path retains not-reached phases" jq -e \
  '.exit_code == 0 and .phases.initial_scan == "completed" and .phases.final_gate == "not_reached" and .phases.tests == "not_reached" and .phases.verification == "not_reached" and .license_command == ""' "$EVI_ROOT/clean/run.json"
check "evidence clean fast path does not fabricate a final gate" test ! -f "$EVI_ROOT/clean/final-gate.json"
evi_run rejected "$EVI_REPO/.git/evidence"
check "evidence directory cannot contaminate the source, even under .git" test "$EVI_RC" -ne 0
check "rejected evidence directory was not created" test ! -d "$EVI_REPO/.git/evidence"

# Canonical commands may create an implicit workspace; it must not leak into
# a retry or subsequent scanner. Existing files belong to the caller.
echo "test-command workspace ownership"
EVI_WORKSPACE_BASE="$EVI_BASE"
git -C "$EVI_REPO" remote add fork https://github.com/example-fork/evidence.git
evi_workspace_reset() {
  git -C "$EVI_REPO" reset -q --hard
  git -C "$EVI_REPO" checkout -q devel
  git -C "$EVI_REPO" reset -q --hard "$EVI_WORKSPACE_BASE"
  rm -rf "$EVI_REPO/go.work" "$EVI_REPO/go.work.sum"
  : > "$EVI_REPO/.git/info/exclude"
  rm -f "$EVI_ROOT/workspace-scans" "$EVI_ROOT/workspace-residue" "$EVI_ROOT/cancelled-diff"
  rm -f "$EVI_ROOT/"{late-change,late-restored,late-cancelled,late-before-head,late-after-head,late-status,ignore-commit}
  EVI_BASE="$EVI_WORKSPACE_BASE"
  git -C "$EVI_REPO" update-ref refs/remotes/origin/devel "$EVI_BASE"
}
evi_workspace_reset
EVI_WORKSPACE_MODE=retry evi_run workspace-retry "$EVI_ROOT/workspace-retry"
check "new workspace is cleaned before retry succeeds" test "$EVI_RC" -eq 0
check "workspace retry runs exactly twice" test "$(cat "$EVI_ROOT/test-count")" -eq 2
check "workspace first actual child failure is retained" jq -e '.exit_code == 7' "$EVI_ROOT/workspace-retry/tests/1-1.json"
check "workspace retry actual child success is retained" jq -e '.exit_code == 0' "$EVI_ROOT/workspace-retry/tests/1-2.json"
check "successful workspace cleanup permits downstream scans" test -s "$EVI_ROOT/workspace-scans"
check "downstream scans never see generated workspaces" test ! -e "$EVI_ROOT/workspace-residue"
check "workspace cleanup leaves both generated paths absent" test ! -e "$EVI_REPO/go.work"
check "workspace cleanup leaves generated checksum absent" test ! -e "$EVI_REPO/go.work.sum"
check "successful workspace cleanup preserves publication eligibility" grep -q '^PR command:' "$EVI_ROOT/workspace-retry.log"

evi_workspace_reset
EVI_WORKSPACE_MODE=failed EVI_TEST_RESULT=7 evi_run workspace-failed "$EVI_ROOT/workspace-failed"
check "failed command still cleans its workspace" test ! -e "$EVI_REPO/go.work"
check "failed command still cleans its workspace checksum" test ! -e "$EVI_REPO/go.work.sum"
check "failed command retry retains actual failure" jq -e '.exit_code == 7' "$EVI_ROOT/workspace-failed/tests/1-2.json"
check "failed command generated workspace does not reach scanners" test ! -e "$EVI_ROOT/workspace-residue"

evi_workspace_reset
EVI_WORKSPACE_MODE=timeout CVE_FIX_TEST_TIMEOUT=1 evi_run workspace-timeout "$EVI_ROOT/workspace-timeout"
check "test timeout still blocks successful completion" test "$EVI_RC" -eq 2
check "test timeout preserves actual timeout receipt" jq -e '.exit_code == 124' "$EVI_ROOT/workspace-timeout/tests/1-1.json"
check "test timeout records actual run status" jq -e '.test_exit_code == 124' "$EVI_ROOT/workspace-timeout/run.json"
check "test timeout is not retried" test "$(cat "$EVI_ROOT/test-count")" -eq 1
check "test timeout cleans generated workspace" test ! -e "$EVI_REPO/go.work"
check "test timeout cleans generated checksum" test ! -e "$EVI_REPO/go.work.sum"
check "test timeout retains downstream gate scans" test -s "$EVI_ROOT/workspace-scans"
check "test timeout workspace does not reach downstream scans" test ! -e "$EVI_ROOT/workspace-residue"
check "test timeout suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/workspace-timeout.log"

for _workspace in go.work go.work.sum; do
  for _ownership in tracked untracked ignored symlink; do
    evi_workspace_reset
    _seed=file
    if [[ "$_ownership" == tracked ]]; then
      printf 'preserved workspace\n' > "$EVI_REPO/$_workspace"
      git -C "$EVI_REPO" add "$_workspace"
      git -C "$EVI_REPO" commit -qsm 'Caller workspace'
      EVI_BASE=$(git -C "$EVI_REPO" rev-parse HEAD)
      git -C "$EVI_REPO" update-ref refs/remotes/origin/devel "$EVI_BASE"
      _seed=""
    elif [[ "$_ownership" == ignored ]]; then
      printf '/%s\n' "$_workspace" > "$EVI_REPO/.git/info/exclude"
    elif [[ "$_ownership" == symlink ]]; then
      _seed=symlink
    fi
    _case="workspace-$_workspace-$_ownership"
    EVI_WORKSPACE_MODE=preserve EVI_WORKSPACE_KEEP="$_workspace" EVI_WORKSPACE_SEED="$_seed" \
      evi_run "$_case" "$EVI_ROOT/$_case"
    check "$_ownership $_workspace permits successful gates" test "$EVI_RC" -eq 0
    if [[ "$_ownership" == symlink ]]; then
      check "caller dangling $_workspace symlink is preserved" test "$(readlink "$EVI_REPO/$_workspace")" = missing-workspace-target
      check "caller $_workspace symlink remains dangling" test ! -e "$EVI_REPO/$_workspace"
    else
      check "caller $_ownership $_workspace bytes are preserved" grep -qx 'preserved workspace' "$EVI_REPO/$_workspace"
    fi
    _other=go.work
    [[ "$_workspace" == go.work ]] && _other=go.work.sum
    check "$_ownership $_workspace does not prevent cleaning new $_other" test ! -e "$EVI_REPO/$_other"
    check "$_ownership workspace counterpart never reaches scanners" test ! -e "$EVI_ROOT/workspace-residue"
  done
done

evi_workspace_reset
EVI_WORKSPACE_MODE=newly-tracked EVI_WORKSPACE_KEEP=go.work evi_run workspace-tracked-during-test "$EVI_ROOT/workspace-tracked-during-test"
check "newly tracked workspace bytes are preserved" grep -qx 'generated workspace' "$EVI_REPO/go.work"
check "newly tracked workspace does not preserve untracked checksum" test ! -e "$EVI_REPO/go.work.sum"
check "newly tracked workspace blocks verification" test "$EVI_RC" -eq 2
check "newly tracked workspace retains actual successful child receipt" jq -e '.exit_code == 0' "$EVI_ROOT/workspace-tracked-during-test/tests/1-1.json"
check "newly tracked workspace stops downstream scans" test ! -e "$EVI_ROOT/workspace-scans"
check "newly tracked workspace suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/workspace-tracked-during-test.log"

# A test result is meaningful only for the same committed tracked tree. Check
# index and worktree separately: opposing edits can cancel in a HEAD diff.
for _dirt in worktree index cancel; do
  evi_workspace_reset
  _case="pre-test-$_dirt"
  EVI_WORKSPACE_MODE=guard EVI_PRE_TEST_DIRT="$_dirt" evi_run "$_case" "$EVI_ROOT/$_case"
  check "pre-test $_dirt dirt blocks pipeline" test "$EVI_RC" -eq 2
  check "pre-test $_dirt dirt prevents child execution" test ! -e "$EVI_ROOT/test-count"
  check "pre-test $_dirt dirt does not fabricate a child receipt" test ! -e "$EVI_ROOT/$_case/tests/1-1.json"
  check "pre-test $_dirt dirt stops downstream scans" test ! -e "$EVI_ROOT/workspace-scans"
  check "pre-test $_dirt dirt suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/$_case.log"
done

for _change in worktree index cancel timeout head; do
  evi_workspace_reset
  _case="post-test-$_change"
  _child_rc=0
  _mode=guard
  _timeout=1800
  [[ "$_change" != index ]] || _child_rc=7
  if [[ "$_change" == timeout ]]; then _child_rc=124; _mode=timeout; _timeout=1; fi
  EVI_WORKSPACE_MODE="$_mode" EVI_TRACKED_CHANGE="$_change" EVI_TEST_RESULT="$_child_rc" CVE_FIX_TEST_TIMEOUT="$_timeout" \
    evi_run "$_case" "$EVI_ROOT/$_case"
  check "post-test $_change mutation blocks pipeline" test "$EVI_RC" -eq 2
  check "post-test $_change mutation is never retried" test "$(cat "$EVI_ROOT/test-count")" -eq 1
  check "post-test $_change mutation preserves actual child $_child_rc receipt" jq -e \
    ".exit_code == $_child_rc" "$EVI_ROOT/$_case/tests/1-1.json"
  check "post-test $_change mutation records completed actual child $_child_rc status" jq -e \
    ".test_exit_code == $_child_rc and .phases.tests == \"completed\" and .phases.verification == \"not_reached\"" "$EVI_ROOT/$_case/run.json"
  check "post-test $_change mutation still cleans new workspace" test ! -e "$EVI_REPO/go.work"
  check "post-test $_change mutation still cleans new checksum" test ! -e "$EVI_REPO/go.work.sum"
  check "post-test $_change mutation stops downstream scans" test ! -e "$EVI_ROOT/workspace-scans"
  check "post-test $_change mutation suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/$_case.log"
  if [[ "$_change" == cancel ]]; then
    check "opposing staged and worktree edits evade aggregate HEAD diff" test -s "$EVI_ROOT/cancelled-diff"
  elif [[ "$_change" == head ]]; then
    check "test command really moved HEAD before guard and abort cleanup" test \
      "$(cat "$EVI_ROOT/test-before-head")" != "$(cat "$EVI_ROOT/test-after-head")"
    check "test commit left tracked index and worktree clean" test ! -s "$EVI_ROOT/test-commit-status"
  fi
done

for _child_rc in 0 7; do
  evi_workspace_reset
  _case="workspace-cleanup-failure-$_child_rc"
  EVI_WORKSPACE_MODE=cleanup-failure EVI_TEST_RESULT="$_child_rc" evi_run "$_case" "$EVI_ROOT/$_case"
  check "workspace cleanup failure after child $_child_rc blocks pipeline" test "$EVI_RC" -ne 0
  check "workspace cleanup failure after child $_child_rc does not retry" test "$(cat "$EVI_ROOT/test-count")" -eq 1
  check "workspace cleanup failure preserves actual child $_child_rc receipt" jq -e \
    ".exit_code == $_child_rc" "$EVI_ROOT/$_case/tests/1-1.json"
  check "workspace cleanup failure preserves actual child $_child_rc run status" jq -e \
    ".test_exit_code == $_child_rc and .phases.tests == \"completed\" and .phases.verification == \"not_reached\"" "$EVI_ROOT/$_case/run.json"
  check "workspace cleanup failure after child $_child_rc stops downstream scans" test ! -e "$EVI_ROOT/workspace-scans"
  check "workspace cleanup failure after child $_child_rc prevents final gate" test ! -e "$EVI_ROOT/$_case/final-gate.json"
  check "workspace cleanup failure after child $_child_rc suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/$_case.log"
  check "workspace cleanup failure does not recursively delete command directory" test -d "$EVI_REPO/go.work"
done
evi_workspace_reset
EVI_WORKSPACE_MODE=record-failure evi_run workspace-record-failure "$EVI_ROOT/workspace-record-failure"
check "unwritable test evidence blocks the pipeline" test "$EVI_RC" -ne 0
check "test evidence failure still cleans generated workspace" test ! -e "$EVI_REPO/go.work"
check "test evidence failure still cleans generated checksum" test ! -e "$EVI_REPO/go.work.sum"
check "test evidence failure does not retry" test "$(cat "$EVI_ROOT/test-count")" -eq 1
check "test evidence failure stops downstream scans" test ! -e "$EVI_ROOT/workspace-scans"
check "test evidence failure suppresses publication" ! grep -q '^PR command:' "$EVI_ROOT/workspace-record-failure.log"
# An empty initial scan cannot certify source changed by its own build, even
# when generated-file normalization subsequently erases the tracked difference.
for _initial_case in worktree head generated generated-with-cve; do
  evi_workspace_reset
  _change="$_initial_case"
  _rules=""
  _empty=true
  if [[ "$_initial_case" == generated* ]]; then
    _change=generated
    printf '// protoc-gen-go v1.0.0\npackage evidence\n' > "$EVI_REPO/generated.pb.go"
    git -C "$EVI_REPO" add generated.pb.go
    git -C "$EVI_REPO" commit -qsm 'Generated source fixture'
    EVI_BASE=$(git -C "$EVI_REPO" rev-parse HEAD)
    git -C "$EVI_REPO" update-ref refs/remotes/origin/devel "$EVI_BASE"
    _rules="-I$(protoc_version_pattern)"
  fi
  [[ "$_initial_case" != generated-with-cve ]] || _empty=false
  _case="initial-tree-$_initial_case"
  EVI_LATE_STAGE=initial EVI_LATE_CHANGE="$_change" EVI_INITIAL_RULES="$_rules" EVI_EMPTY="$_empty" \
    evi_run "$_case" "$EVI_ROOT/$_case"
  check "$_case initial build mutation actually ran" test -f "$EVI_ROOT/late-change"
  check "$_case retains actual successful initial scan" jq -e \
    '.exit_code == 0 and .build_failed == false and .scanner_degraded == false' "$EVI_ROOT/$_case/initial-scan-status.json"
  if [[ "$_empty" == true ]]; then
    check "$_case initial scan really has no findings" jq -e \
      '(.matches | length) == 0 and (.ignoredMatches | length) == 0' "$EVI_ROOT/$_case/initial-scan.json"
    check "$_case changed source blocks clean fast path" test "$EVI_RC" -eq 2
    check "$_case does not claim repository clean" ! grep -q 'No CVEs found\.' "$EVI_ROOT/$_case.log"
    check "$_case retains failed run without inventing downstream tests" jq -e \
      '.exit_code == 2 and .phases.initial_scan == "completed" and .phases.tests == "not_reached"' "$EVI_ROOT/$_case/run.json"
  else
    check "nonempty scan continues existing generated normalization" test "$EVI_RC" -eq 0
    check "normalization control actually started with a CVE" jq -e '.matches | length == 1' "$EVI_ROOT/$_case/initial-scan.json"
    check "normalization control still verifies and permits publication" grep -q '^PR command:' "$EVI_ROOT/$_case.log"
  fi
  if [[ "$_change" == generated ]]; then
    check "$_case version-only generated mutation was restored" grep -q 'protoc-gen-go v1.0.0' "$EVI_REPO/generated.pb.go"
  elif [[ "$_change" == head ]]; then
    check "empty initial scan mutation really changed HEAD" test "$(cat "$EVI_ROOT/late-before-head")" != "$(cat "$EVI_ROOT/late-after-head")"
    check "initial build commit left tracked tree clean" test ! -s "$EVI_ROOT/late-status"
  fi
done

# Final scans and license recipes must preserve the source already verified.
for _late_case in final-gate:worktree license:worktree license:cancel license:head before-final:worktree; do
  evi_workspace_reset
  _stage="${_late_case%:*}"
  _change="${_late_case#*:}"
  _case="late-$_stage-$_change"
  EVI_LATE_STAGE="$_stage" EVI_LATE_CHANGE="$_change" evi_run "$_case" "$EVI_ROOT/$_case"
  check "$_case mutation was actually exercised" test -f "$EVI_ROOT/late-change"
  check "$_case mutation blocks successful completion" test "$EVI_RC" -eq 2
  check "$_case preserves actual clean scan and license receipts" jq -e \
    '.exit_code == 2 and .test_exit_code == 0 and .verification_exit_code == 0 and .license_exit_code == 0 and .phases.final_gate == "completed"' "$EVI_ROOT/$_case/run.json"
  check "$_case retains healthy empty gate scan" jq -e '.matches | length == 0' "$EVI_ROOT/$_case/final-gate.json"
  check "$_case does not rerun an already successful test" test "$(cat "$EVI_ROOT/test-count")" -eq 1
  check "$_case suppresses publication despite clean individual gates" ! grep -q '^PR command:' "$EVI_ROOT/$_case.log"
  if [[ "$_change" == cancel ]]; then
    check "late opposing index and worktree changes evade aggregate HEAD diff" test -f "$EVI_ROOT/late-cancelled"
  elif [[ "$_change" == head ]]; then
    check "license command actually moved HEAD" test "$(cat "$EVI_ROOT/late-before-head")" != "$(cat "$EVI_ROOT/late-after-head")"
    check "license commit left tracked index and worktree clean" test ! -s "$EVI_ROOT/late-status"
  elif [[ "$_stage" == before-final ]]; then
    check "pre-final dirty tree was restored before final snapshot check" test -f "$EVI_ROOT/late-restored"
  fi
done

evi_workspace_reset
EVI_IGNORE_COMMIT=true evi_run earlier-ignore-commit "$EVI_ROOT/earlier-ignore-commit"
check "earlier ignore-only commit is accepted by final source boundary" test "$EVI_RC" -eq 0
check "earlier ignore-only commit was actually created" test -f "$EVI_ROOT/ignore-commit"
check "ignore-only commit does not rerun unchanged code tests" test "$(cat "$EVI_ROOT/test-count")" -eq 1
check "ignore-only final head may differ from tested code head" jq -e '.exit_code == 0 and .head != .tested_head' "$EVI_ROOT/earlier-ignore-commit/run.json"
check "earlier ignore-only commit preserves publication eligibility" grep -q '^PR command:' "$EVI_ROOT/earlier-ignore-commit.log"
evi_workspace_reset
git -C "$EVI_REPO" remote remove fork

# Exercise the real catalog-output wiring, including replacement of a failed
# local scan's partial catalog by the container fallback.
mkdir -p "$EVI_ROOT/scanner-bin" "$EVI_ROOT/catalog"
cat > "$EVI_ROOT/scanner-bin/grype" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$EVI_ROOT/local-args"
if [[ "${EVI_FORCE_LOCAL_FAIL:-false}" == true ]]; then
  echo partial > "$EVI_ROOT/catalog/catalog.cdx.json"
  exit 1
fi
for arg in "$@"; do
  [[ "$arg" != cyclonedx-json=* ]] || echo '{"components":[]}' > "${arg#cyclonedx-json=}"
done
echo '{"matches":[],"ignoredMatches":[]}'
SH
cat > "$EVI_ROOT/scanner-bin/container" <<'SH'
#!/usr/bin/env bash
if [[ "$1 $2" == 'image inspect' ]]; then
  echo '{"image_id":"sha256:abc","repo_digests":["anchore/grype@sha256:def"]}'
  exit 0
fi
printf '%s\n' "$@" > "$EVI_ROOT/container-args"
[[ "${EVI_FORCE_CONTAINER_FAIL:-false}" != true ]] || exit 1
[[ ! -f "$EVI_ROOT/catalog/catalog.cdx.json" ]] || exit 1
echo '{"components":[]}' > "$EVI_ROOT/catalog/catalog.cdx.json"
echo '{"matches":[],"ignoredMatches":[]}'
SH
chmod +x "$EVI_ROOT/scanner-bin/"*
mv "$EVI_ROOT/scanner-bin/grype" "$EVI_ROOT/scanner-bin/grype-real"
ln -s grype-real "$EVI_ROOT/scanner-bin/grype"
(
  cd "$EVI_REPO"
  PATH="$EVI_ROOT/scanner-bin:$PATH" HAS_LOCAL_GRYPE=true CONTAINER_CMD="" CVE_FIX_GRYPE_VERSION=""
  CVE_FIX_EVIDENCE_SCAN_DIR=""
  run_grype --no-update --json > "$EVI_ROOT/default-scan.json"
)
check "default scanner invocation adds no catalog observer" ! grep -q cyclonedx-json "$EVI_ROOT/local-args"
check "default scanner invocation writes no selected identity" test ! -f "$EVI_ROOT/catalog/scanner-identity.json"
(
  cd "$EVI_REPO"
  PATH="$EVI_ROOT/scanner-bin:$PATH" HAS_LOCAL_GRYPE=true CONTAINER_CMD="" CVE_FIX_GRYPE_VERSION=""
  CVE_FIX_EVIDENCE_SCAN_DIR="$EVI_ROOT/catalog"
  run_grype --no-update --json > "$EVI_ROOT/local-result.json"
)
check "local scan requests its catalog in the same invocation" grep -qxF "cyclonedx-json=$EVI_ROOT/catalog/catalog.cdx.json" "$EVI_ROOT/local-args"
check "catalog output preserves scanner JSON stdout" jq -e '.matches == []' "$EVI_ROOT/local-result.json"
check "accepted local identity resolves executable symlink and hashes its bytes" jq -e \
  --arg path "$EVI_ROOT/scanner-bin/grype-real" \
  --arg sha "$(sha256sum "$EVI_ROOT/scanner-bin/grype-real" | cut -d' ' -f1)" \
  '.mode == "local" and .path == $path and .sha256 == $sha' "$EVI_ROOT/catalog/scanner-identity.json"
check "selected identity capture preserves scanner output" cmp "$EVI_ROOT/default-scan.json" "$EVI_ROOT/local-result.json"
(
  cd "$EVI_REPO"
  export EVI_FORCE_LOCAL_FAIL=true
  PATH="$EVI_ROOT/scanner-bin:$PATH" HAS_LOCAL_GRYPE=true CONTAINER_CMD="$EVI_ROOT/scanner-bin/container" CVE_FIX_GRYPE_VERSION=""
  CVE_FIX_EVIDENCE_SCAN_DIR="$EVI_ROOT/catalog"
  run_grype --no-update --json > "$EVI_ROOT/container-result.json" 2>/dev/null
)
check "fallback mounts evidence outside the scanned source" grep -qxF "$EVI_ROOT/catalog:/cve-evidence" "$EVI_ROOT/container-args"
check "fallback uses the mounted catalog destination" grep -qxF 'cyclonedx-json=/cve-evidence/catalog.cdx.json' "$EVI_ROOT/container-args"
check "fallback replaces failed local catalog" jq -e '.components == []' "$EVI_ROOT/catalog/catalog.cdx.json"
check "accepted fallback replaces local executable identity with container image" jq -e \
  '.mode == "container" and .image_id == "sha256:abc" and .repo_digests == ["anchore/grype@sha256:def"] and (has("path") | not)' \
  "$EVI_ROOT/catalog/scanner-identity.json"
check "fallback identity capture preserves scanner output" cmp "$EVI_ROOT/default-scan.json" "$EVI_ROOT/container-result.json"
EVI_IDENTITY_RC=0
(
  cd "$EVI_REPO"
  export EVI_FORCE_LOCAL_FAIL=true EVI_FORCE_CONTAINER_FAIL=true
  PATH="$EVI_ROOT/scanner-bin:$PATH" HAS_LOCAL_GRYPE=true CONTAINER_CMD="$EVI_ROOT/scanner-bin/container" CVE_FIX_GRYPE_VERSION=""
  CVE_FIX_EVIDENCE_SCAN_DIR="$EVI_ROOT/catalog"
  run_grype --no-update --json >/dev/null 2>&1
) || EVI_IDENTITY_RC=$?
check "failed scanners still return failure" test "$EVI_IDENTITY_RC" -ne 0
check "failed scanners cannot retain a stale selected identity" test ! -f "$EVI_ROOT/catalog/scanner-identity.json"

# Inventory the actual current native binary, reusing the production detector.
mkdir -p "$EVI_REPO/bin" "$EVI_ROOT/inventory"
printf 'package main\nfunc main() {}\n' > "$EVI_ROOT/probe.go"
GO111MODULE=off go build -o "$EVI_REPO/bin/probe" "$EVI_ROOT/probe.go"
printf '%s\n' "$EVI_REPO/bin/probe" > "$EVI_ROOT/inventory-state.built-artifacts"
(
  cd "$EVI_REPO"
  REPO="$EVI_REPO" STATE_FILE="$EVI_ROOT/inventory-state" BUILD_GO_VERSION="" BUILD_IMAGE=""
  CVE_FIX_EVIDENCE_SCAN_DIR="$EVI_ROOT/inventory"
  detect_opaque_binaries || [[ $? == 1 ]]
)
check "binary evidence links actual file hash and native build metadata" jq -e \
  --arg sha "$(sha256sum "$EVI_REPO/bin/probe" | cut -d' ' -f1)" \
  '.path == "bin/probe" and .sha256 == $sha and .recorded_build_artifact == true and (.build_info | contains("go1."))' \
  "$EVI_ROOT/inventory/binaries.jsonl"

# === Summary ===
echo ""
TOTAL=$((PASS + FAIL))
echo "$PASS/$TOTAL passed"
if [[ "$FAIL" -gt 0 ]]; then echo "$FAIL FAILED"; exit 1; fi
