#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --repo <owner/repo> --pr <number> [--trusted-bots <bot1,bot2>] [--exclude-ids <id1,id2>]" >&2
  echo "" >&2
  echo "Fetch PR comments filtered to trusted users (org members + allowed bots)." >&2
  echo "" >&2
  echo "Options:" >&2
  echo "  --repo          GitHub repository in owner/repo format (required)" >&2
  echo "  --pr            Pull request number (required)" >&2
  echo "  --trusted-bots  Comma-separated list of trusted bot logins (default: coderabbitai)" >&2
  echo "  --exclude-ids   Comma-separated list of comment IDs to exclude" >&2
  exit 1
}

REPO=""
PR=""
TRUSTED_BOTS="coderabbitai"
EXCLUDE_IDS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)         REPO="$2"; shift 2 ;;
    --pr)           PR="$2"; shift 2 ;;
    --trusted-bots) TRUSTED_BOTS="$2"; shift 2 ;;
    --exclude-ids)  EXCLUDE_IDS="$2"; shift 2 ;;
    -h|--help)      usage ;;
    *)              echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$REPO" || -z "$PR" ]]; then
  echo '{"error": "Missing required arguments. Use --repo and --pr."}' >&2
  exit 1
fi

ORG="${REPO%%/*}"

# --- Fetch from all three endpoints ---
raw_inline=$(gh api "repos/${REPO}/pulls/${PR}/comments" --paginate 2>/dev/null || echo "[]")
raw_reviews=$(gh api "repos/${REPO}/pulls/${PR}/reviews" --paginate 2>/dev/null || echo "[]")
raw_issue_comments=$(gh api "repos/${REPO}/issues/${PR}/comments" --paginate 2>/dev/null || echo "[]")

# --- Build trusted user list ---
all_users=$(echo "${raw_inline}" "${raw_reviews}" "${raw_issue_comments}" \
  | jq -r '.[].user.login' 2>/dev/null | sort -u)

trusted_users=""
IFS=',' read -ra BOT_ARRAY <<< "$TRUSTED_BOTS"

for user in ${all_users}; do
  is_trusted=false

  for bot in "${BOT_ARRAY[@]}"; do
    if [[ "${user}" == "${bot}" || "${user}" == "${bot}[bot]" ]]; then
      is_trusted=true
      break
    fi
  done

  if [[ "$is_trusted" == "false" ]]; then
    if gh api "orgs/${ORG}/members/${user}" --silent 2>/dev/null; then
      is_trusted=true
    fi
  fi

  if [[ "$is_trusted" == "true" ]]; then
    trusted_users="${trusted_users} ${user}"
  fi
done

# --- Filter to trusted users ---
trusted_jq_filter=$(echo "${trusted_users}" | xargs -n1 2>/dev/null | jq -R . | jq -s '.' 2>/dev/null || echo '[]')

inline_filtered=$(echo "${raw_inline}" | jq --argjson trusted "${trusted_jq_filter}" \
  '[.[] | select(.user.login as $u | $trusted | index($u))]')
reviews_filtered=$(echo "${raw_reviews}" | jq --argjson trusted "${trusted_jq_filter}" \
  '[.[] | select(.user.login as $u | $trusted | index($u))]')
issue_comments_filtered=$(echo "${raw_issue_comments}" | jq --argjson trusted "${trusted_jq_filter}" \
  '[.[] | select(.user.login as $u | $trusted | index($u))]')

# --- Exclude already-processed IDs ---
if [[ -n "${EXCLUDE_IDS}" ]]; then
  exclude_jq_filter=$(echo "${EXCLUDE_IDS}" | tr ',' '\n' | jq -R . | jq -s '.')
  inline_filtered=$(echo "${inline_filtered}" | jq --argjson seen "${exclude_jq_filter}" \
    '[.[] | select((.id | tostring) as $id | $seen | index($id) | not)]')
  reviews_filtered=$(echo "${reviews_filtered}" | jq --argjson seen "${exclude_jq_filter}" \
    '[.[] | select((.id | tostring) as $id | $seen | index($id) | not)]')
  issue_comments_filtered=$(echo "${issue_comments_filtered}" | jq --argjson seen "${exclude_jq_filter}" \
    '[.[] | select((.id | tostring) as $id | $seen | index($id) | not)]')
fi

# --- Filter out APPROVED/PENDING reviews ---
reviews_filtered=$(echo "${reviews_filtered}" | jq '[.[] | select(.state != "APPROVED" and .state != "PENDING")]')

# --- Extract slim comment objects ---
inline_slim=$(echo "${inline_filtered}" | jq '[.[] | {id: (.id | tostring), user: .user.login, path: (.path // "general"), body: .body}]')
reviews_slim=$(echo "${reviews_filtered}" | jq '[.[] | {id: (.id | tostring), user: .user.login, state: .state, body: .body}]')
issue_comments_slim=$(echo "${issue_comments_filtered}" | jq '[.[] | {id: (.id | tostring), user: .user.login, body: .body}]')

# --- Collect all IDs ---
all_ids=$(echo "${inline_slim} ${reviews_slim} ${issue_comments_slim}" | jq -s 'map(.[].id) | unique')

# --- Counts ---
inline_count=$(echo "${inline_slim}" | jq 'length')
review_count=$(echo "${reviews_slim}" | jq 'length')
issue_comment_count=$(echo "${issue_comments_slim}" | jq 'length')
total=$(( inline_count + review_count + issue_comment_count ))

# --- Formatted text for prompts ---
fmt_inline=$(echo "${inline_slim}" | jq -r '.[] | "**\(.user)** on `\(.path)`:\n\(.body)\n---"' 2>/dev/null || echo "")
fmt_reviews=$(echo "${reviews_slim}" | jq -r '.[] | "**\(.user)** (\(.state)):\n\(.body)\n---"' 2>/dev/null || echo "")
fmt_issue_comments=$(echo "${issue_comments_slim}" | jq -r '.[] | "**\(.user)**:\n\(.body)\n---"' 2>/dev/null || echo "")

# --- Output ---
jq -n \
  --argjson inline_comments "${inline_slim}" \
  --argjson reviews "${reviews_slim}" \
  --argjson issue_comments "${issue_comments_slim}" \
  --argjson all_ids "${all_ids}" \
  --arg total "${total}" \
  --arg fmt_inline "${fmt_inline}" \
  --arg fmt_reviews "${fmt_reviews}" \
  --arg fmt_issue_comments "${fmt_issue_comments}" \
  '{
    inline_comments: $inline_comments,
    reviews: $reviews,
    issue_comments: $issue_comments,
    all_ids: $all_ids,
    total: ($total | tonumber),
    formatted: {
      inline: $fmt_inline,
      reviews: $fmt_reviews,
      issue_comments: $fmt_issue_comments
    }
  }'
