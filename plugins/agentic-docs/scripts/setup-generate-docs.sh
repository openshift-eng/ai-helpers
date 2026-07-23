#!/bin/bash

# Generate Docs Setup Script
# Creates state file for iterative generate→review doc loop

set -euo pipefail

REPO_PATH=""
MAX_ITERATIONS=5
SKIP_GENERATE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      cat << 'HELP_EOF'
Generate Docs - Iterative documentation generation and review

USAGE:
  /generate-docs [PATH] [OPTIONS]

ARGUMENTS:
  PATH              Path to component repository (default: current directory)

OPTIONS:
  --max-iterations N   Maximum review iterations (default: 5)
  --review             Review-only mode: skip generation, only run /review-docs loop
  --skip-generate      Alias for --review
  -h, --help           Show this help message

DESCRIPTION:
  Generates component docs with /component-docs, then iteratively reviews
  with /review-docs --auto-fix until all issues are resolved or max
  iterations is reached.

  The stop hook prevents exit and re-feeds the review prompt until Claude
  outputs <promise>DOCS VERIFIED</promise> — which it should only do when
  /review-docs finds 0 critical issues and 0 warnings.

EXAMPLES:
  /generate-docs                                    # Current dir, 5 iterations
  /generate-docs /path/to/repo --max-iterations 3   # Custom path and limit
  /generate-docs --review                            # Review existing docs only
  /generate-docs --skip-generate                    # Same as --review

STOPPING:
  /cancel-generate-docs                         # Cancel the active loop
HELP_EOF
      exit 0
      ;;
    --max-iterations)
      if [[ -z "${2:-}" ]] || ! [[ "$2" =~ ^[0-9]+$ ]] || [[ "$2" -eq 0 ]]; then
        echo "❌ --max-iterations requires a positive integer (>= 1)" >&2
        exit 1
      fi
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --review|--skip-generate)
      SKIP_GENERATE=true
      shift
      ;;
    *)
      if [[ -z "$REPO_PATH" ]]; then
        REPO_PATH="$1"
      else
        echo "❌ Unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

REPO_PATH="${REPO_PATH:-$PWD}"

if [[ ! -d "$REPO_PATH" ]]; then
  echo "❌ Repository path does not exist: $REPO_PATH" >&2
  exit 1
fi

mkdir -p .claude

COMPLETION_PROMISE="DOCS VERIFIED"

# Resolve the review-docs skill path so the verification agent can read it directly
SKILL_PATH="$(cd "$(dirname "$0")/../skills/review-docs" && pwd)"

if [[ "$SKIP_GENERATE" == "true" ]]; then
  PROMPT_TEXT="Follow these steps IN ORDER. Do not skip any step.

Step 1: Run /review-docs --path \"$REPO_PATH\" --auto-fix to review the documentation.

Step 2: If /review-docs reports ANY critical issues or warnings, fix them:
  a. For EACH issue, grep the entire doc set for all occurrences of the incorrect claim
     before making any edit.
  b. Fix ALL files that contain the incorrect claim in one pass.
  c. After fixing detailed sections, check whether summaries or diagrams in the SAME file
     repeat the claim in simplified form. Fix those too.
  d. After all fixes, do a final grep to confirm no file still contains the old claim.
  e. Write a brief corrections manifest listing each fix: what was wrong, what it was
     changed to, and the verification source. Include this manifest in the verification
     agent's prompt (Step 3).

Step 3 (MANDATORY — independent verification): After fixing issues, you MUST verify
the fixes using an isolated Agent to prevent confirmation bias. Spawn a fresh
general-purpose Agent with this prompt:

  \"You are an independent documentation reviewer for $REPO_PATH.
   Read the review methodology at $SKILL_PATH/SKILL.md, then follow its
   Phase 1 through Phase 5 workflow to review the agentic documentation.
   Skip Phase 6 entirely — do NOT fix anything, only report findings.
   Report: coverage metrics (total claims, verified, failed, skipped),
   issues by severity (critical/warning/minor), and a clear verdict.
   If there are 0 critical issues AND 0 warnings, state: VERIFIED CLEAN.
   Otherwise list every issue with its file, line, and what is wrong.

   CORRECTIONS MANIFEST (from the fixer — verify these were applied consistently):
   <paste the corrections manifest here>

   For each correction in the manifest:
   1. Verify the docs now match the stated correction
   2. Verify the correction is applied consistently across ALL files (grep for the concept)
   3. Spot-check the cited verification source if accessible
   Do NOT re-derive the correct value from scratch unless the cited source is
   unavailable or contradicts itself.\"

CRITICAL: Each verification Agent MUST be a fresh spawn (never resumed) so it
approaches the docs with zero prior context. This is what prevents the
confirmation bias that occurs when the same conversation reviews its own fixes.

Step 4: Read the Agent's report.
  - If the Agent reports VERIFIED CLEAN: output exactly <promise>DOCS VERIFIED</promise>
  - If the Agent found issues: fix each reported issue, then go back to Step 3
    (spawn a NEW fresh Agent — never resume the previous one).

RULES:
- NEVER verify your own fixes by running /review-docs directly — always use a fresh Agent.
- NEVER output the promise tag without a clean Agent verification report.
- NEVER resume a previous verification agent — always spawn a new one.
- If the Agent reports issues you believe are false positives, investigate by reading
  the source code yourself. If confirmed false positive, you may still output the
  promise. If confirmed real, fix and re-verify with another Agent."
else
  PROMPT_TEXT="Step 1 (first iteration only): If component documentation does not yet exist at $REPO_PATH/ai-docs/, generate it with /component-docs --path \"$REPO_PATH\". If ai-docs/ already exists, skip generation.

IMPORTANT: /component-docs Phase 1 asks the user an SME context question (\"Before I start, is there anything about this repo I should know that isn't obvious from the code?\"). You MUST wait for the user's response before proceeding with codebase exploration and documentation generation. Do NOT start exploring code or writing docs until the user has answered (or explicitly declined). This input shapes what you investigate.

Step 2: Run /review-docs --path \"$REPO_PATH\" --auto-fix to review the documentation.

Step 3: If /review-docs reports ANY critical issues or warnings, fix them:
  a. For EACH issue, grep the entire doc set for all occurrences of the incorrect claim
     before making any edit.
  b. Fix ALL files that contain the incorrect claim in one pass.
  c. After fixing detailed sections, check whether summaries or diagrams in the SAME file
     repeat the claim in simplified form. Fix those too.
  d. After all fixes, do a final grep to confirm no file still contains the old claim.
  e. Write a brief corrections manifest listing each fix: what was wrong, what it was
     changed to, and the verification source. Include this manifest in the verification
     agent's prompt (Step 4).

Step 4 (MANDATORY — independent verification): After fixing issues, you MUST verify
the fixes using an isolated Agent to prevent confirmation bias. Spawn a fresh
general-purpose Agent with this prompt:

  \"You are an independent documentation reviewer for $REPO_PATH.
   Read the review methodology at $SKILL_PATH/SKILL.md, then follow its
   Phase 1 through Phase 5 workflow to review the agentic documentation.
   Skip Phase 6 entirely — do NOT fix anything, only report findings.
   Report: coverage metrics (total claims, verified, failed, skipped),
   issues by severity (critical/warning/minor), and a clear verdict.
   If there are 0 critical issues AND 0 warnings, state: VERIFIED CLEAN.
   Otherwise list every issue with its file, line, and what is wrong.

   CORRECTIONS MANIFEST (from the fixer — verify these were applied consistently):
   <paste the corrections manifest here>

   For each correction in the manifest:
   1. Verify the docs now match the stated correction
   2. Verify the correction is applied consistently across ALL files (grep for the concept)
   3. Spot-check the cited verification source if accessible
   Do NOT re-derive the correct value from scratch unless the cited source is
   unavailable or contradicts itself.\"

CRITICAL: Each verification Agent MUST be a fresh spawn (never resumed) so it
approaches the docs with zero prior context. This is what prevents the
confirmation bias that occurs when the same conversation reviews its own fixes.

Step 5: Read the Agent's report.
  - If the Agent reports VERIFIED CLEAN: output exactly <promise>DOCS VERIFIED</promise>
  - If the Agent found issues: fix each reported issue, then go back to Step 4
    (spawn a NEW fresh Agent — never resume the previous one).

RULES:
- NEVER verify your own fixes by running /review-docs directly — always use a fresh Agent.
- NEVER output the promise tag without a clean Agent verification report.
- NEVER resume a previous verification agent — always spawn a new one.
- If the Agent reports issues you believe are false positives, investigate by reading
  the source code yourself. If confirmed false positive, you may still output the
  promise. If confirmed real, fix and re-verify with another Agent."
fi

cat > .claude/generate-docs.local.md <<EOF
---
active: true
iteration: 1
max_iterations: $MAX_ITERATIONS
completion_promise: "$COMPLETION_PROMISE"
skip_generate: $SKIP_GENERATE
repo_path: "$REPO_PATH"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

$PROMPT_TEXT
EOF

cat <<EOF

🔄 Generate-docs loop activated!

Repository:      $REPO_PATH
Generate docs:   $(if [[ "$SKIP_GENERATE" == "true" ]]; then echo "skipped (--review)"; else echo "yes (/component-docs)"; fi)
Max iterations:  $MAX_ITERATIONS
Completion:      When /review-docs finds 0 critical issues and 0 warnings

The stop hook will prevent exit and re-feed the review prompt until docs
are verified clean. To cancel: /cancel-generate-docs

EOF

echo "$PROMPT_TEXT"
