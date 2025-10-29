# Component Health Plugin

Analyze component health and track regressions across OpenShift releases.

## Overview

The Component Health plugin provides tools for monitoring and analyzing the health of OpenShift components across different releases. It helps identify regressions, track component stability, and generate quality metrics.

## Commands

### `/component-health:list-regressions`

Fetch and display regression data for a specific OpenShift release.

**Usage:**

```
/component-health:list-regressions <release> [--opened true|false] [--components comp1 comp2 ...]
```

**Examples:**

```
# List all regressions for release 4.17
/component-health:list-regressions 4.17

# List only open regressions
/component-health:list-regressions 4.17 --opened true

# List closed regressions for release 4.16
/component-health:list-regressions 4.16 --opened false

# Filter by specific components
/component-health:list-regressions 4.21 --components Monitoring etcd

# Combine filters
/component-health:list-regressions 4.21 --opened true --components "kube-apiserver"
```

**Arguments:**

- `<release>`: OpenShift release version (e.g., "4.17", "4.16")
- `--opened true|false`: (Optional) Filter by status
- `--components comp1 [comp2 ...]`: (Optional) Filter by component names (case-insensitive)

## Skills

### list-regressions

Python script for fetching component health regression data from an API.

**Location:** `plugins/component-health/skills/list-regressions/`

**Key Files:**

- `list_regressions.py`: Main script for fetching regression data
- `SKILL.md`: Detailed implementation guide for AI agents
- `README.md`: User-facing documentation

## Setup

### Prerequisites

1. **Python 3.6+**: Required to run the regression analysis scripts
2. **Network Access**: Required to reach the component health API

### Configuration

Before using the plugin, configure the API endpoint:

1. Open `plugins/component-health/skills/list-regressions/list_regressions.py`
2. Update the `base_url` variable with your actual component health API endpoint:

```python
base_url = f"https://your-actual-api.example.com/api/v1/regressions"
```

## Installation

### Via Marketplace (Recommended)

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install component-health@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Use Cases

### Analyze Release Health

Check the overall health of a release by listing all regressions:

```
/component-health:list-regressions 4.17
```

### Track Open Issues

Monitor open regressions that need attention:

```
/component-health:list-regressions 4.17 --opened true
```

### Verify Fixes

Check that regressions have been resolved:

```
/component-health:list-regressions 4.16 --opened false
```

### Track Specific Components

Monitor regressions for specific components:

```
/component-health:list-regressions 4.21 --components Monitoring etcd "kube-apiserver"
```

### Compare Releases

Compare regression counts across releases to track quality trends:

```
/component-health:list-regressions 4.17
/component-health:list-regressions 4.16
```

## Output Format

The command provides:

- **Summary Statistics**: Total counts, open/closed breakdown
- **Regression Details**: Component, ID, description, status, timestamps
- **Human-Readable Format**: Easy-to-scan output with highlighting

## Technical Details

### Architecture

The plugin uses a Python script to:

1. Construct API requests with appropriate parameters
2. Fetch regression data via HTTP GET
3. Parse and format the JSON response
4. Handle errors and edge cases

### Dependencies

- Python 3.6+ standard library only
- No external dependencies required
- Uses `urllib` for HTTP requests
- Uses `json` for parsing responses

### Error Handling

The plugin handles:

- Network connectivity issues
- API errors (404, 500, etc.)
- Invalid release formats
- Timeout scenarios
- Empty result sets

## Contributing

To add new commands or enhance existing functionality:

1. Follow the plugin structure in `AGENTS.md`
2. Add command definitions in `commands/`
3. Add skills in `skills/` for complex functionality
4. Update this README with new commands
5. Run `make lint` to validate changes

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Repository**: https://github.com/openshift-eng/ai-helpers
- **Documentation**: See `AGENTS.md` for development guidelines

## License

See [LICENSE](../../LICENSE) for details.
