---
name: assess-feature-readiness
description: Assess readiness of all OCPSTRAT features targeting a release by running checks R1–R13 against each feature. Produces a markdown report and JSON sidecar. Use when QE leads, release managers, or WG participants need a release-level quality snapshot.
---

## Name
openshift-developer:assess-feature-readiness

## Synopsis
```text
/openshift-developer:assess-feature-readiness <release-version|OCPSTRAT-KEY> [--team <component>] [--check dor|dod]
```

## Description
Evaluates OCPSTRAT Features against 13 readiness checks (R1–R13) covering Definition of Ready, Definition of Done, and Release Pending eligibility. Produces a markdown readiness report in chat and a `readiness-report.json` sidecar file.

**Audience**: QE leads, release managers, team leads, WG meetings.

### Scoping modes

The first positional argument determines scope:

| Mode | `$1` | Scope |
|---|---|---|
| **Release-wide** | `openshift-5.1` or `5.1` | All OCPSTRAT Features targeting this release |
| **Team-scoped** | `openshift-5.1 --team networking` | Only features whose Jira `components` field includes the given component |
| **Single-feature** | `OCPSTRAT-2962` | One specific feature — full detail, no aggregation |

### Check filter

| Mode | Flag | Checks run |
|---|---|---|
| Full scan (default) | _(none)_ | R1–R13 |
| DoR only | `--check dor` | R1, R6, R8, R9 |
| DoD only | `--check dod` | R2, R3, R4, R5, R7, R10, R11, R12, R13 |

### Output grouping (release-wide and team-scoped modes)

When reporting on multiple features, the output is **grouped by team** (the Jira `components` field). Each team section includes a per-team summary followed by its features. Features with multiple components appear under each applicable team. A feature with no components appears under an "Unassigned" group.

## Implementation

### Step 1: Parse input

1. Accept `$1` as the first positional argument.
2. **Determine scope**:
   - If `$1` matches an OCPSTRAT issue key pattern (e.g. `OCPSTRAT-2962`): **single-feature mode**. Skip Steps 3–4; fetch this one issue directly.
   - Otherwise treat `$1` as a release version string:
     - Strip the `openshift-` prefix if present (e.g. `openshift-5.1` → `5.1`).
     - Validate: must match pattern `X.Y` where X and Y are integers. Reject with an error if invalid.
     - Reconstruct the full release string as `openshift-X.Y` for Jira queries.
3. **Parse `--team`** (optional, release-wide mode only): If `--team <component>` is passed, store the component name for JQL filtering in Step 4.
4. **Parse `--check`** (optional): If `--check dor` is passed, report only DoR checks: R1, R6, R8, R9. If `--check dod`, report only DoD checks: R2, R3, R4, R5, R7, R10, R11, R12, R13. Otherwise report all R1–R13. **Important**: some checks depend on others as prerequisites (R8 needs R4's work items, R9 needs R1+R2+R6, R7 needs R1+R4+R6, R13 needs R1+R3+R5+R10+R12). Always compute prerequisite checks internally even in filtered mode — only limit which checks appear in the reported output.

### Step 2: Discover Jira MCP tool

Try tool names in this order until one responds successfully:

1. `mcp__atlassian__jira_get_issue`
2. `mcp__atlassian__getJiraIssue`
3. `mcp__plugin_jira_atlassian__getJiraIssue`
4. `mcp__user_jira__getJiraIssue`

The first one that responds becomes the tool for **all** subsequent Jira calls. Also discover the corresponding search variant from the same namespace (`jira_search`, `searchJiraIssuesUsingJql`, etc.).

### Step 3: Acquire cloudId

Call `getAccessibleAtlassianResources` (from the discovered namespace) to obtain the `cloudId`. This cloudId is required for all Jira API calls. If the namespace provides the cloudId automatically, extract it from the response.

### Step 4: Query OCPSTRAT features

**Single-feature mode**: Fetch the one issue by key. Populate `features[]` with that single entry. Skip to Step 5.

**Release-wide mode**:

1. Build JQL:
   ```
   project = OCPSTRAT AND type = Feature AND "Target Version" = "openshift-X.Y"
   ```
   If `--team <component>` was provided, append:
   ```
   AND component = "<component>"
   ```
2. Use `maxResults = 50` and paginate with `startAt` to collect all matching features.
3. For each feature, request fields: `summary`, `description`, `priority`, `status`, `subtasks`, `issuelinks`, `remotelinks`, `labels`, `components`, `customfield_12319243` (QA Contact).
4. Store all features in a `features[]` array with their full issue data.
5. Report the total feature count (and team filter if applicable) to the user before proceeding.

### Step 5: Per feature — run readiness checks

For each feature in `features[]`, run the checks specified by the invocation mode. Read [references/readiness-criteria.md](references/readiness-criteria.md) for the complete specification of each check (R1–R13) including field mappings, logic, verdicts, and output fields.

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

**Hierarchy traversal**: R4 uses **two-level traversal** — for each OCPSTRAT Feature, it collects direct subtasks and linked issues (level 1), then expands any linked Epics to discover their child Stories/Tasks (level 2). This gives accurate work-item counts and completion percentages. Cap at 20 Epics per feature to bound API calls. See [references/readiness-criteria.md](references/readiness-criteria.md) for the full R4 specification.

```
OCPSTRAT Feature (assessed)
  ├── subtasks[]           ← level 1: direct children
  ├── issuelinks[]         ← level 1: linked Epics, Stories, Tasks
  │     ├── SPLAT-2137 (Epic)
  │     │     ├── Story-1  ← level 2: children inside the Epic
  │     │     └── Story-2  ← level 2
  │     └── OSDOCS-20703 (Epic)
  │           └── Task-1   ← level 2
  └── (R5 computes completion % across ALL items from both levels)
```

### Step 6: Aggregate results

1. Compute per-feature verdicts using the verdict logic:
   ```
   IF priority ∈ {Critical, Blocker} AND (R1=❌ OR R4=❌ OR R6=❌):
     verdict = 🔴 CRITICAL
   ELIF count(❌ checks) >= 4:
     verdict = 🔴 AT RISK
   ELIF count(❌ checks) >= 1 OR count(⚠️ checks) >= 2:
     verdict = ⚠️ PARTIAL
   ELSE:
     verdict = ✅ READY
   ```
2. **Group features by team**: Use each feature's Jira `components` field to assign it to team groups. A feature with multiple components appears under each. Features with no components go under `"Unassigned"`.
3. Per-team stats: For each team group, count `total`, `ready`, `partial`, `at_risk`, `critical`.
4. Release-level stats: Count overall totals, `% with plans`, `% template filled`, `critical gaps`.
5. Sort: within each team group, sort features by gap severity (critical first). Sort team groups by worst verdict (teams with critical gaps first).
6. **Single-feature mode**: Skip grouping. Present the one feature's full check-by-check detail directly.

### Step 7: Produce output

Generate two outputs:

#### Markdown report (shown in chat)

**Release-wide / team-scoped mode** — grouped by team:

```markdown
# Feature Readiness Report — openshift-X.Y
Generated: <date>

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
| QA contact missing | N |
| Critical features without plans | N |

## Team: networking (5 features — 2 ✅ 2 ⚠️ 1 🔴)

### Readiness overview

| Feature | Priority | Status | Plan | Template | QA | Work Items | Docs | DoR | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| OCPSTRAT-2962 | Critical | In Progress | ❌ | ❌ | ❌ | ❌ 0 | ❌ | 0% | 🔴 |
| OCPSTRAT-3100 | Major | In Progress | ✅ | ⚠️ | ✅ | ✅ 4 | ✅ | 80% | ⚠️ |
| ... |

### Quality & delivery detail

| Feature | Quality Status | Work Progress | Priority Align | Quality Items | CI Visible | PR Evidence | RP Eligible |
|---|---|---|---|---|---|---|---|
| OCPSTRAT-2962 | ❌ 0 tests | — | 🔴 gap (R1,R4,R6) | ❌ 0 | ⚠️ unknown | ❌ no PRs | N/A |
| OCPSTRAT-3100 | ✅ 14 tests | 🔄 75% | ✅ adequate | ✅ 2 | ✅ visible | ✅ 3 merged | N/A |
| ... |

## Team: monitoring (3 features — 3 ✅ 0 ⚠️ 0 🔴)

_(same two-table structure per team)_

## Features Requiring Immediate Attention
1. **networking** — OCPSTRAT-2962: Critical, no plan, no work items, 5 unfilled sections
   → Actions: Assign QA contact, Run generate-test-plan, Fill template
2. ...
```

**Single-feature mode** — full check-by-check detail:

```markdown
# Feature Readiness — OCPSTRAT-2962
**OVN-K Gateway Enhancements** · Priority: Critical · Status: In Progress
Generated: <date>

## Verdict: 🔴 CRITICAL

## Check Results
| # | Check | Result | Detail |
|---|---|---|---|
| R1 | Test plan linked | ❌ Missing | No matching remote link |
| R2 | Template filled | ❌ Unfilled | 5 sections: Goals, Requirements, Use Cases, Deployment, Customer |
| R3 | Quality Status | ❌ Empty | estimated_tests=0, automation_pct=n/a |
| R4 | Work items | ❌ 0 | No engineering work items (OSDOCS excluded) |
| R5 | Work progress | — | N/A (no items) |
| R6 | QA contact | ❌ Empty | No QA contact assigned |
| R9 | DoR | ❌ 0% | 0/5 sub-checks passed |
| R12 | Documentation | ⚠️ tracked | OSDOCS-12345 exists but in New status |
| ... |

## Recommended Actions
1. Assign a QA contact
2. Run `/openshift-developer:generate-test-plan OCPSTRAT-2962`
3. Fill 5 template sections: Goals, Requirements, Use Cases, Deployment, Customer
```

#### JSON sidecar (written to `readiness-report.json`)

Write the JSON sidecar to `.work/assess-feature-readiness/readiness-report.json` with the structure documented in [references/readiness-criteria.md](references/readiness-criteria.md). The JSON includes:
- `release`: the release version string
- `generated`: ISO 8601 timestamp
- `scope`: `"release"`, `"team"`, or `"feature"` — indicates the invocation mode
- `team_filter`: the component name if `--team` was used, otherwise `null`
- `summary`: aggregate counts and percentages (release-wide/team-scoped modes)
- `teams{}`: dict of team name → `{ summary, features[] }` (release-wide/team-scoped modes)
- `feature`: single feature object with full check detail (single-feature mode)

### Step 8: Present to user

1. Show the markdown summary and per-feature table in chat.
2. Offer to drill into any specific feature for detailed check results.
3. Offer to run `/openshift-developer:generate-test-plan` for features missing test plans (R1=❌).
4. Offer to export the report or take action on critical gaps.

## Arguments
- `$1` — Release version string (e.g. `openshift-5.1` or `5.1`) **or** a single OCPSTRAT issue key (e.g. `OCPSTRAT-2962`) (required)
- `--team <component>` — Filter to features with this Jira component (release-wide mode only)
- `--check dor` — Run only Definition of Ready checks (R1, R6, R8, R9)
- `--check dod` — Run only Definition of Done checks (R2, R3, R4, R5, R7, R10, R11, R12, R13)

## Examples

1. **Full readiness scan for a release** (grouped by team):
   ```text
   /openshift-developer:assess-feature-readiness openshift-5.1
   ```

2. **Team-scoped scan** (only networking features):
   ```text
   /openshift-developer:assess-feature-readiness openshift-5.1 --team networking
   ```

3. **Single feature deep-dive**:
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
- The QA Contact custom field ID (`customfield_12319243`) may differ per Jira instance — see readiness-criteria.md for configurability notes
- Do not check ownership/process items (PM assignment, rank, capacity) — only quality artifacts
- Sort output by severity so the most critical gaps appear first
- When a check cannot be evaluated (e.g. no PR links for R10), report as ⚠️ Unknown rather than ❌
