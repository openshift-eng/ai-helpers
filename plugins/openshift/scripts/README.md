# OpenShift Plugin Scripts

This directory contains reusable utility scripts for the OpenShift plugin commands.

## Available Scripts

### install-govc.sh

Automatically downloads and installs the latest version of `govc` (VMware vSphere CLI) for the current platform.

**Usage:**
```bash
bash plugins/openshift/scripts/install-govc.sh
```

**Features:**
- Auto-detects OS (Linux/macOS) and architecture (x86_64/arm64)
- Downloads the latest release from GitHub
- Installs to user-local directory (`~/.local/bin` or `~/bin`) when possible
- Falls back to system-wide installation (`/usr/local/bin`) if needed
- Verifies installation and reports version

**Used by:**
- `/openshift:install-vsphere` - For vSphere infrastructure auto-discovery
- `/openshift:create-cluster` - For cluster creation workflows

**Requirements:**
- `curl` - For downloading files
- `jq` - For parsing GitHub API responses
- `tar` - For extracting archives
- `sudo` - Only if installing to `/usr/local/bin`

---

### install-vcenter-certs.sh

Downloads and installs vCenter SSL certificates to the system trust store.

**Usage:**
```bash
bash plugins/openshift/scripts/install-vcenter-certs.sh <vcenter-server>
```

**Example:**
```bash
bash plugins/openshift/scripts/install-vcenter-certs.sh vcenter.example.com
```

**Features:**
- Downloads certificate bundle from vCenter
- Validates ZIP archive integrity
- Installs certificates to OS-specific trust store:
  - **macOS:** System Keychain
  - **Linux:** `/usr/local/share/ca-certificates/` + `update-ca-certificates`
- Automatic cleanup of temporary files
- Detailed error messages and troubleshooting guidance

**Used by:**
- `/openshift:install-vsphere` - For secure govc communication with vCenter

**Requirements:**
- `curl` - For downloading certificates
- `unzip` - For extracting certificate bundle
- `sudo` - Required for installing certificates to system trust store

---

### download-openshift-installer.sh

Downloads the `openshift-install` binary for the current platform.

**Usage:**
```bash
bash plugins/openshift/scripts/download-openshift-installer.sh <version> [output-directory]
```

**Examples:**
```bash
# Download latest 4.20.x to current directory
bash plugins/openshift/scripts/download-openshift-installer.sh 4.20

# Download to specific directory
bash plugins/openshift/scripts/download-openshift-installer.sh 4.20 /usr/local/bin

# Use explicit channel
bash plugins/openshift/scripts/download-openshift-installer.sh stable-4.19
```

**Features:**
- Auto-detects OS (Linux/macOS) and architecture (x86_64/arm64)
- Supports version formats: `4.20`, `latest-4.20`, `stable-4.20`, `fast-4.20`
- Downloads from official OpenShift mirror
- Validates download and extraction
- Makes binary executable automatically
- Shows version after successful download

**Used by:**
- `/openshift:install-vsphere` - For cluster installation
- `/openshift:create-cluster` - For cluster provisioning

**Requirements:**
- `curl` - For downloading installer
- `tar` - For extracting archive
