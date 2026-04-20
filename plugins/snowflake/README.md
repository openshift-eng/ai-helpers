# Snowflake Plugin

Snowflake data analysis commands for engineering metrics and reports. Uses the [Snowflake MCP server](https://github.com/Snowflake-Labs/mcp) to query data directly from Snowflake, with AI-powered analysis and interactive HTML report generation.

## Prerequisites

1. **Snowflake access** -- You need an account on your organization's Snowflake instance with the appropriate role (e.g., `JIRA_CLOUDMARTS_GROUP` for Jira data). See [the data platform documentation](https://dataverse.pages.redhat.com/data-docs/data-users/) for access provisioning.

2. **Python 3** -- Required for report generation. Most systems have this pre-installed.

3. **plotly** (optional) -- `pip install plotly` for richer interactive charts. Without it, the report uses a D3.js fallback that requires no installation.

## Setup

Setup is fully automated. On first use, any Snowflake command will:

1. Check if the Snowflake MCP server is configured
2. If not, prompt you for your Snowflake username (ALL CAPS)
3. Install `uvx` if needed
4. Create `~/.snowflake/connections.toml` and `~/.snowflake/service_config.yaml`
5. Add the Snowflake MCP server to `~/.claude.json`
6. Ask you to restart Claude Code

After restarting, re-run your command. Browser-based SSO will open for authentication.

### Manual Setup (Reference)

If you prefer to configure manually or need to troubleshoot:

#### 1. Install uv

```bash
# Fedora/RHEL
dnf install -y uv

# macOS
brew install uv

# Other
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. Configure Snowflake Connection

Create `~/.snowflake/connections.toml`:

```toml
[rhprod]
account = "GDADCLC-RHPROD"
user = "YOUR_USERNAME"
authenticator = "EXTERNALBROWSER"
```

Set permissions: `chmod 0600 ~/.snowflake/connections.toml`

#### 3. Create Service Config

Create `~/.snowflake/service_config.yaml`:

```yaml
other_services:
  object_manager: true
  query_manager: true
sql_statement_permissions:
  - all: true
```

#### 4. Add MCP Server to Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "snowflake": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/Snowflake-Labs/mcp",
        "mcp-server-snowflake",
        "--connection-name", "rhprod",
        "--service-config-file", "~/.snowflake/service_config.yaml"
      ],
      "env": {}
    }
  }
}
```

Restart Claude Code after adding the configuration.

### Documentation Links

- **Obtaining Snowflake access**: https://dataverse.pages.redhat.com/data-docs/data-users/
- **Snowflake MCP setup**: https://dataverse.pages.redhat.com/ai-docs/ai-agent-user/snowflake/

## Commands

### `/snowflake:activity-type-report <projects> [months]`

Classify Jira issues into activity types and generate an interactive sankey report.

**Arguments:**
- `projects` -- Comma-separated Jira project keys (e.g., `DPTP,TRT,ART`)
- `months` -- Lookback period in months (default: 6)

**Examples:**

```bash
# Single project, last 6 months
/snowflake:activity-type-report DPTP

# Multiple projects, last 3 months
/snowflake:activity-type-report DPTP,TRT,ART,OCPERT 3

# Full year analysis
/snowflake:activity-type-report DPTP,TRT,ART,OCPERT,OCPCRT 12
```

**Output:** An interactive HTML report at `.work/snowflake/reports/<run-dir>/activity-type-report.html` with:
- Sankey diagram showing issue flow from Project to Activity Type
- Stacked bar chart of Activity Type composition per project
- Summary statistics
- Drill-down links to Jira for each flow segment
- Searchable, paginated detail table with direct Jira links per issue
- CSV export

## How Classification Works

1. Issues are fetched from `JIRA_DB.CLOUDRHAI_MARTS` (PII-sanitized) via Snowflake MCP
2. A Python script (`classify_issues.py`) sends issues in batches of ~15 to Claude via Vertex AI
3. Each API call includes category definitions and classification rules inline
4. Results are merged and `generate_sankey.py` produces the HTML report

**Requirements:** The classification script calls Claude via Vertex AI and requires:
- `gcloud` CLI authenticated (`gcloud auth login`)
- Environment variables: `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID` (already set in the org's devcontainer)
- Optional: `ANTHROPIC_SMALL_FAST_MODEL` to override the model (default: `claude-sonnet-4-6`)

The AI considers each issue's summary, description, type, status, components, and project context when classifying. Categories are:

| Category | Description |
|----------|-------------|
| Associate Wellness & Development | Training, learning, mentorship, team building |
| Incidents & Support | Production incidents, customer escalations, on-call |
| Security & Compliance | CVE remediation, vulnerabilities, audits |
| Quality / Stability / Reliability | Bug fixes, flaky tests, CI reliability |
| Future Sustainability | Tech debt, architecture improvements, modernization |
| Product / Portfolio Work | Features, enhancements, roadmap items |
| Uncategorized | Insufficient information to classify |

## Scaling

| Scale | Issues | Estimated Time |
|-------|--------|---------------|
| Single team | 50-200 | 15-30 seconds |
| Group (5 teams) | 500-1,000 | 30-60 seconds |
| Large org | 2,000-8,000 | 2-5 minutes |

Classification calls Vertex AI directly (no sub-agents), processing ~15 issues per API call sequentially.

## Shell Commands

This plugin runs Python scripts via shell commands during report generation. You will be prompted to approve these commands:

- `python3 .../classify_issues.py` -- Classifies issues by calling Claude via Vertex AI
- `python3 .../generate_sankey.py` -- Generates the interactive HTML report
- `python3 .../open_report.py` -- Starts a temporary HTTP server (auto-shuts down after 30s) and opens the report in your browser via VS Code port forwarding
- `gcloud auth print-access-token` -- Called by the classification script for Vertex AI authentication

These scripts are located in the plugin's `scripts/` directory and only read/write local files.

## Cost Reporting

The classification script reports API usage after each run, including:
- Input/output token counts
- Number of API calls
- Wall clock time
- Estimated cost based on current Sonnet pricing

## Future: Cloud-Hosted Dashboard

If local setup proves impractical for broad adoption, a Cloud Run-based alternative could run classification on a schedule and publish dashboards to a shared URL. This is a fallback option -- the plugin approach is preferred because it requires no server infrastructure and puts the user in control.
