# OLM Plugin

The OLM plugin provides commands for debugging and analyzing OLM (Operator Lifecycle Manager) issues in OpenShift clusters.

## Overview

This plugin helps developers and SREs troubleshoot OLM-related issues by automatically correlating must-gather logs with the appropriate OLM source code and searching for known bugs in Jira. It supports both OLMv0 and OLMv1 architectures and intelligently selects the correct code branch based on the OpenShift version.

## Commands

### `/olm:debug`

Debug OLM issues using must-gather logs and source code analysis.

**Usage:**
```
/olm:debug <issue-description> <must-gather-path> [olm-version]
```

**Arguments:**
- `issue-description`: Brief description of the OLM issue being investigated
- `must-gather-path`: Path to the must-gather log directory
- `olm-version`: (Optional) Either `olmv0` (default) or `olmv1`

**Examples:**

1. Debug a CSV stuck in pending state (OLMv0):
   ```
   /olm:debug "CSV stuck in pending state" /path/to/must-gather
   ```

2. Debug OLMv1 ClusterExtension issue:
   ```
   /olm:debug "ClusterExtension installation failing" /path/to/must-gather olmv1
   ```

3. Debug operator upgrade issue:
   ```
   /olm:debug "Operator upgrade from v1.0 to v2.0 fails with dependency resolution error" ~/Downloads/must-gather.local.123456 olmv0
   ```

## How It Works

The `olm:debug` command performs the following steps:

1. **Extracts OCP version** from the must-gather logs
2. **Clones appropriate repositories**:
   - OLMv0: `operator-framework-olm`
   - OLMv1: `operator-framework-operator-controller` and `cluster-olm-operator`
3. **Checks out the correct branch** matching the OCP version (e.g., `release-4.14`)
4. **Analyzes logs** to identify errors, warnings, and failed reconciliations
5. **Queries Jira** for known bugs in OCPBUGS project (OLM component) matching the OCP version
6. **Matches errors** with known bugs based on error messages and symptoms
7. **Correlates errors with source code** to identify root causes
8. **Generates a comprehensive analysis report** with recommendations and links to related Jira issues

## Output

The command creates a working directory at `.work/olm-debug/<timestamp>/` containing:

- `analysis.md`: Comprehensive analysis report with known bugs section
- `relevant-logs.txt`: Extracted relevant log entries
- `code-references.md`: Links to relevant source code
- `known-bugs.md`: List of potentially related Jira bugs with match confidence and workarounds
- `repos/`: Cloned repository directories

## Prerequisites

- `git` must be installed
- Network access to GitHub and Jira (https://issues.redhat.com/)
- Valid must-gather logs from an OpenShift cluster
- (Optional) Jira credentials for full access to bug details

## OLM Version Support

### OLMv0
- Used in OpenShift 4.x (traditional OLM)
- Repository: [operator-framework-olm](https://github.com/openshift/operator-framework-olm)
- Key resources: CSV, Subscription, InstallPlan

### OLMv1
- Next-generation OLM architecture
- Repositories:
  - [operator-framework-operator-controller](https://github.com/openshift/operator-framework-operator-controller)
  - [cluster-olm-operator](https://github.com/openshift/cluster-olm-operator)
- Key resources: ClusterExtension, Catalog

## Troubleshooting

**Issue**: Cannot determine OCP version from must-gather
- **Solution**: Manually specify the OCP version when prompted, or check that the must-gather is complete

**Issue**: Repository clone fails
- **Solution**: Check network connectivity and GitHub access. You can manually clone the repositories and point the command to them.

**Issue**: Branch not found for OCP version
- **Solution**: The command will fall back to the `main` branch. Be aware that there may be version differences.

**Issue**: Jira access fails or returns no results
- **Solution**: Check network connectivity to https://issues.redhat.com/. The command will continue with analysis even if Jira is unavailable. For full access, you may need to authenticate.

**Issue**: Too many potential bug matches returned
- **Solution**: Review the `known-bugs.md` file and focus on high-confidence matches. Verify each match by reading the full bug description in Jira.

## Resources

- [OLM Documentation](https://olm.operatorframework.io/)
- [OpenShift OLM Documentation](https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html)
- [Must-gather Documentation](https://docs.openshift.com/container-platform/latest/support/gathering-cluster-data.html)
- [OCPBUGS Jira Project](https://issues.redhat.com/projects/OCPBUGS/)
- [Jira REST API Documentation](https://docs.atlassian.com/jira-software/REST/latest/)

## Contributing

To add new commands to this plugin:

1. Create a new `.md` file in `plugins/olm/commands/`
2. Follow the command definition format in existing commands
3. Update this README with the new command documentation

## Support

For issues or feature requests, please file an issue at:
https://github.com/openshift-eng/ai-helpers/issues
