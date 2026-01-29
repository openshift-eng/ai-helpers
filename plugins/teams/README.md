# Teams Plugin

Team structure knowledge and health analysis commands for OpenShift teams.

## Overview

The Teams plugin provides comprehensive information about OpenShift team structure and health analysis capabilities. It helps teams understand:

1. **Team Structure**:
   - Team component ownership mapping
   - Repository assignments
   - Communication channels (Slack)
   - Team member information

2. **Team Health Analysis**:
   - Regression management metrics across team components
   - Bug backlog health for team components
   - Combined quality grading with actionable recommendations
   - Trend tracking across releases

The plugin offers commands at different levels:
- **Discovery**: List teams and their component ownership
- **Data**: Raw regression and JIRA data for investigation
- **Summary**: Aggregated statistics and counts
- **Analysis**: Combined health grading with recommendations

## Commands

### Team Discovery

#### `/teams:list-teams`

List all teams from the team component mapping.

**Usage:**
```
/teams:list-teams
```

**Use Cases:**
- Discover available teams
- Validate team names for other commands
- Understanding team structure

#### `/teams:list-components`

List all OCPBUGS components, optionally filtered by team.

**Usage:**
```
/teams:list-components
/teams:list-components --team "API Server"
```

**Use Cases:**
- Discover components owned by a team
- Validate component names for JIRA queries
- Understanding component ownership

### Health Analysis

#### `/teams:health-check`

Analyze and grade team or component health based on regression and JIRA bug metrics.

**Usage:**
```
/teams:health-check <release> --team <team-name> [--project JIRAPROJECT]
/teams:health-check <release> --components comp1 comp2 ... [--project JIRAPROJECT]
```

**Examples:**
```
# Analyze team health (recommended)
/teams:health-check 4.21 --team "API Server"

# Analyze specific components
/teams:health-check 4.21 --components Monitoring etcd

# Use alternative JIRA project
/teams:health-check 4.21 --team "Networking" --project OCPBUGS
```

**Use Cases:**
- Grade overall team quality
- Identify components needing attention
- Get actionable recommendations
- Generate comprehensive health scorecards
- Prioritize engineering investment
- Track team health across releases

**Requirements:**
- Either `--team` or `--components` is REQUIRED
- Analyzing all components is too much data

#### `/teams:health-check-regressions`

Query and summarize just regression data with counts and metrics. Part of the overall health-check command.

**Usage:**
```
/teams:health-check-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
/teams:health-check-regressions <release> --team <team-name> [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

**Examples:**
```
# Team-based summary (recommended)
/teams:health-check-regressions 4.21 --team "API Server"

# Component-based summary
/teams:health-check-regressions 4.21 --components Monitoring etcd

# Custom date range
/teams:health-check-regressions 4.17 --start 2024-05-17 --end 2024-10-29
```

**Use Cases:**
- Get quick regression counts by team or component
- Track triage coverage and response times
- Understanding open vs closed breakdown
- Generate summary reports for teams

#### `/teams:health-check-jiras`

Query and summarize JIRA bugs with counts by component, status, and priority. Part of the overall health-check command.

**Usage:**
```
/teams:health-check-jiras --project <project> [--component comp1 ...] [--status status1 ...] [--include-closed] [--limit N]
/teams:health-check-jiras --project <project> --team <team-name> [--status status1 ...] [--include-closed] [--limit N]
```

**Examples:**
```
# Team-based JIRA summary
/teams:health-check-jiras --project OCPBUGS --team "API Server"

# Component-based summary
/teams:health-check-jiras --project OCPBUGS --component "kube-apiserver" "etcd"

# Include closed bugs
/teams:health-check-jiras --project OCPBUGS --team "Networking" --include-closed
```

**Use Cases:**
- Get bug counts by team or component
- Track recent bug flow (opened vs closed)
- Monitor bug velocity and closure rates
- Compare bug backlogs across teams

### Raw Data

#### `/teams:list-regressions`

Fetch and list raw regression data for OpenShift releases without summarization.

**Usage:**
```
/teams:list-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
/teams:list-regressions <release> --team <team-name> [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

**Use Cases:**
- Access complete regression details for investigation
- Build custom analysis workflows
- Export data for offline analysis

#### `/teams:list-jiras`

Query and list raw JIRA bug data for a specific project.

**Usage:**
```
/teams:list-jiras --project <project> [--component comp1 comp2 ...] [--status status1 ...] [--include-closed] [--limit N]
```

**Use Cases:**
- Access detailed JIRA bug information
- Custom bug analysis workflows
- Export bug data for reporting

## Team Structure Data

The plugin maintains a committed mapping file (`team_component_map.json`) that contains:

- **Team names**: All OpenShift teams with OCPBUGS components
- **Component ownership**: Which OCPBUGS components each team owns
- **Metadata**: Component counts per team

**Data Source**: The mapping data originates from https://gitlab.cee.redhat.com/hybrid-platforms/org (requires Red Hat VPN).

**To update the mapping**:
1. Submit PRs to the org repository to correct team/component assignments
2. After merge, regenerate: `python3 plugins/teams/generate_team_component_map.py`
3. Commit the updated mapping file

## Installation

### Via Marketplace (Recommended)

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install teams@ai-helpers

# Use the commands
/teams:list-teams
/teams:health-check 4.21 --team "API Server"
```

### Manual Installation

```bash
# Clone the repository
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Prerequisites

1. **Python 3.6+**: Required to run analysis scripts
2. **Network Access**: Required to reach component health API and JIRA
3. **JIRA Authentication** (for bug analysis):
   - `JIRA_URL`: Your JIRA instance URL
   - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token

## Use Cases

### Analyze Team Health

Get a comprehensive health scorecard for a team:

```
/teams:health-check 4.21 --team "API Server"
```

Output includes:
- Team-level regression metrics
- Team-level bug backlog metrics
- Per-component breakdowns
- Health grades and recommendations

### Track Team Trends

Compare team health across releases:

```
/teams:health-check 4.21 --team "Networking"
/teams:health-check 4.20 --team "Networking"
```

### Discover Team Structure

Find teams and their components:

```
/teams:list-teams
/teams:list-components --team "API Server"
```

### Monitor Bug Backlogs

Track team bug health:

```
/teams:health-check-jiras --project OCPBUGS --team "API Server"
```

## Output Format

### health-check Command

Provides a **Comprehensive Health Report** with:

- **Team Summary** (when using --team):
  - Overall team metrics combining all components
  - Per-component breakdowns within the team
  - Team-level health grade

- **Component Scorecards**:
  - Regression triage coverage (target: 90%+)
  - Average time to triage (target: <24 hours)
  - Bug backlog size and age
  - Combined health grades (✅/⚠️/❌)

- **Actionable Recommendations**:
  - Open untriaged regressions
  - High bug backlogs
  - Slow triage response
  - Growing bug trends

## Contributing

See [AGENTS.md](../../AGENTS.md) for development guidelines.

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Repository**: https://github.com/openshift-eng/ai-helpers

## License

See [LICENSE](../../LICENSE) for details.
