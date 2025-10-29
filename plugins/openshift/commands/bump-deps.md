---
description: Bump dependencies in OpenShift projects with automated analysis and PR creation
argument-hint: <dependency> [version] [--create-jira] [--create-pr]
---

## Name

openshift:bump-deps

## Synopsis

```
/openshift:bump-deps <dependency> [version] [--create-jira] [--create-pr]
```

## Description

The `openshift:bump-deps` command automates the process of bumping dependencies in OpenShift organization projects. It analyzes the dependency, determines the appropriate version to bump to, updates the necessary files (go.mod, go.sum, package.json, etc.), runs tests, and optionally creates Jira tickets and pull requests.

This command significantly reduces the manual effort required for dependency updates by automating:

- Dependency version discovery and analysis
- Compatibility checking with current codebase
- File updates (go.mod, package.json, Dockerfile, etc.)
- Test execution to verify the update
- Jira ticket creation with comprehensive details
- Pull request creation with proper formatting
- Release notes generation

The command intelligently handles different dependency types (Go modules, npm packages, container images, etc.) and can process single or multiple dependencies at once.

## Implementation

The command executes the following workflow:

### 1. Repository Analysis

- Detects repository type (Go, Node.js, Python, etc.)
- Identifies dependency management files (go.mod, package.json, requirements.txt, etc.)
- Determines current project structure and conventions
- Checks for existing CI/CD configuration

### 2. Dependency Discovery

**For Go Projects:**
- Parses go.mod to find current version
- Uses `go list -m -versions <module>` to list available versions
- Checks for major version compatibility (v0, v1, v2+)
- Identifies if dependency is direct or indirect

**For Node.js Projects:**
- Parses package.json for current version
- Uses npm/yarn to find latest versions
- Checks semantic versioning constraints
- Identifies devDependencies vs dependencies

**For Container Images:**
- Parses Dockerfile and related files
- Checks registry for available tags
- Verifies image digest and signatures
- Identifies base images and tool images

**For Python Projects:**
- Parses requirements.txt or pyproject.toml
- Uses pip to find available versions
- Checks for version constraints

### 3. Version Selection

If no version is specified:
- Suggests latest stable version
- Considers semantic versioning (patch, minor, major)
- Checks for breaking changes in release notes
- Validates against project's minimum version requirements

If version is specified:
- Validates version exists
- Checks compatibility with current project version
- Warns about major version jumps

### 4. Impact Analysis

- Searches codebase for usage of the dependency
- Identifies files importing/using the dependency
- Analyzes API changes between versions
- Checks for deprecated features being used
- Reviews upstream changelog and release notes
- Identifies potential breaking changes

### 5. File Updates

**Go Projects:**
- Updates go.mod with new version
- Runs `go mod tidy` to update go.sum
- Runs `go mod vendor` if vendor directory exists
- Updates any version constraints in comments

**Node.js Projects:**
- Updates package.json
- Runs `npm install` or `yarn install`
- Updates package-lock.json or yarn.lock

**Container Images:**
- Updates Dockerfile(s)
- Updates related manifests (kubernetes, etc.)
- Updates any CI configuration using the image

**Python Projects:**
- Updates requirements.txt or pyproject.toml
- Generates new lock file if applicable

### 6. Testing Strategy

- Identifies relevant test suites
- Runs unit tests: `make test` or equivalent
- Runs integration tests if available
- Runs e2e tests for critical dependencies
- Checks for test failures and analyzes logs
- Verifies build succeeds: `make build`

### 7. Jira Ticket Creation (if --create-jira)

Creates a Jira ticket with:
- **Summary**: `Bump {dependency} from {old_version} to {new_version}`
- **Type**: Task or Bug (if security update)
- **Components**: Auto-detected from repository
- **Labels**: ["dependencies", "automated-update", "ai-generated"]
  - Adds "security" if CVE-related
  - Adds "breaking-change" if major version bump
- **Description**: Includes:
  - Dependency information and type
  - Current and new versions
  - Changelog summary
  - Breaking changes (if any)
  - Files modified
  - Test results
  - Migration steps (if needed)
  - Links to upstream release notes
- **Target Version**: Auto-detected from release branches

### 8. Pull Request Creation (if --create-pr)

Creates a pull request with:
- **Title**: `[{JIRA-ID}] Bump {dependency} from {old_version} to {new_version}`
- **Body**: Includes:
  - Link to Jira ticket
  - Summary of changes
  - Breaking changes callout
  - Testing performed
  - Checklist for reviewers
  - Release notes snippet
- **Labels**: Auto-applied based on change type
- **Branch naming**: `deps/{dependency}-{new_version}` or `{jira-id}-bump-{dependency}`

### 9. Conflict Resolution

If updates cause issues:
- Identifies conflicting dependencies
- Suggests resolution strategies
- Can attempt automatic resolution for common cases
- Provides manual resolution steps for complex scenarios

## Return Value

- **Claude agent text**: Processing status, test results, and summary
- **Side effects**:
  - Modified dependency files (go.mod, package.json, etc.)
  - Updated lock files
  - Jira ticket created (if --create-jira)
  - Pull request created (if --create-pr)
  - Git branch created with changes

## Examples

1. **Bump a Go dependency to latest**:

   ```
   /openshift:bump-deps k8s.io/api
   ```

   Output:

   ```
   Analyzing dependency: k8s.io/api
   Current version: v0.28.0
   Latest version: v0.29.1

   Checking compatibility...
   ✅ No breaking changes detected

   Updating go.mod...
   Running go mod tidy...

   Running tests...
   ✅ All tests passed

   Summary:
   - Dependency: k8s.io/api
   - Old version: v0.28.0
   - New version: v0.29.1
   - Files modified: go.mod, go.sum
   - Tests: ✅ Passed

   Changes are ready. Use --create-pr to create a pull request.
   ```

2. **Bump to a specific version with Jira ticket**:

   ```
   /openshift:bump-deps golang.org/x/net v0.20.0 --create-jira
   ```

   Output:

   ```
   Analyzing dependency: golang.org/x/net
   Current version: v0.19.0
   Target version: v0.20.0

   Reviewing changes...
   ⚠️  Breaking changes detected in v0.20.0:
   - http2: Server.IdleTimeout applies to idle h2 connections

   Updating go.mod...
   Running tests...
   ✅ All tests passed

   Creating Jira ticket...
   ✅ Created: OCPBUGS-12345

   Summary:
   - Jira: https://issues.redhat.com/browse/OCPBUGS-12345
   - Dependency: golang.org/x/net
   - Version: v0.19.0 → v0.20.0
   - Breaking changes: Yes
   ```

3. **Bump and create PR in one step**:

   ```
   /openshift:bump-deps github.com/spf13/cobra --create-jira --create-pr
   ```

   Output:

   ```
   Processing dependency bump for github.com/spf13/cobra...

   [1/7] Analyzing dependency...
   Current: v1.7.0
   Latest: v1.8.0

   [2/7] Checking changelog...
   Changes include:
   - New features: Enhanced shell completion
   - Bug fixes: 5 issues resolved
   - No breaking changes

   [3/7] Updating files...
   ✅ go.mod updated
   ✅ go.sum updated

   [4/7] Running tests...
   ✅ Unit tests: 156/156 passed
   ✅ Integration tests: 23/23 passed

   [5/7] Creating Jira ticket...
   ✅ Created: OCPBUGS-12346

   [6/7] Creating git branch...
   ✅ Branch: OCPBUGS-12346-bump-cobra

   [7/7] Creating pull request...
   ✅ PR created: #1234

   Summary:
   - Jira: https://issues.redhat.com/browse/OCPBUGS-12346
   - PR: https://github.com/openshift/repo/pull/1234
   - Dependency: github.com/spf13/cobra
   - Version: v1.7.0 → v1.8.0
   - Tests: All passed

   Next steps:
   1. Review the PR at the link above
   2. Address any reviewer comments
   3. Merge when approved
   ```

4. **Bump multiple related dependencies**:

   ```
   /openshift:bump-deps "k8s.io/*"
   ```

   Output:

   ```
   Found 8 Kubernetes dependencies to update:

   [1/8] k8s.io/api: v0.28.0 → v0.29.1
   [2/8] k8s.io/apimachinery: v0.28.0 → v0.29.1
   [3/8] k8s.io/client-go: v0.28.0 → v0.29.1
   [4/8] k8s.io/kubectl: v0.28.0 → v0.29.1
   ...

   These should be updated together to maintain compatibility.
   Proceed with batch update? [y/N]
   ```

5. **Bump a container base image**:

   ```
   /openshift:bump-deps registry.access.redhat.com/ubi9/ubi-minimal
   ```

   Output:

   ```
   Analyzing container image: ubi9/ubi-minimal
   Current: 9.3-1361
   Latest: 9.4-1194

   Checking for security updates...
   ✅ 3 CVEs fixed in new version

   Updating Dockerfile...
   Building test image...
   Running container tests...
   ✅ All tests passed

   Files modified:
   - Dockerfile
   - .github/workflows/build.yml
   ```

## Arguments

- **$1** (required): Dependency identifier
  - Go module: `github.com/org/repo` or `golang.org/x/net`
  - npm package: `@types/node` or `react`
  - Container image: `registry.access.redhat.com/ubi9/ubi-minimal`
  - Wildcard for batch: `k8s.io/*` (requires confirmation)

- **$2** (optional): Target version
  - Semantic version: `v1.2.3`, `1.2.3`
  - Version range: `^1.2.0`, `~1.2.0`
  - Special: `latest`, `latest-stable`
  - If omitted: suggests latest stable version

- **--create-jira** (flag): Create a Jira ticket for the update
  - Auto-detects project from repository
  - Can be configured with JIRA_PROJECT env var
  - Ticket includes full change analysis

- **--create-pr** (flag): Create a pull request with the changes
  - Implies creating a git branch
  - Includes --create-jira automatically
  - PR is created as draft if tests fail

- **--jira-project** (option): Specify Jira project (default: auto-detect)
  - Example: `--jira-project OCPBUGS`

- **--component** (option): Specify Jira component (default: auto-detect)
  - Example: `--component "Control Plane"`

- **--branch** (option): Specify git branch name (default: auto-generate)
  - Example: `--branch feature/update-deps`

- **--skip-tests** (flag): Skip running tests (not recommended)
  - Use only for non-critical updates
  - PR will be marked as draft

- **--force** (flag): Force update even if tests fail
  - Creates PR as draft
  - Includes test failure details in PR

## Error Handling

The command handles common error cases:

- **Dependency not found**: Lists similar dependencies in project
- **Version not found**: Shows available versions
- **Test failures**:
  - Provides detailed error logs
  - Suggests potential fixes
  - Asks whether to create draft PR anyway
- **Conflicting dependencies**:
  - Identifies conflicts
  - Suggests resolution order
  - Can attempt batch update
- **Breaking changes**:
  - Highlights breaking changes
  - Links to migration guides
  - Requires explicit confirmation for major bumps
- **Network failures**: Retries with exponential backoff
- **Permission errors**: Checks git/GitHub authentication

## Notes

- Repository name and organization are auto-detected from `git remote -v`
- For Go dependencies, supports both versioned (v2+) and unversioned modules
- Automatically detects if running in a fork vs upstream repository
- Respects `.gitignore` and doesn't commit generated/vendored files unnecessarily
- Can handle dependencies with replace directives in go.mod
- Supports monorepos with multiple go.mod files
- All Jira tickets are labeled with "ai-generated" for tracking
- PR creation requires GitHub CLI (gh) to be installed and authenticated
- For security updates (CVEs), automatically prioritizes and labels appropriately
- Compatible with Renovate - can be used to customize/enhance Renovate PRs

## Environment Variables

- **JIRA_PROJECT**: Default Jira project for ticket creation
- **JIRA_COMPONENT**: Default component for Jira tickets
- **GITHUB_TOKEN**: GitHub authentication (if not using gh auth)
- **DEFAULT_BRANCH**: Override default branch detection (default: main)

## See Also

- `utils:process-renovate-pr` - Process existing Renovate dependency PRs
- `git:create-pr` - General PR creation command
- `jira:create` - Manual Jira ticket creation
