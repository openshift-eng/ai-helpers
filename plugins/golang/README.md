# Golang Plugin

A Claude Code plugin for Go development, providing LSP integration via `gopls` and automatic `gofmt` formatting.

## Installation

```bash
/plugin install golang@ai-helpers
```

## Features

### gopls MCP Server

Integrates the `gopls` language server as an MCP server, providing Go-aware code intelligence including go-to-definition, find references, hover documentation, and workspace symbols.

### Automatic gofmt Formatting

A PostToolUse hook automatically runs `gofmt -w -s` on any `.go` file after it is written or edited, keeping code consistently formatted without manual intervention.

### LSP Integration (via dependency)

Depends on the `gopls-lsp` plugin from `claude-plugins-official`, which enables LSP-based operations for Go code navigation and analysis.

## Prerequisites

- Go toolchain with `gopls` and `gofmt` available in `$PATH`
- `golangci-lint` available in `$PATH` (required by the `golang:lint` and `golang:lint-fix` skills)

Install `gopls` if not already present:

```bash
go install golang.org/x/tools/gopls@latest
```

Install `golangci-lint` if not already present:

```bash
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

## Skills

### `golang:lint`

Runs `golangci-lint` to check Go code quality. Discovers the lint command via CLAUDE.md/AGENTS.md, Makefile targets (`lint`, `verify-lint`), or direct `golangci-lint run ./...` invocation. Reports total issue count, breakdown by linter, and examples. Read-only — never modifies files.

Invoked automatically when linting is appropriate (e.g., before committing Go changes), or on demand.

### `golang:lint-fix`

Runs `golangci-lint --fix` to auto-fix issues, then uses AI to resolve any remaining ones iteratively until the output is clean. Uses the same discovery cascade as `golang:lint`.

User-invocable only (`/golang:lint-fix`) — not triggered automatically due to its destructive nature.

## Dependencies

| Plugin | Marketplace | Purpose |
|--------|-------------|---------|
| `gopls-lsp` | `claude-plugins-official` | LSP integration for Go code intelligence |
