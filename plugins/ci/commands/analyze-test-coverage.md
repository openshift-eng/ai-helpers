---
description: Analyze whether specific tests will be executed in OpenShift CI jobs
argument-hint: <job-names> [test-tags]
---

## Name
ci:analyze-test-coverage

## Synopsis
```
/ci:analyze-test-coverage <job-names> [test-tags]
```

## Description
The `ci:analyze-test-coverage` command analyzes whether specific tests will be executed in given OpenShift CI jobs by examining test suite configurations, test tags, and job definitions.

This command helps answer questions like:
- Will my test run in these CI jobs?
- Why isn't my test being executed in a specific job?
- Which CI jobs will run my test?
- What test suite tags do I need to add?

The analysis examines:
- Test suite definitions in `pkg/testsuites/standard_suites.go`
- Test tags (e.g., `[sig-cli]`, `[Suite:openshift/conformance/parallel]`)
- CI job configurations in the openshift/release repository
- Workflow and test step configurations

## Arguments
- `$1` (job-names): Comma-separated list of CI job names or a file containing job names (one per line)
  - Example: `periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial`
  - Example: `4.21-nightly-blocking-ci-jobs` (file path)
- `$2` (test-tags) [optional]: Test tags or test file path to analyze
  - Example: `[sig-cli]`
  - Example: `test/extended/cli/mustgather.go`
  - If not provided, analyzes general test suite coverage for the jobs

## Implementation

### Prerequisites

The command requires access to these repositories:
- **openshift/origin**: For test suite definitions and test files
- **openshift/release**: For CI job configurations

Claude will automatically locate these repositories or prompt for their paths.

### Analysis Steps

#### Step 1: Parse Job Names and Test Input

```bash
# Parse job names from comma-separated list or file
if [[ -f "$1" ]]; then
  mapfile -t JOBS < "$1"
else
  IFS=',' read -ra JOBS <<< "$1"
fi

# Parse test tags/file
TEST_INPUT="$2"
```

#### Step 2: Extract Test Tags

If a test file is provided, extract tags from test descriptions:

```bash
# Extract all tags from Ginkgo test descriptions
# Example: g.It("test name [sig-cli][Suite:openshift/conformance/parallel]", ...)
grep -oP '\[.*?\]' "$TEST_FILE" | sort -u
```

#### Step 3: Analyze Each CI Job

For each job, determine:

1. **Test Suite Used**:
   - Find job config in `ci-operator/config/openshift/release/`
   - Extract workflow name from job definition
   - Locate workflow in `ci-operator/step-registry/`
   - Extract `TEST_SUITE` environment variable

2. **Test Type** (upgrade vs suite):
   - Check job name patterns (`*upgrade*`, `*serial*`, etc.)
   - Determine if it runs `upgrade-conformance` or `suite`

3. **Suite Filter**:
   - Load suite definition from `pkg/testsuites/standard_suites.go`
   - Extract qualifier CEL expressions

#### Step 4: Match Tests Against Filters

Compare test tags with suite filters:

```go
// Example suite filters from standard_suites.go:

// openshift/conformance/parallel
Qualifiers: []string{
  "name.contains('[Suite:openshift/conformance/parallel')",
}

// openshift/conformance/serial
Qualifiers: []string{
  "name.contains('[Suite:openshift/conformance/serial')",
}

// openshift/build
Qualifiers: []string{
  "name.contains('[Feature:Builds]')",
}
```

#### Step 5: Generate Analysis Report

Produce structured markdown report with:
- Summary statistics
- Per-job analysis (will run / won't run)
- Detailed reasons and explanations
- Actionable recommendations

## Output Format

The command produces a comprehensive analysis report:

```markdown
# Test Coverage Analysis Report

Generated: 2024-12-15 19:30:00 UTC
Analyzing: 13 CI jobs

---

## Summary
- ✅ Tests WILL run in: 0 jobs
- ❌ Tests WILL NOT run in: 13 jobs
- Test tags analyzed: [sig-cli], [apigroup:config.openshift.io]

## Test Tags Found
- [sig-cli]
- [apigroup:config.openshift.io]
- [Timeout:20m]

**Missing conformance tags:**
- [Suite:openshift/conformance/parallel]
- [Suite:openshift/conformance/serial]

---

## Detailed Job Analysis

### ❌ periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial-1of2

**Test Suite:** openshift/conformance/serial
**Test Type:** suite (conformance)
**Workflow:** openshift-e2e-aws-ovn-serial

**Filter Expression:**
```
name.contains('[Suite:openshift/conformance/serial')
```

**Required Tags:**
- [Suite:openshift/conformance/serial]

**Result:** ❌ Tests WILL NOT RUN

**Reason:**
Tests are tagged with `[sig-cli]` but do not have the required `[Suite:openshift/conformance/serial]` tag. The conformance/serial suite only executes tests explicitly tagged for conformance testing.

**Recommendation:**
Add conformance suite tag to test descriptions:
```go
g.It("runs successfully [Suite:openshift/conformance/serial][sig-cli][apigroup:config.openshift.io]", func() {
```

---

### ❌ periodic-ci-openshift-release-master-ci-4.21-e2e-aws-upgrade-ovn-single-node

**Test Suite:** N/A (upgrade test)
**Test Type:** upgrade-conformance
**Workflow:** openshift-upgrade-aws-single-node

**Result:** ❌ Tests WILL NOT RUN

**Reason:**
This is an upgrade job that runs conformance tests after upgrade completes. Only tests tagged with conformance suite tags are included in post-upgrade validation.

**Recommendation:**
Add `[Suite:openshift/conformance/parallel]` to run in upgrade jobs:
```go
g.It("runs successfully [Suite:openshift/conformance/parallel][sig-cli]", func() {
```

---

## Test Suite Reference Guide

### openshift/conformance/parallel
- **Filter:** `name.contains('[Suite:openshift/conformance/parallel')`
- **Required Tag:** `[Suite:openshift/conformance/parallel]`
- **Parallelism:** 30 concurrent tests
- **Jobs using this:** 45+ jobs in 4.21
- **Purpose:** Fast parallel conformance validation

### openshift/conformance/serial
- **Filter:** `name.contains('[Suite:openshift/conformance/serial')`
- **Required Tag:** `[Suite:openshift/conformance/serial]`
- **Parallelism:** 1 (serial execution)
- **Jobs using this:** 12+ jobs in 4.21
- **Purpose:** Tests requiring serial execution (e.g., cluster-wide config changes)

### all
- **Filter:** `true` (matches everything)
- **Required Tag:** None (runs all tests)
- **Jobs using this:** Very few (resource intensive)

---

## Recommendations

### Option 1: Add Conformance Tags (Recommended)

To run in the existing 4.21 nightly blocking jobs, add conformance suite tags:

**For parallel execution:**
```go
g.It("runs successfully [Suite:openshift/conformance/parallel][sig-cli][apigroup:config.openshift.io]", func() {
```

**For serial execution:**
```go
g.It("runs audit logs [Suite:openshift/conformance/serial][sig-cli][apigroup:config.openshift.io]", func() {
```

### Option 2: Create Dedicated CI Jobs

Create jobs specifically for sig-cli tests:

```yaml
- as: e2e-aws-ovn-sig-cli
  interval: 168h
  steps:
    cluster_profile: aws-2
    workflow: openshift-e2e-aws-ovn
    env:
      TEST_SUITE: all
      TEST_ARGS: --ginkgo.focus='\[sig-cli\]'
```

### Option 3: Use TEST_ARGS in Existing Jobs

Some jobs support TEST_ARGS to override suite filtering. However, most nightly blocking jobs have fixed test suites for consistency.

---

## Key Insights

### Why Tests Don't Run

The most common reasons tests don't run in CI jobs:

1. **Missing conformance tags** (90% of cases)
   - Tests need explicit `[Suite:openshift/conformance/*]` tags
   - Sig tags alone (`[sig-cli]`) don't trigger inclusion

2. **Wrong suite tag for job type**
   - Parallel jobs need `[Suite:openshift/conformance/parallel]`
   - Serial jobs need `[Suite:openshift/conformance/serial]`

3. **Upgrade jobs are selective**
   - Only run conformance-tagged tests post-upgrade
   - Designed to validate cluster health, not all functionality

### Best Practices

1. **Tag tests appropriately from the start**
   - Add conformance tags during test development
   - Consider both parallel and serial execution needs

2. **Use parallel tags when possible**
   - Parallel tests run in more jobs (45+ vs 12+)
   - Faster feedback on PRs and nightlies

3. **Serial tags for disruptive tests**
   - Tests that modify cluster-wide config
   - Tests that can't run concurrently
   - Tests with shared resource dependencies

---
```

## Examples

### Example 1: Analyze must-gather tests in 4.21 nightly jobs

**Input:**
```bash
/ci:analyze-test-coverage 4.21-nightly-blocking-ci-jobs test/extended/cli/mustgather.go
```

Where `4.21-nightly-blocking-ci-jobs` contains:
```
periodic-ci-openshift-release-master-ci-4.21-e2e-aws-upgrade-ovn-single-node
periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-upgrade-fips
periodic-ci-openshift-release-master-ci-4.21-e2e-azure-ovn-upgrade
...
```

**Output:** Complete analysis showing tests won't run (no conformance tags)

### Example 2: Analyze specific test tags

**Input:**
```bash
/ci:analyze-test-coverage periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial "[sig-network][Suite:openshift/conformance/serial]"
```

**Output:** Analysis showing tests WILL run (has required tags)

### Example 3: Quick check for single job

**Input:**
```bash
/ci:analyze-test-coverage periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn "[Feature:Builds]"
```

**Output:** Analysis for builds tests in parallel job

## Practical Workflow

### Typical Usage Pattern

1. **Developer adds new test** to origin repository
2. **Runs analysis** to see which CI jobs will execute it
3. **Adds appropriate tags** based on recommendations
4. **Re-runs analysis** to verify coverage
5. **Submits PR** with properly tagged test

### Integration with Development

This command integrates with:
- **Pre-PR validation**: Check test coverage before submitting
- **PR reviews**: Reviewers verify test coverage
- **CI debugging**: Understand why tests aren't running
- **Test planning**: Design test suite coverage strategy

## Error Handling

The command handles:

- **Repository not found**: Auto-detects or prompts for paths
  ```
  Error: openshift/release repository not found
  Please specify path: export RELEASE_REPO=/path/to/release
  ```

- **Job not found**: Suggests similar job names
  ```
  Warning: Job 'e2e-aws-ovn-4.21' not found
  Did you mean:
  - periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn
  - periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn
  ```

- **Invalid test file**: Provides guidance
  ```
  Error: test/extended/cli/mustgather2.go not found
  Test files should be in test/extended/ directory
  ```

- **Ambiguous workflow**: Lists options
  ```
  Warning: Multiple workflows found for job
  Using: openshift-e2e-aws-ovn (most common)
  Alternatives: openshift-e2e-aws-ovn-serial
  ```

## Environment Variables

- `ORIGIN_REPO`: Path to openshift/origin (auto-detected: ~/github-go/openshift/origin, ~/go/src/github.com/openshift/origin)
- `RELEASE_REPO`: Path to openshift/release (auto-detected: ~/go/src/github.com/openshift/release)
- `VERBOSE`: Set to `1` for detailed debug output showing each analysis step

## Technical Implementation Details

### Test Suite Filter Matching

The command uses CEL (Common Expression Language) expression evaluation:

```python
# Example: Check if test matches filter
filter_expr = "name.contains('[Suite:openshift/conformance/parallel')"
test_name = "should create pod [Suite:openshift/conformance/parallel][sig-cli]"

# Evaluation
match = "[Suite:openshift/conformance/parallel" in test_name  # True
```

### Repository Structure Understanding

```
openshift/origin/
├── pkg/testsuites/
│   └── standard_suites.go      # Suite definitions
└── test/extended/
    └── cli/
        └── mustgather.go       # Test file

openshift/release/
├── ci-operator/
│   ├── config/openshift/release/
│   │   └── openshift-release-master__nightly-4.21.yaml
│   ├── jobs/openshift/release/
│   │   └── openshift-release-master-periodics.yaml
│   └── step-registry/
│       └── openshift/e2e/aws/ovn/
│           └── openshift-e2e-aws-ovn-workflow.yaml
```

### Performance Optimization

- **Caching**: Suite definitions cached after first load
- **Parallel processing**: Jobs analyzed concurrently when possible
- **Smart searching**: Uses grep/ripgrep for fast file searching
- **Result memoization**: Avoids re-analyzing same job+suite combinations

## Performance Characteristics

- **Single job analysis**: < 1 second
- **10 jobs**: 2-5 seconds
- **50+ jobs**: 10-20 seconds

## Related Commands

- `/ci:query-test-result` - Query historical test results
- `/ci:list-unstable-tests` - Find flaky tests
- `/ci:ask-sippy` - Ask AI about test/CI patterns
- `/openshift:review-test-cases` - Review test code quality
- `/openshift:new-e2e-test` - Create new E2E tests

## Notes

- Analysis is based on current main branch configurations
- Results may differ for PR-specific job configurations
- Some jobs have dynamic TEST_SUITE overrides not captured in static analysis
- Hypershift jobs may have different test suite behaviors

## Return Value
- **Exit 0**: Analysis completed successfully
- **Exit 1**: Error (missing repos, invalid args, etc.)
- **Stdout**: Markdown-formatted analysis report
- **Stderr**: Warnings and error messages
