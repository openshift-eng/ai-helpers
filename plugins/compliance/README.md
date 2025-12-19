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
- Multi-level verification (dependency check → static analysis → govulncheck → **call graph reachability**)
- Generates reports with confidence levels (HIGH/MEDIUM/LOW)
- Provides exact remediation commands
- Optionally applies fixes with approval

**Output:**
- `.work/compliance/analyze-cve/{CVE-ID}/report.md` - Full analysis with confidence assessment
- `.work/compliance/analyze-cve/{CVE-ID}/callgraph.svg` - Visual execution path (if call graph analysis performed)
- `.work/compliance/analyze-cve/{CVE-ID}/govulncheck-output.txt` - Scanner results

## Verification Levels

The command uses multiple methods with increasing confidence:

1. **Dependency check** → Confirms package presence
2. **Static analysis** → Finds function usage  
3. **govulncheck** → Official Go vulnerability scanner
4. **Call graph reachability** → Proves execution path (HIGHEST confidence)
5. **Context analysis** → Checks security controls

Reports include confidence level (HIGH/MEDIUM/LOW) based on verification methods used.

## Prerequisites

**All tools are REQUIRED.** The command will exit with an error if any are missing.

```bash
# Install all required Go tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest

# Optional: For visual call graphs
brew install graphviz  # macOS
```

**Required:**
- Go toolchain (`go version`)
- `go.mod` file in workspace
- `govulncheck` - vulnerability scanner
- `callgraph` - call graph analysis
- `digraph` - graph traversal

The command validates all tools in Phase 0 and provides installation instructions if any are missing.

## Fallback Mode

If internet access fails, the command prompts for manual CVE information (description, affected packages, versions, fixes). Analysis proceeds with user-provided data, clearly marked in the report.

## Report Includes

- **Executive Summary**: Verdict (AFFECTED/NOT AFFECTED) with confidence level
- **Analysis Methodology**: Which verification methods were used
- **Impact Assessment**: Evidence from codebase, call chains (if found)
- **Remediation Steps**: Exact commands and fixes
- **Visual Artifacts**: Call graph SVG, scanner outputs

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
