---
name: pr-analyzer
argument hint: PR (pull request)
description: Analyze RHEL/ClusterLabs resource-agents PRs and generate comprehensive documentation
---


## Name
jira:pr-analyzer

## Synopsis
```bash
/jira:pr-analyzer #PR Number
```

## Prerequisites
It will help to have the GitHub CLI, or gh installed.

## Description
The `jira:pr-analyzer` command generates comprehensive documentation and a verification script to help understand PR changes. 
It produces a shareable guide with a summary, testing steps, and troubleshooting information, plus an executable verification script.

## Implementation
When user says "analyze PR [number]" or provides PR URL/diff, create 2 files:

1. PR{NUMBER}_GUIDE.md:
   - Summary: JIRA link, status (merged date), author, 2-3 sentence description, priority, customer impact
   - Quick Start: One-line description, "Do you need this?" checklist, quick verification command
   - Context: Why it matters for TNF (two node fencing) 2-node clusters
   - Code Changes Summary: Files/lines changed, commits (hash+message), functions added/modified (with line numbers)
   - How the Fix Works: Before/after code snippets
   - Before vs After Comparison Table
   - Dependencies & Related PRs
   - Step-by-Step Testing
   - Testing Matrix
   - Troubleshooting: Node discovery (crm_node -l), diagnostics, common issues, SSH patterns (direct + ProxyJump)
   - Security & Impact Assessment
   - Version Compatibility Matrix: RHEL versions, merge date, which versions include PR
   - Deployment Checklist
   - Metrics & Observability
   - Rollback Steps
   - Understanding PR #{NUMBER} Logs (IMPORTANT):
     * When the log appears (conditions required)
     * Code paths that skip this log (with line numbers)
     * Multi-Level Verification:
       - Level 1: Code presence (grep - most reliable)
       - Level 2: Behavior testing (functional)
       - Level 3: Log confirmation (optional)
     * Emphasize: Absence of log ≠ PR not working
   - Quick Reference Card
   - Footer: Last updated, PR status, recommended action

2. verify_pr{NUMBER}.sh:
   - #!/bin/bash, set -euo pipefail
   - Run from bastion, SSH to nodes
   - ssh_node/ssh_sudo helpers
   - Target: ${1:-$NODE1}
   - All pcs/crm use sudo
   - Steps: "Step N: ..."
   - 5 checks, score X/5
   - grep -q for booleans
   - Search actual logs, multiple paths
   - Wait for async ops
   - Troubleshooting hints on fail
   - Cleanup/restore
   - exit 0/1

JIRA Patterns: OCPBUGS-*/OCPEDGE-*/RHEL-* → [https://issues.redhat.com/browse/{ID}](https://issues.redhat.com/browse/{ID})

Context: ClusterLabs/RHEL resource-agents, Pacemaker/OCF, TNF (two node fencing) 2-node clusters, production RHEL/OpenShift
