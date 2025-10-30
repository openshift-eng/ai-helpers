# Component Health Plugin

Analyze component health and track regressions across OpenShift releases.

## Overview

The Component Health plugin provides tools for monitoring and analyzing the health of OpenShift components across different releases. It helps identify regressions, track component stability, and generate quality metrics.

## Commands

### `/component-health:analyze-regressions`

Fetch and analyze regression data for a specific OpenShift release.

**Usage:**

```
/component-health:analyze-regressions <release> [--components comp1 comp2 ...]
```

**Examples:**

```
# Analyze all regressions for release 4.17
/component-health:analyze-regressions 4.17

# Filter by specific components
/component-health:analyze-regressions 4.21 --components Monitoring etcd

# Filter by single component
/component-health:analyze-regressions 4.21 --components "kube-apiserver"
```

**Arguments:**

- `<release>`: OpenShift release version (e.g., "4.17", "4.16")
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

# Use the command
/component-health:analyze-regressions 4.21
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

Check the overall health of a release by analyzing all regressions:

```
/component-health:analyze-regressions 4.17
```

Note: Open regressions will have `"closed": null`, while closed regressions will show a timestamp.

### Track Specific Components

Monitor regressions for specific components:

```
/component-health:analyze-regressions 4.21 --components Monitoring etcd "kube-apiserver"
```

### Compare Releases

Compare regression counts across releases to track quality trends:

```
/component-health:analyze-regressions 4.17
/component-health:analyze-regressions 4.16
```

## Output Format

The command provides:

- **Overall Summary**: Total counts across all components, open/closed breakdown
- **Regressions by Component**: Regressions grouped by component name (sorted alphabetically)
  - Each component includes its own summary statistics (total, open, closed counts)
  - Each component includes its regression details
- **Regression Details**: Component, ID, description, status, timestamps for each regression
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
