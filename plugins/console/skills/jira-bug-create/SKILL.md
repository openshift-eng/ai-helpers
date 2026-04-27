---
name: jira-bug-create
description: Create a Jira bug for OpenShift Console with all required fields from the Definition of Ready. Walks the user through providing all mandatory information before creating the issue. Use when user asks to create a Jira bug for OpenShift Console.
compatibility: "Designed for Claude Code. Uses Jira MCP by default; falls back to jira-cli if MCP is unavailable."
argument-hint: [--dry-run] [bug description] (optional - will prompt if not provided)
allowed-tools: WebFetch, AskUserQuestion, Bash, mcp__jira__jira_create_issue, mcp__jira__jira_add_comment, mcp__jira__jira_search, mcp__jira__jira_get_project_versions
license: Apache-2.0
---

# /jira-bug-create

## Context

- This skill creates OCPBUGS Jira bugs for the OpenShift Console project that comply with the team's Definition of Ready (`docs/process/definition-of-ready.md`).
- The goal is to produce bugs with sufficient detail for AI tools to pick up and implement fixes autonomously.
- Component is always "Management Console" and project is always "OCPBUGS".

## Jira Access Method

Before starting the wizard, determine which Jira access method to use:

1. **Try MCP first:** Attempt a lightweight MCP call (e.g., `mcp__jira__jira_search` with a minimal query like `project = OCPBUGS AND key = OCPBUGS-1`).
2. **If MCP succeeds:** Use MCP tools for all Jira operations throughout the wizard. This is the preferred path.
3. **If MCP fails or is unavailable:** Fall back to `jira-cli`. Verify CLI is available by running `jira --version`. If neither MCP nor CLI is available, inform the user and stop.

Set an internal flag `JIRA_MODE` to either `mcp` or `cli` and use it throughout all subsequent steps.

**Reference:** For full CLI command reference, see `plugins/jira/reference/cli-fallback.md`.

## Wizard Steps

Each step MUST show a progress header: `**Step N of 7: Title**`

Do NOT skip steps or combine steps. Complete each step fully before moving to the next.

---

### Step 1 of 7: Bug Description

1. If no bug description was provided as an argument, ask:
   > Describe the bug you'd like to report. Include enough context for someone unfamiliar with the issue to understand what's broken.
2. If the description is a one-liner or too vague for an AI agent to investigate, push back and ask the user to expand it before proceeding.
3. Search Jira for duplicates. Search across all statuses:
   - **MCP:** `mcp__jira__jira_search` with JQL `project = OCPBUGS AND component = "Management Console"` and keywords from the description.
   - **CLI:** `jira issue search 'project = OCPBUGS AND component = "Management Console" AND summary ~ "keyword"'`
4. If potential duplicates are found, present them (key, summary, status) and use `AskUserQuestion`:
   - "A potential duplicate was found. How would you like to proceed?" — Continue creating new bug / Abandon (it's a duplicate)

---

### Step 2 of 7: Reproduction Details

Prompt the user for all three fields in a single message:

> Please provide the following reproduction details:
>
> 1. **Steps to Reproduce** — numbered list of exact steps to trigger the bug
> 2. **Actual results** — what happens when following those steps
> 3. **Expected results** — what should happen instead

If the steps are vague (e.g., "it doesn't work", no numbered steps, missing navigation paths), push back with specific feedback on what's missing before accepting.

---

### Step 3 of 7: Environment & Configuration

Use a single `AskUserQuestion` call with 4 questions:

| # | Question | Options | multiSelect |
|---|----------|---------|-------------|
| 1 | "What cluster type is this bug on?" | OCP, ROSA, ARO, Hypershift | false |
| 2 | "Which feature gate is enabled?" | None, TechPreviewNoUpgrade, DevPreviewNoUpgrade, CustomNoUpgrade | false |
| 3 | "How reproducible is this bug?" | Always, Sometimes, Rarely, Unknown | false |
| 4 | "Which browser was used?" | Chrome, Firefox, Safari, Edge | false |

After the `AskUserQuestion` response, prompt for the cluster version:

> What cluster version are you running? (e.g., 4.18.0, 4.19.0-rc.1)

---

### Step 4 of 7: Severity & Priority

Use a single `AskUserQuestion` call with 2 questions:

| # | Question | Options | multiSelect |
|---|----------|---------|-------------|
| 1 | "What is the severity of this bug?" | Low, Moderate, Important, Critical | false |
| 2 | "What priority should this bug have?" | Normal, Major, Critical, Blocker | false |

If the user types "Skip" or similar for priority, omit the field.

Note: If severity is "Urgent", the user will select it via the automatic "Other" option.

---

### Step 5 of 7: Versions

1. Fetch versions for project OCPBUGS. Filter out archived versions, sort latest first.
   - **MCP:** Call `mcp__jira__jira_get_project_versions` for project OCPBUGS.
   - **CLI:** Run `jira issue search 'project = OCPBUGS' | head -1` to get an issue key, then `jira issue get <key>` to inspect available version fields. If version fetching is unreliable via CLI, present the user with a free-text prompt to type the version strings manually.
2. From the fetched versions, pick the 4 most relevant (latest non-archived) for each question.
3. Use `AskUserQuestion` with 3 questions:

| # | Question | Options (top 4 from fetched) | multiSelect |
|---|----------|------------------------------|-------------|
| 1 | "Which version does this bug affect?" | {top 4 versions} | false |
| 2 | "Which version should contain the fix?" | {top 4 versions} | false |
| 3 | "What is the target version?" | {top 4 versions} | false |

4. Then ask with a second `AskUserQuestion` call (1 question):

| # | Question | Options | multiSelect |
|---|----------|---------|-------------|
| 1 | "Do you need to target backport versions? (z-stream only)" | No backports needed, {top 3 z-stream versions from fetched} | false |

---

### Step 6 of 7: Artifacts

At least one artifact is required by the Definition of Ready.

1. Use `AskUserQuestion` with 1 question:

| # | Question | Options | multiSelect |
|---|----------|---------|-------------|
| 1 | "Which artifacts can you provide? (at least one required)" | Screenshot/recording, Must-gather, HAR file, Console stack trace | true |

2. For each selected artifact type, prompt for a link (one at a time):
   > Please provide a link for: {artifact_type} (Jira attachment URL, Google Drive link, or paste inline)

---

### Step 7 of 7: Review & Create

1. Assemble the Jira description using the template below.
2. Present the complete bug report showing all fields:
   - Summary (auto-generated from description — short, prefix-free)
   - Full formatted description
   - Severity, Priority (if set)
   - Affects versions, Fix Versions, Target Version
   - Target Backport Versions (if set)
   - Component: Management Console
3. Ask the user to confirm or request changes.
4. If changes are requested, update the relevant fields and present again.
5. On confirmation:
   - If `--dry-run` was passed: display the report labeled `[DRY RUN]` and stop.
   - Otherwise, create the issue with project OCPBUGS, issue type Bug, component Management Console, and all collected fields:
     - **MCP:** Use `mcp__jira__jira_create_issue`.
     - **CLI:** Use `jira create -p OCPBUGS -t Bug -s '<summary>' -d '<description>' -c 'Management Console'` with additional flags for severity (`--priority`), affects version, and fix version. Use single-quoted heredoc for the description to preserve formatting (see `plugins/jira/reference/cli-fallback.md` for quoting rules).
   - Report the created issue key and URL.

## Description Template

```
*Description of problem:*
{description}

*Version-Release number of selected component:*
Cluster type: {cluster_type}
Cluster version: {cluster_version}
Feature gates: {feature_gates}

*How reproducible:*
{reproducibility}

*Steps to Reproduce:*
1. {step1}
2. {step2}
...

*Actual results:*
{actual}

*Expected results:*
{expected}

*Additional info:*
Browser: {browser}
Artifacts:
- {artifact_type}: {link}
```

## Important Notes

### Safety
- NEVER modify or delete existing Jira issues.
- NEVER create an issue without explicit user confirmation in Step 7.
- Always check for duplicates before creating (Step 1).

### Quality
- Push back on vague reproduction steps — they must be specific enough for someone unfamiliar with the issue to reproduce it.
- Push back on one-liner descriptions — help the user expand into the full template.
- The description must have enough detail for an AI agent to investigate and fix the bug autonomously.
