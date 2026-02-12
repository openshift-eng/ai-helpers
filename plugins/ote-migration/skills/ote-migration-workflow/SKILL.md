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

1. User Input Collection (10 inputs - includes Dockerfile integration choice)
2. Repository Setup (source and target)
3. Structure Creation (directories and files)
4. Code Generation (go.mod, main.go, Makefile, bindata.mk, fixtures.go)
5. Test Migration (automated with rollback on failure)
6. Dependency Resolution (go mod tidy + vendor + build verification)
7. **Dockerfile Integration (uses choice from Input 10)**
8. Final Summary and Next Steps

**DO NOT skip Phase 7. After Phase 6 completes, proceed immediately to Phase 7.**

**Key Design Principles:**
- **No sig filtering**: All tests included without filtering logic
- **CMD at root** (monorepo): `cmd/extension/main.go` (not under test/)
- **Simple annotations**: [OTP] at beginning of Describe, [Level0] at beginning of test name only
- **Vendor at root** (monorepo): Only `vendor/` at repository root, NOT in test module
- **No compress/copy targets**: Removed from root Makefile

## Migration Phases

### Phase 1: User Input Collection (10 inputs)

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
- **Test module**: `test/e2e/go.mod` or `test/e2e/<test-dir-name>/go.mod`
- **Vendor location**: `vendor/` at root ONLY (not in test module)

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

#### Input 5: Test Directory Name (conditional - monorepo only)

**Skip this input if single-module strategy**

For monorepo strategy, check if test/e2e exists:

```bash
cd "$WORKING_DIR"

if [ -d "test/e2e" ]; then
    echo "⚠️  test/e2e already exists"
    TEST_DIR_EXISTS=true
else
    TEST_DIR_EXISTS=false
fi
```

**If test/e2e exists:**
Ask: "The directory 'test/e2e' already exists. Please specify a subdirectory name (default: 'extension'):"
- Default: "extension"
- Store in: `<test-dir-name>` = subdirectory name (e.g., "extension")

**If test/e2e doesn't exist:**
- Use default: `test/e2e`
- Store in: `<test-dir-name>` = "e2e"

#### Input 6: Local Source Repository (Optional)

Ask: "Do you have a local clone of openshift-tests-private? If yes, provide the path (or press Enter to clone):"

**Store in variable:** `<local-source-path>` (empty if user wants to clone)

#### Input 7: Update Local Source Repository (if local source provided)

If local source provided:
Ask: "Do you want to update the local source repository? (git fetch && git pull) [Y/n]:"

**Store in variable:** `<update-source>` (value: "yes" or "no")

#### Input 8: Source Test Subfolder

Ask: "What is the test subfolder name under test/extended/?"
- Example: "networking", "router", "storage"

**Store in variable:** `<test-subfolder>`

#### Input 9: Source Testdata Subfolder (Optional)

**IMPORTANT**: This determines which testdata fixtures are copied from the source OTE repository.
The testdata files are embedded into bindata.go and accessed via FixturePath() calls in tests.

Ask: "What is the testdata subfolder name under test/extended/testdata/?"

**Options:**
- Press **Enter** to use the same value as the test subfolder (Input 8)
- Enter a **subfolder name** (e.g., "router", "networking") if different from test subfolder
- Enter **"none"** if no testdata fixtures exist for these tests

**Default**: Same as Input 8 (recommended for most cases)

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

#### Input 10: Dockerfile Integration Choice

Ask: "Do you want to update Dockerfiles automatically, or do it manually?"

**Options:**
1. **Automated** - Let the plugin update your Dockerfiles automatically (with backup)
2. **Manual** - Get instructions to update Dockerfiles yourself

**Store in variable:** `<dockerfile-choice>` (value: "automated" or "manual")

#### Input 10a: Select Dockerfiles to Update (conditional - only if automated)

**This input is ONLY asked if user chose "automated" in Input 10.**

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
```
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

```
========================================
Migration Configuration Summary
========================================
Strategy:              <structure-strategy>
Workspace:             <working-dir>
Target Repository:     <target-repo-path>
Update Target Repo:    <update-target or "cloned from URL" or "N/A">
Extension Name:        <extension-name>
Test Directory:        <test-dir-name>
Source Repository:     <local-source-path or "will clone">
Update Source Repo:    <update-source or "will clone" or "N/A">
Test Subfolder:        <test-subfolder>
Testdata Subfolder:    <testdata-subfolder>
Dockerfile Integration: <dockerfile-choice>
Selected Dockerfiles:  <selected-dockerfiles or "manual integration" or "none">
========================================
```

**Example output (local target, automated Dockerfile):**
```
========================================
Migration Configuration Summary
========================================
Strategy:              monorepo
Workspace:             /home/user/repos
Target Repository:     /home/user/repos/router
Update Target Repo:    yes
Extension Name:        router
Test Directory:        e2e
Source Repository:     /home/user/openshift-tests-private
Update Source Repo:    yes
Test Subfolder:        router
Testdata Subfolder:    router
Dockerfile Integration: automated
Selected Dockerfiles:  ./Dockerfile, ./Dockerfile.rhel8
========================================
```

**Example output (cloned target, manual Dockerfile):**
```
========================================
Migration Configuration Summary
========================================
Strategy:              single-module
Workspace:             /tmp/migration
Target Repository:     /tmp/migration/router
Update Target Repo:    cloned from URL
Extension Name:        router
Test Directory:        e2e
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

# Auto-detect structure variant
if [ -d "test/e2e" ]; then
    TEST_E2E_EXISTS=true
    echo "✅ Variant B (Subdirectory mode)"
else
    TEST_E2E_EXISTS=false
    echo "✅ Variant A (Direct mode)"
fi

# Set directory paths
if [ "$TEST_E2E_EXISTS" = true ]; then
    TEST_CODE_DIR="test/e2e/<test-dir-name>"
    TESTDATA_DIR="test/e2e/<test-dir-name>/testdata"
    TEST_MODULE_DIR="test/e2e/<test-dir-name>"
else
    TEST_CODE_DIR="test/e2e"
    TESTDATA_DIR="test/e2e/testdata"
    TEST_MODULE_DIR="test/e2e"
fi

# Create directories
# IMPORTANT: cmd is at root level (cmd/extension/), NOT under test/
mkdir -p cmd/extension
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

# Extract Go version from root
GO_VERSION=$(grep '^go ' go.mod | awk '{print $2}')

cd "$TEST_MODULE_DIR"

# Initialize test module
if [ "$TEST_E2E_EXISTS" = true ]; then
    ROOT_MODULE=$(grep '^module ' ../../../go.mod | awk '{print $2}')
    go mod init "$ROOT_MODULE/$TEST_MODULE_DIR"
else
    ROOT_MODULE=$(grep '^module ' ../../go.mod | awk '{print $2}')
    go mod init "$ROOT_MODULE/test/e2e"
fi

# Set Go version
sed -i "s/^go .*/go $GO_VERSION/" go.mod

# Add dependencies
OTE_LATEST=$(git ls-remote https://github.com/openshift-eng/openshift-tests-extension.git refs/heads/main | awk '{print $1}')
OTE_SHORT="${OTE_LATEST:0:12}"

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

# Copy replace directives from openshift-tests-private
SOURCE_PATH=$([ "$TEST_E2E_EXISTS" = true ] && echo "../../../$SOURCE_REPO" || echo "../../$SOURCE_REPO")

grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
    grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

echo "" >> go.mod
echo "replace (" >> go.mod
cat /tmp/replace_directives.txt >> go.mod
echo ")" >> go.mod
rm -f /tmp/replace_directives.txt

# Step 4b: Update Ginkgo to latest OpenShift fork (prevents build failures from stale August 2024 version)
echo "Updating Ginkgo to latest from OpenShift fork..."
GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')
GINKGO_SHORT="${GINKGO_LATEST:0:12}"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@$GINKGO_SHORT"
echo "✅ Ginkgo updated to latest OpenShift fork version"

# Add replace directive for root module
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}' | sed "s|/$TEST_MODULE_DIR||")

if [ "$TEST_E2E_EXISTS" = true ]; then
    echo "" >> go.mod
    echo "replace $MODULE_NAME => ../../.." >> go.mod
else
    echo "" >> go.mod
    echo "replace $MODULE_NAME => ../.." >> go.mod
fi

# Generate minimal go.sum (defer full tidy to Phase 6)
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download || echo "⚠️  Some downloads failed - will retry in Phase 6"

# Return to root
cd $([ "$TEST_E2E_EXISTS" = true ] && echo "../../.." || echo "../..")

# Update root go.mod
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

if ! grep -q "replace.*$MODULE_NAME/$TEST_MODULE_DIR" go.mod; then
    if grep -q "^replace (" go.mod; then
        sed -i "/^replace (/a\\    $MODULE_NAME/$TEST_MODULE_DIR => ./$TEST_MODULE_DIR" go.mod
    else
        echo "" >> go.mod
        echo "replace $MODULE_NAME/$TEST_MODULE_DIR => ./$TEST_MODULE_DIR" >> go.mod
    fi
fi

echo "✅ Monorepo go.mod setup complete"
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

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift-eng/openshift-tests-extension@$OTE_SHORT"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/origin@main"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/ginkgo/v2@latest
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/onsi/gomega@latest

# Copy replace directives
SOURCE_PATH="../$SOURCE_REPO"

grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
    grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

echo "" >> go.mod
echo "replace (" >> go.mod
cat /tmp/replace_directives.txt >> go.mod
echo ")" >> go.mod
rm -f /tmp/replace_directives.txt

# Step 4b: Update Ginkgo to latest OpenShift fork (prevents build failures from stale August 2024 version)
echo "Updating Ginkgo to latest from OpenShift fork..."
GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')
GINKGO_SHORT="${GINKGO_LATEST:0:12}"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@$GINKGO_SHORT"
echo "✅ Ginkgo updated to latest OpenShift fork version"

# Generate minimal go.sum
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download || echo "⚠️  Will retry in Phase 6"

cd ..
```

#### Step 2: Generate Extension Binary (main.go)

**For Monorepo Strategy:**

**IMPORTANT:**
- CMD Location: `cmd/extension/main.go` (at repository root, NOT under test/)
- NO sig filtering logic

```bash
cd <working-dir>
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

# Determine test import path
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    TEST_IMPORT="$MODULE_NAME/$TEST_MODULE_DIR"
else
    TEST_IMPORT="$MODULE_NAME/test/e2e"
fi

# Create main.go at cmd/extension/main.go
cat > cmd/extension/main.go << 'EOF'
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

    "github.com/openshift/origin/test/extended/util"
    "k8s.io/kubernetes/test/e2e/framework"

    // Import testdata package
    testdata "<TEST_IMPORT>/testdata"

    // Import test packages
    _ "<TEST_IMPORT>"
)

func main() {
    util.InitStandardFlags()
    if err := util.InitTest(false); err != nil {
        panic(fmt.Sprintf("couldn't initialize test framework: %+v", err.Error()))
    }
    framework.AfterReadingAllFlags(&framework.TestContext)

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs from Ginkgo - NO SIG FILTERING
    specs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

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
        re := regexp.MustCompile(`\[platform:([a-z]+)\]`)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }
    })

    // Set lifecycle for all migrated tests to Informing
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        spec.Lifecycle = et.LifecycleInforming
    })

    // Wrap test execution with cleanup handler
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
EOF

# Replace placeholders
sed -i "s|<TEST_IMPORT>|$TEST_IMPORT|g" cmd/extension/main.go
sed -i "s|<extension-name>|$EXTENSION_NAME|g" cmd/extension/main.go
sed -i "s|<Extension Name>|${EXTENSION_NAME^}|g" cmd/extension/main.go

echo "✅ Created cmd/extension/main.go"
```

**For Single-Module Strategy:**

```bash
cd <working-dir>/tests-extension

cat > cmd/main.go << 'EOF'
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

    "github.com/openshift/origin/test/extended/util"
    "k8s.io/kubernetes/test/e2e/framework"

    _ "github.com/openshift/<extension-name>-tests-extension/test/e2e"
)

func main() {
    util.InitStandardFlags()
    if err := util.InitTest(false); err != nil {
        panic(fmt.Sprintf("couldn't initialize test framework: %+v", err.Error()))
    }
    framework.AfterReadingAllFlags(&framework.TestContext)

    registry := e.NewRegistry()
    ext := e.NewExtension("openshift", "payload", "<extension-name>")

    ext.AddSuite(e.Suite{
        Name:    "openshift/<extension-name>/tests",
        Parents: []string{"openshift/conformance/parallel"},
    })

    // Build test specs - NO SIG FILTERING
    specs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    if err != nil {
        panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
    }

    // Apply platform filters
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        for label := range spec.Labels {
            if strings.HasPrefix(label, "Platform:") {
                platformName := strings.TrimPrefix(label, "Platform:")
                spec.Include(et.PlatformEquals(platformName))
            }
        }
    })

    specs.Walk(func(spec *et.ExtensionTestSpec) {
        re := regexp.MustCompile(`\[platform:([a-z]+)\]`)
        if match := re.FindStringSubmatch(spec.Name); match != nil {
            platform := match[1]
            spec.Include(et.PlatformEquals(platform))
        }
    })

    // Set lifecycle to Informing
    specs.Walk(func(spec *et.ExtensionTestSpec) {
        spec.Lifecycle = et.LifecycleInforming
    })

    // Wrap test execution
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
EOF

sed -i "s|<extension-name>|$EXTENSION_NAME|g" cmd/main.go
sed -i "s|<Extension Name>|${EXTENSION_NAME^}|g" cmd/main.go
```

#### Step 3: Create bindata.mk

**For Monorepo:**

```bash
cd <working-dir>

# bindata.mk location: same level as testdata/
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    BINDATA_MK_PATH="$TEST_MODULE_DIR/bindata.mk"
else
    BINDATA_MK_PATH="test/e2e/bindata.mk"
fi

cat > "$BINDATA_MK_PATH" << 'EOF'
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
	git diff --exit-code $(BINDATA_OUT) || (echo "❌ Bindata is out of date" && exit 1)
	@echo "✅ Bindata is up to date"

.PHONY: bindata
bindata: update-bindata

.PHONY: clean-bindata
clean-bindata:
	@echo "Cleaning bindata..."
	@rm -f $(BINDATA_OUT)
EOF

echo "✅ Created bindata.mk at: $BINDATA_MK_PATH"
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
	@go install github.com/go-bindata/go-bindata/v3/go-bindata@latest

.PHONY: bindata
bindata: clean-bindata $(GO_BINDATA)
	@echo "Generating bindata..."
	@mkdir -p $(TESTDATA_PATH)
	$(GO_BINDATA) -nocompress -nometadata \
		-pkg testdata -o $(TESTDATA_PATH)/bindata.go -prefix "testdata" $(TESTDATA_PATH)/...
	@gofmt -s -w $(TESTDATA_PATH)/bindata.go

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

if [ ! -f "Makefile" ]; then
    echo "❌ ERROR: No root Makefile found"
    exit 1
fi

if grep -q "tests-ext-build" Makefile; then
    echo "⚠️  OTE targets already exist, skipping..."
else
    # Determine build command based on structure
    if [ "$TEST_DIR_EXISTS" = "true" ]; then
        # Subdirectory mode
        cat >> Makefile << EOF

# OTE test extension binary configuration
TESTS_EXT_DIR := $TEST_MODULE_DIR
TESTS_EXT_BINARY := bin/$EXTENSION_NAME-tests-ext

.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	cd \$(TESTS_EXT_DIR) && GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o ../../../\$(TESTS_EXT_BINARY) ../../cmd/extension
	@echo "✅ Extension binary built: \$(TESTS_EXT_BINARY)"

.PHONY: extension
extension: tests-ext-build

.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY)
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) -f bindata.mk clean-bindata 2>/dev/null || true
EOF
    else
        # Direct mode
        cat >> Makefile << EOF

# OTE test extension binary configuration
TESTS_EXT_DIR := test/e2e
TESTS_EXT_BINARY := bin/$EXTENSION_NAME-tests-ext

.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) -f bindata.mk update-bindata
	@mkdir -p bin
	cd \$(TESTS_EXT_DIR) && GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go build -o ../../\$(TESTS_EXT_BINARY) ../../cmd/extension
	@echo "✅ Extension binary built: \$(TESTS_EXT_BINARY)"

.PHONY: extension
extension: tests-ext-build

.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f \$(TESTS_EXT_BINARY)
	@cd \$(TESTS_EXT_DIR) && \$(MAKE) -f bindata.mk clean-bindata 2>/dev/null || true
EOF
    fi

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

if [ "$TEST_DIR_EXISTS" = "true" ]; then
    TESTDATA_IMPORT="$MODULE_NAME/$TEST_MODULE_DIR/testdata"
else
    TESTDATA_IMPORT="$MODULE_NAME/test/e2e/testdata"
fi

TEST_FILES=$(grep -rl "testdata\.FixturePath" "$TEST_CODE_DIR" --include="*_test.go" 2>/dev/null || true)

for file in $TEST_FILES; do
    if ! grep -q "\"$TESTDATA_IMPORT\"" "$file"; then
        if grep -q "^import (" "$file"; then
            sed -i "/^import (/a\\    \"$TESTDATA_IMPORT\"" "$file"
        else
            sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
        fi
    fi
done

echo "✅ Testdata imports added"
```

#### Step 3: Remove Old Imports

```bash
echo "Step 3: Removing old imports..."

TEST_FILES=$(find "$TEST_CODE_DIR" -name '*_test.go' -type f)

for file in $TEST_FILES; do
    # Comment out compat_otp import if not used
    if grep -q "compat_otp" "$file" && ! grep -q "compat_otp\." "$file"; then
        sed -i 's|^\(\s*\)"\(.*compat_otp\)"|// \1"\2" // Replaced|g' "$file"
    fi

    # Comment out exutil import if not used
    if grep -q "github.com/openshift/origin/test/extended/util\"" "$file" && ! grep -q "exutil\." "$file"; then
        sed -i 's|^\(\s*\)"\(github.com/openshift/origin/test/extended/util\)"|// \1"\2" // Replaced|g' "$file"
    fi
done

echo "✅ Old imports cleaned up"
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

**IMPORTANT: For monorepo, only vendor at ROOT level (not in test module)**

#### For Monorepo:

```bash
cd <working-dir>

echo "========================================="
echo "Phase 6: Dependency Resolution"
echo "========================================="

# Step 1: Tidy test module (NO vendor)
cd "$TEST_MODULE_DIR"
echo "Step 1: Running go mod tidy in test module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -ne 0 ]; then
    echo "❌ go mod tidy failed in test module"
    exit 1
fi
echo "✅ Test module dependencies resolved"

# Return to root
if [ "$TEST_DIR_EXISTS" = "true" ]; then
    cd ../../..
else
    cd ../..
fi

# Step 2: Sync replace directives to root
echo "Step 2: Syncing replace directives to root..."

TEST_REPLACES=$(grep -A 1000 "^replace (" "$TEST_MODULE_DIR/go.mod" | grep "=>" | grep -v "^)" || echo "")

if [ -n "$TEST_REPLACES" ]; then
    # Ensure root has replace block
    if ! grep -q "^replace (" go.mod; then
        echo "" >> go.mod
        echo "replace (" >> go.mod
        echo ")" >> go.mod
    fi

    UPDATED_COUNT=0
    while IFS= read -r replace_line; do
        PACKAGE=$(echo "$replace_line" | awk '{print $1}')
        if [ -z "$PACKAGE" ]; then
            continue
        fi

        # Skip root module replace directive
        if echo "$replace_line" | grep -q "=> \.\./\.\."; then
            continue
        fi

        # Update or add replace directive
        if grep -q "^[[:space:]]*$PACKAGE " go.mod; then
            sed -i "/^[[:space:]]*$PACKAGE /d" go.mod
            sed -i "/^replace (/a\\    $replace_line" go.mod
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
        else
            sed -i "/^replace (/a\\    $replace_line" go.mod
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
        fi
    done <<< "$TEST_REPLACES"

    echo "✅ Synced $UPDATED_COUNT replace directives to root"
fi

# Step 3: Add test module dependency to root
echo "Step 3: Adding test module dependency to root..."
ROOT_MODULE=$(grep "^module " go.mod | awk '{print $2}')

GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "$ROOT_MODULE/$TEST_MODULE_DIR"
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get github.com/openshift/origin/test/extended/util

# Step 4: Tidy root module
echo "Step 4: Running go mod tidy in root module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -ne 0 ]; then
    echo "❌ go mod tidy failed in root module"
    exit 1
fi
echo "✅ Root module dependencies resolved"

# Step 5: Vendor at ROOT only (NOT in test module)
echo "Step 5: Running go mod vendor in root module..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod vendor

if [ $? -ne 0 ]; then
    echo "❌ go mod vendor failed in root module"
    exit 1
fi
echo "✅ Root module dependencies vendored (vendor/ at root)"

# Step 6: Build verification
echo "Step 6: Building extension binary for verification..."
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

echo "Step 1: Running go mod tidy..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

if [ $? -ne 0 ]; then
    echo "❌ go mod tidy failed"
    exit 1
fi

echo "Step 2: Running go mod vendor..."
GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod vendor

if [ $? -ne 0 ]; then
    echo "❌ go mod vendor failed"
    exit 1
fi

echo "Step 3: Building extension binary for verification..."
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

```dockerfile
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

```dockerfile
# Copy test extension binary
COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name>-test-extension.tar.gz /usr/bin/

# For single-module:
# COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/tests-extension/bin/<extension-name>-test-extension.tar.gz /usr/bin/
```

## Example: Multi-Stage Dockerfile

```dockerfile
# Your existing builder
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21 AS builder
WORKDIR /go/src/github.com/openshift/<extension-name>
COPY . .
RUN make build

# NEW: Test extension builder stage (builds and compresses)
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21 AS test-extension-builder
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

```dockerfile
# NEW: Test extension builder stage (added as first stage)
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21 AS test-extension-builder
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

    # Extract existing builder image
    BUILDER_IMAGE=$(grep "^FROM.*AS builder" "$DOCKERFILE" | head -1 | awk '{print $2}')

    if [ -z "$BUILDER_IMAGE" ]; then
        BUILDER_IMAGE="registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.21"
        echo "⚠️  No builder image found, using default: $BUILDER_IMAGE"
    else
        echo "Using builder image: $BUILDER_IMAGE"
    fi

    # Check if OTE stage already exists
    if grep -q "test-extension-builder" "$DOCKERFILE"; then
        echo "⚠️  test-extension-builder stage already exists, skipping"
        continue
    fi

    # Create test-extension-builder stage (builds and compresses)
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

Successfully migrated **<extension-name>** to OTE framework using **monorepo strategy**.

## Created Structure

```
<working-dir>/
├── bin/
│   └── <extension-name>-tests-ext
├── cmd/
│   └── extension/
│       └── main.go                    # OTE entry point (at root)
├── test/
│   └── e2e/
│       ├── go.mod                     # Test module
│       ├── go.sum
│       ├── *_test.go                  # Migrated test files
│       ├── testdata/
│       │   ├── bindata.go
│       │   └── fixtures.go
│       └── bindata.mk
├── vendor/                            # Vendored at ROOT only
├── go.mod                             # Root module (updated)
├── Makefile                           # Updated with OTE targets
└── Dockerfile                         # Updated (if automated)
```

## Key Features

1. **CMD Location**: `cmd/extension/main.go` (at root, not under test/)
2. **No Sig Filtering**: All tests included without filtering
3. **Annotations**:
   - [OTP] added to all Describe blocks at beginning
   - [Level0] added to test names with -LEVEL0- suffix only
4. **Vendored at Root**: Only `vendor/` at repository root (not in test module)
5. **Dockerfile Integration**: Automated Docker image integration

## Next Steps

### 1. Verify Build

```bash
# Build extension binary
make extension

# Verify binary exists
ls -lh bin/<extension-name>-tests-ext
```

### 2. List Tests

```bash
# List all migrated tests
./bin/<extension-name>-tests-ext list

# Count total tests
./bin/<extension-name>-tests-ext list | wc -l

# Count Level0 tests
./bin/<extension-name>-tests-ext list | grep -c "\[Level0\]"
```

### 3. Run Tests

```bash
# Run all tests
./bin/<extension-name>-tests-ext run

# Run specific test
./bin/<extension-name>-tests-ext run --grep "test-name-pattern"

# Run Level0 tests only
./bin/<extension-name>-tests-ext run --grep "\[Level0\]"
```

### 4. Build Docker Image

```bash
# Build image
docker build -t <component>:test .

# Verify test extension in image
docker run --rm <component>:test ls -lh /usr/bin/*-test-extension.tar.gz
```

### 5. Verify Test Annotations

```bash
# Check [OTP] annotations
grep -r "\[OTP\]" test/e2e/*_test.go

# Check [Level0] annotations
grep -r "\[Level0\]" test/e2e/*_test.go

# Verify no -LEVEL0- suffixes remain
grep -r "\-LEVEL0\-" test/e2e/*_test.go || echo "✅ All -LEVEL0- removed"
```

## Files Created/Modified

- ✅ `cmd/extension/main.go` - Created
- ✅ `test/e2e/go.mod` - Created
- ✅ `test/e2e/testdata/fixtures.go` - Created
- ✅ `test/e2e/testdata/bindata.go` - Created
- ✅ `test/e2e/bindata.mk` - Created
- ✅ `test/e2e/*_test.go` - Modified (annotations, imports)
- ✅ `go.mod` - Updated (replace directives)
- ✅ `vendor/` - Created at root
- ✅ `Makefile` - Updated (tests-ext-build target)
- ✅ `Dockerfile` - Updated (if automated integration)

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

```
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
```

## Next Steps

### 1. Build Extension

```bash
cd tests-extension
make build
```

### 2. List Tests

```bash
./bin/<extension-name>-tests-ext list
```

### 3. Run Tests

```bash
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

### Build Failures

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

### Vendor Issues

```bash
# For monorepo: Clean and rebuild vendor at ROOT
rm -rf vendor/
go mod vendor

# Verify vendor
go mod verify
```

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
