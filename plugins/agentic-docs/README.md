# Agentic Docs

AI-optimized OpenShift documentation with progressive disclosure, reference style (tables/checklists), and pointer-based navigation.

## Two-Tier Architecture

**Platform Docs** (`openshift/enhancements/ai-docs/`) - **Already exists**  
Generic patterns, testing, security, K8s/OpenShift fundamentals, cross-repo ADRs. ~34 files, 4.4k lines.

**Component Docs** (`{component}/ai-docs/`)  
Component CRDs, architecture, local ADRs, exec-plans. Links to platform docs. ~15 files, 2.5k lines (58% leaner).

## Skills

### `/update-platform-docs`
Incrementally update platform docs with automatic gap detection.

```bash
cd /path/to/openshift/enhancements
/update-platform-docs
```

Scans ai-docs/, reports missing files, lets you fill gaps or add custom content. Auto-updates indexes/navigation and validates conventions. Use for incremental changes to existing platform documentation.

### `/component-docs`
Creates lean component docs in component repositories.

```bash
cd /path/to/component-repository
/component-docs
```

Creates AGENTS.md + ai-docs/ with: component CRDs only, architecture, component ADRs, exec-plans, ecosystem links to platform docs, development/testing guides. Excludes generic patterns (lives in platform docs). Example: [machine-config-operator/ai-docs](https://github.com/openshift/machine-config-operator/tree/master/ai-docs).

### `/review-docs`
Review agentic documentation for hallucinations and verify claims against authoritative sources.

```bash
cd /path/to/component-repository
/review-docs
```

Uses the **chai-bot MCP server** to verify documentation claims against verified OpenShift knowledge, GitHub source code, Slack history, Jira, and official docs. Detects hallucinations, outdated conventions, and missing references.

**Prerequisites**: Requires chai-bot MCP server configuration (see Setup below).

## Setup

### chai-bot MCP Server (for `/review-docs`)

The `/review-docs` skill requires access to the **chai-bot MCP server** configured with the **"OpenShift AI helpdesk"** persona — an AI agent with verified OpenShift knowledge.

**Prerequisites:**
1. **Red Hat VPN** - Must be connected to Red Hat VPN
2. **Bearer Token** - Obtain from the chai-bot Slack app
3. **Persona** - This plugin uses the `ocp_ai_helpdesk` persona (OpenShift AI helpdesk)

**Configuration:**

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "chai-bot": {
      "type": "http",
      "url": "https://ship-help-mcp-continuous-release-tooling--ship-help-bot.apps.gpc.ocp-hub.prod.psi.redhat.com/personas/ocp_ai_helpdesk/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Important:** 
- The URL includes `/personas/ocp_ai_helpdesk` — this is the **OpenShift AI helpdesk** persona
- Replace `YOUR_TOKEN_HERE` with your bearer token from the chai-bot Slack app
- Restart Claude Code after configuration

**Alternative:** Merge `plugins/agentic-docs/.mcp.json.sample` into your existing `~/.mcp.json` (or create it if it doesn't exist):
```bash
# Merge without overwriting existing entries
jq -s '.[0] * .[1]' ~/.mcp.json plugins/agentic-docs/.mcp.json.sample > ~/.mcp.json.tmp \
  && mv ~/.mcp.json.tmp ~/.mcp.json \
  || cp plugins/agentic-docs/.mcp.json.sample ~/.mcp.json
```
Then edit `~/.mcp.json` and replace the `YOUR_TOKEN_HERE` placeholder with your actual bearer token from the chai-bot Slack app.

**Verification:**
```bash
# Must be on VPN
ping -c 1 ship-help-mcp-continuous-release-tooling--ship-help-bot.apps.gpc.ocp-hub.prod.psi.redhat.com

# Check config
jq '.mcpServers."chai-bot"' ~/.mcp.json
```

After configuration, restart Claude Code to load the MCP server.

## Development

Skills live under `skills/{update-platform-docs,component-docs,review-docs}/` with SKILL.md, scripts, and templates.

**License:** Apache 2.0
