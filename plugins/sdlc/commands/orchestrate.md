---
description: Orchestrate complete SDLC from Jira issue through deployment
---

## Name
sdlc:orchestrate

## Synopsis
```
/sdlc:orchestrate <jira-key> [remote] [--ci] [--resume]
```

## Description

The `sdlc:orchestrate` command automates the complete Software Development Lifecycle (SDLC) for OpenShift development workflows. It orchestrates 7 sequential phases from enhancement proposal generation through deployment verification.

**Phases:**
1. **Enhancement Generation** - Generate OpenShift enhancement proposal from Jira epic/feature
2. **Design & Planning** - Create detailed implementation specification
3. **Implementation** - Execute code changes with verification
4. **Testing & Validation** - Run comprehensive test suite
5. **PR Creation & Review** - Create pull request with full context
6. **Merge & Deployment Tracking** - Monitor merge and track payload inclusion
7. **Completion & Verification** - Update Jira and generate report

**Key Features:**
- ✅ Full resumability (pause/resume at any phase)
- ✅ State tracking with YAML state files
- ✅ Verification gates between phases
- ✅ Interactive and automation modes
- ✅ OpenShift payload tracking
- ✅ Comprehensive reporting

**Usage Examples:**

1. **Interactive orchestration** (recommended for first-time users):
   ```
   /sdlc:orchestrate OCPSTRAT-1612 origin
   ```

2. **Resume from saved state**:
   ```
   /sdlc:orchestrate OCPSTRAT-1612 origin --resume
   ```

3. **Fully automated (CI mode)**:
   ```
   /sdlc:orchestrate OCPSTRAT-1612 origin --ci
   ```

## Implementation

### Prerequisites Check

Before starting orchestration, verify:

1. **Required skills available**:
   - Load `sdlc-state-yaml` skill (MUST be loaded first)
   - Verify `jira:generate-enhancement` command exists (Phase 1 dependency)
2. **Tools available**:
   - Git repository (check with `git rev-parse --is-inside-work-tree`)
   - GitHub CLI (`gh --version`)
   - Build tools (detect Makefile or language-specific tools)
3. **Credentials configured**:
   - Jira access (check MCP configuration)
   - GitHub authentication (check `gh auth status`)
4. **Working directory**:
   - Must be in git repository root
   - Working directory should be clean (or user-confirmed dirty state)

If any prerequisites fail:
- In interactive mode: Ask user to fix issue and retry
- In automation mode: Exit with clear error message

### Parse Arguments

**Arguments:**
- `$1` (required): Jira issue key (e.g., `OCPSTRAT-1612`, `HIVE-2589`)
- `$2` (optional): Git remote name (default: `"origin"`)
- `$3` (optional): `--ci` flag for non-interactive automation mode
- `$4` (optional): `--resume` flag to resume from saved state

**Parse and validate:**

```bash
JIRA_KEY="$1"
REMOTE="${2:-origin}"
CI_MODE=false
RESUME_MODE=false

# Parse flags from any position
for arg in "$@"; do
  case "$arg" in
    --ci) CI_MODE=true ;;
    --resume) RESUME_MODE=true ;;
  esac
done

# Validate JIRA_KEY format
if [[ ! "$JIRA_KEY" =~ ^[A-Z]+-[0-9]+$ ]]; then
  echo "Error: Invalid Jira key format. Expected: PROJECT-123"
  exit 1
fi

# Verify remote exists
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "Error: Git remote '$REMOTE' not found"
  git remote -v
  exit 1
fi
```

**Set mode**:
```bash
MODE="interactive"
if [ "$CI_MODE" = true ]; then
  MODE="automation"
fi
```

### Initialize or Resume State

**If `--resume` flag is set:**

1. Check if state file exists:
   ```bash
   STATE_FILE=".work/sdlc/$JIRA_KEY/sdlc-state.yaml"
   if [ ! -f "$STATE_FILE" ]; then
     echo "Error: No state file found at $STATE_FILE"
     echo "Cannot resume - no previous orchestration found"
     exit 1
   fi
   ```

2. Load state file using `sdlc-state-yaml` skill "Resume Detection" operation

3. Validate state file:
   - Check `schema_version` is compatible
   - Check `resumability.can_resume` is `true`
   - Identify phase to resume from

4. Display resume information:
   ```
   Resuming SDLC orchestration for {jira_key}

   Current phase: {current_phase.name} ({current_phase.status})
   Last updated: {current_phase.last_updated}
   Progress: {completed_phases}/7 phases completed

   Completed phases:
   ✅ {phase1}
   ✅ {phase2}
   ...

   Resume from: {resume_from_phase}
   ```

5. In interactive mode:
   - Ask: "Continue from where you left off? (yes/no)"
   - If no: Exit
   - If yes: Proceed to phase execution starting from `resume_from_phase`

6. In automation mode:
   - Proceed automatically

**If NOT resuming (fresh start):**

1. Fetch Jira issue to get context:
   ```bash
   # Using MCP tool or curl to Jira API
   JIRA_URL="https://redhat.atlassian.net/rest/api/3/issue/$JIRA_KEY"
   JIRA_DATA=$(curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" "$JIRA_URL")
   ```

2. Parse Jira data:
   - Extract `summary` (feature summary)
   - Extract `key` (jira_key)
   - Build jira_url

3. Create state directory:
   ```bash
   mkdir -p ".work/sdlc/$JIRA_KEY"
   ```

4. Initialize state file using `sdlc-state-yaml` skill "Create" operation:
   - Set metadata (jira_key, jira_url, feature_summary, etc.)
   - Set all phases to "pending"
   - Set current_phase to "enhancement"
   - Set resumability.can_resume to true

5. Display initialization:
   ```
   📋 SDLC Orchestrator v0.1.0
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Fetching {jira_key} from Jira...
   ✓ Issue found: "{feature_summary}"
   ✓ Issue type: {issue_type}
   ✓ Status: {status}

   Initializing state file at .work/sdlc/{jira_key}/sdlc-state.yaml

   Mode: {interactive|automation}
   Remote: {remote}

   Starting SDLC orchestration...
   ```

### Phase Execution Loop

Execute phases sequentially from start (or resume point) through completion:

```pseudocode
START_PHASE = resume_from_phase if resuming else "enhancement"
PHASES = ["enhancement", "design", "implementation", "testing", "pr_review", "merge", "completion"]

for phase in PHASES[index_of(START_PHASE):]:
  execute_phase(phase)

  # Check if user wants to pause (interactive mode)
  if MODE == "interactive" and user_wants_pause():
    update_state_for_pause()
    exit_gracefully()

  # Check if phase failed
  if phase_failed(phase):
    handle_phase_failure(phase)
    break
```

**For each phase:**

1. **Display phase header** (interactive mode):
   ```
   ━━━ Phase {N}/7: {Phase Name} ━━━
   ```

2. **Invoke phase skill**:
   ```
   Use Skill tool with skill name: "phase-{phase_name}"
   ```

   Skills to invoke:
   - Phase 1: `Skill(skill: "phase-enhancement")`
   - Phase 2: `Skill(skill: "phase-design")`
   - Phase 3: `Skill(skill: "phase-implementation")`
   - Phase 4: `Skill(skill: "phase-testing")`
   - Phase 5: `Skill(skill: "phase-pr-review")`
   - Phase 6: `Skill(skill: "phase-merge")`
   - Phase 7: `Skill(skill: "phase-completion")`

3. **Phase skill executes** and updates state file

4. **Check phase result**:
   - Read updated state file
   - Check `phases.{phase_name}.status`
   - If "completed": Continue to next phase
   - If "failed": Handle failure (see Error Handling)
   - If "blocked": Handle blocking (see Error Handling)

5. **Pause checkpoint** (interactive mode only):
   - After each phase completion, ask user:
     ```
     Phase {N} complete. Continue to Phase {N+1}? (yes/pause)
     ```
   - If pause: Update state, display resume instructions, exit
   - If yes: Continue

6. **Progress tracking**:
   - Update state file with progress
   - Log phase completion timestamps
   - Calculate estimated time remaining (based on average phase duration)

### Completion

After all 7 phases complete:

1. Read final state file

2. Display final summary (from Phase 7 output)

3. In interactive mode:
   - Ask: "Orchestration complete. Would you like to:
     1. View completion report
     2. Open PR in browser
     3. Open Jira issue in browser
     4. Exit"
   - Handle user choice

4. Exit with success code

### Error Handling

**Phase Failure:**

If a phase fails:

1. Read error details from state file:
   - `errors[]` array
   - `phases.{phase_name}.status == "failed"`

2. Display error:
   ```
   ❌ Phase {N} failed: {phase_name}

   Error: {error_message}
   Type: {error_type}
   ```

3. In interactive mode:
   - Show error details
   - Ask: "Would you like to:
     1. Retry phase
     2. Skip phase (if allowed)
     3. Abort orchestration
     4. Debug (show state file)"
   - Handle user choice

4. In automation mode:
   - Log detailed error
   - Update state with failure
   - Exit with error code

5. Update `resumability`:
   - Set `can_resume` based on whether failure is recoverable
   - Set `blocking_issues` with failure description
   - Set `manual_intervention_required` if user action needed

**Phase Blocked:**

If a phase is blocked (e.g., waiting for PR merge):

1. Display blocking reason:
   ```
   ⏸ Phase {N} blocked: {phase_name}

   Reason: {blocking_reason}
   ```

2. In interactive mode:
   - Ask: "Would you like to:
     1. Wait (poll for unblock)
     2. Pause (resume later with --resume)
     3. Force continue (skip waiting)"

3. In automation mode:
   - Update state with block reason
   - Exit with message: "Orchestration blocked. Resume with --resume when {condition} is met."

**User Cancellation:**

If user cancels (Ctrl+C) during interactive mode:

1. Trap signal:
   ```bash
   trap 'handle_cancel' INT TERM
   ```

2. Handle cancellation:
   - Display: "Orchestration cancelled by user"
   - Ensure state file is written with current progress
   - Display resume instructions
   - Exit cleanly

### Pause and Resume Instructions

When orchestration is paused:

```
Orchestration paused.

State saved to: .work/sdlc/{jira_key}/sdlc-state.yaml
Current phase: {current_phase.name}
Progress: {completed_phases}/7 phases completed

To resume:
  /sdlc:orchestrate {jira_key} {remote} --resume

To review state:
  Read .work/sdlc/{jira_key}/sdlc-state.yaml
```

### Interactive vs Automation Mode Differences

| Aspect | Interactive Mode | Automation Mode (--ci) |
|--------|------------------|------------------------|
| User prompts | Shows all prompts, waits for input | No prompts, proceeds automatically |
| Spec approval | User reviews and approves | AI proceeds if confidence ≥ 80% |
| Phase transitions | Asks between phases | Automatic |
| Error handling | Offers choices | Fails fast with error |
| PR review | User reviews PR description | Creates draft PR, no review |
| Blocking | Offers wait/pause options | Exits with resume instructions |
| Jira transition | Asks user | Skips transition |

### State File Management

The orchestrator relies heavily on the state file:

**State file operations:**
- Create: When starting fresh orchestration
- Read: At start of each phase
- Update: During and after each phase
- Archive: On completion

**State file location:**
- `.work/sdlc/{jira-key}/sdlc-state.yaml`

**All state operations use the `sdlc-state-yaml` skill**

**State file provides:**
- Current phase tracking
- Phase outputs (enhancement path, spec path, PR number, etc.)
- Verification gate status
- Error history
- Resumability information
- Progress metrics

## Arguments

- `$1`: The Jira issue key to orchestrate (required)
- `$2`: The git remote name (default: "origin")
- `$3` or `$4`: Optional `--ci` flag for non-interactive automation mode
- `$3` or `$4`: Optional `--resume` flag to resume from saved state

## Examples

**Example 1: Basic Interactive Orchestration**

```bash
/sdlc:orchestrate OCPSTRAT-1612 origin
```

Runs full SDLC with user prompts and approvals at each phase.

**Example 2: Resume After Pause**

```bash
# First run - user pauses at Phase 3
/sdlc:orchestrate OCPSTRAT-1612 origin
# ... user pauses ...

# Later - resume from where left off
/sdlc:orchestrate OCPSTRAT-1612 origin --resume
```

**Example 3: Fully Automated**

```bash
/sdlc:orchestrate OCPSTRAT-1612 origin --ci
```

Runs all phases automatically without user interaction.

**Example 4: Different Remote**

```bash
/sdlc:orchestrate HIVE-2589 upstream
```

Uses "upstream" remote instead of "origin".

## Output

The orchestrator creates the following artifacts in `.work/sdlc/{jira-key}/`:

- `sdlc-state.yaml` - State file tracking progress
- `enhancement-proposal.md` - Generated enhancement (Phase 1)
- `implementation-spec.md` - Implementation plan (Phase 2)
- `test-output.txt` - Test results (Phase 4)
- `coverage.html` - Coverage report (Phase 4)
- `pr-description.md` - PR description (Phase 5)
- `completion-report.md` - Final report (Phase 7)
- `sdlc-state-completed-{timestamp}.yaml` - Archived state (Phase 7)

## Notes

- **Prerequisite**: The `jira:generate-enhancement` command must be available (feature-based-enhancement branch must be merged to main)
- **OpenShift-specific**: This orchestrator is designed for OpenShift development workflows with Jira, GitHub, and payload tracking
- **Resumability**: Orchestration can be paused and resumed at any phase using `--resume`
- **State tracking**: All progress is tracked in YAML state files
- **Verification gates**: Each phase has verification gates that must pass before proceeding
- **CI mode**: Use `--ci` flag for fully automated execution (suitable for CI/CD pipelines)

## See Also

- Related Skill: `sdlc-state-yaml` — State schema and operations
- Related Skill: `phase-enhancement` — Phase 1 implementation
- Related Skill: `phase-design` — Phase 2 implementation
- Related Skill: `phase-implementation` — Phase 3 implementation
- Related Skill: `phase-testing` — Phase 4 implementation
- Related Skill: `phase-pr-review` — Phase 5 implementation
- Related Skill: `phase-merge` — Phase 6 implementation
- Related Skill: `phase-completion` — Phase 7 implementation
- Related Command: `/jira:generate-enhancement` — Enhancement generation (Phase 1)
- Related Command: `/jira:solve` — Implementation patterns (Phase 3)
