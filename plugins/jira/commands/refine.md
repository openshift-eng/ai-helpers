---
description: Refine partially defined JIRA issues with complete descriptions and acceptance criteria
argument-hint: <issue-key> [<issue-key>...]
---

## Name
jira:refine

## Synopsis
```bash
/jira:refine <issue-key> [<issue-key>...]
```

## Description
The `jira:refine` command enhances partially defined or under-specified Jira issues by adding missing critical information such as complete descriptions, well-formed user stories, comprehensive acceptance criteria, and proper field values.

This command is particularly useful for:
- Backlog grooming sessions where issues need refinement before sprint planning
- Converting stub tickets created by bots or automation into actionable work items
- Enhancing issues created quickly without full details
- Ensuring stories follow proper user story format (As a... I want... So that...)
- Adding missing acceptance criteria to make issues testable
- Validating and improving issue quality before implementation

## Key Features

- **Smart Analysis** - Analyzes existing issue content to understand intent and context
- **User Story Formatting** - Converts vague descriptions into proper "As a... I want... So that..." format for stories
- **Acceptance Criteria Generation** - Adds comprehensive, testable acceptance criteria
- **Field Completion** - Suggests and sets missing required fields (component, version, priority)
- **Issue Type Detection** - Recognizes whether incomplete work should be a story, task, or bug
- **Context Preservation** - Retains existing good content while enhancing weak areas
- **Incremental Refinement** - Can be run multiple times to progressively improve quality
- **Security Validation** - Scans additions for credentials and secrets

## Issue Analysis Phase

The refinement process begins with comprehensive analysis:

### Content Analysis
- **Summary quality** - Is it concise, descriptive, action-oriented?
- **Description completeness** - Does it explain what needs to be done and why?
- **User story format** - For stories, is the "As a... I want... So that..." format present?
- **Acceptance criteria** - Are they present, testable, and comprehensive?
- **Context sufficiency** - Is there enough information for implementation?

### Field Analysis
- **Component** - Is component set? Does it match the work described?
- **Priority** - Is priority defined?
- **Target Version** - Is version set if required?
- **Story Points** - For stories/tasks, are story points estimated?
- **Labels** - Are appropriate labels applied?
- **Parent/Epic Link** - Is the issue properly linked in the hierarchy?

### Issue Type Validation
Verify the issue type matches the work:
- **Story** - User-facing functionality? Has acceptance criteria?
- **Task** - Technical work? Clear deliverable?
- **Bug** - Has reproduction steps? Expected vs actual results?
- **Epic** - Body of work? Has objective and scope?

## Implementation

The `jira:refine` command runs in multiple phases:

### 🎯 Phase 1: Load Refinement Guidance

Invoke the `refine-issue` skill using the Skill tool to load refinement best practices and workflows.

### 📊 Phase 2: Fetch & Analyze Current State

Use MCP tools to retrieve the issue and analyze its current state:

```python
# Fetch full issue details
issue = mcp__atlassian__jira_get_issue(
    issue_key="<issue-key>",
    fields="*all"  # Get all fields including custom fields
)

# Extract for analysis:
# - summary
# - description
# - issuetype
# - status
# - priority
# - components
# - customfield_12319940 (Target Version)
# - customfield_12310243 (Story Points)
# - customfield_12311140 (Epic Link)
# - customfield_12313140 (Parent Link)
# - labels
# - assignee
```

Analyze what's missing or weak:
- ❌ No description or < 100 characters
- ❌ Story without "As a... I want... So that..." format
- ❌ No acceptance criteria section
- ❌ Acceptance criteria too vague (< 2 specific criteria)
- ❌ Missing component (when required)
- ❌ Undefined priority
- ❌ No story points (for stories/tasks ready for sprint)
- ❌ Summary is too vague or too long

### 💡 Phase 3: Generate Refinement Plan

Create a refinement plan based on analysis:

```text
Refinement Plan for <ISSUE-KEY>
================================

Issue Type: Story
Current State: Partially defined
Missing/Weak Areas:
  1. Description lacks user story format
  2. No acceptance criteria
  3. Component not set
  4. Priority undefined
  5. No story points

Proposed Changes:
  1. Rewrite description in user story format
  2. Add 4-5 acceptance criteria based on summary
  3. Set component to "Frontend" (detected from summary keywords)
  4. Set priority to "Normal" (default for new features)
  5. Estimate at 5 story points (medium complexity)

Would you like to proceed with these changes? (yes/no/modify)
```

### 🔄 Phase 4: Interactive Refinement

Guide the user through refinement based on issue type:

#### For Stories:

1. **User Story Format**
   - Extract or collect: Who (user), What (action), Why (value)
   - Format: "As a \<user\>, I want to \<action\>, so that \<value\>."
   - Preserve existing good content, enhance weak parts

2. **Acceptance Criteria**
   - Generate 4-6 testable criteria based on summary and description
   - Use appropriate format (Test that... / Given-When-Then)
   - Ask user to review and refine

3. **Additional Context**
   - Add sections: Dependencies, Out of Scope, Technical Notes (if needed)

#### For Tasks:

1. **Task Description**
   - What needs to be done (clear deliverable)
   - Why it's needed (context/motivation)
   - How it fits into larger work (if applicable)

2. **Acceptance Criteria**
   - Definition of done
   - Verification steps
   - Success criteria

3. **Technical Details**
   - Files/components affected
   - Approach or constraints
   - References to related work

#### For Bugs:

1. **Bug Template**
   - Description of problem
   - Version/Release number
   - How reproducible
   - Steps to Reproduce
   - Actual results
   - Expected results
   - Additional info (logs, screenshots)

2. **Validation**
   - Ensure all template sections are filled
   - Verify reproduction steps are clear

#### For All Types:

1. **Component Assignment**
   - Auto-detect from keywords or existing component
   - Prompt if cannot determine
   - Validate component exists in project

2. **Priority Setting**
   - Suggest priority based on keywords (urgent, critical, etc.)
   - Use Normal as default if unclear
   - Ask user to confirm

3. **Story Point Estimation** (Stories/Tasks)
   - Analyze complexity indicators
   - Suggest sizing (1, 2, 3, 5, 8, 13)
   - Explain reasoning
   - Ask user to confirm or adjust

4. **Epic/Parent Linking**
   - Search for related epics based on keywords
   - Suggest parent link if found
   - Ask user to confirm or specify different parent

### 🔒 Phase 5: Security Validation

Scan all proposed additions for sensitive data:
- API keys, passwords, tokens
- Kubeconfigs, certificates
- Cloud credentials
- URLs with embedded credentials

If detected:
- STOP update
- Inform user of issue type
- Ask for redaction
- Provide placeholder guidance

### ✅ Phase 6: Apply Updates via MCP

Build update payload and apply changes:

```python
# Update issue with refined content
mcp__atlassian__jira_update_issue(
    issue_key="<issue-key>",
    fields={
        "description": "<refined description with proper format>",
        "priority": {"name": "<priority>"},
        "components": [{"name": "<component>"}] if component else None
    },
    additional_fields={
        "customfield_12310243": <story-points> if applicable,
        "customfield_12311140": "<epic-key>" if epic link needed,
        "labels": <existing-labels> + ["refined-by-ai"] if not present
    }
)
```

**Update strategy:**
- **Append** to existing good content (don't overwrite)
- **Enhance** weak sections (improve quality)
- **Add** missing sections (AC, context)
- **Preserve** user-created content (comments, attachments, work logs)

### 📤 Phase 7: Return Result

Display refinement summary:

```text
Refined: PROJECT-1234
Title: <issue summary>
URL: <issue URL>

Changes Applied:
  ✓ Added user story format to description
  ✓ Added 5 acceptance criteria
  ✓ Set component: Frontend
  ✓ Set priority: Normal
  ✓ Estimated: 5 story points
  ✓ Linked to epic: PROJECT-100

The issue is now ready for sprint planning.
```

## Usage Examples

1. **Refine a stub story**:
   ```bash
   /jira:refine MYPROJECT-123
   ```
   → Analyzes issue, adds user story format, acceptance criteria, and missing fields

2. **Refine auto-generated task**:
   ```bash
   /jira:refine SPLAT-2575
   ```
   → Expands description, adds clear deliverables, sets priority and story points

3. **Refine incomplete bug**:
   ```bash
   /jira:refine OCPBUGS-12345
   ```
   → Adds bug template structure, ensures reproduction steps are complete

4. **Batch refinement** (multiple issues):
   ```bash
   /jira:refine MYPROJECT-100 MYPROJECT-101 MYPROJECT-102
   ```
   → Refines each issue in sequence, maintaining consistency

## Arguments

- **$1 – issue-key** *(required)*
  Jira issue key to refine (e.g., `CNTRLPLANE-123`, `OCPBUGS-456`)

- **$2, $3, ... – additional-keys** *(optional)*
  Additional issue keys to refine in batch mode

## Return Value

- **Issue Key**: The refined Jira issue identifier
- **Issue URL**: Direct link to the updated issue
- **Changes Summary**: List of fields updated and content added
- **Refinement Status**: Ready for sprint / Needs more info / etc.

## Refinement Quality Indicators

After refinement, the issue should meet these quality bars:

### For Stories:
- ✅ Summary is concise (5-10 words)
- ✅ Description has "As a... I want... So that..." format
- ✅ At least 3-5 specific, testable acceptance criteria
- ✅ Component assigned
- ✅ Priority set
- ✅ Story points estimated (if ready for sprint)
- ✅ Linked to parent epic (if part of larger work)

### For Tasks:
- ✅ Clear description of what needs to be done
- ✅ Context explaining why it's needed
- ✅ Definition of done / acceptance criteria
- ✅ Component assigned
- ✅ Priority set
- ✅ Story points estimated (if ready for sprint)

### For Bugs:
- ✅ All bug template sections filled
- ✅ Clear reproduction steps
- ✅ Expected vs actual results defined
- ✅ Version/release specified
- ✅ Priority reflects severity
- ✅ Component assigned

## Error Handling

### Issue Not Found

**Scenario:** Issue key doesn't exist.

**Action:**
```text
Issue MYPROJECT-999 not found.

Please verify the issue key and try again.
Example: /jira:refine MYPROJECT-123
```

### Issue Already Well-Defined

**Scenario:** Issue already has complete description, AC, and all fields.

**Action:**
```text
MYPROJECT-123 appears to be well-defined already:
  ✓ Complete description
  ✓ Acceptance criteria present (5 criteria)
  ✓ All required fields set
  ✓ Story points estimated

No refinement needed. Would you like to:
1. Review and improve anyway
2. Skip this issue
3. Cancel
```

### Conflicting Information

**Scenario:** Summary suggests Story but issue type is Task.

**Action:**
```text
The summary "Enable user dashboard" suggests user-facing functionality,
but this is currently a Task.

Should this be converted to a Story instead? (yes/no/keep-as-task)
```

### Missing Permissions

**Scenario:** User cannot edit the issue.

**Action:**
```text
You don't have permission to edit MYPROJECT-123.

This may be because:
- Issue is in a status that prevents edits
- You're not assigned to this project
- Issue is closed/resolved

Contact your project admin for access.
```

### Security Validation Failure

**Scenario:** Proposed content contains secrets.

**Action:**
```text
I detected what appears to be an API token in the generated content.

Before proceeding, please review this section:
<show relevant section>

Use placeholder values like YOUR_API_KEY or <redacted>.

Would you like me to:
1. Automatically redact and proceed
2. Let you edit manually
3. Cancel refinement
```

## Best Practices

1. **Refine before sprint planning** - Ensure issues are ready for estimation
2. **Use for bot-created issues** - Enhance automated stub tickets
3. **Batch refine related work** - Maintain consistency across related issues
4. **Preserve intent** - Enhance, don't completely rewrite existing content
5. **Involve stakeholders** - Review refined content with product owners
6. **Iterate** - Run multiple times to progressively improve quality

## Anti-Patterns to Avoid

❌ **Over-refinement**
```text
Adding 20 acceptance criteria and pages of context
```
✅ Keep it right-sized for a sprint (3-7 AC typically sufficient)

❌ **Changing the intent**
```text
Issue was about API performance, refined to add a UI
```
✅ Enhance the existing scope, don't expand or change it

❌ **Removing user content**
```text
Deleting comments or attachments added by team
```
✅ Only update description and fields, preserve discussions

❌ **Generic acceptance criteria**
```text
- Test that it works
- Verify functionality
```
✅ Be specific: "Test that API response time is < 200ms"

## Workflow Summary

1. 📋 Fetch issue details via MCP
2. 🔍 Analyze current state (description, AC, fields)
3. 📝 Identify missing/weak areas
4. 💡 Generate refinement plan
5. 💬 Interactive enhancement (user story, AC, fields)
6. 🔒 Security validation
7. ✅ Apply updates via MCP
8. 📤 Return refinement summary

## See Also

- `jira:create` - Create new well-formed issues
- `jira:grooming` - Generate grooming meeting agendas
- `jira:backlog` - Find suitable backlog tickets
- `jira:solve` - Analyze and solve Jira issues

## Skills Reference

This command automatically invokes the following skill:

- **refine-issue** - Issue refinement guidance and workflows

To view skill details:
```bash
cat plugins/jira/skills/refine-issue/SKILL.md
```
