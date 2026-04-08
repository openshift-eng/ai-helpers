---
description: Find and verify Konflux-built container images from a GitHub PR
argument-hint: "<PR-URL>"
---

## Name

utils:find-konflux-images

## Synopsis

/utils:find-konflux-images <PR-URL>

## Description

Given a PR in any Konflux-enabled repository, find all Konflux/Tekton pipeline-built container images, check their availability on quay.io, and report the results. Works with any repository that has `.tekton/` pipeline configurations.

### Usage Example

`/utils:find-konflux-images https://github.com/org/repo/pull/123`

### Arguments

- **$ARGUMENTS** *(required)*: A full GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`). Extract org, repo, and PR number from the URL.

## Implementation

The command executes the following workflow:

### 1. Resolve the PR

Use `gh pr view <PR> --json headRefOid,baseRefName,state` to get:
- The commit SHA (`headRefOid`)
- The base branch (`baseRefName`) — shown in the output for context
- The PR state (`state`) — used to determine if retrigger is possible

### 2. Find the pull-request pipeline templates

Look in the `.tekton/` directory at the PR's head commit for `*-pull-request.yaml` files. Read each one and extract the `output-image` value, which contains the image URL pattern with `{{revision}}` placeholder.

Use the GitHub API to fetch from the PR's commit SHA directly (not the base branch), so results are accurate even if the PR modifies `.tekton/` files:

```bash
PR_FILES=$(gh api "repos/${REPO}/contents/.tekton?ref=${COMMIT_SHA}" \
  --jq '.[] | select(.type=="file" and (.name | endswith("-pull-request.yaml"))) | .name')

for file in $PR_FILES; do
  CONTENT=$(gh api "repos/${REPO}/contents/.tekton/${file}?ref=${COMMIT_SHA}" --jq '.content' | base64 -d)
  IMAGE_PATTERN=$(echo "$CONTENT" | grep -A1 'name: output-image' | grep 'value:' | head -1 | sed 's/.*value: *//')
  COMPONENT=$(echo "$file" | sed 's/-pull-request\.yaml$//')
done
```

### 3. Check which Konflux builds were triggered

```bash
gh pr checks ${PR_NUMBER} --repo ${REPO} --json name,state \
  --jq '.[] | select(.name | test("-on-pull-request$")) | .name'
```

Use structured output to identify image-build checks consistently. The `enterprise-contract` checks are verification-only.

### 4. Verify image availability and get expiration date from quay.io

**Only check images for triggered pipelines.** Skip quay.io lookup for untriggered components — report them directly as NOT TRIGGERED.

For each triggered component, replace `{{revision}}` in the `IMAGE_PATTERN` extracted from step 2 with the commit SHA to get the full image URL. Then parse the repo path and tag from it to query the quay.io tag API:

```bash
# Derive the full image URL from IMAGE_PATTERN
FULL_IMAGE=$(echo "$IMAGE_PATTERN" | sed "s/{{revision}}/${COMMIT_SHA}/g")
# Parse: quay.io/<REPO_PATH>:<TAG>
REPO_PATH=$(echo "$FULL_IMAGE" | sed 's|quay.io/||' | sed 's|:.*||')
TAG=$(echo "$FULL_IMAGE" | sed 's|.*:||')

# Query the quay.io tag API — returns availability, creation time, and expiration date
TAG_INFO=$(curl --fail --silent --show-error --max-time 15 \
  "https://quay.io/api/v1/repository/${REPO_PATH}/tag/?specificTag=${TAG}") \
  || { echo "ERROR: Unable to reach quay.io registry API."; exit 1; }
# Parse the response:
#   - tags[0].expiration: exact expiration date (e.g., "Sun, 22 Mar 2026 21:22:50 -0000")
#   - tags[0].start_ts: creation timestamp
#   - empty tags array means image not found (never built or already expired/garbage-collected)
```

Use `tags` array length to determine availability (non-empty = found). Extract the `expiration` field for the exact expiry date. Format it as a short date (e.g., `2026-03-22`).

**Important:** Compare the expiration timestamp against the current time (UTC). The quay.io tag API may still return tags after they have expired (before garbage collection). If the expiration date is in the past, mark the image as **EXPIRED** — it is no longer pullable even though the API still returns it.

### 5. Present results

Present results as a Markdown table:

| Component | Status | Expiration | Image URL |
|---|---|---|---|
| my-component | AVAILABLE | 2026-04-05 | `quay.io/redhat-user-workloads/...` |
| my-other-component | EXPIRED | 2026-03-20 | -- |
| optional-component | NOT TRIGGERED | -- | -- |

- **AVAILABLE**: Tag found in quay.io and expiration date is in the future — image is pullable
- **EXPIRED**: Tag found in quay.io but expiration date is in the past — image is no longer pullable
- **NOT FOUND**: Tag not found in quay.io (build failed or image already garbage-collected)
- **NOT TRIGGERED**: Pipeline was not triggered for this PR (file changes didn't match the CEL filter)
- Only show the full image URL when the status is AVAILABLE
- Show `--` in the Image URL and Expiration columns when the image is not available
- Show the base branch name (e.g., `main`, `release-4.21`)

### 6. Offer to retrigger expired images

If any triggered images are EXPIRED or NOT FOUND, and the PR is still open, offer to retrigger by commenting `/retest` on the PR:

```bash
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/retest"
```

**Key facts about `/retest`:**
- **Prow** treats `/retest` as "rerun only failed jobs" — if all Prow jobs pass, Prow does nothing
- **Konflux (Pipelines as Code)** treats `/retest` as "rerun all pipeline runs" — it rebuilds all images
- This means `/retest` is safe to use for rebuilding expired Konflux images without re-running passing Prow jobs
- Builds typically take 10-20 minutes; re-run this command to check availability afterward

## Error Handling

| Scenario | Action |
|----------|--------|
| PR not found | Show error with PR number |
| No .tekton/ directory | `ERROR: No .tekton/ directory found. This repo may not use Konflux.` |
| No pull-request configs found | `ERROR: No pull-request Tekton pipeline configs found in .tekton/.` |
| quay.io API unreachable | `ERROR: Unable to reach quay.io registry API.` |
| Image expired (tag exists but past expiration) | Report as EXPIRED with the expiration date, show `--` in Image URL column, offer to retrigger via `/retest` if PR is still open |
| Image gone (tag not found) | Report as NOT FOUND, show `--` in both Expiration and Image URL columns, offer to retrigger via `/retest` if PR is still open |
| PR is closed/merged | Do not offer retrigger; note that images can only be rebuilt on open PRs |

## Important Notes

- PR images have an expiration date set by quay.io. Query the tag API to get the exact expiry date per image.
- For EXPIRED images (tag exists but expiration is in the past), show the expiration date but `--` in the Image URL column.
- For NOT FOUND images (not triggered or already garbage-collected), show `--` in both Expiration and Image URL columns.
- Expired images can be rebuilt by commenting `/retest` on the PR (only works if PR is still open)
- Image URL patterns **vary between components** — always read from the Tekton config
- Not all pipelines trigger on every PR — each has a CEL expression filtering on changed file paths

## Requirements

- `gh` CLI authenticated with access to the target repository
- `curl` available
