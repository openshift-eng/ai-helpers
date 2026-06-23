# github

GitHub utilities for image uploads, asset management, and PR automation.

## Skills

### upload-screenshot

Upload screenshots and images to GitHub via release assets, returning stable URLs that can be embedded in PR comments, issue descriptions, and markdown.

Uses the official `gh` CLI release asset API — no browser sessions, cookies, or third-party dependencies required.

### fetch-pr-comments

Fetch all comments from a GitHub PR, filtered to trusted users only (org members + allowed bots). Returns structured JSON with comments from all three GitHub endpoints (inline review, review summaries, PR conversation) plus pre-formatted text ready for Claude prompts. Supports stateful polling via exclude-ids tracking.

### check-pr-ci-status

Check CI status on a GitHub PR and detect new failures since the last check. Returns failing check details and a `has_new_failures` flag for efficient polling loops. Designed to be called repeatedly with the previous iteration's failure list.
