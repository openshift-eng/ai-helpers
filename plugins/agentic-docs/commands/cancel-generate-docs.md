---
description: "Cancel active generate-docs loop"
allowed-tools:
  - "Bash(test -f .claude/generate-docs.local.md:*)"
  - "Bash(rm .claude/generate-docs.local.md)"
  - "Read(.claude/generate-docs.local.md)"
---

# Cancel Generate Docs

To cancel the generate-docs loop:

1. Check if `.claude/generate-docs.local.md` exists using Bash: `test -f .claude/generate-docs.local.md && echo "EXISTS" || echo "NOT_FOUND"`

2. **If NOT_FOUND**: Say "No active generate-docs loop found."

3. **If EXISTS**:
   - Read `.claude/generate-docs.local.md` to get the current iteration number from the `iteration:` field
   - Remove the file using Bash: `rm .claude/generate-docs.local.md`
   - Report: "Cancelled generate-docs loop (was at iteration N)" where N is the iteration value
