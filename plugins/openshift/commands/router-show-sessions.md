---
description: Display all active router sessions
argument-hint: "[router-pod-name]"
---

## Name
openshift:router-show-sessions

## Synopsis
```
/openshift:router-show-sessions [router-pod-name]
```

## Description

The `router-show-sessions` command retrieves and displays all active router sessions from OpenShift router pods in the `openshift-ingress` namespace. It executes the `show sess all` command against the router admin socket to provide real-time session information.

This command is useful for:
- Monitoring active connections and sessions
- Troubleshooting connection issues
- Identifying long-running or stuck connections
- Analyzing session distribution across backends
- Debugging routing and load balancing behavior

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (oc)**: Required to access router pods
   - Install from [mirror.openshift.com](https://mirror.openshift.com/pub/openshift-v4/clients/ocp/)
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set correctly

3. **Sufficient permissions**: Must have exec access to router pods
   - Need to execute commands in pods in the `openshift-ingress` namespace
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

### 3. Query Admin Socket for Sessions

Execute the admin socket command to retrieve all active sessions:

```bash
echo ""
echo "Retrieving HAProxy sessions from pod: $ROUTER_POD"
echo "=========================================="
echo ""

# Execute "show sess all" command against the HAProxy socket
# Using socat to communicate with the Unix socket
oc exec -n $NAMESPACE $ROUTER_POD -- /bin/sh -c 'socat stdio /var/lib/haproxy/run/haproxy.sock <<<"show sess all"'
```

### 4. Save Sessions Output to File

Save the sessions data to the `.work` directory:

```bash
# Save to .work/openshift/router-sessions/ directory
# The .work directory is the repository standard for temporary files (in .gitignore)
OUTPUT_DIR=".work/openshift/router-sessions"
mkdir -p $OUTPUT_DIR
OUTPUT_FILE="$OUTPUT_DIR/${ROUTER_POD}-sessions-$(date +%Y%m%d-%H%M%S).txt"

oc exec -n $NAMESPACE $ROUTER_POD -- socat stdio /var/lib/haproxy/run/haproxy.sock <<< "show sess all" > $OUTPUT_FILE

echo ""
echo "=========================================="
echo "Sessions data saved to: $OUTPUT_FILE"
```

## Return Value

- **Format**: HAProxy sessions output (plain text)
- **Output**:
  - Displayed to stdout
  - Saved to `.work/openshift/router-sessions/{pod-name}-sessions-{timestamp}.txt`
- **Content**: Active session information including:
  - Session IDs
  - Connection states
  - Frontend and backend information
  - Session age and timers
  - Request/response states

## Examples

1. **Show sessions from any available router pod**:
   ```text
   /openshift:router-show-sessions
   ```
   Output:
   ```text
   Finding router pods in namespace: openshift-ingress
   Selected router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy sessions from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================

   0x7f8e4c000a20: proto=tcpv4 src=192.168.1.100:45678 fe=public be=be_http_default_myapp state=7 ...
   0x7f8e4c000b30: proto=tcpv4 src=192.168.1.101:45679 fe=public be=be_http_default_otherapp state=7 ...
   ...

   ==========================================
   Sessions data saved to: .work/openshift/router-sessions/router-default-7c5c8d9f4b-x7k9p-sessions-20260106-143022.txt
   ```

2. **Show sessions from a specific router pod**:
   ```text
   /openshift:router-show-sessions router-default-7c5c8d9f4b-x7k9p
   ```
   Output:
   ```text
   Using specified router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy sessions from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================
   ...
   ```

## Related Commands

- `/openshift:router-show-config` - Display the router configuration
- `/openshift:router-show-info` - Display router process information
