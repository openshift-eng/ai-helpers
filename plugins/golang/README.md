# Golang Plugin

A Claude Code plugin for running [golangci-lint](https://golangci-lint.run/) to check and fix code quality issues in Go projects.


## Installation

```bash
/plugin install golang@ai-helpers
```

## Commands

| Command | Description |
|---------|-------------|
| `/golang:lint-fix` | Run golangci-lint and automatically fix all reported issues |

## Skills

| Skill | Description |
|-------|-------------|
| Go Lint | Detects and runs golangci-lint using the best available method for the repository. Loaded automatically when linting is relevant, and used by both commands above. |

## Prerequisites

- go compiler (available in $PATH)

- **Optional**: `make lint` target configured in Makefile, if not present the command will run `golangci-lint` directly.

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

### `/golang:lint`: check for linter issues

This will:
1. Run golangci-lint using available methods (via the "Go Lint" skill)
2. Report total number of issues found
3. Summarize issues by category (goconst, gocyclo, staticcheck, etc.)
4. Show example issues

The "Go Lint" skill is also loaded automatically when the agent detects that linting is needed (e.g., the user says "run the linter" or "check for lint issues").

### `/golang:lint-fix`: check for linter issues and fix them

This will:
1. Run the "Go Lint" skill to identify all issues
2. Systematically fix each category of issues
3. Re-run linter after each fix to verify
4. Continue until all issues are resolved
