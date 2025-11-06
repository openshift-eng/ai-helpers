---
description: Launch CAMGI (Cluster Autoscaler Must-Gather Inspector) web interface to analyze cluster autoscaler behavior
argument-hint: [must-gather-path|stop]
---

## Name
must-gather:camgi

## Synopsis
```
/must-gather:camgi [must-gather-path]
/must-gather:camgi stop
```

## Description

The `must-gather:camgi` command launches the CAMGI (Cluster Autoscaler Must-Gather Inspector) web-based tool to examine must-gather records and investigate cluster autoscaler behavior in OpenShift environments.

CAMGI is a specialized tool from the [okd-camgi project](https://github.com/elmiko/okd-camgi) that provides a web interface for analyzing:
- Cluster autoscaler configuration
- Autoscaler behavior and scaling decisions
- Scaling events and node group status
- Autoscaler-related issues and debugging

## Prerequisites

**Container Runtime:**

The command requires one of the following:
- **Podman** (recommended)
- **Docker**
- **Local install** (optional): `pip3 install okd-camgi --user`

**Must-Gather Data:**

Must-gather data with autoscaler information:
```
must-gather/
└── registry-ci-openshift-org-origin-...-sha256-<hash>/
    ├── cluster-scoped-resources/
    ├── namespaces/
    └── ...
```

**File Permissions:**

Must-gather files need read permissions for the container user. The launcher script will automatically detect and offer to fix permission issues.

## Error Handling

**Permission Errors:**

If container shows permission denied errors, the script will prompt:
```
Fix permissions now? (Y/n)
```

Press Y to allow the script to make files readable (`chmod -R a+r`). This is safe for must-gather data which should not contain secrets.

**Manual fix** (if needed):
```bash
chmod -R a+r /path/to/must-gather
```

**Port Already in Use:**

If port 8080 is occupied, stop existing CAMGI containers:
```bash
/must-gather:camgi stop
```

**Browser Doesn't Open:**

If the web interface is not accessible:
- The script opens http://127.0.0.1:8080 automatically
- If it doesn't open, manually navigate to http://127.0.0.1:8080
- Use 127.0.0.1 (IPv4) instead of localhost to avoid IPv6 compatibility issues

**SELinux Issues:**

The script uses `:Z` volume mount flag for automatic SELinux relabeling. No manual SELinux configuration needed.

## Implementation

The command performs the following steps:

1. **Determine Action**:
   - If argument is "stop", stop all running CAMGI containers
   - Otherwise, proceed with launching CAMGI

2. **Get Must-Gather Path**:
   - If path not provided as argument, ask the user
   - Accept either root must-gather directory or exact subdirectory
   - Script will auto-detect the subdirectory structure if needed

3. **Launch CAMGI**:
   Execute the CAMGI launcher script:
   ```bash
   /home/psundara/ws/src/github.com/openshift/must-gather/.claude-plugin/skills/must-gather-analyzer/scripts/run-camgi.sh <must-gather-path>
   ```

   The script will:
   - Auto-detect the must-gather subdirectory structure
   - Check file permissions and prompt to fix if necessary
   - Start CAMGI using containerized version (podman/docker) or local install
   - Open browser automatically at http://127.0.0.1:8080

4. **Inform User**:
   After launching, provide usage instructions and how to stop CAMGI

## Return Value

The command provides status information:

**On Successful Launch:**
```
CAMGI is now running!

The web interface should open automatically in your browser at:
http://127.0.0.1:8080

If the browser didn't open automatically, click the URL above.

Use CAMGI to:
- Examine cluster autoscaler configuration
- Investigate autoscaler behavior and decisions
- Review scaling events and node group status
- Debug autoscaler-related issues

To stop CAMGI when you're done:
Ctrl+C in this terminal, or run:
  /must-gather:camgi stop
```

**On Stop:**
```
Stopping all CAMGI containers...
CAMGI stopped successfully.
```

## Technical Details

**Container Command:**

```bash
podman run --rm -it -p 8080:8080 \
  -v /path/to/must-gather:/must-gather:Z \
  quay.io/elmiko/okd-camgi
```

**Key Flags:**
- `--rm`: Auto-remove container when stopped
- `-it`: Interactive terminal (Ctrl+C works)
- `-p 8080:8080`: Port mapping for web interface
- `-v path:/must-gather:Z`: Volume mount + SELinux relabeling
- No `--security-opt label=disable`: SELinux stays enabled

**Port:**
- CAMGI runs on port 8080
- Accessible at http://127.0.0.1:8080
- Uses IPv4 (127.0.0.1) to avoid IPv6 compatibility issues with rootless podman

**SELinux:**
- The `:Z` flag handles SELinux labeling automatically
- No security-opt disabling needed

## Examples

1. **Start CAMGI with path**:
   ```
   /must-gather:camgi /home/user/must-gather
   ```
   Launches CAMGI with the provided must-gather path and opens browser.

2. **Start CAMGI interactively**:
   ```
   /must-gather:camgi
   ```
   Asks for must-gather path, then launches CAMGI.

3. **Stop CAMGI**:
   ```
   /must-gather:camgi stop
   ```
   Stops all running CAMGI containers.

## Notes

- **Foreground Execution**: CAMGI runs in the foreground - use Ctrl+C to stop, or run the stop command
- **File Permissions**: Must-gather files need read permissions for the container user
- **IPv4 vs localhost**: Uses IPv4 (127.0.0.1) to avoid IPv6 compatibility issues with rootless podman
- **SELinux Friendly**: The `:Z` flag handles SELinux labeling automatically
- **No Installation Required**: Uses containerized version, no need to install okd-camgi locally
- **Container Cleanup**: The `--rm` flag ensures containers are automatically removed when stopped

## Additional Resources

- CAMGI GitHub: https://github.com/elmiko/okd-camgi
- CAMGI PyPI: https://pypi.org/project/okd-camgi/
- Launcher Script: `.claude-plugin/skills/must-gather-analyzer/scripts/run-camgi.sh`

## Arguments

- **$1** (must-gather-path|stop): Optional. Either:
  - Path to the must-gather directory (root or subdirectory)
  - The keyword "stop" to stop all running CAMGI containers
  - If not provided and not "stop", the user will be asked for the path
