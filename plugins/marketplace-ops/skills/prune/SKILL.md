---
name: prune
description: Use when running the marketplace pruning workflow. Analyzes flagged plugin commands and skills for staleness, applying LLM judgment to decide which items should be removed. Invoked by CI after deterministic scoring scripts have already identified candidates.
---

# Marketplace Prune — LLM Item Review

You receive the output of the deterministic scoring scripts and apply qualitative judgment to decide which flagged items to actually remove.

## Input

You will be given a JSON file path containing the output of `score-items.py`. The `flagged` array contains items with score >= 3 that need your review.

## Your Task

For each flagged item, read its source file and evaluate:

1. **AI reasoning required?** Does the command/skill require AI analysis, decisions, or judgment? Or could it be a shell alias, Makefile target, or simple script wrapper? Items that don't require AI reasoning violate the repo's contribution rules and are strong removal candidates.
2. **Duplication.** Does this substantially overlap with another command/skill in the marketplace? Check for similar names, descriptions, or functionality.
3. **Dead references.** Does it reference tools, APIs, services, or URLs that no longer exist or are deprecated?
4. **Utility.** Would an engineering organization find this command/skill useful in practice?

Only recommend removal when **both** the quantitative signals (already flagged by the script) **and** your qualitative judgment (low utility) agree. When in doubt, keep the item.

## Output

Print a JSON array to stdout with your decisions. Each element:

```json
{
  "path": "plugins/foo/commands/bar.md",
  "action": "remove",
  "reason": "Wraps a single curl command with no AI reasoning required"
}
```

For items you decide to **keep**, include them with `"action": "keep"`:

```json
{
  "path": "plugins/foo/commands/baz.md",
  "action": "keep",
  "reason": "Requires LLM judgment to interpret error logs"
}
```

## Procedure

1. Read the flagged items JSON provided as your argument.
2. For each flagged item, use the Read tool to read its source file.
3. Evaluate using the four criteria above.
4. Print the complete JSON array as a fenced code block tagged `json` to stdout.

Do NOT remove files, create branches, or open PRs. Your only job is to output the judgment JSON.
