#!/usr/bin/env bash
# Review CVE fix results using the configured LLM agent.
# Pre-fetches all evidence, builds prompt from template, invokes the agent.
# Usage: review.sh STATE_FILE FIX_SUMMARY
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: review.sh STATE_FILE FIX_SUMMARY [SCAN_OUTPUT]}"
FIX_SUMMARY="${2:-}"
CURRENT_SCAN="${3:-}"
load_state "$STATE_FILE"
GO_MINOR_GUARD=${GO_MINOR_GUARD:-false}
rm -f -- "${STATE_FILE}.review-unresolved"

PROMPT_TEMPLATE="$SCRIPT_DIR/review-prompt.md"
[[ -f "$PROMPT_TEMPLATE" ]] || die "Prompt template not found: $PROMPT_TEMPLATE"

# --- Pre-fetch evidence ---

# Use provided scan output, or run a fresh scan
if [[ -z "$CURRENT_SCAN" ]]; then
  echo "Running scan for review evidence..."
  # shellcheck disable=SC2119
  CURRENT_SCAN=$(run_grype 2>&1) || CURRENT_SCAN="(scan failed)"
fi

# Locate info for any NEEDS_REVIEW packages
LOCATE_OUTPUT=""
PACKAGE_SUMMARY=$(printf '%s\n' "$FIX_SUMMARY" | package_review_summary)
NEEDS_REVIEW_PKGS=$(printf '%s\n' "$PACKAGE_SUMMARY" | sed -nE 's/^NEEDS_REVIEW: ([^ ]+) — .*/\1/p')
for PKG in $NEEDS_REVIEW_PKGS; do
  if [[ "$PKG" != *.* ]]; then
    LOCATE_OUTPUT+="$PKG: see fix output above (not a Go module path)."$'\n\n'
    continue
  fi
  LOCATE_OUTPUT+="$(bash "$SCRIPT_DIR/locate.sh" "$STATE_FILE" "$PKG" 2>&1 || true)"
  LOCATE_OUTPUT+=$'\n\n'
done

if [[ -z "$LOCATE_OUTPUT" ]]; then
  LOCATE_OUTPUT="All CVEs were fixed in the deterministic phase."
fi

# --- Build prompt ---
PROMPT=$(render_template REPO BRANCH FIX_SUMMARY CURRENT_SCAN LOCATE_OUTPUT \
  BUILD_GO_VERSION GO_MINOR_GUARD < "$PROMPT_TEMPLATE")

# --- Invoke configured agent ---
AGENT_PROVIDER=$(cve_fix_agent_provider)
echo "Invoking $AGENT_PROVIDER for review..."
if ! command -v "$AGENT_PROVIDER" &>/dev/null; then
  echo "WARNING: $AGENT_PROVIDER CLI not available, skipping agent review."
  echo "Deterministic fix results are still valid. Review manually:"
  echo ""
  echo "$FIX_SUMMARY"
  exit 0
fi

# Scrub provider vars (ENV_UNSET) so a mis-pointed shell rc can't force an auth
# failure. env(1), never eval — PROMPT is untrusted (multi-line, may hold `$()`).
build_env_scrub

# Retry transient infra blips (e.g. 429/overload) with exponential backoff; a
# clean result returns on the first pass. Deterministic auth errors do NOT retry.
MAX_ATTEMPTS="${CVE_FIX_AGENT_ATTEMPTS:-3}"
AGENT_RC=0
OUTPUT=""
for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
  AGENT_RC=0
  build_cve_fix_agent_command "$PROMPT"
  OUTPUT=$(timeout "${CVE_FIX_AGENT_TIMEOUT:-600}" \
    "${ENV_SCRUB[@]+"${ENV_SCRUB[@]}"}" "${CVE_FIX_AGENT_CMD[@]}" \
    </dev/null 2>&1) || AGENT_RC=$?
  # Structured reviews can quote provider errors. Keep genuine terminal errors
  # authoritative, including zero-exit errors beside prompt-like outcome lines.
  PROVIDER_ERROR_OUTPUT="$OUTPUT"
  if [[ $AGENT_RC -eq 0 ]] && grep -qE '^(UNRESOLVED|RESOLVED):' <<< "$OUTPUT"; then
    PROVIDER_ERROR_OUTPUT=$(awk '
      /^[[:space:]]*(```|~~~)/ { quoted=!quoted; next }
      !quoted && /^(ERROR:|Error:|error:|API Error:|HTTP error:)/ { print }
    ' <<< "$OUTPUT")
  fi
  if printf '%s' "$PROVIDER_ERROR_OUTPUT" | is_auth_error || printf '%s' "$PROVIDER_ERROR_OUTPUT" | is_infra_error; then
    AGENT_RC=1
  fi
  [[ $AGENT_RC -eq 0 ]] && break
  # Deterministic auth/permission/model error: retrying won't help.
  printf '%s' "$OUTPUT" | is_auth_error && break
  if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]] && { [[ $AGENT_RC -eq 124 ]] || printf '%s' "$OUTPUT" | is_infra_error; }; then
    DELAY=$(cve_fix_backoff_delay "$ATTEMPT")
    echo "Agent review hit a transient error (exit $AGENT_RC); retrying in ${DELAY}s..." >&2
    sleep "$DELAY"
    continue
  fi
  break
done

echo "$OUTPUT"

# A non-zero exit is a deterministic env or transient failure — fall back to
# manual review. Auth errors also print provider env for diagnostics.
# Note: block 3 (catch-all) intentionally merges "Review manually:" into its
# warning line; the shared echo "$FIX_SUMMARY" / exit 0 tail is still factored.
if [[ $AGENT_RC -ne 0 ]]; then
  if printf '%s' "$OUTPUT" | is_auth_error; then
    echo ""
    echo "WARNING: agent review unavailable ($AGENT_PROVIDER auth error, exit $AGENT_RC)."
    print_provider_env
    echo "Deterministic fix results are still valid. Review manually:"
  elif [[ $AGENT_RC -eq 124 ]] || printf '%s' "$OUTPUT" | is_infra_error; then
    echo ""
    echo "WARNING: agent review unavailable ($AGENT_PROVIDER infra error, exit $AGENT_RC)."
    echo "Deterministic fix results are still valid. Review manually:"
  else
    echo ""
    echo "WARNING: agent review unavailable ($AGENT_PROVIDER exited $AGENT_RC — unclassified error). Review manually:"
  fi
  echo "$FIX_SUMMARY"
  exit 0
fi

# Validate structured lines before they can affect parent state. The reviewer is
# untrusted text: only outcomes for packages explicitly sent for policy review
# may affect parent state. Residuals for other packages are handled by the
# deterministic rebuild/scan-regression/final-scan gates.
EXPECTED_PKGS=$(printf '%s\n' "$PACKAGE_SUMMARY" | \
  sed -nE 's/^(NEEDS_REVIEW|ERROR|TIMEOUT): ([^ ]+).*/\2/p' | sort -u)
# Codex CLI can repeat its final answer after usage metadata. Collapse exact
# duplicate outcome lines before validation/state propagation.
RAW_SUMMARY_LINES=$(printf '%s\n' "$OUTPUT" | grep -E "^(UNRESOLVED|RESOLVED):" | awk '!seen[$0]++' || true)
SUMMARY_LINES=""
if [[ -n "$EXPECTED_PKGS" ]]; then
  if [[ -z "$RAW_SUMMARY_LINES" ]]; then
    echo "ERROR: reviewer returned no structured outcome for requested packages." >&2
    exit 1
  fi
  while IFS= read -r _summary_line; do
    _summary_pkg=$(printf '%s' "$_summary_line" | sed -nE 's/^[^:]+: ([^ ]+).*/\1/p')
    if [[ -z "$_summary_pkg" ]] || ! grep -qxF "$_summary_pkg" <<< "$EXPECTED_PKGS"; then
      echo "WARNING: ignoring out-of-scope reviewer outcome: ${_summary_pkg:-<missing>}" >&2
      continue
    fi
    if [[ "$_summary_line" =~ \ —\ reason[[:space:]]*$ || "$_summary_pkg" == "pkg.name/path" ]]; then
      echo "ERROR: reviewer returned a placeholder outcome: $_summary_line" >&2
      exit 1
    fi
    SUMMARY_LINES+="${SUMMARY_LINES:+$'\n'}$_summary_line"
  done <<< "$RAW_SUMMARY_LINES"
  while IFS= read -r _expected_pkg; do
    [[ -z "$_expected_pkg" ]] && continue
    if ! printf '%s\n' "$SUMMARY_LINES" | \
        sed -nE 's/^(UNRESOLVED|RESOLVED): ([^ ]+) —.*/\2/p' | grep -qxF "$_expected_pkg"; then
      echo "ERROR: reviewer omitted requested package: $_expected_pkg" >&2
      exit 1
    fi
  done <<< "$EXPECTED_PKGS"
fi

# Extract summary lines
echo ""
echo "=== Review Summary ==="
[[ -n "$SUMMARY_LINES" ]] && printf '%s\n' "$SUMMARY_LINES" || echo "(no structured summary from agent)"

# Write UNRESOLVED items to a result file so fix-all.sh can propagate them to
# UNSEEN_NEEDS_REVIEW. Without this, a run can exit 0 while the agent emitted
# UNRESOLVED: lines — the caller has no way to detect them from the exit code.
# RESOLVED is an informational outcome: the reviewer confirms that the
# deterministic fix plus the authoritative clean scan needs no team decision.
# Only UNRESOLVED outcomes affect PR gating.
UNRESOLVED_LINES=$(printf '%s\n' "$SUMMARY_LINES" | grep -E "^UNRESOLVED:" || true)
if [[ -n "$UNRESOLVED_LINES" ]]; then
  printf '%s\n' "$UNRESOLVED_LINES" > "${STATE_FILE}.review-unresolved"
fi
