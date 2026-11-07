# CI Plugin

A plugin for working with OpenShift CI infrastructure, providing
commands to analyze CI workflow,chain or data, investigate failures, and understand
release quality.

## Commands

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

### analyze-prow-job-resource

Analyze Kubernetes resource lifecycle in Prow job artifacts. Generates interactive HTML reports with timeline visualization.

**Usage:**
```bash
/ci:analyze-prow-job-resource <prowjob-url> [namespace:][kind/][resource-name]
```

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

## MCP Server: openshift-ci-mcp

This plugin bundles the [openshift-ci-mcp](https://github.com/openshift-eng/openshift-ci-mcp)
server, which exposes OpenShift CI data directly as tools: Sippy, the Release Controller,
Search.CI, and Prow job history, runs, logs, and artifacts. Its tools are named
`mcp__plugin_ci_openshift-ci-mcp__<tool>`. The `prow-job-analysis` and `fetch-prowjob-json`
skills use the Prow tools when the server is running and fall back to gcloud or HTTPS
otherwise; plugins that depend on ci, such as ci-extras, use the same server.

**Prerequisites:** Go toolchain (`go` must be on your `PATH`). openshift-ci-mcp v0.6.0
requires Go 1.25.9 or newer; an older Go (1.21+) downloads that toolchain automatically
unless `GOTOOLCHAIN=local` is set, in which case the server cannot start. The server is
fetched and compiled on first use (about 20 seconds on a cold Go cache, longer when a
toolchain is downloaded) and then reused. The plugin pins openshift-ci-mcp v0.6.0, the
first release with the Prow tools and the release reviewed for this plugin; a newer
release is picked up by updating the version in `.mcp.json` after reviewing it.

**Private QE deck:** runs on `qe-private-deck` need an OpenShift OAuth token for the app.ci
cluster (a ServiceAccount token does not work). Log in as described under
[Authentication for Gangway Commands](#authentication-for-gangway-commands), then set the
token in the shell you start Claude Code from:

```bash
export OPENSHIFT_CI_TOKEN="$(oc whoami -t)"
```

The server inherits Claude Code's environment, so a token exported after Claude Code
started takes effect only after restarting Claude Code. The token is sent only to the
private deck's own hosts over HTTPS. It expires; a 401 from the Prow tools names
`OPENSHIFT_CI_TOKEN` when it needs renewing.

**Tools enabled by default:**

| Group | Tool | Description |
|-------|------|-------------|
| core | `get_releases` | OpenShift releases with availability and dev cycle dates |
| core | `get_release_health` | Health data for a release: success rates, variant summary, payload acceptance |
| core | `get_variants` | Variants and their possible values (arch, topology, platform, network) |
| core | `get_tool_fields` | Discover field names returned by a tool |
| payload | `get_payload_status` | Recent payload acceptance status from the Release Controller |
| payload | `get_payload_diff` | PR changes between payload tags |
| payload | `get_payload_test_failures` | Test failures for payload job runs |
| payload | `get_component_readiness` | Component readiness report for the current dev cycle |
| payload | `get_regressions` | Tests performing significantly worse than the previous release |
| payload | `get_regression_detail` | Regression detail with triages and Jiras |
| jobs | `get_job_report` | Job pass rates with filtering and pagination |
| jobs | `get_job_runs` | Results, timings, and risk analysis for recent job runs |
| jobs | `get_job_run_summary` | Test failures and cluster operator status for a single job run |
| tests | `get_ci_test_report` | Pass/fail/flake rates for tests with optional filtering |
| tests | `get_test_details` | Pass rates broken down by variant and job |
| tests | `get_recent_test_failures` | Tests that recently started failing |
| prs | `get_release_prs` | Pull requests for a specific release or presubmits |
| prs | `get_pr_impact` | Test failure impact for a specific PR (rate-limited: 20 req/hr) |
| search | `search_ci_logs` | Search logs and JUnit output across OpenShift CI |
| prow | `get_prow_job_history` | Runs of a Prow job, or of one PR, including presubmits and `/pj-rehearse` runs that Sippy does not track |
| prow | `get_prow_job_run` | Result, timing, refs, and per-step pass/fail with failure excerpts for one run |
| prow | `get_prow_artifacts` | Files and directories of a run, one directory per call |
| prow | `get_prow_artifact_content` | A run's build log, a step's build log, or any text artifact, with tail, head, or grep |

**Proxy tools (disabled by default):**

Raw API passthroughs to Sippy, the Release Controller, and search.ci. Enable with `ENABLE_PROXY_TOOLS=true`:

```bash
export ENABLE_PROXY_TOOLS=true
```

> **Note:** Restart the MCP server after setting this variable for the proxy tools to become available.

| Tool | Description |
|------|-------------|
| `sippy_api` | Raw passthrough to any Sippy API endpoint |
| `release_controller_api` | Raw passthrough to the Release Controller API |
| `search_ci_api` | Raw passthrough to the Search.CI API |

## Additional Resources

- [Triggering ProwJobs via REST](https://docs.ci.openshift.org/docs/how-tos/triggering-prowjobs-via-rest/)
- [Gangway CLI](https://github.com/openshift-eng/gangway-cli)
