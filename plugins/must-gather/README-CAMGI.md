# OKD-CAMGI Integration

Integration of [okd-camgi](https://github.com/elmiko/okd-camgi) (Cluster Autoscaler Must-Gather Inspector) for analyzing must-gather data.

## What is CAMGI?

CAMGI is a web-based tool for examining must-gather records to investigate cluster infrastructure and autoscaler behavior in OKD/OpenShift environments.

**CAMGI analyzes:**
- Cluster autoscaler configuration and behavior
- Autoscaler scaling decisions and events
- Cluster operators status and health
- Machines, MachineSets, and Nodes configuration
- Control Plane MachineSets
- Machine API operator status
- Machine Config operator status
- Cloud Controller Manager details
- Node group status and autoscaler-related issues

## Quick Start

```bash
./run-camgi.sh /path/to/must-gather
```

Or use the slash command from anywhere:
```
/must-gather:camgi /path/to/must-gather
```

The script will automatically:
1. Detect must-gather subdirectory structure
2. **Check and fix file permissions** (with your confirmation)
3. Start camgi (containerized or local install)
4. Open web interface at [http://127.0.0.1:8080](http://127.0.0.1:8080)

## Commands

### Start CAMGI
```bash
./run-camgi.sh <must-gather-path>
# Or
/must-gather:camgi <must-gather-path>
```

### Stop CAMGI
```bash
./run-camgi.sh stop
# Or
/must-gather:camgi stop
```

## Key Features

### ✅ Automatic Permission Fixing
- Detects restrictive file permissions
- Prompts: "Fix permissions now? (Y/n)"
- Runs `chmod -R a+r` with user confirmation
- No manual chmod needed!

### ✅ SELinux Compatible
- Uses `:Z` volume mount flag for proper SELinux labeling
- Works with SELinux in enforcing mode
- No security-opt disabling required

### ✅ Automatic Browser Opening
- Opens [http://127.0.0.1:8080](http://127.0.0.1:8080) automatically
- Uses IPv4 address (avoids IPv6 issues)

### ✅ Smart Container Management
- Auto-detects podman/docker
- Falls back to containerized version if camgi not installed locally
- Simple stop command cleans up all containers

### ✅ User-Friendly
- Clear colored output
- Helpful error messages
- Ctrl+C works properly

## Installation Methods

### Method 1: Containerized (Default)
No installation needed! The script automatically uses the container image.

**Prerequisites:**
- Podman or Docker

### Method 2: Local Install (Optional)
```bash
pip3 install okd-camgi --user
```

**Benefits:**
- Faster startup
- Uses `--webbrowser` flag
- No container overhead

## Technical Details

### Container Command
```bash
podman run --rm -it -p 8080:8080 \
  -v /path/to/must-gather:/must-gather:Z \
  quay.io/elmiko/okd-camgi
```

### Flags Explained
- `--rm` - Auto-remove container when stopped
- `-it` - Interactive terminal (Ctrl+C works)
- `-p 8080:8080` - Port mapping
- `-v path:/must-gather:Z` - Volume mount + SELinux relabeling
- **No** `--security-opt label=disable` - SELinux stays enabled!

### File Permissions
The script checks for restrictive permissions and offers to fix them.

**Manual fix (if needed):**
```bash
chmod -R a+r /path/to/must-gather
```

This is safe - must-gather data should not contain secrets.

## Troubleshooting

### Permission Errors
**Symptom:** `PermissionError: [Errno 13] Permission denied`

**Solution:** The script will prompt you to fix this. Press Y to allow automatic fixing.

**Manual fix:**
```bash
chmod -R a+r /path/to/must-gather
```

### Cannot Connect to Browser
**Symptom:** Browser can't access localhost:8080

**Solution:** Use http://127.0.0.1:8080 instead of localhost

This is due to IPv6 compatibility with rootless podman.

### Port Already in Use
**Symptom:** Port 8080 is occupied

**Solution:** Stop other containers or run manually with different port:
```bash
podman run --rm -it -p 9090:8080 \
  -v /path/to/must-gather:/must-gather:Z \
  quay.io/elmiko/okd-camgi
```

Then access at http://127.0.0.1:9090

### SELinux Denials
**Check status:**
```bash
getenforce
```

**View denials:**
```bash
sudo ausearch -m AVC -ts recent
```

The `:Z` flag should handle all SELinux labeling automatically.

## Files Included

1. **run-camgi.sh** - Main executable script
2. **README-CAMGI.md** - This documentation

## References

- CAMGI GitHub: https://github.com/elmiko/okd-camgi
- CAMGI on PyPI: https://pypi.org/project/okd-camgi/
- Must-Gather Documentation: https://docs.openshift.com/container-platform/latest/support/gathering-cluster-data.html

## Future Enhancements

- `--port` flag for custom port selection
- Support for tar.gz must-gather files
- `--no-browser` flag to skip automatic opening
- Custom container registry support
