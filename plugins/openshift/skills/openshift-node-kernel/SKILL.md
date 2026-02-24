---
name: OpenShift Node Kernel Inspection
description: Inspect kernel-level networking configuration on OpenShift/Kubernetes nodes using oc debug
---

# OpenShift Node Kernel Inspection Skill

This skill provides utilities for inspecting kernel-level networking configuration on OpenShift/Kubernetes nodes using `oc debug`.

## Overview

The skill enables interaction with kernel networking tools on Kubernetes nodes without requiring SSH access. It uses `oc debug` to create ephemeral containers with host network access and executes kernel commands in the host's namespace.

## Commands Provided

### node-kernel-ip

Executes `ip` commands to inspect routing tables, network devices, and interfaces.

**Script**: `node-kernel-ip.sh`

**Usage**:
```bash
./node-kernel-ip.sh <node> <image> --command <cmd> [--options <opts>] [--filter <params>]
```

**Example**:
```bash
./node-kernel-ip.sh worker-1 registry.redhat.io/rhel9/support-tools --command "route show"
```

### node-kernel-iptables

Executes `iptables` or `ip6tables` commands to inspect packet filter rules.

**Script**: `node-kernel-iptables.sh`

**Usage**:
```bash
./node-kernel-iptables.sh <node> <image> --command <cmd> [--table <table>] [--filter <params>]
```

**Example**:
```bash
./node-kernel-iptables.sh worker-1 registry.redhat.io/rhel9/support-tools --command "-L POSTROUTING" --table nat --filter "-nv4"
```

### node-kernel-nft

Executes `nft` commands to inspect nftables packet filtering and classification rules.

**Script**: `node-kernel-nft.sh`

**Usage**:
```bash
./node-kernel-nft.sh <node> <image> --command <cmd> [--family <family>]
```

**Example**:
```bash
./node-kernel-nft.sh worker-1 registry.redhat.io/rhel9/support-tools --command "list tables" --family inet
```

### node-kernel-conntrack

Executes `conntrack` commands or reads `/proc/net/nf_conntrack` to inspect connection tracking entries.

**Script**: `node-kernel-conntrack.sh`

**Usage**:
```bash
./node-kernel-conntrack.sh <node> <image> [--command <cmd>] [--filter <params>]
```

**Example**:
```bash
./node-kernel-conntrack.sh worker-1 registry.redhat.io/rhel9/support-tools --command "-L" --filter "-s 1.2.3.4"
```

## Helper Functions

The `kernel-helper.sh` script provides shared functions:

- `check_utility_exists`: Verifies a utility exists in the debug image
- `execute_kernel_command`: Executes commands on a node via `oc debug`
- `filter_warnings`: Removes common oc debug warning messages from output
- `validate_node_exists`: Validates node name exists in cluster
- `detect_and_set_kubeconfig`: Auto-detects and configures kubeconfig

## Output Handling

All commands ensure:
- **stdout contains only the actual command output** (routing tables, interface info, etc.)
- **stderr contains warnings, debug messages, and errors**
- **Common `oc debug` warnings are filtered out automatically** using improved regex patterns
- **Output is explicitly captured and returned** to ensure proper data flow to calling processes

### Improvements

The `execute_kernel_command()` function explicitly captures all output from `oc debug` and filters warnings before returning results, ensuring:
1. **Complete output capture**: All stdout/stderr is captured in a variable
2. **Reliable filtering**: Uses single `grep -E` with multiple patterns for efficiency
3. **Guaranteed output**: The `|| cat` fallback ensures output passes through even if no warnings are found
4. **Explicit return**: Output is explicitly sent to stdout using `printf` for reliable data flow
