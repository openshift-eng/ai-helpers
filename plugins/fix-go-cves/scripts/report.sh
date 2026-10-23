#!/usr/bin/env bash
# Scan a repository's current checkout without creating a branch or commit.
# Usage: report.sh [repo]
# Exit 0: scan complete. Exit 2: coverage/preservation incomplete (see INCOMPLETE).
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
RESTORE_BUILD_OUTPUT=false
REPORT_HEAD="" REPORT_REF=""
_report_cleanup() {
  local status="$1" current_head="" current_ref=""
  trap - EXIT
  if $RESTORE_BUILD_OUTPUT; then
    current_head=$(git rev-parse --verify HEAD) || true
    current_ref=$(git symbolic-ref --quiet HEAD) || true
    if [[ "$current_head" != "$REPORT_HEAD" || "$current_ref" != "$REPORT_REF" ]]; then
      echo "INCOMPLETE: checkout moved during the build; preserving its files and index" >&2
      echo "Recovery state: $STATE_FILE" >&2
      exit 2
    fi
    if ! git restore --source="$REPORT_HEAD" --staged --worktree -- .; then
      echo "INCOMPLETE: could not restore tracked build changes to $REPORT_HEAD" >&2
      echo "Recovery state: $STATE_FILE" >&2
      exit 2
    fi
  fi
  if ! rm -rf -- "$(dirname "$STATE_FILE")"; then
    echo "INCOMPLETE: could not remove private report state: $STATE_FILE" >&2
    exit 2
  fi
  exit "$status"
}
trap '_report_cleanup "$?"' EXIT
[[ "$BRANCH" == "$(git branch --show-current)" ]] || die "report.sh scans the checked-out branch; got $BRANCH"

# A configured build may regenerate tracked files. Never run it over caller
# changes; reports without a build remain read-only and accept dirty input.
if [[ -n "${BUILD_CMD:-}" ]]; then
  if ! report_dirty=$(git status --porcelain --untracked-files=all); then
    echo "INCOMPLETE: could not establish checkout cleanliness before the build" >&2
    exit 2
  fi
  if [[ -n "$report_dirty" ]]; then
    echo "INCOMPLETE: configured report build requires a clean checkout; caller changes were preserved" >&2
    exit 2
  fi
  REPORT_HEAD=$(git rev-parse --verify HEAD)
  REPORT_REF=$(git symbolic-ref --quiet HEAD)
  RESTORE_BUILD_OUTPUT=true
fi

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
