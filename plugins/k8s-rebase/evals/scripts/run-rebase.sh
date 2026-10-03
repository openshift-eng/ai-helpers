#!/bin/bash
set -euo pipefail

# run-rebase.sh — eval runner for the k8s-rebase skill.
#
# Invokes the skill exactly like test-skill.sh's cmd_run does (same
# --plugin-dir / --permission-mode / --disallowed-tools flags — do not
# drop or modify these, they are what makes the skill's own safety
# hooks load and enforce in a headless session), but synchronously
# (claude -p, not claude --bg) so cost/tokens are directly capturable.
#
# Usage:
#   run-rebase.sh <repo_url> <from_commit> <version> [model] [known_good_url] [known_good_ref]
#
# Env vars:
#   AI_HELPERS_DIR   — path to ai-helpers checkout (default: auto-detect)
#   EVAL_REPO_DIR    — override the clone location (default: cached under
#                       evals/.repos/, keyed by repo_url)
#   SKILL_MAX_TURNS  — passed to claude -p --max-turns. Default: 200.

REPO_URL=${1:?"Usage: $0 <repo_url> <from_commit> <version> [model] [known_good_url] [known_good_ref]"}
FROM_COMMIT=${2:?"Usage: $0 <repo_url> <from_commit> <version> [model] [known_good_url] [known_good_ref]"}
VERSION=${3:?"Usage: $0 <repo_url> <from_commit> <version> [model] [known_good_url] [known_good_ref]"}
SKILL_MODEL=${4:-claude-sonnet-4-6}
KNOWN_GOOD_URL=${5:-}
KNOWN_GOOD_REF=${6:-}
AI_HELPERS_DIR=${AI_HELPERS_DIR:-$(cd "$(dirname "$0")/../../../.." && pwd)}
PLUGIN_DIR="$AI_HELPERS_DIR/plugins/k8s-rebase"
PERMISSION_MODE="${PERMISSION_MODE:-bypassPermissions}"
MAX_TURNS="${SKILL_MAX_TURNS:-200}"

OUTPUT_DIR="$(pwd)/output"
mkdir -p "$OUTPUT_DIR"

REPO_DIR="${EVAL_REPO_DIR:-$AI_HELPERS_DIR/plugins/k8s-rebase/evals/.repos/$(echo "$REPO_URL" | sed -E 's#https?://github\.com/##; s#/#_#g')}"

# Write infra_error as the first filesystem op — SIGKILL (a plausible
# harness timeout mechanism) won't fire any trap, so this must exist
# before any other work. Only the success path overwrites it to completed.
write_status() {
  local status="$1" reason="$2"
  jq -n --arg status "$status" --arg reason "$reason" \
    '{status: $status, reason: $reason}' > "$OUTPUT_DIR/run-status.json.tmp"
  mv "$OUTPUT_DIR/run-status.json.tmp" "$OUTPUT_DIR/run-status.json"  # atomic
}
write_status "infra_error" "run-rebase.sh exited unexpectedly before completion"

on_err() {
  trap - ERR
  write_status "infra_error" "run-rebase.sh failed (see session-stderr.log / trap)"
}
trap on_err ERR

echo "=== k8s-rebase Eval: $REPO_URL @ $VERSION (model: $SKILL_MODEL) ==="

# Always reset at run start, not end — a post-run reset would race with
# output capture by the next run on the same cached clone.
if [[ ! -d "$REPO_DIR/.git" ]]; then
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"
# Restore origin fetch URL — the skill may have run `git remote set-url origin
# file:///dev/null/fake-remote` as an extra push-block, poisoning future fetches.
git remote set-url origin "$REPO_URL"
# Discard any uncommitted changes a prior run left — must happen before
# checkout or git will refuse to switch branches over modified files.
git restore . 2>/dev/null || git checkout -- . 2>/dev/null || true
git clean -fdx
git fetch origin "$FROM_COMMIT"
# Detach HEAD before deleting stale bump branches — avoids "cannot delete
# checked-out branch" if a prior run left us on a bump* branch.
git checkout --detach "$FROM_COMMIT"
git branch | grep -E '^\s*(bump|rebase-)' | xargs -r git branch -D || true
git reset --hard "$FROM_COMMIT"
git clean -fdx
rm -rf "$REPO_DIR/.rebase-tmp"  # not removed by git clean if gitignored
git config user.name "k8s-rebase-eval"
git config user.email "eval@k8s-rebase.local"

set +e
claude -p "/k8s-rebase:k8s-rebase $VERSION" \
  --output-format stream-json \
  --verbose \
  --max-turns "$MAX_TURNS" \
  --model "$SKILL_MODEL" \
  --plugin-dir "$PLUGIN_DIR" \
  --permission-mode "$PERMISSION_MODE" \
  --disallowed-tools 'Bash(git push *),Bash(*git push*),Bash(git -c *push*),Bash(*send-pack*),Bash(gh pr create *),Bash(*gh pr create*),Bash(*gh api*repos*pulls*),Bash(go mod tidy*),Bash(go mod get*),Bash(go mod vendor*),Bash(go mod edit*),Bash(go get *),Bash(go generate *),Bash(go run *)' \
  2>"$OUTPUT_DIR/session-stderr.log" \
  | tee "$OUTPUT_DIR/session-output.json"
PIPE_STATUS=("${PIPESTATUS[@]}")  # snapshot before set -e resets it
SKILL_EXIT=${PIPE_STATUS[0]}
TEE_EXIT=${PIPE_STATUS[1]}
set -e

if [[ $SKILL_EXIT -ne 0 ]]; then
  write_status "infra_error" "skill exited $SKILL_EXIT"; exit 1
fi
if [[ $TEE_EXIT -ne 0 ]]; then
  write_status "infra_error" "tee failed writing session-output.json (disk full?)"; exit 1
fi

# Extract cost/tokens into metrics.json (CLI runner contract).
# tail -1: in multi-turn sessions the last "type":"result" event has
# cumulative cost; earlier events are partial-cost snapshots.
grep '"type":"result"' "$OUTPUT_DIR/session-output.json" 2>/dev/null \
  | tail -1 \
  | jq --arg model "$SKILL_MODEL" '{
      token_usage: {
        input: (.usage.input_tokens // 0),
        output: (.usage.output_tokens // 0)
      },
      cost_usd: (.total_cost_usd // 0),
      num_turns: (.num_turns // 0),
      model: $model
    }' 2>/dev/null \
  > "$OUTPUT_DIR/metrics.json" \
  || echo "{\"token_usage\":{\"input\":0,\"output\":0},\"cost_usd\":0,\"num_turns\":0,\"model\":\"$SKILL_MODEL\"}" > "$OUTPUT_DIR/metrics.json"
echo "Cost/tokens:"
cat "$OUTPUT_DIR/metrics.json"

# cmd_status exits 0 in both DONE:true and DONE:false paths; the judge
# reads the output text, not the exit code.
bash "$PLUGIN_DIR/scripts/k8s-rebase-orchestrator.sh" status "$REPO_DIR" \
  > "$OUTPUT_DIR/final-status.txt" 2>&1

# .rebase-tmp/status/INCOMPLETE is written unconditionally on force-advance;
# orchestrator `status` only surfaces it conditionally, so check directly.
if [[ -f "$REPO_DIR/.rebase-tmp/status/INCOMPLETE" ]]; then
  cp "$REPO_DIR/.rebase-tmp/status/INCOMPLETE" "$OUTPUT_DIR/force-advance.log"
else
  : > "$OUTPUT_DIR/force-advance.log"
fi

mkdir -p "$OUTPUT_DIR/gate-reports"
cp "$REPO_DIR"/.rebase-tmp/gates/*.report "$OUTPUT_DIR/gate-reports/" 2>/dev/null || true

# Same exclusions as cmd_court (test-skill.sh) — vendor/go.sum/packages/mocks
# are generated/resolver output that would blow up the diff an LLM judge reads.
COURT_EXCLUDES=(':!.rebase-tmp' ':(exclude,glob)**/vendor/**' ':(exclude,glob)**/go.sum' ':(exclude,glob)**/packages/**' ':(exclude,glob)**/mocks/**')
git diff "$FROM_COMMIT"..HEAD -- . "${COURT_EXCLUDES[@]}" > "$OUTPUT_DIR/diff.patch" 2>/dev/null || true
git diff "$FROM_COMMIT"..HEAD --name-only -- . "${COURT_EXCLUDES[@]}" > "$OUTPUT_DIR/files-changed.txt" 2>/dev/null || true
git diff "$FROM_COMMIT"..HEAD --name-only > "$OUTPUT_DIR/files-changed-all.txt" 2>/dev/null || true

if [[ -n "$KNOWN_GOOD_REF" ]]; then
  _kg_fetch_ok=false
  _kg_ref=FETCH_HEAD
  if [[ -n "$KNOWN_GOOD_URL" && "$KNOWN_GOOD_URL" != "$REPO_URL" ]]; then
    # known_good lives on a fork — fetch from that remote, not "origin".
    # set-url first: cached clone may have a stale known-good-remote URL.
    git remote set-url known-good-remote "$KNOWN_GOOD_URL" 2>/dev/null \
      || git remote add known-good-remote "$KNOWN_GOOD_URL"
    git fetch known-good-remote "$KNOWN_GOOD_REF" 2>/dev/null && _kg_fetch_ok=true || true
  else
    # GitHub blocks fetching unadvertised SHAs (upload-pack: not our ref).
    # Try direct SHA fetch first; fall back to guessing the branch name from
    # the rebase script's naming convention (bump<major>.<minor>).
    git fetch origin "$KNOWN_GOOD_REF" 2>/dev/null && _kg_fetch_ok=true || {
      _kg_branch="bump${VERSION%.*}"
      echo ":: known-good SHA fetch failed — trying branch $KNOWN_GOOD_URL:${_kg_branch}" >&2
      git fetch origin "${_kg_branch}" 2>/dev/null \
        && git rev-parse "FETCH_HEAD" >/dev/null 2>&1 \
        && git merge-base --is-ancestor "$KNOWN_GOOD_REF" FETCH_HEAD 2>/dev/null \
        && _kg_ref="$KNOWN_GOOD_REF" \
        && _kg_fetch_ok=true || true
    }
  fi
  if [[ "$_kg_fetch_ok" == true ]]; then
    # A fallback branch supplies the object, not a replacement comparison tip.
    KNOWN_GOOD_SHA=$(git rev-parse --verify "${_kg_ref}^{commit}")
    git diff "$FROM_COMMIT".."$KNOWN_GOOD_SHA" -- . "${COURT_EXCLUDES[@]}" > "$OUTPUT_DIR/known-good.patch" 2>/dev/null || true
  else
    echo ":: WARNING: could not fetch known-good ref $KNOWN_GOOD_REF — known-good.patch will be empty; LLM judges will skip Phase 1 gap analysis" >&2
    : > "$OUTPUT_DIR/known-good.patch"
  fi
else
  : > "$OUTPUT_DIR/known-good.patch"
fi

# Scope to Bash-only tool_results by collecting Bash tool_use_ids first —
# prevents gate/skill file reads (prose with "error") from polluting the output.
jq -rs '
  ( [.[] | select(.type == "assistant")
       | .message.content[]?
       | select(.type == "tool_use" and .name == "Bash")
       | .id] | unique) as $bash_ids |
  .[] | select(.type == "user")
      | .message.content[]?
      | select(.type == "tool_result" and ([$bash_ids[] == .tool_use_id] | any))
      | (.content[]? | select(.type == "text") | .text) // (.content // empty)
' "$OUTPUT_DIR/session-output.json" 2>/dev/null \
  | grep -iE '(^.+\.go:[0-9]+:|undefined:|cannot use |type mismatch|cannot find |not enough arguments|too many arguments|does not implement|incompatible types|has no field|declared and not used|declared but not used)' \
  > "$OUTPUT_DIR/build-errors.txt" || true

# Scope to tool_use events only — the skill prints a `git push` command for
# the user to copy in step 5, so a raw transcript grep would false-positive.
# tool_use events are nested inside assistant.message.content[], not top-level.
set +e
jq -e -rs --arg pat 'git\s+push|gh\s+pr\s+create' \
    '[.[] | select(.type=="assistant")
          | .message.content[]?
          | select(.type=="tool_use")
          | .input.command // ""] | any(test($pat))' \
    "$OUTPUT_DIR/session-output.json" > /dev/null 2>&1
PUSH_JQ_EXIT=$?
set -e
if [[ $PUSH_JQ_EXIT -eq 0 ]]; then
  if grep -q "BLOCKED: The k8s-rebase skill does not push or create PRs." \
      "$OUTPUT_DIR/session-output.json" 2>/dev/null; then
    echo "PUSH_STATUS: BLOCKED" > "$OUTPUT_DIR/push-attempt.log"
    echo "Push/PR-create tool_use found; denial text confirmed." >> "$OUTPUT_DIR/push-attempt.log"
  else
    echo "PUSH_STATUS: ATTEMPTED_UNBLOCKED" > "$OUTPUT_DIR/push-attempt.log"
    echo "WARNING: push/PR-create tool_use found but denial text NOT found." >> "$OUTPUT_DIR/push-attempt.log"
  fi
else
  echo "PUSH_STATUS: NONE" > "$OUTPUT_DIR/push-attempt.log"
fi

# Extract all assistant text before deleting session-output.json.
# step5 outputs "gh pr create" as assistant text (not a tool_use), so
# the push-attempt.log check above won't capture it. Join all assistant
# text blocks for the step5_pr_command_printed judge.
jq -rs '[.[] | select(.type=="assistant")
             | .message.content[]?
             | select(.type=="text")
             | .text] | join("\n")' \
  "$OUTPUT_DIR/session-output.json" \
  > "$OUTPUT_DIR/pr-command.txt" 2>/dev/null || true

# Remove large files the harness would otherwise load into outputs["files"].
rm -f "$OUTPUT_DIR/session-output.json" "$OUTPUT_DIR/session-stderr.log"

trap - ERR
write_status "completed" ""
