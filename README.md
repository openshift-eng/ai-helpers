# AI Helpers

A collection of Claude Code plugins to automate and assist with various development tasks.

## 🚀 New Hire Quick Start

### Understanding General vs Team-Specific Resources

Welcome to OpenShift engineering! OpenShift consists of **dozens of teams** working across **many repositories**. This guide focuses on **general OpenShift resources** useful to all teams.

#### General Resources (All Teams)

**1. ai-helpers (THIS REPO) - General Automation**
- 🤖 Claude Code automation plugins for common tasks
- 🔧 Workflow commands: JIRA, CI analysis, component health
- 📝 Tools useful across all OpenShift teams
- 🎯 **Use for:** JIRA automation, CI debugging, bug tracking

**2. openshift/enhancements - General OpenShift Knowledge**
- 📚 Enhancement proposals (KEPs) for OpenShift features
- 🏗️ Architecture docs for how OpenShift works
- 📖 Process docs for the OpenShift project
- 🔍 **Use for:** Understanding OpenShift design, cross-component architecture

#### Team-Specific Resources

Your specific team (e.g., kube-apiserver, networking, storage, etc.) has:
- **Component repos**: Your team's code (operators, controllers, etc.)
- **Team docs**: Team-specific runbooks and guides
- **Team tools**: Custom automation and development tools

👉 **Ask your manager or team lead** about team-specific repositories and onboarding!

### Setup General Resources (5 minutes)

This section covers general OpenShift resources. Your team will guide you through team-specific setup separately.

#### Step 1: Clone General Repositories

```bash
# ai-helpers: General automation (you likely have this already)
git clone https://github.com/openshift-eng/ai-helpers.git

# enhancements: General OpenShift knowledge (optional but recommended)
cd .. && git clone https://github.com/openshift/enhancements.git

# Or clone enhancements to Go workspace:
mkdir -p ~/go/src/github.com/openshift
cd ~/go/src/github.com/openshift
git clone https://github.com/openshift/enhancements.git
```

#### Step 2: Open in Claude Code

**Option A: Use the Workspace File (Recommended)**

Open both repos together using the provided workspace file:

```bash
# From the ai-helpers directory
code openshift-eng.code-workspace
```

This opens both ai-helpers and enhancements side-by-side with optimal settings.

**Option B: Open ai-helpers Only**

```bash
cd path/to/ai-helpers
code .
```

You can open enhancements later in a separate window when needed.

#### Step 3: Verify Your Setup

In Claude Code, run:

```bash
/onboarding:start
```

This command will:
- ✅ Detect if you have the enhancements repo
- ⚙️ Check your environment variables (JIRA credentials, etc.)
- 📋 Show you available commands
- 🎯 Provide personalized next steps

#### Step 4: Start Automating

Try your first automation commands:

```bash
# See component bug metrics
/component-health:summarize-jiras OCPBUGS --component "kube-apiserver"

# Search for documentation across both repos
/onboarding:search "networking"

# Create a JIRA ticket
/jira:create task OCPBUGS "My first automated ticket"
```

### Navigation Tips

**Working in ai-helpers (automation):**
- Use slash commands like `/jira:solve`, `/component-health:summarize-jiras`
- This repo provides tools, not technical documentation
- Commands are organized by plugin in `plugins/`

**When you need deep technical knowledge:**
1. Open the enhancements repo in a new Claude Code window:
   ```bash
   cd path/to/enhancements
   code . --new-window
   ```
2. Ask Claude about specific enhancement proposals (KEPs)
3. Search for architecture documentation
4. Understand design decisions and feature history

**Cross-repo search from here:**
```bash
/onboarding:search "your topic"
```
Searches both repos and routes you to the right documentation!

### Why These General Repos?

- **ai-helpers**: Automates common tasks (JIRA, CI, bug tracking) across all teams
- **enhancements**: Explains how OpenShift works at a high level

These are **general resources** useful regardless of your team. They complement (but don't replace) your team-specific repositories. Think of them as:
- **ai-helpers**: Swiss Army knife of automation tools
- **enhancements**: OpenShift architectural encyclopedia

Your team's specific repos will teach you about your component; these teach you about OpenShift as a whole.

### Need Help?

```bash
# Verify your setup anytime
/onboarding:start

# Search for help on any topic
/onboarding:search "topic"

# See all available commands
Type / in Claude Code to see autocomplete
```

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
