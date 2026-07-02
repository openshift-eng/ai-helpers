# CI Infrastructure Changes Reference

How CI infrastructure changes cause job failures, and how to distinguish "the product broke"
from "someone changed the CI configuration." Covers the layers between a developer's code
change and the test result.

---

## Table of Contents

1. [When to Use This Reference](#when-to-use-this-reference)
2. [The `openshift/release` Repo](#the-openshiftrelease-repo)
3. [ci-operator — The Test Orchestrator](#ci-operator--the-test-orchestrator)
4. [Step Registry Deep Dive](#step-registry-deep-dive)
5. [Distinguishing CI Infrastructure vs Product Failures](#distinguishing-ci-infrastructure-vs-product-failures)
6. [How to Check for Recent CI Infrastructure Changes](#how-to-check-for-recent-ci-infrastructure-changes)
7. [Image Promotion and Registry Interactions](#image-promotion-and-registry-interactions)
8. [CI Job Lifecycle Phases](#ci-job-lifecycle-phases)
9. [Detecting CI Infrastructure Failures — Practical Steps](#detecting-ci-infrastructure-failures--practical-steps)
10. [Environment Variables and Overrides](#environment-variables-and-overrides)
11. [Artifact Directory Structure Reference](#artifact-directory-structure-reference)
12. [See Also](#see-also)

---

## When to Use This Reference

- Job fails before any product code runs (lease acquisition, image build, etc.)
- ci-operator itself crashes or reports internal errors
- Cluster lease or cloud quota issues prevent the job from starting
- Test infrastructure components (Prow, ci-operator, step registry) malfunction
- A new failure correlates with a recent `openshift/release` PR rather than a product PR
- The same failure appears across multiple unrelated repos or jobs simultaneously
- A job that was passing starts failing with no product code changes

---

## The `openshift/release` Repo

[`openshift/release`](https://github.com/openshift/release) is the single source of truth for
OpenShift CI job configuration. Every CI job — presubmit, postsubmit, periodic — is defined or
generated from config files here. Changes can cause widespread job failures with no product
code changes.

### Repo Structure

```text
openshift/release/
├── ci-operator/
│   ├── config/                    # Per-repo CI configuration
│   │   └── openshift/             # Organization level
│   │       └── installer/         # Repository level
│   │           ├── openshift-installer-master.yaml
│   │           ├── openshift-installer-release-4.18.yaml
│   │           └── ...
│   ├── jobs/                      # Generated Prow job definitions (do NOT edit directly)
│   │   ├── openshift/
│   │   │   └── installer/
│   │   │       ├── openshift-installer-master-presubmits.yaml
│   │   │       ├── openshift-installer-master-postsubmits.yaml
│   │   │       └── ...
│   │   └── infra-periodics.yaml   # Infrastructure periodic jobs
│   └── step-registry/             # Shared test step definitions
│       ├── ipi/
│       │   └── install/
│       │       ├── ipi-install-workflow.yaml
│       │       ├── install/
│       │       │   ├── ipi-install-install-ref.yaml
│       │       │   └── ipi-install-install-commands.sh
│       │       └── rbac/
│       │           ├── ipi-install-rbac-ref.yaml
│       │           └── ipi-install-rbac-commands.sh
│       ├── gather/
│       │   ├── must-gather/
│       │   ├── extra/
│       │   └── audit-logs/
│       ├── hypershift/
│       │   └── ...
│       └── ...
├── cluster/                       # Build cluster configuration
│   └── test-deploy/               # CI infrastructure deployments
├── core-services/                 # Core CI service configs
│   ├── prow/                      # Prow controller configs
│   └── release-controller/        # Release controller configs
└── hack/                          # Helper scripts (generators, validators)
    └── generators/                # Job config generators
```

### ci-operator Config Files

**Location**: `ci-operator/config/<org>/<repo>/<org>-<repo>-<branch>.yaml`

These YAML files define how ci-operator builds, tests, and promotes images for a specific repo
branch. Each file contains:

```yaml
# Example: ci-operator/config/openshift/installer/openshift-installer-master.yaml
base_images:
  base:
    name: "4.18"
    namespace: ocp
    tag: base
build_root:
  image_stream_tag:
    name: release
    namespace: openshift
    tag: golang-1.22
images:
  - from: base
    to: installer
    dockerfile_path: Dockerfile.ci
releases:
  initial:
    integration:
      name: "4.18"
      namespace: ocp
  latest:
    integration:
      name: "4.18"
      namespace: ocp
tests:
  - as: e2e-aws-ovn             # Test name (becomes the --target)
    steps:
      cluster_profile: aws       # Cloud credentials and config
      workflow: openshift-e2e-aws
  - as: e2e-gcp
    steps:
      cluster_profile: gcp
      workflow: openshift-e2e-gcp
      env:
        COMPUTE_NODE_TYPE: n2-standard-4
promotion:
  to:
    - name: "4.18"
      namespace: ocp
```

**Key fields and their impact on job behavior**:

| Field | Purpose | Failure Impact |
|-------|---------|----------------|
| `base_images` | Images pulled as build inputs | Image pull failures if tag is removed or registry is down |
| `build_root` | Build environment image | Build failures if root image is unavailable |
| `images` | Images built from source | Build errors, Dockerfile changes |
| `releases` | Release payloads to use for testing | `creating_release_images` failures if payload tag doesn't exist |
| `tests[].steps.workflow` | Which step registry workflow to run | Workflow changes affect test execution |
| `tests[].steps.cluster_profile` | Cloud credentials and cluster config | Cloud authentication and quota issues |
| `tests[].steps.env` | Environment variable overrides | Behavior changes from env var modifications |
| `promotion` | Where built images are pushed | Promotion failures affect downstream consumers |

**Validation rule for ref steps in config files**: In config files (under
`ci-operator/config/`), ref steps cannot have sibling properties like `timeout`,
`best_effort`, `as`, `commands`, `from`, `from_image`, or `resources`. The validator treats
these as literal test step definitions requiring all mandatory fields. This restriction does
NOT apply to workflow files under `ci-operator/step-registry/`, where `timeout` and
`best_effort` on ref steps are valid. For custom timeouts in config files, use the `TIMEOUT`
env var in the job's `env:` section.

### Job Definitions (Generated)

**Location**: `ci-operator/jobs/<org>/<repo>/`

Job definition files are **generated** by `make jobs` from the ci-operator config files; never
edit them directly. The generated files define the Prow job with:

```yaml
# Example structure (generated, do not edit)
presubmits:
  openshift/installer:
    - name: pull-ci-openshift-installer-master-e2e-aws-ovn
      agent: kubernetes
      decorate: true
      cluster: build01
      spec:
        containers:
          - image: ci-operator:latest
            command:
              - ci-operator
            args:
              - --image-import-pull-secret=/etc/pull-secret/.dockerconfigjson
              - --target=e2e-aws-ovn
```

**Job naming convention**:
- Presubmits: `pull-ci-<org>-<repo>-<branch>-<target>`
- Postsubmits: `branch-ci-<org>-<repo>-<branch>-<target>`
- Periodics: `periodic-ci-<org>-<repo>-<branch>-<target>`
  - Release periodics: `periodic-ci-openshift-release-master-ci-<version>-<target>`
  - Nightly periodics: `periodic-ci-openshift-release-master-nightly-<version>-<target>`

**Job types and their execution model**:

| Job Type | Trigger | Execution Type ID | Purpose |
|----------|---------|-------------------|---------|
| Presubmit | PR creation/update, `/test` comment | 3 | Validate PR changes |
| Postsubmit | Merge to branch | 2 | Post-merge validation, image promotion |
| Periodic | Cron schedule | 1 | Continuous validation, nightly testing |

### The Step Registry

A library of reusable test steps in `ci-operator/step-registry/`, using a hierarchical
composition model:

```text
Workflow (top-level orchestration)
  └── defines pre/test/post phases
       ├── Phase: pre (setup/installation)
       │   ├── Chain (group of steps)
       │   │   ├── Ref (single step) → commands.sh
       │   │   └── Ref (single step) → commands.sh
       │   └── Ref (single step) → commands.sh
       ├── Phase: test (actual testing)
       │   └── Ref (single step) → commands.sh
       └── Phase: post (teardown/gathering)
           ├── Chain: gather
           │   ├── Ref: gather-must-gather → commands.sh
           │   ├── Ref: gather-extra → commands.sh
           │   └── Ref: gather-audit-logs → commands.sh
           └── Ref: deprovision → commands.sh
```

#### Step Types

**Workflows** (`*-workflow.yaml`) — Top-level orchestration defining the three phases:

```yaml
# ci-operator/step-registry/openshift/e2e/aws/openshift-e2e-aws-workflow.yaml
workflow:
  as: openshift-e2e-aws
  steps:
    pre:
      - chain: ipi-aws-pre
    test:
      - ref: openshift-e2e-test
    post:
      - chain: ipi-aws-post
  documentation: |-
    Run the OpenShift end-to-end test suite on AWS.
```

**Chains** (`*-chain.yaml`) — Ordered groups of refs or other chains:

```yaml
# ci-operator/step-registry/ipi/aws/pre/ipi-aws-pre-chain.yaml
chain:
  as: ipi-aws-pre
  steps:
    - ref: ipi-install-rbac
    - ref: ipi-conf
    - ref: ipi-conf-aws
    - chain: ipi-install
```

**Refs** (`*-ref.yaml`) — Individual executable steps with an associated shell script:

```yaml
# ci-operator/step-registry/ipi/install/install/ipi-install-install-ref.yaml
ref:
  as: ipi-install-install
  from: installer
  commands: ipi-install-install-commands.sh
  resources:
    requests:
      cpu: 1000m
      memory: 2Gi
  timeout: 30m
  grace_period: 30m
  env:
    - name: OPENSHIFT_INSTALL_INVOKER
      default: openshift-internal-ci/ci-operator
  documentation: |-
    Runs the openshift-install create cluster command.
```

**Commands** (`*-commands.sh`) — The shell script executed by a ref step. Runs inside a
container built from the image specified by the ref's `from` field.

#### Step Resolution Order

When ci-operator resolves a workflow:

1. Look up the workflow definition from the step registry
2. For each phase (pre, test, post), resolve the listed chains and refs
3. Chains are recursively expanded into their constituent refs
4. Each ref maps to a commands.sh script and a container image
5. The final execution plan is a flat list of steps per phase

#### Key Step Registry Paths

| Path | Purpose |
|------|---------|
| `ci-operator/step-registry/ipi/install/` | IPI cluster installation steps |
| `ci-operator/step-registry/ipi/conf/` | IPI configuration steps (install-config) |
| `ci-operator/step-registry/ipi/deprovision/` | IPI cluster teardown |
| `ci-operator/step-registry/openshift/e2e/` | E2E test execution |
| `ci-operator/step-registry/gather/` | Artifact gathering (must-gather, extra, audit) |
| `ci-operator/step-registry/hypershift/` | HyperShift-specific steps |
| `ci-operator/step-registry/cucushift/` | Extended platform test steps |
| `ci-operator/step-registry/upi/` | UPI installation steps |

### Cluster Profiles

**Location**: `cluster/test-deploy/<profile-name>/` or defined in Vault

Cluster profiles provide cloud credentials, SSH keys, pull secrets, and platform-specific
config for test jobs. Specified in the ci-operator config:

```yaml
tests:
  - as: e2e-aws
    steps:
      cluster_profile: aws    # References the "aws" cluster profile
      workflow: openshift-e2e-aws
```

**Common cluster profiles and what they provide**:

| Profile | Platform | Contents |
|---------|----------|----------|
| `aws` | AWS | AWS credentials, region config, instance types |
| `aws-2` | AWS | Alternate AWS account (different quotas) |
| `gcp` | GCP | GCP service account, project config |
| `azure4` | Azure | Azure credentials, subscription config |
| `metal` | Bare Metal | IPMI credentials, network config |
| `packet` | Equinix Metal | API token, project config |
| `vsphere` | vSphere | vCenter credentials, datacenter config |
| `ibmcloud` | IBM Cloud | API key, resource group config |

**How cluster profiles affect job behavior**:
- Different profiles may have different cloud quotas available
- Region or zone selection within a profile affects resource availability
- Profile changes (e.g., rotating credentials) can cause authentication failures
- Adding/removing profiles requires coordinated changes across config and Vault

### Templates (Legacy vs Step Registry)

The step registry is the modern approach. Legacy templates predate it and defined entire test
workflows in a single OpenShift template. Some jobs still use templates, identifiable by a
`--template` argument in the ci-operator invocation instead of `--target` with multi-stage
steps. Template-based jobs are being migrated to the step registry.

### Leases and Resource Management

Two systems lease scarce infrastructure to CI jobs; both emit `failed to acquire lease...`
in the top-level `build-log.txt`, and both are CI infrastructure problems — never product bugs:

- **Boskos** brokers cloud-account / quota "slices" for cloud jobs (aws/gcp/azure).
- **OFCIR** (OpenShift Fleeting CI Resources) leases pre-provisioned hosts for bare-metal and
  Equinix (`metal`/`packet`) jobs.

```text
failed to acquire lease: context deadline exceeded
```

```text
failed to acquire lease for cloud quota slice "aws-quota-slice": all resources are in use
```

**Common lease failure patterns**:
- `context deadline exceeded` — no lease became available within the timeout
- `all resources are in use` — every account/slice for that platform is occupied
- `failed to release lease` — cleanup failure (does not affect test results)

For the per-system CRDs and checks (Boskos slices, OFCIR `cip`/`cir`, Hive `ClusterClaim`), see
[Cloud Provider Errors](cloud-provider-errors.md#1-ci-resource-acquisition-job-never-provisions).

---

## ci-operator — The Test Orchestrator

`ci-operator` orchestrates CI test execution. It runs as a pod in the build cluster and
manages the entire test lifecycle.

### What ci-operator Does

1. **Source cloning** — Clones the repo under test (and any additional repos)
2. **Image building** — Builds container images from Dockerfiles in the repo
3. **Release image creation** — Assembles or imports release payload images
4. **Multi-stage test execution** — Runs the workflow's pre/test/post steps
5. **Artifact collection** — Gathers logs, JUnit results, and other artifacts to GCS
6. **Image promotion** — Pushes built images to the CI registry (postsubmit only)

### ci-operator Arguments

The most important ci-operator arguments (visible in `prowjob.json`):

```bash
ci-operator \
  --image-import-pull-secret=/etc/pull-secret/.dockerconfigjson \
  --lease-server-credentials-file=/etc/boskos/credentials \
  --target=e2e-aws-ovn \          # Which test to run (maps to tests[].as in config)
  --variant=                       # Config variant (if any)
  --resolver-address=...           # Step registry resolver endpoint
  --gcs-upload-secret=...          # GCS upload credentials
```

The `--target` argument identifies the test definition in the ci-operator config file. Use the
**job name** from `.spec.job` in `prowjob.json` only for the top-level Prow bucket path; the
step artifacts live under `artifacts/{target}/`, keyed by the `--target` value. The job name
and target can differ for PR jobs, so do not substitute one for the other.

### Image Building and Promotion

ci-operator builds images in this order:

1. **Pull base images** — from `base_images` in config (e.g., `ocp/4.18:base`)
2. **Build root image** — the build environment (Go compiler, tools)
3. **Build source image** — clone the repo into the build root
4. **Build pipeline images** — intermediate build stages
5. **Build output images** — final images defined in `images` config section
6. **Assemble release payload** — create or import the release image (for `releases` config)

**Image promotion** (postsubmit only):
- After tests pass, built images are pushed to the CI image registry
- The `promotion` config section defines the target image stream
- Promoted images become available for other jobs and release payloads
- Promotion failures do not affect test results but block image availability

### Release Image Creation and Injection

The `releases` section defines which release payloads to use:

```yaml
releases:
  initial:                    # The "from" version (for upgrade tests)
    integration:
      name: "4.17"
      namespace: ocp
  latest:                     # The "to" version (what we're testing)
    integration:
      name: "4.18"
      namespace: ocp
```

ci-operator creates release images by:
1. Importing the base release payload from the image stream
2. Replacing images that were built from source in this job
3. Creating a custom release payload with the test changes included

**Common `creating_release_images` failure**:
```text
error creating release images: failed to import release ...
```
This occurs when:
- The referenced image stream tag doesn't exist
- The CI registry is experiencing issues
- The release payload import times out
- Network issues between build cluster and registry

### Multi-Stage Test Execution Model

ci-operator executes multi-stage tests in three phases:

```text
PRE phase (setup)     → Runs sequentially; failure aborts remaining pre steps AND skips test phase
                         Post phase still runs for cleanup
TEST phase (testing)  → Runs sequentially; failure records test failure
                         Post phase still runs for cleanup
POST phase (cleanup)  → Runs sequentially; failures are recorded but don't change overall result
                         Always runs, even if pre or test phases failed
```

**Step failure propagation rules**:
1. If a **pre** step fails → remaining pre steps are skipped, test phase is skipped,
   post phase runs for cleanup
2. If a **test** step fails → remaining test steps may be skipped (depends on config),
   post phase runs for cleanup
3. If a **post** step fails → subsequent post steps continue running, the step failure
   is noted but does not change the overall job result
4. Steps marked `best_effort: true` do not cause phase failure regardless of outcome
5. Steps with `optional: true` can be skipped without causing failure

### ci-operator vs Test Errors

Whether an error comes from ci-operator itself or from test code is critical for correct
root-cause analysis.

**ci-operator infrastructure errors** — indicate CI infrastructure problems:

| Error Message | Category | Meaning |
|---------------|----------|---------|
| `failed to resolve release images` | Release resolution | Image stream or tag not found |
| `failed to build [image]` | Image build | Dockerfile or dependency issue |
| `error creating release images` | Release creation | Payload assembly failed |
| `error: the interrupt handler was triggered` | Timeout/interrupt | Job was killed (timeout or preemption) |
| `failed to acquire lease` | Resource management | No cloud quota available |
| `could not resolve ...` | Step resolution | Step registry reference broken |
| `unresolvable tag` | Image resolution | Referenced image tag missing |
| `error: Process interrupted` | Pod kill | Build cluster node issues |
| `pod pending timeout` | Scheduling | Pod couldn't be scheduled on build cluster |

**Test errors** — indicate product or test code problems:

| Error Pattern | Category | Meaning |
|---------------|----------|---------|
| `FAIL [test name]` | Test failure | A Go test assertion failed |
| `panic:` in test output | Test crash | Test binary crashed |
| `timed out waiting for` | Test timeout | Product not ready in time |
| `install should succeed` | Install failure | OpenShift installation failed |
| Step build-log shows application errors | Application error | Product component failure |

**Key distinction**: ci-operator errors appear in the **top-level `build-log.txt`** before
test execution begins. Test errors appear in **step-level build logs** under
`artifacts/{target}/{step-name}/build-log.txt`.

### ci-operator Step Graph

The `ci-operator-step-graph.json` artifact shows all steps, their dependencies, and timing:

```json
[
  {
    "step": "ipi-install-install",
    "duration": "18m32s",
    "state": "succeeded",
    "started_at": "2024-01-15T10:23:45Z",
    "finished_at": "2024-01-15T10:42:17Z"
  },
  {
    "step": "openshift-e2e-test",
    "duration": "45m12s",
    "state": "failed",
    "started_at": "2024-01-15T10:42:30Z",
    "finished_at": "2024-01-15T11:27:42Z"
  }
]
```

If steps never started or all failed simultaneously at a very early timestamp, it's almost
certainly an infrastructure issue, not a product issue.

### Common ci-operator Failure Modes

#### `creating_release_images`

The job fails during release image assembly. Usual causes:
- The release image stream tag being deleted or moved
- CI registry (registry.ci.openshift.org) outage or slowness
- Network issues between the build cluster and the registry
- A recent change to the `releases` section in ci-operator config

**Diagnose**: Check the top-level `build-log.txt` for lines starting with `Creating release
images`. The error message typically includes which specific image import failed.

#### `pod_pending`

The ci-operator pod or a test step pod could not be scheduled:

```text
error: pod ci-op-xxxxx/test did not start running within 30m:
  containers with unready status: [test]
  pod is in Pending phase
```

Causes:
- Build cluster at capacity (node pressure)
- Resource requests exceeding available node capacity
- Node selector or affinity constraints not satisfiable
- Image pull backoff (registry issues)

#### `image_build_failure`

Image building from source failed:

```text
failed to build "installer": error building image: ...
```

This can be CI infrastructure (missing base image, registry issues) or product code
(Dockerfile errors, compilation failures). Check whether the `base_images` are available and
whether the build error is a compilation error or an image pull error.

#### `step_resolution_failure`

A step registry reference could not be resolved:

```text
could not resolve 'ipi-install-install': no such ref
```

The step registry was changed and a reference broke. Check recent `openshift/release` PRs
modifying the step registry.

---

## Step Registry Deep Dive

### The ipi-install Workflow

The IPI (Installer-Provisioned Infrastructure) workflow is the most common; its structure
covers the majority of CI job failures.

**Typical ipi-install workflow execution order**:

```text
PRE PHASE:
  1. ipi-install-rbac              → Set up RBAC for CI service accounts
  2. ipi-conf                      → Generate base install-config.yaml
  3. ipi-conf-{platform}           → Platform-specific install-config tweaks
  4. ipi-install-install            → Run openshift-install create cluster
  5. [optional additional setup]

TEST PHASE:
  6. openshift-e2e-test             → Run the e2e test suite
  (or custom test steps)

POST PHASE:
  7. gather-must-gather             → Collect must-gather archive
  8. gather-extra                   → Collect oc command outputs, pod logs
  9. gather-audit-logs              → Collect API server audit logs
  10. ipi-deprovision-deprovision   → Destroy the cluster and cloud resources
```

### Common Gather Steps

Gather steps run in the POST phase and collect diagnostic artifacts. Critical for post-mortem
analysis, but their failures do not change the overall job result.

**`gather-must-gather`** — Runs `oc adm must-gather` to collect:
- ClusterOperator status and logs
- Pod status across all namespaces
- Node status and conditions
- Events
- Operator-specific diagnostics

**`gather-extra`** — Runs a series of `oc` commands to capture:
- `oc get nodes -o yaml` → `artifacts/oc_cmds/nodes`
- `oc get pods --all-namespaces` → `artifacts/oc_cmds/pods`
- `oc get events --all-namespaces` → `artifacts/oc_cmds/events`
- Pod logs by namespace → `artifacts/pods/`
- API server audit logs → `artifacts/audit_logs/`
- Node journal logs → `artifacts/journal_logs/`

**`gather-audit-logs`** — Specifically collects API server audit logs for detailed
request-level analysis.

### Pre/Test/Post Execution Model

The phase model is essential for classifying failures:

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  PRE Phase   │────►│  TEST Phase  │────►│  POST Phase  │
│  (setup)     │     │  (testing)   │     │  (cleanup)   │
└──────────────┘     └──────────────┘     └──────────────┘
     │ fail              │ fail              │ fail
     ▼                   ▼                   ▼
  Skip TEST          Record failure      Log warning
  Run POST           Run POST            Continue POST
```

**JUnit artifacts encode phase information**:

The ci-operator JUnit XML (`junit_operator.xml`) includes phase-level testcases:
- `"Run multi-stage test pre phase"` — indicates pre phase status
- `"Run multi-stage test test phase"` — indicates test phase status
- `"Run multi-stage test post phase"` — indicates post phase status

Individual step results also appear as testcases in the JUnit XML, allowing you to
identify exactly which step in which phase failed.

### How Step Failures Propagate

When a step fails, the behavior depends on its configuration:

1. **Normal step failure**: The step exits with a non-zero exit code. ci-operator records
   the failure and applies phase-level propagation rules (see above).

2. **Step timeout**: If a step exceeds its `timeout` value, ci-operator kills the pod
   and records a timeout failure. The `grace_period` allows the step to clean up before
   being forcefully terminated.

3. **`best_effort` step**: Even if it fails, the phase continues as if it succeeded.
   Common for gather steps where partial collection is acceptable.

4. **`optional` step**: Can be skipped entirely without causing failure. Used for
   steps that may not be needed in all configurations.

5. **Resource quota exceeded**: If the step pod's resource requests exceed what's
   available on the build cluster, the pod stays Pending until timeout.

---

## Distinguishing CI Infrastructure vs Product Failures

The most important diagnostic skill. Getting it wrong wastes time investigating the wrong repo.

### Decision Framework

```text
Is the failure in the top-level build-log.txt (ci-operator output)?
  ├── YES → Likely CI infrastructure
  │         Check: lease errors, image pull errors, pod scheduling, step resolution
  └── NO → Is the failure in a step build-log under artifacts/?
            ├── Is the failure in a PRE phase step?
            │   ├── ipi-install-install → Could be product (installer) or infra (cloud)
            │   ├── ipi-conf-* → Usually CI config issue
            │   └── Other setup → Depends on step content
            ├── Is the failure in a TEST phase step?
            │   └── Usually product or test code issue
            │       But check for: test infra issues, flaky tests, env setup failures
            └── Is the failure in a POST phase step?
                └── Usually does not affect test result
                    Gather failures mean fewer diagnostics available
```

### Strong Indicators of CI Infrastructure Issues

1. **Same failure across multiple unrelated jobs**
   - If jobs for `openshift/installer`, `openshift/origin`, and `openshift/cluster-version-operator`
     all fail with the same error at the same time → CI infrastructure issue
   - Check [Sippy](https://sippy.dptools.openshift.org/) for widespread failure patterns
   - Check [search.ci.openshift.org](https://search.ci.openshift.org/) for the error pattern

2. **Failure before test code runs**
   - Errors in the top-level `build-log.txt` during image building, lease acquisition,
     or step resolution are always CI infrastructure
   - No artifacts under `artifacts/{target}/` means ci-operator failed before test execution

3. **ci-operator error reasons**
   - `creating_release_images` → CI registry or image stream issue
   - `pod_pending` → Build cluster capacity issue
   - `acquiring_lease` → Cloud quota exhaustion
   - `building_image` → May be product (compile error) or infra (base image missing)
   - `resolving_step` → Step registry broken reference

4. **Build farm / build cluster issues**
   - Node pressure causing pod evictions: check if `prowjob.json` shows very short
     duration with no test output
   - Registry problems: `ImagePullBackOff` errors in build-log.txt
   - DNS resolution failures: `lookup registry.ci.openshift.org: no such host`
   - GCS upload failures: artifacts missing but tests may have passed

5. **Correlation with `openshift/release` PRs**
   - Check if a recent PR to `openshift/release` modified the step, workflow, chain,
     or config used by the failing job
   - Use the timing: if failures started at a specific time, check what merged around then

6. **Cloud provider outages**
   - Multiple jobs on the same cloud failing with API errors
   - AWS: `RequestLimitExceeded`, `InsufficientInstanceCapacity`
   - GCP: `QUOTA_EXCEEDED`, `ZONE_RESOURCE_POOL_EXHAUSTED`
   - Azure: `OperationNotAllowed`, `QuotaExceeded`

### Strong Indicators of Product Code Issues

1. **Failure only in specific job variant**
   - If only the `e2e-aws-ovn` job for `openshift/installer` fails but other installer
     jobs pass → likely product issue specific to that configuration

2. **Failure correlates with product PR**
   - The failure started in a specific PR's presubmit → very likely product issue
   - The failure appeared in periodics after a specific merge → product regression

3. **Test assertion failures**
   - `FAIL: TestFoo` in a test step build-log → test or product issue
   - Stack traces pointing to product code → product issue
   - Stack traces pointing to test framework code → test infrastructure issue

4. **Step script errors**
   - If the error is a scripting issue in a CI step (unbound variable, syntax error,
     missing command, bad exit code from a shell script), read the step build-log to
     identify the shell error, then check recent commits to that step's `*-commands.sh`
     in `openshift/release`. This is a CI infrastructure issue caused by a step registry
     change, not a product bug — the fix is a PR to `openshift/release`. Include the
     responsible PR in your evidence.

### Ambiguous Cases

Some failures can be either CI or product:

| Symptom | CI Infrastructure | Product Code |
|---------|-------------------|--------------|
| `install should succeed` | Cloud quota, lease timeout, region outage | Installer bug, config generation error |
| Image pull failure | Registry outage, tag moved | Wrong image reference in product code |
| Test timeout | Build cluster slow, resource contention | Product performance regression |
| Network connectivity error | Build cluster networking, DNS | Product networking bug, CNI issue |
| `OOMKilled` | Build cluster node pressure, wrong resource requests | Memory leak in product code |

For ambiguous cases:
1. Check if the failure reproduces consistently (product) or is intermittent (likely infra)
2. Check if other jobs on the same cluster/profile show similar issues
3. Check the timing correlation with both product PRs and `openshift/release` PRs

---

## How to Check for Recent CI Infrastructure Changes

### Finding Relevant `openshift/release` PRs

#### By Time Correlation

If failures started at a specific time, check what merged to `openshift/release` around then:

```text
https://github.com/openshift/release/pulls?q=is%3Apr+is%3Amerged+sort%3Aupdated-desc
```

Filter by the path that affects the failing job:
- `ci-operator/config/<org>/<repo>/` — job configuration changes
- `ci-operator/step-registry/<step-path>/` — step definition changes
- `cluster/test-deploy/` — cluster profile changes
- `core-services/` — core CI service changes

#### By Step Registry Path

If a specific step is failing, find PRs that modified it:

```text
https://github.com/openshift/release/pulls?q=is%3Apr+is%3Amerged+path%3Aci-operator/step-registry/ipi/install/
```

#### By Job Config Path

If a specific job's configuration may have changed:

```text
https://github.com/openshift/release/pulls?q=is%3Apr+is%3Amerged+path%3Aci-operator/config/openshift/installer/
```

### Checking Step Registry Changes

To investigate a step change:

1. **Identify the failing step** from the JUnit XML or build-log.txt
2. **Map step name to file path**: Step names use dashes (`ipi-install-install`) and map to
   directory paths (`ci-operator/step-registry/ipi/install/install/`)
3. **Check recent changes** to the step's ref, chain, or commands:
   ```bash
   git log --oneline -20 -- ci-operator/step-registry/ipi/install/install/
   ```
4. **Check if the step was modified** in a recent workflow change that includes it

Use `/ci:list-step` to see the full hierarchy of a workflow or chain, including all refs and
their command scripts with repo paths.

### Identifying Cluster Profile Changes

Cluster profile changes can affect all jobs using that profile:

1. Check if credentials were rotated (usually announced in advance)
2. Check for changes to profile defaults (regions, instance types)
3. Check Vault for secret updates (requires privileged access)

### Lease and Quota Changes

Lease configuration changes affect resource availability:

1. Check for changes to Boskos/OFCIR configuration in `openshift/release`
2. Check if cloud account quotas were modified
3. Check if new jobs were added that compete for the same quota pool

### pj-rehearse — Testing Config Changes

The `pj-rehearse` system in `openshift/release` runs rehearsal jobs for config changes before
they merge. When investigating a suspected config change issue:

1. Find the `openshift/release` PR that modified the config
2. Check if `pj-rehearse` ran and passed for that PR
3. If rehearse passed but production fails, the issue may be environmental (different cluster,
   timing, or resource availability)

---

## Image Promotion and Registry Interactions

### How Images Flow Through CI

```text
Developer PR
    │
    ▼
Presubmit Job (ci-operator)
    │  Build images from source
    │  Create test release payload
    │  Run tests
    │  ✗ Images are NOT promoted
    │
    ▼
PR Merges
    │
    ▼
Postsubmit Job (ci-operator)
    │  Build images from source
    │  Run tests (if configured)
    │  ✓ Promote images to CI registry
    │     registry.ci.openshift.org/ocp/4.18:component-name
    │
    ▼
Release Controller
    │  Assembles new release payload from promoted images
    │  Creates nightly/CI payload tag
    │  Triggers acceptance jobs
    │
    ▼
Periodic Jobs
    │  Test against assembled release payload
    │  Use RELEASE_IMAGE_LATEST or similar env vars
    │
    ▼
Release (if acceptance passes)
```

### CI Image Registry

The CI image registry at `registry.ci.openshift.org` stores:

- **Built images**: Components built from source by postsubmit jobs
- **Release payloads**: Assembled by the release controller
- **Base images**: Shared base images used by builds
- **Test images**: Images specifically for test infrastructure

Image references use OpenShift image stream notation:
```text
registry.ci.openshift.org/ocp/4.18:installer
registry.ci.openshift.org/ocp/release:4.18.0-0.nightly-2024-01-15-010101
```

### Registry Pull Failures

**Registry outage or slowness**:
```text
error: unable to pull image registry.ci.openshift.org/ocp/4.18:base: ...
```
- Affects many jobs simultaneously
- Check registry status and recent incidents
- Retrying the job usually helps once the registry recovers

**Rate limiting**:
```text
toomanyrequests: You have reached your pull rate limit
```
- External registries (quay.io, docker.io) may rate-limit CI
- Internal registry (registry.ci.openshift.org) has higher limits but can still be affected

**Image not found / `manifest unknown`**:
```text
manifest unknown: manifest unknown
```
This can indicate:
- The image tag was deleted or moved
- The promotion job hasn't run yet (timing issue between post-submit and consumer)
- The image stream tag reference is incorrect
- A recent change to the `releases` or `base_images` section in ci-operator config
  pointed to a non-existent tag

### `manifest unknown` Timing Issues

A common scenario after a product merge:

1. PR merges to `openshift/installer`
2. Postsubmit job starts to build and promote images
3. Meanwhile, a periodic job starts and tries to use the new payload
4. The periodic job fails with `manifest unknown` because the postsubmit hasn't finished
   promoting yet

This is a transient CI infrastructure issue, NOT a product bug. The periodic job passes on the
next run once the postsubmit completes promotion.

### Promotion Failures

When a postsubmit promotion fails:
- The component's image in the CI registry becomes stale
- Subsequent release payloads will use the older image version
- This can cause payload rejection, test failures in periodic jobs that depend on the updated
  image, and version skew between components

**Detect**: Check the postsubmit job for the repo. If its most recent run failed or hasn't run,
the image promotion may be stale.

---

## CI Job Lifecycle Phases

A CI job runs through eight phases: (1) Prow scheduling, (2) ci-operator startup, (3) source
cloning, (4) image building, (5) lease acquisition, (6) multi-stage test execution
(pre/test/post), (7) artifact gathering, (8) teardown. Per-phase failure indicators and causes
are covered in the failure-modes and practical-steps sections above and below.

**Key rule**: Failures at phases 1–5 are almost always CI infrastructure issues.
Failures at phase 6 require careful analysis to distinguish CI from product issues.
Failures at phases 7–8 are informational and don't change the test result.

---

## Detecting CI Infrastructure Failures — Practical Steps

### Step 1: Check `build-log.txt` First

The top-level `build-log.txt` shows ci-operator output. Read the first ~50 lines and the last
~100 lines:

- **First lines**: ci-operator version, configuration loading, early setup
- **Last lines**: the final error, step summary, exit reason

If the build log never reaches `"Running multi-stage test"` or `"Executing step"`, the failure
is in CI infrastructure before test execution.

### Step 2: Check `prowjob.json` Timing

```bash
jq '{
  start: .status.startTime,
  pending: .status.pendingTime,
  completion: .status.completionTime,
  state: .status.state,
  duration_minutes: ((.status.completionTime | fromdateiso8601) -
                     (.status.startTime | fromdateiso8601)) / 60
}' prowjob.json
```

**Interpretation**:
- Long gap between `pendingTime` and `startTime` → scheduling issues (CI infrastructure)
- Very short total duration with no test artifacts → early CI infrastructure failure
- Normal duration with test artifacts → test-level failure (product or CI config)
- Duration near the job's timeout → timeout issue (could be either)

### Step 3: Check `ci-operator-step-graph.json`

This artifact shows all steps, their execution status, and timing. Look for:

- Steps that never started → infrastructure failure prevented execution
- All steps failed simultaneously → cluster-level or infrastructure issue
- Only one step failed → focus investigation on that specific step
- Timing gaps between steps → resource contention or scheduling delays

### Step 4: Check JUnit XML

Download and parse `junit_operator.xml` from the artifacts:

```bash
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/junit*.xml"
```

The JUnit XML encodes:
- Phase-level results (`"Run multi-stage test pre phase"`)
- Individual step results (each step as a testcase)
- Failure messages and error details

### Step 5: Check for Symptom Labels

The CI system attaches machine-detected symptom labels to job runs:

```bash
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/job_labels/"
```

Each JSON file under `job_labels/` describes a detected symptom with a summary and explanation.
These are environmental observations, NOT definitive root causes. They provide context (e.g.,
"test failures occurred during high CPU events") but require correlation with other evidence.

### Step 6: Cross-Reference with Other Jobs

Check whether the failure is isolated or widespread:

1. **Same job, recent runs**: Does it fail consistently or intermittently?
2. **Same workflow, different repos**: Do other repos using the same workflow fail?
3. **Same cloud profile, different jobs**: Do other jobs on the same cloud fail?
4. **Same build cluster, different jobs**: Is the build cluster having issues?

Use [Sippy](https://sippy.dptools.openshift.org/) to check pass rates for the job
over time and identify when the failure pattern started.

Use [search.ci.openshift.org](https://search.ci.openshift.org/) to search for the
specific error message across all recent CI jobs.

---

## Environment Variables and Overrides

CI jobs are parameterized through environment variables; these help diagnose
configuration-driven failures.

### Common Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `RELEASE_IMAGE_LATEST` | Release payload image to test | ci-operator config / override |
| `RELEASE_IMAGE_INITIAL` | Initial version for upgrade tests | ci-operator config / override |
| `OPENSHIFT_INSTALL_INVOKER` | Identifies the installer caller | Step registry ref |
| `CLUSTER_TYPE` | Cloud platform type | Cluster profile |
| `TEST_SUITE` | Which e2e test suite to run | ci-operator config env |
| `COMPUTE_NODE_TYPE` | Cloud instance type for workers | ci-operator config env |

### Multistage Parameter Overrides

Step registry steps can define parameters that are overridable:

```yaml
# In the ref definition
env:
  - name: TIMEOUT
    default: "3600"
    documentation: "Test timeout in seconds"
```

These can be overridden in the ci-operator config:

```yaml
tests:
  - as: e2e-aws
    steps:
      env:
        TIMEOUT: "5400"
```

Or via the gangway API using the `MULTISTAGE_PARAM_OVERRIDE_` prefix:

```json
{
  "pod_spec_options": {
    "envs": {
      "MULTISTAGE_PARAM_OVERRIDE_TIMEOUT": "5400"
    }
  }
}
```

---

## Artifact Directory Structure Reference

See [Artifacts Reference](artifacts.md) for the complete GCS artifact tree and paths.

**Pitfall**: The `{target}` directory under `artifacts/` is named after the `--target` value,
**not** the job name. Only the top-level Prow bucket path uses the job name from `.spec.job` in
`prowjob.json`. For PR jobs the two can differ, so use `--target` for step-artifact paths and
`.spec.job` only for the bucket path.

---

## See Also

- [Artifacts Reference](artifacts.md) — Complete artifact directory structure and paths
- [Cloud Provider Errors](cloud-provider-errors.md) — AWS/GCP/Azure-specific failure patterns
- [Flaky Test Identification](flaky-test-identification.md) — Distinguishing flaky tests from real failures
- [Install Failure Reference](install/general.md) — OpenShift installation failure analysis
- [Test Extension Binaries](test-extension-binaries.md) — component `*-tests-ext` (OTE) binary failures
