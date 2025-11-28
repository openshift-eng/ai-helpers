---
name: Jira Feature Documentation Generator
description: Detailed implementation guide for recursively analyzing Jira features and generating comprehensive documentation
---

# Jira Feature Documentation Generator

This skill provides detailed step-by-step implementation guidance for the `/jira:generate-feature-doc` command, which generates comprehensive feature documentation by recursively analyzing a Jira feature and all its related issues and GitHub pull requests.

**IMPORTANT FOR AI**: This is a **procedural skill** - when invoked, you should directly execute the implementation steps defined in this document. Do NOT look for or execute external scripts. Follow the step-by-step instructions below, starting with Step 1.

## When to Use This Skill

This skill is automatically invoked by the `/jira:generate-feature-doc` command and should not be called directly by users.

## Prerequisites

- **MCP Jira server configured and running** (required - see `plugins/jira/README.md` for setup)
- GitHub CLI (`gh`) installed and authenticated (for analyzing PRs)
- User has read access to Jira issues (including private issues via MCP authentication)
- User has read access to linked GitHub repositories
- Working directory has `.work/jira/feature-doc/` for output (will be created if needed)

## Implementation Steps

### Step 1: Initialize and Fetch Main Feature Issue

**Objective**: Set up environment and fetch main feature issue.

**Actions**:

1. **Save initial directory**: `INITIAL_DIR=$(pwd)` (save at start, before any cd commands)

2. **Check prerequisites**: Verify `jq` and `gh` CLI are installed and authenticated
   - If missing, display error with installation instructions

3. **Create output directory**: `WORK_DIR=$INITIAL_DIR/.work/jira/feature-doc/<feature-key>` (use `mkdir -p`)

4. **Fetch main feature**: Use MCP Jira tool to get issue with all fields:
   ```
   mcp__atlassian__jira_get_issue(issue_key=<feature-key>, fields="*all")
   ```
   - If MCP unavailable, display error pointing to `plugins/jira/README.md`

5. **Parse response**: Extract `key`, `summary`, `description`, `issuetype`, `status`
   - If fetch fails, display error and exit

6. **Display progress**: Show feature summary and type

### Step 2: Analyze Each GitHub PR

**Important**: This step expects PR data as input from the `jira:extract-prs` skill (invoked by the command file). The input is structured JSON containing all discovered PRs with their metadata.

**Input Format**:
```json
{
  "pull_requests": [
    {
      "url": "https://github.com/org/repo/pull/123",
      "state": "MERGED",
      "title": "PR title",
      "isDraft": false,
      "sources": ["remote_link", "description"],
      "found_in_issues": ["ISSUE-123"]
    }
  ]
}
```

**Objective**: Fetch and analyze PR details to extract implementation information.

**Important**: This command is for documenting **completed features**. Only analyze PRs that have been **MERGED**. Skip OPEN, DRAFT, WIP, or CLOSED (but not merged) PRs.

**Actions**:

1. **Filter for MERGED PRs**: Only analyze PRs with `state == "MERGED"` AND `isDraft == false`
   - Skip OPEN PRs (work in progress)
   - Skip PRs with `isDraft == true` (not ready for review)
   - Skip CLOSED PRs (not merged)

2. **For each MERGED PR, fetch detailed data**:
   - Parse PR URL to extract org/repo/number
   - Fetch metadata: `gh pr view {number} --repo {org}/{repo} --json title,body,mergedAt,author,commits,files`
   - Fetch diff: `gh pr diff {number} --repo {org}/{repo}`
   - Fetch comments: `gh pr view {number} --repo {org}/{repo} --json comments`

3. **Extract key information**:
   - **From body**: Purpose, approach, breaking changes
   - **From commits**: Implementation steps, testing
   - **From diff**: New APIs, architectural changes, config updates
   - **From comments**: Design decisions, rationale, considerations

4. **Handle errors**: If PR inaccessible (403, 404), log warning and continue

5. **Save data**: Store metadata, diff, and comments to `${WORK_DIR}/pr-{org}-{repo}-{number}.*`

### Step 3: Synthesize Documentation Structure

**Objective**: Organize information into structured outline.

**Available sections** (calling command specifies which to generate):

1. **Overview**: Jira link, status, counts, dates, authors (from main issue + PR metadata)
2. **Background and Goals**: Description from main issue (clean Jira formatting)
3. **Architecture and Design**: High-level changes, components, design decisions (from PRs)
4. **Implementation Details**: Core changes, API changes, configuration (from PR diffs, code snippets)
5. **Usage Guide**: Prerequisites, basic/advanced usage (from README updates, PR descriptions)
6. **Testing**: Test coverage, strategies, key test PRs
7. **Related Resources**: Can include external links, issue tables, PR tables, dependency graphs

### Step 4: Generate Documentation Content

**Objective**: Fill in the outline with actual content based on command requirements.

**Section generation guidelines**:

1. **Overview**: Extract from main issue + PR metadata (Jira link, status, counts, dates, authors)
2. **Background**: Clean Jira formatting from main issue description
3. **Architecture**: Synthesize from PR descriptions and comments (high-level overview, components, decisions with PR links)
4. **Implementation**: Group by core changes, API changes, configuration (include code snippets, link to PRs, list key files)
5. **Usage**: Extract from README updates and PR descriptions (prerequisites, YAML/CLI examples)
6. **Testing**: Summarize by category (unit, E2E, CI), list key test PRs
7. **Related Resources**: Format depends on command requirements (external links, tables, graphs)

**Note**: Only generate sections specified by the calling command. Check the command file for exact requirements.

### Step 5: Output

**Objective**: Save documentation and display summary.

**Actions**:

1. **Write documentation**: Save to `${WORK_DIR}/feature-doc.md` with footer:
   ```markdown
   ---
   *Generated by `/jira:generate-feature-doc` on <timestamp>*
   *Source: <feature-key> and <count> related issues*
   ```

2. **Save metadata**: Store analysis log with timestamps, counts, output files, errors/warnings

3. **Display summary**:
   - Success message with file location
   - Statistics: issues analyzed, PRs analyzed, commits, files changed, doc lines
   - Warnings if any (inaccessible PRs, missing descriptions)
   - Additional files for debugging

## Error Handling

**Issue Not Found** (404, 403, network error):
- Display error with verification steps (issue key format, permissions, MCP config)
- Exit gracefully without creating files

**No PRs Found**:
- Display warning (feature not implemented, PRs not linked, or small feature)
- Generate documentation from main issue only

**GitHub Rate Limit**:
- Display error with progress and reset time
- Offer options: wait, generate from partial data, or cancel

**Large Feature** (>50 PRs):
- Display warning with estimated time and API calls
- Offer options: continue or cancel

**Malformed Issue Data**:
- Log warning about missing/invalid fields
- Continue with remaining issues (don't fail entire process)

## Performance Optimization

**Parallel PR Analysis**:
- For >10 PRs, use parallel processing (`xargs -P 5`)
- Limit to ~5 concurrent requests to avoid rate limits

**Smart Diff Analysis**:
- Use `--stat` to identify key files
- Skip vendor/, generated files, test fixtures
- Fetch full diff only for critical files

## Best Practices for AI Implementation

1. **Progress feedback**: Show progress after each major step (discovery, PR analysis, etc.)

2. **Error resilience**: Don't fail the entire process if one PR is inaccessible

3. **Smart synthesis**: Don't just concatenate PR descriptions - synthesize into coherent narrative

4. **Context awareness**: Understand the codebase domain (e.g., Kubernetes, OpenShift) to better interpret changes

5. **Structured output**: Use consistent markdown formatting with proper headers, code blocks, tables

6. **Link preservation**: Always provide clickable links to Jira issues and GitHub PRs

7. **Timestamp tracking**: Note when PRs were merged to understand timeline

8. **Author attribution**: Credit authors of PRs and issues where relevant

9. **Code examples**: Include actual code snippets from PRs to illustrate changes

10. **Visual hierarchy**: Use tables, lists, and headers to make documentation scannable

## Example Workflow

```
User runs: /jira:generate-feature-doc OCPSTRAT-1612

1. Initialize
   - Fetch main feature issue (OCPSTRAT-1612)
   - Create working directory (.work/jira/feature-doc/OCPSTRAT-1612/)
   - Verify prerequisites (jq, gh CLI)

2. Extract PRs (via extract-prs skill)
   - Discover descendants using childIssuesOf() JQL → 3 issues total
   - Extract PRs from remote links (primary) + text (backup) → 7 PRs
   - Fetch PR state from GitHub → 5 MERGED, 1 OPEN, 1 CLOSED

3. Analyze MERGED PRs
   - Filter for MERGED PRs → 5 PRs to analyze
   - For each: fetch metadata + diff + comments
   - Extract implementation details, design decisions

4. Generate Documentation
   - Synthesize sections: Overview, Architecture, Implementation, Usage, Testing
   - Create tables for issues and PRs
   - Write to feature-doc.md

5. Display Results
   ✅ Documentation generated successfully!
   📄 File: .work/jira/feature-doc/OCPSTRAT-1612/feature-doc.md
   📊 3 issues, 5 MERGED PRs, ~380 lines generated
```
