---
description: Verify test coverage and CI results for a GitHub PR linked to a Jira issue
argument-hint: <pr-url> [count] [--execute | --dry-run]
---

## Name

check-pr-tests:check-pr-tests

## Synopsis

```
/check-pr-tests:check-pr-tests <pr-url> [count] [--execute | --dry-run]
```

## Description

The `check-pr-tests:check-pr-tests` command performs deep test coverage verification and CI validation for a GitHub PR linked to a Jira issue. It:

1. Extracts the Jira key from the PR title
2. Discovers all upstream/downstream PRs via `/jira:extract-prs`
3. Deeply inspects commits for test coverage (new test files, test function names)
4. Determines if tests are required based on change classification
5. Finds exact CI test names (unit tests, e2e/Ginkgo tests via Sippy)
6. Checks Prow CI results for pass/fail status
7. Posts actionable feedback as a comment on the downstream PR (**only with `--execute`**)

## Execution Modes

- **`--dry-run`** (default): Runs the full analysis and outputs the structured JSON report, but does **not** post any comment to the PR or add labels. Use this to preview what the skill would do.
- **`--execute`**: Runs the full analysis **and** posts the appropriate comment to the downstream PR on GitHub. Required to take any action on the PR.

If neither flag is provided, `--dry-run` is assumed.

## Implementation

1. **Parse input arguments**:
   - `$1` (required): GitHub PR URL (e.g., `https://github.com/openshift/cluster-network-operator/pull/3031`)
   - `$2` (optional): Expected PR count. `1` = downstream only, `2` = upstream + downstream. If omitted, auto-detects by classifying PRs from extract-prs as upstream/downstream.
   - `--execute`: Post comment to the downstream PR after analysis.
   - `--dry-run`: Run analysis only; do not post comment (this is the default).

2. **Execute the `check-pr-tests` skill**: Follow all 7 phases as defined in the skill's SKILL.md:
   - Phase 1: Jira Key Extraction & PR Discovery
   - Phase 2: Upstream/Downstream Classification
   - Phase 3: Deep Commit Inspection
   - Phase 4: Determine If Test Is Required (when no tests found)
   - Phase 5: Find Exact Test Names for CI Lookup
   - Phase 6: Prow CI Result Lookup
   - Phase 7: PR Feedback — only posts the comment when `--execute` is specified

3. **Present the structured JSON output** to the user, including the verdict, action taken (or action that *would* be taken in dry-run mode), and the full `comment_body` for review.

## Return Value

- **Format**: Structured JSON report (schema version 1.1)
- **Key fields**: `metadata` (jira key, PR URL, mode), `prs` (upstream/downstream details with `test_coverage.new_tests` and `test_coverage.existing_tests`), `change_classification`, `ci_status`, `action_taken`, `verdict`
- **`comment_body`**: Always included in the output under `action_taken.comment_body` — in both `--dry-run` and `--execute` modes — so the user can review the exact comment text
- **Comment structure**: The comment body uses per-bug sections (`### {jira_key}`) and distinguishes between **New Tests** (added in the PR) and **Existing Tests** (already in the repo)
- **Side effect** (`--execute` only): A comment is posted to the downstream PR on GitHub
- **Dry-run**: `action_taken.type` is prefixed with `dry_run:` to indicate no action was taken (e.g., `dry_run:verified_with_tests`)

## Examples

### Example 1: Dry-run analysis (default)

```
/check-pr-tests:check-pr-tests https://github.com/openshift/cluster-network-operator/pull/3031
```

Runs the full analysis and outputs the JSON report. No comment is posted to the PR.

### Example 2: Execute and post comment

```
/check-pr-tests:check-pr-tests https://github.com/openshift/cluster-network-operator/pull/3031 --execute
```

Runs the full analysis and posts the appropriate comment to the downstream PR.

### Example 3: Explicit dry-run with count

```
/check-pr-tests:check-pr-tests https://github.com/openshift/cluster-network-operator/pull/3031 2 --dry-run
```

Expects upstream + downstream PRs. Runs analysis only.

### Example 4: Execute with explicit count=1

```
/check-pr-tests:check-pr-tests https://github.com/openshift/cluster-network-operator/pull/3031 1 --execute
```

Only analyzes the downstream PR and posts the comment.

## Arguments

- **$1** *(required)*: GitHub PR URL — must be a full URL like `https://github.com/org/repo/pull/123`
- **$2** *(optional)*: Expected PR count (`1` or `2`). If omitted, auto-detects from `/jira:extract-prs` results.
- **--execute** *(optional)*: Post the verification comment to the downstream PR.
- **--dry-run** *(optional)*: Run analysis only; do not post comment. This is the default.

## Skills Used

- `check-pr-tests`: Core skill implementing all 7 phases of test coverage verification
- `jira:extract-prs`: Discovers all PRs linked to the Jira issue (invoked in Phase 1)
- `ci:fetch-test-report`: Queries Sippy for e2e test names by component (used in Phase 5)
- `ci:fetch-test-runs`: Fetches individual test run results via Sippy (used in Phase 6)
- `ci:fetch-releases`: Determines the latest OCP release for Sippy queries (used in Phase 5)
