# shellcheck shell=bash
set -euo pipefail
# Shared functions for CVE fix scripts

# mapfile and other bash 4+ builtins are required
(( BASH_VERSINFO[0] >= 4 )) || { echo "ERROR: bash 4+ required (found: $BASH_VERSION). On macOS: brew install bash" >&2; exit 1; }

# Fatal error: print to stderr and exit. For use in top-level scripts only;
# library functions use `return 1` so callers can decide how to handle errors.
# Functions that produce values write to stdout; functions that test conditions use return 0/1.
die() { echo "ERROR: $*" >&2; exit 1; }

# Compute state file path from repo path and branch name
state_file_path() {
  local repo_basename branch_sanitized
  repo_basename=$(basename "$1")
  branch_sanitized=$(echo "$2" | tr './' '-')
  # A private run directory holds the state file and every "$STATE_FILE.*"
  # sidecar, so other users of a shared temporary directory cannot plant or
  # replace any of them.
  local run_dir
  run_dir=$(mktemp -d "${TMPDIR:-/tmp}/cve-fix-${repo_basename}-${branch_sanitized}.XXXXXX") || return 1
  (umask 077; : > "$run_dir/state.env") || { rmdir "$run_dir"; return 1; }
  printf '%s\n' "$run_dir/state.env"
}

# Load state from file, cd to repo
load_state() {
  local state_file="${1:?Usage: load_state STATE_FILE}"
  if [[ ! -f "$state_file" || -L "$state_file" ]]; then
    echo "ERROR: State file not found: $state_file" >&2
    echo "Run detect.sh first." >&2
    return 1
  fi
  if [[ ! -O "$state_file" ]]; then
    echo "ERROR: Refusing state file not owned by the current user: $state_file" >&2
    return 1
  fi
  # shellcheck source=/dev/null
  source "$state_file"
  [[ -n "${REPO:-}" ]] || die "Corrupt state file: missing REPO — re-run detect.sh to regenerate"
  [[ -n "${BRANCH:-}" ]] || die "Corrupt state file: missing BRANCH — re-run detect.sh to regenerate"
  cd "$REPO" || return 1
  [[ -f go.mod ]] || die "REPO '$REPO' has no go.mod — state file may be corrupt"
}

github_remote_owner() {
  local url="${1:-}"
  # Match GitHub, including its ssh.github.com endpoint for port 443.
  # A non-match emits nothing, never the URL or its embedded credentials.
  local re='^((https?|ssh)://([^/@]+@)?(ssh[.])?github[.]com(:[0-9]+)?/|([^/@]+@)?(ssh[.])?github[.]com:)([A-Za-z0-9][A-Za-z0-9-]*)/.+'
  [[ "${url,,}" =~ $re ]] || return 0
  printf '%s\n' "${BASH_REMATCH[8]}"
}

# Fetch BRANCH from origin into its remote-tracking ref, using exactly the URL
# the repository is configured with. Never rewrite it: public repositories are
# expected to have an HTTPS fetch URL and an SSH pushurl, while private ones
# need SSH to fetch. Fail fast instead of waiting on an SSH passphrase or a
# credential prompt. A configured core.sshCommand is kept, since GIT_SSH_COMMAND
# would otherwise override it.
fetch_origin_branch() {
  local branch="${1:?fetch_origin_branch BRANCH}" ssh_cmd="${GIT_SSH_COMMAND:-}"
  [[ -n "$ssh_cmd" ]] || ssh_cmd=$(git config --get core.sshCommand 2>/dev/null || true)
  if [[ -z "$ssh_cmd" && -n "${GIT_SSH:-}" ]]; then
    # GIT_SSH names one executable, unlike the shell command GIT_SSH_COMMAND.
    # Quote it for Git's shell so paths with spaces/apostrophes stay one argv.
    ssh_cmd="'${GIT_SSH//\'/\'\\\'\'}'"
  fi
  [[ -n "$ssh_cmd" ]] || ssh_cmd=ssh
  GIT_SSH_COMMAND="$ssh_cmd -o BatchMode=yes" GIT_TERMINAL_PROMPT=0 \
    git fetch origin "+refs/heads/$branch:refs/remotes/origin/$branch"
}


# A successful scan can still inspect nothing: Syft skips virtual filesystems
# such as /dev/shm. Its JSON contains matches, not the package inventory. Request
# informational diagnostics and reject an empty catalog when tracked modules
# declare dependencies. A dependency-free library may legitimately catalog zero.
grype_catalog_usable() {
  local errfile="$1" modfile mod_json
  if ! grep -Eq 'gathered packages packages=0([[:space:]]|$)|across 0 packages([[:space:]]|$)' "$errfile"; then
    return 0
  fi
  while IFS= read -r modfile; do
    [[ -n "$modfile" ]] || continue
    if ! mod_json=$(GOTOOLCHAIN=local go -C "$(dirname "$modfile")" mod edit -json 2>/dev/null) ||
        ! jq -e '(.Require // []) | length == 0' <<< "$mod_json" >/dev/null; then
      echo "ERROR: Grype cataloged zero packages despite declared Go dependencies in $modfile; scan coverage is unconfirmed. Move the checkout out of scanner-excluded filesystems or check cataloger exclusions." >&2
      return 1
    fi
  done < <(find_gomods)
}

# Resolve one scanner image for both DB updates and scans. The default release
# is advanced only after scanner fixtures and live verification pass. Callers
# may provide an immutable digest or a mirrored versioned image for their registry.
grype_container_image() {
  local version="${CVE_FIX_GRYPE_VERSION:-v0.112.0}" image="${CVE_FIX_GRYPE_IMAGE:-}"
  version="${version#v}"
  [[ "$version" =~ ^[0-9]+[.][0-9]+[.][0-9]+$ ]] || {
    echo "ERROR: invalid grype release version: $version" >&2
    return 1
  }
  if [[ -z "$image" ]]; then
    if [[ "$version" == 0.112.0 ]]; then
      # The reviewed multi-architecture manifest used in live comparisons.
      image="anchore/grype:v0.112.0@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d"
    else
      image="anchore/grype:v$version"
    fi
  fi
  # Reject mutable latest/implicit tags and shell/option-like input. The image
  # is always passed as one argv element, including private registry references.
  if [[ "$image" == -* || "$image" =~ [[:space:]] ||
        ( "$image" != *@sha256:* && "${image##*/}" != *:* ) ||
        "${image##*:}" == latest ]]; then
    echo "ERROR: grype image must have a version tag or SHA256 digest: $image" >&2
    return 1
  fi
  if [[ "$image" == *@* && ! "$image" =~ @sha256:[[:xdigit:]]{64}$ ]]; then
    echo "ERROR: invalid grype image digest: $image" >&2
    return 1
  fi
  printf '%s\n' "$image"
}

grype_container_version_matches() {
  local runtime="$1" image="$2" version="${3#v}" actual
  [[ -n "$image" ]] || return 1
  if ! actual=$(timeout --foreground "${CVE_FIX_SCAN_TIMEOUT:-600}" \
      "$runtime" run --rm "$image" version -o json) ||
      ! jq -se --arg version "$version" 'length == 1 and .[0].version == $version' <<< "$actual" >/dev/null; then
    echo "ERROR: container scanner $image could not confirm requested grype v$version" >&2
    return 1
  fi
}

# Run grype scan via local install or container fallback
# Usage: run_grype [--fresh] [--no-update] [--json]
# --fresh: ensure DB is up-to-date (grype auto-updates if stale)
# --no-update: skip DB update check (use after a recent --fresh scan)
# --json: output JSON instead of table
run_grype() {
  local fresh=false no_update=false output_format="table"
  for arg in "$@"; do
    case "$arg" in
      --fresh) fresh=true ;;
      --no-update) no_update=true ;;
      --json) output_format="json" ;;
    esac
  done

  # Build config flag (only if .grype.yaml exists)
  local -a config_args=()
  [[ -f .grype.yaml ]] && config_args=(--config .grype.yaml)

  # Reset the DB-degraded and scan-transient signals for this call. Both are globals
  # so scan.sh can read them after run_grype returns. GRYPE_DB_DEGRADED is only set
  # when an update was attempted (with --no-update grype never fetches, so its silence
  # carries no signal). GRYPE_SCAN_TRANSIENT is set when the scanner itself failed with
  # a transient network error — distinct from a permanent failure (bad config, etc.).
  # grype's stderr is captured to inspect for these failures, then replayed.
  # Exported as function outputs for scan.sh; this also makes the contract
  # explicit to static analysis even though callers normally read them in-shell.
  export GRYPE_DB_DEGRADED=0
  export GRYPE_SCAN_TRANSIENT=0
  local errfile outfile
  errfile=$(mktemp "${TMPDIR:-/tmp}/cve-grype-err.XXXXXX")
  outfile=$(mktemp "${TMPDIR:-/tmp}/cve-grype-out.XXXXXX")

  # Prefer local grype (fast, uses host-cached DB); fall back to container on failure
  local use_local="$HAS_LOCAL_GRYPE"
  if [[ "$use_local" == true && -n "${CVE_FIX_GRYPE_VERSION:-}" ]]; then
    if ! grype version -o json 2>/dev/null | jq -se --arg version "${CVE_FIX_GRYPE_VERSION#v}" \
        'length == 1 and .[0].version == $version' >/dev/null; then
      echo "WARNING: local scanner could not confirm requested grype $CVE_FIX_GRYPE_VERSION; trying the pinned container." >&2
      use_local=false
    fi
  fi
  if [[ "$use_local" == "true" ]]; then
    local grype_ok=false
    # Environment overrides .grype.yaml: a repository may keep its ignores and
    # excludes, but must not hide fixable findings from the gate.
    local -a _grype_env=(env GRYPE_ONLY_NOTFIXED=false GRYPE_IGNORE_WONTFIX=)
    [[ "$no_update" == "true" ]] && \
      _grype_env+=(GRYPE_DB_AUTO_UPDATE=false GRYPE_DB_VALIDATE_AGE=false)
    "${_grype_env[@]+"${_grype_env[@]}"}" grype . "${config_args[@]}" \
      -v -o "$output_format" >"$outfile" 2>"$errfile" && grype_ok=true
    cat "$errfile" >&2
    if [[ "$no_update" != "true" ]] && grype_db_degraded "$errfile"; then
      GRYPE_DB_DEGRADED=1
    fi
    if [[ "$grype_ok" == "true" ]] && grype_catalog_usable "$errfile"; then
      cat "$outfile"
      rm -f "$errfile" "$outfile"
      return 0
    fi
    if is_scan_transient "$errfile"; then
      echo "WARNING: Local grype failed with a transient network error — retry may help." >&2
      GRYPE_SCAN_TRANSIENT=1
    fi
    echo "WARNING: Local grype failed. Trying container fallback..." >&2
  fi

  # Fall back to container
  if [[ -n "$CONTAINER_CMD" ]]; then
    local scanner_image
    scanner_image=$(grype_container_image) || { rm -f "$errfile" "$outfile"; return 1; }
    if [[ -n "${CVE_FIX_GRYPE_VERSION:-}" ]] &&
       ! grype_container_version_matches "$CONTAINER_CMD" "$scanner_image" "$CVE_FIX_GRYPE_VERSION"; then
      rm -f "$errfile" "$outfile"
      return 1
    fi
    # The fallback result supersedes diagnostics from the failed local attempt.
    # Recompute both signals from the container update/scan so a healthy fallback
    # cannot inherit a false degraded or transient sentinel.
    GRYPE_DB_DEGRADED=0
    GRYPE_SCAN_TRANSIENT=0
    : > "$errfile"
    if [[ "$fresh" == "true" ]]; then
      $CONTAINER_CMD volume create grype-db >/dev/null 2>&1 || true
      echo "Updating vulnerability database (container)..." >&2
      if ! $CONTAINER_CMD run --rm \
        -e GRYPE_DB_CACHE_DIR=/root/.cache/grype/db \
        -v grype-db:/root/.cache/grype "$scanner_image" db update >&2; then
        echo "WARNING: DB update failed. Scan will use cached data." >&2
        GRYPE_DB_DEGRADED=1
      fi
    fi
    local -a env_args=(-e GRYPE_DB_CACHE_DIR=/root/.cache/grype/db -e GRYPE_ONLY_NOTFIXED=false -e GRYPE_IGNORE_WONTFIX=)
    if [[ "$no_update" == "true" ]]; then
      env_args+=(-e GRYPE_DB_AUTO_UPDATE=false -e GRYPE_DB_VALIDATE_AGE=false)
    fi
    local -a container_config=()
    [[ -f .grype.yaml ]] && container_config=(--config /src/.grype.yaml)
    : > "$outfile"
    if $CONTAINER_CMD run --rm "${env_args[@]}" \
      -v grype-db:/root/.cache/grype \
      -v "$(pwd)":/src \
      "$scanner_image" /src "${container_config[@]}" -v -o "$output_format" >"$outfile" 2>"$errfile" &&
        grype_catalog_usable "$errfile"; then
      cat "$errfile" >&2
      if [[ "$no_update" != "true" ]] && grype_db_degraded "$errfile"; then
        GRYPE_DB_DEGRADED=1
      fi
      cat "$outfile"
      rm -f "$errfile" "$outfile"
      return 0
    fi
    cat "$errfile" >&2
    if is_scan_transient "$errfile"; then
      echo "WARNING: Container scan failed with a transient network error — retry may help." >&2
      GRYPE_SCAN_TRANSIENT=1
    fi
    echo "WARNING: Container scan failed." >&2
  fi

  rm -f "$errfile" "$outfile"
  echo "ERROR: No scanner available." >&2
  echo "  Install grype locally or docker/podman." >&2
  return 1
}

# Remove duplicate no-fix findings from generated Go binaries when the same
# CVE/package is already covered by a source-module ignore. Generated binaries
# are scanned for freshness, but their paths are not stable repository module
# locations and must not cause a committed /bin/... ignore.
filter_generated_binary_duplicates() {
  local repo="${1:-}" manifest="${2:-}" script_dir
  if [[ -z "$repo" || -z "$manifest" ]]; then cat; return; fi
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  python3 "$script_dir/binary-module-locations.py" "$repo" "$manifest" --filter-duplicates
}

# Check if version A >= version B using SemVer precedence.
# Strips the +incompatible suffix before comparing — it is a Go module
# metadata marker, not a version component, so v2.3.4+incompatible and
# v2.3.4 are semantically identical for ordering purposes.
#
version_gte() {
  local a="${1#v}" b="${2#v}"
  a="${a%%+*}" b="${b%%+*}"

  # Parse the numeric core, accepting the two-component versions used by a few
  # callers. Fall back to the historical comparison only for non-SemVer input.
  local re='^([0-9]+)([.]([0-9]+))?([.]([0-9]+))?(-(.+))?$'
  local a_major a_minor a_patch a_pre b_major b_minor b_patch b_pre
  if [[ "$a" =~ $re ]]; then
    a_major="${BASH_REMATCH[1]}" a_minor="${BASH_REMATCH[3]:-0}"
    a_patch="${BASH_REMATCH[5]:-0}" a_pre="${BASH_REMATCH[7]:-}"
  else
    [[ "$(printf '%s\n' "$a" "$b" | sort -V | head -1)" == "$b" ]]
    return
  fi
  if [[ "$b" =~ $re ]]; then
    b_major="${BASH_REMATCH[1]}" b_minor="${BASH_REMATCH[3]:-0}"
    b_patch="${BASH_REMATCH[5]:-0}" b_pre="${BASH_REMATCH[7]:-}"
  else
    [[ "$(printf '%s\n' "$a" "$b" | sort -V | head -1)" == "$b" ]]
    return
  fi

  local av bv
  local -a a_core=("$a_major" "$a_minor" "$a_patch")
  local -a b_core=("$b_major" "$b_minor" "$b_patch")
  local i
  for i in 0 1 2; do
    av=$((10#${a_core[$i]})) bv=$((10#${b_core[$i]}))
    (( av > bv )) && return 0
    (( av < bv )) && return 1
  done

  # A release has higher precedence than every prerelease of the same core.
  [[ -z "$a_pre" && -n "$b_pre" ]] && return 0
  [[ -n "$a_pre" && -z "$b_pre" ]] && return 1
  [[ -z "$a_pre" ]] && return 0

  # Compare prerelease dot identifiers per SemVer: numeric numerically, numeric
  # below nonnumeric, nonnumeric lexically, then shorter sequence below longer.
  local -a a_ids b_ids
  IFS=. read -r -a a_ids <<< "$a_pre"
  IFS=. read -r -a b_ids <<< "$b_pre"
  local ai bi a_num b_num max=${#a_ids[@]}
  (( ${#b_ids[@]} > max )) && max=${#b_ids[@]}
  for ((i=0; i<max; i++)); do
    (( i >= ${#a_ids[@]} )) && return 1
    (( i >= ${#b_ids[@]} )) && return 0
    ai="${a_ids[$i]}" bi="${b_ids[$i]}"
    [[ "$ai" == "$bi" ]] && continue
    a_num=false b_num=false
    [[ "$ai" =~ ^[0-9]+$ ]] && a_num=true
    [[ "$bi" =~ ^[0-9]+$ ]] && b_num=true
    if [[ "$a_num" == true && "$b_num" == true ]]; then
      (( 10#$ai > 10#$bi )) && return 0 || return 1
    fi
    [[ "$a_num" == true ]] && return 1
    [[ "$b_num" == true ]] && return 0
    [[ "$ai" > "$bi" ]] && return 0 || return 1
  done
  return 0
}

# Portable in-place sed edit. BSD and GNU sed disagree on the -i flag (BSD needs
# an explicit backup suffix), so route every edit through a temp file + mv.
# Usage: sed_inplace SCRIPT FILE
sed_inplace() {
  local script="$1" file="$2" tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX") || return 1
  sed "$script" "$file" > "$tmp" && mv "$tmp" "$file"
}

# Collapse runs of blank lines down to a single blank line. Replaces the classic
# sed '/^$/{N;…}' form, whose N/branch syntax is not BSD-portable. Used to tidy
# go.mod / .grype.yaml after edits. Usage: squeeze_blank_lines FILE
squeeze_blank_lines() {
  local file="$1" tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX") || return 1
  awk 'NF>0{b=0} NF==0{b++} b<2' "$file" > "$tmp" && mv "$tmp" "$file"
}

# Print the installed version of PACKAGE resolved in module dir MODDIR, as a
# bare semver (including prerelease/pseudo-version, without 'v' or metadata), or empty if
# the package is not a dependency of that module, or "0.0.0" if the package is
# replaced by a local path (which has no semver).
#
# Why bare: version_gte compares against a bare second arg (callers pass bare
# VERSION); sort -V orders any bare version before a v-prefixed one, so feeding
# it a 'v'-prefixed installed version makes version_gte unconditionally true and
# every package looks already-fixed. Normalize here to keep that contract.
#
# Why "0.0.0" for local-path replaces (Invariant 1): a local-path replace
# (replace PKG => ./... or => /...) has no semver RHS. Returning "" would be
# treated by callers as "not a dependency here" (substring-only match), causing
# them to skip the STILL_VULNERABLE check — a false-FIXED. "0.0.0" is non-empty
# (callers don't skip it) and always fails version_gte against any real CVE fix
# version (every fix version > 0.0.0), so STILL_VULNERABLE is set and
# fix-package.sh correctly exits 3 (CVE persists after update).
#
# Primary source is 'go list -m' (authoritative; honors replace/require). The
# fallback is an anchored go.mod scan matching PACKAGE as a whole token, so a
# sibling module whose path contains PACKAGE as a substring cannot leak its
# version (the false-FIXED bug). Guarded so 'set -e'/ERR traps don't trip.
get_installed_version() {
  local moddir="$1" pkg="$2" raw="" norm=""
  raw=$(go -C "$moddir" list -m -f '{{if .Replace}}{{.Replace.Version}}{{else}}{{.Version}}{{end}}' "$pkg" 2>/dev/null) || raw=""
  # A local-path replacement has no Replace.Version; retain the required module
  # version so callers can still detect the unverifiable local replacement.
  if [[ -z "$raw" ]]; then
    raw=$(go -C "$moddir" list -m -f '{{.Version}}' "$pkg" 2>/dev/null) || raw=""
  fi
  if [[ -z "$raw" ]]; then
    local gomod="$moddir/go.mod"
    if [[ -f "$gomod" ]]; then
      raw=$(awk -v pkg="$pkg" '
        /=>/ {
          sub(/\/\/.*/, "")        # strip inline comments before parsing
          # Collect replace directives for our package. Two forms:
          #   versioned:     replace pkg vLHS => path vRHS   (only applies when require == vLHS)
          #   non-versioned: replace pkg      => path [vRHS] (overrides all versions)
          for (i = 1; i <= NF; i++) {
            if ($i != pkg) continue
            arrow = 0
            for (j = i; j <= NF; j++) { if ($j == "=>") { arrow = j; break } }
            if (!arrow) break
            nxt = (i + 1 <= NF) ? $(i + 1) : ""
            if (nxt ~ /^v[0-9]/) {
              # Versioned replace: record lhs_ver -> rhs_ver mapping
              lhs = nxt; rhs = ""
              for (j = arrow + 1; j <= NF; j++)
                if ($j ~ /^v[0-9]/) { rhs = $j; break }
              vrep[lhs] = rhs
            } else {
              # Non-versioned replace: applies to any require version
              rhs = ""
              for (j = arrow + 1; j <= NF; j++)
                if ($j ~ /^v[0-9]/) { rhs = $j; break }
              uvrep = rhs; has_uvrep = 1
            }
            break
          }
          next
        }
        { sub(/\/\/.*/, "") }               # strip line comments (// indirect)
        { for (i=1; i<NF; i++)
            if ($i == pkg && $(i+1) ~ /^v[0-9]/) { req = $(i+1) } }
        END {
          # Honour replace directives: a non-versioned replace overrides all
          # require versions; a versioned replace overrides only the matching
          # version; no replace → use the raw require version.
          # A local-path replace has no RHS semver (resolved == ""); return
          # "0.0.0" so callers see a present-but-unversioned dependency rather
          # than treating it as "not a dependency here" (Invariant 1 fix).
          if (has_uvrep)                         { print (uvrep  != "" ? uvrep  : "0.0.0") }
          else if (req != "" && (req in vrep))   { print (vrep[req] != "" ? vrep[req] : "0.0.0") }
          else                                   { print req }
        }
      ' "$gomod") || raw=""
    fi
  fi
  # Preserve the complete prerelease: Go also emits pseudo-versions based on
  # prerelease tags (vX.Y.Z-pre.0.TIMESTAMP-HASH). Extracting only a numeric
  # prefix makes those and ordinary RCs look like the final fixed release.
  norm="${raw#v}"
  norm="${norm%%+*}"
  [[ "$norm" =~ ^[0-9]+[.][0-9]+[.][0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]] || norm=""
  printf '%s\n' "$norm"
}

# Test whether a go.mod contains an exact require or replace entry for PACKAGE.
# Plain grep is insufficient here: a comment or sibling module such as
# example.com/foo-client must not suppress graph-based handling of
# example.com/foo.
# An optional version suffix restricts the match to versioned references.
gomod_has_module_reference() {
  local gomod="$1" pkg="$2" version_suffix="${3:-}"
  awk -v pkg="$pkg" -v suffix="$version_suffix" '
    function matches(start, i) {
      if ($start != pkg) return 0
      if (suffix == "") return 1
      for (i=start+1; i<=NF && substr($i,1,2) != "//"; i++)
        if ($i ~ /^v[0-9]+[.]/ && substr($i,length($i)-length(suffix)+1) == suffix) return 1
      return 0
    }
    { sub(/\/\/.*/, "") }
    $1 == "require" || $1 == "replace" {
      if (matches(2)) found=1
      section=($2 == "(" ? $1 : "")
      next
    }
    $1 == ")" { section=""; next }
    section != "" && matches(1) { found=1 }
    END { exit !found }
  ' "$gomod" 2>/dev/null
}

# Resolve PACKAGE from the effective module graph in MODDIR.
# Return codes: 0=present, 1=absent, 2=graph lookup failed, 3=local replace.
# Unlike get_installed_version, this helper never conflates a failed graph
# lookup with an absent dependency. Callers fixing CVEs must fail closed.
# shellcheck disable=SC2034 # RESOLVE_ERROR is part of the caller-visible resolver contract
resolve_module_dependency() {
  local moddir="$1" pkg="$2" graph entry err_file
  RESOLVED_VERSION=""
  RESOLVED_REPLACE_DIR=""
  # Returned through the global resolver contract.
  # shellcheck disable=SC2034
  RESOLVE_ERROR=""

  if ! command -v jq >/dev/null 2>&1; then
    RESOLVE_ERROR="jq is required to parse the Go module graph"
    return 2
  fi

  err_file=$(mktemp "${TMPDIR:-/tmp}/cve-fix-graph.XXXXXX") || return 2
  # Graph inspection must not add checksum entries. Mutation commands in
  # fix-package use -mod=mod separately after this read-only decision point.
  if ! graph=$(GOWORK=off GOFLAGS="${GOFLAGS:+$GOFLAGS }-mod=readonly" \
      timeout "${GO_LIST_TIMEOUT:-120}" go -C "$moddir" list -m -json all 2>"$err_file"); then
    RESOLVE_ERROR=$(cat "$err_file" 2>/dev/null || true)
    rm -f "$err_file"
    return 2
  fi
  rm -f "$err_file"

  if ! entry=$(jq -c --arg pkg "$pkg" 'select(.Path == $pkg)' <<< "$graph" 2>/dev/null); then
    RESOLVE_ERROR="jq could not parse the Go module graph for $pkg"
    return 2
  fi
  [[ -n "$entry" ]] || return 1

  # Downloaded versioned replacements also have a cache Dir. Only a
  # replacement without Version is local and cannot prove a published fix.
  if ! RESOLVED_REPLACE_DIR=$(jq -r '
      if .Replace != null and (.Replace.Version // "") == "" then
        .Replace.Dir // .Replace.Path // empty
      else empty end' <<< "$entry" 2>/dev/null); then
    RESOLVE_ERROR="jq could not parse the resolved module entry for $pkg"
    return 2
  fi
  if [[ -n "$RESOLVED_REPLACE_DIR" ]]; then
    return 3
  fi
  if ! RESOLVED_VERSION=$(jq -r 'if .Replace.Version then .Replace.Version else .Version end' <<< "$entry" 2>/dev/null); then
    RESOLVE_ERROR="jq could not read the resolved version for $pkg"
    return 2
  fi
  [[ -n "$RESOLVED_VERSION" ]] || {
    RESOLVE_ERROR="module graph returned no usable version for $pkg"
    return 2
  }
  RESOLVED_VERSION="${RESOLVED_VERSION#v}"
  return 0
}

# Whether `make TARGET` names a real, runnable goal in the current directory.
# Reliable only when the Makefile has no catch-all rule (see has_catchall_rule);
# use has_build_target for the build check, which accounts for that.
has_make_target() {
  local rc=0
  make -q "$1" 2>/dev/null || rc=$?
  [[ $rc -ne 2 ]]
}

# Whether the Makefile in the current directory has a catch-all rule that makes
# `make -q` report every goal as existing. Dapper/wrapper Makefiles do this (e.g.
# Shipyard's '$(filter-out ...,$(MAKECMDGOALS)): ...' delegates any goal into a
# container). Detected by probing a goal that cannot exist: if even that "exists"
# (make -q returns something other than 2 = no-rule), a catch-all is in play.
has_catchall_rule() {
  [[ -f Makefile || -f GNUmakefile || -f makefile ]] || return 1
  local rc=0
  make -q cve-fix-nonexistent-probe >/dev/null 2>&1 || rc=$?
  [[ $rc -ne 2 ]]
}

has_explicit_make_target() {
  local target="${1:?has_explicit_make_target TARGET}" makefile
  for makefile in Makefile Makefile.inc GNUmakefile makefile; do
    [[ -f "$makefile" ]] || continue
    grep -qE "^${target}([[:space:]]+[^:]*)?:" "$makefile" && return 0
  done
  return 1
}

# Catch-all-aware target test for build, clean, unit, and test detection.
has_real_make_target() {
  local target="${1:?has_real_make_target TARGET}"
  if has_catchall_rule; then
    has_explicit_make_target "$target"
  else
    has_make_target "$target"
  fi
}

# Whether the repo genuinely builds binaries (a real `build` target). Drives
# NEEDS_BUILD_FOR_SCAN: a compile is only needed for stdlib CVE detection when
# there are binaries to scan. Under a catch-all Makefile `make -q build` always
# says yes, so a library repo (no build target) would be compiled with a target
# that doesn't exist, failing the whole run. Require an explicit build target in
# that case — a generic wrapper never invents a real build recipe.
has_build_target() {
  has_real_make_target build
}

# Abbreviate Go package path for commit messages
# github.com/docker/docker -> docker/docker
# golang.org/x/net -> x/net
# helm.sh/helm/v3 -> helm/v3
# go.opentelemetry.io/otel -> otel
# go.opentelemetry.io/otel/exporters/otlp/*/X -> otel/X
# google.golang.org/grpc -> grpc
# sigs.k8s.io/controller-runtime -> controller-runtime
# k8s.io/* stays as-is
abbreviate_package() {
  local pkg="$1"
  case "$pkg" in
    github.com/*) echo "${pkg#github.com/}" ;;
    golang.org/x/*) echo "x/${pkg#golang.org/x/}" ;;
    helm.sh/*) echo "${pkg#helm.sh/}" ;;
    go.etcd.io/etcd/*) echo "etcd/${pkg#go.etcd.io/etcd/}" ;;
    go.opentelemetry.io/otel/exporters/otlp/*)
      echo "otel/$(basename "$pkg")" ;;
    go.opentelemetry.io/*) echo "${pkg#go.opentelemetry.io/}" ;;
    google.golang.org/*) echo "${pkg#google.golang.org/}" ;;
    sigs.k8s.io/*) echo "${pkg#sigs.k8s.io/}" ;;
    *) echo "$pkg" ;;
  esac
}

# Count CVE IDs cleared across all FIXED lines of a fix summary: the
# space-separated IDs after " for ", excluding the module scope suffix.
# Used for the run headline so
# it reflects CVEs resolved, not just the number of packages or commits.
count_cves_fixed() {
  printf '%s' "${1:-}" | awk -F' for ' '
    /^FIXED:/ && NF>1 {sub(/ at \/.*go[.]mod$/, "", $2); n+=split($2,a," ")}
    END{print n+0}'
}

# Render fix-summary detail lines, collapsing CVE lists longer than 3 to
# "<first> ... (N CVEs)" so long lines stay scannable. Full IDs live in commits.
format_fix_detail() {
  printf '%s' "${1:-}" | awk -F' for ' '
    /^(FIXED|IGNORED):/ && NF>1 {
      cves=$2; scope=""
      if (match(cves, / at \/.*go[.]mod$/)) {
        scope=substr(cves, RSTART); cves=substr(cves, 1, RSTART-1)
      }
      n = split(cves, a, " ")
      if (n > 3) { print $1 " for " a[1] " ... (" n " CVEs)" scope; next }
    }
    { print }
  '
}


# Go module pseudo-versions can follow an untagged, release or prerelease base.
# Keep their complete timestamp/revision suffix; ordinary prereleases are excluded.
is_go_pseudo_version() {
  [[ "${1#v}" =~ ^[0-9]+[.][0-9]+[.][0-9]+-(0[.]|[0-9A-Za-z.-]+[.]0[.])?[0-9]{14}-[0-9a-f]+([+]incompatible)?$ ]]
}

module_fix_version_usable() {
  [[ -n "$1" ]] || return 1
  is_go_pseudo_version "$1" || { [[ "$1" != *-* ]] && ! [[ "$1" =~ [0-9](rc|beta|alpha)[0-9] ]]; }
}

# Select the best fix version within the same minor stream as the currently-installed
# package version. Used when CVE_FIX_ALL_VERSIONS is set (by fix-all.sh) to prefer
# an in-stream patch (e.g. etcd v3.6.14) over a cross-minor upgrade (v3.7.1) that
# would trigger a Go/K8s dependency bump and flag the fix as NEEDS_REVIEW.
#
# Usage: select_instream_version PACKAGE CURRENT_VERSION
# Prints the chosen version (bare, without leading 'v') on stdout; prints
# CURRENT_VERSION unchanged when no in-stream candidate is found.
select_instream_version() {
  local pkg="$1" current="$2" inst_minor best="" v
  inst_minor=$(echo "$current" | cut -d. -f1-2)
  local -a fv
  IFS=',' read -ra fv <<< "${CVE_FIX_ALL_VERSIONS:-}"
  for v in "${fv[@]}"; do
    v="${v#v}"
    [[ -z "$v" ]] && continue                                  # skip empty (null in join)
    # Accept all Go pseudo-version forms while excluding ordinary prereleases.
    module_fix_version_usable "$v" || continue
    [[ "$(echo "$v" | cut -d. -f1-2)" == "$inst_minor" ]] || continue
    version_gte "$v" "$current" || continue
    { [[ -z "$best" ]] || version_gte "$v" "$best"; } && best="$v"
  done
  # If the only in-stream fix version is a pseudo-version but current is a real
  # release, SemVer precedence alone cannot establish whether the commit belongs
  # after that release on the module's history. Return current so
  # the condition `_BEST != _INST` in fix-package.sh evaluates to FALSE and
  # VERSION is left at the grype-reported fix version, which triggers the proper
  # update or a STILL_VULNERABLE surfacing.
  if [[ -n "$best" ]] && is_go_pseudo_version "$best" && ! is_go_pseudo_version "$current"; then
    echo "$current"
    return
  fi
  echo "${best:-$current}"
}

# Select the lowest package version that reaches a reported fix threshold for
# every CVE in a grouped remediation. First choose the greatest per-CVE minimum,
# preferring thresholds at or above installed and requiring the combined target
# to reach installed. An earlier dependency fix can already have satisfied some
# of the advisory thresholds. Then, for the resulting target minor stream,
# prefer each advisory's threshold in that stream when one exists. This handles
# alternate patched release streams without selecting a version that is still
# vulnerable in the chosen stream. The final Grype scan remains authoritative
# for unusual non-monotonic affected ranges. REQUIREMENTS_B64 is base64 JSON shaped as:
# [{"cve":"ID","versions":["1.82.4","1.83.2"]}, ...]
select_common_fix_version() {
  local current="${1#v}" encoded="${2:-}" requirements cve v candidate="" target_stream
  [[ -n "$encoded" ]] || return 1
  requirements=$(printf '%s' "$encoded" | jq -Rr '@base64d | fromjson' 2>/dev/null) || return 1

  local -a cves versions
  mapfile -t cves < <(jq -r '.[].cve' <<< "$requirements" | sort -u)
  [[ ${#cves[@]} -gt 0 ]] || return 1

  for cve in "${cves[@]}"; do
    mapfile -t versions < <(jq -r --arg cve "$cve" '.[] | select(.cve == $cve) | .versions[]?' \
      <<< "$requirements" | sed 's/^v//')
    v=$(select_advisory_fix_threshold "$current" "" "${versions[@]+"${versions[@]}"}") || return 1
    if [[ -z "$candidate" ]] || version_gte "$v" "$candidate"; then
      candidate="$v"
    fi
  done
  [[ -n "$candidate" ]] || return 1
  version_gte "$candidate" "$current" || return 1

  # Advisories can publish fixes for parallel release streams. Prefer the
  # selected stream, preserving its first threshold at or above installed.
  # Selecting an earlier patch here can incorrectly reject a valid newer fix.
  target_stream=$(printf '%s' "$candidate" | cut -d. -f1-2)
  candidate=""
  for cve in "${cves[@]}"; do
    mapfile -t versions < <(jq -r --arg cve "$cve" '.[] | select(.cve == $cve) | .versions[]?' \
      <<< "$requirements" | sed 's/^v//')
    v=$(select_advisory_fix_threshold "$current" "$target_stream" "${versions[@]+"${versions[@]}"}") ||
      v=$(select_advisory_fix_threshold "$current" "" "${versions[@]+"${versions[@]}"}") || return 1
    if [[ -z "$candidate" ]] || version_gte "$v" "$candidate"; then
      candidate="$v"
    fi
  done
  [[ -n "$candidate" ]] || return 1
  version_gte "$candidate" "$current" || return 1
  printf '%s\n' "$candidate"
}

# Replace grouped requirements with thresholds reported above a rejected
# version ("CVE v1,v2" lines on stdin): thresholds at or below it are disproven.
# Prints the new base64 requirements; fails when nothing changes, so evidence
# can drive at most one retry.
merge_fix_requirements() {
  local encoded="$1" additions
  additions=$(awk 'NF == 2 { print $1 "\t" $2 }' | jq -Rsc '
    split("\n") | map(select(length > 0) | split("\t") |
      {key: .[0], value: (.[1] | split(",") | map(ltrimstr("v")) | unique)}) | from_entries') || return 1
  printf '%s' "$encoded" | jq -Rr --argjson add "$additions" '
    (@base64d | fromjson) as $old |
    ($old | map(if $add[.cve] then .versions = $add[.cve] else . end)) as $new |
    if $new == $old then error("no new thresholds") else $new | tojson | @base64 end' 2>/dev/null || return 1
}

# Prefer the earliest usable threshold at or above installed, optionally within
# one release stream. If all thresholds are older, retain the earliest so a
# different grouped advisory can still supply a non-downgrading combined target.
select_advisory_fix_threshold() {
  local current="$1" stream="$2" threshold fallback="" preferred=""
  shift 2
  for threshold in "$@"; do
    module_fix_version_usable "$threshold" || continue
    [[ -z "$stream" || "$(printf '%s' "$threshold" | cut -d. -f1-2)" == "$stream" ]] || continue
    if [[ -z "$fallback" ]] || version_gte "$fallback" "$threshold"; then
      fallback="$threshold"
    fi
    if version_gte "$threshold" "$current" &&
       { [[ -z "$preferred" ]] || version_gte "$preferred" "$threshold"; }; then
      preferred="$threshold"
    fi
  done
  threshold="${preferred:-$fallback}"
  [[ -n "$threshold" ]] || return 1
  printf '%s\n' "$threshold"
}

# Go fixes are release-stream thresholds, not monotonically interchangeable
# module versions. Require every advisory to name the selected stream explicitly.
select_common_go_fix_version() {
  local current="${1#go}" encoded="$2" requirements stream filtered candidate
  requirements=$(printf '%s' "$encoded" | jq -Rr '@base64d | fromjson |
    map(.versions |= map(select(type == "string") | ltrimstr("v") |
      select(test("^[0-9]+[.][0-9]+[.][0-9]+$"))))' 2>/dev/null) || return 1
  current=$(printf '%s' "$current" | cut -d. -f1-2)
  while IFS= read -r stream; do
    [[ -n "$stream" ]] || continue
    version_gte "$stream" "$current" || continue
    filtered=$(jq -c --arg stream "$stream" \
      'map(.versions |= map(select(startswith($stream + "."))))' <<< "$requirements")
    jq -e 'length > 0 and all(.[]; (.versions | length) > 0)' <<< "$filtered" >/dev/null || continue
    filtered=$(printf '%s' "$filtered" | base64 | tr -d '\n')
    candidate=$(select_common_fix_version "$stream.0" "$filtered") || continue
    printf '%s\n' "$candidate"
    return 0
  done < <(jq -r '.[].versions[] | split(".")[0:2] | join(".")' <<< "$requirements" | sort -Vu)
  return 1
}

# Find all go.mod files in the repo (excluding vendor and gitignored dirs)
find_gomods() {
  # Only repository-owned modules are in scope. Including untracked go.mod files
  # lets an unrelated scratch module affect version selection and be modified.
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git ls-files --cached -- \
      '*/go.mod' 'go.mod' ':(exclude)vendor/*' ':(exclude)*/vendor/*'
  else
    find . -name go.mod -not -path '*/vendor/*'
  fi
}

# Canonical Grype/module location: `/src/tools/go.mod`, `/tools/go.mod`, and
# `tools/go.mod` all refer to the same module.
normalize_scan_location() {
  local location="${1:-}"
  location="${location#/src/}"
  location="${location#/}"
  if [[ -n "$location" ]]; then
    printf '/%s\n' "$location"
  fi
}

# Return success only for the Grype JSON fields consumed by the CVE
# evidence pipeline. Grype omits ignoredMatches when there are none, but when
# present it must be an array. matches is always required; otherwise an unusable
# document such as {} could be mistaken for a clean scan.
# Usage: grype_scan_json_valid [FILE] (reads stdin when FILE is omitted)
grype_scan_json_valid() {
  local filter='def nonempty: type == "string" and length > 0;
    def validmatch:
      type == "object" and (.artifact | type == "object") and
      (.artifact.type | nonempty) and (.vulnerability | type == "object") and
      (if .artifact.type == "go-module" then
        (.artifact.name | nonempty) and (.vulnerability.id | nonempty) and
        ((.artifact.locations // []) | type == "array" and all(.[]; .path | type == "string"))
       else true end);
    type == "object" and
    (.matches | type == "array") and
    ((has("ignoredMatches") | not) or (.ignoredMatches | type == "array")) and
    all((.matches + (.ignoredMatches // []))[]; validmatch)'
  if (( $# > 0 )); then
    jq -se "length == 1 and (.[0] | $filter)" "$1" >/dev/null 2>&1
  else
    jq -se "length == 1 and (.[0] | $filter)" >/dev/null 2>&1
  fi
}

# Stable advisory/package/module keys for tracked source modules. Include ignored
# findings so an existing rule cannot conceal a newly introduced vulnerability.
# Binary freshness and coverage are checked separately by the final scan gate.
grype_source_findings() {
  local scan_file="$1" modules modfile
  modules=$(while IFS= read -r modfile; do
    normalize_scan_location "$modfile"
  done < <(find_gomods) | jq -Rsc 'split("\n") | map(select(length > 0))') || return 1
  jq -c --argjson modules "$modules" '
    def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
    [((.matches // []) + (.ignoredMatches // []))[] |
      select(.artifact.type == "go-module") | . as $match |
      .artifact.locations[]? | (.path | normloc) as $path |
      select($modules | index($path)) |
      [$match.vulnerability.id, $match.artifact.name, $path]] | unique
  ' "$scan_file"
}

# Choose evidence for this verification iteration. A failed current scan must
# not fall back to an older snapshot and recommend removing a live ignore.
# Direct companion callers may use the initial scan when no rescan was attempted.
review_scan_file() {
  local report_dir="${1:-}" scan_file=""
  [[ -n "$report_dir" ]] || return 0
  if [[ -f "$report_dir/final-scan.json" ]]; then
    scan_file="$report_dir/final-scan.json"
  elif [[ -f "$report_dir/scan-regression.evidence" ]] &&
       grep -qE '^(SCAN_FAILED=1|SKIP:)' "$report_dir/scan-regression.evidence"; then
    echo "ERROR: Current verification scan failed" >&2
    return 1
  elif [[ -f "$report_dir/initial-scan.json" ]]; then
    scan_file="$report_dir/initial-scan.json"
  fi
  [[ -n "$scan_file" ]] || return 0
  grype_scan_json_valid "$scan_file" || {
    echo "ERROR: Invalid Grype evidence: $scan_file" >&2
    return 1
  }
  printf '%s\n' "$scan_file"
}

grype_fix_states() {
  # Read actual scalar fields, not reason comments. YAML only starts an inline
  # comment after whitespace; unknown#literal must remain an invalid state.
  awk '/^[[:space:]]*fix-state:/ {
    sub(/^[[:space:]]*fix-state:[[:space:]]*/, "")
    sub(/[[:space:]]+#.*$/, "")
    if ($0 ~ /^#/) $0=""
    sub(/^[[:space:]]+/, ""); sub(/[[:space:]]+$/, "")
    # Keep quoted enum scalars supported by the other ignore auditors.
    quote=substr($0, 1, 1)
    if ((quote == "\"" || quote == "\047") && substr($0, length($0), 1) == quote)
      $0=substr($0, 2, length($0)-2)
    print
  }'
}

# Return 0 when FILE contains the exact CVE/package/location ignore entry.
# Empty LOCATION means an unscoped entry, not "any scope".
grype_ignore_entry_exists() {
  local file="$1" want_cve="$2" want_pkg="$3" want_loc="${4:-}"
  [[ -f "$file" ]] || return 1
  want_loc=$(normalize_scan_location "$want_loc")
  awk -v want_cve="$want_cve" -v want_pkg="$want_pkg" -v want_loc="$want_loc" '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function normloc(s) { s=trim(s); sub(/^\/src\//, "/", s); if (s != "" && s !~ /^\//) s="/" s; return s }
    function flush() {
      if (vuln==want_cve && pkg==want_pkg && normloc(loc)==want_loc) found=1
      vuln=pkg=loc=""
    }
    /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
    /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore && active) flush(); in_ignore=0; active=0 }
    in_ignore && /^[[:space:]]*-([[:space:]]|$)/ { if (active) flush(); active=1 }
    in_ignore && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    in_ignore && /^[[:space:]]*name:/ { x=$0; sub(/.*name:[[:space:]]*/, "", x); pkg=trim(x) }
    in_ignore && /^[[:space:]]*location:/ { x=$0; sub(/.*location:[[:space:]]*/, "", x); loc=trim(x) }
    END { if (active) flush(); exit !found }
  ' "$file"
}

# Report policy conflicts where a repository-wide ignore shadows one or more
# module-scoped ignores for the same vulnerability/package.  Different scoped
# locations are independent and are therefore not conflicts.
# Output is stable enough for companion evidence and human review.
grype_ignore_scope_conflicts() {
  local file="${1:?grype_ignore_scope_conflicts FILE}"
  [[ -f "$file" ]] || return 0
  awk '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function normloc(s) { s=trim(s); sub(/^\/src\//, "/", s); if (s != "" && s !~ /^\//) s="/" s; return s }
    function flush() {
      if (vuln != "" && pkg != "") {
        key=vuln SUBSEP pkg
        if (loc == "") broad[key]=1
        else scoped[key SUBSEP normloc(loc)]=1
      }
      vuln=pkg=loc=""
    }
    /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
    /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore && active) flush(); in_ignore=0; active=0 }
    in_ignore && /^[[:space:]]*-([[:space:]]|$)/ { if (active) flush(); active=1 }
    in_ignore && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    in_ignore && /^[[:space:]]*name:/ { x=$0; sub(/.*name:[[:space:]]*/, "", x); pkg=trim(x) }
    in_ignore && /^[[:space:]]*location:/ { x=$0; sub(/.*location:[[:space:]]*/, "", x); loc=trim(x) }
    END {
      if (active) flush()
      for (key in broad) {
        split(key, pair, SUBSEP)
        for (entry in scoped) {
          split(entry, fields, SUBSEP)
          if (fields[1] == pair[1] && fields[2] == pair[2])
            print "SCOPE_CONFLICT: " pair[1] " (" pair[2] ") has unscoped and scoped ignore at " fields[3]
        }
      }
    }
  ' "$file" | sort -u
}

# Return 0 when FILE has any scoped entry for CVE_ID/PACKAGE.
grype_ignore_scoped_entry_exists() {
  local file="$1" cve_id="$2" package="$3"
  [[ -f "$file" ]] || return 1
  awk -v want_cve="$cve_id" -v want_pkg="$package" '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function flush() { if (vuln==want_cve && pkg==want_pkg && loc!="") found=1; vuln=pkg=loc="" }
    /^[[:space:]]*-([[:space:]]|$)/ { if (active) flush(); active=1 }
    active && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    active && /^[[:space:]]*name:/ { x=$0; sub(/.*name:[[:space:]]*/, "", x); pkg=trim(x) }
    active && /^[[:space:]]*location:/ { x=$0; sub(/.*location:[[:space:]]*/, "", x); loc=trim(x) }
    END { if (active) flush(); exit !found }
  ' "$file"
}

# Narrow an existing auto-expiring unscoped entry to an exact scanner-reported
# module. The caller must have established that this is the sole matching scan
# location; dependency-graph presence elsewhere is not a scanner finding and
# must not block narrowing. Permanent ignores are human policy and never get
# narrowed automatically.
migrate_grype_ignore_scope() {
  local file="$1" cve_id="$2" package="$3" requested_location="$4" requested_state="${5:-}"
  local state reason actual_location
  requested_location=$(normalize_scan_location "$requested_location")
  [[ -n "$requested_location" ]] || return 1
  grype_ignore_entry_exists "$file" "$cve_id" "$package" "" || return 1
  state=$(awk -v want_cve="$cve_id" -v want_pkg="$package" '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function flush() { if (vuln==want_cve && pkg==want_pkg && loc=="") { print state; found=1 } vuln=pkg=state=loc="" }
    /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
    /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore && active) flush(); in_ignore=0; active=0 }
    in_ignore && /^[[:space:]]*-([[:space:]]|$)/ { if (active) flush(); active=1 }
    in_ignore && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    in_ignore && /fix-state:/ { x=$0; sub(/.*fix-state:[[:space:]]*/, "", x); state=trim(x) }
    in_ignore && /^[[:space:]]*name:/ { x=$0; sub(/.*name:[[:space:]]*/, "", x); pkg=trim(x) }
    in_ignore && /^[[:space:]]*location:/ { x=$0; sub(/.*location:[[:space:]]*/, "", x); loc=trim(x) }
    END { if (active) flush() }
  ' "$file" | head -1)
  [[ "$state" == "not-fixed" || "$state" == "unknown" ]] || return 1
  # Preserve the requested effective Grype state when migrating. An older
  # unscoped rule may use not-fixed even though the current scan reports an
  # empty state, which Grype matches as unknown; retaining the old state would
  # leave the newly scoped rule unapplied.
  [[ -z "$requested_state" ]] || state="$requested_state"

  reason=$(awk -v want_cve="$cve_id" -v want_pkg="$package" '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function flush() { if (vuln==want_cve && pkg==want_pkg && loc=="") { print comment; found=1 } vuln=pkg=loc=comment="" }
    /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
    /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore && active) flush(); in_ignore=0; active=0 }
    # Comments above an item describe it; keep them with the migrated entry.
    in_ignore && /^[[:space:]]*-([[:space:]]|$)/ { if (active) flush(); active=1; comment=pending; pending="" }
    in_ignore && /^[[:space:]]*#/ { x=$0; sub(/^[[:space:]]*#[[:space:]]?/, "", x); pending=(pending == "" ? "" : pending " ") trim(x) }
    in_ignore && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    in_ignore && /^[[:space:]]*name:/ { x=$0; sub(/.*name:[[:space:]]*/, "", x); pkg=trim(x) }
    in_ignore && /^[[:space:]]*location:/ { x=$0; sub(/.*location:[[:space:]]*/, "", x); loc=trim(x) }
    END { if (active) flush() }
  ' "$file" | head -1)
  [[ -n "$reason" ]] || reason="Scoped CVE ignore"
  remove_grype_ignore "$file" "$cve_id" "$package" ""
  insert_grype_ignore "$file" "$cve_id" "$package" "$reason" "$state" "$requested_location"
  echo "Migrated unscoped ignore: $cve_id ($package) -> $requested_location"
}

# Print MODDIR's toolchain directive (for example go1.25.7), or nothing when the
# module has none. Fails (non-zero, go's error on stderr) when go.mod cannot be
# read, so an unreadable file is never mistaken for "no directive". Read through
# `go mod edit -json` so a trailing comment can never leak into the value.
# GOTOOLCHAIN=local keeps every helper below a pure file operation: `go mod edit`
# under GOTOOLCHAIN=auto would first download any newer toolchain that go.mod
# names, which fails offline and is never wanted here.
gomod_toolchain() {
  local moddir="${1:?gomod_toolchain MODDIR}" json
  json=$(GOTOOLCHAIN=local go -C "$moddir" mod edit -json) || return 1
  jq -r '.Toolchain // empty' <<< "$json"
}

# Set a Go toolchain name or "default", or remove the directive with "none".
set_gomod_toolchain() {
  local moddir="${1:?set_gomod_toolchain MODDIR NAME}" name="${2:?set_gomod_toolchain MODDIR NAME}"
  [[ "$name" =~ ^(none|default|go[0-9]+[.][0-9]+([.][0-9]+|(rc|beta)[0-9]+)?(-[[:alnum:]_.-]+)?)$ ]] || {
    echo "ERROR: invalid toolchain directive '$name'" >&2
    return 1
  }
  GOTOOLCHAIN=local go -C "$moddir" mod edit -toolchain="$name"
}

# Restore MODDIR's toolchain directive to a value read earlier with
# gomod_toolchain (empty means none). Go commands add and rewrite this
# directive as incidental output; it is repository policy and must not drift.
# Leaves the file alone when it already matches.
restore_gomod_toolchain() {
  local moddir="${1:?restore_gomod_toolchain MODDIR BEFORE}" before="${2:-}" now
  now=$(gomod_toolchain "$moddir") || return 1
  [[ "$now" == "$before" ]] && return 0
  set_gomod_toolchain "$moddir" "${before:-none}"
}

# Print the Go release MODDIR effectively requires, bare (1.25.7): the greater of
# its go and toolchain directives. A toolchain older than the go line is ignored
# by Go, so it never lowers the requirement.
gomod_effective_go() {
  local moddir="${1:?gomod_effective_go MODDIR}" go_ver toolchain
  go_ver=$(awk '$1 == "go" { print $2; exit }' "$moddir/go.mod" 2>/dev/null || true)
  toolchain=$(gomod_toolchain "$moddir") || return 1
  # Go treats custom suffixes as the corresponding standard release; default
  # disables toolchain switching and does not name a compiler version.
  [[ "$toolchain" != "default" ]] || toolchain=""
  toolchain="${toolchain#go}"
  toolchain="${toolchain%%-*}"
  go_ver="${go_ver:-1.16}"
  # Native Go prerelease names omit the patch and hyphen (go1.26rc1).
  # Normalize them for the SemVer comparator and release-stream selection.
  if [[ "$toolchain" =~ ^([0-9]+[.][0-9]+)(rc|beta)([0-9]+)$ ]]; then
    toolchain="${BASH_REMATCH[1]}.0-${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  fi
  if [[ "$go_ver" =~ ^([0-9]+[.][0-9]+)(rc|beta)([0-9]+)$ ]]; then
    go_ver="${BASH_REMATCH[1]}.0-${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  fi
  if [[ -n "$toolchain" ]] && { [[ -z "$go_ver" ]] || version_gte "$toolchain" "$go_ver"; }; then
    go_ver="$toolchain"
  fi
  printf '%s\n' "$go_ver"
}

# Normalize harmless whitespace added by go mod tidy. Toolchain directives are
# repository policy and must not be deleted globally; mutation callers that need
# to discard a newly-added directive must restore their own pre-change snapshot.
clean_gomod() {
  local gomod
  while IFS= read -r gomod; do
    squeeze_blank_lines "$gomod"
  done < <(find_gomods)
}

# Insert an ignore entry into a .grype.yaml file.
# Inserts before exclude: section if present, otherwise appends.
# When FIX_STATE is provided (e.g. "not-fixed"), the entry auto-expires
# once grype's DB shows a fix is available.
# When LOCATION is provided (grype's exact reported path, e.g. "/tools/go.mod"),
# the ignore is scoped to that module so it can't mask the same CVE elsewhere.
# It is written after name: — remove_grype_ignore relies on that order.
_grype_yaml_valid() {
  python3 -c "import yaml,sys; list(yaml.safe_load_all(open(sys.argv[1])))" "$1" 2>/dev/null
}

# Usage: insert_grype_ignore FILE CVE_ID PACKAGE REASON [FIX_STATE] [LOCATION]
insert_grype_ignore() {
  local file="$1" cve_id="$2" package="$3" reason="$4" fix_state="${5:-}" location="${6:-}" tmp

  # Validate argument order: first arg must look like a file path, second like a CVE ID.
  # Accept paths with a slash (absolute/relative) or dotfiles like .grype.yaml.
  [[ "$file" == */* || "$file" == .* || -f "$file" ]] || \
    { echo "ERROR: insert_grype_ignore: first arg must be a file path (got: $file). Check argument order." >&2; return 1; }
  [[ "$cve_id" =~ ^(CVE|GHSA|GO)-[A-Za-z0-9] ]] || \
    { echo "ERROR: insert_grype_ignore: invalid CVE ID (got: $cve_id). Check argument order." >&2; return 1; }

  reason="${reason//$'\n'/ }"
  [[ -n "$location" ]] && location=$(normalize_scan_location "$location")
  # Never leave a broad rule shadowing a module-scoped rule. A scoped request
  # may safely migrate an auto-expiring broad rule only when the package is
  # proven to live in exactly that one module; permanent or ambiguous policy
  # fails closed for human review.
  if [[ -n "$location" ]] && grype_ignore_entry_exists "$file" "$cve_id" "$package" ""; then
    if ! migrate_grype_ignore_scope "$file" "$cve_id" "$package" "$location" "$fix_state"; then
      echo "ERROR: refusing scoped ignore while an unscoped ignore exists for $cve_id ($package); scope policy requires review" >&2
      return 2
    fi
    return 0
  fi
  if [[ -z "$location" ]] && grype_ignore_scoped_entry_exists "$file" "$cve_id" "$package"; then
    echo "ERROR: refusing unscoped ignore while scoped ignores exist for $cve_id ($package); scope policy requires review" >&2
    return 2
  fi
  # Replace only the same scope. Root, tools, and other module-specific entries
  # for the same CVE/package are independent security decisions.
  local was_valid=true backup=""
  if [[ -f "$file" ]]; then
    _grype_yaml_valid "$file" || was_valid=false
    backup=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX") && cp -- "$file" "$backup" || return 1
  fi
  remove_grype_ignore "$file" "$cve_id" "$package" "$location"
  local entry padding width=2 ignore_line insert_line
  if [[ ! -f "$file" ]]; then
    printf -- '---\nignore:\n' > "$file"
  elif grep -qE '^ignore:[[:space:]]*\[[[:space:]]*\][[:space:]]*(#.*)?$' "$file"; then
    # An empty flow sequence cannot take block items; make it an empty block.
    sed_inplace 's/^ignore:[[:space:]]*\[[[:space:]]*\][[:space:]]*\(#.*\)\{0,1\}$/ignore:/' "$file"
  elif grep -qE '^ignore:[[:space:]]*[^[:space:]#]' "$file"; then
    echo "ERROR: $file has an inline ignore: value; convert it to a block list first" >&2
    return 1
  elif ! grep -q '^ignore:' "$file"; then
    # Add the parent before existing keys, preserving document headers/directives.
    insert_line=$(awk '
      /^[^[:space:]#]/ && !/^---([[:space:]]|$)/ && !/^%/ { print NR; exit }
    ' "$file")
    [[ -n "$insert_line" ]] || insert_line=$(( $(wc -l < "$file") + 1 ))
    tmp=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX")
    { head -n "$((insert_line - 1))" "$file"; printf '\nignore:\n'; tail -n +"$insert_line" "$file"; } > "$tmp"
    mv "$tmp" "$file"
  fi
  # All items in a YAML sequence must share indentation, including column zero.
  ignore_line=$(grep -n '^ignore:' "$file" | head -1 | cut -d: -f1)
  width=$(awk -v start="$ignore_line" '
    NR > start && /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { exit }
    NR > start && /^[[:space:]]*-([[:space:]]|$)/ { match($0,/^[[:space:]]*/); print RLENGTH; found=1; exit }
    END { if (!found) print 2 }
  ' "$file")
  printf -v padding '%*s' "$width" ''
  entry="${padding}# $reason
${padding}- vulnerability: $cve_id"
  [[ -n "$fix_state" ]] && entry+=$'\n'"${padding}  fix-state: $fix_state"
  entry+=$'\n'"${padding}  package:
${padding}    name: $package"
  [[ -n "$location" ]] && entry+=$'\n'"${padding}    location: $location"
  # Insert at the block end even when unrelated top-level keys follow ignore.
  insert_line=$(awk -v start="$ignore_line" '
    NR > start && /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { print NR; exit }
  ' "$file")
  [[ -n "$insert_line" ]] || insert_line=$(( $(wc -l < "$file") + 1 ))
  tmp=$(mktemp "${TMPDIR:-/tmp}/cve-fix.XXXXXX")
  { head -n "$((insert_line - 1))" "$file"; printf '%s\n' "$entry"; tail -n +"$insert_line" "$file"; } > "$tmp"
  mv "$tmp" "$file"
  if ! python3 -c "import yaml" 2>/dev/null; then
    echo "WARNING: python3-yaml unavailable — skipping YAML validation of $file"
  elif $was_valid && ! _grype_yaml_valid "$file"; then
    echo "ERROR: inserting the ignore made $file invalid YAML" >&2
    if [[ -n "$backup" ]]; then mv -- "$backup" "$file"; else rm -f -- "$file"; fi
    return 1
  fi
  [[ -z "$backup" ]] || rm -f -- "$backup"
}

# Remove an ignore entry from a .grype.yaml file by CVE ID and package name.
# Removes the entire block: preceding comment lines, vulnerability line,
# optional fix-state line, and package block (package: + name:).
# No-op if the entry doesn't exist or doesn't match the package.
# LOCATION selects the exact normalized scope; empty selects only an unscoped
# entry. This prevents repairing one module from deleting a valid sibling ignore.
# Usage: remove_grype_ignore FILE CVE_ID PACKAGE [LOCATION]
remove_grype_ignore() {
  local file="$1" cve_id="$2" package="$3" requested_location="${4:-}"
  requested_location=$(normalize_scan_location "$requested_location")
  [[ -f "$file" ]] || return 0

  # Escape '.' — the only ERE metacharacter that appears in Go module paths and
  # CVE/GHSA/GO ids — so it matches literally (and identically on GNU/BSD grep).
  local cve_re
  cve_re=${cve_id//./\\.}

  # Collect the vulnerability line of every entry for this EXACT CVE. Anchor the
  # id as a whole token (trailing whitespace or end-of-line) so CVE-2024-123
  # never matches a longer CVE-2024-1234 and delete an unrelated entry. The same
  # CVE can be ignored under more than one package, so we must locate the block
  # whose name: matches THIS package rather than blindly taking the first.
  #
  # Use a restart loop: after each deletion line numbers shift, so re-scan the
  # file from scratch rather than continuing with a stale index snapshot. The
  # outer while-true loop terminates when no more matching blocks are found
  # (including the initial no-match case) or when all matching entries have been
  # processed by the inner for-loop without finding a package match.
  local -a vuln_lines=()
  local vuln_line end_line start_line _found_and_deleted actual_location item_name
  while true; do
    mapfile -t vuln_lines < <(grep -nE "vulnerability:[[:space:]]*${cve_re}[[:space:]]*\$" "$file" 2>/dev/null | cut -d: -f1)
    [[ ${#vuln_lines[@]} -gt 0 ]] || return 0

    _found_and_deleted=false
    for vuln_line in "${vuln_lines[@]}"; do
      # The item spans every following line indented deeper than its dash, so
      # fields after name: (type:, version:, location:) leave nothing behind.
      end_line=$(awk -v start="$vuln_line" '
        NR == start { match($0, /^[[:space:]]*/); dash = RLENGTH; last = NR; next }
        NR > start && /^[[:space:]]*(#.*)?$/ { next }
        NR > start { match($0, /^[[:space:]]*/); if (RLENGTH <= dash) exit; last = NR }
        END { print last }' "$file")
      item_name=$(sed -n "${vuln_line},${end_line}p" "$file" | \
        sed -n 's/^[[:space:]]*name:[[:space:]]*//p' | head -1 | xargs)
      # Only delete when THIS block's package matches (whole value). Otherwise skip
      # to the next entry sharing the CVE — deleting the wrong block would silently
      # un-ignore a still-valid entry.
      [[ "$item_name" == "$package" ]] || continue
      actual_location=$(sed -n "${vuln_line},${end_line}p" "$file" | \
        sed -n 's/^[[:space:]]*location:[[:space:]]*//p' | head -1 | xargs)
      actual_location=$(normalize_scan_location "$actual_location")
      [[ "$actual_location" == "$requested_location" ]] || continue

      # Block start: walk backwards over this entry's comment lines.
      start_line=$vuln_line
      while [[ $((start_line - 1)) -ge 1 ]]; do
        if sed -n "$((start_line - 1))p" "$file" | grep -q '^[[:space:]]*#'; then
          start_line=$((start_line - 1))
        else
          break
        fi
      done

      sed_inplace "${start_line},${end_line}d" "$file"
      squeeze_blank_lines "$file"
      # yamllint disallows blank lines immediately after a mapping key (empty-lines rule).
      # After removing entries, a blank line may land right after "ignore:" — strip it.
      sed_inplace '/^ignore:[[:space:]]*\(#.*\)\?$/{n;/^[[:space:]]*$/d}' "$file"
      echo "Removed ignore: $cve_id ($package${requested_location:+ at $requested_location}) from $file"
      # Line numbers have shifted; restart the outer loop to re-scan.
      _found_and_deleted=true
      break
    done
    # If the inner loop ran without finding a package-matching block, all
    # remaining blocks are for different packages — we are done.
    [[ "$_found_and_deleted" == true ]] || return 0
  done
}

# Delete ignore-list entries that lack either an exact vulnerability or package
# name. Such broad selectors can suppress unrelated future findings. Returns 0
# and prints one line per removed entry; callers decide whether to commit.
remove_invalid_grype_ignores() {
  local file="${1:?remove_invalid_grype_ignores FILE}" range start end
  [[ -f "$file" ]] || return 0
  while true; do
    range=$(awk '
      # Comments immediately before the next list item belong to that item,
      # not to the entry being finalized. Keep them when removing an invalid
      # preceding entry (for example a rationale for a fix-state: unknown).
      function end_before_item_comments(end, line) {
        while (end > start && lines[end] ~ /^[[:space:]]*#/) end--
        return end
      }
      function finish(end) {
        if (entry && (vuln==0 || pkg==0)) {
          print start ":" end_before_item_comments(end); emitted=1; exit
        }
        entry=0; vuln=pkg=0
      }
      { lines[NR]=$0 }
      /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
      /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore) finish(NR-1); in_ignore=0 }
      in_ignore && /^[[:space:]]*-([[:space:]]|$)/ { finish(NR-1); entry=1; start=NR }
      in_ignore && entry && /vulnerability:[[:space:]]*[^[:space:]]/ { vuln=1 }
      # Block or flow style: "name: x" or "package: {name: x}", outside comments.
      in_ignore && entry {
        t = $0; sub(/(^|[[:space:]])#.*/, "", t)
        if (t ~ /^[[:space:]]*name:[[:space:]]*[^[:space:]]/ ||
            t ~ /package:[[:space:]]*\{[^}]*name:[[:space:]]*[^[:space:],}]/) pkg=1
      }
      END { if (!emitted && in_ignore) finish(NR) }
    ' "$file")
    [[ -n "$range" ]] || break
    start="${range%%:*}" end="${range#*:}"
    while (( start > 1 )) && sed -n "$((start - 1))p" "$file" | grep -q '^[[:space:]]*#'; do
      ((start -= 1))
    done
    sed_inplace "${start},${end}d" "$file"
    squeeze_blank_lines "$file"
    echo "Removed unsafe broad ignore entry from $file"
  done
}

# Print a section header
banner() {
  echo ""
  echo "--- $1 ---"
}

# Remove the throwaway fix branch that detect.sh --setup-branch created. Safe
# only when the branch carries nothing worth keeping — used on clean/no-op and
# early-abort exits so an empty fix branch isn't left behind. Reads
# FIX_BRANCH/ORIGINAL_REF from the loaded state; a no-op when no branch was set up.
remove_fix_branch() {
  [[ -n "${FIX_BRANCH:-}" ]] || return 0
  git checkout "${ORIGINAL_REF:-}" 2>/dev/null || true
  git branch -D "$FIX_BRANCH" 2>/dev/null || true
}

# Fail fast, before any change is committed, when scan.sh recorded that the
# initial scan ran in a broken environment. Two sentinels (written out-of-band by
# scan.sh, since its stdout is grype's output) make the scan untrustworthy:
#   .network-broken   — the build failed with a network/DNS error (offline). go
#                       get, the rebuild, and the rescan gate all need the network.
#   .scanner-degraded — grype couldn't update/load its vulnerability DB, so it fell
#                       back to a stale/absent DB and its "clean" result can't be
#                       trusted (it may silently miss CVEs).
# Either case would otherwise yield an unverifiable fix and misleading "clean"
# output, so print a clear banner, drop the empty fix branch, and exit 2. Checks
# .network-broken first: when both fire it's the more actionable root cause. A
# no-op (returns 0) when neither sentinel is present. Reads FIX_BRANCH/etc from the
# loaded state via remove_fix_branch. Usage: abort_if_environment_broken STATE_FILE
abort_if_environment_broken() {
  local state_file="${1:?abort_if_environment_broken STATE_FILE}"

  if [[ -f "${state_file}.network-broken" ]]; then
    rm -f "${state_file}.network-broken"
    banner "Aborted: environment offline"
    echo "The build failed with a network/DNS error (often Docker networking)."
    echo "CVEs can't be built, fixed, or verified while the network is down, so"
    echo "no changes were committed. Restore connectivity — e.g.:"
    echo "  sudo systemctl restart docker"
    echo "then re-run."
    remove_fix_branch
    exit 2
  fi

  if [[ -f "${state_file}.scanner-degraded" ]]; then
    rm -f "${state_file}.scanner-degraded"
    banner "Aborted: vulnerability database unavailable"
    echo "grype could not update its vulnerability database (network/DNS)."
    echo "A scan against a stale or missing DB can silently miss CVEs, so its"
    echo "results can't be trusted and no changes were committed. Restore"
    echo "connectivity and re-run."
    remove_fix_branch
    exit 2
  fi

  if [[ -f "${state_file}.scan-transient" ]]; then
    rm -f "${state_file}.scan-transient"
    banner "Aborted: scanner network error"
    echo "grype failed with a transient network/DNS error and no results were produced."
    echo "No changes were committed. Restore connectivity — e.g.:"
    echo "  sudo systemctl restart docker"
    echo "then re-run."
    remove_fix_branch
    exit 2
  fi
}


# Render a template on stdin, replacing ${VAR} for each named variable with its
# current value. Pure-bash replacement of envsubst's named-variable mode:
#   - single pass: a value that itself contains ${OTHER} is never re-expanded, so
#     ordering of the name list is irrelevant (matches envsubst);
#   - values are inserted literally, so arbitrary content — '$', '/', '&',
#     backslashes and newlines — is safe (bash 5.2's ${var/pat/&} backreference
#     would corrupt values containing '&', so we do not use it);
#   - only the listed names are replaced; any other ${...} is left untouched.
# shellcheck disable=SC2016 # match literal template placeholders without shell expansion
render_template() {
  local -A _rt_val=()
  local name
  for name in "$@"; do _rt_val["$name"]="${!name-}"; done

  local content out
  content=$(cat)
  out=""
  # Walk the template, emitting text up to each "${", then deciding whether the
  # token that follows is a known variable name terminated by "}".
  while [[ "$content" == *'${'* ]]; do
    out+="${content%%'${'*}"       # text before the first "${"
    content="${content#*'${'}"      # remainder after "${"
    local token="${content%%'}'*}"  # candidate name up to the next "}"
    if [[ "$content" == *'}'* && -n "${_rt_val[$token]+x}" ]]; then
      out+="${_rt_val[$token]}"     # known var: substitute its literal value
      content="${content#*'}'}"     # consume through the closing "}"
    else
      out+='${'                     # not a known ${VAR}: emit "${" literally
    fi
  done
  out+="$content"
  printf '%s' "$out"
}

# Ensure the skill-local grype binary is present and at the latest release.
# Installs to the plugin bin/grype (git-ignored) without sudo.
# Called from preflight_check; also callable directly.
ensure_grype() {
  local bin_dir script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  bin_dir="$script_dir/../bin"
  local grype_bin="$bin_dir/grype"

  command -v curl >/dev/null 2>&1 || {
    echo "ERROR: curl is required to install or update grype." >&2
    return 1
  }
  mkdir -p "$bin_dir"
  local lock_dir="$bin_dir/.grype-install.lock" attempt=0
  until mkdir "$lock_dir" 2>/dev/null; do
    ((attempt += 1))
    if (( attempt > 300 )); then
      echo "ERROR: timed out waiting for grype installation lock: $lock_dir" >&2
      return 1
    fi
    sleep 0.1
  done

  local install_rc=0
  (
    local latest_ver current_ver tmp_dir os arch artifact checksums_url artifact_url
    local expected_sha actual_sha
    tmp_dir=""
    trap 'rmdir "$lock_dir" 2>/dev/null || true; [[ -z "$tmp_dir" ]] || rm -rf -- "$tmp_dir"' EXIT
    tmp_dir=$(mktemp -d "$bin_dir/.grype-install.XXXXXX")
    latest_ver="${CVE_FIX_GRYPE_VERSION:-}"
    if [[ -z "$latest_ver" ]]; then
      latest_ver=$(curl -sSfL "https://api.github.com/repos/anchore/grype/releases/latest" \
        | grep -oE '"tag_name"[[:space:]]*:[[:space:]]*"v[^"]+"' \
        | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' || true)
    fi
    [[ -n "$latest_ver" ]] && [[ "$latest_ver" == v* ]] || latest_ver="v$latest_ver"
    if [[ "$latest_ver" == "v" ]]; then
      echo "WARNING: could not fetch latest grype version; skipping update check." >&2
      [[ -x "$grype_bin" ]] && exit 0
      echo "ERROR: grype not installed and version check failed." >&2
      exit 1
    fi
    [[ "$latest_ver" =~ ^v[0-9]+[.][0-9]+[.][0-9]+$ ]] || {
      echo "ERROR: invalid grype release version: $latest_ver" >&2
      exit 1
    }

    current_ver=""
    [[ -x "$grype_bin" ]] && current_ver=$("$grype_bin" version 2>/dev/null | \
      grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/^v//' || true)
    [[ "$current_ver" == "${latest_ver#v}" ]] && exit 0

    command -v tar >/dev/null 2>&1 || {
      echo "ERROR: tar is required to install or update grype." >&2
      exit 1
    }

    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)
    case "$arch" in
      x86_64|amd64) arch=amd64 ;;
      aarch64|arm64) arch=arm64 ;;
      ppc64le|s390x) ;;
      *) echo "ERROR: unsupported grype architecture: $arch" >&2; exit 1 ;;
    esac
    case "$os" in
      linux|darwin) ;;
      *) echo "ERROR: unsupported grype operating system: $os" >&2; exit 1 ;;
    esac

    artifact="grype_${latest_ver#v}_${os}_${arch}.tar.gz"
    checksums_url="https://github.com/anchore/grype/releases/download/${latest_ver}/grype_${latest_ver#v}_checksums.txt"
    artifact_url="https://github.com/anchore/grype/releases/download/${latest_ver}/${artifact}"
    echo "Installing checksum-verified grype $latest_ver to $bin_dir..." >&2
    curl -sSfL -o "$tmp_dir/checksums.txt" "$checksums_url" || {
      echo "ERROR: failed to download grype $latest_ver checksums" >&2
      exit 1
    }
    curl -sSfL -o "$tmp_dir/$artifact" "$artifact_url" || {
      echo "ERROR: failed to download grype $latest_ver artifact" >&2
      exit 1
    }
    expected_sha=$(awk -v artifact="$artifact" '$2 == artifact { print $1; exit }' \
      "$tmp_dir/checksums.txt")
    [[ "$expected_sha" =~ ^[[:xdigit:]]{64}$ ]] || {
      echo "ERROR: no valid checksum published for $artifact" >&2
      exit 1
    }
    if command -v sha256sum >/dev/null 2>&1; then
      actual_sha=$(sha256sum "$tmp_dir/$artifact" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
      actual_sha=$(shasum -a 256 "$tmp_dir/$artifact" | awk '{print $1}')
    else
      echo "ERROR: sha256sum or shasum is required to verify grype." >&2
      exit 1
    fi
    [[ "${actual_sha,,}" == "${expected_sha,,}" ]] || {
      echo "ERROR: checksum verification failed for $artifact" >&2
      exit 1
    }
    tar -xzf "$tmp_dir/$artifact" -C "$tmp_dir" grype || {
      echo "ERROR: failed to extract grype $latest_ver" >&2
      exit 1
    }
    [[ -f "$tmp_dir/grype" && ! -L "$tmp_dir/grype" && -x "$tmp_dir/grype" ]] || {
      echo "ERROR: grype artifact produced no regular executable" >&2
      exit 1
    }
    current_ver=$("$tmp_dir/grype" version 2>/dev/null | \
      grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/^v//' || true)
    [[ "$current_ver" == "${latest_ver#v}" ]] || {
      echo "ERROR: installed grype version v$current_ver, expected $latest_ver" >&2
      exit 1
    }
    mv "$tmp_dir/grype" "$grype_bin"
    echo "grype $latest_ver installed to $grype_bin" >&2
  ) || install_rc=$?

  [[ $install_rc -eq 0 ]] || return "$install_rc"
  export PATH="$bin_dir:$PATH"
  command -v grype >/dev/null 2>&1
}

# Package outcomes have an exact delimiter; workflow failures such as
# "tests failed" and "subagent verification failed" are separate hard gates.
# Never ask a package reviewer to resolve those statuses as module names.
package_review_summary() {
  grep -E '^(NEEDS_REVIEW|ERROR|TIMEOUT): [^ ]+ — ' || true
}

# Outcome scope is an explicit suffix, shared by attempts and verification.
# An absent suffix means a repository-wide operation, not an arbitrary module.
package_outcome_location() {
  local line="$1" re=' at (/.*go[.]mod)$'
  if [[ "$line" =~ $re ]]; then
    normalize_scan_location "${BASH_REMATCH[1]}"
  fi
}

package_outcome_exists() {
  local kind="$1" pkg="$2" location="${3:-}" line
  while IFS= read -r line; do
    [[ "$line" == "$kind: $pkg "* ]] || continue
    [[ "$(package_outcome_location "$line")" == "$location" ]] && return 0
  done
  return 1
}

# Filter only the requested package/scope. '*' is reserved for a verified
# repository-wide repair; an empty location matches only unscoped outcomes.
filter_package_outcomes() {
  local kind="$1" pkg="$2" location="${3:-}" line
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    if [[ "$line" == "$kind: $pkg "* ]] &&
       { [[ "$location" == '*' ]] || [[ "$(package_outcome_location "$line")" == "$location" ]]; }; then
      continue
    fi
    printf '%s\n' "$line"
  done
}

# Record a reviewer's UNRESOLVED reason for PKG. It replaces the deterministic
# reason (the reviewer sees Go bumps and MVS constraints the scripts do not)
# in every module scope already under review, keeping one line per scope; an
# unscoped line already covers every module, so it absorbs the scoped ones.
# FIX_LINES/REVIEW_COUNT are the orchestrator's output variables.
apply_review_outcome() {
  local pkg="$1" reason="${2% at /*go.mod}" line scope
  local -a scopes=()
  for line in "${FIX_LINES[@]+"${FIX_LINES[@]}"}"; do
    [[ "$line" == "NEEDS_REVIEW: $pkg "* ]] && scopes+=("$(package_outcome_location "$line")")
  done
  if [[ ${#scopes[@]} -eq 0 ]]; then
    FIX_LINES+=("NEEDS_REVIEW: $pkg — $reason")
    REVIEW_COUNT=$((REVIEW_COUNT + 1))
    return 0
  fi
  mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
    filter_package_outcomes NEEDS_REVIEW "$pkg" '*')
  for scope in "${scopes[@]}"; do
    [[ -n "$scope" ]] || { scopes=(""); break; }
  done
  while IFS= read -r scope; do
    FIX_LINES+=("NEEDS_REVIEW: $pkg — $reason${scope:+ at $scope}")
  done < <(printf '%s\n' "${scopes[@]}" | sort -u)
}

# Fold actual verification outcomes without clearing a sibling module's policy
# boundary. FIX_LINES/FIXED_COUNT are the orchestrator's output variables.
fold_fixed_package_outcomes() {
  local report_dir="$1" entry pkg location clear_scope ids previous line
  [[ -f "$report_dir/fixed-pkgs" ]] || return 0
  while IFS= read -r entry; do
    [[ -n "$entry" ]] || continue
    pkg="${entry%% *}"
    location=$(package_outcome_location "$entry")
    # Preserve verified advisories from earlier repairs while updating the
    # version. Binary/source evidence can repeat the same advisory ID.
    if [[ "$entry" == *' for '* ]]; then
      ids="${entry#* for }"; ids="${ids% at *}"
      for line in "${FIX_LINES[@]+"${FIX_LINES[@]}"}"; do
        [[ "$line" == "FIXED: $pkg "* && "$(package_outcome_location "$line")" == "$location" ]] || continue
        previous="${line#* for }"; ids+=" ${previous% at *}"
      done
      ids=$(awk '{for (i=1; i<=NF; i++) if (!seen[$i]++) print $i}' <<< "$ids" | paste -sd ' ')
      entry="${entry%% for *} for $ids${location:+ at $location}"
    fi
    clear_scope="$location"
    if [[ -n "$location" ]] && ! pkg_sentinel_file_matches "$report_dir/needs-review-pkgs" "$pkg" "$location"; then
      mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
        filter_package_outcomes NEEDS_REVIEW "$pkg" "$clear_scope")
    elif [[ -z "$location" ]] && package_ignore_can_clear_review "$pkg" "$report_dir/needs-review-pkgs"; then
      clear_scope='*'
      mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
        filter_package_outcomes NEEDS_REVIEW "$pkg" "$clear_scope")
    fi
    mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
      filter_package_outcomes ERROR "$pkg" "$clear_scope")
    if printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" | package_outcome_exists FIXED "$pkg" "$location"; then
      # Later verification may repair a newer affected range. Report its
      # actual version without counting the same package/scope again.
      mapfile -t FIX_LINES < <(printf '%s\n' "${FIX_LINES[@]+"${FIX_LINES[@]}"}" |
        filter_package_outcomes FIXED "$pkg" "$location")
    else
      FIXED_COUNT=$((FIXED_COUNT + 1))
    fi
    FIX_LINES+=("FIXED: $entry")
  done < "$report_dir/fixed-pkgs"
}

# Ignoring one advisory does not resolve another advisory's policy boundary.
# Keep that decision visible even when the optional reviewer is unavailable.
package_ignore_can_clear_review() {
  local pkg="$1" policy_file="$2" unresolved
  shift 2
  for unresolved in "$@"; do
    [[ "$unresolved" != "$pkg" ]] || return 1
  done
  if [[ -f "$policy_file" ]] && awk -F '|' -v pkg="$pkg" \
      '$1 == pkg { found=1 } END { exit !found }' "$policy_file"; then
    return 1
  fi
  return 0
}

# Print the reviewer CLI selected by CVE_FIX_AGENT (claude by default).
cve_fix_agent_provider() {
  local provider="${CVE_FIX_AGENT:-claude}"
  case "$provider" in
    claude|codex) printf '%s\n' "$provider" ;;
    *)
      echo "ERROR: unsupported CVE_FIX_AGENT '$provider' (expected: claude or codex)" >&2
      return 1
      ;;
  esac
}

# Build an argv-safe, read-only command for an LLM review. Models inspect the
# fully-prefetched evidence and return structured text on stdout; only the shell
# orchestrator may mutate dependencies, ignores, Git metadata, or report files.
build_cve_fix_agent_command() {
  local prompt="${1:?build_cve_fix_agent_command PROMPT}"
  local provider
  provider=$(cve_fix_agent_provider) || return 1

  local -a model_args=()
  [[ -n "${CVE_FIX_MODEL:-}" ]] && model_args=(--model "$CVE_FIX_MODEL")

  # An empty working directory keeps the target repository's instruction and
  # settings files out of the reviewer; all evidence is in the prompt.
  local cwd
  if [[ -n "${STATE_FILE:-}" ]]; then
    cwd="${STATE_FILE%/*}/reviewer"
    mkdir -p "$cwd" || return 1
  else
    cwd=$(mktemp -d "${TMPDIR:-/tmp}/cve-fix-reviewer.XXXXXX") || return 1
  fi

  CVE_FIX_AGENT_CMD=()
  case "$provider" in
    claude)
      # No tools, MCP servers or project settings: evidence is prefetched, and
      # the target repository's settings and hooks must not configure the reviewer.
      CVE_FIX_AGENT_CMD=(env -C "$cwd" claude -p "$prompt" --print \
        "${model_args[@]+"${model_args[@]}"}" --tools "" --strict-mcp-config \
        --setting-sources user --no-session-persistence)
      ;;
    codex)
      CVE_FIX_AGENT_CMD=(codex exec --ephemeral --sandbox read-only \
        --cd "$cwd" --skip-git-repo-check --color never)
      CVE_FIX_AGENT_CMD+=("${model_args[@]+"${model_args[@]}"}" "$prompt")
      ;;
  esac
}

# Requires bash >= 4.0 plus the core CLIs and a scanner (grype OR docker/podman);
# the selected LLM reviewer is optional (verification degrades to deterministic
# evidence when its CLI is unavailable).
preflight_check() {
  local tool missing=() container_scanner=false scanner_runtime=""
  cve_fix_agent_provider >/dev/null || return 1
  for tool in git go jq awk sed timeout base64 make python3; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "ERROR: missing required tools: ${missing[*]}" >&2
    return 1
  fi
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    container_scanner=true; scanner_runtime=docker
  elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    container_scanner=true; scanner_runtime=podman
  fi

  # Prefer the checksum-verified local binary, but preserve the documented
  # container fallback when curl or the release service is unavailable.
  local skill_bin
  skill_bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../bin"
  [[ -d "$skill_bin" ]] && export PATH="$skill_bin:$PATH"
  if command -v curl >/dev/null 2>&1; then
    if ! ensure_grype; then
      if ! command -v grype >/dev/null 2>&1 && [[ "$container_scanner" != true ]]; then
        return 1
      fi
      if [[ -n "${CVE_FIX_GRYPE_VERSION:-}" ]] &&
         { [[ "$container_scanner" != true ]] ||
           ! grype_container_version_matches "$scanner_runtime" "$(grype_container_image)" "$CVE_FIX_GRYPE_VERSION"; }; then
        echo "ERROR: could not provide requested grype ${CVE_FIX_GRYPE_VERSION}." >&2
        return 1
      fi
      echo "WARNING: could not update grype; using the available scanner." >&2
    fi
  elif [[ -n "${CVE_FIX_GRYPE_VERSION:-}" ]]; then
    local requested_version="${CVE_FIX_GRYPE_VERSION#v}" current_version=""
    if command -v grype >/dev/null 2>&1; then
      current_version=$(grype version 2>/dev/null | \
        grep -oE 'v?[0-9]+[.][0-9]+[.][0-9]+' | head -1 | sed 's/^v//' || true)
    fi
    if [[ "$current_version" != "$requested_version" ]] &&
       { [[ "$container_scanner" != true ]] ||
         ! grype_container_version_matches "$scanner_runtime" "$(grype_container_image)" "$requested_version"; }; then
      echo "ERROR: curl is unavailable and requested grype v$requested_version is not installed." >&2
      return 1
    fi
  elif ! command -v grype >/dev/null 2>&1 && [[ "$container_scanner" != true ]]; then
    echo "ERROR: no scanner found and curl is unavailable for grype installation." >&2
    return 1
  fi
  if ! command -v grype >/dev/null 2>&1 \
     && [[ "$container_scanner" != true ]]; then
    echo "ERROR: no scanner found — install grype, or docker/podman." >&2
    return 1
  fi
  # Semver ordering relies on 'sort -V', which POSIX/BusyBox sort may lack.
  if ! printf '%s\n' 1.0.0 1.0.1 | sort -V >/dev/null 2>&1; then
    echo "ERROR: 'sort -V' unavailable; install GNU coreutils sort." >&2
    return 1
  fi
  # Verify the temp directory is writable and not full. All mktemp/state-file
  # writes land in ${TMPDIR:-/tmp}; a full or unwritable temp dir causes
  # cryptic ENOSPC failures later. Set TMPDIR to redirect to a writable path.
  local _tmpdir="${TMPDIR:-/tmp}"
  local _probe
  if ! _probe=$(mktemp "${_tmpdir}/.cve-fix-space-probe.XXXXXX" 2>&1); then
    echo "ERROR: temp directory full or not writable: $_tmpdir" >&2
    echo "  Is the filesystem full? Try: df -h $_tmpdir" >&2
    echo "  Set TMPDIR to a directory on a filesystem with available space:" >&2
    echo "    export TMPDIR=/path/with/space" >&2
    return 1
  fi
  rm -f "$_probe"
  return 0
}

# --- Subagent verification infrastructure ---

# Grep REGEX against a file path, a literal string, or stdin (when arg absent).
# Used by the four error-classifier functions below to avoid triple-arm duplication.
_grep_pattern() {
  local re="$1" src="${2:-}"
  if [[ -n "$src" && -f "$src" ]]; then
    grep -qiE "$re" "$src" 2>/dev/null
  elif [[ -n "$src" ]]; then
    grep -qiE "$re" <<<"$src"
  else
    grep -qiE "$re"
  fi
}

# Regex matching transient infra/auth errors emitted by the selected agent CLI
# (e.g. Vertex "403 ... IAM deny", 401/429/5xx API errors, model overload).
# These are environment failures, not fix failures.
INFRA_ERROR_RE='Failed to authenticate|API Error: (4|5)[0-9][0-9]|HTTP( error)?:[[:space:]]*(4|5)[0-9][0-9]|unexpected status (4|5)[0-9][0-9]|PERMISSION_DENIED|Overloaded|^ERROR: Selected model is at capacity\. Please try a different model\.$'

# Return 0 if a subagent's captured output looks like a transient infra/auth error.
is_infra_error() { _grep_pattern "$INFRA_ERROR_RE" "${1:-}"; }

# Regex matching DETERMINISTIC auth/permission/model errors (401/403, IAM deny,
# unknown/denied model). Unlike infra errors these do not clear on retry — the
# shell env points at a project/region/model the identity can't use — so callers
# must skip immediately without a retry storm. Account usage limits ("You've hit
# your session limit · resets ...") last hours, so they belong here too.
# Anchored to real signatures so a "403" inside e.g. a CVE id can't misroute a
# rate-limit (429) as auth.
AUTH_ERROR_RE='API Error: 40[13]|HTTP( error)?:[[:space:]]*40[13]|unexpected status 40[13]|40[13] Unauthorized|Missing bearer|not logged in|login required|PERMISSION_DENIED|Failed to authenticate|invalid model|model[^.]*not[^.]*found|(^|: )[[:space:]]*You.{1,3}ve hit your ([^ ]+ )*(limit|budget)|^[[:space:]]*Claude( AI)? usage limit reached'

# Return 0 if output looks like a deterministic auth/permission/model error.
# Check this BEFORE is_infra_error (403 matches both; auth must win to avoid retry storm).
is_auth_error() { _grep_pattern "$AUTH_ERROR_RE" "${1:-}"; }

# Regex matching transient scanner/runtime network errors (grype DB pull,
# docker/podman DNS) that may clear on retry — distinct from a real scan failure
# (e.g. invalid JSON from a broken config), which won't.
SCAN_TRANSIENT_RE='no route to host|TLS handshake timeout|server misbehaving|connection refused|i/o timeout|temporary failure in name resolution|could not connect|dial tcp|operation not permitted'

# Return 0 if scanner output looks like a transient network/runtime error.
is_scan_transient() { _grep_pattern "$SCAN_TRANSIENT_RE" "${1:-}"; }

# Return 0 if any executable in the tree is scanner-opaque or stale-readable.
# grype extracts stdlib versions only from binaries it can parse:
#
#   1. OPAQUE (UPX-packed): `go version -m` cannot parse the binary AND UPX!
#      packer magic is present in a non-text file. Executable scripts can quote
#      that magic without being packed. grype is blind to stdlib CVEs in a packed
#      binary; a "clean" scan is not trustworthy.
#
#   2. UNCOMPARABLE: a readable binary has a development/experimental compiler
#      marker that Grype cannot compare with advisory version ranges.
#
#   3. STALE READABLE: `go version -m` succeeds but the embedded Go version
#      differs from the host Go. grype CAN read the binary and WILL report its
#      stdlib CVEs, but they reflect the old toolchain, not the one in use now.
#      The remedy is `make clean` + rebuild. Checked only when the host `go`
#      command is available; absent-go repos (e.g. pure Dapper builds where host
#      and container Go differ legitimately) skip this check silently.
#
# Safe-direction: a false positive only forces a review, never hides a CVE.
# Detects UPX specifically (the common Go packer); other packers are a documented
# residual gap. All executables are checked (not just freshly-built ones).
# Usage: detect_opaque_binaries
detect_opaque_binaries() {
  local bin_path found=1 expected_go go_m_rc go_m_out bin_go bin_go_marker
  expected_go=$(compiler_go_version)
  # Only compare to the host toolchain for genuinely local builds. A Dapper
  # binary should match its configured builder, which may intentionally differ.
  if [[ -z "$expected_go" && -z "${BUILD_IMAGE:-}" ]]; then
    expected_go=$(go version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1 || true)
  fi
  while IFS= read -r bin_path; do
    go_m_rc=0
    go_m_out=$(go version -m "$bin_path" 2>/dev/null) || go_m_rc=$?
    if [[ $go_m_rc -ne 0 ]] && ! LC_ALL=C grep -Iq . "$bin_path" 2>/dev/null &&
       LC_ALL=C grep -qa 'UPX!' "$bin_path" 2>/dev/null; then
      # Case 1: packed/opaque binary — grype is blind to its stdlib CVEs
      echo "WARNING: packed/opaque binary — stdlib coverage unknown: $bin_path" >&2
      found=0
    elif [[ $go_m_rc -eq 0 ]]; then
      # Read the complete compiler marker after the path delimiter. Stripping
      # an experimental suffix can hide Grype's inability to compare that version.
      bin_go_marker=$(head -1 <<< "$go_m_out" | sed -n 's/^.*:[[:space:]]\{1,\}//p')
      [[ -n "$bin_go_marker" ]] || continue
      if ! [[ "$bin_go_marker" =~ ^go[0-9]+[.][0-9]+([.][0-9]+)?$ ]]; then
        echo "WARNING: uncomparable Go compiler marker ($bin_go_marker) — stdlib coverage unknown: $bin_path" >&2
        found=0
        continue
      fi
      bin_go="${bin_go_marker#go}"
      if [[ -n "$expected_go" && "$bin_go" != "$expected_go" ]]; then
        echo "WARNING: stale readable binary (Go $bin_go, expected $expected_go) — rebuild to scan current stdlib: $bin_path" >&2
        found=0
      fi
    fi
  done < <(find . -type f -perm -100 -not -path './.git/*' 2>/dev/null)
  return "$found"
}

# Regex matching grype vulnerability-DB update/load failures. grype degrades
# gracefully when it can't reach its DB source: it falls back to a stale or
# absent DB and still emits valid JSON — so a "clean" result is indistinguishable
# from a genuinely clean repo while silently under-reporting CVEs. A --fresh scan
# exists precisely to guarantee a current DB, so this failure invalidates its
# premise; callers treat it as unconfirmed, never clean.
# A failed application-release check does not invalidate the vulnerability DB.
GRYPE_DB_DEGRADED_RE='failed to fetch (the )?latest[^:]*[[:space:]](database|db)([[:space:]:]|$)|unable to (update|check).*(database|db)|failed to (load|update|read).*(vulnerability )?(database|db)|no (valid )?vulnerability database|database is older than|could not (download|update).*(database|db)|db update failed'

# Return 0 if scanner output shows a grype DB update/load failure.
grype_db_degraded() { _grep_pattern "$GRYPE_DB_DEGRADED_RE" "${1:-}"; }

# Extract the highest fix version for a CVE+package from grype's ignoredMatches JSON.
# Returns empty string if no fix version is available.
grype_ignored_fix_version() {
  local _vid="$1" _pkg="$2" _file="$3" _location="${4:-}"
  _location=$(normalize_scan_location "$_location")
  jq -r --arg vid "$_vid" --arg pkg "$_pkg" --arg location "$_location" '
    def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
    [.ignoredMatches[] |
      select(.vulnerability.id==$vid and .artifact.name==$pkg) |
      select($location == "" or any(.artifact.locations[]?; (.path | normloc) == $location)) |
      .vulnerability.fix.versions[]] |
    map(select(type=="string" and .!="")) |
    if length==0 then "" else sort_by(ltrimstr("v")|split("+")[0]|split("-")[0]|split(".")|map(tonumber? // 0))|last end' \
    "$_file" 2>/dev/null || true
}

# Return 0 if the scan-regression companion recorded a scanner failure
# (SCAN_FAILED sentinel). A scanner failure means the final scan is unreliable,
# so an LLM PASS must NOT be trusted — the caller forces the fix unverified.
scan_regression_failed() {
  local report_dir="${1:?scan_regression_failed REPORT_DIR}"
  local ev="$report_dir/scan-regression.evidence"
  # Fail closed when the companion left no trustworthy evidence: a missing file,
  # a crash before its NEW_CVES= marker (set -e abort), or an explicit scanner
  # failure. Keep the SCAN_FAILED=1 check even though such files carry a
  # NEW_CVES=0 line (emitted before the sentinel), so it isn't masked here.
  [[ -f "$ev" ]] || return 0
  grep -q '^SCAN_FAILED=1' "$ev" 2>/dev/null && return 0
  grep -q '^NEW_CVES=' "$ev" 2>/dev/null || return 0
  return 1
}

# Aggregate every companion's deterministic .evidence into a single verdict.
# Companions emit counters (scan-regression: NEW_CVES/UNRESOLVED; the others:
# NEW_ISSUES) plus SKIP:/SCAN_FAILED lines. Returns 0 (PASS) only when at least
# one evidence file exists AND all are clean: every counter 0, no SKIP:, no
# SCAN_FAILED. Returns 1 for FAIL (a counter > 0) or INCONCLUSIVE (missing/empty
# evidence, SKIP, or scanner failure) so callers fail closed when the LLM gate
# is unavailable. Used as the authoritative fallback when the LLM is blocked.
evidence_verdict() {
  local report_dir="${1:?evidence_verdict REPORT_DIR [SUBAGENT_DIR]}"
  local subagent_dir="${2:-}"
  local ev found=0 problems=0 name
  # When the companion set is known, require one complete evidence file for
  # every companion. A partial directory is not proof of a clean result.
  if [[ -n "$subagent_dir" ]]; then
    local sh_file expected
    for sh_file in "$subagent_dir"/*.sh; do
      [[ -f "$sh_file" ]] || continue
      expected="$report_dir/$(basename "$sh_file" .sh).evidence"
      if [[ ! -f "$expected" ]]; then
        echo "  evidence INCONCLUSIVE: missing $(basename "$expected")" >&2
        problems=1
      fi
    done
  fi
  shopt -s nullglob
  for ev in "$report_dir"/*.evidence; do
    found=1
    name=$(basename "$ev" .evidence)
    if grep -qE '(NEW_CVES|UNRESOLVED|NEW_ISSUES)=[1-9]' "$ev" 2>/dev/null; then
      echo "  evidence FAIL: $name has outstanding issues" >&2
      problems=1
    fi
    if grep -qE '^SCAN_FAILED=1|^SKIP:' "$ev" 2>/dev/null; then
      echo "  evidence INCONCLUSIVE: $name did not complete" >&2
      problems=1
    fi
    # A present-but-marker-less file means the companion crashed before emitting
    # its counter line (set -e under pipefail) — treat as INCONCLUSIVE, not clean.
    if ! grep -qE '(NEW_CVES|UNRESOLVED|NEW_ISSUES)=|^SCAN_FAILED=1|^SKIP:' "$ev" 2>/dev/null; then
      echo "  evidence INCONCLUSIVE: $name produced no marker" >&2
      problems=1
    fi
  done
  shopt -u nullglob
  if [[ $found -eq 0 ]]; then
    echo "  evidence INCONCLUSIVE: no companion evidence found" >&2
    return 1
  fi
  [[ $problems -eq 0 ]]
}

# Print companion names whose deterministic counters are non-zero. This is
# deliberately independent of the LLM report: a model PASS cannot overrule
# scanner evidence, and an unavailable model cannot prevent deterministic repair.
evidence_issue_names() {
  local report_dir="${1:?evidence_issue_names REPORT_DIR}" ev
  shopt -s nullglob
  for ev in "$report_dir"/*.evidence; do
    if grep -qE '(NEW_CVES|UNRESOLVED|NEW_ISSUES)=[1-9]' "$ev" 2>/dev/null; then
      basename "$ev" .evidence
    fi
  done
  shopt -u nullglob
}

# Wrap raw companion output in the report shape consumed by deterministic fix
# handlers. The raw evidence stays authoritative and remains preserved for audit.
evidence_as_report() {
  local evidence_file="${1:?evidence_as_report EVIDENCE_FILE REPORT_FILE}" report_file="$2"
  local issues
  issues=$(grep -oE '(NEW_CVES|UNRESOLVED|NEW_ISSUES)=[0-9]+' "$evidence_file" 2>/dev/null | \
    awk -F= '{s += $2} END {print s + 0}')
  {
    echo "VERDICT: FAIL"
    echo "ISSUES: $issues"
    echo "SUMMARY: Deterministic companion found actionable issues"
    echo "DETAILS:"
    grep -vE '^(NEW_CVES|NEW_ISSUES)=' "$evidence_file" || true
  } > "$report_file"
}

# Extract the final structured report from a CLI transcript. Codex may echo the
# prompt (including valid-looking examples) before printing its answer, and may
# repeat the answer after usage metadata. Select the last complete, typed report
# block so prompt examples can never become an authoritative verdict.
extract_agent_report() {
  local input_file="${1:?extract_agent_report INPUT_FILE OUTPUT_FILE}" output_file="$2"
  awk '
    /^VERDICT: (PASS|FAIL|SKIP)$/ {
      candidate = NR
      verdict = $0
      next
    }
    candidate && NR == candidate + 1 && /^ISSUES: [0-9]+$/ {
      issues = $0
      next
    }
    candidate && NR == candidate + 2 && /^SUMMARY: .+$/ {
      summary = $0
      next
    }
    candidate && NR == candidate + 3 && /^DETAILS:$/ {
      last = candidate
      last_verdict = verdict
      last_issues = issues
      last_summary = summary
    }
    { lines[NR] = $0 }
    END {
      if (!last) exit 1
      print last_verdict
      print last_issues
      print last_summary
      print "DETAILS:"
      for (i = last + 4; i <= NR; i++) print lines[i]
    }
  ' "$input_file" > "$output_file"
}

# Return 0 when a sentinel file contains either the exact package/location key
# or an explicitly unscoped package key. A scoped sentinel must never exempt the
# same package in a different module; an unscoped fix attempt covered the repo.
pkg_sentinel_file_matches() {
  local _file="$1" _pkg="$2" _loc="${3:-}" _key
  [[ -f "$_file" ]] || return 1
  _loc=$(normalize_scan_location "$_loc")
  _key="$_pkg${_loc:+|$_loc}"
  grep -qxF "$_key" "$_file" 2>/dev/null && return 0
  [[ -n "$_loc" ]] && grep -qxF "$_pkg" "$_file" 2>/dev/null
}

# Return 0 if PKG/scope appears in any skip-sentinel file under REPORT_DIR.
pkg_is_exempt() {
  local _pkg="$1" _dir="$2" _loc="${3:-}"
  [[ -z "$_dir" ]] && return 1
  pkg_sentinel_file_matches "$_dir/needs-review-pkgs" "$_pkg" "$_loc" && return 0
  pkg_sentinel_file_matches "$_dir/fix-failed-pkgs" "$_pkg" "$_loc" && return 0
  return 1
}

# Existing or tracked vendor trees belong to their own tracked module, including
# nested modules when the repository root does not itself use vendoring.
find_vendor_dirs() {
  local gomod vendor_dir
  while IFS= read -r gomod; do
    vendor_dir="${gomod%go.mod}vendor"
    vendor_dir="${vendor_dir#./}"
    if [[ -d "$vendor_dir" ]] || [[ -n "$(git ls-files -- "$vendor_dir")" ]]; then
      printf '%s\n' "$vendor_dir"
    fi
  done < <(find_gomods)
}

# Stage changed module files and their changed vendor trees. An unrelated module
# must not contribute its pre-existing untracked vendor files to this update.
stage_gomod_files() {
  local -a _mod_files
  local gomod vendor_dir
  while IFS= read -r vendor_dir; do
    gomod="${vendor_dir%/vendor}/go.mod"
    [[ "$vendor_dir" != vendor ]] || gomod=go.mod
    if ! git check-ignore -q -- "$vendor_dir" &&
       ! git diff --quiet HEAD -- "$gomod" "${gomod%go.mod}go.sum" "$vendor_dir"; then
      git add -A -- "$vendor_dir"
    fi
  done < <(find_vendor_dirs)
  mapfile -t _mod_files < <(git diff --name-only | grep -E '(^|/)go\.(mod|sum|work(\.sum)?)$')
  [[ ${#_mod_files[@]} -gt 0 ]] && git add -- "${_mod_files[@]}"
  return 0
}

# Match only a complete YAML annotation version stamp, including raw YAML lines
# embedded in generated Go. Mentioning the annotation in program text is not noise.
controller_gen_version_pattern() {
  printf '%s\n' '^[[:space:]]*controller-gen[.]kubebuilder[.]io/version:[[:space:]]*v?[0-9]+([.][0-9]+)*([-+][[:alnum:]_.+-]+)?[[:space:]]*$'
}

protoc_version_pattern() {
  printf '%s\n' '^//[[:space:]]+(protoc-gen-go|protoc)[[:space:]]+v?[0-9]+([.][0-9]+)*([-+][[:alnum:]_.+-]+)?[[:space:]]*$'
}

# True when FILE is a tracked generated file that DIFF_IGNORE_ARGS is meant to
# tolerate: a protoc-gen-go output or a file carrying the controller-gen version
# annotation. Dependency files, .grype.yaml and vendor/ are never generated noise.
_is_tolerated_generated_file() {
  local file="$1"
  case "$file" in
    go.mod|*/go.mod|go.sum|*/go.sum|go.work|go.work.sum|.grype.yaml|*/.grype.yaml|vendor/*|*/vendor/*) return 1 ;;
  esac
  [[ "$file" == *.pb.go ]] || grep -qF 'controller-gen.kubebuilder.io/version' -- "$file" 2>/dev/null
}

# Generated files that the first, pre-fix build already changes are out of date
# on the base branch. Record and restore them so fix commits never absorb drift
# the repository had before this run.
record_generated_drift() {
  local drift="${STATE_FILE}.generated-drift" file
  local -a ignore_args=()
  : > "$drift"
  [[ -n "${DIFF_IGNORE_ARGS:-}" ]] || return 0
  read -ra ignore_args <<< "$DIFF_IGNORE_ARGS"
  while IFS= read -r file; do
    _is_tolerated_generated_file "$file" || continue
    git diff --quiet "${ignore_args[@]}" -- "$file" || printf '%s\n' "$file" >> "$drift"
    git checkout -- "$file"
  done < <(git diff --name-only)
}

# Reconcile generated files the scan build left dirty. A file whose diff is
# empty once DIFF_IGNORE_ARGS (the `git diff -I` regexes detect.sh enabled) is
# applied differs only by tool-version noise and is restored. A file with a
# substantive change is staged, as dependency updates can legitimately change
# generated output. A no-op unless detect.sh found a rule that applies.
reconcile_generated_files() {
  [[ -n "${DIFF_IGNORE_ARGS:-}" ]] || return 0
  local -a ignore_args=()
  local file diff_rc
  read -ra ignore_args <<< "$DIFF_IGNORE_ARGS"
  while IFS= read -r file; do
    _is_tolerated_generated_file "$file" || continue
    if grep -qxF -- "$file" "${STATE_FILE:-/dev/null}.generated-drift" 2>/dev/null; then
      git checkout -- "$file"
      continue
    fi
    # grep -q can close a large diff early. Under pipefail Git's SIGPIPE then
    # makes a substantive update look empty and discards it. Use Git's status
    # directly, and propagate errors rather than treating them as version noise.
    diff_rc=0
    git diff --quiet "${ignore_args[@]}" -- "$file" || diff_rc=$?
    case "$diff_rc" in
      0) git checkout -- "$file" ;;
      1) git add -- "$file" ;;
      *) return "$diff_rc" ;;
    esac
  done < <(git diff --name-only)
}

# Reject a fix branch that touches files other than dependency metadata
# (go.mod, go.sum, .grype.yaml, and their submodule variants like tools/go.mod).
# Prints a warning and returns nonzero when unexpected files are found; silent
# and successful otherwise.
# Takes a single arg: the upstream base branch name (e.g. "release-0.24").
# Reads from git in the current working directory; a no-op when git is absent.
audit_branch_non_cve_files() {
  local base_branch="${1:?audit_branch_non_cve_files BASE_BRANCH}"
  local unexpected_files
  # Files that are expected in a CVE-only fix branch: go.mod, go.sum, .grype.yaml
  # and their submodule variants (e.g. tools/go.mod, coredns/go.sum).
  unexpected_files=$(git --no-pager diff --name-only "origin/$base_branch"..HEAD 2>/dev/null | \
    grep -Ev '(^|/)(go\.(mod|sum)|\.grype\.yaml)$|^go\.work(\.sum)?$|(^|/)vendor/' || true)
  if [[ -n "$unexpected_files" ]]; then
    echo ""
    echo "WARNING: CVE fix branch touches non-dependency files:"
    printf '  %s\n' "${unexpected_files//$'\n'/$'\n  '}"
    echo "Confirm these changes belong in a CVE-only PR, or move them to a separate branch."
    return 1
  fi
}

# Decide the run's final exit code from the post-fix rescan gate and the non-CVE
# failure flags. Prints "2" (needs attention) when actionable CVEs still remain
# (remaining > 0), the gate rescan itself couldn't be trusted (gate_failed —
# build or scanner failure), tests failed, or verification never confirmed the
# fixes, or PR prerequisites failed. Prints "0" only when the gate is clean
# and every check passed. Pure decision logic with no I/O so it can be
# unit-tested offline.
cve_fix_exit_code() {
  local remaining="${1:-0}" gate_failed="${2:-false}"
  # Sanitize remaining: non-numeric values (e.g. "false" in tests) → 0
  [[ "$remaining" =~ ^[0-9]+$ ]] || remaining=0
  local tests_failed="${3:-false}" verify_failed="${4:-false}"
  local unseen_needs_review="${5:-false}"
  local pr_not_ready="${6:-false}"
  if [[ "$remaining" -gt 0 || "$gate_failed" == "true" \
     || "$tests_failed" == "true" || "$verify_failed" == "true" \
     || "$unseen_needs_review" == "true" || "$pr_not_ready" == "true" ]]; then
    echo 2
  else
    echo 0
  fi
}

# True when fix results are not ready to push. A clean vulnerability rescan does
# not prove that dependency updates compile or preserve behavior, and a stale
# base ref can make an otherwise correct branch incomplete, so test/fetch failures
# suppress the ready-to-run PR command too.
results_unconfirmed() {
  local gate_failed="${1:-false}" tests_failed="${2:-false}" verify_failed="${3:-false}"
  local unseen_needs_review="${4:-false}" gate_remaining="${5:-0}" fetch_failed="${6:-false}"
  local base_changed="${7:-false}" dco_failed="${8:-false}" base_refresh_failed="${9:-false}"
  local policy_check_failed="${10:-false}"
  # Repository policy gates also apply to counted partial fixes. The permission
  # to submit outstanding advisories does not waive licensing or file scope.
  # Infrastructure, test, and stale-base failures always suppress the PR.
  [[ "$gate_failed" == "true" || "$tests_failed" == "true" || \
     "$verify_failed" == "true" || "$fetch_failed" == "true" || \
     "$base_changed" == "true" || "$dco_failed" == "true" || \
     "$base_refresh_failed" == "true" || "$policy_check_failed" == "true" ]] && return 0
  # Policy UNRESOLVED items (review agent said team input needed) suppress the PR
  # only when gate_remaining=0. When gate_remaining>0, the partial-fix PR title
  # already signals outstanding CVEs; suppressing blocks valid commits from being
  # submitted just because one package needs a policy decision.
  [[ "$unseen_needs_review" == "true" && "$gate_remaining" -eq 0 ]]
}

# Print commits in BASE..HEAD whose messages have no DCO sign-off. A generated
# fix branch must be safe to push, including any manual follow-up commits.
dco_missing_commits() {
  local base="$1" sha
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    git show -s --format='%B' "$sha" | grep -qE '^Signed-off-by: .+ <[^>]+>[[:space:]]*$' ||
      printf '%s\n' "$sha"
  done < <(git rev-list "$base"..HEAD)
}

# Print provider-relevant environment to help diagnose an auth error (e.g. a
# Vertex 403 from a mis-pointed region/project). Credential-looking values are
# masked; routing vars (region/project) are shown since they are the diagnostic.
print_provider_env() {
  echo "  Provider environment seen by the subagent:" >&2
  local shown=0 name val env_var provider_re
  case "${CVE_FIX_AGENT:-claude}" in
    codex) provider_re='^(CODEX_|OPENAI_|AZURE_OPENAI_|AWS_)' ;;
    *)     provider_re='^(CLAUDE_|ANTHROPIC_|CLOUD_ML_|AWS_|[^=]*VERTEX[^=]*|[^=]*BEDROCK[^=]*)=' ;;
  esac
  while IFS='=' read -r name val; do
    case "$name" in
      *KEY*|*TOKEN*|*SECRET*|*PASSWORD*|*CREDENTIAL*) val='***' ;;
    esac
    echo "    $name=$val" >&2
    shown=1
  done < <(env | grep -E "$provider_re" | sort)
  for env_var in ${ENV_UNSET:-}; do
    [[ -z "${!env_var:-}" ]] && continue
    case "$env_var" in
      *KEY*|*TOKEN*|*SECRET*|*PASSWORD*|*CREDENTIAL*) echo "    $env_var=***" >&2 ;;
      *) echo "    $env_var=${!env_var}" >&2 ;;
    esac
    shown=1
  done
  [[ $shown -eq 0 ]] && echo "    (none set)" >&2
  echo "  Hint: fix your shell rc / provider config, or add the offending var to" >&2
  echo "        'unset-env' in the repo config so subagents don't inherit it." >&2
}

# Distribution toolchains can set GOEXPERIMENT in GOROOT/go.env (Fedora sets
# nodwarf5). Their binaries report versions such as go1.26.8-X:nodwarf5, which
# Grype records verbatim and cannot match, so stdlib coverage stays unknown.
# When the caller chose no experiments, build with upstream defaults for the
# whole run; an explicit GOEXPERIMENT is kept and remains fail-closed.
use_upstream_goexperiment() {
  local default
  [[ -z "${GOEXPERIMENT+set}" ]] || return 0
  default=$(cd / && go env GOEXPERIMENT 2>/dev/null) || return 0
  # A value set with "go env -w" is the user's choice, not a distribution default.
  [[ -n "$default" && "$default" == "$(cd / && GOENV=off go env GOEXPERIMENT 2>/dev/null)" ]] || return 0
  export GOEXPERIMENT=,
}

compiler_go_version() {
  echo "$BUILD_GO_VERSION" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo ""
}

# Whether REQUIRED may replace CURRENT under the builder policy. A detected
# builder is the exact upper bound (including patch). Without builder evidence,
# only a same-minor directive change is automatically allowed.
go_directive_supported() {
  local current="${1#go}" required="${2#go}" builder="${3#go}"
  [[ -n "$current" && -n "$required" ]] || return 1
  # Dependency remediation must never lower the repository's language/toolchain
  # floor, even when the builder could run the lower version.
  version_gte "$required" "$current" || return 1
  if [[ -n "$builder" ]]; then
    version_gte "$builder" "$required"
  else
    [[ "$(printf '%s' "$current" | cut -d. -f1-2)" == \
       "$(printf '%s' "$required" | cut -d. -f1-2)" ]]
  fi
}

# Commit linters commonly enforce 80-column bodies. One trailer per advisory
# stays readable and bounded regardless of group size.
format_cve_fixes() {
  printf 'Fixes: %s\n' "$@"
}

# Populate ENV_SCRUB with an 'env -u VAR …' prefix removing the ENV_UNSET names
# from a child's environment. Expand as "${ENV_SCRUB[@]+"${ENV_SCRUB[@]}"}".
# It uses env(1), never eval: prompts are untrusted text.
ENV_SCRUB=()
build_env_scrub() {
  ENV_SCRUB=()
  [[ -z "${ENV_UNSET:-}" ]] && return 0
  ENV_SCRUB=(env)
  local env_var
  for env_var in ${ENV_UNSET}; do ENV_SCRUB+=(-u "$env_var"); done
}

# Track executable artifacts produced by this run's builds. Some repositories
# write hash-named binaries into the source tree; retaining an older generated
# binary makes the next Grype scan report stale CVEs even though go.mod and the
# current binary are fixed. Only files created by this run are removed; files
# present before the run remain part of the scan.
# shellcheck disable=SC2153 # STATE_FILE comes from the loaded run state
artifact_manifest_prepare() {
  local manifest="${STATE_FILE}.generated-artifacts" baseline="${STATE_FILE}.baseline-artifacts"
  if [[ ! -f "$baseline" ]]; then
    find "$REPO" -path "$REPO/.git" -prune -o -type f -perm -u+x -print | sort > "$baseline"
  fi
  if [[ -f "$manifest" ]]; then
    while IFS= read -r artifact; do
      [[ -z "$artifact" || ! -f "$artifact" ]] || rm -f -- "$artifact"
    done < "$manifest"
  fi
}

artifact_manifest_record() {
  local manifest="${STATE_FILE}.generated-artifacts" baseline="${STATE_FILE}.baseline-artifacts" current
  current=$(mktemp "${TMPDIR:-/tmp}/cve-fix-artifacts.XXXXXX")
  find "$REPO" -path "$REPO/.git" -prune -o -type f -perm -u+x -print | sort > "$current"
  comm -23 "$current" "$baseline" > "$manifest"
  rm -f "$current"
}

# Return the DETAILS: body of a subagent report, stripping the header line.
# Replaces the fragile 'grep -A 999 | tail -n +2' pattern used at three call sites.
_details_section() { awk '/^DETAILS:/{f=1;next} f' "$1"; }

# Seconds to wait before retry attempt N (1-based): exponential backoff
# base*2^(N-1), capped at 30s. CVE_FIX_RETRY_BASE overrides the base (tests
# set it to 0 for instant retries).
cve_fix_backoff_delay() {
  local attempt="${1:-1}" base="${CVE_FIX_RETRY_BASE:-2}" delay
  delay=$(( base * (1 << (attempt - 1)) ))
  (( delay > 30 )) && delay=30
  echo "$delay"
}

# Classify a failed subagent run as retry/skip/fail.
# Auth errors skip immediately (deterministic). Infra errors retry until exhausted, then skip.
# Anything else (no report, genuine failure) is fail.
subagent_retry_decision() {
  local rc="$1" f="$2" attempt="$3" max="$4"
  if is_auth_error "$f"; then echo skip; return; fi
  if [[ "$rc" -eq 124 ]] || is_infra_error "$f"; then
    [[ $attempt -lt $max ]] && { echo retry; return; }
    echo skip; return
  fi
  echo fail
}

# Phase-1 helper: run companion .sh scripts sequentially, writing evidence files.
_run_companions() {
  local subagent_dir="$1" state_file="$2" report_dir="$3"
  local sh_file sa_name evidence scan_regression="$subagent_dir/scan-regression.sh"
  local -a ordered=()
  [[ -f "$scan_regression" ]] && ordered+=("$scan_regression")
  for sh_file in "$subagent_dir"/*.sh; do
    [[ -f "$sh_file" ]] || continue
    [[ "$sh_file" == "$scan_regression" ]] || ordered+=("$sh_file")
  done
  # Audit ignores against this iteration's rescan, not the initial snapshot.
  for sh_file in "${ordered[@]+"${ordered[@]}"}"; do
    sa_name=$(basename "$sh_file" .sh)
    echo "  Companion: $sa_name..."
    _rc=0
    evidence=$(bash "$sh_file" "$state_file" "$report_dir" 2>&1) || _rc=$?
    if [[ $_rc -ne 0 ]]; then
      printf '%s\nSKIP: companion crashed (exit %s)\n' "$evidence" "$_rc" \
        > "$report_dir/${sa_name}.evidence"
    else
      printf '%s\n' "$evidence" > "$report_dir/${sa_name}.evidence"
    fi
  done
}

# Phase-2 helper: launch all _RSA_PENDING agents in parallel.
# Reads _RSA_PENDING and _RSA_PROMPT; writes _RSA_PIDS.
_launch_llm_agents() {
  local report_dir="$1" attempt="$2" max_attempts="$3"
  local sa_name
  _RSA_PIDS=()
  for sa_name in "${_RSA_PENDING[@]}"; do
    if [[ $attempt -eq 1 ]]; then
      echo "  Subagent: $sa_name..."
    else
      echo "  Subagent: $sa_name (retry $((attempt - 1))/$((max_attempts - 1)))..."
    fi
    build_cve_fix_agent_command "${_RSA_PROMPT[$sa_name]}"
    timeout "${CVE_FIX_AGENT_TIMEOUT:-600}" \
      "${ENV_SCRUB[@]+"${ENV_SCRUB[@]}"}" "${CVE_FIX_AGENT_CMD[@]}" \
      </dev/null \
      > "$report_dir/${sa_name}.agent-output" 2>&1 &
    _RSA_PIDS+=("$!:$sa_name")
  done
}

# Phase-3 helper: wait for _RSA_PIDS and classify each result.
# Reads _RSA_PIDS; writes _RSA_FAILED, _RSA_SKIPPED, _RSA_UNVERIFIED, _RSA_RETRY.
_collect_agent_results() {
  local report_dir="$1" attempt="$2" max_attempts="$3"
  local provider="${CVE_FIX_AGENT:-claude}"
  _RSA_FAILED=() _RSA_SKIPPED=() _RSA_UNVERIFIED=() _RSA_RETRY=()
  local pid_name pid sa_name rc report_file output_file verdict issues
  for pid_name in "${_RSA_PIDS[@]}"; do
    pid="${pid_name%%:*}" sa_name="${pid_name#*:}" rc=0
    wait "$pid" 2>/dev/null || rc=$?
    report_file="$report_dir/${sa_name}.report"
    output_file="$report_dir/${sa_name}.agent-output"
    # Provider errors can exit zero after echoing a valid-looking prompt example.
    # Classify them before accepting any report from the transcript.
    local _decision
    _decision=$(subagent_retry_decision "$rc" "$output_file" "$attempt" "$max_attempts")
    case "$_decision" in
      skip)
        if is_auth_error "$output_file"; then
          echo "  SKIP: $sa_name — $provider auth error (exit $rc); not retrying"
          print_provider_env
        else
          echo "  SKIP: $sa_name — $provider unavailable (infra error, exit $rc)"
        fi
        _RSA_SKIPPED+=("$sa_name")
        continue
        ;;
      retry) _RSA_RETRY+=("$sa_name"); continue ;;
    esac

    if [[ $rc -ne 0 ]]; then
      echo "  WARNING: $sa_name exited $rc; its report is unconfirmed"
      _RSA_UNVERIFIED+=("$sa_name")
      continue
    fi

    # Read-only agents return the report on stdout. Parse the final complete
    # report rather than copying a transcript that may echo prompt examples.
    if [[ ! -f "$report_file" ]] && \
       extract_agent_report "$output_file" "$report_file.tmp" 2>/dev/null; then
      mv "$report_file.tmp" "$report_file"
    else
      rm -f "$report_file.tmp"
    fi
    if [[ -f "$report_file" ]]; then
      verdict=$(grep '^VERDICT:' "$report_file" | head -1 | awk '{print $2}')
      issues=$(grep '^ISSUES:' "$report_file" | head -1 | awk '{print $2}')
      echo "  $sa_name: ${verdict:-<none>} (issues: ${issues:-?})"
      # Fail closed: only an explicit PASS clears a subagent. FAIL is a real
      # regression; SKIP means the agent intentionally opted out (falls back to
      # deterministic evidence); anything else (empty/garbled) is unverified.
      case "$verdict" in
        PASS) ;;
        FAIL) _RSA_FAILED+=("$sa_name") ;;
        SKIP) echo "  SKIP (agent opted out): $sa_name"
              _RSA_SKIPPED+=("$sa_name") ;;
        *)    _RSA_UNVERIFIED+=("$sa_name") ;;
      esac
    else
      echo "  WARNING: $sa_name produced no report"
      _RSA_FAILED+=("$sa_name")
    fi
  done
}

# Run verification subagents: companion scripts first, then LLM subagents in parallel.
# Usage: run_subagents STATE_FILE SUBAGENT_DIR REPORT_DIR
# Returns: 0 if all pass OR all remaining were skipped/unverified, 1 if any FAIL.
# Sets globals RUN_SUBAGENTS_SKIPPED / _SKIPPED_NAMES (infra/auth skips) and
# RUN_SUBAGENTS_UNVERIFIED / _UNVERIFIED_NAMES (report present but verdict not
# PASS). The caller (verify_fix_loop) treats a non-zero skip OR unverified count
# as "not verified" so a blocked/garbled subagent never reads as a silent pass.
run_subagents() {
  local state_file="$1" subagent_dir="$2" report_dir="$3"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  local -A _RSA_PROMPT         # sa_name -> expanded prompt (built once per run)
  local -a _RSA_PENDING        # agents still to launch this attempt
  local -a _RSA_PIDS           # "pid:name" pairs from _launch_llm_agents
  local -a _RSA_FAILED         # agents with FAIL verdict or no report
  local -a _RSA_SKIPPED        # agents skipped for auth/infra reasons
  local -a _RSA_UNVERIFIED     # agents with non-PASS report verdict
  local -a _RSA_RETRY          # agents queued for backoff retry

  RUN_SUBAGENTS_SKIPPED=0 RUN_SUBAGENTS_SKIPPED_NAMES=""
  RUN_SUBAGENTS_UNVERIFIED=0 RUN_SUBAGENTS_UNVERIFIED_NAMES=""
  # Keep this established global name for compatibility with callers that
  # source lib.sh. It now means that the selected agent (Claude or Codex) is
  # absent, despite the legacy Claude-specific spelling.
  RUN_SUBAGENTS_CLAUDE_ABSENT=0

  # The public script already validated this generated state file with
  # load_state; source it without changing the caller's working directory.
  # shellcheck source=/dev/null
  source "$state_file"
  mkdir -p "$report_dir"
  rm -f "$report_dir"/*.report  # Clear stale reports (crashed agent can't mask prior PASS)

  _run_companions "$subagent_dir" "$state_file" "$report_dir"

  # When the selected agent is absent, companion evidence from Phase 1 is authoritative;
  # verify_fix_loop falls back to evidence_verdict.
  local provider
  provider=$(cve_fix_agent_provider) || return 1
  if ! command -v "$provider" &>/dev/null; then
    echo "  WARNING: $provider CLI not available; relying on deterministic evidence."
    RUN_SUBAGENTS_CLAUDE_ABSENT=1
    return 0
  fi

  # Scrub provider vars (ENV_UNSET) from the subagent env so a mis-pointed shell
  # rc can't force a Vertex/Bedrock auth failure. Built once, reused per launch.
  build_env_scrub
  local max_attempts="${CVE_FIX_AGENT_ATTEMPTS:-3}"

  # Build each subagent's prompt once (reused across retries).
  _RSA_PROMPT=() _RSA_PENDING=()
  local md_file sa_name evidence_file companion_evidence prompt_template
  for md_file in "$subagent_dir"/*.md; do
    [[ -f "$md_file" ]] || continue
    sa_name=$(basename "$md_file" .md)
    _RSA_PENDING+=("$sa_name")
    evidence_file="$report_dir/${sa_name}.evidence"
    companion_evidence=""
    [[ -f "$evidence_file" ]] && companion_evidence=$(cat "$evidence_file")
    prompt_template=$(cat "$md_file")
    _RSA_PROMPT["$sa_name"]=$(REPO="$REPO" BRANCH="$BRANCH" CVE_SCRIPTS="$script_dir" \
      REPORT_DIR="$report_dir" SUBAGENT_NAME="$sa_name" \
      COMPANION_EVIDENCE="$companion_evidence" \
      render_template REPO BRANCH CVE_SCRIPTS REPORT_DIR SUBAGENT_NAME COMPANION_EVIDENCE \
      <<< "$prompt_template")
  done
  [[ ${#_RSA_PENDING[@]} -eq 0 ]] && return 0

  local failed=() skipped=() unverified=()
  local attempt delay
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    [[ ${#_RSA_PENDING[@]} -eq 0 ]] && break
    _launch_llm_agents "$report_dir" "$attempt" "$max_attempts"
    _collect_agent_results "$report_dir" "$attempt" "$max_attempts"
    failed+=(${_RSA_FAILED[@]+"${_RSA_FAILED[@]}"})
    skipped+=(${_RSA_SKIPPED[@]+"${_RSA_SKIPPED[@]}"})
    unverified+=(${_RSA_UNVERIFIED[@]+"${_RSA_UNVERIFIED[@]}"})
    _RSA_PENDING=(${_RSA_RETRY[@]+"${_RSA_RETRY[@]}"})
    if [[ ${#_RSA_PENDING[@]} -gt 0 ]]; then
      delay=$(cve_fix_backoff_delay "$attempt")
      echo "  ${#_RSA_PENDING[@]} subagent(s) hit a transient error; retrying in ${delay}s..."
      sleep "$delay"
    fi
  done

  if [[ ${#skipped[@]} -gt 0 ]]; then
    echo "  SKIPPED (infra/auth, not verified): ${skipped[*]}"
    RUN_SUBAGENTS_SKIPPED=${#skipped[@]}
    # shellcheck disable=SC2034 # output variable read by verify_fix_loop
    RUN_SUBAGENTS_SKIPPED_NAMES="${skipped[*]}"
  fi
  if [[ ${#unverified[@]} -gt 0 ]]; then
    echo "  UNVERIFIED (non-PASS verdict): ${unverified[*]}"
    RUN_SUBAGENTS_UNVERIFIED=${#unverified[@]}
    RUN_SUBAGENTS_UNVERIFIED_NAMES="${unverified[*]}"
  fi
  if [[ ${#failed[@]} -gt 0 ]]; then
    echo "  FAILED: ${failed[*]}"
    return 1
  fi
  return 0
}

# Run subagents with verify-fix loop.
# Usage: verify_fix_loop STATE_FILE SUBAGENT_DIR REPORT_DIR [MAX_ITERATIONS]
verify_fix_loop() {
  local state_file="$1" subagent_dir="$2" report_dir="$3" max_iter="${4:-3}"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  for ((i=1; i<=max_iter; i++)); do
    echo ""
    echo "Verification iteration $i/$max_iter..."

    local run_rc=0
    run_subagents "$state_file" "$subagent_dir" "$report_dir" || run_rc=$?

    # Evidence completeness and scanner health are prerequisites. Do this before
    # reading any LLM verdict so a PASS can never mask a crashed companion.
    if scan_regression_failed "$report_dir" || ! evidence_verdict "$report_dir" "$subagent_dir"; then
      local -a dirty_evidence=()
      mapfile -t dirty_evidence < <(evidence_issue_names "$report_dir")
      if [[ ${#dirty_evidence[@]} -eq 0 ]]; then
        echo "Verification INCONCLUSIVE — deterministic evidence is incomplete; fix NOT verified."
        return 1
      fi

      if [[ $i -eq $max_iter ]]; then
        echo "Deterministic issues remain after $max_iter iterations."
        return 1
      fi

      # Dispatch every dirty companion directly from its evidence. LLM reports
      # remain a semantic cross-check, never the trigger for known mechanical work.
      local sa_name evidence_file synthesized fix_fn
      for sa_name in "${dirty_evidence[@]}"; do
        evidence_file="$report_dir/${sa_name}.evidence"
        synthesized="$report_dir/${sa_name}.deterministic.report"
        evidence_as_report "$evidence_file" "$synthesized"
        fix_fn="subagent_fix_${sa_name//-/_}"
        echo "  Fixing deterministic evidence: $sa_name"
        if declare -f "$fix_fn" &>/dev/null; then
          "$fix_fn" "$state_file" "$synthesized" "$script_dir" || true
        else
          echo "  No deterministic fix for $sa_name"
        fi
        rm -f "$synthesized"
      done
      continue
    fi

    if [[ $run_rc -eq 0 ]]; then
      RUN_SUBAGENTS_VERIFIED_BY=""
      # A report that exists but isn't PASS is a real signal — fail closed
      # (this precedes the evidence fallback per design).
      if [[ "${RUN_SUBAGENTS_UNVERIFIED:-0}" -gt 0 ]]; then
        echo "Verification UNVERIFIED (non-PASS verdict) — fix NOT verified: ${RUN_SUBAGENTS_UNVERIFIED_NAMES}"
        return 1
      fi
      # When the LLM gave no verdict (absent, or every subagent skipped for
      # infra/auth), the deterministic companion evidence is authoritative — it
      # was still produced in Phase 1. Consult it rather than blindly passing.
      if [[ "${RUN_SUBAGENTS_CLAUDE_ABSENT:-0}" -gt 0 || "${RUN_SUBAGENTS_SKIPPED:-0}" -gt 0 ]]; then
        if evidence_verdict "$report_dir" "$subagent_dir"; then
          echo "Verified deterministically (LLM cross-check unavailable)."
          RUN_SUBAGENTS_VERIFIED_BY=evidence
          return 0
        fi
        echo "Deterministic evidence did not confirm the fix — fix NOT verified."
        return 1
      fi
      echo "All subagents passed."
      # shellcheck disable=SC2034 # output variable used by callers/tests
      RUN_SUBAGENTS_VERIFIED_BY=llm
      return 0
    fi

    if [[ $i -eq $max_iter ]]; then
      echo "Subagents still failing after $max_iter iterations."
      return 1
    fi

    # A semantic reviewer disagreement with clean deterministic evidence is
    # advisory and cannot authorize mutation. Fail closed for human review.
    echo "LLM review disagreed with clean deterministic evidence; no model-proposed changes were applied."
    return 1
  done
}

# Fix function: yaml-integrity — remove only unsafe broad ignore selectors
subagent_fix_yaml_integrity() {
  local state_file="$1" report_file="$2" script_dir="$3"
  # shellcheck source=/dev/null
  source "$state_file"
  # Never reset the entire file or reinterpret prior ignore commits. That can
  # erase unrelated edits and once converted expired not-fixed rules into
  # permanent ignores. Only unsafe broad selectors have a deterministic repair;
  # other formatting findings remain unresolved and fail closed.
  if [[ -f "$REPO/.grype.yaml" ]]; then
    remove_invalid_grype_ignores "$REPO/.grype.yaml"
    if ! git -C "$REPO" diff --quiet -- .grype.yaml 2>/dev/null; then
      git -C "$REPO" add .grype.yaml
      git -C "$REPO" commit -s -m "Remove unsafe broad CVE ignores"
    fi
  fi
}

# _fix_fv_package: shared core for handling one FIX-AVAILABLE line.
# Callers own package dedup and retry policy; this function handles the fix
# attempt, exit-2/3 classification, and stale-ignore cleanup.
# Args: state_file report_dir script_dir stale_msg pkg version location cve_id [cve_id...]
_fix_fv_package() {
  local state_file="$1" report_dir="$2" script_dir="$3" stale_msg="$4"
  local pkg="$5" version="$6" location=""
  shift 6
  # Backward-compatible optional location: old direct callers put the first CVE
  # here. New callers pass an empty string or a go.mod location first.
  if [[ "${1:-}" != CVE-* && "${1:-}" != GHSA-* && "${1:-}" != GO-* ]]; then
    location="${1:-}"
    shift || true
  fi
  local cve_args=("$@")
  mapfile -t cve_args < <(printf '%s\n' "${cve_args[@]+"${cve_args[@]}"}" | awk 'NF && !seen[$0]++')
  local nr_file="$report_dir/needs-review-pkgs"
  local ff_file="$report_dir/fix-failed-pkgs"
  local timeout_file="$report_dir/timeout-pkgs"
  local -a location_flag=()
  [[ -n "$location" ]] && location_flag=(--location "$location")
  local sentinel_key="$pkg${location:+|$(normalize_scan_location "$location")}"

  echo "  Attempting fix: $pkg@$version for ${cve_args[*]}"
  local fix_rc=0
  # Prefer a caller-supplied CVE_FIX_ALL_VERSIONS (e.g. from scan-regression which
  # reads .matches[] instead of .ignoredMatches[]). Fall back to the ignored-match
  # query when not pre-set (fix-availability and existing-entries callers).
  local all_fix_versions="${CVE_FIX_ALL_VERSIONS:-}"
  local requirements_b64="${CVE_FIX_REQUIREMENTS_B64:-}" cve_json requirements_json
  local evidence_scan="${CVE_FIX_SCAN_JSON:-}"
  if [[ -z "$evidence_scan" ]]; then
    evidence_scan=$(review_scan_file "$report_dir") || return 2
  elif ! grype_scan_json_valid "$evidence_scan"; then
    echo "NEEDS_REVIEW: $pkg — invalid current scan evidence"
    return 2
  fi
  if [[ -n "$report_dir" ]] && [[ -f "$evidence_scan" ]]; then
    cve_json=$(printf '%s\n' "${cve_args[@]}" | jq -Rsc 'split("\n") | map(select(. != ""))')
    requirements_json=$(jq -c --arg pkg "$pkg" --arg location "$(normalize_scan_location "$location")" --argjson cves "$cve_json" '
      def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
      [((.ignoredMatches // []) + (.matches // []))[] |
        .vulnerability.id as $id |
        select(.artifact.name == $pkg and ($cves | index($id))) |
        select($location == "" or any(.artifact.locations[]?; (.path | normloc) == $location)) |
        {cve: .vulnerability.id, versions: (.vulnerability.fix.versions // [])}] |
      group_by(.cve) | map({cve: .[0].cve, versions: ([.[].versions[]] | unique)})' \
      "$evidence_scan" 2>/dev/null || true)
    if [[ -n "$requirements_json" && "$requirements_json" != "[]" ]]; then
      requirements_b64=$(printf '%s' "$requirements_json" | base64 | tr -d '\n')
      if [[ -z "$all_fix_versions" ]]; then
        all_fix_versions=$(jq -r '[.[].versions[]] | unique | join(",")' <<< "$requirements_json")
      fi
    fi
  fi
  local _fp_output
  _fp_output=$(CVE_FIX_ALL_VERSIONS="${all_fix_versions}" \
    CVE_FIX_REQUIREMENTS_B64="${requirements_b64}" \
    bash "$script_dir/fix-package.sh" "$state_file" "$pkg" "$version" \
      "${location_flag[@]+"${location_flag[@]}"}" "${cve_args[@]}" </dev/null 2>&1) || fix_rc=$?
  [[ -n "$_fp_output" ]] && echo "$_fp_output"

  if [[ $fix_rc -eq 2 ]]; then
    echo "  NEEDS_REVIEW: $pkg — deterministic fix reached a policy boundary"
    echo "$sentinel_key" >> "$nr_file"
    return 2
  elif [[ $fix_rc -eq 3 ]]; then
    echo "  Fix failed (exit 3): $pkg — CVE persists after update"
    echo "$sentinel_key" >> "$ff_file"
    return 3
  elif [[ $fix_rc -eq 4 ]]; then
    # Lookup failure does not establish no-fix status for any advisory.
    if [[ "$_fp_output" == *INCOMPATIBLE_MAJOR* ]]; then
      echo "  NEEDS_REVIEW: $pkg — incompatible major version bump (module path changed)"
    else
      echo "  NEEDS_REVIEW: $pkg — selected fix $version is unavailable at the current module path; verify advisory version mapping or alternative fixes"
    fi
    echo "$sentinel_key" >> "$nr_file"
    return 4
  elif [[ $fix_rc -eq 124 ]]; then
    # timeout(1) exits 124 when the child is killed by the deadline.
    # Write to timeout_file (not nr_file) so the package is NOT skipped on
    # subsequent verify_fix_loop iterations — it may succeed on retry.
    echo "  TIMEOUT: $pkg — go get timed out after ${GO_GET_TIMEOUT:-120}s (transient network error)"
    echo "$pkg" >> "$timeout_file"
    return 124
  elif [[ $fix_rc -eq 5 ]]; then
    # fix-package.sh exit 5: go get failed with a transient network/timeout
    # error — not a deterministic failure (exit 3) or a missing registry tag
    # (exit 4). Write to timeout_file so the package is retried on the next
    # verify_fix_loop iteration; do NOT write to nr_file (which permanently
    # skips the package) or ff_file (which signals a non-retryable failure).
    echo "  TRANSIENT: $pkg — go get failed with a network error (retryable)"
    echo "$pkg" >> "$timeout_file"
    return 5
  elif [[ $fix_rc -ne 0 ]]; then
    # Catch-all for unexpected exit codes to prevent silent drops.
    echo "  ERROR: $pkg — fix-package exited $fix_rc (unexpected)"
    echo "$sentinel_key" >> "$nr_file"
    return "$fix_rc"
  fi

  # Record the fix so fix-all.sh can update FIX_LINES from the parent process.
  if [[ -n "$report_dir" ]]; then
    local _used_ver
    _used_ver=$(grep "^FIXED: $pkg v" <<< "$_fp_output" 2>/dev/null | head -1 | sed "s|^FIXED: $pkg v||" | awk '{print $1}') || true
    [[ -z "$_used_ver" ]] && _used_ver="$version"
    echo "$pkg v$_used_ver for ${cve_args[*]}${location:+ at $(normalize_scan_location "$location")}" >> "$report_dir/fixed-pkgs"
  fi

  # On successful fix, remove stale ignore entries from .grype.yaml.
  if [[ -f "$REPO/.grype.yaml" ]]; then
    for cve in "${cve_args[@]}"; do
      remove_grype_ignore "$REPO/.grype.yaml" "$cve" "$pkg" "$location"
    done
    if ! git -C "$REPO" diff --quiet -- .grype.yaml 2>/dev/null; then
      git -C "$REPO" add .grype.yaml
      local abbrev
      abbrev=$(abbreviate_package "$pkg")
      if git -C "$REPO" log -1 --format="%s" | grep -qF "Bump $abbrev "; then
        git -C "$REPO" commit --amend --no-edit -s
      else
        git -C "$REPO" commit -s -m "$(printf '%s\n\n%s' \
          "Remove stale ignore for $abbrev" \
          "$stale_msg")"
      fi
      echo "  Cleaned up stale ignore entries for ${cve_args[*]}"
    fi
  fi
}

# Parse FIX-AVAILABLE lines from a report and attempt to fix each package.
# Deduplicates by package and normalized module location using a two-pass approach.
# This ensures multiple FIX-AVAILABLE lines for the same package (different CVEs
# or different fix versions) are merged rather than having the second line skipped.
# Skips packages already in nr_file or ff_file.
# Both subagent_fix_fix_availability and subagent_fix_existing_entries delegate
# here so the while-read loop and dedup logic are not copy-pasted.
# Args: report_file nr_file ff_file state_file report_dir script_dir stale_msg
_parse_and_fix_available() {
  local report_file="$1" nr_file="$2" ff_file="$3"
  local state_file="$4" report_dir="$5" script_dir="$6" stale_msg="$7"
  local line pkg version location key
  declare -A fa_pkg_ver
  declare -A fa_pkg_cves
  declare -A fa_pkg_name
  declare -A fa_pkg_location
  local fa_pkg_order=()

  # Pass 1: collect all FIX-AVAILABLE lines, accumulating CVEs and max version per package
  while IFS= read -r line; do
    [[ "$line" =~ ^FIX-AVAILABLE:\ (.+)\ (.+)\ -\>\ (.+) ]] || continue
    pkg="${BASH_REMATCH[1]}"
    version="${BASH_REMATCH[3]}"
    version="${version%% *}"
    version="${version#v}"
    location=""
    [[ "$line" =~ location:([^[:space:]]+) ]] && location=$(normalize_scan_location "${BASH_REMATCH[1]}")
    key="$pkg|$location"

    # Track insertion order (first occurrence)
    if [[ -z "${fa_pkg_ver[$key]+x}" ]]; then
      fa_pkg_order+=("$key")
      fa_pkg_name[$key]="$pkg"
      fa_pkg_location[$key]="$location"
      fa_pkg_ver[$key]="$version"
    elif version_gte "$version" "${fa_pkg_ver[$key]}"; then
      fa_pkg_ver[$key]="$version"
    fi

    # Accumulate CVE IDs (comma-separated, matching input format)
    if [[ "$line" =~ CVEs:([^[:space:]]+) ]]; then
      local new_cves="${BASH_REMATCH[1]}"
      if [[ -z "${fa_pkg_cves[$key]:-}" ]]; then
        fa_pkg_cves[$key]="$new_cves"
      else
        fa_pkg_cves[$key]="${fa_pkg_cves[$key]},${new_cves}"
      fi
    fi
  done < <(_details_section "$report_file")

  # Pass 2: dispatch one call per package with the max version and all CVE IDs
  local -a cve_args
  for key in "${fa_pkg_order[@]}"; do
    pkg="${fa_pkg_name[$key]}"
    location="${fa_pkg_location[$key]}"
    pkg_is_exempt "$pkg" "$report_dir" "$location" && continue

    cve_args=()
    if [[ -n "${fa_pkg_cves[$key]:-}" ]]; then
      IFS=',' read -ra cve_args <<< "${fa_pkg_cves[$key]}"
    fi
    [[ ${#cve_args[@]} -eq 0 ]] && cve_args=("UNKNOWN-CVE")

    _fix_fv_package "$state_file" "$report_dir" "$script_dir" \
      "$stale_msg" "$pkg" "${fa_pkg_ver[$key]}" "$location" "${cve_args[@]}" || true
  done
}

# Fix function: fix-availability — bump packages where fixes are available.
# fix-availability.sh reports per-gomod; fix-package.sh updates all gomods.
subagent_fix_fix_availability() {
  local state_file="$1" report_file="$2" script_dir="$3"
  local report_dir
  report_dir="$(dirname "$report_file")"
  # shellcheck source=/dev/null
  source "$state_file"

  # Shared tracking files — same files as subagent_fix_scan_regression so that
  # packages already classified in one fix function are skipped in the other.
  local nr_file="$report_dir/needs-review-pkgs"
  local ff_file="$report_dir/fix-failed-pkgs"

  _parse_and_fix_available "$report_file" "$nr_file" "$ff_file" "$state_file" "$report_dir" \
    "$script_dir" "Fix is now available; not-fixed entry no longer needed."
}

# Fix function: existing-entries — remove stale ignores and fix FIX-AVAILABLE packages.
# STALE: CVE no longer in grype DB — remove the dead ignore entry.
# FIX-AVAILABLE: permanent ignore had wrong rationale — bump the package and remove it.
# FIX-AVAILABLE processing is shared with subagent_fix_fix_availability via
# _parse_and_fix_available (which delegates to _fix_fv_package).
subagent_fix_existing_entries() {
  local state_file="$1" report_file="$2" script_dir="$3"
  local report_dir
  report_dir="$(dirname "$report_file")"
  # shellcheck source=/dev/null
  source "$state_file"

  # Shared tracking files with fix-availability and scan-regression.
  local nr_file="$report_dir/needs-review-pkgs"
  local ff_file="$report_dir/fix-failed-pkgs"

  # Pass 1+3 combined: single _details_section read dispatching on line prefix.
  # STALE lines commit immediately (Pass 1); FIX-NOW-AVAILABLE lines collect into
  # assoc arrays and are dispatched after the loop (Pass 3 collection phase).
  # Ordering constraint: STALE commits still land before Pass 2 fix calls.
  local _scope_re='^SCOPE-AVAILABLE:[[:space:]]([^[:space:]]+)[[:space:]]\(([^)]+)\)[[:space:]]->[[:space:]]([^[:space:]]+)[[:space:]]+fix-state:[[:space:]]([^[:space:]]+)'
  local _stale_re='^STALE:[[:space:]]([^[:space:]]+)[[:space:]]\(([^)]+)\)'
  local _fna_re='^FIX-NOW-AVAILABLE:[[:space:]]([^[:space:]]+)[[:space:]]\(([^)]+)\)[^|]*fix[[:space:]]([^[:space:]|]+)'
  local line scope_cve scope_pkg scope_loc scope_state stale_cve stale_pkg stale_loc abbrev fna_cve fna_pkg fna_ver fna_loc fna_key
  declare -A fna_pkg_cves
  declare -A fna_pkg_ver
  declare -A fna_pkg_name
  declare -A fna_pkg_loc
  local fna_pkg_order=()   # preserve discovery order

  while IFS= read -r line; do
    if [[ "$line" =~ $_scope_re ]]; then
      scope_cve="${BASH_REMATCH[1]}"
      scope_pkg="${BASH_REMATCH[2]}"
      scope_loc=$(normalize_scan_location "${BASH_REMATCH[3]}")
      scope_state="${BASH_REMATCH[4]}"
      if [[ -f "$REPO/.grype.yaml" ]] &&
         migrate_grype_ignore_scope "$REPO/.grype.yaml" "$scope_cve" "$scope_pkg" "$scope_loc" "$scope_state"; then
        if ! git -C "$REPO" diff --quiet -- .grype.yaml 2>/dev/null; then
          git -C "$REPO" add .grype.yaml
          abbrev=$(abbreviate_package "$scope_pkg")
          git -C "$REPO" commit -s -m "Scope $abbrev CVE ignore to module"
          echo "  Scoped ignore: $scope_cve ($scope_pkg) -> $scope_loc"
        fi
      else
        echo "  WARNING: could not safely scope $scope_cve ($scope_pkg) -> $scope_loc"
      fi
    elif [[ "$line" =~ $_stale_re ]]; then
      stale_cve="${BASH_REMATCH[1]}" stale_pkg="${BASH_REMATCH[2]}"
      stale_loc=""
      [[ "$line" =~ location:([^[:space:]]+) ]] && stale_loc=$(normalize_scan_location "${BASH_REMATCH[1]}")
      pkg_is_exempt "$stale_pkg" "$report_dir" "$stale_loc" && continue
      if [[ -f "$REPO/.grype.yaml" ]] && \
         grep -qE "vulnerability:[[:space:]]*${stale_cve//./\\.}[[:space:]]*$" "$REPO/.grype.yaml" 2>/dev/null; then
        remove_grype_ignore "$REPO/.grype.yaml" "$stale_cve" "$stale_pkg" "$stale_loc"
        if ! git -C "$REPO" diff --quiet -- .grype.yaml 2>/dev/null; then
          git -C "$REPO" add .grype.yaml
          abbrev=$(abbreviate_package "$stale_pkg")
          git -C "$REPO" commit -s -m "$(printf '%s\n\n%s' \
            "Remove stale $stale_cve $abbrev ignore" \
            "grype no longer reports $stale_cve for $stale_pkg.")"
          echo "  Removed stale ignore: $stale_cve ($stale_pkg)"
        fi
      fi
    elif [[ "$line" =~ $_fna_re ]]; then
      fna_cve="${BASH_REMATCH[1]}"
      fna_pkg="${BASH_REMATCH[2]}"
      fna_ver="${BASH_REMATCH[3]#v}"
      fna_loc=""
      [[ "$line" =~ location:([^[:space:]]+) ]] && fna_loc=$(normalize_scan_location "${BASH_REMATCH[1]}")
      fna_key="$fna_pkg|$fna_loc"
      if [[ -z "${fna_pkg_cves[$fna_key]+x}" ]]; then
        fna_pkg_order+=("$fna_key")
        fna_pkg_name[$fna_key]="$fna_pkg"
        fna_pkg_loc[$fna_key]="$fna_loc"
      fi
      fna_pkg_cves[$fna_key]+="${fna_pkg_cves[$fna_key]:+ }$fna_cve"
      if [[ -z "${fna_pkg_ver[$fna_key]:-}" ]] || version_gte "$fna_ver" "${fna_pkg_ver[$fna_key]}"; then
        fna_pkg_ver[$fna_key]="$fna_ver"
      fi
    fi
  done < <(_details_section "$report_file")

  # Pass 2: fix FIX-AVAILABLE packages (permanent ignore was wrong — a real fix exists).
  _parse_and_fix_available "$report_file" "$nr_file" "$ff_file" "$state_file" "$report_dir" \
    "$script_dir" "Fix is now available; permanent ignore was incorrect."

  # FNA dispatch: process each package once with all its CVEs and the highest fix version
  local -a fna_cve_args
  for fna_key in "${fna_pkg_order[@]}"; do
    fna_pkg="${fna_pkg_name[$fna_key]}"
    pkg_is_exempt "$fna_pkg" "$report_dir" "${fna_pkg_loc[$fna_key]}" && continue
    read -ra fna_cve_args <<< "${fna_pkg_cves[$fna_key]}"
    _fix_fv_package "$state_file" "$report_dir" "$script_dir" \
      "Fix is now available; not-fixed entry no longer needed." \
      "$fna_pkg" "${fna_pkg_ver[$fna_key]}" "${fna_pkg_loc[$fna_key]}" "${fna_cve_args[@]}" || true
  done
}

# Fix function: scan-regression — fix NEW and UNRESOLVED CVEs
# Groups all CVEs by package first so that fix-package.sh/ignore.sh receive
# every CVE ID in a single call. Without grouping, the dedup logic would
# pass only the first CVE per package and skip the rest, requiring extra
# verify_fix_loop iterations (one CVE per iteration per package).
subagent_fix_scan_regression() {
  local state_file="$1" report_file="$2" script_dir="$3"
  local report_dir
  report_dir="$(dirname "$report_file")"
  # shellcheck source=/dev/null
  source "$state_file"
  # Validate before dispatching either dependency updates or no-fix ignores.
  local _current_scan
  _current_scan=$(review_scan_file "$report_dir") || return 2

  # Retry dispatch needs the same proven binary ownership as initial dispatch.
  # Keep the authoritative scan/report untouched, and use a separate mapped
  # copy for module-scoped fix requirements. Unproven paths stay fail-closed.
  local _binary_locations='{}' _dispatch_scan=''
  if [[ -f "$_current_scan" && -f "$script_dir/binary-module-locations.py" && -f "${state_file}.generated-artifacts" ]]; then
    _binary_locations=$(python3 "$script_dir/binary-module-locations.py" "$REPO" \
      "${state_file}.generated-artifacts" --location-map < "$_current_scan") || return 2
    _dispatch_scan=$(mktemp "${TMPDIR:-/tmp}/cve-fix-dispatch.XXXXXX")
    if ! python3 "$script_dir/binary-module-locations.py" "$REPO" \
      "${state_file}.generated-artifacts" < "$_current_scan" > "$_dispatch_scan"; then
      rm -f "$_dispatch_scan"
      return 2
    fi
    _current_scan="$_dispatch_scan"
  fi

  # Packages that fix-package.sh returned exit 2 for (a builder, Kubernetes,
  # module-scope, or common-fix-stream policy boundary). Retained for the final
  # summary. Retry any NEW/UNRESOLVED evidence still dispatched here: a prior
  # policy decision must never exempt a newly introduced vulnerability.
  local nr_file="$report_dir/needs-review-pkgs"
  # Packages that fix-package.sh returned exit 3 for (CVE persists after update —
  # likely a missed replace directive). Retain the classification while retrying
  # within verify_fix_loop's bounded iteration count.
  # Group CVEs by package: collect all CVEs and fix versions per package.
  # Both fix-package.sh and ignore.sh accept multiple CVE IDs.
  declare -A pkg_fix_cves
  declare -A pkg_nofix_cves
  declare -A pkg_fix_ver
  declare -A pkg_severity
  declare -A pkg_names
  declare -A pkg_locations
  local pkg_order=()         # preserve discovery order

  while IFS= read -r line; do
    # Parse: NEW: CVE-ID (pkg version severity fix_ver)
    # or: UNRESOLVED: CVE-ID (pkg version severity fix_ver)
    local re='^(NEW|UNRESOLVED): ([^ ]+) \(([^ ]+) ([^ ]+) ([^ ]+) ([^)]+)\)'
    [[ "$line" =~ $re ]] || continue
    local cve="${BASH_REMATCH[2]}" pkg="${BASH_REMATCH[3]}" fix_ver="${BASH_REMATCH[6]}"
    local severity="${BASH_REMATCH[5]}"
    local location="" key
    [[ "$line" =~ location:([^[:space:]]+) ]] && location=$(normalize_scan_location "${BASH_REMATCH[1]}")
    if [[ "$pkg" != stdlib && -n "$location" ]]; then
      local _binary_scope
      _binary_scope=$(jq -r --arg location "$location" '.[$location] // empty' <<< "$_binary_locations")
      [[ -z "$_binary_scope" ]] || location="$_binary_scope"
    fi
    key="$pkg|$location"

    # Track package order (first occurrence)
    if [[ -z "${pkg_fix_cves[$key]+x}" ]] && [[ -z "${pkg_nofix_cves[$key]+x}" ]]; then
      pkg_order+=("$key")
      pkg_names[$key]="$pkg"
      pkg_locations[$key]="$location"
    fi

    pkg_severity[$key]="$severity"

    if [[ "$fix_ver" != "no-fix" ]]; then
      fix_ver="${fix_ver#v}"
      pkg_fix_cves[$key]+="${pkg_fix_cves[$key]:+ }$cve"
      # Track highest fix version
      if [[ -z "${pkg_fix_ver[$key]:-}" ]] || version_gte "$fix_ver" "${pkg_fix_ver[$key]}"; then
        pkg_fix_ver[$key]="$fix_ver"
      fi
    else
      pkg_nofix_cves[$key]+="${pkg_nofix_cves[$key]:+ }$cve"
    fi
  done < <(_details_section "$report_file")

  # Process each package once with all its CVEs
  local pkg
  local key location sentinel_key
  for key in "${pkg_order[@]}"; do
    pkg="${pkg_names[$key]}"
    location="${pkg_locations[$key]}"
    sentinel_key="$pkg${location:+|$location}"
    local -a loc_flag=()
    [[ -n "$location" ]] && loc_flag=(--location "$location")
    # Handle fixable CVEs via _fix_fv_package (shared with fix-availability and
    # existing-entries). Use the current scan evidence, because remediation can
    # expose a fix threshold that was absent from the initial scan. Fall back to
    # the initial scan only for direct callers that predate final-scan.json.
    if [[ -n "${pkg_fix_cves[$key]:-}" ]]; then
      local -a cve_arr
      read -ra cve_arr <<< "${pkg_fix_cves[$key]}"
      local ver="${pkg_fix_ver[$key]}"
      # Look up all fix versions from the current scan JSON so fix-package.sh can
      # perform in-stream version selection (e.g. etcd 3.6.14 instead of 3.7.1
      # when the installed version is in the 3.6.x stream and 3.7.1 would require
      # a Go minor-version bump). Without this, fix-package.sh only sees the
      # highest version and may flag a fixable package as NEEDS_REVIEW.
      local all_fix_vers=""
      if [[ -f "$_current_scan" ]]; then
        all_fix_vers=$(jq -r --arg pkg "$pkg" \
          '[.matches[] | select(.artifact.name == $pkg) | (.vulnerability.fix.versions // [])[]] | map(select(type == "string" and . != "")) | unique | join(",")' \
          "$_current_scan" 2>/dev/null || true)
      fi
      local CVE_FIX_ALL_VERSIONS="$all_fix_vers"
      local CVE_FIX_SCAN_JSON="$_current_scan"
      _fix_fv_package "$state_file" "$report_dir" "$script_dir" \
        "Regression from dependency update; not-fixed entry no longer needed." \
        "$pkg" "$ver" "$location" "${cve_arr[@]}" || true
    fi

    # Handle no-fix CVEs
    if [[ -n "${pkg_nofix_cves[$key]:-}" ]]; then
      local -a cve_arr
      read -ra cve_arr <<< "${pkg_nofix_cves[$key]}"
      local severity="${pkg_severity[$key]}"
      # Preserve Grype's actual state: OSV can also report "unknown". A rule
      # using not-fixed will not suppress an unknown finding, and must not
      # replace an existing correctly scoped unknown rule.
      local fix_state="not-fixed"
      local _nofix_ids _nofix_states=''
      _nofix_ids=$(printf '%s\n' "${cve_arr[@]}" | jq -Rsc 'split("\n") | map(select(. != ""))')
      if [[ -f "$_current_scan" ]]; then
        _nofix_states=$(jq -r --arg pkg "$pkg" --arg location "$location" --argjson cves "$_nofix_ids" '
          def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
          [.matches[] | .vulnerability.id as $id |
            select(.artifact.name == $pkg and ($cves | index($id))) |
            select($location == "" or any(.artifact.locations[]?; (.path | normloc) == $location)) |
            (.vulnerability.fix.state | if . == null or . == "" then "unknown" else . end)] |
          unique | .[]' "$_current_scan")
      fi
      [[ -z "$_nofix_states" ]] || fix_state="$_nofix_states"
      case "$fix_state" in
        not-fixed|wont-fix|unknown) ;;
        *)
          echo "  NEEDS_REVIEW: $pkg — ambiguous no-fix states in current scan"
          echo "$sentinel_key" >> "$nr_file"
          continue
          ;;
      esac
      echo "  Ignoring unfixable: $pkg (${cve_arr[*]})"
      local _ignore_rc=0
      bash "$script_dir/ignore.sh" "$state_file" "$pkg" "${severity:-High}" \
        "Regression from dependency update (no fix available)" --fix-state "$fix_state" \
        "${loc_flag[@]+"${loc_flag[@]}"}" "${cve_arr[@]}" </dev/null || _ignore_rc=$?
      if [[ $_ignore_rc -eq 0 ]]; then
        echo "$sentinel_key" >> "$nr_file"
        echo "$pkg (no fix available) for ${cve_arr[*]}" >> "$report_dir/ignored-pkgs"
      fi
    fi
  done
  [[ -z "$_dispatch_scan" ]] || rm -f "$_dispatch_scan"
}
