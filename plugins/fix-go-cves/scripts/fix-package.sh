#!/usr/bin/env bash
set -euo pipefail
# Fix a single CVE package: update, verify, commit.
# Usage: fix-package.sh STATE_FILE PACKAGE VERSION CVE_ID [CVE_ID...]
# Exit 0: fixed. Exit 2: needs review (breaking change). Exit 3: CVE persists.
# Exit 4: fix version not in Go module registry (version tag not published yet).
# Exit 5: transient network error (timeout or connection failure).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: fix-package.sh STATE_FILE PACKAGE VERSION CVE_ID [CVE_ID...]}"
PACKAGE="${2:?Missing PACKAGE}"
VERSION="${3:?Missing VERSION}"
VERSION="${VERSION#v}"
shift 3

# Optional --location flag: grype-reported go.mod path (e.g. /go.mod, /src/tools/go.mod).
# When set, only fix in that module. When absent, fall back to all-module behaviour.
FIX_LOCATION=""
FIX_GOMOD=""
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --) shift; break ;;
    --location) FIX_LOCATION="${2:?--location requires a path argument}"; shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

CVE_IDS=("$@")
[[ ${#CVE_IDS[@]} -gt 0 ]] || die "At least one CVE_ID required. Usage: fix-package.sh STATE_FILE PACKAGE VERSION CVE_ID [CVE_ID...]"

# Normalize a grype location path to a relative go.mod path.
# Grype prefixes with /src when run in Docker (repo mounted at /src), or just /
# for local runs. Strip those prefixes so we get go.mod, tools/go.mod, etc.
_normalize_grype_location() {
  local loc="$1"
  loc="${loc#/src/}" # strip the exact Docker mount prefix
  loc="${loc#/}"     # strip leading slash
  echo "$loc"
}

# Location-aware gomod iterator: when --location is set, yield only that module.
# The caller validates a supplied path as an exact tracked go.mod before iteration.
# Without a location, iterate every tracked module (multi-location or binary CVEs).
_iter_gomods() {
  if [[ -n "$FIX_GOMOD" ]]; then
    echo "$FIX_GOMOD"
  else
    find_gomods
  fi
}

load_state "$STATE_FILE"

# A scoped scan result is a security boundary: never broaden an invalid scope to
# every module, and never allow a crafted location to escape the repository.
if [[ -n "$FIX_LOCATION" ]]; then
  FIX_GOMOD=$(_normalize_grype_location "$FIX_LOCATION")
  if [[ -z "$FIX_GOMOD" || "$FIX_GOMOD" == /* || "$FIX_GOMOD" == ".." || \
        "$FIX_GOMOD" == ../* || "$FIX_GOMOD" == */../* || "$FIX_GOMOD" != *.mod ]] || \
     ! find_gomods | grep -qxF "$FIX_GOMOD"; then
    echo "NEEDS_REVIEW: $PACKAGE — scanner location '$FIX_LOCATION' is not a tracked repository go.mod"
    exit 2
  fi
  FIX_LOCATION=$(normalize_scan_location "$FIX_GOMOD")
fi

_BUILD_GOTOOLCHAIN="${GOTOOLCHAIN-}"
_BUILD_GOTOOLCHAIN_SET="${GOTOOLCHAIN+x}"
_BUILD_GOWORK="${GOWORK-}"
_BUILD_GOWORK_SET="${GOWORK+x}"
export GOTOOLCHAIN=auto
# Disable workspace mode so go get resolves modules against go.mod, not go.work.
# The go.work file is preserved on disk; GOWORK=off is local to this script run.
export GOWORK=off
# Resolve and mutate from go.mod even when a repository has a stale or partial
# vendor directory. Each changed module's vendor directory is regenerated below.
# Append so an inherited -mod=vendor cannot silently override remediation.
_BUILD_GOFLAGS="${GOFLAGS-}"
_BUILD_GOFLAGS_SET="${GOFLAGS+x}"
export GOFLAGS="${GOFLAGS:+$GOFLAGS }-mod=mod"
export GOPROXY="${GOPROXY:-https://proxy.golang.org,direct}"
if [[ "${GOPROXY}" == "off" ]]; then
    echo "WARNING: GOPROXY=off is set — go get will fail unless packages are cached."
    echo "         Set GOPROXY=https://proxy.golang.org,direct or unset GOPROXY."
fi
if [[ "${GONOSUMDB:-}" == *"*"* ]]; then
    echo "WARNING: GONOSUMDB='${GONOSUMDB}' includes '*' — matching modules skip checksum-database lookups."
    echo "         Checksums for updated packages may not be verified against sum.golang.org."
fi

# || true is intentional: reset/checkout can fail if nothing is staged/modified,
# and we still want the original error to surface, not a cleanup failure.
trap 'git reset --quiet HEAD -- . 2>/dev/null || true; git checkout -- . 2>/dev/null || true' ERR

# go mod vendor can create files absent from HEAD. A tracked-file checkout alone
# leaves those files behind after a rejected upgrade, corrupting later builds.
# Snapshot only pre-existing untracked vendor files, including ignored files;
# roll back this package's new files without sweeping other repository outputs.
declare -A _VENDOR_UNTRACKED_BEFORE=()
mapfile -t _VENDOR_DIRS < <(find_vendor_dirs)
_VENDOR_SNAPSHOT=""
_VENDOR_SNAPSHOT_READY=false
_PACKAGE_SCAN_BEFORE=""
_PACKAGE_SCAN_AFTER=""
_DEPENDENCY_SNAPSHOT=""
declare -A _DEPENDENCY_BEFORE=()
_finish_package_transaction() {
  local status="$1" rollback="${2:-false}" file
  if [[ "$status" -ne 0 || "$rollback" == true ]]; then
    git reset --quiet HEAD -- . 2>/dev/null || true
    git checkout -- . 2>/dev/null || true
    for file in "${!_DEPENDENCY_BEFORE[@]}"; do
      if [[ "${_DEPENDENCY_BEFORE[$file]}" == present ]]; then
        cp -pP -- "$_DEPENDENCY_SNAPSHOT/$file" "$file"
      else
        rm -f -- "$file"
      fi
    done
    if [[ "$_VENDOR_SNAPSHOT_READY" == true ]]; then
      while IFS= read -r -d '' file; do
        [[ -n "${_VENDOR_UNTRACKED_BEFORE[$file]+present}" ]] || rm -f -- "$file"
      done < <(git ls-files --others -z -- "${_VENDOR_DIRS[@]}")
      for file in "${!_VENDOR_UNTRACKED_BEFORE[@]}"; do
        mkdir -p "$(dirname "$file")"
        cp -P -- "$_VENDOR_SNAPSHOT/$file" "$file"
      done
    fi
  fi
  [[ -z "$_VENDOR_SNAPSHOT" ]] || rm -rf -- "$_VENDOR_SNAPSHOT"
  [[ -z "$_DEPENDENCY_SNAPSHOT" ]] || rm -rf -- "$_DEPENDENCY_SNAPSHOT"
  rm -f "${_GO_GET_LOG:-}"
  rm -f "${_PACKAGE_SCAN_BEFORE:-}" "${_PACKAGE_SCAN_AFTER:-}"
  return "$status"
}
trap '_finish_package_transaction $?' EXIT
# Capture dependency metadata before even version lookups: go list -mod=mod
# can create go.sum. Preserve existing untracked/ignored files as well as
# tracked ones, and remove only metadata absent at the start of this attempt.
_DEPENDENCY_SNAPSHOT=$(mktemp -d "${TMPDIR:-/tmp}/cve-dependency-before.XXXXXX")
while IFS= read -r _gm; do
  for _metadata in "$_gm" "${_gm%go.mod}go.sum"; do
    if [[ -L "$_metadata" ]]; then
      echo "NEEDS_REVIEW: $PACKAGE — dependency metadata '$_metadata' is a symlink"
      exit 2
    fi
    if [[ -e "$_metadata" ]]; then
      mkdir -p "$_DEPENDENCY_SNAPSHOT/$(dirname "$_metadata")"
      cp -pP -- "$_metadata" "$_DEPENDENCY_SNAPSHOT/$_metadata"
      _DEPENDENCY_BEFORE["$_metadata"]=present
    else
      _DEPENDENCY_BEFORE["$_metadata"]=absent
    fi
  done
done < <(find_gomods)
_metadata=go.work.sum
if [[ -L "$_metadata" ]]; then
  echo "NEEDS_REVIEW: $PACKAGE — dependency metadata '$_metadata' is a symlink"
  exit 2
fi
if [[ -e "$_metadata" ]]; then
  cp -pP -- "$_metadata" "$_DEPENDENCY_SNAPSHOT/$_metadata"
  _DEPENDENCY_BEFORE["$_metadata"]=present
else
  _DEPENDENCY_BEFORE["$_metadata"]=absent
fi
if [[ ${#_VENDOR_DIRS[@]} -gt 0 ]]; then
  _VENDOR_SNAPSHOT=$(mktemp -d "${TMPDIR:-/tmp}/cve-vendor-before.XXXXXX")
  for _vendor_dir in "${_VENDOR_DIRS[@]}"; do
    if [[ -L "$_vendor_dir" ]]; then
      echo "NEEDS_REVIEW: $PACKAGE — vendor directory '$_vendor_dir' is a symlink"
      exit 2
    fi
  done
  while IFS= read -r -d '' _file; do
    _VENDOR_UNTRACKED_BEFORE["$_file"]=1
    mkdir -p "$_VENDOR_SNAPSHOT/$(dirname "$_file")"
    cp -P -- "$_file" "$_VENDOR_SNAPSHOT/$_file"
  done < <(git ls-files --others -z -- "${_VENDOR_DIRS[@]}")
  _VENDOR_SNAPSHOT_READY=true
fi

# Prefer a candidate explicitly known to fix every grouped CVE. Fall back to the
# legacy union selector only for callers that do not yet supply per-CVE data.
if [[ -n "${CVE_FIX_REQUIREMENTS_B64:-}" || -n "${CVE_FIX_ALL_VERSIONS:-}" ]]; then
  _INST=""
  while IFS= read -r _GM; do
    _CANDIDATE_INST=$(get_installed_version "$(dirname "$_GM")" "$PACKAGE" 2>/dev/null || echo "")
    [[ -z "$_CANDIDATE_INST" ]] && continue
    # Anchor common-stream selection on the lowest in-scope occurrence. An
    # already-safe sibling module must not mask an older vulnerable copy in
    # another module of the same repository.
    if [[ -z "$_INST" ]] || version_gte "$_INST" "$_CANDIDATE_INST"; then
      _INST="$_CANDIDATE_INST"
    fi
  done < <(_iter_gomods)
  if [[ -n "$_INST" ]]; then
    _BEST=""
    if [[ -n "${CVE_FIX_REQUIREMENTS_B64:-}" ]]; then
      # An active finding at a version above the listed threshold is not proof
      # that an older version is safe: affected ranges can be non-monotonic, or
      # a newer release stream can require its own patched threshold. Never
      # downgrade; require a combined target at or above installed, reaching
      # every advisory threshold. The mandatory final scan confirms the result.
      _BEST=$(select_common_fix_version "$_INST" "$CVE_FIX_REQUIREMENTS_B64" || true)
      if [[ -z "$_BEST" ]]; then
        # Another package's upgrade may have removed these initial findings.
        # Version ordering alone cannot prove that: consult a current scan,
        # including ignored findings, before reporting the package as fixed.
        if [[ "${HAS_LOCAL_GRYPE:-false}" == true || -n "${CONTAINER_CMD:-}" ]]; then
          _CURRENT_SCAN=$(mktemp "${TMPDIR:-/tmp}/cve-package-current.XXXXXX")
          _CURRENT_SCAN_RC=0
          timeout --foreground "${CVE_FIX_SCAN_TIMEOUT:-600}" bash "$CVE_SCRIPTS/scan.sh" \
            "$STATE_FILE" --skip-build --no-update --json > "$_CURRENT_SCAN" 2>/dev/null || _CURRENT_SCAN_RC=$?
          _IDS_JSON=$(printf '%s\n' "${CVE_IDS[@]}" | jq -R . | jq -s .)
          if [[ "$_CURRENT_SCAN_RC" -eq 0 && ! -f "${STATE_FILE}.scanner-degraded" && \
                ! -f "${STATE_FILE}.coverage-unknown" && ! -f "${STATE_FILE}.build-failed" ]] && \
             grype_scan_json_valid "$_CURRENT_SCAN" && \
             jq -e --arg pkg "$PACKAGE" --argjson ids "$_IDS_JSON" '
               [((.matches // []) + (.ignoredMatches // []))[] |
                 select(.artifact.name == $pkg) |
                 .vulnerability.id as $id | select($ids | index($id))] | length == 0
             ' "$_CURRENT_SCAN" >/dev/null; then
            rm -f "$_CURRENT_SCAN"
            # The fix predates this attempt; discard lookup-induced metadata edits.
            _finish_package_transaction 0 true
            trap - EXIT
            echo "FIXED: $PACKAGE v$_INST for ${CVE_IDS[*]}"
            echo "NOTE: current Grype evidence confirms these findings were fixed by a prior dependency update"
            exit 0
          fi
          rm -f "$_CURRENT_SCAN"
        fi
        echo "NEEDS_REVIEW: $PACKAGE — no stable fix threshold at or above the installed version satisfies every grouped CVE"
        echo "NOTE: Installed selection anchor: v$_INST"
        # Canonical JSON escapes advisory text and retains the actual reported
        # versions, making a rejected grouped selection reproducible.
        _REPORTED_REQUIREMENTS=$(printf '%s' "$CVE_FIX_REQUIREMENTS_B64" | base64 -d 2>/dev/null | \
          jq -c 'if type == "array" then . else error("invalid requirements") end' 2>/dev/null || true)
        echo "NOTE: Reported grouped fix requirements: ${_REPORTED_REQUIREMENTS:-invalid requirement data}"
        exit 2
      fi
    else
      _BEST=$(select_instream_version "$PACKAGE" "$_INST")
      if [[ "$_BEST" == "$_INST" ]] && version_gte "$_INST" "$VERSION"; then
        echo "NEEDS_REVIEW: $PACKAGE — no stable fix version at or above the installed version"
        exit 2
      fi
    fi
    if [[ -n "$_BEST" && "$_BEST" != "$_INST" ]]; then
      echo "NOTE: Selecting shared fix threshold v$_BEST for all grouped CVEs (requested v$VERSION)"
      VERSION="$_BEST"
    fi
  fi
fi

echo "--- Fixing: $PACKAGE -> v$VERSION for ${CVE_IDS[*]} ---"

# Module vendoring would replace a workspace vendor tree and drop its siblings.
if [[ "$(head -1 vendor/modules.txt 2>/dev/null)" == "## workspace" ]]; then
  echo "NEEDS_REVIEW: $PACKAGE — workspace vendoring (go work vendor) is not automated"
  exit 2
fi

# Compare current source evidence before and after the transaction. A version
# that fixes one advisory can introduce another (OpenTelemetry 1.39 -> 1.41).
# Graph version ordering alone cannot detect these non-monotonic affected ranges.
_package_scan() {
  local output="$1" scan_rc=0
  timeout --foreground "${CVE_FIX_SCAN_TIMEOUT:-600}" bash "$CVE_SCRIPTS/scan.sh" \
    "$STATE_FILE" --skip-build --no-update --json > "$output" || scan_rc=$?
  [[ "$scan_rc" -eq 0 && ! -f "${STATE_FILE}.scanner-degraded" &&
     ! -f "${STATE_FILE}.coverage-unknown" ]] &&
    grype_scan_json_valid "$output"
}
if [[ "${HAS_LOCAL_GRYPE:-false}" == true || -n "${CONTAINER_CMD:-}" ]]; then
  _PACKAGE_SCAN_BEFORE=$(mktemp "${TMPDIR:-/tmp}/cve-package-before.XXXXXX")
  if ! _package_scan "$_PACKAGE_SCAN_BEFORE"; then
    echo "NEEDS_REVIEW: $PACKAGE — current source scan could not establish a baseline before dependency update"
    exit 2
  fi
  if [[ -n "${CVE_FIX_REQUIREMENTS_B64:-}" && -n "${_INST:-}" ]]; then
    # Earlier fixes may move this package into a release stream with a different
    # threshold for the same advisory. Prefer its current source evidence.
    _BEFORE_FINDINGS=$(grype_source_findings "$_PACKAGE_SCAN_BEFORE") || exit 2
    _INITIAL_REQUIREMENTS=$(printf '%s' "$CVE_FIX_REQUIREMENTS_B64" | jq -Rr '@base64d | fromjson') || exit 2
    _CURRENT_REQUIREMENTS=$(jq -c --arg pkg "$PACKAGE" --arg location "$FIX_LOCATION" \
      --argjson original "$_INITIAL_REQUIREMENTS" --argjson source "$_BEFORE_FINDINGS" '
      def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
      [((.matches // []) + (.ignoredMatches // []))[] | select(.artifact.name == $pkg) as $m |
        .artifact.locations[]? | (.path | normloc) as $path |
        select($location == "" or $path == $location) |
        [$m.vulnerability.id, $pkg, $path] as $key | select($source | any(. == $key)) |
        {cve: $m.vulnerability.id, versions: ($m.vulnerability.fix.versions // [])}] |
      group_by(.cve) | map({cve: .[0].cve, versions: ([.[].versions[]] | unique)}) as $current |
      $original | map(. as $old | ([$current[] | select(.cve == $old.cve)] | first) // $old)
      ' "$_PACKAGE_SCAN_BEFORE") || exit 2
    _CURRENT_REQUIREMENTS_B64=$(printf '%s' "$_CURRENT_REQUIREMENTS" | base64 | tr -d '\n')
    _CURRENT_BEST=$(select_common_fix_version "$_INST" "$_CURRENT_REQUIREMENTS_B64" || true)
    if [[ -n "$_CURRENT_BEST" && "$_CURRENT_BEST" != "$VERSION" ]] && version_gte "$_CURRENT_BEST" "$VERSION"; then
      echo "NOTE: Current source scan selects shared fix threshold v$_CURRENT_BEST (initial v$VERSION)"
      VERSION="$_CURRENT_BEST"
    fi
  fi
fi

# Check for replace directives across all go.mod files (warn, don't block)
while IFS= read -r GOMOD; do
  if _replace=$(grep "replace.*${PACKAGE}" "$GOMOD" 2>/dev/null); then
    echo "WARNING: Replace directive found in $GOMOD for $PACKAGE"
    printf '%s\n' "$_replace"
  fi
done < <(find_gomods)

# Snapshot explicit indirect dependency versions per module before update.
# go mod tidy can lower these when the newly-updated package requires lower
# minimums for shared transitive deps — silently re-introducing already-fixed CVEs.
declare -A _INDIRECT_BEFORE=()
while IFS= read -r GOMOD; do
  MODDIR=$(dirname "$GOMOD")
  while read -r _ipkg _iver _; do
    [[ -n "$_ipkg" && -n "$_iver" ]] && \
      _INDIRECT_BEFORE["$MODDIR:$_ipkg"]="${_iver#v}"
  done < <(grep '// indirect' "$GOMOD" 2>/dev/null | sed -E 's/^[[:space:]]*require[[:space:]]+//')
done < <(find_gomods)

# Snapshot Go directives before update (for builder-policy validation)
declare -A _GO_BEFORE=()
declare -A _TOOLCHAIN_BEFORE=()
while IFS= read -r GOMOD; do
  GO_VER=$(awk '$1 == "go" { print $2; exit }' "$GOMOD" 2>/dev/null)
  [[ -n "$GO_VER" ]] && _GO_BEFORE["$GOMOD"]="$GO_VER"
  _TOOLCHAIN_BEFORE["$GOMOD"]=$(gomod_toolchain "$(dirname "$GOMOD")")
done < <(find_gomods)

# Restore exactly the repository's original toolchain policy after Go commands.
# Newer go tooling may add/change this directive as incidental metadata.
_restore_toolchain_directives() {
  local _gm
  for _gm in "${!_TOOLCHAIN_BEFORE[@]}"; do
    [[ -f "$_gm" ]] || continue
    restore_gomod_toolchain "$(dirname "$_gm")" "${_TOOLCHAIN_BEFORE[$_gm]}"
  done
}

_k8s_minor_versions() {
  while IFS= read -r _GM; do
    grep -E 'k8s\.io/(api|apimachinery|client-go) v0\.' "$_GM" 2>/dev/null || true
  done < <(find_gomods) | { grep -oE 'v0\.[0-9]+' || true; } | sed 's/^v0\.//' | sort -un | tr '\n' ' '
}
# Compare existing declared dependency pairs without losing module identity.
# Return 1 for a minor change, 2 when the comparison cannot be verified.
_k8s_minor_pairs_unchanged() {
  [[ -r "$1" && -r "$2" ]] || return 2
  awk '
    function dependency(pkg, version, parts, minor) {
      if (pkg !~ /^k8s[.]io\/(api|apimachinery|client-go)$/) return
      if (version !~ /^v0[.][0-9]+[.][0-9]+([+-].*)?$/) return
      split(version, parts, ".")
      minor=parts[2]
      if (FILENAME == ARGV[1]) before[pkg]=minor
      else if (pkg in before && before[pkg] != minor) changed=1
    }
    FNR == 1 { section=0 }
    { sub(/\/\/.*/, "") }
    $1 == "require" {
      section=($2 == "(")
      if (!section) dependency($2, $3)
      next
    }
    $1 == ")" { section=0; next }
    section { dependency($1, $2) }
    END { exit (changed ? 1 : 0) }
  ' "$1" "$2"
}
K8S_BEFORE=""
if [[ "${K8S_VERSION_GUARD:-false}" == "true" ]]; then
  K8S_BEFORE=$(_k8s_minor_versions)
fi

# Helper: run go get and detect if the fix version is absent from the module proxy.
# Uses 'if !' to suppress set -e on the go get call so we can inspect the output
# before deciding how to exit. Sets MODULE_NOT_IN_PROXY=true when the error message
# contains "unknown revision" — the canonical Go proxy error for a missing tag.
MODULE_NOT_IN_PROXY=false
MAJOR_PATH_CHANGE=false
_GO_GET_LOG=$(mktemp)
# A failed logger cannot provide complete verification evidence. Keep the
# command's actual status in the diagnosis; a command timeout stays transient.
_check_package_capture() {
  [[ "$2" -eq 0 ]] && return 0
  echo "ERROR: Cannot capture $3 output (command exited $1; tee exited $2); verification stopped." >&2
  [[ "$1" -ne 124 ]] || exit 5
  exit 2
}

_go_get_version() {
  local moddir="$1" pkg="$2" ver="$3"
  local _rc=0
  local -a _get_status=(0 0)
  module_go "$moddir" get "${pkg}@v${ver}" 2>&1 | tee -a "$_GO_GET_LOG" || _get_status=("${PIPESTATUS[@]}")
  _rc=${_get_status[0]}
  _check_package_capture "$_rc" "${_get_status[1]}" "go get"
  if [[ "$_rc" -ne 0 ]]; then
    if grep -qE "unknown revision v?${ver}|invalid version: unknown revision v?${ver}" \
         "$_GO_GET_LOG" 2>/dev/null; then
      MODULE_NOT_IN_PROXY=true
    elif grep -qE "post-v[0-9]+ module path|should be v0 or v1|module path must match major version" "$_GO_GET_LOG" 2>/dev/null; then
      MODULE_NOT_IN_PROXY=true MAJOR_PATH_CHANGE=true
    fi
    return "$_rc"
  fi
}

# Tracks whether MVS resolved the CVE TARGET package below the required fix version.
# This is the DIRECT vulnerability check — if the package we're fixing is still
# vulnerable, the fix failed. Set only by lines 163-168 (direct package checks).
PRIMARY_STILL_VULNERABLE=false
PRIMARY_UPDATE_FAILED=false

# Diagnostic info for when PRIMARY_STILL_VULNERABLE is set (for better error reporting)
VULNERABLE_RESOLVED_VERSION=""  # Version that MVS actually resolved to
VULNERABLE_REQUIRED_VERSION=""  # Version that was needed for the fix

# Tracks whether re-pinning indirect dependencies failed. This is separate from
# PRIMARY_STILL_VULNERABLE because indirect-dep failures are architectural issues
# (e.g. go-tuf constraint conflicts) not CVE persistence. They should be reported
# but not block a successful primary fix.
REPIN_FAILED_PKG=""
REPIN_FAILED_INDIRECT=false

# Helper: run go get + mod tidy in MODDIR, then check if PRIMARY package resolved below fix version.
# Sets PRIMARY_STILL_VULNERABLE=true when MVS resolves the target package below the fix version.
# Calls exit 5 (in the main shell, not a subshell) on transient network errors.
# Calls exit 2 (in the main shell) when go get succeeds but the go directive minor version jumped —
# GOTOOLCHAIN=auto writes the new go directive before failing on the missing toolchain binary.
_go_get_and_check() {
  local moddir="$1" pkg="$2" ver="$3"
  _GGV_RC=0
  _go_get_version "$moddir" "$pkg" "$ver" || _GGV_RC=$?
  if [[ $_GGV_RC -ne 0 ]]; then
    if [[ $_GGV_RC -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
      echo "TRANSIENT_ERROR: go get failed with exit $_GGV_RC (timeout or network error)"
      rm -f "$_GO_GET_LOG"
      git checkout -- . 2>/dev/null || true
      exit 5
    fi
    # Non-transient go get failure: restore go.mod so subsequent get_installed_version
    # calls (for this or other packages) read clean state, not a partially-mutated go.mod.
    echo "ERROR: go get failed with exit $_GGV_RC for $pkg in $moddir"
    git checkout -- . 2>/dev/null || true
    PRIMARY_UPDATE_FAILED=true
    return 0
  fi
  # go get succeeded. Before running mod tidy, enforce the detected builder as
  # the exact upper bound for any changed Go directive. Since Go 1.21, patch
  # components are also minimum toolchain requirements, so checking only minor
  # changes would wrongly permit go 1.25.3 with a go1.25.2 builder.
  local _go_mod="$moddir/go.mod"
  _go_mod="${_go_mod#./}"
  local _go_was="${_GO_BEFORE["$_go_mod"]:-}"
  local _go_now
  _go_now=$(grep '^go ' "$_go_mod" 2>/dev/null | awk '{print $2}' || true)
  if [[ -n "$_go_was" && -n "$_go_now" && "$_go_was" != "$_go_now" ]]; then
    local _compiler_go
    _compiler_go=$(compiler_go_version)
    if [[ -n "$_compiler_go" ]] && go_directive_supported "$_go_was" "$_go_now" "$_compiler_go" "${GO_MINOR_GUARD:-false}"; then
      echo "NOTE: go directive $_go_was -> $_go_now (safe: build image has Go $_compiler_go)"
    elif [[ -n "$_compiler_go" ]]; then
      echo "NEEDS_REVIEW: $pkg — Go $_go_was -> $_go_now is outside repository/builder policy (builder $_compiler_go; go-minor-guard=${GO_MINOR_GUARD:-false})"
      git checkout -- . 2>/dev/null || true
      exit 2
    elif ! go_directive_supported "$_go_was" "$_go_now" "" "${GO_MINOR_GUARD:-false}"; then
      echo "NEEDS_REVIEW: $pkg — go get upgraded Go directive $_go_was -> $_go_now but the build image Go version is unknown (go-minor-guard=${GO_MINOR_GUARD:-false})"
      git checkout -- . 2>/dev/null || true
      exit 2
    else
      echo "NOTE: build image Go version unknown; allowing same-minor directive bump $_go_was -> $_go_now"
    fi
  fi
  local _tidy_rc=0
  local -a _tidy_status=(0 0)
  module_go "$moddir" mod tidy 2>&1 | tee -a "$_GO_GET_LOG" || _tidy_status=("${PIPESTATUS[@]}")
  _tidy_rc=${_tidy_status[0]}
  _check_package_capture "$_tidy_rc" "${_tidy_status[1]}" "go mod tidy"
  if [[ $_tidy_rc -ne 0 ]]; then
    if [[ $_tidy_rc -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
      echo "TRANSIENT_ERROR: mod tidy failed with exit $_tidy_rc (timeout or network error)"
      rm -f "$_GO_GET_LOG"
      git checkout -- . 2>/dev/null || true
      exit 5
    fi
    echo "ERROR: go mod tidy failed with exit $_tidy_rc for $pkg in $moddir"
    git checkout -- . 2>/dev/null || true
    PRIMARY_UPDATE_FAILED=true
    return 0
  fi
  _POST_INSTALLED=$(get_installed_version "$moddir" "$pkg" 2>/dev/null || true)
  if [[ -n "$_POST_INSTALLED" ]] && ! version_gte "$_POST_INSTALLED" "$ver"; then
    echo "WARNING: $pkg — MVS resolved $pkg@$_POST_INSTALLED (needed >= $ver)"
    PRIMARY_STILL_VULNERABLE=true
    # Capture diagnostic info for better error reporting (globals survive function return)
    VULNERABLE_RESOLVED_VERSION="$_POST_INSTALLED"
    VULNERABLE_REQUIRED_VERSION="$ver"
  fi
}

# Record selected-target major crossings before any in-scope module changes.
# A local/unknown version is not major zero. Preserve its existing handling,
# and distinguish an unverifiable graph from a confirmed policy boundary.
_TARGET_MAJOR_BREAKING=""
_TARGET_MAJOR_UNVERIFIED=""
_TARGET_MAJOR="${VERSION%%.*}"
if [[ "$_TARGET_MAJOR" =~ ^[0-9]+$ && "$_TARGET_MAJOR" != 0 ]]; then
  while IFS= read -r _target_gomod; do
    _target_installed=$(get_installed_version "$(dirname "$_target_gomod")" "$PACKAGE" 2>/dev/null || true)
    [[ -n "$_target_installed" ]] || continue
    _target_installed_major="${_target_installed%%.*}"
    version_gte "$_target_installed_major.0.0" "$_TARGET_MAJOR.0.0" && continue
    _target_resolve_rc=0
    resolve_module_dependency "$(dirname "$_target_gomod")" "$PACKAGE" || _target_resolve_rc=$?
    case "$_target_resolve_rc" in
      0)
        if [[ ! "$RESOLVED_VERSION" =~ ^[0-9]+[.][0-9]+[.][0-9]+(-[0-9A-Za-z.-]+)?([+][0-9A-Za-z.-]+)?$ ]]; then
          _TARGET_MAJOR_UNVERIFIED="${_TARGET_MAJOR_UNVERIFIED:+$_TARGET_MAJOR_UNVERIFIED; }$_target_gomod"
        elif ! version_gte "${RESOLVED_VERSION%%.*}.0.0" "$_TARGET_MAJOR.0.0"; then
          _TARGET_MAJOR_BREAKING="${_TARGET_MAJOR_BREAKING:+$_TARGET_MAJOR_BREAKING; }$_target_gomod: $PACKAGE v$RESOLVED_VERSION -> v$VERSION"
        fi
        ;;
      1|3) : ;; # absent or local replacement: retain existing fix/verification handling
      *) _TARGET_MAJOR_UNVERIFIED="${_TARGET_MAJOR_UNVERIFIED:+$_TARGET_MAJOR_UNVERIFIED; }$_target_gomod" ;;
    esac
  done < <(_iter_gomods)
fi

# Update direct and transitive dependencies in the selected module scope. A Grype
# location limits which go.mod may change; it does not mean the package must be a
# textual require in that file. The effective MVS graph is authoritative.
while IFS= read -r GOMOD; do
  MODDIR=$(dirname "$GOMOD")
  if gomod_has_module_reference "$GOMOD" "$PACKAGE"; then
    INSTALLED=$(get_installed_version "$MODDIR" "$PACKAGE")
    if [[ -z "$INSTALLED" ]]; then
      : # substring-only match (sibling module); not a direct dep here — skip
    elif version_gte "$INSTALLED" "$VERSION"; then
      echo "NOTE: $GOMOD already has $PACKAGE v$INSTALLED (>= v$VERSION)"
    else
      echo "Updating $PACKAGE in $GOMOD..."
      _go_get_and_check "$MODDIR" "$PACKAGE" "$VERSION"
    fi
  else
    RESOLVE_RC=0
    resolve_module_dependency "$MODDIR" "$PACKAGE" || RESOLVE_RC=$?
    case "$RESOLVE_RC" in
    0)
      if ! version_gte "$RESOLVED_VERSION" "$VERSION"; then
        echo "Updating transitive dep $PACKAGE v$RESOLVED_VERSION in $GOMOD..."
        _go_get_and_check "$MODDIR" "$PACKAGE" "$VERSION"
      fi
      ;;
    1) : ;; # not in this module's effective graph
    2)
      echo "ERROR: could not resolve $PACKAGE in $GOMOD: ${RESOLVE_ERROR:-unknown graph error}"
      PRIMARY_UPDATE_FAILED=true
      ;;
    3)
      echo "NEEDS_REVIEW: $PACKAGE — local replace in $GOMOD has no verifiable fixed version"
      PRIMARY_UPDATE_FAILED=true
      ;;
    esac
  fi
done < <(_iter_gomods)

# Exit 4 when the candidate cannot resolve at the current Go module path.
# This does not prove that the advisory lacks a published fix: a product tag
# may differ from its Go module version, or another candidate may be available.
# Callers retain the findings for review without generating no-fix ignores.
#
# Exception: when the installed version uses +incompatible and the fix version
# changes the major integer (e.g. docker/docker v28→v29), the module path or
# API changed at the major boundary and the version may require a source
# migration. Emit INCOMPATIBLE_MAJOR_BUMP so the caller leaves it actionable as
# NEEDS_REVIEW rather than creating any vulnerability ignore.
if [[ "$MODULE_NOT_IN_PROXY" == true ]]; then
  $MAJOR_PATH_CHANGE && echo "INCOMPATIBLE_MAJOR_BUMP: $PACKAGE v$VERSION moved to a /v${VERSION%%.*} module path"
  while ! $MAJOR_PATH_CHANGE && IFS= read -r GOMOD; do
    if gomod_has_module_reference "$GOMOD" "$PACKAGE" +incompatible; then
      _cur=$(get_installed_version "$(dirname "$GOMOD")" "$PACKAGE" 2>/dev/null || true)
      if [[ -n "$_cur" ]]; then
        _inst_maj="${_cur%%.*}"
        _fix_maj="${VERSION%%.*}"
        if [[ "$_fix_maj" =~ ^[0-9]+$ ]] && [[ "$_inst_maj" =~ ^[0-9]+$ ]] && \
           [[ "$_fix_maj" -gt "$_inst_maj" ]] 2>/dev/null; then
          echo "INCOMPATIBLE_MAJOR_BUMP: $PACKAGE v${_inst_maj} -> v${_fix_maj}"
          break
        fi
      fi
    fi
  done < <(_iter_gomods)
  $MAJOR_PATH_CHANGE || echo "NOTE: fix version v$VERSION for $PACKAGE not available in Go module registry"
  rm -f "$_GO_GET_LOG"
  git checkout -- . 2>/dev/null || true
  exit 4
fi
# Preserve registry, failed updates and below-target MVS results. Unverifiable evidence is
# not a policy exemption, even when another module has a known major crossing.
if ! $PRIMARY_UPDATE_FAILED && ! $PRIMARY_STILL_VULNERABLE; then
  if [[ -n "$_TARGET_MAJOR_UNVERIFIED" ]]; then
    echo "ERROR: $PACKAGE — effective installed version could not be verified in $_TARGET_MAJOR_UNVERIFIED"
    exit 3
  fi
fi
clean_gomod

# Synchronization can change sibling requirements, so regenerate affected vendor
# trees and build only after it completes. Policy is rechecked before staging.
# Go work sync ignores -mod in GOFLAGS; graph queries retain module-mode flags,
# while the native build below restores the caller's flags.
if git ls-files --error-unmatch go.work >/dev/null 2>&1; then
  declare -A _SYNC_GOMOD_BEFORE=()
  while IFS= read -r _sync_gomod; do
    _SYNC_GOMOD_BEFORE["$_sync_gomod"]=$(git hash-object -- "$_sync_gomod")
  done < <(find_gomods)
  _sync_rc=0
  _sync_status=(0 0)
  if ! validate_go_metadata; then
    echo "NEEDS_REVIEW: $PACKAGE — workspace members changed outside the owned transaction"
    exit 2
  fi
  env GOWORK="$PWD/go.work" timeout "${GO_GET_TIMEOUT:-120}" go work sync -modfile= -overlay= \
    2>&1 | tee -a "$_GO_GET_LOG" || _sync_status=("${PIPESTATUS[@]}")
  _sync_rc=${_sync_status[0]}
  _check_package_capture "$_sync_rc" "${_sync_status[1]}" "go work sync"
  if [[ $_sync_rc -ne 0 ]]; then
    if [[ $_sync_rc -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
      echo "TRANSIENT_ERROR: go work sync failed with exit $_sync_rc (timeout or network error)"
      exit 5
    fi
    echo "NEEDS_REVIEW: $PACKAGE — go work sync failed with exit $_sync_rc"
    exit 2
  fi
  # Sync can leave checksums in go.work.sum rather than a sibling's go.sum.
  # Refresh only modules it changed before re-pinning and module-mode vendoring.
  for _sync_gomod in "${!_SYNC_GOMOD_BEFORE[@]}"; do
    [[ "$(git hash-object -- "$_sync_gomod")" != "${_SYNC_GOMOD_BEFORE[$_sync_gomod]}" ]] || continue
    _sync_tidy_rc=0
    _sync_tidy_status=(0 0)
    module_go "$(dirname "$_sync_gomod")" mod tidy \
      2>&1 | tee -a "$_GO_GET_LOG" || _sync_tidy_status=("${PIPESTATUS[@]}")
    _sync_tidy_rc=${_sync_tidy_status[0]}
    _check_package_capture "$_sync_tidy_rc" "${_sync_tidy_status[1]}" "workspace go mod tidy"
    if [[ $_sync_tidy_rc -ne 0 ]]; then
      if [[ $_sync_tidy_rc -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
        echo "TRANSIENT_ERROR: workspace mod tidy failed with exit $_sync_tidy_rc (timeout or network error)"
        exit 5
      fi
      echo "NEEDS_REVIEW: $PACKAGE — workspace mod tidy failed in $_sync_gomod (exit $_sync_tidy_rc)"
      exit 2
    fi
  done
fi

# Re-pin indirect deps that were downgraded (or removed) by go mod tidy.
# Iterates each module and restores any package whose version fell below the
# pre-update snapshot — preventing silent re-introduction of patched CVEs.
if [[ "${#_INDIRECT_BEFORE[@]}" -gt 0 ]]; then
  while IFS= read -r GOMOD; do
    MODDIR=$(dirname "$GOMOD")
    _local_repinned=false
    for _key in "${!_INDIRECT_BEFORE[@]}"; do
      [[ "$_key" == "$MODDIR:"* ]] || continue
      _pkg="${_key#"$MODDIR:"}"
      _old="${_INDIRECT_BEFORE[$_key]}"
      _cur=$(get_installed_version "$MODDIR" "$_pkg" 2>/dev/null || true)
      if [[ -z "$_cur" ]] && \
         ! module_go "$MODDIR" list -m "$_pkg" 2>/dev/null | grep -q .; then
        echo "INFO: $_pkg removed from module graph after fix — not a CVE risk, skipping re-pin"
        continue
      fi
      if [[ -z "$_cur" ]] || ! version_gte "$_cur" "$_old"; then
        echo "WARNING: $_pkg downgraded in $GOMOD (v${_old} -> v${_cur:-removed}); re-pinning to v${_old}..."
        _REPIN_RC=0
        _repin_status=(0 0)
        module_go "$MODDIR" get "${_pkg}@v${_old}" \
          2>&1 | tee -a "$_GO_GET_LOG" || _repin_status=("${PIPESTATUS[@]}")
        _REPIN_RC=${_repin_status[0]}
        _check_package_capture "$_REPIN_RC" "${_repin_status[1]}" "indirect go get"
        if [[ $_REPIN_RC -eq 0 ]]; then
          _repin_tidy_rc=0
          _repin_tidy_status=(0 0)
          module_go "$MODDIR" mod tidy 2>&1 | tee -a "$_GO_GET_LOG" || _repin_tidy_status=("${PIPESTATUS[@]}")
          _repin_tidy_rc=${_repin_tidy_status[0]}
          _check_package_capture "$_repin_tidy_rc" "${_repin_tidy_status[1]}" "indirect go mod tidy"
          if [[ $_repin_tidy_rc -ne 0 ]]; then
            if [[ $_repin_tidy_rc -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
              echo "TRANSIENT_ERROR: re-pin mod tidy failed with exit $_repin_tidy_rc (timeout or network error)"
              rm -f "$_GO_GET_LOG"
              git checkout -- . 2>/dev/null || true
              exit 5
            fi
            echo "WARNING: re-pin mod tidy failed with exit $_repin_tidy_rc"
            REPIN_FAILED_INDIRECT=true
            [[ -z "$REPIN_FAILED_PKG" ]] && REPIN_FAILED_PKG="$_pkg"
            continue
          fi
          _after_repin=$(get_installed_version "$MODDIR" "$_pkg" 2>/dev/null || true)
          if [[ -z "$_after_repin" ]] && \
             ! module_go "$MODDIR" list -m "$_pkg" 2>/dev/null | grep -q .; then
            echo "INFO: $_pkg removed from module graph after re-pin tidy — not a CVE risk, skipping"
            continue
          fi
          if [[ -z "$_after_repin" ]] || ! version_gte "$_after_repin" "$_old"; then
            echo "WARNING: $_pkg downgrade persisted after re-pin attempt (v${_after_repin:-removed}, needed >= v${_old})"
            REPIN_FAILED_INDIRECT=true
            [[ -z "$REPIN_FAILED_PKG" ]] && REPIN_FAILED_PKG="$_pkg"
          else
            _local_repinned=true
          fi
        else
          if [[ $_REPIN_RC -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
            echo "TRANSIENT_ERROR: re-pin go get failed with exit $_REPIN_RC (timeout or network error)"
            rm -f "$_GO_GET_LOG"
            git checkout -- . 2>/dev/null || true
            exit 5
          fi
          echo "WARNING: re-pin of $_pkg failed with exit $_REPIN_RC"
          REPIN_FAILED_INDIRECT=true
          [[ -z "$REPIN_FAILED_PKG" ]] && REPIN_FAILED_PKG="$_pkg"
        fi
      fi
    done
    if [[ "$_local_repinned" == true ]]; then
      clean_gomod
    fi
  done < <(find_gomods)
fi

for _vendor_dir in "${_VENDOR_DIRS[@]}"; do
  _vendor_moddir="${_vendor_dir%/vendor}"
  [[ "$_vendor_dir" != vendor ]] || _vendor_moddir=.
  # A scoped update must not regenerate unrelated module trees. Include any
  # sibling actually changed by indirect re-pinning, or tracked vendor cleanup.
  if git diff --quiet HEAD -- "$_vendor_moddir/go.mod" "$_vendor_moddir/go.sum" "$_vendor_dir"; then
    continue
  fi
  echo "Syncing vendor directory in $_vendor_moddir..."
  _vendor_rc=0
  _vendor_status=(0 0)
  module_go "$_vendor_moddir" mod vendor 2>&1 | tee -a "$_GO_GET_LOG" || _vendor_status=("${PIPESTATUS[@]}")
  _vendor_rc=${_vendor_status[0]}
  _check_package_capture "$_vendor_rc" "${_vendor_status[1]}" "go mod vendor"
  if [[ $_vendor_rc -ne 0 ]]; then
    if [[ $_vendor_rc -eq 124 ]] || grep -qiE "$SCAN_TRANSIENT_RE" "$_GO_GET_LOG" 2>/dev/null; then
      echo "TRANSIENT_ERROR: go mod vendor failed with exit $_vendor_rc (timeout or network error)"
      rm -f "$_GO_GET_LOG"
      git checkout -- . 2>/dev/null || true
      exit 5
    fi
    echo "WARNING: go mod vendor failed with exit $_vendor_rc"
    exit 1
  fi
  _vendor_check_rc=0
  _vendor_check_status=(0 0)
  module_go "$_vendor_moddir" list -mod=vendor -m 2>&1 | tee -a "$_GO_GET_LOG" || _vendor_check_status=("${PIPESTATUS[@]}")
  _vendor_check_rc=${_vendor_check_status[0]}
  _check_package_capture "$_vendor_check_rc" "${_vendor_check_status[1]}" "vendor verification"
  if [[ $_vendor_check_rc -ne 0 ]]; then
    echo "NEEDS_REVIEW: $PACKAGE — vendor metadata is inconsistent in $_vendor_moddir"
    exit 2
  fi
done

# A dependency's patch can break one of its callers without changing Go or K8s
# versions (for example NTLM's ProcessChallenge gained an argument while an old
# LDAP caller retained three). Validate the actual project build before keeping
# that update. Reuse the scanner's artifact tracking so every later scan rebuilds
# outputs produced during a rejected or superseded package update.
if [[ -n "${BUILD_CMD:-}" ]]; then
  echo "Verifying project build after updating $PACKAGE..."
  build_env_scrub
  artifact_manifest_prepare
  _PACKAGE_BUILD_RC=0
  _PACKAGE_BUILD_STATUS=(0 0)
  (
    # Resolution uses module mode internally; native builds retain the caller's
    # environment (or their own defaults). Apply ENV_UNSET after restoration.
    if [[ "$_BUILD_GOFLAGS_SET" == x ]]; then export GOFLAGS="$_BUILD_GOFLAGS"
    else unset GOFLAGS
    fi
    if [[ "$_BUILD_GOWORK_SET" == x ]]; then export GOWORK="$_BUILD_GOWORK"
    else unset GOWORK
    fi
    if [[ "$_BUILD_GOTOOLCHAIN_SET" == x ]]; then export GOTOOLCHAIN="$_BUILD_GOTOOLCHAIN"
    else unset GOTOOLCHAIN
    fi
    "${ENV_SCRUB[@]+"${ENV_SCRUB[@]}"}" env ${BUILD_REPO_NAME:+REPO="$BUILD_REPO_NAME"} \
      MAKEFLAGS=-B timeout --foreground "${CVE_FIX_BUILD_TIMEOUT:-1800}" bash -c "$BUILD_CMD"
  ) \
    2>&1 | tee -a "$_GO_GET_LOG" || _PACKAGE_BUILD_STATUS=("${PIPESTATUS[@]}")
  _PACKAGE_BUILD_RC=${_PACKAGE_BUILD_STATUS[0]}
  artifact_manifest_record
  _check_package_capture "$_PACKAGE_BUILD_RC" "${_PACKAGE_BUILD_STATUS[1]}" "project build"
  if [[ "$_PACKAGE_BUILD_RC" -ne 0 ]]; then
    if is_scan_transient "$_GO_GET_LOG"; then
      echo "TRANSIENT_ERROR: project build could not verify $PACKAGE (exit $_PACKAGE_BUILD_RC)"
      exit 5
    fi
    echo "NEEDS_REVIEW: $PACKAGE — project build failed after dependency update (exit $_PACKAGE_BUILD_RC)"
    exit 2
  fi
fi

# Recheck policy after tidy/vendor/re-pinning: those commands can change the Go
# directive after the earlier go-get guard. Go directive bumps are safe if the
# detected build image satisfies the exact requirement (including patch). With
# unknown builder evidence, only same-minor bumps are automatically accepted.
# K8s minor version changes are genuinely breaking (different API versions).
COMPILER_GO=$(compiler_go_version)
BREAKING=""
for GOMOD in "${!_GO_BEFORE[@]}"; do
  GO_WAS="${_GO_BEFORE[$GOMOD]}"
  GO_AFTER=$(grep '^go ' "$GOMOD" 2>/dev/null | awk '{print $2}')
  [[ -z "$GO_AFTER" ]] && continue
  if [[ "$GO_WAS" != "$GO_AFTER" ]]; then
    if go_directive_supported "$GO_WAS" "$GO_AFTER" "$COMPILER_GO" "${GO_MINOR_GUARD:-false}"; then
      if [[ -n "$COMPILER_GO" ]]; then
      echo "NOTE: $GOMOD Go $GO_WAS -> $GO_AFTER (safe: build image has Go $COMPILER_GO)"
      else
        echo "NOTE: $GOMOD Go $GO_WAS -> $GO_AFTER (same minor; build image version unknown)"
      fi
    else
      BREAKING="${BREAKING:+$BREAKING; }$GOMOD: Go $GO_WAS -> $GO_AFTER exceeds repository/builder policy (go-minor-guard=${GO_MINOR_GUARD:-false})"
    fi
  fi
done

if [[ "${K8S_VERSION_GUARD:-false}" == "true" ]]; then
  K8S_AFTER=$(_k8s_minor_versions)
  if [[ -n "$K8S_BEFORE" ]] && [[ -n "$K8S_AFTER" ]] && [[ "$K8S_BEFORE" != "$K8S_AFTER" ]]; then
    BREAKING="${BREAKING:+$BREAKING; }K8s minor versions changed"
  else
    # Workspace sync can change siblings outside a scoped update. Compare every
    # tracked module against the existing transaction snapshot after all syncs.
    while IFS= read -r GOMOD; do
      _K8S_PAIR_RC=0
      _k8s_minor_pairs_unchanged "$_DEPENDENCY_SNAPSHOT/$GOMOD" "$GOMOD" || _K8S_PAIR_RC=$?
      if [[ "$_K8S_PAIR_RC" -eq 1 ]]; then
        BREAKING="${BREAKING:+$BREAKING; }$GOMOD: K8s minor versions changed"
        break
      elif [[ "$_K8S_PAIR_RC" -ne 0 ]]; then
        BREAKING="${BREAKING:+$BREAKING; }$GOMOD: K8s minor versions could not be verified"
        break
      fi
    done < <(find_gomods)
  fi
fi

if [[ -n "$BREAKING" ]]; then
  echo "NEEDS_REVIEW: $PACKAGE — would upgrade $BREAKING"
  git checkout -- . || echo "ERROR: Could not rollback changes" >&2
  exit 2
fi

# Verify fix against the resolved module graph, including transitive dependencies
# that do not appear textually in go.mod.
# Scoped to the same modules as the fix loop (_iter_gomods) so a transitive occurrence
# in another module (e.g. tools at v1.67.3 when root was fixed to v1.83.1) does not
# set PRIMARY_STILL_VULNERABLE and roll back the successful root fix.
while IFS= read -r GOMOD; do
  MODDIR=$(dirname "$GOMOD")
  if gomod_has_module_reference "$GOMOD" "$PACKAGE"; then
    # Preserve direct/replace checks for textual entries. This avoids an
    # unnecessary graph download and keeps local replace semantics visible in
    # offline or otherwise hermetic environments.
    INSTALLED=$(get_installed_version "$MODDIR" "$PACKAGE")
    if [[ -z "$INSTALLED" ]]; then
      if grep -E "^[[:space:]]*replace[[:space:]]" "$GOMOD" 2>/dev/null | \
         grep -qF "$PACKAGE" 2>/dev/null; then
        echo "WARNING: $GOMOD has $PACKAGE pinned by replace directive — effective version unverifiable"
        PRIMARY_STILL_VULNERABLE=true
      fi
    elif version_gte "$INSTALLED" "$VERSION"; then
      _EFFECTIVE=$(module_go "$MODDIR" list -m -f '{{if .Replace}}{{.Replace.Version}}{{end}}' \
        "$PACKAGE" 2>/dev/null || true)
      _EFFECTIVE="${_EFFECTIVE#v}"
      _LOCAL_REPLACE=$(module_go "$MODDIR" list -m -f '{{if .Replace}}{{.Replace.Dir}}{{end}}' \
        "$PACKAGE" 2>/dev/null || true)
      # A fetched versioned replacement has a cache directory too. Its
      # published Version remains verifiable; local replacements have none.
      if [[ -n "$_LOCAL_REPLACE" && -z "$_EFFECTIVE" ]]; then
        echo "WARNING: $GOMOD has $PACKAGE replace-pinned to local path — effective version unverifiable"
        PRIMARY_STILL_VULNERABLE=true
      elif [[ -n "$_EFFECTIVE" ]] && ! version_gte "$_EFFECTIVE" "$VERSION"; then
        echo "WARNING: $GOMOD has $PACKAGE replace-pinned to v${_EFFECTIVE} (need >= v$VERSION)"
        PRIMARY_STILL_VULNERABLE=true
      fi
    else
      echo "WARNING: $GOMOD has $PACKAGE at v${INSTALLED:-unknown} (need >= v$VERSION)"
      PRIMARY_STILL_VULNERABLE=true
    fi
  else
    RESOLVE_RC=0
    resolve_module_dependency "$MODDIR" "$PACKAGE" || RESOLVE_RC=$?
    case "$RESOLVE_RC" in
    0)
      if ! version_gte "$RESOLVED_VERSION" "$VERSION"; then
        echo "WARNING: $GOMOD has transitive $PACKAGE at v$RESOLVED_VERSION (need >= v$VERSION)"
        PRIMARY_STILL_VULNERABLE=true
      fi
      ;;
    1) : ;; # package is absent from this module's effective graph
    2)
      echo "WARNING: could not verify $PACKAGE in $GOMOD: ${RESOLVE_ERROR:-unknown graph error}"
      PRIMARY_STILL_VULNERABLE=true
      ;;
    3)
      echo "WARNING: $GOMOD has $PACKAGE replaced by a local path — effective version unverifiable"
      PRIMARY_STILL_VULNERABLE=true
      ;;
    esac
  fi
done < <(_iter_gomods)

# Exit logic: Primary CVE must be fixed. Re-pin failures are separate issues.
if [[ "$PRIMARY_UPDATE_FAILED" == "true" || "$PRIMARY_STILL_VULNERABLE" == "true" ]]; then
  if [[ -n "$VULNERABLE_RESOLVED_VERSION" ]]; then
    echo "NEEDS_REVIEW: $PACKAGE — MVS resolved to v$VULNERABLE_RESOLVED_VERSION but need >= v$VULNERABLE_REQUIRED_VERSION"
  else
    echo "NEEDS_REVIEW: $PACKAGE — CVE persists after update to v$VERSION"
  fi
  git checkout -- . || echo "ERROR: Could not rollback changes" >&2
  exit 3
fi

# A policy rejection must not mask a failed or unverifiable primary update.
if [[ -n "$_TARGET_MAJOR_BREAKING" ]]; then
  echo "NEEDS_REVIEW: $PACKAGE — selected fix crosses a major version: $_TARGET_MAJOR_BREAKING"
  exit 2
fi

# If primary fix succeeded but re-pin of indirect deps failed, that's a different issue
# (e.g. architectural dependency constraint). Report it but don't reject the primary fix.
if [[ "$REPIN_FAILED_INDIRECT" == "true" ]]; then
  echo "WARNING: $PACKAGE fix succeeded, but re-pinning indirect deps failed (${REPIN_FAILED_PKG})"
  echo "NEEDS_REVIEW: $PACKAGE — indirect dep constraint (${REPIN_FAILED_PKG}) may affect stability"
  # Note: Don't exit here — the primary fix succeeded. This is a warning, not a blocker.
fi

# Stage all changed go.mod/go.sum files. Use mapfile to collect the list first
# so that an empty list skips git add entirely (avoiding a bare "git add" that
# would be a no-op on some platforms but could error on others). This also lets
# real "git add" failures propagate to the ERR trap instead of being silenced by
# || true, which would leave the fix unstaged and reported as FIXED while clean.
# Restore only after every graph lookup, vendor operation and workspace sync.
# Even go list -mod=mod can rewrite incidental toolchain metadata; restoring it
# earlier would both obstruct vendor and let later commands silently change it.
_restore_toolchain_directives
clean_gomod
if [[ -n "$_PACKAGE_SCAN_BEFORE" ]]; then
  _PACKAGE_SCAN_AFTER=$(mktemp "${TMPDIR:-/tmp}/cve-package-after.XXXXXX")
  if ! _package_scan "$_PACKAGE_SCAN_AFTER"; then
    echo "NEEDS_REVIEW: $PACKAGE — source scan could not verify dependency update"
    exit 2
  fi
  _BEFORE_FINDINGS=$(grype_source_findings "$_PACKAGE_SCAN_BEFORE") || exit 2
  _AFTER_FINDINGS=$(grype_source_findings "$_PACKAGE_SCAN_AFTER") || exit 2
  # A different release stream can remain affected above the original fix
  # threshold. Current findings, including ignored ones, override version order.
  _REQUESTED_IDS=$(printf '%s\n' "${CVE_IDS[@]}" | jq -R . | jq -s .)
  _PERSISTING_REQUESTED=$(jq -c --arg pkg "$PACKAGE" --arg location "$FIX_LOCATION" \
    --argjson ids "$_REQUESTED_IDS" '
    [.[] | select(.[1] == $pkg and ($location == "" or .[2] == $location)) |
      .[0] as $id | select($ids | index($id))]
    ' <<< "$_AFTER_FINDINGS") || exit 2
  if [[ "$_PERSISTING_REQUESTED" != '[]' ]]; then
    echo "NEEDS_REVIEW: $PACKAGE — requested CVEs remain in the updated source scan; reverting dependency update"
    jq -r '.[] | "STILL_VULNERABLE: \(.[0]) (\(.[1])) location:\(.[2])"' <<< "$_PERSISTING_REQUESTED"
    # The installed version matched only one affected range; the updated scan
    # shows the advisory's thresholds for the version just rejected. Report
    # those above it so the orchestrator can retry once.
    while read -r _retry_cve _retry_versions; do
      _retry_above=()
      for _retry_v in ${_retry_versions//,/ }; do
        _retry_v="${_retry_v#v}"
        module_fix_version_usable "$_retry_v" && [[ "$_retry_v" != "$VERSION" ]] &&
          version_gte "$_retry_v" "$VERSION" && _retry_above+=("$_retry_v")
      done
      [[ ${#_retry_above[@]} -eq 0 ]] || echo "RETRY_FIX: $_retry_cve $(IFS=,; echo "${_retry_above[*]}")"
    done < <(jq -r --arg pkg "$PACKAGE" --arg location "$FIX_LOCATION" --argjson ids "$_REQUESTED_IDS" '
      def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
      [((.matches // []) + (.ignoredMatches // []))[] | select(.artifact.name == $pkg) |
        select($location == "" or any(.artifact.locations[]?; (.path | normloc) == $location)) |
        .vulnerability as $v | select($ids | index($v.id)) |
        {cve: $v.id, versions: ($v.fix.versions // [])}] |
      group_by(.cve)[] | "\(.[0].cve) \([.[].versions[]] | unique | join(","))"
      ' "$_PACKAGE_SCAN_AFTER" || true)
    exit 2
  fi
  # Unignored findings in other packages that this update also resolved, as
  # "package|advisory", so the commit message credits them.
  _ALSO_FIXED=$(jq -r --arg pkg "$PACKAGE" --argjson after "$_AFTER_FINDINGS" '
    def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
    [(.matches // [])[] | select(.artifact.type == "go-module" and .artifact.name != $pkg) |
      . as $m | .artifact.locations[]? | [$m.vulnerability.id, $m.artifact.name, (.path | normloc)] |
      select(.[2] | endswith("go.mod")) | . as $k | select($after | any(. == $k) | not) |
      "\(.[1])|\(.[0])"] | unique | .[]' "$_PACKAGE_SCAN_BEFORE") || _ALSO_FIXED=""
  _NEW_FINDINGS=$(jq -cn --argjson before "$_BEFORE_FINDINGS" \
    --argjson after "$_AFTER_FINDINGS" '$after - $before') || exit 2
  if [[ "$_NEW_FINDINGS" != '[]' ]]; then
    echo "NEEDS_REVIEW: $PACKAGE — update introduces new source findings; reverting dependency update"
    jq -r '.[] | "NEW_FINDING: \(.[0]) (\(.[1])) location:\(.[2])"' <<< "$_NEW_FINDINGS"
    exit 2
  fi
fi
stage_gomod_files
# A successful first update may create go.sum in a library that did not yet
# track one. Stage only newly created metadata, respecting repository ignores.
for _metadata in "${!_DEPENDENCY_BEFORE[@]}"; do
  if [[ "${_DEPENDENCY_BEFORE[$_metadata]}" == absent && -f "$_metadata" ]] &&
     ! git check-ignore -q -- "$_metadata"; then
    git add -- "$_metadata"
  fi
done

# Generated files left dirty by the scan build: discard tool-version noise,
# keep substantive changes (CI tolerates the former via git diff -I).
reconcile_generated_files

# If nothing to commit, the CVE was already fixed by a prior package upgrade
if ! git diff --staged --quiet 2>/dev/null; then
  # Determine if tools-only change (all staged go files under tools/)
  TOOLS_ONLY=""
  if ! git diff --staged --name-only | grep -qE '^go\.(mod|sum)$' && \
       git diff --staged --name-only | grep -qE '^tools/'; then
    TOOLS_ONLY=" in /tools"
  fi

  # Format commit message (subject must be <=50 chars per commit conventions)
  ABBREV=$(abbreviate_package "$PACKAGE")
  SUBJECT="Bump ${ABBREV} for ${CVE_IDS[0]}${TOOLS_ONLY}"
  if [[ ${#SUBJECT} -le 50 ]] && [[ ${#CVE_IDS[@]} -eq 1 ]]; then
    BODY="Full package: $PACKAGE"
  else
    # Multi-CVE format: CVE IDs move to body Fixes: line
    SUBJECT="Bump ${ABBREV} for CVEs${TOOLS_ONLY}"
    FIXES_LINE=$(format_cve_fixes "${CVE_IDS[@]}")
    BODY="Full package: $PACKAGE
$FIXES_LINE"
    if [[ ${#SUBJECT} -gt 50 ]]; then
      ABBREV=$(abbreviate_package "$PACKAGE" "$((50 - ${#SUBJECT} + ${#ABBREV}))")
      SUBJECT="Bump ${ABBREV} for CVEs${TOOLS_ONLY}"
      [[ -z "$FIX_LOCATION" ]] || BODY+=$'\n'"Module: $FIX_LOCATION"
    fi
  fi
  _also_pkg=""
  while IFS='|' read -r _pkg _cve; do
    [[ -n "$_pkg" ]] || continue
    [[ "$_pkg" == "$_also_pkg" ]] && BODY+=", $_cve" || BODY+=$'\n'"Also fixes, in $_pkg: $_cve"
    _also_pkg="$_pkg"
  done <<< "${_ALSO_FIXED:-}"
  # A required go directive change matters on release branches; say so.
  while IFS= read -r _gm; do
    _was=$(git show "HEAD:$_gm" 2>/dev/null | awk '$1 == "go" { print $2; exit }')
    _now=$(git show ":$_gm" 2>/dev/null | awk '$1 == "go" { print $2; exit }')
    [[ -n "$_was" && -n "$_now" && "$_was" != "$_now" ]] || continue
    BODY+=$'\n'"Raises go in $_gm from $_was to $_now, as v$VERSION requires."
  done < <(git diff --staged --name-only | grep -E '(^|/)go\.mod$')

  if ! git commit -s -m "$(printf '%s\n\n%s' "$SUBJECT" "$BODY")"; then
    # git commit creates .git/index.lock, which can still be present when the
    # commit fails (e.g. hook failure, concurrent git process). Wait briefly for
    # it to clear before attempting to unstage, otherwise git reset also fails.
    for _i in 1 2 3 4 5; do
      [[ ! -f .git/index.lock ]] && break
      sleep 1
    done
    git reset HEAD -- . 2>/dev/null || git restore --staged . 2>/dev/null || true
    die "git commit failed for $PACKAGE (possible index lock; retry after other git processes complete)"
  fi
else
  echo "NOTE: $PACKAGE already at v$VERSION (fixed by prior upgrade)"
fi

echo "FIXED: $PACKAGE v$VERSION for ${CVE_IDS[*]}"
