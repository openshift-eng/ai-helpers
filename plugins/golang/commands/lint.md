---
description: Run golangci-lint tool to check for code quality issues
---

## Name
golang:lint

## Synopsis
```
/golang:lint
/golang:lint [<linter-flags>]
```

## Description
This command runs golangci-lint to check for code quality issues in the current Go repository. This is a read-only command that reports issues without making any changes to the codebase.

The command automatically detects the best way to run golangci-lint based on what's available in the project, trying multiple approaches in order of preference.

## Implementation

**Phase 1**: Try the following approaches in order (proceed to Phase 2 once any approach succeeds):
1. Check for a lint script in common locations - many repositories (especially OpenShift projects) have scripts that run golangci-lint in a containerized way with repo-specific configuration. Check for these patterns and run if found:
   - `hack/go-lint.sh`
   - `hack/lint.sh`
   - `hack/verify-golangci-lint.sh`
   - `hack/verify-lint.sh`
   - `scripts/go-lint.sh`
   - `scripts/lint.sh`
   - Or any other `*lint*.sh` script in `hack/` or `scripts/` directories
2. Check the Makefile in the directory and look for a make target like `make lint` or `make verify-lint`, run it
3. If neither of the above exist, try: `golangci-lint run`
4. If golangci-lint tool was not found on path, try:
   - `$(go env GOPATH)/bin/golangci-lint run`
5. If golangci-lint is not installed, inform the user how to install it:
   - macOS/Linux: `curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin`
   - Or using go install: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
   - and retry running from step 3.

During the linter run:
- Fix any encountered issues like a missing golang `golangci.yaml` configuration,
   Alternatively, try with `golangci-lint run --noconfig`
- If the codebase contains an existing `golangci.yaml`
   use it with `golangci-lint run --config=<path>`

**Phase 2**: After running the linter tool:
1. Report the total number of issues found
2. Summarize the issues by category (e.g., goconst, gocyclo, staticcheck, etc.)
3. Show the first 2-3 issues as examples
4. If there are no issues, confirm that the code passes all linter checks

+**Do not attempt to fix any issues yet**.

## Return Value
- **Format**: Text report summarizing linter findings
- **Success**: List of issues grouped by category with counts
- **No issues**: Confirmation message that code passes all checks
- **Error**: Installation instructions if golangci-lint was unable to be installed or run succesfully

## Examples

1. **Basic usage**:
   ```text
   /golang:lint
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
   /golang:lint
   ```
   Output:
   ```text
   ✓ Code passes all linter checks (0 issues found)
   ```

## Arguments

- **$1** (flags): Optional. Arbitrary flags to be passed to the golangci-lint utility.
  - Any arguments passed to this command will be chained to the `golangci-lint` tool directly eg. `--tests`,  `--concurrency 4`, `--config /path/to/golangci.yaml`, etc.
  - Do not allow running this command with `--fix` instead ask the user to use the other `/golang:lint-fix` command.

## Examples
- `/golang:lint --tests` will run `golangci-lint run --tests`
- `/golang:lint --concurrency 4 --config /path/to/golangci.yaml` will run `golangci-lint run --concurrency 4 --config /path/to/golangci.yaml` 
