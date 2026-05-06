---
name: Kube Compare Integration
description: Integrates with kube-compare-mcp for cluster-level validation against Telco RDS profiles
---

# Kube Compare Integration

This skill provides the bridge between blueprint document validation and live cluster validation using the `kube-compare-mcp` MCP server. It translates kube-compare results into blueprint compliance findings.

## When to Use This Skill

Use this skill when:

- The `validate` command needs cluster-level validation (Phase 7)
- The `status` command checks current cluster compliance
- Cross-referencing blueprint deviations against actual cluster state
- Validating that a deployed cluster matches its blueprint's specifications

## Prerequisites

- The `kube-compare-mcp` MCP server must be configured and running
- A valid kubeconfig or manifest files for the target cluster
- See `reference/mcp-tools.md` for the complete tool signatures

## Implementation Steps

### Step 1: Determine RDS Profile

Based on the blueprint's deployment scenario, select the correct RDS profile:

| Blueprint Deployment Type | RDS Profile |
|--------------------------|-------------|
| Single Node OpenShift / DU | ran-du |
| Multi-node / 5G Core | core |
| Management / ACM Hub | hub |

Use the `kube_compare_resolve_rds` tool to confirm the profile is available and get its reference configuration paths.

For multi-profile blueprints (e.g., Hub + Core), run `kube_compare_resolve_rds` separately for each profile and validate each cluster independently against its corresponding RDS. Cluster validation results should be reported per profile in the integration report.

### Step 2: Run Cluster Comparison

Invoke `kube_compare_cluster_diff` with the appropriate RDS profile:

1. If a live cluster is available (kubeconfig provided): Compare against the live cluster
2. If manifest files are available: Compare against the manifest files
3. If neither is available: Skip this step and note in the report

The tool returns structured diffs showing where the cluster deviates from the RDS reference.

### Step 3: Parse Comparison Results

Process the kube-compare output to extract:

1. **Matching configurations**: Components that align with RDS (compliant)
2. **Deviations**: Components that differ from RDS (need documentation)
3. **Missing configurations**: RDS-required components not found in the cluster
4. **Extra configurations**: Components present in the cluster but not in RDS

### Step 4: Map Results to Blueprint Sections

Translate kube-compare findings into blueprint section references:

| kube-compare Finding | Blueprint Section |
|---------------------|-------------------|
| Operator version mismatch | Software and Configuration > Operators |
| Missing CRD or CR | Software and Configuration > Configuration Baseline |
| Network config deviation | Networking |
| Node label/taint mismatch | Hardware and Node Configuration > Node Labels and Taints |
| Resource partitioning diff | Hardware and Node Configuration > Resource Partitioning |
| BIOS setting deviation | Hardware and Node Configuration > Kernel and BIOS Settings |

### Step 5: Cross-Reference with Documented Deviations

Compare kube-compare findings against the blueprint's documented deviations:

1. For each kube-compare deviation, check if it appears in the blueprint's deviations section
2. **Documented deviation**: Mark as acknowledged — no action needed
3. **Undocumented deviation**: Flag as a compliance gap — needs documentation or remediation
4. **Documented but not found**: The deviation may have been resolved — suggest removing from the blueprint

### Step 6: Run BIOS Validation (Optional)

If hardware BIOS settings are available, invoke `baremetal_bios_diff`:

1. Compare current BIOS settings against the RDS reference
2. Map deviations to the Hardware and Node Configuration section
3. Flag any BIOS settings that should be documented as deviations

### Step 7: Generate Integration Report

Produce a summary that integrates with the main compliance report:

```text
## Cluster Validation Results

### RDS Profile: <profile-name>
### Cluster: <cluster-identifier>

| Category | Compliant | Deviations | Missing |
|----------|-----------|------------|---------|
| Operators | X | Y | Z |
| Network Config | X | Y | Z |
| Node Config | X | Y | Z |
| BIOS Settings | X | Y | Z |

### Undocumented Deviations (Action Required)
1. <deviation-description> — Blueprint section: <section>
2. ...

### Documented Deviations (Acknowledged)
1. <deviation-description> — SUPPORTEX: <ticket>
2. ...
```

## Return Value

- Cluster compliance summary (compliant / deviations / missing counts)
- List of undocumented deviations requiring blueprint updates
- List of documented deviations confirmed by cluster state
- Mapping of findings to blueprint sections
- Integration report for inclusion in the main compliance report

## Error Handling

- **kube-compare-mcp not available**: Inform user, skip cluster validation, note in report
- **Invalid kubeconfig**: Ask user for correct cluster credentials
- **RDS profile not found**: List available profiles and ask user to select
- **Timeout on large clusters**: Suggest running against specific namespaces or component subsets
