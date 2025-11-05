# Component Health Plugin

Grade component health based on various metrics for OpenShift releases.

## Overview

The Component Health plugin evaluates how well OpenShift components are managing their test regressions by analyzing key regression management metrics. It provides health grades based on three key indicators:

1. **Triage Coverage**: What percentage of regressions have been triaged to JIRA bugs
2. **Triage Timeliness**: How quickly regressions are being triaged
3. **Resolution Speed**: How quickly regressions are being resolved

These metrics help identify components that need attention in their regression management and track overall quality trends.

## Commands

### `/component-health:analyze-regressions`

Grade component health based on regression triage metrics for a specific OpenShift release.

**Usage:**

```
/component-health:analyze-regressions <release> [--components comp1 comp2 ...]
```

**Examples:**

```
# Grade overall component health for release 4.17
/component-health:analyze-regressions 4.17
# Shows triage coverage % and timeliness across all components

# Grade specific components
/component-health:analyze-regressions 4.21 --components Monitoring etcd
# Compare health grades for Monitoring and etcd

# Deep dive into single component health
/component-health:analyze-regressions 4.21 --components "kube-apiserver"
# Detailed health metrics for kube-apiserver component
```

**Arguments:**

- `<release>`: OpenShift release version (e.g., "4.17", "4.16")
- `--components comp1 [comp2 ...]`: (Optional) Filter by component names (case-insensitive)

**Automatic Date Filtering:**

The command automatically fetches release dates and filters regressions to the development window:

- For GA'd releases (e.g., 4.17): Filters to regressions within the development window
  - Excludes regressions closed before development started (--start filter)
  - Excludes regressions opened after GA date (--end filter)
  - Focuses analysis on regressions during active development
- For in-development releases (e.g., 4.21 with null GA date): Partial filtering applied
  - Excludes regressions closed before development started (--start filter)
  - No end date filtering (release still in development)

This ensures health grading reflects component behavior during the release development period, excluding pre-release regressions and (for GA'd releases) post-GA regressions that may not have been actively monitored.

## Skills

### list-regressions

Python script for fetching component health regression data from an API.

**Location:** `plugins/component-health/skills/list-regressions/`

**Key Files:**

- `list_regressions.py`: Main script for fetching regression data
- `SKILL.md`: Detailed implementation guide for AI agents
- `README.md`: User-facing documentation

### get-release-dates

Python script for fetching OpenShift release dates and metadata from Sippy.

**Location:** `plugins/component-health/skills/get-release-dates/`

**Key Files:**

- `get_release_dates.py`: Main script for fetching release information
- `SKILL.md`: Detailed implementation guide for AI agents
- `README.md`: User-facing documentation

**Usage:**

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.21
```

Returns GA dates, development start dates, and capabilities for the specified release.

## Setup

### Prerequisites

1. **Python 3.6+**: Required to run the regression analysis scripts
2. **Network Access**: Required to reach the component health API

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

### Grade Release Health

Get a health scorecard for a release based on triage metrics:

```
/component-health:analyze-regressions 4.20
```

Output includes:

- Overall triage coverage percentage (target: 90%+)
- Average time to triage (target: <24 hours)
- Per-component health grades
- Components needing attention

### Identify Components Needing Attention

Find components with poor triage metrics:

```
/component-health:analyze-regressions 4.21 --components Monitoring etcd "kube-apiserver"
```

Compare components by:

- Triage coverage percentage
- Average triage timeliness
- Open regression counts

### Track Health Trends Across Releases

Compare triage metrics across releases to track improvement:

```
/component-health:analyze-regressions 4.17
/component-health:analyze-regressions 4.16
```

## Output Format

The command provides a **Component Health Report** with:

### Overall Health Grade

- **Triage Coverage**: Percentage of regressions triaged (e.g., "95.2% triaged")
  - 90-100%: Excellent ✅
  - 70-89%: Good ⚠️
  - 50-69%: Needs Improvement ⚠️
  - <50%: Poor ❌
- **Triage Timeliness**: Average hours to triage (e.g., "68 hours avg")
  - <24 hours: Excellent ✅
  - 24-72 hours: Good ⚠️
  - 72-168 hours: Needs Improvement ⚠️
  - > 168 hours: Poor ❌
- **Resolution Speed**: Average hours to close regressions (e.g., "168 hours avg")
  - <168 hours (1 week): Excellent ✅
  - 168-336 hours (1-2 weeks): Good ⚠️
  - 336-720 hours (2-4 weeks): Needs Improvement ⚠️
  - > 720 hours (4+ weeks): Poor ❌
- Total regressions and triaged counts
- Breakdown by open/closed status

### Per-Component Health Scorecard

- Ranked table of components with:
  - Triage coverage percentage
  - Average time to triage
  - Average time to close (resolution speed)
  - Open regression count
  - Health grade (✅/⚠️/❌)

### Components Needing Attention

- Highlighted list of components with poor health metrics
- Focus on low triage coverage, slow triage response, or slow resolution times

### Detailed Metrics (Optional)

- Time to close metrics
- Age of open regressions
- Lists of untriaged regressions

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
