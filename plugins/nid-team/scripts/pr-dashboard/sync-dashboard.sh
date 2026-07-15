#!/bin/bash
set -euo pipefail

# --- Preflight checks ---
echo "Running preflight checks..."

if ! command -v gh &>/dev/null; then
    echo "ERROR: gh CLI not found. Install from https://cli.github.com/" >&2
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR: gh is not authenticated. Run: gh auth login" >&2
    exit 1
fi

RATE_JSON=$(gh api /rate_limit 2>/dev/null || echo '{}')
GRAPHQL_REMAINING=$(echo "$RATE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('resources',{}).get('graphql',{}).get('remaining',0))" 2>/dev/null || echo "0")
if [ "$GRAPHQL_REMAINING" -lt 300 ]; then
    RESET_TIME=$(echo "$RATE_JSON" | python3 -c "
import json,sys,datetime
reset = json.load(sys.stdin).get('resources',{}).get('graphql',{}).get('reset',0)
dt = datetime.datetime.fromtimestamp(reset)
print(dt.strftime('%H:%M:%S'))
" 2>/dev/null || echo "unknown")
    echo "ERROR: GitHub GraphQL rate limit too low ($GRAPHQL_REMAINING remaining, need 300+). Resets at $RESET_TIME" >&2
    exit 1
fi
echo "  GraphQL rate limit: $GRAPHQL_REMAINING remaining"

if ! command -v acli &>/dev/null; then
    echo "ERROR: acli not found. Sustaining PR detection will not work." >&2
    exit 1
fi

if ! acli jira workitem view OCPBUGS-86709 --fields labels --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('key')" &>/dev/null; then
    echo "ERROR: acli jira access failed. Make sure you have access to OCPBUGS project." >&2
    exit 1
fi

echo "Preflight checks passed."
echo ""

# Load shared configuration (team members, project IDs, repo maps)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

echo "=== NI&D Dashboard Sync ==="
echo ""

# Fetch all project items
echo "Fetching project items..."
ITEMS_JSON=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500)
ITEM_COUNT=$(echo "$ITEMS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['items']))")
echo "Found $ITEM_COUNT items"
echo ""

# --- Operation A: Populate PR Author ---
# GitHub Projects doesn't have a built-in Author column, so we use a free-text
# field and populate it with display names from the team map (or raw login).
echo "--- Operation A: Populate PR Author ---"

echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    pr_author = item.get('pR Author', '')
    if not pr_author and item.get('content', {}).get('type') == 'PullRequest':
        repo = item['content']['repository']
        number = item['content']['number']
        item_id = item['id']
        print(f'{item_id}\t{repo}\t{number}')
" | while IFS=$'\t' read -r item_id repo number; do
    author=$(gh pr view "$number" -R "$repo" --json author -q '.author.login' 2>/dev/null || echo "")
    if [ -z "$author" ]; then
        echo "  SKIP: Could not get author for $repo#$number"
        continue
    fi
    display="${USERNAME_TO_DISPLAY[$author]:-$author}"
    echo "  SET: $repo#$number → $display"
    if ! gh project item-edit \
        --project-id "$PROJECT_ID" \
        --id "$item_id" \
        --field-id "$FIELD_PR_AUTHOR" \
        --text "$display"; then
        echo "  ERROR: failed to set PR Author for $repo#$number" >&2
    fi
done

echo ""

# --- Operation B: Sync Reviewers → GitHub Assignees ---
# We can't modify PR assignees via the API (org permissions), so this syncs by
# commenting /assign on the PR. The Primary/Secondary Reviewer columns on the
# dashboard make reviewer assignments visible at a glance without changing how
# we assign today — just set the reviewer on the board and the script handles the rest.
echo "--- Operation B: Sync Reviewers → Assignees ---"

# Sync Primary and Secondary Reviewer to GitHub assignees.
# "Other" means a non-team reviewer is handling it — skip the /assign.
echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    if item.get('content', {}).get('type') != 'PullRequest':
        continue
    url = item['content']['url']
    repo = item['content']['repository']
    number = item['content']['number']
    assignees = ','.join(item.get('assignees', []))
    item_id = item['id']
    status = item.get('status', '')
    jira_pri = item.get('jira Priority', '')
    pr_pri = item.get('pR Priority', '')
    primary = item.get('primary Reviewer', '')
    secondary = item.get('secondary Reviewer', '')
    if primary:
        print(f'{primary}|{url}|{repo}|{number}|{assignees}|{item_id}|{status}|{jira_pri}|{pr_pri}')
    if secondary and secondary != primary and secondary != 'Other':
        print(f'{secondary}|{url}|{repo}|{number}|{assignees}|{item_id}|{status}|{jira_pri}|{pr_pri}')
" | while IFS='|' read -r reviewer url repo number assignees item_id status jira_pri pr_pri; do
    # "Other" means a non-team reviewer — set status to Assigned but skip /assign
    if [ "$reviewer" = "Other" ]; then
        if [ "$status" = "New" ]; then
            gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
                --field-id "$FIELD_STATUS" --single-select-option-id "$STATUS_ASSIGNED" 2>/dev/null
            echo "  STATUS: $repo#$number → Assigned (Other reviewer)"
            # Copy Jira Priority → PR Priority if not set
            if [ -z "$pr_pri" ] && [ -n "$jira_pri" ]; then
                pri_option_id=""
                case "$jira_pri" in
                    Urgent) pri_option_id="$PR_PRIORITY_URGENT" ;;
                    High)   pri_option_id="$PR_PRIORITY_HIGH" ;;
                    Medium) pri_option_id="$PR_PRIORITY_MEDIUM" ;;
                    Low)    pri_option_id="$PR_PRIORITY_LOW" ;;
                esac
                if [ -n "$pri_option_id" ]; then
                    gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
                        --field-id "$FIELD_PR_PRIORITY" --single-select-option-id "$pri_option_id" 2>/dev/null
                    echo "  PR PRIORITY: $repo#$number → $jira_pri (from Jira)"
                fi
            fi
        fi
        continue
    fi

    login="${FULLNAME_TO_USERNAME[$reviewer]:-}"
    if [ -z "$login" ]; then
        echo "  SKIP: Unknown reviewer name '$reviewer' on $repo#$number"
        continue
    fi
    if [[ ",$assignees," == *",$login,"* ]]; then
        echo "  OK: $repo#$number already assigned to $login"
        # Still set status to Assigned if it's New
        if [ "$status" = "New" ]; then
            gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
                --field-id "$FIELD_STATUS" --single-select-option-id "$STATUS_ASSIGNED" 2>/dev/null
        fi
        continue
    fi
    echo "  ASSIGN: $repo#$number → $login ($reviewer)"
    if ! gh pr comment "$url" --body "/assign @$login"; then
        echo "  ERROR: failed to assign $login on $repo#$number" >&2
    fi
    # Set status to Assigned
    if [ "$status" = "New" ]; then
        gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
            --field-id "$FIELD_STATUS" --single-select-option-id "$STATUS_ASSIGNED" 2>/dev/null
        echo "  STATUS: $repo#$number → Assigned"
    fi
    # Copy Jira Priority → PR Priority if PR Priority is not set
    if [ -z "$pr_pri" ] && [ -n "$jira_pri" ]; then
        pri_option_id=""
        case "$jira_pri" in
            Urgent) pri_option_id="$PR_PRIORITY_URGENT" ;;
            High)   pri_option_id="$PR_PRIORITY_HIGH" ;;
            Medium) pri_option_id="$PR_PRIORITY_MEDIUM" ;;
            Low)    pri_option_id="$PR_PRIORITY_LOW" ;;
        esac
        if [ -n "$pri_option_id" ]; then
            gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
                --field-id "$FIELD_PR_PRIORITY" --single-select-option-id "$pri_option_id" 2>/dev/null
            echo "  PR PRIORITY: $repo#$number → $jira_pri (from Jira)"
        fi
    fi
done

echo ""

# --- Operation C: Add shared repo PRs from team members ---
# GitHub Projects auto-add workflows can't filter by PR author, so we can't
# auto-add from shared repos (api, release, origin, etc.) without picking up
# every other team's PRs too. This manually fetches team-authored PRs only.
echo "--- Operation C: Add shared repo team PRs ---"

EXISTING_URLS=$(echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    url = item.get('content', {}).get('url', '')
    if url:
        print(url)
")

SHARED_ADDED=0

for repo in "${SHARED_REPOS[@]}"; do
    for member in "${TEAM_USERNAMES[@]}"; do
        urls=$(gh pr list --repo "$repo" --state open --search "author:$member" --json url -q '.[].url' 2>/dev/null || echo "")
        for url in $urls; do
            if echo "$EXISTING_URLS" | grep -qFx "$url"; then
                continue
            fi
            echo "  ADD: $url (by $member)"
            if ! gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url"; then
                echo "  ERROR: failed to add $url" >&2
                continue
            fi
            EXISTING_URLS="$EXISTING_URLS
$url"
            SHARED_ADDED=$((SHARED_ADDED + 1))
        done
    done
done

echo ""

# --- Operation F: Add docs PRs linked to team's Jira issues ---
# Docs PRs are written by the docs team, not us, but we need to review them.
# We can't filter openshift-docs PRs by author (they're not our team) or by
# file path (too expensive). Instead, we query Jira for issues with our
# components, then search openshift-docs for PRs matching those issue keys.
# We search both OSDOCS (docs-specific issues) and OCPBUGS (bugs that have
# docs PRs filed under "Documentation / Network Edge").
echo "--- Operation F: Add docs PRs from Jira issues ---"

DOCS_ADDED=0

# Search OSDOCS with "Network Edge" component
OSDOCS_KEYS=$(acli jira workitem search --jql 'project = OSDOCS AND component = "Network Edge" AND status NOT IN (Closed, "Release Pending")' --fields "key" --csv --limit 100 2>/dev/null | tail -n +2 | cut -d',' -f1)
OSDOCS_COUNT=$(echo "$OSDOCS_KEYS" | grep -c "OSDOCS" || true)

# Search OCPBUGS with "Documentation / Network Edge" component
OCPBUGS_DOCS_KEYS=$(acli jira workitem search --jql 'project = OCPBUGS AND component = "Documentation / Network Edge" AND status NOT IN (Closed, "Release Pending")' --fields "key" --csv --limit 100 2>/dev/null | tail -n +2 | cut -d',' -f1)
OCPBUGS_DOCS_COUNT=$(echo "$OCPBUGS_DOCS_KEYS" | grep -c "OCPBUGS" || true)

ALL_DOCS_KEYS="$OSDOCS_KEYS $OCPBUGS_DOCS_KEYS"
echo "  Found $OSDOCS_COUNT OSDOCS + $OCPBUGS_DOCS_COUNT OCPBUGS docs issues"

for key in $ALL_DOCS_KEYS; do
    [ -z "$key" ] && continue
    urls=$(gh pr list -R openshift/openshift-docs --state open --search "\"$key\" in:title" --json url,title -q '.[] | .url + "|" + .title' 2>/dev/null || true)
    while IFS='|' read -r url pr_title; do
        [ -z "$url" ] && continue
        if ! echo "$pr_title" | grep -qF "$key"; then
            continue
        fi
        if echo "$EXISTING_URLS" | grep -qFx "$url"; then
            continue
        fi
        echo "  ADD: $url ($key)"
        if ! gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url"; then
            echo "  ERROR: failed to add $url" >&2
            continue
        fi
        EXISTING_URLS="$EXISTING_URLS
$url"
        DOCS_ADDED=$((DOCS_ADDED + 1))
    done <<< "$urls"
done

echo ""

# Re-fetch items if we added new ones
if [ "$SHARED_ADDED" -gt 0 ] || [ "$DOCS_ADDED" -gt 0 ]; then
    echo "Re-fetching project items after additions..."
    ITEMS_JSON=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 500)
    ITEM_COUNT=$(echo "$ITEMS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['items']))")
    echo "Now $ITEM_COUNT items"
    echo ""
fi

# --- Operation D: Set Area for deterministic repos ---
# Area represents which sub-area of the team owns a PR: GWAPI, Router, DNS,
# ExDNS, ALBO, or Misc. Some repos map 1:1 to an area (e.g.,
# external-dns-operator is always "ExDNS"). Those are set here.
# Ambiguous repos like cluster-ingress-operator (could be Router or GWAPI)
# are left for AI classification in the skill's Step 2.
echo "--- Operation D: Set Area (repo-based) ---"

echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    area = item.get('area', '')
    if not area and item.get('content', {}).get('type') == 'PullRequest':
        repo = item['content']['repository']
        item_id = item['id']
        number = item['content']['number']
        print(f'{item_id}\t{repo}\t{number}')
" | while IFS=$'\t' read -r item_id repo number; do
    area_id="${REPO_TO_AREA[$repo]:-}"
    if [ -z "$area_id" ]; then
        continue
    fi
    area_name=$(case "$area_id" in
        "$AREA_EXTERNAL_DNS") echo "ExDNS" ;;
        "$AREA_ALBO") echo "ALBO" ;;
        "$AREA_DNS") echo "DNS" ;;
        "$AREA_AI") echo "AI" ;;
        "$AREA_ROUTER") echo "Router" ;;
        "$AREA_GWAPI") echo "GWAPI" ;;
        *) echo "unknown" ;;
    esac)
    echo "  SET: $repo#$number → area $area_name"
    if ! gh project item-edit \
        --project-id "$PROJECT_ID" \
        --id "$item_id" \
        --field-id "$FIELD_AREA" \
        --single-select-option-id "$area_id"; then
        echo "  ERROR: failed to set area for $repo#$number" >&2
    fi
done

echo ""

# --- Operation E: Set Author Type ---
# Author Type categorizes who opened the PR: Team, External, Bot, Sustaining,
# or Docs. This lets us slice the dashboard by author type during triage —
# e.g., review all team PRs first, then external, then bots. Sustaining is
# detected by checking if the linked OCPBUGS issue has the "ocp-sustaining"
# label in Jira. Docs is set for openshift-docs PRs.
echo "--- Operation E: Set Author Type ---"

# Write untyped items to a temp file to avoid subshell issues with pipes
UNTYPED_FILE=$(mktemp)
echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    author_type = item.get('author Type', '')
    if not author_type and item.get('content', {}).get('type') == 'PullRequest':
        pr_author = item.get('pR Author', '')
        repo = item['content']['repository']
        number = item['content']['number']
        title = item['content'].get('title', '')
        item_id = item['id']
        print(f'{item_id}|{repo}|{number}|{pr_author}|{title}')
" > "$UNTYPED_FILE"

echo "  Found $(wc -l < "$UNTYPED_FILE") items to classify"

while IFS='|' read -r item_id repo number pr_author title; do
    [ -z "$item_id" ] && continue

    # Determine author login - if PR Author is empty, fetch from GitHub
    author_login=""
    if [ -n "$pr_author" ]; then
        for login in "${!USERNAME_TO_DISPLAY[@]}"; do
            if [ "${USERNAME_TO_DISPLAY[$login]}" = "$pr_author" ]; then
                author_login="$login"
                break
            fi
        done
        # If no match in display names, pr_author might be the raw login
        if [ -z "$author_login" ]; then
            author_login="$pr_author"
        fi
    else
        # PR Author not cached yet, fetch directly
        author_login=$(gh pr view "$number" -R "$repo" --json author -q '.author.login' 2>/dev/null || echo "")
    fi

    # Classify
    type_id=""
    type_name=""

    # Check if it's a docs PR
    if [ "$repo" = "openshift/openshift-docs" ]; then
        type_id="$AUTHOR_TYPE_DOCS"
        type_name="Docs"
    fi

    # Check if it's a team member
    if [ -z "$type_id" ]; then
        for member in "${TEAM_USERNAMES[@]}"; do
            if [ "$author_login" = "$member" ]; then
                type_id="$AUTHOR_TYPE_TEAM"
                type_name="Team"
                break
            fi
        done
    fi

    # Check if it's a bot
    if [ -z "$type_id" ]; then
        # GitHub Apps start with "app/"
        if [[ "$author_login" == app/* ]]; then
            type_id="$AUTHOR_TYPE_BOT"
            type_name="Bot"
        fi
        # Known bot logins
        for bot in $BOT_USERNAMES; do
            if [ "$author_login" = "$bot" ]; then
                type_id="$AUTHOR_TYPE_BOT"
                type_name="Bot"
                break
            fi
        done
    fi

    # Check if it's a sustaining PR (OCPBUGS with ocp-sustaining label in Jira)
    if [ -z "$type_id" ]; then
        ocpbugs_id=$(echo "$title" | grep -oE 'OCPBUGS-[0-9]+' | head -1 || true)
        if [ -n "$ocpbugs_id" ]; then
            has_sustaining=$(acli jira workitem view "$ocpbugs_id" --fields labels --json 2>/dev/null \
                | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if 'ocp-sustaining' in d.get('fields',{}).get('labels',[]) else 'no')" 2>/dev/null || echo "no")
            if [ "$has_sustaining" = "yes" ]; then
                type_id="$AUTHOR_TYPE_SUSTAINING"
                type_name="Sustaining"
            fi
        fi
    fi

    # Default to External
    if [ -z "$type_id" ]; then
        type_id="$AUTHOR_TYPE_EXTERNAL"
        type_name="External"
    fi

    echo "  SET: $repo#$number ($pr_author) → $type_name"
    if ! gh project item-edit \
        --project-id "$PROJECT_ID" \
        --id "$item_id" \
        --field-id "$FIELD_AUTHOR_TYPE" \
        --single-select-option-id "$type_id"; then
        echo "  ERROR: failed to set author type for $repo#$number" >&2
    fi
done < "$UNTYPED_FILE"

rm -f "$UNTYPED_FILE"

echo ""

# --- Operation G: Set Jira Priority from linked issues ---
# Determines priority from linked Jira issues:
# - OCPBUGS: use bug priority (Critical→Urgent, Major→High, Normal→Medium, Minor→Low)
# - CVE/Vulnerability: floor at High, Urgent if Critical or blocker
# - NE stories: walk up Story→Epic→Feature, use Feature priority (Critical/Major→High)
# - blocker+ label on features: High (Urgent reserved for production bugs)
# - Fallback: jira/severity-* labels on the PR
# Items with Jira Priority already set are skipped. Blanks mean Jira
# doesn't have priority data — the team should set it during triage.
echo "--- Operation G: Set Jira Priority ---"

PRIORITY_FILE=$(mktemp)
echo "$ITEMS_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data['items']:
    ai_priority = item.get('jira Priority', '')
    if ai_priority:
        continue
    content = item.get('content', {})
    if content.get('type') != 'PullRequest':
        continue
    title = content.get('title', '')
    item_id = item['id']
    repo = content.get('repository', '')
    number = content.get('number', '')
    labels = ','.join(item.get('labels', []))
    print(f'{item_id}|{repo}|{number}|{title}|{labels}')
" > "$PRIORITY_FILE"

PRIORITY_COUNT=$(wc -l < "$PRIORITY_FILE" | tr -d ' ')
echo "  Found $PRIORITY_COUNT items without Jira Priority"

while IFS='|' read -r item_id repo number title labels; do
    [ -z "$item_id" ] && continue

    priority_id=""
    priority_name=""
    reason=""

    # Extract Jira key from title
    jira_key=$(echo "$title" | grep -oE '(OCPBUGS|NE)-[0-9]+' | head -1 || true)

    if [ -n "$jira_key" ]; then
        # Fetch Jira issue details
        jira_json=$(acli jira workitem view "$jira_key" --fields priority,issuetype,labels,parent --json 2>/dev/null || echo "{}")

        jira_priority=$(echo "$jira_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('fields',{}).get('priority',{}).get('name',''))" 2>/dev/null || echo "")
        jira_type=$(echo "$jira_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('fields',{}).get('issuetype',{}).get('name',''))" 2>/dev/null || echo "")
        jira_labels=$(echo "$jira_json" | python3 -c "import json,sys; print(','.join(json.load(sys.stdin).get('fields',{}).get('labels',[])))" 2>/dev/null || echo "")
        parent_key=$(echo "$jira_json" | python3 -c "import json,sys; p=json.load(sys.stdin).get('fields',{}).get('parent',{}); print(p.get('key','') if p else '')" 2>/dev/null || echo "")

        # Check for blocker label
        if echo "$jira_labels" | grep -qi "blocker+"; then
            priority_id="$JIRA_PRIORITY_URGENT"
            priority_name="Urgent"
            reason="blocker+ on $jira_key"
        fi

        # Check for CVE/Vulnerability — floor at High
        if [ -z "$priority_id" ] && ([ "$jira_type" = "Vulnerability" ] || echo "$jira_labels" | grep -qi "Security" || echo "$title" | grep -qi "CVE"); then
            if [ "$jira_priority" = "Critical" ] || [ "$jira_priority" = "Blocker" ]; then
                priority_id="$JIRA_PRIORITY_URGENT"
                priority_name="Urgent"
                reason="Critical CVE $jira_key"
            else
                priority_id="$JIRA_PRIORITY_HIGH"
                priority_name="High"
                reason="CVE $jira_key"
            fi
        fi

        # For NE stories/epics, walk up to Feature
        if [ -z "$priority_id" ] && [[ "$jira_key" == NE-* ]]; then
            # Walk up: Story→Epic→Feature
            current_key="$jira_key"
            feature_priority=""
            for _depth in 1 2 3; do
                if [ -z "$parent_key" ]; then
                    break
                fi
                parent_json=$(acli jira workitem view "$parent_key" --fields priority,issuetype,labels,parent --json 2>/dev/null || echo "{}")
                parent_type=$(echo "$parent_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('fields',{}).get('issuetype',{}).get('name',''))" 2>/dev/null || echo "")
                parent_priority=$(echo "$parent_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('fields',{}).get('priority',{}).get('name',''))" 2>/dev/null || echo "")
                parent_labels=$(echo "$parent_json" | python3 -c "import json,sys; print(','.join(json.load(sys.stdin).get('fields',{}).get('labels',[])))" 2>/dev/null || echo "")

                # Check for blocker at any level — High for features (not Urgent,
                # which is reserved for production bugs/outages)
                if echo "$parent_labels" | grep -qi "blocker+"; then
                    priority_id="$JIRA_PRIORITY_HIGH"
                    priority_name="High"
                    reason="blocker+ on $parent_key (feature)"
                    break
                fi

                # If we reached a Feature, use its priority
                if [ "$parent_type" = "Feature" ] || [ "$parent_type" = "Initiative" ]; then
                    feature_priority="$parent_priority"
                    reason="$parent_key ($parent_type) $parent_priority"
                    break
                fi

                # Move up
                current_key="$parent_key"
                parent_key=$(echo "$parent_json" | python3 -c "import json,sys; p=json.load(sys.stdin).get('fields',{}).get('parent',{}); print(p.get('key','') if p else '')" 2>/dev/null || echo "")
            done

            # Map feature priority — Critical features are High (not Urgent,
            # which is reserved for production bugs). Feature work has deadlines
            # but isn't a firefight.
            if [ -z "$priority_id" ] && [ -n "$feature_priority" ]; then
                case "$feature_priority" in
                    Critical|Blocker)
                        priority_id="$JIRA_PRIORITY_HIGH"
                        priority_name="High" ;;
                    Major)
                        priority_id="$JIRA_PRIORITY_HIGH"
                        priority_name="High" ;;
                    Normal)
                        priority_id="$JIRA_PRIORITY_MEDIUM"
                        priority_name="Medium" ;;
                    Minor)
                        priority_id="$JIRA_PRIORITY_LOW"
                        priority_name="Low" ;;
                esac
            fi
        fi

        # For OCPBUGS, use bug priority directly
        if [ -z "$priority_id" ] && [[ "$jira_key" == OCPBUGS-* ]]; then
            case "$jira_priority" in
                Critical|Blocker)
                    priority_id="$JIRA_PRIORITY_URGENT"
                    priority_name="Urgent"
                    reason="$jira_key $jira_priority" ;;
                Major)
                    priority_id="$JIRA_PRIORITY_HIGH"
                    priority_name="High"
                    reason="$jira_key $jira_priority" ;;
                Normal)
                    priority_id="$JIRA_PRIORITY_MEDIUM"
                    priority_name="Medium"
                    reason="$jira_key $jira_priority" ;;
                Minor)
                    priority_id="$JIRA_PRIORITY_LOW"
                    priority_name="Low"
                    reason="$jira_key $jira_priority" ;;
            esac
        fi
    fi

    # Fallback: check PR's jira/severity-* labels if still unset
    if [ -z "$priority_id" ] && [ -n "$labels" ]; then
        if echo "$labels" | grep -q "jira/severity-critical"; then
            priority_id="$JIRA_PRIORITY_URGENT"
            priority_name="Urgent"
            reason="severity-critical label"
        elif echo "$labels" | grep -q "jira/severity-important"; then
            priority_id="$JIRA_PRIORITY_HIGH"
            priority_name="High"
            reason="severity-important label"
        elif echo "$labels" | grep -q "jira/severity-moderate"; then
            priority_id="$JIRA_PRIORITY_MEDIUM"
            priority_name="Medium"
            reason="severity-moderate label"
        elif echo "$labels" | grep -q "jira/severity-low"; then
            priority_id="$JIRA_PRIORITY_LOW"
            priority_name="Low"
            reason="severity-low label"
        elif echo "$labels" | grep -q "jira/severity-informational"; then
            priority_id="$JIRA_PRIORITY_LOW"
            priority_name="Low"
            reason="severity-informational label"
        fi
    fi

    # Set if we determined a priority
    if [ -n "$priority_id" ]; then
        echo "  SET: $repo#$number → $priority_name ($reason)"
        gh project item-edit --project-id "$PROJECT_ID" --id "$item_id" \
            --field-id "$FIELD_JIRA_PRIORITY" --single-select-option-id "$priority_id" 2>/dev/null
    fi
done < "$PRIORITY_FILE"

rm -f "$PRIORITY_FILE"

echo ""
echo "=== Sync Complete ==="
echo "  Shared PRs added: $SHARED_ADDED"
echo "  Docs PRs added: $DOCS_ADDED"
echo "$ITEMS_JSON" | python3 -c "
import json, sys
deterministic = {$(printf '"%s",' "${!REPO_TO_AREA[@]}")}
data = json.load(sys.stdin)
area_count = 0
priority_count = 0
for item in data['items']:
    if item.get('content', {}).get('type') != 'PullRequest':
        continue
    area = item.get('area', '')
    repo = item.get('content', {}).get('repository', '')
    if not area and repo not in deterministic:
        area_count += 1
print(f'  Items without Area (need AI classification): {area_count}')
"
