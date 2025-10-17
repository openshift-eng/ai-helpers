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

## Available Plugins

### JIRA Plugin

Comprehensive Jira automation including:
- **Issue Analysis & Solutions** (`/jira:solve`) - Analyze JIRA issues and create pull requests to solve them
- **Weekly Status Rollups** (`/jira:status-rollup`) - Generate status summaries by analyzing all child issues
- **Backlog Grooming** (`/jira:grooming`) - Analyze new bugs and cards for grooming meetings

See [plugins/jira/README.md](plugins/jira/README.md) for full documentation.

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

## License

See [LICENSE](LICENSE) for details.
