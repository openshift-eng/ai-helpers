---
name: codebase-impact-analysis
description: Analyze a Go codebase to determine if it is impacted by a specific CVE using multiple verification methods and assign a risk level
---

# Codebase Impact Analysis

Determines whether a Go codebase is impacted by a specific CVE by applying multiple analysis methods with increasing confidence, collecting evidence, and assigning a risk level.

## When to Use This Skill

Use this skill when:
- A CVE profile has been gathered (from the cve-intelligence-gathering skill)
- You need to determine if the current Go project is affected
- You need to assign a risk level with supporting evidence

## Prerequisites

### Required Tools (validated in Phase 0 of parent command)
- `go` toolchain with `go.mod` in workspace root
- `govulncheck`: `go install golang.org/x/vuln/cmd/govulncheck@latest`
- `callgraph`: `go install golang.org/x/tools/cmd/callgraph@latest`
- `digraph`: `go install golang.org/x/tools/cmd/digraph@latest`

### Required Inputs

**From Phase 1 (cve-intelligence-gathering skill):**
- CVE ID
- Affected package/module name(s)
- Vulnerable version range
- Fixed version (if available)
- Vulnerable function signatures (if known)

**From Parent Command:**
- `--algo` preference for call graph analysis (default: `vta`)
- `REPO_DIR` — the repository cloned in Phase 0.7 (e.g. `.work/compliance/analyze-cve/repos/hypershift`). All commands below run against this directory, not necessarily the shell's current working directory.

## Implementation Steps

### Step 1: Identify Go Module Dependencies

```bash
# Parse dependencies from go.mod
go list -m all

# Get detailed dependency info
go list -m -json all
```

- Read `go.mod` from workspace root
- Parse direct and indirect dependencies
- Extract module versions

### Step 2: Cross-Reference Vulnerable Packages

Apply the following methods in order. Each provides increasing confidence.

#### Method 1: Dependency Matching

- Compare CVE-affected packages with `go.mod` dependencies
- Check if affected package versions are in use
- Account for version ranges and semantic versioning

```bash
# Check if vulnerable package is a dependency
go list -m <vulnerable-package>
```

**Decision Point:**
- IF package NOT in dependencies → Skip to risk assignment (likely LOW RISK)
- IF package found → Continue to Method 2

#### Method 2: Go Vulnerability Scanner

> **CRITICAL RULES — read before running anything:**
> 1. **Run govulncheck AT MOST ONCE per analysis run.** Keep all Method 2 scratch and cache files under `${OUT_DIR}/` (same per-CVE workspace as call-graph artifacts). The canonical result is `${OUT_DIR}/govulncheck-source.txt` — if it already exists and is non-empty for this run, read it and do not re-run.
> 2. **Never pipe govulncheck to `head`, `tail`, `grep`, or any other command.** Always redirect to a file (`> file 2>&1`). Piping causes govulncheck to hang (SIGPIPE) when the reader closes.
> 3. **"No findings" is a valid and final result** — it means the CVE is not yet in the Go vuln database. Proceed to Method 3 immediately. Do NOT re-run in a different mode or format.
> 4. **Always use `timeout -k 10`** to force-kill if SIGTERM is ignored. Plain `timeout` sends SIGTERM but govulncheck can ignore it when stuck in package loading.

This method has 4 sequential steps. If any step fails or times out, skip the remaining steps and proceed to Method 3 — govulncheck is one signal, not the only one.

```bash
OUT_DIR="${OUT_DIR:-${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}}"
mkdir -p "${OUT_DIR}"
```

---

**Step 2a — go.mod check (instant)**

```bash
VULN_PKG="google.golang.org/grpc"   # replace with actual vulnerable package
echo "=== Step 2a: go.mod check for ${VULN_PKG} ==="
grep "${VULN_PKG}" "${REPO_DIR}/go.mod" && echo "FOUND in go.mod" || echo "NOT FOUND in go.mod"
```

- IF **NOT FOUND** → record "package not in module graph" as LOW signal; **skip Steps 2b–2d entirely**; proceed to Method 3
- IF **FOUND** → note the version; continue

---

**Step 2b — Pre-flight: download modules and verify toolchain (max 2 min)**

Large repos (300+ deps like spiffe-spire) need all modules cached before govulncheck can load them. Separate this from the scan to isolate network issues from analysis hangs.

```bash
cd "${REPO_DIR}"
echo "=== Step 2b: Pre-flight ==="

# Download all modules (network-bound, do first)
echo "Downloading modules..."
timeout -k 10 120 env CGO_ENABLED=0 go mod download > "${OUT_DIR}/go-mod-download.txt" 2>&1
if [ $? -ne 0 ]; then
  echo "⚠ go mod download failed or timed out — govulncheck may fail"
  cat "${OUT_DIR}/go-mod-download.txt"
fi

# Verify the Go toolchain can load the package graph (CGO disabled first — many repos fail only with CGO enabled)
echo "Loading package list (CGO_ENABLED=0)..."
timeout -k 10 60 env CGO_ENABLED=0 go list ./... > "${OUT_DIR}/go-list-packages.txt" 2>&1
LIST_EXIT=$?
PKG_COUNT=$(wc -l < "${OUT_DIR}/go-list-packages.txt" 2>/dev/null || echo 0)
echo "Package count: ${PKG_COUNT}, exit code: ${LIST_EXIT}"

if [ $LIST_EXIT -ne 0 ]; then
  echo "go list with CGO_ENABLED=0 failed — retrying after CGO probe (Step 2c) before skipping govulncheck"
fi
```

- IF `go list` succeeds with `CGO_ENABLED=0` → continue to Step 2c, then 2d
- IF `go list` still fails after Step 2c's CGO probe (with the chosen `CGO_SETTING`) → write the error to `${OUT_DIR}/govulncheck-source.txt`, **skip Steps 2c–2d**, proceed to Method 3

---

**Step 2c — CGO probe (max 60s, skip if compiler absent)**

```bash
echo "=== Step 2c: CGO probe ==="
CGO_SETTING=0
if command -v gcc >/dev/null 2>&1 || command -v cc >/dev/null 2>&1; then
  timeout -k 10 60 env CGO_ENABLED=1 go build ./... > "${OUT_DIR}/cgo-probe.txt" 2>&1
  if [ $? -eq 0 ]; then
    CGO_SETTING=1
    echo "✓ CGO works — using CGO_ENABLED=1"
  else
    echo "✗ CGO build failed — using CGO_ENABLED=0"
  fi
else
  echo "✗ No C compiler — using CGO_ENABLED=0"
fi
echo "CGO_ENABLED=${CGO_SETTING}"

if [ $LIST_EXIT -ne 0 ]; then
  echo "Retrying go list with CGO_ENABLED=${CGO_SETTING}..."
  timeout -k 10 60 env CGO_ENABLED=${CGO_SETTING} go list ./... > "${OUT_DIR}/go-list-packages.txt" 2>&1
  LIST_EXIT=$?
  PKG_COUNT=$(wc -l < "${OUT_DIR}/go-list-packages.txt" 2>/dev/null || echo 0)
  echo "Retry package count: ${PKG_COUNT}, exit code: ${LIST_EXIT}"
  if [ $LIST_EXIT -ne 0 ]; then
    echo "✗ go list failed after CGO probe — skipping govulncheck entirely"
    echo "go list failed (exit ${LIST_EXIT})" > "${OUT_DIR}/govulncheck-source.txt"
    cat "${OUT_DIR}/go-list-packages.txt" >> "${OUT_DIR}/govulncheck-source.txt"
  fi
fi
```

- IF `go list` still fails after retry → `${OUT_DIR}/govulncheck-source.txt` is populated; skip Step 2d and proceed to Method 3
- IF `go list` succeeds → continue

---

**Step 2d — govulncheck scan (max 5 min)**

Use `-scan=package` first (fast, checks if CVE is in vuln DB and package imported). Only escalate to symbol-level if package-level finds something.

```bash
if [ ! -s "${OUT_DIR}/govulncheck-source.txt" ] && [ $LIST_EXIT -eq 0 ]; then
  # Package-level scan first (fast — no symbol resolution)
  echo "=== Step 2d: govulncheck package scan ==="
  timeout -k 10 120 env CGO_ENABLED=${CGO_SETTING} govulncheck -scan=package ./... > "${OUT_DIR}/govulncheck-package.txt" 2>&1
  PKG_EXIT=$?
  echo "govulncheck -scan=package exit: ${PKG_EXIT}"
  cat "${OUT_DIR}/govulncheck-package.txt"

  # Check if the package scan found anything worth escalating to symbol level
  if grep -qi "Vulnerability\|finding\|${VULN_PKG}" "${OUT_DIR}/govulncheck-package.txt" 2>/dev/null; then
    echo "=== Step 2d: govulncheck symbol scan (escalating — CVE found at package level) ==="
    timeout -k 10 300 env CGO_ENABLED=${CGO_SETTING} govulncheck ./... > "${OUT_DIR}/govulncheck-source.txt" 2>&1
    SOURCE_EXIT=$?
    if [ $SOURCE_EXIT -eq 124 ] || [ $SOURCE_EXIT -eq 137 ]; then
      echo "govulncheck symbol scan timed out or was killed — using package-level results"
      cp "${OUT_DIR}/govulncheck-package.txt" "${OUT_DIR}/govulncheck-source.txt"
    fi
  else
    echo "Package scan found no findings — CVE likely not in Go vuln DB yet"
    cp "${OUT_DIR}/govulncheck-package.txt" "${OUT_DIR}/govulncheck-source.txt"
  fi
  echo "govulncheck complete"
else
  echo "=== govulncheck (using cached result) ==="
fi
cat "${OUT_DIR}/govulncheck-source.txt"

# Verify repo is still accessible after govulncheck
echo "=== Post-govulncheck repo check ==="
ls "${REPO_DIR}/go.mod" > /dev/null 2>&1 && echo "✓ Repo intact at ${REPO_DIR}" || echo "✗ WARNING: Repo missing at ${REPO_DIR}"
```

- IF CGO was disabled → note in report: "CGO-gated code paths excluded from analysis"
- IF package scan found no findings → CVE is not in Go vuln DB; do NOT escalate to symbol scan; proceed to Method 3
- IF symbol scan timed out → use package-level results instead; proceed to Method 3
- Save `${OUT_DIR}/govulncheck-source.txt` as a workflow artifact

**Decision Point — govulncheck is ONE signal. Always continue to Method 3 next.**
- IF scan reports vulnerable symbols called → Strong evidence for HIGH RISK; still continue to Method 3
- IF scan reports **no findings** → CVE likely not yet in Go vuln database. **Do NOT re-run.** Proceed to Method 3.
- IF scan timed out or was skipped → Proceed to Method 3; note the gap in the report

#### Method 3: Direct Dependency Check

```bash
# Verify package is included (directly or transitively)
go list -mod=mod <vulnerable-package>
```

**Note:** Package presence alone doesn't prove vulnerable functions are called.

#### Method 4: Source Code Analysis

- Search for import statements of vulnerable packages in source code
- Use grep/codebase_search to find package usage
- Search for vulnerable function/method names in codebase
- Identify actual code paths that use vulnerable functions
- Check if vulnerable functions are called in reachable code

#### Method 5: Call Graph Reachability Analysis (Mandatory when package is present)

Delegate to the [call-graph-analysis](../call-graph-analysis/SKILL.md) skill.

- **Pass**: `--algo` preference from user, vulnerable function signature, package path
- **Receive**: Risk level, call chain, evidence files

> **Scope rule:** Never invoke `callgraph` with `./...`. Always target a specific main package (e.g. `./cmd/controller`, `.`). The tool resolves transitive dependencies automatically. Running on `./...` causes VTA to exhaust resources on repos with >50 packages (external-secrets has 138, spiffe-spire has 300+). See the call-graph-analysis skill for the progressive fallback chain (`vta` → `rta` → `cha`).

**This method is REQUIRED whenever the vulnerable package is present in `go.mod`** — regardless of what Methods 2, 3, or 4 found. Source code analysis (Method 4) is heuristic: it can miss indirect calls through interfaces, generated code, and runtime dispatch. Only a call graph provides provable reachability.

**Valid reasons to skip call graph:**
- Package is NOT in `go.mod` (genuinely unreachable — LOW RISK by definition)
- Codebase does not compile (note the limitation; rely on other methods)
- Vulnerable function signature is unknown (note the gap; rely on govulncheck and source analysis)

**NOT a valid reason to skip:**
- Source code analysis found no direct calls to the vulnerable function
- govulncheck did not flag it (CVE may not be in the Go vuln DB yet)
- The analysis "feels" complete from earlier methods

#### Method 6: Configuration and Context Analysis

- Review if vulnerable features are actually enabled
- Check if vulnerable code paths are behind feature flags
- Verify if inputs can reach vulnerable functions
- Consider security controls (input validation, sandboxing)

### Confidence Levels

Each method provides increasing confidence:

1. **Basic Presence** (Low) — Package in `go.mod` (Method 1, 3)
2. **Import & Version Analysis** (Medium) — Package imported, version in vulnerable range, function names found (Method 4)
3. **Vulnerability Scanner** (Medium-High) — `govulncheck` confirms reachable vulnerable symbols (Method 2)
4. **Call Graph Reachability** (Definitive) — Proven execution path from entry point to vulnerable function (Method 5)
5. **Context Analysis** — Mitigating or aggravating factors (Method 6)

**Required minimum:** If the package is in `go.mod`, the analysis is not complete until Method 5 has run or a valid skip reason has been documented. Never stop at Method 4 alone.

### Step 3: Build Evidence Package

Collect evidence from all methods used:

- **Dependency Evidence**: `go.mod` entries, `go list` output, version info
- **Static Code Evidence**: File paths, line numbers, code snippets showing usage
- **Reachability Evidence**: Call graph output, execution paths, DOT visualization (saved to `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/{CVE-ID}/callgraph.svg`, outside `REPO_DIR`)
- **Scanner Evidence**: `govulncheck` output, vulnerability findings
- **Mitigation Factors**: Input validation, disabled features, feature flags, security controls

### Step 4: Assign Risk Level

Evaluate all evidence and assign a risk level. The determination should be data-driven, not formula-based.

**HIGH RISK:**
- Call graph shows a reachable path to the vulnerable function, OR
- Symbol-level `govulncheck` confirms **called** vulnerable symbols (package-level import alone is not sufficient)

**MEDIUM RISK:**
- Package + vulnerable version in dependencies, usage evidence present, but call graph could not run (build failure or unknown function signature) — reachability not definitively proven

**LOW RISK:**
- Package not in dependencies (call graph skipped — genuinely unreachable), OR version not in vulnerable range, OR call graph ran and found no reachable path

**NEEDS REVIEW:**
- Package is in `go.mod` but call graph was skipped for any reason other than package absence or build failure — escalate; do not leave as LOW based on source code analysis alone
- Conflicting signals or incomplete analysis

> **Rule:** If package is in `go.mod` and call graph was skipped because source analysis "found nothing", assign **NEEDS REVIEW**, not LOW RISK. Document the skip reason explicitly.

## Return Value

Return structured result to parent command:

```json
{
  "skill": "codebase-impact-analysis",
  "status": "success",
  "risk_level": "<HIGH|MEDIUM|LOW|NEEDS_REVIEW>",
  "methods_used": ["dependency_matching", "govulncheck", "direct_dependency_check", "source_code_analysis", "call_graph", "context_analysis"],
  "evidence": {
    "dependency": {
      "package_found": true,
      "current_version": "<version>",
      "dependency_type": "<direct|indirect>",
      "in_vulnerable_range": true
    },
    "govulncheck": {
      "ran": true,
      "cve_found": true,
      "vulnerable_symbols_called": true
    },
    "call_graph": {
      "ran": true,
      "algorithm": "<vta|rta|cha|static>",
      "reachable_from_main": true,
      "call_chain": "main -> handler -> parse -> VULN",
      "evidence_files": ["callgraph.dot", "callgraph.svg"],
      "skip_reason": "<null if ran | 'package_not_in_gomod' | 'build_failure' | 'unknown_function_signature'>"
    },
    "source_analysis": {
      "import_found": true,
      "function_usage_found": true,
      "files": ["<file1>:<line>", "<file2>:<line>"]
    },
    "mitigation_factors": []
  },
  "confidence_assessment": {
    "level": "<HIGH|MEDIUM|LOW>",
    "methods_count": 4,
    "gaps": ["<any gaps in analysis>"]
  }
}
```

## Error Handling

### Build Failures
- IF project doesn't compile → Note limitation, skip call graph analysis, rely on other methods

### Missing CVE in govulncheck Database
- IF govulncheck doesn't know about this CVE → Continue with other methods, note gap

### Large Codebases
- IF call graph times out → Follow fallback strategy in call-graph-analysis skill: algorithm fallback (`vta` → `rta` → `cha`), always targeting a specific main package. Never use `./...` as scope.

### Incomplete CVE Information
- IF vulnerable function signature unknown → Skip call graph, note `skip_reason: unknown_function_signature`, assign MEDIUM at best — do NOT assign LOW based on source analysis alone

### Source Code Analysis Shows No Usage
- This is **NOT** a valid reason to skip call graph. Proceed with Method 5.
- Source code search misses interface dispatch, generated code, and indirect call paths.

## Integration with Parent Command

This skill is called from Phase 2 of the `/compliance:analyze-cve` command, after the [Repo Guard](../../commands/analyze-cve.md#repo-guard--re-clone-if-missing) has confirmed `REPO_DIR` still exists.

**Input:** CVE profile from Phase 1, `--algo` preference from user, `REPO_DIR` set in Phase 0.7
**Output:** Risk level, evidence package, confidence assessment
**Next:** Parent command uses risk level to decide whether to generate report and proceed to remediation
