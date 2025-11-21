#!/usr/bin/env bash
# install-govc.sh - Download and install govc for macOS or Linux
# Works on both macOS and Linux with automatic OS/architecture detection

set -euo pipefail

# Detect OS
OS=$(uname -s)
echo "Detected OS: $OS"

# Detect architecture
ARCH=$(uname -m)
echo "Detected Architecture: $ARCH"

# Validate OS is supported
if [[ "$OS" != "Linux" && "$OS" != "Darwin" ]]; then
  echo "Error: Unsupported OS: $OS (only Linux and Darwin/macOS are supported)"
  exit 1
fi

# Construct asset pattern for GitHub release
# GitHub uses capitalized OS names: Linux, Darwin
ASSET_PATTERN="govc_${OS}_${ARCH}.tar.gz"
echo "Looking for asset: $ASSET_PATTERN"

# Fetch latest release info from GitHub API
echo "Fetching latest govc release from GitHub..."
RELEASE_JSON=$(curl -s https://api.github.com/repos/vmware/govmomi/releases/latest)

# Extract version
VERSION=$(echo "$RELEASE_JSON" | jq -r '.tag_name')
echo "Latest version: $VERSION"

# Find matching asset download URL
DOWNLOAD_URL=$(echo "$RELEASE_JSON" | jq -r ".assets[] | select(.name == \"$ASSET_PATTERN\") | .browser_download_url")

if [[ -z "$DOWNLOAD_URL" ]]; then
  echo "Error: Could not find asset matching pattern: $ASSET_PATTERN"
  echo "Available assets:"
  echo "$RELEASE_JSON" | jq -r '.assets[].name' | grep "^govc_"
  exit 1
fi

echo "Download URL: $DOWNLOAD_URL"

# Download and extract to /tmp
echo "Downloading govc..."
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

curl -L "$DOWNLOAD_URL" -o "$TEMP_DIR/govc.tar.gz"
echo "Extracting..."
tar xzf "$TEMP_DIR/govc.tar.gz" -C "$TEMP_DIR"
chmod +x "$TEMP_DIR/govc"

# Determine installation location
# Prefer user-local directories, fall back to system-wide
if [[ -d "$HOME/.local/bin" ]]; then
  INSTALL_DIR="$HOME/.local/bin"
elif [[ -d "$HOME/bin" ]]; then
  INSTALL_DIR="$HOME/bin"
else
  INSTALL_DIR="/usr/local/bin"
  echo "Note: Installing to $INSTALL_DIR (may require sudo)"
fi

# Install govc
echo "Installing govc to $INSTALL_DIR..."
if [[ "$INSTALL_DIR" == "/usr/local/bin" ]]; then
  sudo mv "$TEMP_DIR/govc" "$INSTALL_DIR/govc"
else
  mv "$TEMP_DIR/govc" "$INSTALL_DIR/govc"
fi

echo "✓ govc installed successfully to $INSTALL_DIR/govc"

# Verify installation
if command -v govc &>/dev/null; then
  echo "✓ govc is in PATH"
  govc version
else
  echo "⚠ govc is not in PATH. You may need to add $INSTALL_DIR to your PATH"
  echo "  Add this to your ~/.bashrc or ~/.zshrc:"
  echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi
