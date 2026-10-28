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
| **MCP call** | `getJiraIssue` with fields: `["remotelinks"]` — or fetch remote links separately |
| **Logic** | 1. Fetch all external/remote links on the feature. 2. For each link, check if the title matches pattern `*test*plan*` (case-insensitive). 3. Also accept: links with URL path containing `/plans/` or `/test-plan`. 4. The pattern must be deterministic and published. |
| **Verdicts** | ✅ Linked (URL found) · ❌ Missing (no matching link) |
| **Output fields** | `plan_status`: `"linked"` / `"missing"`, `plan_url`: the URL if found |

---

## R2 — Template filled

| Field | Detail |
|---|---|
| **Question** | Is the feature's Jira description actually filled in, or still placeholder text? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["description"]` |
| **Logic** | 1. Fetch the feature's description (rendered as text). 2. Scan for placeholder markers: `<your text here>` (literal), `TBD` / `TODO` / `N/A` in required sections, blank table rows (cells containing only whitespace between pipes), empty sections (heading followed immediately by next heading). 3. Count unfilled sections out of total expected sections. 4. Expected sections (from OCPSTRAT template): **Feature Overview**, **Goals**, **Requirements**, **Use Cases**, **Deployment Considerations**, **Interoperability**, **Customer Considerations**. |
| **Verdicts** | ✅ Filled (0 placeholders) · ⚠️ Partial (1–3 sections unfilled) · ❌ Unfilled (4+ sections) |
| **Output fields** | `template_status`: `"filled"` / `"partial"` / `"unfilled"`, `unfilled_sections`: list of section names, `unfilled_count`: number |

---

## R3 — Quality Status table

| Field | Detail |
|---|---|
| **Question** | Does the Quality Status table have real test numbers, not zero or n/a? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["description"]` (same fetch as R2 — reuse) |
| **Logic** | 1. Parse the description for the Quality Status structured table. 2. Extract fields: "Estimated number of e2e/integration tests" → `estimated_tests`, "% tests automated" → `automation_pct`. 3. Check: `estimated_tests > 0` AND `automation_pct ≠ "n/a"` AND `automation_pct ≠ ""`. |
| **Verdicts** | ✅ Has numbers (tests > 0, automation has %) · ⚠️ Partial (one field missing) · ❌ Empty (tests == 0 or n/a) |
| **Output fields** | `estimated_tests`: number, `automation_pct`: string, `quality_status_verdict`: string |
| **Note** | Quality Status table is transitional. Data should eventually come from CI. |

---

## R4 — Work items exist

| Field | Detail |
|---|---|
| **Question** | Are there child Jira issues (Stories/Tasks/Epics) linked to this feature, and what do those Epics contain? |
| **FQS phase** | Planning → Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["subtasks", "issuelinks"]` — then for each linked Epic: `getJiraIssue` with fields: `["subtasks", "issuelinks"]` to discover its children |
| **Logic** | **Two-level traversal** (Feature → children → grandchildren): 1. Read `subtasks` field → direct children. 2. Read `issuelinks` field → linked issues. **Filter link types**: include `Incorporates`, `Related`, `Blocks`, `Depend`; **exclude** `Account`, `Duplicate`, `Cloners`. 3. **Classify linked items by project**: OSDOCS-prefixed Epics are **documentation tracking** (pass to R12, not counted as engineering work items); OCPNODE/SPLAT/STOR/other-prefixed Epics and Stories are **engineering work items**. 4. **For each engineering Epic** (non-OSDOCS): fetch its own `subtasks` and `issuelinks` to collect the Stories/Tasks inside it (second level). 5. Deduplicate all collected work items by key. 6. Count total engineering work items found (Epics + their children). |
| **Verdicts** | ✅ Found (count > 0) · ❌ None (count == 0) |
| **Output fields** | `work_items_count`: number, `work_items_keys`: list of Jira keys, `epics_traversed`: number (how many Epics were expanded), `grandchildren_count`: number (items discovered inside Epics) |
| **Performance note** | For features with many linked Epics, this adds one API call per Epic. Cap at 20 Epics per feature to bound latency. Log a warning if the cap is hit. |

---

## R5 — Work item progress

| Field | Detail |
|---|---|
| **Question** | What's the status of the work items — done, in progress, or not started? |
| **FQS phase** | Development → Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | For each work item key from R4 (including grandchildren): `getJiraIssue` with fields: `["status"]` — or reuse statuses already fetched during R4 traversal |
| **Logic** | 1. For each work item found in R4 (including Stories/Tasks inside Epics), fetch or reuse its status. 2. Classify: Done/Closed/Resolved → `"done"`, In Progress/In Review/Code Review → `"in_progress"`, Open/New/To Do/Backlog → `"not_started"`, Blocked → `"blocked"`. 3. Compute: `done_count / total_count = completion %`. 4. **Epic rollup**: also report per-Epic completion so the output shows which Epics are lagging. |
| **Verdicts** | ✅ All Done (100%) · 🔄 In Progress (1–99%) · ❌ Not Started (0%) |
| **Output fields** | `done`: number, `in_progress`: number, `not_started`: number, `blocked`: number, `completion_pct`: number, `epic_progress`: dict of Epic key → `{ total, done, completion_pct }` |
| **Dependency** | Requires R4 work item list (including grandchildren). If R4 = ❌ (no items), R5 = N/A with `completion_pct: 0`. |

---

## R6 — QA contact assigned

| Field | Detail |
|---|---|
| **Question** | Is there a named QA contact on this feature? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | `getJiraIssue` with fields: `["customfield_12319243"]` (see Configuration section for field ID) |
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
| **Logic** | 1. Read feature priority. 2. IF priority ∈ {Critical, Blocker}: R1 must be ✅ (plan linked), R4 must be ✅ (work items exist), R6 must be ✅ (QA contact assigned). IF any of these are ❌ → Critical Gap 🔴. 3. IF priority ∈ {Major, Minor} → no additional requirement. |
| **Verdicts** | ✅ Adequate (not Critical, or Critical with all three) · 🔴 Critical Gap (Critical + missing R1/R4/R6) |
| **Output fields** | `priority`: string, `priority_alignment`: `"adequate"` / `"critical_gap"`, `missing_for_priority`: list |
| **Dependency** | Requires R1, R4, R6 results. |

---

## R8 — Quality work items

| Field | Detail |
|---|---|
| **Question** | Are there Jira Stories/Tasks specifically for quality activities (not just dev work)? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse R4 work items list (including grandchildren); for each: `getJiraIssue` with fields: `["summary", "labels", "components"]` (or reuse data already fetched in R4 traversal) |
| **Logic** | 1. Take R4's full work item list (Epics, Stories, Tasks — including items discovered inside Epics). 2. For each, classify as quality or dev by checking: summary contains `"test"`, `"QE"`, `"quality"`, `"automation"`, `"CI"`, `"e2e"`, `"integration test"` (case-insensitive); labels contain `"qe"`, `"quality"`, `"test-plan"`, `"automation"`; component is a QE component. 3. Count quality-specific items. |
| **Verdicts** | ✅ Found (quality items > 0) · ❌ None (zero quality-specific items) |
| **Output fields** | `quality_work_items_count`: number, `quality_work_items_keys`: list |
| **Dependency** | Requires R4 work item list (including grandchildren). If R4 = ❌ (no items), R8 = ❌. |

---

## R9 — Definition of Ready

| Field | Detail |
|---|---|
| **Question** | Has this feature met DoR exit criteria from the OCPSTRAT Playbook? |
| **FQS phase** | Planning |
| **DoR/DoD** | DoR |
| **MCP call** | Reuse data from R1, R2, R6, and `getJiraIssue` with fields: `["issuelinks", "description"]` |
| **Logic** | DoR requires ALL of: 1. ✅ Sizing from dev/QE/docs contributors → check: linked estimation story or description contains sizing info. 2. ✅ Design doc linked → check: external link with title `*design*doc*` or `*enhancement*proposal*` (case-insensitive). 3. ✅ Test plan linked → reuse R1 result. 4. ✅ QA contact assigned → reuse R6 result. 5. ✅ Feature description filled → reuse R2 result (at least `"partial"`). |
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
| **MCP call** | `getJiraIssue` with fields: `["remotelinks"]` → extract linked repos; then `gh` CLI or Grep |
| **Logic** | 1. From feature's linked PRs, identify test file paths. 2. Check if those test files are included in any Prow job config: search `ci-operator/config/` for the component's job configs, check if the test binary/suite is referenced. 3. Optionally: query Sippy API for test name visibility. 4. Fallback: if no PR links, check cannot be evaluated → `"unknown"`. |
| **Verdicts** | ✅ Visible (tests found in CI) · ⚠️ Unknown (no PR data) · ❌ Not Visible (tests exist but not in CI) |
| **Output fields** | `ci_visibility`: `"visible"` / `"unknown"` / `"not_visible"`, `ci_jobs`: list of job names if found |

---

## R11 — PR evidence

| Field | Detail |
|---|---|
| **Question** | Do the feature's PRs have verification artifacts? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` remote links → for each PR: `gh pr view` or GitHub MCP |
| **Logic** | 1. Fetch all linked PRs from the feature. 2. For each PR, check for: `verified` or `lgtm` labels present, CI checks passed (green status), PR body references test plan or Jira test task, PR is not abandoned (state = merged or open, not closed without merge). 3. Classify PRs: Feature PRs (code changes to main source), Test-only PRs (only test files changed), Vendor/generated PRs (auto-generated, vendor updates). 4. Report: total PRs, verified count, abandoned count. |
| **Verdicts** | ✅ Evidence present (≥ 1 merged PR with CI green) · ⚠️ Partial (PRs exist but some lack verification) · ❌ No PRs |
| **Output fields** | `pr_count`: number, `pr_merged`: number, `pr_verified`: number, `pr_abandoned`: number, `pr_types`: dict |

---

## R12 — Documentation

| Field | Detail |
|---|---|
| **Question** | Does documentation exist for this feature? |
| **FQS phase** | Development |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["issuelinks", "remotelinks"]` — for linked OSDOCS Epics: also fetch their status |
| **Logic** | 1. Search external/remote links for documentation URLs: links to `docs.openshift.com`, OSDOCS PRs, links with title matching `*doc*`, `*documentation*`. These are strong evidence. 2. Search issue links for linked OSDOCS Jira issues — but **an OSDOCS Epic alone is not sufficient**. Auto-created `Document`-type OSDOCS Epics exist on nearly every OCPSTRAT Feature. Only count an OSDOCS Epic as evidence if its status is `Closed`, `In Progress`, or `In Review` (i.e. actual doc work happened). OSDOCS Epics in `New`, `To Do`, or `Backlog` status are **not** evidence of documentation. 3. Check linked PRs for doc-only PRs (files in `docs/` directory). |
| **Verdicts** | ✅ Exists (doc URL found, or OSDOCS in Closed/In Progress, or doc PR exists) · ⚠️ Tracked (OSDOCS Epic exists but in New/To Do — doc work not started) · ❌ Missing (no doc links, no OSDOCS Epic at all) |
| **Output fields** | `documentation_status`: `"exists"` / `"tracked"` / `"missing"`, `doc_links`: list of URLs, `osdocs_key`: OSDOCS Epic key if present, `osdocs_status`: OSDOCS Epic status |
| **Note** | Every OCPSTRAT Feature typically gets an auto-created OSDOCS Epic via the `Document` link type. Its mere existence does not mean documentation was written — always check the OSDOCS Epic's status. |

---

## R13 — Release Pending eligible

| Field | Detail |
|---|---|
| **Question** | Is this feature actually eligible to be at Release Pending status? |
| **FQS phase** | Stabilization |
| **DoR/DoD** | DoD |
| **MCP call** | `getJiraIssue` with fields: `["status"]` + reuse all other check results |
| **Logic** | 1. Check current Jira status. 2. IF status == `"Release Pending"`: all R4 work items must be Done (R5 = 100%), R1 plan must exist, R3 quality status must have numbers, R10 tests must be in CI, R12 docs must exist. 3. IF status != `"Release Pending"` → check not applicable (N/A). 4. IF status == `"Release Pending"` AND any sub-check fails → flag as premature RP. |
| **Verdicts** | ✅ Eligible (all sub-checks pass) · 🔴 Not Eligible (at RP but sub-checks fail) · N/A (not at RP) |
| **Output fields** | `rp_eligible`: `"eligible"` / `"not_eligible"` / `"na"`, `rp_missing`: list of failed sub-checks |
| **Dependency** | Requires R1, R3, R5, R10, R12 results. Only evaluated when status = Release Pending. |

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
  IF priority ∈ {Critical, Blocker} AND (R1=❌ OR R4=❌ OR R6=❌):
    verdict = 🔴 CRITICAL
  ELIF count(❌ checks) >= 4:
    verdict = 🔴 AT RISK
  ELIF count(❌ checks) >= 1 OR count(⚠️ checks) >= 2:
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
            "R3": { "status": "empty", "estimated_tests": 0, "automation_pct": "n/a" },
            "R4": { "status": "none", "work_items_count": 0, "work_items_keys": [] },
            "R5": { "status": "na", "done": 0, "in_progress": 0, "not_started": 0, "blocked": 0, "completion_pct": 0 },
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
      "R3": { "status": "empty", "estimated_tests": 0, "automation_pct": "n/a" },
      "R4": { "status": "none", "work_items_count": 0, "work_items_keys": [] },
      "R5": { "status": "na", "done": 0, "in_progress": 0, "not_started": 0, "blocked": 0, "completion_pct": 0 },
      "R6": { "status": "empty", "qa_contact": null },
      "R7": { "status": "critical_gap", "priority": "Critical", "missing_for_priority": ["R1", "R4", "R6"] },
      "R8": { "status": "none", "quality_work_items_count": 0, "quality_work_items_keys": [] },
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
- Checks: R1, R2, R4, R6, R8, R9

### Delivery phase (while work is underway)
- **IN PROGRESS → RELEASE PENDING → CLOSED** — all exit criteria must be met = Definition of Done (DoD)
- Checks: R3, R5, R7, R10, R11, R12, R13

### What this skill does NOT check (intentionally out of scope)
These are ownership/process items, not quality artifacts:
- Owner identification (PM, Assignee, Architect)
- Rank on Plan View
- Capacity confirmation
- Weekly status comments
- Technical Enablement OnePagers
- Retrospective completion
- Release closure in Jira
