---
description: Triage all open CVEs for OpenShift Node team components with reachability analysis
argument-hint: "[--component <name>] [--ocp-version X.Y] [--days N] [--notify-jira] [--notify-slack] [--dry-run] [--yes] [--max-trackers N] [--handoff --trackers FILE]"
---

## Name
node-cve:triage

## Synopsis
```text
/node-cve:triage [--component "Node / CRI-O"] [--ocp-version 5.0] [--days 7]
                 [--notify-jira] [--notify-slack] [--dry-run] [--yes] [--max-trackers 50]
                 [--handoff --trackers .work/node-cve/trackers.tsv]
```

## Description

Queries all open CVE vulnerability issues in OCPBUGS for Node team components, deduplicates across version trackers, clones affected repositories, and analyzes source code for CVE reachability. Optionally posts analysis comments to Jira trackers and sends a Slack summary.

Posting to Jira or Slack is outward-facing and hard to undo. The command never posts without an explicit confirmation (interactive) or `--yes` (headless), and `--dry-run` shows exactly what would be posted without posting anything.

Designed for both interactive use and headless execution via `claude --print`. With `--handoff` the command makes no Jira or Slack calls at all: the caller supplies the tracker rows and posts from the posting plan the command writes. This is for runners such as Chai RWS, where the worker that runs the command has no Jira or Slack credentials and the coordinator holds the Jira and Slack tools.

## Prerequisites

- `bash`, `curl`, `jq` and `git`. With `--handoff`, the Jira and Slack variables below are not needed. All Jira access goes through the Jira REST API, Slack through the Slack API or a webhook. The `jira` CLI is not used: it cannot list or edit comments, has no component column, and its pagination offset is ignored on Jira Cloud.
- Environment variables: `JIRA_API_TOKEN`, and `JIRA_USER` (or `JIRA_EMAIL`) with the Jira login. `JIRA_USER` falls back to `git config user.email`, which is usually absent in containers, so set it explicitly for headless runs and service accounts.
- Optional, for `--notify-slack`: either `SLACK_API_TOKEN` (channel from `SLACK_CHANNEL`, threaded messages) or `SLACK_WEBHOOK` (single message)
- The `node-team` plugin (declared dependency) for shared component and version data. Run `/node-team:preflight` first if credentials have not been checked on this machine.

## Implementation

### Helper script and tool use

All Jira, Slack and git access goes through one helper script, invoked as a single command per step:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" help
```

This keeps the command usable in headless runs with a strict tool allowlist: the only Bash command needed is `bash <plugin-root>/skills/report-findings/scripts/node-cve-lib.sh ...`. Rules for the executor:

- **Do not write ad-hoc `curl`, `jira`, or `git` commands, and do not chain commands** with `&&`, `;`, pipes or redirects. Every helper subcommand is self-contained, takes file paths as arguments, and writes its own output files. Shell variables do not persist between Bash tool calls anyway.
- **Use the Read, Grep, Glob and Write tools** for everything that touches files: reading the shared references, searching source code, finding cached analysis files, writing reports and payload texts under `.work/node-cve/`.
- **Never pass a secret as an argument** and never print one. The helper reads tokens from the environment and hands them to `curl` on stdin.
- The helper never reads from a terminal, so it cannot hang in a headless run.

### Locating shared data

This command reads canonical data from the `node-team` plugin (declared dependency). The markdown links in this file resolve in a repository checkout and on the docs site. When the plugins are installed, each plugin lives in its own versioned cache directory, so the relative links do not resolve. The helper's `init` subcommand (Phase 0) finds the real directory, both in a checkout and in the plugin cache, and prints it as `NODE_REFS=<path>`. Read the shared files from that path with the Read tool.

If `init` reports that the references were not found, invoke the `node-team:node` skill and read `references/shared/components.md` and `references/shared/version-map.md` from its base directory. If that also fails, abort. Never continue with a component list from memory.

The files used are:
- [shared/components.md](../../node-team/skills/node/references/shared/components.md): Jira component list, component to repository mapping, `pscomponent:` label mapping
- [shared/version-map.md](../../node-team/skills/node/references/shared/version-map.md): OCP to K8s/CRI-O version mapping and branch naming

### Phase 0: Setup and Argument Parsing

1. **Parse Arguments** (see [Arguments](#arguments) for the full description)
   - `--component <name>`: single Node team component. If omitted, ALL Node team components are included, and only Node team components. The command never queries or posts to components outside the Node team.
   - `--ocp-version X.Y`: triage this OCP version instead of the auto-detected one.
   - `--days N`: only CVEs updated in the last N days.
   - `--notify-jira`, `--notify-slack`: outward-facing posts, both off by default.
   - `--dry-run`: run everything, post nothing, record what would be posted.
   - `--yes`: skip the interactive confirmation (required for headless posting).
   - `--max-trackers N`: hard abort threshold for Jira posting. Default: 50.
   - `--handoff`: no Jira or Slack access. Requires `--trackers FILE`. See [Handoff mode](#handoff-mode).
   - `--trackers FILE`: tracker rows supplied by the caller (only with `--handoff`).
   - `--handoff` with `--days`: stop with "--days is not supported with --handoff".

   **Version scope:** The command triages exactly one OCP version: the latest in-development release. Each CVE typically has tracker issues across many OCP versions (for example 4.12.z through the current release). The OCP sustaining team owns triage and remediation for all versions except the latest. Posting Node team reachability analysis to older-version trackers creates noise for the sustaining team and duplicates their work.

2. **Validate tools and credentials, create the work directory**

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" init
   ```

   With `--handoff`, run `init --handoff` instead. It skips the Jira and Slack checks, prints `MODE=handoff`, and makes the helper refuse `search`, `post-comment` and `slack` for the rest of the run.

   `init` checks `git`, `curl` and `jq`, verifies Jira authentication, creates `.work/node-cve/repos/` and `.work/node-cve/triage-YYYY-MM-DD/`, and prints `NODE_REFS`, `TRIAGE_DIR` and `SLACK_MODE`. If it exits non-zero, show what is missing (or point to `/node-team:preflight`) and stop. It never prints a token.

3. **If `--notify-slack`** (not in handoff mode), check the `SLACK_MODE` line printed by `init`:
   - `api`: `$SLACK_API_TOKEN` is set. The channel is `$SLACK_CHANNEL`, default `GK6BJJ1J5` (`#team-node`). Summary plus threaded reply.
   - `webhook`: only `$SLACK_WEBHOOK` is set. Single message, no threading.
   - `none`: exit with an error, since `--notify-slack` cannot work.

4. **Check the component file**

   `init` extracts the CVE-tracked component names (the full "Jira Components (OCPBUGS)" list plus Driver Toolkit and Machine Config Operator) from `<NODE_REFS>/shared/components.md` into `.work/node-cve/node-components.txt` and prints `COMPONENTS=<file> (<n> names)`. The search in Phase 1 and the posting-time validation in Phase 3 both read this file. Do not write or edit it by hand: a misspelled name would make every tracker of that component fail validation. If `init` reports that it could not extract the list, stop.

   `init` also pins the run directory (printed as `TRIAGE_DIR=`). All later helper calls use it, also when the run crosses midnight, so use that path instead of building `triage-YYYY-MM-DD` from the current date.

---

### Phase 1: Query Open CVEs

- **Skill**: [query-open-cves](../skills/query-open-cves/SKILL.md)
- **Input**: optional `--component`, `--days` and `--ocp-version`
- **Output**: deduplicated, version-filtered list of CVEs with metadata (one OCP version only)

**CRITICAL SAFEGUARD:** The `component in (...)` filter below is mandatory and must never be omitted, regardless of whether `--component` was passed. This is the first of two layers of defense against cross-team contamination. The second is the posting-time re-validation in [report-findings](../skills/report-findings/SKILL.md) Step 2. Both layers exist because a prior incident (2026-07-15) showed that CVE analysis can otherwise be posted to 200+ trackers belonging to other OpenShift teams.

**Steps:**

1. Run the search. The helper builds the JQL itself, so the component clause cannot be forgotten: it always contains `component in (...)` with the double-quoted names from `.work/node-cve/node-components.txt`, or the single `--component` value, which must be in that file.

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" search --out .work/node-cve/trackers.tsv
   ```

   **Handoff mode:** do not run `search`. Use the `--trackers` file instead: it has the same columns and must hold the result of the un-narrowed search (all Node components, no `--days`), so it can also serve the version detection in step 4. Print the JQL the caller should have used, for the record, with `bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" jql`. When `--component` was given, keep only the rows with that component in step 3. `--days` is not supported with `--handoff`, since the rows carry no update time. The sanity check of [query-open-cves](../skills/query-open-cves/SKILL.md) Step 2 applies unchanged: rows with a non-Node component are dropped.

   Add `--component "Node / CRI-O"` and `--days N` when those arguments were given. The JQL used is printed for the record, for example `project = OCPBUGS AND type = Vulnerability AND component in ("Node / CRI-O", "Node / Kubelet", ...) AND status not in (Closed, Done, Verified)`.

   Output columns (tab-separated): key, summary, components (`;`-separated), status, assignee, labels (`,`-separated). The helper paginates until the last page, retries on HTTP 429, and exits non-zero without writing the file on any error, so a failed query is never read as "0 CVEs". Read the file with the Read tool.

2. Parse results and extract CVE IDs from summaries (regex: `CVE-[0-9]{4}-[0-9]+`).

3. Deduplicate: group tracker issues by CVE ID. For each unique CVE, collect:
   - All tracker keys
   - Affected OCP versions (from summary brackets, for example `[openshift-5.0]`)
   - Component names and labels per tracker (a CVE may span multiple components)
   - Assignee and status (from the tracker of the selected version)

4. **Determine the OCP version and filter to it** (see [query-open-cves](../skills/query-open-cves/SKILL.md) Step 5 for the full logic). The version is never taken from a result set narrowed by `--days` or `--component`, because such a set may contain no tracker for the real latest version and would silently select a sustaining-owned release:
   - `--ocp-version X.Y` given: use it.
   - Otherwise detect the highest numeric `major.minor` from a search with the full Node component list and no `--days` (a second `search --out .work/node-cve/trackers-all.tsv` when the first one was narrowed), using the `versions` subcommand, then sanity-check it against `shared/version-map.md`.

   Keep only trackers matching that version. CVEs without a tracker for it are excluded. They are the sustaining team's responsibility.

   Print the version scope: "Version filter: <version> (<auto-detected|from --ocp-version>). Other versions are triaged by the sustaining team."

5. Print intermediate summary: "Found N unique CVEs across M tracker issues (version: <version>)."

**Decision Point:**
- IF 0 CVEs found: print "No open CVEs for Node team components at version <version>." and exit.
- IF CVEs found: continue to Phase 1.5.

---

### Phase 1.5: Check for Prior Analysis (Cache Check)

Before cloning repos and running analysis, check for existing results from prior runs. This avoids redundant reanalysis when the tool is run repeatedly.

Each CVE has exactly one branch to analyze (the release branch of the selected OCP version), so the cache key is the CVE ID plus that branch. For each unique CVE from Phase 1, check two cache sources in order:

**1. Local artifacts**: use the Glob tool with the pattern `.work/node-cve/triage-*/<CVE-ID>-<branch>-analysis.md` and take the match with the newest `triage-YYYY-MM-DD` directory. If that date is within the last 30 days, read the file and reuse its classification and evidence. Local artifacts do not exist in ephemeral environments (containers, CronJobs). There, only the Jira comment cache applies.

**2. Jira comments** (present if `--notify-jira` was used on a prior run, skipped in handoff mode, which has no Jira access): check the tracker for an existing analysis comment:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" find-comment OCPBUGS-XXXXX
```

This prints the newest triage comment as JSON (`id`, `created`, `updated`, `author`, `own`, `own_id`, `body`), or nothing. "Newest" and the 30-day cache age go by `updated`, because a comment edited in place keeps its `created` time. `own_id` is the newest triage comment of your own account, which can be an older one than `id`. It matches the wiki markup footer `[node-cve:triage|` (current and legacy formats) and any link to `plugins/node-cve`. A non-zero exit means the lookup failed: treat the CVE as not cached, and do not post to that tracker in Phase 3. If a comment exists, is within 30 days, and its "Branch" row matches the current branch, reuse its classification. Keep `own_id`: Phase 3 updates that comment in place, and adds a new one only when your account has none.

**Forced re-analysis:** a follow-up comment containing `[reanalyze]` forces re-analysis, but only when it is trusted:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" reanalyze OCPBUGS-XXXXX
```

Exit code 0 means re-analyze, and the helper records the tag as consumed in `.work/node-cve/reanalyze-consumed.txt` so it is honored once. When the cached result came from a local analysis file and the tracker has no triage comment, pass the date of that file as a second argument (`reanalyze OCPBUGS-XXXXX 2026-09-01`); without it every trusted, unconsumed tag counts. Remember which CVEs were re-analyzed on request: Phase 3 must refresh their Jira comment even when the result is unchanged. The tag is honored only if its author is the account running this command or the tracker's current assignee, and only if it is newer than the last update of the analysis comment, so a tag that was already honored does not force re-analysis again. Tags from anyone else are ignored.

**Cache invalidation:**
- Analysis older than 30 days: re-analyze
- Trusted `[reanalyze]` tag posted after the analysis: re-analyze
- Cached analysis is for a different branch than the current one: re-analyze
- New CVEs (no prior result): always get full analysis

Print the decision per CVE: "CVE-XXXX-XXXXX: reusing prior analysis from YYYY-MM-DD (Reachable)" or "CVE-XXXX-XXXXX: analyzing (<reason>)".

---

### Phase 2: Clone Repos and Analyze CVEs in Parallel

- **Skill**: [analyze-cve-repos](../skills/analyze-cve-repos/SKILL.md)
- **Input**: version-filtered list of unique CVEs from Phase 1, minus cache hits from Phase 1.5
- **Output**: reachability results per CVE

#### Step 1: Determine affected repos, branches, and clone

Analysis targets only the release branch for the selected OCP version, meaning a single release branch per repo per CVE. The `main` branch may have newer dependencies or Go versions that mask vulnerabilities present in shipped releases. Analysis targets downstream forks only.

**Component to repository mapping:** read from `shared/components.md`. Use the "Component to Repository Mapping" table for downstream forks and branch patterns, and the "pscomponent Label Mapping" table for label-based repo resolution. When a tracker carries a `pscomponent:` label that appears in the label table, the label wins over the Jira component for choosing the repository. Otherwise use the component row. (This precedence applies to repo selection only. Tracker ownership for posting is decided by the Jira component alone, see Phase 3.)

**OpenShift version to release branch mapping:** read from `shared/version-map.md` and apply its formulas and branch naming conventions. Do not use a formula from memory or from this file. The map is the only source, and it covers both OCP 4.Y and 5.Y.

**Clone or refresh:** multiple CVEs sharing the same repo and branch use the same directory. One call per repo and branch:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" clone https://github.com/openshift/cri-o release-5.0
```

The second argument is a release branch or a tag. Components that `shared/components.md` maps to upstream tags (conmon, conmon-rs, crun, cri-tools) are cloned at the tag that ships in the selected OCP version, for example `clone https://github.com/containers/conmon v2.1.13`.

The helper clones with `--depth 1` into `.work/node-cve/repos/<repo-name>-<branch>/`. A directory left over from a prior run is refreshed (fetch, hard reset to `FETCH_HEAD`, clean), never cloned over and never analyzed stale. On success it prints `DIR=` and `COMMIT=` (short hash and commit date). Pass both to the analysis agent. Clones are unauthenticated and need no credentials.

- Exit code 3 (`NOT-FOUND`): the fork or branch does not exist. Classify as Uncertain with note "downstream fork/branch not found".
- Exit code 4 (`CLONE-FAILED`): the branch exists but clone or fetch failed (timeout, network). Classify as Uncertain with note "clone failed". Do not report it as a missing branch.

All clones must complete before proceeding to Step 2.

#### Step 2: Analyze CVEs in parallel

Spawn a concurrent analysis agent for each unique CVE. Each CVE has one branch to analyze. Each agent runs the [analyze-cve-repos](../skills/analyze-cve-repos/SKILL.md) skill independently and receives the resolved repo directory, branch, OCP version, and the CVE record. The skill defines the analysis steps, the stdlib handling, and the classification values. In short:

1. Gather CVE intelligence (affected package, vulnerable functions, attack vector, fixed version).
2. Check whether the affected code is present: dependency files for third-party packages, the Go toolchain version for Go standard library CVEs.
3. Analyze source code for reachability.
4. Classify the result using the enum in the skill (`REACHABLE`, `PRESENT_NOT_EXPLOITABLE`, `PRESENT_NOT_REACHABLE`, `UNAFFECTED`, `UNCERTAIN`) with a confidence level.
5. Save the analysis to `<TRIAGE_DIR>/<CVE-ID>-<branch>-analysis.md` (the run directory `init` printed, not a path built from the current date) with file paths, call sites, and evidence.

Wait for all agents to complete, then collect results. Print progress for each: "Analyzed CVE-XXXX-XXXXX against <repo> (<branch>): <result>"

---

### Phase 3: Report Findings

- **Skill**: [report-findings](../skills/report-findings/SKILL.md)
- **Input**: analysis results from Phase 2 and cache hits from Phase 1.5, notification flags, `version_filter`
- **Output**: report file, optional Jira comments, optional Slack message, posting audit log

1. **Generate report** at `<TRIAGE_DIR>/report.md`. The report template lives in [report-findings](../skills/report-findings/SKILL.md) Step 1 and is the only copy. Follow it exactly.

2. **Posting gate (if `--notify-jira`, `--notify-slack`, or `--dry-run`)**: follow [report-findings](../skills/report-findings/SKILL.md) Step 2 before any post:
   - Re-validate every tracker against the Node team component list and the version filter (`validate` subcommand). Skip and log anything that fails.
   - Threshold: if more trackers pass validation than `--max-trackers` (default 50), the helper closes the posting gate and refuses every Jira comment in this run. `--yes` does not bypass this.
   - With `--dry-run`: pass `--dry-run` to every posting subcommand. The would-post list goes to `posting-audit.log` and nothing is posted.
   - Without `--yes` and without `--dry-run`: show the plan (tracker count, tracker keys, Slack channel or webhook mode) and ask the user to confirm once. If the user cannot be asked (headless `--print` run), abort before posting: post nothing and report "ABORTED: posting needs --yes in a headless run". There is no terminal prompt and no TTY check, so a headless run never hangs.

3. **If `--notify-jira`** (and the gate passed): post or update one comment per validated tracker, in Atlassian wiki markup, as described in [report-findings](../skills/report-findings/SKILL.md) Step 3. An existing `node-cve:triage` comment with an unchanged classification is skipped, unless the CVE was re-analyzed because of a trusted `[reanalyze]` tag: then the comment is refreshed, so the tag counts as handled on the next run. A changed classification updates the existing comment in place instead of adding a new one.

4. **If `--notify-slack`** (and the gate passed): post the summary as described in [report-findings](../skills/report-findings/SKILL.md) Step 4. With an API token this is a summary plus a threaded reply. With a webhook it is a single message.

In handoff mode, Phase 3 follows [Handoff mode](#handoff-mode) instead of items 2 to 4.

5. **Audit output**: whenever the gate ran, finish with `audit-summary`, which appends the totals to `posting-audit.log` and prints the whole log to stdout, so headless runs in ephemeral pods keep a record in their job log.

---

### Handoff mode

With `--handoff`, the command posts nothing and hands the posts to the caller in `<TRIAGE_DIR>/posting-plan.json`. The safeguards that run in the command stay: the component and version validation, the `--max-trackers` threshold and the footer check. Deduplication, `[reanalyze]` tags and the Jira comment cache need Jira access, so they move to the caller (see the [node-cve README](../README.md#chai-rws)).

1. Generate the report as usual.
2. If `--notify-jira`, `--notify-slack` or `--dry-run` was given, validate against the supplied rows, with the same candidate file as in [report-findings](../skills/report-findings/SKILL.md) Step 2a:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" validate --max-trackers 50 --trackers .work/node-cve/trackers.tsv 5.0 .work/node-cve/triage-YYYY-MM-DD/candidate-trackers.txt
   ```

3. If `--notify-jira`: write the comment body per tracker exactly as in report-findings Step 3 and add it to the plan, one call per validated tracker. There is no `ADD`/`UPDATE`/`SKIP-UNCHANGED` decision here, every validated tracker gets an entry:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" plan-comment OCPBUGS-XXXXX .work/node-cve/triage-YYYY-MM-DD/CVE-XXXX-XXXXX-comment.txt
   ```

4. If `--notify-slack`: write the summary and details files as in report-findings Step 4, then run `plan-slack` with the same `--header`, `--summary` and `--details` options as `slack`.
5. Finish the plan and print it, then run `audit-summary` with mode `handoff`:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" plan-show 5.0
   ```

   Add `--dry-run` after the version when `--dry-run` was given, so the caller knows not to post. When the threshold closed the gate, `plan-show` drops all Jira entries.

No confirmation is asked and `--yes` is not needed, since the command posts nothing. The caller decides whether to post.

---

### Phase 4: Summary Output

Print a final summary grouped by classification with bold section headings. Include the version scope in the headline:

```text
Node CVE Triage (N CVEs analyzed, OCP <version>)
🔴 Reachable: N (M unassigned)
🟡 Present: N (M unassigned)
🟢 Unaffected: N (M unassigned)
⚠️ Uncertain: N (M unassigned)

**Reachable (action required):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Present (no action needed):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Unaffected:**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Uncertain (needs manual investigation):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, low confidence, N trackers[, M unassigned])

Report: .work/node-cve/triage-YYYY-MM-DD/report.md
```

Rules for this output (do not print these rules):
- A tracker counts as unassigned when its assignee is empty or a placeholder account (`ocp-sustaining-blocked-trackers`, `Node Team Bot Account`). Only show "(M unassigned)" when M > 0.
- Omit empty sections. Each section heading must be bold or visually distinct from the CVE entries beneath it.
- "Present" groups `PRESENT_NOT_EXPLOITABLE` and `PRESENT_NOT_REACHABLE`, since both mean no urgent action is needed. The detailed classification is preserved in the per-CVE report and Jira comments.
- Headline on a first run: "Node CVE Triage (N CVEs analyzed, OCP <version>)". With cached results: "Node CVE Triage (N CVEs, M new, OCP <version>)". If classifications changed since the last run, also show "K updated".
- If trackers were skipped during validation, print a warning line before the report path, for example "⚠️ Skipped N trackers during posting (K non-Node-component, J wrong version), see posting-audit.log". Omit the line when the skip count is 0.
- With `--dry-run`, print "Dry run: nothing was posted. Would post to N trackers, see posting-audit.log".
- With `--handoff`, print "Handoff: nothing was posted. N Jira comments[ and the Slack summary] in <TRIAGE_DIR>/posting-plan.json", and end the output with the JSON that `plan-show` printed, so the caller gets the plan from the command output.
- In a headless run with a notify flag but without `--yes`, print "ABORTED: posting needs --yes in a headless run. Nothing was posted."
- If the `--max-trackers` threshold aborted posting, print "ABORTED Jira posting: N trackers exceeds --max-trackers <limit>".

## Return Value

- **Format**: text summary on stdout (Phase 4) plus files under `.work/node-cve/triage-YYYY-MM-DD/`: `report.md`, `cves.json`, one `<CVE-ID>-<branch>-analysis.md` per analyzed CVE, `posting-audit.log` when `--notify-jira`, `--notify-slack`, or `--dry-run` was used, and `posting-plan.json` with `--handoff`.
- Every outward-facing post (or would-post) is also appended to `.work/node-cve/posting-history.log`, which is kept across runs.

## Arguments

- `--component <name>`: Filter to a single OCPBUGS component. Must match a Node team component name exactly (for example "Node / CRI-O"). Optional. If omitted, ALL Node team components are included, and only Node team components, never all OCPBUGS components.
- `--ocp-version X.Y`: OCP version to triage (for example `5.0`). Optional. Default: auto-detected from a query that is not narrowed by `--days` or `--component`. Use it when several in-development versions have open trackers and the highest one is not the release the team currently triages.
- `--days N`: Only include CVEs created or updated in the last N days. Default: all open CVEs.
- `--notify-jira`: Post analysis as a comment on each validated Jira tracker. Requires `JIRA_API_TOKEN`. Also enables cross-run caching via Jira comments. Default: off.
- `--notify-slack`: Send a summary to Slack. Requires `SLACK_API_TOKEN` (channel from `SLACK_CHANNEL`, default `GK6BJJ1J5`) or `SLACK_WEBHOOK`. Default: off.
- `--dry-run`: Run query, analysis, report, and validation, then record what would be posted in `posting-audit.log`. Posts nothing to Jira or Slack, even if `--yes` is given.
- `--yes`: Do not ask for confirmation before posting. Required for headless posting: without it a headless run aborts before posting. Does not bypass validation or `--max-trackers`.
- `--max-trackers N`: Refuse all Jira posting if more than N trackers pass validation. Default: 50. One OCP version across the Node components normally yields far fewer. A higher number signals a scoping bug.
- `--handoff`: Make no Jira or Slack calls. Validate against the `--trackers` rows and write `posting-plan.json` for the caller to post. For runners whose worker has no Jira or Slack credentials, such as Chai RWS.
- `--trackers FILE`: Tracker rows from the caller's Jira search, tab-separated in the `search` output format (key, summary, components `;`-separated, status, assignee, labels `,`-separated). Required with `--handoff`, not accepted without it.

## Examples

1. **Triage without posting anything (default)**:
   ```text
   /node-cve:triage
   ```

2. **Preview what would be posted**:
   ```text
   /node-cve:triage --notify-jira --notify-slack --dry-run
   ```

3. **Triage CRI-O CVEs only and post to Jira after confirmation**:
   ```text
   /node-cve:triage --component "Node / CRI-O" --notify-jira
   ```

4. **Headless run with Jira and Slack notification**:
   ```bash
   claude --print "/node-cve:triage --notify-jira --notify-slack --yes"
   ```

5. **Pin the OCP version, recent CVEs only**:
   ```text
   /node-cve:triage --ocp-version 5.0 --days 7
   ```

6. **Handoff run on Chai RWS** (the coordinator wrote the tracker rows and posts the plan):
   ```text
   /node-cve:triage --handoff --trackers .work/node-cve/trackers.tsv --notify-jira --notify-slack
   ```

## Notes

- The Jira query uses OCPBUGS component names from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md).
- **Version scope:** one OCP version per run. The sustaining team owns triage for all earlier versions. The version is detected at runtime from an un-narrowed query, or set with `--ocp-version`, so no release is hardcoded in this plugin.
- **Cross-team safeguard:** the command filters to Node team components at query time (Phase 1) AND re-validates each tracker's component immediately before posting any Jira comment (Phase 3). Never write or run an ad-hoc Jira search scoped only by CVE ID to find trackers to comment on. A CVE can span 200+ trackers across dozens of unrelated OpenShift teams, and a CVE-ID-only search returns all of them. Always reuse the already-filtered `tracker_keys` from Phase 1. Any tracker that fails the component or version re-validation is skipped and logged in `posting-audit.log`, never posted to.
- **Secrets:** the helper passes tokens to `curl` through a config on stdin (`curl -K -`), never as command-line arguments, and never echoes them or writes them to files.
- **Tool footprint:** the only Bash command is the helper script. File work uses the Read, Grep, Glob and Write tools, and CVE research uses WebSearch and WebFetch.
- Each CVE typically has multiple tracker issues (one per OCP version). The command deduplicates by CVE ID and filters to one version's trackers before analysis.
- Analysis targets downstream forks only (for example openshift/cri-o). If the downstream fork or branch does not exist, the CVE is classified as Uncertain. Dependency versions and Go toolchain versions differ across releases, so version-specific branches are used.
- Large repos like openshift/kubernetes may take longer to analyze. The helper uses `--depth 1` clones for speed.
- Reachability analysis is performed by Claude reading the source code directly, not by external tools. This works across Go, Rust, and C codebases.
- Jira comments use Atlassian wiki markup (not Markdown), which requires the Jira REST API v2 comment endpoints.
- The command does not modify any code or create PRs. It only reads, analyzes, and reports.
- Reports and artifacts are saved to `.work/node-cve/` (gitignored). `/node-team:cleanup` purges old `triage-*` directories and the `repos/` clones.
