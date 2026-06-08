---
name: jira-conventions
description: Project-specific and team-specific Jira conventions for CNTRLPLANE, OCPBUGS, GCP, and HyperShift
---

# Jira Conventions

Use this skill whenever you are operating in any of the following Jira projects or teams to learn their specific conventions for issue creation, field mappings, version handling, and component selection:

## Project Conventions

| Project Key | Description | Reference |
|-------------|-------------|-----------|
| **CNTRLPLANE** | OpenShift Control Planes — Stories, Epics, Features, Tasks | Read `reference/cntrlplane.md` |
| **OCPBUGS** | OpenShift Bugs — Bug reports only | Read `reference/ocpbugs.md` |
| **GCP** | GCP Hosted Control Planes (Hypershift on GKE) — Stories, Epics, Tasks, Bugs, Features | Read `reference/gcp-hcp.md` |

## Team Conventions

| Team | Applies To | Reference |
|------|-----------|-----------|
| **HyperShift** | CNTRLPLANE and OCPBUGS issues involving HyperShift, ARO HCP, or ROSA HCP | Read `reference/hypershift.md` |

## How to Use

1. **Match the project key** from the user's request to the table above. Read the corresponding reference file for that project's conventions (custom fields, version handling, component requirements, templates).

2. **Check for team conventions** by scanning the issue summary and description for team keywords (e.g., "HyperShift", "ARO HCP", "ROSA HCP", "GCP HCP"). If a team match is found, also read that team's reference file and layer its conventions on top of the project conventions.

3. **Apply both layers** — project conventions set the baseline (field IDs, version formats, issue types), and team conventions add specifics (component selection, labels, templates).

## When to Invoke This Skill

This skill is automatically invoked by `/jira:create` when:
- The project key matches a known project (CNTRLPLANE, OCPBUGS, GCP)
- Keywords in the summary/description match a known team (HyperShift, GCP HCP)
- The user explicitly requests project or team conventions

## Adding New Conventions

To add conventions for a new project or team:
1. Create a new reference file at `reference/your-project.md`
2. Add an entry to the appropriate table above
3. Update `/jira:create` to detect and invoke the conventions

## Other References

| Reference | Description |
|-----------|-------------|
| `reference/markdown-for-jira.md` | Markdown formatting guide for Jira descriptions |
