#!/bin/bash
# Gate companion: build-vet — deterministic go build + go vet check.
# Wired to step2/build-vet only. step4/build-vet-recheck has no companion — its .md
# inlines its own build/vet loop with a base-branch pre-existing-error exclusion.
# Writes evidence for the subagent to judge; never writes a verdict autonomously.
# Usage: bash build-vet.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()

for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | sort); do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    details+=("SKIP $mod_dir (vendor is gitignored)")
    echo "SKIP $mod_dir (vendor is gitignored)"
    continue
  fi

  echo "CHECK $mod_dir"
  details+=("CHECK $mod_dir")
  pushd "$mod_dir" >/dev/null

  build_rc=0
  build_out=$(timeout "${GATE_TIMEOUT:-300}" go build ./... 2>&1) || build_rc=$?
  if (( build_rc >= 124 )); then
    # Timeout or signal-kill: tool never completed. Write crash and defer —
    # never FAIL (a build that would compile must not be called broken).
    mkdir -p "$REPO/.rebase-tmp/gates"
    printf 'CRASH: exit %s (inner go build kill)\n' "$build_rc" \
      > "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash"
    echo "CRASH: ${GATE_NAME} — go build killed (exit ${build_rc}); no verdict; deferring to subagent"
    trap - EXIT; exit 0
  fi

  vet_rc=0
  vet_out=$(timeout "${GATE_TIMEOUT:-300}" go vet ./... 2>&1) || vet_rc=$?
  if (( vet_rc >= 124 )); then
    mkdir -p "$REPO/.rebase-tmp/gates"
    printf 'CRASH: exit %s (inner go vet kill)\n' "$vet_rc" \
      > "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash"
    details+=("VET_TIMEOUT $mod_dir: go vet did not complete within ${GATE_TIMEOUT:-300}s — test file errors may be undetected")
    echo "VET_TIMEOUT: ${GATE_NAME} — go vet killed in $mod_dir (exit ${vet_rc}); test file errors may be undetected"
    popd >/dev/null
    finish_evidence "$NEW_ISSUES build/vet errors" "${details[@]}"
  fi

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" == "# "* ]] && continue
    echo "  BUILD: $line"
    details+=("BUILD $mod_dir: $line")
    inc NEW_ISSUES
  done <<< "$build_out"

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" == "# "* ]] && continue
    echo "  VET: $line"
    details+=("VET $mod_dir: $line")
    inc NEW_ISSUES
  done <<< "$vet_out"

  popd >/dev/null
done

finish_evidence "$NEW_ISSUES build/vet errors" "${details[@]}"
