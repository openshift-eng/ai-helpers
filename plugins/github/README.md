# GitHub Plugin

A Claude Code plugin for automating GitHub workflows, with a focus on intelligent issue management and triage.

## Overview

The GitHub plugin provides AI-powered automation for common GitHub repository management tasks. It leverages Claude's natural language understanding to analyze issues, apply appropriate labels, and maintain consistent categorization across your repositories.

## Commands

### `/github:issue-triage`

Automatically triage and label GitHub issues using AI-powered content analysis.

**Usage:**
```
/github:issue-triage <owner/repo> [issue-number]
```

**Arguments:**
- `owner/repo` (required): Repository in format `owner/repo` (e.g., `openshift-eng/ai-helpers`)
- `issue-number` (optional): Specific issue number to triage. If omitted, triages all open unlabeled issues.

**Examples:**
```
# Triage a specific issue
/github:issue-triage openshift-eng/ai-helpers 184

# Triage all unlabeled issues
/github:issue-triage kubernetes/kubernetes

# Triage issue in personal repo
/github:issue-triage username/my-project 42
```

**Features:**
- Analyzes issue title and description for technical content
- Identifies issue type (bug, enhancement, question, documentation, etc.)
- Detects affected components and areas
- Applies labels based on repository's existing label set
- Provides detailed reasoning for label selections
- Handles batch triage for multiple issues
- Conservative approach to avoid misclassification

**Prerequisites:**
- GitHub CLI (`gh`) installed and authenticated
- Write access to the target repository

**Output:**
The command provides a summary table showing:
- Issues triaged
- Labels applied to each issue
- Reasoning for label selection
- Any warnings or issues requiring manual review

## Installation

### From Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the github plugin
/plugin install github@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Link to Claude Code commands directory
mkdir -p ~/.claude/commands
ln -s "$(pwd)/ai-helpers" ~/.claude/commands/ai-helpers
```

## Prerequisites

This plugin requires:

1. **GitHub CLI (gh)**
   - Install from: https://cli.github.com/
   - Authenticate: `gh auth login`
   - Verify: `gh auth status`

2. **Repository Permissions**
   - Write access to repositories you want to triage
   - For organization repos, ensure proper team permissions

## How It Works

The issue triage command follows this workflow:

1. **Fetch Issue Data**: Retrieves issue details using GitHub CLI
2. **Fetch Repository Labels**: Gets all available labels from the repository
3. **AI Analysis**: Analyzes issue content to understand:
   - Issue type and intent
   - Technical areas and components affected
   - Clarity and completeness
4. **Label Selection**: Chooses appropriate labels based on:
   - Repository's existing label taxonomy
   - Objective criteria from issue content
   - Best practices for categorization
5. **Apply Labels**: Updates the issue with selected labels
6. **Report Results**: Provides detailed summary of changes

## Label Selection Criteria

The AI uses the following criteria when selecting labels:

- **Type Labels**: `bug`, `enhancement`, `question`, `documentation`
- **Area/Component Labels**: Repository-specific labels for different modules or areas
- **Status Labels**: `needs-triage`, `needs-info`, `good-first-issue`
- **Platform Labels**: OS or environment-specific labels when relevant
- **Special Flags**: `duplicate`, `wontfix`, `stale` when appropriate

**Important Constraints:**
- Only uses labels that exist in the repository
- Avoids priority labels (p0, p1, p2) unless explicitly required
- Does not post comments on issues
- Applies 2-5 labels per issue for optimal categorization
- Uses `needs-info` for vague or unclear issues

## Use Cases

### Daily Triage for Active Repositories

```bash
# Triage all new unlabeled issues
/github:issue-triage my-org/my-project
```

Run this daily to keep up with new issues in active repositories.

### Pre-Planning Triage

```bash
# Triage specific issues before sprint planning
/github:issue-triage my-org/my-project 101
/github:issue-triage my-org/my-project 102
/github:issue-triage my-org/my-project 103
```

Prepare issues for team review by ensuring they're properly labeled.

### Bulk Cleanup

```bash
# Clean up unlabeled backlog
/github:issue-triage legacy-org/legacy-project
```

Apply consistent labels to older issues that were never triaged.

## Best Practices

1. **Review AI Decisions**: While the AI is objective, always review applied labels for accuracy
2. **Customize Repository Labels**: Maintain a clear, well-organized label structure in your repository
3. **Use Descriptive Labels**: Ensure repository labels have clear names and descriptions
4. **Batch Triage Carefully**: For large backlogs, triage in smaller batches to review results
5. **Combine with Manual Review**: Use AI triage as a first pass, then refine manually
6. **Regular Cadence**: Run triage regularly to avoid backlog buildup

## Limitations

- Maximum 100 issues processed per batch to avoid rate limiting
- Requires GitHub API access and appropriate permissions
- Label selection limited to repository's existing labels
- Cannot create new labels automatically
- Does not modify issue assignees, milestones, or other properties

## Troubleshooting

### "gh: command not found"
Install GitHub CLI from https://cli.github.com/

### "authentication required"
Run `gh auth login` to authenticate with GitHub

### "permission denied"
Ensure you have write access to the repository

### "rate limit exceeded"
Wait a few minutes before retrying, or reduce batch size

### "label not found"
The command only uses existing labels; check your repository's label list

## Contributing

Contributions are welcome! To add new commands or improve existing ones:

1. Fork the repository
2. Create a feature branch
3. Add or modify commands in `plugins/github/commands/`
4. Update this README
5. Run `make lint` to validate
6. Submit a pull request

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Documentation**: https://github.com/openshift-eng/ai-helpers
- **Claude Code Docs**: https://docs.claude.com/

## License

See the main repository for license information.
