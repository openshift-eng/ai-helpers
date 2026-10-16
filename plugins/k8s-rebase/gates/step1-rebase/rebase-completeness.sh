#!/bin/bash
# Gate companion: rebase-completeness — deterministic step-1 completion evidence.
# Checks 1, 2, and 5 are fully deterministic (counts). Checks 3 and 4 emit raw
# data (commit log, dep lines) for the subagent to apply exception logic.
# Usage: bash rebase-completeness.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()

# Check 1: step1-result.txt
result_file="$REPO/.rebase-tmp/step1-result.txt"
result_val="MISSING"
if [[ -f "$result_file" ]]; then
  result_val=$(tr -d '[:space:]' < "$result_file")
  details+=("CHECK1_RESULT_FILE: $result_val")
  # Valid tokens: EXIT2 (deps bumped) or EXIT0 (already at target).
  # Any other content means the script exited abnormally.
  [[ "$result_val" != "EXIT2" && "$result_val" != "EXIT0" ]] && inc NEW_ISSUES
else
  details+=("CHECK1_RESULT_FILE: MISSING")
  inc NEW_ISSUES
fi

# Check 2: modified-or-staged uncommitted go.mod / vendor / generated files.
# Uses git status --short (not diff --cached) to catch both staged and unstaged
# modifications — go mod tidy may update files on disk without staging them.
uncommitted_count=0
while IFS= read -r f; do
  details+=("CHECK2_UNCOMMITTED: $f")
  inc uncommitted_count
done < <(git status --short 2>/dev/null \
  | grep -v '^??' | awk '{print $NF}' \
  | grep -E 'go\.mod$|go\.sum$|^vendor/|\.go$' || true)
details+=("CHECK2_UNCOMMITTED_COUNT: $uncommitted_count")
[[ "$uncommitted_count" -gt 0 ]] && inc NEW_ISSUES

# Check 3: commit log above BASE for subagent to count missing commit types
if [[ -n "$BASE" ]]; then
  commit_count=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    details+=("CHECK3_LOG: $line")
    inc commit_count
  done < <(git log --oneline "$BASE"..HEAD 2>/dev/null || true)
  details+=("CHECK3_COMMITS_ABOVE_BASE: $commit_count")

  # Number of non-vendor go.mod files with k8s.io/* deps (min expected rebase commits)
  gomod_with_k8s=0
  while IFS= read -r gm; do
    grep -q 'k8s\.io/' "$gm" 2>/dev/null && inc gomod_with_k8s || true
  done < <(find "$REPO" -name 'go.mod' -not -path '*/vendor/*' \
    -not -path "$REPO/.claude/*" 2>/dev/null)
  details+=("CHECK3_GOMOD_WITH_K8S_DEPS: $gomod_with_k8s")

  # Codegen exception inputs
  if [[ -f "$REPO/.rebase-tmp/codegen.log" ]]; then
    details+=("CHECK3_CODEGEN_LOG: EXISTS")
  else
    details+=("CHECK3_CODEGEN_LOG: MISSING")
  fi
  if [[ -f "$REPO/.rebase-tmp/summary.txt" ]]; then
    if grep -q '## CODEGEN FAILURE' "$REPO/.rebase-tmp/summary.txt" 2>/dev/null; then
      details+=("CHECK3_CODEGEN_FAILURE_IN_SUMMARY: YES")
    else
      details+=("CHECK3_CODEGEN_FAILURE_IN_SUMMARY: NO")
    fi
  else
    details+=("CHECK3_CODEGEN_FAILURE_IN_SUMMARY: SUMMARY_MISSING")
  fi
else
  details+=("CHECK3_COMMITS_ABOVE_BASE: NO_BASE")
fi

# Check 4: all k8s.io/* dep lines from non-vendor go.mod files
# Subagent applies replace/indirect exception logic.
while IFS= read -r gm; do
  rel="${gm#"$REPO/"}"
  while IFS= read -r dep; do
    details+=("CHECK4_DEP: $rel: $dep")
  done < <(grep -E '\bk8s\.io/' "$gm" 2>/dev/null \
    | grep -v 'sigs\.k8s\.io/' || true)
done < <(find "$REPO" -name 'go.mod' -not -path '*/vendor/*' \
  -not -path "$REPO/.claude/*" 2>/dev/null | LC_ALL=C sort)

# Check 5: conflict markers in non-vendor source files
conflict_count=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  details+=("CHECK5_CONFLICT: $line")
  inc conflict_count
done < <(grep -rnE '<<<<<<<|>>>>>>>' \
  --include='*.go' --include='*.yaml' --include='*.json' \
  "$REPO" 2>/dev/null | grep -v '/vendor/' | grep -v '/.claude/' || true)
details+=("CHECK5_CONFLICT_COUNT: $conflict_count")
[[ "$conflict_count" -gt 0 ]] && inc NEW_ISSUES

details+=("NEW_ISSUES=$NEW_ISSUES")
finish_evidence \
  "result=${result_val:-MISSING} uncommitted=$uncommitted_count conflicts=$conflict_count" \
  "${details[@]}"
