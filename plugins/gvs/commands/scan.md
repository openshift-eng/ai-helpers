---
description: Scan a Go repository for CVE vulnerabilities
argument-hint: "[repo-url] [CVE-ID] [--branch <branch>] [--algorithm <algo>] [--graph]"
---

## Name
gvs:scan

## Synopsis
```text
/gvs:scan [repo-url] [CVE-ID] [options]
```

## Description
The `gvs:scan` command scans a Go repository for vulnerabilities. It supports two modes:

1. **Full scan** (no CVE specified): Discovers ALL known vulnerabilities using govulncheck
2. **Targeted scan** (CVE specified): Performs deep call graph analysis to determine if vulnerable code is reachable

If no repository URL is provided, the command auto-detects the repository from the current working directory's `.git` configuration.

For targeted scans, the command uses call graph analysis to verify if the vulnerable code paths are actually reachable from your application's entry points.

## Implementation

### Step 0: Verify MCP Server Configuration

Before proceeding, verify the GVS MCP server is configured:

1. **Check if "gvs" MCP server is available**
   - If not configured, inform the user and suggest running `/gvs:setup`
   - Display: "GVS MCP server is not configured. Run `/gvs:setup` to configure it."

### Step 1: Detect Repository (if not provided)

If no repository URL is provided as an argument:

1. **Check for `.git` directory**
   - Verify the current directory is a Git repository
   - If not, inform user and ask for repository URL

2. **Get remote URL**
   ```bash
   # List available remotes
   git remote -v
   
   # Use first available remote
   REMOTE=$(git remote | head -1)
   git remote get-url "$REMOTE"
   ```
   - Use the first available remote
   - If multiple remotes exist, use whichever is listed first
   - If no remotes configured, inform user and ask for repository URL

3. **Convert SSH to HTTPS format**
   - If URL is `git@github.com:org/repo.git` → convert to `https://github.com/org/repo`
   - If URL is `ssh://git@github.com/org/repo.git` → convert to `https://github.com/org/repo`
   - If URL is already HTTPS → use as-is
   - Remove `.git` suffix if present

4. **Get current branch/commit**
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   - If detached HEAD, use commit hash: `git rev-parse HEAD`

### Step 2: Full Scan (no CVE specified)

1. **Call the MCP tool**
   - Use `CallMcpTool` with:
     - `server`: "gvs"
     - `toolName`: "scan_all_vulnerabilities"
     - `arguments`: `{ "repo": "<repo-url>", "branch": "<branch>" }`

2. **Display results**
   - Show total vulnerabilities found
   - List each CVE with affected packages
   - Show modules scanned

### Step 3: Targeted Scan (with CVE)

1. **Call the MCP tool**
   - Use `CallMcpTool` with:
     - `server`: "gvs"
     - `toolName`: "scan_vulnerability"
     - `arguments`: `{ "repo": "<repo-url>", "cve": "<CVE-ID>", "branch": "<branch>", "algorithm": "<algo>", "generate_graph": true/false }`

2. **Display results**
   - Show vulnerability status (vulnerable/not vulnerable/unknown)
   - Display call path if vulnerable
   - Show reflection risks if detected
   - Display SVG call graph if requested

## Return Value

### Full Scan
- **repo**: Repository scanned
- **branch**: Branch analyzed
- **modules_scanned**: Number of Go modules scanned
- **total_vulnerabilities**: Count of vulnerabilities found
- **output**: Detailed vulnerability list

### Targeted Scan
- **is_vulnerable**: Vulnerability status ("true", "false", "unknown")
- **cve**: CVE ID checked
- **summary**: Human-readable summary
- **algorithm**: Call graph algorithm used
- **graph_svg**: SVG visualization (if requested)
- **reflection_risks**: Potential reflection-based risks

## Examples

1. **Scan current repository for all vulnerabilities**:
   ```text
   /gvs:scan
   ```

2. **Scan current repository for specific CVE**:
   ```text
   /gvs:scan CVE-2024-45338
   ```

3. **Scan external repository**:
   ```text
   /gvs:scan https://github.com/kubernetes/kubernetes
   ```

4. **Scan specific branch**:
   ```text
   /gvs:scan https://github.com/kubernetes/kubernetes --branch release-1.29
   ```

5. **Targeted scan with visualization**:
   ```text
   /gvs:scan CVE-2024-1234 --graph
   ```

6. **Use different algorithm**:
   ```text
   /gvs:scan CVE-2024-1234 --algorithm vta
   ```

## Arguments

- `$1` - **repo-url** *(optional)*: Git repository URL to scan (public repositories only). If omitted, auto-detects from current directory's `.git` configuration.
- `$2` - **CVE-ID** *(optional)*: Specific CVE to check (omit for full scan). It can be the first argument if repo-url is omitted.
- `--branch` *(optional)*: Branch name or commit hash. If omitted and using local repo, uses current branch.
- `--algorithm` *(optional)*: Call graph algorithm for targeted scans:
  - `static` - Fastest, least precise
  - `cha` - Class hierarchy analysis
  - `rta` - Rapid type analysis (default, good for reflection)
  - `vta` - Variable type analysis (slowest, highest precision)
- `--graph` *(optional)*: Generate SVG call graph visualization

## See Also

- `/gvs:lookup` - Look up CVE details
- `/gvs:reachability` - Check symbol reachability
- `/gvs:call-graph` - Generate call graph visualization
