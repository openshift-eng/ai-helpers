# Rollback

Rollback is straightforward because the bind mount never touched the original binary. The original is intact underneath the mount.

## Procedure

### Step 1: Cordon and Drain

```bash
oc adm cordon <node>
oc adm drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=120s
```

### Step 2: Stop Service and Unmount

```bash
# Stop the service
ssh core@${WORKER} "sudo systemctl stop <service>"

# Unmount the bind mount (restores original binary)
ssh core@${WORKER} "sudo umount <original-path>"
```

### Step 3: Remove Systemd Drop-ins

If you created a systemd drop-in to persist the mount across reboots, remove it:

```bash
ssh core@${WORKER} "sudo rm -rf /etc/systemd/system/<service>.d"
ssh core@${WORKER} "sudo systemctl daemon-reload"
```

### Step 4: Remove Config Drop-ins

If you added any configuration drop-in files:

```bash
ssh core@${WORKER} "sudo rm -f <config-drop-in-path>"
```

### Step 5: Start Service and Dependents

```bash
# Start the service (now using the original binary)
ssh core@${WORKER} "sudo systemctl start <service>"

# Restart dependent services
ssh core@${WORKER} "sudo systemctl restart <dependent-service>"

# Verify original version
ssh core@${WORKER} "sudo <binary> --version"
```

### Step 6: Verify Node Health

```bash
oc get node <node>
```

Wait for `Ready` status. If the node does not recover, check service logs:

```bash
ssh core@${WORKER} "sudo journalctl -u <service> --no-pager -n 30"
```

### Step 7: Uncordon

```bash
oc adm uncordon <node>
```

## Quick Rollback (Single Command)

For when you need to rollback fast:

```bash
oc adm cordon <node> && \
oc adm drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=120s && \
ssh core@${WORKER} "sudo systemctl stop <service> && \
  sudo umount <original-path> && \
  sudo rm -rf /etc/systemd/system/<service>.d && \
  sudo rm -f <config-drop-in-path> && \
  sudo systemctl daemon-reload && \
  sudo systemctl start <service> && \
  sudo systemctl restart <dependent-service>" && \
oc adm uncordon <node>
```

## Cleanup

The debug binary remains at `/home/core/<binary>` after unmounting. Remove it if no longer needed:

```bash
ssh core@${WORKER} "rm /home/core/<binary>"
```

## Troubleshooting

### Service will not start after rollback

This should not happen since the original binary is untouched, but if it does:

1. **Verify the unmount happened:**
   ```bash
   ssh core@${WORKER} "mount | grep <original-path>"
   ```
   If it still shows a bind mount, run `sudo umount <original-path>` again.

2. **Verify the original binary is intact:**
   ```bash
   ssh core@${WORKER} "rpm -V <package-name>"
   ```

3. **Restore SELinux context on the original:**
   ```bash
   ssh core@${WORKER} "sudo restorecon <original-path>"
   ```

4. **Check logs:**
   ```bash
   ssh core@${WORKER} "sudo journalctl -u <service> -n 50"
   ```

### Unmount fails with "target is busy"

The service is still using the binary. Stop it first:

```bash
ssh core@${WORKER} "sudo systemctl stop <service>"
ssh core@${WORKER} "sudo umount <original-path>"
```

If it is still busy, check for other processes using it:

```bash
ssh core@${WORKER} "sudo fuser -v <original-path>"
```
