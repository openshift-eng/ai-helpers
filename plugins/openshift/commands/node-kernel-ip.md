---
description: Inspect routing, network devices, and interfaces on Kubernetes node
argument-hint: <node> <image> --command <cmd> [--options <opts>] [--filter <params>]
run: ../skills/openshift-node-kernel/node-kernel-ip.sh
---

## Name
openshift:node-kernel-ip

## Synopsis
```
/openshift:node-kernel-ip <node> <image> --command <cmd> [--options <opts>] [--filter <params>]
```

## Description
The `openshift:node-kernel-ip` command allows interaction with the kernel to list routing tables, network devices, and interfaces. The `ip` utility is the modern Linux networking configuration tool that shows and manipulates routing, network devices, policy routing, and tunnels.

In OVN-Kubernetes environments, the ip command is essential for:
- Inspecting OVN overlay network interfaces (genev_sys_*, ovn-k8s-mp0, etc.)
- Viewing routing tables for pod and service traffic
- Debugging network namespace configurations
- Analyzing interface states and configurations
- Troubleshooting connectivity issues between nodes and pods

The command uses `oc debug` to create an ephemeral container with host network access, then executes ip operations. The image must contain the `ip` utility (from iproute2 package).

## Implementation

This command invokes the `openshift-node-kernel` skill which provides kernel-level networking inspection capabilities:

1. **Parameter Validation**: Validates required node, image, and command parameters
2. **Utility Check**: Verifies the debug image contains the `ip` utility
3. **Command Execution**: Uses `oc debug` to create ephemeral container and execute ip commands
4. **Output Filtering**: Removes common oc debug warnings to provide clean output

**Skill Reference:**
- Implementation: `plugins/openshift/skills/openshift-node-kernel/node-kernel-ip.sh`
- Helper functions: `plugins/openshift/skills/openshift-node-kernel/kernel-helper.sh`
- Documentation: `plugins/openshift/skills/openshift-node-kernel/SKILL.md`

## Parameters

### Required Parameters

- **node**: Name of the Kubernetes node where network information should be extracted.
  - Must be a valid node name in the cluster
  - Example: `ovn-control-plane`, `ovn-worker`, `worker-0`

- **image**: Container image to use for creating a debug connection to the node.
  - Must contain `ip` utility (iproute2 package)
  - Common images:
    - `registry.redhat.io/rhel9/support-tools`
    - `nicolaka/netshoot`

- **--command \<cmd\>**: IP operation to perform. Valid commands:
  - `address show`: Display protocol (IP/IPv6) addresses on devices
  - `link show`: Display network devices
  - `neighbour show` or `neighbor show`: Display ARP or NDISC cache entries
  - `netns show`: Display network namespaces
  - `route show`: Display routing table entries
  - `rule show`: Display rules in routing policy database
  - `vrf show`: Display virtual routing and forwarding devices

### Optional Parameters

- **--options \<opts\>**: Additional options for the ip command
  - `-d, -details`: Output more detailed information
  - `-4`: Shortcut for `-family inet` (IPv4 only)
  - `-6`: Shortcut for `-family inet6` (IPv6 only)
  - `-r, -resolve`: Use DNS to resolve names instead of showing IPs
  - `-n, -netns <NETNS>`: Execute in specified network namespace
  - `-a, -all`: Execute command over all objects (if supported)
  - `-s, -stats`: Output statistics

- **--filter \<params\>**: Sub-commands and filters for more specific queries
  - Varies by command type
  - Examples: `dev eth0`, `table all`, `type veth`

## Return Value

The command returns ip utility output in standard format. Output varies based on the command:

**For `address show`:**
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
    inet6 ::1/128 scope host
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP
    link/ether 02:42:ac:11:00:02 brd ff:ff:ff:ff:ff:ff
    inet 172.17.0.2/16 brd 172.17.255.255 scope global eth0
```

**For `route show`:**
```
default via 172.17.0.1 dev eth0
10.244.0.0/16 via 10.244.1.1 dev ovn0 src 10.244.0.1
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.2
```

## Examples

### Example 1: Show all network interfaces
```
/openshift:node-kernel-ip ovn-worker registry.redhat.io/rhel9/support-tools --command "link show"
```

Output:
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP
3: ovn-k8s-mp0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1400 qdisc noqueue state UNKNOWN
4: genev_sys_6081: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65000 qdisc noqueue state UNKNOWN
```

### Example 2: Show IPv4 routing table
```
/openshift:node-kernel-ip ovn-control-plane nicolaka/netshoot --command "route show" --options "-4"
```

Output:
```
default via 10.0.0.254 dev br-ex proto dhcp src 10.0.0.10 metric 48
10.0.0.0/24 dev br-ex proto kernel scope link src 10.0.0.10 metric 48
10.244.0.0/24 dev ovn-k8s-mp0 proto kernel scope link src 10.244.0.1
```

### Example 3: Show all routing tables (including policy routing)
```
/openshift:node-kernel-ip ovn-worker registry.redhat.io/rhel9/support-tools --command "route show" --filter "table all"
```

Output:
```
default via 10.0.0.254 dev eth0 table default
10.244.0.0/16 dev ovn0 table main
local 127.0.0.0/8 dev lo table local
local 10.0.0.5 dev eth0 table local
broadcast 10.0.0.255 dev eth0 table local
```

### Example 4: Show detailed interface information
```
/openshift:node-kernel-ip ovn-control-plane registry.redhat.io/rhel9/support-tools --command "link show" --options "-d"
```

Output:
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00 promiscuity 0
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000
    link/ether 02:42:ac:11:00:02 brd ff:ff:ff:ff:ff:ff promiscuity 0
    inet 172.17.0.2/16 brd 172.17.255.255 scope global eth0
```

### Example 5: Show specific interface
```
/openshift:node-kernel-ip ovn-worker nicolaka/netshoot --command "address show" --filter "dev ovn-k8s-mp0"
```

Output:
```
3: ovn-k8s-mp0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1400 qdisc noqueue state UNKNOWN group default
    link/ether 0a:58:0a:f4:00:01 brd ff:ff:ff:ff:ff:ff
    inet 10.244.0.1/24 brd 10.244.0.255 scope global ovn-k8s-mp0
```

### Example 6: Show ARP/neighbor cache
```
/openshift:node-kernel-ip ovn-control-plane registry.redhat.io/rhel9/support-tools --command "neighbour show"
```

Output:
```
10.0.0.254 dev eth0 lladdr 52:54:00:12:34:56 REACHABLE
10.244.1.5 dev ovn0 lladdr 0a:58:0a:f4:01:05 STALE
fe80::1 dev eth0 lladdr 52:54:00:12:34:56 router REACHABLE
```

### Example 7: Show network namespaces
```
/openshift:node-kernel-ip ovn-worker registry.redhat.io/rhel9/support-tools --command "netns show"
```

Output:
```
ovnkube-node-12345 (id: 0)
```

### Example 8: Show routing policy rules
```
/openshift:node-kernel-ip ovn-control-plane nicolaka/netshoot --command "rule show"
```

Output:
```
0:      from all lookup local
100:    from 10.244.0.0/16 lookup main
32766:  from all lookup main
32767:  from all lookup default
```

### Example 9: Show interface statistics
```
/openshift:node-kernel-ip ovn-worker registry.redhat.io/rhel9/support-tools --command "link show" --options "-s"
```

Output:
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    RX: bytes  packets  errors  dropped overrun mcast
    1234567    12345    0       0       0       0
    TX: bytes  packets  errors  dropped carrier collsns
    1234567    12345    0       0       0       0
```

### Example 10: Show IPv6 addresses
```
/openshift:node-kernel-ip ovn-control-plane registry.redhat.io/rhel9/support-tools --command "address show" --options "-6"
```

Output:
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN
    inet6 ::1/128 scope host
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP
    inet6 fe80::42:acff:fe11:2/64 scope link
```

## Understanding Output

### Link States
- **UP**: Interface is administratively up
- **LOWER_UP**: Interface has carrier/link detected
- **UNKNOWN**: State cannot be determined
- **DOWN**: Interface is administratively down

### Link Types
- **loopback**: Loopback interface (lo)
- **ether**: Ethernet interface
- **veth**: Virtual Ethernet pair
- **geneve**: GENEVE tunnel interface
- **bridge**: Bridge interface

### Route Types
- **unicast**: Standard route to destination
- **local**: Local interface address
- **broadcast**: Broadcast address
- **multicast**: Multicast route

### Route Scopes
- **global**: Routes valid everywhere
- **link**: Valid only on directly connected network
- **host**: Valid only inside this host

### Neighbor States
- **REACHABLE**: Neighbor is reachable
- **STALE**: Neighbor entry is valid but suspicious
- **DELAY**: Neighbor entry validation pending
- **INCOMPLETE**: ARP resolution in progress
- **FAILED**: ARP resolution failed

## Troubleshooting

### Image doesn't have ip utility
The command will fail if ip utility is not available.

**Solution**: Use an image with iproute2 package:
```
/openshift:node-kernel-ip ovn-worker registry.redhat.io/rhel9/support-tools --command "link show"
```

### No OVN interfaces visible
If you don't see ovn-k8s-mp0 or genev_sys_* interfaces:
1. OVN-Kubernetes might not be running on this node
2. You might be in wrong network namespace

**Solution**: Check network namespaces:
```
/openshift:node-kernel-ip <node> <image> --command "netns show"
```

### Empty routing table
Could indicate:
1. Wrong routing table queried
2. No routes configured (unlikely)

**Solution**: Show all tables:
```
/openshift:node-kernel-ip <node> <image> --command "route show" --filter "table all"
```

### Permission errors
Debug pod might lack necessary privileges.

**Solution**: Verify your OpenShift user has permissions for privileged debug pods.

## OVN-Kubernetes Network Interfaces

In OVN-Kubernetes environments, you'll commonly see:

### Node Interfaces
- **ovn-k8s-mp0**: OVN management port (node to pod communication)
- **genev_sys_6081**: GENEVE tunnel interface (overlay network)
- **br-ex**: External bridge (node external connectivity)
- **breth0**: Bridge for physical interface

### Pod Interfaces (in pod network namespace)
- **eth0**: Pod's primary interface
- **vethXXXXXX**: Virtual ethernet pair connecting pod to OVS bridge

### Common Interface Patterns
```
ovn-k8s-mp0: Management port, usually 10.244.X.1
genev_sys_6081: GENEVE tunnel endpoint
br-ex: External bridge for node connectivity
```

## Routing in OVN-Kubernetes

Typical routing setup on OVN-Kubernetes node:

1. **Default route**: Via br-ex to external gateway
2. **Pod CIDR routes**: Via ovn-k8s-mp0 to local pods
3. **Service CIDR routes**: Via OVN overlay to service backends
4. **Local table**: Local interface addresses

Example routing table:
```
default via 10.0.0.254 dev br-ex
10.244.0.0/24 dev ovn-k8s-mp0 proto kernel scope link
10.244.1.0/24 via 10.244.1.1 dev ovn0
```

## Network Namespaces

OVN-Kubernetes uses network namespaces for isolation:
- **Host namespace**: Default namespace with all node interfaces
- **Pod namespaces**: Each pod gets its own network namespace
- **OVN namespace**: Some OVN components may use dedicated namespace

Use `--options "-n <namespace>"` to query specific namespace.

## See Also

- `/openshift:node-kernel-conntrack` - Inspect connection tracking entries
- `/openshift:node-kernel-iptables` - Inspect packet filter rules
- `/openshift:node-kernel-nft` - Inspect nftables configuration
- [ip command manual](https://man7.org/linux/man-pages/man8/ip.8.html)
- [iproute2 documentation](https://wiki.linuxfoundation.org/networking/iproute2)
