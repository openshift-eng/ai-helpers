# Readiness Criteria Reference — R1 through R13

This reference defines the complete specification for each readiness check used by the `assess-feature-readiness` skill. Each check includes the question it answers, the FQS phase it belongs to, the MCP call required, the evaluation logic, verdict definitions, and output fields.

---

## Configuration

The following values may differ per Jira instance. Update them here if the instance changes.

| Config key | Default value | Description |
|---|---|---|
| `qa_contact_field` | `customfield_12319243` | Jira custom field ID for QA Contact |
| `target_version_field` | `Target Version` | Jira field name used in JQL for release targeting |

---

## R1 — Test plan linked

| Field | Detail |
|---|---|
| **Question** | Does this feature have a test plan document linked? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Fetch remote links via the **separate remote-links call** documented in the skill Step 4 (not as an issue field). Reuse the stored `remote_links[]` and `remote_links_status` for this feature. |
| **Logic** | 1. If `remote_links_status == "unavailable"` and no test-plan URL was recovered from description/comments → ⚠️ Unknown (do **not** treat as ❌ Missing — a Jira remote link may exist but was not fetched). 2. Otherwise use the merged `remote_links[]` from Step 4. 3. For each link, check if the title matches pattern `*test*plan*` (case-insensitive). 4. Also accept: links with URL path containing `/plans/` or `/test-plan`. 5. The pattern must be deterministic and published. |
| **Verdicts** | ✅ Linked (URL found) · ⚠️ Unknown (remote-links retrieval failed and no description/comment plan URL) · ❌ Missing (retrieval ok/empty and no matching link) |
| **Output fields** | `plan_status`: `"linked"` / `"missing"` / `"unknown"`, `plan_url`: the URL if found |

---

## R2 — Template filled

| Field | Detail |
|---|---|
| **Question** | Is the feature's Jira description actually filled in, or still placeholder text? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["description"]` |
| **Logic** | 1. Fetch the feature's description (rendered as text). 2. Expected sections (from OCPSTRAT template): **Feature Overview**, **Goals**, **Requirements**, **Use Cases**, **Deployment Considerations**, **Interoperability**, **Customer Considerations**. 3. **Absent expected sections count as unfilled**: for each expected section, if no matching heading exists in the description (empty description, truncated template, or renamed/missing heading), add that section to `unfilled_sections`. 4. For sections that are present, scan for placeholder markers: `<your text here>` (literal), `TBD` / `TODO` / `N/A` in the section body, blank table rows (cells containing only whitespace between pipes), empty sections (heading followed immediately by next heading or end of description). 5. `unfilled_count` = absent sections + present-but-placeholder sections. |
| **Verdicts** | ✅ Filled (`unfilled_count` == 0) · ⚠️ Partial (1–3 unfilled) · ❌ Unfilled (4+ unfilled, including all-absent / empty description) |
| **Output fields** | `template_status`: `"filled"` / `"partial"` / `"unfilled"`, `unfilled_sections`: list of section names, `unfilled_count`: number |

---

## R3 — Quality Status table

| Field | Detail |
|---|---|
| **Question** | Does the Quality Status table have real test numbers, not zero or n/a? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["description"]` (same fetch as R2 — reuse) |
| **Logic** | 1. Parse the description for the Quality Status structured table. 2. Extract fields: "Estimated number of e2e/integration tests" → `estimated_tests`, "% tests automated" → `automation_pct`. 3. Parse `estimated_tests` as a non-negative integer (treat non-numeric / empty as 0). 4. **Validate `automation_pct` as a real percentage** before accepting it: strip whitespace; accept forms `N`, `N%`, or `N.N%` where `N` is 0–100; reject empty, `n/a`, `N/A`, `TBD`, `TODO`, and any other non-percentage text. Store a boolean `automation_pct_valid`. 5. Pass only when `estimated_tests > 0` AND `automation_pct_valid`. |
| **Verdicts** | ✅ Has numbers (`estimated_tests > 0` AND valid %) · ⚠️ Partial (exactly one of the two is valid — e.g. tests > 0 but pct is TBD, or valid pct but tests == 0) · ❌ Empty (tests == 0 / missing AND pct missing or invalid) |
| **Output fields** | `estimated_tests`: number, `automation_pct`: string (raw), `automation_pct_valid`: boolean, `quality_status_verdict`: string |
| **Note** | Quality Status table is transitional. Data should eventually come from CI. A nonempty but non-percentage value (e.g. `TBD`) must never count as “Has numbers”. |

---

## R4 — Work items exist

| Field | Detail |
|---|---|
| **Question** | Are there child Jira issues (Stories/Tasks/Epics) linked to this feature, and what do those Epics contain? |
| **FQS phase** | Planning → Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["subtasks", "issuelinks"]` — then `searchJiraIssuesUsingJql` / `jira_search` with `parent = <feature-key>` (paginated) for direct children not in those fields — then for each engineering Epic: `parent = <epic-key>` (paginated) plus the Epic's `subtasks`. Do **not** use the Epic's `issuelinks` as the child set. |
| **Logic** | **Two-level traversal** (Feature → children → grandchildren): 1. Read Feature `subtasks` → direct children. 2. Read Feature `issuelinks` → candidate linked Epics/Stories. **Filter link types**: include `Incorporates`, `Related`, `Blocks`, `Depend`; **exclude** `Account`, `Duplicate`, `Cloners`. Prefer `Incorporates` / parent links as ownership evidence. 3. **Search `parent = <feature-key>`** (paginated) — Epics/Stories/Tasks can have the Feature as their parent without appearing in `subtasks` or `issuelinks`; merge those into the level-1 set. 4. **Classify** level-1 items by project: OSDOCS-prefixed Epics are **documentation tracking** (pass to R12, not counted as engineering work items); other-prefixed Epics/Stories are **engineering**. 5. **For each engineering Epic** (non-OSDOCS), up to a hard cap of **20 Epics**: discover children **only** via (a) JQL `parent = <epic-key>` (paginate until exhausted) and (b) the Epic's own `subtasks` field. **Do not** merge the Epic's `issuelinks` into the child set — an Epic can link to unrelated engineering issues, and counting those would inflate R5/R13. If a linked issue is considered, verify `parent` is this Epic or the Feature before counting it. 6. **Pagination**: use the selected search tool's contract — Rovo/`searchJiraIssuesUsingJql` uses `nextPageToken` / `isLast`; retain `startAt` / `maxResults` only for tools that support offset pagination. Apply the same rule to Feature-parent and Epic-child searches. 7. Deduplicate all collected work items by key. 8. Count total engineering work items found (Epics + their verified children). 9. If more than 20 engineering Epics exist, **stop expanding**, set `traversal_complete = false`, record `epics_skipped`, and log a warning. Otherwise `traversal_complete = true`. |
| **Verdicts** | ✅ Found (count > 0, traversal complete) · ⚠️ Found incomplete (count > 0, but Epic cap hit — children unread) · ❌ None (count == 0) |
| **Output fields** | `work_items_count`: number, `work_items_keys`: list of Jira keys, `epics_traversed`: number (how many Epics were expanded), `grandchildren_count`: number (items discovered inside Epics), `traversal_complete`: boolean, `epics_skipped`: number (0 when complete) |
| **Performance note** | Cap at 20 Epics per feature to bound latency. When the cap is hit, dependent checks (R5, R8, R13) must treat the work-item set as **incomplete** — never report definitive 100% Done from a truncated traversal. |

---

## R5 — Work item progress

| Field | Detail |
|---|---|
| **Question** | What's the status of the work items — done, in progress, or not started? |
| **FQS phase** | Development → Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | For each work item key from R4 (including grandchildren): `getJiraIssue` with fields: `["status"]` — or reuse statuses already fetched during R4 traversal |
| **Logic** | 1. For each work item found in R4 (including Stories/Tasks inside Epics), fetch or reuse its status. 2. Classify: Done/Closed/Resolved → `"done"`, In Progress/In Review/Code Review → `"in_progress"`, Open/New/To Do/Backlog → `"not_started"`, Blocked → `"blocked"`. Any other status → `"unknown"` (do not silently drop it). 3. Compute: `done_count / total_count = completion %` over the **collected** set only (`unknown` items count in `total_count` but not in `done`). 4. **Epic rollup**: also report per-Epic completion so the output shows which Epics are lagging. 5. Set `completion_definitive = R4.traversal_complete`. If traversal was truncated, treat `completion_pct` as an **incomplete sample of the collected set only** — not a lower (or upper) bound on true completion. Unread Epics can be entirely open or entirely done, so 100% of the collected set does **not** imply ≥ true completion. Never report ✅ All Done from a truncated set. 6. **Zero completion ≠ Not Started**: when `completion_pct == 0`, inspect classified statuses — if any item is `"in_progress"` or `"blocked"`, the work has started; only report ❌ Not Started when every item is `"not_started"`. 7. **Unknown statuses**: if any item is `"unknown"` and traversal is otherwise complete, do not force All Done / Not Started / In Progress from completion % alone — report ⚠️ Indeterminate. |
| **Verdicts** | ✅ All Done (100% **and** `completion_definitive` **and** zero `unknown`) · ⚠️ Incomplete sample (any collected %, but R4 cap hit — unread Epics remain; % is not a bound) · ⚠️ Indeterminate (traversal complete, but ≥1 status is `"unknown"`) · 🔄 In Progress (1–99% **or** 0% with ≥1 `in_progress`/`blocked`, traversal complete, zero `unknown`) · ❌ Not Started (0% **and** all items `not_started`, traversal complete) |
| **Output fields** | `done`: number, `in_progress`: number, `not_started`: number, `blocked`: number, `unknown`: number, `completion_pct`: number, `completion_definitive`: boolean, `epic_progress`: dict of Epic key → `{ total, done, completion_pct }` |
| **Dependency** | Requires R4 work item list (including grandchildren). If R4 = ❌ (no items), R5 = N/A with `completion_pct: 0`, `completion_definitive: true`. |

---

## R6 — QA contact assigned

| Field | Detail |
|---|---|
| **Question** | Is there a named QA contact on this feature? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | `getJiraIssue` with fields: `[qa_contact_field]` — use the configured `qa_contact_field` from the Configuration section (default `customfield_12319243`) |
| **Logic** | 1. Read the QA Contact custom field. 2. Check: field is non-null AND non-empty AND contains a `displayName`. |
| **Verdicts** | ✅ Assigned (has name) · ❌ Empty |
| **Output fields** | `qa_contact`: string or null, `qa_contact_status`: `"assigned"` / `"empty"` |

---

## R7 — Priority alignment

| Field | Detail |
|---|---|
| **Question** | Do Critical/Blocker features have the minimum quality artifacts? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["priority"]` (reuse from initial fetch) |
| **Logic** | 1. Read feature priority. 2. IF priority ∈ {Critical, Blocker}: require plan linked (R1 ✅), work items exist (`R4.work_items_count > 0` — treat R4 ✅ Found **or** ⚠️ Found incomplete as existence satisfied), and QA contact assigned (R6 ✅). IF R1 or R6 is ❌, or `work_items_count == 0` → Critical Gap 🔴. 3. IF R1 is ⚠️ Unknown (remote links unavailable) while priority is Critical/Blocker and the other two pass → ⚠️ Unknown (cannot prove plan linked). 4. IF priority ∈ {Major, Minor} → no additional requirement. |
| **Verdicts** | ✅ Adequate (not Critical, or Critical with plan + work items + QA) · 🔴 Critical Gap (Critical + missing plan / work items / QA) · ⚠️ Unknown (Critical; work items and QA present, but R1 unevaluable) |
| **Output fields** | `priority`: string, `priority_alignment`: `"adequate"` / `"critical_gap"` / `"unknown"`, `missing_for_priority`: list |
| **Dependency** | Requires R1, R4, R6 results (and R4 `work_items_count`). |

---

## R8 — Quality work items

| Field | Detail |
|---|---|
| **Question** | Are there Jira Stories/Tasks specifically for quality activities (not just dev work)? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse R4 work items list (including grandchildren); for each: `getJiraIssue` with fields: `["summary", "labels", "components"]` (or reuse data already fetched in R4 traversal) |
| **Logic** | 1. Take R4's full work item list (Epics, Stories, Tasks — including items discovered inside Epics). 2. For each, classify as quality or dev: **longer phrases** may use case-insensitive substring match (`"quality"`, `"automation"`, `"e2e"`, `"integration test"`); **short tokens** `"test"`, `"CI"`, and `"QE"` must match on **token boundaries** only. The pipes below are Markdown-escaped (`\|`) so this table cell renders; **when applying the regex in code, use the unescaped form** `(?i)(^|[^A-Za-z0-9])(test|CI|QE)([^A-Za-z0-9]|$)` — do **not** keep the backslashes. Escaped display form: `(?i)(^\|[^A-Za-z0-9])(test\|CI\|QE)([^A-Za-z0-9]\|$)`. This prevents summaries like "Update latest container image" or "Implement special handling" from matching. Labels: exact/case-insensitive membership in `{"qe", "quality", "test-plan", "automation"}`. Component is a QE component. 3. Count quality-specific items. 4. **Incomplete traversal**: if `R4.traversal_complete == false` and quality items == 0, do **not** report ❌ None — unread Epics may still contain quality work. Return ⚠️ Unknown instead. |
| **Verdicts** | ✅ Found (quality items > 0) · ⚠️ Unknown (zero quality items **and** R4 traversal incomplete) · ❌ None (zero quality-specific items **and** traversal complete) |
| **Output fields** | `quality_work_items_count`: number, `quality_work_items_keys`: list, `quality_status`: `"found"` / `"unknown"` / `"none"` |
| **Dependency** | Requires R4 work item list (including grandchildren) and `traversal_complete`. If R4 = ❌ (no items), R8 = ❌. |

---

## R9 — Definition of Ready

| Field | Detail |
|---|---|
| **Question** | Has this feature met DoR exit criteria from the OCPSTRAT Playbook? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse data from R1, R2, R6, and `getJiraIssue` with fields: `["issuelinks", "description"]` |
| **Logic** | DoR requires ALL of: 1. ✅ Sizing from dev/QE/docs contributors → check: linked estimation story or description contains sizing info. 2. ✅ Design doc linked → check: external link with title `*design*doc*` or `*enhancement*proposal*` (case-insensitive). 3. ✅ Test plan linked → reuse R1 result. 4. ✅ QA contact assigned → reuse R6 result. 5. ✅ Feature description filled → reuse R2 result; requires R2 = `"filled"` (all expected sections present and non-placeholder). R2 = `"partial"` does **not** satisfy this sub-check. |
| **Verdicts** | ✅ Met (all 5 sub-checks pass) · ⚠️ Partial (3–4 pass) · ❌ Not Met (< 3 pass) |
| **Output fields** | `dor_status`: `"met"` / `"partial"` / `"not_met"`, `dor_checks`: dict of sub-check results |
| **Dependency** | Requires R1, R2, R6 results. |

---

## R10 — Tests visible in CI

| Field | Detail |
|---|---|
| **Question** | Are this feature's tests running in CI jobs and visible in Sippy? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | Reuse `remote_links[]` from Step 4 → extract linked PRs/repos; then `gh` CLI or Grep. Optionally query Sippy. |
| **Logic** | 1. **Candidate CI links** — a remote link is a CI candidate only if it **identifies CI infrastructure**, not an arbitrary title substring: (a) URL host is `prow.ci.openshift.org`, `sippy*` OpenShift Sippy host, or `testgrid.k8s.io` **and** the path looks like a job/job-history/Sippy/TestGrid page (e.g. contains `/job-history/`, `/job/`, `/pr-logs/`, `periodic-`, `presubmit-`); **or** (b) title has standalone token `CI` / `Prow` / `Sippy` / `TestGrid` (token-boundary match) **and** the same path/host shape. Homepages, dashboards without a job, and titles like "Architecture decision" must **not** match. 2. **Feature association required for ✅**: a candidate is ✅ Visible only when there is evidence it exercises **this feature's tests** — e.g. job name/path overlaps the feature's component or known test identifiers from the Quality Status table / linked PR test paths, or a Sippy query returns those test names for the job. A generic Prow/TestGrid URL with no feature-test association → ⚠️ Unknown (not ✅). 3. Otherwise, from feature's linked PRs, identify test file paths and check if those files are referenced in `ci-operator/config/` for the component. 4. Optionally: query Sippy API for test name visibility. 5. Fallback: if no PR/CI data, or remote links unavailable and no other evidence → `"unknown"`. |
| **Verdicts** | ✅ Visible (CI link/job associated with this feature's tests, or tests found in CI/Sippy) · ⚠️ Unknown (no PR/CI data, or CI URL present but feature-test association not established) · ❌ Not Visible (feature tests identified but confirmed absent from CI) |
| **Output fields** | `ci_visibility`: `"visible"` / `"unknown"` / `"not_visible"`, `ci_jobs`: list of job names if found, `ci_association`: `"matched"` / `"unverified"` / `"none"` |

---

## R11 — PR evidence

| Field | Detail |
|---|---|
| **Question** | Do the feature's PRs have verification artifacts? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | Reuse `remote_links[]` / `remote_links_status` from Step 4 → for each PR URL: `gh pr view` or GitHub MCP. When a remote link already carries hermetic fields (`state`, `labels`, `ci_status`), reuse those and skip live GitHub calls for that PR. |
| **Logic** | 1. If `remote_links_status == "unavailable"` and no PR URLs were recovered from description/comments → ⚠️ Unknown (not ❌ No PRs). 2. Collect linked PRs from `remote_links[]` (and description/comments as backup). 3. For each PR, prefer inline remote-link fields when present (`state`, `labels`, `ci_status`); otherwise call `gh pr view` / GitHub MCP. Check for: `verified` or `lgtm` labels present, CI checks passed (green / `ci_status=success`), PR body references test plan or Jira test task (when available), PR is not abandoned (state = merged or open, not closed without merge). 4. Classify PRs: Feature PRs (code changes to main source), Test-only PRs (only test files changed), Vendor/generated PRs (auto-generated, vendor updates). 5. Report: total PRs, verified count, abandoned count. |
| **Verdicts** | ✅ Evidence present (≥ 1 merged PR with CI green) · ⚠️ Partial (PRs exist but some lack verification) · ⚠️ Unknown (remote-links retrieval failed and no PR URL elsewhere) · ❌ No PRs |
| **Output fields** | `pr_count`: number, `pr_merged`: number, `pr_verified`: number, `pr_abandoned`: number, `pr_types`: dict |

---

## R12 — Documentation

| Field | Detail |
|---|---|
| **Question** | Does documentation exist for this feature? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["issuelinks"]` plus reuse `remote_links[]` / `remote_links_status` from Step 4 — for linked OSDOCS Epics: also fetch their status |
| **Logic** | 1. Search `remote_links[]` for **product documentation artifacts**: links to `docs.openshift.com`, OSDOCS PRs (`github.com/openshift/openshift-docs` or similar), or titles matching `*documentation*` / `*user guide*` / `*release note*` (case-insensitive). **Do not** treat design documents as product docs — titles matching `*design*doc*`, `*enhancement*proposal*`, or `*architecture*` belong to R9 (DoR design-doc sub-check), not R12. A bare `*doc*` substring is **not** enough (it would match "Design Doc"). 2. Check linked PRs for doc-only PRs (files in `docs/` directory / openshift-docs). 3. Search issue links for linked OSDOCS Jira issues. An OSDOCS Epic is **tracking**, not proof of shipped docs — auto-created `Document`-type OSDOCS Epics exist on nearly every OCPSTRAT Feature. Record the Epic key/status for context, but **never** treat Epic status alone (`Closed` / `In Progress` / `In Review` / `New`) as sufficient for ✅ Exists. 4. If no doc artifact and no OSDOCS Epic, and `remote_links_status == "unavailable"` → ⚠️ Unknown (not ❌ Missing). |
| **Verdicts** | ✅ Exists (**documentation artifact required**: doc URL, OSDOCS/docs PR, or doc-only PR) · ⚠️ Tracked (OSDOCS Epic present — any status — but no documentation artifact yet) · ⚠️ Unknown (remote-links retrieval failed; no OSDOCS Epic and no description/comment doc URL) · ❌ Missing (retrieval ok and no doc artifact and no OSDOCS Epic) |
| **Output fields** | `documentation_status`: `"exists"` / `"tracked"` / `"missing"`, `doc_links`: list of URLs, `osdocs_key`: OSDOCS Epic key if present, `osdocs_status`: OSDOCS Epic status |
| **Note** | Every OCPSTRAT Feature typically gets an auto-created OSDOCS Epic via the `Document` link type. Epic existence or status alone never proves documentation exists — require a URL or PR artifact for ✅ Exists. Keep In Progress / Closed OSDOCS without an artifact as ⚠️ Tracked so R13 cannot treat them as docs-complete. |

---

## R13 — Release Pending eligible

| Field | Detail |
|---|---|
| **Question** | Is this feature actually eligible to be at Release Pending status? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["status"]` + reuse all other check results |
| **Logic** | 1. Check current Jira status. 2. IF status != `"Release Pending"` → N/A. 3. IF status == `"Release Pending"`: evaluate sub-checks — R5 Done with definitive completion (100% **and** `completion_definitive` **and** zero unknown statuses), R1 plan linked, R3 ✅ Has numbers (full pass: `estimated_tests > 0` **and** `automation_pct_valid` — do **not** accept `automation_pct_valid` alone), R10 `visible`, R12 docs exist (`documentation_status = "exists"`). 4. **Known failures first**: classify each sub-check as pass / fail / unknown. If **any** evaluable sub-check fails (e.g. R1 missing plan, R12 missing docs, R3 empty/partial), return 🔴 Not Eligible with those keys in `rp_missing` — even when another prerequisite is unevaluable (e.g. R10 = `unknown`). A known failure already proves the feature is not eligible. 5. **Unknown only when no known failure**: if no evaluable sub-check fails but at least one is unevaluable (notably R10 = `unknown`, or R5 incomplete traversal / indeterminate statuses that prevent a definitive Done/not-Done call), record those keys in `rp_unknown` and return ⚠️ Unknown. Never treat truncated 100% as Done — put `R5_traversal_incomplete` in `rp_unknown` when unread work blocks the decision, or in `rp_missing` only when treating as not eligible for another reason. 6. IF all sub-checks are known and pass → ✅ Eligible. |
| **Verdicts** | ✅ Eligible (all sub-checks pass) · 🔴 Not Eligible (at RP; at least one known prerequisite fails) · ⚠️ Unknown (at RP; no known failures, but at least one prerequisite unevaluable) · N/A (not at RP) |
| **Output fields** | `rp_eligible`: `"eligible"` / `"not_eligible"` / `"unknown"` / `"na"`, `rp_missing`: list of failed sub-checks, `rp_unknown`: list of unevaluable prerequisite keys |
| **Dependency** | Requires R1, R3, R5, R10, R12 results (and R4 `traversal_complete`). Only evaluated when status = Release Pending. |

---

## Check-to-Phase Mapping (DoR / DoD split)

| Check | Phase | DoR | DoD | Question |
|---|---|---|---|---|
| R1 | Planning | ✅ | — | Test plan linked? |
| R2 | Planning | — | ✅ | Template filled? |
| R3 | Stabilization | — | ✅ | Quality Status populated? |
| R4 | Development | — | ✅ | Work items exist? |
| R5 | Development | — | ✅ | Work items done? |
| R6 | Planning | ✅ | — | QA contact assigned? |
| R7 | Stabilization | — | ✅ | Priority vs coverage adequate? |
| R8 | Planning | ✅ | — | Quality work items created? |
| R9 | Planning | ✅ | — | DoR criteria met? |
| R10 | Development | — | ✅ | Tests visible in CI? |
| R11 | Development | — | ✅ | PR verification evidence? |
| R12 | Development | — | ✅ | Documentation exists? |
| R13 | Stabilization | — | ✅ | Release Pending eligible? |

---

## Per-Feature Verdict Logic

```
FOR EACH feature:
  # Count hard failures: ❌ and 🔴 (e.g. R13 Not Eligible) both count as failed
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

---

## JSON Sidecar Structure

The `readiness-report.json` file structure depends on the invocation mode.

### Release-wide / team-scoped mode

Features are grouped by team (Jira `components` field). A feature with multiple components appears under each applicable team. Features with no components appear under `"Unassigned"`.

```json
{
  "release": "openshift-X.Y",
  "generated": "2026-10-27T10:30:00Z",
  "scope": "release",
  "team_filter": null,
  "summary": {
    "total": 47,
    "team_count": 8,
    "ready": 22,
    "partial": 12,
    "at_risk": 10,
    "critical": 3,
    "plan_coverage_pct": 66,
    "template_filled_pct": 51,
    "no_qa_contact": 8,
    "critical_without_plans": 3
  },
  "teams": {
    "networking": {
      "summary": { "total": 5, "ready": 2, "partial": 2, "at_risk": 0, "critical": 1 },
      "features": [
        {
          "key": "OCPSTRAT-2962",
          "name": "OVN-K Gateway Enhancements",
          "priority": "Critical",
          "status": "In Progress",
          "checks": {
            "R1": { "status": "missing", "plan_url": null },
            "R2": { "status": "unfilled", "unfilled_sections": ["Goals", "Requirements", "Use Cases", "Deployment", "Customer"], "unfilled_count": 5 },
            "R3": { "status": "empty", "estimated_tests": 0, "automation_pct": "n/a", "automation_pct_valid": false },
            "R4": { "status": "none", "work_items_count": 0, "work_items_keys": [], "traversal_complete": true, "epics_skipped": 0 },
            "R5": { "status": "na", "done": 0, "in_progress": 0, "not_started": 0, "blocked": 0, "unknown": 0, "completion_pct": 0, "completion_definitive": true },
            "R6": { "status": "empty", "qa_contact": null },
            "R7": { "status": "critical_gap", "priority": "Critical", "missing_for_priority": ["R1", "R4", "R6"] }
          },
          "verdict": "critical",
          "actions": ["Assign QA contact", "Create test plan", "Fill 5 template sections"]
        }
      ]
    },
    "monitoring": {
      "summary": { "total": 3, "ready": 3, "partial": 0, "at_risk": 0, "critical": 0 },
      "features": []
    }
  }
}
```

When `--team networking` is used, `scope` is `"team"`, `team_filter` is `"networking"`, and only that team's features appear (though `teams` still uses the dict structure for consistency).

### Single-feature mode

```json
{
  "release": null,
  "generated": "2026-10-27T10:30:00Z",
  "scope": "feature",
  "team_filter": null,
  "feature": {
    "key": "OCPSTRAT-2962",
    "name": "OVN-K Gateway Enhancements",
    "priority": "Critical",
    "status": "In Progress",
    "components": ["networking"],
    "checks": {
      "R1": { "status": "missing", "plan_url": null },
      "R2": { "status": "unfilled", "unfilled_sections": ["Goals", "Requirements", "Use Cases", "Deployment", "Customer"], "unfilled_count": 5 },
      "R3": { "status": "empty", "estimated_tests": 0, "automation_pct": "n/a", "automation_pct_valid": false },
      "R4": { "status": "none", "work_items_count": 0, "work_items_keys": [], "traversal_complete": true, "epics_skipped": 0 },
      "R5": { "status": "na", "done": 0, "in_progress": 0, "not_started": 0, "blocked": 0, "unknown": 0, "completion_pct": 0, "completion_definitive": true },
      "R6": { "status": "empty", "qa_contact": null },
      "R7": { "status": "critical_gap", "priority": "Critical", "missing_for_priority": ["R1", "R4", "R6"] },
      "R8": { "status": "none", "quality_status": "none", "quality_work_items_count": 0, "quality_work_items_keys": [] },
      "R9": { "status": "not_met", "dor_checks": { "sizing": false, "design_doc": false, "test_plan": false, "qa_contact": false, "description": false } },
      "R10": { "status": "unknown", "ci_jobs": [] },
      "R11": { "status": "no_prs", "pr_count": 0, "pr_merged": 0, "pr_verified": 0, "pr_abandoned": 0, "pr_types": {} },
      "R12": { "status": "missing", "doc_links": [] },
      "R13": { "status": "na", "rp_missing": [] }
    },
    "verdict": "critical",
    "actions": ["Assign QA contact", "Create test plan", "Fill 5 template sections", "Link design doc"]
  }
}
```

---

## OCPSTRAT Playbook Alignment

This skill's checks are grounded in the OpenShift (OCPSTRAT) Feature / Initiative Playbook:

### Discovery phase (before delivery starts)
- **NEW → REFINEMENT → BACKLOG** — all exit criteria must be met = Definition of Ready (DoR)
- Checks: R1, R6, R8, R9 (aligned with `--check dor` and each check's DoR/DoD classification)

### Delivery phase (while work is underway)
- **IN PROGRESS → RELEASE PENDING → CLOSED** — all exit criteria must be met = Definition of Done (DoD)
- Checks: R2, R3, R4, R5, R7, R10, R11, R12, R13 (aligned with `--check dod`; R2 template fill and R4 work-item existence are DoD)

### What this skill does NOT check (intentionally out of scope)
These are ownership/process items, not quality artifacts:
- Owner identification (PM, Assignee, Architect)
- Rank on Plan View
- Capacity confirmation
- Weekly status comments
- Technical Enablement OnePagers
- Retrospective completion
- Release closure in Jira
