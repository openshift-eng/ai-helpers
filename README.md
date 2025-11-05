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

For a complete list of all available plugins and commands, see **[PLUGINS.md](PLUGINS.md)**.

## Plugin Development

Want to contribute or create your own plugins? Check out the `plugins/` directory for examples.
Make sure your commands and agents follow the conventions for the Sections structure presented in the hello-world reference implementation plugin (see [`hello-world:echo`](plugins/hello-world/commands/echo.md) for an example).

### Ethical Guidelines

Plugins, commands, skills, and hooks must NEVER reference real people by name, even as stylistic examples (e.g., "in the style of <specific human>").

**Ethical rationale:**
1. **Consent**: Individuals have not consented to have their identity or persona used in AI-generated content
2. **Misrepresentation**: AI cannot accurately replicate a person's unique voice, style, or intent
3. **Intellectual Property**: A person's distinctive style may be protected
4. **Dignity**: Using someone's identity without permission diminishes their autonomy

**Instead, describe specific qualities explicitly**

Good examples:

* "Write commit messages that are direct, technically precise, and focused on the rationale behind changes"
* "Explain using clear analogies, a sense of wonder, and accessible language for non-experts"
* "Code review comments that are encouraging, constructive, and focus on collaborative improvement"

When you identify a desirable characteristic (clarity, brevity, formality, humor, etc.), describe it explicitly rather than using a person as proxy.

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

### Updating Plugin Documentation

After adding or modifying plugins, regenerate the PLUGINS.md file:

```bash
make update
```

This automatically scans all plugins and regenerates the complete plugin/command documentation in PLUGINS.md.

## Additional Documentation

- **[PLUGINS.md](PLUGINS.md)** - Complete list of all available plugins and commands
- **[AGENTS.md](AGENTS.md)** - Complete guide for AI agents working with this repository
- **[CLAUDE.md](CLAUDE.md)** - Claude-specific configuration and notes

## License

See [LICENSE](LICENSE) for details.
