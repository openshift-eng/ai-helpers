---
description: Automate OpenShift Tests Extension (OTE) migration for component repositories
argument-hint: ""
---

## Name
ote-migration:migrate

## Synopsis
```
/ote-migration:migrate
```

## Description
The `ote-migration:migrate` command automates the migration of component repositories to use the openshift-tests-extension (OTE) framework. It guides users through the entire migration process, from collecting configuration information to generating all necessary boilerplate code, copying test files, and setting up the build infrastructure.

## Implementation
The command implements an interactive 8-phase migration workflow:
1. **Cleanup** - Prepare the environment
2. **User Input Collection** - Gather all configuration (extension name, directory strategy, repository paths, test subfolders)
3. **Repository Setup** - Clone/update source (openshift-tests-private) and target repositories
4. **Structure Creation** - Create directory layout (supports both monorepo and single-module strategies)
5. **Code Generation** - Generate main.go, Makefile, go.mod, fixtures.go, and bindata configuration
6. **Test Migration** - Automatically replace FixturePath calls and update imports
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
6. Apply environment selectors and filters
7. Set up test suites and registrations

## Migration Workflow

### Phase 1: Cleanup

No files to delete in this phase.

### Phase 2: User Input Collection (up to 10 inputs, some conditional)

Collect all necessary information from the user before starting the migration.

**Note:** Source repository is always `git@github.com:openshift/openshift-tests-private.git`

#### Input 1: Extension Name

Ask: "What is the name of your extension?"
- Example: "sdn", "router", "storage", "cluster-network-operator"
- This will be used for the binary name and identifiers

#### Input 2: Directory Structure Strategy

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

#### Input 3: Working Directory

Ask: "What is the working directory path?"
- **If monorepo strategy**: This should be the root of the target component repository
- **If single-module strategy**: This is where we'll create the `tests-extension/` directory
- Options:
  - Provide an existing directory path
  - Provide a new directory path (we'll create it)
- Example: `/home/user/repos/sdn` (for monorepo) or `/home/user/workspace/sdn-migration` (for single-module)

#### Input 4: Validate Git Status (if existing directory)

If the working directory already exists:
- Check if it's a git repository
- If yes, run `git status` and verify it's clean
- If there are uncommitted changes, ask user to commit or stash them first
- If no, continue without git validation

#### Input 5: Local Source Repository (Optional)

Ask: "Do you have a local clone of openshift-tests-private? If yes, provide the path (or press Enter to clone it):"
- If provided: Use this existing local repository
- If empty: Will clone `git@github.com:openshift/openshift-tests-private.git`
- Example: `/home/user/repos/openshift-tests-private`

#### Input 6: Update Local Source Repository (if local source provided)

If a local source repository path was provided:
Ask: "Do you want to update the local source repository? (git fetch && git pull) [Y/n]:"
- Default: Yes
- If yes: Run `git fetch && git pull` in the local repo
- If no: Use current state

#### Input 7: Source Test Subfolder

Ask: "What is the test subfolder name under test/extended/?"
- Example: "networking", "router", "storage", "templates"
- This will be used as: `test/extended/<subfolder>/`
- Leave empty to use all of `test/extended/`

#### Input 8: Source Testdata Subfolder (Optional)

Ask: "What is the testdata subfolder name under test/extended/testdata/? (or press Enter to use same as test subfolder)"
- Default: Same as Input 7 (test subfolder)
- Example: "networking", "router", etc.
- This will be used as: `test/extended/testdata/<subfolder>/`
- Enter "none" if no testdata exists

#### Input 9: Local Target Repository (Optional - skip for monorepo)

**Skip this input if monorepo strategy** - the working directory IS the target repo.

**For single-module strategy only:**
Ask: "Do you have a local clone of the target repository? If yes, provide the path (or press Enter to clone from URL):"
- If provided: Use this existing local repository
  - Can be absolute path: `/home/user/repos/sdn`
  - Can be relative path: `../sdn`
  - Can be current directory: `.`
- If empty: Will ask for URL to clone (Input 10)
- After providing a path, you will be asked in Input 11 if you want to update it

#### Input 10: Target Repository URL (if no local target provided and single-module)

**Skip this input if monorepo strategy.**

**For single-module strategy only:**
If no local target repository was provided in Input 9:
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
- If yes: Run `cd <target-path> && git fetch origin && git pull`
- If no: Use current state without updating

**Display all collected inputs** for user confirmation:

**For Monorepo Strategy:**
```
Migration Configuration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extension: <extension-name>
Strategy: Multi-module (integrate into existing repo)
Working Directory: <working-dir> (target repo root)

Source Repository (openshift-tests-private):
  URL: git@github.com:openshift/openshift-tests-private.git
  Local Path: <local-source-path> (or "Will clone")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Destination Structure (in target repo):
  Extension Binary: cmd/extension/main.go
  Test Files: test/e2e/*.go (regular package in main module)
  Testdata: test/testdata/ (regular package in main module)
  Root go.mod: Will be updated with OTE dependency and replace directive for test/e2e
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**For Single-Module Strategy:**
```
Migration Configuration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extension: <extension-name>
Strategy: Single-module (isolated directory)
Working Directory: <working-dir>

Source Repository (openshift-tests-private):
  URL: git@github.com:openshift/openshift-tests-private.git
  Local Path: <local-source-path> (or "Will clone")
  Test Subfolder: test/extended/<test-subfolder>/
  Testdata Subfolder: test/extended/testdata/<testdata-subfolder>/

Target Repository:
  Local Path: <local-target-path> (or "Will clone from URL")
  URL: <target-repo-url> (if cloning)

Destination Structure (in tests-extension/):
  Extension Binary: tests-extension/cmd/main.go
  Test Files: tests-extension/test/e2e/*.go
  Testdata: tests-extension/test/testdata/
  Module: tests-extension/go.mod (single module)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Ask for confirmation before proceeding.

### Phase 3: Repository Setup (2 steps)

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
    git fetch origin
    git pull origin "$TARGET_BRANCH"
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
        echo "No remote found for openshift-tests-private, adding origin..."
        git remote add origin git@github.com:openshift/openshift-tests-private.git
        git fetch origin
        git pull origin master || git pull origin main
    fi
    cd ../..
    SOURCE_REPO="repos/openshift-tests-private"
else
    echo "Cloning openshift-tests-private repository..."
    git clone git@github.com:openshift/openshift-tests-private.git repos/openshift-tests-private
    SOURCE_REPO="repos/openshift-tests-private"
fi
```

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

#### Step 2: Setup Target Repository

**For Monorepo Strategy:**
```bash
# Working directory IS the target repository
TARGET_REPO="<working-dir>"
echo "Using target repository at: $TARGET_REPO"

# Extract module name from go.mod if it exists
if [ -f "$TARGET_REPO/go.mod" ]; then
    MODULE_NAME=$(grep '^module ' "$TARGET_REPO/go.mod" | awk '{print $2}')
    echo "Found existing module: $MODULE_NAME"
else
    echo "Warning: No go.mod found in target repository"
    echo "Will create test/go.mod for test dependencies"
fi
```

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
        git fetch origin
        git pull origin "$TARGET_BRANCH"
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
        echo "No remote found for target repository, adding origin..."
        git remote add origin <target-repo-url>
        git fetch origin
        git pull origin master || git pull origin main
    fi
    cd ../..
    TARGET_REPO="repos/target"
else
    echo "Cloning target repository..."
    git clone <target-repo-url> repos/target
    TARGET_REPO="repos/target"
fi
```

**Note:** In subsequent phases, use `$SOURCE_REPO` and `$TARGET_REPO` variables instead of hardcoded `repos/source` and `repos/target` paths.

### Phase 4: Structure Creation (5 steps)

#### Step 1: Create Directory Structure

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Create cmd directory for main.go
mkdir -p cmd/extension

# Create bin directory for binary output
mkdir -p bin

# Create test directories
mkdir -p test/e2e
mkdir -p test/testdata

echo "Created monorepo structure in existing repository"
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
mkdir -p test/testdata

echo "Created single-module structure in tests-extension/"
```

#### Step 2: Copy Test Files

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Copy test files from source to test/e2e/
# Use $SOURCE_TEST_PATH variable (set in Phase 3)
cp -r "$SOURCE_TEST_PATH"/* test/e2e/

# Count and display copied files
echo "Copied $(find test/e2e -name '*_test.go' | wc -l) test files from $SOURCE_TEST_PATH"
```

**For Single-Module Strategy:**
```bash
cd <working-dir>/tests-extension

# Copy test files from source to test/e2e/
# Use $SOURCE_TEST_PATH variable (set in Phase 3)
cp -r "$SOURCE_TEST_PATH"/* test/e2e/

# Count and display copied files
echo "Copied $(find test/e2e -name '*_test.go' | wc -l) test files from $SOURCE_TEST_PATH"
```

#### Step 3: Copy Testdata

**For Monorepo Strategy:**
```bash
cd <working-dir>

# Copy testdata if it exists (skip if user specified "none")
# Use $SOURCE_TESTDATA_PATH variable (set in Phase 3)
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

**For Single-Module Strategy:**
```bash
cd <working-dir>/tests-extension

# Copy testdata if it exists (skip if user specified "none")
# Use $SOURCE_TESTDATA_PATH variable (set in Phase 3)
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

### Phase 5: Code Generation (6 steps)

#### Step 1: Generate/Update go.mod Files

**For Monorepo Strategy:**

Create test/e2e/go.mod as a separate module:
```bash
cd <working-dir>

# Extract Go version from root go.mod
GO_VERSION=$(grep '^go ' go.mod | awk '{print $2}')
echo "Using Go version: $GO_VERSION (from target repo)"

# Get source repo path (set in Phase 3)
OTP_PATH="$SOURCE_REPO"

echo "Step 1: Create test/e2e/go.mod..."
cd test/e2e

# Initialize go.mod in test/e2e directory
ROOT_MODULE=$(grep '^module ' ../../go.mod | awk '{print $2}')
go mod init "$ROOT_MODULE/test/e2e"

echo "Step 2: Set Go version to match target repo..."
sed -i "s/^go .*/go $GO_VERSION/" go.mod

echo "Step 3: Get latest origin version from main branch..."
# Get the latest commit hash from origin/main
ORIGIN_LATEST=$(git ls-remote https://github.com/openshift/origin.git refs/heads/main | awk '{print $1}')
ORIGIN_SHORT="${ORIGIN_LATEST:0:12}"
ORIGIN_DATE=$(date -u +%Y%m%d%H%M%S)
ORIGIN_VERSION="v0.0.0-${ORIGIN_DATE}-${ORIGIN_SHORT}"
echo "Using latest origin version: $ORIGIN_VERSION"

echo "Step 4: Add required dependencies..."
go get github.com/openshift-eng/openshift-tests-extension@latest
go get "github.com/openshift/origin@main"
go get github.com/onsi/ginkgo/v2@latest
go get github.com/onsi/gomega@latest

echo "Step 5: Extract and add replace directives from openshift-tests-private..."
# Extract all replace directives from openshift-tests-private
grep -A 1000 "^replace" "$OTP_PATH/go.mod" | grep -B 1000 "^)" | grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

# Add replace directives to go.mod
echo "" >> go.mod
echo "replace (" >> go.mod
cat /tmp/replace_directives.txt >> go.mod
echo ")" >> go.mod

echo "Step 6: Resolve all dependencies..."
go mod tidy

echo "Step 7: Verify go.mod and go.sum are created..."
if [ -f "go.mod" ] && [ -f "go.sum" ]; then
    echo "✅ test/e2e/go.mod and go.sum created successfully"
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

echo "Step 8: Update root go.mod to add replace directive for test/e2e..."
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')

if ! grep -q "replace.*$MODULE_NAME/test/e2e" go.mod; then
    if grep -q "^replace (" go.mod; then
        # Add to existing replace section
        sed -i "/^replace (/a\\	$MODULE_NAME/test/e2e => ./test/e2e" go.mod
    else
        # Create new replace section
        echo "" >> go.mod
        echo "replace $MODULE_NAME/test/e2e => ./test/e2e" >> go.mod
    fi
    echo "✅ Replace directive added to root go.mod"
fi

echo "✅ Monorepo go.mod setup complete"
```

**Note:** For monorepo strategy:
- test/e2e has its own go.mod (separate module)
- go.mod/go.sum are in test/e2e/ directory
- Root go.mod has replace directive pointing to test/e2e
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

echo "Step 3: Get latest origin version from main branch..."
# Get the latest commit hash from origin/main
ORIGIN_LATEST=$(git ls-remote https://github.com/openshift/origin.git refs/heads/main | awk '{print $1}')
ORIGIN_SHORT="${ORIGIN_LATEST:0:12}"
ORIGIN_DATE=$(date -u +%Y%m%d%H%M%S)
ORIGIN_VERSION="v0.0.0-${ORIGIN_DATE}-${ORIGIN_SHORT}"
echo "Using latest origin version: $ORIGIN_VERSION"

echo "Step 4: Add required dependencies..."
go get github.com/openshift-eng/openshift-tests-extension@latest
go get "github.com/openshift/origin@main"
go get github.com/onsi/ginkgo/v2@latest
go get github.com/onsi/gomega@latest

echo "Step 5: Extract and add replace directives from openshift-tests-private..."
# Extract all replace directives from openshift-tests-private
grep -A 1000 "^replace" "$OTP_PATH/go.mod" | grep -B 1000 "^)" | grep -v "^replace" | grep -v "^)" > /tmp/replace_directives.txt

# Add replace directives to go.mod
echo "" >> go.mod
echo "replace (" >> go.mod
cat /tmp/replace_directives.txt >> go.mod
echo ")" >> go.mod

echo "Step 6: Resolve all dependencies..."
go mod tidy

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
```

#### Step 2: Generate Extension Binary (main.go)

**For Monorepo Strategy:**

Create `cmd/extension/main.go`:

**IMPORTANT:** Extract module name from go.mod first:
```bash
cd <working-dir>
MODULE_NAME=$(grep '^module ' go.mod | awk '{print $2}')
echo "Using module name: $MODULE_NAME"
```

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
	_ "$MODULE_NAME/test/e2e"
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
		re := regexp.MustCompile(` + "`\\[platform:([a-z]+)\\]`" + `)
		if match := re.FindStringSubmatch(spec.Name); match != nil {
			platform := match[1]
			spec.Include(et.PlatformEquals(platform))
		}
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
		re := regexp.MustCompile(` + "`\\[platform:([a-z]+)\\]`" + `)
		if match := re.FindStringSubmatch(spec.Name); match != nil {
			platform := match[1]
			spec.Include(et.PlatformEquals(platform))
		}
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

# Testdata path
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
		-pkg testdata -o $(TESTDATA_PATH)/bindata.go $(TESTDATA_PATH)/...
	@gofmt -s -w $(TESTDATA_PATH)/bindata.go
	@echo "Bindata generated successfully at $(TESTDATA_PATH)/bindata.go"

.PHONY: clean-bindata
clean-bindata:
	@echo "Cleaning bindata..."
	@rm -f $(TESTDATA_PATH)/bindata.go
```

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
```

#### Step 4: Create Makefile

**For Monorepo Strategy:**

Update root `Makefile` (or add extension target to existing one):

```makefile
# OTE binary configuration
TESTS_EXT_DIR := ./cmd/extension
TESTS_EXT_BINARY := bin/<extension-name>-tests-ext

# Build OTE extension binary
.PHONY: tests-ext-build
tests-ext-build:
	@echo "Building OTE test extension binary..."
	@cd test && $(MAKE) -f bindata.mk bindata
	@mkdir -p bin
	go build -mod=vendor -o $(TESTS_EXT_BINARY) $(TESTS_EXT_DIR)
	@echo "OTE binary built successfully at $(TESTS_EXT_BINARY)"

# Alias for backward compatibility
.PHONY: extension
extension: tests-ext-build

# Clean extension binary
.PHONY: clean-extension
clean-extension:
	@echo "Cleaning extension binary..."
	@rm -f $(TESTS_EXT_BINARY)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  tests-ext-build - Build OTE extension binary"
	@echo "  extension       - Alias for tests-ext-build"
	@echo "  clean-extension - Remove extension binary"
```

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
	go build -o $(BINARY) ./cmd
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

#### Step 5: Create fixtures.go

**For Monorepo Strategy:**

Create `test/testdata/fixtures.go`:

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
// This replaces functions like compat_otp.FixturePath().
//
// The file is extracted from embedded bindata to the filesystem on first access.
// Files are extracted to a temporary directory that persists for the test run.
//
// Example:
//   configPath := testdata.FixturePath("manifests/config.yaml")
//   data, err := os.ReadFile(configPath)
func FixturePath(relativePath string) string {
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
// Example:
//   data, err := testdata.GetFixtureData("config.yaml")
func GetFixtureData(relativePath string) ([]byte, error) {
	// Normalize path - bindata uses "testdata/" prefix
	cleanPath := relativePath
	if len(cleanPath) > 0 && cleanPath[0] == '/' {
		cleanPath = cleanPath[1:]
	}

	return Asset(filepath.Join("testdata", cleanPath))
}

// MustGetFixtureData is like GetFixtureData but panics on error.
// Useful in test initialization code.
func MustGetFixtureData(relativePath string) []byte {
	data, err := GetFixtureData(relativePath)
	if err != nil {
		panic(fmt.Sprintf("failed to get fixture data for %s: %v", relativePath, err))
	}
	return data
}

// Component-specific helper functions

// FixtureExists checks if a fixture exists in the embedded bindata.
// Use this to validate fixtures before accessing them.
//
// Example:
//   if testdata.FixtureExists("manifests/deployment.yaml") {
//       path := testdata.FixturePath("manifests/deployment.yaml")
//   }
func FixtureExists(relativePath string) bool {
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
```

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
RUN gzip cmd/extension/<extension-name>-tests-ext

# Final stage - Runtime image
FROM registry.ci.openshift.org/ocp/4.17:base-rhel9

# Copy the compressed OTE binary to /usr/bin/
COPY --from=builder /go/src/github.com/<org>/<component-name>/cmd/extension/<extension-name>-tests-ext.gz /usr/bin/

# ... rest of your Dockerfile (copy other binaries, set entrypoint, etc.)
```

**Key Points:**
- The Dockerfile builds the OTE binary using the `tests-ext-build` Makefile target
- The binary is compressed with gzip following OpenShift conventions
- The compressed binary (.gz) is copied to `/usr/bin/` in the final image
- The build happens in a builder stage with the Go toolchain
- The final runtime image only contains the compressed binary

**For Single-Module Strategy:**

For single-module strategy, refer to the Dockerfile integration section in the migration summary (Phase 8).

### Phase 6: Test Migration (3 steps - AUTOMATED)

#### Step 1: Replace FixturePath Calls

**For Monorepo Strategy:**

```bash
cd <working-dir>

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

    echo "✅ FixturePath calls replaced successfully"
fi
```

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

    echo "✅ FixturePath calls replaced successfully"
fi
```

#### Step 2: Add Testdata Import

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "Adding testdata import to test files..."

# Find all test files that now use testdata.FixturePath
TEST_FILES=$(grep -rl "testdata\.FixturePath" test/e2e/ --include="*_test.go" 2>/dev/null || true)

if [ -z "$TEST_FILES" ]; then
    echo "No test files need testdata import"
else
    TESTDATA_IMPORT="$MODULE_NAME/test/testdata"

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
            sed -i "/^import (/a\\	\"$TESTDATA_IMPORT\"" "$file"
            echo "  ✓ Added import to $file (existing import block)"
        elif grep -q "^import \"" "$file"; then
            # Convert single import to multi-import block
            sed -i '0,/^import "/s/^import "/import (\n\t"/' "$file"
            sed -i "/^import (/a\\	\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (created import block)"
        else
            # No imports yet, add after package line
            sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (new import block)"
        fi
    done

    echo "✅ Testdata imports added successfully"
fi
```

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
            sed -i "/^import (/a\\	\"$TESTDATA_IMPORT\"" "$file"
            echo "  ✓ Added import to $file (existing import block)"
        elif grep -q "^import \"" "$file"; then
            # Convert single import to multi-import block
            sed -i '0,/^import "/s/^import "/import (\n\t"/' "$file"
            sed -i "/^import (/a\\	\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (created import block)"
        else
            # No imports yet, add after package line
            sed -i "/^package /a\\\\nimport (\n\t\"$TESTDATA_IMPORT\"\n)" "$file"
            echo "  ✓ Added import to $file (new import block)"
        fi
    done

    echo "✅ Testdata imports added successfully"
fi
```

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
```

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

### Phase 7: Dependency Resolution and Verification (1 step)

#### Step 1: Verify Build and Test (Required)

**This is Step 3 of the Go module workflow: Build or test to verify everything works**

**For Monorepo Strategy:**

```bash
cd <working-dir>

echo "========================================="
echo "Verifying build and dependencies"
echo "========================================="

# Build the extension binary using Makefile
echo "Building extension binary..."
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
    echo "Migration complete - ready to commit"
    echo "========================================="
    echo "Files to commit:"
    echo "  - go.mod (root module with test/e2e replace directive)"
    echo "  - cmd/extension/main.go"
    echo "  - test/e2e/go.mod"
    echo "  - test/e2e/go.sum"
    echo "  - test/e2e/*.go (test files)"
    echo "  - test/testdata/fixtures.go"
    echo "  - test/bindata.mk"
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
```

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
1. ✅ go mod init (completed in Phase 5)
2. ✅ go get dependencies (completed in Phase 5)
3. ✅ go mod tidy (completed in Phase 5 and Step 1 above)
4. ✅ go build/test to verify (this step)

After successful verification, you're ready to commit both go.mod and go.sum files.

### Phase 8: Documentation (1 step)

#### Generate Migration Summary

Provide a comprehensive summary based on the strategy used:

**For Monorepo Strategy:**

```markdown
# OTE Migration Complete! 🎉

## Summary

Successfully migrated **<extension-name>** to OpenShift Tests Extension (OTE) framework using **monorepo strategy**.

## Created Structure

```
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
- ✅ `test/e2e/go.mod` - Test module with OpenShift replace directives
- ✅ `test/testdata/fixtures.go` - Testdata wrapper functions
- ✅ `test/bindata.mk` - Bindata generation rules
- ✅ `go.mod` (updated) - Added test/e2e replace directive
- ✅ `Makefile` (updated) - Added extension build target

### Test Files (Fully Automated)
- ✅ Copied **X** test files to `test/e2e/`
- ✅ Copied **Y** testdata files to `test/testdata/`
- ✅ Automatically replaced `compat_otp.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically replaced `exutil.FixturePath()` → `testdata.FixturePath()`
- ✅ Automatically added imports: `$MODULE_NAME/test/testdata`
- ✅ Automatically cleaned up old compat_otp/exutil imports

## Statistics

- **Test files:** X files
- **Testdata files:** Y files (or "none" if not applicable)
- **Platform filters:** Detected from labels and test names
- **Test suites:** 1 main suite (`<org>/<extension-name>/tests`)

## Next Steps (Monorepo)

### 1. Build Extension

```bash
cd <working-dir>
make extension
```

This will generate bindata and build the binary to `bin/<extension-name>-tests-ext`

### 2. Validate Tests

```bash
# List all discovered tests
./bin/<extension-name>-tests-ext list

# Run tests in dry-run mode
./bin/<extension-name>-tests-ext run --dry-run

# Test platform filtering
./bin/<extension-name>-tests-ext run --platform=aws --dry-run
```

### 3. Run Tests

```bash
# Run all tests
./bin/<extension-name>-tests-ext run

# Run specific test
./bin/<extension-name>-tests-ext run "test name pattern"
```

## Troubleshooting

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

# Resolve all dependencies
go mod tidy

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

go mod tidy
go mod download
```

### If Build Fails

```bash
# Check import paths in test files
grep -r "import" test/e2e/*.go

# Verify all dependencies are available
cd test/e2e && go mod verify

# Clean and rebuild
make clean-extension
make tests-ext-build
```

**For Single-Module Strategy:**

```markdown
# OTE Migration Complete! 🎉

## Summary

Successfully migrated **<extension-name>** to OpenShift Tests Extension (OTE) framework using **single-module strategy**.

## Created Structure

```
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
- **Platform filters:** Detected from labels and test names
- **Test suites:** 1 main suite (`<org>/<extension-name>/tests`)

## Next Steps (Single-Module)

### 1. Generate Bindata

```bash
cd <working-dir>/tests-extension
make bindata
```

This creates `test/testdata/bindata.go` with embedded test data.

### 2. Update Dependencies

```bash
go get github.com/openshift-eng/openshift-tests-extension@latest
go mod tidy
```

### 3. Build Extension

```bash
make build
```

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
```

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
```

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
```

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

## Troubleshooting

### If Dependency Download Was Interrupted

If you see warnings about failed dependency downloads during migration, complete the process manually:

```bash
cd <working-dir>/tests-extension

# Get the correct openshift/origin version from openshift-tests-private
OTP_PATH="<path-to-openshift-tests-private>"
ORIGIN_VERSION=$(grep "github.com/openshift/origin" "$OTP_PATH/go.mod" | head -1 | awk '{print $2}')
echo "Using openshift/origin version: $ORIGIN_VERSION"

# Complete dependency resolution
go get github.com/openshift-eng/openshift-tests-extension@latest
go get "github.com/openshift/origin@$ORIGIN_VERSION"
go get github.com/onsi/ginkgo/v2@latest
go get github.com/onsi/gomega@latest

# Resolve all dependencies
go mod tidy

# Download all modules
go mod download

# Verify files are created
ls -la go.mod go.sum
```

### If Build Fails

```bash
cd <working-dir>/tests-extension

# Check import paths in test files
grep -r "import" test/e2e/*.go

# Verify all dependencies are available
go mod verify

# Re-vendor dependencies
go mod vendor

# Clean and rebuild
make clean
make build
```

## Customization Options

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
```

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
```

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
   ```

2. **List tests:**
   ```bash
   ./<extension-name> list
   ```

3. **Run dry-run:**
   ```bash
   ./<extension-name> run --dry-run
   ```

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
   ```

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

Start by collecting all user inputs from Phase 2, then proceed through each phase systematically!
