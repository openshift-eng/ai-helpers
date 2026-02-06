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
The command implements an interactive 7-phase migration workflow:
1. **User Input Collection** - Gather all configuration (extension name, directory strategy, repository paths, test subfolders)
2. **Repository Setup** - Clone/update source (openshift-tests-private) and target repositories
3. **Structure Creation** - Create directory layout (supports both monorepo and single-module strategies)
4. **Code Generation** - Generate main.go, Makefile, go.mod, fixtures.go, and bindata configuration
5. **Test Migration** - Automatically replace FixturePath calls, update imports, and add OTP/Level0 annotations (per-Describe-block, not per-file)
6. **Dependency Resolution and Verification** - Run go mod tidy and verify build
7. **Documentation** - Generate comprehensive migration summary with next steps

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

### Phase 1: User Input Collection (up to 11 inputs, some conditional)

Collect all necessary information from the user before starting the migration.

**CRITICAL INSTRUCTION FOR AI AGENT:**
- **Input Collection Order is IMPORTANT**: Follow the exact order below
- **Extension name (Input 4)**: AUTO-DETECT from target repository - do NOT ask user
- **Sig filter tags (Input 5)**: AUTO-DETECT from source test files with user confirmation
- **All other inputs**: Ask user explicitly using AskUserQuestion tool or direct prompts
- **WAIT for user response** before proceeding to the next input or phase
- **Switch to target repository** happens after Input 3 (before auto-detecting extension name)

**Important Notes:**
- Source repository is always `git@github.com:openshift/openshift-tests-private.git`
- Variables collected (shown as `<variable-name>`) will be used throughout the migration:
  - `<structure-strategy>` - "monorepo" or "single-module" (from Input 1)
  - `<working-dir>` - Working directory path (workspace) (from Input 2)
  - `<target-repo-path>` or `<target-repo-url>` - Target repository (from Input 3)
  - `<extension-name>` - Extension name (auto-detected from Input 4, AFTER switching to target repo)
  - `<sig-filter-tags>` - Comma-separated sig tags for test filtering (from Input 5)
  - `<test-dir-name>` - Test directory name, defaults to "e2e" (from Input 6, monorepo only)
  - All file paths and code templates use these variables

#### Input 1: Directory Structure Strategy

Ask: "Which directory structure strategy do you want to use?"

**Option 1: Monorepo strategy (integrate into existing repo)**
- Integrates into existing repository structure
- Uses existing `cmd/` and `test/` directories
- **Two variants depending on whether test/e2e already exists:**

**IMPORTANT - Directory Structure is ENFORCED:**
- Base path `test/e2e/` is **REQUIRED** by OTE framework conventions
- Only the subdirectory name in Variant B is customizable (default: 'extension')
- These paths cannot be changed to other locations (e.g., cannot use `tests/e2e/` or `testing/e2e/`)

**Variant A: test/e2e doesn't exist (fresh migration)**
- Files created:
  - `test/e2e/cmd/main.go` - Extension binary **INSIDE test module** (at test/e2e root level)
  - `bin/<extension-name>-tests-ext` - Compiled binary (created by make)
  - `test/e2e/go.mod` - Separate test module
  - `test/e2e/*.go` - Test files (in test module)
  - `test/e2e/testdata/` - Test data (inside test module)
- Build command: `cd test/e2e && go build -o ../../bin/<ext> ./cmd`
- Root `go.mod` updated with replace directive for test module
- **Why cmd is inside test module:** Keeps cmd in the same module as tests for ginkgo discovery (consistent with Variant B)
- Best for: Repos without existing test/e2e structure

**Variant B: test/e2e exists (subdirectory mode)**
- Files created:
  - `test/e2e/<test-dir-name>/cmd/main.go` - Extension binary **INSIDE test module** (default: 'extension')
  - `bin/<extension-name>-tests-ext` - Compiled binary (created by make)
  - `test/e2e/<test-dir-name>/go.mod` - Separate test module in subdirectory
  - `test/e2e/<test-dir-name>/*.go` - Test files (in test module subdirectory)
  - `test/e2e/<test-dir-name>/testdata/` - Test data (inside test module)
- Build command: `cd test/e2e/<test-dir-name> && go build -o ../../../bin/<ext> ./cmd`
- Root `go.mod` updated with replace directive for test module
- **Why cmd is inside test module:** When test module is separate (has go.mod), ginkgo can only discover tests within that module. The cmd must be in the same module as the tests.
- **Note:** `<test-dir-name>` is user-specified subdirectory name (default: 'extension'). See Input 6.
- Best for: Repos with existing test/e2e directory

**Option 2: Single-module strategy (isolated directory)**
- Creates isolated `tests-extension/` directory
- Self-contained with single `go.mod`

**IMPORTANT - Directory Structure is ENFORCED:**
- Base path `tests-extension/test/e2e/` is **REQUIRED** by OTE framework conventions
- The `tests-extension/` name is fixed (cannot use other names like `test-extension/` or `tests/`)
- The internal structure `test/e2e/` inside tests-extension is also fixed

- Files created:
  - `tests-extension/cmd/main.go`
  - `tests-extension/test/e2e/*.go`
  - `tests-extension/test/e2e/testdata/`
  - `tests-extension/test/e2e/bindata.mk`
  - `tests-extension/go.mod`
- No changes to existing repo structure
- Best for: Standalone test extensions or repos without existing test structure

User selects: **1** or **2**

Store the selection in variable: `<structure-strategy>` (value: "monorepo" or "single-module")

#### Input 2: Working Directory (Workspace)

Ask: "What is the working directory path for migration workspace?

**IMPORTANT**: This is a temporary workspace for cloning repositories. Your target repository will be collected in the next step (Input 3), and that's where tests-extension/ (or test/e2e/) will be created."

**Purpose of this workspace directory**:
- **Temporary location** for cloning repositories that don't exist locally:
  - openshift-tests-private (source repo) - if not already available locally
  - Target repository (if you provide a Git URL in Input 3 instead of a local path)
- **Recommendation**: If your target repository already exists locally, provide its parent directory here (e.g., `/home/user/repos` if target is `/home/user/repos/router`)
- Example: `/home/user/repos` (parent of target), `.` (current dir), `/tmp/workspace` (temporary)

**User provides the path:**
- Can provide existing directory (e.g., parent directory of your target repo)
- Can provide current directory (`.`) as workspace
- Can provide a new directory path (we'll create it)
- Path can be absolute or relative

**Store in variable:** `<working-dir>`

**IMPORTANT**: After Input 3 (Target Repository), the working directory will switch to the target repository where all OTE files (tests-extension/ or test/e2e/) will be created. This workspace is only for temporary cloning operations.

#### Input 3: Target Repository

This input collects the target repository information and then **immediately switches** to it.

**CRITICAL**: After this input, the working directory becomes the target repository. All subsequent inputs and operations happen in the target repository context.

**Note**: BOTH strategies require the target repository:
- Both strategies can use either local path OR Git URL to clone
- The target repository is where OTE files will be created

**For both strategies:**

Ask: "What is the path to your target repository, or provide a Git URL to clone?"

- **Option 1: Local path** - Use existing local repository
  - Can be absolute path: `/home/user/repos/router` or `/home/user/repos/sdn`
  - Can be relative path: `~/openshift/cloud-credential-operator` or `../sdn`
  - Can be current directory if you're already in the target repo: `.`
  - Should be a git repository (will be validated below)
  - Store in variable: `<target-repo-path>`
- **Option 2: Git URL** - Clone from remote repository
  - Example: `git@github.com:openshift/router.git` or `git@github.com:openshift/sdn.git`
  - Will be cloned to `<workspace>/<repo-name>` (e.g., `router` or `sdn`)
  - Store in variable: `<target-repo-url>`

#### Input 3a: Update Local Target Repository (if local target provided)

**Skip this if target repository was not provided as local path (will be cloned instead).**

If a local target repository path was provided in Input 3:

Ask: "Do you want to update the local target repository? (git fetch && git pull) [Y/n]:"
- Default: Yes
- If yes: Run `git fetch && git pull` in the target repo
- If no: Use current state

**Store user's choice.**

#### Input 3b: Validate and Switch to Target Repository

**For both strategies**, after collecting target repo information:

**Step 1: Validate and update target repository**

For both strategies if local path provided:
```bash
# Validate target repository exists
if [ ! -d "$TARGET_REPO_PATH" ]; then
    echo "❌ ERROR: Target repository does not exist at: $TARGET_REPO_PATH"
    exit 1
fi

# Check if it's a git repository
if [ -d "$TARGET_REPO_PATH/.git" ]; then
    cd "$TARGET_REPO_PATH"

    # Update repository if user requested (from Input 3a)
    if [ "<update-target>" = "yes" ]; then
        echo "Updating target repository..."

        # Check current branch
        CURRENT_BRANCH=$(git branch --show-current)
        echo "Repository is on branch '$CURRENT_BRANCH'"

        # Discover remote name (don't assume 'origin')
        TARGET_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
        if [ -z "$TARGET_REMOTE" ]; then
            echo "⚠️  WARNING: No git remote found, skipping update"
        else
            echo "Updating from remote: $TARGET_REMOTE"
            git fetch "$TARGET_REMOTE"
            git pull "$TARGET_REMOTE" "$CURRENT_BRANCH"
        fi
    fi

    # Check git status
    if ! git diff-index --quiet HEAD --; then
        echo "⚠️  WARNING: Target repository has uncommitted changes"
        echo "Please commit or stash changes before proceeding"
        # Ask user if they want to continue anyway
        read -p "Continue anyway? [y/N]: " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    echo "✅ Target repository validated: $TARGET_REPO_PATH"
else
    echo "⚠️  WARNING: Target repository is not a git repository: $TARGET_REPO_PATH"
    echo "Proceeding with migration..."
fi
```

For both strategies if URL provided (need to clone):
```bash
# Extract repository name from URL
# Example: git@github.com:openshift/router.git → router
REPO_NAME=$(echo "$TARGET_REPO_URL" | sed -E 's|.*/([^/]+)\.git$|\1|' | sed -E 's|.*:([^/]+)\.git$|\1|')

if [ -z "$REPO_NAME" ]; then
    echo "❌ ERROR: Could not extract repository name from URL: $TARGET_REPO_URL"
    exit 1
fi

echo "Detected repository name: $REPO_NAME"

# Clone to workspace
cd "$WORKING_DIR"
git clone "$TARGET_REPO_URL" "$REPO_NAME"
TARGET_REPO_PATH="$WORKING_DIR/$REPO_NAME"
echo "✅ Target repository cloned to: $TARGET_REPO_PATH"

# Create feature branch for OTE migration
cd "$TARGET_REPO_PATH"
BRANCH_NAME="ote-migration-$(date +%Y%m%d)"
git checkout -b "$BRANCH_NAME"
echo "✅ Created feature branch: $BRANCH_NAME"
```

**Step 2: Switch working directory to target repository**

**CRITICAL - This switch happens NOW, before extension name detection:**

```bash
cd "$TARGET_REPO_PATH"
WORKING_DIR="$TARGET_REPO_PATH"

echo ""
echo "========================================="
echo "Switched to target repository"
echo "========================================="
echo "Working directory is now: $WORKING_DIR"
echo ""
echo "All subsequent operations will happen in this directory."
echo "Extension name will be auto-detected from this repository."
echo "========================================="
```

**Store the final values:**
- `<target-repo-path>` = absolute path to target repository
- `<working-dir>` = same as `<target-repo-path>` (switched)

**From this point forward, all operations use `$WORKING_DIR` which is now the target repository.**

#### Input 4: Extension Name (Auto-Detection)

**DO NOT ask the user for this - auto-detect it from the target repository.**

Now that we're in the target repository, auto-detect the extension name from the repository:

```bash
# We're now in target repository ($WORKING_DIR)
cd "$WORKING_DIR"

# Try to detect from git remote first
if [ -d ".git" ]; then
    # Discover available remotes first (no hardcoded assumptions)
    DISCOVERED_REMOTE=$(git remote -v | head -1 | awk '{print $1}')

    # Get the repository URL from discovered remote
    if [ -n "$DISCOVERED_REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$DISCOVERED_REMOTE" 2>/dev/null)
    else
        REMOTE_URL=""
    fi

    if [ -n "$REMOTE_URL" ]; then
        # Extract repo name from URL
        # Handle both git@github.com:org/repo.git and https://github.com/org/repo formats
        EXTENSION_NAME=$(echo "$REMOTE_URL" | sed 's/.*[:/]\([^/]*\)\/\([^/]*\)\.git$/\2/' | sed 's/.*\/\([^/]*\)$/\1/' | sed 's/\.git$//')
        echo "Detected extension name from git remote: $EXTENSION_NAME"
    else
        # Fallback to directory name
        EXTENSION_NAME=$(basename "$WORKING_DIR")
        echo "Detected extension name from directory: $EXTENSION_NAME"
    fi
else
    # Not a git repo, use directory name
    EXTENSION_NAME=$(basename "$WORKING_DIR")
    echo "Detected extension name from directory: $EXTENSION_NAME"
fi

# Validate the detected name
if [ -z "$EXTENSION_NAME" ]; then
    echo "❌ ERROR: Could not auto-detect extension name"
    exit 1
fi

echo "Extension name: $EXTENSION_NAME"
```

**Store in variable:** `<extension-name>`

**Examples:**
- Target repo URL: `git@github.com:openshift/router.git` → Extension name: `router`
- Target repo URL: `https://github.com/openshift/machine-config-operator` → Extension name: `machine-config-operator`
- Target repo directory: `/home/user/repos/sdn` → Extension name: `sdn`

**Important:** This name will be used for:
- Binary name: `bin/<extension-name>-tests-ext`
- Module paths in generated code
- Test suite names: `openshift/<extension-name>/tests`

#### Input 5: Sig Filter Tags

**AUTO-DETECT with user confirmation.**

**What are sig filter tags:**

Sig tags are used in test names like `[sig-router]` or `[sig-network-edge]` to categorize tests by component. The migration generates code that filters tests to include ONLY those matching your specified tags.

**Auto-detection process:**

```bash
echo "========================================="
echo "Auto-detecting sig tags from test files..."
echo "========================================="

# Ensure we're in the workspace directory with source repo
cd "<working-dir>/openshift-tests-private"

# Scan test files for sig tags
DETECTED_TAGS=$(grep -rh "g\.Describe" "test/extended/<extension-name>/" --include="*.go" 2>/dev/null | \
    grep -o '\[sig-[^]]*\]' | \
    sed 's/\[sig-//g' | \
    sed 's/\]//g' | \
    sort -u | \
    paste -sd "," -)

if [ -z "$DETECTED_TAGS" ]; then
    echo "⚠️  No sig tags detected in test files at test/extended/<extension-name>/"
    echo ""
    echo "Please enter sig tags manually."
    echo "Example: router (for single tag) or router,network-edge (for multiple tags)"
    read -p "Sig tags: " SIG_FILTER_TAGS
else
    echo "Detected sig tags: $DETECTED_TAGS"
    echo ""
    read -p "Use these detected tags? [Y/n]: " CONFIRM

    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        echo "Please enter sig tags manually."
        read -p "Sig tags: " SIG_FILTER_TAGS
    else
        SIG_FILTER_TAGS="$DETECTED_TAGS"
        echo "✓ Using detected tags: $SIG_FILTER_TAGS"
    fi
fi
```

**Result:**
- Auto-detected: Tags are discovered from `test/extended/<extension-name>/` directory
- User confirms or overrides the detected tags
- Tags are comma-separated (e.g., `router,network-edge`)

**Store in variable:** `<sig-filter-tags>`

**Why this is critical:**

The generated `main.go` file will use these tags to filter which tests are registered:

```go
// Filter to only include component-specific tests
sigTags := strings.Split("<sig-filter-tags>", ",")
var filteredSpecs []*et.ExtensionTestSpec
allSpecs.Walk(func(spec *et.ExtensionTestSpec) {
    for _, tag := range sigTags {
        tag = strings.TrimSpace(tag)
        if strings.Contains(spec.Name, "[sig-"+tag+"]") {
            filteredSpecs = append(filteredSpecs, spec)
            return
        }
    }
})
```

**If tags don't match:**

If the tags you provide don't match the actual tags in your test files, the binary will show 0 tests when you run `./bin/<extension-name>-tests-ext list` because no tests will pass the filter.

**Examples:**
- Router tests: `router`
- Network edge tests: `network-edge`
- Multiple components: `router,network-edge`

#### Input 6: Test Directory Name (conditional - monorepo strategy only)

**Skip this input if single-module strategy** - single-module uses `tests-extension/test/e2e`

**For monorepo strategy only:**

**IMPORTANT - What Can Be Customized:**
- ✅ **Customizable**: Only the subdirectory name in Variant B (when test/e2e exists)
- ❌ **NOT Customizable**: The base path `test/e2e/` is FIXED and REQUIRED by OTE framework
- Example: You can choose `test/e2e/my-tests/` but you CANNOT use `tests/e2e/` or `testing/e2e/`

**Note**: Since we're already in the target repository (switched in Input 3b), we can now check the repository structure.

Check if the default test directory already exists:

```bash
# We're already in target repository ($WORKING_DIR)
cd "$WORKING_DIR"

# Check if test/e2e already exists
if [ -d "test/e2e" ]; then
    echo "⚠️  Warning: test/e2e directory already exists in the target repository"
    echo "📌 Using Variant B: Subdirectory mode"
    TEST_DIR_EXISTS=true
else
    echo "📌 Using Variant A: Direct mode"
    TEST_DIR_EXISTS=false
fi
```

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

**Important:** The test module location depends on whether test/e2e already exists:
- **If test/e2e doesn't exist**: go.mod at `test/e2e/go.mod`
- **If test/e2e exists**: go.mod at `test/e2e/<test-dir-name>/go.mod` (in the subdirectory)

**Directory Structure:**
- If test/e2e doesn't exist: Tests, testdata, and go.mod directly in `test/e2e/`
- If test/e2e exists: Tests, testdata, and go.mod in subdirectory `test/e2e/<test-dir-name>/`

**Examples:**
- If test/e2e doesn't exist: `test/e2e/*.go` and `test/e2e/testdata/`
- If test/e2e exists and user accepts default: `test/e2e/extension/*.go` and `test/e2e/extension/testdata/`
- If test/e2e exists and user specifies "ote": `test/e2e/ote/*.go` and `test/e2e/ote/testdata/`

#### Input 7: Local Source Repository (Optional)

Ask: "Do you have a local clone of openshift-tests-private? If yes, provide the path (or press Enter to clone it):"
- If provided: Use this existing local repository
- If empty: Will clone `git@github.com:openshift/openshift-tests-private.git`
- Example: `/home/user/repos/openshift-tests-private`

#### Input 8: Update Local Source Repository (if local source provided)

If a local source repository path was provided:
Ask: "Do you want to update the local source repository? (git fetch && git pull) [Y/n]:"
- Default: Yes
- If yes: Run `git fetch && git pull` in the local repo
- If no: Use current state

#### Input 9: Source Test Subfolder

Ask: "What is the test subfolder name under test/extended/?"
- Example: "networking", "router", "storage", "templates"
- This will be used as: `test/extended/<subfolder>/`
- Leave empty to use all of `test/extended/`

#### Input 10: Source Testdata Subfolder (Optional)

Ask: "What is the testdata subfolder name under test/extended/testdata/? (or press Enter to use same as test subfolder)"
- Default: Same as Input 9 (test subfolder)
- Example: "networking", "router", etc.
- This will be used as: `test/extended/testdata/<subfolder>/`
- Enter "none" if no testdata exists

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
  Local Path: <local-source-path> (or "Will clone to <working-dir>/")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Destination Structure (in target repo):
  Extension Source: cmd/extension/main.go (at repository root)
  Extension Binary: bin/<extension-name>-tests-ext (created by make)
  Test Module: test/e2e/go.mod OR test/e2e/<test-dir-name>/go.mod (auto-detected)
  Test Files: test/e2e/*.go OR test/e2e/<test-dir-name>/*.go (auto-detected)
  Testdata: test/e2e/testdata/ OR test/e2e/<test-dir-name>/testdata/ (inside test module)
  Root go.mod: Will be updated with replace directive for test module

Note: Directory structure is auto-detected:
  - If test/e2e doesn't exist: Creates test/e2e/ with testdata at test/e2e/testdata/
  - If test/e2e exists: Creates test/e2e/<test-dir-name>/ with testdata at test/e2e/<test-dir-name>/testdata/
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
  Local Path: <local-source-path> (or "Will clone to <working-dir>/")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Target Repository:
  Local Path: <local-target-path> (or "Will clone to <working-dir>/<repo-name>")
  URL: <target-repo-url> (if cloning)

Destination Structure (in target repo):
  Extension Binary: tests-extension/cmd/main.go
  Test Files: tests-extension/test/e2e/*.go
  Testdata: tests-extension/test/e2e/testdata/
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

4. **Verify target repository path was collected:**
   ```bash
   if [ -z "$TARGET_REPO_PATH" ]; then
       echo "❌ ERROR: Target repository path not collected"
       echo "Required: Specify target repository (Input 3)"
       echo "Example: /home/user/repos/router"
       exit 1
   fi

   echo "✅ Target repository: $TARGET_REPO_PATH"
   ```

5. **Verify we're in the target repository:**
   ```bash
   # After Input 3b, WORKING_DIR should be same as TARGET_REPO_PATH
   if [ "$WORKING_DIR" != "$TARGET_REPO_PATH" ]; then
       echo "❌ ERROR: Working directory not switched to target repository"
       echo "Current working directory: $WORKING_DIR"
       echo "Expected (target repo): $TARGET_REPO_PATH"
       echo "Required: Input 3b should have switched directory"
       exit 1
   fi

   echo "✅ Working directory switched to target repository: $WORKING_DIR"
   ```

**Checkpoint Summary:**

```bash
echo ""
echo "========================================="
echo "Phase 1 Validation Complete"
echo "========================================="
echo "✅ Strategy: $STRUCTURE_STRATEGY"
echo "✅ Extension name: $EXTENSION_NAME (auto-detected from target repo)"
echo "✅ Sig filter tags: $SIG_FILTER_TAGS"
echo "✅ Target repository: $TARGET_REPO_PATH"
echo "✅ Working directory: $WORKING_DIR (switched to target repo)"

echo ""
echo "NOTE: We are now in the target repository."
echo "      All file creation operations will happen in: $WORKING_DIR"
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

# Check if we already have a remote configured for openshift-tests-private
if [ -d "openshift-tests-private" ]; then
    cd openshift-tests-private
    SOURCE_REMOTE=$(git remote -v | grep 'openshift/openshift-tests-private' | head -1 | awk '{print $1}')

    if [ -n "$SOURCE_REMOTE" ]; then
        echo "Updating openshift-tests-private from remote: $SOURCE_REMOTE"
        git fetch "$SOURCE_REMOTE"
        git pull "$SOURCE_REMOTE" master || git pull "$SOURCE_REMOTE" main
    else
        echo "No remote found for openshift-tests-private, adding new remote..."
        # Use descriptive remote name instead of hardcoded assumption
        SOURCE_REMOTE="ote-source"
        git remote add "$SOURCE_REMOTE" git@github.com:openshift/openshift-tests-private.git
        git fetch "$SOURCE_REMOTE"
        git pull "$SOURCE_REMOTE" master || git pull "$SOURCE_REMOTE" main
    fi
    cd ..
    SOURCE_REPO="openshift-tests-private"
else
    echo "Cloning openshift-tests-private repository..."
    git clone git@github.com:openshift/openshift-tests-private.git openshift-tests-private
    SOURCE_REPO="openshift-tests-private"
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
```

**Note:** Phase 2 only handles source repository setup. Target repository was already set up and switched to in Phase 1 (Input 3b). We are now in the target repository ($WORKING_DIR = $TARGET_REPO_PATH).

### Phase 3: Structure Creation (5 steps)

#### Step 1: Create Directory Structure

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Auto-detect if test/e2e already exists in target repo
if [ -d "test/e2e" ]; then
    TEST_E2E_EXISTS=true
    echo "========================================="
    echo "✅ Detected: Variant B (Subdirectory mode)"
    echo "   Structure: test/e2e/<test-dir-name>/"
    echo "========================================="
else
    TEST_E2E_EXISTS=false
    echo "========================================="
    echo "✅ Detected: Variant A (Direct mode)"
    echo "   Structure: test/e2e/"
    echo "========================================="
fi

# Set directory paths based on detection
if [ "$TEST_E2E_EXISTS" = true ]; then
    # Case 1: test/e2e exists - create subdirectory for our tests to avoid conflicts
    TEST_CODE_DIR="test/e2e/<test-dir-name>"
    TESTDATA_DIR="test/e2e/<test-dir-name>/testdata"
    TEST_MODULE_DIR="test/e2e/<test-dir-name>"  # go.mod goes in subdirectory
    TEST_IMPORT_PATH="<test-dir-name>"  # Relative import within test/e2e module
    echo "Structure: Subdirectory mode (test/e2e already exists)"
else
    # Case 2: test/e2e doesn't exist - use test/e2e directly for cleaner structure
    TEST_CODE_DIR="test/e2e"
    TESTDATA_DIR="test/e2e/testdata"
    TEST_MODULE_DIR="test/e2e"  # go.mod in test/e2e when no subdirectory
    TEST_IMPORT_PATH=""  # Import root of test/e2e module
    echo "Structure: Direct mode (creating fresh test/e2e)"
fi

# Create cmd directory (always inside test module for both variants)
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    # Subdirectory mode: cmd INSIDE test module subdirectory
    mkdir -p "$TEST_MODULE_DIR/cmd"
    echo "   Cmd location: $TEST_MODULE_DIR/cmd (inside test module subdirectory)"
else
    # Direct mode: cmd INSIDE test module at root level
    mkdir -p "$TEST_MODULE_DIR/cmd"
    echo "   Cmd location: $TEST_MODULE_DIR/cmd (inside test module at root level)"
fi

# Create bin directory for binary output
mkdir -p bin

# Create test code directory
mkdir -p "$TEST_CODE_DIR"

# Create testdata directory at test/e2e level
mkdir -p "$TESTDATA_DIR"

echo "✅ Created monorepo structure in existing repository"
echo "   Test code: $TEST_CODE_DIR"
echo "   Testdata: $TESTDATA_DIR"
echo "   Go module: $TEST_MODULE_DIR"
```

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
mkdir -p test/e2e/testdata

echo "Created single-module structure in tests-extension/"
```bash

#### Step 2: Copy Test Files

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Copy test files to test code directory (set in Step 1)
# Use $SOURCE_TEST_PATH variable (set in Phase 2)
# Use $TEST_CODE_DIR variable (set in Step 1: test/e2e or test/e2e/<test-dir-name>)
cp -r "$SOURCE_TEST_PATH"/* "$TEST_CODE_DIR"/

# Count and display copied files
echo "Copied $(find "$TEST_CODE_DIR" -name '*_test.go' | wc -l) test files from $SOURCE_TEST_PATH"
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

# Auto-detect if test/e2e exists to determine testdata path
if [ -d "test/e2e" ]; then
    # test/e2e exists - check if we're using subdirectory
    if [ -n "<test-dir-name>" ] && [ "<test-dir-name>" != "e2e" ]; then
        # Using subdirectory: test/e2e/$TEST_DIR_NAME/testdata/
        TESTDATA_TARGET_DIR="test/e2e/<test-dir-name>/testdata"
    else
        # Using test/e2e directly: test/e2e/testdata/
        TESTDATA_TARGET_DIR="test/e2e/testdata"
    fi
else
    # test/e2e doesn't exist - will create test/e2e/testdata/
    TESTDATA_TARGET_DIR="test/e2e/testdata"
fi

# Copy testdata if it exists (skip if user specified "none")
# Use $SOURCE_TESTDATA_PATH variable (set in Phase 2)
if [ -n "$SOURCE_TESTDATA_PATH" ]; then
    # Create subdirectory structure to match bindata paths
    # Files are organized as testdata/<subfolder>/ to match how tests call FixturePath()
    if [ -n "<testdata-subfolder>" ]; then
        mkdir -p "$TESTDATA_TARGET_DIR/<testdata-subfolder>"
        cp -r "$SOURCE_TESTDATA_PATH"/* "$TESTDATA_TARGET_DIR/<testdata-subfolder>/"
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to $TESTDATA_TARGET_DIR/<testdata-subfolder>/"
        echo "Tests should call: testdata.FixturePath(\"<testdata-subfolder>/filename.yaml\")"
    else
        # No subfolder specified, copy directly
        mkdir -p "$TESTDATA_TARGET_DIR"
        cp -r "$SOURCE_TESTDATA_PATH"/* "$TESTDATA_TARGET_DIR/"
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to $TESTDATA_TARGET_DIR/"
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
        mkdir -p "test/e2e/testdata/<testdata-subfolder>"
        cp -r "$SOURCE_TESTDATA_PATH"/* "test/e2e/testdata/<testdata-subfolder>/"
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/e2e/testdata/<testdata-subfolder>/"
        echo "Tests should call: testdata.FixturePath(\"<testdata-subfolder>/filename.yaml\")"
    else
        # No subfolder specified, copy directly
        cp -r "$SOURCE_TESTDATA_PATH"/* test/e2e/testdata/
        echo "Copied testdata files from $SOURCE_TESTDATA_PATH to test/e2e/testdata/"
    fi
else
    echo "Skipping testdata copy (none specified)"
fi
```

### Phase 4: Code Generation (6 steps)

#### Step 1: Generate/Update go.mod Files

**For Monorepo Strategy:**

Create go.mod in the test module directory (using $TEST_MODULE_DIR variable):
```bash
cd <working-dir>

# Extract Go version from root go.mod
GO_VERSION=$(grep '^go ' go.mod | awk '{print $2}')
echo "Using Go version: $GO_VERSION (from target repo)"

# Get source repo path (set in Phase 2)
OTP_PATH="$SOURCE_REPO"

echo "Step 1: Create $TEST_MODULE_DIR/go.mod..."
cd "$TEST_MODULE_DIR"

# Initialize go.mod in test module directory
# Determine path back to root based on subdirectory depth
if [ "$TEST_E2E_EXISTS" = true ]; then
    # Subdirectory mode: test/e2e/<test-dir-name> -> need ../../../
    ROOT_MODULE=$(grep '^module ' ../../../go.mod | awk '{print $2}')
    go mod init "$ROOT_MODULE/$TEST_MODULE_DIR"
else
    # Direct mode: test/e2e -> need ../../
    ROOT_MODULE=$(grep '^module ' ../../go.mod | awk '{print $2}')
    go mod init "$ROOT_MODULE/test/e2e"
fi

echo "Step 2: Set Go version to match target repo..."
sed -i "s/^go .*/go $GO_VERSION/" go.mod

echo "Step 3: Add required dependencies..."
# Get latest openshift-tests-extension commit from main branch
OTE_LATEST=$(git ls-remote https://github.com/openshift-eng/openshift-tests-extension.git refs/heads/main | awk '{print $1}')
OTE_SHORT="${OTE_LATEST:0:12}"
echo "Using openshift-tests-extension commit: $OTE_SHORT"

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

echo "Step 4: Copy ALL replace directives from openshift-tests-private/go.mod..."
# Navigate to source repo (path depends on subdirectory depth)
if [ "$TEST_E2E_EXISTS" = true ]; then
    SOURCE_PATH="../../../$SOURCE_REPO"
else
    SOURCE_PATH="../../$SOURCE_REPO"
fi

if [ -f "$SOURCE_PATH/go.mod" ]; then
    echo "Extracting ALL replace directives from openshift-tests-private/go.mod..."

    # Extract ALL replace directives verbatim from openshift-tests-private
    # This ensures we get the exact same dependency graph that's battle-tested
    grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
        grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

    # IMPORTANT: This is an APPEND operation
    # - Appends replace section to existing go.mod (doesn't overwrite)
    # - Does NOT affect the require section (populated by go get and go mod tidy)
    # - ONLY affects the replace section
    # - Replace directives are NEVER removed by go mod tidy (standard Go behavior)
    echo "" >> go.mod
    echo "replace (" >> go.mod
    cat /tmp/replace_directives.txt >> go.mod
    echo ")" >> go.mod

    # Cleanup
    rm -f /tmp/replace_directives.txt

    echo "✅ Copied all replace directives from openshift-tests-private"
else
    echo "❌ Error: openshift-tests-private go.mod not found at $SOURCE_PATH"
    echo "Cannot proceed without replace directives from source"
    exit 1
fi

echo "Step 5: Add replace directive for root module..."
# CRITICAL: Test module needs to import testdata from root module
# Add replace directive so go can find <module>/test/<testdata-dir>
# Path back to root depends on subdirectory depth
if [ "$TEST_E2E_EXISTS" = true ]; then
    # Subdirectory mode: test/e2e/<test-dir-name> is 3 levels deep
    MODULE_NAME=$(grep '^module ' "$OLDPWD/go.mod" | awk '{print $2}')
    echo "" >> go.mod
    echo "replace $MODULE_NAME => ../../../.." >> go.mod
    echo "✅ Added replace directive for root module: $MODULE_NAME => ../../../.."
else
    # Direct mode: test/e2e is 2 levels deep
    MODULE_NAME=$(grep '^module ' "$OLDPWD/go.mod" | awk '{print $2}')
    echo "" >> go.mod
    echo "replace $MODULE_NAME => ../../.." >> go.mod
    echo "✅ Added replace directive for root module: $MODULE_NAME => ../../.."
fi

echo "Step 6a: Upgrade api and client-go to latest versions..."
# NOTE: Origin's go.mod often specifies outdated versions that are incompatible with origin's actual code
# Instead of using origin's go.mod versions, upgrade to latest to ensure API compatibility
echo "Fetching latest client-go version..."

# Get latest client-go commit (fast - just a git ls-remote call)
CLIENT_GO_LATEST=$(git ls-remote https://github.com/openshift/client-go.git refs/heads/master 2>/dev/null | awk '{print $1}')
if [ -n "$CLIENT_GO_LATEST" ]; then
    echo "Latest client-go commit: $CLIENT_GO_LATEST"
    echo "Upgrading client-go to latest (this may take 30-60 seconds)..."
    # Use timeout to prevent hanging - if it fails, we'll resolve in Phase 6
    timeout 90s env GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/client-go@$CLIENT_GO_LATEST" 2>&1 || \
        echo "⚠️  client-go upgrade timed out or failed - will resolve with go mod tidy in Phase 6"
    echo "✅ api and client-go upgrade attempted"
else
    echo "⚠️  Could not fetch latest client-go commit - will use default dependency resolution"
fi

echo "Step 7: Generate go.sum (deferred full resolution)..."
# PERFORMANCE FIX: Don't run full 'go mod tidy' here - it can timeout (60-120s)
# Instead, generate minimal go.sum and defer full resolution until after test migration
# This ensures Phase 5 (Test Migration) runs even if dependency resolution is slow

# Generate minimal go.sum from go.mod
echo "Generating minimal go.sum..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download || echo "⚠️  Some dependencies failed to download - will retry after test migration"

# Mark that go mod tidy needs to be run later
echo "⚠️  Note: Full dependency resolution deferred to Phase 6"
echo "    This prevents timeout before test migration completes"

echo "Step 8: Verify go.mod and go.sum are created..."
if [ -f "go.mod" ] && [ -f "go.sum" ]; then
    echo "✅ $TEST_MODULE_DIR/go.mod and go.sum created successfully"
    echo "Module: $(grep '^module' go.mod)"
    echo "Go version: $(grep '^go ' go.mod)"

    # Count replace directives
    REPLACE_COUNT=$(grep -c "=>" go.mod || echo 0)
    echo "Replace directives: $REPLACE_COUNT"
else
    echo "❌ Error: go.mod or go.sum not created properly"
    exit 1
fi

# Return to root directory (path depends on subdirectory depth)
if [ "$TEST_E2E_EXISTS" = true ]; then
    cd ../../..  # From test/e2e/<test-dir-name> back to root
else
    cd ../..  # From test/e2e back to root
fi

echo "Step 9: Update root go.mod with replace directives..."
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Step 9a: Add replace directive for test module
# Note: testdata is inside test module, not a separate module
if ! grep -q "replace.*$MODULE_NAME/$TEST_MODULE_DIR" go.mod; then
    if grep -q "^replace (" go.mod; then
        # Add to existing replace section
        sed -i "/^replace (/a\\    $MODULE_NAME/$TEST_MODULE_DIR => ./$TEST_MODULE_DIR" go.mod
    else
        # Create new replace section
        echo "" >> go.mod
        echo "replace $MODULE_NAME/$TEST_MODULE_DIR => ./$TEST_MODULE_DIR" >> go.mod
    fi
    echo "✅ Test module replace directive added to root go.mod: $MODULE_NAME/$TEST_MODULE_DIR => ./$TEST_MODULE_DIR"
fi

# Step 9b: Copy k8s.io and other upstream replace directives from test module to root
echo "Copying k8s.io and upstream replace directives from $TEST_MODULE_DIR/go.mod to root go.mod..."

# Extract replace directives from test module (excluding the self-reference)
TEST_REPLACES=$(grep -A 1000 "^replace (" "$TEST_MODULE_DIR/go.mod" | grep -v "^replace (" | grep "=>" | grep -v "^)" || echo "")

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

# Step 8c: Update critical OpenShift dependencies in root go.mod to match test module
echo "Updating critical OpenShift dependencies in root go.mod to match test module..."

# First, get origin version from test module
ORIGIN_VERSION=$(grep "github.com/openshift/origin" "$TEST_MODULE_DIR/go.mod" | grep "=>" | awk '{print $NF}' || echo "")
if [ -z "$ORIGIN_VERSION" ]; then
    # Try to get from require section
    ORIGIN_VERSION=$(grep "github.com/openshift/origin" "$TEST_MODULE_DIR/go.mod" | grep -v "=>" | awk '{print $2}' | head -1 || echo "")
fi

# Fetch origin's go.mod to get compatible client-go and api versions
if [ -n "$ORIGIN_VERSION" ]; then
    echo "  Found origin version in test module: $ORIGIN_VERSION"

    # Extract commit hash from pseudo-version (format: v0.0.0-20260130020739-e713d4ecc0db)
    ORIGIN_COMMIT=$(echo "$ORIGIN_VERSION" | sed 's/.*-//')

    echo "  Fetching origin's go.mod to get compatible dependency versions..."
    ORIGIN_GOMOD=$(curl -s "https://raw.githubusercontent.com/openshift/origin/${ORIGIN_COMMIT}/go.mod" || echo "")

    if [ -n "$ORIGIN_GOMOD" ]; then
        # Extract api and client-go versions from origin's go.mod
        API_VERSION=$(echo "$ORIGIN_GOMOD" | grep "github.com/openshift/api " | grep -v "=>" | awk '{print $2}' | head -1)
        CLIENT_GO_VERSION=$(echo "$ORIGIN_GOMOD" | grep "github.com/openshift/client-go " | grep -v "=>" | awk '{print $2}' | head -1)

        echo "  Origin requires:"
        echo "    - github.com/openshift/api: $API_VERSION"
        echo "    - github.com/openshift/client-go: $CLIENT_GO_VERSION"
    else
        echo "  ⚠️  Could not fetch origin's go.mod, falling back to test module versions"
        # Fallback to test module versions
        API_VERSION=$(grep "github.com/openshift/api" "$TEST_MODULE_DIR/go.mod" | grep "=>" | awk '{print $NF}' || echo "")
        if [ -z "$API_VERSION" ]; then
            API_VERSION=$(grep "github.com/openshift/api" "$TEST_MODULE_DIR/go.mod" | grep -v "=>" | awk '{print $2}' | head -1 || echo "")
        fi

        CLIENT_GO_VERSION=$(grep "github.com/openshift/client-go" "$TEST_MODULE_DIR/go.mod" | grep "=>" | awk '{print $NF}' || echo "")
        if [ -z "$CLIENT_GO_VERSION" ]; then
            CLIENT_GO_VERSION=$(grep "github.com/openshift/client-go" "$TEST_MODULE_DIR/go.mod" | grep -v "=>" | awk '{print $2}' | head -1 || echo "")
        fi
    fi
else
    echo "  ⚠️  Origin version not found in test module, using test module dependency versions"
    # Fallback to test module versions
    API_VERSION=$(grep "github.com/openshift/api" "$TEST_MODULE_DIR/go.mod" | grep "=>" | awk '{print $NF}' || echo "")
    if [ -z "$API_VERSION" ]; then
        API_VERSION=$(grep "github.com/openshift/api" "$TEST_MODULE_DIR/go.mod" | grep -v "=>" | awk '{print $2}' | head -1 || echo "")
    fi

    CLIENT_GO_VERSION=$(grep "github.com/openshift/client-go" "$TEST_MODULE_DIR/go.mod" | grep "=>" | awk '{print $NF}' || echo "")
    if [ -z "$CLIENT_GO_VERSION" ]; then
        CLIENT_GO_VERSION=$(grep "github.com/openshift/client-go" "$TEST_MODULE_DIR/go.mod" | grep -v "=>" | awk '{print $2}' | head -1 || echo "")
    fi
fi

UPDATED_COUNT=0

# Update github.com/openshift/api if version found
if [ -n "$API_VERSION" ]; then
    echo "  Updating root go.mod github.com/openshift/api to: $API_VERSION"
    GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/api@$API_VERSION" 2>/dev/null || \
        GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/api@latest"
    UPDATED_COUNT=$((UPDATED_COUNT + 1))
    echo "  ✅ Updated github.com/openshift/api in root go.mod"
fi

# Update github.com/openshift/client-go if version found
if [ -n "$CLIENT_GO_VERSION" ]; then
    echo "  Updating root go.mod github.com/openshift/client-go to: $CLIENT_GO_VERSION"
    GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/client-go@$CLIENT_GO_VERSION" 2>/dev/null || \
        GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/client-go@latest"
    UPDATED_COUNT=$((UPDATED_COUNT + 1))
    echo "  ✅ Updated github.com/openshift/client-go in root go.mod"
fi

if [ $UPDATED_COUNT -gt 0 ]; then
    echo "✅ Updated $UPDATED_COUNT critical OpenShift dependencies in root go.mod"
    echo "  Running go mod tidy to resolve dependencies..."
    GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy
else
    echo "⚠️  No critical OpenShift dependencies found to update"
fi

echo "✅ Monorepo go.mod setup complete"
```

**Note:** For monorepo strategy:
- Test module has its own go.mod (separate module)
- go.mod/go.sum location depends on directory structure:
  - If test/e2e doesn't exist: go.mod in `test/e2e/`
  - If test/e2e exists: go.mod in `test/e2e/<test-dir-name>/` (subdirectory)
- Root go.mod has replace directive pointing to the test module directory
- k8s.io/* and upstream replace directives are automatically copied from test module to root go.mod
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

echo "Step 3: Add required dependencies..."
# Get latest openshift-tests-extension commit from main branch
OTE_LATEST=$(git ls-remote https://github.com/openshift-eng/openshift-tests-extension.git refs/heads/main | awk '{print $1}')
OTE_SHORT="${OTE_LATEST:0:12}"
echo "Using openshift-tests-extension commit: $OTE_SHORT"

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

echo "Step 4: Copy ALL replace directives from openshift-tests-private/go.mod..."
# Source repo path for single-module
SOURCE_PATH="../$SOURCE_REPO"

if [ -f "$SOURCE_PATH/go.mod" ]; then
    echo "Extracting ALL replace directives from openshift-tests-private/go.mod..."

    # Extract ALL replace directives verbatim from openshift-tests-private
    # This ensures we get the exact same dependency graph that's battle-tested
    grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
        grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

    # IMPORTANT: This is an APPEND operation
    # - Appends replace section to existing go.mod (doesn't overwrite)
    # - Does NOT affect the require section (populated by go get and go mod tidy)
    # - ONLY affects the replace section
    # - Replace directives are NEVER removed by go mod tidy (standard Go behavior)
    echo "" >> go.mod
    echo "replace (" >> go.mod
    cat /tmp/replace_directives.txt >> go.mod
    echo ")" >> go.mod

    # Cleanup
    rm -f /tmp/replace_directives.txt

    echo "✅ Copied all replace directives from openshift-tests-private"
else
    echo "❌ Error: openshift-tests-private go.mod not found at $SOURCE_PATH"
    echo "Cannot proceed without replace directives from source"
    exit 1
fi

echo "Step 5: Generate go.sum (deferred full resolution)..."
# PERFORMANCE FIX: Don't run full 'go mod tidy' here - it can timeout (60-120s)
# Instead, generate minimal go.sum and defer full resolution until after test migration
# This ensures Phase 5 (Test Migration) runs even if dependency resolution is slow

# Generate minimal go.sum from go.mod
echo "Generating minimal go.sum..."
go mod download || echo "⚠️  Some dependencies failed to download - will retry after test migration"

# Mark that go mod tidy needs to be run later
echo "⚠️  Note: Full dependency resolution deferred to Phase 6"
echo "    This prevents timeout before test migration completes"

echo "Step 6: Verify go.mod and go.sum are created..."
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

**IMPORTANT:** Extract module name and detect test module import path:
```bash
cd <working-dir>
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')
echo "Using module name: $MODULE_NAME"

# Determine main.go location and import path based on directory structure
# Both variants have main.go inside test module, just at different levels
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    # Subdirectory mode: main.go INSIDE test module subdirectory
    MAIN_GO_PATH="$TEST_MODULE_DIR/cmd/main.go"
    TEST_IMPORT="$MODULE_NAME/$TEST_MODULE_DIR"
    echo "Main.go location: $MAIN_GO_PATH (inside test module subdirectory)"
else
    # Direct mode: main.go INSIDE test module at root level
    MAIN_GO_PATH="$TEST_MODULE_DIR/cmd/main.go"
    TEST_IMPORT="$MODULE_NAME/test/e2e"
    echo "Main.go location: $MAIN_GO_PATH (inside test module at root level)"
fi
echo "Using test import path: $TEST_IMPORT"
```

**Note:** Both variants have main.go inside the test module for consistency:
- **Variant A (test/e2e doesn't exist):** `test/e2e/cmd/main.go` (inside test module at root level)
- **Variant B (test/e2e exists):** `test/e2e/extension/cmd/main.go` (inside test module subdirectory)

Then generate main.go at the determined location with the actual module name and import path:

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

    // Import testdata package from test module
    testdata "$TEST_IMPORT/testdata"

    // Import test packages from test module
    _ "$TEST_IMPORT"
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

**Principle:** bindata.mk must always be at the same directory level as testdata/ for correct path resolution.

**For Monorepo Strategy:**

Create bindata.mk at the same level as testdata/ directory:

```bash
cd <working-dir>

# Create bindata.mk at same level as testdata/ directory
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    # Subdirectory mode: bindata.mk at test/e2e/<test-dir-name>/
    BINDATA_MK_PATH="$TEST_MODULE_DIR/bindata.mk"
else
    # Direct mode: bindata.mk at test/e2e/
    BINDATA_MK_PATH="$TEST_MODULE_DIR/bindata.mk"
fi

cat > "$BINDATA_MK_PATH" << 'EOF'
# bindata.mk for embedding testdata files

BINDATA_PKG := testdata
BINDATA_OUT := testdata/bindata.go

.PHONY: update-bindata
update-bindata:
	@echo "Generating bindata for testdata files..."
	go-bindata \
		-nocompress \
		-nometadata \
		-prefix "testdata" \
		-pkg $(BINDATA_PKG) \
		-o testdata/bindata.go \
		testdata/...
	@echo "✅ Bindata generated successfully"

.PHONY: verify-bindata
verify-bindata: update-bindata
	@echo "Verifying bindata is up to date..."
	git diff --exit-code $(BINDATA_OUT) || (echo "❌ Bindata is out of date. Run 'make update-bindata'" && exit 1)
	@echo "✅ Bindata is up to date"

# Legacy alias for backward compatibility
.PHONY: bindata
bindata: update-bindata

.PHONY: clean-bindata
clean-bindata:
	@echo "Cleaning bindata..."
	@rm -f $(BINDATA_OUT)
EOF

echo "✅ Created bindata.mk at: $BINDATA_MK_PATH"
```

**For Single-Module Strategy:**

Create `tests-extension/test/e2e/bindata.mk` (same level as `tests-extension/test/e2e/testdata/`):

```makefile
# Bindata generation for testdata files

# Testdata path (relative to tests-extension/test/e2e/ directory)
TESTDATA_PATH := testdata

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
        -pkg testdata -o $(TESTDATA_PATH)/bindata.go -prefix "testdata" $(TESTDATA_PATH)/...
    @gofmt -s -w $(TESTDATA_PATH)/bindata.go
    @echo "Bindata generated successfully at $(TESTDATA_PATH)/bindata.go"

.PHONY: clean-bindata
clean-bindata:
    @echo "Cleaning bindata..."
    @rm -f $(TESTDATA_PATH)/bindata.go
```makefile

#### Step 4: Create Makefile

**For Monorepo Strategy:**

Update existing root Makefile to build extension binary:

```bash
cd <working-dir>

# Verify Makefile exists (required for monorepo strategy)
if [ ! -f "Makefile" ]; then
    echo "❌ ERROR: No root Makefile found in target repository"
    echo ""
    echo "Monorepo strategy requires an existing Makefile."
    echo "Please either:"
    echo "  1. Create a basic Makefile in your repository first, OR"
    echo "  2. Use single-module strategy instead"
    exit 1
fi

echo "Updating root Makefile with OTE extension targets..."

# Check if OTE targets already exist
if grep -q "tests-ext-build" Makefile; then
    echo "⚠️  OTE targets already exist in Makefile, skipping..."
else
    # Generate appropriate Makefile targets based on directory structure
    # Note: Using actual variable values (not placeholders)
    # $TEST_MODULE_DIR is set in Phase 3, Step 1:
    #   - Variant A (test/e2e doesn't exist): TEST_MODULE_DIR="test/e2e"
    #   - Variant B (test/e2e exists): TEST_MODULE_DIR="test/e2e/<actual-test-dir-name>"

    if [ "$TEST_DIR_EXISTS" = "true" ]; then
        # Variant B (Subdirectory mode): test/e2e exists
        # Build from test module at: test/e2e/<test-dir-name>/
        # bindata.mk location: test/e2e/<test-dir-name>/bindata.mk
        # Output path from module: ../../../bin/<extension-name>-tests-ext
        cat >> Makefile << EOF

# OTE test extension binary configuration (Variant B: Subdirectory mode)
TESTS_EXT_DIR := $TEST_MODULE_DIR/cmd
TESTS_EXT_BINARY := bin/<extension-name>-tests-ext

# Build OTE extension binary (builds from test module, outputs to bin/)
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd $TEST_MODULE_DIR && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	cd $TEST_MODULE_DIR && GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o ../../../\$(TESTS_EXT_BINARY) ./cmd
	@echo "✅ Extension binary built: \$(TESTS_EXT_BINARY)"
EOF
    else
        # Variant A (Direct mode): test/e2e doesn't exist
        # Build from test module at: test/e2e/
        # bindata.mk location: test/e2e/bindata.mk
        # Output path from module: ../../bin/<extension-name>-tests-ext
        cat >> Makefile << EOF

# OTE test extension binary configuration (Variant A: Direct mode)
TESTS_EXT_DIR := test/e2e/cmd
TESTS_EXT_BINARY := bin/<extension-name>-tests-ext

# Build OTE extension binary (builds from test module, outputs to bin/)
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd test/e2e && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	cd test/e2e && GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o ../../\$(TESTS_EXT_BINARY) ./cmd
	@echo "✅ Extension binary built: \$(TESTS_EXT_BINARY)"
EOF
    fi

    # Add common targets for both variants
    # Note: Uses $TEST_MODULE_DIR variable which is already set to correct path
    cat >> Makefile << EOF

# Compress OTE extension binary (for CI/CD and container builds)
.PHONY: tests-ext-compress
tests-ext-compress: tests-ext-build
	@echo "Compressing OTE extension binary..."
	@cd bin && tar -czvf <extension-name>-tests-ext.tar.gz <extension-name>-tests-ext && rm -f <extension-name>-tests-ext
	@echo "Compressed binary created at bin/<extension-name>-tests-ext.tar.gz"

# Copy compressed binary to _output directory (for CI/CD)
.PHONY: tests-ext-copy
tests-ext-copy: tests-ext-compress
	@echo "Copying compressed binary to _output..."
	@mkdir -p _output
	@cp bin/<extension-name>-tests-ext.tar.gz _output/
	@echo "Binary copied to _output/<extension-name>-tests-ext.tar.gz"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY) bin/<extension-name>-tests-ext.tar.gz _output/<extension-name>-tests-ext.tar.gz
	@cd $TEST_MODULE_DIR && \$(MAKE) -f bindata.mk clean-bindata 2>/dev/null || true
EOF

    echo "✅ Root Makefile updated with OTE targets"
fi
```bash

**For Single-Module Strategy:**

Create `tests-extension/Makefile`:

```bash
cd <working-dir>/tests-extension

# For single-module strategy:
# - bindata.mk is at: tests-extension/test/e2e/bindata.mk
# - testdata is at: tests-extension/test/e2e/testdata/
# - tests are at: tests-extension/test/e2e/*.go
# - binary output: tests-extension/bin/<extension-name>-tests-ext

cat > Makefile << EOF
# Binary name and output directory
BINARY := bin/<extension-name>-tests-ext

# Build extension binary
.PHONY: build
build:
	@echo "Building extension binary..."
	@cd test/e2e && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o \$(BINARY) ./cmd
	@echo "✅ Binary built successfully at \$(BINARY)"

# Clean generated files
.PHONY: clean
clean:
	@echo "Cleaning binaries..."
	@rm -f \$(BINARY)
	@cd test/e2e && \$(MAKE) -f bindata.mk clean-bindata

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build       - Build extension binary (includes bindata)"
	@echo "  clean       - Remove extension binary and bindata"
EOF

echo "✅ Created tests-extension/Makefile"
```

**Update Root Makefile (Target Repository - Optional):**

Optionally update the root Makefile in the target repository for convenience:

```bash
cd <working-dir>

if [ -f "Makefile" ]; then
    echo "Updating root Makefile with OTE extension targets..."

    if grep -q "tests-ext-build" Makefile; then
        echo "⚠️  OTE targets already exist in Makefile, skipping..."
    else
        # For single-module: bindata is at tests-extension/test/e2e/bindata.mk
        cat >> Makefile << EOF

# OTE test extension binary configuration (single-module strategy)
TESTS_EXT_DIR := ./tests-extension
TESTS_EXT_BINARY := tests-extension/bin/<extension-name>-tests-ext

# Build OTE extension binary
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) build
	@echo "✅ OTE binary built successfully at \$(TESTS_EXT_BINARY)"

# Compress OTE extension binary (for CI/CD and container builds)
.PHONY: tests-ext-compress
tests-ext-compress: tests-ext-build
	@echo "Compressing OTE extension binary..."
	@cd tests-extension/bin && tar -czvf <extension-name>-tests-ext.tar.gz <extension-name>-tests-ext && rm -f <extension-name>-tests-ext
	@echo "Compressed binary created at tests-extension/bin/<extension-name>-tests-ext.tar.gz"

# Copy compressed binary to _output directory (for CI/CD)
.PHONY: tests-ext-copy
tests-ext-copy: tests-ext-compress
	@echo "Copying compressed binary to _output..."
	@mkdir -p _output
	@cp tests-extension/bin/<extension-name>-tests-ext.tar.gz _output/
	@echo "Binary copied to _output/<extension-name>-tests-ext.tar.gz"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY) tests-extension/bin/<extension-name>-tests-ext.tar.gz _output/<extension-name>-tests-ext.tar.gz
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) clean
EOF

        echo "✅ Root Makefile updated with OTE targets"
    fi
else
    echo "⚠️  No root Makefile found in target repository"
    echo "For single-module strategy, you can use tests-extension/Makefile directly:"
    echo "  cd tests-extension && make build"
fi
```bash

**Key Points:**
- `tests-extension/Makefile` is self-contained and handles bindata generation
- Root Makefile integration is **optional** but provides convenient targets from root
- Binary is built to `tests-extension/bin/<extension-name>-tests-ext`
- Provides standard targets:
  - `make tests-ext-build` - Build the binary (root)
  - `make build` - Build the binary (inside tests-extension/)
  - `make tests-ext-compress` - Build and compress (root, for CI/CD)
  - `make tests-ext-copy` - Build, compress, and copy to `_output/` (root, for CI/CD)
  - `make extension` - Alias for tests-ext-build (root)

#### Step 5: Create fixtures.go (Helper Functions)

**IMPORTANT:** This creates the helper functions file `fixtures.go`. This is SEPARATE from `bindata.go` which is generated by go-bindata.

**For Monorepo Strategy:**

Create fixtures.go helper file at the testdata directory location:
- If test/e2e exists and using subdirectory: `test/e2e/<test-dir-name>/testdata/fixtures.go`
- If test/e2e doesn't exist (direct mode): `test/e2e/testdata/fixtures.go`

**For Single-Module Strategy:**

Create `tests-extension/test/e2e/testdata/fixtures.go`

**Note:** The fixtures.go helper functions content is the same for both strategies. This file provides FixturePath() and other utility functions that wrap the bindata-generated Asset/RestoreAsset functions:

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

#### Step 6: Update Dockerfile

**This step modifies or creates a Dockerfile to include OTE binary compilation and packaging for both strategies.**

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Step 6: Updating Dockerfile for OTE binary"
echo "========================================="

# Determine bindata path based on directory structure
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    # Subdirectory mode: bindata at test/e2e/<test-dir-name>/
    BINDATA_PATH="test/e2e/<test-dir-name>"
else
    # Direct mode: bindata at test/e2e/
    BINDATA_PATH="test/e2e"
fi

# Check if Dockerfile exists
if [ -f "Dockerfile" ]; then
    echo "Found existing Dockerfile - will add OTE binary build stages"

    # Create backup
    cp Dockerfile Dockerfile.pre-ote-migration
    echo "✅ Created backup: Dockerfile.pre-ote-migration"

    # Check if Dockerfile already has OTE binary build
    if grep -q "tests-ext-build" Dockerfile; then
        echo "⚠️  Dockerfile already contains OTE binary build - skipping modification"
    else
        # Create temporary file with OTE build stages
        cat > /tmp/ote-build-stage.txt << EOF
# OTE Extension Binary Build (added by migration)
RUN cd $BINDATA_PATH && make -f bindata.mk update-bindata
RUN make tests-ext-build
RUN gzip bin/<extension-name>-tests-ext
EOF

        # Find builder stage and add OTE build commands
        if grep -q "FROM.*AS builder" Dockerfile; then
            # Existing builder stage found - add OTE build after COPY . .
            echo "Adding OTE build to existing builder stage..."

            # Find line number after "COPY . ." in builder stage
            COPY_LINE=$(grep -n "COPY \. \." Dockerfile | head -1 | cut -d: -f1)

            if [ -n "$COPY_LINE" ]; then
                # Insert OTE build commands after COPY line
                sed -i "${COPY_LINE}r /tmp/ote-build-stage.txt" Dockerfile
                echo "✅ Added OTE build commands to builder stage"
            else
                echo "⚠️  Could not find 'COPY . .' in Dockerfile - please add OTE build manually"
            fi
        else
            echo "⚠️  No builder stage found in Dockerfile - creating OTE-specific Dockerfile.ote"
            # Will create separate Dockerfile below
        fi

        # Add COPY command to runtime stage
        echo "Adding OTE binary COPY to runtime stage..."

        # Find the runtime stage (usually "FROM.*base" or last FROM)
        RUNTIME_LINE=$(grep -n "^FROM" Dockerfile | tail -1 | cut -d: -f1)

        if [ -n "$RUNTIME_LINE" ]; then
            # Add COPY command after runtime FROM line
            cat > /tmp/ote-copy.txt << EOF

# Copy OTE extension binary (added by migration)
COPY --from=builder /go/src/github.com/<org>/<component-name>/bin/<extension-name>-tests-ext.gz /usr/bin/
EOF
            sed -i "${RUNTIME_LINE}r /tmp/ote-copy.txt" Dockerfile
            echo "✅ Added OTE binary COPY to runtime stage"
        fi

        rm -f /tmp/ote-build-stage.txt /tmp/ote-copy.txt
    fi
else
    echo "No Dockerfile found - creating Dockerfile.ote with OTE binary build"

    # Create a complete Dockerfile for OTE binary
    cat > Dockerfile.ote << EOF
# Multi-stage Dockerfile for OTE Extension Binary
# Generated by ote-migration plugin

# Build stage - Build the OTE test extension binary
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

# Copy source code
COPY . .

# Generate testdata bindata
RUN cd $BINDATA_PATH && make -f bindata.mk update-bindata

# Build the OTE extension binary
RUN make tests-ext-build

# Compress the binary (following OpenShift pattern)
RUN gzip bin/<extension-name>-tests-ext

# Runtime stage - Copy compressed binary
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9

# Copy the compressed OTE binary to /usr/bin/
COPY --from=builder /go/src/github.com/<org>/<component-name>/bin/<extension-name>-tests-ext.gz /usr/bin/

# Add any additional runtime dependencies here
# COPY other binaries, set ENTRYPOINT, etc.
EOF

    echo "✅ Created Dockerfile.ote - merge this into your main Dockerfile"
fi

echo ""
echo "Dockerfile update complete!"
echo ""
echo "OTE Binary Location in Image: /usr/bin/<extension-name>-tests-ext.gz"
echo "To register with origin, use path: /usr/bin/<extension-name>-tests-ext.gz"
echo ""
```

**For Single-Module Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Step 6: Updating Dockerfile for OTE binary"
echo "========================================="

# Check if Dockerfile exists
if [ -f "Dockerfile" ]; then
    echo "Found existing Dockerfile - will add OTE binary build stages"

    # Create backup
    cp Dockerfile Dockerfile.pre-ote-migration
    echo "✅ Created backup: Dockerfile.pre-ote-migration"

    # Check if Dockerfile already has OTE binary build
    if grep -q "tests-ext-build" Dockerfile; then
        echo "⚠️  Dockerfile already contains OTE binary build - skipping modification"
    else
        # Create temporary file with OTE build stages
        cat > /tmp/ote-build-stage.txt << EOF
# OTE Extension Binary Build (added by migration)
RUN make tests-ext-build
RUN gzip tests-extension/bin/<extension-name>-tests-ext
EOF

        # Find builder stage and add OTE build commands
        if grep -q "FROM.*AS builder" Dockerfile; then
            # Existing builder stage found - add OTE build after COPY . .
            echo "Adding OTE build to existing builder stage..."

            # Find line number after "COPY . ." in builder stage
            COPY_LINE=$(grep -n "COPY \. \." Dockerfile | head -1 | cut -d: -f1)

            if [ -n "$COPY_LINE" ]; then
                # Insert OTE build commands after COPY line
                sed -i "${COPY_LINE}r /tmp/ote-build-stage.txt" Dockerfile
                echo "✅ Added OTE build commands to builder stage"
            else
                echo "⚠️  Could not find 'COPY . .' in Dockerfile - please add OTE build manually"
            fi
        else
            echo "⚠️  No builder stage found in Dockerfile - creating OTE-specific Dockerfile.ote"
            # Will create separate Dockerfile below
        fi

        # Add COPY command to runtime stage
        echo "Adding OTE binary COPY to runtime stage..."

        # Find the runtime stage (usually "FROM.*base" or last FROM)
        RUNTIME_LINE=$(grep -n "^FROM" Dockerfile | tail -1 | cut -d: -f1)

        if [ -n "$RUNTIME_LINE" ]; then
            # Add COPY command after runtime FROM line
            cat > /tmp/ote-copy.txt << EOF

# Copy OTE extension binary (added by migration)
COPY --from=builder /go/src/github.com/<org>/<component-name>/tests-extension/bin/<extension-name>-tests-ext.gz /usr/bin/
EOF
            sed -i "${RUNTIME_LINE}r /tmp/ote-copy.txt" Dockerfile
            echo "✅ Added OTE binary COPY to runtime stage"
        fi

        rm -f /tmp/ote-build-stage.txt /tmp/ote-copy.txt
    fi
else
    echo "No Dockerfile found - creating Dockerfile.ote with OTE binary build"

    # Create a complete Dockerfile for OTE binary
    cat > Dockerfile.ote << EOF
# Multi-stage Dockerfile for OTE Extension Binary
# Generated by ote-migration plugin

# Build stage - Build the OTE test extension binary
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.17 AS builder
WORKDIR /go/src/github.com/<org>/<component-name>

# Copy source code
COPY . .

# Build the OTE extension binary
RUN make tests-ext-build

# Compress the binary (following OpenShift pattern)
RUN gzip tests-extension/bin/<extension-name>-tests-ext

# Runtime stage - Copy compressed binary
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9

# Copy the compressed OTE binary to /usr/bin/
COPY --from=builder /go/src/github.com/<org>/<component-name>/tests-extension/bin/<extension-name>-tests-ext.gz /usr/bin/

# Add any additional runtime dependencies here
# COPY other binaries, set ENTRYPOINT, etc.
EOF

    echo "✅ Created Dockerfile.ote - merge this into your main Dockerfile"
fi

echo ""
echo "Dockerfile update complete!"
echo ""
echo "OTE Binary Location in Image: /usr/bin/<extension-name>-tests-ext.gz"
echo "To register with origin, use path: /usr/bin/<extension-name>-tests-ext.gz"
echo ""
```

**Key Points:**
- Automatically detects existing Dockerfile and modifies it, or creates Dockerfile.ote if none exists
- Creates backup (Dockerfile.pre-ote-migration) before modifying
- Adds OTE binary build to existing builder stage if present
- Compiles extension binary using `make tests-ext-build`
- Compresses binary with gzip following OpenShift conventions
- Copies compressed binary to `/usr/bin/<extension-name>-tests-ext.gz` in runtime image
- Binary path can be registered to origin: `/usr/bin/<extension-name>-tests-ext.gz`
- Works for both monorepo (Variant A and B) and single-module strategies

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
if [ -d "$TEST_CODE_DIR" ]; then
    cp -r "$TEST_CODE_DIR" "$BACKUP_DIR/test-backup"
    echo "Backup created at: $BACKUP_DIR/test-backup"
fi

# Error tracking
PHASE5_FAILED=0

# Cleanup function
cleanup_on_error() {
    if [ $PHASE5_FAILED -eq 1 ]; then
        echo "❌ Phase 5 failed - rolling back test files..."
        if [ -d "$BACKUP_DIR/test-backup" ]; then
            rm -rf "$TEST_CODE_DIR"
            cp -r "$BACKUP_DIR/test-backup" "$TEST_CODE_DIR"
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

# Get root module name
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Auto-detect testdata import path based on directory structure
# If test/e2e/<test-dir-name> exists (subdirectory mode): $MODULE_NAME/test/e2e/<test-dir-name>/testdata
# If only test/e2e exists (direct mode): $MODULE_NAME/test/e2e/testdata
if [ -d "test/e2e/<test-dir-name>" ]; then
    # Subdirectory mode
    TESTDATA_IMPORT="$MODULE_NAME/test/e2e/<test-dir-name>/testdata"
    TEST_FILES=$(grep -rl "testdata\.FixturePath" test/e2e/<test-dir-name>/ --include="*_test.go" 2>/dev/null || true)
else
    # Direct mode
    TESTDATA_IMPORT="$MODULE_NAME/test/e2e/testdata"
    TEST_FILES=$(grep -rl "testdata\.FixturePath" test/e2e/ --include="*_test.go" 2>/dev/null || true)
fi

if [ -z "$TEST_FILES" ]; then
    echo "No test files need testdata import"
else
    echo "Using testdata import path: $TESTDATA_IMPORT"

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
    TESTDATA_IMPORT="github.com/openshift/<extension-name>-tests-extension/test/e2e/testdata"

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
- **[OTP]**: Added to ALL Describe blocks (marks tests that have been ported)
- **[Level0]**: Added by creating SEPARATE Describe blocks for Level0 tests

**Important annotation logic:**
1. Add `[OTP]` to ALL Describe blocks (right after `[sig-xxx]`)
2. Identify tests with `-LEVEL0-` suffix in their names
3. Create a SEPARATE Describe block with `[sig-xxx][OTP][Level0]` for Level0 tests
4. Move Level0 tests to the new Describe block
5. Remove `-LEVEL0-` suffix from test names

**Example:**
```go
// Before migration:
var _ = g.Describe("[sig-cco] Cluster_Operator CCO is enabled", func() {
    defer g.GinkgoRecover()
    var oc = compat_otp.NewCLI("default-cco", compat_otp.KubeConfigPath())

    g.It("Author:mihuang-High-23352-Cloud credential operator", func() {})
    g.It("Author:mihuang-Critical-33204-LEVEL0-[cco-passthrough]IPI", func() {})
    g.It("Author:jshu-Critical-36498-LEVEL0-CCO credentials secret", func() {})
})

// After migration:
var _ = g.Describe("[sig-cco][OTP] Cluster_Operator CCO is enabled", func() {
    defer g.GinkgoRecover()
    var oc = compat_otp.NewCLI("default-cco", compat_otp.KubeConfigPath())

    g.It("Author:mihuang-High-23352-Cloud credential operator", func() {})
})

var _ = g.Describe("[sig-cco][OTP][Level0] Cluster_Operator CCO is enabled", func() {
    defer g.GinkgoRecover()
    var oc = compat_otp.NewCLI("default-cco", compat_otp.KubeConfigPath())

    g.It("Author:mihuang-Critical-33204-[cco-passthrough]IPI", func() {})
    g.It("Author:jshu-Critical-36498-CCO credentials secret", func() {})
})

// Full test names become:
// "[sig-cco][OTP] Cluster_Operator CCO is enabled Author:mihuang-High-23352-Cloud credential operator"
// "[sig-cco][OTP][Level0] Cluster_Operator CCO is enabled Author:mihuang-Critical-33204-[cco-passthrough]IPI"
// "[sig-cco][OTP][Level0] Cluster_Operator CCO is enabled Author:jshu-Critical-36498-CCO credentials secret"
```

**Note:** This same code works for both monorepo and single-module strategies.

```bash
echo "========================================="
echo "Adding [OTP] and [Level0] annotations..."
echo "Sig filter tags: $SIG_FILTER_TAGS"
echo "Test directory: test/$TEST_DIR_NAME"
echo "========================================="

# Create Python script for per-Describe-block annotation
cat > /tmp/annotate_tests.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def find_describe_blocks(lines):
    """Find Describe block ranges by tracking brace nesting."""
    describe_blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for g.Describe lines
        if 'g.Describe("' in line and 'func()' in line:
            # Extract the Describe line signature
            match = re.search(r'g\.Describe\("([^"]+)"', line)
            if match:
                desc_text = match.group(1)
                # Find the opening brace (might be on same line or next line)
                start_line = i
                found_opening_line = None
                for j in range(i, min(i + 5, len(lines))):  # Check next few lines
                    if '{' in lines[j]:
                        found_opening_line = j
                        break

                if found_opening_line is not None:
                    # Track braces to find the end of this Describe block
                    # Start with brace count of 1 (for the opening brace we found)
                    brace_count = 1
                    j = found_opening_line
                    # Count braces on the opening line
                    brace_count += lines[j].count('{') - lines[j].count('}') - 1
                    j += 1

                    # Continue from next line until braces balance
                    while j < len(lines) and brace_count > 0:
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        j += 1

                    describe_blocks.append({
                        'line_num': i,
                        'desc_text': desc_text,
                        'start': start_line,
                        'end': j
                    })
        i += 1

    return describe_blocks

def find_level0_tests(lines):
    """Find all tests with -LEVEL0- suffix and their line ranges."""
    level0_tests = {}
    current_test_id = None
    current_test_start = None
    brace_count = 0
    in_test = False

    for i, line in enumerate(lines):
        # Check for g.It() lines with -LEVEL0-
        if ('g.It(' in line or 'g.It (' in line) and '-LEVEL0-' in line:
            # Extract a unique test identifier (use line number as ID)
            current_test_id = str(i)
            current_test_start = i
            in_test = True
            brace_count = 0

        if in_test:
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and current_test_start is not None:
                # End of test found
                level0_tests[current_test_id] = (current_test_start, i)
                in_test = False
                current_test_start = None
                current_test_id = None

    return level0_tests

def annotate_file(filepath, sig_tags):
    """
    Add [OTP] to Describe blocks and create separate Level0 Describe blocks.

    Strategy:
    1. Add [OTP] to all Describe blocks
    2. Find tests with -LEVEL0- suffix
    3. Extract those tests from the original Describe block
    4. Create a new Describe block with [Level0] for those tests
    5. Remove -LEVEL0- suffix from test names
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    original_content = ''.join(lines)

    # Step 1: Find all Describe blocks
    describe_blocks = find_describe_blocks(lines)

    # Step 2: Add [OTP] to ALL Describe blocks
    for block in describe_blocks:
        desc_line = lines[block['line_num']]
        if 'g.Describe' in desc_line and '[OTP]' not in desc_line:
            lines[block['line_num']] = re.sub(
                r'g\.Describe\("\[sig-([^\]]+)\]([^"]*)"',
                r'g.Describe("[sig-\1][OTP]\2"',
                desc_line
            )

    # Step 3: Find Level0 tests
    level0_tests = find_level0_tests(lines)

    if not level0_tests:
        # No Level0 tests, just remove -LEVEL0- if present and return
        for i, line in enumerate(lines):
            if '-LEVEL0-' in line:
                lines[i] = line.replace('-LEVEL0-', '-')

        new_content = ''.join(lines)
        if new_content != original_content:
            with open(filepath, 'w') as f:
                f.write(new_content)
            return True
        return False

    # Step 4: Extract Level0 tests and setup variables
    level0_test_content = []
    for test_id, (start, end) in sorted(level0_tests.items(), key=lambda x: x[1][0]):
        level0_test_content.extend(lines[start:end+1])

    # Step 5: Remove Level0 tests from original positions (in reverse order)
    for test_id, (start, end) in sorted(level0_tests.items(), key=lambda x: x[1][0], reverse=True):
        del lines[start:end+1]

    # Step 6: Extract Describe block setup code from first Describe block
    first_describe = None
    for block in describe_blocks:
        if '[sig-' in lines[block['line_num']]:
            first_describe = block
            break

    if not first_describe:
        print(f"Warning: No sig-tagged Describe block found in {filepath}")
        return False

    # Extract setup code (var declarations, BeforeEach, etc.) from first Describe
    # Look for lines between Describe and first g.It()
    setup_lines = []
    desc_line_num = first_describe['line_num']

    # Get the Describe declaration with [OTP] added
    desc_text = lines[desc_line_num]
    match = re.search(r'g\.Describe\("(\[sig-[^\]]+\]\[OTP\][^"]*)"', desc_text)
    if match:
        base_desc_text = match.group(1)
        # Create Level0 version
        level0_desc_text = base_desc_text.replace('[OTP]', '[OTP][Level0]')
    else:
        print(f"Warning: Could not extract Describe text from {filepath}")
        return False

    # Find setup code (between Describe line and first g.It())
    i = desc_line_num + 1
    while i < len(lines) and not ('g.It(' in lines[i] or 'g.It (' in lines[i]):
        setup_lines.append(lines[i])
        i += 1

    # Step 7: Create new Level0 Describe block
    level0_describe = [f'var _ = g.Describe("{level0_desc_text}", func() {{\n']
    level0_describe.extend(setup_lines)
    level0_describe.append('\n')
    level0_describe.extend(level0_test_content)
    level0_describe.append('})\n\n')

    # Step 8: Insert Level0 Describe block right before the last Describe block (disabled tests)
    # Find insertion point (right before "CCO is disabled" Describe block if exists)
    insertion_point = len(lines)
    for i in range(len(lines)):
        if 'g.Describe' in lines[i] and 'disabled' in lines[i].lower():
            insertion_point = i
            break

    # Insert the Level0 Describe block
    for line in reversed(level0_describe):
        lines.insert(insertion_point, line)

    # Step 9: Remove -LEVEL0- suffix from all test names
    for i, line in enumerate(lines):
        if '-LEVEL0-' in line:
            lines[i] = line.replace('-LEVEL0-', '-')

    # Write back
    new_content = ''.join(lines)
    with open(filepath, 'w') as f:
        f.write(new_content)
    return True

if __name__ == '__main__':
    test_dir = sys.argv[1]
    sig_tags = sys.argv[2].split(',')
    sig_tags = [tag.strip() for tag in sig_tags]

    test_files = list(Path(test_dir).rglob('*.go'))

    for filepath in test_files:
        changed = annotate_file(str(filepath), sig_tags)
        if changed:
            print(f"✓ {filepath}")
        else:
            print(f"- {filepath} (no changes)")
PYTHON_SCRIPT

chmod +x /tmp/annotate_tests.py

# Run the Python script
python3 /tmp/annotate_tests.py "test/$TEST_DIR_NAME" "$SIG_FILTER_TAGS"

echo ""
echo "✅ Annotations added successfully"
echo ""
echo "Summary of changes:"
echo "  [OTP]       - Added to ALL Describe blocks with sig tags (format: [sig-xxx][OTP])"
echo "  [Level0]    - Separate Describe block created with [sig-xxx][OTP][Level0] for Level0 tests"
echo "  -LEVEL0-    - Removed suffix from test names"
echo ""
echo "Expected results:"
echo "  • Regular Describe: g.Describe(\"[sig-xxx][OTP] Test Suite\", ...)"
echo "  • Level0 Describe:  g.Describe(\"[sig-xxx][OTP][Level0] Test Suite\", ...)"
echo "  • Test names: -LEVEL0- suffix removed"
echo "  • Full test names for Level0 tests will start with [sig-xxx][OTP][Level0]"
```


#### Step 5: Validate Tags and Annotations

**Purpose:** Verify that all required tags are properly applied before proceeding to build verification.

**Note:** This same code works for both monorepo and single-module strategies.

```bash
echo ""
echo "========================================="
echo "Validating tags and annotations..."
echo "========================================="

VALIDATION_FAILED=0

# Find all test files
TEST_FILES=$(find "$TEST_CODE_DIR" -name '*_test.go' -type f)
TOTAL_FILES=$(echo "$TEST_FILES" | wc -l)

echo "Found $TOTAL_FILES test files to validate"

# Get sig tags for validation
IFS=',' read -ra SIG_TAGS <<< "$SIG_FILTER_TAGS"

# Validation 1: Check for [OTP] tag in Describe blocks
echo ""
echo "Validation 1: Checking for [OTP] tags in Describe blocks..."
MISSING_OTP_TAG=0
for file in $TEST_FILES; do
    # Check each sig tag
    for sig_tag in "${SIG_TAGS[@]}"; do
        sig_tag=$(echo "$sig_tag" | xargs)
        if grep -q "g\.Describe.*\[sig-$sig_tag\]" "$file"; then
            if ! grep -q "g\.Describe.*\[sig-$sig_tag\]\[OTP\]" "$file"; then
                echo "  ❌ Missing [OTP] tag after [sig-$sig_tag] in: $file"
                MISSING_OTP_TAG=$((MISSING_OTP_TAG + 1))
                VALIDATION_FAILED=1
            fi
        fi
    done
done

if [ $MISSING_OTP_TAG -eq 0 ]; then
    echo "  ✅ All Describe blocks have [OTP] tag"
else
    echo "  ❌ $MISSING_OTP_TAG file(s) missing [OTP] tag"
fi

# Validation 2: Check that -LEVEL0- suffix is removed from files with [Level0] tag
echo ""
echo "Validation 2: Checking for -LEVEL0- suffix removal..."
LEVEL0_NOT_REMOVED=0
for file in $TEST_FILES; do
    # Check if file has [Level0] tag in Describe and still contains -LEVEL0- anywhere
    for sig_tag in "${SIG_TAGS[@]}"; do
        sig_tag=$(echo "$sig_tag" | xargs)
        if grep -q "g\.Describe.*\[sig-$sig_tag\]\[OTP\]\[Level0\]" "$file"; then
            if grep -q -- '-LEVEL0-' "$file"; then
                echo "  ❌ File has [Level0] in Describe but still contains -LEVEL0- suffix: $file"
                LEVEL0_NOT_REMOVED=$((LEVEL0_NOT_REMOVED + 1))
                VALIDATION_FAILED=1
                break
            fi
        fi
    done
done

if [ $LEVEL0_NOT_REMOVED -eq 0 ]; then
    echo "  ✅ All -LEVEL0- suffixes properly removed"
else
    echo "  ❌ $LEVEL0_NOT_REMOVED file(s) have [Level0] tag but still contain -LEVEL0- suffix"
fi

# Validation 3: Verify testdata imports are present
echo ""
echo "Validation 3: Checking for testdata imports..."
MISSING_TESTDATA_IMPORT=0
for file in $TEST_FILES; do
    # Only check files that use testdata.FixturePath
    if grep -q 'testdata\.FixturePath' "$file"; then
        if ! grep -q 'testdata' "$file" || ! grep -q 'import' "$file"; then
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
    echo "Migration is ready to proceed to Phase 6 (Dependency Resolution)"
else
    echo "❌ Validation failed!"
    echo ""
    echo "Please review and fix the issues above before proceeding."
    echo "Common fixes:"
    echo "  - Re-run Step 4 (Add OTP and Level0 Annotations)"
    echo "  - Manually verify sed commands executed successfully"
    echo "  - Check that [OTP] appears right after [sig-xxx] in Describe blocks"
    echo "  - Check that [Level0] appears after [OTP] for files with Level0 tests"
    echo "  - Ensure -LEVEL0- suffix is completely removed from test names"
    echo ""
    echo "After fixing, you can re-run this validation step."
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
cd <working-dir>/test/e2e

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
TEST_REPLACES=$(grep -A 1000 "^replace (" test/e2e/go.mod | grep -v "^replace (" | grep "=>" | grep -v "^)" || echo "")

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

# Add required dependencies to root module
echo ""
echo "Adding required dependencies to root module..."

# Detect module name from root go.mod
ROOT_MODULE=$(grep "^module " go.mod | awk '{print $2}')

# Add test extension module dependency
echo "Adding test extension module dependency..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "$ROOT_MODULE/test/e2e"

# Add origin util dependency (required for most tests)
echo "Adding origin util dependency..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/openshift/origin/test/extended/util

# Add kubernetes framework dependency (required for test framework)
echo "Adding kubernetes framework dependency..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get k8s.io/kubernetes/test/e2e/framework

echo "✅ Dependencies added to root module"

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
# 1. Generate bindata from test/e2e/testdata/ (or subdirectory if applicable)
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

    # Show current branch
    CURRENT_BRANCH=$(git branch --show-current)
    echo "Current branch: $CURRENT_BRANCH"
    echo ""

    echo "Files to commit:"
    echo "  - go.mod (root module with test/e2e replace directive)"
    echo "  - cmd/extension/main.go"
    echo "  - test/e2e/go.mod"
    echo "  - test/e2e/go.sum"
    echo "  - test/e2e/*.go (test files - may be in subdirectory)"
    echo "  - test/e2e/testdata/fixtures.go (or subdirectory)"
    echo "  - test/e2e/bindata.mk (or subdirectory if test/e2e already existed)"
    echo "  - Makefile updates"
else
    echo "❌ Build failed - manual intervention required"
    echo "Common issues:"
    echo "  - Check import paths in test files and cmd/extension/main.go"
    echo "  - Verify all test dependencies are available in test/e2e/go.mod"
    echo "  - Run 'go mod tidy' in test/e2e directory"
    echo "  - Check for invalid replace directives in test/e2e/go.mod"
    echo "  - Ensure root go.mod has: replace $MODULE_NAME/test/e2e => ./test/e2e"
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
└── openshift-tests-private/          # Source repo (if cloned to workspace)
```

## Configuration

**Extension:** <extension-name>
**Strategy:** Multi-module (integrated into existing repo)
**Working Directory:** <working-dir>

**Source Repository:** git@github.com:openshift/openshift-tests-private.git
  - Local Path: <local-source-path> (or "Cloned to openshift-tests-private")
  - Test Subfolder: test/extended/<test-subfolder>/
  - Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

**Module Configuration:**
  - Root Module: $MODULE_NAME
  - Test Module: $MODULE_NAME/test/e2e
  - Replace Directive: Added to root go.mod replace section

## Files Created/Modified

### Generated Code
- ✅ `cmd/extension/main.go` - OTE entry point (source code at repository root)
- ✅ `bin/<extension-name>-tests-ext` - Compiled binary (created by `make extension`)
- ✅ `test/e2e/go.mod` - Test module with OpenShift replace directives
- ✅ `test/e2e/testdata/fixtures.go` (or subdirectory) - Testdata wrapper functions
- ✅ `test/e2e/bindata.mk` (or subdirectory) - Bindata generation rules (same level as testdata/)
- ✅ `go.mod` (updated) - Added test/e2e replace directive
- ✅ `Makefile` (updated) - Added extension build target

### Test Files (Fully Automated)
- ✅ Copied **X** test files to `test/e2e/` (or subdirectory if test/e2e already exists)
- ✅ Copied **Y** testdata files to `test/e2e/testdata/` (or subdirectory)
- ✅ Automatically replaced `compat_otp.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically replaced `exutil.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically added imports: `$MODULE_NAME/test/e2e/testdata` (or subdirectory)
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
# Navigate to test module directory
# If test/e2e didn't exist: cd <working-dir>/test/e2e
# If test/e2e exists: cd <working-dir>/test/e2e/<test-dir-name>
cd <working-dir>/<test-module-dir>

# Get the commit hash from go.mod for openshift-tests-extension
OTE_COMMIT=$(grep "openshift-tests-extension" go.mod | grep -o '[0-9a-f]\{12\}' | head -1)

# Complete dependency resolution using commit hash (avoids timestamp issues)
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@${OTE_COMMIT}"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

# Resolve all dependencies (auto-download required Go version if needed)
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

# Download all modules
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download

# Verify files are created
ls -la go.mod go.sum

# Return to root
cd <working-dir>
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
  - Local Path: <local-source-path> (or "Cloned to openshift-tests-private")
  - Test Subfolder: test/extended/<test-subfolder>/
  - Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

**Target Repository:** <target-repo-url>
  - Local Path: <local-target-path> (or "Cloned to <repo-name>")

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
- ✅ Copied **Y** testdata files to `test/e2e/testdata/`
- ✅ Vendored dependencies to `vendor/`
- ✅ Automatically replaced `compat_otp.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically replaced `exutil.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically added imports: `github.com/<org>/<extension-name>-tests-extension/test/e2e/testdata`
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

- Always check if `<repo-name>` exists before cloning (repo name extracted from URL)
- Source repo clones to `openshift-tests-private` in workspace directory
- Target repo clones to `<repo-name>` in workspace directory (e.g., `router` for `openshift/router.git`)
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
