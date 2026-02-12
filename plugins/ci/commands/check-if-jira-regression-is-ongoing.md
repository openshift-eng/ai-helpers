---
description: Check if the regression described in a Jira bug is still ongoing or has resolved
argument-hint: <jira-key-or-url>
---

## Name

ci:check-if-jira-regression-is-ongoing

## Synopsis

```
/ci:check-if-jira-regression-is-ongoing <jira-key-or-url>
```

## Description

The `ci:check-if-jira-regression-is-ongoing` command reads a Jira bug and determines whether the regression(s) it describes are still actively failing or have resolved. It extracts test names, test IDs, and regression IDs from the bug description, status, and comments, then cross-references with live data from Sippy and Component Readiness.

This command is useful for:

- Checking if a bug's regression has resolved and the bug can be closed
- Finding out if new regressions have appeared for the same test since the bug was filed
- Discovering if other triaged bugs exist for the same test that don't match this bug
- Getting a quick status on whether a fix has landed and is effective

## Implementation

1. **Parse Arguments**: Extract the Jira key

   Accept either a full URL or a bare key:
   - `https://issues.redhat.com/browse/OCPBUGS-74690` → `OCPBUGS-74690`
   - `OCPBUGS-74690` → `OCPBUGS-74690`

   Strip the URL prefix if present:
   ```bash
   jira_key=$(echo "$input" | sed 's|.*/browse/||')
   ```

2. **Fetch Jira Issue**: Read the bug description, status, and comments

   Use the `fetch-jira-issue` skill to retrieve the bug data:

   ```bash
   jira_script="plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py"
   jira_data=$(python3 "$jira_script" "$jira_key" --format json)
   ```

   See `plugins/ci/skills/fetch-jira-issue/SKILL.md` for complete implementation details including error handling.

   Extract and read from the JSON output:
   - `summary`: Bug title
   - `comments[].body`: All comment bodies
   - `status`: Current Jira status (e.g., New, Assigned, Modified, Closed)
   - `components[]`: Jira component(s)
   - `progress.level`: Automatic progress classification (ACTIVE/STALLED/NEEDS_ATTENTION/RESOLVED)

3. **Extract Test Identifiers**: Scan the bug for test names, test IDs, and regression IDs

   Search through the summary, description, and all comment bodies for:

   - **Test IDs** (`test_id`): Match the pattern `suite-name:hex-hash` (e.g., `openshift-tests:bb3a7d828630760296ef203c5cacf708`). These are BigQuery/Component Readiness test IDs.
   - **Regression IDs**: Match standalone integers that appear in context suggesting they are regression IDs (e.g., "regression 34446", "Regression ID: 34446", or in Sippy URLs containing `/regressions/`). Also extract from Component Readiness URLs like `sippy.dptools.openshift.org/...`.
   - **Test names**: Match strings in the format `[sig-*] ...` which are full OpenShift CI test names (e.g., `[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]`).

   **If no test ID, test name, or regression ID can be found, abort**:
   ```
   Error: Could not identify any test name, test ID, or regression ID in OCPBUGS-74690.
   Cannot check regression status without at least one of these identifiers.
   ```

   If multiple identifiers are found, use all of them — the bug may cover multiple tests/regressions.

4. **Determine Release**: Get the release version

   Check if the bug description or title mentions a release version (e.g., "4.22", "4.21"). If not, use the `fetch-releases` skill:

   ```bash
   release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
   ```

5. **Check Regression IDs** (if found): Query each regression's current status

   For each regression ID extracted from the bug:

   ```bash
   script_path="plugins/ci/skills/fetch-regression-details/fetch_regression_details.py"
   regression_data=$(python3 "$script_path" <regression_id> --format json)
   ```

   For each regression, determine:
   - **Status**: Is it open or closed?
   - **If open**: How long has it been open? (`opened` timestamp to now)
   - **If closed**: When did it close? (`closed` timestamp). How long was it open?
   - **Triages**: What bugs are triaged against it? Do any of the triage `jira_key` values match our bug? If a triage points to a *different* bug, flag this for the user.
   - **Pass sequences**: Check `sample_failed_jobs` pass sequences. Are recent runs (left side) passing or failing?

6. **Check Test Names and Test IDs Against Open Regressions**: Find if the test appears in any current regressions

   Use the `list-regressions` skill with `--test-name` to fetch regressions matching this test:

   ```bash
   script_path="plugins/teams/skills/list-regressions/list_regressions.py"
   matching_regressions=$(python3 "$script_path" --release "$release" --test-name "$test_name")
   ```

   This returns only regressions for the exact test name across all components and variants, without needing to fetch and parse the full regression list.

   For each matching regression:
   - Note whether it is **open** or **closed**
   - Note when it was opened and (if closed) when it was closed
   - Check if it is **triaged** and to which Jira bug
   - **If triaged to a different bug than the one we're investigating, flag this**:
     ```
     ⚠ Regression <id> is triaged to OCPBUGS-XXXXX (not this bug OCPBUGS-74690).
       This may indicate a duplicate or a related but separate issue.
     ```
   - Note the variants affected

   If the bug contained a `test_id` but no `test_name`, use any regression match to obtain the test name for subsequent steps.

7. **Check Global Test Report**: Use `fetch-test-report` with `--no-collapse`

   ```bash
   script_path="plugins/ci/skills/fetch-test-report/fetch_test_report.py"
   test_report=$(python3 "$script_path" "$test_name" --release "$release" --no-collapse --format json)
   ```

   Analyze:
   - **Overall pass rate**: Is the test healthy (>99%) or still failing?
   - **Per-variant breakdown**: Which specific variant combinations are still failing? Which have recovered?
   - **Trend** (`net_working_improvement`): Is the test improving (positive) or getting worse (negative)?
   - **Open bugs count**: Are there other open bugs mentioning this test?
   - **Comparison to bug context**: If the bug mentioned specific variants (e.g., "metal-ipi", "aws"), check those variants specifically.

8. **Check Recent Test Runs**: Use `fetch-test-runs` to see current failure activity

   ```bash
   script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
   recent_runs=$(python3 "$script_path" "$test_id" --include-success --format json)
   ```

   Analyze:
   - **Recent pass/fail ratio**: Count successes vs failures in recent runs
   - **Mass failure detection**: Check `failed_tests` field — if `failed_tests > 10`, the test may be caught up in broader infrastructure failures rather than a test-specific regression
   - **Error consistency**: Are the failure outputs consistent with what the bug describes?
   - **Last failure date**: When was the most recent failure? If all recent runs are passing, the regression may have resolved.

9. **Synthesize and Present Report**: Summarize the findings

   Present a clear report answering the core question: **Is the regression described in this bug still ongoing?**

   **Report Format**:

   ```
   Regression Status Check: OCPBUGS-74690
   ============================================================

   Bug: <summary>
   Status: <jira status>
   Component: <component>

   Identifiers Found:
   - Test Name: <test name>
   - Test ID: <test_id>
   - Regression IDs: <list>

   --- Regression Status ---

   [For each regression ID checked:]
   Regression <id>: OPEN / CLOSED
     Opened: <date> (<N days ago>)
     Closed: <date> (<N days ago>) [if closed]
     Triaged to: <jira key> [matches this bug / DIFFERENT BUG ⚠]
     Recent Pattern: <pass_sequence summary>

   --- Current Regressions for This Test ---

   [For each matching regression in current release:]
   Regression <id>: OPEN / CLOSED
     Variants: <variant list>
     Triaged: Yes → OCPBUGS-XXXXX / No
     [If triaged to different bug: ⚠ Triaged to OCPBUGS-XXXXX, not this bug]

   --- Global Test Health ---

   Overall Pass Rate: <X>% (trend: improving/regressing)
   Open Bugs: <N>

   Per-Variant Breakdown:
     <variant combo>: <pass rate>% [FAILING / HEALTHY]
     <variant combo>: <pass rate>% [FAILING / HEALTHY]
     ...

   --- Recent Test Runs ---

   Total runs: <N> (Passes: <N>, Failures: <N>)
   Mass failure runs: <N> of <N> failures had >10 other test failures
   Last failure: <date>
   Last success: <date>

   --- Conclusion ---

   <One of the following assessments:>

   ✅ RESOLVED: The regression appears to have resolved. The test has been
      passing consistently since <date>. The global pass rate is <X>%.
      [Recommend closing the bug if no further action needed.]

   ⚠ PARTIALLY RESOLVED: The test is passing in most variants but still
      failing in <variant list>. Pass rate is <X>% overall.
      [Recommend keeping the bug open until all variants recover.]

   ❌ STILL ONGOING: The regression is still actively failing. The test
      has a <X>% pass rate with <N> failures in the last 7 days.
      [The bug should remain open.]

   🔄 INCONCLUSIVE: Could not definitively determine regression status.
      <reason — e.g., mass failures obscuring results, test not running recently>
   ```

   **If the bug is Closed or Verified but the regression is STILL ONGOING or PARTIALLY RESOLVED**:

   This indicates the fix was insufficient or the problem has recurred. Offer to reopen the bug:

   ```
   ⚠ FAILED FIX: This bug is <Closed/Verified> but the regression is still ongoing.
   The test has a <X>% pass rate with <N> recent failures.

   Would you like me to:
   1. Add a comment explaining the regression is still active
   2. Reopen the bug by moving status back to ASSIGNED
   ```

   If the user confirms, perform both actions:

   **Add a comment** explaining the situation, including:
   - Current pass rate and failure count
   - Which variants are still failing
   - Link to the Sippy test details report
   - A note that the regression was detected as still ongoing by the check command

   ```bash
   # Add comment to the bug
   curl -s -X POST \
     -H "Authorization: Bearer $JIRA_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"body": "<comment text>"}' \
     "https://issues.redhat.com/rest/api/2/issue/<jira_key>/comment"
   ```

   **Transition the bug back to ASSIGNED**:

   First, fetch available transitions to find the correct transition ID:
   ```bash
   transitions=$(curl -s -H "Authorization: Bearer $JIRA_TOKEN" \
     "https://issues.redhat.com/rest/api/2/issue/<jira_key>/transitions")
   ```

   Look through the transitions for one that moves to "Assigned" status, then execute it:
   ```bash
   curl -s -X POST \
     -H "Authorization: Bearer $JIRA_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"transition": {"id": "<transition_id>"}}' \
     "https://issues.redhat.com/rest/api/2/issue/<jira_key>/transitions"
   ```

   Display confirmation:
   ```
   Bug reopened:
   - JIRA: https://issues.redhat.com/browse/<jira_key>
   - Status: ASSIGNED
   - Comment added explaining regression is still active
   ```

## Return Value

- **Format**: Human-readable summary report
- **Key information**:
  - Whether the regression is still ongoing, resolved, or partially resolved
  - When the regression appears to have resolved (if applicable)
  - Current pass rates per variant
  - Whether other regressions or bugs exist for the same test
  - Flags for regressions triaged to different bugs

## Examples

1. **Check a bug by URL**:
   ```
   /ci:check-if-jira-regression-is-ongoing https://issues.redhat.com/browse/OCPBUGS-74690
   ```

2. **Check a bug by key**:
   ```
   /ci:check-if-jira-regression-is-ongoing OCPBUGS-74690
   ```

## Arguments

- `$1` (required): Jira issue key or URL
  - Format: Either a bare key (`OCPBUGS-74690`) or a full URL (`https://issues.redhat.com/browse/OCPBUGS-74690`)

## Prerequisites

1. **JIRA_TOKEN**: Required to read the Jira issue

   - Set environment variable: `export JIRA_TOKEN="your-jira-api-token"`
   - Obtain from: https://issues.redhat.com (Profile → Personal Access Tokens)

2. **Sippy Port-Forward**: Required for `fetch-test-report` and `fetch-test-runs` skills

   - Typically via: `kubectl port-forward -n sippy svc/sippy 8080:8080`

3. **Python 3**: Required for all skill scripts

   - Version: 3.6 or later

## Skills Used

- `fetch-regression-details`: Checks regression status (open/closed), triages, and pass sequences
- `fetch-test-report`: Gets global test health with per-variant breakdown
- `fetch-test-runs`: Gets recent test run results to check current failure activity
- `fetch-releases`: Determines the latest OCP release when not specified in the bug
- `list-regressions` (teams plugin): Lists all regressions for a release to find matches by test name/ID

## See Also

- Related Command: `/ci:analyze-regression` — Full regression analysis workflow
- Related Command: `/ci:fetch-test-report` — Fetch test health report by name
- Related Skill: `fetch-regression-details` (`plugins/ci/skills/fetch-regression-details/SKILL.md`)
- Related Skill: `fetch-test-report` (`plugins/ci/skills/fetch-test-report/SKILL.md`)
- Related Skill: `fetch-test-runs` (`plugins/ci/skills/fetch-test-runs/SKILL.md`)
- Related Skill: `fetch-releases` (`plugins/ci/skills/fetch-releases/SKILL.md`)
- Related Skill: `list-regressions` (`plugins/teams/skills/list-regressions/SKILL.md`)
