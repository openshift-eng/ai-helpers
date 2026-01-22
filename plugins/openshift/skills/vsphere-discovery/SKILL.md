---
name: vSphere Discovery
description: Auto-discover vSphere infrastructure (datacenters, clusters, datastores, networks) using govmomi with correct path handling
---

# vSphere Discovery Skill

This skill discovers vSphere infrastructure components using either the `vsphere-helper` binary (govmomi-based, preferred) or `govc` CLI (fallback) and presents them to users for interactive selection.

## When to Use This Skill

Use this skill when you need to:
- Auto-discover vSphere infrastructure components
- Get correct vSphere inventory paths for install-config.yaml
- List datacenters, clusters, datastores, or networks
- Present interactive dropdowns for user selection
- Handle vCenter authentication and certificate setup

This skill is used by:
- `/openshift:install-vsphere` - For gathering vSphere infrastructure details
- `/openshift:create-cluster` - For cluster provisioning workflows

## Prerequisites

Before starting, ensure these tools are available:

1. **vsphere-helper binary (Preferred)**
   - Check if available: `which vsphere-helper`
   - If not available, check if it exists in skill directory: `ls plugins/openshift/skills/vsphere-discovery/vsphere-helper`
   - If source exists but binary doesn't, offer to build it:
     ```bash
     cd plugins/openshift/skills/vsphere-discovery
     make build
     # Or for user installation:
     make install
     ```
   - **Why prefer vsphere-helper?**
     - Uses govmomi library directly → correct path handling
     - Returns structured JSON → easy parsing
     - Better error messages
     - Faster than spawning govc subprocesses

2. **govc CLI (Fallback)**
   - Check if available: `which govc`
   - If not available, install using: `bash plugins/openshift/scripts/install-govc.sh`
   - Used when vsphere-helper binary is not available

3. **vCenter Certificates**
   - Required for secure connection (VSPHERE_INSECURE=false)
   - Install using: `bash plugins/openshift/scripts/install-vcenter-certs.sh <vcenter-server>`
   - Optional if using insecure connection (not recommended for production)

## Input Format

The user will provide:
1. **vCenter Server URL** - e.g., "vcenter.ci.ibmc.devcluster.openshift.com" or "vcenter.example.com"
2. **vCenter Username** - e.g., "administrator@vsphere.local"
3. **vCenter Password** - Handle securely, never log or display

Optional:
4. **Datacenter name** - If already known, skip datacenter discovery
5. **Insecure connection** - Whether to skip SSL verification (default: false)

## Output Format

Return a structured result containing selected infrastructure components:

```json
{
  "datacenter": "DC1",
  "datacenter_path": "/DC1",
  "cluster": "Cluster1",
  "cluster_path": "/DC1/host/Cluster1",
  "datastore": "datastore1",
  "datastore_path": "/DC1/datastore/datastore1",
  "network": "ci-vlan-981",
  "network_path": "/DC1/network/ci-vlan-981"
}
```

**Path Handling Rules (CRITICAL for install-config.yaml):**
- **datacenter**: Name only, no leading slash (e.g., "DC1")
- **cluster_path**: Full path required (e.g., "/DC1/host/Cluster1")
- **datastore_path**: Full path required (e.g., "/DC1/datastore/datastore1")
- **network**: Name only, no path prefix (e.g., "ci-vlan-981")

## Implementation Steps

### Step 1: Choose Discovery Tool

Determine which tool to use:

```bash
# Check for vsphere-helper binary (preferred)
if which vsphere-helper &>/dev/null; then
  echo "Using vsphere-helper (govmomi-based)"
  USE_VSPHERE_HELPER=true
elif [ -f "plugins/openshift/skills/vsphere-discovery/vsphere-helper" ]; then
  echo "Using vsphere-helper from skill directory"
  USE_VSPHERE_HELPER=true
  VSPHERE_HELPER_PATH="plugins/openshift/skills/vsphere-discovery/vsphere-helper"
else
  echo "vsphere-helper not found, checking for govc..."
  if which govc &>/dev/null; then
    echo "Using govc CLI (fallback)"
    USE_VSPHERE_HELPER=false
  else
    echo "Neither vsphere-helper nor govc found. Installing govc..."
    bash plugins/openshift/scripts/install-govc.sh
    USE_VSPHERE_HELPER=false
  fi
fi
```

### Step 2: Install vCenter Certificates (Optional but Recommended)

```bash
# Prompt user if they want to install vCenter certificates
# This enables secure SSL connections (VSPHERE_INSECURE=false)

read -p "Install vCenter SSL certificates for secure connection? (recommended) [Y/n]: " response
if [[ "$response" =~ ^([yY]|)$ ]]; then
  bash plugins/openshift/scripts/install-vcenter-certs.sh "$VCENTER_SERVER"
  VSPHERE_INSECURE=false
else
  echo "Skipping certificate installation. Using insecure connection."
  VSPHERE_INSECURE=true
fi
```

### Step 3: Set up vSphere Connection Environment

```bash
# Set environment variables for vsphere-helper
export VSPHERE_SERVER="$VCENTER_SERVER"
export VSPHERE_USERNAME="$VCENTER_USERNAME"
export VSPHERE_PASSWORD="$VCENTER_PASSWORD"
export VSPHERE_INSECURE="$VSPHERE_INSECURE"  # "true" or "false"

# For govc (if using fallback)
export GOVC_URL="https://${VCENTER_SERVER}/sdk"
export GOVC_USERNAME="$VCENTER_USERNAME"
export GOVC_PASSWORD="$VCENTER_PASSWORD"
export GOVC_INSECURE="$VSPHERE_INSECURE"
```

### Step 4: Discover Datacenters

**Using vsphere-helper (preferred):**
```bash
# List all datacenters
DATACENTERS_JSON=$(vsphere-helper list-datacenters)

# Parse JSON to get datacenter names and paths
echo "$DATACENTERS_JSON" | jq -r '.[] | "\(.name) (\(.path))"'

# Example output:
# DC1 (/DC1)
# DC2 (/DC2)
# vcenter-110-dc01 (/vcenter-110-dc01)
```

**Using govc (fallback):**
```bash
# List all datacenters
govc ls /

# Example output:
# /DC1
# /DC2
# /vcenter-110-dc01
```

**Present to user:**
- Use `AskUserQuestion` tool to present dropdown of available datacenters
- Store user's selection

**Path extraction:**
```bash
# From vsphere-helper JSON
DATACENTER_NAME=$(echo "$DATACENTERS_JSON" | jq -r ".[] | select(.path == \"$USER_SELECTION\") | .name")

# From govc output
DATACENTER_NAME=$(echo "$USER_SELECTION" | sed 's|^/||')  # Remove leading slash
```

**IMPORTANT:** For install-config.yaml, use datacenter NAME without leading slash (e.g., "DC1", not "/DC1")

### Step 5: Discover Clusters

**Using vsphere-helper (preferred):**
```bash
# List clusters in selected datacenter
CLUSTERS_JSON=$(vsphere-helper list-clusters --datacenter "$DATACENTER_NAME")

# Parse JSON
echo "$CLUSTERS_JSON" | jq -r '.[] | "\(.name) (\(.path))"'

# Example output:
# Cluster1 (/DC1/host/Cluster1)
# vcenter-110-cl01 (/vcenter-110-dc01/host/vcenter-110-cl01)
```

**Using govc (fallback):**
```bash
# List clusters
govc ls "/${DATACENTER_NAME}/host"

# Example output:
# /DC1/host/Cluster1
# /DC1/host/Cluster2
```

**Present to user:**
- Use `AskUserQuestion` tool with dropdown
- Display cluster name and full path for clarity

**Path extraction:**
```bash
# From vsphere-helper JSON
CLUSTER_PATH=$(echo "$CLUSTERS_JSON" | jq -r ".[] | select(.name == \"$USER_SELECTION\") | .path")

# From govc output
CLUSTER_PATH="$USER_SELECTION"  # Already has full path
```

**IMPORTANT:** For install-config.yaml, use FULL cluster path (e.g., "/DC1/host/Cluster1")

### Step 6: Discover Datastores

**Using vsphere-helper (preferred):**
```bash
# List datastores with capacity information
DATASTORES_JSON=$(vsphere-helper list-datastores --datacenter "$DATACENTER_NAME")

# Parse and format with capacity info
echo "$DATASTORES_JSON" | jq -r '.[] | "\(.name): \(.freeSpace / 1024 / 1024 / 1024 | floor)GB free / \(.capacity / 1024 / 1024 / 1024 | floor)GB total (\(.type))"'

# Example output:
# datastore1: 500GB free / 1000GB total (VMFS)
# vcenter-110-cl01-ds-vsan01: 2048GB free / 4096GB total (vsan)
```

**Using govc (fallback):**
```bash
# List datastores
govc ls "/${DATACENTER_NAME}/datastore"

# Get capacity for each datastore
for ds in $(govc ls "/${DATACENTER_NAME}/datastore"); do
  ds_name=$(basename "$ds")
  free=$(govc datastore.info -json "$ds" | jq -r '.Datastores[0].Info.FreeSpace')
  capacity=$(govc datastore.info -json "$ds" | jq -r '.Datastores[0].Info.Capacity')
  free_gb=$((free / 1024 / 1024 / 1024))
  capacity_gb=$((capacity / 1024 / 1024 / 1024))
  echo "$ds_name: ${free_gb}GB free / ${capacity_gb}GB total"
done
```

**Present to user:**
- Use `AskUserQuestion` tool with dropdown
- Show datastore name with capacity information for better decision-making

**Path extraction:**
```bash
# From vsphere-helper JSON
DATASTORE_PATH=$(echo "$DATASTORES_JSON" | jq -r ".[] | select(.name == \"$USER_SELECTION\") | .path")

# From govc output
DATASTORE_PATH="/${DATACENTER_NAME}/datastore/${USER_SELECTION}"
```

**IMPORTANT:** For install-config.yaml, use FULL datastore path (e.g., "/DC1/datastore/datastore1")

### Step 7: Discover Networks

**Using vsphere-helper (preferred):**
```bash
# List networks
NETWORKS_JSON=$(vsphere-helper list-networks --datacenter "$DATACENTER_NAME")

# Parse JSON
echo "$NETWORKS_JSON" | jq -r '.[] | "\(.name) (\(.type))"'

# Example output:
# ci-vlan-981 (DistributedVirtualPortgroup)
# VM Network (Network)
```

**Using govc (fallback):**
```bash
# List networks
govc ls "/${DATACENTER_NAME}/network"

# Example output:
# /DC1/network/ci-vlan-981
# /DC1/network/VM Network
```

**Present to user:**
- Use `AskUserQuestion` tool with dropdown
- Show network name and type
- Note: User should select the IBM Cloud Classic VLAN-associated port group if applicable

**Path extraction:**
```bash
# From vsphere-helper JSON
NETWORK_NAME=$(echo "$NETWORKS_JSON" | jq -r ".[] | select(.path == \"$USER_SELECTION\") | .name")

# From govc output
NETWORK_NAME=$(basename "$USER_SELECTION")
```

**IMPORTANT:** For install-config.yaml, use network NAME only without path prefix (e.g., "ci-vlan-981", not "/DC1/network/ci-vlan-981")

### Step 8: Return Results

Compile all discovered information and return as structured data:

```bash
# Create result JSON
cat > /tmp/vsphere-discovery-result.json <<EOF
{
  "datacenter": "$DATACENTER_NAME",
  "datacenter_path": "/$DATACENTER_NAME",
  "cluster": "$(basename "$CLUSTER_PATH")",
  "cluster_path": "$CLUSTER_PATH",
  "datastore": "$(basename "$DATASTORE_PATH")",
  "datastore_path": "$DATASTORE_PATH",
  "network": "$NETWORK_NAME",
  "network_path": "/${DATACENTER_NAME}/network/${NETWORK_NAME}"
}
EOF

# Display summary to user
echo "=== vSphere Discovery Complete ==="
cat /tmp/vsphere-discovery-result.json | jq .

# Return result
cat /tmp/vsphere-discovery-result.json
```

## Error Handling

### Connection Errors

**If connection to vCenter fails:**
```
Error: failed to connect to vSphere: x509: certificate signed by unknown authority
```

**Solution:**
- Install vCenter certificates: `bash plugins/openshift/scripts/install-vcenter-certs.sh <vcenter-server>`
- Or use insecure connection (not recommended): `export VSPHERE_INSECURE=true`

### Authentication Errors

**If authentication fails:**
```
Error: failed to connect to vSphere: ServerFaultCode: Cannot complete login due to an incorrect user name or password
```

**Solution:**
- Verify vCenter username and password
- Ensure user has correct permissions
- Check if account is locked

### Discovery Errors

**If datacenter/cluster/datastore not found:**
```
Error: failed to find datacenter 'DC1': datacenter 'DC1' not found
```

**Solution:**
- List available resources to verify exact names
- Check user has permission to view the resource
- Verify vCenter server is correct

### Tool Not Available

**If neither vsphere-helper nor govc available:**
- Offer to install govc: `bash plugins/openshift/scripts/install-govc.sh`
- Or offer to build vsphere-helper: `cd plugins/openshift/skills/vsphere-discovery && make install`

## Benefits of vsphere-helper vs govc

| Feature | vsphere-helper (govmomi) | govc CLI |
|---------|-------------------------|----------|
| **Path Accuracy** | ✅ Native govmomi paths | ⚠️ Manual string parsing |
| **Output Format** | ✅ Structured JSON | ⚠️ Text parsing required |
| **Performance** | ✅ Single binary call | ⚠️ Multiple subprocess spawns |
| **Error Messages** | ✅ Detailed Go errors | ⚠️ Generic CLI errors |
| **Type Safety** | ✅ Strongly typed | ❌ Strings only |
| **Session Management** | ✅ Efficient connection | ⚠️ Login per command |

**Recommendation:** Always prefer vsphere-helper when available. Gracefully fall back to govc when needed.

## Building vsphere-helper

If the binary is not pre-built, guide the user to build it:

```bash
cd plugins/openshift/skills/vsphere-discovery

# Build for current platform
make build

# Or install to ~/.local/bin
make install

# Or build for all platforms
make build-all
```

Requirements:
- Go 1.23 or later
- Internet connection (to download govmomi dependency)

The Makefile handles cross-compilation for:
- Linux: amd64, arm64
- macOS: amd64, arm64 (M1/M2)

## Example Workflow

```bash
# 1. Set up environment
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USERNAME="administrator@vsphere.local"
export VSPHERE_PASSWORD="mypassword"
export VSPHERE_INSECURE="false"

# 2. Install certificates (recommended)
bash plugins/openshift/scripts/install-vcenter-certs.sh "$VSPHERE_SERVER"

# 3. Discover datacenters
vsphere-helper list-datacenters
# User selects: "DC1"

# 4. Discover clusters
vsphere-helper list-clusters --datacenter DC1
# User selects: "/DC1/host/Cluster1"

# 5. Discover datastores
vsphere-helper list-datastores --datacenter DC1
# User selects: "/DC1/datastore/datastore1" (500GB free)

# 6. Discover networks
vsphere-helper list-networks --datacenter DC1
# User selects: "ci-vlan-981"

# 7. Return result JSON
{
  "datacenter": "DC1",
  "cluster_path": "/DC1/host/Cluster1",
  "datastore_path": "/DC1/datastore/datastore1",
  "network": "ci-vlan-981"
}
```

## Notes

- **Security:** Never log or display the vCenter password
- **Cleanup:** Unset environment variables after use if they contain sensitive data
- **Compatibility:** Supports vCenter 7.x and 8.x
- **Performance:** vsphere-helper is significantly faster for multiple queries (single session vs multiple govc calls)
- **Path Correctness:** Using govmomi ensures paths match exactly what OpenShift installer expects
