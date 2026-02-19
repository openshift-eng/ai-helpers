---
name: Triage Regression
description: Create or update a Component Readiness triage record linking regressions to a JIRA bug
---

# Triage Regression

This skill creates or updates triage records via the Sippy API, linking one or more Component Readiness regressions to a JIRA bug.

## When to Use This Skill

Use this skill when you need to:

- File a triage record for one or more regressions identified by the analyze-regression command
- Link multiple related regressions to a single JIRA bug
- Update an existing triage to add more regressions or change details

## Prerequisites

1. **OpenShift CLI Authentication**: Required for authenticating to the sippy-auth API
   - Must be logged into the DPCR cluster via `oc login`
   - Cluster API: `https://api.cr.j7t7.p1.openshiftapps.com:6443`
   - Use the `oc-auth` skill to obtain the Bearer token

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

3. **Input Data**: Requires regression IDs, a JIRA bug URL, and a triage type
   - Regression IDs: from Component Readiness UI or `fetch-regression-details` skill
   - JIRA URL: an existing JIRA bug (e.g., `https://issues.redhat.com/browse/OCPBUGS-12345`)
   - Triage type: `product`, `test`, `ci-infra`, or `product-infra`

## Implementation Steps

### Step 1: Obtain Authentication Token

Use the `oc-auth` skill to obtain a Bearer token from the DPCR cluster:

```bash
# Get token from the DPCR cluster context
# The oc-auth skill's curl_with_token.sh uses this cluster for sippy-auth
DPCR_CLUSTER="https://api.cr.j7t7.p1.openshiftapps.com:6443"

# Find the oc context for the DPCR cluster and get the token
CONTEXT=$(oc config get-contexts -o name 2>/dev/null | while read -r ctx; do
  server=$(oc config view -o jsonpath="{.clusters[?(@.name=='$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" 2>/dev/null)')].cluster.server}" 2>/dev/null || echo "")
  server_clean=$(echo "$server" | sed -E 's|^https?://||')
  if [ "$server_clean" = "api.cr.j7t7.p1.openshiftapps.com:6443" ]; then
    echo "$ctx"
    break
  fi
done)

if [ -z "$CONTEXT" ]; then
  echo "Error: Not logged into DPCR cluster. Please run: oc login $DPCR_CLUSTER"
  exit 1
fi

TOKEN=$(oc whoami -t --context="$CONTEXT" 2>/dev/null)
if [ -z "$TOKEN" ]; then
  echo "Error: Failed to get token. Please re-authenticate to DPCR cluster."
  exit 1
fi
```

### Step 2: Run the Python Script

```bash
script_path="plugins/ci/skills/triage-regression/triage_regression.py"

# Create a new triage for one regression
python3 "$script_path" 33639 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json

# Create a new triage for multiple regressions
python3 "$script_path" 33639,33640,33641 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --description "API discovery regression across metal variants" \
  --format json

# Update an existing triage to add more regressions (url and type inherited from existing triage)
python3 "$script_path" 33639,33640,33641,33642 \
  --token "$TOKEN" \
  --triage-id 456 \
  --format json
```

**Arguments**:
- `regression_ids`: Required comma-separated list of regression IDs (integers)

**Required Options**:
- `--token <token>`: OAuth Bearer token for sippy-auth (obtained from oc-auth skill)
- `--url <jira_url>`: JIRA bug URL (required for create, optional for update - uses existing value)
- `--type <triage_type>`: Triage type: `product`, `test`, `ci-infra`, `product-infra` (required for create, optional for update - uses existing value)

**Options**:
- `--triage-id <id>`: Existing triage ID to update (omit to create new)
- `--description <text>`: Description for the triage
- `--format json|summary`: Output format (default: json)

### Step 3: Parse the Output

```bash
output=$(python3 "$script_path" 33639 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json)

success=$(echo "$output" | jq -r '.success')

if [ "$success" = "true" ]; then
  triage_id=$(echo "$output" | jq -r '.triage.id')
  echo "Triage created with ID: $triage_id"
else
  error=$(echo "$output" | jq -r '.error')
  echo "Error: $error"
fi
```

## Triage Types

| Type | Description |
|------|-------------|
| `product` | Actual product regressions (default for most bugs) |
| `test` | Test framework issues (flaky tests, test bugs) |
| `ci-infra` | CI infrastructure problems that did not impact customers |
| `product-infra` | Infrastructure problems that impacted CI and customers |

## API Details

**Base URL**: `https://sippy-auth.dptools.openshift.org`

**Authentication**: Bearer token from the DPCR cluster (`api.cr.j7t7.p1.openshiftapps.com:6443`)

**Create Triage**:
- Method: `POST`
- Endpoint: `/api/component_readiness/triages`
- Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`
- Body:
  ```json
  {
    "url": "https://issues.redhat.com/browse/OCPBUGS-12345",
    "type": "product",
    "description": "Optional description",
    "regressions": [{"id": 33639}, {"id": 33640}]
  }
  ```

**Update Triage**:
- Method: `PUT`
- Endpoint: `/api/component_readiness/triages/{id}`
- Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`
- Body: Same as create, but must include `"id"` matching the URL path

## Script Output Format

### JSON Format (--format json)

**Success Response**:
```json
{
  "success": true,
  "operation": "create",
  "regression_ids": [33639],
  "triage": {
    "id": 456,
    "url": "https://issues.redhat.com/browse/OCPBUGS-12345",
    "type": "product",
    "description": "API discovery regression",
    "regressions": [
      {"id": 33639}
    ],
    "links": {
      "self": "/api/component_readiness/triages/456"
    }
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "HTTP error 400: Bad Request",
  "detail": "regression ID 99999 not found",
  "operation": "create",
  "regression_ids": [99999]
}
```

### Summary Format (--format summary)

```
Triage Create - SUCCESS
============================================================

Triage ID: 456
URL: https://issues.redhat.com/browse/OCPBUGS-12345
Type: product
Description: API discovery regression
Linked Regressions: 1
  - Regression 33639
```

## Error Handling

### Case 1: Authentication Failure

```json
{
  "success": false,
  "error": "HTTP error 401: Unauthorized",
  "detail": "",
  "operation": "create",
  "regression_ids": [33639]
}
```

Re-authenticate to the DPCR cluster and obtain a fresh token.

### Case 2: Invalid Regression ID

```json
{
  "success": false,
  "error": "HTTP error 400: Bad Request",
  "detail": "regression ID 99999 not found",
  "operation": "create",
  "regression_ids": [99999]
}
```

### Case 3: Invalid Triage Type

The script validates triage type locally before making the API call:
```
Error: Invalid type 'invalid'. Must be one of: product, test, ci-infra, product-infra
```

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid input, API error, network error, etc.)

## Examples

### Example 1: Triage a Single Regression

```bash
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json
```

### Example 2: Triage Multiple Related Regressions

```bash
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639,33640,33641 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --description "Same root cause: API discovery failure across metal variants" \
  --format json
```

### Example 3: Update Existing Triage with Additional Regressions

```bash
# First, get the existing triage ID from regression data
existing_triage_id=$(echo "$regression_data" | jq -r '.triages[0].id')

# Update it with additional regression IDs (url and type inherited from existing triage)
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639,33640,33641,33642 \
  --token "$TOKEN" \
  --triage-id "$existing_triage_id" \
  --format json
```

### Example 4: Triage a Test Flake

```bash
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639 \
  --token "$TOKEN" \
  --url "https://issues.redhat.com/browse/OCPBUGS-67890" \
  --type test \
  --description "Flaky test: intermittent timeout in discovery suite" \
  --format json
```

## Notes

- Uses only Python standard library - no external dependencies required
- Authenticates to `https://sippy-auth.dptools.openshift.org` using a Bearer token from the DPCR cluster
- Use the `oc-auth` skill to obtain the token (requires `oc login` to DPCR cluster)
- Validates triage type locally before making the API call
- When creating, do not provide `--triage-id`; when updating, `--triage-id` is required
- The API will validate that all regression IDs exist and return an error if any are missing
- When updating a triage, the script automatically fetches existing regressions and merges them with the new ones (safe additive behavior)
- The API automatically looks up and links the JIRA bug if the URL matches an imported bug

## See Also

- Related Skill: `oc-auth` (provides authentication tokens for sippy-auth)
- Related Skill: `fetch-regression-details` (provides regression IDs and existing triage info)
- Related Command: `/ci:analyze-regression` (analyzes regressions and suggests triage)
