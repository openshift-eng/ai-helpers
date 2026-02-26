---
name: Fetch New PRs in Payload
description: Fetch pull requests that are new in a given OpenShift payload compared to the previous payload
---

# Fetch New PRs in Payload

This skill fetches the list of pull requests that are new in a given OpenShift payload tag compared to the previous payload. It uses the Sippy payload diff API to identify which PRs were merged between two consecutive payloads.

## When to Use This Skill

Use this skill when you need to:

- Determine what changed between two consecutive payloads
- Identify which PRs were included in a specific payload
- Investigate whether a specific PR or component change landed in a payload
- Correlate a regression or test failure with newly merged PRs
- Build a changelog of what shipped in a payload

The payload tag can be obtained from the `fetch-prowjob-json` skill (`release.openshift.io/tag` annotation) or from release controller pages.

## Prerequisites

1. **Network Access**: Must be able to reach the Sippy API
   - Check: `curl -s https://sippy.dptools.openshift.org/api/health`
   - No authentication required for public API endpoints

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Run the Python Script

The skill uses a Python script to fetch and format the payload diff data:

```bash
# Path to the Python script
script_path="${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py"

# Fetch new PRs in JSON format
python3 "$script_path" <payload_tag> --format json

# Or fetch as human-readable summary grouped by component
python3 "$script_path" <payload_tag> --format summary
```

### Step 2: Parse the Output

The script outputs structured JSON data that can be further processed:

```bash
# Store JSON output in a variable for processing
pr_data=$(python3 "$script_path" 4.22.0-0.ci-2026-02-06-195709 --format json)

# Extract specific fields using jq if needed
total=$(echo "$pr_data" | jq '.total_prs')
pr_urls=$(echo "$pr_data" | jq -r '.pull_requests[].url')
components=$(echo "$pr_data" | jq -r '[.pull_requests[].component] | unique[]')

# Find PRs for a specific component
echo "$pr_data" | jq '.pull_requests[] | select(.component == "hypershift")'

# Find PRs with associated bugs
echo "$pr_data" | jq '.pull_requests[] | select(.bug_url != "")'
```

### Step 3: Use the Data

The structured data includes all PR details from the payload diff:

```json
{
  "payload_tag": "4.22.0-0.nightly-2026-01-15-114134",
  "total_prs": 17,
  "pull_requests": [
    {
      "url": "https://github.com/openshift/assisted-service/pull/8594",
      "pull_request_id": "8594",
      "component": "agent-installer-api-server",
      "description": "Create Enhancement Document for 3rd Party CNI / No CNI Support in Assisted Installer",
      "bug_url": "https://issues.redhat.com/browse/MGMT-22584"
    },
    {
      "url": "https://github.com/openshift/hypershift/pull/7470",
      "pull_request_id": "7470",
      "component": "hypershift",
      "description": "use InfraStatus.APIPort for custom DNS kubeconfig",
      "bug_url": "https://issues.redhat.com/browse/OCPBUGS-72258"
    }
  ]
}
```

## Error Handling

The Python script handles common error cases automatically:

### Case 1: Payload Not Found (404)

```bash
python3 fetch_new_prs_in_payload.py 4.22.0-0.ci-9999-99-99-000000
# Error: Payload '4.22.0-0.ci-9999-99-99-000000' not found.
# Verify the payload tag exists (e.g., 4.22.0-0.ci-2026-02-06-195709).
```

### Case 2: Network Error

```bash
python3 fetch_new_prs_in_payload.py 4.22.0-0.ci-2026-02-06-195709
# Error: Failed to connect to Sippy API: [Errno -2] Name or service not known
# Check network connectivity.
```

### Case 3: Missing Arguments

```bash
python3 fetch_new_prs_in_payload.py
# usage: fetch_new_prs_in_payload.py [-h] [--format {json,summary}] payload_tag
# fetch_new_prs_in_payload.py: error: the following arguments are required: payload_tag
```

**Exit Codes:**
- `0`: Success
- `1`: Error (invalid input, API error, network error, etc.)

## API Details

### Endpoint

```text
GET https://sippy.dptools.openshift.org/api/payloads/diff?toPayload={payload_tag}
```

### Parameters

- `toPayload` (required): The payload tag to diff against its predecessor (e.g., `4.22.0-0.ci-2026-02-06-195709`)

### Response Schema

The API returns a JSON array of PR objects:

```json
[
  {
    "id": 0,
    "created_at": "0001-01-01T00:00:00Z",
    "updated_at": "0001-01-01T00:00:00Z",
    "deleted_at": null,
    "url": "https://github.com/openshift/hypershift/pull/7470",
    "pull_request_id": "7470",
    "name": "hypershift",
    "description": "use InfraStatus.APIPort for custom DNS kubeconfig",
    "bug_url": "https://issues.redhat.com/browse/OCPBUGS-72258"
  }
]
```

**Raw API Fields:**
- `id`, `created_at`, `updated_at`, `deleted_at`: Database metadata (not useful for consumers)
- `url`: Full GitHub pull request URL
- `pull_request_id`: PR number as a string
- `name`: Component name(s) affected by this PR (may contain comma-separated values for multi-component PRs, e.g., `"olm-catalogd, olm-operator-controller"`)
- `description`: PR title/description
- `bug_url`: Associated Jira bug URL (empty string if none)

The Python script remaps `name` to `component` in its output for clarity.

## Examples

### Example 1: Fetch PRs as JSON

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py 4.22.0-0.nightly-2026-01-15-114134 --format json
```

**Expected Output:**
```json
{
  "payload_tag": "4.22.0-0.nightly-2026-01-15-114134",
  "total_prs": 17,
  "pull_requests": [
    {
      "url": "https://github.com/openshift/assisted-service/pull/8594",
      "pull_request_id": "8594",
      "component": "agent-installer-api-server",
      "description": "Create Enhancement Document for 3rd Party CNI / No CNI Support in Assisted Installer",
      "bug_url": "https://issues.redhat.com/browse/MGMT-22584"
    },
    {
      "url": "https://github.com/openshift/machine-config-operator/pull/5509",
      "pull_request_id": "5509",
      "component": "machine-config-operator",
      "description": "Set `NodeDegraded` MCN condition when node state annotation is set to `Degraded`",
      "bug_url": "https://issues.redhat.com/browse/OCPBUGS-67229"
    }
  ]
}
```

### Example 2: Fetch PRs as Summary

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py 4.22.0-0.nightly-2026-01-15-114134 --format summary
```

**Expected Output:**
```text
New PRs in payload 4.22.0-0.nightly-2026-01-15-114134
============================================================
Total: 17 new pull requests

  agent-installer-api-server (1 PRs):
    - Create Enhancement Document for 3rd Party CNI / No CNI Support in Assisted Installer [https://issues.redhat.com/browse/MGMT-22584]
      https://github.com/openshift/assisted-service/pull/8594

  hypershift (4 PRs):
    - [kubevirt] Make L3 migration labeling conditional [https://issues.redhat.com/browse/OCPBUGS-66205]
      https://github.com/openshift/hypershift/pull/7308
    - feat(api): add support for graceful service account signing key rotation [https://issues.redhat.com/browse/CNTRLPLANE-1768]
      https://github.com/openshift/hypershift/pull/7324
    - Scaffold OpenShiftManager controller [https://issues.redhat.com/browse/API-1835]
      https://github.com/openshift/hypershift/pull/7445
    - use InfraStatus.APIPort for custom DNS kubeconfig [https://issues.redhat.com/browse/OCPBUGS-72258]
      https://github.com/openshift/hypershift/pull/7470

  machine-config-operator (2 PRs):
    - Set `NodeDegraded` MCN condition when node state annotation is set to `Degraded` [https://issues.redhat.com/browse/OCPBUGS-67229]
      https://github.com/openshift/machine-config-operator/pull/5509
    - Prevent unnecessary systemd unit disable [https://issues.redhat.com/browse/OCPBUGS-58023]
      https://github.com/openshift/machine-config-operator/pull/5527
```

### Example 3: Use with fetch-prowjob-json Skill

Combine with the `fetch-prowjob-json` skill to get the payload tag from a Prow job, then find what PRs were new in that payload:

```bash
# 1. Get payload tag from prowjob.json (via fetch-prowjob-json skill)
#    payload_tag = metadata.annotations["release.openshift.io/tag"]
#    e.g., "4.22.0-0.ci-2026-02-06-195709"

# 2. Fetch new PRs in that payload
script_path="${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py"
python3 "$script_path" "$payload_tag" --format json
```

## Notes

- The API does not require authentication for read-only access
- The Python script uses only standard library modules (no external dependencies)
- The API automatically determines the previous payload to diff against; you only provide the target payload
- Payload tags follow the format: `{version}-0.{stream}-{date}-{time}` (e.g., `4.22.0-0.ci-2026-02-06-195709` or `4.22.0-0.nightly-2026-01-15-114134`)
- The `component` field (called `name` in the raw API) may contain multiple comma-separated component names for PRs that affect multiple components
- PRs without an associated bug will have an empty string for `bug_url`
- An empty response array means no new PRs were found (the payload may be identical to its predecessor)

## See Also

- Related Skill: `fetch-prowjob-json` (provides payload tag from Prow job metadata)
- Related Skill: `fetch-regression-details` (for correlating regressions with payload changes)
- Related Command: `/ci:analyze-regression` (analyzes regressions that may be caused by new PRs)
