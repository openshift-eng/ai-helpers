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

### analyze-payload

Analyze an OpenShift CI payload image to display component data and PRs included in the payload.

**Usage:**
```bash
/ci:analyze-payload <payload-image>
```

**What it does:**
- Extracts release version and metadata
- Lists all component versions (operators, controllers, etc.)
- Shows all images included in the payload with digests
- Displays architecture information
- Identifies pull requests (PRs) included in the payload via Sippy
- Provides release notes and upgrade information (if available)

**Prerequisites:**
- OpenShift CLI (`oc`) must be installed
- Network access to the registry containing the payload
- Network access to Sippy API (no authentication required)
- **For CI payloads** (registry.ci.openshift.org):
  - `oc login` to the app.ci cluster (required)
  - `oc registry login` to authenticate with the registry (required)

**Examples:**

1. **Analyze a standard release payload:**
   ```bash
   /ci:analyze-payload registry.ci.openshift.org/ocp/release:4.22.0-0.nightly-2025-12-23-042336
   ```

2. **Analyze a multi-arch payload:**
   ```bash
   /ci:analyze-payload quay.io/openshift-release-dev/ocp-release:4.22.0-0.nightly-multi-2025-12-22-191247
   ```

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
