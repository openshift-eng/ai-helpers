---
name: Fetch Releases
description: Fetch available OpenShift releases from the Sippy API
---

# Fetch Releases

This skill fetches the list of available OpenShift releases from the Sippy API. It can return all OCP releases or just the latest version.

## When to Use This Skill

Use this skill when you need to:

- Determine the latest OCP release version
- Get a list of all available OCP releases
- Provide a default release version when the user hasn't specified one

## Prerequisites

1. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

2. **Network Access**: Must be able to reach the public Sippy API
   - Check: `curl -s https://sippy.dptools.openshift.org/api/releases | head -c 100`

## Implementation Steps

### Step 1: Get the Latest Release

To get just the latest OCP release version:

```bash
release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
echo "$release"
# Output: 4.22
```

### Step 2: List All Releases

To list all available OCP releases:

```bash
# JSON format (includes GA dates)
python3 plugins/ci/skills/fetch-releases/fetch_releases.py --format json

# Simple list, one per line
python3 plugins/ci/skills/fetch-releases/fetch_releases.py --format list
```

### Step 3: Use with Other Skills

The primary use case is providing a default release to other skills:

```bash
# Determine release
release="${user_specified_release:-$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)}"

# Use with fetch-test-report
python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py "<test_name>" --release "$release"
```

## Output Format

### --latest

Prints a single release version string:

```
4.22
```

### --format json (default)

```json
[
  {"release": "4.22"},
  {"release": "4.21", "ga": "2025-06-17T00:00:00Z"},
  {"release": "4.20", "ga": "2025-10-21T00:00:00Z"},
  {"release": "4.19", "ga": "2025-06-17T00:00:00Z"}
]
```

Releases without a `ga` field are still in development.

### --format list

```
4.22
4.21
4.20
4.19
4.18
```

## Error Handling

1. **Network Error**: If the Sippy API is unreachable, the script prints an error to stderr and exits with code 1.
2. **No Releases**: If no standard OCP releases are found, exits with code 1.

**Exit Codes:**
- `0`: Success
- `1`: Error

## Notes

- Uses the public Sippy API at `https://sippy.dptools.openshift.org/api/releases` (no port-forward needed)
- Filters out non-standard releases (okd, aro, presubmits, etc.) — only returns releases matching `X.Y` format
- The API returns releases in order with the latest first
- This skill is based on the same API as the `teams` plugin's `get-release-dates` skill

## See Also

- Related Skill: `fetch-test-report` (uses release to query test data)
- Related Skill (teams plugin): `get-release-dates` (fetches detailed release dates and metadata)
