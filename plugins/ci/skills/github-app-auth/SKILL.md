---
name: github-app-auth
description: GitHub App JWT token generation for CI
disable-model-invocation: true
---

# GitHub App Authentication

Shell library for generating short-lived GitHub App installation access tokens via JWT. The script handles the full flow: read credentials, sign a JWT, exchange it for an installation token. This skill exists only as a distribution mechanism — it is sourced by CI process scripts, not invoked by Claude.

## Prerequisites

- `app-id` and `private-key` files in `GITHUB_APP_CREDS_DIR` (default: `/var/run/claude-code-service-account`)
- `openssl`, `curl`, `jq` available on the runner

## Usage

Source the script and call `generate_github_token` with an installation ID:

```bash
source /tmp/ai-helpers/plugins/ci/skills/github-app-auth/github-app-auth.sh

TOKEN=$(generate_github_token "$INSTALLATION_ID")
```

Token goes to stdout, errors to stderr. Non-zero exit on failure.

| Environment Variable | Default | Purpose |
|---|---|---|
| `GITHUB_APP_CREDS_DIR` | `/var/run/claude-code-service-account` | Directory containing `app-id` and `private-key` |
