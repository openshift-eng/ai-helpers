---
name: lint-fix
description: Run golangci-lint and fix all reported issues. Use only when explicitly asked to fix lint issues in a Go project.
disable-model-invocation: true
model: sonnet
context: fork
allowed-tools: Bash(golangci-lint *) Bash(grep *) Bash(make lint) Bash(make verify-lint) Read Edit(**/*.go)
---

# Go Lint Fix

Run `golangci-lint` and fix all reported issues, using auto-fix first then AI for the rest.

## Discovery

This skill always calls `golangci-lint` directly (required for `--fix`). Discovery finds any project-specific flags, config, or plugins to carry into those calls.

1. **CLAUDE.md / AGENTS.md**: Check for linting instructions. Note any flags, config paths, or constraints documented there.
2. **Makefile targets**: Check for `lint` or `verify-lint` targets (`grep -E "^(lint|verify-lint):" Makefile`). Inspect the target body to extract flags such as `--config`, `--timeout`, `--build-tags`, or module plugin references.
3. **Fallback**: Use `golangci-lint run ./...` with no extra flags.

Collect all discovered flags into a `$FLAGS` variable used throughout the Fix Process.

## If golangci-lint Is Not Found

Report that `golangci-lint` is not available and direct the user to the [installation docs](https://golangci-lint.run/welcome/install/). Do not auto-install.

## Fix Process

1. **Baseline**: Run `golangci-lint run $FLAGS ./...` and record the issue count.
2. **Auto-fix**: Run `golangci-lint run --fix $FLAGS ./...` to resolve all automatically fixable issues.
3. **Re-check**: Run `golangci-lint run $FLAGS ./...` again to see remaining issues.
4. **AI fixes**: For each remaining issue, fix it directly in the source file.
5. **Verify**: Re-run `golangci-lint run $FLAGS ./...` after each batch of AI fixes.
6. **Loop**: Repeat steps 4–5 until the output is clean or no further progress is made.

## Guidelines

- **Prefer real fixes** over `//nolint` directives. Use `//nolint` only as a last resort with a comment explaining why.
- **Generated files**: Do not modify files with a `// Code generated` header. Add `//nolint` at the call site or exclude the file in `.golangci.yml` instead.
- **Constants**: Before adding a new constant to fix a magic-number lint error, check whether an equivalent constant already exists in the package or its imports.
