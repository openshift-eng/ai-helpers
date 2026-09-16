# Output and verified label

### Output

After completing all phases, produce a **user-friendly summary** followed by the structured JSON report.

#### User-Friendly Summary

Before the JSON, output a concise human-readable summary table to the console. This is the primary output the user reads — the JSON is for programmatic consumption.

Format:

```
═══ Check PR Tests: {downstream_pr_url} ═══

Verified label eligibility: {YES|NO}
  {If NO: Reason: {verified_reason}}

Bugs: {jira_key_1}, {jira_key_2}
Mode: {dry_run|execute}

┌─────────────────┬────────────┬──────────────────────────────┬──────────┐
│ Bug             │ Change Type│ Test Coverage                │ Verdict  │
├─────────────────┼────────────┼──────────────────────────────┼──────────┤
│ OCPBUGS-98616   │ bug_fix    │ ✓ Unit (PR)  ⚠ Perf (manual)│ PASS     │
│ OCPBUGS-98491   │ deletion   │ ✓ Existing tests             │ PASS     │
└─────────────────┴────────────┴──────────────────────────────┴──────────┘

CI: 26/28 passed │ 1 failed (ci/prow/security — unrelated) │ 1 pending (tide)

⚠ Gaps:
  • OCPBUGS-98616: Performance testing was manual only (Sachin Ninganure) — no automated regression test

[dry_run] Comment would be posted to PR (shown below)
```

Use these symbols consistently:
- `✓` — automated coverage exists (PR diff or CI)
- `⚠` — manual-only coverage or gap worth noting
- `✗` — required but not covered at all

**Multi-bug PRs**: When a PR fixes multiple Jira issues, each bug gets its own row in the summary table. The overall verdict is the **most restrictive** across all bugs — if any bug is not eligible, the PR is not eligible.

#### Structured JSON Report

**Important**: The `comment_body` field is **always included** in the output — in both `--dry-run` and `--execute` modes — so the user can review exactly what was (or would be) posted to the PR.

```json
{
  "schema_version": "1.3",
  "metadata": {
    "generated_at": "<ISO-8601 timestamp>",
    "input_pr": "<input pr_url>",
    "jira_key": "<extracted jira key>",
    "expected_pr_count": "<count or auto-detected count>",
    "mode": "<execute|dry_run>"
  },
  "prs": {
    "upstream": {
      "url": "<upstream PR URL or null>",
      "state": "<OPEN|MERGED|CLOSED>",
      "code_changes": ["<list of changed source files>"],
      "test_coverage": {
        "new_tests": {
          "files_modified": ["<test files added/modified in this PR>"],
          "functions_added": ["<test function names added in diff>"]
        },
        "existing_tests": {
          "same_package_tests": ["<pre-existing test files in same package>"],
          "functions_covered": ["<function names referenced in existing tests>"],
          "e2e_tests": ["<e2e test names covering this component>"]
        }
      },
      "has_new_tests": true,
      "has_existing_coverage": true
    },
    "downstream": {
      "url": "<downstream PR URL>",
      "state": "<OPEN|MERGED|CLOSED>",
      "code_changes": ["<list of changed source files>"],
      "test_coverage": {
        "new_tests": {
          "files_modified": ["<test files added/modified in this PR>"],
          "functions_added": ["<test function names added in diff>"]
        },
        "existing_tests": {
          "same_package_tests": ["<pre-existing test files in same package>"],
          "functions_covered": ["<function names referenced in existing tests>"],
          "e2e_tests": ["<e2e test names covering this component>"]
        }
      },
      "has_new_tests": false,
      "has_existing_coverage": true,
      "upstream_tests_carried": false
    }
  },
  "change_classification": {
    "type": "<dependency_bump|bug_fix|new_feature|api_change|config_infra|refactor>",
    "test_required": true,
    "reasoning": "<explanation of why test is/isn't required>"
  },
  "jira_test_context": {
    "<jira_key>": {
      "required_test_types": ["unit", "e2e_performance"],
      "testing_performed": [
        {
          "type": "<manual_e2e_performance|manual_e2e|automated_unit|automated_e2e|conformance_run|...>",
          "performed_by": "<person or bot name>",
          "details": "<summary of what was tested and results>",
          "automated": false
        }
      ],
      "testing_gaps": ["<description of missing test coverage>"],
      "has_manual_verification": true,
      "reasoning": "<why these test types are required for this issue>",
      "automation_suggestions": [
        {
          "test_idea": "string",
          "source": "jira_manual_testing|jira_description|code_diff",
          "test_type": "unit|e2e|e2e_performance|functional|conformance",
          "suggested_location": "string (file path or test suite name)",
          "what_to_assert": "string"
        }
      ]
    }
  },
  "ci_status": {
    "downstream_pr": "<downstream PR URL>",
    "checks_summary": {
      "total": 15,
      "passed": 12,
      "failed": 2,
      "pending": 1
    },
    "failed_checks": [
      {
        "name": "<check name>",
        "status": "<FAILURE|ERROR>",
        "url": "<details URL>"
      }
    ],
    "test_specific_results": [
      {
        "test_name": "<test name>",
        "test_file": "<source file containing the test>",
        "category": "<new|existing>",
        "job": "<job name>",
        "status": "<PASSED|FAILED>",
        "error_snippet": "<truncated error message, or null if passed>",
        "url": "<prow job URL>"
      }
    ]
  },
  "action_taken": {
    "type": "<[dry_run:]verified_with_tests|[dry_run:]ci_failure|[dry_run:]comment_requesting_tests|[dry_run:]verified_existing_coverage|[dry_run:]verified_test_not_required>",
    "label_added": null,
    "comment_url": "<URL of the posted comment, or null in dry-run mode>",
    "comment_body": "<the full composed comment text — always included in both modes>"
  },
  "verdict": {
    "tests_included": false,
    "existing_coverage": true,
    "ci_passing": false,
    "verified_eligible": false,
    "verified_reason": "<reason for eligibility or ineligibility>",
    "summary": "<human-readable summary of the verdict>",
    "test_type_coverage": {
      "unit": { "required": true, "covered": true, "source": "pr_diff" },
      "e2e": { "required": true, "covered": false, "source": null, "manual_only": true },
      "conformance": { "required": false, "covered": false, "source": null },
      "functional": { "required": false, "covered": false, "source": null },
      "performance": { "required": true, "covered": false, "source": null, "manual_only": true }
    }
  }
}
```

**Schema changes in 1.3** (vs 1.2):
- `jira_test_context` added (object, keyed by Jira key) — testing requirements and QA context extracted from Jira issues (Phase 3.5)
- `jira_test_context.<key>.required_test_types` — array of test types required based on Jira analysis
- `jira_test_context.<key>.testing_performed` — array of testing activities found in Jira comments
- `jira_test_context.<key>.testing_gaps` — array of identified gaps in test coverage
- `jira_test_context.<key>.has_manual_verification` — boolean indicating manual QA was performed
- `jira_test_context.<key>.automation_suggestions` added — array of test automation ideas derived from Jira context and code diff
- `verdict.test_type_coverage` added (object) — per-test-type breakdown of coverage status with `required`, `covered`, `source`, and optional `manual_only` fields

**Schema changes in 1.2** (vs 1.1):
- `verdict.verified_eligible` added (boolean) — whether the PR qualifies for the `/verified` label
- `verdict.verified_reason` added (string) — human-readable explanation of eligibility determination

**Schema changes in 1.1** (vs 1.0):
- `prs.*.test_files_modified` and `prs.*.test_functions_added` replaced by `prs.*.test_coverage` object with `new_tests` and `existing_tests` sub-objects
- `prs.*.has_tests` split into `has_new_tests` and `has_existing_coverage` booleans
- `prs.downstream.existing_test_coverage` moved into `prs.downstream.test_coverage.existing_tests`
- `ci_status.test_specific_results[].category` added (`"new"` or `"existing"`)
- `ci_status.test_specific_results[].test_file` added
- `ci_status.test_specific_results[].error_snippet` added (null if passed)

### Verified Label Eligibility

The `verdict.verified_eligible` field is a boolean that indicates whether the PR qualifies for the `/verified` label. It is determined by evaluating the following decision matrix:

#### Eligible (`verified_eligible: true`)

| Scenario | Conditions |
| --- | --- |
| **New tests pass** | `has_new_tests == true` AND `ci_passing == true` |
| **Existing coverage passes** | `has_existing_coverage == true` AND `ci_passing == true` AND (`test_required == false` OR existing tests cover the changed functions) |
| **Test not required** | `change_classification.test_required == false` AND `ci_passing == true` (e.g., dependency bump, config-only, refactor) |

#### Not eligible (`verified_eligible: false`)

| Scenario | `verified_reason` |
| --- | --- |
| CI has failing checks | `"CI checks failing: {failed_check_names}"` |
| CI checks still pending (non-tide) | `"CI checks still pending: {pending_check_names}"` |
| Test required but none found | `"Test coverage required for {change_type} but no new or existing tests found"` |
| No CI checks found | `"No Prow CI checks found on PR"` |
| Required test type has manual-only coverage | `"Required test type {test_type} has manual-only verification — automated regression test needed for {jira_key}"` |

#### Edge cases

- **`tide` pending**: The `tide` check is merge automation, not a test. It should be **excluded** from the pending check evaluation. A PR with only `tide` pending and all other checks passing is still eligible.
- **Test infrastructure updated (no new `func Test*`)**: If the PR modifies test helper files (e.g., regex patterns in `events.go`) but does not add new `func Test*` functions, this counts as existing coverage being updated — eligible if CI passes.
- **Pure code deletion**: If the fix only removes code (no new logic), test requirement is relaxed — eligible if CI passes and no regressions detected.
- **Jira indicates required test type with manual-only verification**: If Jira context indicates a test type is required AND only manual (non-automated) verification exists (e.g., QA Contact performed manual E2E/performance testing), set `verified_eligible: false`. Record `manual_only: true` in `test_type_coverage`. Manual QA confirms the fix works but does not constitute automated regression coverage — the `/verified` label requires all required test types to have automated coverage. The report must include a **"Suggested Test Automation"** section that summarizes what was tested manually and provides concrete suggestions for automating each gap (e.g., specific test frameworks, test file locations, what the automated test should assert).
- **Jira indicates required test type with no coverage at all**: If Jira context indicates a test type is required AND no coverage exists (no automated tests, no manual verification), flag it in the report and in `testing_gaps`, but defer to the existing eligibility rules (CI passing + tests present). The Jira context is advisory, not blocking.

Output this JSON to the console. Only save to `.work/check-pr-tests/{jira_key}/output.json` if the user explicitly requests to save results.

