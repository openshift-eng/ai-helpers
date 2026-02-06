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

1. **Network Access**: Must be able to reach the Sippy triage API
   - **NOTE**: Currently using localhost endpoint while testing against local Sippy
   - Check: `curl -s http://127.0.0.1:8080/api/component_readiness/triages`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

3. **Input Data**: Requires regression IDs, a JIRA bug URL, and a triage type
   - Regression IDs: from Component Readiness UI or `fetch-regression-details` skill
   - JIRA URL: an existing JIRA bug (e.g., `https://issues.redhat.com/browse/OCPBUGS-12345`)
   - Triage type: `product`, `test`, `ci-infra`, or `product-infra`

## Implementation Steps

### Step 1: Run the Python Script

```bash
script_path="plugins/ci/skills/triage-regression/triage_regression.py"

# Create a new triage for one regression
python3 "$script_path" 33639 \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json

# Create a new triage for multiple regressions
python3 "$script_path" 33639,33640,33641 \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --description "API discovery regression across metal variants" \
  --format json

# Update an existing triage (e.g., to add more regressions)
python3 "$script_path" 33639,33640,33641,33642 \
  --triage-id 456 \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json
```

**Arguments**:
- `regression_ids`: Required comma-separated list of regression IDs (integers)

**Required Options**:
- `--url <jira_url>`: JIRA bug URL
- `--type <triage_type>`: Triage type (`product`, `test`, `ci-infra`, `product-infra`)

**Options**:
- `--triage-id <id>`: Existing triage ID to update (omit to create new)
- `--description <text>`: Description for the triage
- `--format json|summary`: Output format (default: json)

### Step 2: Parse the Output

```bash
output=$(python3 "$script_path" 33639 \
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

**Create Triage**:
- Method: `POST`
- Endpoint: `/api/component_readiness/triages`
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

### Case 1: API Not Available

```json
{
  "success": false,
  "error": "Failed to connect to Sippy API: Connection refused. Ensure localhost:8080 is running.",
  "operation": "create",
  "regression_ids": [33639]
}
```

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
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json
```

### Example 2: Triage Multiple Related Regressions

```bash
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639,33640,33641 \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --description "Same root cause: API discovery failure across metal variants" \
  --format json
```

### Example 3: Update Existing Triage with Additional Regressions

```bash
# First, get the existing triage ID from regression data
existing_triage_id=$(echo "$regression_data" | jq -r '.triages[0].id')

# Update it with additional regression IDs
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639,33640,33641,33642 \
  --triage-id "$existing_triage_id" \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --format json
```

### Example 4: Triage a Test Flake

```bash
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639 \
  --url "https://issues.redhat.com/browse/OCPBUGS-67890" \
  --type test \
  --description "Flaky test: intermittent timeout in discovery suite" \
  --format json
```

## Notes

- Uses only Python standard library - no external dependencies required
- **Currently using localhost endpoint** - will switch to production Sippy once safe to write to prod
- Validates triage type locally before making the API call
- When creating, do not provide `--triage-id`; when updating, `--triage-id` is required
- The API will validate that all regression IDs exist and return an error if any are missing
- When updating a triage, the regressions list replaces the existing linked regressions entirely
- The API automatically looks up and links the JIRA bug if the URL matches an imported bug

## See Also

- Related Skill: `fetch-regression-details` (provides regression IDs and existing triage info)
- Related Command: `/ci:analyze-regression` (analyzes regressions and suggests triage)
