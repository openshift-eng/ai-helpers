# OCPSTRAT Feature Test Plan Reference

Use this reference **only** when the processed Jira issue is an OCPSTRAT Feature (project `OCPSTRAT`, issue type `Feature`). Follow the instructions below for template parsing, analysis, scenario generation, document structure, and reporting. All generic steps from the main skill still apply; this reference provides the OCPSTRAT-specific additions and overrides.

---

## 1. OCPSTRAT Feature Template Parsing

Extract each template section by detecting the **actual content format** of the Jira response (see SKILL.md Step 1f). Do not assume wiki markup — the format varies by API version and call parameters.

**Section detection by format:**

| Format | Heading pattern | Example |
|---|---|---|
| ADF (JSON) | `{"type": "heading", "attrs": {"level": 3}, "content": [...]}` | Structured JSON traversal |
| HTML | `<h3>Feature Overview</h3>` | Tag matching |
| Markdown | `### Feature Overview` | Prefix matching |
| Wiki markup | `h3. *Feature Overview*` | Legacy pattern |

The standard OCPSTRAT feature template sections are:

- **Feature Overview** (heading: `Feature Overview` or `Goal Summary`)
- **Goals** (heading: `Goals`)
- **Requirements / Acceptance Criteria** (heading: `Requirements`), with sub-headings for:
  - Functional Requirements
  - Testing and Validation Requirements
  - Non-Functional Requirements
  - Operational Requirements
- **Use Cases** (heading: `Use Cases`)
- **Deployment considerations** — a table with topology rows (self-managed/managed, classic/HCP, multi-node/compact/SNO, connected/restricted, architectures, operator compat, backport, UI)
- **Interoperability Considerations** (heading: `Interoperability Considerations`)
- **Customer Considerations** (heading: `Customer Considerations`)
- **Quality Status** — a structured table with columns like "Test Type", "Count", "Automated %"
- **Out of Scope** (heading: `Out of Scope`)
- **Background** (heading: `Background`)
- **Success Criteria** (heading: `Success Criteria` — typically a top-level section), with subsections:
  - Adoption
  - Outcomes

If specific sections are absent, proceed with whichever sections are present; fall through to generic behavior for any missing content.

---

## 2. OCPSTRAT-Specific Analysis

**Strict sourcing applies.** Every section of the IEEE 829 output must trace to content in the OCPSTRAT feature template. If a template section is empty or absent, insert a gap marker (see SKILL.md Step 3.0) rather than inventing content. Common gaps to flag:

- Deployment considerations table is blank → flag: *"⚠️ GAP — Deployment Considerations: The feature does not include a deployment considerations table. Please update the feature ticket with topology/platform applicability."*
- No Interoperability Considerations section → flag: *"⚠️ GAP — Interoperability: No interoperability considerations provided. If cross-component interactions exist, update the feature ticket."*
- No Non-Functional Requirements → flag: *"⚠️ GAP — Non-Functional Requirements: No NFRs provided. If performance, scale, or security targets exist, update the feature ticket."*
- No Success Criteria → flag: *"⚠️ GAP — Success Criteria: No success criteria or adoption/outcomes metrics provided."*

Perform these analysis steps **in addition to** the generic analysis (Step 3 in the main skill):

### 2a. Core component detection

Detect whether the feature targets a **core component** (OVN-Kubernetes, the installer, the API server, etcd, the MCO, CVO, or the monitoring stack). Core components have additional needs beyond the standard template:

- **Multi-repository tracking**: Core features often span multiple repositories (e.g. OVN-K spans `openshift/ovn-kubernetes`, `openshift/cluster-network-operator`, `openshift/api`, `openshift/origin`). For each repository involved, generate a per-repository test section or a separate test plan (cross-referenced).
- **Upstream coverage reference**: Check whether the upstream community project (e.g. `kubernetes/kubernetes` for API server changes) already tests relevant functionality. Reference this to justify downstream testing decisions — but do not direct new test development to upstream repos.
- **Component Readiness visibility**: If the feature affects Component Readiness metrics, note which metrics/signals are relevant and include a "Component Readiness Impact" section.
- **Feature-gate lifecycle**: If the feature is gated, document the feature-gate name, its current lifecycle phase (`alpha`, `beta`, `GA` — matching Kubernetes convention), and include scenarios for. Note: OpenShift feature sets (`TechPreviewNoUpgrade`, `CustomNoUpgrade`) control gate enablement separately — document the applicable feature set if relevant:
  - Feature enabled (gate on)
  - Feature disabled (gate off — regression test)
  - Upgrade with gate transition
- **Ginkgo pending test convention**: When the test framework uses Ginkgo, identify which scenarios are candidates for pending test registration. Use `ginkgo.PIt` or `ginkgo.XIt` with labels `manual:true` and `testCase:path/to/case-description.md` pointing to the detailed test case markdown file. See SKILL.md Step 4g for the exact format and example.

### 2b. Template analysis

- Map each **testable** "Testing and Validation Requirements" item to at least one test scenario. Apply the testability check (SKILL.md Step 3c) first — tautological or untestable items (e.g. "E2E tests are written") do not get scenarios; report them in the Criteria Assessment section instead.
- Parse the "Deployment considerations" table to extract a platform/topology matrix of applicable configurations.
- Map each "Interoperability Considerations" item to an interoperability test scenario.
- **Also** read interoperability data from the Jira `issuelinks` field (Step 1e in the main skill). Merge structured link data with the prose interoperability section, deduplicating. Prefer structured data when both exist.
- Derive end-to-end scenario-based tests from the "Use Cases" section.
- Map every "Non-Functional Requirements" item to an appropriate test scenario category (performance, scale, reliability, security, compatibility, resource consumption, usability, accessibility); when a specific NFR does not warrant a dedicated test scenario, document it with a brief rationale explaining why.
- Derive negative test cases from the "Out of Scope" section only when items explicitly define unsupported behavior or must-not-change boundaries; otherwise record them as exclusions without inferring expected behavior.
- Map "Operational Requirements" to Day-2 operational test scenarios (metrics exposure, troubleshooting workflows, support runbook validation).
- Use "Customer Considerations" to inform edge-case and real-world usage test scenarios. **Scrub any customer names before including in the output** — replace with generic identifiers (e.g. "Customer A", "a large-scale deployment scenario").
- Use "Goals" to inform overall test plan scope and prioritization — Goals do not require individual test mappings but should guide which scenarios are high priority.
- Map each item in the "Success Criteria" section (including Adoption and Outcomes subsections) to at least one test scenario with explicit pass/fail criteria derived from the stated metric or target.

### 2c. Quality Status table parsing

If the feature carries a Quality Status table:

1. Parse the table to extract estimated test counts per type and automation percentages.
2. Compare generated scenario counts against these estimates.
3. Flag significant discrepancies: *"The Quality Status table estimates N unit tests but this plan generates M unit-tier scenarios. [Explanation of the gap]."*

### 2d. Acceptance criteria testability assessment

Apply the testability assessment from SKILL.md Step 3c. For OCPSTRAT features specifically:

- Criteria like "E2E tests are written" or "should contribute to elevating perceived quality" are tautological. Report them in the Criteria Assessment section but do **not** generate test scenarios for them.
- Criteria with quantitative targets ("latency under 50ms at 1000 nodes") are testable and should generate scenarios with explicit pass/fail thresholds.

---

## 3. OCPSTRAT Scenario Categories

Generate these scenario categories **in addition to** the generic scenarios (Step 4 in the main skill). Every scenario must include the full structure from SKILL.md Step 4a (ID, CI tier, target file path, coverage status).

- **Functional validation** (`TC-FUNC-NNN`): Test cases derived from each item in the Functional Requirements sub-section.
- **Testing and Validation** (`TC-TVAL-NNN`): Test cases mapped 1:1 from the "Testing and Validation Requirements" sub-section.
- **Deployment/topology variations** (`TC-DEPLOY-NNN`): For each applicable row in the Deployment considerations table, generate platform-specific test scenarios.
- **Interoperability** (`TC-INTOP-NNN`): For each item in Interoperability Considerations (both prose and issuelinks), generate a test scenario.
- **Upgrade/rollback** (`TC-UPGRD-NNN`): Generate upgrade and rollback scenarios only when the issue, linked PRs, or release contract documents a supported upgrade or rollback path. Include feature-gate lifecycle transitions when applicable.
- **Success Criteria** (`TC-SUCC-NNN`): For each item in the Success Criteria section (Adoption and Outcomes), generate a scenario with explicit pass/fail criteria.
- **Non-functional** (`TC-NFR-NNN`): Scenarios derived from every Non-Functional Requirements item. Include measurable criteria where quantitative targets exist; for qualitative requirements, define observable expected behavior. When a specific NFR does not warrant a dedicated test scenario, document it with a rationale rather than silently omitting it.
- **Operational** (`TC-OPS-NNN`): Day-2 operational scenarios derived from Operational Requirements.
- **Negative tests** (`TC-NEG-NNN`): For each Out of Scope item that explicitly defines unsupported behavior or a must-not-change boundary, generate a test verifying the stated constraint.

---

## 4. Document Structure (adapted from IEEE 829)

When OCPSTRAT-aware parsing is active and the target repository has no existing test plan convention (see SKILL.md Step 2a), generate the test plan as a Markdown document following the outline below. This outline is **adapted from** the IEEE 829 Level Test Plan structure for OpenShift feature readiness — it is not a verbatim reproduction of the standard. It is a **recommendation** for teams that do not have something already in place — teams with an existing process should keep their format. When an existing convention is detected, embed the OCPSTRAT-specific content within that format instead.

**Section applicability rule**: When a section is not relevant to the specific feature, include the section heading and write a single sentence explaining why it does not apply (e.g. *"This feature does not modify any upgrade-sensitive resources; upgrade/rollback testing is not applicable."*). Do not use a bare "N/A" marker — always provide context so reviewers understand the decision.

### Sections (adapted from IEEE 829)

1. **Test Plan Identifier**: `<OCPSTRAT-XXXX>-test-plan` — a unique identifier for this plan. For features requiring multiple plans (e.g. cross-component work), use descriptive suffixes (e.g. `OCPSTRAT-1234-networking-test-plan`).
2. **Introduction**:
   - **Purpose**: What this test plan validates — derived from the Feature Overview / Goal Summary.
   - **Scope**: What is in scope for testing (from Goals and Requirements) and what is explicitly excluded (from Out of Scope).
3. **Background / References**: The OCPSTRAT feature, enhancement proposals, design documents, upstream issues, and linked PRs. Use **real links**: `https://<jira-host>/browse/OCPSTRAT-XXXX`, `https://github.com/<org>/<repo>/pull/<N>`. Derive the Jira host from the MCP connection or `$JIRA_URL`. If the host is unavailable, use the Jira key without a URL rather than a placeholder.
4. **Test Items**: Software components, operators, APIs, or CLI tools under test — derived from the feature description and linked PRs.
5. **Features to Be Tested**: Each testable capability, drawn from Functional Requirements, Testing and Validation Requirements, Use Cases, and Success Criteria.
6. **Features Not to Be Tested**: Items from Out of Scope and any Requirements explicitly marked as deferred. Include the Criteria Assessment — list any acceptance criteria that are untestable or tautological with an explanation.
7. **Approach**: Testing strategy with three subsections:
   - **Testing strategy table**: CI tier assignments (unit, integration, e2e-serial, e2e-parallel, e2e-periodic) with cost reasoning. Do not assign scenarios to `payload` tier — payload jobs are managed by TRT/QSE, not feature teams.
   - **CI placement matrix**: For each downstream repository that holds test code, list what runs **pre-merge** (PR CI) vs **post-merge** (periodic/release jobs). This is what makes the plan actionable — it tells engineers exactly where to put each test and when it will execute. Do not use a sequential "Execution phases" list — CI jobs run in parallel, not in a prescribed order. Example structure:
     ```
     openshift/<component>:
       Pre-merge: unit tests (TC-FUNC-xxx)
       Post-merge: none
     openshift/origin:
       Pre-merge: e2e-parallel (TC-DEPLOY-003–005)
       Post-merge periodic: e2e-serial disruptive-longrunning (TC-DEPLOY-001–002, TC-UPGRD-xxx)
     ```
8. **Item Pass/Fail Criteria**: Criteria for each test item — derived from acceptance criteria, non-functional requirements, and observable expected behavior. Where quantitative targets exist, state them explicitly. Where no numeric threshold exists but the criterion has relevant qualitative expected behavior, define pass/fail evidence based on observable outcomes. When a criterion is genuinely not applicable, explain why in a sentence.
9. **Suspension Criteria and Resumption Requirements**: External dependencies that could block testing — e.g. waiting on upstream deliverables, build system outages, infrastructure unavailability, or blocked development dependencies outside the team's control. This section describes dependency-driven blockers, not test automation logic (which belongs in test design). When not applicable, explain why.
10. **Test Deliverables**: Expected outputs — the test plan document, test case results, defect reports, and any CI artifacts or coverage reports.
11. **Testing Tasks**: Discrete work items — environment provisioning, test case authoring, execution passes, regression sweeps, results analysis.
12. **Environmental Needs**: Infrastructure, cluster topologies, and platform configurations required — derived from the Deployment considerations matrix. Include feature-gate configuration steps.
13. **Responsibilities**: Roles involved (engineering, SRE, release engineering) and their testing responsibilities. Do not reference "QE" as a separate team — development and testing are owned by the engineering team.
14. **Staffing and Training Needs**: Skill gaps or training requirements for engineers executing the test plan. Do not reference "QE engineers" — use "engineers". When not applicable, explain why.
15. **Schedule**: Only include hard dates from external dependencies (e.g. upstream delivery dates, stabilization period start, GA release date). Do not invent feature-specific test milestones. Use `TBD` for items not yet scheduled.
16. **Risks and Contingencies**: Risks to the testing effort and mitigation strategies.
17. **Approvals**: Placeholder for stakeholder sign-off. Typical approvers: Feature Owner or Feature Lead, and optionally a Test Lead if one is assigned. Do not reference "QE Lead".
18. **Test Approach Details**: High-level description of what testing occurs for each scenario category, integrated into the Approach section (§7). Keep this at the strategy level — describe *what* is tested and *why*, not individual test case steps. Categories:
    - Functional validation, Testing and Validation, Deployment/topology, Interoperability, Upgrade/rollback, Non-functional, Operational / Day-2, Negative tests, Regression

    **Detailed test case lists, existing coverage analysis, and coverage summaries** should be generated as **separate referenced documents** (not inline in the test plan) to keep the plan focused. Reference them from the plan:
    - `<feature-name>-test-cases.md` — full test case inventory with IDs, CI tiers, target file paths, traceability, implementation status, and coverage status
    - `<feature-name>-coverage-analysis.md` — existing test coverage gap report and coverage summary

    Offer to generate these companion documents on follow-up request.

---

## 4a. OCP-Specific Extensions (beyond IEEE 829)

The following sections are **not part of IEEE 829**. They are OpenShift-specific additions that address real-world needs IEEE 829 does not cover. In the generated plan, these sections are clearly labeled as *"OCP Extension — not part of IEEE 829"* so readers know which sections are standard and which are added.

| Extension | Why IEEE 829 doesn't cover it | Why OCP needs it |
|-----------|-------------------------------|------------------|
| Plan Status Header | IEEE 829 has no plan lifecycle tracking | Teams need to track Draft → In Review → Approved → Final |
| Feature Gates | IEEE 829 predates feature-gated software | OCP features are often behind alpha/beta gates that engineers must enable |
| Pre-existing Verification Evidence | IEEE 829 only looks forward (plan new tests) | PR authors already include test results — don't lose that evidence |
| Existing Test Coverage (separate doc) | IEEE 829 assumes a blank slate | Engineers need to know what's ALREADY tested — kept as a separate referenced document to keep the plan focused |
| Repo-Organized Tables | IEEE 829 assumes a single test organization | OCP test plans target multiple downstream repos (`openshift/<component>`, `openshift/origin`); tables organized by repo help teams see what each needs to implement |
| OCP Version Applicability Matrix | IEEE 829 assumes one target version | OCP runs CI across multiple versions (4.18, 4.22, 5.0) — tests must skip gracefully |
| Conformance Metadata | IEEE 829 is human-readable only | Tooling and automation need machine-readable YAML (scenario counts, tier distribution) |
| Deferred Scenarios Appendix | IEEE 829 has "out of scope" but no prioritized backlog | Teams need Phase 2 backlog with effort/value for planning |

### OCP Extension Sections

**EXT-1. Plan Status Header** *(placed before the title)*:
```markdown
**Plan Status:** Draft
**Feature:** [OCPSTRAT-XXXX](https://...) — <summary>
**Testing Epic:** [TESTING-EPIC-KEY](https://...) (if linked)
**Component:** <component from Jira>
```
`Plan Status` is always `Draft` for generated plans. Omit `Testing Epic` if no testing-specific epic is linked.

**EXT-2. Feature Gates** *(placed after §1, when the feature is gated)*:
A dedicated section listing each feature gate with: gate name, lifecycle phase (alpha/beta/GA), default state (on/off), minimum Kubernetes/OCP version, and enable command if needed.
| Gate | Phase | Default | Min Version | Enable Command |
|------|-------|---------|-------------|----------------|
| `MyFeatureGate` | alpha | off | K8s 1.36+ / OCP 4.23+ | `oc patch featuregate cluster ...` |

**EXT-3. Pre-existing Verification Evidence** *(placed after §17)*:
Author-provided test results, coverage baselines, and verification evidence extracted from PR bodies (SKILL.md Step 1l). Omit this section if no evidence was found in PRs.

**EXT-4. Existing Test Coverage** *(generated as a separate referenced document, not inline)*:
Gap report from SKILL.md Step 3a — generated as `<feature-name>-coverage-analysis.md`. Referenced from the test plan but kept separate to avoid bloating the plan. Contains what is already covered (`[COVERED]`), partially covered (`[PARTIAL]`), and missing (`[GAP]`).

**EXT-5. Repo-Organized Tables + OCP Version Matrix** *(within the companion test cases document)*:
- **Separate test tables by downstream repository**: (1) **Component Repo Tests** (`openshift/<component>`) — unit/integration tests, (2) **Origin E2e Tests** (`openshift/origin`) — e2e tests in a running OCP cluster. Optionally include (3) **Upstream Coverage Reference** — a summary of what the community project already tests (informational only).
- **OCP Version Applicability Matrix**: When tests have version-dependent skip conditions:
    | OCP version | Kubernetes | Feature available | Tests that run | Tests that skip |
    |---|---|---|---|---|
    | 4.18–4.20 | 1.31–1.33 | No | TC-NEG-00x (missing-dependency) | All happy-path |
    | 4.23+ | 1.36+ | Yes | All happy-path | Missing-dependency |

**EXT-6. Conformance Metadata** *(placed at the end, wrapped in an HTML comment so it does not render)*:
Wrap the YAML block in `<!-- ... -->` so it is hidden in rendered Markdown but available for tooling:
```markdown
<!--
plan_version: 1
generated_at: <ISO-8601 timestamp>
jira_key: <OCPSTRAT-XXXX>
jira_status: <status at generation time>
scenario_count: <N>
scenarios_by_tier:
  unit: <N>
  integration: <N>
  e2e-serial: <N>
  e2e-parallel: <N>
  e2e-periodic: <N>
coverage:
  covered: <N>
  partial: <N>
  gap: <N>
  preliminary: <N>
core_component: <true|false>
feature_gate: <gate-name or null>
-->
```

**EXT-7. Appendix: Deferred Scenarios** *(optional — include when scenarios are intentionally postponed)*:
A structured table of scenarios deferred to Phase 2 or later, with prioritization:
| ID | Scenario | Estimated Effort | Value | Why Deferred | Status |
|---|---|---|---|---|---|
| TC-DEFER-001 | Borrowing across cohorts | Medium | High | Blocked by upstream feature X | Not started |

This gives the team a prioritized backlog for future test work — not just a flat "out of scope" list. Include effort and value estimates to help prioritize.

---

## 5. Readiness Guidance

Do **not** include a separate "Readiness Integration" section in the generated plan — it duplicates Testing Tasks and other IEEE 829 sections. Instead, embed readiness actions directly into the relevant sections:

- In **Testing Tasks** (§11): include "Link test plan on OCPSTRAT feature" and "Commit plan to `docs/test-plans/`" as tasks.
- In **Test Deliverables** (§10): note that the plan should be stored in the component repository's `docs/test-plans/` directory.
- For features spanning multiple repos: note in §1 (Identifier) that separate per-component plans may be needed.

---

## 6. Reporting

In addition to the generic reporting steps (Step 6 in the main skill):

- Note which format the plan follows: IEEE 829 (when no repo convention was detected) or the repository's existing convention (when one was found in Step 2a). Highlight the readiness integration steps (linking, storage, work item derivation).
- Report the tier distribution (how many scenarios at each CI tier).
- Report the coverage status summary (covered/partial/gap).
- If a core component was detected, note the multi-repo tracking and any upstream coverage references.
- If customer names were scrubbed from Customer Considerations, note that scrubbing was applied.
- Offer to expand specific Detailed Test Case categories with full step-by-step instructions on follow-up request.

---

## 7. OCPSTRAT Guidelines

- Map every "Testing and Validation Requirements" item to at least one test scenario.
- Every scenario must have a unique ID (`TC-<CATEGORY>-<NNN>`), a CI tier, and a target file path (identifies the downstream repo).
- When the target repository has no existing test plan convention (see SKILL.md Step 2a), generate the test plan as an IEEE 829-style Markdown document with all standard sections. When a section is not relevant, include the heading and explain why — do not use bare `N/A` markers. When an existing convention is detected, follow that format instead and embed OCPSTRAT-specific content within it.
- Retain the Deployment/topology, Interoperability, Non-Functional, Upgrade/rollback, and Negative Testing section headings; populate them when source data is present, and explain their omission when it is absent.
- Map each Success Criteria item to at least one test scenario with explicit pass/fail criteria.
- Include readiness guidance on linking, storage, multiple plans, and work item derivation.
- Present the Detailed Test Cases appendix as a coverage summary by default; expand on follow-up.
- Default to the cheapest CI tier for each scenario. Justify tier placement.
- Use real links to Jira and GitHub — never placeholders.
- Scrub customer names from generated output. Replace with generic identifiers.
- Read interoperability from both Jira issuelinks and prose sections.
- Parse the Quality Status table when present and flag discrepancies with generated counts.
- Do not generate scenarios for untestable or tautological acceptance criteria.
