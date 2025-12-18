# OKD Build Plugin

Automate the compilation of OpenShift operators from source to target OKD (Stream CoreOS - SCOS).

## Overview

The OKD Build plugin streamlines the process of building OpenShift operators for OKD SCOS releases. It handles the entire workflow from source discovery to release payload creation, including:

- Automatic operator discovery in your workspace
- Dockerfile transformation for SCOS compatibility
- Container image building with Podman
- Custom release payload orchestration

## Installation

### From Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install okd-build@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git ~/.claude/commands/ai-helpers

# The plugin will be available after restarting Claude Code
```

## Commands

### `/okd-build:build-operators`

Discovers, builds, and orchestrates OpenShift operators for OKD SCOS.

**Syntax:**
```
/okd-build:build-operators [--fix] [--registry=<registry>] [--base-release=<release-image>] [--bash]
```

**Options:**
- `--fix`: Automatically attempt to fix common build errors
- `--registry=<registry>`: Target registry for images (default: `quay.io/${USER}`)
- `--base-release=<release-image>`: Base OKD release image (default: `quay.io/okd/scos-release:4.21.0-okd-scos.ec.3`)
- `--bash`: Generate a bash script instead of executing builds directly

**Examples:**

1. Basic usage (build all operators):
   ```
   /okd-build:build-operators
   ```

2. Build with automatic error fixing:
   ```
   /okd-build:build-operators --fix
   ```

3. Build and push to custom registry:
   ```
   /okd-build:build-operators --registry=quay.io/myuser
   ```

4. Build with custom base release:
   ```
   /okd-build:build-operators --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```

5. Build with all options:
   ```
   /okd-build:build-operators --fix --registry=quay.io/myuser --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```

6. Generate bash script for manual execution:
   ```
   /okd-build:build-operators --bash
   ```

7. Generate bash script with custom configuration:
   ```
   /okd-build:build-operators --bash --registry=quay.io/myuser --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
   ```

## Workflow

### 1. Discovery Phase
The command scans your workspace for operator directories and identifies the appropriate Dockerfiles:
- Checks root directory for `Dockerfile`
- Searches common locations: `openshift/`, `build/`, `images/`
- Selects most recent Dockerfile if multiple exist

### 2. SCOS Transformation
Automatically converts Dockerfiles for SCOS compatibility:
- Replaces RHEL base images with SCOS equivalents
- Adds SCOS build arguments when applicable
- Example transformation:
  ```dockerfile
  # Before
  FROM registry.ci.openshift.org/ocp/4.21:base-rhel9

  # After
  FROM registry.ci.openshift.org/origin/scos-4.21:base-stream9
  ```

### 3. Build Execution
Builds each operator using Podman:
- Constructs appropriate build commands
- Handles SCOS-specific build flags
- Optionally attempts to fix build errors with `--fix`

### 4. Release Orchestration
Generates a custom OKD release payload:
- Uses base release (configurable via `--base-release`, default: `quay.io/okd/scos-release:4.21.0-okd-scos.ec.3`)
- Maps operator images to release components
- Provides ready-to-execute `oc adm release new` command

### Bash Script Mode (--bash flag)
When using the `--bash` flag, the workflow changes:
- Phases 1 & 2 execute normally (Discovery and SCOS Transformation)
- Instead of building, a bash script is generated: `build-okd-operators.sh`
- The script includes:
  - `cd` commands to navigate to each operator directory
  - `podman build` commands with SCOS tags
  - Image tagging and pushing to registry
  - `skopeo inspect` commands to extract image digests
  - Final `oc adm release new` command with captured digests
- You can review, customize, and execute the script manually

## Prerequisites

### Required Tools

1. **Podman** - Container build engine
   ```bash
   # Check installation
   which podman

   # Install: https://podman.io/getting-started/installation
   ```

2. **oc CLI** - OpenShift command-line interface (for release orchestration)
   ```bash
   # Check installation
   which oc

   # Install: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html
   ```

3. **Registry Authentication**
   ```bash
   # Login to your container registry
   podman login quay.io
   ```

4. **skopeo** - Container image inspection (required for `--bash` mode)
   ```bash
   # Check installation
   which skopeo

   # Install: https://github.com/containers/skopeo/blob/main/install.md
   ```

5. **jq** - JSON processor (required for `--bash` mode)
   ```bash
   # Check installation
   which jq

   # Install: https://stedolan.github.io/jq/download/
   ```

## Use Cases

### Building Multiple Operators
If you have a workspace with multiple operator repositories:

```bash
workspace/
├── cluster-monitoring-operator/
├── cluster-ingress-operator/
└── cluster-network-operator/
```

Simply run `/okd-build:build-operators` from the workspace directory, and the command will discover and build all operators.

### Creating Custom OKD Releases
After building operators, you can create a custom OKD release that includes your modified operators. The command generates the complete `oc adm release new` command for you.

### Testing Operator Changes
When developing operator changes for OKD:
1. Make your code changes
2. Run `/okd-build:build-operators --fix` to build and test
3. Use the generated release command to deploy to a test cluster

## Troubleshooting

### Build Failures
- **Missing dependencies**: Use `--fix` flag to attempt automatic resolution
- **Architecture mismatches**: Ensure you're building for the correct architecture
- **Registry access**: Verify registry authentication with `podman login`

### Dockerfile Not Found
The command searches common locations. If your Dockerfile is in an unusual location:
1. Create a symlink: `ln -s path/to/Dockerfile Dockerfile`
2. Or move the Dockerfile to a standard location

### SCOS Build Tags
All operators are built with `--build-arg TAGS=scos` to ensure SCOS compatibility. This build argument is automatically included in all podman build commands executed by the plugin.

## Advanced Usage

### Targeting Specific OKD Versions
To target a different OKD version, use the `--base-release` flag with your desired release:
```bash
/okd-build:build-operators --base-release=quay.io/okd/scos-release:4.22.0-okd-scos.ec.1
```

Note: You may also need to update the base image transformations in Dockerfiles if targeting versions other than 4.21 (e.g., `ocp/4.22:base-rhel9` → `origin/scos-4.22:base-stream9`)

### Custom Build Arguments
If you need additional build arguments beyond `--build-arg TAGS=scos`, you can:
- Modify the Dockerfile before running the command
- Or extend the command implementation to accept custom build args

## Contributing

To contribute improvements to this plugin:

1. Fork the repository: https://github.com/openshift-eng/ai-helpers
2. Make your changes following the plugin conventions in `CLAUDE.md`
3. Test with `/okd-build:build-operators`
4. Submit a pull request

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Documentation**: https://github.com/openshift-eng/ai-helpers

## License

This plugin is part of the ai-helpers project. See the repository LICENSE for details.
