---
description: Access OpenShift node via debug pod and capture network traffic using tcpdump on specified or all interfaces
argument-hint: "<node-name> [--interface <interface>] [--filter <tcpdump-filter>] [--duration <seconds>] [--tcpdump-options <options>] [--output <filename>]"
---

## Name
node:tcpdump

## Synopsis
```
/node:tcpdump <node-name> [--interface <interface>] [--filter <tcpdump-filter>] [--duration <seconds>] [--count <packets>] [--tcpdump-options <options>] [--output <filename>]
```

## Description

The `/node:tcpdump` command allows you to capture network traffic on OpenShift cluster nodes by accessing the node through a debug pod and running tcpdump. This is essential for debugging network connectivity issues, analyzing traffic patterns, troubleshooting service mesh problems, or investigating security incidents at the node level.

The command handles the complexity of:
- Creating a debug pod with host network access on the target node
- Installing tcpdump if not available
- Capturing packets on specified or all network interfaces
- Applying custom tcpdump filters for targeted packet capture
- Transferring the capture file (.pcap) back to your local machine for analysis with Wireshark or other tools
- Cleaning up debug resources after capture completion

**Common use cases:**
- Debug pod-to-pod networking issues
- Analyze traffic between nodes and external services
- Troubleshoot DNS resolution problems
- Investigate network performance bottlenecks
- Capture traffic for security analysis
- Debug load balancer or ingress connectivity
- Analyze CNI plugin behavior (OVN-Kubernetes, etc.)

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Required for node access
   - Install from: <https://mirror.openshift.com/pub/openshift-v4/clients/ocp/>
   - Verify with: `oc version`

2. **Active cluster connection with appropriate permissions**:
   - Verify with: `oc whoami`
   - Required permissions:
     - Ability to create debug pods (`oc debug node`)
     - Cluster-admin or equivalent role with node access

3. **Local disk space**: Sufficient space to store packet capture files
   - Typical capture: 100MB - 1GB depending on duration and traffic volume
   - Long captures can generate multi-GB files

4. **Wireshark or tcpdump** (optional): For local analysis of captured .pcap files
   - Install Wireshark: <https://www.wireshark.org/download.html>
   - Or use tcpdump locally: `tcpdump -r capture.pcap`

## Arguments

- **node-name** (required): The name of the OpenShift node to capture traffic from
  - Example: `ip-10-0-143-232.ec2.internal`
  - Get node names with: `oc get nodes`

- **--interface** (optional): Network interface to capture packets from
  - Default: `any` (captures from all interfaces)
  - Common interfaces:
    - `any`: All interfaces (default)
    - `eth0`: Primary network interface
    - `br-ex`: External bridge (OVN-Kubernetes)
    - `ovs-system`: OVS datapath interface
    - `ovn-k8s-mp0`: OVN-Kubernetes management port
    - `tun0`: VPN tunnel interface
  - List interfaces on node: `oc debug node/<node-name> -- chroot /host ip link show`

- **--filter** (optional): tcpdump filter expression for targeted capture
  - Default: No filter (captures all packets)
  - Examples:
    - `"port 443"`: HTTPS traffic
    - `"host 10.0.1.5"`: Traffic to/from specific IP
    - `"tcp and port 6443"`: API server traffic
    - `"icmp"`: ICMP/ping packets
    - `"udp port 53"`: DNS queries
    - `"net 10.128.0.0/14"`: Pod network traffic
  - Full tcpdump filter syntax: <https://www.tcpdump.org/manpages/pcap-filter.7.html>

- **--duration** (optional): Capture duration in seconds
  - Default: 60 seconds
  - Examples: `30`, `120`, `300`
  - Use with `--count` for dual limits (stops at first reached)

- **--count** (optional): Maximum number of packets to capture
  - Default: Unlimited (stopped by duration or manual interrupt)
  - Examples: `100`, `1000`, `10000`
  - Useful for capturing specific number of packets for analysis

- **--tcpdump-options** (optional): Additional tcpdump command-line options
  - Default: None
  - Common options:
    - `"-n"`: Don't resolve hostnames (faster, shows IPs only)
    - `"-nn"`: Don't resolve hostnames or port names
    - `"-s 0"` or `"-s 65535"`: Capture full packets (default snaplen may truncate)
    - `"-B 4096"`: Set buffer size in KB (useful for high-traffic captures)
    - `"-U"`: Make output packet-buffered (for real-time monitoring)
  - Examples:
    - `--tcpdump-options "-n -s 0"`: No name resolution, full packet capture
    - `--tcpdump-options "-nn -B 8192"`: No resolution, 8MB buffer
  - **Note**: Options like `-v/-vv/-vvv` don't affect pcap file output, only live display
  - **Warning**: Don't include `-i`, `-w`, `-c`, or filter expressions here (use dedicated parameters)

- **--output** (optional): Output filename for the capture file
  - Default: `node-<node-name>-<interface>-<timestamp>.pcap`
  - Example: `api-server-traffic.pcap`
  - File will be saved in: `.work/node-tcpdump/<filename>`

## Implementation

The command executes the following workflow:

### 1. Validate Prerequisites

Check that required tools are available and cluster is accessible:

```bash
# Check for oc CLI
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    echo "Download from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
    exit 1
fi

# Verify cluster connectivity
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster."
    echo "Please login with: oc login <cluster-url>"
    exit 1
fi

# Verify node exists
if ! oc get node "$NODE_NAME" &> /dev/null; then
    echo "Error: Node '$NODE_NAME' not found."
    echo "Available nodes:"
    oc get nodes -o name
    exit 1
fi
```

### 2. Prepare Capture Parameters

Parse user arguments and set defaults:

```bash
NODE_NAME=$1
INTERFACE=${INTERFACE:-any}
FILTER=${FILTER:-""}
DURATION=${DURATION:-60}
COUNT=${COUNT:-0}
TCPDUMP_OPTIONS=${TCPDUMP_OPTIONS:-""}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_FILE=${OUTPUT:-"node-${NODE_NAME}-${INTERFACE}-${TIMESTAMP}.pcap"}
WORK_DIR=".work/node-tcpdump"

# Create working directory
mkdir -p "$WORK_DIR"

# Build tcpdump command
TCPDUMP_CMD="tcpdump -i $INTERFACE -w /host/tmp/capture.pcap"

# Add additional tcpdump options if specified
if [ -n "$TCPDUMP_OPTIONS" ]; then
    TCPDUMP_CMD="$TCPDUMP_CMD $TCPDUMP_OPTIONS"
fi

# Add packet count limit if specified
if [ "$COUNT" -gt 0 ]; then
    TCPDUMP_CMD="$TCPDUMP_CMD -c $COUNT"
fi

# Add filter if specified
if [ -n "$FILTER" ]; then
    TCPDUMP_CMD="$TCPDUMP_CMD $FILTER"
fi
```

### 3. Start Debug Pod and Run tcpdump

Create a privileged debug pod on the target node with host network access:

```bash
echo "Starting packet capture on node: $NODE_NAME"
echo "Interface: $INTERFACE"
echo "Duration: ${DURATION}s"
[ -n "$FILTER" ] && echo "Filter: $FILTER"
echo ""
echo "Press Ctrl+C to stop capture early..."
echo ""

# Run tcpdump in debug pod with timeout
# Use --keep-labels to preserve node selector
# Use -- chroot /host to access host filesystem and network namespace
oc debug node/$NODE_NAME --keep-labels=false -- bash -c "
    # Ensure tcpdump is available
    if ! chroot /host which tcpdump &> /dev/null; then
        echo 'Installing tcpdump...'
        chroot /host yum install -y tcpdump || chroot /host dnf install -y tcpdump
    fi

    # Run tcpdump with timeout
    echo 'Starting packet capture...'
    timeout ${DURATION} chroot /host $TCPDUMP_CMD &
    TCPDUMP_PID=\$!

    # Wait for tcpdump to start
    sleep 2

    # Monitor capture
    echo 'Capture in progress...'
    wait \$TCPDUMP_PID

    echo 'Capture completed.'
"

# Note: The above creates and auto-deletes the debug pod after command completion
```

### 4. Copy Capture File from Node

After tcpdump completes, the debug pod is automatically deleted. We need to use a second debug pod to retrieve the file:

```bash
echo "Retrieving capture file from node..."

# Create temporary pod to copy file
oc debug node/$NODE_NAME --keep-labels=false -- chroot /host cat /tmp/capture.pcap > "$WORK_DIR/$OUTPUT_FILE"

# Verify file was captured
if [ ! -f "$WORK_DIR/$OUTPUT_FILE" ]; then
    echo "Error: Failed to retrieve capture file."
    exit 1
fi

FILE_SIZE=$(du -h "$WORK_DIR/$OUTPUT_FILE" | cut -f1)
echo "Capture file saved: $WORK_DIR/$OUTPUT_FILE ($FILE_SIZE)"
```

### 5. Clean Up and Display Results

Remove temporary files from the node and show analysis options:

```bash
# Clean up temporary file on node
oc debug node/$NODE_NAME --keep-labels=false -- chroot /host rm -f /tmp/capture.pcap

echo ""
echo "======================================"
echo "Packet Capture Complete"
echo "======================================"
echo "File: $WORK_DIR/$OUTPUT_FILE"
echo "Size: $FILE_SIZE"
echo ""
echo "Analysis options:"
echo "  1. Wireshark (GUI):   wireshark $WORK_DIR/$OUTPUT_FILE"
echo "  2. tcpdump (CLI):     tcpdump -r $WORK_DIR/$OUTPUT_FILE"
echo "  3. tcpdump verbose:   tcpdump -vv -r $WORK_DIR/$OUTPUT_FILE"
echo "  4. Count packets:     tcpdump -r $WORK_DIR/$OUTPUT_FILE | wc -l"
echo ""
```

### 6. Error Handling

Handle common error scenarios:

- **Node not accessible**: Check if node is Ready and user has debug permissions
- **tcpdump installation fails**: May require internet connectivity or pre-installed package
- **Permission denied**: Ensure cluster-admin role or equivalent
- **Timeout**: Increase duration or use Ctrl+C to stop manually
- **Disk full**: Check node disk space before starting long captures
- **No packets captured**: Verify interface name and network traffic exists

## Return Value

- **Capture file**: `.work/node-tcpdump/<output-filename>.pcap`
- **Format**: Standard pcap format compatible with Wireshark and tcpdump
- **Console output**:
  - Capture progress and status
  - File location and size
  - Analysis command suggestions

## Examples

### 1. Basic capture on all interfaces (60 seconds)

```
/node:tcpdump ip-10-0-143-232.ec2.internal
```

Captures all traffic on all interfaces for 60 seconds (default).

### 2. Capture on specific interface

```
/node:tcpdump ip-10-0-143-232.ec2.internal --interface eth0
```

Captures traffic only on the eth0 interface.

### 3. Capture HTTPS traffic to API server

```
/node:tcpdump ip-10-0-143-232.ec2.internal --filter "tcp port 6443" --duration 120
```

Captures only TCP traffic on port 6443 (Kubernetes API) for 2 minutes.

### 4. Capture DNS queries

```
/node:tcpdump ip-10-0-143-232.ec2.internal --filter "udp port 53" --count 100
```

Captures first 100 DNS query packets.

### 5. Capture traffic to specific pod IP

```
/node:tcpdump ip-10-0-143-232.ec2.internal --filter "host 10.128.2.15" --duration 300 --output pod-traffic.pcap
```

Captures all traffic to/from pod IP 10.128.2.15 for 5 minutes.

### 6. Capture ICMP traffic (ping)

```
/node:tcpdump ip-10-0-143-232.ec2.internal --filter "icmp" --duration 30
```

Captures ping and other ICMP packets for 30 seconds.

### 7. Capture pod network traffic

```
/node:tcpdump ip-10-0-143-232.ec2.internal --filter "net 10.128.0.0/14" --interface ovn-k8s-mp0
```

Captures pod-to-pod traffic on the OVN management interface.

### 8. Capture traffic between two specific IPs

```
/node:tcpdump worker-0 --filter "host 10.0.1.5 and host 10.0.1.10"
```

Captures only traffic between two specific IP addresses.

### 9. Capture full packets without name resolution (faster)

```
/node:tcpdump worker-0 --tcpdump-options "-n -s 0" --filter "port 443"
```

Captures HTTPS traffic with full packet size and without DNS resolution (faster, shows IPs instead of hostnames).

### 10. Capture with large buffer for high-traffic interface

```
/node:tcpdump worker-0 --interface eth0 --tcpdump-options "-B 8192 -nn" --duration 120
```

Captures all traffic on eth0 with 8MB buffer and no name resolution, useful for busy interfaces to prevent packet drops.

### 11. Capture complete packets with specific snaplen

```
/node:tcpdump worker-0 --tcpdump-options "-s 65535" --filter "tcp port 8080"
```

Captures full packets (up to 64KB) on port 8080. This ensures large packets aren't truncated.

## Troubleshooting

### Issue: "oc debug node failed"
**Solution**: Verify you have cluster-admin or appropriate RBAC permissions:
```bash
oc auth can-i create pods/exec
oc adm policy add-cluster-role-to-user cluster-admin <username>
```

### Issue: "tcpdump: command not found"
**Solution**: The command will attempt to install tcpdump automatically. If this fails, ensure the node has internet connectivity or access to RHEL repositories.

### Issue: "No packets captured"
**Solution**:
- Verify the interface name: `oc debug node/<node> -- chroot /host ip link show`
- Check if traffic exists on that interface
- Try interface `any` to capture from all interfaces
- Verify your tcpdump filter syntax

### Issue: "Permission denied" errors
**Solution**:
- Ensure you're using `oc debug node` which creates privileged pods
- Verify your user has cluster-admin or equivalent permissions
- Check node SELinux status if capture fails

### Issue: Capture file is empty or very small
**Solution**:
- Increase capture duration
- Verify network traffic exists during capture window
- Check if tcpdump filter is too restrictive
- Try without filter first to verify capture works

## Advanced Usage

### Capture and Analyze in Real-Time

For quick analysis without saving to file:

```bash
oc debug node/<node-name> -- chroot /host tcpdump -i any -n -vv port 443
```

### Capture Larger Packets

By default, tcpdump captures only packet headers. To capture full packets:

```bash
# Modify the tcpdump command to include -s 0 (snaplen 0 = capture entire packet)
# In the Implementation section, use:
TCPDUMP_CMD="tcpdump -i $INTERFACE -s 0 -w /host/tmp/capture.pcap"
```

### Capture with Multiple Filters

Combine multiple conditions using tcpdump filter syntax:

```bash
/node:tcpdump worker-1 --filter "(port 443 or port 80) and host 10.0.1.5"
```

## Security Considerations

- **Sensitive Data**: Packet captures may contain sensitive information (passwords, tokens, etc.). Handle with care.
- **Storage**: Ensure capture files are stored securely and deleted after analysis.
- **Permissions**: Restrict access to nodes and debug capabilities to authorized users only.
- **Performance Impact**: Long-running captures on busy nodes may impact performance. Monitor CPU and disk usage.

## Related Commands

- `oc get nodes`: List all cluster nodes
- `oc debug node/<node>`: Access node for manual debugging
- `oc adm node-logs <node>`: View node system logs
- `/node:cluster-node-health-check`: Check overall node health
