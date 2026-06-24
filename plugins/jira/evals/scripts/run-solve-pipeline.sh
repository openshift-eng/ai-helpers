#!/bin/bash
set -euo pipefail

# run-solve-pipeline.sh — eval runner for the jira-agent 3-phase pipeline
#
# Runs: solve → code-review → address-review against a snapshot branch.
# Produces output files for agent-eval-harness judges to evaluate.
# Does NOT push or create PRs.
#
# Usage:
#   run-solve-pipeline.sh <issue_key> <repo_url> <eval_branch> [model]
#
# Env vars:
#   AI_HELPERS_DIR  — path to ai-helpers checkout (default: auto-detect)
#   WORK_DIR        — output directory (default: mktemp)

ISSUE_KEY=${1:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
REPO_URL=${2:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
EVAL_BRANCH=${3:?"Usage: $0 <issue_key> <repo_url> <eval_branch> [model]"}
SKILL_MODEL=${4:-claude-opus-4-6}
AI_HELPERS_DIR=${AI_HELPERS_DIR:-$(cd "$(dirname "$0")/../../../.." && pwd)}
WORK_DIR=${WORK_DIR:-$(mktemp -d)}

echo "=== Solve Pipeline Eval: $ISSUE_KEY ==="
echo "Repo: $REPO_URL"
echo "Branch: $EVAL_BRANCH"
echo "Model: $SKILL_MODEL"
echo "Workdir: $WORK_DIR"
echo "ai-helpers: $AI_HELPERS_DIR"

# Validate ai-helpers has the required plugins
if [ ! -f "$AI_HELPERS_DIR/plugins/jira/commands/solve.md" ]; then
  echo "ERROR: solve.md not found at $AI_HELPERS_DIR/plugins/jira/commands/solve.md"
  exit 1
fi
REVIEW_PLUGIN_DIR="$AI_HELPERS_DIR/plugins/code-review"
if [ ! -d "$REVIEW_PLUGIN_DIR/.claude-plugin" ]; then
  echo "ERROR: code-review plugin not found at $REVIEW_PLUGIN_DIR/.claude-plugin"
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
git clone "$REPO_URL" "$WORK_DIR/repo"
cd "$WORK_DIR/repo"
git checkout "$EVAL_BRANCH"
BASE_SHA=$(git rev-parse HEAD)

git config user.name "Eval Runner"
git config user.email "eval@test.local"

mkdir -p .claude/commands
cp "$AI_HELPERS_DIR/plugins/jira/commands/solve.md" .claude/commands/jira-solve.md

SKILL_CONTENT=$(cat .claude/commands/jira-solve.md)

# ── Phase 1: Solve ──
echo ""
echo "=========================================="
echo "Phase 1: Solve ($ISSUE_KEY)"
echo "=========================================="

SOLVE_CONTEXT="IMPORTANT: Do NOT create a Pull Request. Do NOT push to any remote. Just implement the changes, run tests, and commit to the local branch."

PHASE1_START=$(date +%s)

set +e
claude -p "$ISSUE_KEY origin --ci. $SOLVE_CONTEXT" \
  --system-prompt "$SKILL_CONTENT" \
  --allowedTools "Bash Read Write Edit Grep Glob WebFetch" \
  --max-turns 200 \
  --effort max \
  --model "$SKILL_MODEL" \
  --output-format stream-json \
  --verbose \
  2>"$WORK_DIR/phase1-stderr.log" \
  | tee "$WORK_DIR/phase1-output.json"
PHASE1_EXIT=$?
set -e

PHASE1_END=$(date +%s)
echo "Phase 1 duration: $((PHASE1_END - PHASE1_START))s (exit $PHASE1_EXIT)"

# Capture phase 1 state (committed + uncommitted changes)
{ git diff "$BASE_SHA"..HEAD 2>/dev/null; git diff HEAD 2>/dev/null; } > "$WORK_DIR/phase1-diff.patch" || true
{ git diff "$BASE_SHA"..HEAD --stat 2>/dev/null; git diff HEAD --stat 2>/dev/null; } > "$WORK_DIR/phase1-diffstat.txt" || true
extract_tokens "$WORK_DIR/phase1-output.json" > "$WORK_DIR/phase1-tokens.json"
extract_text "$WORK_DIR/phase1-output.json" > "$WORK_DIR/phase1-text.txt"

BRANCH=$(git branch --show-current)

CHANGED_FILES=$( { git diff "$BASE_SHA"..HEAD --name-only 2>/dev/null; git diff HEAD --name-only 2>/dev/null; } | sort -u || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo "No code changes produced by Phase 1"
  echo "no_changes" > "$WORK_DIR/phase1-result.txt"
  # Write empty outputs so judges can still evaluate
  touch "$WORK_DIR/diff.patch" "$WORK_DIR/files-changed.txt" "$WORK_DIR/commit-log.txt"
  touch "$WORK_DIR/review-findings.txt" "$WORK_DIR/coverage.txt"
  echo "1" > "$WORK_DIR/make-test-exit"
  echo "No code changes — make test not run" > "$WORK_DIR/make-test.log"
  echo "1" > "$WORK_DIR/make-verify-exit"
  echo "No code changes — make verify not run" > "$WORK_DIR/make-verify.log"
  echo '{"total_cost_usd":0}' > "$WORK_DIR/phase2-tokens.json"
  echo '{"total_cost_usd":0}' > "$WORK_DIR/phase3-tokens.json"
  jq -s '{total_cost_usd: (map(.total_cost_usd // 0) | add), phases: length}' \
    "$WORK_DIR"/phase*-tokens.json > "$WORK_DIR/total-cost.json" 2>/dev/null || true
  echo "=== Pipeline complete (no changes). Outputs in $WORK_DIR ==="
  exit 0
fi

echo "Changes on branch '$BRANCH':"
echo "$CHANGED_FILES" | sed 's/^/  /'
echo "changes_on_branch=$BRANCH" > "$WORK_DIR/phase1-result.txt"

# ── Phase 2: Code Review ──
echo ""
echo "=========================================="
echo "Phase 2: Code Review"
echo "=========================================="

PHASE2_START=$(date +%s)

set +e
claude -p "/code-review:pre-commit-review --language go --profile hypershift" \
  --plugin-dir "$REVIEW_PLUGIN_DIR" \
  --allowedTools "Bash Read Grep Glob Task" \
  --max-turns 75 \
  --effort max \
  --model "$SKILL_MODEL" \
  --output-format stream-json \
  --verbose \
  2>"$WORK_DIR/phase2-stderr.log" \
  | tee "$WORK_DIR/phase2-output.json"
PHASE2_EXIT=$?
set -e

PHASE2_END=$(date +%s)
echo "Phase 2 duration: $((PHASE2_END - PHASE2_START))s (exit $PHASE2_EXIT)"

extract_text "$WORK_DIR/phase2-output.json" > "$WORK_DIR/review-findings.txt"
extract_tokens "$WORK_DIR/phase2-output.json" > "$WORK_DIR/phase2-tokens.json"

# ── Phase 3: Address Review ──
echo ""
echo "=========================================="
echo "Phase 3: Address Review Findings"
echo "=========================================="

REVIEW_FINDINGS=$(cat "$WORK_DIR/review-findings.txt" 2>/dev/null || echo "")

PHASE3_START=$(date +%s)

if [ -n "$REVIEW_FINDINGS" ]; then
  FIX_PROMPT="A code review was performed on the changes in the current branch. Below are the review findings. Address all actions and improvements by editing the code. After making all fixes, commit the changes.

REVIEW FINDINGS:
${REVIEW_FINDINGS}

IMPORTANT:
- Fix every issue identified in the review — all actions and improvements.
- Run 'make test' and 'make verify' after fixes to verify nothing is broken.
- If 'make verify' generates new files, commit those too and run 'make verify' again.
- Commit all fixes.
- Do NOT push to any remote. Do NOT create a Pull Request."

  set +e
  claude -p "$FIX_PROMPT" \
    --allowedTools "Bash Read Write Edit Grep Glob" \
    --max-turns 75 \
    --effort max \
    --model "$SKILL_MODEL" \
    --output-format stream-json \
    --verbose \
    2>"$WORK_DIR/phase3-stderr.log" \
    | tee "$WORK_DIR/phase3-output.json"
  PHASE3_EXIT=$?
  set -e
else
  echo "No review findings to address, skipping Phase 3"
  echo '{}' > "$WORK_DIR/phase3-output.json"
  PHASE3_EXIT=0
fi

PHASE3_END=$(date +%s)
echo "Phase 3 duration: $((PHASE3_END - PHASE3_START))s (exit $PHASE3_EXIT)"
extract_tokens "$WORK_DIR/phase3-output.json" > "$WORK_DIR/phase3-tokens.json"

# ── Capture final outputs ──
echo ""
echo "=========================================="
echo "Final Output Capture"
echo "=========================================="

# Capture committed + uncommitted changes
{ git diff "$BASE_SHA"..HEAD 2>/dev/null; git diff HEAD 2>/dev/null; } > "$WORK_DIR/diff.patch"
{ git diff "$BASE_SHA"..HEAD --name-only 2>/dev/null; git diff HEAD --name-only 2>/dev/null; } | sort -u > "$WORK_DIR/files-changed.txt"
git log --oneline "$BASE_SHA"..HEAD > "$WORK_DIR/commit-log.txt"

echo "Final diff: $(wc -l < "$WORK_DIR/diff.patch") lines"
echo "Files changed: $(wc -l < "$WORK_DIR/files-changed.txt")"
echo "Commits: $(wc -l < "$WORK_DIR/commit-log.txt")"

# Clean up skill workspace artifacts that cause make verify to reject untracked files
rm -rf .claude/commands/jira-solve.md .work/ 2>/dev/null || true
rmdir .claude/commands .claude 2>/dev/null || true
git checkout -- .work/ .claude/ 2>/dev/null || true
git clean -fd .work/ .claude/ 2>/dev/null || true

# Run make test and make verify independently (not relying on what the agent ran)
echo ""
echo "Running make test..."
set +e
make test 2>&1 | tee "$WORK_DIR/make-test.log"
echo $? > "$WORK_DIR/make-test-exit"
echo "make test exit: $(cat "$WORK_DIR/make-test-exit")"

echo "Running make verify..."
make verify 2>&1 | tee "$WORK_DIR/make-verify.log"
echo $? > "$WORK_DIR/make-verify-exit"
echo "make verify exit: $(cat "$WORK_DIR/make-verify-exit")"
set -e

# Diff coverage — coverage of changed lines only (requires cov-diff)
CHANGED_PKGS=$( { git diff "$BASE_SHA"..HEAD --name-only -- '*.go' 2>/dev/null; git diff HEAD --name-only -- '*.go' 2>/dev/null; } \
  | grep -v '_test.go$' \
  | xargs -I{} dirname {} 2>/dev/null \
  | sort -u \
  | sed 's|^|./|' || echo "")
if [ -n "$CHANGED_PKGS" ]; then
  echo "Running diff coverage for changed packages..."
  set +e
  go test -coverprofile="$WORK_DIR/cover.out" $CHANGED_PKGS 2>&1 | tee "$WORK_DIR/coverage-raw.txt"
  if command -v cov-diff >/dev/null 2>&1 && [ -f "$WORK_DIR/cover.out" ]; then
    git diff "$BASE_SHA"..HEAD > "$WORK_DIR/pr.diff"
    GO_MODULE=$(grep "^module " go.mod | awk '{print $2}')
    DIFF_COV=$(cov-diff -coverprofile "$WORK_DIR/cover.out" -diff "$WORK_DIR/pr.diff" -path . -module "$GO_MODULE" 2>/dev/null | sed -n 's/.*: \([0-9]*\)%.*/\1/p' || echo "")
    if [ -n "$DIFF_COV" ]; then
      echo "diff-coverage: ${DIFF_COV}% of changed lines covered" > "$WORK_DIR/coverage.txt"
    else
      echo "diff-coverage: could not compute" > "$WORK_DIR/coverage.txt"
      cat "$WORK_DIR/coverage-raw.txt" >> "$WORK_DIR/coverage.txt"
    fi
  else
    cp "$WORK_DIR/coverage-raw.txt" "$WORK_DIR/coverage.txt"
  fi
  set -e
else
  echo "no go source files changed" > "$WORK_DIR/coverage.txt"
fi

# Aggregate cost across all phases
jq -s '{
  total_cost_usd: (map(.total_cost_usd // 0) | add),
  total_duration_ms: (map(.duration_ms // 0) | add),
  total_turns: (map(.num_turns // 0) | add),
  total_input_tokens: (map(.input_tokens // 0) | add),
  total_output_tokens: (map(.output_tokens // 0) | add),
  phases: length
}' "$WORK_DIR"/phase*-tokens.json > "$WORK_DIR/total-cost.json" 2>/dev/null \
  || echo '{"total_cost_usd":0,"phases":0}' > "$WORK_DIR/total-cost.json"

# Fetch known-good PR diff for judge comparison (if input.yaml specifies one)
KNOWN_PR=$(grep 'known_good_pr' "${WORK_DIR}/../input.yaml" 2>/dev/null | sed 's/.*: *//' | tr -d '"' || echo "")
if [ -n "$KNOWN_PR" ]; then
  echo "Fetching known-good PR diff: $KNOWN_PR"
  PR_NUM=$(echo "$KNOWN_PR" | grep -oE '[0-9]+$')
  PR_REPO=$(echo "$KNOWN_PR" | sed 's|https://github.com/||;s|/pull/.*||')
  set +e
  gh pr diff "$PR_NUM" --repo "$PR_REPO" > "$WORK_DIR/known-good.patch" 2>/dev/null
  set -e
  if [ -s "$WORK_DIR/known-good.patch" ]; then
    echo "Known-good PR diff: $(wc -l < "$WORK_DIR/known-good.patch") lines"
  else
    echo "Could not fetch known-good PR diff"
    rm -f "$WORK_DIR/known-good.patch"
  fi
fi

# Copy judge-relevant files to output/ (excludes large JSON/log blobs)
# The eval harness reads output/ for {{ outputs }} in LLM judge prompts.
JUDGE_DIR="${WORK_DIR}/../output"
if [ -d "$JUDGE_DIR" ]; then
  for f in diff.patch phase1-diff.patch phase1-diffstat.txt files-changed.txt \
           commit-log.txt review-findings.txt coverage.txt phase1-text.txt \
           make-test-exit make-verify-exit total-cost.json \
           phase1-tokens.json phase2-tokens.json phase3-tokens.json \
           known-good.patch; do
    [ -f "$WORK_DIR/$f" ] && cp "$WORK_DIR/$f" "$JUDGE_DIR/$f"
  done
fi

# Remove large files that blow up {{ outputs }} if the _modified collector picks them up
rm -f "$WORK_DIR"/phase*-output.json

echo ""
echo "=== Pipeline complete. Outputs in $WORK_DIR ==="
echo "Cost: $(jq -r '.total_cost_usd' "$WORK_DIR/total-cost.json") USD"
