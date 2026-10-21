#!/usr/bin/env bash
# Scan a repository's current checkout without creating a branch or commit.
# Usage: report.sh [repo]
# Exit 0: scan complete. Exit 2: coverage incomplete (see the WARNING lines).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -le 1 && "${1:-}" != -* ]] || die "Usage: report.sh [repo]"
preflight_check
use_upstream_goexperiment

STATE_FILE=$("$SCRIPT_DIR/detect.sh" "$@" | tail -1) || die "detect.sh failed (a branch argument is not accepted)"
[[ "$STATE_FILE" == */cve-fix-*/state.env ]] || die "unexpected state path: $STATE_FILE"
load_state "$STATE_FILE"
# A report leaves no trace: undo tracked files the build regenerates.
CLEAN_AT_START=false
[[ -n "$(git status --porcelain --untracked-files=no)" ]] || CLEAN_AT_START=true
trap '$CLEAN_AT_START && git checkout -- . 2>/dev/null; rm -rf -- "$(dirname "$STATE_FILE")"' EXIT
[[ "$BRANCH" == "$(git branch --show-current)" ]] || die "report.sh scans the checked-out branch; got $BRANCH"

# Use the validated JSON path once; table-mode scanner output has no evidence
# validation and an empty successful response cannot establish a complete scan.
SCAN_JSON=$("$SCRIPT_DIR/scan.sh" "$STATE_FILE" --fresh --json)
jq -r '
  def row($status):
    [.artifact.name, .artifact.version,
     ((.vulnerability.fix.versions // []) | join(", ")),
     .vulnerability.id, .vulnerability.severity, $status];
  ["NAME", "INSTALLED", "FIXED-IN", "VULNERABILITY", "SEVERITY", "STATUS"],
  (.matches[] | row("finding")),
  (.ignoredMatches[]? | row("ignored")) | @tsv
' <<< "$SCAN_JSON"
for sentinel in build-failed coverage-unknown scanner-degraded scan-transient; do
  if [[ -e "$STATE_FILE.$sentinel" ]]; then
    echo "INCOMPLETE: $sentinel — this scan may miss findings" >&2
    exit 2
  fi
done
