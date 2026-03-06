---
name: CodeRabbit Inheritance Scanner - Check
description: Check a repo's .coderabbit.yaml for inheritance: true
---

# CodeRabbit Inheritance Scanner - Check

This skill checks a single repository's `.coderabbit.yaml` (or `.coderabbit.yml`) to determine whether `inheritance: true` is set.

## When to Use This Skill

Use this skill as Step 2 of the `/git:github-coderabbit-inheritance-scanner` command. Call it once per repo found by the search skill. Multiple repos can be checked in a single bash invocation using the batch procedure below.

## Procedure

For a batch of repos stored in a bash array, run the following to classify each one:

```bash
# Input: REPOS array of "org/repo" strings
# Output: prints classification and default branch for each repo

for REPO in "${REPOS[@]}"; do
  CONTENT=""
  CFGFILE=""
  for FILENAME in .coderabbit.yaml .coderabbit.yml; do
    CONTENT=$(gh api "repos/${REPO}/contents/${FILENAME}" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null)
    if [ -n "$CONTENT" ]; then
      CFGFILE="$FILENAME"
      break
    fi
  done

  # Get default branch for link generation
  DEFAULT_BRANCH=$(gh api "repos/${REPO}" --jq '.default_branch' 2>/dev/null)

  if [ -z "$CONTENT" ]; then
    echo "ERROR|${REPO}|${DEFAULT_BRANCH}|${CFGFILE}"
    continue
  fi

  if echo "$CONTENT" | grep -qE '^\s*inheritance:\s*true'; then
    echo "COMPLIANT|${REPO}|${DEFAULT_BRANCH}|${CFGFILE}"
  elif echo "$CONTENT" | grep -qE '^\s*inheritance:\s*false'; then
    echo "FALSE|${REPO}|${DEFAULT_BRANCH}|${CFGFILE}"
  else
    echo "MISSING|${REPO}|${DEFAULT_BRANCH}|${CFGFILE}"
  fi

  sleep 0.3
done
```

## Output Format

Pipe-separated fields per line:

```
STATUS|org/repo|default_branch|config_filename
```

Where STATUS is one of:
- `COMPLIANT` - `inheritance: true` is set
- `FALSE` - `inheritance: false` is explicitly set
- `MISSING` - the `inheritance` key is absent
- `ERROR` - could not fetch the file
