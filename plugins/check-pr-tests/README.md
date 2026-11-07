# check-pr-tests Plugin

Deep test coverage verification and CI validation for GitHub PRs linked to Jira issues. Determines whether a PR qualifies for the `/verified` label.

## Commands

### `/check-pr-tests:check-pr-tests`

Performs end-to-end test coverage verification for a GitHub PR. Extracts the Jira key, discovers upstream/downstream PRs, inspects commits for test coverage, checks Prow CI results, and optionally posts actionable feedback.

**Usage:**
```bash
/check-pr-tests:check-pr-tests <pr-url> [count] [--execute | --dry-run]
```

**Arguments:**
- `<pr-url>` *(required)*: GitHub PR URL (e.g., `https://github.com/openshift/ovn-kubernetes/pull/3361`)
- `count` *(optional)*: Expected PR count. `1` = downstream only, `2` = upstream + downstream. Auto-detected if omitted.
- `--execute`: Post the verification comment to the downstream PR.
- `--dry-run` *(default)*: Run analysis only; do not post any comment.

## Skills

### `check-pr-tests`

Core skill implementing a 7-phase analysis pipeline:

1. **Jira Key Extraction & PR Discovery** — extracts the Jira key from the PR title and discovers linked PRs via `/jira:extract-prs`
2. **Upstream/Downstream Classification** — classifies PRs as upstream (non-openshift/) or downstream (openshift/)
3. **Deep Commit Inspection** — identifies code changes, test files, and test function names from the diff
4. **Jira Issue Test Context** — analyzes Jira description, comments, labels, and metadata for testing requirements and generates test automation suggestions
5. **Test Requirement Determination** — classifies the change type and cross-references with Jira context to determine if tests are needed
6. **CI Test Name Discovery** — maps test functions to CI-executable names via Sippy
7. **Prow CI Result Lookup** — validates test results from Prow job artifacts
8. **PR Feedback** — composes and optionally posts a structured comment with test coverage report, Jira test context, and suggested test automation

## Dependencies

- `gh` CLI installed and authenticated
- MCP Jira server configured and running
- `jq` installed
- `python3` available
- Network access to Sippy API at `https://sippy.dptools.openshift.org`

## Related Skills

- `jira:extract-prs` — discovers all PRs linked to a Jira issue
- `ci:fetch-test-report` — queries Sippy for test pass rates
- `ci:fetch-test-runs` — fetches individual test run results
- `ci:fetch-releases` — determines latest OCP release for Sippy queries
