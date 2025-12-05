#!/usr/bin/env bash
# setup-vcenter-env.sh - Securely prompt for vCenter credentials and create environment file
# Usage: source $(bash setup-vcenter-env.sh)

set -euo pipefail

# Output file for environment variables
ENV_FILE=".work/.vcenter-env"

echo "=== vCenter Connection Setup ==="
echo ""

# Prompt for vCenter server
read -p "vCenter server URL (e.g., vcenter.example.com): " VCENTER_SERVER
if [ -z "$VCENTER_SERVER" ]; then
  echo "Error: vCenter server URL cannot be empty"
  exit 1
fi

# Prompt for username
read -p "vCenter username (e.g., user@vsphere.local): " VCENTER_USERNAME
if [ -z "$VCENTER_USERNAME" ]; then
  echo "Error: Username cannot be empty"
  exit 1
fi

# Prompt for password (securely - no echo)
read -s -p "vCenter password: " VCENTER_PASSWORD
echo ""
if [ -z "$VCENTER_PASSWORD" ]; then
  echo "Error: Password cannot be empty"
  exit 1
fi

# Prompt for insecure mode (skip certificate validation)
read -p "Skip certificate validation? (true/false, default: true): " VCENTER_INSECURE
VCENTER_INSECURE=${VCENTER_INSECURE:-true}

# Create .work directory if it doesn't exist
mkdir -p .work

# Create environment file
cat > "$ENV_FILE" <<EOF
# vCenter connection environment variables
# Generated: $(date)
# Source this file: source $ENV_FILE

export GOVC_URL="https://${VCENTER_SERVER}/sdk"
export GOVC_USERNAME="${VCENTER_USERNAME}"
export GOVC_PASSWORD="${VCENTER_PASSWORD}"
export GOVC_INSECURE=${VCENTER_INSECURE}
EOF

# Secure the file (only owner can read/write)
chmod 600 "$ENV_FILE"

echo ""
echo "✓ Environment file created: $ENV_FILE"
echo ""
echo "To use these credentials, run:"
echo "  source $ENV_FILE"
echo ""
echo "IMPORTANT: This file contains sensitive credentials."
echo "  - It is protected with 600 permissions (owner read/write only)"
echo "  - It should NEVER be committed to git"
echo "  - The .work directory is already in .gitignore"
echo ""

# Output the path so it can be sourced
echo "$ENV_FILE"
