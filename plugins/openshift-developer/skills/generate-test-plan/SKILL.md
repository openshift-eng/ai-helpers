---
name: generate-test-plan
description: Generate a comprehensive manual testing guide from a Jira issue, GitHub PR URLs, or both. Use when the user wants test steps, a QE test plan, or a testing guide for code changes.
---

## Name
openshift-developer:generate-test-plan

## Synopsis
```text
/openshift-developer:generate-test-plan <JIRA_KEY | PR_URL> [additional PR URLs...]
```

## Description
Generates a comprehensive manual testing guide by analyzing a Jira issue, one or more GitHub PRs, or both. Consolidates context from Jira acceptance criteria, PR diffs, commit messages, and changed files into actionable test scenarios.

When given a Jira key, it auto-discovers linked PRs. When given PR URLs directly, it works without Jira. Both can be combined.

## Implementation

### Step 1: Parse input and gather sources

1. Parse arguments:
   - If `$1` matches a Jira issue key pattern (e.g. `CNTRLPLANE-205`, `OCPBUGS-12345`): treat as Jira key
   - If `$1` is a GitHub URL: treat as PR URL (no Jira context)
   - Remaining arguments (`$2`, `$3`, ...): additional PR URLs

2. **If a Jira key was provided**, fetch Jira issue details using the Jira MCP tools (`mcp__atlassian__jira_get_issue`):
   - Issue summary, description, acceptance criteria
   - Steps to reproduce (for bugs)
   - Issue type (Story, Bug, Task, etc.)
   - **Project key** (e.g. `OCPSTRAT`, `OCPBUGS`, `CNTRLPLANE`)

3. **Detect OCPSTRAT feature template**: If the issue's project is `OCPSTRAT` and the issue type is `Feature`, activate OCPSTRAT-aware parsing. Extract each template section by matching `h3.` wiki-style headings (e.g. `h3. *Testing and Validation Requirements*`). The standard OCPSTRAT feature template sections are:
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

   If OCPSTRAT-aware parsing is active but specific sections are absent, proceed with whichever sections are present; fall through to generic behavior for any missing content.

   For **non-OCPSTRAT issues** (or OCPSTRAT issues that do not follow the template), skip this step entirely and continue with the generic flow below.

4. **Discover PRs**:
   - If explicit PR URLs were provided: use only those
   - If only a Jira key was provided: use `mcp__atlassian__jira_get_issue` with `include: "remote_links"` and look for GitHub PR links. Also check the issue description and comments for PR URLs.
   - For each PR, fetch details:
     ```bash
     gh pr view <PR_NUMBER> --repo <owner/repo> --json title,body,commits,files,labels,state
     ```
   - Read changed files and their diffs to understand implementation

### Step 2: Analyze changes

1. Identify the type of change (feature, bug fix, refactor)
2. Determine affected components (API, CLI, operator, control-plane, etc.)
3. Find platform-specific changes (AWS, Azure, KubeVirt, etc.)
4. When multiple PRs exist:
   - Map which PR addresses which component or aspect
   - Identify dependencies between PRs
   - Determine testing order
5. Use Grep and Glob to find related test files, configuration, and documentation
6. **OCPSTRAT-specific analysis** (when OCPSTRAT-aware parsing is active):
   - Map the "Testing and Validation Requirements" section items directly to test scenario categories — each requirement should produce at least one test scenario
   - Parse the "Deployment considerations" table to extract a platform/topology matrix of applicable configurations
   - Map each "Interoperability Considerations" item to an interoperability test scenario
   - Derive end-to-end scenario-based tests from the "Use Cases" section
   - Map "Non-Functional Requirements" to performance, scale, and reliability test scenarios
   - Derive negative test cases from the "Out of Scope" section only when items explicitly define unsupported behavior or must-not-change boundaries; otherwise record them as exclusions without inferring expected behavior
   - Map "Operational Requirements" to Day-2 operational test scenarios (metrics exposure, troubleshooting workflows, support runbook validation)
   - Use "Customer Considerations" to inform edge-case and real-world usage test scenarios
   - Use "Goals" to inform overall test plan scope and prioritization — Goals do not require individual test mappings but should guide which scenarios are high priority

### Step 3: Generate test scenarios

1. Map Jira acceptance criteria to test cases (when Jira context available)
2. For bugs: derive test cases from reproduction steps
3. Generate scenarios covering:
   - Happy path (based on acceptance criteria or PR description)
   - Edge cases and error handling
   - Platform-specific variations if applicable
   - Regression scenarios for related features
4. For multiple PRs: create integration scenarios verifying PRs work together
5. **OCPSTRAT-specific scenario categories** (when OCPSTRAT-aware parsing is active — generate these in addition to the generic scenarios above):
   - **Functional validation**: test cases derived from each item in the Functional Requirements sub-section
   - **Testing and Validation**: test cases mapped 1:1 from the "Testing and Validation Requirements" sub-section (e.g. "Validate upgrade and rollback behavior" → upgrade/rollback test scenario)
   - **Deployment/topology variations**: for each applicable row in the Deployment considerations table, generate platform-specific test scenarios (e.g. "Verify feature on SNO cluster", "Verify on restricted network", "Verify on HCP deployment")
   - **Interoperability**: for each item in Interoperability Considerations, generate a test scenario that validates co-existence (e.g. "Verify feature works alongside NetworkPolicy enforcement")
   - **Upgrade/rollback**: include upgrade and rollback scenarios by default for OCPSTRAT features, as these are commonly required for release readiness
   - **Non-functional**: performance, scale, and resiliency scenarios derived from Non-Functional Requirements (e.g. "Verify minimal control-plane performance regression")
   - **Operational**: Day-2 operational scenarios derived from Operational Requirements (e.g. "Verify metrics are exposed for reconciliation failures", "Verify troubleshooting workflows are documented and functional")
   - **Negative tests**: for each Out of Scope item that explicitly defines unsupported behavior or a must-not-change boundary, generate a test verifying the stated constraint (e.g. "Verify that non-OVN-Kubernetes CNI providers are not affected"); record remaining Out of Scope items as exclusions without inferring expected behavior

### Step 4: Apply smart filtering

Skip PRs that don't require testing:
- PRs with only documentation changes (`.md` files)
- PRs with only CI/tooling changes (`.github/`, `.claude/` directories)
- PRs with labels like `skip-testing` or `docs-only`

Note skipped PRs in the output with reasoning.

### Step 5: Create the test guide

**Filename convention**:
- Jira-based: `test-{jira-key-lowercase}.md` (e.g. `test-cntrlplane-205.md`)
- PR-only: `test-pr-{number1}-{number2}.md` (e.g. `test-pr-6888-6889.md`)

**Generic document structure** *(for non-OCPSTRAT issues or OCPSTRAT issues that do not follow the template)*:

- **Summary**: Jira key + title (if available), list of PRs with titles, overall objective
- **Prerequisites**: Required infrastructure, tools, environment setup, access requirements
- **Test Scenarios**: Numbered test cases with:
  - Clear step-by-step instructions
  - Expected results and verification commands
  - Mapping to acceptance criteria (when Jira context available)
  - Platform-specific variations where applicable
- **Deployment Matrix** *(OCPSTRAT features only, when deployment-consideration data is present)*: A table of platform/topology combinations to test, derived from the Deployment considerations table. Each row is a configuration axis (e.g. "Self-managed classic", "HCP", "SNO", "Restricted network", "ARM") with columns for: configuration name, applicability (Yes/No/N/A), and notes on specific test variations needed.
- **Interoperability Testing** *(OCPSTRAT features only, when interoperability data is present)*: Dedicated test scenarios for each item listed in Interoperability Considerations. Each scenario verifies co-existence with the named feature or component (e.g. "Verify feature with NetworkPolicy enforcement enabled", "Verify feature with EgressIP configured").
- **Non-Functional Testing** *(OCPSTRAT features only, when NFR data is present)*: Performance, scale, and resiliency test scenarios derived from Non-Functional Requirements. Include measurable criteria where specified (e.g. "Verify minimal control-plane performance regression under load").
- **Negative Testing** *(OCPSTRAT features only, when out-of-scope data is present)*: Test cases derived from Out of Scope items that explicitly define unsupported behavior or must-not-change boundaries (e.g. "Verify that non-supported CNI providers are unaffected"). Items that merely indicate lack of coverage are recorded as exclusions without generating test cases.
- **Regression Testing**: Related features to verify, areas that might be affected
- **Success Criteria**: Checklist mapping to Jira acceptance criteria (when available)
- **Troubleshooting**: Common issues and debug steps
- **Notes**: Known limitations, links to Jira and PRs, dependencies between PRs

**Exclusions**: Do NOT include build/deploy steps or cleanup steps. Assume the environment is already set up. Focus purely on testing procedures.

**OCPSTRAT Feature document structure** *(IEEE 829-style — use instead of the generic structure when OCPSTRAT-aware parsing is active)*:

When OCPSTRAT-aware parsing is active, generate the test plan as a Markdown document following the IEEE 829 Test Plan outline adapted for OpenShift feature readiness. Include every section below; mark a section `N/A` when it is not relevant to the specific feature rather than omitting it.

1. **Test Plan Identifier**: `<OCPSTRAT-XXXX>-test-plan` — a unique identifier for this plan. For features requiring multiple plans (e.g. cross-component work), use descriptive suffixes (e.g. `OCPSTRAT-1234-networking-test-plan`, `OCPSTRAT-1234-storage-test-plan`).
2. **Introduction**:
   - **Purpose**: What this test plan validates — derived from the Feature Overview / Goal Summary.
   - **Scope**: What is in scope for testing (from Goals and Requirements) and what is explicitly excluded (from Out of Scope).
3. **Background / References**: The OCPSTRAT feature, enhancement proposals, design documents, upstream issues, and linked PRs. Use generic placeholders (e.g. "the OCPSTRAT feature for this plan") rather than embedding organization-internal URLs directly.
4. **Test Items**: Software components, operators, APIs, or CLI tools under test — derived from the feature description and linked PRs.
5. **Features to Be Tested**: Each testable capability, drawn from Functional Requirements, Testing and Validation Requirements, and Use Cases.
6. **Features Not to Be Tested**: Items from Out of Scope and any Requirements explicitly marked as deferred or not applicable. Record these as exclusions.
7. **Approach**: Testing strategy — manual vs. automated, environment tiers (dev, staging, CI), and how the OCPSTRAT-specific scenario categories (functional, deployment/topology, interoperability, non-functional, operational, upgrade/rollback, negative) map to execution phases.
8. **Item Pass/Fail Criteria**: Measurable criteria for each test item — derived from acceptance criteria and non-functional requirements where quantitative targets exist. Use `N/A` for items without measurable thresholds.
9. **Suspension Criteria and Resumption Requirements**: Conditions under which testing should halt (e.g. blocking infrastructure failures, critical defect discovery) and what must be resolved before resumption. Use `N/A` when not applicable to the feature.
10. **Test Deliverables**: Expected outputs — the test plan document, test case results, defect reports, and any CI artifacts or coverage reports.
11. **Testing Tasks**: Discrete work items — environment provisioning, test case authoring, execution passes, regression sweeps, results analysis.
12. **Environmental Needs**: Infrastructure, cluster topologies, and platform configurations required — derived from the Deployment considerations matrix.
13. **Responsibilities**: Roles involved (QE, development, SRE, release engineering) and their testing responsibilities. Use generic role names.
14. **Staffing and Training Needs**: Skill gaps or training requirements for the testing team. Use `N/A` if not applicable.
15. **Schedule**: High-level timeline or milestones for test execution relative to the release cycle. Use `TBD` for items not yet scheduled.
16. **Risks and Contingencies**: Risks to the testing effort (environment availability, dependency delays, scope changes) and mitigation strategies.
17. **Approvals**: Placeholder section for stakeholder sign-off — list the roles that should approve the plan (e.g. QE lead, feature owner).
18. **Detailed Test Cases** *(appendix)*: The full set of numbered test cases, organized by the OCPSTRAT-specific scenario categories defined in Step 3:
    - Functional validation (from Functional Requirements)
    - Testing and Validation (from Testing and Validation Requirements)
    - Deployment/topology variations (from the Deployment Matrix — include the platform/topology table here)
    - Interoperability (from Interoperability Considerations)
    - Upgrade/rollback
    - Non-functional (from Non-Functional Requirements — include measurable criteria)
    - Operational / Day-2 (from Operational Requirements)
    - Negative tests (from explicit Out of Scope boundaries only)
    - Regression scenarios

    Each test case includes: ID, title, preconditions, step-by-step instructions, expected results, and verification commands.

**Readiness guidance** *(OCPSTRAT features only — include at the end of the generated document in a "Readiness Integration" section)*:

- **Link from the feature**: Add the test plan as a link or reference on the OCPSTRAT feature so it is discoverable during readiness reviews.
- **Store in a Git repository**: Commit the Markdown test plan to an appropriate repository (e.g. the component repository's `docs/` or `test-plans/` directory, or a dedicated quality repository) so it is version-controlled and reviewable.
- **Multiple plans for complex work**: For features spanning multiple components or repositories, generate separate per-component test plans and cross-reference them. Each plan should be self-contained but reference sibling plans for the same feature.
- **Derive work items**: Use the Testing Tasks and Detailed Test Cases sections to create specific quality work items (e.g. stories or tasks for the QE team). Each work item should trace back to a test case ID in the plan.

### Step 6: Report

- Show the file path where the guide was saved
- Summarize: Jira issue (if applicable), number of PRs analyzed, number of test scenarios, critical test cases
- For OCPSTRAT features: note that the plan follows the IEEE 829 outline and highlight the readiness integration steps (linking, storage, work item derivation)
- Highlight skipped PRs and reasoning
- Ask if the user wants modifications

## Examples

1. **From a Jira issue (auto-discovers PRs)**:
   ```text
   /openshift-developer:generate-test-plan CNTRLPLANE-205
   ```

2. **From a Jira issue with specific PRs only**:
   ```text
   /openshift-developer:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
   ```

3. **From PR URLs only (no Jira)**:
   ```text
   /openshift-developer:generate-test-plan https://github.com/openshift/hypershift/pull/6888
   ```

4. **Multiple PRs without Jira**:
   ```text
   /openshift-developer:generate-test-plan https://github.com/openshift/hypershift/pull/6888 https://github.com/openshift/hypershift/pull/6889
   ```

5. **From an OCPSTRAT feature (generates IEEE 829-style plan with deployment matrix, interop, NFR sections)**:
   ```text
   /openshift-developer:generate-test-plan OCPSTRAT-3266
   ```

## Arguments
- `$1` — Jira issue key (e.g. `CNTRLPLANE-205`) or a GitHub PR URL (required)
- `$2, $3, ..., $N` — Additional GitHub PR URLs (optional)

## Guidelines
- Use Jira MCP tools for Jira data, `gh` CLI for PR data
- Derive test scenarios from actual code changes, not assumptions
- Keep test steps concrete with exact commands and expected output
- When Jira acceptance criteria exist, map every criterion to at least one test case
- For OCPSTRAT features, map every "Testing and Validation Requirements" item to at least one test scenario
- For OCPSTRAT features, generate the test plan as an IEEE 829-style Markdown document with all standard sections; use `N/A` for sections that are not applicable to the specific feature rather than omitting them
- For OCPSTRAT features, generate the Deployment Matrix, Interoperability Testing, Non-Functional Testing, and Negative Testing content only when the corresponding source data is present in the issue — omit the content entirely if no data exists, but keep the section heading with `N/A`
- For OCPSTRAT features, include readiness guidance on linking, storage, multiple plans, and work item derivation
- For non-OCPSTRAT issues or OCPSTRAT issues that do not follow the template, fall back to the generic flow with no changes to existing behavior
