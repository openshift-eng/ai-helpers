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

## Building the Binary

Derive everything from the cri-o checkout you are building — do not rely on
hardcoded lists, they go stale and can differ between release branches:

- **Build dependencies**: listed in [`install.md`](https://github.com/cri-o/cri-o/blob/main/install.md)
  ("Build and install CRI-O from source" section) in the checkout. Read the
  version of that file from the branch you are building, not from `main`.
- **Go version**: check `go.mod` in the checkout; use the matching
  `golang:<version>-bookworm` Docker image.
- **Build command**: `make bin/crio`. The Makefile auto-detects build tags
  based on available libraries (`BUILDTAGS` is a Makefile variable computed by
  `hack/*_tag.sh` probes, not a target) — verify the chosen tags in the
  `-tags "..."` portion of the build output, or after building with
  `bin/crio version` (BuildTags field).
- **Dynamic libraries**: after building, run `ldd bin/crio` and compare the
  sonames against `ldd /usr/bin/crio` on the target node. They must match —
  a missing soname on the node means a build dependency mismatch.

### Example Dockerfile (illustrative snapshot — verify against install.md)

```dockerfile
FROM --platform=linux/amd64 golang:1.23-bookworm

# Snapshot of build deps as of cri-o 1.33 — re-derive from install.md
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

Restarting CRI-O does **not** kill running containers: each container is
supervised by its own conmon process, which runs independently of the CRI-O
daemon, and CRI-O re-attaches to running containers on startup. Kubelet's CRI
connection drops briefly and re-establishes automatically. One side effect to
expect: a container whose liveness probe depends on the CRI socket (e.g. an
exec probe running `crictl`) can fail its probe during the restart window and
be restarted by kubelet — probe-driven, not CRI-O killing it.

After starting CRI-O, restart kubelet to ensure it cleanly re-establishes the
CRI connection:

```bash
sudo systemctl restart crio
sudo systemctl restart kubelet
```

Wait ~15 seconds, then verify the node returns to `Ready`:

```bash
oc get node <node-name>
```

Cordon/drain before the swap is still recommended — not because the restart
kills workloads (it does not), but because you are putting an untested debug
binary in charge of the node's containers: if it crashes or misbehaves, you do
not want production workloads on the node when it does.

### Restarting via `oc debug` (no SSH access)

If the cluster has no SSH/bastion access, run the restart through a node debug
pod, wrapping commands in `chroot /host`:

```bash
oc debug node/<node-name> -- chroot /host sh -c 'systemctl restart crio && systemctl restart kubelet'
```

Caveat: the debug pod is itself a container running on the node you are
restarting. A CRI-O restart does not kill running containers (they are held by
their conmon processes and CRI-O re-attaches on startup), so the session
usually survives — but if it does drop mid-sequence, the kubelet restart never
runs and the node stays `NotReady`. To make the sequence immune to the session
dying, detach it with `systemd-run`:

```bash
oc debug node/<node-name> -- chroot /host \
  systemd-run --unit=debug-restart sh -c 'systemctl restart crio && systemctl restart kubelet'
```

Then verify from your workstation with `oc get node <node-name>` and
`oc debug node/<node-name> -- chroot /host systemctl is-active crio kubelet`.

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

Follow the standard rollback procedure in the Rollback section of [deploy.md](deploy.md) with these values:

| Parameter | Value |
|-----------|-------|
| `<service>` | `crio` |
| `<original-path>` | `/usr/bin/crio` |
| `<dependent-service>` | `kubelet` |
| `<config-drop-in-path>` | `/etc/crio/crio.conf.d/01-custom.conf` (if created) |
| `<package-name>` | `cri-o` |
