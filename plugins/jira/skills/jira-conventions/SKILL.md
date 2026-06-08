---
name: jira-conventions
description: Use this skill to load relevant Jira conventions, like project-specific field mappings, team component requirements, version handling, and Markdown formatting
---

# Jira Conventions

Use this skill whenever you are operating in any of the following Jira projects or teams to learn their specific conventions for issue creation, field mappings, version handling, and component selection:

## Project Conventions

### CNTRLPLANE — [../reference/cntrlplane.md](../../reference/cntrlplane.md)

Read when the project key is **CNTRLPLANE**, or the user is creating Stories, Epics, Features, or Tasks for OpenShift Control Planes. Covers version normalization (`openshift-X.Y` format), target version field (`customfield_10855` as array with version ID), parent linking fields (Epic Link vs Parent Link), and Epic Name requirements.

### OCPBUGS — [../reference/ocpbugs.md](../../reference/ocpbugs.md)

Read when the project key is **OCPBUGS**, or the user is filing a bug without specifying a project (OCPBUGS is the default for bugs). Covers Affects Version (`versions` field), target version handling, and bug-specific field formats. Note: OCPBUGS uses string format for target version, unlike CNTRLPLANE which uses array format.

### GCP-HCP — [../reference/gcp-hcp.md](../../reference/gcp-hcp.md)

Read when the project key is **GCP**, or the summary/description contains GCP HCP keywords ("GCP HCP", "Hypershift on GKE", "GKE hosted control plane"). Covers GCP-specific components (`hypershift-operator-gcp`, `gcp-hcp-automation`, etc.), story points (auto-estimated on Fibonacci scale), priority scheme (OJA-PRIS-001), epic linking best practices, and full team-standardized templates for Stories, Tasks, Epics, Features, and Definition of Done.

## Formatting Conventions

### Markdown for Jira — [../reference/markdown-for-jira.md](../../reference/markdown-for-jira.md)

Read when writing or editing Jira issue descriptions or comments via MCP tools. Covers Markdown syntax mapping to Jira rendering, auto-linking of issue keys, and example templates for user stories, bug reports, epics, and tasks.

## Team Conventions

### HyperShift — [../reference/hypershift.md](../../reference/hypershift.md)

Read when the summary or description contains HyperShift keywords ("HyperShift", "ARO HCP", "ROSA HCP", "hosted control plane"), or a component contains "HyperShift". This layers **on top of** CNTRLPLANE or OCPBUGS project conventions — always read the project file first, then this one. Covers mandatory component selection (HyperShift / ARO vs HyperShift / ROSA vs HyperShift), auto-detection logic from keywords, platform-specific labels, and version defaults.

## How to Use

1. **Match the project key** from the user's request to a project above. Read the corresponding reference file for that project's conventions (custom fields, version handling, component requirements, templates).

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
