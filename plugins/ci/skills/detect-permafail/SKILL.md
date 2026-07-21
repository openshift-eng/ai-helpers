---
name: detect-permafail
description: Analyze consecutive job failures to determine if they represent a permafail pattern versus flaky failures
---

# Detect Permafail

## When to Use This Skill

Use this skill when you have 2-10 consecutive failures of the same job and need to determine if the failures represent a systematic/permanent failure (permafail) versus a flaky failure. This is critical for CI/CD pipeline analysis to distinguish between:

- **Permafail**: A systematic failure affecting the same test(s) or infrastructure issue, detected by analyzing comparable runs (same failure type):
  - 2-3 comparable runs: All must have the same failure (100% match)
  - 4-5 comparable runs: At least 4 must have the same failure (80% match)
  - 6-10 comparable runs: At least ceil(count × 0.7) must have the same failure (70% match)
- **Flaky**: Non-deterministic failures with varying root causes, or failures that don't meet the permafail thresholds

## Prerequisites

- Access to OpenShift CI Prow job artifacts via gcsweb URLs
- Access to the `Bash` tool for running `plugins/ci/scripts/classify-job-failures.py`
- Python with the `requests` package available for artifact fetching
- Knowledge of Prow artifact structure (from `fetch-prowjob-json` and `prow-job-artifact-search` skills)
- 2-10 URLs pointing to consecutive job failures (from Prow/OpenShift CI, ordered newest to oldest)
- Job name context to verify consistency across all failures
- PR information to provide context for analysis

## Implementation Steps

### Step 1: Validate Inputs

**Standard Mode (URL-based):**

Verify that all required inputs are present with expected types and constraints:
- `failure_urls`: Array of 2-10 strings matching Prow job URL pattern `https://prow.ci.openshift.org/view/gs/<bucket>/<path>/<job-name>/<build-id>` where path may be `logs/`, `pr-logs/pull/`, or other GCS paths (must be consecutive runs, ordered newest to oldest)
- `job_name`: Non-empty string identifier of the job being analyzed
- `pr_info`: Object containing PR number (integer) and repository context (string)
- Each URL must match the Prow job URL pattern above

Reject requests if:
- URLs count is less than 2 or more than 10
- Job names don't match across all URLs (validate via prowjob.json metadata, not path position)
- PR context is missing

Notes:
- URL ordering (newest first) is assumed but not validated - the frontend provides them in this order
- Job name validation should check prowjob.json metadata or verify the name appears in the extracted GCS path, not assume a fixed path position (presubmit URLs include org/repo/pr segments)

**Offline/Eval Mode (Pre-normalized Signatures):**

For testing or offline analysis, the skill can accept pre-normalized failure signatures directly instead of fetching from URLs. This mode skips Steps 2-4 (artifact fetching and classification) and proceeds directly to Step 5 (threshold analysis).

Input format:
- `signatures`: Array of 2-10 pre-normalized signature objects (see Step 4 output format)
- Each signature must be either test_failure format `{type: "test_failure", url: "...", tests: [...], test_count: N}` or infra_failure format `{type: "infra_failure", url: "...", error: "...", error_hash: "..."}`

When signatures are provided, skip to Step 5 and apply threshold logic directly. Use this mode only for evals or when signatures have been extracted by another tool.

### Step 2: Classify Job Failures with Script

For standard URL-based analysis, call the deterministic classifier script to fetch artifacts and produce normalized signatures:

```bash
"$SKILL_DIR/../../scripts/classify-job-failures.py" --json-input '{
  "failure_urls": ["https://prow.ci.openshift.org/view/gs/..."],
  "job_name": "pull-ci-openshift-origin-master-e2e-aws",
  "pr_info": {"pr_number": 12345, "repository": "openshift/origin"}
}'
```

The script performs the artifact-based work that does not require AI judgment:

1. Parses the full GCS path from each Prow URL.
2. Fetches `prowjob.json` from gcsweb.
3. Browses the artifacts directory.
4. Classifies each run as `test_failure` or `infra_failure` based on artifacts, not error text alone.
5. Extracts failing test names from junit/build logs or normalized infrastructure errors.
6. Returns the Step 4 normalized signature array.

If the script exits non-zero, report its JSON error and do not continue to threshold analysis unless at least two valid signatures are available from another trusted source.

### Step 3: Artifact Classification Rules

The classifier follows these rules:

- **TEST_FAILURE** when artifacts contain `openshift-e2e-test/`, `e2e-*`, `junit/`, junit XML files, `openshift-tests-*`, or `monitor-test-*`.
- **INFRA_FAILURE** only when artifacts show setup/build/gather output without test artifacts, or artifacts are empty/unavailable after a valid job fetch.
- MonitorTest failures count as test failures because MonitorTests run during e2e execution.
- Classification must be artifact-based. Do not classify from Prow descriptions or error messages alone.

### Step 4: Use Normalized Failure Signatures

Use the script output directly as the normalized signature array.

**For test failures:**
```json
{
  "type": "test_failure",
  "url": "job_url",
  "tests": ["failing_test_name1", "failing_test_name2"],
  "test_count": 2
}
```

**For infrastructure failures:**
```json
{
  "type": "infra_failure",
  "url": "job_url",
  "error": "normalized_error_message",
  "error_hash": "md5_of_error_message"
}
```

### Step 5: Compare Signatures for Permafail Pattern

Apply permafail detection logic using **failure-type-based thresholds** - the denominator is the count of comparable runs (same failure type), not the matching group size:

**Detection Thresholds (based on comparable run count):**
- 2-3 comparable runs: All must match (100% match required)
- 4-5 comparable runs: At least 4 must match (80% match required)
- 6-10 comparable runs: At least ceil(count × 0.7) must match (70% threshold)

**For Test Failures:**
1. Count total test_failure signatures (this is the **denominator**)
2. Extract all unique test names from test_failure signatures
3. For each unique test name, count how many test_failure signatures contain it (this is the **numerator**)
4. Apply threshold based on the **denominator** (total test_failure count):
   - If denominator is 2-3: numerator must equal denominator (100%)
   - If denominator is 4-5: numerator must be ≥4 (80%)
   - If denominator is 6-10: numerator must be ≥ceil(denominator × 0.7) (70%)
5. If ANY test name meets its threshold: **PERMAFAIL = TRUE**
   - Report which test(s) met the threshold and their occurrence count
6. If no test meets the threshold: **PERMAFAIL = FALSE**

Example: 8 test_failure signatures, "TestNetworkPolicy" appears in 6 → 6/8 = 75% → needs ceil(8×0.7)=6 → 6≥6 ✓ PERMAFAIL

**For Infrastructure Failures:**
1. Count total infra_failure signatures (this is the **denominator**)
2. Extract error messages and group similar errors (exact match or >70% character similarity using normalized Levenshtein: `similarity = 1 - (levenshtein_distance(a, b) / max(len(a), len(b)))`. Treat two normalized errors as similar when `similarity > 0.70`. If both strings are empty, do not group them as similar; require a non-empty normalized error.)
3. For each error group, count how many infra_failure signatures contain it (this is the **numerator**)
4. Apply threshold based on the **denominator** (total infra_failure count):
   - If denominator is 2-3: numerator must equal denominator (100%)
   - If denominator is 4-5: numerator must be ≥4 (80%)
   - If denominator is 6-10: numerator must be ≥ceil(denominator × 0.7) (70%)
5. If ANY error group meets its threshold: **PERMAFAIL = TRUE**
   - Report the error message and occurrence count
6. If no error group meets the threshold: **PERMAFAIL = FALSE**

Example: 5 infra_failure signatures - 3 have "operator X timeout", 2 have random errors → 3/5 = 60% → needs 4/5 (80%) → 3<4 → NOT PERMAFAIL

**For Mixed Failure Types:**
1. Separate signatures by type (test_failure vs infra_failure)
2. For each type, count total signatures (the **denominator** for that type)
3. Apply threshold logic to each type independently:
   - **Test failures**: If ≥2 test_failure signatures exist, check if any test appears frequently enough to meet the threshold based on test_failure count
   - **Infra failures**: If ≥2 infra_failure signatures exist, check if any error appears frequently enough to meet the threshold based on infra_failure count
4. **Minimum runs requirement**: Need at least 2 runs of the same type to establish a permafail pattern. A single failure of either type is insufficient.
5. If either type meets the threshold AND has ≥2 runs: **PERMAFAIL = TRUE**
   - Report the dominant pattern (the one that triggered permafail)
   - Explain which runs contributed and which were ignored (e.g., "All 4 runs that reached e2e tests failed on TestNetworkPolicy. 3 other runs failed during cluster setup and are not relevant to this test failure pattern.")
6. If neither type meets criteria: **PERMAFAIL = FALSE**

**Example Scenario 1: PERMAFAIL (4 test, 3 infra):**
- 7 total runs provided
- 3 runs: infra_failure (cluster creation failed)
- 4 runs: test_failure (all failing on TestNetworkPolicy)

**Analysis:**
- Test failures: 4 runs → use 4/5 threshold (80%) → need 4 matching → have 4/4 (100%) ✓ PERMAFAIL
- Infra failures: 3 runs → use 3/3 threshold (100%) → different errors → NOT permafail
- Verdict: **PERMAFAIL = TRUE** (test failure group met criteria)
- Reason: "All 4 runs that reached e2e tests failed on TestNetworkPolicy (100% match). 3 additional runs failed during infrastructure setup and are not relevant to this test failure pattern."

**Example Scenario 2: NOT PERMAFAIL (1 test, 6 diverse infra):**
- 7 total runs provided
- 6 runs: infra_failure (each with different errors: cluster creation timeout, AWS quota, network issue, pod eviction, storage failure, DNS timeout)
- 1 run: test_failure (failed on TestNetworkPolicy)

**Analysis:**
- Test failures: 1 run → INSUFFICIENT (need minimum 2 runs to establish pattern)
- Infra failures: 6 runs with all different errors → no single error appears ≥5 times → NOT permafail
- Verdict: **PERMAFAIL = FALSE**
- Reason: "Only 1 out of 7 runs reached e2e tests and failed on '[sig-arch] daemonset cni-sysctl-allowlist-ds maxUnavailable requirement'. The other 6 runs failed during infrastructure setup, each with different unrelated issues (no consistent infra pattern). A single test failure is insufficient to establish a permafail pattern - we need multiple runs with consistent failures to confirm systematic breakage."

### Step 6: Generate Verdict and Return JSON

Construct the final response object with:
- Boolean verdict: `permafail` (true/false)
- Reason string explaining the determination. Always include explicit slash-format ratios for the dominant pattern and strongest non-matching pattern, such as `7/10`, `4/4`, `5/6`, or `2/10`. Do not write only `7 of 10`; include `7/10`.
- Complete failure signatures array
- Common tests array (if applicable and permafail=true)
- Confidence score as a JSON number from 0.0 to 1.0, representing confidence in the final verdict, not the raw match ratio. Never use strings such as `"high"`, `"medium"`, or `"0.95"`. For example, a clearly non-permafail `2/10` pattern can still have confidence around 0.70 because the verdict is well supported.
- Stable `failure_type` value:
  - `test_failure` when the final verdict is driven by test-failure analysis, or only test failures are present
  - `infra_failure` when the final verdict is driven by infrastructure-failure analysis, or only infrastructure failures are present
  - `mixed` when both test and infrastructure failures are present and no single type meets the permafail threshold
- `match_ratio`: Slash-format string for the dominant pattern, such as `"7/10"`, `"4/4"`, `"5/6"`, or `"2/10"`.
- `threshold_required`: Integer count required for the comparable-run group to qualify as permafail.
- `matching_runs`: Integer numerator for the dominant or strongest pattern.
- `comparable_runs`: Integer denominator for the comparable-run group.

The final JSON must be machine-checkable. The ratio-bearing fields must be top-level fields, not nested under an analysis object. Use this exact style:

```json
{
  "permafail": true,
  "confidence": 0.95,
  "reason": "7/10 test_failure runs failed TestNetworkPolicy, meeting the required 7/10 threshold.",
  "failure_type": "test_failure",
  "match_ratio": "7/10",
  "matching_runs": 7,
  "comparable_runs": 10,
  "threshold_required": 7,
  "signatures": []
}
```

For a mixed non-permafail, use `failure_type: "mixed"` and include the word `insufficient` in the reason when one failure type has fewer than 2 comparable runs.

Do not set `confidence` equal to the match percentage. Confidence means confidence in the verdict:

- Clear non-permafail with complete data and a strongest pattern below threshold, such as `2/10`, should use `confidence: 0.70` or higher.
- Exact threshold permafail, such as `7/10` test failures or `5/6` infra failures, should use `confidence: 0.85` or higher.
- All comparable runs matching, such as `4/4`, should use `confidence: 0.99`.
- Ambiguous or incomplete data should use lower confidence.

## Output Format

The skill returns a JSON object with this schema:

```json
{
  "permafail": true,
  "confidence": 0.95,
  "reason": "3/3 test_failure runs show the same failing test 'test_node_scale' - consistent permanent failure",
  "failure_type": "test_failure",
  "match_ratio": "3/3",
  "matching_runs": 3,
  "comparable_runs": 3,
  "threshold_required": 3,
  "signatures": [
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "tests": ["test_node_scale"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "tests": ["test_node_scale"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "tests": ["test_node_scale"],
      "test_count": 1
    }
  ],
  "common_tests": ["test_node_scale"]
}
```

### For Infrastructure Failure (permafail=true)

```json
{
  "permafail": true,
  "confidence": 0.92,
  "reason": "All 3 runs fail at cluster creation with identical error: 'Insufficient quota for machine type n1-standard-4'",
  "failure_type": "infra_failure",
  "signatures": [
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "error": "Insufficient quota for machine type n1-standard-4",
      "error_hash": "a1b2c3d4e5f6g7h8"
    },
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "error": "Insufficient quota for machine type n1-standard-4",
      "error_hash": "a1b2c3d4e5f6g7h8"
    },
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/bucket/logs/...",
      "error": "Insufficient quota for machine type n1-standard-4",
      "error_hash": "a1b2c3d4e5f6g7h8"
    }
  ]
}
```

### For Non-Permafail (mixed or varying failures)

```json
{
  "permafail": false,
  "confidence": 0.88,
  "reason": "Mixed failure types detected: 2/3 runs are test_failure, 1/3 is infra_failure. Inconsistent pattern indicates flaky behavior, not a systematic permafail. Test failures: 2/3 (threshold: 2/3). Infra failures: 1/3 (threshold: 1/3).",
  "failure_type": "mixed",
  "match_ratio": "2/3",
  "matching_runs": 2,
  "comparable_runs": 3,
  "threshold_required": 2,
  "signatures": [
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["test_networking"],
      "test_count": 1
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "Pod evicted due to memory pressure",
      "error_hash": "x1y2z3a4b5c6d7e8"
    },
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["test_storage", "test_deployment"],
      "test_count": 2
    }
  ]
}
```

## Failure Signature Format

### Test Failure Signature

```json
{
  "type": "test_failure",
  "url": "string (job URL)",
  "tests": ["array", "of", "failing_test_names"],
  "test_count": "integer (length of tests array)"
}
```

**Fields:**
- `type`: Always "test_failure"
- `url`: The Prow job URL for this run
- `tests`: Array of test names extracted from failure logs (deduplicated)
- `test_count`: Count of unique failing tests

### Infrastructure Failure Signature

```json
{
  "type": "infra_failure",
  "url": "string (job URL)",
  "error": "string (normalized error message)",
  "error_hash": "string (MD5 hash of normalized error)"
}
```

**Fields:**
- `type`: Always "infra_failure"
- `url`: The Prow job URL for this run
- `error`: Normalized error message with timestamps and build IDs removed
- `error_hash`: MD5 hash for fast similarity comparison

## Permafail Detection Logic

### Test Failure Logic

Apply the threshold rules from Step 5 based on the number of test_failure signatures (the comparable run count):

1. Count total test_failure signatures (this is N, the **denominator**)
2. Collect all unique test names from test_failure signatures
3. For each unique test name, count how many test_failure signatures contain it (the **numerator**)
4. Check if any test meets the threshold:
   - **N=2-3**: Test must appear in ALL N runs (100% match required)
   - **N=4-5**: Test must appear in ≥4 runs (80% match required)
   - **N=6-10**: Test must appear in ≥ceil(N × 0.7) runs (70% match required)
5. **Permafail = TRUE** if ANY test meets the threshold
6. Set confidence based on match strength:
   - 0.99 if all test_failure runs have identical test set
   - 0.85 or higher if threshold is met exactly (e.g., 3/3, 4/5, 7/10)
   - 0.92 if threshold is exceeded (e.g., 5/5, 8/10)
   - 0.70 or higher if no test meets threshold but the non-permafail verdict is clear
7. In the `reason`, include the strongest test ratio in slash form, for example `7/10 test_failure runs failed TestNetworkPolicy` or `2/10 test_failure runs failed TestNetworkPolicy`.
8. Include top-level `match_ratio`, `matching_runs`, `comparable_runs`, and `threshold_required` fields for the strongest test pattern.

### Infrastructure Failure Logic

Apply the threshold rules from Step 5 based on the number of infra_failure signatures (the comparable run count):

1. Count total infra_failure signatures (this is N, the **denominator**)
2. Extract error messages and group similar errors (exact hash match or >70% string similarity)
3. For each error group, count how many infra_failure signatures contain it (the **numerator**)
4. Apply threshold based on **N** (total infra_failure count, not the error group size):
   - **N=2-3**: Error must appear in ALL N runs (100% required)
   - **N=4-5**: Error must appear in ≥4 runs (80% required)
   - **N=6-10**: Error must appear in ≥ceil(N × 0.7) runs (70% required)
5. **Permafail = TRUE** if ANY error group meets its threshold
   - Example: 5 total infra_failure signatures, 3 with "operator X timeout", 2 with random errors
   - Denominator N=5 → needs 4/5 (80%) → 3/5 = 60% < 80% → NOT PERMAFAIL
6. Set confidence based on match strength:
   - 0.99 if all infra_failure runs have identical error hash
   - 0.85 or higher if the threshold is met exactly
   - 0.92 if threshold is met with >80% string similarity
   - 0.88 if threshold is met with >70% string similarity
   - 0.70 or higher if no error group meets threshold but the non-permafail verdict is clear
7. In the `reason`, include the strongest infra ratio in slash form, for example `5/6 infra_failure runs share operator authentication timeout` or `1/6 infra_failure runs share the strongest error`.
8. Include top-level `match_ratio`, `matching_runs`, `comparable_runs`, and `threshold_required` fields for the strongest infra pattern.

### Mixed Type Logic

When both test_failure and infra_failure types are present:
1. **Analyze each group independently** using their respective thresholds
2. **Test failures**: Check if test_failure signatures have common failing tests
3. **Infra failures**: Check if infra_failure signatures have common errors
4. If **either group meets the permafail criteria**: **PERMAFAIL = TRUE**
   - Report the pattern that triggered permafail (tests or infra)
   - Explain the breakdown (e.g., "4 of 4 test runs failed on the same test; 3 other runs failed during setup")
   - Set `failure_type` to the type that triggered the permafail: `test_failure` or `infra_failure`
   - Use the triggering type's top-level ratio fields. For example, if 4/4 test failures match and infra failures are noise, set `failure_type: "test_failure"`, `match_ratio: "4/4"`, `matching_runs: 4`, `comparable_runs: 4`, and the test threshold.
5. If **neither group meets criteria**: **PERMAFAIL = FALSE**
   - Reason: "No consistent pattern found in test failures or infrastructure failures"
   - If both test_failure and infra_failure signatures are present, set `failure_type` to `mixed`, not `flaky`
6. In mixed cases, include slash-format ratios for the evaluated groups in the `reason`, such as `1/1 test_failure runs` and `1/6 infra_failure runs`.

**Key Principle**: Infrastructure failures (cluster setup, resource quota, network issues) are **orthogonal** to test failures. A PR can have a systematic test failure (permafail) even if some runs fail during infrastructure setup. Analyze each type separately and detect permafails in either category.

## Error Handling

### Scenario 1: Artifact Fetch Failure

If artifact fetching fails for a job URL:
- Return status: "error"
- Return error message with specific failure reason (network error, 404, timeout, etc.)
- Continue with remaining jobs when at least 2 jobs have not yet been attempted
- Do NOT return a permafail verdict when fewer than 2 jobs completed successfully

**Response:**
```json
{
  "status": "error",
  "error": "Failed to fetch artifacts for job: 404 Not Found at gcsweb URL",
  "action": "verify_job_url_validity"
}
```

### Scenario 2: Timeout on Job Analysis

If the classifier script times out or returns an incomplete result:
- Report the script error.
- Continue only if at least 2 valid signatures are available from another trusted source.
- If only 1 or 0 signatures are available: Return error.

**Response:**
```json
{
  "status": "error",
  "error": "Analysis timeout: Only 2 of 3 jobs analyzed successfully. Insufficient data for permafail determination.",
  "completed_jobs": 2,
  "action": "retry_with_single_job"
}
```

### Scenario 3: Invalid Job URLs

If URL validation fails:
- Return status: "error"
- Return specific validation error message
- Do NOT attempt analysis

**Response:**
```json
{
  "status": "error",
  "error": "Invalid job URL format: 'url3' is not a valid Prow job URL",
  "invalid_url": "url3",
  "action": "provide_valid_urls"
}
```

### Scenario 4: Job Names Don't Match

If the job_name parameter doesn't match the actual job names extracted from URLs:
- Return status: "error"
- Return the expected vs actual job names

**Response:**
```json
{
  "status": "error",
  "error": "Job name mismatch. Expected 'pull-ci-job-xyz' but found 'pull-ci-job-abc' in run 2",
  "expected_job": "pull-ci-job-xyz",
  "actual_job": "pull-ci-job-abc",
  "action": "provide_matching_job_urls"
}
```

### Scenario 5: Insufficient Comparable Runs (Different Types)

If analysis completes but there are insufficient comparable runs for permafail determination (e.g., 1 test_failure + 1 infra_failure):
- Return permafail: false
- Explain that neither failure type has ≥2 comparable runs
- This is NOT an error - the analysis succeeded but found no same-type pattern

**Response:**
```json
{
  "permafail": false,
  "confidence": 0.70,
  "reason": "Insufficient comparable runs: 1/2 test failures, 1/2 infra failures. Cannot establish a permafail pattern with only one run of each type. Need at least 2 runs of the same failure type to determine if failures are systematic. Test: 1/2 (threshold: 2/2). Infra: 1/2 (threshold: 2/2).",
  "failure_type": "mixed",
  "match_ratio": "1/2",
  "matching_runs": 1,
  "comparable_runs": 2,
  "threshold_required": 2,
  "signatures": [
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["[sig-network] test"]
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "cluster creation failed"
    }
  ]
}
```

### Scenario 6: Failure to Extract Failure Details

If the classifier output doesn't contain expected failure information:
- Mark this run as "incomplete"
- Continue with other runs
- If ≥2 runs have valid failure data, proceed with analysis
- Otherwise, return error

**Response:**
```json
{
  "status": "incomplete",
  "warning": "Run 1 analysis incomplete: could not extract failure details",
  "completed_jobs": 2,
  "incomplete_jobs": 1,
  "permafail": "unknown",
  "recommendation": "Review job logs manually or retry analysis"
}
```

## Examples

### Example 1: Permafail - Identical Failing Test

**Input:**
```json
{
  "failure_urls": [
    "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234567",
    "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234568",
    "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234569"
  ],
  "job_name": "pull-ci-openshift-origin-master-e2e-aws",
  "pr_info": {
    "pr_number": 12345,
    "repository": "openshift/origin"
  }
}
```

**Subagent analysis results for all 3 runs:**
- Run 1: Failed tests = ["[sig-api] API discovery should provide capability information"]
- Run 2: Failed tests = ["[sig-api] API discovery should provide capability information"]
- Run 3: Failed tests = ["[sig-api] API discovery should provide capability information"]

**Output:**
```json
{
  "permafail": true,
  "confidence": 0.99,
  "reason": "3/3 consecutive runs fail with identical test: '[sig-api] API discovery should provide capability information'. This is a systematic permanent failure.",
  "failure_type": "test_failure",
  "match_ratio": "3/3",
  "matching_runs": 3,
  "comparable_runs": 3,
  "threshold_required": 3,
  "signatures": [
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234567",
      "tests": ["[sig-api] API discovery should provide capability information"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234568",
      "tests": ["[sig-api] API discovery should provide capability information"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/pull-ci-openshift-origin-master-e2e-aws/1234569",
      "tests": ["[sig-api] API discovery should provide capability information"],
      "test_count": 1
    }
  ],
  "common_tests": ["[sig-api] API discovery should provide capability information"]
}
```

### Example 2: Permafail Despite Mixed Failure Types

**Input:**
```json
{
  "failure_urls": [
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1111",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1112",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1113",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1114",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1115",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1116",
    "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1117"
  ],
  "job_name": "periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node",
  "pr_info": {
    "pr_number": 3186,
    "repository": "openshift/ovn-kubernetes"
  }
}
```

**Subagent analysis results:**
- Run 1: Infrastructure failure = "Cluster creation timeout" (infra_failure)
- Run 2: Failed tests = ["[sig-network] Networking should provide connectivity"] (test_failure)
- Run 3: Infrastructure failure = "AWS quota exceeded" (infra_failure)
- Run 4: Failed tests = ["[sig-network] Networking should provide connectivity"] (test_failure)
- Run 5: Failed tests = ["[sig-network] Networking should provide connectivity"] (test_failure)
- Run 6: Infrastructure failure = "Cluster creation timeout" (infra_failure)
- Run 7: Failed tests = ["[sig-network] Networking should provide connectivity"] (test_failure)

**Analysis:**
- 7 total runs: 3 infra_failures, 4 test_failures
- Test failures: 4/4 (100%) have identical failing test
- Infra failures: 3 runs, but different errors (not a permafail pattern in infra)
- Verdict: **PERMAFAIL = TRUE** based on test failure group

**Output:**
```json
{
  "permafail": true,
  "confidence": 0.99,
  "reason": "All 4 runs that reached e2e tests failed on '[sig-network] Networking should provide connectivity' (100% match). 3 additional runs failed during infrastructure setup (cluster creation, AWS quota) and are not relevant to this test failure pattern. This is a systematic test failure caused by the PR changes.",
  "failure_type": "test_failure",
  "signatures": [
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1111",
      "error": "Cluster creation timeout",
      "error_hash": "a1b2c3d4"
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1112",
      "tests": ["[sig-network] Networking should provide connectivity"],
      "test_count": 1
    },
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1113",
      "error": "AWS quota exceeded",
      "error_hash": "e5f6g7h8"
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1114",
      "tests": ["[sig-network] Networking should provide connectivity"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1115",
      "tests": ["[sig-network] Networking should provide connectivity"],
      "test_count": 1
    },
    {
      "type": "infra_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1116",
      "error": "Cluster creation timeout",
      "error_hash": "a1b2c3d4"
    },
    {
      "type": "test_failure",
      "url": "https://prow.ci.openshift.org/view/gs/..../logs/periodic-ci-openshift-release-main-ci-4.19-e2e-aws-upgrade-ovn-single-node/1117",
      "tests": ["[sig-network] Networking should provide connectivity"],
      "test_count": 1
    }
  ],
  "common_tests": ["[sig-network] Networking should provide connectivity"]
}
```

### Example 3: NOT Permafail - Insufficient Matching Infra Errors

**Input:** 5 runs where 3 have identical operator installation failure, 2 have random infra issues

**Subagent analysis results:**
- Run 1: Infrastructure failure = "operator authentication timeout waiting for operator to reach Available=True" (infra_failure)
- Run 2: Infrastructure failure = "AWS quota exceeded for instance type m5.xlarge" (infra_failure)
- Run 3: Infrastructure failure = "operator authentication timeout waiting for operator to reach Available=True" (infra_failure)
- Run 4: Infrastructure failure = "operator authentication timeout waiting for operator to reach Available=True" (infra_failure)
- Run 5: Infrastructure failure = "Pod evicted due to memory pressure on node ip-10-0-1-2" (infra_failure)

**Analysis:**
- 5 total infra_failure signatures (denominator = 5)
- "operator authentication timeout" appears in 3 runs (numerator = 3)
- Threshold for N=5 (4-5 runs): need at least 4 matching (80% required)
- 3/5 = 60% < 80% → NOT PERMAFAIL

**Output:**
```json
{
  "permafail": false,
  "confidence": 0.70,
  "reason": "Infrastructure failures are not consistent enough. 3/5 runs failed with 'operator authentication timeout waiting for operator to reach Available=True' (60% match), but with 5 infra failures at least 4/5 must match (80% required). The presence of 2 different random errors indicates flaky infrastructure rather than systematic failure.",
  "failure_type": "infra_failure",
  "match_ratio": "3/5",
  "matching_runs": 3,
  "comparable_runs": 5,
  "threshold_required": 4,
  "signatures": [
    {
      "type": "infra_failure",
      "url": "...",
      "error": "operator authentication timeout waiting for operator to reach Available=True",
      "error_hash": "a1b2c3d4"
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "AWS quota exceeded for instance type m5.xlarge",
      "error_hash": "e5f6g7h8"
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "operator authentication timeout waiting for operator to reach Available=True",
      "error_hash": "a1b2c3d4"
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "operator authentication timeout waiting for operator to reach Available=True",
      "error_hash": "a1b2c3d4"
    },
    {
      "type": "infra_failure",
      "url": "...",
      "error": "Pod evicted due to memory pressure on node ip-10-0-1-2",
      "error_hash": "i9j0k1l2"
    }
  ]
}
```

### Example 4: Non-Permafail - No Consistent Pattern

**Input:** 3 runs with different test failures

**Subagent analysis results:**
- Run 1: Failed tests = ["[sig-network] networking should support networking"] (test_failure)
- Run 2: Failed tests = ["[sig-storage] storage should support volumes"] (test_failure)
- Run 3: Failed tests = ["[sig-api] API discovery should work"] (test_failure)

**Output:**
```json
{
  "permafail": false,
  "confidence": 0.70,
  "reason": "No consistent failure pattern detected. 0/3 runs show matching tests - each of the 3 runs failed with different tests: networking, storage, API discovery. This indicates flaky/non-deterministic behavior rather than a systematic permafail.",
  "failure_type": "test_failure",
  "match_ratio": "0/3",
  "matching_runs": 0,
  "comparable_runs": 3,
  "threshold_required": 3,
  "signatures": [
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["[sig-network] networking should support networking"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["[sig-storage] storage should support volumes"],
      "test_count": 1
    },
    {
      "type": "test_failure",
      "url": "...",
      "tests": ["[sig-api] API discovery should work"],
      "test_count": 1
    }
  ]
}
```

### Threshold Logic Validation Examples

**Table-driven test cases demonstrating correct threshold behavior:**

| Total URLs | Test Failures | Infra Failures | Matching Test Count | Verdict | Reason |
|------------|---------------|----------------|---------------------|---------|---------|
| 10 | 10 | 0 | 2 same test | NOT permafail | 2/10 = 20% < 70% threshold (need ≥7) |
| 10 | 10 | 0 | 7 same test | PERMAFAIL | 7/10 = 70% ≥ 70% threshold ✓ |
| 7 | 4 | 3 | 4 same test (in test bucket) | PERMAFAIL | 4/4 = 100% ≥ 80% threshold (4-5 runs need ≥4) ✓ |
| 7 | 1 | 6 | 1 test, all 6 infra diverse | NOT permafail | Only 1 test_failure (need ≥2), and infra errors are all different |
| 7 | 1 | 6 | 1 test, 5 same infra error | PERMAFAIL | 5/6 = 83% ≥ ceil(6×0.7)=5 (70% threshold) → infra bucket meets threshold ✓ |

## Technical Details

### Artifact Analysis Approach

This skill analyzes Prow job artifacts directly using techniques from existing CI skills:

1. **URL parsing** - Extract job name and build ID from Prow URLs
2. **Artifact fetching** - Use `plugins/ci/scripts/classify-job-failures.py` to fetch prowjob.json and browse artifacts
3. **Classification** - Use artifact-based detection (junit files, test directories) to classify failures
4. **Failure extraction** - Parse junit XML or build logs to extract test names or error messages

This approach follows patterns from `fetch-prowjob-json`, `prow-job-artifact-search`, and `prow-job-analyze-test-failure` skills.

### Script Execution Strategy

The classifier script performs deterministic artifact analysis before AI threshold reasoning:

```text
failure_urls ━━━ classify-job-failures.py ━━━ normalized signatures ━━━ Step 5 threshold analysis
```

**Benefits:**
- Keeps artifact fetching and parsing deterministic.
- Avoids spending agent reasoning on mechanical classification.
- Produces the same normalized signature schema used by offline eval cases.

**Synchronization:**
- Run the script once with all failure URLs.
- Require at least 2 valid normalized signatures to proceed.
- Stop and report the script's JSON error if URL validation or artifact fetching fails.

### Error Message Normalization

Normalize infrastructure error messages for comparison:

1. Remove timestamps: `2025-05-12T14:32:10Z` → ""
2. Remove build IDs: `build-12345-xyz` → ""
3. Remove resource names with IDs: `pod-abc123xyz` → "pod-*"
4. Remove request/limit values: Numbers in memory/CPU specs → ""
5. Keep: Error classification, core message, error type

**Example normalization:**
```text
Input:  "Pod evicted at 2025-05-12T14:32:10Z (build-12345): insufficient memory (512M < 1Gi required)"
Output: "Pod evicted: insufficient memory (* < *Gi required)"
```

### Confidence Scoring

Confidence reflects how certain the permafail verdict is:

- **0.99**: All 3 runs have identical failure signature (test names or error hashes)
- **0.95**: All 3 runs have ≥1 common failing test in test_failure
- **0.92**: All 3 runs have >80% similar error messages in infra_failure
- **0.85**: 2 of 3 runs share common failure or mixed types detected
- **0.70**: Insufficient data or ambiguous failure patterns

Use confidence to determine remediation priority:
- Confidence ≥ 0.95: High priority permafail, block PR merge
- Confidence 0.85-0.94: Medium priority, warn but allow manual override
- Confidence < 0.85: Low confidence verdict, require manual review
