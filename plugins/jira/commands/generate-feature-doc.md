---
description: Generate comprehensive feature documentation from Jira feature and all related issues and PRs
argument-hint: <feature-key>
---

## Name
jira:generate-feature-doc

## Synopsis
```
/jira:generate-feature-doc <feature-key>
```

## Description

The `jira:generate-feature-doc` command generates comprehensive feature documentation by recursively analyzing a Jira feature ticket and all its related issues, sub-tasks, and linked GitHub pull requests.

This command is particularly useful for:
- Creating complete feature documentation after implementation
- Understanding the full scope and implementation details of a feature
- Generating onboarding materials for new team members
- Creating technical design documents from actual implementation
- Documenting complex features with multiple related issues and PRs

The command performs deep analysis of:
- The main feature issue and all related Jira tickets (recursively)
- All linked GitHub PRs, commits, and code changes
- Design decisions captured in PR discussions and code reviews
- Implementation details from actual code changes

## Implementation

This command orchestrates two skills in sequence to generate comprehensive feature documentation:

1. **Extract GitHub PRs** (via `jira:extract-prs` skill)
   - Discovers all descendant issues recursively using `childIssuesOf()` JQL
   - Extracts PR URLs from Jira Remote Links (primary) and text content (backup)
   - Fetches PR metadata from GitHub (state, title)
   - Returns structured JSON with deduplicated PRs

2. **Generate Documentation** (via `jira-doc-generator` skill)
   - Receives PR data from step 1
   - Analyzes MERGED PRs only (fetches metadata, diff, comments)
   - Synthesizes feature documentation with the following sections:
     * Overview
     * Background and Goals
     * Architecture and Design
     * Usage Guide
     * Related Resources (External Links only)
   - Skip sections: Implementation Details, Testing
   - Outputs to `.work/jira/feature-doc/<feature-key>/feature-doc.md`

For detailed implementation, see:
- `plugins/jira/skills/extract-prs/SKILL.md`
- `plugins/jira/skills/jira-doc-generator/SKILL.md`

## Arguments

- **$1 – feature-key** *(required)*
  Jira issue key for the feature (e.g., `OCPSTRAT-1612`).
  Can be any issue type, but typically used for Features, Epics, or Stories.

## Return Value

- **Documentation File**: `.work/jira/feature-doc/<feature-key>/feature-doc.md`
- **Summary Statistics**: Number of issues analyzed, PRs analyzed, total lines of documentation
- **Related Resources**: List of all Jira issues and GitHub PRs included in the analysis
- **Debug Files**: Raw issue data, PR data, and analysis log

## Output Format

The command generates a comprehensive markdown document at:
```
.work/jira/feature-doc/<feature-key>/feature-doc.md
```

### Document Structure

```markdown
# Feature: <Feature Title>

## Overview
- **Jira Issue**: <main issue link>
- **Status**: <status>
- **Related Issues**: <count>
- **Related PRs**: <count>
- **Implementation Period**: <date range>

## Background and Goals
<Extracted from feature description>

## Architecture and Design
<Synthesized from design discussions and PR descriptions>

## Usage Guide
<How to use the implemented feature>

## Related Resources
<External links only - no tables>
```

## Examples

### Basic Usage

Generate documentation for a feature:
```
/jira:generate-feature-doc OCPSTRAT-1612
```

The command will:
1. Fetch the main feature issue
2. Recursively discover all related issues (sub-tasks, linked issues, etc.)
3. Extract all GitHub PR links from Remote Links API and text
4. Analyze each PR (description, code changes, discussions)
5. Synthesize all information into a comprehensive document
6. Save to `.work/jira/feature-doc/OCPSTRAT-1612/feature-doc.md`
7. Display summary statistics

### Example Output

```
📋 Analyzing OCPSTRAT-1612...

🔗 Discovering related issues (subtasks only)...
  ✓ Found main feature: "Configure and Modify Internal OVN IPV4 Subnets"
  ✓ Discovered 2 subtasks
  Total issues: 3

🔗 Extracting GitHub PRs...
  - From text (descriptions/comments): 1 PR
  - From Remote Links API (PRIMARY): 6 PRs
  Total unique PRs: 7 (after deduplication)

🔍 Analyzing PRs (MERGED only)...
  ✓ [1/7] openshift/hypershift#6444 (MERGED)
  ⚠️  [2/7] openshift/hypershift#6500 (OPEN - skipped)
  ✓ [3/7] openshift/hypershift#6554 (MERGED)
  ...

📝 Generating documentation...
  ✓ Feature overview and background
  ✓ Architecture and design section
  ✓ Implementation details
  ✓ Related resources index

✅ Documentation generated successfully!

📄 File: .work/jira/feature-doc/OCPSTRAT-1612/feature-doc.md
📊 Statistics:
  - Jira issues analyzed: 3 (1 feature + 2 subtasks)
  - GitHub PRs discovered: 7
  - GitHub PRs analyzed: 5 (MERGED only)
  - GitHub PRs skipped: 2 (1 OPEN, 1 CLOSED)
  - Total commits: 12
  - Total files changed: 41
  - Documentation lines: 150
```

## Error Handling

For complete error handling documentation, see SKILL.md. Common scenarios:

- **Issue Not Found**: 404 from Jira API - verify issue key and permissions
- **No Related Issues or PRs**: Feature may not be implemented yet - generates docs from main issue only
- **Circular Dependencies**: Cycle detection prevents infinite loops
- **GitHub Rate Limit**: Can resume after rate limit reset or generate partial docs
- **PR Not Accessible**: Skips inaccessible PRs (403, 404) but lists them in output
- **Large Feature**: Warns when >50 issues/PRs, allows user to cancel

See `jira-doc-generator` SKILL.md Section "Error Handling" for detailed guidance.

## Prerequisites

### Required Tools

1. **jq** - JSON parser
   - Check: `which jq`
   - Install: `brew install jq` (macOS) or `apt-get install jq` (Linux)

2. **GitHub CLI (`gh`)** - For fetching PR data
   - Install: `brew install gh` (macOS) or see [GitHub CLI docs](https://cli.github.com/)
   - Authenticate: `gh auth login`
   - Verify: `gh auth status`

3. **JIRA Access** - Read permissions for issues
   - Network access to `https://issues.redhat.com`

4. **GitHub Access** - Read access to repositories where PRs are located
   - PRs in private repos require appropriate GitHub permissions

### Performance Considerations

- **Time**: Large features may take 5-10 minutes to analyze completely
- **API Quota**: Each PR analysis uses ~3-4 GitHub API calls
- **Rate Limits**: GitHub allows 5,000 API calls/hour when authenticated
- **Disk Space**: Generated documents typically range from 10KB to 500KB

## Best Practices

1. **Link issues properly**: Ensure sub-tasks and related issues are properly linked in Jira
2. **Use Remote Links**: Add GitHub PRs via "Link Issue" in JIRA UI (not just in descriptions)
3. **Use for completed features**: Best results when feature is fully implemented
4. **Review and edit**: Generated documentation is a starting point - review and enhance manually
5. **Save the output**: Keep generated docs in version control for team reference

## See Also

- `jira:solve` - Analyze and solve Jira issues
- `jira:create-release-note` - Generate release notes from bugs and PRs
- `jira:status-rollup` - Create status rollup reports
- `utils:generate-test-plan` - Generate test plans for features

## Technical Notes

### Recursive Discovery Algorithm

Uses depth-first search with cycle detection:
- Maximum recursion depth: 5 levels (configurable)
- Visited issues tracked in a set to prevent re-processing
- **Only explores**: subtasks and parent issues
- **Does NOT explore**: issuelinks (relates, blocks, clones, duplicates) - these represent separate features

See SKILL.md Step 2 for complete algorithm details.

### GitHub PR Extraction Strategy

**Dual-source approach** (implemented in SKILL.md Step 3):
1. **Primary**: JIRA Remote Links API (`/rest/api/2/issue/{key}/remotelink`)
   - Authoritative source for PRs added via "Link Issue" UI
   - NOT included in main issue API response
2. **Backup**: Text extraction from descriptions and comments
   - Regex: `https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/pulls?/[0-9]+`

Both sources are merged and deduplicated.

### PR Analysis Filter

**Only MERGED PRs are analyzed** (implemented in SKILL.md Step 4):
- **MERGED**: Analyzed and included in documentation
- **OPEN**: Skipped (work in progress, may change)
- **CLOSED**: Skipped (not merged, implementation not accepted)

This ensures documentation reflects only shipped implementation.

### Output Directory Structure

```
.work/jira/feature-doc/<feature-key>/
├── feature-doc.md           # Main documentation
├── main-issue.json          # Main feature issue data
├── issue-*.json             # Related issue data
├── pr-*.json                # PR metadata
├── pr-*.diff                # PR diffs
├── pr-urls.txt              # All discovered PR URLs
└── analysis-log.txt         # Analysis log (for debugging)
```
