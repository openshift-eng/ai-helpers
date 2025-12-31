---
description: Discover which OpenShift CI jobs will run tests based on test labels
argument-hint: <test-input> [job-filter]
---

## Name
ci:analyze-test-coverage

## Synopsis
```
/ci:analyze-test-coverage <test-input> [job-filter]
```

## Description
The `ci:analyze-test-coverage` command helps developers and QE engineers **discover which OpenShift CI jobs** their tests will be executed in by analyzing test labels (Ginkgo tags).

This command answers:
- **Which CI jobs will run my test?**
- **Which jobs WON'T run my test and why?**
- **What test suite tags do I need to add to run in more jobs?**

**Important:** For new tests, it is **NOT recommended** to add them to blocking jobs immediately. New tests should start in optional/informing jobs, prove stability over 2-4 weeks (>98% pass rate), and only then be promoted to blocking jobs.

## Arguments
- `$1` (test-input): **Required.** PR URL/number, test file path, or test labels
  - **PR URL:** `https://github.com/openshift/origin/pull/12345` (analyzes all test files in PR)
  - **PR shorthand:** `openshift/origin#12345` or `#12345` (assumes openshift/origin)
  - **Test file:** `test/extended/cli/mustgather.go` (extracts labels from file)
  - **Test labels:** `"[sig-cli][Feature:CLI]"` (uses labels directly)
- `$2` (job-filter): **Optional.** Filter to limit which jobs to analyze
  - If not provided, analyzes **all blocking jobs** for the latest release
  - Example: `4.21` (analyzes all 4.21 jobs)
  - Example: `nightly-blocking` (analyzes nightly blocking jobs)
  - Example: `periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial` (specific job)
  - Example: `jobs.txt` (file containing job names, one per line)

## Implementation

This command uses the **analyze-test-coverage** skill to perform complex analysis.

**You MUST invoke the skill immediately:**
```
Skill: analyze-test-coverage
```

The skill will:
1. Validate prerequisites (Python, required tools, repositories)
2. Auto-detect openshift/origin and openshift/release repositories
3. Extract test labels from Go files (using `extract_test_labels.py`)
4. Parse test suite definitions (using `parse_suites.py`)
5. Analyze CI job configurations (using `analyze_job.py`)
6. Match test labels against suite filters
7. Generate comprehensive analysis report with recommendations

### Key Principle

The skill emphasizes that **new tests should NOT be added to blocking jobs initially**. Instead:
- Start in optional/informing jobs
- Monitor stability over 2-4 weeks
- Achieve >98% pass rate
- Only then consider adding conformance tags for blocking jobs

## Return Value
- **Format:** Markdown report with detailed analysis
- **Contains:**
  - Summary (jobs that will/won't run tests)
  - Test labels found
  - Per-job analysis with reasons
  - Actionable recommendations
  - Suite reference guide

## Examples

### Example 1: Analyze PR to discover which jobs will run its tests

```bash
/ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345
```

**What it does:**
- Fetches all changed files from the PR
- Identifies test files (files ending in `_test.go`)
- Extracts test labels from all test files
- Analyzes **all blocking jobs** to discover which will run the tests

**Expected Output:**
```markdown
# Test Coverage Analysis Report

Analyzing PR: openshift/origin#12345
Found test files in PR:
  - test/extended/cli/new_feature_test.go
  - test/integration/api/api_test.go

Extracted labels from PR:
  - [sig-cli]
  - [Feature:NewFeature]
  - [apigroup:config.openshift.io]

Analyzed: 45 blocking jobs across all release versions
Test labels: [sig-cli], [Feature:NewFeature], [apigroup:config.openshift.io]

## Summary
- ✅ Tests WILL run in: 0 jobs
- ❌ Tests WILL NOT run in: 45 jobs

## Recommendations
**For new tests, it is NOT recommended to add them to blocking jobs immediately.**
...
```

### Example 2: Analyze PR with shorthand syntax

```bash
/ci:analyze-test-coverage openshift/origin#12345
# or even shorter (assumes openshift/origin):
/ci:analyze-test-coverage #12345
```

**What it does:** Same as Example 1, but with shorter syntax.

### Example 3: Analyze PR for specific release version

```bash
/ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345 4.21
```

**What it does:**
- Fetches test files from PR
- Extracts labels
- Analyzes only 4.21 jobs (instead of all blocking jobs)

### Example 4: Discover which jobs will run a test file (default: all blocking jobs)

```bash
/ci:analyze-test-coverage test/extended/cli/mustgather.go
```

**What it does:** Analyzes **all blocking jobs** to discover which ones will run the test.

**Expected Output:**
```markdown
# Test Coverage Analysis Report

Analyzed: 45 blocking jobs across all release versions
Test labels: [sig-cli], [apigroup:config.openshift.io]

## Summary
- ✅ Tests WILL run in: 0 jobs
- ❌ Tests WILL NOT run in: 45 jobs

## Jobs That WILL Run This Test
(none)

## Jobs That WILL NOT Run This Test
All 45 blocking jobs will NOT run this test because it lacks conformance tags.

### Why Tests Don't Run
Missing required tags:
- [Suite:openshift/conformance/parallel] - for parallel blocking jobs
- [Suite:openshift/conformance/serial] - for serial blocking jobs

## Recommendations
**For new tests, it is NOT recommended to add them to blocking jobs immediately.**
Create or use optional CI jobs instead...
```

### Example 5: Discover jobs for a specific release version

```bash
/ci:analyze-test-coverage "[sig-cli][Feature:CLI]" 4.21
```

**What it does:** Analyzes all 4.21 jobs to find which ones will run the test.

**Expected Output:**
```markdown
# Test Coverage Analysis Report

Analyzed: 23 jobs for release 4.21
Test labels: [sig-cli], [Feature:CLI]

## Jobs That WILL Run This Test (0)
(none)

## Jobs That WILL NOT Run This Test (23)
- periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn (needs [Suite:openshift/conformance/parallel])
- periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial (needs [Suite:openshift/conformance/serial])
...
```

### Example 6: Check if a specific job will run your test

```bash
/ci:analyze-test-coverage "[sig-network][Suite:openshift/conformance/serial]" periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial
```

**Expected Output:**
```markdown
## Summary
- ✅ Tests WILL run in: 1 job

### ✅ periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-serial

**Test Suite:** openshift/conformance/serial
**Result:** ✅ Tests WILL RUN
**Reason:** Test has required tag [Suite:openshift/conformance/serial]
```

### Example 7: Analyze nightly blocking jobs

```bash
/ci:analyze-test-coverage test/extended/builds/build.go nightly-blocking
```

**What it does:** Scans only nightly blocking jobs to discover coverage.

## Notes

- Analysis is based on current main branch configurations
- Some jobs may have dynamic TEST_SUITE overrides not captured
- Upgrade jobs typically run only conformance-tagged tests
- The skill uses helper scripts (`extract_test_labels.py`, `parse_suites.py`, `analyze_job.py`)

## Related Commands

- `/ci:ask-sippy` - Query test history and stability
- `/ci:list-unstable-tests` - Find flaky tests
- `/ci:query-test-result` - Check specific test results
