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
# These snapshots describe the decision before any policy mutation. A parse
# failure cannot authorize a no-op; the existing writable guard reports it.
_current_entries=$(printf '%s\n' "$_current_yaml" | grype_policy_entries /dev/stdin) || _current_entries=null
_committed_entries=$(printf '%s\n' "$_committed_yaml" | grype_policy_entries /dev/stdin) || _committed_entries=null
_IGNORE_DECISIONS=$(printf '%s\n%s\n' "$_current_entries" "$_committed_entries" |
  jq -sr --arg p "$PACKAGE" --arg s "$FIX_STATE" --arg l "$LOCATION" --args '
    .[0] as $current | .[1] as $committed |
    def package_entry($v):
      .vulnerability == $v and .package == $p and (.type | IN("", "go-module"));
    def exact($entries; $v):
      any($entries[]?; package_entry($v) and .fix_state == $s and .location == $l);
    [all($ARGS.positional[]; . as $v | exact($current; $v) and exact($committed; $v)),
     # Restating an existing entry counts as an update at any state or scope.
     all($ARGS.positional[]; . as $v | any($current[]?; package_entry($v)))] | @tsv
  ' "${CVE_IDS[@]}")
read -r _all_already_present _UPDATES_EXISTING <<< "$_IGNORE_DECISIONS"

if [[ "$_all_already_present" == true ]]; then
  echo "NOTE: All entries already committed in .grype.yaml — nothing to commit"
  echo "IGNORED: ${CVE_IDS[*]} ($PACKAGE) — already ignored"
  exit 0
fi

_grype_policy_writable .grype.yaml || exit 2
_IGNORE_HEAD=$(git rev-parse --verify HEAD)
_IGNORE_REF=$(git symbolic-ref --quiet HEAD) || _IGNORE_REF=""
_IGNORE_EXISTED=false
_IGNORE_SNAPSHOT=$(mktemp "${TMPDIR:-/tmp}/cve-ignore-before.XXXXXX")
if [[ -e .grype.yaml ]]; then
  _IGNORE_EXISTED=true
  cp -p -- .grype.yaml "$_IGNORE_SNAPSHOT"
fi
_finish_ignore() {
  local status="$?"
  if [[ "$status" -ne 0 ]]; then
    if ! checkout_matches "$_IGNORE_HEAD" "$_IGNORE_REF"; then
      echo "NEEDS_REVIEW: $PACKAGE — checkout moved; preserving files/index and policy snapshot $_IGNORE_SNAPSHOT" >&2
      return "$status"
    fi
    git reset --quiet HEAD -- .grype.yaml || return "$status"
    if $_IGNORE_EXISTED; then cp -p -- "$_IGNORE_SNAPSHOT" .grype.yaml || return "$status"
    else rm -f -- .grype.yaml || return "$status"
    fi
  fi
  rm -f -- "$_IGNORE_SNAPSHOT"
  return "$status"
}
trap _finish_ignore EXIT

for CVE_ID in "${CVE_IDS[@]}"; do
  insert_grype_ignore .grype.yaml "$CVE_ID" "$PACKAGE" "$REASON" "$FIX_STATE" "$LOCATION"
done

checkout_matches "$_IGNORE_HEAD" "$_IGNORE_REF" || exit 2
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
