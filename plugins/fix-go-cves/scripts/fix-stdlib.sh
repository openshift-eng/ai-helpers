#!/usr/bin/env bash
# Fix stdlib CVEs by setting the go.mod toolchain directive.
# Usage: fix-stdlib.sh STATE_FILE GO_VERSION ALL_FIX_VERSIONS CVE_ID [CVE_ID...]
# Exit 0: fixed. Exit 2: needs review (Go version incompatible).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: fix-stdlib.sh STATE_FILE GO_VERSION ALL_FIX_VERSIONS CVE_ID [CVE_ID...]}"
GO_VERSION="${2:?Missing GO_VERSION}"
ALL_FIX_VERSIONS="${3:-}"
shift 3
CVE_IDS=("$@")
[[ ${#CVE_IDS[@]} -gt 0 ]] || die "At least one CVE_ID required"

load_state "$STATE_FILE"

trap 'git reset --quiet HEAD -- . 2>/dev/null || true; git checkout -- . 2>/dev/null || true' ERR

echo "--- Fixing stdlib: go $GO_VERSION for ${CVE_IDS[*]} ---"

# Workspace builds take their toolchain from go.work, ignoring each module's.
if git ls-files --error-unmatch go.work >/dev/null 2>&1; then
  echo "NEEDS_REVIEW: stdlib — go.work selects the toolchain for workspace builds; update its toolchain directive or the build image"
  exit 2
fi

# Select from the lowest effective compiler floor across repository modules.
# A library may keep go 1.18 while selecting toolchain go1.26; its language floor
# must not select an obsolete fix stream or reject a same-stream compiler patch.
# A newer root must likewise not hide an older tools module.
declare -A EFFECTIVE_GO=()
declare -A TOOLCHAIN_NAMES=()
REF_GO=""
while IFS= read -r GOMOD; do
  CUR_GO=$(gomod_effective_go "$(dirname "$GOMOD")")
  EFFECTIVE_GO["$GOMOD"]="$CUR_GO"
  TOOLCHAIN_NAMES["$GOMOD"]=$(gomod_toolchain "$(dirname "$GOMOD")")
  if [[ -z "$REF_GO" ]] || version_gte "$REF_GO" "$CUR_GO"; then
    REF_GO="$CUR_GO"
  fi
done < <(find_gomods)
[[ -n "$REF_GO" ]] || die "No tracked Go modules found"

# Prefer the build image's release stream when known.
COMPILER_GO=$(compiler_go_version)
REF_MINOR=$(echo "${COMPILER_GO:-$REF_GO}" | cut -d. -f1-2)

# toolchain was introduced in Go 1.21. An older builder cannot parse this
# directive, even when its patch version already includes the requested fix.
if [[ -n "$COMPILER_GO" ]] && ! version_gte "$COMPILER_GO" 1.21.0; then
  echo "NEEDS_REVIEW: stdlib — build image has Go $COMPILER_GO, which cannot read a toolchain directive (needs Go 1.21+)"
  exit 2
fi

# Returns 0 (true) if the version string is a pre-release that should be skipped.
# Excludes Go pseudo-versions (14-digit timestamp), which are not pre-releases.
_is_go_prerelease() {
  local v="$1"
  { [[ "$v" == *-* ]] && ! [[ "$v" =~ -[0-9]{14}- ]]; } || \
    [[ "$v" =~ [0-9](rc|beta|alpha)[0-9] ]]
}

# When per-CVE requirements are available, select one release stream explicitly
# fixed for every grouped advisory. This prevents a union of unrelated fixed-in
# versions from producing a false stdlib repair.
if [[ -n "${CVE_FIX_REQUIREMENTS_B64:-}" ]]; then
  BEST=""
  if [[ -n "$COMPILER_GO" ]]; then
    # Each advisory must explicitly provide a fix in the builder's stream.
    # Anchor at its initial release, not the builder's patch: a builder newer
    # than the fix is supported and must not force a still newer upgrade.
    STREAM_REQUIREMENTS=$(printf '%s' "$CVE_FIX_REQUIREMENTS_B64" |
      jq -Rr --arg stream "$REF_MINOR" '@base64d | fromjson |
        map(.versions |= map(select(ltrimstr("v") | startswith($stream + ".")))) |
        tojson | @base64')
    BEST=$(select_common_go_fix_version "$REF_MINOR.0" "$STREAM_REQUIREMENTS" || true)
  fi
  [[ -n "$BEST" ]] || BEST=$(select_common_go_fix_version "$REF_GO" "$CVE_FIX_REQUIREMENTS_B64" || true)
  if [[ -z "$BEST" ]]; then
    echo "NEEDS_REVIEW: stdlib — no single Go release stream is explicitly fixed for every grouped CVE"
    exit 2
  fi
  GO_VERSION="$BEST"
# Legacy callers: pick the HIGHEST fix version in the compiler's minor stream. grype's
# fix.versions array is not sorted, so stopping at the first stream match can
# select a patch below one a CVE needs, leaving the stdlib CVE unfixed. Compare
# every candidate with version_gte and keep the greatest.
elif [[ -n "$ALL_FIX_VERSIONS" ]]; then
  IFS=',' read -ra FIX_VERS <<< "$ALL_FIX_VERSIONS"
  BEST=""
  for v in "${FIX_VERS[@]}"; do
    v="${v#v}"                                        # tolerate a 'v' prefix
    _is_go_prerelease "$v" && continue
    [[ "$(echo "$v" | cut -d. -f1-2)" == "$REF_MINOR" ]] || continue
    if [[ -z "$BEST" ]] || version_gte "$v" "$BEST"; then
      BEST="$v"
    fi
  done
  if [[ -n "$BEST" ]]; then
    GO_VERSION="$BEST"
  else
    # All fix candidates were pre-releases; GO_VERSION retains its original value.
    # Validate it is not itself a pre-release before proceeding.
    if _is_go_prerelease "$GO_VERSION"; then
      echo "NEEDS_REVIEW: stdlib — fix version $GO_VERSION is a pre-release with no stable alternative in stream $REF_MINOR"
      exit 2
    fi
  fi
fi

NEW_MINOR=$(echo "$GO_VERSION" | cut -d. -f1-2)

# A Go toolchain fix must be a stable Go release, never a module pseudo-version.
if [[ ! "$GO_VERSION" =~ ^[0-9]+[.][0-9]+([.][0-9]+)?$ ]]; then
  echo "NEEDS_REVIEW: stdlib — fix version $GO_VERSION is not a stable Go release"
  exit 2
fi

# Confirm the build image is at or above the exact fixed version. The directive
# may be in an older stream than the compiler (for example go 1.25 with a 1.26
# builder); the policy is an upper bound, not stream equality.
if [[ -n "$COMPILER_GO" ]]; then
  if ! version_gte "$COMPILER_GO" "$GO_VERSION"; then
    echo "NEEDS_REVIEW: stdlib — build image has Go $COMPILER_GO, fix needs $GO_VERSION (update build image)"
    exit 2
  fi
else
  echo "NOTE: build image Go version unknown; limiting toolchain edits to same-minor patches"
fi

# The fix is a `toolchain` directive, never a `go` directive. `go` is the minimum
# language version and is inherited by every dependent module, so raising it for
# a stdlib patch forces the bump on consumers of library-like modules and breaks
# GOTOOLCHAIN=local builds ("go.mod requires go >= X"). `toolchain` only selects
# the toolchain used to build this module: it is not propagated to dependents,
# and a local-only build ignores it. Setting it is a pure file edit, so there is
# no `go mod tidy`, vendor sync or network access, and go.sum is untouched.
echo "Setting toolchain directive to go${GO_VERSION}..."
SKIPPED_MODULES=()
UPDATE_MODULES=()
while IFS= read -r GOMOD; do
  # A module's effective requirement is the greater of its go and toolchain
  # directives; never lower it.
  CUR_GO="${EFFECTIVE_GO[$GOMOD]}"
  # A module in another stream may advance only when the configured build image
  # proves support. Never lower a module already on a newer stream.
  if [[ -n "$CUR_GO" ]]; then
    CUR_MINOR=$(echo "$CUR_GO" | cut -d. -f1-2)
    if [[ "$CUR_MINOR" != "$NEW_MINOR" ]]; then
      if [[ -n "$COMPILER_GO" ]] && go_directive_supported "$CUR_GO" "$GO_VERSION" "$COMPILER_GO" && \
         ! version_gte "$CUR_GO" "$GO_VERSION"; then
        echo "NOTE: $GOMOD toolchain go$GO_VERSION above effective Go $CUR_GO (safe: build image has Go $COMPILER_GO)"
      else
        echo "NOTE: $GOMOD go $CUR_GO is in minor stream $CUR_MINOR, not $NEW_MINOR; leaving as-is"
        if ! version_gte "$CUR_GO" "$GO_VERSION"; then
          SKIPPED_MODULES+=("$GOMOD (effective Go $CUR_GO -> toolchain go$GO_VERSION): cross-minor toolchain change needs build-image evidence")
        else
          SKIPPED_MODULES+=("$GOMOD ($CUR_GO): stream $CUR_MINOR needs its own stdlib fix verification")
        fi
        continue
      fi
    fi
    if version_gte "$CUR_GO" "$GO_VERSION"; then
      echo "NOTE: $GOMOD already at go $CUR_GO (>= $GO_VERSION); leaving as-is"
      continue
    fi
    # Without builder evidence, a pre-1.21 module may be built by a Go that
    # rejects a toolchain line, while any Go that reads it exceeds this fix.
    if [[ -z "$COMPILER_GO" ]] && ! version_gte "$CUR_GO" 1.21.0; then
      SKIPPED_MODULES+=("$GOMOD ($CUR_GO): Go below 1.21 cannot read a toolchain directive")
      continue
    fi
  fi
  # A custom toolchain can encode vendor or compliance policy. Do not replace
  # it with stock Go or invent a custom release whose availability is unknown.
  if [[ "${TOOLCHAIN_NAMES[$GOMOD]}" == go*-* ]]; then
    SKIPPED_MODULES+=("$GOMOD: custom toolchain ${TOOLCHAIN_NAMES[$GOMOD]} needs a vendor-supported fix")
    continue
  fi
  UPDATE_MODULES+=("$GOMOD")
done < <(find_gomods)

if [[ ${#SKIPPED_MODULES[@]} -gt 0 && ${#UPDATE_MODULES[@]} -eq 0 ]]; then
  echo "NEEDS_REVIEW: stdlib — ${SKIPPED_MODULES[*]}"
  exit 2
fi
for GOMOD in "${UPDATE_MODULES[@]+"${UPDATE_MODULES[@]}"}"; do
  set_gomod_toolchain "$(dirname "$GOMOD")" "go${GO_VERSION}"
done

# Stage only the go.mod files that changed: a toolchain edit touches nothing else.
mapfile -t _CHANGED_GOMODS < <(git diff --name-only -- go.mod '*/go.mod')
[[ ${#_CHANGED_GOMODS[@]} -eq 0 ]] || git add -- "${_CHANGED_GOMODS[@]}"

FIXES=$(format_cve_fixes "${CVE_IDS[@]}")
PARTIAL=""
[[ ${#SKIPPED_MODULES[@]} -eq 0 ]] ||
  PARTIAL=$'\n'"Not updated, needs review:"$'\n'"$(printf -- '- %s\n' "${SKIPPED_MODULES[@]}")"$'\n'
if ! git diff --staged --quiet 2>/dev/null; then
  git commit -s -m "$(cat <<EOF
Bump Go to $GO_VERSION for stdlib CVEs

Sets the toolchain directive to go$GO_VERSION to address stdlib
vulnerabilities. The go directive is unchanged, so dependent modules
are not forced to upgrade.
$PARTIAL
$FIXES
EOF
)"
elif [[ ${#SKIPPED_MODULES[@]} -eq 0 ]]; then
  echo "NOTE: stdlib already at go $GO_VERSION (all modules at or above fix version)"
fi

if [[ ${#SKIPPED_MODULES[@]} -gt 0 ]]; then
  echo "NEEDS_REVIEW: stdlib — ${SKIPPED_MODULES[*]}"
  exit 2
fi

echo "FIXED: stdlib go $GO_VERSION for ${CVE_IDS[*]}"
