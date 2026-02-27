# CI Plugin

A plugin for working with OpenShift CI infrastructure, providing
commands to analyze CI workflow,chain or data, investigate failures, and understand
release quality.

## Commands

### e2e-retest

Find and retest failed e2e CI jobs on a pull request (fast, focused version).

**Usage:**
```bash
# Auto-detect repo from current directory
/ci:e2e-retest <pr-number>

# Specify repo name (assumes openshift org)
/ci:e2e-retest <repo> <pr-number>

# Specify full org/repo
/ci:e2e-retest <org>/<repo> <pr-number>
```

**What it does:**
- Analyzes PR status checks to find failed e2e jobs
- Parses prow history to count consecutive failures
- Shows recent job statistics (fail/pass/abort counts)
- Excludes currently running jobs from retest lists
- Provides interactive options to retest selected or all failed jobs
- Posts `/test` comments to GitHub

**Examples:**

1. **From within the repository**:
   ```bash
   cd ~/repos/ovn-kubernetes
   /ci:e2e-retest 2782
   ```

2. **From anywhere, with repo name**:
   ```bash
   /ci:e2e-retest ovn-kubernetes 2782
   ```

3. **With full org/repo**:
   ```bash
   /ci:e2e-retest openshift/origin 5432
   ```

**Retest Options:**
- **Retest selected**: Choose specific jobs to retest
- **Retest all failed**: Automatically retest all currently failing jobs
- **Use /retest**: Post a single `/retest` comment
- **Just show list**: Display failures without taking action

**Performance:**
- **Immediate execution**: Bash script starts in background while Claude reads command file
- **Phase 1 (Bash)**: Fetches PR status and prow history in parallel (~2-3 seconds)
- **Phase 2 (Claude)**: Displays results and handles interaction (~3-5 seconds)
- **Total time**: ~5-8 seconds from invocation to results

### payload-retest

Find and retest failed payload jobs on a pull request (fast, focused version).

**Usage:**
```bash
# Auto-detect repo from current directory
/ci:payload-retest <pr-number>

# Specify repo name (assumes openshift org)
/ci:payload-retest <repo> <pr-number>

# Specify full org/repo
/ci:payload-retest <org>/<repo> <pr-number>
```

**What it does:**
- Searches PR comments for all payload run URLs
- Fetches all payload pages in parallel
- Analyzes all runs to track each job's status over time
- For each job, finds its most recent status and counts consecutive failures
- Shows all currently failing jobs with consecutive failure counts
- Excludes currently running jobs from retest lists
- Provides interactive options to retest selected or all failed jobs
- Posts `/payload-job` comments to GitHub

**Examples:**

1. **From within the repository**:
   ```bash
   cd ~/repos/ovn-kubernetes
   /ci:payload-retest 2782
   ```

2. **From anywhere, with repo name**:
   ```bash
   /ci:payload-retest ovn-kubernetes 2782
   ```

3. **With full org/repo**:
   ```bash
   /ci:payload-retest openshift/origin 5432
   ```

**Retest Options:**
- **Retest selected**: Choose specific jobs to retest
- **Retest all failed**: Automatically retest all currently failing jobs
- **Just show list**: Display failures without taking action

**Performance:**
- **Immediate execution**: Bash script starts in background while Claude reads command file
- **Phase 1 (Bash)**: Fetches all payload pages in parallel and analyzes (~2-5 seconds)
- **Phase 2 (Claude)**: Displays results and handles interaction (~3-5 seconds)
- **Total time**: ~5-10 seconds from invocation to results

**Notes:**
- Payload jobs are OpenShift-specific and may not exist for all PRs
- Command gracefully exits if no payload runs found
- Analyzes ALL payload runs to track job history
- Handles jobs that don't appear in every run
- Counts consecutive failures across multiple runs

### pr-retest

Find and retest failed e2e CI jobs and payload jobs on a pull request (combined version).

**Usage:**
```bash
# Auto-detect repo from current directory
/ci:pr-retest <pr-number>

# Specify repo name (assumes openshift org)
/ci:pr-retest <repo> <pr-number>

# Specify full org/repo
/ci:pr-retest <org>/<repo> <pr-number>
```

**What it does:**
- Analyzes PR status checks to find failed e2e jobs
- Parses prow history to track consecutive failures
- Checks for failed payload jobs (if applicable)
- Excludes currently running jobs from retest lists
- Provides interactive options to retest selected or all failed jobs
- Posts `/test` or `/payload-job` comments to GitHub

**Examples:**

1. **From within the repository**:
   ```bash
   cd ~/repos/ovn-kubernetes
   /ci:pr-retest 2838
   ```

2. **From anywhere, with repo name**:
   ```bash
   /ci:pr-retest ovn-kubernetes 2838
   ```

3. **With full org/repo**:
   ```bash
   /ci:pr-retest openshift/origin 5432
   ```

**Retest Options:**
- **Retest selected**: Choose specific jobs to retest
- **Retest all failed**: Automatically retest all currently failing jobs
- **Use /retest**: Post a single `/retest` comment (e2e jobs only)
- **Just show list**: Display failures without taking action

**Performance:**
- **Immediate execution**: Both bash scripts start in background while Claude reads command file
- **Phase 1 (Bash)**: Fetches e2e and payload data in parallel (~3-5 seconds, overlapped)
- **Phase 2 (Claude)**: Displays results and handles interaction for both sections (~5-10 seconds)
- **Total time**: ~10-15 seconds from invocation to completion
- **Note**: For faster analysis of just e2e or just payload, use `/ci:e2e-retest` or `/ci:payload-retest`

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

### list-step
Lists all step references (ref) used in a specified workflow or chain.

**Prerequisites:**

Run this command from your local clone of the openshift/release repository.

**Usage:**
```bash
/list-step
```
**Arguments:**
- workflow-name (e.g., `hypershift-aws-e2e-external`)

or 
- chain-name(e.g., `rosa-cluster-provision-chain`)

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

### analyze-prow-job-test-failure

Analyze a failed test by inspecting test code and Prow CI job artifacts.

**Usage:**
```bash
/ci:analyze-prow-job-test-failure <prowjob-url> <test-name>
```

### analyze-prow-job-install-failure

Analyze OpenShift installation failures in Prow CI jobs by examining installer logs, log bundles, and sosreports.

**Usage:**
```bash
/ci:analyze-prow-job-install-failure <prowjob-url>
```

### analyze-prow-job-resource

Analyze Kubernetes resource lifecycle in Prow job artifacts. Generates interactive HTML reports with timeline visualization.

**Usage:**
```bash
/ci:analyze-prow-job-resource <prowjob-url> [namespace:][kind/][resource-name]
```

### extract-prow-job-must-gather

Extract and decompress must-gather archives from Prow job artifacts into an interactive HTML file browser.

**Usage:**
```bash
/ci:extract-prow-job-must-gather <prowjob-url>
```

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
