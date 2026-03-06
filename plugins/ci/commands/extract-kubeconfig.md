---
description: Extract kubeconfig from a running CI job in a PR
argument-hint: <pr-url>
---

## Name
ci:extract-kubeconfig

## Synopsis
```bash
/ci:extract-kubeconfig <pr-url>
```

## Description

The `ci:extract-kubeconfig` command extracts the kubeconfig from a running rehearsal/CI job in a GitHub PR. It checks the job's step status to determine if the cluster is ready, then connects to the build cluster to extract the kubeconfig from the running pod.

The command accepts:
- **PR URL** (required): GitHub PR URL in the `openshift/release` repository

**What it does:**
1. Validates the PR URL and checks ownership
2. Finds running (PENDING) jobs on the PR
3. Determines the build cluster (via GCS for public jobs, or via job config in the repo for qe-private-deck jobs)
4. Logs into the build cluster and finds the CI namespace
5. Checks step status via pod statuses to verify the cluster is ready
6. Extracts the kubeconfig (and nested kubeconfig for HyperShift) from the running pod
7. Verifies cluster health and reports results

**Key features:**
- Supports both standard and HyperShift (nested kubeconfig) clusters
- Supports both public (`prow.ci.openshift.org`) and private (`qe-private-deck`) jobs
- Uses ci-op namespace prefix on kubeconfig filenames to support multiple concurrent extractions
- Warns if you're not the PR author (may lack namespace access)
- Recognizes `wait` steps as valid running states for extraction

## Prerequisites

1. **GitHub CLI (`gh`)**
   - Check if installed: `which gh`
   - Must be authenticated: `gh auth status`

2. **OpenShift CLI (`oc`)**
   - Check if installed: `which oc`
   - Used to login to build clusters and extract kubeconfig

3. **Google Cloud Storage (`gsutil`)** (optional)
   - Check if installed: `which gsutil`
   - No authentication needed (test-platform-results bucket is public)
   - If not installed, the command falls back to finding the build cluster from the job config in the openshift/release repo

4. **PR in openshift/release repository**
   - The command only supports PRs in the `openshift/release` repository
   - You should be the PR author to have access to the CI namespace on the build cluster

## Implementation

The command performs the following steps:

### Step 1: Validate PR URL

Parse the PR URL to extract the org, repo, and PR number. The URL should match the format `https://github.com/<org>/<repo>/pull/<number>`.

If the repo is NOT `openshift/release`, warn the user and stop.

### Step 2: Check PR Ownership

Fetch the PR author and compare with the current GitHub user:

```bash
gh pr view <number> --repo openshift/release --json author --jq '.author.login'
gh api user --jq '.login'
```

If the PR author does NOT match the current user, warn: "You are not the author of this PR. You may not have access to the CI namespace on the build cluster to extract the kubeconfig." Ask the user if they want to continue. Stop if they say no.

### Step 3: Find Running Jobs

Fetch the PR status checks:

```bash
gh pr view <number> --repo openshift/release --json title,state,statusCheckRollup > /tmp/pr-checks.json
```

Parse the JSON to find checks with `state: PENDING` (these use `__typename: StatusContext` with fields `context`, `state`, `targetUrl`). Exclude the `tide` check.

- If multiple running jobs found, list them and ask the user which one to use.
- If exactly one running job found, use it automatically.
- If no running jobs found, report that and stop.

### Step 4: Determine the Build Cluster

From the matching check, extract the `targetUrl` which points to the Prow job page. Determine the build cluster using one of two methods:

**Method A — Via GCS prowjob.json** (preferred when `gsutil` is installed and the job uses public `prow.ci.openshift.org`):

Parse the GCS path from `targetUrl`:
- Format: `https://prow.ci.openshift.org/view/gs/test-platform-results/.../<build_id>`
- Extract the GCS base: `gs://test-platform-results/.../<build_id>`
- Download `prowjob.json` and extract `spec.cluster`:
  ```bash
  gsutil cp "<gcs_base>/prowjob.json" /tmp/prowjob.json
  ```

**Method B — Via job config in openshift/release repo** (fallback when `gsutil` is not installed, or when the job uses `qe-private-deck`):

Find the build cluster from the generated job config in the openshift/release repo using the PR's fork and branch:

1. Get the PR's head ref info:
   ```bash
   gh pr view <number> --repo openshift/release --json headRefName,headRepository,headRepositoryOwner
   ```

2. Determine the original job name. For rehearsal jobs, the check context is like `ci/rehearse/periodic-ci-<org>-<repo>-...`. Strip the `ci/rehearse/` prefix to get the rehearsal job name, then strip `rehearse-<pr_number>-` to get the original job name.

3. Parse the org from the original job name (first segment after `periodic-ci-` or `pull-ci-`).

4. List repo directories under `ci-operator/jobs/<org>/` via the GitHub Contents API on the PR's fork/branch:
   ```bash
   gh api "repos/<owner>/<repo>/contents/ci-operator/jobs/<org>?ref=<branch>" --jq '.[].name'
   ```
   Match the longest directory name that is a prefix of the job name remainder (after stripping `periodic-ci-<org>-`).

5. List files in that directory matching `*-periodics.yaml` and download the matching file via raw URL:
   ```bash
   curl -sL "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/ci-operator/jobs/<org>/<repo_dir>/<periodics_file>" \
     | grep -B 30 "name: <original_job_name>" | grep "cluster:"
   ```

### Step 5: Login to the Build Cluster

Check if a context for the build cluster already exists:

```bash
oc config get-contexts | grep <cluster>
```

If a context exists, use `--context=<context_name>` for all subsequent `oc` commands instead of switching the current context. This avoids issues with `oc login --web` not persisting.

If no context exists, login:

```bash
oc login --server=https://api.<cluster>.ci.devcluster.openshift.com:6443 --web
```

Where `<cluster>` is the build cluster determined in Step 4.

### Step 6: Find CI Namespace

Use `oc get projects` and grep for the PR number and job name to find the ci-op namespace:

```bash
oc [--context=<ctx>] get projects | grep "rehearse-<pr_number>-<job_name_suffix>"
```

The project display name includes the prow job name. For rehearsal jobs, this contains both the PR number and the job name, e.g.:
```text
ci-op-tk28ym3x    ci-op-tk28ym3x - rehearse-75742-periodic-ci-...    Active
```

Construct the grep pattern from the check context found in Step 3. The context is like `ci/rehearse/periodic-ci-openshift-...`. The rehearsal job name in the project description is `rehearse-<pr_number>-periodic-ci-openshift-...`. So grep with both the PR number and enough of the job name to be unique.

### Step 7: Check Step Status via Pods

List pods in the namespace to determine step status:

```bash
oc [--context=<ctx>] get pods -n <namespace>
```

Each pod name corresponds to a step in the job. Pod statuses indicate step progress:
- `Completed` — step finished successfully
- `Running` — step is currently executing
- `Error` — step failed

Report the status of all steps/pods. If any pod shows `Error` status, report the failure and stop.

Determine if the pre phase has completed by checking that setup/provisioning pods (names containing `setup`, `install`, `create`, `provision`) show `Completed` status, and there is a currently `Running` pod (typically a test step or a `wait` step).

### Step 8: Extract Kubeconfig

Find a pod that is in `Running` status.

Use the ci-op namespace as a prefix for kubeconfig filenames to avoid collisions when extracting from multiple jobs.

Extract the kubeconfig:
```bash
oc [--context=<ctx>] exec -n <namespace> <running_pod> -c test -- cat /tmp/secret/kubeconfig > /tmp/<namespace>-kubeconfig.yaml
```

Also check for nested kubeconfig (for HyperShift/hosted clusters):
```bash
oc [--context=<ctx>] exec -n <namespace> <running_pod> -c test -- ls /tmp/secret/nested_kubeconfig 2>/dev/null
```

If `nested_kubeconfig` exists, extract it too:
```bash
oc [--context=<ctx>] exec -n <namespace> <running_pod> -c test -- cat /tmp/secret/nested_kubeconfig > /tmp/<namespace>-nested-kubeconfig.yaml
```

### Step 9: Verify and Report

Test the kubeconfig(s):
```bash
KUBECONFIG=/tmp/<namespace>-kubeconfig.yaml oc get nodes
KUBECONFIG=/tmp/<namespace>-kubeconfig.yaml oc get co
```

If nested kubeconfig exists:
```bash
KUBECONFIG=/tmp/<namespace>-nested-kubeconfig.yaml oc get nodes
KUBECONFIG=/tmp/<namespace>-nested-kubeconfig.yaml oc get co
```

## Return Value

- **Success**: Kubeconfig file(s) extracted and cluster health report displayed
- **Error**: Error message explaining the issue (no running jobs, cluster not ready, etc.)

Report includes:
- PR title and number
- Job name and Prow URL
- Build cluster and CI namespace
- Step status summary (which completed, which is running)
- Management cluster kubeconfig path and node/CO health summary
- If nested kubeconfig found: hosted cluster kubeconfig path, platform, and node/CO health summary
- Instructions for using the kubeconfig(s)

## Examples

1. **Extract kubeconfig from a running rehearsal job**:
   ```bash
   /ci:extract-kubeconfig https://github.com/openshift/release/pull/75742
   ```
   Expected output:
   - Finds the running rehearsal job
   - Verifies pre phase steps passed
   - Extracts kubeconfig from test pod on build10
   - Reports: 3 master nodes, 4 workers, 34 COs healthy

2. **Extract kubeconfig from a HyperShift job (with nested kubeconfig)**:
   ```bash
   /ci:extract-kubeconfig https://github.com/openshift/release/pull/75716
   ```
   Expected output:
   - Extracts both management and hosted cluster kubeconfigs
   - Management cluster: 7 nodes, 34 COs
   - Hosted cluster: 3 nodes, 21 COs
   - Reports both kubeconfig paths

3. **PR with multiple running jobs**:
   ```bash
   /ci:extract-kubeconfig https://github.com/openshift/release/pull/12345
   ```
   Expected output:
   - Lists all running jobs
   - Asks user to select which job to extract from
   - Proceeds with selected job

## Notes

- **Kubeconfig expiry**: Extracted kubeconfig files become invalid when the CI job finishes. The credentials are tied to the ephemeral CI cluster and cannot be reused after the job completes.
- **PR ownership**: You must be the PR author to have access to the ci-op namespace on the build cluster. The command warns if you're not the author.
- **Private QE deck**: Jobs using `qe-private-deck` have inaccessible GCS artifacts. The command finds the build cluster from the job config in the openshift/release repo instead.
- **Build clusters**: OpenShift CI uses multiple build clusters (build01-build12). The command automatically determines which cluster from `prowjob.json` (when `gsutil` is available and the job is public) or from the job config YAML in the repo (fallback).
- **Context reuse**: If you've previously logged into a build cluster, the command reuses the existing context instead of requiring a new login.
- **Namespace discovery**: The ci-op namespace is found via `oc get projects` filtered by PR number and job name, which works reliably for running jobs.
- **Multiple extractions**: Kubeconfig files use the ci-op namespace as prefix (e.g., `/tmp/ci-op-abc123-kubeconfig.yaml`) to support extracting from multiple jobs without overwriting.
- **Wait steps**: Jobs with a `wait` step (used for debugging) are valid targets for kubeconfig extraction.

## Arguments

- **$1** (pr-url): GitHub PR URL in the openshift/release repository (required). Format: `https://github.com/openshift/release/pull/<number>`
