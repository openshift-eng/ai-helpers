---
description: Validate BMC Redfish compliance against OpenStack Ironic profile
argument-hint: "<bmc-address> <credentials-file>"
---

## Name
openshift:bmh-ironic-check-redfish-profile

## Synopsis
```bash
/openshift:bmh-ironic-check-redfish-profile <bmc-address> <credentials-file>
```

## Description

The `openshift:bmh-ironic-check-redfish-profile` command validates a Baseboard Management Controller (BMC) against the OpenStack Ironic Redfish Interoperability Profile. This ensures the BMC hardware has the necessary Redfish API capabilities required for successful baremetal provisioning with Metal3/Ironic in OpenShift environments.

The command uses the DMTF Redfish-Interop-Validator tool to perform comprehensive validation against the official OpenStack Ironic profile, which includes checking for:
- Virtual media support (CD/DVD mounting)
- Boot source override capabilities
- Power state management
- System inventory reporting
- Required Redfish schema versions

This command is useful for:
- Pre-deployment hardware validation for OpenShift baremetal clusters
- Troubleshooting provisioning failures related to BMC capabilities
- Verifying BMC firmware meets Ironic requirements
- Comparing different BMC models for compatibility
- Validating BMC configuration before enrolling BareMetalHosts

**Security Note**: Credentials are read from a file to avoid exposing sensitive information in command-line arguments, shell history, or process listings.

## Prerequisites

Before using this command, ensure you have:

1. **Python 3**: Required for running the Redfish-Interop-Validator
   - Verify with: `python3 --version`
   - Minimum version: Python 3.6+
   - Install on RHEL/Fedora: `sudo dnf install python3`

2. **pip (Python package manager)**: Required for installing the validator
   - Verify with: `pip3 --version` or `python3 -m pip --version`
   - Install on RHEL/Fedora: `sudo dnf install python3-pip`
   - Install on Ubuntu: `sudo apt install python3-pip`

3. **curl or wget**: Required for downloading the Ironic profile
   - Verify with: `which curl` or `which wget`
   - Most systems have these pre-installed

4. **Network connectivity**: Direct access to both the BMC and GitHub
   - Verify BMC access: `ping <bmc-address>`
   - Verify GitHub access: `curl -I https://github.com`
   - Ensure no firewall rules block HTTPS (port 443)

5. **BMC credentials file**: A file containing BMC username and password
   - Credentials should have at least read-only access to Redfish API
   - Administrative access is NOT required for this validation
   - File format (plain text, one credential per line):
     ```ini
     username=user
     password=password
     ```
   - Set restrictive permissions: `chmod 600 <credentials-file>`
   - Do NOT commit credentials files to version control

6. **BMC with Redfish support**: The BMC must support Redfish protocol
   - Minimum Redfish version: 1.6.0 (for full Ironic compatibility)
   - Most modern BMCs (iDRAC, iLO, Supermicro, etc.) support Redfish

## Implementation

The command performs the following steps to validate BMC Redfish compliance:

### 1. Validate Input Arguments and Read Credentials

```bash
BMC_ADDRESS="$1"
CREDENTIALS_FILE="$2"

# Validate all required arguments are provided
if [ -z "$BMC_ADDRESS" ] || [ -z "$CREDENTIALS_FILE" ]; then
    echo "Error: Missing required arguments"
    echo "Usage: /openshift:bmh-ironic-check-redfish-profile <bmc-address> <credentials-file>"
    exit 1
fi

# Verify credentials file exists and is readable
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "Error: Credentials file not found: $CREDENTIALS_FILE"
    exit 1
fi

if [ ! -r "$CREDENTIALS_FILE" ]; then
    echo "Error: Credentials file not readable: $CREDENTIALS_FILE"
    exit 1
fi

# Read credentials from file
# Expected format (one per line):
#   username=<value>
#   password=<value>
BMC_USERNAME=$(grep -E '^username=' "$CREDENTIALS_FILE" | cut -d'=' -f2-)
BMC_PASSWORD=$(grep -E '^password=' "$CREDENTIALS_FILE" | cut -d'=' -f2-)

# Validate credentials were found
if [ -z "$BMC_USERNAME" ]; then
    echo "Error: Username not found in credentials file"
    echo "Expected format: username=<value>"
    exit 1
fi

if [ -z "$BMC_PASSWORD" ]; then
    echo "Error: Password not found in credentials file"
    echo "Expected format: password=<value>"
    exit 1
fi

# Ensure BMC address has protocol prefix
if [[ ! "$BMC_ADDRESS" =~ ^https?:// ]]; then
    BMC_ADDRESS="https://${BMC_ADDRESS}"
fi

# Create working directory for validation artifacts
WORK_DIR=".work/bmh-ironic-check-redfish-profile"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"
```

### 2. Check and Install Redfish-Interop-Validator

Verify the validator is installed, or install it if needed:

```bash
echo "Checking for Redfish-Interop-Validator..."

# Check if the validator is already installed
if command -v rf_interop_validator &> /dev/null; then
    echo "✓ Redfish-Interop-Validator is already installed"
    VALIDATOR_VERSION=$(rf_interop_validator --version 2>&1 | grep -oP 'version \K[0-9.]+' || echo "unknown")
    echo "  Version: ${VALIDATOR_VERSION}"
else
    echo "Installing Redfish-Interop-Validator from PyPI..."

    # Try to install using pip3
    if pip3 install --user redfish_interop_validator; then
        echo "✓ Successfully installed Redfish-Interop-Validator"

        # Add user site-packages bin to PATH if not already there
        USER_BIN="$HOME/.local/bin"
        if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
            export PATH="$USER_BIN:$PATH"
            echo "  Added $USER_BIN to PATH"
        fi

        # Verify installation
        if ! command -v rf_interop_validator &> /dev/null; then
            echo "Warning: rf_interop_validator not found in PATH after installation"
            echo "Attempting to use python3 -m redfish_interop_validator instead"
            RF_VALIDATOR_CMD="python3 -m redfish_interop_validator"
        else
            RF_VALIDATOR_CMD="rf_interop_validator"
        fi
    else
        echo "Error: Failed to install Redfish-Interop-Validator"
        echo "Please install manually: pip3 install --user redfish_interop_validator"
        exit 1
    fi
fi

# Set the validator command if not already set
RF_VALIDATOR_CMD="${RF_VALIDATOR_CMD:-rf_interop_validator}"
```

### 3. Download OpenStack Ironic Redfish Profile

Retrieve the official Ironic interoperability profile from GitHub:

```bash
echo ""
echo "Downloading OpenStack Ironic Redfish profile..."

PROFILE_URL="https://raw.githubusercontent.com/openstack/ironic/master/redfish-interop-profiles/OpenStackIronicProfile.v1_1_0.json"
PROFILE_FILE="OpenStackIronicProfile.v1_1_0.json"

# Download the profile using curl or wget
if command -v curl &> /dev/null; then
    if curl -sL -o "$PROFILE_FILE" "$PROFILE_URL"; then
        echo "✓ Successfully downloaded Ironic profile"
    else
        echo "Error: Failed to download Ironic profile from GitHub"
        echo "URL: $PROFILE_URL"
        exit 1
    fi
elif command -v wget &> /dev/null; then
    if wget -q -O "$PROFILE_FILE" "$PROFILE_URL"; then
        echo "✓ Successfully downloaded Ironic profile"
    else
        echo "Error: Failed to download Ironic profile from GitHub"
        echo "URL: $PROFILE_URL"
        exit 1
    fi
else
    echo "Error: Neither curl nor wget is available"
    echo "Please install curl or wget to download the profile"
    exit 1
fi

# Verify the downloaded file is valid JSON
if ! python3 -c "import json; json.load(open('$PROFILE_FILE'))" 2>/dev/null; then
    echo "Error: Downloaded profile is not valid JSON"
    echo "File may be corrupted or URL may have changed"
    exit 1
fi

echo "  Profile: OpenStackIronicProfile v1.1.0"
echo "  Location: $(pwd)/$PROFILE_FILE"
```

### 4. Run Redfish Interoperability Validation

Execute the validator against the BMC:

```bash
echo ""
echo "Running Redfish interoperability validation..."
echo "BMC: ${BMC_ADDRESS}"
echo ""

# Prepare validator arguments
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="validation_report_${TIMESTAMP}"
mkdir -p "$REPORT_DIR"

# Run the validator
# Key options:
#   -i, --ip: BMC address (must include https://)
#   -u, --username: BMC username
#   -p, --password: BMC password
#   --logdir: Directory for output reports and logs
#   profile: Path to the profile JSON (positional argument)
#
# Note: SSL certificate verification is not enforced by default for basic auth

echo "This may take several minutes as the validator checks all Redfish endpoints..."
echo ""

$RF_VALIDATOR_CMD \
    -i "$BMC_ADDRESS" \
    -u "$BMC_USERNAME" \
    -p "$BMC_PASSWORD" \
    --logdir "$REPORT_DIR" \
    "$PROFILE_FILE" \
    2>&1 | tee "${REPORT_DIR}/validation.log"

VALIDATOR_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "Validation complete"
```

### 5. Parse and Present Validation Results

Analyze the validation output and present key findings:

```bash
echo ""
echo "=========================================="
echo "Validation Results Summary"
echo "=========================================="
echo ""

# The validator creates several output files:
# - results.json: Detailed JSON results
# - index.html: HTML report (if applicable)
# - validation.log: Execution log

RESULTS_FILE="${REPORT_DIR}/results.json"

if [ -f "$RESULTS_FILE" ]; then
    # Parse the JSON results
    echo "BMC Address: ${BMC_ADDRESS}"
    echo "Profile: OpenStack Ironic v1.1.0"
    echo ""

    # Extract key metrics using python
    python3 << PYPARSESCRIPT
import json
import sys

try:
    with open('${RESULTS_FILE}') as f:
        results = json.load(f)

    # Count passes, warnings, and failures
    total_tests = results.get('totals', {}).get('total', 0)
    passes = results.get('totals', {}).get('pass', 0)
    warnings = results.get('totals', {}).get('warn', 0)
    failures = results.get('totals', {}).get('fail', 0)

    print(f"Total Tests: {total_tests}")
    print(f"  ✓ Passed: {passes}")
    print(f"  ⚠ Warnings: {warnings}")
    print(f"  ✗ Failed: {failures}")
    print()

    # Calculate compliance percentage
    if total_tests > 0:
        compliance = (passes / total_tests) * 100
        print(f"Compliance Score: {compliance:.1f}%")
        print()

    # Show critical failures if any
    if failures > 0:
        print("Critical Issues Found:")
        print()

        # Extract failure details
        for test_name, test_result in results.get('results', {}).items():
            if isinstance(test_result, dict) and test_result.get('status') == 'FAIL':
                print(f"  ✗ {test_name}")
                if 'message' in test_result:
                    print(f"    {test_result['message']}")
        print()

    # Check for virtual media support specifically
    has_virtual_media = False
    for test_name in results.get('results', {}).keys():
        if 'virtualmedia' in test_name.lower():
            has_virtual_media = True
            break

    if has_virtual_media:
        print("✓ Virtual Media: Detected in validation")
    else:
        print("✗ Virtual Media: Not detected or not tested")
    print()

except FileNotFoundError:
    print("Error: Results file not found")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: Invalid JSON in results file")
    sys.exit(1)
except Exception as e:
    print(f"Error parsing results: {e}")
    sys.exit(1)

PYPARSESCRIPT

else
    echo "Warning: Detailed results file not found"
    echo "Validation may have failed to complete successfully"
    echo ""
fi

# Check validator exit code and normalize to documented exit codes
if [ $VALIDATOR_EXIT_CODE -eq 0 ]; then
    echo "=========================================="
    echo "Result: BMC PASSED validation"
    echo "=========================================="
    echo ""
    echo "✓ This BMC meets the OpenStack Ironic Redfish requirements"
    echo "✓ Compatible with Metal3/Ironic provisioning"
    echo "✓ Suitable for OpenShift baremetal deployments"
    echo ""
    echo "Recommended BMC protocol (use in BareMetalHost address):"
    echo "  Dell iDRAC: idrac-virtualmedia:// (if virtual media supported)"
    echo "  Redfish:    redfish-virtualmedia:// or redfish://"

    FINAL_EXIT_CODE=0
else
    echo "=========================================="
    echo "Result: BMC FAILED validation"
    echo "=========================================="
    echo ""
    echo "⚠ This BMC does not fully meet the Ironic requirements"
    echo ""
    echo "Common issues:"
    echo "  - Missing virtual media support"
    echo "  - Incomplete boot source override implementation"
    echo "  - Outdated Redfish schema versions"
    echo "  - Missing required Redfish endpoints"
    echo ""
    echo "Recommendations:"
    echo "  1. Check for BMC firmware updates"
    echo "  2. Review detailed report for specific failures"
    echo "  3. Consider using non-virtualmedia protocol (redfish://, ipmi://)"
    echo "  4. Contact hardware vendor for support"

    # Normalize to exit code 2 for validation failures
    FINAL_EXIT_CODE=2
fi

echo ""
echo "Detailed Reports Available:"
echo "  - Log: ${REPORT_DIR}/validation.log"
echo "  - Results: ${REPORT_DIR}/results.json"
if [ -f "${REPORT_DIR}/index.html" ]; then
    echo "  - HTML Report: ${REPORT_DIR}/index.html"
fi
echo ""
echo "Working Directory: $(pwd)"

# Exit with normalized exit code
exit $FINAL_EXIT_CODE
```

### 6. Error Handling

Handle common error scenarios:

```bash
# Network connectivity issues
if ! curl -s --connect-timeout 5 "$BMC_ADDRESS/redfish/v1/" &>/dev/null; then
    echo "Error: Cannot connect to BMC at $BMC_ADDRESS"
    echo "Please verify:"
    echo "  - BMC address is correct"
    echo "  - Network connectivity to BMC"
    echo "  - BMC is powered on and responsive"
    exit 1
fi

# Authentication failures
if curl -s -u "$BMC_USERNAME:$BMC_PASSWORD" "$BMC_ADDRESS/redfish/v1/" 2>&1 | grep -qi "unauthorized\|401"; then
    echo "Error: Authentication failed"
    echo "Please verify:"
    echo "  - Username is correct"
    echo "  - Password is correct"
    echo "  - Account is not locked"
    exit 1
fi

# Missing Python dependencies
if ! python3 -c "import redfish" &>/dev/null; then
    echo "Warning: Python redfish module not found"
    echo "Installing required Python dependencies..."
    pip3 install --user redfish
fi

# GitHub connectivity for profile download
if ! curl -s --connect-timeout 5 -I https://github.com &>/dev/null; then
    echo "Error: Cannot reach GitHub to download profile"
    echo "Please verify:"
    echo "  - Internet connectivity"
    echo "  - Proxy settings (if applicable)"
    echo "  - Firewall rules"
    exit 1
fi

# Insufficient disk space for reports
AVAILABLE_SPACE=$(df -k . | awk 'NR==2 {print $4}')
if [ "$AVAILABLE_SPACE" -lt 10240 ]; then  # Less than 10MB
    echo "Warning: Low disk space available"
    echo "Available: ${AVAILABLE_SPACE}KB"
    echo "Validation reports may not be generated"
fi
```

### 7. Cleanup (Optional)

Users may want to preserve or cleanup validation artifacts:

```bash
# Note: We preserve the working directory by default for user review
# Users can manually clean up with:
# rm -rf .work/bmh-ironic-check-redfish-profile

echo "Note: Validation artifacts preserved for review"
echo "To clean up: rm -rf .work/bmh-ironic-check-redfish-profile"
```

## Adaptation Guidance

If the standard validation process doesn't work for your environment:

### Using a Different Profile Version

If a newer profile version is available:

```bash
# Check for available profiles
curl -s https://api.github.com/repos/openstack/ironic/contents/redfish-interop-profiles | \
    grep -o '"name": "[^"]*OpenStackIronicProfile[^"]*"'

# Use a specific version
PROFILE_URL="https://raw.githubusercontent.com/openstack/ironic/master/redfish-interop-profiles/OpenStackIronicProfile.v1_2_0.json"
```

### Running Validation with Custom Options

The Redfish-Interop-Validator supports many options:

```bash
# Show all available options
rf_interop_validator --help

# Common additional options:
#   --logdir: Directory for logs and output files
#   -v, --verbose: Verbosity of tool in stdout
#   --debugging: Output debug statements to text log
#   --collectionlimit: Limit on number of collection members to validate
#   --authtype: Authorization type (None|Basic|Session|Token)

# Example with additional options:
rf_interop_validator \
    -i "$BMC_ADDRESS" \
    -u "$BMC_USERNAME" \
    -p "$BMC_PASSWORD" \
    --logdir "$REPORT_DIR" \
    --verbose \
    --collectionlimit 100 \
    "$PROFILE_FILE"
```

### Handling Proxy Environments

If behind a corporate proxy:

```bash
# Set proxy environment variables before running
export https_proxy="http://proxy.example.com:8080"
export http_proxy="http://proxy.example.com:8080"
export no_proxy="localhost,127.0.0.1"

# Then run the command
/openshift:bmh-ironic-check-redfish-profile ...
```

### Offline Validation

If internet access is restricted:

```bash
# 1. Pre-download the profile on a machine with internet access
curl -o OpenStackIronicProfile.v1_1_0.json \
    https://raw.githubusercontent.com/openstack/ironic/master/redfish-interop-profiles/OpenStackIronicProfile.v1_1_0.json

# 2. Transfer the file to the target system
scp OpenStackIronicProfile.v1_1_0.json user@target:/path/to/.work/

# 3. Modify the command to skip download and use local file
# (The implementation should check if file exists before downloading)
```

## Return Value

The command outputs a comprehensive validation report with:

- **Format**: Text-based summary with structured sections

**Example output (PASSED validation):**
```text
Checking for Redfish-Interop-Validator...
✓ Redfish-Interop-Validator is already installed
  Version: 2.1.5

Downloading OpenStack Ironic Redfish profile...
✓ Successfully downloaded Ironic profile
  Profile: OpenStackIronicProfile v1.1.0
  Location: /path/to/.work/bmh-ironic-check-redfish-profile/OpenStackIronicProfile.v1_1_0.json

Running Redfish interoperability validation...
BMC: https://192.168.1.100

This may take several minutes as the validator checks all Redfish endpoints...

Validating Service Root...
Validating Systems Collection...
Validating Managers Collection...
Validating VirtualMedia Resources...
[... detailed validation output ...]

Validation complete

==========================================
Validation Results Summary
==========================================

BMC Address: https://192.168.1.100
Profile: OpenStack Ironic v1.1.0

Total Tests: 142
  ✓ Passed: 138
  ⚠ Warnings: 3
  ✗ Failed: 1

Compliance Score: 97.2%

✓ Virtual Media: Detected in validation

==========================================
Result: BMC PASSED validation
==========================================

✓ This BMC meets the OpenStack Ironic Redfish requirements
✓ Compatible with Metal3/Ironic provisioning
✓ Suitable for OpenShift baremetal deployments

Recommended BMC protocol (use in BareMetalHost address):
  Dell iDRAC: idrac-virtualmedia:// (if virtual media supported)
  Redfish:    redfish-virtualmedia:// or redfish://

Detailed Reports Available:
  - Log: validation_report_20231216_143022/validation.log
  - Results: validation_report_20231216_143022/results.json
  - HTML Report: validation_report_20231216_143022/index.html

Working Directory: /path/to/.work/bmh-ironic-check-redfish-profile

Note: Validation artifacts preserved for review
To clean up: rm -rf .work/bmh-ironic-check-redfish-profile
```

**Example output (FAILED validation):**
```text
[... installation and setup output ...]

==========================================
Validation Results Summary
==========================================

BMC Address: https://192.168.1.101
Profile: OpenStack Ironic v1.1.0

Total Tests: 142
  ✓ Passed: 98
  ⚠ Warnings: 12
  ✗ Failed: 32

Compliance Score: 69.0%

Critical Issues Found:

  ✗ VirtualMedia.Insert
    Required action 'InsertMedia' not found
  ✗ VirtualMedia.Eject
    Required action 'EjectMedia' not found
  ✗ ComputerSystem.Boot.BootSourceOverrideTarget
    Missing required boot target options

✗ Virtual Media: Not detected or not tested

==========================================
Result: BMC FAILED validation
==========================================

⚠ This BMC does not fully meet the Ironic requirements

Common issues:
  - Missing virtual media support
  - Incomplete boot source override implementation
  - Outdated Redfish schema versions
  - Missing required Redfish endpoints

Recommendations:
  1. Check for BMC firmware updates
  2. Review detailed report for specific failures
  3. Consider using non-virtualmedia protocol (redfish://, ipmi://)
  4. Contact hardware vendor for support

Detailed Reports Available:
  - Log: validation_report_20231216_143522/validation.log
  - Results: validation_report_20231216_143522/results.json

Working Directory: /path/to/.work/bmh-ironic-check-redfish-profile

Note: Validation artifacts preserved for review
To clean up: rm -rf .work/bmh-ironic-check-redfish-profile
```

**Exit codes:**
- **0**: BMC passed validation (meets Ironic requirements)
- **1**: Error occurred (connection failure, installation error, missing profile)
- **2**: BMC failed validation (does not meet requirements)

## Example


```bash
# Create credentials file
cat > ~/.bmc-creds << 'EOF'
username=user
password=password
EOF

# Set restrictive permissions
chmod 600 ~/.bmc-creds

# Run validation
/openshift:bmh-ironic-check-redfish-profile 192.168.1.100 ~/.bmc-creds
```

## Arguments

- **$1 (bmc-address)**: The BMC network address (IP address or FQDN)
  - Can be provided with or without `https://` prefix
  - Examples: `192.168.1.100`, `ilo-server.example.com`, `https://bmc.local`

- **$2 (credentials-file)**: Path to file containing BMC credentials
  - File format (plain text, one per line):
    ```ini
    username=<bmc-username>
    password=<bmc-password>
    ```
  - **Security best practices**:
    - Set restrictive permissions: `chmod 600 <file>`
    - Store outside repository/version control
    - Delete after use or store in secure location
    - Never commit to git
  - Example file content:
    ```ini
    username=user
    password=password
    ```

## Understanding the OpenStack Ironic Profile

The OpenStackIronicProfile defines the minimum Redfish capabilities required for Ironic provisioning:

### Key Requirements Checked:

1. **Virtual Media Support**
   - CD/DVD virtual media devices
   - InsertMedia and EjectMedia actions
   - Ability to mount remote ISO images via HTTP/HTTPS

2. **Boot Control**
   - Boot source override capability
   - Support for CD, Hdd, Pxe boot targets
   - One-time and continuous boot modes

3. **Power Management**
   - Power state reporting (On, Off)
   - Power control actions (ForceOff, ForceOn, GracefulShutdown, ForceRestart)

4. **System Information**
   - System inventory (model, serial number, manufacturer)
   - Processor and memory information
   - Network interface details

5. **Manager Information**
   - BMC firmware version
   - Manager network configuration
   - Manager reset capabilities

6. **Indicators**
   - System LED control (for visual identification)

### Profile Versions

- **v1.1.0**: Enhanced requirements (current, includes virtual media)

## Troubleshooting

### Installation Failures

If Redfish-Interop-Validator fails to install:

```bash
# Try upgrading pip first
python3 -m pip install --upgrade pip

# Install with verbose output
pip3 install -v --user redfish_interop_validator

# Check Python version
python3 --version  # Should be 3.6 or higher

# Install dependencies manually
pip3 install --user requests redfish jsonschema
```

### Validation Hangs or Times Out

If validation takes too long or hangs:

```bash
# Limit collection members to test (add to validator command)
--collectionlimit 10

# Enable verbose output to see progress
-v

# Check BMC responsiveness
curl -sk -u "user:pass" https://bmc-address/redfish/v1/
```

### Profile Download Failures

If unable to download the Ironic profile:

```bash
# Check GitHub accessibility
curl -I https://raw.githubusercontent.com

# Try alternative download methods
wget https://raw.githubusercontent.com/openstack/ironic/master/redfish-interop-profiles/OpenStackIronicProfile.v1_1_0.json

# Manual download and use local file
# (Copy profile to .work/ directory before running)
```

### Permission Errors

If encountering permission issues:

```bash
# Check write permissions in working directory
ls -ld .work/

# Create working directory manually with proper permissions
mkdir -p .work/bmh-ironic-check-redfish-profile
chmod 755 .work/bmh-ironic-check-redfish-profile

# Install validator to user directory (not system-wide)
pip3 install --user redfish_interop_validator
```

### Incomplete Validation Results

If validation produces incomplete results:

```bash
# Run with verbose output
rf_interop_validator --verbose ...

# Check validation log for errors
cat .work/bmh-ironic-check-redfish-profile/validation_report_*/validation.log

# Verify BMC is fully operational
# Some BMCs enter degraded modes that affect Redfish
```

## Security Considerations

- **Credentials file security**: Credentials are read from a file to avoid exposure in command-line arguments
  - **Set restrictive permissions**: `chmod 600 <credentials-file>` (owner read/write only)
  - **Store securely**: Use secure locations like `~/.config/` or encrypted filesystems
  - **Never commit to version control**: Add to `.gitignore` immediately
  - **Delete after use**: For temporary validations, remove credentials files: `rm <file>`
  - **Audit access**: Check file permissions regularly: `ls -l <credentials-file>`
  - **Alternative**: Use Kubernetes secrets or vault systems for production environments

- **TLS certificate validation**: The validator does not strictly enforce certificate validation with basic auth
  - Acceptable for lab/testing environments with self-signed certificates
  - For production, consider using proper CA certificates
  - Self-signed certificates can be added to system trust store
  - Use `--authtype Session` for stricter security requirements

- **Network security**: Communication with BMC occurs over HTTPS
  - Ensure BMC network is properly segmented
  - Consider using VPN or jump host for remote access
  - BMCs should not be directly exposed to the internet

- **Report artifacts**: Validation reports may contain sensitive system information
  - Review reports before sharing
  - Clean up reports when no longer needed
  - Store securely if retention is required

- **Read-only validation**: This command only reads BMC status
  - No modifications are made to BMC configuration
  - Safe to run multiple times
  - No risk of service disruption

## Performance Considerations

- **Validation duration**: Full validation typically takes 5-15 minutes
  - Depends on BMC performance and network latency
  - Some BMCs rate-limit API requests
  - Can be reduced with `--sample` option (less thorough)

- **Network impact**: Validation makes numerous HTTP requests
  - May trigger rate limiting on some BMCs
  - Minimal bandwidth usage (mostly small JSON payloads)
  - No impact on production workloads

- **Resource usage**: Validator has minimal resource requirements
  - CPU: < 5% on modern systems
  - Memory: < 200MB
  - Disk: ~10MB for reports
  - Network: ~1-5MB total data transfer

## See Also

- Redfish-Interop-Validator: https://github.com/DMTF/Redfish-Interop-Validator
- OpenStack Ironic Profiles: https://github.com/openstack/ironic/tree/master/redfish-interop-profiles
- Redfish API Specification: https://www.dmtf.org/standards/redfish
- Metal3 Documentation: https://metal3.io/
- OpenShift Baremetal Documentation: https://docs.openshift.com/container-platform/latest/installing/installing_bare_metal/
- BareMetalHost API: https://github.com/metal3-io/baremetal-operator/blob/main/docs/api.md
- Related commands: `/openshift:ironic-status`, `/openshift:cluster-health-check`

## Notes

- This validation provides a comprehensive check beyond simple virtual media detection
- The Ironic profile represents community-validated minimum requirements
- Passing validation strongly indicates compatibility with Metal3/Ironic
- Some BMCs may still work even if failing validation (degraded functionality)
- Regular firmware updates may improve compliance scores
- Different BMC vendors have varying levels of Redfish implementation completeness
- The validator is maintained by DMTF and regularly updated for new Redfish versions
