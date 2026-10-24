#!/usr/bin/env bash
set -euo pipefail
# Add CVE(s) to the .grype.yaml ignore list and commit.
# Use --fix-state VALUE (or --no-fix) when ignoring because no fix is available;
# the entry auto-expires once grype's vulnerability DB shows a fix exists.
# Permanent ignores (for a verified false positive or explicit policy decision)
# require --permanent so an omitted fix-state cannot silently create one.
# Use --location PATH (grype's exact reported path, e.g. /tools/go.mod) to scope
# the ignore to one module so it can't mask the same CVE found elsewhere.
# Usage: ignore.sh STATE_FILE PACKAGE SEVERITY REASON [--no-fix|--fix-state VALUE|--permanent] [--location PATH] CVE_ID [CVE_ID...]
# Exit 0: ignored (or already ignored). Exit 1: validation error.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: ignore.sh STATE_FILE PACKAGE SEVERITY REASON [--no-fix|--fix-state VALUE|--permanent] [--location PATH] CVE_ID [CVE_ID...]}"
PACKAGE="${2:?Missing PACKAGE}"
SEVERITY="${3:?Missing SEVERITY}"
REASON="${4:?Missing REASON}"
shift 4

# Flags may appear in any order before the CVE IDs. CVE IDs start with
# CVE-/GHSA-/GO-, never "--", so the loop stops cleanly at the first CVE.
FIX_STATE=""
LOCATION=""
PERMANENT=false
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --no-fix) FIX_STATE="not-fixed"; shift ;;
    --fix-state) FIX_STATE="${2:?Missing value for --fix-state}"; shift 2 ;;
    --permanent) PERMANENT=true; shift ;;
    --location) LOCATION="${2:?Missing value for --location}"; shift 2 ;;
    *) die "Unknown flag: $1" ;;
  esac
done

if [[ "$PERMANENT" == "true" && -n "$FIX_STATE" ]]; then
  die "--permanent cannot be combined with --no-fix or --fix-state"
fi
if [[ "$PERMANENT" != "true" && -z "$FIX_STATE" ]]; then
  die "Refusing an implicit permanent ignore; use --fix-state VALUE or explicit --permanent"
fi

if [[ -n "$FIX_STATE" ]] && ! [[ "$FIX_STATE" =~ ^(not-fixed|unknown|wont-fix)$ ]]; then
  die "Invalid fix-state: $FIX_STATE (use not-fixed/unknown/wont-fix)"
fi

CVE_IDS=("$@")
[[ ${#CVE_IDS[@]} -gt 0 ]] || die "At least one CVE_ID required"

[[ "$SEVERITY" =~ ^(Critical|High|Medium|Low|Negligible|Unknown)$ ]] || \
  die "Invalid severity: $SEVERITY (use Critical/High/Medium/Low/Negligible/Unknown)"
for _cve in "${CVE_IDS[@]}"; do
  [[ "$_cve" =~ ^(CVE-|GHSA-|GO-) ]] || \
    die "Invalid CVE ID format: $_cve (must start with CVE-, GHSA-, or GO-)"
done

load_state "$STATE_FILE"
[[ -n "$LOCATION" ]] && LOCATION=$(normalize_scan_location "$LOCATION")

echo "--- Ignoring: ${CVE_IDS[*]} ($PACKAGE) [$SEVERITY] ---"

# Check whether all CVE entries are already in the working tree AND in HEAD.
# insert_grype_ignore uses remove-then-reinsert, so git diff --staged always shows
# a change even for logically identical content — the position or comment may shift.
# The two-part check (working tree + HEAD match) ensures we skip re-commits on
# repeated runs while still allowing a deterministic repair to reinsert a missing
# exact entry in the working tree even when an older commit contains that entry.
_current_yaml=$(cat .grype.yaml 2>/dev/null || true)
_committed_yaml=$(git show HEAD:.grype.yaml 2>/dev/null || true)
_all_already_present=true
_semantic_entry_present() {
  local content="$1" cve="$2"
  printf '%s\n' "$content" | grype_policy_entries /dev/stdin | jq -e \
    --arg v "$cve" --arg p "$PACKAGE" --arg s "$FIX_STATE" --arg l "$LOCATION" '
      any(.[]; .vulnerability == $v and .package == $p and .fix_state == $s and .location == $l and (.type | IN("", "go-module")))' >/dev/null

}
for _cve in "${CVE_IDS[@]}"; do
  # Identity includes fix-state and normalized module location. A CVE/package
  # match at another scope must not suppress the requested update.
  if ! _semantic_entry_present "$_current_yaml" "$_cve" || \
     ! _semantic_entry_present "$_committed_yaml" "$_cve"; then
    _all_already_present=false
    break
  fi
done

if [[ "$_all_already_present" == true ]]; then
  echo "NOTE: All entries already committed in .grype.yaml — nothing to commit"
  echo "IGNORED: ${CVE_IDS[*]} ($PACKAGE) — already ignored"
  exit 0
fi

# Entries that already exist are only rescoped or restated, not added.
_UPDATES_EXISTING=true
for CVE_ID in "${CVE_IDS[@]}"; do
  grype_ignore_entry_exists .grype.yaml "$CVE_ID" "$PACKAGE" "" ||
    grype_ignore_scoped_entry_exists .grype.yaml "$CVE_ID" "$PACKAGE" || _UPDATES_EXISTING=false
done
for CVE_ID in "${CVE_IDS[@]}"; do
  insert_grype_ignore .grype.yaml "$CVE_ID" "$PACKAGE" "$REASON" "$FIX_STATE" "$LOCATION"
done

git add .grype.yaml

# If all entries were duplicates (e.g. working tree already had them), skip commit
if git diff --staged --quiet .grype.yaml; then
  echo "NOTE: All entries already in .grype.yaml — nothing to commit"
  echo "IGNORED: ${CVE_IDS[*]} ($PACKAGE) — already ignored"
  exit 0
fi

ABBREV=$(abbreviate_package "$PACKAGE")
_SUBJECT_PACKAGE="$ABBREV"

if [[ -n "$FIX_STATE" ]]; then
  SUBJECT="Ignore $ABBREV CVEs (no fix available)"
else
  SUBJECT="Ignore $ABBREV CVEs incompatible with $BRANCH"
fi

# Preserve the existing branch-incompatible short forms before bounding the label.
if [[ ${#SUBJECT} -gt 50 ]] && [[ -z "$FIX_STATE" ]]; then
  # Only the branch-incompatible form has a documented short variant
  SUBJECT="Ignore $ABBREV CVEs ($BRANCH)"
  # If even the short form exceeds 50 chars, strip trailing major-version suffix
  # (/v2, /v3, ...) before taking the final path component — avoids non-descriptive
  # subjects like "Ignore v2 CVEs (branch)" for versioned module abbreviations.
  if [[ ${#SUBJECT} -gt 50 ]]; then
    _ABBREV_BASE="${ABBREV%/v[0-9]*}"
    SUBJECT="Ignore ${_ABBREV_BASE##*/} CVEs ($BRANCH)"
  fi
fi

if [[ "$_UPDATES_EXISTING" == true ]]; then
  SUBJECT="Update $ABBREV CVE ignores"
  REASON="$REASON

Updates the existing entries${LOCATION:+, scoped to $LOCATION,} to the fix-state
Grype reports${FIX_STATE:+ ($FIX_STATE)}."
fi

BODY="$REASON"
if [[ ${#SUBJECT} -gt 50 ]]; then
  _SUBJECT_PREFIX="Ignore "
  if [[ "$_UPDATES_EXISTING" == true ]]; then
    _SUBJECT_PREFIX="Update "; _SUBJECT_SUFFIX=" CVE ignores"
  elif [[ -n "$FIX_STATE" ]]; then
    _SUBJECT_SUFFIX=" CVEs (no fix available)"
  else
    _SUBJECT_SUFFIX=" CVEs ($BRANCH)"
  fi
  _SUBJECT_BUDGET=$((50 - ${#_SUBJECT_PREFIX} - ${#_SUBJECT_SUFFIX}))
  ABBREV=$(abbreviate_package "$PACKAGE" "$_SUBJECT_BUDGET") || die "Commit subject has no room for a package label"
  SUBJECT="$_SUBJECT_PREFIX$ABBREV$_SUBJECT_SUFFIX"
fi
if [[ "$SUBJECT" != "Ignore $_SUBJECT_PACKAGE "* && "$SUBJECT" != "Update $_SUBJECT_PACKAGE "* ]]; then
  BODY="$REASON

Full package: $PACKAGE${LOCATION:+
Module: $LOCATION}
$(format_cve_fixes "${CVE_IDS[@]}")"
fi

git commit -s -m "$(printf '%s\n\n%s' "$SUBJECT" "$BODY")"

echo "IGNORED: ${CVE_IDS[*]} ($PACKAGE) — $REASON"
