---
description: Analyze code for reflection patterns that could invoke vulnerable symbols
argument-hint: "[repo-url] [--branch <branch>] [--algorithm <algo>] [--cve <CVE-ID>]"
---

## Name
gvs:reflection

## Synopsis
```text
/gvs:reflection [repo-url] [options]
```

## Description
The `gvs:reflection` command analyzes Go code for reflection patterns that could invoke vulnerable symbols at runtime. It detects patterns like:

- `reflect.ValueOf` / `reflect.TypeOf`
- `MethodByName` / `FieldByName`
- Function registries
- Dynamic dispatch patterns

If no repository URL is provided, the command auto-detects the repository from the current working directory's `.git` configuration.

Reflection can bypass static call graph analysis, making it important to identify code that might invoke vulnerable functions through reflection.

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
- `toolName`: "analyze_reflection_risks"
- `arguments`:
  ```json
  {
    "repo": "<repo-url>",
    "branch": "<branch>",
    "algorithm": "<algo>",
    "cve": "<CVE-ID>"
  }
  ```

### Step 3: Display results

- Show summary of reflection usage
- List reflection risks by confidence level (high/medium/low)
- Display locations and evidence for each risk
- Show affected packages and symbols

## Return Value

- **repo**: Repository analyzed
- **branch**: Branch analyzed
- **algorithm**: Algorithm used
- **unsafe_usage**: Whether `unsafe` package is used (boolean)
- **reflect_usage**: Whether `reflect` package is used (boolean)
- **risk_count**: Total number of reflection risks found
- **high_confidence_risks**: Count of high-confidence risks
- **medium_confidence_risks**: Count of medium-confidence risks
- **low_confidence_risks**: Count of low-confidence risks
- **reflection_risks**: Array of detailed risk objects:
  - `type`: Type of reflection pattern
  - `confidence`: Risk confidence level
  - `location`: File and line location
  - `evidence`: Code patterns detected
  - `symbol`: Affected symbol
  - `package`: Affected package
- **summary**: Human-readable summary

## Examples

1. **Analyze current repository for reflection risks**:
   ```text
   /gvs:reflection
   ```

2. **Analyze external repository**:
   ```text
   /gvs:reflection https://github.com/kubernetes/kubernetes
   ```

3. **Targeted analysis for a CVE**:
   ```text
   /gvs:reflection --cve CVE-2024-1234
   ```

4. **Use RTA algorithm (best for reflection)**:
   ```text
   /gvs:reflection --algorithm rta
   ```

## Arguments

- `$1` - **repo-url** *(optional)*: Git repository URL to analyze (public repositories only). If omitted, auto-detects from current directory's `.git` configuration.
- `--branch` *(optional)*: Branch name or commit hash. If omitted and using local repo, uses current branch.
- `--algorithm` *(optional)*: Call graph algorithm:
  - `static` - Fastest, least precise
  - `cha` - Class hierarchy analysis
  - `rta` - Rapid type analysis (default, best for reflection)
  - `vta` - Variable type analysis (slowest, highest precision)
- `--cve` *(optional)*: CVE ID for targeted analysis

## See Also

- `/gvs:scan` - Scan for CVE vulnerabilities
- `/gvs:reachability` - Check symbol reachability
- `/gvs:call-graph` - Generate call graph visualization
