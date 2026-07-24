#!/bin/bash
# =============================================================================
# NI&D PR Dashboard — Shared Configuration
# Sourced by sync-dashboard.sh and list-unclassified-areas.sh
# =============================================================================

# =============================================================================
# TEAM CONFIGURATION
# Update these when team membership changes.
# =============================================================================

TEAM_USERNAMES=("candita" "gcs278" "Miciah" "rfredette" "Thealisyed" "grzpiotrowski" "rikatz" "davidesalerno" "bentito" "jcmoraisjr" "aswinsuryan" "melvinjoseph86" "rhamini3")

# GitHub login → short display name (used for PR Author column)
declare -A USERNAME_TO_DISPLAY=(
    ["candita"]="Candace H."
    ["gcs278"]="Grant S."
    ["Miciah"]="Miciah M."
    ["rfredette"]="Ryan F."
    ["Thealisyed"]="Ali S."
    ["grzpiotrowski"]="Grzegorz P."
    ["rikatz"]="Ricardo K."
    ["davidesalerno"]="Davide S."
    ["bentito"]="Brett T."
    ["jcmoraisjr"]="Joao M."
    ["aswinsuryan"]="Aswin S."
    ["melvinjoseph86"]="Melvin J."
    ["rhamini3"]="Ishmam A."
)

# Full name → GitHub login (used to match Primary/Secondary Reviewer dropdown)
declare -A FULLNAME_TO_USERNAME=(
    ["Candace Holman"]="candita"
    ["Grant Spence"]="gcs278"
    ["Miciah Masters"]="Miciah"
    ["Ryan Fredette"]="rfredette"
    ["Ali Syed"]="Thealisyed"
    ["Grzegorz Piotrowski"]="grzpiotrowski"
    ["Ricardo Katz"]="rikatz"
    ["Davide Salerno"]="davidesalerno"
    ["Brett Tofel"]="bentito"
    ["Joao Morais"]="jcmoraisjr"
    ["Aswin Suryanarayanan"]="aswinsuryan"
    ["Melvin Joseph"]="melvinjoseph86"
    ["Ishmam Amin"]="rhamini3"
)

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
STATUS_ASSIGNED="f75ad846"

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

# Repo → Area mapping (deterministic cases only)
# Any repo NOT in this map is considered ambiguous and needs AI classification.
declare -A REPO_TO_AREA=(
    ["openshift/external-dns"]="$AREA_EXTERNAL_DNS"
    ["openshift/external-dns-operator"]="$AREA_EXTERNAL_DNS"
    ["openshift/aws-load-balancer-operator"]="$AREA_ALBO"
    ["openshift/aws-load-balancer-controller"]="$AREA_ALBO"
    ["openshift/cluster-dns-operator"]="$AREA_DNS"
    ["openshift/coredns"]="$AREA_DNS"
    ["openshift/coredns-ocp-dnsnameresolver"]="$AREA_DNS"
    ["openshift-eng/ai-helpers"]="$AREA_AI"
    ["openshift/openshift-mcp-server"]="$AREA_AI"
)

# Helper: check if a repo is ambiguous (not in REPO_TO_AREA)
is_ambiguous_repo() {
    [ -z "${REPO_TO_AREA[$1]+x}" ]
}
