---
description: Analyze a JIRA feature enhancement request and generate actionable implementation plan
argument-hint: [JIRA URL]
---

## Name
utils:analyze-feature

## Synopsis
/utils:analyze-feature [JIRA URL]

## Description
The 'utils:analyze-feature' command analyzes a JIRA feature enhancement request and breaks it down into a summary with implementable, realistic, and measurable action items. It fetches the JIRA issue details, analyzes the requirements, identifies technical considerations, and creates a structured implementation plan that can be tracked and executed.

**Feature Enhancement Analyzer**

## Implementation

- The command uses `curl` to fetch JIRA issue data via the JIRA REST API
- Analyzes the feature request description, acceptance criteria, and comments
- Identifies technical requirements and dependencies
- Generates SMART (Specific, Measurable, Achievable, Relevant, Time-bound) action items
- Creates a structured implementation plan with clear milestones

## Process Flow:

1. **JIRA Issue Fetch**: Extract and retrieve JIRA issue details:
   - Parse the JIRA URL to extract issue key (e.g., OCPBUGS-12345)
   - Extract JIRA base URL (e.g., https://issues.redhat.com)
   - Use JIRA REST API to fetch issue data:
     ```bash
     curl -s "{JIRA_BASE_URL}/rest/api/2/issue/{ISSUE_KEY}" | jq '.'
     ```
   - Extract key fields:
     - Summary and description
     - Issue type and priority
     - Acceptance criteria (from description or custom fields)
     - Comments and discussion threads
     - Related issues (blocks, depends on, relates to)
     - Labels and components

2. **Requirement Analysis**: Understand the feature request:
   - Parse the description to identify:
     - Core functionality being requested
     - User stories or use cases
     - Business value and motivation
     - Success criteria
   - Analyze comments for:
     - Clarifications and additional context
     - Technical constraints or preferences
     - Stakeholder concerns
   - Identify scope boundaries:
     - What's explicitly in scope
     - What's explicitly out of scope
     - What needs clarification
   - Extract technical requirements:
     - APIs or interfaces to modify/create
     - Configuration changes needed
     - Documentation requirements
     - Testing requirements

3. **Technical Assessment**: Evaluate implementation feasibility:
   - Search codebase for related functionality:
     - Use Grep to find similar features
     - Identify components that need modification
     - Find existing tests that can be extended
   - Assess technical dependencies:
     - Required libraries or tools
     - External service integrations
     - Platform or version constraints
   - Identify potential risks:
     - Breaking changes
     - Performance implications
     - Security considerations
     - Backward compatibility concerns

4. **Action Item Generation**: Create implementable tasks:
   - Break down the feature into logical phases:
     - **Phase 1: Research & Design**
       - Document current state and gaps
       - Create technical design document
       - Review design with stakeholders
     - **Phase 2: Implementation**
       - Core functionality implementation
       - Configuration and CLI changes
       - Error handling and validation
     - **Phase 3: Testing & Documentation**
       - Unit tests
       - Integration tests
       - End-to-end tests
       - User documentation
       - API documentation
     - **Phase 4: Review & Release**
       - Code review
       - QE validation
       - Release notes
   - For each action item, ensure it is:
     - **Specific**: Clear what needs to be done
     - **Measurable**: Has clear completion criteria
     - **Achievable**: Realistic given constraints
     - **Relevant**: Directly contributes to the feature
     - **Time-bound**: Can be estimated for planning
   - Assign dependencies between action items
   - Identify which items can be parallelized

5. **Implementation Plan Creation**: Generate structured output:
   - Save to `.work/analyze-feature/{ISSUE_KEY}/implementation-plan.md`
   - Include the following sections:
     - **Feature Summary**:
       - JIRA issue key and link
       - Feature title and description
       - Business value and motivation
       - Target users or use cases
     - **Scope**:
       - In scope: What will be delivered
       - Out of scope: What won't be included
       - Open questions: What needs clarification
     - **Technical Overview**:
       - Components affected
       - Dependencies and prerequisites
       - Key technical decisions
       - Risks and mitigation strategies
     - **Action Items** (grouped by phase):
       - Numbered tasks with clear descriptions
       - Acceptance criteria for each task
       - Dependencies (e.g., "Task 3 depends on Task 1")
       - Estimated complexity (Small/Medium/Large)
     - **Success Metrics**:
       - How to measure successful implementation
       - Testing approach
       - Documentation deliverables
     - **Timeline Considerations**:
       - Critical path items
       - Potential blockers
       - Suggested milestones

6. **Output**: Display the implementation plan:
   - Show the file path where the plan was saved
   - Provide a summary of the feature
   - Highlight the number of action items and phases
   - Show any critical dependencies or blockers
   - Ask if the user would like any modifications or clarifications

## Return Value

- **Format**: Markdown file containing the implementation plan
- **Location**: `.work/analyze-feature/{ISSUE_KEY}/implementation-plan.md`
- **Sections**: Feature summary, scope, technical overview, action items, success metrics, timeline considerations

## Examples

1. **Analyze a feature enhancement request**:
   `/utils:analyze-feature https://issues.redhat.com/browse/OCPBUGS-12345`

2. **Analyze a feature with custom JIRA instance**:
   `/utils:analyze-feature https://jira.company.com/browse/FEAT-789`

## Arguments

- $1: JIRA URL (required)
  - Must be a valid JIRA issue URL
  - Examples:
    - `https://issues.redhat.com/browse/OCPBUGS-12345`
    - `https://jira.company.com/browse/FEAT-789`

## Notes

- The command requires network access to fetch JIRA issue data
- For authenticated JIRA instances, the API call may need credentials (handled via browser authentication or JIRA tokens)
- The analysis quality depends on the completeness of the JIRA issue description
- The command will prompt for clarification if critical information is missing from the JIRA issue
- Action items are intentionally kept at a high level to be further broken down during implementation
