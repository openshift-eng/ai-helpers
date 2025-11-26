# vSphere Discovery Skill

Auto-discover vSphere infrastructure components (datacenters, clusters, datastores, networks) with correct path handling for OpenShift installations.

## Overview

This skill provides automated vSphere infrastructure discovery using:
- **vsphere-helper** binary (preferred) - Go binary using govmomi library for accurate path handling
- **govc** CLI (fallback) - VMware's official CLI tool

The skill is used by `/openshift:install-vsphere` and other OpenShift cluster provisioning commands to gather vSphere infrastructure details.

## Quick Start

### Prerequisites

1. **vCenter Access** - URL, username, and password
2. **Go 1.23+** (only if building from source)

### Building the Binary

```bash
cd plugins/openshift/skills/vsphere-discovery

# Build for your current platform
make build

# Or install to ~/.local/bin
make install

# Or build for all platforms
make build-all
```

### Using vsphere-helper

```bash
# Set up environment
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USERNAME="administrator@vsphere.local"
export VSPHERE_PASSWORD="your-password"
export VSPHERE_INSECURE="false"  # true to skip SSL verification

# List all datacenters
vsphere-helper list-datacenters

# List clusters in a datacenter
vsphere-helper list-clusters --datacenter DC1

# List datastores with capacity info
vsphere-helper list-datastores --datacenter DC1

# List networks
vsphere-helper list-networks --datacenter DC1
```

## Features

### Accurate Path Handling

Unlike text-based govc parsing, vsphere-helper uses govmomi library directly to ensure paths match exactly what OpenShift expects:

- **Datacenter**: Name only, no leading slash (e.g., `DC1`)
- **Cluster**: Full path required (e.g., `/DC1/host/Cluster1`)
- **Datastore**: Full path required (e.g., `/DC1/datastore/datastore1`)
- **Network**: Name only, no path prefix (e.g., `ci-vlan-981`)

### Structured JSON Output

All commands return well-formatted JSON for easy parsing:

```json
[
  {
    "name": "datastore1",
    "path": "/DC1/datastore/datastore1",
    "freeSpace": 537698893824,
    "capacity": 1073741824000,
    "type": "VMFS"
  }
]
```

### Capacity Information

Datastore listings include free space and capacity in bytes for informed decision-making.

## Commands

### list-datacenters

Lists all datacenters in vCenter.

**Example:**
```bash
vsphere-helper list-datacenters
```

**Output:**
```json
[
  {
    "name": "DC1",
    "path": "/DC1"
  },
  {
    "name": "vcenter-110-dc01",
    "path": "/vcenter-110-dc01"
  }
]
```

### list-clusters

Lists all clusters in a datacenter.

**Usage:**
```bash
vsphere-helper list-clusters --datacenter <datacenter-name>
```

**Example:**
```bash
vsphere-helper list-clusters --datacenter DC1
```

**Output:**
```json
[
  {
    "name": "Cluster1",
    "path": "/DC1/host/Cluster1"
  }
]
```

### list-datastores

Lists all datastores in a datacenter with capacity information.

**Usage:**
```bash
vsphere-helper list-datastores --datacenter <datacenter-name>
```

**Example:**
```bash
vsphere-helper list-datastores --datacenter DC1
```

**Output:**
```json
[
  {
    "name": "datastore1",
    "path": "/DC1/datastore/datastore1",
    "freeSpace": 537698893824,
    "capacity": 1073741824000,
    "type": "VMFS"
  },
  {
    "name": "vcenter-110-cl01-ds-vsan01",
    "path": "/vcenter-110-dc01/datastore/vcenter-110-cl01-ds-vsan01",
    "freeSpace": 2199023255552,
    "capacity": 4398046511104,
    "type": "vsan"
  }
]
```

### list-networks

Lists all networks in a datacenter.

**Usage:**
```bash
vsphere-helper list-networks --datacenter <datacenter-name>
```

**Example:**
```bash
vsphere-helper list-networks --datacenter DC1
```

**Output:**
```json
[
  {
    "name": "/DC1/network/ci-vlan-981",
    "path": "/DC1/network/ci-vlan-981",
    "type": "DistributedVirtualPortgroup"
  },
  {
    "name": "/DC1/network/VM Network",
    "path": "/DC1/network/VM Network",
    "type": "Network"
  }
]
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `VSPHERE_SERVER` | vCenter server hostname | Yes | - |
| `VSPHERE_USERNAME` | vCenter username | Yes | - |
| `VSPHERE_PASSWORD` | vCenter password | Yes | - |
| `VSPHERE_INSECURE` | Skip SSL verification | No | `false` |

## SSL Certificates

For secure connections (recommended), install vCenter SSL certificates:

```bash
bash plugins/openshift/scripts/install-vcenter-certs.sh vcenter.example.com
```

This installs certificates to:
- **macOS**: System Keychain
- **Linux**: `/usr/local/share/ca-certificates/`

Alternatively, use `VSPHERE_INSECURE=true` to skip SSL verification (not recommended for production).

## Building

### Requirements

- Go 1.23 or later
- make
- Internet connection (to download dependencies)

### Build Targets

```bash
# Build for current platform
make build

# Install to ~/.local/bin or ~/bin
make install

# Build for specific platforms
make build-linux          # Linux amd64
make build-linux-arm64    # Linux arm64
make build-darwin         # macOS amd64
make build-darwin-arm64   # macOS arm64 (M1/M2)

# Build for all platforms
make build-all

# Clean build artifacts
make clean

# Show help
make help
```

### Manual Build

```bash
# Download dependencies
go mod download

# Build
CGO_ENABLED=0 go build -ldflags "-s -w" -o vsphere-helper .
```

## Error Handling

### Certificate Errors

```
Error: x509: certificate signed by unknown authority
```

**Solution**: Install vCenter certificates or use `VSPHERE_INSECURE=true`

### Authentication Errors

```
Error: Cannot complete login due to an incorrect user name or password
```

**Solution**: Verify username, password, and ensure account is not locked

### Resource Not Found

```
Error: failed to find datacenter 'DC1': datacenter 'DC1' not found
```

**Solution**: List available resources and verify exact names

## Performance

vsphere-helper is significantly faster than govc for multiple queries:

| Operation | vsphere-helper | govc CLI |
|-----------|---------------|----------|
| Single query | ~100ms | ~500ms |
| 4 queries | ~400ms | ~2000ms |
| Session reuse | ✅ Yes | ❌ No |

**Why?** vsphere-helper maintains a single vSphere session across all operations, while govc creates a new session for each command.

## Contributing

### Project Structure

```
vsphere-discovery/
├── main.go           # CLI implementation
├── go.mod            # Go module definition
├── Makefile          # Build automation
├── SKILL.md          # AI skill instructions
└── README.md         # This file
```

### Adding New Commands

1. Add command function to `main.go`
2. Add command case to `main()` switch
3. Update SKILL.md with usage instructions
4. Update this README

## License

Part of the [ai-helpers](https://github.com/openshift-eng/ai-helpers) project.

## Related

- **Scripts**: `plugins/openshift/scripts/install-govc.sh` - Install govc CLI
- **Scripts**: `plugins/openshift/scripts/install-vcenter-certs.sh` - Install vCenter certificates
- **Command**: `/openshift:install-vsphere` - Uses this skill for infrastructure discovery
