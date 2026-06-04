# SSH Bastion Access to RHCOS Nodes

RHCOS worker nodes are not directly accessible via SSH. The [ssh-bastion](https://github.com/eparis/ssh-bastion) project deploys a bastion pod that proxies SSH connections to cluster nodes.

## Setup

### 1. Deploy the Bastion

Use the deploy script from the upstream repo:

```bash
curl -sL https://raw.githubusercontent.com/eparis/ssh-bastion/master/deploy/deploy.sh | bash
```

The script creates the `openshift-ssh-bastion` namespace, deploys the bastion pod, and prints the LoadBalancer IP.

If the script is unavailable, apply the individual manifests:

```bash
for f in serviceaccount role clusterrole deployment service; do
  oc apply -f "https://raw.githubusercontent.com/eparis/ssh-bastion/master/deploy/${f}.yaml"
done
```

**LoadBalancer warm-up:** After deployment, the cloud LoadBalancer (especially on GCP) takes 30-60 seconds to become reachable. SSH connections will be refused during this period. Wait and retry -- do not assume the bastion is broken.

```bash
sleep 30
ssh -i $SSH_KEY -o ConnectTimeout=15 core@${BASTION_HOST} echo "connected"
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

```bash
SSH_KEY=~/.ssh/<matching-key>
BASTION_HOST=<from-above>
WORKER=<node-name>

ssh -i $SSH_KEY \
  -o StrictHostKeyChecking=no \
  -o ProxyCommand="ssh -i $SSH_KEY -A -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -W %h:%p core@${BASTION_HOST}" \
  core@${WORKER} "<command>"
```

## SCP (Transferring Files)

Use SCP with the same proxy command:

```bash
scp -i $SSH_KEY \
  -o StrictHostKeyChecking=no \
  -o ProxyCommand="ssh -i $SSH_KEY -A -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -W %h:%p core@${BASTION_HOST}" \
  ./local-file core@${WORKER}:/home/core/remote-file
```

The upstream [scp.sh](https://github.com/eparis/ssh-bastion/blob/master/scp.sh) script is also available but requires `SSH_KEY_PATH` to be set.

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
- `/home/core/` -- user home
- `/var/` -- variable data
- `/etc/` -- configuration (overlayed)
- `/tmp/` -- temporary

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
  -o go-template='{{ with (index (index .status.loadBalancer.ingress 0)) }}{{ or .hostname .ip }}{{end}}')
```

### Permission denied

- Verify you are using the correct SSH key (see step 2 above)
- Verify you are connecting as user `core` (not `root`)
- Check that the SSH agent has the key loaded: `ssh-add -l`

### Connection timeout

- The node might not be reachable from the bastion network
- Verify the node internal IP: `oc get node <node> -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'`
- Check that the bastion pod is in the same VPC/network as the nodes
