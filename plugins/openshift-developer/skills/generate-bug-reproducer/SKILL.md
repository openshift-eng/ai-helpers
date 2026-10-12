---
name: generate-bug-reproducer
description: Generate bug reproduction steps and fix-verification steps from a Jira bug and its fix PRs, optionally executing them against a live cluster. Use when a Jira bug lacks complete reproduction steps and they must be inferred from the fix PR diff.
---

## Name
openshift-developer:generate-bug-reproducer

## Synopsis
```text
/openshift-developer:generate-bug-reproducer <JIRA_KEY> [PR URLs...] [--apply]
```

## Description
Produces a reproducer report for a Jira bug: how to trigger the bug on an unfixed build, what the broken behavior looks like, and how to verify the fix resolves it.

Reproduction steps already written in the Jira description are the primary source. The fix PR diff is used to infer the steps Jira is missing, to establish the root cause, and to reconcile what the bug report claims against what the code change implies. Every inference is recorded with an explicit confidence level so a reviewer can tell which steps are evidence-based and which are inferred.

This is distinct from `openshift-developer:generate-test-plan`, which produces broad QE coverage (happy path, regression, platform variations) for a change. A reproducer targets one specific defect and its verification. The two share source gathering, and this skill reuses that part rather than restating it.

With `--apply`, the generated steps are executed against a live OpenShift cluster: read-only commands are bulk-approved once, write commands are confirmed individually, and the observed output is compared against the report's expected behavior.

## Prerequisites
- Atlassian MCP server configured (`mcp__atlassian__jira_get_issue`)
- `gh` CLI authenticated for GitHub PR access
- `oc` CLI with an active login to the target cluster — only when `--apply` is used

## Implementation

### Step 1: Parse arguments

1. Extract the Jira issue key from `$1`. If `$1` is not an issue key, reject with a usage error — this skill requires a bug to reproduce.
2. Parse each remaining argument exactly once, in order:
   - `--apply`: mark apply mode requested
   - a valid GitHub PR URL (`https://github.com/*/pull/*`): append to the PR list
   - anything else: reject with a usage error — never forward an unrecognized flag to `gh pr view`/`gh pr diff` as if it were a PR URL
3. If the issue type is not a bug, warn the user and continue with best effort.
4. If apply mode is set and a report already exists at `.work/generate-bug-reproducer/{ISSUE_KEY}/reproducer-report.md`, read its embedded provenance metadata (see Step 4) and compare it against this invocation:
   - If the issue key and PR list both match, ask the user whether to reuse or regenerate
   - If anything differs, or the metadata is missing or unparseable, state the mismatch and default to regenerating unless the user confirms they want the stale report
   - If the user chooses to reuse, skip Steps 2-5 and go directly to Step 6

### Step 2: Gather sources

Follow **Step 1 (Parse input and gather sources)** and **Step 2 (Analyze changes)** of [`openshift-developer:generate-test-plan`](../generate-test-plan/SKILL.md) to fetch the Jira issue, discover linked PRs, and analyze the diffs. Apply the same PR filtering it describes (documentation-only, CI/tooling-only, `skip-testing` / `docs-only` labels) and note skipped PRs.

Beyond what that skill extracts, capture for reproducer purposes:

- Steps to reproduce, and expected vs actual behavior, as written in the Jira description
- Environment facts stated in the bug: cluster version, platform, install config, feature gates
- Trigger conditions the PR author states in the PR description or commit messages
- The specific code path the diff changes, and what input reaches it

If no PRs are found, warn that root-cause inference will rely on Jira text alone and cap the confidence at low.

### Step 3: Establish root cause and reconcile sources

Determine, from the diff, what the code did before the fix and what it does after. The reproducer is the input that reaches the changed code path and produces the pre-fix behavior.

Reconcile explicitly:

| Source | Use |
|--------|-----|
| Jira steps to reproduce | Primary source when present and complete |
| Jira expected vs actual | Defines the broken state the reproducer must demonstrate |
| PR diff | Infers missing steps and the root cause; identifies preconditions |
| PR description and commits | Author-stated trigger conditions |

Record where Jira and the code disagree, which steps required inference, and the resulting confidence (high / medium / low).

### Step 4: Generate the reproducer report

Write to `.work/generate-bug-reproducer/{ISSUE_KEY}/reproducer-report.md`.

Embed provenance metadata as an HTML comment above the first heading so a later `--apply` run can verify the report still matches its inputs:

```html
<!-- generate-bug-reproducer-metadata
issue: {ISSUE_KEY}
pr_urls: {comma-separated PR URLs actually analyzed, or "none"}
generated_at: {ISO 8601 timestamp}
-->
```

Sections:

1. **Bug Summary** — Jira key, title, components, concise problem statement
2. **Root Cause Analysis** — what the code did wrong, derived from the diff
3. **Prerequisites / Environment** — cluster version, platform, configuration, tools
4. **Steps to Reproduce (Pre-Fix)** — numbered steps that trigger the bug on an unfixed build, each with concrete commands in code blocks
5. **Observed vs Expected Behavior** — the broken state the reproducer demonstrates
6. **Fix Verification Steps (Post-Fix)** — in most cases identical to the reproduction steps with a corrected expected result; restate them in full rather than cross-referencing, and call out any step that only becomes reachable once the fix is applied
7. **Automation Opportunities** — whether this belongs in an e2e or integration suite (describe only; do not generate test code)
8. **Confidence & Assumptions** — high / medium / low, with each assumption listed
9. **Open Questions** — what the PR author or bug reporter still needs to confirm
10. **PR Summary** — PRs analyzed, and skipped PRs with reasoning

Keep every step concrete: exact commands, exact expected output. Do not include build or deploy steps.

### Step 5: Present results

Show the report path, the Jira issue and PRs analyzed, the number of reproduction steps, the confidence level, and any skipped PRs. Ask whether the user wants modifications. If `--apply` was requested, say the apply phase begins next and continue to Step 6.

### Step 6: Apply to cluster (when `--apply` is set)

#### 6.1: Verify the report

A report must already exist, either generated above or reused via Step 1.4. If the file is missing, abort the apply phase. If its provenance metadata is missing, unparseable, or does not match the current issue key and PR list, treat it as unverified: warn, and require explicit confirmation to apply it or regenerate instead.

#### 6.2: Prerequisite checks

1. **`oc` CLI installed:**
   ```bash
   which oc
   ```
   If not found, abort the apply phase with installation instructions:
   ```text
   Error: 'oc' CLI is not installed.
   Install from: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html
   ```

2. **Cluster reachable:**
   ```bash
   oc whoami
   ```
   If this fails, abort with login instructions:
   ```text
   Error: Not logged in to an OpenShift cluster.
   Please log in first:
     1. Visit the cluster console in your browser
     2. Click on your username → 'Copy login command'
     3. Paste and execute the 'oc login' command in your terminal
   ```

3. **Confirm the target cluster:**
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

#### 6.3: Parse steps from the report

Extract the "Steps to Reproduce (Pre-Fix)" section. For each step capture the number and description, the commands inside code blocks, and the expected output from the step or from "Observed vs Expected Behavior".

Steps written in prose with no executable command are flagged "manual — no executable command found" and handed to the user to perform. Treat heredocs and inline YAML piped to `oc apply -f -` as one logical command.

#### 6.4: Classify commands

**Read-only** (eligible for bulk approval):
- `oc get`, `oc describe`, `oc logs`, `oc whoami`, `oc version`, `oc status`
- `oc explain`, `oc api-resources`, `oc api-versions`
- `oc config view`, `oc config get-contexts`
- `oc adm top`
- `oc auth can-i`
- `kubectl get`, `kubectl describe`, `kubectl logs`
- Non-cluster shell commands: `cat`, `echo`, `grep`, `jq`, `yq`
- `curl` **only** as a single plain GET: no `-X`/`--request` other than `GET`, no `-d`/`--data*`/`-F`/`-T`/`--upload-file`, no `-o`/`--output` to a sensitive path, and the target must be an endpoint already referenced in the report — never an arbitrary, internal, or metadata URL

**Write** (individual confirmation required):
- `oc apply`, `oc create`, `oc delete`, `oc patch`, `oc replace`
- `oc label`, `oc annotate`, `oc scale`, `oc rollout`
- `oc set`, `oc expose`, `oc run`
- `oc exec`, `oc cp`, `oc edit`, `oc debug`
- `oc adm` (any subcommand other than `top`)
- `kubectl apply`, `kubectl create`, `kubectl delete`, `kubectl patch`
- Any compound or chained command (`&&`, `||`, `;`, `|`, command substitution `$(...)` or backticks, redirection `>`/`>>`) — chaining can hide destructive or exfiltrating behavior behind read-only-looking parts, so classify as write even when every visible component looks safe
- `curl` with any method or flag not allowed above, or targeting an internal or unreferenced endpoint
- Any unrecognized `oc` subcommand, or anything that does not cleanly match a single pattern above — default to write; never bulk-approve an ambiguous command

#### 6.5: Present the execution plan

```text
=== Execution Plan for {ISSUE_KEY} ===

Read-only commands (one-time approval):
  Step 1: oc get namespace test-namespace
  Step 3: oc get pods -n test-namespace

Write commands (individual approval before each):
  Step 2: oc create namespace test-namespace
  Step 4: oc apply -f - <<EOF ... EOF

Manual steps (no executable command):
  Step 5: Navigate to the web console and verify...

Total: {N} steps ({R} read-only, {W} write, {M} manual)

Proceed? (yes/no)
```

If the user says no, abort the apply phase.

#### 6.6: Execute

**One-time read-only approval:**

```text
The following {R} read-only commands will be executed without individual prompts:
  - oc get namespace test-namespace
  - oc get pods -n test-namespace

Approve all read-only commands? (yes/no)
```

If the user says no, fall back to individual confirmation for every command.

**Redact before displaying or persisting any output:**
- Redact values from `oc get secret`, `oc get -o yaml` on Secret or ConfigMap resources, `oc config view` (unless credentials are already elided), and any `Authorization`, `token`, `password`, or `Bearer` field in JSON/YAML/HTTP output
- Replace them with `[REDACTED]` both on screen and in the apply log — never write raw secret material under `.work/`
- For commands known to return sensitive data, ask for explicit confirmation before displaying or persisting the output even when classified read-only

**For each step, in order:**

1. Display the step number and description
2. Read-only commands execute immediately when bulk-approved
3. Write commands ask for individual confirmation:
   ```text
   About to execute (WRITE):
     oc apply -f - <<EOF
     apiVersion: v1
     kind: Namespace
     ...
     EOF

   Execute this command? (yes/skip/abort)
   ```
   **yes** executes, **skip** moves to the next step, **abort** stops everything immediately
4. Manual steps display the instruction and wait for the user to confirm completion
5. Before running anything, ensure it terminates on its own. Convert streaming or interactive commands (`oc logs -f`, `oc exec` without a fixed command, `oc rsh`, interactive `oc debug`) to a bounded form such as `--tail=200` or `--since=`, or ask the user to confirm an explicit timeout
6. Enforce a per-command timeout — 30s read-only, 60s write, longer only with explicit confirmation. On timeout, terminate the process group, mark the step `TIMED OUT`, and continue; one hung command must never block the rest of the plan
7. Capture and display output with redaction applied, capped to a bounded size (first and last 200 lines, or 20KB, noting truncation)
8. Where the step has an expected result, compare:
   ```text
   Expected: {expected behavior from report}
   Observed: {actual command output}
   Match: yes/no/partial
   ```

#### 6.7: Report results

```text
=== Apply Results for {ISSUE_KEY} ===

Step 1: oc get namespace test-namespace ........... EXECUTED (output matched expected)
Step 2: oc create namespace test-namespace ........ EXECUTED (success)
Step 3: oc get pods -n test-namespace ............. EXECUTED (output diverged)
Step 4: oc apply -f deployment.yaml ............... SKIPPED (user skipped)
Step 5: Manual verification ....................... COMPLETED
Step 6: oc delete namespace test-namespace ........ NOT REACHED (execution aborted)

Reproduction Assessment:
- The bug [was reproduced / was NOT reproduced / could not be determined].

Resources Created:
- namespace/test-namespace (Step 2) — not cleaned up

Recommendation:
- {Contextual next steps based on results}
```

Save the log to `.work/generate-bug-reproducer/{ISSUE_KEY}/apply-log-{timestamp}.md` with redaction applied, and show the path.

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | Report error; verify the issue key and Jira access |
| `$1` is not a Jira issue key | Usage error; this skill requires a bug to reproduce |
| No PRs found | Continue with Jira-only analysis; cap confidence at low |
| `gh` not authenticated | Provide `gh auth login` instructions |
| Non-bug issue type | Warn; proceed with best effort |
| PR diff too large | Focus on files matching the Jira component and summary |
| `oc` CLI not installed | Installation instructions; abort the apply phase |
| Cluster not reachable | Login instructions; abort the apply phase |
| User declines cluster confirmation | Abort the apply phase; the report remains available |
| Write command fails | Display the error; ask whether to continue or abort |
| Read-only command fails | Display the error; continue to the next step |
| Command exceeds its timeout | Terminate the process group; mark `TIMED OUT`; continue |
| Reused report metadata missing or mismatched | Warn; require explicit confirmation or regenerate |
| Step output diverges from expected | Flag as divergence in the summary; do not abort |
| No executable commands in the report | Warn that nothing can be applied; abort the apply phase |

## Examples

1. **Auto-discover the fix PRs from Jira**:
   ```text
   /openshift-developer:generate-bug-reproducer OCPBUGS-12345
   ```

2. **Restrict analysis to one fix PR** (typical for bug verification, which is usually done one PR at a time):
   ```text
   /openshift-developer:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
   ```

3. **Generate and execute against a live cluster**:
   ```text
   /openshift-developer:generate-bug-reproducer OCPBUGS-12345 --apply
   ```

4. **Apply a specific PR's reproducer to a cluster**:
   ```text
   /openshift-developer:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888 --apply
   ```

## Arguments
- `$1` — Jira bug key, e.g. `OCPBUGS-12345` (required)
- `$2, $3, ..., $N` — GitHub PR URLs to analyze (optional; auto-discovered from Jira when omitted)
- `--apply` — Execute the generated steps against the connected cluster after generating or reusing the report

## Guidelines
- Use the Atlassian MCP tools for Jira data and `gh` for PR data
- Treat Jira's own reproduction steps as authoritative; infer only what is missing
- State confidence explicitly and list every assumption — a reproducer a reviewer cannot audit is not useful
- Keep steps concrete: exact commands, exact expected output
- Under `--apply`, never bulk-approve anything ambiguous, and never persist unredacted output

## See Also
- `openshift-developer:generate-test-plan` — broad QE test coverage for a change, rather than one defect
