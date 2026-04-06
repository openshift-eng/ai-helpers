---
description: Generate OpenShift enhancement proposal markdown from a Jira epic or feature
argument-hint: <issue-key>
---

## Name
jira:generate-enhancement

## Synopsis
```
/jira:generate-enhancement <issue-key>
```

## Description
The `jira:generate-enhancement` command generates an OpenShift enhancement proposal markdown file based on a Jira epic or feature. It fetches the feature details, analyzes the content, and creates a properly formatted enhancement document following the OpenShift enhancement template structure. You can optionally provide additional links (GitHub PRs, related Jira issues, enhancement proposals, documentation) to enrich the generated enhancement with more context.

This command is particularly useful for:
- Converting strategic Jira features or epics into formal enhancement proposals
- Bootstrapping enhancement documents with epic/feature context
- Enriching enhancements with implementation details from GitHub PRs
- Incorporating lessons learned from related bugs and issues
- Maintaining consistency between Jira planning and enhancement documentation
- Accelerating the enhancement proposal writing process

## Key Features

- **Automatic Feature Fetching** - Retrieves feature details from Jira including description, epics, and context
- **Additional Context Links** - Enrich enhancements with GitHub PRs, related Jira issues, documentation, and other enhancement proposals
- **Template-Based Generation** - Creates enhancement markdown following the official OpenShift template
- **Content Mapping** - Intelligently maps Jira feature fields to enhancement sections
- **Epic Integration** - Incorporates linked epics as implementation details
- **Interactive Refinement** - Prompts for missing information and clarifications
- **File Naming** - Generates appropriate filename based on feature summary

## Workflow

The command follows these steps:

### 0. Process Additional Context Links (Optional)
- When `--additional-links` is provided, fetch and analyze additional context
- Extract API changes from GitHub PRs
- Identify risks from related Jira bugs
- Reference related enhancement proposals
- Pull context from documentation links

### 1. Fetch Jira Epic or Feature
- Retrieve epic/feature details using MCP Jira tools or REST API
- Extract summary, description, child issues, components, timeline
- Validate issue type (must be an Epic or Feature issue type)

### 2. Analyze Epic or Feature Content
- Parse description, goals, acceptance criteria
- Identify user stories and objectives
- Extract scope and child issues (epics, stories, tasks)
- Determine topology considerations from components

### 3. Generate Enhancement Sections
- Map Jira content to enhancement template sections
- Create initial draft with available information
- Identify gaps requiring user input

### 4. Interactive Refinement
- Prompt for technical implementation details
- Collect test plan information
- Define graduation criteria
- Gather operational considerations

### 5. Write Enhancement File
- Generate filename from feature summary
- Create markdown file in appropriate directory
- Include all required sections with content or placeholders

### 6. Verify and Sync with PRs (Optional)

When using `--verify` or `--sync-from-prs` flags:

**Verification Mode** (`--verify`):
- Fetch all PRs linked to the epic/feature (from Jira links and GitHub PR descriptions)
- Compare enhancement sections against actual PR implementation
- Generate verification report showing:
  - ✅ Matches: Sections that align with PR implementation
  - ⚠️ Deviations: Changes in approach or scope
  - ❌ Incomplete: Missing implementation or tests
- Recommend whether enhancement needs updating

**Sync Mode** (`--sync-from-prs`):
- Analyze linked PRs for actual implementation details
- Update enhancement sections with real API changes, test coverage, etc.
- Add "Implementation Notes" section documenting deviations from original proposal
- Preserve sections marked with `<!-- MANUAL -->` comments
- Update metadata with sync date and analyzed PR count

**Interactive Mode** (`--interactive`):
- Show diff for each section change
- Prompt for confirmation before applying updates
- Allow selective section updates

## Enhancement Structure Mapping

| Enhancement Section | Primary Source | Additional Context (via --additional-links) |
|---------------------|----------------|---------------------------------------------|
| **Metadata** | Issue key, creation date, authors | See-also from related enhancements |
| **Summary** | Epic/Feature description overview | Context from documentation links |
| **Motivation** | Problem statement from description | Background from related enhancements |
| **User Stories** | Derived from description or child stories | Patterns from related feature requests |
| **Goals** | Epic/Feature objectives and acceptance criteria | — |
| **Non-Goals** | Out of scope items from description | — |
| **API Extensions** | User prompts | **Auto-extracted from GitHub PRs** |
| **Proposal** | Implementation details from child issues | Implementation patterns from PRs |
| **Topology Considerations** | Detected from components (HyperShift, etc.) | — |
| **Risks and Mitigations** | User prompts | **Risks from related Jira bugs** |
| **Test Plan** | User prompts or child issue details | Test patterns from PR test files |
| **Graduation Criteria** | Derived from acceptance criteria | — |
| **Support Procedures** | User prompts | Diagnostic patterns from bugs |

## Usage Examples

1. **Generate enhancement from feature**:
   ```
   /jira:generate-enhancement OCPSTRAT-1596
   ```
   → Fetches feature, generates enhancement proposal

2. **Generate enhancement from epic**:
   ```
   /jira:generate-enhancement HIVE-2589
   ```
   → Fetches epic and child issues, generates enhancement proposal

3. **With custom output directory**:
   ```
   /jira:generate-enhancement CNTRLPLANE-100 --output enhancements/hypershift/
   ```
   → Generates enhancement in specified directory

4. **Verify PRs match enhancement**:
   ```
   /jira:generate-enhancement OCPSTRAT-1596 --verify
   ```
   → Compares enhancement against linked PRs, shows deviations and incomplete items

5. **Update enhancement from actual implementation**:
   ```
   /jira:generate-enhancement OCPSTRAT-1596 --sync-from-prs
   ```
   → Updates enhancement with actual API changes, test coverage, implementation approach

6. **Interactive sync with review**:
   ```
   /jira:generate-enhancement OCPSTRAT-1596 --sync-from-prs --interactive
   ```
   → Shows each change and prompts for confirmation before applying

7. **With additional context links**:
   ```
   /jira:generate-enhancement OCPSTRAT-1596 --additional-links "https://github.com/openshift/api/pull/1234,https://issues.redhat.com/browse/OCPBUGS-5678"
   ```
   → Uses the provided GitHub PR and Jira issue as additional context for generation

8. **With multiple types of context links**:
   ```
   /jira:generate-enhancement HIVE-2589 --additional-links "https://github.com/openshift/api/pull/1234,https://issues.redhat.com/browse/OCPBUGS-5678,https://github.com/openshift/enhancements/blob/master/enhancements/cluster-api/cluster-api-integration.md"
   ```
   → Enriches enhancement with API changes from PR, risks from bug, and references related enhancement

## Arguments

- **$1 – issue-key** *(required)*
  Jira epic or feature key (e.g., `HIVE-2589`, `OCPSTRAT-1596`, `CNTRLPLANE-100`).
  Must be an Epic or Feature issue type.

- **--output** *(optional)*
  Output directory for enhancement file.
  **Default:** `.work/enhancements/`

- **--verify** *(optional)*
  Verify linked PRs match the enhancement proposal.
  Generates a verification report showing matches, deviations, and incomplete items.

- **--sync-from-prs** *(optional)*
  Update the enhancement based on actual PR implementation.
  Analyzes linked PRs and updates enhancement sections with actual implementation details.

- **--interactive** *(optional)*
  Prompt before applying sync changes (use with `--sync-from-prs`).
  Shows a diff and asks for confirmation before updating each section.

- **--preserve-manual** *(optional)*
  Don't overwrite sections marked with `<!-- MANUAL -->` comments.
  **Default:** `true`

- **--repos** *(optional)*
  Comma-separated list of GitHub repos to search for PRs.
  **Default:** `openshift/api,openshift/installer,openshift/machine-api-operator,openshift/cluster-api-provider-aws,openshift/hive`

- **--additional-links** *(optional)*
  Comma-separated list of additional URLs to use as context for generation.
  Supported link types: GitHub PRs, Jira issues, OpenShift documentation, enhancement proposals.
  **Example:** `--additional-links "https://github.com/openshift/api/pull/1234,https://issues.redhat.com/browse/OCPBUGS-5678,https://github.com/openshift/enhancements/blob/master/enhancements/example.md"`

## Return Value

- **Enhancement file path**: Location of created enhancement markdown file
- **Summary**: Overview of generated content and sections requiring attention

## Implementation

This command invokes the `jira:generate-enhancement` skill which provides detailed guidance on:
- Epic and Feature content extraction
- Enhancement template structure
- Content mapping strategies (from both epic and feature formats)
- Child issue integration (stories, tasks, sub-epics)
- Interactive prompting workflows
- File organization best practices

## Error Handling

### Issue Not Found

**Scenario:** Issue key doesn't exist in Jira.

**Action:**
```
Issue CNTRLPLANE-999 not found.

Please verify the issue key and try again.
```

### Wrong Issue Type

**Scenario:** Issue is not an Epic or Feature type.

**Action:**
```
CNTRLPLANE-123 is a Story, not an Epic or Feature.

This command requires an Epic or Feature issue type. Use /jira:generate-enhancement with an Epic or Feature key.
```

### Incomplete Epic or Feature

**Scenario:** Epic/Feature lacks required content sections.

**Action:**
```
Warning: Issue is missing some recommended sections:
- Detailed description
- Acceptance criteria
- Child issues

The enhancement will include placeholders for these sections.
Continue? (yes/no)
```

### MCP Access Error

**Scenario:** Cannot access Jira via MCP.

**Action:**
```
Cannot access Jira. Please ensure:
1. MCP Jira server is configured
2. You have permissions to view CNTRLPLANE project
3. Network connectivity is working

Run: /mcp status
```

## Best Practices

1. **Complete the epic/feature first**: Ensure the Jira epic or feature has comprehensive content before generating the enhancement
2. **Review and refine**: The generated enhancement is a starting point; review and enhance with technical details
3. **Iterate with stakeholders**: Share the draft enhancement for feedback before submitting PR
4. **Keep synchronized**: Regenerate the enhancement as the epic/feature evolves in Jira
5. **Link back to Jira**: The tracking-link metadata will automatically reference the source issue

## File Organization

Enhancement files are created following OpenShift conventions:


The command suggests the appropriate directory based on feature components.

## See Also

- `jira:generate-feature-doc` - Generate feature documentation
- `jira:create` - Create Jira issues
- OpenShift Enhancement Guidelines: https://github.com/openshift/enhancements/tree/master/guidelines

## Skills Reference

This command invokes:
- **generate-enhancement** - Enhancement generation guidance and template mapping

To view skill details:
```bash
cat plugins/jira/skills/generate-enhancement/SKILL.md
```
