# Container Image Plugin

Container image inspection and analysis tools using skopeo and podman.

## Overview

This plugin provides commands to inspect, analyze, and compare container images from any OCI-compliant registry. It leverages `skopeo` and `podman` to provide detailed insights into image structure, manifest lists, layers, and configuration without requiring full image pulls.

## Features

- **Image Inspection**: Detailed breakdown of image metadata, layers, and configuration
- **Manifest List Analysis**: Identify multi-architecture support and platform variants
- **Image Comparison**: Compare two images to identify differences
- **Tag Discovery**: List and analyze available tags for a repository

## Commands

### `/container-image:inspect`

Inspect and provide detailed breakdown of a container image.

**Usage:**
```bash
/container-image:inspect <image>
```

**Examples:**
```bash
/container-image:inspect quay.io/openshift-release-dev/ocp-release:4.17.0-x86_64
/container-image:inspect registry.redhat.io/ubi9/ubi:latest
/container-image:inspect docker.io/library/nginx@sha256:abc123...
```

**What it shows:**
- Image digest and basic metadata
- Architecture and OS information
- Size breakdown and layer details
- Configuration (environment, entrypoint, ports, volumes)
- Labels and annotations
- Manifest type (single image vs manifest list)

See [commands/inspect.md](commands/inspect.md) for full documentation.

### `/container-image:manifest-list`

Analyze and display manifest list details for multi-architecture images.

**Usage:**
```bash
/container-image:manifest-list <image>
```

**Examples:**
```bash
/container-image:manifest-list quay.io/openshift-release-dev/ocp-release:4.17.0
/container-image:manifest-list registry.redhat.io/ubi9/ubi:latest
```

**What it shows:**
- Whether the image is a manifest list or single image
- Available platforms (architecture + OS combinations)
- Platform-specific digests and sizes
- Comparison across platforms
- How to pull specific platform variants

See [commands/manifest-list.md](commands/manifest-list.md) for full documentation.

### `/container-image:compare`

Compare two container images to identify differences.

**Usage:**
```bash
/container-image:compare <image1> <image2>
```

**Examples:**
```bash
/container-image:compare quay.io/myapp:v1.0.0 quay.io/myapp:v2.0.0
/container-image:compare registry.prod.example.com/myapp:latest registry.staging.example.com/myapp:latest
```

**What it shows:**
- Whether images are identical (digest match)
- Metadata differences (creation date, size)
- Layer analysis (added, removed, modified layers)
- Configuration changes (environment variables, labels, entrypoint)
- Size impact
- Summary of significant changes

See [commands/compare.md](commands/compare.md) for full documentation.

### `/container-image:tags`

List and analyze available tags for a container image repository.

**Usage:**
```bash
/container-image:tags <repository>
```

**Examples:**
```bash
/container-image:tags quay.io/openshift-release-dev/ocp-release
/container-image:tags docker.io/library/nginx
```

**What it shows:**
- All available tags for the repository
- Tag metadata (creation date, size, architecture)
- Tag categorization (version, date-based, special tags)
- Recent tags and update patterns
- Recommendations for tag selection
- Duplicate tags (same digest, different names)

See [commands/tags.md](commands/tags.md) for full documentation.

## Installation

### From the Claude Code Plugin Marketplace

1. **Add the marketplace** (if not already added):
   ```bash
   /plugin marketplace add openshift-eng/ai-helpers
   ```

2. **Install the container-image plugin**:
   ```bash
   /plugin install container-image@ai-helpers
   ```

3. **Use the commands**:
   ```bash
   /container-image:inspect quay.io/openshift-release-dev/ocp-release:4.17.0
   ```

## Prerequisites

### Required Tools

**skopeo** - Primary tool for image inspection

- Check if installed: `which skopeo`
- Installation:
  - RHEL/Fedora: `sudo dnf install skopeo`
  - Ubuntu/Debian: `sudo apt-get install skopeo`
  - macOS: `brew install skopeo`
- Documentation: https://github.com/containers/skopeo

### Optional Tools

**podman** - Additional image analysis capabilities

- Installation:
  - RHEL/Fedora: `sudo dnf install podman`
  - Ubuntu/Debian: `sudo apt-get install podman`
  - macOS: `brew install podman`
- Documentation: https://podman.io/

**dive** - Interactive layer analysis (for `/container-image:compare`)

- Installation: https://github.com/wagoodman/dive
- Provides detailed layer-by-layer exploration

### Registry Authentication

For private registries, authenticate before running commands:

```bash
# Using skopeo
skopeo login registry.example.com

# Using podman (if installed)
podman login registry.example.com
```

Authentication is typically stored at `~/.docker/config.json` or `${XDG_RUNTIME_DIR}/containers/auth.json`.

## Use Cases

### Development Workflows

1. **Version Selection**: Find the right image version for your deployment
   ```bash
   /container-image:tags quay.io/myapp
   /container-image:inspect quay.io/myapp:v2.1.0
   ```

2. **Multi-Arch Development**: Verify architecture support before deployment
   ```bash
   /container-image:manifest-list registry.redhat.io/ubi9/ubi:latest
   ```

3. **Update Analysis**: Understand changes before upgrading
   ```bash
   /container-image:compare myapp:current myapp:latest
   ```

### Troubleshooting

1. **Deployment Issues**: Verify correct image is being used
   ```bash
   /container-image:inspect <failing-image>
   ```

2. **Architecture Mismatches**: Check platform compatibility
   ```bash
   /container-image:manifest-list <image>
   ```

3. **Size Issues**: Identify what's consuming space
   ```bash
   /container-image:inspect <large-image>
   /container-image:compare <old-image> <new-image>
   ```

### Security & Compliance

1. **Image Verification**: Confirm image authenticity via digest
   ```bash
   /container-image:inspect myapp@sha256:abc123...
   ```

2. **Change Tracking**: Document what changed between versions
   ```bash
   /container-image:compare prod:v1.0.0 prod:v1.1.0
   ```

3. **Registry Migration**: Verify images copied correctly
   ```bash
   /container-image:compare source.registry.com/app:v1 dest.registry.com/app:v1
   ```

## Common Workflows

### Upgrading an Application Image

```bash
# 1. List available versions
/container-image:tags quay.io/myapp

# 2. Inspect the new version
/container-image:inspect quay.io/myapp:v2.0.0

# 3. Compare with current version
/container-image:compare quay.io/myapp:v1.5.0 quay.io/myapp:v2.0.0

# 4. Check architecture support
/container-image:manifest-list quay.io/myapp:v2.0.0
```

### Verifying Multi-Architecture Support

```bash
# 1. Check if image is multi-arch
/container-image:manifest-list quay.io/myapp:latest

# 2. Inspect specific platform
/container-image:inspect quay.io/myapp@sha256:<arm64-digest>

# 3. Compare platforms
/container-image:compare quay.io/myapp@sha256:<amd64-digest> quay.io/myapp@sha256:<arm64-digest>
```

### Investigating Image Bloat

```bash
# 1. Inspect current image
/container-image:inspect myapp:latest

# 2. Compare with previous version
/container-image:compare myapp:v1.0.0 myapp:latest

# 3. Identify which layers added size
# (Layer analysis in the comparison output)
```

## Tips & Best Practices

### Image References

- **Use digests for production**: `myapp@sha256:abc123...` (immutable)
- **Use tags for development**: `myapp:latest` (convenient but mutable)
- **Be specific**: `myapp:v1.2.3` is better than `myapp:v1`

### Multi-Architecture Images

- Always check platform support with `/container-image:manifest-list`
- Pull specific platforms when needed: `podman pull --platform=linux/arm64 <image>`
- Verify all platforms are updated in manifest lists

### Performance

- `skopeo inspect` doesn't pull the full image (fast and efficient)
- For large repositories, `/container-image:tags` may sample tags
- Use `--filter` options to narrow results for large tag lists

### Security

- Always verify image digests match expectations
- Check for unexpected configuration changes with `/container-image:compare`
- Use `/container-image:inspect` to review labels and metadata

## Plugin Structure

```
plugins/container-image/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── commands/
│   ├── inspect.md           # Image inspection command
│   ├── manifest-list.md     # Manifest list analysis command
│   ├── compare.md           # Image comparison command
│   └── tags.md              # Tag listing command
└── README.md                # This file
```

## Development

### Adding New Commands

To add a new command to this plugin:

1. Create a new markdown file in `commands/`:
   ```bash
   touch plugins/container-image/commands/your-command.md
   ```

2. Follow the structure from existing commands (see `commands/inspect.md`)

3. Include these sections:
   - Name
   - Synopsis
   - Description
   - Prerequisites
   - Implementation
   - Return Value
   - Examples
   - Error Handling
   - Notes
   - Arguments

4. Test your command:
   ```bash
   /container-image:your-command
   ```

### Testing

Test commands with various image types:
- Public images (docker.io, quay.io)
- Private registries (requires authentication)
- Multi-arch images (manifest lists)
- Single-arch images
- Large images (layer analysis)
- Different registries (Red Hat, Quay, Docker Hub)

## Related Plugins

- **openshift** - OpenShift development utilities (includes cluster and dependency management)
- **must-gather** - Analyze OpenShift diagnostic data (may include container image analysis)
- **prow-job** - CI job analysis (analyzes build artifacts including images)

## Contributing

Contributions are welcome! When adding new container image analysis commands:

1. Ensure the command provides unique value not covered by existing commands
2. Follow the existing command structure and documentation format
3. Include comprehensive examples and error handling
4. Test with multiple registries and image types
5. Update this README with new command documentation

## License

See [LICENSE](../../LICENSE) for details.
