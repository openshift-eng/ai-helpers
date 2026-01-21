# CI Plugin

A plugin for working with OpenShift CI infrastructure, providing
commands to analyze CI data, investigate failures, and understand
release quality.

## Commands

### ask-sippy

Query the Sippy Chat AI agent for CI/CD data analysis.  Sippy Chat has a
[web interface](https://sippy-auth.dptools.openshift.org/sippy-ng/chat)
available as well.

**Note:** Each query is independent with no conversation history
maintained between calls. Use the web interface for longer sessions
requiring more context.

Thinking steps are not currently streamed, so it may take some time to
appear to get a result, 10-60 seconds in most cases.

**Usage:**
```bash
/ask-sippy [question]
```

**What it does:**
- Analyzes OpenShift release payloads and rejection reasons
- Investigates CI job failures and patterns
- Examines test failures, flakes, and regressions
- Provides CI health trends and comparisons
- Delivers release quality metrics

**Prerequisites:**

You need to set a token for Sippy's authenticated instance. You can
obtain the OAuth token by visiting
[api.ci](https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/k8s/cluster/projects)
and logging in with SSO, and displaying your API token (sha256~<something>).

```bash
export ASK_SIPPY_API_TOKEN='your-token-here'
```

**Examples:**

1. **Payload investigation:**
   ```bash
   /ask-sippy Why was the latest 4.21 payload rejected?
   ```

2. **Test failure analysis:**
   ```bash
   /ask-sippy What are the most common test failures in e2e-aws this week?
   ```

3. **CI health check:**
   ```bash
   /ask-sippy How is the overall CI health for 4.20 compared to last week?
   ```

4. **Specific test inquiry:**
   ```bash
   /ask-sippy Why is the test "sig-network Feature:SCTP should create a Pod with SCTP HostPort" failing?
   ```

### analyze-test-coverage

**Discover which OpenShift CI jobs** will run your tests based on test labels (Ginkgo tags).

**Goal:** Help developers and QE engineers determine which CI jobs their tests will be executed in by analyzing test labels. **Important:** For new tests, it is NOT recommended to add them to blocking jobs immediately. New tests should start in optional jobs, prove stability (>98% pass rate over 2-4 weeks), and only then be promoted to blocking jobs.

**Usage:**
```bash
/ci:analyze-test-coverage <test-input> [job-filter]
```

**What it does:**
- Extracts test labels from Go test files
- **Discovers which CI jobs** will run the tests (default: all blocking jobs)
- Identifies missing conformance suite tags
- Explains why tests are excluded from specific jobs
- Provides actionable recommendations (emphasizing optional jobs for new tests)

**Prerequisites:**
- Python 3.6+ with PyYAML (`pip install pyyaml`)
- Local clones of openshift/origin and openshift/release repositories
  - Auto-detected from common locations
  - Can be specified via `ORIGIN_REPO` and `RELEASE_REPO` environment variables

**Arguments:**
- `<test-input>`: **Required.** PR URL/number, test file path, or test labels
  - **PR URL:** `https://github.com/openshift/origin/pull/12345` (analyzes all test files in PR)
  - **PR shorthand:** `openshift/origin#12345` or `#12345` (assumes openshift/origin)
  - **Test file:** `test/extended/cli/mustgather.go` (extracts labels from file)
  - **Test labels:** `"[sig-cli][Feature:CLI]"` (uses labels directly)
- `[job-filter]`: **Optional.** Filter to narrow down job discovery
  - **If omitted:** Analyzes all blocking jobs (default)
  - Example: `4.21` (all 4.21 jobs)
  - Example: `nightly-blocking` (only nightly blocking jobs)
  - Example: `periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn` (specific job)
  - Example: `jobs.txt` (file with job names, one per line)

**Examples:**

1. **Analyze a PR to discover which jobs will run its tests:**
   ```bash
   /ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345
   ```
   Output: Fetches test files from PR, extracts labels, shows which blocking jobs will run them

2. **Analyze PR with shorthand syntax:**
   ```bash
   /ci:analyze-test-coverage openshift/origin#12345
   # or simply:
   /ci:analyze-test-coverage #12345
   ```
   Output: Same as example 1, assumes openshift/origin repo

3. **Analyze PR for specific release version:**
   ```bash
   /ci:analyze-test-coverage https://github.com/openshift/origin/pull/12345 4.21
   ```
   Output: Shows which 4.21 jobs will run the PR's tests

4. **Discover which blocking jobs will run your test file:**
   ```bash
   /ci:analyze-test-coverage test/extended/cli/mustgather.go
   ```
   Output: Lists all blocking jobs that will/won't run the test

5. **Discover which 4.21 jobs will run your test:**
   ```bash
   /ci:analyze-test-coverage "[sig-cli][Feature:CLI]" 4.21
   ```
   Output: Shows all 4.21 jobs and whether they'll run the test

6. **Check if a specific job will run your test:**
   ```bash
   /ci:analyze-test-coverage test/extended/builds/build.go periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn
   ```
   Output: Analyzes just that one job

**Output:**
- Comprehensive markdown report showing:
  - **Jobs that WILL run the test** (with reasons)
  - **Jobs that WON'T run the test** (with reasons)
  - Test labels found
  - Missing tags needed for coverage
  - Recommendations (emphasizing optional jobs for new tests)
  - Suite reference guide

**Key Recommendation:**
If tests won't run in any blocking jobs, the command recommends creating or using **optional CI jobs** for new tests rather than adding conformance tags immediately. Only add conformance tags to run in blocking jobs after tests have proven stable.

### trigger-periodic

Trigger a periodic gangway job with optional environment variable overrides.

**Prerequisites:** Authentication to app.ci cluster (see Configuration)

**Usage:**
```bash
/trigger-periodic
```

**Arguments (interactive):**
- Job name (e.g., `periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn`)
- Optional environment variable overrides

### trigger-postsubmit

Trigger a postsubmit gangway job with repository refs.

**Prerequisites:** Authentication to app.ci cluster (see Configuration)

**Usage:**
```bash
/trigger-postsubmit
```

**Arguments (interactive):**
- Job name (e.g., `branch-ci-openshift-assisted-installer-release-4.12-images`)
- Repository organization (e.g., `openshift`)
- Repository name (e.g., `assisted-installer`)
- Base ref/branch (e.g., `release-4.12`)
- Base SHA (commit hash)
- Repository link
- Optional base link (comparison URL)
- Optional environment variable overrides

### trigger-presubmit

Trigger a presubmit gangway job.

**Prerequisites:** Authentication to app.ci cluster (see Configuration)

**Usage:**
```bash
/trigger-presubmit
```

**WARNING:** Presubmit jobs should typically be triggered using GitHub Prow commands (`/test`, `/retest`). Only use this if you have a specific reason to trigger via REST API.

**Arguments (interactive):**
- Job name
- Pull request information (org, repo, base ref, PR number, SHAs)
- Optional environment variable overrides

### query-job-status

Query the status of a gangway job execution by ID.

**Prerequisites:** Authentication to app.ci cluster (see Configuration)

**Usage:**
```bash
/query-job-status
```

**Arguments (interactive):**
- Execution ID (returned when a job is triggered)

**Returns:**
- Job name, type, and status (SUCCESS, FAILURE, PENDING, RUNNING, ABORTED)
- GCS path to artifacts (if available)

## Configuration

### Authentication for Gangway Commands

Gangway commands require authentication to the app.ci cluster:

1. Visit https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
2. Log in with SSO and click "Copy login command"
3. Execute the `oc login` command in your terminal

Verify with: `oc whoami`

## Additional Resources

- [Sippy Chat Web Interface](https://sippy-auth.dptools.openshift.org/sippy-ng/chat)
- [Triggering ProwJobs via REST](https://docs.ci.openshift.org/docs/how-tos/triggering-prowjobs-via-rest/)
- [Gangway CLI](https://github.com/openshift-eng/gangway-cli)
