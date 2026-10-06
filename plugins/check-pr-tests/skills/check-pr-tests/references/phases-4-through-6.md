# Phases 4–6

### Phase 4: Determine If Test Is Required (when no tests found in PR)

**Skip this phase if test files were found in Phase 3.**

#### 4a. Change classification

Fetch the diff for non-vendor, non-generated files:

```bash
pr_diff=$(gh pr diff "$target_pr_url")
```

Analyze the diff and classify the change into one of these categories:

| Category | Test Required? | Reasoning |
|----------|----------------|-----------|
| **Dependency bump only** (go.mod + vendor changes, no source code changes) | Likely no | Existing tests exercise the dependency |
| **Bug fix** (logic change in existing function) | Yes | Regression test should prove the fix works |
| **New feature** (new functions, new files) | Yes | New behavior needs coverage |
| **API change** (interface changes, type changes) | Yes | Contract changes must be tested |
| **Config/infra change** (Dockerfile, CI config, Makefile only) | Likely no | Not unit-testable; CI pipeline validates |
| **Refactor** (moving code, renaming, no behavior change) | Likely no | Existing tests should still pass |

Use AI analysis of the actual diff content to make this classification. Look at:
- Whether code files (not vendor/config) were changed
- Whether functions were added, modified, or only moved
- Whether the change is purely mechanical (import paths, variable renames)

**Cross-reference with Jira test context** (from Phase 3.5):

After classifying the change from the diff, cross-reference the `jira_test_context` to refine test requirements:

- If Jira indicates performance testing is required (e.g., `required_test_types` includes `e2e_performance`) but only unit tests exist in the PR → flag as a **test type gap**
- If Jira shows manual QA verification was performed (`has_manual_verification == true`) → record as "manual verification performed" — this is valid coverage for E2E/performance test types but is not automated coverage
- If the bug description implies E2E-level behavior (cluster-level symptoms, pod behavior, network policy changes) → recommend E2E coverage in addition to any unit tests found
- If Jira labels or components suggest specific test scopes (e.g., `SDN:Scale`) → ensure the corresponding test type is listed in `required_test_types`

The combined analysis should produce both the `change_classification` (from the diff) and the `required_test_types` (informed by Jira context), which together determine coverage adequacy.

#### 4b. Check for existing test coverage in the repo

Even when no test files are modified in the PR, existing tests may cover the changed code:

1. **Same-package test files**: Check if `_test.go` files exist in the same package as the changed files:
   ```bash
   for pkg_dir in $changed_packages; do
     existing_tests=$(gh api "repos/${owner_repo}/contents/${pkg_dir}" --jq '.[].name' 2>/dev/null | grep '_test\.go$')
   done
   ```

2. **Function-level coverage**: Search existing test files for references to the changed functions. Extract function names from the diff (functions that were added or modified), then search for them:
   ```bash
   # Extract modified/added function names from diff
   changed_funcs=$(echo "$pr_diff" | grep -oE '^\+func ([A-Za-z][A-Za-z0-9_]*)' | sed 's/^+func //' | sort -u)

   # Search test files in the repo for calls to those functions
   for func_name in $changed_funcs; do
     gh search code "repo:${owner_repo} path:*_test.go ${func_name}" --json path --jq '.[].path' 2>/dev/null
   done
   ```

3. **E2E test coverage**: Check if the component has e2e tests:
   ```bash
   # Search openshift/origin for component-related e2e tests
   component_name=$(basename "$owner_repo" | sed 's/^cluster-//' | sed 's/-operator$//')
   gh search code "repo:openshift/origin ${component_name}" --filename '_test.go' --json path --jq '.[].path' 2>/dev/null
   ```

#### 4c. Produce a determination

Based on the analysis:

- **"Test required — not found"**: Code change is a bug fix, new feature, or API change AND no existing tests cover the changed functions.
- **"Covered by existing tests"**: Code change is exercised by existing test files in the same package or e2e tests reference the component.
- **"Test not required"**: Pure dependency bump, config change, or refactor with existing coverage.

### Phase 5: Find Exact Test Names for CI Lookup

**When count=2**: Test file names and function names discovered from the upstream PR are searched for in the downstream PR's diff. If the upstream test commit was cherry-picked or carried downstream, the same test files/functions should appear. This confirms the test made it to the downstream repo.

When tests are found (in PR or existing), map them to CI-executable test names.

#### 5a. Unit test names

Go test names follow the pattern `TestFunctionName` and run as `{package_path}.TestFunctionName`.

Search the downstream PR's CI checks for unit test jobs:
```bash
unit_jobs=$(gh pr checks "$downstream_pr_url" --json name,state | jq -r '.[] | select(.name | test("unit|lint|verify")) | .name')
```

#### 5b. E2E/Ginkgo test names

OpenShift e2e tests use the format: `[sig-network][Feature:EgressRouter] should create egress router resources`

To find matching e2e tests:

1. **Search by component in Sippy**:
   ```bash
   component_keyword=$(basename "$owner_repo" | sed 's/^cluster-//' | sed 's/-operator$//')
   release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest 2>/dev/null || echo "4.19")

   sippy_filter=$(jq -n --arg kw "$component_keyword" '{items:[{columnField:"name",operatorValue:"contains",value:$kw}]}')
   encoded_filter=$(jq -rn --arg s "$sippy_filter" '$s | @uri')
   sippy_url="https://sippy.dptools.openshift.org/api/tests/v2?release=${release}&filter=${encoded_filter}"
   curl -s "$sippy_url" | jq '.[]'
   ```

2. **Search openshift-tests source**:
   ```bash
   gh search code "repo:openshift/origin ${component_keyword}" --filename '*.go' --json path --jq '.[].path' 2>/dev/null | head -10
   ```

#### 5c. Record discovered test names

Store a list of discovered tests with:
- Test function name (e.g., `TestMacvlanCreate`)
- Full CI test name if known (e.g., `[sig-network][Feature:EgressRouter] should create egress router resources`)
- Test ID from Sippy if available (e.g., `openshift-tests:71c053c318c...`)

### Phase 6: Prow CI Result Lookup

#### 6a. Get all CI checks on the downstream PR

```bash
ci_checks=$(gh pr checks "$downstream_pr_url" --json name,state,detailsUrl)
```

**Error conditions to check**:
- **No checks found at all**: Error out — "No Prow CI checks found on the downstream PR. Prow CI is required to verify the bug." Guide: "Ensure the PR is opened against a repo in the openshift/ org with Prow configured."
- **Checks still running (any state is "PENDING")**: Error out — "Prow job {job_name} is still in progress — artifacts not yet available." Guide: "Wait for the job to complete and re-run the skill."

#### 6b. Overall CI status summary

```bash
total=$(echo "$ci_checks" | jq 'length')
passed=$(echo "$ci_checks" | jq '[.[] | select(.state == "SUCCESS" or .state == "PASS")] | length')
failed=$(echo "$ci_checks" | jq '[.[] | select(.state == "FAILURE" or .state == "FAIL" or .state == "ERROR")] | length')
pending=$(echo "$ci_checks" | jq '[.[] | select(.state == "PENDING" or .state == "QUEUED")] | length')
```

#### 6c. Test-specific result lookup

For each test name discovered in Phase 5:

1. **In PR's Prow job artifacts**: If a CI job has completed, attempt to find the specific test result in JUnit XML artifacts. Extract the Prow job URL from `detailsUrl` in the checks output.

   The GCS artifact path pattern is:
   ```
   gs://test-platform-results/{path_from_prow_url}/artifacts/{job_step}/**/junit*.xml
   ```

   **If GCS is not accessible** (authentication failure): Error out with:
   ```
   ERROR: GCS authentication failed — cannot download JUnit XML from test-platform-results bucket.
   Run `gcloud auth login` and ensure access to gs://test-platform-results.
   ```

   **If artifacts have expired** (404/not found): Error out with:
   ```
   ERROR: Prow artifacts for job {job_name} have been garbage collected (typically retained 2-8 weeks).
   Re-trigger the Prow job with `/retest` on the PR to generate fresh artifacts.
   ```

2. **Via Sippy API**: If a test ID was discovered in Phase 5, call the `fetch-test-runs` script directly:
   ```bash
   python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py "$test_id" --format json
   ```
   Filter the returned runs to find those matching the downstream PR's Prow job URLs.

3. **Pass/fail determination**: For each test, record:
   - Job name where it ran
   - Pass or fail status
   - If failed: error message snippet from JUnit XML or build log

