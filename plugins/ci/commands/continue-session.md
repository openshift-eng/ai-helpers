---
description: Download and continue a Claude session from a Prow CI job's artifacts
argument-hint: <prowjob-url>
---

## Name
ci:continue-session

## Synopsis
```bash
/ci:continue-session <prowjob-url>
```

## Description

Downloads Claude session artifacts from a Prow CI job and allows you to continue one of those sessions locally. This is useful when Claude ran as part of a CI job and you want to pick up where it left off.

The command accepts:
- **prowjob-url** (required): URL to a Prow job run

## Prerequisites

1. **gcloud CLI** — for accessing GCS artifacts
   - Check: `which gcloud`
   - The `test-platform-results` bucket is publicly accessible (no auth needed)

2. **Python 3** (3.6+)
   - Check: `which python3`

3. **tar** — for extracting archives

## Implementation

### Step 1: Search for session archives

Load the `ci:prow-job-artifact-search` skill and use its search operation to find files matching `**/claude-session*.tar*` in the job's artifacts.

Parse the JSON output. If no matches are found (`count: 0`), tell the user "No Claude session archives found in this job's artifacts." and stop.

### Step 2: Download archives to .work directory

Create a working directory:

```bash
mkdir -p .work/continue-session
```

For each matched archive file, download it from GCS using `gcloud storage cp`:

```bash
gcloud storage cp --no-user-output-enabled <gcs_uri> .work/continue-session/
```

### Step 3: Extract archives

For each downloaded archive in `.work/continue-session/`:

```bash
# For .tar.gz files
tar xzf .work/continue-session/<filename>.tar.gz -C .work/continue-session/

# For .tar files (not gzipped)
tar xf .work/continue-session/<filename>.tar -C .work/continue-session/
```

After extraction, the structure contains a `projects/` directory. Each session consists of two parts:
- A JSONL file at `projects/<project-path>/<session-uuid>.jsonl` (the main conversation log)
- A directory at `projects/<project-path>/<session-uuid>/` (containing subagent data and other session state)

Both must be copied together for the session to work.

### Step 4: Discover sessions and extract first user message

Find all session JSONL files (files matching `*.jsonl` under the extracted `projects/` hierarchy). Each `.jsonl` file corresponds to a session, and its filename (without extension) is the session UUID.

For each session JSONL file found:
1. Read the JSONL file line by line
2. Look for the first message with `"type": "user"` that does NOT have `"isMeta": true` — this is the first real user message
3. Extract the text content from `message.content` — it may be a string or an array of content blocks. If it's an array, look for blocks with `"type": "text"` and extract the `text` field.
4. Truncate the message to 120 characters for display purposes
5. Record the session UUID, the full path to the JSONL file, and the truncated first user message

If no sessions are found after extraction, tell the user "No Claude sessions found in the extracted archives." and stop.

### Step 5: Present session list to user

If only one session is found, display its details and confirm with the user before proceeding.

If multiple sessions are found, display a numbered list asking "What session would you like to continue?" with each entry showing:
- The session number
- The session UUID
- The truncated first user message

Example:
```text
What session would you like to continue?

1. [abc12345-...] "Please analyze the test failures in..."
2. [def67890-...] "Can you help fix the flaky e2e test..."
```

Use AskUserQuestion to let the user select a session by number.

### Step 6: Copy selected session to local Claude projects directory

The extracted archive contains sessions under a CI-specific project path (e.g., `projects/-home-prow-go-src-github.com-org-repo/`). This path reflects where the repo was checked out in CI and will not match the local project path.

Determine the **local project path** that Claude uses for the current working directory. Claude's projects directory structure encodes the absolute path of the project by replacing `/` with `-` and stripping the leading slash. For example, if the current working directory is `/Users/stbenjam/git/my-repo`, the local project path is:

```text
~/.claude/projects/-Users-stbenjam-git-my-repo/
```

Compute this by taking `pwd` and replacing all `/` with `-`. Since absolute paths start with `/`, this naturally produces a leading `-`.

Before copying, check if the session UUID already exists locally (either the `.jsonl` file or the directory). If it does, warn the user that a local session with this UUID already exists and ask whether to overwrite it. If the user declines, stop.

Copy both the selected session's JSONL file and its corresponding directory into the local project path:

```bash
# Determine local project path
LOCAL_PROJECT_DIR="$HOME/.claude/projects/$(pwd | tr '/' '-')"
mkdir -p "$LOCAL_PROJECT_DIR"

# Copy the session JSONL file
cp <path-to-extracted>/<session-uuid>.jsonl "$LOCAL_PROJECT_DIR/"

# Copy the session directory (contains subagent data)
cp -r <path-to-extracted>/<session-uuid> "$LOCAL_PROJECT_DIR/"
```

Only the single selected session is copied — do not copy other sessions. Both the `.jsonl` file and the UUID directory must be copied for the session to be resumable.

### Step 7: Report success

Tell the user:

```text
You are all set! You can now continue the session by launching a new Claude:

claude --resume <session-uuid>
```

Where `<session-uuid>` is the UUID of the session they selected.

## Arguments

- **$1** (prowjob-url): URL to a Prow job run (required). Accepts standard Prow UI URLs or gcsweb URLs.
