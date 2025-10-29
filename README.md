# AI Helpers

A collection of Claude Code plugins to automate and assist with various development tasks.

## Installation

### From the Claude Code Plugin Marketplace

1. **Add the marketplace:**
   ```bash
   /plugin marketplace add openshift-eng/ai-helpers
   ```

2. **Install a plugin:**
   ```bash
   /plugin install jira@ai-helpers
   ```

3. **Use the commands:**
   ```bash
   /jira:solve OCPBUGS-12345 origin
   ```

### Using Cursor

Cursor is able to find the various commands defined in this repo by
making it available inside your `~/.cursor/commands` directory.

```
$ mkdir -p ~/.cursor/commands
$ git clone git@github.com:openshift-eng/ai-helpers.git
$ ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Using the Docker Container

A container is available with Claude Code and all plugins pre-installed.

### Building the Container

```bash
podman build -f images/Dockerfile -t ai-helpers .
```

### Running with Vertex AI and gcloud Authentication

To use Claude Code with Google Cloud's Vertex AI, you need to pass through your gcloud credentials and set the required environment variables:

```bash
podman run -it \
  -e CLAUDE_CODE_USE_VERTEX=1 \
  -e CLOUD_ML_REGION=your-ml-region \
  -e ANTHROPIC_VERTEX_PROJECT_ID=your-project-id \
  -v ~/.config/gcloud:/home/claude/.config/gcloud:ro \
  -v $(pwd):/workspace \
  -w /workspace \
  ai-helpers
```

**Environment Variables:**
- `CLAUDE_CODE_USE_VERTEX=1` - Enable Vertex AI integration
- `CLOUD_ML_REGION` - Your GCP region (e.g., `us-east5`)
- `ANTHROPIC_VERTEX_PROJECT_ID` - Your GCP project ID

**Volume Mounts:**
- `-v ~/.config/gcloud:/home/claude/.config/gcloud:ro` - Passes through your gcloud authentication (read-only)
- `-v $(pwd):/workspace` - Mounts your current directory into the container

### Running Commands Non-Interactively

You can execute Claude Code commands directly without entering an interactive session using the `-p` or `--print` flag:

```bash
podman run -it \
  -e CLAUDE_CODE_USE_VERTEX=1 \
  -e CLOUD_ML_REGION=your-ml-region \
  -e ANTHROPIC_VERTEX_PROJECT_ID=your-project-id \
  -v ~/.config/gcloud:/home/claude/.config/gcloud:ro \
  -v $(pwd):/workspace \
  -w /workspace \
  ai-helpers \
  --print "/hello-world:echo Hello from Claude Code!"
```

This will:
1. Start the container with your gcloud credentials
2. Execute the `/hello-world:echo` command with the provided message
3. Print the response and exit when complete

## Available Plugins

### JIRA Plugin

Comprehensive Jira automation including:
- **Issue Analysis & Solutions** (`/jira:solve`) - Analyze JIRA issues and create pull requests to solve them
- **Weekly Status Rollups** (`/jira:status-rollup`) - Generate status summaries by analyzing all child issues
- **Backlog Grooming** (`/jira:grooming`) - Analyze new bugs and cards for grooming meetings
- **Test Generation** (`/jira:generate-test-plan`) - Generate comprehensive test steps for JIRA issues by analyzing related PRs

See [plugins/jira/README.md](plugins/jira/README.md) for full documentation.

### Utils Plugin

General-purpose utilities for development workflows:
- **PR Test Generation** (`/utils:generate-test-plan`) - Generate test steps for one or more related PRs
- **Process Renovate PRs** (`/utils:process-renovate-pr`) - Process Renovate dependency PRs to meet repository standards

See [plugins/utils/commands/generate-test-plan.md](plugins/utils/commands/generate-test-plan.md) for full documentation.

### OpenShift Plugin

OpenShift development workflow automation:
- **E2E Test Generation** (`/openshift:new-e2e-test`) - Generate end-to-end tests for OpenShift features
- **Rebase** (`/openshift:rebase`) - Rebases git repository in the current working directory to a new upstream release specified
- **Create Cluster** (`/openshift:create-cluster`) - Automates the process of extracting the OpenShift installer from a release image
- **Dependency Bumping** (`/openshift:bump-deps`) - Bump dependencies with automated analysis, testing, and PR creation

See [plugins/openshift/README.md](plugins/openshift/README.md) for full documentation.

### Git Plugin

Git workflow automation and utilities:
- **Commit Suggestion** (`/git:commit-suggest`) - Generate Conventional Commits style commit messages for staged changes or recent commits
- **Cherry-pick by Patch** (`/git:cherry-pick-by-patch`) - Cherry-pick a commit using the patch command instead of git cherry-pick
- **Debt Scan** (`/git:debt-scan`) - Scan the codebase for technical debt markers and generate a report
- **Summary** (`/git:summary`) - Generate a summary of git repository changes and activity

See [plugins/git/README.md](plugins/git/README.md) for full documentation.

## Plugin Development

Want to contribute or create your own plugins? Check out the `plugins/` directory for examples.
Make sure your commands and agents follow the conventions for the Sections structure presented in the hello-world reference implementation plugin (see [`hello-world:echo`](plugins/hello-world/commands/echo.md) for an example).

### Adding New Commands

When contributing new commands:

1. **If your command fits an existing plugin**: Add it to the appropriate plugin's `commands/` directory
2. **If your command doesn't have a clear parent plugin**: Add it to the **utils plugin** (`plugins/utils/commands/`)
   - The utils plugin serves as a catch-all for commands that don't fit existing categories
   - Once we accumulate several related commands in utils, they can be segregated into a new targeted plugin

### Creating a New Plugin

If you're contributing several related commands that warrant their own plugin:

1. Create a new directory under `plugins/` with your plugin name
2. Create the plugin structure:
   ```
   plugins/your-plugin/
   ├── .claude-plugin/
   │   └── plugin.json
   └── commands/
       └── your-command.md
   ```
3. Register your plugin in `.claude-plugin/marketplace.json`

### Validating Plugins

This repository uses [claudelint](https://github.com/stbenjam/claudelint) to validate plugin structure:

```bash
make lint
```

## Additional Documentation

- **[AGENTS.md](AGENTS.md)** - Complete guide for AI agents working with this repository
- **[CLAUDE.md](CLAUDE.md)** - Claude-specific configuration and notes

## License

See [LICENSE](LICENSE) for details.
