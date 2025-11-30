---
description: Compare two container images to identify differences
argument-hint: <image1> <image2>
---

## Name
container-image:compare

## Synopsis
```
/container-image:compare <image1> <image2>
```

## Description

The `container-image:compare` command compares two container images and identifies their differences. This is useful for understanding what changed between image versions, comparing images from different registries, or verifying image rebuilds.

The command analyzes and compares:
- Image metadata (digests, creation dates)
- Layer differences (added, removed, modified)
- Size differences
- Configuration changes (environment variables, labels, entrypoints)
- Platform/architecture support
- Security and vulnerability differences (if scanning tools available)

This command is useful for:
- Understanding changes between image versions
- Verifying image rebuilds match expectations
- Comparing images across registries (e.g., production vs staging)
- Identifying what layers changed in an update
- Troubleshooting deployment issues
- Security auditing and change tracking

## Prerequisites

**Required Tools:**

1. **skopeo** - For image inspection and comparison
   - Check if installed: `which skopeo`
   - Installation:
     - RHEL/Fedora: `sudo dnf install skopeo`
     - Ubuntu/Debian: `sudo apt-get install skopeo`
     - macOS: `brew install skopeo`
   - Documentation: https://github.com/containers/skopeo

**Optional Tools:**

2. **podman** - For additional image analysis
   - Useful for layer-by-layer comparison
   - Installation: See `/container-image:inspect` prerequisites

3. **dive** - For detailed layer analysis
   - Check if installed: `which dive`
   - Installation: https://github.com/wagoodman/dive
   - Provides interactive layer comparison

**Registry Authentication:**

For private registries:
```bash
skopeo login registry.example.com
```

## Implementation

The command performs the following comparison:

1. **Check Tool Availability**:
   - Verify `skopeo` is installed
   - Check for optional tools (`podman`, `dive`)

2. **Inspect Both Images**:
   ```bash
   skopeo inspect docker://<image1>
   skopeo inspect docker://<image2>
   ```

3. **Compare Basic Metadata**:
   - Digests (are they the same image?)
   - Creation timestamps
   - Architecture and OS
   - Manifest type (single vs manifest list)

4. **Analyze Layer Differences**:
   - Extract layer digests from both images
   - Identify:
     - **Common layers**: Layers shared between images
     - **Added layers**: New layers in image2
     - **Removed layers**: Layers from image1 not in image2
     - **Modified layers**: Layers with same position but different content
   - Calculate size differences

5. **Compare Configuration**:
   - Environment variables (added, removed, changed)
   - Labels and annotations
   - Exposed ports
   - Entrypoint and command
   - Working directory
   - User/UID
   - Volume mount points

6. **Calculate Size Impact**:
   - Total size difference
   - Size added by new layers
   - Size saved by removed layers

7. **Present Structured Comparison**:
   - Summary of differences
   - Detailed breakdown by category
   - Highlight significant changes
   - Provide recommendations

## Return Value

The command outputs a structured comparison report:

```
================================================================================
CONTAINER IMAGE COMPARISON
================================================================================
Image 1: quay.io/openshift-release-dev/ocp-release:4.16.0
Image 2: quay.io/openshift-release-dev/ocp-release:4.17.0

COMPARISON SUMMARY:
  Images are:     DIFFERENT
  Digest match:   NO
  Architecture:   Both linux/amd64

METADATA COMPARISON:
  Attribute        Image 1                          Image 2                          Change
  ────────────────────────────────────────────────────────────────────────────────────────
  Digest           sha256:abc123...                 sha256:def456...                 CHANGED
  Created          2023-11-15T10:30:45Z             2024-01-15T10:30:45Z             +61 days
  Size             1.15 GB                          1.22 GB                          +70 MB

LAYER ANALYSIS:
  Total Layers (Image 1):  15
  Total Layers (Image 2):  17

  Common Layers:    12 layers (850 MB)
  Added Layers:     5 layers (220 MB)
  Removed Layers:   3 layers (150 MB)

  Layer Breakdown:
  ✓ Layer 1-8:     IDENTICAL (base layers)
  + Layer 9:       ADDED in Image 2 (45 MB)    - New component added
  - Layer 10:      REMOVED from Image 1 (30 MB) - Old dependency removed
  ✓ Layer 11-15:   IDENTICAL
  + Layer 16-17:   ADDED in Image 2 (25 MB)    - Updates

CONFIGURATION DIFFERENCES:

  Environment Variables:
    + OPENSHIFT_VERSION=4.17.0  (was: 4.16.0)
    + NEW_FEATURE_FLAG=enabled  (added)
    - DEPRECATED_FLAG=true      (removed)

  Labels:
    + io.openshift.release=4.17.0  (was: 4.16.0)
    + io.openshift.build-date=2024-01-15  (was: 2023-11-15)

  Exposed Ports:
    ✓ 8080/tcp  (unchanged)
    ✓ 8443/tcp  (unchanged)

  Entrypoint:
    ✓ ["/usr/bin/entrypoint.sh"]  (unchanged)

  Command:
    - ["--legacy-mode"]  (removed)
    + ["--v2-mode"]      (added)

SIGNIFICANT CHANGES:
  • Version upgrade: 4.16.0 → 4.17.0
  • Size increase: +70 MB (+6%)
  • 5 new layers added
  • 3 old layers removed
  • Command-line arguments changed
  • New feature flag enabled

RECOMMENDATIONS:
  • Review changelog for 4.16.0 → 4.17.0 upgrade
  • Test with new command-line arguments (--v2-mode)
  • Verify NEW_FEATURE_FLAG behavior in your environment
  • Consider size impact (+70 MB) in constrained environments
================================================================================
```

**For Identical Images:**
```
================================================================================
CONTAINER IMAGE COMPARISON
================================================================================
Image 1: quay.io/myapp:v1.0.0
Image 2: registry.example.com/myapp:v1.0.0

COMPARISON SUMMARY:
  Images are:     IDENTICAL
  Digest match:   YES (sha256:abc123...)

These images are the same, just referenced from different registries.
No differences found.
================================================================================
```

## Examples

1. **Compare two versions of the same image**:
   ```
   /container-image:compare quay.io/openshift-release-dev/ocp-release:4.16.0 quay.io/openshift-release-dev/ocp-release:4.17.0
   ```
   Shows what changed between OpenShift 4.16 and 4.17.

2. **Compare production vs staging**:
   ```
   /container-image:compare registry.prod.example.com/myapp:latest registry.staging.example.com/myapp:latest
   ```
   Verifies staging matches production.

3. **Compare images across registries**:
   ```
   /container-image:compare docker.io/library/nginx:1.25 quay.io/nginx/nginx:1.25
   ```
   Checks if images from different registries are identical.

4. **Verify image rebuild**:
   ```
   /container-image:compare myapp:v1.0.0-original myapp:v1.0.0-rebuilt
   ```
   Confirms rebuild produced the same image.

5. **Compare by digest**:
   ```
   /container-image:compare quay.io/myapp@sha256:abc123... quay.io/myapp@sha256:def456...
   ```
   Compares specific image versions by digest.

## Error Handling

- **Image not found**: Verify both image references are correct
- **Authentication required**: Ensure you're logged into both registries
- **Network errors**: Check connectivity to both registries
- **Tool not available**: Provide installation instructions for `skopeo`
- **Different architectures**: Note when comparing images for different platforms

## Notes

- **Digest Comparison**: If digests match, images are identical
- **Layer Sharing**: Base layers are often shared between versions
- **Size Calculation**: Sizes shown are compressed (as stored in registry)
- **Semantic Versioning**: Helps identify major vs minor changes
- **Build Reproducibility**: Identical source should produce identical digests
- **Registry Metadata**: Some metadata may differ even if image content is identical

## Advanced Usage

**Compare Specific Architectures:**

For manifest lists, you can compare specific platform variants:
```bash
# Compare amd64 variants
/container-image:compare quay.io/myapp:v1@sha256:<amd64-digest-v1> quay.io/myapp:v2@sha256:<amd64-digest-v2>
```

**Layer-by-Layer Analysis:**

If `dive` is installed, the command can provide interactive layer comparison:
```bash
dive <image1> --compare <image2>
```

## Use Cases

1. **Version Upgrades**: Understand what changed before upgrading
2. **Security Auditing**: Track changes to identify security implications
3. **Deployment Verification**: Confirm correct image is deployed
4. **Registry Migration**: Verify images copied between registries
5. **Build Debugging**: Identify why builds differ
6. **Compliance**: Document and track image changes

## Arguments

- **$1** (image1): Required. First image reference.
  - Format: `[registry/]repository[:tag|@digest]`

- **$2** (image2): Required. Second image reference.
  - Format: `[registry/]repository[:tag|@digest]`

**Note**: Images can be from the same or different registries.
