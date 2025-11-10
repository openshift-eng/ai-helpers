# Polarion Plugin

Polarion test management integration and test case tracking for OpenShift projects. This plugin provides comprehensive access to Polarion test data, project discovery, and test execution activity tracking through Claude Code slash commands.

## Commands

### `/polarion:activity`

Generate comprehensive test activity reports across OpenShift projects, tracking test runs, test cases, and contributor activity.

### `/polarion:projects`

Discover and list OpenShift-related projects in Polarion with advanced filtering capabilities.

### `/polarion:test-runs`

Analyze test runs for specific projects with detailed filtering and export options.

### `/polarion:health-check`

Perform health checks on Polarion connectivity and project accessibility.

### `/polarion:weekly-report`

Generate automated weekly test activity reports for team standup and management.

See the [commands/](commands/) directory for full documentation of each command.

## Installation

### From the Claude Code Plugin Marketplace

1. **Add the marketplace** (if not already added):
   ```bash
   /plugin marketplace add openshift-eng/ai-helpers
   ```

2. **Install the polarion plugin**:
   ```bash
   /plugin install polarion@ai-helpers
   ```

3. **Use the commands**:
   ```bash
   /polarion:activity --days-back 7
   ```

## Prerequisites

Before using this plugin, ensure you have:

1. **Polarion API Token**: 
   - Get from [Red Hat Polarion](https://polarion.engineering.redhat.com) → User Settings → Security → API Tokens
   - Set as environment variable: `export POLARION_TOKEN="your_token_here"`

2. **Network Access**:
   - Access to `polarion.engineering.redhat.com`
   - Corporate proxy configured if applicable

3. **Project Permissions**:
   - Read access to OpenShift-related projects in Polarion
   - Minimum permissions for test runs and test cases

## Available Commands

### Test Activity Analysis

#### `/polarion:activity` - Comprehensive Test Activity Reports

Generate detailed test activity reports across OpenShift projects with contributor tracking and project statistics.

**Basic Usage:**
```bash
# Weekly activity summary
/polarion:activity

# Custom timeframe
/polarion:activity --days-back 30

# Focus on specific projects
/polarion:activity --keywords openshift container platform

# Export detailed report
/polarion:activity --output qe-weekly-report.json
```

**Key Features:**
- Cross-project activity correlation
- Test contributor tracking
- Project activity rankings
- Export to JSON/CSV formats
- Time-based trend analysis

**Arguments:**
- `--days-back <days>`: Time period to analyze (default: 7)
- `--project-limit <num>`: Maximum projects to analyze (default: 5)
- `--keywords <words>`: Filter projects by keywords
- `--output <file>`: Export results to file
- `--format <json|csv>`: Output format
- `--verbose`: Detailed output with debug information

**Examples:**

1. Weekly team standup report:
   ```bash
   /polarion:activity --days-back 7 --output weekly-test-activity.json
   ```

2. Monthly management summary:
   ```bash
   /polarion:activity --days-back 30 --project-limit 10 --output monthly-summary.csv --format csv
   ```

3. Specific project focus:
   ```bash
   /polarion:activity --keywords "splat" "openshift" --days-back 14
   ```

### Project Discovery

#### `/polarion:projects` - Discover OpenShift Projects

Search and filter Polarion projects with intelligent keyword matching.

**Basic Usage:**
```bash
# List OpenShift-related projects
/polarion:projects

# Custom keyword search
/polarion:projects --keywords container storage platform

# Export project list
/polarion:projects --output projects.csv --format csv
```

### Test Analysis

#### `/polarion:test-runs` - Analyze Test Runs

Examine test runs for specific projects with detailed filtering.

**Basic Usage:**
```bash
# Recent test runs for project
/polarion:test-runs SPLAT

# Custom timeframe and limit
/polarion:test-runs OPENSHIFT --days-back 30 --limit 50

# Export test run data
/polarion:test-runs SPLAT --output splat-runs.json
```

### Health and Diagnostics

#### `/polarion:health-check` - Connection and Access Validation

Verify Polarion connectivity and project access permissions.

**Basic Usage:**
```bash
# Basic health check
/polarion:health-check

# Detailed diagnostics
/polarion:health-check --verbose
```

#### `/polarion:weekly-report` - Automated Weekly Reports

Generate formatted weekly reports optimized for team communication.

**Basic Usage:**
```bash
# Standard weekly report
/polarion:weekly-report

# Custom team focus
/polarion:weekly-report --keywords openshift --output weekly-team-report.md --format markdown
```

## Integration Workflows

This plugin is designed to integrate with existing QE and development workflows:

### With Team Standup

```bash
# Generate quick weekly summary for standup
/polarion:activity --days-back 7 --project-limit 3

# Export for sharing with team
/polarion:weekly-report --output standup-$(date +%Y%m%d).json
```

### With Management Reporting

```bash
# Monthly comprehensive analysis
/polarion:activity --days-back 30 --project-limit 10 --output monthly-qe-metrics.csv --format csv

# Project health overview
/polarion:projects --keywords openshift --output project-status.json
```

### With CI/CD Pipelines

```bash
# Health check in deployment pipeline
/polarion:health-check || echo "WARNING: Polarion connectivity issues"

# Automated weekly reports
/polarion:weekly-report --output reports/weekly-$(date +%Y%m%d).json
```

## Configuration

### Environment Variables
- `POLARION_TOKEN`: API authentication token (required)
- `POLARION_BASE_URL`: Custom Polarion instance URL (optional, defaults to Red Hat Polarion)
- `HTTPS_PROXY`: Corporate proxy configuration (if needed)

### Default Behavior
- **Default timeframe**: 7 days
- **Default project limit**: 5 projects
- **Default keywords**: `["openshift", "splat", "ocp", "platform", "container"]`
- **Default output format**: JSON

## Troubleshooting

### Authentication Issues
```bash
# Test token validity
/polarion:health-check

# Common fixes:
# 1. Regenerate token in Polarion UI
# 2. Verify POLARION_TOKEN environment variable
# 3. Check network connectivity
```

### Empty Results
```bash
# Debug with verbose output
/polarion:activity --verbose

# Common causes:
# 1. Insufficient project permissions
# 2. No activity in specified timeframe
# 3. Project keyword filters too restrictive
```

### Performance Issues
```bash
# Optimize queries
/polarion:activity --project-limit 3 --days-back 7

# For large datasets, use incremental approach
/polarion:activity --days-back 14 --output batch1.json
/polarion:activity --days-back 14 --keywords specific-project --output batch2.json
```

## Error Handling

The plugin includes comprehensive error handling:

- **Authentication**: Clear messages for token issues with resolution steps
- **Network**: Retry logic with exponential backoff for transient failures  
- **Rate Limiting**: Automatic handling with courtesy delays
- **Permissions**: Informative errors for insufficient access rights
- **Data Validation**: Robust parsing with fallbacks for malformed responses

## Security Considerations

- **Token Storage**: Never commit API tokens to version control
- **Data Handling**: Reports may contain sensitive project information
- **Network Security**: All communications use HTTPS with Red Hat Polarion
- **Access Control**: Plugin respects Polarion RBAC and project permissions

## Related Plugins

- **jira** - JIRA integration for correlating test results with issues
- **ci** - OpenShift CI integration for test failure analysis
- **prow-job** - Prow job analysis for CI/CD correlation
- **component-health** - Component health analysis across releases

## Development

### Adding New Commands

To add a new command to this plugin:

1. Create a new markdown file in `commands/`:
   ```bash
   touch plugins/polarion/commands/your-command.md
   ```

2. Follow the structure from existing commands (see `commands/activity.md` for reference)

3. Include these sections:
   - Name, Synopsis, Description
   - Prerequisites and Arguments  
   - Implementation details
   - Examples and Return Value
   - Error Handling and Notes

4. Test your command:
   ```bash
   /polarion:your-command
   ```

### Plugin Structure

```
plugins/polarion/
├── .claude-plugin/
│   └── plugin.json               # Plugin metadata
├── commands/
│   ├── activity.md               # QE activity analysis
│   ├── projects.md               # Project discovery
│   ├── test-runs.md              # Test run analysis
│   ├── health-check.md           # Connection diagnostics
│   └── weekly-report.md          # Weekly reporting
├── skills/                       # Optional: Complex implementations
│   └── polarion-client/
│       ├── SKILL.md              # Detailed client usage
│       └── polarion_client.py    # Reference client
└── README.md                     # This file
```

## Contributing

Contributions are welcome! When adding new Polarion-related commands:

1. Ensure the command is specific to QE/testing workflows
2. Follow the existing command structure and documentation format
3. Include comprehensive examples and error handling
4. Test with real Polarion projects
5. Update this README with new command documentation

## License

See [LICENSE](../../LICENSE) for details.