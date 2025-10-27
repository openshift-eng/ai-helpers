#!/bin/bash
# check-and-configure-template.sh - Check vSphere for existing RHCOS templates and configure for installation
#
# This script implements the workflow for:
# 1. Fetching RHCOS metadata from the OpenShift installer repo (branch-based)
# 2. Extracting the RHCOS version from the OVA filename
# 3. Checking vSphere for existing templates with that version
# 4. Returning the template path if found, or indicating upload is needed
#
# Usage:
#   bash check-and-configure-template.sh <openshift-version> <datacenter>
#
# Example:
#   bash check-and-configure-template.sh 4.20 cidatacenter
#
# Output:
#   - RHCOS version
#   - Template path (if exists) or empty (if needs upload)
#   - Exit code 0 if template found, 1 if not found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
  echo "Usage: $0 <openshift-version> <datacenter>"
  echo "Example: $0 4.20 cidatacenter"
  exit 1
fi

OPENSHIFT_VERSION="$1"
DATACENTER="$2"

# Ensure vCenter credentials are sourced
if [ -z "${GOVC_URL:-}" ]; then
  echo "Error: vCenter credentials not set. Please source .work/.vcenter-env first."
  exit 1
fi

echo "=== RHCOS Template Discovery ==="
echo ""

# Step 1: Fetch RHCOS metadata from installer repo
# The metadata is stored in the installer repo on a per-version branch:
# - OpenShift 4.20 → branch release-4.20
# - OpenShift 4.19 → branch release-4.19
# This ensures we get the correct RHCOS version for the OpenShift release
echo "Fetching RHCOS metadata for OpenShift $OPENSHIFT_VERSION..."
METADATA=$(python3 "$SCRIPT_DIR/fetch-rhcos-metadata.py" "$OPENSHIFT_VERSION" 2>/dev/null)

if [ $? -ne 0 ]; then
  echo "Error: Failed to fetch RHCOS metadata for version $OPENSHIFT_VERSION"
  exit 1
fi

# Step 2: Extract RHCOS version from OVA filename
# The OVA URL contains the RHCOS version in the filename
# Example: rhcos-9.6.20251015-1-vmware.x86_64.ova → version is 9.6.20251015-1
OVA_URL=$(echo "$METADATA" | python3 -c "import sys, json; print(json.load(sys.stdin)['url'])")
OVA_FILENAME=$(basename "$OVA_URL")
RHCOS_VERSION=$(echo "$OVA_FILENAME" | sed 's/rhcos-//; s/-vmware.x86_64.ova//')

echo -e "${GREEN}✓${NC} RHCOS Version: $RHCOS_VERSION"
echo "  OVA Filename: $OVA_FILENAME"
echo ""

# Step 3: Check vSphere for existing templates with this version
# Search for any VM or template that contains the RHCOS version in its name
# This avoids re-uploading templates that already exist from previous installations
echo "Checking vSphere for existing templates in datacenter: $DATACENTER"
echo "Searching for templates with version: $RHCOS_VERSION"

EXISTING_TEMPLATE=$(govc find "/$DATACENTER" -type m -name "*${RHCOS_VERSION}*" 2>/dev/null | head -1 || true)

# Step 4: Return results
echo ""
if [ -n "$EXISTING_TEMPLATE" ]; then
  echo -e "${GREEN}✓ Found existing template:${NC} $EXISTING_TEMPLATE"
  echo ""
  echo "This template can be used in install-config.yaml:"
  echo "  platform:"
  echo "    vsphere:"
  echo "      failureDomains:"
  echo "      - topology:"
  echo "          template: $EXISTING_TEMPLATE"
  echo ""
  echo "$EXISTING_TEMPLATE"
  exit 0
else
  echo -e "${YELLOW}⚠ No existing template found${NC}"
  echo ""
  echo "You can either:"
  echo "1. Upload the OVA manually using:"
  echo "   bash $SCRIPT_DIR/manage-rhcos-template.sh install $OPENSHIFT_VERSION \\"
  echo "     --datacenter $DATACENTER \\"
  echo "     --datastore /path/to/datastore \\"
  echo "     --cluster /path/to/cluster"
  echo ""
  echo "2. Skip template and let installer upload OVA (slower)"
  echo ""
  exit 1
fi
