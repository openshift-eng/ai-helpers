---
description: Inspect IPv4 and IPv6 packet filter rules on Kubernetes node
argument-hint: <node> <image> --command <cmd> [--table <table>] [--filter <params>]
run: ../skills/openshift-node-kernel/node-kernel-iptables.sh
---

## Name
openshift:node-kernel-iptables

## Synopsis
```
/openshift:node-kernel-iptables <node> <image> --command <cmd> [--table <table>] [--filter <params>]
```

## Description
The `openshift:node-kernel-iptables` command allows interaction with the kernel to list packet filter rules. Iptables and ip6tables are used to inspect the tables of IPv4 and IPv6 packet filter rules in the Linux kernel.

In OVN-Kubernetes environments, iptables rules are crucial for:
- Network address translation (NAT) for services
- Packet filtering and security policies
- Connection tracking integration
- SNAT/DNAT for egress and ingress traffic
- Debugging packet flow issues

The command uses `oc debug` to create an ephemeral container with host network access, then executes iptables operations. The image must contain `iptables` or `ip6tables` CLI utilities.

## Implementation

This command invokes the `openshift-node-kernel` skill which provides kernel-level packet filter inspection capabilities:

1. **Parameter Validation**: Validates required node, image, and command parameters
2. **Utility Check**: Verifies the debug image contains `iptables` or `ip6tables` utilities
3. **Command Execution**: Uses `oc debug` to create ephemeral container and execute iptables commands
4. **Output Filtering**: Removes common oc debug warnings to provide clean output

**Skill Reference:**
- Implementation: `plugins/openshift/skills/openshift-node-kernel/node-kernel-iptables.sh`
- Helper functions: `plugins/openshift/skills/openshift-node-kernel/kernel-helper.sh`
- Documentation: `plugins/openshift/skills/openshift-node-kernel/SKILL.md`

## Parameters

### Required Parameters

- **node**: Name of the Kubernetes node where iptables rules should be extracted.
  - Must be a valid node name in the cluster
  - Example: `ovn-control-plane`, `ovn-worker`, `worker-0`

- **image**: Container image to use for creating a debug connection to the node.
  - Must contain `iptables` and/or `ip6tables` utilities
  - Common images:
    - `registry.redhat.io/rhel9/support-tools`
    - `nicolaka/netshoot`

- **--command \<cmd\>**: Iptables operation to perform
  - `-L, --list [chain]`: List all rules in selected chain (or all chains if not specified)
  - `-S, --list-rules [chain]`: Print all rules in iptables-save format

### Optional Parameters

- **--table \<table\>**: Iptables table to query (default: `filter`)
  - `filter`: Default table for packet filtering
  - `nat`: Network address translation table
  - `mangle`: Packet alteration table
  - `raw`: Connection tracking exemptions table
  - `security`: Mandatory Access Control (MAC) networking rules

- **--filter \<params\>**: Additional filter parameters
  - `-s, --source <address[/mask]>`: Source specification
  - `-d, --destination <address[/mask]>`: Destination specification
  - `-v, --verbose`: Verbose output with packet and byte counters
  - `-n, --numeric`: Numeric output (no DNS resolution)
  - `-p, --protocol <protocol>`: Protocol filter (tcp, udp, icmp, etc.)
  - `-4, --ipv4`: IPv4 rules only
  - `-6, --ipv6`: IPv6 rules only

## Return Value

The command returns iptables rules in standard iptables format. Output varies based on the command:

**For -L (list) command:**
```
Chain POSTROUTING (policy ACCEPT 675K packets, 41M bytes)
 pkts bytes target     prot opt in     out     source               destination
 675K   41M OVN-KUBE-EGRESS-IP-MULTI-NIC  all  --  *      *       0.0.0.0/0            0.0.0.0/0
```

**For -S (list-rules) command:**
```
-P POSTROUTING ACCEPT
-A POSTROUTING -j OVN-KUBE-EGRESS-IP-MULTI-NIC
```

## Examples

### Example 1: List NAT table rules with verbose output
```
/openshift:node-kernel-iptables ovn-control-plane registry.redhat.io/rhel9/support-tools --command -L --table nat --filter "-nv4"
```

Output:
```
Chain PREROUTING (policy ACCEPT 1234 packets, 89012 bytes)
 pkts bytes target     prot opt in     out     source               destination
 1234 89012 OVN-KUBE-NODEPORT  all  --  *      *       0.0.0.0/0            0.0.0.0/0

Chain POSTROUTING (policy ACCEPT 567 packets, 45678 bytes)
 pkts bytes target     prot opt in     out     source               destination
  567 45678 OVN-KUBE-SNAT-MGMTPORT  all  --  *      *       0.0.0.0/0            0.0.0.0/0
```

### Example 2: Show filter table in iptables-save format
```
/openshift:node-kernel-iptables ovn-worker nicolaka/netshoot --command -S --table filter
```

Output:
```
-P INPUT ACCEPT
-P FORWARD ACCEPT
-P OUTPUT ACCEPT
-N OVN-KUBE-FIREWALL
-A FORWARD -j OVN-KUBE-FIREWALL
-A OVN-KUBE-FIREWALL -m comment --comment "default deny policy" -j DROP
```

### Example 3: List specific chain
```
/openshift:node-kernel-iptables ovn-control-plane registry.redhat.io/rhel9/support-tools --command "-L FORWARD" --table filter --filter "-n"
```

Output:
```
Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
OVN-KUBE-FIREWALL  all  --  0.0.0.0/0            0.0.0.0/0
```

### Example 4: Filter by protocol and destination
```
/openshift:node-kernel-iptables ovn-worker nicolaka/netshoot --command -L --table nat --filter "-p tcp -d 10.96.0.1"
```

Output:
```
Chain PREROUTING (policy ACCEPT)
target     prot opt source               destination
DNAT       tcp  --  anywhere             10.96.0.1            tcp dpt:443 to:10.0.0.5:6443
```

### Example 5: List all tables for comprehensive view
```
/openshift:node-kernel-iptables ovn-control-plane registry.redhat.io/rhel9/support-tools --command -L --table nat
/openshift:node-kernel-iptables ovn-control-plane registry.redhat.io/rhel9/support-tools --command -L --table filter
/openshift:node-kernel-iptables ovn-control-plane registry.redhat.io/rhel9/support-tools --command -L --table mangle
```

### Example 6: IPv6 rules
```
/openshift:node-kernel-iptables ovn-worker registry.redhat.io/rhel9/support-tools --command -L --table filter --filter "-6 -nv"
```

## Understanding Output

### Chain Types
- **PREROUTING**: Rules applied before routing decision
- **INPUT**: Rules for packets destined to local processes
- **FORWARD**: Rules for packets being routed through the system
- **OUTPUT**: Rules for locally generated packets
- **POSTROUTING**: Rules applied after routing decision

### Target Actions
- **ACCEPT**: Allow packet to pass through
- **DROP**: Silently discard packet
- **REJECT**: Discard packet and send error response
- **DNAT**: Destination NAT (change destination address)
- **SNAT**: Source NAT (change source address)
- **MASQUERADE**: Dynamic source NAT
- **Custom chains**: Jump to user-defined chain (e.g., OVN-KUBE-*)

### Packet Counters
When using `-v` (verbose):
- **pkts**: Number of packets matching this rule
- **bytes**: Total bytes of packets matching this rule

## Troubleshooting

### Image doesn't have iptables utility
The command will fail if the image lacks iptables/ip6tables.

**Solution**: Use an image with iptables utilities:
```
/openshift:node-kernel-iptables ovn-worker registry.redhat.io/rhel9/support-tools --command -L
```

### Legacy vs nftables backend
Modern systems may use nftables backend for iptables.

**Solution**: If you need nftables information, use `/openshift:node-kernel-nft` command instead.

### Empty output or no rules
This could indicate:
1. The specified table/chain has no rules
2. Wrong table name
3. Using IPv6 filters on IPv4 rules (or vice versa)

**Solution**: Try listing all chains without filters:
```
/openshift:node-kernel-iptables <node> <image> --command -L --table nat
```

### Permission errors
Debug pod might lack necessary privileges.

**Solution**: Verify your OpenShift user has permissions for creating privileged debug pods.

## OVN-Kubernetes Specific Chains

In OVN-Kubernetes environments, you'll commonly see these custom chains:

- **OVN-KUBE-NODEPORT**: Handles NodePort service traffic
- **OVN-KUBE-EXTERNALIP**: Manages external IP services
- **OVN-KUBE-SNAT-MGMTPORT**: SNAT for management port traffic
- **OVN-KUBE-EGRESS-IP**: Egress IP functionality
- **OVN-KUBE-FIREWALL**: Network policy enforcement

## See Also

- `/openshift:node-kernel-conntrack` - Inspect connection tracking entries
- `/openshift:node-kernel-nft` - Inspect nftables configuration
- `/openshift:node-kernel-ip` - Inspect network interfaces and routing
- [iptables man page](https://linux.die.net/man/8/iptables)
