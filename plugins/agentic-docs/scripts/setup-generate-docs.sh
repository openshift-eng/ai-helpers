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
  a fresh verification Agent reports 0 critical issues and 0 warnings.

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

SKILL_PATH="$(cd "$(dirname "$0")/../skills/review-docs" && pwd)"

if [[ "$SKIP_GENERATE" == "true" ]]; then
  PROMPT_TEXT="WORKFLOW: review → fix → spawn verification Agent → read verdict → promise or loop

1. Run /review-docs --path \"$REPO_PATH\" --auto-fix

2. If issues found, fix them:
   - Grep entire doc set for each incorrect claim before editing
   - Fix ALL files containing the claim in one pass
   - After fixes, grep again to confirm nothing was missed
   - Write a corrections manifest (what was wrong → what it's now → source)

3. SPAWN A VERIFICATION AGENT (mandatory — the stop hook checks for this):
   Use the Agent tool to spawn a fresh general-purpose Agent with this prompt:

   \"Independent documentation reviewer for $REPO_PATH.
   Read $SKILL_PATH/SKILL.md, follow Phase 1-5 to review ai-docs/.
   Skip Phase 6 — do NOT fix anything, only report.
   Report: coverage metrics, issues by severity, verdict.
   0 critical + 0 warnings = state VERIFIED CLEAN.
   Otherwise list every issue with file, line, and what is wrong.\"

   Include the corrections manifest in the Agent prompt.
   Each Agent MUST be a fresh spawn — never resume a previous one.

4. Read the Agent's verdict:
   - VERIFIED CLEAN → output <promise>DOCS VERIFIED</promise>
   - Issues found → fix them, go back to step 3 with a NEW Agent

RULES:
- You MUST use the Agent tool before outputting the promise. The stop hook
  verifies an Agent was spawned — it will reject the promise if you skip this.
- NEVER verify your own fixes directly — always use a fresh Agent.
- NEVER resume a previous verification Agent."
else
  PROMPT_TEXT="WORKFLOW: generate → review → fix → spawn verification Agent → verdict → promise or loop

1. If ai-docs/ does not exist: run /component-docs --path \"$REPO_PATH\"
   IMPORTANT: /component-docs asks an SME context question first. Wait for the
   user's response before proceeding. Do NOT start until the user has answered.

2. Run /review-docs --path \"$REPO_PATH\" --auto-fix

3. If issues found, fix them:
   - Grep entire doc set for each incorrect claim before editing
   - Fix ALL files containing the claim in one pass
   - After fixes, grep again to confirm nothing was missed
   - Write a corrections manifest (what was wrong → what it's now → source)

4. SPAWN A VERIFICATION AGENT (mandatory — the stop hook checks for this):
   Use the Agent tool to spawn a fresh general-purpose Agent with this prompt:

   \"Independent documentation reviewer for $REPO_PATH.
   Read $SKILL_PATH/SKILL.md, follow Phase 1-5 to review ai-docs/.
   Skip Phase 6 — do NOT fix anything, only report.
   Report: coverage metrics, issues by severity, verdict.
   0 critical + 0 warnings = state VERIFIED CLEAN.
   Otherwise list every issue with file, line, and what is wrong.\"

   Include the corrections manifest in the Agent prompt.
   Each Agent MUST be a fresh spawn — never resume a previous one.

5. Read the Agent's verdict:
   - VERIFIED CLEAN → output <promise>DOCS VERIFIED</promise>
   - Issues found → fix them, go back to step 4 with a NEW Agent

RULES:
- You MUST use the Agent tool before outputting the promise. The stop hook
  verifies an Agent was spawned — it will reject the promise if you skip this.
- NEVER verify your own fixes directly — always use a fresh Agent.
- NEVER resume a previous verification Agent."
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
Completion:      When verification Agent reports 0 critical issues and 0 warnings

The stop hook will prevent exit and re-feed the review prompt until docs
are verified clean. To cancel: /cancel-generate-docs

EOF

echo "$PROMPT_TEXT"
