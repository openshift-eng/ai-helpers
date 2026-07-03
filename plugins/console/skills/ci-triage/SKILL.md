---
name: ci-triage
description: >
  Triage CI failures on an OpenShift Console PR by fetching Prow job logs,
  extracting error details, and classifying each failure as PR-related or
  unrelated. Produces an actionable summary table.
  Use this skill whenever the user wants to understand why CI is failing on a PR,
  asks to "check CI", "triage CI", "why is CI red", "prow failures",
  "ci failures", "check prow", or wants to analyze CI job results for a pull request.
  Also trigger when the user mentions a failing Prow job name
  (e.g. "frontend job failed", "analyze job is red", "e2e-gcp-console failing").
compatibility: Designed for OpenShift Console PRs. Requires gh CLI (authenticated) and internet access.
argument-hint: "[PR-number]"
allowed-tools: Bash(gh *), Bash(git *), Bash(grep *), WebFetch, Read, AskUserQuestion
---

# CI Triage for OpenShift Console PRs

Analyze CI failures on an OpenShift Console PR. Fetch Prow job logs, extract
specific error messages, cross-reference them against the PR's changed files,
and classify each failure as PR-related or unrelated.

The output is an actionable triage table the user can act on — not a wall of
raw logs. After the report, the user decides what to fix; this skill does not
attempt fixes itself.

## Step 1 — Determine the PR

The input is an optional PR number passed as an argument (e.g. `/ci-triage 16269`).

**If a PR number is provided**, use it directly.

**If no PR number is provided**, detect it from context:
1. Check if the current directory is a worktree whose name matches `pr-*` (e.g. `pr-16269`).
2. Check the current git branch name — it may encode the PR or Jira key.
3. Use `gh pr view --json number` to see if the current branch has an open PR.

If detection fails, ask the user for the PR number.

## Step 2 — Gather PR context

Run these in parallel:

```bash
# PR metadata + changed files
gh pr view <PR> --json title,headRefName,files,additions,deletions,commits

# CI check status
gh pr checks <PR>
```

From `gh pr view`, extract:
- The list of changed file paths (this is the reference for "is this failure related?")
- The commit SHA (to match against Prow job results)

From `gh pr checks`, extract:
- Each job name, pass/fail status, and the Prow URL

## Step 3 — Find the CI failure table

The `openshift-ci[bot]` posts a comment with a markdown table listing all
failed jobs. This table has columns: Test name, Commit, Details, Required,
Rerun command. It is marked with `<!-- test report -->` at the end.

Fetch it:

```bash
gh api repos/{owner}/{repo}/issues/<PR>/comments \
  --jq '.[] | select(.user.login == "openshift-ci[bot]") | select(.body | contains("<!-- test report -->")) | .body'
```

Take the **last** such comment (most recent test run). Parse the markdown table
to get each failing job's:
- **Job name** (e.g. `ci/prow/frontend`)
- **Required or not**
- **Prow URL** (contains the build ID needed for artifact fetching)

If the bot comment isn't found, fall back to the `gh pr checks` output from
Step 2 — filter to `fail` status rows and use the URLs there.

## Step 4 — Fetch Prow job logs

For each failing job, fetch the error details. The goal is to get the specific
failure message, not the entire build log.

### URL patterns

Given a Prow URL like:
```
https://prow.ci.openshift.org/view/gs/test-platform-results/pr-logs/pull/openshift_console/<PR>/<JOB_NAME>/<BUILD_ID>
```

The GCS artifacts are at:
```
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/openshift_console/<PR>/<JOB_NAME>/<BUILD_ID>/
```

### Fetching strategy (in priority order)

1. **`artifacts/junit_operator.xml`** — Always try this first. It contains
   structured test case results with failure messages. WebFetch it and ask for
   "all test case results, failures, and error details". This is the single
   most valuable artifact.

2. **E2e test build logs** — For e2e jobs (`e2e-gcp-console`, `e2e-playwright`,
   etc.), the junit may only say "container test failed". Dig deeper:
   - Navigate to `artifacts/<JOB_NAME>/test/build-log.txt`
   - This contains the actual Cypress/Playwright output with specific spec
     file names and assertion errors.

3. **Top-level `build-log.txt`** — Fall back to this only if junit doesn't
   have enough detail. It can be large and truncated by WebFetch, so prefer
   the structured sources above.

### What to extract

For each failing job, capture:
- The **specific error message** (assertion text, compilation error, etc.)
- The **failing test/spec name** if applicable
- The **file paths** mentioned in the error
- Whether the failure is in the "test" phase vs infrastructure/setup

### Parallel fetching

Fetch logs for all failing jobs in parallel using separate WebFetch calls
(or subagents if many jobs failed). Don't go one-by-one — the user is waiting.

## Step 5 — Classify each failure

For each failure, determine if it's **PR-related** or **unrelated** by
cross-referencing the error against the PR's changes.

### PR-related signals

A failure is **PR-related** if any of these are true:
- The error message mentions a file that the PR modified
- The error references a string, function, import, or symbol introduced by the PR
- The error is a missing i18n key for a string the PR added (common pattern:
  `yarn i18n` wasn't run)
- The error is a bundle size limit exceeded and the PR added new imports
- A test that exercises code changed by the PR now fails
- The error is in a test file the PR added or modified

### Unrelated signals

A failure is **unrelated** if:
- The error is in code/tests the PR didn't touch and doesn't reference
  PR-introduced symbols
- The test is flagged as "flaky" (retried and eventually passed, or is a known
  flaky test like Alertmanager/Insights popup tests)
- The failure is an infrastructure issue (cluster provisioning timeout, image
  pull error, quota exceeded)
- The failure is in a setup/teardown phase unrelated to the PR's code

### When in doubt

If you can't confidently classify a failure, mark it as **"Possibly related"**
with your reasoning. Don't guess — surface the ambiguity for the user.

## Step 6 — Output the triage report

Present the results as a markdown table:

```
| # | CI Job | Required? | Error Type | Error Summary | PR-Related? | Reasoning |
|---|--------|-----------|------------|---------------|-------------|-----------|
```

After the table, add:

1. **Fix priority** — Which failures to address first (required jobs before
   optional, quick wins before complex fixes)
2. **Common root causes** — If multiple jobs fail for the same reason (e.g.
   missing i18n keys causing frontend + Cypress + Playwright failures), group
   them and state which single fix resolves multiple jobs
3. **Unrelated failures** — Briefly note what the unrelated failures are so the
   user knows they can `/retest` those

Keep the report concise. The user wants to know what to fix, not to read
a log analysis essay.

## Common failure patterns in OpenShift Console CI

These are the most frequent PR-caused CI failures. Knowing them helps
classification:

| Pattern | Affected Jobs | Root Cause |
|---------|--------------|------------|
| Missing i18n keys | frontend, e2e-gcp-console, e2e-playwright | New translatable strings added but `yarn i18n` not run. Cypress/Playwright `afterEach` hooks validate no untranslated keys appear in DOM. |
| Bundle size exceeded | analyze | New imports pulled dependencies into the main vendor bundle. Fix with lazy loading (`AsyncComponent`) or check for accidental barrel imports. |
| TypeScript/lint errors | frontend | Type errors or lint violations in changed files. |
| Test assertion failure | frontend, e2e-* | Unit or e2e test fails on code the PR changed. |
| Snapshot mismatch | frontend | Component rendering changed, snapshots need updating. |
| Import from barrel/index | analyze, frontend | Importing from package index (e.g. `@console/shared`) instead of specific file path. |

## Notes

- The GCS web interface returns HTML directory listings. When fetching a
  directory URL, ask WebFetch to "list all files and subdirectories".
- junit_operator.xml is small (typically 1-15 KB) and always parseable.
  build-log.txt can be 30-100 KB and may get truncated.
- Some Prow URLs contain the repo as `openshift_console` (underscore) in the
  path. Preserve that when constructing URLs.
- The `gh pr checks` output gives the full Prow URL; you can extract the
  BUILD_ID from it (the numeric suffix).
