---
description: Fetch recent release payloads from the OpenShift release controller
argument-hint: "[architecture] [version] [stream]"
---

## Name

ci:fetch-payloads

## Synopsis

```
/ci:fetch-payloads [architecture] [version] [stream]
```

## Description

The `ci:fetch-payloads` command fetches recent release payloads from the OpenShift release controller. It shows each payload's tag name, phase (Accepted/Rejected/Ready), timestamp, and blocking job results. For rejected payloads, it reports which blocking jobs failed with Prow links.

## Implementation

1. **Determine parameters**: Default to `amd64` architecture and `nightly` stream if the user hasn't specified them. If no version is provided, the script fetches the latest from the Sippy API.

2. **Fetch payloads**: Use the `fetch-payloads` skill:
   ```bash
   python3 plugins/ci/skills/fetch-payloads/fetch_payloads.py [architecture] [version] [stream]
   ```

   Optional flags:
   - `--phase Accepted|Rejected|Ready` to filter by phase
   - `--limit N` to control how many results to show (default 5)

3. **Present the results**: Show the user the payload list. For rejected payloads, highlight the failed blocking jobs and their Prow links.

## Return Value

- **Format**: One block per payload with tag, phase, timestamp, URL, and job details
- **Rejected payloads**: Each failed blocking job is listed with retry count and Prow link
- **Ready payloads**: Summary of succeeded/pending/failed blocking job counts
- **Accepted payloads**: Confirmation that all blocking jobs succeeded

## Examples

1. **Latest nightly payloads (defaults to amd64, latest version, last 5)**:
   ```
   /ci:fetch-payloads
   ```

2. **Specific version and architecture**:
   ```
   /ci:fetch-payloads arm64 4.18 nightly
   ```

3. **Only rejected payloads**:
   ```
   /ci:fetch-payloads amd64 4.18 nightly --phase Rejected
   ```

## Arguments

- $1: CPU architecture (optional, default: amd64) — amd64, arm64, ppc64le, s390x, multi
- $2: OCP version (optional, default: latest from Sippy) — e.g., 4.18, 4.23
- $3: Release stream (optional, default: nightly) — nightly, ci

## Skills Used

- `fetch-payloads`: Queries the release controller API for payload tags and release details
- `fetch-releases` (indirectly): Used by the script to determine the latest version when not specified
