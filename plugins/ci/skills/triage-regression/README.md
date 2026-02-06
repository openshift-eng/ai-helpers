# Triage Regression

Create or update a Component Readiness triage record linking regressions to a JIRA bug.

## Overview

This skill creates or updates triage records via the Sippy API. It links one or more Component Readiness regressions to a JIRA bug with a triage type and optional description.

Key features:
- Create a new triage for one or more regressions
- Update an existing triage to change details or add regressions
- Authenticates to sippy-auth using a Bearer token from the DPCR cluster (via oc-auth skill)
- Validates triage type locally before calling the API
- Supports `product`, `test`, `ci-infra`, and `product-infra` triage types

## Usage

```bash
# Obtain token using oc-auth skill (DPCR cluster)
TOKEN=$(oc whoami -t --context=<dpcr-context>)

# Create a new triage for a single regression
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <regression_ids> \
  --token "$TOKEN" \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]

# Create a new triage for multiple regressions
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <id1,id2,id3> \
  --token "$TOKEN" \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]

# Update an existing triage
python3 plugins/ci/skills/triage-regression/triage_regression.py \
  <regression_ids> \
  --token "$TOKEN" \
  --triage-id <existing_triage_id> \
  --url <jira_url> \
  --type <triage_type> \
  [--description <text>] \
  [--format json|summary]
```

**Arguments**:
- `regression_ids`: Comma-separated list of regression IDs (integers)

**Required Options**:
- `--token <token>`: OAuth Bearer token for sippy-auth (use oc-auth skill to obtain from DPCR cluster)
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
  --token "$TOKEN" \
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

## Authentication

This skill authenticates to `https://sippy-auth.dptools.openshift.org` using a Bearer token from the DPCR cluster (`api.cr.j7t7.p1.openshiftapps.com:6443`). Use the `oc-auth` skill to obtain the token. You must be logged into the DPCR cluster via `oc login`.

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `oc-auth` skill (provides authentication tokens for sippy-auth)
- Related: `fetch-regression-details` skill (provides regression IDs and existing triage info)
- Related: `/ci:analyze-regression` command (analyzes regressions and suggests triage)
