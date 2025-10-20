---
description: Process Renovate dependency PR(s) to meet repository contribution standards
argument-hint: <PR_NUMBER|open> [JIRA_PROJECT] [COMPONENT]
---

## Name

utils:process-renovate-pr

## Synopsis

```
/utils:process-renovate-pr <PR_NUMBER|open> [JIRA_PROJECT] [COMPONENT]
```

## Description

The `utils:process-renovate-pr` command automates the processing of Renovate/Konflux dependency update pull requests to meet repository contribution standards. It analyzes dependencies, creates comprehensive Jira tickets, and updates PR titles with proper references.

This command significantly reduces manual PR processing time from approximately 15 minutes to 2 minutes by automating:

- Dependency analysis (direct vs indirect)
- OpenShift version detection from release branches
- Jira ticket creation with comprehensive details
- PR title updates with Jira references
- Testing strategy identification

The command can process either a single PR by number or all open dependency PRs from the Konflux bot.

## Implementation

The command executes the following workflow:

### 1. Validation

- Verifies the PR is from `red-hat-konflux[bot]`
- Checks PR title matches pattern: `chore(deps): update * digest to * (main)`
- Filters out "Pipelines as Code configuration" PRs
- If argument is "open", fetches all open dependency PRs

### 2. Target Version Determination

- Fetches latest state: `git fetch origin`
- Gets commit hash for `origin/main`
- Finds all release branches matching main's commit: `origin/release-*`
- Selects the lowest version number (e.g., if both 4.21 and 4.22 match, uses 4.21)

### 3. Dependency Analysis

From the PR diff (go.mod changes):

**Type Classification:**

- Checks for `// indirect` comment in go.mod
- For indirect: uses `go mod why <package>` to identify parent dependency

**Usage Analysis:**

- Direct dependencies: Searches codebase for import statements
  - Identifies importing files
  - Determines purpose (e.g., "OpenStack image management", "AWS integration")
  - Distinguishes runtime code vs tooling (check hack/tools/)
- Indirect dependencies: Documents parent dependency usage

**Version Changes:**

- Extracts old and new pseudo-versions from go.mod
- Fetches upstream commit messages via GitHub API
- Categorizes as patch/minor/major or digest update

**Testing Strategy:**

- hack/tools dependencies: Identifies Makefile targets
- Runtime dependencies: Suggests component testing

### 4. Jira Ticket Management

- Checks existing PR comments for Jira references
- Creates new ticket if none exists with:
  - **Summary**: `{Package name} ({Brief purpose})`
  - **Type**: Task
  - **Components**: From $3 or default "HyperShift"
  - **Labels**: ["dependencies", "renovate", "ai-generated"] plus context labels
  - **Description**: Comprehensive details including:
    - Dependency information (type, versions, location)
    - Usage in repository
    - Changes in update
    - Step-by-step testing instructions
  - **Target Version**: Sets customfield_12319940 to openshift-X.Y

### 5. PR Title Update

Posts comment with `/retitle` command and processing summary:

```
/retitle [PROJECT-XXXX](https://issues.redhat.com/browse/PROJECT-XXXX): {Package name} ({Brief description})
```

Includes checklist of completed actions and link to Jira ticket.

## Return Value

- **Claude agent text**: Processing status and summary
- **Side effects**:
  - Jira ticket created or referenced
  - PR comment posted with /retitle command
  - Progress updates for multiple PRs

## Examples

1. **Process a single PR**:

   ```
   /utils:process-renovate-pr 7051
   ```

   Output:

   ```
   ✅ Processed PR #7051
   - Dependency: github.com/go-logr/logr
   - Type: Direct
   - Jira: CNTRLPLANE-1234
   - Target Version: openshift-4.21
   - PR title updated with Jira reference
   ```

2. **Process with custom Jira project**:

   ```
   /utils:process-renovate-pr 7051 OCPBUGS
   ```

   Creates ticket in OCPBUGS project instead of default CNTRLPLANE.

3. **Process with custom component**:

   ```
   /utils:process-renovate-pr 7051 CNTRLPLANE "Control Plane Operator"
   ```

   Creates ticket with specified component name.

4. **Process all open dependency PRs**:

   ```
   /utils:process-renovate-pr open
   ```

   Output:

   ```
   Processing 3 dependency PRs...

   [1/3] Processing PR #7051...
   ✅ Completed PR #7051
   - Dependency: github.com/go-logr/logr
   - Jira: CNTRLPLANE-1234

   [2/3] Processing PR #7049...
   ✅ Completed PR #7049
   - Dependency: golang.org/x/net
   - Jira: CNTRLPLANE-1235

   [3/3] Processing PR #7048...
   ✅ Completed PR #7048
   - Dependency: k8s.io/api
   - Jira: CNTRLPLANE-1236

   Summary:
   ✅ Processed 3 PRs successfully
   - Jira project: CNTRLPLANE
   - Component: HyperShift
   - Target Version: openshift-4.21
   ```

5. **Process all open PRs with custom settings**:
   ```
   /utils:process-renovate-pr open OCPBUGS Infrastructure
   ```

## Arguments

- **$1** (required): PR number (e.g., `7051`) or `open` to process all open dependency PRs from Konflux bot
  - When `open`: Automatically fetches and filters dependency PRs, excluding "Pipelines as Code configuration" PRs

- **$2** (optional): Jira project key (default: `CNTRLPLANE`)
  - Examples: `CNTRLPLANE`, `OCPBUGS`, `HOSTEDCP`

- **$3** (optional): Jira component name (default: `HyperShift`)
  - Use quotes for multi-word components: `"Control Plane Operator"`

## Error Handling

The command handles common error cases:

- **PR not from Konflux bot**: Explains requirement and exits
- **Pipeline configuration PR**: Explains this command only handles dependency updates
- **Jira creation failure**: Provides ticket content for manual creation
- **Version field update failure**: Notes it may need manual setting
- **Invalid PR number**: Validates PR exists before processing

## Notes

- Repository name is automatically detected from `git remote -v` (non-fork remote)
- Direct dependencies include file-level usage analysis
- Indirect dependencies focus on dependency chain documentation
- Testing instructions are tailored to dependency type (tooling vs runtime)
- All Jira tickets are labeled with "ai-generated" for tracking
