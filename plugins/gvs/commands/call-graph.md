---
description: Generate call graph visualization for a CVE vulnerability path
argument-hint: <CVE-ID> [repo-url] [--branch <branch>] [--algorithm <algo>] [--symbol <symbol>]
---

## Name
gvs:call-graph

## Synopsis
```text
/gvs:call-graph <CVE-ID> [repo-url] [options]
```

## Description
The `gvs:call-graph` command generates an SVG call graph visualization showing the path from entry points to a vulnerable symbol. This helps understand how your code reaches a vulnerable function.

If no repository URL is provided, the command auto-detects the repository from the current working directory's `.git` configuration.

The generated SVG shows:
- Entry points (main functions, test functions)
- Intermediate function calls
- The vulnerable symbol at the end of the path

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
- `toolName`: "get_call_graph"
- `arguments`:
  ```json
  {
    "repo": "<repo-url>",
    "cve": "<CVE-ID>",
    "branch": "<branch>",
    "algorithm": "<algo>",
    "symbol": "<symbol>"
  }
  ```

### Step 3: Display results

- Save SVG to a local file
- Display the call graph visualization
- Provide path to the saved SVG file

## Return Value

- **svg**: SVG visualization of the call graph (string containing SVG markup)

## Examples

1. **Generate call graph for a CVE in current repo**:
   ```text
   /gvs:call-graph CVE-2024-45338
   ```

2. **Generate call graph for external repository**:
   ```text
   /gvs:call-graph CVE-2024-45338 https://github.com/org/repo
   ```

3. **Use high-precision algorithm**:
   ```text
   /gvs:call-graph CVE-2024-45338 --algorithm vta
   ```

4. **Trace specific symbol**:
   ```text
   /gvs:call-graph CVE-2024-45338 --symbol Parse
   ```

## Arguments

- `$1` - **CVE-ID** *(required)*: CVE ID to trace (e.g., CVE-2024-1234)
- `$2` - **repo-url** *(optional)*: Git repository URL to analyze (public repositories only). If omitted, auto-detects from current directory's `.git` configuration.
- `--branch` *(optional)*: Branch name or commit hash. If omitted and using local repo, uses current branch.
- `--algorithm` *(optional)*: Call graph algorithm:
  - `static` - Fastest, least precise
  - `cha` - Class hierarchy analysis
  - `rta` - Rapid type analysis (default)
  - `vta` - Variable type analysis (slowest, highest precision)
- `--symbol` *(optional)*: Specific symbol to trace (defaults to first vulnerable symbol found)

## Output

The command saves the SVG visualization to:
```text
.work/gvs/call-graph/<CVE-ID>/graph.svg
```

## See Also

- `/gvs:scan` - Scan for CVE vulnerabilities
- `/gvs:reachability` - Check symbol reachability
- `/gvs:reflection` - Analyze reflection patterns
