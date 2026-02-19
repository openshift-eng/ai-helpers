---
name: Fetch ProwJob JSON
description: Fetch and return key data from a Prow job's prowjob.json artifact given a Prow job URL
---

# Fetch ProwJob JSON

This skill fetches the `prowjob.json` artifact for a given Prow job and returns key fields including job metadata, spec details, status, and release annotations.

## When to Use This Skill

Use this skill when you need to:

- Get metadata about a specific Prow job run (status, timing, cluster, pod name)
- Determine what payload a job was tested against (`release.openshift.io/tag`)
- Determine the upgrade source version for upgrade jobs (`release.openshift.io/from-tag`)
- Get the release images (`RELEASE_IMAGE_LATEST`, `RELEASE_IMAGE_INITIAL`) used in a job
- Check the ci-operator target and variant for a job
- Get the GCS bucket path for a job's artifacts

## Prerequisites

1. **Network Access**: Must be able to reach the GCS web proxy
   - Check: `curl -s -o /dev/null -w '%{http_code}' https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/`
   - No authentication required

## Implementation Steps

### Step 1: Parse the Prow Job URL

Extract the GCS path from the Prow job URL. Prow URLs follow this pattern:

```
https://prow.ci.openshift.org/view/gs/<bucket>/<path>/<job-name>/<build-id>
```

Extract everything after `/view/` to get the GCS reference:

```
gs/<bucket>/<path>/<job-name>/<build-id>
```

### Step 2: Construct the GCS Web URL

Convert the Prow URL to a gcsweb URL that serves the raw `prowjob.json`:

```
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/<bucket>/<path>/<job-name>/<build-id>/prowjob.json
```

**Example:**

- **Input Prow URL**: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.22-e2e-gcp-ovn-upgrade/2019864414127132672`
- **GCS Web URL**: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.22-e2e-gcp-ovn-upgrade/2019864414127132672/prowjob.json`

The conversion is: replace `https://prow.ci.openshift.org/view/` with `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/` and append `/prowjob.json`.

### Step 3: Fetch the prowjob.json

Use `curl` or `WebFetch` to retrieve the JSON content from the constructed URL.

```bash
curl -s "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job-name>/<build-id>/prowjob.json"
```

### Step 4: Extract and Return Key Fields

From the full `prowjob.json`, extract and return the following fields:

#### Required Fields

| Field | JSON Path | Description |
|-------|-----------|-------------|
| **Job Name** | `spec.job` | Full periodic/presubmit/postsubmit job name |
| **Job Type** | `spec.type` | `periodic`, `presubmit`, or `postsubmit` |
| **Build ID** | `status.build_id` | Unique build identifier |
| **State** | `status.state` | `success`, `failure`, `aborted`, `pending`, `triggered` |
| **Description** | `status.description` | Human-readable status description |
| **Start Time** | `status.startTime` | ISO 8601 timestamp |
| **Completion Time** | `status.completionTime` | ISO 8601 timestamp (null if still running) |
| **Cluster** | `spec.cluster` | Build cluster (e.g., `build02`, `build05`) |
| **Pod Name** | `status.pod_name` | Kubernetes pod name |
| **Prow URL** | `status.url` | Link back to the Prow job view |
| **Payload Tag** | `metadata.annotations["release.openshift.io/tag"]` | The payload version tested or upgraded to (e.g., `4.22.0-0.ci-2026-02-06-195709`). This is the payload the cluster was tested against or upgraded to. |
| **Upgrade From Tag** | `metadata.annotations["release.openshift.io/from-tag"]` | The original payload version before upgrade (e.g., `4.22.0-0.ci-2026-02-05-195709`). Only present for upgrade jobs. This is the version the cluster starts at before upgrading to the payload tag. |
| **Release Source** | `metadata.annotations["release.openshift.io/source"]` | Release stream source (e.g., `ocp/4.22`) |
| **Architecture** | `metadata.annotations["release.openshift.io/architecture"]` | CPU architecture (e.g., `amd64`, `arm64`, `multi`) |
| **Refs** | `spec.extra_refs` | Array of repo references (org, repo, base_ref) |
| **Target** | From `spec.pod_spec.containers[0].args` | The `--target=` value from ci-operator args |
| **Variant** | From `spec.pod_spec.containers[0].args` | The `--variant=` value from ci-operator args |
| **RELEASE_IMAGE_LATEST** | From `spec.pod_spec.containers[0].env` | The release image the job upgrades to or installs |
| **RELEASE_IMAGE_INITIAL** | From `spec.pod_spec.containers[0].env` | The initial release image (for upgrade jobs) |

#### Notes on Release Annotations

- **`release.openshift.io/tag`**: Present on release-controller-triggered jobs. Identifies the payload being validated. For upgrade jobs, this is the version the cluster upgrades **to**.
- **`release.openshift.io/from-tag`**: Only present on upgrade jobs. Identifies the version the cluster starts at **before** the upgrade. If absent, the job is not an upgrade job.
- These annotations may not be present on manually triggered or presubmit jobs.
- The `RELEASE_IMAGE_LATEST` and `RELEASE_IMAGE_INITIAL` environment variables correspond to these tags and contain the full registry pull spec.

## Error Handling

### Case 1: Invalid Prow URL Format

If the URL doesn't match the expected pattern `https://prow.ci.openshift.org/view/gs/...`:

- Report the error to the user
- Show the expected URL format

### Case 2: prowjob.json Not Found (404)

If the GCS web proxy returns a 404:

- The job may have been garbage collected or the URL may be incorrect
- Suggest verifying the Prow job URL is correct and the job exists

### Case 3: Network Error

If the GCS web proxy is unreachable:

- Check connectivity to `gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com`
- The proxy does not require VPN or authentication

## Examples

### Example 1: Fetch a Periodic Upgrade Job

**Input:**
```
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.22-e2e-gcp-ovn-upgrade/2019864414127132672
```

**Key output fields:**
```
Job Name:             periodic-ci-openshift-release-master-ci-4.22-e2e-gcp-ovn-upgrade
Job Type:             periodic
Build ID:             2019864414127132672
State:                failure
Start Time:           2026-02-06T20:02:58Z
Completion Time:      2026-02-07T00:36:09Z
Cluster:              build02
Payload Tag:          4.22.0-0.ci-2026-02-06-195709
Upgrade From Tag:     4.22.0-0.ci-2026-02-05-195709
Architecture:         amd64
Target:               e2e-gcp-ovn-upgrade
Variant:              ci-4.22
RELEASE_IMAGE_LATEST: registry.ci.openshift.org/ocp/release:4.22.0-0.ci-2026-02-06-195709
RELEASE_IMAGE_INITIAL:registry.ci.openshift.org/ocp/release:4.22.0-0.ci-2026-02-05-195709
```

### Example 2: Non-Upgrade Job (No from-tag)

For a non-upgrade job, the `Upgrade From Tag` field will be absent:

```
Job Name:             periodic-ci-openshift-release-master-ci-4.22-e2e-gcp-ovn
Job Type:             periodic
Build ID:             2019864414127132999
State:                success
Payload Tag:          4.22.0-0.ci-2026-02-06-195709
Upgrade From Tag:     (not present - not an upgrade job)
Architecture:         amd64
Target:               e2e-gcp-ovn
Variant:              ci-4.22
```

## Notes

- The `prowjob.json` is uploaded to GCS by Prow's sidecar after the job completes (or is aborted). It may not be available for jobs still in progress.
- The `managedFields` section of the metadata can be omitted from output as it contains only field ownership bookkeeping.
- The `metadata.labels` section is truncated for some fields (e.g., job name) due to Kubernetes label length limits. Always use `metadata.annotations` or `spec.job` for the full job name.
- The GCS web proxy at `gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com` serves raw file content without authentication.
- Duration can be calculated from `completionTime - startTime`.
- The `spec.decoration_config.timeout` field shows the maximum allowed runtime for the job.

## See Also

- Related Command: `/ci:analyze-prow-job-test-failure` (analyzes test failures in a Prow job)
- Related Command: `/ci:analyze-prow-job-install-failure` (analyzes install failures in a Prow job)
- Related Skill: `ci:prow-job-analyze-test-failure` (detailed test failure analysis)
