---
description: Generate must-gather from an OpenShift cluster
argument-hint: [image] [--dest-dir path]
---

## Name
must-gather:generate

## Synopsis
```
/must-gather:generate [image] [--dest-dir path]
```

## Description
The `must-gather:generate` command collects diagnostic information from an OpenShift cluster using the `oc adm must-gather` command. It gathers logs, resource definitions, and cluster state information useful for troubleshooting and support cases.

## Arguments
- `image` (optional): The must-gather image to use. If not specified, uses the default image for the cluster version.
- `--dest-dir` (optional): Destination directory for the must-gather output. Defaults to `/tmp/must-gather-$(date +%Y%m%d-%H%M%S)`

## Implementation

1. **Verify Prerequisites**
   - Check if `oc` CLI is installed: `which oc`
   - Verify cluster connection: `oc whoami`
   - If not connected, provide instructions to log in

2. **Determine Must-Gather Image**
   - If image argument provided, use it directly
   - Otherwise, get cluster version: `oc get clusterversion version -o jsonpath='{.status.desired.version}'`
   - Use default image: `registry.redhat.io/openshift4/ose-must-gather:v<version>`

3. **Prepare Output Directory**
   - If `--dest-dir` specified, use that path
   - Otherwise, create: `/tmp/must-gather-$(date +%Y%m%d-%H%M%S)`
   - Ensure directory exists: `mkdir -p <dest-dir>`
4. **Run Must-Gather**
   - Execute: `oc adm must-gather --dest-dir=<dest-dir> [--image=<image>]`
   - Display progress to user
   - This may take 5-10 minutes depending on cluster size

5. **Post-Collection**
   - Display location of collected data
   - Show size of collected data: `du -sh <dest-dir>`
   - Optionally offer to compress: `tar -czf must-gather-$(date +%Y%m%d-%H%M%S).tar.gz -C <dest-dir> .`
   - Ask if user wants to run `/must-gather:analyze` on the collected data

## Return Value

- **Success**: Path to the must-gather directory and summary of collected data
- **Failure**: Error message indicating what went wrong (not connected, insufficient permissions, etc.)

## Examples

1. **Generate must-gather with default image**:
   ```
   /must-gather:generate
   ```
   Output: Must-gather data saved to `/tmp/must-gather-20251215-143022/`

2. **Generate must-gather with specific image**:
   ```
   /must-gather:generate registry.redhat.io/openshift4/ose-must-gather:v4.14
   ```

3. **Generate must-gather to specific directory**:
   ```
   /must-gather:generate --dest-dir /tmp/my-must-gather
   ```

4. **Generate must-gather with custom image (e.g., network diagnostics)**:
   ```
   /must-gather:generate quay.io/openshift/origin-must-gather:latest
   ```

5. **Generate and then analyze**:
   ```
   /must-gather:generate
   ```
   (After completion, Claude will offer to run `/must-gather:analyze` on the collected data)

## Notes

- Must-gather collection requires cluster-admin or similar elevated permissions
- The operation creates a pod in the cluster that runs the collection process
- Some must-gather images collect specific subsystem data (network, storage, etc.)
- After collection completes, you can use `/must-gather:analyze` to analyze the data

## See Also

- `/must-gather:analyze` - Analyze collected must-gather data
- `oc adm must-gather --help` - For all available options
- OpenShift documentation: https://docs.openshift.com/container-platform/latest/support/gathering-cluster-data.html
