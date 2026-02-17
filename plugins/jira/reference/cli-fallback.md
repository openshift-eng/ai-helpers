---
name: Jira CLI Fallback Reference
description: jira-cli commands as fallback when MCP is unavailable
---

# Jira CLI Fallback Reference

**IMPORTANT:** Use MCP tools as the primary method for Jira operations. This guide provides `jira-cli` commands for scenarios where the MCP Jira server is unavailable or not configured.

This guide documents `jira-cli` commands as a fallback when the MCP (Model Context Protocol) Jira server is unavailable or not configured.

## Table of Contents

- [Shell Quoting Best Practice](#shell-quoting-best-practice)
- [Common Commands](#common-commands)
  - [Create an Issue](#create-an-issue)
  - [Get Issue Details](#get-issue-details)
  - [Search Issues](#search-issues)
  - [Edit Issue](#edit-issue)
  - [Transition Issue](#transition-issue)
  - [Link Issues](#link-issues)
  - [Add Label](#add-label)
  - [Add Component](#add-component)
  - [Set Custom Fields](#set-custom-fields)
- [Complex Example](#complex-example-create-epic-with-parent-link)
- [Custom Field Names](#custom-field-names)
- [Troubleshooting](#troubleshooting)
- [Reference](#reference)

## Shell Quoting Best Practice

**CRITICAL:** When passing Wiki Markup or complex strings to jira-cli, **always use single quotes** to prevent shell interpretation:

```bash
# Single quotes preserve wiki markup
jira create -p GCP -t Story -s 'Enable Pod Disruption Budgets' -d '
As a cluster admin, I want to enable Pod Disruption Budgets for the control plane, so that I can prevent accidental disruptions.

h2. Acceptance Criteria

* Test that PDB is configured for all control plane pods
* Test that pods are protected from voluntary disruptions
'
```

## Common Commands

### Create an Issue

```bash
jira create -p PROJECT-KEY -t Story -s "Summary text" -d "Description text"
```

**Parameters:**
- `-p, --project` - Project key (required)
- `-t, --type` - Issue type (Story, Epic, Task, Bug, Feature Request)
- `-s, --summary` - Issue summary (required)
- `-d, --description` - Issue description (optional, use wiki markup)

**Example - Story:**

```bash
jira create \
  -p GCP \
  -t Story \
  -s 'Enable automated backups for GKE control planes' \
  -d '
As a cluster administrator, I want to enable automated backups for my GKE-hosted control planes, so that I can quickly recover from data loss or corruption.

h2. Acceptance Criteria

* Test that backups can be scheduled daily at a configurable time
* Test that backup retention policy is enforced (30 days default)
* Test that backups can be restored to the same or different GCP project
* Test that backup operations do not interrupt cluster operations
'
```

### Get Issue Details

```bash
jira issue get PROJ-123
```

### Search Issues

```bash
jira issue search 'project = GCP AND type = Story'
jira issue search 'project = GCP AND status = "In Progress"'
```

### Edit Issue

```bash
jira issue edit PROJ-123 -S 'New summary'
jira issue edit PROJ-123 -D 'New description'
```

### Transition Issue

```bash
jira issue move PROJ-123 "In Progress"
jira issue move PROJ-123 "Done"
```

### Link Issues

```bash
jira issue link PROJ-123 PROJ-456 "is blocked by"
jira issue link PROJ-100 PROJ-200 "relates to"
```

### Add Label

```bash
jira issue edit PROJ-123 -l "ai-generated-jira"
jira issue edit PROJ-123 -l "urgent" -l "blocker"
```

### Add Component

```bash
jira issue edit PROJ-123 -c "HyperShift / ROSA"
```

### Set Custom Fields

**Custom field naming:** Use dash-separated lowercase (e.g., `epic-link` for `customfield_12311140`)

```bash
# Epic Link (Link Story/Task to Epic)
jira issue edit PROJ-123 -f 'epic-link=PROJ-456'

# Parent Link (Link Epic to Feature)
jira issue edit PROJ-100 -f 'parent-link=PROJ-50'

# Target Version
jira issue edit PROJ-123 -f 'target-version=openshift-4.21'
```

## Complex Example: Create Epic with Parent Link

```bash
# Step 1: Create the Epic
EPIC=$(jira create \
  -p GCP \
  -t Epic \
  -s 'Multi-cluster monitoring and observability' \
  -d '
h2. Use Case / Context

Implement comprehensive monitoring and observability for GCP-hosted control planes across multiple GKE clusters.

h2. Desired State

All management cluster workloads have real-time metrics collection and centralized aggregation.

h2. Scope

* Metrics collection from control plane pods
* Central metrics aggregation and storage
* Dashboards for monitoring cluster health
* Alerting framework for critical metrics

h2. Acceptance Criteria

* Test that metrics are collected from all control plane pods
* Test that metrics are available within 30 seconds of generation
* Test that dashboards accurately reflect cluster state
' | grep -oE 'GCP-[0-9]+' | head -1)

# Step 2: Link to parent Feature
jira issue edit $EPIC -f 'parent-link=GCP-100'

echo "Created Epic: $EPIC"
```

## Custom Field Names

Map between Jira UI field names and jira-cli custom field identifiers:

| UI Name | CLI Name | Custom Field ID | Usage |
|---------|----------|-----------------|-------|
| Epic Name | epic-name | customfield_12311141 | Required when creating Epics |
| Epic Link | epic-link | customfield_12311140 | Link Story/Task → Epic |
| Parent Link | parent-link | customfield_12313140 | Link Epic → Feature |
| Target Version | target-version | customfield_12319940 | Set target release version |

## Troubleshooting

### Authentication Failed

```bash
# Re-authenticate
jira login

# Or update config file
nano ~/.jira.d/config.yml
```

### Command Not Found

```bash
# Verify installation
which jira
jira -v

# Try full path
/usr/local/bin/jira --version
```

### Issue Creation Failed

```bash
# Check project exists
jira issue search 'project = GCP' | head -5

# Verify issue type is valid
jira create -p GCP -t InvalidType -s "Test" # Will error with valid types

# Check field permissions
jira issue get GCP-1 # View existing issue structure
```

### Custom Field Not Found

```bash
# List all fields
jira issue get GCP-1 -a

# Use full custom field ID instead of CLI name
jira issue edit PROJ-123 -f 'customfield_12311140=PROJ-456'
```

## Reference

- [go-jira GitHub Repository](https://github.com/go-jira/jira)
- [go-jira Documentation](https://github.com/go-jira/jira#readme)
- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
