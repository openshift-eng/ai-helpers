---
description: Interactive onboarding that guides new Node team members through access, tools, and environment setup
argument-hint: "[--track dev|qe] [--resume] [--check-only]"
---

## Name

node-onboarding:checklist

## Synopsis

```
/node-onboarding:checklist [--track dev|qe] [--resume] [--check-only]
```

## Description

Walks a new Node team member through the full onboarding process: access
requests, tool installation, environment setup, and first cluster creation.
The command runs automated checks to verify each step that can be tested
programmatically. For manual steps, it provides instructions and links,
then asks the user to confirm completion.

Progress is saved between sessions so the checklist can be resumed later.
`/node-team:cleanup` leaves the progress file alone unless the user confirms
its removal.

## Implementation

### Phase 0: Setup and Argument Parsing

1. Parse arguments:
   - `--track dev|qe`: onboarding track (default: `dev`). The `qe` track
     adds QE-specific items after the common sections.
   - `--resume`: load prior progress from
     `~/.node-assistant/onboarding-progress.json` and skip completed sections.
   - `--check-only`: run only automated verification checks without
     interactive prompts. Print pass/fail for each checkable item. This mode
     does not write the progress file. It takes precedence over `--resume`:
     with both flags the progress file is neither read, created nor modified,
     and every checkable item is verified again.
2. Handle existing progress in `~/.node-assistant/onboarding-progress.json`:
   - With `--resume`: read the file and skip completed sections. If the file
     does not exist, start fresh.
   - Without `--resume`, if the file exists: do not overwrite it silently.
     Show its track, start date and completion state, then ask whether to
     resume it or start over. Only start over after the user confirms. In
     `--check-only` mode skip this question, since nothing is written.
3. Read the checklist from
   [references/onboarding-checklist.md](../references/onboarding-checklist.md).
   It is the single source for sections, items, item keys, check commands,
   manual actions and links. Do not rely on item lists from memory.
4. Locating shared data: the checklist links to `node-team` files
   (`jira.md`, `SETUP.md`, `shared/team-info.md`, `shared/version-map.md`).
   Those links are relative to a repo checkout. When the plugin is installed,
   read them from
   `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/` (glob
   the version directory), or invoke the `node-team:node` skill and read from
   its base directory.

### Phase 1: Interactive Checklist

Walk through the sections of the reference file in order. Skip sections whose
`Track:` line does not match the selected track (`both` always applies). For
each item:
- If a check command is defined, run it and report the result.
- If the check passes, mark the item complete automatically.
- If the check fails or no check exists, show the manual action or URL from
  the reference and ask the user to confirm when done (skip this prompt in
  `--check-only` mode and report the item as not verified).
- Save progress to `~/.node-assistant/onboarding-progress.json` after each
  section completes, using the item keys from the reference. In
  `--check-only` mode never create or modify the progress file.

Notes for running the checks:
- Shell state does not persist between Bash tool calls. For the Jira checks,
  run the `jira_status` helper definition from the reference and the check in
  the same invocation. Never print the token or put it on a command line.
- Ask for the user's GitHub handle before the GitHub section and substitute
  it in the org membership check.
- The VPN, ServiceNow and SupportShell checks need the Red Hat VPN. If the
  VPN check fails, say so once instead of reporting each dependent failure as
  a separate problem.
- In the Development Environment section, suggest `/node-team:setup` after
  the tool checks pass.
- In the Cluster Creation section, present ClusterBot first and resolve
  "latest GA version" from node-team `shared/version-map.md`.
- In the Customer Support Readiness section, explain the workflow after the
  checks: `yank -y <case_id>` on SupportShell to download, `omc use <file>`
  to load, then `omc get nodes`, `omc get mc`.

### Phase 2: Progress Summary

1. Calculate completion percentage: `completed_items / total_items * 100`
2. Print summary:
   - Sections complete vs. remaining
   - For incomplete items, list the specific action needed
   - If all items complete, print next steps:
     - Pick up your first Jira ticket
     - Submit your first PR
     - Update this onboarding doc for the next new team member
3. Save final progress to `~/.node-assistant/onboarding-progress.json`
   (not in `--check-only` mode).

### Progress File Format

```json
{
  "track": "dev",
  "started": "<YYYY-MM-DD>",
  "last_updated": "<YYYY-MM-DD>",
  "sections": {
    "prerequisites": {"status": "complete", "items": {"vpn": true, "jira": true}},
    "access": {"status": "in_progress", "items": {"ldap_node_team": true, "slack_team_node": false}}
  }
}
```

## Return Value

A completion summary showing which sections passed, which have remaining
items, and specific next steps for incomplete items.

## Examples

1. **Start fresh onboarding (dev track)**:
   ```bash
   /node-onboarding:checklist
   ```

2. **QE-specific onboarding**:
   ```bash
   /node-onboarding:checklist --track qe
   ```

3. **Resume after a break**:
   ```bash
   /node-onboarding:checklist --resume
   ```

4. **Just check what's done**:
   ```bash
   /node-onboarding:checklist --check-only
   ```

## Arguments

- **--track** *(optional)*
  Onboarding track. `dev` (default) covers the standard developer path.
  `qe` adds QE-specific items (Polarion, openshift-tests-private, Ginkgo).

- **--resume** *(optional)*
  Load progress from `~/.node-assistant/onboarding-progress.json` and skip
  completed sections.

- **--check-only** *(optional)*
  Run automated verification checks only. Do not prompt for manual
  confirmation. Does not read, create or modify the progress file. Useful for
  periodic re-validation.
