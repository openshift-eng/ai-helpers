---
name: Generate Test Plan
description: Shared implementation for JIRA test plans and bug reproducer reports from issue details and fix PRs
---

# Generate Test Plan

This skill analyzes a JIRA issue and related fix PRs to produce either a **manual test plan** or a **bug reproducer report**. It is invoked by:

- `/jira:generate-test-plan` — test plan mode (default)
- `/jira:generate-test-plan --reproducer` — reproducer mode
- `/jira:generate-bug-reproducer` — reproducer mode (alias)

## When to Use This Skill

Use **test plan mode** when QE or a developer needs step-by-step guidance to validate a fix after it is applied, including regression coverage.

Use **reproducer mode** when the JIRA bug lacks complete reproduction steps and you need to infer how to trigger the bug from the fix PR diff and JIRA narrative, then verify the fix resolves it.

## Prerequisites

- JIRA credentials (`JIRA_USERNAME`, `JIRA_API_TOKEN`) or Jira MCP server configured
- `gh` CLI authenticated for GitHub PR access
- `jq` available for JSON parsing

## Input Format

| Parameter | Required | Description |
|-----------|----------|-------------|
| JIRA issue key | Yes | e.g. `OCPBUGS-12345`, `CNTRLPLANE-205` |
| PR URLs | No | One or more GitHub PR URLs; auto-discovered from JIRA if omitted |
| Mode | No | `test-plan` (default) or `reproducer` |

## Implementation Steps

### Step 1: Parse Arguments

1. Extract the JIRA issue key from `$1`
2. Collect optional PR URLs from remaining arguments
3. Detect `--reproducer` flag in any argument position
4. Set mode:
   - `reproducer` if `--reproducer` is present or the mode is explicitly set to `reproducer` by the invoking command
   - `test-plan` otherwise
5. For reproducer mode on non-bug issue types, warn the user and continue with best effort

### Step 2: Fetch JIRA Issue

Fetch issue data via Jira MCP `getJiraIssue` or REST API:

```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/issue/{ISSUE_KEY}"
```

For issues.redhat.com projects, also try:

```bash
curl -s -H "Authorization: Bearer $JIRA_PERSONAL_TOKEN" \
  "https://issues.redhat.com/rest/api/2/issue/{ISSUE_KEY}"
```

Extract:

- Summary, description (convert ADF to plain text if needed)
- Issue type, status, components, labels
- Steps to reproduce, expected vs actual behavior (for bugs)
- Acceptance criteria (for stories/features)
- Linked development items and comments containing PR URLs

### Step 3: Discover Pull Requests

**If PR URLs were provided:** use only those.

**If no PR URLs provided:**

1. Scan JIRA description, remote links, and comments for `github.com/*/pull/*` URLs
2. Use WebFetch on `https://issues.redhat.com/browse/{ISSUE_KEY}` or the Atlassian browse URL
3. Check Development panel and issue links for PR references

If no PRs are found in reproducer mode, warn that root-cause inference will rely on JIRA text only and confidence will be lower.

### Step 4: Analyze Pull Requests

For each PR:

```bash
gh pr view {URL_OR_NUMBER} --json title,body,commits,files,labels,state,baseRefName,headRefName
```

```bash
gh pr diff {URL_OR_NUMBER}
```

Analyze:

- What behavior changed and why (infer the bug from the fix)
- Affected components (API, CLI, operator, controller, etc.)
- Platform or configuration preconditions
- Related test files in the diff
- Dependencies between multiple PRs — for multi-PR issues, identify how PRs interact and create integrated test scenarios that verify they work correctly together

**Skip PRs that don't need analysis** (note them in the report):

- Documentation-only changes (`.md` files only)
- CI/tooling-only changes (`.github/`, `.claude/`)
- PRs labeled `skip-testing` or `docs-only`

Use Grep and Glob in the target repository to find related tests, configs, and usage examples.

### Step 5: Cross-Reference JIRA and PR Analysis

| Source | Test plan mode | Reproducer mode |
|--------|----------------|-----------------|
| JIRA steps to reproduce | Use as test cases when present | Use as primary source when complete |
| JIRA expected/actual | Map to verification criteria | Define broken vs correct behavior |
| PR diff | Inform test scenarios and regression scope | **Infer** missing reproduction steps and root cause |
| PR description | Supplement test coverage | Extract author-stated trigger conditions |

In reproducer mode, explicitly reconcile:

- What JIRA says vs what the code change implies
- Gaps where inference was required
- Confidence level (high / medium / low) based on available evidence

### Step 6: Generate Report

Create the output directory:

```bash
mkdir -p .work/jira/generate-test-plan/{ISSUE_KEY}
```

#### Test Plan Mode

**Filename:** `.work/jira/generate-test-plan/{ISSUE_KEY}/test-plan.md`

**Sections:**

1. **JIRA Summary** — key, title, type, description, acceptance criteria
2. **PR Summary** — linked PRs and how they relate to the JIRA
3. **Prerequisites** — infrastructure, tools, access (no build/deploy steps)
4. **Test Scenarios** — numbered cases covering these categories where applicable:
   - Happy path scenarios (based on acceptance criteria)
   - Negative test cases (invalid inputs, boundary conditions)
   - Edge cases specific to the implementation
   - Integration scenarios (how changes interact with existing system; for multi-PR issues, verify PRs work correctly together)
   - Error handling verification
   - Performance considerations if applicable
   - Platform-specific test variations (AWS, Azure, KubeVirt, etc.) if the PR contains platform-specific changes
   - Each case includes: steps, expected results, verification commands
5. **Regression Testing** — related features and affected areas
6. **Success Criteria** — checklist mapped to acceptance criteria
7. **Troubleshooting** — common issues and debug steps
8. **Notes** — limitations, links, critical cases, skipped PRs

Do **not** include build/deploy or cleanup sections.

#### Reproducer Mode

**Filename:** `.work/jira/generate-test-plan/{ISSUE_KEY}/reproducer-report.md`

**Sections:**

1. **Bug Summary** — JIRA key, title, components, concise problem statement
2. **Root Cause Analysis** — inferred from PR diff and JIRA narrative
3. **Prerequisites / Environment** — cluster version, platform, config, tools required
4. **Steps to Reproduce (Pre-Fix)** — numbered steps that trigger the bug on an unfixed build
5. **Observed vs Expected Behavior** — broken state the reproducer should demonstrate
6. **Fix Verification Steps (Post-Fix)** — same reproducer with fix applied; expected corrected behavior
7. **Automation Opportunities** — whether this could become an e2e or integration test (no code generation)
8. **Confidence & Assumptions** — high/medium/low with explicit assumptions made during inference
9. **Open Questions** — items for PR author or bug reporter to confirm
10. **PR Summary** — fix PRs analyzed and skipped PRs with reasoning

### Step 7: Present Results

Display to the user:

- Report file path
- Mode used (`test-plan` or `reproducer`)
- JIRA issue and PRs analyzed
- Number of test scenarios or reproducer steps generated
- Confidence level (reproducer mode)
- Skipped PRs and why
- Ask if the user wants modifications

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | Report error; verify issue key and JIRA access |
| No PRs found | Continue with JIRA-only analysis; lower confidence in reproducer mode |
| `gh` not authenticated | Provide `gh auth login` instructions |
| Non-bug issue in reproducer mode | Warn; proceed with best-effort reproduction steps |
| PR diff too large | Focus on files most relevant to the JIRA component/summary |

## Examples

**Test plan with auto-discovered PRs:**

```
/jira:generate-test-plan CNTRLPLANE-205
```

**Test plan with specific PRs:**

```
/jira:generate-test-plan OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
```

**Test plan command with reproducer mode:**

```
/jira:generate-test-plan OCPBUGS-12345 --reproducer
```

**Reproducer alias:**

```
/jira:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
```
