---
description: Check if a symbol is reachable from entry points in a repository
argument-hint: <package> <symbol> [repo-url] [--branch <branch>] [--algorithm <algo>] [--graph]
---

## Name
gvs:reachability

## Synopsis
```text
/gvs:reachability <package> <symbol> [repo-url] [options]
```

## Description
The `gvs:reachability` command checks if a specific symbol (function, method) from any Go package is reachable from entry points in a repository. Use this to manually verify if code can call a particular function without needing a CVE ID.

If no repository URL is provided, the command auto-detects the repository from the current working directory's `.git` configuration.

This is useful for:
- Verifying if a vulnerable function is actually called
- Understanding code dependencies
- Auditing third-party package usage

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

### Step 2: Call the MCP tool

Use `CallMcpTool` with:
- `server`: "gvs"
- `toolName`: "check_symbol_reachability"
- `arguments`: 
  ```json
  {
    "repo": "<repo-url>",
    "package": "<package>",
    "symbol": "<symbol>",
    "branch": "<branch>",
    "algorithm": "<algo>",
    "generate_graph": true/false
  }
  ```

### Step 3: Display results

- Show reachability status (reachable/not reachable)
- Display the call path if reachable
- Show entry point that reaches the symbol
- Display SVG visualization if requested

## Return Value

- **repo**: Repository analyzed
- **branch**: Branch analyzed
- **package**: Package containing the symbol
- **symbol**: Symbol checked
- **algorithm**: Call graph algorithm used
- **is_reachable**: Whether the symbol is reachable (boolean)
- **entry_point**: The entry point that can reach the symbol
- **call_path**: Array showing the call chain from entry to symbol
- **graph_svg**: SVG visualization (if requested)
- **summary**: Human-readable summary

## Examples

1. **Check if html.Parse is reachable in current repo**:
   ```text
   /gvs:reachability golang.org/x/net/html Parse
   ```

2. **Check SSH function reachability in current repo**:
   ```text
   /gvs:reachability golang.org/x/crypto/ssh NewServerConn
   ```

3. **Check in external repository**:
   ```text
   /gvs:reachability golang.org/x/net/html Parse https://github.com/org/repo
   ```

4. **Generate call graph visualization**:
   ```text
   /gvs:reachability golang.org/x/net/html Parse --graph
   ```

5. **Use high-precision algorithm**:
   ```text
   /gvs:reachability golang.org/x/net/html Parse --algorithm vta
   ```

## Arguments

- `$1` - **package** *(required)*: Full Go package path (e.g., `golang.org/x/crypto/ssh`)
- `$2` - **symbol** *(required)*: Symbol name to check (e.g., `NewServerConn`, `Parse`)
- `$3` - **repo-url** *(optional)*: Git repository URL to analyze (public repositories only). If omitted, auto-detects from current directory's `.git` configuration.
- `--branch` *(optional)*: Branch name or commit hash. If omitted and using local repo, uses current branch.
- `--algorithm` *(optional)*: Call graph algorithm:
  - `static` - Fastest, least precise
  - `cha` - Class hierarchy analysis
  - `rta` - Rapid type analysis (default)
  - `vta` - Variable type analysis (slowest, highest precision)
- `--graph` *(optional)*: Generate SVG call graph visualization

## See Also

- `/gvs:scan` - Scan for CVE vulnerabilities
- `/gvs:call-graph` - Generate call graph for a CVE
- `/gvs:reflection` - Analyze reflection patterns
