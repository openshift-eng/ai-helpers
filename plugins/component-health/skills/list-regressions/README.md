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

The script outputs JSON data containing regression information to stdout. Diagnostic messages are written to stderr.

**Note**: Time fields are automatically simplified:

- `closed`: Shows timestamp string if closed (e.g., `"2025-09-27T12:04:24.966914Z"`), otherwise `null`
- `last_failure`: Shows timestamp string if valid (e.g., `"2025-09-25T14:41:17Z"`), otherwise `null`

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
