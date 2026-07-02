---
name: generate-test-plan
description: Shared implementation for JIRA test plans and bug reproducer reports from issue details and fix PRs, with optional live cluster execution
---

# Generate Test Plan

This skill analyzes a JIRA issue and related fix PRs to produce either a **manual test plan** or a **bug reproducer report**. It is invoked by:

- `/jira:generate-test-plan` — test plan mode (default)
- `/jira:generate-test-plan --reproducer` — reproducer mode
- `/jira:generate-bug-reproducer` — reproducer mode (alias)
- `--apply` flag on any of the above — executes generated steps against a live OpenShift cluster

## When to Use This Skill

Use **test plan mode** when QE or a developer needs step-by-step guidance to validate a fix after it is applied, including regression coverage.

Use **reproducer mode** when the JIRA bug lacks complete reproduction steps and you need to infer how to trigger the bug from the fix PR diff and JIRA narrative, then verify the fix resolves it.

## Prerequisites

- JIRA credentials (`JIRA_USERNAME`, `JIRA_API_TOKEN`) or Jira MCP server configured
- `gh` CLI authenticated for GitHub PR access
- `jq` available for JSON parsing

## Input Format

| Parameter | Required | Description |
|-----------|----------|-------------|
| JIRA issue key | Yes | e.g. `OCPBUGS-12345`, `CNTRLPLANE-205` |
| PR URLs | No | One or more GitHub PR URLs; auto-discovered from JIRA if omitted |
| Mode | No | `test-plan` (default) or `reproducer` |
| Apply | No | `true` when `--apply` is present; executes steps on a live cluster after report generation |

## Implementation Steps

### Step 1: Parse Arguments

1. Extract the JIRA issue key from `$1`
2. Collect optional PR URLs from remaining arguments
3. Detect `--reproducer` flag in any argument position
4. Set mode:
   - `reproducer` if `--reproducer` is present or the mode is explicitly set to `reproducer` by the invoking command
   - `test-plan` otherwise
5. Detect `--apply` flag in any argument position
6. Set apply mode:
   - `true` if `--apply` is present
   - `false` otherwise
7. If apply mode is `true` and a report already exists at the expected path (see Step 8.1), ask the user whether to reuse or regenerate. If the user chooses to reuse, skip Steps 2-7 and proceed directly to Step 8
8. For reproducer mode on non-bug issue types, warn the user and continue with best effort

### Step 2: Fetch JIRA Issue

Fetch issue data via Jira MCP `getJiraIssue` or REST API:

```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/issue/{ISSUE_KEY}"
```

For issues.redhat.com projects, also try:

```bash
curl -s -H "Authorization: Bearer $JIRA_PERSONAL_TOKEN" \
  "https://issues.redhat.com/rest/api/2/issue/{ISSUE_KEY}"
```

Extract:

- Summary, description (convert ADF to plain text if needed)
- Issue type, status, components, labels
- Steps to reproduce, expected vs actual behavior (for bugs)
- Acceptance criteria (for stories/features)
- Linked development items and comments containing PR URLs

### Step 3: Discover Pull Requests

**If PR URLs were provided:** use only those.

**If no PR URLs provided:**

1. Scan JIRA description, remote links, and comments for `github.com/*/pull/*` URLs
2. Use WebFetch on `https://issues.redhat.com/browse/{ISSUE_KEY}` or the Atlassian browse URL
3. Check Development panel and issue links for PR references

If no PRs are found in reproducer mode, warn that root-cause inference will rely on JIRA text only and confidence will be lower.

### Step 4: Analyze Pull Requests

For each PR:

```bash
gh pr view {URL_OR_NUMBER} --json title,body,commits,files,labels,state,baseRefName,headRefName
```

```bash
gh pr diff {URL_OR_NUMBER}
```

Analyze:

- What behavior changed and why (infer the bug from the fix)
- Affected components (API, CLI, operator, controller, etc.)
- Platform or configuration preconditions
- Related test files in the diff
- Dependencies between multiple PRs — for multi-PR issues, identify how PRs interact and create integrated test scenarios that verify combined behavior produces expected results

**Skip PRs that don't need analysis** (note them in the report):

- Documentation-only changes (`.md` files only)
- CI/tooling-only changes (`.github/`, `.claude/`)
- PRs labeled `skip-testing` or `docs-only`

Use Grep and Glob in the target repository to find related tests, configs, and usage examples.

### Step 5: Cross-Reference JIRA and PR Analysis

| Source | Test plan mode | Reproducer mode |
|--------|----------------|-----------------|
| JIRA steps to reproduce | Use as test cases when present | Use as primary source when complete |
| JIRA expected/actual | Map to verification criteria | Define broken vs correct behavior |
| PR diff | Inform test scenarios and regression scope | **Infer** missing reproduction steps and root cause |
| PR description | Supplement test coverage | Extract author-stated trigger conditions |

In reproducer mode, explicitly reconcile:

- What JIRA says vs what the code change implies
- Gaps where inference was required
- Confidence level (high / medium / low) based on available evidence

### Step 6: Generate Report

Create the output directory:

```bash
mkdir -p .work/jira/generate-test-plan/{ISSUE_KEY}
```

#### Test Plan Mode

**Filename:** `.work/jira/generate-test-plan/{ISSUE_KEY}/test-plan.md`

**Sections:**

1. **JIRA Summary** — key, title, type, description, acceptance criteria
2. **PR Summary** — linked PRs and how they relate to the JIRA
3. **Prerequisites** — infrastructure, tools, access (no build/deploy steps)
4. **Test Scenarios** — numbered cases covering these categories where applicable:
   - Happy path scenarios (based on acceptance criteria)
   - Negative test cases (invalid inputs, boundary conditions)
   - Edge cases specific to the implementation
   - Integration scenarios (how changes interact with existing system; for multi-PR issues, verify PRs produce expected results when combined)
   - Error handling verification
   - Performance considerations if applicable
   - Platform-specific test variations (AWS, Azure, KubeVirt, etc.) if the PR contains platform-specific changes
   - Each case includes: steps, expected results, verification commands
5. **Regression Testing** — related features and affected areas
6. **Success Criteria** — checklist mapped to acceptance criteria
7. **Troubleshooting** — common issues and debug steps
8. **Notes** — limitations, links, critical cases, skipped PRs

Do **not** include build/deploy or cleanup sections.

#### Reproducer Mode

**Filename:** `.work/jira/generate-test-plan/{ISSUE_KEY}/reproducer-report.md`

**Sections:**

1. **Bug Summary** — JIRA key, title, components, concise problem statement
2. **Root Cause Analysis** — inferred from PR diff and JIRA narrative
3. **Prerequisites / Environment** — cluster version, platform, config, tools required
4. **Steps to Reproduce (Pre-Fix)** — numbered steps that trigger the bug on an unfixed build
5. **Observed vs Expected Behavior** — broken state the reproducer should demonstrate
6. **Fix Verification Steps (Post-Fix)** — same reproducer with fix applied; expected corrected behavior
7. **Automation Opportunities** — whether this could become an e2e or integration test (no code generation)
8. **Confidence & Assumptions** — high/medium/low with explicit assumptions made during inference
9. **Open Questions** — items for PR author or bug reporter to confirm
10. **PR Summary** — fix PRs analyzed and skipped PRs with reasoning

### Step 7: Present Results

Display to the user:

- Report file path
- Mode used (`test-plan` or `reproducer`)
- JIRA issue and PRs analyzed
- Number of test scenarios or reproducer steps generated
- Confidence level (reproducer mode)
- Skipped PRs and why
- Ask if the user wants modifications
- If `--apply` was requested, inform the user that the apply phase will begin next and proceed to Step 8

### Step 8: Apply to Cluster (when `--apply` is set)

This step executes the generated reproducer or test plan steps against a live OpenShift cluster. It is only run when the `--apply` flag is present.

#### 8.1: Verify Report Exists

At this point a report must already exist — either generated in Steps 2-7 or reused via the decision in Step 1.7. Verify the expected file is present:

- **Reproducer mode**: `.work/jira/generate-test-plan/{ISSUE_KEY}/reproducer-report.md`
- **Test plan mode**: `.work/jira/generate-test-plan/{ISSUE_KEY}/test-plan.md`

If the file is missing (e.g., generation was skipped by mistake), abort the apply phase with a clear error.

#### 8.2: Prerequisite Checks

Verify the environment is ready for cluster interaction:

1. **Check `oc` CLI is installed:**
   ```bash
   which oc
   ```
   If not found, display installation instructions and abort the apply phase:
   ```text
   Error: 'oc' CLI is not installed.
   Install from: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html
   ```

2. **Verify cluster connectivity:**
   ```bash
   oc whoami
   ```
   If this fails, display login instructions and abort the apply phase:
   ```text
   Error: Not logged in to an OpenShift cluster.
   Please log in first:
     1. Visit the cluster console in your browser
     2. Click on your username → 'Copy login command'
     3. Paste and execute the 'oc login' command in your terminal
   ```

3. **Display cluster context and ask for confirmation:**
   ```bash
   oc whoami --show-server
   oc version
   ```
   ```text
   You are logged in to:
     Server: {server-url}
     User:   {username}
     Version: {oc-version}

   Proceed with applying the reproducer steps on this cluster? (yes/no)
   ```
   If the user says no, abort the apply phase.

#### 8.3: Parse Steps from Report

Read the generated report and extract executable steps:

- **Reproducer mode**: parse the "Steps to Reproduce (Pre-Fix)" section
- **Test plan mode**: parse the "Test Scenarios" section

For each step, extract:
- Step number and description (human-readable text)
- Executable commands (content within ``` code blocks)
- Expected output or behavior (from the step's expected results or the "Observed vs Expected Behavior" section)

Steps that describe actions in prose without executable commands in code blocks should be flagged as "manual — no executable command found" and presented to the user for manual action.

Handle multi-line commands (heredocs, inline YAML with `oc apply -f -`) as single logical commands.

#### 8.4: Classify Commands

Classify each extracted command as **read-only** or **write**:

**Read-only commands** (safe, bulk-confirmable):
- `oc get`, `oc describe`, `oc logs`, `oc whoami`, `oc version`, `oc status`
- `oc explain`, `oc api-resources`, `oc api-versions`
- `oc config view`, `oc config get-contexts`
- `oc adm top`
- `oc auth can-i`
- `kubectl get`, `kubectl describe`, `kubectl logs`
- Non-cluster shell commands: `cat`, `echo`, `grep`, `jq`, `yq`, `curl` (GET only)

**Write commands** (individual confirmation required):
- `oc apply`, `oc create`, `oc delete`, `oc patch`, `oc replace`
- `oc label`, `oc annotate`, `oc scale`, `oc rollout`
- `oc set`, `oc expose`, `oc run`
- `oc exec`, `oc cp`, `oc edit`, `oc debug`
- `oc adm` (subcommands other than `top`)
- `kubectl apply`, `kubectl create`, `kubectl delete`, `kubectl patch`
- Any command piped to a write command (e.g., `... | oc apply -f -`)
- Any unrecognized `oc` subcommand (default to write for safety)

#### 8.5: Present Execution Plan

Display the classified execution plan:

```text
=== Execution Plan for {ISSUE_KEY} ===
Mode: {reproducer|test-plan}

Read-only commands (will ask for one-time approval):
  Step 1: oc get namespace test-namespace
  Step 3: oc get pods -n test-namespace

Write commands (will ask for individual approval before each):
  Step 2: oc create namespace test-namespace
  Step 4: oc apply -f - <<EOF ... EOF

Manual steps (no executable command):
  Step 5: Navigate to the web console and verify...

Total: {N} steps ({R} read-only, {W} write, {M} manual)

Proceed? (yes/no)
```

If the user says no, abort the apply phase.

#### 8.6: Execute Steps

**One-time read-only approval:**

```text
The following {R} read-only commands will be executed without individual prompts:
  - oc get namespace test-namespace
  - oc get pods -n test-namespace

Approve all read-only commands? (yes/no)
```

If the user says no, fall back to individual confirmation for every command.

**Execute steps in order:**

For each step:

1. Display the step number and description
2. For read-only commands (if bulk-approved): execute immediately
3. For write commands: ask for individual confirmation:
   ```text
   About to execute (WRITE):
     oc apply -f - <<EOF
     apiVersion: v1
     kind: Namespace
     ...
     EOF

   Execute this command? (yes/skip/abort)
   ```
   - **yes**: execute the command
   - **skip**: skip this step, continue to the next
   - **abort**: stop all execution immediately
4. For manual steps: display the instruction and wait for the user to confirm they have completed it before continuing
5. After executing each command, capture and display the output
6. If the step has expected output, compare:
   ```text
   Expected: {expected behavior from report}
   Observed: {actual command output}
   Match: yes/no/partial
   ```

#### 8.7: Report Results

After all steps execute (or the user aborts), display a summary:

```text
=== Apply Results for {ISSUE_KEY} ===

Step 1: oc get namespace test-namespace ........... EXECUTED (output matched expected)
Step 2: oc create namespace test-namespace ........ EXECUTED (success)
Step 3: oc get pods -n test-namespace ............. EXECUTED (output diverged)
Step 4: oc apply -f deployment.yaml ............... SKIPPED (user skipped)
Step 5: Manual verification ....................... COMPLETED
Step 6: oc delete namespace test-namespace ........ NOT REACHED (execution aborted)

Bug Reproduction Assessment:
- [Reproducer mode]: Based on the outputs, the bug [was reproduced / was NOT reproduced / could not be determined].
- [Test plan mode]: {N} of {M} test scenarios executed. {P} passed, {F} diverged from expected results.

Resources Created:
- namespace/test-namespace (Step 2) — not cleaned up

Recommendation:
- {Contextual next steps based on results}
```

Save the execution log to `.work/jira/generate-test-plan/{ISSUE_KEY}/apply-log-{timestamp}.md` and display the path.

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | Report error; verify issue key and JIRA access |
| No PRs found | Continue with JIRA-only analysis; lower confidence in reproducer mode |
| `gh` not authenticated | Provide `gh auth login` instructions |
| Non-bug issue in reproducer mode | Warn; proceed with best-effort reproduction steps |
| PR diff too large | Focus on files most relevant to the JIRA component/summary |
| `oc` CLI not installed | Display installation instructions; abort apply phase |
| Cluster not reachable | Display login instructions; abort apply phase |
| User declines cluster confirmation | Abort apply phase; the report is still available |
| Write command fails | Display error output; ask user whether to continue or abort |
| Read-only command fails | Display error; continue to next step (non-fatal) |
| Step output diverges from expected | Flag as divergence in results summary; do not abort |
| Report not parseable for apply | Warn that no executable commands were found; abort apply phase |

## Examples

**Test plan with auto-discovered PRs:**

```bash
/jira:generate-test-plan CNTRLPLANE-205
```

**Test plan with specific PRs:**

```bash
/jira:generate-test-plan OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
```

**Test plan command with reproducer mode:**

```bash
/jira:generate-test-plan OCPBUGS-12345 --reproducer
```

**Reproducer alias:**

```bash
/jira:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
```

**Reproducer with live cluster execution:**

```bash
/jira:generate-bug-reproducer OCPBUGS-12345 --apply
```

**Test plan with live cluster execution:**

```bash
/jira:generate-test-plan CNTRLPLANE-205 --apply
```

**Reproducer with apply, reusing existing report:**

```bash
/jira:generate-bug-reproducer OCPBUGS-12345 --apply
# → Agent detects existing report and offers to apply it directly
```
