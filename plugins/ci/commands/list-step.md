---
description: List the step for the given workflow or chain name
argument-hint: <workflow-or-chain-name>
---

## Name

ci:list-step

## Synopsis

/ci:list-step <workflow-or-chain-name>

## Description

The ci:list-step command analyzes an OpenShift CI workflow or chain and provides a complete hierarchical breakdown of all the workflow, chain, and ref
files with their repo paths that make up the workflow or chain.

The command accepts:
- Workflow/Chain name (required)

It uses the step-registry-analyzer agent to examine the workflow/chain structure and identify all related components including workflows, chains, refs, and
their associated command files.

## Implementation

The command performs the following steps:

1. Parse Arguments:
   - $1: Workflow or chain name (required, e.g., "hypershift-aws-reqserving-e2e")
2. Execute Analysis: Use the Task tool with step-registry-analyzer agent:
   Task tool with:
- subagent_type: "step-registry-analyzer"
- description: "analzye and list all workflow/chain/ref with repository path for <workflow-or-chain-name> and keep the hierarchical structure"
- prompt: Detailed request to analyze the workflow or chain and provide complete hierarchical breakdown

3. Display Results: Present the hierarchical structure showing:
   - Main workflow or chain file path
   - All chain files referenced in the workflow or chain with their repository paths
   - All ref files referenced in the chains with their repository paths
   - Any command files (.sh) associated with the refs
   - The complete hierarchical structure showing relationships between all files
4. Format Output: Use a clear hierarchical tree format with:
   - Full repository paths for all files
   - Indentation showing the workflow/chain/ref relationships
   - File types (workflow/chain/ref/command) clearly identified
   - Summary of total files and execution phases

## Return Value

- Success: Complete hierarchical structure of the OpenShift CI workflow or chain
- Error: Workflow or Chain not found, analysis failure, or invalid workflow or chain name

## Important for Claude:
1. REQUIRED: Always use the step-registry-analyzer agent for this analysis
2. Use the Task tool with the specialized agent to ensure comprehensive analysis
3. Maintain the proper directory structure and show the relationships between files
4. Include all phases (PRE/TEST/POST) in the hierarchy
5. Show both the structural hierarchy and file paths clearly
6. Show all workflow/chain/ref/command files with repository path
6. Provide a summary of total files and execution flow

## Examples

1. ** Analyze hypershift aws e2e external workflow ** :
```
   /list-step hypershift-aws-e2e-external
```
   Returns:
```
     Workflow: ci-operator/step-registry/hypershift/aws/e2e/external/hypershift-aws-e2e-external-workflow.yaml

Complete Repository Path Hierarchy

ci-operator/step-registry/hypershift/aws/e2e/external/hypershift-aws-e2e-external-workflow.yaml
├── PRE Phase (Infrastructure Setup)
│   ├── ci-operator/step-registry/ipi/install/rbac/ipi-install-rbac-ref.yaml
│   │   └── ci-operator/step-registry/ipi/install/rbac/ipi-install-rbac-commands.sh
│   ├── ci-operator/step-registry/hypershift/setup-nested-management-cluster/hypershift-setup-nested-management-
cluster-chain.yaml
│   │   └── Embedded Steps:
│   │       ├── create-management-cluster (inline command)
│   │       └── Dependencies: hypershift-operator, AWS credentials, kubeconfigs
│   └── ci-operator/step-registry/hypershift/install/hypershift-install-ref.yaml
│       └── ci-operator/step-registry/hypershift/install/hypershift-install-commands.sh
├── TEST Phase (E2E External Tests)
│   └── ci-operator/step-registry/hypershift/aws/run-e2e/external/hypershift-aws-run-e2e-external-ref.yaml
│       └──
ci-operator/step-registry/hypershift/aws/run-e2e/external/hypershift-aws-run-e2e-external-commands.sh
└── POST Phase (Cleanup)
└── ci-operator/step-registry/hypershift/destroy-nested-management-cluster/hypershift-destroy-nested-managem
ent-cluster-chain.yaml
├── Embedded Step: dump-management-cluster (inline command)
├── ci-operator/step-registry/hypershift/dump/extra/hypershift-dump-extra-ref.yaml
│   └── ci-operator/step-registry/hypershift/dump/extra/hypershift-dump-extra-commands.sh
└── Embedded Step: destroy-management-cluster (inline command)

File Summary

Total Files: 10 files
- 1 workflow file: Main orchestration defining pre/test/post phases
- 2 chain files: Setup and destroy management cluster chains
- 4 ref files: RBAC, E2E test runner, installation, and artifact dump steps
- 3 command files: Shell scripts for executing the ref implementations

Execution Flow

PRE Phase: RBAC Setup → Management Cluster Creation → HyperShift Installation
TEST Phase: External E2E Tests with OIDC support
POST Phase: Artifact Collection → Infrastructure Cleanup

This workflow provides comprehensive end-to-end testing for HyperShift on AWS with external OIDC authentication, multi-architecture support, upgrade
testing, and complete infrastructure lifecycle management.
  ```
   
## Notes

- Hierarchy Structure: Shows both the logical flow (PRE/TEST/POST) and file dependencies
- File Relationships: Clearly indicates how chains reference refs and how commands are associated
- Path Completeness: All paths are shown as full repository paths from the root

## Arguments
- $1 (workflow-or-chain-name): The name of the OpenShift CI workflow or chain to analyze (required)
