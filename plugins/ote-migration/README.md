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
- **No sig filtering** - All tests included without filtering logic
- **Automatic replace directive propagation (monorepo)** - Copies k8s.io/* and upstream replace directives from test module to root go.mod
- **Vendor at root only (monorepo)** - Vendored dependencies only at repository root, not in test module
- **Custom test directory support** - Handles existing test/e2e directories with configurable alternatives
- **Dynamic git remote discovery** - No assumptions about remote names (no hardcoded 'origin')
- **Smart repository management** - Remote detection and update capabilities
- **Dynamic dependency resolution** - Fetches latest dependencies from upstream
- **Automatic Go toolchain management** - Uses `GOTOOLCHAIN=auto` to download required Go version
- **Automatic test migration** - Replaces FixturePath() calls, updates imports, and adds annotations atomically with rollback
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
- **Automatic upstream replace directives**: k8s.io/* and other replace directives are automatically copied from test module go.mod to root go.mod
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
docker build -t test-image:latest .

# Verify binary exists in image
docker run --rm test-image:latest ls -lh /usr/bin/*-test-extension.tar.gz

# Extract and test binary
docker run --rm test-image:latest cat /usr/bin/<extension-name>-test-extension.tar.gz | tar -xzv
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

## Resources

- [OTE Framework Enhancement](https://github.com/openshift/enhancements/pull/1676)
- [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension)
- [Example Implementation](https://github.com/openshift-eng/openshift-tests-extension/blob/main/cmd/example-tests/main.go)
- [Complete Design Document](../../OTE_PLUGIN_COMPLETE_DESIGN.md) - Comprehensive technical documentation with detailed directory structures, complete Dockerfile examples, and troubleshooting guides for both monorepo and single-module strategies
