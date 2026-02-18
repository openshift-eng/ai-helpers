---
description: Collect diagnostic data from agent-based installer nodes
argument-hint: <node-ip> [--output path] [--all-nodes]
---

## Name
agent-gather:collect

## Synopsis
```
/agent-gather:collect <node-ip> [--output path] [--all-nodes]
```

## Description
The `agent-gather:collect` command collects diagnostic information from OpenShift agent-based installer nodes using SSH. It gathers system journals, installation logs, and configuration data useful for troubleshooting installation failures that occur before the cluster API is available.

## Arguments
- `node-ip` (required): IP address of the rendezvous host or target node
- `--output` (optional): Destination directory for the agent-gather archive. Defaults to current directory
- `--all-nodes` (optional): Collect from all nodes (prompts for additional IPs)

## Implementation

1. **Verify Prerequisites**
   - Check if SSH is available: `which ssh`
   - Verify SSH connectivity to node: `ssh -o ConnectTimeout=5 core@<node-ip> echo "connected"`
   - If connection fails, provide troubleshooting steps (check network, SSH keys, etc.)

2. **Identify Rendezvous Host**
   - Explain that the rendezvous host is the temporary bootstrap node
   - It's typically one of the control plane nodes specified in `agent-config.yaml`
   - Ask user to confirm this is the correct node IP
   - If `--all-nodes` is specified, prompt for additional node IPs

3. **Collect Data from Node(s)**
   - For each node, execute:
     ```bash
     ssh core@<node-ip> agent-gather -O > agent-gather-<node-ip>.tar.xz
     ```
   - Display progress to user
   - Show file size after collection: `ls -lh agent-gather-<node-ip>.tar.xz`
   - This typically takes 1-2 minutes per node

4. **Extract Archive**
   - Create extraction directory: `mkdir -p agent-gather-extracted-<node-ip>`
   - Extract archive: `tar -xf agent-gather-<node-ip>.tar.xz -C agent-gather-extracted-<node-ip>/`
   - List extracted contents: `ls -lh agent-gather-extracted-<node-ip>/`

5. **Display Summary**
   - Show location of extracted data
   - List key files found (journal.export, log files, etc.)
   - Display archive size and extraction location
   - Suggest next steps:
     - `/agent-gather:decode-journal` to make journals readable
     - `/agent-gather:analyze` to search for common issues

6. **Handle Multiple Nodes** (if `--all-nodes` specified)
   - Collect from each node sequentially
   - Organize data in separate directories per node
   - Provide summary of all collections

## Return Value

- **Success**: Path to extracted agent-gather data and summary of contents
- **Failure**: Error message indicating what went wrong (SSH failure, command not found, etc.)

## Examples

1. **Collect from rendezvous host**:
   ```
   /agent-gather:collect 192.168.1.100
   ```
   Output:
   ```
   Connecting to 192.168.1.100...
   Running agent-gather...
   Collected 45MB of diagnostic data
   Archive saved to: agent-gather-192.168.1.100.tar.xz
   Extracted to: agent-gather-extracted-192.168.1.100/

   Next steps:
   - Run /agent-gather:decode-journal to decode system journals
   - Run /agent-gather:analyze to search for common issues
   ```

2. **Collect with specific output directory**:
   ```
   /agent-gather:collect 192.168.1.100 --output /tmp/diagnostics/
   ```

3. **Collect from multiple nodes**:
   ```
   /agent-gather:collect 192.168.1.100 --all-nodes
   ```
   The plugin will prompt:
   ```
   Enter additional node IPs (one per line, empty line to finish):
   ```
   User enters:
   ```
   192.168.1.101
   192.168.1.102

   ```

4. **Collect with SSH key specification**:
   ```
   /agent-gather:collect 192.168.1.100
   ```
   If default SSH key doesn't work, plugin will ask:
   ```
   SSH connection failed. Would you like to specify a custom SSH key path?
   ```

## SSH Key Configuration

If SSH connection fails, the plugin guides the user through:

1. **Check default SSH key**:
   ```bash
   ls -l ~/.ssh/id_rsa ~/.ssh/id_ed25519
   ```

2. **Test SSH connection**:
   ```bash
   ssh -v core@<node-ip>
   ```

3. **Use specific SSH key**:
   ```bash
   ssh -i /path/to/key core@<node-ip> agent-gather -O > agent-gather.tar.xz
   ```

4. **Add SSH key to agent** (if needed):
   ```bash
   eval $(ssh-agent)
   ssh-add /path/to/key
   ```

## Troubleshooting

### SSH Connection Refused
```
Error: Connection refused (port 22)
```
**Solutions**:
- Verify node IP: `ping <node-ip>`
- Check if node is booted and accessible
- Verify network connectivity from your machine
- Check firewall rules

### Permission Denied
```
Error: Permission denied (publickey)
```
**Solutions**:
- Verify SSH key is correct
- Check `~/.ssh/config` for host-specific settings
- Try: `ssh -i /path/to/key core@<node-ip>`
- Ensure the key was added during installation (via `sshKey` in `install-config.yaml`)

### agent-gather Command Not Found
```
Error: bash: agent-gather: command not found
```
**Solutions**:
- Verify you're connecting to the rendezvous host (not a random node)
- Check OpenShift version (agent-gather available in 4.12+)
- Confirm this is an agent-based installer deployment
- Try checking if the binary exists: `ssh core@<node-ip> ls -l /usr/local/bin/agent-gather`

### Disk Space Issues
```
Error: No space left on device
```
**Solutions**:
- Check available disk space: `df -h`
- Specify different output directory with more space
- Clean up old agent-gather archives

## Notes

- Agent-gather is only available on agent-based installer deployments (not IPI or UPI)
- The rendezvous host is typically the first control plane node listed in your configuration
- Collection typically generates 30-100MB of compressed data
- Data collection is read-only and doesn't affect the installation
- The agent-gather binary is located at `/usr/local/bin/agent-gather` on RHCOS nodes
- Sensitive data (pull secrets, passwords) is automatically redacted

## Data Collected

The agent-gather archive typically contains:

- `journal.export` - System journal logs in binary export format
- `assisted-service.log` - Assisted-installer service logs
- `agent-tui.log` - Agent text UI logs
- `db/` - Assisted-service database exports (cluster and host validation info)
- `etc/` - Configuration files and certificates
- `logs/` - Various service and system logs

## See Also

- `/agent-gather:decode-journal` - Decode journal export files to readable format
- `/agent-gather:analyze` - Analyze collected data for common issues
- [Agent-based Installer Documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/installing_an_on-premise_cluster_with_the_agent-based_installer/)
