---
description: Debug OLM issues using must-gather logs and source code analysis
argument-hint: <issue-description> <must-gather-path> [olm-version]
---

## Name
olm:debug

## Synopsis
```
/olm:debug <issue-description> <must-gather-path> [olm-version]
```

## Description
The `olm:debug` command analyzes OLM (Operator Lifecycle Manager) issues by correlating must-gather logs with the appropriate OLM source code. It automatically determines the OCP version from the must-gather logs, checks out the corresponding branch from the relevant OLM repositories, queries Jira for known bugs in the OCPBUGS project (OLM component), and provides detailed analysis and debugging insights.

## Arguments
- **$1** (required): Issue description - A brief description of the OLM issue being investigated
- **$2** (required): Must-gather path - Absolute or relative path to the must-gather log directory
- **$3** (optional): OLM version - Either `olmv0` (default) or `olmv1`
  - `olmv0`: Uses operator-framework-olm repository
  - `olmv1`: Uses operator-framework-operator-controller and cluster-olm-operator repositories

## Implementation

### Phase 1: Environment Setup and Validation

1. **Validate arguments**
   - Check that issue description is provided
   - Verify must-gather path exists and is accessible
   - Set OLM version to `olmv0` if not specified

2. **Parse must-gather logs to determine OCP version**
   - Look for version information in must-gather logs
   - Common locations:
     - `cluster-scoped-resources/core/nodes/*.yaml` - check node annotations
     - `cluster-scoped-resources/config.openshift.io/clusterversions/*.yaml`
   - Extract OCP version (e.g., `4.14`, `4.15`, `4.16`)
   - Determine corresponding branch name (e.g., `release-4.14`)

3. **Create working directory**
   - Use `.work/olm-debug/<timestamp>/` for temporary files
   - Create subdirectories: `repos/`, `analysis/`, `logs/`

### Phase 2: Repository Setup

4. **Clone appropriate repositories based on OLM version**

   **For olmv0:**
   - Clone `https://github.com/openshift/operator-framework-olm.git`
   - Checkout branch `release-<ocp-version>` (e.g., `release-4.14`)
   - If branch doesn't exist, try `main` or `master` branch

   **For olmv1:**
   - Clone `https://github.com/openshift/operator-framework-operator-controller.git`
   - Clone `https://github.com/openshift/cluster-olm-operator.git`
   - For each repo, checkout branch `release-<ocp-version>`
   - If branch doesn't exist, try `main` or `master` branch

5. **Verify repository setup**
   - Confirm branches are checked out successfully
   - List key directories to understand codebase structure

### Phase 3: Log Analysis

6. **Extract relevant OLM logs from must-gather**
   - For olmv0, look for:
     - `namespaces/openshift-operator-lifecycle-manager/` logs
     - OLM operator logs: `pods/catalog-operator-*/`, `pods/olm-operator-*/`
     - CSV (ClusterServiceVersion) resources
     - Subscription resources
     - InstallPlan resources
   - For olmv1, look for:
     - `namespaces/openshift-operator-controller/` logs
     - Operator controller logs
     - ClusterExtension resources
     - Catalog resources

7. **Identify error patterns and relevant logs**
   - Search for ERROR, WARN, FATAL level logs
   - Extract stack traces
   - Identify failed reconciliations
   - Note timestamps of issues

### Phase 4: Known Bug Search in Jira

8. **Query Jira for known OLM bugs**
   - Search OCPBUGS project with component "olm"
   - Use Jira REST API or web scraping to fetch bugs
   - Query parameters:
     - Project: `OCPBUGS`
     - Component: `olm`
     - Affects Version: Matches the OCP version (e.g., `4.14.0`, `4.15.0`)
     - Status: Open, In Progress, or Recently Resolved
   - API endpoint example:
     ```
     https://issues.redhat.com/rest/api/2/search?jql=project=OCPBUGS AND component=olm AND affectedVersion~"4.14"
     ```

9. **Match errors with known bugs**
   - Extract error messages and keywords from logs
   - Search for matching patterns in Jira bug summaries and descriptions
   - Look for similar symptoms in bug reports
   - Identify potential matches based on:
     - Error message similarity
     - Affected OCP version
     - Component affected (catalog-operator, olm-operator, etc.)
     - Symptom descriptions

10. **Categorize and prioritize matches**
    - High priority: Exact error message match with same OCP version
    - Medium priority: Similar symptoms with same component
    - Low priority: Related issues in same version range
    - Note bugs that have patches or workarounds available

### Phase 5: Code Correlation

11. **Map errors to source code**
    - Search cloned repositories for:
      - Error messages found in logs
      - Function names from stack traces
      - Related controllers and reconcilers
    - Use grep/ripgrep to find relevant code sections

12. **Analyze relevant code sections**
    - Read the source code around identified errors
    - Understand the reconciliation logic
    - Identify potential root causes

### Phase 6: Analysis and Recommendations

13. **Generate detailed analysis report**
    - Summary of the issue
    - OCP and OLM version information
    - Timeline of events from logs
    - Known bugs section with Jira links
    - Relevant code sections with explanations
    - Potential root causes
    - Recommended debugging steps
    - Suggested fixes or workarounds

14. **Create output files**
    - `analysis.md`: Detailed analysis report
    - `relevant-logs.txt`: Extracted relevant log entries
    - `code-references.md`: Links to relevant source code sections with line numbers
    - `known-bugs.md`: List of potentially related Jira bugs with match confidence

### Error Handling

- **Must-gather path not found**: Provide clear error message with expected path format
- **Unable to determine OCP version**: Ask user to provide OCP version manually
- **Repository clone failures**: Check network connectivity, provide manual clone instructions
- **Branch not found**: Fall back to main/master branch and warn user about version mismatch
- **No relevant logs found**: Provide guidance on what logs to look for manually
- **Jira access failures**: Continue with analysis if Jira is unavailable; note in report that known bug search was skipped
- **Jira authentication required**: Provide instructions for setting up Jira credentials if needed

## Return Value

The command generates the following outputs in `.work/olm-debug/<timestamp>/`:

- **analysis.md**: Comprehensive analysis report including:
  - Issue summary
  - Version information (OCP, OLM)
  - Log analysis with timeline
  - Known bugs section with links to matching Jira issues
  - Code correlation and root cause analysis
  - Recommendations

- **relevant-logs.txt**: Extracted relevant log entries from must-gather

- **code-references.md**: Links to relevant source code files with line numbers

- **known-bugs.md**: List of potentially related Jira bugs including:
  - Bug ID and link (e.g., OCPBUGS-12345)
  - Bug summary and status
  - Match confidence (High/Medium/Low)
  - Affected versions
  - Available workarounds or patches

- **repos/**: Cloned repository directories for further manual investigation

## Examples

1. **Basic usage with olmv0 (default)**:
   ```
   /olm:debug "CSV stuck in pending state" /path/to/must-gather
   ```

2. **Debug olmv1 issue**:
   ```
   /olm:debug "ClusterExtension installation failing" /path/to/must-gather olmv1
   ```

3. **Debug with detailed issue description**:
   ```
   /olm:debug "Operator upgrade from v1.0 to v2.0 fails with dependency resolution error" ~/Downloads/must-gather.local.123456 olmv0
   ```

## Notes

- The command requires `git` to be installed for cloning repositories
- Network access is required to clone from GitHub and access Jira
- Large must-gather archives may take time to process
- The analysis is based on pattern matching and may require manual verification
- For private repositories, ensure GitHub credentials are configured
- Jira access to https://issues.redhat.com/ may require authentication for full access
- Known bug matching is based on text similarity and may produce false positives
- Always verify suggested bug matches by reading the full bug description

## See Also

- OLM Documentation: https://olm.operatorframework.io/
- OpenShift OLM: https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html
- Must-gather documentation: https://docs.openshift.com/container-platform/latest/support/gathering-cluster-data.html
- OCPBUGS Jira Project: https://issues.redhat.com/projects/OCPBUGS/
- Jira REST API: https://docs.atlassian.com/jira-software/REST/latest/
