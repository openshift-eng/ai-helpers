# Readiness Criteria Reference — R1 through R13

This reference defines the complete specification for each readiness check used by the `assess-feature-readiness` skill. Each check includes the question it answers, the FQS phase it belongs to, the MCP call required, the evaluation logic, verdict definitions, and output fields.

---

## Configuration

The following values may differ per Jira instance. Update them here if the instance changes.

Defaults below are for **redhat.atlassian.net** (Jira Cloud). Do not use legacy Jira Server field IDs.

| Config key | Default value | Description |
|---|---|---|
| `qa_contact_field` | `customfield_10470` | Jira custom field ID for QA Contact (Cloud). Legacy Server ID `customfield_12319243` is invalid here. |
| `target_version_field` | `Target Version` | Jira field name used in JQL for release targeting (Cloud ID `customfield_10855` if a REST update needs the ID) |

---

## R1 — Test plan linked

| Field | Detail |
|---|---|
| **Question** | Does this feature have a test plan document linked? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Fetch remote links via the **separate remote-links call** documented in the skill Step 4 (not as an issue field). Reuse the stored `remote_links[]` and `remote_links_status` for this feature. |
| **Logic** | 1. If `remote_links_status == "unavailable"` and no test-plan URL was recovered from description/comments → ⚠️ Unknown (do **not** treat as ❌ Missing — a Jira remote link may exist but was not fetched). 2. If the feature payload lacks a `description` key (and comments are unavailable / not scanned) and no plan URL is already in `remote_links[]` → ⚠️ Unknown (description-sourced URLs could not be merged). 3. Otherwise use the merged `remote_links[]` from Step 4. 4. For each link, check if the title matches ordered pattern `*test*plan*` (case-insensitive — `"test"` before `"plan"`, e.g. regex `(?i)test.*plan`). Titles like `"Plan for test"` alone do **not** match. 5. Also accept: links with URL path containing `/plans/` or `/test-plan`. |
| **Verdicts** | ✅ Linked (URL found) · ⚠️ Unknown (remote-links retrieval failed, description key missing, or comments unavailable — and no plan URL found) · ❌ Missing (retrieval ok and description available; no matching link) |
| **Output fields** | `plan_status`: `"linked"` / `"missing"` / `"unknown"`, `plan_url`: the URL if found |

---

## R2 — Template filled

| Field | Detail |
|---|---|
| **Question** | Is the feature's Jira description actually filled in, or still placeholder text? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["description"]` |
| **Logic** | 1. Fetch the feature's description as text. If Jira returns ADF (REST v3 object), flatten content nodes to plain text **before** section matching (`evaluate_checks.py` does this; prefer converting at fetch). Never pass a raw dict into regexes. 2. Expected sections (from OCPSTRAT template): **Feature Overview**, **Goals**, **Requirements**, **Use Cases**, **Deployment Considerations**, **Interoperability**, **Customer Considerations**. 3. Detect sections **only via heading lines** (`hN. …` / `# …`) — prose mentions like "See Requirements for limits" must **not** count as a section heading. 4. Section bodies run until the next expected-section heading; **preserve nested subsection headings and their content** (do not strip `h4`/`####` bodies). 5. Split failures into `sections_absent` (no matching heading) and `sections_placeholder` (heading present but body is placeholder-only/`TBD`/`TODO`/`N/A`/blank). A placeholder marker must be a **whole line** (after trim), not a substring inside substantive text (e.g. "uses existing RBAC" must not match `n/a`). 6. `unfilled_count` = absent + placeholder. 7. **All seven headings absent** → ⚠️ Unknown (template variant or parse failure) — do **not** treat a total heading miss as ❌ Unfilled. |
| **Verdicts** | ✅ Filled (`unfilled_count` == 0) · ⚠️ Partial (1–3 unfilled) · ⚠️ Unknown (all expected headings absent) · ❌ Unfilled (4+ unfilled with at least one heading matched) |
| **Output fields** | `template_status`: `"filled"` / `"partial"` / `"unfilled"` / `"unknown"`, `sections_absent`: list, `sections_placeholder`: list, `unfilled_sections`: list (union), `unfilled_count`: number |

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
| **Logic** | **Two-level traversal** (Feature → children → grandchildren): 1. Read Feature `subtasks` → direct children. 2. Read Feature `issuelinks` → candidate linked Epics/Stories. **Filter link types**: include `Incorporates`, `Related`, `Blocks`, `Depend`; **exclude** `Account`, `Duplicate`, `Cloners`. Prefer `Incorporates` / parent links as ownership evidence. 3. **Search `parent = <feature-key>`** (paginated) — Epics/Stories/Tasks can have the Feature as their parent without appearing in `subtasks` or `issuelinks`; merge those into the level-1 set. 4. **Classify** level-1 items by project: OSDOCS-prefixed Epics are **documentation tracking** (pass to R12, not counted as engineering work items); other-prefixed Epics/Stories are **engineering**. 5. **For each engineering Epic** (non-OSDOCS), up to a hard cap of **20 Epics**: discover children **only** via (a) JQL `parent = <epic-key>` (paginate until exhausted) and (b) the Epic's own `subtasks` field. **Do not** merge the Epic's `issuelinks` into the child set — an Epic can link to unrelated engineering issues, and counting those would inflate R5/R13. If a linked issue is considered, verify `parent` is this Epic or the Feature before counting it. 6. **Pagination**: use the selected search tool's contract — Rovo/`searchJiraIssuesUsingJql` uses `nextPageToken` / `isLast`; retain `startAt` / `maxResults` only for tools that support offset pagination. Apply the same rule to Feature-parent and Epic-child searches. 7. Deduplicate all collected work items by key. 8. Count total engineering work items found (Epics + their verified children). 9. If more than 20 engineering Epics exist, **stop expanding**, set `traversal_complete = false`, record `epics_skipped`, and log a warning. 10. **Failed search/page = incomplete**: if any required Feature-parent search, Epic-child search, or pagination page fails/errors/times out — even with fewer than 20 Epics — set `traversal_complete = false` and record the failure. Do **not** set `traversal_complete = true` when children may remain unread. Only set `traversal_complete = true` when every required search completed successfully and the Epic cap was not hit. |
| **Verdicts** | ✅ Found (count > 0, traversal complete) · ⚠️ Found incomplete (count > 0, but Epic cap hit **or** a required search/page failed — children unread) · ❌ None (count == 0 **and** traversal searches completed; if searches failed with count == 0 → ⚠️ Found incomplete / unknown set, not definitive None) |
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
| **Logic** | 1. For each work item found in R4 (including Stories/Tasks inside Epics), fetch or reuse its status. 2. Classify: Done/Closed/Resolved → `"done"`, In Progress/In Review/Code Review → `"in_progress"`, Open/New/To Do/Backlog → `"not_started"`, Blocked → `"blocked"`. Any other status → `"unknown"` (do not silently drop it). 3. Compute: `done_count / total_count = completion %` over the **collected** set only (`unknown` items count in `total_count` but not in `done`). 4. **Epic rollup**: also report per-Epic completion so the output shows which Epics are lagging. 5. Set `completion_definitive = R4.traversal_complete`. If traversal was truncated **or** a required search failed, treat `completion_pct` as an **incomplete sample of the collected set only** — not a lower (or upper) bound on true completion. Unread Epics can be entirely open or entirely done, so 100% of the collected set does **not** imply ≥ true completion. Never report ✅ All Done from a truncated/failed traversal. 6. **Zero completion ≠ Not Started**: when `completion_pct == 0`, inspect classified statuses — if any item is `"in_progress"` or `"blocked"`, the work has started; only report ❌ Not Started when every **known** item is `"not_started"` (see step 7). 7. **Known unfinished before unknown**: if any item is `"not_started"`, `"in_progress"`, or `"blocked"`, that **proves work is not all done** — report 🔄 In Progress or ❌ Not Started from those known statuses **even when other items are `"unknown"`**. Do **not** hide known unfinished work behind ⚠️ Indeterminate. Use ⚠️ Indeterminate only when traversal is complete, there is **no** known unfinished item, ≥1 status is `"unknown"`, and therefore All Done cannot be confirmed. |
| **Verdicts** | ✅ All Done (100% **and** `completion_definitive` **and** zero `unknown`) · ⚠️ Incomplete sample (any collected %, but R4 incomplete — unread Epics remain; % is not a bound) · ⚠️ Indeterminate (traversal complete; no known unfinished; ≥1 `"unknown"` so All Done unconfirmed) · 🔄 In Progress (known `"in_progress"`/`"blocked"` **or** 1–99% among known statuses — even if some statuses are `"unknown"`) · ❌ Not Started (every **known** item is `"not_started"`; unknowns may still exist) |
| **Output fields** | `done`: number, `in_progress`: number, `not_started`: number, `blocked`: number, `unknown`: number, `completion_pct`: number, `completion_definitive`: boolean, `epic_progress`: dict of Epic key → `{ total, done, completion_pct }` |
| **Dependency** | Requires R4 work item list (including grandchildren). If R4 = ❌ (no items), R5 = N/A with `completion_pct: 0`, `completion_definitive: true`. |

---

## R6 — QA contact assigned

| Field | Detail |
|---|---|
| **Question** | Is there a named QA contact on this feature? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | `getJiraIssue` with fields: `[qa_contact_field]` — use the configured `qa_contact_field` from the Configuration section (default `customfield_10470`) |
| **Logic** | 1. Confirm `qa_contact_field` is present as a **key** in the fetched issue payload (see Step 4.3b). **If the key is absent entirely** (as opposed to present-and-null), the field was not returned — return ⚠️ Unknown with `qa_contact_status: "unfetched"`. Never infer "no QA contact" from a missing key. 2. If the key is present: check non-null AND non-empty AND contains a `displayName` (or a non-empty string). |
| **Verdicts** | ✅ Assigned (has name) · ⚠️ Unknown (field not returned by the fetch — `unfetched`) · ❌ Empty (field returned, but null/blank) |
| **Output fields** | `qa_contact`: string or null, `qa_contact_status`: `"assigned"` / `"empty"` / `"unfetched"` |

---

## R7 — Priority alignment

| Field | Detail |
|---|---|
| **Question** | Do Critical/Blocker features have the minimum quality artifacts? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["priority"]` (reuse from initial fetch) |
| **Logic** | 1. Read feature priority. 2. IF priority ∈ {Critical, Blocker}: require plan linked (R1 ✅), work items exist (`R4.work_items_count > 0`), and QA contact assigned (R6 ✅). IF R1 or R6 is ❌, or `work_items_count == 0` → Critical Gap 🔴. 3. IF R1 or R6 is ⚠️ Unknown while priority is Critical/Blocker and no hard ❌ gap → ⚠️ Unknown. 4. IF the three existence inputs pass but R4 is ⚠️ Found incomplete (Epic cap) → ⚠️ Adequate (unverified) — never present truncated traversal as clean ✅ Adequate. 5. IF priority ∈ {Major, Minor} → no additional requirement (✅ Adequate). |
| **Verdicts** | ✅ Adequate (not Critical, or Critical with plan + complete work-item set + QA) · ⚠️ Adequate (unverified) (Critical; plan + QA + `work_items_count > 0`, but R4 traversal incomplete) · 🔴 Critical Gap (Critical + confirmed missing plan / work items / QA) · ⚠️ Unknown (Critical; unevaluable R1/R6 and no confirmed gap) |
| **Output fields** | `priority`: string, `priority_alignment`: `"adequate"` / `"adequate_unverified"` / `"critical_gap"` / `"unknown"`, `missing_for_priority`: list |
| **Dependency** | Requires R1, R4, R6 results (and R4 `work_items_count` / `traversal_complete`). |

---

## R8 — Quality work items

| Field | Detail |
|---|---|
| **Question** | Are there Jira Stories/Tasks specifically for quality activities (not just dev work)? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse R4 work items list (including grandchildren); for each: `getJiraIssue` with fields: `["summary", "labels", "components"]` (or reuse data already fetched in R4 traversal) |
| **Logic** | 1. Take R4's full work item list. 2. Classify each item using the **Quality-item matcher** below (prefer `scripts/evaluate_checks.py`). 3. Count quality-specific items. 4. **Incomplete traversal**: if `R4.traversal_complete == false` and quality items == 0 → ⚠️ Unknown (not ❌ None). |
| **Verdicts** | ✅ Found (quality items > 0) · ⚠️ Unknown (zero quality items **and** R4 traversal incomplete) · ❌ None (zero quality-specific items **and** traversal complete) |
| **Output fields** | `quality_work_items_count`: number, `quality_work_items_keys`: list, `quality_status`: `"found"` / `"unknown"` / `"none"` |
| **Dependency** | Requires R4 work item list (including grandchildren) and `traversal_complete`. If R4 = ❌ (no items), R8 = ❌. |

**Quality-item matcher** (apply exactly — do not invent substring shortcuts):

```python
import re

LONG_PHRASES = ("quality", "automation", "e2e", "integration test")
SHORT_TOKEN_RE = re.compile(r"(?i)(^|[^A-Za-z0-9])(tests?|CI|QE)([^A-Za-z0-9]|$)")
QUALITY_LABELS = {"qe", "quality", "test-plan", "automation"}

def is_quality_item(summary: str, labels: list[str], components: list[str]) -> bool:
    s = summary or ""
    low = s.lower()
    if any(p in low for p in LONG_PHRASES):
        return True
    if SHORT_TOKEN_RE.search(s):
        return True
    if any((lbl or "").lower() in QUALITY_LABELS for lbl in (labels or [])):
        return True
    if any("qe" == (c or "").lower() or (c or "").lower().startswith("qe ") for c in (components or [])):
        return True
    return False
```

Summaries like `"Update latest container image"` and `"Implement special handling"` must **not** match.

---

## R9 — Definition of Ready

| Field | Detail |
|---|---|
| **Question** | Has this feature met DoR exit criteria from the OCPSTRAT Playbook? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse data from R1, R2, R6, and `getJiraIssue` with fields: `["issuelinks", "description"]` |
| **Logic** | DoR requires ALL of: 1. ✅ Sizing from dev/QE/docs contributors → check: linked estimation story or description contains sizing info. 2. ✅ Design doc linked → check: external link with title `*design*doc*` or `*enhancement*proposal*` (case-insensitive). 3. ✅ Test plan linked → reuse R1 (`linked` only). 4. ✅ QA contact assigned → reuse R6 (`assigned` only). 5. ✅ Feature description filled → reuse R2 (`filled` only). Classify each sub-check as `pass` / `fail` / `unknown` (R1/R6/R2 unknown/unfetched/unevaluable → `unknown`; confirmed misses → `fail`). **Verdict selection**: if `pass_count == 5` → ✅ Met. Else if any `unknown` sub-check remains and `(pass_count + unknown_count) >= 3` (unknowns could still push the result to Partial or Met) → ⚠️ Unknown — do **not** emit ❌ Not Met while unevaluated prerequisites can change the band. Else if `pass_count` in 3–4 → ⚠️ Partial. Else → ❌ Not Met. |
| **Verdicts** | ✅ Met (all 5 pass) · ⚠️ Partial (3–4 pass, no decisive unknowns left) · ⚠️ Unknown (unevaluated R1/R6/R2 could still change Partial/Met) · ❌ Not Met (< 3 pass and unknowns cannot reach Partial) |
| **Output fields** | `dor_status`: `"met"` / `"partial"` / `"unknown"` / `"not_met"`, `dor_checks`: dict of sub-check results (`pass`/`fail`/`unknown`) |
| **Dependency** | Requires R1, R2, R6 results. |

---

## R10 — Tests visible in CI

| Field | Detail |
|---|---|
| **Question** | Are this feature's tests running in CI jobs and visible in Sippy? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | Reuse `remote_links[]` from Step 4 → extract linked PRs/repos; then `gh` CLI or Grep. Sippy is **off by default** — only query when `--sippy` is passed; always record `sippy_attempted: true/false` in the output. |
| **Logic** | 1. **Candidate CI links** — a remote link is a CI candidate only if it **identifies CI infrastructure**, not an arbitrary title substring: (a) URL host is `prow.ci.openshift.org`, `sippy*` OpenShift Sippy host, or `testgrid.k8s.io` **and** the path looks like a job/job-history/Sippy/TestGrid page (e.g. contains `/job-history/`, `/job/`, `/pr-logs/`, `periodic-`, `presubmit-`); **or** (b) title has standalone token `CI` / `Prow` / `Sippy` / `TestGrid` (token-boundary match) **and** the same path/host shape. Homepages, dashboards without a job, and titles like "Architecture decision" must **not** match. 2. **Feature association required for ✅**: a candidate is ✅ Visible only when there is evidence it exercises **this feature's tests** — e.g. job name/path overlaps the feature's component or known test identifiers from the Quality Status table / linked PR test paths, or (only if `--sippy`) a Sippy query returns those test names. A generic Prow/TestGrid URL with no feature-test association → ⚠️ Unknown (not ✅). 3. Otherwise, from feature's linked PRs, identify test file paths and check if those files are referenced in `ci-operator/config/` for the component. 4. Fallback: if no PR/CI data, or remote links unavailable and no other evidence → `"unknown"`. |
| **Verdicts** | ✅ Visible (CI link/job associated with this feature's tests, or tests found in CI/Sippy) · ⚠️ Unknown (no PR/CI data, or CI URL present but feature-test association not established) · ❌ Not Visible (feature tests identified but confirmed absent from CI) |
| **Output fields** | `ci_visibility`: `"visible"` / `"unknown"` / `"not_visible"`, `ci_jobs`: list of job names if found, `ci_association`: `"matched"` / `"unverified"` / `"none"`, `sippy_attempted`: boolean |

---

## R11 — PR evidence

| Field | Detail |
|---|---|
| **Question** | Do the feature's PRs have verification artifacts? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | Reuse `remote_links[]` / `remote_links_status` from Step 4 → for each PR URL: `gh pr view` or GitHub MCP. When a remote link already carries hermetic fields (`state`, `labels`, `ci_status`), reuse those and skip live GitHub calls for that PR. |
| **Logic** | 1. If `remote_links_status == "unavailable"` (or description/comments keys unavailable for fallback) and no PR URLs were recovered → ⚠️ Unknown (not ❌ No PRs) — unread sources may still hold PR links. 2. Collect linked PRs from `remote_links[]` (and description/comments as backup when those keys exist). 3. For each PR, prefer inline remote-link fields when present (`state`, `labels`, `ci_status`); otherwise call `gh pr view` / GitHub MCP. Check for: `verified` or `lgtm` labels present, CI checks passed (green / `ci_status=success`), PR body references test plan or Jira test task (when available), PR is not abandoned (state = merged or open, not closed without merge). 4. Classify PRs: Feature PRs (code changes to main source), Test-only PRs (only test files changed), Vendor/generated PRs (auto-generated, vendor updates). 5. Report: total PRs, verified count, abandoned count. |
| **Verdicts** | ✅ Evidence present (≥ 1 merged PR with CI green) · ⚠️ Partial (PRs exist but some lack verification) · ⚠️ Unknown (remote-links / description / comments unread and no PR URL found) · ❌ No PRs (sources readable; none found) |
| **Output fields** | `pr_count`: number, `pr_merged`: number, `pr_verified`: number, `pr_abandoned`: number, `pr_types`: dict |

---

## R12 — Documentation

| Field | Detail |
|---|---|
| **Question** | Does documentation exist for this feature? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["issuelinks"]` plus reuse `remote_links[]` / `remote_links_status` from Step 4 — for linked OSDOCS Epics: also fetch their status |
| **Logic** | 1. Search `remote_links[]` for **product documentation artifacts**: links to `docs.openshift.com`, OSDOCS PRs (`github.com/openshift/openshift-docs` or similar), or titles matching `*documentation*` / `*user guide*` / `*release note*` (case-insensitive). **Do not** treat design documents as product docs — titles matching `*design*doc*`, `*enhancement*proposal*`, or `*architecture*` belong to R9 (DoR design-doc sub-check), not R12. A bare `*doc*` substring is **not** enough (it would match "Design Doc"). 2. Check linked PRs for doc-only PRs (files in `docs/` directory / openshift-docs). 3. Search issue links for linked OSDOCS Jira issues. An OSDOCS Epic is **tracking**, not proof of shipped docs — auto-created `Document`-type OSDOCS Epics exist on nearly every OCPSTRAT Feature. Record the Epic key/status for context, but **never** treat Epic status alone as sufficient for ✅ Exists. 4. **Unread artifact sources**: if **any** required source is unread — `remote_links_status == "unavailable"`, **or** `comments_available == false`, **or** description key missing — and no documentation artifact was found in the sources that *were* read → ⚠️ Unknown — **even when an OSDOCS Epic exists**. Do not return Tracked: a comment or unread remote link may still hold a doc URL, and Tracked is a known non-Exists outcome that R13 treats as a hard failure. 5. **Tracked** only when every artifact source that this check relies on was readable (`remote_links_status == "ok"`, comments available or successfully scanned, description present when used), no artifact was found, and an OSDOCS Epic is present. |
| **Verdicts** | ✅ Exists (doc URL / docs PR / doc-only PR) · ⚠️ Tracked (all relevant sources readable; OSDOCS present; no artifact) · ⚠️ Unknown (any required source unread and no artifact found — OSDOCS may still be recorded for context) · ❌ Missing (all relevant sources readable; no artifact; no OSDOCS Epic) |
| **Output fields** | `documentation_status`: `"exists"` / `"tracked"` / `"unknown"` / `"missing"`, `doc_links`: list of URLs, `osdocs_key`: OSDOCS Epic key if present, `osdocs_status`: OSDOCS Epic status |
| **Note** | Every OCPSTRAT Feature typically gets an auto-created OSDOCS Epic via the `Document` link type. Epic existence or status alone never proves documentation exists — require a URL or PR artifact for ✅ Exists. When remote links are unread, prefer Unknown so R13 reports Unknown instead of Not Eligible. |

---

## R13 — Release Pending eligible

| Field | Detail |
|---|---|
| **Question** | Is this feature actually eligible to be at Release Pending status? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["status"]` + reuse all other check results |
| **Logic** | 1. Check current Jira status. 2. IF status != `"Release Pending"` → N/A. 3. IF status == `"Release Pending"`: evaluate sub-checks — R5 Done with definitive completion (100% **and** `completion_definitive` **and** zero unknown statuses), R1 plan linked, R3 ✅ Has numbers (full pass: `estimated_tests > 0` **and** `automation_pct_valid` — do **not** accept `automation_pct_valid` alone), R10 `visible`, R12 docs exist (`documentation_status = "exists"` only). 4. **Known failures first**: classify each sub-check as pass / fail / unknown. R12 `tracked` / `missing` = fail; R12 `unknown` = unknown (not fail). R5 with **known unfinished** work (`in_progress` / `not_started` / `blocked`, or In Progress / Not Started verdict) = **fail** for eligibility — do **not** treat that as unknown just because other item statuses are `"unknown"`. If **any** evaluable sub-check fails (e.g. R1 missing plan, R12 tracked/missing, R3 empty/partial, R5 known unfinished), return 🔴 Not Eligible with those keys in `rp_missing` — even when another prerequisite is unevaluable. 5. **Unknown only when no known failure**: if no evaluable sub-check fails but at least one is unevaluable (R10 unknown, R12 unknown, R5 indeterminate with no known unfinished, R1 unknown), record those keys in `rp_unknown` and return ⚠️ Unknown. Never treat truncated 100% as Done. 6. IF all sub-checks are known and pass → ✅ Eligible. |
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
  # Do NOT count ⚠️ Unknown as hard failures — but Unknown blocks READY
  failed = count(❌ checks) + count(🔴 checks)
  unknowns = count(⚠️ checks)   # includes R13 Unknown, unfetched fields, etc.

  IF priority ∈ {Critical, Blocker} AND (R1=❌ OR R4=❌ OR R6=❌):
    verdict = 🔴 CRITICAL
  ELIF failed >= 4:
    verdict = 🔴 AT RISK
  ELIF failed >= 1 OR unknowns >= 1:
    verdict = ⚠️ PARTIAL
  ELSE:
    verdict = ✅ READY
```

Ready requires **zero** hard failures **and** **zero** unknowns. A lone ⚠️ (e.g. Release Pending eligibility Unknown) must not fall through to Ready.

---

## JSON Sidecar Structure

The `readiness-report.json` file structure depends on the invocation mode.

Operator-only diagnostics (`mcp_calls_used`, `mcp_call_budget`, raw `fields_missing` custom-field IDs, transport notes) stay in this sidecar. The chat markdown report must **not** dump MCP/OAuth/setup/call-budget prose — see SKILL.md Step 7 **Report hygiene**.

### Release-wide / team-scoped mode

Features are grouped by team (Jira `components` field). A feature with multiple components appears under each applicable team. Features with no components appear under `"Unassigned"`.

```json
{
  "release": "openshift-X.Y",
  "generated": "2026-10-27T10:30:00Z",
  "scope": "release",
  "team_filter": null,
  "fields_missing": [],
  "comments_available": true,
  "qa_contact_field_fetched": true,
  "calibration_flags": [],
  "mcp_calls_used": 0,
  "mcp_call_budget": 1500,
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
    "qa_contact_unknown": 0,
    "critical_without_plans": 3,
    "not_assessed": 0
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
