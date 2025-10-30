---
description: Install and configure the gh2jira utility with all required tools and credentials
---

## Name
jira:setup-gh2jira

## Synopsis
```
/jira:setup-gh2jira
```

## Description
The `jira:setup-gh2jira` command guides you through the complete installation and configuration of the [gh2jira utility](https://github.com/oceanc80/gh2jira), which enables cloning and reconciling GitHub issues with Jira. This command:

- Checks for and installs required dependencies (Go)
- Clones and builds the gh2jira utility
- Guides you through creating GitHub and Jira Personal Access Tokens
- Creates and configures `tokenstore.yaml` with your credentials
- Optionally creates `profiles.yaml` for project shortcuts
- Creates default `workflows.yaml` for state mapping
- Adds gh2jira to your PATH for easy access

## Implementation

### 📋 Phase 1: Check Prerequisites

#### 1.1 Verify Go Installation

**Check if Go is installed:**
```bash
go version
```

**If Go is not installed:**
- Display Go version if present
- If missing, provide installation instructions based on platform:

**macOS:**
```bash
# Using Homebrew (recommended)
brew install go

# Or download from: https://go.dev/dl/
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install golang-go

# Fedora/RHEL
sudo dnf install golang

# Or download from: https://go.dev/dl/
```

**Windows:**
- Download installer from: https://go.dev/dl/
- Run the MSI installer
- Verify installation by opening a new terminal and running `go version`

**Minimum Go version:** 1.18 or higher

#### 1.2 Verify Git Installation

```bash
git --version
```

If not installed, provide platform-specific instructions.

#### 1.3 Check for Existing gh2jira Installation

```bash
which gh2jira
```

If gh2jira is found, ask the user if they want to:
1. Reconfigure the existing installation
2. Reinstall from scratch
3. Exit setup

### 🔧 Phase 2: Install gh2jira

#### 2.1 Determine Installation Location

Ask the user where they want to install gh2jira:

**Recommended locations:**
- `~/go/src/github.com/oceanc80/gh2jira` (Go workspace convention)
- `~/.local/bin/gh2jira` (User local binaries)
- Custom path specified by user

**Prompt:**
```
Where would you like to install gh2jira?

1. ~/go/src/github.com/oceanc80/gh2jira (recommended)
2. ~/.local/share/gh2jira
3. Custom path

Enter choice (1-3):
```

Store the chosen installation directory as `$GH2JIRA_DIR`.

#### 2.2 Clone the Repository

```bash
mkdir -p $(dirname $GH2JIRA_DIR)
git clone https://github.com/oceanc80/gh2jira.git $GH2JIRA_DIR
cd $GH2JIRA_DIR
```

**Handle errors:**
- Directory already exists: Ask to remove or use existing
- Network issues: Provide troubleshooting steps
- Permission issues: Suggest using different directory or fixing permissions

#### 2.3 Build gh2jira

```bash
cd $GH2JIRA_DIR
make
```

**Verify build:**
```bash
./gh2jira --version
```

**If build fails:**
- Check Go version meets minimum requirements
- Check for missing dependencies
- Display error message and suggest checking gh2jira README

### 🔐 Phase 3: Configure Authentication

This phase guides the user through creating and configuring authentication tokens.

#### 3.1 Create GitHub Personal Access Token

**Instructions for user:**

```
Creating GitHub Personal Access Token
======================================

1. Open: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Set token description: "gh2jira access"
4. Select scopes:
   ✓ public_repo (Access public repositories)
   ✓ read:project (Read project data)
5. Click "Generate token"
6. Copy the token (you won't see it again!)

IMPORTANT: Keep this token secure. Do not commit it to version control.
```

**Prompt user to enter token:**
```
Please paste your GitHub Personal Access Token:
(input will be hidden)
```

Store in variable: `$GITHUB_TOKEN`

**Validate token:**
```bash
# Test token with a simple API call
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq -r '.login'
```

If successful, display: `✓ GitHub token validated for user: <username>`

If failed:
```
✗ GitHub token validation failed.

Possible issues:
- Token is invalid or expired
- Token doesn't have required scopes
- Network connectivity issues

Please verify your token and try again.
```

#### 3.2 Create Jira Personal Access Token

**Instructions for user:**

```
Creating Jira Personal Access Token
====================================

The process varies by Jira installation:

For Atlassian Cloud (issues.redhat.com, *.atlassian.net):
1. Open: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Enter a label: "gh2jira access"
4. Click "Create"
5. Copy the token

For Jira Data Center/Server:
- Contact your Jira administrator for token creation process
- Some organizations use different authentication methods

For Red Hat Jira:
- May require specific Red Hat SSO or Kerberos setup
- Consult your organization's documentation
```

**Prompt user to enter token:**
```
Please paste your Jira Personal Access Token:
(input will be hidden)

If you're unsure about your Jira token setup, enter 'skip' to configure later.
```

Store in variable: `$JIRA_TOKEN`

**Validate token (optional, requires Jira URL):**
```
Enter your Jira base URL (e.g., https://issues.redhat.com):
```

```bash
# Test token
curl -s -H "Authorization: Bearer $JIRA_TOKEN" "$JIRA_URL/rest/api/2/myself" | jq -r '.displayName'
```

#### 3.3 Create tokenstore.yaml

```bash
cat > $GH2JIRA_DIR/tokenstore.yaml << EOF
schema: gh2jira.tokenstore
authTokens:
  jira: $JIRA_TOKEN
  github: $GITHUB_TOKEN
EOF

# Secure the file (permissions: owner read/write only)
chmod 600 $GH2JIRA_DIR/tokenstore.yaml
```

**Confirm:**
```
✓ Created tokenstore.yaml
✓ File permissions set to 600 (owner read/write only)

Location: $GH2JIRA_DIR/tokenstore.yaml
```

### 📂 Phase 4: Configure Profiles (Optional)

Profiles make it easier to work with specific GitHub/Jira project combinations.

**Ask user:**
```
Would you like to create project profiles?

Profiles allow you to use shortcuts like:
  gh2jira clone 123 --profile-name my-project

Instead of:
  gh2jira clone 123 --github-project org/repo --jira-project KEY

Create profiles now? (y/n):
```

If yes, proceed with profile creation:

#### 4.1 Collect Profile Information

For each profile (allow creating multiple):

```
Profile Configuration
=====================

Profile #1

Description (e.g., "OLM Project", "OpenShift Origin"):
>

GitHub project (org/repo format, e.g., "operator-framework/operator-lifecycle-manager"):
>

Jira project key (e.g., "OCPBUGS", "CNTRLPLANE"):
>

Add another profile? (y/n):
```

#### 4.2 Create profiles.yaml

```bash
cat > $GH2JIRA_DIR/profiles.yaml << 'EOF'
profiles:
EOF

# For each profile, append:
cat >> $GH2JIRA_DIR/profiles.yaml << EOF
- description: $PROFILE_DESC
  githubConfig:
     project: $GITHUB_PROJECT
  jiraConfig:
     project: $JIRA_PROJECT
  tokenStore: tokenstore.yaml
EOF
```

**Confirm:**
```
✓ Created profiles.yaml with X profile(s)

Profiles:
  - $PROFILE_1_DESC
  - $PROFILE_2_DESC
  ...

Location: $GH2JIRA_DIR/profiles.yaml
```

### 🔄 Phase 5: Configure Workflows

Workflows define how GitHub and Jira issue states are mapped.

**Explain to user:**
```
Workflow Configuration
======================

Workflows map GitHub issue states (open/closed) to Jira status values.

Default mapping:
  GitHub "open"   → Jira: To Do, In Progress, New, Code Review
  GitHub "closed" → Jira: Done, Dev Complete, Release Pending

Would you like to:
1. Use default workflow mapping (recommended)
2. Customize workflow mapping
3. Skip workflow setup

Enter choice (1-3):
```

#### 5.1 Create Default workflows.yaml

```bash
cat > $GH2JIRA_DIR/workflows.yaml << 'EOF'
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

#### 5.2 Custom Workflow Mapping

If user chooses custom mapping:

```
Custom Workflow Configuration
==============================

For GitHub state "open", enter Jira statuses (comma-separated):
Examples: To Do, In Progress, Backlog, New
>

For GitHub state "closed", enter Jira statuses (comma-separated):
Examples: Done, Closed, Resolved, Verified
>
```

Create workflows.yaml with custom mappings.

**Confirm:**
```
✓ Created workflows.yaml

Location: $GH2JIRA_DIR/workflows.yaml

You can edit this file later to adjust state mappings.
```

### 🔗 Phase 6: Add to PATH

Make gh2jira easily accessible from anywhere.

**Detect shell:**
```bash
echo $SHELL
```

**Ask user:**
```
Add gh2jira to PATH?
====================

This will make gh2jira available from any directory.

We can add it to your shell configuration:
  - Detected shell: $SHELL
  - Config file: $SHELL_CONFIG

Add to PATH now? (y/n):
```

#### 6.1 Create Symlink or Alias

**Option 1: Symlink (recommended)**

```bash
# Create symlink in user's local bin (ensure directory exists)
mkdir -p ~/.local/bin
ln -sf $GH2JIRA_DIR/gh2jira ~/.local/bin/gh2jira

# Add ~/.local/bin to PATH if not already there
if ! echo $PATH | grep -q "$HOME/.local/bin"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> $SHELL_CONFIG
fi
```

**Option 2: PATH export**

```bash
echo "export PATH=\"$GH2JIRA_DIR:\$PATH\"" >> $SHELL_CONFIG
```

**Shell config files by shell type:**
- bash: `~/.bashrc` or `~/.bash_profile`
- zsh: `~/.zshrc`
- fish: `~/.config/fish/config.fish`

**Confirm:**
```
✓ Added gh2jira to PATH

To use gh2jira immediately, run:
  source $SHELL_CONFIG

Or open a new terminal.
```

### ✅ Phase 7: Verify Installation

Run validation checks to ensure everything is configured correctly.

```bash
# Check gh2jira is in PATH
which gh2jira

# Verify version
gh2jira --version

# Test configuration files exist
test -f $GH2JIRA_DIR/tokenstore.yaml && echo "✓ tokenstore.yaml"
test -f $GH2JIRA_DIR/profiles.yaml && echo "✓ profiles.yaml"
test -f $GH2JIRA_DIR/workflows.yaml && echo "✓ workflows.yaml"
```

**Display summary:**
```
Installation Complete!
======================

✓ gh2jira installed at: $GH2JIRA_DIR
✓ GitHub token configured
✓ Jira token configured
✓ Profiles created: X
✓ Workflows configured
✓ Added to PATH

Next Steps:
-----------

1. Test GitHub connection:
   gh2jira github list --github-project your-org/your-repo

2. Test Jira connection:
   gh2jira jira list --jira-project YOUR-PROJECT-KEY

3. Clone a GitHub issue:
   gh2jira clone <issue-number> --profile-name <profile>

4. Use with Claude Code commands:
   /jira:clone-from-github <issue-number> --profile <profile>
   /jira:reconcile-github --profile <profile>

Documentation:
--------------
- gh2jira README: https://github.com/oceanc80/gh2jira
- Command help: gh2jira --help
- Claude Code commands: /jira:clone-from-github, /jira:reconcile-github

Configuration Files:
--------------------
- Tokens: $GH2JIRA_DIR/tokenstore.yaml
- Profiles: $GH2JIRA_DIR/profiles.yaml
- Workflows: $GH2JIRA_DIR/workflows.yaml

To update tokens or configuration, edit these files or run /jira:setup-gh2jira again.
```

### 🔄 Phase 8: Environment Variables (Optional)

Optionally set environment variables for easier configuration:

```bash
# Add to shell config
cat >> $SHELL_CONFIG << EOF

# gh2jira configuration
export GH2JIRA_DIR="$GH2JIRA_DIR"
export GH2JIRA_TOKENSTORE="$GH2JIRA_DIR/tokenstore.yaml"
export GH2JIRA_PROFILES="$GH2JIRA_DIR/profiles.yaml"
export GH2JIRA_WORKFLOWS="$GH2JIRA_DIR/workflows.yaml"
EOF
```

## Return Value

**Success:**
- Installation directory path
- Configuration file locations
- Summary of created resources
- Next steps for using gh2jira

**Partial Success:**
- List of completed steps
- List of skipped or failed steps
- Instructions to complete remaining setup manually

**Error:**
- Detailed error message
- Step where failure occurred
- Troubleshooting suggestions
- Link to gh2jira documentation

## Examples

### Example 1: Complete setup with profiles

```
/jira:setup-gh2jira

> Installing to ~/go/src/github.com/oceanc80/gh2jira
> Building gh2jira...
> Enter GitHub token: ***
> Enter Jira token: ***
> Create profile: "My Project"
>   GitHub: myorg/myrepo
>   Jira: MYPROJ
> Using default workflows
> Added to PATH

✓ Setup complete!
```

### Example 2: Minimal setup without profiles

```
/jira:setup-gh2jira

> Installing to ~/.local/share/gh2jira
> Building gh2jira...
> Enter GitHub token: ***
> Enter Jira token: ***
> Skip profiles
> Using default workflows
> Added to PATH

✓ Setup complete!
```

### Example 3: Reconfigure existing installation

```
/jira:setup-gh2jira

> Found existing installation at ~/go/src/github.com/oceanc80/gh2jira
> Reconfigure? yes
> Keep existing GitHub token
> Update Jira token: ***
> Add new profile: "Second Project"
> Keep existing workflows

✓ Reconfiguration complete!
```

## Error Handling

### Go Not Installed

**Scenario:** Go is not found on the system.

**Action:**
```
✗ Go is not installed

gh2jira requires Go 1.18 or higher.

Install Go:
- macOS: brew install go
- Linux: sudo apt install golang-go (Ubuntu/Debian)
- Windows: Download from https://go.dev/dl/

After installing, run /jira:setup-gh2jira again.
```

### Build Failure

**Scenario:** `make` fails to build gh2jira.

**Action:**
```
✗ Failed to build gh2jira

Error output:
<error message>

Troubleshooting:
1. Ensure Go version is 1.18+: go version
2. Check for missing dependencies: go mod download
3. Try manual build: cd $GH2JIRA_DIR && go build
4. See gh2jira README: https://github.com/oceanc80/gh2jira

Would you like to:
1. Retry build
2. Continue setup without building (configure only)
3. Exit setup
```

### Invalid GitHub Token

**Scenario:** GitHub token validation fails.

**Action:**
```
✗ GitHub token validation failed

The token may be invalid, expired, or lack required permissions.

Required scopes:
- public_repo
- read:project

Options:
1. Re-enter token
2. Skip GitHub token (configure later)
3. Exit setup

Check token at: https://github.com/settings/tokens
```

### Invalid Jira Token

**Scenario:** Jira token validation fails.

**Action:**
```
✗ Jira token validation failed

This may be due to:
- Invalid or expired token
- Incorrect Jira URL
- Network issues
- Organization-specific authentication requirements

Options:
1. Re-enter token
2. Try different Jira URL
3. Skip Jira token (configure later)
4. Exit setup

For Red Hat Jira or custom setups, consult your organization's documentation.
```

### Permission Denied

**Scenario:** Cannot write to installation directory.

**Action:**
```
✗ Permission denied: Cannot write to <directory>

Options:
1. Choose different installation directory
2. Fix permissions: sudo chown -R $USER <directory>
3. Use user directory: ~/.local/share/gh2jira

Would you like to:
1. Select new directory
2. Exit setup
```

### PATH Already Contains gh2jira

**Scenario:** gh2jira is already in PATH from a different location.

**Action:**
```
⚠ gh2jira already exists in PATH at: <existing-path>

This installation is at: <new-path>

Options:
1. Replace existing with new installation
2. Keep both (may cause confusion)
3. Skip PATH modification
4. Abort installation

Which would you prefer?
```

## Best Practices

1. **Secure your tokens**: The setup command sets `tokenstore.yaml` to mode 600 (owner read/write only). Never commit this file to version control.

2. **Use profiles**: Create profiles for frequently-used project combinations to simplify commands.

3. **Test connections**: After setup, test both GitHub and Jira connections with `gh2jira github list` and `gh2jira jira list`.

4. **Backup configuration**: Keep a backup of your configuration files (excluding `tokenstore.yaml`) for easy recovery.

5. **Update regularly**: Periodically update gh2jira by running `cd $GH2JIRA_DIR && git pull && make`.

6. **Token rotation**: When rotating tokens, simply edit `tokenstore.yaml` with new values or run `/jira:setup-gh2jira` again.

## Security Considerations

- **Token storage**: Tokens are stored in plaintext in `tokenstore.yaml`. Ensure file has restrictive permissions (600).
- **Token scopes**: Only grant minimum required scopes to tokens.
- **Environment variables**: Avoid storing tokens in environment variables that may be logged.
- **Shared systems**: On shared systems, be extra cautious about file permissions and token security.
- **Token expiration**: Set token expiration dates and rotate regularly per your security policy.

## See Also

- [gh2jira Repository](https://github.com/oceanc80/gh2jira)
- [Go Installation Guide](https://go.dev/doc/install)
- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [Atlassian API Tokens](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
- `/jira:clone-from-github` - Clone GitHub issues to Jira
- `/jira:reconcile-github` - Reconcile state between GitHub and Jira

## Troubleshooting

### Command not found after setup

```bash
# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc, etc.

# Or verify PATH
echo $PATH | grep gh2jira
```

### Cannot clone issues after setup

1. Verify tokens: Check `tokenstore.yaml` has valid tokens
2. Test connections: Run `gh2jira github list` and `gh2jira jira list`
3. Check profiles: Verify `profiles.yaml` has correct project names
4. Review errors: Run with verbose output for detailed errors

### Workflow reconciliation not working

1. Check `workflows.yaml` exists and has valid YAML syntax
2. Verify state names match your Jira workflow states exactly
3. Test with `gh2jira reconcile --profile-name <profile>`
