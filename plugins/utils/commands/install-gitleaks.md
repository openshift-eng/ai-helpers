---
description: Install gitleaks for detecting secrets in code
---

## Name
utils:install-gitleaks

## Synopsis
```
/utils:install-gitleaks
```

## Description
The `utils:install-gitleaks` command installs [gitleaks](https://github.com/gitleaks/gitleaks), a SAST tool for detecting and preventing hardcoded secrets like passwords, API keys, and tokens in git repositories and files.

Gitleaks is essential for verifying that sensitive information has been properly redacted before committing code or sharing files.

## Implementation

### Step 1: Check if Gitleaks is Already Installed

```bash
which gitleaks
```

**Expected outcomes:**
- **Path returned** (e.g., `/usr/local/bin/gitleaks`): Gitleaks is already installed
  - Check version: `gitleaks version`
  - If version is recent (8.0+), skip to Step 4
  - If version is old, proceed to Step 2
- **Command not found**: Proceed to Step 2

### Step 2: Detect Operating System and Architecture

Determine the user's platform to download the correct binary:

```bash
uname -s
uname -m
```

**Common platform mappings:**
- `Darwin` + `x86_64` → macOS Intel (`darwin_x64`)
- `Darwin` + `arm64` → macOS Apple Silicon (`darwin_arm64`)
- `Linux` + `x86_64` → Linux AMD64 (`linux_x64`)
- `Linux` + `aarch64` → Linux ARM64 (`linux_arm64`)

### Step 3: Install Gitleaks

Choose the appropriate installation method based on the platform:

#### Option A: macOS (using Homebrew - Recommended)

```bash
# Check if Homebrew is installed
which brew

# If Homebrew is available:
brew install gitleaks
```

#### Option B: macOS (manual installation)

```bash
# Determine architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    PLATFORM="darwin_arm64"
else
    PLATFORM="darwin_x64"
fi

# Download latest release
VERSION="8.20.1"  # Check https://github.com/gitleaks/gitleaks/releases for latest
curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_${PLATFORM}.tar.gz" -o gitleaks.tar.gz

# Extract and install
tar -xzf gitleaks.tar.gz gitleaks
sudo mv gitleaks /usr/local/bin/gitleaks
sudo chmod +x /usr/local/bin/gitleaks

# Clean up
rm gitleaks.tar.gz
```

#### Option C: Linux (manual installation)

```bash
# Determine architecture
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    PLATFORM="linux_arm64"
else
    PLATFORM="linux_x64"
fi

# Download latest release
VERSION="8.20.1"  # Check https://github.com/gitleaks/gitleaks/releases for latest
curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_${PLATFORM}.tar.gz" -o gitleaks.tar.gz

# Extract and install
tar -xzf gitleaks.tar.gz gitleaks
sudo mv gitleaks /usr/local/bin/gitleaks
sudo chmod +x /usr/local/bin/gitleaks

# Clean up
rm gitleaks.tar.gz
```

#### Option D: Using Go (any platform)

If the user has Go installed:

```bash
go install github.com/gitleaks/gitleaks/v8@latest
```

**Note:** This installs to `$GOPATH/bin/gitleaks` (usually `~/go/bin/gitleaks`)

### Step 4: Verify Installation

```bash
gitleaks version
```

**Expected output:**
```
v8.20.1
```

Test basic functionality:
```bash
echo 'password = "SuperSecret123!"' > /tmp/test_leak.txt
gitleaks detect --no-git --source /tmp/test_leak.txt --verbose
rm /tmp/test_leak.txt
```

**Expected output:** Should detect the password as a leak

### Step 5: Inform User of Installation Success

Provide the user with:
1. Confirmation that gitleaks is installed
2. The installed version
3. Installation location
4. Basic usage example

## Return Value

**Success:**
- Gitleaks is installed and functional
- Version information displayed
- Basic usage instructions provided

**Failure:**
- Error message explaining what went wrong
- Troubleshooting steps or alternative installation methods
- Link to official documentation: https://github.com/gitleaks/gitleaks#installation

## Error Handling

### Homebrew Not Installed (macOS)

**Problem:** `brew` command not found on macOS

**Solution:**
1. Offer to install Homebrew:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Or proceed with manual installation (Option B)

### Permission Denied

**Problem:** Cannot write to `/usr/local/bin/`

**Solution:**
1. Ask user to provide sudo password when prompted
2. Or install to user directory:
   ```bash
   mkdir -p ~/bin
   mv gitleaks ~/bin/gitleaks
   chmod +x ~/bin/gitleaks
   # Add to PATH
   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc  # or ~/.zshrc
   ```

### Download Failed

**Problem:** Cannot download release from GitHub

**Solution:**
1. Check internet connection
2. Verify GitHub is accessible
3. Try alternative installation method (Homebrew, Go, etc.)

### Unsupported Platform

**Problem:** Platform not supported (Windows, unusual architecture)

**Solution:**
1. Check https://github.com/gitleaks/gitleaks/releases for available platforms
2. For Windows, recommend installing via WSL and following the Linux installation steps

## Examples

### Example 1: Install on macOS with Homebrew

```
User: /utils:install-gitleaks