---
name: Network Analysis
description: Analyze network configuration data from sosreport archives, extracting interface configurations, routing tables, active connections, firewall rules (firewalld/iptables), and DNS settings from the sosreport directory structure to diagnose network connectivity and configuration issues
---

# Network Analysis Skill

This skill provides detailed guidance for analyzing network configuration and connectivity from sosreport archives, including interfaces, routing, firewall rules, and DNS configuration.

## When to Use This Skill

Use this skill when:
- Analyzing the `/sosreport:analyze` command's network analysis phase
- Investigating network connectivity issues
- Diagnosing firewall or routing problems
- Verifying network configuration

## Prerequisites

- Sosreport archive must be extracted to a working directory
- Path to the sosreport root directory must be known
- Understanding of Linux networking concepts

## Key Network Data Locations in Sosreport

1. **Network Interfaces**:
   - `sos_commands/networking/ip_-o_addr` - IP addresses
   - `sos_commands/networking/ip_link` - Link status
   - `sos_commands/networking/ip_-s_link` - Link statistics with errors
   - `etc/sysconfig/network-scripts/` - Network configuration files (RHEL)

2. **Routing**:
   - `sos_commands/networking/ip_route` - Routing table
   - `sos_commands/networking/ip_-6_route` - IPv6 routing table
   - `proc/net/route` - Kernel routing table

3. **Network Connections**:
   - `sos_commands/networking/netstat_-neopa` - Active connections
   - `sos_commands/networking/ss_-tupna` - Socket statistics
   - `proc/net/tcp` - TCP connections
   - `proc/net/udp` - UDP connections

4. **Firewall**:
   - `sos_commands/firewalld/` - Firewalld configuration
   - `sos_commands/iptables/iptables_-vnxL` - iptables rules
   - `sos_commands/nftables/` - nftables configuration

5. **DNS and Resolution**:
   - `etc/resolv.conf` - DNS servers
   - `etc/hosts` - Static hostname mappings
   - `etc/nsswitch.conf` - Name resolution order

6. **Network Services**:
   - `sos_commands/networking/networkmanager_info` - NetworkManager status
   - `systemctl status NetworkManager` output

## Implementation Steps

### Step 1: Analyze Network Interfaces

1. **List all network interfaces**:
   ```bash
   if [ -f sos_commands/networking/ip_-o_addr ]; then
     cat sos_commands/networking/ip_-o_addr
   fi
   ```

2. **Check interface states**:
   ```bash
   if [ -f sos_commands/networking/ip_link ]; then
     # Look for interface states (UP/DOWN)
     grep -E "^[0-9]+:" sos_commands/networking/ip_link
   fi
   ```

3. **Parse interface information**:
   - Interface name (eth0, ens192, etc.)
   - State (UP/DOWN)
   - IP addresses (IPv4 and IPv6)
   - MAC address
   - MTU size

4. **Check for interface errors**:
   ```bash
   if [ -f sos_commands/networking/ip_-s_link ]; then
     # Look for RX/TX errors, drops, overruns
     cat sos_commands/networking/ip_-s_link
   fi
   ```

5. **Identify interface issues**:
   - Interfaces with no IP address (when expected)
   - Interfaces in DOWN state (when should be UP)
   - High error counts (RX/TX errors, drops)
   - Duplicate IP addresses
   - MTU mismatches

### Step 2: Analyze Routing Configuration

1. **Check default route**:
   ```bash
   if [ -f sos_commands/networking/ip_route ]; then
     grep "^default" sos_commands/networking/ip_route || echo "No default route found"
   fi
   ```

2. **Review routing table**:
   ```bash
   if [ -f sos_commands/networking/ip_route ]; then
     cat sos_commands/networking/ip_route
   fi
   ```

3. **Check IPv6 routing**:
   ```bash
   if [ -f sos_commands/networking/ip_-6_route ]; then
     cat sos_commands/networking/ip_-6_route
   fi
   ```

4. **Identify routing issues**:
   - Missing default route
   - Multiple default routes (conflicting)
   - Incorrect gateway addresses
   - Route to nowhere (unreachable gateway)

### Step 3: Analyze Network Connectivity

1. **Check active connections**:
   ```bash
   if [ -f sos_commands/networking/netstat_-neopa ]; then
     cat sos_commands/networking/netstat_-neopa
   elif [ -f sos_commands/networking/ss_-tupna ]; then
     cat sos_commands/networking/ss_-tupna
   fi
   ```

2. **Count connections by state**:
   ```bash
   # Count TCP connection states
   if [ -f sos_commands/networking/netstat_-neopa ]; then
     grep "^tcp" sos_commands/networking/netstat_-neopa | awk '{print $6}' | sort | uniq -c
   fi
   ```

3. **Find listening services**:
   ```bash
   # Show what's listening on which ports
   if [ -f sos_commands/networking/netstat_-neopa ]; then
     grep "LISTEN" sos_commands/networking/netstat_-neopa
   fi
   ```

4. **Check for connection issues**:
   - Excessive TIME_WAIT connections
   - Many connections in SYN_SENT (connection attempts failing)
   - High number of CLOSE_WAIT (application not closing)
   - Port conflicts (multiple services on same port)

### Step 4: Analyze Firewall Configuration

1. **Check if firewalld is active**:
   ```bash
   if [ -d sos_commands/firewalld ]; then
     # Firewalld is present
     if [ -f sos_commands/firewalld/firewall-cmd_--list-all-zones ]; then
       cat sos_commands/firewalld/firewall-cmd_--list-all-zones
     fi
   fi
   ```

2. **Review iptables rules**:
   ```bash
   if [ -f sos_commands/iptables/iptables_-vnxL ]; then
     cat sos_commands/iptables/iptables_-vnxL
   fi
   ```

3. **Check firewall zones and rules**:
   - Active zones
   - Allowed services
   - Allowed ports
   - Rich rules
   - Drop/reject policies

4. **Identify firewall issues**:
   - Required ports blocked
   - Overly permissive rules (any any accept)
   - Conflicting rules
   - Missing rules for services

### Step 5: Analyze DNS Configuration

1. **Check DNS servers**:
   ```bash
   if [ -f etc/resolv.conf ]; then
     cat etc/resolv.conf
   fi
   ```

2. **Review /etc/hosts**:
   ```bash
   if [ -f etc/hosts ]; then
     # Show non-comment, non-empty lines
     grep -v "^#\|^$" etc/hosts
   fi
   ```

3. **Check hostname resolution**:
   ```bash
   # Check hostname
   if [ -f hostname ]; then
     cat hostname
   fi

   # Check FQDN
   if [ -f etc/hostname ]; then
     cat etc/hostname
   fi
   ```

4. **Verify nsswitch configuration**:
   ```bash
   if [ -f etc/nsswitch.conf ]; then
     grep "^hosts:" etc/nsswitch.conf
   fi
   ```

5. **Identify DNS issues**:
   - No DNS servers configured
   - Unreachable DNS servers (check connectivity in logs)
   - Incorrect search domains
   - Hostname resolution failures in logs

### Step 6: Check for Network Errors in Logs

1. **Look for network-related errors**:
   ```bash
   # Connection refused errors
   grep -i "connection refused" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20

   # Timeout errors
   grep -i "timeout\|timed out" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20

   # Network unreachable
   grep -i "network.*unreachable\|no route to host" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20

   # DNS resolution failures
   grep -i "could not resolve\|dns.*fail\|name resolution" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

2. **Check for link state changes**:
   ```bash
   grep -i "link.*up\|link.*down\|carrier.*lost" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

3. **Look for network device errors**:
   ```bash
   grep -i "network.*error\|eth[0-9].*error\|transmit.*error" var/log/dmesg 2>/dev/null
   ```

### Step 7: Generate Network Analysis Summary

Create a structured summary with the following sections:

1. **Interface Summary**:
   - List of all interfaces with status
   - IP addresses assigned
   - Interface errors/drops
   - Link speeds and duplex settings

2. **Routing Summary**:
   - Default gateway
   - Number of routes
   - Any routing anomalies

3. **Connectivity Summary**:
   - Active connection count by state
   - Listening services and ports
   - Connection issues detected

4. **Firewall Summary**:
   - Firewall type (firewalld/iptables/nftables)
   - Active zones (if firewalld)
   - Key allowed services/ports
   - Potential blocking rules

5. **DNS Summary**:
   - DNS servers configured
   - Search domains
   - Hostname configuration
   - DNS resolution issues

6. **Network Issues**:
   - Critical network problems
   - Warnings and recommendations
   - Evidence from logs

## Error Handling

1. **Missing network files**:
   - Different sosreport versions may have different file names
   - Fall back to alternative files (netstat vs ss)
   - Document missing data in summary

2. **Multiple network configurations**:
   - System may use NetworkManager, systemd-networkd, or traditional ifcfg
   - Identify which is in use and analyze accordingly

3. **IPv6 presence**:
   - Check if IPv6 is enabled
   - Analyze IPv6 configuration if present
   - Note if IPv6 is disabled when expected

## Output Format

The network analysis should produce:

```bash
NETWORK CONFIGURATION SUMMARY
==============================

NETWORK INTERFACES
------------------
Interface: {name}
  State: {UP|DOWN}
  IP Addresses: {ipv4}, {ipv6}
  MAC: {mac_address}
  MTU: {mtu}
  RX Errors: {rx_errors} packets, {rx_dropped} dropped
  TX Errors: {tx_errors} packets, {tx_dropped} dropped
  Status: {OK|WARNING|CRITICAL}

ROUTING
-------
Default Gateway: {gateway_ip} via {interface}
Total Routes: {count}

Key Routes:
  {destination} via {gateway} dev {interface}

Status: {OK|WARNING|CRITICAL}
Issues:
  - {routing_issue_description}

CONNECTIVITY
------------
Total Active Connections: {count}

Connections by State:
  ESTABLISHED: {count}
  TIME_WAIT: {count}
  CLOSE_WAIT: {count}
  SYN_SENT: {count}

Listening Services:
  {port}/{protocol} - {service_name} (PID {pid})

Status: {OK|WARNING|CRITICAL}
Issues:
  - {connectivity_issue_description}

FIREWALL
--------
Type: {firewalld|iptables|nftables|none}
Default Zone: {zone_name} (if firewalld)

Allowed Services: {service1}, {service2}, ...
Allowed Ports: {port1/protocol}, {port2/protocol}, ...

Active Rules Count: {count}

Status: {OK|WARNING|CRITICAL}
Potential Issues:
  - {firewall_issue_description}

DNS CONFIGURATION
-----------------
DNS Servers: {dns1}, {dns2}, {dns3}
Search Domains: {domain1}, {domain2}
Hostname: {hostname}
FQDN: {fqdn}

Status: {OK|WARNING|CRITICAL}
Issues:
  - {dns_issue_description}

NETWORK ERRORS FROM LOGS
------------------------
Connection Refused: {count} occurrences
Timeouts: {count} occurrences
DNS Failures: {count} occurrences
Link State Changes: {count} occurrences

Recent Network Errors:
  {timestamp}: {error_message}

CRITICAL NETWORK ISSUES
-----------------------
{severity}: {issue_description}
  Evidence: {file_path_or_log_excerpt}
  Impact: {impact_description}
  Recommendation: {remediation_action}

RECOMMENDATIONS
---------------
1. {actionable_recommendation}
2. {actionable_recommendation}

DATA SOURCES
------------
- Interfaces: {sosreport_path}/sos_commands/networking/ip_-o_addr
- Routes: {sosreport_path}/sos_commands/networking/ip_route
- Connections: {sosreport_path}/sos_commands/networking/netstat_-neopa
- Firewall: {sosreport_path}/sos_commands/firewalld/
- DNS: {sosreport_path}/etc/resolv.conf
```

## Examples

### Example 1: Interface Analysis

```bash
# Check interface IP addresses
$ cat sos_commands/networking/ip_-o_addr
1: lo    inet 127.0.0.1/8 scope host lo
2: eth0  inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0
2: eth0  inet6 fe80::a00:27ff:fe4e:66a1/64 scope link

# Check for errors
$ cat sos_commands/networking/ip_-s_link | grep -A 4 "eth0"
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    RX: bytes  packets  errors  dropped overrun mcast
    15234567   98234    0       0       0       123
    TX: bytes  packets  errors  dropped carrier collsns
    8765432    54321    15      0       0       0

# Interpretation: eth0 has 15 TX errors - investigate cable/switch
```

### Example 2: Firewall Rule Analysis

```bash
# Check firewalld active zone
$ grep -A 20 "public" sos_commands/firewalld/firewall-cmd_--list-all-zones
public (active)
  target: default
  services: ssh dhcpv6-client http https
  ports: 8080/tcp 9090/tcp
  ...

# Interpretation: HTTP/HTTPS allowed, custom ports 8080 and 9090 open
```

### Example 3: Connection State Issues

```bash
# Count connection states
$ grep "^tcp" sos_commands/networking/netstat_-neopa | awk '{print $6}' | sort | uniq -c
    234 ESTABLISHED
   1523 TIME_WAIT
     12 CLOSE_WAIT
      5 SYN_SENT

# Interpretation:
# - Excessive TIME_WAIT (normal after closing connections)
# - CLOSE_WAIT suggests application not properly closing sockets
# - SYN_SENT indicates outbound connection attempts failing
```

## Tips for Effective Analysis

1. **Check interface consistency**: Ensure IP addresses match expected configuration
2. **Verify gateway reachability**: Default gateway should be on the same subnet
3. **Look for asymmetric routing**: Packets in/out may take different paths
4. **Check MTU settings**: MTU mismatches can cause packet fragmentation issues
5. **Correlate with logs**: Network errors in logs often explain configuration issues
6. **Consider network topology**: Understand expected network layout
7. **Check both IPv4 and IPv6**: Be sure to check IPv6 if it's in use

## Common Network Patterns and Issues

1. **No default route**: "Network unreachable" errors, can't reach internet
2. **Interface down**: "Network is down" errors, no connectivity
3. **Duplicate IP**: ARP conflicts, intermittent connectivity
4. **Firewall blocking**: "Connection refused/timeout" for specific ports
5. **DNS failure**: Can't resolve hostnames, but IP connectivity works
6. **Port exhaustion**: Too many TIME_WAIT connections, can't create new connections
7. **MTU issues**: Large packets fail, small packets work (PMTUD failure)

## Network Issue Severity Classification

| Issue Type | Severity | Impact |
|------------|----------|--------|
| No network interface | Critical | Complete loss of connectivity |
| No default route | Critical | No external connectivity |
| Interface errors >1% | Warning | Potential packet loss |
| Excessive TIME_WAIT | Warning | May indicate performance issue |
| Missing DNS server | Critical | Name resolution failure |
| Firewall blocking required port | High | Service unavailable |
| IPv6 autoconfiguration failure | Low | IPv6 connectivity issue |

## See Also

- Logs Analysis Skill: For detailed network error log analysis
- System Configuration Analysis Skill: For network service status
- Resource Analysis Skill: For network I/O statistics
