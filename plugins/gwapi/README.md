# Gateway API Plugin

Install and configure Gateway API resources on Kubernetes and OpenShift clusters.

## Overview

The Gateway API plugin provides utilities for installing Gateway API resources with automatic cluster configuration. It simplifies the deployment of GatewayClass and Gateway resources by automatically detecting your cluster's ingress domain and applying the appropriate configuration.

## Commands

### `/gwapi:install`

Install Gateway API resources to a Kubernetes/OpenShift cluster.

**Synopsis:**
```
/gwapi:install [namespace]
```

**Features:**
- Automatically detects cluster ingress domain
- Installs GatewayClass and Gateway resources
- Supports both OpenShift (`oc`) and Kubernetes (`kubectl`)
- Optional namespace targeting
- Idempotent installation (safe to run multiple times)

**Example:**
```bash
# Install to default namespace
/gwapi:install

# Install to specific namespace
/gwapi:install gateway-system
```

See [commands/install.md](commands/install.md) for complete documentation.

## Installation

```bash
/plugin install gwapi@ai-helpers
```

## Prerequisites

- Either `oc` (OpenShift CLI) or `kubectl` (Kubernetes CLI) must be installed
- Active connection to a Kubernetes or OpenShift cluster
- Appropriate permissions to create cluster-scoped resources (GatewayClass) and namespaced resources (Gateway)

## Resources Installed

The plugin installs the following Gateway API resources:

1. **GatewayClass** (`openshift-default`)
   - Controller: `openshift.io/gateway-controller/v1`
   - Cluster-scoped resource defining the gateway implementation

2. **Gateway** (`gateway`)
   - Namespace: `openshift-ingress` (default)
   - Hostname pattern: `*.gwapi.${DOMAIN}` (automatically configured)
   - Listener on port 80 (HTTP)
   - Allows routes from all namespaces

## How It Works

1. Detects available CLI tool (`oc` or `kubectl`)
2. Verifies cluster connectivity
3. Retrieves cluster ingress domain (OpenShift) or prompts for manual input (Kubernetes)
4. Applies GatewayClass resource
5. Substitutes cluster domain into Gateway resource and applies it
6. Verifies installation success

## Notes

- The Gateway resource uses `${DOMAIN}` as a placeholder that gets replaced with your cluster's actual ingress domain
- Resources are applied idempotently - you can run the command multiple times safely
- Original YAML files are not modified; domain substitution happens in-memory during application
