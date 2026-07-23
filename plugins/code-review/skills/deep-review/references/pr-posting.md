# Phase 6 — Post to PR

This phase runs ONLY when `--comment` was passed with a PR identifier.

Before posting, confirm repository coordinates from Step 1.2:

- **GitHub:** `$OWNER`, `$REPO`, `$PR_NUMBER` must be set
- **GitLab:** `$PROJECT`, `$MR_IID` must be set

If any required value is missing, derive it from the PR/MR URL or
the matching git remote (`git remote -v`) before continuing. Capture
any created review ID as `$REVIEW_ID` for later submit/drop steps.

## Step 6.1: Post as comment

Post the full verdict as a PR comment:

**GitHub:**
```bash
gh pr comment "$PR_NUMBER" --repo "$OWNER/$REPO" --body "$(cat <<'EOF'
<verdict content>
EOF
)"
```

**GitLab:**
```bash
glab mr note "$MR_IID" --repo "$PROJECT" --message "$(cat <<'EOF'
<verdict content>
EOF
)"
```

If the comment fails, report the error but still display the verdict
to the user — the review itself is not lost.

## Step 6.2: Offer inline review (GitHub only)

After posting the comment, offer to also create a PENDING review
with inline comments on specific lines:

**Ask the user**: "Want me to also add inline review comments?
(yes / no)"

If the user says no, stop here.

If yes, compute diff positions and create the review:

**GitHub position rules:**
- The `position` is the 1-based line index in the file's unified
  diff, where position 1 is the first line AFTER the first `@@`
  hunk header. `@@` headers are NOT counted.
- Count every line (context, additions, deletions) sequentially
  across ALL hunks. Each new `@@` header is skipped in the count.
- The count does NOT reset between hunks

If a finding's line falls outside any diff hunk, skip the inline
comment and include it in the review body instead.

**CRITICAL**: Do NOT include an `"event"` field in the JSON payload.
Omitting it creates a PENDING review.

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  --input /tmp/deep-review-payload.json
```

Capture the created review id:

```bash
REVIEW_ID=$(jq -r '.id' < /tmp/deep-review-response.json)
```

Cap at **30 inline comments**. Overflow goes to the review body.

### Inline comment format

**For BLOCKING findings with a confirmed reproducer:**
```markdown
**Bug: {title}**

{body}

Fix: {suggestion}

<details>
<summary>Reproducer</summary>

**Steps:** {steps}

**Expected:** {expected}

**Actual:** {actual}
</details>
```

**For findings where the reproducer failed:**
```markdown
**Potential: {title}**

{body}

Note: A reproducer was attempted but did not confirm this bug.
Manual verification recommended.
```

**For SUGGESTION/NOTE findings:**
```markdown
**{Severity}: {title}**

{body}

Suggestion: {suggestion}
```

## Step 6.3: User approval gate

```text
PENDING review created with N inline comments on PR #NNN.

Commands:
  "submit"           — post as informational comment
  "request changes"  — post requesting changes
  "drop"             — delete the pending review
```

**Do NOT submit automatically. Wait for the user.**

On "submit":
```bash
gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID/events" \
  --method POST -f event="COMMENT"
```

On "request changes":
```bash
gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID/events" \
  --method POST -f event="REQUEST_CHANGES"
```

On "drop":
```bash
gh api -X DELETE "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID"
```
