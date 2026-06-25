# CNTRLPLANE Conventions

Project-specific conventions for creating Jira issues in the CNTRLPLANE project.

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | CNTRLPLANE |
| **Full Name** | Red Hat OpenShift Control Planes |
| **Issue Types** | Feature, Epic, Story, Task, Spike |
| **Used By** | Multiple OpenShift teams (HyperShift, Cluster Infrastructure, Networking, Storage, etc.) |

## Target Version (customfield_10855)

**Status:** OPTIONAL (many issues have null target version)

**Prompt:** "Which OpenShift version should this target? (e.g., 4.22, openshift 4.22, OCP 4.22) or press Enter to skip"

### Version Input Normalization

| User Input | Normalized Output |
|------------|-------------------|
| `4.21` | `openshift-4.21` |
| `4.22.0` | `openshift-4.22` |
| `openshift 4.23` | `openshift-4.23` |
| `openshift-4.21` | `openshift-4.21` |
| `OCP 4.22` | `openshift-4.22` |
| `ocp 4.21` | `openshift-4.21` |

**Normalization rules:**
1. Convert to lowercase
2. Remove "ocp" or "openshift" prefix (with or without space/hyphen)
3. Extract version number (X.Y or X.Y.Z → X.Y)
4. Prepend "openshift-"

### Setting Target Version via MCP

1. Fetch available versions via `getJiraIssueTypeMetaWithFields` — the `versions` field's `allowedValues` contains valid version IDs
2. Find the version ID for the normalized version name
3. Use array format: `"customfield_10855": [{"id": "VERSION_ID"}]`

**Never set** Fix Version/s (`fixVersions`) — managed by the release team.

## CNTRLPLANE-Specific Fields

For shared custom fields (Epic Link, Parent Link, Epic Name, Target Version), see the `create` skill. The table below shows CNTRLPLANE-specific usage:

| Creating | Parent Type | Field | Value Format |
|----------|-------------|-------|--------------|
| Story | Epic | `customfield_10014` (Epic Link) | `"CNTRLPLANE-123"` (string) |
| Task | Epic | `customfield_10014` (Epic Link) | `"CNTRLPLANE-123"` (string) |
| Epic | Feature | `customfield_10018` (Parent Link) | `"CNTRLPLANE-123"` (string) |

Both fields take STRING values (issue key), NOT objects.

**Per issue type:**

| Issue Type | Key Fields |
|---|---|
| Story | `customfield_10014` (Epic Link): parent epic key (optional) |
| Epic | `customfield_10011` (Epic Name): must match summary; `customfield_10018` (Parent Link): parent feature key (optional) |
| Feature | No type-specific custom fields required |
| Task | `customfield_10014` (Epic Link): parent epic key (optional) |

## Component Requirements

Components are **team-specific**. The CNTRLPLANE project does not enforce component selection at the project level.

- Teams may have their own conventions (e.g., [HyperShift conventions](hypershift.md) for component selection)
- If not specified, prompt: "Does this issue require a component? (optional)"

## Issue Type Notes

- **Stories:** Must include acceptance criteria; may link to parent Epic
- **Epics:** Epic Name field (`customfield_10011`) required, must match summary; may link to parent Feature
- **Tasks:** May link to parent Story or Epic
- **Bugs:** Should be created in [OCPBUGS](ocpbugs.md), not CNTRLPLANE

## Team-Specific Extensions

- **HyperShift team:** See [HyperShift conventions](hypershift.md) for component selection
- **GCP HCP team:** See [GCP HCP conventions](gcp-hcp.md) for GCP project conventions
