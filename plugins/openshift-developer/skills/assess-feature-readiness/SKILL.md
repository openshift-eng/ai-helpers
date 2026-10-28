---
name: assess-feature-readiness
description: Assess readiness of all OCPSTRAT features targeting a release by running checks R1–R13 against each feature. Produces a markdown report and JSON sidecar. Use when QE leads, release managers, or WG participants need a release-level quality snapshot.
allowed-tools: Read Write Bash(python3 *) Bash(gh *) Grep
---

## Name
openshift-developer:assess-feature-readiness

## Synopsis
```text
/openshift-developer:assess-feature-readiness <release-version|OCPSTRAT-KEY> [--team <component>] [--check dor|dod] [--sippy]
```

## Description
Evaluates OCPSTRAT Features against 13 readiness checks (R1–R13) covering Definition of Ready, Definition of Done, and Release Pending eligibility. Produces a markdown readiness report in chat and a scoped JSON sidecar.

**Audience**: QE leads, release managers, team leads, WG meetings.

**Accuracy rule**: Never emit ❌ for a field or remote-link source that was not confirmed present in the fetch. Prefer ⚠️ Unknown over a false gap. Headline 0%/100% results must be calibration-flagged when they saturate.

### Scoping modes

The first positional argument determines scope:

| Mode | `$1` | Scope |
|---|---|---|
| **Release-wide** | `openshift-5.1` or `5.1` | All OCPSTRAT Features targeting this release |
| **Team-scoped** | `openshift-5.1 --team networking` | Features whose Jira `components` include the given component (**case-insensitive**) |
| **Single-feature** | `OCPSTRAT-2962` | One specific feature — full detail, no aggregation |

### Check filter

| Mode | Flag | Checks run |
|---|---|---|
| Full scan (default) | _(none)_ | R1–R13 |
| DoR only | `--check dor` | R1, R6, R8, R9 |
| DoD only | `--check dod` | R2, R3, R4, R5, R7, R10, R11, R12, R13 |

`--sippy` enables optional Sippy queries for R10 (off by default; always record `sippy_attempted`).

### Output grouping (release-wide and team-scoped modes)

When reporting on multiple features, the output is **grouped by team** (the Jira `components` field). Each team section includes a per-team summary followed by its features. Features with multiple components appear under each applicable team. A feature with no components appears under an "Unassigned" group.

## Implementation

### Step 1: Parse input

1. Accept `$1` as the first positional argument.
2. **Determine scope**:
   - If `$1` matches an OCPSTRAT issue key pattern (e.g. `OCPSTRAT-2962`): **single-feature mode**. Still run Steps 2–3 (tool discovery + cloudId). Step 4's single-feature branch fetches the one issue.
   - Otherwise treat `$1` as a release version string:
     - Strip the `openshift-` prefix if present (e.g. `openshift-5.1` → `5.1`).
     - Validate: must match pattern `X.Y` where X and Y are integers. Reject with an error if invalid.
     - Reconstruct the full release string as `openshift-X.Y` for Jira queries.
3. **Parse `--team`** (optional, release-wide mode only): store the component name. Matching is **case-insensitive** against Jira component names.
4. **Parse `--check`** / **`--sippy`** (optional): If `--check dor`, report only DoR checks: R1, R6, R8, R9. If `--check dod`, report only DoD checks: R2, R3, R4, R5, R7, R10, R11, R12, R13. Otherwise report all R1–R13. **Important**: some checks depend on others as prerequisites (R8 needs R4's work items, R9 needs R1+R2+R6, R7 needs R1+R4+R6, R13 needs R1+R3+R5+R10+R12). Always compute prerequisite checks internally even in filtered mode — only limit which checks appear in the reported output. Sippy is attempted only when `--sippy` is set.

### Step 2: Choose a Jira data path

Prefer Jira MCP when it works. **Authenticated Jira Cloud REST is also valid** (same authoritative API) when MCP is unavailable or needs auth the session does not have — e.g. `JIRA_API_TOKEN` + Atlassian email/user in the shell, or equivalent curl/`gh`-style helpers already used by the operator. Never scrape HTML or guess field values. Do **not** narrate which path you chose in the markdown report (see Step 7 Report hygiene).

**MCP path (preferred when available):**

1. Inspect available tool metadata for candidate namespaces, preferring this order when present:
   - `mcp__atlassian__*`
   - `mcp__plugin_jira_atlassian__*`
   - `mcp__user_jira__*`
2. From the chosen namespace, note the issue tool name (`jira_get_issue` / `getJiraIssue`), the search tool (`jira_search` / `searchJiraIssuesUsingJql`), and `getAccessibleAtlassianResources` (or equivalent).
3. Proceed to Step 3 to acquire `cloudId` **before** the first issue fetch.

**REST fallback:** If no MCP namespace works (timeout, OAuth required, missing tools) and credentials such as `JIRA_API_TOKEN` are available, call `https://redhat.atlassian.net/rest/api/2/` (or `/rest/api/3/`) for issue get, JQL search, remotelink, and field catalog. Use the same field list and remote-link rules as Step 4. Record `data_path: "rest"` only in the JSON sidecar.

### Step 3: Acquire cloudId (MCP path)

Call `getAccessibleAtlassianResources` (from the discovered namespace) to obtain the `cloudId`. This cloudId is required for MCP-backed Jira calls — including single-feature mode. If the namespace provides the cloudId automatically, extract it from the response. Skip this step when using the REST fallback (host + token are enough).

Only after `cloudId` is available on the MCP path, make a smoke-test issue/search call if needed to confirm the selected tool names. Use the chosen path (MCP **or** REST) consistently for **all** subsequent Jira calls in the run.

### Step 4: Query OCPSTRAT features

**Both modes** use the same per-issue field list and the same separate remote-links fetch below.

**Per-run workspace (required):** Before fetching, choose a unique `RUN_ID` (`YYYYMMDD-HHMMSS`) and a dedicated features directory:
```text
FEATURES_DIR=.work/assess-feature-readiness/runs/<RUN_ID>/features
```
Create that directory empty for this run. **Do not** reuse or append into a shared `features/` folder from a prior scan — leftover JSON would be scored again in Step 5. Pass this same `FEATURES_DIR` to `evaluate_checks.py`.

**Single-feature mode**: Fetch the one issue by key using the field list in **Step 4.3**, then fetch remote links for that issue using **Step 4.4**. Populate `features[]` with that single entry. Run **Step 4.3b** on it. **Persist** the payload under `$FEATURES_DIR/<KEY>.json` (same as Step 4.5) **before** skipping to Step 5 so `evaluate_checks.py` can read it. If description is Atlassian Document Format (ADF object), flatten to plain text **before** persistence (or rely on the evaluator's ADF flattener — never leave a raw dict for R2/R3 regexes without conversion).

**Release-wide mode**:

1. Build JQL using the configured `target_version_field` from [references/readiness-criteria.md](references/readiness-criteria.md) Configuration (default `Target Version`) — substitute that name; do not hardcode a different field:
   ```
   project = OCPSTRAT AND type = Feature AND "<target_version_field>" = "openshift-X.Y"
   ```
   Example with the default: `... AND "Target Version" = "openshift-X.Y"`.
   If `--team <component>` was provided, prefer fetching the release set then filtering **case-insensitively** on `components` (Jira JQL `component =` can be case-sensitive). You may still append `AND component = "<component>"` when the instance matches case, but always verify matches case-insensitively after fetch.
2. Use `maxResults = 50` and paginate until exhausted. Follow the selected search tool's pagination contract: Rovo / `searchJiraIssuesUsingJql` uses `nextPageToken` / `isLast`; use `startAt` only for tools that support offset pagination. Apply the same rule to Epic-child and Feature-parent searches in R4. Track MCP calls against the global budget in Step 5.
3. For each feature, request fields: `summary`, `description`, `priority`, `status`, `subtasks`, `issuelinks`, `comment`, `labels`, `components`, and the configured QA Contact field ID from [references/readiness-criteria.md](references/readiness-criteria.md) Configuration (`qa_contact_field`, default `customfield_10470` on redhat.atlassian.net). Substitute that configured value — do not hardcode a different ID. **Do not** request `remotelinks` as an issue field — remote links are not part of the main issue response (`/rest/api/3/issue/{key}`); they live at `/rest/api/3/issue/{key}/remotelink`. Include `comment` so the remote-link fallback can find URLs that exist only in comments.
   3b. **Verify field acquisition before running any check.** Run the key check on **every** fetched feature (not only the first). Absent key ≠ null value.
   - Per feature, build `fields_missing[]` for that payload; union into a run-level `fields_missing[]`.
   - If `qa_contact_field` is missing on a feature → that feature's R6 is `unfetched` / ⚠️ Unknown. If it is missing on the first feature (or systematically across the run): resolve once via the Jira field catalog by **name** `QA Contact`, set **`effective_qa_contact_field`** to that ID for the rest of the run, **re-fetch** any payloads already requested under the stale configured ID so they include the resolved key, and record the resolved ID only in the JSON sidecar — do **not** narrate field-ID remapping in the markdown report. If catalog resolve fails, keep R6 as Unknown and leave `effective_qa_contact_field` as the configured ID.
   - If `comment` is missing on a feature → that feature's `comments_available: false`; R1/R11/R12 must not emit ❌ from a missing-URL conclusion — only ⚠️ Unknown — until comments are fetched separately and succeed.
   - If `description` is missing on a feature → do not merge description-sourced URLs; R1/R2/R3/R9/R12 description-dependent paths return ⚠️ Unknown when no substitute evidence exists (never ❌ Missing / Unfilled solely from a missing description key).
   - Record `fields_missing[]`, `qa_contact_field_fetched`, and `comments_available` at the top level of the **JSON sidecar** (and per-feature when they differ). The markdown report only surfaces these when they change how a reader should interpret a check — see Step 7 **Report hygiene**.
   - If ≥2 required fields are missing on the first feature, **STOP** and report rather than scanning 200+ features against a broken fetch.
   - Prefer the helper: `python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" verify-fields --feature <path> --qa-field <configured-qa_contact_field>`.
4. **Fetch remote links separately** for each feature (required for R1, R9, R10, R11, R12):
   - Confirm the parameter/tool name for the discovered MCP namespace (examples seen elsewhere: `properties=remoteLinks`, `include="remote_links"`, or a dedicated remote-links call). Name the tool in logs only after it is confirmed to return data.
   - Attempt the remote-links call. Set `remote_links_status` on the feature:
     - `"ok"` — call succeeded (list may be empty)
     - `"unavailable"` — tool missing, call failed, or response unusable (distinguish from a true empty list)
     - Do **not** treat `"unavailable"` as `"ok"` with zero links
   - When the call succeeds, collect remote link entries (`title`/`url`).
   - **Always** also scan the description **and comments** (when `comments_available`) for artifact URLs and **merge** them into `remote_links[]` — even when the remote-link response is nonempty. If comments are truncated, fetch comments separately and paginate until exhausted before concluding no URL exists.
   - Deduplicate by URL, then store `remote_links[]` plus `remote_links_status`.
   - Dependent checks must propagate ⚠️ Unknown when `remote_links_status == "unavailable"` (or comments unavailable) and no substitute URL was found — never invent ❌ Missing from a failed fetch.
5. Store all features in a `features[]` array with their full issue data plus `remote_links[]` and `remote_links_status`. Persist raw payloads under `$FEATURES_DIR/` for this run only (see per-run workspace above).
6. **Empty-result stop**: if `features[]` is empty after JQL + team filter, **STOP**. Report the exact JQL executed, the resolved `target_version_field`, the `--team` value (if any), and suggest verifying component names. When `--team` matched nothing, list distinct component values seen in the unfiltered release set (if available). **Never emit an all-zero readiness report for an empty set.**
7. Report the total feature count (and team filter if applicable) to the user before proceeding.

### Step 5: Per feature — run readiness checks

For each feature in `features[]`, run the checks specified by the invocation mode. Read [references/readiness-criteria.md](references/readiness-criteria.md) for the complete specification of each check (R1–R13).

**Deterministic matchers**: for R1/R6/R8 field-presence and quality-item classification, use the committed helper rather than reinventing regexes:

```sh
# Pass the *effective* QA Contact field ID for this run (resolved catalog ID if
# Step 4.3b remapped; otherwise the configured default customfield_10470).
QA_FIELD="<effective_qa_contact_field from this run>"
FEATURES_DIR=".work/assess-feature-readiness/runs/<RUN_ID>/features"
python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" selftest
python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" evaluate \
  --features-dir "$FEATURES_DIR" \
  --qa-field "$QA_FIELD"
```

Do **not** reimplement R8 with bare `kw in summary` substring checks — that falsely matches `"latest"` → `test`. Always pass the **effective** `qa_contact_field` actually used for fetches in this run (not a stale configured ID after catalog resolve). The evaluator flattens ADF `description` objects to text; prefer converting at fetch time before persistence.

**Check summary** (see reference file for full details):

| Check | Question | Phase | DoR | DoD |
|---|---|---|---|---|
| R1 | Test plan linked? | Planning | ✅ | — |
| R2 | Template filled? | Planning | — | ✅ |
| R3 | Quality Status populated? | Stabilization | — | ✅ |
| R4 | Work items exist? | Development | — | ✅ |
| R5 | Work items done? | Development | — | ✅ |
| R6 | QA contact assigned? | Planning | ✅ | — |
| R7 | Priority vs coverage adequate? | Stabilization | — | ✅ |
| R8 | Quality work items created? | Planning | ✅ | — |
| R9 | DoR criteria met? | Planning | ✅ | — |
| R10 | Tests visible in CI? | Development | — | ✅ |
| R11 | PR verification evidence? | Development | — | ✅ |
| R12 | Documentation exists? | Development | — | ✅ |
| R13 | Release Pending eligible? | Stabilization | — | ✅ |

**Data reuse**: R2 and R3 share the same description fetch. R4 feeds R5 and R8. R1 and R6 feed R9. Avoid redundant MCP calls by reusing fetched data across checks.

**Global MCP call budget**: default **1500** calls per invocation. Count every issue/search/remote-link/comment page. When the budget is exhausted: finish the feature currently in progress, mark remaining features `not_assessed`, record `mcp_calls_used` / `mcp_call_budget` in the **JSON sidecar**, and surface only the **Not assessed (budget)** count in the Release Summary. Do not put call-budget counters, MCP/REST transport notes, or credential details in the markdown report.

**Hierarchy traversal**: R4 uses **two-level traversal** — for each OCPSTRAT Feature, it collects direct subtasks and Feature `issuelinks` (level 1), also searches `parent = <feature-key>` for children that omit those fields, then expands each linked engineering Epic via JQL `parent = <epic-key>` **plus Epic `subtasks` only** (level 2). Do **not** count an Epic's arbitrary `issuelinks` as children. Cap at 20 Epics per feature to bound API calls. **If the cap is hit, or any required parent/Epic-child search or page fails**, set `traversal_complete = false` and treat R5 `%` as an incomplete sample (never report ✅ All Done / R13-eligible 100% from a truncated or failed set). See [references/readiness-criteria.md](references/readiness-criteria.md) for the full R4/R5 specification.

```
OCPSTRAT Feature (assessed)
  ├── subtasks[]              ← level 1: direct children
  ├── issuelinks[]            ← level 1: linked Epics, Stories, Tasks
  ├── parent = <feature-key>  ← level 1: children missing from the fields above
  │     ├── SPLAT-2137 (Epic)
  │     │     ├── Story-1     ← level 2: parent=<epic> + epic subtasks only
  │     │     └── Story-2     ← (Epic issuelinks are NOT children)
  │     └── OSDOCS-20703 (Epic)  ← excluded from R4/R5 (passed to R12)
  │           └── Task-1      ← not counted in engineering totals
  └── (R5 computes completion % across engineering items only from both levels)
```

### Step 6: Aggregate results

1. Compute per-feature verdicts using the verdict logic:
   ```
   # Count hard failures: ❌ and 🔴 (e.g. R13 Not Eligible) both count as failed
   # ⚠️ Unknown does not count as failed, but any Unknown blocks READY
   failed = count(❌ checks) + count(🔴 checks)
   unknowns = count(⚠️ checks)

   IF priority ∈ {Critical, Blocker} AND (R1=❌ OR R4=❌ OR R6=❌):
     verdict = 🔴 CRITICAL
   ELIF failed >= 4:
     verdict = 🔴 AT RISK
   ELIF failed >= 1 OR unknowns >= 1:
     verdict = ⚠️ PARTIAL
   ELSE:
     verdict = ✅ READY
   ```
   Ready requires zero hard failures **and** zero unknowns (a lone R13 Unknown must be Partial, not Ready).
2. **Group features by team**: Use each feature's Jira `components` field to assign it to team groups. In release-wide mode, a feature with multiple components appears under each. Features with no components go under `"Unassigned"`. In **team-scoped mode** (`--team`), only the filtered component's section appears in the output — other components from multi-component features are not shown as separate groups. Match `--team` **case-insensitively**.
3. Per-team stats: For each team group, count `total`, `ready`, `partial`, `at_risk`, `critical`.
4. Release-level stats: Count overall totals, `% with plans` (**only R1=linked**), `% template filled`, `no_qa_contact` (**only R6=`empty`**), `qa_contact_unknown` (**R6=`unfetched`/`unknown`**), `critical gaps`, `not_assessed`.
5. **Saturation / calibration check** (required when ≥10 features assessed): for each check, if a single verdict accounts for **100%** of results, add a calibration flag rather than reporting the number bare. Use the **English check name** in the markdown (JSON may keep `R<n>`):
   `⚠️ CALIBRATION: <English check name> returned <verdict> for 100% of N features. This is consistent with either a genuine org-wide gap or a data-acquisition failure. Verify before acting: <what that check depends on>.`
   Place these flags **above** the Release Summary table. Helper: `python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" saturation --report <sidecar>`.
6. Sort: within each team group, sort features by gap severity (critical first). Sort team groups by worst verdict (teams with critical gaps first).
7. **Single-feature mode**: Skip grouping. Present the one feature's full check-by-check detail directly, with **English check names** in the Check column (not bare `R1` / `R4`).

### Step 7: Produce output

Generate two outputs with **scoped, collision-safe filenames** (include seconds; never clobber a prior run in the same minute):

- Markdown: `.work/assess-feature-readiness/readiness-report-<scope>-<release|team|key>-<YYYYMMDD-HHMMSS>.md`
- JSON: `.work/assess-feature-readiness/readiness-report-<scope>-<release|team|key>-<YYYYMMDD-HHMMSS>.json`
- Prefer writing under `.work/assess-feature-readiness/runs/<RUN_ID>/` alongside `$FEATURES_DIR`. Also copy/symlink the JSON to `readiness-report-latest.json` in `.work/assess-feature-readiness/` for convenience.

`<scope>` is `release`, `team`, or `feature`. Examples: `readiness-report-team-networking-20261116-143045.json`, `readiness-report-release-openshift-5.1-20261116-150012.json`.

#### Markdown report (shown in chat)

**Report hygiene (required — all scopes, including single-feature / `--check dor|dod`)**: The chat markdown is for QE leads, release managers, and WG readers. It must contain **feature readiness results only**.

**Never include in the markdown report** (chat or `.md` file):
- MCP / Claude / agent setup, namespace discovery, OAuth, CONNECT_TIMEOUT, or "needs auth" status
- Transport choice (MCP vs REST vs `gh`), hostnames, cloudId, credentials, or "operator's credentials"
- Raw custom-field IDs, field-ID remapping stories, or "config is stale" narratives
- Call counts / budgets (`11 REST / 1500`), tool names, or pagination internals
- Multi-bullet "acquisition caveats" about the session
- Bare check codes as the primary label (`R1`, `R4`, …) in prose, tables, calibration notes, or "why Critical" explanations — readers should not have to decode internal IDs

Those details belong only in the **JSON sidecar** (and optionally a one-line operator note *after* the report if the user asks why a check is Unknown). Prefer human field names in any coverage note (e.g. "QA Contact") over `customfield_*`.

**Plain-language checks (required in markdown):** Always use the English check names below. JSON sidecar keys may stay `R1`…`R13`. Optional short codes in parentheses are OK only after the English name (e.g. `Test plan (R1)`), never alone in reader-facing sentences.

| Code | English name (use this in the report) |
|---|---|
| R1 | Test plan |
| R2 | Template filled |
| R3 | Quality Status table |
| R4 | Work items |
| R5 | Work item progress |
| R6 | QA contact |
| R7 | Priority alignment |
| R8 | Quality work items |
| R9 | Definition of Ready |
| R10 | Tests visible in CI |
| R11 | PR evidence |
| R12 | Documentation |
| R13 | Release Pending eligible |

**Bad:** `Priority is Critical and both R1 = ❌ and R4 = ❌, which triggers the CRITICAL branch…`  
**Good:** `Priority is Critical, and both the test plan and work items are missing (❌), so the verdict is Critical.`

**Data coverage** — omit the section entirely when every required field was fetched and remote links / comments were available. Include it **only** when missing data changes how a verdict should be read:

```markdown
## Data coverage
| Item | Value |
|---|---|
| Fields not returned | none — or human-readable names (e.g. QA Contact) |
| QA contact evaluable | yes / no (no → QA contact is Unknown, not confirmed missing) |
| Comments available | yes / no |
| Remote links | available (N) / unavailable |
```

Do **not** add free-form caveats under this table.

**Release-wide / team-scoped mode** — grouped by team:

```markdown
# Feature Readiness Report — openshift-X.Y
Generated: <date>

## Calibration
⚠️ CALIBRATION: ... (omit section if none)

## Data coverage
... (omit section if nothing incomplete — see Report hygiene)

## Release Summary
| Metric | Value |
|---|---|
| Total features | N |
| Teams | N |
| ✅ Ready | N (%) |
| ⚠️ Partial | N (%) |
| 🔴 At Risk | N (%) |
| 🔴 Critical | N (%) |
| With test plans | N (%) |
| Template fully filled | N (%) |
| QA contact missing (confirmed empty) | N |
| QA contact unknown (unfetched) | N |
| Not assessed (budget) | N |
| Critical features without plans | N |

## Team: Networking (5 features — 2 ✅ 2 ⚠️ 1 🔴)

### Readiness overview

| Feature | Priority | Status | Plan | Template | QA | Work Items | Docs | DoR | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| OCPSTRAT-2962 | Critical | In Progress | ❌ | ❌ | ⚠️ | ❌ 0 | ❌ | 0% | 🔴 |
| ... |

### Quality & delivery detail

| Feature | Quality Status | Work Progress | Priority Align | Quality Items | CI Visible | PR Evidence | RP Eligible |
|---|---|---|---|---|---|---|---|
| ... |

## Features Requiring Immediate Attention
1. ...
```

**Single-feature mode** — full check-by-check detail (state clearly when QA contact was unfetched / Unknown). Same hygiene: no Acquisition/MCP/setup dump; lead with the feature key, verdict, and checks. Example check table:

```markdown
## Checks
| Check | Result | Detail |
|---|---|---|
| Test plan | ❌ Missing | No linked test-plan URL |
| Template filled | ⚠️ … | … |
| Work items | ❌ None | No child Stories/Tasks/Epics |
| QA contact | ✅ … | … |
```

For "why this verdict" prose, name the checks in English (see Report hygiene) — never `R1 = ❌ and R4 = ❌`.

#### JSON sidecar

Write the scoped JSON with the structure in [references/readiness-criteria.md](references/readiness-criteria.md), including top-level `fields_missing`, `comments_available`, `qa_contact_field_fetched`, `calibration_flags`, `mcp_calls_used`, `mcp_call_budget`, and summary fields `no_qa_contact` + `qa_contact_unknown` + `not_assessed`. Sidecar may also record transport/field-resolution diagnostics for operators; **do not mirror that prose into the markdown report**.

### Step 8: Present to user

1. Show the markdown summary and per-feature table in chat — **lead with Calibration** (if any), then **Release / feature Summary**, then check tables. Include **Data coverage** only when incomplete fetches affect interpretation (per Report hygiene).
2. Offer to drill into any specific feature for detailed check results.
3. Offer to run `/openshift-developer:generate-test-plan` for features with R1=❌ (not for R1=⚠️).
4. Offer to export the report or take action on critical gaps.
5. If the user asks why a check is Unknown, briefly explain data coverage — still without dumping MCP/OAuth/setup logs. Recommend a known-good single-feature calibration run when instance field mapping may have changed.

## Arguments
- `$1` — Release version string (e.g. `openshift-5.1` or `5.1`) **or** a single OCPSTRAT issue key (e.g. `OCPSTRAT-2962`) (required)
- `--team <component>` — Filter to features with this Jira component (case-insensitive)
- `--check dor` — Run only Definition of Ready checks (R1, R6, R8, R9)
- `--check dod` — Run only Definition of Done checks (R2, R3, R4, R5, R7, R10, R11, R12, R13)
- `--sippy` — Attempt Sippy queries for R10 (off by default)

## Examples

1. **Full readiness scan for a release** (grouped by team):
   ```text
   /openshift-developer:assess-feature-readiness openshift-5.1
   ```

2. **Team-scoped scan** (only networking features):
   ```text
   /openshift-developer:assess-feature-readiness openshift-5.1 --team networking
   ```

3. **Single feature deep-dive** (use as calibration before large scans):
   ```text
   /openshift-developer:assess-feature-readiness OCPSTRAT-2962
   ```

4. **DoR-only check for a team**:
   ```text
   /openshift-developer:assess-feature-readiness openshift-5.1 --team monitoring --check dor
   ```

5. **DoD-only check across the release**:
   ```text
   /openshift-developer:assess-feature-readiness 5.1 --check dod
   ```

## Guidelines
- Fetch Jira data via MCP **or** authenticated Jira REST (`JIRA_API_TOKEN` / equivalent) — never scrape HTML or guess. Prefer MCP when available; REST is fine when MCP is not. Do not put the transport choice in the markdown report
- Reuse fetched data across checks to minimize API calls
- Resolve QA Contact via `qa_contact_field` in readiness-criteria.md Configuration (default `customfield_10470` on Cloud); substitute that value in Step 4 field requests and R6
- Resolve release JQL via `target_version_field` in readiness-criteria.md Configuration (default `Target Version`); substitute that value in Step 4 JQL
- Do not check ownership/process items (PM assignment, rank, capacity) — only quality artifacts
- Sort output by severity so the most critical gaps appear first
- When a check cannot be evaluated (unfetched field, `remote_links_status=unavailable`, missing comments), report as ⚠️ Unknown rather than ❌
- Prefer `--team` scans until a run fits the call budget; merge sidecars mentally rather than stalling a 234-feature unbounded scan
- Treat saturated 0%/100% headline metrics as alarms until Data coverage / sidecar confirms the underlying field was fetched
- Keep the markdown report audience-facing: no Claude setup, MCP health, OAuth, REST fallback, custom-field remapping, or call-budget prose — put that in the JSON sidecar only
- In markdown, always say **Test plan**, **Work items**, **QA contact**, etc. — not bare `R1` / `R4`. JSON may keep `R1`…`R13` keys
