# Compliance Plugin

Security compliance and vulnerability analysis tools for Go projects.

## Command

### `/compliance:analyze-cve <CVE-ID>`

Analyzes Go codebases to determine CVE impact with multi-level confidence assessment.

**Example:**
```
/compliance:analyze-cve CVE-2024-24783
```

**Features:**
- Fetches CVE details from NVD, MITRE, and Go Vulnerability Database
- **Dependency tree visualization** showing how vulnerable packages are included
- Multi-level verification (dependency check → static analysis → govulncheck → **call graph reachability**)
- Generates reports with confidence levels (HIGH/MEDIUM/LOW)
- Identifies direct vs transitive dependencies with upgrade strategies
- Provides exact remediation commands
- Optionally applies fixes with approval

**Output:**
- `.work/compliance/analyze-cve/{CVE-ID}/report.md` - Full analysis with confidence assessment
- `.work/compliance/analyze-cve/{CVE-ID}/dependency-tree.txt` - ASCII dependency tree visualization
- `.work/compliance/analyze-cve/{CVE-ID}/dependency-graph.svg` - Visual dependency graph (if graphviz available)
- `.work/compliance/analyze-cve/{CVE-ID}/callgraph.svg` - Visual execution path (if call graph analysis performed)
- `.work/compliance/analyze-cve/{CVE-ID}/govulncheck-output.txt` - Scanner results
- `.work/compliance/analyze-cve/{CVE-ID}/mod-graph.txt` - Raw dependency graph data

## Verification Levels

The command uses multiple methods with increasing confidence:

1. **Dependency check** → Confirms package presence
2. **Static analysis** → Finds function usage  
3. **govulncheck** → Official Go vulnerability scanner
4. **Call graph reachability** → Proves execution path (HIGHEST confidence)
5. **Context analysis** → Checks security controls

Reports include confidence level (HIGH/MEDIUM/LOW) based on verification methods used.

## Prerequisites

**Required:** Go toolchain

**Recommended (for higher confidence):**
```bash
# Go vulnerability tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest

# Optional: For visual graphs
brew install graphviz  # macOS
```

The command auto-detects available tools and uses the most comprehensive methods possible.

## Fallback Mode

If internet access fails, the command prompts for manual CVE information (description, affected packages, versions, fixes). Analysis proceeds with user-provided data, clearly marked in the report.

## Report Includes

- **Executive Summary**: Verdict (AFFECTED/NOT AFFECTED) with confidence level
- **Analysis Methodology**: Which verification methods were used
- **Impact Assessment**: Evidence from codebase, call chains (if found)
- **Remediation Steps**: Exact commands and fixes
- **Visual Artifacts**: Dependency tree, call graph SVG, scanner outputs

## Examples

### Basic usage
```
/compliance:analyze-cve CVE-2024-24783
```
Analyzes codebase for crypto/x509 vulnerability, provides upgrade command if affected.

### High-confidence analysis
```
/compliance:analyze-cve CVE-2024-45338
```
**Result:**
- Finds `golang.org/x/net/html v0.21.0` (vulnerable)
- Proves execution path: `main → HTTPHandler → ParseHTML → html.Parse`
- **Confidence**: HIGH | **Verdict**: AFFECTED
- Generates `callgraph.svg` showing call chain
- Recommends: `go get golang.org/x/net@v0.23.0`

### Dependency tree analysis
```
/compliance:analyze-cve CVE-2024-45338
```
**Result:**
- Identifies vulnerable package: `golang.org/x/net v0.0.0-20211015210444`
- Shows dependency tree:
  ```
  your-app v1.0.0
  ├── github.com/gin-gonic/gin v1.8.0
  │   └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
  └── github.com/spf13/cobra v1.5.0
      └── golang.org/x/net v0.0.0-20211015210444 ⚠️ VULNERABLE
  ```
- **Dependency Type**: TRANSITIVE (indirect)
- **Introduced via**: 2 packages (gin-gonic/gin, spf13/cobra)
- Provides upgrade strategy with options
- Generates visual `dependency-graph.svg`
