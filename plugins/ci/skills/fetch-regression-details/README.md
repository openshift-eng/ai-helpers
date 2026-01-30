# Fetch Regression Details Skill

This skill fetches detailed information about a Component Readiness regression from the Sippy API.

## Overview

The `fetch-regression-details` skill retrieves comprehensive regression data from the Component Readiness system, including:

- Test name and component
- Release version
- Regression status and dates
- Affected platform/topology variants
- Existing triage records and JIRA tickets
- Links to sample failures

## Usage

This skill is used internally by the `/ci:analyze-regression` command but can also be invoked directly when you need to fetch regression details programmatically.

### Input

- **Regression ID**: Integer ID from Component Readiness (e.g., 34446)

### Output

Structured JSON data containing:

```json
{
  "regression_id": 34446,
  "test_name": "[sig-network] Feature:SCTP...",
  "release": "4.21",
  "component": "Networking",
  "opened": "2024-12-20T08:02:45.127153Z",
  "closed": null,
  "status": "open",
  "variants": ["Architecture:amd64", "Platform:aws"],
  "test_details_url": "https://sippy.dptools.openshift.org/...",
  "triages": [...],
  "sample_pass_sequence": "FFFFFSFFFSSFFFFSFFFFFFFSSSSSSSSSSSSSSSSS",
  "sample_failed_jobs": [
    {
      "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
      "job_run_id": "2017184460591599616",
      "start_time": "2026-01-30T10:33:47",
      "job_name": "periodic-ci-openshift-release-master-nightly-4.22-e2e-..."
    }
  ]
}
```

**Note:**
- `sample_pass_sequence`: Chronological success/fail pattern (newest to oldest). "S" = success, "F" = failure.
- `sample_failed_jobs`: Always included, contains job runs where the test failed.

## API Endpoint

The skill fetches data from:

```
https://sippy.dptools.openshift.org/api/component_readiness/regressions/{regression_id}
```

No authentication is required for read-only access.

## Prerequisites

- Network access to sippy.dptools.openshift.org
- Python 3.6 or later (uses standard library only)

## Usage

```bash
# Fetch as JSON (default, includes failed jobs)
python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py 34446

# Fetch as human-readable summary
python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py 34446 --format summary
```

## Implementation Details

The skill uses a Python script (`fetch_regression_details.py`) that:
1. Fetches regression data from the Sippy API
2. Parses and structures the response
3. Outputs either JSON or formatted summary

See [SKILL.md](./SKILL.md) for complete implementation guidance.

## Related Commands

- `/ci:analyze-regression` - Analyzes a regression using this skill
- `/teams:list-regressions` - Lists all regressions for a release
