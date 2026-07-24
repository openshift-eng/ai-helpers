#!/bin/bash
# k8s-rebase-autofix.sh — Apply known fix patterns after a k8s rebase
#
# Usage: k8s-rebase-autofix.sh (no arguments — run from repo root)
#
# Runs the verification block as a diagnostic, applies deterministic
# fixes for every non-zero check, then re-verifies. Outputs PASS/FAIL.
#
# Exit codes: 0 = all checks pass (RESULT: PASS)
#             1 = some checks remain (RESULT: FAIL with details)
#
# Fix function scope:
#   Generic (any Go+k8s repo): fix_xexp, fix_reflect_ptr, fix_klog_v2, fix_fieldsv1,
#     fix_eventf, fix_addtoscheme, fix_imports, fix_bounding_dirs,
#     fix_mocks, fix_go_version, fix_lint_version, fix_version_refs,
#     fix_docs_version, fix_crd_int64_validation, fix_crd_name_validation
#   Ecosystem (network-policy-api): fix_conformance_renames,
#     fix_banp_egresspeer, fix_obsgen, fix_network_policy_api_crds
#   Ecosystem (KIND e2e): fix_kind_image, fix_kind_version,
#     fix_relaxed_service_name_validation, fix_kubeadm_v1beta4
#   Ecosystem (client-go features): fix_feature_gates
#   Repo-specific (ovnk): fix_kubevirt_version, fix_metallb_version

set -uo pipefail

AI_TRAILER="Assisted-by: Claude Code <noreply@anthropic.com>"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
cd "$REPO_ROOT" || exit 1

# Guard: refuse to run on master/main — autofix must run on the rebase branch.
_current_branch=$(git branch --show-current 2>/dev/null || true)
if [[ "$_current_branch" == "master" || "$_current_branch" == "main" ]]; then
  echo "ERROR: Autofix is running on '$_current_branch', not the rebase branch."
  if [[ -f "$REPO_ROOT/.rebase-tmp/branch-name" ]]; then
    echo "The rebase branch is: $(cat "$REPO_ROOT/.rebase-tmp/branch-name")"
    echo "Run: git checkout $(cat "$REPO_ROOT/.rebase-tmp/branch-name")"
  fi
  exit 1
fi

# Format commit messages per project convention.
_detect_commit_style() {
  [[ -n "${_COMMIT_STYLE:-}" ]] && return
  for _contrib in "$REPO_ROOT/docs/governance/CONTRIBUTING.md" "$REPO_ROOT/CONTRIBUTING.md"; do
    if [[ -f "$_contrib" ]] && grep -qi 'prefixed with\|prefix.*component\|subcomponent:' "$_contrib" 2>/dev/null; then
      _COMMIT_STYLE="prefix"
      return
    fi
  done
  _COMMIT_STYLE="plain"
}
format_msg() {
  _detect_commit_style
  local cat="$1" desc="$2"
  if [[ "$_COMMIT_STYLE" == "prefix" ]]; then
    desc="$(echo "${desc:0:1}" | tr '[:upper:]' '[:lower:]')${desc:1}"
    echo "${cat}: ${desc}"
  else
    echo "$desc"
  fi
}
export GOWORK=off
REBASE_TMP="$REPO_ROOT/.rebase-tmp"
mkdir -p "$REBASE_TMP"
grep -qF '.rebase-tmp' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.rebase-tmp/' >> "$REPO_ROOT/.git/info/exclude"
grep -qF '.gitconfig' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.gitconfig' >> "$REPO_ROOT/.git/info/exclude"

# Find primary go.mod with k8s.io deps
PRIMARY_GOMOD=""
for gm in go-controller/go.mod go.mod; do
  [[ -f "$gm" ]] && grep -q "k8s.io/" "$gm" && PRIMARY_GOMOD="$gm" && break
done
[[ -z "$PRIMARY_GOMOD" ]] && PRIMARY_GOMOD=$(find . -name "go.mod" -not -path "*/vendor/*" -exec grep -l "k8s.io/" {} \; | head -1)
MODULE_ROOT="."
[[ -n "$PRIMARY_GOMOD" ]] && MODULE_ROOT=$(dirname "$PRIMARY_GOMOD")
K8S_MINOR=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//' || true)
K8S_MAJOR_MINOR="1.${K8S_MINOR:-??}"

# Auto-containerize if local Go is too old for the repo's go.mod
REQUIRED_GO=""
[[ -n "$PRIMARY_GOMOD" ]] && REQUIRED_GO=$(grep "^go " "$PRIMARY_GOMOD" | awk '{print $2}')
CURRENT_GO=$(go env GOVERSION 2>/dev/null | sed 's/go//' || echo "0.0")
if [[ -n "$REQUIRED_GO" ]] && [[ "${K8S_REBASE_IN_CONTAINER:-}" != "1" ]]; then
  REQ_MINOR=$(echo "$REQUIRED_GO" | cut -d. -f2)
  CUR_MINOR=$(echo "$CURRENT_GO" | cut -d. -f2)
  if [[ "$CUR_MINOR" -lt "$REQ_MINOR" ]] 2>/dev/null; then
    CONTAINER_RT=""
    command -v podman &>/dev/null && CONTAINER_RT=podman
    [[ -z "$CONTAINER_RT" ]] && command -v docker &>/dev/null && CONTAINER_RT=docker
    if [[ -n "$CONTAINER_RT" ]]; then
      GO_IMAGE="docker.io/library/golang:${REQUIRED_GO}"
      echo ":: Go $CURRENT_GO < $REQUIRED_GO — re-running autofix inside $GO_IMAGE"
      SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
      USERNS_FLAG=""
      [[ "$CONTAINER_RT" == "podman" ]] && USERNS_FLAG="--userns=keep-id"
      exec $CONTAINER_RT run --rm \
        --security-opt label=disable \
        $USERNS_FLAG \
        -v "$REPO_ROOT:$REPO_ROOT" \
        -v "$(dirname "$SCRIPT_PATH"):$(dirname "$SCRIPT_PATH"):ro" \
        -w "$REPO_ROOT" \
        -e GIT_AUTHOR_NAME="$(git config user.name)" \
        -e GIT_AUTHOR_EMAIL="$(git config user.email)" \
        -e GIT_COMMITTER_NAME="$(git config user.name)" \
        -e GIT_COMMITTER_EMAIL="$(git config user.email)" \
        -e K8S_REBASE_IN_CONTAINER=1 \
        "$GO_IMAGE" \
        bash "$SCRIPT_PATH"
    else
      echo ":: WARNING: Go $CURRENT_GO < $REQUIRED_GO and no container runtime — go vet/goimports skipped. Install Go $REQUIRED_GO+ or podman/docker."
    fi
  fi
fi

# Container setup: git safe.directory for mounted volumes.
# Use env vars instead of git config --global which writes a .gitconfig
# file that could end up committed to the repo.
if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=safe.directory
  export GIT_CONFIG_VALUE_0="$REPO_ROOT"
  # Install jq if missing (needed by verify-third-party-licenses)
  if ! command -v jq &>/dev/null; then
    curl -sL https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 -o /tmp/jq 2>/dev/null \
      && echo "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5  /tmp/jq" | sha256sum -c --quiet 2>/dev/null \
      && chmod +x /tmp/jq && export PATH="/tmp:$PATH"
  fi
fi

# ── Problematic feature gates (extend for future releases) ────────
# Curated: only gates that change fake-clientset wire protocol or API behavior.
# Each entry: parent gate → space-separated dependents (empty if none).
# Gates are only applied if they exist in the vendored k8s.io code.
# Adding a gate for k8s 1.37+: one line here, everything else automatic.
declare -A GATE_DEPS
GATE_DEPS[WatchListClient]=""
# k8s 1.37+: add new entries like:
# GATE_DEPS[NewGate]="Dep1 Dep2 Dep3"

# ── Verification block ─────────────────────────────────────────────
# Single source of truth — used for both diagnostic and final check.
# Generic checks work for any k8s rebase. Version-specific checks
# return 0 when their target files don't exist (safe for future bumps).

run_checks() {
  local F=0
  r() { echo "$1: $2"; [ "$2" != "0" ] && F=$((F+1)); }
  # Only check conformance renames if conformance module uses v0.2.0+
  local _conf_npa_minor=0
  local _conf_gomod=$(find . -name "go.mod" -path "*/conformance/*" -not -path "*/vendor/*" | head -1)
  [[ -n "$_conf_gomod" ]] && _conf_npa_minor=$(grep "network-policy-api " "$_conf_gomod" 2>/dev/null | awk '{print $2}' | cut -d. -f2)
  if (( _conf_npa_minor >= 2 )) 2>/dev/null; then
    r "Conformance old names" "$(grep -w 'SupportAdminNetworkPolicy' test/conformance/network_policy_v2_test.go 2>/dev/null | wc -l)"
  else
    r "Conformance old names" "0"
  fi
  local _factory=$(find . -name "factory.go" -path "*/factory/*" -not -path "*/vendor/*" | head -1)
  r "AddToScheme in factory" "$(grep 'anpapi.AddToScheme' "$_factory" 2>/dev/null | wc -l)"
  # Only check conformance AddToScheme if conformance module uses v0.2.0+
  if (( _conf_npa_minor >= 2 )) 2>/dev/null; then
    r "AddToScheme in conformance" "$(grep 'AddToScheme' test/conformance/network_policy_v2_test.go 2>/dev/null | wc -l)"
  else
    r "AddToScheme in conformance" "0"
  fi
  # Only flag shared EgressPeer in BANP test if the split type exists in vendor
  if grep -rq "BaselineAdminNetworkPolicyEgressPeer" "$MODULE_ROOT/vendor/sigs.k8s.io/network-policy-api/" 2>/dev/null; then
    local _banp_test=$(find . -name "baseline_admin_network_policy_test.go" -not -path "*/vendor/*" | head -1)
    r "BANP wrong EgressPeer" "$(grep 'AdminNetworkPolicyEgressPeer' "$_banp_test" 2>/dev/null | grep -vc Baseline)"
  else
    r "BANP wrong EgressPeer" "0"
  fi
  # Gate checks — driven by GATE_DEPS map. Only checks gates that
  # exist in the vendored k8s code (safe across k8s versions).
  local _active_gates="" _all_gate_names=""
  for _p in "${!GATE_DEPS[@]}"; do
    if grep -rq "\"$_p\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null; then
      _active_gates="$_active_gates $_p"
      _all_gate_names="$_all_gate_names $_p"
      for _d in ${GATE_DEPS[$_p]}; do
        grep -rq "\"$_d\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null && _all_gate_names="$_all_gate_names $_d"
      done
    fi
  done
  local _gmiss=0
  local _test_go_sh
  _test_go_sh=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" 2>/dev/null | head -1)
  if [[ -n "$_test_go_sh" ]]; then
    for _g in $_all_gate_names; do
      grep -q "KUBE_FEATURE_$_g\|\"$_g\"" "$_test_go_sh" 2>/dev/null || _gmiss=$((_gmiss+1))
    done
  fi
  r "Gates in test-go.sh" "$_gmiss"
  # Env var files: check ALL gates (parents + deps).
  # Match on os.Setenv/t.Setenv calls, not just KUBE_FEATURE_ (avoids comments).
  local _genv=0
  for _f in $(grep -rl 'os\.Setenv.*KUBE_FEATURE\|t\.Setenv.*KUBE_FEATURE' --include='*_test.go' --include='*_suite_test.go' "$MODULE_ROOT"/ 2>/dev/null | grep -v vendor); do
    for _g in $_all_gate_names; do
      grep -q "$_g" "$_f" || _genv=$((_genv+1))
    done
  done
  r "Gates in env var files" "$_genv"
  # SetFromMap files: check ALL gates (parents + deps) that exist in vendor.
  # SetFromMap validates parent-dep consistency and rejects unrecognized gates.
  local _sfm_gates="$_active_gates"
  for _p in "${!GATE_DEPS[@]}"; do
    grep -rq "\"$_p\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null || continue
    for _d in ${GATE_DEPS[$_p]}; do
      grep -rq "\"$_d\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null && _sfm_gates="$_sfm_gates $_d"
    done
  done
  local _gsfm=0
  for _f in $(grep -rl 'SetFromMap' --include='*_test.go' --include='*_suite_test.go' "$MODULE_ROOT"/ 2>/dev/null | grep -v vendor); do
    for _g in $_sfm_gates; do
      grep -q "\"$_g\"" "$_f" || _gsfm=$((_gsfm+1))
    done
  done
  r "Gates in SetFromMap files" "$_gsfm"
  # Check ObservedGeneration completeness: need at least 5 references
  # (2 assignments + 1 comparison + 2 propagations). Fewer means partial fix.
  local _obsgen_file
  _obsgen_file=$(find . -name "status.go" -path "*/admin_network_policy/*" -not -path "*/vendor/*" | head -1)
  local _obsgen_count=0
  [[ -f "$_obsgen_file" ]] && _obsgen_count=$(grep -c 'ObservedGeneration' "$_obsgen_file" 2>/dev/null || true)
  if [[ -f "$_obsgen_file" ]] && [[ "$_obsgen_count" -gt 0 ]] && [[ "$_obsgen_count" -lt 5 ]]; then
    r "ObsGen incomplete" "1"
  else
    r "ObsGen missing" "$(grep -L 'WithObservedGeneration\|ObservedGeneration' "$_obsgen_file" 2>/dev/null | wc -l)"
  fi
  r "x/exp imports" "$(grep -rn 'golang.org/x/exp' --include='*.go' . | grep -v vendor | wc -l)"
  r "reflect.Ptr" "$(grep -rn 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor | wc -l)"
  r "FieldsV1.Raw" "$(grep -rn 'FieldsV1\.Raw\b\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor | wc -l)"
  r "Bare Eventf" "$(grep -rn 'Eventf(.*\.Error())' --include='*.go' . | grep -v vendor | grep -v '%[svdqxXoOfFeEgGtTp]' | wc -l)"
  local NEW OLD
  NEW=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')
  if [[ -n "$NEW" ]]; then
    OLD=$((NEW-1))
    r "Stale docs ver" "$(grep "| *1\.${OLD} *|" docs/features/requirements.md 2>/dev/null | wc -l)"
  else
    r "Stale docs ver" "0"
  fi
  # CRD checks: verify int64 format and metadata.name validations
  # Check specifically for format: int32 preceding maximum: 4294967295
  # (can't just check for absence of format: int64 — unrelated fields may have it)
  local _crd_int64_miss=0
  for _crd in $(find . -path "*/helm/*/crds/*.yaml" -not -path "*/vendor/*" 2>/dev/null); do
    if awk '/format: int32/{p=1;next} /maximum: 4294967295/{if(p){found=1;exit}} {p=0} END{exit !found}' "$_crd" 2>/dev/null; then
      _crd_int64_miss=$((_crd_int64_miss+1))
    fi
  done
  r "CRD format:int32 before uint32 max" "$_crd_int64_miss"
  local _crd_name_miss=0
  local _base=""
  for _c in master main; do git rev-parse --verify "$_c" &>/dev/null && _base="$_c" && break; done
  if [[ -n "$_base" ]]; then
    for _crd in $(find . -path "*/helm/*/crds/*.yaml" -not -path "*/vendor/*" 2>/dev/null); do
      local _rel
      _rel=$(git ls-files --full-name "$_crd" 2>/dev/null) || continue
      # Did the base branch have a metadata.name pattern?
      local _had_pattern
      _had_pattern=$(git show "${_base}:${_rel}" 2>/dev/null | awk '
        /^          metadata:/ { m=1; next }
        m && /pattern:/ { print 1; exit }
        m && /^          [a-z]/ { exit }
      ')
      if [[ "$_had_pattern" == "1" ]]; then
        local _has_pattern
        _has_pattern=$(awk '
          /^          metadata:/ { m=1; next }
          m && /pattern:/ { print 1; exit }
          m && /^          [a-z]/ { exit }
        ' "$_crd")
        [[ "$_has_pattern" != "1" ]] && _crd_name_miss=$((_crd_name_miss+1))
      fi
    done
  fi
  r "CRD missing name validation" "$_crd_name_miss"
  # E2e test fixes: check if known CI-blocking test patterns exist
  # without their corresponding fix. Each entry is: file, old pattern
  # (the broken code), fix marker (the new code). If old exists but
  # fix doesn't, the test will fail in CI.
  local _e2e_miss=0
  if [[ -f "test/e2e/kubevirt.go" ]]; then
    if grep -q "virtualMachineAddressesFromStatus" "test/e2e/kubevirt.go" && \
       ! grep -q "virtLauncherNetworkStatusIPs" "test/e2e/kubevirt.go"; then
      _e2e_miss=$((_e2e_miss+1))
    fi
  fi
  r "E2e test fixes missing" "$_e2e_miss"
  r "Uncommitted" "$(git status --short | grep -v '^[?]' | wc -l)"
  echo "---"
  [ "$F" -eq 0 ] && echo "RESULT: PASS" || echo "RESULT: FAIL ($F checks non-zero)"
  return "$F"
}

# ── Fix functions ──────────────────────────────────────────────────
# Generic fixes (apply to any k8s rebase)

fix_xexp() {
  local files
  files=$(grep -rln 'golang.org/x/exp/' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing x/exp imports in $(echo "$files" | wc -l) files"
  for f in $files; do
    # In-place replacement — always produces compilable code even if
    # goimports fails to install. Import ends up in the wrong group
    # (third-party instead of stdlib) but goimports/gci fix that.
    sed -i 's|"golang.org/x/exp/maps"|"maps"|g' "$f"
    sed -i 's|"golang.org/x/exp/slices"|"slices"|g' "$f"
    sed -i 's|"golang.org/x/exp/constraints"|"cmp"|g' "$f"
    # Replace API usage
    sed -i 's/constraints\.Ordered/cmp.Ordered/g' "$f"
    # maps.Keys/Values now return iterators — wrap with slices.Collect
    # Protect already-wrapped instances with placeholders so both Keys
    # and Values on the same line are handled independently.
    sed -i 's/slices\.Collect(maps\.Keys(/\x00SCMK(/g' "$f"
    sed -i 's/slices\.Collect(maps\.Values(/\x00SCMV(/g' "$f"
    sed -i 's/\bmaps\.Keys(\([^)]*\))/slices.Collect(maps.Keys(\1))/g' "$f"
    sed -i 's/\bmaps\.Values(\([^)]*\))/slices.Collect(maps.Values(\1))/g' "$f"
    sed -i 's/\x00SCMK(/slices.Collect(maps.Keys(/g' "$f"
    sed -i 's/\x00SCMV(/slices.Collect(maps.Values(/g' "$f"
    # maps.Clear → builtin clear
    sed -i 's/\bmaps\.Clear(\([^)]*\))/clear(\1)/g' "$f"
    # Import grouping (maps/slices/cmp in stdlib section) handled by goimports below
  done
  # Remove x/exp from go.mod/vendor — needs Go toolchain
  for gomod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -exec grep -l 'golang.org/x/exp' {} \; | xargs -I{} dirname {}); do
    echo ":: Running go mod tidy in $gomod_dir"
    (cd "$gomod_dir" && go mod tidy 2>/dev/null && [[ -d vendor ]] && go mod vendor 2>/dev/null) || true
  done
}

fix_klog_v2() {
  local files
  files=$(grep -rln '"k8s.io/klog"' --include='*.go' . | grep -v vendor | grep -v '/v2')
  [[ -z "$files" ]] && return 0
  echo ":: Fixing klog v1 → v2 imports in $(echo "$files" | wc -l) files"
  for f in $files; do
    sed -i 's|"k8s.io/klog"|"k8s.io/klog/v2"|g' "$f"
  done
  if grep -q 'k8s.io/klog ' "$PRIMARY_GOMOD" 2>/dev/null; then
    echo ":: Running go mod tidy to remove stale klog v1 dependency"
    (cd "$(dirname "$PRIMARY_GOMOD")" && GOWORK=off go mod tidy 2>/dev/null) || true
  fi
}

fix_reflect_ptr() {
  local files
  files=$(grep -rln 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing reflect.Ptr → reflect.Pointer in $(echo "$files" | wc -l) files"
  for f in $files; do
    sed -i 's/reflect\.Ptr\b/reflect.Pointer/g' "$f"
  done
}

fix_fieldsv1() {
  local files
  files=$(grep -rln 'FieldsV1\.Raw\b\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing FieldsV1.Raw in $(echo "$files" | wc -l) files"
  for f in $files; do
    # Read access: .FieldsV1.Raw → .FieldsV1.GetRawBytes()
    # Skip lines where .Raw is on the left side of an assignment
    sed -i '/\.FieldsV1\.Raw\s*=/!s/\.FieldsV1\.Raw\b/.FieldsV1.GetRawBytes()/g' "$f"
    # Construction: &metav1.FieldsV1{Raw: []byte(`...`)} → metav1.NewFieldsV1(`...`)
    sed -i 's/&metav1\.FieldsV1{Raw: \[\]byte(\(`[^`]*`\))}/metav1.NewFieldsV1(\1)/g' "$f"
  done
}

fix_eventf() {
  local files
  files=$(grep -rln 'Eventf(.*\.Error())' --include='*.go' . | grep -v vendor | while read f; do
    grep 'Eventf(.*\.Error())' "$f" | grep -qv '%[svdqxXoOfFeEgGtTp]' && echo "$f"
  done)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing bare Eventf format strings"
  for f in $files; do
    # Only fix simple case: .Error() is the format string (3 commas before it).
    # Complex case (4+ commas = extra args before .Error()) needs agent judgment.
    while IFS= read -r match; do
      local lineno content commas
      lineno=$(echo "$match" | cut -d: -f1)
      content=$(echo "$match" | cut -d: -f2-)
      commas=$(echo "$content" | sed 's/\.Error().*//' | tr -cd ',' | wc -c)
      if [[ "$commas" -le 3 ]]; then
        sed -i "${lineno}s/,\( *\)\([a-zA-Z_][a-zA-Z_0-9.]*\)\.Error())/,\1\"%v\", \2)/" "$f"
      else
        echo ":: WARNING: Complex Eventf at $f:$lineno (needs manual fix — extra args before .Error())"
      fi
    done < <(grep -n 'Eventf(.*\.Error())' "$f" | grep -v '%[svdqxXoOfFeEgGtTp]')
  done
}

fix_docs_version() {
  local NEW OLD
  NEW=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')
  [[ -z "$NEW" ]] && return 0
  OLD=$((NEW-1))
  local file="docs/features/requirements.md"
  [[ -f "$file" ]] || return 0
  if grep -q "| *1\.${OLD} *|" "$file"; then
    echo ":: Fixing stale docs version 1.${OLD} → 1.${NEW}"
    sed -i "s/| *1\.${OLD} *|/| 1.${NEW} |/g" "$file"
  fi
}

fix_version_refs() {
  # Update stale K8S version references in CI, scripts, and docs.
  # Defense-in-depth for Phase 3 which may fail in some container setups.
  local NEW OLD
  NEW=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')
  [[ -z "$NEW" ]] && return 0
  OLD=$((NEW-1))
  local changed=0
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    # Skip K8S_VERSION and kindest/node lines — fix_kind_image owns
    # those and sets them based on actual KIND image availability.
    sed -i -E "/K8S_VERSION|kindest\/node/!{s|v1\.${OLD}\.[0-9]+|v1.${NEW}.0|g; s|v1\.${OLD}\b|v1.${NEW}|g}" "$f"
    changed=1
  done < <(grep -rln -E "v1\.${OLD}(\.[0-9]+)?\b" \
    --include="*.yml" --include="*.yaml" --include="*.sh" \
    --include="*.md" --include="Makefile*" --include="Dockerfile*" . \
    | grep -v vendor | grep -v '/\.git/' | grep -v go.mod || true)
  [[ "$changed" -eq 1 ]] && echo ":: Fixed stale v1.${OLD} version references → v1.${NEW}" || true
}

fix_go_version() {
  # Update Go version references in CI, Makefiles, and Dockerfiles.
  # Defense-in-depth for Phase 3's Go version block which may not commit.
  local new_go old_go
  new_go=$(grep "^go " "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}' | grep -oE '[0-9]+\.[0-9]+')
  [[ -z "$new_go" ]] && return 0
  # Detect old Go version from CI files (the version BEFORE the rebase)
  old_go=$(grep -oE 'golang[:-][0-9]+\.[0-9]+' .github/workflows/docker.yml 2>/dev/null | head -1 | sed 's/golang[:-]//')
  [[ -z "$old_go" ]] && old_go=$(grep -roE 'GO_VERSION \?= [0-9]+\.[0-9]+' --include="Makefile*" . 2>/dev/null | head -1 | sed 's/.*GO_VERSION ?= //')
  [[ -z "$old_go" ]] && old_go=$(grep -roE 'GO_VERSION: "[0-9]+\.[0-9]+"' --include="*.yml" --include="*.yaml" . 2>/dev/null | grep -v vendor | head -1 | sed 's/.*GO_VERSION: "//;s/"//')
  [[ -z "$old_go" ]] && return 0
  [[ "$old_go" == "$new_go" ]] && return 0
  echo ":: Fixing Go version refs: $old_go → $new_go"
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    sed -i \
      -e "s|golang:${old_go}|golang:${new_go}|g" \
      -e "s|golang-${old_go}|golang-${new_go}|g" \
      -e "s|GO_VERSION ?= ${old_go}|GO_VERSION ?= ${new_go}|g" \
      -e "s|GOLANG_VERSION ?= ${old_go}|GOLANG_VERSION ?= ${new_go}|g" \
      -e "s|go-version: \[${old_go}|go-version: [${new_go}|g" \
      -e "s|go-version: ${old_go}|go-version: ${new_go}|g" \
      -e "s|GO_VERSION: \"${old_go}\"|GO_VERSION: \"${new_go}\"|g" \
      "$f"
  done < <(grep -rlnE "golang[:-]${old_go}|GO_VERSION.{0,5}${old_go}|GOLANG_VERSION.{0,5}${old_go}|go-version:.{0,3}${old_go}" \
    --include="*.yml" --include="*.yaml" --include="Makefile*" --include="Dockerfile*" . \
    | grep -v vendor | grep -v '/\.git/' | grep -v go.mod || true)
}

fix_lint_version() {
  local lint_sh
  lint_sh=$(find . -name "lint.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
  [[ -z "$lint_sh" ]] && return 0
  local LATEST_LINT
  LATEST_LINT=$(curl -sf --retry 2 --connect-timeout 10 "https://api.github.com/repos/golangci/golangci-lint/releases/latest" 2>/dev/null | grep -oE '"tag_name": "v[^"]+"' | sed 's/"tag_name": "//;s/"//' || true)
  local lint_ver test_yml
  lint_ver=$(grep -oE 'VERSION=v[0-9.]+' "$lint_sh" | head -1 | sed 's/VERSION=//')

  # Bump lint version if the current one can't parse the target Go version.
  # golangci-lint binaries are built with a specific Go version and can't
  # parse code targeting a newer Go. Fetch latest to get one built with
  # a recent enough Go.
  local required_go
  required_go=$(grep "^go " "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}' | cut -d. -f2)
  if [[ -n "$lint_ver" ]] && [[ -n "$required_go" ]] && [[ "$required_go" -ge 26 ]] 2>/dev/null; then
    # v2.5.0 was built with Go 1.25, v2.12+ with Go 1.26
    local lint_minor
    lint_minor=$(echo "$lint_ver" | sed 's/v[0-9]*\.//' | cut -d. -f1)
    if [[ "$lint_ver" == v2.* ]] && (( lint_minor < 12 )) 2>/dev/null; then
      if [[ -n "$LATEST_LINT" ]]; then
        echo ":: Bumping golangci-lint: $lint_ver → $LATEST_LINT (Go 1.${required_go} requires newer build)"
        sed -i "s/VERSION=${lint_ver}/VERSION=${LATEST_LINT}/" "$lint_sh"
        lint_ver="$LATEST_LINT"
      else
        echo ":: WARNING: golangci-lint $lint_ver may not support Go 1.${required_go} — could not fetch latest version"
      fi
    fi
  fi

  test_yml=$(find . -name "test.yml" -path "*/.github/workflows/*" | head -1)
  if [[ -n "$test_yml" ]]; then
    local test_ver
    test_ver=$(grep -oE 'version: v[0-9.]+' "$test_yml" | head -1 | sed 's/version: //')
    if [[ -n "$lint_ver" ]] && [[ -n "$test_ver" ]] && [[ "$lint_ver" != "$test_ver" ]]; then
      echo ":: Syncing lint version: test.yml $test_ver → $lint_ver"
      sed -i "s/version: ${test_ver}/version: ${lint_ver}/g" "$test_yml"
    fi
  fi
  # Fix golangci-lint v1 + newer Go incompatibility.
  # v1 is EOL — the last release was built with Go 1.24 which
  # can't parse Go 1.26+ syntax. The container image fails, but
  # go install builds from source with the local Go and works.
  # Replace the Makefile's no-op else branch with go install,
  # AND bump GOLANGCI_LINT_VERSION from v1 to v2.
  if [[ -n "$lint_ver" ]] && [[ "$lint_ver" == v1.* ]]; then
    required_go=$(grep "^go " "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}' | cut -d. -f2)
    if [[ -n "$required_go" ]] && [[ "$required_go" -ge 26 ]] 2>/dev/null; then
      if grep -q "can only be run within a container" "$REPO_ROOT/Makefile" 2>/dev/null; then
        echo ":: Fixing Makefile lint fallback for Go 1.${required_go} compatibility"
        # Use v2 import path since we're bumping to v2
        if grep -q "GOLANGCI_LINT_VERSION" "$REPO_ROOT/Makefile" 2>/dev/null; then
          sed -i 's|echo "linter can only be run within a container.*|GOFLAGS="" GOLANGCI_LINT_CACHE=/tmp/golangci-lint-cache go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@$(GOLANGCI_LINT_VERSION) 2>/dev/null \&\& GOLANGCI_LINT_CACHE=/tmp/golangci-lint-cache golangci-lint run --verbose --timeout=15m0s|g' "$REPO_ROOT/Makefile"
        else
          sed -i "s|echo \"linter can only be run within a container.*|GOFLAGS=\"\" GOLANGCI_LINT_CACHE=/tmp/golangci-lint-cache go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@${GOLANGCI_LINT_VERSION:-latest} 2>/dev/null \&\& GOLANGCI_LINT_CACHE=/tmp/golangci-lint-cache golangci-lint run --verbose --timeout=15m0s|g" "$REPO_ROOT/Makefile"
        fi
      else
        echo ":: WARNING: lint.sh uses golangci-lint $lint_ver (built with Go <1.26)."
        echo "   The container image can't parse Go 1.${required_go} code."
      fi
      # Bump GOLANGCI_LINT_VERSION in Makefile from v1 to v2
      local latest_v2="${LATEST_LINT:-v2.12.0}"
      if grep -qE "GOLANGCI_LINT_VERSION.*= *v1\." "$REPO_ROOT/Makefile" 2>/dev/null; then
        echo ":: Bumping Makefile GOLANGCI_LINT_VERSION from v1 to ${latest_v2}"
        sed -i -E "s|(GOLANGCI_LINT_VERSION.*= *)v1\.[0-9.]+|\1${latest_v2}|" "$REPO_ROOT/Makefile"
        # Update any existing go install references to use v2 import path
        sed -i 's|golangci/golangci-lint/cmd/golangci-lint|golangci/golangci-lint/v2/cmd/golangci-lint|g' "$REPO_ROOT/Makefile"
      fi
      # Also bump hack/lint.sh if it's still on v1
      if [[ -n "$lint_sh" ]] && grep -qE "VERSION=v1\." "$lint_sh" 2>/dev/null; then
        echo ":: Bumping hack/lint.sh from v1 to ${latest_v2}"
        sed -i -E "s|VERSION=v1\.[0-9.]+|VERSION=${latest_v2}|" "$lint_sh"
        # Update container image tag if present (golangci/golangci-lint:vX)
        sed -i -E "s|golangci/golangci-lint:v1\.[0-9.]+|golangci/golangci-lint:${latest_v2}|" "$lint_sh"
      fi
    fi
  fi

  # Remove v1-only CLI flags that don't exist in v2 (runs regardless
  # of current version — the flag could linger after a manual bump)
  if [[ -n "$lint_sh" ]] && grep -q '\-\-print-resources-usage' "$lint_sh" 2>/dev/null; then
    echo ":: Removing --print-resources-usage (v1-only flag)"
    sed -i 's/ *--print-resources-usage//g' "$lint_sh"
  fi
}

fix_kind_image() {
  local NEW
  NEW=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')
  [[ -z "$NEW" ]] && return 0
  # Find the highest available kindest/node image for this minor version.
  # Try specific tags first (less rate-limit-prone than listing all),
  # fall back to listing API.
  local kind_tag="" go_mod_patch
  go_mod_patch=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+\.[0-9]+' | sed 's/v0\.[0-9]*\.//')
  for _p in $(seq "${go_mod_patch:-2}" -1 0 | head -5); do
    local _try="v1.${NEW}.${_p}"
    if curl -sf -o /dev/null "https://hub.docker.com/v2/repositories/kindest/node/tags/${_try}" 2>/dev/null; then
      kind_tag="$_try"
      break
    fi
  done
  # Fall back to listing API if per-tag checks all failed
  if [[ -z "$kind_tag" ]]; then
    kind_tag=$(curl -sf --retry 2 "https://hub.docker.com/v2/repositories/kindest/node/tags?page_size=100&name=v1.${NEW}" 2>/dev/null \
      | grep -oE "\"name\":\"v1\.${NEW}\.[0-9]+\"" \
      | sed 's/"name":"//;s/"//' \
      | sort -V | tail -1 || true)
  fi
  # Only override K8S_VERSION in repos where it controls the KIND image.
  # K8S_VERSION is overloaded: some repos use it for KIND image selection
  # (kind create cluster --image kindest/node:$K8S_VERSION), others for
  # kubectl download or envtest. The signal: does any non-vendor file
  # contain BOTH K8S_VERSION and kindest/node?
  local uses_k8s_version_for_kind=""
  if grep -rl "K8S_VERSION" --include="*.sh" --include="*.yml" --include="*.yaml" --include="Makefile*" . 2>/dev/null | grep -v vendor | xargs grep -l "kindest/node" 2>/dev/null | grep -q .; then
    uses_k8s_version_for_kind=1
  fi
  if [[ -z "$kind_tag" ]]; then
    local OLD=$((NEW-1))
    local revert_tag="v1.${OLD}.1"
    echo ":: kindest/node:v1.${NEW}.* not available — reverting KIND refs to ${revert_tag}"
    for f in $(grep -rln "kindest/node" \
      --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" . \
      | grep -v vendor); do
      sed -i -E "s|kindest/node:v1\.${NEW}\.[0-9]+|kindest/node:${revert_tag}|g" "$f"
    done
    if [[ -n "$uses_k8s_version_for_kind" ]]; then
      for f in $(grep -rln "K8S_VERSION" \
        --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" . \
        | grep -v vendor); do
        sed -i -E "/K8S_VERSION/s#v1\.${NEW}\.[0-9]+#${revert_tag}#g" "$f"
      done
    fi
  else
    local _changed=0
    for f in $(grep -rln "kindest/node" \
      --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" . \
      | grep -v vendor | grep -v go.mod); do
      sed -i -E "s|kindest/node:v1\.${NEW}\.[0-9]+|kindest/node:${kind_tag}|g" "$f"
      _changed=1
    done
    if [[ -n "$uses_k8s_version_for_kind" ]]; then
      for f in $(grep -rln "K8S_VERSION" \
        --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" . \
        | grep -v vendor | grep -v go.mod); do
        sed -i -E "/K8S_VERSION/s#v1\.${NEW}\.[0-9]+#${kind_tag}#g" "$f"
        _changed=1
      done
    fi
    if [[ "$_changed" -eq 1 ]]; then
      echo ":: Updated kindest/node refs to ${kind_tag}"
      [[ -n "$uses_k8s_version_for_kind" ]] && echo ":: Updated K8S_VERSION refs to ${kind_tag} (KIND cluster repo)"
    fi
  fi
}

fix_kind_version() {
  # Bump the KIND binary to the latest release. Newer KIND versions
  # are needed to create clusters with newer kindest/node images.
  local install_script
  install_script=$(find . -name "install-kind.sh" -not -path "*/vendor/*" | head -1)
  [[ -z "$install_script" ]] && return 0
  local current_ver
  current_ver=$(grep -oE 'kind.sigs.k8s.io/dl/v[0-9.]+' "$install_script" | head -1 | sed 's|kind.sigs.k8s.io/dl/||')
  [[ -z "$current_ver" ]] && return 0
  local latest_ver
  latest_ver=$(curl -sf --retry 2 "https://api.github.com/repos/kubernetes-sigs/kind/releases/latest" 2>/dev/null | grep -oE '"tag_name": "[^"]+"' | sed 's/"tag_name": "//;s/"//' || true)
  [[ -z "$latest_ver" ]] && return 0
  if [[ "$current_ver" != "$latest_ver" ]]; then
    echo ":: Bumping KIND binary: $current_ver → $latest_ver"
    sed -i "s|kind.sigs.k8s.io/dl/${current_ver}|kind.sigs.k8s.io/dl/${latest_ver}|g" "$install_script"
    current_ver="$latest_ver"
  fi
  # Update stale KIND_VERSION= in workflow files to match install-kind.sh
  # (runs regardless — workflows can be stale even when install-kind.sh is current)
  for wf in $(grep -rln 'KIND_VERSION=v' --include="*.yml" --include="*.yaml" . 2>/dev/null | grep -v vendor); do
    local wf_ver
    wf_ver=$(grep -oE 'KIND_VERSION=v[0-9.]+' "$wf" | head -1 | sed 's/KIND_VERSION=//')
    if [[ -n "$wf_ver" ]] && [[ "$wf_ver" != "$current_ver" ]]; then
      sed -i "s|KIND_VERSION=${wf_ver}|KIND_VERSION=${current_ver}|g" "$wf"
      echo ":: Updated KIND_VERSION in $wf: $wf_ver → $current_ver"
    fi
  done
}

fix_metallb_version() {
  local kind_common
  kind_common=$(find . -name "kind-common.sh" -not -path "*/vendor/*" | head -1)
  [[ -z "$kind_common" ]] && return 0
  local current_metallb
  current_metallb=$(grep -oE 'metallb_version=v[0-9.]+' "$kind_common" | head -1 | sed 's/metallb_version=//')
  [[ -z "$current_metallb" ]] && return 0

  local latest_metallb
  # /releases/latest returns Helm chart releases (metallb-chart-*),
  # not code releases. Use /releases and filter for v-prefixed tags.
  latest_metallb=$(curl -sf "https://api.github.com/repos/metallb/metallb/releases?per_page=20" 2>/dev/null | grep -oE '"tag_name": "v[0-9][^"]+"' | head -1 | sed 's/"tag_name": "//;s/"//' || true)
  [[ -z "$latest_metallb" ]] && { echo ":: WARNING: Could not fetch latest MetalLB version (GitHub API may be rate-limited)"; return 0; }

  if [[ "$current_metallb" != "$latest_metallb" ]]; then
    echo ":: Bumping MetalLB: $current_metallb → $latest_metallb"
    sed -i "s|metallb_version=${current_metallb}|metallb_version=${latest_metallb}|" "$kind_common"

    # MetalLB versions ship different FRR images. Add a separate variable
    # so install_metallb replaces the correct source tag.
    local metallb_frr_tag
    metallb_frr_tag=$(curl -sf "https://raw.githubusercontent.com/metallb/metallb/${latest_metallb}/charts/metallb/values.yaml" 2>/dev/null | awk '/repository.*frrouting\/frr/{getline; if(/tag:/) {gsub(/.*tag: */,""); print; exit}}' || true)
    if [[ -n "$metallb_frr_tag" ]]; then
      local metallb_frr_image="quay.io/frrouting/frr:${metallb_frr_tag}"
      if ! grep -q "METALLB_UPSTREAM_FRR_IMAGE" "$kind_common"; then
        sed -i "/^readonly FRR_K8S_UPSTREAM_FRR_IMAGE=/a readonly METALLB_UPSTREAM_FRR_IMAGE=${metallb_frr_image}" "$kind_common"
        echo ":: Added METALLB_UPSTREAM_FRR_IMAGE=${metallb_frr_image}"
      fi
      # Update replace_in_file_or_exit calls inside install_metallb() to use the new var
      # Handles both ${VAR} and ${VAR##*:} patterns
      sed -i '/^install_metallb()/,/^}/s/FRR_K8S_UPSTREAM_FRR_IMAGE/METALLB_UPSTREAM_FRR_IMAGE/g' "$kind_common"
      if sed -n '/^install_metallb()/,/^}/p' "$kind_common" | grep -q 'FRR_K8S_UPSTREAM_FRR_IMAGE'; then
        echo ":: WARNING: install_metallb still references FRR_K8S_UPSTREAM_FRR_IMAGE — manual update needed"
      else
        echo ":: Updated install_metallb to use METALLB_UPSTREAM_FRR_IMAGE"
      fi
    else
      echo ":: WARNING: Could not detect FRR image for MetalLB $latest_metallb"
      echo "   Verify FRR image tags in install_metallb manually."
    fi
  fi
}

fix_kubevirt_version() {
  local kind_common
  kind_common=$(find . -name "kind-common.sh" -not -path "*/vendor/*" | head -1)
  [[ -z "$kind_common" ]] && return 0
  grep -q 'KUBEVIRT_VERSION:-"v[0-9]' "$kind_common" || return 0
  local current current_minor latest_patch
  current=$(grep -oE 'KUBEVIRT_VERSION:-"v[^"]+' "$kind_common" | head -1 | sed 's/.*:-"//')
  # Only bump patches within the same minor — never cross minor boundaries.
  # KubeVirt minors have different k8s compatibility matrices.
  current_minor="${current%.*}"
  latest_patch=$(curl -sf --retry 2 --connect-timeout 10 \
    "https://api.github.com/repos/kubevirt/kubevirt/releases?per_page=30" 2>/dev/null \
    | grep -oE '"tag_name": "v[0-9][^"]*"' | sed 's/"tag_name": "//;s/"//g' \
    | grep "^${current_minor//./\\.}\." \
    | grep -v '\-\(alpha\|beta\|rc\)' \
    | sort -V | tail -1 || true)
  if [[ -n "$latest_patch" && "$latest_patch" != "$current" ]]; then
    sed -i "s|KUBEVIRT_VERSION:-\"${current}\"|KUBEVIRT_VERSION:-\"${latest_patch}\"|" "$kind_common"
    echo ":: Bumped KubeVirt ${current} → ${latest_patch} (latest patch in ${current_minor}.x)"
  fi
}

fix_relaxed_service_name_validation() {
  # Version-aware: k8s >= 1.36 (beta/default-on) removes the explicit
  # gate to prevent "unknown feature gate" errors when it graduates to
  # GA. k8s < 1.36 (alpha/default-off) adds it for upgrade CI.
  local kind_yaml
  kind_yaml=$(find . -name "kind.yaml.j2" -path "*/contrib/*" | head -1)
  [[ -z "$kind_yaml" ]] && return 0

  if [[ "${K8S_MINOR:-0}" -ge 36 ]]; then
    grep -q "RelaxedServiceNameValidation" "$kind_yaml" || return 0
    local gate_count
    gate_count=$(awk '/^featureGates:/{f=1;next} f && /^  [A-Za-z]/{n++} f && /^[^ ]/{f=0} END{print n+0}' "$kind_yaml")
    if [[ "$gate_count" -le 1 ]]; then
      awk '
        /^#/ { buf[++n] = $0; next }
        /^featureGates:/ { n = 0; fg = 1; next }
        { for (i = 1; i <= n; i++) print buf[i]; n = 0 }
        fg && /^  [A-Za-z]/ { next }
        fg && /^$/ { fg = 0; next }
        fg && /^[^ ]/ { fg = 0 }
        { print }
        END { for (i = 1; i <= n; i++) print buf[i] }
      ' "$kind_yaml" > "${kind_yaml}.tmp" && mv "${kind_yaml}.tmp" "$kind_yaml"
      echo ":: Removed RelaxedServiceNameValidation block from kind.yaml.j2 (default-on in k8s >= 1.36)"
    else
      sed -i '/^  RelaxedServiceNameValidation:/d' "$kind_yaml"
      echo ":: Removed RelaxedServiceNameValidation line from kind.yaml.j2 (default-on in k8s >= 1.36)"
    fi
  else
    grep -q "RelaxedServiceNameValidation" "$kind_yaml" && return 0
    awk '/^networking:/ { print "featureGates:"; print "  RelaxedServiceNameValidation: true"; print "" } 1' "$kind_yaml" > "${kind_yaml}.tmp" && { chmod --reference="$kind_yaml" "${kind_yaml}.tmp" 2>/dev/null || true; } && mv "${kind_yaml}.tmp" "$kind_yaml"
    echo ":: Added RelaxedServiceNameValidation to kind.yaml.j2"
  fi
}

fix_kubeadm_v1beta4() {
  # k8s 1.36 silently ignores kubeadm v1beta3 extraArgs map format,
  # causing controller-manager flags (e.g. -service-lb-controller) to
  # not be applied. Migrate kind.yaml.j2 to v1beta4 list format.
  local kind_yaml
  kind_yaml=$(find . -name "kind.yaml.j2" -path "*/contrib/*" | head -1)
  [[ -z "$kind_yaml" ]] && return 0
  grep -q "apiVersion: kubeadm.k8s.io/v1beta4" "$kind_yaml" && return 0
  # Only act if the file has kubeadm extraArgs in map format (not list)
  grep -q 'extraArgs:' "$kind_yaml" || return 0
  # Skip if already in list format (- name: pattern under extraArgs)
  if awk '/[Ee]xtraArgs:$/{ea=1;next} ea && /- name:/{found=1;exit} ea && /^[^ ]/{ea=0} END{exit !found}' "$kind_yaml" 2>/dev/null; then
    return 0
  fi

  echo ":: Migrating kind.yaml.j2 kubeadm config to v1beta4 format"
  awk '
    # Add apiVersion after kind: *Configuration lines (inside kubeadmConfigPatches)
    /kind: (Cluster|Init|Join)Configuration/ && !/apiVersion/ {
      print
      # Preserve indentation: same as current line
      match($0, /^[[:space:]]*/); indent = substr($0, 1, RLENGTH)
      print indent "apiVersion: kubeadm.k8s.io/v1beta4"
      next
    }
    # Track when we enter an extraArgs or kubeletExtraArgs block
    /[Ee]xtraArgs:$/ {
      in_args = 1
      # Record the indentation of the extraArgs key itself
      match($0, /^[[:space:]]*/); args_indent = RLENGTH
      print
      next
    }
    # Inside extraArgs: convert "key": "value" to - name: / value:
    in_args {
      # Check if this line is a child of extraArgs (deeper indentation)
      match($0, /^[[:space:]]*/); cur_indent = RLENGTH
      if (cur_indent <= args_indent) {
        # Left the extraArgs block
        in_args = 0
        print
        next
      }
      # Skip comment lines (preserve them as-is)
      if ($0 ~ /^[[:space:]]*#/) { print; next }
      # Parse "key": "value" — strip quotes and extract key/value
      line = $0; gsub(/^[[:space:]]+/, "", line); gsub(/[[:space:]]+$/, "", line)
      gsub(/"/, "", line)
      n = index(line, ":")
      if (n > 0) {
        key = substr(line, 1, n-1)
        val = substr(line, n+1); gsub(/^[[:space:]]+/, "", val)
        entry_indent = ""
        for (i = 0; i < args_indent + 2; i++) entry_indent = entry_indent " "
        sub_indent = entry_indent "  "
        print entry_indent "- name: \"" key "\""
        print sub_indent "value: \"" val "\""
      } else {
        # Unrecognized format, pass through
        print
      }
      next
    }
    { print }
  ' "$kind_yaml" > "${kind_yaml}.tmp"

  if ! grep -q "v1beta4" "${kind_yaml}.tmp"; then
    echo "  WARNING: kubeadm v1beta4 migration failed — file unchanged"
    rm -f "${kind_yaml}.tmp"
    return 0
  fi

  chmod --reference="$kind_yaml" "${kind_yaml}.tmp" 2>/dev/null || true
  mv "${kind_yaml}.tmp" "$kind_yaml"
  echo ":: Migrated kubeadm extraArgs to v1beta4 list format"
}

fix_crd_int64_validation() {
  # k8s 1.36 rejects CRD integer fields where Maximum > int32 max
  # but format is int32 (the default for uint32 Go types).
  #
  # Two-part fix:
  # 1. Add +kubebuilder:validation:Format=int64 marker to types.go
  #    (ensures future codegen produces correct CRDs)
  # 2. Patch format: int64 directly into the CRD YAML files
  #    (immediate fix without re-running codegen, which would strip
  #    hand-edited metadata blocks from unrelated CRDs)
  local files fixed=0
  files=$(find . -name "*types*.go" -path "*/crd/*" -not -path "*/vendor/*" 2>/dev/null)
  [[ -z "$files" ]] && return 0
  for f in $files; do
    if grep -q "Maximum.*4294967295" "$f" && ! grep -q "Format.*int64\|Format=int64" "$f"; then
      echo ":: Adding Format=int64 kubebuilder marker in $f"
      sed -i '/Maximum.*4294967295/a\\t// +kubebuilder:validation:Format=int64' "$f"
      fixed=1
    fi
  done
  if [[ "$fixed" -eq 1 ]]; then
    # Patch CRD YAML files directly instead of re-running codegen
    # (which strips hand-edited metadata blocks from unrelated CRDs).
    # Handles two cases:
    # - format: int32 exists (Phase 2 codegen ran) → change to int64
    # - no format line (Phase 2 codegen failed) → insert format: int64
    echo ":: Patching CRD YAML files: ensure format: int64 for uint32 fields"
    local helm_crd_dir
    helm_crd_dir=$(find . -path "*/helm/*/crds" -type d -not -path "*/vendor/*" | head -1)
    local output_dir
    output_dir=$(find . -path "*/_output/crds" -type d -not -path "*/vendor/*" | head -1)
    for dir in $helm_crd_dir $output_dir; do
      [[ -n "$dir" && -d "$dir" ]] || continue
      for crd_yaml in "$dir"/*.yaml; do
        [[ -f "$crd_yaml" ]] || continue
        grep -q "maximum: 4294967295" "$crd_yaml" || continue
        # Two cases:
        # 1. "format: int32" before "maximum: 4294967295" → replace with int64
        # 2. No format line before "maximum: 4294967295" → insert int64
        # The awk also buffers "format: int64" lines so it's idempotent —
        # an already-fixed field is recognized and passed through unchanged.
        awk '
          /format: int(32|64)/ { prev=$0; prev_nr=NR; next }
          /maximum: 4294967295/ {
            if (prev_nr==NR-1) {
              sub(/int32/, "int64", prev)
              print prev
            } else {
              if (prev!="") print prev
              match($0, /^[[:space:]]*/);
              printf "%s%s\n", substr($0, 1, RLENGTH), "format: int64"
            }
            print; prev=""; next
          }
          { if (prev!="") print prev; prev=""; print }
          END { if (prev!="") print prev }
        ' "$crd_yaml" > "${crd_yaml}.tmp"
        chmod --reference="$crd_yaml" "${crd_yaml}.tmp" 2>/dev/null || true
        mv "${crd_yaml}.tmp" "$crd_yaml"
        # Verify: no format: int32 should remain before maximum: 4294967295
        if ! awk '/format: int32/{p=1;next} /maximum: 4294967295/{if(p){found=1;exit}} {p=0} END{exit !found}' "$crd_yaml" 2>/dev/null; then
          echo "  Patched $(basename "$crd_yaml")"
        else
          echo "  WARNING: format: int32 still precedes maximum: 4294967295 in $(basename "$crd_yaml")"
        fi
      done
    done
  fi
}

fix_crd_name_validation() {
  # Safety net: k8s-rebase.sh Phase 2 preserves CRD metadata blocks
  # across codegen. This function catches any that slipped through
  # (e.g., agent ran codegen manually, or k8s-rebase.sh was skipped).
  # Uses the base branch as the source of truth for what should exist.
  local helm_crd_dir
  helm_crd_dir=$(find . -path "*/helm/*/crds" -type d -not -path "*/vendor/*" | head -1)
  [[ -z "$helm_crd_dir" ]] && return 0

  local base_branch=""
  for candidate in master main; do
    git rev-parse --verify "$candidate" &>/dev/null && base_branch="$candidate" && break
  done
  [[ -z "$base_branch" ]] && return 0

  for crd_file in "$helm_crd_dir"/*.yaml; do
    [[ -f "$crd_file" ]] || continue
    local rel_path
    rel_path=$(git ls-files --full-name "$crd_file" 2>/dev/null)
    [[ -z "$rel_path" ]] && continue
    local old_file
    old_file=$(git show "${base_branch}:${rel_path}" 2>/dev/null) || continue

    # Compare metadata section line counts — if old has more, hand-edits were lost
    # (|| true prevents pipefail from killing the script on no-match)
    local s_start s_end c_start c_end
    s_start=$(echo "$old_file" | grep -n "^          metadata:" 2>/dev/null | head -1 | cut -d: -f1 || true)
    c_start=$(grep -n "^          metadata:" "$crd_file" 2>/dev/null | head -1 | cut -d: -f1 || true)
    [[ -z "$s_start" || -z "$c_start" ]] && continue
    s_end=$(echo "$old_file" | awk "NR>$s_start && /^          [a-z]/{print NR; exit}")
    c_end=$(awk "NR>$c_start && /^          [a-z]/{print NR; exit}" "$crd_file")
    [[ -z "$s_end" || -z "$c_end" ]] && continue

    local s_lines=$((s_end - s_start)) c_lines=$((c_end - c_start))
    if [[ "$s_lines" -gt "$c_lines" ]]; then
      echo ":: Restoring CRD metadata hand-edits in $(basename "$crd_file")"
      {
        head -n "$((c_start - 1))" "$crd_file"
        echo "$old_file" | sed -n "${s_start},$((s_end - 1))p"
        tail -n "+${c_end}" "$crd_file"
      } > "${crd_file}.tmp"
      chmod --reference="$crd_file" "${crd_file}.tmp" 2>/dev/null || true
      mv "${crd_file}.tmp" "$crd_file"
    fi
  done
}

fix_network_policy_api_crds() {
  # The conformance module may use a different network-policy-api version
  # than go-controller. Do NOT force-bump the conformance module to match —
  # the conformance suite's fixtures must match the API version the controller
  # supports. If go-controller uses v0.2.0 (Go types still include
  # AdminNetworkPolicy v1alpha1), the conformance module may use a pre-release
  # that has v1alpha1 fixtures. Bumping to v0.2.0 would bring v1alpha2
  # ClusterNetworkPolicy fixtures that the controller can't enforce.
  #
  # Only add ClusterNetworkPolicy CRD if the conformance module itself
  # uses v0.2.0+ (meaning the conformance tests expect it).
  local conf_gomod
  conf_gomod=$(find . -name "go.mod" -path "*/conformance/*" -not -path "*/vendor/*" | head -1)
  [[ -z "$conf_gomod" ]] && return 0

  local conf_npa
  conf_npa=$(grep "network-policy-api " "$conf_gomod" 2>/dev/null | awk '{print $2}' || true)
  [[ -z "$conf_npa" ]] && return 0

  # Only add CRD if conformance module uses v0.2.0+ (not a pre-release)
  local conf_minor
  conf_minor=$(echo "$conf_npa" | cut -d. -f2)
  # Pre-release versions like v0.1.9-0.20260225... have minor=1
  (( conf_minor < 2 )) 2>/dev/null && return 0

  local kind_helm
  kind_helm=$(find . -name "kind-helm.sh" -not -path "*/vendor/*" | head -1)
  [[ -z "$kind_helm" ]] && kind_helm=$(find . -name "kind.sh" -not -path "*/vendor/*" -not -type l | head -1)
  if [[ -n "$kind_helm" ]] && ! grep -q "clusternetworkpolicies" "$kind_helm"; then
    local anp_line
    anp_line=$(grep -n "adminnetworkpolicies.yaml" "$kind_helm" | head -1 | cut -d: -f1 || true)
    if [[ -n "$anp_line" ]]; then
      echo ":: Adding ClusterNetworkPolicy CRD for conformance (${conf_npa})"
      sed -i "${anp_line}a\\  run_kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/network-policy-api/${conf_npa}/config/crd/experimental/policy.networking.k8s.io_clusternetworkpolicies.yaml" "$kind_helm"
    fi
  fi
}

# Pattern-based fixes (conditional — only run if pattern found)

fix_addtoscheme() {
  # Replace AddToScheme with Install where vendored source confirms Install exists
  local files
  files=$(grep -rln '\.AddToScheme\b' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  for f in $files; do
    while IFS= read -r line; do
      local pkg_alias
      pkg_alias=$(echo "$line" | sed 's/\.AddToScheme.*//' | grep -oE '[a-zA-Z0-9_]+$')
      [[ -z "$pkg_alias" ]] && continue
      # Find the import path for this alias
      local import_path
      import_path=$(sed -n '/^import/,/^)/{/^[[:space:]]*'"$pkg_alias"' "/{ s/.*"\(.*\)".*/\1/; p; }}' "$f" | head -1)
      [[ -z "$import_path" ]] && continue
      # Check if Install exists in the vendored source
      local vendor_dir
      vendor_dir=$(find . -path "*/vendor/${import_path}" -type d | head -1)
      [[ -z "$vendor_dir" ]] && continue
      # Only rename if AddToScheme is actually REMOVED (not just deprecated).
      # If AddToScheme still exists as a func or var, it compiles fine — skip.
      if grep -rq 'func AddToScheme\b\|AddToScheme\s*=' "$vendor_dir" 2>/dev/null; then
        continue
      fi
      if grep -rq 'func Install\b' "$vendor_dir" 2>/dev/null; then
        echo ":: Fixing ${pkg_alias}.AddToScheme → Install in $f"
        sed -i "s/${pkg_alias}\.AddToScheme/${pkg_alias}.Install/g" "$f"
      fi
    done < <(grep '\.AddToScheme\b' "$f")
  done
}

fix_conformance_renames() {
  # SupportAdminNetworkPolicy* → SupportClusterNetworkPolicy* (all variants)
  # SupportBaselineAdminNetworkPolicy* → SupportClusterNetworkPolicy* (merged)
  # Only rename if the conformance module uses v0.2.0+ where these symbols
  # were renamed. Pre-release versions (v0.1.9-0.2026...) still use the old names.
  local conf_gomod
  conf_gomod=$(find . -name "go.mod" -path "*/conformance/*" -not -path "*/vendor/*" | head -1)
  # No conformance module → nothing to rename
  [[ -z "$conf_gomod" ]] && return 0
  local conf_npa_minor
  conf_npa_minor=$(grep "network-policy-api " "$conf_gomod" 2>/dev/null | awk '{print $2}' | cut -d. -f2)
  # Pre-release versions (minor < 2) still use the old symbol names
  (( conf_npa_minor < 2 )) 2>/dev/null && return 0
  local files
  files=$(grep -rln 'SupportAdminNetworkPolicy\|SupportBaselineAdminNetworkPolicy' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing conformance suite renames"
  for f in $files; do
    # Replace Baseline variants first (longer prefix), then non-Baseline
    # No \b — must also catch EgressNodePeers, NamedPorts suffixes
    sed -i 's/SupportBaselineAdminNetworkPolicy/SupportClusterNetworkPolicy/g' "$f"
    sed -i 's/SupportAdminNetworkPolicy/SupportClusterNetworkPolicy/g' "$f"
    # ConformanceProfileName type cast → CNPConformanceProfileName
    sed -i 's/ConformanceProfileName(suite\.SupportClusterNetworkPolicy)/CNPConformanceProfileName/g' "$f"
    # Remove duplicate conformance lines after baseline→cluster merge
    awk '!/SupportClusterNetworkPolicy|CNPConformanceProfileName/ || !seen[$0]++' "$f" > "${f}.tmp" && mv "${f}.tmp" "$f"
  done
}

fix_obsgen() {
  # Ensure ObservedGeneration is set on ANP/BANP status conditions.
  # Handles both patterns:
  #   Builder chain: .WithObservedGeneration(anp.Generation)
  #   Struct literal: newCondition.ObservedGeneration = anp.Generation
  local file
  file=$(find . -name "status.go" -path "*/admin_network_policy/*" -not -path "*/vendor/*" | head -1)
  [[ -z "$file" ]] && return 0
  grep -q 'WithObservedGeneration\|\.ObservedGeneration' "$file" && return 0

  echo ":: Fixing ObsGen in $file"
  if grep -q 'Condition()' "$file"; then
    # Builder pattern: insert WithObservedGeneration in chain
    local is_first=true
    while IFS= read -r lineno; do
      local gen_var="anp.Generation"
      $is_first && gen_var="banp.Generation" && is_first=false
      sed -i "${lineno}a\\
\\t\\t\\tWithObservedGeneration(${gen_var})." "$file"
    done < <(grep -n 'WithStatus(newCondition' "$file" | tac | cut -d: -f1)
  else
    # Struct literal pattern: three changes needed for correctness.
    # 1. Set newCondition.ObservedGeneration = X.Generation after fetching
    # 2. Add ObservedGeneration to doesStatusNeedAnUpdate comparison
    # 3. Propagate ObservedGeneration when reusing existingCondition

    # Change 1: insert assignment after object fetch + error check
    for func_pattern in "updateANPZoneStatusCondition" "updateBANPZoneStatusCondition"; do
      local obj_var="anp"
      [[ "$func_pattern" == *BANP* ]] && obj_var="banp"
      local return_line
      return_line=$(awk "
        /func.*${func_pattern}/ { in_func=1 }
        in_func && /${obj_var}, err :=/ { found_fetch=1 }
        in_func && found_fetch && /return err/ { print NR; found_fetch=0; exit }
      " "$file")
      if [[ -n "$return_line" ]]; then
        sed -i "$((return_line + 1))a\\
\\tnewCondition.ObservedGeneration = ${obj_var}.Generation" "$file"
      fi
    done

    # Change 2: add ObservedGeneration to the equality check in doesStatusNeedAnUpdate
    if grep -q "existingCondition.Message == newCondition.Message {" "$file" &&
       ! grep -q "existingCondition.ObservedGeneration == newCondition.ObservedGeneration" "$file"; then
      sed -i 's/existingCondition\.Message == newCondition\.Message {/existingCondition.Message == newCondition.Message \&\&\
\t\texistingCondition.ObservedGeneration == newCondition.ObservedGeneration {/' "$file"
    fi

    # Change 3: propagate ObservedGeneration when copying from existingCondition
    # Insert after each "existingCondition.Message = newCondition.Message" line
    if ! grep -q "existingCondition.ObservedGeneration = newCondition.ObservedGeneration" "$file"; then
      sed -i '/existingCondition\.Message = newCondition\.Message/a\\t\texistingCondition.ObservedGeneration = newCondition.ObservedGeneration' "$file"
    fi
  fi
}

fix_banp_egresspeer() {
  local file
  file=$(find . -name "baseline_admin_network_policy_test.go" -not -path "*/vendor/*" | head -1)
  [[ -z "$file" ]] && return 0
  # Only rename if BaselineAdminNetworkPolicyEgressPeer exists in vendored source.
  # In network-policy-api v0.1.x, the type doesn't exist — BANP uses the
  # shared AdminNetworkPolicyEgressPeer. In v0.2.0+ it was split.
  if ! grep -rq "BaselineAdminNetworkPolicyEgressPeer" "$MODULE_ROOT/vendor/sigs.k8s.io/network-policy-api/" 2>/dev/null; then
    return 0
  fi
  local count
  count=$(grep 'AdminNetworkPolicyEgressPeer' "$file" | grep -vc Baseline)
  [[ "$count" -eq 0 ]] && return 0
  echo ":: Fixing BANP EgressPeer type in $file ($count occurrences)"
  sed -i 's/\bAdminNetworkPolicyEgressPeer\b/BaselineAdminNetworkPolicyEgressPeer/g' "$file"
  sed -i 's/BaselineBaselineAdminNetworkPolicyEgressPeer/BaselineAdminNetworkPolicyEgressPeer/g' "$file"
}

fix_feature_gates() {
  # Iterate GATE_DEPS directly — no external file needed.
  # Only process gates that exist in the vendored k8s code.
  local parents=() all_deps=()
  for gate in "${!GATE_DEPS[@]}"; do
    grep -rq "\"$gate\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null || continue
    parents+=("$gate")
    for dep in ${GATE_DEPS[$gate]}; do
      grep -rq "\"$dep\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null && all_deps+=("$dep")
    done
  done
  [[ ${#parents[@]} -eq 0 ]] && return 0

  local all_gates=("${all_deps[@]}" "${parents[@]}")

  # ── Layer 1: test-go.sh exports ──
  local test_go_sh
  test_go_sh=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
  if [[ -n "$test_go_sh" ]]; then
    for gate in "${all_gates[@]}"; do
      if ! grep -q "KUBE_FEATURE_${gate}" "$test_go_sh"; then
        echo ":: Adding gate $gate to $test_go_sh"
        local insert_after
        insert_after=$(grep -n "KUBE_FEATURE_" "$test_go_sh" | tail -1 | cut -d: -f1 || true)
        if [[ -n "$insert_after" ]]; then
          sed -i "${insert_after}a export KUBE_FEATURE_${gate}=false" "$test_go_sh"
        else
          sed -i "1a export KUBE_FEATURE_${gate}=false" "$test_go_sh"
        fi
      fi
    done
  fi

  # ── Layer 2: os.Setenv / t.Setenv in test files ──
  local env_files
  env_files=$(grep -rl 'os\.Setenv.*KUBE_FEATURE\|t\.Setenv.*KUBE_FEATURE' --include='*_test.go' --include='*_suite_test.go' "$MODULE_ROOT"/ 2>/dev/null | grep -v vendor)
  for tf in $env_files; do
    for gate in "${all_gates[@]}"; do
      [[ -z "$gate" ]] && continue
      if grep -q 'os\.Setenv.*KUBE_FEATURE' "$tf" && ! grep -q "os\.Setenv.*${gate}" "$tf"; then
        local setenv_line
        setenv_line=$(grep -n 'os\.Setenv.*KUBE_FEATURE' "$tf" | head -1 | cut -d: -f1 || true)
        sed -i "${setenv_line}i\\
\\tos.Setenv(\"KUBE_FEATURE_${gate}\", \"false\")" "$tf"
      fi
      if grep -q 't\.Setenv.*KUBE_FEATURE' "$tf" && ! grep -q "t\.Setenv.*${gate}" "$tf"; then
        local tsetenv_line
        tsetenv_line=$(grep -n 't\.Setenv.*KUBE_FEATURE' "$tf" | head -1 | cut -d: -f1 || true)
        sed -i "${tsetenv_line}i\\
\\tt.Setenv(\"KUBE_FEATURE_${gate}\", \"false\")" "$tf"
      fi
    done
  done

  # ── Layer 3: SetFromMap in test files ──
  # Add ALL gates (parents + deps) to SetFromMap. SetFromMap validates
  # parent-dep consistency — disabling a parent without its deps errors.
  # Each gate is checked against vendor to avoid adding removed gates.
  local sfm_gates=()
  for gate in "${parents[@]}"; do
    sfm_gates+=("$gate")
  done
  for dep in "${all_deps[@]}"; do
    grep -rq "\"$dep\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null && sfm_gates+=("$dep")
  done

  local sfm_files
  sfm_files=$(grep -rl 'SetFromMap' --include='*_test.go' --include='*_suite_test.go' "$MODULE_ROOT"/ 2>/dev/null | grep -v vendor)
  for tf in $sfm_files; do
    local missing=false
    for g in "${sfm_gates[@]}"; do
      grep -q "\"$g\"" "$tf" || { missing=true; break; }
    done
    $missing || continue

    echo ":: Adding gates to SetFromMap in $tf"
    for g in "${sfm_gates[@]}"; do
      if ! grep -q "\"$g\"" "$tf"; then
        sed -i "/SetFromMap/s/false}/false, \"${g}\": false}/" "$tf" 2>/dev/null || true
      fi
    done

    # Broaden the unrecognized-gate filter if present (safety net).
    if grep -q 'unrecognized feature gate: WatchListClient' "$tf"; then
      sed -i 's/unrecognized feature gate: WatchListClient/unrecognized feature gate/' "$tf"
    fi

    # Update stale error messages that name a single gate.
    if grep -q 'Failed to disable .* feature gate' "$tf"; then
      sed -i 's/Failed to disable .* feature gate/Failed to disable feature gates/' "$tf"
    fi
  done

  # ── Layer 4: Warn about test packages that may need gates ──
  # Not all fake clientset packages need gates — only those using
  # informers (list/watch). Too many false positives to auto-fix.
  # Only checks suite files; packages without suites (e.g., pod/)
  # are caught by the validate script's dynamic test selection.
  local _missing_gate_list=""
  for suite in $(find "$MODULE_ROOT"/ -name "*_suite_test.go" -not -path "*/vendor/*" 2>/dev/null); do
    local pkg_dir
    pkg_dir=$(dirname "$suite")
    grep -rq "KUBE_FEATURE_\|SetFromMap" "$pkg_dir"/*.go 2>/dev/null && continue
    grep -rq "fake\.NewClientBuilder\|fake\.NewSimpleClientset\|fake\.NewClientset" "$pkg_dir"/*.go 2>/dev/null || continue
    _missing_gate_list+="   $suite\n"
  done
  if [[ -n "$_missing_gate_list" ]]; then
    echo ":: NOTE: These test suites use fake clientsets without gate env vars:"
    echo -e "$_missing_gate_list"
    echo "   If tests hang with informer timeouts, add KUBE_FEATURE_ env vars."
  fi
}

fix_imports() {
  # Two-step import fix:
  # 1. goimports: fixes import grouping (x/exp→stdlib replacements end up in wrong group)
  # 2. gci: orders imports to match the project's golangci-lint config
  #    (goimports only does 2 groups; gci handles the project-specific
  #    multi-group layout like stdlib/external/k8s.io/local)
  # Find all Go files changed since the rebase started (not just unstaged).
  # Import issues may have been committed by earlier steps.
  local merge_base modified
  merge_base=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo "HEAD~10")
  modified=$(git diff --name-only "$merge_base" -- '*.go' | grep -v vendor | grep -v 'zz_generated')
  [[ -z "$modified" ]] && modified=$(git diff --name-only -- '*.go' | grep -v vendor | grep -v 'zz_generated')
  [[ -z "$modified" ]] && return 0

  # Step 1: goimports fixes import grouping
  if ! command -v goimports &>/dev/null; then
    if ! go install golang.org/x/tools/cmd/goimports@latest 2>/dev/null; then
      echo ":: WARNING: goimports install failed — import grouping may be wrong"
    fi
  fi
  if command -v goimports &>/dev/null; then
    echo ":: Running goimports on $(echo "$modified" | wc -l) modified files"
    for f in $modified; do
      [[ -f "$f" ]] && goimports -w "$f"
    done
  fi

  # Step 2: gci fixes import grouping to match project lint config
  if ! command -v gci &>/dev/null; then
    if ! go install github.com/daixiang0/gci@latest 2>/dev/null; then
      echo ":: WARNING: gci install failed — import grouping may not match project lint config"
    fi
  fi
  if command -v gci &>/dev/null; then
    # Read gci sections from project's golangci config
    local gci_args=()
    local lint_config
    lint_config=$(find . \( -name ".golangci.yml" -o -name ".golangci.yaml" \) -not -path "*/vendor/*" | head -1)
    if [[ -f "$lint_config" ]] && grep -q 'gci:' "$lint_config"; then
      while IFS= read -r section; do
        [[ -n "$section" ]] && gci_args+=(-s "$section")
      done < <(awk '/^ *gci:/{found=1} found && /sections:/{in_sec=1; next} in_sec && /^ *- /{gsub(/^ *- /,""); print; next} in_sec && !/^ *- / && !/^ *#/{exit}' "$lint_config")
      # Respect custom-order setting (required for multi-prefix sections)
      if grep -A10 'gci:' "$lint_config" | grep -q 'custom-order: true'; then
        gci_args+=(--custom-order)
      fi
    fi
    if [[ ${#gci_args[@]} -eq 0 ]]; then
      echo ":: Skipping gci (not configured in project lint config)"
    else
      # gci localmodule needs to run from a dir with go.mod
      local gci_dir="."
      [[ -n "$PRIMARY_GOMOD" ]] && gci_dir="$(dirname "$PRIMARY_GOMOD")"
      echo ":: Running gci on modified files (${gci_args[*]})"
      for f in $modified; do
        [[ -f "$f" ]] && (cd "$gci_dir" && gci write "${gci_args[@]}" "$REPO_ROOT/$f") 2>/dev/null || true
      done
    fi
  else
    echo ":: WARNING: gci not available — import ordering may need manual fix"
  fi
}

fix_bounding_dirs() {
  # Remove deprecated --bounding-dirs flag from codegen scripts.
  # k8s 1.36 deepcopy-gen removed this flag. k8s-rebase.sh auto-retries
  # on "unknown flag" errors but may not permanently remove the flag if
  # the tool accepts it as a no-op.
  local codegen_script
  codegen_script=$(find . -name "update-codegen.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
  [[ -z "$codegen_script" ]] && return 0
  if grep -q "bounding-dirs" "$codegen_script"; then
    echo ":: Removing deprecated --bounding-dirs from $(basename "$codegen_script")"
    sed -i '/--bounding-dirs/d' "$codegen_script"
  fi
}

fix_mocks() {
  # Regenerate mocks if codegen deleted them. This covers the case where
  # the agent (not k8s-rebase.sh) ran codegen — k8s-rebase.sh has its
  # own mockery step, but it only runs when its auto-retry succeeds.
  local mockery_config
  mockery_config=$(find . -name ".mockery.yaml" -not -path "*/vendor/*" | head -1)
  [[ -z "$mockery_config" ]] && return 0
  local mock_dir
  mock_dir=$(dirname "$mockery_config")
  if ! find "$mock_dir/pkg/crd" -name "mocks" -type d 2>/dev/null | grep -q .; then
    echo ":: Mock directories missing — running mockery..."
    if make -C "$mock_dir" mocksgen > "$REBASE_TMP/mocksgen.log" 2>&1; then
      echo ":: Mockery regenerated mocks"
    else
      echo ":: WARNING: mockery failed — agent must regenerate mocks"
      tail -5 "$REBASE_TMP/mocksgen.log" 2>/dev/null
    fi
  fi
}

run_vet() {
  # Run go test -run='^$' (vet-only, no tests) on all modules.
  # Stricter than standalone go vet — catches Eventf format/arg
  # count mismatches and other printf-family issues.
  # Skip if local Go is too old — re-validation auto-containerizes.
  local required_go
  required_go=$(grep "^go " "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}')
  local current_go
  current_go=$(go env GOVERSION 2>/dev/null | sed 's/go//')
  if [[ -n "$required_go" ]] && [[ -n "$current_go" ]]; then
    local req_minor cur_minor
    req_minor=$(echo "$required_go" | cut -d. -f2)
    cur_minor=$(echo "$current_go" | cut -d. -f2)
    if [[ "$cur_minor" -lt "$req_minor" ]] 2>/dev/null; then
      echo ":: Skipping vet (Go $current_go < $required_go required — re-validation will check)"
      return 0
    fi
  fi
  echo ":: Running vet (go test -run='^$') on all modules"
  local vet_failed=0
  for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" | sort); do
    local mod_dir
    mod_dir=$(dirname "$gomod")
    # Skip modules with gitignored vendor dirs — their vendor may be
    # stale (not updated by the rebase) and produce false vet errors
    if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
      echo "  Skipping $mod_dir (vendor is gitignored)"
      continue
    fi
    (cd "$mod_dir" && GOMAXPROCS="${GOMAXPROCS:-2}" go test -run='^$' -count=1 ./...) 2>&1 || vet_failed=1
  done
  return "$vet_failed"
}

# Human-readable descriptions for fix functions (used in commit bodies)
declare -A FIX_DESC=(
  [xexp]="migrate x/exp imports to stdlib (maps, slices, cmp)"
  [klog_v2]="migrate klog v1 imports to klog/v2"
  [reflect_ptr]="replace reflect.Ptr with reflect.Pointer"
  [fieldsv1]="replace FieldsV1.Raw with GetRawBytes/NewFieldsV1"
  [eventf]="fix bare Eventf format strings"
  [docs_version]="update version references in docs"
  [version_refs]="update stale version references"
  [go_version]="bump Go version"
  [lint_version]="bump golangci-lint version"
  [kind_image]="update KIND node image tag"
  [kind_version]="bump KIND binary version"
  [metallb_version]="bump MetalLB version"
  [kubevirt_version]="bump KubeVirt version (patch only)"
  [relaxed_service_name_validation]="manage RelaxedServiceNameValidation gate"
  [kubeadm_v1beta4]="migrate kubeadm config to v1beta4 format"
  [crd_int64_validation]="add int64 format to CRD integer fields"
  [crd_name_validation]="update CRD name validation"
  [network_policy_api_crds]="update network-policy-api CRD vendored copies"
  [addtoscheme]="rename AddToScheme to Install"
  [conformance_renames]="apply conformance test renames"
  [obsgen]="add ObservedGeneration to status conditions"
  [banp_egresspeer]="fix BANP EgressPeer type references"
  [feature_gates]="disable problematic feature gates for tests"
  [imports]="deduplicate and sort imports"
  [bounding_dirs]="remove dropped --bounding-dirs codegen flag"
  [mocks]="regenerate mock files"
)

_APPLIED=()
run_fix() {
  local fn="$1" before after
  before=$(git status --short | grep -v '^[?]' | md5sum)
  "$fn"
  after=$(git status --short | grep -v '^[?]' | md5sum)
  [[ "$before" != "$after" ]] && _APPLIED+=("${fn#fix_}")
}

fix_uncommitted() {
  local custom_msg="${1:-}"
  if [[ -n "$(git status --short | grep -v '^[?]')" ]]; then
    git add -A
    local changed_files
    changed_files=$(git diff --cached --name-only)
    local msg="${custom_msg:-$(format_msg "deps" "Apply automated k8s rebase fixes")}"
    # Auto-detect import-only changes when no custom message given
    if [[ -z "$custom_msg" ]]; then
      local changed_count diff_lines
      changed_count=$(echo "$changed_files" | wc -l)
      diff_lines=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
      if [[ "$changed_count" -le 3 ]] && [[ "$diff_lines" -le 30 ]] && ! echo "$changed_files" | grep -qvE '\.go$'; then
        msg="$(format_msg "deps" "Reorder imports after k8s rebase fixes")"
      fi
    fi
    # Build commit body from tracked fix functions
    local body=""
    if [[ ${#_APPLIED[@]} -gt 0 ]]; then
      local descs=()
      for _tag in "${_APPLIED[@]}"; do
        descs+=("${FIX_DESC[$_tag]:-$_tag}")
      done
      body=$(printf '\n\nApplied: %s' "$(printf '%s, ' "${descs[@]}" | sed 's/, $//')")
    fi
    _APPLIED=()
    echo ":: Committing: $(echo "$msg" | head -1)"
    if ! git commit -s --trailer "$AI_TRAILER" -m "${msg}${body}"; then
      echo "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  else
    _APPLIED=()
  fi
}

# ── Main ───────────────────────────────────────────────────────────

# Guard: refuse to run if the rebase script (k8s-rebase.sh) isn't complete.
# Uncommitted go.mod/vendor changes mean the rebase script is still
# running or failed partway. The agent should finish the rebase script and
# commit all changes before running autofix.
if git status --short | grep -qE "go\.mod|go\.sum|vendor/"; then
  echo "ERROR: Uncommitted go.mod/vendor changes — rebase script not complete."
  echo "Finish k8s-rebase.sh and commit all module changes before running autofix."
  echo ""
  git status --short | grep -E "go\.mod|go\.sum|vendor/" | head -5
  exit 1
fi

echo "━━━━ Phase A: Diagnostic ━━━━"
echo ""
DIAG=$(run_checks)
echo "$DIAG"
echo ""

if ! echo "$DIAG" | grep -q "RESULT: PASS"; then
  echo "━━━━ Phase B: Applying fixes ━━━━"
  echo ""

  # ── Code fixes: one commit per fix category for reviewability.
  # fix_imports MUST run last — fix_xexp puts stdlib imports in
  # wrong group, goimports corrects them.
  run_fix fix_xexp
  fix_uncommitted "$(format_msg "deps" "Migrate x/exp imports to stdlib (maps, slices, cmp)")"
  run_fix fix_reflect_ptr
  fix_uncommitted "$(format_msg "deps" "Replace reflect.Ptr with reflect.Pointer")"
  run_fix fix_klog_v2
  fix_uncommitted "$(format_msg "deps" "Migrate klog v1 to v2 import path")"
  run_fix fix_fieldsv1
  fix_uncommitted "$(format_msg "deps" "Replace FieldsV1.Raw with GetRawBytes/NewFieldsV1")"
  run_fix fix_eventf
  fix_uncommitted "$(format_msg "vet" "Fix bare Eventf format strings")"
  run_fix fix_addtoscheme
  fix_uncommitted "$(format_msg "deps" "Replace removed AddToScheme with Install")"
  run_fix fix_conformance_renames
  run_fix fix_banp_egresspeer
  run_fix fix_network_policy_api_crds
  fix_uncommitted "$(format_msg "deps" "Update network-policy-api symbols for conformance")"
  run_fix fix_obsgen
  fix_uncommitted "$(format_msg "deps" "Add ObservedGeneration to ANP/BANP status conditions")"
  run_fix fix_crd_int64_validation
  run_fix fix_crd_name_validation
  fix_uncommitted "$(format_msg "deps" "Fix CRD validation (int64 format, metadata.name)")"
  run_fix fix_bounding_dirs
  fix_uncommitted "$(format_msg "codegen" "Remove deprecated --bounding-dirs flag")"
  run_fix fix_mocks
  fix_uncommitted "$(format_msg "codegen" "Regenerate mocks for updated interfaces")"
  run_fix fix_imports
  fix_uncommitted "$(format_msg "deps" "Reorder imports after stdlib migrations")"
fi

# ── Feature gates (test-only changes)
run_fix fix_feature_gates
fix_uncommitted "$(format_msg "test" "Disable new default-true feature gates for k8s ${K8S_MAJOR_MINOR}")"

# ── CI infrastructure: one commit per ecosystem dep
run_fix fix_kind_image
fix_uncommitted "$(format_msg "ci" "Update KIND image to match k8s ${K8S_MAJOR_MINOR}")"
run_fix fix_kind_version
fix_uncommitted "$(format_msg "ci" "Bump KIND binary to latest release")"
run_fix fix_metallb_version
fix_uncommitted "$(format_msg "ci" "Bump MetalLB to latest release")"
run_fix fix_kubevirt_version
fix_uncommitted "$(format_msg "ci" "Bump KubeVirt to latest patch")"
run_fix fix_relaxed_service_name_validation
run_fix fix_kubeadm_v1beta4
fix_uncommitted "$(format_msg "ci" "Update KIND cluster config for k8s ${K8S_MAJOR_MINOR}")"

# ── Version refs, lint, licenses
run_fix fix_docs_version
fix_uncommitted "$(format_msg "docs" "Update k8s version in documentation")"
run_fix fix_version_refs
run_fix fix_go_version
run_fix fix_lint_version
fix_uncommitted "$(format_msg "ci" "Update version references and lint for k8s ${K8S_MAJOR_MINOR}")"
for _makefile in $(find . -name "Makefile" -not -path "*/vendor/*" -maxdepth 3); do
  _mdir=$(dirname "$_makefile")
  if grep -q "^third-party-licenses:" "$_makefile" 2>/dev/null; then
    echo ":: Regenerating third-party licenses in $_mdir"
    if ! GOTOOLCHAIN=auto make -C "$_mdir" third-party-licenses 2>.rebase-tmp/licenses-err.log; then
      echo "  WARNING: third-party-licenses failed"
      tail -5 .rebase-tmp/licenses-err.log 2>/dev/null | sed 's/^/    /'
    fi
    rm -f "$_mdir"/.third-party-licenses.*.mod "$_mdir"/.third-party-licenses.*.sum 2>/dev/null
  fi
done
fix_uncommitted "$(format_msg "deps" "Regenerate third-party licenses")"

echo ""
echo "━━━━ Phase B.5: Compiler check ━━━━"
echo ""
VET_FAILED=0
run_vet || VET_FAILED=1

# Vet may update go.work.sum or download checksums as a side effect
fix_uncommitted

echo ""
echo "━━━━ Phase C: Re-verification ━━━━"
echo ""
RESULT=$(run_checks)
echo "$RESULT"

CHECKS_PASSED=true
if ! echo "$RESULT" | grep -q "RESULT: PASS"; then
  CHECKS_PASSED=false
fi
if [[ "$VET_FAILED" -eq 1 ]]; then
  CHECKS_PASSED=false
fi

if [[ "$CHECKS_PASSED" == "true" ]]; then
  echo "RESULT: PASS (all checks + vet clean)"
  exit 0
else
  echo ""
  echo "━━━━ Remaining issues (agent must fix) ━━━━"
  echo ""
  # Show file:line details for remaining non-zero grep checks
  echo "$RESULT" | grep -v ': 0$' | grep -v '^---' | grep -v '^RESULT' | while IFS=: read -r name count; do
    count=$(echo "$count" | tr -d ' ')
    case "$name" in
      *"ObsGen"*)
        echo "  $name: Add .WithObservedGeneration(anp.Generation) to the metav1apply.Condition() builder chain."
        echo "    ObservedGeneration is on ConditionApplyConfiguration (k8s.io/client-go/applyconfigurations/meta/v1),"
        echo "    NOT on the ANP/BANP status struct. File:"
        find . -name "status.go" -path "*/admin_network_policy/*" -not -path "*/vendor/*" -exec grep -L 'WithObservedGeneration' {} \; 2>/dev/null | sed 's/^/    /'
        ;;
      *"x/exp"*)
        echo "  $name: Migrate these imports to stdlib (maps, slices, cmp):"
        grep -rn 'golang.org/x/exp' --include='*.go' . | grep -v vendor | sed 's/^/    /'
        ;;
      *"Eventf"*)
        echo "  $name: Wrap .Error() with \"%s\" format string:"
        grep -rn 'Eventf(.*\.Error())' --include='*.go' . | grep -v vendor | grep -v '%s\|%v' | sed 's/^/    /'
        ;;
      *"Gates"*)
        echo "  $name: Feature gates missing. Check GATE_DEPS in autofix script."
        ;;
      *"Conformance old names"*)
        echo "  $name: Rename SupportAdminNetworkPolicy → AdminNetworkPolicy in:"
        grep -n 'SupportAdminNetworkPolicy' test/conformance/network_policy_v2_test.go 2>/dev/null | sed 's/^/    test\/conformance\/network_policy_v2_test.go:/' | sed 's/:/:/' | head -20
        ;;
      *"AddToScheme in factory"*)
        echo "  $name: Remove anpapi.AddToScheme (now registered via scheme init):"
        find . -name "factory.go" -path "*/factory/*" -not -path "*/vendor/*" -exec grep -n 'anpapi.AddToScheme' {} + 2>/dev/null | sed 's/^/    /'
        ;;
      *"AddToScheme in conformance"*)
        echo "  $name: Remove AddToScheme calls (now registered via scheme init):"
        grep -n 'AddToScheme' test/conformance/network_policy_v2_test.go 2>/dev/null | sed 's/^/    test\/conformance\/network_policy_v2_test.go:/' | head -20
        ;;
      *"BANP wrong EgressPeer"*)
        echo "  $name: Change AdminNetworkPolicyEgressPeer → BaselineAdminNetworkPolicyEgressPeer:"
        find . -name "baseline_admin_network_policy_test.go" -not -path "*/vendor/*" -exec grep -n 'AdminNetworkPolicyEgressPeer' {} + 2>/dev/null | grep -v Baseline | sed 's/^/    /'
        ;;
      *"reflect.Ptr"*)
        echo "  $name: Replace reflect.Ptr → reflect.Pointer (deprecated in Go 1.18):"
        grep -rn 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor | sed 's/^/    /'
        ;;
      *"FieldsV1.Raw"*)
        echo "  $name: Replace FieldsV1.Raw with FieldsV1.Items or MarshalJSON():"
        grep -rn 'FieldsV1\.Raw\b\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor | sed 's/^/    /'
        ;;
      *"Stale docs ver"*)
        echo "  $name: Update k8s version references in docs/features/requirements.md:"
        grep -n "| *1\." docs/features/requirements.md 2>/dev/null | sed 's/^/    docs\/features\/requirements.md:/' | head -20
        ;;
      *"CRD format:int32"*)
        echo "  $name: Change format: int32 → format: int64 for uint32 max fields:"
        for _crd in $(find . -path "*/helm/*/crds/*.yaml" -not -path "*/vendor/*" 2>/dev/null); do
          awk '/format: int32/{line=NR; fmt=$0} /maximum: 4294967295/{if(NR==line+1) printf "    %s:%d: %s\n", FILENAME, line, fmt}' "$_crd" 2>/dev/null
        done
        ;;
      *"CRD missing name"*)
        echo "  $name: Restore metadata.name pattern validation in CRD(s):"
        for _crd in $(find . -path "*/helm/*/crds/*.yaml" -not -path "*/vendor/*" 2>/dev/null); do
          awk '/^          metadata:/{m=NR} m && /^          [a-z]/ && !/pattern:/{printf "    %s:%d: metadata block missing pattern\n", FILENAME, m; m=0}' "$_crd" 2>/dev/null
        done
        ;;
      *"E2e test"*)
        echo "  $name: Replace virtualMachineAddressesFromStatus → virtLauncherNetworkStatusIPs:"
        grep -n 'virtualMachineAddressesFromStatus' test/e2e/kubevirt.go 2>/dev/null | sed 's/^/    test\/e2e\/kubevirt.go:/' | head -20
        ;;
      *"Uncommitted"*)
        echo "  $name: $count uncommitted changes — stage and commit:"
        git status --short | grep -v '^[?]' | sed 's/^/    /'
        ;;
      *)
        echo "  $name: $count remaining (see patterns doc for fix)"
        ;;
    esac
  done
  if [[ "$VET_FAILED" -eq 1 ]]; then
    echo ""
    echo "  vet errors found above — fix before proceeding"
  fi
  exit 1
fi
