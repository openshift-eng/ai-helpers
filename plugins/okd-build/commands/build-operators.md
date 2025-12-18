---
description: Automate compilation of OpenShift operators from source to target OKD SCOS
argument-hint: [--fix] [--registry=<registry>] [--base-release=<release-image>]
---

## Name
okd-build:build-operators

## Synopsis
```
/okd-build:build-operators [--fix] [--registry=<registry>] [--base-release=<release-image>]
```

## Description
The `okd-build:build-operators` command automates the compilation of OpenShift operators from source to target OKD (Stream CoreOS - SCOS). It discovers operator directories, transforms Dockerfiles for SCOS compatibility, builds container images using Podman, and orchestrates the creation of a custom OKD release payload.

This command streamlines the process of building multiple operators in a workspace by:
- Automatically discovering operator directories and their Dockerfiles
- Converting base images from RHEL to SCOS variants
- Building operators with appropriate SCOS tags
- Optionally creating a custom release payload using `oc adm release new`

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
   - Find and replace any OpenShift base image with SCOS equivalent:
     - Pattern: `FROM registry.ci.openshift.org/ocp/4.21:base-rhel9`
     - Replacement: `FROM registry.ci.openshift.org/origin/scos-4.21:base-stream9`
     - Also handle variants like `base-rhel8`, `builder`, etc.
   - Use the Edit tool to perform the replacement

3. **Determine SCOS build arguments**
   - Check if the operator supports SCOS builds:
     - Examine `Makefile` for `TAGS` or `scos` references
     - Check `OWNERS` file or repository documentation
   - If SCOS is supported, prepare build arg: `--build-arg TAGS=scos`

### Phase 3: Build Execution (Podman)

1. **Prepare build command**
   - Extract operator name from directory name
   - Construct Podman build command:
     ```bash
     podman build -t test-[OPERATOR-NAME]:latest -f [DOCKERFILE_PATH] [BUILD_ARGS] [CONTEXT_DIR]
     ```
   - Include `--build-arg TAGS=scos` if applicable

2. **Execute builds**
   - Run the Podman build command for each operator
   - Capture stdout and stderr for analysis
   - Display build progress to the user

3. **Error handling**
   - If build fails, analyze error logs:
     - Check for missing dependencies (e.g., Go modules, system packages)
     - Check for architecture mismatches (e.g., ARM vs x86)
     - Check for network issues (registry access)
   - If `--fix` flag is present:
     - Attempt common fixes:
       - Add missing dependencies to Dockerfile
       - Adjust build architecture flags
       - Update Go module requirements
     - Retry the build once
   - If build still fails or `--fix` is not present, report error to user and continue with next operator

4. **Tag and push images** (optional)
   - If `--registry` is provided:
     - Determine user's registry namespace (from `--registry` or default to `quay.io/${USER}`)
     - Tag images: `podman tag test-[OPERATOR-NAME]:latest [REGISTRY]/[OPERATOR-NAME]:latest`
     - Push images: `podman push [REGISTRY]/[OPERATOR-NAME]:latest`
     - Capture image digests for release orchestration

### Phase 4: Release Orchestration

1. **Verify prerequisites**
   - Check if `oc` CLI is installed and available
   - Verify all operator images were successfully pushed to registry
   - Collect image digests from push operation

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
     - Use `--base-release` flag value if provided
     - Default: `quay.io/okd/scos-release:4.21.0-okd-scos.ec.3`
   - Construct command:
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

## Return Value

- **Format**: Summary report with build status and optional release command

The command outputs:

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

Example output:
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

## Examples

1. **Build all operators in workspace**:
   ```
   /okd-build:build-operators
   ```
   Discovers and builds all operators in current directory subdirectories.

2. **Build with automatic error fixing**:
   ```
   /okd-build:build-operators --fix
   ```
   Attempts to automatically resolve common build errors.

3. **Build and push to custom registry**:
   ```
   /okd-build:build-operators --registry=quay.io/myuser
   ```
   Builds operators and pushes to specified registry.

4. **Build with custom base release**:
   ```
   /okd-build:build-operators --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```
   Uses a specific OKD release as the base for the custom release payload.

5. **Build with fixing and custom registry**:
   ```
   /okd-build:build-operators --fix --registry=quay.io/myuser
   ```
   Combines automatic error fixing with custom registry.

6. **Build with all options**:
   ```
   /okd-build:build-operators --fix --registry=quay.io/myuser --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```
   Uses all available options for maximum flexibility.

## Arguments

- `--fix` (Optional): Boolean flag. When present, automatically attempts to fix common build errors such as missing dependencies or architecture mismatches. Will retry failed builds once after applying fixes.

- `--registry` (Optional): String. Target registry for pushing built images. Format: `registry.example.com/namespace`. Default: `quay.io/${USER}` where `${USER}` is the current system user.

- `--base-release` (Optional): String. Base OKD release image to use for creating the custom release payload. This should be a fully qualified image reference. Default: `quay.io/okd/scos-release:4.21.0-okd-scos.ec.3`. Examples:
  - `quay.io/okd/scos-release:4.21.0-okd-scos.ec.3`
  - `quay.io/okd/scos-release:4.22.0-okd-scos.ec.1`
  - Custom release images from your registry

## Prerequisites

1. **Podman**: Container build tool
   - Check if installed: `which podman`
   - Installation: https://podman.io/getting-started/installation

2. **oc CLI** (for release orchestration): OpenShift CLI
   - Check if installed: `which oc`
   - Installation: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html

3. **Registry Authentication**: Credentials for target registry
   - Login: `podman login quay.io`

## Notes

- The command operates on subdirectories of the current working directory
- Each subdirectory is treated as a potential operator project
- SCOS transformation specifically targets OKD 4.21 base images
- Failed builds do not stop the overall process - the command continues with remaining operators
- The `--allow-missing-images` flag in the release command permits partial operator updates
