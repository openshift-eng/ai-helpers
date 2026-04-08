# SDLC Plugin

Software Development Lifecycle (SDLC) orchestrator for OpenShift development workflows.

## Overview

The SDLC plugin automates the complete software development lifecycle from Jira issue through deployment verification. It orchestrates 7 sequential phases with state tracking, resumability, and comprehensive reporting.

**What it does:**
- Generates OpenShift enhancement proposals from Jira epics/features
- Creates detailed implementation specifications
- Executes code changes with verification gates
- Runs comprehensive test suites
- Creates pull requests with full context
- Tracks merge and deployment to payloads
- Updates Jira and generates completion reports

**Key benefits:**
- ✅ Consistency across development workflows
- ✅ Nothing falls through the cracks
- ✅ Full audit trail and documentation
- ✅ Pause and resume at any phase
- ✅ Interactive or fully automated modes
- ✅ OpenShift payload tracking

## Commands

### `/sdlc:orchestrate`

Orchestrate complete SDLC from Jira issue through deployment.

**Synopsis:**
```bash
/sdlc:orchestrate <jira-key> [remote] [--ci] [--resume]
```

**Arguments:**
- `<jira-key>` (required): Jira epic/feature/story key (e.g., `OCPSTRAT-1612`)
- `[remote]` (optional): Git remote name (default: `origin`)
- `--ci` (optional): Non-interactive automation mode
- `--resume` (optional): Resume from saved state

**Examples:**

```bash
# Interactive mode (recommended)
/sdlc:orchestrate OCPSTRAT-1612 origin

# Resume after pause
/sdlc:orchestrate OCPSTRAT-1612 origin --resume

# Fully automated (CI mode)
/sdlc:orchestrate OCPSTRAT-1612 origin --ci

# Use different remote
/sdlc:orchestrate HIVE-2589 upstream
```

## Phases

The orchestrator executes 7 sequential phases:

### Phase 1: Enhancement Generation
- Generates OpenShift enhancement proposal from Jira epic/feature
- Uses `/jira:generate-enhancement` command
- Output: `enhancement-proposal.md`

### Phase 2: Design & Planning
- Analyzes enhancement and codebase
- Creates detailed implementation specification
- User reviews and approves (interactive mode)
- Output: `implementation-spec.md`

### Phase 3: Implementation
- Executes code changes according to spec
- Follows `/jira:solve` patterns
- Runs verification: `make lint-fix`, `make verify`, `make test`, `make build`
- Creates logical conventional commits
- Output: Feature branch with commits

### Phase 4: Testing & Validation
- Runs comprehensive test suite
- Measures coverage
- Distinguishes new vs pre-existing failures
- Output: Test results and coverage reports

### Phase 5: PR Creation & Review
- Creates pull request with comprehensive description
- Links to enhancement, spec, and Jira
- Triggers CI checks
- User reviews PR (interactive mode)
- Output: GitHub PR

### Phase 6: Merge & Deployment Tracking
- Monitors PR merge status
- Tracks commit inclusion in OpenShift payloads
- Verifies deployment
- Output: Merge details and payload status

### Phase 7: Completion & Verification
- Generates completion report
- Adds Jira comment with summary
- Optionally transitions Jira status
- Archives state file
- Output: Completion report

## State Management

All progress is tracked in YAML state files at `.work/sdlc/{jira-key}/sdlc-state.yaml`.

**State includes:**
- Current phase and status
- Outputs from each phase (paths, URLs, metrics)
- Verification gate results
- Error history
- Resumability information

**State file schema:**
```yaml
schema_version: "1.0"
metadata:
  jira_key: "OCPSTRAT-1612"
  jira_url: "https://redhat.atlassian.net/browse/OCPSTRAT-1612"
  mode: "interactive"  # or "automation"
  remote: "origin"
current_phase:
  name: "implementation"
  status: "in_progress"
phases:
  enhancement: {status: "completed", outputs: {...}}
  design: {status: "completed", outputs: {...}}
  implementation: {status: "in_progress", outputs: {...}}
  testing: {status: "pending"}
  pr_review: {status: "pending"}
  merge: {status: "pending"}
  completion: {status: "pending"}
resumability:
  can_resume: true
  resume_from_phase: "implementation"
```

## Resumability

Orchestration can be paused and resumed at any phase:

**Pause:**
- User presses Ctrl+C or selects "pause" option
- State file is saved with current progress
- Resume instructions displayed

**Resume:**
```bash
/sdlc:orchestrate {jira-key} {remote} --resume
```

- Loads saved state
- Skips completed phases
- Continues from where it left off

**Use cases for pause/resume:**
- Long-running implementations (pause overnight, resume next day)
- Waiting for code review feedback
- Waiting for PR merge
- Switching between tasks

## Verification Gates

Each phase has verification gates that must pass before proceeding:

| Phase | Verification Gates |
|-------|-------------------|
| Enhancement | Document exists, valid markdown, required sections |
| Design | Spec exists, contains plan, user approval (interactive) |
| Implementation | make lint-fix, make verify, make test, commits created |
| Testing | Tests executed, no new failures, coverage adequate |
| PR Review | PR created, linked to Jira, CI triggered |
| Merge | PR merged, commit identified, payload tracked (OpenShift) |
| Completion | Report generated, Jira updated, deployment verified |

## Interactive vs Automation Modes

### Interactive Mode (default)

- User prompts at key decision points
- Spec approval before implementation
- PR description review
- Phase transition confirmations
- Pause/continue options
- Best for: Development work, learning the orchestrator

### Automation Mode (`--ci` flag)

- No user prompts
- AI proceeds automatically
- Fails fast on errors
- Creates draft PRs
- Best for: CI/CD pipelines, batch processing

**Toggle modes:**
```bash
# Interactive (default)
/sdlc:orchestrate OCPSTRAT-1612 origin

# Automation
/sdlc:orchestrate OCPSTRAT-1612 origin --ci
```

## Prerequisites

### Required

1. **Feature Branch Merged**:
   - The `jira:generate-enhancement` command must be available
   - Merge `feature-based-enhancement` branch to main first

2. **Git Repository**:
   - Must be in git repository root
   - Remote must be configured

3. **GitHub CLI**:
   - `gh` command must be installed and authenticated

4. **Jira Access**:
   - Valid Jira credentials configured in MCP settings

### Optional

- **Build Tools**: Makefile or language-specific build tools
- **Test Frameworks**: For running tests and coverage
- **OpenShift CI Access**: For payload tracking (OpenShift repos only)

## Output Artifacts

All artifacts are saved to `.work/sdlc/{jira-key}/`:

| File | Phase | Description |
|------|-------|-------------|
| `sdlc-state.yaml` | All | State file tracking progress |
| `enhancement-proposal.md` | 1 | OpenShift enhancement proposal |
| `implementation-spec.md` | 2 | Detailed implementation plan |
| `test-output.txt` | 4 | Test execution results |
| `coverage.html` | 4 | Test coverage report |
| `pr-description.md` | 5 | Pull request description |
| `completion-report.md` | 7 | Final completion report |
| `sdlc-state-completed-*.yaml` | 7 | Archived state file |

## Error Handling

The orchestrator handles errors gracefully:

### Phase Failures

If a phase fails:
- Error details recorded in state file
- Interactive mode: User offered options (retry, skip, abort, debug)
- Automation mode: Fails fast with detailed error

### Recoverable Errors

Examples: Lint failures, test failures, Jira API timeouts
- Automatic retry with exponential backoff
- Distinguish pre-existing vs new failures
- Attempt automatic fixes where possible

### Blocking Conditions

Examples: PR not yet merged, payload pending
- State saved with blocking reason
- Resumability enabled
- User can resume later when unblocked

### Non-recoverable Errors

Examples: jira:generate-enhancement not available, PR closed without merge
- State updated with error
- `resumability.can_resume` set to false
- Clear error message with resolution steps

## Troubleshooting

### "jira:generate-enhancement command not found"

**Problem**: The enhancement generation command is not available.

**Solution**:
```bash
# Merge the feature branch first
git checkout feature-based-enhancement
git pull
git checkout main
git merge feature-based-enhancement
```

### "Cannot resume - no state file found"

**Problem**: Trying to resume but no previous orchestration exists.

**Solution**:
```bash
# Remove --resume flag for fresh start
/sdlc:orchestrate {jira-key} {remote}
```

### "PR closed without merging"

**Problem**: PR was closed but not merged.

**Solution**:
1. Reopen the PR if it should be merged
2. Or start fresh orchestration if PR was intentionally closed

### "Payload tracking failed"

**Problem**: Unable to track OpenShift payloads.

**Solution**:
- Verify network access to release controller
- Check if repository is actually an OpenShift component
- Payload tracking is optional - orchestration can succeed without it

### "Phase blocked: waiting for PR merge"

**Problem**: Orchestration paused waiting for PR to be merged.

**Solution**:
1. Review and merge the PR
2. Resume orchestration:
   ```bash
   /sdlc:orchestrate {jira-key} {remote} --resume
   ```

## Best Practices

### When to Use Interactive Mode

- First time using the orchestrator
- Complex features requiring review at each phase
- Learning how the workflow works
- When you want control over phase transitions

### When to Use Automation Mode

- Batch processing multiple issues
- CI/CD pipeline integration
- Simple/small features with high confidence
- Reproducible automated workflows

### When to Pause

- End of work day (pause overnight)
- Waiting for external input (code review, design feedback)
- Switching to higher priority task
- Need to debug unexpected behavior

### Managing State Files

- **Keep state files**: They're your audit trail
- **Archive on completion**: State is automatically archived
- **Clean old states**: Periodically remove old `.work/sdlc/` directories
- **Backup important orchestrations**: State files contain full history

## Advanced Usage

### Custom Verification Commands

If repository doesn't have standard Makefile targets, the orchestrator will detect language and use appropriate commands:

- **Go**: `go fmt`, `go vet`, `go test`, `go build`
- **Node.js**: `npm run lint`, `npm test`, `npm run build`
- **Python**: `pylint`, `black`, `pytest`

### Skipping Phases

Generally not recommended, but some phases can be skipped:
- Enhancement generation: If enhancement already exists
- Testing: If repository has no tests (warning issued)
- Payload tracking: For non-OpenShift repositories

### Multiple Parallel Orchestrations

You can run orchestrations for multiple issues in different directories:

```bash
# Terminal 1
cd /path/to/repo1
/sdlc:orchestrate OCPSTRAT-1612 origin

# Terminal 2
cd /path/to/repo2
/sdlc:orchestrate OCPSTRAT-1613 origin
```

Each orchestration maintains independent state.

## Version History

### v0.1.0 (Current)

Initial release with:
- 7-phase orchestration workflow
- State management and resumability
- Interactive and automation modes
- OpenShift payload tracking
- Comprehensive error handling
- Full documentation

## License

Copyright Red Hat, Inc.

## Contributing

To contribute to the SDLC plugin:

1. Follow the patterns in existing skills
2. Update version in `plugin.json` when changing functionality
3. Run `make lint` before committing
4. Update README if adding new features
5. Test with real Jira issues before submitting PR

## Support

For issues or questions:
- Check troubleshooting section above
- Review state file for error details
- Open issue at https://github.com/anthropics/claude-code/issues
- Tag with "plugin: sdlc"
