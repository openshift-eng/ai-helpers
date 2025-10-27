#!/usr/bin/env bash
# download-openshift-installer.sh - Download openshift-install binary
# Works on both macOS and Linux with automatic OS/architecture detection

set -euo pipefail

# Function to show usage
usage() {
  echo "Usage: $0 <version> [output-directory]"
  echo ""
  echo "Downloads openshift-install binary for the current platform"
  echo ""
  echo "Arguments:"
  echo "  version            OpenShift version (e.g., '4.20', '4.19', 'stable-4.20', 'latest-4.20')"
  echo "  output-directory   Optional: Directory to extract binary to (default: current directory)"
  echo ""
  echo "Examples:"
  echo "  $0 4.20                    # Downloads latest 4.20.x release"
  echo "  $0 stable-4.19             # Downloads latest stable 4.19.x release"
  echo "  $0 4.20 /usr/local/bin     # Downloads and extracts to /usr/local/bin"
  exit 1
}

# Check for required argument
if [ $# -lt 1 ]; then
  usage
fi

VERSION="$1"
OUTPUT_DIR="${2:-.}"  # Default to current directory

# Normalize version format
# If version is just "4.20", prepend "latest-"
if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+$ ]]; then
  VERSION="latest-${VERSION}"
fi

# If version doesn't start with "latest-" or "stable-", prepend "latest-"
if [[ ! "$VERSION" =~ ^(latest-|stable-|fast-|candidate-) ]]; then
  VERSION="latest-${VERSION}"
fi

echo "OpenShift version: $VERSION"

# Detect OS
OS=$(uname -s)
echo "Detected OS: $OS"

# Detect architecture
ARCH=$(uname -m)
echo "Detected Architecture: $ARCH"

# Construct binary filename based on OS and architecture
if [ "$OS" = "Darwin" ]; then
  # macOS
  if [ "$ARCH" = "arm64" ]; then
    BINARY="openshift-install-mac-arm64.tar.gz"
  else
    BINARY="openshift-install-mac.tar.gz"
  fi
elif [ "$OS" = "Linux" ]; then
  # Linux
  if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    BINARY="openshift-install-linux-arm64.tar.gz"
  else
    BINARY="openshift-install-linux.tar.gz"
  fi
else
  echo "Error: Unsupported OS: $OS (only Darwin/macOS and Linux are supported)"
  exit 1
fi

echo "Binary to download: $BINARY"

# Construct download URL
DOWNLOAD_URL="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/${VERSION}/${BINARY}"
echo "Download URL: $DOWNLOAD_URL"

# Create output directory if it doesn't exist
if [ ! -d "$OUTPUT_DIR" ]; then
  echo "Creating output directory: $OUTPUT_DIR"
  mkdir -p "$OUTPUT_DIR"
fi

# Download and extract
echo "Downloading openshift-install..."
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

if ! curl -f -L "$DOWNLOAD_URL" -o "$TEMP_DIR/installer.tar.gz"; then
  echo "Error: Failed to download openshift-install from $DOWNLOAD_URL"
  echo ""
  echo "Possible issues:"
  echo "  - Version '$VERSION' may not exist"
  echo "  - Network connectivity issues"
  echo "  - Binary '$BINARY' may not be available for this version"
  echo ""
  echo "Try checking available versions at:"
  echo "  https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
  exit 1
fi

echo "Extracting to $OUTPUT_DIR..."
tar xzf "$TEMP_DIR/installer.tar.gz" -C "$OUTPUT_DIR"

# Verify extraction
if [ ! -f "$OUTPUT_DIR/openshift-install" ]; then
  echo "Error: openshift-install binary not found after extraction"
  exit 1
fi

# Make executable
chmod +x "$OUTPUT_DIR/openshift-install"

echo "✓ openshift-install downloaded successfully"
echo "Location: $OUTPUT_DIR/openshift-install"

# Show version
if "$OUTPUT_DIR/openshift-install" version 2>/dev/null | head -1; then
  true
else
  echo "Note: Run '$OUTPUT_DIR/openshift-install version' to verify"
fi
