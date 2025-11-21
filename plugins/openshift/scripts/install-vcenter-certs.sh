#!/usr/bin/env bash
# install-vcenter-certs.sh - Download and install vCenter certificates
# Works on both macOS and Linux

set -euo pipefail

# Check for required argument
if [ $# -lt 1 ]; then
  echo "Usage: $0 <vcenter-server>"
  echo "Example: $0 vcenter.example.com"
  exit 1
fi

VCENTER_SERVER="$1"
CERT_URL="https://${VCENTER_SERVER}/certs/download.zip"

echo "Downloading vCenter certificates from: $CERT_URL"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Download certificates
if ! curl -sk "$CERT_URL" -o "$TEMP_DIR/vcenter-certs.zip"; then
  echo "Error: Failed to download certificates from $CERT_URL"
  echo "Please verify the vCenter server address is correct and accessible"
  exit 1
fi

# Verify we got a valid zip file
if ! file "$TEMP_DIR/vcenter-certs.zip" | grep -q "Zip archive"; then
  echo "Error: Downloaded file is not a valid ZIP archive"
  echo "The vCenter server may be unreachable or the certificates endpoint is unavailable"
  exit 1
fi

# Extract certificates
echo "Extracting certificates..."
unzip -q -o "$TEMP_DIR/vcenter-certs.zip" -d "$TEMP_DIR/vcenter-certs"

# Check if extraction was successful
if [ ! -d "$TEMP_DIR/vcenter-certs/certs" ]; then
  echo "Error: Certificate extraction failed - certs directory not found"
  exit 1
fi

# Detect OS-specific certificate directory
OS_TYPE=$(uname -s)
if [ "$OS_TYPE" = "Darwin" ]; then
  CERT_SOURCE_DIR="$TEMP_DIR/vcenter-certs/certs/mac"
  CERT_PATTERN="*.0"
elif [ "$OS_TYPE" = "Linux" ]; then
  CERT_SOURCE_DIR="$TEMP_DIR/vcenter-certs/certs/lin"
  CERT_PATTERN="*.0"
else
  CERT_SOURCE_DIR="$TEMP_DIR/vcenter-certs/certs/win"
  CERT_PATTERN="*.0.crt"
fi

# Count certificates (only .0 files, not .r0 CRL files)
CERT_COUNT=$(find "$CERT_SOURCE_DIR" -name "$CERT_PATTERN" -not -name "*.r0" | wc -l)
if [ "$CERT_COUNT" -eq 0 ]; then
  echo "Error: No certificate files found in $CERT_SOURCE_DIR"
  exit 1
fi

echo "Found $CERT_COUNT certificate(s) to install"

# Install certificates to system trust store
OS=$(uname -s)

if [ "$OS" = "Darwin" ]; then
  # macOS
  echo "Installing certificates to macOS System Keychain (requires sudo)..."
  for cert in "$CERT_SOURCE_DIR"/*.0; do
    [ -e "$cert" ] || continue  # Skip if no matches
    [ "$(basename "$cert")" != "*.r0" ] || continue  # Skip CRL files
    CERT_NAME=$(basename "$cert")
    echo "  Installing: $CERT_NAME"
    if ! sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$cert"; then
      echo "  Warning: Failed to install $CERT_NAME"
    fi
  done
  echo "✓ Certificates installed to macOS System Keychain"

elif [ "$OS" = "Linux" ]; then
  # Linux - detect RHEL/Fedora vs Debian/Ubuntu
  echo "Installing certificates to Linux CA trust store (requires sudo)..."

  if [ -d "/etc/pki/ca-trust/source/anchors" ]; then
    # RHEL/Fedora/CentOS
    echo "Detected RHEL/Fedora system"
    for cert in "$CERT_SOURCE_DIR"/*.0; do
      [ -e "$cert" ] || continue  # Skip if no matches
      [ "$(basename "$cert")" != "*.r0" ] || continue  # Skip CRL files
      CERT_NAME=$(basename "$cert" .0)
      sudo cp "$cert" "/etc/pki/ca-trust/source/anchors/${CERT_NAME}.crt"
      echo "  Installed: ${CERT_NAME}.crt"
    done
    sudo update-ca-trust extract
    echo "✓ Certificates installed to RHEL/Fedora CA trust store"
  elif [ -d "/usr/local/share/ca-certificates" ]; then
    # Debian/Ubuntu
    echo "Detected Debian/Ubuntu system"
    for cert in "$CERT_SOURCE_DIR"/*.0; do
      [ -e "$cert" ] || continue  # Skip if no matches
      [ "$(basename "$cert")" != "*.r0" ] || continue  # Skip CRL files
      CERT_NAME=$(basename "$cert" .0)
      sudo cp "$cert" "/usr/local/share/ca-certificates/${CERT_NAME}.crt"
      echo "  Installed: ${CERT_NAME}.crt"
    done
    sudo update-ca-certificates
    echo "✓ Certificates installed to Debian/Ubuntu CA trust store"
  else
    echo "Error: Could not find CA trust store directory"
    echo "Tried: /etc/pki/ca-trust/source/anchors (RHEL/Fedora)"
    echo "       /usr/local/share/ca-certificates (Debian/Ubuntu)"
    exit 1
  fi

else
  echo "Error: Unsupported OS: $OS (only Darwin/macOS and Linux are supported)"
  exit 1
fi

echo "✓ vCenter certificates installed successfully"
