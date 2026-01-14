# OTE Migration Plugin

  Automated migration tools for integrating OpenShift component repositories with the openshift-tests-extension (OTE) framework.

  ## Overview

  This plugin automates the complete process of migrating OpenShift component repositories to use the OTE framework. The tool handles everything from repository setup to code generation with customizable destination paths.

  ## Commands

  ### `/ote-migration:migrate`

  Performs the complete OTE migration in one workflow.

  **What it does:**
  1. Collects user inputs - Extension name, directories, repository URLs
  2. Sets up repositories - Clones/updates source and target repositories
  3. Creates structure - Builds test/e2e and test/testdata directories
  4. Copies files - Moves test files and testdata to destinations
  5. Vendors dependencies - Automatically vendors Go dependencies
  6. Generates code - Creates go.mod, cmd/main.go, Makefile, fixtures.go
  7. Migrates tests - Automatically replaces FixturePath() calls and updates imports
  8. Provides validation - Gives comprehensive next steps and validation guide

  **Key Features:**
  - **Complete automation** - One command handles the entire migration
  - **Two directory strategies** - Monorepo (integrated) or single-module (isolated)
  - **Smart repository management** - Remote detection and update capabilities
  - **Dynamic dependency resolution** - Fetches latest Kubernetes and ginkgo versions from upstream
  - **Automatic Go toolchain management** - Uses `GOTOOLCHAIN=auto` to download required Go version
  - **Automatic test migration** - Replaces FixturePath() calls and updates imports
  - **Component-specific test filtering** - Generated main.go filters tests by `[sig-<extension-name>]` tag
  - **Test tracking annotations** - Automatically adds [OTP] and [Level0] tags to test cases
  - **Build verification** - Validates successful compilation before completion
  - **Git status validation** - Ensures clean working directory
  - **Auto-install go-bindata** - For generating embedded testdata
  - **Dockerfile integration** - Provides templates for both strategies

  ## Installation

  This plugin is available through the ai-helpers marketplace:

  ```bash
  /plugin marketplace add openshift-eng/ai-helpers
  /plugin install ote-migration@ai-helpers

  Usage

  /ote-migration:migrate

  Follow the prompts to provide:
  - Extension name (e.g., "sdn", "router", "storage")
  - Directory structure strategy (monorepo or single-module)
  - Working directory
  - Local openshift-tests-private path (optional)
  - Test subfolder under test/extended/
  - Testdata subfolder under test/extended/testdata/
  - Local target repository path (optional)
  - Target repository URL (if not using local)

  ## Directory Structure Strategies

  The migration tool supports two directory strategies to fit different repository layouts:

  ### Option 1: Monorepo Strategy (Recommended for Component Repositories)

  Integrates OTE into existing repository structure with **separate test module**.

  **Structure created:**
  ```
  <repo-root>/
  ├── cmd/
  │   └── extension/
  │       └── main.go                # OTE entry point
  ├── test/
  │   ├── e2e/
  │   │   ├── go.mod                 # Separate test module
  │   │   ├── go.sum
  │   │   └── *_test.go              # Test files
  │   ├── testdata/
  │   │   ├── bindata.go             # Generated
  │   │   └── fixtures.go
  │   └── bindata.mk
  ├── go.mod                         # Root module (with replace directive)
  └── Makefile                       # Extension target added
  ```

  **Key characteristics:**
  - **Separate test module**: `test/e2e/go.mod` is independent from root `go.mod`
  - **Replace directive**: Root `go.mod` includes `replace <module>/test/e2e => ./test/e2e`
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

  Creates isolated `tests-extension/` directory with **single go.mod**.

  **Structure created:**
  ```
  <working-dir>/
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

  The generated `cmd/main.go` (or `cmd/extension/main.go` for monorepo) includes **component-specific test filtering** using the `[sig-<extension-name>]` tag. This ensures only your component's tests are registered with the OTE framework.

  **Filter implementation:**
  ```go
  // Build test specs from Ginkgo
  allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
  if err != nil {
      panic(fmt.Sprintf("couldn't build extension test specs from ginkgo: %+v", err.Error()))
  }

  // Filter to only include component-specific tests (tests with [sig-<extension-name>] in name)
  var filteredSpecs []*et.ExtensionTestSpec
  allSpecs.Walk(func(spec *et.ExtensionTestSpec) {
      if strings.Contains(spec.Name, "[sig-<extension-name>]") {
          filteredSpecs = append(filteredSpecs, spec)
      }
  })
  specs := et.ExtensionTestSpecs(filteredSpecs)
  ```

  **Why this matters:**
  - Without this filter, you'd see **5,000+ upstream Kubernetes tests** in addition to your component tests
  - The filter ensures `./bin/<extension-name>-tests-ext list` shows only tests tagged with `[sig-<extension-name>]`
  - Tests must have the `[sig-<extension-name>]` tag in their name to be included

  **Verification after migration:**
  ```bash
  # Should show only component-specific tests with [sig-<extension-name>] tag
  ./bin/<extension-name>-tests-ext list

  # Count filtered tests
  ./bin/<extension-name>-tests-ext list | grep -c "\[sig-<extension-name>\]"
  ```

  ### Test Tracking Annotations

  The migration **automatically modifies test files** to add tracking annotations. This happens in Phase 6 (Test Migration) and restructures test names for better organization.

  **Automatic annotations added:**

  1. **[OTP]** - Added to ALL Describe blocks
     - Marks all tests ported from openshift-tests-private
     - Helps track migration progress
     - Placement: After `[sig-<extension-name>]` in Describe blocks
     - Example: `g.Describe("[sig-router][OTP]", func() { ... })`

  2. **[Level0]** - Added to individual It() test cases with "-LEVEL0-" in name
     - Identifies level0 conformance tests
     - Auto-detected by searching for "-LEVEL0-" string in It() descriptions
     - Placement: At the beginning of It() descriptions
     - Example: `g.It("[Level0] Router should handle basic routing", func() { ... })`

  **Test restructuring performed:**

  The migration simplifies test structure by:
  - Moving Describe block text into It() descriptions
  - Simplifying Describe to just tags: `[sig-<extension-name>][OTP]`
  - Prepending `[Level0]` to It() for tests with "-LEVEL0-"

  **Before migration:**
  ```go
  g.Describe("[sig-router] Router functionality", func() {
      g.It("should handle basic routing -LEVEL0-", func() {
          // test code
      })
  })
  ```

  **After migration:**
  ```go
  g.Describe("[sig-router][OTP]", func() {
      g.It("[Level0] Router functionality should handle basic routing -LEVEL0-", func() {
          // test code
      })
  })
  ```

  **Full test name visible in list:**
  ```
  [sig-router][OTP] [Level0] Router functionality should handle basic routing -LEVEL0-
  ```

  **Benefits:**
  - **Track migration progress** - Count tests with `[OTP]` tag
  - **Identify level0 tests** - Filter by `[Level0]` tag
  - **Cleaner test hierarchy** - Describe blocks use tags only
  - **Flexibility for test execution** - Run level0 tests separately or in conformance suites

  **Verification after migration:**
  ```bash
  # Count total ported tests (all should have [OTP])
  ./bin/<extension-name>-tests-ext list | grep -c "\[OTP\]"

  # Count level0 conformance tests
  ./bin/<extension-name>-tests-ext list | grep -c "\[Level0\]"

  # View restructured test names
  ./bin/<extension-name>-tests-ext list | head -10
  ```

  ### Dynamic Dependency Resolution

  The migration tool **fetches latest versions** of critical dependencies directly from upstream repositories instead of copying potentially stale versions from openshift-tests-private.

  **What's fetched dynamically:**

  1. **Kubernetes dependencies** - From `github.com/openshift/kubernetes` (master branch)
     ```bash
     K8S_LATEST=$(git ls-remote https://github.com/openshift/kubernetes.git refs/heads/master | awk '{print $1}')
     # Creates versioned replace directives for all k8s.io/* packages
     ```

  2. **Ginkgo testing framework** - From `github.com/openshift/onsi-ginkgo` (v2.27.2-openshift-4.22 branch)
     ```bash
     GINKGO_LATEST=$(git ls-remote https://github.com/openshift/onsi-ginkgo.git refs/heads/v2.27.2-openshift-4.22 | awk '{print $1}')
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
  - Generates fresh pseudo-versions
  - Ensures compatibility with current OpenShift ecosystem

  ### Automatic Go Toolchain Management

  The migration uses `GOTOOLCHAIN=auto` and `GOSUMDB=sum.golang.org` to automatically download required Go versions.

  **What this solves:**

  If dependencies require Go 1.24.6 but you have Go 1.24.3 installed:

  ```bash
  # Without GOTOOLCHAIN=auto (fails):
  go: go.mod requires go >= 1.24.6 (running go 1.24.3; GOTOOLCHAIN=local)

  # With GOTOOLCHAIN=auto (succeeds):
  # Automatically downloads and uses go1.24.11
  ```

  **How it works:**
  - Your system Go: 1.24.3
  - Dependencies require: 1.24.6+
  - `GOTOOLCHAIN=auto` downloads: 1.24.11 (from go.mod's toolchain directive)
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

  ## Resources

  - [OTE Framework Enhancement](https://github.com/openshift/enhancements/pull/1676)
  - [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension)
  - [Example Implementation](https://github.com/openshift-eng/openshift-tests-extension/blob/main/cmd/example-tests/main.go)
