#!/usr/bin/env bash
# Scan for CVEs using grype.
# Usage: scan.sh STATE_FILE [--fresh] [--no-update] [--json] [--skip-build]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: scan.sh STATE_FILE [--fresh] [--no-update] [--json] [--skip-build]}"
shift
load_state "$STATE_FILE"
printf 'scan incomplete; native-binary coverage unverified\n' > "${STATE_FILE}.scan-scope"

# Collect flags
GRYPE_FLAGS=()
SKIP_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --fresh|--no-update|--json) GRYPE_FLAGS+=("$arg") ;;
    --skip-build) SKIP_BUILD=true ;;
    *) die "Unknown flag: $arg" ;;
  esac
done

SCAN_EVIDENCE_DIR=""
if [[ -n "${CVE_FIX_EVIDENCE_DIR:-}" ]]; then
  prepare_evidence_directory
  mkdir -p "$CVE_FIX_EVIDENCE_DIR/scans"
  SCAN_EVIDENCE_DIR=$(mktemp -d "$CVE_FIX_EVIDENCE_DIR/scans/${CVE_FIX_EVIDENCE_PHASE:-scan}.XXXXXX")
  CVE_FIX_EVIDENCE_SCAN_DIR="$SCAN_EVIDENCE_DIR"
  : > "$SCAN_EVIDENCE_DIR/binaries.jsonl"
fi
BUILD_EVIDENCE_STATUS=not_configured
BUILD_EVIDENCE_RC=null
[[ "$SKIP_BUILD" != true ]] || BUILD_EVIDENCE_STATUS=skipped
[[ -z "$SCAN_EVIDENCE_DIR" ]] || record_scan_status "$SCAN_EVIDENCE_DIR/status.json" null "$BUILD_EVIDENCE_STATUS"

# Build if configured (needed for stdlib CVE detection in compiled binaries).
# A build failure means the scan covers source only and may miss stdlib CVEs in
# binaries — record it out-of-band in a sentinel file (stdout is grype JSON) so
# fix-all.sh can refuse to report the repo clean. Cleared on a successful build.
if [[ -n "${BUILD_CMD:-}" ]] && [[ "$SKIP_BUILD" != "true" ]]; then
  build_env_scrub
  artifact_manifest_prepare
  rm -f "${STATE_FILE}.build-failed" "${STATE_FILE}.network-broken" "${STATE_FILE}.coverage-unknown"
  # Capture the build output (still streamed to stderr) so a failure can be
  # classified. A DNS/proxy/registry error (see is_scan_transient) means the
  # environment is offline, not that the code is broken — record a distinct
  # sentinel so fix-all.sh can fail fast instead of producing an unverifiable
  # fix (go get, the rebuild, and the rescan gate all need the network).
  if [[ -n "$SCAN_EVIDENCE_DIR" ]]; then build_log="$SCAN_EVIDENCE_DIR/build.log"
  else build_log=$(mktemp "${TMPDIR:-/tmp}/cve-fix-build.XXXXXX"); fi
  # Dependency changes do not reliably appear as Make prerequisites of binary
  # targets. Force both the outer Make and any nested Dapper Make to rebuild so
  # Grype never evaluates binaries produced from the pre-fix module graph.
  build_rc=0
  build_status=(0 0)
  BUILD_EVIDENCE_STATUS=running
  [[ -z "$SCAN_EVIDENCE_DIR" ]] || record_scan_status "$SCAN_EVIDENCE_DIR/status.json" null running
  BUILD_ENV=(env)
  [[ ${#ENV_SCRUB[@]} -eq 0 ]] || BUILD_ENV=("${ENV_SCRUB[@]}")
  "${BUILD_ENV[@]}" ${BUILD_REPO_NAME:+REPO="$BUILD_REPO_NAME"} MAKEFLAGS=-B \
    timeout --foreground "${CVE_FIX_BUILD_TIMEOUT:-1800}" bash -c "$BUILD_CMD" 2>&1 | \
    tee "$build_log" >&2 || build_status=("${PIPESTATUS[@]}")
  build_rc=${build_status[0]}
  BUILD_EVIDENCE_STATUS=completed
  BUILD_EVIDENCE_RC=$build_rc
  if [[ ${build_status[1]} -ne 0 ]]; then
    printf 'scan incomplete: build output capture failed (command %s, tee %s)\n' \
      "$build_rc" "${build_status[1]}" > "${STATE_FILE}.scan-scope"
    echo "ERROR: Cannot capture build output (tee exited ${build_status[1]}; build exited $build_rc); scan stopped." >&2
    [[ -z "$SCAN_EVIDENCE_DIR" ]] || record_scan_status "$SCAN_EVIDENCE_DIR/status.json" 2 completed "$build_rc"
    [[ -n "$SCAN_EVIDENCE_DIR" ]] || rm -f "$build_log"
    exit 2
  fi
  if [[ $build_rc -ne 0 ]]; then
    echo "WARNING: Build failed. Scanning source only (may miss stdlib CVEs in binaries)." >&2
    : > "${STATE_FILE}.build-failed"
    if [[ $build_rc -eq 124 ]]; then
      echo "WARNING: Build timed out after ${CVE_FIX_BUILD_TIMEOUT:-1800}s." >&2
    elif [[ $build_rc -eq 137 ]]; then
      echo "WARNING: Build was killed (exit 137)." >&2
    elif is_scan_transient "$build_log"; then
      : > "${STATE_FILE}.network-broken"
    fi
  else
    artifact_manifest_record
    # grype reads stdlib versions only from binaries it can parse. If any
    # executable in the tree (new or pre-existing) is packed (opaque), the scan
    # is blind to its stdlib CVEs — record a sentinel so fix-all.sh won't report
    # the repo clean on coverage it couldn't actually verify.
    detect_opaque_binaries && : > "${STATE_FILE}.coverage-unknown"
  fi
  [[ -n "$SCAN_EVIDENCE_DIR" ]] || rm -f "$build_log"
else
  # No build step configured — still detect pre-existing opaque/stale binaries in
  # the tree. A source-only scan is blind to stdlib CVEs in any such binary, so
  # write the coverage-unknown sentinel when any are found; clear a stale sentinel
  # from a prior run when none are found.
  rm -f "${STATE_FILE}.coverage-unknown"
  detect_opaque_binaries && : > "${STATE_FILE}.coverage-unknown"
fi

# run_grype sets GRYPE_DB_DEGRADED when grype couldn't update/load its vuln DB
# during a scan that attempted a fetch. A stale/absent DB silently under-reports
# CVEs, so record a sentinel (stdout is grype's output) that fix-all.sh keys off
# to refuse a "clean" verdict it can't trust. Cleared first so it never lingers.
# run_grype also sets GRYPE_SCAN_TRANSIENT when the scanner itself failed due to
# a transient network error (DNS, VPN) — distinct from a degraded-DB success.
rm -f "${STATE_FILE}.scanner-degraded" "${STATE_FILE}.scan-transient"
grype_rc=0
scan_output_file=$(mktemp "${TMPDIR:-/tmp}/cve-grype-scan.XXXXXX")
if [[ -n "$SCAN_EVIDENCE_DIR" ]]; then
  run_grype "${GRYPE_FLAGS[@]}" >"$scan_output_file" 2> "$SCAN_EVIDENCE_DIR/scanner.log" || grype_rc=$?
  cat "$SCAN_EVIDENCE_DIR/scanner.log" >&2
  cp "$scan_output_file" "$SCAN_EVIDENCE_DIR/scanner-output.txt"
else
  run_grype "${GRYPE_FLAGS[@]}" >"$scan_output_file" 2> >(cat >&2) || grype_rc=$?
fi
scan_output=$(cat "$scan_output_file")
rm -f "$scan_output_file"
if [[ " ${GRYPE_FLAGS[*]} " == *" --json "* ]]; then
  # Validate the scanner's original document before a filter can normalize
  # missing arrays into an empty result and accidentally manufacture a clean scan.
  if grype_scan_json_valid <<< "$scan_output"; then
    filtered_output=$(printf '%s\n' "$scan_output" | \
      filter_generated_binary_duplicates "$REPO" "${STATE_FILE}.built-artifacts" 2>/dev/null) || filtered_output="$scan_output"
    printf '%s\n' "$filtered_output"
  else
    echo "ERROR: scanner produced invalid Grype JSON evidence." >&2
    [[ $grype_rc -ne 0 ]] || grype_rc=1
    printf '%s\n' "$scan_output"
  fi
else
  printf '%s\n' "$scan_output"
fi
if [[ "${GRYPE_DB_DEGRADED:-0}" == "1" ]]; then
  : > "${STATE_FILE}.scanner-degraded"
fi
if [[ "${GRYPE_SCAN_TRANSIENT:-0}" == "1" ]] && [[ "$grype_rc" -ne 0 ]]; then
  : > "${STATE_FILE}.scan-transient"
fi
if [[ -n "$SCAN_EVIDENCE_DIR" ]]; then
  record_scan_status "$SCAN_EVIDENCE_DIR/status.json" "$grype_rc" "$BUILD_EVIDENCE_STATUS" "$BUILD_EVIDENCE_RC"
fi
if [[ $grype_rc -eq 0 ]]; then
  native_locations=""
  if [[ -n "$SCAN_EVIDENCE_DIR" && -f "$SCAN_EVIDENCE_DIR/catalog.cdx.json" ]]; then
    native_locations=$(jq -r '[.components[]? | select(.name == "stdlib") |
      select(any(.properties[]?; .name == "syft:package:foundBy" and .value == "go-module-binary-cataloger")) |
      .properties[]? | select(.name | test("^syft:location:[0-9]+:path$")) | .value] | unique | join(", ")' \
      "$SCAN_EVIDENCE_DIR/catalog.cdx.json" 2>/dev/null) || native_locations=""
  fi
  if [[ -n "$native_locations" ]]; then
    printf 'Go dependency scan; native Go binaries cataloged at %s; coverage of other binaries unverified\n' \
      "$native_locations" > "${STATE_FILE}.scan-scope"
  else
    printf 'Go dependency scan; native-binary coverage unverified (no positive catalog evidence retained)\n' > "${STATE_FILE}.scan-scope"
  fi
fi
printf 'Scan scope (%s): %s\n' "${CVE_FIX_EVIDENCE_PHASE:-scan}" "$(cat "${STATE_FILE}.scan-scope")" >&2
exit "$grype_rc"
