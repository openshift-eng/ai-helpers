# Analyze Test Coverage Skill

This skill helps determine which OpenShift CI jobs will execute specific tests based on their Ginkgo test labels.

## Purpose

Developers and QE engineers often need to answer: **"Which CI jobs will run my test?"**

This skill provides that answer by:
1. Extracting test labels from Go test files
2. **Discovering CI jobs** (all blocking jobs by default, or filtered)
3. Analyzing job configurations and suite filters
4. Matching tests against each job's requirements
5. Providing actionable recommendations

## Key Principle

**For new tests, it is NOT recommended to add them to blocking jobs immediately.**

New tests should:
- Start in optional/informing jobs
- Prove stability over time (2-4 weeks, >98% pass rate)
- Demonstrate value and importance
- Only then be promoted to blocking jobs

## Helper Scripts

This skill includes three Python helper scripts:

### 1. `extract_test_labels.py`

Extracts Ginkgo test labels from Go test files.

**Usage:**
```bash
python3 extract_test_labels.py test/extended/cli/mustgather.go
```

**Output:**
```
Timeout:20m
apigroup:config.openshift.io
sig-cli
```

### 2. `parse_suites.py`

Parses test suite definitions from `pkg/testsuites/standard_suites.go`.

**Usage:**
```bash
python3 parse_suites.py /path/to/openshift/origin
```

**Output:**
```json
{
  "openshift/conformance/parallel": [
    "name.contains('[Suite:openshift/conformance/parallel')"
  ],
  "openshift/conformance/serial": [
    "name.contains('[Suite:openshift/conformance/serial')"
  ],
  "all": [
    "true"
  ]
}
```

### 3. `analyze_job.py`

Analyzes a CI job to determine which test suite it uses.

**Usage:**
```bash
python3 analyze_job.py /path/to/openshift/release periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn
```

**Output:**
```json
{
  "job_name": "periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn",
  "config_file": "ci-operator/jobs/openshift/release/openshift-release-master-periodics.yaml",
  "test_suite": "openshift/conformance/parallel",
  "workflow": "openshift-e2e-aws-ovn",
  "test_type": "suite"
}
```

## How It Works

1. **Locate Repositories** - Auto-detects openshift/origin and openshift/release
2. **Extract Labels** - Parses test files for Ginkgo labels like `[sig-cli]`
3. **Load Suite Definitions** - Reads suite filters from standard_suites.go
4. **Analyze Jobs** - For each job, determines the test suite used
5. **Match Tests** - Compares test labels against suite filters
6. **Generate Report** - Creates detailed analysis with recommendations

## Example Workflow

```bash
# 1. Developer adds new test to origin
vim test/extended/cli/new_feature.go

# 2. Discover which jobs will run this test
/ci:analyze-test-coverage test/extended/cli/new_feature.go

# 3. Review results
#    → Shows 0 blocking jobs will run (missing conformance tags)
#    → Lists all 45 blocking jobs that won't run it
#    → Recommends starting in optional jobs

# 4. Discover 4.21 job coverage specifically
/ci:analyze-test-coverage test/extended/cli/new_feature.go 4.21

# 5. Create or use optional job (not blocking)
# 6. Monitor stability over 2-4 weeks
# 7. If stable (>98% pass rate), consider adding conformance tags
# 8. Re-run discovery to verify coverage increase
```

## Common Test Suite Filters

| Suite Name | Filter Expression | Required Tag |
|------------|-------------------|--------------|
| `openshift/conformance/parallel` | `name.contains('[Suite:openshift/conformance/parallel')` | `[Suite:openshift/conformance/parallel]` |
| `openshift/conformance/serial` | `name.contains('[Suite:openshift/conformance/serial')` | `[Suite:openshift/conformance/serial]` |
| `openshift/build` | `name.contains('[Feature:Builds]')` | `[Feature:Builds]` |
| `all` | `true` | None (runs everything) |

## Best Practices

1. **New Tests Start Optional** - Don't add conformance tags immediately
2. **Prove Stability** - Let tests run in optional jobs for 2-4 weeks
3. **Monitor Pass Rates** - Aim for >98% pass rate before promoting
4. **Use Parallel When Possible** - Faster feedback, more jobs
5. **Reserve Serial for Special Cases** - Only for tests that must run alone

## Prerequisites

- Python 3.6+
- PyYAML (`pip install pyyaml`)
- Local clones of openshift/origin and openshift/release

## See Also

- [SKILL.md](SKILL.md) - Detailed implementation guide
- [../commands/analyze-test-coverage.md](../../commands/analyze-test-coverage.md) - Command documentation
