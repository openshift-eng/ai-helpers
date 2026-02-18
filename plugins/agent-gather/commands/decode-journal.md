---
description: Decode systemd journal export files to human-readable format
argument-hint: [path] [--service name] [--priority level]
---

## Name
agent-gather:decode-journal

## Synopsis
```
/agent-gather:decode-journal [path] [--service name] [--priority level]
```

## Description
The `agent-gather:decode-journal` command converts systemd journal export files (collected by agent-gather) into human-readable log format. Journal export files are in a binary format that requires conversion using `systemd-journal-remote` and `journalctl` tools.

## Arguments
- `path` (optional): Path to journal.export file or directory containing it. Defaults to current directory
- `--service` (optional): Filter logs by specific systemd service (e.g., `assisted-service`, `kubelet`)
- `--priority` (optional): Filter by log priority (emerg, alert, crit, err, warning, notice, info, debug)

## Implementation

1. **Verify Prerequisites**
   - Check if `systemd-journal-remote` is installed: `which systemd-journal-remote`
   - Check if `journalctl` is available: `which journalctl`
   - If not available on macOS/Windows, offer container-based solution

2. **Install Dependencies** (if needed)
   - On RHEL/CentOS/Fedora: `sudo dnf install systemd-journal-remote`
   - On Ubuntu/Debian: `sudo apt-get install systemd-journal-remote`
   - On macOS/Windows: Provide container command (see below)

3. **Locate journal.export File**
   - If path argument provided, use it
   - Otherwise, search current directory: `find . -name "journal.export" -type f`
   - If multiple files found, prompt user to select one
   - If none found, show error and suggest checking path

4. **Convert to Binary Journal Format**
   - Execute conversion:
     ```bash
     cat journal.export | systemd-journal-remote -o node-0.journal -
     ```
   - Verify output file created: `ls -lh node-0.journal`
   - Display file size to user

5. **Generate Human-Readable Output**
   - Basic conversion:
     ```bash
     journalctl --file node-0.journal > jnl.log
     ```
   - If `--service` specified:
     ```bash
     journalctl --file node-0.journal -u <service> > <service>.log
     ```
   - If `--priority` specified:
     ```bash
     journalctl --file node-0.journal --priority=<level> > priority-<level>.log
     ```

6. **Display Summary**
   - Show output file location and size
   - Display first 20 lines of output as preview
   - Show statistics (total entries, date range, etc.)
   - Offer to search for specific patterns or errors

7. **Container-based Workflow** (for macOS/Windows)
   - If systemd tools not available, automatically offer container solution:
     ```bash
     podman run -it --rm -v $(pwd):/data:Z registry.access.redhat.com/ubi9/ubi bash -c \
       "dnf install -y systemd-journal-remote && cd /data && \
        cat journal.export | systemd-journal-remote -o node-0.journal - && \
        journalctl --file node-0.journal > jnl.log"
     ```

## Return Value

- **Success**: Path to decoded log file and preview of contents
- **Failure**: Error message with troubleshooting steps

## Examples

1. **Decode journal from current directory**:
   ```
   /agent-gather:decode-journal
   ```
   Output:
   ```
   Found: ./agent-gather-extracted-192.168.1.100/journal.export
   Converting journal export to binary format...
   Generated: node-0.journal (12.5 MB)
   Creating human-readable log file...
   Generated: jnl.log (45.2 MB, 125,430 lines)

   Preview (first 20 lines):
   Dec 24 10:15:23 node-0 systemd[1]: Starting assisted-service...
   Dec 24 10:15:24 node-0 assisted-service[1234]: Starting server on :8090
   ...
   ```

2. **Decode specific journal file**:
   ```
   /agent-gather:decode-journal /tmp/agent-gather-extracted/journal.export
   ```

3. **Filter by service**:
   ```
   /agent-gather:decode-journal --service assisted-service
   ```
   Generates `assisted-service.log` with only logs from that service

4. **Filter by priority (errors only)**:
   ```
   /agent-gather:decode-journal --priority err
   ```
   Generates `priority-err.log` with only error-level messages and higher

5. **Combine filters**:
   ```
   /agent-gather:decode-journal --service kubelet --priority warning
   ```
   Shows only warning-level (and higher) messages from kubelet service

## Understanding Journal Export Format

The journal export format is systemd's serialization format:

- **Binary format**: Not directly human-readable
- **Text fields**: UTF-8 fields serialized as `field_name=value`
- **Binary fields**: Special encoding with size prefixes
- **Entry separation**: Double newlines between entries
- **Metadata**: Includes timestamps, cursor info, and other metadata

## Common Services to Filter

When using `--service`, these are commonly useful services:

| Service | Description |
|---------|-------------|
| `assisted-service` | Main installation orchestration service |
| `agent-tui` | Agent text-based UI logs |
| `kubelet` | Kubernetes node agent |
| `crio` | Container runtime |
| `NetworkManager` | Network configuration |
| `ironic` | Bare metal provisioning (if used) |
| `chronyd` | Time synchronization |

## Log Priority Levels

When using `--priority`, available levels (from highest to lowest):

| Level | Code | Description |
|-------|------|-------------|
| emerg | 0 | System is unusable |
| alert | 1 | Action must be taken immediately |
| crit | 2 | Critical conditions |
| err | 3 | Error conditions |
| warning | 4 | Warning conditions |
| notice | 5 | Normal but significant |
| info | 6 | Informational messages |
| debug | 7 | Debug-level messages |

**Note**: Specifying a priority shows that level and all higher priorities.

## Advanced Journalctl Queries

After decoding, you can use journalctl for advanced queries:

```bash
# View logs from specific time range
journalctl --file node-0.journal --since "2025-12-24 10:00:00" --until "2025-12-24 11:00:00"

# Follow logs (live tail simulation)
journalctl --file node-0.journal --no-pager | tail -f

# Export to JSON format
journalctl --file node-0.journal -o json-pretty > journal.json

# Show only kernel messages
journalctl --file node-0.journal -k

# Show boot messages
journalctl --file node-0.journal -b

# Reverse order (newest first)
journalctl --file node-0.journal -r

# Show with full timestamps
journalctl --file node-0.journal -o short-precise
```

## Troubleshooting

### systemd-journal-remote Not Found

**Error:**
```
-bash: systemd-journal-remote: command not found
```

**Solutions:**

**On Linux:**
```bash
# RHEL/CentOS/Fedora
sudo dnf install systemd-journal-remote

# Ubuntu/Debian
sudo apt-get install systemd-journal-remote
```

**On macOS/Windows:**
Use containerized approach:
```bash
podman run -it --rm -v $(pwd):/data:Z registry.access.redhat.com/ubi9/ubi bash
# Inside container:
dnf install -y systemd-journal-remote
cd /data
cat journal.export | systemd-journal-remote -o node-0.journal -
journalctl --file node-0.journal > jnl.log
exit
```

### journal.export Not Found

**Error:**
```
Error: journal.export file not found
```

**Solutions:**
- Verify you've extracted the agent-gather archive: `tar -xf agent-gather.tar.xz`
- Check if file exists: `find . -name "journal.export"`
- Ensure you ran `/agent-gather:collect` first
- Verify the agent-gather archive actually contains a journal export

### Corrupt or Invalid Journal Export

**Error:**
```
Failed to parse journal file
```

**Solutions:**
- Verify file integrity: `file journal.export`
- Check file size: `ls -lh journal.export` (should not be 0 bytes)
- Try extracting archive again
- Re-collect agent-gather data if file is corrupted

### Permission Denied

**Error:**
```
Permission denied: node-0.journal
```

**Solutions:**
- Check directory permissions: `ls -ld .`
- Ensure you have write access to current directory
- Try using sudo: `sudo journalctl --file node-0.journal > jnl.log`
- Change to a directory where you have write access

## Notes

- Journal decoding requires Linux with systemd (macOS/Windows users should use containers)
- The conversion process typically takes 10-30 seconds depending on journal size
- Decoded logs are usually 3-4x larger than the compressed export format
- Journal files preserve exact timestamps and metadata from the original system
- Multiple journal.export files can be decoded separately (one per node)

## Output Format Options

`journalctl` supports various output formats:

```bash
# Short format (default, syslog-style)
journalctl --file node-0.journal -o short

# Verbose format (all fields)
journalctl --file node-0.journal -o verbose

# JSON format (one entry per line)
journalctl --file node-0.journal -o json

# JSON pretty-printed
journalctl --file node-0.journal -o json-pretty

# Export format (original binary format)
journalctl --file node-0.journal -o export

# Cat format (message text only, no metadata)
journalctl --file node-0.journal -o cat
```

## See Also

- `/agent-gather:collect` - Collect agent-gather data from nodes
- `/agent-gather:analyze` - Analyze decoded logs for common issues
- [Systemd Journal Export Formats](https://systemd.io/JOURNAL_EXPORT_FORMATS/)
- `man journalctl` - Full journalctl documentation
- `man systemd-journal-remote` - systemd-journal-remote documentation
