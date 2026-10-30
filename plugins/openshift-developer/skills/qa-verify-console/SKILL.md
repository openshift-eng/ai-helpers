---
name: qa-verify-console
description: Capture before/after screenshots of OpenShift Console PRs running against a live cluster using Puppeteer, generate visual diff comparisons, and post evidence to the PR. Use when a Console PR needs visual QA verification or screenshot-based regression testing.
---

# qa-verify-console — Visual QA Verification for OpenShift Console PRs

## Overview

This skill captures before/after screenshots of an OpenShift Console PR running
against a live cluster, generates flicker GIFs to highlight visual differences,
and posts evidence to the PR. It enables rapid visual QA without manual browser
testing.

> **"Agent"** throughout this document refers to the Claude Code agent executing
> the skill — the LLM-driven process that runs commands, makes decisions about
> which routes to capture, and interprets results.

> **Post-PR design:** This skill operates on an already-published pull request.
> It requires a valid PR number so it can fetch both the head and base branches,
> read the diff to identify affected routes, and post evidence back as a PR
> comment. It is not designed for pre-PR / local-branch workflows.

The agent:
1. Clones `openshift/console`, builds both the base and PR branches
2. Runs the console bridge (dev server) against a real OCP cluster
3. Uses Puppeteer to capture screenshots of affected routes
4. Compares baseline vs candidate screenshots and posts evidence to the PR

---

## Prerequisites

| Dependency       | Minimum Version | Notes                                      |
|------------------|----------------|--------------------------------------------|
| Node.js          | 22+            | Required by console's frontend build       |
| Corepack         | (bundled)      | Must be enabled: `corepack enable`         |
| Yarn Berry       | 4.x            | Managed via corepack, `.yarnrc.yml` in repo |
| Go               | 1.25+          | Required for backend (bridge) build        |
| `oc`             | 4.x            | OpenShift CLI for cluster access           |
| `gh`             | 2.99+          | GitHub CLI for PR metadata + comment posting|
| `git`            | 2.x            | Full clone required (both branches needed) |
| Chrome/Chromium  | 120+           | Installed by Puppeteer; system libs needed |

### Recommended Pod Resources

```
CPU:               8 cores
Memory:            16Gi
Ephemeral Storage: 40Gi
```

The console frontend build (`yarn install --immutable && yarn run build`) is
CPU- and memory-intensive. The Go backend build is lighter but still benefits
from multiple cores.

---

## Inputs

The agent receives two inputs:

1. **PR number** — The `openshift/console` pull request to verify (e.g., `17199`)
2. **OC login command** — A full `oc login` command string with token and server
   URL, passed explicitly as the `OC_LOGIN_CMD` environment variable. This is
   not an ambient kubeconfig assumption — the caller must provide a complete
   `oc login --token=... --server=...` command that the script `eval`s to
   authenticate against the target cluster.

Optional:

3. **Routes** — Comma-separated list of console routes to capture. If not
   provided, the agent analyzes the PR diff to determine affected routes.

---

## Evidence Directory Layout

```
/workspace/evidence/
  baseline/           # Screenshots from the base branch
    overview.png
    k8s_cluster_nodes.png
    ...
  candidate/          # Screenshots from the PR branch
    overview.png
    k8s_cluster_nodes.png
    ...
  flicker/            # Animated GIFs showing differences
    overview.gif
    k8s_cluster_nodes.gif
    ...
  metadata.json       # PR metadata (branches, author, etc.)
  baseline.json       # Capture summary for baseline
  candidate.json      # Capture summary for candidate
```

---

## Phases

### Phases 0–1 — Validate Inputs & Setup Environment

Fully automated by `scripts/setup.sh` — the agent just runs it and checks the
exit code. No LLM decisions needed.

```bash
OC_LOGIN_CMD="oc login --token=... --server=..." \
  bash /workspace/qa-verify-console/scripts/setup.sh "$PR_NUMBER"
```

On success (`exit 0`), the script produces:
- `/workspace/evidence/metadata.json` — PR metadata
- `/workspace/console/` — cloned repo with `base-branch` checked out and
  `pr-branch` available
- `/workspace/evidence/setup-env.sh` — sourceable env vars (`LD_LIBRARY_PATH`,
  `CHROME_BIN`, `QA_TOOLS_DIR`, branch refs)

The agent should `source /workspace/evidence/setup-env.sh` before proceeding.

On failure (non-zero exit), `setup.sh` prints a descriptive error to stderr.
The agent should report the error and stop.

---

### Phase 2 — Determine Routes & Capture Baseline

**Goal:** Decide which console routes to screenshot, then build the base branch
and capture them.

**Agent decisions (LLM judgement required):**

1. **Route selection** — Analyze the PR diff (`gh pr diff "$PR_NUMBER"`) to
   determine which console routes are visually affected by the changes.
   Consider:
   - Which React components are modified and what routes render them
   - Whether the change is cosmetic (CSS/layout) vs. behavioral
   - Common route patterns:
     - `/` (overview/dashboard)
     - `/k8s/cluster/nodes`, `/k8s/cluster/projects`
     - `/k8s/ns/<namespace>/pods`
     - `/monitoring/alerts`, `/settings/cluster`
   - If the diff doesn't clearly map to routes, ask the user

2. **Failure triage** — If the build or bridge fails, read the error log and
   decide whether the failure is environmental (retry/report) or a real issue.

**Mechanical steps** (run these; no decisions needed):

```bash
cd /workspace/console && ./build.sh                       # Build backend + frontend
export BRIDGE_USER_AUTH="disabled"                         # Required for headless mode
source ./contrib/oc-environment.sh                         # Sets BRIDGE_K8S_AUTH_BEARER_TOKEN
nohup ./bin/bridge -branding openshift > /tmp/bridge-baseline.log 2>&1 &
# Wait for HTTP 200 on localhost:9000, then capture:
# NOTE: Replace the example routes below with the routes you selected from PR diff analysis in Phase 2.
node /workspace/qa-verify-console/scripts/capture-screenshots.js \
  --routes "/" --routes "/k8s/cluster/nodes" \
  --output-dir /workspace/evidence/baseline \
  --base-url http://localhost:9000
# Kill bridge after capture
```

Save the JSON summary to `/workspace/evidence/baseline.json`.

---

### Phase 3 — Capture Candidate (PR Branch)

**Goal:** Switch to the PR branch, rebuild, and capture the same routes.

**Agent decisions:** None — use the same route list from Phase 2. The only
judgement call is **failure triage**: if the PR branch fails to build, that
likely indicates a real issue with the PR (report it rather than retrying).

**Mechanical steps:**

```bash
cd /workspace/console && git checkout pr-branch
./build.sh
export BRIDGE_USER_AUTH="disabled"
source ./contrib/oc-environment.sh
nohup ./bin/bridge -branding openshift > /tmp/bridge-candidate.log 2>&1 &
# Wait for HTTP 200, then capture same routes as Phase 2
node /workspace/qa-verify-console/scripts/capture-screenshots.js \
  --routes "/" --routes "/k8s/cluster/nodes" \
  --output-dir /workspace/evidence/candidate \
  --base-url http://localhost:9000
# Kill bridge after capture
```

Save the JSON summary to `/workspace/evidence/candidate.json`.

---

### Phase 4 — Compare Results & Publish Evidence

**Goal:** Generate visual comparisons and post evidence to the PR.

**Agent decisions (LLM judgement required):**

1. **Interpret visual differences** — Compare baseline vs. candidate screenshots
   (file size deltas, visual inspection). Decide which routes show meaningful
   visual changes (>5% file size difference is a useful heuristic) vs. noise.

2. **Compose the PR comment** — Summarize what changed visually, highlight
   routes with significant differences, and note any routes that failed to
   capture. Use console's `build-comment-attach.sh` if available, otherwise
   fall back to `gh pr comment` with embedded image links.

3. **Handle partial results** — If some screenshots are missing or GIF
   generation fails, decide what to include in the report and what to note as
   skipped. Post what is available rather than failing entirely.

**Mechanical steps:**

- Generate flicker GIFs for each baseline/candidate pair (use console's
  `make-flicker-gif.sh` if available, otherwise `convert -delay 100 -loop 0`)
- Upload images via `stage-attachments.sh` if available
- Post the PR comment via `gh pr comment`
- Store evidence summaries in the result store for coordinator access

---

## Error Handling Reference

| Error                              | Phase | Action                                     |
|------------------------------------|-------|--------------------------------------------|
| Missing PR_NUMBER                  | 0     | Exit with usage message                    |
| Missing OC_LOGIN_CMD               | 0     | Exit with credentials request              |
| `oc login` fails                   | 0     | Exit with cluster connectivity error       |
| PR not found                       | 0     | Exit with PR number validation error       |
| `git clone` fails                  | 1     | Exit with network/auth error               |
| PR branch fetch fails              | 1     | Exit with branch not found error           |
| Chrome lib download fails          | 1     | Warn, continue (may still work)            |
| Puppeteer install fails            | 1     | Exit with Node.js/npm error                |
| `./build.sh` fails                 | 2/3   | Exit with build error log                  |
| Bridge won't start                 | 2/3   | Check log, exit with bridge error          |
| Bridge returns errors              | 2/3   | Check bearer token, exit with auth error   |
| Single screenshot fails            | 2/3   | Skip route, mark as skipped, continue      |
| All screenshots fail               | 2/3   | Exit with capture error                    |
| GIF generation fails               | 4     | Skip GIFs, post screenshots only           |
| PR comment posting fails           | 4     | Store locally, report to coordinator       |

---

## Reused Scripts from Console Repo

After cloning `openshift/console`, these scripts are available under
`.claude/skills/qa-verify/scripts/`:

| Script                     | Purpose                                         |
|----------------------------|--------------------------------------------------|
| `backend.sh`               | Build backend only (Go)                         |
| `rebuild.sh`               | Incremental rebuild                              |
| `build-comment-attach.sh`  | Post comment with attachments to PR              |
| `stage-attachments.sh`     | Upload images for PR comment embedding           |
| `make-flicker-gif.sh`      | Generate before/after flicker GIF                |
| `check-prerequisites.sh`   | Verify system dependencies                       |

These scripts may or may not exist depending on the console version. The agent
should check for their existence before using them and fall back to inline
equivalents.

---

## Usage Example

```
User: "Run QA verification on console PR #17199"

Agent:
1. Receives PR_NUMBER=17199, OC_LOGIN_CMD from environment
2. Runs setup.sh 17199
3. Analyzes PR diff → affected routes: /, /k8s/cluster/nodes, /monitoring/alerts
4. Builds base branch, captures 3 baseline screenshots
5. Switches to PR branch, rebuilds, captures 3 candidate screenshots
6. Generates 3 flicker GIFs
7. Posts comment to PR #17199 with evidence
```

---

## Limitations

1. **No dynamic plugins** — The dev bridge does not load OLM-installed console
   plugins. Pages that depend on dynamic plugins will show plugin-not-found
   states.

2. **Auth-disabled mode** — `BRIDGE_USER_AUTH="disabled"` bypasses OAuth. The
   console runs with the service account's bearer token, not a real user
   session. Some user-specific UI elements may differ from production.

3. **Dev branding** — The bridge runs with `-branding openshift` in dev mode.
   Minor visual differences from production branding are expected.

4. **No multi-user testing** — All screenshots are captured under a single
   service account context. RBAC-dependent views cannot be tested for different
   user roles.

5. **Network policies** — The bridge connects to the cluster API. If the
   workspace pod has network restrictions, API calls may fail.

6. **SPA rendering timing** — The capture script waits for network idle and
   spinner disappearance, but some async-loaded components may not be fully
   rendered. The 2-second settle time mitigates most cases.

7. **Viewport only** — Screenshots use a fixed viewport (default 1920x1080).
   Responsive/mobile layouts are not tested unless explicitly requested with
   `--viewport`.

---

## Skill Script Inventory

| File                              | Type   | Purpose                              |
|-----------------------------------|--------|--------------------------------------|
| `SKILL.md`                        | Doc    | This file — skill documentation      |
| `scripts/setup.sh`               | Bash   | Phase 0 + 1: validate, clone, setup  |
| `scripts/capture-screenshots.js` | Node   | Phase 2/3: Puppeteer screenshot tool |
