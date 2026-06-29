# [Component Name] - Development Guide

> **Generic Development Practices**: See [Platform Development Practices](Platform documentation) for Go standards, controller-runtime patterns, and CI/CD workflows.

This guide covers **[COMPONENT]-specific** development practices.

## Quick Start

### Prerequisites

- Go [X.XX]+ (from go.mod)
- Access to OpenShift cluster
- `KUBECONFIG` environment variable set
- Container build tool (Podman or Docker)

### Build Binaries

```bash
# Build component
make [component-name]

# Build all binaries
make binaries

# Or use go directly
go build -o _output/[binary-name] ./cmd/[component]
```

**Binaries output**: `./_output/linux/amd64/` or `./bin/`

## Development Workflow

### 1. Local Development

Edit code, build binaries locally:

```bash
make [component-name]
```text

Run unit tests:

```bash
make test-unit

# Or specific package
go test -v ./pkg/[package]/...
```text

### 2. Testing on Cluster

**Option A: Replace running pod**

```bash
# Build image
make image

# Push to registry
podman push localhost/[component]:latest quay.io/[user]/[component]:dev

# Update deployment to use dev image
oc set image deployment/[component] [container]=[image]:dev -n [namespace]
```text

**Option B: Run locally against cluster**

```bash
# Port-forward if needed
oc port-forward svc/[service] 8443:8443 -n [namespace]

# Run binary with KUBECONFIG
./_output/[binary] --kubeconfig=$KUBECONFIG
```text

### 3. Debugging

**View logs**:
```bash
oc logs -f deployment/[component] -n [namespace]
```text

**Exec into pod**:
```bash
oc exec -it deployment/[component] -n [namespace] -- /bin/bash
```text

**Debug with delve**:
```bash
# Build with debug symbols
go build -gcflags="all=-N -l" -o _output/[binary] ./cmd/[component]

# Run with delve
dlv exec ./_output/[binary]
```text

## Code Organization

### Controllers

Location: `pkg/controller/[name]/`

**Pattern**:
- `controller.go` - Controller setup, watches
- `reconcile.go` - Reconcile logic
- `*_test.go` - Unit tests

**Generic controller patterns**: See [Platform](Platform documentation)

### Domain Logic

Location: `pkg/[domain]/`

Document component-specific business logic here.

## Common Tasks

[Discover and document the 3-5 most common development tasks for this repo.
Replace these placeholders with repo-specific steps including exact file paths,
shared utilities to use, registration/wiring points, and naming conventions.
If tasks vary in complexity, document tiers with specific file modification lists.]

### Update Dependencies

```bash
# Update specific dependency
go get [module]@[version]

# Tidy and vendor
go mod tidy
go mod vendor
```

## Build & Release

### Local Build

```bash
make image
```text

### CI Build

Component images are built by OpenShift CI on PR merge. See `.ci-operator.yaml`.

### Release Process

Component is released as part of OpenShift release image. See [Platform Release Process](Platform documentation).

## Common Mistakes

[Discover from code patterns, comments, and code reviews. Study 2-3 existing
implementations to identify anti-patterns. List as numbered "DO NOT" items.]

1. DO NOT [pattern] — [brief explanation of why]

## Component-Specific Notes

[Add component-specific development notes here]

- Special build flags
- Environment variables
- Local development quirks

## See Also

- [Testing Guide](./[COMPONENT]_TESTING.md)
- [Architecture](./architecture/components.md)
- [Platform Development Practices](Platform documentation)
