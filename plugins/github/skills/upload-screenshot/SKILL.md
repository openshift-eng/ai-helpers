---
name: upload-screenshot
description: Upload screenshots or images to GitHub and get back embeddable URLs for PR comments and issues. Use this when you have taken a screenshot, captured a UI change, or have any image file that needs to be shared in a GitHub PR or issue.
---

# Upload Screenshot

Upload images to GitHub via release assets and get back stable, embeddable URLs. This is the recommended way to share screenshots of frontend changes, UI diffs, or any visual artifacts in PR comments and issue descriptions.

**Important:** Always upload to the **fork** repo, not upstream, to avoid polluting upstream releases.

## When to Use This Skill

Use this skill when you:

- Have taken a screenshot of a frontend/UI change and need to show it in a PR
- Need to attach visual evidence (error screenshots, UI comparisons) to a GitHub issue or PR comment
- Want to embed an image in any GitHub markdown context (PR description, comment, issue)
- Are working in an agentic workflow and need to share visual output

## Prerequisites

1. **`gh` CLI**: Authenticated with `gh auth login`
2. **Repository write access**: The `gh` token must have permission to create releases on the target repo

## Implementation

### Upload a screenshot

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/upload-screenshot/upload_screenshot.sh" \
  --file /path/to/screenshot.png \
  --repo owner/fork-repo
```

### Upload with a custom title

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/upload-screenshot/upload_screenshot.sh" \
  --file /path/to/screenshot.png \
  --repo owner/fork-repo \
  --title "Login page after dark mode changes"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--file`       | Yes      | Path to the image file (png, jpg, gif, svg, webp) |
| `--repo`       | No       | Target GitHub repository in `owner/repo` format (defaults to `$FORK_REPO` env var) |
| `--title`      | No       | Alt text for the image (defaults to filename) |
| `--token-file` | No       | Path to a file containing a GitHub token to use for auth |

When `--token-file` is provided, the token is loaded into `GITHUB_TOKEN` for the duration of the script. This is useful in CI where the default `GITHUB_TOKEN` may not have write access to the target repo.

**Environment variable defaults:** If `--repo` is not provided, the script uses `$FORK_REPO`. If no explicit token is provided via `--token-file`, the script uses `$GH_FORK_TOKEN` when available. This means in CI environments where these env vars are set, you can call the script with just `--file` and it will upload to the correct fork with the right credentials.

### Output

JSON on stdout:

```json
{
  "url": "https://github.com/owner/fork-repo/releases/download/screenshot-1719100000-a1b2c3d4/screenshot.png",
  "markdown": "![Login page](https://github.com/owner/fork-repo/releases/download/screenshot-1719100000-a1b2c3d4/screenshot.png)",
  "tag": "screenshot-1719100000-a1b2c3d4",
  "repo": "owner/fork-repo"
}
```

### Embedding in a PR comment

After uploading, use the `markdown` field directly in a `gh pr comment`:

```bash
result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/upload-screenshot/upload_screenshot.sh" \
  --file /tmp/screenshot.png --repo owner/fork-repo --title "UI change")

markdown=$(echo "$result" | jq -r '.markdown')
gh pr comment 123 --repo owner/upstream-repo --body "## Screenshot

$markdown"
```

## How It Works

1. Creates a GitHub prerelease with a unique tag (`screenshot-<timestamp>-<random>`)
2. Attaches the image file as a release asset
3. Extracts the `browser_download_url` from the GitHub API
4. Returns the URL in both raw and markdown-formatted forms

The release is marked as a prerelease and tagged with a `screenshot-` prefix for easy identification and cleanup.

## Cleanup

Screenshot releases accumulate over time. To clean up old uploads:

```bash
# Delete a specific screenshot release
gh release delete screenshot-1719100000-a1b2c3d4 --yes --cleanup-tag --repo owner/fork-repo

# Delete all screenshot releases older than 30 days
gh api "repos/owner/fork-repo/releases" --paginate --jq \
  '.[] | select(.tag_name | startswith("screenshot-")) | select(.prerelease) | .tag_name' | \
  while read -r tag; do
    gh release delete "$tag" --yes --cleanup-tag --repo owner/fork-repo
  done
```

## Limitations

- URLs are only accessible as long as the release exists
- For private repos, viewers must have repo access to see the images
- GitHub release asset size limit is 2 GB per file
- Creates one release per upload (use cleanup to manage volume)

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `Missing required arguments` | `--file` or `--repo` not provided | Provide both required arguments |
| `File not found` | Image path doesn't exist | Check the file path |
| `Failed to create release` | Auth or permission issue | Run `gh auth login` or check repo access |
| `Failed to retrieve asset URL` | Release created but asset missing | Retry; the release is auto-cleaned on failure |

## See Also

- GitHub Releases API: https://docs.github.com/en/rest/releases
- `gh release create` docs: https://cli.github.com/manual/gh_release_create
