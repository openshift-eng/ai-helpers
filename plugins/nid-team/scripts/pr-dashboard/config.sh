#!/bin/bash
# =============================================================================
# NI&D PR Dashboard — Shared Configuration
# Sourced by sync-dashboard.sh and list-unclassified-areas.sh
# =============================================================================

# =============================================================================
# BASH COMPATIBILITY
# Associative arrays (declare -A) require bash 4+, but macOS ships bash 3.2.
# We define team/area data once as pipe-delimited tables (below) and expose it
# through accessor functions. When bash 4+ is available we build associative
# arrays for O(1) lookups; on bash 3.2 the accessors fall back to scanning the
# tables. Either way the sourcing scripts call the same functions.
# =============================================================================
if [ "${BASH_VERSINFO:-0}" -ge 4 ]; then
    HAVE_ASSOC=1
else
    HAVE_ASSOC=0
fi

# =============================================================================
# TEAM CONFIGURATION
# Single source of truth: one row per member as  login|display|fullname
#   login    — GitHub login
#   display  — short display name (PR Author column)
#   fullname — Primary/Secondary Reviewer dropdown label
# Update this table when team membership changes.
# =============================================================================
TEAM_DATA="\
candita|Candace H.|Candace Holman
gcs278|Grant S.|Grant Spence
Miciah|Miciah M.|Miciah Masters
rfredette|Ryan F.|Ryan Fredette
Thealisyed|Ali S.|Ali Syed
grzpiotrowski|Grzegorz P.|Grzegorz Piotrowski
rikatz|Ricardo K.|Ricardo Katz
davidesalerno|Davide S.|Davide Salerno
bentito|Brett T.|Brett Tofel
jcmoraisjr|Joao M.|Joao Morais
aswinsuryan|Aswin S.|Aswin Suryanarayanan
melvinjoseph86|Melvin J.|Melvin Joseph
rhamini3|Ishmam A.|Ishmam Amin
pedjak|Predrag K.|Predrag Knezevic"

# Derive the plain login list (indexed arrays work on all bash versions).
TEAM_USERNAMES=()
while IFS='|' read -r _login _disp _full; do
    [ -n "$_login" ] && TEAM_USERNAMES+=("$_login")
done <<< "$TEAM_DATA"

BOT_USERNAMES="openshift-bot openshift-cherrypick-robot"

# Shared repos: PRs are only added if authored by a team member
SHARED_REPOS=("openshift/images" "openshift/api" "openshift/release" "openshift/origin" "openshift/enhancements" "openshift-eng/ai-helpers" "openshift/openshift-mcp-server" "openshift/library-go" "openshift/openshift-apiserver" "openshift/coredns-ocp-dnsnameresolver")

# =============================================================================
# GITHUB PROJECT CONFIGURATION
# IDs from: gh project field-list 28 --owner openshift --format json
# =============================================================================

PROJECT_NUM=28
PROJECT_ID="PVT_kwDOAAwXEc4BbxeH"
OWNER="openshift"

# Field IDs
FIELD_PR_AUTHOR="PVTF_lADOAAwXEc4BbxeHzhWgBPY"
FIELD_PRIMARY_REVIEWER="PVTSSF_lADOAAwXEc4BbxeHzhWfjp4"
FIELD_SECONDARY_REVIEWER="PVTSSF_lADOAAwXEc4BbxeHzhWfjp0"
FIELD_AREA="PVTSSF_lADOAAwXEc4BbxeHzhW9Lxw"
FIELD_AUTHOR_TYPE="PVTSSF_lADOAAwXEc4BbxeHzhW9SlE"
FIELD_STATUS="PVTSSF_lADOAAwXEc4BbxeHzhWfjpE"
FIELD_PR_PRIORITY="PVTSSF_lADOAAwXEc4BbxeHzhW9pYU"

# PR Priority option IDs
PR_PRIORITY_URGENT="3e8e0c36"
PR_PRIORITY_HIGH="774497bf"
PR_PRIORITY_MEDIUM="b6818094"
PR_PRIORITY_LOW="fce977ce"
FIELD_JIRA_PRIORITY="PVTSSF_lADOAAwXEc4BbxeHzhXc2J0"

# Status option IDs
STATUS_NEW="196ba1c2"
STATUS_DEFERRED="637b6153"
STATUS_ASSIGNED="f75ad846"
STATUS_DONE="39490499"

# Jira Priority option IDs
JIRA_PRIORITY_URGENT="e0e67daf"
JIRA_PRIORITY_HIGH="b3b8d2af"
JIRA_PRIORITY_MEDIUM="61f8af68"
JIRA_PRIORITY_LOW="9174c2b6"

# Author Type option IDs
AUTHOR_TYPE_TEAM="9d372701"
AUTHOR_TYPE_EXTERNAL="5710b4ff"
AUTHOR_TYPE_BOT="d0782f7d"
AUTHOR_TYPE_SUSTAINING="0d225d31"
AUTHOR_TYPE_DOCS="952271b4"

# Area option IDs
AREA_GWAPI="196a759b"
AREA_DNS="c2935ddd"
AREA_EXTERNAL_DNS="b02c7810"
AREA_ALBO="a6184328"
AREA_ROUTER="667048b1"
AREA_AI="9f9c29ab"

# Repo → Area mapping (deterministic cases only), as  repo|area_option_id
# Any repo NOT in this table is considered ambiguous and needs AI classification.
REPO_AREA_DATA="\
openshift/external-dns|$AREA_EXTERNAL_DNS
openshift/external-dns-operator|$AREA_EXTERNAL_DNS
openshift/aws-load-balancer-operator|$AREA_ALBO
openshift/aws-load-balancer-controller|$AREA_ALBO
openshift/cluster-dns-operator|$AREA_DNS
openshift/coredns|$AREA_DNS
openshift/coredns-ocp-dnsnameresolver|$AREA_DNS
openshift-eng/ai-helpers|$AREA_AI
openshift/openshift-mcp-server|$AREA_AI"

# =============================================================================
# LOOKUP ACCESSORS
# On bash 4+ these use associative arrays; on bash 3.2 they scan the tables.
# =============================================================================
if [ "$HAVE_ASSOC" = 1 ]; then
    declare -A _DISPLAY_BY_LOGIN _LOGIN_BY_DISPLAY _LOGIN_BY_FULLNAME _AREA_BY_REPO
    while IFS='|' read -r _login _disp _full; do
        [ -n "$_login" ] || continue
        _DISPLAY_BY_LOGIN["$_login"]="$_disp"
        _LOGIN_BY_DISPLAY["$_disp"]="$_login"
        _LOGIN_BY_FULLNAME["$_full"]="$_login"
    done <<< "$TEAM_DATA"
    while IFS='|' read -r _repo _area; do
        [ -n "$_repo" ] || continue
        _AREA_BY_REPO["$_repo"]="$_area"
    done <<< "$REPO_AREA_DATA"

    display_name()         { echo "${_DISPLAY_BY_LOGIN[$1]:-$1}"; }
    login_for_display()    { echo "${_LOGIN_BY_DISPLAY[$1]:-}"; }
    login_for_fullname()   { echo "${_LOGIN_BY_FULLNAME[$1]:-}"; }
    area_for_repo()        { echo "${_AREA_BY_REPO[$1]:-}"; }
    is_ambiguous_repo()    { [ -z "${_AREA_BY_REPO[$1]+x}" ]; }
    deterministic_repos()  { printf '%s\n' "${!_AREA_BY_REPO[@]}"; }
else
    # login → display name (falls back to the login when not a team member)
    display_name() {
        local login disp full
        while IFS='|' read -r login disp full; do
            [ "$login" = "$1" ] && { echo "$disp"; return; }
        done <<< "$TEAM_DATA"
        echo "$1"
    }
    # display name → login ("" if not found)
    login_for_display() {
        local login disp full
        while IFS='|' read -r login disp full; do
            [ "$disp" = "$1" ] && { echo "$login"; return; }
        done <<< "$TEAM_DATA"
        echo ""
    }
    # full name → login ("" if not found)
    login_for_fullname() {
        local login disp full
        while IFS='|' read -r login disp full; do
            [ "$full" = "$1" ] && { echo "$login"; return; }
        done <<< "$TEAM_DATA"
        echo ""
    }
    # repo → area option id ("" if not deterministic)
    area_for_repo() {
        local repo area
        while IFS='|' read -r repo area; do
            [ "$repo" = "$1" ] && { echo "$area"; return; }
        done <<< "$REPO_AREA_DATA"
        echo ""
    }
    # true (0) when the repo is not in the deterministic table
    is_ambiguous_repo() {
        local repo area
        while IFS='|' read -r repo area; do
            [ "$repo" = "$1" ] && return 1
        done <<< "$REPO_AREA_DATA"
        return 0
    }
    # print each deterministic repo, one per line
    deterministic_repos() {
        local repo area
        while IFS='|' read -r repo area; do
            [ -n "$repo" ] && echo "$repo"
        done <<< "$REPO_AREA_DATA"
    }
fi
