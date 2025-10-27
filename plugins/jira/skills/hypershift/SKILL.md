---
name: HyperShift Jira Conventions
description: HyperShift team-specific Jira requirements for component selection and conventions
---

# HyperShift Jira Conventions

This skill provides HyperShift team-specific conventions for creating Jira issues in CNTRLPLANE and OCPBUGS projects.

## When to Use This Skill

This skill is automatically invoked when:
- Summary or description contains HyperShift keywords: "HyperShift", "ARO HCP", "ROSA HCP", "hosted control plane"
- Component contains "HyperShift"
- User explicitly requests HyperShift conventions

This skill works **in conjunction with** the `cntrlplane` skill, adding HyperShift-specific requirements on top of generic CNTRLPLANE/OCPBUGS conventions.

## Component Requirements

**ALL** HyperShift issues in CNTRLPLANE and OCPBUGS **must** have a component set to one of:

1. **HyperShift / ARO** - ARO HCP (Azure Red Hat OpenShift Hosted Control Planes)
2. **HyperShift / ROSA** - ROSA HCP (Red Hat OpenShift Service on AWS Hosted Control Planes)
3. **HyperShift** - When it's not clear if the issue is about AWS, Azure, or agent platform

### Component Selection Logic

**Auto-detection based on summary/description keywords:**

| Keywords | Component | Confidence |
|----------|-----------|------------|
| ARO, Azure, "ARO HCP" | **HyperShift / ARO** | High |
| ROSA, AWS, "ROSA HCP" | **HyperShift / ROSA** | High |
| Both ARO and ROSA mentioned | **HyperShift** | High (multi-platform) |
| "All platforms", "platform-agnostic" | **HyperShift** | Medium (verify with user) |
| **No platform keywords** | **Prompt user** | N/A (cannot auto-detect) |

**Important:** If no platform keywords are found, do NOT assume platform-agnostic. Prompt the user to clarify which component.

**Examples:**
```
Summary: "Enable autoscaling for ROSA HCP clusters"
→ Component: HyperShift / ROSA (auto-detected)

Summary: "ARO HCP control plane pods crash on upgrade"
→ Component: HyperShift / ARO (auto-detected)

Summary: "Multi-cloud support for ARO and ROSA HCP"
→ Component: HyperShift (auto-detected, mentions both platforms)

Summary: "Improve control plane pod scheduling"
→ Component: Prompt user (no keywords, cannot determine platform)
```

### When Auto-Detection is Uncertain

If component cannot be confidently auto-detected:
1. Present options to user with descriptions
2. Ask for clarification

**Prompt example:**
```
Which HyperShift platform does this issue affect?

1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues or affects both

Select (1-3):
```

## Version Defaults

HyperShift team uses specific version defaults:

### CNTRLPLANE Issues

**Target Version** (customfield_12319940):
- **Default:** `openshift-4.21`
- **Override:** User may specify different versions (e.g., `4.20`, `4.22`, `4.23`)

### OCPBUGS Issues

**Affects Version/s**:
- **Default:** `4.21`
- **User should specify:** The actual version where the bug was found

**Target Version** (customfield_12319940):
- **Default:** `4.21`
- **Override:** May be different based on severity and backport requirements

## Labels

In addition to `ai-generated-jira` (from CNTRLPLANE skill), HyperShift issues may include:

**Platform-specific:**
- `aro-hcp` - ARO HCP specific
- `rosa-hcp` - ROSA HCP specific

**Feature area:**
- `autoscaling`
- `networking`
- `observability`
- `upgrade`
- `lifecycle`

**Priority/type:**
- `technical-debt`
- `security`
- `performance`

## MCP Tool Integration

### For HyperShift Stories/Tasks in CNTRLPLANE

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<issue summary>",
    issue_type="Story" | "Task" | "Epic" | "Feature",
    description="<formatted description>",
    components="HyperShift / ARO" | "HyperShift / ROSA" | "HyperShift",
    additional_fields={
        "customfield_12319940": "openshift-4.21",  # target version
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For HyperShift Bugs in OCPBUGS

```python
mcp__atlassian__jira_create_issue(
    project_key="OCPBUGS",
    summary="<bug summary>",
    issue_type="Bug",
    description="<formatted bug template>",
    components="HyperShift / ARO" | "HyperShift / ROSA" | "HyperShift",
    additional_fields={
        "versions": [{"name": "4.21"}],          # affects version
        "customfield_12319940": "4.21",           # target version
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

## Examples

### Example 1: ROSA HCP Story (Auto-Detection)

**Input:**
```bash
/jira:create story CNTRLPLANE "Enable automatic node pool scaling for ROSA HCP"
```

**Auto-detected:**
- Component: **HyperShift / ROSA** (detected from "ROSA HCP")
- Target Version: openshift-4.21
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- User story format (As a... I want... So that...)
- Acceptance criteria

**Result:**
- Story created with HyperShift / ROSA component
- All CNTRLPLANE conventions applied

### Example 2: ARO HCP Bug

**Input:**
```bash
/jira:create bug "ARO HCP control plane pods crash on upgrade"
```

**Auto-detected:**
- Project: OCPBUGS (default for bugs)
- Component: **HyperShift / ARO** (detected from "ARO HCP")
- Affected Version: 4.21 (default, user can override)
- Target Version: 4.21
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- Bug template sections

**Result:**
- Bug created in OCPBUGS with HyperShift / ARO component

### Example 3: Platform-Agnostic Epic

**Input:**
```bash
/jira:create epic CNTRLPLANE "Improve HyperShift operator observability"
```

**Auto-detected:**
- Component: **HyperShift** (platform-agnostic, from "HyperShift operator")
- Target Version: openshift-4.21
- Epic Name: Same as summary
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- Epic objective and scope
- Acceptance criteria

**Result:**
- Epic created with HyperShift component (not platform-specific)

### Example 4: Multi-Platform Feature

**Input:**
```bash
/jira:create feature CNTRLPLANE "Advanced observability for ROSA and ARO HCP"
```

**Auto-detected:**
- Component: **HyperShift** (affects both platforms)
- Target Version: openshift-4.21
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- Market problem
- Strategic value
- Success criteria
- Epic breakdown

**Result:**
- Feature with HyperShift component (since it affects both platforms)

### Example 5: Uncertain Component (Prompts User)

**Input:**
```bash
/jira:create story CNTRLPLANE "Improve control plane pod scheduling"
```

**Detection:** Summary doesn't contain platform-specific keywords

**Prompt:**
```
Which HyperShift platform does this issue affect?

1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues or affects both

Select (1-3):
```

**User selects:** 3

**Result:**
- Component set to **HyperShift**

## Component Override

User can override auto-detection using `--component` flag:

```bash
# Override auto-detection
/jira:create story CNTRLPLANE "Enable autoscaling for ROSA HCP" --component "HyperShift"
```

This will use "HyperShift" component instead of auto-detected "HyperShift / ROSA".

## Error Handling

### Invalid Component

**Scenario:** User specifies component that's not a valid HyperShift component.

**Action:**
```
Component "Networking" is not a valid HyperShift component.

HyperShift issues must use one of:
- HyperShift / ARO
- HyperShift / ROSA
- HyperShift

Which component would you like to use?
```

### Component Required but Missing

**Scenario:** Component cannot be auto-detected and user didn't specify.

**Action:**
```
HyperShift issues require a component. Which component?

1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues

Select (1-3):
```

## Workflow Summary

When creating a HyperShift issue:

1. ✅ **CNTRLPLANE skill loads** - Applies generic conventions (security, labels, versions)
2. ✅ **HyperShift skill loads** - Adds HyperShift-specific requirements
3. 🔍 **Auto-detect component** - Analyze summary/description for ARO/ROSA keywords
4. ⚙️ **Apply component:**
   - If auto-detected with high confidence → Use detected component
   - If uncertain → Prompt user for component selection
   - If `--component` flag provided → Use specified component (validate it's HyperShift)
5. 💬 **Interactive prompts** - Collect issue type-specific information
6. 🔒 **Security scan** - Validate no credentials/secrets
7. ✅ **Create issue** - Use MCP tool with HyperShift component
8. 📤 **Return result** - Issue key, URL, applied defaults (including component)

## Best Practices

1. **Include platform keywords in summary** - Makes auto-detection more accurate
   - ✅ "Enable autoscaling for ROSA HCP"
   - ❌ "Enable autoscaling" (unclear which platform)

2. **Be specific about platform when known**
   - If issue is ARO-specific, mention "ARO" or "Azure" in summary
   - If issue is ROSA-specific, mention "ROSA" or "AWS" in summary

3. **Use platform-agnostic component wisely**
   - Only use "HyperShift" (without /ARO or /ROSA) when issue truly affects all platforms
   - When in doubt, ask the team

4. **Component consistency within epic**
   - Stories within an epic should generally have the same component as the epic
   - Exception: Epic is platform-agnostic but stories target specific platforms

## See Also

- `/jira:create` - Main command that invokes this skill
- `cntrlplane` skill - Generic CNTRLPLANE/OCPBUGS conventions
- HyperShift team documentation
