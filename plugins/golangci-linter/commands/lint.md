---
description: Run golangci-lint to check for code quality issues
---

## Name
golangci-linter:lint

## Synopsis
```
/golangci-linter:lint
```

## Description
The `golangci-linter:lint` command runs golangci-lint to check for code quality issues in the current Go repository. This is a **read-only** command that reports issues without making any changes to the codebase.

The command automatically detects the best way to run golangci-lint based on what's available in the project, trying multiple approaches in order of preference.

## Implementation

Try the following approaches in order:
1. First try: `golangci-lint run`
2. If golangci-lint is not found, try: `make lint` (if Makefile exists)
3. If neither works, check if golangci-lint is in a local bin directory:
   - `./bin/golangci-lint run`
   - `$(go env GOPATH)/bin/golangci-lint run`

After running the linter:
1. Report the total number of issues found
2. Summarize the issues by category (e.g., goconst, gocyclo, staticcheck, etc.)
3. Show the first few issues as examples
4. If there are no issues, confirm that the code passes all linter checks

**Do not fix any issues** - only report what was found.

If golangci-lint is not installed, inform the user how to install it:
- macOS/Linux: `curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin`
- Or using go install: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

## Return Value
- **Format**: Text report summarizing linter findings
- **Success**: List of issues grouped by category with counts
- **No issues**: Confirmation message that code passes all checks
- **Error**: Installation instructions if golangci-lint is not found

## Examples

1. **Basic usage**:
   ```text
   /golangci-linter:lint
   ```
   Output:
   ```text
   Found 15 issues:
   - goconst: 5 issues
   - staticcheck: 4 issues
   - gocyclo: 3 issues
   - revive: 3 issues

   Example issues:
   - pkg/api/handler.go:42: string "application/json" has 3 occurrences (goconst)
   - pkg/utils/helper.go:87: cyclomatic complexity 15 of function ProcessData (gocyclo)
   ```

2. **Clean codebase**:
   ```text
   /golangci-linter:lint
   ```
   Output:
   ```text
   ✓ Code passes all linter checks (0 issues found)
   ```

## Arguments
This command takes no arguments.
