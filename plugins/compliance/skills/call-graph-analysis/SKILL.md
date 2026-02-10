---
name: Call Graph Reachability Analysis
description: Perform definitive call graph analysis to prove whether vulnerable functions are reachable from program entry points
---

# Call Graph Reachability Analysis

Provides highest-confidence vulnerability assessment by proving whether vulnerable functions can actually be reached during program execution.

## When to Use This Skill

Use this skill when:
- You need definitive proof that a vulnerable function is or isn't reachable
- Medium/high confidence analysis shows possible vulnerability but needs confirmation
- Generating evidence for security compliance or audit requirements
- `govulncheck` is unavailable or didn't find the CVE
- You need visual proof of execution paths for stakeholders

## Prerequisites

### Required Tools
- `callgraph`: `go install golang.org/x/tools/cmd/callgraph@latest`
- `digraph`: `go install golang.org/x/tools/cmd/digraph@latest`
- Go workspace with `go.mod` file

### Optional Tools
- `graphviz` (for visualization): `brew install graphviz` (macOS) or `sudo apt-get install graphviz` (Linux)
- `sfdp` or `dot` command (part of graphviz)

### Input Requirements
- CVE vulnerable function signature (e.g., `<package-path>.<function-name>`)
- Package path from CVE analysis
- Workspace path to analyze
- Algorithm preference (optional, default: `vta`) — passed via `--algo` from parent command

## Timeout and Algorithm Convention

- Use the algorithm specified by the user via `--algo` (default: `vta`).
- All `callgraph` invocations use `timeout 300` (5 minutes) to prevent hanging on large codebases.
- If the chosen algorithm times out: fall back to the next faster algorithm (`vta` → `rta` → `cha`), then narrow scope to specific packages (e.g., `./cmd/...`, `./pkg/...`).

## Implementation Steps

### Step 1: Verify Tools Are Available

```bash
# Check for callgraph
which callgraph || echo "callgraph not found - install with: go install golang.org/x/tools/cmd/callgraph@latest"

# Check for digraph
which digraph || echo "digraph not found - install with: go install golang.org/x/tools/cmd/digraph@latest"

# Optional: Check for graphviz
which sfdp || echo "graphviz not found - visual graphs won't be generated (optional)"
```

**Decision Point:**
- IF callgraph OR digraph missing → Exit this skill, return to parent analysis
- IF both present → Continue

### Step 2: Build Complete Call Graph

```bash
# ALGO defaults to "vta" unless user specified --algo
ALGO="${USER_ALGO:-vta}"

# Build call graph from workspace root
# Timeout after 300s (5 minutes) to avoid hanging on large codebases
timeout 300 callgraph -algo "${ALGO}" -format=digraph . > /tmp/callgraph.txt
```

**Error Handling:**
- IF build fails (compilation errors) → Note in report that call graph cannot be built
- IF command times out → Fall back to next faster algorithm (`vta` → `rta` → `cha`) and retry
- IF all algorithms time out → Narrow scope: `timeout 300 callgraph -algo rta -format=digraph ./cmd/... ./pkg/... > /tmp/callgraph.txt`
- IF successful → Continue to Step 3

**Output:** `/tmp/callgraph.txt` containing the full program call graph

### Step 3: Check if Vulnerable Function Exists in Graph

Extract the vulnerable function signature from CVE details.

```bash
# Search for exact function in the cached call graph
VULN_FUNC="<package-path>.<vulnerable-function>"
cat /tmp/callgraph.txt | digraph nodes | grep "${VULN_FUNC}$"
```

**Decision Point:**
- IF function found → Continue to Step 4
- IF function NOT found → Report as LOW RISK → Recommend manual review → Exit skill

### Step 4: Find Execution Paths from Entry Points

Search for paths from main entry points to the vulnerable function.

```bash
# Find path from main() to vulnerable function using cached call graph
ENTRY_POINT="command-line-arguments.main"
VULN_FUNC="<package-path>.<vulnerable-function>"

cat /tmp/callgraph.txt | \
  digraph somepath "${ENTRY_POINT}" "${VULN_FUNC}"
```

**Alternative Entry Points to Check:**
- `command-line-arguments.main` (main program)
- Test entry points: `*_test.go` test functions
- Init functions: `*.init`
- HTTP handlers if it's a web service

**Interpretation:**
- IF path found → Vulnerable function IS reachable → HIGH RISK
- IF no path found → Check alternative entry points
- IF still no path → Function may be in unreachable code → MEDIUM RISK

**Output:** Text representation of call chain or empty result

### Step 5: Generate DOT Graph for Visualization

If path exists, generate visual representation:

```bash
# Generate DOT format from cached call graph
cat /tmp/callgraph.txt | \
  digraph somepath "${ENTRY_POINT}" "${VULN_FUNC}" | \
  digraph to dot > /tmp/callgraph.dot

# Convert to SVG (if graphviz available)
if which sfdp > /dev/null; then
  sfdp -Tsvg -ocallgraph.svg -Goverlap=scale /tmp/callgraph.dot
  echo "Visual graph saved to: callgraph.svg"
else
  echo "Graphviz not available - DOT file saved to: /tmp/callgraph.dot"
fi
```

**Output Files:**
- `/tmp/callgraph.dot` - DOT notation of call path
- `callgraph.svg` - Visual graph (if graphviz available)

### Step 6: Parse and Format Call Chain

Extract human-readable call chain from digraph output:

```bash
# Get call chain as text from cached call graph
cat /tmp/callgraph.txt | \
  digraph somepath "${ENTRY_POINT}" "${VULN_FUNC}" | \
  digraph to dot | \
  grep " -> " | \
  sed 's/"//g' | \
  sed 's/;//g'
```

**Example Output:**
```
command-line-arguments.main -> <package-path>.Handler
<package-path>.Handler -> <package-path>.ProcessFunction
<package-path>.ProcessFunction -> <vulnerable-package>.<vulnerable-function>
```

**Format for Report:**
```
Execution Path Found:
main → Handler → ProcessFunction → <vulnerable-function> (VULNERABLE)
```

### Step 7: Assess Risk Level

**HIGH RISK:**
- Reachable path from main() to vulnerable function
- Action: Proceed to remediation

**MEDIUM RISK:**
- Function in graph but no direct path from main()
- Action: Recommend manual review + remediation

**LOW RISK:**
- Function not found in call graph
- Action: Recommend manual review to confirm

## Return Value

Return structured result to parent analysis:

```json
{
  "method": "call-graph-reachability",
  "algorithm": "vta",
  "vulnerable_function": "<package-path>.<vulnerable-function>",
  "found_in_graph": true,
  "reachable_from_main": true,
  "call_chain": "main → Handler → ProcessFunction → <vulnerable-function>",
  "risk_level": "HIGH",
  "evidence": {
    "dot_file": "/tmp/callgraph.dot",
    "svg_file": "callgraph.svg"
  }
}
```

## Error Handling

### Build Failures
- IF project doesn't compile → Note in report, cannot perform call graph analysis
- Suggest: Fix compilation errors first

### Very Large Codebases
- IF chosen algorithm times out (>5 minutes) → Fall back to next faster algorithm (`vta` → `rta` → `cha`)
- IF all algorithms time out → Narrow scope: `timeout 300 callgraph -algo rta -format=digraph ./cmd/... ./pkg/... > /tmp/callgraph.txt`

### Missing Entry Points
- IF `command-line-arguments.main` not found → Look for other entry points
- Web services: Check HTTP handler registrations
- Libraries: Note that call graph analysis may not be applicable

### Tool Installation Issues
- IF tools cannot be installed → Fall back to lower confidence methods
- Document limitation in final report

## Example: Generic Analysis Workflow

```bash
# Step 1: Build call graph (default: vta; user can override with --algo)
$ timeout 300 callgraph -algo vta -format=digraph . > /tmp/callgraph.txt

# Step 2: Check if function is called
$ cat /tmp/callgraph.txt | digraph nodes | grep "<package-path>.<vulnerable-function>$"
<package-path>.<vulnerable-function>

# Step 3: Find path from main
$ cat /tmp/callgraph.txt | digraph somepath command-line-arguments.main <package-path>.<vulnerable-function>
digraph {
    "command-line-arguments.main" -> "<app-package>.Handler";
    "<app-package>.Handler" -> "<app-package>.ProcessFunction";
    "<app-package>.ProcessFunction" -> "<intermediate-package>.HelperFunction";
    "<intermediate-package>.HelperFunction" -> "<vulnerable-package>.<vulnerable-function>";
}

# Step 4: Generate visual graph
$ cat /tmp/callgraph.txt | digraph somepath command-line-arguments.main <package-path>.<vulnerable-function> | digraph to dot | sfdp -Tsvg -ocallgraph.svg

# Result: HIGH RISK — reachable path found
# Call chain: main → Handler → ProcessFunction → HelperFunction → <vulnerable-function>
```

## Integration with Parent Command

This skill is called from Phase 2, Method 4 of the `/compliance:analyze-cve` command.

**When to Invoke:**
- After basic dependency checks show package is present
- When highest confidence assessment is needed
- When tools are available (checked in Phase 0)

**Return to Parent:**
- Provide risk level (HIGH/MEDIUM/LOW)
- Include evidence (call chain, graph files)
- Update report with reachability findings

