# Component Health Plugin

Analyze component health based on regression and bug metrics for OpenShift releases.

## Overview

The Component Health plugin provides comprehensive quality analysis for OpenShift components by evaluating:

1. **Regression Management Metrics**:
   - Triage Coverage: What percentage of regressions have been triaged to JIRA bugs
   - Triage Timeliness: How quickly regressions are being triaged
   - Resolution Speed: How quickly regressions are being resolved

2. **Bug Backlog Health**:
   - Open bug counts by component
   - Bug age distribution
   - Recent bug flow (opened vs closed)
   - Priority breakdowns

The plugin offers three levels of analysis:
- **List**: Raw regression data for detailed investigation
- **Summarize**: Summary statistics and counts
- **Analyze**: Combined health grading with actionable recommendations

## Commands

### `/component-health:list-regressions`

Fetch and list raw regression data for OpenShift releases without summarization.

**Usage:**

```
/component-health:list-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

**Examples:**

```
# List all regressions for release 4.17
/component-health:list-regressions 4.17

# Filter by specific component
/component-health:list-regressions 4.21 --components Monitoring

# Filter by development window
/component-health:list-regressions 4.17 --start 2024-05-17 --end 2024-10-29
```

**Use Cases:**
- Accessing complete regression details for investigation
- Building custom analysis workflows
- Exporting data for offline analysis

### `/component-health:summarize-regressions`

Query and summarize regression data with counts and metrics.

**Usage:**

```
/component-health:summarize-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

**Examples:**

```
# Summarize all regressions for release 4.17
/component-health:summarize-regressions 4.17
# Shows counts, triage percentages, timing metrics

# Filter by specific components
/component-health:summarize-regressions 4.21 --components Monitoring etcd
# Compare summary metrics for Monitoring and etcd

# Custom date range
/component-health:summarize-regressions 4.17 --start 2024-05-17 --end 2024-10-29
```

**Use Cases:**
- Getting quick regression counts by component
- Tracking triage coverage and response times
- Understanding open vs closed breakdown
- Generating summary reports

### `/component-health:analyze`

Analyze and grade component health based on regression and JIRA bug metrics.

**Usage:**

```
/component-health:analyze <release> [--components comp1 comp2 ...] [--project JIRAPROJECT]
```

**Examples:**

```
# Comprehensive health analysis for release 4.17
/component-health:analyze 4.17
# Shows combined regression + bug backlog health grades

# Analyze specific components
/component-health:analyze 4.21 --components Monitoring etcd
# Compare overall health grades for Monitoring and etcd

# Deep dive into single component
/component-health:analyze 4.21 --components "kube-apiserver"
# Detailed health metrics with actionable recommendations

# Use alternative JIRA project
/component-health:analyze 4.21 --project OCPSTRAT
```

**Use Cases:**
- Grading overall component quality
- Identifying components needing attention
- Getting actionable recommendations
- Generating comprehensive health scorecards
- Prioritizing engineering investment

**Automatic Date Filtering:**

The analyze command automatically fetches release dates and filters regressions to the development window:

- For GA'd releases (e.g., 4.17): Filters to regressions within the development window
  - Excludes regressions closed before development started
  - Excludes regressions opened after GA date
  - Focuses analysis on regressions during active development
- For in-development releases (e.g., 4.21): Partial filtering applied
  - Excludes regressions closed before development started
  - No end date filtering (release still in development)

This ensures health grading reflects component behavior during the release development period.

### `/component-health:list-jiras`

Query and list raw JIRA bug data for a specific project.

**Usage:**

```
/component-health:list-jiras <project> [--component comp1 comp2 ...] [--status status1 ...] [--include-closed] [--limit N]
```

See command documentation for detailed usage.

### `/component-health:summarize-jiras`

Query and summarize JIRA bugs with counts by component, status, and priority.

**Usage:**

```
/component-health:summarize-jiras --project <project> [--component comp1 ...] [--status status1 ...] [--include-closed] [--limit N]
```

See command documentation for detailed usage.

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

# Use the commands
/component-health:analyze 4.21
/component-health:summarize-regressions 4.21
/component-health:list-regressions 4.21
```

### Manual Installation

```bash
# Clone the repository
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Use Cases

### Analyze Overall Component Health

Get a comprehensive health scorecard combining regression and bug metrics:

```
/component-health:analyze 4.20
```

Output includes:

- Regression triage coverage percentage (target: 90%+)
- Average time to triage regressions (target: <24 hours)
- Bug backlog counts and age distribution
- Per-component health grades
- Actionable recommendations

### Identify Components Needing Attention

Find components with quality issues:

```
/component-health:analyze 4.21 --components Monitoring etcd "kube-apiserver"
```

Compare components by:

- Regression triage coverage percentage
- Average regression triage timeliness
- Open bug backlog size
- Combined health grade

### Generate Regression Summary Reports

Get summary statistics for regression management:

```
/component-health:summarize-regressions 4.21
```

Shows:

- Total regressions per component
- Triage percentages
- Timing metrics (average/max)
- Open vs closed breakdown

### Investigate Specific Regressions

Access raw regression data for detailed investigation:

```
/component-health:list-regressions 4.21 --components "kube-apiserver"
```

Returns complete regression details including:

- Test names and variants
- Opened/closed timestamps
- Triage information
- Failure counts

### Track Trends Across Releases

Compare metrics across releases to track improvement:

```
/component-health:analyze 4.17
/component-health:analyze 4.16
```

## Output Format

### analyze Command

The `/component-health:analyze` command provides a **Comprehensive Component Health Report** with:

#### Overall Health Grade

- **Regression Metrics**:
  - Triage Coverage: Percentage of regressions triaged
    - 90-100%: Excellent ✅
    - 70-89%: Good ⚠️
    - 50-69%: Needs Improvement ⚠️
    - <50%: Poor ❌
  - Triage Timeliness: Average hours to triage
    - <24 hours: Excellent ✅
    - 24-72 hours: Good ⚠️
    - 72-168 hours: Needs Improvement ⚠️
    - >168 hours: Poor ❌
  - Resolution Speed: Average hours to close regressions
    - <168 hours (1 week): Excellent ✅
    - 168-336 hours (1-2 weeks): Good ⚠️
    - 336-720 hours (2-4 weeks): Needs Improvement ⚠️
    - >720 hours (4+ weeks): Poor ❌

- **Bug Backlog Metrics**:
  - Total open bugs across all components
  - Bugs opened/closed in last 30 days
  - Priority distribution

#### Per-Component Health Scorecard

- Ranked table of components with:
  - Regression triage coverage percentage
  - Average time to triage regressions
  - Average resolution time
  - Open bug count
  - Bug age metrics
  - Combined health grade (✅/⚠️/❌)

#### Components Needing Attention

- Prioritized list with actionable recommendations:
  - Open untriaged regressions (only actionable items)
  - High bug backlogs
  - Growing bug trends
  - Slow triage response times

### summarize-regressions Command

The `/component-health:summarize-regressions` command provides:

- Total regression counts by component
- Triage percentages (overall, open, closed)
- Timing metrics (average/max time to triage, time to close)
- Open vs closed breakdown
- Per-component summaries

### list-regressions Command

The `/component-health:list-regressions` command returns raw JSON data including:

- Complete regression objects with all fields
- Test names, variants, timestamps
- Triage information (linked JIRA bugs)
- Failure counts and last failure timestamps

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
