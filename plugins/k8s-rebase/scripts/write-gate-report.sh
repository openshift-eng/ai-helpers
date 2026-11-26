#!/bin/bash
# write-gate-report.sh — Helper for gate subagents to write consistent reports.
#
# Usage: write-gate-report.sh <repo> <gate-name> <verdict> <issues> <summary> [details...]
#
# Example:
#   write-gate-report.sh /path/to/repo step3-deprecated-calls PASS 0 "No deprecated calls found"
#   write-gate-report.sh /path/to/repo step3-deprecated-calls FAIL 3 "Found 3 deprecated calls" \
#     "pkg/foo.go:42: AddToScheme is deprecated" \
#     "pkg/bar.go:17: klog v1 import"

set -euo pipefail

REPO="${1:?Usage: $0 <repo> <gate-name> <verdict> <issues> <summary> [details...]}"
GATE_NAME="${2:?Missing gate name}"
VERDICT="${3:?Missing verdict (PASS, FAIL, SKIP, or INCONCLUSIVE)}"
ISSUES="${4:?Missing issue count}"
SUMMARY="${5:?Missing summary}"
shift 5

[[ "$VERDICT" =~ ^(PASS|FAIL|SKIP|INCONCLUSIVE)$ ]] || { echo "ERROR: verdict must be PASS, FAIL, SKIP, or INCONCLUSIVE (got: $VERDICT)" >&2; exit 1; }
[[ "$GATE_NAME" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "ERROR: invalid gate name: $GATE_NAME" >&2; exit 1; }

# A successful vulnerability verdict requires complete query coverage, not a
# sample of dependencies. The companion collects facts; the reviewer still
# decides severity, attribution, reachability, and the final verdict.
if [[ "$GATE_NAME" == step4-dep-cve-check && "$VERDICT" =~ ^(PASS|SKIP)$ ]]; then
  evidence_digest=$(python3 "$(dirname "$0")/check-cve-evidence.py" "$REPO") || exit 1
fi

mkdir -p "$REPO/.rebase-tmp/gates"
{
  echo "HEAD: $(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "VERDICT: $VERDICT"
  [[ -z "${evidence_digest:-}" ]] || echo "EVIDENCE_SHA256: $evidence_digest"
  echo "ISSUES: $ISSUES"
  echo "SUMMARY: $SUMMARY"
  echo "DETAILS:"
  printf '%s\n' "$@"
} > "$REPO/.rebase-tmp/gates/${GATE_NAME}.report.tmp"
mv "$REPO/.rebase-tmp/gates/${GATE_NAME}.report.tmp" \
   "$REPO/.rebase-tmp/gates/${GATE_NAME}.report"
