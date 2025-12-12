# Golang Plugin

A Claude Code plugin for Go code quality analysis, linting, and modernization.


## Installation

```bash
/plugin install golang@ai-helpers
```

## Commands

| Command | Description |
|---------|-------------|
| `/golang:lint-fix` | Run golangci-lint and automatically fix all reported issues |
| `/golang:improve` | Analyze and fix Go code quality issues using gopls and go vet |

## Skills

| Skill | Description |
|-------|-------------|
| Go Lint | Detects and runs golangci-lint using the best available method for the repository. Loaded automatically when linting is relevant, and used by both commands above. |

## Prerequisites

- go compiler (available in $PATH)

- **Optional**: `make lint` target configured in Makefile, if not present the command will run `golangci-lint` directly.

- **Optional**: `gopls` (Go language server) for `/golang:improve`: `go install golang.org/x/tools/gopls@latest`

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

### `/golang:lint-fix`: check for linter issues and fix them

This will:
1. Run golangci-lint using available methods (via the "Go Lint" skill)
2. Systematically fix each category of issues
3. Re-run linter after each fix to verify
4. Continue until all issues are resolved

### `/golang:improve`: analyze and fix code quality issues

This will:
1. Run `gopls check` and `go vet` to find issues
2. Categorize findings by severity (critical bugs, deprecated APIs, modernization, code quality)
3. Automatically apply all fixes
4. Verify changes with build and tests
