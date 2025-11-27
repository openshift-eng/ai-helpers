---
name: PR Retest Wrapper Script
description: Wrapper script that combines e2e and payload retest functionality for comprehensive PR CI analysis
---

# PR Retest Wrapper Script

This skill provides a bash wrapper script that powers the `/ci:pr-retest` command. It orchestrates both e2e and payload job analysis by invoking the e2e-retest and payload-retest scripts sequentially.

## When to Use This Skill

This skill is automatically invoked by the `/ci:pr-retest` command. You typically don't need to call this script directly.

## Components

### 1. `pr-retest.sh`
Wrapper script that:
- Invokes `e2e-retest.sh` from the e2e-retest skill
- Invokes `payload-retest.sh` from the payload-retest skill
- Passes all arguments transparently to both scripts
- Provides clear section separators in output

**Usage:**
```bash
./pr-retest.sh [repo] <pr-number>
```

**What it does:**
1. Displays "E2E JOBS" header
2. Runs `../e2e-retest/e2e-retest.sh` with provided arguments
3. Displays "PAYLOAD JOBS" header
4. Runs `../payload-retest/payload-retest.sh` with provided arguments

## Implementation Details

### Script Orchestration
The wrapper uses `set -euo pipefail` to ensure:
- Exits on any command failure
- Treats unset variables as errors
- Catches failures in pipelines

### Path Resolution
Script locates sibling skill directories using:
```bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
```

This ensures correct paths regardless of where the script is invoked from.

### Output Organization
Clear section headers help distinguish between e2e and payload results:
```
=========================================
E2E JOBS
=========================================
[e2e-retest output]

=========================================
PAYLOAD JOBS
=========================================
[payload-retest output]
```

## Prerequisites

Same as the underlying skills:
- `gh` CLI (GitHub CLI)
- `jq` (JSON processor)
- `curl`
- Authenticated with GitHub (`gh auth login`)

Plus:
- `e2e-retest` skill scripts must exist in `../e2e-retest/`
- `payload-retest` skill scripts must exist in `../payload-retest/`

## Repository Detection

The wrapper transparently passes repository arguments to both underlying scripts:
- **No argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>`
- **Full org/repo**: Use any GitHub repository

## Notes

- This is a simple orchestration wrapper with no complex logic
- All analysis and interaction is delegated to the underlying skills
- If either e2e or payload analysis fails, the script exits immediately (due to `set -e`)
- Total execution time is the sum of both analyses (~10-15 seconds)
