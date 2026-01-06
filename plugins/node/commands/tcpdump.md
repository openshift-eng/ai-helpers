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

**By default, the command displays captured packets directly in the terminal for quick analysis.**

The command handles the complexity of:
- Creating a debug pod with host network access on the target node (tcpdump is pre-installed in debug pods)
- Capturing packets on specified or all network interfaces
- Applying custom tcpdump filters for targeted packet capture
- **Default mode**: Displaying captured packets in human-readable format directly in the terminal
- **Optional file mode**: When `--output` is specified, saves the capture to a `.pcap` file for offline analysis with Wireshark
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
  - List interfaces on node: `oc debug node/<node-name> -- ip link show`

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

- **--output** (optional): Save capture to a pcap file instead of displaying in terminal
  - Default: Not set (displays packets in terminal)
  - When specified: Saves capture to `.work/node-tcpdump/<filename>.pcap`
  - Example: `--output api-server-traffic.pcap`
  - Use this option when you want to analyze the capture later with Wireshark or save it for documentation

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
OUTPUT_FILE=${OUTPUT:-""}  # Empty means display mode, not file mode
WORK_DIR=".work/node-tcpdump"

# Determine capture mode
if [ -n "$OUTPUT_FILE" ]; then
    # File mode: save to pcap file
    CAPTURE_MODE="file"
    mkdir -p "$WORK_DIR"
    echo "Mode: Saving to file $WORK_DIR/$OUTPUT_FILE"
else
    # Display mode: show packets in terminal
    CAPTURE_MODE="display"
    echo "Mode: Displaying packets in terminal"
fi
```

### 3. Run tcpdump

Execute tcpdump in two different modes based on whether --output is specified:

#### Mode 1: Display Mode (Default - No --output specified)

Display packets directly in terminal for quick analysis:

```bash
echo "Starting packet capture on node: $NODE_NAME"
echo "Interface: $INTERFACE"
echo "Duration: ${DURATION}s"
[ -n "$FILTER" ] && echo "Filter: $FILTER"
[ -n "$COUNT" ] && [ "$COUNT" -gt 0 ] && echo "Packet limit: $COUNT"
echo ""

# Build tcpdump command for display mode
TCPDUMP_CMD="tcpdump -i $INTERFACE"

# Add additional options
[ -n "$TCPDUMP_OPTIONS" ] && TCPDUMP_CMD="$TCPDUMP_CMD $TCPDUMP_OPTIONS"

# Add packet count limit
[ -n "$COUNT" ] && [ "$COUNT" -gt 0 ] && TCPDUMP_CMD="$TCPDUMP_CMD -c $COUNT"

# Add filter
[ -n "$FILTER" ] && TCPDUMP_CMD="$TCPDUMP_CMD $FILTER"

# Run tcpdump and display output directly
oc debug node/$NODE_NAME --keep-labels=false -- bash -c "
    timeout ${DURATION} $TCPDUMP_CMD
"
```

#### Mode 2: File Mode (When --output is specified)

Save packets to pcap file for later analysis:

```bash
echo "Starting packet capture on node: $NODE_NAME"
echo "Interface: $INTERFACE"
echo "Duration: ${DURATION}s"
[ -n "$FILTER" ] && echo "Filter: $FILTER"
[ -n "$COUNT" ] && [ "$COUNT" -gt 0 ] && echo "Packet limit: $COUNT"
echo "Output file: $WORK_DIR/$OUTPUT_FILE"
echo ""

# Build tcpdump command for file mode
TCPDUMP_CMD="tcpdump -i $INTERFACE -w /tmp/capture.pcap"

# Add additional options
[ -n "$TCPDUMP_OPTIONS" ] && TCPDUMP_CMD="$TCPDUMP_CMD $TCPDUMP_OPTIONS"

# Add packet count limit
[ -n "$COUNT" ] && [ "$COUNT" -gt 0 ] && TCPDUMP_CMD="$TCPDUMP_CMD -c $COUNT"

# Add filter
[ -n "$FILTER" ] && TCPDUMP_CMD="$TCPDUMP_CMD $FILTER"

# Run tcpdump, save to temp file, then copy to host
oc debug node/$NODE_NAME --keep-labels=false -- bash -c "
    # Capture packets to temp file
    timeout ${DURATION} $TCPDUMP_CMD

    # Copy to host filesystem for retrieval
    cp /tmp/capture.pcap /host/tmp/capture-\$(date +%s).pcap

    # Print the filename for retrieval
    ls -1 /host/tmp/capture-*.pcap | tail -1
"
```

### 4. Retrieve Capture File (File Mode Only)

**This step only applies when --output is specified.**

After tcpdump completes, retrieve the pcap file from the host:

```bash
if [ "$CAPTURE_MODE" = "file" ]; then
    echo "Retrieving capture file from node..."

    # Get the capture filename from previous step
    CAPTURE_FILE=$(oc debug node/$NODE_NAME --keep-labels=false -- bash -c "ls -1 /host/tmp/capture-*.pcap 2>/dev/null | tail -1" 2>/dev/null)

    if [ -z "$CAPTURE_FILE" ]; then
        echo "Error: No capture file found on node."
        exit 1
    fi

    # Retrieve the file
    oc debug node/$NODE_NAME --keep-labels=false -- cat "$CAPTURE_FILE" 2>/dev/null > "$WORK_DIR/$OUTPUT_FILE"

    # Verify file was captured
    if [ ! -f "$WORK_DIR/$OUTPUT_FILE" ]; then
        echo "Error: Failed to retrieve capture file."
        exit 1
    fi

    FILE_SIZE=$(du -h "$WORK_DIR/$OUTPUT_FILE" | cut -f1)
    echo "Capture file saved: $WORK_DIR/$OUTPUT_FILE ($FILE_SIZE)"

    # Clean up temporary file on node
    oc debug node/$NODE_NAME --keep-labels=false -- rm -f "$CAPTURE_FILE" 2>/dev/null

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
fi
```

### 5. Error Handling

Handle common error scenarios:

- **Node not accessible**: Check if node is Ready and user has debug permissions
- **Permission denied**: Ensure cluster-admin role or equivalent
- **Timeout**: Increase duration or use Ctrl+C to stop manually
- **Disk full**: Check node disk space before starting long captures
- **No packets captured**: Verify interface name and network traffic exists

## Return Value

**Display Mode (Default - no --output):**
- Packets are printed directly to terminal in human-readable format
- Shows: timestamp, source, destination, protocol, packet details
- Output appears in real-time during capture

**File Mode (with --output):**
- **Capture file**: `.work/node-tcpdump/<output-filename>.pcap`
- **Format**: Standard pcap format compatible with Wireshark and tcpdump
- **Console output**:
  - Capture progress and status
  - File location and size
  - Analysis command suggestions

## Examples

### Display Mode Examples (Quick Analysis)

### 1. Quick ICMP troubleshooting (display mode)

```
/node:tcpdump worker-2 --interface br-ex --filter "icmp" --duration 60
```

Displays ICMP (ping) packets on br-ex interface for 60 seconds. Perfect for quick network connectivity debugging.

### 2. Monitor DNS queries in real-time

```
/node:tcpdump worker-0 --filter "udp port 53" --count 50
```

Shows the first 50 DNS queries directly in terminal for quick DNS troubleshooting.

### 3. Watch API server traffic

```
/node:tcpdump master-0 --filter "tcp port 6443" --duration 30
```

Displays Kubernetes API server traffic for 30 seconds.

### 4. Check pod network connectivity

```
/node:tcpdump worker-1 --filter "host 10.128.2.15" --count 100
```

Shows first 100 packets to/from specific pod IP.

### File Mode Examples (Save for Later Analysis)

### 5. Save HTTPS traffic for Wireshark analysis

```
/node:tcpdump worker-0 --filter "tcp port 443" --duration 300 --output https-traffic.pcap
```

Saves 5 minutes of HTTPS traffic to file for detailed analysis with Wireshark.

### 6. Capture complete network dump to file

```
/node:tcpdump ip-10-0-143-232.ec2.internal --interface eth0 --duration 120 --output node-traffic.pcap
```

Saves all traffic on eth0 interface for 2 minutes to a pcap file.

### 7. Save pod traffic with verbose options

```
/node:tcpdump worker-1 --filter "net 10.128.0.0/14" --interface ovn-k8s-mp0 --tcpdump-options "-n -s 0" --output pod-network.pcap
```

Saves pod-to-pod traffic with full packets and no name resolution to file.

### 8. Capture with large buffer for high-traffic (save to file)

```
/node:tcpdump worker-0 --interface eth0 --tcpdump-options "-B 8192 -nn" --duration 120 --output high-traffic.pcap
```

Saves high-traffic capture with 8MB buffer to prevent packet drops.

## Troubleshooting

### Issue: "oc debug node failed"
**Solution**: Verify you have cluster-admin or appropriate RBAC permissions:
```bash
oc auth can-i create pods/exec
oc adm policy add-cluster-role-to-user cluster-admin <username>
```

### Issue: "No packets captured"
**Solution**:
- Verify the interface name: `oc debug node/<node> -- ip link show`
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

### Combine Multiple Filters

Use complex tcpdump filter expressions:

```
/node:tcpdump worker-1 --filter "(port 443 or port 80) and host 10.0.1.5"
```

### Capture Full Packets

To capture complete packets (not just headers), use the snaplen option:

```
/node:tcpdump worker-0 --tcpdump-options "-s 0" --filter "port 8080" --output full-packets.pcap
```

### Verbose Output in Display Mode

Add verbose flags to see more packet details in terminal:

```
/node:tcpdump worker-0 --tcpdump-options "-vv" --filter "icmp" --count 20
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
