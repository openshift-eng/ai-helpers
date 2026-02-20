---
name: Detect Container Runtime
description: Detect whether podman or docker is available on the system and configure appropriate runtime settings
---

# Detect Container Runtime

This skill detects the available container runtime (podman or docker) on the system and provides the appropriate configuration for running containers, including SELinux mount flags.

## When to Use This Skill

Use this skill when you need to:

- Determine which container runtime is available on the system
- Run containers with proper volume mount flags for the detected runtime
- Build container images using the available runtime
- Execute container commands in a portable way across different systems

## Prerequisites

At least one of the following must be installed:

1. **Podman** (preferred)
   - Check if installed: `command -v podman`
   - Common on RHEL, CentOS, Fedora systems

2. **Docker**
   - Check if installed: `command -v docker`
   - Common on Ubuntu, macOS, Windows systems

## Implementation Steps

### Step 1: Detect Available Runtime

Run the following detection logic:

```bash
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    SELINUX_FLAG=":Z"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    SELINUX_FLAG=""
else
    echo "Error: Neither podman nor docker found in PATH"
    exit 1
fi
```

### Step 2: Capture Runtime Variables

After detection, you will have two variables:

1. **CONTAINER_RUNTIME**: Either `podman` or `docker`
2. **SELINUX_FLAG**: Either `:Z` (for podman) or empty string (for docker)

### Step 3: Use in Commands

**For building images:**

```bash
$CONTAINER_RUNTIME build -t <image-name>:latest -f <Dockerfile> .
```

**For running containers with volume mounts:**

```bash
$CONTAINER_RUNTIME run --rm -v /path/to/local:/path/in/container${SELINUX_FLAG} <image-name>:latest
```

**For running with environment variables:**

```bash
$CONTAINER_RUNTIME run --rm \
  -e SOME_VAR=value \
  -v /path/to/local:/path/in/container${SELINUX_FLAG} \
  <image-name>:latest
```

## Output Variables

| Variable | Description | Podman Value | Docker Value |
|----------|-------------|--------------|--------------|
| `CONTAINER_RUNTIME` | Path to the container runtime binary | `podman` | `docker` |
| `SELINUX_FLAG` | SELinux volume mount flag | `:Z` | (empty) |

## SELinux Context

The `:Z` flag is used with podman on SELinux-enabled systems (RHEL, Fedora, CentOS) to:

- Relabel the mounted volume content with the container's SELinux label
- Allow the container to access the mounted files
- This is a **private unshared label** - only this container can access the files

For docker, SELinux handling is typically different or disabled, so no flag is needed.

## Error Handling

### Neither Runtime Found

If neither podman nor docker is available:

```
Error: Neither podman nor docker found in PATH

Please install one of the following:
  - Podman: https://podman.io/getting-started/installation
  - Docker: https://docs.docker.com/get-docker/
```

### Permission Issues

If the container runtime requires elevated privileges:

**Podman** (rootless by default):
- Usually works without sudo
- If issues occur, check: `podman info`

**Docker**:
- May require user to be in the `docker` group
- Check with: `groups | grep docker`
- Add user: `sudo usermod -aG docker $USER`

## Examples

### Example 1: Basic Detection

```bash
# Detect runtime
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    SELINUX_FLAG=":Z"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    SELINUX_FLAG=""
else
    echo "Error: Neither podman nor docker found in PATH"
    exit 1
fi

echo "Using container runtime: $CONTAINER_RUNTIME"
```

### Example 2: Build and Run

```bash
# After detection...
IMAGE_NAME="my-app"

# Build
$CONTAINER_RUNTIME build -t ${IMAGE_NAME}:latest -f Dockerfile .

# Run with volume mount
$CONTAINER_RUNTIME run --rm \
  -v $HOME/.kube/config:/kubeconfig/config${SELINUX_FLAG} \
  ${IMAGE_NAME}:latest
```

### Example 3: Inline Flag Handling

For one-liners where you can't set variables:

```bash
$(command -v podman || command -v docker) run --rm \
  -v $KUBECONFIG:/kubeconfig/config$([ "$(command -v podman)" ] && echo ":Z" || echo "") \
  my-image:latest
```

## Integration with Other Skills

This skill is used by:

- `generate-e2e-dockerfile` - To build the generated Dockerfile
- `run-e2e-tests-in-container` command - Main e2e test execution
- Any skill that needs to run containers

## Notes

- Podman is preferred when both are available (better rootless support, no daemon)
- The detection order (podman first) is intentional
- SELinux flags are only needed for volume mounts, not for other operations
- Both runtimes use compatible command-line interfaces for basic operations

