# MCP Tools Reference

This document lists the MCP server tools used by this plugin for cluster validation and JIRA integration.

## kube-compare-mcp Tools

The `kube-compare-mcp` server wraps the `kube-compare` kubectl plugin for AI-assisted cluster validation against Telco Reference Design Specifications (RDS).

**Prerequisites**: The kube-compare-mcp server must be configured and running. See `kube-compare-mcp` repository for setup.

### kube_compare_resolve_rds

Resolves available RDS profiles (RAN-DU, Core, Hub).

**Usage**: Call before validation to determine which RDS profile applies to the blueprint's deployment scenario.

```text
Tool: kube_compare_resolve_rds
Input: { "profile": "ran-du" }  // or "core", "hub"
Returns: RDS reference configuration paths and metadata
```

### kube_compare_cluster_diff

Compares a live cluster or manifests against an RDS reference configuration.

**Usage**: Called by the `validate` command (Phase 7) to perform cluster-level compliance checks.

```text
Tool: kube_compare_cluster_diff
Input: {
  "reference": "<rds-profile>",
  "cluster": "<kubeconfig-or-manifests-path>"
}
Returns: Structured diff showing deviations from RDS
```

### kube_compare_validate_rds

Validates an RDS reference configuration itself for correctness.

```text
Tool: kube_compare_validate_rds
Input: { "reference": "<rds-profile>" }
Returns: Validation result with any configuration issues
```

### baremetal_bios_diff

Compares BIOS settings against reference configurations.

**Usage**: Relevant for the Hardware and Node Configuration section of blueprints (H-BOM, Kernel/BIOS settings).

```text
Tool: baremetal_bios_diff
Input: {
  "reference": "<bios-reference>",
  "current": "<current-bios-settings>"
}
Returns: BIOS setting deviations
```

## JIRA Integration

JIRA integration is handled through the existing `jira` plugin's MCP tools. This plugin delegates to the jira plugin for ticket operations.

### Creating ECOPS Tickets

Use the jira plugin's create command or MCP tools to create ECOPS tickets:

```text
Project: ECOPS
Issue Type: Task or Bug
Fields:
  - Summary: "[Blueprint] <partner-name> - <issue-description>"
  - Description: Compliance finding details, section reference, recommended fix
  - Labels: ["blueprint", "compliance", "<partner-name>"]
```

### Querying Existing Tickets

Search for blueprint-related ECOPS tickets using JQL:

```text
JQL: project = ECOPS AND labels = "blueprint" AND labels = "<partner-name>"
```

### SUPPORTEX Ticket References

Support exception tickets follow the pattern `SUPPORTEX-XXXXX` and are tracked at:
`https://issues.redhat.com/browse/SUPPORTEX-XXXXX`

When documenting deviations, always link to the corresponding SUPPORTEX ticket.

## RDSAnalyzer Integration

The RDSAnalyzer CLI can be used as an additional validation layer:

```text
Flow: kube-compare (diffs) → RDSAnalyzer (rule evaluation) → Impact Reports
Profiles: RAN-DU, Core, Hub
Impact Levels: 4 levels (Critical, High, Medium, Low)
Output: HTML/text reports
```

This tool is complementary to kube-compare-mcp and provides rule-based deviation impact assessment.
