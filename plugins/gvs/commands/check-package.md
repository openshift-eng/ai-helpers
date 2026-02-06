---
description: Check if a Go package version has known vulnerabilities
argument-hint: <package> <version>
---

## Name
gvs:check-package

## Synopsis
```text
/gvs:check-package <package> <version>
```

## Description
The `gvs:check-package` command checks if a specific Go package version has known vulnerabilities. It returns a list of CVEs affecting the package@version combination along with fix versions.

Use this command to quickly verify if a dependency in your `go.mod` is vulnerable before updating.

## Implementation

### Step 0: Verify MCP Server Configuration

Before proceeding, verify the GVS MCP server is configured:

1. **Check if "gvs" MCP server is available**
   - If not configured, inform the user and suggest running `/gvs:setup`
   - Display: "GVS MCP server is not configured. Run `/gvs:setup` to configure it."

### Step 1: Parse and Call

1. **Parse arguments**
   - Extract package path (e.g., `golang.org/x/net`)
   - Extract version (e.g., `v0.17.0`)

2. **Call the MCP tool**
   - Use `CallMcpTool` with:
     - `server`: "gvs"
     - `toolName`: "check_package_version"
     - `arguments`: `{ "package": "<package>", "version": "<version>" }`

3. **Display results**
   - Show package and version checked
   - Display vulnerability status (vulnerable/safe)
   - List CVEs affecting this version
   - Show fix versions for each CVE

## Return Value

- **package**: The Go package path checked
- **version**: The version checked
- **status**: Vulnerability status ("vulnerable" or "safe")
- **count**: Number of vulnerabilities found
- **vulnerabilities**: List of CVEs with details and fix versions

## Examples

1. **Check a specific package version**:
   ```text
   /gvs:check-package golang.org/x/net v0.17.0
   ```

2. **Check a crypto package**:
   ```text
   /gvs:check-package golang.org/x/crypto v0.14.0
   ```

3. **Check standard library package**:
   ```text
   /gvs:check-package stdlib v1.21.0
   ```

## Arguments

- `$1` - **package** *(required)*: Go package path (e.g., `golang.org/x/net`, `github.com/gin-gonic/gin`)
- `$2` - **version** *(required)*: Package version to check (e.g., `v0.17.0`, `v1.9.1`)

## See Also

- `/gvs:lookup` - Look up CVE details
- `/gvs:scan` - Scan a repository for all vulnerabilities
