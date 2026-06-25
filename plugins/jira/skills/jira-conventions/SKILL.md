---
name: jira-conventions
description: Project and team-specific Jira conventions for CNTRLPLANE, OCPBUGS, GCP, HyperShift, and hosted control plane issues
---

# Jira Conventions Router

This skill routes to the correct project or team conventions based on the Jira project key, component, or keywords in the issue summary.

## Routing Table

Match on project key, component, or summary keywords. Load the corresponding reference file.

### By Project Key

| Project Key | Conventions | Reference |
|---|---|---|
| **CNTRLPLANE** | Red Hat OpenShift Control Planes — features, epics, stories, tasks | [CNTRLPLANE conventions](../../reference/cntrlplane.md) |
| **OCPBUGS** | OpenShift Bugs — bug reports only | [OCPBUGS conventions](../../reference/ocpbugs.md) |
| **GCP** | GCP Hosted Control Planes (Hypershift on GKE) — stories, epics, tasks, bugs, features | [GCP HCP conventions](../../reference/gcp-hcp.md) |

### By Team / Keywords

Detect these keywords in the issue summary, description, or component to layer team-specific conventions on top of project conventions:

| Keywords | Team Conventions | Reference |
|---|---|---|
| HyperShift, ARO HCP, ROSA HCP, hosted control plane | HyperShift team — component selection (HyperShift / ARO, HyperShift / ROSA, HyperShift) | [HyperShift conventions](../../reference/hypershift.md) |
| GCP HCP, Hypershift on GKE, GKE hosted control plane | GCP HCP team — GCP project conventions, team templates, sizing guide | [GCP HCP conventions](../../reference/gcp-hcp.md) |

### Layering Rules

1. **Project conventions** are loaded first based on the project key
2. **Team conventions** are layered on top when keywords match
3. Both can apply simultaneously (e.g., CNTRLPLANE + HyperShift)
4. If no project or team matches, skip this skill — the issue uses only type-specific guidance from the `create` skill

## How to Use

After identifying the matching conventions:

1. **Read** the linked reference file(s)
2. **Apply** project-specific custom fields, version handling, and component requirements
3. **Layer** team-specific conventions if keywords match (component selection, labels, templates)
4. **Defer** to the `create` skill for issue-type guidance (story template, bug template, etc.)
