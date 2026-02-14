# OTE Migration Plugin

Automated migration tools for integrating OpenShift component repositories with the openshift-tests-extension (OTE) framework.

## Overview

This plugin automates the complete process of migrating OpenShift component repositories to use the OTE framework. The tool handles everything from repository setup to code generation with customizable destination paths.

## Commands

### `/ote-migration:migrate`

Performs the complete OTE migration in one workflow.

**What it does:**

1. Collects directory structure strategy - Monorepo or single-module
2. Collects workspace directory - For migration operations
3. Collects target repository - Then **immediately switches to it**
4. Auto-detects extension name - From target repository (AFTER switching to it)
5. Collects source repository details - Test and testdata subfolders
6. Collects Dockerfile integration choice - Automated or manual
7. If automated: Searches target repository and asks user to select Dockerfiles
8. Displays migration configuration summary - For user review (includes selected Dockerfiles)
9. Sets up source repository - Clones/updates openshift-tests-private
10. Creates structure - Builds test/e2e/ with testdata/ inside
11. Copies files - Moves test files and testdata to destinations
12. Generates code - Creates go.mod, cmd/extension/main.go (at root for monorepo), Makefile, fixtures.go
13. Migrates tests - Automatically replaces FixturePath() calls, updates imports, and adds annotations
14. Resolves dependencies - Runs go mod tidy and vendor (vendor at root only for monorepo)
15. Integrates with Docker - Updates selected Dockerfiles or provides manual instructions
16. Provides validation - Gives comprehensive next steps and validation guide

**Key Features:**

- **Complete automation** - One command handles the entire migration
- **Smart extension name detection** - Auto-detects from repository name for binary/module naming
- **Two directory strategies** - Monorepo (integrated) or single-module (isolated)
- **CMD at root (monorepo)** - Places cmd/extension/main.go at repository root, not under test/
- **Filesystem-based test filtering** - Uses filesystem paths to include only local test/e2e/ tests, excluding unwanted kubernetes sig- tests from module cache
- **Smart e2e framework import handling** - Adds k8s.io/kubernetes/test/e2e/framework import where tests use e2e.Logf() or e2e.Failf()
- **Smart dependency filtering** - Excludes openshift-tests-private dependency to prevent importing entire test suite
- **Smart replace directive propagation (monorepo)** - Syncs non-k8s.io replace directives from test module to root, allowing independent k8s.io versions between modules
- **Vendor at root only (monorepo)** - Vendored dependencies only at repository root, not in test module
- **Custom test directory support** - Handles existing test/e2e directories with configurable alternatives
- **Dynamic git remote discovery** - No assumptions about remote names (no hardcoded 'origin')
- **Smart repository management** - Remote detection and update capabilities
- **Dynamic dependency resolution** - Fetches latest dependencies from upstream
- **Automatic Go toolchain management** - Uses `GOTOOLCHAIN=auto` to download required Go version
- **Automatic test migration** - Replaces FixturePath() calls, updates imports, removes kubernetes e2e framework, and adds annotations atomically with rollback
- **Simple test annotations** - Adds [OTP] at beginning of Describe blocks, [Level0] at beginning of test names only
- **Tag validation** - Validates all required tags are present before build
- **Informing lifecycle by default** - All migrated tests set to informing (won't block CI on failure)
- **Build verification** - Validates successful compilation before completion
- **Auto-install go-bindata** - For generating embedded testdata
- **Dockerfile integration** - Automated or manual Docker integration with backup

## Installation

This plugin is available through the ai-helpers marketplace:

```bash
/plugin marketplace add openshift-eng/ai-helpers
/plugin install ote-migration@ai-helpers
```

## Usage

Run the migration command:

```bash
/ote-migration:migrate
```

The plugin will:

1. **Directory structure strategy**
   - Monorepo (integrate into existing repo)
   - Single-module (isolated tests-extension/ directory)

2. **Workspace directory**
   - **Purpose**: Temporary directory for cloning repositories that don't exist locally:
     - Target repository (if Git URL provided in step 3)
     - openshift-tests-private source repo (if not already local)
   - **Recommendation**: Use an existing directory (like parent of your target repo) to minimize cloning overhead, or provide a temporary directory path for isolation
   - Example: `/home/user/repos` (parent dir), `.` (current dir), `/tmp/workspace`
   - **Note**: The working directory will switch to the target repository in step 3

3. **Target repository** (where files will be created)
   - **BOTH strategies require the target repository**
   - For both strategies: Can provide local path OR Git URL to clone
   - **If local path provided**: Will ask if you want to update it (git pull)
   - **If cloned from URL**: Automatically creates feature branch `ote-migration-YYYYMMDD`
   - **CRITICAL:** The migration immediately switches to this directory after collecting it

4. **Auto-detect extension name** from target repository
   - Detection happens AFTER switching to target repository
   - Detects from git remote URL or directory name
   - Used for binary name (`router-tests-ext`), module paths, directory structure
   - Example: Target repo `git@github.com:openshift/router.git` → extension name: `router`

5. **Test directory name** (monorepo only, if test/e2e exists)
   - Alternative name like `e2e-ote` or `ote-tests`

6. **Source repository details:**
   - Local openshift-tests-private path (optional)
   - Test subfolder under test/extended/
   - Testdata subfolder under test/extended/testdata/

7. **Dockerfile integration choice:**
   - **Automated** - Plugin will immediately search target repository for all Dockerfiles
   - **Manual** - Get instructions to update Dockerfiles yourself

8. **If automated: Select Dockerfiles** (conditional)
   - Plugin searches target repository recursively for all Dockerfiles
   - Displays numbered list of found Dockerfiles
   - Ask user to select which to update (by number, 'all', or 'none')

9. **Migration configuration summary** - Review all inputs before proceeding
   - Includes selected Dockerfiles if automated integration chosen

Then the migration proceeds with structure creation, file copying, code generation, test migration, and Dockerfile integration.

## Workspace vs Target Repository

The migration uses a clear separation between workspace and target repository:

**Workspace (Temporary)**:
- Temporary directory for migration preparation
- Used to clone repositories that don't exist locally:
  - `openshift-tests-private` (source repo) → cloned to `<workspace>/openshift-tests-private`
  - Target repository (if Git URL provided) → cloned to `<workspace>/<repo-name>` (e.g., `router`)
- Collected in Input 2 for both strategies
- Example: `/tmp/migration-workspace`, `/home/user/repos` (parent of target)
- **Recommendation**: Use an existing directory (like parent of your target repo) to minimize cloning overhead, or use a temporary directory for isolation
- **Note**: This is NOT the final working directory; migration switches to target repository

**Target Repository**:
- The actual component repository where OTE files will be created
- **Both strategies can use local path OR Git URL to clone**
- Collected in Input 3 (local path or Git URL for both strategies)
- Example: `/home/user/repos/router`, `git@github.com:openshift/router.git`

**Automatic Directory Switch**:
- **IMMEDIATELY after Input 3** (before extension name detection), the working directory BECOMES the target repository
- **If target repository was cloned**: Automatically creates feature branch `ote-migration-YYYYMMDD`
- From this point forward, all operations happen in the target repository:
  - Extension name is auto-detected from the target repository (Input 4)
  - All remaining inputs collected in target repository context
  - All OTE files created in target repository
- This ensures:
  - Extension name is detected from the correct repository
  - Files are never created in the temporary workspace
  - The workspace is only used for cloning repositories that don't exist locally
  - Migration work is isolated on a feature branch (when cloning)

## Directory Structure Strategies

The migration tool supports two directory strategies to fit different repository layouts:

### Option 1: Monorepo Strategy (Recommended for Component Repositories)

Integrates OTE into existing repository structure with **separate test module**.

**Structure created (when test/e2e doesn't exist):**

```text
<repo-root>/
├── bin/                           # Build artifacts (created by make)
│   └── <extension-name>-tests-ext # Binary
├── cmd/
│   └── extension/
│       └── main.go                # OTE entry point (at root, NOT under test/)
├── test/
│   └── e2e/                       # Created fresh
│       ├── go.mod                 # Separate test module
│       ├── go.sum
│       ├── *_test.go              # Test files
│       ├── testdata/              # Testdata inside test module
│       │   ├── bindata.go         # Generated
│       │   └── fixtures.go
│       └── bindata.mk             # Same level as testdata/
├── vendor/                        # Vendored at ROOT only
├── go.mod                         # Root module (with replace directive)
└── Makefile                       # Extension target added
```

**Structure created (when test/e2e already exists):**

```text
<repo-root>/
├── bin/                           # Build artifacts (created by make)
│   └── <extension-name>-tests-ext # Binary (same location)
├── cmd/
│   └── extension/
│       └── main.go                # OTE entry point (at root, NOT under test/)
├── test/
│   └── e2e/
│       ├── (existing-files...)    # Existing e2e tests (untouched)
│       └── <test-dir-name>/       # New subdirectory for OTE (e.g., "extension")
│           ├── go.mod             # Separate test module
│           ├── go.sum
│           ├── *_test.go          # Test files
│           ├── testdata/          # Testdata inside test module
│           │   ├── bindata.go     # Generated
│           │   └── fixtures.go
│           └── bindata.mk         # Same level as testdata/
├── vendor/                        # Vendored at ROOT only
├── go.mod                         # Root module (with replace directive)
└── Makefile                       # Extension target added
```

**Key characteristics:**

- **CMD at root**: `cmd/extension/main.go` located at repository root, NOT under test/
- **Separate test module**: Test module has its own `go.mod` independent from root `go.mod`
  - If `test/e2e` doesn't exist: `test/e2e/go.mod`
  - If `test/e2e` exists: `test/e2e/<subdir>/go.mod` (e.g., `test/e2e/extension/go.mod`)
- **Replace directive**: Root `go.mod` includes replace directive for test module:
  - If `test/e2e` doesn't exist: `replace <module>/test/e2e => ./test/e2e`
  - If `test/e2e` exists: `replace <module>/test/e2e/<subdir> => ./test/e2e/<subdir>`
- **Testdata inside test module**: Testdata is part of the test module (not a separate module)
  - If `test/e2e` doesn't exist: `test/e2e/testdata/`
  - If `test/e2e` exists: `test/e2e/<subdir>/testdata/`
- **Smart upstream replace directives**: Non-k8s.io replace directives are automatically synced from test module to root. k8s.io/* and OpenShift API/client-go/library-go replace directives are kept separate, allowing test module to use proven openshift-tests-private versions while root maintains its own k8s.io versions
- **Vendor at root only**: Dependencies vendored only at repository root (`vendor/`), NOT in test module
- **Auto-detected directory structure**: If `test/e2e` already exists, creates subdirectory (e.g., `test/e2e/extension/`) with go.mod, tests, and testdata all inside the subdirectory
- **Integrated build**: Makefile target `tests-ext-build` added to root
- **Binary location**: `bin/<extension-name>-tests-ext`

**Best for:**

- Component repos with existing `cmd/` and `test/` structure
- Teams wanting OTE tests alongside production code
- Repos that already use multi-module layout

**Example repositories:**

- machine-config-operator
- cluster-network-operator
- router

### Option 2: Single-Module Strategy (For Standalone Test Extensions)

Creates isolated `tests-extension/` directory with **single go.mod** in the target repository.

**Structure created:**

```text
<target-repo>/
└── tests-extension/
    ├── cmd/
    │   └── main.go                # OTE entry point
    ├── test/
    │   └── e2e/
    │       ├── *_test.go
    │       ├── testdata/
    │       │   ├── bindata.go
    │       │   └── fixtures.go
    │       └── bindata.mk         # Same level as testdata/
    ├── go.mod                     # Single module
    ├── go.sum
    └── Makefile
```

**Note:** The `<working-dir>` is used as a temporary workspace during migration. After repository setup, the working directory automatically switches to `<target-repo>` where all files are created.

**Key characteristics:**

- **Single module**: All code in one `go.mod`
- **Self-contained**: No changes to existing repo structure
- **Standalone binary**: `tests-extension/bin/<extension-name>-tests-ext`

**Best for:**

- Standalone test extensions
- Prototyping OTE migrations
- Repos without existing test structure
- Separate test repositories

## Important Notes

### Test Tracking Annotations

  The migration **automatically modifies test files** to add tracking annotations. This happens in Phase 5 (Test Migration).

  **Automatic annotations added:**

  1. **[OTP]** - Added at the BEGINNING of ALL Describe blocks
     - Marks all tests ported from openshift-tests-private
     - Helps track migration progress
     - Placement: At the very beginning of Describe string
     - Example: `g.Describe("[OTP][sig-router] Router tests", func() { ... })`

  2. **[Level0]** - Added at the BEGINNING of test names (ONLY for tests with "-LEVEL0-" suffix)
     - Identifies Level0 conformance tests
     - Auto-detected by searching for "-LEVEL0-" suffix in test names
     - **Automatically removes `-LEVEL0-` suffix** from test names after adding [Level0]
     - Example: `g.It("[Level0] Author:john-Critical-Test", func() {})` (was "Author:john-LEVEL0-Critical-Test")

  **Annotation logic:**

  1. **Add `[OTP]`** at BEGINNING of ALL Describe blocks
  2. **Find tests with `-LEVEL0-` suffix**
  3. **Add `[Level0]`** at BEGINNING of those test names
  4. **Remove `-LEVEL0-` suffix** from test names

  **Example: File with mixed tests**

  **Before migration:**
  ```go
  var _ = g.Describe("[sig-router] Router tests", func() {
      defer g.GinkgoRecover()
      var oc = compat_otp.NewCLI("default-router", compat_otp.KubeConfigPath())

      g.It("Author:john-LEVEL0-Critical-12345-Basic routing", func() {})
      g.It("Author:jane-High-67890-Advanced routing", func() {})
      g.It("Author:bob-LEVEL0-Critical-11111-Health check", func() {})
  })
  ```

  **After migration:**
  ```go
  var _ = g.Describe("[OTP][sig-router] Router tests", func() {
      defer g.GinkgoRecover()
      var oc = compat_otp.NewCLI("default-router", compat_otp.KubeConfigPath())

      g.It("[Level0] Author:john-Critical-12345-Basic routing", func() {})  // [Level0] added, -LEVEL0- removed
      g.It("Author:jane-High-67890-Advanced routing", func() {})  // No [Level0] - wasn't a Level0 test
      g.It("[Level0] Author:bob-Critical-11111-Health check", func() {})    // [Level0] added, -LEVEL0- removed
  })
  ```

  **Full test names visible in list:**
  ```text
  [OTP][sig-router] Router tests [Level0] Author:john-Critical-12345-Basic routing
  [OTP][sig-router] Router tests Author:jane-High-67890-Advanced routing
  [OTP][sig-router] Router tests [Level0] Author:bob-Critical-11111-Health check
  ```

  **Benefits:**
- **Track migration progress** - Count tests with `[OTP]` tag
- **Identify Level0 tests** - Filter by `[Level0]` tag
- **Simpler test structure** - No Describe block splitting required
- **Easier review** - Less file changes, clearer diff

  **Verification after migration:**
  ```bash
  # Count total ported tests (all should have [OTP])
  ./bin/<extension-name>-tests-ext list | grep -c "\[OTP\]"

  # Count Level0 conformance tests
  ./bin/<extension-name>-tests-ext list | grep -c "\[Level0\]"

  # View restructured test names
  ./bin/<extension-name>-tests-ext list | head -10
  ```

### Test Filtering to Prevent Unwanted Tests

  The migration includes **two layers of protection** to ensure ONLY your migrated tests are included in the binary, preventing 1000+ unwanted tests from being registered.

  **Problem Solved**: Without these protections, the binary would include:
  - 600+ kubernetes sig- tests from dependencies in `/go/pkg/mod/`
  - 400+ openshift-tests-private tests from dependency imports
  - Result: 1000+ extra tests instead of just your ~50 migrated tests

  **Protection Layer 1: Dependency Filtering (Phase 4)**

  When copying replace directives from openshift-tests-private/go.mod, the migration **excludes** the openshift-tests-private package itself:

  ```bash
  grep -A 1000 "^replace" "$SOURCE_PATH/go.mod" | grep -B 1000 "^)" | \
      grep -v "^replace" | grep -v "^)" | \
      grep -v "github.com/openshift/openshift-tests-private" > /tmp/replace_directives.txt
  ```

  This prevents `github.com/openshift/openshift-tests-private` from appearing as a dependency in your test module's go.mod.

  **Protection Layer 2: Filesystem Path Filtering in main.go (Phase 4)**

  The generated `cmd/extension/main.go` filters specs to ONLY include tests from local `test/e2e/` directory:

  ```go
  // Build test specs from Ginkgo
  allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()

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

  ext.AddSpecs(componentSpecs)
  ```

  **Why this works**: Ginkgo reports filesystem paths in CodeLocations:
  - ✅ Local tests: `/home/user/repo/test/e2e/file.go`
  - ❌ Kubernetes tests: `/go/pkg/mod/github.com/openshift/kubernetes@v1.30.1.../test/e2e/...`
  - ❌ Vendor tests: `/vendor/k8s.io/kubernetes/test/e2e/...`

  **Result**: Binary lists ONLY your local test/e2e/ tests, excluding all kubernetes sig- tests from module cache and vendor.

  **Verification after migration:**
  ```bash
  # List tests - should only show YOUR local tests
  ./bin/<extension-name>-tests-ext list tests | jq -r '.[].name'

  # Count should match number of migrated test cases
  ./bin/<extension-name>-tests-ext list tests | jq -r '.[].name' | wc -l
  ```

### Dynamic Dependency Resolution

  The migration tool **fetches the latest commit from specified upstream branches** directly from repositories instead of copying potentially stale versions from openshift-tests-private.

  **What's fetched dynamically:**

  1. **Kubernetes dependencies** - Latest commit from `github.com/openshift/kubernetes` **master branch**
     ```bash
     K8S_LATEST=$(git ls-remote https://github.com/openshift/kubernetes.git refs/heads/master | awk '{print $1}')
     # Creates versioned replace directives for all k8s.io/* packages using this commit hash
     ```

  2. **Ginkgo testing framework** - Latest commit from `github.com/openshift/onsi-ginkgo` **v2.27.2-openshift-4.22 branch**
     ```bash
     GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')
     # Uses the latest commit from this specific OpenShift-maintained branch, not ginkgo's main branch
     ```

  3. **Origin dependencies** - From `github.com/openshift/origin` (main branch)
     ```bash
     ORIGIN_LATEST=$(git ls-remote https://github.com/openshift/origin.git refs/heads/main | awk '{print $1}')
     ```

  **Why this matters:**

  Prevents common API incompatibility errors:
- ❌ `undefined: ginkgo.NewWriter`
- ❌ `undefined: diff.Diff` (library-go)
- ❌ `undefined: otelgrpc.UnaryClientInterceptor` (cri-client)
- ❌ `structured-merge-diff/v6 vs v4` type mismatches

  **Old behavior (problematic):**
- Copied all replace directives from `openshift-tests-private/go.mod`
- Could be weeks or months out of date
- Led to build failures with newer dependencies

  **New behavior (reliable):**
- Fetches latest commit hashes at migration time
- Generates fresh pseudo-versions **using actual git commit timestamps** (not current time)
- Ensures compatibility with current OpenShift ecosystem
- Prevents `invalid pseudo-version: does not match version-control timestamp` errors

  **Ginkgo version upgrade (Step 4b - Single-Module Only):**

  **NOTE:** This step is currently implemented **only for single-module strategy**. Monorepo strategy uses the original working approach without this explicit ginkgo update.

  For single-module, after copying replace directives from openshift-tests-private (which may contain an outdated ginkgo version from August 2024), the migration **explicitly updates ginkgo to the latest version** from the v2.27.2-openshift-4.22 branch:

  ```bash
  # Step 4: Copy replace directives from openshift-tests-private (may be old)
  grep -A 1000 "^replace" openshift-tests-private/go.mod >> go.mod

  # Step 4b: Immediately update ginkgo to latest (prevents build failures)
  GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')
  GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/onsi-ginkgo/v2@${GINKGO_LATEST}"
  ```

  **Why this is critical for single-module:**
  - openshift-tests-private may have ginkgo from August 2024 (v2.6.1-0.20240806135314)
  - August 2024 version lacks APIs like `ginkgo.NewWriter` and `spec.Labels`
  - Migration needs November 2024+ version (v2.6.1-0.20251120221002) from v2.27.2-openshift-4.22 branch
  - Without Step 4b, build fails with `undefined: ginkgo.NewWriter` or `spec.Labels undefined`
  - This step ensures correct version is set BEFORE Phase 6, making migration more robust
  - Uses `go get` to create proper pseudo-version format (not `sed` which creates malformed versions)

### Module Independence: k8s.io Version Isolation (Monorepo)

  **IMPORTANT:** In monorepo strategy, the test module and root module can maintain **independent k8s.io versions**.

  **The design:**
  - Test module uses k8s.io replace directives from `openshift-tests-private` (proven, tested configuration)
  - Root module keeps its own k8s.io versions (whatever the component project uses)
  - **k8s.io/* and `github.com/openshift/{api,client-go,library-go}` replace directives are NOT synced** from test module to root

  **Why this matters:**
  - Test module needs specific k8s.io versions proven to work with openshift-tests-private
  - Root module may use newer or different k8s.io versions for the component itself
  - Module boundaries (via `replace` directives) allow each module to use its own dependencies
  - Prevents version conflicts like `k8s.io/kubernetes v1.35.1` (root) vs `v1.34.1` (test)

  **What gets synced in Phase 6:**
  - ✅ Non-k8s.io replace directives (e.g., `github.com/onsi/ginkgo/v2`)
  - ✅ Other upstream replace directives
  - ❌ `k8s.io/*` replace directives (kept separate per module)
  - ❌ `github.com/openshift/api` (kept separate per module)
  - ❌ `github.com/openshift/client-go` (kept separate per module)
  - ❌ `github.com/openshift/library-go` (kept separate per module)

  **Example:**
  ```
  Root module go.mod:
    require k8s.io/kubernetes v1.35.1  // Root uses v1.35.1

  Test module go.mod:
    require k8s.io/kubernetes v1.34.1
    replace k8s.io/kubernetes => github.com/openshift/kubernetes v1.30.1-0.20241002124647-1892e4deb967
    // Test uses v1.30.1 via replace (from openshift-tests-private)
  ```

  Both versions coexist peacefully thanks to proper module boundaries.

### API Version Upgrades

  The migration **ensures API compatibility** by upgrading `github.com/openshift/api` and `github.com/openshift/client-go` to the latest versions from their master branches.

  **The problem this solves:**

  Origin's go.mod often specifies outdated versions that are incompatible with origin's actual code. For example:

  ```bash
  # Build error from version mismatch:
  undefined: configv1.InsightsDataGatherInterface

  # Root cause:
  # - Origin (latest) uses newer APIs
  # - Origin's go.mod specifies old client-go from 3 months ago
  # - Old client-go doesn't have the new APIs
  ```

  **How it works:**

  1. **During test module creation** (Phase 4, Step 6a):
     - Fetches latest client-go commit from master branch: `git ls-remote https://github.com/openshift/client-go.git refs/heads/master`
     - Upgrades to latest version: `go get github.com/openshift/client-go@<latest-commit>`
     - This pulls in compatible api version automatically

  2. **Deferred full resolution** (Phase 6, Step 1):
     - Runs full `go mod tidy` after test migration completes
     - Resolves any remaining dependency conflicts
     - Ensures all transitive dependencies are compatible

  **Example:**

  ```bash
  # Fetch latest client-go commit (fast - just git ls-remote)
  CLIENT_GO_LATEST=$(git ls-remote https://github.com/openshift/client-go.git refs/heads/master | awk '{print $1}')
  # CLIENT_GO_LATEST=a1b2c3d4e5f6...

  # Upgrade to latest (may take 30-60 seconds)
  GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go get "github.com/openshift/client-go@$CLIENT_GO_LATEST"

  # This automatically pulls in compatible api version
  # e.g., github.com/openshift/api v0.0.0-20260201123456-abc123def456
  ```

  **Benefits:**

- ✅ Prevents `undefined: <type>` errors from API mismatches
- ✅ Uses latest APIs compatible with current origin
- ✅ Avoids stale versions from origin's go.mod
- ✅ Includes timeout protection and fallback to go mod tidy
- ✅ Both test module and root module get compatible versions via go mod tidy

### Automatic Go Toolchain Management

  The migration uses `GOTOOLCHAIN=auto` and `GOSUMDB=sum.golang.org` to automatically download required Go versions.

  **What this solves:**

  If dependencies require a newer Go version than what you have installed:

  ```bash
  # Without GOTOOLCHAIN=auto (fails):
  go: go.mod requires go >= 1.XX.Y (running go 1.XX.Z; GOTOOLCHAIN=local)

  # With GOTOOLCHAIN=auto (succeeds):
  # Automatically downloads and uses the required Go version
  ```

  **How it works:**
- Your system Go: older version (e.g., 1.23.1)
- Dependencies require: newer version (e.g., 1.24.0+)
- `GOTOOLCHAIN=auto` downloads: version specified in go.mod's toolchain directive
- Build succeeds using the downloaded toolchain

  **Used in these migration steps:**
  ```bash
  # During go.mod creation
  GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod tidy

  # During dependency verification
  GOTOOLCHAIN=auto GOSUMDB=sum.golang.org go mod download
  ```

  **Manual usage after migration:**
  ```bash
  # Set globally in your environment
  export GOTOOLCHAIN=auto
  export GOSUMDB=sum.golang.org

  # Or per-command
  GOTOOLCHAIN=auto go mod tidy
  ```

### Smart Go Version Management (Phase 6, Step 2b)

  **The Problem:**
  - Docker builder images typically support up to Go 1.24
  - Root or test module go.mod may require Go 1.25+
  - Extension binary builds from `./cmd/extension`, which imports the test module
  - Go checks **both** root and test module go.mod files during build
  - Build fails with: `go: module ./test/e2e requires go >= 1.25.0 (running go 1.24.11; GOTOOLCHAIN=local)`

  **The Solution:**
  Automatically adjust **both** root and test module go.mod to Go 1.24 (matching Docker builder) when either requires Go 1.25+:

  ```bash
  # Check both go.mod files
  ROOT_GO_VERSION=$(grep "^go " go.mod | awk '{print $2}' | cut -d. -f1,2)
  TEST_GO_VERSION=$(grep "^go " "$TEST_MODULE_DIR/go.mod" | awk '{print $2}' | cut -d. -f1,2)

  # If either requires 1.25+, adjust BOTH to 1.24
  if [ "$ROOT_GO_VERSION" = "1.25" ] || [ "$ROOT_GO_VERSION" = "1.26" ] || [ "$ROOT_GO_VERSION" = "1.27" ]; then
      NEEDS_ADJUSTMENT=true
  fi
  if [ "$TEST_GO_VERSION" = "1.25" ] || [ "$TEST_GO_VERSION" = "1.26" ] || [ "$TEST_GO_VERSION" = "1.27" ]; then
      NEEDS_ADJUSTMENT=true
  fi

  if [ "$NEEDS_ADJUSTMENT" = "true" ]; then
      # Adjust root go.mod
      sed -i 's/^go .*/go 1.24/' go.mod

      # Adjust test module go.mod
      sed -i 's/^go .*/go 1.24/' "$TEST_MODULE_DIR/go.mod"
  fi
  ```

  **Why This Works:**
  - The `go 1.24` directive is a **minimum requirement**, not a maximum
  - With `GOTOOLCHAIN=auto`, dependencies that need Go 1.25+ still work (toolchain auto-downloads)
  - Neither root nor test module code actually requires Go 1.25+ features
  - Extension binary build command (`go build ./cmd/extension`) resolves **both** go.mod files
  - Docker builder (Go 1.24) can successfully build Go 1.24 code
  - `go mod tidy` with `GOTOOLCHAIN=auto` continues to work correctly for both modules

  **Impact on Operations:**

  | Operation | Before Fix | After Fix | Impact |
  |-----------|------------|-----------|---------|
  | `go mod tidy` (test module) | ✅ Works (GOTOOLCHAIN=auto) | ✅ Works (GOTOOLCHAIN=auto) | No change |
  | `go mod tidy` (root) | ✅ Works (GOTOOLCHAIN=auto) | ✅ Works (GOTOOLCHAIN=auto) | No change |
  | `make extension` (local) | ❌ **Failed** (Go 1.25 required) | ✅ **Fixed** (Go 1.24 matches) | **Positive** |
  | Docker build | ❌ **Failed** (Go 1.25 required) | ✅ **Fixed** (Go 1.24 matches) | **Positive** |

  **Benefits:**
  - ✅ Docker builds succeed with Go 1.24 builder images
  - ✅ Local `make extension` builds succeed
  - ✅ `go mod tidy` operations unaffected (GOTOOLCHAIN=auto still works)
  - ✅ Clean solution without environment variable complexity
  - ✅ Both modules maintain proper dependency resolution

### Makefile Targets

The migration creates Makefile targets for building the OTE extension binary:

**Available targets:**

```bash
make tests-ext-build     # Build the OTE binary
make extension           # Alias for tests-ext-build
make clean-extension     # Clean all generated binaries and artifacts
```

**Output locations:**

- **Monorepo:** `bin/<extension-name>-tests-ext`
- **Single-module:** `tests-extension/bin/<extension-name>-tests-ext`

### Docker Build Integration

The migration provides **automated or manual Dockerfile integration** to include the OTE extension binary in your component's Docker image.

**Integration Options:**

During Phase 7 of migration, you can choose:
1. **Automated** - Plugin updates your Dockerfiles automatically with backup
2. **Manual** - Plugin provides instructions for you to update yourself

**Automated Integration:**

**Phase 1 (During initial setup):**
1. Search target repository recursively for all Dockerfiles
   - Searches for files named `Dockerfile` or `Dockerfile.*`
   - Excludes `vendor/`, `.git/`, and `tests-extension/` directories
2. Display a numbered list of found Dockerfiles
3. **Ask you to choose** which Dockerfile(s) to update (select by number, 'all', or 'none')
4. Store your selection for use in Phase 7

**Phase 7 (Dockerfile Integration):**
1. Use the Dockerfiles you selected in Phase 1
2. Create backup for selected files (e.g., `Dockerfile.pre-ote-migration`)
3. Add test-extension-builder stage (builds and compresses)
4. Add COPY command to final stage

**How it works:**

1. **Test extension builder stage** (added by migration):
   ```dockerfile
   # Test extension builder stage
   FROM <your-existing-builder> AS test-extension-builder
   RUN mkdir -p /go/src/github.com/openshift/<extension-name>
   WORKDIR /go/src/github.com/openshift/<extension-name>
   COPY . .
   RUN make tests-ext-build && \
       cd bin && \
       tar -czvf <extension-name>-test-extension.tar.gz <extension-name>-tests-ext && \
       rm -f <extension-name>-tests-ext
   ```

2. **Copy to final stage** (added by migration):
   ```dockerfile
   # Copy test extension binary
   COPY --from=test-extension-builder /go/src/github.com/openshift/<extension-name>/bin/<extension-name>-test-extension.tar.gz /usr/bin/
   ```

**Final image includes:**
- Your component binaries (e.g., `/usr/bin/component-operator`)
- OTE extension binary at `/usr/bin/<extension-name>-test-extension.tar.gz`

**Binary registration with OpenShift origin:**

The binary at `/usr/bin/<extension-name>-test-extension.tar.gz` can be registered in OpenShift origin's test registry for automatic test discovery and execution in CI.

**Key file locations:**

All strategies follow this principle: **bindata.mk must be at the same level as the testdata package**

- **Monorepo (test/e2e doesn't exist)**:
  - testdata: `test/e2e/testdata/`
  - bindata.mk: `test/e2e/bindata.mk`

- **Monorepo (test/e2e exists - subdirectory mode)**:
  - testdata: `test/e2e/extension/testdata/`
  - bindata.mk: `test/e2e/extension/bindata.mk`

- **Single-Module**:
  - testdata: `tests-extension/test/e2e/testdata/`
  - bindata.mk: `tests-extension/test/e2e/bindata.mk`

**Verification:**

```bash
# Build image locally
docker build -t test-image:latest -f <path-to-dockerfile> .

# Verify binary exists in image (override ENTRYPOINT to run ls)
docker run --rm --entrypoint ls test-image:latest -lh /usr/bin/*-test-extension.tar.gz

# Extract and test binary (override ENTRYPOINT to run cat)
docker run --rm --entrypoint cat test-image:latest /usr/bin/<extension-name>-test-extension.tar.gz | tar -xzv
./bin/<extension-name>-tests-ext list
```

### Test Lifecycle (Informing by Default)

All migrated tests are automatically set to **Informing** lifecycle - they will run but won't block CI on failure.

```go
// Set lifecycle for all migrated tests to Informing
// Tests will run but won't block CI on failure
specs.Walk(func(spec *et.ExtensionTestSpec) {
    spec.Lifecycle = et.LifecycleInforming
})
```

**Lifecycle options:**

- `et.LifecycleInforming` - Test failures don't block CI (default for migrated tests)
- `et.LifecycleBlocking` - Test failures block CI

**To make tests blocking:**

If you want certain tests to block CI, modify the generated `main.go` or `cmd/extension/main.go`:

```go
// Example: Make Level0 tests blocking, others informing
specs.Walk(func(spec *et.ExtensionTestSpec) {
    if strings.Contains(spec.Name, "[Level0]") {
        spec.Lifecycle = et.LifecycleBlocking
    } else {
        spec.Lifecycle = et.LifecycleInforming
    }
})
```

### Tag Validation

Before build verification, the migration validates that all required tags are properly applied:

**Validation checks:**

1. All Describe blocks have `[OTP]` tag at the beginning
2. No remaining `-LEVEL0-` suffixes in test names (should be replaced with `[Level0]` prefix)
3. Files using `testdata.FixturePath` have proper imports

**On validation failure:**

The migration stops and provides specific guidance on which files need fixing, preventing incomplete migrations.

## Recent Updates

The migration workflow has been enhanced with comprehensive test filtering and proper framework initialization to ensure tests run correctly both locally and in-cluster:

### Latest Critical Fix - Framework Initialization

**Problem**: Tests were failing with `unable to load in-cluster configuration, KUBERNETES_SERVICE_HOST and KUBERNETES_SERVICE_PORT must be defined` even when KUBECONFIG was set.

**Solution**: Preserved framework initialization (`util.InitStandardFlags()` and `framework.AfterReadingAllFlags()`) while removing only the cleanup wrapper. This ensures:
- ✅ Kubeconfig flags are registered (KUBECONFIG environment variable works)
- ✅ Framework context is properly set up
- ✅ Tests can connect to cluster both locally and in-cluster
- ✅ OTE framework handles cleanup automatically (no `util.WithCleanup()` needed)

### Key Improvements

1. **Filesystem Path Filtering (2026-02-14)** - Changed from module paths to filesystem paths for test filtering. Uses `/test/e2e/` with exclusions for `/go/pkg/mod/` and `/vendor/` to match Ginkgo's actual CodeLocation format
2. **Smart E2E Framework Import Handling (2026-02-14)** - Changed from removing e2e framework import to adding it where needed. Tests using `e2e.Logf()` or `e2e.Failf()` now get the import automatically
3. **Monorepo Variant Support (2026-02-14)** - Monorepo mode now supports two variants: (1) No existing test/e2e → create test/e2e directly; (2) Existing test/e2e → create test/e2e/<subdirectory> to avoid conflicts. User can specify subdirectory name (default: "extension")
4. **Automatic k8s.io Version Fix (2026-02-14)** - Detects outdated OpenShift kubernetes fork (October 2024) and automatically updates to October 2025 fork. Adds missing k8s.io/externaljwt package, pins otelgrpc to v0.53.0, removes deprecated packages, and updates Ginkgo version. Prevents build errors: `undefined: otelgrpc.UnaryClientInterceptor`, `cannot use v6 as net.IP`, `undefined: diff.Diff`
5. **Lightweight Framework Initialization** - Uses `util.InitStandardFlags()` and `compat_otp.InitTest()` without heavy kubernetes e2e framework dependency for smaller binaries and faster builds
5. **Two-Layer Test Filtering** - Layer 1: Dependency filtering excludes openshift-tests-private; Layer 2: Filesystem path filter includes only local test/e2e/ tests, excluding module cache and vendor
6. **Vendor Mode Build** - Uses `-mod=vendor` instead of `-mod=mod` to ensure consistent dependency resolution in all build environments
7. **Go Import Conventions** - Uses `goimports` to automatically fix import ordering after migration, ensuring testdata imports are properly positioned per Go conventions
8. **Auto-install go-bindata** - bindata.mk automatically installs go-bindata if not present, preventing Docker build failures
9. **Smart Go Version Management** - Automatically adjusts root go.mod to match Docker builder version (e.g., 1.24) while keeping test module at higher version (e.g., 1.25) for dependencies
10. **Enhanced Dependency Management** - Added retry logic and better error handling for all `go get` commands
11. **Ginkgo Version Alignment** - Automatically aligns with OTE framework's Ginkgo version (December 2024) instead of using OTP's older version (August 2024)
12. **k8s.io Version Consistency** - Syncs ALL replace directives (including k8s.io) from test module to root for version consistency
13. **Old kube-openapi Pin Removal** - Automatically removes stale kube-openapi pins from February 2024 that cause yaml type errors
14. **Smart Docker Builder Selection** - Intelligently maps Go versions (1.21-1.27) to appropriate OpenShift builder images
15. **Comprehensive Troubleshooting** - Added 8 detailed troubleshooting entries based on real-world migration experience

### Two-Layer Test Filtering

See the "Test Filtering to Prevent Unwanted Tests" section above for comprehensive details on how these layers work together.

### Documentation

- **[skill-updates-summary.md](../../skill-updates-summary.md)** - Initial three-layer filtering implementation
- **[latest-skill-updates.md](../../latest-skill-updates.md)** - Latest framework initialization fix and enhancements

## Resources

- [OTE Framework Enhancement](https://github.com/openshift/enhancements/pull/1676)
- [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension)
- [Example Implementation](https://github.com/openshift-eng/openshift-tests-extension/blob/main/cmd/example-tests/main.go)
- [Complete Design Document](../../OTE_PLUGIN_COMPLETE_DESIGN.md) - Comprehensive technical documentation with detailed directory structures, complete Dockerfile examples, and troubleshooting guides for both monorepo and single-module strategies
- [Skill Updates Summary](../../skill-updates-summary.md) - Initial three-layer test filtering implementation
- [Latest Skill Updates](../../latest-skill-updates.md) - Framework initialization fix and recent enhancements
