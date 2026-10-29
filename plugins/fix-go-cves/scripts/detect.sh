#!/usr/bin/env bash
# Detect repository configuration for CVE fixing and optionally set up fix branch.
# Usage: detect.sh [repo] [branch] [--setup-branch]
# Prints state file path as last line of stdout.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

# --- Argument parsing (order-independent) ---
REPO=""
BRANCH=""
SETUP_BRANCH=false
# Registry resolution order: $CVE_FIX_REPOS → XDG config → in-repo. The shipped
# example is documentation, never an executable registry.
# repos.yaml is git-ignored so per-user paths and org names stay out of version control.
if [[ -n "${CVE_FIX_REPOS:-}" ]]; then
  [[ -f "$CVE_FIX_REPOS" ]] || die "CVE_FIX_REPOS is set but file not found: $CVE_FIX_REPOS"
  REPOS_YAML="$CVE_FIX_REPOS"
elif [[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/cve-fix/repos.yaml" ]]; then
  REPOS_YAML="${XDG_CONFIG_HOME:-$HOME/.config}/cve-fix/repos.yaml"
elif [[ -f "$SCRIPT_DIR/../repos.yaml" ]]; then
  REPOS_YAML="$SCRIPT_DIR/../repos.yaml"
else
  REPOS_YAML=""
fi
if [[ -n "$REPOS_YAML" ]]; then
  python3 "$SCRIPT_DIR/read-config.py" repos-list "$REPOS_YAML" >/dev/null || \
    die "Invalid repository registry: $REPOS_YAML"
fi

# Resolve repository arguments before classifying branches so an arbitrary
# branch can precede its repository, independent of the caller's current repo.
BRANCH_ARGS=()
for arg in "$@"; do
  case "$arg" in
    "") ;;  # an omitted optional argument passed as an empty string
    --setup-branch) SETUP_BRANCH=true ;;
    *)
      arg="${arg/#\~/$HOME}"
      if [[ "$arg" == /* ]]; then
        [[ -n "$REPO" ]] && die "Multiple repositories specified"
        REPO="$arg"
      elif [[ -n "$REPOS_YAML" ]] && \
           _path=$(python3 "$SCRIPT_DIR/read-config.py" repo-path "$REPOS_YAML" "$arg" 2>/dev/null) && \
           [[ -n "$_path" ]]; then
        [[ -n "$REPO" ]] && die "Multiple repositories specified"
        REPO="${_path/#\~/$HOME}"
      else
        BRANCH_ARGS+=("$arg")
      fi
      ;;
  esac
done

# Before Bash 4.4, plain empty-array expansion can fail under set -u. This guard
# expands to zero arguments while retaining support for older Bash 4 releases.
for arg in "${BRANCH_ARGS[@]+"${BRANCH_ARGS[@]}"}"; do
  # With no explicit repository, retain useful unknown-registry-name errors.
  # Standard branches and locally known feature branches select the current repo.
  if [[ -z "$REPO" && ! "$arg" =~ ^[0-9]+\.[0-9]+ &&
        ! "$arg" =~ ^release- && "$arg" != devel && "$arg" != main && "$arg" != master ]] &&
     ! git show-ref --verify --quiet "refs/heads/$arg" &&
     ! git show-ref --verify --quiet "refs/remotes/origin/$arg"; then
    if [[ -n "$REPOS_YAML" ]]; then
      echo "  Not found in $REPOS_YAML. Use an absolute path or add it to repos.yaml." >&2
    else
      echo "  No repository registry configured. Copy repos.yaml.example to repos.yaml, set CVE_FIX_REPOS, or use an absolute path." >&2
    fi
    die "Unknown repo: $arg"
  fi
  [[ -n "$BRANCH" ]] && die "Multiple branches specified"
  BRANCH="$arg"
done

REPO="${REPO:-.}"

# --- Validate repo ---
[[ -d "$REPO" ]] || die "Repository not found: $REPO"
git -C "$REPO" rev-parse --git-dir &>/dev/null || die "Not a git repository: $REPO"
[[ -f "$REPO/go.mod" ]] || die "REPO $REPO has no go.mod — is this a Go project?"

# --- Resolve branch ---
if [[ -z "$BRANCH" ]]; then
  BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null)
  [[ -n "$BRANCH" ]] || die "Not on a branch (detached HEAD). Specify branch explicitly."
  [[ ! "$BRANCH" =~ ^fix-.+-cves-[0-9-]+(-v[0-9]+)?$ ]] ||
    die "On fix branch $BRANCH from an earlier run; specify the base branch"
  echo "Using current branch: $BRANCH"
fi

# Normalize short version (0.23 -> release-0.23)
if [[ "$BRANCH" =~ ^[0-9]+\.[0-9]+$ ]]; then
  BRANCH="release-${BRANCH}"
  echo "Normalized to branch: $BRANCH"
fi

# --- Change to repo (absolute path) ---
REPO="$(cd "$REPO" && pwd)"
cd "$REPO"
ORIGINAL_REPO="$REPO"

REPO_NAME=$(basename "$REPO")
echo ""
echo "=== CVE Fix: $REPO_NAME/$BRANCH ==="

# --- Branch setup (optional) ---
ORIGINAL_REF=""
FIX_BRANCH=""
FETCH_FAILED=false
BASE_SHA=""
DETECT_COMMITTED=false
CREATED_BRANCH=false

# Branch setup is transactional. fix-all.sh cannot clean a mutation
# made before this script emits its state file, so roll back locally unless the
# complete state was written successfully.
rollback_incomplete_setup() {
  local exit_status="${1:-$?}"
  if [[ "$SETUP_BRANCH" == "true" && "$DETECT_COMMITTED" != "true" && \
        "$CREATED_BRANCH" == "true" && -n "$FIX_BRANCH" ]]; then
    if [[ -n "$ORIGINAL_REF" ]]; then
      if git -C "$ORIGINAL_REPO" show-ref --verify --quiet "refs/heads/$ORIGINAL_REF"; then
        git -C "$ORIGINAL_REPO" checkout -q "$ORIGINAL_REF" 2>/dev/null || true
      else
        git -C "$ORIGINAL_REPO" checkout -q --detach "$ORIGINAL_REF" 2>/dev/null || true
      fi
    fi
    git -C "$ORIGINAL_REPO" branch -D "$FIX_BRANCH" 2>/dev/null || true
  fi
  return "$exit_status"
}
trap 'rollback_incomplete_setup $?' EXIT
trap 'trap - INT TERM; exit 130' INT
trap 'trap - INT TERM; exit 143' TERM

if [[ "$SETUP_BRANCH" == "true" ]]; then
  if [[ -n "$(git status --porcelain --untracked-files=normal 2>/dev/null)" ]]; then
    die "Working tree has uncommitted changes. Commit or stash first."
  fi

  ORIGINAL_REF=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  [[ "$ORIGINAL_REF" == "HEAD" ]] && ORIGINAL_REF=$(git rev-parse HEAD)

  echo "Fetching latest changes..."
  # Use the remote exactly as configured (see fetch_origin_branch): the fetch
  # URL is never rewritten, so private repositories that require SSH keep working.
  if ! _fetch_err=$(fetch_origin_branch "$BRANCH" 2>&1 >/dev/null); then
    echo "WARNING: git fetch failed. Continuing with cached remote state."
    [[ -z "$_fetch_err" ]] || printf '%s\n' "$_fetch_err" | sed 's/^/  git: /' >&2
    FETCH_FAILED=true
  fi
  unset _fetch_err
  if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    BASE_SHA=$(git rev-parse "refs/remotes/origin/$BRANCH")
  fi

  DATE=$(date +%Y-%m-%d)
  VERSION="${BRANCH//release-/}"
  FIX_BRANCH="fix-${VERSION}-cves-${DATE}"

  _BASE_FIX_BRANCH="$FIX_BRANCH"
  N=2
  while git show-ref --verify --quiet "refs/heads/$FIX_BRANCH"; do
    FIX_BRANCH="${_BASE_FIX_BRANCH}-v${N}"
    ((N++))
  done

  _FETCH_HINT=""
  [[ "$FETCH_FAILED" == "true" ]] && \
    _FETCH_HINT=" (git fetch failed — origin/$BRANCH may not be current; check network and retry)"

  if ! git checkout -b "$FIX_BRANCH" "origin/$BRANCH" 2>/dev/null; then
    if git show-ref --verify "refs/heads/$FIX_BRANCH" &>/dev/null; then
      die "Fix branch $FIX_BRANCH already exists (concurrent run in progress?). Retry to get a -v2 suffix."
    fi
    die "Could not create fix branch from origin/$BRANCH${_FETCH_HINT}"
  fi
  CREATED_BRANCH=true
  echo "Fix branch: $FIX_BRANCH"
fi

# --- Detect config ---
# Runs AFTER branch setup so probes see the checked-out target tree, not the
# branch that happened to be checked out on entry.

# Generated files whose diffs may contain only tool-version noise. CI tolerates
# that with `git diff -I<regex>`, so enable every rule that applies. controller-gen
# stamps its version into the CRD YAML it generates (and, on older branches, into
# Go files embedding those CRDs); protoc-gen-go stamps comments into *.pb.go.
# Only tracked files outside vendor/ count.
DIFF_IGNORE_ARGS=""
if git grep -q -I -F -e "controller-gen.kubebuilder.io/version" -- . \
     ':(exclude)vendor' ':(exclude)*/vendor/*' 2>/dev/null; then
  DIFF_IGNORE_ARGS="-I$(controller_gen_version_pattern)"
fi
if [[ -n "$(git ls-files -- '*.pb.go' ':(exclude)vendor' ':(exclude)*/vendor/*' 2>/dev/null)" ]]; then
  DIFF_IGNORE_ARGS+="${DIFF_IGNORE_ARGS:+ }-I$(protoc_version_pattern)"
fi

# Shipyard Dapper files are commonly git-ignored and downloaded by Make on the
# first real target. Detect the wrapper itself so builder policy and scan-build
# flags are correct even on a pristine clone where Dockerfile.dapper is absent.
USES_SHIPYARD_DAPPER=false
if { [[ -f Dockerfile.dapper ]] && grep -qE 'SHIPYARD_REPO|shipyard-dapper-base' Dockerfile.dapper; } || \
   { [[ -f Makefile ]] && grep -q 'include Makefile[.]dapper' Makefile && \
     grep -q 'raw[.]githubusercontent[.]com/submariner-io/shipyard' Makefile; }; then
  USES_SHIPYARD_DAPPER=true
fi

NEEDS_BUILD_FOR_SCAN=false
has_build_target && NEEDS_BUILD_FOR_SCAN=true

if command -v docker &>/dev/null && docker info &>/dev/null; then
  CONTAINER_CMD="docker"
elif command -v podman &>/dev/null && podman info &>/dev/null; then
  CONTAINER_CMD="podman"
else
  CONTAINER_CMD=""
fi

# Prefer skill-local grype (installed by ensure_grype in lib.sh) over any system grype
_SKILL_BIN="$SCRIPT_DIR/../bin"
[[ -d "$_SKILL_BIN" ]] && export PATH="$_SKILL_BIN:$PATH"

HAS_LOCAL_GRYPE=false
command -v grype &>/dev/null && HAS_LOCAL_GRYPE=true

# --- Read .cve-fix.yaml config (optional) ---
# Env vars CVE_FIX_BUILD_IMAGE, CVE_FIX_BUILD_CMD, CVE_FIX_CLEAN_CMD, CVE_FIX_TEST_CMD
# override .cve-fix.yaml and auto-detection, useful when the file can't be committed
# to the target branch (e.g., to skip dapper clean on low-memory hosts).
BUILD_IMAGE="${CVE_FIX_BUILD_IMAGE:-}"
BUILD_CMD="${CVE_FIX_BUILD_CMD:-}"
CLEAN_CMD="${CVE_FIX_CLEAN_CMD:-}"
TEST_CMD="${CVE_FIX_TEST_CMD:-}"
# Some Shipyard image helpers use REPO as a Docker image namespace. Keep the
# filesystem path in REPO for discovery, but provide a valid local namespace
# for those helpers when the target repository builds its own images.
BUILD_REPO_NAME=""
if [[ "$USES_SHIPYARD_DAPPER" == "true" && -f "$REPO/Makefile.images" ]]; then
  BUILD_REPO_NAME="cve-fix-$(printf '%s' "$REPO_NAME" | tr '[:upper:]_' '[:lower:]-' | sed 's/[^a-z0-9.-]/-/g; s/--*/-/g; s/^[.-]*//; s/[.-]*$//')"
fi
ENV_UNSET=""
K8S_VERSION_GUARD="${CVE_FIX_K8S_VERSION_GUARD:-}"
GO_MINOR_GUARD="${CVE_FIX_GO_MINOR_GUARD:-}"
UPSTREAM_ORG=""
_cve_config="$REPO/.cve-fix.yaml"
if [[ -f "$_cve_config" ]]; then
  _config_json=$(python3 "$SCRIPT_DIR/read-config.py" config-json "$_cve_config") || \
    die "Invalid .cve-fix.yaml"
  _v=$(jq -r '.["build-image"] // empty' <<< "$_config_json"); [[ -n "$_v" && -z "$BUILD_IMAGE" ]] && BUILD_IMAGE="$_v"
  _v=$(jq -r '.["build-command"] // empty' <<< "$_config_json"); [[ -n "$_v" && -z "$BUILD_CMD" ]] && BUILD_CMD="$_v"
  _v=$(jq -r '.["clean-command"] // empty' <<< "$_config_json"); [[ -n "$_v" && -z "$CLEAN_CMD" ]] && CLEAN_CMD="$_v"
  _v=$(jq -r '.["test-command"] // empty' <<< "$_config_json"); [[ -n "$_v" && -z "$TEST_CMD" ]] && TEST_CMD="$_v"
  ENV_UNSET=$(jq -r '.["unset-env"] // empty' <<< "$_config_json")
  [[ -n "$K8S_VERSION_GUARD" ]] || K8S_VERSION_GUARD=$(jq -r '.["k8s-version-guard"] // false' <<< "$_config_json")
  [[ -n "$GO_MINOR_GUARD" ]] || GO_MINOR_GUARD=$(jq -r '.["go-minor-guard"] // false' <<< "$_config_json")
  UPSTREAM_ORG=$(jq -r '.["upstream-org"] // empty' <<< "$_config_json")
  for _var in $ENV_UNSET; do
    [[ "$_var" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Invalid unset-env name in .cve-fix.yaml: $_var"
  done
fi

GO_MINOR_GUARD=${GO_MINOR_GUARD:-false}
[[ "$GO_MINOR_GUARD" == true || "$GO_MINOR_GUARD" == false ]] || die "CVE_FIX_GO_MINOR_GUARD must be true or false"
K8S_VERSION_GUARD=${K8S_VERSION_GUARD:-false}
[[ "$K8S_VERSION_GUARD" == true || "$K8S_VERSION_GUARD" == false ]] || die "CVE_FIX_K8S_VERSION_GUARD must be true or false"

# Auto-detect build/clean/test commands if not set by config
if [[ -z "$BUILD_CMD" ]] && [[ "$NEEDS_BUILD_FOR_SCAN" == "true" ]]; then
  # Dapper only forwards variables named by DAPPER_ENV. MAKEFLAGS does not carry
  # BUILD_UPX through its docker boundary, so name and set it explicitly. The
  # Fedora-based Dapper image defaults GOEXPERIMENT, which makes binaries
  # unmatchable by Grype; forward the run's choice, defaulting to upstream.
  if [[ "$USES_SHIPYARD_DAPPER" == "true" ]]; then
    # shellcheck disable=SC2016 # expanded later by bash -c in the build environment
    BUILD_CMD='DAPPER_ENV="${DAPPER_ENV:+$DAPPER_ENV }BUILD_UPX GOEXPERIMENT" BUILD_UPX=false GOEXPERIMENT="${GOEXPERIMENT-,}" make build'
  else
    BUILD_CMD="make build"
  fi
fi
# Do not auto-run a consumer's outer Dapper clean target. On a pristine checkout
# its generated wrapper may not exist yet; once present, Shipyard clean graphs
# can include host-wide cluster cleanup. The subsequent build refreshes current
# outputs, and any genuinely stale binary remains visible to the fail-closed
# final scan. Repositories may still opt in explicitly.
if [[ -z "$CLEAN_CMD" && "$USES_SHIPYARD_DAPPER" != "true" ]] && has_real_make_target clean; then
  CLEAN_CMD="make clean"
fi
if [[ -z "$TEST_CMD" ]]; then
  # Shipyard's standard unit target lives in Makefile.inc inside Dapper and is
  # therefore invisible to a pristine outer checkout's make target probe.
  if [[ "$USES_SHIPYARD_DAPPER" == "true" ]]; then TEST_CMD="make unit"
  elif has_real_make_target unit; then TEST_CMD="make unit"
  elif has_real_make_target test; then TEST_CMD="make test"
  elif has_real_make_target test-unit; then TEST_CMD="make test-unit"
  else TEST_CMD="go test ./..."
  fi
fi

# Shipyard builds in shipyard-dapper-base tagged by branch (release-0.22 on a
# release branch). Dockerfile.dapper may name another registry with
# SHIPYARD_REPO; pristine checkouts download it only when Make runs.
if [[ -z "$BUILD_IMAGE" && "$USES_SHIPYARD_DAPPER" == "true" ]]; then
  _repo_arg=$(grep -E '^ARG SHIPYARD_REPO=' Dockerfile.dapper 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)
  BUILD_IMAGE="${_repo_arg:-quay.io/submariner}/shipyard-dapper-base:${BRANCH}"
  echo "Auto-detected Shipyard build image: $BUILD_IMAGE"
fi

if [[ "$BUILD_IMAGE" == -* || "$BUILD_IMAGE" =~ [[:space:]] ]]; then
  die "Invalid build image: $BUILD_IMAGE"
fi

# Detect Go version from the build image (if configured); otherwise "unknown".
# We deliberately do NOT fall back to the host `go version`: it is cwd-dependent
# and mislabels the host toolchain as the build-image compiler. Leaving it
# "unknown" routes cross-minor stdlib fixes to an honest NEEDS_REVIEW instead.
BUILD_GO_VERSION="unknown"
if [[ -n "$BUILD_IMAGE" ]] && [[ -n "$CONTAINER_CMD" ]]; then
  # A cold host may not have the configured image yet. Pull on demand so a safe
  # builder-supported Go directive bump is not misclassified as unknown.
  BUILD_GO_VERSION=$(timeout "${CVE_FIX_IMAGE_TIMEOUT:-180}" \
    "$CONTAINER_CMD" run --pull=missing --rm "$BUILD_IMAGE" go version 2>/dev/null || echo "unknown")
  [[ -n "$BUILD_GO_VERSION" ]] || BUILD_GO_VERSION="unknown"
fi

# --- Write state file ---
STATE_FILE=$(state_file_path "$REPO" "$BRANCH")
write_state_var() { printf '%s=%q\n' "$1" "$2"; }
# shellcheck disable=SC2094 # serialize the path value; no state-file content is read here
{
  write_state_var STATE_FILE "$STATE_FILE"
  write_state_var REPO "$REPO"
  write_state_var BRANCH "$BRANCH"
  write_state_var FIX_BRANCH "$FIX_BRANCH"
  write_state_var ORIGINAL_REF "$ORIGINAL_REF"
  write_state_var DIFF_IGNORE_ARGS "$DIFF_IGNORE_ARGS"
  write_state_var CONTAINER_CMD "$CONTAINER_CMD"
  write_state_var HAS_LOCAL_GRYPE "$HAS_LOCAL_GRYPE"
  write_state_var BUILD_IMAGE "$BUILD_IMAGE"
  write_state_var BUILD_GO_VERSION "$BUILD_GO_VERSION"
  write_state_var BUILD_CMD "$BUILD_CMD"
  write_state_var BUILD_REPO_NAME "$BUILD_REPO_NAME"
  write_state_var CLEAN_CMD "$CLEAN_CMD"
  write_state_var TEST_CMD "$TEST_CMD"
  write_state_var ENV_UNSET "$ENV_UNSET"
  write_state_var K8S_VERSION_GUARD "$K8S_VERSION_GUARD"
  write_state_var GO_MINOR_GUARD "$GO_MINOR_GUARD"
  write_state_var UPSTREAM_ORG "$UPSTREAM_ORG"
  write_state_var FETCH_FAILED "$FETCH_FAILED"
  write_state_var BASE_SHA "$BASE_SHA"
  write_state_var CVE_SCRIPTS "$SCRIPT_DIR"
} > "$STATE_FILE"
DETECT_COMMITTED=true

# Last line is the state file path (captured by callers)
echo "$STATE_FILE"
