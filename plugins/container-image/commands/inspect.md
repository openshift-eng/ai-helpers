---
description: Inspect and provide detailed breakdown of a container image
argument-hint: <image>
---

## Name
container-image:inspect

## Synopsis
```
/container-image:inspect <image>
```

## Description

The `container-image:inspect` command provides a comprehensive breakdown of a container image using `skopeo` and `podman`. It analyzes the image metadata, configuration, and layers to give you detailed information about the image structure, size, architecture, and contents.

This command is useful for:
- Understanding image composition and layers
- Verifying image architecture and OS
- Checking image size and disk usage
- Inspecting image labels and annotations
- Validating image configuration
- Troubleshooting image-related issues
- Verifying multi-architecture image support
- Checking which platforms are available for an image
- Comparing platform-specific image differences
- Planning multi-arch image builds

The command works with images from any registry (quay.io, docker.io, registry.redhat.io, etc.) and automatically detects whether an image is a manifest list (multi-architecture) or a single image, providing detailed analysis for both cases.

## Prerequisites

**Required Tools:**

1. **skopeo** - For image inspection without pulling
   - Check if installed: `which skopeo`
   - Installation:
     - RHEL/Fedora: `sudo dnf install skopeo`
     - Ubuntu/Debian: `sudo apt-get install skopeo`
     - macOS: `brew install skopeo`
   - Documentation: https://github.com/containers/skopeo

2. **podman** (Optional) - For additional image analysis
   - Check if installed: `which podman`
   - Installation:
     - RHEL/Fedora: `sudo dnf install podman`
     - Ubuntu/Debian: `sudo apt-get install podman`
     - macOS: `brew install podman`
   - Documentation: https://podman.io/

**Registry Authentication:**

For private registries, ensure you're authenticated:
```bash
# Using skopeo
skopeo login registry.example.com

# Using podman
podman login registry.example.com
```

## Implementation

The command performs the following analysis steps:

1. **Check Tool Availability**:
   - Verify `skopeo` is installed
   - Check for `podman` (optional but recommended)
   - If tools are missing, provide installation instructions

2. **Inspect Image Metadata with skopeo**:
   ```bash
   skopeo inspect docker://<image>
   ```

   This provides:
   - Image digest and tags
   - Architecture and OS
   - Layer information
   - Creation timestamp
   - Labels and annotations
   - Environment variables
   - Exposed ports
   - Entrypoint and command

3. **Determine Image Type**:
   - Check if the image is a **manifest list** (multi-arch) or a **single image**
   - Fetch raw manifest to determine type:
     ```bash
     skopeo inspect --raw docker://<image>
     ```
   - Parse `schemaVersion` and `mediaType` to identify:
     - **Manifest List** (OCI Index): `application/vnd.oci.image.index.v1+json`
     - **Manifest List** (Docker): `application/vnd.docker.distribution.manifest.list.v2+json`
     - **Single Image** (OCI): `application/vnd.oci.image.manifest.v1+json`
     - **Single Image** (Docker): `application/vnd.docker.distribution.manifest.v2+json`

4. **Extract Manifest List Details** (if applicable):
   - For manifest lists, extract platform information for each variant:
     - Architecture (amd64, arm64, ppc64le, s390x, etc.)
     - OS (linux, windows)
     - Variant (v7, v8 for ARM)
     - Digest of platform-specific image
     - Size of platform-specific image
   - Optionally inspect each platform variant:
     ```bash
     skopeo inspect docker://<image>@<platform-digest>
     ```
   - Compare platform differences:
     - Image sizes across platforms
     - Layer counts
     - Creation timestamps
     - Configuration differences

5. **Analyze Image Layers**:
   - List all layers with their sizes
   - Calculate total image size
   - Identify the largest layers
   - Show layer history (if available)

6. **Extract Configuration Details**:
   - Operating system and distribution
   - Architecture (amd64, arm64, ppc64le, s390x, etc.)
   - Environment variables
   - Working directory
   - User/UID
   - Exposed ports
   - Volume mount points
   - Labels (including OpenShift/Kubernetes metadata)

7. **Infer Image Purpose**:
   - Analyze image metadata to determine the likely purpose:
     - Image name and repository patterns (e.g., "nginx", "postgres", "ocp-release")
     - Labels (especially `io.openshift.*`, `io.k8s.*`, `org.opencontainers.*`)
     - Entrypoint and command (what executable is being run)
     - Exposed ports (common service ports)
     - Environment variables (framework indicators, version info)
   - Provide context about:
     - What the image is (e.g., "web server", "database", "operator", "release payload")
     - Common use cases
     - Notable characteristics based on configuration

8. **Present Organized Summary**:
   - Image identity (digest, tags)
   - Inferred purpose and context
   - Basic information (OS, architecture, created date)
   - Size breakdown
   - Configuration summary
   - Manifest list details (if applicable)
   - Notable labels and annotations

## Return Value

The command outputs a structured breakdown of the image:

```
================================================================================
CONTAINER IMAGE INSPECTION
================================================================================
Image: quay.io/openshift-release-dev/ocp-release:4.20.0-multi

IMAGE PURPOSE:
  This is an OpenShift release image containing the cluster-version-operator
  for OpenShift 4.20.0. It's part of the OpenShift release payload used to
  manage cluster upgrades and version management.

BASIC INFORMATION:
  Manifest Digest: sha256:4f1e772349a20f2eb69e8cf70d73b4fcc299c15cb6e4f027696eb469e66d4080
  Type:            Manifest List (Multi-Architecture)
  Manifest Type:   Docker Distribution Manifest List v2
  Created:         2025-10-16T13:35:26Z

MANIFEST LIST DETAILS:
  This is a multi-architecture manifest list containing 4 platform variants.

  AVAILABLE PLATFORMS (4):
  --------------------------------------------------------------------------------
  1. linux/amd64
     Digest:  sha256:b4bd68afe0fb47bf9876f51e33d88e9dd218fed2dcf41b025740591746dda5c9
     Size:    167.6 MB (175,762,648 bytes)
     Layers:  6
     Created: 2025-10-16T13:35:26Z

  2. linux/arm64
     Digest:  sha256:eec6b0e6ff1c4cf5edc158c41a171ac8b02d7e0389715b663528a4ec0931b1f2
     Size:    161.6 MB (169,501,175 bytes)
     Layers:  6
     Created: 2025-10-16T13:35:26Z

  3. linux/ppc64le
     Digest:  sha256:4bb9eb125d4d35c100699617ec8278691a9cee771ebacb113173b75f0707df56
     Size:    174.4 MB (182,863,818 bytes)
     Layers:  6
     Created: 2025-10-16T13:35:26Z

  4. linux/s390x
     Digest:  sha256:5e852c796f2d3b83b3bd4506973a455a521b6933e3944740b32c1ed483b2174e
     Size:    163.2 MB (171,055,271 bytes)
     Layers:  6
     Created: 2025-10-16T13:35:26Z

  PLATFORM COMPARISON:
    Size Range:      161.6 MB - 174.4 MB (arm64 smallest, ppc64le largest)
    Size Variance:   ~12.8 MB difference between smallest and largest
    Architectures:   4 platforms (amd64, arm64, ppc64le, s390x)
    OS:              linux (all)
    Layer Count:     6 (all platforms)
    Build Time:      All platforms built simultaneously

  USAGE:
    To pull a specific platform:
      podman pull --platform=linux/amd64 quay.io/openshift-release-dev/ocp-release:4.20.0-multi
      podman pull quay.io/openshift-release-dev/ocp-release@sha256:b4bd68afe0fb...  # amd64

CONFIGURATION (amd64 example):
  User:           <default>
  WorkingDir:     <default>
  Entrypoint:     ["/usr/bin/cluster-version-operator"]
  Cmd:            <none>
  Env:
    - PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    - BUILD_VERSION=v4.20.0
    - OS_GIT_VERSION=4.20.0-202509230726.p2.g9de00ba.assembly.stream.el9-9de00ba

EXPOSED PORTS:
  <none>

LABELS:
  io.openshift.release: 4.20.0
  io.openshift.release.base-image-digest: sha256:6f58f521f51ae43617d2dead1efbe9690b605d646565892bb0f8c6030a742ba7

VOLUMES:
  <none>

LAYER DETAILS (amd64):
  Total Layers: 6
  Total Size:   167.6 MB (compressed)
================================================================================
```

## Examples

1. **Inspect a public image**:
   ```
   /container-image:inspect quay.io/openshift-release-dev/ocp-release:4.17.0-x86_64
   ```
   Provides full breakdown of the OpenShift release image.

2. **Inspect a manifest list**:
   ```
   /container-image:inspect registry.redhat.io/ubi9/ubi:latest
   ```
   Shows available architectures and platform-specific details.

3. **Inspect with specific tag**:
   ```
   /container-image:inspect docker.io/library/nginx:1.25
   ```
   Analyzes the nginx image with tag 1.25.

4. **Inspect by digest**:
   ```
   /container-image:inspect quay.io/prometheus/prometheus@sha256:abc123...
   ```
   Inspects a specific image version by its digest.

5. **Inspect a private registry image**:
   ```
   /container-image:inspect registry.example.com/myorg/myapp:v1.0.0
   ```
   Analyzes an image from a private registry (requires authentication).

## Error Handling

- **Image not found**: If the image doesn't exist or the name is incorrect:
  - Verify the image name and tag
  - Check registry accessibility
  - Ensure authentication is set up for private registries

- **Tool not available**: If `skopeo` is not installed:
  - Display installation instructions for the user's platform
  - Suggest using `podman inspect` as an alternative (if podman is available)

- **Authentication errors**: If registry requires authentication:
  - Prompt user to run `skopeo login <registry>` or `podman login <registry>`
  - Provide documentation link for registry authentication

- **Network errors**: If registry is unreachable:
  - Check internet connectivity
  - Verify registry URL is correct
  - Check for proxy/firewall issues

## Notes

- **No Image Pull Required**: `skopeo inspect` fetches metadata without downloading the entire image
- **Manifest Lists**: For multi-arch images, the command automatically detects and shows detailed platform information including per-platform digests, sizes, and configurations
- **Manifest List vs Single Image**: The command clearly distinguishes between manifest lists and single-architecture images
- **Platform Selection**: Container runtimes automatically select the correct platform from a manifest list
- **Digest Pinning**: Always displays the image digest for reproducible deployments
- **Label Standards**: Highlights important labels like OpenShift/Kubernetes metadata
- **Size Accuracy**: Layer sizes are compressed sizes as stored in the registry
- **Size Variations**: Platform-specific images may have different sizes due to architecture differences
- **OCI vs Docker**: Supports both OCI and Docker manifest formats
- **Variant Field**: ARM images may have variants (v7, v8) for different ARM versions
- **Registry Support**: Works with any OCI-compliant registry

## Arguments

- **$1** (image): Required. The full image reference including registry, repository, and tag/digest.
  - Format: `[registry/]repository[:tag|@digest]`
  - Examples:
    - `quay.io/openshift/origin-node:latest`
    - `docker.io/library/alpine:3.18`
    - `registry.redhat.io/ubi9/ubi@sha256:abc123...`
