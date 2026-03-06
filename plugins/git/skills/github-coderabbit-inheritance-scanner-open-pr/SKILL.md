---
name: CodeRabbit Inheritance Scanner - Open PR
description: Fork, sync, and open a fix PR to add inheritance: true to a repo's .coderabbit.yaml
---

# CodeRabbit Inheritance Scanner - Open PR

This skill handles the complete workflow of opening a pull request to add `inheritance: true` to a repository's `.coderabbit.yaml` file. It always operates via a personal fork to avoid needing direct push access to upstream repos.

## When to Use This Skill

Use this skill as Step 6 of the `/git:github-coderabbit-inheritance-scanner` command, after the user has confirmed they want to open PRs. Call it once per non-compliant repo that does not already have an open fix PR.

**Do NOT call this skill in `--dry-run` mode.** Instead, display the actions that would be taken for each repo.

## Prerequisites

- `gh` CLI authenticated with `repo` scope
- `workflow` scope is needed if the upstream repo contains GitHub Actions workflow files (for `gh repo sync`). If missing, the skill will skip the repo with a warning.

## Procedure

For each repo that needs a fix PR, run the following. The variables `REPO` (e.g., `openshift/api`), `DEFAULT_BRANCH` (e.g., `master` or `main`), and `CFGFILE` (e.g., `.coderabbit.yaml`) must be set.

```bash
# Derive names
REPO_NAME="${REPO##*/}"
GH_USER=$(gh api user --jq '.login')
WORKDIR="/tmp/cr-fix-workdir/${REPO_NAME}"
BRANCH_NAME="add-coderabbit-inheritance"

echo "Processing: ${REPO}"

# Step 1: Fork the repo (idempotent - safe to call if fork exists)
gh repo fork "${REPO}" --clone=false 2>&1 || true
sleep 2

# Step 2: Sync the fork's default branch with upstream
SYNC_OUTPUT=$(gh repo sync "${GH_USER}/${REPO_NAME}" --source "${REPO}" --branch "${DEFAULT_BRANCH}" 2>&1)
SYNC_EXIT=$?
if [ $SYNC_EXIT -ne 0 ]; then
  if echo "$SYNC_OUTPUT" | grep -q "workflow"; then
    echo "SKIP|${REPO}|Fork sync failed: workflow scope required. Run: gh auth refresh -h github.com -s workflow"
    # Continue to next repo in the calling loop
    return 1 2>/dev/null || continue
  fi
  echo "SKIP|${REPO}|Fork sync failed: ${SYNC_OUTPUT}"
  return 1 2>/dev/null || continue
fi

# Step 3: Delete any stale branch from a previous run
gh api -X DELETE "repos/${GH_USER}/${REPO_NAME}/git/refs/heads/${BRANCH_NAME}" 2>/dev/null || true
sleep 1

# Step 4: Clone the fork and create the fix branch
rm -rf "${WORKDIR}"
gh repo clone "${GH_USER}/${REPO_NAME}" "${WORKDIR}" -- -b "${DEFAULT_BRANCH}" --depth 1 2>&1
cd "${WORKDIR}"
git checkout -b "${BRANCH_NAME}" 2>&1

# Step 5: Add inheritance: true to the config file
if [ ! -f "${CFGFILE}" ]; then
  echo "ERROR|${REPO}|Config file ${CFGFILE} not found in cloned repo"
  cd /tmp
  return 1 2>/dev/null || continue
fi

if ! grep -q 'inheritance:' "${CFGFILE}"; then
  # Prepend inheritance: true as the first line
  printf 'inheritance: true\n' | cat - "${CFGFILE}" > "${CFGFILE}.tmp" && mv "${CFGFILE}.tmp" "${CFGFILE}"
else
  # Replace existing inheritance: false with true
  sed -i.bak 's/^\(\s*\)inheritance:\s*false/\1inheritance: true/' "${CFGFILE}" && rm -f "${CFGFILE}.bak"
fi

# Step 6: Commit and push
git add "${CFGFILE}"
git commit -m "$(cat <<'COMMITEOF'
Add inheritance: true to .coderabbit.yaml

Ensures this repo inherits the org-wide CodeRabbit review rules
defined in https://github.com/openshift/coderabbit
COMMITEOF
)" 2>&1

git push origin "${BRANCH_NAME}" 2>&1

# Step 7: Create the PR from fork to upstream
PR_URL=$(gh pr create \
  --repo "${REPO}" \
  --head "${GH_USER}:${BRANCH_NAME}" \
  --base "${DEFAULT_BRANCH}" \
  --title "Add CodeRabbit inheritance for org-wide rules" \
  --body "$(cat <<'BODYEOF'
Adds `inheritance: true` to `.coderabbit.yaml` so this repo inherits the org-wide review rules from [openshift/coderabbit](https://github.com/openshift/coderabbit).

Without this setting, the repo's custom `.coderabbit.yaml` overrides the org-level configuration entirely, meaning org-wide review instructions and path-based rules are not applied.
BODYEOF
)" 2>&1)

cd /tmp

if echo "$PR_URL" | grep -q "https://github.com"; then
  echo "OK|${REPO}|${PR_URL}"
else
  echo "ERROR|${REPO}|PR creation failed: ${PR_URL}"
fi

sleep 1
```

## Output Format

Pipe-separated fields per line:

```
STATUS|org/repo|detail
```

Where STATUS is one of:
- `OK` - PR created successfully; detail is the PR URL
- `SKIP` - Repo was skipped; detail is the reason (e.g., missing workflow scope)
- `ERROR` - An error occurred; detail is the error message

## Dry Run Output

When `--dry-run` is active, do NOT execute this skill. Instead, for each repo that would get a PR, display:

```
[DRY RUN] openshift/<repo>:
  1. Fork openshift/<repo> (or use existing fork)
  2. Sync fork's <default_branch> with upstream
  3. Create branch: add-coderabbit-inheritance
  4. Prepend "inheritance: true" to <config_file>
  5. Push branch to fork
  6. Open PR: "Add CodeRabbit inheritance for org-wide rules"
     From: <user>:add-coderabbit-inheritance -> openshift/<repo>:<default_branch>
```

## Notes

- The fork operation is idempotent - `gh repo fork` will not fail if the fork already exists.
- The stale branch deletion (Step 3) ensures a clean state if the command was previously run and the PR was closed without merging.
- macOS `sed -i` requires a backup extension; the `.bak` file is cleaned up.
- The `WORKDIR` under `/tmp/cr-fix-workdir/` is cleaned up before each clone to ensure fresh state.
