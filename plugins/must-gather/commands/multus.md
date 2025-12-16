---
description: Analyze Multus CNI configuration and multi-networked pods from must-gather data
argument-hint: [must-gather-path] [output-html-path]
---

## Name
must-gather:multus

## Synopsis
```
/must-gather:multus [must-gather-path] [output-html-path]
```

## Description

The `multus` command analyzes Multus CNI (Container Network Interface) configuration and multi-networked pods from must-gather data. It generates a comprehensive HTML report showing cluster health, Multus infrastructure status, NetworkAttachmentDefinitions (NADs), and pods using additional network interfaces.

**What it analyzes:**
- **Cluster Information**: Version, platform, network type, and node status
- **Cluster Health**: Operator status and overall cluster health assessment
- **Multus Infrastructure**: DaemonSets, Deployments, and pod status
- **CNI Configuration**: Configuration files, binaries, and Multus daemon settings
- **NetworkAttachmentDefinitions (NADs)**: Available network attachment definitions across namespaces
- **Multi-Networked Pods**: Pods with additional network interfaces and their configurations
- **Network Topology**: Visual representation of network architecture

**Output:**
1. **HTML Summary Report**: A detailed, visually polished HTML report with tabs for different analysis sections
2. **Failure Analysis**: A separate text-based failure analysis highlighting detected issues

The HTML report uses the same styling and layout as the OpenShift Multus Summary template, providing a consistent and professional presentation of the analysis results.

## Prerequisites

**Required Tools:**
- Python 3.6 or later with `pyyaml` module
  - Check with: `python3 --version`
  - Install pyyaml: `pip3 install pyyaml`

**Analysis Script:**
The script is bundled with this plugin:
```
<plugin-root>/skills/must-gather-analyzer/scripts/analyze_multus.py
```

Where `<plugin-root>` is the directory where this plugin is installed (typically `~/.cursor/commands/ai-helpers/plugins/must-gather/` or similar).

Claude will automatically locate it by searching for the script in the plugin installation directory.

## Implementation

The command performs the following steps:

1. **Locate Analysis Script**:
   ```bash
   SCRIPT_PATH=$(find ~ -name "analyze_multus.py" -path "*/must-gather/skills/must-gather-analyzer/scripts/*" 2>/dev/null | head -1)
   
   if [ -z "$SCRIPT_PATH" ]; then
       echo "ERROR: analyze_multus.py script not found."
       echo "Please ensure the must-gather plugin from ai-helpers is properly installed."
       exit 1
   fi
   ```

2. **Extract Must-Gather Archive** (if needed):
   - If the must-gather path is a `.tar` file, extract it to a temporary directory
   - Locate the extracted must-gather directory structure

3. **Analyze Cluster Information**:
   - Parse `cluster-scoped-resources/config.openshift.io/clusterversions/*.yaml` for cluster version
   - Parse `cluster-scoped-resources/core/nodes/*.yaml` for node information
   - Parse `cluster-scoped-resources/config.openshift.io/networks.yaml` for network configuration

4. **Analyze Cluster Health**:
   - Parse `cluster-scoped-resources/config.openshift.io/clusteroperators/*.yaml` for operator status
   - Determine overall cluster health based on operator conditions

5. **Analyze Multus Infrastructure**:
   - Parse `namespaces/openshift-multus/apps/daemonsets/*.yaml` for DaemonSet status
   - Parse `namespaces/openshift-multus/apps/deployments/*.yaml` for Deployment status
   - Parse `namespaces/openshift-multus/pods/*/*.yaml` for pod status and details

6. **Analyze CNI Configuration**:
   - Extract CNI configuration details from Multus DaemonSet and Deployment specs
   - Document CNI binary locations and configuration directories

7. **Analyze NetworkAttachmentDefinitions**:
   - Parse `cluster-scoped-resources/k8s.cni.cncf.io/network-attachment-definitions/*.yaml`
   - Parse namespace-scoped NADs from `namespaces/*/k8s.cni.cncf.io/network-attachment-definitions/*.yaml`
   - Extract NAD specifications including CNI type, IPAM configuration, and network parameters

8. **Analyze Multi-Networked Pods**:
   - Search for pods with `k8s.v1.cni.cncf.io/networks` annotation
   - Extract network interface details and IP addresses
   - Correlate pods with their NetworkAttachmentDefinitions

9. **Generate Failure Analysis**:
   - Identify pods in non-Running state
   - Detect DaemonSets or Deployments with unavailable replicas
   - Flag missing or misconfigured NetworkAttachmentDefinitions
   - Report pods with network attachment errors

10. **Generate HTML Report**:
    - Create a comprehensive HTML report using the template styling
    - Include all analysis sections with tabs for easy navigation
    - Add interactive elements and visual indicators for health status

## Return Value

The command generates two output files:

1. **HTML Summary Report** (specified by `output-html-path`):
   - Format: HTML with embedded CSS and JavaScript
   - Sections: Cluster Information, Cluster Health, Multus CNI Summary, NetworkAttachmentDefinitions, Multi-Networked Pods, Topology Diagram
   - Interactive tabs for easy navigation

2. **Failure Analysis** (same directory as HTML report, with `.failure-analysis.txt` suffix):
   - Format: Plain text
   - Content: List of detected issues with severity, impact, and recommendations

**Example Output Structure:**
```
/path/to/output/
├── MULTUS_ANALYSIS_REPORT.html       # Main HTML report
└── MULTUS_ANALYSIS_REPORT.failure-analysis.txt  # Failure analysis
```

## Examples

1. **Analyze must-gather and generate report**:
   ```
   /must-gather:multus /path/to/must-gather.tar /path/to/output/report.html
   ```
   Analyzes the must-gather archive and generates an HTML report at the specified location.

2. **Analyze extracted must-gather directory**:
   ```
   /must-gather:multus /path/to/extracted-must-gather/ /path/to/output/multus-report.html
   ```
   Analyzes an already-extracted must-gather directory.

3. **Analyze Prow CI job must-gather**:
   ```
   /must-gather:multus /path/to/prow-job/gather-must-gather/artifacts/must-gather.tar /path/to/analysis.html
   ```
   Analyzes must-gather data from a Prow CI job.

4. **Interactive usage without arguments**:
   ```
   /must-gather:multus
   ```
   The command will prompt for the must-gather path and output HTML path.

## Error Handling

**Missing Python or pyyaml:**
```
Error: Python 3 not found or pyyaml module not installed.
Please install Python 3 and run: pip3 install pyyaml
```
Solution: Install Python 3 and the pyyaml module.

**Invalid must-gather path:**
```
Error: Must-gather path not found: /path/to/must-gather
```
Solution: Verify the path exists and is accessible.

**Missing Multus namespace:**
```
Warning: openshift-multus namespace not found in must-gather.
This cluster may not have Multus CNI installed.
```
Solution: Verify the cluster has Multus CNI installed, or the must-gather was collected correctly.

**Cannot write output file:**
```
Error: Cannot write to output path: /path/to/output.html
Permission denied
```
Solution: Ensure the output directory exists and is writable.

## Notes

- **Must-Gather Structure**: The command expects standard OpenShift must-gather directory structure
- **Multus Namespace**: Analyzes resources in the `openshift-multus` namespace
- **NetworkAttachmentDefinitions**: Searches both cluster-scoped and namespace-scoped NADs
- **Multi-Networked Pods**: Identifies pods by the `k8s.v1.cni.cncf.io/networks` annotation
- **HTML Template**: Uses the same styling as the reference OpenShift Multus Summary template
- **Failure Analysis**: Automatically generated alongside the HTML report
- **Performance**: Analysis time depends on must-gather size (typically 10-60 seconds)

## Use Cases

1. **Troubleshoot Multus CNI Issues**:
   - Verify Multus infrastructure is healthy
   - Check DaemonSet and Deployment status
   - Identify pods with network attachment errors

2. **Audit NetworkAttachmentDefinitions**:
   - List all available NADs across namespaces
   - Review NAD configurations and CNI types
   - Identify unused or misconfigured NADs

3. **Analyze Multi-Networked Pods**:
   - Find pods using additional network interfaces
   - Verify network attachment configurations
   - Check IP address assignments

4. **Generate Documentation**:
   - Create a comprehensive report of Multus configuration
   - Document network topology and architecture
   - Share analysis results with team members

5. **Post-Mortem Analysis**:
   - Analyze must-gather data from failed CI jobs
   - Identify root causes of networking issues
   - Generate detailed failure analysis reports

## Arguments

- **$1** (must-gather-path): Required. Path to the must-gather directory or `.tar` archive. Can be a Prow CI job path or a local must-gather collection.
- **$2** (output-html-path): Required. Path where the HTML report will be generated. The failure analysis will be created in the same directory with a `.failure-analysis.txt` suffix.

