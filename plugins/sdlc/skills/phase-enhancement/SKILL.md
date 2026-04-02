---
name: Phase Enhancement
description: Generate OpenShift enhancement proposal from Jira epic or feature (Phase 1 of SDLC orchestrator)
---

# Phase Enhancement

This skill implements Phase 1 of the SDLC orchestrator: Enhancement Generation. It generates an OpenShift enhancement proposal from a Jira epic or feature using the `/jira:generate-enhancement` command.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded before this phase
2. **Feature Branch Merged**: The `jira:generate-enhancement` command must be available (feature-based-enhancement branch merged to main)
3. **Jira Access**: Valid Jira credentials configured in MCP settings
4. **State File**: SDLC state file must exist at `.work/sdlc/{jira-key}/sdlc-state.yaml`

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key (e.g., `"OCPSTRAT-1612"`)
- `metadata.mode`: Orchestration mode (`"interactive"` or `"automation"`)
- `current_phase.name`: Should be `"enhancement"` when this phase starts

## Outputs

Written to state file:
- `phases.enhancement.outputs.enhancement_doc_path`: Path to generated enhancement document
- `phases.enhancement.outputs.jira_key`: Jira issue key
- `phases.enhancement.outputs.feature_summary`: Feature summary from Jira
- `phases.enhancement.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file: `.work/sdlc/{jira-key}/sdlc-state.yaml`
2. Update state using the "Update Phase Start" operation from `sdlc-state-yaml`:
   - `current_phase.name`: `"enhancement"`
   - `current_phase.status`: `"in_progress"`
   - `current_phase.started_at`: Current timestamp
   - `phases.enhancement.status`: `"in_progress"`
   - `phases.enhancement.started_at`: Current timestamp
3. Write updated state file

### Step 2: Check for Existing Enhancement Document

Check if an enhancement document already exists:

1. Define expected path: `.work/sdlc/{jira-key}/enhancement-proposal.md`
2. Check if file exists using the Read tool
3. If exists:
   - Log: "Enhancement document already exists, skipping generation"
   - Set `reused_existing: true` in outputs
   - Skip to Step 5 (Verification)
4. If not exists:
   - Continue to Step 3

### Step 3: Verify jira:generate-enhancement Availability

Check if the required command is available:

1. Use Glob tool to search for: `plugins/jira/commands/generate-enhancement.md`
2. If not found:
   - Update state with error:
     - `phase`: `"enhancement"`
     - `error_type`: `"missing_dependency"`
     - `message`: `"jira:generate-enhancement command not found. The feature-based-enhancement branch must be merged to main first."`
     - `resolved`: `false`
   - Update phase status to `"failed"`
   - Update `resumability.can_resume`: `false`
   - Update `resumability.blocking_issues`: `["jira:generate-enhancement command not available"]`
   - Write state file and exit with error
3. If found:
   - Continue to Step 4

### Step 4: Generate Enhancement Document

Invoke the `jira:generate-enhancement` command:

1. Invoke using the Skill tool:
   ```
   skill: "jira:generate-enhancement"
   args: "{jira_key} --output .work/sdlc/{jira-key}/"
   ```
2. The command will:
   - Fetch the Jira epic/feature
   - Generate enhancement proposal
   - Save to `.work/sdlc/{jira-key}/enhancement-proposal.md`
3. If the Skill invocation fails:
   - Append error to state `errors` array
   - Update phase status to `"failed"`
   - Ask user if they want to:
     - Retry enhancement generation
     - Provide an existing enhancement document path
     - Skip enhancement phase (proceed without enhancement)
   - Handle user choice accordingly
4. If successful:
   - Continue to Step 5

### Step 5: Verify Enhancement Document

Run verification gates:

**Gate 1: Document Exists**

1. Check if file exists: `.work/sdlc/{jira-key}/enhancement-proposal.md`
2. Update verification gate in state:
   ```yaml
   - gate: "document_exists"
     status: "passed"  # or "failed"
     timestamp: "{current_timestamp}"
   ```
3. If failed:
   - Update phase status to `"failed"`
   - Write state and exit

**Gate 2: Valid Markdown Format**

1. Read the enhancement document
2. Check that it's valid markdown:
   - Starts with YAML frontmatter (between `---` markers)
   - Contains markdown content after frontmatter
3. Update verification gate in state:
   ```yaml
   - gate: "document_valid_markdown"
     status: "passed"  # or "failed"
     timestamp: "{current_timestamp}"
   ```
4. If failed:
   - Update phase status to `"failed"`
   - Write state and exit

**Gate 3: Required Sections Present**

1. Parse the enhancement document
2. Check for required sections (case-insensitive):
   - `## Summary`
   - `## Motivation`
   - `## Goals` (or `### Goals` under Motivation)
   - `## Proposal`
   - `## Risks and Mitigations` (or `## Risks`)
3. Update verification gate in state:
   ```yaml
   - gate: "required_sections_present"
     status: "passed"  # or "failed"
     timestamp: "{current_timestamp}"
   ```
4. If failed:
   - Log warning (not blocking) - some enhancement templates vary
   - Mark gate as `"warning"` instead of `"failed"`

**Gate 4: Tracking Link to Jira**

1. Parse YAML frontmatter
2. Check for `tracking-link` field containing the Jira URL
3. Update verification gate in state:
   ```yaml
   - gate: "jira_tracking_link"
     status: "passed"  # or "failed"
     timestamp: "{current_timestamp}"
   ```
4. If failed:
   - Log warning (not blocking)
   - Mark gate as `"warning"`

### Step 6: Extract Outputs

Extract information from the enhancement document:

1. Parse YAML frontmatter:
   - Extract `title` field
2. Read Jira data from state `metadata`
3. Update state with outputs:
   ```yaml
   phases:
     enhancement:
       outputs:
         enhancement_doc_path: ".work/sdlc/{jira-key}/enhancement-proposal.md"
         jira_key: "{jira_key}"
         feature_summary: "{title or summary from enhancement}"
         reused_existing: false  # or true if existing doc was reused
   ```

### Step 7: Update State - Phase Complete

1. Read current state
2. Update state using "Update Phase Complete" operation:
   - `phases.enhancement.status`: `"completed"`
   - `phases.enhancement.completed_at`: Current timestamp
   - `resumability.resume_from_phase`: `"design"` (next phase)
3. Write updated state file

### Step 8: Display Summary (Interactive Mode Only)

If `metadata.mode == "interactive"`:

1. Display summary to user:
   ```
   ━━━ Phase 1/7: Enhancement Generation ━━━ COMPLETE

   ✓ Enhancement document generated
   ✓ Saved to: .work/sdlc/{jira-key}/enhancement-proposal.md
   ✓ All verification gates passed

   Next phase: Design & Planning
   ```

2. Ask user if they want to continue to next phase or pause:
   - If continue: Return to orchestrator to proceed to Phase 2
   - If pause: Update `resumability.manual_intervention_required = true` and exit

If `metadata.mode == "automation"`:
- Skip user interaction
- Return to orchestrator automatically

## Error Handling

### Enhancement Generation Fails

If `jira:generate-enhancement` fails:

1. Append error to state:
   ```yaml
   errors:
     - phase: "enhancement"
       timestamp: "{current_timestamp}"
       error_type: "generation_failed"
       message: "{error message from skill}"
       resolved: false
   ```
2. Update phase status to `"failed"`
3. In interactive mode:
   - Ask user: "Enhancement generation failed. Options: (1) Retry, (2) Provide existing enhancement path, (3) Skip enhancement phase"
   - Handle user choice
4. In automation mode:
   - Exit with failure

### Enhancement Document Invalid

If verification gates fail:

1. Append error to state with specific gate failure
2. Update phase status to `"failed"`
3. In interactive mode:
   - Show which gates failed
   - Ask user: "Enhancement document validation failed. Options: (1) Regenerate, (2) Manually fix and retry validation, (3) Skip validation"
4. In automation mode:
   - Exit with failure

### Command Not Available

If `jira:generate-enhancement` command doesn't exist:

1. Error already recorded in Step 3
2. Provide clear message: "The jira:generate-enhancement command is not available. Please merge the feature-based-enhancement branch first."
3. Update `resumability.can_resume: false`
4. Exit with failure (cannot proceed without this dependency)

## Success Criteria

Phase 1 is successful when:

- ✅ Enhancement document exists at expected path
- ✅ Document is valid markdown with YAML frontmatter
- ✅ Required sections are present (or warnings logged)
- ✅ Jira tracking link is present (or warning logged)
- ✅ State file updated with outputs and status
- ✅ All verification gates passed (or warnings only)

## See Also

- Related Command: `/jira:generate-enhancement` — generates enhancement from Jira
- Related Skill: `sdlc-state-yaml` — state schema and operations
- Next Phase: `phase-design` — creates implementation specification
