---
description: Analyze Go codebase for CVE vulnerabilities and suggest fixes
argument-hint: "<CVE-ID> | --jira=<PROJ-NNN> | --jql=\"...\" [--repo=<url-or-component>] [--algo=vta|rta|cha|static] [--auto-approve=yes|no]"
---

## Name
compliance:analyze-cve

## Synopsis
```
/compliance:analyze-cve <CVE-ID> [--repo=<url-or-component>] [--algo=vta|rta|cha|static] [--auto-approve=yes|no]
/compliance:analyze-cve --jira=<PROJ-NNN> [--repo=...] [--algo=...] [--auto-approve=yes|no]
/compliance:analyze-cve --jql="<JQL query>" [--repo=...] [--algo=...] [--auto-approve=yes|no]
```

## Description
The `compliance:analyze-cve` command performs comprehensive security vulnerability analysis for Go projects. Given a CVE identifier — supplied directly, or resolved from a Jira ticket — it resolves and clones the affected repository, gathers vulnerability intelligence, analyzes the codebase for impact, generates a risk report, optionally applies fixes, and optionally opens a GitHub pull request after a verified fix.

Repository resolution works in four ways, in priority order: (1) an explicit `--repo=` (full URL or short image/component name), (2) exactly one pre-cloned repository already present in this workspace's `repos/` directory when `--repo=` was not passed, (3) an image name extracted from a Jira ticket's summary/labels/custom fields when `--jira=`/`--jql=` was used, or (4) an interactive prompt for the repository URL or image name. See [Phase 0.7](#phase-07-repository-resolution-and-cloning) for the full resolution and cloning logic.

Designed for both interactive use and headless execution (e.g. `claude --print "/compliance:analyze-cve --jira=OCPBUGS-12345 --auto-approve=yes"`) for scheduled/periodic runs.

## Arguments

Exactly one of the following input modes is required:

- **`<CVE-ID>`** — Direct CVE identifier (format: `CVE-YYYY-NNNNN`, case-insensitive). Use when you already know the CVE.
- **`--jira=PROJ-NNN`** — Jira ticket key (e.g. `--jira=OCPBUGS-12345`). The command fetches the ticket and extracts the CVE ID, affected image name, and enrichment context (CVSS, CWE, priority, workarounds) from it.
- **`--jql="..."`** — JQL query (e.g. `--jql="project = OCPBUGS AND labels = needs-cve-analysis"`). The command fetches a batch of matching issues, filters out any already labeled `ai-cve-analyzed`, and processes exactly **one** of the remainder per run (see [Phase 0.3](#phase-03-jql-resolution-only-when---jql-is-provided)). Re-running the same JQL periodically works through the queue over multiple invocations.

Optional flags:

- **`--repo=<url-or-component>`**: Repository to analyze. Accepts:
  - A full GitHub URL: `--repo=https://github.com/openshift/cert-manager-operator`
  - A short image/component name: `--repo=cert-manager-operator-rhel9` (resolved via the [image-repo-mapping](../skills/image-repo-mapping/SKILL.md) skill)
  - If omitted, Phase 0.7 checks for exactly one pre-cloned repo in this workspace first, then resolves from the Jira ticket's image name (if `--jira`/`--jql` was used), then prompts the user.
- **`--algo`** (default: `vta`): Call graph construction algorithm.
  - `vta` — Most precise, fewest false positives (recommended)
  - `rta` — Good balance of precision and speed
  - `cha` — Fast, less precise
  - `static` — Fastest, least precise
- **`--auto-approve=yes|no`** (default: `no`): Run end-to-end without interactive approval prompts. See [Autonomous Mode](#autonomous-mode---auto-approveyesno) below. Intended for scheduled/headless runs.

## Autonomous Mode (`--auto-approve=yes|no`)

`AUTO_APPROVE` is parsed **once**, in Phase 0, from `--auto-approve` (default `no`). It is the **single source of truth** for every approval prompt in this command and its skills — every phase and skill below reads this same value instead of asking independently. Do not add new local "yes/no" prompts anywhere; gate them on `AUTO_APPROVE` the same way.

`AUTO_APPROVE` only answers **yes/no risk decisions** that a human would otherwise approve — it does **not** authorize guessing when required information is missing or ambiguous. Guessing in those cases (wrong repo, wrong branch, wrong CVE, wrong file set) is a correctness/security risk, not a convenience trade-off, so those points **always hard-fail** regardless of `AUTO_APPROVE`, exactly as they do today for a human who doesn't answer.

| # | Decision point | Interactive (`AUTO_APPROVE=no`) | `AUTO_APPROVE=yes` |
|---|---|---|---|
| 1 | Phase 2: risk = `NEEDS_REVIEW` — proceed to remediation guidance? | Ask | Proceed (yes) |
| 2 | Phase 4: apply fixes automatically (→ Phase 5)? | Ask | Proceed (yes) |
| 3 | Phase 6: create a GitHub PR (→ `create-fix-pr`)? | Ask | Proceed (yes) |
| 4 | `create-fix-pr` Step 2: conflicting open PR found (title match) | Ask: stack / wait / independent — do not guess | Always **`wait`** — skip PR creation this run; never auto-stack onto or auto-duplicate someone else's PR |
| 5 | `report-to-jira` Step 3b: restricted-visibility posting unavailable, only public MCP/CLI fallback works — proceed? | Ask | Proceed (yes) — post via the fallback, clearly logged as posted without the visibility restriction |

**Always hard-fail regardless of `AUTO_APPROVE`** (never guess):

| Decision point | Behavior |
|---|---|
| Phase 0.7 Step 1: multiple pre-cloned repos found | Exit with error listing the candidates; require `--repo=` |
| Phase 0.7 Step 2: repo URL/image still unresolved | Exit with error (unchanged from today) |
| Phase 0.7 Step 3a: mapped Jira branch doesn't exist, and the verbatim-Jira-value fallback *also* doesn't exist | Exit with error; do not invent a branch name |
| `jira-cve-extraction` Step 4: multiple CVE IDs found in one ticket | Exit with error listing them; require the caller to disambiguate (e.g. re-run with a direct `<CVE-ID>`) |
| `cve-intelligence-gathering` Step 6: no CVE data from any source | Exit with error; do not proceed on fabricated CVE details |
| `create-fix-pr` Step 3b: `PHASE5_FILES` allowlist missing/empty and cannot be rebuilt | Return `status: failed` (`phase5_files_missing`) immediately — never prompt |
| `create-fix-pr` Step 0/3b: branch diff contains paths outside `PHASE5_FILES` | Return `status: failed` (`phase5_files_mismatch`) immediately — never prompt; committed history is never silently dropped or included |

All other absolute rules are unaffected by `AUTO_APPROVE`: embargo abort, credential handling, no force-push to `main`/`master`, no `--no-verify`, and "never change code without approval."

---

## Security — Credential Handling

> **This rule applies to every shell command, log line, and model response in this command, without exception.**

- **Never print, echo, log, or display credentials in any form.** This includes API tokens, passwords, PATs, service-account keys, and any environment variable whose name contains `TOKEN`, `KEY`, `SECRET`, `PASSWORD`, `PAT`, `CREDENTIAL`, or `AUTH`.
- If a command requires a credential, pass it directly via the environment variable reference (e.g. `$JIRA_API_TOKEN`). Never interpolate the value into a string that will be printed or logged.
- If a credential accidentally appears in command output, **do not repeat or quote it** in any subsequent message or log.
- When logging command invocations for debugging, **mask** credential arguments. Pass auth headers via a `chmod 600` curl config file (`curl -K`) — never as a `-H "Authorization: ..."` argv flag, which exposes the token to `ps aux` / `/proc/<pid>/cmdline` while `curl` runs. Reject non-HTTPS `JIRA_BASE_URL` values before sending credentials:
  ```bash
  # Good — credential stays out of argv and stdout
  case "${JIRA_BASE_URL}" in https://*) ;; *) echo "ERROR: JIRA_BASE_URL must use HTTPS"; exit 1 ;; esac
  curl_cfg=$(mktemp); chmod 600 "${curl_cfg}"
  trap 'rm -f "${curl_cfg}"' EXIT INT TERM
  printf 'header = "Authorization: Bearer %s"\n' "${JIRA_API_TOKEN}" > "${curl_cfg}"
  curl -s -K "${curl_cfg}" "${JIRA_BASE_URL}/rest/api/2/issue/PROJ-123"
  rm -f "${curl_cfg}"
  trap - EXIT INT TERM
  echo "Calling Jira API with Bearer token (masked)"

  # Bad — token value exposed in log or process list
  echo "Token is: $JIRA_API_TOKEN"
  curl -H "Authorization: Bearer $JIRA_API_TOKEN" ...
  curl -v -H "Authorization: Bearer eyJhb..."
  ```
- The same rule applies to SSH keys, `~/.netrc` contents, Git credential helpers, and any secrets mounted as files.

---

## Runtime Configuration

- **`AI_HELPERS_WORKSPACE`** (optional, default: `.` — the current working directory): base directory for everything this command writes — cloned repos (`${AI_HELPERS_WORKSPACE}/.work/compliance/analyze-cve/repos/`), reports, and Phase 5 artifacts (`${AI_HELPERS_WORKSPACE}/.work/compliance/analyze-cve/{CVE-ID}/`). Leave unset for normal local/CLI use. Set it when this command runs somewhere the caller's cwd isn't a stable, writable location for `.work/` — e.g. a Remote Workspace pod (set `AI_HELPERS_WORKSPACE=/workspace`) or another headless/CI runner with its own persistent mount.
- **`FORK_ORG`** (optional): if set, Phase 6 pushes the fix branch to a fork under this org instead of the resolved repo's own `origin`, and opens a cross-repo PR. See `create-fix-pr`'s [Fork Mode](../skills/create-fix-pr/SKILL.md#fork-mode-fork_org-set). Use this when the identity running Phase 6 isn't a direct collaborator on every repo `image-repo-mapping` might resolve to (common for a bot identity in CI/RWS).

---

## Implementation

### Phase 0: Setup and Tool Validation

1. **Parse Arguments**
   - Determine input mode:
     - IF `--jql="..."` provided → set `JQL_QUERY`, resolve to a single ticket in Phase 0.3
     - ELSE IF `--jira=PROJ-NNN` provided → set `JIRA_TICKET=PROJ-NNN`, CVE-ID to be resolved in Phase 0.5
     - ELSE IF a bare `CVE-YYYY-NNNNN` token is present → set `CVE_ID` directly
     - ELSE → exit with error: "Provide a CVE ID, a Jira ticket (--jira=), or a JQL query (--jql=)"
   - Extract `--repo` value if provided (optional); store as `REPO_INPUT`.
   - Extract `--algo` value if provided (optional, default: `vta`). Valid values: `vta`, `rta`, `cha`, `static`.
   - Extract `--auto-approve` value if provided (optional, default: `no`); store as `AUTO_APPROVE`. Valid values: `yes`, `no` (case-insensitive). Any other value → warn and treat as `no`. See [Autonomous Mode](#autonomous-mode---auto-approveyesno) — this single value is passed to every phase and skill below instead of asking independently.

2. **Check Required Tools**

   ```bash
   go version 2>/dev/null || echo "MISSING: go"
   which govulncheck 2>/dev/null || echo "MISSING: govulncheck"
   which callgraph 2>/dev/null || echo "MISSING: callgraph"
   which digraph 2>/dev/null || echo "MISSING: digraph"
   which git 2>/dev/null || echo "MISSING: git"
   ```

3. **If ANY Tool is Missing** → Display installation instructions and **exit with error**:

   ```bash
   go install golang.org/x/vuln/cmd/govulncheck@latest
   go install golang.org/x/tools/cmd/callgraph@latest
   go install golang.org/x/tools/cmd/digraph@latest
   ```

   `git` has no install command here — it's expected to already be present; if missing, point the user at their OS package manager.

4. **Optional Phase 6 tool** (warn only, do not exit):

   ```bash
   which gh 2>/dev/null || echo "OPTIONAL: gh (needed only for Phase 6 GitHub PR creation)"
   ```

5. **If all required tools present** → Continue to Phase 0.3 (if JQL mode), Phase 0.5 (if Jira mode), or Phase 0.7 (if direct CVE mode).

---

### Phase 0.3: JQL Resolution _(only when `--jql` is provided)_

Run the JQL query once, fetch a small batch of candidates, and select exactly **one** ticket to process this run — this phase never drains a whole queue in a single invocation. The rest are left for a future run.

```python
results = searchJiraIssuesUsingJql(
    jql=JQL_QUERY,
    fields=["key", "summary", "labels"],
    maxResults=10   # a candidate batch, not a work queue to process in one run
)
```

**Decision Point:**
- IF query returns 0 results → exit with: `No Jira issues matched the JQL query: <JQL_QUERY>`
- IF query returns 1 or more results → continue to Step 1.

#### Step 1: Filter Out Already-Processed Tickets

Partition the batch:

```python
unprocessed = [r for r in results if "ai-cve-analyzed" not in r["fields"]["labels"]]
already_done = [r for r in results if "ai-cve-analyzed" in r["fields"]["labels"]]
```

This exists to avoid a "stuck forever" failure mode: naively always taking `results[0]` would keep re-selecting the same already-processed ticket on every scheduled re-run whenever the caller's JQL doesn't explicitly exclude `ai-cve-analyzed`. Filtering here — not just relying on the idempotency check in `jira-cve-extraction` Step 2.5 — is what makes repeatedly invoking the *same* JQL an actual way to drain a queue over time.

- IF `unprocessed` is empty (every fetched candidate already has `ai-cve-analyzed`) → exit with:

  ```
  All <N> ticket(s) matching this JQL in the fetched batch are already processed (ai-cve-analyzed).
  There may be more matches beyond this batch of 10 — narrow the JQL or re-run later.
  ```

  Do not fall back to an already-processed ticket, and do not fetch further pages automatically.

#### Step 2: Select One Ticket from the Unprocessed Set

- IF `JQL_QUERY` contains an explicit `ORDER BY` clause (case-insensitive substring match) → **respect it**: select `unprocessed[0]`.
- IF `JQL_QUERY` has **no** `ORDER BY` clause → Jira's default ordering is not a documented/guaranteed sort, so **pick uniformly at random** from `unprocessed` instead of always taking whichever ticket happens to sort first. Combined with Step 1's filtering, repeated invocations of the same unordered JQL naturally work through the whole matching set over time.
- Set `JIRA_TICKET` to the selected ticket's key.

#### Step 3: Report

Print a summary table covering every fetched candidate, not just the selected one:

```
JQL matched <N> issue(s) in this batch (there may be more beyond max_results=10).

✅  <PROJ-NNN>  <summary>          ← selected — processing now
♻️   <PROJ-NNN>  <summary>          ← already processed (ai-cve-analyzed) — skipped
⏭   <PROJ-NNN>  <summary>          ← unprocessed, not selected this run — left for a future run
...
```

- Continue to Phase 0.5 with `JIRA_TICKET` set.

---

### Phase 0.5: Jira CVE Extraction _(only when `--jira` or `--jql` is provided)_

- **Skill**: [jira-cve-extraction](../skills/jira-cve-extraction/SKILL.md)
- **Input**: Jira ticket key from `--jira=` (or resolved in Phase 0.3), `AUTO_APPROVE`
- **Output**: `CVE_ID`, `IMAGE_NAME`, `BRANCH`, `SOURCE_TICKET`, full `jira_context` enrichment block, and top-level `analysis_hints` (including `urgency_override`)

**Extraction priority (per skill):**
1. Parse ticket **summary** — format `CVE-YYYY-NNNNN <image>: <desc> [branch]` — provides CVE ID, image name, and branch in one step
2. `pscomponent:` label → image name fallback
3. `Downstream Component Name` custom field → image name fallback
4. `Custom field (CVE ID)` → CVE ID fallback

**Decision Point:**
- IF ticket not found or access denied → Exit with error
- IF `embargo_status = True` → **Exit immediately. Do not proceed. Do not output any ticket data.**
- IF label `ai-cve-analyzed` already present → Exit with `status: skipped` (already processed)
- IF no CVE ID found → IF `AUTO_APPROVE=no`, prompt user to supply manually; if declined → Exit. IF `AUTO_APPROVE=yes`, exit immediately (never gated).
- IF no image name found → Leave blank; Phase 0.7 will prompt (or hard-fail if `AUTO_APPROVE=yes`, per its own rules)
- IF resolved → Set `CVE_ID` + `IMAGE_NAME`, carry `jira_context` (includes CVSS, CWE, priority, versions) forward → Continue to Phase 0.7

---

### Phase 0.7: Repository Resolution and Cloning

- **Skill**: [image-repo-mapping](../skills/image-repo-mapping/SKILL.md)

#### Storage path

Cloned repos are stored under this command's own workspace directory (see [Runtime Configuration](#runtime-configuration) for `AI_HELPERS_WORKSPACE`), gitignored and persistent across runs:

```bash
REPOS_BASE="${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/repos"
mkdir -p "${REPOS_BASE}"
```

#### Step 1: Check for a Pre-Cloned Repository

```bash
ls "${REPOS_BASE}/" 2>/dev/null
PRECLONE_CANDIDATE=""
if [ "$(find "${REPOS_BASE}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)" -eq 1 ]; then
  PRECLONE_CANDIDATE="$(find "${REPOS_BASE}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1)"
fi
```

- IF `REPOS_BASE` contains multiple directories AND `--repo=` was not passed → **always** list them and exit with an error asking the caller to re-run with `--repo=`. This is not gated by `AUTO_APPROVE` — guessing the wrong repo is a correctness risk, not a convenience trade-off.
- IF exactly one directory AND `--repo=` was not passed AND **`--jira`/`--jql` was NOT used** → set `REPO_DIR="${PRECLONE_CANDIDATE}"`. IF `[ ! -d "${REPO_DIR}/.git" ]` or `git -C "${REPO_DIR}" remote get-url origin` does not normalize to a valid `owner/repo` slug → exit with error. Otherwise set `REPO_URL` from that origin and skip to Step 4.
- IF exactly one directory AND `--jira`/`--jql` was used → **do not reuse yet**; continue to Step 2 so `IMAGE_NAME` maps to the expected `REPO_URL`/`GIT_BRANCH`, then validate the checkout in Step 3b before reuse.
- IF `REPOS_BASE` is empty, or `--repo=` was explicitly passed → continue to Step 2.

#### Step 2: Resolve Repository URL

Determine `REPO_URL` using the first applicable source:

1. **`--repo` flag provided**:
   - Full URL (`https://...`) → use directly.
   - Short name or image name → run `image-repo-mapping` skill.
2. **`--jira`/`--jql` was used and `IMAGE_NAME` was extracted** → run `image-repo-mapping` skill with `IMAGE_NAME`.
3. **Neither** → prompt user: "Please provide the repository URL or image name (e.g. https://github.com/openshift/cert-manager-operator or --repo=cert-manager-operator-rhel9)." IF `AUTO_APPROVE=yes` (no user to prompt) → skip straight to exiting with error below.

**Decision Point:**
- IF `REPO_URL` still unresolved after prompting → Exit with error. Always exits this way regardless of `AUTO_APPROVE` — there is no safe default repository to guess.

#### Step 3: Resolve the Target Branch and Repository Pattern

Check whether the image maps to a **Pattern A** (direct repo) or **Pattern B** (release repo + submodules) component — this is indicated in the `image-repo-mapping` skill output.

**If Pattern B:** the `REPO_URL` returned by `image-repo-mapping` is the release repo URL. Continue to Step 3a (release repo clone), then Step 3c (submodule resolution), then Step 3b (component clone).

**If Pattern A:** skip Steps 3a and 3c. Proceed directly to Step 3b with `GIT_BRANCH` from Step 3 below.

##### Step 3a (Pattern B only): Clone the Release Repo and Read `.gitmodules`

Use `BRANCH` extracted by `jira-cve-extraction` (e.g. `openshift-4.17`, `ztwim-1.0`), resolved per its "Branch Resolution" section (Pattern A table) or passed through verbatim for Pattern B (this skill's own release-branch table handles it).

**Verify the branch exists before cloning:**

```bash
git ls-remote --heads "${REPO_URL}" "${GIT_BRANCH}" | grep -q "${GIT_BRANCH}"
```

- IF branch exists → clone with `-b "${GIT_BRANCH}"` in Step 3b.
- IF branch does not exist → try the Jira value verbatim as a fallback (same automatic step regardless of `AUTO_APPROVE`).
  - IF the verbatim fallback branch exists → use it, and note in the report that the mapped branch name was not found and the verbatim Jira value was used instead.
  - IF the verbatim fallback **also** does not exist → IF `AUTO_APPROVE=no`, warn the user and ask them to confirm or provide the correct branch name. IF `AUTO_APPROVE=yes`, there is no one to ask — **exit with error** instead of guessing a branch name. This case is never gated by `AUTO_APPROVE`.
- IF `BRANCH` was not extracted (direct CVE mode, no Jira ticket, and `--repo=` was a bare URL with no branch hint) → clone default branch; note this in the analysis.

##### Step 3c (Pattern B only): Read `.gitmodules` and Resolve Component Repo

```bash
# Fresh per-run release clone — never reuse a shared /tmp path across executions
RELEASE_CLONE_DIR="${REPOS_BASE}/.release-clones/$(echo "${RELEASE_REPO_URL}" | sed -E 's#^[a-zA-Z]+://github\.com/##; s#\.git$##; s#/$##' | tr '/' '-')-${GIT_BRANCH}"
rm -rf "${RELEASE_CLONE_DIR}"
mkdir -p "$(dirname "${RELEASE_CLONE_DIR}")"
echo "Cloning release repo ${RELEASE_REPO_URL} @ ${GIT_BRANCH} ..."
timeout 120 git clone --depth=1 -b "${GIT_BRANCH}" "${RELEASE_REPO_URL}" "${RELEASE_CLONE_DIR}"
RELEASE_CLONE_EXIT=$?
if [ $RELEASE_CLONE_EXIT -eq 124 ]; then
  echo "ERROR: release repo clone timed out after 120s"
  exit 1
elif [ $RELEASE_CLONE_EXIT -ne 0 ]; then
  echo "ERROR: release repo clone failed for ${RELEASE_REPO_URL}"
  exit 1
fi
echo "✓ Release repo cloned"

# Print .gitmodules so the model can parse it
cat "${RELEASE_CLONE_DIR}/.gitmodules"
```

From `.gitmodules`, find the entry matching the target image (use the submodule name from the `image-repo-mapping` skill output). Extract:
- `url` → the component repo to clone (`COMPONENT_URL`)
- `path` → submodule path within the release repo (`SUBMODULE_PATH`)
- `branch` → informational only for Pattern B — the release repo tree pins the exact commit
- `tag` → if present instead of `branch`, clone at this tag (`COMPONENT_TAG`) for non-submodule flows

Read the **pinned commit** recorded in the release repo tree (do not guess from `.gitmodules` branch alone):

```bash
PINNED_COMMIT=$(git -C "${RELEASE_CLONE_DIR}" ls-tree HEAD "${SUBMODULE_PATH}" | awk '{print $3}')
echo "Pinned commit for ${SUBMODULE_PATH}: ${PINNED_COMMIT}"
if [ -z "${PINNED_COMMIT}" ]; then
  echo "ERROR: no pinned commit found for submodule ${SUBMODULE_PATH} in ${RELEASE_REPO_URL}@${GIT_BRANCH}"
  exit 1
fi
```

Set `REPO_URL = COMPONENT_URL` and `GIT_BRANCH = ${PINNED_COMMIT}` (detached checkout) for Step 3b. IF `PINNED_COMMIT` is empty → exit with error; do not clone at an unpinned branch.

##### Step 3b: Clone the Repository

```bash
normalize_git_url() {
  printf '%s' "$1" | sed -E 's#^[a-zA-Z]+://github\.com/##; s#\.git$##; s#/$##; s#^git@github\.com:##'
}

is_commit_ref() {
  [[ "${1}" =~ ^[0-9a-f]{7,40}$ ]]
}

validate_repo_slug() {
  local slug="$1"
  [[ "${slug}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || return 1
  case "${slug}" in ..*|*/..|*../*|*/*/) return 1 ;; esac
  return 0
}

assert_repo_dir_under_base() {
  local abs_base abs_dir
  abs_base="$(cd "${REPOS_BASE}" && pwd)"
  abs_dir="$(cd "${REPO_DIR}" 2>/dev/null && pwd || echo "${abs_base}/$(basename "${REPO_DIR}")")"
  case "${abs_dir}" in
    "${abs_base}"/*) return 0 ;;
    *) echo "ERROR: REPO_DIR ${REPO_DIR} escapes REPOS_BASE ${REPOS_BASE}"; exit 1 ;;
  esac
}

REPO_SLUG="$(normalize_git_url "${REPO_URL}")"
if ! validate_repo_slug "${REPO_SLUG}"; then
  echo "ERROR: invalid repository URL slug from ${REPO_URL}"
  exit 1
fi
REPO_DIR="${REPOS_BASE}/$(echo "${REPO_SLUG}" | tr '/' '-')"
mkdir -p "${REPOS_BASE}"
assert_repo_dir_under_base

clone_repo_at_ref() {
  local url="$1" dir="$2" ref="${3:-}"
  if [ -n "${ref}" ] && is_commit_ref "${ref}"; then
    timeout -k 10 300 git clone "${url}" "${dir}" || return $?
    timeout -k 10 120 git -C "${dir}" fetch origin "${ref}" || return $?
    git -C "${dir}" checkout "${ref}" || return $?
  elif [ -n "${ref}" ]; then
    timeout -k 10 300 git clone --depth=50 -b "${ref}" "${url}" "${dir}" || return $?
  else
    timeout -k 10 300 git clone --depth=50 "${url}" "${dir}" || return $?
  fi
}

sync_existing_repo() {
  local expected_slug current_slug current_origin
  expected_slug="$(normalize_git_url "${REPO_URL}")"
  current_origin="$(git -C "${REPO_DIR}" remote get-url origin 2>/dev/null || true)"
  current_slug="$(normalize_git_url "${current_origin}")"
  if [ -z "${current_slug}" ] || [ "${expected_slug}" != "${current_slug}" ]; then
    echo "⚠ Existing clone at ${REPO_DIR} points at ${current_origin:-unknown}, expected ${REPO_URL} — removing and re-cloning"
    assert_repo_dir_under_base
    rm -rf "${REPO_DIR}"
    clone_repo_at_ref "${REPO_URL}" "${REPO_DIR}" "${GIT_BRANCH}"
    if [ $? -ne 0 ]; then
      echo "ERROR: re-clone failed after origin mismatch for ${REPO_URL}"
      exit 1
    fi
    return
  fi

  if [ -n "${GIT_BRANCH}" ] && is_commit_ref "${GIT_BRANCH}"; then
    local current_head
    current_head="$(git -C "${REPO_DIR}" rev-parse HEAD 2>/dev/null || true)"
    if [ "${current_head}" != "${GIT_BRANCH}" ]; then
      echo "Switching to pinned commit ${GIT_BRANCH} ..."
      timeout -k 10 120 git -C "${REPO_DIR}" fetch origin "${GIT_BRANCH}"
      git -C "${REPO_DIR}" checkout "${GIT_BRANCH}"
    fi
    return
  fi

  local current_branch
  current_branch="$(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [ -n "${GIT_BRANCH}" ] && ! is_commit_ref "${GIT_BRANCH}" && [ "${current_branch}" != "${GIT_BRANCH}" ]; then
    echo "Switching from ${current_branch} to ${GIT_BRANCH} ..."
    timeout -k 10 120 git -C "${REPO_DIR}" fetch origin "${GIT_BRANCH}"
    git -C "${REPO_DIR}" checkout "${GIT_BRANCH}"
    current_branch="$(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  fi
  if [ "${current_branch}" = "HEAD" ] || is_commit_ref "${GIT_BRANCH}"; then
    echo "Detached HEAD — skipping git pull --ff-only"
    return
  fi
  timeout -k 10 120 git -C "${REPO_DIR}" pull --ff-only
}

if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "Cloning ${REPO_URL} (ref: ${GIT_BRANCH:-default}) into ${REPO_DIR} ..."
  clone_repo_at_ref "${REPO_URL}" "${REPO_DIR}" "${GIT_BRANCH}"
  CLONE_EXIT=$?
  if [ $CLONE_EXIT -eq 124 ] || [ $CLONE_EXIT -eq 137 ]; then
    echo "ERROR: git clone timed out after 300s for ${REPO_URL}"
    echo "The repository may be too large or the network too slow."
    exit 1
  elif [ $CLONE_EXIT -ne 0 ]; then
    echo "ERROR: git clone failed (exit ${CLONE_EXIT}) for ${REPO_URL}"
    exit 1
  fi
else
  sync_existing_repo
fi

# Explicit verification — always print this so it's visible in the session
echo "✓ Repository ready: ${REPO_DIR}"
echo "  Branch : $(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD)"
echo "  Commit : $(git -C "${REPO_DIR}" rev-parse --short HEAD)"
echo "  go.mod : $([ -f "${REPO_DIR}/go.mod" ] && echo 'present' || echo 'MISSING')"
```

- IF clone times out → exit with instructions to pre-clone or retry.
- IF clone fails → exit with error details.
- IF clone succeeds → `REPO_DIR` and `GIT_BRANCH` are set as working context for all subsequent phases.
- The verification block at the end **must always print** — this confirms to the user that the repo is ready and is visible in the session context.

#### Step 4: Verify Go Project

```bash
[ -f "${REPO_DIR}/go.mod" ] || echo "WARNING: no go.mod found in ${REPO_DIR}"
```

- IF `go.mod` missing → warn user; call graph and govulncheck steps will be skipped, dependency-based methods only.
- IF `go.mod` present → Continue to Phase 1.

#### Repo Guard — Re-clone if Missing

Even though repos are cloned under this command's own `.work/` directory (not a temp mount), external cleanup (e.g. `git clean -fdx`, a stray `rm -rf .work`) can still remove `REPO_DIR` between phases. Every phase that needs `REPO_DIR` runs this guard first:

```bash
if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "⚠ Repo missing at ${REPO_DIR} — re-cloning..."
  mkdir -p "${REPOS_BASE}"
  clone_repo_at_ref "${REPO_URL}" "${REPO_DIR}" "${GIT_BRANCH}"
  if [ $? -ne 0 ]; then
    echo "✗ Re-clone failed. Cannot continue without the repository."
    exit 1
  fi
  echo "✓ Re-cloned: ${REPO_DIR} @ $(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD)"
fi
```

Run this guard at the start of **Phase 2, Phase 4, Phase 5, and Phase 6**.

---

### Phase 1: CVE Intelligence Gathering

- **Skill**: [cve-intelligence-gathering](../skills/cve-intelligence-gathering/SKILL.md)
- **Input**: `CVE_ID` (from argument or Phase 0.5) **+ `jira_context` from Phase 0.5 (if `--jira`/`--jql` was provided)**
- **Output**: Merged CVE profile combining Jira internal data (when present) with public sources (NVD, GHSA, Go vulndb)

Pass the full `jira_context` object from Phase 0.5 into the skill, when present. The skill uses Jira fields (CVSS, CWE, affected versions, internal notes, workarounds, release note text) as a pre-populated starting point, then uses web searches to verify, fill gaps, and add public context. Neither source replaces the other — both are combined.

**Decision Point:**
- IF invalid CVE format → Exit with error
- IF CVE not found AND (user declines to provide info, or `AUTO_APPROVE=yes` with no one to ask) → Exit with error
- IF CVE is not Go-related → Generate "Not Applicable" report → Exit
- IF CVE details found → Continue to Phase 2

---

### Phase 2: Codebase Impact Analysis

**Before starting:** Run the [Repo Guard](#repo-guard--re-clone-if-missing) to verify `REPO_DIR` still exists. Re-clone if needed.

- **Skill**: [codebase-impact-analysis](../skills/codebase-impact-analysis/SKILL.md)
  - Sub-skill: [call-graph-analysis](../skills/call-graph-analysis/SKILL.md)
- **Working directory**: `REPO_DIR` set in Phase 0.7 (e.g. `.work/compliance/analyze-cve/repos/hypershift`)
- **Input**: CVE profile from Phase 1, `--algo` preference
- **Output**: Risk level (HIGH/MEDIUM/LOW/NEEDS_REVIEW), evidence package, confidence assessment

**Decision Point:**
- IF HIGH RISK or MEDIUM RISK → Generate report (Phase 3) → Proceed to Phase 4
- IF LOW RISK → Generate report (Phase 3) → Recommend manual review → Exit
- IF NEEDS REVIEW → Generate report (Phase 3) → IF `AUTO_APPROVE=no`, ask user if they want remediation guidance: IF yes → Proceed to Phase 4; IF no → Exit. IF `AUTO_APPROVE=yes` → proceed to Phase 4 automatically.

---

### Phase 3: Report Generation

Generate analysis report at `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/{CVE-ID}/report.md` — the same workspace base as Phase 0.7's `REPOS_BASE`, so the report lands in the configured workspace regardless of the caller's current directory.

**Report structure:**
- Executive Summary: risk level, confidence, key takeaway
- CVE Context: vulnerability description, sources (tag verified vs user-provided)
- Jira Context _(if `--jira`/`--jql` was provided)_: ticket URL, priority, status, assignee, target versions, components, internal notes, linked issues
- Analysis Methods: what was used, why, and what was found
- Findings: specific evidence (file paths, versions, code snippets, call chains)
- Risk Assessment: severity + actual exposure + exploitability in this context; escalate if `analysis_hints.urgency_override` is set
- Next Steps: remediation guidance or monitoring recommendations; note any existing workarounds from the Jira ticket
- Sources and Limitations: tools used, gaps, analysis date

**Additional artifacts** (as generated):
- `callgraph.svg` (if call graph analysis was performed)
- `govulncheck-output.txt` (if scanner was run)
- `evidence.json` (structured evidence data)

---

### Phase 4: Remediation Guidance

**Before starting:** Run the [Repo Guard](#repo-guard--re-clone-if-missing) to verify `REPO_DIR` still exists. Re-clone if needed.

- **Skill**: [remediation-planning](../skills/remediation-planning/SKILL.md)
- **Input**: CVE profile from Phase 1, risk level and evidence from Phase 2
- **Output**: Remediation plan (strategy, commands, verification steps, risk assessment)

**Decision Point:**
- Present remediation plan to user
- IF `AUTO_APPROVE=no` → Ask: "Would you like me to apply these fixes automatically?" IF yes → Continue to Phase 5. IF no → Exit with report and manual instructions.
- IF `AUTO_APPROVE=yes` → Continue to Phase 5 automatically. Still present the plan in the session output first — automation skips the prompt, not the transparency.

After presenting the report (regardless of whether the user proceeds to Phase 5), IF a Jira ticket is involved (`--jira`/`--jql` was used), invoke the report-to-jira skill:

- **Skill**: [report-to-jira](../skills/report-to-jira/SKILL.md)
- **Input**: completed report, `CVE_ID`, risk level, `SOURCE_TICKET`, `jira_context` (label snapshot from Phase 0.5), `AUTO_APPROVE`
- **Output**: comment and `ai-cve-analyzed` label posted to `SOURCE_TICKET`; skipped silently in direct CVE mode; if posting fails, comment body is displayed in session for manual copy-paste

---

### Phase 5: Interactive Fix Application

**Before starting:** Run the [Repo Guard](#repo-guard--re-clone-if-missing) to verify `REPO_DIR` still exists. Re-clone if needed.

Requires **explicit approval** before proceeding — this is the Phase 4 decision point above (`AUTO_APPROVE=yes` counts as that approval; no separate prompt here). Do not change live cluster or production-environment configuration. Repo-tracked config files are allowed only as the approved remediation.

**Before applying anything**, snapshot the worktree so Phase 6 can stage only Phase 5 files (including new untracked paths). `WORK_CVE` is in **this command's own workspace**, not inside `REPO_DIR` — derive it from the same base as `REPOS_BASE` (Phase 0.7), not a bare relative path, so it doesn't depend on the caller's current directory:

```bash
WORK_CVE="${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}"
mkdir -p "${WORK_CVE}"
git -C "${REPO_DIR}" status --porcelain > "${WORK_CVE}/phase5-before.status"
```

1. **Apply Fixes** (all commands below run against `REPO_DIR`)
   - Dependency bump: update `go.mod`/`go.sum` with `go get -u <package>@<fixed-version>` + `go mod tidy`
   - **Vendor sync (dependency bumps only):** IF `go.mod`/`go.sum` changed **and** `vendor/` exists → run `go mod vendor` (or `make vendor` if that target exists) now, before writing `PHASE5_FILES`. Doing this later, in Phase 6, would generate `vendor/` paths that never make it into the allowlist and get silently dropped from the commit.
   - Source changes if required (as identified in Phase 4)
   - Repo-tracked config (YAML, Dockerfiles, scripts) if that is the approved remediation

2. **Verify Changes** (after vendor sync, so the vendored tree is what gets verified; run inside `REPO_DIR`)
   - Check for Makefile targets first, fall back to standard Go commands:
     - Verify: `make verify` or `go mod verify`
     - Build: `make build` or `go build ./...`
     - Test: `make test` or `go test ./...`
   - Re-check: `govulncheck ./...`

3. **Document Changes**
   - Summary of changes, files modified, git diff, suggested commit message (Phase 6 uses this if the user approves a PR)
   - Write `PHASE5_FILES` (one **repo-relative** path per line, no porcelain status prefix) to `${WORK_CVE}/phase5-files.txt`. Include every path Phase 5 added, modified, or deleted — including untracked files, and every `vendor/` path touched by the sync above. Union of:
     - porcelain-status paths that are new or whose status code changed vs `phase5-before.status`
     - paths this phase actually edited (so a pre-dirty file Phase 5 touched is not dropped)
   - Exclude `.work/`, analysis reports, and credentials. Do not list pre-existing dirty files that Phase 5 did not touch.

**Decision Point:**
- IF verification failed → stop. Do not offer a PR. Leave the tree for the user to inspect.
- IF verification succeeded → Continue to Phase 6.

---

### Phase 6: GitHub PR Creation

**Before starting:** Run the [Repo Guard](#repo-guard--re-clone-if-missing) to verify `REPO_DIR` still exists. Re-clone if needed.

- **Skill**: [create-fix-pr](../skills/create-fix-pr/SKILL.md)
- **Input**: `REPO_DIR`, `GIT_BRANCH`, `REPO_URL`, `CVE_ID`, `SOURCE_TICKET` (if `--jira`/`--jql` was provided), `PHASE5_FILES` allowlist, Phase 5 change summary, module bump (`old` → `new`) **only if** the fix is a dependency bump, `AUTO_APPROVE`, and `FORK_ORG` (optional env var — if set, the skill pushes to a fork under that org and opens a cross-repo PR instead of pushing directly to the resolved upstream repo; see the skill's [Fork Mode](../skills/create-fix-pr/SKILL.md#fork-mode-fork_org-set) section)
- **Output**: GitHub PR URL (created or updated); optional follow-up Jira comment with that URL

Requires **explicit approval** before any commit, push, or `gh pr create`. This is a separate approval from Phase 5 (applying the fix locally does not imply opening a PR) — `AUTO_APPROVE=yes` must satisfy both approvals independently.

1. IF `AUTO_APPROVE=no` → Ask: "The fix is applied and verified locally. Create a GitHub PR against `<GIT_BRANCH>`?" IF no → Exit. Leave local changes uncommitted (or committed only if the user asked). Print the suggested commit message from Phase 5.
2. IF `AUTO_APPROVE=yes` → treat as yes automatically, skip the prompt.
3. IF proceeding → Run `create-fix-pr`, passing `AUTO_APPROVE` through (`git` and `gh` are **hard requirements of that skill** — if either is missing or `gh` is unauthenticated, fail Phase 6; do not create the PR another way):
   - Check open PRs on the same `org/repo` + base branch whose **title** contains this `CVE_ID` or `SOURCE_TICKET` (title only — ignore files, body, and module versions)
   - If a title match exists: IF `AUTO_APPROVE=no` → present **stack / wait / independent** and wait for the user; do not guess. IF `AUTO_APPROVE=yes` → always **`wait`** (return `status: skipped`, `user_wait_for_pr_auto`, with the existing PR URL) — never auto-stack onto or auto-duplicate someone else's PR unattended.
   - Branch from the mapped release branch, commit **only `PHASE5_FILES`** (for a version bump that is often `go.mod` / `go.sum` / `vendor/`, already vendor-synced in Phase 5; other remediations may be source or config only), using the repo's own commit convention when detectable (e.g. `UPSTREAM:` style) and signing off (DCO) by default
   - Push to `origin` and open a same-repo PR by default, or — if `FORK_ORG` is set — push to a fork under that org and open a cross-repo PR instead (see `create-fix-pr`'s Fork Mode)
   - Validate the staged (and, for `stack`, the branch) path set exactly matches `PHASE5_FILES`; reject/unstage anything extra before continuing
   - Push and `gh pr create` (or update the stacked PR)
   - PR title/body include `CVE_ID`, a summary of the actual Phase 5 change (module/version only when the fix is a dependency bump), short CVE description, and — in Jira mode — a `Fixes:` link to `SOURCE_TICKET`
   - Direct CVE mode (no `--jira`/`--jql`): create the PR **without** Jira links
4. After the PR exists, post the PR URL as a **new** comment on `SOURCE_TICKET` (do not replace the Phase 4 analysis comment). Skip Jira posting in direct CVE mode.
5. Embargo abort and "never change code without approval" still apply. Never force-push `<GIT_BRANCH>`/`main`/`master`.

---

## Return Value

- **Format**: Markdown report at `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/{CVE-ID}/report.md`
- **Content**: Vulnerability details, risk assessment, evidence, remediation recommendations, applied fixes (if approved), GitHub PR URL (if Phase 6 ran)

## Arguments

- `<CVE-ID>`: The CVE identifier to analyze (e.g., CVE-2024-1234, CVE-2023-45678)
  - Format: CVE-YYYY-NNNNN
  - Case insensitive
  - Required unless `--jira=` or `--jql=` is used
- `--jira=PROJ-NNN`: A Jira ticket key to extract the CVE from (e.g. `--jira=OCPBUGS-12345`)
- `--jql="..."`: A JQL query to select one unprocessed ticket per run (e.g. `--jql="project = OCPBUGS AND labels = needs-cve-analysis"`)
- `--repo=<url-or-component>`: Repository to analyze — a full GitHub URL, or a short image/component name resolved via [image-repo-mapping](../skills/image-repo-mapping/SKILL.md) (optional; see [Phase 0.7](#phase-07-repository-resolution-and-cloning) for resolution order)
- `--algo`: Call graph construction algorithm (optional, default: `vta`)
  - `vta` - Most precise, fewest false positives (recommended)
  - `rta` - Good balance of precision and speed
  - `cha` - Fast, less precise
  - `static` - Fastest, least precise
- `--auto-approve=yes|no`: Run end-to-end without interactive approval prompts (optional, default: `no`). See [Autonomous Mode](#autonomous-mode---auto-approveyesno).

## Examples

1. **Basic CVE analysis against an explicit repo**:
   ```
   /compliance:analyze-cve CVE-2024-45338 --repo=https://github.com/golang/net
   ```

2. **With specific algorithm**:
   ```
   /compliance:analyze-cve CVE-2024-45338 --repo=https://github.com/golang/net --algo=rta
   ```

3. **Starting from a Jira ticket (repo/branch resolved automatically from the ticket's image name)**:
   ```
   /compliance:analyze-cve --jira=OCPBUGS-12345
   ```

4. **Unattended run from a JQL queue, applying fixes and opening a PR without prompts**:
   ```bash
   claude --print "/compliance:analyze-cve --jql=\"project = OCPBUGS AND labels = needs-cve-analysis ORDER BY created ASC\" --auto-approve=yes"
   ```

## Prerequisites

All tools below are **required**. The command exits with an error if any are missing.

```bash
# Install all required Go tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest

# git is also required (Phase 0.7 repository cloning) — install via your OS package manager
```

**Optional**:
- `graphviz` for visual call graph generation (`brew install graphviz` or `sudo apt-get install graphviz`)
- `gh` (GitHub CLI, authenticated via `gh auth login`) for Phase 6 pull-request creation. Missing `gh` does **not** fail Phase 0 — analysis and local fixes still run; Phase 6 is skipped until it's available.
- An Atlassian MCP server (e.g. the `jira` plugin's bundled Rovo MCP) or `jira-cli` for `--jira=`/`--jql=` input modes and posting reports back to Jira

**Internet access** is recommended for CVE data fetching but not required if you can provide CVE details manually.

## Notes

- Focuses on Go-specific vulnerabilities.
- Resolves and clones the target repository automatically — via `--repo=`, Jira image-name mapping, or reusing a repo already cloned into `.work/compliance/analyze-cve/repos/` by a previous run — see [Phase 0.7](#phase-07-repository-resolution-and-cloning). All analysis and fix-application phases run against that cloned `REPO_DIR`, not the directory the command happened to be invoked from.
- Falls back to user-provided information if internet access fails.
- Does NOT make changes, commits, or pull requests without explicit approval — either interactive, or given once upfront via `--auto-approve=yes` (see [Autonomous Mode](#autonomous-mode---auto-approveyesno)).
- Reports are saved locally (`.work/compliance/analyze-cve/`, gitignored) and not committed to git — see [Runtime Configuration](#runtime-configuration) (`AI_HELPERS_WORKSPACE`) to relocate this base directory.
- Never process or disclose embargoed CVEs — if a Jira ticket's Embargo Status is `True`, the command stops immediately and outputs nothing about the ticket.
