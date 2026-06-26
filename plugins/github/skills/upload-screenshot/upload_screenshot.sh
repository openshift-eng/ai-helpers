#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --file <path> --repo <owner/repo> [--title <title>] [--token-file <path>]" >&2
  echo "" >&2
  echo "Upload an image to GitHub as a release asset and return the URL." >&2
  echo "" >&2
  echo "Options:" >&2
  echo "  --file        Path to the image file (required)" >&2
  echo "  --repo        GitHub repository in owner/repo format (required)" >&2
  echo "  --title       Alt text / title for the image (default: filename)" >&2
  echo "  --token-file  Path to a file containing a GitHub token to use for auth" >&2
  exit 1
}

FILE=""
REPO=""
TITLE=""
TOKEN_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)       FILE="$2"; shift 2 ;;
    --repo)       REPO="$2"; shift 2 ;;
    --title)      TITLE="$2"; shift 2 ;;
    --token-file) TOKEN_FILE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$FILE" || -z "$REPO" ]]; then
  echo '{"error": "Missing required arguments. Use --file and --repo."}' >&2
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "{\"error\": \"File not found: $FILE\"}" >&2
  exit 1
fi

FILENAME=$(basename "$FILE")
if [[ -z "$TITLE" ]]; then
  TITLE="$FILENAME"
fi

if [[ -n "$TOKEN_FILE" ]]; then
  if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "{\"error\": \"Token file not found: $TOKEN_FILE\"}" >&2
    exit 1
  fi
  export GITHUB_TOKEN
  GITHUB_TOKEN=$(cat "$TOKEN_FILE")
fi

TAG="screenshot-$(date +%s)-$(head -c 4 /dev/urandom | xxd -p)"

if ! gh release create "$TAG" "$FILE" \
  --repo "$REPO" \
  --title "Screenshot: $TITLE" \
  --notes "Automated screenshot upload. Safe to delete." \
  --prerelease > /dev/null 2>&1; then
  echo '{"error": "Failed to create release. Check gh auth and repo permissions."}' >&2
  exit 1
fi

URL=$(gh api "repos/$REPO/releases/tags/$TAG" --jq '.assets[0].browser_download_url' 2>/dev/null)

if [[ -z "$URL" || "$URL" == "null" ]]; then
  gh release delete "$TAG" --yes --cleanup-tag --repo "$REPO" > /dev/null 2>&1 || true
  echo '{"error": "Release created but failed to retrieve asset URL."}' >&2
  exit 1
fi

cat <<EOF
{"url": "$URL", "markdown": "![${TITLE}](${URL})", "tag": "$TAG", "repo": "$REPO"}
EOF
