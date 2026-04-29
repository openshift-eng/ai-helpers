# [Component Name] - Development Guide

> **Generic Development Practices**: See [Tier 1 Development Practices](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/development) for Go standards, controller-runtime patterns, and CI/CD workflows.

This guide covers **[COMPONENT]-specific** development practices.

## Quick Start

### Prerequisites

- Go 1.22+ (check go.mod for exact version)
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

## Repository Structure

```text
cmd/                           # Binary entrypoints
├── [component-1]/             # Component 1
└── [component-2]/             # Component 2

pkg/
├── controller/                # Controllers
│   ├── [controller-1]/        # Controller 1
│   └── [controller-2]/        # Controller 2
├── [domain-logic]/            # Domain-specific logic
└── [utilities]/               # Utilities

manifests/                     # Deployment manifests
├── [component-1]/             # Component 1 deployment
└── [component-2]/             # Component 2 deployment

test/
├── e2e/                       # End-to-end tests
└── integration/               # Integration tests
```

## Development Workflow

### 1. Local Development

Edit code, build binaries locally:

```bash
make [component-name]
```

Run unit tests:

```bash
make test-unit

# Or specific package
go test -v ./pkg/[package]/...
```

### 2. Testing on Cluster

**Option A: Replace running pod**

```bash
# Build image
make image

# Push to registry
podman push localhost/[component]:latest quay.io/[user]/[component]:dev

# Update deployment to use dev image
oc set image deployment/[component] [container]=[image]:dev -n [namespace]
```

**Option B: Run locally against cluster**

```bash
# Port-forward if needed
oc port-forward svc/[service] 8443:8443 -n [namespace]

# Run binary with KUBECONFIG
./_output/[binary] --kubeconfig=$KUBECONFIG
```

### 3. Debugging

**View logs**:
```bash
oc logs -f deployment/[component] -n [namespace]
```

**Exec into pod**:
```bash
oc exec -it deployment/[component] -n [namespace] -- /bin/bash
```

**Debug with delve**:
```bash
# Build with debug symbols
go build -gcflags="all=-N -l" -o _output/[binary] ./cmd/[component]

# Run with delve
dlv exec ./_output/[binary]
```

## Code Organization

### Controllers

Location: `pkg/controller/[name]/`

**Pattern**:
- `controller.go` - Controller setup, watches
- `reconcile.go` - Reconcile logic
- `*_test.go` - Unit tests

**Generic controller patterns**: See [Tier 1](https://github.com/openshift/enhancements/tree/master/ai-docs/platform/operator-patterns/controller-runtime.md)

### Domain Logic

Location: `pkg/[domain]/`

Document component-specific business logic here.

## Common Tasks

### Add New CRD

1. Define types in `pkg/apis/[group]/[version]/types.go`
2. Run `make manifests` to generate CRD YAML
3. Update RBAC in `manifests/*/rbac.yaml`
4. Create controller in `pkg/controller/[name]/`
5. Register controller in `cmd/[component]/main.go`

### Add New Controller

1. Create `pkg/controller/[name]/controller.go`
2. Implement `Reconcile()` function
3. Register in main.go
4. Add unit tests
5. Add E2E tests

### Update Dependencies

```bash
# Update specific dependency
go get [module]@[version]

# Update all dependencies
go get -u ./...

# Tidy and vendor
go mod tidy
go mod vendor
```

## Build & Release

### Local Build

```bash
make image
```

### CI Build

Component images are built by OpenShift CI on PR merge. See `.ci-operator.yaml`.

### Release Process

Component is released as part of OpenShift release image. See [Tier 1 Release Process](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/development).

## Component-Specific Notes

[Add component-specific development notes here]

- Special build flags
- Environment variables
- Local development quirks
- Common gotchas

## See Also

- [Testing Guide](./[COMPONENT]_TESTING.md)
- [Architecture](./architecture/components.md)
- [Tier 1 Development Practices](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/development)
