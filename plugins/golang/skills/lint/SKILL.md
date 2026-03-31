---
name: Go Lint
description: Detect and run golangci-lint in a Go repository using the best available method
---

# Go Lint

This skill detects the best way to run golangci-lint in the current Go repository and executes it, reporting results in a structured summary.

## When to Use This Skill

Use this skill when:
- The user asks to run the linter, check for lint issues, or verify code quality in a Go project
- Another command needs to run golangci-lint as a prerequisite step (e.g., `golang:lint-fix`)
- The agent decides linting is needed before committing Go code changes

## Prerequisites

- A Go repository (contains `go.mod`)
- `golangci-lint` installed, or the ability to install it (see Step 6 below)

## Implementation Steps

### Step 1: Detect the Lint Command

Try the following approaches in order. Proceed to Step 2 once any approach succeeds:

1. **Check project documentation first** - Read `AGENTS.md` or `CLAUDE.md` in the repository root (if they exist) and look for linting instructions (e.g., `make lint`, `make verify`, specific golangci-lint commands, or other linter commands). If found, use those instructions.

2. **Check for lint scripts** - Many repositories (especially OpenShift projects) have scripts that run golangci-lint in a containerized way with repo-specific configuration. Check for these patterns and run if found:
   - `hack/go-lint.sh`
   - `hack/lint.sh`
   - `hack/verify-golangci-lint.sh`
   - `hack/verify-lint.sh`
   - `scripts/go-lint.sh`
   - `scripts/lint.sh`
   - Or any other `*lint*.sh` script in `hack/` or `scripts/` directories

3. **Check the Makefile** - Look for a make target like `make lint` or `make verify-lint`, and run it.

4. **Run golangci-lint directly** - Try: `golangci-lint run`

5. **Try GOPATH binary** - If golangci-lint was not found on PATH, try:
   - `$(go env GOPATH)/bin/golangci-lint run`

6. **Install golangci-lint** - If not installed, inform the user how to install it:
   - macOS/Linux: `curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin`
   - Or using go install: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`
   - Then retry from step 4.

### Step 2: Handle Configuration

During the linter run:
- If the codebase contains an existing `.golangci.yml` or `.golangci.yaml`, use it with `golangci-lint run --config=<path>`
- If there are issues with a missing config, try with `golangci-lint run --noconfig`

### Step 3: Report Results

After running the linter:
1. Report the total number of issues found
2. Summarize the issues by category (e.g., goconst, gocyclo, staticcheck, etc.)
3. Show the first 2-3 issues as examples
4. If there are no issues, confirm that the code passes all linter checks

**Do not attempt to fix any issues** - this skill is read-only.

## Output Format

- **Success with issues**:
  ```
  Found 15 issues:
  - goconst: 5 issues
  - staticcheck: 4 issues
  - gocyclo: 3 issues
  - revive: 3 issues

  Example issues:
  - pkg/api/handler.go:42: string "application/json" has 3 occurrences (goconst)
  - pkg/utils/helper.go:87: cyclomatic complexity 15 of function ProcessData (gocyclo)
  ```

- **No issues**:
  ```
  Code passes all linter checks (0 issues found)
  ```

- **Error**: Installation instructions if golangci-lint could not be installed or run

## Important Notes

- Remember the exact `golangci-lint` command that was used, as callers (like `golang:lint-fix`) may need it
- If the user passes additional flags, chain them to the `golangci-lint` invocation (e.g., `--tests`, `--concurrency 4`)
- Do not run with `--fix`; if the user wants fixes, direct them to the `/golang:lint-fix` command
