# golangci-linter Plugin

A Claude Code plugin for running [golangci-lint](https://golangci-lint.run/) to check and fix code quality issues in Go projects.

## Commands

| Command | Description |
|---------|-------------|
| `/golangci-linter:lint` | Run golangci-lint to check for code quality issues (read-only) |
| `/golangci-linter:lint-fix` | Run golangci-lint and automatically fix all reported issues |

## Prerequisites

- Go project with golangci-lint configured
- One of the following:
  - `golangci-lint` installed globally
  - `make lint` target in your Makefile
  - `./bin/golangci-lint` in your project

## Recommended Permissions

To allow Claude Code to run the linter commands without prompting for approval, add the following to your project's `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(curl -s https://api.github.com/repos/golangci/golangci-lint/releases/latest)",
      "Bash(make golangci-lint:*)",
      "Bash(./bin/golangci-lint:*)",
      "Bash(GOBIN=/tmp go install:*)",
      "Bash(/tmp/golangci-lint:*)",
      "Bash(make lint:*)",
      "Bash(make lint)"
    ]
  }
}
```

### What these permissions allow:

| Permission | Purpose |
|------------|---------|
| `curl ... golangci-lint/releases/latest` | Check for latest golangci-lint version |
| `make golangci-lint:*` | Run make targets for golangci-lint installation |
| `./bin/golangci-lint:*` | Run golangci-lint from project's bin directory |
| `GOBIN=/tmp go install:*` | Install golangci-lint to /tmp for temporary use |
| `/tmp/golangci-lint:*` | Run golangci-lint from /tmp |
| `make lint:*`, `make lint` | Run the standard `make lint` target |

## Usage

### Check for issues (read-only)

```text
/golangci-linter:lint
```

This will:
1. Run golangci-lint using available methods
2. Report total number of issues found
3. Summarize issues by category (goconst, gocyclo, staticcheck, etc.)
4. Show example issues

### Fix all issues

```text
/golangci-linter:lint-fix
```

This will:
1. Run `make lint` to identify all issues
2. Systematically fix each category of issues
3. Re-run linter after each fix to verify
4. Continue until all issues are resolved

## Supported Linter Categories

The `lint-fix` command handles these common linter issues:

| Category | Fix Strategy |
|----------|--------------|
| **goconst** | Add constants for repeated strings (3+ occurrences) |
| **gocyclo** | Add `//nolint:gocyclo` for complex test functions |
| **prealloc** | Pre-allocate slices with known capacity |
| **revive** | Fix comment spacing (add space after `//`) |
| **staticcheck** | Fix deprecated code, naming conventions (ErrFoo for errors) |
| **unparam** | Remove unused parameters or always-nil error returns |



