# OCPSTRAT Feature Test Plan Reference

Use this reference **only** when the processed Jira issue is an OCPSTRAT Feature (project `OCPSTRAT`, issue type `Feature`). Follow the instructions below for template parsing, analysis, scenario generation, document structure, and reporting. All generic steps from the main skill still apply; this reference provides the OCPSTRAT-specific additions and overrides.

---

## 1. OCPSTRAT Feature Template Parsing

Extract each template section by matching `h3.` wiki-style headings (e.g. `h3. *Testing and Validation Requirements*`). The standard OCPSTRAT feature template sections are:

- **Feature Overview** (`h3. *Feature Overview*` or `h3. *Goal Summary*`)
- **Goals** (`h3. *Goals*`)
- **Requirements / Acceptance Criteria** (`h3. *Requirements*`), with sub-headings for:
  - Functional Requirements (`h4.`)
  - Testing and Validation Requirements (`h4.`)
  - Non-Functional Requirements (`h4.`)
  - Operational Requirements (`h4.`)
- **Use Cases** (`h3. *Use Cases*`)
- **Deployment considerations** — a table with topology rows (self-managed/managed, classic/HCP, multi-node/compact/SNO, connected/restricted, architectures, operator compat, backport, UI)
- **Interoperability Considerations** (`h3. *Interoperability Considerations*`)
- **Customer Considerations** (`h3. *Customer Considerations*`)
- **Out of Scope** (`h3. *Out of Scope*`)
- **Background** (`h3. *Background*`)
- **Success Criteria** (`h2. *Success Criteria*` — a top-level section, not `h3.`), with subsections:
  - Adoption (`h3.` or inline heading)
  - Outcomes (`h3.` or inline heading)

If specific sections are absent, proceed with whichever sections are present; fall through to generic behavior for any missing content.

---

## 2. OCPSTRAT-Specific Analysis

Perform these analysis steps **in addition to** the generic analysis (Step 2 items 1–5 in the main skill):

- Map the "Testing and Validation Requirements" section items directly to test scenario categories — each requirement should produce at least one test scenario
- Parse the "Deployment considerations" table to extract a platform/topology matrix of applicable configurations
- Map each "Interoperability Considerations" item to an interoperability test scenario
- Derive end-to-end scenario-based tests from the "Use Cases" section
- Map every "Non-Functional Requirements" item to an appropriate test scenario category (e.g. performance, scale, reliability, security, compatibility, resource consumption, usability, accessibility); when a specific NFR does not warrant a dedicated test scenario, document it as not applicable with a brief rationale
- Derive negative test cases from the "Out of Scope" section only when items explicitly define unsupported behavior or must-not-change boundaries; otherwise record them as exclusions without inferring expected behavior
- Map "Operational Requirements" to Day-2 operational test scenarios (metrics exposure, troubleshooting workflows, support runbook validation)
- Use "Customer Considerations" to inform edge-case and real-world usage test scenarios
- Use "Goals" to inform overall test plan scope and prioritization — Goals do not require individual test mappings but should guide which scenarios are high priority
- Map each item in the "Success Criteria" section (including Adoption and Outcomes subsections) to at least one test scenario with explicit pass/fail criteria derived from the stated metric or target

---

## 3. OCPSTRAT Scenario Categories

Generate these scenario categories **in addition to** the generic scenarios (Step 3 items 1–4 in the main skill):

- **Functional validation**: test cases derived from each item in the Functional Requirements sub-section
- **Testing and Validation**: test cases mapped 1:1 from the "Testing and Validation Requirements" sub-section (e.g. "Validate upgrade and rollback behavior" -> upgrade/rollback test scenario)
- **Deployment/topology variations**: for each applicable row in the Deployment considerations table, generate platform-specific test scenarios (e.g. "Verify feature on SNO cluster", "Verify on restricted network", "Verify on HCP deployment")
- **Interoperability**: for each item in Interoperability Considerations, generate a test scenario that validates co-existence (e.g. "Verify feature works alongside NetworkPolicy enforcement")
- **Upgrade/rollback**: generate upgrade and rollback scenarios only when the issue, linked PRs, or release contract documents a supported upgrade or rollback path; otherwise mark this category `N/A`
- **Success Criteria**: for each item in the Success Criteria section (Adoption and Outcomes), generate a scenario that validates the stated metric or target with explicit pass/fail criteria
- **Non-functional**: scenarios derived from every Non-Functional Requirements item, mapped to the appropriate category (performance, scale, reliability, security, compatibility, resource consumption, usability, accessibility, or other relevant concern). For example: "Verify minimal control-plane performance regression", "Verify TLS configuration meets security requirements", "Verify resource consumption stays within documented limits". When a specific NFR does not warrant a dedicated test scenario, document it as not applicable with a brief rationale rather than silently omitting it
- **Operational**: Day-2 operational scenarios derived from Operational Requirements (e.g. "Verify metrics are exposed for reconciliation failures", "Verify troubleshooting workflows are documented and functional")
- **Negative tests**: for each Out of Scope item that explicitly defines unsupported behavior or a must-not-change boundary, generate a test verifying the stated constraint (e.g. "Verify that non-OVN-Kubernetes CNI providers are not affected"); record remaining Out of Scope items as exclusions without inferring expected behavior

---

## 4. IEEE 829 Document Structure

When OCPSTRAT-aware parsing is active, generate the test plan as a Markdown document following the IEEE 829 Test Plan outline adapted for OpenShift feature readiness. **Use this structure instead of the generic document structure.** Include every section below; mark a section `N/A` when it is not relevant to the specific feature rather than omitting it.

1. **Test Plan Identifier**: `<OCPSTRAT-XXXX>-test-plan` — a unique identifier for this plan. For features requiring multiple plans (e.g. cross-component work), use descriptive suffixes (e.g. `OCPSTRAT-1234-networking-test-plan`, `OCPSTRAT-1234-storage-test-plan`).
2. **Introduction**:
   - **Purpose**: What this test plan validates — derived from the Feature Overview / Goal Summary.
   - **Scope**: What is in scope for testing (from Goals and Requirements) and what is explicitly excluded (from Out of Scope).
3. **Background / References**: The OCPSTRAT feature, enhancement proposals, design documents, upstream issues, and linked PRs. Use generic placeholders (e.g. "the OCPSTRAT feature for this plan") rather than embedding organization-internal URLs directly.
4. **Test Items**: Software components, operators, APIs, or CLI tools under test — derived from the feature description and linked PRs.
5. **Features to Be Tested**: Each testable capability, drawn from Functional Requirements, Testing and Validation Requirements, Use Cases, and Success Criteria (Adoption and Outcomes).
6. **Features Not to Be Tested**: Items from Out of Scope and any Requirements explicitly marked as deferred or not applicable. Record these as exclusions.
7. **Approach**: Testing strategy — manual vs. automated, environment tiers (dev, staging, CI), and how the OCPSTRAT-specific scenario categories (functional, deployment/topology, interoperability, non-functional, operational, upgrade/rollback, negative) map to execution phases.
8. **Item Pass/Fail Criteria**: Criteria for each test item — derived from acceptance criteria, non-functional requirements, and observable expected behavior. Where quantitative targets exist, state them explicitly. Where no numeric threshold exists but the criterion has relevant qualitative expected behavior (e.g. expected error handling, documented behavioral contracts, or observable system responses), define pass/fail evidence based on those observable outcomes. Use `N/A` only for items that are genuinely not applicable to the feature under test.
9. **Suspension Criteria and Resumption Requirements**: Conditions under which testing should halt (e.g. blocking infrastructure failures, critical defect discovery) and what must be resolved before resumption. Use `N/A` when not applicable to the feature.
10. **Test Deliverables**: Expected outputs — the test plan document, test case results, defect reports, and any CI artifacts or coverage reports.
11. **Testing Tasks**: Discrete work items — environment provisioning, test case authoring, execution passes, regression sweeps, results analysis.
12. **Environmental Needs**: Infrastructure, cluster topologies, and platform configurations required — derived from the Deployment considerations matrix.
13. **Responsibilities**: Roles involved (QE, development, SRE, release engineering) and their testing responsibilities. Use generic role names.
14. **Staffing and Training Needs**: Skill gaps or training requirements for the testing team. Use `N/A` if not applicable.
15. **Schedule**: High-level timeline or milestones for test execution relative to the release cycle. Use `TBD` for items not yet scheduled.
16. **Risks and Contingencies**: Risks to the testing effort (environment availability, dependency delays, scope changes) and mitigation strategies.
17. **Approvals**: Placeholder section for stakeholder sign-off — list the roles that should approve the plan (e.g. QE lead, feature owner).
18. **Detailed Test Cases** *(appendix — coverage summary by default)*: A coverage summary listing each OCPSTRAT-specific scenario category from section 3 above, the test cases derived per category (ID and title), the source requirement each traces to, and a coverage assessment (complete, partial, or gap). Include the following categories:
    - Functional validation (from Functional Requirements)
    - Testing and Validation (from Testing and Validation Requirements)
    - Deployment/topology variations (from the Deployment Matrix — include the platform/topology table here)
    - Interoperability (from Interoperability Considerations)
    - Upgrade/rollback (when documented — otherwise `N/A`)
    - Success Criteria (from Adoption and Outcomes — include explicit pass/fail criteria)
    - Non-functional (from every Non-Functional Requirements item — include measurable criteria where quantitative targets exist; for qualitative requirements, define observable expected behavior and pass/fail evidence)
    - Operational / Day-2 (from Operational Requirements)
    - Negative tests (from explicit Out of Scope boundaries only)
    - Regression scenarios

    For each category, list test case IDs, titles, and requirement traceability. Omit full step-by-step instructions, preconditions, and verification commands from the initial plan — offer to expand individual categories or test cases with full detail on follow-up request (e.g. "expand the Functional validation test cases" or "show full details for TC-FUNC-01").

---

## 5. Readiness Guidance

Include the following at the end of the generated document in a "Readiness Integration" section:

- **Link from the feature**: Add the test plan as a link or reference on the OCPSTRAT feature so it is discoverable during readiness reviews.
- **Store in a Git repository**: Commit the Markdown test plan to an appropriate repository (e.g. the component repository's `docs/` or `test-plans/` directory, or a dedicated quality repository) so it is version-controlled and reviewable.
- **Multiple plans for complex work**: For features spanning multiple components or repositories, generate separate per-component test plans and cross-reference them. Each plan should be self-contained but reference sibling plans for the same feature.
- **Derive work items**: Use the Testing Tasks and Detailed Test Cases sections to create specific quality work items (e.g. stories or tasks for the QE team). Each work item should trace back to a test case ID in the plan.

---

## 6. Reporting

In addition to the generic reporting steps (Step 6 in the main skill):

- Note that the plan follows the IEEE 829 outline and highlight the readiness integration steps (linking, storage, work item derivation)
- Offer to expand specific Detailed Test Case categories with full step-by-step instructions, preconditions, expected results, and verification commands on follow-up request

---

## 7. OCPSTRAT Guidelines

- Map every "Testing and Validation Requirements" item to at least one test scenario
- Generate the test plan as an IEEE 829-style Markdown document with all standard sections; use `N/A` for sections that are not applicable to the specific feature rather than omitting them
- Retain the Deployment/topology, Interoperability, Non-Functional, Upgrade/rollback, and Negative Testing section headings in the IEEE 829 outline; populate them when the corresponding source data is present in the issue, and mark them `N/A` when it is absent
- Map each Success Criteria item (Adoption and Outcomes) to at least one test scenario with explicit pass/fail criteria
- Include readiness guidance on linking, storage, multiple plans, and work item derivation
- Present the Detailed Test Cases appendix as a coverage summary (IDs, titles, requirement traceability) by default; expand individual categories or test cases with full step-by-step detail only on follow-up request
