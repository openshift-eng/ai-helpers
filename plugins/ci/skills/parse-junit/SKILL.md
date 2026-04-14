---
name: Parse JUnit XML
description: Parse JUnit XML files from OpenShift CI jobs to extract test results, failure messages, lifecycle metadata, and aggregated run data
---

# Parse JUnit XML

This skill parses JUnit XML files produced by OpenShift CI test steps. It extracts test results including pass/fail/skip status, failure messages and output, the source test suite/binary, and test lifecycle (informing vs blocking). For aggregated JUnit files (from `release-analysis-aggregator`), it also parses the per-run YAML data embedded in `<system-out>`.

## When to Use This Skill

Use this skill when you need to:

- List failed, passed, or skipped tests from a CI job run
- Extract failure messages and output text for root cause analysis
- Get a test count summary (total / passed / failed / skipped)
- Identify which test binary or suite produced each test (e.g., `openshift-tests`, `openshift-tests-upgrade`)
- Determine test lifecycle — **informing** tests do not cause job failures on their own, but badly behaved informing tests could impact the cluster and are worth investigating as a potential cause of other failures
- Parse aggregated JUnit XML to get per-run pass/fail/skip data with Prow job URLs
- Filter tests by name pattern (e.g., all `sig-network` tests, all `BackendDisruption` tests)
- Parse gzip-compressed JUnit files (`.xml.gz`)
- Parse JUnit XML piped from `gcloud storage cat` or `curl`

## Prerequisites

1. **Python 3** (3.7 or later)
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

2. **JUnit XML files** — obtained from CI job artifacts, either:
   - Downloaded locally via `gcloud storage cp`
   - Piped via `gcloud storage cat` or `curl`

## Key Concepts

### Test Lifecycle: Informing vs Blocking

OpenShift CI tests have two lifecycle modes:

- **Blocking**: Test failures cause the job to fail. These are the primary signals for regression detection.
- **Informing**: Test failures are recorded but do **not** cause the job to fail on their own. However, badly behaved informing tests can still impact the cluster (e.g., by consuming excessive resources, creating conflicting objects, or destabilizing operators), so they are worth investigating as a potential cause of other failures.

The script auto-detects lifecycle from the JUnit filename and suite name (looking for "informing" in the path). You can also filter by lifecycle explicitly with `--lifecycle informing|blocking`.

### Test Source (Suite / Binary)

The `suite_name` field (from the `<testsuite name="...">` attribute) identifies which test binary produced the test. Common values:

- `openshift-tests` — the main e2e test binary from the payload
- `openshift-tests-upgrade` — upgrade-specific tests
- `BackendDisruption` — disruption monitoring tests
- Step names from `junit_operator.xml` (e.g., CI step-level pass/fail)

The `classname` field (from `<testcase classname="...">`) may contain additional package or grouping information.

### Aggregated JUnit

Aggregated jobs (e.g., `aggregated-*` jobs) run the same job multiple times and produce a `junit-aggregated.xml` file. Each `<testcase>` in this file has a `<system-out>` containing YAML-formatted data with per-run results:

```yaml
passes:
- jobRunID: "1234567890"
  humanURL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
  gcsArtifactURL: gs://test-platform-results/logs/...
failures:
- jobRunID: "0987654321"
  humanURL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
  gcsArtifactURL: gs://test-platform-results/logs/...
skips:
- ...
```

The script automatically parses this YAML and includes it in the output as the `aggregated` field (JSON) or inline in the summary/failures formats.

## Implementation Steps

### Step 1: Obtain JUnit XML Files

Download JUnit XML files from the CI job artifacts. Common locations:

```bash
# List all JUnit files for a job run
gcloud storage ls "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/{target}/**/junit*.xml"

# Download all JUnit files
gcloud storage cp "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/{target}/**/junit*.xml" \
  .work/{build_id}/junit/ --recursive --no-user-output-enabled

# For aggregated jobs, the aggregated JUnit is at:
# gs://test-platform-results/{bucket-path}/artifacts/release-analysis-aggregator/
#   openshift-release-analysis-aggregator/artifacts/release-analysis-aggregator/
#   {job-name}/{payload-tag}/junit-aggregated.xml
```

### Step 2: Run the Parser

```bash
script_path="plugins/ci/skills/parse-junit/parse_junit.py"

# Parse a single file (JSON output)
python3 "$script_path" junit.xml

# Parse multiple files
python3 "$script_path" .work/{build_id}/junit/junit*.xml

# Parse gzip-compressed file
python3 "$script_path" junit.xml.gz

# Parse from stdin (e.g., piped from GCS)
gcloud storage cat gs://test-platform-results/.../junit.xml | python3 "$script_path" --stdin

# Human-readable summary
python3 "$script_path" junit.xml --format summary

# Only failures with output text
python3 "$script_path" junit.xml --format failures --show-output

# Just test names
python3 "$script_path" junit.xml --format names

# Filter by name pattern
python3 "$script_path" junit.xml --filter "sig-network"
python3 "$script_path" junit.xml --filter "BackendDisruption"

# Filter by status
python3 "$script_path" junit.xml --status failed
python3 "$script_path" junit.xml --status "failed,error"

# Filter by lifecycle
python3 "$script_path" junit.xml --lifecycle informing --format failures

# Combine filters
python3 "$script_path" junit*.xml --filter "sig-network" --status failed --format failures --show-output
```

### Step 3: Use the Output

**JSON output** (default) returns a list of test result objects:

```bash
# Get just failed test names with jq
python3 "$script_path" junit.xml | jq -r '.[] | select(.status == "failed") | .name'

# Get failure messages
python3 "$script_path" junit.xml | jq '.[] | select(.status == "failed") | {name, failure_message, suite_name, lifecycle}'

# Count failures by suite
python3 "$script_path" junit.xml | jq '[.[] | select(.status == "failed")] | group_by(.suite_name) | map({suite: .[0].suite_name, count: length})'

# Get aggregated run URLs for a specific failed test
python3 "$script_path" junit-aggregated.xml --filter "specific test name" | jq '.[0].aggregated.failures[].humanURL'
```

## CLI Reference

```
python3 parse_junit.py [FILES...] [OPTIONS]

Positional:
  FILES                 JUnit XML file(s) to parse (.xml, .xml.gz)

Options:
  --stdin               Read JUnit XML from stdin (supports gzip)
  --format FORMAT       Output format: json (default), summary, failures, names
  --filter PATTERN      Filter tests by name (regex, case-insensitive)
  --status STATUS       Filter by status: passed,failed,error,skipped (comma-separated)
  --lifecycle MODE      Filter by lifecycle: informing or blocking
  --show-output         Include failure output text in summary/failures format
```

## Output Schema (JSON format)

```json
[
  {
    "name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]",
    "status": "failed",
    "suite_name": "openshift-tests",
    "classname": "openshift-tests",
    "time_seconds": 10.5,
    "lifecycle": "blocking",
    "source_file": "junit_e2e.xml",
    "failure_message": "expected X got Y",
    "failure_text": "full stack trace or output text...",
    "system_out": "raw system-out content if present",
    "aggregated": {
      "passes": [
        {"jobRunID": "123", "humanURL": "https://prow.ci.openshift.org/...", "gcsArtifactURL": "gs://..."}
      ],
      "failures": [
        {"jobRunID": "456", "humanURL": "https://prow.ci.openshift.org/...", "gcsArtifactURL": "gs://..."}
      ],
      "skips": []
    }
  }
]
```

**Key Fields:**

- `name`: Full test name including sig prefix and suite tags
- `status`: One of `passed`, `failed`, `error`, `skipped`
- `suite_name`: Test suite / binary that produced this test (from `<testsuite name="...">`)
- `classname`: Test class or package (from `<testcase classname="...">`)
- `time_seconds`: Test execution time
- `lifecycle`: `blocking` or `informing` — auto-detected from filename/suite, or set via `--lifecycle`
- `source_file`: Path of the JUnit XML file this test came from
- `failure_message`: Short failure description (from `<failure message="...">`)
- `failure_text`: Full failure output (from `<failure>` element text content)
- `error_message` / `error_text`: Same as failure fields but for `<error>` elements
- `skipped_message`: Reason for skipping (from `<skipped message="...">`)
- `system_out`: Raw `<system-out>` content
- `aggregated`: Only present for aggregated JUnit — contains per-run pass/fail/skip data with Prow URLs

Fields with empty values are omitted from JSON output to reduce noise.

## Error Handling

### Case 1: File Not Found

```
Error: File not found: /path/to/junit.xml
```

The script prints an error to stderr and continues processing other files.

### Case 2: Invalid XML

```
Error: Failed to parse XML from junit.xml: syntax error: line 42, column 5
```

The script prints an error to stderr and returns an empty result for that file.

### Case 3: No Results After Filtering

Returns `[]` (JSON), or a "No test results found." / "No test failures found." message in text formats.

### Case 4: Gzip Decompression Error

If a `.gz` file is corrupt, Python's gzip module raises an error. The script will print it to stderr.

**Exit Codes:**
- `0`: Success (even if no tests matched filters)
- `2`: Argument error (no files and no `--stdin`)

## Examples

### Example 1: Quick Failure Summary from a Job Run

```bash
# Download and parse all JUnit files from a job
gcloud storage cp "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/{target}/**/junit*.xml" \
  /tmp/junit/ --recursive --no-user-output-enabled 2>/dev/null

python3 plugins/ci/skills/parse-junit/parse_junit.py /tmp/junit/junit*.xml --format summary
```

### Example 2: Failures with Output Text

```bash
python3 plugins/ci/skills/parse-junit/parse_junit.py junit_e2e.xml --format failures --show-output
```

**Example output:**
```
Test Failures (3)
============================================================

[sig-network] Services should serve endpoints on same port and different protocols [Conformance]
  Source: openshift-tests
  Status: failed
  Lifecycle: blocking
  Message: timed out waiting for the condition
  Output:
    Expected service to be reachable on port 80/TCP and 80/UDP
    Timed out after 30s waiting for endpoints to be ready
    ...

[sig-storage] PersistentVolumes NFS should be mountable [INFORMING]
  Source: openshift-tests
  Status: failed
  Lifecycle: informing
  Message: mount failed: exit status 32
  Output:
    mount.nfs: access denied by server while mounting 10.0.0.1:/export
    ...

Note: 1 of 3 failure(s) are from informing tests.
Informing test failures do not cause job failures on their own,
but badly behaved informing tests could impact the cluster.
```

### Example 3: Parse Aggregated JUnit

```bash
gcloud storage cat "gs://test-platform-results/.../junit-aggregated.xml" | \
  python3 plugins/ci/skills/parse-junit/parse_junit.py --stdin --format failures --show-output
```

### Example 4: Filter Disruption Tests

```bash
python3 plugins/ci/skills/parse-junit/parse_junit.py junit*.xml \
  --filter "BackendDisruption" --status failed --format json
```

### Example 5: Pipe from GCS

```bash
gcloud storage cat gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/{target}/openshift-e2e-test/artifacts/junit/junit_e2e_*.xml.gz | \
  python3 plugins/ci/skills/parse-junit/parse_junit.py --stdin --format summary
```

### Example 6: Identify Informing vs Blocking Failures

```bash
# Show only informing test failures (these don't cause job failures)
python3 plugins/ci/skills/parse-junit/parse_junit.py junit*.xml \
  --lifecycle informing --status failed --format failures

# Show only blocking test failures (these DO cause job failures)
python3 plugins/ci/skills/parse-junit/parse_junit.py junit*.xml \
  --lifecycle blocking --status failed --format failures
```

## Notes

- The script uses only Python standard library — no pip dependencies
- Gzip-compressed files (`.xml.gz`) are handled transparently, both from disk and stdin
- Lifecycle detection is heuristic: the script looks for "informing" in the filename path or suite name. The authoritative source for informing vs blocking is the CI step configuration in the step registry, not the JUnit XML itself
- When parsing multiple files, results from all files are combined. Use `source_file` to identify which file each test came from
- The `suite_name` field is the best proxy for "which binary produced this test" — it comes from the `<testsuite name="...">` attribute. The actual container image is in `prowjob.json`, not in the JUnit XML
- For aggregated JUnit, `failure_message` contains the aggregation summary (e.g., "Passed 5 times, failed 3 times...") while `aggregated` contains the per-run URLs
- Empty fields are omitted from JSON output to keep it concise

## See Also

- Related Skill: `prow-job-analyze-test-failure` (downloads JUnit files and analyzes failures end-to-end)
- Related Skill: `fetch-test-report` (looks up test pass rates in Sippy — uses test name from JUnit)
- Related Skill: `fetch-test-runs` (fetches individual test run results from Sippy)
- Related Skill: `prow-job-artifact-search` (finds artifact files in a job's GCS bucket)
- Related Skill: `analyze-disruption` (specialized disruption analysis using interval/timeline data)
