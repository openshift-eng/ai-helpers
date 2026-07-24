#!/bin/bash
set -euo pipefail

# run-solve.sh — eval runner for the 3-phase solve pipeline
#
# Runs: solve → code-review → address-review against a snapshot branch.
# Each phase invokes the skill directly, matching the CI pipeline in
# openshift/release jira-agent-process-commands.sh.
#
# Produces output files for agent-eval-harness judges to evaluate.
# Does NOT push or create PRs.
#
# Called by the eval harness via runner.type: cli. The harness sets cwd to
# the case workspace which contains input.yaml and a pre-created output/ dir.
#
# Usage:
#   run-solve.sh <issue_key> <repo_url> <eval_branch> [model]
#
# Env vars:
#   AI_HELPERS_DIR  — path to ai-helpers checkout (default: auto-detect)

ISSUE_KEY=${1:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
REPO_URL=${2:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
EVAL_BRANCH=${3:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
SKILL_MODEL=${4:-claude-opus-4-6}
AI_HELPERS_DIR=${AI_HELPERS_DIR:-$(cd "$(dirname "$0")/../../../.." && pwd)}

# The harness pre-creates output/ in the workspace (cwd)
WORKSPACE="$(pwd)"
OUTPUT_DIR="${WORKSPACE}/output"
REPO_DIR="${EVAL_REPO_DIR:-$(mktemp -d "${HOME}/.cache/eval-solve.XXXXXX")/repo}"

OPENSHIFT_DEV_PLUGIN="$AI_HELPERS_DIR/plugins/openshift-developer"
CODE_REVIEW_PLUGIN="$AI_HELPERS_DIR/plugins/code-review"

echo "=== Solve Eval: $ISSUE_KEY ==="
echo "Repo: $REPO_URL"
echo "Branch: $EVAL_BRANCH"
echo "Model: $SKILL_MODEL"
echo "Workspace: $WORKSPACE"
echo "ai-helpers: $AI_HELPERS_DIR"

# Validate plugins
if [ ! -f "$OPENSHIFT_DEV_PLUGIN/skills/solve/SKILL.md" ]; then
  echo "ERROR: solve SKILL.md not found at $OPENSHIFT_DEV_PLUGIN/skills/solve/SKILL.md" >&2
  exit 1
fi
if [ ! -d "$CODE_REVIEW_PLUGIN/.claude-plugin" ]; then
  echo "ERROR: code-review plugin not found at $CODE_REVIEW_PLUGIN" >&2
  exit 1
fi

# Helper: extract token/cost JSON from stream-json output
extract_tokens() {
  local file=$1
  grep '"type":"result"' "$file" 2>/dev/null \
    | head -1 \
    | jq '{
        total_cost_usd: (.total_cost_usd // 0),
        duration_ms: (.duration_ms // 0),
        num_turns: (.num_turns // 0),
        input_tokens: (.usage.input_tokens // 0),
        output_tokens: (.usage.output_tokens // 0),
        cache_read_input_tokens: (.usage.cache_read_input_tokens // 0),
        cache_creation_input_tokens: (.usage.cache_creation_input_tokens // 0),
        model: ((.modelUsage // {} | keys | first) // "unknown")
      }' 2>/dev/null \
    || echo '{"total_cost_usd":0,"duration_ms":0,"num_turns":0,"input_tokens":0,"output_tokens":0,"model":"unknown"}'
}

# Helper: extract assistant text from stream-json
extract_text() {
  local file=$1
  jq -j 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text // empty' "$file" 2>/dev/null || true
}

# ── Verify tool dependencies ──
export PATH="${GOPATH:-$HOME/go}/bin:$HOME/.local/bin:$PATH"
for cmd in gopls cov-diff; do
  command -v "$cmd" >/dev/null 2>&1 || echo "WARNING: $cmd not found — install before running eval"
done

# ── Setup: clone repo and prepare workspace ──
echo ""
echo "--- Setup ---"
rm -rf "$REPO_DIR"
git clone "$REPO_URL" "$REPO_DIR"
cd "$REPO_DIR"
git checkout "$EVAL_BRANCH"
BASE_SHA=$(git rev-parse HEAD)

git config user.name "Eval Runner"
git config user.email "eval@test.local"

NO_PUSH_CONTEXT="IMPORTANT: Do NOT create a Pull Request. Do NOT push to any remote. Just implement the changes, run tests, and commit to the local branch."

# ── Phase 1: Solve ──
echo ""
echo "=========================================="
echo "Phase 1: Solve ($ISSUE_KEY)"
echo "=========================================="

PHASE1_START=$(date +%s)

set +e
claude -p "/openshift-developer:solve ${ISSUE_KEY} origin --ci" \
  --plugin-dir "$OPENSHIFT_DEV_PLUGIN" \
  --allowedTools "Bash Read Write Edit Grep Glob WebFetch Agent Skill Task" \
  --max-turns 300 \
  --effort max \
  --model "$SKILL_MODEL" \
  --output-format stream-json \
  --verbose \
  --append-system-prompt "$NO_PUSH_CONTEXT" \
  2>"$OUTPUT_DIR/phase1-stderr.log" \
  | tee "$OUTPUT_DIR/phase1-output.json"
PHASE1_EXIT=$?
set -e

PHASE1_END=$(date +%s)
echo "Phase 1 duration: $((PHASE1_END - PHASE1_START))s (exit $PHASE1_EXIT)"

{ git diff "$BASE_SHA"..HEAD 2>/dev/null; git diff HEAD 2>/dev/null; } > "$OUTPUT_DIR/phase1-diff.patch" || true
{ git diff "$BASE_SHA"..HEAD --stat 2>/dev/null; git diff HEAD --stat 2>/dev/null; } > "$OUTPUT_DIR/phase1-diffstat.txt" || true
extract_tokens "$OUTPUT_DIR/phase1-output.json" > "$OUTPUT_DIR/phase1-tokens.json"
extract_text "$OUTPUT_DIR/phase1-output.json" > "$OUTPUT_DIR/phase1-text.txt"

CHANGED_FILES=$( { git diff "$BASE_SHA"..HEAD --name-only 2>/dev/null; git diff HEAD --name-only 2>/dev/null; } | sort -u || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo "No code changes produced by Phase 1"
  touch "$OUTPUT_DIR/diff.patch" "$OUTPUT_DIR/files-changed.txt" "$OUTPUT_DIR/commit-log.txt"
  touch "$OUTPUT_DIR/review-findings.txt" "$OUTPUT_DIR/coverage.txt"
  echo "1" > "$OUTPUT_DIR/make-test-exit"
  echo "No code changes — make test not run" > "$OUTPUT_DIR/make-test.log"
  echo "1" > "$OUTPUT_DIR/make-verify-exit"
  echo "No code changes — make verify not run" > "$OUTPUT_DIR/make-verify.log"
  echo '{"total_cost_usd":0}' > "$OUTPUT_DIR/phase2-tokens.json"
  echo '{"total_cost_usd":0}' > "$OUTPUT_DIR/phase3-tokens.json"
  jq -s '{total_cost_usd: (map(.total_cost_usd // 0) | add), phases: length}' \
    "$OUTPUT_DIR"/phase*-tokens.json > "$OUTPUT_DIR/total-cost.json" 2>/dev/null || true
  echo "=== Pipeline complete (no changes) ==="
  exit 0
fi

echo "Changed files:"
echo "$CHANGED_FILES" | sed 's/^/  /'

# ── Phase 2: Code Review ──
echo ""
echo "=========================================="
echo "Phase 2: Code Review"
echo "=========================================="

PHASE2_START=$(date +%s)

set +e
claude -p "/code-review:pre-commit-review --language go --profile hypershift" \
  --plugin-dir "$CODE_REVIEW_PLUGIN" \
  --allowedTools "Bash Read Grep Glob Task Agent Skill" \
  --max-turns 225 \
  --effort max \
  --model "$SKILL_MODEL" \
  --output-format stream-json \
  --verbose \
  2>"$OUTPUT_DIR/phase2-stderr.log" \
  | tee "$OUTPUT_DIR/phase2-output.json"
PHASE2_EXIT=$?
set -e

PHASE2_END=$(date +%s)
echo "Phase 2 duration: $((PHASE2_END - PHASE2_START))s (exit $PHASE2_EXIT)"

extract_text "$OUTPUT_DIR/phase2-output.json" > "$OUTPUT_DIR/review-findings.txt"
extract_tokens "$OUTPUT_DIR/phase2-output.json" > "$OUTPUT_DIR/phase2-tokens.json"

# ── Phase 3: Address Review Findings ──
echo ""
echo "=========================================="
echo "Phase 3: Address Review Findings"
echo "=========================================="

REVIEW_FINDINGS=$(cat "$OUTPUT_DIR/review-findings.txt" 2>/dev/null || echo "")

PHASE3_START=$(date +%s)

if [ -n "$REVIEW_FINDINGS" ]; then
  set +e
  claude -p "/openshift-developer:address-review-precommit" \
    --plugin-dir "$OPENSHIFT_DEV_PLUGIN" \
    --allowedTools "Bash Read Write Edit Grep Glob Agent Skill Task" \
    --max-turns 225 \
    --effort max \
    --model "$SKILL_MODEL" \
    --output-format stream-json \
    --verbose \
    --append-system-prompt "REVIEW FINDINGS:
${REVIEW_FINDINGS}

${NO_PUSH_CONTEXT}" \
    2>"$OUTPUT_DIR/phase3-stderr.log" \
    | tee "$OUTPUT_DIR/phase3-output.json"
  PHASE3_EXIT=$?
  set -e
else
  echo "No review findings to address, skipping Phase 3"
  echo '{}' > "$OUTPUT_DIR/phase3-output.json"
  PHASE3_EXIT=0
fi

PHASE3_END=$(date +%s)
echo "Phase 3 duration: $((PHASE3_END - PHASE3_START))s (exit $PHASE3_EXIT)"
extract_tokens "$OUTPUT_DIR/phase3-output.json" > "$OUTPUT_DIR/phase3-tokens.json"

# ── Capture final outputs ──
echo ""
echo "=========================================="
echo "Final Output Capture"
echo "=========================================="

{ git diff "$BASE_SHA"..HEAD 2>/dev/null; git diff HEAD 2>/dev/null; } > "$OUTPUT_DIR/diff.patch"
{ git diff "$BASE_SHA"..HEAD --name-only 2>/dev/null; git diff HEAD --name-only 2>/dev/null; } | sort -u > "$OUTPUT_DIR/files-changed.txt"
git log --oneline "$BASE_SHA"..HEAD > "$OUTPUT_DIR/commit-log.txt"

echo "Final diff: $(wc -l < "$OUTPUT_DIR/diff.patch") lines"
echo "Files changed: $(wc -l < "$OUTPUT_DIR/files-changed.txt")"
echo "Commits: $(wc -l < "$OUTPUT_DIR/commit-log.txt")"

# Clean up skill workspace artifacts
rm -rf .work/ 2>/dev/null || true
git checkout -- .work/ 2>/dev/null || true
git clean -fd .work/ 2>/dev/null || true

# Run make test and make verify independently
echo ""
echo "Running make test..."
set +e
make test 2>&1 | tee "$OUTPUT_DIR/make-test.log"
echo $? > "$OUTPUT_DIR/make-test-exit"
echo "make test exit: $(cat "$OUTPUT_DIR/make-test-exit")"

echo "Running make verify..."
make verify 2>&1 | tee "$OUTPUT_DIR/make-verify.log"
echo $? > "$OUTPUT_DIR/make-verify-exit"
echo "make verify exit: $(cat "$OUTPUT_DIR/make-verify-exit")"
set -e

# Diff coverage
CHANGED_PKGS=$( { git diff "$BASE_SHA"..HEAD --name-only -- '*.go' 2>/dev/null; git diff HEAD --name-only -- '*.go' 2>/dev/null; } \
  | grep -v '_test.go$' \
  | xargs -I{} dirname {} 2>/dev/null \
  | sort -u \
  | sed 's|^|./|' || echo "")
if [ -n "$CHANGED_PKGS" ]; then
  echo "Running diff coverage for changed packages..."
  set +e
  go test -coverprofile="$OUTPUT_DIR/cover.out" $CHANGED_PKGS 2>&1 | tee "$OUTPUT_DIR/coverage-raw.txt"
  if command -v cov-diff >/dev/null 2>&1 && [ -f "$OUTPUT_DIR/cover.out" ]; then
    git diff "$BASE_SHA"..HEAD > "$OUTPUT_DIR/pr.diff"
    GO_MODULE=$(grep "^module " go.mod | awk '{print $2}')
    DIFF_COV=$(cov-diff -coverprofile "$OUTPUT_DIR/cover.out" -diff "$OUTPUT_DIR/pr.diff" -path . -module "$GO_MODULE" 2>/dev/null | sed -n 's/.*: \([0-9]*\)%.*/\1/p' || echo "")
    if [ -n "$DIFF_COV" ]; then
      echo "diff-coverage: ${DIFF_COV}% of changed lines covered" > "$OUTPUT_DIR/coverage.txt"
    else
      echo "diff-coverage: could not compute" > "$OUTPUT_DIR/coverage.txt"
      cat "$OUTPUT_DIR/coverage-raw.txt" >> "$OUTPUT_DIR/coverage.txt"
    fi
  else
    cp "$OUTPUT_DIR/coverage-raw.txt" "$OUTPUT_DIR/coverage.txt"
  fi
  set -e
else
  echo "no go source files changed" > "$OUTPUT_DIR/coverage.txt"
fi

# Aggregate cost across all phases
jq -s '{
  total_cost_usd: (map(.total_cost_usd // 0) | add),
  total_duration_ms: (map(.duration_ms // 0) | add),
  total_turns: (map(.num_turns // 0) | add),
  total_input_tokens: (map(.input_tokens // 0) | add),
  total_output_tokens: (map(.output_tokens // 0) | add),
  phases: length
}' "$OUTPUT_DIR"/phase*-tokens.json > "$OUTPUT_DIR/total-cost.json" 2>/dev/null \
  || echo '{"total_cost_usd":0,"phases":0}' > "$OUTPUT_DIR/total-cost.json"

# Write metrics.json for the eval harness (CLI runner contract)
jq '{
  token_usage: {input: .total_input_tokens, output: .total_output_tokens},
  cost_usd: .total_cost_usd,
  num_turns: .total_turns,
  model: "'"$SKILL_MODEL"'"
}' "$OUTPUT_DIR/total-cost.json" > "$OUTPUT_DIR/metrics.json" 2>/dev/null \
  || echo '{"cost_usd":0,"num_turns":0}' > "$OUTPUT_DIR/metrics.json"

# Fetch known-good PR diff for judge comparison
KNOWN_PR=$(grep 'known_good_pr' "${WORKSPACE}/input.yaml" 2>/dev/null | sed 's/.*: *//' | tr -d '"' || echo "")
if [ -n "$KNOWN_PR" ]; then
  echo "Fetching known-good PR diff: $KNOWN_PR"
  PR_NUM=$(echo "$KNOWN_PR" | grep -oE '[0-9]+$')
  PR_REPO=$(echo "$KNOWN_PR" | sed 's|https://github.com/||;s|/pull/.*||')
  set +e
  gh pr diff "$PR_NUM" --repo "$PR_REPO" > "$OUTPUT_DIR/known-good.patch" 2>/dev/null
  set -e
  if [ -s "$OUTPUT_DIR/known-good.patch" ]; then
    echo "Known-good PR diff: $(wc -l < "$OUTPUT_DIR/known-good.patch") lines"
  else
    echo "Could not fetch known-good PR diff"
    rm -f "$OUTPUT_DIR/known-good.patch"
  fi
fi

# Remove large stream-json files that would blow up {{ outputs }}
rm -f "$OUTPUT_DIR"/phase*-output.json "$OUTPUT_DIR"/phase*-stderr.log
rm -f "$OUTPUT_DIR/cover.out" "$OUTPUT_DIR/pr.diff" "$OUTPUT_DIR/coverage-raw.txt"

echo ""
echo "=== Pipeline complete ==="
echo "Cost: $(jq -r '.total_cost_usd' "$OUTPUT_DIR/total-cost.json") USD"
