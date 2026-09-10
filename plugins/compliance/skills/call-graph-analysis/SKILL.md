---
name: call-graph-analysis
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
- `CVE_ID` — used to construct the output directory
- `OUT_DIR` (optional, default: `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}`) — where artifacts are written; same workspace base as Phase 0.7's `REPOS_BASE`

## Critical Rules

> 1. **Always use `timeout -k 10`** — plain `timeout` sends SIGTERM but `callgraph` can ignore it when stuck in SSA construction or type resolution. `-k 10` sends SIGKILL after 10s grace, guaranteeing termination.
> 2. **Never run `callgraph` on `./...`** for repos with more than ~50 packages. Target specific main packages (e.g. `./cmd/controller`, `./main.go`) and let the tool pull in transitive deps automatically.
> 3. **Always redirect output to a file** (`> file 2>&1`). Never pipe callgraph output to another command — if the reader closes, callgraph can hang on SIGPIPE.

## Timeout and Algorithm Convention

- Use the algorithm specified by the user via `--algo` (default: `vta`).
- All `callgraph` invocations use `timeout -k 10 300` (5 minutes + 10s force-kill) to prevent hanging.
- Scope: target the **specific main package** (e.g. `./cmd/controller`), not `./...`. The `callgraph` tool resolves transitive deps automatically — there is no need to include the entire repo.
- If the chosen algorithm times out: fall back to the next faster algorithm (`vta` → `rta` → `cha`), then narrow scope further to a single binary entry point.

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

### Step 2: Identify Main Packages and Build Call Graph

First, discover the main packages that serve as entry points:

```bash
# Find main packages
MAIN_PKGS=$(find . -name "main.go" -exec dirname {} \; | sort -u)
echo "Main packages: ${MAIN_PKGS}"
```

Pick the most relevant main package for the analysis (typically the controller or server binary, not CLI tools or test helpers). If unsure, prefer the package that imports the vulnerable package's parent tree.

```bash
# Select exactly one TARGET_PKG before running callgraph
if [ -z "${TARGET_PKG:-}" ]; then
  TARGET_PKG=$(printf '%s\n' ${MAIN_PKGS} | grep -E '(^|/)(cmd/)?(controller|manager|operator|server|main)(/|$)' | head -1)
  [ -z "${TARGET_PKG}" ] && TARGET_PKG=$(printf '%s\n' ${MAIN_PKGS} | head -1)
fi

# Normalize to a package path callgraph accepts (./cmd/foo or .)
case "${TARGET_PKG}" in
  .|./) TARGET_PKG="." ;;
  *) TARGET_PKG="./${TARGET_PKG#./}" ;;
esac

if [ -z "${TARGET_PKG}" ] || [ "${TARGET_PKG}" = "./" ]; then
  echo "ERROR: No main package found for call graph analysis"
  exit 1
fi
echo "Selected TARGET_PKG=${TARGET_PKG}"
```

```bash
ALGO="${USER_ALGO:-vta}"
OUT_DIR="${OUT_DIR:-${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}}"
mkdir -p "${OUT_DIR}"

# TARGET_PKG is the specific main package (e.g. ./cmd/controller, .)
# NEVER use ./... — it causes VTA to explode on large repos
echo "Building call graph: algo=${ALGO}, target=${TARGET_PKG}"
timeout -k 10 300 env CGO_ENABLED=0 callgraph -algo "${ALGO}" -format=digraph "${TARGET_PKG}" > "${OUT_DIR}/callgraph.txt" 2>&1
CG_EXIT=$?
echo "callgraph exit: ${CG_EXIT}, lines: $(wc -l < "${OUT_DIR}/callgraph.txt")"
```

**Progressive fallback if the command times out or fails:**

```bash
# Fallback 1: faster algorithm
if [ $CG_EXIT -eq 124 ] || [ $CG_EXIT -eq 137 ]; then
  echo "⚠ ${ALGO} timed out — falling back to rta"
  timeout -k 10 300 env CGO_ENABLED=0 callgraph -algo rta -format=digraph "${TARGET_PKG}" > "${OUT_DIR}/callgraph.txt" 2>&1
  CG_EXIT=$?
fi

# Fallback 2: fastest algorithm
if [ $CG_EXIT -eq 124 ] || [ $CG_EXIT -eq 137 ]; then
  echo "⚠ rta timed out — falling back to cha"
  timeout -k 10 300 env CGO_ENABLED=0 callgraph -algo cha -format=digraph "${TARGET_PKG}" > "${OUT_DIR}/callgraph.txt" 2>&1
  CG_EXIT=$?
fi

if [ $CG_EXIT -eq 124 ] || [ $CG_EXIT -eq 137 ]; then
  echo "✗ All algorithms timed out — call graph analysis skipped"
fi
```

**Error Handling:**
- IF build fails (compilation errors) → Note in report that call graph cannot be built
- IF command times out → Fallback chain: `vta` → `rta` → `cha`, all on the same target package
- IF all algorithms time out → Skip call graph, assign NEEDS_REVIEW
- IF successful → Continue to Step 3

**Output:** `${OUT_DIR}/callgraph.txt` containing the call graph rooted at the target binary

### Step 3: Check if Vulnerable Function Exists in Graph

Extract the vulnerable function signature from CVE details.

```bash
# Search for exact function in the cached call graph
VULN_FUNC="<package-path>.<vulnerable-function>"
cat "${OUT_DIR}/callgraph.txt" | digraph nodes | grep "${VULN_FUNC}$"
```

**Decision Point:**
- IF function found in this `TARGET_PKG` graph → Continue to Step 4
- IF function NOT found in this graph → Try the next candidate from `MAIN_PKGS` (different `TARGET_PKG`) before concluding
- IF every examined main package shows no path → Return **NEEDS_REVIEW** (or MEDIUM if other evidence exists) — do **not** assign LOW RISK from a single unexamined or inconclusive graph

### Step 4: Find Execution Paths from Entry Points

Search for paths from main entry points to the vulnerable function.

```bash
# Find path from main() to vulnerable function using cached call graph
ENTRY_POINT="command-line-arguments.main"
VULN_FUNC="<package-path>.<vulnerable-function>"

cat "${OUT_DIR}/callgraph.txt" | \
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
cat "${OUT_DIR}/callgraph.txt" | \
  digraph somepath "${ENTRY_POINT}" "${VULN_FUNC}" | \
  digraph to dot > "${OUT_DIR}/callgraph.dot"

# Convert to SVG (if graphviz available)
if which sfdp > /dev/null; then
  sfdp -Tsvg -o"${OUT_DIR}/callgraph.svg" -Goverlap=scale "${OUT_DIR}/callgraph.dot"
  echo "Visual graph saved to: ${OUT_DIR}/callgraph.svg"
else
  echo "Graphviz not available - DOT file saved to: ${OUT_DIR}/callgraph.dot"
fi
```

**Output Files:**
- `${OUT_DIR}/callgraph.dot` - DOT notation of call path
- `${OUT_DIR}/callgraph.svg` - Visual graph (if graphviz available)

### Step 6: Parse and Format Call Chain

Extract human-readable call chain from digraph output:

```bash
# Get call chain as text from cached call graph
cat "${OUT_DIR}/callgraph.txt" | \
  digraph somepath "${ENTRY_POINT}" "${VULN_FUNC}" | \
  digraph to dot | \
  grep " -> " | \
  sed 's/"//g' | \
  sed 's/;//g'
```

**Example Output:**
```text
command-line-arguments.main -> <package-path>.Handler
<package-path>.Handler -> <package-path>.ProcessFunction
<package-path>.ProcessFunction -> <vulnerable-package>.<vulnerable-function>
```

**Format for Report:**
```text
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
    "callgraph_file": "${OUT_DIR}/callgraph.txt",
    "dot_file": "${OUT_DIR}/callgraph.dot",
    "svg_file": "${OUT_DIR}/callgraph.svg"
  }
}
```

## Error Handling

### Build Failures
- IF project doesn't compile → Note in report, cannot perform call graph analysis
- Suggest: Fix compilation errors first

### Very Large Codebases
- IF chosen algorithm times out (>5 minutes) → Fall back to next faster algorithm (`vta` → `rta` → `cha`)
- IF all algorithms time out on the chosen main package → Try a narrower entry point (single binary)
- IF still failing → Skip call graph, assign NEEDS_REVIEW, document the limitation
- NEVER use `./...` as scope — always target a specific main package

### Missing Entry Points
- IF `command-line-arguments.main` not found → Look for other entry points
- Web services: Check HTTP handler registrations
- Libraries: Call graph analysis may not be applicable

### Tool Installation Issues
- IF tools cannot be installed → Fall back to lower confidence methods
- Document limitation in final report

## Example: Generic Analysis Workflow

```bash
# Setup
CVE_ID="CVE-YYYY-NNNNN"
OUT_DIR="${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}"
mkdir -p "${OUT_DIR}"

# Step 1: Build call graph targeting a specific main package
timeout -k 10 300 env CGO_ENABLED=0 callgraph -algo vta -format=digraph ./cmd/controller > "${OUT_DIR}/callgraph.txt" 2>&1

# Step 2: Check if function is called
digraph nodes < "${OUT_DIR}/callgraph.txt" | grep "<package-path>.<vulnerable-function>$"

# Step 3: Find path from main
digraph somepath command-line-arguments.main "<package-path>.<vulnerable-function>" < "${OUT_DIR}/callgraph.txt"

# Step 4: Generate visual graph (if graphviz available)
digraph somepath command-line-arguments.main "<package-path>.<vulnerable-function>" < "${OUT_DIR}/callgraph.txt" | \
  digraph to dot | sfdp -Tsvg -o"${OUT_DIR}/callgraph.svg"

# Result: HIGH RISK — reachable path found
```

## Integration with Parent Command

This skill is called from Method 5 of the [codebase-impact-analysis](../codebase-impact-analysis/SKILL.md) skill.

**When to Invoke:**
- After basic dependency checks show package is present
- Mandatory whenever the vulnerable package is in `go.mod` (see codebase-impact-analysis Method 5) — not just for "highest confidence"
- When tools are available (checked in Phase 0)

**Return to Parent:**
- Provide risk level (HIGH/MEDIUM/LOW)
- Include evidence (call chain, graph files)
- Update report with reachability findings

