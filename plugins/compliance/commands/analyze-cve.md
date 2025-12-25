---
description: Analyze Go codebase for CVE vulnerabilities and suggest fixes
argument-hint: <CVE-ID>
---

## Name
compliance:analyze-cve

## Synopsis
```
/compliance:analyze-cve <CVE-ID>
```

## Description
The `compliance:analyze-cve` command performs comprehensive security vulnerability analysis for Go projects. Given a CVE identifier, it fetches complete vulnerability details from authoritative sources, analyzes the codebase for potential impact, and provides actionable remediation guidance.

This command helps developers:
- Understand the full scope of a CVE vulnerability
- Determine if their Go codebase is affected
- Get specific fix recommendations
- Optionally apply fixes automatically

## Implementation

### Phase 0: Setup and Tool Validation

1. **Check Required Tools**
   
   Check for all required tools and collect missing ones:
   
   ```bash
   # Check Go toolchain
   go version 2>/dev/null || echo "MISSING: go"
   
   # Check for go.mod in workspace
   [ -f go.mod ] || echo "MISSING: go.mod"
   
   # Check govulncheck
   which govulncheck 2>/dev/null || echo "MISSING: govulncheck"
   
   # Check callgraph
   which callgraph 2>/dev/null || echo "MISSING: callgraph"
   
   # Check digraph
   which digraph 2>/dev/null || echo "MISSING: digraph"
   ```

2. **If ANY Tool is Missing**
   
   Display error message with installation instructions:
   
   ```
   ❌ ERROR: Missing required tools for CVE analysis
   
   The following tools are required but not found:
   
   [ ] Go toolchain
       Install: https://go.dev/doc/install
   
   [ ] go.mod in workspace
       Initialize: cd <your-project> && go mod init <module-name>
   
   [ ] govulncheck (Go vulnerability scanner)
       Install: go install golang.org/x/vuln/cmd/govulncheck@latest
   
   [ ] callgraph (Call graph analysis)
       Install: go install golang.org/x/tools/cmd/callgraph@latest
   
   [ ] digraph (Graph traversal)
       Install: go install golang.org/x/tools/cmd/digraph@latest
   
   Please install the missing tools and try again.
   
   Note: All tools are required for comprehensive CVE analysis with high confidence.
   ```
   
   **Exit with error code** - Do NOT proceed with analysis

3. **If All Tools Present**
   
   Display confirmation and proceed:
   
   ```
   ✅ All required tools found:
   - Go toolchain: <version>
   - govulncheck: <version>
   - callgraph: available
   - digraph: available
   
   Proceeding with full-confidence CVE analysis...
   ```

**Decision Point:**
- IF ANY tool missing → Display installation instructions → Exit with error
- IF ALL tools present → Continue to Phase 1

---

### Phase 1: CVE Intelligence Gathering

**Note**: This is a complex information gathering process - see skill documentation for full details  
**Skill**: [cve-intelligence-gathering](../../skills/cve-intelligence-gathering/SKILL.md)

**Summary**:

1. **Validate CVE Format**
   - Verify CVE ID follows standard format (e.g., CVE-2024-1234)
   - Extract year and number components
   
**Decision Point:**
- IF invalid format → Exit with error message
- OTHERWISE → Continue with CVE lookup

2. **Fetch CVE Details from Multiple Sources**
   
   Use web_search tool to gather information from these sources:
   
   - **Primary Sources**: NVD, MITRE
   - **Go-Specific Sources**: Go vulnerability database, GitHub Security Advisories
   - **Remediation Sources**: Security advisories, fix commits, release notes
   
3. **Handle Search Issues and Limited Results**
   - Try alternative search strategies
   - Check if govulncheck knows about it
   - Request user input as fallback
   - Document information sources
   
4. **Compile Vulnerability Profile**
   - Severity, CVSS scores, affected versions
   - Fixed versions and remediation guidance
   - Clearly mark information sources (verified vs user-provided)
   - Assess information completeness and Go relevance

**For detailed implementation of CVE gathering**, refer to the [cve-intelligence-gathering skill](../../skills/cve-intelligence-gathering/SKILL.md).

**Decision Point After Phase 1:**
- IF CVE details NOT found (no web results + user declined to provide info) → Exit with error
- IF CVE is not Go-related (affects other languages/platforms only) → Generate "Not Applicable" report and exit
- IF CVE details found (from any source) → Continue to Phase 2
- IF only partial information available → Note limitations and continue

---

### Phase 2: Codebase Impact Analysis

1. **Identify Go Module Dependencies**
   - Read `go.mod` file from workspace root
   - Parse direct and indirect dependencies
   - Extract module versions using `go list -m all`
   - Build dependency tree if needed

2. **Cross-Reference Vulnerable Packages**
   - **Method 1: Dependency Matching**
     - Compare CVE-affected packages with `go.mod` dependencies
     - Check if affected package versions are in use
     - Account for version ranges and semantic versioning
   
   - **Method 2: Go Vulnerability Scanner**
     - Run `govulncheck` if available in the environment
     - Command: `govulncheck ./...`
     - Parse output for CVE matches
     - Alternative: Use `go list -json -m all` and cross-reference
   
   - **Method 3: Direct Dependency Check**
     - Use `go list` to verify package presence
     - Command: `go list -mod=mod <vulnerable-package>`
     - Confirms package is included (directly or transitively)
     - Note: This alone doesn't prove vulnerable functions are called
   
   - **Method 4: Call Graph Reachability Analysis** (Highest Confidence)
     - **Note**: This is a complex analysis - see skill documentation for full details
     - **Skill**: [call-graph-analysis](../../skills/call-graph-analysis/SKILL.md)
     - **Summary**:
       - Build complete program call graph using `callgraph` tool
       - Search for vulnerable function in graph nodes
       - Trace execution paths from main() to vulnerable function
       - Generate visual DOT/SVG graphs showing call chains
       - Provides definitive proof of reachability
     - **Only run if**:
       - `callgraph` and `digraph` tools are available (checked in Phase 0)
       - Codebase compiles successfully
       - Highest confidence assessment is needed
     - **Output**:
       - Reachability verdict (reachable/not reachable/uncertain)
       - Call chain text (e.g., "main → handler → parse → VULN")
       - Visual graph file: `callgraph.svg`
     - **For detailed implementation**, refer to the skill documentation
   
   - **Method 5: Source Code Analysis**
     - Search for import statements of vulnerable packages
     - Use grep/codebase_search to find package usage
     - Identify actual code paths that use vulnerable functions
     - Check if vulnerable functions are called in reachable code

3. **Verify Impact with Multiple Methods & Confidence Levels**
   
   Use multiple verification layers, with each providing increasing confidence:
   
   - **Level 1: Basic Presence (Low Confidence)**
     - Check `go.mod` for vulnerable package
     - Run: `go list -mod=mod <vulnerable-package>`
     - Result: Confirms package is a dependency (direct or transitive)
     - ⚠️ Limitation: Doesn't prove the vulnerable code is actually used
   
   - **Level 2: Import & Version Analysis (Medium Confidence)**
     - Verify package is imported in source code (grep/codebase_search)
     - Check version is in vulnerable range
     - Search for vulnerable function/method names in codebase
     - ⚠️ Limitation: Function may exist but not be in reachable code paths
   
   - **Level 3: Vulnerability Scanner (Medium-High Confidence)**
     - Run `govulncheck ./...` (official Go vulnerability checker)
     - Performs reachability analysis automatically
     - Reports if vulnerable functions are actually called
     - ✓ Advantage: Maintained by Go team, knows about CVEs
   
   - **Level 4: Call Graph Reachability (Highest Confidence)**
     - Use `callgraph` + `digraph` to prove execution path exists
     - Trace from `main()` (or test entry points) to vulnerable function
     - Generate visual call graph showing exact path
     - ✓ Advantage: Provides definitive proof with traceable evidence
     - Shows complete call chain from entry points to vulnerable functions
   
   - **Level 5: Configuration & Context Analysis**
     - Review if vulnerable features are actually enabled
     - Check if vulnerable code paths are behind feature flags
     - Verify if inputs can reach vulnerable functions
     - Consider security controls (input validation, sandboxing)
   
   **Recommended Approach**: Use multiple methods and determine confidence level based on:
   - **Quality of evidence**: How definitive is the proof?
   - **Number of verification methods**: More methods = higher confidence
   - **Reachability analysis**: Can vulnerable code actually execute?
   - **Context factors**: Configuration, feature flags, input paths
   
   **Assign confidence level by evaluating:**
   - What evidence do we have? (presence, usage, reachability)
   - How strong is each piece of evidence?
   - Are there mitigating factors? (dead code, disabled features)
   - What are the gaps in our analysis?
   
   **Confidence determination should be data-driven, not formula-based.**

4. **Build Evidence Package**
   
   Collect comprehensive evidence for the report:
   
   - **Dependency Evidence**:
     - `go.mod` entries showing vulnerable package
     - `go list` output confirming presence
     - Version information from `go list -m <package>`
   
   - **Static Code Evidence**:
     - File paths where vulnerable packages are imported
     - Line numbers where vulnerable functions are called
     - Code snippets showing usage context
   
   - **Reachability Evidence** (if call graph analysis performed):
     - Call graph output showing vulnerable function in nodes
     - Execution path from entry points to vulnerable code
     - DOT graph visualization (saved to `.work/compliance/analyze-cve/{CVE-ID}/callgraph.svg`)
     - Complete call chain as text (e.g., "main → handler → parse → VULN")
   
   - **Scanner Evidence**:
     - `govulncheck` output (full text)
     - Vulnerability findings with line numbers
   
   - **Mitigation Factors**:
     - Input validation or sanitization in place
     - Vulnerable features disabled by configuration
     - Code behind feature flags or conditional execution
     - Security controls limiting exposure
   
   - **Confidence Assessment**:
     - List which verification methods were used
     - Assign overall confidence level based on evidence
     - Note any gaps in analysis or areas needing manual review

**Decision Point After Phase 2:**
- IF clearly NOT AFFECTED:
  - Package not in dependencies → Generate "Not Affected" report (Phase 3) → Exit
  - Package present but version not vulnerable → Generate "Not Affected" report (Phase 3) → Exit
  - Dead code (no reachable path found) → Generate "Not Affected" report (Phase 3) → Exit

- IF clearly AFFECTED:
  - High confidence (call graph shows reachable path OR govulncheck confirms) → Generate "Affected" report (Phase 3) → Proceed to Phase 4 (Remediation)
  - Medium confidence (package + version + usage found) → Generate "Likely Affected" report (Phase 3) → Proceed to Phase 4 (Remediation)

- IF UNCLEAR:
  - Low confidence (package present but no usage evidence) → Generate "Possibly Affected - Manual Review Needed" report (Phase 3) → Offer to continue to Phase 4 or exit
  - Conflicting signals → Generate "Unclear - Manual Review Needed" report (Phase 3) → Offer to continue to Phase 4 or exit

---

### Phase 3: Report Generation

1. **Create Analysis Report**
   - Location: `.work/compliance/analyze-cve/{CVE-ID}/report.md`
   - Additional artifacts as generated: 
     - `callgraph.svg` (if call graph analysis was performed)
     - `govulncheck-output.txt` (if scanner was run)
     - `evidence.json` (structured evidence data)
   
   **Design the report structure based on the analysis performed:**
   
   - **Start with Executive Summary**:
     - What's the bottom-line conclusion? (AFFECTED/NOT AFFECTED/UNKNOWN)
     - What's the confidence level and why?
     - What should the reader know immediately?
   
   - **Present CVE Context**:
     - What is this vulnerability?
     - Where did the information come from?
     - Tag information sources clearly (verified vs. user-provided)
     - What packages/functions are affected?
   
   - **Explain the Analysis**:
     - What methods were used to assess impact?
     - Why were those methods chosen?
     - What tools were available and used?
     - How was confidence determined?
     - Show the reasoning, not just the results
   
   - **Present Findings**:
     - What was found in the codebase?
     - Include specific evidence (file paths, versions, code snippets)
     - If reachability was analyzed, explain the findings
     - Connect evidence to conclusions
   
   - **Assess Risk**:
     - Consider: severity + actual exposure + exploitability in THIS context
     - Don't just repeat CVSS score - interpret it for this codebase
     - Account for mitigating factors
   
   - **Provide Next Steps**:
     - If affected: specific remediation guidance
     - If not affected: explain why and suggest monitoring
     - If unclear: recommend manual review steps
     - Prioritize based on risk assessment
   
   - **Document Sources and Limitations**:
     - What sources were consulted?
     - What tools/versions were used?
     - What are the gaps or limitations?
     - When was this analysis performed?

2. **Format Report for Clarity**
   - Use clear, readable markdown
   - Add visual indicators (badges, icons) for key information
   - Include code blocks for evidence
   - Link to external references
   - Make recommendations actionable
   - **Distinguish information quality**:
     - Verified from authoritative sources
     - Based on user-provided information
     - Inferred or uncertain information

**Decision Point After Phase 3:**
- IF verdict is "NOT AFFECTED" → Exit (no remediation needed)
- IF verdict is "AFFECTED" or "LIKELY AFFECTED" → Continue to Phase 4 (Remediation Guidance)
- IF verdict is "UNCLEAR" or "POSSIBLY AFFECTED":
  - Ask user: "Manual review is recommended. Would you like remediation guidance anyway?"
  - IF yes → Continue to Phase 4
  - IF no → Exit

---

### Phase 4: Remediation Guidance (Conditional - Only for Affected Code)

**Note**: This is a complex planning process - see skill documentation for full details  
**Skill**: [remediation-planning](../../skills/remediation-planning/SKILL.md)

**Summary**:

1. **If Codebase is NOT Affected**
   - Explain why (version not vulnerable, package not used, etc.)
   - Suggest preventive measures
   - Recommend ongoing monitoring

2. **If Codebase IS Affected**
   
   Generate comprehensive remediation plan including:
   
   - **Dependency Update Strategy**
     - Direct vs indirect dependency handling
     - Exact `go get` commands
     - Version compatibility assessment
     - Breaking change analysis
   
   - **Code Changes** (if required)
     - API migration steps
     - Before/after examples
     - Files requiring updates
   
   - **Workarounds** (if no fix available)
     - Input validation
     - Rate limiting
     - Feature disabling
     - Alternative libraries
   
   - **Project-Specific Build Commands**
     - Detect Makefile targets
     - Prefer `make verify`, `make build`, `make test`
     - Fall back to standard Go commands
   
   - **Verification Plan**
     - Dependency verification
     - Build verification
     - Test execution
     - Vulnerability re-check with govulncheck
   
   - **Risk Assessment**
     - Update complexity (LOW/MEDIUM/HIGH)
     - Estimated effort
     - Rollback plan

**For detailed implementation of remediation planning**, refer to the [remediation-planning skill](../../skills/remediation-planning/SKILL.md).

**Decision Point After Phase 4:**
- Present remediation guidance to user
- Ask: "Would you like me to apply these fixes automatically?"
- IF yes → Continue to Phase 5 (Apply Fixes)
- IF no → Exit with report and manual instructions

---

### Phase 5: Interactive Fix Application (Conditional - Only with User Approval)

1. **Present Remediation Plan**
   - Show complete analysis report
   - Highlight critical findings
   - List all proposed fixes

2. **Ask User for Permission**
   - "Would you like me to apply these fixes automatically?"
   - Wait for explicit user confirmation
   - Do NOT proceed without approval

3. **If User Approves, Apply Fixes**
   - **Update go.mod and go.sum**
     - Run `go get -u <package>@<fixed-version>`
     - Run `go mod tidy` to clean up
   
   - **Modify Source Code** (if required)
     - Apply code changes identified in Phase 4
     - Use search_replace or write tools
     - Maintain code style and formatting
   
   - **Verify Changes**
     - Check if project has Makefile with common targets
     - **For verification**:
       - Try `make verify` first (if target exists)
       - Fallback: `go mod verify`
     - **For building**:
       - Try `make build` first (if target exists)
       - Fallback: `go build ./...`
     - **For testing**:
       - Try `make test` first (if target exists)
       - Fallback: `go test ./...`
     - **Re-check vulnerability**:
       - Run `govulncheck ./...` to confirm fix

4. **Document Changes**
   - Create summary of changes made
   - List files modified
   - Provide git diff summary
   - Suggest commit message

## Return Value

- **Format**: Markdown report at `.work/compliance/analyze-cve/{CVE-ID}/report.md`
- **Content**:
  - Vulnerability details and severity
  - Impact assessment (AFFECTED/NOT AFFECTED/UNCLEAR)
  - Evidence from codebase analysis
  - Specific remediation recommendations
  - Applied fixes (if user approved)

## Examples

1. **CVE analysis**:
   ```
   /compliance:analyze-cve CVE-2024-45338
   ```
   Analyzes the codebase for CVE-2024-45338

## Arguments

- `<CVE-ID>`: The CVE identifier to analyze (e.g., CVE-2024-1234, CVE-2023-45678)
  - Format: CVE-YYYY-NNNNN
  - Case insensitive
  - Required argument

## Notes

- The command focuses on Go-specific vulnerabilities
- **Flexible Information Sources**:
  - Prefers automatic CVE lookup from authoritative sources (NVD, MITRE, Go vulndb)
  - Falls back to user-provided information if internet access fails or CVE data is unavailable
  - Clearly distinguishes between verified and user-provided information in reports
- Analysis may take several minutes for complex codebases
- If `govulncheck` is not installed, the command will use alternative methods
- The command does NOT make changes without explicit user approval
- Generated reports are saved locally and not committed to git
- **When providing manual CVE information**, include as much detail as possible:
  - Affected Go package/module names
  - Vulnerable and fixed version numbers
  - Severity and CVSS score (if known)
  - Links to security advisories or patches

## Prerequisites

All tools listed below are **REQUIRED**. The command will exit with an error if any are missing.

### Required Tools

1. **Go toolchain**
   - Check: `go version`
   - Install: https://go.dev/doc/install

2. **go.mod file**
   - Must exist in the workspace root
   - Create: `go mod init <module-name>`

3. **govulncheck** - Go's official vulnerability scanner
   ```bash
   go install golang.org/x/vuln/cmd/govulncheck@latest
   ```

4. **callgraph** - Call graph analysis
   ```bash
   go install golang.org/x/tools/cmd/callgraph@latest
   ```

5. **digraph** - Graph traversal tool
   ```bash
   go install golang.org/x/tools/cmd/digraph@latest
   ```

### Optional Tools

- **graphviz** - For visual call graph generation (recommended but not required)
  ```bash
  # macOS
  brew install graphviz
  # Linux
  sudo apt-get install graphviz
  ```

### Installation Quick Start

Install all required Go tools at once:
```bash
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest
```

### Internet Access

- **Recommended** for automatic CVE data fetching
- **Not required** if you can provide CVE details manually

**Note**: The command performs comprehensive tool validation in Phase 0. If any required tool is missing, you'll receive clear installation instructions and the command will exit without proceeding.

## Exit Conditions

- **Success**: Report generated with clear impact assessment based on complete information
- **Success with User Input**: Report generated based on user-provided CVE details when internet access fails
- **Partial Success**: Report generated but impact is unclear (needs manual review)
  - Marked with confidence level: "Low" or "Medium"
  - Includes recommendations for further investigation
- **Failure Scenarios**:
  - Invalid CVE format (must be CVE-YYYY-NNNNN)
  - User declines to provide information when automatic lookup fails
  - No Go-related information available (CVE is for different technology)
  - Insufficient information to proceed with analysis

