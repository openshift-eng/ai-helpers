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
  - Sub-skill: [go-mod-dependency-paths](../skills/go-mod-dependency-paths/SKILL.md) — paths in `go mod graph` output (Phase 2, Method 2)
- **Input**: CVE profile from Phase 1, `--algo` preference
- **Output**: Risk level (HIGH/MEDIUM/LOW/NEEDS_REVIEW), evidence package, confidence assessment

2. **Build Dependency Tree Visualization**

   Create a comprehensive dependency tree showing how the vulnerable package is included:

   - **Method 1: Generate Dependency Graph**
     - Command: `go mod graph > .work/compliance/analyze-cve/{CVE-ID}/mod-graph.txt`
     - This produces pairs showing dependency relationships:
       ```
       your-module@v1.0.0 github.com/gin-gonic/gin@v1.8.0
       github.com/gin-gonic/gin@v1.8.0 golang.org/x/net@v0.0.0-20211015210444
       ```
     - Each line shows: `dependent-module dependency-module`

   - **Method 2: Find All Paths to Vulnerable Package**
     - **Skill**: [go-mod-dependency-paths](../skills/go-mod-dependency-paths/SKILL.md) — run the checked-in script (do not inline or rewrite the parser in the agent session).
     - After `mod-graph.txt` exists, from the **ai-helpers repository root** (path is stable for review and CI):
       ```bash
       python3 plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py \
         .work/compliance/analyze-cve/{CVE-ID}/mod-graph.txt \
         "<vulnerable-module@version-or-path>" \
         | tee .work/compliance/analyze-cve/{CVE-ID}/dependency-tree.txt
       ```
     - Use the module coordinate from the CVE profile; see the skill for `--max-depth` and matching rules.

   - **Method 3: Visual Dependency Tree (Text Format)**
     - Generate ASCII tree showing dependency chain
     - Example output format:
       ```
       your-app v1.0.0
       ├── github.com/gin-gonic/gin v1.8.0
       │   ├── golang.org/x/net v0.0.0-20211015210444 (VULNERABLE - CVE-2024-1234)
       │   └── github.com/gin-contrib/sse v0.1.0
       └── github.com/spf13/cobra v1.5.0
           └── golang.org/x/net v0.0.0-20211015210444 (VULNERABLE - CVE-2024-1234)

       Summary:
       - 2 paths lead to vulnerable package
       - Vulnerable package: golang.org/x/net v0.0.0-20211015210444
       - Dependency type: TRANSITIVE (indirect)
       - Introduced via: github.com/gin-gonic/gin, github.com/spf13/cobra
       ```
     - Save to: `.work/compliance/analyze-cve/{CVE-ID}/dependency-tree.txt`

   - **Method 4: Visual Dependency Graph (SVG Format)**
     - Use `graphviz` to create visual graph (optional, requires graphviz installed)
     - Generate DOT format:
       ```bash
       # Create DOT file from mod graph
       cat > .work/compliance/analyze-cve/{CVE-ID}/deps.dot << 'EOF'
       digraph dependencies {
         rankdir=LR;
         node [shape=box, style=rounded];

         // Highlight vulnerable package
         "vulnerable-pkg" [style=filled, fillcolor=red, fontcolor=white];

         // Add edges from go mod graph
         "your-app" -> "dep1";
         "dep1" -> "vulnerable-pkg";
       }
       EOF

       # Convert to SVG
       dot -Tsvg .work/compliance/analyze-cve/{CVE-ID}/deps.dot \
         -o .work/compliance/analyze-cve/{CVE-ID}/dependency-graph.svg
       ```
     - Alternative: Use `go mod graph | modgraphviz` if available
       ```bash
       # Install modgraphviz if not present
       go install golang.org/x/exp/cmd/modgraphviz@latest

       # Generate visual graph
       go mod graph | modgraphviz | dot -Tsvg \
         -o .work/compliance/analyze-cve/{CVE-ID}/dependency-graph.svg
       ```

   - **Method 5: Determine Dependency Classification**
     - Identify if the vulnerable package is:
       - **Direct dependency**: Listed in `go.mod` `require` section
       - **Transitive dependency**: Not in `go.mod` but pulled in by another package

     - Check direct dependencies:
       ```bash
       # List direct dependencies only
       go list -m -f '{{if not .Indirect}}{{.Path}}@{{.Version}}{{end}}' all | grep "<vulnerable-package>"

       # If found → DIRECT
       # If not found → TRANSITIVE
       ```

     - For transitive dependencies, identify immediate parent:
       ```bash
       # Use go mod why to understand why package is needed
       go mod why <vulnerable-package>
       ```
       Example output:
       ```
       # golang.org/x/net
       your-app
       github.com/gin-gonic/gin
       golang.org/x/net/http2
       ```

   - **Method 6: Analyze Upgrade Impact**
     - For each path to vulnerable package, check if intermediate dependencies constrain versions
     - Commands:
       ```bash
       # Check what version the parent package requires
       go mod graph | grep "github.com/gin-gonic/gin.*golang.org/x/net"

       # See if upgrading vulnerable package would break parent
       go list -m -json github.com/gin-gonic/gin | jq -r '.Require[] | select(.Path == "golang.org/x/net")'
       ```

     - Identify blockers:
       - If parent explicitly pins old version → upgrading vulnerable package may require upgrading parent
       - If multiple parents depend on different versions → version conflict possible

   - **Output Format**
     - Create structured report section with:
       ```markdown
       ## Dependency Tree Analysis

       **Vulnerable Package**: golang.org/x/net v0.0.0-20211015210444
       **CVE**: CVE-2024-1234
       **Dependency Type**: TRANSITIVE

       ### Dependency Paths (2 found)

       #### Path 1 (Shortest - Length: 3)
       ```
       your-app v1.0.0
       └── github.com/gin-gonic/gin v1.8.0
           └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
       ```

       #### Path 2 (Length: 3)
       ```
       your-app v1.0.0
       └── github.com/spf13/cobra v1.5.0
           └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
       ```

       ### Upgrade Strategy

       **Option 1: Direct Upgrade** (when `go get` on the vulnerable module succeeds without version conflicts)
       ```bash
       go get golang.org/x/net@v0.23.0  # Fixed version
       go mod tidy
       ```

       **Option 2: Upgrade Parent Packages** (recommended for transitive deps)
       ```bash
       go get github.com/gin-gonic/gin@latest
       go get github.com/spf13/cobra@latest
       go mod tidy
       ```

       **Blocking Dependencies**: None detected

       **Recommended Approach**:
       Since this is a transitive dependency, first try Option 1 (direct upgrade).
       If that causes conflicts, use Option 2 to upgrade parent packages.

       ### Visual Dependency Graph

       See: `.work/compliance/analyze-cve/{CVE-ID}/dependency-graph.svg`
       ```
     - Save detailed tree to: `.work/compliance/analyze-cve/{CVE-ID}/dependency-tree.txt`
     - Include in main report at: `.work/compliance/analyze-cve/{CVE-ID}/report.md`

3. **Cross-Reference Vulnerable Packages**
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
     - Example: `go list -mod=mod golang.org/x/net/html`
     - Confirms package is included (directly or transitively)
     - Note: This alone doesn't prove vulnerable functions are called
   
   - **Method 4: Call Graph Reachability Analysis** (Highest Confidence)
     - Build complete program call graph using `callgraph` tool
     - Search for vulnerable function signatures in the graph
     - Commands:
       ```bash
       # Check if vulnerable function exists in call graph
       callgraph -format=digraph . | digraph nodes | grep "<vulnerable-function-signature>"
       
       # Find execution path from main to vulnerable function
       callgraph -format=digraph . | digraph somepath command-line-arguments.main <vulnerable-function> | digraph to dot
       ```
     - Example (for CVE-2024-45338 affecting `golang.org/x/net/html.Parse`):
       ```bash
       # Step 1: Check if Parse is called anywhere
       callgraph -format=digraph . | digraph nodes | grep "golang.org/x/net/html.Parse$"
       
       # Step 2: Find path from main() to Parse()
       callgraph -format=digraph . | digraph somepath command-line-arguments.main golang.org/x/net/html.Parse
       ```
     - **Interpretation**:
       - If path exists: Code is DEFINITELY vulnerable (reachable code path)
       - If no path: Function may be dead code or only called conditionally
       - Generates DOT graph showing exact call chain
     - **Visualization** (optional):
       ```bash
       callgraph -format=digraph . | digraph somepath <entrypoint> <vulnerable-func> | digraph to dot | sfdp -Tsvg -o callgraph.svg
       ```
     - Prerequisites: Install tools if missing
       ```bash
       go install golang.org/x/tools/cmd/callgraph@latest
       go install golang.org/x/tools/cmd/digraph@latest
       ```
   
   - **Method 5: Source Code Analysis**
     - Search for import statements of vulnerable packages
     - Use grep/codebase_search to find package usage
     - Identify actual code paths that use vulnerable functions
     - Check if vulnerable functions are called in reachable code
**Decision Point:**
- IF HIGH RISK or MEDIUM RISK → Generate report (Phase 3) → Proceed to Phase 4
- IF LOW RISK → Generate report (Phase 3) → Recommend manual review → Exit
- IF NEEDS REVIEW → Generate report (Phase 3) → Ask user if they want remediation guidance
  - IF yes → Proceed to Phase 4
  - IF no → Exit

---

### Phase 3: Report Generation

1. **Create Analysis Report**
   - Location: `.work/compliance/analyze-cve/{CVE-ID}/report.md`
   - Additional artifacts:
     - `callgraph.svg` (if generated)
     - `govulncheck-output.txt` (if run)
     - `evidence.json` (structured evidence data)
     - `dependency-tree.txt` (dependency tree visualization)
     - `dependency-graph.svg` (visual dependency graph, if graphviz available)
     - `mod-graph.txt` (raw go mod graph output)
     - Path enumeration uses `plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py` (shipped with the plugin; not copied into `.work/`)
   
   - Include sections:
     - **Executive Summary**: 
       - Impact verdict (AFFECTED/NOT AFFECTED/UNKNOWN)
       - Confidence level badge (HIGH/MEDIUM/LOW)
       - Quick summary of findings
     
     - **CVE Details**: 
       - Full vulnerability information
       - Tag information sources (e.g., "Source: NVD", "Source: User-provided")
       - Affected package/function signatures
       - Vulnerability type and attack vector
     
     - **Analysis Methodology**:
       - List all verification methods used
       - Note which tools were available (callgraph, govulncheck, etc.)
       - Explain confidence level determination
       - Example:
         ```
         ✓ Method 1: Dependency check (go list) - POSITIVE
         ✓ Method 2: Version analysis - VULNERABLE VERSION FOUND
         ✓ Method 3: govulncheck scan - CVE REPORTED
         ✓ Method 4: Call graph analysis - REACHABLE PATH FOUND
         → Confidence: HIGH
         ```
     
     - **Dependency Analysis**:
       - Package versions from go.mod
       - Direct vs. transitive dependencies
       - Vulnerable package version range
       - **Dependency Tree** (enhanced section):
         - Number of paths to vulnerable package
         - Visual ASCII tree showing dependency chains
         - Dependency type classification (DIRECT or TRANSITIVE)
         - Parent packages that introduce the vulnerability
         - Upgrade impact analysis (version conflicts, blockers)
         - Link to visual dependency graph (if generated)
         - Example format:
           ```markdown
           ## Dependency Tree Analysis

           **Vulnerable Package**: golang.org/x/net v0.0.0-20211015210444
           **Dependency Type**: TRANSITIVE
           **Number of Dependency Paths**: 2

           ### Path 1 (Shortest - Length: 3)
           ```
           your-app v1.0.0
           └── github.com/gin-gonic/gin v1.8.0
               └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
           ```

           ### Path 2 (Length: 3)
           ```
           your-app v1.0.0
           └── github.com/spf13/cobra v1.5.0
               └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
           ```

           **Introduced via**: github.com/gin-gonic/gin, github.com/spf13/cobra
           **Blocking Dependencies**: None detected

           ### Upgrade Strategy
           - **Option 1**: Direct upgrade to golang.org/x/net@v0.23.0
           - **Option 2**: Upgrade parent packages to latest versions
           - **Recommended**: Try Option 1 first (simpler, less risk)

           **Visual Graph**: [dependency-graph.svg](./dependency-graph.svg)
           ```

     - **Impact Assessment**: 
       - Specific findings in codebase
       - File paths and line numbers
       - Code snippets showing vulnerable usage
       - **Reachability Analysis** (if performed):
         - Call chain from entry points to vulnerable functions
         - Visual call graph (link to SVG)
         - Interpretation of findings
     
     - **Risk Level**: 
       - Based on exploitability, exposure, and reachability
       - Consider CVSS score + actual codebase context
     
     - **Evidence**: 
       - All collected evidence organized by type
       - Terminal output from tools
       - Screenshots or links to visualizations
     
     - **Confidence Assessment**:
       - Final confidence: High/Medium/Low
       - Justification based on methods used
       - Gaps or limitations noted
       - Recommendations for additional verification if needed
     
     - **Remediation Steps**: 
       - Specific fixes needed (version updates, code changes)
       - Verification commands (prefer make targets, fallback to go commands)
       - Note which make targets are available in the project
       - Priority based on confidence level and risk
     
     - **References**: 
       - All sources consulted (automated + user-provided)
       - Tool versions used
       - Timestamp of analysis
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