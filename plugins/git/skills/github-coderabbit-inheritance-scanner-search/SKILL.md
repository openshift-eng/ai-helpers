---
name: CodeRabbit Inheritance Scanner - Search
description: Search for repos with .coderabbit.yaml files in the openshift GitHub org
---

# CodeRabbit Inheritance Scanner - Search

This skill searches the `openshift` GitHub organization for repositories containing `.coderabbit.yaml` or `.coderabbit.yml` files using the GitHub code search API.

## When to Use This Skill

Use this skill as Step 1 of the `/git:github-coderabbit-inheritance-scanner` command.

## Procedure

Run the following bash script to search for repos. This uses GitHub code search to avoid iterating all ~800 repos individually.

```bash
ALL_REPOS=""

for FILENAME in .coderabbit.yaml .coderabbit.yml; do
  PAGE=1
  while true; do
    RESULT=$(gh api -X GET "search/code" \
      -f "q=filename:${FILENAME} org:openshift" \
      -f "per_page=100" \
      -f "page=${PAGE}" \
      --jq '.items[] | .repository.full_name' 2>/dev/null)
    if [ -z "$RESULT" ]; then
      break
    fi
    ALL_REPOS="${ALL_REPOS}${RESULT}"$'\n'
    COUNT=$(echo "$RESULT" | wc -l | xargs)
    if [ "$COUNT" -lt 100 ]; then
      break
    fi
    PAGE=$((PAGE + 1))
    sleep 1
  done
  sleep 2
done

# Deduplicate, sort, exclude openshift/coderabbit
echo "$ALL_REPOS" | sort -u | grep -v '^$' | grep -v '^openshift/coderabbit$'
```

## Output

A newline-separated list of `org/repo` names (e.g., `openshift/api`), excluding `openshift/coderabbit`.

## Error Handling

If the code search API is unavailable or returns an error (e.g., due to authentication scope), inform the user that the search failed and suggest checking `gh auth status`.
