#!/bin/bash
# Gate companion: version-consistency — check k8s.io/* versions match target.
# Usage: bash version-consistency.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()

TARGET=""
if [[ -f "$REPO/.rebase-tmp/target-k8s-api-version.txt" ]]; then
  TARGET=$(tr -d '[:space:]' < "$REPO/.rebase-tmp/target-k8s-api-version.txt")
  echo "TARGET_VERSION: $TARGET"
  details+=("TARGET_VERSION: $TARGET")
else
  echo "NO_TARGET: target-k8s-api-version.txt absent, version comparison skipped"
  details+=("NO_TARGET: target-k8s-api-version.txt absent — version comparison skipped")
  inc NEW_ISSUES
fi

for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" | sort); do
  mod_dir=$(dirname "$gomod")
  echo "CHECK $mod_dir/go.mod"
  details+=("CHECK $mod_dir/go.mod")

  while read -r mod ver; do
    [[ -z "$mod" || -z "$ver" ]] && continue

    if [[ -n "$TARGET" && "$ver" != "$TARGET" ]]; then
      details+=("MISMATCH: $mod_dir: $mod at $ver, expected $TARGET")
      inc NEW_ISSUES
    fi
  done < <(grep 'k8s.io/' "$gomod" | grep -v '^\s*//' | grep -v 'replace' | grep -v '=>' | \
            grep -E '^\s' | grep -v 'sigs\.k8s\.io/' | \
            grep -vE 'k8s\.io/(klog|utils|kube-openapi|kubernetes|gengo)\b' | \
            awk '{print $1, $2}')

  if [[ -d "$mod_dir/vendor" ]]; then
    verify_out=$(cd "$mod_dir" && go mod verify 2>&1) || true
    if [[ "$verify_out" =~ FAIL|modified ]]; then
      echo "  VENDOR-DRIFT: $mod_dir"
      details+=("VENDOR-DRIFT: $mod_dir: vendor drift detected by go mod verify")
      inc NEW_ISSUES
    fi
  fi
done

# If K8S_VERSION in test/scripts/install-kind.sh was bumped by this branch,
# verify that KIND_URL was also updated. Pre-built kindest/node images only
# exist for the kind version that shipped with that k8s release; keeping an
# old kind with a new K8S_VERSION breaks every 'kind create cluster' call.
if [[ -n "$BASE" ]] && [[ -f test/scripts/install-kind.sh ]]; then
  _base_k8s=$(git show "$BASE":test/scripts/install-kind.sh 2>/dev/null | grep '^K8S_VERSION=' | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
  _head_k8s=$(grep '^K8S_VERSION=' test/scripts/install-kind.sh 2>/dev/null | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
  _base_kind=$(git show "$BASE":test/scripts/install-kind.sh 2>/dev/null | grep 'KIND_URL=' | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
  _head_kind=$(grep 'KIND_URL=' test/scripts/install-kind.sh 2>/dev/null | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
  if [[ -n "$_base_k8s" && -n "$_head_k8s" && "$_base_k8s" != "$_head_k8s" ]]; then
    details+=("K8S_VERSION: $BASE=$_base_k8s HEAD=$_head_k8s KIND_URL: $BASE=$_base_kind HEAD=$_head_kind")
    if [[ "$_base_kind" == "$_head_kind" ]]; then
      echo "  NEW MISMATCH: K8S_VERSION bumped $_base_k8s→$_head_k8s but KIND_URL unchanged at $_head_kind"
      echo "    kindest/node images only exist for kind versions paired with that k8s release; update KIND_URL"
      details+=("MISMATCH: K8S_VERSION bumped but KIND_URL unchanged — kind create cluster will fail for $_head_k8s")
      inc NEW_ISSUES
    fi
  fi
fi

finish_evidence "$NEW_ISSUES version inconsistencies" "${details[@]}"
