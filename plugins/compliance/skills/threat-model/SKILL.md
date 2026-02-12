---
name: threat-model
description: Analyze a PR for security threats, map to MITRE ATT&CK, generate report
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, WebFetch
argument-hint: "<PR-number | GitHub-URL>"
---

# PR Threat Analysis

Analyze a pull request for security threats, map to MITRE ATT&CK, and generate a formal report.

## Input Formats

The skill accepts flexible input:

### Option 1: PR Number Only
```
/threat-model 1234
```
Detects the repository from the current working directory. Must be inside a repo under `~/Projects/tnf-dev-env/repos/<repo>/`.

### Option 2: GitHub PR URL
```
/threat-model https://github.com/openshift/cluster-etcd-operator/pull/1234
```
Extracts org, repo, and PR number from the URL automatically.

### Option 3: Explicit repo and PR
```
/threat-model cluster-etcd-operator 1234
```
Specify repo name and PR number explicitly.

### Option 4: With topology override
```
/threat-model --tnf 1234
/threat-model --tna https://github.com/openshift/installer/pull/5678
```
Force a specific topology instead of auto-detection.

## Parsing Logic

1. **If input is a URL** (contains `github.com`):
   - Extract org/repo/PR from: `https://github.com/<org>/<repo>/pull/<PR>`

2. **If input is a single number**:
   - Detect repo from current directory path
   - Look for pattern `repos/<repo-name>/` in the working directory
   - Use the repo's configured remote to determine the org

3. **If input is `<repo> <number>`**:
   - Use provided repo name
   - Look up org from the repository mapping table below

## Topology Detection

After parsing the PR input, determine which topology (TNF or TNA) the PR relates to.

### Detection Rules (in priority order)

1. **Manual override**: If the user specifies `--tnf` or `--tna` in the input, use that.

2. **Repo-exclusive**: Some repos are topology-exclusive:
   - `resource-agents` -> always TNF (podman-etcd OCF agent)
   - `pacemaker` -> always TNF

3. **Code path indicators**: Check the PR diff for topology-specific paths:

   **TNF indicators** (any match -> TNF):
   - `pkg/tnf/` (CEO TNF controller)
   - `heartbeat/podman-etcd` (OCF agent)
   - `heartbeat/podman` (base OCF agent)
   - `fencing-credentials`, `fencing_credentials`, `FencingCredential`
   - `stonith`, `STONITH`
   - `pacemaker`, `corosync`, `pcsd`, `pcs `
   - `two-node-with-fencing`, `two-node-fencing`
   - `templates/master/00-master/two-node-with-fencing/`

   **TNA indicators** (any match -> TNA):
   - `arbiter` in file paths (arbiter.go, arbiter*.go, arbiter.machineconfigpool)
   - `IsArbiterEnabled`, `HighlyAvailableArbiter`, `ArbiterNodeTopology`
   - `arbiter_topology.go`, `tna_recovery.go`
   - `TNA_IPV4`, `TNA_IPV6`, `NUM_ARBITERS`
   - `two-node-arbiter`, `arbiter-clusters`

4. **Both indicators present**: If the PR touches both TNF and TNA code paths (e.g., shared installer validation), analyze for both topologies and note the dual scope in the report.

5. **Neither indicator**: If no topology-specific code paths are found (e.g., generic CEO or MCO changes), check the PR title and description for topology keywords. If still unclear, ask the user.

### Topology Determines

Once topology is determined, it controls:
- Which DFD reference file to load (`dfd-elements-tnf.md` or `dfd-elements-tna.md`)
- Which "Code Path to DFD Element" mapping table to use
- Which "Trust Boundary Crossings" table to use
- Which formal threat model to cross-reference (`TNF-THREAT-MODEL.md` or `TNA-THREAT-MODEL.md`)
- Which topology-specific MITRE/OWASP mappings are relevant
- The topology field in the report header and findings tracker

## Repository Mapping

| Repo | GitHub Org |
|------|------------|
| assisted-service | openshift |
| cluster-etcd-operator | openshift |
| machine-config-operator | openshift |
| installer | openshift |
| cluster-baremetal-operator | openshift |
| resource-agents | ClusterLabs |
| origin | openshift |
| dev-scripts | openshift-metal3 |
| release | openshift |
| enhancements | openshift |
| openshift-docs | openshift |
| pacemaker | ClusterLabs |

## Instructions

1. **Parse input** to determine org, repo, and PR number
2. **Fetch PR details** using `gh pr view <PR> --repo <org>/<repo>` or WebFetch
3. **Get changed files** with `gh pr diff <PR> --repo <org>/<repo>` or WebFetch
4. **Run ShellCheck** on any shell scripts in the changed files (see Automated Scanner section)
5. **Analyze all changes** for security-relevant patterns (AI analysis)
6. **Map to DFD elements** — identify which DFD elements are affected by the PR using the topology-appropriate mapping table (see DFD Element Mapping section and `dfd-elements-tnf.md` / `dfd-elements-tna.md`)
7. **Apply per-element STRIDE** to affected elements and cross-reference against the appropriate formal threat model:
   - **TNF**: `repos/two-node-toolbox/docs/TNF-THREAT-MODEL.md`
   - **TNA**: `repos/two-node-toolbox/docs/TNA-THREAT-MODEL.md`
8. **Combine findings** from ShellCheck + AI analysis + DFD/STRIDE analysis
9. **Map findings to MITRE ATT&CK** techniques
10. **Generate report** at `~/Projects/tnf-dev-env/repos/two-node-toolbox/docs/`
11. **Update tracking file** at `.claude/skills/threat-model/mitre-findings.md`

---

## Automated Scanner: ShellCheck

ShellCheck is available in RHEL/Fedora repos (`dnf install ShellCheck`) - no external downloads required.

### Installation Check

```bash
command -v shellcheck >/dev/null && echo "shellcheck: installed" || echo "shellcheck: NOT installed (run: dnf install ShellCheck)"
```

### Running ShellCheck

```bash
# JSON output for parsing
shellcheck -f json <script-file>

# Human-readable with severity filter
shellcheck -S warning <script-file>

# Check specific shell dialect
shellcheck -s bash <script-file>
```

### Security-Relevant ShellCheck Codes

| Code | Severity | Security Relevance | MITRE |
|------|----------|-------------------|-------|
| SC2086 | Warning | Unquoted variable - command injection risk | T1059 |
| SC2091 | Warning | Command in $() used as condition - injection | T1059 |
| SC2046 | Warning | Unquoted command substitution | T1059 |
| SC2012 | Info | Parsing ls output - can be exploited | T1059 |
| SC2029 | Warning | ssh command with unescaped variables | T1059 |
| SC2087 | Warning | Unquoted heredoc - variable expansion | T1059 |
| SC2155 | Warning | Declare/assign separately to avoid masking errors | - |
| SC2164 | Warning | cd without `\|\|` exit - path traversal risk | T1083 |

### Include in Report

Add ShellCheck results to the report under Automated Scanner Results:

```markdown
## Automated Scanner Results

### ShellCheck

**Tool**: ShellCheck (from RHEL repos)
**Version**: X.X.X

| Code | Severity | File | Line | Message |
|------|----------|------|------|---------|
| SC2086 | warning | podman-etcd | 42 | Double quote to prevent globbing and word splitting |

*Security-relevant findings (SC2086, SC2091, SC2046, SC2029) are highlighted above.*
```

If ShellCheck is not installed:
```markdown
### ShellCheck

*Not installed. Install with: `dnf install ShellCheck`*
```

If no shell scripts in PR:
```markdown
### ShellCheck

*No shell scripts in this PR - skipped.*
```

---

## Optional External Scanners

The following scanners provide additional coverage but require **external downloads**. Use at your own discretion based on your security policy.

### Risk Assessment

| Tool | Source | Risks | Mitigations |
|------|--------|-------|-------------|
| **Semgrep** | pip/GitHub | Fetches rules from semgrep.dev; may send telemetry | Use `--offline` mode with local rules |
| **Gitleaks** | GitHub releases | Binary from external source | Verify checksums; use container image |
| **gosec** | GitHub/go install | Binary from external source | Verify checksums; audit source |

### Semgrep (Optional)

```bash
# Install (EXTERNAL - requires pip)
pip install semgrep

# Run with offline mode (no rule fetching)
semgrep scan --config ~/path/to/local/rules.yaml --offline <files>

# Or accept external rule download risk:
semgrep scan --config p/security-audit <files> --json
```

**Note**: By default, Semgrep fetches rules from the internet and may send telemetry. Use `--offline` with local rules for air-gapped environments.

### Gitleaks (Optional)

```bash
# Install (EXTERNAL - from GitHub)
go install github.com/gitleaks/gitleaks/v8@latest

# Run (rules are bundled - no network needed after install)
gitleaks detect --source <repo-path> --verbose --report-format json
```

**Note**: Binary downloaded from GitHub. Verify checksums before use.

### gosec (Optional)

```bash
# Install (EXTERNAL - from GitHub)
go install github.com/securego/gosec/v2/cmd/gosec@latest

# Run (rules are bundled - no network needed after install)
gosec -fmt json ./...
```

**Note**: Binary downloaded from GitHub. Verify checksums before use. Only useful for Go code.

### Using Optional Scanners

If optional scanners are installed and you choose to use them, include their output:

```markdown
## Automated Scanner Results

### ShellCheck (RHEL repos - trusted)
[results]

### Semgrep (external - optional)
[results or "Not installed"]

### Gitleaks (external - optional)
[results or "Not installed"]

### gosec (external - optional)
[results or "Not installed"]
```

### Check Optional Scanner Availability

```bash
command -v semgrep >/dev/null && echo "semgrep: installed" || echo "semgrep: not installed (external)"
command -v gitleaks >/dev/null && echo "gitleaks: installed" || echo "gitleaks: not installed (external)"
command -v gosec >/dev/null && echo "gosec: installed" || echo "gosec: not installed (external)"
```

---

## Security Patterns to Detect

| Category | Patterns | MITRE | Severity |
|----------|----------|-------|----------|
| Command Injection | shell exec, os.system, subprocess, fmt.Sprintf with shell | T1059 | Critical |
| Credentials | hardcoded secrets, API keys, tokens, passwords in code | T1552 | Critical |
| Privilege Escalation | setuid, capabilities, privileged containers, sudo, nsenter | T1548 | High |
| Authentication | auth bypass, weak validation, token handling flaws | T1078 | High |
| Crypto Weakness | weak algorithms, hardcoded keys, disabled TLS verify | T1573 | High |
| Path Traversal | unsanitized file paths, symlink attacks | T1083 | Medium |
| Container Escape | host mounts, hostPID, hostNetwork, privileged mode | T1611 | Critical |
| Logging Exposure | sensitive data in logs, credential printing | T1005 | Medium |
| SSRF/Network | unvalidated URLs, exposed internal endpoints | T1046 | Medium |
| Deserialization | unsafe unmarshal, pickle, yaml.load | T1059 | High |

## DFD Element Mapping

The formal threat models define Data Flow Diagrams with numbered elements. When analyzing a PR, map changed files to the affected DFD elements using the topology-appropriate table below to focus the STRIDE analysis. See `dfd-elements-tnf.md` for TNF elements or `dfd-elements-tna.md` for TNA elements.

### TNF: Code Path to DFD Element

| Code Path Pattern | DFD Element | STRIDE Focus |
|-------------------|-------------|--------------|
| `assisted-service/internal/installcfg/` | P1 (Installer) | I, T, R |
| `assisted-service/internal/bminventory/` | P1 (Installer) | I, S, T |
| `assisted-service/models/fencing*` | P1 (Installer), DF1 | I, T |
| `cluster-etcd-operator/pkg/tnf/operator/` | P2 (CEO Controller) | S, D, E |
| `cluster-etcd-operator/pkg/tnf/auth/` | P3 (Auth Job) | S, E |
| `cluster-etcd-operator/pkg/tnf/setup/` | P4 (Setup Job) | T, I, E, D |
| `cluster-etcd-operator/pkg/tnf/fencing/` | P5 (Fencing Job) | I, T, R, E |
| `cluster-etcd-operator/pkg/tnf/pkg/pcs/fencing*` | P5, DF7, DF9 | I, T |
| `cluster-etcd-operator/pkg/tnf/pkg/pcs/cluster*` | P4, DS3 | T, D |
| `cluster-etcd-operator/pkg/tnf/pkg/tools/secrets*` | DS2, DF4 | I, T |
| `cluster-etcd-operator/pkg/tnf/pkg/tools/redact*` | P5, DF9 | I, R |
| `cluster-etcd-operator/pkg/tnf/pkg/exec/` | P3-P5 (nsenter) | E |
| `cluster-etcd-operator/bindata/tnfdeployment/job*` | P3-P5 (container spec) | E |
| `pacemaker/daemons/fenced/` | P6 (fenced) | S, I, D |
| `resource-agents/heartbeat/podman-etcd` | P7 (OCF Agent) | T, D, I |
| `resource-agents/heartbeat/podman` | P7 (OCF Agent) | T, D |
| `machine-config-operator/templates/*two-node*` | DS4 (PCSD setup) | T, E |
| `installer/pkg/asset/agent/manifests/fencing*` | P1, DS1, DF1, DF2 | I, T |

### TNA: Code Path to DFD Element

| Code Path Pattern | DFD Element | STRIDE Focus |
|-------------------|-------------|--------------|
| `installer/pkg/asset/machines/arbiter*` | P1 (Installer) | T, D |
| `installer/pkg/asset/ignition/machine/arbiter*` | P1, DS6 | T, I |
| `installer/pkg/types/installconfig.go` (IsArbiterEnabled) | P1 | T, D |
| `installer/pkg/types/validation/installconfig.go` (arbiter) | P1 | T |
| `assisted-service/internal/common/common.go` (arbiter) | P1 | T |
| `assisted-service/internal/cluster/validator.go` (arbiter role) | P1 | S, T |
| `machine-config-operator/manifests/arbiter*` | P3 (MCO) | T, D |
| `machine-config-operator/templates/arbiter/` | P3 | T, E |
| `cluster-etcd-operator/pkg/operator/ceohelpers/control_plane_topology.go` | P4 (CEO) | T, D |
| `cluster-etcd-operator/pkg/operator/ceohelpers/multiselector_lister.go` | P4 | T, D |
| `cluster-etcd-operator/pkg/operator/configobservation/*replicas*` | P4 | T, D |
| `origin/test/extended/two_node/arbiter_topology.go` | Test | - |
| `origin/test/extended/two_node/tna_recovery.go` | Test | - |

### TNF: Trust Boundary Crossings

When a PR modifies code that crosses a trust boundary, apply additional scrutiny:

| Boundary Crossing | Code Indicators | Key Threats |
|-------------------|-----------------|-------------|
| TB2→TB3 (K8s → Privileged Container) | Job specs, SA tokens, secret reads | E (escape), I (secret leak) |
| TB3→TB4 (Container → Host) | nsenter calls, hostPID, privileged | E (host access), T (CIB tamper) |
| TB4→TB5 (Host → BMC) | fence_redfish calls, Redfish URLs | S (MITM), I (credential exposure) |
| TB2→TB4 (Secrets → CIB) | Secret→pcs command pipeline | I (plaintext creds in XML) |
| TB6 (Inter-Node) | Corosync config, PCSD auth | S (spoofing), D (quorum loss) |

### TNA: Trust Boundary Crossings

| Boundary Crossing | Code Indicators | Key Threats |
|-------------------|-----------------|-------------|
| TB1->TB2 (Admin -> K8s API) | install-config, oc commands | S (admin impersonation), T (config tampering) |
| TB2 internal (MCO -> kubelet) | arbiter MCP, kubelet config, taint | T (taint removal), D (misconfiguration) |
| TB2->TB3 (K8s API -> Worker) | CSR approval, ignition endpoint | S (rogue CSR), E (lateral movement) |

### Per-Element STRIDE for PR Analysis

For each affected DFD element, ask these questions:

**Processes (all 6 STRIDE categories)**:
- **S**: Can the process be impersonated? Are auth checks adequate?
- **T**: Can inputs/outputs be modified? Is data validated?
- **R**: Are actions auditable? Are logs adequate and redacted?
- **I**: Does it handle secrets? Are they protected in transit/at rest?
- **D**: Can it be crashed or blocked? What happens on failure?
- **E**: Does it run with minimal privilege? Can it be abused for escalation?

**Data Stores (T, I, D)**:
- **T**: Can stored data be modified by unauthorized parties?
- **I**: Is sensitive data encrypted? Who can read it?
- **D**: Can the store be corrupted or deleted?

**Data Flows (T, I, D)**:
- **T**: Can data in transit be modified? Is integrity verified?
- **I**: Is the channel encrypted? Are credentials visible?
- **D**: Can the flow be interrupted or flooded?

**External Entities (S, R)**:
- **S**: Can the entity be impersonated? Is authentication enforced?
- **R**: Can the entity deny having performed an action? Are interactions logged?

### Cross-Referencing the Threat Model

After identifying per-element threats in a PR, check if they match existing threats in the formal threat model:

1. Read the appropriate threat model based on detected topology:
   - **TNF**: `repos/two-node-toolbox/docs/TNF-THREAT-MODEL.md`
   - **TNA**: `repos/two-node-toolbox/docs/TNA-THREAT-MODEL.md`
2. Search for the relevant `PE-<element>-*` IDs in the Per-Element STRIDE Analysis section
3. If a PR introduces a **new** threat not covered by existing PE-* entries, flag it as a gap
4. If a PR **mitigates** an existing PE-* threat, note it as a positive finding
5. If a PR **worsens** an existing PE-* threat, flag with elevated severity

---

## Report Naming Convention

Generate reports with this naming:
- **Full threat model**: `PR<number>-THREAT-MODEL-<repo>.md`
- **Individual vuln**: `VULN-PR<number>-<short-desc>.md`

## Report Format: Threat Model

Use this structure (based on existing reports in `two-node-toolbox/docs/`):

```markdown
# PR #<number> Threat Analysis: <PR Title>

**Document Version**: 1.0
**Date**: YYYY-MM-DD
**Classification**: Internal - Security Sensitive
**Repository**: <repo>
**Topology**: TNF / TNA / Both
**PR Author**: <author>
**PR URL**: <url>

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Change Overview](#change-overview)
3. [Affected Files](#affected-files)
4. [DFD Impact Analysis](#dfd-impact-analysis)
5. [Threat Analysis](#threat-analysis)
6. [MITRE ATT&CK Mapping](#mitre-attck-mapping)
7. [Risk Assessment](#risk-assessment)
8. [Recommendations](#recommendations)
   - [For Developers (Code Changes)](#for-developers-code-changes)
   - [For Customers (Deployment & Operations)](#for-customers-deployment--operations)

---

## Executive Summary

[Brief overview of the PR and key security findings]

### Findings Summary

| Severity | Count | Summary |
|----------|-------|---------|
| Critical | X | [brief] |
| High | X | [brief] |
| Medium | X | [brief] |
| Low | X | [brief] |

---

## Change Overview

[What this PR does, its purpose, and security-relevant changes]

---

## Affected Files

| File | Changes | Security Relevance |
|------|---------|-------------------|
| path/to/file.go | +X/-Y lines | [relevance] |

---

## DFD Impact Analysis

This PR affects the following elements in the [TNF|TNA] Data Flow Diagram
(see [TNF-THREAT-MODEL.md|TNA-THREAT-MODEL.md]):

### Affected DFD Elements

| Element | Name | Impact | Trust Boundary |
|---------|------|--------|----------------|
| P# | [process name] | [what changed] | TB# |
| DS# | [store name] | [what changed] | TB# |
| DF# | [flow description] | [what changed] | TB#→TB# |

### Trust Boundary Crossings

[Describe any trust boundaries crossed by the changed code, and whether the PR introduces, modifies, or removes crossing logic]

### Per-Element STRIDE

| Element | S | T | R | I | D | E | Notes |
|---------|---|---|---|---|---|---|-------|
| P# | - | - | - | - | - | - | [Processes: all 6 categories] |
| DS# | N/A | - | N/A | - | - | N/A | [Data Stores: T, I, D only] |
| DF# | N/A | - | N/A | - | - | N/A | [Data Flows: T, I, D only] |
| EE# | - | N/A | - | N/A | N/A | N/A | [External Entities: S, R only] |

**Legend**: **X** = new threat found, **~** = existing threat modified, **-** = no impact, N/A = category not applicable to this element type

### Threat Model Cross-Reference

| PR Finding | Existing PE-* ID | Status |
|------------|-----------------|--------|
| [finding] | PE-XX-X-X | Matches existing / New gap / Mitigated |

---

## Threat Analysis

### VULN-1: [Vulnerability Title]

**Severity**: Critical/High/Medium/Low
**OWASP**: A##:2025 - Category Name
**MITRE ATT&CK**: T#### - Technique Name
**CWE**: CWE-###

### Affected Code

**File**: `path/to/file.go:line`

```go
// vulnerable code snippet
```

#### Description

[Detailed description of the vulnerability]

#### Attack Vector

[How this could be exploited]

#### Impact

- **Confidentiality**: [impact]
- **Integrity**: [impact]
- **Availability**: [impact]

#### Recommended Fix

```go
// fixed code
```

---

## OWASP & MITRE ATT&CK Mapping

| Finding | OWASP | MITRE | CWE | Status |
|---------|-------|-------|-----|--------|
| VULN-1 | A05:2025 Injection | T1059 | CWE-78 | Open |

---

## Risk Assessment

| Finding | Likelihood | Impact | Risk |
|---------|------------|--------|------|
| VULN-1 | High | Critical | Critical |

---

## Recommendations

### For Developers (Code Changes)

Actions for the PR author and reviewers to address before or after merge.

#### Before Merge

1. [Code fix or change required in this PR]

#### After Merge

1. [Follow-up code improvement, test addition, or refactor]

### For Customers (Deployment & Operations)

Guidance for cluster administrators deploying or operating TNF clusters.

#### Configuration Hardening

1. [Cluster configuration or hardening recommendation]

#### Operational Practices

1. [Monitoring, incident response, or day-2 operational guidance]

---

## References

- [OWASP Top 10:2025](https://owasp.org/Top10/2025/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [MITRE ATT&CK](https://attack.mitre.org/)
- [Relevant CVEs, CWEs, documentation]

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| YYYY-MM-DD | Claude Code | Initial analysis |
```

## Report Format: Individual Vulnerability (for Critical/High findings)

For significant findings, also create individual VULN reports:

```markdown
# Security Ticket: [Vulnerability Title]

**Ticket ID**: VULN-PR<number>-<seq>
**Severity**: CRITICAL/HIGH
**Component**: <repo>
**Status**: Open
**Created**: YYYY-MM-DD
**PR**: #<number>

---

## Summary

[One paragraph summary]

---

## Affected Code

**File**: `path/to/file.go:lines`

```go
// code with vulnerability highlighted
```

---

## Exploitation

### Attack Flow

```
[ASCII diagram of attack flow]
```

### Exploit Examples

[Code examples showing exploitation]

---

## Impact

[Detailed impact analysis]

---

## Recommended Fix

### For Developers

[Code showing the fix with explanation]

### For Customers

[Deployment hardening, configuration changes, or monitoring guidance to mitigate this vulnerability in production]

---

## References

- [CWE, OWASP, other references]
```

## Available Repositories

Repos in `~/Projects/tnf-dev-env/repos/`:

| Repo | Org | Focus Areas |
|------|-----|-------------|
| assisted-service | openshift | API security, credential handling |
| cluster-etcd-operator | openshift | Privilege, shell injection, secrets |
| machine-config-operator | openshift | Node config, privilege escalation |
| installer | openshift | Install config, credential storage |
| cluster-baremetal-operator | openshift | BMC access, metal3 security |
| resource-agents | ClusterLabs | OCF scripts, shell injection |
| two-node-toolbox | (internal) | Deployment scripts, credentials |
| origin | openshift | Test code security |
| dev-scripts | openshift-metal3 | Shell scripts, credential handling |

## Reference Files

- `dfd-elements-tnf.md` - TNF DFD element catalog (P1-P8, DS1-DS5, DF1-DF12, TB1-TB6)
- `dfd-elements-tna.md` - TNA DFD element catalog (P1, P3-P5, DS5-DS6, TB1-TB3)
- `mitre-reference.md` - Quick MITRE ATT&CK lookup with DFD element mappings (TNF + TNA)
- `owasp-reference.md` - OWASP Top 10:2025 mapping with DFD element cross-references (TNF + TNA)
- `mitre-findings.md` - Cumulative findings tracker
- `~/Projects/tnf-dev-env/repos/two-node-toolbox/docs/TNF-THREAT-MODEL.md` - TNF formal threat model with DFD and per-element STRIDE analysis
- `~/Projects/tnf-dev-env/repos/two-node-toolbox/docs/TNA-THREAT-MODEL.md` - TNA formal threat model
- Existing reports in `~/Projects/tnf-dev-env/repos/two-node-toolbox/docs/` for format reference
