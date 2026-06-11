# Deploying Debug Binaries to RHCOS Nodes

Deploy a custom-built binary (CRI-O, crun, kubelet, etc.) to an OpenShift worker node running RHCOS for debugging or POC testing.

## The Challenge

RHCOS (Red Hat Enterprise Linux CoreOS) has an **immutable `/usr` filesystem**. You cannot overwrite `/usr/bin/crio` or any other system binary directly. There is no package manager (`dnf`/`yum`), no compiler toolchain, and no development headers on the node.

## The Solution

**Bind-mount** your custom binary over the original. The bind mount shadows the original file without modifying the rootfs. The original binary remains intact underneath and is instantly recoverable by unmounting.

```bash
mount --bind /home/core/crio /usr/bin/crio
```

For cluster-wide deployment that survives reboots, use layered images instead (see the comparison below).

## Four Phases

### Phase 1: Build (Cross-Compile)

Cross-compile the binary for `linux/amd64` using a Docker container that matches the target OS libraries. The binary must be dynamically linked against compatible library versions (same sonames as RHCOS).

See [debug-binary/cross-compile.md](debug-binary/cross-compile.md)

### Phase 2: Access (SSH Bastion)

Reach the worker node via an SSH bastion pod. RHCOS nodes are not directly accessible from outside the cluster. You need to discover the SSH key used at cluster install time and deploy a bastion DaemonSet.

See [debug-binary/ssh-bastion.md](debug-binary/ssh-bastion.md)

### Phase 3: Deploy (Bind Mount)

Transfer the binary to the node, verify it works, cordon/drain the node, set SELinux context, point the service at the new binary (systemd drop-in override or bind mount), restart the service. This phase has the most gotchas around SELinux, systemd, and service dependencies.

See [debug-binary/deploy.md](debug-binary/deploy.md)

### Phase 4: Rollback

Remove the drop-in (or unmount the bind mount), remove any config drop-ins, restart the service. The original binary is untouched.

See the Rollback section in [debug-binary/deploy.md](debug-binary/deploy.md)

## Binary-Specific References

Each binary has its own reference with build dependencies, systemd units, and deployment details:

- **CRI-O**: [debug-binary/crio.md](debug-binary/crio.md) -- build tags, library deps, kubelet restart, config drop-ins

## Safety Rules

These are non-negotiable. Skipping any of these can take a node out of the cluster.

1. **Verify SSH bastion connectivity first.** Before building or deploying anything, confirm you can reach the target worker node via the bastion. Run `uname -a` over SSH. If you cannot reach the node, nothing else matters.

2. **Always preflight-test the binary** before deploying. SCP it to `/home/core/`, run `ldd` to verify libraries resolve, and run `<binary> --version` to confirm it loads. If either fails, do not proceed.

3. **Always cordon and drain first.** Never restart a container runtime on a node with running workloads.

4. **Always test on ONE worker node.** Keep at least one healthy worker to maintain cluster capacity.

5. **Always set the SELinux context** before bind-mounting:
   ```bash
   sudo chcon --reference=/usr/bin/<original> /home/core/<binary>
   ```
   Without the correct context (e.g., `container_runtime_exec_t` for CRI-O), systemd will refuse to execute the binary with `Permission denied`.

6. **Know how to rollback before you deploy.** The rollback is: remove the drop-in (or unmount), restart service. Read the Rollback section in [debug-binary/deploy.md](debug-binary/deploy.md) before starting.

## Quick Reference

| Step | Command |
|------|---------|
| Check node OS | `oc get nodes -o wide` |
| Check current binary version | SSH in, `<binary> --version` |
| Cordon node | `oc adm cordon <node>` |
| Drain node | `oc adm drain <node> --ignore-daemonsets --delete-emptydir-data` |
| Uncordon node | `oc adm uncordon <node>` |
| Verify node health | `oc get node <node>` (wait for Ready) |
| Check bind mounts | `ssh core@<node> "mount \| grep /usr/bin"` |

## Deciding: Bind Mount vs Layered Image

| | Bind Mount | Layered Image |
|---|---|---|
| Scope | Single node | All nodes in a pool |
| Survives reboot | No (unless systemd drop-in) | Yes |
| Speed | Minutes | 30-60 min (MCO rollout) |
| Use case | Quick debug/test | Cluster-wide validation, customer simulation |
| Rollback | `umount` | Delete MachineConfig |

Use bind mounts for quick single-node testing. Use layered images when you need the binary on all nodes or need it to persist across reboots.

## Workflow Diagram

```text
Local Machine                    RHCOS Worker Node
─────────────                    ─────────────────
1. Cross-compile in Docker       
   (linux/amd64, matching libs)  
          │                      
2. SCP via bastion ─────────────► /home/core/<binary>
                                 3. ldd, --version (preflight)
                                 4. chcon (SELinux)
          │                      
   oc adm cordon/drain           
                                 5. mount --bind
                                 6. systemctl restart
          │                      
   oc adm uncordon               
                                 7. Verify: --version, node Ready
```
