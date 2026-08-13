# Next Work

Production infrastructure for 100+ OpenShift repos.

## Where we are

Both modes work:
- spec=all (blind): 95% (20/21)
- spec=none (production): **100% (3/3)**
- overnight: **24/24 PASS**

## Correctness

### Silent go get assertion
Add warn-and-continue after skew alignment (~line 523):
grep k8s.io deps (excluding kube-openapi/utils/klog/gengo),
warn if any not at API_VERSION. Non-fatal — gate catches.

### CRD check scope
Replace `*/helm/*/crds/*.yaml` in run_checks (lines 244, 254)
with the 6-path + 3-exclusion pattern from fix_crd_int64.

### sigs.k8s.io in Rule 1
`k8s\.io/` already matches `sigs.k8s.io/` as substring —
removing the alternation is a NO-OP. Need explicit exclusion:
`grep -E "k8s\.io/" | grep -v "sigs\.k8s\.io/"` in Rule 1
(line 390). Rule 3 catches sigs.k8s.io correctly via bare
`go get`.

## Trust

### go-mod-tidy hook vs step2
Hook regex blocks scripts with args. Created depfix wrapper,
updated hook regex. **MUST also update step2-compilation.md
line 107** to call `bash "$PLUGIN_ROOT/scripts/k8s-rebase-
depfix.sh" <module>` instead of direct `go get`. Without this,
the hook blocks the agent on repos with dep conflicts.

### Pre-push hook on die()
ERR trap does NOT fire on die() — confirmed empirically.
Fix: `die() { echo "ERROR: $*" >&2; cleanup_hook; exit 1; }`
Safe if hook not yet installed (cleanup_hook returns 0).

### Dead rebase-report.md
Remove rules.md lines 84-88 (checkpoint instructions). Also
update step5-pr.md lines 45 and 57 (dangling references to
rebase-report.md).

### Hook jq guard
Add after set -euo pipefail in all 4 hooks:
`command -v jq >/dev/null 2>&1 || { printf '{"decision":
"block","reason":"jq required"}\n'; exit 0; }`

## Performance

- 33 PLUGIN_ROOT finds per run
- Companion script migration to gate-script-lib.sh
- Gate consolidation 33 → 31

## Dropped (verified wrong)

- Remove block-module-ops hook — hook is correct, scripts
  exempted by design
- EXIT trap for pre-push — removes safety guard on success
- Replace jq with grep/sed — breaks on escaped quotes
- Remove sigs.k8s.io alternation only — no-op, needs grep -v
- AtomicFIFO — doesn't affect fake clientsets
- ovnk rename — false
- "autofix counterproductive" — disproven, 3/3 PASS
