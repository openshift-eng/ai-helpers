# Onboarding Plugin

The onboarding plugin helps new hires learn about **general OpenShift knowledge and automation** available to all teams, regardless of which specific team they join.

## Purpose

OpenShift consists of **dozens of teams** working across **many repositories**. This plugin focuses on **general resources** useful to all teams, not team-specific onboarding.

### General Resources (All Teams)

1. **ai-helpers** (this repo) - General automation tools for common tasks
2. **openshift/enhancements** - General OpenShift architecture and design knowledge

### Team-Specific Resources (Not Covered Here)

Each team has their own:
- Component repositories (operators, controllers, etc.)
- Team documentation and runbooks
- Team-specific tools and workflows

**Team-specific onboarding is handled by each team separately.**

## What This Plugin Does

This plugin helps new hires:
- Understand what general OpenShift resources are available
- Access the enhancements repo for architectural knowledge
- Use general automation tools (JIRA, CI analysis, etc.)
- Search general OpenShift documentation
- Learn that team-specific onboarding happens elsewhere

## Commands

### `/onboarding:start`

**Purpose:** Introduce general OpenShift resources and automation tools

**Usage:**
```bash
/onboarding:start
```

**What it does:**
- Explains the purpose of ai-helpers (general automation)
- Detects if enhancements repo is available (general knowledge)
- Checks environment variables (JIRA credentials, etc.)
- Lists general automation tools available to all teams
- **Reminds users about team-specific onboarding**

**When to use:**
- First command to understand general resources
- Learning what automation is available across all teams
- Understanding what enhancements repo contains
- Getting oriented to general OpenShift knowledge

**Output:**
- ✅ Shows available general resources
- 📚 Explains what enhancements repo contains
- 🤖 Lists general automation commands
- ⚠️ Reminds about team-specific onboarding

### `/onboarding:search`

**Purpose:** Search general OpenShift documentation (not team-specific repos)

**Usage:**
```bash
/onboarding:search <search-term>

# Examples:
/onboarding:search networking          # Find general networking KEPs
/onboarding:search "kube-apiserver"   # General kube-apiserver docs
/onboarding:search "enhancement process"  # OpenShift processes
```

**What it does:**
- Searches ai-helpers (general automation) and enhancements (general knowledge)
- Prioritizes enhancement proposals (KEPs) about OpenShift features
- Finds general automation tools
- **Does NOT search team-specific component repos**

**When to use:**
- Learning how OpenShift features work (cross-component)
- Finding KEPs about general OpenShift architecture
- Discovering general automation tools
- Understanding OpenShift design decisions
- **NOT for team-specific component documentation** (search your team's repos directly)

**Output:**
- 📚 Enhancement proposals (general OpenShift knowledge)
- 🤖 General automation tools and commands
- 📖 General process documentation
- ⚠️ Note: Does not search team-specific repos

## Use Cases

### Learning General OpenShift Knowledge

```bash
# 1. New hire wants to understand general resources
/onboarding:start
# Output: Explains ai-helpers (automation) and enhancements (knowledge)
#         Reminds about team-specific onboarding

# 2. Clone enhancements for general knowledge (optional)
cd .. && git clone https://github.com/openshift/enhancements.git

# 3. Search for general OpenShift architecture info
/onboarding:search "how does the installer work"
# Output: KEPs about installer design, general architecture

# 4. Meanwhile, ask team lead about team-specific repos
# (Your team handles that separately)
```

### Finding General Documentation

```bash
# Learn about general OpenShift networking
/onboarding:search networking

# Output shows:
# - KEPs about OpenShift network architecture
# - General automation tools for network components
# - Does NOT show team-specific network operator code
#   (search your team's repo for that)
```

### Understanding Available Automation

```bash
# What general tools are available?
/onboarding:start

# Output shows:
# - JIRA automation commands (all teams)
# - CI analysis tools (all teams)
# - Component health tracking (all teams)
```

## Architecture

### Repository Detection

The plugin searches common locations for the `openshift/enhancements` repo:
- `../enhancements` (sibling directory)
- `../openshift-enhancements` (alternative name)
- `~/go/src/github.com/openshift/enhancements` (Go workspace)
- `~/src/openshift/enhancements` (src directory)

This covers most common clone patterns without requiring configuration.

### Search Strategy

1. **Search ai-helpers** (always available)
   - Commands and tool documentation
   - Quick reference guides
   - Plugin READMEs

2. **Search enhancements** (if available)
   - Enhancement proposals (KEPs)
   - Architecture documentation
   - Process guides

3. **Categorize and prioritize results**
   - KEPs ranked highest (most valuable for learning)
   - Commands second (most actionable)
   - General docs third (supporting information)

### Graceful Degradation

The plugin is designed to be helpful even with incomplete setup:
- Works without enhancements repo (limited search)
- Works without environment variables (shows setup instructions)
- Never errors, always provides guidance

## Integration with Other Plugins

The onboarding plugin complements other plugins:

- **JIRA plugin**: Checks JIRA credentials, guides setup
- **Component Health plugin**: Suggests bug analysis commands
- **CI plugin**: Points to CI analysis tools
- **Prow Job plugin**: Highlights test failure analysis

## Files

```
plugins/onboarding/
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata
├── commands/
│   ├── start.md                 # Setup verification command
│   └── search.md                # Cross-repo search command
├── skills/
│   ├── start/
│   │   └── SKILL.md             # Setup verification implementation
│   └── search/
│       └── SKILL.md             # Search implementation
└── README.md                    # This file
```

## Configuration

No configuration required! The plugin:
- Auto-detects repository locations
- Works with or without the enhancements repo
- Provides setup guidance for missing components

## Best Practices

### For New Hires

1. **Always run `/onboarding:start` first** - Verifies your setup
2. **Clone both repositories** - You need both for effective work
3. **Use `/onboarding:search`** - Don't waste time grepping manually
4. **Keep repos as siblings** - Simplest detection pattern

### For Managers/Mentors

1. **Add to onboarding docs**: Tell new hires to run `/onboarding:start`
2. **Verify workspace file**: Share `openshift-eng.code-workspace` for easy setup
3. **Point to this README**: Explains the multi-repo philosophy

## Future Enhancements

Potential improvements:
- Detect additional repos (operator repos, test repos, etc.)
- Cache search results for faster repeated queries
- Integration with team-specific onboarding checklists
- Suggest relevant enhancement proposals based on JIRA component
- Track onboarding progress (which commands have been tried)

## Troubleshooting

### "Enhancements repo not detected"

The repo is in an unusual location. Either:
1. Clone it to a standard location (see `/onboarding:start`)
2. Create a symlink: `ln -s /your/path/enhancements ../enhancements`

### "No search results found"

Try:
1. Broader search terms
2. Check spelling
3. Verify enhancements repo is cloned (`/onboarding:start`)
4. Ask Claude directly about the topic

### "JIRA credentials not working"

1. Run `/onboarding:start` to check configuration
2. Verify token hasn't expired in JIRA
3. Check `echo $JIRA_PERSONAL_TOKEN` shows a value

## See Also

- Main README: `../../README.md` (multi-repo setup guide)
- Workspace file: `../../openshift-eng.code-workspace` (VS Code multi-repo workspace)
- Enhancements repo: https://github.com/openshift/enhancements
