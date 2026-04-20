---
name: Setup Snowflake
description: This skill should be used before any Snowflake command to verify MCP connectivity, guide users through access provisioning, and set the session context. Invoke this skill proactively whenever a command needs Snowflake data access.
---

# Setup Snowflake Connection

This skill verifies that the Snowflake MCP server is available and properly configured. If it is not, it performs automated setup -- the user only needs to provide their Snowflake username. This skill should be invoked at the start of every command that needs Snowflake data.

## When to Use This Skill

Use this skill automatically at the beginning of any Snowflake-dependent command (e.g., `/snowflake:activity-type-report`). Do not skip this step -- it ensures the user has a working connection before any queries are attempted.

## Implementation Steps

### Step 1: Check MCP Availability

Attempt to call the Snowflake MCP tool to verify it exists:

```text
mcp__snowflake__execute_sql(query="SELECT CURRENT_USER()")
```

If the tool is **available and succeeds**, proceed to Step 3.

If the tool is **not available** (MCP server not configured) or the call fails because the server cannot start, proceed to Step 2.

### Step 2: Automated Setup

When the Snowflake MCP server is not available, perform the following sub-steps. Each sub-step is idempotent -- skip it if the expected state already exists.

#### 2a: Ensure `uvx` Is Installed

Use the Bash tool to check if `uvx` is available:

```bash
which uvx
```

If `uvx` is **not found**, tell the user:

> The Snowflake MCP server requires `uvx` (part of the `uv` Python package manager). I need to install it.

Then install it (after the user grants permission). Use the appropriate method for the platform:

```bash
# Fedora/RHEL
dnf install -y uv

# macOS
brew install uv

# Other
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2b: Ask for Snowflake Username

Ask the user for their Snowflake username. It must be in ALL CAPS (e.g., `BLEANHAR`). Say:

> What is your Snowflake username? It should be in ALL CAPS (e.g., `BLEANHAR`).
>
> If you don't have Snowflake access yet, follow the instructions at:
> **https://dataverse.pages.redhat.com/data-docs/data-users/**
>
> Once you have access, come back and re-run this command.

Wait for the user to provide the username before proceeding. If they indicate they don't have access, abort gracefully.

#### 2c: Write Snowflake Connection Config

First check if `~/.snowflake/connections.toml` already exists with a `[rhprod]` section containing the correct username. If it does, skip this step.

Otherwise:

1. Create the directory if needed:

```bash
mkdir -p ~/.snowflake
```

2. Use the Write tool to create `~/.snowflake/connections.toml` (replacing `THE_USERNAME` with the username from Step 2b):

```toml
[rhprod]
account = "GDADCLC-RHPROD"
user = "THE_USERNAME"
authenticator = "EXTERNALBROWSER"
```

3. Set secure permissions:

```bash
chmod 0600 ~/.snowflake/connections.toml
```

#### 2d: Write Service Config

Check if `~/.snowflake/service_config.yaml` already exists. If it does with the correct content, skip this step.

Otherwise, use the Write tool to create `~/.snowflake/service_config.yaml`:

```yaml
other_services:
  object_manager: true
  query_manager: true
sql_statement_permissions:
  - all: true
```

#### 2e: Add MCP Server to Claude Code Config

Read `~/.claude.json` and check whether `mcpServers.snowflake` already exists with the correct configuration (including `--service-config-file`). If it already matches, skip this step.

Otherwise, use the Edit tool to add or update the `mcpServers.snowflake` entry in `~/.claude.json`. The entry should be:

```json
{
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
```

If `mcpServers` does not exist as a top-level key in `~/.claude.json`, create it. If it exists but does not contain `snowflake`, add the `snowflake` key. If `snowflake` exists but has incorrect or outdated configuration (e.g., missing `--service-config-file`), update it.

**Important**: Preserve all other existing content in `~/.claude.json`. Only add or modify the `mcpServers.snowflake` key.

#### 2f: Instruct User to Restart

After completing steps 2a-2e, tell the user:

> Snowflake MCP server has been configured. You need to **restart Claude Code** for the new MCP server to be loaded.
>
> After restarting, re-run your command and setup will complete automatically (browser-based SSO will open for authentication on first connect).

Then **abort the current command gracefully**. Do not attempt to proceed to Step 3 -- the MCP server will not be available until Claude Code restarts.

### Step 3: Set Session Context

Once the MCP tool is confirmed available, set the database, schema, and role for the session:

```text
mcp__snowflake__execute_sql(query="USE ROLE JIRA_CLOUDMARTS_GROUP")
mcp__snowflake__execute_sql(query="USE DATABASE JIRA_DB")
mcp__snowflake__execute_sql(query="USE SCHEMA CLOUDRHAI_MARTS")
```

If any of these fail (e.g., role not granted), inform the user:

> Your Snowflake account does not have the `JIRA_CLOUDMARTS_GROUP` role. This role is required to access Jira data in Snowflake. Please request this role through the access provisioning process at:
>
> **https://dataverse.pages.redhat.com/data-docs/data-users/**

### Step 4: Verify Data Access

Run a quick verification query to confirm the user can read from the expected views:

```sql
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA = 'CLOUDRHAI_MARTS'
ORDER BY TABLE_NAME
LIMIT 5
```

If this returns results, the connection is verified. Report success and return the list of available views for diagnostic purposes.

If this returns an error or zero rows, warn the user that the schema may not be accessible with their current role.

**Note**: `CLOUDRHAI_MARTS` exposes views, not base tables. `SHOW TABLES` will return nothing — use `SHOW VIEWS` or query `INFORMATION_SCHEMA.VIEWS` as above.

## Error Handling

- **MCP tool not found**: Run automated setup (Step 2)
- **Authentication failure**: Suggest running `snowsql -a GDADCLC-RHPROD -u YOUR_USERNAME --authenticator externalbrowser` to refresh browser-based auth, then retry
- **Role not granted**: Point user to access provisioning docs
- **Network timeout**: Suggest checking VPN connection (Snowflake may require corporate network access)
- **`uvx` install failure**: Suggest manual installation via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **`~/.claude.json` parse error**: If the file contains invalid JSON, warn the user and do not attempt to modify it. Ask them to fix it manually.

## Notes

- This skill deliberately does NOT hardcode the full access provisioning process. The documentation URLs are the source of truth because the provisioning process may change over time.
- The `EXTERNALBROWSER` authenticator triggers a browser-based SSO flow. This works in local development environments but may not work in headless CI containers.
- The session context (role, database, schema) must be set per-session. The MCP server does not persist these across restarts.
- The `--service-config-file` argument is required for the Snowflake MCP server to enable the query manager and object manager services. Without it, the server fails to start.
- The `connections.toml` file must have `0600` permissions or the Snowflake connector will emit warnings.
