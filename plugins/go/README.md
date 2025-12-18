# Go Plugin

A plugin for Go code quality and modernization tasks, helping developers identify and fix issues using static analysis tools.

## Commands

### `/go:improve`

Analyzes Go code using `gopls check` and `go vet` to identify and automatically fix:

- Deprecated API usage
- Code modernization opportunities
- Potential bugs and suspicious constructs
- Code quality issues

The command runs analysis tools, presents categorized findings, automatically applies fixes, and verifies the changes with tests.

See [commands/improve.md](commands/improve.md) for detailed documentation.

## Installation

```bash
/plugin install go@ai-helpers
```

## Prerequisites

- Go toolchain installed
- `gopls` (Go language server) installed: `go install golang.org/x/tools/gopls@latest`

## Usage Examples

```bash
# Analyze and fix the entire repository
/go:improve

# Analyze a specific package
/go:improve pkg/operator

# Analyze all packages under a path
/go:improve ./pkg/controllers/...
```
