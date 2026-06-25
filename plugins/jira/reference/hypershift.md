# HyperShift Conventions

Team-specific conventions for creating Jira issues involving HyperShift in CNTRLPLANE and OCPBUGS projects.

## Component Requirements

**ALL** HyperShift issues in CNTRLPLANE and OCPBUGS **must** have a component:

| Component | Usage |
|-----------|-------|
| **HyperShift / ARO** | ARO HCP (Azure Red Hat OpenShift Hosted Control Planes) |
| **HyperShift / ROSA** | ROSA HCP (Red Hat OpenShift Service on AWS Hosted Control Planes) |
| **HyperShift** | Platform-agnostic or affects both ARO and ROSA |

### Auto-Detection Keywords

| Keywords | Component | Confidence |
|----------|-----------|------------|
| ARO, Azure, "ARO HCP" | **HyperShift / ARO** | High |
| ROSA, AWS, "ROSA HCP" | **HyperShift / ROSA** | High |
| Both ARO and ROSA mentioned | **HyperShift** | High (multi-platform) |
| "All platforms", "platform-agnostic" | **HyperShift** | Medium (verify with user) |
| **No platform keywords** | **Prompt user** | N/A |

### Prompt When Uncertain

```
Which HyperShift platform does this issue affect?

1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues or affects both

Select (1-3):
```

### Component Override

User can override auto-detection with `--component` flag.

## Version Defaults

### CNTRLPLANE Issues

- **Target Version** (`customfield_10855`): default `openshift-4.21`, user may override

### OCPBUGS Issues

- **Affects Version/s**: default `4.21`, user should specify actual version
- **Target Version** (`customfield_10855`): default `4.21`, may differ based on severity/backport

## Labels

In addition to `ai-generated-jira`, HyperShift issues may include:

**Platform-specific:** `aro-hcp`, `rosa-hcp`

**Feature area:** `autoscaling`, `networking`, `observability`, `upgrade`, `lifecycle`

**Priority/type:** `technical-debt`, `security`, `performance`

## MCP Tool Integration

### CNTRLPLANE Stories/Tasks

Use `createJiraIssue` with `contentFormat: "markdown"`, project `CNTRLPLANE`. Set `components` to the auto-detected or user-selected HyperShift component. Include `customfield_10855` for target version.

### OCPBUGS Bugs

Use `createJiraIssue` with `contentFormat: "markdown"`, project `OCPBUGS`, type `Bug`. Set `components` to the HyperShift component. Include `versions` (affects version) as `[{"name": "4.21"}]` and `customfield_10855` (target version).

## Related Conventions

- [CNTRLPLANE conventions](cntrlplane.md) — project-level conventions (version normalization, parent linking)
- [OCPBUGS conventions](ocpbugs.md) — bug-specific version fields
- [GCP HCP conventions](gcp-hcp.md) — GCP-specific HyperShift conventions (Hypershift on GKE)
