# AGENTS.md - Guide for AI Coding Agents

This guide helps AI coding agents navigate and contribute to the ai-helpers repository, which contains Claude Code plugins for automating development tasks.

## Repository Overview

This repository contains Claude Code plugins organized under the `plugins/` directory. Each plugin provides slash commands that can be invoked in Claude Code to automate specific workflows.

**Repository Structure:**
```
ai-helpers/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace registration
├── plugins/
│   ├── {plugin-name}/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json       # Plugin metadata
│   │   ├── commands/
│   │   │   └── *.md              # Command definitions
│   │   ├── skills/               # Optional: Task-specific implementation details
│   │   │   └── {skill-name}/
│   │   │       └── SKILL.md      # Skill documentation
│   │   └── README.md             # Plugin documentation
│   └── ...
└── README.md
```

## Plugin Conventions

### 1. Plugin Structure

Every plugin must follow this structure:

```
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json               # Required: Plugin metadata
├── commands/
│   └── {command-name}.md         # Required: At least one command
├── skills/                        # Optional: Complex implementation details
│   └── {skill-name}/
│       ├── SKILL.md               # Detailed implementation guide
│       ├── README.md              # User-facing documentation
│       └── *.py                   # Optional: Helper scripts
└── README.md                      # Recommended: Plugin documentation
```

### 2. Plugin Metadata (`plugin.json`)

Location: `plugins/{plugin-name}/.claude-plugin/plugin.json`

```json
{
  "name": "plugin-name",
  "description": "Brief description of what this plugin does",
  "version": "0.0.1",
  "author": {
    "name": "github.com/openshift-eng"
  }
}
```

### 3. Command Definition Format

All commands are defined in Markdown files under `plugins/{plugin-name}/commands/`.

**File naming:** `{command-name}.md` → becomes slash command `/plugin-name:command-name`

**Required frontmatter:**
```markdown
---
description: Brief description of the command
argument-hint: [optional] [arguments]  # Optional: shown in autocomplete
---
```

**Required sections** (inspired by [Linux man pages](https://man7.org/linux/man-pages/man7/man-pages.7.html)):

1. **Name** - Command identifier
   ```markdown
   ## Name
   plugin-name:command-name
   ```

2. **Synopsis** - Usage syntax
   ```markdown
   ## Synopsis
   ```
   /plugin-name:command-name [arguments]
   ```
   ```

3. **Description** - What the command does
   ```markdown
   ## Description
   The `plugin-name:command-name` command does X, Y, and Z...
   ```

4. **Implementation** - How it works (implementation details)
   ```markdown
   ## Implementation
   - Step 1: ...
   - Step 2: ...
   ```

5. **Return Value** - What the command outputs
   ```markdown
   ## Return Value
   - **Format**: Description
   ```

6. **Examples** - Usage examples (optional but recommended)
   ```markdown
   ## Examples

   1. **Basic usage**:
      ```
      /plugin-name:command-name arg1
      ```
   ```

7. **Arguments** - Argument descriptions
   ```markdown
   ## Arguments:
   - $1: Description of first argument
   - $2: Description of second argument
   ```

**Example:** See `plugins/hello-world/commands/echo.md` for a complete reference implementation.

### 4. Skills (Optional)

For complex commands that require detailed implementation guidance, create a skill:

**Location:** `plugins/{plugin-name}/skills/{skill-name}/SKILL.md`

**Structure:**
```markdown
---
name: Skill Name
description: Brief description
---

# Skill Name

Detailed implementation instructions that guide the AI agent step-by-step.

## When to Use This Skill
...

## Prerequisites
...

## Implementation Steps
### Step 1: ...
### Step 2: ...
...

## Error Handling
...

## Examples
...
```

**Example:** See `plugins/prow-job/skills/prow-job-analyze-resource/SKILL.md` for a comprehensive skill implementation.

### 5. Marketplace Registration

All plugins must be registered in `.claude-plugin/marketplace.json`:

```json
{
  "name": "ai-helpers",
  "owner": {
    "name": "openshift-eng"
  },
  "plugins": [
    {
      "name": "plugin-name",
      "source": "./plugins/plugin-name",
      "description": "Description of plugin"
    }
  ]
}
```

## Installation and Usage

### Installing from Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install a specific plugin
/plugin install jira@ai-helpers

# Use the command
/jira:solve OCPBUGS-12345 origin
```

### Manual Installation (for Cursor)

```bash
# Clone repository
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Contributing New Plugins or Commands

### When to Add a New Command

1. **Existing Plugin:** If your command fits an existing plugin's scope, add it to that plugin's `commands/` directory
2. **Utils Plugin:** If your command doesn't have a clear parent plugin, add it to `plugins/utils/commands/`
3. **New Plugin:** If you have multiple related commands that warrant their own plugin, create a new plugin

### Creating a New Command

1. **Create the command file:**
   ```bash
   touch plugins/{plugin-name}/commands/{command-name}.md
   ```

2. **Follow the command definition format** (see section 3 above)

3. **Test locally:**
   - Restart Claude Code
   - Verify command appears in autocomplete
   - Test command execution

### Creating a New Plugin

1. **Create plugin structure:**
   ```bash
   mkdir -p plugins/{plugin-name}/.claude-plugin
   mkdir -p plugins/{plugin-name}/commands
   ```

2. **Create `plugin.json`:**
   ```bash
   cat > plugins/{plugin-name}/.claude-plugin/plugin.json << 'EOF'
   {
     "name": "plugin-name",
     "description": "Description",
     "version": "0.0.1",
     "author": {
       "name": "github.com/openshift-eng"
     }
   }
   EOF
   ```

3. **Register in marketplace:**
   - Edit `.claude-plugin/marketplace.json`
   - Add entry to `plugins` array

4. **Create at least one command** (see "Creating a New Command" above)

5. **Create README.md** documenting the plugin

### Adding Helper Scripts (Optional)

If your command needs helper scripts (Python, Bash, etc.):

1. Place scripts in `plugins/{plugin-name}/skills/{skill-name}/`
2. Reference scripts using relative paths: `plugins/{plugin-name}/skills/{skill-name}/script.py`
3. Document script usage in the SKILL.md file

**Example:** `plugins/prow-job/skills/prow-job-analyze-resource/parse_all_logs.py`

### Validating with the Linter

Before committing changes, always run the plugin linter to ensure compliance:

```bash
make lint
```

**When to run the linter:**
- After creating a new plugin
- After adding or modifying commands
- Before committing changes
- To diagnose structural issues

## Best Practices for AI Agents

### Ethical Guidelines

**IMPORTANT: Never Reference Real People**

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

### Before Contributing New Commands

**Check for overlaps first** to avoid duplicate work:

1. **Planning phase** - Validate your idea before coding:
   ```
   /utils:review-ai-helpers-overlap --idea "brief description of your command"
   ```
   If HIGH/MODERATE overlap found → collaborate on existing PR or wait for it to merge

2. **Before opening PR** - Check your implementation:
   ```
   /utils:review-ai-helpers-overlap
   ```
   If overlap found → differentiate your approach or consolidate with existing work

This command checks main branch + all open PRs for similar commands, skills, sub-agents, and hooks in the `openshift-eng/ai-helpers` repository. See `plugins/utils/commands/review-ai-helpers-overlap.md` for detailed usage.

### When Implementing Commands

1. **Follow existing patterns:** Review similar commands before implementing
2. **Use consistent structure:** Follow the command definition format exactly
3. **Be thorough in Implementation section:** Provide step-by-step guidance
4. **Include error handling:** Document failure scenarios and recovery
5. **Add examples:** Show common usage patterns
6. **Test before committing:** Verify the command works as expected
7. **Run the linter:** Use `make lint` to validate your plugin structure and format
8. **Respect ethical guidelines:** Never reference real people; describe specific qualities instead

### When Writing SKILL.md Files

1. **Be explicit:** Don't assume the AI knows domain-specific details
2. **Provide complete commands:** Include full bash/python commands with paths
3. **Handle edge cases:** Document what to do when things go wrong
4. **Include prerequisites:** List required tools and how to check for them
5. **Show examples:** Real-world examples help clarify complex workflows
6. **Respect ethical guidelines:** Never reference real people; describe specific qualities instead

### File Naming and Paths

- **Command files:** Use kebab-case: `analyze-test-failure.md`
- **Skill directories:** Use kebab-case: `prow-job-analyze-resource/`
- **Plugin names:** Use kebab-case: `prow-job`, `hello-world`
- **Working directories:** Use `.work/{plugin-name}/{command-name}/` for command output and temporary files (already in .gitignore)
  - Pattern: `.work/{plugin-name}/{command-name}/{identifier}/` for multi-file outputs **or** `.work/{plugin-name}/{command-name}/report-{identifier}.{ext}` for single files
  - Example: `.work/prow-job/analyze-resource/1234567890/` or `.work/jira/grooming/report-2025-01-29.md`
  - See "File Creation Patterns" section for detailed guidance

## Common Patterns

### Multi-Phase Commands

For commands with distinct phases (like `/jira:solve`):

```markdown
## Implementation

1. **Issue Analysis**: Parse JIRA URL and fetch issue details
   - Use curl to fetch data
   - Parse JSON response
   - Extract required fields

2. **Codebase Analysis**: Search and analyze relevant code
   - Find related files
   - Understand implementation
   - Identify changes needed

3. **Solution Implementation**: Make the changes
   - Create detailed plan
   - Ask user for approval
   - Implement changes
   - Run tests

4. **PR Creation**: Create pull request
   - Create feature branch
   - Make logical commits
   - Push to remote
   - Create draft PR
```

### Commands with Tool Dependencies

Always check for required tools and provide installation instructions:

```markdown
## Prerequisites

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - If not installed, provide instructions for user's platform
   - Installation guide: https://cloud.google.com/sdk/docs/install
```

### File Creation Patterns

Commands that create files should follow one of these standardized patterns based on their use case:

#### Pattern 1: Commands that Generate Reports/Artifacts (Default Pattern)

**Use case**: Analysis commands producing output files (HTML reports, JSON summaries, diagrams)

**Pattern**: `.work/{plugin-name}/{command-name}/{identifier}/`

**Example**:
```markdown
## Return Value
- **Format**: HTML report with analysis results
- **Location**: `.work/prow-job/analyze-resource/1234567890/report.html`
```

**When to use**:
- Commands generating analysis reports
- Commands creating visualization artifacts
- Commands downloading and processing external data
- Any command producing output files for user review

**Reference implementation**: `plugins/prow-job/skills/prow-job-analyze-resource/SKILL.md`

#### Pattern 2: Commands with Cached Data

**Use case**: Commands that download/cache external data for reuse

**Pattern**: Check if `.work/{plugin}/{command}/{id}/` exists, ask user to reuse or re-download

**Key behavior**:
```markdown
## Implementation
1. Check if `.work/{plugin}/{command}/{id}/` exists
2. If exists, use AskUserQuestion to prompt: "Cached data found. Reuse existing data or re-download?"
3. If user chooses reuse, skip download and use cached files
4. If user chooses re-download, download fresh data to same location
```

**When to use**:
- Commands downloading large files (CI logs, cluster data)
- Commands with expensive API calls
- Commands where cached data remains valid

**Reference implementation**: `plugins/prow-job/skills/prow-job-analyze-resource/SKILL.md` lines 94-108

#### Pattern 3: Commands with User-Specified Output Paths

**Use case**: User needs custom output locations (config files, YAML docs, scripts)

**Pattern**: Accept user path argument OR default to `.work/{plugin}/{command}/output.{ext}`

**Key behavior**:
```markdown
## Arguments
- $1: Required input parameter
- $2: (Optional) Output file path where the generated content will be written

## Implementation
1. Generate content based on $1
2. If $2 provided: Write to specified path using Write tool
3. If $2 omitted: Either write to `.work/{plugin}/{command}/output.{ext}` OR display to terminal
```

**When to use**:
- Commands generating configuration files
- Commands creating documentation
- Commands where user may want files in specific repository locations

**Reference implementations**:
- `plugins/yaml/commands/docs.md` - Displays to terminal when no output path specified
- `plugins/test-coverage/commands/gaps.md` - Writes to multiple format options

#### Pattern 4: Commands that Modify Repository Files

**Use case**: Files that must persist in repository root (session files, persistent logs)

**Pattern**: `{prefix}-{timestamp}-{description}.{ext}` in repository root

**Example**:
```markdown
## Return Value
- **Format**: Markdown session file
- **Location**: `session-2025-01-29-investigating-bug.md` (repository root)
```

**When to use**:
- Session save/restore functionality
- Persistent documentation that should be committed
- Files that need to be part of repository history

**Key characteristics**:
- Include timestamp for uniqueness
- Use descriptive names
- Place in repository root or specified subdirectory
- NOT temporary - intended to be committed

**Reference implementation**: `plugins/session/commands/save-session.md`

#### Pattern 5: Workspace and Configuration Directories

**Use case**: Commands creating workspaces outside repository

**Pattern**: Use configured workspace root, NOT `.work/`

**When to use**:
- Commands creating entire project workspaces
- Commands managing external environments
- Commands working with system-level configuration

**Key characteristic**: These commands manage directories outside the current repository

**Reference implementation**: `plugins/workspaces/commands/create.md`

#### Quick Reference Table

| Scenario | Pattern | Example Path | Display/File |
|----------|---------|--------------|--------------|
| Analysis report | Pattern 1 | `.work/prow-job/analyze-resource/123/report.html` | File |
| Cached CI logs | Pattern 2 | `.work/prow-job/analyze-resource/123/logs/` | File (with reuse prompt) |
| YAML documentation | Pattern 3 | `.work/yaml/docs/output.yaml` OR user-specified | File or terminal |
| Session save | Pattern 4 | `session-2025-01-29-investigating.md` | File (repo root) |
| External workspace | Pattern 5 | `~/workspaces/my-project/` | Directory (external) |

#### Best Practices

1. **Always use `.work/` for command output** (unless Pattern 4 or 5 applies)
2. **Include unique identifiers** in paths (timestamps, IDs, names) to avoid collisions
3. **Ask before overwriting** existing files - use AskUserQuestion
4. **Document output location** explicitly in Return Value section
5. **Show actual paths** in Examples section
6. **Never use `/tmp/`** for command output generation (only for user input examples)
7. **Preserve `.work/` in .gitignore** - output files should not be committed

#### Validation Checklist

When creating a new command or updating existing ones, verify:

- [ ] Return Value section documents exact output location
- [ ] Implementation section specifies which pattern is used
- [ ] Examples show actual file paths, not placeholders
- [ ] If generating files, uses appropriate pattern (1-5)
- [ ] If caching data, implements reuse prompt (Pattern 2)
- [ ] If accepting output path argument, documents default behavior (Pattern 3)
- [ ] No usage of `/tmp/` for output generation

## Available Plugins

| Plugin | Purpose | Key Commands |
|--------|---------|--------------|
| `hello-world` | Reference implementation | `/hello-world:echo` |
| `jira` | JIRA automation | `/jira:solve`, `/jira:status-rollup`, `/jira:grooming`, `/jira:outcome-refinement` |
| `prow-job` | Prow CI analysis | `/prow-job:analyze-test-failure`, `/prow-job:analyze-resource` |
| `ci` | OpenShift CI integration | `/ci:trigger-presubmit`, `/ci:ask-sippy` |
| `utils` | General utilities | `/utils:generate-test-plan`, `/utils:address-reviews` |
| `git` | Git workflows | `/git:bisect`, `/git:commit-suggest`, `/git:summary` |
| `session` | Session management | `/session:save-session` |

## Additional Resources

- **Example Plugin:** `plugins/hello-world/` - Minimal reference implementation
- **Complex Plugin:** `plugins/jira/` - Full-featured plugin with multiple commands
- **Skills Example:** `plugins/prow-job/skills/prow-job-analyze-resource/` - Detailed implementation guide
- **Main README:** `README.md` - User-facing documentation
- **Claude Code Docs:** https://docs.claude.com/en/docs/claude-code/

## Support

- **Issues:** https://github.com/openshift-eng/ai-helpers/issues
- **Repository:** https://github.com/openshift-eng/ai-helpers
