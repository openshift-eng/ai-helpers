---
name: RHCOS Template Manager
description: Download and manage RHCOS OVA templates for OpenShift vSphere installations
---

# RHCOS Template Manager

Download, cache, and upload RHCOS (Red Hat CoreOS) OVA templates to vSphere for faster OpenShift installations.

## Why Use Templates?

Installing OpenShift without a pre-uploaded template requires the installer to upload a ~1GB OVA during installation:
- **Over VPN**: 30-60 minutes per installation
- **On fast network**: 5-10 minutes per installation

With a pre-uploaded template:
- **First cluster**: 10-30 minutes (one-time upload)
- **Subsequent clusters**: 2-5 minutes (template clone)

**Total savings**: 25-55 minutes per cluster after the first one!

## Quick Start

### Install a Template

```bash
# Set up vSphere connection
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USERNAME="administrator@vsphere.local"
export VSPHERE_PASSWORD="your-password"

# Download and upload RHCOS template for OpenShift 4.20
bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/datastore1 \
  --cluster /DC1/host/Cluster1
```

### Use in install-config.yaml

```yaml
platform:
  vsphere:
    failureDomains:
    - name: us-east-1
      topology:
        datacenter: DC1
        computeCluster: /DC1/host/Cluster1
        datastore: /DC1/datastore/datastore1
        template: /DC1/vm/rhcos-420.94.202501071309-0-template  # ← Template path
```

## Commands

### install - Download and Upload in One Step

Download RHCOS OVA and upload to vSphere as a template.

**Usage:**
```bash
manage-rhcos-template.sh install <version> \
  --datacenter <name> \
  --datastore <path> \
  --cluster <path>
```

**Example:**
```bash
bash manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/datastore1 \
  --cluster /DC1/host/Cluster1
```

**Options:**
- `--template-name <name>` - Custom template name (default: auto-generated)
- `--use-govc` - Force use of govc instead of vsphere-helper

---

### download - Download OVA Only

Download RHCOS OVA to local cache without uploading to vSphere.

**Usage:**
```bash
manage-rhcos-template.sh download <version>
```

**Example:**
```bash
bash manage-rhcos-template.sh download 4.20
# Output: .work/openshift-vsphere-install/ova-cache/rhcos-vmware.x86_64.ova
```

---

### upload - Upload Existing OVA

Upload a previously downloaded OVA to vSphere.

**Usage:**
```bash
manage-rhcos-template.sh upload <ova-file> \
  --datacenter <name> \
  --datastore <path> \
  --cluster <path>
```

**Example:**
```bash
bash manage-rhcos-template.sh upload /path/to/rhcos.ova \
  --datacenter DC1 \
  --datastore /DC1/datastore/datastore1 \
  --cluster /DC1/host/Cluster1
```

---

### list - List Cached OVAs

Show all cached OVA files and their sizes.

**Usage:**
```bash
manage-rhcos-template.sh list
```

**Example Output:**
```
Cached OVA files in .work/openshift-vsphere-install/ova-cache:

  rhcos-4.20.ova (1.2G) - RHCOS 420.94.202501071309-0
  rhcos-4.19.ova (1.1G) - RHCOS 419.92.202412345678-0

Total cache size: 2.3G
```

---

### clean - Remove Cached OVAs

Remove all cached OVA files to free up disk space.

**Usage:**
```bash
manage-rhcos-template.sh clean
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `VSPHERE_SERVER` | vCenter server hostname | Yes | - |
| `VSPHERE_USERNAME` | vCenter username | Yes | - |
| `VSPHERE_PASSWORD` | vCenter password | Yes | - |
| `VSPHERE_INSECURE` | Skip SSL verification | No | `false` |
| `CACHE_DIR` | OVA cache directory | No | `.work/openshift-vsphere-install/ova-cache` |

## How It Works

### Download Process

1. **Fetch Metadata**: Query OpenShift installer repository for RHCOS version and OVA URL
2. **Check Cache**: Look for existing OVA in cache directory
3. **Download**: Download OVA from official mirror (if not cached)
4. **Verify**: Validate SHA256 checksum
5. **Cache**: Store OVA for reuse

### Upload Process

1. **Check Existence**: Verify if template already exists in vSphere
2. **Import OVA**: Upload OVA to vSphere as a VM using `govc`
3. **Verify**: Confirm template was created successfully
4. **Return Path**: Output template path for use in install-config.yaml

### Caching Behavior

- OVAs are cached in `.work/openshift-vsphere-install/ova-cache/`
- Checksums are verified before reuse
- Corrupted files are automatically re-downloaded
- Cache persists across installations
- Use `clean` command to remove cached files

## Version Mapping

The skill automatically maps OpenShift versions to RHCOS versions:

| OpenShift Version | RHCOS Branch | OVA Source |
|-------------------|--------------|------------|
| 4.20.x | release-4.20 | `openshift/installer` GitHub |
| 4.19.x | release-4.19 | `openshift/installer` GitHub |
| 4.18.x | release-4.18 | `openshift/installer` GitHub |

## Prerequisites

### Required Tools

- **Python 3** - For metadata fetching
- **curl** - For downloading OVAs
- **govc** - For uploading to vSphere

Install govc if missing:
```bash
bash plugins/openshift/scripts/install-govc.sh
```

### vSphere Requirements

- vCenter 7.x or 8.x
- User with permissions to:
  - Import OVAs
  - Create VMs
  - Access datastores

### Network Access

- Internet connection to download OVAs
- Access to vCenter server
- GitHub access for metadata

## SSL Certificates

For secure connections (recommended), install vCenter certificates:

```bash
bash plugins/openshift/scripts/install-vcenter-certs.sh vcenter.example.com
```

Or use insecure connection (not recommended):
```bash
export VSPHERE_INSECURE=true
```

## Examples

### Example 1: Basic Installation

```bash
# Set credentials
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USERNAME="admin@vsphere.local"
export VSPHERE_PASSWORD="password"

# Install template
bash manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/ds1 \
  --cluster /DC1/host/Cluster1

# Output:
# [INFO] Fetching RHCOS metadata for OpenShift 4.20...
# [INFO] RHCOS version: 420.94.202501071309-0
# [INFO] Downloading RHCOS OVA (this may take several minutes)...
# [INFO] ✓ Download complete
# [INFO] ✓ Checksum verified
# [INFO] Uploading OVA to vSphere (this may take 10-30 minutes)...
# [INFO] ✓ OVA import complete
# [INFO] ✓ Template created successfully: /DC1/vm/rhcos-420.94.202501071309-0-template
#
# /DC1/vm/rhcos-420.94.202501071309-0-template
```

### Example 2: Download Then Upload

```bash
# Download OVA (can be done offline or before vSphere access)
OVA_PATH=$(bash manage-rhcos-template.sh download 4.20)
echo "Downloaded: $OVA_PATH"

# Later, upload to vSphere
bash manage-rhcos-template.sh upload "$OVA_PATH" \
  --datacenter DC1 \
  --datastore /DC1/datastore/ds1 \
  --cluster /DC1/host/Cluster1
```

### Example 3: Custom Template Name

```bash
bash manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/ds1 \
  --cluster /DC1/host/Cluster1 \
  --template-name my-custom-rhcos-template
```

### Example 4: Cache Management

```bash
# List cached OVAs
bash manage-rhcos-template.sh list

# Clean cache to free space
bash manage-rhcos-template.sh clean
```

## Troubleshooting

### Download Fails

**Problem**: `Error: failed to fetch RHCOS metadata`

**Solution**:
- Check internet connection
- Verify OpenShift version exists
- Check GitHub access

---

### Upload Fails

**Problem**: `Error: failed to connect to vSphere`

**Solution**:
- Verify vCenter credentials
- Install certificates or use `VSPHERE_INSECURE=true`
- Check network access to vCenter

---

### Template Already Exists

**Behavior**: Script detects existing template and skips upload

**Output**:
```
[INFO] Template already exists: rhcos-420.94.202501071309-0-template
[INFO] Skipping upload
```

This is normal and saves time.

---

### Checksum Mismatch

**Problem**: `Error: Checksum verification failed!`

**Solution**: Script automatically re-downloads. If persistent:
- Check disk space
- Verify network stability
- Report issue if mirror is corrupted

---

### Permission Denied

**Problem**: `Error: insufficient privileges`

**Solution**:
- Verify user has permission to import OVAs
- Check datastore access
- Verify resource pool permissions

## Performance

### Network Impact

| Connection | Download Time | Upload Time | Total |
|------------|---------------|-------------|-------|
| Fast (100+ Mbps) | 1-3 min | 5-10 min | 6-13 min |
| VPN (~10 Mbps) | 10-20 min | 15-30 min | 25-50 min |
| Slow (<5 Mbps) | 20-40 min | 30-60 min | 50-100 min |

### Disk Space

- Each OVA: ~1-1.5 GB
- Recommended: 10+ GB free space for cache

### Time Savings

| Scenario | Without Template | With Template | Savings |
|----------|------------------|---------------|---------|
| First cluster | 30-60 min | 25-50 min | 5-10 min |
| Second cluster | 30-60 min | 2-5 min | 25-55 min |
| Ten clusters | 300-600 min | 50-75 min | 250-525 min |

## Integration

### With `/openshift:install-vsphere`

This skill is automatically invoked by the install-vsphere command when the user chooses to pre-upload the template.

### With Custom Workflows

```bash
#!/bin/bash
# Custom cluster creation script

# 1. Install template once
TEMPLATE=$(bash manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/ds1 \
  --cluster /DC1/host/Cluster1)

# 2. Create multiple clusters using the same template
for cluster in cluster1 cluster2 cluster3; do
  # Generate install-config.yaml with template path
  cat > install-config.yaml <<EOF
apiVersion: v1
metadata:
  name: $cluster
platform:
  vsphere:
    failureDomains:
    - topology:
        template: $TEMPLATE
# ... rest of config
EOF

  # Run installation
  openshift-install create cluster
done
```

## Files

```
rhcos-template-manager/
├── fetch-rhcos-metadata.py      # Python script to fetch RHCOS metadata
├── manage-rhcos-template.sh     # Main management script
├── SKILL.md                     # AI skill instructions
└── README.md                    # This file
```

## Related

- **Scripts**: `plugins/openshift/scripts/install-govc.sh` - Install govc CLI
- **Skills**: `plugins/openshift/skills/vsphere-discovery` - vSphere infrastructure discovery
- **Command**: `/openshift:install-vsphere` - Uses this skill for template management
