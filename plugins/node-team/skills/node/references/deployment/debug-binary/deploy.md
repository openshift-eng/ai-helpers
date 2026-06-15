# Deploying the Binary

This is the critical phase. Follow the steps in order. Do not skip the preflight check.

## Step 1: SCP Binary to Node

Transfer the cross-compiled binary to the node via the SSH bastion:

```bash
scp -i $SSH_KEY \
  -o StrictHostKeyChecking=no \
  -o ProxyCommand="ssh -i $SSH_KEY -A -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -W %h:%p core@${BASTION_HOST}" \
  ./bin/<binary> core@${WORKER}:/home/core/<binary>
```

Make it executable:

```bash
ssh core@${WORKER} "chmod +x /home/core/<binary>"
```

### No SSH access: transfer via a helper pod

`oc debug node/...` does **not** forward stdin (you get an empty file), and
`oc cp` requires `tar` inside the image. What works: a privileged pod on the
target node with `/var/home/core` hostPath-mounted, streaming the binary over
`oc exec -i`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: binary-copy-helper
  namespace: default
spec:
  nodeName: <node>
  restartPolicy: Never
  tolerations:
  - operator: Exists
  containers:
  - name: helper
    image: registry.access.redhat.com/ubi9/ubi-minimal:latest
    command: ["sleep", "600"]
    securityContext:
      privileged: true
      runAsUser: 0
    volumeMounts:
    - name: corehome
      mountPath: /host-home
  volumes:
  - name: corehome
    hostPath:
      path: /var/home/core
      type: Directory
```

```bash
oc wait --for=condition=Ready pod/binary-copy-helper -n default --timeout=120s

oc exec -i -n default binary-copy-helper -- sh -c 'cat > /host-home/<binary>' < ./bin/<binary>

# Verify integrity — compare against the local checksum
oc exec -n default binary-copy-helper -- sha256sum /host-home/<binary>

oc delete pod binary-copy-helper -n default
```

For the remaining steps, replace `ssh core@${WORKER} "<cmd>"` with
`oc debug node/<node> -- chroot /host sh -c '<cmd>'`.

## Step 2: Preflight Test

Verify the binary works before touching anything:

```bash
# Check libraries resolve
ssh core@${WORKER} "ldd /home/core/<binary>"

# Check it runs
ssh core@${WORKER} "/home/core/<binary> --version"
# or
ssh core@${WORKER} "/home/core/<binary> -h"
```

If `ldd` shows `not found` for any library, the binary was built against incompatible versions. Go back to the cross-compile step.

If `--version` fails, check the error -- it may be an architecture mismatch, missing library, or permissions issue.

## Step 3: Set SELinux Context

RHCOS runs SELinux in enforcing mode. Systemd checks the SELinux context of binaries before executing them. A binary in `/home/core/` has `user_home_t` context, which systemd will reject.

Copy the context from the original binary:

```bash
ssh core@${WORKER} "sudo chcon --reference=<original-path> /home/core/<binary>"
```

Verify:

```bash
ssh core@${WORKER} "ls -laZ /home/core/<binary> <original-path>"
```

Both should show the same context (e.g., `system_u:object_r:container_runtime_exec_t:s0` for CRI-O).

Without this step, systemd will fail with:
```text
Failed to locate executable <path>: Permission denied
```

## Step 4: Cordon Node

Prevent new pods from being scheduled:

```bash
oc adm cordon <node>
```

## Step 5: Drain Node

Evict existing workloads:

```bash
oc adm drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=120s
```

If drain times out on a stuck pod:

```bash
oc get pods --all-namespaces --field-selector spec.nodeName=<node> | grep Terminating
oc delete pod <pod> -n <namespace> --force --grace-period=0
```

## Step 6: Point the Service at the New Binary

Two methods. The systemd drop-in (Option A) is simpler — no service stop, the
original binary is never touched, and it persists across reboots. Use the bind
mount (Option B) when the unit file is awkward to override.

### Option A (recommended): systemd drop-in override

Inspect the unit first and copy the exact `ExecStart` line — the override must
replicate the original arguments exactly:

```bash
ssh core@${WORKER} "systemctl cat <service>"
```

Create a drop-in that clears `ExecStart` and re-points it at the new binary
(the empty `ExecStart=` line is required to clear the original):

```bash
ssh core@${WORKER} "sudo mkdir -p /etc/systemd/system/<service>.d"

ssh core@${WORKER} "sudo tee /etc/systemd/system/<service>.d/10-debug-binary.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/home/core/<binary> <original-args>
EOF"

ssh core@${WORKER} "sudo systemctl daemon-reload && sudo systemctl restart <service>"
```

This can be brittle if you skipped the preflight check (Step 2) or the
arguments do not match the original — the service will fail on restart, so
check `systemctl status <service>` immediately.

### Option B: bind mount

Stop the service, mount the new binary over the original, start the service:

```bash
# Stop the service
ssh core@${WORKER} "sudo systemctl stop <service>"

# Bind mount the new binary over the original
ssh core@${WORKER} "sudo mount --bind /home/core/<binary> <original-path>"

# Start the service
ssh core@${WORKER} "sudo systemctl start <service>"
```

The bind mount shadows the original binary without modifying it. The original remains intact underneath.

## Step 7: Make Persistent (Option B only)

The drop-in from Option A already persists across reboots. A bind mount does
not — if you used Option B, create a systemd drop-in that re-creates the mount
before the service starts:

```bash
ssh core@${WORKER} "sudo mkdir -p /etc/systemd/system/<service>.d"

ssh core@${WORKER} "sudo tee /etc/systemd/system/<service>.d/10-bind-mount.conf <<'EOF'
[Service]
ExecStartPre=/usr/bin/mount --bind /home/core/<binary> <original-path>
EOF"

ssh core@${WORKER} "sudo systemctl daemon-reload"
```

## Step 8: Restart Service and Dependents

Verify the service is running with the new binary:

```bash
# Check service status
ssh core@${WORKER} "sudo systemctl is-active <service>"

# Verify the new version
ssh core@${WORKER} "sudo <binary> --version"

# Restart dependent services (e.g., kubelet after CRI-O restart)
ssh core@${WORKER} "sudo systemctl restart <dependent-service>"
ssh core@${WORKER} "sudo systemctl is-active <dependent-service>"
```

Check the binary-specific reference (e.g., [crio.md](crio.md)) for which dependent services need restarting.

## Step 9: Verify Node Health

```bash
# Wait for the node to become Ready
oc get node <node>
```

If the node stays `NotReady`, check dependent services. A common issue is forgetting to restart kubelet after CRI-O restart.

## Step 10: Uncordon

```bash
oc adm uncordon <node>
```

## Optional: Config Drop-ins

To add configuration (e.g., feature flags), write a drop-in file and restart:

```bash
ssh core@${WORKER} "sudo tee <config-drop-in-path> <<'EOF'
<config-content>
EOF"

ssh core@${WORKER} "sudo systemctl restart <service>"
```

## Updating an Already-Deployed Binary

With Option A (drop-in), the original path was never shadowed, so updating is
just a swap-and-restart:

```bash
scp <new-binary> core@${WORKER}:/home/core/<binary>-v2

ssh core@${WORKER} "sudo systemctl stop <service> && \
  mv /home/core/<binary>-v2 /home/core/<binary> && \
  chmod +x /home/core/<binary> && \
  sudo chcon --reference=<original-path> /home/core/<binary> && \
  sudo systemctl start <service>"
```

With Option B, if you need to deploy a newer version and the bind mount is already in place:

1. SCP the new binary to a **different filename** (the mounted path is busy)
2. Stop the service
3. Unmount the old bind mount
4. Rename the new file to the expected name
5. Set SELinux context
6. Mount and start

```bash
scp <new-binary> core@${WORKER}:/home/core/<binary>-v2

ssh core@${WORKER} "sudo systemctl stop <service> && \
  sudo umount <original-path> && \
  mv /home/core/<binary>-v2 /home/core/<binary> && \
  chmod +x /home/core/<binary> && \
  sudo chcon --reference=<original-path> /home/core/<binary> && \
  sudo mount --bind /home/core/<binary> <original-path> && \
  sudo systemctl start <service>"
```

## Full Single-Command Deploy

For convenience, after preflight passes and SELinux is set (bind-mount method
shown; for the drop-in method, run the Option A commands between cordon and
uncordon instead):

```bash
oc adm cordon <node> && \
oc adm drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=120s && \
ssh core@${WORKER} "sudo systemctl stop <service> && \
  sudo mount --bind /home/core/<binary> <original-path> && \
  sudo systemctl start <service> && \
  sudo systemctl restart <dependent-service>" && \
oc adm uncordon <node>
```

## Rollback

Rollback is straightforward because neither method touched the original
binary. Cordon and drain first (as in Steps 4–5), then undo the override:

Remove **only the drop-in files you created** — on RHCOS,
`/etc/systemd/system/<service>.d/` also contains MCO-shipped drop-ins
(e.g. `10-mco-default-env.conf` for crio); deleting the whole directory
breaks the node's managed configuration.

**Option A (drop-in):**

```bash
ssh core@${WORKER} "sudo rm -f /etc/systemd/system/<service>.d/10-debug-binary.conf && \
  sudo systemctl daemon-reload && \
  sudo systemctl restart <service>"
```

**Option B (bind mount):**

```bash
ssh core@${WORKER} "sudo systemctl stop <service> && \
  sudo umount <original-path> && \
  sudo rm -f /etc/systemd/system/<service>.d/10-bind-mount.conf && \
  sudo systemctl daemon-reload && \
  sudo systemctl start <service>"
```

Then for either option:

```bash
# Remove any config drop-ins you added
ssh core@${WORKER} "sudo rm -f <config-drop-in-path>"

# Restart dependent services and verify the original version is back
ssh core@${WORKER} "sudo systemctl restart <dependent-service>"
ssh core@${WORKER} "sudo <binary> --version"

# Verify node health, then uncordon
oc get node <node>
oc adm uncordon <node>
```

The debug binary remains at `/home/core/<binary>`; remove it if no longer
needed.

### Rollback troubleshooting

- **Unmount fails with "target is busy"** — the service is still using the
  binary. Stop it first (`sudo systemctl stop <service>`), retry the umount,
  and if still busy check `sudo fuser -v <original-path>`.
- **Service will not start after rollback** — verify the unmount actually
  happened (`mount | grep <original-path>`), verify the original binary is
  intact (`rpm -V <package-name>`), and restore its SELinux context
  (`sudo restorecon <original-path>`). Then check
  `sudo journalctl -u <service> -n 50`.
