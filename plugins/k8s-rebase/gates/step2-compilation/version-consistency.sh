#!/bin/bash
# Gate companion: version-consistency — check k8s.io/* versions match target.
# Usage: bash version-consistency.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

NEW_ISSUES=0
details=()

TARGET=""
if [[ -f "$REPO/.rebase-tmp/target-k8s-api-version.txt" ]]; then
  TARGET=$(cat "$REPO/.rebase-tmp/target-k8s-api-version.txt" 2>/dev/null | tr -d '[:space:]')
  echo "TARGET_VERSION: $TARGET"
fi

for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" | sort); do
  mod_dir=$(dirname "$gomod")
  echo "CHECK $mod_dir/go.mod"

  while IFS= read -r line; do
    mod=$(echo "$line" | awk '{print $1}')
    ver=$(echo "$line" | awk '{print $2}')
    [[ -z "$mod" || -z "$ver" ]] && continue

    if [[ -n "$TARGET" && "$ver" != *"$TARGET"* ]]; then
      echo "  MISMATCH: $mod $ver (expected *$TARGET*)"
      details+=("$mod_dir: $mod at $ver, expected $TARGET")
      ((NEW_ISSUES++)) || true
    fi
  done < <(grep 'k8s.io/' "$gomod" | grep -v '^\s*//' | grep -v 'replace' | \
            grep -E '^\s' | awk '{print $1, $2}')

  if [[ -d "$mod_dir/vendor" ]]; then
    verify_out=$(cd "$mod_dir" && go mod verify 2>&1) || true
    if echo "$verify_out" | grep -q "FAIL\|modified"; then
      echo "  VENDOR-DRIFT: $mod_dir"
      details+=("$mod_dir: vendor drift detected by go mod verify")
      ((NEW_ISSUES++)) || true
    fi
  fi
done

finish_gate "$NEW_ISSUES" "$NEW_ISSUES version inconsistencies" "${details[@]}"
