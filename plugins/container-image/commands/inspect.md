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

The command works with images from any registry (quay.io, docker.io, registry.redhat.io, etc.) and can inspect both manifest lists and individual images.

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
   - For manifest lists, identify available architectures
   - Extract the manifest list structure if applicable

4. **Analyze Image Layers**:
   - List all layers with their sizes
   - Calculate total image size
   - Identify the largest layers
   - Show layer history (if available)

5. **Extract Configuration Details**:
   - Operating system and distribution
   - Architecture (amd64, arm64, ppc64le, s390x, etc.)
   - Environment variables
   - Working directory
   - User/UID
   - Exposed ports
   - Volume mount points
   - Labels (including OpenShift/Kubernetes metadata)

6. **Present Organized Summary**:
   - Image identity (digest, tags)
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
Image: quay.io/openshift-release-dev/ocp-release:4.17.0-x86_64

BASIC INFORMATION:
  Digest:         sha256:abc123...
  Architecture:   amd64
  OS:             linux
  Created:        2024-01-15T10:30:45Z
  Type:           Single Image / Manifest List

MANIFEST LIST (if applicable):
  Available Architectures:
    - linux/amd64
    - linux/arm64
    - linux/ppc64le
    - linux/s390x

SIZE BREAKDOWN:
  Total Size:     1.2 GB
  Layers:         15
  Largest Layer:  256 MB (layer 7)

CONFIGURATION:
  User:           1001
  WorkingDir:     /opt/app
  Entrypoint:     ["/usr/bin/entrypoint.sh"]
  Cmd:            []
  Env:
    - PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    - OPENSHIFT_VERSION=4.17.0

EXPOSED PORTS:
  - 8080/tcp
  - 8443/tcp

LABELS:
  io.k8s.display-name: OpenShift Release
  io.openshift.release: 4.17.0
  version: 4.17.0

VOLUMES:
  - /var/lib/data

LAYER DETAILS:
  Layer 1:  45 MB   sha256:def456...
  Layer 2:  120 MB  sha256:ghi789...
  ...
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
- **Manifest Lists**: For multi-arch images, the command shows all available platforms
- **Digest Pinning**: Always displays the image digest for reproducible deployments
- **Label Standards**: Highlights important labels like OpenShift/Kubernetes metadata
- **Size Accuracy**: Layer sizes are compressed sizes as stored in the registry
- **Registry Support**: Works with any OCI-compliant registry

## Arguments

- **$1** (image): Required. The full image reference including registry, repository, and tag/digest.
  - Format: `[registry/]repository[:tag|@digest]`
  - Examples:
    - `quay.io/openshift/origin-node:latest`
    - `docker.io/library/alpine:3.18`
    - `registry.redhat.io/ubi9/ubi@sha256:abc123...`
