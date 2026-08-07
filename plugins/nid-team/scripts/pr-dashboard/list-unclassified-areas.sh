#!/bin/bash
# Helper script for the /sync-pr-dashboard skill's AI classification step.
# Lists project board items that don't have an Area set and come from repos
# where the area is ambiguous (not in REPO_TO_AREA). For each item, fetches
# the PR's changed files so Claude can classify the area based on which
# directories and files were modified.
# Output format is structured text that Claude parses to make classification
# decisions.
set -euo pipefail

# Load shared configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Build a space-separated string of deterministic repos for Python to parse
DETERMINISTIC_REPOS=$(printf '%s ' "${!REPO_TO_AREA[@]}")

echo "Fetching project items..."
ITEMS_JSON=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500)

echo "Fetching changed files..." >&2

ITEMS=$(echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
deterministic = set('$DETERMINISTIC_REPOS'.split())
for item in data['items']:
    area = item.get('area', '')
    content = item.get('content', {})
    if content.get('type') != 'PullRequest':
        continue
    repo = content.get('repository', '')
    if not area and repo not in deterministic:
        print(f'{item[\"id\"]}|{repo}|{content[\"number\"]}|{content[\"title\"]}|{content[\"url\"]}')
")

ITEM_COUNT=$(echo "$ITEMS" | grep -c '|' || true)
echo "Found $ITEM_COUNT items needing classification"

echo "---"
echo "UNCLASSIFIED_ITEMS"
echo "---"

echo "$ITEMS" | while IFS='|' read -r item_id repo number title url; do
    [ -z "$item_id" ] && continue
    files=$(gh pr view "$number" -R "$repo" --json files -q '[.files[].path] | join(", ")' 2>/dev/null || echo "unknown")
    echo "ITEM: $item_id"
    echo "  REPO: $repo"
    echo "  PR: #$number"
    echo "  TITLE: $title"
    echo "  URL: $url"
    echo "  FILES: $files"
    echo ""
done
