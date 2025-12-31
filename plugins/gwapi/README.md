# Gateway API Plugin

Install and configure Gateway API resources on Kubernetes and OpenShift clusters.

## Overview

This Gateway API plugin provides utilities for installing Gateway API resources with automatic cluster configuration. It simplifies the deployment of GatewayClass and Gateway resources by applying the appropriate configuration.

## Commands

### `/gwapi:install`

Install Gateway API resources to a Kubernetes/OpenShift cluster.

See [commands/install.md](commands/install.md) for complete documentation.

### `/gwapi:check`

Check the installed Gateway API resources in the connected cluster.

See [commands/check.md](commands/check.md) for complete documentation.

### `/gwapi:delete`

Delete Gateway API resources in the Kubernetes/OpenShift cluster.

See [commands/delete.md](commands/delete.md) for complete documentation.

**Synopsis:**
```
/gwapi:install [namespace]
/gwapi:check [namespace]
/gwapi:delete [namespace]
```

**Features:**
- Automatically detects cluster ingress domain
- Installs GatewayClass and Gateway resources
- Supports both OpenShift (`oc`) and Kubernetes (`kubectl`)
- Optional namespace targeting
- Check installed Gateway API resources
- Delete Gateway API resources
- Idempotent installation (safe to run multiple times)

## Installation

```bash
/plugin install gwapi@ai-helpers
```

## Prerequisites

- Either `oc` (OpenShift CLI) or `kubectl` (Kubernetes CLI) must be installed
- Active connection to a Kubernetes or OpenShift cluster
- Appropriate permissions to create cluster-scoped resources (GatewayClass) and namespaced resources (Gateway)

## Resources Installed

The plugin installs, checks and deletes the following Gateway API resources:

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
7. Checks the installed and other related Gateway API resources
8. Deletes all related resources after prompting the user

## Notes

- The Gateway resource uses `${DOMAIN}` as a placeholder that gets replaced with your cluster's actual ingress domain
- Resources are applied idempotently - you can run the command multiple times safely
- Original YAML files are not modified; domain substitution happens in-memory during application
- Deleting the Gateway API resources provides warnings and disclaimers
