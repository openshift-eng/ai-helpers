---
description: Analyze and display manifest list details for multi-architecture images
argument-hint: <image>
---

## Name
container-image:manifest-list

## Synopsis
```
/container-image:manifest-list <image>
```

## Description

The `container-image:manifest-list` command specifically analyzes manifest lists (also known as multi-architecture images or "fat manifests"). It determines whether an image is a manifest list or a single-architecture image and provides detailed information about each platform variant.

A **manifest list** is an index that points to multiple platform-specific images, allowing container runtimes to automatically select the appropriate image based on the host architecture. This is commonly used for images that support multiple CPU architectures (amd64, arm64, ppc64le, s390x) and operating systems.

This command is useful for:
- Verifying multi-architecture image support
- Checking which platforms are available for an image
- Comparing platform-specific image differences
- Troubleshooting architecture-specific issues
- Planning multi-arch image builds
- Validating manifest list structure

## Prerequisites

**Required Tools:**

1. **skopeo** - For manifest inspection
   - Check if installed: `which skopeo`
   - Installation:
     - RHEL/Fedora: `sudo dnf install skopeo`
     - Ubuntu/Debian: `sudo apt-get install skopeo`
     - macOS: `brew install skopeo`
   - Documentation: https://github.com/containers/skopeo

**Registry Authentication:**

For private registries:
```bash
skopeo login registry.example.com
```

## Implementation

The command performs the following analysis:

1. **Check Tool Availability**:
   - Verify `skopeo` is installed
   - If missing, provide installation instructions

2. **Fetch Raw Manifest**:
   ```bash
   skopeo inspect --raw docker://<image>
   ```

   This returns the raw manifest or manifest list JSON.

3. **Determine Manifest Type**:
   - Parse the `schemaVersion` and `mediaType` fields
   - Identify if it's:
     - **Manifest List** (OCI Index): `application/vnd.oci.image.index.v1+json`
     - **Manifest List** (Docker): `application/vnd.docker.distribution.manifest.list.v2+json`
     - **Single Image** (OCI): `application/vnd.oci.image.manifest.v1+json`
     - **Single Image** (Docker): `application/vnd.docker.distribution.manifest.v2+json`

4. **Extract Platform Information** (for manifest lists):
   - For each platform in the manifest list:
     - Architecture (amd64, arm64, ppc64le, s390x, etc.)
     - OS (linux, windows)
     - Variant (v7, v8 for ARM)
     - Digest of the platform-specific image
     - Size of the platform-specific image

5. **Inspect Each Platform Variant**:
   For manifest lists, optionally inspect each platform-specific image:
   ```bash
   skopeo inspect docker://<image>@<platform-digest>
   ```

6. **Compare Platform Differences**:
   - Image sizes across platforms
   - Layer counts
   - Creation timestamps
   - Configuration differences

## Return Value

The command outputs detailed manifest list analysis:

**For Manifest Lists:**
```
================================================================================
MANIFEST LIST ANALYSIS
================================================================================
Image: quay.io/openshift-release-dev/ocp-release:4.17.0

Manifest Type: OCI Image Index (Manifest List)
Manifest Digest: sha256:abc123...

AVAILABLE PLATFORMS (4):
--------------------------------------------------------------------------------
1. linux/amd64
   Digest:  sha256:def456...
   Size:    1.2 GB
   Layers:  15

2. linux/arm64
   Digest:  sha256:ghi789...
   Size:    1.1 GB
   Layers:  15

3. linux/ppc64le
   Digest:  sha256:jkl012...
   Size:    1.3 GB
   Layers:  15

4. linux/s390x
   Digest:  sha256:mno345...
   Size:    1.2 GB
   Layers:  15

PLATFORM COMPARISON:
  Size Range:      1.1 GB - 1.3 GB
  Architecture:    4 platforms
  OS:              linux (all)

PLATFORM-SPECIFIC DETAILS:
--------------------------------------------------------------------------------
Platform: linux/amd64
  Created:    2024-01-15T10:30:45Z
  Entrypoint: ["/usr/bin/entrypoint.sh"]
  Labels:     io.openshift.release=4.17.0

Platform: linux/arm64
  Created:    2024-01-15T10:32:12Z
  Entrypoint: ["/usr/bin/entrypoint.sh"]
  Labels:     io.openshift.release=4.17.0
  ...

USAGE:
To pull a specific platform:
  podman pull --platform=linux/amd64 quay.io/openshift-release-dev/ocp-release:4.17.0
  skopeo copy docker://quay.io/openshift-release-dev/ocp-release:4.17.0@sha256:def456... ...
================================================================================
```

**For Single Images:**
```
================================================================================
MANIFEST LIST ANALYSIS
================================================================================
Image: docker.io/library/alpine:3.18

Manifest Type: Docker Image Manifest v2 (Single Image)
Manifest Digest: sha256:xyz789...

This is NOT a manifest list - it's a single-architecture image.

PLATFORM:
  Architecture: amd64
  OS:           linux
  Size:         7.3 MB
  Layers:       1

NOTES:
  - This image only supports a single platform (linux/amd64)
  - To use on other architectures, a manifest list would be needed
  - Consider using a multi-arch variant if available
================================================================================
```

## Examples

1. **Analyze a multi-arch OpenShift image**:
   ```
   /container-image:manifest-list quay.io/openshift-release-dev/ocp-release:4.17.0
   ```
   Shows all supported architectures for the OpenShift release.

2. **Check if an image is multi-arch**:
   ```
   /container-image:manifest-list registry.redhat.io/ubi9/ubi:latest
   ```
   Determines if UBI has multi-arch support and lists platforms.

3. **Inspect a specific platform variant**:
   ```
   /container-image:manifest-list quay.io/prometheus/prometheus:latest
   ```
   Shows available platforms and their specific details.

4. **Verify architecture support**:
   ```
   /container-image:manifest-list docker.io/library/nginx:latest
   ```
   Checks which architectures nginx supports.

## Error Handling

- **Image not found**: Verify image name and tag are correct
- **Not a manifest list**: Clearly indicate when an image is single-architecture
- **Tool not available**: Provide installation instructions for `skopeo`
- **Authentication errors**: Guide user to authenticate with the registry
- **Network errors**: Suggest checking connectivity and registry accessibility

## Notes

- **Manifest List vs Single Image**: The command clearly distinguishes between the two
- **Platform Selection**: Container runtimes automatically select the correct platform
- **Digest Pinning**: For reproducible builds, always use digest references
- **Size Variations**: Platform-specific images may have different sizes due to architecture differences
- **OCI vs Docker**: The command supports both OCI and Docker manifest formats
- **Variant Field**: ARM images may have variants (v7, v8) for different ARM versions

## Use Cases

1. **Multi-Arch Verification**: Confirm an image supports required architectures before deployment
2. **Build Validation**: Verify all platforms were built and pushed correctly
3. **Troubleshooting**: Diagnose architecture-specific issues by comparing platform variants
4. **Migration Planning**: Understand platform support when migrating to new architectures
5. **Image Optimization**: Compare sizes across platforms to identify optimization opportunities

## Arguments

- **$1** (image): Required. The full image reference including registry, repository, and tag/digest.
  - Format: `[registry/]repository[:tag|@digest]`
  - Examples:
    - `quay.io/openshift-release-dev/ocp-release:4.17.0`
    - `registry.redhat.io/ubi9/ubi:latest`
    - `docker.io/library/alpine@sha256:abc123...`
