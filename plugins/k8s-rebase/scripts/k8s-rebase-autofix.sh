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
#     fix_mocks, fix_docs_version, fix_go_version, fix_lint_version, fix_version_refs,
#     fix_crd_int64_validation
#   Ecosystem (KIND e2e): fix_kind_image, fix_kind_version,
#     fix_kubeadm_v1beta4
#   Ecosystem (client-go features): fix_feature_gates

set -uo pipefail

AI_TRAILER="Assisted-by: Claude Code <noreply@anthropic.com>"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
cd "$REPO_ROOT" || exit 1

# Guard: refuse to run on master/main — autofix must run on the rebase branch.
_current_branch=$(git branch --show-current 2>/dev/null || true)
if [[ "$_current_branch" == "master" || "$_current_branch" == "main" ]]; then
  echo "ERROR: Autofix is running on '$_current_branch', not the rebase branch." >&2
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
GIT_DIR=$(git -C "$REPO_ROOT" rev-parse --git-dir 2>/dev/null)
GIT_COMMON_DIR=$(git -C "$REPO_ROOT" rev-parse --git-common-dir 2>/dev/null || echo "$GIT_DIR")
mkdir -p "$GIT_COMMON_DIR/info" 2>/dev/null || true
if [[ -d "$GIT_COMMON_DIR/info" ]]; then
  grep -qF '.rebase-tmp' "$GIT_COMMON_DIR/info/exclude" 2>/dev/null || echo '.rebase-tmp/' >> "$GIT_COMMON_DIR/info/exclude"
  grep -qF '.gitconfig' "$GIT_COMMON_DIR/info/exclude" 2>/dev/null || echo '.gitconfig' >> "$GIT_COMMON_DIR/info/exclude"
fi

# Find primary go.mod with k8s.io deps
PRIMARY_GOMOD=""
for gm in go-controller/go.mod go.mod; do
  [[ -f "$gm" ]] && grep -q "k8s.io/" "$gm" && PRIMARY_GOMOD="$gm" && break
done
[[ -z "$PRIMARY_GOMOD" ]] && PRIMARY_GOMOD=$(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec grep -l "k8s.io/" {} \; | head -1)
MODULE_ROOT="."
[[ -n "$PRIMARY_GOMOD" ]] && MODULE_ROOT=$(dirname "$PRIMARY_GOMOD")
K8S_MINOR=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//' || true)
K8S_MAJOR_MINOR="1.${K8S_MINOR:-??}"

# Auto-containerize if local Go is too old for the repo's go.mod
REQUIRED_GO=""
[[ -n "$PRIMARY_GOMOD" ]] && REQUIRED_GO=$(grep "^go " "$PRIMARY_GOMOD" | awk '{print $2}')
CURRENT_GO=$(go env GOVERSION 2>/dev/null | sed 's/go//' || echo "0.0")
if [[ -n "$REQUIRED_GO" ]] && [[ "${K8S_REBASE_IN_CONTAINER:-}" != "1" ]]; then
  REQ_MINOR=$(cut -d. -f2 <<< "$REQUIRED_GO")
  CUR_MINOR=$(cut -d. -f2 <<< "$CURRENT_GO")
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
      # Mount the host Go module cache to avoid ENOSPC in the container's
      # overlay filesystem and to reuse already-downloaded modules.
      HOST_GOMODCACHE="$(go env GOMODCACHE 2>/dev/null || echo "${GOPATH:-$HOME/go}/pkg/mod")"
      GOMODCACHE_MOUNT=""
      if [[ -n "$HOST_GOMODCACHE" ]]; then
        mkdir -p "$HOST_GOMODCACHE"
        GOMODCACHE_MOUNT="-v $HOST_GOMODCACHE:$HOST_GOMODCACHE"
      fi
      # For git worktrees, the .git file points outside REPO_ROOT to the
      # common git dir. Mount it so git rev-parse works inside the container.
      GIT_COMMON_DIR_HOST="$(git -C "$REPO_ROOT" rev-parse --git-common-dir 2>/dev/null || true)"
      # Absolutize: if git-common-dir returns relative path, resolve it
      if [[ -n "$GIT_COMMON_DIR_HOST" && "$GIT_COMMON_DIR_HOST" != /* ]]; then
        GIT_COMMON_DIR_HOST="$(cd "$REPO_ROOT/$GIT_COMMON_DIR_HOST" 2>/dev/null && pwd || true)"
      fi
      GIT_COMMON_MOUNT=""
      if [[ -n "$GIT_COMMON_DIR_HOST" && "$GIT_COMMON_DIR_HOST" != "$REPO_ROOT/.git" ]]; then
        GIT_COMMON_MOUNT="-v $GIT_COMMON_DIR_HOST:$GIT_COMMON_DIR_HOST"
      fi
      exec $CONTAINER_RT run --rm \
        --security-opt label=disable \
        $USERNS_FLAG \
        -v "$REPO_ROOT:$REPO_ROOT" \
        $GOMODCACHE_MOUNT \
        $GIT_COMMON_MOUNT \
        -v "$(dirname "$SCRIPT_PATH"):$(dirname "$SCRIPT_PATH"):ro" \
        -w "$REPO_ROOT" \
        -e GIT_AUTHOR_NAME="$(git config user.name)" \
        -e GIT_AUTHOR_EMAIL="$(git config user.email)" \
        -e GIT_COMMITTER_NAME="$(git config user.name)" \
        -e GIT_COMMITTER_EMAIL="$(git config user.email)" \
        -e K8S_REBASE_IN_CONTAINER=1 \
        -e GOMODCACHE="$HOST_GOMODCACHE" \
        "$GO_IMAGE" \
        bash "$SCRIPT_PATH"
    else
      echo ":: WARNING: Go $CURRENT_GO < $REQUIRED_GO and no container runtime — go vet/goimports skipped. Install Go $REQUIRED_GO+ or podman/docker."
    fi
  fi
fi

# Disable GPG signing — scripts run non-interactively (nohup/containers)
# where gpg-agent cannot prompt. Append to existing GIT_CONFIG_COUNT
# rather than clobbering (user may have proxy/credential config).
_gc=${GIT_CONFIG_COUNT:-0}
export GIT_CONFIG_KEY_${_gc}=commit.gpgsign
export GIT_CONFIG_VALUE_${_gc}=false
_gc=$((_gc + 1))
if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
  export GIT_CONFIG_KEY_${_gc}=safe.directory
  export GIT_CONFIG_VALUE_${_gc}="$REPO_ROOT"
  _gc=$((_gc + 1))
  # Install jq if missing (needed by verify-third-party-licenses)
  if ! command -v jq &>/dev/null; then
    curl -sL https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 -o /tmp/jq 2>/dev/null \
      && echo "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5  /tmp/jq" | sha256sum -c --quiet 2>/dev/null \
      && chmod +x /tmp/jq && export PATH="/tmp:$PATH"
  fi
fi
export GIT_CONFIG_COUNT=$_gc

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
  # Gate checks — driven by GATE_DEPS map. Only checks gates that
  # exist in the vendored k8s code (safe across k8s versions).
  local _active_gates="" _all_gate_names=""
  for _p in "${!GATE_DEPS[@]}"; do
    if grep -rq "\"$_p\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null; then
      # Skip GA+LockToDefault gates (cannot be disabled, would cause SetFromMap error)
      if awk -v g="${_p}:" '$0 ~ g {found=1; next} found && /LockToDefault: true/ {print "locked"; exit} found && /^[[:space:]]*[A-Z]/ {exit} found && /^[[:space:]]*\}/ {exit}' \
         "$MODULE_ROOT/vendor/k8s.io/client-go/features/known_features.go" 2>/dev/null | grep -q "locked"; then
        continue
      fi
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
      grep -q "KUBE_FEATURE_${_g}" "$_f" || _genv=$((_genv+1))
    done
  done
  r "Gates in env var files" "$_genv"
  # SetFromMap files: check ALL gates (parents + deps) that exist in vendor.
  # SetFromMap validates parent-dep consistency and rejects unrecognized gates.
  local _sfm_gates="$_active_gates"
  for _p in "${!GATE_DEPS[@]}"; do
    grep -rq "\"$_p\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null || continue
    # Skip locked parents — their deps must not appear in SetFromMap either.
    if awk -v g="${_p}:" '$0 ~ g {found=1; next} found && /LockToDefault: true/ {print "locked"; exit} found && /^[[:space:]]*[A-Z]/ {exit} found && /^[[:space:]]*\}/ {exit}' \
       "$MODULE_ROOT/vendor/k8s.io/client-go/features/known_features.go" 2>/dev/null | grep -q "locked"; then
      continue
    fi
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
  r "x/exp imports" "$(grep -rn 'golang.org/x/exp' --include='*.go' . | grep -v vendor | wc -l)"
  r "reflect.Ptr" "$(grep -rn 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor | wc -l)"
  if [[ "${K8S_MINOR:-0}" -ge 36 ]] 2>/dev/null; then
    r "FieldsV1.Raw" "$(grep -rn 'FieldsV1\.Raw\b\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor | wc -l)"
  else
    r "FieldsV1.Raw" "0"
  fi
  # Generic major-version import check: find bare imports where /vN exists in go.mod
  local _mv_stale=0
  for _mod in $(grep -oP 'k8s\.io/[a-zA-Z0-9_-]+/v\d+' "$PRIMARY_GOMOD" 2>/dev/null | sed 's|/v[0-9]*$||' | sort -u); do
    local _bare
    _bare=$(grep -rn "\"$_mod\"" --include='*.go' . 2>/dev/null | grep -v vendor/ | grep -v "\"${_mod}/v" | wc -l)
    _mv_stale=$((_mv_stale + _bare))
  done
  r "Stale major-version imports" "$_mv_stale"
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
  for _crd in $(find . \( -path "*/crds/*.yaml" -o -path "*/crd/*.yaml" \
    -o -path "*/bindata/*.yaml" -o -path "*/manifests/*.yaml" \
    -o -path "*/config/crd/*.yaml" -o -path "*/_output/*.yaml" \) \
    -not -path "*/vendor/*" -not -path "*/.claude/*" -not -path "*/testdata/*" 2>/dev/null); do
    if awk '/format: int32/{p=1;next} /maximum: 4294967295/{if(p){found=1;exit}} {p=0} END{exit !found}' "$_crd" 2>/dev/null; then
      _crd_int64_miss=$((_crd_int64_miss+1))
    fi
  done
  r "CRD int32 before uint32 max" "$_crd_int64_miss"
  local _crd_name_miss=0
  local _base=""
  for _c in master main; do git rev-parse --verify "$_c" &>/dev/null && _base="$_c" && break; done
  if [[ -n "$_base" ]]; then
    for _crd in $(find . \( -path "*/crds/*.yaml" -o -path "*/crd/*.yaml" \
      -o -path "*/bindata/*.yaml" -o -path "*/manifests/*.yaml" \
      -o -path "*/config/crd/*.yaml" -o -path "*/_output/*.yaml" \) \
      -not -path "*/vendor/*" -not -path "*/.claude/*" -not -path "*/testdata/*" 2>/dev/null); do
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
  r "Uncommitted" "$(git status --short | grep -v '^[?]' | wc -l)"
  echo "---"
  [[ "$F" -eq 0 ]] && echo "RESULT: PASS" || echo "RESULT: FAIL ($F checks non-zero)"
  return "$F"
}

# ── Fix functions ──────────────────────────────────────────────────
# Generic fixes (apply to any k8s rebase)

fix_xexp() {
  local files
  files=$(grep -rln 'golang.org/x/exp/' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing x/exp imports in $(wc -l <<< "$files") files"
  for f in $files; do
    # In-place replacement — always produces compilable code even if
    # goimports fails to install. Import ends up in the wrong group
    # (third-party instead of stdlib) but goimports/gci fix that.
    sed -i 's|"golang.org/x/exp/maps"|"maps"|g' "$f"
    sed -i 's|"golang.org/x/exp/slices"|"slices"|g' "$f"
    if grep -q 'constraints\.\(Integer\|Float\|Signed\|Unsigned\|Complex\)' "$f"; then
      echo ":: WARNING: $f uses non-Ordered constraints types — skipping constraints rewrite (manual fix required)"
    else
      sed -i 's|"golang.org/x/exp/constraints"|"cmp"|g' "$f"
      sed -i 's/constraints\.Ordered/cmp.Ordered/g' "$f"
    fi
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
  for gomod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec grep -l 'golang.org/x/exp' {} \; | xargs -I{} dirname {}); do
    echo ":: Running go mod tidy in $gomod_dir"
    (cd "$gomod_dir" && go mod tidy 2>/dev/null && [[ -d vendor ]] && go mod vendor 2>/dev/null) || true
  done
}

fix_klog_v2() {
  local files
  files=$(grep -rln '"k8s.io/klog"' --include='*.go' . | grep -v vendor | grep -v '/v2')
  [[ -z "$files" ]] && return 0
  echo ":: Fixing klog v1 → v2 imports in $(wc -l <<< "$files") files"
  for f in $files; do
    sed -i 's|"k8s.io/klog"|"k8s.io/klog/v2"|g' "$f"
  done
  for _gm in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec grep -l 'k8s.io/klog ' {} \;); do
    echo ":: Running go mod tidy+vendor in $(dirname "$_gm") to remove stale klog v1"
    (cd "$(dirname "$_gm")" && GOWORK=off go mod tidy 2>/dev/null && [[ -d vendor ]] && go mod vendor 2>/dev/null) || true
  done
}

fix_reflect_ptr() {
  local files
  files=$(grep -rln 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing reflect.Ptr → reflect.Pointer in $(wc -l <<< "$files") files"
  for f in $files; do
    sed -i 's/reflect\.Ptr\b/reflect.Pointer/g' "$f"
  done
}

fix_fieldsv1() {
  # GetRawBytes/NewFieldsV1 only exist in apimachinery v0.36+ (k8s 1.36+)
  [[ "${K8S_MINOR:-0}" -lt 36 ]] && return 0
  local files
  files=$(grep -rln 'FieldsV1\.Raw\b\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor)
  [[ -z "$files" ]] && return 0
  echo ":: Fixing FieldsV1.Raw in $(wc -l <<< "$files") files"
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
      lineno="${match%%:*}"
      content="${match#*:}"
      commas=$(sed 's/\.Error().*//' <<< "$content" | tr -cd ',' | wc -c)
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
  [[ -z "$old_go" ]] && old_go=$(grep -oE 'golang-[0-9]+\.[0-9]+' .ci-operator.yaml 2>/dev/null | head -1 | sed 's/golang-//')
  [[ -z "$old_go" ]] && old_go=$(grep -roE 'golang[:-][0-9]+\.[0-9]+' --include="Dockerfile*" . 2>/dev/null | grep -v vendor | grep -v '/\.git/' | head -1 | sed 's/.*golang[:-]//')
  [[ -z "$old_go" ]] && old_go=$(grep -roE 'GOVERSION="?[0-9]+\.[0-9]+' --include="Dockerfile*" . 2>/dev/null | grep -v vendor | grep -v '/\.git/' | head -1 | sed 's/.*GOVERSION="*//')
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
      -e "s|GOVERSION=\"${old_go}|GOVERSION=\"${new_go}|g" \
      -e "s|GOVERSION=${old_go}|GOVERSION=${new_go}|g" \
      "$f"
  done < <(grep -rlnE "golang[:-]${old_go}|GO_VERSION.{0,5}${old_go}|GOLANG_VERSION.{0,5}${old_go}|GOVERSION.{0,5}${old_go}|go-version:.{0,3}${old_go}" \
    --include="*.yml" --include="*.yaml" --include="Makefile*" --include="Dockerfile*" . \
    | grep -v vendor | grep -v '/\.git/' | grep -v go.mod || true)

  # Second pass: catch workflow files with any stale go-version (pre-existing mismatches)
  while IFS= read -r _gvf; do
    # Skip files with a multi-version go-version matrix (e.g. [1.22, 1.23]).
    # Replacing only the first element would leave a stale secondary version.
    if grep -qE 'go-version: *\[[0-9]+\.[0-9]+,' "$_gvf"; then
      echo "WARN: skipping second-pass go-version rewrite in $_gvf (multi-version matrix — update manually)"
      continue
    fi
    sed -i -E \
      -e "s|go-version: \[[0-9]+\.[0-9]+|go-version: [${new_go}|g" \
      -e "s|go-version: [0-9]+\.[0-9]+|go-version: ${new_go}|g" \
      "$_gvf"
  done < <(grep -rlE "go-version: *\[?[0-9]+\.[0-9]+" \
    --include="*.yml" --include="*.yaml" .github/workflows/ 2>/dev/null \
    | grep -v vendor | grep -v "/\.git/" || true)
}

fix_lint_version() {
  local lint_sh
  lint_sh=$(find . -name "lint.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
  [[ -z "$lint_sh" ]] && return 0
  local LATEST_LINT
  LATEST_LINT=$(curl -sf --retry 2 --connect-timeout 10 "https://api.github.com/repos/golangci/golangci-lint/releases/latest" 2>/dev/null | grep -oE '"tag_name": "v[^"]+"' | sed 's/"tag_name": "//;s/"//' || true)
  local lint_ver test_yml
  lint_ver=$(grep -oE '^VERSION=v[0-9.]+' "$lint_sh" | head -1 | sed 's/VERSION=//')

  # Bump lint version if the current one can't parse the target Go version.
  # golangci-lint binaries are built with a specific Go version and can't
  # parse code targeting a newer Go. Fetch latest to get one built with
  # a recent enough Go.
  local required_go
  required_go=$(grep "^go " "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}' | cut -d. -f2)
  if [[ -n "$lint_ver" ]] && [[ -n "$required_go" ]] && [[ "$required_go" -ge 26 ]] 2>/dev/null; then
    # v2.5.0 was built with Go 1.25, v2.12+ with Go 1.26
    local lint_minor="${lint_ver#v*.}"
    lint_minor="${lint_minor%%.*}"
    if [[ "$lint_ver" == v2.* ]] && (( lint_minor < 12 )) 2>/dev/null; then
      if [[ -n "$LATEST_LINT" ]]; then
        echo ":: Bumping golangci-lint: $lint_ver → $LATEST_LINT (Go 1.${required_go} requires newer build)"
        sed -i "s/^VERSION=${lint_ver}/VERSION=${LATEST_LINT}/" "$lint_sh"
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
      if [[ -n "$lint_sh" ]] && grep -qE "^VERSION=v1\." "$lint_sh" 2>/dev/null; then
        echo ":: Bumping hack/lint.sh from v1 to ${latest_v2}"
        sed -i -E "s|^VERSION=v1\.[0-9.]+|VERSION=${latest_v2}|" "$lint_sh"
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
  if grep -rl "K8S_VERSION" --include="*.sh" --include="*.yml" --include="*.yaml" --include="Makefile*" --include="kind-common" . 2>/dev/null | grep -v vendor | xargs grep -l "kindest/node" 2>/dev/null | grep -q .; then
    uses_k8s_version_for_kind=1
  fi
  local OLD=$((NEW-1))
  if [[ -z "$kind_tag" ]]; then
    local revert_tag="v1.${OLD}.1"
    echo ":: kindest/node:v1.${NEW}.* not available — reverting KIND refs to ${revert_tag}"
    for f in $(grep -rln "kindest/node" \
      --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" --include="kind-common" . \
      | grep -v vendor); do
      perl -i -pe 'BEGIN{$n='$NEW'; $t="'"$revert_tag"'"} s{kindest/node:v1\.(\d+)\.\d+}{$1 < $n ? "kindest/node:$t" : $&}ge' "$f"
    done
    if [[ -n "$uses_k8s_version_for_kind" ]]; then
      for f in $(grep -rln "K8S_VERSION" \
        --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" --include="kind-common" . \
        | grep -v vendor); do
        sed -i -E "/K8S_VERSION/s#v1\.${NEW}\.[0-9]+#${revert_tag}#g" "$f"
      done
    fi
  else
    local _changed=0
    for f in $(grep -rln "kindest/node" \
      --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" --include="kind-common" . \
      | grep -v vendor | grep -v go.mod); do
      perl -i -pe 'BEGIN{$n='$NEW'; $t="'"$kind_tag"'"} s{kindest/node:v1\.(\d+)\.\d+}{$1 < $n ? "kindest/node:$t" : $&}ge' "$f"
      _changed=1
    done
    if [[ -n "$uses_k8s_version_for_kind" ]]; then
      for f in $(grep -rln "K8S_VERSION" \
        --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile*" --include="kind-common" . \
        | grep -v vendor | grep -v go.mod); do
        sed -i -E "/K8S_VERSION/s#v?1\.${OLD}(\.[0-9]+)?#${kind_tag}#g; /K8S_VERSION/s#v1\.${NEW}\.[0-9]+#${kind_tag}#g" "$f"
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

  chmod "$(stat -c '%a' "$kind_yaml" 2>/dev/null || stat -f '%Lp' "$kind_yaml" 2>/dev/null || echo 644)" "${kind_yaml}.tmp" 2>/dev/null || true
  mv "${kind_yaml}.tmp" "$kind_yaml"
  echo ":: Migrated kubeadm extraArgs to v1beta4 list format"
}

fix_crd_go_markers() {
  # Add +kubebuilder:validation:Format=int64 markers to Go types files.
  # (ensures future codegen produces correct CRDs)
  local files
  files=$(find . -name "*types*.go" -path "*/crd/*" -not -path "*/vendor/*" 2>/dev/null)
  for f in $files; do
    if grep -q "Maximum.*4294967295" "$f" && ! grep -q "Format.*int64\|Format=int64" "$f"; then
      echo ":: Adding Format=int64 kubebuilder marker in $f"
      sed -i '/Maximum.*4294967295/a\\t// +kubebuilder:validation:Format=int64' "$f"
    fi
  done
}

fix_crd_yaml_format() {
  # Patch format: int64 directly into CRD YAML files.
  # (immediate fix without re-running codegen, which would strip
  # hand-edited metadata blocks from unrelated CRDs)
  # Runs unconditionally — repos like CNO have vendored CRD YAMLs with no types.go.
  local crd_yamls
  crd_yamls=$(find . \( -path "*/crds/*.yaml" -o -path "*/crd/*.yaml" \
    -o -path "*/bindata/*.yaml" -o -path "*/manifests/*.yaml" \
    -o -path "*/config/crd/*.yaml" -o -path "*/_output/*.yaml" \) \
    -not -path "*/vendor/*" -not -path "*/.claude/*" -not -path "*/testdata/*" \
    -exec grep -l "maximum: 4294967295" {} \; 2>/dev/null)
  [[ -z "$crd_yamls" ]] && return 0
  echo ":: Patching CRD YAML files: ensure format: int64 for uint32 fields"
  for crd_yaml in $crd_yamls; do
    grep -q "maximum: 4294967295" "$crd_yaml" || continue
    if ! awk '
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
    ' "$crd_yaml" > "${crd_yaml}.tmp"; then
      echo "  WARNING: awk failed on $(basename "$crd_yaml") — leaving original unchanged"
      rm -f "${crd_yaml}.tmp"
      continue
    fi
    chmod "$(stat -c '%a' "$crd_yaml" 2>/dev/null || stat -f '%Lp' "$crd_yaml" 2>/dev/null || echo 644)" "${crd_yaml}.tmp" 2>/dev/null || true
    mv "${crd_yaml}.tmp" "$crd_yaml"
    if ! awk '/format: int32/{p=1;next} /maximum: 4294967295/{if(p){found=1;exit}} {p=0} END{exit !found}' "$crd_yaml" 2>/dev/null; then
      echo "  Patched $(basename "$crd_yaml")"
    else
      echo "  WARNING: format: int32 still precedes maximum: 4294967295 in $(basename "$crd_yaml")"
    fi
  done
}

fix_crd_int64_validation() {
  # k8s 1.36 rejects CRD integer fields where Maximum > int32 max
  # but format is int32 (the default for uint32 Go types).
  fix_crd_go_markers
  fix_crd_yaml_format
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
      pkg_alias=$(sed 's/\.AddToScheme.*//' <<< "$line" | grep -oE '[a-zA-Z0-9_]+$')
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
fix_feature_gates() {
  # Iterate GATE_DEPS directly — no external file needed.
  # Only process gates that exist in the vendored k8s code.
  # Skip gates that are GA+LockToDefault (cannot be disabled via SetFromMap).
  local parents=() all_deps=()
  for gate in "${!GATE_DEPS[@]}"; do
    grep -rq "\"$gate\"" "$MODULE_ROOT/vendor/k8s.io/" 2>/dev/null || continue
    if awk -v g="${gate}:" '$0 ~ g {found=1; next} found && /LockToDefault: true/ {print "locked"; exit} found && /^[[:space:]]*[A-Z]/ {exit} found && /^[[:space:]]*\}/ {exit}' \
       "$MODULE_ROOT/vendor/k8s.io/client-go/features/known_features.go" 2>/dev/null | grep -q "locked"; then
      echo ":: Skipping locked gate $gate (GA, cannot be disabled)"
      continue
    fi
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
        setenv_line=$(grep -n 'os\.Setenv.*KUBE_FEATURE' "$tf" | head -1 | cut -d: -f1)
        if [[ -z "$setenv_line" ]]; then
          echo "  WARNING: could not locate os.Setenv line in $tf — skipping gate $gate"
          continue
        fi
        sed -i "${setenv_line}i\\
\\tos.Setenv(\"KUBE_FEATURE_${gate}\", \"false\")" "$tf"
      fi
      if grep -q 't\.Setenv.*KUBE_FEATURE' "$tf" && ! grep -q "t\.Setenv.*${gate}" "$tf"; then
        local tsetenv_line
        tsetenv_line=$(grep -n 't\.Setenv.*KUBE_FEATURE' "$tf" | head -1 | cut -d: -f1)
        if [[ -z "$tsetenv_line" ]]; then
          echo "  WARNING: could not locate t.Setenv line in $tf — skipping gate $gate"
          continue
        fi
        sed -i "${tsetenv_line}i\\
\\tt.Setenv(\"KUBE_FEATURE_${gate}\", \"false\")" "$tf"
      fi
    done
  done

  # ── Layer 3: SetFromMap in test files ──
  # Add ALL gates (parents + deps) to SetFromMap. SetFromMap validates
  # parent-dep consistency — disabling a parent without its deps errors.
  # Each gate is checked against vendor to avoid adding removed gates.
  local sfm_gates=("${parents[@]}")
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
        sed -i "/SetFromMap/s/\(true\|false\)}/\1, \"${g}\": false}/" "$tf" 2>/dev/null || true
        if ! grep -q "\"$g\"" "$tf"; then
          echo "  WARNING: gate $g not inserted into $tf (SetFromMap may be multi-line — manual fix needed)"
        fi
      fi
    done

    # Broaden the unrecognized-gate filter if present (safety net).
    if grep -qE 'unrecognized feature gate: [A-Za-z0-9]+' "$tf"; then
      sed -i 's/unrecognized feature gate: [A-Za-z0-9]\+/unrecognized feature gate/' "$tf"
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
    echo ":: Running goimports on $(wc -l <<< "$modified") modified files"
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
  # Read output dir from config; skip (don't assume missing) if unparseable.
  local out_dir
  out_dir=$(grep -m1 '^[[:space:]]*dir:' "$mockery_config" | awk '{print $2}')
  [[ -z "$out_dir" ]] && return 0
  if ! find "$mock_dir/$out_dir" -name "*.go" -type f 2>/dev/null | grep -q .; then
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
    req_minor=$(cut -d. -f2 <<< "$required_go")
    cur_minor=$(cut -d. -f2 <<< "$current_go")
    if [[ "$cur_minor" -lt "$req_minor" ]] 2>/dev/null; then
      echo ":: Skipping vet (Go $current_go < $required_go required — re-validation will check)"
      return 0
    fi
  fi
  echo ":: Running vet (go test -run='^$') on all modules"
  local vet_failed=0
  for gomod in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" | sort); do
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
  [kubeadm_v1beta4]="migrate kubeadm config to v1beta4 format"
  [crd_int64_validation]="add int64 format to CRD integer fields"
  [addtoscheme]="rename AddToScheme to Install"
  [feature_gates]="disable problematic feature gates for tests"
  [imports]="deduplicate and sort imports"
  [bounding_dirs]="remove dropped --bounding-dirs codegen flag"
  [mocks]="regenerate mock files"
)

_APPLIED=()
run_fix() {
  local fn="$1" before after
  before=$(git status --short | grep -v '^[?]' | md5sum)
  "$fn" || echo "WARNING: $fn returned non-zero — partial changes may have been staged above"
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
      changed_count=$(wc -l <<< "$changed_files")
      diff_lines=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
      if [[ "$changed_count" -le 3 ]] && [[ "$diff_lines" -le 30 ]] && ! grep -qvE '\.go$' <<< "$changed_files"; then
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

if [[ "$DIAG" != *"RESULT: PASS"* ]]; then
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
  run_fix fix_crd_int64_validation
  fix_uncommitted "$(format_msg "deps" "Fix CRD int64 format validation")"
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
run_fix fix_kubeadm_v1beta4
fix_uncommitted "$(format_msg "ci" "Migrate KIND kubeadm config to v1beta4")"

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
if [[ "$RESULT" != *"RESULT: PASS"* ]]; then
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
    count="${count// /}"
    case "$name" in
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
      *"CRD int32"*)
        echo "  $name: Change format: int32 → format: int64 for uint32 max fields:"
        for _crd in $(find . \( -path "*/crds/*.yaml" -o -path "*/crd/*.yaml" \
      -o -path "*/bindata/*.yaml" -o -path "*/manifests/*.yaml" \
      -o -path "*/config/crd/*.yaml" -o -path "*/_output/*.yaml" \) \
      -not -path "*/vendor/*" -not -path "*/.claude/*" -not -path "*/testdata/*" 2>/dev/null); do
          awk '/format: int32/{line=NR; fmt=$0} /maximum: 4294967295/{if(NR==line+1) printf "    %s:%d: %s\n", FILENAME, line, fmt}' "$_crd" 2>/dev/null
        done
        ;;
      *"CRD missing name"*)
        echo "  $name: Restore metadata.name pattern validation in CRD(s):"
        for _crd in $(find . \( -path "*/crds/*.yaml" -o -path "*/crd/*.yaml" \
      -o -path "*/bindata/*.yaml" -o -path "*/manifests/*.yaml" \
      -o -path "*/config/crd/*.yaml" -o -path "*/_output/*.yaml" \) \
      -not -path "*/vendor/*" -not -path "*/.claude/*" -not -path "*/testdata/*" 2>/dev/null); do
          awk '/^          metadata:/{m=NR} m && /^          [a-z]/ && !/pattern:/{printf "    %s:%d: metadata block missing pattern\n", FILENAME, m; m=0}' "$_crd" 2>/dev/null
        done
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
