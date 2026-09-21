---
name: query-open-cves
description: Query and deduplicate open CVE vulnerability issues from OCPBUGS for Node team components
---

## When to Use

Use this skill when Phase 1 of the `node-cve:triage` command needs to fetch all open CVE trackers from Jira and deduplicate them into a list of unique CVEs.

## Prerequisites

- `bash`, `curl` and `jq`
- Environment variables: `JIRA_API_TOKEN`, and `JIRA_USER` (or `JIRA_EMAIL`) with the Jira login. Set it explicitly in containers, where the `git config user.email` fallback does not exist.
- Network access to Jira instance
- The `node-team` plugin (shared component and version data)

## Locating shared data and the helper script

The links to `node-team` files below resolve in a repository checkout and on the docs site. When the plugins are installed they do not resolve, because every plugin lives in its own versioned cache directory. Get the real directory from the helper script, then read the files from there with the Read tool:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" refs
```

The helper script is [node-cve-lib.sh](../report-findings/scripts/node-cve-lib.sh). It is the only Bash command this plugin needs, which keeps headless runs with a strict tool allowlist working. Do not write ad-hoc `curl`, `jira` or `git` commands and do not chain commands. Use the Read, Grep, Glob and Write tools for file work. Shell variables do not persist between Bash tool calls, so pass values as literal arguments.

If `refs` fails, invoke the `node-team:node` skill and read `references/shared/` from its base directory. If the files still cannot be found, stop with "node-team shared references not found". Never fall back to data from memory.

## Implementation Steps

### Step 1: Load Node team components

Read the CVE-tracked component list from the [node-team shared components reference](../../../node-team/skills/node/references/shared/components.md). Use the full "Jira Components (OCPBUGS)" list plus the additional CVE triage components (Driver Toolkit, Machine Config Operator).

The helper's `init` subcommand extracts these names into `.work/node-cve/node-components.txt` (the triage command runs it in Phase 0). Do not write the file by hand. The posting-time validation in Phase 3 reads the same file.

**Default behavior (no `--component` flag): include ALL Node team components, and ONLY Node team components.** "No flag" does not mean "no filter". It means "the full Node component list". Never construct a query that omits the component filter entirely, even when no `--component` value was given.

If `--component` was specified, only that single component is queried. The value must match an entry in the component file exactly. If it does not, the helper prints the valid component names and exits, rather than falling back to an unfiltered query.

The Jira saved filter "Node Components" (ID 91645) does not include Driver Toolkit and Machine Config Operator, so the explicit list from the shared reference is used for CVE queries to ensure completeness.

**CRITICAL SAFEGUARD:** This component filter is what scopes every downstream step (analysis, reporting, and above all Jira comment posting in Phase 3) to Node team trackers only. Many CVEs (especially Go stdlib or vendored-dependency vulnerabilities) have 50-200+ tracker issues across dozens of OpenShift teams. Omitting or bypassing this filter, for example by later re-querying Jira with only a CVE ID and no component constraint, is what caused the 2026-07-15 incident where Node-specific analysis was posted to ~200 non-Node trackers (HyperShift, Storage, Networking, Installer, etc.). See the [report-findings](../report-findings/SKILL.md) "Node Team Component Safeguard" section for the posting-time re-validation this feeds into.

### Step 2: Query Jira

Run the search through the helper. It builds the JQL itself, and the `component in (...)` clause is part of every query it sends, whether or not `--component` was passed:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" search --out .work/node-cve/trackers.tsv
```

Options: `--component "Node / CRI-O"` (single component, must be in the component file) and `--days N` (adds `AND updated >= -Nd`).

What the helper does:
- Builds `project = OCPBUGS AND type = Vulnerability AND component in ("Node / CRI-O", "Node / Kubelet", ...) AND status not in (Closed, Done, Verified)`. Component names contain spaces and slashes, so each one is double-quoted inside the JQL. The JQL travels in a JSON body, so no shell quoting is involved. The JQL is printed for the record.
- Calls `POST /rest/api/3/search/jql` and follows `nextPageToken` until the last page. The `jira` CLI is not used for this: on Jira Cloud its `--paginate <from>:<limit>` offset is ignored, so it never returns more than the first 100 results, and its plain output has no component column.
- Retries on HTTP 429 using `Retry-After`. On any other error it exits non-zero and writes no output file.
- Passes credentials to `curl` on stdin, never on the command line.

Output columns (tab-separated): key, summary, components (`;`-separated), status, assignee display name, labels (`,`-separated). Read the file with the Read tool.

**Sanity check:** After fetching results, verify that every component in the third column (`;`-separated when a tracker has several) is in the Node team component list, or equals the `--component` value. If any row has an unexpected component, this indicates a JQL construction bug. Log a warning with the offending tracker key and component, and exclude that row rather than propagating it downstream.

**Handoff mode** (`--handoff`): there is no Jira access and `search` is refused. The caller supplies the rows in the same format with `--trackers FILE`, from a search with the JQL that `node-cve-lib.sh jql` prints (all Node components, no `--days`). Read that file instead of `trackers.tsv`. It serves the version detection as well. Apply the sanity check above to it.

**Version detection query:** when `--days` or `--component` narrowed the query above and `--ocp-version` was not given, run the search once more without those options, with `--out .work/node-cve/trackers-all.tsv`. Step 5 detects the version from that file only. When the query was not narrowed, `trackers.tsv` serves both purposes.

### Step 3: Parse results

For each row in the output:
1. Extract the issue key (e.g., `OCPBUGS-85948`)
2. Extract the CVE ID from the summary using regex: `CVE-[0-9]{4}-[0-9]+`
3. Extract the OCP version from the summary brackets: `\[openshift-([^\]]+)\]`
4. Extract component name
5. Extract status and assignee
6. Extract labels (preserve `pscomponent:*` labels for Phase 2 repo mapping)

### Step 4: Deduplicate by CVE ID

Group all tracker issues by CVE ID. For each unique CVE, build a record:

```json
{
  "cve_id": "CVE-2026-32281",
  "summary": "Go crypto/x509: Denial of Service via inefficient certificate chain validation",
  "components": ["Node / CRI-O"],
  "status": "New",
  "assignee": "ocp-sustaining-blocked-trackers",
  "tracker_keys": ["OCPBUGS-85948", "OCPBUGS-85932", "OCPBUGS-85914", "..."],
  "affected_versions": ["4.18.z", "4.19.z", "4.20.z", "4.21", "4.22", "4.23", "5.0"],
  "labels": ["pscomponent:cri-o", "SecurityTracking"]
}
```

A single CVE may span multiple components (e.g., both "Node / CRI-O" and "Machine Config Operator"), so `components` is an array collecting all distinct component values across tracker issues for that CVE.

Use the highest version tracker for the "primary" assignee and status (issues on newer versions are typically more actively managed).

### Step 5: Determine the OCP version and filter to it

The Node team triages one OCP version: the latest in-development release. All other versions belong to the sustaining team.

**The version must never be derived from a narrowed result set.** With `--days N` or `--component`, the results may contain no tracker for the real latest version. The highest version present (for example an older z-stream) would then be selected, and analysis would be posted to sustaining-owned trackers. The posting-time check uses the same `version_filter`, so it would not catch the mistake.

1. **`--ocp-version X.Y` given:** validate that it matches `<digits>.<digits>` and use it as `version_filter`. Set `version_source` to `"argument"`. Skip to item 5.
2. **Otherwise auto-detect** from the un-narrowed tracker list (`trackers-all.tsv` when the query was narrowed, else `trackers.tsv`, see Step 2). If that list is empty, return an empty CVE list with `version_filter: null` and print: "No open CVEs found; version auto-detection skipped."
3. Collect all OCP versions from the summaries. **Discard non-numeric versions:** only `<digits>.<digits>`, optionally followed by `.z`, is valid. Discard anything else (`latest`, `nightly`, ...) with a warning. If no valid version remains, return an empty CVE list with `version_filter: null` and print: "No valid numeric OCP versions found in tracker summaries; version auto-detection failed."
4. Determine the latest version. `bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" versions <file>` prints the tracker count per valid version, highest first, and reports invalid version strings on stderr. The rules it applies:
   - Strip trailing `.z` suffixes for comparison (`.z` marks a maintenance stream).
   - Parse each version as `(major, minor)`, for example `5.0` is `(5, 0)` and `4.14.z` is `(4, 14)`.
   - Sort descending by major, then minor. The first entry is the latest. `version_filter` always stores the stripped `major.minor` form. Set `version_source` to `"auto-detected"`.
   - Print the top three detected versions with their tracker counts, so the operator can see what was considered.
5. **Sanity-check against `shared/version-map.md`:**
   - The version must be covered by one of the formulas in the map (OCP 4.Y or OCP 5.Y). If the map has no formula for that major version, stop with: "OCP <version> is not covered by version-map.md. Update node-team or pass --ocp-version."
   - Derive the release branch for one affected repo per the map's branch naming and confirm it exists with the helper's `clone <fork-url> <branch>` subcommand (exit code 3 means the branch does not exist; the clone is reused in Phase 2). If it does not exist, the version is probably too new to have branched. Stop and ask the user to pass `--ocp-version` (in a headless run: stop with that message). Never silently fall back to a lower version.
   - If several versions without a `.z` suffix have open trackers (for example two in-development releases at once), say so and name the one selected, so the operator can override it with `--ocp-version`.
6. For each CVE record from Step 4, keep only trackers whose version equals `version_filter` after stripping `.z` from the tracker version. If a CVE has no remaining trackers, exclude it entirely.
7. Rebuild each CVE record's metadata entirely from the retained tracker set. Per-tracker associations (component, labels, assignee, status) must be preserved during Step 4 so they can be used here. Recompute `tracker_keys`, `affected_versions`, `components`, `labels`, `assignee`, `status`, and `is_unassigned`. No metadata from removed trackers may leak into Phase 2 (repo selection) or Phase 3 (reporting).
8. Print: "Version filter: <version> (<auto-detected|from --ocp-version>). Other versions are triaged by the sustaining team."

### Step 6: Identify unassigned CVEs

Flag CVEs where:
- Assignee is empty or a placeholder account (`ocp-sustaining-blocked-trackers`, `Node Team Bot Account`)
- Status is "New" (not yet picked up)

## Return Value

```json
{
  "skill": "query-open-cves",
  "status": "success",
  "version_filter": "5.0",
  "version_source": "auto-detected",
  "total_trackers": 8,
  "total_trackers_before_version_filter": 45,
  "unique_cves": 6,
  "cves": [
    {
      "cve_id": "CVE-2026-32281",
      "summary": "...",
      "components": ["Node / CRI-O"],
      "status": "New",
      "assignee": "ocp-sustaining-blocked-trackers",
      "is_unassigned": true,
      "tracker_keys": ["OCPBUGS-85948"],
      "affected_versions": ["5.0"],
      "labels": ["pscomponent:cri-o"]
    }
  ]
}
```

`version_filter` is the selected OCP version in stripped `major.minor` form (the `5.0` above is only an example). `version_source` is `"auto-detected"` or `"argument"`. `version_filter` is `null` when no version could be detected (zero Jira rows or all extracted versions were non-numeric). In that case `cves` is an empty array. Downstream consumers must check for `null` before using `version_filter` as a version string.

## Error Handling

- If the `search` subcommand exits non-zero, print its error and exit. Never treat a failed query as "0 CVEs". Common causes: expired API token (HTTP 401), network issues, invalid JQL (HTTP 400, check the quoting of component names).
- HTTP 429 is retried by the helper with the `Retry-After` delay, up to 5 attempts per page.
- If the node-team shared references cannot be found, exit with an error (see "Locating shared data").
- If the query returns 0 results, return an empty list (not an error).
- If a CVE ID cannot be extracted from a summary, log a warning and skip that tracker.
