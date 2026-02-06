# Triage Regression

Create or update a Component Readiness triage record linking regressions to a JIRA bug.

## Overview

This skill creates or updates triage records via the Sippy API. It links one or more Component Readiness regressions to a JIRA bug with a triage type and optional description.

Key features:
- Create a new triage for one or more regressions
- Update an existing triage to change details or add regressions
- Validates triage type locally before calling the API
- Supports `product`, `test`, `ci-infra`, and `product-infra` triage types

## Usage

```bash
# Create a new triage for a single regression
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <regression_ids> \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]

# Create a new triage for multiple regressions
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <id1,id2,id3> \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]

# Update an existing triage
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <regression_ids> \
  --triage-id <existing_triage_id> \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]
```

**Arguments**:
- `regression_ids`: Comma-separated list of regression IDs (integers)

**Required Options**:
- `--url <jira_url>`: JIRA bug URL (e.g., `https://issues.redhat.com/browse/OCPBUGS-12345`)
- `--type <triage_type>`: Triage type: `product`, `test`, `ci-infra`, `product-infra`

**Options**:
- `--triage-id <id>`: Existing triage ID to update (omit to create new)
- `--description <text>`: Description for the triage
- `--format`: Output format - `json` (default) or `summary`

## Example

```bash
# Create a triage linking three regressions to one bug
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  33639,33640,33641 \
  --url "https://issues.redhat.com/browse/OCPBUGS-12345" \
  --type product \
  --description "API discovery failure across metal variants" \
  --format json
```

## Output

```json
{
  "success": true,
  "operation": "create",
  "regression_ids": [33639, 33640, 33641],
  "triage": {
    "id": 456,
    "url": "https://issues.redhat.com/browse/OCPBUGS-12345",
    "type": "product",
    "description": "API discovery failure across metal variants",
    "regressions": [
      {"id": 33639},
      {"id": 33640},
      {"id": 33641}
    ]
  }
}
```

## Note

Currently using localhost endpoint (`http://127.0.0.1:8080`) to avoid writing to production data. Will switch to production Sippy URL once the workflow is validated.

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `fetch-regression-details` skill (provides regression IDs and existing triage info)
- Related: `/ci:analyze-regression` command (analyzes regressions and suggests triage)
