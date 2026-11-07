# Phases 1–3.5

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

