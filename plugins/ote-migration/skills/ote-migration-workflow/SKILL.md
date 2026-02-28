---
name: OTE Migration Workflow
description: Automated workflow for migrating OpenShift component repositories to OTE framework
---

# OTE Migration Workflow Skill

This skill provides step-by-step implementation guidance for the complete OTE migration workflow.

## When to Use This Skill

Use this skill when executing the `/ote-migration:migrate` command to automate the migration of OpenShift component repositories to the openshift-tests-extension (OTE) framework.

## Prerequisites

- Go toolchain (1.21+)
- Git installed and configured
- Access to openshift-tests-private repository:
  - **Option 1**: Existing local clone (with optional update)
  - **Option 2**: Git credentials to clone from `git@github.com:openshift/openshift-tests-private.git`
- Target component repository:
  - **Option 1**: Local path to existing repository
  - **Option 2**: Git URL to clone repository

## Overview

The migration is an **8-phase workflow** that collects configuration, sets up repositories, creates structure, generates code, migrates tests, resolves dependencies, integrates with Docker, and provides documentation.

**Workflow Summary:**

**ALL 8 PHASES ARE MANDATORY - EXECUTE EACH PHASE IN ORDER:**

1. User Input Collection (9 inputs - includes Dockerfile integration choice)
2. Repository Setup (source and target)
3. Structure Creation (directories and files)
4. Code Generation (go.mod, main.go, Makefile, bindata.mk, fixtures.go)
5. Test Migration (automated with rollback on failure)
6. Dependency Resolution (go mod tidy + vendor + build verification)
7. **Dockerfile Integration (uses choice from Input 9)**
8. Final Summary and Next Steps

**DO NOT skip Phase 7. After Phase 6 completes, proceed immediately to Phase 7.**

**Key Design Principles:**
- **No sig filtering**: All tests included without filtering logic
- **CMD at root** (monorepo): `cmd/<extension-name>-tests-ext/main.go` (not under test/)
- **Simple annotations**: [OTP] at beginning of Describe, [Level0] at beginning of test name only
- **Single go.mod** (monorepo): All dependencies in root go.mod (no separate test module)
- **Vendor at root** (monorepo): Only `vendor/` at repository root
- **No compress/copy targets**: Removed from root Makefile

## Migration Phases

### Phase 1: User Input Collection (9 inputs)

Collect all necessary information from the user before starting the migration.

**CRITICAL INSTRUCTIONS:**
- **Extension name (Input 4)**: AUTO-DETECT from target repository - do NOT ask user
- **All other inputs**: Ask user explicitly using AskUserQuestion tool or direct prompts
- **WAIT for user response** before proceeding to the next input or phase
- **Switch to target repository** happens after Input 3 (before auto-detecting extension name)
- **Dockerfile integration (Input 10)**: Ask user choice - will be used in Phase 7

**Variables collected** (shown as `<variable-name>`) will be used throughout the migration.

#### Input 1: Directory Structure Strategy

Ask: "Which directory structure strategy do you want to use?"

**Option 1: Monorepo strategy (integrate into existing repo)**
- Integrates into existing repository structure
- Uses existing `cmd/` and `test/` directories
- **CMD location**: `cmd/extension/main.go` (at repository root, NOT under test/)
- **Single go.mod**: All dependencies in root go.mod (no separate test module)
- **Vendor location**: `vendor/` at root ONLY

**Option 2: Single-module strategy (isolated directory)**
- Creates isolated `tests-extension/` directory
- Self-contained with single `go.mod`
- **CMD location**: `tests-extension/cmd/main.go`
- **Vendor location**: `tests-extension/vendor/`

User selects: **1** or **2**

Store the selection in variable: `<structure-strategy>` (value: "monorepo" or "single-module")

#### Input 2: Working Directory (Workspace)

Ask: "What is the working directory path for migration workspace?

**IMPORTANT**: This is a temporary workspace for cloning repositories. Your target repository will be collected in the next step (Input 3), and that's where OTE files will be created."

**Purpose:**
- Temporary location for cloning repositories that don't exist locally
- Recommendation: Parent directory of your target repo or temporary directory

**User provides the path:**
- Can be absolute or relative
- Can be current directory (`.`)
- Will create if doesn't exist

**Store in variable:** `<working-dir>`

#### Input 3: Target Repository

Ask: "What is the path to your target repository, or provide a Git URL to clone?"

- **Option 1: Local path** - Use existing local repository (e.g., `/home/user/repos/router`)
- **Option 2: Git URL** - Clone from remote repository (e.g., `git@github.com:openshift/router.git`)

**Store in variable:** `<target-repo-path>` or `<target-repo-url>`

#### Input 3a: Update Local Target Repository (if local target provided)

If a local target repository path was provided:

Ask: "Do you want to update the local target repository? (git fetch && git pull) [Y/n]:"
- Default: Yes
- Store in variable: `<update-target>` (value: "yes" or "no")

#### Input 3b: Validate and Switch to Target Repository

**Step 1: Validate and update target repository**

For local path:
```bash
# Validate target repository exists
if [ ! -d "$TARGET_REPO_PATH" ]; then
    echo "❌ ERROR: Target repository does not exist"
    exit 1
fi

# Check if git repository and update if requested
if [ -d "$TARGET_REPO_PATH/.git" ]; then
    cd "$TARGET_REPO_PATH"

    if [ "<update-target>" = "yes" ]; then
        CURRENT_BRANCH=$(git branch --show-current)
        TARGET_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
        git fetch "$TARGET_REMOTE"
        git pull "$TARGET_REMOTE" "$CURRENT_BRANCH"
    fi
fi
```

For Git URL:
```bash
# Extract repository name
REPO_NAME=$(echo "$TARGET_REPO_URL" | sed -E 's|.*/([^/]+)\.git$|\1|')
cd "$WORKING_DIR"
git clone "$TARGET_REPO_URL" "$REPO_NAME"
TARGET_REPO_PATH="$WORKING_DIR/$REPO_NAME"

# Create feature branch
cd "$TARGET_REPO_PATH"
BRANCH_NAME="ote-migration-$(date +%Y%m%d)"
git checkout -b "$BRANCH_NAME"
```

**Step 2: Switch working directory to target repository**

```bash
cd "$TARGET_REPO_PATH"
WORKING_DIR="$TARGET_REPO_PATH"

echo "========================================="
echo "Switched to target repository"
echo "Working directory is now: $WORKING_DIR"
echo "========================================="
```

**CRITICAL**: From this point forward, all operations happen in the target repository.

#### Input 4: Extension Name (Auto-Detection)

**DO NOT ask the user for this - auto-detect it from the target repository.**

```bash
cd "$WORKING_DIR"

if [ -d ".git" ]; then
    DISCOVERED_REMOTE=$(git remote -v | head -1 | awk '{print $1}')
    if [ -n "$DISCOVERED_REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$DISCOVERED_REMOTE" 2>/dev/null)
        EXTENSION_NAME=$(echo "$REMOTE_URL" | sed 's/.*[:/]\([^/]*\)\/\([^/]*\)\.git$/\2/' | sed 's/\.git$//')
    else
        EXTENSION_NAME=$(basename "$WORKING_DIR")
    fi
else
    EXTENSION_NAME=$(basename "$WORKING_DIR")
fi

echo "Extension name auto-detected: $EXTENSION_NAME"
```

**Store in variable:** `<extension-name>`

#### Input 4a: Target Test Directory Name (Conditional - Monorepo Mode Only)

**This input is ONLY asked if:**
1. Monorepo strategy is selected (from Input 1)
2. Target repository already has `test/e2e/` directory

**Purpose**: When migrating to a repository that already has `test/e2e/`, we need to create a subdirectory to avoid conflicts with existing tests.

**Detection logic:**
```bash
cd "$WORKING_DIR"

if [ "$STRUCTURE_STRATEGY" = "monorepo" ] && [ -d "test/e2e" ]; then
    echo "⚠️  Target repository already has test/e2e/ directory"
    echo "Tests will be migrated to a subdirectory under test/e2e/"

    # Ask for target test directory name
    TARGET_TEST_DIR_NAME=""
fi
```

**If test/e2e exists, ask:**

Ask: "What subdirectory name should be used under test/e2e/ for migrated tests? (default: extension):"
- Default: "extension"
- Example: If you enter "router", tests will be at `test/e2e/router/`
- Example: If you press Enter, tests will be at `test/e2e/extension/`

**Store in variable:** `<target-test-dir>` (default: "extension" if empty)

**If test/e2e does NOT exist:**
```bash
# No subdirectory needed - tests go directly in test/e2e/
TARGET_TEST_DIR_NAME=""
```

**Store in variable:** `<target-test-dir>` (empty string)

#### Input 5: Local Source Repository (Optional)

Ask: "Do you have a local clone of openshift-tests-private? If yes, provide the path (or press Enter to clone):"

**Store in variable:** `<local-source-path>` (empty if user wants to clone)

#### Input 6: Update Local Source Repository (if local source provided)

If local source provided:
Ask: "Do you want to update the local source repository? (git fetch && git pull) [Y/n]:"

**Store in variable:** `<update-source>` (value: "yes" or "no")

#### Input 7: Source Test Subfolder

Ask: "What is the test subfolder name under test/extended/?"
- Example: "networking", "router", "storage"

**Store in variable:** `<test-subfolder>`

#### Input 8: Source Testdata Subfolder (Optional)

**IMPORTANT**: This determines which testdata fixtures are copied from the source OTE repository.
The testdata files are embedded into bindata.go and accessed via FixturePath() calls in tests.

Ask: "What is the testdata subfolder name under test/extended/testdata/?"

**Options:**
- Press **Enter** to use the same value as the test subfolder (Input 7)
- Enter a **subfolder name** (e.g., "router", "networking") if different from test subfolder
- Enter **"none"** if no testdata fixtures exist for these tests

**Default**: Same as Input 7 (recommended for most cases)

**Examples:**
- If test subfolder is "router" and testdata is at `test/extended/testdata/router/`, press Enter
- If test subfolder is "router" but testdata is at `test/extended/testdata/edge/`, enter "edge"
- If no testdata files exist, enter "none"

**AI MUST execute this verification** before asking the user:
```bash
# List testdata subdirectories to help user answer
if [ -d "<source-repo>/test/extended/testdata" ]; then
    echo "Available testdata subdirectories:"
    ls -la "<source-repo>/test/extended/testdata/" | grep "^d" | grep -v "^\.$" | awk '{print $NF}'
else
    echo "No testdata directory found at <source-repo>/test/extended/testdata"
fi
```

Then present the discovered subdirectories to the user and ask for their choice.

**Store in variable:** `<testdata-subfolder>`

#### Input 9: Dockerfile Integration Choice

Ask: "Do you want to update Dockerfiles automatically, or do it manually?"

**Options:**
1. **Automated** - Let the plugin update your Dockerfiles automatically (with backup)
2. **Manual** - Get instructions to update Dockerfiles yourself

**Store in variable:** `<dockerfile-choice>` (value: "automated" or "manual")

#### Input 9a: Select Dockerfiles to Update (conditional - only if automated)

**This input is ONLY asked if user chose "automated" in Input 9.**

If user chose automated, search for all Dockerfiles in the target repository and ask user to select:

```bash
cd <working-dir>  # Should already be in target repository from Input 3

echo "Searching for Dockerfiles in target repository..."

# Search for all Dockerfiles recursively
DOCKERFILES=$(find . -type f \( -name "Dockerfile" -o -name "Dockerfile.*" \) ! -path "*/vendor/*" ! -path "*/.git/*" ! -path "*/tests-extension/*" 2>/dev/null)

if [ -z "$DOCKERFILES" ]; then
    echo "⚠️  No Dockerfiles found in repository"
    echo "You can add Dockerfiles later and integrate manually, or continue without Dockerfile integration"
    SELECTED_DOCKERFILES=""
else
    # Display found Dockerfiles
    echo ""
    echo "Found Dockerfiles:"
    echo "$DOCKERFILES" | nl -w2 -s'. '
    echo ""
fi
```

**If Dockerfiles were found, ask user to select:**

Ask: "Which Dockerfile(s) do you want to update?"

**Options:**
- Enter a number (e.g., `1` for first Dockerfile)
- Enter `all` to update all Dockerfiles
- Enter `none` to skip Dockerfile integration

**Example:**
```text
Found Dockerfiles:
 1. ./Dockerfile
 2. ./Dockerfile.rhel8
 3. ./build/Dockerfile

Which Dockerfile(s) do you want to update? (number, 'all', or 'none'):
```

**Store user selection:**

```bash
# Get user choice
CHOICE=<user-input>

if [ -z "$DOCKERFILES" ] || [ "$CHOICE" = "none" ]; then
    SELECTED_DOCKERFILES=""
    echo "Skipping Dockerfile integration"
elif [ "$CHOICE" = "all" ]; then
    SELECTED_DOCKERFILES="$DOCKERFILES"
    echo "Selected: All Dockerfiles"
else
    # Convert to array and get selected file
    DOCKERFILES_ARRAY=($DOCKERFILES)
    if [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le "${#DOCKERFILES_ARRAY[@]}" ]; then
        SELECTED_DOCKERFILES="${DOCKERFILES_ARRAY[$((CHOICE-1))]}"
        echo "Selected: $SELECTED_DOCKERFILES"
    else
        echo "❌ Invalid choice"
        exit 1
    fi
fi
```

**Store in variable:** `<selected-dockerfiles>` (space-separated list of Dockerfile paths, or empty if none)

#### Display Configuration Summary

Show all collected inputs for user confirmation before proceeding:

```text
========================================
Migration Configuration Summary
========================================
Strategy:              <structure-strategy>
Workspace:             <working-dir>
Target Repository:     <target-repo-path>
Update Target Repo:    <update-target or "cloned from URL" or "N/A">
Extension Name:        <extension-name>
Target Test Directory: <target-test-dir or "test/e2e (no subdirectory)" or "N/A (single-module)">
Source Repository:     <local-source-path or "will clone">
Update Source Repo:    <update-source or "will clone" or "N/A">
Test Subfolder:        <test-subfolder>
Testdata Subfolder:    <testdata-subfolder>
Dockerfile Integration: <dockerfile-choice>
Selected Dockerfiles:  <selected-dockerfiles or "manual integration" or "none">
========================================
```

**Example output (local target with existing test/e2e, automated Dockerfile):**
```text
========================================
Migration Configuration Summary
========================================
Strategy:              monorepo
Workspace:             /home/user/repos
Target Repository:     /home/user/repos/router
Update Target Repo:    yes
Extension Name:        router
Target Test Directory: test/e2e/extension
Source Repository:     /home/user/openshift-tests-private
Update Source Repo:    yes
Test Subfolder:        router
Testdata Subfolder:    router
Dockerfile Integration: automated
Selected Dockerfiles:  ./Dockerfile, ./Dockerfile.rhel8
========================================
```

**Example output (local target without test/e2e, automated Dockerfile):**
```text
========================================
Migration Configuration Summary
========================================
Strategy:              monorepo
Workspace:             /home/user/repos
Target Repository:     /home/user/repos/mycomponent
Update Target Repo:    yes
Extension Name:        mycomponent
Target Test Directory: test/e2e (no subdirectory)
Source Repository:     /home/user/openshift-tests-private
Update Source Repo:    yes
Test Subfolder:        mycomponent
Testdata Subfolder:    mycomponent
Dockerfile Integration: automated
Selected Dockerfiles:  ./Dockerfile
========================================
```

**Example output (cloned target, manual Dockerfile, single-module strategy):**
```text
========================================
Migration Configuration Summary
========================================
Strategy:              single-module
Workspace:             /tmp/migration
Target Repository:     /tmp/migration/router
Update Target Repo:    cloned from URL
Extension Name:        router
Target Test Directory: N/A (single-module)
Source Repository:     will clone
Update Source Repo:    N/A
Test Subfolder:        router
Testdata Subfolder:    router
Dockerfile Integration: manual
Selected Dockerfiles:  manual integration
========================================
```

Ask: "Proceed with migration? [Y/n]:"

#### Phase 1 Validation Checkpoint

**MANDATORY VALIDATION:**

```bash
# Verify extension name detected
if [ -z "$EXTENSION_NAME" ]; then
    echo "❌ ERROR: Extension name not detected"
    exit 1
fi

# Verify strategy selected
if [ -z "$STRUCTURE_STRATEGY" ]; then
    echo "❌ ERROR: Strategy not selected"
    exit 1
fi

# Verify target repository path collected
if [ -z "$TARGET_REPO_PATH" ]; then
    echo "❌ ERROR: Target repository path not collected"
    exit 1
fi

# Verify working directory switched to target
if [ "$WORKING_DIR" != "$TARGET_REPO_PATH" ]; then
    echo "❌ ERROR: Working directory not switched to target"
    exit 1
fi

echo "✅ Phase 1 Validation Complete"
```

### Phase 2: Repository Setup

#### Step 1: Setup Source Repository

**For local source:**
```bash
SOURCE_REPO="<local-source-path>"

if [ "<update-source>" = "yes" ]; then
    cd "$SOURCE_REPO"
    CURRENT_BRANCH=$(git branch --show-current)

    # Checkout main/master if on different branch
    if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
        if git show-ref --verify --quiet refs/heads/main; then
            git checkout main
            TARGET_BRANCH="main"
        else
            git checkout master
            TARGET_BRANCH="master"
        fi
    else
        TARGET_BRANCH="$CURRENT_BRANCH"
    fi

    SOURCE_REMOTE=$(git remote -v | awk '{print $1}' | head -1)
    git fetch "$SOURCE_REMOTE"
    git pull "$SOURCE_REMOTE" "$TARGET_BRANCH"
fi
```

**For cloning:**
```bash
cd <working-dir>

if [ -d "openshift-tests-private" ]; then
    cd openshift-tests-private
    SOURCE_REMOTE=$(git remote -v | grep 'openshift/openshift-tests-private' | head -1 | awk '{print $1}')
    git fetch "$SOURCE_REMOTE"
    git pull "$SOURCE_REMOTE" master || git pull "$SOURCE_REMOTE" main
    cd ..
else
    git clone git@github.com:openshift/openshift-tests-private.git openshift-tests-private
fi

SOURCE_REPO="openshift-tests-private"
```

**Set source paths:**
```bash
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

### Phase 3: Structure Creation

#### Step 1: Create Directory Structure

**For Monorepo Strategy:**

```bash
cd <working-dir>

# Set directory paths based on whether test/e2e already exists
if [ -n "$TARGET_TEST_DIR_NAME" ]; then
    # test/e2e exists - use subdirectory
    TEST_CODE_DIR="test/e2e/$TARGET_TEST_DIR_NAME"
    TESTDATA_DIR="test/e2e/$TARGET_TEST_DIR_NAME/testdata"
    echo "Using test subdirectory: test/e2e/$TARGET_TEST_DIR_NAME/"
else
    # No test/e2e - use test/e2e directly
    TEST_CODE_DIR="test/e2e"
    TESTDATA_DIR="test/e2e/testdata"
    echo "Using test directory: test/e2e/"
fi

# Create directories
# IMPORTANT: cmd follows pattern cmd/extension/, NOT under test/
mkdir -p "cmd/extension"
mkdir -p bin
mkdir -p "$TEST_CODE_DIR"
mkdir -p "$TESTDATA_DIR"

echo "✅ Created monorepo structure"
echo "   CMD directory: cmd/extension/"
echo "   Test code: $TEST_CODE_DIR"
echo "   Testdata: $TESTDATA_DIR"
```

**For Single-Module Strategy:**

```bash
cd <working-dir>
mkdir -p tests-extension

cd tests-extension
mkdir -p cmd
mkdir -p bin
mkdir -p test/e2e
mkdir -p test/e2e/testdata

echo "✅ Created single-module structure"
```

#### Step 2: Copy Test Files

**For Monorepo:**
```bash
cp -r "$SOURCE_TEST_PATH"/* "$TEST_CODE_DIR"/
echo "Copied $(find "$TEST_CODE_DIR" -name '*_test.go' | wc -l) test files"
```

**For Single-Module:**
```bash
cp -r "$SOURCE_TEST_PATH"/* test/e2e/
echo "Copied $(find test/e2e -name '*_test.go' | wc -l) test files"
```

#### Step 3: Copy Testdata

**IMPORTANT**: This step copies fixture files from the source OTE repository's testdata directory.
If testdata files are not copied, bindata generation will only embed fixtures.go, causing runtime panics
when tests try to load fixture files via FixturePath().

**For Monorepo:**
```bash
if [ -n "$SOURCE_TESTDATA_PATH" ] && [ "$SOURCE_TESTDATA_PATH" != "" ]; then
    echo "Copying testdata from: $SOURCE_TESTDATA_PATH"
    echo "Target testdata directory: $TESTDATA_DIR"

    if [ -n "<testdata-subfolder>" ] && [ "<testdata-subfolder>" != "none" ]; then
        # Copy with subfolder structure preserved
        mkdir -p "$TESTDATA_DIR/<testdata-subfolder>"
        cp -rv "$SOURCE_TESTDATA_PATH"/* "$TESTDATA_DIR/<testdata-subfolder>/" || {
            echo "❌ Failed to copy testdata files"
            exit 1
        }
        echo "✅ Copied testdata files to $TESTDATA_DIR/<testdata-subfolder>/"
        ls -la "$TESTDATA_DIR/<testdata-subfolder>/" | head -10
    else
        # Copy without subfolder (flatten)
        cp -rv "$SOURCE_TESTDATA_PATH"/* "$TESTDATA_DIR/" || {
            echo "❌ Failed to copy testdata files"
            exit 1
        }
        echo "✅ Copied testdata files to $TESTDATA_DIR/"
        ls -la "$TESTDATA_DIR/" | head -10
    fi
else
    echo "⚠️  No testdata files to copy (SOURCE_TESTDATA_PATH is empty or 'none')"
fi
```

**For Single-Module:**
```bash
if [ -n "$SOURCE_TESTDATA_PATH" ] && [ "$SOURCE_TESTDATA_PATH" != "" ]; then
    echo "Copying testdata from: $SOURCE_TESTDATA_PATH"
    echo "Target testdata directory: test/e2e/testdata"

    if [ -n "<testdata-subfolder>" ] && [ "<testdata-subfolder>" != "none" ]; then
        # Copy with subfolder structure preserved
        mkdir -p "test/e2e/testdata/<testdata-subfolder>"
        cp -rv "$SOURCE_TESTDATA_PATH"/* "test/e2e/testdata/<testdata-subfolder>/" || {
            echo "❌ Failed to copy testdata files"
            exit 1
        }
        echo "✅ Copied testdata files to test/e2e/testdata/<testdata-subfolder>/"
        ls -la "test/e2e/testdata/<testdata-subfolder>/" | head -10
    else
        # Copy without subfolder (flatten)
        cp -rv "$SOURCE_TESTDATA_PATH"/* test/e2e/testdata/ || {
            echo "❌ Failed to copy testdata files"
            exit 1
        }
        echo "✅ Copied testdata files to test/e2e/testdata/"
        ls -la "test/e2e/testdata/" | head -10
    fi
else
    echo "⚠️  No testdata files to copy (SOURCE_TESTDATA_PATH is empty or 'none')"
fi

# Verify testdata files were copied (excluding fixtures.go and bindata.go)
TESTDATA_FILE_COUNT=$(find "$TESTDATA_DIR" -type f ! -name "fixtures.go" ! -name "bindata.go" 2>/dev/null | wc -l)
if [ "$TESTDATA_FILE_COUNT" -eq 0 ]; then
    echo "⚠️  WARNING: No testdata fixture files found in $TESTDATA_DIR"
    echo "This may cause test failures if tests use FixturePath() to load fixtures."
    echo "Verify that testdata-subfolder input was correct."
fi
```

**For Single-Module:**
```bash
# Same validation for single-module
TESTDATA_FILE_COUNT=$(find test/e2e/testdata -type f ! -name "fixtures.go" ! -name "bindata.go" 2>/dev/null | wc -l)
if [ "$TESTDATA_FILE_COUNT" -eq 0 ]; then
    echo "⚠️  WARNING: No testdata fixture files found in test/e2e/testdata"
    echo "This may cause test failures if tests use FixturePath() to load fixtures."
    echo "Verify that testdata-subfolder input was correct."
fi
```

### Phase 4: Code Generation

#### Step 1: Generate/Update go.mod Files

**For Monorepo Strategy:**

```bash
cd <working-dir>

# Add OTE test dependencies to root go.mod (single module approach)
echo "Adding OTE test dependencies to root go.mod..."

# Add dependencies
OTE_LATEST=$(git ls-remote https://github.com/openshift-eng/openshift-tests-extension.git refs/heads/main | awk '{print $1}')
OTE_SHORT="${OTE_LATEST:0:12}"

echo "Adding OTE dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"; then
    echo "❌ Failed to get openshift-tests-extension"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/openshift-eng/openshift-tests-extension@latest"
        exit 1
    fi
fi
echo "✅ OTE dependency added"

echo "Adding origin dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"; then
    echo "❌ Failed to get github.com/openshift/origin@main"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/openshift/origin@main"
        exit 1
    fi
fi
echo "✅ Origin dependency added"

echo "Adding Ginkgo dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest; then
    echo "❌ Failed to get ginkgo"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/onsi/ginkgo/v2@latest"
        exit 1
    fi
fi
echo "✅ Ginkgo dependency added"

echo "Adding Gomega dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest; then
    echo "❌ Failed to get gomega"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/onsi/gomega@latest"
        exit 1
    fi
fi
echo "✅ Gomega dependency added"

# Copy replace directives from openshift-tests-private to root go.mod
# IMPORTANT: Filter out openshift-tests-private itself to avoid importing entire test suite
echo "Copying replace directives from openshift-tests-private..."

if [ -n "$SOURCE_REPO" ]; then
    grep -A 1000 "^replace" "$SOURCE_REPO/go.mod" | grep -B 1000 "^)" | \
        grep -v "^replace" | grep -v "^)" | \
        grep -v "github.com/openshift/openshift-tests-private" > /tmp/replace_directives.txt

    # Check if replace block already exists in root go.mod
    if ! grep -q "^replace (" go.mod; then
        echo "" >> go.mod
        echo "replace (" >> go.mod
        cat /tmp/replace_directives.txt >> go.mod
        echo ")" >> go.mod
    else
        # Append to existing replace block (before closing parenthesis)
        # Find the line number of the closing ) for replace block
        REPLACE_CLOSE_LINE=$(grep -n "^replace (" go.mod | head -1 | cut -d: -f1)
        # Find next closing ) after replace (
        NEXT_CLOSE=$(tail -n +$((REPLACE_CLOSE_LINE + 1)) go.mod | grep -n "^)" | head -1 | cut -d: -f1)
        REPLACE_CLOSE_LINE=$((REPLACE_CLOSE_LINE + NEXT_CLOSE))

        # Insert before closing )
        head -n $((REPLACE_CLOSE_LINE - 1)) go.mod > /tmp/go.mod.tmp
        cat /tmp/replace_directives.txt >> /tmp/go.mod.tmp
        tail -n +$REPLACE_CLOSE_LINE go.mod >> /tmp/go.mod.tmp
        mv /tmp/go.mod.tmp go.mod
    fi
    rm -f /tmp/replace_directives.txt
fi

# Step 4b: Align Ginkgo version with OTE framework (newer version is backward compatible)
# IMPORTANT: Use OTE's Ginkgo version (December 2024), NOT OTP's older version (August 2024)
# The December 2024 fork is backward compatible with August 2024 code from OTP
echo "Aligning Ginkgo version with OTE framework..."
OTE_REPO="https://github.com/openshift-eng/openshift-tests-extension.git"
OTE_GINKGO_VERSION=$(git ls-remote "$OTE_REPO" refs/heads/main | xargs -I {} git ls-remote https://github.com/openshift-eng/openshift-tests-extension {} | git archive --remote=https://github.com/openshift-eng/openshift-tests-extension HEAD go.mod 2>/dev/null | tar -xO | grep "github.com/onsi/ginkgo/v2 =>" | awk '{print $NF}' 2>/dev/null || echo "v2.6.1-0.20241205171354-8006f302fd12")

# Fallback to known working version if detection fails
if [ -z "$OTE_GINKGO_VERSION" ]; then
    OTE_GINKGO_VERSION="v2.6.1-0.20241205171354-8006f302fd12"
    echo "ℹ️  Using fallback OTE Ginkgo version: $OTE_GINKGO_VERSION"
else
    echo "ℹ️  Detected OTE Ginkgo version: $OTE_GINKGO_VERSION"
fi

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@$OTE_GINKGO_VERSION"
echo "✅ Ginkgo aligned to OTE framework version (backward compatible with OTP)"

echo "✅ Monorepo go.mod setup complete (single module with all dependencies)"
```

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

# Extract Go version from target repo or use default
if [ -f "$TARGET_REPO/go.mod" ]; then
    GO_VERSION=$(grep '^go ' "$TARGET_REPO/go.mod" | awk '{print $2}')
else
    GO_VERSION="1.21"
fi

go mod init github.com/openshift/<extension-name>-tests-extension
sed -i "s/^go .*/go $GO_VERSION/" go.mod

# Add dependencies
OTE_LATEST=$(git ls-remote https://github.com/openshift-eng/openshift-tests-extension.git refs/heads/main | awk '{print $1}')
OTE_SHORT="${OTE_LATEST:0:12}"

echo "Adding OTE dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"; then
    echo "❌ Failed to get openshift-tests-extension"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/openshift-eng/openshift-tests-extension@latest"
        exit 1
    fi
fi
echo "✅ OTE dependency added"

echo "Adding origin dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"; then
    echo "❌ Failed to get github.com/openshift/origin@main"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/openshift/origin@main"
        exit 1
    fi
fi
echo "✅ Origin dependency added"

echo "Adding Ginkgo dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest; then
    echo "❌ Failed to get ginkgo"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/onsi/ginkgo/v2@latest"
        exit 1
    fi
fi
echo "✅ Ginkgo dependency added"

echo "Adding Gomega dependency..."
if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest; then
    echo "❌ Failed to get gomega"
    echo "Retrying..."
    sleep 2
    if ! GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest; then
        echo "❌ Failed after retry - you may need to run manually: go get github.com/onsi/gomega@latest"
        exit 1
    fi
fi
echo "✅ Gomega dependency added"

# Copy replace directives
# IMPORTANT: Filter out openshift-tests-private itself to avoid importing entire test suite
SOURCE_PATH="../$SOURCE_REPO"

grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
    grep -v "^replace" | grep -v "^)" | \
    grep -v "github.com/openshift/openshift-tests-private" > /tmp/replace_directives.txt

echo "" >> go.mod
echo "replace (" >> go.mod
cat /tmp/replace_directives.txt >> go.mod
echo ")" >> go.mod
rm -f /tmp/replace_directives.txt

# Step 4b: Align Ginkgo version with OTE framework (newer version is backward compatible)
# IMPORTANT: Use OTE's Ginkgo version (December 2024), NOT OTP's older version (August 2024)
# The December 2024 fork is backward compatible with August 2024 code from OTP
echo "Aligning Ginkgo version with OTE framework..."
OTE_REPO="https://github.com/openshift-eng/openshift-tests-extension.git"
OTE_GINKGO_VERSION=$(git ls-remote "$OTE_REPO" refs/heads/main | xargs -I {} git ls-remote https://github.com/openshift-eng/openshift-tests-extension {} | git archive --remote=https://github.com/openshift-eng/openshift-tests-extension HEAD go.mod 2>/dev/null | tar -xO | grep "github.com/onsi/ginkgo/v2 =>" | awk '{print $NF}' 2>/dev/null || echo "v2.6.1-0.20241205171354-8006f302fd12")

# Fallback to known working version if detection fails
if [ -z "$OTE_GINKGO_VERSION" ]; then
    OTE_GINKGO_VERSION="v2.6.1-0.20241205171354-8006f302fd12"
    echo "ℹ️  Using fallback OTE Ginkgo version: $OTE_GINKGO_VERSION"
else
    echo "ℹ️  Detected OTE Ginkgo version: $OTE_GINKGO_VERSION"
fi

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@$OTE_GINKGO_VERSION"
echo "✅ Ginkgo aligned to OTE framework version (backward compatible with OTP)"

# Generate minimal go.sum
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download || echo "⚠️  Will retry in Phase 6"

cd ..
```

#### Step 2: Generate Extension Binary (main.go)

**For Monorepo Strategy:**

**IMPORTANT:**
- CMD Location: `cmd/extension/main.go` (at repository root, NOT under test/)
- NO sig filtering logic
- Single module approach: imports test package from same module

```bash
cd <working-dir>
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Re-derive variables from Phase 1/3 using IDENTICAL logic
# (Variables don't persist between phases - need to re-calculate)

# EXTENSION_NAME: Use same logic as Phase 1 Input 4
if [ -d ".git" ]; then
    DISCOVERED_REMOTE=$(git remote -v | head -1 | awk '{print $1}')
    if [ -n "$DISCOVERED_REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$DISCOVERED_REMOTE" 2>/dev/null)
        EXTENSION_NAME=$(echo "$REMOTE_URL" | sed 's/.*[:/]\([^/]*\)\/\([^/]*\)\.git$/\2/' | sed 's/\.git$//')
    else
        EXTENSION_NAME=$(basename "$(pwd)")
    fi
else
    EXTENSION_NAME=$(basename "$(pwd)")
fi

# TARGET_TEST_DIR_NAME: Detect from filesystem (user-created directory from Phase 3)
TARGET_TEST_DIR_NAME=""
if [ -d "test/e2e" ]; then
    # Check if test/e2e has subdirectories besides testdata
    SUBDIRS=$(find test/e2e -mindepth 1 -maxdepth 1 -type d ! -name testdata 2>/dev/null)
    if [ -n "$SUBDIRS" ]; then
        # Has subdirectories - find the one with Go test files
        for dir in $SUBDIRS; do
            if ls "$dir"/*_test.go >/dev/null 2>&1; then
                TARGET_TEST_DIR_NAME=$(basename "$dir")
                break
            fi
        done
    fi
fi

# Determine test import path based on whether test/e2e has subdirectory
if [ -n "$TARGET_TEST_DIR_NAME" ]; then
    # test/e2e exists with subdirectory (e.g., github.com/openshift/router/test/e2e/extension)
    TEST_IMPORT="$MODULE_NAME/test/e2e/$TARGET_TEST_DIR_NAME"
    TEST_FILTER_PATH="/test/e2e/$TARGET_TEST_DIR_NAME/"
    echo "Tests are at: test/e2e/$TARGET_TEST_DIR_NAME/"
else
    # No subdirectory - use test/e2e directly (e.g., github.com/openshift/router/test/e2e)
    TEST_IMPORT="$MODULE_NAME/test/e2e"
    TEST_FILTER_PATH="/test/e2e/"
    echo "Tests are at: test/e2e/"
fi

# Create main.go at cmd/extension/main.go
cat > "cmd/extension/main.go" << 'EOF'
package main

import (
    "fmt"
    "os"
    "regexp"
    "strings"

    "github.com/spf13/cobra"
    "k8s.io/component-base/logs"

    "github.com/openshift-eng/openshift-tests-extension/pkg/cmd"
    e "github.com/openshift-eng/openshift-tests-extension/pkg/extension"
    et "github.com/openshift-eng/openshift-tests-extension/pkg/extension/extensiontests"
    g "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"
    "github.com/openshift/origin/test/extended/util"
    compat_otp "github.com/openshift/origin/test/extended/util/compat_otp"
    framework "k8s.io/kubernetes/test/e2e/framework"

    // Import testdata package from same module
    _ "<TEST_IMPORT>/testdata"

    // Import test packages from same module
    _ "<TEST_IMPORT>"
)

func main() {
    // Initialize test framework flags (required for kubeconfig, provider, etc.)
    util.InitStandardFlags()
    framework.AfterReadingAllFlags(&framework.TestContext)

    logs.InitLogs()
    defer logs.FlushLogs()

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs from Ginkgo
    // Note: ModuleTestsOnly() is applied by default, which filters out /vendor/ and k8s.io/kubernetes tests
    allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

    // Filter to only include tests from this module's test directory
    // Excludes tests from /go/pkg/mod/ (module cache) and /vendor/
    componentSpecs := allSpecs.Select(func(spec *et.ExtensionTestSpec) bool {
        for _, loc := range spec.CodeLocations {
            // Include tests from local test directory (not from module cache or vendor)
            if strings.Contains(loc, "<TEST_FILTER_PATH>") && !strings.Contains(loc, "/go/pkg/mod/") && !strings.Contains(loc, "/vendor/") {
                return true
            }
        }
        return false
    })

    // Initialize test framework before all tests
    componentSpecs.AddBeforeAll(func() {
        if err := compat_otp.InitTest(false); err != nil {
            panic(err)
        }
    })

    // Process all specs
    componentSpecs.Walk(func(spec *et.ExtensionTestSpec) {
        // Apply platform filters based on Platform: labels
        for label := range spec.Labels {
            if strings.HasPrefix(label, "Platform:") {
                platformName := strings.TrimPrefix(label, "Platform:")
                spec.Include(et.PlatformEquals(platformName))
            }
        }

        // Apply platform filters based on [platform:xxx] in test names
        re := regexp.MustCompile(`\[platform:([a-z]+)\]`)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }

        // Set lifecycle to Informing
        spec.Lifecycle = et.LifecycleInforming
    })

    // Add filtered component specs to extension
    ext.AddSpecs(componentSpecs)

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
EOF

# Replace placeholders
sed -i "s|<TEST_IMPORT>|$TEST_IMPORT|g" "cmd/extension/main.go"
sed -i "s|<TEST_FILTER_PATH>|$TEST_FILTER_PATH|g" "cmd/extension/main.go"
sed -i "s|<extension-name>|$EXTENSION_NAME|g" "cmd/extension/main.go"
sed -i "s|<Extension Name>|${EXTENSION_NAME^}|g" "cmd/extension/main.go"
sed -i "s|<MODULE_PATH>|$MODULE_NAME|g" "cmd/extension/main.go"

echo "✅ Created cmd/extension/main.go"
```

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

cat > cmd/main.go << 'EOF'
package main

import (
    "fmt"
    "os"
    "regexp"
    "strings"

    "github.com/spf13/cobra"
    "k8s.io/component-base/logs"

    "github.com/openshift-eng/openshift-tests-extension/pkg/cmd"
    e "github.com/openshift-eng/openshift-tests-extension/pkg/extension"
    et "github.com/openshift-eng/openshift-tests-extension/pkg/extension/extensiontests"
    g "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"
    "github.com/openshift/origin/test/extended/util"
    compat_otp "github.com/openshift/origin/test/extended/util/compat_otp"
    framework "k8s.io/kubernetes/test/e2e/framework"

    // Import testdata package from this module
    _ "github.com/openshift/<extension-name>-tests-extension/test/e2e/testdata"

    // Import test packages from this module
    _ "github.com/openshift/<extension-name>-tests-extension/test/e2e"
)

func main() {
    // Initialize test framework flags (required for kubeconfig, provider, etc.)
    util.InitStandardFlags()
    framework.AfterReadingAllFlags(&framework.TestContext)

    logs.InitLogs()
    defer logs.FlushLogs()

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs from Ginkgo
    // Note: ModuleTestsOnly() is applied by default, which filters out /vendor/ and k8s.io/kubernetes tests
    allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

    // Filter to only include tests from this module's test/e2e/ directory
    // Excludes tests from /go/pkg/mod/ (module cache) and /vendor/
    componentSpecs := allSpecs.Select(func(spec *et.ExtensionTestSpec) bool {
        for _, loc := range spec.CodeLocations {
            // Include tests from local test/e2e/ directory (not from module cache or vendor)
            if strings.Contains(loc, "/test/e2e/") && !strings.Contains(loc, "/go/pkg/mod/") && !strings.Contains(loc, "/vendor/") {
                return true
            }
        }
        return false
    })

    // Initialize test framework before all tests
    componentSpecs.AddBeforeAll(func() {
        if err := compat_otp.InitTest(false); err != nil {
            panic(err)
        }
    })

    // Process all specs
    componentSpecs.Walk(func(spec *et.ExtensionTestSpec) {
        // Apply platform filters based on Platform: labels
        for label := range spec.Labels {
            if strings.HasPrefix(label, "Platform:") {
                platformName := strings.TrimPrefix(label, "Platform:")
                spec.Include(et.PlatformEquals(platformName))
            }
        }

        // Apply platform filters based on [platform:xxx] in test names
        re := regexp.MustCompile(`\[platform:([a-z]+)\]`)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }

        // Set lifecycle to Informing
        spec.Lifecycle = et.LifecycleInforming
    })

    // Add filtered component specs to extension
    ext.AddSpecs(componentSpecs)

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
EOF

sed -i "s|<extension-name>|$EXTENSION_NAME|g" cmd/main.go
sed -i "s|<Extension Name>|${EXTENSION_NAME^}|g" cmd/main.go
sed -i "s|<Extension Name>|${EXTENSION_NAME^}|g" cmd/main.go
```

#### Step 3: Create bindata.mk

**For Monorepo:**

```bash
cd <working-dir>

# Re-derive directory paths from Phase 3
# (Variables don't persist between phases - need to re-calculate)
if [ -d "test/e2e" ]; then
    # Check if test/e2e has subdirectories besides testdata
    SUBDIRS=$(find test/e2e -mindepth 1 -maxdepth 1 -type d ! -name testdata 2>/dev/null)
    if [ -n "$SUBDIRS" ]; then
        TESTDATA_DIR=""
        # Has subdirectories - find the one with testdata
        for dir in $SUBDIRS; do
            if [ -d "$dir/testdata" ]; then
                TESTDATA_DIR="$dir/testdata"
                break
            fi
        done
        # Fallback if no matching subdir had testdata
        if [ -z "$TESTDATA_DIR" ]; then
            TESTDATA_DIR="test/e2e/testdata"
        fi
    else
        # No subdirectories - use test/e2e/testdata directly
        TESTDATA_DIR="test/e2e/testdata"
    fi
else
    echo "❌ Cannot find test/e2e directory"
    exit 1
fi

echo "Using testdata directory: $TESTDATA_DIR"

# bindata.mk location: at root for single-module monorepo approach
cat > "bindata.mk" << 'EOF'
TESTDATA_PATH := <TESTDATA_DIR>
GOPATH ?= $(shell go env GOPATH)
GO_BINDATA := $(GOPATH)/bin/go-bindata

$(GO_BINDATA):
	@echo "Installing go-bindata..."
	@GOFLAGS= go install github.com/go-bindata/go-bindata/v3/go-bindata@latest

.PHONY: update-bindata
update-bindata: $(GO_BINDATA)
	@echo "Generating bindata for testdata files..."
	$(GO_BINDATA) \
		-nocompress \
		-nometadata \
		-prefix "<TESTDATA_DIR>" \
		-pkg testdata \
		-o <TESTDATA_DIR>/bindata.go \
		<TESTDATA_DIR>/...
	@gofmt -s -w <TESTDATA_DIR>/bindata.go
	@echo "✅ Bindata generated successfully"

.PHONY: verify-bindata
verify-bindata: update-bindata
	@echo "Verifying bindata is up to date..."
	git diff --exit-code $(TESTDATA_PATH)/bindata.go || (echo "❌ Bindata is out of date" && exit 1)
	@echo "✅ Bindata is up to date"

.PHONY: bindata
bindata: clean-bindata update-bindata

.PHONY: clean-bindata
clean-bindata:
	@echo "Cleaning bindata..."
	@rm -f $(TESTDATA_PATH)/bindata.go
EOF

# Replace placeholders
sed -i "s|<TESTDATA_DIR>|$TESTDATA_DIR|g" "bindata.mk"

echo "✅ Created bindata.mk at root"
```

**For Single-Module:**

```bash
cd <working-dir>/tests-extension

cat > test/e2e/bindata.mk << 'EOF'
TESTDATA_PATH := testdata
GOPATH ?= $(shell go env GOPATH)
GO_BINDATA := $(GOPATH)/bin/go-bindata

$(GO_BINDATA):
	@echo "Installing go-bindata..."
	@GOFLAGS= go install github.com/go-bindata/go-bindata/v3/go-bindata@latest

.PHONY: update-bindata
update-bindata: $(GO_BINDATA)
	@echo "Generating bindata..."
	@mkdir -p $(TESTDATA_PATH)
	$(GO_BINDATA) -nocompress -nometadata \
		-pkg testdata -o $(TESTDATA_PATH)/bindata.go -prefix "testdata" $(TESTDATA_PATH)/...
	@gofmt -s -w $(TESTDATA_PATH)/bindata.go
	@echo "✅ Bindata generated successfully"

.PHONY: verify-bindata
verify-bindata: update-bindata
	@echo "Verifying bindata is up to date..."
	git diff --exit-code $(TESTDATA_PATH)/bindata.go || (echo "❌ Bindata is out of date" && exit 1)
	@echo "✅ Bindata is up to date"

.PHONY: bindata
bindata: clean-bindata update-bindata

.PHONY: clean-bindata
clean-bindata:
	@rm -f $(TESTDATA_PATH)/bindata.go
EOF

echo "✅ Created test/e2e/bindata.mk"
```

#### Step 4: Create/Update Makefile

**For Monorepo Strategy:**

**IMPORTANT: Do NOT add tests-ext-compress or tests-ext-copy targets**

```bash
cd <working-dir>

# Re-derive EXTENSION_NAME using IDENTICAL logic as Phase 1
# (Variables don't persist between phases - need to re-calculate)
if [ -d ".git" ]; then
    DISCOVERED_REMOTE=$(git remote -v | head -1 | awk '{print $1}')
    if [ -n "$DISCOVERED_REMOTE" ]; then
        REMOTE_URL=$(git remote get-url "$DISCOVERED_REMOTE" 2>/dev/null)
        EXTENSION_NAME=$(echo "$REMOTE_URL" | sed 's/.*[:/]\([^/]*\)\/\([^/]*\)\.git$/\2/' | sed 's/\.git$//')
    else
        EXTENSION_NAME=$(basename "$(pwd)")
    fi
else
    EXTENSION_NAME=$(basename "$(pwd)")
fi

if [ ! -f "Makefile" ]; then
    echo "❌ ERROR: No root Makefile found"
    exit 1
fi

if grep -q "tests-ext-build" Makefile; then
    echo "⚠️  OTE targets already exist, skipping..."
else
    # Single module approach - build from root
    cat >> Makefile << EOF

# OTE test extension binary configuration
TESTS_EXT_BINARY := bin/$EXTENSION_NAME-tests-ext

.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@\$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -mod=vendor -o \$(TESTS_EXT_BINARY) ./cmd/extension
	@echo "✅ Extension binary built: \$(TESTS_EXT_BINARY)"

.PHONY: extension
extension: tests-ext-build

.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY)
	@\$(MAKE) -f bindata.mk clean-bindata 2>/dev/null || true
EOF

    echo "✅ Root Makefile updated with OTE targets"
fi
```

**For Single-Module:**

```bash
cd <working-dir>/tests-extension

cat > Makefile << EOF
BINARY := bin/$EXTENSION_NAME-tests-ext

.PHONY: build
build:
	@echo "Building extension binary..."
	@cd test/e2e && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o \$(BINARY) ./cmd
	@echo "✅ Binary built: \$(BINARY)"

.PHONY: clean
clean:
	@rm -f \$(BINARY)
	@cd test/e2e && \$(MAKE) -f bindata.mk clean-bindata

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build  - Build extension binary"
	@echo "  clean  - Remove binaries and bindata"
EOF

echo "✅ Created Makefile"
```

#### Step 5: Create fixtures.go

Create `testdata/fixtures.go` helper file:

**For Monorepo:**

```bash
cd <working-dir>

cat > "$TESTDATA_DIR/fixtures.go" << 'EOF'
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
    fixtureDir string
)

func init() {
    var err error
    fixtureDir, err = ioutil.TempDir("", "testdata-fixtures-")
    if err != nil {
        panic(fmt.Sprintf("failed to create fixture directory: %v", err))
    }
}

func FixturePath(elem ...string) string {
    relativePath := filepath.Join(elem...)
    targetPath := filepath.Join(fixtureDir, relativePath)

    if _, err := os.Stat(targetPath); err == nil {
        return targetPath
    }

    if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
        panic(fmt.Sprintf("failed to create directory for %s: %v", relativePath, err))
    }

    bindataPath := relativePath
    tempDir, err := os.MkdirTemp("", "bindata-extract-")
    if err != nil {
        panic(fmt.Sprintf("failed to create temp directory: %v", err))
    }
    defer os.RemoveAll(tempDir)

    if err := RestoreAsset(tempDir, bindataPath); err != nil {
        if err := RestoreAssets(tempDir, bindataPath); err != nil {
            panic(fmt.Sprintf("failed to restore fixture %s: %v", relativePath, err))
        }
    }

    extractedPath := filepath.Join(tempDir, bindataPath)
    if err := os.Rename(extractedPath, targetPath); err != nil {
        panic(fmt.Sprintf("failed to move extracted files: %v", err))
    }

    return targetPath
}

func CleanupFixtures() error {
    if fixtureDir != "" {
        return os.RemoveAll(fixtureDir)
    }
    return nil
}

func GetFixtureData(elem ...string) ([]byte, error) {
    relativePath := filepath.Join(elem...)
    cleanPath := relativePath
    if len(cleanPath) > 0 && cleanPath[0] == '/' {
        cleanPath = cleanPath[1:]
    }
    return Asset(cleanPath)
}

func MustGetFixtureData(elem ...string) []byte {
    data, err := GetFixtureData(elem...)
    if err != nil {
        panic(fmt.Sprintf("failed to get fixture data: %v", err))
    }
    return data
}

func FixtureExists(elem ...string) bool {
    relativePath := filepath.Join(elem...)
    cleanPath := relativePath
    if len(cleanPath) > 0 && cleanPath[0] == '/' {
        cleanPath = cleanPath[1:]
    }
    _, err := Asset(cleanPath)
    return err == nil
}

func ListFixtures() []string {
    names := AssetNames()
    fixtures := make([]string, 0, len(names))
    for _, name := range names {
        if strings.HasPrefix(name, "testdata/") {
            fixtures = append(fixtures, strings.TrimPrefix(name, "testdata/"))
        }
    }
    sort.Strings(fixtures)
    return fixtures
}
EOF

echo "✅ Created $TESTDATA_DIR/fixtures.go"
```

**For Single-Module:** Same content, different path (`tests-extension/test/e2e/testdata/fixtures.go`)

### Phase 5: Test Migration (Automated with Error Handling)

This phase migrates test files with atomic error handling and rollback capability.

#### Step 0: Setup Error Handling and Backup

```bash
echo "========================================="
echo "Phase 5: Test Migration (atomic)"
echo "========================================="

# Re-derive directory paths from Phase 3
# (Variables don't persist between phases - need to re-calculate)
if [ -d "test/e2e" ]; then
    # Check if test/e2e has subdirectories besides testdata
    SUBDIRS=$(find test/e2e -mindepth 1 -maxdepth 1 -type d ! -name testdata 2>/dev/null)
    if [ -n "$SUBDIRS" ]; then
        TEST_CODE_DIR=""
        TESTDATA_DIR=""
        # Has subdirectories - find the one with Go test files
        for dir in $SUBDIRS; do
            if ls "$dir"/*_test.go >/dev/null 2>&1; then
                TEST_CODE_DIR="$dir"
                TESTDATA_DIR="$dir/testdata"
                break
            fi
        done
        # Fallback if no subdir contains tests
        if [ -z "$TEST_CODE_DIR" ]; then
            TEST_CODE_DIR="test/e2e"
            TESTDATA_DIR="test/e2e/testdata"
        fi
    else
        # No subdirectories - use test/e2e directly
        TEST_CODE_DIR="test/e2e"
        TESTDATA_DIR="test/e2e/testdata"
    fi
else
    echo "❌ Cannot find test/e2e directory"
    exit 1
fi

echo "Using test directory: $TEST_CODE_DIR"
echo "Using testdata directory: $TESTDATA_DIR"

BACKUP_DIR=$(mktemp -d)
if [ -d "$TEST_CODE_DIR" ]; then
    cp -r "$TEST_CODE_DIR" "$BACKUP_DIR/test-backup"
    echo "Backup created at: $BACKUP_DIR/test-backup"
fi

PHASE5_FAILED=0

cleanup_on_error() {
    if [ $PHASE5_FAILED -eq 1 ]; then
        echo "❌ Phase 5 failed - rolling back..."
        if [ -d "$BACKUP_DIR/test-backup" ]; then
            rm -rf "$TEST_CODE_DIR"
            cp -r "$BACKUP_DIR/test-backup" "$TEST_CODE_DIR"
            echo "✅ Test files restored from backup"
        fi
    fi
    rm -rf "$BACKUP_DIR"
}

trap cleanup_on_error EXIT
```

#### Step 1: Replace FixturePath Calls

```bash
echo "Step 1: Replacing FixturePath calls..."

TEST_FILES=$(grep -rl "FixturePath" "$TEST_CODE_DIR" --include="*_test.go" 2>/dev/null || true)

if [ -n "$TEST_FILES" ]; then
    for file in $TEST_FILES; do
        # Replace compat_otp.FixturePath
        sed -i 's/compat_otp\.FixturePath/testdata.FixturePath/g' "$file"

        # Replace exutil.FixturePath
        sed -i 's/exutil\.FixturePath/testdata.FixturePath/g' "$file"

        # Remove redundant "testdata" prefix
        sed -i 's/testdata\.FixturePath("testdata", /testdata.FixturePath(/g' "$file"
    done
    echo "✅ FixturePath calls replaced"
else
    echo "⚠️  No FixturePath usage found"
fi
```

#### Step 2: Add Testdata Import

```bash
echo "Step 2: Adding testdata imports..."

MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Testdata import path (uses $TESTDATA_DIR from Step 0)
TESTDATA_IMPORT="$MODULE_NAME/$TESTDATA_DIR"

TEST_FILES=$(grep -rl "testdata\.FixturePath" "$TEST_CODE_DIR" --include="*_test.go" 2>/dev/null || true)

for file in $TEST_FILES; do
    # Check if import already exists (avoid ! operator in if statement)
    if grep -q "\"$TESTDATA_IMPORT\"" "$file"; then
        continue  # Skip if already has import
    fi

    # Add import
    if grep -q "^import (" "$file"; then
        sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"" "$file"
    else
        sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
    fi
done

echo "✅ Testdata imports added"

# Fix import ordering using goimports (Go standard tool)
if command -v goimports >/dev/null 2>&1; then
    echo "Step 2b: Fixing import ordering with goimports..."
    goimports -w "$TEST_CODE_DIR"/*.go 2>/dev/null || true
    echo "✅ Import ordering fixed"
else
    echo "⚠️  goimports not found - import ordering may not follow Go conventions"
    echo "   Install with: go install golang.org/x/tools/cmd/goimports@latest"
fi
```

#### Step 3: Add e2e framework import where needed

**IMPORTANT**: If tests use `e2e.Logf()` or `e2e.Failf()`, they need the e2e framework import. Add it to files that use these functions.

```bash
echo "Step 3: Adding e2e framework import where needed..."

TEST_FILES=$(find "$TEST_CODE_DIR" -name '*.go' -type f)

for file in $TEST_FILES; do
    # Check if file uses e2e.Logf or e2e.Failf
    if grep -q "e2e\.Logf\|e2e\.Failf" "$file"; then
        # Check if e2e import already exists (avoid ! operator)
        if grep -q "e2e \"k8s.io/kubernetes/test/e2e/framework\"" "$file"; then
            : # Already has import, do nothing
        else
            echo "  Adding e2e framework import to: $file"

            # Add import after other imports in import block
            if grep -q "^import (" "$file"; then
                # Find last k8s.io import and add after it, or add before closing paren
                if grep -q "k8s.io" "$file"; then
                    sed -i '/k8s\.io.*$/a\	e2e "k8s.io/kubernetes/test/e2e/framework"' "$file"
                else
                    sed -i '/^import (/a\	e2e "k8s.io/kubernetes/test/e2e/framework"' "$file"
                fi
            else
                # Create import block
                sed -i "/^package /a\\\\nimport (\n\te2e \"k8s.io/kubernetes/test/e2e/framework\"\n)" "$file"
            fi
        fi
    fi

    # Comment out compat_otp import if not used (avoid ! operator)
    HAS_COMPAT_IMPORT=$(grep -c "compat_otp" "$file" || echo 0)
    HAS_COMPAT_USAGE=$(grep -c "compat_otp\." "$file" || echo 0)
    if [ "$HAS_COMPAT_IMPORT" -gt 0 ] && [ "$HAS_COMPAT_USAGE" -eq 0 ]; then
        sed -i 's|^\(\s*\)"\(.*compat_otp\)"|// \1"\2" // Replaced|g' "$file"
    fi

    # Comment out exutil import if not used (avoid ! operator)
    HAS_EXUTIL_IMPORT=$(grep -c "github.com/openshift/origin/test/extended/util\"" "$file" || echo 0)
    HAS_EXUTIL_USAGE=$(grep -c "exutil\." "$file" || echo 0)
    if [ "$HAS_EXUTIL_IMPORT" -gt 0 ] && [ "$HAS_EXUTIL_USAGE" -eq 0 ]; then
        sed -i 's|^\(\s*\)"\(github.com/openshift/origin/test/extended/util\)"|// \1"\2" // Replaced|g' "$file"
    fi
done

echo "✅ e2e framework imports added where needed"
```

#### Step 4: Add OTP and Level0 Annotations

**ANNOTATION LOGIC:**
1. Add `[OTP]` at **BEGINNING** of ALL Describe blocks
2. Add `[Level0]` at **BEGINNING** of It string ONLY for tests with "-LEVEL0-" suffix
3. Remove "-LEVEL0-" suffix after adding [Level0]

```bash
echo "Step 4: Adding [OTP] and [Level0] annotations..."

# Create Python script for annotation
cat > /tmp/annotate_tests.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def annotate_file(filepath):
    """
    Add [OTP] to Describe blocks and [Level0] to test names.

    Logic:
    1. Add [OTP] at BEGINNING of all Describe blocks
    2. Add [Level0] at BEGINNING of It string (only for tests with -LEVEL0-)
    3. Remove -LEVEL0- suffix
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    changed = False

    # Step 1: Add [OTP] at BEGINNING of ALL Describe blocks
    for i, line in enumerate(lines):
        if 'g.Describe' in line and '[OTP]' not in line:
            # Add [OTP] at the very beginning of the string
            lines[i] = re.sub(
                r'g\.Describe\("([^"]*)"',
                r'g.Describe("[OTP]\1"',
                line
            )
            changed = True

    # Step 2: Add [Level0] at BEGINNING of It string ONLY for tests with -LEVEL0-
    for i, line in enumerate(lines):
        if ('g.It(' in line or 'g.It (' in line) and '-LEVEL0-' in line:
            # Add [Level0] at beginning and remove -LEVEL0- suffix
            lines[i] = re.sub(
                r'g\.It\("([^"]*)-LEVEL0-([^"]*)"',
                r'g.It("[Level0] \1-\2"',
                line
            )
            changed = True

    if changed:
        with open(filepath, 'w') as f:
            f.writelines(lines)
        return True
    return False

if __name__ == '__main__':
    test_dir = sys.argv[1]
    test_files = list(Path(test_dir).rglob('*.go'))

    updated_count = 0
    for filepath in test_files:
        if annotate_file(str(filepath)):
            print(f"✓ {filepath}")
            updated_count += 1
        else:
            print(f"- {filepath} (no changes)")

    print(f"\n✅ Updated {updated_count} files")
PYTHON_SCRIPT

chmod +x /tmp/annotate_tests.py
python3 /tmp/annotate_tests.py "$TEST_CODE_DIR"

echo ""
echo "Annotation Summary:"
echo "  [OTP]    - Added to ALL Describe blocks at beginning"
echo "  [Level0] - Added to test names with -LEVEL0- suffix only"
echo "  -LEVEL0- - Removed from test names after adding [Level0]"
```

**Expected Results:**

Before:
```go
g.Describe("[sig-router] Router tests", func() {
    g.It("Author:john-LEVEL0-Critical-Test", func() {})
    g.It("Author:jane-High-Test", func() {})
})
```

After:
```go
g.Describe("[OTP][sig-router] Router tests", func() {
    g.It("[Level0] Author:john-Critical-Test", func() {})
    g.It("Author:jane-High-Test", func() {})
})
```

#### Step 5: Validate Tags and Annotations

```bash
echo "Step 5: Validating annotations..."

VALIDATION_FAILED=0
TEST_FILES=$(find "$TEST_CODE_DIR" -name '*_test.go' -type f)

# Check for [OTP] in Describe blocks
MISSING_OTP=0
for file in $TEST_FILES; do
    if grep -q "g\.Describe" "$file"; then
        if ! grep -q "\[OTP\]" "$file"; then
            echo "  ❌ Missing [OTP] in: $file"
            MISSING_OTP=$((MISSING_OTP + 1))
            VALIDATION_FAILED=1
        fi
    fi
done

if [ $MISSING_OTP -eq 0 ]; then
    echo "  ✅ All Describe blocks have [OTP]"
fi

# Check that -LEVEL0- suffix is removed
LEVEL0_NOT_REMOVED=0
for file in $TEST_FILES; do
    if grep -q -- '-LEVEL0-' "$file"; then
        echo "  ❌ Still contains -LEVEL0-: $file"
        LEVEL0_NOT_REMOVED=$((LEVEL0_NOT_REMOVED + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $LEVEL0_NOT_REMOVED -eq 0 ]; then
    echo "  ✅ All -LEVEL0- suffixes removed"
fi

# Check testdata imports for files using FixturePath
MISSING_IMPORT=0
for file in $TEST_FILES; do
    if grep -q "testdata\.FixturePath" "$file" && ! grep -q "\"$TESTDATA_IMPORT\"" "$file"; then
        echo "  ❌ Missing testdata import: $file"
        MISSING_IMPORT=$((MISSING_IMPORT + 1))
        VALIDATION_FAILED=1
    fi
done

if [ $MISSING_IMPORT -eq 0 ]; then
    echo "  ✅ All testdata imports correct"
fi

if [ $VALIDATION_FAILED -eq 1 ]; then
    echo "❌ Validation failed"
    PHASE5_FAILED=1
    exit 1
fi

echo "✅ Phase 5 validation complete"
PHASE5_FAILED=0
```

### Phase 6: Dependency Resolution and Verification

**IMPORTANT: Single module approach - all dependencies in root go.mod**

#### For Monorepo:

**CRITICAL INSTRUCTION: Execute ALL bash commands in this phase EXACTLY as written.**
**Do NOT skip steps based on your interpretation or assumptions.**
**Do NOT generate your own messages - use the echo statements provided.**
**Step 1b MUST execute to ensure k8s.io/kms replace directive exists.**

```bash
cd <working-dir>

echo "========================================="
echo "Phase 6: Dependency Resolution"
echo "========================================="

# Step 1: Detect and fix outdated k8s.io versions
echo "Step 1: Checking for outdated k8s.io versions..."

# Check if go.mod uses old OpenShift kubernetes fork (October 2024 or earlier)
OLD_K8S_COMMITS="1892e4deb967"  # October 2, 2024

if grep -q "$OLD_K8S_COMMITS" go.mod; then
    echo "⚠️  WARNING: Detected outdated OpenShift kubernetes fork (October 2024)"
    echo "OTE framework requires October 2025 fork for compatibility"
    echo ""
    echo "Applying automatic fix..."

    # Backup go.mod before making changes
    cp go.mod go.mod.backup.k8s-version-fix

    # Update all k8s.io packages to October 2025 version
    NEW_K8S_COMMIT_HASH="96593f323733"  # October 17, 2025 commit hash
    NEW_K8S_VERSION="20251017000000-96593f323733"  # Full pseudo-version suffix (timestamp + hash)
    sed -i "s/$OLD_K8S_COMMITS/$NEW_K8S_COMMIT_HASH/g" go.mod
    echo "  ✅ Updated k8s.io packages from October 2024 to October 2025"

    # Add otelgrpc replace if missing
    if ! grep -q "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc =>" go.mod; then
        echo "  Adding otelgrpc replace directive..."
        # Insert after ginkgo replace
        sed -i '/github.com\/onsi\/ginkgo\/v2 =>/a\	go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc => go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.53.0' go.mod
        echo "  ✅ Added otelgrpc v0.53.0 replace directive"
    fi

    # Add k8s.io/externaljwt if missing
    if ! grep -q "k8s.io/externaljwt =>" go.mod; then
        echo "  Adding k8s.io/externaljwt package..."
        # Insert after k8s.io/endpointslice (alphabetically)
        sed -i "/k8s.io\/endpointslice =>/a\	k8s.io/externaljwt => github.com/openshift/kubernetes/staging/src/k8s.io/externaljwt v0.0.0-$NEW_K8S_VERSION" go.mod
        echo "  ✅ Added k8s.io/externaljwt package"
    fi

    # Add k8s.io/kms if missing (required for Docker build compatibility with Go 1.24)
    if ! grep -q "k8s.io/kms =>" go.mod; then
        echo "  Adding k8s.io/kms package..."
        # Insert after k8s.io/kube-scheduler (alphabetically)
        sed -i "/k8s.io\/kube-scheduler =>/a\	k8s.io/kms => github.com/openshift/kubernetes/staging/src/k8s.io/kms v0.0.0-$NEW_K8S_VERSION" go.mod
        echo "  ✅ Added k8s.io/kms package (prevents Docker build Go version errors)"
    fi

    # Remove deprecated k8s.io/legacy-cloud-providers if present
    if grep -q "k8s.io/legacy-cloud-providers" go.mod; then
        echo "  Removing deprecated k8s.io/legacy-cloud-providers..."
        sed -i '/k8s.io\/legacy-cloud-providers/d' go.mod
        echo "  ✅ Removed deprecated package"
    fi

    # Update Ginkgo to October 2025 version if using old version
    OLD_GINKGO="v2.6.1-0.20241205171354-8006f302fd12"  # December 5, 2024
    NEW_GINKGO="v2.6.1-0.20251001123353-fd5b1fb35db1"  # October 1, 2025
    if grep -q "$OLD_GINKGO" go.mod; then
        sed -i "s/$OLD_GINKGO/$NEW_GINKGO/g" go.mod
        echo "  ✅ Updated Ginkgo to October 2025 version"
    fi

    echo "✅ k8s.io version compatibility fix applied"
    echo "   Backup saved to: go.mod.backup.k8s-version-fix"
    echo ""
else
    echo "✅ k8s.io versions are compatible (October 2025 or newer)"
fi

# Step 1b: Ensure k8s.io/kms replace directive exists (required for all repos)
# This must run regardless of k8s.io version to ensure OpenShift fork is used
if ! grep -q "k8s.io/kms =>" go.mod; then
    echo "Step 1b: Adding k8s.io/kms replace directive..."

    # Get current k8s.io pseudo-version from existing replace directives (keep full version)
    CURRENT_K8S_VERSION=$(grep "k8s.io/kubernetes =>" go.mod | grep -o 'v0\.0\.0-[0-9]\{14\}-[a-f0-9]\{12\}' | head -1)

    # Check immediately after extraction
    if [ -z "$CURRENT_K8S_VERSION" ]; then
        echo "❌ CRITICAL: Could not detect k8s.io pseudo-version in go.mod"
        echo "   Expected format: v0.0.0-YYYYMMDDHHMMSS-COMMITHASH"
        echo "   This repo might not have k8s.io/kubernetes replace directives"
        echo "   Cannot determine OpenShift fork version to use for k8s.io/kms"
        exit 1
    fi

    echo "  ✅ Detected k8s.io pseudo-version: $CURRENT_K8S_VERSION"

    # Check if replace section exists
    if grep -q "^replace" go.mod; then
        # Replace section exists - try to insert alphabetically after k8s.io/kube-scheduler
        if grep -q "k8s.io/kube-scheduler =>" go.mod; then
            sed -i "/k8s.io\/kube-scheduler =>/a\	k8s.io/kms => github.com/openshift/kubernetes/staging/src/k8s.io/kms $CURRENT_K8S_VERSION" go.mod
        else
            # No kube-scheduler, insert after k8s.io/kubernetes
            sed -i "/k8s.io\/kubernetes =>/a\	k8s.io/kms => github.com/openshift/kubernetes/staging/src/k8s.io/kms $CURRENT_K8S_VERSION" go.mod
        fi
    else
        # No replace section - create one at the end
        echo "" >> go.mod
        echo "replace (" >> go.mod
        echo "	k8s.io/kms => github.com/openshift/kubernetes/staging/src/k8s.io/kms $CURRENT_K8S_VERSION" >> go.mod
        echo ")" >> go.mod
    fi

    # Verify it was added
    if grep -q "k8s.io/kms =>" go.mod; then
        echo "  ✅ Added k8s.io/kms replace directive (ensures compatibility with OpenShift kubernetes fork)"
    else
        echo "  ❌ Failed to add k8s.io/kms replace directive"
        echo "  This is required to use OpenShift kubernetes fork instead of upstream"
        exit 1
    fi
else
    echo "Step 1b: k8s.io/kms replace directive already exists ✅"
fi

# CRITICAL VERIFICATION: k8s.io/kms MUST exist after Step 1b
# DO NOT REMOVE THIS DIRECTIVE - IT IS REQUIRED FOR COMPATIBILITY
echo "Verifying k8s.io/kms replace directive exists..."
if ! grep -q "k8s.io/kms =>" go.mod; then
    echo "❌ CRITICAL ERROR: k8s.io/kms replace directive was removed or missing"
    echo "   This directive is MANDATORY to use OpenShift kubernetes fork"
    echo "   DO NOT remove k8s.io/kms - it prevents build failures"
    echo "   Redirects from upstream k8s.io/kms to OpenShift fork"
    exit 1
fi
echo "✅ Verification passed: k8s.io/kms replace directive exists"

# Step 2: Tidy root module
echo "Step 2: Running go mod tidy in root module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -ne 0 ]; then
    echo "❌ go mod tidy failed in root module"
    exit 1
fi
echo "✅ Root module dependencies resolved"

# Step 3: Vendor at ROOT
echo "Step 3: Running go mod vendor in root module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod vendor

if [ $? -ne 0 ]; then
    echo "❌ go mod vendor failed in root module"
    exit 1
fi
echo "✅ Root module dependencies vendored (vendor/ at root)"

# Step 4: Build verification
echo "Step 4: Building extension binary for verification..."
make extension

if [ $? -eq 0 ]; then
    echo "✅ Extension binary built successfully"

    # Test binary execution
    ./bin/$EXTENSION_NAME-tests-ext --help > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ Binary executes correctly"
    else
        echo "⚠️  Binary built but execution check failed"
    fi
else
    echo "❌ Build failed"
    exit 1
fi

echo "========================================="
echo "✅ Phase 6 Complete"
echo "========================================="
```

#### For Single-Module:

```bash
cd <working-dir>/tests-extension

echo "========================================="
echo "Phase 6: Dependency Resolution"
echo "========================================="

# Step 1: Verify k8s.io versions after fresh go.mod creation
echo "Step 1: Verifying k8s.io versions..."

# For single-module, go.mod is created fresh, but we still check for compatibility
# This is informational - dependencies will be resolved correctly by go mod tidy
if grep -q "k8s.io" go.mod; then
    # Check if OTE/origin pulled in compatible k8s.io versions
    if grep "k8s.io" go.mod | grep -q "v0.30\|v0.31\|v0.32\|v0.33\|v0.34\|v0.35"; then
        echo "⚠️  Note: k8s.io dependencies are at v0.30-v0.35 range"
        echo "   OTE framework uses OpenShift kubernetes fork (October 2025)"
        echo "   go mod tidy will resolve compatible versions automatically"
    fi
    echo "✅ k8s.io versions will be resolved by go mod tidy"
else
    echo "✅ No k8s.io dependencies detected yet"
fi

echo "Step 2: Running go mod tidy..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -ne 0 ]; then
    echo "❌ go mod tidy failed"
    exit 1
fi

echo "Step 3: Running go mod vendor..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod vendor

if [ $? -ne 0 ]; then
    echo "❌ go mod vendor failed"
    exit 1
fi

echo "Step 4: Building extension binary for verification..."
make build

if [ $? -eq 0 ]; then
    echo "✅ Extension binary built successfully"

    # Test binary execution
    ./bin/$EXTENSION_NAME-tests-ext --help > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ Binary executes correctly"
    fi
else
    echo "❌ Build failed"
    exit 1
fi

echo "========================================="
echo "✅ Phase 6 Complete"
echo "========================================="
```

### Phase 7: Dockerfile Integration

**🚨 MANDATORY PHASE - MUST BE EXECUTED 🚨**

**CRITICAL: This phase is REQUIRED. After Phase 6 completes, you MUST proceed to Phase 7. DO NOT skip this phase.**

```bash
echo "========================================="
echo "Phase 7: Dockerfile Integration"
echo "========================================="
echo "Using choice from Input 10: <dockerfile-choice>"
```

**This phase executes automated or manual Dockerfile integration based on the user's choice from Input 10.**

#### Step 1: Check Dockerfile Integration Choice and Selected Files

Use the `<dockerfile-choice>` and `<selected-dockerfiles>` variables collected in Phase 1, Input 10 and 10a.

- If `<dockerfile-choice>` = "manual", proceed to Step 2
- If `<dockerfile-choice>` = "automated" and `<selected-dockerfiles>` is empty, skip Phase 7 (no Dockerfiles selected)
- If `<dockerfile-choice>` = "automated" and `<selected-dockerfiles>` is not empty, proceed to Step 3

#### Step 2: Manual Integration - Provide Instructions

If user chose manual integration:

```markdown
========================================
Manual Dockerfile Integration Instructions
========================================

To integrate the OTE extension binary into your Docker image, add one builder stage and one COPY command.

**Note**: This works for both single-stage and multi-stage Dockerfiles.

## 1. Test Extension Builder Stage

Add this stage to build and compress the OTE extension binary.

**For multi-stage Dockerfiles**: Add after your existing builder stage.
**For single-stage Dockerfiles**: Add as the first stage before your existing FROM.

```
# Test extension builder stage
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21 AS test-extension-builder
RUN mkdir -p /go/src/github.com/openshift/<extension-name>
WORKDIR /go/src/github.com/openshift/<extension-name>
COPY . .

# For monorepo strategy:
RUN make tests-ext-build && \
    cd bin && \
    tar -czvf <extension-name>-test-extension.tar.gz <extension-name>-tests-ext && \
    rm -f <extension-name>-tests-ext

# For single-module strategy:
RUN cd tests-extension && \
    make build && \
    cd bin && \
    tar -czvf <extension-name>-test-extension.tar.gz <extension-name>-tests-ext && \
    rm -f <extension-name>-tests-ext
```

## 2. Copy to Final Image

Add this to your final runtime stage:

```
# Copy test extension binary
COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name>-test-extension.tar.gz /usr/bin/

# For single-module:
# COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/tests-extension/bin/<extension-name>-test-extension.tar.gz /usr/bin/
```

## Example: Multi-Stage Dockerfile

```
# Your existing builder
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.24-openshift-4.23 AS builder
WORKDIR /go/src/github.com/openshift/<extension-name>
COPY . .
RUN make build

# NEW: Test extension builder stage (builds and compresses)
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22 AS test-extension-builder
RUN mkdir -p /go/src/github.com/openshift/<extension-name>
WORKDIR /go/src/github.com/openshift/<extension-name>
COPY . .
RUN make tests-ext-build && \
    cd bin && \
    tar -czvf <extension-name>-test-extension.tar.gz <extension-name>-tests-ext && \
    rm -f <extension-name>-tests-ext

# Your final image
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9
COPY --from=builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name> /usr/bin/

# NEW: Copy test extension
COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name>-test-extension.tar.gz /usr/bin/
```

## Example: Single-Stage Dockerfile

```
# NEW: Test extension builder stage (added as first stage)
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22 AS test-extension-builder
RUN mkdir -p /go/src/github.com/openshift/<extension-name>
WORKDIR /go/src/github.com/openshift/<extension-name>
COPY . .
RUN make tests-ext-build && \
    cd bin && \
    tar -czvf <extension-name>-test-extension.tar.gz <extension-name>-tests-ext && \
    rm -f <extension-name>-tests-ext

# Your existing single-stage image
FROM registry.svc.ci.openshift.org/openshift/origin-v4.0:base-router
RUN INSTALL_PKGS="socat haproxy28 rsyslog" && \
    yum install -y $INSTALL_PKGS && \
    yum clean all
COPY images/router/haproxy/ /var/lib/haproxy/

# NEW: Copy test extension (added after COPY)
COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name>-test-extension.tar.gz /usr/bin/

USER 1001
EXPOSE 80 443
ENTRYPOINT ["/usr/bin/openshift-router"]
```

Replace <extension-name> with your actual extension name.

**Note:** The Makefile uses `-mod=vendor` by default, which means all dependencies are built from the vendored code. This eliminates the need for SSH authentication or network access during Docker builds.

========================================
```

Exit Phase 7 after providing instructions.

#### Step 3: Automated Integration - Update Selected Dockerfiles

If user chose automated integration, use the `<selected-dockerfiles>` from Phase 1, Input 10a:

```bash
echo "========================================="
echo "Phase 7: Dockerfile Integration (Automated)"
echo "========================================="

# Use the Dockerfiles selected in Phase 1
SELECTED_DOCKERFILES="<selected-dockerfiles>"

echo "Updating selected Dockerfiles: $SELECTED_DOCKERFILES"
echo ""
```

Convert the stored selection to an array for processing:

```bash
# Convert space-separated list to array
SELECTED_DOCKERFILES_ARRAY=($SELECTED_DOCKERFILES)

if [ ${#SELECTED_DOCKERFILES_ARRAY[@]} -eq 0 ]; then
    echo "No Dockerfiles selected for update"
    exit 0
fi
```

#### Step 4: Update Each Selected Dockerfile

For each selected Dockerfile:

```bash
for DOCKERFILE in "${SELECTED_DOCKERFILES_ARRAY[@]}"; do
    echo ""
    echo "Updating $DOCKERFILE..."

    # Create backup
    cp "$DOCKERFILE" "${DOCKERFILE}.pre-ote-migration"
    echo "✅ Created backup: ${DOCKERFILE}.pre-ote-migration"

    # Determine builder image for test-extension-builder stage
    # Strategy: Use existing builder image if found, otherwise derive from go.mod
    BUILDER_IMAGE=$(grep "^FROM.*AS builder" "$DOCKERFILE" | head -1 | awk '{print $2}')

    if [ -z "$BUILDER_IMAGE" ]; then
        # No named builder stage found - need to select appropriate Go builder image
        # Extract Go version from root go.mod to match toolchain
        GO_VERSION=$(grep "^go " <working-dir>/go.mod | awk '{print $2}' | cut -d. -f1,2)

        if [ -z "$GO_VERSION" ]; then
            GO_VERSION="1.22"
            echo "⚠️  Could not detect Go version from go.mod, defaulting to $GO_VERSION"
        fi

        # Map Go version to available OpenShift builder image
        case "$GO_VERSION" in
            1.25)
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22"
                echo "ℹ️  No builder stage found, using Go builder: $BUILDER_IMAGE"
                ;;
            1.24)
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.24-openshift-4.22"
                echo "ℹ️  No builder stage found, using Go builder: $BUILDER_IMAGE"
                ;;
            1.23)
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.23-openshift-4.20"
                echo "ℹ️  No builder stage found, using Go builder: $BUILDER_IMAGE"
                ;;
            1.22)
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.22-openshift-4.19"
                echo "ℹ️  No builder stage found, using Go builder: $BUILDER_IMAGE"
                ;;
            1.21)
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21-openshift-4.19"
                echo "ℹ️  No builder stage found, using Go builder: $BUILDER_IMAGE"
                ;;
            *)
                # Default to Go 1.22 for older or unknown versions
                BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.22-openshift-4.19"
                echo "⚠️  Unknown Go version $GO_VERSION, defaulting to Go 1.22 builder"
                ;;
        esac
    else
        echo "✅ Using existing builder image: $BUILDER_IMAGE"
    fi

    # Check if OTE stage already exists
    if grep -q "test-extension-builder" "$DOCKERFILE"; then
        echo "⚠️  test-extension-builder stage already exists, skipping"
        continue
    fi

    # Create test-extension-builder stage (builds and compresses)
    # Uses -mod=vendor by default (no SSH needed)
    TEST_BUILDER_STAGE="
# Test extension builder stage (added by ote-migration)
FROM $BUILDER_IMAGE AS test-extension-builder
RUN mkdir -p /go/src/github.com/openshift/$EXTENSION_NAME
WORKDIR /go/src/github.com/openshift/$EXTENSION_NAME
COPY . .
"

    # Add build and compress commands based on strategy
    if [ "$STRUCTURE_STRATEGY" = "monorepo" ]; then
        TEST_BUILDER_STAGE+="RUN make tests-ext-build && \\
    cd bin && \\
    tar -czvf $EXTENSION_NAME-test-extension.tar.gz $EXTENSION_NAME-tests-ext && \\
    rm -f $EXTENSION_NAME-tests-ext
"
    else
        TEST_BUILDER_STAGE+="RUN cd tests-extension && \\
    make build && \\
    cd bin && \\
    tar -czvf $EXTENSION_NAME-test-extension.tar.gz $EXTENSION_NAME-tests-ext && \\
    rm -f $EXTENSION_NAME-tests-ext
"
    fi

    # Detect Dockerfile type and find insertion point
    BUILDER_LINE=$(grep -n "^FROM.*AS builder" "$DOCKERFILE" | head -1 | cut -d: -f1)
    FIRST_FROM_LINE=$(grep -n "^FROM" "$DOCKERFILE" | head -1 | cut -d: -f1)

    if [ -n "$BUILDER_LINE" ]; then
        # Multi-stage Dockerfile with existing builder stage
        echo "Detected multi-stage Dockerfile with builder stage"

        # Find end of builder stage (next FROM line)
        NEXT_FROM_LINE=$(tail -n +$((BUILDER_LINE + 1)) "$DOCKERFILE" | grep -n "^FROM" | head -1 | cut -d: -f1)

        if [ -n "$NEXT_FROM_LINE" ]; then
            INSERT_LINE=$((BUILDER_LINE + NEXT_FROM_LINE))

            # Insert test-extension-builder stage after builder stage
            {
                head -n $((INSERT_LINE - 1)) "$DOCKERFILE"
                echo "$TEST_BUILDER_STAGE"
                tail -n +$INSERT_LINE "$DOCKERFILE"
            } > "${DOCKERFILE}.tmp"

            mv "${DOCKERFILE}.tmp" "$DOCKERFILE"
            echo "✅ Added test-extension-builder stage after existing builder stage"
        else
            echo "❌ Failed to find end of builder stage"
            continue
        fi
    elif [ -n "$FIRST_FROM_LINE" ]; then
        # Single-stage or multi-stage without named builder
        echo "Detected single-stage or multi-stage Dockerfile without named builder"

        # Insert test-extension-builder stage before first FROM (as first stage)
        {
            head -n $((FIRST_FROM_LINE - 1)) "$DOCKERFILE"
            echo "$TEST_BUILDER_STAGE"
            echo ""
            tail -n +$FIRST_FROM_LINE "$DOCKERFILE"
        } > "${DOCKERFILE}.tmp"

        mv "${DOCKERFILE}.tmp" "$DOCKERFILE"
        echo "✅ Added test-extension-builder stage as first stage"
    else
        echo "❌ No FROM line found in Dockerfile, skipping"
        continue
    fi

    # Add COPY command to final stage
    FINAL_FROM_LINE=$(grep -n "^FROM" "$DOCKERFILE" | tail -1 | cut -d: -f1)

    if [ -n "$FINAL_FROM_LINE" ]; then
        # Determine COPY path based on strategy
        if [ "$STRUCTURE_STRATEGY" = "monorepo" ]; then
            COPY_PATH="/go/src/github.com/openshift/$EXTENSION_NAME/bin/$EXTENSION_NAME-test-extension.tar.gz"
        else
            COPY_PATH="/go/src/github.com/openshift/$EXTENSION_NAME/tests-extension/bin/$EXTENSION_NAME-test-extension.tar.gz"
        fi

        COPY_CMD="
# Copy test extension binary (added by ote-migration)
COPY --from=test-extension-builder $COPY_PATH /usr/bin/"

        # Insert COPY command after final FROM line
        {
            head -n $FINAL_FROM_LINE "$DOCKERFILE"
            echo "$COPY_CMD"
            tail -n +$((FINAL_FROM_LINE + 1)) "$DOCKERFILE"
        } > "${DOCKERFILE}.tmp"

        mv "${DOCKERFILE}.tmp" "$DOCKERFILE"
        echo "✅ Added COPY command to final stage"
    fi

    echo "✅ Updated $DOCKERFILE"
done

echo ""
echo "========================================="
echo "Dockerfile Integration Complete"
echo "========================================="
echo "Updated Dockerfiles:"
for DF in "${SELECTED_DOCKERFILES_ARRAY[@]}"; do
    echo "  - $DF"
    echo "    Backup: ${DF}.pre-ote-migration"
done
echo ""
```

### Phase 8: Final Summary and Next Steps

Generate comprehensive summary based on strategy used.

**For Monorepo:**

```markdown
========================================
🎉 OTE Migration Complete!
========================================

## Summary

Successfully migrated **<extension-name>** to OTE framework using **monorepo strategy** with single module approach.

## Created Structure

Directory tree:

    <working-dir>/
    ├── bin/
    │   └── <extension-name>-tests-ext
    ├── cmd/
    │   └── extension/
    │       └── main.go                    # OTE entry point (at root)
    ├── test/
    │   └── e2e/
    │       ├── *_test.go                  # Migrated test files
    │       └── testdata/
    │           ├── bindata.go
    │           └── fixtures.go
    ├── vendor/                            # Vendored at ROOT
    ├── bindata.mk                         # Bindata generation (at root)
    ├── go.mod                             # Single module with all dependencies
    ├── go.sum                             # Single go.sum
    ├── Makefile                           # Updated with OTE targets
    └── Dockerfile                         # Updated (if automated)

## Key Features

1. **CMD Location**: `cmd/extension/main.go` (at root, not under test/)
2. **Single Module**: All dependencies (component + tests) in root go.mod
3. **No Sig Filtering**: All tests included without filtering
4. **Annotations**:
   - [OTP] added to all Describe blocks at beginning
   - [Level0] added to test names with -LEVEL0- suffix only
5. **Vendored at Root**: Only `vendor/` at repository root
6. **Dockerfile Integration**: Automated Docker image integration

## Next Steps

### 1. Verify Build

```
# Build extension binary
make extension

# Verify binary exists
ls -lh bin/<extension-name>-tests-ext
```

### 2. List Tests

```
# List all migrated tests
./bin/<extension-name>-tests-ext list

# Count total tests
./bin/<extension-name>-tests-ext list | wc -l

# Count Level0 tests
./bin/<extension-name>-tests-ext list | grep -c "\[Level0\]"
```

### 3. Run Tests

```
# Run all tests
./bin/<extension-name>-tests-ext run

# Run specific test
./bin/<extension-name>-tests-ext run --grep "test-name-pattern"

# Run Level0 tests only
./bin/<extension-name>-tests-ext run --grep "\[Level0\]"
```

### 4. Build Docker Image

```
# Build image
podman build -t <component>:test -f <path-to-dockerfile> .
# Or for Docker:
# docker build -t <component>:test -f <path-to-dockerfile> .

# Verify test extension in image (override ENTRYPOINT to run ls)
podman run --rm --entrypoint ls <component>:test -lh /usr/bin/*-test-extension.tar.gz
# Or for Docker:
# docker run --rm --entrypoint ls <component>:test -lh /usr/bin/*-test-extension.tar.gz
```

### 5. Verify Test Annotations

```
# Check [OTP] annotations
grep -r "\[OTP\]" test/e2e/*_test.go

# Check [Level0] annotations
grep -r "\[Level0\]" test/e2e/*_test.go

# Verify no -LEVEL0- suffixes remain
grep -r "\-LEVEL0\-" test/e2e/*_test.go || echo "✅ All -LEVEL0- removed"
```

## Files Created/Modified

- ✅ `cmd/extension/main.go` - Created
- ✅ `test/e2e/testdata/fixtures.go` - Created
- ✅ `test/e2e/testdata/bindata.go` - Created (generated, can be in .gitignore)
- ✅ `bindata.mk` - Created (at repository root)
- ✅ `test/e2e/*_test.go` - Modified (annotations, imports)
- ✅ `go.mod` - Updated (all dependencies + replace directives)
- ✅ `go.sum` - Updated
- ✅ `vendor/` - Created at root
- ✅ `Makefile` - Updated (tests-ext-build target)
- ✅ `Dockerfile` - Updated (if automated integration)

## Files to Commit (IMPORTANT!)

Before creating a PR, ensure these files are committed to git:

**Required for reproducible builds:**
- ✅ `go.mod` - Single module with all dependencies
- ✅ `go.sum` - Single go.sum for reproducible builds
- ✅ `cmd/extension/main.go` - OTE entry point
- ✅ `test/e2e/testdata/fixtures.go` - Testdata helper functions
- ✅ `bindata.mk` - Bindata generation makefile (at repository root)
- ✅ `test/e2e/*_test.go` - Migrated test files
- ✅ `Makefile` - Updated with OTE targets

**Can be in .gitignore:**
- ⚠️ `test/e2e/testdata/bindata.go` - Generated file (regenerated during build)
- ⚠️ `bin/<extension-name>-tests-ext` - Binary (build artifact)
- ⚠️ `vendor/` - Optional (some repos commit, others don't)

**Why go.sum is critical:**

Without committed go.sum, Docker builds will:
- ❌ Be slower (must download all modules and generate go.sum)
- ❌ Be less reproducible (module versions can drift)
- ❌ Fail on network issues or GOSUMDB problems
- ❌ Potentially use different dependency versions

With committed go.sum, Docker builds will:
- ✅ Be faster (use checksums from go.sum)
- ✅ Be reproducible (exact same dependencies every time)
- ✅ Work reliably in CI/CD environments
- ✅ Ensure consistent behavior across builds

**Verify file is tracked:**

```
# Check if go.sum is tracked
git status go.sum

# If untracked, add it:
git add go.mod go.sum
```

## Troubleshooting

If you encounter issues, see the troubleshooting guide below.

========================================
Migration completed successfully! 🎉
========================================
```

**For Single-Module:**

```markdown
========================================
🎉 OTE Migration Complete!
========================================

## Summary

Successfully migrated **<extension-name>** to OTE framework using **single-module strategy**.

## Created Structure

Directory tree:

    <working-dir>/
    └── tests-extension/
        ├── cmd/
        │   └── main.go                    # OTE entry point
        ├── bin/
        │   └── <extension-name>-tests-ext
        ├── test/
        │   └── e2e/
        │       ├── *_test.go              # Migrated tests
        │       ├── testdata/
        │       │   ├── bindata.go
        │       │   └── fixtures.go
        │       └── bindata.mk
        ├── vendor/                        # Vendored dependencies
        ├── go.mod
        ├── go.sum
        └── Makefile

## Next Steps

### 1. Build Extension

```
cd tests-extension
make build
```

### 2. List Tests

```
./bin/<extension-name>-tests-ext list
```

### 3. Run Tests

```
./bin/<extension-name>-tests-ext run
```

## Files Created

- ✅ `tests-extension/cmd/main.go`
- ✅ `tests-extension/go.mod`
- ✅ `tests-extension/vendor/`
- ✅ `tests-extension/test/e2e/*_test.go`
- ✅ `tests-extension/test/e2e/testdata/fixtures.go`
- ✅ `tests-extension/Makefile`

========================================
Migration completed successfully! 🎉
========================================
```

## Error Handling

Throughout the workflow:

1. **Validate inputs** before proceeding to next phase
2. **Create backups** before modifying files (Phase 5)
3. **Rollback on failure** in atomic phases (Phase 5)
4. **Provide clear error messages** with recovery steps

## Troubleshooting

This section provides solutions to common issues encountered during OTE migration based on real-world experience.

### Ginkgo Version Conflicts

**Symptom:**
```text
undefined: ginkgo.NewWriter
spec.Labels undefined (type types.TestSpec has no field or method Labels)
```

**Root Cause:**
Test module uses old Ginkgo version from OTP (August 2024), but OTE framework requires newer version (December 2024).

**Solution:**
The December 2024 Ginkgo fork is backward compatible with August 2024 code. Always use OTE's Ginkgo version:

```bash
cd test/e2e  # or test/e2e/<test-dir-name>

# Get OTE's Ginkgo version (December 2024)
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@v2.6.1-0.20241205171354-8006f302fd12"

# Update root go.mod replace directive
cd ../..  # or ../../.. for subdirectory mode
grep -q "github.com/onsi/ginkgo/v2 =>" go.mod || echo "replace github.com/onsi/ginkgo/v2 => github.com/openshift/onsi-ginkgo/v2 v2.6.1-0.20241205171354-8006f302fd12" >> go.mod

go mod tidy
go mod vendor
```

**Why this works:**
OTE's December 2024 fork is backward compatible with OTP's August 2024 code. Using OTE's version everywhere prevents API incompatibilities.

### k8s.io Version Mismatches

**Symptom:**
```text
k8s.io/cri-client/pkg/remote_image.go:75:39: undefined: otelgrpc.UnaryClientInterceptor
```

**Root Cause:**
Root module uses old k8s.io/kubernetes replace directives (October 2024), but test module needs newer versions from OTP (October 2025).

**Solution:**
Sync k8s.io replace directives from test module to root:

```bash
# Extract k8s.io replace directives from test module
cd test/e2e  # or test/e2e/<test-dir-name>
grep "k8s.io/" go.mod | grep "=>" > /tmp/k8s_replaces.txt

# Apply to root go.mod
cd ../..  # or ../../.. for subdirectory mode

while IFS= read -r replace_line; do
    PACKAGE=$(echo "$replace_line" | awk '{print $1}')
    # Remove old version if exists
    sed -i "/^[[:space:]]*$PACKAGE /d" go.mod
    # Add new version
    sed -i "/^replace (/a\\    $replace_line" go.mod
done < /tmp/k8s_replaces.txt

go mod tidy
go mod vendor
```

**Why this works:**
OTP's k8s.io versions (October 2025) are proven stable. The OTE Ginkgo fork (December 2024) is compatible with these versions.

### kube-openapi yaml Type Errors

**Symptom:**
```text
k8s.io/kube-openapi/pkg/util/proto/document_v3.go:291:31: cannot use s.GetDefault().ToRawInfo() (value of type *"go.yaml.in/yaml/v3".Node) as *"gopkg.in/yaml.v3".Node value in argument to parseV3Interface
```

**Root Cause:**
Old kube-openapi pin from February 2024 conflicts with natural version resolution.

**Solution:**
Remove old kube-openapi pin to allow natural version resolution:

```bash
cd <working-dir>

# Remove old kube-openapi pin
sed -i '/k8s.io\/kube-openapi => k8s.io\/kube-openapi v0.0.0-2024/d' go.mod

# Clean and rebuild
rm -rf vendor/
go mod tidy
go mod vendor
make clean-extension
make extension
```

**Why this works:**
Removing the old pin allows Go to resolve the correct kube-openapi version naturally based on k8s.io dependencies.

### Test Execution Fails: Unable to Load Kubeconfig

**Symptom:**
```text
unable to load in-cluster configuration, KUBERNETES_SERVICE_HOST and KUBERNETES_SERVICE_PORT must be defined
[FAILED] in [BeforeEach] - framework.go:222
```

**Root Cause:**
Removing `util.InitStandardFlags()` prevents the test framework from registering kubeconfig flags. Tests fail even when KUBECONFIG is set. However, the kubernetes e2e framework import is NOT needed and should be avoided to reduce dependencies.

**Solution:**
Keep util.InitStandardFlags() and use compat_otp.InitTest() in BeforeAll:

```go
// CORRECT main.go setup:
import (
    "k8s.io/component-base/logs"
    "github.com/openshift/origin/test/extended/util"
    compat_otp "github.com/openshift/origin/test/extended/util/compat_otp"
    framework "k8s.io/kubernetes/test/e2e/framework"
)

func main() {
    // Initialize test framework flags (required for kubeconfig, provider, etc.)
    util.InitStandardFlags()
    framework.AfterReadingAllFlags(&framework.TestContext)

    logs.InitLogs()
    defer logs.FlushLogs()

    // ... build and filter specs ...

    // Initialize test framework before all tests
    componentSpecs.AddBeforeAll(func() {
        if err := compat_otp.InitTest(false); err != nil {
            panic(err)
        }
    })

    // ... rest of extension setup ...
}
```

**What to keep:**
- ✅ `util.InitStandardFlags()` - Registers kubeconfig, provider, and other test flags
- ✅ `framework.AfterReadingAllFlags(&framework.TestContext)` - Initializes framework context (REQUIRED)
- ✅ `logs.InitLogs()` - Initialize logging
- ✅ `compat_otp.InitTest(false)` in BeforeAll - Sets up test framework context
- ✅ `e2e "k8s.io/kubernetes/test/e2e/framework"` import - Keep if tests use `e2e.Logf()` or `e2e.Failf()`

**What to remove:**
- ❌ `util.WithCleanup()` wrapper - OTE handles cleanup automatically

**Why this works:**
- `util.InitStandardFlags()` registers framework flags so KUBECONFIG is recognized
- `framework.AfterReadingAllFlags(&framework.TestContext)` initializes the framework context, preventing nil pointer dereference in framework.BeforeEach
- `compat_otp.InitTest()` in BeforeAll sets up the framework context when tests start
- OTE framework handles cleanup automatically via its test lifecycle
- Tests can now connect to the cluster using kubeconfig

### structured-merge-diff v4/v6 Incompatibility (Vendor Mode)

**Symptom:**
```text
100+ errors with -mod=vendor:
vendor/k8s.io/apimachinery/pkg/util/managedfields/internal/fieldmanager.go:26:2: imported and not used: "sigs.k8s.io/structured-merge-diff/v4/fieldpath"
```

**Root Cause:**
Vendor directory contains both v4 and v6 of structured-merge-diff, causing conflicts. This is a specific symptom of vendor directory being out of sync with go.mod.

**Solution:**
See the "Vendor Directory Out of Sync" section below for the complete solution and explanation.

### Build Failures (General)

```bash
# Check go.mod in test module
cd test/e2e
go mod verify

# Rebuild vendor at root
cd ../..
rm -rf vendor/
go mod vendor

# Clean and rebuild
make clean-extension
make extension
```

### Import Errors

```bash
# Check testdata imports
grep -r "testdata.FixturePath" test/e2e/

# Verify import paths
grep -r "import" test/e2e/*.go | grep testdata
```

### Annotation Issues

```bash
# Check for missing [OTP]
grep -L "\[OTP\]" test/e2e/*_test.go

# Check for remaining -LEVEL0-
grep -r "\-LEVEL0\-" test/e2e/

# Re-run annotation script if needed
python3 /tmp/annotate_tests.py test/e2e/
```

### Docker Build Failures

```bash
# Check Dockerfile stages
docker build --target test-extension-builder .

# Verify binary exists before compression
docker run --rm <image> ls -la bin/

# Check Makefile target
make tests-ext-build
```

### Vendor Directory Out of Sync

**Symptom:**
```text
# Build fails with import errors or version conflicts
vendor/k8s.io/apimachinery/pkg/util/managedfields/internal/fieldmanager.go:26:2: imported and not used
```

**Cause:** The vendor directory doesn't match the current go.mod (happens after updating k8s.io versions or replace directives).

**Solution:**

```bash
# Regenerate vendor directory to match go.mod
rm -rf vendor/
go mod tidy
go mod vendor

# Verify vendor is clean
go mod verify

# Retry build
make clean-extension
make tests-ext-build

# If Docker build:
docker build -t <component>:test -f <dockerfile> .
```

**Why this works:**
The Makefile uses `-mod=vendor` by default, which builds from the vendored code. After updating go.mod, the vendor directory must be regenerated to contain the correct resolved dependencies. This ensures reproducible, offline builds without requiring network access during Docker builds.

### Testdata Fixtures Not Found at Runtime

**Symptom:**
```text
panic: failed to restore fixture router/haproxy.cfg: Asset not found
```

**Root Cause:**
Testdata files not copied from openshift-tests-private during Phase 3, or bindata.go not regenerated.

**Solution:**

```bash
# Check if testdata files exist (excluding generated files)
find test/e2e/testdata -type f ! -name "fixtures.go" ! -name "bindata.go"

# If empty, copy testdata from source
SOURCE_TESTDATA="<source-repo>/test/extended/testdata/<testdata-subfolder>"
cp -rv "$SOURCE_TESTDATA"/* test/e2e/testdata/

# Regenerate bindata.go
cd test/e2e
make -f bindata.mk update-bindata

# Rebuild extension
cd ../..
make clean-extension
make extension
```

**Why this works:**
bindata.go embeds all files from testdata/ directory. If testdata files weren't copied, bindata.go only contains fixtures.go, causing runtime panics when tests try to load fixtures via FixturePath().

## Summary

This skill provides complete automation for OTE migration with:

- **7-phase workflow** with clear separation of concerns
- **Atomic test migration** with backup and rollback
- **Automated Dockerfile integration** with manual fallback
- **Simplified annotation logic** - [OTP] at beginning, [Level0] in test names only
- **Vendor at root** (monorepo) - Only `vendor/` at repository root
- **No sig filtering** - all tests included
- **Comprehensive validation** at each phase

Follow each phase sequentially for successful migration. All phases include error handling and validation to ensure migration integrity.

