---
description: Inspect nftables packet filtering and classification rules on Kubernetes node
argument-hint: <node> <image> --command <cmd> [--family <family>]
run: ../skills/openshift-node-kernel/node-kernel-nft.sh
---

## Name
openshift:node-kernel-nft

## Synopsis
```
/openshift:node-kernel-nft <node> <image> --command <cmd> [--family <family>]
```

## Description
The `openshift:node-kernel-nft` command allows interaction with the kernel to list packet filtering and classification rules managed by nftables. Nftables is the modern successor to iptables, providing a more unified and efficient packet filtering framework in the Linux kernel.

In OVN-Kubernetes environments, nftables may be used for:
- Modern packet filtering replacing legacy iptables
- Service load balancing rules
- Network policy enforcement
- NAT rules for ingress and egress traffic
- More efficient rule matching than iptables

The command uses `oc debug` to create an ephemeral container with host network access, then executes nft operations. The image must contain the `nft` CLI utility.

## Implementation

This command invokes the `openshift-node-kernel` skill which provides kernel-level nftables inspection capabilities:

1. **Parameter Validation**: Validates required node, image, and command parameters
2. **Utility Check**: Verifies the debug image contains the `nft` utility
3. **Command Execution**: Uses `oc debug` to create ephemeral container and execute nft commands
4. **Output Filtering**: Removes common oc debug warnings to provide clean output

**Skill Reference:**
- Implementation: `plugins/openshift/skills/openshift-node-kernel/node-kernel-nft.sh`
- Helper functions: `plugins/openshift/skills/openshift-node-kernel/kernel-helper.sh`
- Documentation: `plugins/openshift/skills/openshift-node-kernel/SKILL.md`

## Parameters

### Required Parameters

- **node**: Name of the Kubernetes node where nftables configuration should be extracted.
  - Must be a valid node name in the cluster
  - Example: `ovn-control-plane`, `ovn-worker`, `worker-0`

- **image**: Container image to use for creating a debug connection to the node.
  - Must contain `nft` utility
  - Common images:
    - `registry.redhat.io/rhel9/support-tools`
    - `nicolaka/netshoot`

- **--command \<cmd\>**: Nftables operation to perform. Valid commands:
  - `list ruleset`: Print the entire ruleset in human-readable format
  - `list tables`: List all tables
  - `list chains`: List all chains (optionally filtered by table/family)
  - `list sets`: Display elements in sets
  - `list maps`: Display elements in maps
  - `list flowtables`: List all flowtables

### Optional Parameters

- **--family \<family\>**: Address family to filter results. Valid families:
  - `ip`: IPv4 address family
  - `ip6`: IPv6 address family
  - `inet`: Internet (IPv4/IPv6) address family
  - `arp`: ARP address family (IPv4 ARP packets)
  - `bridge`: Bridge address family (packets traversing bridge device)
  - `netdev`: Netdev address family (ingress/egress packet handling)

## Return Value

The command returns nftables configuration in nft native format. Output format depends on the command:

**For `list tables`:**
```
table inet ovn-kubernetes
table ip nat
```

**For `list ruleset`:**
```
table inet ovn-kubernetes {
  chain forward {
    type filter hook forward priority 0; policy accept;
    ct state related,established accept
    ct state invalid drop
  }
}
```

**For `list chains`:**
```
table inet ovn-kubernetes {
  chain forward {
    type filter hook forward priority 0; policy accept;
  }
  chain input {
    type filter hook input priority 0; policy accept;
  }
}
```

## Examples

### Example 1: List all nftables tables
```
/openshift:node-kernel-nft ovn-control-plane registry.redhat.io/rhel9/support-tools --command "list tables"
```

Output:
```
table inet ovn-kubernetes
table ip nat
table ip filter
```

### Example 2: List tables for specific address family
```
/openshift:node-kernel-nft ovn-worker nicolaka/netshoot --command "list tables" --family inet
```

Output:
```
table inet ovn-kubernetes
```

### Example 3: Show complete ruleset
```
/openshift:node-kernel-nft ovn-control-plane registry.redhat.io/rhel9/support-tools --command "list ruleset"
```

Output:
```
table inet ovn-kubernetes {
  chain PREROUTING {
    type nat hook prerouting priority -100; policy accept;
    ip daddr 10.96.0.0/12 dnat to meta mark map @svc_map
  }

  chain FORWARD {
    type filter hook forward priority 0; policy accept;
    ct state related,established accept
    ct state invalid drop
    ip saddr 10.244.0.0/16 accept
  }

  set svc_ips {
    type ipv4_addr
    elements = { 10.96.0.1, 10.96.0.10, 10.96.0.100 }
  }

  map svc_map {
    type mark : ipv4_addr
    elements = { 0x100 : 10.0.0.5, 0x101 : 10.0.0.6 }
  }
}
```

### Example 4: List only chains
```
/openshift:node-kernel-nft ovn-worker registry.redhat.io/rhel9/support-tools --command "list chains" --family inet
```

Output:
```
table inet ovn-kubernetes {
  chain PREROUTING {
    type nat hook prerouting priority -100; policy accept;
  }
  chain FORWARD {
    type filter hook forward priority 0; policy accept;
  }
  chain POSTROUTING {
    type nat hook postrouting priority 100; policy accept;
  }
}
```

### Example 5: List sets (for service IPs, pod IPs, etc.)
```
/openshift:node-kernel-nft ovn-control-plane nicolaka/netshoot --command "list sets"
```

Output:
```
table inet ovn-kubernetes {
  set svc_ips {
    type ipv4_addr
    elements = { 10.96.0.1, 10.96.0.10, 10.96.0.100 }
  }
  set pod_ips {
    type ipv4_addr
    elements = { 10.244.0.5, 10.244.0.10, 10.244.1.5 }
  }
}
```

### Example 6: List flowtables (for connection offloading)
```
/openshift:node-kernel-nft ovn-worker registry.redhat.io/rhel9/support-tools --command "list flowtables"
```

Output:
```
table inet ovn-kubernetes {
  flowtable fastpath {
    hook ingress priority 0;
    devices = { eth0, ovn0 };
  }
}
```

## Understanding Output

### Address Families
- **ip**: IPv4 only rules
- **ip6**: IPv6 only rules
- **inet**: Combined IPv4/IPv6 rules (most common in modern setups)
- **arp**: ARP protocol handling
- **bridge**: Bridge device packet processing
- **netdev**: Device-level packet processing

### Chain Types and Hooks
- **filter hook input**: Process packets destined for local system
- **filter hook forward**: Process packets being routed through system
- **filter hook output**: Process locally generated packets
- **nat hook prerouting**: NAT before routing decision
- **nat hook postrouting**: NAT after routing decision

### Priority
Lower priority number = earlier execution. Common priorities:
- `-100`: Early NAT operations
- `0`: Standard filtering
- `100`: Late NAT operations

### Verdicts
- **accept**: Allow packet
- **drop**: Silently discard packet
- **reject**: Discard and send error
- **jump \<chain\>**: Jump to another chain
- **goto \<chain\>**: Go to chain without return
- **return**: Return to calling chain

### Data Structures
- **sets**: Collections of unique values (IPs, ports, etc.)
- **maps**: Key-value mappings (marks to IPs, etc.)
- **flowtables**: Hardware offload tables for fast path

## Troubleshooting

### Image doesn't have nft utility
The command will fail if nft is not available.

**Solution**: Use an image with nft utility:
```
/openshift:node-kernel-nft ovn-worker registry.redhat.io/rhel9/support-tools --command "list tables"
```

### No tables found
This indicates nftables is not in use on this node.

**Solution**: The system might be using legacy iptables. Try:
```
/openshift:node-kernel-iptables <node> <image> --command -L
```

### Invalid command error
Only specific list commands are allowed for safety.

**Solution**: Use one of the valid commands:
- `list ruleset`
- `list tables`
- `list chains`
- `list sets`
- `list maps`
- `list flowtables`

### Permission denied
Debug pod lacks necessary privileges.

**Solution**: Verify your OpenShift user has permissions for privileged debug pods.

### Empty output
Could indicate:
1. No nftables rules configured
2. Wrong address family filter
3. Nftables not in use (system using iptables instead)

**Solution**: Try without family filter first:
```
/openshift:node-kernel-nft <node> <image> --command "list tables"
```

## OVN-Kubernetes Nftables Usage

Modern OVN-Kubernetes deployments may use nftables for:

1. **Service load balancing**: Maps and sets for service IP to backend mapping
2. **NAT operations**: SNAT/DNAT rules in PREROUTING/POSTROUTING
3. **Network policies**: Filtering rules in FORWARD chain
4. **Connection tracking**: Integration with conntrack for stateful filtering
5. **Flow offloading**: Flowtables for hardware-accelerated packet processing

Common table names in OVN-Kubernetes:
- `inet ovn-kubernetes`: Main OVN-K table
- `ip nat`: IPv4 NAT rules
- `inet filter`: Packet filtering rules

## Performance Considerations

Nftables offers better performance than iptables:
- Single rule evaluation (vs. multiple tables in iptables)
- Better scalability with large rule sets
- More efficient matching with sets and maps
- Hardware offload support via flowtables

## See Also

- `/openshift:node-kernel-conntrack` - Inspect connection tracking entries
- `/openshift:node-kernel-iptables` - Inspect legacy iptables rules
- `/openshift:node-kernel-ip` - Inspect network interfaces and routing
- [nftables wiki](https://wiki.nftables.org/)
- [nftables manual](https://www.netfilter.org/projects/nftables/manpage.html)
