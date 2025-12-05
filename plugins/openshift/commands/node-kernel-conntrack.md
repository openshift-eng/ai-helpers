---
description: Get connection tracking entries from Kubernetes node
argument-hint: <node> <image> [--command <cmd>] [--filter <params>]
run: ../skills/openshift-node-kernel/node-kernel-conntrack.sh
---

## Name
openshift:node-kernel-conntrack

## Synopsis
```
/openshift:node-kernel-conntrack <node> <image> [--command <cmd>] [--filter <params>]
```

## Description
The `openshift:node-kernel-conntrack` command allows interaction with the connection tracking system of a Kubernetes node. Use this command to discover all or a filtered selection of currently tracked connections. This is essential for debugging NAT issues, connection state problems, and understanding packet flows through the kernel's netfilter subsystem.

Connection tracking (conntrack) is a critical component of Linux networking that maintains state information about network connections. In OVN-Kubernetes environments, conntrack is used for:
- Service load balancing and NAT
- Network policy enforcement
- Connection state tracking across network namespace boundaries
- Debugging intermittent connectivity issues

The command uses `oc debug` to create an ephemeral container with host network access, then executes conntrack operations. If the provided image doesn't contain the `conntrack` CLI utility, the command falls back to printing `/proc/net/nf_conntrack` directly.

## Implementation

This command invokes the `openshift-node-kernel` skill which provides kernel-level connection tracking inspection capabilities:

1. **Parameter Validation**: Validates required node and image parameters
2. **Utility Check**: Verifies if the debug image contains the `conntrack` utility
3. **Command Execution**: Uses `oc debug` to create ephemeral container and execute conntrack commands
4. **Fallback Handling**: If conntrack utility is not available, falls back to reading `/proc/net/nf_conntrack`
5. **Output Filtering**: Removes common oc debug warnings to provide clean output

**Skill Reference:**
- Implementation: `plugins/openshift/skills/openshift-node-kernel/node-kernel-conntrack.sh`
- Helper functions: `plugins/openshift/skills/openshift-node-kernel/kernel-helper.sh`
- Documentation: `plugins/openshift/skills/openshift-node-kernel/SKILL.md`

## Parameters

### Required Parameters

- **node**: Name of the Kubernetes node where conntrack entries should be extracted.
  - Must be a valid node name in the cluster
  - Example: `ovn-control-plane`, `ovn-worker`, `worker-0`

- **image**: Container image to use for creating a debug connection to the node.
  - Should contain networking utilities (preferably with `conntrack` CLI)
  - Common images:
    - `registry.redhat.io/rhel9/support-tools` (Red Hat)
    - `nicolaka/netshoot` (community)
  - If image lacks `conntrack` utility, `/proc/net/nf_conntrack` will be printed

### Optional Parameters

- **--command \<cmd\>**: Conntrack operation to perform (requires `conntrack` CLI in image)
  - `-L, --dump`: List connection tracking table (default)
  - `-C, --count`: Show table counter
  - `-S, --stats`: Show in-kernel connection tracking statistics

- **--filter \<params\>**: Filter parameters to narrow down results
  - `-s, --src, --orig-src <IP>`: Match source address in original direction
  - `-d, --dst, --orig-dst <IP>`: Match destination address in original direction
  - `-p, --proto <PROTO>`: Specify layer 4 protocol (TCP, UDP, etc.)
  - `--sport, --orig-port-src <PORT>`: Source port in original direction
  - `--dport, --orig-port-dst <PORT>`: Destination port in original direction

## Return Value

The command returns connection tracking entries in the following format:

```
tcp 6 91 ESTABLISHED src=1.2.3.4 dst=5.6.7.8 sport=32000 dport=10250 src=5.6.7.8 dst=1.2.3.4 sport=10250 dport=32000 [ASSURED] mark=0 secctx=system_u:object_r:unlabeled_t:s0 use=2
```

Each entry contains:
- Protocol (tcp/udp/icmp)
- Protocol number
- TTL (time to live in seconds)
- Connection state (ESTABLISHED, TIME_WAIT, etc.)
- Original direction: source/destination IP and ports
- Reply direction: source/destination IP and ports
- Connection flags ([ASSURED], [UNREPLIED], etc.)
- Connection mark
- Security context
- Usage counter

## Examples

### Example 1: List all conntrack entries
```
/openshift:node-kernel-conntrack ovn-worker registry.redhat.io/rhel9/support-tools --command -L
```

Output:
```
tcp      6 431999 ESTABLISHED src=10.0.0.5 dst=10.96.0.1 sport=54321 dport=443 src=10.96.0.1 dst=10.0.0.5 sport=443 dport=54321 [ASSURED] mark=0 use=1
udp      17 29 src=10.0.0.5 dst=8.8.8.8 sport=45678 dport=53 src=8.8.8.8 dst=10.0.0.5 sport=53 dport=45678 [ASSURED] mark=0 use=1
```

### Example 2: Show conntrack statistics
```
/openshift:node-kernel-conntrack ovn-control-plane nicolaka/netshoot --command -S
```

Output:
```
cpu=0   found=1234 invalid=0 insert=567 insert_failed=0 drop=0 early_drop=0 error=0 search_restart=0
cpu=1   found=2345 invalid=0 insert=678 insert_failed=0 drop=0 early_drop=0 error=0 search_restart=0
```

### Example 3: Filter by specific source and destination
```
/openshift:node-kernel-conntrack ovn-worker registry.redhat.io/rhel9/support-tools --command -L --filter "-s 10.244.0.5 -d 10.96.0.1 -p tcp"
```

Output:
```
tcp      6 86399 ESTABLISHED src=10.244.0.5 dst=10.96.0.1 sport=38456 dport=443 src=10.96.0.1 dst=10.244.0.5 sport=443 dport=38456 [ASSURED] mark=0 use=1
```

### Example 4: Filter by port
```
/openshift:node-kernel-conntrack ovn-worker nicolaka/netshoot --filter "--dport 10250 -p tcp"
```

Output:
```
tcp      6 299 ESTABLISHED src=10.0.0.1 dst=10.0.0.5 sport=45678 dport=10250 src=10.0.0.5 dst=10.0.0.1 sport=10250 dport=45678 [ASSURED] mark=0 use=2
```

### Example 5: Count total conntrack entries
```
/openshift:node-kernel-conntrack ovn-control-plane registry.redhat.io/rhel9/support-tools --command -C
```

Output:
```
12847
```

## Troubleshooting

### Image doesn't have conntrack utility
If the specified image doesn't contain the `conntrack` CLI tool, the command automatically falls back to reading `/proc/net/nf_conntrack`. The output format is the same, but advanced filtering options won't be available.

**Solution**: Use an image with conntrack utility:
- `nicolaka/netshoot`

### No entries returned
This could indicate:
1. No active connections matching the filter criteria
2. Connection tracking module not loaded

**Solution**: Check without filters first, then verify kernel modules:
```
/openshift:node-kernel-ip <node> <image> --command "netns show"
```

### Permission denied errors
The debug pod might not have sufficient privileges.

**Solution**: Ensure your OpenShift user has permissions to create debug pods with host access.

## See Also

- `/openshift:node-kernel-iptables` - Inspect packet filter rules
- `/openshift:node-kernel-nft` - Inspect nftables configuration
- `/openshift:node-kernel-ip` - Inspect network interfaces and routing
- [Netfilter conntrack documentation](https://www.netfilter.org/documentation/)
