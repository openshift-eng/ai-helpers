---
description: Install OpenShift on vSphere with automated workflow
argument-hint: [openshift-version]
---

## Name
openshift:install-vsphere

## Synopsis
```
/openshift:install-vsphere [openshift-version]
```

## Description
The `openshift:install-vsphere` command automates the complete workflow for installing OpenShift on VMware vSphere using the IPI (Installer-Provisioned Infrastructure) method. This command is specifically designed for IBM Cloud Classic vSphere environments with pre-configured VLANs and Route53 DNS management.

This command is designed to streamline the installation process by:
- Interactively gathering all required vSphere connection details and credentials
- Guiding through the IBM Cloud Classic network configuration workflow
- Assisting with VIP selection and Route53 DNS record creation
- Validating vSphere prerequisites (permissions, resources, network configuration)
- Generating a customized install-config.yaml file
- Downloading the appropriate openshift-install binary
- Executing the installation and monitoring progress
- Providing troubleshooting guidance if issues occur

The installation uses the IPI method, where the OpenShift installer automatically provisions the virtual machines and configures the infrastructure on vSphere.

**Environment-Specific Details:**
- Works with IBM Cloud Classic infrastructure with vSphere
- Supports mixed vCenter versions (7.x and 8.x)
- Pre-configured VLANs and subnets associated with vSphere port groups
- Requires manual Route53 DNS A record creation for api, api-int, and *.apps wildcard
- VIP selection via Route53 lookup and ping verification

## Implementation

### Phase 1: Prerequisites Check

1. **Check for required tools**:

   a. **jq**: Required for JSON parsing
      ```bash
      if ! which jq &>/dev/null; then
        echo "jq not found. Please install jq:"
        echo "  macOS: brew install jq"
        echo "  Linux: sudo apt-get install jq  (or yum install jq)"
        exit 1
      fi
      ```

   b. **go**: Required for building vsphere-helper
      ```bash
      if ! which go &>/dev/null; then
        echo "Go not found. Please install Go 1.23+:"
        echo "  https://golang.org/doc/install"
        exit 1
      fi
      ```

   c. **openshift-install**: Auto-download based on selected version
      - Will be downloaded in Phase 1, step 2 after version is determined

   d. **oc/kubectl**: Optional but recommended
      - Check if present, inform user they can be installed later

   **Note on govc:** NOT required - we use `vsphere-helper` (Go binary with govmomi) instead.
   - govc is only used as fallback if vsphere-helper fails
   - Will be auto-installed if needed via `plugins/openshift/scripts/install-govc.sh`

2. **Determine OpenShift version**:
   - If `$1` (openshift-version) is provided, use that version
   - If not provided, fetch available versions from the mirror and ask the user:
     ```bash
     # Fetch available "latest-*" versions from the mirror
     AVAILABLE_VERSIONS=$(curl -sL "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/" | \
       grep -oE 'href="latest-[^"]*/"' | \
       sed 's/href="latest-//g' | \
       sed 's/\/"//g' | \
       sort -V -r | \
       head -5)

     echo "Available OpenShift versions:"
     echo "$AVAILABLE_VERSIONS"
     ```
   - Present the versions (e.g., "4.20", "4.19", "4.18", "4.17") to the user using AskUserQuestion
   - Once version is selected (e.g., "4.20"), download the installer:
     ```bash
     # Use the reusable installer download script
     VERSION="{selected-version}"  # e.g., "4.20"
     bash plugins/openshift/scripts/download-openshift-installer.sh "$VERSION" .
     ```
     - Script location: `plugins/openshift/scripts/download-openshift-installer.sh`
     - Auto-detects OS (macOS/Linux) and architecture
     - Supports version formats: `4.20`, `latest-4.20`, `stable-4.20`
     - Downloads and extracts to current directory
     - Makes binary executable automatically

### Phase 2: Gather vSphere Configuration

**ALWAYS USE:** `vsphere-discovery` skill for vSphere infrastructure discovery.

**Why vsphere-helper (NOT govc):**
- ✅ Correct vSphere inventory paths (native govmomi library, no text parsing)
- ✅ Structured JSON output for easy parsing
- ✅ 5x faster performance (persistent session vs multiple govc calls)
- ✅ Detailed error messages
- ✅ Built-in retry logic and connection handling

**Fallback:** Only use govc if vsphere-helper build fails (auto-install via `plugins/openshift/scripts/install-govc.sh`)

**Skill location:** `plugins/openshift/skills/vsphere-discovery/`

**Implementation:** See SKILL.md for detailed usage instructions.

**CRITICAL SECURITY REQUIREMENT:**

⚠️ **CREDENTIAL HANDLING POLICY** ⚠️

When implementing this command, you MUST follow these security rules:

1. **NEVER display passwords, tokens, or credentials in:**
   - Command output
   - Bash commands
   - Log files
   - Error messages
   - Any terminal output

2. **Credential Collection Process:**
   - Prompt user interactively for: vCenter server, username, password
   - Store values in variables (never echo/display them)
   - Create environment file: `.work/.vcenter-env`
   - Set file permissions: `chmod 600 .work/.vcenter-env`
   - Source the file for all subsequent commands

3. **Environment File Format:**
   ```bash
   # .work/.vcenter-env (chmod 600)
   export GOVC_URL="https://${VCENTER_SERVER}/sdk"
   export GOVC_USERNAME="${VCENTER_USERNAME}"
   export GOVC_PASSWORD="${VCENTER_PASSWORD}"
   export GOVC_INSECURE=true
   ```

4. **Using Credentials:**
   ```bash
   # Source environment file before using govc
   source .work/.vcenter-env

   # Commands reference env vars (never display values)
   govc about
   govc ls /
   ```

5. **Reference:** See `SECURITY.md` for complete security policy

**END SECURITY REQUIREMENT**

1. **vCenter Connection Details and Credential Setup**:

   **Step 1: Collect Credentials from User**
   - Prompt for vCenter server URL (e.g., "vcenter.ci.ibmc.devcluster.openshift.com")
   - Prompt for vCenter username (e.g., "user@vsphere.local")
   - Prompt for vCenter password (**NEVER display or log this value**)
   - Prompt for certificate validation preference (true/false for GOVC_INSECURE)

   **Step 2: Create Secure Environment File**
   ```bash
   # Create .work directory if it doesn't exist
   mkdir -p .work

   # Create environment file with collected credentials
   # CRITICAL: Use variables, NEVER hardcode or echo credential values
   cat > .work/.vcenter-env <<EOF
   export GOVC_URL="https://${VCENTER_SERVER}/sdk"
   export GOVC_USERNAME="${VCENTER_USERNAME}"
   export GOVC_PASSWORD="${VCENTER_PASSWORD}"
   export GOVC_INSECURE=${VCENTER_INSECURE}
   EOF

   # Secure the file (owner read/write only)
   chmod 600 .work/.vcenter-env

   # Log success WITHOUT displaying credentials
   echo "✓ vCenter credentials configured"
   ```

   **Step 3: Install vCenter SSL Certificates (REQUIRED)**

   ⚠️ **CRITICAL:** The OpenShift installer ALWAYS validates vCenter SSL certificates. You MUST install certificates before running the installer.

   ```bash
   # Use the reusable certificate installation script
   bash plugins/openshift/scripts/install-vcenter-certs.sh "$VCENTER_SERVER"
   ```

   **What this does:**
   - Downloads vCenter SSL certificates from `https://${VCENTER_SERVER}/certs/download.zip`
   - Extracts OS-specific certificates (`.0` files from `certs/lin/` or `certs/mac/`)
   - Installs to system trust store:
     - **RHEL/Fedora**: `/etc/pki/ca-trust/source/anchors/` + `update-ca-trust extract`
     - **Debian/Ubuntu**: `/usr/local/share/ca-certificates/` + `update-ca-certificates`
     - **macOS**: System Keychain via `security add-trusted-cert`
   - Requires `sudo` for system trust store access

   **Script location:** `plugins/openshift/scripts/install-vcenter-certs.sh`

   **If this step fails:**
   - The installer will fail with: `tls: failed to verify certificate: x509: certificate signed by unknown authority`
   - You must fix certificate installation before proceeding

   **Step 4: Source Environment and Validate Connection**
   ```bash
   # Source the credentials
   source .work/.vcenter-env

   # Test connection (credentials referenced via env vars)
   # Note: govc uses GOVC_INSECURE=true from env, but installer will validate certs
   govc about
   ```

   **Important Notes:**
   - The `.work/` directory is in `.gitignore` - credentials will NOT be committed
   - All subsequent commands MUST source `.work/.vcenter-env` first
   - NEVER display credential values in any output
   - Certificates MUST be installed before running `openshift-install`
   - If connection fails, provide troubleshooting guidance WITHOUT exposing credentials

2. **vSphere Infrastructure Discovery (using vsphere-helper)**:

   **Prerequisites:**
   ```bash
   # Build vsphere-helper if not already built
   if [ ! -f plugins/openshift/skills/vsphere-discovery/vsphere-helper ]; then
     echo "Building vsphere-helper..."
     cd plugins/openshift/skills/vsphere-discovery && make build && cd -
   fi

   # Source vCenter credentials (from Phase 2, step 1)
   source .work/.vcenter-env
   ```

   a. **Datacenter**: List and select datacenter
      ```bash
      # List datacenters (returns JSON)
      DATACENTERS=$(plugins/openshift/skills/vsphere-discovery/vsphere-helper list-datacenters \
        --url "$GOVC_URL" \
        --username "$GOVC_USERNAME" \
        --password "$GOVC_PASSWORD" \
        --insecure "$GOVC_INSECURE")

      # Parse JSON to get datacenter names
      echo "$DATACENTERS" | jq -r '.[].name'
      ```
      - Present list to user via AskUserQuestion
      - **IMPORTANT**: Store only the datacenter name (e.g., "DC1") as required by install-config.yaml
      - Example: User selects "cidatacenter" from ["cidatacenter-1", "cidatacenter"]

   b. **Cluster**: List and select cluster
      ```bash
      # List clusters in selected datacenter
      CLUSTERS=$(plugins/openshift/skills/vsphere-discovery/vsphere-helper list-clusters \
        --url "$GOVC_URL" \
        --username "$GOVC_USERNAME" \
        --password "$GOVC_PASSWORD" \
        --insecure "$GOVC_INSECURE" \
        --datacenter "${DATACENTER_NAME}")

      # Parse JSON
      echo "$CLUSTERS" | jq -r '.[] | "\(.name) (\(.path))"'
      ```
      - Present clusters to user
      - **IMPORTANT**: Store the full path (e.g., "/cidatacenter/host/vcs-mdcnc-workload-1") for install-config.yaml

   c. **Datastore**: List and select datastore
      ```bash
      # List datastores in datacenter
      DATASTORES=$(plugins/openshift/skills/vsphere-discovery/vsphere-helper list-datastores \
        --url "$GOVC_URL" \
        --username "$GOVC_USERNAME" \
        --password "$GOVC_PASSWORD" \
        --insecure "$GOVC_INSECURE" \
        --datacenter "${DATACENTER_NAME}")

      # Parse JSON with free space info
      echo "$DATASTORES" | jq -r '.[] | "\(.name) (\(.freeSpace / 1024 / 1024 / 1024 | floor)GB free) - \(.path)"'
      ```
      - Present datastores with available space
      - Example: "datastore1 (500GB free) - /DC1/datastore/datastore1"
      - **IMPORTANT**: Store the full path for install-config.yaml

   d. **Network/Port Group**: List and select network
      ```bash
      # List networks in datacenter
      NETWORKS=$(plugins/openshift/skills/vsphere-discovery/vsphere-helper list-networks \
        --url "$GOVC_URL" \
        --username "$GOVC_USERNAME" \
        --password "$GOVC_PASSWORD" \
        --insecure "$GOVC_INSECURE" \
        --datacenter "${DATACENTER_NAME}")

      # Parse JSON
      echo "$NETWORKS" | jq -r '.[].name'
      ```
      - Present network names to user
      - **Note**: User should select IBM Cloud Classic VLAN-associated port group
      - **IMPORTANT**: Store only the network name (e.g., "ci-vlan-981") for install-config.yaml

   e. **Folder for VMs** (optional): Not implemented in vsphere-helper yet
      - Default: Use root vm folder
      - Can be added later if needed

   f. **Resource Pool** (optional): Not implemented in vsphere-helper yet
      - Default: Use default resource pool
      - Most users don't need custom resource pools

3. **Cluster Configuration**:
   - Cluster name (DNS-compatible name)
   - Base domain (e.g., "example.com")

4. **Failure Domain Configuration**:
   - Failure domain name (e.g., "us-east-1")
   - Region (e.g., "us-east")
   - Zone (e.g., "us-east-1a")
   - Note: These define the logical topology for the cluster deployment

5. **Network Configuration and VIP Selection**:

   **Preferred Method:** Use the `network-vip-configurator` skill for automated VIP selection and DNS management.

   **Overview:**
   This skill automates the complete VIP configuration workflow:
   - Scans subnet CIDR to find available IPs (parallel ping + optional Route53 check)
   - Presents available IPs for user selection (API VIP and Ingress VIP)
   - Creates DNS records (Route53 automated or manual guidance)
   - Verifies DNS resolution before proceeding

   **Step-by-step using the skill:**

   a. **Get Machine Network CIDR**:
      - Ask user for the subnet CIDR associated with the port group
      - Example: "10.0.0.0/24" or "172.16.10.0/24"

   b. **Scan for Available IPs**:
      ```bash
      # Use the skill's subnet scanner
      # Automatically pings IPs and checks Route53 (if configured)
      AVAILABLE_IPS=$(python3 plugins/openshift/skills/network-vip-configurator/scan-available-ips.py \
        "${MACHINE_NETWORK_CIDR}" \
        --max-candidates 10 \
        --verbose)

      # Parse and present to user
      echo "$AVAILABLE_IPS" | jq -r '.[].ip'
      ```

   c. **User Selects VIPs**:
      - Present available IPs using `AskUserQuestion` tool
      - User selects API VIP (e.g., "10.0.0.100")
      - User selects Ingress VIP (e.g., "10.0.0.101") - must be different from API VIP

   d. **Configure DNS** (Route53 or Manual):

      **Option 1: Route53 (Automated)**
      ```bash
      # Automatically create DNS records in Route53
      bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh create-route53 \
        --cluster-name "${CLUSTER_NAME}" \
        --base-domain "${BASE_DOMAIN}" \
        --api-vip "${API_VIP}" \
        --ingress-vip "${INGRESS_VIP}"

      # Creates:
      # - api.${CLUSTER_NAME}.${BASE_DOMAIN} → API VIP
      # - api-int.${CLUSTER_NAME}.${BASE_DOMAIN} → API VIP
      # - *.apps.${CLUSTER_NAME}.${BASE_DOMAIN} → Ingress VIP
      ```

      **Option 2: Manual DNS**
      - Guide user to create DNS A records manually
      - Display required records and their values
      - Wait for user confirmation

   e. **Verify DNS Resolution**:
      ```bash
      # Verify DNS records resolve correctly
      # The script will retry up to timeout if records haven't propagated yet
      bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh verify \
        --cluster-name "${CLUSTER_NAME}" \
        --base-domain "${BASE_DOMAIN}" \
        --api-vip "${API_VIP}" \
        --ingress-vip "${INGRESS_VIP}" \
        --timeout 60

      # Verifies:
      # - api.${CLUSTER_NAME}.${BASE_DOMAIN} → API VIP
      # - api-int.${CLUSTER_NAME}.${BASE_DOMAIN} → API VIP
      # - test.apps.${CLUSTER_NAME}.${BASE_DOMAIN} → Ingress VIP
      ```

   **Skill location:** `plugins/openshift/skills/network-vip-configurator/`

   **Features:**
   - Parallel subnet scanning (20 workers, ~10-15 seconds for /24)
   - Automated ping and Route53 availability checking
   - Route53 DNS automation or manual DNS guidance
   - DNS verification with automatic retry/timeout
   - Prevents VIP conflicts before installation

   **Alternative (manual method):**
   - See `plugins/openshift/skills/network-vip-configurator/README.md` for step-by-step manual process
   - Can be used if skill is unavailable or for debugging

6. **Pull Secret**:
   - Prompt user to provide their Red Hat pull secret
   - Can be obtained from https://console.redhat.com/openshift/install/pull-secret
   - Validate JSON format

7. **SSH Key**:
   - Check if `~/.ssh/id_rsa.pub` exists
   - If not, ask user to provide SSH public key
   - This allows SSH access to cluster nodes for debugging

8. **RHCOS Template (Optional - Recommended for VPN/Slow Connections)**:

   **Preferred Method:** Use the `rhcos-template-manager` skill for automated template management.

   **Why use a template?**
   - Installing OpenShift over VPN can be slow because the installer uploads the OVA (~1GB) each time
   - Pre-uploading the OVA as a vSphere template speeds up installation significantly
   - With template: 2-5 minutes (template clone)
   - Without template: 30-60 minutes (OVA upload)
   - **Savings**: 25-55 minutes per cluster after the first one!

   **Step 1: Check for Existing Templates First**

   Before uploading, always check if a template already exists in vSphere:

   ```bash
   # Check vSphere for existing RHCOS templates
   if bash plugins/openshift/skills/rhcos-template-manager/check-and-configure-template.sh \
       "${OCP_VERSION}" \
       "${DATACENTER_NAME}"; then
     # Template exists - capture the path
     TEMPLATE_PATH=$(bash plugins/openshift/skills/rhcos-template-manager/check-and-configure-template.sh \
         "${OCP_VERSION}" \
         "${DATACENTER_NAME}" | tail -1)
     echo "Using existing template: $TEMPLATE_PATH"
   else
     echo "No existing template found"
     TEMPLATE_PATH=""
   fi
   ```

   **What this does:**
   - Fetches RHCOS metadata from the installer repo (branch `release-${VERSION}`)
   - Extracts RHCOS version from OVA filename (e.g., `rhcos-9.6.20251015-1-vmware.x86_64.ova` → `9.6.20251015-1`)
   - Searches vSphere for VMs/templates with that version in the name
   - Returns the full template path if found, or exits with code 1 if not found

   **Step 2: Ask User if Template Should Be Uploaded (If Not Exists)**

   If no template exists, ask user: "Do you want to pre-upload the RHCOS OVA template? (Recommended for VPN/slow connections)"

   If **yes** and template doesn't exist, upload it:

   ```bash
   if [ -z "$TEMPLATE_PATH" ]; then
     # Download and upload RHCOS template in one step
     # The skill handles:
     # - Fetching RHCOS metadata from openshift/installer
     # - Downloading OVA (with caching and checksum verification)
     # - Uploading to vSphere using govc
     # - Template verification

     TEMPLATE_RESULT=$(bash plugins/openshift/skills/rhcos-template-manager/manage-rhcos-template.sh install ${OCP_VERSION} \
       --datacenter "${DATACENTER_NAME}" \
       --datastore "${DATASTORE_PATH}" \
       --cluster "${CLUSTER_PATH}")

     # Extract template path from result
     TEMPLATE_PATH=$(echo "$TEMPLATE_RESULT" | tail -1)

     echo "Template uploaded: $TEMPLATE_PATH"
   else
     echo "Skipping upload - using existing template: $TEMPLATE_PATH"
   fi
   ```

   **Skill location:** `plugins/openshift/skills/rhcos-template-manager/`

   **Features:**
   - Automatic RHCOS version detection based on OpenShift version
   - OVA caching (reuse across multiple installations)
   - SHA256 checksum verification
   - Template existence checking (skip if already exists)
   - Progress indicators for long-running operations
   - Detailed error messages and troubleshooting

   **Alternative (manual method):**
   - See `plugins/openshift/skills/rhcos-template-manager/README.md` for step-by-step manual process
   - Can be used if the skill is unavailable or for debugging

   If **no** (skip template upload):
   - Set TEMPLATE_PATH to empty/null
   - The installer will upload the OVA during installation (slower)

### Phase 3: Generate install-config.yaml

1. **Create working directory**:
   ```bash
   mkdir -p .work/openshift-vsphere-install/{cluster-name}
   cd .work/openshift-vsphere-install/{cluster-name}
   ```

2. **Generate install-config.yaml** with the following structure:
   ```yaml
   apiVersion: v1
   baseDomain: {base-domain}
   metadata:
     name: {cluster-name}
   networking:
     machineNetwork:
     - cidr: {machine-network-cidr}
   platform:
     vsphere:
       apiVIP: {api-vip}
       ingressVIP: {ingress-vip}
       vcenters:
       - server: {vcenter-server}
         user: {vcenter-username}
         password: '{vcenter-password}'
         datacenters:
         - {datacenter}
       failureDomains:
       - name: {failure-domain-name}  # e.g., "us-east-1"
         region: {region}  # e.g., "us-east"
         zone: {zone}  # e.g., "us-east-1a"
         server: {vcenter-server}
         topology:
           datacenter: {datacenter}
           computeCluster: {cluster}  # Full path (e.g., "/vcenter-110-dc01/host/vcenter-110-cl01")
           networks:
           - {network}  # Name only, no path prefix (e.g., "ci-vlan-981")
           datastore: {datastore}  # Full path (e.g., "/vcenter-110-dc01/datastore/vcenter-110-cl01-ds-vsan01")
           template: {template-path}  # OPTIONAL: Include if template was uploaded in Phase 2, step 8
   pullSecret: '{pull-secret}'
   sshKey: '{ssh-public-key}'
   ```

   **Important notes about the template field**:
   - **Include `template` field ONLY if** the user chose to pre-upload the RHCOS template in Phase 2, step 8
   - **Omit the entire `template` line** if the user skipped template upload
   - The template path should be the TEMPLATE_PATH from Phase 2, step 8e (e.g., `/vcenter-110-dc01/vm/rhcos-420.94.202501071309-0-template`)
   - If template is specified, the installer will clone this template instead of uploading the OVA

3. **Backup the install-config.yaml**:
   ```bash
   cp install-config.yaml install-config.yaml.backup
   ```
   Note: The installer consumes the install-config.yaml file, so keep a backup

4. **Display the configuration** to the user and ask for confirmation before proceeding

### Phase 4: Validate Prerequisites

1. **Verify vSphere prerequisites**:
   - Check vCenter version is supported (7.0+ recommended)
   - Verify user has required permissions (docs: https://docs.openshift.com/container-platform/latest/installing/installing_vsphere/installing-vsphere-installer-provisioned.html#installation-vsphere-installer-infra-requirements_installing-vsphere-installer-provisioned)
   - Check sufficient resources available (CPU, memory, storage)
   - Verify network connectivity and DNS resolution
   - Confirm VIPs are available and not in use

2. **DNS Prerequisites**:
   - Verify DNS records were created in Phase 2, step 4:
     - `api.{cluster-name}.{base-domain}` -> {api-vip}
     - `api-int.{cluster-name}.{base-domain}` -> {api-vip}
     - `*.apps.{cluster-name}.{base-domain}` -> {ingress-vip}
   - Re-verify DNS resolution using `dig`:
     ```bash
     dig +short api.{cluster-name}.{base-domain}
     dig +short api-int.{cluster-name}.{base-domain}
     dig +short randomtest.apps.{cluster-name}.{base-domain}
     ```
   - All queries should return the expected VIP addresses before proceeding

3. **Certificate Validation**:
   - If vCenter uses self-signed certificates, may need to set up certificate trust
   - Provide guidance on certificate handling if needed

### Phase 5: Execute Installation

1. **Run the installer**:
   ```bash
   ./openshift-install create cluster --dir=.work/openshift-vsphere-install/{cluster-name} --log-level=info
   ```

2. **Monitor installation progress**:
   - The installation typically takes 30-45 minutes
   - Display progress updates to the user
   - Watch for common errors (VIP conflicts, network issues, insufficient resources)

3. **Handle installation output**:
   - Save installation logs to `.work/openshift-vsphere-install/{cluster-name}/.openshift_install.log`
   - Monitor for ERROR or FATAL messages
   - If errors occur, parse logs and provide troubleshooting guidance

### Phase 6: Post-Installation

1. **Display cluster credentials**:
   - Extract kubeadmin password from `.work/openshift-vsphere-install/{cluster-name}/auth/kubeadmin-password`
   - Show cluster console URL: `https://console-openshift-console.apps.{cluster-name}.{base-domain}`
   - Show API endpoint: `https://api.{cluster-name}.{base-domain}:6443`

2. **Set up kubeconfig**:
   ```bash
   export KUBECONFIG=.work/openshift-vsphere-install/{cluster-name}/auth/kubeconfig
   ```

3. **Verify cluster health**:
   ```bash
   oc get nodes
   oc get co  # Check cluster operators
   oc get clusterversion
   ```

4. **Provide next steps**:
   - How to access the web console
   - How to add additional users
   - Where to find documentation for post-install configuration
   - How to delete the cluster (using `openshift-install destroy cluster`)

### Error Handling

Common installation failures and resolutions:

1. **VIP already in use**:
   - Verify VIPs are not assigned to other devices
   - Check DHCP range doesn't overlap with VIPs
   - Suggest using `ping` to test VIP availability

2. **Insufficient permissions**:
   - Verify vCenter user has all required privileges
   - Reference: https://docs.openshift.com/container-platform/latest/installing/installing_vsphere/installing-vsphere-installer-provisioned.html#installation-vsphere-installer-infra-requirements_installing-vsphere-installer-provisioned

3. **DNS resolution failures**:
   - Verify DNS records are created and propagated
   - Test with `dig api.{cluster-name}.{base-domain}`
   - Test with `dig test.apps.{cluster-name}.{base-domain}`

4. **Network connectivity issues**:
   - Verify vSphere network allows required traffic
   - Check firewall rules
   - Ensure DHCP is available on the network (for bootstrap)

5. **Insufficient resources**:
   - Check available CPU, memory, and storage in vSphere cluster
   - May need to reduce worker count or VM sizes

6. **Certificate errors**:
   - If using self-signed certs, may need to add to trust store
   - Consider using `--skip-tls-verify` for testing (not recommended for production)

If installation fails, provide:
- Relevant error messages from logs
- Specific troubleshooting steps based on the error
- Links to relevant documentation
- Option to retry with different configuration

## Return Value
- **Working directory**: `.work/openshift-vsphere-install/{cluster-name}/`
- **Kubeconfig**: `.work/openshift-vsphere-install/{cluster-name}/auth/kubeconfig`
- **Admin credentials**: `.work/openshift-vsphere-install/{cluster-name}/auth/kubeadmin-password`
- **Installation logs**: `.work/openshift-vsphere-install/{cluster-name}/.openshift_install.log`
- **Cluster information**: API endpoint, console URL, and access credentials displayed in terminal

## Examples

1. **Install latest stable OpenShift version**:
   ```
   /openshift:install-vsphere
   ```
   The command will interactively prompt for all required configuration.

2. **Install specific OpenShift version**:
   ```
   /openshift:install-vsphere 4.15.0
   ```
   Installs OpenShift 4.15.0 specifically.

3. **Install using stable channel**:
   ```
   /openshift:install-vsphere stable-4.16
   ```
   Installs the latest stable release from the 4.16 channel.

## Arguments
- $1: (Optional) OpenShift version to install. Can be a specific version (e.g., "4.15.0") or a channel (e.g., "stable-4.16", "fast-4.16"). If not provided, defaults to "stable" which installs the latest stable release.

## Notes

**IBM Cloud Classic Specific:**
- Port group must be obtained from infrastructure team before starting
- Route53 DNS records (api, api-int, *.apps) must be created manually before VIP selection
- Use Route53 queries and ping to determine available IP addresses for VIPs
- VIPs must be within the subnet CIDR associated with the port group
- Mixed vCenter versions (7.x and 8.x) are supported

**General Installation:**
- Installation typically takes 30-45 minutes to complete
- Ensure DNS records are created and verified before starting installation
- Keep the install-config.yaml.backup file for reference
- The installer will create a bootstrap VM that is automatically deleted after installation
- Default VM sizes: Control plane (4 vCPU, 16GB RAM, 120GB disk), Worker (2 vCPU, 8GB RAM, 120GB disk)
- Minimum cluster: 3 control plane + 2 worker nodes (can scale workers to 0 for minimal install)
- The .work directory contents should not be committed to git (already in .gitignore)

**Performance Optimization for VPN/Slow Connections:**
- Pre-uploading the RHCOS OVA template (Phase 2, step 8) significantly speeds up installation over VPN
- Without a template: installer uploads ~1GB OVA during installation (can take 30-60 minutes over VPN)
- With a template: installer clones the existing VM template (typically 2-5 minutes)
- The template can be reused for multiple cluster installations with the same OpenShift version
- Template files are cached in `.work/openshift-vsphere-install/ova-cache/` for reuse

## References
- Official vSphere IPI Installation Guide: https://docs.openshift.com/container-platform/latest/installing/installing_vsphere/installing-vsphere-installer-provisioned.html
- vSphere Prerequisites: https://docs.openshift.com/container-platform/latest/installing/installing_vsphere/installing-vsphere-installer-provisioned.html#installation-vsphere-installer-infra-requirements_installing-vsphere-installer-provisioned
- Download OpenShift installer: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
- Get Pull Secret: https://console.redhat.com/openshift/install/pull-secret
- RHCOS OVA metadata: https://github.com/openshift/installer/tree/main/data/data/coreos (per-version branches)
