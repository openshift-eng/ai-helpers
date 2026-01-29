---
description: Automate OpenShift Tests Extension (OTE) migration for component repositories
argument-hint: ""
---

## Name
ote-migration:migrate

## Synopsis
```bash
/ote-migration:migrate
```bash

## Description
The `ote-migration:migrate` command automates the migration of component repositories to use the openshift-tests-extension (OTE) framework. It guides users through the entire migration process, from collecting configuration information to generating all necessary boilerplate code, copying test files, and setting up the build infrastructure.

## Implementation
The command implements an interactive 8-phase migration workflow:
1. **Cleanup** - Prepare the environment
2. **User Input Collection** - Gather all configuration (extension name, directory strategy, repository paths, test subfolders)
3. **Repository Setup** - Clone/update source (openshift-tests-private) and target repositories
4. **Structure Creation** - Create directory layout (supports both monorepo and single-module strategies)
5. **Code Generation** - Generate main.go, Makefile, go.mod, fixtures.go, and bindata configuration
6. **Test Migration** - Automatically replace FixturePath calls, update imports, and add OTP/Level0 annotations
7. **Dependency Resolution** - Run go mod tidy, vendor dependencies, and verify build
8. **Documentation** - Generate comprehensive migration summary with next steps

See the detailed workflow below for step-by-step implementation instructions.

## Context

The openshift-tests-extension framework allows external repositories to contribute tests to openshift-tests' suites. This migration process will:

1. Collect all necessary configuration information
2. Set up the repository structure
3. Clone/update source and target repositories
4. Copy test files and testdata to customizable destinations
5. Generate all necessary boilerplate code
6. Apply test filtering (only tests with `[sig-<extension-name>]` tag)
7. Add tracking annotations ([OTP] for all ported tests, [Level0] for Level0 tests)
8. Apply environment selectors and platform filters
9. Set up test suites and registrations

**Important:**
- The generated code will filter tests to only include those with `[sig-<extension-name>]` in their test names, ensuring only component-specific tests are registered.
- All ported tests will be annotated with `[OTP]` at the Describe block level for tracking purposes.
- Describe blocks containing at least one test with "-LEVEL0-" in its name will be annotated with `[Level0]` (placed after `[OTP]`) for future conformance suite integration.

## Migration Workflow

### Phase 1: User Input Collection (up to 10 inputs, some conditional)

Collect all necessary information from the user before starting the migration.

**CRITICAL INSTRUCTION FOR AI AGENT:**
- **Extension name (Input 1)**: AUTO-DETECT from git remote or directory name - do NOT ask user
- **Sig filter tags (Input 2)**: MUST ask user explicitly - do NOT auto-detect or infer
- **All other inputs**: Ask user explicitly using AskUserQuestion tool or direct prompts
- **WAIT for user response** before proceeding to the next input or phase

**Important Notes:**
- Source repository is always `git@github.com:openshift/openshift-tests-private.git`
- Variables collected (shown as `<variable-name>`) will be used throughout the migration:
  - `<extension-name>` - Extension name (auto-detected from Input 1)
  - `<sig-filter-tags>` - Comma-separated sig tags for test filtering (from Input 2)
  - `<structure-strategy>` - "monorepo" or "single-module" (from Input 3)
  - `<working-dir>` - Working directory path (from Input 4)
  - `<test-dir-name>` - Test directory name, defaults to "e2e" (from Input 5a, monorepo only)
  - All file paths and code templates use these variables

#### Input 1: Extension Name (Auto-detected)

**Auto-detect the extension name from the repository or directory context:**

```bash
# Try to detect from git remote URL first
if [ -d .git ]; then
    # Discover actual remote names first (don't assume 'origin')
    FIRST_REMOTE=$(git remote | head -1)
    if [ -n "$FIRST_REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$FIRST_REMOTE" 2>/dev/null)
        if [ -n "$REMOTE_URL" ]; then
            # Extract repo name from URL (e.g., git@github.com:openshift/router.git -> router)
            EXTENSION_NAME=$(echo "$REMOTE_URL" | sed 's/.*\/\([^/]*\)\.git$/\1/' | sed 's/.*\/\([^/]*\)$/\1/')
        fi
    fi
fi

# Fallback to directory name if git detection fails
if [ -z "$EXTENSION_NAME" ]; then
    EXTENSION_NAME=$(basename "$PWD")
fi

echo "Detected extension name: $EXTENSION_NAME"
```bash

**This extension name will be used for:**
- Binary name: `<extension-name>-tests-ext`
- Module paths and directory structure
- Suite name: `openshift/<extension-name>/tests`

**Store in variable:** `<extension-name>`

#### Input 2: Sig Filter Tags

**IMPORTANT:** The sig filter tags control which tests are included in the generated binary. The binary will filter tests by searching for these tags in test names.

**Why sig filter tags matter:**

The generated `main.go` includes filtering logic that searches for tests containing the specified sig tags:

```go
// Filter to only include component-specific tests
var filteredSpecs []*et.ExtensionTestSpec
allSpecs.Walk(func(spec *et.ExtensionTestSpec) {
    // Check if test name contains any of the specified sig tags
    if strings.Contains(spec.Name, "[sig-router]") ||
       strings.Contains(spec.Name, "[sig-network-edge]") {
        filteredSpecs = append(filteredSpecs, spec)
    }
})
```

**Without correct sig filter tags:**
- `./bin/<extension-name>-tests-ext list` will show 0 tests (or wrong tests)
- Your component tests won't be registered with the OTE framework
- The binary won't be able to discover or run your tests

**With correct sig filter tags:**
- `./bin/<extension-name>-tests-ext list` shows only your component's tests
- Tests are properly filtered from the 5000+ upstream Kubernetes tests
- Binary correctly discovers and runs component-specific tests

**To find your sig tags:**
```bash
# Search your test files for sig tags
grep -r "g\.Describe" test/extended/<your-subfolder>/ --include="*.go" | grep -o '\[sig-[^]]*\]' | sort -u

# Example output:
# [sig-network-edge]
# [sig-router]
```bash

**Ask the user for sig filter tags:**

Question: "What sig tag(s) should be used to filter tests? (e.g., 'router' for [sig-router], or 'router,network-edge' for multiple tags. This will be used in main.go to filter test names when running './bin/<extension-name>-tests-ext list')"
- Provide a text input field for the user to enter sig tag(s)
- User can enter single tag: `router`
- User can enter multiple tags separated by comma: `router,network-edge`
- Tags should be entered without the `[sig-` prefix and `]` suffix

**Wait for user to provide the sig filter tags. Do not proceed until the user has provided this input.**

**User provides the sig filter tags:**
- Single tag example: `router` → will filter for `[sig-router]`
- Multiple tags example: `router,network-edge` → will filter for `[sig-router]` OR `[sig-network-edge]`

**Store in variable:** `<sig-filter-tags>`

#### Input 3: Directory Structure Strategy

Ask: "Which directory structure strategy do you want to use?"

**Option 1: Monorepo strategy (integrate into existing repo)**
- Integrates into existing repository structure
- Uses existing `cmd/` and `test/` directories
- Files created:
  - `cmd/extension/main.go` - Extension binary
  - `test/e2e/*.go` - Test files (regular package in main module)
  - `test/testdata/` - Test data (regular package in main module)
  - **NO test/e2e/go.mod** - All code in one module
- Root `go.mod` updated with OTE dependency and replace directive
- Best for: Component repos with existing `cmd/` and `test/` structure

**Option 2: Single-module strategy (isolated directory)**
- Creates isolated `tests-extension/` directory
- Self-contained with single `go.mod`
- Files created:
  - `tests-extension/cmd/main.go`
  - `tests-extension/test/e2e/*.go`
  - `tests-extension/test/testdata/`
  - `tests-extension/go.mod`
- No changes to existing repo structure
- Best for: Standalone test extensions or repos without existing test structure

User selects: **1** or **2**

Store the selection in variable: `<structure-strategy>` (value: "monorepo" or "single-module")

#### Input 4: Working Directory (Workspace)

Ask: "What is the working directory path for migration workspace?"

**For both strategies**:
- This is the workspace directory for migration operations
- Used for cloning openshift-tests-private (if needed)
- Used for temporary migration operations
- Example: `/home/user/workspace`, `/tmp/migration-workspace`

**User provides the path:**
- Can provide an existing directory path
- Can provide a new directory path (we'll create it)
- Path can be absolute or relative

**Store in variable:** `<working-dir>`

**Note**: This is NOT where files will be created. The target repository path will be collected separately.

#### Input 5: Test Directory Name (conditional - monorepo strategy only)

**Skip this input if single-module strategy** - single-module uses `tests-extension/test/e2e`

**For monorepo strategy only:**

**Note**: This input is collected AFTER Input 9b (target repo validation) so we can check the target repository structure.

Check if the default test directory already exists:

```bash
cd <target-repo-path>

# Check if test/e2e already exists
if [ -d "test/e2e" ]; then
    echo "⚠️  Warning: test/e2e directory already exists in the target repository"
    TEST_DIR_EXISTS=true
else
    TEST_DIR_EXISTS=false
fi
```bash

**If test/e2e exists:**
Ask: "The directory 'test/e2e' already exists. Please specify a subdirectory name under test/e2e/ (default: 'extension'):"
- User can provide a custom name or press Enter for default "extension"
- Example: "extension", "ote", "openshift-tests"
- Default: "extension"
- This will be used as a **subfolder**: `test/e2e/<subdirectory-name>/`
- Store in variable: `<test-dir-name>` = "e2e/<subdirectory-name>" (e.g., "e2e/extension")

**If test/e2e does not exist:**
- Use default: `test/e2e`
- Store in variable: `<test-dir-name>` = "e2e"

**Important:** Throughout the rest of the migration, use `test/<test-dir-name>` instead of hardcoded `test/e2e`

**Examples:**
- If test/e2e doesn't exist: `test/e2e/` (standard layout)
- If test/e2e exists and user accepts default: `test/e2e/extension/`
- If test/e2e exists and user specifies "ote": `test/e2e/ote/`

#### Input 6: Local Source Repository (Optional)

Ask: "Do you have a local clone of openshift-tests-private? If yes, provide the path (or press Enter to clone it):"
- If provided: Use this existing local repository
- If empty: Will clone `git@github.com:openshift/openshift-tests-private.git`
- Example: `/home/user/repos/openshift-tests-private`

#### Input 7: Update Local Source Repository (if local source provided)

If a local source repository path was provided:
Ask: "Do you want to update the local source repository? (git fetch && git pull) [Y/n]:"
- Default: Yes
- If yes: Run `git fetch && git pull` in the local repo
- If no: Use current state

#### Input 8: Source Test Subfolder

Ask: "What is the test subfolder name under test/extended/?"
- Example: "networking", "router", "storage", "templates"
- This will be used as: `test/extended/<subfolder>/`
- Leave empty to use all of `test/extended/`

#### Input 9: Source Testdata Subfolder (Optional)

Ask: "What is the testdata subfolder name under test/extended/testdata/? (or press Enter to use same as test subfolder)"
- Default: Same as Input 7 (test subfolder)
- Example: "networking", "router", etc.
- This will be used as: `test/extended/testdata/<subfolder>/`
- Enter "none" if no testdata exists

#### Input 9a: Target Repository Path (monorepo only)

**Skip this input if single-module strategy.**

**For monorepo strategy only:**
Ask: "What is the path to your component repository (target repo) where OTE integration will be added?"
- This is the repository where `cmd/extension/`, `test/e2e/`, etc. will be created
- Can be absolute path: `/home/user/repos/router`
- Can be relative path: `~/openshift/cloud-credential-operator`
- Example: `/home/user/repos/router`, `/home/user/openshift/sdn`

**User provides the path:**
- Must be an existing directory
- Should be a git repository (will be validated in next input)

**Store in variable:** `<target-repo-path>` (for monorepo)

#### Input 9b: Validate Target Repository Git Status (monorepo only)

**Skip this input if single-module strategy.**

**For monorepo strategy only:**
If the target repository path was provided in Input 9a:
1. First, check if it's a git repository (has `.git` directory)
2. If it IS a git repository, run `git status` and verify it's clean
3. If there are uncommitted changes, ask user to commit or stash them first
4. If it is NOT a git repository, show warning and continue

#### Input 10: Local Target Repository (Optional - single-module only)

**Skip this input if monorepo strategy** - target repo was already collected in Input 9a.

**For single-module strategy only:**
Ask: "Do you have a local clone of the target repository? If yes, provide the path (or press Enter to clone from URL):"
- If provided: Use this existing local repository
  - Can be absolute path: `/home/user/repos/sdn`
  - Can be relative path: `../sdn`
  - Can be current directory: `.`
- If empty: Will ask for URL to clone (Input 10)
- After providing a path, you will be asked in Input 11 if you want to update it

#### Input 10b: Target Repository URL (if no local target provided and single-module)

**Skip this input if monorepo strategy.**

**For single-module strategy only:**
If no local target repository was provided in Input 10:
Ask: "What is the Git URL of the target repository (component repository)?"
- Example: `git@github.com:openshift/sdn.git`
- This is where the OTE integration will be added

#### Input 11: Update Local Target Repository (if local target provided and single-module)

**Skip this input if monorepo strategy.**

**For single-module strategy only:**
**IMPORTANT:** This input is REQUIRED when Input 9 provided a local path.

If a local target repository path was provided in Input 9:
1. First, check if the path is a git repository (has `.git` directory)
2. If it IS a git repository, ask:
   "Do you want to update the local target repository? (git fetch && git pull) [Y/n]:"
   - Default: Yes
   - User can answer: Y (yes) or N (no)
3. If it is NOT a git repository, skip this question and show warning

**Examples:**
- User provided: `/home/user/repos/sdn` → Ask this question
- User provided: `.` (current directory) → Ask this question if it's a git repo
- User pressed Enter in Input 9 → Skip this question (will clone instead)

**Action:**
- If yes: Discover the remote and update
  ```bash
  cd <target-path>
  TARGET_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
  git fetch "$TARGET_REMOTE"
  git pull "$TARGET_REMOTE" "$(git branch --show-current)"
```bash
- If no: Use current state without updating

**Display all collected inputs** for user confirmation:

**For Monorepo Strategy:**
```
Migration Configuration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extension: <extension-name>
Strategy: Multi-module (integrate into existing repo)
Working Directory (workspace): <working-dir>
Target Repository: <target-repo-path>

Source Repository (openshift-tests-private):
  URL: git@github.com:openshift/openshift-tests-private.git
  Local Path: <local-source-path> (or "Will clone to <working-dir>/repos/")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Destination Structure (in target repo):
  Extension Binary: cmd/extension/main.go
  Test Files: test/<test-dir-name>/*.go (separate module)
  Testdata: test/<flattened-test-dir-name>-testdata/ (regular package in main module)
  Root go.mod: Will be updated with replace directive for test/<test-dir-name>

Note: <test-dir-name> examples:
  - "e2e" → testdata at test/e2e-testdata/ (standard layout)
  - "e2e/extension" → testdata at test/e2e-extension-testdata/ (nested path flattened)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```bash

**For Single-Module Strategy:**
```makefile
Migration Configuration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extension: <extension-name>
Strategy: Single-module (isolated directory)
Working Directory (workspace): <working-dir>

Source Repository (openshift-tests-private):
  URL: git@github.com:openshift/openshift-tests-private.git
  Local Path: <local-source-path> (or "Will clone to <working-dir>/repos/")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Target Repository:
  Local Path: <local-target-path> (or "Will clone to <working-dir>/repos/target")
  URL: <target-repo-url> (if cloning)

Destination Structure (in target repo):
  Extension Binary: tests-extension/cmd/main.go
  Test Files: tests-extension/test/e2e/*.go
  Testdata: tests-extension/test/testdata/
  Module: tests-extension/go.mod (single module)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Ask for confirmation before proceeding.

#### Phase 1 Validation Checkpoint (CRITICAL - DO NOT SKIP)

**MANDATORY VALIDATION BEFORE PROCEEDING TO PHASE 2:**

This checkpoint prevents incomplete input collection that causes files to be created in wrong locations.

**For ALL strategies (monorepo and single-module):**

1. **Verify extension name was detected:**
   ```bash
   if [ -z "$EXTENSION_NAME" ]; then
       echo "❌ ERROR: Extension name not detected"
       echo "Required: Auto-detect from git remote or directory name"
       exit 1
   fi
   ```

2. **Verify sig filter tags were provided:**
   ```bash
   if [ -z "$SIG_FILTER_TAGS" ]; then
       echo "❌ ERROR: Sig filter tags not provided"
       echo "Required: User must specify sig tag(s) for test filtering"
       echo "Example: router,network-edge"
       exit 1
   fi
   ```

3. **Verify strategy was selected:**
   ```bash
   if [ -z "$STRUCTURE_STRATEGY" ]; then
       echo "❌ ERROR: Directory structure strategy not selected"
       echo "Required: Choose 'monorepo' or 'single-module'"
       exit 1
   fi
   ```

4. **Verify working directory was provided:**
   ```bash
   if [ -z "$WORKING_DIR" ]; then
       echo "❌ ERROR: Working directory not provided"
       echo "Required: Specify working directory path"
       exit 1
   fi
   ```

**For monorepo strategy:**

5. **Verify target repository path was collected:**
   ```bash
   if [ "$STRUCTURE_STRATEGY" = "monorepo" ]; then
       if [ -z "$TARGET_REPO_PATH" ]; then
           echo "❌ ERROR: Target repository path not provided for monorepo strategy"
           echo "Required: Specify target repository path (Input 9a)"
           echo "Example: /home/user/repos/router"
           exit 1
       fi

       echo "✅ Target repository path provided: $TARGET_REPO_PATH"
   fi
   ```

**For single-module strategy:**

6. **Verify target repository information was collected:**
   ```bash
   if [ "$STRUCTURE_STRATEGY" = "single-module" ]; then
       if [ -z "$TARGET_REPO_PATH" ] && [ -z "$TARGET_REPO_URL" ]; then
           echo "❌ ERROR: Target repository information missing for single-module strategy"
           echo ""
           echo "For single-module strategy, you must provide EITHER:"
           echo "  1. Local target repository path (Input 10), OR"
           echo "  2. Target repository Git URL (Input 10b)"
           echo ""
           echo "Without this, files will be created in the wrong location."
           echo "Please restart migration and provide target repository information."
           exit 1
       fi

       if [ -n "$TARGET_REPO_PATH" ]; then
           echo "✅ Target repository path provided: $TARGET_REPO_PATH"
       else
           echo "✅ Target repository URL provided: $TARGET_REPO_URL"
       fi
   fi
   ```

**Checkpoint Summary:**

```bash
echo ""
echo "========================================="
echo "Phase 1 Validation Complete"
echo "========================================="
echo "✅ Extension name: $EXTENSION_NAME"
echo "✅ Sig filter tags: $SIG_FILTER_TAGS"
echo "✅ Strategy: $STRUCTURE_STRATEGY"
echo "✅ Working directory (workspace): $WORKING_DIR"

# Show target repository for both strategies
if [ "$STRUCTURE_STRATEGY" = "monorepo" ]; then
    echo "✅ Target repository: $TARGET_REPO_PATH"
elif [ "$STRUCTURE_STRATEGY" = "single-module" ]; then
    if [ -n "$TARGET_REPO_PATH" ]; then
        echo "✅ Target repository: $TARGET_REPO_PATH (local)"
    else
        echo "✅ Target repository: $TARGET_REPO_URL (will clone)"
    fi
fi

echo ""
echo "All required inputs collected - proceeding to Phase 2"
echo "========================================="
```

### Phase 2: Repository Setup (2 steps)

#### Step 1: Setup Source Repository

**Hardcoded Source:** `git@github.com:openshift/openshift-tests-private.git`

Two scenarios:

**A) If user provided local source repository path:**
```bash
cd <working-dir>
mkdir -p repos

# Use the local repo path directly
SOURCE_REPO="<local-source-path>"

# Update if user requested
if [ "<update-source>" = "yes" ]; then
    echo "Updating openshift-tests-private repository..."
    cd "$SOURCE_REPO"

    # Check current branch and checkout to main/master if needed
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
        echo "Repository is currently on branch '$CURRENT_BRANCH'"

        # Try to checkout main first, fall back to master
        if git show-ref --verify --quiet refs/heads/main; then
            echo "Checking out main branch..."
            git checkout main
            TARGET_BRANCH="main"
        elif git show-ref --verify --quiet refs/heads/master; then
            echo "Checking out master branch..."
            git checkout master
            TARGET_BRANCH="master"
        else
            echo "Error: Neither 'main' nor 'master' branch exists"
            cd - > /dev/null
            exit 1
        fi
    else
        TARGET_BRANCH="$CURRENT_BRANCH"
    fi

    echo "On branch $TARGET_BRANCH, updating..."
    # Discover remote name (don't assume 'origin')
    SOURCE_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
    if [ -z "$SOURCE_REMOTE" ]; then
        echo "Error: No git remote found"
        cd - > /dev/null
        exit 1
    fi
    git fetch "$SOURCE_REMOTE"
    git pull "$SOURCE_REMOTE" "$TARGET_BRANCH"
    cd - > /dev/null
fi
```

**B) If no local source repository (need to clone):**
```bash
cd <working-dir>
mkdir -p repos

# Check if we already have a remote configured for openshift-tests-private
if [ -d "repos/openshift-tests-private" ]; then
    cd repos/openshift-tests-private
    SOURCE_REMOTE=$(git remote -v | grep 'openshift/openshift-tests-private' | head -1 | awk '{print $1}')

    if [ -n "$SOURCE_REMOTE" ]; then
        echo "Updating openshift-tests-private from remote: $SOURCE_REMOTE"
        git fetch "$SOURCE_REMOTE"
        git pull "$SOURCE_REMOTE" master || git pull "$SOURCE_REMOTE" main
    else
        echo "No remote found for openshift-tests-private, adding upstream..."
        SOURCE_REMOTE="upstream"
        git remote add "$SOURCE_REMOTE" git@github.com:openshift/openshift-tests-private.git
        git fetch "$SOURCE_REMOTE"
        git pull "$SOURCE_REMOTE" master || git pull "$SOURCE_REMOTE" main
    fi
    cd ../..
    SOURCE_REPO="repos/openshift-tests-private"
else
    echo "Cloning openshift-tests-private repository..."
    git clone git@github.com:openshift/openshift-tests-private.git repos/openshift-tests-private
    SOURCE_REPO="repos/openshift-tests-private"
fi
```bash

**Set source paths based on subfolder inputs:**
```bash
# Set full source paths
if [ -z "<test-subfolder>" ]; then
    SOURCE_TEST_PATH="$SOURCE_REPO/test/extended"
else
    SOURCE_TEST_PATH="$SOURCE_REPO/test/extended/<test-subfolder>"
fi

if [ "<testdata-subfolder>" = "none" ]; then
    SOURCE_TESTDATA_PATH=""
elif [ -z "<testdata-subfolder>" ]; then
    SOURCE_TESTDATA_PATH="$SOURCE_REPO/test/extended/testdata"
else
    SOURCE_TESTDATA_PATH="$SOURCE_REPO/test/extended/testdata/<testdata-subfolder>"
fi
```bash

#### Step 2: Setup Target Repository

**For Monorepo Strategy:**
```bash
# Use the target repository path from Input 9a
TARGET_REPO="<target-repo-path>"
echo "Using target repository at: $TARGET_REPO"

# Validate target repository exists
if [ ! -d "$TARGET_REPO" ]; then
    echo "❌ ERROR: Target repository does not exist at: $TARGET_REPO"
    exit 1
fi

# Extract module name from go.mod if it exists
if [ -f "$TARGET_REPO/go.mod" ]; then
    MODULE_NAME=$(grep '^module ' "$TARGET_REPO/go.mod" | awk '{print $2}')
    echo "Found existing module: $MODULE_NAME"
else
    echo "Warning: No go.mod found in target repository"
    echo "Will create test/go.mod for test dependencies"
fi

# Switch working directory to target repository for file creation
echo "Switching working directory to target repository..."
cd "$TARGET_REPO"
WORKING_DIR="$TARGET_REPO"
echo "Working directory is now: $WORKING_DIR"
```bash

**For Single-Module Strategy:**

Two scenarios:

**A) If user provided local target repository path:**
```bash
# Use the local repo path directly in subsequent steps
TARGET_REPO="<local-target-path>"

# Check if it's a git repository and update if user requested
if [ -d "$TARGET_REPO/.git" ]; then
    if [ "<update-target>" = "yes" ]; then
        echo "Updating target repository at $TARGET_REPO..."
        cd "$TARGET_REPO"

        # Check current branch and checkout to main/master if needed
        CURRENT_BRANCH=$(git branch --show-current)
        if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
            echo "Repository is currently on branch '$CURRENT_BRANCH'"

            # Try to checkout main first, fall back to master
            if git show-ref --verify --quiet refs/heads/main; then
                echo "Checking out main branch..."
                git checkout main
                TARGET_BRANCH="main"
            elif git show-ref --verify --quiet refs/heads/master; then
                echo "Checking out master branch..."
                git checkout master
                TARGET_BRANCH="master"
            else
                echo "Error: Neither 'main' nor 'master' branch exists"
                cd - > /dev/null
                exit 1
            fi
        else
            TARGET_BRANCH="$CURRENT_BRANCH"
        fi

        echo "On branch $TARGET_BRANCH, updating..."
        # Discover remote name (don't assume 'origin')
        TARGET_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
        if [ -z "$TARGET_REMOTE" ]; then
            echo "Error: No git remote found"
            cd - > /dev/null
            exit 1
        fi
        git fetch "$TARGET_REMOTE"
        git pull "$TARGET_REMOTE" "$TARGET_BRANCH"
        echo "Target repository updated successfully"

        cd - > /dev/null
    else
        echo "Using target repository at $TARGET_REPO (not updating)"
    fi
else
    echo "Warning: $TARGET_REPO is not a git repository"
fi
```

**B) If no local target repository (need to clone):**
```bash
# Extract repository name from URL for remote detection
TARGET_REPO_NAME=$(echo "<target-repo-url>" | sed 's/.*\/\([^/]*\)\.git/\1/' | sed 's/.*\/\([^/]*\)$/\1/')

# Clone or update target repo
if [ -d "repos/target" ]; then
    cd repos/target
    TARGET_REMOTE=$(git remote -v | grep "$TARGET_REPO_NAME" | head -1 | awk '{print $1}')

    if [ -n "$TARGET_REMOTE" ]; then
        echo "Updating target repository from remote: $TARGET_REMOTE"
        git fetch "$TARGET_REMOTE"
        git pull "$TARGET_REMOTE" master || git pull "$TARGET_REMOTE" main
    else
        echo "No remote found for target repository, adding upstream..."
        TARGET_REMOTE="upstream"
        git remote add "$TARGET_REMOTE" <target-repo-url>
        git fetch "$TARGET_REMOTE"
        git pull "$TARGET_REMOTE" master || git pull "$TARGET_REMOTE" main
    fi
    cd ../..
    TARGET_REPO="repos/target"
else
    echo "Cloning target repository..."
    git clone <target-repo-url> repos/target
    TARGET_REPO="repos/target"
fi
```

**After setting up target repository (both scenarios):**
```bash
# Switch working directory to target repository for file creation
echo "Switching working directory to target repository..."
cd "$TARGET_REPO"
WORKING_DIR="$TARGET_REPO"
echo "Working directory is now: $WORKING_DIR"

# Now we'll create tests-extension/ in this directory
echo "tests-extension/ will be created in: $WORKING_DIR/tests-extension/"
```bash

**Note:** In subsequent phases, use `$SOURCE_REPO` and `$TARGET_REPO` variables instead of hardcoded `repos/source` and `repos/target` paths.

### Phase 3: Structure Creation (5 steps)

#### Step 1: Create Directory Structure

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Create cmd directory for main.go
mkdir -p cmd/extension

# Create bin directory for binary output
mkdir -p bin

# Create test directories (use custom test directory name from Input 4a)
mkdir -p test/<test-dir-name>

# Create testdata directory (flatten path: e2e/extension → e2e-extension-testdata)
TESTDATA_DIR_NAME=$(echo "<test-dir-name>" | tr '/' '-')
mkdir -p test/${TESTDATA_DIR_NAME}-testdata

echo "Created monorepo structure in existing repository"
echo "Test directory: test/<test-dir-name>"
echo "Testdata directory: test/${TESTDATA_DIR_NAME}-testdata"
```bash

**For Single-Module Strategy:**
```bash
cd <working-dir>
mkdir -p tests-extension

cd tests-extension

# Create cmd directory for main.go
mkdir -p cmd

# Create bin directory for binary output
mkdir -p bin

# Create test directories
mkdir -p test/e2e
mkdir -p test/testdata

echo "Created single-module structure in tests-extension/"
```bash

#### Step 2: Copy Test Files

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Copy test files from source to test/<test-dir-name>/
# Use $SOURCE_TEST_PATH variable (set in Phase 2)
cp -r "$SOURCE_TEST_PATH"/* test/<test-dir-name>/

# Count and display copied files
echo "Copied $(find test/<test-dir-name> -name '*_test.go' | wc -l) test files from $SOURCE_TEST_PATH"
```

**For Single-Module Strategy:**
```bash
cd <working-dir>/tests-extension

# Copy test files from source to test/e2e/
# Use $SOURCE_TEST_PATH variable (set in Phase 2)
cp -r "$SOURCE_TEST_PATH"/* test/e2e/

# Count and display copied files
echo "Copied $(find test/e2e -name '*_test.go' | wc -l) test files from $SOURCE_TEST_PATH"
```bash

#### Step 3: Copy Testdata

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Flatten test directory path for testdata (e.g., e2e/extension → e2e-extension)
TESTDATA_DIR_NAME=$(echo "<test-dir-name>" | tr '/' '-')

# Copy testdata if it exists (skip if user specified "none")
# Use $SOURCE_TESTDATA_PATH variable (set in Phase 2)
if [ -n "$SOURCE_TESTDATA_PATH" ]; then
    # Create subdirectory structure to match bindata paths
    # Files are organized as testdata/<subfolder>/ to match how tests call FixturePath()
    if [ -n "<testdata-subfolder>" ]; then
        mkdir -p "test/${TESTDATA_DIR_NAME}-testdata/<testdata-subfolder>"
        cp -r "$SOURCE_TESTDATA_PATH"/* "test/${TESTDATA_DIR_NAME}-testdata/<testdata-subfolder>/"
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/${TESTDATA_DIR_NAME}-testdata/<testdata-subfolder>/"
        echo "Tests should call: testdata.FixturePath(\"<testdata-subfolder>/filename.yaml\")"
    else
        # No subfolder specified, copy directly
        cp -r "$SOURCE_TESTDATA_PATH"/* test/${TESTDATA_DIR_NAME}-testdata/
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/${TESTDATA_DIR_NAME}-testdata/"
    fi
else
    echo "Skipping testdata copy (none specified)"
fi
```bash

**For Single-Module Strategy:**
```bash
cd <working-dir>/tests-extension

# Copy testdata if it exists (skip if user specified "none")
# Use $SOURCE_TESTDATA_PATH variable (set in Phase 2)
if [ -n "$SOURCE_TESTDATA_PATH" ]; then
    # Create subdirectory structure to match bindata paths
    # Files are organized as testdata/<subfolder>/ to match how tests call FixturePath()
    if [ -n "<testdata-subfolder>" ]; then
        mkdir -p "test/testdata/<testdata-subfolder>"
        cp -r "$SOURCE_TESTDATA_PATH"/* "test/testdata/<testdata-subfolder>/"
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/testdata/<testdata-subfolder>/"
        echo "Tests should call: testdata.FixturePath(\"<testdata-subfolder>/filename.yaml\")"
    else
        # No subfolder specified, copy directly
        cp -r "$SOURCE_TESTDATA_PATH"/* test/testdata/
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/testdata/"
    fi
else
    echo "Skipping testdata copy (none specified)"
fi
```

### Phase 4: Code Generation (6 steps)

#### Step 1: Generate/Update go.mod Files

**For Monorepo Strategy:**

Create test/<test-dir-name>/go.mod as a separate module:
```bash
cd <working-dir>

# Extract Go version from root go.mod
GO_VERSION=$(grep '^go ' go.mod | awk '{print $2}')
echo "Using Go version: $GO_VERSION (from target repo)"

# Get source repo path (set in Phase 2)
OTP_PATH="$SOURCE_REPO"

echo "Step 1: Create test/<test-dir-name>/go.mod..."
cd test/<test-dir-name>

# Initialize go.mod in test/<test-dir-name> directory
ROOT_MODULE=$(grep '^module ' ../../go.mod | awk '{print $2}')
go mod init "$ROOT_MODULE/test/<test-dir-name>"

echo "Step 2: Set Go version to match target repo..."
sed -i "s/^go .*/go $GO_VERSION/" go.mod

echo "Step 3: Get latest versions from upstream repositories (parallel fetch)..."
# Fetch commit hashes in parallel (fast - no cloning)
echo "Fetching latest commit hashes..."
ORIGIN_LATEST=$(git ls-remote https://github.com/openshift/origin.git refs/heads/main | awk '{print $1}')
K8S_LATEST=$(git ls-remote https://github.com/openshift/kubernetes.git refs/heads/master | awk '{print $1}')
GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')

ORIGIN_SHORT="${ORIGIN_LATEST:0:12}"
K8S_SHORT="${K8S_LATEST:0:12}"
GINKGO_SHORT="${GINKGO_LATEST:0:12}"

echo "Fetching commit timestamps (parallel shallow clones)..."
# Create temp directories
TEMP_ORIGIN=$(mktemp -d)
TEMP_K8S=$(mktemp -d)
TEMP_GINKGO=$(mktemp -d)

# Clone all repos in parallel to get timestamps - CRITICAL PERFORMANCE FIX
# Old approach: Sequential clones took ~90s
# New approach: Parallel clones take ~30-45s
(git clone --depth=1 https://github.com/openshift/origin.git "$TEMP_ORIGIN" >/dev/null 2>&1) &
PID_ORIGIN=$!

(git clone --depth=1 https://github.com/openshift/kubernetes.git "$TEMP_K8S" >/dev/null 2>&1) &
PID_K8S=$!

(git clone --depth=1 --branch=v2.27.2-openshift-4.22 https://github.com/openshift/onsi-ginkgo.git "$TEMP_GINKGO" >/dev/null 2>&1) &
PID_GINKGO=$!

# Wait for all clones to complete
echo "Waiting for parallel clones to complete..."
wait $PID_ORIGIN $PID_K8S $PID_GINKGO

# Extract timestamps
ORIGIN_TIMESTAMP=$(cd "$TEMP_ORIGIN" && git show -s --format=%ct HEAD 2>/dev/null || echo "")
K8S_TIMESTAMP=$(cd "$TEMP_K8S" && git show -s --format=%ct HEAD 2>/dev/null || echo "")
GINKGO_TIMESTAMP=$(cd "$TEMP_GINKGO" && git show -s --format=%ct HEAD 2>/dev/null || echo "")

# Cleanup temp directories
rm -rf "$TEMP_ORIGIN" "$TEMP_K8S" "$TEMP_GINKGO"

# Fallback if timestamps couldn't be extracted
if [ -z "$ORIGIN_TIMESTAMP" ] || [ -z "$K8S_TIMESTAMP" ] || [ -z "$GINKGO_TIMESTAMP" ]; then
    echo "❌ Error: Failed to extract commit timestamps"
    echo "This usually means network issues or repository access problems"
    exit 1
fi

# Generate pseudo-version dates
ORIGIN_DATE=$(date -u -d @${ORIGIN_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${ORIGIN_TIMESTAMP} +%Y%m%d%H%M%S)
K8S_DATE=$(date -u -d @${K8S_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${K8S_TIMESTAMP} +%Y%m%d%H%M%S)
GINKGO_DATE=$(date -u -d @${GINKGO_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${GINKGO_TIMESTAMP} +%Y%m%d%H%M%S)

# Generate version strings
ORIGIN_VERSION="v0.0.0-${ORIGIN_DATE}-${ORIGIN_SHORT}"
K8S_VERSION="v1.30.1-0.${K8S_DATE}-${K8S_SHORT}"
GINKGO_VERSION="v2.6.1-0.${GINKGO_DATE}-${GINKGO_SHORT}"

echo "Using latest origin version: $ORIGIN_VERSION"
echo "Using Kubernetes version: $K8S_VERSION"
echo "Using ginkgo version: $GINKGO_VERSION"

echo "Step 4: Add required dependencies..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/openshift-eng/openshift-tests-extension@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

echo "Step 5: Add replace directives with latest versions to avoid stale dependencies..."
# Fetch latest versions from upstream to avoid outdated dependencies from openshift-tests-private

# Add replace directives to go.mod with fresh versions
echo "" >> go.mod
echo "replace (" >> go.mod
echo "    bitbucket.org/ww/goautoneg => github.com/munnerz/goautoneg v0.0.0-20120707110453-a547fc61f48d" >> go.mod
echo "    github.com/jteeuwen/go-bindata => github.com/jteeuwen/go-bindata v3.0.8-0.20151023091102-a0ff2567cfb7+incompatible" >> go.mod
echo "    github.com/onsi/ginkgo/v2 => github.com/openshift/onsi-ginkgo/v2 $GINKGO_VERSION" >> go.mod
echo "    k8s.io/api => github.com/openshift/kubernetes/staging/src/k8s.io/api v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apiextensions-apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/apiextensions-apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apimachinery => github.com/openshift/kubernetes/staging/src/k8s.io/apimachinery v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cli-runtime => github.com/openshift/kubernetes/staging/src/k8s.io/cli-runtime v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/client-go => github.com/openshift/kubernetes/staging/src/k8s.io/client-go v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cloud-provider => github.com/openshift/kubernetes/staging/src/k8s.io/cloud-provider v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cluster-bootstrap => github.com/openshift/kubernetes/staging/src/k8s.io/cluster-bootstrap v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/code-generator => github.com/openshift/kubernetes/staging/src/k8s.io/code-generator v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/component-base => github.com/openshift/kubernetes/staging/src/k8s.io/component-base v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/component-helpers => github.com/openshift/kubernetes/staging/src/k8s.io/component-helpers v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/controller-manager => github.com/openshift/kubernetes/staging/src/k8s.io/controller-manager v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cri-api => github.com/openshift/kubernetes/staging/src/k8s.io/cri-api v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cri-client => github.com/openshift/kubernetes/staging/src/k8s.io/cri-client v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/csi-translation-lib => github.com/openshift/kubernetes/staging/src/k8s.io/csi-translation-lib v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/dynamic-resource-allocation => github.com/openshift/kubernetes/staging/src/k8s.io/dynamic-resource-allocation v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/endpointslice => github.com/openshift/kubernetes/staging/src/k8s.io/endpointslice v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-aggregator => github.com/openshift/kubernetes/staging/src/k8s.io/kube-aggregator v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-controller-manager => github.com/openshift/kubernetes/staging/src/k8s.io/kube-controller-manager v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-proxy => github.com/openshift/kubernetes/staging/src/k8s.io/kube-proxy v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-scheduler => github.com/openshift/kubernetes/staging/src/k8s.io/kube-scheduler v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubectl => github.com/openshift/kubernetes/staging/src/k8s.io/kubectl v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubelet => github.com/openshift/kubernetes/staging/src/k8s.io/kubelet v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubernetes => github.com/openshift/kubernetes $K8S_VERSION" >> go.mod
echo "    k8s.io/legacy-cloud-providers => github.com/openshift/kubernetes/staging/src/k8s.io/legacy-cloud-providers v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/metrics => github.com/openshift/kubernetes/staging/src/k8s.io/metrics v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/mount-utils => github.com/openshift/kubernetes/staging/src/k8s.io/mount-utils v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/pod-security-admission => github.com/openshift/kubernetes/staging/src/k8s.io/pod-security-admission v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/sample-apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-cli-plugin => github.com/openshift/kubernetes/staging/src/k8s.io/sample-cli-plugin v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-controller => github.com/openshift/kubernetes/staging/src/k8s.io/sample-controller v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod

echo "Step 5a: Extract additional replace directives from openshift-tests-private..."
# Extract replace directives from openshift-tests-private that aren't k8s.io/* or ginkgo
# This captures other important dependencies
cd ../../$SOURCE_REPO
if [ -f "go.mod" ]; then
    echo "Extracting non-k8s replace directives from openshift-tests-private..."
    # Extract replace directives, excluding k8s.io/*, github.com/onsi/ginkgo, and already added ones
    grep "^ *[a-z].*=>" go.mod | \
        grep -v "k8s.io/" | \
        grep -v "github.com/onsi/ginkgo" | \
        grep -v "bitbucket.org/ww/goautoneg" | \
        grep -v "github.com/jteeuwen/go-bindata" | \
        while read -r line; do
            echo "    $line" >> "$OLDPWD/go.mod"
            echo "  Added: $line"
        done
    cd "$OLDPWD"
else
    echo "Warning: openshift-tests-private go.mod not found, skipping additional replace directives"
    cd "$OLDPWD"
fi

echo ")" >> go.mod

echo "Step 6: Generate go.sum (deferred full resolution)..."
# PERFORMANCE FIX: Don't run full 'go mod tidy' here - it can timeout (60-120s)
# Instead, generate minimal go.sum and defer full resolution until after test migration
# This ensures Phase 5 (Test Migration) runs even if dependency resolution is slow

# Generate minimal go.sum from go.mod
echo "Generating minimal go.sum..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download || echo "⚠️  Some dependencies failed to download - will retry after test migration"

# Mark that go mod tidy needs to be run later
echo "⚠️  Note: Full dependency resolution deferred to Phase 6"
echo "    This prevents timeout before test migration completes"

echo "Step 7: Verify go.mod and go.sum are created..."
if [ -f "go.mod" ] && [ -f "go.sum" ]; then
    echo "✅ test/<test-dir-name>/go.mod and go.sum created successfully"
    echo "Module: $(grep '^module' go.mod)"
    echo "Go version: $(grep '^go ' go.mod)"

    # Count replace directives
    REPLACE_COUNT=$(grep -c "=>" go.mod || echo 0)
    echo "Replace directives: $REPLACE_COUNT"
else
    echo "❌ Error: go.mod or go.sum not created properly"
    exit 1
fi

cd ../..

echo "Step 8: Update root go.mod with replace directives..."
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Step 8a: Add replace directive for test module
if ! grep -q "replace.*$MODULE_NAME/test/<test-dir-name>" go.mod; then
    if grep -q "^replace (" go.mod; then
        # Add to existing replace section
        sed -i "/^replace (/a\\    $MODULE_NAME/test/<test-dir-name> => ./test/<test-dir-name>" go.mod
    else
        # Create new replace section
        echo "" >> go.mod
        echo "replace $MODULE_NAME/test/<test-dir-name> => ./test/<test-dir-name>" >> go.mod
    fi
    echo "✅ Test module replace directive added to root go.mod"
fi

# Step 8b: Copy k8s.io and other upstream replace directives from test module to root
echo "Copying k8s.io and upstream replace directives from test/<test-dir-name>/go.mod to root go.mod..."

# Extract replace directives from test module (excluding the self-reference)
TEST_REPLACES=$(grep -A 1000 "^replace (" test/<test-dir-name>/go.mod | grep -v "^replace (" | grep "=>" | grep -v "^)" || echo "")

if [ -n "$TEST_REPLACES" ]; then
    # Ensure root go.mod has a replace block
    if ! grep -q "^replace (" go.mod; then
        echo "" >> go.mod
        echo "replace (" >> go.mod
        echo ")" >> go.mod
    fi

    # Add each replace directive if it doesn't already exist
    ADDED_COUNT=0
    while IFS= read -r replace_line; do
        # Extract the package being replaced (e.g., "k8s.io/api")
        PACKAGE=$(echo "$replace_line" | awk '{print $1}')

        # Skip empty lines
        if [ -z "$PACKAGE" ]; then
            continue
        fi

        # Check if this replace directive already exists in root go.mod
        if ! grep -q "^[[:space:]]*$PACKAGE " go.mod; then
            # Add the replace directive to the replace block
            sed -i "/^replace (/a\\    $replace_line" go.mod
            ADDED_COUNT=$((ADDED_COUNT + 1))
        fi
    done <<< "$TEST_REPLACES"

    echo "✅ Copied $ADDED_COUNT replace directives from test module to root go.mod"
else
    echo "⚠️  No replace directives found in test module"
fi

echo "✅ Monorepo go.mod setup complete"
```

**Note:** For monorepo strategy:
- test/e2e has its own go.mod (separate module)
- go.mod/go.sum are in test/e2e/ directory
- Root go.mod has replace directive pointing to test/e2e
- k8s.io/* and upstream replace directives are automatically copied from test/e2e/go.mod to root go.mod
- Replace directives are dynamically extracted from openshift-tests-private
- Origin version is fetched from github.com/openshift/origin@main

**For Single-Module Strategy:**

Create `tests-extension/go.mod` with dynamic dependencies:
```bash
cd <working-dir>/tests-extension

# Extract Go version from target repo or fallback to openshift-tests-private
if [ -n "$TARGET_REPO" ] && [ -f "$TARGET_REPO/go.mod" ]; then
    GO_VERSION=$(grep '^go ' "$TARGET_REPO/go.mod" | awk '{print $2}')
    echo "Using Go version: $GO_VERSION (from target repo)"
else
    GO_VERSION=$(grep '^go ' "$OTP_PATH/go.mod" | awk '{print $2}')
    echo "Using Go version: $GO_VERSION (from openshift-tests-private)"
fi

echo "Step 1: Initialize Go module..."
go mod init github.com/openshift/<extension-name>-tests-extension

echo "Step 2: Set Go version to match target repo..."
sed -i "s/^go .*/go $GO_VERSION/" go.mod

echo "Step 3: Get latest versions from upstream repositories (parallel fetch)..."
# Fetch commit hashes in parallel (fast - no cloning)
echo "Fetching latest commit hashes..."
ORIGIN_LATEST=$(git ls-remote https://github.com/openshift/origin.git refs/heads/main | awk '{print $1}')
K8S_LATEST=$(git ls-remote https://github.com/openshift/kubernetes.git refs/heads/master | awk '{print $1}')
GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')

ORIGIN_SHORT="${ORIGIN_LATEST:0:12}"
K8S_SHORT="${K8S_LATEST:0:12}"
GINKGO_SHORT="${GINKGO_LATEST:0:12}"

echo "Fetching commit timestamps (parallel shallow clones)..."
# Create temp directories
TEMP_ORIGIN=$(mktemp -d)
TEMP_K8S=$(mktemp -d)
TEMP_GINKGO=$(mktemp -d)

# Clone all repos in parallel to get timestamps - CRITICAL PERFORMANCE FIX
# Old approach: Sequential clones took ~90s
# New approach: Parallel clones take ~30-45s
(git clone --depth=1 https://github.com/openshift/origin.git "$TEMP_ORIGIN" >/dev/null 2>&1) &
PID_ORIGIN=$!

(git clone --depth=1 https://github.com/openshift/kubernetes.git "$TEMP_K8S" >/dev/null 2>&1) &
PID_K8S=$!

(git clone --depth=1 --branch=v2.27.2-openshift-4.22 https://github.com/openshift/onsi-ginkgo.git "$TEMP_GINKGO" >/dev/null 2>&1) &
PID_GINKGO=$!

# Wait for all clones to complete
echo "Waiting for parallel clones to complete..."
wait $PID_ORIGIN $PID_K8S $PID_GINKGO

# Extract timestamps
ORIGIN_TIMESTAMP=$(cd "$TEMP_ORIGIN" && git show -s --format=%ct HEAD 2>/dev/null || echo "")
K8S_TIMESTAMP=$(cd "$TEMP_K8S" && git show -s --format=%ct HEAD 2>/dev/null || echo "")
GINKGO_TIMESTAMP=$(cd "$TEMP_GINKGO" && git show -s --format=%ct HEAD 2>/dev/null || echo "")

# Cleanup temp directories
rm -rf "$TEMP_ORIGIN" "$TEMP_K8S" "$TEMP_GINKGO"

# Fallback if timestamps couldn't be extracted
if [ -z "$ORIGIN_TIMESTAMP" ] || [ -z "$K8S_TIMESTAMP" ] || [ -z "$GINKGO_TIMESTAMP" ]; then
    echo "❌ Error: Failed to extract commit timestamps"
    echo "This usually means network issues or repository access problems"
    exit 1
fi

# Generate pseudo-version dates
ORIGIN_DATE=$(date -u -d @${ORIGIN_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${ORIGIN_TIMESTAMP} +%Y%m%d%H%M%S)
K8S_DATE=$(date -u -d @${K8S_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${K8S_TIMESTAMP} +%Y%m%d%H%M%S)
GINKGO_DATE=$(date -u -d @${GINKGO_TIMESTAMP} +%Y%m%d%H%M%S 2>/dev/null || date -u -r ${GINKGO_TIMESTAMP} +%Y%m%d%H%M%S)

# Generate version strings
ORIGIN_VERSION="v0.0.0-${ORIGIN_DATE}-${ORIGIN_SHORT}"
K8S_VERSION="v1.30.1-0.${K8S_DATE}-${K8S_SHORT}"
GINKGO_VERSION="v2.6.1-0.${GINKGO_DATE}-${GINKGO_SHORT}"

echo "Using latest origin version: $ORIGIN_VERSION"
echo "Using Kubernetes version: $K8S_VERSION"
echo "Using ginkgo version: $GINKGO_VERSION"

echo "Step 4: Add required dependencies..."
go get github.com/openshift-eng/openshift-tests-extension@latest
go get "github.com/openshift/origin@main"
go get github.com/onsi/ginkgo/v2@latest
go get github.com/onsi/gomega@latest

echo "Step 5: Add replace directives with latest versions to avoid stale dependencies..."
# Fetch latest versions from upstream to avoid outdated dependencies from openshift-tests-private

# Add replace directives to go.mod with fresh versions
echo "" >> go.mod
echo "replace (" >> go.mod
echo "    bitbucket.org/ww/goautoneg => github.com/munnerz/goautoneg v0.0.0-20120707110453-a547fc61f48d" >> go.mod
echo "    github.com/jteeuwen/go-bindata => github.com/jteeuwen/go-bindata v3.0.8-0.20151023091102-a0ff2567cfb7+incompatible" >> go.mod
echo "    github.com/onsi/ginkgo/v2 => github.com/openshift/onsi-ginkgo/v2 $GINKGO_VERSION" >> go.mod
echo "    k8s.io/api => github.com/openshift/kubernetes/staging/src/k8s.io/api v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apiextensions-apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/apiextensions-apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apimachinery => github.com/openshift/kubernetes/staging/src/k8s.io/apimachinery v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cli-runtime => github.com/openshift/kubernetes/staging/src/k8s.io/cli-runtime v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/client-go => github.com/openshift/kubernetes/staging/src/k8s.io/client-go v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cloud-provider => github.com/openshift/kubernetes/staging/src/k8s.io/cloud-provider v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cluster-bootstrap => github.com/openshift/kubernetes/staging/src/k8s.io/cluster-bootstrap v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/code-generator => github.com/openshift/kubernetes/staging/src/k8s.io/code-generator v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/component-base => github.com/openshift/kubernetes/staging/src/k8s.io/component-base v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/component-helpers => github.com/openshift/kubernetes/staging/src/k8s.io/component-helpers v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/controller-manager => github.com/openshift/kubernetes/staging/src/k8s.io/controller-manager v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cri-api => github.com/openshift/kubernetes/staging/src/k8s.io/cri-api v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/cri-client => github.com/openshift/kubernetes/staging/src/k8s.io/cri-client v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/csi-translation-lib => github.com/openshift/kubernetes/staging/src/k8s.io/csi-translation-lib v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/dynamic-resource-allocation => github.com/openshift/kubernetes/staging/src/k8s.io/dynamic-resource-allocation v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/endpointslice => github.com/openshift/kubernetes/staging/src/k8s.io/endpointslice v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-aggregator => github.com/openshift/kubernetes/staging/src/k8s.io/kube-aggregator v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-controller-manager => github.com/openshift/kubernetes/staging/src/k8s.io/kube-controller-manager v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-proxy => github.com/openshift/kubernetes/staging/src/k8s.io/kube-proxy v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kube-scheduler => github.com/openshift/kubernetes/staging/src/k8s.io/kube-scheduler v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubectl => github.com/openshift/kubernetes/staging/src/k8s.io/kubectl v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubelet => github.com/openshift/kubernetes/staging/src/k8s.io/kubelet v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/kubernetes => github.com/openshift/kubernetes $K8S_VERSION" >> go.mod
echo "    k8s.io/legacy-cloud-providers => github.com/openshift/kubernetes/staging/src/k8s.io/legacy-cloud-providers v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/metrics => github.com/openshift/kubernetes/staging/src/k8s.io/metrics v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/mount-utils => github.com/openshift/kubernetes/staging/src/k8s.io/mount-utils v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/pod-security-admission => github.com/openshift/kubernetes/staging/src/k8s.io/pod-security-admission v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-apiserver => github.com/openshift/kubernetes/staging/src/k8s.io/sample-apiserver v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-cli-plugin => github.com/openshift/kubernetes/staging/src/k8s.io/sample-cli-plugin v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod
echo "    k8s.io/sample-controller => github.com/openshift/kubernetes/staging/src/k8s.io/sample-controller v0.0.0-${K8S_DATE}-${K8S_SHORT}" >> go.mod

echo "Step 5a: Extract additional replace directives from openshift-tests-private..."
# Extract replace directives from openshift-tests-private that aren't k8s.io/* or ginkgo
# This captures other important dependencies
cd ../../$SOURCE_REPO
if [ -f "go.mod" ]; then
    echo "Extracting non-k8s replace directives from openshift-tests-private..."
    # Extract replace directives, excluding k8s.io/*, github.com/onsi/ginkgo, and already added ones
    grep "^ *[a-z].*=>" go.mod | \
        grep -v "k8s.io/" | \
        grep -v "github.com/onsi/ginkgo" | \
        grep -v "bitbucket.org/ww/goautoneg" | \
        grep -v "github.com/jteeuwen/go-bindata" | \
        while read -r line; do
            echo "    $line" >> "$OLDPWD/go.mod"
            echo "  Added: $line"
        done
    cd "$OLDPWD"
else
    echo "Warning: openshift-tests-private go.mod not found, skipping additional replace directives"
    cd "$OLDPWD"
fi

echo ")" >> go.mod

echo "Step 6: Generate go.sum (deferred full resolution)..."
# PERFORMANCE FIX: Don't run full 'go mod tidy' here - it can timeout (60-120s)
# Instead, generate minimal go.sum and defer full resolution until after test migration
# This ensures Phase 5 (Test Migration) runs even if dependency resolution is slow

# Generate minimal go.sum from go.mod
echo "Generating minimal go.sum..."
go mod download || echo "⚠️  Some dependencies failed to download - will retry after test migration"

# Mark that go mod tidy needs to be run later
echo "⚠️  Note: Full dependency resolution deferred to Phase 6"
echo "    This prevents timeout before test migration completes"

echo "Step 7: Verify go.mod and go.sum are created..."
if [ -f "go.mod" ] && [ -f "go.sum" ]; then
    echo "✅ go.mod and go.sum created successfully"
    echo "Module: $(grep '^module' go.mod)"
    echo "Go version: $(grep '^go ' go.mod)"

    # Count replace directives
    REPLACE_COUNT=$(grep -c "=>" go.mod || echo 0)
    echo "Replace directives: $REPLACE_COUNT"
else
    echo "❌ Error: go.mod or go.sum not created properly"
    exit 1
fi

cd ..
```bash

#### Step 2: Generate Extension Binary (main.go)

**For Monorepo Strategy:**

Create `cmd/extension/main.go`:

**IMPORTANT:** Extract module name from go.mod first:
```bash
cd <working-dir>
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')
echo "Using module name: $MODULE_NAME"
```go

Then generate main.go with the actual module name (not a placeholder):

```go
package main

import (
    "context"
    "fmt"
    "os"
    "regexp"
    "strings"

    "github.com/spf13/cobra"

    "github.com/openshift-eng/openshift-tests-extension/pkg/cmd"
    e "github.com/openshift-eng/openshift-tests-extension/pkg/extension"
    et "github.com/openshift-eng/openshift-tests-extension/pkg/extension/extensiontests"
    g "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"

    // Import test framework packages for initialization
    "github.com/openshift/origin/test/extended/util"
    "k8s.io/kubernetes/test/e2e/framework"

    // Import test packages from test module
    _ "$MODULE_NAME/test/<test-dir-name>"
)

func main() {
    // Initialize test framework
    // This sets TestContext.KubeConfig from KUBECONFIG env var and initializes the cloud provider
    util.InitStandardFlags()
    if err := util.InitTest(false); err != nil {
        panic(fmt.Sprintf("couldn't initialize test framework: %+v", err.Error()))
    }
    framework.AfterReadingAllFlags(&framework.TestContext)

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    // Add main test suite
    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs from Ginkgo
    allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

    // Filter to only include component-specific tests (tests with specified sig tags)
    // Parse sig filter tags from comma-separated list
    sigTags := strings.Split("<sig-filter-tags>", ",")
    var filteredSpecs []*et.ExtensionTestSpec
    allSpecs.Walk(func(spec *et.ExtensionTestSpec) {
        for _, tag := range sigTags {
            tag = strings.TrimSpace(tag)
            if strings.Contains(spec.Name, "[sig-"+tag+"]") {
                filteredSpecs = append(filteredSpecs, spec)
                return // Found a match, no need to check other tags
            }
        }
    })
    specs := et.ExtensionTestSpecs(filteredSpecs)

    // Apply platform filters based on Platform: labels
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        for label := range spec.Labels {
            if strings.HasPrefix(label, "Platform:") {
                platformName := strings.TrimPrefix(label, "Platform:")
                spec.Include(et.PlatformEquals(platformName))
            }
        }
    })

    // Apply platform filters based on [platform:xxx] in test names
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        re := regexp.MustCompile(` + "`\\[platform:([a-z]+)\\]`" + `)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }
    })

    // Set lifecycle for all migrated tests to Informing
    // Tests will run but won't block CI on failure
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        spec.Lifecycle = et.LifecycleInforming
    })

    // Wrap test execution with cleanup handler
    // This marks tests as started and ensures proper cleanup
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        originalRun := spec.Run
        spec.Run = func(ctx context.Context) *et.ExtensionTestResult {
            var result *et.ExtensionTestResult
            util.WithCleanup(func() {
                result = originalRun(ctx)
            })
            return result
        }
    })

    ext.AddSpecs(specs)
    registry.Register(ext)

    root := &cobra.Command{
        Long: "<Extension Name> Tests",
    }

    root.AddCommand(cmd.DefaultExtensionCommands(registry)...)

    if err := func() error {
        return root.Execute()
    }(); err != nil {
        os.Exit(1)
    }
}
```bash

**For Single-Module Strategy:**

Create `cmd/main.go`:

```go
package main

import (
    "context"
    "fmt"
    "os"
    "regexp"
    "strings"

    "github.com/spf13/cobra"

    "github.com/openshift-eng/openshift-tests-extension/pkg/cmd"
    e "github.com/openshift-eng/openshift-tests-extension/pkg/extension"
    et "github.com/openshift-eng/openshift-tests-extension/pkg/extension/extensiontests"
    g "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"

    // Import test framework packages for initialization
    "github.com/openshift/origin/test/extended/util"
    "k8s.io/kubernetes/test/e2e/framework"

    // Import test packages
    _ "github.com/openshift/<extension-name>-tests-extension/test/e2e"
)

func main() {
    // Initialize test framework
    // This sets TestContext.KubeConfig from KUBECONFIG env var and initializes the cloud provider
    util.InitStandardFlags()
    if err := util.InitTest(false); err != nil {
        panic(fmt.Sprintf("couldn't initialize test framework: %+v", err.Error()))
    }
    framework.AfterReadingAllFlags(&framework.TestContext)

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    // Add main test suite
    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs from Ginkgo
    allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

    // Filter to only include component-specific tests (tests with specified sig tags)
    // Parse sig filter tags from comma-separated list
    sigTags := strings.Split("<sig-filter-tags>", ",")
    var filteredSpecs []*et.ExtensionTestSpec
    allSpecs.Walk(func(spec *et.ExtensionTestSpec) {
        for _, tag := range sigTags {
            tag = strings.TrimSpace(tag)
            if strings.Contains(spec.Name, "[sig-"+tag+"]") {
                filteredSpecs = append(filteredSpecs, spec)
                return // Found a match, no need to check other tags
            }
        }
    })
    specs := et.ExtensionTestSpecs(filteredSpecs)

    // Apply platform filters based on Platform: labels
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        for label := range spec.Labels {
            if strings.HasPrefix(label, "Platform:") {
                platformName := strings.TrimPrefix(label, "Platform:")
                spec.Include(et.PlatformEquals(platformName))
            }
        }
    })

    // Apply platform filters based on [platform:xxx] in test names
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        re := regexp.MustCompile(` + "`\\[platform:([a-z]+)\\]`" + `)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }
    })

    // Set lifecycle for all migrated tests to Informing
    // Tests will run but won't block CI on failure
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        spec.Lifecycle = et.LifecycleInforming
    })

    // Wrap test execution with cleanup handler
    // This marks tests as started and ensures proper cleanup
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        originalRun := spec.Run
        spec.Run = func(ctx context.Context) *et.ExtensionTestResult {
            var result *et.ExtensionTestResult
            util.WithCleanup(func() {
                result = originalRun(ctx)
            })
            return result
        }
    })

    ext.AddSpecs(specs)
    registry.Register(ext)

    root := &cobra.Command{
        Long: "<Extension Name> Tests",
    }

    root.AddCommand(cmd.DefaultExtensionCommands(registry)...)

    if err := func() error {
        return root.Execute()
    }(); err != nil {
        os.Exit(1)
    }
}
```

#### Step 3: Create bindata.mk

**For Monorepo Strategy:**

Create `test/bindata.mk`:

```makefile
# Bindata generation for testdata files

# Testdata path (relative to test/ directory)
# Flattened from test path: e2e/extension → e2e-extension-testdata
TESTDATA_DIR_NAME := $(shell echo "<test-dir-name>" | tr '/' '-')
TESTDATA_PATH := $(TESTDATA_DIR_NAME)-testdata

# go-bindata tool path
GOPATH ?= $(shell go env GOPATH)
GO_BINDATA := $(GOPATH)/bin/go-bindata

# Install go-bindata if not present
$(GO_BINDATA):
    @echo "Installing go-bindata to $(GO_BINDATA)..."
    @go install github.com/go-bindata/go-bindata/v3/go-bindata@latest
    @echo "go-bindata installed successfully"

# Generate bindata.go from testdata directory
.PHONY: bindata
bindata: clean-bindata $(GO_BINDATA)
    @echo "Generating bindata from $(TESTDATA_PATH)..."
    @mkdir -p $(TESTDATA_PATH)
    $(GO_BINDATA) -nocompress -nometadata \
        -pkg testdata -o $(TESTDATA_PATH)/bindata.go $(TESTDATA_PATH)/...
    @gofmt -s -w $(TESTDATA_PATH)/bindata.go
    @echo "Bindata generated successfully at $(TESTDATA_PATH)/bindata.go"

.PHONY: clean-bindata
clean-bindata:
    @echo "Cleaning bindata..."
    @rm -f $(TESTDATA_PATH)/bindata.go
```bash

**For Single-Module Strategy:**

Create `tests-extension/bindata.mk`:

```makefile
# Bindata generation for testdata files

# Testdata path
TESTDATA_PATH := test/testdata

# go-bindata tool path
GOPATH ?= $(shell go env GOPATH)
GO_BINDATA := $(GOPATH)/bin/go-bindata

# Install go-bindata if not present
$(GO_BINDATA):
    @echo "Installing go-bindata to $(GO_BINDATA)..."
    @go install github.com/go-bindata/go-bindata/v3/go-bindata@latest
    @echo "go-bindata installed successfully"

# Generate bindata.go from testdata directory
.PHONY: bindata
bindata: clean-bindata $(GO_BINDATA)
    @echo "Generating bindata from $(TESTDATA_PATH)..."
    @mkdir -p $(TESTDATA_PATH)
    $(GO_BINDATA) -nocompress -nometadata \
        -pkg testdata -o $(TESTDATA_PATH)/bindata.go -prefix "test" $(TESTDATA_PATH)/...
    @gofmt -s -w $(TESTDATA_PATH)/bindata.go
    @echo "Bindata generated successfully at $(TESTDATA_PATH)/bindata.go"

.PHONY: clean-bindata
clean-bindata:
    @echo "Cleaning bindata..."
    @rm -f $(TESTDATA_PATH)/bindata.go
```makefile

#### Step 4: Create Makefile

**For Monorepo Strategy:**

Update root `Makefile` (or add extension target to existing one):

```bash
cd <working-dir>

# Flatten test directory path for bindata (e.g., e2e/extension → e2e-extension)
TESTDATA_DIR_NAME=$(echo "<test-dir-name>" | tr '/' '-')

# Check if Makefile exists
if [ -f "Makefile" ]; then
    echo "Updating root Makefile with OTE extension target..."

    # Check if OTE targets already exist
    if grep -q "tests-ext-build" Makefile; then
        echo "⚠️  OTE targets already exist in Makefile, skipping..."
    else
        # Add OTE extension build targets for monorepo
        cat >> Makefile << EOF

# OTE test extension binary configuration
TESTS_EXT_BINARY := bin/<extension-name>-tests-ext
TESTDATA_DIR_NAME := ${TESTDATA_DIR_NAME}

# Build OTE extension binary
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@echo "Generating bindata from test/\$(TESTDATA_DIR_NAME)-testdata/..."
	@$(MAKE) -C test bindata
	@echo "Building binary..."
	@mkdir -p bin
	@GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o \$(TESTS_EXT_BINARY) ./cmd/extension
	@echo "OTE binary built successfully at \$(TESTS_EXT_BINARY)"

# Compress OTE extension binary (for CI/CD and container builds)
.PHONY: tests-ext-compress
tests-ext-compress: tests-ext-build
	@echo "Compressing OTE extension binary..."
	@gzip -f \$(TESTS_EXT_BINARY)
	@echo "Compressed binary created at \$(TESTS_EXT_BINARY).gz"

# Copy compressed binary to _output directory (for CI/CD)
.PHONY: tests-ext-copy
tests-ext-copy: tests-ext-compress
	@echo "Copying compressed binary to _output..."
	@mkdir -p _output
	@cp \$(TESTS_EXT_BINARY).gz _output/
	@echo "Binary copied to _output/<extension-name>-tests-ext.gz"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY) \$(TESTS_EXT_BINARY).gz _output/<extension-name>-tests-ext.gz
	@$(MAKE) -C test clean-bindata
EOF

        echo "✅ Root Makefile updated with OTE targets"
    fi
else
    echo "⚠️  No root Makefile found in target repository"
    echo "Creating a basic Makefile with OTE targets..."
    cat > Makefile << EOF
# OTE test extension binary configuration
TESTS_EXT_BINARY := bin/<extension-name>-tests-ext
TESTDATA_DIR_NAME := ${TESTDATA_DIR_NAME}

.PHONY: all
all: tests-ext-build

# Build OTE extension binary
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@echo "Generating bindata from test/\$(TESTDATA_DIR_NAME)-testdata/..."
	@$(MAKE) -C test bindata
	@echo "Building binary..."
	@mkdir -p bin
	@GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o \$(TESTS_EXT_BINARY) ./cmd/extension
	@echo "OTE binary built successfully at \$(TESTS_EXT_BINARY)"

# Compress OTE extension binary (for CI/CD and container builds)
.PHONY: tests-ext-compress
tests-ext-compress: tests-ext-build
	@echo "Compressing OTE extension binary..."
	@gzip -f \$(TESTS_EXT_BINARY)
	@echo "Compressed binary created at \$(TESTS_EXT_BINARY).gz"

# Copy compressed binary to _output directory (for CI/CD)
.PHONY: tests-ext-copy
tests-ext-copy: tests-ext-compress
	@echo "Copying compressed binary to _output..."
	@mkdir -p _output
	@cp \$(TESTS_EXT_BINARY).gz _output/
	@echo "Binary copied to _output/<extension-name>-tests-ext.gz"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY) \$(TESTS_EXT_BINARY).gz _output/<extension-name>-tests-ext.gz
	@$(MAKE) -C test clean-bindata
EOF

    echo "✅ Root Makefile created with OTE targets"
fi
```bash

**For Single-Module Strategy:**

Create `tests-extension/Makefile`:

```makefile
# Include bindata targets
include bindata.mk

# Binary name and output directory
BINARY := bin/<extension-name>-tests-ext

# Build extension binary
.PHONY: build
build: bindata
    @echo "Building extension binary..."
    @mkdir -p bin
    GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o $(BINARY) ./cmd
    @echo "Binary built successfully at $(BINARY)"

# Clean generated files
.PHONY: clean
clean:
    @echo "Cleaning binaries..."
    @rm -f $(BINARY)

.PHONY: help
help:
    @echo "Available targets:"
    @echo "  bindata     - Generate bindata.go from test/testdata"
    @echo "  build       - Build extension binary (includes bindata)"
    @echo "  clean       - Remove extension binary"
```

**Update Root Makefile (Target Repository):**

For single-module strategy, also update the root Makefile in the target repository to add a target for building the OTE extension:

```bash
cd <working-dir>

# Check if Makefile exists
if [ -f "Makefile" ]; then
    echo "Updating root Makefile with OTE extension target..."

    # Check if OTE targets already exist
    if grep -q "tests-ext-build" Makefile; then
        echo "⚠️  OTE targets already exist in Makefile, skipping..."
    else
        # Add OTE extension build target
        cat >> Makefile << 'EOF'

# OTE test extension binary configuration
TESTS_EXT_DIR := ./tests-extension
TESTS_EXT_BINARY := tests-extension/bin/<extension-name>-tests-ext

# Build OTE extension binary
.PHONY: tests-ext-build
tests-ext-build:
    @echo "Building OTE test extension binary..."
    @cd $(TESTS_EXT_DIR) && $(MAKE) build
    @echo "OTE binary built successfully at $(TESTS_EXT_BINARY)"

# Compress OTE extension binary (for CI/CD and container builds)
.PHONY: tests-ext-compress
tests-ext-compress: tests-ext-build
    @echo "Compressing OTE extension binary..."
    @gzip -f $(TESTS_EXT_BINARY)
    @echo "Compressed binary created at $(TESTS_EXT_BINARY).gz"

# Copy compressed binary to _output directory (for CI/CD)
.PHONY: tests-ext-copy
tests-ext-copy: tests-ext-compress
    @echo "Copying compressed binary to _output..."
    @mkdir -p _output
    @cp $(TESTS_EXT_BINARY).gz _output/
    @echo "Binary copied to _output/<extension-name>-tests-ext.gz"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
    @echo "Cleaning extension binary..."
    @rm -f $(TESTS_EXT_BINARY) $(TESTS_EXT_BINARY).gz _output/<extension-name>-tests-ext.gz
    @cd $(TESTS_EXT_DIR) && $(MAKE) clean
EOF

        echo "✅ Root Makefile updated with OTE targets"
    fi
else
    echo "⚠️  No root Makefile found in target repository"
    echo "You may need to create one or integrate the build manually"
fi
```bash

**Key Points:**
- The root Makefile delegates to `tests-extension/Makefile` for building
- Binary is built to `tests-extension/bin/<extension-name>-tests-ext`
- Provides compression and copy targets for CI/CD workflows:
  - `make tests-ext-build` - Build the binary
  - `make tests-ext-compress` - Build and compress with gzip
  - `make tests-ext-copy` - Build, compress, and copy to `_output/`
  - `make extension` - Alias for tests-ext-build
- Can be called from Dockerfile or CI/CD scripts

#### Step 5: Create fixtures.go

**For Monorepo Strategy:**

Create `test/<flattened-test-dir-name>-testdata/fixtures.go`:

(Where `<flattened-test-dir-name>` = `<test-dir-name>` with `/` replaced by `-`)
Example: `test/e2e/extension/` → `test/e2e-extension-testdata/fixtures.go`

**For Single-Module Strategy:**

Create `tests-extension/test/testdata/fixtures.go`:

**Note:** The fixtures.go content is the same for both strategies:

```go
package testdata

import (
    "fmt"
    "io/ioutil"
    "os"
    "path/filepath"
    "sort"
    "strings"
)

var (
    // fixtureDir is where extracted fixtures are stored
    fixtureDir string
)

// init sets up the temporary directory for fixtures
func init() {
    var err error
    fixtureDir, err = ioutil.TempDir("", "testdata-fixtures-")
    if err != nil {
        panic(fmt.Sprintf("failed to create fixture directory: %v", err))
    }
}

// FixturePath returns the filesystem path to a test fixture file.
// This replaces functions like compat_otp.FixturePath() and exutil.FixturePath().
//
// The file is extracted from embedded bindata to the filesystem on first access.
// Files are extracted to a temporary directory that persists for the test run.
//
// Accepts multiple path elements that will be joined together.
//
// IMPORTANT: Do NOT include "testdata" as the first argument.
// The function automatically prepends "testdata/" to construct the bindata path.
//
// Migration examples:
//   Origin-tests:        compat_otp.FixturePath("testdata", "router", "config.yaml")
//   Tests-extension:     testdata.FixturePath("router", "config.yaml")
//
//   Origin-tests:        exutil.FixturePath("testdata", "manifests", "pod.yaml")
//   Tests-extension:     testdata.FixturePath("manifests", "pod.yaml")
//
// Example:
//   configPath := testdata.FixturePath("manifests", "config.yaml")
//   data, err := os.ReadFile(configPath)
func FixturePath(elem ...string) string {
    // Join all path elements
    relativePath := filepath.Join(elem...)
    targetPath := filepath.Join(fixtureDir, relativePath)

    // Check if already extracted
    if _, err := os.Stat(targetPath); err == nil {
        return targetPath
    }

    // Create parent directory
    if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
        panic(fmt.Sprintf("failed to create directory for %s: %v", relativePath, err))
    }

    // Bindata stores assets with "testdata/" prefix
    // e.g., bindata has "testdata/router/file.yaml" but tests call FixturePath("router/file.yaml")
    bindataPath := filepath.Join("testdata", relativePath)

    // Extract to temp directory first to handle path mismatch
    tempDir, err := os.MkdirTemp("", "bindata-extract-")
    if err != nil {
        panic(fmt.Sprintf("failed to create temp directory: %v", err))
    }
    defer os.RemoveAll(tempDir)

    // Try to restore single asset or directory to temp location
    if err := RestoreAsset(tempDir, bindataPath); err != nil {
        // If single file fails, try restoring as directory
        if err := RestoreAssets(tempDir, bindataPath); err != nil {
            panic(fmt.Sprintf("failed to restore fixture %s: %v", relativePath, err))
        }
    }

    // Move extracted files from temp location to target location
    extractedPath := filepath.Join(tempDir, bindataPath)
    if err := os.Rename(extractedPath, targetPath); err != nil {
        panic(fmt.Sprintf("failed to move extracted files from %s to %s: %v", extractedPath, targetPath, err))
    }

    // Set appropriate permissions for directories
    if info, err := os.Stat(targetPath); err == nil && info.IsDir() {
        filepath.Walk(targetPath, func(path string, info os.FileInfo, err error) error {
            if err != nil {
                return err
            }
            if info.IsDir() {
                os.Chmod(path, 0755)
            } else {
                os.Chmod(path, 0644)
            }
            return nil
        })
    }

    return targetPath
}

// CleanupFixtures removes all extracted fixture files.
// Call this in test cleanup (e.g., AfterAll hook).
func CleanupFixtures() error {
    if fixtureDir != "" {
        return os.RemoveAll(fixtureDir)
    }
    return nil
}

// GetFixtureData reads and returns the contents of a fixture file directly from bindata.
// Use this for small files that don't need to be written to disk.
//
// Accepts multiple path elements that will be joined together.
//
// Example:
//   data, err := testdata.GetFixtureData("manifests", "config.yaml")
func GetFixtureData(elem ...string) ([]byte, error) {
    // Join all path elements
    relativePath := filepath.Join(elem...)

    // Normalize path - bindata uses "testdata/" prefix
    cleanPath := relativePath
    if len(cleanPath) > 0 && cleanPath[0] == '/' {
        cleanPath = cleanPath[1:]
    }

    return Asset(filepath.Join("testdata", cleanPath))
}

// MustGetFixtureData is like GetFixtureData but panics on error.
// Useful in test initialization code.
//
// Accepts multiple path elements that will be joined together.
func MustGetFixtureData(elem ...string) []byte {
    data, err := GetFixtureData(elem...)
    if err != nil {
        panic(fmt.Sprintf("failed to get fixture data for %s: %v", filepath.Join(elem...), err))
    }
    return data
}

// Component-specific helper functions

// FixtureExists checks if a fixture exists in the embedded bindata.
// Use this to validate fixtures before accessing them.
//
// Accepts multiple path elements that will be joined together.
//
// Example:
//   if testdata.FixtureExists("manifests", "deployment.yaml") {
//       path := testdata.FixturePath("manifests", "deployment.yaml")
//   }
func FixtureExists(elem ...string) bool {
    // Join all path elements
    relativePath := filepath.Join(elem...)

    cleanPath := relativePath
    if len(cleanPath) > 0 && cleanPath[0] == '/' {
        cleanPath = cleanPath[1:]
    }
    _, err := Asset(filepath.Join("testdata", cleanPath))
    return err == nil
}

// ListFixtures returns all available fixture paths in the embedded bindata.
// Useful for debugging and test discovery.
//
// Example:
//   fixtures := testdata.ListFixtures()
//   fmt.Printf("Available fixtures: %v\n", fixtures)
func ListFixtures() []string {
    names := AssetNames()
    fixtures := make([]string, 0, len(names))
    for _, name := range names {
        // Remove "testdata/" prefix for cleaner paths
        if strings.HasPrefix(name, "testdata/") {
            fixtures = append(fixtures, strings.TrimPrefix(name, "testdata/"))
        }
    }
    sort.Strings(fixtures)
    return fixtures
}

// ListFixturesInDir returns all fixtures within a specific directory.
//
// Example:
//   manifests := testdata.ListFixturesInDir("manifests")
//   // Returns: ["manifests/deployment.yaml", "manifests/service.yaml", ...]
func ListFixturesInDir(dir string) []string {
    allFixtures := ListFixtures()
    var matching []string
    prefix := dir
    if !strings.HasSuffix(prefix, "/") {
        prefix = prefix + "/"
    }
    for _, fixture := range allFixtures {
        if strings.HasPrefix(fixture, prefix) {
            matching = append(matching, fixture)
        }
    }
    return matching
}

// GetManifest is a convenience function for accessing manifest files.
// Equivalent to FixturePath("manifests/" + name).
//
// Example:
//   deploymentPath := testdata.GetManifest("deployment.yaml")
func GetManifest(name string) string {
    return FixturePath(filepath.Join("manifests", name))
}

// GetConfig is a convenience function for accessing config files.
// Equivalent to FixturePath("configs/" + name).
//
// Example:
//   configPath := testdata.GetConfig("settings.yaml")
func GetConfig(name string) string {
    return FixturePath(filepath.Join("configs", name))
}

// ValidateFixtures checks that all expected fixtures are present in bindata.
// Call this in BeforeAll to catch missing testdata early.
//
// Example:
//   required := []string{"manifests/deployment.yaml", "configs/config.yaml"}
//   if err := testdata.ValidateFixtures(required); err != nil {
//       panic(err)
//   }
func ValidateFixtures(required []string) error {
    var missing []string
    for _, fixture := range required {
        if !FixtureExists(fixture) {
            missing = append(missing, fixture)
        }
    }
    if len(missing) > 0 {
        return fmt.Errorf("missing required fixtures: %v", missing)
    }
    return nil
}

// GetFixtureDir returns the temporary directory where fixtures are extracted.
// Use this if you need to pass a directory path to external tools.
//
// Example:
//   fixtureRoot := testdata.GetFixtureDir()
func GetFixtureDir() string {
    return fixtureDir
}
```bash

#### Step 6: Update Dockerfile (Monorepo Strategy Only)

**For Monorepo Strategy:**

Following the pattern from machine-config-operator PR #4665, update the Dockerfile to build and include the OTE binary:

```dockerfile
# Example multi-stage Dockerfile update
# Add this to your existing Dockerfile or create a new one

# Build stage - Build the OTE test extension binary
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

# Copy source code
COPY . .

# Generate testdata bindata
RUN cd test && make bindata

# Build the OTE extension binary using the Makefile target
RUN make tests-ext-build

# Compress the binary (following OpenShift pattern)
RUN gzip bin/<extension-name>-tests-ext

# Final stage - Runtime image
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9

# Copy the compressed OTE binary to /usr/bin/
COPY --from=builder /go/src/github.com/<org>/<component-name>/bin/<extension-name>-tests-ext.gz /usr/bin/

# ... rest of your Dockerfile (copy other binaries, set entrypoint, etc.)
```bash

**Key Points:**
- The Dockerfile builds the OTE binary using the `tests-ext-build` Makefile target
- The binary is compressed with gzip following OpenShift conventions
- The compressed binary (.gz) is copied to `/usr/bin/` in the final image
- The build happens in a builder stage with the Go toolchain
- The final runtime image only contains the compressed binary

**For Single-Module Strategy:**

Following the same pattern, update the target repository's Dockerfile to build and include the OTE binary:

```dockerfile
# Example multi-stage Dockerfile update for single-module strategy
# Add this to your existing Dockerfile in the target repository

# Build stage - Build the OTE test extension binary
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

# Copy source code
COPY . .

# Build the OTE extension binary using the root Makefile target
# This delegates to tests-extension/Makefile
RUN make tests-ext-build

# Compress the binary (following OpenShift pattern)
RUN gzip tests-extension/bin/<extension-name>-tests-ext

# Final stage - Runtime image
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9

# Copy the compressed OTE binary to /usr/bin/
COPY --from=builder /go/src/github.com/<org>/<component-name>/tests-extension/bin/<extension-name>-tests-ext.gz /usr/bin/

# ... rest of your Dockerfile (copy other binaries, set entrypoint, etc.)
```

**Key Points:**
- The Dockerfile uses the root Makefile target `make tests-ext-build`
- The Root Makefile delegates to `tests-extension/Makefile`
- Binary is compressed from `tests-extension/bin/<extension-name>-tests-ext`
- The compressed binary (.gz) is copied to `/usr/bin/` in the final image
- The build happens in a builder stage with the Go toolchain
- The final runtime image only contains the compressed binary

### Phase 5: Test Migration (5 steps - AUTOMATED with error handling)

**CRITICAL: This phase must complete atomically - all steps succeed or rollback**

#### Step 0: Setup Error Handling and Backup

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Phase 5: Test Migration with error handling"
echo "========================================="

# Create backup of test files before migration
echo "Creating backup of test files..."
BACKUP_DIR=$(mktemp -d)
if [ -d "test/<test-dir-name>" ]; then
    cp -r "test/<test-dir-name>" "$BACKUP_DIR/test-backup"
    echo "Backup created at: $BACKUP_DIR/test-backup"
fi

# Error tracking
PHASE5_FAILED=0

# Cleanup function
cleanup_on_error() {
    if [ $PHASE5_FAILED -eq 1 ]; then
        echo "❌ Phase 5 failed - rolling back test files..."
        if [ -d "$BACKUP_DIR/test-backup" ]; then
            rm -rf "test/<test-dir-name>"
            cp -r "$BACKUP_DIR/test-backup" "test/<test-dir-name>"
            echo "✅ Test files restored from backup"
        fi
    fi
    rm -rf "$BACKUP_DIR"
}

# Set trap to cleanup on error
trap cleanup_on_error EXIT
```

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "========================================="
echo "Phase 5: Test Migration with error handling"
echo "========================================="

# Create backup of test files before migration
echo "Creating backup of test files..."
BACKUP_DIR=$(mktemp -d)
if [ -d "test/e2e" ]; then
    cp -r "test/e2e" "$BACKUP_DIR/test-backup"
    echo "Backup created at: $BACKUP_DIR/test-backup"
fi

# Error tracking
PHASE5_FAILED=0

# Cleanup function
cleanup_on_error() {
    if [ $PHASE5_FAILED -eq 1 ]; then
        echo "❌ Phase 5 failed - rolling back test files..."
        if [ -d "$BACKUP_DIR/test-backup" ]; then
            rm -rf "test/e2e"
            cp -r "$BACKUP_DIR/test-backup" "test/e2e"
            echo "✅ Test files restored from backup"
        fi
    fi
    rm -rf "$BACKUP_DIR"
}

# Set trap to cleanup on error
trap cleanup_on_error EXIT
```

#### Step 1: Replace FixturePath Calls

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Step 1: Replacing FixturePath calls..."
echo "========================================="

# Find all test files that use FixturePath
TEST_FILES=$(grep -rl "FixturePath" test/e2e/ --include="*_test.go" 2>/dev/null || true)

if [ -z "$TEST_FILES" ]; then
    echo "No test files using FixturePath found - skipping migration"
else
    echo "Found $(echo "$TEST_FILES" | wc -l) test files using FixturePath"

    # Replace compat_otp.FixturePath with testdata.FixturePath
    echo "Replacing compat_otp.FixturePath() calls..."
    for file in $TEST_FILES; do
        if grep -q "compat_otp\.FixturePath" "$file"; then
            sed -i 's/compat_otp\.FixturePath/testdata.FixturePath/g' "$file"
            echo "  ✓ Updated $file (compat_otp)"
        fi
    done

    # Replace exutil.FixturePath with testdata.FixturePath
    echo "Replacing exutil.FixturePath() calls..."
    for file in $TEST_FILES; do
        if grep -q "exutil\.FixturePath" "$file"; then
            sed -i 's/exutil\.FixturePath/testdata.FixturePath/g' "$file"
            echo "  ✓ Updated $file (exutil)"
        fi
    done

    # Remove first "testdata" argument from FixturePath calls
    # In origin-tests: compat_otp.FixturePath("testdata", "router")
    # In tests-extension: testdata.FixturePath("router")
    echo "Removing redundant 'testdata' prefix from FixturePath arguments..."
    for file in $TEST_FILES; do
        if grep -q 'testdata\.FixturePath("testdata"' "$file"; then
            sed -i 's/testdata\.FixturePath("testdata", /testdata.FixturePath(/g' "$file"
            echo "  ✓ Updated $file (removed testdata prefix)"
        fi
    done

    echo "✅ FixturePath calls replaced successfully"
fi
```bash

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "========================================="
echo "Automating test file migration..."
echo "========================================="

# Find all test files that use FixturePath
TEST_FILES=$(grep -rl "FixturePath" test/e2e/ --include="*_test.go" 2>/dev/null || true)

if [ -z "$TEST_FILES" ]; then
    echo "No test files using FixturePath found - skipping migration"
else
    echo "Found $(echo "$TEST_FILES" | wc -l) test files using FixturePath"

    # Replace compat_otp.FixturePath with testdata.FixturePath
    echo "Replacing compat_otp.FixturePath() calls..."
    for file in $TEST_FILES; do
        if grep -q "compat_otp\.FixturePath" "$file"; then
            sed -i 's/compat_otp\.FixturePath/testdata.FixturePath/g' "$file"
            echo "  ✓ Updated $file (compat_otp)"
        fi
    done

    # Replace exutil.FixturePath with testdata.FixturePath
    echo "Replacing exutil.FixturePath() calls..."
    for file in $TEST_FILES; do
        if grep -q "exutil\.FixturePath" "$file"; then
            sed -i 's/exutil\.FixturePath/testdata.FixturePath/g' "$file"
            echo "  ✓ Updated $file (exutil)"
        fi
    done

    # Remove first "testdata" argument from FixturePath calls
    # In origin-tests: compat_otp.FixturePath("testdata", "router")
    # In tests-extension: testdata.FixturePath("router")
    echo "Removing redundant 'testdata' prefix from FixturePath arguments..."
    for file in $TEST_FILES; do
        if grep -q 'testdata\.FixturePath("testdata"' "$file"; then
            sed -i 's/testdata\.FixturePath("testdata", /testdata.FixturePath(/g' "$file"
            echo "  ✓ Updated $file (removed testdata prefix)"
        fi
    done

    echo "✅ FixturePath calls replaced successfully"
fi
```

#### Step 2: Add Testdata Import

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "Adding testdata import to test files..."

# Flatten test directory path for import (e.g., e2e/extension → e2e-extension)
TESTDATA_DIR_NAME=$(echo "<test-dir-name>" | tr '/' '-')

# Find all test files that now use testdata.FixturePath
TEST_FILES=$(grep -rl "testdata\.FixturePath" test/<test-dir-name>/ --include="*_test.go" 2>/dev/null || true)

if [ -z "$TEST_FILES" ]; then
    echo "No test files need testdata import"
else
    TESTDATA_IMPORT="$MODULE_NAME/test/${TESTDATA_DIR_NAME}-testdata"

    for file in $TEST_FILES; do
        # Check if import already exists
        if grep -q "\"$TESTDATA_IMPORT\"" "$file"; then
            echo "  ✓ $file (import already exists)"
            continue
        fi

        # Add import after package declaration
        # Look for existing import block
        if grep -q "^import (" "$file"; then
            # Add to existing import block (after "import (" line)
            sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"" "$file"
            echo "  ✓ Added import to $file (existing import block)"
        elif grep -q "^import \"" "$file"; then
            # Convert single import to multi-import block
            sed -i '0,/^import "/s/^import "/import (\n\t"/' "$file"
            sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (created import block)"
        else
            # No imports yet, add after package line
            sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (new import block)"
        fi
    done

    echo "✅ Testdata imports added successfully"
fi
```bash

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "Adding testdata import to test files..."

# Find all test files that now use testdata.FixturePath
TEST_FILES=$(grep -rl "testdata\.FixturePath" test/e2e/ --include="*_test.go" 2>/dev/null || true)

if [ -z "$TEST_FILES" ]; then
    echo "No test files need testdata import"
else
    TESTDATA_IMPORT="github.com/openshift/<extension-name>-tests-extension/test/testdata"

    for file in $TEST_FILES; do
        # Check if import already exists
        if grep -q "\"$TESTDATA_IMPORT\"" "$file"; then
            echo "  ✓ $file (import already exists)"
            continue
        fi

        # Add import after package declaration
        # Look for existing import block
        if grep -q "^import (" "$file"; then
            # Add to existing import block (after "import (" line)
            sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"" "$file"
            echo "  ✓ Added import to $file (existing import block)"
        elif grep -q "^import \"" "$file"; then
            # Convert single import to multi-import block
            sed -i '0,/^import "/s/^import "/import (\n\t"/' "$file"
            sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (created import block)"
        else
            # No imports yet, add after package line
            sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (new import block)"
        fi
    done

    echo "✅ Testdata imports added successfully"
fi
```bash

#### Step 3: Remove Old Imports (Optional Cleanup)

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "Removing old compat_otp and exutil imports..."

# Find all test files
TEST_FILES=$(find test/e2e -name '*_test.go' -type f)

for file in $TEST_FILES; do
    CHANGED=0

    # Comment out compat_otp import if it exists and is no longer used
    if grep -q "compat_otp" "$file" && ! grep -q "compat_otp\." "$file"; then
        sed -i 's|^\(\s*\)"\(.*compat_otp\)"|// \1"\2" // Replaced by testdata package|g' "$file"
        CHANGED=1
    fi

    # Comment out exutil import if FixturePath was the only usage
    if grep -q "github.com/openshift/origin/test/extended/util\"" "$file" && \
       ! grep -q "exutil\." "$file"; then
        sed -i 's|^\(\s*\)"\(github.com/openshift/origin/test/extended/util\)"|// \1"\2" // Replaced by testdata package|g' "$file"
        CHANGED=1
    fi

    if [ $CHANGED -eq 1 ]; then
        echo "  ✓ Cleaned up imports in $file"
    fi
done

echo "✅ Old imports cleaned up"
```bash

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "Removing old compat_otp and exutil imports..."

# Find all test files
TEST_FILES=$(find test/e2e -name '*_test.go' -type f)

for file in $TEST_FILES; do
    CHANGED=0

    # Comment out compat_otp import if it exists and is no longer used
    if grep -q "compat_otp" "$file" && ! grep -q "compat_otp\." "$file"; then
        sed -i 's|^\(\s*\)"\(.*compat_otp\)"|// \1"\2" // Replaced by testdata package|g' "$file"
        CHANGED=1
    fi

    # Comment out exutil import if FixturePath was the only usage
    if grep -q "github.com/openshift/origin/test/extended/util\"" "$file" && \
       ! grep -q "exutil\." "$file"; then
        sed -i 's|^\(\s*\)"\(github.com/openshift/origin/test/extended/util\)"|// \1"\2" // Replaced by testdata package|g' "$file"
        CHANGED=1
    fi

    if [ $CHANGED -eq 1 ]; then
        echo "  ✓ Cleaned up imports in $file"
    fi
done

echo "✅ Old imports cleaned up"
```

#### Step 4: Add OTP and Level0 Annotations

**Purpose:** Add tracking annotations to ported tests:
- **[OTP]**: Marks tests that have been ported (for tracking how many tests migrated)
- **[Level0]**: Marks Describe blocks for test files containing "-LEVEL0-" tests (appears as `[sig-<extension-name>][OTP][Level0]` in full test name)

**Important:** This process restructures test names by:
1. Simplifying Describe blocks to just `[sig-<extension-name>][OTP]` or `[sig-<extension-name>][OTP][Level0]`
2. Moving Describe text into It() descriptions
3. Adding `[Level0]` to Describe block (after `[OTP]`) if file contains any tests with "-LEVEL0-"
4. **Removing `-LEVEL0-` suffix** from test names to avoid duplication
   - Before: `"...Author:<author>-LEVEL0-Critical..."`
   - After (in a file with [Level0]): Full test name becomes `"[sig-network-edge][OTP][Level0] ...Author:<author>-Critical..."`

**Note:** The automated script below is a simplified version. For complex test files with multiple Describe blocks, manual adjustment may be needed. The CCO repository required manual restructuring to properly handle multiple Describe blocks ("CCO is enabled" and "CCO is disabled").

**For Monorepo Strategy:**

**IMPORTANT:** Use the actual extension name and test directory name from user inputs.

```bash
cd <working-dir>

# Set variables from user inputs collected in Phase 1
SIG_FILTER_TAGS="<sig-filter-tags>"  # From Input 2 (comma-separated)
TEST_DIR_NAME="<test-dir-name>"       # From Input 5a (defaults to "e2e")

echo "========================================="
echo "Adding [OTP] and [Level0] annotations..."
echo "Sig filter tags: $SIG_FILTER_TAGS"
echo "Test directory: test/$TEST_DIR_NAME"
echo "========================================="

# Convert comma-separated tags to array
IFS=',' read -ra SIG_TAGS <<< "$SIG_FILTER_TAGS"

# Find all test files
TEST_FILES=$(find "test/$TEST_DIR_NAME" -name '*.go' -type f)

for file in $TEST_FILES; do
    CHANGED=0

    # Step 1: Extract Describe block text and simplify to just tags
    # Process each sig tag
    for sig_tag in "${SIG_TAGS[@]}"; do
        sig_tag=$(echo "$sig_tag" | xargs)  # Trim whitespace

        # Check if this file uses this sig tag
        if grep -q "g\.Describe.*\[sig-$sig_tag\]" "$file"; then
            # Extract the Describe text (everything after the tags)
            # Example: "[sig-network-edge] Some Description" -> extract "Some Description"
            DESCRIBE_TEXT=$(grep "g\.Describe.*\[sig-$sig_tag\]" "$file" | sed "s/.*\[sig-$sig_tag\] \(.*\)\".*/\1/" | head -1)

            # Check if file contains any Level0 tests
            HAS_LEVEL0=false
            if grep -q -- '-LEVEL0-' "$file"; then
                HAS_LEVEL0=true
            fi

            if [ -n "$DESCRIBE_TEXT" ]; then
                # Add [OTP] and [Level0] (if needed) to Describe blocks
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP][Level0] /g" "$file"
                    echo "  ✓ Added [OTP][Level0] to [sig-$sig_tag] in $file"
                else
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP] /g" "$file"
                    echo "  ✓ Added [OTP] to [sig-$sig_tag] in $file"
                fi

                # Extract describe text for prepending to It()
                # Then simplify Describe to just tags
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/g\.Describe(\"\[sig-$sig_tag\]\[OTP\]\[Level0\] [^\"]*\"/g.Describe(\"[sig-$sig_tag][OTP][Level0]\"/" "$file"
                else
                    sed -i "s/g\.Describe(\"\[sig-$sig_tag\]\[OTP\] [^\"]*\"/g.Describe(\"[sig-$sig_tag][OTP]\"/" "$file"
                fi

                # Prepend the Describe text to all It() in this file
                # This is approximate - in practice, need to track which Describe block each It belongs to
                sed -i "/g\.It/ s/g\.It(\"/g.It(\"$DESCRIBE_TEXT /" "$file"

                CHANGED=1
                echo "  ✓ Restructured Describe/It for [sig-$sig_tag] in $file"
            else
                # Just add [OTP] and [Level0] (if needed)
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP][Level0] /g" "$file"
                    echo "  ✓ Added [OTP][Level0] to [sig-$sig_tag] in $file"
                else
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP] /g" "$file"
                    echo "  ✓ Added [OTP] to [sig-$sig_tag] in $file"
                fi
                CHANGED=1
            fi
        fi
    done

    # Step 2: Handle Level0 test transformations (prepend [Level0] tag and remove suffix)
    if grep -q -- '-LEVEL0-' "$file"; then
        # First, prepend [Level0] to It() descriptions that contain -LEVEL0- (if not already present)
        # Example: g.It("Author:john-LEVEL0-Critical...") → g.It("[Level0] Author:john-LEVEL0-Critical...")
        sed -i '/g\.It("[^"]*-LEVEL0-[^"]*"/{/\[Level0\]/!s/g\.It("/g.It("[Level0] /}' "$file"

        # Then remove the -LEVEL0- suffix from test names
        # Example: "Author:john-LEVEL0-Critical..." → "Author:john-Critical..."
        sed -i 's/-LEVEL0-/-/g' "$file"

        # Clean up any double dashes that might result from suffix removal
        sed -i 's/--/-/g' "$file"

        CHANGED=1
        echo "  ✓ Added [Level0] prefix and removed -LEVEL0- suffix in $file"
    fi

    if [ $CHANGED -eq 0 ]; then
        echo "  - No annotations needed for $file"
    fi
done

echo "✅ Annotations added successfully"
echo ""
echo "Summary of annotations:"
echo "  [OTP]       - Added to all Describe blocks (tracking)"
echo "  [Level0]    - Added to Describe blocks for files containing -LEVEL0- tests (conformance)"
echo "  [Level0]    - Prepended to It() for tests with -LEVEL0-, suffix removed"
echo "  Test names  - Restructured: Describe text moved into It() descriptions"
```bash

**For Single-Module Strategy:**

**IMPORTANT:** Use sig filter tags from user input. Single-module always uses `test/e2e` directory.

```bash
cd <working-dir>/tests-extension

# Set variables from user inputs collected in Phase 1
SIG_FILTER_TAGS="<sig-filter-tags>"  # From Input 2 (comma-separated)

echo "========================================="
echo "Adding [OTP] and [Level0] annotations..."
echo "Sig filter tags: $SIG_FILTER_TAGS"
echo "Test directory: test/e2e"
echo "========================================="

# Convert comma-separated tags to array
IFS=',' read -ra SIG_TAGS <<< "$SIG_FILTER_TAGS"

# Find all test files (single-module always uses test/e2e)
TEST_FILES=$(find test/e2e -name '*.go' -type f)

for file in $TEST_FILES; do
    CHANGED=0

    # Step 1: Extract Describe block text and simplify to just tags
    # Process each sig tag
    for sig_tag in "${SIG_TAGS[@]}"; do
        sig_tag=$(echo "$sig_tag" | xargs)  # Trim whitespace

        # Check if this file uses this sig tag
        if grep -q "g\.Describe.*\[sig-$sig_tag\]" "$file"; then
            # Extract the Describe text (everything after the tags)
            # Example: "[sig-network-edge] Some Description" -> extract "Some Description"
            DESCRIBE_TEXT=$(grep "g\.Describe.*\[sig-$sig_tag\]" "$file" | sed "s/.*\[sig-$sig_tag\] \(.*\)\".*/\1/" | head -1)

            # Check if file contains any Level0 tests
            HAS_LEVEL0=false
            if grep -q -- '-LEVEL0-' "$file"; then
                HAS_LEVEL0=true
            fi

            if [ -n "$DESCRIBE_TEXT" ]; then
                # Add [OTP] and [Level0] (if needed) to Describe blocks
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP][Level0] /g" "$file"
                    echo "  ✓ Added [OTP][Level0] to [sig-$sig_tag] in $file"
                else
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP] /g" "$file"
                    echo "  ✓ Added [OTP] to [sig-$sig_tag] in $file"
                fi

                # Extract describe text for prepending to It()
                # Then simplify Describe to just tags
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/g\.Describe(\"\[sig-$sig_tag\]\[OTP\]\[Level0\] [^\"]*\"/g.Describe(\"[sig-$sig_tag][OTP][Level0]\"/" "$file"
                else
                    sed -i "s/g\.Describe(\"\[sig-$sig_tag\]\[OTP\] [^\"]*\"/g.Describe(\"[sig-$sig_tag][OTP]\"/" "$file"
                fi

                # Prepend the Describe text to all It() in this file
                # This is approximate - in practice, need to track which Describe block each It belongs to
                sed -i "/g\.It/ s/g\.It(\"/g.It(\"$DESCRIBE_TEXT /" "$file"

                CHANGED=1
                echo "  ✓ Restructured Describe/It for [sig-$sig_tag] in $file"
            else
                # Just add [OTP] and [Level0] (if needed)
                if [ "$HAS_LEVEL0" = true ]; then
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP][Level0] /g" "$file"
                    echo "  ✓ Added [OTP][Level0] to [sig-$sig_tag] in $file"
                else
                    sed -i "s/\(\[sig-$sig_tag\]\)\s*/\1[OTP] /g" "$file"
                    echo "  ✓ Added [OTP] to [sig-$sig_tag] in $file"
                fi
                CHANGED=1
            fi
        fi
    done

    # Step 2: Handle Level0 test transformations (prepend [Level0] tag and remove suffix)
    if grep -q -- '-LEVEL0-' "$file"; then
        # First, prepend [Level0] to It() descriptions that contain -LEVEL0- (if not already present)
        # Example: g.It("Author:john-LEVEL0-Critical...") → g.It("[Level0] Author:john-LEVEL0-Critical...")
        sed -i '/g\.It("[^"]*-LEVEL0-[^"]*"/{/\[Level0\]/!s/g\.It("/g.It("[Level0] /}' "$file"

        # Then remove the -LEVEL0- suffix from test names
        # Example: "Author:john-LEVEL0-Critical..." → "Author:john-Critical..."
        sed -i 's/-LEVEL0-/-/g' "$file"

        # Clean up any double dashes that might result from suffix removal
        sed -i 's/--/-/g' "$file"

        CHANGED=1
        echo "  ✓ Added [Level0] prefix and removed -LEVEL0- suffix in $file"
    fi

    if [ $CHANGED -eq 0 ]; then
        echo "  - No annotations needed for $file"
    fi
done

echo "✅ Annotations added successfully"
echo ""
echo "Summary of annotations:"
echo "  [OTP]       - Added to all Describe blocks (tracking)"
echo "  [Level0]    - Added to Describe blocks for files containing -LEVEL0- tests (conformance)"
echo "  [Level0]    - Prepended to It() for tests with -LEVEL0-, suffix removed"
echo "  Test names  - Restructured: Describe text moved into It() descriptions"
```bash


#### Step 5: Validate Tags and Annotations

**Purpose:** Verify that all required tags are properly applied before proceeding to build verification.

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo ""
echo "========================================="
echo "Validating tags and annotations..."
echo "========================================="

VALIDATION_FAILED=0

# Find all test files
TEST_FILES=$(find test/<test-dir-name> -name '*_test.go' -type f)
TOTAL_FILES=$(echo "$TEST_FILES" | wc -l)

echo "Found $TOTAL_FILES test files to validate"

# Validation 1: Check for [sig-<extension-name>] tag in all test files
echo ""
echo "Validation 1: Checking for [sig-<extension-name>] tags..."
MISSING_SIG_TAG=0
for file in $TEST_FILES; do
    if ! grep -q '\[sig-<extension-name>\]' "$file"; then
        echo "  ❌ Missing [sig-<extension-name>] tag in: $file"
        MISSING_SIG_TAG=$((MISSING_SIG_TAG + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $MISSING_SIG_TAG -eq 0 ]; then
    echo "  ✅ All test files have [sig-<extension-name>] tag"
else
    echo "  ❌ $MISSING_SIG_TAG file(s) missing [sig-<extension-name>] tag"
fi

# Validation 2: Check for [OTP] tag in Describe blocks
echo ""
echo "Validation 2: Checking for [OTP] tags in Describe blocks..."
MISSING_OTP_TAG=0
for file in $TEST_FILES; do
    if grep -q 'g\.Describe.*\[sig-<extension-name>\]' "$file"; then
        if ! grep -q 'g\.Describe.*\[sig-<extension-name>\]\[OTP\]' "$file"; then
            echo "  ❌ Missing [OTP] tag in: $file"
            MISSING_OTP_TAG=$((MISSING_OTP_TAG + 1))
            VALIDATION_FAILED=1
        fi
    fi
done

if [ $MISSING_OTP_TAG -eq 0 ]; then
    echo "  ✅ All Describe blocks have [OTP] tag"
else
    echo "  ❌ $MISSING_OTP_TAG file(s) missing [OTP] tag"
fi

# Validation 3: Check that -LEVEL0- suffix is removed from tests with [Level0] tag
echo ""
echo "Validation 3: Checking for -LEVEL0- suffix removal..."
LEVEL0_NOT_REMOVED=0
for file in $TEST_FILES; do
    # Check if file has [Level0] tag and still contains -LEVEL0-
    if grep -q '\[Level0\]' "$file" && grep -q -- '-LEVEL0-' "$file"; then
        echo "  ⚠️  File has [Level0] tag but still contains -LEVEL0- suffix: $file"
        LEVEL0_NOT_REMOVED=$((LEVEL0_NOT_REMOVED + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $LEVEL0_NOT_REMOVED -eq 0 ]; then
    echo "  ✅ No duplicate -LEVEL0- suffixes found"
else
    echo "  ❌ $LEVEL0_NOT_REMOVED file(s) have [Level0] tag but still contain -LEVEL0- suffix"
fi

# Validation 4: Verify testdata imports are present
echo ""
echo "Validation 4: Checking for testdata imports..."

# Flatten test directory path for import validation (e.g., e2e/extension → e2e-extension)
TESTDATA_DIR_NAME=$(echo "<test-dir-name>" | tr '/' '-')

MISSING_TESTDATA_IMPORT=0
for file in $TEST_FILES; do
    # Only check files that use testdata.FixturePath
    if grep -q 'testdata\.FixturePath' "$file"; then
        if ! grep -q "\"$MODULE_NAME/test/${TESTDATA_DIR_NAME}-testdata\"" "$file" && \
           ! grep -q 'testdata "' "$file"; then
            echo "  ❌ Missing testdata import in: $file"
            MISSING_TESTDATA_IMPORT=$((MISSING_TESTDATA_IMPORT + 1))
            VALIDATION_FAILED=1
        fi
    fi
done

if [ $MISSING_TESTDATA_IMPORT -eq 0 ]; then
    echo "  ✅ All files using testdata.FixturePath have proper imports"
else
    echo "  ❌ $MISSING_TESTDATA_IMPORT file(s) missing testdata import"
fi

# Summary
echo ""
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo "Total test files validated: $TOTAL_FILES"
echo ""

if [ $VALIDATION_FAILED -eq 0 ]; then
    echo "✅ All validations passed!"
    echo "Migration is ready to proceed to build verification"
else
    echo "❌ Validation failed!"
    echo ""
    echo "Please review and fix the issues above before proceeding."
    echo "Common fixes:"
    echo "  - Re-run Step 4 (Add OTP and Level0 Annotations)"
    echo "  - Manually add missing tags to affected files"
    echo "  - Check that sed commands executed successfully"
    echo ""
    echo "After fixing, you can re-run this validation step."
    exit 1
fi
```bash

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo ""
echo "========================================="
echo "Validating tags and annotations..."
echo "========================================="

VALIDATION_FAILED=0

# Find all test files
TEST_FILES=$(find test/e2e -name '*_test.go' -type f)
TOTAL_FILES=$(echo "$TEST_FILES" | wc -l)

echo "Found $TOTAL_FILES test files to validate"

# Validation 1: Check for [sig-<extension-name>] tag in all test files
echo ""
echo "Validation 1: Checking for [sig-<extension-name>] tags..."
MISSING_SIG_TAG=0
for file in $TEST_FILES; do
    if ! grep -q '\[sig-<extension-name>\]' "$file"; then
        echo "  ❌ Missing [sig-<extension-name>] tag in: $file"
        MISSING_SIG_TAG=$((MISSING_SIG_TAG + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $MISSING_SIG_TAG -eq 0 ]; then
    echo "  ✅ All test files have [sig-<extension-name>] tag"
else
    echo "  ❌ $MISSING_SIG_TAG file(s) missing [sig-<extension-name>] tag"
fi

# Validation 2: Check for [OTP] tag in Describe blocks
echo ""
echo "Validation 2: Checking for [OTP] tags in Describe blocks..."
MISSING_OTP_TAG=0
for file in $TEST_FILES; do
    if grep -q 'g\.Describe.*\[sig-<extension-name>\]' "$file"; then
        if ! grep -q 'g\.Describe.*\[sig-<extension-name>\]\[OTP\]' "$file"; then
            echo "  ❌ Missing [OTP] tag in: $file"
            MISSING_OTP_TAG=$((MISSING_OTP_TAG + 1))
            VALIDATION_FAILED=1
        fi
    fi
done

if [ $MISSING_OTP_TAG -eq 0 ]; then
    echo "  ✅ All Describe blocks have [OTP] tag"
else
    echo "  ❌ $MISSING_OTP_TAG file(s) missing [OTP] tag"
fi

# Validation 3: Check that -LEVEL0- suffix is removed from tests with [Level0] tag
echo ""
echo "Validation 3: Checking for -LEVEL0- suffix removal..."
LEVEL0_NOT_REMOVED=0
for file in $TEST_FILES; do
    # Check if file has [Level0] tag and still contains -LEVEL0-
    if grep -q '\[Level0\]' "$file" && grep -q -- '-LEVEL0-' "$file"; then
        echo "  ⚠️  File has [Level0] tag but still contains -LEVEL0- suffix: $file"
        LEVEL0_NOT_REMOVED=$((LEVEL0_NOT_REMOVED + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $LEVEL0_NOT_REMOVED -eq 0 ]; then
    echo "  ✅ No duplicate -LEVEL0- suffixes found"
else
    echo "  ❌ $LEVEL0_NOT_REMOVED file(s) have [Level0] tag but still contain -LEVEL0- suffix"
fi

# Validation 4: Verify testdata imports are present
echo ""
echo "Validation 4: Checking for testdata imports..."
MISSING_TESTDATA_IMPORT=0
for file in $TEST_FILES; do
    # Only check files that use testdata.FixturePath
    if grep -q 'testdata\.FixturePath' "$file"; then
        if ! grep -q '"github.com/openshift/<extension-name>-tests-extension/test/testdata"' "$file" && \
           ! grep -q 'testdata "' "$file"; then
            echo "  ❌ Missing testdata import in: $file"
            MISSING_TESTDATA_IMPORT=$((MISSING_TESTDATA_IMPORT + 1))
            VALIDATION_FAILED=1
        fi
    fi
done

if [ $MISSING_TESTDATA_IMPORT -eq 0 ]; then
    echo "  ✅ All files using testdata.FixturePath have proper imports"
else
    echo "  ❌ $MISSING_TESTDATA_IMPORT file(s) missing testdata import"
fi

# Summary
echo ""
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo "Total test files validated: $TOTAL_FILES"
echo ""

if [ $VALIDATION_FAILED -eq 0 ]; then
    echo "✅ All validations passed!"

    # Mark Phase 5 as successful - disable rollback
    PHASE5_FAILED=0
    trap - EXIT  # Remove error trap

    echo "✅ Phase 5 (Test Migration) complete!"
    echo "Migration is ready to proceed to Phase 6 (Dependency Resolution)"
else
    echo "❌ Validation failed!"
    echo ""
    echo "Please review and fix the issues above before proceeding."
    echo "Common fixes:"
    echo "  - Re-run Step 4 (Add OTP and Level0 Annotations)"
    echo "  - Manually add missing tags to affected files"
    echo "  - Check that sed commands executed successfully"
    echo ""
    echo "After fixing, you can re-run this validation step."

    # Mark Phase 5 as failed - trigger rollback
    PHASE5_FAILED=1
    exit 1
fi
```

### Phase 6: Dependency Resolution and Verification (2 steps)

**CRITICAL INSTRUCTION**: Phase 6 must ALWAYS run to completion, even if there are warnings from go mod tidy. Do not stop early or prompt for manual steps. The build verification in Step 2 will determine if there are actual problems. This phase is fully automated.

#### Step 1: Complete Dependency Resolution (Deferred from Phase 4)

**Run the full go mod tidy that was deferred earlier**

**IMPORTANT**: This step should always continue to Step 2 (build verification) even if go mod tidy shows warnings. The build step will verify if dependencies are actually problematic.

**For Monorepo Strategy:**

```bash
cd <working-dir>/test/<test-dir-name>

echo "========================================="
echo "Phase 6 Step 1: Completing dependency resolution"
echo "========================================="

# Now that test files are migrated (Phase 5), run full go mod tidy
# This was deferred from Phase 4 Step 6 to prevent timeout before test migration
echo "Running full go mod tidy in test module (this may take 2-3 minutes)..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -eq 0 ]; then
    echo "✅ Test module dependency resolution complete"
else
    echo "⚠️  go mod tidy had warnings in test module"
    echo "    This is normal - continuing to build verification..."
fi

# Sync replace directives from test module to root module to prevent dependency conflicts
echo ""
echo "Syncing replace directives from test module to root module..."
cd ../..

# Extract replace directives from test module (excluding the self-reference)
TEST_REPLACES=$(grep -A 1000 "^replace (" test/<test-dir-name>/go.mod | grep -v "^replace (" | grep "=>" | grep -v "^)" || echo "")

if [ -n "$TEST_REPLACES" ]; then
    # Ensure root go.mod has a replace block
    if ! grep -q "^replace (" go.mod; then
        echo "" >> go.mod
        echo "replace (" >> go.mod
        echo ")" >> go.mod
    fi

    # Update or add each replace directive
    UPDATED_COUNT=0
    while IFS= read -r replace_line; do
        # Extract the package being replaced (e.g., "k8s.io/api")
        PACKAGE=$(echo "$replace_line" | awk '{print $1}')

        # Skip empty lines
        if [ -z "$PACKAGE" ]; then
            continue
        fi

        # Check if this replace directive exists in root go.mod
        if grep -q "^[[:space:]]*$PACKAGE " go.mod; then
            # Replace existing directive with updated version
            # First, remove the old line
            sed -i "/^[[:space:]]*$PACKAGE /d" go.mod
            # Then add the new line to the replace block
            sed -i "/^replace (/a\\    $replace_line" go.mod
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
        else
            # Add new replace directive to the replace block
            sed -i "/^replace (/a\\    $replace_line" go.mod
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
        fi
    done <<< "$TEST_REPLACES"

    echo "✅ Synced $UPDATED_COUNT replace directives from test module to root go.mod"
else
    echo "⚠️  No replace directives found in test module"
fi

# Now run go mod tidy in root module with synced replace directives
echo ""
echo "Running go mod tidy in root module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -eq 0 ]; then
    echo "✅ Root module dependency resolution complete"
else
    echo "⚠️  go mod tidy had warnings in root module"
    echo "    This is normal - continuing to build verification..."
fi

echo ""
echo "✅ Phase 6 Step 1 complete - proceeding to build verification"
```

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "========================================="
echo "Phase 6: Completing dependency resolution"
echo "========================================="

# Now that test files are migrated (Phase 5), run full go mod tidy
# This was deferred from Phase 4 Step 6 to prevent timeout before test migration
echo "Running full go mod tidy (this may take 2-3 minutes)..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -eq 0 ]; then
    echo "✅ Dependency resolution complete"
else
    echo "⚠️  go mod tidy had errors - you may need to fix import issues manually"
    echo "    Common issues:"
    echo "    - Missing package imports in test files"
    echo "    - Old compat_otp imports not removed"
    echo "    - Check test files for import errors"
fi

cd ..
```

#### Step 2: Verify Build and Test (Required)

**This is Step 3 of the Go module workflow: Build or test to verify everything works**

**IMPORTANT**: This step MUST run automatically. The Makefile target handles bindata generation and build. Do not prompt for manual steps.

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Phase 6 Step 2: Build verification"
echo "========================================="

# Build the extension binary using Makefile
# This will automatically:
# 1. Generate bindata from test/<testdata-dir>-testdata/
# 2. Build the binary to bin/<extension-name>-tests-ext
echo "Building extension binary (includes bindata generation)..."
make extension

if [ $? -eq 0 ]; then
    echo "✅ Extension binary built successfully!"

    # Run a quick test to ensure the binary works
    echo "Testing binary execution..."
    ./bin/<extension-name>-tests-ext --help > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ Binary executes correctly!"
    else
        echo "⚠️  Binary built but --help failed"
    fi

    echo ""
    echo "========================================="
    echo "✅ MIGRATION COMPLETE - FULLY AUTOMATED"
    echo "========================================="
    echo "All phases completed successfully:"
    echo "  ✅ Phase 1: User input collection"
    echo "  ✅ Phase 2: Repository setup"
    echo "  ✅ Phase 3: Structure creation"
    echo "  ✅ Phase 4: Code generation"
    echo "  ✅ Phase 5: Test migration (atomic)"
    echo "  ✅ Phase 6: Dependency resolution and build"
    echo ""
    echo "Ready to commit - no manual steps required!"
    echo "========================================="
    echo "Files to commit:"
    echo "  - go.mod (root module with test/<test-dir-name> replace directive)"
    echo "  - cmd/extension/main.go"
    # Flatten test directory path for display (e.g., e2e/extension → e2e-extension)
    TESTDATA_DISPLAY=$(echo "<test-dir-name>" | tr '/' '-')

    echo "  - test/<test-dir-name>/go.mod"
    echo "  - test/<test-dir-name>/go.sum"
    echo "  - test/<test-dir-name>/*.go (test files)"
    echo "  - test/${TESTDATA_DISPLAY}-testdata/fixtures.go"
    echo "  - test/bindata.mk"
    echo "  - Makefile updates"
else
    echo "❌ Build failed - manual intervention required"
    echo "Common issues:"
    echo "  - Check import paths in test files and cmd/extension/main.go"
    echo "  - Verify all test dependencies are available in test/<test-dir-name>/go.mod"
    echo "  - Run 'go mod tidy' in test/<test-dir-name> directory"
    echo "  - Check for invalid replace directives in test/<test-dir-name>/go.mod"
    echo "  - Ensure root go.mod has: replace $MODULE_NAME/test/<test-dir-name> => ./test/<test-dir-name>"
    exit 1
fi
```bash

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

echo "========================================="
echo "Verifying build and dependencies"
echo "========================================="

# Build the extension binary using Makefile
echo "Building extension binary..."
make build

if [ $? -eq 0 ]; then
    echo "✅ Extension binary built successfully!"

    # Run a quick test to ensure the binary works
    echo "Testing binary execution..."
    ./bin/<extension-name>-tests-ext --help > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ Binary executes correctly!"
    else
        echo "⚠️  Binary built but --help failed"
    fi

    echo ""
    echo "========================================="
    echo "Migration complete - ready to commit"
    echo "========================================="
    echo "Files to commit:"
    echo "  - go.mod"
    echo "  - go.sum"
    echo "  - cmd/main.go"
    echo "  - test/e2e/*.go"
    echo "  - test/testdata/fixtures.go"
    echo "  - Makefile"
    echo "  - bindata.mk"
else
    echo "❌ Build failed - manual intervention required"
    echo "Common issues:"
    echo "  - Check import paths in test files and cmd/main.go"
    echo "  - Verify all test dependencies are available in go.mod"
    echo "  - Run 'go mod tidy' again"
    echo "  - Check for invalid replace directives in go.mod"
    exit 1
fi
```

**Note:** This verification step completes the 4-step Go module workflow:
1. ✅ go mod init (completed in Phase 4)
2. ✅ go get dependencies (completed in Phase 4)
3. ✅ go mod tidy (completed in Phase 4 and Step 1 above)
4. ✅ go build/test to verify (this step)

After successful verification, you're ready to commit both go.mod and go.sum files.

### Phase 7: Documentation (1 step)

#### Generate Migration Summary

Provide a comprehensive summary based on the strategy used:

**For Monorepo Strategy:**

```markdown
# OTE Migration Complete! 🎉

## Summary

Successfully migrated **<extension-name>** to OpenShift Tests Extension (OTE) framework using **monorepo strategy**.

## Created Structure

```bash
<working-dir>/                        # Target repository root
├── bin/
│   └── <extension-name>-tests-ext    # Extension binary
├── cmd/
│   └── extension/
│       └── main.go                   # OTE extension entry point
├── test/
│   ├── e2e/                          # Test files
│   │   ├── go.mod                    # Test module (separate from root)
│   │   ├── go.sum
│   │   └── *_test.go
│   ├── testdata/                     # Testdata files
│   │   ├── bindata.go                # Generated
│   │   └── fixtures.go               # Wrapper functions
│   └── bindata.mk                    # Bindata generation
├── go.mod                            # Root module (with replace directive)
├── Makefile                          # Root Makefile (extension target added)
└── repos/                            # Cloned repositories (if not using local)
    └── openshift-tests-private/      # Source repo
```

## Configuration

**Extension:** <extension-name>
**Strategy:** Multi-module (integrated into existing repo)
**Working Directory:** <working-dir>

**Source Repository:** git@github.com:openshift/openshift-tests-private.git
  - Local Path: <local-source-path> (or "Cloned to repos/openshift-tests-private")
  - Test Subfolder: test/extended/<test-subfolder>/
  - Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

**Module Configuration:**
  - Root Module: $MODULE_NAME
  - Test Module: $MODULE_NAME/test/e2e
  - Replace Directive: Added to root go.mod replace section

## Files Created/Modified

### Generated Code
- ✅ `cmd/extension/main.go` - OTE entry point with platform filters
- ✅ `test/<test-dir-name>/go.mod` - Test module with OpenShift replace directives
- ✅ `test/<flattened-test-dir-name>-testdata/fixtures.go` - Testdata wrapper functions (path flattened)
- ✅ `test/bindata.mk` - Bindata generation rules
- ✅ `go.mod` (updated) - Added test/<test-dir-name> replace directive
- ✅ `Makefile` (updated) - Added extension build target

Note: `<flattened-test-dir-name>` = `<test-dir-name>` with `/` → `-` (e.g., `e2e/extension` → `e2e-extension`)

### Test Files (Fully Automated)
- ✅ Copied **X** test files to `test/<test-dir-name>/`
- ✅ Copied **Y** testdata files to `test/<flattened-test-dir-name>-testdata/`
- ✅ Automatically replaced `compat_otp.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically replaced `exutil.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically added imports: `$MODULE_NAME/test/<flattened-test-dir-name>-testdata`
- ✅ Automatically cleaned up old compat_otp/exutil imports

## Statistics

- **Test files:** X files
- **Testdata files:** Y files (or "none" if not applicable)
- **Test filtering:** Only tests with `[sig-<extension-name>]` tag in name are included
- **Platform filters:** Detected from labels and test names
- **Test suites:** 1 main suite (`<org>/<extension-name>/tests`)

## Next Steps (Monorepo)

### 1. Build Extension

```bash
cd <working-dir>
make extension
```bash

This will generate bindata and build the binary to `bin/<extension-name>-tests-ext`

### 2. Validate Tests

```bash
# List all discovered tests
./bin/<extension-name>-tests-ext list

# Run tests in dry-run mode
./bin/<extension-name>-tests-ext run --dry-run

# Test platform filtering
./bin/<extension-name>-tests-ext run --platform=aws --dry-run
```bash

### 3. Run Tests

```bash
# Run all tests
./bin/<extension-name>-tests-ext run

# Run specific test
./bin/<extension-name>-tests-ext run "test name pattern"
```bash

## Troubleshooting

### Dependency Version Management (IMPORTANT)

**The migration tool now fetches latest versions** of critical dependencies (Kubernetes and ginkgo) directly from their repositories instead of copying from `openshift-tests-private`. This prevents stale dependency issues.

**What changed:**
- ✅ **Old behavior**: Copied all replace directives from `openshift-tests-private/go.mod` (could be outdated)
- ✅ **New behavior**: Dynamically fetches latest commits from:
  - `github.com/openshift/kubernetes` (master branch)
  - `github.com/openshift/onsi-ginkgo` (v2.27.2-openshift-4.22 branch)

**Why this matters:**
Prevents API incompatibility errors such as:
- `undefined: ginkgo.NewWriter`
- `undefined: diff.Diff` (library-go)
- `undefined: otelgrpc.UnaryClientInterceptor` (cri-client)
- `structured-merge-diff/v6 vs v4` type mismatches
- `too many arguments in call to testdata.FixturePath`

**If you encounter version issues:**
1. Check the git ls-remote outputs in Step 5 to verify latest commits are being used
2. Manually update replace directives in `go.mod` if a specific version is required
3. Run `go mod tidy` after any manual changes

**Go Version Compatibility:**

The migration automatically uses `GOTOOLCHAIN=auto GOSUMDB=sum.golang.org` when running `go mod tidy`. This allows Go to automatically download and use a newer toolchain version if required by dependencies.

**If you see errors like:**
```
go: go.mod requires go >= 1.24.6 (running go 1.24.3; GOTOOLCHAIN=local)
```bash

**This is automatically handled by the migration.** The `GOTOOLCHAIN=auto` setting allows Go to download the required version (e.g., go1.24.11) without requiring you to manually upgrade your system Go installation.

**What happens:**
- Your system Go: 1.24.3
- Dependencies require: 1.24.6+
- `GOTOOLCHAIN=auto` downloads: 1.24.11 (as specified in go.mod's toolchain directive)
- Build succeeds using the downloaded toolchain

**If you need to manually run go mod tidy later:**
```bash
cd ~/router/tests-extension
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy
```bash

**Or set it globally in your environment:**
```bash
export GOTOOLCHAIN=auto
export GOSUMDB=sum.golang.org
```bash

### If Dependency Download Was Interrupted

If you see warnings about failed dependency downloads during migration, complete the process manually:

**For Monorepo Strategy:**

```bash
cd <working-dir>/test/e2e

# Complete dependency resolution
go get github.com/openshift-eng/openshift-tests-extension@latest
go get "github.com/openshift/origin@$ORIGIN_VERSION"
go get github.com/onsi/ginkgo/v2@latest
go get github.com/onsi/gomega@latest

# Resolve all dependencies (auto-download required Go version if needed)
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

# Download all modules
go mod download

# Verify files are created
ls -la go.mod go.sum

# Return to root
cd ../..
```

**Root module (if needed):**

```bash
cd <working-dir>

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy
go mod download
```bash

### If Build Fails

```bash
# Check import paths in test files
grep -r "import" test/e2e/*.go

# Verify all dependencies are available
cd test/e2e && go mod verify

# Clean and rebuild
make clean-extension
make tests-ext-build
```bash

**For Single-Module Strategy:**

```markdown
# OTE Migration Complete! 🎉

## Summary

Successfully migrated **<extension-name>** to OpenShift Tests Extension (OTE) framework using **single-module strategy**.

## Created Structure

```bash
<working-dir>/
└── tests-extension/                   # Isolated test extension directory
    ├── cmd/
    │   └── main.go                   # OTE entry point
    ├── test/
    │   ├── e2e/                      # Test files
    │   │   └── *_test.go
    │   └── testdata/                 # Testdata files
    │       ├── bindata.go            # Generated
    │       └── fixtures.go           # Wrapper functions
    ├── vendor/                       # Vendored dependencies
    ├── go.mod                        # Single module
    ├── go.sum
    ├── Makefile                      # Build targets
    └── bindata.mk                    # Bindata generation
```

## Configuration

**Extension:** <extension-name>
**Strategy:** Single-module (isolated directory)
**Working Directory:** <working-dir>

**Source Repository:** git@github.com:openshift/openshift-tests-private.git
  - Local Path: <local-source-path> (or "Cloned to repos/openshift-tests-private")
  - Test Subfolder: test/extended/<test-subfolder>/
  - Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

**Target Repository:** <target-repo-url>
  - Local Path: <local-target-path> (or "Cloned to repos/target")

## Files Created/Modified

### Generated Code
- ✅ `cmd/main.go` - OTE entry point with filters and hooks
- ✅ `test/testdata/fixtures.go` - Testdata wrapper functions
- ✅ `go.mod` - Go module with OTE dependencies
- ✅ `go.sum` - Dependency checksums
- ✅ `Makefile` - Build targets
- ✅ `bindata.mk` - Bindata generation rules

### Test Files (Fully Automated)
- ✅ Copied **X** test files to `test/e2e/`
- ✅ Copied **Y** testdata files to `test/testdata/`
- ✅ Vendored dependencies to `vendor/`
- ✅ Automatically replaced `compat_otp.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically replaced `exutil.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically added imports: `github.com/<org>/<extension-name>-tests-extension/test/testdata`
- ✅ Automatically cleaned up old compat_otp/exutil imports

## Statistics

- **Test files:** X files
- **Testdata files:** Y files (or "none" if not applicable)
- **Test filtering:** Only tests with `[sig-<extension-name>]` tag in name are included
- **Platform filters:** Detected from labels and test names
- **Test suites:** 1 main suite (`<org>/<extension-name>/tests`)

## Next Steps (Single-Module)

### 1. Generate Bindata

```bash
cd <working-dir>/tests-extension
make bindata
```bash

This creates `test/testdata/bindata.go` with embedded test data.

### 2. Update Dependencies

```bash
go get github.com/openshift-eng/openshift-tests-extension@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy
```bash

### 3. Build Extension

```bash
make build
```bash

### 4. Validate Tests

```bash
# List all discovered tests
make list

# Run tests in dry-run mode
./<extension-name> run --dry-run

# Test platform filtering
./<extension-name> run --platform=aws --dry-run
```

### 5. Run Tests

```bash
# Run all tests
./<extension-name> run

# Run specific test
./<extension-name> run "test name pattern"

# Run with platform filter
./<extension-name> run --platform=aws
```bash

### 6. Integrate into Component Dockerfile

To include the OTE extension binary in your component's Docker image, add build steps to your Dockerfile.

**Example multi-stage Dockerfile (following machine-api-operator and machine-config-operator patterns):**

```dockerfile
# Stage 1: Build the extension binary
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

# Copy source code
COPY . .

# Generate testdata bindata
RUN cd test && make bindata

# Build the extension binary
RUN GO111MODULE=on go build -mod=vendor -o /go/bin/extension ./cmd/extension

# Stage 2: Final image with extension binary
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9
COPY --from=builder /go/bin/extension /usr/bin/extension

# ... rest of your Dockerfile
```makefile

**For repos using `make` targets:**

```dockerfile
# Build stage
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

COPY . .

# Build using make target (includes bindata generation)
RUN make extension

# Final stage
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9
COPY --from=builder /go/src/github.com/<org>/<component-name>/extension /usr/bin/extension

# ... rest of your Dockerfile
```bash

**Key points:**
- Build happens in the builder stage with Go toolchain
- `test/bindata.go` is generated before building the binary
- Final binary is copied to `/usr/bin/extension` in the runtime image
- Use vendored dependencies with `-mod=vendor` flag
- The extension binary can be run in the container for test discovery and execution

**Updating your Makefile for Docker builds:**

Add a docker-build target to your root Makefile:

```makefile
.PHONY: docker-build
docker-build:
    docker build -t <component-name>:latest .

.PHONY: docker-extension
docker-extension: docker-build
    docker run --rm <component-name>:latest /usr/bin/extension list
```

## Customization Options

### Test Lifecycle (Informing by Default)

**By default, all migrated tests are set to "informing"** - they will run but won't block CI builds on failure. This is the recommended setting for newly migrated tests to avoid breaking CI while tests are being stabilized.

The generated `main.go` includes this enabled by default:

```go
// Set lifecycle for all migrated tests to Informing
// Tests will run but won't block CI on failure
specs.Walk(func(spec *et.ExtensionTestSpec) {
    spec.Lifecycle = et.LifecycleInforming
})
```bash

**Available lifecycle values:**
- `et.LifecycleInforming` - Test failures won't block CI (default for migrated tests)
- `et.LifecycleBlocking` - Test failures will block CI

**To make specific tests blocking:**

Edit `cmd/main.go` (for single-module) or `cmd/extension/main.go` (for monorepo) to customize:

```go
// Make Level0 tests blocking, all others informing
specs.Walk(func(spec *et.ExtensionTestSpec) {
    if strings.Contains(spec.Name, "[Level0]") {
        spec.Lifecycle = et.LifecycleBlocking
    } else {
        spec.Lifecycle = et.LifecycleInforming
    }
})
```bash

**To make ALL tests blocking:**

Comment out or remove the informing lifecycle code if you want all tests to block CI.

### Add More Environment Filters

Edit `cmd/main.go` and add filters:

```go
// Network filter
specs.Walk(func(spec *et.ExtensionTestSpec) {
    if strings.Contains(spec.Name, "[network:ovn]") {
        spec.Include(et.NetworkEquals("ovn"))
    }
})

// Topology filter
specs.Walk(func(spec *et.ExtensionTestSpec) {
    re := regexp.MustCompile(` + "`\\[topology:(ha|single)\\]`" + `)
    if match := re.FindStringSubmatch(spec.Name); match != nil {
        spec.Include(et.TopologyEquals(match[1]))
    }
})
```bash

### Add Custom Test Suites

```go
// Slow tests suite
ext.AddSuite(e.Suite{
    Name: "<org>/<extension-name>/slow",
    Qualifiers: []string{
        ` + "`labels.exists(l, l==\"SLOW\")`" + `,
    },
})

// Conformance tests suite
ext.AddSuite(e.Suite{
    Name: "<org>/<extension-name>/conformance",
    Qualifiers: []string{
        ` + "`labels.exists(l, l==\"Conformance\")`" + `,
    },
})
```

### Add More Hooks

```go
// Before each test
specs.AddBeforeEach(func() {
    // Setup for each test
})

// After each test
specs.AddAfterEach(func(res *et.ExtensionTestResult) {
    if res.Result == et.ResultFailed {
        // Collect diagnostics on failure
    }
})
```bash

## Important Notes

- **Always run `make bindata` before building** to regenerate embedded testdata
- **`test/testdata/bindata.go` is generated** - not committed to git
- **go-bindata is auto-installed** - Makefile uses `go install` if not present
- **Use `testdata.FixturePath()`** in tests to replace `compat_otp.FixturePath()`
- **Cleanup is automatic** - `CleanupFixtures()` hook is already added

## Troubleshooting

### Tests not discovered
- Check that test files are in `test/e2e/`
- Verify imports in `cmd/main.go`
- Ensure test packages are imported correctly
- Run `go mod tidy` and `go mod vendor` to refresh dependencies

### Bindata errors
- Run `make bindata` before building
- Check that `test/testdata/` exists and contains files
- Ensure go-bindata is installed (Makefile auto-installs it)

### Platform filters not working
- Check test name patterns (case-sensitive)
- Verify label format: `Platform:aws` (capital P)
- Test with: `./<extension-name> run --platform=aws --dry-run`

## Resources

- [OTE Framework Enhancement](https://github.com/openshift/enhancements/pull/1676)
- [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension)
- [Environment Selectors Documentation](https://github.com/openshift-eng/openshift-tests-extension/blob/main/pkg/extension/extensiontests/environment.go)

```

## Validation Steps

After migration, guide the user through validation:

1. **Build the extension:**
   ```bash
   cd <working-dir>/tests-extension
   make build
```bash

2. **List tests:**
   ```bash
   ./<extension-name> list
   ```

3. **Run dry-run:**
   ```bash
   ./<extension-name> run --dry-run
```bash

4. **Verify environment filtering:**
   ```bash
   ./<extension-name> run --platform=aws --dry-run
   ./<extension-name> run --platform=gcp --dry-run
   ```

5. **Run actual tests:**
   ```bash
   # Run all tests
   ./<extension-name> run

   # Run specific test
   ./<extension-name> run "test name"
```bash

## Testing Docker Image Integration

After updating the Dockerfile to include the OTE extension binary, you should test that the build process works correctly and the binary is properly included in the image.

### Testing Monorepo Strategy

**For Monorepo Strategy (binary in `bin/`):**

```bash
cd <target-repo-root>

# Step 1: Build the Docker image
docker build -t <component-name>:test .

# Step 2: Verify the compressed binary exists in the image
docker run --rm <component-name>:test ls -lh /usr/bin/<extension-name>-tests-ext.gz

# Expected output:
# -rw-r--r-- 1 root root 15M <date> /usr/bin/<extension-name>-tests-ext.gz

# Step 3: Extract and decompress the binary for inspection
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz | file -"

# Expected output:
# /dev/stdin: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, Go BuildID=...

# Step 4: Test the binary executes correctly
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz > /tmp/ext && chmod +x /tmp/ext && /tmp/ext --help"

# Expected output: Help message from the OTE extension binary

# Step 5: Verify binary size (compressed vs uncompressed)
echo "Compressed size:"
docker run --rm <component-name>:test ls -lh /usr/bin/<extension-name>-tests-ext.gz | awk '{print $5}'

echo "Uncompressed size:"
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz | wc -c | numfmt --to=iec-i --suffix=B"

# Step 6: Extract the binary locally for testing
docker run --rm <component-name>:test cat /usr/bin/<extension-name>-tests-ext.gz > /tmp/<extension-name>-tests-ext.gz
gzip -d /tmp/<extension-name>-tests-ext.gz
chmod +x /tmp/<extension-name>-tests-ext
/tmp/<extension-name>-tests-ext list

# Cleanup
rm -f /tmp/<extension-name>-tests-ext
```bash

### Testing Single-Module Strategy

**For Single-Module Strategy (binary in `tests-extension/bin/`):**

```bash
cd <target-repo-root>

# Step 1: Verify the root Makefile target works
make tests-ext-build

# Expected output:
# Building OTE test extension binary...
# Binary built successfully at tests-extension/bin/<extension-name>-tests-ext

# Step 2: Test local compression
gzip -c tests-extension/bin/<extension-name>-tests-ext > /tmp/<extension-name>-tests-ext.gz
ls -lh /tmp/<extension-name>-tests-ext.gz

# Step 3: Verify the compressed binary can be decompressed and executed
gzip -dc /tmp/<extension-name>-tests-ext.gz > /tmp/<extension-name>-tests-ext
chmod +x /tmp/<extension-name>-tests-ext
/tmp/<extension-name>-tests-ext --help

# Step 4: Build the Docker image
docker build -t <component-name>:test .

# Step 5: Verify the compressed binary exists in the image
docker run --rm <component-name>:test ls -lh /usr/bin/<extension-name>-tests-ext.gz

# Step 6: Test the binary executes correctly in the container
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz > /tmp/ext && chmod +x /tmp/ext && /tmp/ext --help"

# Step 7: Compare image size with and without compression
docker images <component-name>:test

# Cleanup
rm -f /tmp/<extension-name>-tests-ext /tmp/<extension-name>-tests-ext.gz
```bash

### Common Validation Checks

**1. Verify Build Process:**
```bash
# Check that the Makefile target is called correctly in Dockerfile
docker build --progress=plain -t <component-name>:test . 2>&1 | grep -A 5 "tests-ext-build"

# Expected output should show:
# RUN make tests-ext-build
# Building OTE test extension binary...
# Binary built successfully
```

**2. Verify Compression Ratio:**
```bash
# Compare sizes - compression should reduce size by 60-70%
ORIGINAL_SIZE=$(docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz | wc -c")
COMPRESSED_SIZE=$(docker run --rm <component-name>:test stat -c%s /usr/bin/<extension-name>-tests-ext.gz)

echo "Original size: $(numfmt --to=iec-i --suffix=B $ORIGINAL_SIZE)"
echo "Compressed size: $(numfmt --to=iec-i --suffix=B $COMPRESSED_SIZE)"
echo "Compression ratio: $(echo "scale=2; 100 - ($COMPRESSED_SIZE * 100 / $ORIGINAL_SIZE)" | bc)%"
```bash

**3. Test Binary Functionality in Container:**
```bash
# Create a test container
docker run -it --rm <component-name>:test sh

# Inside the container:
cd /tmp
gzip -dc /usr/bin/<extension-name>-tests-ext.gz > extension
chmod +x extension

# List available tests
./extension list

# Run tests in dry-run mode
./extension run --dry-run

# Exit container
exit
```bash

**4. Verify Binary Architecture:**
```bash
# Ensure binary matches container architecture
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz | file -"

# Expected: ELF 64-bit LSB executable, x86-64 (or arm64 for ARM images)
```bash

### Troubleshooting Docker Build

**Problem: Binary not found in builder stage**
```bash
# Debug the builder stage
docker build --target builder -t <component-name>:builder .
docker run --rm <component-name>:builder ls -la bin/
docker run --rm <component-name>:builder ls -la tests-extension/bin/
```

**Problem: Compression fails**
```bash
# Check if binary exists before compression
docker build --target builder -t <component-name>:builder .
docker run --rm <component-name>:builder sh -c "ls -la bin/<extension-name>-tests-ext || ls -la tests-extension/bin/<extension-name>-tests-ext"
```bash

**Problem: Binary path mismatch in COPY command**
```bash
# Inspect builder image to find correct path
docker build --target builder -t <component-name>:builder .
docker run --rm <component-name>:builder find /go/src -name "<extension-name>-tests-ext.gz"
```bash

**Problem: Binary won't execute in final image**
```bash
# Check binary permissions and dependencies
docker run --rm <component-name>:test sh -c "gzip -dc /usr/bin/<extension-name>-tests-ext.gz > /tmp/ext && chmod +x /tmp/ext && ldd /tmp/ext"

# If you see "not a dynamic executable", the binary is statically linked (good!)
# If you see missing libraries, check CGO_ENABLED settings in build
```bash

### CI/CD Integration Testing

**Test in OpenShift CI Environment:**

```bash
# Example: Test with podman (used in OpenShift CI)
podman build -t <component-name>:test .
podman run --rm <component-name>:test ls -lh /usr/bin/<extension-name>-tests-ext.gz

# Test with specific builder image versions
podman build --build-arg BUILDER_IMAGE=registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.22-openshift-4.18 -t <component-name>:test .
```

**Create a Simple Test Script:**

```bash
#!/bin/bash
# test-docker-ote.sh

set -e

IMAGE_NAME="${1:-<component-name>:test}"
EXTENSION_NAME="${2:-<extension-name>}"

echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

echo "Checking binary exists..."
docker run --rm "$IMAGE_NAME" ls -lh /usr/bin/${EXTENSION_NAME}-tests-ext.gz

echo "Testing binary extraction and execution..."
docker run --rm "$IMAGE_NAME" sh -c "
    gzip -dc /usr/bin/${EXTENSION_NAME}-tests-ext.gz > /tmp/ext && \
    chmod +x /tmp/ext && \
    /tmp/ext --help
"

echo "✅ Docker image validation complete!"
```bash

**Usage:**
```bash
chmod +x test-docker-ote.sh
./test-docker-ote.sh <component-name>:test <extension-name>
```bash

## Important Implementation Notes

### Git Repository Handling

- Always check if `repos/source` and `repos/target` exist before cloning
- Use `git fetch && git pull` for updates
- Handle authentication errors gracefully
- Allow user to specify branch if needed (default: main/master)

### Error Handling

- Verify directories exist before copying
- Check for write permissions
- Warn if files will be overwritten
- Validate Go module structure
- Ensure testdata path is not empty if files are being copied

### Template Placeholders

Replace these placeholders with actual values:
- `<extension-name>` - Extension name from user input
- `<org>` - Organization extracted from target repo URL
- `<working-dir>` - Working directory path
- `<target-repo-url>` - Target repository URL
- `<source-test-path>` - Source test file path (from openshift-tests-private)
- `<source-testdata-path>` - Source testdata path (from openshift-tests-private)

## Begin Migration

Start by collecting all user inputs from Phase 1, then proceed through each phase systematically!
