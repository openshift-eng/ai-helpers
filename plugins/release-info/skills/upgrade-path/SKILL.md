---
name: OCP Upgrade Path
description: "Queries Cincinnati to find available OCP upgrade paths from a given version. Auto-applies when asked about upgrade paths, whether a version can upgrade to another, what updates are available, or if a z-stream is in a specific channel."
---

# OCP Upgrade Path

Queries the Cincinnati update graph API to find available upgrade paths from a given OCP version.

## When to Use This Skill

This skill automatically applies when:
- Asked what upgrades are available from a specific OCP version
- Asked whether a cluster can upgrade from version X to version Y
- Checking if a z-stream is reachable via upgrade from a given version
- Checking which channel a release is in (candidate, fast, stable)
- Asked about OCP upgrade compatibility

## How to Run

Run the script at `${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh`:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh" <version> [--channel <channel>] [--arch <arch>] [--to <target>]
```

### Examples

```bash
# All upgrades from 4.16.3 in stable-4.16
bash "${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh" 4.16.3

# Cross-minor upgrades via fast channel
bash "${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh" 4.16.3 --channel fast-4.17

# Check if a specific target is reachable
bash "${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh" 4.16.3 --channel stable-4.17 --to 4.17.8

# ARM architecture
bash "${CLAUDE_PLUGIN_ROOT}/skills/upgrade-path/upgrade-path.sh" 4.16.3 --arch arm64
```

### Input

- **version** (required): Source OCP version (e.g., `4.16.3`)
- **--channel** (optional): Cincinnati channel. Defaults to `stable-<minor>` derived from the version. Common channels: `candidate-4.X`, `fast-4.X`, `stable-4.X`, `eus-4.X`
- **--arch** (optional): Cluster architecture. Defaults to `amd64`. Options: `amd64`, `arm64`, `s390x`, `ppc64le`, `multi`
- **--to** (optional): Check reachability to a specific target version

### Output

Tab-separated list of available target versions with their payload pullspec and errata URL.

When `--to` is used, reports whether the specific upgrade path exists.

### Prerequisites

Requires `curl` and `jq`. No authentication needed — queries the public Cincinnati API.

### Complementary Tools

After finding that a fix shipped in a z-stream (via `pr-to-release-version`), use this skill to verify customers can actually upgrade to that release.

After querying upgrade paths, suggest the interactive graph visualizer for the relevant channel: `https://ctron.github.io/openshift-update-graph#<channel>`
