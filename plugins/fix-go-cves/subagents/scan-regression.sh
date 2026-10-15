#!/usr/bin/env bash
# Compare initial and final scans to detect regressions.
# Finds new CVEs introduced by fixes and unresolved CVEs without ignore entries.
# Usage: scan-regression.sh STATE_FILE REPORT_DIR
set -euo pipefail

STATE_FILE="${1:?Usage: scan-regression.sh STATE_FILE REPORT_DIR}"
REPORT_DIR="${2:?Usage: scan-regression.sh STATE_FILE REPORT_DIR}"

# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/lib.sh"
load_state "$STATE_FILE"

NEW_CVES=0
UNRESOLVED=0
DETAILS=()

_pkg_info_from_scan() {
  local _cve="$1" _pkg="$2" _loc="$3"
  echo "$FINAL_SCAN" | jq -r --arg cve "$_cve" --arg pkg "$_pkg" --arg loc "$_loc" \
    'def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
     .matches[] | select(.vulnerability.id == $cve and .artifact.name == $pkg) |
     select($loc == "" or any(.artifact.locations[]?; (.path | normloc) == $loc)) |
     "\(.artifact.name) \(.artifact.version) \(.vulnerability.severity) \(((.vulnerability.fix.versions // []) | map(select(type == "string" and . != "")) | if length == 0 then "no-fix" else (sort_by(ltrimstr("v") | split("+")[0] | split("-")[0] | split(".") | map(tonumber? // 0)) | last) end))"' \
    2>/dev/null | head -1 || echo "unknown"
}

# Read initial scan. A missing initial scan means we can't compare — that is a
# scanner/pipeline failure, not a clean result, so emit SCAN_FAILED and exit
# non-zero (callers must not trust an LLM PASS when the scan is unreliable).
INITIAL_SCAN_FILE="$REPORT_DIR/initial-scan.json"
FINAL_SCAN_FILE="$REPORT_DIR/final-scan.json"
# A prior verification iteration must never supply evidence for the current
# report. Publish only the JSON produced by this invocation, after validation.
rm -f "$FINAL_SCAN_FILE"
if [[ ! -f "$INITIAL_SCAN_FILE" ]]; then
  echo "NEW_CVES=0 UNRESOLVED=0"
  echo "SCAN_FAILED=1"
  echo "SKIP: No initial scan found at $INITIAL_SCAN_FILE"
  exit 1
fi

if ! grype_scan_json_valid "$INITIAL_SCAN_FILE"; then
  echo "NEW_CVES=0 UNRESOLVED=0"
  echo "SCAN_FAILED=1"
  echo "SKIP: Initial scan has invalid Grype JSON schema"
  exit 1
fi

# Run final scan, retrying transient scanner/network blips (grype DB pull,
# docker/podman DNS). A persistent empty/invalid result is a scanner failure,
# not a clean repo — emit SCAN_FAILED so callers don't trust an LLM PASS.
FINAL_SCAN=""
SCAN_ERR=""
FINAL_ATTEMPTS="${CVE_FIX_SCAN_ATTEMPTS:-3}"
SCAN_OUT_FILE=$(mktemp "${TMPDIR:-/tmp}/cve-scan.XXXXXX")
for ((SCAN_TRY=1; SCAN_TRY<=FINAL_ATTEMPTS; SCAN_TRY++)); do
  # Rebuild on every verification iteration: a previous iteration may have
  # changed go.mod, making the prior binaries stale evidence.
  SCAN_RC=0
  SCAN_ERR=$(BUILD_UPX=false bash "$CVE_SCRIPTS/scan.sh" "$STATE_FILE" --no-update --json \
    2>&1 1>"$SCAN_OUT_FILE") || SCAN_RC=$?
  FINAL_SCAN=$(cat "$SCAN_OUT_FILE")
  if [[ $SCAN_RC -eq 0 && -n "$FINAL_SCAN" &&
        ! -f "${STATE_FILE}.build-failed" && ! -f "${STATE_FILE}.scanner-degraded" &&
        ! -f "${STATE_FILE}.coverage-unknown" ]] && printf '%s\n' "$FINAL_SCAN" | grype_scan_json_valid; then
    break
  fi
  FINAL_SCAN=""
  # Retry only transient scanner/network errors; a real invalid result won't clear.
  if [[ $SCAN_TRY -lt $FINAL_ATTEMPTS ]] && printf '%s' "$SCAN_ERR" | is_scan_transient; then
    sleep "$(cve_fix_backoff_delay "$SCAN_TRY")"
    continue
  fi
  break
done
rm -f "$SCAN_OUT_FILE"

if [[ -z "$FINAL_SCAN" ]]; then
  echo "NEW_CVES=0 UNRESOLVED=0"
  echo "SCAN_FAILED=1"
  echo "SKIP: Final scan failed or produced invalid JSON"
  [[ -n "$SCAN_ERR" ]] && echo "SCAN_ERR: $(printf '%s' "$SCAN_ERR" | tail -3 | tr '\n' ' ')"
  exit 1
fi

FINAL_SCAN_TMP="${FINAL_SCAN_FILE}.tmp.$$"
printf '%s\n' "$FINAL_SCAN" > "$FINAL_SCAN_TMP"
mv "$FINAL_SCAN_TMP" "$FINAL_SCAN_FILE"

# Extract exact (CVE-ID, artifact-name, normalized-location) tuples.
# Keying on both fields prevents a new pkg-B carrying the same CVE-ID as a
# fixed pkg-A from being misclassified as UNRESOLVED (same CVE, different pkg).
INITIAL_CVES=$(jq -r 'def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
  .matches[] | select(.artifact.type == "go-module") as $m |
  (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
  "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc)"' "$INITIAL_SCAN_FILE" 2>/dev/null | sort -u || echo "")

# Extract (CVE-ID, artifact-name) tuples from final scan (go-module only)
FINAL_CVES=$(echo "$FINAL_SCAN" | jq -r 'def normloc: sub("^/src/"; "/") | if . == "" or startswith("/") then . else "/" + . end;
  .matches[] | select(.artifact.type == "go-module") as $m |
  (($m.artifact.locations // []) | if length == 0 then [{"path":""}] else . end)[] |
  "\($m.vulnerability.id)|\($m.artifact.name)|\(.path | normloc)"' 2>/dev/null | sort -u || echo "")

# Find NEW CVEs: in final scan but not in initial scan
if [[ -n "$FINAL_CVES" ]] && [[ -n "$INITIAL_CVES" ]]; then
  NEW_CVE_LIST=$(comm -23 <(echo "$FINAL_CVES") <(echo "$INITIAL_CVES") || echo "")
elif [[ -n "$FINAL_CVES" ]]; then
  NEW_CVE_LIST="$FINAL_CVES"
else
  NEW_CVE_LIST=""
fi

while IFS= read -r cve_tuple; do
  [[ -z "$cve_tuple" ]] && continue
  IFS='|' read -r cve_id pkg_name location <<< "$cve_tuple"
  # Get package info from final scan (include fix version for deterministic fix)
  PKG_INFO=$(_pkg_info_from_scan "$cve_id" "$pkg_name" "$location")
  location_suffix=""
  [[ -n "$location" ]] && location_suffix=" location:$location"
  DETAILS+=("NEW: $cve_id ($PKG_INFO)$location_suffix")
  NEW_CVES=$((NEW_CVES + 1))
done <<< "$NEW_CVE_LIST"

# Find UNRESOLVED CVEs: present in both the initial and final scans. Ignores are
# already applied by grype via --config — unscoped ignores are moved out of
# .matches, and location-scoped/expired ones correctly stay — so any CVE still in
# .matches is genuinely unresolved. (A local .grype.yaml re-parse here was blind to
# grype's location scoping and fix-state auto-expiry, dropping real UNRESOLVED CVEs.)
if [[ -n "$FINAL_CVES" ]] && [[ -n "$INITIAL_CVES" ]]; then
  STILL_PRESENT=$(comm -12 <(echo "$FINAL_CVES") <(echo "$INITIAL_CVES") || echo "")

  while IFS= read -r cve_tuple; do
    [[ -z "$cve_tuple" ]] && continue
    IFS='|' read -r cve_id pkg_name location <<< "$cve_tuple"

    # Get package info (include fix version for deterministic fix)
    PKG_INFO=$(_pkg_info_from_scan "$cve_id" "$pkg_name" "$location")
    location_suffix=""
    [[ -n "$location" ]] && location_suffix=" location:$location"

    # A known policy boundary leaves an existing finding for team review without
    # invalidating other verified repairs. The final gate still counts it as an
    # outstanding CVE and keeps the run partial. Failed fixes remain unresolved,
    # and the NEW loop above never exempts regressions using these markers.
    if pkg_sentinel_file_matches "$REPORT_DIR/needs-review-pkgs" "$pkg_name" "$location"; then
      DETAILS+=("NEEDS_REVIEW: $cve_id ($PKG_INFO)$location_suffix")
    else
      DETAILS+=("UNRESOLVED: $cve_id ($PKG_INFO)$location_suffix")
      UNRESOLVED=$((UNRESOLVED + 1))
    fi
  done <<< "$STILL_PRESENT"
fi

# Output structured results
echo "NEW_CVES=$NEW_CVES UNRESOLVED=$UNRESOLVED"
for detail in "${DETAILS[@]}"; do
  echo "$detail"
done
