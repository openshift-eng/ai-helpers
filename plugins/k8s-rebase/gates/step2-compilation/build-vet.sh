#!/bin/bash
# Gate companion: build-vet — deterministic go build + go vet check.
# Wired to step2/build-vet only. step4/build-vet-recheck has no companion — its .md
# inlines its own build/vet loop with a base-branch pre-existing-error exclusion.
# Writes evidence for the subagent to judge; never writes a verdict autonomously.
# Usage: bash build-vet.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()
failed_commands=0

while IFS= read -r mod_dir; do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    details+=("SKIP $mod_dir (vendor is gitignored)")
    echo "SKIP $mod_dir (vendor is gitignored)"
    continue
  fi

  echo "CHECK $mod_dir"
  details+=("CHECK $mod_dir")
  pushd "$mod_dir" >/dev/null || exit

  build_rc=0
  build_out=$(timeout "${GATE_TIMEOUT:-300}" go build ./... 2>&1) || build_rc=$?
  details+=("RESULT $mod_dir: build=$build_rc")
  (( build_rc == 0 )) || inc failed_commands
  if (( build_rc >= 124 )); then
    # Timeout or signal-kill: tool never completed. Write crash and defer —
    # never FAIL (a build that would compile must not be called broken).
    mkdir -p "$REPO/.rebase-tmp/gates"
    printf 'CRASH: exit %s (inner go build kill)\n' "$build_rc" \
      > "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash"
    echo "CRASH: ${GATE_NAME} — go build killed (exit ${build_rc}); no verdict; deferring to subagent"
    details+=("BUILD $mod_dir: $build_out" "NOT_RUN: vet and remaining modules; collection stopped after build kill")
    finish_evidence "INCOMPLETE: go build killed (exit $build_rc)" "${details[@]}"
  fi

  vet_rc=0
  vet_out=$(timeout "${GATE_TIMEOUT:-300}" go vet ./... 2>&1) || vet_rc=$?
  details+=("RESULT $mod_dir: vet=$vet_rc")
  (( vet_rc == 0 )) || inc failed_commands
  if (( vet_rc >= 124 )); then
    mkdir -p "$REPO/.rebase-tmp/gates"
    printf 'CRASH: exit %s (inner go vet kill)\n' "$vet_rc" \
      > "$REPO/.rebase-tmp/gates/${GATE_NAME}.crash"
    details+=("VET_TIMEOUT $mod_dir: go vet did not complete within ${GATE_TIMEOUT:-300}s — test file errors may be undetected")
    echo "VET_TIMEOUT: ${GATE_NAME} — go vet killed in $mod_dir (exit ${vet_rc}); test file errors may be undetected"
    popd >/dev/null || exit
    details+=("BUILD $mod_dir: $build_out" "VET $mod_dir: $vet_out"
              "NOT_RUN: remaining modules; collection stopped after vet kill")
    finish_evidence "INCOMPLETE: go vet killed (exit $vet_rc)" "${details[@]}"
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

  popd >/dev/null || exit
done < <(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | sort)

finish_evidence "$NEW_ISSUES build/vet diagnostic lines; $failed_commands failed commands" "${details[@]}"
