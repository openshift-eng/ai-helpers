---
description: Configure the GVS MCP server in Cursor
argument-hint: ""
---

## Name
gvs:setup

## Synopsis
```text
/gvs:setup
```

## Description
The `gvs:setup` command configures the GVS MCP server in Cursor. It checks the current configuration, and if not configured, creates or updates the MCP configuration file automatically with user confirmation.

## Implementation

### Step 1: Check if MCP server is already configured

1. **Check for existing GVS MCP server**
   - Look for "gvs" in the MCP server list
   - If configured, test the connection

2. **If already configured and working**
   - Display: "GVS MCP server is already configured and ready."
   - Show server URL
   - Exit successfully

### Step 2: Detect IDE and config file location (if not configured)

1. **Determine config file path**
   
   For Cursor, check in order:
   - Project-level: `.cursor/mcp.json` (in workspace root)
   - User-level: `~/.cursor/mcp.json`
   
   For Claude Code:
   - User-level: `~/.config/claude/mcp.json`

2. **Read existing config (if any)**
   - Parse the JSON file if it exists
   - Preserve existing MCP server configurations

### Step 3: Create/Update MCP config with user confirmation

1. **Show the configuration to be added**
   
   Display to user:
   ```text
   I will add the GVS MCP server to your configuration:
   
   Server Name: gvs
   Type: SSE
   URL: http://gvs.gsslab.pnq2.redhat.com:8083/sse
   
   Config file: <detected-path>
   ```

2. **Ask for confirmation**
   - "Would you like me to add this configuration? (yes/no)"
   - Wait for explicit user approval

3. **If user approves, update config file**
   
   Add to `mcpServers` section:
   ```json
   {
     "mcpServers": {
       "gvs": {
         "url": "http://gvs.gsslab.pnq2.redhat.com:8083/sse",
         "transport": "sse"
       }
     }
   }
   ```
   
   - If file exists, merge with existing config (preserve other servers)
   - If file doesn't exist, create it with proper structure
   - Create parent directories if needed

4. **Handle errors gracefully**
   - If write fails due to permissions, show manual instructions
   - If JSON is malformed, offer to backup and recreate

### Step 4: Verify configuration

1. **Inform user to restart/reload**
   - Display: "Configuration updated. Please restart Cursor for changes to take effect."

2. **After restart, test the connection**
   - Attempt to call `lookup_cve` with a known CVE (e.g., CVE-2024-45338)
   - If successful, display: "GVS MCP server configured successfully!"
   - If failed, display error and suggest troubleshooting steps

## Return Value

- **Already configured**: Confirmation that GVS MCP server is ready
- **Configuration updated**: Confirmation that config file was updated
- **Manual instructions**: If automatic configuration fails, provides manual steps
- **Error**: Troubleshooting suggestions if configuration fails

## Examples

1. **Configure GVS server (first time)**:
   ```text
   /gvs:setup
   ```
   
   Output:
   ```text
   I will add the GVS MCP server to your configuration:
   
   Server Name: gvs
   Type: SSE
   URL: http://gvs.gsslab.pnq2.redhat.com:8083/sse
   
   Config file: /Users/you/.cursor/mcp.json
   
   Would you like me to add this configuration? (yes/no)
   ```

2. **If already configured**:
   ```text
   /gvs:setup
   ```
   
   Output:
   ```text
   GVS MCP server is already configured and ready.
   Server URL: http://gvs.gsslab.pnq2.redhat.com:8083/sse
   ```

## Arguments

This command takes no arguments.

## Config File Format

The command creates/updates MCP config with this structure:

```json
{
  "mcpServers": {
    "gvs": {
      "url": "http://gvs.gsslab.pnq2.redhat.com:8083/sse",
      "transport": "sse"
    }
  }
}
```

## Troubleshooting

### "Permission denied" when writing config

The command cannot write to the config file. Options:
- Run with appropriate permissions
- Manually add the configuration (see Config File Format above)

### "Connection refused" or timeout after setup

- Verify you can reach the server: `curl http://gvs.gsslab.pnq2.redhat.com:8083/`
- Check if you're connected to the Red Hat network or VPN
- The server may be temporarily unavailable

### "MCP server not found" after setup

- Restart Cursor after configuration changes
- Check that the config file was saved correctly
- Verify the server name is exactly `gvs` (lowercase)

### "SSE connection failed"

- Verify the URL ends with `/sse`: `http://gvs.gsslab.pnq2.redhat.com:8083/sse`
- Check for proxy settings that might block SSE connections

## See Also

- `/gvs:lookup` - Test the connection by looking up a CVE
- `/gvs:scan` - Scan a repository for vulnerabilities
