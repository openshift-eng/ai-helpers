---
name: Phase Design
description: Create detailed implementation specification from enhancement proposal (Phase 2 of SDLC orchestrator)
---

# Phase Design

This skill implements Phase 2 of the SDLC orchestrator: Design & Planning. It analyzes the enhancement proposal and codebase to create a detailed implementation specification.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded
2. **Phase 1 Complete**: Enhancement phase must be completed with valid enhancement document
3. **Codebase Access**: Must be in git repository root
4. **State File**: SDLC state file must exist with Phase 1 outputs

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key
- `metadata.mode`: Orchestration mode
- `phases.enhancement.outputs.enhancement_doc_path`: Path to enhancement document
- `phases.enhancement.outputs.feature_summary`: Feature summary

## Outputs

Written to state file:
- `phases.design.outputs.spec_path`: Path to implementation specification
- `phases.design.outputs.estimated_complexity`: Complexity estimate (low/medium/high)
- `phases.design.outputs.files_to_modify`: Array of file paths to modify
- `phases.design.outputs.repos_cloned`: Array of cloned repository paths (if applicable)
- `phases.design.outputs.codebase_analysis_complete`: Boolean indicating if actual code was analyzed
- `phases.design.outputs.implementation_analysis_path`: Path to detailed code analysis document (if created)
- `phases.design.outputs.key_files_identified`: Array of key files with line numbers
- `phases.design.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file
2. Update state using "Update Phase Start" operation:
   - `current_phase.name`: `"design"`
   - `current_phase.status`: `"in_progress"`
   - `phases.design.status`: `"in_progress"`
   - `phases.design.started_at`: Current timestamp
3. Write state file

### Step 2: Analyze Enhancement Document

Read and analyze the enhancement proposal:

1. Read enhancement document from `phases.enhancement.outputs.enhancement_doc_path`
2. Parse YAML frontmatter to extract:
   - Title
   - Tracking links
   - Authors
3. Parse markdown sections to extract:
   - **Summary**: High-level overview
   - **Motivation**: Why this change is needed
   - **Goals**: What the feature aims to achieve
   - **Non-Goals**: What is explicitly out of scope
   - **Proposal/Workflow Description**: How it will work
   - **API Extensions**: Any API changes required
   - **Implementation Details/Notes/Constraints**: Technical details
   - **Risks and Mitigations**: Known risks
   - **Test Plan**: Testing approach
4. Create a summary of key implementation requirements:
   - API changes needed (new types, fields, CRDs)
   - Controller/operator logic changes
   - CLI changes
   - Test requirements
   - Documentation requirements

### Step 3: Clone Required Repositories (if external repos needed)

If the implementation requires modifying code in external repositories (e.g., openshift/installer, kubernetes/kubernetes):

1. **Create repos directory**:
   ```bash
   mkdir -p .work/sdlc/{jira-key}/repos
   ```

2. **Clone required repositories**:
   ```bash
   cd .work/sdlc/{jira-key}/repos
   git clone --depth 1 https://github.com/{org}/{repo}.git
   ```
   
   - Use `--depth 1` for faster shallow clone
   - Run clones in parallel using `run_in_background: true` when cloning multiple repos
   - Wait for completion notifications before proceeding

3. **Update state file** with cloned repository information:
   ```yaml
   outputs:
     repos_cloned:
       - "{org}/{repo} -> .work/sdlc/{jira-key}/repos/{repo}"
   ```

4. **Benefits of cloning**:
   - Analyze actual code structure with precise line numbers
   - Search for existing patterns and conventions
   - Identify exact modification points
   - Understand current implementation details
   - Find related test files and testing patterns

**When to clone repositories**:
- Enhancement proposes changes to external projects (OpenShift, Kubernetes, etc.)
- Need to analyze actual code structure for accurate implementation plan
- Implementation requires understanding existing patterns
- Want to provide exact file paths and line numbers in specification

**When to skip cloning**:
- Working entirely in current repository
- Enhancement is conceptual without code changes
- Time constraints (can analyze via GitHub web interface instead)

### Step 4: Search Codebase for Related Code

Identify existing code that will need modification (either in cloned repos or current directory):

1. **Search for related file patterns** based on component:
   - Use Glob tool to find files matching patterns like:
     - `api/**/*.go` (for API changes)
     - `pkg/operator/**/*.go` or `controllers/**/*.go` (for operator logic)
     - `cmd/**/*.go` (for CLI changes)
     - Component-specific paths from enhancement
2. **Search for related functions/types**:
   - Use Grep tool to search for keywords from enhancement:
     - Type names mentioned in proposal
     - Function names mentioned
     - Configuration keys mentioned
   - Search in output mode `"files_with_matches"` to get file list
3. **Read key files** to understand current implementation:
   - Use Read tool with `limit` parameter for large files
   - Identify exact struct definitions, function signatures
   - Note current line numbers for modification points
4. **Find similar existing implementations**:
   - Search for similar features that can serve as examples
   - Identify existing patterns and conventions
5. **Find test files**:
   - Use Glob to find test files: `**/*_test.go`, `test/**/*.go`, etc.
   - Identify test patterns used in the codebase

**Example repository analysis** (from OCPSTRAT-2933):
```bash
# Clone repository
git clone --depth 1 https://github.com/openshift/installer.git

# Find struct definition
grep -n "type VCenter struct" pkg/types/vsphere/platform.go
# Output: line 291

# Find secret creation
grep -n "vsphere-creds" pkg/asset/manifests/vsphere/cluster.go  
# Output: lines 26, 33-34

# Read actual code
cat pkg/types/vsphere/platform.go | sed -n '291,314p'
```

This provides **exact line numbers** for implementation specification.

### Step 5: Create Implementation Specification

Generate a detailed implementation plan:

1. Create spec file path: `.work/sdlc/{jira-key}/implementation-spec.md`
2. Write specification with the following structure:

```markdown
# Implementation Specification: {Feature Summary}

**Jira Issue**: {jira_key}
**Enhancement Proposal**: {enhancement_doc_path}
**Generated**: {current_timestamp}

## Overview

{Brief description of what needs to be implemented based on enhancement}

## Goals

{Copied from enhancement Goals section}

## Non-Goals

{Copied from enhancement Non-Goals section}

## Architecture Decisions

{AI analysis of implementation approach}

### Decision 1: {Decision Title}
- **Rationale**: {Why this approach}
- **Alternatives Considered**: {Other options}
- **Trade-offs**: {Pros/cons}

### Decision 2: {Decision Title}
...

## Implementation Plan

### Phase 1: API Changes

**Files to modify:**
- `{file_path}` - {description of changes}

**Changes:**
1. Add new field `{field_name}` to type `{type_name}`
   - Type: `{field_type}`
   - Purpose: {why needed}
   - Validation: {validation rules}
2. Update CRD schema for `{resource_name}`
   - Add new properties
   - Update documentation

**Code example:**
```go
{example code snippet showing the change}
```

### Phase 2: Vendor Updates (if needed)

**Dependencies to update:**
- `{module_name}` - {version} → {new_version}

**Reason**: {why dependency update is needed}

### Phase 3: Generated Code

**Files to regenerate:**
- Run: `make update-codegen` or equivalent
- Expected changes:
  - `{generated_file_path}` - client code
  - `{generated_file_path}` - CRD manifests

### Phase 4: Operator/Controller Logic

**Files to modify:**
- `{controller_file_path}` - {description}

**Changes:**
1. Implement `{function_name}` function
   - Purpose: {what it does}
   - Inputs: {parameters}
   - Outputs: {return values}
   - Error handling: {approach}
2. Update reconciliation logic in `{reconcile_function}`
   - Add handling for {new condition}
   - Update status reporting

**Code example:**
```go
{example implementation}
```

### Phase 5: CLI Changes (if applicable)

**Files to modify:**
- `{cli_file_path}` - {description}

**Changes:**
1. Add flag `--{flag_name}` to command `{command_name}`
2. Update validation logic
3. Update help text

### Phase 6: Support/Utility Code (if needed)

**Files to modify:**
- `{utility_file_path}` - {description}

**Changes:**
{description of utility changes}

### Phase 7: Tests

**Test files to create/modify:**
- `{test_file_path}` - {description}

**Test cases:**
1. Test `{scenario}`:
   - Setup: {test setup}
   - Action: {what to test}
   - Expected: {expected outcome}
2. Test `{scenario}`:
   ...

**Integration tests** (if applicable):
- {description of integration test approach}

### Phase 8: Documentation

**Files to modify:**
- `docs/{doc_file}` - {description}

**Documentation changes:**
1. Add section on {feature}
2. Update examples
3. Update configuration reference

## Complexity Estimate

**Overall Complexity**: {Low/Medium/High}

**Rationale**: {Why this complexity level}

**Estimated Effort**: {X hours/days}

**Factors Contributing to Complexity**:
- {Factor 1}
- {Factor 2}
- ...

## Risks and Mitigations

{Copied from enhancement, plus any new risks identified during planning}

### Risk 1: {Risk Description}
- **Impact**: {High/Medium/Low}
- **Likelihood**: {High/Medium/Low}
- **Mitigation**: {How to address}

## Verification Strategy

**Build Verification**:
- Run `make lint-fix` to ensure code formatting
- Run `make verify` to check generated code is up to date
- Run `make build` to ensure compilation succeeds

**Test Verification**:
- Run `make test` to execute unit tests
- Run integration tests (if applicable)
- Verify test coverage meets project standards

**Manual Verification** (if needed):
- {Manual test steps}

## Open Questions

{Any unresolved questions that need clarification before implementation}

1. Question: {question}
   - Options: {possible answers}
   - Recommendation: {recommended answer}

## References

- Jira Issue: {jira_url}
- Enhancement Proposal: {enhancement_doc_path}
- Related PRs: {any related PRs found}
- Related Issues: {any related issues}
```

3. Estimate complexity based on:
   - Number of files to modify (< 5 = low, 5-15 = medium, > 15 = high)
   - API changes required (adds complexity)
   - Multiple components affected (adds complexity)
   - Test coverage required
4. Populate `files_to_modify` array with all identified files

### Step 6: Create Detailed Code Analysis (if repos cloned)

If repositories were cloned and analyzed, create an additional implementation analysis document:

1. Create analysis file path: `.work/sdlc/{jira-key}/implementation-analysis.md`

2. Document exact implementation points with:
   - **File paths with line numbers**: `pkg/types/vsphere/platform.go:291-314`
   - **Current code snippets**: Show what exists now
   - **Proposed changes**: Show exact modifications needed
   - **Helper functions**: Complete code for new utility functions
   - **Key findings**: Important discoveries from code analysis

3. Structure:
   ```markdown
   # {Feature} Implementation Analysis
   
   ## Codebase Analysis Summary
   - Repository: {org}/{repo}
   - Files analyzed: {count}
   - Key findings: {discoveries}
   
   ## Key Findings
   1. **{Finding 1}**: {description}
      - File: {path}:{line}
      - Current implementation: {description}
      - Required change: {description}
   
   ## Exact Implementation Points
   
   ### 1. {Modification Category}
   **File**: `{path}`
   **Location**: Line {start}-{end}
   
   **Current code**:
   ```language
   {current code}
   ```
   
   **New code**:
   ```language
   {new code}
   ```
   
   **Explanation**: {why this change}
   
   ## Files Requiring Modification (Summary)
   1. {file} - {description}
   2. {file} - {description}
   
   ## Testing Strategy
   {test approach based on actual codebase patterns}
   ```

4. Update state file:
   ```yaml
   outputs:
     implementation_analysis_path: ".work/sdlc/{jira-key}/implementation-analysis.md"
     codebase_analysis_complete: true
     key_files_identified:
       - "{file}:{lines} ({description})"
   ```

**This document complements the implementation specification** by providing the exact "surgical instructions" for code modification, while the specification provides the broader architectural plan.

### Step 7: User Review (Interactive Mode)

If `metadata.mode == "interactive"`:

1. Display specification summary:
   ```
   ━━━ Phase 2/7: Design & Planning ━━━

   ✓ Analyzed enhancement proposal
   ✓ Searched codebase for related code
   ✓ Created implementation specification

   Specification: .work/sdlc/{jira-key}/implementation-spec.md
   Estimated Complexity: {complexity}
   Files to modify: {count}

   Please review the specification.
   ```

2. Ask user for approval:
   - **Options**: "approve", "edit", "regenerate", "pause"
   - **approve**: Proceed to verification gates
   - **edit**: Provide instructions for manual edits, then ask again
   - **regenerate**: Ask what to change, regenerate spec with feedback, ask again
   - **pause**: Update state and exit for later resumption

3. Record user approval in state:
   ```yaml
   user_approvals:
     - approval_type: "spec_review"
       approved_at: "{timestamp}"
       notes: "{any user notes}"
   ```

If `metadata.mode == "automation"`:
- Skip user review
- Continue to verification automatically

### Step 8: Verify Specification

Run verification gates:

**Gate 1: Spec File Exists**

1. Check if file exists: `.work/sdlc/{jira-key}/implementation-spec.md`
2. Update verification gate:
   ```yaml
   - gate: "spec_exists"
     status: "passed"
     timestamp: "{timestamp}"
   ```

**Gate 2: Spec Contains Implementation Plan**

1. Read spec file
2. Verify it contains "## Implementation Plan" section
3. Verify it has at least one phase/step defined
4. Update verification gate:
   ```yaml
   - gate: "spec_contains_plan"
     status: "passed"
     timestamp: "{timestamp}"
   ```

**Gate 3: User Approval (Interactive Mode Only)**

If `metadata.mode == "interactive"`:
1. Check that user approval was recorded
2. Update verification gate:
   ```yaml
   - gate: "user_approval"
     status: "passed"
     timestamp: "{timestamp}"
   ```

If `metadata.mode == "automation"`:
- Skip this gate (mark as "skipped")

**Gate 4: Complexity Estimated**

1. Verify `estimated_complexity` field is set in outputs
2. Update verification gate:
   ```yaml
   - gate: "complexity_estimated"
     status: "passed"
     timestamp: "{timestamp}"
   ```

**Gate 5: Actual Files Verified (Optional - if repos cloned)**

If repositories were cloned and analyzed:
1. Verify `codebase_analysis_complete` is true
2. Verify `key_files_identified` array is populated
3. Update verification gate:
   ```yaml
   - gate: "actual_files_verified"
     status: "passed"
     timestamp: "{timestamp}"
     notes: "Verified via analysis of cloned repositories"
   ```

If repositories were not cloned:
- Skip this gate (mark as "skipped")

### Step 9: Update State - Phase Complete

1. Read current state
2. Update state with outputs:
   ```yaml
   phases:
     design:
       status: "completed"
       completed_at: "{timestamp}"
       outputs:
         spec_path: ".work/sdlc/{jira-key}/implementation-spec.md"
         estimated_complexity: "{low|medium|high}"
         files_to_modify: [{array of file paths}]
       user_approvals:
         - approval_type: "spec_review"
           approved_at: "{timestamp}"
           notes: ""
       verification_gates: [{gates array}]
   ```
3. Update `resumability.resume_from_phase`: `"implementation"`
4. Write state file

### Step 10: Display Summary

Display completion summary:
```
━━━ Phase 2/7: Design & Planning ━━━ COMPLETE

✓ Implementation specification created
✓ Complexity: {complexity}
✓ Files to modify: {count}
✓ All verification gates passed

Next phase: Implementation
```

## Error Handling

### Enhancement Document Not Found

If Phase 1 didn't complete successfully:

1. Append error:
   ```yaml
   errors:
     - phase: "design"
       error_type: "missing_prerequisite"
       message: "Enhancement document not found. Phase 1 must complete first."
       resolved: false
   ```
2. Update phase status to `"failed"`
3. Exit with error

### Codebase Analysis Fails

If unable to search codebase:

1. Log warning but continue
2. Create spec based on enhancement document only
3. Note in spec: "⚠️ Limited codebase analysis - manual review recommended"
4. Reduce AI confidence in complexity estimate

### User Rejects Specification (Interactive Mode)

If user repeatedly rejects spec:

1. After 3 regeneration attempts:
   - Ask user: "Would you like to manually edit the specification or pause to create it yourself?"
   - If manual edit: Wait for user to confirm edits complete, then verify
   - If pause: Update state and exit

## Success Criteria

Phase 2 is successful when:

- ✅ Implementation specification exists
- ✅ Spec contains detailed implementation plan with phases
- ✅ Complexity estimated
- ✅ Files to modify identified
- ✅ User approval obtained (interactive mode) or AI confidence ≥ 80% (automation mode)
- ✅ All verification gates passed
- ✅ State file updated

**Enhanced success criteria** (when repositories cloned):
- ✅ Required repositories cloned to `.work/sdlc/{jira-key}/repos/`
- ✅ Actual code analyzed with exact file paths and line numbers
- ✅ Implementation analysis document created with code snippets
- ✅ Key files identified with precise modification points

## See Also

- Related Skill: `sdlc-state-yaml` — state schema and operations
- Previous Phase: `phase-enhancement` — generates enhancement proposal
- Next Phase: `phase-implementation` — executes the implementation plan
