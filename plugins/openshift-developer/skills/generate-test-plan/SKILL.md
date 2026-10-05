---
name: generate-test-plan
description: Generate a comprehensive testing guide from a Jira issue, GitHub PR URLs, or both. Use when the user wants test steps, a test plan, or a testing guide for code changes.
---

## Name
openshift-developer:generate-test-plan

## Synopsis
```text
/openshift-developer:generate-test-plan <JIRA_KEY | PR_URL> [additional PR URLs...]
```

## Description
Generates a structured testing guide by analyzing a Jira issue, one or more GitHub PRs, or both. Consolidates context from Jira acceptance criteria, PR diffs, commit messages, and changed files into actionable, ID-tagged test scenarios with CI tier placement, target file paths, and traceability.

When given a Jira key, it auto-discovers linked PRs. When given PR URLs directly, it works without Jira. Both can be combined.

## Implementation

### Step 1: Parse input and resolve sources

#### 1a. Parse arguments

- If `$1` matches a Jira issue key pattern (e.g. `CNTRLPLANE-205`, `OCPBUGS-12345`): treat as Jira key.
- If `$1` is a GitHub URL: treat as PR URL (no Jira context).
- Remaining arguments (`$2`, `$3`, ...): additional PR URLs.

#### 1b. Discover the Jira MCP tool and acquire cloudId

Do **not** hardcode a single MCP tool name. The Jira MCP tool name varies across environments. For each candidate below, check whether it requires a `cloudId` parameter **before** attempting an issue fetch:

1. For each candidate tool name:
   - `mcp__user_jira__jira_get_issue`
   - `mcp__plugin_jira_atlassian__getJiraIssue`
   - `mcp__atlassian__jira_get_issue`
2. Check the tool's schema/parameters to see if `cloudId` is required.
3. If `cloudId` is required, first call the tool's accessible-resources operation (e.g. `jira_list_accessible_resources` or equivalent) to obtain the `cloudId`. Extract it from the first accessible resource.
4. Then attempt a test fetch with the resolved `cloudId`.
5. Use the first candidate that responds successfully for all subsequent Jira calls.

If no MCP tool responds (not authenticated, no accessible sites, or none available), fall back to Bash-based Jira access via `ci:fetch-jira-issue`. Record which tool and `cloudId` were resolved for use in all later Jira calls.

**Fallback field coverage**: The `ci:fetch-jira-issue` fallback may not return all relationship fields (e.g. `parent`, `issuelinks`, `subtasks`). When using the fallback, make separate Jira REST calls (via `curl` or the fetch script's `--fields` option) to retrieve these fields if the initial response does not include them. Steps 1d–1e require `issuelinks`, `parent`, and `subtasks` for clone chain and link traversal — skip those steps only if the fields genuinely cannot be retrieved.

#### 1c. Fetch Jira issue (when a Jira key is provided)

Fetch the issue with **all** of these fields — do not omit any:

- `summary`, `description`, `status`, `issuetype`, `project`
- `acceptance criteria` — may be stored in a custom field (e.g. `customfield_12316743` or similar, varies by Jira instance) or embedded in the `description`. When using the MCP tool, include all custom fields in the request. When using the `ci:fetch-jira-issue` fallback, check whether acceptance criteria appear in the response; if not, make a separate REST call with `?fields=customfield_12316743` (resolve the field ID by searching Jira's field metadata for a field named "Acceptance Criteria").
- `parent` — the parent issue (epic or initiative)
- `issuelinks` — all linked issues (blocks, is blocked by, clones, is cloned by, relates to)
- `subtasks` — child issues
- `components`, `labels`, `fixVersions`

**Remote links** — fetch separately using the remote-links endpoint or parameter. Confirm the parameter name is correct for the discovered MCP tool (e.g. `properties=remoteLinks`, `include="remote_links"`, or a separate `jira_get_remote_links` call). Verify the response actually contains remote link data; if empty, fall back to scanning the description and comments for GitHub PR URLs.

#### 1d. Backport and clone chain traversal

If the issue has `is cloned by` or `cloned from` links (indicating backports or clones):

1. Follow the chain to the **root parent** — the original issue that carries the full change description and test evidence.
2. Use the root parent's description, acceptance criteria, and linked PRs as the primary context.
3. Note the backport chain in the output for traceability.

#### 1e. Parent, epic, and link traversal

Read `parent`, `issuelinks`, and `subtasks` fields:

- If the issue has a parent epic/feature, fetch its summary and description for broader context.
- For `issuelinks` of type `relates to`, `blocks`, `is blocked by`: fetch summaries to identify interoperability surfaces and dependencies.
- For `subtasks`: understand the decomposition and which parts are in scope.

#### 1f. Determine Jira content format

Jira returns content in different formats depending on API version and call parameters:

- **Atlassian Document Format (ADF)** — structured JSON with `type: "doc"`, `content: [...]`
- **HTML** — `<h3>`, `<p>`, `<table>` tags
- **Markdown** — `### heading`, `**bold**`
- **Wiki markup** — `h3. heading`, `*bold*`

**Detect the actual format** of the returned description/fields before parsing. Do not assume wiki markup. Parse section headings using the detected format:
- ADF: traverse `content` nodes for `heading` type
- HTML: match `<h1>`–`<h6>` tags
- Markdown: match `#`–`######` prefixes
- Wiki markup: match `h1.`–`h6.` prefixes

#### 1g. OCPSTRAT feature routing

If the issue's project is `OCPSTRAT` and the issue type is `Feature`:
1. Read [references/ocpstrat-feature.md](references/ocpstrat-feature.md) and follow its instructions.
2. For all subsequent steps, the OCPSTRAT reference provides overrides. Continue with the steps below for any areas not covered by the reference.

For **non-OCPSTRAT issues**, do not read the reference — continue with the generic flow.

#### 1h. Unfilled-template detection

Before proceeding, check whether the Jira issue contains substantive content:

- If the description consists primarily of placeholder text (e.g. `<Describe the feature>`, `TBD`, `TODO`, template boilerplate with no filled sections), **stop** and report: *"This issue's description appears to still contain unfilled template placeholders. The feature is not refined enough to generate a meaningful test plan. Please complete the following sections: [list unfilled sections]."*
- If the deployment considerations table is entirely blank or contains only placeholder rows, note this as a gap but continue if other sections have content.

#### 1i. Discover PRs

- If explicit PR URLs were provided: use those.
- If only a Jira key was provided: collect PR URLs from remote links (Step 1c), description, and comments.
- For each discovered PR, fetch details:
  ```bash
  gh pr view <PR_NUMBER> --repo <owner/repo> --json title,body,commits,files,labels,state,baseRefName,additions,deletions,changedFiles
  ```

#### 1j. PR state and branch validation

For each PR:

1. **Check state**: If a PR is `CLOSED` (not merged), skip it entirely and note: *"PR #N is closed without merging — skipped (code never shipped)."*
2. **Check base branch**: Record `baseRefName`. If the PR targets a release branch (e.g. `release-4.17`) but the test plan's target environment is `main`/`master`, flag: *"PR #N targets release branch `release-4.17` — test scenarios may not be executable on `main`. Verify branch compatibility."*

#### 1k. PR content classification

For each PR, classify its content by analyzing changed files:

| Classification | Criteria | Action |
|---|---|---|
| **Test-only** | All changed files are under `*_test.go`, `test/`, `e2e/`, or test fixture directories | Enter **test-code-as-deliverable mode** (Step 2b) |
| **Vendor-only** | All changed files are under `vendor/` | Skip with note: *"PR #N contains only vendor updates — no product test scenarios generated."* |
| **Generated-only** | All changed files match generated patterns (`zz_generated*`, `*_generated.go`, `bindata.go`) | Skip with note: *"PR #N contains only generated files — no product test scenarios generated."* |
| **Docs-only** | All changed files are `.md`, `.adoc`, or under `docs/` | Skip with note (existing behavior) |
| **Mixed** | Contains product code alongside test/vendor/generated | Analyze only the product code portion; note the non-product files separately |

#### 1l. PR body evidence extraction

Read each PR body for author-provided testing evidence:

- **Test results**: Look for sections like "Testing", "Test Results", "Verification", "How to test"
- **Coverage baselines**: Lines like `coverage: 85%`, coverage reports
- **Manual verification**: Screenshots, command output, cluster test results
- **Linked test PRs**: References to companion test PRs

Preserve this evidence and include it in the output under a "Pre-existing Verification Evidence" section.

#### 1m. Diff size normalization

Do not use raw `additions + deletions` as a proxy for change complexity. Compute normalized change size:

1. Start with the raw diff line count.
2. Subtract lines in `vendor/` paths.
3. Subtract lines in generated files (`zz_generated*`, `*_generated.go`, `bindata.go`, `*_openapi.go`).
4. Subtract lines in pure whitespace/formatting changes when detectable.
5. Report both raw and normalized size.

#### 1n. Zero-PR path

If the Jira issue is at an early stage (e.g. status is `New`, `Planning`, `Design`, `Refinement`, or `To Do`) and no implementation PRs exist:

- Generate a **preliminary test plan** based solely on the Jira description and acceptance criteria.
- Mark every scenario as `[PRELIMINARY — no implementation PR available]`.
- Omit sections that require code analysis (target file paths, existing test reconciliation).
- Note: *"This is a preliminary test plan based on requirements only. Re-run after implementation PRs are available for a complete plan with code-level analysis."*

### Step 2: Classify input and select output format

#### 2a. Detect target repository format and template conformance check

Before generating, check whether the target repository has its own test plan conventions:

1. Look for existing test plan files: `Glob` for `**/test-plan*.md`, `**/test_plan*.md`, `**/TEST_PLAN*`, `docs/test-plans/*`, `test-plans/*`, `docs/plans/**`.
2. Look for a test plan template: `Glob` for `**/TEMPLATE*test*`, `**/.github/ISSUE_TEMPLATE/*test*`.
3. If existing plans are found, read one to detect the local format and mirror it.
4. If no local convention exists, use the format rules in Step 5.

**Template conformance check**: When an existing team template or plan is detected (steps 1–3 above), map its sections against the checklist below and include a **Template Conformance Report** in the output. This tells the team where their template aligns with standard test plan practice and what they have intentionally left out — without forcing them to adopt any particular standard.

The following checklist is adapted from IEEE 829 (Level Test Plan outline) for OpenShift test plan use. It is not a verbatim reproduction of the standard:

| # | Section (adapted from IEEE 829) | Check |
|---|---|---|
| 1 | Test Plan Identifier | Does the template have a unique ID or naming convention? |
| 2 | Introduction (Purpose + Scope) | Does the template have an overview/introduction/scope section? |
| 3 | References | Does the template link to Jira, PRs, KEPs, or design docs? |
| 4 | Test Items | Does the template list components under test? |
| 5 | Features to Be Tested | Does the template enumerate testable capabilities? |
| 6 | Features Not to Be Tested / Out of Scope | Does the template have an exclusions section? |
| 7 | Approach / Test Strategy | Does the template describe the testing strategy (tiers, test ownership placement)? |
| 8 | Pass/Fail Criteria | Does the template define exit criteria? |
| 9 | Suspension Criteria | Does the template describe when to halt testing? |
| 10 | Test Deliverables | Does the template list expected outputs? |
| 11 | Testing Tasks | Does the template list work items? |
| 12 | Environmental Needs / Target Environments | Does the template specify required infrastructure? |
| 13 | Responsibilities | Does the template assign roles? |
| 14 | Staffing and Training Needs | Does the template identify skill gaps or training? |
| 15 | Schedule | Does the template include a timeline? |
| 16 | Risks | Does the template list risks? |
| 17 | Approvals | Does the template have a sign-off or approval section? |
| 18 | Detailed Test Cases | Does the template list scenarios with IDs? |

Output the conformance report as a table appended after the generated plan:

```markdown
## Template Conformance Report (vs IEEE 829)

| IEEE 829 Section | Team Template Section | Status |
|---|---|---|
| Test Plan Identifier | *Title + Plan Status header* | ✅ Covered |
| Introduction | *Overview + Introduction* | ✅ Covered |
| References | *References table* | ✅ Covered |
| Test Items | *(not present)* | ⚠️ Missing — consider listing components under test |
| Suspension Criteria | *(not present)* | ℹ️ Intentionally omitted — team uses ad-hoc suspension |
| ... | ... | ... |
```

Use three statuses:
- ✅ **Covered** — the team template has a matching section
- ⚠️ **Missing** — the team template lacks this section; the skill adds it to the generated plan and flags it for the team to review
- ℹ️ **Intentionally omitted** — the team template explicitly excludes this (e.g. "N/A" or "Not applicable" in the template)

When the skill mirrors the team template format (Priority 1 in Step 5a), it should still **fill in missing IEEE 829 sections** at the end of the plan as supplementary sections, clearly marked as *"Added by skill — not in team template"*. This way the team gets their format plus IEEE 829 coverage, and the conformance report shows the delta.

#### 2b. Test-code-as-deliverable mode

When all PRs are classified as **test-only** (Step 1k):

- Do **not** generate a test plan for product changes.
- Instead, generate a **test review document** that:
  - Summarizes what the test code covers
  - Identifies which product features/behaviors are now tested
  - Checks for gaps in the test code itself (missing edge cases, error paths)
  - Lists the test file paths and their coverage targets
  - Provides a "Test Adequacy Assessment" rather than "Test Scenarios"

#### 2c. Quality Status table parsing (OCPSTRAT features)

If the Jira issue contains a Quality Status table (structured table with columns like "Test Type", "Count", "Automated %"):

1. Parse the table to extract estimated test counts and automation percentages.
2. Use these as baseline expectations when generating scenario counts.
3. Flag discrepancies between the Quality Status estimates and the generated plan.

### Step 3: Analyze changes

#### 3.0. Strict sourcing rule — do not invent content

Every section of the generated test plan must be **traceable to data in the Jira issue, linked PRs, or the codebase**. The skill must never fabricate scenarios, requirements, or technical details that are not present in the input.

- **If a section has no corresponding data in the Jira issue**, do not fill it with assumptions. Instead, insert a gap marker:
  > ⚠️ **GAP — <Section Name>**: This section could not be populated because the feature description does not include `<missing info>`. Please update the feature ticket or fill this section manually.
- **If a section is genuinely inapplicable** to the feature (e.g. "Interoperability" for a single-component internal refactor), mark it with a reason:
  > This section is not applicable: `<one-sentence reason>`.
- **Do not infer deployment topologies** that are not mentioned in the Jira description or deployment considerations table.
- **Do not generate test scenarios** for capabilities not described in the requirements, goals, or acceptance criteria.
- **Do not assume feature gate names, repository names, or file paths** that are not discoverable from the Jira issue or linked PRs. Use `TBD` and flag the gap.

Examples of what to flag vs what to generate:

| Source data present? | Action |
|---|---|
| Jira says "must work on SNO" | ✅ Generate SNO topology test scenario |
| Jira has no mention of SNO | ❌ Do NOT generate SNO test — instead flag: *"Deployment considerations do not mention SNO. If SNO is in scope, update the feature ticket."* |
| Jira says "must support ETCD encryption" | ✅ Generate encryption test scenario |
| Jira has no security section | ❌ Do NOT invent security tests — flag: *"No security or encryption requirements found in the feature description."* |

1. Identify the type of change (feature, bug fix, refactor, test addition, backport).
2. Determine affected components (API, CLI, operator, control-plane, networking, storage, etc.).
3. Identify which repositories are involved (for multi-repo features).
4. Find platform-specific changes (AWS, Azure, KubeVirt, etc.).
5. When multiple PRs exist:
   - Map which PR addresses which component or aspect.
   - Identify dependencies between PRs.
   - Determine testing order.
6. Use Grep and Glob to find related test files, configuration, and documentation.

#### 3a. Existing test corpus reconciliation

For each component/package affected by the change:

1. **Find existing tests**: Use Grep/Glob to locate test files in the same package and related packages:
   ```
   Glob: <package>/*_test.go, test/e2e/*<component>*, test/extended/*<component>*
   Grep: function names matching the changed behavior
   ```

2. **Extract existing coverage**: For each existing test file found, extract:
   - Test function names (e.g. `TestFoo`, `It("should ...")`)
   - What behavior they cover (from test names and comments)
   - Which scenarios are already handled

3. **Generate a gap report**: For each proposed test scenario, mark it as:
   - `[COVERED]` — an existing test already validates this scenario (cite the test name and file)
   - `[PARTIAL]` — an existing test covers a related case but not this exact scenario
   - `[GAP]` — no existing test covers this scenario

Include the gap report in the output.

#### 3b. Interoperability analysis

Read interoperability data from **both** sources:

1. **Structured issuelinks**: Jira `issuelinks` fields of types `relates to`, `interoperates with`, etc. (fetched in Step 1e).
2. **Prose section**: The interoperability section in the Jira description (if present).

Merge both sources, deduplicating. Prefer structured data when both exist.

#### 3c. Acceptance criteria testability assessment

For each acceptance criterion from the Jira issue:

1. **Assess testability**: Is the criterion measurable and verifiable?
   - ✅ Testable: "API returns 404 when resource not found" → generates a scenario
   - ❌ Untestable/tautological: "E2E tests are written", "Should contribute to elevating perceived quality" → do **not** generate a test scenario
   - ⚠️ Ambiguous: "Performance is acceptable" → flag as needing refinement

2. Report untestable criteria in a "Criteria Assessment" section:
   *"The following acceptance criteria are tautological or unmeasurable and cannot be mapped to test scenarios: [list]. Consider refining these criteria with specific, observable conditions."*

### Step 4: Generate test scenarios

#### 4a. Scenario structure

Every test scenario **must** include:

| Field | Description |
|---|---|
| **ID** | Unique identifier: `TC-<CATEGORY>-<NNN>` (e.g. `TC-FUNC-001`, `TC-EDGE-003`, `TC-UPGRADE-001`) |
| **Title** | Concise description of what is being tested |
| **CI Tier** | One of: `unit`, `integration`, `e2e-serial`, `e2e-parallel`, `e2e-periodic` |
| **Tier Justification** | Why this tier was chosen (cost reasoning) |
| **Target File Path** | Where the test will live in the codebase (e.g. `test/e2e/network/ovn_egressip_test.go`). **Preliminary plans (Step 1n)**: set to `TBD — requires implementation PR` instead of inventing a path. |
| **Steps** | Numbered step-by-step instructions with expected results and verification commands. **For OCPSTRAT initial plans**: omit steps from the first generation (include only ID, title, tier, traceability, and status) — offer to expand on follow-up request. For non-OCPSTRAT plans or follow-up expansions: include full steps. |
| **Coverage Status** | `[COVERED]`, `[PARTIAL]`, or `[GAP]` from the reconciliation in Step 3a. **Preliminary plans (Step 1n)**: set to `[PRELIMINARY]` — coverage reconciliation requires code analysis and is skipped when no PRs are available. |
| **Implementation Status** | One of: `Implemented in <PR link>`, `To be automated`, `Manual only`. Track which tests exist vs which are planned. |
| **OCP Version Applicability** | Which OCP versions this test applies to (e.g. `4.23+`, `all`, `4.18–4.22 only`). If the test should `Skip` on certain versions, note the skip condition. |
| **Traceability** | Which requirement/acceptance criterion this maps to |

#### 4b. CI tier vocabulary and cost reasoning

Use the organization's CI tier vocabulary. Default to the **cheapest tier** that can validate the scenario:

| Tier | Cost | When to use |
|---|---|---|
| `unit` | Lowest | Pure logic, no cluster needed, fast. **Prefer this as default.** |
| `integration` | Low | Needs API server or etcd but not a full cluster |
| `e2e-serial` | Medium | Requires a running cluster and must run alone (destructive, cluster-scoped) |
| `e2e-parallel` | Medium | Requires a running cluster but safe to run concurrently |
| `e2e-periodic` | High | Long-running, expensive, or flake-prone — runs on a schedule, not every PR |
Include a brief cost justification for each scenario's tier placement. If a scenario can be validated at `unit` tier, do not place it at `e2e`.

> **Note:** `payload` tier (nightly/blocking payload jobs) is managed by TRT/QSE, not by feature teams. Do not assign scenarios to `payload` tier in generated test plans. Payload jobs are the most expensive CI tier and their configuration is a release-level decision, not a feature-level one.

When generating the §7 Approach section, include a **CI placement matrix** that maps each downstream repository to its pre-merge and post-merge test coverage. CI jobs run in parallel, not sequentially — do not generate a sequential "Execution phases" list. Instead, organize by repository and execution trigger:

- **Pre-merge** (PR CI): Tests that gate every pull request.
- **Post-merge periodic**: Tests that run on a schedule after merge (e.g. `disruptive-longrunning`, nightly suites).

This tells engineers exactly where to add each test and when it will run. All repositories in the matrix are downstream (`openshift/*`).

#### 4c. Scope and upstream references

##### Scope

This test plan covers **downstream** testing — all quality activities performed in `openshift/*` repositories for OCPSTRAT features selected for delivery in a specific OCP release. Features may have originated in a community project but the test plan's starting point is the code and PRs delivered in downstream repos.

> **Terminology:**
> - **Downstream** = all repositories in the `openshift/` namespace: `openshift/<component>`, `openshift/origin`, etc. This is where all new test development occurs.
> - **Upstream** = community project repositories (e.g. `kubernetes/kubernetes`, `kubernetes-sigs/*`). Upstream development and testing is **out of scope** for this plan.
> - **`openshift-tests-private`** is locked for new test contributions. Do not direct new test scenarios there.

All scenarios use the **Target File Path** to specify which downstream repo and file the test belongs in. No separate ownership tier column is needed — the file path already identifies the repo.

##### Upstream coverage reference (informational only)

When the feature builds on work from a community project, teams may know that certain functions are well-tested upstream. It is fine to reference this to justify reduced downstream test effort:

- Note which upstream scenarios already cover the feature's core logic.
- Reference the upstream test files or plans if known.
- Explain what additional downstream testing is needed beyond what upstream provides.

This is informational — the test plan does not direct work to upstream repos. Pushing tests upstream after rebase is out of scope.

#### 4d. Target file paths

For each scenario, specify where the test code should live:

1. If an existing test file covers the same component, place the new test there.
2. Otherwise, follow the repository's directory conventions:
   - `*_test.go` in the same package for unit tests
   - `test/e2e/<component>/` for e2e tests
   - `test/extended/<area>/` for extended tests
3. If no repository context is available, set the target file path to `TBD — requires repository context` and flag the gap per Step 3.0. Do not invent a path from generic patterns.

#### 4e. Scenario generation by change type

1. **Feature**: Map acceptance criteria to test cases. Generate happy path, edge cases, error handling, platform variations, regression scenarios.
2. **Bug fix**: Derive test cases from reproduction steps. The primary scenario is "verify the bug is fixed." Add regression tests for related paths.
3. **Refactor**: Focus on behavioral equivalence — tests that confirm no behavior changed.
4. **Backport**: Inherit scenarios from the parent issue's test plan if one exists. Note any branch-specific variations.

#### 4f. Feature gate documentation

If the feature uses Kubernetes or operator feature gates, include a **Feature Gates** section in the output with:

| Field | Description |
|---|---|
| **Gate name** | e.g. `MyFeatureGate`, `TechPreviewNoUpgrade` |
| **Lifecycle phase** | `alpha` (default-off), `beta` (default-on), `GA` (locked-on) |
| **Default state** | `enabled` or `disabled` at the target version |
| **Minimum version** | Kubernetes or OCP version required (e.g. `Kubernetes 1.36+ / OCP 4.23+`) |
| **Enable command** | If not default-on, the exact command to enable it |

This section is separate from Environmental Needs — it documents the gate lifecycle, not just the setup step.

#### 4g. Setup steps policy

Do **not** include generic build/deploy steps (e.g. `oc new-project`, cluster provisioning). However, **do** include:

- **Feature-gate configuration**: Steps to enable/disable the feature gate under test (e.g. `oc patch featuregate cluster --type merge -p '{"spec":{"featureSet":"TechPreviewNoUpgrade"}}'`)
- **Topology setup**: Cluster topology requirements that are essential to executing the test (e.g. "requires SNO cluster", "requires HCP deployment")
- **Test-specific configuration**: Any configuration that is part of the test itself (e.g. creating a NetworkPolicy, configuring a StorageClass)

#### 4h. Ginkgo pending test convention

When the target repository uses Ginkgo and a scenario is identified as manual (not yet automated), note that it should be registered as a pending Ginkgo test:

- Use `ginkgo.PIt` or `ginkgo.XIt` instead of `ginkgo.It` for the pending test case.
- Include labels: `manual:true` and `testCase:path/to/case-description.md` (pointing to the detailed test case markdown file).
- Example:
  ```go
  ginkgo.PIt("manual test, to be hopefully automated later on",
      ginkgo.Labels(
          "manual:true",
          "testCase:test/docs/cases/<feature>/<case-name>.md",
      ),
      func() {
          // manual test, not implemented yet
      },
  )
  ```
- A single test case markdown file can be referenced from multiple Ginkgo tests if needed.
- This convention enables future OTE enhancements to register and work with manual test cases alongside the automated test suite.

For each scenario marked as manual/pending, include the `PIt` registration path in the target file path field.

#### 4i. OCP version applicability matrix

When the feature or its dependencies are version-gated, generate a **Version Applicability Matrix** showing which tests run on which OCP/Kubernetes versions:

| OCP version | Kubernetes | Feature available | Tests that run | Tests that skip |
|---|---|---|---|---|
| 4.18–4.20 | 1.31–1.33 | No (APIs absent) | TC-NEG-00x (missing-dependency) | All happy-path tests |
| 4.23+ | 1.36+ | Yes | All happy-path tests | Missing-dependency tests |

For each scenario, include an **OCP Version Applicability** field. Tests should `Skip` (not fail) on versions where the feature is unavailable.

### Step 5: Create the test guide

#### 5a. Output format selection

IEEE 829 is a **recommendation**, not a requirement. Teams that already have a test plan format should keep it. The skill respects existing conventions first:

| Priority | Condition | Format |
|---|---|---|
| 1 (highest) | Repo has existing test plan convention (detected in Step 2a) | Mirror the detected convention |
| 2 | OCPSTRAT Feature, no existing convention | IEEE 829 (per [references/ocpstrat-feature.md](references/ocpstrat-feature.md)) — recommended, not mandated |
| 3 | Core component enhancement (OVN-K, installer, API server), no existing convention | Extended format with multi-repo tracking (see [references/ocpstrat-feature.md](references/ocpstrat-feature.md) §2a) |
| 4 (lowest) | Generic (all other cases), no existing convention | Generic format below |

If the target repository already has test plans in a different format, mirror that format even for OCPSTRAT features. IEEE 829 sections and scenario structure (IDs, tiers, file paths) should still be included as content within the existing format where possible.

#### 5b. Filename and path convention

Do **not** output a flat file in the current directory. Use the repository's conventional path:

1. If the repo has an existing test plan directory detected in Step 2a (e.g. `docs/plans/`, `docs/test-plans/`, `test-plans/`, or `test/docs/plans/`): use that directory.
2. Otherwise create `docs/test-plans/`.
3. **Filename**: Use the feature name (kebab-case), not the Jira key:
   - Jira-based: `docs/test-plans/<feature-name>.md` (e.g. `docs/test-plans/egress-ip-reachability.md`)
   - PR-only: `docs/test-plans/<component>-<brief-description>.md` (e.g. `docs/test-plans/ovn-kubernetes-egressip-fix.md`)
   - Derive the feature name from the Jira summary or PR title.

**Test case documentation**: When scenarios include manual test cases or cases not yet automated, recommend placing detailed test case documentation alongside the test plan:
- Convention: `test/docs/cases/` (or `docs/test-cases/`) in the same repository as the test plan.
- Format: Markdown with `# Setup`, `# Test` (with `## Step` / `## Expect` pairs), and `# Cleanup` sections.
- Reference: Each test case file can be referenced from multiple Ginkgo tests using the `testCase:path/to/case.md` label (see Step 4h).

#### 5c. Real links

Use **real, clickable links** throughout — never generic placeholders:

- Jira issues: `https://<jira-host>/browse/<KEY>` (derive the host from the MCP connection or `$JIRA_URL`)
- GitHub PRs: `https://github.com/<owner>/<repo>/pull/<number>`
- GitHub files: `https://github.com/<owner>/<repo>/blob/<branch>/<path>`

If the Jira host cannot be determined, use the Jira key as a reference (e.g. `OCPSTRAT-1234`) without a broken placeholder URL.

#### 5d. Abbreviations key

Every generated test plan must include an **Abbreviations** section (either in the introduction or as an appendix) so all readers — engineering, management — can follow the plan without guessing:

```markdown
## Abbreviations

| Abbreviation | Full Form |
|---|---|
| TC | Test Case |
| FUNC | Functional Test |
| TVAL | Testing and Validation Test |
| NEG | Negative Test |
| INTOP | Interoperability Test |
| DEPLOY | Deployment / Topology Test |
| UPGRD | Upgrade / Rollback Test |
| OPS | Operational / Day-2 Test |
| SUCC | Success Criteria Test |
| NFR | Non-Functional Requirement Test |
| SEC | Security Test |
| PROP | Propagation Test |
| REG | Regression Test |
| DEFER | Deferred Scenario (Phase 2+) |
| HCP | Hosted Control Planes (HyperShift) |
| SNO | Single Node OpenShift |
| MCO | Machine Config Operator |
| CVO | Cluster Version Operator |
| CRI-O | Container Runtime Interface for OCP |
| DRA | Dynamic Resource Allocation |
| IEEE 829 | IEEE Standard for Software Test Documentation |
| ADF | Atlassian Document Format |
```

Only include abbreviations that are actually used in the generated plan. Do not include unused entries.

#### 5e. Plan status header

Every generated test plan must start with a **metadata header** before the title:

```markdown
**Plan Status:** Draft
**Feature:** [OCPSTRAT-XXXX](https://...) — <summary>
**Testing Epic:** [TESTING-EPIC-KEY](https://...) (if a testing epic exists in Jira)
**Component:** <component name>
```

- `Plan Status` is always `Draft` for generated plans. The team changes it to `In Review` → `Approved` → `Final` as the plan progresses.
- `Testing Epic` — look for a linked epic or subtask specifically for testing. If none exists, omit the field.
- `Component` — from the Jira `components` field.

#### 5f. Generic document structure

For non-OCPSTRAT, non-repo-convention plans:

- **Test Plan Identifier**: `<JIRA-KEY>-test-plan` or `<component>-<description>-test-plan`
- **Summary**: Jira key + title (if available), list of PRs with titles and real links, overall objective
- **Prerequisites**: Required infrastructure, tools, environment setup, access requirements. Include feature-gate and topology setup steps where applicable.
- **Pre-existing Verification Evidence**: Author-provided test results, coverage baselines, and verification evidence extracted from PR bodies (Step 1l). If none, omit this section.
- **Criteria Assessment**: List of acceptance criteria with testability verdicts. Untestable criteria are listed here and excluded from scenarios.
- **Test Scenarios**: Scenarios with full structure per Step 4a (ID, CI tier, target file path, steps, coverage status, traceability)
- **Existing Test Coverage**: Gap report from Step 3a — what is already covered, what is partial, what is missing
- **Regression Testing**: Related features to verify, areas that might be affected
- **Success Criteria**: Checklist mapping to Jira acceptance criteria (when available)
- **Troubleshooting**: Common issues and debug steps
- **Notes**: Known limitations, real links to Jira and PRs, dependencies between PRs, backport chain if applicable
- **Conformance Metadata** (machine-readable YAML front matter or appendix):
  ```yaml
  plan_version: 1
  generated_at: <ISO-8601 timestamp>
  jira_key: <KEY>
  jira_status: <status at generation time>
  prs_analyzed:
    - url: <real PR URL>
      state: <open|merged|closed>
      base_branch: <branch>
  scenario_count: <N>
  coverage:
    covered: <N>
    partial: <N>
    gap: <N>
    preliminary: <N>
  ```

#### 5g. Deferred scenarios appendix

If any scenarios were intentionally deferred (lower priority, blocked by dependencies, or planned for Phase 2), include an **Appendix: Deferred Scenarios** section at the end with:

| ID | Scenario | Estimated Effort | Value | Why Deferred | Status |
|---|---|---|---|---|---|
| TC-DEFER-001 | Borrowing across cohorts | Medium | High | Blocked by upstream feature X | Not started |

This gives the team a prioritized backlog for future test phases, not just a flat "out of scope" list.

#### 5h. Organize test tables by downstream repository

When the feature spans multiple downstream repositories, **physically separate** the test scenario tables by repository:

1. **Component repo tests** (`openshift/<component>`): Unit and integration tests in the component's source repository.
2. **Origin e2e tests** (`openshift/origin`): E2e tests validating the component in a running OCP cluster.
3. **Upstream coverage reference** *(optional, informational)*: If the feature builds on community project work, summarize what is already tested upstream. This is a **reference** — not a directive for new upstream development. It helps justify where reduced downstream effort is appropriate.

This split makes it clear: (a) what the component team needs to implement, (b) what the e2e team needs to implement.

#### 5i. Preliminary plan markers (zero-PR path)

When generating a preliminary plan (Step 1n), add a banner at the top:

```markdown
> ⚠️ **PRELIMINARY TEST PLAN** — Generated from requirements only (no implementation PRs available).
> Scenarios are based on acceptance criteria and may change when implementation details are known.
> Re-run this command after implementation PRs are available.
```

### Step 6: Report and iterative workflow

#### 6a. First-generation report

- Show the file path where the guide was saved.
- Summarize: Jira issue (if applicable), number of PRs analyzed, number of test scenarios by tier, coverage status summary (N covered, N partial, N gaps, N preliminary).
- Report skipped PRs and reasoning (closed unmerged, vendor-only, generated-only, docs-only).
- Report unfilled template sections or untestable criteria if any.
- Report backport chain if traversed.
- **List all gap markers** (⚠️ GAP sections) so the reviewer knows exactly what needs manual attention.
- Ask if the user wants modifications.

#### 6b. Human review cycle

After the first generation, the expected workflow is:

1. **Human reviews** the generated plan and fills in domain-specific details, corrects any inaccuracies, and adds sections the skill flagged as gaps.
2. **Human updates the feature ticket** if the skill flagged missing information (e.g. deployment considerations, security requirements, feature gate names).
3. **Re-run the skill** on the same Jira key after the feature ticket is updated. The skill will regenerate the plan reflecting the new information.

When re-running on an already-generated plan:
- If the output file already exists, **do not overwrite it**. Instead, write the new version to a separate candidate file (e.g. `<feature-name>-candidate.md`) so the reviewer can compare and merge changes without losing their edits.
- Note in the report: *"A previous plan exists at `<path>`. The updated plan has been written to `<candidate-path>`. Please review and merge any human-added details from the original into the candidate."*
- Scenarios that were previously marked `[PRELIMINARY]` may now be promoted to `[GAP]`, `[PARTIAL]`, or `[COVERED]` if implementation PRs are now available.

#### 6c. What the skill does NOT do

- The skill does **not** add domain-specific details that only a human with product knowledge can provide (e.g. specific cluster configurations, internal team processes, SLA numbers not in the Jira issue).
- The skill does **not** replace human judgment — it provides a structured starting point that humans refine.
- The skill does **not** persist state between runs — each run is a fresh generation from the current Jira issue and PR state.

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

5. **From an OCPSTRAT feature (generates IEEE 829-style plan)**:
   ```text
   /openshift-developer:generate-test-plan OCPSTRAT-3266
   ```

6. **Early-stage feature with no PRs (preliminary plan)**:
   ```text
   /openshift-developer:generate-test-plan OCPSTRAT-4000
   ```

## Arguments
- `$1` — Jira issue key (e.g. `CNTRLPLANE-205`) or a GitHub PR URL (required)
- `$2, $3, ..., $N` — Additional GitHub PR URLs (optional)

## Guidelines
- **Strict sourcing**: Generate content only from what is in the Jira issue, linked PRs, or the codebase. Never fabricate scenarios, requirements, or technical details. Flag missing information with gap markers so the human reviewer knows what to fill in.
- Use Jira MCP tools for Jira data (discover tool name dynamically, do not hardcode), `gh` CLI for PR data.
- Derive test scenarios from actual code changes and measurable acceptance criteria, not assumptions or tautological criteria.
- Keep test steps concrete with exact commands and expected output.
- When Jira acceptance criteria exist, map every **testable** criterion to at least one test case. Report untestable criteria separately.
- Every scenario must have a unique ID (`TC-<CATEGORY>-<NNN>`), a CI tier, a target file path (identifies the downstream repo), an implementation status, and OCP version applicability.
- All test scenarios target downstream repos (`openshift/*`). When the feature builds on community project work, reference existing upstream coverage to justify downstream testing decisions — but do not direct new test development to upstream repos. Do not direct new tests to `openshift-tests-private` (locked for new contributions).
- Default to the cheapest CI tier that can validate each scenario.
- Include a Plan Status header (Draft) at the top of every generated plan.
- When features are version-gated, include a Feature Gates section and OCP Version Applicability Matrix.
- When scenarios are intentionally deferred, include a Deferred Scenarios appendix with effort/value estimates.
- Use real links to Jira issues and GitHub PRs — never placeholders.
- **Scrub customer names** from all generated output — replace with generic identifiers (e.g. "Customer A", "a large-scale deployment scenario"). This applies to all plan types, not just OCPSTRAT. Also check Jira summaries and PR titles used in filenames — do not embed customer names in output file paths.
- Do not generate test plans for closed-unmerged PRs, vendor-only PRs, or generated-only PRs.
- When the input is test code (no product code), use test-code-as-deliverable mode.
- When the Jira issue has unfilled template placeholders, refuse to generate and report the gaps.
