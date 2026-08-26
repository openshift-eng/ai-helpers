# CI Plugin

A plugin for working with OpenShift CI infrastructure, providing
commands to analyze CI workflow,chain or data, investigate failures, and understand
release quality.

## User-Invocable Skills

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
- Job name, type, and status (TRIGGERED, PENDING, SUCCESS, FAILURE, ABORTED)
- GCS path to artifacts (if available)

### detect-permafail

Detect permafail patterns in consecutive job failures to distinguish systematic failures from flaky failures.

**Usage:**
```bash
/ci:detect-permafail --job-urls="[url1,url2,...]" --job-name="job-name" --pr="owner/repo#123"
```

**Arguments:**
- `--job-urls`: JSON array of 2-10 consecutive Prow job URLs (newest first)
- `--job-name`: Name of the job being analyzed
- `--pr`: PR identifier (format: "owner/repo#number")

**What it does:**
- Analyzes 2-10 consecutive failures to determine if they represent a permafail
- Uses artifact-based classification (test vs infrastructure failures)
- Applies thresholds based on comparable run count (same failure type)
- Example: 7 runs where 4 are test failures and all 4 have same test → detects permafail (4/4 = 100% ≥ 80% threshold)
- Returns JSON with permafail verdict, confidence score, and failure signatures

### extract-kubeconfig

Extract kubeconfig from a running rehearsal/CI job in a GitHub PR. Checks step status to verify the cluster is ready, then connects to the build cluster to extract the kubeconfig from the running pod. Supports both standard and HyperShift (nested kubeconfig) clusters, and both public (`prow.ci.openshift.org`) and private (`qe-private-deck`) jobs.

**Prerequisites:** `gh` and `oc` CLI tools required. `gsutil` is optional — when unavailable, the command falls back to finding the build cluster from the job config in the repo. You should be the PR author.

**Usage:**
```bash
/ci:extract-kubeconfig <pr-url>
```

**Arguments:**
- PR URL (e.g., `https://github.com/openshift/release/pull/75742`)

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
