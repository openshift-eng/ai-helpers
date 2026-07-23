---
description: "Generate and iteratively review component docs until all issues are fixed"
argument-hint: "[PATH] [--max-iterations N] [--review] [--skip-generate]"
allowed-tools:
  - "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup-generate-docs.sh:*)"
---

# Generate Docs Command

Execute the setup script to initialize the docs loop:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/setup-generate-docs.sh" $ARGUMENTS
```

Work on the task as described in the prompt output. The docs loop stop hook re-feeds the review prompt on exit, so you iterate on reviews until the documentation is clean.

CRITICAL RULE: Only output `<promise>DOCS VERIFIED</promise>` when `/review-docs` genuinely reports 0 critical issues and 0 warnings. Do not output a false promise to escape the loop.
