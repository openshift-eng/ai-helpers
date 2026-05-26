#!/usr/bin/env bash
# Validate a classifications.json file for activity type correctness.
# Usage: validate-classifications.sh <classifications.json>

set -euo pipefail

FILE="${1:?Usage: validate-classifications.sh <classifications.json>}"

if [[ ! -f "$FILE" ]]; then
  echo "FAIL: File not found: $FILE"
  exit 1
fi

if ! jq empty "$FILE" 2>/dev/null; then
  echo "FAIL: Invalid JSON in $FILE"
  exit 1
fi

VALID_TYPES=(
  "Associate Wellness & Development"
  "Incidents & Support"
  "Security & Compliance"
  "Quality / Stability / Reliability"
  "Future Sustainability"
  "Product / Portfolio Work"
)

ERRORS=0
TOTAL=$(jq 'length' "$FILE")

# Check required fields
MISSING_FIELDS=$(jq -r '[.[] | select(.key == null or .activityType == null or .confidence == null or .reasoning == null) | .key // "UNKNOWN"] | join(", ")' "$FILE")
if [[ -n "$MISSING_FIELDS" ]]; then
  echo "FAIL: Missing required fields in entries: $MISSING_FIELDS"
  ERRORS=$((ERRORS + 1))
fi

# Check valid activity type values
VALID_REGEX=$(printf '%s\n' "${VALID_TYPES[@]}" | jq -R . | jq -s .)
INVALID=$(jq -r --argjson valid "$VALID_REGEX" '[.[] | select(.activityType as $at | $valid | index($at) | not) | "\(.key): \(.activityType)"] | join("\n")' "$FILE")
if [[ -n "$INVALID" ]]; then
  echo "FAIL: Invalid activity type values:"
  echo "$INVALID"
  ERRORS=$((ERRORS + 1))
fi

# Check for duplicate keys
DUPES=$(jq -r '[.[] | .key] | group_by(.) | map(select(length > 1) | .[0]) | join(", ")' "$FILE")
if [[ -n "$DUPES" ]]; then
  echo "FAIL: Duplicate issue keys: $DUPES"
  ERRORS=$((ERRORS + 1))
fi

if [[ $ERRORS -gt 0 ]]; then
  echo ""
  echo "FAIL: $ERRORS validation error(s) found in $TOTAL entries"
  exit 1
fi

# Print summary
echo "PASS: All $TOTAL classifications are valid"
echo ""
echo "Distribution:"
for TYPE in "${VALID_TYPES[@]}"; do
  COUNT=$(jq --arg t "$TYPE" '[.[] | select(.activityType == $t)] | length' "$FILE")
  echo "  $TYPE: $COUNT"
done
