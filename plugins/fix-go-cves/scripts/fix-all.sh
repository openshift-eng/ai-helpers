#!/usr/bin/env bash
set -euo pipefail
# fix-all.sh — End-to-end CVE fix pipeline for a single repository.
# Usage: fix-all.sh [repo] [branch]
#
# Phases:
#   1. Setup   — load helpers, check toolchain, register cleanup trap
#   2. Scan    — detect repo/branch, clean artifacts, run initial grype scan
#   3. Fix     — for each CVE group: ignore, fix-stdlib, or fix-package
#   4. Verify  — deterministic repair, final-tree tests
#   5. Gate    — authoritative final rescan; any remaining CVE = non-zero exit
#   6. Report  — summary headline, per-package detail, PR command

# ── Phase 1: Setup ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

# Allow sourcing for test isolation — skip main body when sourced.
[[ "${BASH_SOURCE[0]}" != "$0" ]] && return 0

# Fail fast if the toolchain can't support a real run.
preflight_check
use_upstream_goexperiment

_EVIDENCE_READY=false
_EVIDENCE_INITIAL_STATUS=not_reached
_EVIDENCE_FINAL_STATUS=not_reached
_EVIDENCE_TEST_STATUS=not_reached
_EVIDENCE_VERIFY_STATUS=not_reached
_EVIDENCE_LICENSE_STATUS=not_reached
_EVIDENCE_TEST_RUN=0
TESTED_HEAD=""
_TEST_ATTEMPT_RESULTS=()
INITIAL_SCAN_SCOPE="not established"
FINAL_SCAN_SCOPE="not reached"

# Check the expected checkout and tracked files. Later gates can restore only
# tolerated generator version stamps, without staging or accepting new source.
_tracked_tree_unchanged() {
  local expected_head="$1" expected_ref="${INITIAL_REF:-}" observed_head tracked_status
  observed_head=$(git rev-parse HEAD) || return 1
  if [[ "${2:-}" == --restore-generated-noise && "$observed_head" == "$expected_head" ]] &&
     { [[ -z "$expected_ref" ]] || checkout_matches "$expected_head" "$expected_ref"; }; then
    reconcile_generated_files --restore-only || return 1
  fi
  tracked_status=$(git status --porcelain --untracked-files=no) || return 1
  if [[ "$observed_head" == "$expected_head" && -z "$tracked_status" ]] &&
     { [[ -z "$expected_ref" ]] || checkout_matches "$expected_head" "$expected_ref"; }; then
    return 0
  fi
  printf 'Expected HEAD: %s; observed HEAD: %s\n' "$expected_head" "$observed_head" >&2
  [[ -z "$tracked_status" ]] || printf '%s\n' "$tracked_status" >&2
  return 1
}

# Only a completed, captured transaction may advance cleanup's owned commit.
_record_owned_head() {
  [[ "$(git symbolic-ref --quiet HEAD)" == "$INITIAL_REF" ]] || return 1
  OWNED_HEAD=$(git rev-parse --verify HEAD)
}

_record_test_evidence() {
  $_EVIDENCE_READY || return 0
  local rc="${1:-null}" target="$CVE_FIX_EVIDENCE_DIR/tests/$_EVIDENCE_TEST_RUN-$_EVIDENCE_TEST_ATTEMPT"
  mkdir -p "$CVE_FIX_EVIDENCE_DIR/tests" || return 1
  [[ ! -f "${TEST_LOG:-}" ]] || cp "$TEST_LOG" "$target.log" || return 1
  jq -n --arg head "${TESTED_HEAD:-}" --arg command "${TEST_CMD:-}" --argjson exit_code "$rc" \
    '{head:$head,command:$command,exit_code:$exit_code}' > "$target.json" || return 1
  _EVIDENCE_TEST_RECORDED=true
}

# shellcheck disable=SC2329 # invoked by the EXIT cleanup trap
_record_run_evidence() {
  $_EVIDENCE_READY || return 0
  if [[ "$_EVIDENCE_TEST_STATUS" == running ]]; then _record_test_evidence null || return 1; fi
  if [[ "$_EVIDENCE_TEST_STATUS" == completed && "${_EVIDENCE_TEST_RECORDED:-false}" != true ]]; then
    _record_test_evidence "$_EVIDENCE_TEST_RC" || return 1
  fi
  [[ ! -f "${STATE_FILE:-}" ]] || cp "$STATE_FILE" "$CVE_FIX_EVIDENCE_DIR/state.env" || return 1
  if [[ -d "${SUBAGENT_REPORT_DIR:-}" ]]; then
    mkdir -p "$CVE_FIX_EVIDENCE_DIR/audits" || return 1
    cp -R "$SUBAGENT_REPORT_DIR/." "$CVE_FIX_EVIDENCE_DIR/audits/" || return 1
  fi
  jq -n --argjson exit_code "$1" --arg repo "${REPO:-}" --arg base_branch "${BRANCH:-}" \
    --arg base_commit "${BASE_SHA:-}" --arg head "$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)" \
    --arg branch "$(git -C "$REPO" branch --show-current 2>/dev/null || true)" \
    --arg build_command "${BUILD_CMD:-}" --arg test_command "${TEST_CMD:-}" \
    --arg clean_command "${CLEAN_CMD:-}" --arg build_image "${BUILD_IMAGE:-}" \
    --arg build_go_version "${BUILD_GO_VERSION:-unknown}" --arg tested_head "${TESTED_HEAD:-}" \
    --arg initial_scan "$_EVIDENCE_INITIAL_STATUS" --arg final_gate "$_EVIDENCE_FINAL_STATUS" \
    --arg tests "$_EVIDENCE_TEST_STATUS" --argjson test_exit_code "${_EVIDENCE_TEST_RC:-null}" \
    --arg verification "$_EVIDENCE_VERIFY_STATUS" --argjson verification_exit_code "${_EVIDENCE_VERIFY_RC:-null}" \
    --arg license "$_EVIDENCE_LICENSE_STATUS" --argjson license_exit_code "${_EVIDENCE_LICENSE_RC:-null}" \
    '{exit_code:$exit_code,repo:$repo,base_branch:$base_branch,base_commit:$base_commit,head:$head,branch:$branch,
      build_command:$build_command,test_command:$test_command,clean_command:$clean_command,
      license_command:(if $license == "running" or $license == "completed" or $license == "capture_failed" then "make licensecheck" else "" end),
      build_image:$build_image,build_go_version:$build_go_version,tested_head:$tested_head,
      phases:{initial_scan:$initial_scan,final_gate:$final_gate,tests:$tests,verification:$verification,license:$license},
      test_exit_code:(if $tests == "completed" then $test_exit_code else null end),
      verification_exit_code:(if $verification == "completed" then $verification_exit_code else null end),
      license_exit_code:(if $license == "completed" or $license == "capture_failed" then $license_exit_code else null end)}' \
      > "$CVE_FIX_EVIDENCE_DIR/run.json"
}

# Clean up on exit without signaling the caller's process group. In some PTYs
# fix-all.sh is itself the process-group leader, so `kill -- -$$` signals this
# shell and replaces a successful/partial exit status with 1. Restrict process
# cleanup to background jobs launched by this shell.
# shellcheck disable=SC2317,SC2329 # invoked via trap
cleanup() {
  local exit_status="${1:-$?}"
  local child_pid
  while IFS= read -r child_pid; do
    [[ -n "$child_pid" ]] && kill "$child_pid" 2>/dev/null || true
  done < <(jobs -pr 2>/dev/null || true)
  # Only revert once the target repo is known. The trap installs before
  # 'cd "$REPO"', so an early failure would otherwise run these in the user's
  # invocation directory. Guard on REPO/FIX_BRANCH and target $REPO explicitly.
  local owns_checkout=false observed_branch="" observed_head="" owned_head=""
  if [[ -n "${FIX_BRANCH:-}" && -n "${REPO:-}" ]]; then
    observed_branch=$(git -C "$REPO" symbolic-ref --quiet HEAD) || true
    observed_head=$(git -C "$REPO" rev-parse --verify HEAD) || true
    owned_head="${TESTED_HEAD:-${OWNED_HEAD:-${INITIAL_HEAD:-}}}"
    if [[ -z "$owned_head" ]]; then
      owned_head=$(git -C "$REPO" rev-parse --verify "refs/heads/$FIX_BRANCH") || true
    fi
    if [[ "$observed_branch" == "refs/heads/$FIX_BRANCH" && -n "$owned_head" && "$observed_head" == "$owned_head" ]]; then
      owns_checkout=true
      git -C "$REPO" reset --quiet HEAD -- . 2>/dev/null || true
      git -C "$REPO" checkout -- . 2>/dev/null || true
    else
      echo "WARNING: Checkout no longer matches the run-owned state; preserving its files/index and $FIX_BRANCH for recovery." >&2
      printf 'Observed branch: %s; HEAD: %s\n' "${observed_branch:-detached or unavailable}" "${observed_head:-unavailable}" >&2
    fi
  fi
  # A completed run (including a confirmed partial result) keeps its fix branch.
  # An aborted run restores the original ref before deleting the branch;
  # otherwise an interrupt can strand the checkout on an unpublished fix branch.
  if [[ "${RUN_COMPLETED:-false}" != "true" && "$owns_checkout" == true ]]; then
    if [[ -n "${ORIGINAL_REF:-}" ]]; then
      if [[ "${ORIGINAL_REF}" == "HEAD" ]]; then
        git -C "$REPO" checkout -q --detach HEAD 2>/dev/null || true
      else
        git -C "$REPO" checkout -q "$ORIGINAL_REF" 2>/dev/null || true
      fi
    fi
    git -C "$REPO" branch -D "$FIX_BRANCH" 2>/dev/null || true
  fi
  if ! _record_run_evidence "$exit_status"; then
    echo "WARNING: durable runtime evidence is incomplete; private diagnostics are preserved." >&2
    printf 'State: %s\nTests: %s\nFixes: %s\nReports: %s\n' \
      "${STATE_FILE:-unavailable}" "${TEST_LOG:-unavailable}" \
      "${FIX_LOG:-unavailable}" "${SUBAGENT_REPORT_DIR:-unavailable}" >&2
    return "$exit_status"
  fi
  if [[ -n "${STATE_FILE:-}" ]]; then
    rm -f "$STATE_FILE" "${STATE_FILE}.scan-scope" "${STATE_FILE}.build-failed" "${STATE_FILE}.network-broken" "${STATE_FILE}.scanner-degraded" "${STATE_FILE}.scan-transient" "${STATE_FILE}.coverage-unknown" "${STATE_FILE}.generated-artifacts" "${STATE_FILE}.built-artifacts" "${STATE_FILE}.baseline-artifacts" "${STATE_FILE}.generated-drift" 2>/dev/null || true
    rm -f "${STATE_FILE}.license.baseline-artifacts" "${STATE_FILE}.license.generated-artifacts" "${STATE_FILE}.license.built-artifacts" 2>/dev/null || true
    rmdir "$(dirname "$STATE_FILE")" 2>/dev/null || true
  fi
  # Preserve subagent reports on verification failure so they can be debugged;
  # the "see reports" message points here.
  if [[ -z "${PRESERVE_REPORTS:-}" && -n "${SUBAGENT_REPORT_DIR:-}" ]]; then
    rm -rf -- "$SUBAGENT_REPORT_DIR" 2>/dev/null || true
  fi
  rm -f "${FIX_LOG:-}" "${TEST_LOG:-}"
  return "$exit_status"
}
RUN_COMPLETED=false
SUBAGENT_REPORT_DIR=""
trap 'cleanup $?' EXIT
trap 'trap - INT TERM; exit 130' INT
trap 'trap - INT TERM; exit 143' TERM

# Read a sentinel file: set VARNAME=true and delete the file if it exists, else set false.
_read_sentinel() {
  local _f="${STATE_FILE}.${1}"
  if [[ -f "$_f" ]]; then printf -v "$2" true; rm -f "$_f"
  else printf -v "$2" false; fi
}

_remove_needs_review() {
  mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
    filter_package_outcomes NEEDS_REVIEW "$1" "${2:-}")
}

_remove_error_line() {
  mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
    filter_package_outcomes ERROR "$1" "${2:-}")
}

# ── Phase 2: Scan ─────────────────────────────────────────────────────────────

# detect.sh prints state file path as last line (and its own banner)
DETECT_OUT=$("$SCRIPT_DIR/detect.sh" "$@" --setup-branch) || die "detect.sh failed: $DETECT_OUT"
STATE_FILE=$(printf '%s\n' "$DETECT_OUT" | tail -1)
load_state "$STATE_FILE"
[[ -n "$UPSTREAM_REF" ]] || die "State does not identify the selected upstream remote"
if ! INITIAL_HEAD=$(git rev-parse HEAD); then
  echo "NEEDS_REVIEW: retained HEAD could not be confirmed before the initial scan." >&2
  exit 2
fi
INITIAL_REF=$(git symbolic-ref --quiet HEAD) || exit 2
OWNED_HEAD=$INITIAL_HEAD
printf '%s\n' "$DETECT_OUT" >&2
if [[ -n "${CVE_FIX_EVIDENCE_DIR:-}" ]]; then
  prepare_evidence_directory || die "Cannot prepare runtime evidence directory"
  [[ -z "$(find "$CVE_FIX_EVIDENCE_DIR" -mindepth 1 -print -quit)" ]] || die "Runtime evidence directory must be empty"
  _EVIDENCE_READY=true
fi

# Inherited selectors are maintainer policy. Do not let a build, clean command
# or the YAML repair loop erase them, even when a scanner would report no CVEs.
if [[ -e .grype.yaml || -L .grype.yaml ]]; then
  if ! python3 "$SCRIPT_DIR/check-grype-ignores.py" .grype.yaml; then
    echo "NEEDS_REVIEW: inherited Grype ignore policy is invalid or broad; maintainer must review .grype.yaml before rerunning." >&2
    exit 2
  fi
fi

echo ""
if [[ -n "${CLEAN_CMD:-}" ]]; then
  echo "Cleaning build artifacts..."
  _initial_clean_rc=0
  bounded_command "${CVE_FIX_BUILD_TIMEOUT:-1800}" bash -c "$CLEAN_CMD" 2>&1 || _initial_clean_rc=$?
  if [[ $_initial_clean_rc -ne 0 ]]; then
    echo "WARNING: clean command failed (exit $_initial_clean_rc). Continuing with existing artifacts."
  fi
  if ! checkout_matches "$INITIAL_HEAD" "$INITIAL_REF"; then
    echo "NEEDS_REVIEW: initial clean changed checkout; scanning stopped." >&2
    exit 2
  fi
fi

echo "Scanning for CVEs..."
SCAN_RC=0
_EVIDENCE_INITIAL_STATUS=running
SCAN_JSON=$(CVE_FIX_EVIDENCE_PHASE=initial BUILD_UPX=false "$SCRIPT_DIR/scan.sh" "$STATE_FILE" --fresh --json) || SCAN_RC=$?
INITIAL_TREE_UNCHANGED=true
_tracked_tree_unchanged "$INITIAL_HEAD" || INITIAL_TREE_UNCHANGED=false
_EVIDENCE_INITIAL_STATUS=completed
INITIAL_SCAN_SCOPE=$(cat "${STATE_FILE}.scan-scope" 2>/dev/null) || INITIAL_SCAN_SCOPE="not established"
if $_EVIDENCE_READY; then
  printf '%s\n' "$SCAN_JSON" > "$CVE_FIX_EVIDENCE_DIR/initial-scan.json"
  CVE_FIX_EVIDENCE_PHASE=initial record_scan_status "$CVE_FIX_EVIDENCE_DIR/initial-scan-status.json" "$SCAN_RC"
fi

# scan.sh records an initial-build failure in a sentinel file (its stdout is the
# grype JSON). A failed build means the scan saw source only and may have missed
# stdlib CVEs in compiled binaries — so we must not report the repo clean.
_read_sentinel build-failed     BUILD_FAILED

# scan.sh also records when a successful build produced packed/opaque binaries
# grype can't read: the scan then saw source (and readable binaries) only and may
# have missed stdlib CVEs in the opaque ones, so — like a build failure — the repo
# must not be reported clean. Only meaningful on the zero-dependency-CVE early
# exit below; when CVEs are fixed, the final rescan gate re-evaluates coverage.
_read_sentinel coverage-unknown COVERAGE_UNKNOWN

if ! checkout_matches "$INITIAL_HEAD" "$INITIAL_REF"; then
  echo "NEEDS_REVIEW: checkout changed during the initial scan; preserving its files and index." >&2
  exit 2
fi
record_generated_drift
if [[ -s "${STATE_FILE}.generated-drift" ]]; then
  echo "NOTE: generated files already out of date on $UPSTREAM_REF are left out of fix commits:"
  sed 's/^/  /' "${STATE_FILE}.generated-drift"
fi

# The initial scan may have run in a broken environment: a network/DNS build
# failure (.network-broken) or a grype DB that couldn't be updated
# (.scanner-degraded). Either makes the scan and every downstream step (go get,
# rebuild, rescan gate) untrustworthy, so abort fast and clearly — with a banner
# and the empty fix branch dropped — before touching anything. No-op when healthy.
abort_if_environment_broken "$STATE_FILE"

if [[ $SCAN_RC -ne 0 ]] || ! grype_scan_json_valid <<< "$SCAN_JSON"; then
  echo "NEEDS_REVIEW: initial scan failed or produced invalid Grype evidence — results unconfirmed"
  exit 2
fi
if ! _tracked_tree_unchanged "$INITIAL_HEAD"; then
  echo "NEEDS_REVIEW: initial clean/build changed tracked source; remediation stopped before accepting a new policy baseline." >&2
  exit 2
fi

if ! MATCH_COUNT=$(jq '[.matches[] | select(.artifact.type == "go-module")] | length' <<< "$SCAN_JSON" 2>/dev/null) || [[ -z "$MATCH_COUNT" ]]; then
  die "Scan failed or produced invalid output. Check scanner availability (grype or docker/podman)."
fi
IGNORED_MATCH_COUNT=$(jq '[.ignoredMatches[]? | select(.artifact.type == "go-module")] | length' <<< "$SCAN_JSON" 2>/dev/null || echo 0)

# Identify renamed Go types by package identity; other ecosystems are outside
# this remediation scope. Reuse the same probe for the authoritative final scan.
_GO_SCHEMA_TYPES='[.matches[] | select(.artifact.type != "go-module") |
  select((.artifact.purl // "") | startswith("pkg:golang/")) | .artifact.type] | unique | join(", ")'
_SCHEMA_TYPES=$(jq -r "$_GO_SCHEMA_TYPES" <<< "$SCAN_JSON") || die "Invalid Go package identity in scan evidence"
if [[ -n "$_SCHEMA_TYPES" ]]; then
  die "Schema mismatch: Go package identity has unsupported artifact type(s): $_SCHEMA_TYPES. Check 'grype version' and update the CVE fix scripts."
fi

if [[ "$MATCH_COUNT" -eq 0 ]] && $BUILD_FAILED; then
  echo "No dependency CVEs found, but the initial build FAILED — stdlib CVE"
  echo "coverage is unknown, so $(basename "$REPO")/$BRANCH is NOT reported clean."
  echo "NEEDS_REVIEW: initial build failed — fix the build and re-run."
  exit 2
fi

if [[ "$MATCH_COUNT" -eq 0 ]] && $COVERAGE_UNKNOWN; then
  echo "No dependency CVEs found, but binary stdlib coverage is unknown —"
  echo "stdlib CVE coverage is unknown, so $(basename "$REPO")/$BRANCH is NOT reported clean."
  echo "NEEDS_REVIEW: packed/opaque binaries or compiler metadata block stdlib scanning — rebuild with a supported compiler and without packing, then re-run."
  exit 2
fi

if [[ "$MATCH_COUNT" -eq 0 && "$IGNORED_MATCH_COUNT" -eq 0 ]]; then
  if ! $INITIAL_TREE_UNCHANGED; then
    echo "NEEDS_REVIEW: retained HEAD and clean tracked files could not be confirmed after the initial scan; clean result unconfirmed." >&2
    exit 2
  fi
  if [[ "${FETCH_FAILED:-false}" == true ]]; then
    echo "NEEDS_REVIEW: base branch fetch failed; an empty scan of cached state cannot confirm the current branch is clean"
    remove_fix_branch
    exit 2
  fi
  _SCOPE_CONFLICTS=$(grype_ignore_scope_conflicts "$REPO/.grype.yaml")
  if [[ -n "$_SCOPE_CONFLICTS" ]]; then
    echo "NEEDS_REVIEW: ignore policy has unscoped/scoped conflicts despite a clean scan"
    printf '%s\n' "$_SCOPE_CONFLICTS"
    exit 2
  fi
  echo "No CVEs found. $(basename "$REPO")/$BRANCH is clean."
  remove_fix_branch
  exit 0
fi

if [[ "$MATCH_COUNT" -gt 0 ]]; then
  echo "Found $MATCH_COUNT actionable CVE finding(s) in $(basename "$REPO")/$BRANCH."
else
  echo "No actionable findings; auditing $IGNORED_MATCH_COUNT ignored CVE finding(s) before declaring the repository clean."
fi

# Show summary table from JSON
jq -r '
  ["NAME","INSTALLED","FIXED-IN","TYPE","VULNERABILITY","SEVERITY"],
  (.matches[] | select(.artifact.type == "go-module") |
    [.artifact.name, .artifact.version,
     ((.vulnerability.fix.versions // []) | map(select(type == "string" and . != "")) | join(",") | if . == "" then "-" else . end),
     .artifact.type, .vulnerability.id, .vulnerability.severity]) |
  @tsv' <<< "$SCAN_JSON" 2>/dev/null || true

# ── Phase 3: Fix ──────────────────────────────────────────────────────────────
# Parse CVE matches into groups (pkg + highest fix version + CVE IDs), then
# dispatch each group: no-fix → ignore.sh, stdlib → fix-stdlib.sh, else →
# fix-package.sh (with a legacy lower-version retry for old callers).

banner "Fixing CVEs"

# Extract unique package+fixVersion+cveIDs groups from JSON
# Uses pipe delimiter (not tab) because bash `read` with IFS=$'\t'
# collapses consecutive tabs, losing empty fields like fixedIn and
# allFixVersions — which shifts fixState into the severity position.
# Binary paths do not identify the module to edit. Use freshly built binaries'
# main-module metadata for dispatch, without rewriting the original scan used
# by the independent verification and final gates. Unproven binaries retain
# their original paths and therefore cannot invent a source-module scope.
if ! DISPATCH_JSON=$(python3 "$SCRIPT_DIR/binary-module-locations.py" "$REPO" \
    "${STATE_FILE}.built-artifacts" <<< "$SCAN_JSON") ||
    ! printf '%s\n' "$DISPATCH_JSON" | grype_scan_json_valid; then
  echo "WARNING: binary-to-module mapping failed; dispatching with raw scan locations." >&2
  DISPATCH_JSON="$SCAN_JSON"
fi
CVE_LINES=$(jq -r '
  def validfix: type == "string" and . != "" and ((contains("-") | not) or test("[-.][0-9]{14}-[0-9a-f]+([+]incompatible)?$"));
  def cleanfix: ltrimstr("v") | split("+")[0];
  [.matches[] |
    select(.artifact.type == "go-module") |
    {
      pkg: (.artifact.name // ""),
      fixedIn: ((.vulnerability.fix.versions // []) | map(select(validfix)) | if length == 0 then "" else sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last | cleanfix end),
      allFixVersions: ((.vulnerability.fix.versions // []) | map(select(validfix)) | join(",")),
      cve: (.vulnerability.id // ""),
      severity: (.vulnerability.severity // "Unknown"),
      locs: ([.artifact.locations[]?.path // empty] |
        map(sub("^/src/"; "/")) | map(select(. != "")) | unique),
      type: (if ((.vulnerability.fix.versions // []) | map(select(validfix)) | length) == 0 then "no-fix"
             elif (.artifact.name // "") == "stdlib" then "stdlib"
             else "package" end),
      # Grype exposes some GovulnDB records with an empty raw state but applies
      # ignore filtering to them as "unknown". Preserve that effective state so
      # the generated exact rule actually matches and still expires on change.
      fixState: (if (.vulnerability.fix.state // "") == "" then "unknown"
                 else .vulnerability.fix.state end)
    }
  ] |
  # No-fix findings retain their exact scan location so each module gets an
  # independent ignore. Fixable packages still group across modules because
  # dependency updates are handled as one package operation.
  map(. + {scanLocation: (if (.locs | length) == 1 and (.locs[0] | endswith("/go.mod")) then .locs[0] else "" end)}) |
  # Dedup: when same (pkg, cve) has both fix and no-fix entries at one scope,
  # keep fix. A no-fix finding at multiple go.mod locations remains separate,
  # so each resulting ignore is exact; binary or empty locations stay broad.
  group_by(.pkg + ":" + .cve + ":" + (if .type == "no-fix" then .scanLocation else "" end)) |
  map(
    ([.[].locs[]] | map(select(type == "string" and . != "")) | unique) as $locs |
    (if ($locs | length) == 1 and ($locs[0] | endswith("/go.mod")) then $locs[0] else "" end) as $location |
    # Duplicate advisory records can supply different patched release streams.
    # Preserve every fix threshold instead of retaining an arbitrary record.
    ([.[] | select(.type != "no-fix") | .allFixVersions | split(",")[]] | unique |
      sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0))) as $versions |
    (sort_by(if .type == "no-fix" then 1 else 0 end) | .[0]) |
    . + {location: $location} |
    if .type == "no-fix" then . else . + {
      allFixVersions: ($versions | join(",")),
      fixedIn: ($versions | last | cleanfix)
    } end
  ) |
  group_by(.pkg + ":" + .type + ":" + (if .type == "no-fix" then .fixState else "" end) + ":" + .location) |
  map({
    pkg: .[0].pkg,
    type: .[0].type,
    fixedIn: (if .[0].type == "no-fix" then ""
              else (map(.fixedIn) | map(select(type == "string" and . != "")) | sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | (last // "") | cleanfix) end),
    allFixVersions: (if .[0].type == "no-fix" then "" else ([.[].allFixVersions] | unique | join(",")) end),
    cves: (map(.cve) | unique),
    severity: .[0].severity,
    fixState: .[0].fixState,
    location: .[0].location,
    requirements: (map({cve: .cve, versions: (.allFixVersions | split(",") | map(select(. != "")))}) |
      unique_by(.cve) | tojson | @base64)
  }) |
  .[] |
  "\(.type)|\(.pkg)|\(.fixedIn)|\(.cves | join(","))|\(.severity)|\(.allFixVersions)|\(.fixState)|\(.location)|\(.requirements)"
' <<< "$DISPATCH_JSON" 2>/dev/null || echo "")

# Track results
FIX_LINES=()
NEEDS_REVIEW_KEYS=()
FIX_FAILED_KEYS=()
TRANSIENT_REVIEW_KEYS=()
FIXED_COUNT=0
# Non-CVE exit drivers, independent of the final CVE rescan gate below.
TESTS_FAILED=false
VERIFY_FAILED=false
# Packages that need team review but aren't visible to the final grype gate
# (fix-state entries moved to policy review by the subagent loop).
UNSEEN_NEEDS_REVIEW=false
POLICY_CHECK_FAILED=false

# If the initial build failed, dependency CVEs are still worth fixing, but stdlib
# coverage is unknown — flag for review so the run can't exit 0 as fully clean.
if $BUILD_FAILED; then
  FIX_LINES+=("NEEDS_REVIEW: initial build failed — stdlib CVE coverage unknown")
  # Preserve the coverage blocker independently of counted dependency findings.
  UNSEEN_NEEDS_REVIEW=true
fi

if [[ "$MATCH_COUNT" -gt 0 && -z "$CVE_LINES" ]]; then
  echo "WARNING: Could not parse CVE data from JSON. All matches may lack fix versions."
  FIX_LINES+=("NEEDS_REVIEW: CVE data could not be parsed from scan JSON")
fi

# Mutators take arguments. Interactive builds must not consume remaining CVE rows.
while IFS='|' read -r TYPE PKG FIX_VER CVE_CSV _SEVERITY ALL_FIX_VERS FIX_STATE_VAL LOCATION REQUIREMENTS_B64; do
  [[ -z "$PKG" ]] && continue
  if ! checkout_matches "$OWNED_HEAD" "$INITIAL_REF"; then
    echo "NEEDS_REVIEW: checkout no longer matches the owned state; remaining fixes stopped." >&2
    exit 2
  fi

  # Split CVE_CSV into array
  IFS=',' read -ra CVES <<< "$CVE_CSV"

  FIX_LOG=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX")
  if [[ "$TYPE" == "no-fix" ]]; then
    _FIX_STATUS=(0 0)
    # Scope the ignore to the reporting module when the scan pinned one (set-u
    # safe empty-array expansion so an unscoped CVE passes no --location).
    _loc_flag=()
    [[ -n "${LOCATION:-}" ]] && _loc_flag=(--location "$LOCATION")
    "$SCRIPT_DIR/ignore.sh" "$STATE_FILE" "$PKG" "${_SEVERITY:-High}" \
      "No fix available for $PKG." --fix-state "${FIX_STATE_VAL:-not-fixed}" ${_loc_flag[@]+"${_loc_flag[@]}"} "${CVES[@]}" </dev/null 2>&1 | tee "$FIX_LOG" || _FIX_STATUS=("${PIPESTATUS[@]}")
    IGNORE_EXIT=${_FIX_STATUS[0]}
    if [[ ${_FIX_STATUS[1]} -ne 0 ]]; then
      printf 'ERROR: Cannot capture ignore output (command exited %s; tee exited %s); verification stopped.\n' \
        "$IGNORE_EXIT" "${_FIX_STATUS[1]}" >&2
      exit 2
    fi
    if [[ "$IGNORE_EXIT" -eq 0 ]]; then
      _record_owned_head || exit 2
      # Remove any prior NEEDS_REVIEW or ERROR line for this package
      _remove_needs_review "$PKG" "$(normalize_scan_location "${LOCATION:-}")"
      _remove_error_line "$PKG" "$(normalize_scan_location "${LOCATION:-}")"
      FIX_LINES+=("IGNORED: $PKG (no fix available) for ${CVES[*]}")
    else
      REASON=$(grep "^NEEDS_REVIEW:" "$FIX_LOG" || echo "NEEDS_REVIEW: $PKG — ignore.sh failed with exit $IGNORE_EXIT")
      FIX_LINES+=("$REASON")
      POLICY_CHECK_FAILED=true
      UNSEEN_NEEDS_REVIEW=true
    fi
  elif [[ "$TYPE" == "stdlib" ]]; then
    _FIX_STATUS=(0 0)
    CVE_FIX_REQUIREMENTS_B64="$REQUIREMENTS_B64" \
      "$SCRIPT_DIR/fix-stdlib.sh" "$STATE_FILE" "$FIX_VER" "$ALL_FIX_VERS" "${CVES[@]}" </dev/null 2>&1 | tee "$FIX_LOG" || _FIX_STATUS=("${PIPESTATUS[@]}")
    STDLIB_EXIT=${_FIX_STATUS[0]}
    if [[ ${_FIX_STATUS[1]} -ne 0 ]]; then
      printf 'ERROR: Cannot capture stdlib fix output (command exited %s; tee exited %s); verification stopped.\n' \
        "$STDLIB_EXIT" "${_FIX_STATUS[1]}" >&2
      exit 2
    fi
    if [[ "$STDLIB_EXIT" -eq 2 ]]; then
      _stdlib_head=$(sed -n 's/^RETAINED_HEAD: //p' "$FIX_LOG" | tail -1)
      if [[ "$_stdlib_head" =~ ^[0-9a-f]{40,64}$ ]] &&
         checkout_matches "$_stdlib_head" "$INITIAL_REF"; then
        _record_owned_head || exit 2
      fi
    fi
    if [[ "$STDLIB_EXIT" -eq 0 ]]; then
      _record_owned_head || exit 2
      _stdlib_used=$(grep '^FIXED: stdlib go ' "$FIX_LOG" | head -1 | awk '{print $4}' || true)
      [[ -z "$_stdlib_used" ]] && _stdlib_used="$FIX_VER"
      FIX_LINES+=("FIXED: stdlib go $_stdlib_used for ${CVES[*]}")
      FIXED_COUNT=$((FIXED_COUNT + 1))
    else
      REASON=$(grep "^NEEDS_REVIEW:" "$FIX_LOG" || echo "NEEDS_REVIEW: stdlib — fix-stdlib.sh exited $STDLIB_EXIT")
      FIX_LINES+=("$REASON")
      NEEDS_REVIEW_KEYS+=("stdlib")
    fi
  else
    _FIX_STATUS=(0 0)
    _outcome_scope=""
    [[ -z "${LOCATION:-}" ]] || _outcome_scope=" at $(normalize_scan_location "$LOCATION")"
    _loc_flag=()
    [[ -n "${LOCATION:-}" ]] && _loc_flag=(--location "$LOCATION")
    CVE_FIX_ALL_VERSIONS="$ALL_FIX_VERS" CVE_FIX_REQUIREMENTS_B64="$REQUIREMENTS_B64" \
    "$SCRIPT_DIR/fix-package.sh" "$STATE_FILE" "$PKG" "$FIX_VER" ${_loc_flag[@]+"${_loc_flag[@]}"} "${CVES[@]}" </dev/null 2>&1 | tee "$FIX_LOG" || _FIX_STATUS=("${PIPESTATUS[@]}")
    EXIT_CODE=${_FIX_STATUS[0]}
    if [[ ${_FIX_STATUS[1]} -ne 0 ]]; then
      printf 'ERROR: Cannot capture package fix output (command exited %s; tee exited %s); verification stopped.\n' \
        "$EXIT_CODE" "${_FIX_STATUS[1]}" >&2
      exit 2
    fi
    # A rejected update can reveal an advisory's threshold in the new release
    # stream (installed versions match only one affected range). Retry once.
    if [[ $EXIT_CODE -eq 2 && -n "${REQUIREMENTS_B64:-}" ]] &&
       _RETRY_REQUIREMENTS=$(sed -n 's/^RETRY_FIX: //p' "$FIX_LOG" | merge_fix_requirements "$REQUIREMENTS_B64"); then
      echo "Retrying $PKG with fix thresholds reported for the updated version..."
      REQUIREMENTS_B64="$_RETRY_REQUIREMENTS"
      _FIX_STATUS=(0 0)
      CVE_FIX_ALL_VERSIONS="$ALL_FIX_VERS" CVE_FIX_REQUIREMENTS_B64="$REQUIREMENTS_B64" \
      "$SCRIPT_DIR/fix-package.sh" "$STATE_FILE" "$PKG" "$FIX_VER" ${_loc_flag[@]+"${_loc_flag[@]}"} "${CVES[@]}" </dev/null 2>&1 | tee "$FIX_LOG" || _FIX_STATUS=("${PIPESTATUS[@]}")
      EXIT_CODE=${_FIX_STATUS[0]}
      if [[ ${_FIX_STATUS[1]} -ne 0 ]]; then
        printf 'ERROR: Cannot capture package retry output (command exited %s; tee exited %s); verification stopped.\n' \
          "$EXIT_CODE" "${_FIX_STATUS[1]}" >&2
        exit 2
      fi
    fi
    # Read the version actually applied from fix-package.sh output. When in-stream
    # selection picks a lower version (e.g. 3.6.14 instead of 3.7.1), the FIXED
    # line reflects that choice — not the FIX_VER we passed in.
    USED_VER=$(grep "^FIXED: $PKG v" "$FIX_LOG" 2>/dev/null | head -1 | sed "s|^FIXED: $PKG v||" | awk '{print $1}') || true
    [[ -z "$USED_VER" ]] && USED_VER="$FIX_VER"
    [[ -n "$USED_VER" ]] && FIX_VER="$USED_VER"
    case $EXIT_CODE in
      0)
        _record_owned_head || exit 2
        FIX_LINES+=("FIXED: $PKG v$USED_VER for ${CVES[*]}$_outcome_scope")
        FIXED_COUNT=$((FIXED_COUNT + 1))
        # A committed fix can carry a caveat (a failed indirect re-pin). Report it
        # as an advisory; independent verification and policy gates own blocking.
        if grep -q '^NEEDS_REVIEW:' "$FIX_LOG"; then
          FIX_LINES+=("$(grep -m1 '^NEEDS_REVIEW:' "$FIX_LOG")$_outcome_scope")
        fi
        ;;
      2|3)
        if [[ $EXIT_CODE -eq 3 ]] && is_scan_transient "$FIX_LOG" 2>/dev/null; then
          FIX_LINES+=("NEEDS_REVIEW: $PKG — network/DNS error blocked go get (check VPN/proxy)$_outcome_scope")
          TRANSIENT_REVIEW_KEYS+=("$PKG${LOCATION:+|$(normalize_scan_location "$LOCATION")}")
        else
          REASON=$(grep "^NEEDS_REVIEW:" "$FIX_LOG" || echo "NEEDS_REVIEW: $PKG — exit code $EXIT_CODE")
          FIX_LINES+=("$REASON$_outcome_scope")
          _review_key="$PKG"
          [[ -n "${LOCATION:-}" ]] && _review_key+="|$(normalize_scan_location "$LOCATION")"
          if [[ $EXIT_CODE -eq 2 ]]; then
            NEEDS_REVIEW_KEYS+=("$_review_key")
          else
            FIX_FAILED_KEYS+=("$_review_key")
          fi
        fi
        ;;
      5)
        # Transient network/timeout error from go get — the package was not
        # updated; the CVE still exists. A retry may succeed once the network
        # recovers. Keep its readiness blocker only if verification leaves
        # this package/scope unresolved; unrelated blockers remain independent.
        FIX_LINES+=("NEEDS_REVIEW: $PKG — transient network error during go get. Re-run the skill.$_outcome_scope")
        TRANSIENT_REVIEW_KEYS+=("$PKG${LOCATION:+|$(normalize_scan_location "$LOCATION")}")
        ;;
      4)
        # A failed module query proves only that this candidate is unavailable
        # at this path. Product tags may differ from Go module versions, and a
        # grouped advisory may have other published fixes. Do not infer no-fix
        # status or manufacture an ignore from this lookup failure.
        if grep -q "^INCOMPATIBLE_MAJOR_BUMP:" "$FIX_LOG" 2>/dev/null; then
          FIX_LINES+=("NEEDS_REVIEW: $PKG — fix v$FIX_VER requires an incompatible major-version migration$_outcome_scope")
        else
          FIX_LINES+=("NEEDS_REVIEW: $PKG — selected fix v$FIX_VER is unavailable at the current module path; verify advisory version mapping or alternative fixes$_outcome_scope")
        fi
        _review_key="$PKG"
        [[ -n "${LOCATION:-}" ]] && _review_key+="|$(normalize_scan_location "$LOCATION")"
        NEEDS_REVIEW_KEYS+=("$_review_key")
        UNSEEN_NEEDS_REVIEW=true
        ;;
      *)
        if is_scan_transient "$FIX_LOG"; then
          FIX_LINES+=("NEEDS_REVIEW: $PKG — network/DNS error blocked go get (check VPN/proxy)$_outcome_scope")
          TRANSIENT_REVIEW_KEYS+=("$PKG${LOCATION:+|$(normalize_scan_location "$LOCATION")}")
        else
          FIX_LINES+=("ERROR: $PKG — fix-package.sh failed with exit code $EXIT_CODE$_outcome_scope")
          FIX_FAILED_KEYS+=("$PKG${LOCATION:+|$(normalize_scan_location "$LOCATION")}")
        fi
        ;;
    esac
  fi
  rm -f "$FIX_LOG"
done <<< "$CVE_LINES"

# ── Phase 4: Verify ───────────────────────────────────────────────────────────

echo ""

# Keep test-created workspaces out of retries and retained-tree verification.
_run_test_attempt() {
  # Clear prior output before an interrupted retry can acquire its own receipt.
  : > "$TEST_LOG"
  _EVIDENCE_TEST_STATUS=running _EVIDENCE_TEST_RECORDED=false
  if ! _tracked_tree_unchanged "$TESTED_HEAD" --restore-generated-noise; then
    echo "ERROR: Cannot verify clean tracked files and retained HEAD before tests; verification stopped." >&2
    _EVIDENCE_TEST_STATUS=not_reached
    exit 2
  fi
  local workspace attempt_unverified=false
  local -a generated_workspaces=()
  for workspace in go.work go.work.sum; do
    if [[ ! -e "$workspace" && ! -L "$workspace" ]] &&
       ! git ls-files --error-unmatch -- "$workspace" &>/dev/null; then
      generated_workspaces+=("$workspace")
    fi
  done
  TEST_RC=0
  local -a test_status=(0 0)
  bounded_command "${CVE_FIX_TEST_TIMEOUT:-1800}" "${TEST_ENV[@]}" bash -c "$TEST_CMD" 2>&1 | tee "$TEST_LOG" || test_status=("${PIPESTATUS[@]}")
  # The command has exited even if logging or a later diagnostic fails. Keep
  # its observed status separate from tee's, including for the EXIT receipt.
  TEST_RC=${test_status[0]}
  _TEST_ATTEMPT_RESULTS+=("$_EVIDENCE_TEST_RUN-$_EVIDENCE_TEST_ATTEMPT@$TESTED_HEAD=$TEST_RC")
  _EVIDENCE_TEST_STATUS=completed _EVIDENCE_TEST_RC=$TEST_RC
  for workspace in "${generated_workspaces[@]+"${generated_workspaces[@]}"}"; do
    git ls-files --error-unmatch -- "$workspace" &>/dev/null && continue
    if ! rm -f -- "$workspace"; then
      echo "ERROR: Cannot remove test-generated $workspace; verification stopped." >&2
      attempt_unverified=true
    fi
  done
  if ! _tracked_tree_unchanged "$TESTED_HEAD" --restore-generated-noise; then
    echo "ERROR: Cannot verify unchanged HEAD and tracked files after tests; verification stopped." >&2
    attempt_unverified=true
  fi
  if [[ ${test_status[1]} -ne 0 ]]; then
    echo "ERROR: Cannot capture test output (tee exited ${test_status[1]}); verification stopped." >&2
    attempt_unverified=true
  fi
  if $attempt_unverified; then
    _record_test_evidence "$TEST_RC"
    exit 2
  fi
  _record_test_evidence "$TEST_RC"
}

# Test the retained HEAD after deterministic verification has finished repairs.
run_tests() {
  TESTED_HEAD=$(git rev-parse HEAD)
  if [[ -z "${TEST_CMD:-}" ]]; then _EVIDENCE_TEST_STATUS=not_configured; return 0; fi
  _EVIDENCE_TEST_STATUS=running
  _EVIDENCE_TEST_RUN=$((_EVIDENCE_TEST_RUN + 1))
  _EVIDENCE_TEST_ATTEMPT=1
  echo ""
  echo "Running tests..."
  build_env_scrub
  TEST_LOG=$(mktemp "${TMPDIR:-/tmp}/cve-fix-test.XXXXXX")
  TEST_ENV=(env)
  [[ ${#ENV_SCRUB[@]} -gt 0 ]] && TEST_ENV=("${ENV_SCRUB[@]}")
  [[ -z "${BUILD_REPO_NAME:-}" ]] || TEST_ENV+=("REPO=$BUILD_REPO_NAME")
  # The outer skill Make invocation can propagate REPO=/absolute/path through
  # MAKEFLAGS as a command-line variable; reset it before nested Make/Dapper
  # tests so the sanitized image namespace is authoritative.
  TEST_ENV+=(MAKEFLAGS=-B)
  _run_test_attempt
  local disk_full=false
  grep -qiE 'no space left on device|disk quota exceeded' "$TEST_LOG" && disk_full=true
  # Retry once except for timeouts or disk exhaustion.
  if [[ $TEST_RC -ne 0 && $TEST_RC -ne 124 && $TEST_RC -ne 137 ]] && ! $disk_full; then
    local first_rc=$TEST_RC
    echo "Tests failed; rerunning once..."
    _EVIDENCE_TEST_ATTEMPT=2
    _run_test_attempt
    grep -qiE 'no space left on device|disk quota exceeded' "$TEST_LOG" && disk_full=true
    [[ $TEST_RC -ne 0 ]] || printf 'Tests passed on retry (first attempt exit %s; retry exit %s).\n' "$first_rc" "$TEST_RC"
  fi
  if [[ $TEST_RC -ne 0 ]]; then
    if $disk_full; then
      FIX_LINES+=("NEEDS_REVIEW: tests could not run — disk full (free space or point TMPDIR elsewhere)")
    elif is_scan_transient "$TEST_LOG"; then
      FIX_LINES+=("NEEDS_REVIEW: tests failed — Docker networking error OR API incompatibility (human investigation required)")
    else
      FIX_LINES+=("NEEDS_REVIEW: tests failed after applying fixes")
    fi
    TESTS_FAILED=true
  fi
  _EVIDENCE_TEST_STATUS=completed
  _EVIDENCE_TEST_RC=$TEST_RC
  rm -f "$TEST_LOG"
}
# Prepare for subagent verification: mark packages that failed in the initial loop
# so the subagents don't retry them. This prevents corrupted version data from being
# passed to fix-package.sh when a package has no valid fix due to MVS constraints.
banner "Subagent Verification"
if ! checkout_matches "$OWNED_HEAD" "$INITIAL_REF"; then
  echo "NEEDS_REVIEW: checkout no longer matches the owned state; verification stopped." >&2
  exit 2
fi
SUBAGENT_DIR="$SCRIPT_DIR/../subagents"

SUBAGENT_REPORT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/cve-fix-subagents-$(basename "$REPO")-${BRANCH//\//-}.XXXXXX")
echo "$SCAN_JSON" > "$SUBAGENT_REPORT_DIR/initial-scan.json"

# Persist exact package/location identities from deterministic fix attempts.
# Scoped failures must not exempt another module containing the same package;
# explicitly unscoped operations intentionally cover every reported location.
if [[ ${#NEEDS_REVIEW_KEYS[@]} -gt 0 ]]; then
  printf '%s\n' "${NEEDS_REVIEW_KEYS[@]}" | sort -u > "$SUBAGENT_REPORT_DIR/needs-review-pkgs"
fi
if [[ ${#FIX_FAILED_KEYS[@]} -gt 0 ]]; then
  printf '%s\n' "${FIX_FAILED_KEYS[@]}" | sort -u > "$SUBAGENT_REPORT_DIR/fix-failed-pkgs"
fi

# Missing audit sources fail through the same verification path as incomplete evidence.
_EVIDENCE_VERIFY_STATUS=running
if ! verify_fix_loop "$STATE_FILE" "$SUBAGENT_DIR" "$SUBAGENT_REPORT_DIR" 3; then
  _EVIDENCE_VERIFY_RC=1
  VERIFY_FAILED=true
  # Preserve audit evidence and state for inspection or rerunning after exit.
  PRESERVE_REPORTS=1
  cp "$STATE_FILE" "$SUBAGENT_REPORT_DIR/state.env" 2>/dev/null || true
  echo "Reports preserved for debugging: $SUBAGENT_REPORT_DIR"
  FIX_LINES+=("NEEDS_REVIEW: subagent verification failed — reports at $SUBAGENT_REPORT_DIR")
else
  _EVIDENCE_VERIFY_RC=0
  _record_owned_head || exit 2
fi
_EVIDENCE_VERIFY_STATUS=completed
if ! checkout_matches "$OWNED_HEAD" "$INITIAL_REF"; then
  echo "NEEDS_REVIEW: verification changed checkout ownership; tests stopped." >&2
  exit 2
fi

# Surface packages classified by fix functions during verify loop that are NOT
# visible via the main fix loop (e.g. fix-state: not-fixed entries in .grype.yaml
# that fix-availability.sh found a version for, but fix-package.sh could not
# verify or accept). These don't appear in the scan, so the final
# gate won't flag them — append them to FIX_LINES explicitly.
if [[ -f "$SUBAGENT_REPORT_DIR/needs-review-pkgs" ]]; then
  while IFS= read -r _sentinel; do
    [[ -z "$_sentinel" ]] && continue
    _pkg="${_sentinel%%|*}"
    _scope=""
    _scope_loc=""
    [[ "$_sentinel" == *'|'* ]] && { _scope_loc="${_sentinel#*|}"; _scope=" at $_scope_loc"; }
    # Skip if main loop already added this package (scan-visible packages get a
    # NEEDS_REVIEW line from fix-package.sh exit 2 during the deterministic phase)
    if ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists NEEDS_REVIEW "$_pkg" "$_scope_loc"; then
      _reason=$(awk -F '\t' -v key="$_sentinel" '
        $1 == key && NF > 1 { reason=substr($0, index($0, "\t") + 1) }
        END { print reason }
      ' "$SUBAGENT_REPORT_DIR/needs-review-reasons" 2>/dev/null || true)
      [[ -n "$_reason" ]] || _reason="deterministic fix requires review; inspect fix output"
      FIX_LINES+=("NEEDS_REVIEW: $_pkg — $_reason$_scope")
    fi
    UNSEEN_NEEDS_REVIEW=true
  done < "$SUBAGENT_REPORT_DIR/needs-review-pkgs"
fi
# Fold successful verification repairs before classifying stale failure/timeout
# markers. Explicit needs-review markers above remain policy boundaries.
fold_fixed_package_outcomes "$SUBAGENT_REPORT_DIR"
if [[ -f "$SUBAGENT_REPORT_DIR/fix-failed-pkgs" ]]; then
  while IFS= read -r _sentinel; do
    [[ -z "$_sentinel" ]] && continue
    _pkg="${_sentinel%%|*}"
    _scope=""
    _scope_loc=""
    [[ "$_sentinel" == *'|'* ]] && { _scope_loc="${_sentinel#*|}"; _scope=" at $_scope_loc"; }
    # A later verified repair supersedes a failed attempt only in its scope;
    # an unscoped success covers the package across all modules.
    if printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists FIXED "$_pkg" "$_scope_loc" ||
       printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists FIXED "$_pkg" ''; then
      continue
    fi
    if ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists NEEDS_REVIEW "$_pkg" "$_scope_loc"; then
      FIX_LINES+=("NEEDS_REVIEW: $_pkg — fix attempt remains unverified (inspect retained diagnostics)$_scope")
    fi
    UNSEEN_NEEDS_REVIEW=true
  done < "$SUBAGENT_REPORT_DIR/fix-failed-pkgs"
fi
if [[ -f "$SUBAGENT_REPORT_DIR/timeout-pkgs" ]]; then
  while IFS= read -r _pkg; do
    [[ -z "$_pkg" ]] && continue
    # Only surface as TIMEOUT if the package was not ultimately fixed or
    # classified by a later verify iteration.
    if ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -qF "FIXED: $_pkg " 2>/dev/null && \
       ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -qF "NEEDS_REVIEW: $_pkg —" 2>/dev/null; then
      FIX_LINES+=("TIMEOUT: $_pkg — go get timed out (transient network error; retry recommended)")
      UNSEEN_NEEDS_REVIEW=true
    fi
  done < "$SUBAGENT_REPORT_DIR/timeout-pkgs"
fi
# Main-loop transient attempts may now be repaired. Only their surviving exact
# outcomes add a blocker; never reset an earlier build, policy or other gate.
for _review_key in "${TRANSIENT_REVIEW_KEYS[@]+"${TRANSIENT_REVIEW_KEYS[@]}"}"; do
  _pkg="${_review_key%%|*}"
  _scope_loc=""
  [[ "$_review_key" != *'|'* ]] || _scope_loc="${_review_key#*|}"
  if printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists NEEDS_REVIEW "$_pkg" "$_scope_loc"; then
    UNSEEN_NEEDS_REVIEW=true
  fi
done
# Verification can commit dependency or policy repairs. Test that retained tree
# once, with the existing bounded retry, even when verification remains blocked.
run_tests
VERIFIED_HEAD=$TESTED_HEAD
# Remove test/build outputs before final scanning without redefining the tested
# source. Failed cleanup cannot certify that the retained artifacts are current.
_cleanup_rc=0
if [[ -n "${CLEAN_CMD:-}" ]]; then
  bounded_command "${CVE_FIX_BUILD_TIMEOUT:-1800}" bash -c "$CLEAN_CMD" 2>&1 || _cleanup_rc=$?
fi
if [[ $_cleanup_rc -ne 0 ]]; then
  echo "NEEDS_REVIEW: Build artifact cleanup failed (exit $_cleanup_rc) before final checks." >&2
  POLICY_CHECK_FAILED=true
  UNSEEN_NEEDS_REVIEW=true
fi
if ! _tracked_tree_unchanged "$VERIFIED_HEAD" --restore-generated-noise; then
  echo "NEEDS_REVIEW: Retained HEAD and clean tracked files could not be confirmed before final checks." >&2
  POLICY_CHECK_FAILED=true
  UNSEEN_NEEDS_REVIEW=true
fi

# Surface eligible ignores without clearing another policy decision.
if [[ -f "$SUBAGENT_REPORT_DIR/ignored-pkgs" ]]; then
  while IFS= read -r _entry; do
    [[ -z "$_entry" ]] && continue
    _pkg="${_entry%% *}"
    if package_ignore_can_clear_review "$_pkg" "$SUBAGENT_REPORT_DIR/needs-review-pkgs" \
        "$SUBAGENT_REPORT_DIR/fix-failed-pkgs"; then
      _remove_needs_review "$_pkg"
      _remove_error_line "$_pkg"
    fi
    if ! printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -qF "IGNORED: $_pkg " 2>/dev/null; then
      FIX_LINES+=("IGNORED: $_entry")
    fi
  done < "$SUBAGENT_REPORT_DIR/ignored-pkgs"
fi

# ── Phase 5: Gate ─────────────────────────────────────────────────────────────
# Authoritative post-fix check after verification and tests: rescan with
# .grype.yaml applied (so ignores are honored) and the same go-module filter as
# the initial scan. Builds (no --skip-build) so stdlib CVEs in rebuilt binaries
# surface too. Any actionable CVE still present — or a rescan we can't trust (a
# build/scanner failure) — forces a non-zero exit so the run never reports clean
# while CVEs stand. This is the gate the exit code keys off of, not the counters.
banner "Final Rescan Gate"
GATE_RC=0
_EVIDENCE_FINAL_STATUS=running
GATE_JSON=$(CVE_FIX_EVIDENCE_PHASE=final-gate BUILD_UPX=false "$SCRIPT_DIR/scan.sh" "$STATE_FILE" --no-update --json) || GATE_RC=$?
_EVIDENCE_FINAL_STATUS=completed
FINAL_SCAN_SCOPE=$(cat "${STATE_FILE}.scan-scope" 2>/dev/null) || FINAL_SCAN_SCOPE="not established"
printf 'Scan scope (final): %s\n' "$FINAL_SCAN_SCOPE"
if $_EVIDENCE_READY; then
  printf '%s\n' "$GATE_JSON" > "$CVE_FIX_EVIDENCE_DIR/final-gate.json"
  CVE_FIX_EVIDENCE_PHASE=final-gate record_scan_status "$CVE_FIX_EVIDENCE_DIR/final-gate-status.json" "$GATE_RC"
fi
# The gate rebuild can re-create .network-broken on a transient failure; the gate
# keys off .build-failed (below) instead, so drop that orphan sentinel now (the
# EXIT trap also cleans it) rather than let it linger into any later check.
rm -f "${STATE_FILE}.network-broken"
# If grype's vulnerability DB was degraded during the gate scan, the result is
# untrustworthy even if it returned JSON — treat it as a gate failure.
_read_sentinel scanner-degraded  GATE_SCANNER_DEGRADED
# The gate rebuild (no --skip-build) re-evaluates binary coverage: if it produced
# packed/opaque binaries, grype couldn't read their stdlib, so a zero-CVE result
# is blind, not clean. Capture and clear it now (the EXIT trap also cleans it).
_read_sentinel coverage-unknown  GATE_COVERAGE_UNKNOWN
GATE_FAILED=false
GATE_REMAINING=0
# Coverage is orthogonal to dependency findings. Packed binaries make stdlib
# coverage untrustworthy even when the scan also reports ordinary Go modules.
if $GATE_COVERAGE_UNKNOWN; then
  GATE_FAILED=true
  echo "WARNING: final rescan could not confirm binary stdlib coverage."
  FIX_LINES+=("NEEDS_REVIEW: packed/opaque binaries or compiler metadata block stdlib scanning — CVE status unconfirmed")
fi
if $GATE_SCANNER_DEGRADED; then
  GATE_FAILED=true
  echo "WARNING: final rescan used a degraded vulnerability DB — CVE status can't be confirmed."
  FIX_LINES+=("NEEDS_REVIEW: final rescan scanner DB degraded — verify CVE status manually")
elif [[ -f "${STATE_FILE}.build-failed" ]]; then
  rm -f "${STATE_FILE}.build-failed"
  GATE_FAILED=true
  echo "WARNING: final rescan build failed — CVE status can't be confirmed."
  FIX_LINES+=("NEEDS_REVIEW: final rescan build failed — CVE status unconfirmed")
elif [[ $GATE_RC -ne 0 ]] || ! grype_scan_json_valid <<< "$GATE_JSON"; then
  GATE_FAILED=true
  echo "WARNING: final rescan failed or produced invalid Grype evidence."
  FIX_LINES+=("NEEDS_REVIEW: final rescan failed — verify CVE status manually")
elif ! GATE_REMAINING=$(jq 'def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
  [.matches[] | select(.artifact.type == "go-module") as $m |
   (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
   "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc)"] | unique | length' <<< "$GATE_JSON" 2>/dev/null) || [[ -z "$GATE_REMAINING" ]]; then
  GATE_FAILED=true
  GATE_REMAINING=0
  echo "WARNING: final rescan failed or produced invalid output."
  FIX_LINES+=("NEEDS_REVIEW: final rescan failed — verify CVE status manually")
elif ! _GATE_TYPES=$(jq -r "$_GO_SCHEMA_TYPES" <<< "$GATE_JSON"); then
  GATE_FAILED=true
  echo "WARNING: final rescan has invalid Go package identity evidence."
  FIX_LINES+=("NEEDS_REVIEW: final rescan has invalid Go package identity evidence")
elif [[ -n "$_GATE_TYPES" ]]; then
  GATE_FAILED=true
  echo "WARNING: gate scan schema mismatch — Go package identity has unsupported artifact type(s): $_GATE_TYPES."
  FIX_LINES+=("NEEDS_REVIEW: gate scan schema mismatch — grype 'go-module' type may have been renamed")
elif [[ "$GATE_REMAINING" -gt 0 ]]; then
  echo "WARNING: $GATE_REMAINING actionable finding(s) still present after all fixes:"
  jq -r 'def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
    [.matches[] | select(.artifact.type == "go-module") as $m |
     (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
     {k: "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc)",
      v: "\($m.vulnerability.id // "") \($m.artifact.name // "") \($m.artifact.version // "") \(.path | normloc)"}] |
    unique_by(.k) | .[].v' <<< "$GATE_JSON" 2>/dev/null | sed 's/^/  /' || true
  # `.matches` is authoritative: a finding present here was not ignored by
  # Grype. Do not subtract it merely because a loosely matching YAML block
  # exists; that block may be expired, scoped to another module, or malformed.
  FIX_LINES+=("NEEDS_REVIEW: $GATE_REMAINING finding(s) still present after fixes")


else
  $GATE_FAILED || echo "Clean: no actionable CVEs remain."
fi

# Scanner cleanliness is not enough: reject a broad ignore shadowing a scoped
# rule for the same CVE/package. This is a YAML policy failure, so no PR command
# is emitted until the conflict is migrated or explicitly resolved.
if [[ -f "$REPO/.grype.yaml" ]]; then
  _SCOPE_CONFLICTS=$(grype_ignore_scope_conflicts "$REPO/.grype.yaml" || true)
  if [[ -n "$_SCOPE_CONFLICTS" ]]; then
    POLICY_CHECK_FAILED=true
    UNSEEN_NEEDS_REVIEW=true
    while IFS= read -r _scope_issue; do
      [[ -n "$_scope_issue" ]] && FIX_LINES+=("NEEDS_REVIEW: $_scope_issue")
    done <<< "$_SCOPE_CONFLICTS"
    echo "WARNING: ignore policy has unscoped/scoped conflicts; PR generation suppressed."
  fi
fi

# Run an existing repository license policy gate, when one is declared. A
# policy failure is actionable but must never be “fixed” by inventing an
# allowlist entry; suppress PR generation until maintainers resolve it.
_EVIDENCE_LICENSE_STATUS=not_configured
if has_real_make_target licensecheck; then
  echo ""
  LICENSE_CHECK_TIMEOUT="${CVE_FIX_LICENSE_TIMEOUT:-300}"
  echo "Running repository license policy check (make licensecheck, timeout ${LICENSE_CHECK_TIMEOUT}s)..."
  build_env_scrub
  LICENSE_ENV=(env)
  [[ ${#ENV_SCRUB[@]} -gt 0 ]] && LICENSE_ENV=("${ENV_SCRUB[@]}")
  [[ -z "${BUILD_REPO_NAME:-}" ]] || LICENSE_ENV+=("REPO=$BUILD_REPO_NAME")
  # Reuse gate-built binaries, but force evaluation if a target file would skip it.
  _license_makeflags=""
  [[ ! -e licensecheck ]] || _license_makeflags=-B
  LICENSE_ENV+=("MAKEFLAGS=$_license_makeflags")
  # Track license tools separately so gate-built and pre-existing files remain.
  _license_artifact_failure=""
  python3 "$SCRIPT_DIR/generated-artifacts.py" prepare "$REPO" "${STATE_FILE}.license" "" || \
    _license_artifact_failure=prepare
  _EVIDENCE_LICENSE_STATUS=running
  _EVIDENCE_LICENSE_RC=0
  _license_status=(0 0)
  if $_EVIDENCE_READY; then
    bounded_command "$LICENSE_CHECK_TIMEOUT" "${LICENSE_ENV[@]}" make licensecheck 2>&1 | \
      tee "$CVE_FIX_EVIDENCE_DIR/license.log" || _license_status=("${PIPESTATUS[@]}")
    _EVIDENCE_LICENSE_RC=${_license_status[0]}
  else
    bounded_command "$LICENSE_CHECK_TIMEOUT" "${LICENSE_ENV[@]}" make licensecheck || _EVIDENCE_LICENSE_RC=$?
  fi
  _EVIDENCE_LICENSE_STATUS=completed
  if [[ ${_license_status[1]} -ne 0 ]]; then
    _EVIDENCE_LICENSE_STATUS=capture_failed
    POLICY_CHECK_FAILED=true
    UNSEEN_NEEDS_REVIEW=true
    echo "ERROR: Cannot capture license output (tee exited ${_license_status[1]}; command exited $_EVIDENCE_LICENSE_RC); PR generation suppressed."
  elif [[ $_EVIDENCE_LICENSE_RC -ne 0 ]]; then
    POLICY_CHECK_FAILED=true
    UNSEEN_NEEDS_REVIEW=true
    echo "POLICY REVIEW REQUIRED: make licensecheck failed or timed out; PR generation suppressed."
  else
    echo "License policy check passed."
  fi
  if [[ -z "$_license_artifact_failure" ]]; then
    python3 "$SCRIPT_DIR/generated-artifacts.py" record "$REPO" "${STATE_FILE}.license" "" || \
      _license_artifact_failure=record
    if [[ -z "$_license_artifact_failure" ]]; then
      python3 "$SCRIPT_DIR/generated-artifacts.py" prepare "$REPO" "${STATE_FILE}.license" "" || \
        _license_artifact_failure=cleanup
    fi
  fi
  if [[ -n "$_license_artifact_failure" ]]; then
    POLICY_CHECK_FAILED=true
    UNSEEN_NEEDS_REVIEW=true
    echo "ERROR: License-tool cleanup unconfirmed (artifact $_license_artifact_failure failed); PR generation suppressed."
  fi
fi

if ! _tracked_tree_unchanged "$VERIFIED_HEAD" --restore-generated-noise; then
  echo "NEEDS_REVIEW: Retained HEAD and unchanged tracked files could not be confirmed after final checks." >&2
  POLICY_CHECK_FAILED=true
  UNSEEN_NEEDS_REVIEW=true
fi

# ── Phase 6: Report ───────────────────────────────────────────────────────────

banner "Summary: $(basename "$REPO")/$BRANCH"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Fix branch: $CURRENT_BRANCH"
if [[ -n "${ORIGINAL_REF:-}" ]]; then
  printf 'Original ref: %s\n' "$ORIGINAL_REF"
fi
GATE_CONFIRMED=true
$GATE_FAILED && GATE_CONFIRMED=false
SUMMARY_TESTED_HEAD="not run"
if [[ "$_EVIDENCE_TEST_STATUS" == completed && ${#_TEST_ATTEMPT_RESULTS[@]} -gt 0 ]]; then
  SUMMARY_TESTED_HEAD=$TESTED_HEAD
fi
printf 'Scans: initial %s (exit %s); final %s (exit %s; confirmed=%s)\n' \
  "$_EVIDENCE_INITIAL_STATUS" "$SCAN_RC" "$_EVIDENCE_FINAL_STATUS" "$GATE_RC" "$GATE_CONFIRMED"
printf 'Scan scope (initial): %s\nScan scope (final): %s\n' "$INITIAL_SCAN_SCOPE" "$FINAL_SCAN_SCOPE"
printf 'Commands: build: %s; test: %s\n' "${BUILD_CMD:-not configured}" "${TEST_CMD:-not configured}"
printf 'Tests: %s (exit %s; failed=%s); tested HEAD: %s; attempts: %s\n' \
  "$_EVIDENCE_TEST_STATUS" "${_EVIDENCE_TEST_RC:-not run}" "$TESTS_FAILED" \
  "$SUMMARY_TESTED_HEAD" "${_TEST_ATTEMPT_RESULTS[*]:-none}"
printf 'Verification: %s (exit %s); license: %s (exit %s)\n' \
  "$_EVIDENCE_VERIFY_STATUS" "${_EVIDENCE_VERIFY_RC:-not run}" \
  "$_EVIDENCE_LICENSE_STATUS" "${_EVIDENCE_LICENSE_RC:-not run}"

# Refresh the base before printing a push/PR command. Do not silently rebase:
# this branch may contain operator edits, and a history rewrite can hide a
# conflict. Instead, require the operator to rerun from the new base.
BASE_CHANGED=false
BASE_REFRESH_FAILED=false
DCO_FAILED=false
if [[ -n "${BASE_SHA:-}" ]]; then
  if ! fetch_upstream_branch "$UPSTREAM_REMOTE" "$BRANCH" >/dev/null 2>&1; then
    BASE_REFRESH_FAILED=true
  elif [[ "$(git rev-parse "$UPSTREAM_REF" 2>/dev/null || true)" != "$BASE_SHA" ]]; then
    BASE_CHANGED=true
  fi
  if ! git rev-parse --verify "$UPSTREAM_REF" >/dev/null 2>&1; then
    BASE_REFRESH_FAILED=true
  fi
  if [[ "$BASE_REFRESH_FAILED" == "false" && "$BASE_CHANGED" == "false" ]]; then
    _DCO_MISSING=$(dco_missing_commits "$UPSTREAM_REF")
    [[ -z "$_DCO_MISSING" ]] || DCO_FAILED=true
  fi
fi

# Reconcile success counts against the authoritative final scan. Include initial
# ignored findings only when Grype already advertised a fix; this credits stale
# ignore repairs (a stale ignore whose fix now exists) without mislabelling no-fix
# exceptions. A tuple is fixed only when absent from both final matches and final
# ignoredMatches at the same normalized module location.
FIXED_CVES=$(count_cves_fixed "$(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}")")
if ! $GATE_FAILED && jq empty <<< "$GATE_JSON" 2>/dev/null; then
  # Mask commit hashes so binaries renamed by fix commits still match.
  _REVS=$(scan_location_revs)
  _INITIAL_FIXABLE_TUPLES=$(jq -r --argjson revs "$_REVS" "$REV_MASK_JQ"'
    def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
    [((.matches // []) + [(.ignoredMatches // [])[] | select((.vulnerability.fix.versions // []) | length > 0)])[] |
      select(.artifact.type == "go-module") as $m |
      (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
      "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc | canon)"] | unique | .[]' \
    <<< "$SCAN_JSON" 2>/dev/null | sort -u)
  _FINAL_ALL_TUPLES=$(jq -r --argjson revs "$_REVS" "$REV_MASK_JQ"'
    def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
    [((.matches // []) + (.ignoredMatches // []) + (.generatedBinaryDuplicates // []))[] |
      select(.artifact.type == "go-module") as $m |
      (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
      "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc | canon)"] | unique | .[]' \
    <<< "$GATE_JSON" 2>/dev/null | sort -u)
  _FIXED_TUPLES=$(comm -23 \
    <(printf '%s\n' "$_INITIAL_FIXABLE_TUPLES" | sed '/^$/d') \
    <(printf '%s\n' "$_FINAL_ALL_TUPLES" | sed '/^$/d'))
  FIXED_CVES=$(printf '%s\n' "$_FIXED_TUPLES" | sed '/^$/d' | wc -l | tr -d ' ')
  FIXED_COUNT=$(printf '%s\n' "$_FIXED_TUPLES" | sed '/^$/d' | cut -d'|' -f2 | sort -u | wc -l | tr -d ' ')
fi

# When the gate build/scan failed, GATE_REMAINING is 0 only because nothing could
# be counted — not because the repo is clean. Report it honestly so the headline
# never reads "Outstanding: 0" on a run whose CVE status is unconfirmed.
if $GATE_FAILED; then
  OUTSTANDING="unknown (rescan failed)"
else
  OUTSTANDING="$GATE_REMAINING"
fi
REVIEW_N=$(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -c "^NEEDS_REVIEW:" || true)
IGNORED_COUNT=$(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | grep -c "^IGNORED:" || true)
echo "Fixed: ${FIXED_COUNT} pkgs / ${FIXED_CVES} findings · Ignored: ${IGNORED_COUNT} · Needs Review: ${REVIEW_N} · Outstanding: ${OUTSTANDING} · Run time: ${SECONDS}s"

# Results are unconfirmed when a gate we couldn't complete (build/scanner failure),
# failing tests, or failed subagent verification leaves the fix unverified. This is
# distinct from GATE_REMAINING>0 (a real, counted partial fix), which is still a
# legitimate PR — so it does not suppress the PR command below.

# Full CVE IDs remain in the commit messages listed below.
format_fix_detail "$(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}")"

COMMIT_COUNT=$(git rev-list --count "$UPSTREAM_REF"..HEAD 2>/dev/null) || COMMIT_COUNT=""
PR_NOT_READY=false
if [[ -z "$COMMIT_COUNT" ]]; then
  PR_NOT_READY=true
  echo "WARNING: could not compare with $UPSTREAM_REF; keeping the fix branch $CURRENT_BRANCH."
elif [[ "$COMMIT_COUNT" -gt 0 ]]; then
  _CS=$([[ "$COMMIT_COUNT" -eq 1 ]] && echo commit || echo commits)
  echo ""
  echo "(${COMMIT_COUNT} ${_CS} — see Commits: below)"
  echo "Commits:"
  git --no-pager log "$UPSTREAM_REF"..HEAD --oneline

  # Audit: reject when the fix branch touches files beyond go.mod/go.sum/.grype.yaml.
  # These non-dependency files belong in a separate branch to keep the CVE audit
  # trail clean.
  if ! audit_branch_non_cve_files "$UPSTREAM_REF"; then
    POLICY_CHECK_FAILED=true
    UNSEEN_NEEDS_REVIEW=true
  fi

  # Suppress the ready-to-push PR command when results are unconfirmed: pushing
  # here risks a PR that claims to fix CVEs it never verified. Show what's wrong
  # instead. (A counted partial fix — GATE_REMAINING>0 — is still confirmed and
  # gets its PR command.)
  # shellcheck disable=SC2153 # FETCH_FAILED comes from the detect.sh state
  if results_unconfirmed "$GATE_FAILED" "$TESTS_FAILED" "$VERIFY_FAILED" \
      "$UNSEEN_NEEDS_REVIEW" "$GATE_REMAINING" "$FETCH_FAILED" \
      "$BASE_CHANGED" "$DCO_FAILED" "$BASE_REFRESH_FAILED" "$POLICY_CHECK_FAILED"; then
    PR_NOT_READY=true
    echo ""
    echo "NOT READY TO PUSH: PR prerequisites are not satisfied."
    $GATE_FAILED && echo "  - final rescan could not confirm CVE status"
    $TESTS_FAILED && echo "  - tests failed after applying fixes"
    $VERIFY_FAILED && echo "  - subagent verification failed"
    $POLICY_CHECK_FAILED && echo "  - repository policy check failed or needs review"
    $UNSEEN_NEEDS_REVIEW && echo "  - packages require team review before merge"
    $FETCH_FAILED && echo "  - base branch fetch failed; commits may be based on stale state"
    $BASE_REFRESH_FAILED && echo "  - final base refresh failed; current base could not be verified"
    $BASE_CHANGED && echo "  - base branch moved during the run; re-run from the current base"
    if $DCO_FAILED; then
      echo "  - commit(s) missing Signed-off-by:"
      printf '      %s\n' "${_DCO_MISSING//$'\n'/$'\n      '}"
    fi
    echo "Review the ${COMMIT_COUNT} commit(s) above and re-run once resolved; no PR command emitted."
  else
    # Generate PR command
    echo ""
    BASE_BRANCH="$BRANCH"
    _ADVISORIES=$(printf '%s\n' "${_FIXED_TUPLES:-}" | sed '/^$/d' | cut -d'|' -f1 | sort -u | wc -l)
    PLURAL=$([[ "$COMMIT_COUNT" -eq 1 && "$_ADVISORIES" -le 1 ]] && echo "" || echo "s")
    if [[ "$GATE_REMAINING" -gt 0 ]]; then
      PR_TITLE="Partial CVE fix in ${BASE_BRANCH} ($GATE_REMAINING unresolved)"
      echo "NOTE: $GATE_REMAINING finding(s) remain — PR title reflects a partial fix."
    else
      PR_TITLE="Fix CVE${PLURAL} in ${BASE_BRANCH}"
    fi
    if publication_target "$CURRENT_BRANCH"; then
      echo "PR command:"
      printf 'git push --no-follow-tags -- %q %q && \\\n' "$PR_PUSH_REMOTE" "refs/heads/$CURRENT_BRANCH:refs/heads/$CURRENT_BRANCH"
      echo "gh pr create \\"
      printf '  --title %q \\\n' "$PR_TITLE"
      printf '  --body %q \\\n' "See commit message${PLURAL} for details."
      printf '  --repo %q \\\n' "$PR_REPOSITORY"
      printf '  --base %q \\\n' "$BASE_BRANCH"
      printf '  --head %q \\\n' "$PR_HEAD"
      echo "  --assignee \"@me\""
    else
      echo "PR command unavailable: GitHub base and a single push destination could not be confirmed."
    fi
  fi
else
  # Nothing to keep: return the checkout to where the run started.
  remove_fix_branch >/dev/null
  git show-ref --verify --quiet "refs/heads/$CURRENT_BRANCH" ||
    echo "No commits; removed the empty fix branch."
fi

if $FETCH_FAILED; then
  # A scan of cached remote state cannot confirm the current branch either way.
  PR_NOT_READY=true
  echo ""
  echo "WARNING: git fetch failed earlier. Branch was created from cached remote state."
  echo "Run 'git fetch' and re-run if it fetches new commits."
fi

# Exit code: driven by the final rescan gate (real outstanding CVEs) plus the
# non-CVE failures the rescan can't see (tests, verification, PR prerequisites).
RUN_COMPLETED=true
exit "$(cve_fix_exit_code "$GATE_REMAINING" "$GATE_FAILED" "$TESTS_FAILED" "$VERIFY_FAILED" "$UNSEEN_NEEDS_REVIEW" "$PR_NOT_READY")"
