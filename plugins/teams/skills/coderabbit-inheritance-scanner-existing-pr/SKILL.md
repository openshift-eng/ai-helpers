---
name: CodeRabbit Inheritance Scanner - Existing PR Check
description: Search for an existing fix PR on a repo before opening a new one
---

# CodeRabbit Inheritance Scanner - Existing PR Check

This skill checks whether a repository already has an open pull request whose title contains `"CodeRabbit inheritance"` (case-insensitive substring match). Teams sometimes modify PR titles to satisfy merge requirements, so a substring match avoids missing renamed PRs. This prevents duplicate PRs from being opened.

## When to Use This Skill

Use this skill as Step 3 of the `/teams:coderabbit-inheritance-scanner` command, after identifying non-compliant repos. Call it for each non-compliant repo.

## Procedure

For a batch of non-compliant repos, check for existing PRs:

```bash
# Input: NON_COMPLIANT_REPOS array of "org/repo" strings
# Output: prints PR status for each repo

for REPO in "${NON_COMPLIANT_REPOS[@]}"; do
  # Search for open PRs whose title contains "CodeRabbit inheritance" (case-insensitive)
  PR_DATA=$(gh api "repos/${REPO}/pulls" \
    -f "state=open" \
    -f "per_page=100" \
    --jq '[.[] | select(.title | ascii_downcase | contains("coderabbit inheritance"))] | first? | {number: .number, html_url: .html_url, created_at: .created_at} // empty' 2>/dev/null)

  if [ -n "$PR_DATA" ]; then
    PR_NUMBER=$(echo "$PR_DATA" | jq -r '.number')
    PR_URL=$(echo "$PR_DATA" | jq -r '.html_url')
    CREATED_AT=$(echo "$PR_DATA" | jq -r '.created_at')

    # Calculate days open
    CREATED_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED_AT" "+%s" 2>/dev/null || date -d "$CREATED_AT" "+%s" 2>/dev/null)
    NOW_EPOCH=$(date "+%s")
    DAYS_OPEN=$(( (NOW_EPOCH - CREATED_EPOCH) / 86400 ))

    echo "HAS_PR|${REPO}|${PR_URL}|${DAYS_OPEN}"
  else
    echo "NO_PR|${REPO}||"
  fi

  sleep 0.3
done
```

## Output Format

Pipe-separated fields per line:

```
STATUS|org/repo|pr_url|days_open
```

Where STATUS is one of:
- `HAS_PR` - An open PR with the expected title was found
- `NO_PR` - No matching open PR exists

## Notes

- Only checks for **open** PRs, not closed or merged ones. A previously merged PR means the repo may have become compliant (the check skill would have already classified it as `COMPLIANT`).
- A previously closed (not merged) PR indicates the fix was rejected. The report should note this so the user can investigate before re-opening.
- The `days_open` field helps prioritize follow-up on stale PRs.
