---
name: generate-test-plan
description: Generate a comprehensive manual testing guide from a Jira issue, GitHub PR URLs, or both. Use when the user wants test steps, a QE test plan, or a testing guide for code changes.
---

## Name
openshift-developer:generate-test-plan

## Synopsis
```text
/openshift-developer:generate-test-plan <JIRA_KEY | PR_URL> [additional PR URLs...]
```

## Description
Generates a comprehensive manual testing guide by analyzing a Jira issue, one or more GitHub PRs, or both. Consolidates context from Jira acceptance criteria, PR diffs, commit messages, and changed files into actionable test scenarios.

When given a Jira key, it auto-discovers linked PRs. When given PR URLs directly, it works without Jira. Both can be combined.

## Implementation

### Step 1: Parse input and gather sources

1. Parse arguments:
   - If `$1` matches a Jira issue key pattern (e.g. `CNTRLPLANE-205`, `OCPBUGS-12345`): treat as Jira key
   - If `$1` is a GitHub URL: treat as PR URL (no Jira context)
   - Remaining arguments (`$2`, `$3`, ...): additional PR URLs

2. **If a Jira key was provided**, fetch Jira issue details using the Jira MCP tools (`mcp__atlassian__jira_get_issue`):
   - Issue summary, description, acceptance criteria
   - Steps to reproduce (for bugs)
   - Issue type (Story, Bug, Task, etc.)

3. **Discover PRs**:
   - If explicit PR URLs were provided: use only those
   - If only a Jira key was provided: use `mcp__atlassian__jira_get_issue` with `include: "remote_links"` and look for GitHub PR links. Also check the issue description and comments for PR URLs.
   - For each PR, fetch details:
     ```bash
     gh pr view <PR_NUMBER> --repo <owner/repo> --json title,body,commits,files,labels,state
     ```
   - Read changed files and their diffs to understand implementation

### Step 2: Analyze changes

1. Identify the type of change (feature, bug fix, refactor)
2. Determine affected components (API, CLI, operator, control-plane, etc.)
3. Find platform-specific changes (AWS, Azure, KubeVirt, etc.)
4. When multiple PRs exist:
   - Map which PR addresses which component or aspect
   - Identify dependencies between PRs
   - Determine testing order
5. Use Grep and Glob to find related test files, configuration, and documentation

### Step 3: Generate test scenarios

1. Map Jira acceptance criteria to test cases (when Jira context available)
2. For bugs: derive test cases from reproduction steps
3. Generate scenarios covering:
   - Happy path (based on acceptance criteria or PR description)
   - Edge cases and error handling
   - Platform-specific variations if applicable
   - Regression scenarios for related features
4. For multiple PRs: create integration scenarios verifying PRs work together

### Step 4: Apply smart filtering

Skip PRs that don't require testing:
- PRs with only documentation changes (`.md` files)
- PRs with only CI/tooling changes (`.github/`, `.claude/` directories)
- PRs with labels like `skip-testing` or `docs-only`

Note skipped PRs in the output with reasoning.

### Step 5: Create the test guide

**Filename convention**:
- Jira-based: `test-{jira-key-lowercase}.md` (e.g. `test-cntrlplane-205.md`)
- PR-only: `test-pr-{number1}-{number2}.md` (e.g. `test-pr-6888-6889.md`)

**Document structure**:

- **Summary**: Jira key + title (if available), list of PRs with titles, overall objective
- **Prerequisites**: Required infrastructure, tools, environment setup, access requirements
- **Test Scenarios**: Numbered test cases with:
  - Clear step-by-step instructions
  - Expected results and verification commands
  - Mapping to acceptance criteria (when Jira context available)
  - Platform-specific variations where applicable
- **Regression Testing**: Related features to verify, areas that might be affected
- **Success Criteria**: Checklist mapping to Jira acceptance criteria (when available)
- **Troubleshooting**: Common issues and debug steps
- **Notes**: Known limitations, links to Jira and PRs, dependencies between PRs

**Exclusions**: Do NOT include build/deploy steps or cleanup steps. Assume the environment is already set up. Focus purely on testing procedures.

### Step 6: Report

- Show the file path where the guide was saved
- Summarize: Jira issue (if applicable), number of PRs analyzed, number of test scenarios, critical test cases
- Highlight skipped PRs and reasoning
- Ask if the user wants modifications

## Examples

1. **From a Jira issue (auto-discovers PRs)**:
   ```text
   /openshift-developer:generate-test-plan CNTRLPLANE-205
   ```

2. **From a Jira issue with specific PRs only**:
   ```text
   /openshift-developer:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
   ```

3. **From PR URLs only (no Jira)**:
   ```text
   /openshift-developer:generate-test-plan https://github.com/openshift/hypershift/pull/6888
   ```

4. **Multiple PRs without Jira**:
   ```text
   /openshift-developer:generate-test-plan https://github.com/openshift/hypershift/pull/6888 https://github.com/openshift/hypershift/pull/6889
   ```

## Arguments
- `$1` — Jira issue key (e.g. `CNTRLPLANE-205`) or a GitHub PR URL (required)
- `$2, $3, ..., $N` — Additional GitHub PR URLs (optional)

## Guidelines
- Use Jira MCP tools for Jira data, `gh` CLI for PR data
- Derive test scenarios from actual code changes, not assumptions
- Keep test steps concrete with exact commands and expected output
- When Jira acceptance criteria exist, map every criterion to at least one test case
