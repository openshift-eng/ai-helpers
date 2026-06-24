---
description: Run the 3-phase jira-agent pipeline (solve → review → address-review) for eval.
---

## Name
jira:solve-pipeline

## Synopsis
```
/jira:solve-pipeline <issue_key> <repo_url> <eval_branch>
```

## Description

Runs the full jira-agent pipeline against a snapshot branch for evaluation purposes.
Does NOT create PRs or push code.

## Implementation

Run the pipeline script and wait for it to complete. This is a long-running operation (30-60 minutes).

Execute this exact command, substituting the arguments:

```bash
AI_HELPERS_DIR=$(pwd) WORK_DIR=$(pwd)/eval-output \
  bash plugins/jira/evals/scripts/run-solve-pipeline.sh "$1" "$2" "$3"
```

Do NOT modify the script. Do NOT interpret its output. Do NOT create PRs or push code.

## Arguments
- $1: Jira issue key or URL (required)
- $2: Repository clone URL (required)
- $3: Snapshot branch name (required)
