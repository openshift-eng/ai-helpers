---
name: assess-pr-test-results
description: Fetch test results for a PR and classify failures as PR-related, pre-existing/flaky, or infrastructure by cross-referencing against mainline CI health
---

# Assess PR Test Results

This skill fetches test results for a pull request, then cross-references each failing test against mainline CI pass rates to determine whether failures are likely caused by the PR, pre-existing on mainline, or infrastructure problems. It produces a structured report classifying each failure.

## When to Use This Skill

Use this skill when you need to:

- Understand whether PR test failures are caused by the PR or are pre-existing
- Triage PR failures to separate signal from noise
- Get a quick health assessment of a PR's CI results
- Identify which failures a PR author should investigate vs. ignore

## Prerequisites

1. **Network Access**: Must be able to reach the Sippy API
   - No authentication required

2. **Python 3**: Python 3.6 or later
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Fetch PR Test Results

Create a working directory and fetch the PR's test results:

```bash
mkdir -p .work/assess-pr-test-results

script_path="plugins/ci/skills/assess-pr-test-results/fetch_pr_test_results.py"

python3 "$script_path" "<pr_url_or_number>" \
  --output .work/assess-pr-test-results/raw-results.json \
  --format json
```

If the user provides a PR URL, pass it directly. If they provide org/repo and PR number separately, use `--org` and `--repo` flags.

Read the JSON output and check `success` is `true`. Record `total_results` and the list of unique SHAs.

### Step 2: Identify Unique Failing Tests and Classify Infrastructure

From the results, extract distinct `test_name` values from failures. Group by `test_name` and count how many job runs each test failed in.

**Immediately classify these as Infrastructure** — do not look them up on mainline:

- Any test containing `[sig-sippy]` (e.g., `[sig-sippy] infrastructure should work`, `[sig-sippy] openshift-tests should work`, `[sig-sippy] install should work`)
- Any test containing `install should succeed`

These are synthetic health indicators or install-level failures, not test regressions. Count them for the report but exclude them from the top 20 list.

Sort the remaining tests by failure count (descending) and take the **top 20**. Note the total number of unique non-infrastructure failing tests so you can report how many were analyzed vs. total.

### Step 3: Cross-Reference Against Mainline CI

For each of the top 20 non-infrastructure failing tests, query its mainline pass rate:

```bash
report_script="plugins/ci/skills/fetch-test-report/fetch_test_report.py"

# For each unique failing test name:
python3 "$report_script" "<test_name>" --format json
```

The script auto-detects the latest release. Parse the JSON array output to extract from the first element:

- `current_pass_percentage` — pass rate over the last 7 days on mainline
- `current_runs` — how many times it ran (low run count = less confident)
- `current_failures` — absolute failure count on mainline
- `open_bugs` — number of open Jira bugs mentioning this test

If the result is an empty array `[]`, the test was not found in mainline. It may be a new test introduced by the PR, or a test that only runs in presubmit context.

### Step 4: Classify Each Failure

Using the mainline pass rate, classify each test:

| Mainline Pass Rate | Classification | Meaning |
|---|---|---|
| Not found in mainline | **New / Presubmit-only** | Test may be new or only runs in presubmit context. Treat as suspicious — the PR author should investigate. |
| ≥ 95% | **Suspicious (PR-related)** | Test is healthy on mainline but failing on this PR. Likely caused by the PR. |
| 80–95% | **Possibly PR-related** | Test has some mainline instability but is mostly passing. Could be the PR or could be a flake. |
| < 80% | **Pre-existing / Known Flaky** | Test is already struggling on mainline. Failure is likely not caused by this PR. |

Additional signals that increase suspicion:
- Test failed in **multiple job runs** on this PR (consistent failure across jobs = less likely a flake)
- Test has **zero mainline failures** in the current period (very healthy baseline)
- Test has `open_bugs > 0` (someone already knows about this — decreases PR suspicion)

### Step 5: Produce Report

Output a structured markdown report:

```
## PR Test Results Assessment: <org>/<repo>#<number>

**Total test failures:** <N>
**Unique failing tests:** <N> (analyzed top <M>)
**Job runs with failures:** <N>
**SHAs tested:** <list>

### Summary

| Classification | Count |
|---|---|
| Suspicious (likely PR-related) | X |
| Possibly PR-related | X |
| Pre-existing / Known Flaky | X |
| New / Presubmit-only | X |
| Infrastructure | X |

### Suspicious Failures (Likely PR-Related)

These tests are healthy on mainline but failing on this PR. The PR author should investigate.

| Test Name | PR Failures | Mainline Pass Rate | Mainline Runs | Jobs |
|---|---|---|---|---|
| `<test_name>` | X / Y runs | 99.5% | 3400 | <job_names> |
| ... | ... | ... | ... | ... |

<For each suspicious test, briefly note what the test exercises based on its name/suite and which jobs it failed in.>

### Possibly PR-Related

These tests have some mainline instability but are mostly passing. Worth a look if the suspicious list is empty.

| Test Name | PR Failures | Mainline Pass Rate | Open Bugs |
|---|---|---|---|
| ... | ... | ... | ... |

### Pre-Existing / Known Flaky

These tests are already failing on mainline. Likely not caused by this PR.

| Test Name | PR Failures | Mainline Pass Rate | Open Bugs |
|---|---|---|---|
| ... | ... | ... | ... |

### New / Presubmit-Only Tests

These tests were not found in mainline CI data. They may be new tests introduced by this PR or tests that only run in presubmit context.

| Test Name | PR Failures | Jobs |
|---|---|---|
| ... | ... | ... |

### Infrastructure Failures

<N> infrastructure test failures across <M> job runs. These indicate jobs that failed to set up properly (install failures, test framework issues), not specific test regressions.
```

Omit any classification section that has zero entries.

### Step 6: Return the Report

The report is your output to the caller. Present it directly. Do not write it to a file unless the caller asks.

## Constraints

- **Limit mainline lookups to top 20 failing tests** (by failure count, excluding infrastructure). Note the total count so the caller knows if more were skipped.
- **Do not speculate on root causes.** Report what the data shows — which tests failed, how they compare to mainline. The caller or a downstream skill will do deeper analysis.
- **Infrastructure tests are noise.** Classify them but do not investigate them. They indicate job-level problems, not test-level regressions.
- **A test not found in mainline is not automatically safe.** It could be a new test introduced by the PR that is broken. Flag it for investigation.
- **Don't block on missing data.** If the mainline lookup fails for a test, note it and move on. Continue with the remaining tests.

## Skills Available

| Skill | When to Use |
|---|---|
| `ci:fetch-test-report` | Query mainline pass rates for individual tests (Step 3) |

## See Also

- Related Skill: `assess-pr-risk` (assesses overall PR risk level and recommends testing)
- Related Skill: `fetch-test-report` (fetches test metadata from Sippy)
