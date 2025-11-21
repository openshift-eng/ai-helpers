---
description: Reconcile state mismatches between GitHub and Jira issues
argument-hint: [--github-project <org/repo>] [--jira-project <key>] [--profile <name>] [--porcelain] [--output json|yaml]
---

## Name
jira:reconcile-github

## Synopsis
```bash
/jira:reconcile-github [options]
```

## Description
The `jira:reconcile-github` command identifies and reports state mismatches between linked GitHub and Jira issues according to a configurable state mapping. This command is useful for:

- Ensuring Jira issues stay synchronized with their linked GitHub issues
- Identifying issues that need status updates
- Maintaining workflow consistency between GitHub and Jira
- Auditing cross-platform issue tracking accuracy

The command uses the [gh2jira utility](https://github.com/oceanc80/gh2jira) to perform the reconciliation. Use `/jira:setup-gh2jira` to install and configure gh2jira if you haven't already.

## Implementation

### 📋 Phase 1: Validate Prerequisites

Check that the gh2jira utility is available and configured:

1. **Verify gh2jira binary exists**:
   ```bash
   which gh2jira || echo "gh2jira not found. Run /jira:setup-gh2jira to install."
   ```

2. **Verify configuration files exist**:
   - Check for `tokenstore.yaml` in the gh2jira directory
   - Check for `profiles.yaml` if using profiles
   - Check for `workflows.yaml` for state mapping configuration
   - If missing, provide instructions on creating them

3. **Check for required tokens**:
   - GitHub token (in tokenstore.yaml)
   - Jira token (in tokenstore.yaml)

**If prerequisites are missing:**
- Inform user about missing requirements
- Provide setup instructions (see Error Handling section)

### 🔍 Phase 2: Parse Arguments

Parse command arguments:

**Optional flags:**
- `--github-project <org/repo>`: GitHub project (e.g., `operator-framework/operator-lifecycle-manager`)
- `--jira-project <key>`: Jira project to reconcile (e.g., `OCPBUGS`, `CNTRLPLANE`)
- `--profile <name>`: Use named profile from profiles.yaml
- `--porcelain`: Output in machine-readable format for scripting
- `--output <format>`: Output format for porcelain mode (`json` or `yaml`, default: `json`)

**Argument validation:**
- If `--profile` is not used, both `--github-project` and `--jira-project` should be provided
- If `--porcelain` is used, `--output` specifies the format

### 🔧 Phase 3: Build gh2jira Command

Construct the gh2jira reconcile command based on provided arguments:

**Basic command structure:**
```bash
gh2jira reconcile [flags]
```

**Flag mapping:**
- `--github-project` → `--github-project org/repo`
- `--jira-project` → `--jira-project KEY`
- `--profile` → `--profile-name name`
- `--porcelain` → `--porcelain`
- `--output` → `--output json|yaml`

**Example commands:**
```bash
# Using profile
gh2jira reconcile --profile-name my-profile

# Using explicit projects
gh2jira reconcile --github-project operator-framework/olm --jira-project OCPBUGS

# Porcelain output for scripting
gh2jira reconcile --profile-name default --porcelain --output json
```

### ▶️ Phase 4: Execute Reconciliation

1. **Run the gh2jira command**:
   - Execute the constructed command
   - Capture stdout and stderr
   - Monitor exit code

2. **Parse reconciliation output**:
   - The command identifies Jira issues with GitHub links
   - Compares states according to workflows.yaml mapping
   - Reports mismatches

3. **Process results**:
   - Parse output (either human-readable or porcelain format)
   - Categorize mismatches by type
   - Calculate statistics

### 📊 Phase 5: Display Results

Format and display results to the user based on output mode:

**Human-readable output (default):**
```text
Reconciliation Report
=====================

Found 25 Jira issues with GitHub links

State Mismatches (5):
---------------------
1. OCPBUGS-4567 ↔ GitHub #123
   Jira: "In Progress" | GitHub: "closed"
   Expected Jira states: Done, Dev Complete, Release Pending
   → Jira issue should be closed

2. OCPBUGS-4568 ↔ GitHub #456
   Jira: "Done" | GitHub: "open"
   Expected Jira states: To Do, In Progress, New, Code Review
   → Jira issue was closed but GitHub issue is still open

Summary:
--------
Total issues checked: 25
Synchronized: 20 (80%)
Mismatched: 5 (20%)
```

**Porcelain output (--porcelain --output json):**
```json
{
  "total_issues": 25,
  "synchronized": 20,
  "mismatched": 5,
  "mismatches": [
    {
      "jira_key": "OCPBUGS-4567",
      "jira_state": "In Progress",
      "github_issue": 123,
      "github_state": "closed",
      "expected_jira_states": ["Done", "Dev Complete", "Release Pending"]
    }
  ]
}
```

## Return Value

- **Success**: Reconciliation report with statistics and mismatches
- **Porcelain mode**: Machine-readable JSON or YAML output
- **Error**: Error messages with troubleshooting guidance

## Examples

### Example 1: Reconcile using profile
```bash
/jira:reconcile-github --profile olm-project
```
Uses the `olm-project` profile to reconcile all linked issues.

### Example 2: Reconcile with explicit projects
```bash
/jira:reconcile-github --github-project operator-framework/operator-lifecycle-manager --jira-project OCPBUGS
```
Reconciles issues between the specified GitHub and Jira projects.

### Example 3: Machine-readable output for scripting
```bash
/jira:reconcile-github --profile default --porcelain --output json
```
Outputs reconciliation results in JSON format for automated processing.

## Arguments

- **--github-project** *(optional)*
  GitHub project in format `org/repo` (e.g., `operator-framework/operator-lifecycle-manager`).
  **Not required if:** using `--profile`

- **--jira-project** *(optional)*
  Jira project key to reconcile (e.g., `OCPBUGS`, `CNTRLPLANE`).
  **Not required if:** using `--profile`

- **--profile** *(optional)*
  Named profile from profiles.yaml that contains GitHub and Jira project mappings.
  **Example:** `--profile olm-project`

- **--porcelain** *(optional)*
  Output in machine-readable format for scripts and automation.
  **Use with:** `--output` to specify format

- **--output** *(optional)*
  Output format when using `--porcelain`.
  **Options:** `json` (default) | `yaml`

## Configuration

### Workflows Configuration

The reconciliation logic uses `workflows.yaml` to define state mappings:

**Default configuration** (workflows.yaml in gh2jira installation directory):

```yaml
schema: gh2jira.workflows
name: jira
mappings:
  - ghstate: "open"
    jstates:
      - "To Do"
      - "In Progress"
      - "New"
      - "Code Review"
  - ghstate: "closed"
    jstates:
      - "Done"
      - "Dev Complete"
      - "Release Pending"
```

**How it works:**
- When a GitHub issue is "open", the linked Jira issue should be in one of: To Do, In Progress, New, or Code Review
- When a GitHub issue is "closed", the linked Jira issue should be in one of: Done, Dev Complete, or Release Pending
- Mismatches are reported when the Jira state doesn't match the expected states for the GitHub state

## Error Handling

### gh2jira Binary Not Found

**Scenario:** The gh2jira binary doesn't exist.

**Action:**
```text
The gh2jira utility is not installed.

Please run /jira:setup-gh2jira to install and configure gh2jira.
```

### Missing TokenStore

**Scenario:** tokenstore.yaml doesn't exist.

**Action:** Provide setup instructions (same as clone-from-github command).

### Missing Workflows Configuration

**Scenario:** workflows.yaml doesn't exist.

**Action:**
```text
Workflows configuration not found.

Please run /jira:setup-gh2jira to configure gh2jira, which will create the default workflows.yaml configuration.

Alternatively, create workflows.yaml manually in the gh2jira installation directory:

cat > workflows.yaml << 'EOF'
schema: gh2jira.workflows
name: jira
mappings:
  - ghstate: "open"
    jstates:
      - "To Do"
      - "In Progress"
      - "New"
      - "Code Review"
  - ghstate: "closed"
    jstates:
      - "Done"
      - "Dev Complete"
      - "Release Pending"
EOF
```

## Best Practices

1. **Run regularly**: Schedule reconciliation checks weekly or after major releases
2. **Use porcelain for automation**: Integrate with CI/CD or reporting tools using JSON/YAML output
3. **Customize workflows**: Edit workflows.yaml to match your team's Jira workflow states
4. **Review mismatches**: Investigate patterns in mismatches to improve processes

## See Also

- `/jira:setup-gh2jira` - Install and configure gh2jira
- `/jira:clone-from-github` - Clone GitHub issues to Jira
- `/jira:solve` - Analyze and solve Jira issues
- `/jira:status-rollup` - Create status rollup reports
- [gh2jira README](https://github.com/oceanc80/gh2jira/blob/main/README.md)
