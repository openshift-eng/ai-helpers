---
description: Look up CVE details from the Go vulnerability database
argument-hint: <CVE-ID>
---

## Name
gvs:lookup

## Synopsis
```text
/gvs:lookup <CVE-ID>
```

## Description
The `gvs:lookup` command retrieves CVE details from the Go vulnerability database. It returns affected packages, vulnerable symbols, and fixed versions without scanning any repository.

Use this command to quickly understand a CVE's impact on Go packages before scanning your codebase.

## Implementation

### Step 0: Verify MCP Server Configuration

Before proceeding, verify the GVS MCP server is configured:

1. **Check if "gvs" MCP server is available**
   - If not configured, inform the user and suggest running `/gvs:setup`
   - Display: "GVS MCP server is not configured. Run `/gvs:setup` to configure it."

### Step 1: Parse and Call

1. **Parse the CVE ID argument**
   - Accept CVE ID (e.g., CVE-2024-1234) or GO-ID (e.g., GO-2024-1234)

2. **Call the MCP tool**
   - Use `CallMcpTool` with:
     - `server`: "gvs"
     - `toolName`: "lookup_cve"
     - `arguments`: `{ "cve": "<CVE-ID>" }`

3. **Display results**
   - Show Go vulnerability ID and CVE ID
   - List affected packages with vulnerable version ranges
   - Show vulnerable symbols/functions
   - Display fixed versions
   - Include any aliases (GHSA, etc.)

## Return Value

- **go_id**: Go vulnerability database ID
- **cve_id**: CVE identifier
- **aliases**: Related identifiers (GHSA, etc.)
- **affected**: List of affected packages with:
  - Package path
  - Vulnerable version ranges
  - Fixed versions
  - Vulnerable symbols

## Examples

1. **Look up a CVE**:
   ```text
   /gvs:lookup CVE-2024-45338
   ```

2. **Look up using GO-ID**:
   ```text
   /gvs:lookup GO-2024-3333
   ```

## Arguments

- `$1` - **CVE-ID** *(required)*: The CVE identifier or GO-ID to look up (e.g., CVE-2024-1234, GO-2024-1234)

## See Also

- `/gvs:scan` - Scan a repository for vulnerabilities
- `/gvs:check-package` - Check if a specific package version is vulnerable
