#!/bin/bash
# Collect complete declaration inventories; the reviewer resolves bindings/verdicts.
source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

scratch=$(mktemp -d "$REPO/.rebase-tmp/deprecation-inventory-XXXXXX")
scan_head=$(git rev-parse HEAD)
tool="$scratch/deprecation-scan"
build_rc=0
# Standalone stdlib tool: no target module resolution or dependency mutations.
GO111MODULE=off GOWORK=off GOFLAGS=-p=1 \
  timeout "${GATE_TIMEOUT:-300}" go build -o "$tool" "$SCRIPT_DIR/deprecation-scan.go" \
  > "$scratch/build.log" 2>&1 || build_rc=$?
details=("SCAN_HEAD: $scan_head" "TOOL_BUILD_EXIT: $build_rc" "TOOL_BUILD_LOG: $scratch/build.log")
if (( build_rc != 0 )); then
  finish_evidence "INCOMPLETE: declaration inventory tool could not compile" "${details[@]}"
fi

collected=0
incomplete=0
modules=0
discovery_rc=0
find . -name go.mod -not -path '*/vendor/*' -not -path '*/.claude/*' -not -path '*/.cache/*' -exec dirname {} \; \
  > "$scratch/modules-unsorted.txt" 2> "$scratch/discovery.log" || discovery_rc=$?
if (( discovery_rc == 0 )); then
  sort "$scratch/modules-unsorted.txt" > "$scratch/modules.txt" || discovery_rc=$?
fi
details+=("MODULE_DISCOVERY_EXIT: $discovery_rc" "MODULE_LIST: $scratch/modules.txt"
          "MODULE_DISCOVERY_LOG: $scratch/discovery.log")
if (( discovery_rc != 0 )); then
  finish_evidence "INCOMPLETE: module discovery failed (exit $discovery_rc)" "${details[@]}"
fi
while IFS= read -r module; do
  inc modules
  if [[ ! -d "$module/vendor" ]]; then
    details+=("NOT_COLLECTED: $module has no vendor; review resolved dependency source separately")
    inc incomplete
    continue
  fi
  if git check-ignore -q "$module/vendor" 2>/dev/null; then
    details+=("NOT_COLLECTED: $module vendor is gitignored")
    inc incomplete
    continue
  fi
  attempt=$(mktemp -d "$scratch/module-XXXXXX")
  scan_rc=0
  timeout "${GATE_TIMEOUT:-300}" "$tool" "$module" "$module/vendor" \
    > "$attempt/inventory.json" 2> "$attempt/stderr.log" || scan_rc=$?
  details+=("MODULE: $module" "INVENTORY_EXIT: $scan_rc"
            "INVENTORY: $attempt/inventory.json" "INVENTORY_STDERR: $attempt/stderr.log")
  if (( scan_rc != 0 )); then
    inc incomplete
    continue
  fi
  summary=$(python3 - "$attempt/inventory.json" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    data = json.load(source)
pairs = {(entry['File'], entry['Name']) for entry in data['Candidates']}
unbound = sum(entry['Kind'] == 'unbound-comment' for entry in data['Declarations'])
print(f"{data['DependencyFiles']} dependency files; {data['SourceFiles']} consumer files; "
      f"{len(data['Declarations'])} declaration/comment records; {len(pairs)} candidate file/name pairs; "
      f"{unbound} unbound comments requiring review")
PY
  )
  details+=("COUNTS: $summary")
  inc collected
done < "$scratch/modules.txt"

if (( modules == 0 )); then
  details+=("NOT_COLLECTED: no module directories found")
  inc incomplete
fi
head_after=$(git rev-parse HEAD)
details+=("HEAD_AFTER: $head_after")
if [[ "$scan_head" != "$head_after" ]]; then
  finish_evidence "INCOMPLETE: revision changed during collection; inventories do not verify current HEAD" "${details[@]}"
fi
finish_evidence "$collected module inventories collected; $incomplete incomplete; identifier bindings and SA1019 still require review" "${details[@]}"
