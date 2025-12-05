---
name: RHCOS Template Manager
description: Download and manage RHCOS OVA templates for OpenShift vSphere installations with caching and automated upload
---

# RHCOS Template Manager Skill

This skill manages RHCOS (Red Hat CoreOS) OVA templates for OpenShift vSphere installations. It handles downloading OVA files from official sources, caching them locally, and uploading them to vSphere as reusable templates.

## When to Use This Skill

Use this skill when you need to:
- Pre-upload RHCOS OVA templates to vSphere before installation
- Speed up OpenShift installations over VPN or slow connections
- Cache RHCOS OVA files for reuse across multiple cluster installations
- Manage RHCOS template lifecycle (download, upload, verify, clean)

**Why use templates?**
- **Performance**: Installing OpenShift over VPN without a template requires uploading ~1GB OVA each time (30-60 minutes)
- **Efficiency**: With a template, the installer clones the existing VM (2-5 minutes)
- **Reusability**: One template can be used for multiple cluster installations with the same OpenShift version

This skill is used by:
- `/openshift:install-vsphere` - Optional step to speed up installation
- `/openshift:create-cluster` - Automated cluster provisioning

## Prerequisites

Before starting, ensure these tools are available:

1. **Python 3**
   - Check if available: `which python3`
   - Required for RHCOS metadata fetching
   - Usually pre-installed on Linux and macOS

2. **curl**
   - Check if available: `which curl`
   - Required for downloading OVA files
   - Usually pre-installed

3. **govc CLI**
   - Check if available: `which govc`
   - Required for uploading OVA to vSphere
   - Install if missing: `bash plugins/openshift/scripts/install-govc.sh`

4. **vSphere Connection**
   - vCenter server URL, username, and password
   - Sufficient permissions to import OVAs and create VMs
   - Certificates installed (optional but recommended)

## Input Format

The user will provide:

1. **OpenShift version** - e.g., "4.20", "4.19", "latest-4.20", "stable-4.19"
2. **vSphere infrastructure details** (for upload):
   - Datacenter name (e.g., "DC1")
   - Datastore path (e.g., "/DC1/datastore/datastore1")
   - Cluster path (e.g., "/DC1/host/Cluster1")
3. **vCenter credentials** (via environment variables):
   - VSPHERE_SERVER
   - VSPHERE_USERNAME
   - VSPHERE_PASSWORD

Optional:
4. **Template name** - Custom name for the template (auto-generated if not specified)
5. **Cache directory** - Where to store downloaded OVAs (default: `.work/openshift-vsphere-install/ova-cache`)

## Output Format

Return a structured result containing the template information:

```json
{
  "template_path": "/DC1/vm/rhcos-420.94.202501071309-0-template",
  "template_name": "rhcos-420.94.202501071309-0-template",
  "rhcos_version": "420.94.202501071309-0",
  "ova_cached": true,
  "ova_path": ".work/openshift-vsphere-install/ova-cache/rhcos-vmware.x86_64.ova"
}
```

## Implementation Steps

### Step 1: Ask User if They Want to Use a Template

Present the benefits and get user confirmation:

```
Installing OpenShift over VPN can be slow because the installer uploads a ~1GB OVA each time.

Pre-uploading the OVA as a vSphere template speeds up installation significantly:
  - Without template: 30-60 minutes OVA upload during installation
  - With template: 2-5 minutes template clone during installation

Do you want to pre-upload the RHCOS OVA template? (Recommended for VPN/slow connections)
```

If user says **no**, skip this skill entirely and let the installer upload the OVA.

If user says **yes**, continue to Step 2.

### Step 2: Determine RHCOS Version for OpenShift Release

The RHCOS version is tied to the OpenShift version. We need to:

1. Extract major.minor from the OpenShift version
   - Example: "4.20.1" → "4.20"
   - Example: "latest-4.19" → "4.19"

2. Map to the installer GitHub branch:
   - OpenShift 4.20.x → `release-4.20`
   - OpenShift 4.19.x → `release-4.19`
   - etc.

### Step 3: Fetch RHCOS Metadata

Use the Python helper script to fetch RHCOS metadata from the openshift/installer repository:

```bash
# Fetch metadata for OpenShift 4.20
METADATA_JSON=$(python3 plugins/openshift/skills/rhcos-template-manager/fetch-rhcos-metadata.py 4.20)

# Parse the JSON to extract information
OVA_URL=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['url'])")
RHCOS_VERSION=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['rhcos_version'])")
SHA256=$(echo "$METADATA_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['sha256'])")

echo "RHCOS Version: $RHCOS_VERSION"
echo "OVA URL: $OVA_URL"
echo "SHA256: $SHA256"
```

**Error Handling:**
- If the branch doesn't exist (version too new/old), the script will error with a clear message
- If network is unavailable, the script will error
- Always show the error message to the user and suggest troubleshooting

### Step 4: Download OVA (with Caching)

Use the management script to download the OVA:

```bash
# Download OVA for OpenShift 4.20
# The script will:
# - Check if already cached
# - Download if not cached
# - Verify SHA256 checksum
# - Store in cache directory

OVA_PATH=$(bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh download 4.20)

echo "OVA downloaded/cached at: $OVA_PATH"
```

**What happens:**
1. Script checks `.work/openshift-vsphere-install/ova-cache/` for existing OVA
2. If found, verifies SHA256 checksum
3. If not found or checksum fails, downloads from official mirror
4. Shows progress bar during download
5. Verifies checksum after download
6. Returns path to OVA file

**Error Handling:**
- Network errors: Show error and suggest checking internet connection
- Checksum mismatch: Script automatically re-downloads
- Disk space: If download fails due to space, suggest cleaning cache with `manage-rhcos-template.sh clean`

### Step 5: Set up vSphere Connection

Set environment variables for vSphere connection:

```bash
# These should be gathered from user earlier (in vSphere discovery phase)
export VSPHERE_SERVER="$VCENTER_SERVER"         # e.g., "vcenter.example.com"
export VSPHERE_USERNAME="$VCENTER_USERNAME"     # e.g., "administrator@vsphere.local"
export VSPHERE_PASSWORD="$VCENTER_PASSWORD"
export VSPHERE_INSECURE="${VSPHERE_INSECURE:-false}"  # "true" or "false"
```

**Security Note:** Never log or display the password. Use it only in environment variables.

### Step 6: Check vSphere for Existing Templates

Before uploading, check if a template or VM already exists with the RHCOS version:

```bash
# Source vCenter credentials
source .work/.vcenter-env

# Determine expected template name based on RHCOS version
EXPECTED_TEMPLATE_NAME="rhcos-${RHCOS_VERSION}-template"

echo "Checking vSphere for existing template: $EXPECTED_TEMPLATE_NAME"

# Search for existing template or VM with this version
# Search in both /vm and /template folders
EXISTING_TEMPLATE=$(govc find "/${DATACENTER_NAME}" -type m -name "*${RHCOS_VERSION}*" 2>/dev/null | head -1)

if [ -n "$EXISTING_TEMPLATE" ]; then
  echo "✓ Found existing template: $EXISTING_TEMPLATE"
  TEMPLATE_PATH="$EXISTING_TEMPLATE"
  echo "Using existing template instead of uploading"
else
  echo "No existing template found for RHCOS version $RHCOS_VERSION"
  TEMPLATE_PATH=""
fi
```

**What this checks:**
1. Searches for VMs or templates with the RHCOS version in the name
2. Searches in the entire datacenter (both vm and template folders)
3. If found, uses the existing template path
4. If not found, template path is empty (skip upload or proceed to Step 7)

**Why check first:**
- Avoids duplicate uploads (saves 10-30 minutes)
- Reuses existing templates from previous installations
- Prevents wasting datastore space

### Step 7: Upload OVA to vSphere (If Not Exists)

If no existing template was found in Step 6, upload the OVA:

```bash
if [ -z "$TEMPLATE_PATH" ]; then
  echo "No existing template found. Uploading OVA to vSphere..."

  # Upload OVA to vSphere
  # This will:
  # - Import OVA as a VM
  # - Verify template creation
  # - Return template path

  TEMPLATE_PATH=$(bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh upload \
    "$OVA_PATH" \
    --datacenter "$DATACENTER_NAME" \
    --datastore "$DATASTORE_PATH" \
    --cluster "$CLUSTER_PATH")

  echo "Template created at: $TEMPLATE_PATH"
else
  echo "Skipping upload - using existing template"
fi
```

**What happens:**
1. Uses `govc import.ova` to upload
2. Shows progress during upload (can take 10-30 minutes over VPN)
3. Verifies template was created successfully
4. Returns full template path for use in install-config.yaml

**Template Naming:**
- Auto-generated based on RHCOS version: `rhcos-{version}-template`
- Example: `rhcos-420.94.202501071309-0-template`
- Can be customized with `--template-name` option if needed

**Error Handling:**
- Connection errors: Verify vSphere credentials and network
- Permission errors: User may not have rights to import OVAs
- Storage errors: Datastore may be full or inaccessible
- Timeout errors: Upload may timeout over very slow connections (increase govc timeout if needed)

### Step 8: Update install-config.yaml with Template Path

If a template path was found or created, add it to the install-config.yaml:

```bash
if [ -n "$TEMPLATE_PATH" ]; then
  echo "Template path to use in install-config.yaml: $TEMPLATE_PATH"

  # The template path should be added to the failureDomains topology section:
  # platform:
  #   vsphere:
  #     failureDomains:
  #     - topology:
  #         template: $TEMPLATE_PATH
else
  echo "No template available - installer will upload OVA during installation"
fi
```

**Important:**
- If TEMPLATE_PATH is set, include the `template:` field in install-config.yaml
- If TEMPLATE_PATH is empty, omit the `template:` field entirely
- The installer will automatically upload the OVA if no template is specified

### Step 9: Return Results

Compile all information and return as structured data:

```bash
# Create result JSON
cat > /tmp/rhcos-template-result.json <<EOF
{
  "template_path": "$TEMPLATE_PATH",
  "template_name": "$(basename "$TEMPLATE_PATH")",
  "rhcos_version": "$RHCOS_VERSION",
  "ova_cached": true,
  "ova_path": "$OVA_PATH"
}
EOF

# Display summary to user
echo "=== RHCOS Template Ready ==="
cat /tmp/rhcos-template-result.json | jq .

# Return result
cat /tmp/rhcos-template-result.json
```

## Cache Management

### Listing Cached OVAs

```bash
# List all cached OVA files
bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh list

# Example output:
# Cached OVA files in .work/openshift-vsphere-install/ova-cache:
#
#   rhcos-4.20.ova (1.2G) - RHCOS 420.94.202501071309-0
#   rhcos-4.19.ova (1.1G) - RHCOS 419.92.202412345678-0
#
# Total cache size: 2.3G
```

### Cleaning Cache

```bash
# Remove all cached OVAs to free up disk space
bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh clean

# This will prompt for confirmation before deleting
```

**When to clean cache:**
- Low disk space
- After major OpenShift version upgrade (old OVAs no longer needed)
- When troubleshooting corrupted downloads

## Error Handling

### Python Script Errors

**Metadata Not Found (404)**
```
Error: RHCOS metadata not found for version 4.25. Branch 'release-4.25' may not exist yet.
```

**Solution:**
- Version may be too new (not released yet)
- Version may be invalid
- Verify version with: https://github.com/openshift/installer/branches

**Network Errors**
```
Error: Network error: [Errno -3] Temporary failure in name resolution
```

**Solution:**
- Check internet connection
- Verify DNS resolution
- Check if GitHub is accessible

### OVA Download Errors

**Download Failed**
```
[ERROR] Download failed
```

**Solution:**
- Check internet connection
- Verify OVA URL is accessible
- Check disk space in cache directory

**Checksum Mismatch**
```
[ERROR] Checksum verification failed!
Expected: abc123...
Got:      def456...
```

**Solution:**
- Script will automatically retry download
- If persistent, may indicate corrupted mirror file
- Report issue to OpenShift team

### vSphere Upload Errors

**Connection Failed**
```
Error: failed to connect to vSphere: x509: certificate signed by unknown authority
```

**Solution:**
- Install vCenter certificates: `bash plugins/openshift/scripts/install-vcenter-certs.sh <vcenter-server>`
- Or use insecure connection: `export VSPHERE_INSECURE=true`

**Permission Denied**
```
Error: insufficient privileges to perform operation
```

**Solution:**
- Verify user has permission to:
  - Import OVAs
  - Create VMs in the datacenter
  - Access the datastore
  - Use the resource pool

**Datastore Full**
```
Error: no space left on device
```

**Solution:**
- Free up space on the datastore
- Choose a different datastore with more capacity
- Delete old templates/VMs

**Upload Timeout**
```
Error: context deadline exceeded
```

**Solution:**
- Upload may be taking too long over slow connection
- Increase govc timeout: `export GOVC_OPERATION_TIMEOUT=3600` (1 hour)
- Consider uploading OVA manually first, then skip this step

## Performance Optimization

### With Template (Recommended)
```
OVA download:    5-30 minutes (one-time, cached)
OVA upload:      10-30 minutes (one-time)
Installation:    2-5 minutes (template clone)

Total first cluster:    15-60 minutes
Total subsequent:       2-5 minutes
```

### Without Template
```
Installation:    30-60 minutes (OVA upload per cluster)

Total per cluster:      30-60 minutes
```

**Savings:** 25-55 minutes per cluster after the first one!

## Integration with install-vsphere

The template path returned by this skill should be used in the install-config.yaml:

```yaml
platform:
  vsphere:
    failureDomains:
    - name: us-east-1
      topology:
        template: /DC1/vm/rhcos-420.94.202501071309-0-template  # ← Use template path here
```

If the template field is omitted, the installer will upload the OVA during installation.

## Example Workflow

```bash
# 1. Set up vSphere connection
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USERNAME="administrator@vsphere.local"
export VSPHERE_PASSWORD="mypassword"
export VSPHERE_INSECURE="false"

# 2. Download and upload in one step
TEMPLATE_PATH=$(bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh install 4.20 \
  --datacenter DC1 \
  --datastore /DC1/datastore/datastore1 \
  --cluster /DC1/host/Cluster1)

# 3. Template is ready for use
echo "Template: $TEMPLATE_PATH"
# Output: Template: /DC1/vm/rhcos-420.94.202501071309-0-template

# 4. Use in install-config.yaml
# template: /DC1/vm/rhcos-420.94.202501071309-0-template
```

## Notes

- **Caching**: OVA files are cached in `.work/openshift-vsphere-install/ova-cache/` and reused
- **Security**: Never log vCenter passwords
- **Compatibility**: Works with vCenter 7.x and 8.x
- **Reusability**: One template can be used for multiple cluster installations
- **Cleanup**: Use `manage-rhcos-template.sh clean` to remove cached OVAs when no longer needed
- **Disk Space**: Each OVA is approximately 1-1.5GB

## Benefits

1. **Speed**: 5-10x faster installation after first cluster
2. **Bandwidth**: Save bandwidth on repeated installations
3. **Reliability**: Cached OVAs reduce dependency on external mirrors during installation
4. **Flexibility**: Can pre-stage templates before cluster creation
5. **Reusability**: One template serves multiple clusters
