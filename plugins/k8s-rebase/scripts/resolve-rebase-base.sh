#!/bin/bash
# Print the immutable starting commit for a rebase, or fail without guessing.
# Usage: resolve-rebase-base.sh <repo> [tip]
# A recorded .rebase-tmp/base-commit takes precedence over moving branch refs.
set -euo pipefail

fail() { echo "ERROR: Cannot resolve rebase baseline: $*" >&2; exit 1; }

[[ $# -ge 1 && $# -le 2 ]] || fail "usage: $0 <repo> [tip]"
repo=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || fail "not a Git worktree: $1"
tip=$(git -C "$repo" rev-parse --verify --end-of-options "${2:-HEAD}^{commit}" 2>/dev/null) \
  || fail "tip '${2:-HEAD}' is not a commit"
record="$repo/.rebase-tmp/base-commit"

if [[ -e "$record" || -L "$record" ]]; then
  [[ -f "$record" ]] || fail "$record is not a regular file"
  base=$(cat "$record") || fail "cannot read $record"
  [[ "$base" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] \
    || fail "$record must contain one full commit SHA"
  resolved=$(git -C "$repo" rev-parse --verify --end-of-options "$base^{commit}" 2>/dev/null) \
    || fail "recorded commit $base is unavailable"
  [[ "$resolved" == "$base" ]] || fail "$record does not identify a commit directly"
  git -C "$repo" merge-base --is-ancestor "$base" "$tip" \
    || fail "recorded commit $base is not an ancestor of $tip; preserve the record and resolve the checkout conflict"
  printf '%s\n' "$base"
  exit 0
fi

# Support repositories whose default branch is release-X.Y, and clones whose
# default remote is not origin. Ref names are hints only; emit a commit SHA.
refs=()
upstream=$(git -C "$repo" rev-parse --symbolic-full-name '@{upstream}' 2>/dev/null || true)
branch=$(git -C "$repo" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
remote=""
[[ -z "$branch" ]] || remote=$(git -C "$repo" config --get "branch.$branch.remote" || true)
if [[ -n "$upstream" ]]; then
  default_ref=$(git -C "$repo" symbolic-ref --quiet "refs/remotes/${remote:-origin}/HEAD" 2>/dev/null || true)
  if [[ "$upstream" == "refs/remotes/$remote/$branch" && "$upstream" != "$default_ref" ]]; then
    fail "tracking this non-default branch does not identify its starting commit; record the verified baseline in $record"
  fi
  refs+=("$upstream")
fi
if [[ -n "$remote" && "$remote" != . && "$remote" != origin ]]; then
  refs+=("refs/remotes/$remote/HEAD")
fi
refs+=(refs/remotes/origin/HEAD)
refs+=(refs/heads/master refs/heads/main refs/remotes/origin/master refs/remotes/origin/main)
for ref in "${refs[@]}"; do
  git -C "$repo" rev-parse --verify --end-of-options "$ref^{commit}" >/dev/null 2>&1 || continue
  if base=$(git -C "$repo" merge-base "$tip" "$ref" 2>/dev/null); then
    printf '%s\n' "$base"
    exit 0
  fi
done

fail "no recorded baseline or usable default/tracking branch for $tip; record the verified starting commit in $record"
