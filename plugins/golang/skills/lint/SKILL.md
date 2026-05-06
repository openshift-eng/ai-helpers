---
name: lint
description: Run golangci-lint to check Go code quality. Use when the user asks to lint, check for lint issues, or verify code quality in a Go project, or when linting is appropriate before committing Go code changes.
model: haiku
allowed-tools: Bash(golangci-lint *) Bash(grep *) Bash(make lint) Bash(make verify-lint) Read
paths:
  - "**/*.go"
  - ".golangci.yml"
  - ".golangci.yaml"
---

# Go Lint

Run `golangci-lint` to check Go code quality and report issues.

## Discovery

Find how to run the linter using this cascade — stop at the first match:

1. **CLAUDE.md / AGENTS.md**: Check for instructions about linting. If a lint command is documented, use it.
2. **Makefile targets**: Check for `lint` or `verify-lint` targets (`grep -E "^(lint|verify-lint):" Makefile`). If found, run `make lint` or `make verify-lint`.
3. **Direct invocation**: Run `golangci-lint run ./...`

## If golangci-lint Is Not Found

Report that `golangci-lint` is not available and direct the user to the [installation docs](https://golangci-lint.run/welcome/install/). Do not auto-install.

## Output

Use this format when issues are found:

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

When clean:

```text
Code passes all linter checks (0 issues found)
```

## Constraint

This skill is **read-only**. Never modify files or attempt fixes. Use the `golang:lint-fix` skill for that.

If the user passes additional flags, chain them to the `golangci-lint` invocation (e.g., `--tests`, `--concurrency 4`).
