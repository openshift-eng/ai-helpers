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

### Phase 1: CVE Intelligence Gathering

1. **Validate CVE Format**
   - Verify CVE ID follows standard format (e.g., CVE-2024-1234)
   - Extract year and number components

2. **Fetch CVE Details from Multiple Sources**
   
   Use web_search tool to gather information from these sources:
   
   - **Primary Sources**:
     - **NVD**: Search for "CVE-{ID} site:nvd.nist.gov"
       - URL pattern: https://nvd.nist.gov/vuln/detail/{CVE-ID}
       - Extract: CVSS score, severity, affected versions, vulnerability type
     
     - **MITRE**: Search for "CVE-{ID} site:cve.mitre.org"
       - URL pattern: https://cve.mitre.org/cgi-bin/cvename.cgi?name={CVE-ID}
       - Extract: Description, references, CWE classification
   
   - **Go-Specific Sources**:
     - **Go Vulnerability Database**: Search for "CVE-{ID} golang vulnerability"
       - Check: https://go.dev/security/vuln/
       - Search GitHub: "CVE-{ID} site:github.com/golang/vulndb"
       - Extract: Affected Go packages, versions, fix versions
     
     - **GitHub Security Advisories**: Search for "CVE-{ID} golang GHSA"
       - May have GHSA-* aliases
       - Often contains detailed remediation steps
   
   - **General Go Security**: 
     - Search: "CVE-{ID} golang fix" or "CVE-{ID} go security"
     - Look for blog posts, security advisories, and discussions

3. **Handle Search Issues and Limited Results**
   
   - **If CVE details cannot be fetched** (network error, search failure, insufficient results):
     - Inform user about the lookup issue
     - Try alternative search strategies:
       - Search for package name + "vulnerability" + year
       - Search for GHSA (GitHub Security Advisory) aliases
       - Check if govulncheck finds it (most reliable for Go CVEs)
     - If still unsuccessful, ask user to provide available information:
       - CVE description and severity
       - Affected Go packages/modules
       - Vulnerable version ranges
       - Fixed versions (if known)
       - Any relevant links or references
     - Document the source as "User-provided information"
     - Note limitations in final report
   
   - **If CVE is very new** (e.g., CVE-2025-xxxxx):
     - May not be in NVD or Go vulndb yet
     - Search for: "CVE-{ID} disclosure" or "CVE-{ID} advisory"
     - Check vendor security pages directly
     - Run govulncheck anyway - it may know about it via GHSA
   
   - **If suggested fixes cannot be found**:
     - Check the package's GitHub releases for recent security fixes
     - Look for security-related commits in the repository
     - Ask user if they have:
       - Official security advisories
       - Patch information
       - Workaround documentation
       - Any relevant fix details
     - Proceed with available information
     - Clearly mark sections as "Based on user input" vs "Verified online"

4. **Gather Remediation Intelligence**
   - Search for:
     - Official security advisories
     - GitHub Security Advisories (GHSA)
     - Vendor patches and updates
     - Community discussions on GitHub, Go forums
   - Follow hyperlinks to:
     - Pull requests with fixes
     - Security mailing list threads
     - Blog posts with analysis
     - Proof-of-concept exploits (for context)
   - If searches fail or return insufficient results:
     - Request user input for any known fixes or workarounds
     - Accept partial information and document gaps

5. **Compile Vulnerability Profile**
   - Create structured summary with:
     - CVE ID and aliases (GHSA-*, etc.)
     - Severity and CVSS metrics
     - Affected packages/modules
     - Vulnerable version ranges
     - Fixed versions
     - Attack vectors and prerequisites
     - Impact assessment (confidentiality, integrity, availability)
     - Recommended mitigations
   - **Clearly distinguish**:
     - Information from authoritative sources (NVD, MITRE, etc.)
     - Information from web searches
     - Information provided by user
     - Information gaps or uncertainties

### Phase 2: Codebase Impact Analysis

1. **Identify Go Module Dependencies**
   - Read `go.mod` file from workspace root
   - Parse direct and indirect dependencies
   - Extract module versions using `go list -m all`
   - Build dependency tree if needed

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
     - Parse the `go mod graph` output to find all paths from root module to vulnerable package
     - Algorithm:
       1. Build directed graph from mod-graph.txt
       2. Find root module (the first module in graph, usually your project)
       3. Perform BFS/DFS to find all paths to vulnerable package
       4. Collect all unique paths

     - Example Python script to parse graph (save to `.work/compliance/analyze-cve/{CVE-ID}/parse_deps.py`):
       ```python
       #!/usr/bin/env python3
       import sys
       from collections import defaultdict, deque

       def parse_mod_graph(filename):
           """Parse go mod graph output into adjacency list"""
           graph = defaultdict(list)
           all_modules = set()

           with open(filename) as f:
               for line in f:
                   if not line.strip():
                       continue
                   parts = line.strip().split()
                   if len(parts) >= 2:
                       source, target = parts[0], parts[1]
                       graph[source].append(target)
                       all_modules.add(source)
                       all_modules.add(target)

           return graph, all_modules

       def find_all_paths(graph, start, target, max_depth=20):
           """Find all paths from start to target using BFS"""
           paths = []
           queue = deque([(start, [start])])

           while queue:
               current, path = queue.popleft()

               if len(path) > max_depth:
                   continue

               if current == target or current.startswith(target.split('@')[0]):
                   paths.append(path)
                   continue

               for neighbor in graph.get(current, []):
                   if neighbor not in path:  # Avoid cycles
                       queue.append((neighbor, path + [neighbor]))

           return paths

       def extract_package_name(module):
           """Extract package name without version"""
           return module.split('@')[0] if '@' in module else module

       def format_tree(path, indent_char="│   ", last_indent="└── ", mid_indent="├── "):
           """Format a path as a tree structure"""
           lines = []
           for i, module in enumerate(path):
               pkg_name = extract_package_name(module)
               version = module.split('@')[1] if '@' in module else 'unknown'

               if i == 0:
                   lines.append(f"{pkg_name} {version}")
               else:
                   prefix = indent_char * (i - 1)
                   branch = last_indent if i == len(path) - 1 else mid_indent
                   lines.append(f"{prefix}{branch}{pkg_name} {version}")

           return "\n".join(lines)

       if __name__ == "__main__":
           if len(sys.argv) < 3:
               print("Usage: parse_deps.py <mod-graph.txt> <vulnerable-package>")
               sys.exit(1)

           graph_file = sys.argv[1]
           vulnerable_pkg = sys.argv[2]

           graph, modules = parse_mod_graph(graph_file)

           # Find root module (first line's first module)
           with open(graph_file) as f:
               root = f.readline().strip().split()[0]

           # Find all paths to vulnerable package
           paths = find_all_paths(graph, root, vulnerable_pkg)

           if not paths:
               print(f"No dependency path found to {vulnerable_pkg}")
               print("\nSearching for similar packages:")
               pkg_base = vulnerable_pkg.split('@')[0]
               similar = [m for m in modules if pkg_base in m]
               for m in similar[:10]:
                   print(f"  - {m}")
               sys.exit(1)

           # Output results
           print(f"Found {len(paths)} dependency path(s) to {vulnerable_pkg}:\n")

           for i, path in enumerate(paths, 1):
               print(f"Path {i}:")
               print(format_tree(path))
               print(f"\nPath length: {len(path)} modules")

               # Identify dependency type
               if len(path) == 2:
                   print("Dependency type: DIRECT")
               else:
                   print(f"Dependency type: TRANSITIVE (via {extract_package_name(path[1])})")
               print()
       ```

     - Run the script:
       ```bash
       python3 .work/compliance/analyze-cve/{CVE-ID}/parse_deps.py \
         .work/compliance/analyze-cve/{CVE-ID}/mod-graph.txt \
         "golang.org/x/net@v0.0.0-20211015210444"
       ```

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

       **Option 1: Direct Upgrade** (if possible)
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
     - Example output shows complete call chain:
       ```
       main → MyHandler → ParseHTML → html.Parse (VULNERABLE)
       ```
   
   - **Level 5: Configuration & Context Analysis**
     - Review if vulnerable features are actually enabled
     - Check if vulnerable code paths are behind feature flags
     - Verify if inputs can reach vulnerable functions
     - Consider security controls (input validation, sandboxing)
   
   **Recommended Approach**: Use multiple methods and assign confidence:
   - **High Confidence (DEFINITELY AFFECTED)**: 
     - Call graph shows reachable path AND version is vulnerable
     - OR govulncheck explicitly reports the CVE
   - **Medium Confidence (LIKELY AFFECTED)**:
     - Package present + vulnerable version + function calls found
     - But no call graph or reachability proof
   - **Low Confidence (POSSIBLY AFFECTED)**:
     - Vulnerable package present but no direct usage evidence
   - **Not Affected**:
     - Package not present OR version not vulnerable OR dead code

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
     - `parse_deps.py` (Python script for dependency analysis)
   
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

2. **Format Report**
   - Use clear markdown formatting
   - Include severity badges
   - Add code blocks for examples
   - Link to external references
   - Provide actionable recommendations
   - **Clearly mark user-provided information** with labels like:
     - "⚠️ Based on user-provided information"
     - "✓ Verified from authoritative sources"
     - "⚠️ Partial information - manual verification recommended"

### Phase 4: Remediation Guidance

1. **If Codebase is NOT Affected**
   - Explain why (version not vulnerable, package not used, etc.)
   - Suggest preventive measures
   - Recommend ongoing monitoring

2. **If Codebase IS Affected**
   - Provide specific remediation steps:
     1. **Update Dependencies**
        - Exact `go get` commands to upgrade packages
        - Target version that fixes the CVE
        - Consider semantic versioning compatibility
        - Note: Use `go mod tidy` after updates
     
     2. **Code Changes** (if needed)
        - Identify functions that need modification
        - Provide before/after code examples
        - Explain breaking changes if any
     
     3. **Workarounds** (if no fix available)
        - Suggest temporary mitigations
        - Configuration changes to reduce risk
        - Input validation or sanitization
     
     4. **Verification Commands**
        - Check for project's Makefile first
        - Prefer project-specific make targets: `make verify`, `make build`, `make test`
        - Fall back to standard Go commands if no Makefile
        - Command to check for make targets: `make -qp | grep "^[a-zA-Z]" | head -20`
     
     5. **Testing Recommendations**
        - Suggest tests to verify the fix
        - Security test cases to add
        - Regression testing guidance
        - Re-run `govulncheck` to confirm vulnerability is resolved

### Phase 5: Interactive Fix Application

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

- **Required**:
  - Go toolchain installed (`go version` should work)
  - Read access to `go.mod` and source files in the workspace

- **Recommended** (for comprehensive analysis):
  - Internet connectivity for automatic CVE data fetching
  - `govulncheck` - Go's official vulnerability checker
    ```bash
    go install golang.org/x/vuln/cmd/govulncheck@latest
    ```
  - `callgraph` & `digraph` - For reachability analysis (highest confidence)
    ```bash
    go install golang.org/x/tools/cmd/callgraph@latest
    go install golang.org/x/tools/cmd/digraph@latest
    ```
  - `sfdp` or `graphviz` - For call graph visualization (optional)
    ```bash
    # macOS
    brew install graphviz
    # Linux
    sudo apt-get install graphviz
    ```

- **Alternative**: If internet access is unavailable, be prepared to provide:
  - CVE description and details
  - Affected package information
  - Specific vulnerable function signatures
  - Remediation guidance from other sources

**Tool Availability Check**: The command will automatically detect which tools are available and use the most comprehensive methods possible. Missing tools will result in lower confidence levels but analysis will still proceed.

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

