---
description: Analyze Go codebase for CVE vulnerabilities and suggest fixes
argument-hint: <CVE-ID> [--algo=vta|rta|cha|static]
---

## Name
compliance:analyze-cve

## Synopsis
```
/compliance:analyze-cve <CVE-ID> [--algo=vta|rta|cha|static]
```

## Description
The `compliance:analyze-cve` command performs comprehensive security vulnerability analysis for Go projects. Given a CVE identifier, it gathers vulnerability intelligence, analyzes the codebase for impact, generates a risk report, and optionally applies fixes.

## Implementation

### Phase 0: Setup and Tool Validation

1. **Parse Arguments**
   - Extract `<CVE-ID>` (required) from the first argument
   - Extract `--algo` value if provided (optional, default: `vta`)
   - Valid `--algo` values: `vta`, `rta`, `cha`, `static`

2. **Check Required Tools**

   ```bash
   go version 2>/dev/null || echo "MISSING: go"
   [ -f go.mod ] || echo "MISSING: go.mod"
   which govulncheck 2>/dev/null || echo "MISSING: govulncheck"
   which callgraph 2>/dev/null || echo "MISSING: callgraph"
   which digraph 2>/dev/null || echo "MISSING: digraph"
   ```

3. **If ANY Tool is Missing** → Display installation instructions and **exit with error**:

   ```
   go install golang.org/x/vuln/cmd/govulncheck@latest
   go install golang.org/x/tools/cmd/callgraph@latest
   go install golang.org/x/tools/cmd/digraph@latest
   ```

4. **If All Tools Present** → Continue to Phase 1

---

### Phase 1: CVE Intelligence Gathering

- **Skill**: [cve-intelligence-gathering](../skills/cve-intelligence-gathering/SKILL.md)
- **Input**: CVE-ID from arguments
- **Output**: CVE profile (severity, affected packages, fixed versions, remediation guidance, Go relevance)

**Decision Point:**
- IF invalid CVE format → Exit with error
- IF CVE not found AND user declines to provide info → Exit with error
- IF CVE is not Go-related → Generate "Not Applicable" report → Exit
- IF CVE details found → Continue to Phase 2

---

### Phase 2: Codebase Impact Analysis

- **Skill**: [codebase-impact-analysis](../skills/codebase-impact-analysis/SKILL.md)
  - Sub-skill: [call-graph-analysis](../skills/call-graph-analysis/SKILL.md)
- **Input**: CVE profile from Phase 1, `--algo` preference
- **Output**: Risk level (HIGH/MEDIUM/LOW/NEEDS_REVIEW), evidence package, confidence assessment

**Decision Point:**
- IF HIGH RISK or MEDIUM RISK → Generate report (Phase 3) → Proceed to Phase 4
- IF LOW RISK → Generate report (Phase 3) → Recommend manual review → Exit
- IF NEEDS REVIEW → Generate report (Phase 3) → Ask user if they want remediation guidance
  - IF yes → Proceed to Phase 4
  - IF no → Exit

---

### Phase 3: Report Generation

Generate analysis report at `.work/compliance/analyze-cve/{CVE-ID}/report.md`

**Report structure:**
- Executive Summary: risk level, confidence, key takeaway
- CVE Context: vulnerability description, sources (tag verified vs user-provided)
- Analysis Methods: what was used, why, and what was found
- Findings: specific evidence (file paths, versions, code snippets, call chains)
- Risk Assessment: severity + actual exposure + exploitability in this context
- Next Steps: remediation guidance or monitoring recommendations
- Sources and Limitations: tools used, gaps, analysis date

**Additional artifacts** (as generated):
- `callgraph.svg` (if call graph analysis was performed)
- `govulncheck-output.txt` (if scanner was run)
- `evidence.json` (structured evidence data)

---

### Phase 4: Remediation Guidance

- **Skill**: [remediation-planning](../skills/remediation-planning/SKILL.md)
- **Input**: CVE profile from Phase 1, risk level and evidence from Phase 2
- **Output**: Remediation plan (strategy, commands, verification steps, risk assessment)

**Decision Point:**
- Present remediation plan to user
- Ask: "Would you like me to apply these fixes automatically?"
- IF yes → Continue to Phase 5
- IF no → Exit with report and manual instructions

---

### Phase 5: Interactive Fix Application

Requires explicit user approval before proceeding.

1. **Apply Fixes**
   - Update `go.mod`/`go.sum`: `go get -u <package>@<fixed-version>` + `go mod tidy`
   - Modify source code if required (as identified in Phase 4)

2. **Verify Changes**
   - Check for Makefile targets first, fall back to standard Go commands:
     - Verify: `make verify` or `go mod verify`
     - Build: `make build` or `go build ./...`
     - Test: `make test` or `go test ./...`
   - Re-check: `govulncheck ./...`

3. **Document Changes**
   - Summary of changes, files modified, git diff, suggested commit message

## Return Value

- **Format**: Markdown report at `.work/compliance/analyze-cve/{CVE-ID}/report.md`
- **Content**: Vulnerability details, risk assessment, evidence, remediation recommendations, applied fixes (if approved)

## Arguments

- `<CVE-ID>`: The CVE identifier to analyze (e.g., CVE-2024-1234, CVE-2023-45678)
  - Format: CVE-YYYY-NNNNN
  - Case insensitive
  - Required argument
- `--algo`: Call graph construction algorithm (optional, default: `vta`)
  - `vta` - Most precise, fewest false positives (recommended)
  - `rta` - Good balance of precision and speed
  - `cha` - Fast, less precise
  - `static` - Fastest, least precise

## Examples

1. **Basic CVE analysis**:
   ```
   /compliance:analyze-cve CVE-2024-45338
   ```

2. **With specific algorithm**:
   ```
   /compliance:analyze-cve CVE-2024-45338 --algo=rta
   ```

## Prerequisites

All tools are **required**. The command exits with an error if any are missing.

```bash
# Install all required Go tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest
```

**Optional**: `graphviz` for visual call graph generation (`brew install graphviz` or `sudo apt-get install graphviz`)

**Internet access** is recommended for CVE data fetching but not required if you can provide CVE details manually.

## Notes

- Focuses on Go-specific vulnerabilities
- Falls back to user-provided information if internet access fails
- Does NOT make changes without explicit user approval
- Reports are saved locally and not committed to git
