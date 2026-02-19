---
description: Fetch a test report from Sippy showing pass rates, test ID, and Jira component
argument-hint: <test-name> [release]
---

## Name

ci:fetch-test-report

## Synopsis

```
/ci:fetch-test-report <test-name> [release]
```

## Description

The `ci:fetch-test-report` command fetches a report for an OpenShift CI test by name from the Sippy API. It returns the test's BigQuery/Component Readiness test ID, Jira component, pass rates for the current and previous 7-day periods, and open bug counts. The `open_bugs` field counts Jira bugs that mention this test by name — this can help surface bugs that have been filed but not yet triaged in Component Readiness.

## Implementation

1. **Determine the release**: If the user did not specify a release, use the `fetch-releases` skill to get the latest OCP release:
   ```bash
   release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
   ```
   If the user specified a release (e.g., "4.21"), use that value directly.

2. **Fetch the test report**: Use the `fetch-test-report` skill to query the Sippy tests API:
   ```bash
   python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py "<test-name>" --release "$release" --format summary
   ```

   To see a per-variant breakdown (one row per variant combo), add `--no-collapse`:
   ```bash
   python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py "<test-name>" --release "$release" --no-collapse --format summary
   ```

3. **Present the results**: Show the user the test report including test ID, pass rates, Jira component, open bugs, and trend. If `open_bugs > 0`, note that existing Jira bugs mention this test — these may be relevant even if the regression hasn't been triaged in Component Readiness yet.

## Return Value

- **Format**: Human-readable summary of the test report
- **Key fields**: test_id (BigQuery/Component Readiness ID), jira_component, current/previous pass rates, run counts, trend, open_bugs
- **open_bugs**: Count of Jira bugs mentioning this test by name — helps find bugs filed but not yet triaged in Component Readiness
- **variants** (with `--no-collapse`): Per-variant breakdown showing which job types the test passes/fails in

## Examples

1. **Look up a test using the latest release**:
   ```
   /ci:fetch-test-report [sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]
   ```

2. **Look up a test for a specific release**:
   ```
   /ci:fetch-test-report [sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance] 4.21
   ```

## Arguments

- $1: Full test name (required) — must be an exact match including sig prefix and suite tags
- $2: OCP release version (optional) — e.g., "4.22", "4.21". If omitted, the latest release is used.

## Skills Used

- `fetch-releases`: Determines the latest OCP release when not specified by the user
- `fetch-test-report`: Queries the Sippy tests API for the test report
