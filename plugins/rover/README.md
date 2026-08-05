# Rover People MCP Server

Local [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes Red Hat’s [Rover People](https://rover.redhat.com/people/) directory as tools for MCP clients (Cursor, Claude Code, and others).

Authentication uses **your Kerberos ticket** — no service account, API key, or password is stored in config.

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Node.js 20+** | Used to build and run the server |
| **curl** | Used for Kerberos/SPNEGO against Keycloak (`curl --negotiate`) |
| **Kerberos client** | `kinit` / `klist` (typical on Red Hat / Fedora corp laptops) |
| **Corporate network / VPN** | Must reach `auth.redhat.com` and `rover.redhat.com` |
| **Valid Red Hat identity** | Same account you use for Rover in a browser |

## Install and build

```bash
cd /path/to/rover-mcp
npm install
npm run build
```

This produces `dist/index.js`, which is the MCP server entry point.

Useful scripts:

```bash
npm run build   # compile TypeScript → dist/
npm start       # run dist/index.js on stdio (waits for an MCP client)
npm run dev     # run TypeScript directly via tsx
```

## Authentication

### How it works

1. You obtain a Kerberos ticket with `kinit` (same as for other Red Hat internal tools).
2. On first API use, the server calls Keycloak with **SPNEGO** (`curl --negotiate`) to get an OIDC authorization code.
3. It exchanges the code for short-lived **Bearer** tokens (`rover-people-oidc` public client).
4. Access tokens last about **5 minutes**. The server refreshes them automatically with the refresh token and only redoes Kerberos if refresh fails.

No credentials are written to disk by this project. Tokens live in memory for the life of the MCP process.

### Set up your ticket

```bash
# Get a ticket (you’ll be prompted for your Red Hat password / 2FA flow as usual)
kinit YOUR_UID@REDHAT.COM

# Confirm it’s valid (exit code 0 = OK)
klist -s && echo "ticket ok" || echo "no ticket"
klist   # optional: see expiry
```

When the ticket expires, run `kinit` again.

### Important: IDE / MCP host must see the ticket

The MCP server is started as a **child process** of Cursor, Claude Code, or another host. It inherits that process’s environment — including Kerberos credentials.

If you `kinit` in a terminal **after** launching the IDE, the MCP child may still have no ticket. Fix:

1. Run `kinit` and verify with `klist -s`
2. **Restart the IDE** (or reload / restart the MCP server) so the new session inherits the ticket

The server checks for a ticket at startup and exits with a clear error if none is found.

## Configure the MCP server

Point your MCP client at the built entrypoint. Use an **absolute path** to `dist/index.js`.

### Cursor

Add to your MCP settings (e.g. Cursor Settings → MCP, or a project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "rover": {
      "command": "node",
      "args": ["/absolute/path/to/rover-mcp/dist/index.js"]
    }
  }
}
```

Example for this machine:

```json
{
  "mcpServers": {
    "rover": {
      "command": "node",
      "args": ["/home/cmoore/code/rover-mcp/dist/index.js"]
    }
  }
}
```

After saving, restart MCP / reload the window, then confirm the `rover` server shows its tools (`get_person`, `search_people`, etc.).

### Claude Code

In `~/.claude/settings.json` or the project `.claude/settings.json`:

```json
{
  "mcpServers": {
    "rover": {
      "command": "node",
      "args": ["/absolute/path/to/rover-mcp/dist/index.js"]
    }
  }
}
```

### Manual smoke test

With a valid ticket:

```bash
npm run build
npx @modelcontextprotocol/inspector node dist/index.js
```

In the Inspector UI, connect and call `get_person` with your uid (e.g. `cmoore`).

## Tools

| Tool | Arguments | Description |
|------|-----------|-------------|
| `get_person` | `kerberos_id` | Full profile by uid or email |
| `search_people` | `query` | Search by name, uid, or email |
| `get_org_chart` | `kerberos_id`, optional `include_indirect` | Manager chain + direct reports |
| `get_team` | `manager_kerberos_id`, optional `include_indirect` | Team members (direct + indirect by default) |
| `get_groups` | `kerberos_id` | Projects, communities, and badges from the profile |

Notes:

- Inputs that contain `@` are treated as **email** and resolved via advanced search.
- Missing people return a clear text message (not a hard protocol error).
- `get_groups` uses profile fields (`rhatProjects`, `rhatCommunities`, `badgePersons`) because Rover does not expose a dedicated group-membership REST API.
- Results may include `formerEmployee: true` when Rover marks someone as a former employee.

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Startup fails: no Kerberos ticket | `kinit`, then `klist -s`, then **restart the IDE** |
| 401 / auth errors mid-session | Ticket or refresh may have expired; `kinit` again and restart MCP |
| Tools work in a terminal but not in the IDE | IDE was started without a ticket — restart IDE after `kinit` |
| Cannot reach Rover / Keycloak | Check VPN / corporate network |
| `curl` / negotiate failures | Ensure `curl` supports GSS-Negotiate; confirm `klist` shows a ticket for the right realm |
| Empty or unexpected search results | Try uid vs display name; email must match Rover `mail` exactly for advanced search |

## Project layout

```
src/
  index.ts          # MCP stdio server + tool registration
  auth.ts           # Kerberos → Keycloak OIDC token manager
  rover-client.ts   # Rover REST client (Bearer + 401 retry)
  types.ts          # Shared Rover / tool types
  tools/            # Tool handlers (get_person, search, org, team, groups)
```

## License

Private / unlicensed — for internal Red Hat use with Rover access.
