---
name: OpenShift CLI Prerequisites
description: Verify oc CLI installation and cluster connectivity before executing OpenShift commands
---

# OpenShift CLI Prerequisites

This skill provides reusable prerequisites checks for any OpenShift command that requires the `oc` CLI and cluster connectivity.

## When to Use This Skill

Use this skill at the beginning of any OpenShift command implementation that needs to:
- Execute `oc` commands against a cluster
- Verify the user is logged into an OpenShift cluster
- Ensure proper environment setup before proceeding

## Prerequisites Checks

### 1. Verify oc CLI Installation

Check if the `oc` command-line tool is installed and available:

```bash
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    echo "Download from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
    exit 1
fi
```

**What this does:**
- Uses `command -v` to check if `oc` is in the PATH
- Provides clear installation instructions if not found
- Points to the official OpenShift mirror for downloads

### 2. Verify Cluster Connectivity

Check if the user is connected and authenticated to an OpenShift cluster:

```bash
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster. Please login first."
    echo "Use: oc login <cluster-url>"
    exit 1
fi
```

**What this does:**
- Uses `oc whoami` to verify authentication
- Returns non-zero exit code if not logged in or cluster unreachable
- Provides clear instructions for logging in

### 3. Optional: Display Current Context

For commands that might affect critical resources, show the current cluster context:

```bash
echo "Current cluster context:"
echo "  User: $(oc whoami)"
echo "  Server: $(oc whoami --show-server)"
echo "  Namespace: $(oc project -q)"
echo ""
```

**When to use this:**
- Commands that modify resources
- Commands that might run against production clusters
- When the user needs context awareness before proceeding

## Usage Pattern

Commands should run these checks in order:

1. **First**: Check oc CLI availability
2. **Second**: Check cluster connectivity
3. **Optional**: Display context for destructive operations

## Examples

### Basic Usage

Most commands just need the first two checks:

```bash
# Check oc CLI
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    echo "Download from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
    exit 1
fi

# Check cluster connectivity
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster. Please login first."
    echo "Use: oc login <cluster-url>"
    exit 1
fi

# Proceed with command implementation...
```

### Usage with Context Display

For potentially destructive operations:

```bash
# Check prerequisites
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found."
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster."
    exit 1
fi

# Show context before proceeding
echo "This operation will affect the following cluster:"
echo "  User: $(oc whoami)"
echo "  Server: $(oc whoami --show-server)"
echo ""
```

## Error Handling

These checks will cause the command to exit early with clear error messages if:
- The `oc` CLI is not installed
- The user is not logged into a cluster
- The cluster is unreachable

This prevents confusing errors later in the command execution.

## Commands Using This Skill

This skill should be used by OpenShift plugin commands that interact with a cluster.
