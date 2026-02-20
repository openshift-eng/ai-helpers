---
description: Display router process information
argument-hint: "[router-pod-name]"
---

## Name
openshift:router-show-info

## Synopsis
```
/openshift:router-show-info [router-pod-name]
```

## Description

The `router-show-info` command retrieves and displays router process information from OpenShift router pods in the `openshift-ingress` namespace. It executes the `show info` command against the router admin socket to provide general information about the router process including version, uptime, configuration, memory usage, and global statistics.

This command is useful for:
- Monitoring router process health and uptime
- Checking router version and configuration limits
- Analyzing connection and session statistics
- Reviewing memory usage and resource consumption
- Understanding global performance metrics (connection rate, session rate)
- Verifying thread and process configuration

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

### 3. Query HAProxy Socket for Info

Execute the HAProxy socket command to retrieve process information:

```bash
echo ""
echo "Retrieving HAProxy process information from pod: $ROUTER_POD"
echo "=========================================="
echo ""

# Execute "show info" command against the HAProxy socket
# Using socat to communicate with the Unix socket
oc exec -n $NAMESPACE $ROUTER_POD -- /bin/sh -c 'socat stdio /var/lib/haproxy/run/haproxy.sock <<<"show info"'
```

### 4. Save Info Output to File

Save the info data to the `.work` directory:

```bash
# Save to .work/openshift/router-info/ directory
# The .work directory is the repository standard for temporary files (in .gitignore)
OUTPUT_DIR=".work/openshift/router-info"
mkdir -p $OUTPUT_DIR
OUTPUT_FILE="$OUTPUT_DIR/${ROUTER_POD}-info-$(date +%Y%m%d-%H%M%S).txt"

oc exec -n $NAMESPACE $ROUTER_POD -- socat stdio /var/lib/haproxy/run/haproxy.sock <<< "show info" > $OUTPUT_FILE

echo ""
echo "=========================================="
echo "HAProxy info saved to: $OUTPUT_FILE"
```

## Return Value

- **Format**: HAProxy process information (key-value pairs)
- **Output**:
  - Displayed to stdout
  - Saved to `.work/openshift/router-info/{pod-name}-info-{timestamp}.txt`
- **Content**: Process and global statistics including:
  - **Process info**: HAProxy version, PID, uptime, node name
  - **Configuration**: Max connections, max sockets, thread/process count
  - **Connection stats**: Current connections, cumulative connections, connection rate
  - **Session stats**: Current sessions, session rate, max session rate
  - **SSL stats**: SSL connections, SSL rate, SSL cache statistics
  - **Performance**: Idle percentage, tasks, run queue, busy polling
  - **Memory**: Memory allocation, pool usage
  - **Bytes**: Total bytes out, bytes out rate
  - **Other**: Dropped logs, failed resolutions, listeners, peers

## Examples

1. **Show info from any available router pod**:
   ```text
   /openshift:router-show-info
   ```
   Output:
   ```text
   Finding router pods in namespace: openshift-ingress
   Selected router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy process information from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================

   Name: HAProxy
   Version: 2.2.19-6c96864
   Release_date: 2021/08/11
   Nbthread: 4
   Nbproc: 1
   Uptime: 5d 3h42m15s
   Uptime_sec: 442935
   Memmax_MB: 0
   CurrConns: 127
   CumConns: 1847392
   MaxConnRate: 487
   ...

   ==========================================
   HAProxy info saved to: .work/openshift/router-info/router-default-7c5c8d9f4b-x7k9p-info-20260106-143022.txt
   ```

2. **Show info from a specific router pod**:
   ```text
   /openshift:router-show-info router-default-7c5c8d9f4b-x7k9p
   ```
   Output:
   ```text
   Using specified router pod: router-default-7c5c8d9f4b-x7k9p

   Retrieving HAProxy process information from pod: router-default-7c5c8d9f4b-x7k9p
   ==========================================
   ...
   ```

## Related Commands

- `/openshift:router-show-config` - Display the router configuration
- `/openshift:router-show-sessions` - Display all active router sessions
