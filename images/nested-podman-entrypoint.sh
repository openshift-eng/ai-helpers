#!/usr/bin/env bash

# Create Home directory
if [ ! -d "${HOME}" ]; then
  mkdir -p "${HOME}"
fi

# Create Podman configuration
mkdir -p "${HOME}/.config/containers"

if [ ! -f "${HOME}/.config/containers/registries.conf" ]; then
  cat > "${HOME}/.config/containers/registries.conf" <<'REGISTRIES'
unqualified-search-registries = [
  "registry.access.redhat.com",
  "registry.redhat.io",
  "docker.io"
]
short-name-mode = "permissive"
REGISTRIES
fi

if [ ! -f "${HOME}/.config/containers/storage.conf" ]; then
  if [ -c "/dev/fuse" ] && [ -f "/usr/bin/fuse-overlayfs" ]; then
    cat > "${HOME}/.config/containers/storage.conf" <<'STORAGE'
[storage]
driver = "overlay"
graphroot = "/tmp/graphroot"
[storage.options.overlay]
mount_program = "/usr/bin/fuse-overlayfs"
STORAGE
  else
    cat > "${HOME}/.config/containers/storage.conf" <<'STORAGE'
[storage]
driver = "vfs"
STORAGE
  fi
fi

# Create User ID entry if running as an unmapped UID (common in OpenShift)
if ! whoami &> /dev/null; then
  if [ -w /etc/passwd ]; then
    echo "${USER_NAME:-user}:x:$(id -u):0:${USER_NAME:-user} user:${HOME}:/bin/bash" >> /etc/passwd
    echo "${USER_NAME:-user}:x:$(id -u):" >> /etc/group
  fi
fi

# Create subuid/gid entries for rootless podman
USER_NAME="$(whoami)"
# In OpenShift CI, the pod runs with hostUsers: false, which maps only 65536
# UIDs/GIDs (0-65535) into the pod's user namespace. The host rootless-podman
# default of 100000:65536 falls outside that range, so newuidmap/newgidmap
# fail with EPERM. Compute the range dynamically so it always fits in 0-65535.
# Outside hostUsers: false (e.g. a normal OpenShift pod with a large
# SCC-assigned arbitrary UID), that computation goes negative or zero, so
# fall back to the host rootless-podman default in that case.
SUBID_START_DEFAULT=$(( $(id -u) + 1 ))
SUBID_COUNT_DEFAULT=$(( 65536 - SUBID_START_DEFAULT ))
if (( SUBID_COUNT_DEFAULT <= 0 )); then
  SUBID_START_DEFAULT=100000
  SUBID_COUNT_DEFAULT=65536
fi
SUBID_START="${SUBID_START:-$SUBID_START_DEFAULT}"
SUBID_COUNT="${SUBID_COUNT:-$SUBID_COUNT_DEFAULT}"
echo "${USER_NAME}:${SUBID_START}:${SUBID_COUNT}" > /etc/subuid
echo "${USER_NAME}:${SUBID_START}:${SUBID_COUNT}" > /etc/subgid

exec "$@"
