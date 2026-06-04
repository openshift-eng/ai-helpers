# CRI-O Binary Reference

## Binary Details

| Property | Value |
|----------|-------|
| Binary path | `/usr/bin/crio` |
| Systemd unit | `crio.service` |
| Dependent service | `kubelet.service` (must restart after CRI-O restart) |
| RPM package | `cri-o` |
| SELinux context | `system_u:object_r:container_runtime_exec_t:s0` |
| Config drop-in dir | `/etc/crio/crio.conf.d/` |
| Linkmode | dynamic |

## Build Dependencies (Debian/Bookworm)

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libseccomp-dev \
    libgpgme-dev \
    libassuan-dev \
    libgpg-error-dev \
    libselinux1-dev \
    pkg-config \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*
```

## Dynamic Libraries

CRI-O links against these shared libraries. The cross-compiled binary must show the same sonames in `ldd` output:

```text
libseccomp.so.2
libgpgme.so.11
libassuan.so.0
libgpg-error.so.0
libc.so.6
```

## Build Command

```bash
make bin/crio
```

The Makefile auto-detects build tags based on available libraries. Expected tags on RHCOS-compatible builds:

```text
containers_image_ostree_stub
exclude_graphdriver_btrfs
btrfs_noversion
seccomp
selinux
```

## Go Version

Check `go.mod` for the required Go version. Use the matching `golang:<version>-bookworm` Docker image.

## Example Dockerfile

```dockerfile
FROM --platform=linux/amd64 golang:1.23-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libseccomp-dev libgpgme-dev libassuan-dev \
    libgpg-error-dev libselinux1-dev \
    pkg-config make git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/cri-o
COPY . .

RUN make bin/crio && ldd bin/crio
```

## pinns Binary

CRI-O uses `pinns` for pod namespace pinning. If your changes affect networking or namespace handling, you may need to deploy a custom `pinns` as well:

| Property | Value |
|----------|-------|
| Binary path | `/usr/bin/pinns` |
| Build command | `make bin/pinns` |

`pinns` is a small C binary. Build it alongside CRI-O in the same Dockerfile:

```bash
make bin/pinns
```

Deploy it the same way as CRI-O (SCP, chcon, bind-mount).

## CRI-O Preflight Checks

After SCPing the binary, run these CRI-O-specific checks:

```bash
# Verify libraries
ssh core@${WORKER} "ldd /home/core/crio"

# Check version and build info
ssh core@${WORKER} "/home/core/crio --version"

# Validate it can parse the existing config
ssh core@${WORKER} "/home/core/crio config 2>&1 | head -5"
```

If `crio config` fails, the binary may have been built without required build tags or is incompatible with the node's config format.

## CRI-O Restart Behavior

**Restarting CRI-O terminates all running containers on the node** and disconnects kubelet from the container runtime. Kubelet will go inactive and the node will become `NotReady`.

After starting CRI-O, **always restart kubelet**:

```bash
sudo systemctl restart crio
sudo systemctl restart kubelet
```

Wait ~15 seconds, then verify the node returns to `Ready`:

```bash
oc get node <node-name>
```

This is why you must cordon/drain before restarting CRI-O. Without draining, all running workloads will be killed.

## Config Drop-ins

CRI-O reads additional configuration from `/etc/crio/crio.conf.d/`. Files are processed in lexicographic order; later files override earlier ones.

Example (setting a runtime option):

```bash
ssh core@${WORKER} "sudo tee /etc/crio/crio.conf.d/01-custom.conf <<'EOF'
[crio.runtime]
default_runtime = \"crun\"
EOF"

ssh core@${WORKER} "sudo systemctl restart crio && sudo systemctl restart kubelet"
```

## Verifying the Deployment

```bash
# Check version and build info
ssh core@${WORKER} "sudo crio --version"

# Check it is running
ssh core@${WORKER} "sudo systemctl is-active crio"

# Check kubelet is connected
ssh core@${WORKER} "sudo systemctl is-active kubelet"

# Check node status (from your workstation)
oc get node <node-name>

# Check CRI-O logs for errors
ssh core@${WORKER} "sudo journalctl -u crio --no-pager -n 20"
```

## Monitoring After Deployment

Watch for issues after uncordoning:

```bash
# Watch for CRI-O errors
ssh core@${WORKER} "sudo journalctl -u crio -f" &

# Watch pod events on this node
oc get events --field-selector involvedObject.kind=Node,involvedObject.name=<node-name> -w

# Verify pods can be scheduled and start
oc run test-pod --image=registry.access.redhat.com/ubi9/ubi-minimal:latest \
  --overrides='{"spec":{"nodeName":"<node-name>"}}' \
  --command -- sleep 30
oc get pod test-pod -w
oc delete pod test-pod
```

## CRI-O Rollback

Follow the standard rollback procedure in [rollback.md](rollback.md) with these values:

| Parameter | Value |
|-----------|-------|
| `<service>` | `crio` |
| `<original-path>` | `/usr/bin/crio` |
| `<dependent-service>` | `kubelet` |
| `<config-drop-in-path>` | `/etc/crio/crio.conf.d/01-custom.conf` (if created) |
| `<package-name>` | `cri-o` |
