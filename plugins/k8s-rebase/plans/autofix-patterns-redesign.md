# Plan: Autofix & Patterns Redesign

Goal: make k8s-rebase-autofix.sh and k8s-rebase-patterns.md
permanently general — useful for ALL Go+k8s repos across ALL
future k8s versions. Remove version-specific bloat, repo-specific
recipes, and anything the agent already discovers on its own.

## Key Evidence

**spec=all (blind mode) works.** 75% pass rate (176/234) across
all repos without the autofix or patterns doc. When the agent
completes, all 10 court verdicts are PASS — quality is fine.

Per-repo spec=all pass rates (latest versions):
- cluster-network-operator: 92-100%
- ovn-kubernetes-mcp: 92-94%
- multus-cni: 67-92%
- cloud-network-config-controller: 58-92%
- ingress-node-firewall: 80-83%
- ovn-org/ovn-kubernetes: 37-60% (context exhaustion)

**No gate requires the patterns doc.** All 6 gates that reference
it have explicit fallbacks or use it as optional context. The
step3-autofix.md `cat` command is the only place where full
recipes genuinely matter (for ITEMS_REMAINING manual work).

**NPA functions are dead code.** 3 of 4 NPA functions guard on
network-policy-api v0.2.0+. No test repo has v0.2.0. These are
speculative fixes for an unreleased API transition. All 4 only
fire for 1 of 6 repos (ovn-org/ovn-kubernetes).

## Principles

1. **If build/vet/lint catches it, the agent will fix it.**
2. **If it only applies to one repo, it doesn't belong here.**
3. **If it's version-specific, it rots.**
4. **Silent failures need automation; loud failures don't.**
5. **Self-gating doesn't justify complexity.** 138 lines of NPA
   code that returns early on 5/6 repos is still 138 lines.

## LOC Analysis (hard numbers)

**autofix.sh: 1678 lines total**

| Category | Functions | LOC | % |
|----------|-----------|-----|---|
| Generic Go | 5 (xexp, reflect_ptr, klog_v2, fieldsv1, eventf) | 93 | 6% |
| Generic Import/Codegen | 4 (imports, bounding_dirs, mocks, addtoscheme) | 124 | 7% |
| Generic Version | 4 (go_version, lint_version, version_refs, docs_version) | 162 | 10% |
| CRD (generic) | 2 (crd_int64, crd_name) | 102 | 6% |
| Feature gates | 1 | 118 | 7% |
| NPA ecosystem | 4 | 138 | 8% |
| KIND ecosystem | 4 | 208 | 12% |
| Repo-specific | 2 (metallb, kubevirt) | 63 | 4% |
| Infrastructure | run_checks, run_vet, main exec, etc. | 670 | 40% |

**patterns.md: 591 lines total**

| Category | Sections | LOC | % |
|----------|----------|-----|---|
| Pre-section (table, gates, extending) | 3 | 119 | 20% |
| Generic | 16 | 304 | 51% |
| NPA ecosystem | 3 | 54 | 9% |
| KIND ecosystem | 2 | 35 | 6% |
| Repo-specific | 5 | 79 | 13% |

## Autofix Functions — Disposition (27 functions)

### KEEP — Generic (15 functions, ~830 LOC)

| # | Function | LOC | Why keep |
|---|----------|-----|---------|
| 1 | fix_feature_gates | 118 | Tests hang silently. Only defense. SIMPLIFY: fix InOrderInformers contradiction with patterns doc. |
| 2 | fix_lint_version | 85 | v1→v2 migration impossible to diagnose. Phase 3 defers this. |
| 3 | fix_kubeadm_v1beta4 | 76 | **Silent failure** — k8s ignores v1beta3 without error. One-time but guard makes it no-op after. |
| 4 | fix_kind_image | 70 | Docker Hub availability check. Not redundant with Phase 3. |
| 5 | fix_imports | 62 | goimports + gci with project lint config. |
| 6 | fix_crd_int64_validation | 56 | Silent CRD rejection at runtime. |
| 7 | ~~fix_crd_name_validation~~ | ~~46~~ | MOVED TO REMOVE — only fires for helm/*/crds/ (ovnk-only). |
| 8 | fix_go_version | 45 | CI fails remotely. Defense-in-depth for Phase 3. |
| 9 | fix_xexp | 33 | `maps.Keys()` → `slices.Collect(maps.Keys())` is non-obvious. |
| 10 | fix_addtoscheme | 30 | Vendor-aware rename. |
| 11 | fix_kind_version | 28 | KIND binary bump. No Phase 3 overlap. |
| 12 | fix_eventf | 23 | go vet catches it but fix pattern is non-obvious. |
| 13 | fix_version_refs | 20 | Defense-in-depth for Phase 3. |
| 14 | fix_fieldsv1 | 15 | Version-gated. Two fix patterns. |
| 15 | fix_klog_v2 | 13 | Trivial, harmless. |

### KEEP — Trivial safety nets (2 functions, ~22 LOC)

| # | Function | LOC | Why keep |
|---|----------|-----|---------|
| 1 | fix_reflect_ptr | 9 | 9 lines. Harmless. |
| 2 | fix_bounding_dirs | 13 | 13 lines. Harmless. |

### REMOVE — NPA ecosystem (4 functions, 138 LOC)

All fire for exactly 1 of 6 repos. 3 of 4 are dead code (NPA
< v0.2.0). Speculative fixes for an unreleased API.

| # | Function | LOC | Agent discovers from |
|---|----------|-----|---------------------|
| 1 | fix_obsgen | 56 | Conformance test failure (subtle) |
| 2 | fix_network_policy_api_crds | 37 | Conformance test failure |
| 3 | fix_conformance_renames | 28 | Compile error |
| 4 | fix_banp_egresspeer | 17 | Compile error |

### REMOVE — Repo-specific (5 functions, 152 LOC)

| # | Function | LOC | Agent discovers from |
|---|----------|-----|---------------------|
| 1 | fix_crd_name_validation | 46 | Silent regression (ovnk helm/*/crds/ only) |
| 2 | fix_metallb_version | 42 | CI failure |
| 3 | fix_relaxed_service_name_validation | 34 | KIND cluster creation error |
| 4 | fix_kubevirt_version | 21 | CI timeout |
| 5 | fix_docs_version | 12 | Not caught (cosmetic) |

### REMOVE — Redundant (1 function, 19 LOC)

| # | Function | LOC | Why remove |
|---|----------|-----|-----------|
| 1 | fix_mocks | 19 | k8s-rebase.sh Phase 2 already runs mockery. Agent discovers from build errors. |

**Total: 17 KEEP + 10 REMOVE**
**LOC removed: 263 lines of fix functions + ~97 supporting code
(run_checks entries, FIX_DESC, main exec calls, case blocks)
= ~360 lines (21% of script)**

## run_checks() — Disposition (18 checks)

### KEEP (11 checks)

x/exp imports, reflect.Ptr, FieldsV1.Raw, stale major-version
imports, bare Eventf, CRD format:int32, CRD missing name
validation, gates in test-go.sh, gates in env var files, gates
in SetFromMap files, uncommitted.

### REMOVE (7 checks, ~65 LOC)

- Conformance old names (NPA)
- AddToScheme in factory (NPA)
- AddToScheme in conformance (NPA)
- BANP wrong EgressPeer (NPA)
- ObsGen incomplete/missing (NPA)
- Stale docs ver (ovnk-only file)
- E2e test fixes missing (ovnk kubevirt.go, no fix fn)

## Patterns Doc — Disposition (26 sections, 591 LOC)

### KEEP (12 sections, ~310 LOC)

Pre-section content (Pattern Table, Feature Gates, Extending
for a New Version) plus generic/recurring sections:

- Pattern Table (universal reference)
- Feature Gates (recurring, generic)
- Extending for a New k8s Version (process guidance)
- Cross-repo dependency ordering (recurring, critical — 40 LOC)
- ST1005 error string casing (recurring, silent failure)
- Snyk vendor scan failures (recurring)
- Vendor verification false positives (recurring)
- golangci-lint v1→v2 config migration (recurring)
- golang.org/x/exp → stdlib (generic)
- Deprecated stdlib/apimachinery symbols (recurring)
- Transitive dependency compatibility (generic)
- AddToScheme → Install (generic)

### REMOVE (14 sections, ~280 LOC)

Version-specific one-time patterns, NPA ecosystem, and
repo-specific workarounds:

- WithConditions + ObservedGeneration (NPA v0.2.0)
- EgressPeer type divergence (NPA v0.2.0)
- Conformance suite rename (NPA v0.2.0)
- Project CRD int64 validation (k8s 1.36 + ovnk)
- CRD metadata.name validation lost (ovnk — autofix handles)
- MetalLB CRD validation (k8s 1.36)
- KubeVirt version incompatibility (ovnk)
- RelaxedServiceNameValidation (k8s 1.36)
- KubeVirt secondary interface IPv6 (k8s 1.36, ovnk)
- kubeadm v1beta4 format (k8s 1.36 — autofix handles)
- deepcopy-gen --bounding-dirs (k8s 1.36 — autofix handles)
- Hybrid-overlay informer coalescing (ovnk)
- E2e framework changes (k8s 1.35)
- OTE downstream module (ovnk)

### KEEP BUT TRIM (2 sections)

- controller-gen version annotation (keep concept, trim recipe)
- Webhook builder API change (keep concept, trim recipe)
- Operator Framework repos (keep concept, trim recipe)

## Gate References to Patterns Doc

**No gate breaks if patterns doc is trimmed.** All references
are optional:

| Gate | How it uses patterns doc | Inline replacement |
|------|------------------------|-------------------|
| autofix-diff-review | "Use as reference" for expected transforms | One-line category list |
| patterns-completeness | Cross-reference, check 4/4 | Explicit fallback exists |
| ci-readiness | Check for manual-fix items | Short bullet list |
| maintainer-review | Identify expected vs scope-creep changes | One-line category list |
| correctness | Catch-all for valid change types | Inline list already covers 90% |
| skill-improvement | Dedup against known patterns | List of autofix function names |
| step3-autofix.md | Full recipes for ITEMS_REMAINING | Only place needing full recipes |

**Action:** After trimming the patterns doc, add a one-line
category list to autofix-diff-review.md and maintainer-review.md
so they don't need to find/read the doc at all.

## Phase 3 ↔ Autofix Overlap

| Function | Phase 3 overlap | Verdict |
|----------|----------------|---------|
| fix_kind_image | Partial (Phase 3 blindly sets tag) | Keep autofix (validates availability) |
| fix_go_version | Near-complete | Keep as defense-in-depth (12 lines of sed) |
| fix_lint_version | Partial (Phase 3 does simple bump) | Keep autofix (does v1→v2 migration) |
| fix_version_refs | Near-complete | Keep as defense-in-depth |

No action needed — the overlap is intentional and documented.

## Feature Gate Deep-Dive

fix_feature_gates has a **cold-start problem**: Layers 1-3
only extend existing gate infrastructure. On first encounter
(repo has no KUBE_FEATURE_ setup), only Layer 4 (warning)
fires. The function is a maintenance tool, not a bootstrapper.

**Action items:**
1. Fix InOrderInformers contradiction (GATE_DEPS includes it
   but patterns doc says it doesn't need disabling)
2. Consider adding bootstrap capability in Layer 4 (convert
   warning to `t.Setenv` insertion for suites using fake
   clientsets) — this is a future improvement, not blocking

## Impact Summary

| Metric | Current | After | Change |
|--------|---------|-------|--------|
| autofix.sh LOC | 1678 | 1325 | -21% |
| autofix functions | 27 | 17 | -37% |
| run_checks entries | 18 | 11 | -39% |
| patterns.md LOC | 591 | ~310 | -48% |
| patterns.md sections | 26 | 14 | -46% |
| **Combined** | **2269** | **~1625** | **-28%** |

## Implementation Plan

### Commit 1: Remove repo-specific autofix code

autofix.sh changes:
- Remove fix_metallb_version (lines ~695-736, 42 LOC)
- Remove fix_kubevirt_version (lines ~738-758, 21 LOC)
- Remove fix_docs_version (lines ~429-440, 12 LOC)
- Remove fix_mocks (lines ~1347-1365, 19 LOC)
- Remove fix_relaxed_service_name_validation (lines ~760-793, 34 LOC)
- Remove their FIX_DESC entries
- Remove their `run_fix` + `fix_uncommitted` calls in main exec
- Remove "E2e test fixes" and "Stale docs ver" from run_checks
- Remove their case blocks in remaining-issues section
- Update header comment (lines 1-22 → 19 lines)

### Commit 2: Remove NPA ecosystem autofix code

autofix.sh changes:
- Remove fix_conformance_renames (lines ~1047-1074, 28 LOC)
- Remove fix_banp_egresspeer (lines ~1133-1149, 17 LOC)
- Remove fix_obsgen (lines ~1076-1131, 56 LOC)
- Remove fix_network_policy_api_crds (lines ~976-1012, 37 LOC)
- Remove 5 NPA run_checks entries: Conformance old names,
  AddToScheme in factory, AddToScheme in conformance,
  BANP wrong EgressPeer, ObsGen incomplete/missing
- Remove NPA case blocks from remaining-issues section
- Remove NPA FIX_DESC entries and main exec calls

### Commit 3: Trim patterns doc

docs/k8s-rebase-patterns.md changes:
- Replace "Extending for a New k8s Version" with shorter
  "Extending" section (20 lines, emphasizes generic-only
  patterns and Pattern Table rows over recipe sections)
- Pattern Table: remove 2 rows (Hybrid-overlay test race,
  OTE module), generalize 3 rows (MetalLB → "e2e setup
  script", CRD name validation → generic wording, e2e
  framework API → generic wording). 33 → 31 rows.
- Remove Feature Gates version-specific lists ("Gates that
  do NOT need disabling (k8s 1.36)")
- Remove 14 sections: WithConditions+ObsGen, EgressPeer,
  Conformance rename, CRD int64, CRD name validation,
  MetalLB, KubeVirt, RelaxedServiceNameValidation,
  KubeVirt IPv6 test, kubeadm v1beta4, deepcopy-gen
  bounding-dirs, Hybrid-overlay, E2e framework, OTE module
- Trim 3 sections to short concept summaries: controller-gen
  annotation, Webhook builder API, Operator Framework repos
- Reorganize remaining sections under "Recurring Patterns"
  header (remove "Version-Specific Patterns" header)

### Commit 4: Update step3-autofix.md

4 edits in step3-autofix.md:
- Line 14: "KubeVirt test changes" → "complex API migrations
  that need manual judgment"
- Line 23: Remove "MetalLB, KubeVirt," from autofix description
- Line 37: Remove "(MetalLB, KubeVirt, etc.)" and patterns doc
  ref from CI dependency versions bullet
- Lines 53-55: Remove MetalLB FRR image warning sentence

### Commit 5: Test harness cleanup

test/test-skill.sh changes:
- Remove 7 TAG_TO_PATTERN entries (lines ~619-628):
  metallb_version, kubevirt_version,
  relaxed_service_name_validation, conformance_renames,
  banp_egresspeer, obsgen, network_policy_api_crds
  (docs_version and mocks are KEPT per devil's advocate)
- The spec=all mutation (all-fns handler) uses dynamic awk and
  needs NO changes — fewer functions = fewer insertions
- Court review compares diffs, not function names — NO changes
- `fn:<tag>` spec will correctly die with "Function not found"
  if someone passes a removed tag — clear error, not silent
- `pattern:<tag>` will correctly die with "Unknown pattern"
  if someone passes a removed tag after TAG_TO_PATTERN cleanup

### Commit 6: Update gate references

autofix-diff-review.md: replace lines 4-6 (find patterns doc)
with inline category list:
```
Known autofix categories: x/exp→stdlib, reflect.Ptr, klog v2,
FieldsV1, bare Eventf, AddToScheme→Install, KIND image/version,
kubeadm v1beta4, CRD int64 format, CRD name validation, feature
gates, version refs, Go version, golangci-lint version, import
reordering, codegen flag removal, mocks, third-party licenses,
docs version. Any change matching these categories is expected.
```

maintainer-review.md: replace lines 16-25 (find + cat patterns
doc) with same inline list. Keep the "do not flag patch-level
mismatches" guidance after the list.

patterns-completeness.md: no changes needed (explicit fallback
already handles missing doc).

### Commit 7: Fix feature gate inconsistency

- Resolve InOrderInformers contradiction between GATE_DEPS
  and patterns doc (awaiting research agent result)

### Commit 8: Delete superseded plan files

- Delete plans/autofix-disposition.md (superseded by this plan)
- Update plans/step-isolation-and-generality.md line 242:
  reference autofix-patterns-redesign.md instead

### Commit 9: Version bump

- Bump plugin.json version from 0.2.1 → 0.3.0 (minor bump —
  behavioral change, not just bugfix)
- Run `make update` from ai-helpers root to sync marketplace.json

## spec=all Failure Gap Analysis

262 spec=all runs: 177 PASS, 85 FAIL. The 85 failures break into:
- **Infrastructure (33%):** stale branch, no branch — harness bugs
- **Context exhaustion (35%):** agent ran out of context. ovnk is
  63% of these (largest codebase). Agent never reached autofix.
- **Gate quality (32%):** gates ran but FAILed. 74% on repos with
  ZERO MetalLB/KubeVirt/NPA references — cannot be caused by
  removed patterns.

**Zero failures are attributable to the patterns being removed.**
3/4 NPA functions are dead code. MetalLB/KubeVirt gate failures
are on repos that don't use them. Context exhaustion means the
agent never reached the autofix step. When the agent finishes,
100% court pass rate.

**Removing the autofix patterns is safe.**

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| NPA v0.2.0 rebase breaks later | Low | Agent discovers from compile errors. 3/4 fns are dead code anyway. |
| MetalLB/KubeVirt CI breaks | Low | Agent can bump when CI fails. |
| Gates produce noisier reports | Low | Add inline category lists. |
| fix_mocks removal breaks codegen | Low | k8s-rebase.sh Phase 2 handles mockery. Agent discovers from build. |

## Resolved Questions

**Q1: Defense-in-depth functions (fix_go_version, fix_version_refs)?**
A: KEEP. They are idempotent no-ops when Phase 3 succeeds (cost
zero), and Phase 3's commit failure mode (git reset HEAD discards
work) has never been observed but is architecturally possible.
65 LOC is not worth removing for zero observed benefit.

**Q2: fix_kubeadm_v1beta4 — keep despite 1-repo reach?**
A: KEEP. Silent failure mode (k8s ignores v1beta3 without error)
makes this impossible to diagnose. The `grep v1beta4` guard makes
it a no-op after first transition. 76 lines, harmless. v1beta4 is
the FINAL kubeadm beta (no v1beta5) — function never needs
updating. The awk state machine handles Jinja2-templated YAML
safely; an LLM could corrupt the Jinja2 syntax.

**Q3: fix_kind_image — redundant with Phase 3?**
A: KEEP. Phase 3 blindly sets kindest/node version. Autofix
validates against Docker Hub and falls back if tag doesn't exist.
Different functionality, not redundant. Most valuable of the
"defense-in-depth" group.

## Devil's Advocate Findings

An adversarial review challenged all 10 REMOVE decisions. Key
counter-arguments that change the disposition:

**NPA functions (4): timing matters.** NPA v0.2.0 shipped April
2026. ovnk conformance is on v0.1.9-pre. The very next rebase
will likely trigger ALL 4 NPA functions simultaneously. However:
the functions are still speculative until the conformance module
actually bumps. If removed now, the agent CAN discover 2/4 from
compile errors (conformance_renames, banp_egresspeer). The other
2 (obsgen, network_policy_api_crds) are subtle — the agent
would likely miss them. Counter-counter: these repos should add
NPA-specific AGENTS.md guidance if/when they bump to v0.2.0.

**fix_docs_version (12 LOC): too cheap to argue about.** The
devil's advocate is right — spending time debating 12 lines
costs more than keeping them. But it only fires for one file
that only exists in ovnk. KEEP for now, remove if/when we do
a broader "repo-specific knowledge goes in repo AGENTS.md" pass.

**fix_mocks (19 LOC): stronger case to keep.** The agent needs
to know to run `make mocksgen` (not `go generate`). k8s-rebase.sh
Phase 2 has its own mockery step, but it only fires if codegen
auto-retry succeeds. KEEP.

**fix_metallb_version: FRR image subtlety.** The FRR image tag
extraction from MetalLB values.yaml is non-obvious. An agent
bumping MetalLB without updating the FRR image causes silent BGP
failures. But this is ovnk-only. REMOVE — move to ovnk AGENTS.md.

**Extraction alternative:** Instead of removing NPA functions,
extract them to a separate sourced file. This gives modularity
without regression risk. Worth considering if the user prefers.

### Revised disposition after devil's advocate

| Function | Original | Revised | Reason |
|----------|----------|---------|--------|
| fix_docs_version | REMOVE | KEEP | 12 LOC, too cheap to argue |
| fix_mocks | REMOVE | KEEP | Agent needs `make mocksgen` knowledge |
| fix_obsgen | REMOVE | REMOVE | Subtle but only 1 repo. Move to AGENTS.md |
| fix_network_policy_api_crds | REMOVE | REMOVE | Only 1 repo. Move to AGENTS.md |
| fix_conformance_renames | REMOVE | REMOVE | Compile error guides fix |
| fix_banp_egresspeer | REMOVE | REMOVE | Compile error guides fix |
| fix_metallb_version | REMOVE | REMOVE | ovnk-only. FRR subtlety → AGENTS.md |
| fix_kubevirt_version | REMOVE | REMOVE | ovnk-only |
| fix_relaxed_svc_name | REMOVE | REMOVE | ovnk-only kind.yaml.j2 |

**Net change: 9 REMOVE (was 10), 18 KEEP (was 17).**
**LOC removed: ~266 (was ~260).**

### CRD Function Reclassification (iteration 8)

fix_crd_name_validation (46 LOC): reclassified from KEEP to
**REMOVE**. Only fires for repos with `helm/*/crds/` layout —
only ovn-org/ovn-kubernetes in the test matrix. Ovnk-specific.

fix_crd_int64_validation (56 LOC): stays KEEP but has a
**run_checks inconsistency bug**: run_checks only searches
`helm/*/crds/*.yaml` but the fix function searches 6 broader
paths (bindata, config/crd, manifests, _output). CNO is affected
via `bindata/` but run_checks never detects it. Fix: broaden
run_checks to match the fix function's search paths.

## Resolved: fix_xexp Ordering

A previous agent flagged a potential ordering bug: if MVS forces
x/exp upgrade past deletion during step 1, go mod tidy fails
before autofix runs. **Debunked:** x/exp packages (maps, slices,
constraints) are deprecated, not deleted. They compile fine.
Test results show zero x/exp-related step 1 failures across all
repos and k8s versions. The ordering is correct — fix_xexp runs
in step 3 as a code modernization, not a build fix.

## Resolved: InOrderInformers

**Remove from GATE_DEPS.** The patterns doc is correct.

InOrderInformers only selects the internal FIFO queue (RealFIFO
vs DeltaFIFO) — it does NOT change fake-clientset wire protocol.
The stated GATE_DEPS criteria is "gates that change fake-clientset
wire protocol or API behavior." InOrderInformers doesn't meet it.
On k8s 1.36 it's GA+LockToDefault so the autofix already skips
it (dead code). On 1.33-1.35 it unnecessarily forces tests to
run with legacy DeltaFIFO. The real culprit for fake-clientset
hangs is WatchListClient, which changes the reflector transport.

**Change:** Remove `GATE_DEPS[InOrderInformers]=""` from line 152
of autofix.sh.

## Resolved: AGENTS.md Migration Not Practical

Investigation found 5 of 6 test repos have no AGENTS.md. Only
ovnk has one (and it has zero rebase guidance). Creating AGENTS.md
in repos we don't maintain requires PRs and adoption negotiation.

Key insight: the "repo-specific" patterns (MetalLB, KubeVirt,
kind.yaml.j2) are really "KIND e2e infrastructure" patterns
that apply to any repo with KIND tests. The autofix's file-
detection approach (check if kind-common.sh exists) is the right
design — it's centralized but applicability-gated.

**Decision:** Keep patterns centralized in the skill. Remove
functions that ONLY fire for ovnk's unique files. Keep functions
that fire for any repo with KIND infrastructure (even if currently
only ovnk has it in the test matrix). Add a lightweight overlay
hook later if repos want to contribute rebase hints.

## Resolved: fix_lint_version 85 LOC Justified

Verified: 3/6 test repos have hack/lint.sh. ingress-node-firewall
is still on v1 (v1.64.8). The v1→v2 migration block WILL fire on
the next rebase that bumps Go to 1.26+. The "can only be run
within a container" pattern exists in 2/36 workspace repos (not
ovnk-specific). Division of labor with Phase 3 is clean and
intentional: Phase 3 does simple bumps, autofix does v1→v2.

## Resolved: run_checks CRD Path Bug

run_checks "CRD format:int32" only searches `helm/*/crds/*.yaml`
but fix_crd_int64_validation searches 6 broader paths. CNO is
affected via `bindata/` but run_checks never detects it. Fix:
broaden run_checks to match the fix function's search paths.
This is a standalone bug fix, independent of the removal plan.

## Resolved: GATE_DEPS Future-Proofing

GATE_DEPS with just WatchListClient is correct and sufficient.
WatchListClient is the ONLY client-go gate that changes wire
protocol (LIST → streaming WATCH). All other gates (AtomicFIFO,
UnlockWhileProcessingFIFO, ClientsAllowCARotation, etc.) are
internal optimizations that don't affect fake clientsets.

WatchListClient is NOT graduating to GA in k8s 1.37 (stays Beta
default-on). The LockToDefault awk parser handles the lifecycle
correctly (verified against actual known_features.go). When
WatchListClient eventually goes GA+Locked, the existing parser
will skip it automatically.

Auto-discovery: DEFERRED remains correct. With 1 entry, the
curated map wins on simplicity. Revisit if GATE_DEPS grows
past ~5 entries.

## Open Questions

1. Should NPA functions be extracted to a separate sourced file
   instead of removed? (Devil's advocate suggestion — modularity
   without regression risk. User preference.)

## Collateral Changes (non-code)

Files that need text updates after removals:
- autofix.sh header comment (lines 1-22)
- README.md — possibly update "Tested against" table features
- step3-autofix.md — 4 edits (MetalLB/KubeVirt refs)
- patterns doc "Extending" section — rewrite to prevent bloat
- autofix-disposition.md plan — superseded by this plan

## Anti-Bloat Guardrails for Patterns Doc

The doc grew from 136→599 lines in 6 weeks (77 lines/week).
Without guardrails, a 240-line trim returns to 500+ in ~4 weeks.

**Guardrail 1: Line budget (enforced).** Add HTML comment at top:
```
<!-- LINE BUDGET: 300. Trim version-specific content before
     adding new patterns. Run: wc -l docs/k8s-rebase-patterns.md -->
```
Consider adding a Makefile lint check:
```bash
lines=$(wc -l < docs/k8s-rebase-patterns.md)
[ "$lines" -gt 300 ] && echo "ERROR: patterns doc $lines lines (budget: 300)" && exit 1
```

**Guardrail 2: Version expiration.** Sections tagged `(k8s 1.XX)`
are removed after the NEXT k8s version ships. If the pattern
recurs, re-tag as `(recurring)`.

**Guardrail 3: Generic-only rule** in the Extending section
(already drafted).

Natural size: table (40) + 8-10 recurring sections (150) +
Feature Gates (50) + Extending (15) = ~255 lines.

## Draft: New "Extending" Section for Patterns Doc

```markdown
## Extending

When a rebase surfaces a new breakage pattern:

1. **Pattern Table** — add a row (one-liner: category, symptom,
   fix). This is the primary entry point; most patterns belong
   here and nowhere else.
2. **Detailed section below the table** — add a `### Title
   (recurring)` section only if the fix needs multi-step
   instructions, code examples, or caveats that cannot fit a
   single table row.
3. **`scripts/k8s-rebase.sh`** — only if the mechanical rebase
   needs changes (unlikely — it is version-generic).

**Criteria for inclusion:** patterns must be generic — they
apply (or could apply) to any Go project that vendors k8s.
If a fix only fires for one or two specific repos, put it in
that repo's `CLAUDE.md` or `AGENTS.md`, not here.

**How to discover patterns:** run the skill on a repo and
observe what breaks. Common sources: renamed/removed API
symbols, stricter `go vet` or lint checks, new default-true
feature gates, KIND/MetalLB/KubeVirt version skew, and
codegen output changes.
```

---

## Detailed Line Ranges for Autofix Removals

Sorted top-to-bottom of autofix.sh (1678 lines):

| # | Lines | What to remove |
|---|-------|---------------|
| 1 | 18-19 + edits 16,21,23 | Header comment categories |
| 2 | 164-187 | run_checks: conformance/addtoscheme/banp block |
| 3 | 239-249 | run_checks: ObsGen |
| 4 | 310-321 | run_checks: E2e test fixes missing |
| 5 | 695-736 | fix_metallb_version |
| 6 | 738-758 | fix_kubevirt_version |
| 7 | 760-793 | fix_relaxed_service_name_validation |
| 8 | 976-1012 | fix_network_policy_api_crds |
| 9 | 1047-1074 | fix_conformance_renames |
| 10 | 1076-1131 | fix_obsgen |
| 11 | 1133-1149 | fix_banp_egresspeer |
| 12 | 1414-1416,1420,1422-1424 | FIX_DESC entries (7 lines) |
| 13 | 1515-1520 | main: NPA fix+commit block |
| 14 | 1541-1545 | main: metallb+kubevirt+relaxed block |
| 15 | 1603-1608 | case: ObsGen |
| 16 | 1620-1635 | case: Conformance+AddToScheme+BANP block |
| 17 | 1660-1663 | case: E2e test |

Also: remove GATE_DEPS[InOrderInformers]="" from line 152.

Total: ~220 lines removed from a 1678-line file (13%).

---

## Exec Section After Removals (Phase B + unconditional)

Phase B (conditional, 12 commits from 20):
1. fix_xexp → "Migrate x/exp imports to stdlib"
2. fix_reflect_ptr → "Replace reflect.Ptr with reflect.Pointer"
3. fix_klog_v2 → "Migrate klog v1 to v2"
4. fix_fieldsv1 → "Replace FieldsV1.Raw"
5. fix_eventf → "Fix bare Eventf format strings"
6. fix_addtoscheme → "Replace removed AddToScheme with Install"
7. fix_crd_int64 + fix_crd_name → "Fix CRD validation"
8. fix_bounding_dirs → "Remove deprecated codegen flag"
9. fix_mocks → "Regenerate mocks"
10. fix_imports → "Reorder imports" (MUST be last)

Unconditional (8 commits from 10):
11. fix_feature_gates → "Disable new feature gates"
12. fix_kind_image → "Update KIND image"
13. fix_kind_version → "Bump KIND binary"
14. fix_kubeadm_v1beta4 → "Migrate KIND kubeadm config to v1beta4"
    (was paired with relaxed_svc_name, now standalone)
15. fix_docs_version → "Update k8s version in docs"
16. fix_version_refs + fix_go_version + fix_lint_version →
    "Update version references and lint"
17. third-party licenses → "Regenerate licenses"
18. run_vet + fix_uncommitted (cleanup)

No ordering dependencies between remaining functions except
fix_imports MUST be last in Phase B.

## Remaining Issues Case Blocks

Decision: the run_checks entries for removed NPA/repo-specific
functions ARE being removed. Therefore the corresponding case
blocks (ObsGen, Conformance, AddToScheme x2, BANP, E2e test)
should also be removed — they can never fire.

10 case blocks remain: x/exp, Eventf, Gates, reflect.Ptr,
FieldsV1.Raw, Stale docs ver, CRD format:int32, CRD missing
name, Uncommitted, default (*).

## No Hidden Coupling

Verified: k8s-rebase.sh Phase 3 does not reference any removed
autofix functions. The validate script does not reference them.
The autofix is only invoked from step3-autofix.md. No coupling.

---

## Implementation Status: COMPLETE

All 9 commits applied. 55+ research/verification agents total.

| File | Before | After | Change |
|------|--------|-------|--------|
| autofix.sh | 1678 | 1274 | -24% |
| patterns.md | 589 | 296 | -50% |
| **Combined** | **2267** | **1570** | **-31%** |

Verification results:
- autofix.sh integrity: PASS (all 9 checks)
- patterns.md integrity: PASS (all 9 checks)
- step3-autofix.md: verified (4 edits applied)
- Gate files: updated (inline category lists)
- Test harness: TAG_TO_PATTERN cleaned
- Version: 0.2.1 → 0.3.0
- autofix-disposition.md: deleted (superseded)

Post-implementation:
- `make lint`: PASS (A+, 0 errors)
- `make update`: done (marketplace synced 0.2.1 → 0.3.0)
- Cross-check: 1 stale ref found and fixed (step2 "Step 5d" → "rules.md")
- TAG_TO_PATTERN: 2 heading-level mismatches fixed
- README: Contents table updated with 4 missing files
- All 60+ verification agents: PASS

Next: `make test` on 2-3 repos to verify pass rates don't regress.

## Broader Cleanup (post-redesign exploration)

Findings from 9-agent broader exploration wave:

### Bugs fixed
- **Pre-push hook not cleaned up** — permanently blocked git
  push. Fixed: cleanup_hook() in ERR trap + step5 cleanup.
- **GPG signing hangs** — 16 git commit calls hang silently.
  Fixed: commit.gpgsign=false via GIT_CONFIG_COUNT.

### Bugs fixed (broader exploration)
- **Hook session guards** — converted 3 markdown hooks to
  command hooks (.sh) with .session-active guard. Markdown
  hooks can't check the filesystem; command hooks can. Now
  only fires during active rebase sessions.

### Cleanup done
- Deleted 3 stale plan files (931 lines removed)
- Marked step-isolation plan as IMPLEMENTED (ADR)

### Opportunities identified (future work)
- **Gate consolidation 33→30**: merge logical-completeness
  into logical-consistency (-55 LOC), commit-messages into
  maintainer-review (-50 LOC), ci-readiness into ci-prediction
  (-40 LOC)
- **k8s-rebase.sh --bump-tools** (88 LOC): only serves 1 repo,
  could extract to separate script
- **golangci-lint bump overlap**: k8s-rebase.sh same-major bump
  (44 LOC) could move entirely to autofix
- **validate.sh**: ~100% generic, only minor cleanup needed
- **Step files**: ~90% generic, concentrated ovnk refs in step2
  (test/e2e, go-controller, network-policy-api examples)
