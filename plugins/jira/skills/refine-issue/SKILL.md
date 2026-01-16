---
name: Refine Jira Issue
description: Implementation guide for refining partially defined stories, tasks, and bugs with complete descriptions and acceptance criteria
---

# Refine Jira Issue

This skill provides implementation guidance for enhancing and refining incomplete or under-specified Jira issues by adding missing critical information while preserving existing good content.

## When to Use This Skill

This skill is automatically invoked by the `/jira:refine` command to guide the refinement process for existing issues.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to edit issues in the target project
- Issue exists and is accessible

## Core Principle: Enhancement, Not Replacement

**CRITICAL:** The refinement process ENHANCES existing content, it does NOT replace or delete it.

**Always:**
- ✅ Preserve existing good content
- ✅ Enhance weak or incomplete sections
- ✅ Add missing required information
- ✅ Maintain original intent and scope

**Never:**
- ❌ Delete or overwrite good existing content
- ❌ Change the fundamental scope or intent
- ❌ Remove user comments or attachments
- ❌ Overwrite carefully crafted sections

## Issue Analysis Framework

### Phase 1: Fetch Current State

Retrieve complete issue details:

```python
issue = mcp__atlassian__jira_get_issue(
    issue_key=issue_key,
    fields="*all"
)
```

Extract key information:
- **Basic fields:** summary, description, issuetype, status, priority
- **Component fields:** components, labels
- **Hierarchy fields:** customfield_12311140 (Epic Link), customfield_12313140 (Parent Link)
- **Version fields:** customfield_12319940 (Target Version)
- **Estimation fields:** customfield_12310243 (Story Points)
- **Assignment:** assignee, reporter

### Phase 2: Quality Assessment

Analyze each aspect of the issue:

#### Summary Quality
**Check for:**
- ✅ Length: 5-15 words (concise but descriptive)
- ✅ Clarity: Action-oriented, clear what needs to be done
- ✅ Keywords: Contains relevant technical terms or components
- ❌ Too vague: "Fix bug", "Update thing"
- ❌ Too long: Full sentences or user stories
- ❌ User story format in summary: "As a... I want..."

**Assessment:**
```python
summary_issues = []
if not summary:
    summary_issues.append("Missing summary")
else:
    if len(summary.split()) < 3:
        summary_issues.append("Too vague")
    if len(summary.split()) > 15:
        summary_issues.append("Too long")
    if summary.lower().startswith("as a"):
        summary_issues.append("User story format in summary (belongs in description)")
```

#### Description Quality (by Issue Type)

**For Stories:**
- ✅ Has "As a... I want... So that..." format
- ✅ Who/What/Why are all present
- ✅ At least 2-3 sentences of context
- ❌ Missing user story format
- ❌ Vague or generic language
- ❌ No explanation of value/benefit

**For Tasks:**
- ✅ Clear description of what needs to be done
- ✅ Context explaining why it's needed
- ✅ Technical details (files, components, approach)
- ❌ Just a title with no body
- ❌ No context or motivation
- ❌ Unclear deliverable

**For Bugs:**
- ✅ Bug template sections present:
  - Description
  - Version
  - How Reproducible
  - Steps to Reproduce
  - Actual Results
  - Expected Results
- ❌ Missing template structure
- ❌ No reproduction steps
- ❌ No expected vs actual

**Assessment:**
```python
description_issues = []

if not description or len(description.strip()) < 100:
    description_issues.append("Too brief")

if issue_type == "Story":
    if "as a" not in description.lower():
        description_issues.append("Missing user story format")
    if "so that" not in description.lower():
        description_issues.append("Missing value statement")

if issue_type == "Bug":
    required_sections = ["reproduce", "actual", "expected"]
    for section in required_sections:
        if section not in description.lower():
            description_issues.append(f"Missing '{section}' section")
```

#### Acceptance Criteria Quality

**Check for:**
- ✅ AC section exists (h2. Acceptance Criteria or similar)
- ✅ At least 3-5 specific criteria
- ✅ Testable and observable criteria
- ✅ Appropriate format (Test that... / Given-When-Then)
- ❌ No AC section
- ❌ Vague criteria ("works well", "is fast")
- ❌ Implementation details instead of behavior
- ❌ Too few (< 2) or too many (> 10)

**Assessment:**
```python
ac_issues = []

has_ac_section = "acceptance criteria" in description.lower() or "ac:" in description.lower()
if not has_ac_section:
    ac_issues.append("No acceptance criteria section")
else:
    # Count bullet points in AC section
    ac_section = extract_section(description, "acceptance criteria")
    ac_count = ac_section.count("*") + ac_section.count("-") + ac_section.count("#")

    if ac_count < 2:
        ac_issues.append(f"Too few criteria ({ac_count})")
    elif ac_count > 10:
        ac_issues.append(f"Too many criteria ({ac_count}) - consider splitting")

    # Check for vague language
    vague_terms = ["works", "good", "well", "properly", "correctly"]
    if any(term in ac_section.lower() for term in vague_terms):
        ac_issues.append("Contains vague criteria")
```

#### Field Completeness

**Check for:**
- Priority: Is it set? Appropriate for the work?
- Component: Is it set? Matches the work?
- Target Version: Required for epics/features?
- Story Points: Set for stories/tasks ready for sprint?
- Epic Link: Should this be linked to an epic?
- Labels: Appropriate labels applied?

**Assessment:**
```python
field_issues = []

if not priority or priority["name"] == "Undefined":
    field_issues.append("Priority not set")

if not components or len(components) == 0:
    if project_requires_component(project_key):
        field_issues.append("Component required but not set")

if issue_type in ["Story", "Task"]:
    if not story_points and status in ["Backlog", "To Do"]:
        field_issues.append("Story points not estimated")

if not epic_link and could_have_epic(summary, description):
    field_issues.append("May need epic link")
```

### Phase 3: Generate Refinement Plan

Based on analysis, create a prioritized refinement plan:

```python
refinement_plan = {
    "critical": [],  # Must fix before issue is usable
    "important": [],  # Should fix for quality
    "optional": []   # Nice to have
}

# Critical: Makes issue unusable
if "No acceptance criteria" in ac_issues:
    refinement_plan["critical"].append("Add acceptance criteria")

if issue_type == "Story" and "Missing user story format" in description_issues:
    refinement_plan["critical"].append("Add user story format to description")

if "Priority not set" in field_issues:
    refinement_plan["critical"].append("Set priority")

# Important: Improves quality significantly
if "Too brief" in description_issues:
    refinement_plan["important"].append("Expand description with context")

if "Component required but not set" in field_issues:
    refinement_plan["important"].append("Set component")

if "Story points not estimated" in field_issues:
    refinement_plan["important"].append("Estimate story points")

# Optional: Enhances but not required
if "May need epic link" in field_issues:
    refinement_plan["optional"].append("Link to parent epic")
```

## Refinement Execution Strategies

### Strategy 1: Description Enhancement

**For Stories:**

If missing user story format, construct it from existing content:

```python
def enhance_story_description(summary, existing_description):
    """
    Enhance story description with proper user story format.
    Preserves existing content while adding structure.
    """
    # Try to extract components from summary/description
    who = infer_user_from_context(summary, existing_description)
    what = extract_action_from_summary(summary)
    why = infer_value_from_context(summary, existing_description)

    # Build enhanced description
    enhanced = f"""As a {who}, I want to {what}, so that {why}.

h2. Background

{existing_description if existing_description else ""}

h2. Acceptance Criteria

* Test that {generate_criteria_from_summary(summary)}
"""

    return enhanced
```

**Example transformation:**

**Before:**
```
Summary: Add metrics endpoint
Description: Need to expose cluster health metrics
```

**After:**
```
Summary: Add metrics endpoint for cluster health
Description:
As a cluster administrator, I want to query cluster health metrics via an API endpoint, so that I can monitor cluster status programmatically.

h2. Background

Need to expose cluster health metrics to enable monitoring integration.

h2. Acceptance Criteria

* Test that /metrics endpoint returns cluster health status
* Test that metrics include CPU, memory, and disk utilization
* Verify that endpoint requires authentication
* Verify that metrics are updated every 30 seconds
```

**For Tasks:**

Structure technical work clearly:

```python
def enhance_task_description(summary, existing_description):
    """
    Enhance task description with clear structure.
    """
    what = extract_deliverable_from_summary(summary)
    why = infer_motivation_from_context(summary, existing_description)

    enhanced = f"""h2. Task Description

{what}

h2. Motivation

{why}

{f"h2. Context\n\n{existing_description}" if existing_description else ""}

h2. Definition of Done

* {generate_done_criteria(summary)}
"""

    return enhanced
```

**For Bugs:**

Add bug template structure:

```python
def enhance_bug_description(summary, existing_description):
    """
    Enhance bug description with standard template.
    """
    enhanced = f"""h2. Description

{existing_description if existing_description else extract_problem_from_summary(summary)}

h2. Version-Release number of selected component

{infer_version_from_labels_or_ask()}

h2. How reproducible

{ask_reproducibility() or "To be determined"}

h2. Steps to Reproduce

1. {generate_initial_steps_from_summary(summary)}

h2. Actual results

{extract_actual_from_description(existing_description) or "To be documented"}

h2. Expected results

{infer_expected_from_summary(summary) or "To be documented"}

h2. Additional info

Logs, screenshots, or other relevant information.
"""

    return enhanced
```

### Strategy 2: Acceptance Criteria Generation

Generate testable, specific acceptance criteria based on the summary and description:

```python
def generate_acceptance_criteria(summary, description, issue_type):
    """
    Generate acceptance criteria based on issue context.
    Returns list of criteria strings.
    """
    criteria = []

    # Extract key actions/features from summary
    actions = extract_verbs_and_objects(summary)

    if issue_type == "Story":
        # Generate user behavior criteria
        for action in actions:
            criteria.append(f"Test that users can {action}")

        # Add validation criteria
        criteria.append("Verify that validation prevents invalid input")

        # Add edge cases
        criteria.append("Verify that appropriate errors are shown for edge cases")

    elif issue_type == "Task":
        # Generate completion criteria
        deliverables = extract_deliverables_from_description(description)
        for deliverable in deliverables:
            criteria.append(f"Verify that {deliverable} is complete")

        # Add quality criteria
        criteria.append("Code review completed and approved")
        criteria.append("Tests added/updated and passing")

    elif issue_type == "Bug":
        # Generate fix verification criteria
        criteria.append("Verify that reproduction steps no longer produce the error")
        criteria.append("Verify that fix doesn't introduce regressions")
        criteria.append("Verify that error handling is appropriate")

    return criteria
```

**Quality guidelines for generated AC:**
- ✅ Observable behavior (what user/system does)
- ✅ Testable (can be verified)
- ✅ Specific (no vague terms like "works well")
- ✅ Complete (covers happy path and edge cases)
- ❌ Implementation details (how code works internally)
- ❌ Vague language ("should be fast", "looks good")

### Strategy 3: Field Assignment

Set missing fields with intelligent defaults:

#### Priority Assignment

```python
def suggest_priority(summary, description, issue_type):
    """
    Suggest priority based on keywords and context.
    """
    urgent_keywords = ["critical", "urgent", "blocker", "security", "data loss", "crash"]
    high_keywords = ["important", "user-facing", "regression", "performance"]

    text = f"{summary} {description}".lower()

    if any(kw in text for kw in urgent_keywords):
        return "Critical"
    elif any(kw in text for kw in high_keywords):
        return "Major"
    elif issue_type == "Bug":
        return "Normal"  # Default for bugs
    else:
        return "Normal"  # Default for enhancements
```

#### Component Detection

```python
def detect_component(summary, description, project_key):
    """
    Detect component from keywords in summary/description.
    """
    component_keywords = {
        "HyperShift / ROSA": ["rosa", "aws", "hypershift"],
        "HyperShift / ARO": ["aro", "azure", "hypershift"],
        "HyperShift": ["hosted control plane", "hcp", "management cluster"],
        "Networking": ["network", "ingress", "route", "dns"],
        "Storage": ["storage", "pvc", "volume", "csi"],
        "API": ["api", "rest", "endpoint", "controller"],
        "CLI": ["cli", "command line", "rosa cli", "oc"],
    }

    text = f"{summary} {description}".lower()

    for component, keywords in component_keywords.items():
        if any(kw in text for kw in keywords):
            return component

    return None  # Prompt user if cannot detect
```

#### Story Point Estimation

```python
def estimate_story_points(summary, description, issue_type):
    """
    Estimate story points based on complexity indicators.
    """
    # Complexity indicators
    complexity_score = 0

    # Multiple components/systems involved
    if summary.count("and") > 1 or description.count("integration") > 0:
        complexity_score += 2

    # New functionality vs enhancement
    if "new" in summary.lower() or "implement" in summary.lower():
        complexity_score += 1

    # External dependencies
    if "upstream" in description.lower() or "api" in description.lower():
        complexity_score += 1

    # UI work
    if "ui" in description.lower() or "frontend" in description.lower():
        complexity_score += 1

    # Map to Fibonacci
    if complexity_score == 0:
        return 1  # Trivial
    elif complexity_score == 1:
        return 2  # Simple
    elif complexity_score == 2:
        return 3  # Medium
    elif complexity_score == 3:
        return 5  # Complex
    else:
        return 8  # Very complex
```

## Interactive Refinement Workflow

### Step 1: Present Refinement Plan

```
Analyzing PROJ-123...

Current State:
  Issue Type: Story
  Status: Backlog
  Summary: Add metrics endpoint

Issues Found:
  Critical:
    ❌ Missing user story format in description
    ❌ No acceptance criteria
    ❌ Priority not set

  Important:
    ⚠️  Description too brief (only 1 sentence)
    ⚠️  Component not set
    ⚠️  Story points not estimated

  Optional:
    💡 Could be linked to epic PROJ-100 (Observability)

Refinement Plan:
  1. Add user story format (As a... I want... So that...)
  2. Generate 5 acceptance criteria based on summary
  3. Set priority to Normal (default for new features)
  4. Expand description with context
  5. Set component to "Monitoring" (detected from keywords)
  6. Estimate at 3 story points (medium complexity)
  7. Link to epic PROJ-100

Proceed with refinement? (yes/no/modify)
```

### Step 2: Collect Missing Information

If information cannot be inferred, prompt user:

```
I need a bit more information to complete the refinement:

1. Who is the primary user of this feature?
   Options: cluster admin, developer, SRE, end user
   > cluster admin

2. What is the main value this provides?
   > to monitor cluster status programmatically

3. Should this be linked to epic PROJ-100 (Observability)?
   > yes

Great! Generating refined content...
```

### Step 3: Show Preview Before Applying

```
Preview of changes to PROJ-123:

=== Summary ===
No changes (already good)

=== Description ===
BEFORE:
  Need to expose cluster health metrics

AFTER:
  As a cluster administrator, I want to query cluster health metrics via an API endpoint, so that I can monitor cluster status programmatically.

  h2. Background

  Need to expose cluster health metrics to enable monitoring integration.

  h2. Acceptance Criteria

  * Test that /metrics endpoint returns cluster health status
  * Test that metrics include CPU, memory, and disk utilization
  * Verify that endpoint requires authentication
  * Verify that metrics are updated every 30 seconds
  * Demonstrate that metrics can be queried via curl

=== Fields ===
  Priority: Undefined → Normal
  Component: (none) → Monitoring
  Story Points: (none) → 3
  Epic Link: (none) → PROJ-100

Apply these changes? (yes/no/edit)
```

### Step 4: Apply Updates

```python
# Build update payload
update_fields = {}
update_additional = {}

# Description (if enhanced)
if enhanced_description != original_description:
    update_fields["description"] = enhanced_description

# Priority (if changed)
if suggested_priority and suggested_priority != current_priority:
    update_fields["priority"] = {"name": suggested_priority}

# Component (if added)
if suggested_component and not current_components:
    update_fields["components"] = [{"name": suggested_component}]

# Story points (if estimated)
if story_points and not current_story_points:
    update_additional["customfield_12310243"] = story_points

# Epic link (if added)
if epic_key and not current_epic_link:
    update_additional["customfield_12311140"] = epic_key

# Add refined label
current_labels = issue.get("labels", [])
if "refined-by-ai" not in current_labels:
    update_additional["labels"] = current_labels + ["refined-by-ai"]

# Apply update
mcp__atlassian__jira_update_issue(
    issue_key=issue_key,
    fields=update_fields,
    additional_fields=update_additional
)
```

### Step 5: Report Results

```
✅ Successfully refined PROJ-123

Changes Applied:
  ✓ Enhanced description with user story format
  ✓ Added 5 specific acceptance criteria
  ✓ Set priority to Normal
  ✓ Set component to Monitoring
  ✓ Estimated at 3 story points
  ✓ Linked to epic PROJ-100

The issue is now ready for sprint planning.

View updated issue: https://issues.redhat.com/browse/PROJ-123
```

## Preservation Guidelines

**Always preserve:**
- ✅ Existing comments and discussions
- ✅ Attachments and linked artifacts
- ✅ Work logs and time tracking
- ✅ Issue history and audit trail
- ✅ Well-written sections of description
- ✅ User-provided context and rationale
- ✅ Existing good acceptance criteria (enhance, don't replace)

**Safe to enhance/replace:**
- ✅ Stub descriptions ("TBD", "TODO", < 50 chars)
- ✅ Auto-generated boilerplate from bots
- ✅ Missing acceptance criteria sections
- ✅ Undefined/unset fields
- ✅ Vague single-sentence descriptions

**Approach for mixed content:**
- If description has both good and weak sections, preserve good and enhance weak
- Use h2 sections to add structure without losing existing content
- Append acceptance criteria section rather than replacing entire description

## Error Handling

### Cannot Infer User Story Components

**Scenario:** For a story, cannot determine Who/What/Why from existing content.

**Action:**
```
I need help understanding this story better to add the user story format:

Current summary: "Update configuration"
Current description: "Config needs updating"

1. Who will benefit from this update?
   (e.g., cluster admin, developer, SRE)

2. What specifically needs to be updated?
   (e.g., add new setting, change default value)

3. Why is this update needed?
   (e.g., to support new feature, fix issue, improve performance)
```

### Component Cannot Be Detected

**Scenario:** Cannot auto-detect component from keywords.

**Action:**
```
I couldn't automatically detect the component for this issue.

Available components for PROJECT:
  1. Frontend
  2. Backend
  3. API
  4. Infrastructure
  5. Documentation

Which component best fits this work? (1-5 or type component name)
```

### Issue Type Mismatch

**Scenario:** Content suggests different issue type than current.

**Action:**
```
This issue is currently a Task, but the description suggests user-facing functionality
which is typically a Story.

Would you like to:
  1. Keep as Task (technical work, no user story needed)
  2. Convert to Story (will add user story format)
  3. Review and decide

Selection (1-3):
```

### Already Well-Defined

**Scenario:** Issue already meets quality bar.

**Action:**
```
PROJ-123 analysis:
  ✓ Complete description with user story format
  ✓ 6 specific acceptance criteria
  ✓ All required fields set
  ✓ Story points estimated

This issue is already well-defined. Refinement options:
  1. Skip (no changes needed)
  2. Review anyway (may find minor improvements)
  3. Add additional context/notes

What would you like to do? (1-3)
```

## Best Practices Summary

1. **Analyze first** - Understand current state before making changes
2. **Enhance, don't replace** - Preserve good existing content
3. **Be specific** - Generate concrete, testable acceptance criteria
4. **Maintain intent** - Don't change scope or direction
5. **Interactive** - Involve user when information is ambiguous
6. **Preview** - Show changes before applying
7. **Quality over quantity** - Better to have 4 great criteria than 10 vague ones
8. **Context matters** - Use project/team conventions when available

## Anti-Patterns to Avoid

❌ **Deleting user-written content**
```python
description = auto_generated_template  # Overwrites everything!
```
✅ Preserve and enhance:
```python
description = f"{existing_description}\n\nh2. Acceptance Criteria\n\n{generated_ac}"
```

❌ **Generic acceptance criteria**
```
* Test that it works
* Verify good performance
```
✅ Specific and testable:
```
* Test that API response time is < 200ms for 95% of requests
* Verify that the endpoint handles 1000 concurrent requests without errors
```

❌ **Changing the scope**
```
Original: "Add metrics endpoint"
Refined: "Add metrics endpoint, dashboard UI, and alerting system"
```
✅ Enhance within original scope:
```
Original: "Add metrics endpoint"
Refined: Add clear user story and AC for the metrics endpoint only
```

❌ **Ignoring existing structure**
```python
description = new_template  # Loses existing h2 sections and formatting
```
✅ Work with existing structure:
```python
if "h2. Acceptance Criteria" not in description:
    description += "\n\nh2. Acceptance Criteria\n\n" + generated_ac
```

## Workflow Summary

1. 📋 Fetch issue via MCP (get all fields)
2. 🔍 Analyze quality (summary, description, AC, fields)
3. 📊 Generate refinement plan (critical/important/optional)
4. 💬 Interactive enhancement (fill gaps, enhance weak areas)
5. 👁️ Preview changes (show before/after)
6. ✅ Apply updates via MCP (preserve existing content)
7. 📤 Report results (summarize changes)

## See Also

- `/jira:refine` - Main command documentation
- `create-story` skill - Story creation best practices
- `create-task` skill - Task creation best practices
- `create-bug` skill - Bug report templates
