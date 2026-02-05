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
5. Collects sig filter tags - User provides sig tag(s) for test filtering
6. Sets up source repository - Clones/updates openshift-tests-private
7. Creates structure - Builds test/e2e and test/testdata directories
8. Copies files - Moves test files and testdata to destinations
9. Generates code - Creates go.mod, cmd/main.go, Makefile, fixtures.go with multi-tag filtering
10. Migrates tests - Automatically replaces FixturePath() calls and updates imports
11. Provides validation - Gives comprehensive next steps and validation guide

**Key Features:**

- **Complete automation** - One command handles the entire migration
- **Smart extension name detection** - Auto-detects from repository name for binary/module naming
- **Automatic sig tag detection** - Scans test files to discover sig tags with user confirmation, eliminating manual tag lookup
- **Flexible sig tag filtering** - Support single or multiple sig tags for test filtering (e.g., `router` or `router,network-edge`)
- **Two directory strategies** - Monorepo (integrated) or single-module (isolated)
- **Automatic replace directive propagation (monorepo)** - Copies k8s.io/* and upstream replace directives from test module to root go.mod, and synchronizes openshift/api and openshift/client-go versions to prevent dependency conflicts
- **Custom test directory support** - Handles existing test/e2e directories with configurable alternatives
- **Dynamic git remote discovery** - No assumptions about remote names (no hardcoded 'origin')
- **Smart repository management** - Remote detection and update capabilities
- **Dynamic dependency resolution** - Fetches latest Kubernetes and ginkgo versions from upstream
- **Automatic Go toolchain management** - Uses `GOTOOLCHAIN=auto` to download required Go version
- **Automatic test migration** - Replaces FixturePath() calls and updates imports
- **Multi-tag test filtering** - Generated main.go filters tests by user-specified sig tags
- **Test tracking annotations** - Automatically adds [OTP] and [Level0] tags, removes duplicate `-LEVEL0-` suffixes
- **Tag validation** - Validates all required tags are present before build
- **Informing lifecycle by default** - All migrated tests set to informing (won't block CI on failure)
- **Enhanced Makefile targets** - Includes compress and copy targets for CI/CD workflows
- **Build verification** - Validates successful compilation before completion
- **Git status validation** - Ensures clean working directory
- **Auto-install go-bindata** - For generating embedded testdata
- **Dockerfile integration** - Provides templates for both strategies

## Performance and Reliability Enhancements

### Recent Critical Fixes (January 2026)

**Problem Solved:** The plugin used to timeout during dependency resolution, leaving test files partially migrated with broken imports.

**Three Critical Fixes:**

1. **Parallel Git Clones (Performance Fix)**
   - **Before:** Sequential clones took ~90 seconds (origin → kubernetes → ginkgo)
   - **After:** Parallel clones take ~30-45 seconds (50% faster)
   - **Impact:** Reduces Phase 4 execution time significantly

   ```bash
   # Old approach (sequential - slow)
   git clone origin   # 30s
   git clone k8s      # 45s
   git clone ginkgo   # 15s
   Total: ~90s

   # New approach (parallel - fast)
   (git clone origin & git clone k8s & git clone ginkgo &)
   wait
   Total: ~45s
   ```

2. **Deferred Dependency Resolution (Decoupling Fix)**
   - **Before:** `go mod tidy` ran in Phase 4, timing out before Phase 5 (Test Migration)
   - **After:** `go mod download` in Phase 4, full `go mod tidy` deferred to Phase 6
   - **Impact:** Test migration (Phase 5) always runs, even if dependency resolution is slow
   - **Result:** No more partially migrated test files with broken imports

3. **Atomic Test Migration (Atomicity Fix)**
   - **Before:** Phase 5 steps could partially complete (Step 1 done, Steps 2-4 skipped)
   - **After:** Phase 5 backs up test files and rolls back on any failure
   - **Impact:** Test files are either fully migrated or left untouched - no partial states

   ```bash
   # Error handling added to Phase 5:
   - Step 0: Create backup of test files
   - Steps 1-4: Execute migration steps
   - Step 5: Validate all changes
   - On success: Remove backup, continue
   - On failure: Restore from backup, exit
   ```

**Migration Flow Before Fixes:**
```text
Phase 4 (go.mod generation)
  ├─ Step 5: git clone origin (30s) ✓
  ├─ Step 5: git clone kubernetes (45s) ✓
  ├─ Step 5: git clone ginkgo (15s) ✓
  ├─ Step 6: go mod tidy (60-120s) ⏱️ TIMEOUT
  └─ Phase 5 never runs → Test files have broken imports ❌

Result: Tests copied but imports not migrated → go mod tidy fails
```

**Migration Flow After Fixes:**
```text
Phase 4 (go.mod generation)
  ├─ Step 3: git ls-remote (parallel, 5s) ✓
  ├─ Step 3: git clone (parallel, 30-45s) ✓
  ├─ Step 6: go mod download (quick, non-blocking) ✓
  └─ Continue to Phase 5 ✓

Phase 5 (Test Migration - atomic)
  ├─ Step 0: Backup test files ✓
  ├─ Step 1: Replace FixturePath calls ✓
  ├─ Step 2: Add testdata imports ✓
  ├─ Step 3: Remove old imports ✓
  ├─ Step 4: Add annotations ✓
  ├─ Step 5: Validate changes ✓
  └─ On success: Remove backup, continue ✓

Phase 6 (Dependency Resolution)
  ├─ Step 1: go mod tidy (now safe after test migration) ✓
  └─ Step 2: Build verification ✓

Result: All test files fully migrated with correct imports ✅
```

**Error Recovery:**

If Phase 5 fails, test files are automatically restored:
```text
❌ Phase 5 failed - rolling back test files...
✅ Test files restored from backup
```

This ensures you can safely retry the migration without manual cleanup.

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

5. **Auto-detect sig filter tag(s)** with user confirmation
   - Automatically scans test files in `test/extended/<extension-name>/` to discover sig tags
   - Shows detected tags (e.g., `router,network-edge`) and asks for confirmation
   - User can accept detected tags or enter manually if detection fails
   - **Why this matters:** The generated binary uses these tags to filter which tests to include. If the tags don't match your test files, `./bin/<extension-name>-tests-ext list` will show 0 tests because the filtering logic won't find your tests

6. **Test directory name** (monorepo only, if test/e2e exists)
   - Alternative name like `e2e-ote` or `ote-tests`

7. **Source repository details:**
   - Local openshift-tests-private path (optional)
   - Test subfolder under test/extended/
   - Testdata subfolder under test/extended/testdata/

Then the migration proceeds with structure creation, file copying, code generation, and test migration.

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
│   ├── <extension-name>-tests-ext # Binary
│   └── <extension-name>-tests-ext.gz  # Compressed (optional)
├── cmd/
│   └── extension/
│       └── main.go                # OTE entry point (source code)
├── test/
│   ├── e2e/                       # Created fresh
│   │   ├── go.mod                 # Separate test module
│   │   ├── go.sum
│   │   ├── *_test.go              # Test files
│   │   └── testdata/              # Testdata inside test module
│   │       ├── bindata.go         # Generated
│   │       └── fixtures.go
│   └── bindata.mk
├── _output/                       # CI/CD artifacts (created by make)
│   └── <extension-name>-tests-ext.gz
├── go.mod                         # Root module (with replace directive)
└── Makefile                       # Extension target added
```

**Structure created (when test/e2e already exists):**

```text
<repo-root>/
├── bin/                           # Build artifacts (created by make)
│   ├── <extension-name>-tests-ext # Binary (same location)
│   └── <extension-name>-tests-ext.gz  # Compressed (optional)
├── cmd/
│   └── extension/
│       └── main.go                # OTE entry point (source code)
├── test/
│   ├── e2e/
│   │   ├── (existing-files...)    # Existing e2e tests (untouched)
│   │   └── <test-dir-name>/       # New subdirectory for OTE (e.g., "extension")
│   │       ├── go.mod             # Separate test module
│   │       ├── go.sum
│   │       ├── *_test.go          # Test files
│   │       └── testdata/          # Testdata inside test module
│   │           ├── bindata.go     # Generated
│   │           └── fixtures.go
│   └── bindata.mk
├── _output/                       # CI/CD artifacts (created by make)
│   └── <extension-name>-tests-ext.gz
├── go.mod                         # Root module (with replace directive)
└── Makefile                       # Extension target added
```

**Key characteristics:**

- **Separate test module**: Test module has its own `go.mod` independent from root `go.mod`
  - If `test/e2e` doesn't exist: `test/e2e/go.mod`
  - If `test/e2e` exists: `test/e2e/<subdir>/go.mod` (e.g., `test/e2e/extension/go.mod`)
- **Replace directive**: Root `go.mod` includes replace directive for test module:
  - If `test/e2e` doesn't exist: `replace <module>/test/e2e => ./test/e2e`
  - If `test/e2e` exists: `replace <module>/test/e2e/<subdir> => ./test/e2e/<subdir>`
- **Testdata inside test module**: Testdata is part of the test module (not a separate module)
  - If `test/e2e` doesn't exist: `test/e2e/testdata/`
  - If `test/e2e` exists: `test/e2e/<subdir>/testdata/`
- **Automatic upstream replace directives**: k8s.io/* and other replace directives are automatically copied from test module go.mod to root go.mod
- **Automatic dependency synchronization**: openshift/api and openshift/client-go in root go.mod are automatically updated to match the test module's versions (compatible with latest origin)
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
    │   ├── e2e/
    │   │   └── *_test.go
    │   └── testdata/
    │       ├── bindata.go
    │       └── fixtures.go
    ├── go.mod                     # Single module
    ├── go.sum
    ├── Makefile
    └── bindata.mk
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

### Test Filtering in Generated main.go

The generated `cmd/main.go` (or `cmd/extension/main.go` for monorepo) includes **component-specific test filtering** using the sig tags you provide during migration (Input 5). This ensures only your component's tests are registered with the OTE framework.

  **Filter implementation:**
  ```go
  // Build test specs from Ginkgo
  allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
  if err != nil {
      panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
  }

  // Filter to only include component-specific tests (tests with specified sig tags)
  // Parse sig filter tags from comma-separated list (value from Input 5)
  sigTags := strings.Split("router,network-edge", ",") // Tags user provided: "router,network-edge"
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
  ```

  **Why this matters:**
- Without this filter, you'd see **5,000+ upstream Kubernetes tests** in addition to your component tests
- The `sigTags` variable holds the comma-separated tags you provided during migration (e.g., `"router,network-edge"`)
- The filter uses **OR logic**: tests matching ANY of your specified sig tags are included
- Example: If you provided `router,network-edge`, tests with either `[sig-router]` OR `[sig-network-edge]` will be registered

  **Verification after migration:**
  ```bash
  # Should show only tests matching your specified sig tags
  ./bin/<extension-name>-tests-ext list

  # Count tests for each sig tag you provided
  # Example: If you provided "router,network-edge"
  ./bin/<extension-name>-tests-ext list | grep -c "\[sig-router\]"
  ./bin/<extension-name>-tests-ext list | grep -c "\[sig-network-edge\]"

  # Count all filtered tests (matching ANY of your sig tags)
  ./bin/<extension-name>-tests-ext list | wc -l
  ```

### Test Tracking Annotations

  The migration **automatically modifies test files** to add tracking annotations. This happens in Phase 5 (Test Migration) and restructures test names for better organization.

  **Automatic annotations added:**

  1. **[OTP]** - Added to ALL Describe blocks
     - Marks all tests ported from openshift-tests-private
     - Helps track migration progress
     - Placement: After `[sig-<extension-name>]` in Describe blocks
     - Example: `g.Describe("[sig-router][OTP]", func() { ... })`

  2. **[Level0]** - Added to Describe blocks containing Level0 tests
     - Identifies Level0 conformance test groups
     - Auto-detected by searching for "-LEVEL0-" string in test names within each Describe block
     - Placement: After `[OTP]` in Describe blocks
     - **Automatically removes `-LEVEL0-` suffix** from test names to prevent duplication
     - Applied per-Describe-block (NOT per-file)

  **Annotation logic (per-Describe-block):**

  The migration processes each Describe block independently:

  1. **Add `[OTP]`** to ALL Describe blocks (right after `[sig-xxx]`)
  2. **For EACH Describe block:**
     - Check if it contains at least one test with `-LEVEL0-` suffix
     - If yes, add `[Level0]` to THAT Describe block (after `[OTP]`)
     - Remove `-LEVEL0-` suffix from ALL test names in the file

  **Example: File with two Describe blocks**

  **Before migration:**
  ```go
  // Describe block #1 - Contains Level0 test
  g.Describe("[sig-router] Router Level0 tests", func() {
      g.It("Author:john-LEVEL0-Critical-12345-Basic routing", func() {})
      g.It("Author:jane-High-67890-Advanced routing", func() {})
  })

  // Describe block #2 - No Level0 tests
  g.Describe("[sig-router] Router performance tests", func() {
      g.It("Author:bob-Medium-11111-Performance test", func() {})
  })
  ```

  **After migration:**
  ```go
  // Describe block #1 - Gets [Level0] because it contains a LEVEL0 test
  g.Describe("[sig-router][OTP][Level0] Router Level0 tests", func() {
      g.It("Author:john-Critical-12345-Basic routing", func() {})  // -LEVEL0- removed
      g.It("Author:jane-High-67890-Advanced routing", func() {})
  })

  // Describe block #2 - Gets only [OTP] (no Level0 tests)
  g.Describe("[sig-router][OTP] Router performance tests", func() {
      g.It("Author:bob-Medium-11111-Performance test", func() {})
  })
  ```

  **Full test names visible in list:**
  ```text
  [sig-router][OTP][Level0] Router Level0 tests Author:john-Critical-12345-Basic routing
  [sig-router][OTP][Level0] Router Level0 tests Author:jane-High-67890-Advanced routing
  [sig-router][OTP] Router performance tests Author:bob-Medium-11111-Performance test
  ```

  **Benefits:**
- **Track migration progress** - Count tests with `[OTP]` tag
- **Identify Level0 tests** - Filter by `[Level0]` tag
- **Cleaner test hierarchy** - Describe blocks use tags only
- **Flexibility for test execution** - Run Level0 tests separately or in conformance suites

  **Verification after migration:**
  ```bash
  # Count total ported tests (all should have [OTP])
  ./bin/<extension-name>-tests-ext list | grep -c "\[OTP\]"

  # Count Level0 conformance tests
  ./bin/<extension-name>-tests-ext list | grep -c "\[Level0\]"

  # View restructured test names
  ./bin/<extension-name>-tests-ext list | head -10
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

### Enhanced Makefile Targets

The migration creates Makefile targets optimized for CI/CD workflows:

**Available targets:**

```bash
make tests-ext-build     # Build the OTE binary
make tests-ext-compress  # Build and compress with gzip
make tests-ext-copy      # Build, compress, and copy to _output/
make extension           # Alias for tests-ext-build
make clean-extension     # Clean all generated binaries and artifacts
```

**Output locations:**

- **Monorepo:** `bin/<extension-name>-tests-ext`
- **Single-module:** `tests-extension/bin/<extension-name>-tests-ext`
- **Compressed:** Same location with `.gz` extension
- **Copy destination:** `_output/<extension-name>-tests-ext.gz`

**CI/CD Integration:**

The `tests-ext-copy` target is designed for CI pipelines that collect build artifacts from the `_output/` directory.

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

1. Each test file contains at least one of the provided sig tags (e.g., `[sig-router]` or `[sig-network-edge]`)
2. All Describe blocks have `[OTP]` tag
3. Tests with `[Level0]` don't have duplicate `-LEVEL0-` suffixes
4. Files using `testdata.FixturePath` have proper imports

**On validation failure:**

The migration stops and provides specific guidance on which files need fixing, preventing incomplete migrations.

## Resources

- [OTE Framework Enhancement](https://github.com/openshift/enhancements/pull/1676)
- [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension)
- [Example Implementation](https://github.com/openshift-eng/openshift-tests-extension/blob/main/cmd/example-tests/main.go)
