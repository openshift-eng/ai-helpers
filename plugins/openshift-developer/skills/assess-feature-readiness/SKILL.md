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

### Step 2: Discover Jira MCP namespace (metadata only)

**Do not probe issue tools yet** — many Atlassian MCP namespaces require `cloudId` before any issue call succeeds.

1. Inspect available tool metadata for candidate namespaces, preferring this order when present:
   - `mcp__atlassian__*`
   - `mcp__plugin_jira_atlassian__*`
   - `mcp__user_jira__*`
2. From the chosen namespace, note the issue tool name (`jira_get_issue` / `getJiraIssue`), the search tool (`jira_search` / `searchJiraIssuesUsingJql`), and `getAccessibleAtlassianResources` (or equivalent).
3. Proceed to Step 3 to acquire `cloudId` **before** the first issue fetch.

### Step 3: Acquire cloudId

Call `getAccessibleAtlassianResources` (from the discovered namespace) to obtain the `cloudId`. This cloudId is required for all Jira API calls — including single-feature mode. If the namespace provides the cloudId automatically, extract it from the response.

Only after `cloudId` is available, make a smoke-test issue/search call if needed to confirm the selected tool names. Use those tools for **all** subsequent Jira calls.

### Step 4: Query OCPSTRAT features

**Both modes** use the same per-issue field list and the same separate remote-links fetch below.

**Single-feature mode**: Fetch the one issue by key using the field list in **Step 4.3**, then fetch remote links for that issue using **Step 4.4**. Populate `features[]` with that single entry. Run **Step 4.3b** on it. **Persist** the payload under `.work/assess-feature-readiness/features/<KEY>.json` (same as Step 4.5) **before** skipping to Step 5 so `evaluate_checks.py` can read it.

**Release-wide mode**:

1. Build JQL using the configured `target_version_field` from [references/readiness-criteria.md](references/readiness-criteria.md) Configuration (default `Target Version`) — substitute that name; do not hardcode a different field:
   ```
   project = OCPSTRAT AND type = Feature AND "<target_version_field>" = "openshift-X.Y"
   ```
   Example with the default: `... AND "Target Version" = "openshift-X.Y"`.
   If `--team <component>` was provided, prefer fetching the release set then filtering **case-insensitively** on `components` (Jira JQL `component =` can be case-sensitive). You may still append `AND component = "<component>"` when the instance matches case, but always verify matches case-insensitively after fetch.
2. Use `maxResults = 50` and paginate until exhausted. Follow the selected search tool's pagination contract: Rovo / `searchJiraIssuesUsingJql` uses `nextPageToken` / `isLast`; use `startAt` only for tools that support offset pagination. Apply the same rule to Epic-child and Feature-parent searches in R4. Track MCP calls against the global budget in Step 5.
3. For each feature, request fields: `summary`, `description`, `priority`, `status`, `subtasks`, `issuelinks`, `comment`, `labels`, `components`, and the configured QA Contact field ID from [references/readiness-criteria.md](references/readiness-criteria.md) Configuration (`qa_contact_field`, default `customfield_12319243`). Substitute that configured value — do not hardcode a different ID. **Do not** request `remotelinks` as an issue field — remote links are not part of the main issue response (`/rest/api/3/issue/{key}`); they live at `/rest/api/3/issue/{key}/remotelink`. Include `comment` so the remote-link fallback can find URLs that exist only in comments.
3b. **Verify field acquisition before running any check.** Run the key check on **every** fetched feature (not only the first). Absent key ≠ null value.
   - Per feature, build `fields_missing[]` for that payload; union into a run-level `fields_missing[]`.
   - If `qa_contact_field` is missing on a feature → that feature's R6 is `unfetched` / ⚠️ Unknown. If it is missing on the first feature (or systematically across the run), emit: `⚠️ QA Contact field <id> was not returned by this Jira instance...` and treat subsequent features the same until a payload includes the key.
   - If `comment` is missing on a feature → that feature's `comments_available: false`; R1/R11/R12 must not emit ❌ from a missing-URL conclusion — only ⚠️ Unknown — until comments are fetched separately and succeed.
   - If `description` is missing on a feature → do not merge description-sourced URLs; R1/R2/R3/R9/R12 description-dependent paths return ⚠️ Unknown when no substitute evidence exists (never ❌ Missing / Unfilled solely from a missing description key).
   - Record `fields_missing[]`, `qa_contact_field_fetched`, and `comments_available` at the top level of the JSON sidecar and in the report header (and per-feature when they differ).
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
5. Store all features in a `features[]` array with their full issue data plus `remote_links[]` and `remote_links_status`. Persist raw payloads under `.work/assess-feature-readiness/features/` for audit.
6. **Empty-result stop**: if `features[]` is empty after JQL + team filter, **STOP**. Report the exact JQL executed, the resolved `target_version_field`, the `--team` value (if any), and suggest verifying component names. When `--team` matched nothing, list distinct component values seen in the unfiltered release set (if available). **Never emit an all-zero readiness report for an empty set.**
7. Report the total feature count (and team filter if applicable) to the user before proceeding.

### Step 5: Per feature — run readiness checks

For each feature in `features[]`, run the checks specified by the invocation mode. Read [references/readiness-criteria.md](references/readiness-criteria.md) for the complete specification of each check (R1–R13).

**Deterministic matchers**: for R1/R6/R8 field-presence and quality-item classification, use the committed helper rather than reinventing regexes:

```sh
# Substitute the configured qa_contact_field from readiness-criteria.md (do not hardcode).
QA_FIELD="<qa_contact_field from Configuration, default customfield_12319243>"
python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" selftest
python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" evaluate \
  --features-dir .work/assess-feature-readiness/features \
  --qa-field "$QA_FIELD"
```

Do **not** reimplement R8 with bare `kw in summary` substring checks — that falsely matches `"latest"` → `test`. Always pass the **same** configured `qa_contact_field` used in Step 4.3.

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

**Global MCP call budget**: default **1500** calls per invocation. Count every issue/search/remote-link/comment page. When the budget is exhausted: finish the feature currently in progress, mark remaining features `not_assessed`, record `mcp_calls_used` / `mcp_call_budget` in the sidecar, and say so in the report header. Do not stall silently mid-scan.

**Hierarchy traversal**: R4 uses **two-level traversal** — for each OCPSTRAT Feature, it collects direct subtasks and Feature `issuelinks` (level 1), also searches `parent = <feature-key>` for children that omit those fields, then expands each linked engineering Epic via JQL `parent = <epic-key>` **plus Epic `subtasks` only** (level 2). Do **not** count an Epic's arbitrary `issuelinks` as children. Cap at 20 Epics per feature to bound API calls. **If the cap is hit**, set `traversal_complete = false` and treat R5 `%` as an incomplete sample (never report ✅ All Done / R13-eligible 100% from a truncated set). See [references/readiness-criteria.md](references/readiness-criteria.md) for the full R4/R5 specification.

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
   # Do NOT count ⚠️ Unknown / unfetched as hard failures
   failed = count(❌ checks) + count(🔴 checks)

   IF priority ∈ {Critical, Blocker} AND (R1=❌ OR R4=❌ OR R6=❌):
     verdict = 🔴 CRITICAL
   ELIF failed >= 4:
     verdict = 🔴 AT RISK
   ELIF failed >= 1 OR count(⚠️ checks) >= 2:
     verdict = ⚠️ PARTIAL
   ELSE:
     verdict = ✅ READY
   ```
2. **Group features by team**: Use each feature's Jira `components` field to assign it to team groups. In release-wide mode, a feature with multiple components appears under each. Features with no components go under `"Unassigned"`. In **team-scoped mode** (`--team`), only the filtered component's section appears in the output — other components from multi-component features are not shown as separate groups. Match `--team` **case-insensitively**.
3. Per-team stats: For each team group, count `total`, `ready`, `partial`, `at_risk`, `critical`.
4. Release-level stats: Count overall totals, `% with plans` (**only R1=linked**), `% template filled`, `no_qa_contact` (**only R6=`empty`**), `qa_contact_unknown` (**R6=`unfetched`/`unknown`**), `critical gaps`, `not_assessed`.
5. **Saturation / calibration check** (required when ≥10 features assessed): for each check, if a single verdict accounts for **100%** of results, add a calibration flag rather than reporting the number bare:
   `⚠️ CALIBRATION: R<n> returned <verdict> for 100% of N features. This is consistent with either a genuine org-wide gap or a data-acquisition failure. Verify before acting: <field/call R<n> depends on>.`
   Place these flags **above** the Release Summary table. Helper: `python3 "${CLAUDE_SKILL_DIR}/scripts/evaluate_checks.py" saturation --report <sidecar>`.
6. Sort: within each team group, sort features by gap severity (critical first). Sort team groups by worst verdict (teams with critical gaps first).
7. **Single-feature mode**: Skip grouping. Present the one feature's full check-by-check detail directly.

### Step 7: Produce output

Generate two outputs with **scoped filenames** (never clobber prior scopes):

- Markdown: `.work/assess-feature-readiness/readiness-report-<scope>-<release|team|key>-<YYYYMMDD-HHMM>.md`
- JSON: `.work/assess-feature-readiness/readiness-report-<scope>-<release|team|key>-<YYYYMMDD-HHMM>.json`
- Also copy/symlink the JSON to `readiness-report-latest.json` in the same directory for convenience.

`<scope>` is `release`, `team`, or `feature`. Examples: `readiness-report-team-networking-20261116-1430.json`, `readiness-report-release-openshift-5.1-20261116-1500.json`.

#### Markdown report (shown in chat)

**Release-wide / team-scoped mode** — grouped by team:

```markdown
# Feature Readiness Report — openshift-X.Y
Generated: <date>

## Acquisition
| Item | Value |
|---|---|
| fields_missing | [] or list |
| qa_contact_field_fetched | true/false |
| comments_available | true/false |
| mcp_calls_used / budget | N / 1500 |

## Calibration
⚠️ CALIBRATION: ... (omit section if none)

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

**Single-feature mode** — full check-by-check detail (include R6 `unfetched` explicitly when applicable).

#### JSON sidecar

Write the scoped JSON with the structure in [references/readiness-criteria.md](references/readiness-criteria.md), including top-level `fields_missing`, `comments_available`, `qa_contact_field_fetched`, `calibration_flags`, `mcp_calls_used`, `mcp_call_budget`, and summary fields `no_qa_contact` + `qa_contact_unknown` + `not_assessed`.

### Step 8: Present to user

1. Show the markdown summary and per-feature table in chat — **lead with Acquisition + Calibration** when either is non-empty.
2. Offer to drill into any specific feature for detailed check results.
3. Offer to run `/openshift-developer:generate-test-plan` for features with R1=❌ (not for R1=⚠️).
4. Offer to export the report or take action on critical gaps.
5. Recommend a known-good single-feature calibration run whenever the Jira instance or MCP namespace changes.

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
- Use Jira MCP tools for all Jira data — never scrape or guess
- Reuse fetched data across checks to minimize MCP calls
- Resolve QA Contact via `qa_contact_field` in readiness-criteria.md Configuration (default `customfield_12319243`); substitute that value in Step 4 field requests and R6
- Resolve release JQL via `target_version_field` in readiness-criteria.md Configuration (default `Target Version`); substitute that value in Step 4 JQL
- Do not check ownership/process items (PM assignment, rank, capacity) — only quality artifacts
- Sort output by severity so the most critical gaps appear first
- When a check cannot be evaluated (unfetched field, `remote_links_status=unavailable`, missing comments), report as ⚠️ Unknown rather than ❌
- Prefer `--team` scans until a run fits the MCP budget; merge sidecars mentally rather than stalling a 234-feature unbounded scan
- Treat saturated 0%/100% headline metrics as alarms until Acquisition confirms the underlying field was fetched
