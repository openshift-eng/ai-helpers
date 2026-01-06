---
description: Display the router configuration
argument-hint: "[router-pod-name]"
---

## Name
openshift:router-show-config

## Synopsis
```
/openshift:router-show-config [router-pod-name]
```

## Description

The `router-show-config` command retrieves and displays the router configuration from OpenShift router pods in the `openshift-ingress` namespace. This command helps you inspect the current configuration for troubleshooting routing issues, understanding route configurations, or validating ingress settings.

This command is useful for:
- Troubleshooting route issues
- Verifying route configurations
- Debugging SSL/TLS certificate configurations
- Inspecting load balancing algorithms and health checks
- Validating route annotations

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (oc)**: Required to access router pods
   - Install from [mirror.openshift.com](https://mirror.openshift.com/pub/openshift-v4/clients/ocp/)
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set correctly

3. **Sufficient permissions**: Must have read access to router pods
   - Need to access pods in the `openshift-ingress` namespace
   - Minimum: ability to `oc get pods` and `oc exec` in the openshift-ingress namespace

## Arguments

- **router-pod-name** (optional): Specific router pod name to inspect
  - If not provided, the command will automatically select the first available router pod
  - Example: `router-default-7c5c8d9f4b-abcde`

## Implementation

The command performs the following steps:

### 1. Verify Prerequisites

Use the **oc-prereqs** skill to:
- Check if `oc` CLI is installed
- Verify cluster connectivity

### 2. Find and Validate Router Pod

Use the **router-pod-helper** skill to:
- Discover router pods in the `openshift-ingress` namespace
- Select appropriate pod (or use user-provided pod name)
- Verify pod is in Running state

After this step, the following variables are set:
- `$NAMESPACE` - Always `openshift-ingress`
- `$ROUTER_POD` - Name of the selected router pod

### 3. Extract HAProxy Configuration

Retrieve the HAProxy configuration file from the router pod:

```bash
echo ""
echo "Retrieving HAProxy configuration from pod: $ROUTER_POD"
echo "=========================================="
echo ""

# HAProxy config is typically at /var/lib/haproxy/conf/haproxy.config
oc exec -n $NAMESPACE $ROUTER_POD -- cat /var/lib/haproxy/conf/haproxy.config
```

### 4. Save Configuration to File

Save the configuration to the `.work` directory for future reference:

```bash
# Save to .work/openshift/router-configs/ directory
# The .work directory is the repository standard for temporary files (in .gitignore)
OUTPUT_DIR=".work/openshift/router-configs"
mkdir -p $OUTPUT_DIR
OUTPUT_FILE="$OUTPUT_DIR/${ROUTER_POD}-haproxy.config"

oc exec -n $NAMESPACE $ROUTER_POD -- cat /var/lib/haproxy/conf/haproxy.config > $OUTPUT_FILE

echo ""
echo "=========================================="
echo "Configuration saved to: $OUTPUT_FILE"
echo ""
echo "You can use this configuration to:"
echo "- Verify backend configurations"
echo "- Check SSL/TLS settings"
echo "- Debug routing issues"
```

### 5. Offer Configuration Analysis

After saving the configuration, offer to analyze it for the user:

```bash
echo ""
echo "Configuration ready for analysis!"
echo ""
echo "You can now ask questions about the configuration, such as:"
echo "- What's the maxconn value?"
echo "- Which backends are configured?"
echo "- What load balancing algorithms are used?"
echo "- What are the client/server/tunnel timeout values?"
echo ""
```

The saved configuration file can be analyzed by Claude Code to answer questions and provide insights about the router setup.

## Return Value

- **Format**: HAProxy configuration file content (plain text)
- **Output**:
  - Displayed to stdout
  - Saved to `.work/openshift/router-configs/{pod-name}-haproxy.config`
- **Content**: Complete HAProxy configuration including:
  - Global settings and defaults
  - Frontend definitions (HTTP/HTTPS)
  - Backend definitions
  - Load balancing algorithms

## Examples

1. **Show config from any available router pod**:
   ```text
   /openshift:router-show-config
   ```
   Output:
   ```text
   Finding router pods in namespace: openshift-ingress
   Selected router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy configuration from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================

   # HAProxy configuration
   global
     maxconn 20000
     daemon
   ...

   ==========================================
   Configuration saved to: .work/openshift/router-configs/router-default-7c5c8d9f4b-x7k9p-haproxy.config
   ```

2. **Show config from a specific router pod**:
   ```text
   /openshift:router-show-config router-default-7c5c8d9f4b-x7k9p
   ```
   Output:
   ```text
   Using specified router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy configuration from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================
   ...
   ```

## Related Commands

- `/openshift:router-show-sessions` - Display all active router sessions
- `/openshift:router-show-info` - Display router process information
