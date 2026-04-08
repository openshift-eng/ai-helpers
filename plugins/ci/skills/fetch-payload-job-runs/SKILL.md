---
name: Fetch Payload Job Runs
description: Fetch job runs for a specific payload tag from Sippy, optionally filtered to upgrade jobs only
---

# Fetch Payload Job Runs

This skill fetches all job runs associated with a specific payload tag from the Sippy API. It can optionally filter to only upgrade jobs, which is useful for verifying that a payload successfully upgrades from a previous version.

## When to Use This Skill

Use this skill when you need to:

- List all job runs (blocking, informing, async) for a specific payload tag
- Check which upgrade jobs passed or failed for a payload
- Verify that a payload successfully upgrades from a prior version
- Get Prow URLs for individual job runs within a payload

## Prerequisites

1. **Python 3**: Version 3.6 or later
2. **Network Access**: Must be able to reach `https://sippy.dptools.openshift.org`

## Implementation

```bash
FETCH_PAYLOAD_JOB_RUNS="${CLAUDE_PLUGIN_ROOT}/skills/fetch-payload-job-runs/fetch_payload_job_runs.py"
if [ ! -f "$FETCH_PAYLOAD_JOB_RUNS" ]; then
  FETCH_PAYLOAD_JOB_RUNS=$(find ~/.claude/plugins -type f -path "*/ci/skills/fetch-payload-job-runs/fetch_payload_job_runs.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$FETCH_PAYLOAD_JOB_RUNS" ] || [ ! -f "$FETCH_PAYLOAD_JOB_RUNS" ]; then echo "ERROR: fetch_payload_job_runs.py not found" >&2; exit 2; fi

# All jobs for a payload
python3 "$FETCH_PAYLOAD_JOB_RUNS" <payload-tag>

# Upgrade jobs only
python3 "$FETCH_PAYLOAD_JOB_RUNS" <payload-tag> --upgrade

# JSON output
python3 "$FETCH_PAYLOAD_JOB_RUNS" <payload-tag> --format json
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `tag` | Yes | Payload tag (e.g., `4.19.0-0.nightly-2026-04-02-000704`) |
| `--upgrade` | No | Filter to upgrade jobs only |
| `--format` | No | Output format: `text` (default) or `json` |

## API Details

**Endpoint**: `https://sippy.dptools.openshift.org/api/releases/job_runs`

**Query Parameters**:
- `release`: Release version extracted from the tag (e.g., `4.19`)
- `filter`: JSON filter object with `release_tag` match and optional `upgrade` filter

**Response**: Array of job run objects with key fields:

| Field | Type | Description |
|-------|------|-------------|
| `job_name` | string | Short job name (e.g., `aws-ovn-upgrade-4.19-micro-fips`) |
| `kind` | string | Job kind: `Blocking`, `Informing`, or `Async` |
| `state` | string | `Succeeded` or `Failed` |
| `url` | string | Prow job URL |
| `retries` | int | Number of retries |
| `upgrade` | bool | Whether this is an upgrade job |
| `upgrades_from` | string | Source payload tag for upgrade jobs |
| `upgrades_to` | string | Target payload tag for upgrade jobs |
| `name` | int | Prow job run ID |

## Output

### Text Format

Structured for AI consumption:
1. **Header**: Payload tag, filter, total count
2. **Jobs grouped by kind** (Blocking, Informing, Async) with pass/fail counts
3. **Per-job details**: State, name, retries, upgrade path, Prow URL

### JSON Format

Raw API response array for structured processing.

## Examples

### Example 1: All jobs for a payload

```bash
python3 fetch_payload_job_runs.py 4.19.0-0.nightly-2026-04-02-000704
```

### Example 2: Check upgrade job results

```bash
python3 fetch_payload_job_runs.py 4.19.0-0.nightly-2026-04-02-000704 --upgrade
```

## See Also

- Related Skill: `fetch-payloads` - Fetch recent payload tags and their acceptance phase
- Related Skill: `fetch-job-run-summary` - Fetch detailed test failure summary for a specific job run
