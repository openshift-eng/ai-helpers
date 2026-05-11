#!/usr/bin/env bash
set -euo pipefail

RELEASE_CONTROLLER="https://amd64.ocp.releases.ci.openshift.org"

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") <pr-url-or-number> <minor-version> [--repo <org/repo>]

Examples:
  $(basename "$0") 7685 4.21 --repo openshift/hypershift
  $(basename "$0") https://github.com/openshift/cluster-kube-apiserver-operator/pull/1893 4.17

Arguments:
  pr-url-or-number  GitHub PR URL or number
  minor-version     OCP minor version (e.g., 4.17, 4.21)
  --repo            Required when using a PR number instead of a full URL
EOF
  exit 1
}

die() { echo "Error: $*" >&2; exit 1; }
info() { echo "$*" >&2; }

# --- Argument parsing ---
[[ $# -lt 2 ]] && usage

PR_INPUT="$1"
MINOR="$2"
shift 2

REPO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) [[ $# -lt 2 ]] && die "--repo requires an argument"; REPO="$2"; shift 2 ;;
    *) usage ;;
  esac
done

if [[ "$PR_INPUT" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
  REPO="${BASH_REMATCH[1]}"
  PR_NUMBER="${BASH_REMATCH[2]}"
else
  PR_NUMBER="$PR_INPUT"
  [[ -z "$REPO" ]] && die "--repo is required when using a PR number"
fi

[[ "$MINOR" =~ ^4\.[0-9]+$ ]] || die "minor version must be like 4.17, got: $MINOR"

# --- Tool validation ---
for cmd in oc gh jq curl; do
  command -v "$cmd" &>/dev/null || die "$cmd is required but not found"
done

# --- Pull secret discovery ---
PULL_SECRET_PATH=""
for f in "${PULL_SECRET:-}" "$HOME/pull-secret.txt" "$HOME/pull-secret.json" "$HOME/.docker/config.json" "${XDG_RUNTIME_DIR:-}/containers/auth.json" "$HOME/.config/containers/auth.json"; do
  [[ -n "$f" ]] && [[ -f "$f" ]] && PULL_SECRET_PATH="$f" && break
done
[[ -z "$PULL_SECRET_PATH" ]] && die "No pull secret found. Set \$PULL_SECRET or place one at ~/pull-secret.txt"

# --- Step 1: PR info ---
info "Fetching PR #${PR_NUMBER} from ${REPO}..."
PR_JSON=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json mergeCommit,state,mergedAt,baseRefName,title)
PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
[[ "$PR_STATE" != "MERGED" ]] && die "PR #${PR_NUMBER} is ${PR_STATE}, not merged"

MERGE_SHA=$(echo "$PR_JSON" | jq -r '.mergeCommit.oid')
MERGED_AT=$(echo "$PR_JSON" | jq -r '.mergedAt')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
PR_BASE=$(echo "$PR_JSON" | jq -r '.baseRefName')

info "PR #${PR_NUMBER}: ${PR_TITLE}"
info "Merged: ${MERGED_AT} to ${PR_BASE} (${MERGE_SHA:0:12})"

# --- Step 2: Component mapping ---
info "Fetching release stream tags..."
TAGS_JSON=$(curl -sf "${RELEASE_CONTROLLER}/api/v1/releasestream/4-stable/tags") \
  || die "Failed to fetch release stream from ${RELEASE_CONTROLLER}"

LATEST_PULLSPEC=$(echo "$TAGS_JSON" | jq -r --arg m "${MINOR}." \
  '[.tags[] | select(.name | startswith($m))] | .[0].pullSpec')
[[ -z "$LATEST_PULLSPEC" || "$LATEST_PULLSPEC" == "null" ]] && die "No releases found for ${MINOR}"

info "Building repo-to-component mapping from ${LATEST_PULLSPEC}..."
REPO_URL="https://github.com/${REPO}"
COMPONENT=$(oc adm release info "$LATEST_PULLSPEC" -a "$PULL_SECRET_PATH" --output=json | \
  jq -r --arg repo "$REPO_URL" \
  '[.references.spec.tags[] |
    select(.annotations["io.openshift.build.source-location"] == $repo)] |
    .[0].name')
[[ -z "$COMPONENT" || "$COMPONENT" == "null" ]] && die "${REPO} is not a component in the OCP ${MINOR} payload"

info "Component: ${COMPONENT}"

# --- Step 3: Enumerate z-streams ---
ZSTREAMS=$(echo "$TAGS_JSON" | jq -c --arg m "${MINOR}." \
  '[.tags[] | select(.name | startswith($m)) | select(.phase == "Accepted")] |
   reverse | [.[] | {name: .name, pullSpec: .pullSpec}]')
ZSTREAM_COUNT=$(echo "$ZSTREAMS" | jq 'length')
[[ "$ZSTREAM_COUNT" -eq 0 ]] && die "No accepted z-streams found for ${MINOR}"

info "Found ${ZSTREAM_COUNT} accepted z-streams"

# --- Step 4: Binary search ---
check_inclusion() {
  local pullspec="$1"
  local payload_commit
  payload_commit=$(oc adm release info "$pullspec" -a "$PULL_SECRET_PATH" --output=json | \
    jq -r --arg c "$COMPONENT" \
    '.references.spec.tags[] | select(.name == $c) | .annotations["io.openshift.build.commit.id"]')

  if [[ -z "$payload_commit" || "$payload_commit" == "null" ]]; then
    echo "skip"
    return
  fi

  echo "$payload_commit"
}

compare_commits() {
  local payload_commit="$1"
  gh api "repos/${REPO}/compare/${MERGE_SHA}...${payload_commit}" --jq '.status' 2>/dev/null || echo "error"
}

lo=0
hi=$((ZSTREAM_COUNT - 1))
result_idx=-1
result_commit=""

while [[ $lo -le $hi ]]; do
  mid=$(( (lo + hi) / 2 ))
  zname=$(echo "$ZSTREAMS" | jq -r ".[$mid].name")
  zpull=$(echo "$ZSTREAMS" | jq -r ".[$mid].pullSpec")

  payload_commit=$(check_inclusion "$zpull")
  if [[ "$payload_commit" == "skip" ]]; then
    info "Checking ${zname}... component not found, skipping"
    lo=$((mid + 1))
    continue
  fi

  status=$(compare_commits "$payload_commit")
  case "$status" in
    identical|ahead)
      info "Checking ${zname}... included"
      result_idx=$mid
      result_commit="$payload_commit"
      hi=$((mid - 1))
      ;;
    behind)
      info "Checking ${zname}... not included"
      lo=$((mid + 1))
      ;;
    diverged)
      info "Checking ${zname}... diverged (commit not on release branch)"
      lo=$((mid + 1))
      ;;
    *)
      info "Checking ${zname}... error comparing commits"
      lo=$((mid + 1))
      ;;
  esac
done

# --- Step 5: Report ---
echo ""
if [[ $result_idx -lt 0 ]]; then
  echo "PR: #${PR_NUMBER} (${PR_TITLE})"
  echo "Merged: ${MERGED_AT} to ${PR_BASE}"
  echo "Component: ${COMPONENT}"
  echo "Result: NOT YET SHIPPED in any ${MINOR} z-stream"
  exit 0
fi

FIRST_ZSTREAM=$(echo "$ZSTREAMS" | jq -r ".[$result_idx].name")
info "→ First shipped in ${FIRST_ZSTREAM}"
echo ""
echo "PR: #${PR_NUMBER} (${PR_TITLE})"
echo "Merged: ${MERGED_AT} to ${PR_BASE}"
echo "Component: ${COMPONENT}"
echo "First z-stream: ${FIRST_ZSTREAM}"
echo "Payload commit: ${result_commit}"
echo "Verification: https://github.com/${REPO}/compare/${MERGE_SHA}...${result_commit}"
