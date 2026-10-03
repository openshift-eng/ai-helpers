---
name: check-pr-tests
description: Use when verifying test coverage and Prow CI for a GitHub PR linked to a Jira issue (optional PR comment with --execute)
allowed-tools: Bash(gh *) Bash(jq *) Bash(curl *) Bash(python3 *) Bash(sed *) Bash(grep *) Bash(cat *) mcp__plugin_jira_atlassian__getAccessibleAtlassianResources mcp__plugin_jira_atlassian__getJiraIssue mcp__plugin_jira_atlassian__searchJiraIssuesUsingJql mcp__plugin_jira_atlassian__getJiraIssueRemoteIssueLinks
---

# Check PR Tests

This skill performs end-to-end test coverage verification and CI validation for a GitHub PR linked to a Jira issue. It extracts the Jira key, discovers upstream/downstream PRs, deeply inspects commits for test coverage, determines if tests are required, finds exact CI test names, checks Prow results, and optionally posts actionable feedback to the PR.

**IMPORTANT FOR AI**: This is a **procedural skill** — when invoked, directly execute the implementation steps in the [Implementation](#implementation) references below. Do NOT look for or execute external scripts.

**No intermediate script files**: Do NOT write temporary `.py`, `.sh`, or other script files to disk and then execute them — this causes multiple user confirmation prompts (one for the Write tool, one for the Bash tool). Instead, run all commands as **inline bash one-liners** or **pipe chains** via a single Bash tool call. Existing scripts from dependent plugins (e.g., `fetch_releases.py`, `fetch_test_runs.py`) can be called directly as bash commands — they do not need to be rewritten or wrapped.

## When to Use This Skill

Use this skill when you need to:
- Verify that a PR fixing a Jira bug includes appropriate test coverage
- Check if existing tests adequately cover a code change (when no new tests were added)
- Validate that CI jobs exercising relevant tests pass
- Post automated verification comments to PRs (only with `--execute` mode)

## Prerequisites

- `gh` CLI installed and authenticated with access to the target repo
- MCP Jira server configured and running (required for `/jira:extract-prs`)
- Network access to Sippy API at `https://sippy.dptools.openshift.org`
- `jq` installed for JSON parsing
- `python3` available (for calling existing ci plugin scripts such as `fetch_releases.py`, `fetch_test_runs.py`)

## Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pr_url` | string | Yes | A GitHub PR URL (e.g., `https://github.com/openshift/cluster-network-operator/pull/3031`) |
| `count` | integer | No | PRs expected per Jira issue. Default: auto-detect. `1` = downstream only, `2` = upstream + downstream |
| `--execute` | flag | No | Post comment to the downstream PR after analysis. Without this flag, no PR comment is posted. |
| `--dry-run` | flag | No | Run analysis only; do not post any comment to the PR. This is the **default** behavior when neither flag is specified. |

## Execution Modes

The skill supports two mutually exclusive modes:

- **`--dry-run`** (default): Runs the full analysis (Phases 1-6) and produces the structured JSON report. Phase 7 is evaluated to determine *which* action would be taken and *what* comment would be posted, but no `gh pr comment` command is executed. The output JSON `action_taken.type` is prefixed with `dry_run:` (e.g., `dry_run:verified_with_tests`).

- **`--execute`**: Runs the full analysis (Phases 1-6) and then executes Phase 7 — posting the appropriate comment to the downstream PR via `gh pr comment`. The output JSON `action_taken.type` contains the actual action (e.g., `verified_with_tests`).

If neither flag is provided, `--dry-run` is assumed.

## Implementation

When invoked, execute every phase in order. Read and follow each bundled reference in sequence (do not skip files):

1. [references/phases-1-through-3.md](references/phases-1-through-3.md) — Phases 1, 2, 3, and 3.5 (Jira/PR discovery, classification, commit and Jira test context)
2. [references/phases-4-through-6.md](references/phases-4-through-6.md) — Phases 4, 5, and 6 (test requirement, Sippy test names, Prow CI)
3. [references/phase-7-pr-feedback.md](references/phase-7-pr-feedback.md) — Phase 7 (PR comment templates and `gh pr comment` when `--execute`)
4. [references/output-and-verdict.md](references/output-and-verdict.md) — User summary, JSON report schema, verified-label eligibility

## Error Handling

| Error | Handling |
|-------|----------|
| No Jira key in PR title | Exit with error; suggest user provide key manually |
| extract-prs returns no PRs | Warn; proceed with only the input PR |
| PR count mismatch (when provided) | Warn but continue with available PRs |
| Count omitted, no upstream found | Proceed as count=1 (downstream only analysis) |
| Diff too large (>20k lines) | Fall back to paginated file list; skip full diff analysis |
| GitHub API rate limit | Display reset time and exit with error |
| `gh search code` returns no results | Note "unable to determine existing coverage"; default to "test required" |
| Prow artifacts not accessible (GCS auth) | **Error out**. Report: "GCS authentication failed — cannot download JUnit XML from test-platform-results bucket." Guide: "Run `gcloud auth login` and ensure access to gs://test-platform-results." |
| Prow artifacts expired | **Error out**. Report: "Prow artifacts for job {job_name} have been garbage collected (typically retained 2-8 weeks)." Guide: "Re-trigger the Prow job with `/retest` on the PR to generate fresh artifacts." |
| Prow job still running | **Error out**. Report: "Prow job {job_name} is still in progress — artifacts not yet available." Guide: "Wait for the job to complete and re-run the skill." |
| PR is in a fork / no Prow CI configured | **Error out**. Report: "No Prow CI checks found on the downstream PR. Prow CI is required to verify the bug." Guide: "Ensure the PR is opened against a repo in the openshift/ org with Prow configured." |
| Cannot add label (permissions) | Log warning; include label suggestion in comment instead |
| Label adding disabled | Labels are commented out for initial testing; uncomment in Phase 7 when ready |

## Dependencies

| Dependency | Used In | Purpose |
|------------|---------|---------|
| `/jira:extract-prs` skill | Phase 1 | Find all PRs linked to Jira issue |
| `fetch-test-report` skill (ci plugin) | Phase 5b | Query Sippy for e2e test names by component |
| `fetch-test-runs` skill (ci plugin) | Phase 6c | Look up individual test run results via Sippy |
| `fetch-releases` skill (ci plugin) | Phase 5b | Determine latest OCP release for Sippy queries |
| `gh` CLI | Phases 1-7 | PR metadata, diffs, checks, comments, labels |
| `gh search code` | Phase 4b | Find existing test files referencing changed functions |
| Sippy API | Phases 5-6 | Test result lookups |
| MCP `getJiraIssue` | Phase 1 (via extract-prs), Phase 3.5 | Jira issue data for PR discovery and test context inspection. Data fetched in Phase 1 should be retained and passed to Phase 3.5 rather than re-fetched. |

## See Also

- Related Skill: `jira:extract-prs` (discovers all PRs linked to a Jira issue)
- Related Skill: `ci:fetch-test-report` (queries Sippy for test pass rates)
- Related Skill: `ci:fetch-test-runs` (fetches individual test run results)
- Related Command: `/check-pr-tests:check-pr-tests` (command that invokes this skill)
