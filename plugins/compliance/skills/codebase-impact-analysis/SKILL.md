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

### Required Tools (validated in Phase 0 of the analyze-cve skill)
- `go` toolchain with `go.mod` somewhere in the repository (root or a subdirectory — resolved to `GO_MODULE_DIR` in Phase 0.7 Step 4)
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
- `REPO_DIR` — the repository cloned in Phase 0.7 (e.g. `.work/compliance/analyze-cve/repos/hypershift`). Git-level operations (status, staging, PR diffing) run against this directory.
- `GO_MODULE_DIR` — the Go module root resolved by Phase 0.7 Step 4 (equal to `REPO_DIR` when `go.mod` is at the repository root; a subdirectory when it isn't — see [Non-root / multi-module repos](../analyze-cve/references/implementation.md#step-4-locate-the-go-module-and-verify-go-project)). **All `go`, `govulncheck`, and `callgraph` commands below run with this as the working directory**, not `REPO_DIR` and not necessarily the shell's current working directory. If `GO_MODULE_DIR` is unset (no `go.mod` found anywhere in `REPO_DIR`), skip straight to risk assignment with dependency-based methods unavailable.

## Implementation Steps

### Step 1: Identify Go Module Dependencies

```bash
cd "${GO_MODULE_DIR}"

# Parse dependencies from go.mod
go list -m all

# Get detailed dependency info
go list -m -json all
```

- Read `go.mod` from `GO_MODULE_DIR` (the resolved module root, not necessarily `REPO_DIR`)
- Parse direct and indirect dependencies
- Extract module versions

### Step 1.5: Go Stdlib CVE — Build-Time Version Check (only when the vulnerable "package" is Go stdlib)

Skip this step for third-party module CVEs — go directly to Step 2. Run it only when the CVE's affected package is part of the Go standard library itself (e.g. `crypto/tls`, `net/http`, `encoding/xml`, `archive/zip`) rather than something listed in `go.mod`.

**Why this needs its own check:** `go.mod`'s `go` directive states the *minimum language version* the module requires to build — it is not proof of the toolchain that actually compiled the shipped binary. A component can declare `go 1.21` while its Dockerfile's build stage uses a much newer (or older) Go builder image — the public `golang:` image, or (common in OpenShift/Red Hat repos) a `go-toolset`/UBI-based builder image instead. Stdlib CVE exposure depends on the **compiler that actually built the binary**, not the declared minimum.

Run the commands in [references/procedures.md#step-15-go-stdlib-build-time-version-check--commands](references/procedures.md#step-15-go-stdlib-build-time-version-check--commands) to collect three version signals — the Dockerfile/Containerfile build-image tag, a `toolchain` directive, and (informational only) the locally installed `go` — then apply the rules below. The version-extraction regex is anchored to the digits immediately after `golang`/`go-toolset` specifically because ART-built OpenShift images pack extra version numbers into the same reference (e.g. an OCP release number ahead of the Go version); anchor your own reasoning the same way if you extend this check.

- IF `DOCKERFILE_GO`/`TOOLCHAIN_GO` resolves to a version **at or above** the CVE's fixed Go version → the shipped binary is very likely already patched, **even though `go.mod`'s declared minimum looks vulnerable**. Note this as a discrepancy in the report and recommend confirming the exact builder-image tag against the fix — do not assert NOT AFFECTED from this signal alone, since a Dockerfile tag can be stale or floating (e.g. `golang:1.22` or a `go-toolset:1.22` image tracking a moving patch level).
- IF `DOCKERFILE_GO`/`TOOLCHAIN_GO` resolves to a version **below** the fix → treat as vulnerable at the toolchain level. This is a stdlib/toolchain fix that must come from a rebuilt builder image, not a `go.mod` dependency bump — flag it for `remediation-planning`'s Go Runtime Update path (Step 2A) and do **not** edit the `go` directive locally to "fix" it.
- IF neither signal is found (no Dockerfile, no toolchain directive) → fall back to `DECLARED_GO` with an explicit caveat in the report: "declared `go.mod` minimum only — actual build-time compiler version could not be confirmed."
- Record `DECLARED_GO`, `DOCKERFILE_GO`, and `TOOLCHAIN_GO` as evidence regardless of outcome, then continue to Step 2.

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
- IF package found → Continue to Method 1.5

#### Method 1.5: Dynamic-Pattern Confidence Scan (always run once the package is present)

Both govulncheck (Method 2) and the call graph (Method 5) are static analyses — they only see a call that appears as a literal call expression in the source. `reflect`-based dispatch, `unsafe` pointer casts, cgo call-backs, and `plugin.Open`-loaded code can all reach a vulnerable function without ever producing that call expression. This method doesn't prove reachability by itself; it sets a confidence level for how much to trust a **negative** result from Methods 2 and 5 later.

Count non-test, non-vendored uses of `reflect`, `unsafe`, `import "C"`, and `plugin.Open`/`plugin.Lookup` under `${GO_MODULE_DIR}` (a `grep -rln` per pattern is enough — the exact command doesn't matter, but keep the list of **matching file paths**, not just the counts: Method 5.5 needs to know which files to read). Sum the four counts as `TOTAL_DYNAMIC` and classify:

- **0** → `STATIC_CONFIDENCE=HIGH`: a "not reachable" result from Method 2/5 later can be trusted as-is.
- **1–9** → `STATIC_CONFIDENCE=MEDIUM`: a later "not reachable" result is provisional — if the package is present, Method 5.5 (reflection/CGO reachability check) must run before finalizing.
- **10+** → `STATIC_CONFIDENCE=LOW`: static tooling is unreliable on this codebase. Method 5.5 is mandatory whenever the package is present, and the report must say so explicitly even if the final level ends up LOW.

Record the four counts, the matching file paths, and `STATIC_CONFIDENCE` as evidence (e.g. `${OUT_DIR}/dynamic-pattern-scan.txt`). Carry `STATIC_CONFIDENCE` and the file list forward — they drive the Confidence Downgrade rule in [Step 4](#step-4-assign-risk-level) and are exactly what Method 5.5 reads when it's mandatory. Continue to Method 2.

#### Method 2: Go Vulnerability Scanner

> **CRITICAL RULES — read before running anything:**
> 1. **Run govulncheck AT MOST ONCE per analysis run.** Keep all Method 2 scratch and cache files under `${OUT_DIR}/` (same per-CVE workspace as call-graph artifacts). The canonical result is `${OUT_DIR}/govulncheck-source.txt` — if it already exists and is non-empty for this run, read it and do not re-run.
> 2. **Never pipe govulncheck to `head`, `tail`, `grep`, or any other command.** Always redirect to a file (`> file 2>&1`). Piping causes govulncheck to hang (SIGPIPE) when the reader closes.
> 3. **"No findings" is a valid and final result** — it means the CVE is not yet in the Go vuln database. Proceed to Method 3 immediately. Do NOT re-run in a different mode or format.
> 4. **Always use `timeout -k 10`** to force-kill if SIGTERM is ignored. Plain `timeout` sends SIGTERM but govulncheck can ignore it when stuck in package loading.

This method has 4 sequential steps, in [references/procedures.md#method-2-go-vulnerability-scanner--detailed-procedure](references/procedures.md#method-2-go-vulnerability-scanner--detailed-procedure): **2a** go.mod presence check (instant) → **2b** pre-flight module download + `go list` toolchain check (max 2 min) → **2c** CGO probe, only if 2b's `CGO_ENABLED=0` load failed (max 60s) → **2d** the govulncheck scan itself, package-level first and escalating to symbol-level only if that finds something (max 5 min). If any step fails or times out, skip the remaining steps and proceed to Method 3 — govulncheck is one signal, not the only one. Each step's own IF/THEN skip conditions are documented alongside its commands in the reference.

**Decision Point — govulncheck is ONE signal. Always continue to Method 2.5 next.**
- IF scan reports vulnerable symbols called → Strong evidence for HIGH RISK; still continue to Method 2.5
- IF scan reports **no findings** → CVE likely not yet in Go vuln database. **Do NOT re-run.** Proceed to Method 2.5.
- IF scan timed out or was skipped → Proceed to Method 2.5; note the gap in the report

#### Method 2.5: Vendor Directory Verification (when `vendor/` exists)

`go.mod` listing a dependency does not prove the *vulnerable* code is actually vendored — some repos vendor only a subset of a module's packages (e.g. a parser library but not the daemon package a CVE actually requires). This catches that "partial vendoring" case, which govulncheck and the call graph (Method 5) cannot see on their own since both operate on whatever `vendor/` happens to contain.

**Decision Point:**
- IF `${GO_MODULE_DIR}/vendor/` does not exist (module-mode build, no vendoring) → skip this method entirely; note "not a vendored repo" and continue to Method 3.
- IF `vendor/` exists → run the commands in [references/procedures.md#method-25-vendor-directory-verification--commands](references/procedures.md#method-25-vendor-directory-verification--commands), which set `VENDOR_STATUS` to one of `not_vendored`, `present`, or `partial_not_vulnerable_part`, then apply the rules below.

- IF `VENDOR_STATUS=not_vendored` → the module isn't in the vendored tree that actually ships in the build, even though `go.mod` lists it (e.g. an unused indirect dependency, or a build-tag-excluded path). This **caps risk at LOW** regardless of what govulncheck or the call graph found — the vulnerable code cannot execute if it was never vendored into the build.
- IF `VENDOR_STATUS=partial_not_vulnerable_part` → the specific vulnerable sub-package/file from the advisory isn't in the vendored subset even though the module is. This **caps risk at LOW**; state the mismatch explicitly in the report (e.g. "go.mod lists `<module>`, but the vendored subset excludes the vulnerable `<sub-package>`").
- IF `VENDOR_STATUS=present` → no downgrade from this method; continue to Method 3 and give full weight to Method 2 and Method 5's results.
- Record `VENDOR_STATUS` and the `find` output as evidence regardless of outcome.

> This method only ever **caps risk downward** toward LOW — it never raises risk on its own. `present` is neutral, not confirmatory; reachability still comes from Method 2/5.

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

#### Method 5.5: Reflection/CGO Reachability Check (mandatory when Method 1.5 confidence is MEDIUM or LOW)

Run this method whenever Method 1.5 flagged reflect/unsafe/cgo/plugin usage (`STATIC_CONFIDENCE` MEDIUM or LOW) **and** the vulnerable function was not proven reachable by Method 5 (no path found, or call graph skipped/build failed). Skip it when `STATIC_CONFIDENCE=HIGH` (nothing to find) or when Method 5 already proved a direct reachable path (no need to also look for an indirect one).

Rather than trust the call graph's silence, read the specific files Method 1.5 flagged — not the whole repo, and not by writing a separate analysis tool; this is a small enough set of files to read directly. Look for:
- `reflect.ValueOf(...).MethodByName("<literal>")` — does the literal method name match (or plausibly match) the vulnerable function's name from the CVE advisory?
- `unsafe.Pointer` casts near a call site that could route into the vulnerable function.
- `import "C"` plus a `//export`ed function — the C side may call it; open the paired `.c`/`.h` file and check whether it does.

**Interpretation:**
- A `MethodByName` literal matching the vulnerable function → reachable via reflection. Escalate toward **HIGH**, and note in the report that reachability was established via reflection, not a static call graph.
- An `//export`ed function whose C caller reaches the vulnerable path → reachable. Escalate toward **HIGH**.
- Nothing found across every flagged file → no evidence of indirect dispatch reaching the vulnerable function. Combined with Method 5's own negative result, this is what justifies a LOW (not NEEDS_REVIEW) conclusion despite MEDIUM/LOW `STATIC_CONFIDENCE` — see the Confidence Downgrade rule in [Step 4](#step-4-assign-risk-level).

Record which files were checked and what was found as evidence either way (e.g. `${OUT_DIR}/reflection-cgo-check.txt`).

#### Method 6: Configuration and Context Analysis

- Review if vulnerable features are actually enabled
- Check if vulnerable code paths are behind feature flags
- Verify if inputs can reach vulnerable functions
- Consider security controls (input validation, sandboxing)

### Confidence Levels

Each method contributes evidence of a different strength, listed in the order they run:

- **Method 1 (Dependency Matching)** — Basic presence: is the package in `go.mod`.
- **Method 1.5 (Dynamic-Pattern Confidence Scan)** — Sets how much to trust a later negative result from Method 2 or Method 5.
- **Method 2 (Go Vulnerability Scanner)** — Medium-high: `govulncheck` confirms reachable vulnerable symbols.
- **Method 2.5 (Vendor Directory Verification)** — Can only cap risk down toward LOW; never raises it.
- **Method 3 (Direct Dependency Check)** — Same tier as Method 1: presence, direct or transitive.
- **Method 4 (Source Code Analysis)** — Medium: import/version/usage evidence found in source.
- **Method 5 (Call Graph Reachability Analysis)** — Definitive: proven execution path from entry point to vulnerable function.
- **Method 5.5 (Reflection/CGO Reachability Check)** — Reachability a static call graph cannot represent.
- **Method 6 (Configuration and Context Analysis)** — Mitigating or aggravating factors layered on top of all of the above.

**Required minimum:** If the package is in `go.mod`, the analysis is not complete until Method 5 has run or a valid skip reason has been documented. Never stop at Method 4 alone. If `STATIC_CONFIDENCE` (Method 1.5) is MEDIUM or LOW and Method 5 returned a negative result, Method 5.5 must also run before the analysis is considered complete.

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

Apply the three overlays below **in this order**, on top of the HIGH/MEDIUM/LOW/NEEDS_REVIEW level assigned above:

**Vendor Override (Method 2.5 — applied after the levels above):**
- IF Method 2.5 was skipped (no `vendor/` directory — module-mode build) → no override; use the level assigned above.
- IF Method 2.5 found `not_vendored` or `partial_not_vulnerable_part` → override the level to **LOW**, regardless of what govulncheck or the call graph found. State in the report that the override happened and why. This is the one case where module-level evidence (govulncheck, call graph) is superseded by vendor-directory evidence.
- IF Method 2.5 found `present` → no override.

**Confidence Downgrade (Method 1.5 / Method 5.5 — applies to a LOW result only):**
- IF the level assigned above is LOW **and** `STATIC_CONFIDENCE` (Method 1.5) is MEDIUM or LOW **and** Method 5.5 either wasn't run or found nothing across the flagged files → do not finalize as LOW. Assign **NEEDS_REVIEW** instead, and state explicitly which dynamic-pattern category (reflect/unsafe/cgo/plugin) drove the downgrade.
- IF `STATIC_CONFIDENCE=HIGH` → no downgrade; a LOW result stands.
- IF Method 5.5 found a reachability match (a matching reflection call or a CGO path into the vulnerable function) → this already escalates the level per Method 5.5's own interpretation rules above; the downgrade rule here does not apply (the level is no longer LOW).

**Stdlib Build-Version Note (Step 1.5 — Go stdlib CVEs only):**
- IF Step 1.5 found a discrepancy between `go.mod`'s declared version and the Dockerfile/toolchain build-time version → state it in the report regardless of the assigned risk level (see Step 1.5 for the exact wording). This does not change the risk level by itself — it's evidence for the human reviewer that the `go.mod` minimum may not reflect the shipped binary's actual exposure.

## Return Value

Return structured result to parent command:

```json
{
  "skill": "codebase-impact-analysis",
  "status": "success",
  "risk_level": "<HIGH|MEDIUM|LOW|NEEDS_REVIEW>",
  "go_module_dir": "<GO_MODULE_DIR, relative to REPO_DIR — '.' when go.mod is at repo root>",
  "methods_used": ["stdlib_build_version_check", "dependency_matching", "dynamic_pattern_scan", "govulncheck", "vendor_check", "direct_dependency_check", "source_code_analysis", "call_graph", "reflection_cgo_check", "context_analysis"],
  "evidence": {
    "stdlib_build_version": {
      "applicable": false,
      "declared_go_mod_version": "<version|null>",
      "dockerfile_build_version": "<version|null>",
      "toolchain_directive": "<version|null>",
      "discrepancy_noted": false
    },
    "dependency": {
      "package_found": true,
      "current_version": "<version>",
      "dependency_type": "<direct|indirect>",
      "in_vulnerable_range": true
    },
    "dynamic_pattern_scan": {
      "reflect_count": 0,
      "unsafe_count": 0,
      "cgo_count": 0,
      "plugin_count": 0,
      "flagged_files": ["<file1>", "<file2>"],
      "static_analysis_confidence": "<HIGH|MEDIUM|LOW>"
    },
    "govulncheck": {
      "ran": true,
      "cve_found": true,
      "vulnerable_symbols_called": true
    },
    "vendor_check": {
      "ran": true,
      "vendor_status": "<present|not_vendored|partial_not_vulnerable_part|null if skipped (no vendor/)>",
      "risk_capped_to_low": false
    },
    "source_analysis": {
      "import_found": true,
      "function_usage_found": true,
      "files": ["<file1>:<line>", "<file2>:<line>"]
    },
    "call_graph": {
      "ran": true,
      "algorithm": "<vta|rta|cha|static>",
      "reachable_from_main": true,
      "call_chain": "main -> handler -> parse -> VULN",
      "evidence_files": ["callgraph.dot", "callgraph.svg"],
      "skip_reason": "<null if ran | 'package_not_in_gomod' | 'build_failure' | 'unknown_function_signature'>"
    },
    "reflection_cgo_check": {
      "ran": false,
      "reason_if_not_ran": "<'static_confidence_high' | 'call_graph_already_reachable' | null if ran>",
      "files_checked": ["<file1>", "<file2>"],
      "finding": "<reflection_match|cgo_match|negative|null if not ran>"
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

Listed in the order the corresponding step/method runs.

### Dockerfile Uses a Floating/Unpinned Base Image Tag (Step 1.5)
- IF the Dockerfile's Go builder-image line uses a moving tag (e.g. `golang:1.22` or `go-toolset:1.22` without a patch version, or a `latest`-style tag) → note this explicitly; the resolved version at analysis time may not match what was actually used for the shipped build. Do not treat this signal as definitive — fall back to the `go.mod` declared minimum with the standard caveat.

### Missing CVE in govulncheck Database (Method 2)
- IF govulncheck doesn't know about this CVE → Continue with other methods, note gap

### No `vendor/` Directory (Method 2.5)
- IF the repo builds in module mode (no `vendor/`) → skip Method 2.5 entirely; this is expected and not a gap. Note "not a vendored repo" and rely on Methods 2/4/5 as usual.

### Source Code Analysis Shows No Usage (Method 4)
- This is **NOT** a valid reason to skip call graph. Proceed with Method 5.
- Source code search misses interface dispatch, generated code, and indirect call paths.

### Build Failures (Method 5)
- IF project doesn't compile → Note limitation, skip call graph analysis, rely on other methods

### Large Codebases (Method 5)
- IF call graph times out → Follow fallback strategy in call-graph-analysis skill: algorithm fallback (`vta` → `rta` → `cha`), always targeting a specific main package. Never use `./...` as scope.

### Incomplete CVE Information (Method 5)
- IF vulnerable function signature unknown → Skip call graph, note `skip_reason: unknown_function_signature`, assign MEDIUM at best — do NOT assign LOW based on source analysis alone

### Too Many Files Flagged for Method 5.5 to Read Individually
- IF Method 1.5 flags an unusually large number of files (e.g. generated code, a vendored copy that wasn't excluded) → prioritize files whose import graph is closest to the vulnerable package, note the ones skipped, and don't treat an incomplete sweep as a clean "nothing found" result. This is a scope/priority call, not a hard rule — use judgment.

## Integration with analyze-cve

This skill is called from Phase 2 of the `analyze-cve` skill, after the [Repo Guard](../analyze-cve/references/implementation.md#repo-guard--re-clone-if-missing) has confirmed `REPO_DIR` still exists.

**Input:** CVE profile from Phase 1, `--algo` preference from user, `REPO_DIR` and `GO_MODULE_DIR` set in Phase 0.7
**Output:** Risk level, evidence package, confidence assessment
**Next:** The analyze-cve skill uses risk level to decide whether to generate report and proceed to remediation
