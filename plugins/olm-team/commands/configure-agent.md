---
description: Configure the k8s-ocp-olm-expert agent with local repository paths
argument-hint: ""
---

## Name
olm-team:configure-agent

## Synopsis
```
/olm-team:configure-agent
```

## Description
The `olm-team:configure-agent` command helps you create or update the configuration file for the k8s-ocp-olm-expert agent. This configuration specifies the local paths to OLM development repositories that the agent uses to provide code-aware responses and documentation references.

The agent requires access to:
- **Documentation**: openshift-docs
- **OLM v0 Upstream**: operator-lifecycle-manager, operator-registry, api
- **OLM v0 Downstream**: operator-framework-olm, operator-marketplace
- **OLM v1 Upstream**: operator-controller
- **OLM v1 Downstream**: operator-framework-operator-controller, cluster-olm-operator
- **OpenShift API**: openshift-api

If you don't have these repositories cloned yet, the command will recommend using `/olm-team:dev-setup` to automatically fork and clone all required repositories.

## Implementation

### Step 1: Check for Existing Configuration

First, check if a configuration file already exists:

```bash
CONFIG_FILE="$HOME/.config/claude-code/olm-agent-config.json"

if [ -f "$CONFIG_FILE" ]; then
  echo "Existing configuration found at: $CONFIG_FILE"
  cat "$CONFIG_FILE"
  # Ask user if they want to update or recreate
else
  echo "No existing configuration found. Creating new configuration..."
fi
```

### Step 2: Detect Repository Locations

Search for OLM repositories in common locations:

```bash
# Common base directories to search
SEARCH_DIRS=(
  "$HOME/go/src/github.com"
  "$HOME/src"
  "$HOME/code"
  "$HOME/workspace"
  "$HOME/dev"
)

# Repository names to search for
REPOS=(
  "openshift-docs"
  "operator-lifecycle-manager"
  "operator-registry"
  "api"
  "operator-framework-olm"
  "operator-marketplace"
  "operator-controller"
  "operator-framework-operator-controller"
  "cluster-olm-operator"
  "openshift-api"
)

# Search for repositories and store found paths
declare -A FOUND_REPOS

for search_dir in "${SEARCH_DIRS[@]}"; do
  if [ -d "$search_dir" ]; then
    for repo in "${REPOS[@]}"; do
      # Search in user directories (e.g., ~/go/src/github.com/<username>/<repo>)
      found=$(find "$search_dir" -maxdepth 3 -type d -name "$repo" 2>/dev/null | head -1)
      if [ -n "$found" ]; then
        FOUND_REPOS[$repo]="$found"
      fi
    done
  fi
done
```

### Step 3: Display Found Repositories and Check Coverage

Show the user what was found and what's missing:

```
Repository Detection Results
=============================

✓ Found:
  - openshift-docs: /path/to/openshift-docs
  - operator-lifecycle-manager: /path/to/operator-lifecycle-manager
  ...

✗ Not Found:
  - operator-marketplace
  - cluster-olm-operator
  ...
```

### Step 4: Recommend dev-setup if Repositories are Missing

If fewer than 8 out of 10 repositories are found, recommend using dev-setup:

```
⚠️  Missing Repositories Detected

You're missing X out of 10 required repositories.

RECOMMENDATION: Run /olm-team:dev-setup

The dev-setup command will:
✓ Fork all OLM repositories to your GitHub account
✓ Clone them to your local machine
✓ Configure git remotes (origin/upstream)
✓ Automatically create this agent configuration

This is the recommended approach for new team members.

Would you like to:
1. Run /olm-team:dev-setup now (Recommended)
2. Continue configuring with existing repositories
3. Manually specify repository paths
```

Use the AskUserQuestion tool to present these options.

If user chooses option 1:
- Exit this command and inform them to run `/olm-team:dev-setup`

If user chooses option 2 or 3:
- Continue to the next step

### Step 5: Prompt for Missing or Custom Paths

For each repository that wasn't automatically found, or if the user wants custom paths:

Use the AskUserQuestion tool or direct prompts to ask for each missing repository path:

```
Enter the full path to <repository-name>:
(Leave empty to skip if you don't have this repository)

Example: /Users/yourname/go/src/github.com/yourname/operator-lifecycle-manager
```

For each path entered:
1. Expand `~` to home directory
2. Verify the path exists and is a directory
3. Check if it's a git repository (has .git directory)
4. Warn if not a git repository but allow proceeding

```bash
# Validate path
validate_path() {
  local path="$1"
  local repo_name="$2"

  # Expand ~
  path="${path/#\~/$HOME}"

  # Check if directory exists
  if [ ! -d "$path" ]; then
    echo "❌ Directory does not exist: $path"
    return 1
  fi

  # Check if it's a git repository
  if [ ! -d "$path/.git" ]; then
    echo "⚠️  Warning: $path is not a git repository"
    echo "   This may not be the correct directory for $repo_name"
  fi

  # Check if directory name matches expected repo name
  dir_name=$(basename "$path")
  if [ "$dir_name" != "$repo_name" ]; then
    echo "⚠️  Warning: Directory name '$dir_name' doesn't match expected '$repo_name'"
  fi

  echo "✓ Path validated: $path"
  return 0
}
```

### Step 6: Build Configuration JSON

Create the configuration file structure:

```bash
# Build JSON configuration
build_config() {
  cat > "$CONFIG_FILE" <<EOF
{
  "repositories": {
    "openshift_docs": "${FOUND_REPOS[openshift-docs]:-/path/to/openshift-docs}",
    "olm_v0_upstream": {
      "operator_lifecycle_manager": "${FOUND_REPOS[operator-lifecycle-manager]:-/path/to/operator-lifecycle-manager}",
      "operator_registry": "${FOUND_REPOS[operator-registry]:-/path/to/operator-registry}",
      "api": "${FOUND_REPOS[api]:-/path/to/api}"
    },
    "olm_v0_downstream": {
      "operator_framework_olm": "${FOUND_REPOS[operator-framework-olm]:-/path/to/operator-framework-olm}",
      "operator_marketplace": "${FOUND_REPOS[operator-marketplace]:-/path/to/operator-marketplace}"
    },
    "olm_v1_upstream": {
      "operator_controller": "${FOUND_REPOS[operator-controller]:-/path/to/operator-controller}"
    },
    "olm_v1_downstream": {
      "operator_framework_operator_controller": "${FOUND_REPOS[operator-framework-operator-controller]:-/path/to/operator-framework-operator-controller}",
      "cluster_olm_operator": "${FOUND_REPOS[cluster-olm-operator]:-/path/to/cluster-olm-operator}"
    },
    "openshift_api": {
      "openshift_api": "${FOUND_REPOS[openshift-api]:-/path/to/openshift-api}"
    }
  }
}
EOF
}
```

### Step 7: Validate Configuration

Before saving, validate the configuration:

```bash
# Validate configuration file
validate_config() {
  local config_file="$1"

  # Check if jq is available
  if ! command -v jq &> /dev/null; then
    echo "⚠️  Warning: jq not found. Cannot validate JSON syntax."
    echo "   Install jq to enable configuration validation: brew install jq"
    return 0
  fi

  # Validate JSON syntax
  if ! jq empty "$config_file" 2>/dev/null; then
    echo "❌ Invalid JSON syntax in configuration file"
    return 1
  fi

  # Extract and validate all paths
  echo "Validating repository paths..."
  local invalid_paths=0
  local valid_paths=0

  for path in $(jq -r '.. | strings | select(startswith("/"))' "$config_file"); do
    if [ -d "$path" ]; then
      echo "  ✓ $path"
      ((valid_paths++))
    else
      echo "  ✗ $path (does not exist)"
      ((invalid_paths++))
    fi
  done

  echo ""
  echo "Validation Summary:"
  echo "  Valid paths: $valid_paths"
  echo "  Invalid paths: $invalid_paths"

  if [ $invalid_paths -gt 0 ]; then
    echo ""
    echo "⚠️  Some paths don't exist. You can:"
    echo "   1. Run /olm-team:dev-setup to clone missing repositories"
    echo "   2. Update the paths manually in: $config_file"
    echo "   3. Continue anyway (agent will warn about missing repos)"
  fi

  return 0
}
```

### Step 8: Save Configuration

Create the config directory if needed and save the file:

```bash
# Create config directory
mkdir -p "$(dirname "$CONFIG_FILE")"

# Save configuration
build_config

# Validate
validate_config "$CONFIG_FILE"

echo ""
echo "Configuration saved to: $CONFIG_FILE"
```

### Step 9: Display Summary and Next Steps

Show the user a summary and what to do next:

```
Configuration Complete
======================

✓ Configuration file created: ~/.config/claude-code/olm-agent-config.json

Repository Paths Configured:
  ✓ openshift-docs
  ✓ operator-lifecycle-manager
  ✓ operator-registry
  ✓ api
  ✓ operator-framework-olm
  ✓ operator-marketplace
  ✓ operator-controller
  ✓ operator-framework-operator-controller
  ✓ cluster-olm-operator
  ✓ openshift-api

The k8s-ocp-olm-expert agent is now configured and will automatically use these
repositories when providing documentation references and code analysis.

Next Steps:
-----------

1. Test the agent:
   Ask a Kubernetes/OpenShift/OLM question and the agent will automatically engage

2. Keep repositories updated:
   cd /path/to/repository
   git fetch upstream
   git merge upstream/main

3. Update configuration anytime:
   /olm-team:configure-agent

4. View agent documentation:
   cat ~/path/to/ai-helpers/plugins/olm-team/skills/k8s-ocp-olm-expert/README.md
```

If there are missing repositories:

```
⚠️  Note: Some repository paths are missing or invalid.

To clone missing repositories, run:
  /olm-team:dev-setup

Or manually clone the repositories and run this command again to update paths.
```

### Step 10: Error Handling

Handle common errors:

1. **Directory creation fails**:
   ```bash
   if ! mkdir -p "$(dirname "$CONFIG_FILE")" 2>/dev/null; then
     echo "❌ Error: Cannot create config directory: $(dirname "$CONFIG_FILE")"
     echo "   Check directory permissions"
     exit 1
   fi
   ```

2. **File write fails**:
   ```bash
   if ! touch "$CONFIG_FILE" 2>/dev/null; then
     echo "❌ Error: Cannot write to config file: $CONFIG_FILE"
     echo "   Check file permissions"
     exit 1
   fi
   ```

3. **Invalid path provided**:
   - Warn the user but allow proceeding
   - Save the path anyway (user might create it later)
   - Add to "invalid paths" list in summary

4. **No repositories found**:
   - Strongly recommend /olm-team:dev-setup
   - Offer to create template config file
   - User can manually edit later

## Return Value

- **Format**: Summary report with configuration status

The command outputs:
1. **Detection Results**: Which repositories were found automatically
2. **Configuration Status**: Success/warning/error for config file creation
3. **Validation Results**: Which paths are valid/invalid
4. **Next Steps**: Guidance for using the agent or cloning missing repositories

## Examples

### 1. First-time configuration (some repos missing)

```
/olm-team:configure-agent
```

Output:
```
Repository Detection Results
=============================
✓ Found 6/10 repositories
✗ Missing 4 repositories

⚠️  RECOMMENDATION: Run /olm-team:dev-setup

Would you like to:
1. Run /olm-team:dev-setup now (Recommended)
2. Continue with partial configuration
3. Manually specify all paths

[User chooses option 1]

Please run: /olm-team:dev-setup
```

### 2. Configuration with all repos present

```
/olm-team:configure-agent
```

Output:
```
Repository Detection Results
=============================
✓ Found all 10 repositories

Creating configuration...
✓ Configuration saved: ~/.config/claude-code/olm-agent-config.json
✓ All paths validated successfully

The k8s-ocp-olm-expert agent is ready to use!
```

### 3. Update existing configuration

```
/olm-team:configure-agent
```

Output:
```
Existing configuration found at: ~/.config/claude-code/olm-agent-config.json
Current paths:
  - openshift-docs: /Users/user/go/src/github.com/user/openshift-docs
  ...

Would you like to:
1. Update configuration (search for new paths)
2. Manually edit paths
3. Keep existing configuration

[User interaction follows]
```

## Arguments

None. The command is interactive and will prompt for any needed information.

## Notes

1. **Automatic Repository Detection**: The command searches common directories (`~/go/src/github.com`, `~/src`, `~/code`) for OLM repositories. This works best if you follow standard directory conventions.

2. **Configuration Location**: The configuration file is stored at `~/.config/claude-code/olm-agent-config.json`. This location is standard for Claude Code user configurations.

3. **dev-setup Integration**: This command is designed to work alongside `/olm-team:dev-setup`. If you're missing repositories, dev-setup is the recommended approach as it handles forking, cloning, and configuration automatically.

4. **Partial Configuration**: You can create a configuration with only some repositories. The agent will warn about missing repos when it needs them, but will still function for queries that only need the configured repos.

5. **Path Validation**: The command validates that paths exist and are git repositories, but doesn't verify they're the correct repositories. Make sure you're pointing to the actual OLM repositories, not other projects with similar names.

6. **Manual Editing**: You can always manually edit `~/.config/claude-code/olm-agent-config.json` if you need to update paths later. Just ensure the JSON syntax remains valid.

7. **Multiple GitHub Accounts**: If you have repositories from multiple GitHub accounts or organizations, you can configure paths to any of them. The agent doesn't care about git remotes, only that the code is present locally.

## See Also

- `/olm-team:dev-setup` - Automated repository setup and configuration
- `plugins/olm-team/skills/k8s-ocp-olm-expert/README.md` - Agent documentation
- `plugins/olm-team/skills/k8s-ocp-olm-expert/config-example.json` - Example configuration file
