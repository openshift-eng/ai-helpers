# Test Extension Binaries Reference

Covers OpenShift test extension binaries (OTE): discovery and invocation by `openshift-tests`,
build and packaging in CI images, and how their failures surface in artifacts. Use this when a
test failure originates from an extension binary rather than the core `openshift-tests` binary.

## When to Use

- A test failure comes from a component-owned extension binary (not origin's own tests)
- Extension binary extraction or discovery fails during CI job startup
- Tests that should run are missing or not being registered
- Extension binary crashes, panics, or produces protocol errors
- Build failures result in missing or broken extension binaries in payload images
- Need to understand the relationship between extension binaries and `openshift-tests`

---

## What Are Test Extension Binaries?

Standalone executables implementing the **openshift-tests-extension (OTE) protocol**. They let
component teams ship their own e2e tests alongside their component images in the release payload,
without merging test code into `openshift/origin`.

### The Extension Model

Traditionally, all OpenShift e2e tests lived in `openshift/origin`, compiled into a single
`openshift-tests` binary. The extension model decentralizes this:

| Aspect | Traditional (origin) | Extension Binary |
|--------|---------------------|-----------------|
| **Test code lives in** | `openshift/origin` | Component repo (e.g., `openshift/cluster-etcd-operator`) |
| **Binary name** | `openshift-tests` | `<component>-tests-ext` (e.g., `cluster-etcd-operator-tests-ext`) |
| **Shipped in image** | `tests` payload image | Component's own payload image |
| **Test registration** | Compiled into binary | Discovered at runtime via OTE protocol |
| **Ownership** | Origin / TRT team | Component team |

### Standard vs Extension Tests

**Standard tests** (origin-native):
- Compiled directly into `openshift-tests`
- Registered via Ginkgo `Describe`/`It` blocks at import time
- Always present — no extraction or discovery needed

**Extension tests**:
- Live in separate binaries shipped inside payload images
- Must be extracted from images and discovered at runtime
- Communicate with `openshift-tests` via a JSON-based protocol over stdout
- Can fail at multiple stages: extraction, discovery, registration, or execution

---

## The OTE Protocol

A command-line protocol that `openshift-tests` (origin) uses to discover and run tests, defined by
the [openshift-tests-extension](https://github.com/openshift-eng/openshift-tests-extension) framework.

### Protocol Commands

Every extension binary must support these subcommands:

#### `info` — Report extension metadata

```bash
<binary> info
```

Returns a JSON object describing the extension:
```json
{
  "apiVersion": "v1.1",
  "source": {
    "commit": "abc123...",
    "build_date": "2026-01-15T10:30:00Z",
    "git_tree_state": "clean",
    "source_url": "https://github.com/openshift/cluster-etcd-operator"
  },
  "component": {
    "product": "openshift",
    "type": "payload",
    "name": "cluster-etcd-operator"
  }
}
```

- Timeout: 10 minutes
- Errors here prevent the binary from being used at all

#### `list` — Enumerate available tests

```bash
<binary> list -o jsonl [--env-flag=VALUE...]
```

Returns one JSON object per line (JSONL format), each describing a test:
```jsonl
{"name":"[sig-etcd] etcd should start successfully","lifecycle":"blocking","labels":["sig-etcd"],"codeLocations":["/path/to/test.go:42"]}
{"name":"[sig-etcd] etcd leader election","lifecycle":"informing","labels":["sig-etcd"],"codeLocations":["/path/to/test.go:87"]}
```

- Timeout: 10 minutes
- Lines not starting with `{` are silently skipped (allows stderr/debug output)
- Environment flags are passed to let the binary determine platform-specific tests

#### `run-test` — Execute specific tests

```bash
<binary> run-test -n "test name 1" -n "test name 2" -o jsonl
```

Returns JSONL results at the **end** of stdout:
```jsonl
{"name":"[sig-etcd] etcd should start successfully","lifecycle":"blocking","result":"passed","duration":12500000000,"output":"..."}
{"name":"[sig-etcd] etcd leader election","lifecycle":"blocking","result":"failed","duration":45200000000,"error":"Error: ...","output":"..."}
```

`result` is one of `passed`/`failed`/`skipped`; `duration` is an int64 in **nanoseconds**
(12.5s = `12500000000`), not a string.

- Results are parsed **backwards** from end of output to avoid stray JSON from logs
- Exit code is ignored (non-zero is expected when tests fail)
- `EXTENSION_ARTIFACT_DIR` environment variable tells the binary where to write artifacts

#### `images` — List required test images (optional)

```bash
<binary> images
```

Returns JSON describing container images the tests need.

### JSON Extraction

Origin's parser (`extractJSON`) is tolerant of non-JSON output before the actual JSON payload.
It scans stdout line-by-line looking for the first line that starts with `{` or `[`. This means
extension binaries can emit log lines to stdout before the JSON — but they must not emit
invalid JSON that looks like it starts a JSON object.

---

## Extension Binary Lifecycle in CI

### How Extension Binaries Are Built

Built in each component's CI pipeline via a Dockerfile multi-stage build. Typical pattern:

```dockerfile
# Build stage for test extension
FROM registry.ci.openshift.org/ocp/builder:rhel-9-golang-1.25-openshift-4.22 AS test-extension-builder
RUN mkdir -p /go/src/github.com/openshift/<component>
WORKDIR /go/src/github.com/openshift/<component>
COPY . .
RUN make tests-ext-build && \
    cd bin && \
    tar -czvf <component>-test-extension.tar.gz <component>-tests-ext && \
    rm -f <component>-tests-ext

# Final image (component's operator image)
FROM ...
COPY --from=test-extension-builder /go/src/github.com/openshift/<component>/bin/<component>-test-extension.tar.gz /usr/bin/
```

The extension binary is:
1. Compiled from Go source using the OTE framework
2. Compressed with gzip (`.gz` suffix in the registry)
3. Placed at a well-known path inside the component's payload image (typically `/usr/bin/`)

### Image Layering

Extension binaries live **inside the component's own release payload image**, not in the
`tests` image. For example:

| Extension Binary | Payload Image Tag | Binary Path in Image |
|-----------------|-------------------|---------------------|
| `cluster-etcd-operator-tests-ext` | `cluster-etcd-operator` | `/usr/bin/cluster-etcd-operator-tests-ext.gz` |
| `machine-config-tests-ext` | `machine-config-operator` | `/usr/bin/machine-config-tests-ext.gz` |
| `ovn-kubernetes-tests-ext` | `ovn-kubernetes` | `/usr/bin/ovn-kubernetes-tests-ext.gz` |
| `k8s-tests-ext` | `hyperkube` | `/usr/bin/k8s-tests-ext.gz` |
| `oc-tests-ext` | `cli` | `/usr/bin/oc-tests-ext.gz` |
| `olmv1-tests-ext` | `olm-operator-controller` | `/usr/bin/olmv1-tests-ext.gz` |

### The Extension Binary Registry

Origin maintains a **hardcoded registry** of known extension binaries in
`pkg/test/extensions/binary.go`, mapping each payload image tag to the binary path within it:

```go
var extensionBinaries = []TestBinary{
    // Self reference for origin's own internal extension
    {imageTag: "tests", binaryPath: os.Args[0]},

    // Extensions in other payload images
    {imageTag: "aws-machine-controllers", binaryPath: "/machine-api-provider-aws-tests-ext.gz"},
    {imageTag: "cli", binaryPath: "/usr/bin/oc-tests-ext.gz"},
    {imageTag: "cluster-etcd-operator", binaryPath: "/usr/bin/cluster-etcd-operator-tests-ext.gz"},
    {imageTag: "cluster-ingress-operator", binaryPath: "/usr/bin/cluster-ingress-operator-tests-ext.gz"},
    {imageTag: "machine-config-operator", binaryPath: "/usr/bin/machine-config-tests-ext.gz"},
    {imageTag: "ovn-kubernetes", binaryPath: "/usr/bin/ovn-kubernetes-tests-ext.gz"},
    // ... 30+ more entries
}
```

**Important**: A new extension binary must be **registered** in origin's `extensionBinaries`
list to be discovered. Without registration, the binary ships in the image but is never used.

### Non-Payload Extension Discovery

Origin also supports **non-payload extensions** — test binaries in images outside the release
payload, discovered dynamically via ImageStreamTag annotations in the cluster:

1. Origin checks for `TestExtensionAdmission` CRDs that define permitted patterns
2. It scans ImageStreamTags across namespaces for `ComponentAnnotation`
3. Permitted extensions are extracted and run alongside payload extensions
4. Unpermitted extensions generate synthetic skip tests

### Extraction Process (`ExtractAllTestBinaries`)

When `openshift-tests` starts a test run, it extracts all extension binaries:

1. **Filter by tags**: Apply `EXTENSION_BINARY_OVERRIDE_INCLUDE_TAGS` /
   `EXTENSION_BINARY_OVERRIDE_EXCLUDE_TAGS` environment variables
2. **Determine release image**: Find the payload image from `RELEASE_IMAGE_LATEST` or cluster
3. **Create temp directory**: `/tmp/external-binary-*` for extracted binaries
4. **Extract in parallel**: Use `oc image extract` to pull each binary from its payload image
   - Self-reference (`tests` image) is skipped — origin is already running
   - Binaries are decompressed from `.gz` format
   - Made executable
5. **Discover non-payload extensions**: Scan ImageStreamTags for permitted extensions
6. **Return all binaries**: Both payload and non-payload extensions

### Environment Variable Controls

| Variable | Purpose |
|----------|---------|
| `OPENSHIFT_SKIP_EXTERNAL_TESTS` | If set, skip ALL external extension binaries (use only origin's built-in tests) |
| `EXTENSION_BINARY_OVERRIDE_INCLUDE_TAGS` | Comma-separated image tags — use ONLY these extensions |
| `EXTENSION_BINARY_OVERRIDE_EXCLUDE_TAGS` | Comma-separated image tags — exclude these extensions |
| `EXTENSION_ARTIFACT_DIR` | Set per-extension — where the binary should write its test artifacts |
| `ARTIFACT_DIR` | Base artifact directory for the CI job |
| `TEST_PROVIDER` | Cluster provider config (passed to extensions via environment flags) |
| `TEST_JUNIT_DIR` | Where JUnit XML results should be written |

---

## Common Extension Binary Failure Patterns

### 1. Binary Not Found / Missing from Image

**Symptoms:**
```text
failed to extract binary from image: file not found: /usr/bin/cluster-foo-operator-tests-ext.gz
```
or
```text
encountered errors while extracting binaries: couldn't extract /usr/bin/component-tests-ext.gz from image ...
```

**Causes:**
- Component repo's Dockerfile doesn't include the test extension build stage
- Binary path in the registry doesn't match the actual path in the image
- Image build failed silently — the extension stage compiled but didn't copy the artifact
- Image was built from a branch that doesn't have the OTE integration yet

**Diagnosis:**
```bash
# Check if the binary exists in the payload image
oc image extract <image-ref> --path /usr/bin/:<output-dir> --confirm
ls -la <output-dir>/*tests-ext*

# Check the Dockerfile in the component repo for test extension stages
grep -n "test-extension\|tests-ext" Dockerfile*
```

### 2. Binary Fails to Execute

**Symptoms:**
```text
failed running '<binary> info': exec: "<binary>": permission denied
failed running '<binary> info': exec format error
failed running '<binary> info': no such file or directory (dynamic linker)
```

**Causes:**
- Binary not marked executable after extraction
- Architecture mismatch (e.g., binary built for amd64, running on arm64)
- Dynamic linking failure — binary depends on shared libraries not in the test pod
- Corrupted binary (incomplete download or extraction)
- Binary was gzipped but path in registry doesn't have `.gz` suffix (or vice versa)

**Diagnosis:**
```bash
# Check binary properties
file <binary-path>
ldd <binary-path>  # Check dynamic linking
chmod +x <binary-path> && ./<binary-path> info  # Test execution
```

### 3. Binary Starts but Fails to Register Tests (Protocol Errors)

**Symptoms:**
```text
no valid JSON found in output from '<binary> info' command
couldn't unmarshal extension info from <binary>: ...
failed running '<binary> list': ...
```
or
```text
no valid JSON found in output: <garbled output here>
```

**Causes:**
- Binary writes non-JSON to stdout before the JSON payload and it starts with `{` or `[`
- Binary crashes during `info` or `list` with a panic that precedes JSON output
- Binary built with incompatible OTE framework version (API version mismatch)
- Binary requires cluster connectivity for `list` but cluster is unavailable at that point
- Initialization code (e.g., `framework.AfterReadingAllFlags(&framework.TestContext)`) was never
  called before the binary emitted output, leaving test context unpopulated

**Diagnosis:**
```bash
# Run the binary manually to see raw output
./<binary> info 2>&1
./<binary> list -o jsonl 2>&1 | head -20

# Check API version compatibility
./<binary> info 2>&1 | jq .apiVersion
```

**Build log patterns:**
```text
Raw output from <binary>: panic: runtime error: invalid memory address or nil pointer dereference
No valid JSON found in output from <binary> info command
```

### 4. Binary Registers Tests but They Don't Run

**Symptoms:**
- Extension binary extracts and lists tests successfully
- But tests are absent from JUnit results
- Test count in build log shows 0 tests selected from extension

**Causes:**
- Test suite filtering (`--suite`) excludes extension tests
- Environment flags cause extension to report 0 applicable tests
- Test names don't match selection regex
- Extension tests are all set to `LifecycleInforming` and the suite only runs blocking tests
- Extension binary's `list` command returned tests, but none matched the current environment

**Diagnosis:**
```bash
# Check what tests the extension advertises
./<binary> list -o jsonl | wc -l
./<binary> list -o jsonl | jq -r '.name' | head -20

# Check test lifecycle
./<binary> list -o jsonl | jq -r '.lifecycle' | sort | uniq -c
```

### 5. Extension Binary Panics During Test Execution

**Symptoms in build log:**
```text
panic: runtime error: invalid memory address or nil pointer dereference
goroutine 1 [running]:
github.com/openshift/cluster-foo-operator/test/e2e.TestSomething(...)
    /go/src/github.com/openshift/cluster-foo-operator/test/e2e/test.go:42 +0x1a4
```

**Common panic causes:**
- Missing `framework.AfterReadingAllFlags(&framework.TestContext)` initialization
- Missing `util.WithCleanup()` in BeforeAll (leaves `testsStarted = false`)
- Nil kubeconfig or missing KUBECONFIG environment variable
- Test expects cluster resources that don't exist in the test environment
- OTE framework version mismatch — binary built with old framework, run by new origin

**Diagnosis:**
- Look for `panic:` in the step-level build log
- Get the full goroutine dump — the crashing function and file:line
- Check if the component's `cmd/extension/main.go` has proper initialization

### 6. Extension Binary Timeout Issues

**Symptoms:**
```text
context deadline exceeded
signal: killed
```

**Causes:**
- `info` command: Timeout is 10 minutes — binary hangs during initialization
- `list` command: Timeout is 10 minutes — binary attempts cluster operations during listing
- `run-test` command: Timeout matches the test timeout — test itself runs too long
- Binary enters an infinite loop or deadlock

**Diagnosis:**
- Check build log for timing — did the binary run for the full timeout period?
- Check if the binary requires cluster access for `info`/`list` (it shouldn't)

---

## How Extension Binary Failures Appear in Artifacts

### JUnit XML Output

Extension test results appear in JUnit XML alongside standard tests:

**Standard test in JUnit:**
```xml
<testcase name="[sig-apps] Deployment should run the lifecycle of a Deployment"
          classname="openshift-tests" time="45.2">
</testcase>
```

**Extension test in JUnit:**
```xml
<testcase name="[sig-etcd] etcd cluster should be healthy"
          classname="openshift-tests" time="12.8">
</testcase>
```

Both appear under `classname="openshift-tests"` because origin orchestrates all test execution.
To identify which binary owned a test, check the test name prefix (e.g., `[sig-etcd]`) or the
build log's binary-to-test mapping.

**Extension binary extraction failure in JUnit:**

When an extension binary fails to extract or initialize, origin may generate a **synthetic
test failure**:
```xml
<testcase name="[sig-trt] extension binary cluster-etcd-operator-tests-ext should load successfully"
          classname="openshift-tests" time="0">
  <failure message="failed to extract binary from image: ...">
    encountered errors while extracting binaries: couldn't extract /usr/bin/cluster-etcd-operator-tests-ext.gz
  </failure>
</testcase>
```

**Unpermitted non-payload extension in JUnit:**
```xml
<testcase name="[sig-trt] unpermitted extension ns/imagestream:tag should be permitted"
          classname="openshift-tests" time="0">
  <skipped message="extension binary not permitted by TestExtensionAdmission"/>
</testcase>
```

### Build-Log Patterns

#### Successful extension loading:
```text
level=info msg="Fetching info for cluster-etcd-operator-tests-ext.gz"
level=info msg="Fetched info for cluster-etcd-operator-tests-ext.gz in 2.1s"
level=info msg="Listing tests" binary=cluster-etcd-operator-tests-ext.gz
level=info msg="OTE API version is: v1.1" binary=cluster-etcd-operator-tests-ext.gz
level=info msg="Listed 42 tests in 3.5s" binary=cluster-etcd-operator-tests-ext.gz
```

#### Extension binary extraction failure:
```text
level=error msg="Failed to extract binary from image tag 'cluster-foo-operator': file not found"
encountered errors while extracting binaries: couldn't extract /usr/bin/cluster-foo-operator-tests-ext.gz from image
```

#### Extension binary info/protocol failure:
```text
level=error msg="Failed to fetch info for cluster-foo-operator-tests-ext.gz: exit status 1"
level=error msg="Command output for cluster-foo-operator-tests-ext.gz: panic: runtime error: ..."
level=error msg="No valid JSON found in output from cluster-foo-operator-tests-ext.gz info command"
level=error msg="Raw output from cluster-foo-operator-tests-ext.gz: <garbled output>"
```

#### Extension binary list failure:
```text
failed running 'cluster-foo-operator-tests-ext.gz list': exit status 2
Output: Error: unable to load kubeconfig: ...
```

#### Skipping external tests:
```text
level=warning msg="Using built-in tests only due to OPENSHIFT_SKIP_EXTERNAL_TESTS being set"
```

#### Tag filtering:
```text
level=info msg="Including extension binary with image tag: cluster-etcd-operator"
level=info msg="Excluding extension binary with image tag: ovn-kubernetes (not in include list)"
```

### How to Distinguish "Extension Binary Broken" from "Test Actually Failed"

| Signal | Extension Binary Issue | Test Actually Failed |
|--------|----------------------|---------------------|
| Error during `info` or `list` | ✅ Binary is broken | ❌ |
| Panic before test output | ✅ Binary initialization failed | ❌ |
| Test runs and produces pass/fail result | ❌ | ✅ Test logic failed |
| "no valid JSON found" in build log | ✅ Protocol error | ❌ |
| Extension not found in JUnit at all | ✅ Extraction failed | ❌ |
| Test listed but never ran | ⚠️ Possibly filtering issue | ⚠️ Possibly skipped |
| Test ran and produced failure message | ❌ | ✅ Check the failure |

---

## Debugging Workflow

### Step 1: Check if the Extension Binary Exists in the Test Image

```bash
# Find the binary's image tag in origin's registry
# (see the Known Extension Binary Implementations table below)

# Extract and check the payload image contents
oc adm release info <release-image> --image-for=<image-tag>
oc image extract <image-ref> --path /usr/bin/:<output-dir> --confirm
ls -la <output-dir>/*tests-ext*
```

**In CI artifacts**: Look at the build-log.txt for extraction messages:
```bash
# Search build log for extension extraction
grep -i "extract\|extension\|tests-ext" build-log.txt
```

### Step 2: Check if it Was Discovered/Loaded

Search the build log for the binary name:
```bash
grep "<binary-name>" build-log.txt
# e.g., grep "cluster-etcd-operator-tests-ext" build-log.txt
```

Expected success pattern:
```text
Fetching info for <binary>.gz
Fetched info for <binary>.gz in Xs
```

Failure pattern:
```text
Failed to fetch info for <binary>.gz: ...
Failed to extract binary from image tag '<tag>': ...
```

### Step 3: Check if Tests Were Registered

```bash
grep "Listed.*tests" build-log.txt
# Expected: "Listed 42 tests in 3.5s"
# Problem:  "Listed 0 tests in 0.1s" or absence of this line
```

If tests were registered, they'll appear in the test selection output:
```bash
grep "Found.*test specs" build-log.txt
```

### Step 4: Check Test Execution Output

Look at the step-level build log for the test step (e.g., `openshift-e2e-test`):
```bash
# Download the step build log
gcloud storage cp \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/openshift-e2e-test/build-log.txt" \
  ./step-build-log.txt --no-user-output-enabled

# Search for extension test output
grep -A5 "run-test\|RunTests" step-build-log.txt
```

### Step 5: Check for Infrastructure vs Test Issues

Determine whether the failure is:

1. **Infrastructure** — binary missing, extraction failed, protocol error
   - Fix: Check the component's Dockerfile, rebuild, or update origin's registry
2. **Framework initialization** — panic during setup, missing config
   - Fix: Check `cmd/extension/main.go` initialization code
3. **Test logic** — test ran but assertion failed
   - Fix: Investigate the test code and cluster state (normal test debugging)
4. **Environment mismatch** — tests not applicable to this platform
   - Fix: Check environment flags and test filtering logic

---

## Extension Binary Naming — Pattern and Exceptions

Most binaries follow **`<image-tag>` → `/usr/bin/<component>-tests-ext.gz`**. Don't rely on a
memorized list — the registry (`extensionBinaries` in `pkg/test/extensions/binary.go`, see
[The Extension Binary Registry](#the-extension-binary-registry) above) grows as components are
added. Read the current list straight from origin:

```bash
curl -s https://raw.githubusercontent.com/openshift/origin/master/pkg/test/extensions/binary.go \
  | grep -oE '(imageTag|binaryPath): "[^"]*"'
```

**Watch for these naming exceptions** — they break the `-tests-ext.gz` convention, so a
pattern-based guess of the binary path will be wrong:

| Image Tag | Binary Path | Deviation |
|-----------|-------------|-----------|
| `cluster-node-tuning-operator` | `/usr/bin/cluster-node-tuning-operator-test-ext.gz` | `-test-ext` (singular) |
| `cluster-control-plane-machine-set-operator` | `/cluster-control-plane-machine-set-operator-ext.gz` | `-ext.gz`, no `/usr/bin` |
| `cluster-version-operator` | `/usr/bin/cluster-version-operator-tests.gz` | `-tests.gz`, no `-ext` |
| `machine-api-operator` | `/machine-api-tests-ext.gz` | no `/usr/bin` prefix |
| `aws-machine-controllers` | `/machine-api-provider-aws-tests-ext.gz` | binary name ≠ image tag |
| `hyperkube` | `/usr/bin/k8s-tests-ext.gz` | upstream Kubernetes |

An image can ship **two** binaries (e.g. `cluster-cloud-controller-manager-operator` has both
a generic and an AWS binary) — expect a tag to appear more than once in the registry.

---

## Packaging and Build Issues

### Build Steps and Entry Point

Extension binaries are built from their component repos using the OTE framework:

1. **Source code**: Test files live in `test/e2e/` within the component repo
2. **Entry point**: `cmd/extension/main.go` initializes the OTE framework
3. **Build**: `make tests-ext-build` compiles the binary to `bin/<name>-tests-ext`
4. **Package**: Dockerfile compresses and copies into the component image

#### Typical `main.go` structure:
```go
package main

import (
    g "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"
    et "github.com/openshift-eng/openshift-tests-extension/pkg/extension/extensiontests"
    // Import test packages to register Ginkgo tests
    _ "github.com/openshift/<component>/test/e2e"
)

func main() {
    // Build test specs from Ginkgo suite
    allSpecs, err := g.BuildExtensionTestSpecsFromOpenShiftGinkgoSuite()
    
    // Filter to only local tests (exclude vendored tests)
    componentSpecs := allSpecs.Select(func(spec *et.ExtensionTestSpec) bool {
        for _, loc := range spec.CodeLocations {
            if strings.Contains(loc, "/test/e2e/") &&
               !strings.Contains(loc, "/go/pkg/mod/") &&
               !strings.Contains(loc, "/vendor/") {
                return true
            }
        }
        return false
    })

    // Set lifecycle (informing = won't block CI)
    componentSpecs.Walk(func(spec *et.ExtensionTestSpec) {
        spec.Lifecycle = et.LifecycleInforming
    })

    ext.AddSpecs(componentSpecs)
    // ... register with extension framework and serve
}
```

### Version Skew Between Extension Binaries and openshift-tests

Version skew across the OTE protocol can cause issues:

| Issue | Symptom | Resolution |
|-------|---------|------------|
| Extension uses newer API version | Origin filters out unsupported env flags | Update origin |
| Extension uses older API version | Missing required fields in JSON | Rebuild extension with newer OTE framework |
| OTE framework mismatch | `undefined: ginkgo.NewWriter` build errors | Align Ginkgo version with OTE framework |
| Go version mismatch | Build fails in Dockerfile | Use matching builder image version |

**API version compatibility**: Origin's `filterToApplicableEnvironmentFlags` checks the
extension's reported `apiVersion` and only passes environment flags that the extension's
version supports. This provides forward compatibility — newer origin versions won't break
older extensions with flags they don't understand.

### Build Failures That Result in Missing/Broken Extensions

1. **Go dependency conflicts**:
   ```text
   undefined: otelgrpc.UnaryClientInterceptor
   cannot use v6 as net.IP
   ```
   Fix: Update Go dependencies, especially `openshift/kubernetes` fork

2. **Missing Ginkgo APIs**:
   ```text
   undefined: ginkgo.NewWriter
   spec.Labels undefined
   ```
   Fix: Update Ginkgo to the version aligned with OTE framework
   (v2.27.2-openshift-4.22 branch of `openshift/onsi-ginkgo`)

3. **Go version too old for dependencies**:
   ```text
   go: go.mod requires go >= 1.25.0 (running go 1.23; GOTOOLCHAIN=local)
   ```
   Fix: Use `GOTOOLCHAIN=auto` or update builder image

4. **k8s.io/kms requires newer Go**:
   ```text
   k8s.io/kms requires go >= 1.25.0
   ```
   Fix: Add k8s.io/kms replace directive to use OpenShift fork

5. **Test filtering not working — 1000+ tests registered**:
   ```text
   Found 1247 test specs  (expected ~50)
   ```
   Fix: Check `main.go` filesystem path filtering — ensure it excludes
   `/go/pkg/mod/` and `/vendor/` paths

---

## Test Selection with Extensions

### How Suite and Name Filtering Interact with Extensions

After discovery, extension tests are integrated into origin's test selection:

1. **All extension binaries list their tests** via the `list` command
2. **Origin merges** all extension tests with its own built-in tests
3. **Suite selection** (`--suite openshift/conformance/parallel`) filters the combined set
4. **Name matching** (`--run "etcd"`) further filters by test name regex
5. **Environment selectors** exclude tests not applicable to the current platform

Extension binaries can define their own suites:
```text
<component>/conformance/parallel
<component>/conformance/serial
<component>/disruptive
<component>/all
```

These suite names are prefixed with the component name to avoid collisions.

### How Extension Tests Are Named and Categorized

Extension tests follow standard OpenShift test naming conventions:

```text
[sig-<sig>] <description> [<labels>]
```

Examples:
```text
[sig-etcd] etcd cluster health should be recoverable [Disruptive]
[sig-network] OVN pods should be running [Serial]
[sig-auth] OAuth server tokens should be refreshed
```

Labels that affect categorization:
- `[Serial]` — must run sequentially, not in parallel
- `[Disruptive]` — may affect cluster state, run in isolation
- `[Skipped:...]` — conditions under which the test is skipped
- `[Level0]` — conformance test (used by OTE-migrated tests)
- `[OTP]` — test ported from openshift-tests-private (tracking marker)

### How to Run Only Extension Tests or Exclude Them

**Run only specific extension's tests:**
```bash
# Set environment to include only one extension
export EXTENSION_BINARY_OVERRIDE_INCLUDE_TAGS=cluster-etcd-operator
openshift-tests run ...
```

**Exclude specific extensions:**
```bash
# Exclude a known-broken extension
export EXTENSION_BINARY_OVERRIDE_EXCLUDE_TAGS=cluster-foo-operator,ovn-kubernetes
openshift-tests run ...
```

**Skip all external extensions:**
```bash
# Run only origin's built-in tests
export OPENSHIFT_SKIP_EXTERNAL_TESTS=1
openshift-tests run ...
```

---

## Artifact Locations for Extension Tests

Stored under a component-specific subdirectory:

```text
$ARTIFACT_DIR/<product>/<kind>/<name>/
```

For example:
```text
artifacts/e2e-aws/openshift-e2e-test/artifacts/openshift/payload/cluster-etcd-operator/
artifacts/e2e-aws/openshift-e2e-test/artifacts/openshift/payload/ovn-kubernetes/
```

Each extension's artifact directory contains:
- JUnit XML results (if the extension writes them)
- Custom artifacts (logs, dumps, screenshots)
- Whatever the extension binary chooses to write to `EXTENSION_ARTIFACT_DIR`

---

## Cross-References

- [CI Infrastructure Changes](ci-infrastructure-changes.md) — CI step script and infrastructure
  analysis, including changes to ci-operator and Prow test infrastructure
- [Aggregated Jobs](aggregated.md) — Statistical test analysis across multiple runs, including
  extension test result aggregation
- [Artifacts Reference](artifacts.md) — Complete artifact directory structure
- [OTE Framework Repository](https://github.com/openshift-eng/openshift-tests-extension) —
  Source code for the extension framework
- [OTE Migration Plugin](../../../../ote-migration/README.md) — Automated migration tool for
  adding OTE support to component repos
- Origin extension registry: `openshift/origin` → `pkg/test/extensions/binary.go`
