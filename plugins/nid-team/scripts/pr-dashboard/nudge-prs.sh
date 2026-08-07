#!/bin/bash
# Sends reminder comments on high-priority assigned PRs that have gone inactive.
# Determines who is blocking (author vs reviewer) based on the last human activity,
# excluding bot activity and mechanical Prow commands (/assign, /label, etc.).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Defaults
DAYS_THRESHOLD=7
DRY_RUN=false
PRIORITIES="High,Urgent"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --days) DAYS_THRESHOLD="$2"; shift 2 ;;
        --dryrun) DRY_RUN=true; shift ;;
        --priority) PRIORITIES="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

echo "=== NID PR Nudge ==="
echo "  Threshold: ${DAYS_THRESHOLD} days of inactivity"
echo "  Priorities: ${PRIORITIES}"
echo "  Dry run: ${DRY_RUN}"
echo ""

# Fetch project items
echo "Fetching project items..."
ITEMS_JSON=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500)

# Build nudge list
NUDGE_FILE=$(mktemp)
echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
priorities = set('$PRIORITIES'.split(','))
for item in data['items']:
    content = item.get('content', {})
    if content.get('type') != 'PullRequest':
        continue
    if item.get('status', '') != 'Assigned':
        continue
    if item.get('pR Priority', '') not in priorities:
        continue
    primary = item.get('primary Reviewer', '')
    secondary = item.get('secondary Reviewer', '')
    repo = content['repository']
    number = content['number']
    url = content['url']
    priority = item.get('pR Priority', '')
    labels = ','.join(item.get('labels', []))
    print(f'{repo}|{number}|{url}|{priority}|{primary}|{secondary}|{labels}')
" > "$NUDGE_FILE"

TOTAL=$(wc -l < "$NUDGE_FILE" | tr -d ' ')
echo "Found $TOTAL assigned High/Urgent PRs"
echo ""

NUDGED=0
SKIPPED=0

while IFS='|' read -r repo number url priority primary secondary labels; do
    [ -z "$repo" ] && continue

    # Get PR details
    pr_json=$(gh pr view "$number" -R "$repo" --json createdAt,commits,reviews,comments,labels,author 2>/dev/null || echo "{}")
    if [ "$pr_json" = "{}" ]; then
        continue
    fi

    # Extract activity and build comment via Python
    result=$(echo "$pr_json" | python3 -c "
import json, sys
from datetime import datetime, timezone

BOT_LOGINS = {'coderabbitai', 'openshift-bot', 'openshift-cherrypick-robot', 'openshift-ci',
              'openshift-ci-robot', 'github-actions', 'ocp-sustaining-admins'}
# Prow commands are mechanical, not real engagement
PROW_COMMANDS = {'/assign', '/unassign', '/label', '/remove-label', '/hold', '/unhold',
                 '/lgtm', '/approve', '/retest', '/test', '/cc', '/uncc'}

def is_bot(login):
    return login in BOT_LOGINS or '[bot]' in login or login.startswith('app/')

def is_prow_command(body):
    stripped = body.strip().split('\n')[0].strip()
    return any(stripped.startswith(cmd) for cmd in PROW_COMMANDS)

pr = json.load(sys.stdin)
now = datetime.now(timezone.utc)
created = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
age_days = (now - created).days
author = pr.get('author', {}).get('login', '')
author_is_bot = is_bot(author)

activities = []

# Last commit
if pr.get('commits'):
    commit_date = datetime.fromisoformat(pr['commits'][-1]['committedDate'].replace('Z', '+00:00'))
    if not is_bot(author):
        activities.append(('pushed commits', author, commit_date))

# Reviews (exclude bots)
for review in pr.get('reviews', []):
    who = review.get('author', {}).get('login', '')
    if is_bot(who): continue
    when = datetime.fromisoformat(review['submittedAt'].replace('Z', '+00:00'))
    activities.append(('reviewed', who, when))

# Comments (exclude bots and prow commands)
for comment in pr.get('comments', []):
    who = comment.get('author', {}).get('login', '')
    if is_bot(who): continue
    body = comment.get('body', '')
    if is_prow_command(body): continue
    when = datetime.fromisoformat(comment['createdAt'].replace('Z', '+00:00'))
    activities.append(('commented', who, when))

if not activities:
    days_inactive = age_days
    last_info = 'none'
    last_who = ''
else:
    activities.sort(key=lambda x: x[2], reverse=True)
    last_type, last_who, last_when = activities[0]
    days_inactive = (now - last_when).days
    last_info = f'{last_when.strftime(\"%b %-d\")} ({days_inactive} days ago, @{last_who} {last_type})'

threshold = int('$DAYS_THRESHOLD')
if days_inactive < threshold:
    print('SKIP')
    sys.exit(0)

pr_labels = [l['name'] for l in pr.get('labels', [])]
needs_rebase = 'needs-rebase' in pr_labels
has_hold = 'do-not-merge/hold' in pr_labels
has_lgtm = 'lgtm' in pr_labels
has_approved = 'approved' in pr_labels

if author_is_bot:
    waiting_on = 'reviewer'
    reason = f'bot PR, last human activity was {days_inactive} days ago' if last_who else 'bot PR with no human review activity'
elif needs_rebase:
    waiting_on = 'author'
    reason = 'needs-rebase'
elif last_who and (last_who == author or last_type == 'pushed commits'):
    waiting_on = 'reviewer'
    reason = f'author pushed/commented {days_inactive} days ago with no review since'
elif last_who:
    waiting_on = 'author'
    reason = f'reviewer commented {days_inactive} days ago with no author response'
else:
    waiting_on = 'reviewer'
    reason = f'no human activity since PR opened {age_days} days ago'

print(f'NUDGE|{age_days}|{created.strftime(\"%b %-d\")}|{days_inactive}|{last_info}|{waiting_on}|{reason}|{author}|{int(needs_rebase)}|{int(has_hold)}|{int(has_lgtm)}|{int(has_approved)}')
" 2>/dev/null || echo "SKIP")

    if [ "$result" = "SKIP" ] || [ -z "$result" ]; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    IFS='|' read -r _ age_days created_str days_inactive last_info waiting_on reason pr_author needs_rebase has_hold has_lgtm has_approved <<< "$result"

    primary_login="${FULLNAME_TO_USERNAME[$primary]:-$primary}"
    secondary_login=""
    if [ -n "$secondary" ] && [ "$secondary" != "Other" ]; then
        secondary_login="${FULLNAME_TO_USERNAME[$secondary]:-$secondary}"
    fi

    # Build comment
    comment="🔔 Automated NID PR Reminder — $priority Priority

• Open for: $age_days days (since $created_str)"

    if [ -n "$primary" ] && [ "$primary" != "Other" ]; then
        comment="$comment
• Primary Reviewer: @$primary_login"
    fi
    if [ -n "$secondary_login" ]; then
        comment="$comment
• Secondary Reviewer: @$secondary_login"
    fi

    comment="$comment
• Last human activity: $last_info"

    if [ "$waiting_on" = "reviewer" ]; then
        reviewers="@$primary_login"
        if [ -n "$secondary_login" ]; then
            reviewers="$reviewers, @$secondary_login"
        fi
        comment="$comment
• Waiting on: Reviewers ($reviewers) — $reason"
    else
        comment="$comment
• Waiting on: Author (@$pr_author) — $reason"
    fi

    if [ "$needs_rebase" = "1" ]; then
        comment="$comment
• ⚠️ needs-rebase"
    fi
    if [ "$has_hold" = "1" ]; then
        comment="$comment
• ⚠️ do-not-merge/hold"
    fi

    if [ "$has_lgtm" = "0" ] && [ "$has_approved" = "0" ]; then
        comment="$comment

No lgtm or approved labels yet."
    elif [ "$has_lgtm" = "1" ] && [ "$has_approved" = "0" ]; then
        comment="$comment

Has lgtm, waiting on approved."
    fi

    comment="$comment

---
_This is an experimental automated reminder. Contact @gcs278 if there are any issues._"

    NUDGED=$((NUDGED + 1))

    if [ "$DRY_RUN" = "true" ]; then
        echo "======================================================================"
        echo "[$priority] $url"
        echo ""
        echo "$comment"
        echo ""
    else
        echo "  NUDGE: $repo#$number → $waiting_on ($reason)"
        gh pr comment "$url" --body "$comment"
    fi

done < "$NUDGE_FILE"

rm -f "$NUDGE_FILE"

echo ""
echo "=== Nudge Complete ==="
echo "  Reminded: $NUDGED"
echo "  Skipped (active): $SKIPPED"
