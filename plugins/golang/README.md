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

### `golang:fix-cve`

Patches a Go module dependency to fix a CVE. Determines the right strategy based on Go version compatibility (direct update, Go patch bump, or `openshift-sustaining` fork replace), applies changes across all `go.mod` files, syncs vendors, and runs repo checks.

```bash
/golang:fix-cve module="google.golang.org/grpc" fix-version="v1.75.1" cve="CVE-2026-33186" ticket="OCPBUGS-83972"
```

### `golang:lint`

Runs `golangci-lint` to check Go code quality. Discovers the lint command via CLAUDE.md/AGENTS.md, Makefile targets (`lint`, `verify-lint`), or direct `golangci-lint run ./...` invocation. Reports total issue count, breakdown by linter, and examples. Read-only — never modifies files.

Invoked automatically when linting is appropriate (e.g., before committing Go changes), or on demand.

### `golang:lint-fix`

Runs `golangci-lint --fix` to auto-fix issues, then uses AI to resolve any remaining ones iteratively until the output is clean. Uses the same discovery cascade as `golang:lint`.

User-invocable only (`/golang:lint-fix`) — not triggered automatically due to its destructive nature.

### `golang:analyze-release-go-versions`

Filters and explains release Go builder, CI build-root, `go.mod` directive, and module version data using the scripts below.

## Release Go version scripts

Run these from the repository root with Python 3 and `oc`. They query GitHub through its API, falling back to existing `gh` access on HTTP 403/404. `--correlate-builder` and `--build-root` also require PyYAML.

```bash
RELEASE_IMAGE='registry.ci.openshift.org/ocp/release-5:5.1.0-0.nightly-2026-09-28-133913'
python3 plugins/golang/scripts/release_go_module_versions.py "$RELEASE_IMAGE" google.golang.org/protobuf
python3 plugins/golang/scripts/release_go_module_versions.py "$RELEASE_IMAGE" --go-version
python3 plugins/golang/scripts/release_go_builder_versions.py "$RELEASE_IMAGE"
python3 plugins/golang/scripts/release_go_builder_versions.py "$RELEASE_IMAGE" --correlate-builder
python3 plugins/golang/scripts/release_go_builder_versions.py "$RELEASE_IMAGE" --build-root
python3 plugins/golang/scripts/release_go_builder_versions.py "$RELEASE_IMAGE" --correlate-builder --build-root
```

The module script checks all `go.mod` files for the requested module or their declared Go version. For a requested module, it reports a matching `replace` target in place of the required version, including fork modules and local paths. The builder script checks Dockerfiles and Containerfiles for Go builder images; `--correlate-builder` limits the scan to files selected by build-data image configs, including distinct OKD variants. `--build-root` reports the Go version from each component's `.ci-operator.yaml` build root image tag (e.g. `rhel-9-release-golang-1.26-openshift-5.0` → `1.26`); used alone it produces a compact 4-column output, or combined with `--correlate-builder` it appends build-root columns to each Dockerfile row in a single pass. The builder script explicitly maps the two installer artifact components to their build-data configs, which lack `payload_name`. When Nutanix cluster API controllers have no build-data config, it scans `openshift/Dockerfile.openshift` in that component's source repository at the release-recorded ref and labels the evidence as `source repo`.

### `golang:native-fips`

Configures Go projects to use Go's native FIPS 140 module (`GOFIPS140`) without the `openssl` RPM dependency. Works for both new projects and migrating existing openssl-based FIPS setups (`GOEXPERIMENT=strictfipsruntime`). Covers build flags, runtime FIPS activation, upstream vs downstream toolchain differences, and post-quantum cryptography (ML-KEM).

Triggered automatically when FIPS-related patterns are detected, or on demand:

```bash
/golang:native-fips
```

## Dependencies

| Plugin | Marketplace | Purpose |
|--------|-------------|---------|
| `gopls-lsp` | `claude-plugins-official` | LSP integration for Go code intelligence |
