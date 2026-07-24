#!/bin/bash
# k8s-rebase.sh — Automate Kubernetes dependency rebase for Go projects
#
# Usage: k8s-rebase.sh [--bump-tools] <version>
#   e.g.: k8s-rebase.sh 1.36.0
#         k8s-rebase.sh --bump-tools 1.36.0
#
# Run from any Go repo with k8s.io dependencies. The script auto-detects
# go.mod files, codegen scripts, and vendor directories.
#
# Handles the automated rebase (deterministic). Validation and
# fixes are handled by the companion skill or manually.
#
# Exit codes: 0 = already at target (nothing to do)
#             1 = error
#             2 = mechanical rebase done, validation needed

# -e: fail fast on unexpected errors (autofix/validate omit -e
# because they must continue past failures to collect all results)
set -euo pipefail
trap 'echo "ERROR: k8s-rebase.sh crashed at line $LINENO" >&2' ERR

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
REBASE_TMP="$REPO_ROOT/.rebase-tmp"
mkdir -p "$REBASE_TMP"
grep -qF '.rebase-tmp' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.rebase-tmp/' >> "$REPO_ROOT/.git/info/exclude"
grep -qF '.config' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.config/' >> "$REPO_ROOT/.git/info/exclude"
grep -qF '.cache' "$REPO_ROOT/.git/info/exclude" 2>/dev/null || echo '.cache/' >> "$REPO_ROOT/.git/info/exclude"

# ── Helpers ──────────────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo ":: $*"; }
banner() { echo ""; echo "━━━━ $* ━━━━"; echo ""; }

# Format commit messages per project convention. If CONTRIBUTING.md
# requires "subcomponent: lowercase" prefixes, prepend the category.
# Otherwise use action-verb sentence case (the default).
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

# Save/restore CRD hand-edits across codegen.
# controller-gen regenerates CRD YAMLs but can't express hand-edited
# constraints like metadata.name patterns. These functions snapshot
# CRD files before codegen and splice preserved sections back after.
save_crd_metadata() {
  local helm_crd_dir save_dir="$REBASE_TMP/crd-pre-codegen"
  helm_crd_dir=$(find "$REPO_ROOT" -path "*/helm/*/crds" -type d -not -path "*/vendor/*" 2>/dev/null | head -1)
  [[ -z "$helm_crd_dir" ]] && return 0
  rm -rf "$save_dir" && mkdir -p "$save_dir"
  cp "$helm_crd_dir"/*.yaml "$save_dir/" 2>/dev/null || true
  echo "$helm_crd_dir" > "$save_dir/.helm-crd-dir"
}
restore_crd_metadata() {
  local save_dir="$REBASE_TMP/crd-pre-codegen"
  [[ -d "$save_dir" ]] || return 0
  local helm_crd_dir
  helm_crd_dir=$(cat "$save_dir/.helm-crd-dir" 2>/dev/null) || return 0
  [[ -d "$helm_crd_dir" ]] || return 0
  local restored=0
  for saved in "$save_dir"/*.yaml; do
    [[ -f "$saved" ]] || continue
    local crd="$helm_crd_dir/$(basename "$saved")"
    [[ -f "$crd" ]] || continue
    # Find metadata section boundaries in both files
    # (|| true prevents pipefail from killing the script on no-match)
    local s_start s_end c_start c_end
    s_start=$(grep -n "^          metadata:" "$saved" 2>/dev/null | head -1 | cut -d: -f1 || true)
    c_start=$(grep -n "^          metadata:" "$crd" 2>/dev/null | head -1 | cut -d: -f1 || true)
    [[ -z "$s_start" || -z "$c_start" ]] && continue
    s_end=$(awk "NR>$s_start && /^          [a-z]/{print NR; exit}" "$saved")
    c_end=$(awk "NR>$c_start && /^          [a-z]/{print NR; exit}" "$crd")
    [[ -z "$s_end" || -z "$c_end" ]] && continue
    # Compare metadata sections — if saved has more lines, hand-edits were stripped
    local s_lines=$((s_end - s_start)) c_lines=$((c_end - c_start))
    if [[ "$s_lines" -gt "$c_lines" ]]; then
      info "Restoring CRD metadata hand-edits in $(basename "$crd") ($s_lines lines → was $c_lines)"
      {
        head -n "$((c_start - 1))" "$crd"
        sed -n "${s_start},$((s_end - 1))p" "$saved"
        tail -n "+${c_end}" "$crd"
      } > "${crd}.tmp"
      chmod --reference="$crd" "${crd}.tmp" 2>/dev/null || true
      mv "${crd}.tmp" "$crd"
      restored=1
    fi
  done
  [[ "$restored" -eq 1 ]] && info "CRD metadata hand-edits restored" || true
}

# ── Argument parsing ─────────────────────────────────────────────────

BUMP_TOOLS=false
VERSION_INPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump-tools) BUMP_TOOLS=true; shift ;;
    *) VERSION_INPUT="$1"; shift ;;
  esac
done

if [[ -z "$VERSION_INPUT" ]]; then
  echo "Usage: $SCRIPT_NAME [--bump-tools] <k8s-version>"
  echo "  e.g.: $SCRIPT_NAME 1.36.0"
  exit 1
fi

# Parse X.Y.Z or X.Y (default Z=0)
if [[ "$VERSION_INPUT" =~ ^([0-9]+)\.([0-9]+)(\.([0-9]+))?$ ]]; then
  K8S_MAJOR="${BASH_REMATCH[1]}"
  K8S_MINOR="${BASH_REMATCH[2]}"
  K8S_PATCH="${BASH_REMATCH[4]:-0}"
  [[ "$K8S_MAJOR" != "1" ]] && die "Expected k8s major version 1, got $K8S_MAJOR"
else
  die "Invalid version format: $VERSION_INPUT (expected X.Y or X.Y.Z)"
fi

K8S_FULL="v${K8S_MAJOR}.${K8S_MINOR}.${K8S_PATCH}"
K8S_MAJOR_MINOR="${K8S_MAJOR}.${K8S_MINOR}"
API_VERSION="v0.${K8S_MINOR}.${K8S_PATCH}"
AI_TRAILER="Assisted-by: Claude Code <noreply@anthropic.com>"

# ── Phase 0: Prerequisites ──────────────────────────────────────────

banner "Phase 0: Prerequisites"

cd "$REPO_ROOT" || die "Cannot cd to $REPO_ROOT"

# Disable Go workspace mode so each module is resolved independently
export GOWORK=off

# Find the primary go.mod (first one with k8s.io deps)
PRIMARY_GOMOD=""
for candidate in go-controller/go.mod go.mod; do
  if [[ -f "$candidate" ]] && grep -qE "k8s\.io/(api|client-go|apimachinery) " "$candidate"; then
    PRIMARY_GOMOD="$candidate"
    break
  fi
done
if [[ -z "$PRIMARY_GOMOD" ]]; then
  # Search within this repo only — skip directories that are separate git repos
  while IFS= read -r -d '' gomod; do
    dir=$(dirname "$gomod")
    # Skip if this go.mod lives inside a nested git repo
    mod_toplevel=$(cd "$dir" && git rev-parse --show-toplevel 2>/dev/null) || continue
    [[ "$mod_toplevel" != "$REPO_ROOT" ]] && continue
    if grep -qE "k8s\.io/(api|client-go|apimachinery) " "$gomod"; then
      PRIMARY_GOMOD="$gomod"
      break
    fi
  done < <(find . -name "go.mod" -not -path "*/vendor/*" -print0 2>/dev/null)
fi
[[ -z "$PRIMARY_GOMOD" ]] && die "No go.mod with k8s.io dependencies found in $REPO_ROOT"

# Detect version from k8s.io/api, client-go, or apimachinery (in priority order)
OLD_API_VERSION=""
for pkg in "k8s.io/api " "k8s.io/client-go " "k8s.io/apimachinery "; do
  OLD_API_VERSION=$(grep "$pkg" "$PRIMARY_GOMOD" 2>/dev/null | grep -v "=>" | head -1 | awk '{print $2}' || true)
  [[ -n "$OLD_API_VERSION" ]] && break
done
OLD_MINOR=$(echo "$OLD_API_VERSION" | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//' || true)
[[ -z "$OLD_MINOR" ]] && die "Cannot detect current k8s minor from $PRIMARY_GOMOD"
OLD_GO_VERSION=$(grep "^go " "$PRIMARY_GOMOD" | awk '{print $2}' || true)
[[ -z "$OLD_GO_VERSION" ]] && die "Cannot detect Go version from $PRIMARY_GOMOD"

info "Current: k8s.io/api $OLD_API_VERSION (k8s 1.${OLD_MINOR}), Go $OLD_GO_VERSION"
info "Target:  k8s.io/api $API_VERSION (k8s $K8S_FULL)"

# Idempotency check — verify ALL modules are at target, not just primary
if [[ "$OLD_MINOR" == "$K8S_MINOR" ]]; then
  stale_count=0
  while IFS= read -r gm; do
    for pkg in "k8s.io/api " "k8s.io/client-go " "k8s.io/apimachinery "; do
      ver=$(grep "$pkg" "$gm" 2>/dev/null | grep -v "=>" | head -1 | awk '{print $2}')
      if [[ -n "$ver" ]]; then
        minor=$(echo "$ver" | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')
        if [[ -n "$minor" && "$minor" != "$K8S_MINOR" ]]; then
          stale_count=$((stale_count + 1)); info "  Stale: $gm ($pkg at k8s 1.${minor})"
          break
        fi
      fi
    done
  done < <(find . -name "go.mod" -not -path "*/vendor/*" -exec grep -l "k8s.io/" {} \; 2>/dev/null)
  if [[ $stale_count -eq 0 ]]; then
    info "Already at k8s 1.${K8S_MINOR} — nothing to do"
    rm -rf "$REBASE_TMP"
    exit 0
  fi
  info "Primary module at k8s 1.${K8S_MINOR} but $stale_count module(s) still need rebasing — resuming"
fi

# Check required tools
MISSING=()
for tool in go git make curl sed grep; do
  command -v "$tool" &>/dev/null || MISSING+=("$tool")
done
[[ ${#MISSING[@]} -gt 0 ]] && die "Missing required tools: ${MISSING[*]}"

# Verify target version exists on Go module proxy
info "Checking Go module proxy for $API_VERSION..."
if ! curl -sf --retry 2 --connect-timeout 10 "https://proxy.golang.org/k8s.io/api/@v/${API_VERSION}.info" > /dev/null 2>&1; then
  die "k8s.io/api@${API_VERSION} not found on Go module proxy. Version may not be released yet."
fi
info "Target version confirmed on proxy"

# Check Go version — if too old, re-exec inside the official Go container
REQUIRED_GO=$(curl -sf --retry 2 --connect-timeout 10 "https://raw.githubusercontent.com/kubernetes/kubernetes/v${K8S_MAJOR}.${K8S_MINOR}.${K8S_PATCH}/go.mod" 2>/dev/null | grep "^go " | awk '{print $2}' || true)
[[ -n "$REQUIRED_GO" ]] && [[ ! "$REQUIRED_GO" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] && die "Unexpected Go version format from upstream: '$REQUIRED_GO'"
CURRENT_GO=$(go env GOVERSION 2>/dev/null | sed 's/go//' || echo "0.0")
GO_OK=1
if [[ -n "$REQUIRED_GO" ]]; then
  REQ_MINOR=$(echo "$REQUIRED_GO" | cut -d. -f2)
  CUR_MINOR=$(echo "$CURRENT_GO" | cut -d. -f2)
  [[ "$CUR_MINOR" -lt "$REQ_MINOR" ]] 2>/dev/null && GO_OK=0
fi

if [[ "$GO_OK" -eq 0 ]] && [[ "${K8S_REBASE_IN_CONTAINER:-}" != "1" ]]; then
  # Detect container runtime (podman or docker)
  CONTAINER_RT=""
  command -v podman &>/dev/null && CONTAINER_RT=podman
  [[ -z "$CONTAINER_RT" ]] && command -v docker &>/dev/null && CONTAINER_RT=docker
  if [[ -z "$CONTAINER_RT" ]]; then
    die "Go $REQUIRED_GO required for k8s $K8S_FULL but running Go $CURRENT_GO. Install Go $REQUIRED_GO, or install podman/docker for automatic containerized execution."
  fi

  GO_IMAGE="docker.io/library/golang:${REQUIRED_GO}"
  info "Go $CURRENT_GO < $REQUIRED_GO required — re-running inside $GO_IMAGE"

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
    bash "$SCRIPT_PATH" $([[ "$BUMP_TOOLS" == true ]] && echo "--bump-tools") "$VERSION_INPUT"
fi
info "Go version: $CURRENT_GO (>= ${REQUIRED_GO:-any} required)"

# Container setup: git safe.directory for mounted volumes
if [[ "${K8S_REBASE_IN_CONTAINER:-}" == "1" ]]; then
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=safe.directory
  export GIT_CONFIG_VALUE_0="$REPO_ROOT"
fi

# Clean working tree (ignore dirs created by containerized Go)
if [[ -n "$(git status --porcelain | grep -v "^?? \.rebase-tmp/" | grep -v "^?? \.config/" | grep -v "^?? \.cache/")" ]]; then
  die "Working tree is not clean. Commit or stash changes first."
fi

# Discover controller-runtime version — find the latest patch for the computed minor
# controller-runtime v0.N maps to k8s 1.(N+12):
# v0.22/k8s1.34, v0.23/k8s1.35, v0.24/k8s1.36, ...
CR_MINOR=$((K8S_MINOR - 12))
CR_VERSION=""
# Try patch versions from highest to lowest
for patch in 9 8 7 6 5 4 3 2 1 0; do
  candidate="v0.${CR_MINOR}.${patch}"
  if curl -sf --retry 2 --connect-timeout 10 "https://proxy.golang.org/sigs.k8s.io/controller-runtime/@v/${candidate}.info" > /dev/null 2>&1; then
    CR_VERSION="$candidate"
    break
  fi
done
if [[ -n "$CR_VERSION" ]]; then
  info "Controller-runtime: $CR_VERSION (formula + latest patch)"
else
  info "Controller-runtime: v0.${CR_MINOR}.x not on proxy — may not be released yet. Will use latest available."
fi

# Warn if not on the default branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || true)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || true)
if [[ -z "$CURRENT_BRANCH" ]]; then
  info "WARNING: detached HEAD — rebase should start from the default branch (master/main)"
elif [[ -n "$DEFAULT_BRANCH" && "$CURRENT_BRANCH" != "$DEFAULT_BRANCH" ]]; then
  info "WARNING: on '$CURRENT_BRANCH', not default branch '$DEFAULT_BRANCH' — rebase normally starts from '$DEFAULT_BRANCH'"
fi

# Create branch (append timestamp if name taken)
BRANCH_NAME="bump${K8S_MAJOR_MINOR}"
if git rev-parse --verify "$BRANCH_NAME" &>/dev/null; then
  BRANCH_NAME="bump${K8S_MAJOR_MINOR}-$(date +%Y%m%d%H%M%S)"
  info "bump${K8S_MAJOR_MINOR} already exists, using $BRANCH_NAME"
fi
git checkout -b "$BRANCH_NAME"
echo "$BRANCH_NAME" > "$REBASE_TMP/branch-name"
info "Created branch: $BRANCH_NAME"

# ── Derivation function ─────────────────────────────────────────────

derive_go_gets() {
  local gomod="$1"
  local cmds=()

  # Rule 1: version-locked (v{N}.{OLD_MINOR}.* → v{N}.{NEW_MINOR}.*)
  while IFS= read -r line; do
    local pkg ver_prefix
    pkg=$(echo "$line" | awk '{print $1}')
    ver_prefix=$(echo "$line" | awk '{print $2}' | grep -oE '^v[0-9]+' | sed 's/v//' || true)
    [[ -z "$ver_prefix" ]] && continue
    cmds+=("go get ${pkg}@v${ver_prefix}.${K8S_MINOR}.${K8S_PATCH}")
  done < <(grep -E "k8s\.io/|sigs\.k8s\.io/" "$gomod" | grep -v "=>" | grep -E "v[0-9]+\.${OLD_MINOR}\." | awk '{print $1, $2}' | sort -u)

  # Rule 2: controller-runtime
  if grep -q "controller-runtime" "$gomod"; then
    if [[ -n "$CR_VERSION" ]]; then
      cmds+=("go get sigs.k8s.io/controller-runtime@${CR_VERSION}")
    else
      cmds+=("go get sigs.k8s.io/controller-runtime")
    fi
  fi

  # Rule 3: everything else in k8s ecosystem
  # Filter out go.mod keywords (module, replace, require, exclude) and
  # the module's own name to avoid self-referencing go gets
  local own_module
  own_module=$(grep "^module " "$gomod" | awk '{print $2}')
  while IFS= read -r pkg; do
    # Skip go.mod keywords, controller-runtime (Rule 2), and self-references
    case "$pkg" in
      module|replace|require|exclude|"$own_module") continue ;;
    esac
    echo "$pkg" | grep -q "controller-runtime" && continue
    # Skip network-policy-api — it has its own versioning independent
    # of k8s releases. Bumping it can break conformance tests by
    # pulling in API renames the controller doesn't support yet.
    echo "$pkg" | grep -q "network-policy-api" && continue
    cmds+=("go get ${pkg}")
  done < <(grep -E "k8s\.io/|sigs\.k8s\.io/|github\.com/openshift/(api|client-go|library-go|build-machinery-go) " "$gomod" | \
           grep -v "=>" | \
           grep -vE "v[0-9]+\.${OLD_MINOR}\." | \
           awk '{print $1}' | sort -u)

  printf '%s\n' "${cmds[@]}"
}

# ── Phase 1: Module Dependency Updates ───────────────────────────────

rebase_module() {
  local module_dir="$1"
  local module_path="$module_dir"
  [[ "$module_path" == "." ]] && module_path=$(basename "$REPO_ROOT")
  local gomod="${REPO_ROOT}/${module_dir}/go.mod"

  [[ -f "$gomod" ]] || { info "No go.mod at $gomod, skipping"; return 0; }

  banner "Phase 1: Rebase $module_path"

  cd "$REPO_ROOT/$module_dir" || die "Cannot cd to $module_dir"

  local commands
  commands=$(derive_go_gets "$gomod")

  if [[ -z "$commands" ]]; then
    info "No k8s ecosystem packages found in $gomod"
    cd "$REPO_ROOT"
    return 0
  fi

  local num_cmds
  num_cmds=$(echo "$commands" | wc -l)
  info "Running $num_cmds go get commands (log: .rebase-tmp/go-get.log)..."
  local cmd_log="" cmd_num=0
  while IFS= read -r cmd; do
    cmd_num=$((cmd_num + 1))
    printf "\r:: [%d/%d] %s" "$cmd_num" "$num_cmds" "$(echo "$cmd" | awk '{print $2}' | sed 's/@.*//')"
    $cmd >> "$REBASE_TMP/go-get.log" 2>&1 || info "  WARNING: $cmd failed (see .rebase-tmp/go-get.log)"
    cmd_log+="$cmd"$'\n'
  done <<< "$commands"
  echo ""

  info "Running go mod tidy..."
  # k8s.io/kubernetes uses local replace directives for staging repos.
  # When bumped, go mod tidy may fail with "unknown revision v0.0.0"
  # for staging deps not yet in go.mod. Retry by resolving each.
  local tidy_attempts=0
  while ! go mod tidy 2>"${REBASE_TMP}/tidy.log"; do
    local missing_mod
    missing_mod=$(grep "unknown revision v0.0.0" "${REBASE_TMP}/tidy.log" | grep -oE 'k8s\.io/[a-z][-a-z]*' | head -1 || true)
    if [[ -z "$missing_mod" ]] || [[ $tidy_attempts -ge 10 ]]; then
      cat "${REBASE_TMP}/tidy.log" >&2
      die "go mod tidy failed in $(basename "$gomod" .mod)"
    fi
    info "  Resolving staging dep: ${missing_mod}@${API_VERSION}"
    go get "${missing_mod}@${API_VERSION}" 2>/dev/null || true
    tidy_attempts=$((tidy_attempts + 1))
  done

  # Align staging modules that tidy pulled in at a stale patch.
  # MVS resolves new transitive deps to minimum version (e.g.,
  # v0.36.0) rather than target patch (v0.36.2).
  local _skewed
  _skewed=$(grep -E '^\s+k8s\.io/' go.mod | grep -v "=>" | \
            grep "v0\.${K8S_MINOR}\." | grep -v "${API_VERSION}" | \
            grep -v 'kube-openapi' | grep -v 'k8s\.io/utils' | \
            awk '{print $1}' || true)
  if [[ -n "$_skewed" ]]; then
    info "Aligning staging modules to ${API_VERSION}..."
    while IFS= read -r _mod; do
      [[ -z "$_mod" ]] && continue
      if go get "${_mod}@${API_VERSION}" >> "$REBASE_TMP/go-get.log" 2>&1; then
        info "  ${_mod}@${API_VERSION}"
      else
        info "  WARNING: failed to bump ${_mod}@${API_VERSION}"
      fi
    done <<< "$_skewed"
    go mod tidy 2>/dev/null || true
  fi

  # k8s.io/kubernetes uses v1.x.x (not v0.x.x like staging modules).
  # The staging alignment above misses it. Re-pin if tidy reverted it.
  local _k8s_ver
  _k8s_ver=$(grep -E '^\s+k8s\.io/kubernetes\s' go.mod | grep -v "=>" | awk '{print $2}' || true)
  if [[ -n "$_k8s_ver" ]] && [[ "$_k8s_ver" != "v${K8S_MAJOR}.${K8S_MINOR}.${K8S_PATCH}" ]]; then
    info "Re-pinning k8s.io/kubernetes: ${_k8s_ver} → v${K8S_MAJOR}.${K8S_MINOR}.${K8S_PATCH}"
    go get "k8s.io/kubernetes@v${K8S_MAJOR}.${K8S_MINOR}.${K8S_PATCH}" >> "$REBASE_TMP/go-get.log" 2>&1 || true
    go mod tidy 2>/dev/null || true
  fi

  if [[ -d "vendor" ]]; then
    info "Running go mod vendor (log: .rebase-tmp/vendor.log)..."
    go mod vendor >> "$REBASE_TMP/vendor.log" 2>&1
    if [[ -x "$REPO_ROOT/go-controller/hack/verify-go-mod-vendor.sh" ]] && [[ "$module_dir" == "go-controller" ]]; then
      info "Verifying vendor..."
      "$REPO_ROOT/go-controller/hack/verify-go-mod-vendor.sh" || info "WARNING: vendor verification failed — run hack/verify-go-mod-vendor.sh to see details"
    fi
  fi

  cd "$REPO_ROOT"

  # Commit if there are changes
  if [[ -n "$(git status --porcelain -- "$module_dir")" ]]; then
    git add "$module_dir"
    if git commit -s --trailer "$AI_TRAILER" -m "$(cat <<EOF
$(format_msg "deps" "Rebase ${module_path} to k8s ${K8S_MAJOR_MINOR}")

${cmd_log}go mod tidy
EOF
)"; then
      info "Committed: Rebase ${module_path} to k8s ${K8S_MAJOR_MINOR}"
    else
      info "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  else
    info "No changes in $module_path (already up to date)"
  fi
}

banner "Phase 1: Module Dependency Updates"

# Auto-detect all go.mod files with k8s.io deps, rebase non-vendored first
VENDOR_MODULES=()
NONVENDOR_MODULES=()
while IFS= read -r gomod; do
  mod_dir=$(dirname "$gomod")
  [[ "$mod_dir" == "." ]] && mod_dir="."
  if [[ -d "$REPO_ROOT/$mod_dir/vendor" ]]; then
    VENDOR_MODULES+=("$mod_dir")
  else
    NONVENDOR_MODULES+=("$mod_dir")
  fi
done < <(find . -name "go.mod" -not -path "*/vendor/*" -exec grep -l "k8s.io/" {} \; | sed 's|^\./||' | sort)

# Non-vendored modules first (lighter, faster feedback)
for mod in "${NONVENDOR_MODULES[@]}"; do
  rebase_module "$mod"
done
# Vendored modules last (heavier, go mod vendor is slow)
for mod in "${VENDOR_MODULES[@]}"; do
  rebase_module "$mod"
done

# Re-tidy modules that depend on sibling modules via replace directives
for gomod in $(find . -name "go.mod" -not -path "*/vendor/*"); do
  mod_dir=$(dirname "$gomod" | sed 's|^\./||')
  if grep -q '\.\./.*go-controller\|\.\./' "$gomod" 2>/dev/null; then
    banner "Phase 1: Re-tidy $mod_dir (replace directive sync)"
    (cd "$REPO_ROOT/$mod_dir" && go mod tidy) || info "WARNING: go mod tidy failed in $mod_dir — continuing"
    if [[ -n "$(git status --porcelain -- "$mod_dir")" ]]; then
      git add "$mod_dir"
      if git commit -s --trailer "$AI_TRAILER" -m "$(format_msg "deps" "Sync ${mod_dir} go.mod after dependency rebase")"; then
        info "Committed: Sync ${mod_dir} go.mod after dependency rebase"
      else
        info "WARNING: git commit failed — unstaging to prevent contamination"
        git reset HEAD 2>/dev/null || true
      fi
    fi
  fi
done

# ── Phase 2: Code Generation ────────────────────────────────────────

# Find codegen script (common locations)
CODEGEN_SCRIPT=""
for candidate in go-controller/hack/update-codegen.sh hack/update-codegen.sh; do
  if [[ -f "$REPO_ROOT/$candidate" ]]; then
    CODEGEN_SCRIPT="$REPO_ROOT/$candidate"
    break
  fi
done

# Save CRD hand-edits before any codegen (restored after)
save_crd_metadata

if [[ -n "$CODEGEN_SCRIPT" ]]; then
  banner "Phase 2: Code Generation"

  # Update code-generator version pin (handles both printf %s and explicit tool names)
  sed -i -E "s|(code-generator/cmd/[^@]+)@v0\.[0-9]+\.[0-9]+|\1@${API_VERSION}|g" "$CODEGEN_SCRIPT"
  info "Updated code-generator version to ${API_VERSION}"

  # Run codegen — try common make targets, auto-retry on dropped flags
  CODEGEN_DIR=$(dirname "$(dirname "$CODEGEN_SCRIPT")")
  CODEGEN_RAN=0
  CODEGEN_FAILED=0
  CODEGEN_LOG="$REBASE_TMP/codegen.log"
  CODEGEN_MSG="$(format_msg "codegen" "Update codegen for k8s ${K8S_MAJOR_MINOR}")"

  run_codegen() {
    for target in codegen generate update-codegen; do
      if make -n -C "$CODEGEN_DIR" "$target" &>/dev/null; then
        info "Running make $target in $CODEGEN_DIR..."
        make -C "$CODEGEN_DIR" "$target" > "$CODEGEN_LOG" 2>&1 && return 0
        return 1
      fi
    done
    info "No codegen make target found, running script directly..."
    bash "$CODEGEN_SCRIPT" > "$CODEGEN_LOG" 2>&1
  }

  if run_codegen; then
    CODEGEN_RAN=1
  else
    info "WARNING: codegen failed — checking for auto-fixable errors"
    # Auto-fix dropped flags and retry
    if grep -q 'unknown flag\|flag provided but not defined' "$CODEGEN_LOG" 2>/dev/null; then
      bad_flag=$(grep -oE '(unknown flag|flag provided but not defined): -+[a-zA-Z0-9_-]+' "$CODEGEN_LOG" | head -1 | sed 's/.*: -*//' || true)
      if [[ -n "$bad_flag" ]] && grep -q "\-\-${bad_flag}" "$CODEGEN_SCRIPT"; then
        info "Removing dropped flag --${bad_flag} from codegen script and retrying"
        sed -i "/^[[:space:]]*--${bad_flag}/d" "$CODEGEN_SCRIPT"
        if run_codegen; then
          CODEGEN_RAN=1
          CODEGEN_MSG="$(format_msg "codegen" "Fix codegen for k8s ${K8S_MAJOR_MINOR}: remove dropped --${bad_flag} flag")"
        fi
      fi
    fi
    [[ "$CODEGEN_RAN" -eq 0 ]] && CODEGEN_FAILED=1
  fi

  # Commit codegen output immediately so progress isn't lost if
  # the script is killed during mockery or later steps.
  cd "$REPO_ROOT"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    if git commit -s --trailer "$AI_TRAILER" -m "$CODEGEN_MSG"; then
      info "Committed: $CODEGEN_MSG"
    else
      info "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  fi

  # Regenerate mocks if codegen deleted them
  if [[ "$CODEGEN_RAN" -eq 1 ]] && [[ -f "$CODEGEN_DIR/.mockery.yaml" ]]; then
    if ! find "$CODEGEN_DIR/pkg/crd" -path "*/mocks/*.go" 2>/dev/null | grep -q .; then
      info "Codegen deleted mock files — running mockery..."
      make -C "$CODEGEN_DIR" mocksgen 2>/dev/null || info "WARNING: mockery failed — the agent will regenerate mocks"
    fi
  fi

  restore_crd_metadata
  cd "$REPO_ROOT"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    if git commit -s --trailer "$AI_TRAILER" -m "$(format_msg "codegen" "Regenerate mocks and codegen output for k8s ${K8S_MAJOR_MINOR}")"; then
      info "Committed: Post-codegen cleanup"
    else
      info "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  fi

  if [[ "$CODEGEN_FAILED" -eq 1 ]]; then
    echo "## CODEGEN FAILURE" >> "$REBASE_TMP/summary.txt"
    tail -10 "$CODEGEN_LOG" >> "$REBASE_TMP/summary.txt"
    echo "Fix the codegen script (e.g. removed flags) and re-run codegen." >> "$REBASE_TMP/summary.txt"
    echo "" >> "$REBASE_TMP/summary.txt"
  fi
elif CODEGEN_MAKEFILE=$(
    for mf in "$REPO_ROOT/Makefile" "$REPO_ROOT/$(dirname "$PRIMARY_GOMOD")/Makefile"; do
      grep -qE "^(generate|manifests):" "$mf" 2>/dev/null && echo "$mf" && break
    done
  ) && [[ -n "$CODEGEN_MAKEFILE" ]]; then
  CODEGEN_MAKEDIR=$(dirname "$CODEGEN_MAKEFILE")
  banner "Phase 2: Code Generation (make)"

  # controller-gen projects use make generate/manifests instead of
  # hack/update-codegen.sh. Run both if available.
  CODEGEN_RAN=0
  CODEGEN_FAILED=0
  CODEGEN_LOG="$REBASE_TMP/codegen.log"
  for target in generate manifests; do
    if grep -q "^${target}:" "$CODEGEN_MAKEFILE"; then
      info "Running make $target in $CODEGEN_MAKEDIR..."
      if make -C "$CODEGEN_MAKEDIR" "$target" >> "$CODEGEN_LOG" 2>&1; then
        CODEGEN_RAN=1
      else
        info "WARNING: make $target failed — the agent will fix"
        CODEGEN_FAILED=1
      fi
    fi
  done
  restore_crd_metadata

  cd "$REPO_ROOT"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    if git commit -s --trailer "$AI_TRAILER" -m "$(format_msg "codegen" "Regenerate code and manifests for k8s ${K8S_MAJOR_MINOR}")"; then
      info "Committed: Regenerate code and manifests for k8s ${K8S_MAJOR_MINOR}"
    else
      info "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  fi

  if [[ "$CODEGEN_FAILED" -eq 1 ]]; then
    echo "## CODEGEN FAILURE" >> "$REBASE_TMP/summary.txt"
    tail -5 "$CODEGEN_LOG" >> "$REBASE_TMP/summary.txt"
    echo "" >> "$REBASE_TMP/summary.txt"
  fi
else
  info "No codegen script found, skipping Phase 2"
fi
rm -rf "$REBASE_TMP/crd-pre-codegen"

# ── Phase 3: Version Reference Updates ───────────────────────────────

banner "Phase 3: Version Reference Updates"

NEW_K8S_FULL="${K8S_FULL}"
OLD_SHORT="${K8S_MAJOR}.${OLD_MINOR}"
NEW_SHORT="${K8S_MAJOR_MINOR}"
CHANGED_FILES=""

# Pass 1: v-prefixed versions in CI, scripts, docs (v1.35.0, v1.35)
# Two-stage sed: patch form first (v1.35.X → v1.36.0), then bare (v1.35 → v1.36)
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  sed -i -E "s|v${K8S_MAJOR}\.${OLD_MINOR}\.[0-9]+|${NEW_K8S_FULL}|g; s|v${K8S_MAJOR}\.${OLD_MINOR}\b|v${NEW_SHORT}|g" "$file"
  CHANGED_FILES+="$file"$'\n'
  info "  Updated: $file"
done < <(grep -rln -E "v${K8S_MAJOR}\.${OLD_MINOR}(\.[0-9]+)?\b" \
  --include="*.yml" --include="*.yaml" --include="*.sh" \
  --include="*.md" --include="Makefile*" --include="Dockerfile*" . \
  | grep -v vendor | grep -v "/\.git/" | grep -v go.mod || true)

# Pass 2: bare version in doc prose (1.35 without v-prefix)
# Uses perl lookbehind/lookahead to avoid corrupting IP addresses
# (10.244.1.35), compound versions (openshift-4.1.35), and patch
# versions (1.35.2) while still replacing standalone bare versions.
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  perl -pi -e "s/(?<!\\d\\.)\b${OLD_SHORT//./\\.}\b(?!\\.\\d)/${NEW_SHORT}/g" "$file"
  CHANGED_FILES+="$file"$'\n'
  info "  Updated (short): $file"
done < <(grep -rln "\b${OLD_SHORT}\b" --include="*.md" docs/ 2>/dev/null | grep -v vendor || true)

# Go version update (if changed)
NEW_GO_VERSION=$(grep "^go " "$PRIMARY_GOMOD" | awk '{print $2}' || true)
if [[ -n "$NEW_GO_VERSION" ]] && [[ "$OLD_GO_VERSION" != "$NEW_GO_VERSION" ]]; then
  info "Go version changed: $OLD_GO_VERSION → $NEW_GO_VERSION"
  OLD_GO_SHORT=$(echo "$OLD_GO_VERSION" | grep -oE '[0-9]+\.[0-9]+')
  NEW_GO_SHORT=$(echo "$NEW_GO_VERSION" | grep -oE '[0-9]+\.[0-9]+')

  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    sed -i \
      -e "s|golang:${OLD_GO_SHORT}|golang:${NEW_GO_SHORT}|g" \
      -e "s|golang-${OLD_GO_SHORT}|golang-${NEW_GO_SHORT}|g" \
      -e "s|GO_VERSION ?= ${OLD_GO_SHORT}|GO_VERSION ?= ${NEW_GO_SHORT}|g" \
      -e "s|GOLANG_VERSION ?= ${OLD_GO_SHORT}|GOLANG_VERSION ?= ${NEW_GO_SHORT}|g" \
      -e "s|go-version: \[${OLD_GO_SHORT}|go-version: [${NEW_GO_SHORT}|g" \
      -e "s|go-version: ${OLD_GO_SHORT}|go-version: ${NEW_GO_SHORT}|g" \
      -e "s|GO_VERSION: \"${OLD_GO_SHORT}\"|GO_VERSION: \"${NEW_GO_SHORT}\"|g" \
      "$file"
    CHANGED_FILES+="$file"$'\n'
    info "  Updated Go version: $file"
  done < <(grep -rlnE "golang[:-]${OLD_GO_SHORT}|GO_VERSION.{0,5}${OLD_GO_SHORT}|GOLANG_VERSION.{0,5}${OLD_GO_SHORT}|go-version:.{0,3}${OLD_GO_SHORT}" \
    --include="*.yml" --include="*.yaml" --include="Makefile*" \
    --include="Dockerfile*" . \
    | grep -v vendor | grep -v "/\.git/" | grep -v go.mod || true)

  # Bump golangci-lint version in lint scripts when Go version changes.
  # Skip when Go >= 1.26 and project uses v1: the autofix script handles
  # the full v1→v2 transition (lint.sh + Makefile + import paths).
  # Bumping v1 here would create an intermediate commit that autofix
  # immediately supersedes — touching the same files in two commits.
  _skip_lint_bump=false
  _go_minor=$(echo "$NEW_GO_SHORT" | cut -d. -f2)
  if [[ -n "$_go_minor" ]] && [[ "$_go_minor" -ge 26 ]] 2>/dev/null; then
    _any_v1=false
    while IFS= read -r _ls; do
      [[ -z "$_ls" ]] && continue
      grep -qE 'VERSION=v1\.' "$_ls" 2>/dev/null && _any_v1=true && break
    done < <(grep -rln "golangci-lint" --include="*.sh" . | grep -v vendor | grep -v "/\.git/" || true)
    if [[ "$_any_v1" == true ]]; then
      _skip_lint_bump=true
      info "  golangci-lint v1→v2 migration deferred to autofix (Go >= 1.26)"
    fi
  fi

  if [[ "$_skip_lint_bump" == false ]]; then
  LATEST_LINT=$(curl -sf --retry 2 --connect-timeout 10 "https://api.github.com/repos/golangci/golangci-lint/releases/latest" 2>/dev/null | grep -oE '"tag_name": "[^"]+"' | sed 's/"tag_name": "//;s/"//' || true)
  if [[ -z "$LATEST_LINT" ]]; then
    info "  WARNING: Could not fetch latest golangci-lint version (API rate limited?). Lint version not bumped."
  fi
  if [[ -n "$LATEST_LINT" ]]; then
    LATEST_LINT_V1=""
    if [[ "$LATEST_LINT" == v2.* ]]; then
      LATEST_LINT_V1=$(curl -sf --retry 2 --connect-timeout 10 "https://api.github.com/repos/golangci/golangci-lint/releases?per_page=50" 2>/dev/null | grep -oE '"tag_name": "v1\.[^"]+"' | head -1 | sed 's/"tag_name": "//;s/"//' || true)
    fi
    while IFS= read -r lintscript; do
      [[ -z "$lintscript" ]] && continue
      OLD_LINT=$(grep -oE 'VERSION=v[0-9]+\.[0-9]+\.[0-9]+' "$lintscript" | head -1 | sed 's/VERSION=//' || true)
      if [[ -n "$OLD_LINT" ]] && [[ "$OLD_LINT" != "$LATEST_LINT" ]]; then
        lint_target="$LATEST_LINT"
        if [[ "$OLD_LINT" == v1.* ]] && [[ "$LATEST_LINT" == v2.* ]]; then
          lint_target="${LATEST_LINT_V1:-$OLD_LINT}"
        fi
        if [[ "$OLD_LINT" != "$lint_target" ]]; then
          old_lint_bare="${OLD_LINT#v}"
          new_lint_bare="${lint_target#v}"
          sed -i "s|${OLD_LINT}|${lint_target}|g; s|\b${old_lint_bare}\b|${new_lint_bare}|g" "$lintscript"
          CHANGED_FILES+="$lintscript"$'\n'
          info "  Updated golangci-lint: $OLD_LINT → $lint_target in $lintscript"
        fi
      fi
    done < <(grep -rln "golangci-lint" --include="*.sh" . | grep -v vendor | grep -v "/\.git/" || true)
    while IFS= read -r mkfile; do
      [[ -z "$mkfile" ]] && continue
      OLD_MK_LINT=$(grep -oE 'GOLANGCI_LINT_VERSION\s*[:?]?=\s*v[0-9]+\.[0-9]+\.[0-9]+' "$mkfile" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
      [[ -z "$OLD_MK_LINT" ]] && continue
      target_lint="$LATEST_LINT"
      if [[ "$OLD_MK_LINT" == v1.* ]] && [[ "$LATEST_LINT" == v2.* ]]; then
        target_lint="${LATEST_LINT_V1:-$OLD_MK_LINT}"
      fi
      if [[ "$OLD_MK_LINT" != "$target_lint" ]]; then
        sed -i "s|${OLD_MK_LINT}|${target_lint}|g" "$mkfile"
        CHANGED_FILES+="$mkfile"$'\n'
        info "  Updated golangci-lint: $OLD_MK_LINT → $target_lint in $mkfile"
      fi
    done < <(grep -rln "GOLANGCI_LINT_VERSION" --include="Makefile*" . | grep -v vendor | grep -v "/\.git/" || true)
  fi
  fi

  # Reconcile Dockerfile ARG defaults with the new Go version.
  # Some Dockerfiles have stale GOLANG_VERSION defaults from prior
  # rebases that the OLD→NEW sed misses.
  while IFS= read -r df; do
    [[ -z "$df" ]] && continue
    sed -i "s|ARG GOLANG_VERSION=[0-9.]\+|ARG GOLANG_VERSION=${NEW_GO_SHORT}|g" "$df"
    CHANGED_FILES+="$df"$'\n'
    info "  Reconciled Dockerfile Go version: $df"
  done < <(grep -rln "ARG GOLANG_VERSION=" --include="Dockerfile*" . | grep -v vendor | grep -v "/\.git/" || true)

  # Update OCP version in CI builder image tags if we can detect
  # the repo's target OCP version from openshift/release configs.
  # Go 1.26 images may only exist for openshift-5.0, not 4.22.
  if grep -q "golang-${NEW_GO_SHORT}.*openshift-" .ci-operator.yaml 2>/dev/null; then
    old_ocp=$(grep -oE 'openshift-[0-9.]+' .ci-operator.yaml | head -1 | sed 's/openshift-//' || true)
    repo_name=$(basename "$REPO_ROOT")
    repo_org=$(basename "$(dirname "$REPO_ROOT")")
    target_ocp=""
    # Detect OCP target from openshift/release ci-operator config
    for branch in master main; do
      target_ocp=$(curl -sf --retry 2 --connect-timeout 10 "https://raw.githubusercontent.com/openshift/release/master/ci-operator/config/${repo_org}/${repo_name}/${repo_org}-${repo_name}-${branch}.yaml" 2>/dev/null | grep 'name: "' | tail -1 | grep -oE '[0-9]+\.[0-9]+' || true)
      [[ -n "$target_ocp" ]] && break
    done
    if [[ -n "$target_ocp" ]]; then
      # Update .ci-operator.yaml if needed
      if [[ "$old_ocp" != "$target_ocp" ]]; then
        info "  Updating OCP version in CI tags: openshift-${old_ocp} → openshift-${target_ocp}"
        sed -i "s|openshift-${old_ocp}|openshift-${target_ocp}|g" .ci-operator.yaml && CHANGED_FILES+=".ci-operator.yaml"$'\n'
      fi
      # Also update ANY Dockerfile still referencing a stale OCP stream.
      # Handles both patterns: openshift-X.Y (builder tag) and ocp/X.Y: (base image)
      for ci_file in $(find . -maxdepth 2 -name "Dockerfile*" -not -path "*/vendor/*" | sed 's|^\./||' | sort); do
        _fixed=0
        # Skip legacy Dockerfiles with Go versions far behind the target.
        # Dockerfile.rhel7 with golang-1.19 should not get openshift-5.0 tags.
        _df_go=$(grep -oE 'golang-[0-9]+\.[0-9]+' "$ci_file" 2>/dev/null | head -1 | sed 's/golang-//' || true)
        if [[ -n "$_df_go" ]]; then
          _df_minor=$(echo "$_df_go" | cut -d. -f2)
          _target_minor=$(echo "$NEW_GO_SHORT" | cut -d. -f2)
          if [[ -n "$_df_minor" ]] && [[ -n "$_target_minor" ]] && (( _target_minor - _df_minor > 2 )) 2>/dev/null; then
            info "  Skipping legacy $ci_file (Go $_df_go, target $NEW_GO_SHORT)"
            continue
          fi
        fi
        # Pattern 1: openshift-X.Y (builder image tag suffix)
        if grep -qE "openshift-[0-9.]+" "$ci_file" && ! grep -q "openshift-${target_ocp}" "$ci_file"; then
          stale_ocp=$(grep -oE 'openshift-[0-9.]+' "$ci_file" | head -1 | sed 's/openshift-//')
          sed -i "s|openshift-${stale_ocp}|openshift-${target_ocp}|g" "$ci_file"
          _fixed=1
        fi
        # Pattern 2: ocp/X.Y: (base image reference)
        if grep -qE "ocp/[0-9.]+:" "$ci_file" && ! grep -q "ocp/${target_ocp}:" "$ci_file"; then
          stale_base=$(grep -oE 'ocp/[0-9.]+:' "$ci_file" | head -1 | sed 's|ocp/||;s|:||')
          sed -i "s|ocp/${stale_base}:|ocp/${target_ocp}:|g" "$ci_file"
          _fixed=1
        fi
        [[ "$_fixed" -eq 1 ]] && info "  Updated OCP stream in $ci_file → ${target_ocp}" && CHANGED_FILES+="$ci_file"$'\n'
      done
    else
      info "  NOTE: CI builder image uses golang-${NEW_GO_SHORT}-openshift-${old_ocp}."
      info "  Could not detect OCP target — check openshift/release CI configs for the correct stream."
    fi
  fi
fi

# Reconcile ENVTEST_K8S_VERSION (kubebuilder test binary version).
# Runs regardless of Go version change — it tracks k8s version.
if grep -q "ENVTEST_K8S_VERSION" "$REPO_ROOT/Makefile" 2>/dev/null; then
  sed -i -E "s|(ENVTEST_K8S_VERSION[[:space:]]*[:?]?=[[:space:]]*)[0-9]+\.[0-9]+[.x0-9]*|\1${K8S_MAJOR}.${K8S_MINOR}|" "$REPO_ROOT/Makefile"
  CHANGED_FILES+="Makefile"$'\n'
  info "  Reconciled ENVTEST_K8S_VERSION to ${K8S_MAJOR}.${K8S_MINOR}"
fi

# Reconcile setup-envtest release branch (tracks controller-runtime).
if grep -q "setup-envtest@release-" "$REPO_ROOT/Makefile" 2>/dev/null; then
  sed -i "s|setup-envtest@release-[0-9.]*|setup-envtest@release-0.${CR_MINOR}|g" "$REPO_ROOT/Makefile"
  CHANGED_FILES+="Makefile"$'\n'
  info "  Reconciled setup-envtest to release-0.${CR_MINOR}"
fi

cd "$REPO_ROOT" || exit 1
# Add only the files we modified (more precise than git add -A)
CHANGED_FILES=$(echo "$CHANGED_FILES" | grep -v '^$' | sort -u || true)
if [[ -n "$CHANGED_FILES" ]]; then
  echo "$CHANGED_FILES" | while IFS= read -r f; do
    [[ -n "$f" ]] && git add "$f" 2>/dev/null || true
  done
  if [[ -n "$(git status --porcelain)" ]]; then
    if git commit -s --trailer "$AI_TRAILER" -m "$(cat <<EOF
$(format_msg "ci" "Update version references for k8s ${K8S_MAJOR_MINOR}")

${CHANGED_FILES}
EOF
)"; then
      info "Committed: Update version references for k8s ${K8S_MAJOR_MINOR}"
    else
      info "WARNING: git commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  fi
fi

# ── Opportunistic tooling bumps (--bump-tools only) ─────────────────
# These are not part of the k8s rebase itself but some repos (e.g.,
# ovn-kubernetes-mcp) bundle test-infra version bumps with rebases.
# Opt-in via --bump-tools. Guarded by var existence — most repos skip.
# Committed separately from version-refs to keep k8s changes distinct.

if [[ "$BUMP_TOOLS" == true ]]; then

TOOL_CHANGED_FILES=""

# ── A. Sync GINKGO_VERSION from go.mod ──────────────────────────────
# Consistency check — keeps Makefile in sync with go.mod, not a latest-bump.
if grep -qE 'GINKGO_VERSION\s*[:?]?=' "$REPO_ROOT/Makefile" 2>/dev/null; then
  _gomod_ginkgo=$(grep 'onsi/ginkgo/v2' "$PRIMARY_GOMOD" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  _mk_ginkgo=$(grep -oE 'GINKGO_VERSION\s*[:?]?=\s*v[0-9]+\.[0-9]+\.[0-9]+' "$REPO_ROOT/Makefile" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [[ -n "$_gomod_ginkgo" ]] && [[ -n "$_mk_ginkgo" ]] && [[ "$_gomod_ginkgo" != "$_mk_ginkgo" ]]; then
    sed -i -E "s|(GINKGO_VERSION\s*[:?]?=\s*)v[0-9]+\.[0-9]+\.[0-9]+|\1${_gomod_ginkgo}|" "$REPO_ROOT/Makefile"
    TOOL_CHANGED_FILES+="Makefile"$'\n'
    info "  Synced GINKGO_VERSION: $_mk_ginkgo → $_gomod_ginkgo (from go.mod)"
  fi
fi

# ── B. Bump Node.js and NPM to latest release ──────────────────────
# Only repos with Node.js e2e tooling (NODE_VERSION in Makefile).
# Uses latest (Current or LTS) since --bump-tools already signals
# "bump everything." Repos wanting LTS-only can pin manually.
if grep -qE 'NODE_VERSION\s*[:?]?=' "$REPO_ROOT/Makefile" 2>/dev/null; then
  _node_info=$(curl -sf --retry 2 --connect-timeout 10 "https://nodejs.org/dist/index.json" 2>/dev/null \
    | tr '{}' '\n' | grep '"version"' | head -1 || true)
  _latest_node=$(echo "$_node_info" | grep -oE '"version":"v[^"]+"' | sed 's/"version":"v//;s/"//' || true)
  _mk_node=$(grep -oE 'NODE_VERSION\s*[:?]?=\s*[0-9]+\.[0-9]+\.[0-9]+' "$REPO_ROOT/Makefile" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [[ -n "$_latest_node" ]] && [[ -n "$_mk_node" ]] && [[ "$_latest_node" != "$_mk_node" ]]; then
    sed -i -E "s|(NODE_VERSION\s*[:?]?=\s*)[0-9]+\.[0-9]+\.[0-9]+|\1${_latest_node}|" "$REPO_ROOT/Makefile"
    TOOL_CHANGED_FILES+="Makefile"$'\n'
    info "  Bumped NODE_VERSION: $_mk_node → $_latest_node"
  fi
  # NPM: fetch latest from registry (repos install npm independently
  # via npm install -g npm@VERSION, not the Node-bundled version).
  _latest_npm=$(curl -sf --retry 2 --connect-timeout 10 "https://registry.npmjs.org/npm/latest" 2>/dev/null | grep -oE '"version":"[^"]+"' | head -1 | sed 's/"version":"//;s/"//' || true)
  if [[ -n "$_latest_npm" ]]; then
    _mk_npm=$(grep -oE 'NPM_VERSION\s*[:?]?=\s*[0-9]+\.[0-9]+\.[0-9]+' "$REPO_ROOT/Makefile" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
    if [[ -n "$_mk_npm" ]] && [[ "$_latest_npm" != "$_mk_npm" ]]; then
      sed -i -E "s|(NPM_VERSION\s*[:?]?=\s*)[0-9]+\.[0-9]+\.[0-9]+|\1${_latest_npm}|" "$REPO_ROOT/Makefile"
      TOOL_CHANGED_FILES+="Makefile"$'\n'
      info "  Bumped NPM_VERSION: $_mk_npm → $_latest_npm"
    fi
  fi
fi

# ── C. Bump NVM_VERSION to latest release ───────────────────────────
if grep -qE 'NVM_VERSION\s*[:?]?=' "$REPO_ROOT/Makefile" 2>/dev/null; then
  _latest_nvm=$(gh api repos/nvm-sh/nvm/releases/latest --jq '.tag_name' 2>/dev/null | sed 's/^v//' || true)
  _mk_nvm=$(grep -oE 'NVM_VERSION\s*[:?]?=\s*[0-9]+\.[0-9]+\.[0-9]+' "$REPO_ROOT/Makefile" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [[ -n "$_latest_nvm" ]] && [[ -n "$_mk_nvm" ]] && [[ "$_latest_nvm" != "$_mk_nvm" ]]; then
    sed -i -E "s|(NVM_VERSION\s*[:?]?=\s*)[0-9]+\.[0-9]+\.[0-9]+|\1${_latest_nvm}|" "$REPO_ROOT/Makefile"
    TOOL_CHANGED_FILES+="Makefile"$'\n'
    info "  Bumped NVM_VERSION: $_mk_nvm → $_latest_nvm"
  fi
fi

# Non-k8s Go module bumps (go-sdk, ginkgo, gomega, etc.) are handled
# by the agent in Step 4d of SKILL.md, not by this script. Go module
# bumps require judgment (which deps to skip, verify k8s pins after
# tidy) that a deterministic script cannot safely provide.

# ── Commit tool bumps separately ────────────────────────────────────
cd "$REPO_ROOT" || exit 1
TOOL_CHANGED_FILES=$(echo "$TOOL_CHANGED_FILES" | grep -v '^$' | sort -u || true)
if [[ -n "$TOOL_CHANGED_FILES" ]]; then
  echo "$TOOL_CHANGED_FILES" | while IFS= read -r f; do
    [[ -n "$f" ]] && git add "$f" 2>/dev/null || true
  done
  if [[ -n "$(git status --porcelain)" ]]; then
    if git commit -s --trailer "$AI_TRAILER" -m "$(cat <<EOF
$(format_msg "deps" "Bump non-k8s tooling versions")

${TOOL_CHANGED_FILES}
EOF
)"; then
      info "Committed: Bump non-k8s tooling versions"
    else
      info "WARNING: tool bump commit failed — unstaging to prevent contamination"
      git reset HEAD 2>/dev/null || true
    fi
  fi
fi

fi # end --bump-tools

# ── Phase 3b: Detect new feature gates (info only) ────────────────
# Scans vendored feature gate definitions for new default-true gates.
# The autofix handles disabling via GATE_DEPS —
# this is informational logging only.

GATE_RANGE=$(seq $((OLD_MINOR + 1)) "$K8S_MINOR" | paste -sd'|')
FEATURE_FILES=$(find . -path "*/k8s.io/*/features/*features*.go" -not -path "*/.git/*" -not -path "*/testdata/*" 2>/dev/null | sort)
NEW_GATES=()

if [[ -n "$FEATURE_FILES" ]]; then
  while IFS= read -r gate; do
    [[ -z "$gate" ]] && continue
    NEW_GATES+=("$gate")
  done < <(
    for _ff in $FEATURE_FILES; do
      awk '
        /^\t+[A-Z][a-zA-Z0-9]*: \{/ { gsub(/:.*/, "", $1); gate = $1 }
        /^\t+[a-z].*: \{/ { gate = "" }
        !/\/\// && / Default: true/ && /MustParse\("1\.('"$GATE_RANGE"')"\)/ { if (gate != "") print gate }
      ' "$_ff"
    done | sort -u)
fi

if [[ ${#NEW_GATES[@]} -gt 0 ]]; then
  info "New default-true feature gates (1.${OLD_MINOR}→1.${K8S_MINOR}): ${NEW_GATES[*]}"
fi

# ── Summary ──────────────────────────────────────────────────────────

banner "Phases 0-3 Complete"
echo "Branch:    $BRANCH_NAME"
echo "Target:    k8s $K8S_FULL (API $API_VERSION)"
echo "From:      k8s 1.${OLD_MINOR} (API $OLD_API_VERSION)"
echo "Go:        $OLD_GO_VERSION → $NEW_GO_VERSION"
echo "CR:        ${CR_VERSION:-latest}"
echo "Commits:   $(git rev-list "${BRANCH_NAME}@{upstream}..HEAD" --count 2>/dev/null || git rev-list master..HEAD --count 2>/dev/null || git rev-list main..HEAD --count 2>/dev/null || echo '?')"
if [[ ${#NEW_GATES[@]} -gt 0 ]]; then
  echo "New gates: ${NEW_GATES[*]}"
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "WARNING:   uncommitted changes exist (git commit may have failed in container)"
fi
echo ""
echo "RESULT: EXIT 2 — mechanical rebase done, proceed to validation"
echo "EXIT 2" > "$REBASE_TMP/step1-result.txt"
exit 2
