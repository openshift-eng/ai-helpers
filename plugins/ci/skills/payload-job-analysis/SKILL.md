---
name: Payload Job Analysis
description: Analyze a failed blocking job for payload triage — investigate the failure, score candidate PRs, and check for existing reverts/fixes. Designed to run as a subagent launched by analyze-payload.
---

# Payload Job Analysis

This skill is the subagent entry point for analyzing a single failed blocking job during payload triage. It combines failure investigation, candidate PR scoring, and revert/fix PR discovery into a single parallelizable unit of work.

## When to Use This Skill

This skill is used exclusively by the `analyze-payload` skill (Step 5). The parent orchestrator launches one subagent per failed blocking job, passing all necessary context. Each subagent runs this skill independently and in parallel.

**Do not use this skill directly.** It expects structured input from the parent orchestrator.

## Input Context

The parent orchestrator provides the following context when launching the subagent:

| Field | Description |
|-------|-------------|
| `job_name` | Full periodic job name |
| `prow_url` | Prow URL for the final attempt |
| `previous_attempt_urls` | List of previous attempt URLs (retries) |
| `retry_count` | Number of retries |
| `payload_tag` | The payload being analyzed |
| `release_controller_url` | URL to the payload on the release controller |
| `streak_length` | Consecutive payloads this job has been failing |
| `originating_payload_tag` | The payload where this job first started failing |
| `is_new_failure` | Whether this failure is new to the target payload |
| `candidate_prs` | JSON array of candidate PRs from the originating payload (from `fetch-new-prs-in-payload`) |

## Implementation Steps

### Phase 1: Investigate the Failure

Determine whether the failure is an install failure or a test failure, then use the appropriate analysis skill.

**Aggregated jobs**: If this is an aggregated job (has `aggregated-` prefix or an `aggregator` step), retries only re-run the aggregation analysis — they do NOT re-run the underlying test jobs. Therefore, only examine the most recent attempt; previous attempts contain the same underlying results and do not provide additional signal.

**Non-aggregated jobs**: **Examine the final attempt first**, then compare with previous attempts to determine whether all retries failed the same way. If retries show different failure modes, note this — it distinguishes consistent regressions from intermittent/infrastructure issues. Consistent failures across all attempts strongly indicate a product regression rather than flakiness.

First, check the JUnit results or build log to determine whether this is an install failure (look for `install should succeed: overall` or similar install-related test failures) or a test failure (install passed, specific tests failed).

Based on the failure type, use the appropriate skill:
- **Install failure**: Use the `ci:prow-job-analyze-install-failure` skill. For metal/bare-metal jobs (job name contains "metal"), perform additional analysis using the `ci:prow-job-analyze-metal-install-failure` skill as needed for dev-scripts, Metal3/Ironic, and BareMetalHost-specific diagnostics.
- **Test failure**: Use the `ci:prow-job-analyze-test-failure` skill. Do NOT use `--fast` — always perform the full analysis including must-gather extraction and analysis.

**IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.

If the job is an aggregated job (has `aggregated-` prefix in the name or an `aggregator` container/step), also extract the **underlying job name** from the junit-aggregated.xml artifacts — each `<testcase>` has `<system-out>` YAML data with a `humanurl` field linking to individual runs whose URL path contains the underlying job name. The underlying job name cannot be derived from the aggregated job name — it must be extracted from the artifacts.

### Phase 2: Score Candidate PRs

Using the failure analysis from Phase 1 and the `candidate_prs` provided by the parent, score each candidate PR against this job's failure using the following weighted rubric:

| Signal | Weight | Criteria |
|--------|--------|----------|
| New failure mode | +30 | The specific failure mode (error messages, symptoms) was not present in previous payloads — the job may have been failing before, but not in this way |
| Component exclusivity | +10 to +30 | The failure involves a component modified by this PR, and fewer other PRs in the originating payload touch the same component. Score: sole modifier = +30, 2-3 PRs touch component = +20, 4+ PRs = +10 |
| Error message match | +40 | Error messages or stack traces directly reference code, packages, or functionality changed by this PR |
| Presubmit coverage gap | +10 | The failing job tests a scenario (upgrade, FIPS, SNO, techpreview, etc.) that wasn't covered by the PR's presubmit tests |
| Single candidate | +10 | Only one PR landed in the originating payload that touches the affected component |

The maximum possible score is 120, but scores above 100 should be capped at 100. Record the numeric score for each candidate PR alongside the qualitative rationale.

If the root cause was traced to a PR **outside** the candidate list (e.g., an `openshift/release` PR that modified a CI step registry script), include it as an additional candidate with its own score.

**Do NOT score highly**:
- Infrastructure failures (cloud quota, API rate limits, network issues)
- Flaky tests that also fail intermittently on accepted payloads
- PRs where the correlation is circumstantial (e.g., same component but unrelated code path)

Only include candidates with a score >= 30 in the output. Lower-scoring candidates add noise without value.

### Phase 3: Check for Existing Reverts and Fixes

For each candidate PR with a score >= 30 (all scored candidates), check for existing revert and fix PRs. Extract the `org/repo` and PR number from the candidate's URL.

#### 3a: Check for Existing Reverts

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state,mergedAt --limit 5
```

Record the result:
- **Merged revert found**: Record `revert_status: "merged"`, the revert PR URL, and when it merged relative to the payload timestamp.
- **Open revert found**: Record `revert_status: "open"` and the revert PR URL.
- **Closed (not merged)**: Ignore — the revert was abandoned.
- **No revert found**: Record `revert_status: "none"`.

#### 3b: Check for Existing Fix PRs

Search using multiple strategies:

1. **Search by PR number reference**:
```bash
gh pr list --repo <org>/<repo> --search "<pr_number> in:title,body" --state open --json number,title,url,state --limit 10
```

2. **Search by changed files**:
```bash
# Get files changed by the candidate PR
gh api "repos/<org>/<repo>/pulls/<pr_number>/files" --jq '.[].filename' | head -20

# List recent open PRs
gh pr list --repo <org>/<repo> --state open --json number,title,url,state,createdAt --limit 20
```
For each open PR, check if it modifies any of the same files:
```bash
gh api "repos/<org>/<repo>/pulls/<open_pr_number>/files" --jq '.[].filename'
```

3. **Search by author**:
```bash
# Get the candidate PR author
gh api "repos/<org>/<repo>/pulls/<pr_number>" --jq '.user.login'

gh pr list --repo <org>/<repo> --state open --author <candidate_pr_author> --json number,title,url,state --limit 5
```

Filter results across all strategies:
- Exclude the original candidate PR itself and any revert PRs (found in 3a)
- Is NOT a revert (title does not start with "Revert")
- Is currently `open` or `draft`
- Was opened after the candidate PR merged

If a fix PR is found, check whether it has payload job coverage:

a. **Payload commands** (pr-payload-tests):
```bash
gh api "repos/<org>/<repo>/issues/<fix_pr_number>/comments?per_page=100&sort=created&direction=desc" \
  --jq '[.[] | select(.user.login == "openshift-ci[bot]" and (.body | contains("pr-payload-tests")))] | .[0] | .body'
```

b. **GitHub check runs** (presubmit CI):
```bash
gh pr checks <fix_pr_number> --repo <org>/<repo> --json name,state --jq '.[] | select(.name | test("<job_name_pattern>"))'
```

Record the fix PR URL, state, and coverage status.

## Output Format

Return an `ANALYSIS_RESULT` block at the end of the response in this exact format:

```
ANALYSIS_RESULT:
failure_analysis:
  failure_type: install|test
  root_cause_summary: <one-line summary>
  affected_components: <comma-separated list>
  key_error_patterns: <comma-separated key error strings>
  known_symptoms: <comma-separated symptom summaries, or "none">
  underlying_job_name: <for aggregated jobs only, or "">
  retries_consistent: yes|no|no_retries|only_final_examined
  retry_summary: <brief comparison of failure modes across attempts>

scored_candidates:
  - pr_url: <GitHub PR URL>
    pr_number: <number>
    component: <component name>
    title: <PR title>
    confidence_score: <0-100>
    rationale: <explanation of score>
    revert_status: none|open|merged
    revert_pr_url: <URL or "">
    revert_pr_merged_at: <ISO timestamp or "">
    fix_pr_url: <URL or "">
    fix_pr_state: <open|draft or "">
    fix_pr_has_coverage: true|false|""
    fix_pr_coverage_detail: <description of coverage or "">
```

If no candidates score >= 30, return `scored_candidates: []`.

## Notes

- Phase 3 (revert/fix checks) is performed for all scored candidates (>= 30). Existing reverts and fixes are valuable context regardless of confidence tier.
- The subagent should complete all three phases before returning. Do not return partial results.
- Keep output concise for inclusion in the parent's summary report. Include key error messages and log excerpts but avoid dumping entire log files.

## See Also

- Related Skill: `analyze-payload` — parent orchestrator that launches this skill as subagents
- Related Skill: `prow-job-analyze-install-failure` — used in Phase 1 for install failures
- Related Skill: `prow-job-analyze-test-failure` — used in Phase 1 for test failures
- Related Skill: `prow-job-analyze-metal-install-failure` — used in Phase 1 for metal install failures
