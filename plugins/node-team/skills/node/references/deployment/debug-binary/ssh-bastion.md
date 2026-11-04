# SSH Bastion Access to RHCOS Nodes

RHCOS worker nodes are not directly accessible via SSH. The [ssh-bastion](https://github.com/eparis/ssh-bastion) project deploys a bastion pod that proxies SSH connections to cluster nodes.

## Setup

### 1. Deploy the Bastion

Use the deploy script from the upstream repo, pinned to a reviewed commit.
Never pipe an unpinned script from the network into a shell against a live
cluster. Download it, read it, show the user what it will create, and run it
only after they confirm:

```bash
# Pinned commit (master as of 2026-09-21). Re-pin deliberately, not implicitly.
BASTION_REF=8c73d4ec1872983a9ba41442bb38853387589c59
BASTION_RAW="https://raw.githubusercontent.com/eparis/ssh-bastion/${BASTION_REF}/deploy"

curl -fsSL -o /tmp/ssh-bastion-deploy.sh "${BASTION_RAW}/deploy.sh"
less /tmp/ssh-bastion-deploy.sh        # review before running

# BASEDIR makes the script fetch its manifests from the same pinned commit
BASEDIR="${BASTION_RAW}" bash /tmp/ssh-bastion-deploy.sh
```

The script creates the `openshift-ssh-bastion` namespace, generates the
`ssh-host-keys` secret, deploys the bastion pod behind a LoadBalancer service,
and prints the LoadBalancer IP. Applying only the YAML manifests by hand does
not work, because the namespace and the host key secret come from the script.

The bastion exposes SSH to the internet through a LoadBalancer. Use it on
development clusters only, and remove it when done:

```bash
oc delete namespace openshift-ssh-bastion
```

**LoadBalancer warm-up:** After deployment, the cloud LoadBalancer (especially on GCP) takes 30-60 seconds to become reachable. SSH connections will be refused during this period. Wait and retry; do not assume the bastion is broken.

```bash
sleep 30
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "core@${BASTION_HOST}" echo "connected"
```

### 2. Discover the SSH Key

The cluster's `99-worker-ssh` MachineConfig contains the authorized public key. Match it against your local keys:

```bash
# Get the public key baked into the nodes
oc get machineconfig 99-worker-ssh -o jsonpath='{.spec.config.passwd.users[0].sshAuthorizedKeys[0]}'

# Compare against local keys
for f in ~/.ssh/*.pub; do echo "=== $f ===" && cat "$f"; done
```

The matching key is what you need. Common gotcha: GCP clusters often use `~/.ssh/google_compute_engine`, not `~/.ssh/id_rsa`.

### 3. Get the Bastion Host

```bash
BASTION_HOST=$(oc get service --all-namespaces -l run=ssh-bastion \
  -o go-template='{{ with (index (index .items 0).status.loadBalancer.ingress 0) }}{{ or .hostname .ip }}{{end}}')
echo "Bastion: $BASTION_HOST"
```

## Running Commands

Use raw SSH with the proxy command. The upstream `ssh-bastion.sh` script appends `sudo -i` which makes it unsuitable for non-interactive command execution.

Define two wrappers once and use them for every command. The other
debug-binary references write `node_ssh` / `node_scp` and mean exactly these
functions. Shell functions do not persist between Bash tool calls, so define
them at the top of each invocation (or source them from a file):

```bash
SSH_KEY=~/.ssh/<matching-key>
BASTION_HOST=<from-above>
WORKER=<node-name>

NODE_SSH_OPTS=(-i "$SSH_KEY"
  -o StrictHostKeyChecking=accept-new
  -o ProxyCommand="ssh -i \"$SSH_KEY\" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -W %h:%p core@${BASTION_HOST}")

node_ssh() { ssh "${NODE_SSH_OPTS[@]}" "core@${WORKER}" "$@"; }
node_scp() { scp "${NODE_SSH_OPTS[@]}" "$@"; }

node_ssh "<command>"
```

Notes:

- No `-A`: `-W` only forwards a TCP stream, so agent forwarding is not needed.
  Forwarding your agent to a shared bastion would let anyone with root there
  use your keys.
- `StrictHostKeyChecking=accept-new` records host keys on first contact and
  refuses changed keys afterwards. Clusters are often recreated behind the
  same names; when a key legitimately changed, remove the stale entry with
  `ssh-keygen -R <host>` instead of disabling the check.

## SCP (Transferring Files)

Use the `node_scp` wrapper from above:

```bash
node_scp ./local-file "core@${WORKER}:/home/core/remote-file"
```

The upstream `scp.sh` script is also available but requires `SSH_KEY_PATH` to be set.

## Alternative: oc debug node

For a quick shell on a node without setting up the bastion:

```bash
oc debug node/<node-name>
chroot /host
```

This gives you a root shell on the node. Limitations:
- Cannot SCP files (no file transfer mechanism)
- Cannot run background processes reliably
- Session dies if the debug pod is evicted
- Runs as a pod, not a real SSH session

Use `oc debug node` for inspection. Use the SSH bastion for deployment workflows that need SCP.

## Writable Paths on RHCOS

RHCOS has an immutable rootfs. You can only write to:
- `/home/core/`: user home
- `/var/`: variable data
- `/etc/`: configuration (overlayed)
- `/tmp/`: temporary

Always SCP files to `/home/core/` first.

## Gotcha: SCP Fails on Bind-Mounted Files

If the target file is already bind-mounted (busy), SCP will fail with `Failure`. Copy to a new filename (e.g., `/home/core/binary-v2`), then swap after unmounting.

## Troubleshooting

### Bastion connectivity issues

If SSH connections are intermittently refused (`Connection refused` on port 22) after the bastion pod is running:

1. **Restart the bastion pod.** Deleting the pod lets the deployment recreate it:

```bash
oc delete pod -n openshift-ssh-bastion -l run=ssh-bastion
sleep 30
```

2. **Verify the pod is running and the LB has an IP:**

```bash
oc get pods -n openshift-ssh-bastion -o wide
oc get svc -n openshift-ssh-bastion ssh-bastion
```

3. **Re-fetch the bastion IP** (it should not change, but confirm):

```bash
BASTION_HOST=$(oc get service -n openshift-ssh-bastion ssh-bastion \
  -o go-template='{{ with (index .status.loadBalancer.ingress 0) }}{{ or .hostname .ip }}{{end}}')
```

### Permission denied

- Verify you are using the correct SSH key (see step 2 above)
- Verify you are connecting as user `core` (not `root`)
- Check that the SSH agent has the key loaded: `ssh-add -l`

### Connection timeout

- The node might not be reachable from the bastion network
- Verify the node internal IP: `oc get node <node> -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'`
- Check that the bastion pod is in the same VPC/network as the nodes
