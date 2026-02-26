---
name: Fetch Payloads
description: Fetch recent release payloads from the OpenShift release controller
---

# Fetch Payloads

This skill fetches recent release payloads from the OpenShift release controller, showing their tag name, acceptance phase, timestamp, blocking job results, and a link to the release details page.

## When to Use This Skill

Use this skill when you need to:

- Find the latest accepted (or rejected) nightly or CI payloads for a given OCP version
- Check the current state of release payloads for any architecture
- See which blocking jobs failed for rejected payloads
- Get a link to the release controller page for a specific payload

## Implementation Steps

### Step 1: Determine defaults

If the user did not specify an architecture or stream, default to `amd64` and `nightly`. If no version is specified, the script automatically fetches the latest from the Sippy API.

### Step 2: Fetch payloads

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py [architecture] [version] [stream]
```

Examples:

```bash
# Latest amd64 nightly payloads (all defaults, last 5)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py

# arm64 4.18 nightly
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py arm64 4.18 nightly

# Only accepted payloads
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py amd64 4.18 nightly --phase Accepted

# Show more results
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py amd64 4.18 nightly --limit 20
```

### Step 3: Present results

The script outputs one block per payload to stdout with job details. Present to the user as-is or summarize.

## Output Format

For each payload, the script outputs:

- **Tag line**: `<tag>  (<phase>)  <timestamp>  <url>`
- **Rejected payloads**: lists each failed blocking job with retry count and Prow link
- **Ready payloads**: summary of succeeded/pending/failed counts
- **Accepted payloads**: confirmation that all blocking jobs succeeded

## Error Handling

1. **Unknown architecture**: Exits with error listing valid architectures
2. **CI stream on non-amd64**: Exits with error (CI stream is amd64-only)
3. **Network error**: Prints connection failure to stderr, exits 1
4. **No payloads found**: Prints message to stderr, exits 1
