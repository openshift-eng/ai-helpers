---
name: chai-presubmit-override-decisions
description: Use when monitoring CHAI presubmit agent decisions in BigQuery to analyze the breakdown of override, retest, and report-only actions on PR presubmit failures and estimate CI cost savings
---

# CHAI Presubmit Override Decisions

Query `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log` to monitor decisions made by the CHAI agent when evaluating PR presubmit failures. The primary goal is understanding the decision breakdown: how many failures are being overridden vs retested vs just reported on, and estimating CI cost savings from overrides.

Follow the `foundations` skill for cost safety, caching, and execution workflow.

## When to Use This Skill

- Monitoring the decision breakdown (override / retest / report_only / no_action_required)
- Estimating CI cost savings from overridden presubmit failures
- Reviewing decisions for a specific PR, repo, or job
- Understanding why the agent made a particular decision (rationale)
- Tracking decision trends over time
- Auditing whether overrides correlate with post-merge regressions

## Default Timespan

Use **one week** unless the user specifies otherwise.

## CI Cost Savings

Each overridden presubmit failure saves an estimated **$3 per job run** in CI costs (cloud compute for the retest that was avoided). When reporting override counts, always calculate and display the estimated savings:

```
estimated_savings = override_count * $3.00
```

## Table

### `ci_analysis_us.chai_presubmit_decision_log`

**Project**: `openshift-gce-devel`

Each row represents one decision the CHAI agent made about a PR presubmit failure.

| Column | Type | Notes |
|--------|------|-------|
| logged_at | TIMESTAMP | When the record was appended (UTC) |
| persona | STRING | The persona that appended the record |
| session_id | STRING | The conversation session ID |
| repo | STRING | The PR's repository |
| pr_number | INTEGER | The PR number |
| head_sha | STRING | The live PR HEAD SHA the decision was made against |
| run_sha | STRING | The SHA the failed run tested, when known |
| revision_match | BOOLEAN | Whether the failed run tested the live PR HEAD SHA |
| status_context | STRING | Full GitHub status context (e.g. `ci/prow/e2e-gcp-ovn-upgrade`) |
| prow_job_name | STRING | Full Prow job name |
| prow_build_id | STRING | Prow build ID of the failed run |
| prow_job_url | STRING | Prow job URL of the failed run |
| run_finished_at | TIMESTAMP | When the failed run finished |
| decision | STRING | The action taken: `override`, `retest`, `report_only`, `no_action_required` |
| job_classification | STRING | Whether the job is an override-eligible long-running e2e or integration job |
| tests_executed | BOOLEAN | Whether the failed run executed tests |
| failing_tests | STRING (REPEATED) | The failing test names |
| job_pass_rate | FLOAT | Fleet-wide pass rate for this job (0-100) |
| linked_bugs | STRING (REPEATED) | Jira bugs linked to failing tests (e.g. `OCPBUGS-12345`) |
| pr_overlap | STRING | The PR's overlap with the failing test or tested surface |
| rationale | STRING | Why this decision was made, in a short paragraph |

### Decision Types

| Decision | Meaning |
|----------|---------|
| `override` | Agent overrode the failure — the PR can merge without retesting. Saves CI cost. |
| `retest` | Agent triggered a retest of the job. |
| `report_only` | Agent reported on the failure but took no action (e.g. waiting for human review). |
| `no_action_required` | Agent determined no action was needed (e.g. failure already resolved). |

A healthy system should show a mix of all decision types. The breakdown reveals whether the agent is being too aggressive (too many overrides) or too conservative (mostly report_only).

## Query Patterns

### Decision breakdown per repo with CI savings (default query)

This is the primary query to run when the user asks about CHAI decisions without a specific question. **Always break down per repo** — the agent is being rolled out to repos incrementally, so per-repo consistency is a key signal.

```sql
SELECT
  repo,
  COUNT(*) AS total_decisions,
  COUNTIF(decision = 'override') AS overrides,
  COUNTIF(decision = 'retest') AS retests,
  COUNTIF(decision = 'report_only') AS report_only,
  COUNTIF(decision = 'no_action_required') AS no_action,
  ROUND(COUNTIF(decision = 'override') * 100.0 / COUNT(*), 1) AS override_pct,
  ROUND(COUNTIF(decision = 'retest') * 100.0 / COUNT(*), 1) AS retest_pct,
  ROUND(COUNTIF(decision = 'report_only') * 100.0 / COUNT(*), 1) AS report_only_pct,
  COUNTIF(decision = 'override') * 3 AS estimated_savings_usd
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY repo
ORDER BY total_decisions DESC
```

After running this, always report:
- **Active repos** — the count of distinct repos with decisions in the time window. Presubmit override decisions are only enabled on select repositories, and repos with no PR activity in the window won't appear, so this reflects active repos, not all enabled repos.
- **Per-repo breakdown** — decision counts and percentages for each repo, calling out whether the mix looks consistent across repos or if some repos skew heavily toward one decision type
- **Total override count and estimated CI savings** — sum of overrides across all repos * $3
- **Overall totals** — aggregate decision counts and percentages

### Overall decision summary

Use alongside the per-repo query for a quick aggregate view:

```sql
SELECT
  COUNT(DISTINCT repo) AS enabled_repos,
  COUNT(*) AS total_decisions,
  COUNTIF(decision = 'override') AS overrides,
  COUNTIF(decision = 'retest') AS retests,
  COUNTIF(decision = 'report_only') AS report_only,
  COUNTIF(decision = 'no_action_required') AS no_action,
  COUNTIF(decision = 'override') * 3 AS estimated_savings_usd
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
```

### Decision breakdown by job

```sql
SELECT
  prow_job_name,
  decision,
  COUNT(*) AS count,
  ROUND(AVG(job_pass_rate), 1) AS avg_pass_rate
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY prow_job_name, decision
ORDER BY count DESC
```

### Daily trend (per repo)

```sql
SELECT
  DATE(logged_at) AS day,
  repo,
  COUNTIF(decision = 'override') AS overrides,
  COUNTIF(decision = 'retest') AS retests,
  COUNTIF(decision = 'report_only') AS report_only,
  COUNTIF(decision = 'no_action_required') AS no_action,
  COUNT(*) AS total,
  COUNTIF(decision = 'override') * 3 AS daily_savings_usd
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY day, repo
ORDER BY day, repo
```

### Override details with rationale

```sql
SELECT
  logged_at,
  repo,
  pr_number,
  prow_job_name,
  job_pass_rate,
  rationale
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND decision = 'override'
ORDER BY logged_at DESC
```

### Decisions for a specific PR

```sql
SELECT
  logged_at,
  prow_job_name,
  decision,
  job_pass_rate,
  revision_match,
  rationale
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND repo = @repo
  AND pr_number = @pr_number
ORDER BY logged_at DESC
```

### Overrides on stale SHAs (revision mismatch)

```sql
SELECT
  logged_at,
  repo,
  pr_number,
  prow_job_name,
  revision_match,
  head_sha,
  run_sha,
  rationale
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND decision = 'override'
  AND revision_match = false
ORDER BY logged_at DESC
```

### Failing tests driving the most decisions

```sql
SELECT
  test,
  COUNT(*) AS decision_count,
  COUNTIF(decision = 'override') AS override_count,
  COUNTIF(decision = 'report_only') AS report_only_count
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`,
  UNNEST(failing_tests) AS test
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY test
ORDER BY decision_count DESC
LIMIT 20
```

### Linked bugs driving overrides

```sql
SELECT
  bug,
  COUNT(*) AS decision_count,
  COUNTIF(decision = 'override') AS override_count
FROM `openshift-gce-devel.ci_analysis_us.chai_presubmit_decision_log`,
  UNNEST(linked_bugs) AS bug
WHERE logged_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY bug
ORDER BY override_count DESC
```

## Reporting

When presenting results, always include:

1. **Active repos** — distinct repos with decisions in the time window, listed by name. Presubmit override decisions are only enabled on select repositories; repos with no PR activity in the window won't appear.
2. **Per-repo decision breakdown** — count and percentage for each decision type per repo. Call out repos that look different from others (e.g. one repo with all report_only while others have a mix of overrides)
3. **CI savings estimate** — total overrides * $3 with a note that this estimates avoided retest costs. Break down per repo if there are enough overrides.
4. **Consistency check** — are the decision ratios similar across repos? Significant divergence could indicate different job profiles or misconfiguration.
5. **Top jobs** — which prow jobs are driving the most decisions
6. **Notable patterns** — e.g. jobs with low pass rates getting overrides, revision mismatches, tests driving most decisions
7. **Linked bugs** — which Jira issues are associated with overridden failures
