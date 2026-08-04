---
name: check-pr-tests
description: Deep test coverage verification and CI validation for GitHub PRs linked to Jira issues
allowed-tools: Bash(gh *) Bash(jq *) Bash(curl *) Bash(python3 *) Bash(sed *) Bash(grep *) Bash(cat *) mcp__plugin_jira_atlassian__getAccessibleAtlassianResources mcp__plugin_jira_atlassian__getJiraIssue mcp__plugin_jira_atlassian__searchJiraIssuesUsingJql mcp__plugin_jira_atlassian__getJiraIssueRemoteIssueLinks
---

# Check PR Tests

This skill performs end-to-end test coverage verification and CI validation for a GitHub PR linked to a Jira issue. It extracts the Jira key, discovers upstream/downstream PRs, deeply inspects commits for test coverage, determines if tests are required, finds exact CI test names, checks Prow results, and optionally posts actionable feedback to the PR.

**IMPORTANT FOR AI**: This is a **procedural skill** — when invoked, directly execute the implementation steps defined in this document. Do NOT look for or execute external scripts. Follow the step-by-step instructions in the phases below.

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

### Phase 1: Jira Key Extraction & PR Discovery

1. **Parse the PR title and author**:
   ```bash
   pr_data=$(gh pr view "$pr_url" --json title,author,number,url,state)
   pr_title=$(echo "$pr_data" | jq -r '.title')
   pr_author=$(echo "$pr_data" | jq -r '.author.login')
   pr_number=$(echo "$pr_data" | jq -r '.number')
   pr_state=$(echo "$pr_data" | jq -r '.state')
   ```

2. **Extract Jira key from the title** using regex `([A-Z][A-Z0-9]+-\d+)`:
   ```bash
   jira_key=$(echo "$pr_title" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)
   ```

3. **If no Jira key found**: Exit with error:
   ```
   ERROR: No Jira key found in PR title: "{pr_title}"
   Please ensure the PR title contains a Jira issue key (e.g., OCPBUGS-12345).
   ```

4. **Invoke `/jira:extract-prs`** with the Jira key to find all linked PRs. Use the `extract-prs` skill from the `jira` plugin. The skill returns JSON with `pull_requests` array containing objects with `url`, `state`, `title`, `isDraft`, `sources`, and `found_in_issues`.

   Store the result for use in Phase 2.

5. **If `extract-prs` returns no PRs**: Warn and proceed with only the input PR:
   ```
   WARNING: /jira:extract-prs returned no linked PRs for {jira_key}. Proceeding with only the input PR.
   ```
   In this case, create a minimal PR list containing just the input PR.

### Phase 2: Upstream/Downstream Classification

Classify each PR discovered in Phase 1:

1. **Classification rules**:
   - **Downstream**: URL contains `github.com/openshift/`
   - **Upstream**: URL does NOT contain `github.com/openshift/`

2. **Count handling**:

   **If `count` was provided**:
   - Validate that the number of discovered PRs matches the provided count
   - If mismatch: warn but continue
     ```
     WARNING: Expected {count} PR(s) but found {actual_count} from extract-prs. Continuing with available PRs.
     ```

   **If `count` was omitted** (auto-detect):
   - Classify all PRs from extract-prs as upstream or downstream
   - If only `openshift/` PRs found → set `detected_count=1` (downstream only)
   - If both openshift and non-openshift PRs found → set `detected_count=2` (upstream + downstream)
   - Log the auto-detected count:
     ```
     Auto-detected count={detected_count}: {description}
     ```

3. **Identify the target PRs**:
   - **When count=2**: The upstream PR is inspected for test files/functions. The downstream PR is the target for CI verification.
   - **When count=1**: The downstream PR (which should be the input PR) is analyzed for both test files and CI results.
   - **Downstream PR**: Use the input PR if it's an openshift/ PR; otherwise use the first openshift/ PR from extract-prs results.

### Phase 3: Deep Commit Inspection

Inspect the target PR to identify code changes and test changes.

**When count=2**: Inspect the upstream PR for test discovery AND the downstream PR for CI checks.
**When count=1**: Inspect the downstream PR for both.

#### 3a. Identify code changes (non-test, non-vendor files)

```bash
# Get all changed files in the PR
owner_repo=$(echo "$target_pr_url" | sed -E 's|https://github.com/([^/]+/[^/]+)/pull/.*|\1|')
pr_num=$(echo "$target_pr_url" | sed -E 's|.*/pull/([0-9]+).*|\1|')
changed_files=$(gh api "repos/${owner_repo}/pulls/${pr_num}/files" --paginate --jq '.[].filename')
```

**Filter OUT** (non-code files):
- Files under `vendor/`
- `go.sum`, `go.mod`
- `.gitignore`
- Files under `docs/`, `documentation/`
- CI config files: `.ci-operator/`, `ci-operator/`, `.github/`, `.prow/`
- Generated files: `zz_generated*`, `*_generated.go`
- `Makefile`, `Dockerfile`, `Containerfile`

**Filter IN** (source code files):
- `*.go` (not under `vendor/`, not `*_test.go`)
- `*.py` (not under `site-packages/`, `.tox/`)

Record the **packages/directories** that changed:
```bash
# Extract unique directory paths from changed code files
changed_packages=$(echo "$code_files" | xargs -I{} dirname {} | sort -u)
```

#### 3b. Identify test changes in the same PR

Filter the changed files list for test patterns:

- **Go**: `*_test.go` (not under `vendor/`)
- **Python**: `test_*.py`, `*_test.py` (not under `site-packages/`, `.tox/`)

```bash
test_files=$(echo "$changed_files" | grep -E '(_test\.go$|^test_.*\.py$|_test\.py$)' | grep -v '^vendor/' | grep -v 'site-packages/' | grep -v '\.tox/')
```

#### 3c. Extract test function names from the diff

For each test file found in 3b, fetch the patch diff and extract added test function names:

```bash
# Get the patch for each test file
for test_file in $test_files; do
  patch=$(gh api "repos/${owner_repo}/pulls/${pr_num}/files" --paginate --jq ".[] | select(.filename == \"${test_file}\") | .patch")

  # Go: extract added test/benchmark function names
  go_test_funcs=$(echo "$patch" | grep -oE '^\+func (Test[A-Za-z0-9_]+|Benchmark[A-Za-z0-9_]+)' | sed 's/^+func //')

  # Python: extract added test function/class names
  py_test_funcs=$(echo "$patch" | grep -oE '^\+(def test_[A-Za-z0-9_]+|class Test[A-Za-z0-9_]+)' | sed 's/^+//' | sed 's/def //' | sed 's/class //')
done
```

#### 3d. Check if test files are in the same package as code changes

Compare directory paths of changed code files vs test files:
```bash
# For each changed code package, check if any test file is in the same directory
for pkg in $changed_packages; do
  matching_tests=$(echo "$test_files" | grep "^${pkg}/")
done
```

### Phase 3.5: Jira Issue Test Context Inspection

This phase runs for **all PRs**, regardless of whether tests were found in Phase 3. It extracts testing requirements and QA context from each Jira issue to determine what test types are needed and what testing has already been performed outside the PR.

**For each Jira key** discovered in Phase 1, use the MCP `getJiraIssue` tool to fetch the full issue data (the Jira data fetched in Phase 1 via `extract-prs` should be retained and reused here rather than re-fetched). Inspect three sources:

#### 3.5a. Description analysis

Parse the Jira issue description for testing-relevant content:

- **Acceptance criteria**: Look for sections labeled "Acceptance Criteria", "Expected Behavior", "Definition of Done" that specify test expectations
- **Test type mentions**: Search for explicit references to test types: "unit test", "e2e", "conformance", "functional", "performance", "scale", "integration"
- **Nature of the bug/change**: Identify whether the issue describes a performance regression, API behavior change, network policy issue, cluster-level symptom, etc. This informs what test types are appropriate:
  - Performance regression → `unit` + `e2e_performance`
  - API behavior change → `unit` + `functional`
  - Network policy / cluster-level → `unit` + `e2e`
  - Data race / concurrency → `unit`
  - UI / console change → `functional` + `e2e`

#### 3.5b. Comment analysis

Scan all Jira issue comments for QA verification and testing context:

- **QA verification results**: Look for patterns indicating manual testing was performed:
  - "Verified", "Tested on", "Validated"
  - Cluster version strings like `4.x.0-0-`, `oc version` output
  - Performance metrics (CPU, memory, latency numbers)
  - References to test environments or clusters
- **Testing performed**: Extract what types of testing were done:
  - Manual E2E testing
  - Performance benchmarks
  - Conformance runs
  - Scale testing
- **Who performed testing**: Distinguish between:
  - QA Contact (formal QA validation)
  - Developer (informal testing)
  - Bot / CI (automated)
- **Testing gaps mentioned**: Look for comments indicating missing coverage:
  - "needs e2e", "conformance not run", "no automation for this"
  - "TODO: add test", "test pending"

#### 3.5c. Jira metadata analysis

Check Jira issue fields for testing scope indicators:

- **Labels**: Look for labels that imply specific test requirements:
  - `SDN:Scale`, `*:Scale` → performance testing expected
  - `*:E2E` → E2E testing expected
  - `TestBlocker` → existing tests are affected
- **QA Contact field**: If a QA Contact is assigned, formal QA validation is expected
- **Issue type and severity**:
  - Critical/Blocker severity → broader test coverage recommended
  - Bug vs Enhancement → bugs need regression tests, enhancements need feature tests
- **Components**: Map components to expected test scopes (e.g., `Networking` → e2e networking tests)

#### 3.5d. Output

For each Jira key, produce a `jira_test_context` object:

```json
{
  "jira_key": "OCPBUGS-98616",
  "required_test_types": ["unit", "e2e_performance"],
  "testing_performed": [
    {
      "type": "manual_e2e_performance",
      "performed_by": "Sachin Ninganure",
      "details": "Verified on 4.19.0 pre-merge: no CPU spikes, peak master CPU 1162m vs 1932m on buggy build",
      "automated": false
    }
  ],
  "testing_gaps": ["No automated performance regression test"],
  "has_manual_verification": true,
  "reasoning": "ANP CPU spike bug requires both unit tests for the fix logic and performance/E2E validation to confirm CPU regression is resolved at scale",
  "automation_suggestions": [
    {
      "test_idea": "Benchmark test measuring API server patch calls with N ANPs",
      "source": "jira_manual_testing",
      "test_type": "unit",
      "suggested_location": "go-controller/pkg/ovn/controller/admin_network_policy/status_test.go",
      "what_to_assert": "Patch call count stays at 0 when status unchanged across 50+ ANPs"
    },
    {
      "test_idea": "Unit test verifying doesStatusNeedAnUpdate returns false for identical conditions",
      "source": "code_diff",
      "test_type": "unit",
      "suggested_location": "go-controller/pkg/ovn/controller/admin_network_policy/status_test.go",
      "what_to_assert": "Function returns false when Status, Reason, and Message are all identical"
    },
    {
      "test_idea": "E2E test creating 50+ ANPs and asserting CPU stays below threshold at CronJob boundaries",
      "source": "jira_description",
      "test_type": "e2e_performance",
      "suggested_location": "[sig-network][Feature:AdminNetworkPolicy] in openshift-tests",
      "what_to_assert": "Master CPU utilization does not spike above baseline after ANP creation"
    }
  ]
}
```

#### 3.5e. Automation suggestion generation

**For each Jira key**, generate `automation_suggestions` by analyzing three sources. Each suggestion must include `test_idea`, `source`, `test_type`, `suggested_location`, and `what_to_assert`.

**Source 1: Manual testing from Jira comments** (`source: "jira_manual_testing"`)
- For each entry in `testing_performed` where `automated == false`, generate a suggestion that automates what was tested manually
- Map the manual test to the appropriate test type and framework
- Example: Manual CPU testing → Go benchmark test or e2e performance test

**Source 2: Jira description and metadata** (`source: "jira_description"`)
- Parse reproduction steps → suggest a test that follows those steps programmatically
- Parse expected/actual results → suggest assertions based on the expected behavior
- Map bug nature to test framework:
  - Performance regression → benchmark test or e2e with metrics assertion
  - Behavioral bug → unit test or functional test exercising the specific scenario
  - Config/env issue → integration test verifying config is respected
- Use labels/components for test naming: e.g., `SDN:Scale` → `[sig-network]` e2e test

**Source 3: Code diff analysis** (`source: "code_diff"`)
- For each new function added in non-test files → suggest a unit test for that function
- For each function modified → suggest a regression test asserting the new behavior
- For code deleted → suggest a test verifying the deleted behavior no longer occurs
- Use the actual package path and existing test file naming conventions for `suggested_location`
- Analyze the function signature and logic to propose meaningful `what_to_assert`

**Deduplication**: If a suggestion from `code_diff` overlaps with one from `jira_manual_testing` (e.g., both suggest testing the same function), merge them and prefer the `jira_manual_testing` source since it has richer context.

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

### Phase 7: PR Feedback (Actions)

**Mode check**: Before executing any action in this phase, check the execution mode:
- If `--dry-run` (or no flag specified): **Do NOT execute** `gh pr comment` or `gh pr edit`. Instead, determine which action *would* be taken, compose the comment body, include it in the output JSON under `action_taken.comment_body`, and prefix `action_taken.type` with `dry_run:`.
- If `--execute`: Execute the `gh pr comment` command to post the comment to the downstream PR.

**In both modes**: Always **display the comment body** to the user in the console output so they can review what was (or would be) posted.

Based on the analysis, determine **ONE** of these actions for the **downstream PR**.

#### Comment Structure Rules

All comments follow a consistent structure with **per-bug sections**. Each Jira key discovered gets its own section. The comment uses the following layout:

1. **Header** — action-specific title (e.g., `## Test Coverage Report`)
2. **Per-bug sections** — one `### {jira_key}` section for each Jira bug, containing:
   - Bug metadata (PR links, change type)
   - Test coverage breakdown with clear **New Tests** vs **Existing Tests** distinction
   - Jira Test Context table (test type requirements, coverage sources, manual verification notes)
   - CI results
3. **CI Summary** — overall CI check counts
4. **Footer** — automation attribution

**GitHub table formatting**: When composing markdown tables for `gh pr comment`, ensure proper rendering by:
- Using a blank line before and after every table
- Aligning the header separator row with consistent dashes (e.g., `| --- | --- | --- | --- |`)
- Keeping cell content concise — truncate error messages to ~80 characters and append `...` if longer
- Not nesting code blocks inside table cells — use inline backticks only
- Testing that pipe characters (`|`) in cell content are escaped as `\|`

#### Test Coverage Categories

When reporting test coverage, clearly distinguish between these categories:

- **New tests (added in this PR)**: Test files and functions that were **added or modified** in the PR diff. These are tests written specifically as part of the code fix. Identified by:
  - New `_test.go` files appearing in the PR's changed file list
  - New `func Test*` / `func Benchmark*` lines in the diff (lines starting with `+`)
  - Modifications to existing test files in the PR

- **Existing tests (already in the repo)**: Test files that were **NOT modified** in this PR but already exist in the same package or test the same component. These are pre-existing tests that exercise the modified code. Identified by:
  - `_test.go` files in the same package directory that are not in the PR's changed file list
  - Test functions in the repo that reference the changed function names (found via `gh search code`)
  - E2E tests in `openshift/origin` that cover the component

This distinction matters because:
- New tests demonstrate the PR author intentionally added coverage for the fix
- Existing tests indicate the change is exercised by pre-existing infrastructure, but no new regression-specific test was written

#### 7a. Tests found AND CI passing

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Upstream PR**: {upstream_pr_url} (state: {upstream_state})
**Change type**: {change_type}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

The following test functions were **added as part of the code fix**:

| Test Function | Test File | Job | Result |
| --- | --- | --- | --- |
| `{test_function_1}` | `{test_file}` | `{job_name}` | PASSED |
| `{test_function_2}` | `{test_file}` | `{job_name}` | PASSED |

#### Existing Tests (already in repo)

The following pre-existing tests also exercise the modified code:

- `{existing_test_file}` in package `{package}` — covers `{function_name}`
- E2E: `{e2e_test_name}` — **PASSED** in `{job_name}` ([link]({prow_url}))

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

All relevant tests passed. Code change is validated.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

**Label**: Label adding is disabled for initial testing. When ready, uncomment:
```bash
# gh pr edit "$downstream_pr_url" --add-label "verified"
```

#### 7b. Tests found BUT CI failing

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Upstream PR**: {upstream_pr_url} (state: {upstream_state})
**Change type**: {change_type}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

The following test functions were **added as part of the code fix**:

| Test Function | Test File | Job | Result |
| --- | --- | --- | --- |
| `{test_function_1}` | `{test_file}` | `{job_name}` | PASSED |

#### Failing Tests

The following tests related to this change are **failing**:

| Test | Test File | Job | Result | Error |
| --- | --- | --- | --- | --- |
| `{test_name}` | `{test_file}` | `{job_name}` | FAILED | `{error_snippet}` |

**Failed job links**:
- [`{job_name}`]({prow_url})

#### Existing Tests (already in repo)

{If existing tests were found, list them here. If none, omit this section.}

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

@{pr_author} — please investigate the test failures above.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

#### 7c. No tests found AND test is required

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Change type**: {bug_fix|new_feature|api_change}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

None. No test files were added or modified in this PR.

#### Existing Tests (already in repo)

No existing tests found that exercise the changed functions.

#### Modified Code Without Test Coverage

| Changed File | Functions Modified |
| --- | --- |
| `{changed_file_1}` | `{func1}`, `{func2}` |
| `{changed_file_2}` | `{func3}` |

Given that this is a **{change_type}**, test coverage is recommended to prevent regressions.

**Suggested test locations**:
- Unit tests: `{package_dir}/{suggested_test_file}`
- E2E tests: consider adding a case under `[sig-{sig}]` in openshift-tests

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

@{pr_author} — please consider adding test coverage for this change.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

#### 7d. No new tests BUT existing tests cover the change

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Change type**: {dependency_bump|refactor|config}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

None. No test files were added or modified in this PR.

#### Existing Tests (already in repo)

The change is covered by pre-existing test infrastructure:

| Test File / Name | Package | Covers |
| --- | --- | --- |
| `{existing_test_file}` | `{package}` | Functions in same package |
| `{e2e_test_name}` | e2e | Component-level coverage |

{If e2e results are available:}
- E2E test `{e2e_test_name}` — **PASSED** in `{job_name}` ([link]({prow_url}))

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

No new tests required — existing test infrastructure covers this change.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

**Label**: Label adding is disabled for initial testing. When ready, uncomment:
```bash
# gh pr edit "$downstream_pr_url" --add-label "verified"
```

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
