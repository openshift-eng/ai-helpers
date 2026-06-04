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

## Step 6: Create Bind Mount

Stop the service, mount the new binary, start the service:

```bash
# Stop the service
ssh core@${WORKER} "sudo systemctl stop <service>"

# Bind mount the new binary over the original
ssh core@${WORKER} "sudo mount --bind /home/core/<binary> <original-path>"

# Start the service
ssh core@${WORKER} "sudo systemctl start <service>"
```

The bind mount shadows the original binary without modifying it. The original remains intact underneath.

## Step 7: Make Persistent (Optional)

The bind mount does not survive a reboot. To make it persistent, create a systemd drop-in that re-creates the mount before the service starts:

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

If you need to deploy a newer version and the bind mount is already in place:

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

For convenience, after preflight passes and SELinux is set:

```bash
oc adm cordon <node> && \
oc adm drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=120s && \
ssh core@${WORKER} "sudo systemctl stop <service> && \
  sudo mount --bind /home/core/<binary> <original-path> && \
  sudo systemctl start <service> && \
  sudo systemctl restart <dependent-service>" && \
oc adm uncordon <node>
```
