#!/bin/bash
# Detect Container Runtime Skill
# Detects whether podman or docker is available and sets appropriate flags

set -e

# Detect available container runtime
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    SELINUX_FLAG=":Z"
    echo "Detected container runtime: podman"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    SELINUX_FLAG=""
    echo "Detected container runtime: docker"
else
    echo "Error: Neither podman nor docker found in PATH" >&2
    echo "" >&2
    echo "Please install one of the following:" >&2
    echo "  - Podman: https://podman.io/getting-started/installation" >&2
    echo "  - Docker: https://docs.docker.com/get-docker/" >&2
    exit 1
fi

# Export variables for use by calling scripts
export CONTAINER_RUNTIME
export SELINUX_FLAG

# Output results
echo "CONTAINER_RUNTIME=$CONTAINER_RUNTIME"
echo "SELINUX_FLAG=$SELINUX_FLAG"
