---
description: Automate compilation of OpenShift operators from source to target OKD SCOS
argument-hint: [--registry=<registry>] [--base-release=<release-image>] [--bash]
---

## Name
okd-build:build-operators

## Synopsis
```
/okd-build:build-operators [--registry=<registry>] [--base-release=<release-image>] [--bash]
```

## Description
The `okd-build:build-operators` command automates the compilation of OpenShift operators from source to target OKD (Stream CoreOS - SCOS). It discovers operator directories, transforms Dockerfiles for SCOS compatibility, builds container images using Podman, and orchestrates the creation of a custom OKD release payload.

This command streamlines the process of building multiple operators in a workspace by:
- Automatically discovering operator directories and their Dockerfiles
- Converting base images from RHEL to SCOS variants
- Building operators with appropriate SCOS tags
- Optionally creating a custom release payload using `oc adm release new`
- Optionally generating a bash script for manual execution with `--bash` flag

## Implementation

### Phase 1: Discovery & Selection

1. **Scan workspace for operator directories**
   - List all subdirectories in the current working directory
   - For each directory, identify if it contains an operator project:
     - Check for presence of common operator files (e.g., `Makefile`, `go.mod`, `OWNERS`)
     - Look for Kubernetes manifests in `manifests/` or `deploy/` directories

2. **Locate Dockerfiles**
   - For each operator directory, find the appropriate Dockerfile using this priority:
     1. Check for `Dockerfile` in the root directory
     2. If not found, search in common subdirectories:
        - `openshift/Dockerfile`
        - `build/Dockerfile`
        - `images/Dockerfile`
     3. If multiple Dockerfiles exist, select the one with the most recent modification time (`mtime`)
   - Use bash commands: `find`, `stat`, `sort` to determine the most recent file

3. **Display discovery results**
   - Present a list of discovered operators and their Dockerfiles to the user
   - Ask for confirmation before proceeding

### Phase 2: SCOS Transformation

1. **Analyze Dockerfile content**
   - Read the selected Dockerfile for each operator
   - Identify base image references

2. **Replace base images**
   - **ONLY replace base image lines** matching the pattern `FROM registry.ci.openshift.org/ocp/X.XX:base-rhel[89]`
   - **DO NOT replace** builder images (e.g., `FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-...`)
   - **DO NOT replace** golang images
   - Replacement pattern:
     - Pattern: `FROM registry.ci.openshift.org/ocp/4.XX:base-rhel9`
     - Replacement: `FROM registry.ci.openshift.org/origin/scos-4.XX:base-stream9`
   - Also handle RHEL 8 variants:
     - Pattern: `FROM registry.ci.openshift.org/ocp/4.XX:base-rhel8`
     - Replacement: `FROM registry.ci.openshift.org/origin/scos-4.XX:base-stream8`
   - Use the Edit tool to perform the replacement
   - Example Dockerfile (before):
     ```dockerfile
     FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.23-openshift-4.19 AS builder
     # ... build steps ...
     FROM registry.ci.openshift.org/ocp/4.19:base-rhel9
     # ... final image steps ...
     ```
   - Example Dockerfile (after):
     ```dockerfile
     FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.23-openshift-4.19 AS builder  # NOT CHANGED
     # ... build steps ...
     FROM registry.ci.openshift.org/origin/scos-4.19:base-stream9  # CHANGED
     # ... final image steps ...
     ```

3. **Prepare SCOS build arguments**
   - All operators will be built with SCOS tags
   - Prepare build arg: `--build-arg TAGS=scos` for all builds

### Phase 3: Build Execution (Podman)

1. **Prepare build command**
   - Extract operator name from directory name
   - Construct Podman build command with SCOS build argument:
     ```bash
     podman build -t test-[OPERATOR-NAME]:latest -f [DOCKERFILE_PATH] --build-arg TAGS=scos [CONTEXT_DIR]
     ```
   - The `--build-arg TAGS=scos` is always included for all operator builds

2. **Execute builds**
   - Run the Podman build command for each operator
   - Capture stdout and stderr for analysis
   - Display build progress to the user

3. **Error handling**
   - If build fails, analyze error logs:
     - Check for missing dependencies (e.g., Go modules, system packages)
     - Check for architecture mismatches (e.g., ARM vs x86)
     - Check for network issues (registry access)
   - Automatically attempt common fixes:
     - Add missing dependencies to Dockerfile
     - Adjust build architecture flags
     - Update Go module requirements
   - Retry the build once after applying fixes
   - If build still fails, report error to user and continue with next operator

4. **Tag and push images** (optional)
   - If `--registry` is provided:
     - Determine user's registry namespace (from `--registry` or default to `quay.io/${USER}`)
     - Tag images: `podman tag test-[OPERATOR-NAME]:latest [REGISTRY]/[OPERATOR-NAME]:latest`
     - Push images: `podman push [REGISTRY]/[OPERATOR-NAME]:latest`
     - Capture image digests using `skopeo inspect docker://[REGISTRY]/[OPERATOR-NAME]:latest`
     - Store digests for release orchestration

### Phase 4: Release Orchestration

1. **Verify prerequisites**
   - Check if `oc` CLI is installed and available
   - Verify all operator images were successfully pushed to registry
   - Use the image digests captured from `skopeo inspect` in Phase 3

2. **Map operators to release components**
   - For each built operator, determine its component name in the release:
     - Extract component name from operator metadata (e.g., `manifests/` directory)
     - Map operator name to standard OpenShift component names
     - Common mappings:
       - `cluster-monitoring-operator` → `cluster-monitoring-operator`
       - `cluster-ingress-operator` → `cluster-ingress-operator`
       - etc.

3. **Generate oc adm release command**
   - Determine base release image:
     - If `--base-release` flag is provided, use that value
     - Otherwise, fetch dynamically from OKD release stream API:
       - Query: `https://amd64.origin.releases.ci.openshift.org/api/v1/releasestreams/accepted`
       - Extract: `jq -r '.["4-scos-next"][0]'` to get latest version (e.g., "4.21.0-okd-scos.ec.13")
       - Construct: `quay.io/okd/scos-release:${VERSION}`
       - Command: `curl -s https://amd64.origin.releases.ci.openshift.org/api/v1/releasestreams/accepted | jq -r '.["4-scos-next"][0]'`
   - Check for cluster-version-operator:
     - If `cluster-version-operator` is in the list of built operators:
       - **Include** `--to-image-base` flag pointing to the CVO image with digest
       - Format: `--to-image-base=[REGISTRY]/cluster-version-operator@[DIGEST]`
     - If `cluster-version-operator` is NOT in the list of built operators:
       - **Omit** the `--to-image-base` flag entirely
   - Construct command (with CVO):
     ```bash
     oc adm release new \
       --from-release=[BASE_RELEASE_IMAGE] \
       --to-image-base=[CVO_IMAGE]@[CVO_DIGEST] \
       cluster-version-operator=[CVO_IMAGE]@[CVO_DIGEST] \
       [OTHER_OPERATOR]=[IMAGE_DIGEST] \
       ... \
       --to-image=quay.io/${USER}/openshift-release:4.21-custom \
       --keep-manifest-list \
       --allow-missing-images
     ```
   - Construct command (without CVO):
     ```bash
     oc adm release new \
       --from-release=[BASE_RELEASE_IMAGE] \
       [OPERATOR_NAME]=[IMAGE_DIGEST] \
       [OPERATOR_NAME2]=[IMAGE_DIGEST2] \
       ... \
       --to-image=quay.io/${USER}/openshift-release:4.21-custom \
       --keep-manifest-list \
       --allow-missing-images
     ```

4. **Execute or display command**
   - Display the generated command to the user
   - Ask if they want to execute it
   - If confirmed, execute and monitor progress
   - Provide the final release image reference

### Bash Script Generation Mode (--bash flag)

When the `--bash` flag is provided, the command operates in script generation mode instead of direct execution:

1. **Perform Discovery and Transformation**
   - Execute Phase 1 (Discovery & Selection) normally
   - Execute Phase 2 (SCOS Transformation) to update Dockerfiles
   - Do NOT execute the actual builds

2. **Generate Build Script**
   - Create a bash script file: `build-okd-operators.sh`
   - For each discovered operator, add commands to:
     - Change directory to the operator location
     - Execute the podman build command with SCOS tags
     - Tag the image for the target registry (if `--registry` provided)
     - Push the image to the registry (if `--registry` provided)
     - Capture image digest using `skopeo inspect` and store in variable
   - Add error handling: `set -e` at the top to exit on errors
   - Add informational echo statements between operations
   - Make script executable: `chmod +x build-okd-operators.sh`

3. **Generate Release Command**
   - At the end of the script, add the `oc adm release new` command
   - Use the digest variables captured from `skopeo inspect` commands
   - Execute the release command automatically in the script

4. **Output Script Location**
   - Display the script location to the user
   - Provide instructions on how to execute it
   - Explain that they should review and customize the script before running

**Example Generated Script Structure:**
```bash
#!/bin/bash
set -e

echo "Building OKD Operators for SCOS"
echo "================================"

# Fetch latest SCOS release version (if --base-release not provided)
echo "Fetching latest SCOS release version..."
SCOS_VERSION=$(curl -s https://amd64.origin.releases.ci.openshift.org/api/v1/releasestreams/accepted | jq -r '.["4-scos-next"][0]')
BASE_RELEASE="quay.io/okd/scos-release:${SCOS_VERSION}"
echo "Using base release: ${BASE_RELEASE}"
echo ""

# Build cluster-version-operator
echo "Building cluster-version-operator..."
cd /path/to/cluster-version-operator
podman build -t test-cluster-version-operator:latest -f Dockerfile --build-arg TAGS=scos .
podman tag test-cluster-version-operator:latest quay.io/user/cluster-version-operator:latest
podman push quay.io/user/cluster-version-operator:latest
CVO_DIGEST=$(skopeo inspect docker://quay.io/user/cluster-version-operator:latest | jq -r '.Digest')
echo "cluster-version-operator digest: ${CVO_DIGEST}"

# Build cluster-monitoring-operator
echo "Building cluster-monitoring-operator..."
cd /path/to/cluster-monitoring-operator
podman build -t test-cluster-monitoring-operator:latest -f openshift/Dockerfile --build-arg TAGS=scos .
podman tag test-cluster-monitoring-operator:latest quay.io/user/cluster-monitoring-operator:latest
podman push quay.io/user/cluster-monitoring-operator:latest
CMO_DIGEST=$(skopeo inspect docker://quay.io/user/cluster-monitoring-operator:latest | jq -r '.Digest')
echo "cluster-monitoring-operator digest: ${CMO_DIGEST}"

# Build cluster-ingress-operator
echo "Building cluster-ingress-operator..."
cd /path/to/cluster-ingress-operator
podman build -t test-cluster-ingress-operator:latest -f Dockerfile --build-arg TAGS=scos .
podman tag test-cluster-ingress-operator:latest quay.io/user/cluster-ingress-operator:latest
podman push quay.io/user/cluster-ingress-operator:latest
CIO_DIGEST=$(skopeo inspect docker://quay.io/user/cluster-ingress-operator:latest | jq -r '.Digest')
echo "cluster-ingress-operator digest: ${CIO_DIGEST}"

echo ""
echo "All builds completed!"
echo ""
echo "Creating custom OKD release..."
# Note: --to-image-base is required when cluster-version-operator is being overwritten
oc adm release new \
  --from-release=${BASE_RELEASE} \
  --to-image-base=quay.io/user/cluster-version-operator@${CVO_DIGEST} \
  cluster-version-operator=quay.io/user/cluster-version-operator@${CVO_DIGEST} \
  cluster-monitoring-operator=quay.io/user/cluster-monitoring-operator@${CMO_DIGEST} \
  cluster-ingress-operator=quay.io/user/cluster-ingress-operator@${CIO_DIGEST} \
  --to-image=quay.io/user/openshift-release:4.21-custom \
  --keep-manifest-list \
  --allow-missing-images

echo ""
echo "Release creation complete!"
```

## Return Value

- **Format**: Summary report with build status and optional release command, or bash script location

The command outputs depend on the execution mode:

### Normal Execution Mode (without --bash)

1. **Discovery Summary**:
   - List of discovered operators
   - Selected Dockerfiles for each operator

2. **Build Results**:
   - Status for each operator (Success/Failed)
   - Image references for successful builds
   - Error messages for failed builds

3. **Release Command** (if applicable):
   - Complete `oc adm release new` command
   - Target release image reference

### Bash Script Generation Mode (with --bash)

1. **Discovery Summary**:
   - List of discovered operators
   - Selected Dockerfiles for each operator

2. **Script Location**:
   - Path to generated script: `build-okd-operators.sh`
   - Instructions to review and execute the script
   - Note about SCOS transformations applied to Dockerfiles

**Example output (Normal Mode):**
```
Discovered Operators:
  1. cluster-monitoring-operator → openshift/Dockerfile
  2. cluster-ingress-operator → Dockerfile
  3. cluster-network-operator → build/Dockerfile

Build Results:
  ✓ cluster-monitoring-operator: quay.io/user/cluster-monitoring-operator:latest (sha256:abc123...)
  ✓ cluster-ingress-operator: quay.io/user/cluster-ingress-operator:latest (sha256:def456...)
  ✗ cluster-network-operator: Build failed - missing dependency

Release Command:
oc adm release new \
  --from-release=quay.io/okd/scos-release:4.21.0-okd-scos.ec.3 \
  cluster-monitoring-operator=quay.io/user/cluster-monitoring-operator@sha256:abc123... \
  cluster-ingress-operator=quay.io/user/cluster-ingress-operator@sha256:def456... \
  --to-image=quay.io/user/openshift-release:4.21-custom \
  --keep-manifest-list \
  --allow-missing-images
```

**Example output (Bash Script Mode):**
```
Discovered Operators:
  1. cluster-monitoring-operator → openshift/Dockerfile
  2. cluster-ingress-operator → Dockerfile
  3. cluster-network-operator → build/Dockerfile

SCOS Transformations Applied:
  ✓ cluster-monitoring-operator: Updated base images to SCOS
  ✓ cluster-ingress-operator: Updated base images to SCOS
  ✓ cluster-network-operator: Updated base images to SCOS

Generated Script: ./build-okd-operators.sh

The script has been created and is ready to execute.
Review the script before running to ensure it meets your requirements.

To execute:
  ./build-okd-operators.sh

The script will:
  - Build all operators with SCOS tags
  - Push images to quay.io/user
  - Create custom OKD release with built operators
```

## Examples

1. **Build all operators in workspace**:
   ```
   /okd-build:build-operators
   ```
   Discovers and builds all operators in current directory subdirectories. Automatically attempts to fix build errors if they occur.

2. **Build and push to custom registry**:
   ```
   /okd-build:build-operators --registry=quay.io/myuser
   ```
   Builds operators and pushes to specified registry.

3. **Build with custom base release**:
   ```
   /okd-build:build-operators --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```
   Uses a specific OKD release as the base for the custom release payload.

4. **Build with all options**:
   ```
   /okd-build:build-operators --registry=quay.io/myuser --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```
   Builds with custom registry and base release.

5. **Generate bash script instead of executing**:
   ```
   /okd-build:build-operators --bash
   ```
   Creates `build-okd-operators.sh` script for manual review and execution.

6. **Generate bash script with custom configuration**:
   ```
   /okd-build:build-operators --bash --registry=quay.io/myuser --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```
   Creates a customized build script with specified registry and base release.

## Arguments

- `--registry` (Optional): String. Target registry for pushing built images. Format: `registry.example.com/namespace`. Default: `quay.io/${USER}` where `${USER}` is the current system user.

- `--base-release` (Optional): String. Base OKD release image to use for creating the custom release payload. This should be a fully qualified image reference. If not provided, the latest SCOS release is automatically fetched from the OKD release stream API (`https://amd64.origin.releases.ci.openshift.org/api/v1/releasestreams/accepted`) by querying the first element of the `4-scos-next` array. Examples:
  - `quay.io/okd/scos-release:4.21.0-okd-scos.ec.13` (auto-fetched if not specified)
  - `quay.io/okd/scos-release:4.22.0-okd-scos.ec.1`
  - Custom release images from your registry

- `--bash` (Optional): Boolean flag. When present, generates a bash script (`build-okd-operators.sh`) instead of executing builds directly. The script will include all build commands, image tagging/pushing, digest extraction using `skopeo inspect`, and the final `oc adm release new` command. This allows for manual review and customization before execution.

## Prerequisites

1. **Podman**: Container build tool
   - Check if installed: `which podman`
   - Installation: https://podman.io/getting-started/installation

2. **oc CLI** (for release orchestration): OpenShift CLI
   - Check if installed: `which oc`
   - Installation: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html

3. **Registry Authentication**: Credentials for target registry
   - Login: `podman login quay.io`

4. **curl**: HTTP client for fetching release data
   - Check if installed: `which curl`
   - Installation: Usually pre-installed on most systems
   - Required for fetching latest SCOS release from OKD API when `--base-release` is not specified

5. **jq**: JSON processor
   - Check if installed: `which jq`
   - Installation: https://stedolan.github.io/jq/download/
   - Required for parsing API responses and image digests

6. **skopeo**: Container image inspection tool
   - Check if installed: `which skopeo`
   - Installation: https://github.com/containers/skopeo/blob/main/install.md
   - Required for extracting image digests from registry

## Notes

- The command operates on subdirectories of the current working directory
- Each subdirectory is treated as a potential operator project
- SCOS transformation specifically targets OKD 4.21 base images
- Failed builds do not stop the overall process - the command continues with remaining operators
- The `--allow-missing-images` flag in the release command permits partial operator updates
- **Special case for cluster-version-operator**:
  - When `cluster-version-operator` IS being overwritten (included in built operators): The `oc adm release new` command **MUST include** the `--to-image-base` flag pointing to the cluster-version-operator image with digest
  - When `cluster-version-operator` IS NOT being overwritten: The command should omit the `--to-image-base` flag entirely
  - The `--to-image-base` flag is required for proper release creation only when the CVO is being overwritten
