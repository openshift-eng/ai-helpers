# GVS Plugin

A plugin to work with GVS MCP server. Provides commands for scanning Go repositories for CVE vulnerabilities, checking package versions, and analyzing code reachability.

## When to Use GVS vs Compliance

This repository has two Go vulnerability plugins with different architectures:

| Use Case | GVS | Compliance |
|----------|-----|------------|
| Scan **public repositories** remotely | Yes | No |
| Analyze **private** codebase | No | Yes |
| Quick CVE lookup without local tools | Yes | No |
| Auto-apply fixes to codebase | No | Yes |
| No local Go tools required | Yes | No |
| Works offline (no network) | No | Yes |
| Scan big Go codebase without resource crunch | Yes | No |

**Summary:**
- Use `/gvs:*` to query any **public repository** remotely via MCP server
- Use `/compliance:analyze-cve` for **local codebase** analysis with auto-fix

## Features

- **CVE Lookup** - Look up CVE details from the Go vulnerability database
- **Package Version Check** - Check if a specific package@version has known vulnerabilities
- **Repository Scanning** - Scan repositories for all vulnerabilities or specific CVEs
- **Reachability Analysis** - Check if vulnerable symbols are reachable from entry points
- **Reflection Analysis** - Detect reflection patterns that could invoke vulnerable symbols
- **Call Graph Visualization** - Generate SVG visualizations of vulnerability paths

## Prerequisites

- Claude Code or Cursor installed
- GVS MCP server configured and accessible

**Note:** The GVS server only supports public Git repositories. Private repositories are not accessible.

### Setting up GVS MCP Server

The GVS MCP server should be running at `gvs.gsslab.pnq2.redhat.com:8083`.

Add the MCP server to Cursor:

1. Open Cursor Settings
2. Navigate to MCP Servers configuration
3. Add a new SSE server:
   - **Name**: `gvs`
   - **URL**: `http://gvs.gsslab.pnq2.redhat.com:8083/sse`

Or for Claude Code:

```bash
# Add the GVS MCP server
claude mcp add --transport sse gvs http://gvs.gsslab.pnq2.redhat.com:8083/sse
```

### Verify Connection

Test the connection by looking up a known CVE:

```bash
/gvs:lookup CVE-2024-45338
```

## Installation

Ensure you have the ai-helpers marketplace enabled, via [the instructions here](/README.md).

```bash
# Install the plugin
/plugin install gvs@ai-helpers
```

## Available Commands

### `/gvs:setup` - Configure MCP Server

Configure the GVS MCP server in Cursor. Run this first if the server is not configured.

```bash
/gvs:setup
```

See [commands/setup.md](commands/setup.md) for full documentation.

---

### `/gvs:lookup` - Look Up CVE Details

Look up CVE details from the Go vulnerability database.

```bash
/gvs:lookup CVE-2024-45338
```

See [commands/lookup.md](commands/lookup.md) for full documentation.

---

### `/gvs:check-package` - Check Package Version

Check if a specific Go package version has known vulnerabilities.

```bash
/gvs:check-package golang.org/x/net v0.17.0
```

See [commands/check-package.md](commands/check-package.md) for full documentation.

---

### `/gvs:scan` - Scan Repository

Scan a Go repository for vulnerabilities. Supports full scans and targeted CVE checks. Auto-detects repository from current directory if not specified.

```bash
# Scan current repository for all vulnerabilities
/gvs:scan

# Scan current repository for specific CVE
/gvs:scan CVE-2024-45338

# Scan external repository
/gvs:scan https://github.com/kubernetes/kubernetes
```

See [commands/scan.md](commands/scan.md) for full documentation.

---

### `/gvs:reachability` - Check Symbol Reachability

Check if a specific symbol is reachable from entry points in a repository. Auto-detects repository from current directory if not specified.

```bash
# Check in current repository
/gvs:reachability golang.org/x/net/html Parse

# Check in external repository
/gvs:reachability golang.org/x/net/html Parse https://github.com/org/repo
```

See [commands/reachability.md](commands/reachability.md) for full documentation.

---

### `/gvs:reflection` - Analyze Reflection Risks

Analyze code for reflection patterns that could invoke vulnerable symbols at runtime. Auto-detects repository from current directory if not specified.

```bash
# Analyze current repository
/gvs:reflection

# Analyze external repository
/gvs:reflection https://github.com/kubernetes/kubernetes
```

See [commands/reflection.md](commands/reflection.md) for full documentation.

---

### `/gvs:call-graph` - Generate Call Graph

Generate SVG call graph visualization showing the path to vulnerable symbols. Auto-detects repository from current directory if not specified.

```bash
# Generate call graph for current repository
/gvs:call-graph CVE-2024-45338

# Generate call graph for external repository
/gvs:call-graph CVE-2024-45338 https://github.com/org/repo
```

See [commands/call-graph.md](commands/call-graph.md) for full documentation.

## Reference Files

| File | Purpose |
|------|---------|
| [reference/mcp-tools.md](reference/mcp-tools.md) | MCP tool signatures and parameters |

## Call Graph Algorithms

Several commands support different call graph algorithms:

| Algorithm | Speed | Precision | Best For |
|-----------|-------|-----------|----------|
| `static` | Fastest | Lowest | Quick checks |
| `cha` | Fast | Low | Class hierarchy analysis |
| `rta` | Medium | Medium | Reflection-heavy code (default) |
| `vta` | Slowest | Highest | Maximum precision |

## Troubleshooting

### "MCP server 'gvs' not found" or "GVS MCP server is not configured"

The MCP server is not configured. Run `/gvs:setup` to configure it, or follow the manual setup instructions in the Prerequisites section.

### "GET requires an active session"

The GVS server requires SSE transport. Ensure you're connecting via the `/sse` endpoint:
- Correct: `http://gvs.gsslab.pnq2.redhat.com:8083/sse`
- Wrong: `http://gvs.gsslab.pnq2.redhat.com:8083/`

### Connection timeout

Verify the GVS server is accessible from your network:

```bash
curl -s http://gvs.gsslab.pnq2.redhat.com:8083/
```

You may need to be connected to the Red Hat network or VPN.

### Tool not found

Ensure the MCP server is properly configured with the name `gvs` (lowercase).

## Contributing

Contributions welcome! Please submit pull requests to the [ai-helpers repository](https://github.com/openshift-eng/ai-helpers).

## License

Apache-2.0
