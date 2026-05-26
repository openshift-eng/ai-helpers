#!/usr/bin/env bash
# Remove collected data artifacts but preserve reports.
# Usage: cleanup.sh [artifacts-dir]

set -euo pipefail

DIR="${1:-.work/activity-type-classifier}"

if [[ ! -d "$DIR" ]]; then
  echo "Directory not found: $DIR"
  exit 1
fi

REMOVED=0

for FILE in "$DIR"/issues.json "$DIR"/classifications.json; do
  if [[ -f "$FILE" ]]; then
    rm "$FILE"
    echo "Removed: $FILE"
    REMOVED=$((REMOVED + 1))
  fi
done

if [[ $REMOVED -eq 0 ]]; then
  echo "Nothing to clean up"
else
  echo "Cleaned up $REMOVED file(s). Reports preserved."
fi
