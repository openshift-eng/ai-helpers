---
description: Clone GitHub issues to Jira with proper formatting and linking
argument-hint: <issue-number> [issue-number...] [--github-project <org/repo>] [--jira-project <key>] [--dryrun]
---

## Name
jira:clone-from-github

## Synopsis
```
/jira:clone-from-github <issue-number> [issue-number...] [options]
```

## Description
The `jira:clone-from-github` command clones one or more GitHub issues to Jira, preserving the original issue content and establishing a link between the GitHub and Jira issues. This command is useful for:

- Migrating GitHub issues to Jira for project tracking
- Creating Jira tickets that track upstream GitHub issues
- Maintaining synchronization between GitHub and Jira workflows
- Bulk importing GitHub issues into Jira projects

The command uses the [gh2jira utility](https://github.com/oceanc80/gh2jira) to perform the cloning operation. Use `/jira:setup-gh2jira` to install and configure gh2jira if you haven't already.

## Implementation

### 📋 Phase 1: Validate Prerequisites and Locate Installation

Check that the gh2jira utility is available and configured:

1. **Locate gh2jira binary and installation directory**:
   ```bash
   # Find the gh2jira binary
   GH2JIRA_BIN=$(which gh2jira 2>/dev/null)

   if [ -z "$GH2JIRA_BIN" ]; then
     echo "gh2jira not found. Run /jira:setup-gh2jira to install."
     exit 1
   fi

   # If it's a symlink, resolve it to find the actual installation
   if [ -L "$GH2JIRA_BIN" ]; then
     GH2JIRA_BIN=$(readlink "$GH2JIRA_BIN")
   fi

   # Get the directory containing the gh2jira binary
   GH2JIRA_DIR=$(dirname "$GH2JIRA_BIN")

   echo "Found gh2jira at: $GH2JIRA_DIR"
   ```

2. **Verify configuration files exist in installation directory**:
   ```bash
   cd "$GH2JIRA_DIR" || exit 1

   # Check for tokenstore.yaml
   if [ ! -f "tokenstore.yaml" ]; then
     echo "tokenstore.yaml not found in $GH2JIRA_DIR"
     echo "Run /jira:setup-gh2jira to configure authentication."
     exit 1
   fi

   # Check for profiles.yaml (optional)
   if [ -f "profiles.yaml" ]; then
     echo "Found profiles.yaml"
   fi
   ```

3. **Verify tokens are configured**:
   - Check that `tokenstore.yaml` contains actual tokens (not placeholder values)
   - GitHub token should not contain "YOUR_GITHUB_TOKEN"
   - Jira token should not contain "YOUR_JIRA_TOKEN"

**IMPORTANT**: All gh2jira commands MUST be executed from the `$GH2JIRA_DIR` directory to ensure configuration files are properly loaded.

**If prerequisites are missing:**
- Inform user about missing requirements
- Provide instructions from gh2jira README on setting up:
  - GitHub Personal Access Token (scope: public_repo, read:project)
  - Jira Personal Access Token
  - Creating tokenstore.yaml file

### 🔍 Phase 2: Parse Arguments

Parse command arguments:

**Required arguments:**
- `issue-number`: One or more GitHub issue numbers (e.g., `123`, `456 789`)

**Optional flags:**
- `--github-project <org/repo>`: GitHub project (e.g., `operator-framework/operator-lifecycle-manager`)
  - Can also use profile name if configured in profiles.yaml
- `--jira-project <key>`: Target Jira project (e.g., `OCPBUGS`, `CNTRLPLANE`)
- `--profile <name>`: Use named profile from profiles.yaml
- `--dryrun`: Show what would be created without actually creating Jira issues

**Argument validation:**
- At least one issue number must be provided
- Issue numbers must be numeric
- If `--profile` is not used, `--github-project` and `--jira-project` are typically required

### 🔧 Phase 3: Build gh2jira Command

Construct the gh2jira clone command based on provided arguments:

**Basic command structure:**
```bash
gh2jira clone <issue-number> [issue-number...] [flags]
```

**Flag mapping:**
- `--github-project` → `--github-project org/repo`
- `--jira-project` → `--jira-project KEY`
- `--profile` → `--profile-name name`
- `--dryrun` → `--dryrun`

**Example commands:**
```bash
# Using profile
gh2jira clone 123 456 --profile-name my-profile --dryrun

# Using explicit projects
gh2jira clone 123 --github-project operator-framework/olm --jira-project OCPBUGS

# Multiple issues with dryrun
gh2jira clone 100 101 102 --profile-name default --dryrun
```

### ▶️ Phase 4: Execute Clone Operation

1. **Run the gh2jira command from installation directory**:
   ```bash
   # IMPORTANT: Change to gh2jira installation directory
   cd "$GH2JIRA_DIR" || exit 1

   # Execute the gh2jira clone command
   gh2jira clone <issue-number> [issue-number...] [flags]
   ```
   - Execute the constructed command from `$GH2JIRA_DIR`
   - Capture stdout and stderr
   - Monitor exit code

2. **Handle dryrun output**:
   - If `--dryrun` was specified, display the Jira issue that would be created
   - Show issue title, description, and fields
   - Ask user if they want to proceed with actual creation

3. **Handle actual clone output**:
   - Display progress for each issue being cloned
   - Show created Jira issue keys and URLs
   - Report any errors or failures

**Note**: Running from `$GH2JIRA_DIR` ensures that `tokenstore.yaml`, `profiles.yaml`, and `workflows.yaml` are found correctly.

### 📊 Phase 5: Display Results

Format and display results to the user:

**Success output (per issue):**
```
✓ Cloned GitHub issue #123 → OCPBUGS-4567
  Title: <issue title>
  URL: https://issues.redhat.com/browse/OCPBUGS-4567
  GitHub link: https://github.com/org/repo/issues/123
```

**Dryrun output:**
```
[DRYRUN] Would create Jira issue from GitHub #123:

Project: OCPBUGS
Type: Bug
Title: <issue title>
Description:
<formatted description with GitHub link>

Labels: <labels>
```

**Error output:**
```
✗ Failed to clone GitHub issue #123
  Error: <error message>

Suggestions:
- Verify GitHub issue exists and is accessible
- Check authentication tokens are valid
- Ensure Jira project accepts this issue type
```

**Summary:**
```
Cloned 3 of 5 GitHub issues successfully:
✓ #123 → OCPBUGS-4567
✓ #124 → OCPBUGS-4568
✓ #125 → OCPBUGS-4569
✗ #126 - Issue not found
✗ #127 - Permission denied
```

## Return Value

- **Success**: List of created Jira issue keys with URLs
- **Dryrun**: Preview of issues that would be created
- **Error**: Error messages with suggestions for resolution

## Examples

### Example 1: Clone single issue using profile
```
/jira:clone-from-github 123 --profile olm-project
```
Uses the `olm-project` profile configuration to clone GitHub issue #123.

### Example 2: Clone multiple issues with explicit projects
```
/jira:clone-from-github 456 789 --github-project operator-framework/operator-lifecycle-manager --jira-project OCPBUGS
```
Clones GitHub issues #456 and #789 from the specified GitHub project to OCPBUGS.

### Example 3: Dryrun before cloning
```
/jira:clone-from-github 100 --profile default --dryrun
```
Shows what Jira issue would be created without actually creating it.

### Example 4: Clone with explicit configuration
```
/jira:clone-from-github 200 201 202 --github-project openshift/origin --jira-project OCPBUGS
```
Clones three GitHub issues from openshift/origin to OCPBUGS project.

## Arguments

- **$1+ – issue-number(s)** *(required)*
  One or more GitHub issue numbers to clone. Can be space-separated.
  **Example:** `123` or `123 456 789`

- **--github-project** *(optional)*
  GitHub project in format `org/repo` (e.g., `operator-framework/operator-lifecycle-manager`).
  **Not required if:** using `--profile`

- **--jira-project** *(optional)*
  Target Jira project key (e.g., `OCPBUGS`, `CNTRLPLANE`).
  **Not required if:** using `--profile`

- **--profile** *(optional)*
  Named profile from profiles.yaml that contains GitHub and Jira project mappings.
  **Example:** `--profile olm-project`

- **--dryrun** *(optional)*
  Preview what would be created without actually creating Jira issues.
  **Recommended** for first-time use or when cloning many issues.

## Configuration

### TokenStore Setup

The command requires a `tokenstore.yaml` file in the gh2jira directory:

```yaml
schema: gh2jira.tokenstore
authTokens:
  jira: <your-jira-pat>
  github: <your-github-pat>
```

**Creating tokens:**
- **GitHub**: Personal Access Token with scopes `public_repo` and `read:project`
  - Create at: https://github.com/settings/tokens
- **Jira**: Personal Access Token
  - Create at: https://id.atlassian.com/manage-profile/security/api-tokens (for Jira Cloud)
  - Or follow your organization's Jira PAT creation process

### Profiles Setup (Optional)

Create `profiles.yaml` in the gh2jira directory for easier management:

```yaml
profiles:
- description: OLM Project
  githubConfig:
     project: operator-framework/operator-lifecycle-manager
  jiraConfig:
     project: OCPBUGS
  tokenStore: tokenstore.yaml
- description: OpenShift Origin
  githubConfig:
     project: openshift/origin
  jiraConfig:
     project: OCPBUGS
```

Then use with `--profile "OLM Project"` instead of specifying projects each time.

### Workflows Configuration

The gh2jira utility uses `workflows.yaml` for state mapping. The default configuration is:

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

This is used by the reconcile command but may affect clone behavior.

## Error Handling

### gh2jira Binary Not Found

**Scenario:** The gh2jira binary doesn't exist.

**Action:**
```
The gh2jira utility is not installed.

Please run /jira:setup-gh2jira to install and configure gh2jira.
```

### Missing TokenStore

**Scenario:** tokenstore.yaml doesn't exist.

**Action:**
```
TokenStore configuration not found.

Please run /jira:setup-gh2jira to configure gh2jira with your GitHub and Jira tokens.

Alternatively, you can manually create the tokenstore.yaml file:

1. Create GitHub Personal Access Token:
   - Go to: https://github.com/settings/tokens
   - Scopes: public_repo, read:project

2. Create Jira Personal Access Token:
   - Follow your organization's process

3. Create tokenstore.yaml in the gh2jira installation directory:

cat > tokenstore.yaml << 'EOF'
schema: gh2jira.tokenstore
authTokens:
  jira: YOUR_JIRA_TOKEN
  github: YOUR_GITHUB_TOKEN
EOF
```

### GitHub Issue Not Found

**Scenario:** Specified GitHub issue doesn't exist or is inaccessible.

**Action:**
```
GitHub issue #999 not found in operator-framework/operator-lifecycle-manager

Possible causes:
- Issue number is incorrect
- Issue is in a different repository
- Repository is private and token lacks access
- Issue has been deleted

Please verify:
- Issue exists at: https://github.com/operator-framework/operator-lifecycle-manager/issues/999
- Your GitHub token has access to this repository
```

### Jira Project Not Found

**Scenario:** Target Jira project doesn't exist or user lacks access.

**Action:**
```
Jira project "INVALIDPROJ" not found or inaccessible

Possible causes:
- Project key is incorrect
- You don't have permission to create issues in this project
- Project doesn't exist in your Jira instance

Please verify:
- Project exists in Jira
- You have "Create Issues" permission
- Project key is correct (usually all caps, e.g., OCPBUGS)
```

### Authentication Failure

**Scenario:** GitHub or Jira tokens are invalid or expired.

**Action:**
```
Authentication failed for GitHub/Jira

Please check your tokens in tokenstore.yaml:
- Verify tokens are not expired
- Ensure tokens have required permissions
- Try regenerating tokens if issues persist

GitHub token scopes required: public_repo, read:project
Jira token: Must have issue creation permissions
```

### Issue Already Exists

**Scenario:** A Jira issue may already exist for this GitHub issue.

**Action:**
```
A Jira issue may already exist for GitHub #123

Existing issue: OCPBUGS-4567
Created: 2024-01-15
URL: https://issues.redhat.com/browse/OCPBUGS-4567

Options:
1. Skip this issue (recommended)
2. Create duplicate anyway
3. Update existing issue

What would you like to do?
```

## Best Practices

1. **Use --dryrun first**: Always preview what will be created before bulk cloning
2. **Set up profiles**: Create profiles.yaml for projects you clone from frequently
3. **Verify tokens**: Ensure your tokens have appropriate permissions
4. **Check issue states**: Review GitHub issues before cloning to ensure they're relevant
5. **Batch responsibly**: Clone in reasonable batches (10-20 issues at a time)
6. **Document links**: The command automatically adds GitHub links to Jira issues

## See Also

- `/jira:setup-gh2jira` - Install and configure gh2jira
- `/jira:reconcile-github` - Reconcile state between GitHub and Jira issues
- `/jira:create` - Create new Jira issues manually
- `/jira:solve` - Analyze and solve Jira issues
- [gh2jira README](https://github.com/oceanc80/gh2jira/blob/main/README.md)
