---
name: Create Jira Bug
description: Implementation guide for creating well-formed Jira bug reports
---

# Create Jira Bug

This skill provides implementation guidance for creating well-structured Jira bug reports with complete reproduction steps and clear problem descriptions.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create bug` command to guide the bug creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Bug information available (problem description, steps to reproduce, etc.)

## Bug Report Best Practices

### Complete Information

A good bug report contains:
1. **Clear summary** - Brief description that identifies the problem
2. **Detailed description** - Complete context and background
3. **Reproducibility** - How often the bug occurs
4. **Steps to reproduce** - Exact sequence to trigger the bug
5. **Actual vs expected results** - What happens vs what should happen
6. **Environment details** - Version, platform, configuration
7. **Additional context** - Logs, screenshots, error messages

### Summary Guidelines

The summary should:
- Be concise (one sentence)
- Identify the problem clearly
- Include key context when helpful
- Avoid vague terms like "broken" or "doesn't work"

**Good examples:**
- "API server returns 500 error when creating namespaces"
- "Control plane pods crash on upgrade from 4.20 to 4.21"
- "Memory leak in etcd container after 24 hours"

**Bad examples:**
- "Things are broken"
- "Error in production"
- "Fix the bug"

## Bug Description Template

Use this template structure for consistency:

```
Description of problem:
<Clear, detailed description of the issue>

Version-Release number of selected component (if applicable):
<e.g., 4.21.0, openshift-client-4.20.5>

How reproducible:
<Always | Sometimes | Rarely>

Steps to Reproduce:
1. <First step - be specific>
2. <Second step>
3. <Third step>

Actual results:
<What actually happens - include error messages>

Expected results:
<What should happen instead>

Additional info:
<Logs, screenshots, stack traces, related issues, workarounds>
```

## Interactive Bug Collection Workflow

When creating a bug, guide the user through each section interactively:

### 1. Problem Description

**Prompt:** "What is the problem? Describe it clearly and in detail."

**Tips to share:**
- Provide context: What were you trying to do?
- Be specific: What component or feature is affected?
- Include impact: Who is affected? How severe is it?

**Example response:**
```
The kube-apiserver pod crashes immediately after upgrading a hosted control plane cluster from version 4.20 to 4.21. The pod enters CrashLoopBackOff state and all API requests to the cluster fail.
```

### 2. Version Information

**Prompt:** "Which version exhibits this issue? (e.g., 4.21.0, 4.20.5)"

**Tips:**
- Include full version number if known
- Specify component version if different from platform version
- Note if issue affects multiple versions

**Default:** Use project-specific default (e.g., 4.21 for OCPBUGS)

### 3. Reproducibility

**Prompt:** "How reproducible is this issue?"

**Options:**
- **Always** - Happens every time following the steps
- **Sometimes** - Happens intermittently, even with same steps
- **Rarely** - Hard to reproduce, happened once or few times

**Use case for each:**
- Always: Easiest to debug and fix
- Sometimes: May be timing-related or race condition
- Rarely: May be environmental or complex interaction

### 4. Steps to Reproduce

**Prompt:** "What are the exact steps to reproduce this issue? Be as specific as possible."

**Guidelines:**
- Number each step
- Be precise (exact commands, button clicks, inputs)
- Include environment setup if needed
- Use code blocks for commands
- Mention any prerequisites

**Example:**
```
Steps to Reproduce:
1. Create a ROSA HCP cluster on version 4.20.0:
   rosa create cluster --name test-cluster --version 4.20.0 --hosted-cp
2. Wait for cluster to be fully ready (about 15 minutes)
3. Initiate upgrade to 4.21.0:
   rosa upgrade cluster --cluster test-cluster --version 4.21.0
4. Monitor the control plane pods:
   oc get pods -n clusters-test-cluster -w
5. Observe kube-apiserver pod status
```

**Validation:**
- Ensure at least one step is provided
- Check that steps are numbered/ordered
- Verify steps are specific enough to follow

### 5. Actual Results

**Prompt:** "What actually happens when you follow those steps?"

**Guidelines:**
- Describe exactly what occurs
- Include error messages (full text)
- Mention symptoms (crashes, hangs, wrong output)
- Include relevant logs or stack traces
- Note timing (immediate, after 5 minutes, etc.)

**Example:**
```
Actual results:
The kube-apiserver pod crashes immediately after the upgrade completes. The pod restarts continuously (CrashLoopBackOff). Error in pod logs:

panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x...]

API requests to the cluster fail with:
Error from server: error dialing backend: dial tcp: lookup kube-apiserver: no such host
```

### 6. Expected Results

**Prompt:** "What should happen instead? What is the expected behavior?"

**Guidelines:**
- Describe the correct behavior
- Be specific about expected state/output
- Contrast with actual results

**Example:**
```
Expected results:
The kube-apiserver pod should start successfully after the upgrade. The pod should be in Running state, and API requests to the cluster should succeed normally.
```

**Validation:**
- Ensure expected results differ from actual results
- Check that expected behavior is clearly stated

### 7. Additional Information

**Prompt:** "Any additional context? (Optional: logs, screenshots, workarounds, related issues)"

**Helpful additions:**
- Full logs or log excerpts
- Screenshots or recordings
- Stack traces
- Related Jira issues or documentation
- Workarounds discovered
- Impact assessment (severity, affected users)
- Environment specifics (region, network config, etc.)

**Example:**
```
Additional info:
- Cluster ID: abc123-def456
- Region: us-east-1
- Full pod logs attached: kube-apiserver.log
- Related issue: OCPBUGS-12340 (similar crash in 4.19→4.20 upgrade)
- Workaround: Rollback to 4.20.0 and cluster recovers
- Affects all ROSA HCP clusters in production
```

## Component and Version Handling

### Auto-Detection

Analyze the bug description for component hints:
- Product names: "OpenShift", "ROSA", "ARO", "HyperShift"
- Component names: "API server", "etcd", "networking", "storage"
- Platform: "AWS", "Azure", "GCP", "bare metal"

### Version Fields

Different projects may use versions differently:

**OCPBUGS:**
- **Affects Version/s** (`versions`): Version where bug was found
- **Target Version** (`customfield_12319940`): Version where fix is targeted
- Never set **Fix Version/s** (`fixVersions`)

**General projects:**
- May only have **Affects Version/s**
- Check project configuration for version fields

### Project-Specific Overrides

If bug is for a known project with specific conventions (e.g., CNTRLPLANE/OCPBUGS), the cntrlplane skill will be invoked automatically and will override defaults.

## Field Validation

Before submitting the bug, validate:

### Required Fields
- ✅ Summary is not empty and is clear
- ✅ Description contains problem description
- ✅ Component is specified (or project doesn't require it)
- ✅ Affects version is specified (if required by project)

### Description Quality
- ✅ "Steps to Reproduce" has at least one step
- ✅ "Actual results" is different from "Expected results"
- ✅ "How reproducible" is specified (Always/Sometimes/Rarely)

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ Logs are sanitized (passwords, tokens redacted)
- ✅ Screenshots don't expose sensitive information

## MCP Tool Parameters

### Basic Bug Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT_KEY>",  # e.g., "OCPBUGS", "MYPROJECT"
    summary="<bug summary>",
    issue_type="Bug",
    description="<formatted bug template>",
    components="<component name>",  # optional, if required by project
    additional_fields={
        "versions": [{"name": "<version>"}],  # affects version, if supported
        # Add other project-specific fields as needed
    }
)
```

### With Project-Specific Fields (e.g., OCPBUGS)

```python
mcp__atlassian__jira_create_issue(
    project_key="OCPBUGS",
    summary="Control plane pods crash on upgrade",
    issue_type="Bug",
    description="""
h2. Description of problem

Control plane pods crash immediately after upgrading from 4.20 to 4.21.

h2. Version-Release number

4.21.0

h2. How reproducible

Always

h2. Steps to Reproduce

# Create a cluster on 4.20
# Upgrade to 4.21
# Observe control plane pod status

h2. Actual results

Pods enter CrashLoopBackOff state.

h2. Expected results

Pods should start successfully.

h2. Additional info

Logs attached.
    """,
    components="HyperShift",
    additional_fields={
        "versions": [{"name": "4.21"}],           # affects version
        "customfield_12319940": "4.21",            # target version
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}   # if required
    }
)
```

## Jira Description Formatting

Use Jira's native formatting (Wiki markup):

### Headings
```
h1. Main Heading
h2. Subheading
h3. Sub-subheading
```

### Text Formatting
```
*bold text*
_italic text_
{{monospace}}
{quote}quoted text{quote}
```

### Lists
```
* Bullet item 1
* Bullet item 2
** Nested bullet

# Numbered item 1
# Numbered item 2
```

### Code Blocks
```
{code}
command line text or code
{code}

{code:java}
// Language-specific syntax highlighting
public class Example {}
{code}
```

### Links
```
[Link text|http://example.com]
[OCPBUGS-123]  // Auto-links to Jira issue
```

## Error Handling

### Missing Required Information

**Scenario:** User doesn't provide required fields.

**Action:**
1. Identify missing required fields
2. Prompt user for each missing field
3. Provide context/examples to help
4. Re-validate before submission

**Example:**
```
Summary is required but not provided. Please provide a brief summary of the bug:
Example: "API server crashes when creating namespaces"
```

### Invalid Version

**Scenario:** Specified version doesn't exist in project.

**Action:**
1. Use `mcp__atlassian__jira_get_project_versions` to fetch valid versions
2. Suggest closest match or list available versions
3. Ask user to confirm or select different version

**Example:**
```
Version "4.21.5" not found for project OCPBUGS.
Available versions: 4.19, 4.20, 4.21, 4.22
Did you mean "4.21"?
```

### Component Required But Not Provided

**Scenario:** Project requires component, but none specified.

**Action:**
1. Ask user which component the bug affects
2. If available, fetch and display component list for project
3. Accept user's component selection
4. Validate component exists before submission

### Security Validation Failure

**Scenario:** Sensitive data detected in bug content.

**Action:**
1. STOP submission immediately
2. Inform user what type of data was detected (without echoing it)
3. Provide guidance on redaction
4. Request sanitized version

**Example:**
```
I detected what appears to be an API token in the "Steps to Reproduce" section.
Please replace with a placeholder like "YOUR_API_TOKEN" or "<redacted>" before proceeding.
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the bug.

**Action:**
1. Parse error message
2. Translate to user-friendly explanation
3. Suggest corrective action
4. Offer to retry

**Common errors:**
- **"Field 'component' is required"** → Prompt for component
- **"Version not found"** → Use version error handling
- **"Permission denied"** → User may lack project permissions, inform them to contact admin

## Examples

### Example 1: Simple Bug

**Input:**
```bash
/jira:create bug MYPROJECT "Login button doesn't work on mobile"
```

**Interactive prompts:**
```
What is the problem? Describe it clearly.
> The login button on the mobile app doesn't respond to taps on iOS devices.

Which version exhibits this issue?
> 2.1.0

How reproducible is this issue?
> Always

What are the exact steps to reproduce?
> 1. Open mobile app on iPhone 13 (iOS 16.5)
> 2. Navigate to login screen
> 3. Tap the "Login" button
> 4. Nothing happens

What actually happens?
> The button doesn't respond to taps. No visual feedback, no navigation.

What should happen instead?
> The button should navigate to the credentials input screen when tapped.

Any additional context?
> Works fine on Android. Only affects iOS.
```

**Result:**
- Issue created in MYPROJECT
- Type: Bug
- Summary: "Login button doesn't work on mobile"
- Description: Formatted with bug template

### Example 2: Bug with Auto-Detection (CNTRLPLANE/OCPBUGS)

**Input:**
```bash
/jira:create bug "ROSA HCP control plane pods crash on upgrade"
```

**Auto-applied (via cntrlplane skill):**
- Project: OCPBUGS (default for bugs)
- Component: HyperShift / ROSA (detected from "ROSA HCP")
- Affects Version: 4.21
- Target Version: 4.21
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- Bug template sections (same as Example 1)

**Result:**
- Full bug report created with all CNTRLPLANE conventions applied

### Example 3: Bug with All Fields Provided

**Input:**
```bash
/jira:create bug OCPBUGS "etcd pod OOMKilled after 48 hours" --component "HyperShift" --version "4.21"
```

**Minimal prompts:**
- Description of problem
- Steps to reproduce
- Actual/expected results
- Additional info

**Result:**
- Bug created with provided component and version
- Only prompts for description content

## Best Practices Summary

1. **Clear summaries:** One sentence, specific problem
2. **Complete steps:** Exact sequence to reproduce
3. **Specific results:** Include error messages and symptoms
4. **Sanitize content:** Remove all credentials and secrets
5. **Add context:** Logs, environment details, workarounds
6. **Use template:** Follow standard bug template structure
7. **Validate before submit:** Check all required fields populated

## Workflow Summary

1. ✅ Parse command arguments (project, summary, flags)
2. 🔍 Auto-detect component/version from summary keywords
3. ⚙️ Apply project-specific defaults (if applicable)
4. 💬 Interactively collect bug template sections
5. 🔒 Scan for sensitive data
6. ✅ Validate required fields
7. 📝 Format description with Jira markup
8. ✅ Create bug via MCP tool
9. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill
- `cntrlplane` skill - CNTRLPLANE/OCPBUGS specific conventions
- Jira documentation on bug workflows
