# List Regressions Skill

Python script for fetching component health regression data for OpenShift releases.

## Overview

This skill provides a Python script that queries a component health API to retrieve regression information for specific OpenShift releases. The data can be filtered by component names.

## Usage

```bash
# List all regressions for a release
python3 list_regressions.py --release 4.17

# Filter by specific components
python3 list_regressions.py --release 4.21 --components Monitoring etcd

# Filter by single component
python3 list_regressions.py --release 4.21 --components "kube-apiserver"
```

## Arguments

- `--release` (required): OpenShift release version (e.g., "4.17", "4.16")
- `--components` (optional): Space-separated list of component names to filter by (case-insensitive)

## Output

The script outputs JSON data with the following structure to stdout:

```json
{
  "summary": {...},
  "components": {
    "ComponentName": {
      "summary": {...},
      "open": [...],
      "closed": [...]
    }
  }
}
```

Diagnostic messages are written to stderr.

**Note**:

- Regressions are grouped by component name (sorted alphabetically)
- Each component maps to an object containing:
  - `summary`: Per-component statistics (total, open, closed, triaged counts, average time to triage)
  - `open`: Array of open regression objects
  - `closed`: Array of closed regression objects
- Time fields are automatically simplified:
  - `closed`: Shows timestamp string if closed (e.g., `"2025-09-27T12:04:24.966914Z"`), otherwise `null`
  - `last_failure`: Shows timestamp string if valid (e.g., `"2025-09-25T14:41:17Z"`), otherwise `null`
- Triaged counts: Number of regressions with non-empty `triages` list (triaged to JIRA bugs)
- Average time to triage: Average hours from regression opened to earliest triage timestamp (null if no triaged regressions)
- Maximum time to triage: Maximum hours from regression opened to earliest triage timestamp (null if no triaged regressions)
- Average open duration: Average hours that open regressions have been open (from opened to current time, only for open regressions)
- Maximum open duration: Maximum hours that open regressions have been open (from opened to current time, only for open regressions)
- Average time to close: Average hours from regression opened to closed timestamp (null if no valid data, only for closed regressions)
- Maximum time to close: Maximum hours from regression opened to closed timestamp (null if no valid data, only for closed regressions)
- Average time triaged to closed: Average hours from first triage to closed timestamp (null if no valid data, only for triaged closed regressions)
- Maximum time triaged to closed: Maximum hours from first triage to closed timestamp (null if no valid data, only for triaged closed regressions)

## Configuration

Before using, update the API endpoint in `list_regressions.py`:

```python
base_url = f"https://your-actual-api.example.com/api/v1/regressions"
```

## Requirements

- Python 3.6 or later
- Network access to the component health API
- No external Python dependencies (uses standard library only)

## See Also

- [SKILL.md](./SKILL.md) - Detailed implementation guide for AI agents
