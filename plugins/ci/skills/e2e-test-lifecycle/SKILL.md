---
name: e2e-test-lifecycle
description: Manage OpenShift Ginkgo e2e test suite membership, lifecycle promotion, and shard rebalancing using OTE labels and Sippy data
---

# E2E Test Lifecycle Management

Manage OpenShift Ginkgo e2e tests: organize them into a hierarchical,
label-driven suite model, promote them through the lifecycle based on
stability data, and rebalance shards for predictable CI job runtimes.

This skill implements the conventions defined in the **"Test Suites"**
enhancement (openshift/enhancements). When guidance here conflicts with
older material, the enhancement is authoritative.

## When to Use This Skill

Use this skill when you need to:

- Assign a test to a suite or move it between suites
- Initialize labels for an existing repo's tests for the first time
  (bulk-classify existing conformance tests into `stable` vs `active`)
- Promote tests from `active` to `stable` based on pass rate and age
- Identify tests in `openshift/conformance` that should migrate to
  feature-specific or `active`/`stable` suites
- Rebalance test shards (`stable-01`, `stable-02`, etc.) based on job
  runtime data
- Audit suite membership for a component or SIG
- Set a test's lifecycle to `Informing()` during its stabilization period
- Create or modify feature suites that compose into the new suite hierarchy
- Set up or manage spot-check suites/jobs for features requiring uncommon
  cluster configurations
- Monitor spot-check job pass status and flag overdue runs in Component
  Readiness

## Prerequisites

1. **Repository context**: Must be run inside a repository containing
   OpenShift Ginkgo e2e tests. This is typically `openshift/origin` but
   increasingly component repos using the OpenShift Tests Extension (OTE)
   framework, plus `openshift/kubernetes` (special-cased below).

2. **Build the repo's test binary** so you can list its tests. Listing and
   labeling never contact a running cluster.
   - origin: `make build` produces `openshift-tests`. `list` runs without a
     `KUBECONFIG`, but a few tests are registered by Ginkgo container bodies
     that read cluster config at tree-build time, so without a *parseable*
     `KUBECONFIG` the list is silently **incomplete** (a fake one restores the
     full set — see [Listing Tests](#listing-tests-and-their-metadata)); the
     cluster is never contacted either way.
   - OTE component repos / `openshift/kubernetes`: build the repo's
     extension binary (`*-tests-ext`; o/k builds `k8s-tests-ext`). These list
     with no kubeconfig at all.

3. **Sippy access**: only for querying test pass rates and job runtimes
   (used for promotion and shard-balancing decisions, not for listing or
   labeling). Use the `ci:fetch-test-runs` and `ci:ask-sippy` skills;
   authentication may be required via `ci:oc-auth`.

## Suite Architecture

### Legacy Suites (Shrink Over Time)

The current flat suites are overcrowded. Under the enhancement they are
replaced by minimal conformance suites that contain **only** core
smoke-test functionality confirming nothing is seriously broken in an
OpenShift cluster:

| Legacy suite (today) | Target minimal suite (enhancement) |
|----------------------|-------------------------------------|
| `openshift/conformance/parallel` | `openshift/conformance/parallel/minimal` |
| `openshift/conformance/serial` | `openshift/conformance/serial/minimal` |
| `openshift/conformance` (union) | union of the two `/minimal` suites |

**Minimal conformance membership is label-driven.** A test belongs to
minimal conformance if and only if it carries the `Conformance` label; the
`.../minimal` suites are defined by a `Qualifiers` CEL expression that
filters on that label (see
[Minimal Conformance Is Label-Driven](#minimal-conformance-is-label-driven)).
Only tests verifying the most fundamental cluster smoke-test functionality
should carry the label. Most tests should NOT.

### New Suite Hierarchy

Tests graduate through a lifecycle of suites. Feature suites compose into
these parent suites. **`active` is explicitly sharded** too
(`active-01`, `active-serial-01`), consistent with `stable`:

| Suite | Purpose | Parallelism |
|-------|---------|-------------|
| `openshift/conformance/parallel/minimal` | Parallel tests carrying the `Conformance` label | parallel |
| `openshift/conformance/serial/minimal` | Serial tests carrying the `Conformance` label | serial |
| `openshift/active-01` | Recent or actively developed features, parallel, shard 1 | parallel |
| `openshift/active-serial-01` | Recent or actively developed features, serial, shard 1 | serial |
| `openshift/stable-NN` | Graduated stable tests, parallel, explicitly sharded (`stable-01`, `stable-02`) | parallel |
| `openshift/stable-serial-NN` | Graduated stable tests, serial, explicitly sharded | serial |
| `openshift/spot-check/<feature>` | Tests requiring uncommon cluster configs, owned by a component team | varies |

### Roles

- **Test author** — a developer contributing tests for a component. Adds
  new tests, declares feature suites, marks tests `Informing()`.
- **QSE engineer** (quality staff engineer) — responsible for suite
  management and test graduation. Reviews pass rates, removes `Informing()`,
  moves feature suites between parents, and balances shards.

### Feature Suites

Teams define feature-specific suites (e.g., `openshift/network/ipsec`,
`openshift/etcd/scaling`) that compose into the parent suites above via
OTE's `Parents` field. A feature suite moves between parent suites over
time (e.g., from `active-01` to `stable-01`) by changing its parent
declaration.

### Composition Model

OTE supports suite composition through the `Parents` field. A child suite's
tests are automatically included when the parent suite runs:

```go
ext.AddSuite(e.Suite{
    Name:    "mycomponent/feature-x",
    Parents: []string{"openshift/active-01"},
})
```

To move a feature suite from `active` to `stable-01`, update its parent:

```go
ext.AddSuite(e.Suite{
    Name:    "mycomponent/feature-x",
    Parents: []string{"openshift/stable-01"},
})
```

Global suites can also use CEL qualifier expressions to filter tests by
labels across all extensions:

```go
ext.AddGlobalSuite(e.Suite{
    Name: "openshift/active-01",
    Qualifiers: []string{
        `labels.exists(l, l=="ACTIVE") && labels.exists(l, l=="SHARD-01")`,
    },
})
```

### Spot-Check Suites

Spot-check suites are for features that require uncommon or specialized
cluster configurations (e.g., etcd scaling, realtime nodes, external OIDC,
CNV-dependent features). These features cannot be tested in the standard
conformance or active/stable jobs because the cluster setup is too
specialized.

Each spot-check suite has:

- **A component owner**: A team responsible for the suite and its tests.
  The owner is accountable for keeping the job passing.
- **Dedicated CI job(s)**: With the specific cluster configuration the
  feature requires.
- **Reduced monitortest sensitivity**: Monitortests (origin tests that
  observe cluster behavior during test runs and optionally generate failure
  JUnit results) still run to gather debugging data, but their ability to
  generate failure JUnits is disabled in most spot-check jobs. These
  specialized configurations often trigger monitortest alerts that are
  expected/acceptable for that configuration but would cause false failures.
- **Component Readiness tracking**: A spot-check job flags in Component
  Readiness if it has not passed within the last 30 days, ensuring coverage
  doesn't silently lapse.

**Spot-check lifecycle:**

| Phase | Cadence | Purpose |
|-------|---------|---------|
| Development (pre-GA) | ~2x/day (minimum 14 runs/week) | Rapid signal during active feature development |
| Graduated (1 release post-GA) | ~1x/month with retries | Ongoing verification that the feature still works |

During development, the higher cadence ensures the minimum 14 runs in the
past week needed for meaningful pass-rate analysis. After the feature GAs
and has been stable for one release, the job promotes to a graduated
spot-check: it runs roughly monthly but must pass (with a couple retries
allowed for infrastructure flakes).

**Existing origin suites that qualify as spot checks**: Several suites
already defined in origin fit the spot-check pattern, including
`openshift/etcd/scaling`, `openshift/etcd/recovery`,
`openshift/etcd/certrotation`, `openshift/nodes/realtime`,
`openshift/nodes/cnv`, `openshift/auth/external-oidc`, `openshift/two-node`,
and `openshift/disruptive-longrunning`. These could be managed under the
spot-check framework going forward.

```go
// Define a spot check suite for a feature requiring specialized config
ext.AddSuite(e.Suite{
    Name:    "openshift/spot-check/etcd-scaling",
    Qualifiers: []string{
        `labels.exists(l, l=="SPOT-CHECK-ETCD-SCALING")`,
    },
})

// Label the test inline for this spot check (at its definition):
g.It("vertical scaling", g.Label("SPOT-CHECK-ETCD-SCALING"), func() { /* ... */ })
```

**Monitortest configuration for spot-check jobs**: monitortests (the
invariant monitors that `openshift-tests run` runs alongside the e2e suite —
disruption, alerts, pod restarts, etc.) still collect data on every run;
what changes for a spot-check is that the sensitive monitortests are
*flaked* instead of hard-failing, so intentional disruption stays visible in
results but cannot fail the job. The control is the `--cluster-stability`
flag on `openshift-tests run`:

```bash
# Spot-check job: keep monitortest data, flake the sensitive monitors
openshift-tests run <suite> --cluster-stability=SpotCheck ...
```

`--cluster-stability` accepts `Stable` (default), `Disruptive`, or
`SpotCheck`. The value selects which set of monitortests hard-fail vs. flake:

| Value | Monitortest behavior |
|-------|----------------------|
| `Stable` | Full monitortest set, all hard-fail (`HardFail`) |
| `Disruptive` | Reduced set; sensitive monitors registered as flakes (`AsFlake`), critical invariants still hard-fail |
| `SpotCheck` | Minimal curated set; sensitive monitors flaked; critical invariants still hard-fail |

In all three modes, data collection (serializers, collectors, interval and
timeline artifacts) always runs — only the fail-vs-flake decision changes.

The fail-vs-flake choice is **per-monitortest, hard-coded** in origin
(`pkg/defaultmonitortests/types.go`, via the `HardFail` / `AsFlake`
constants in `pkg/monitortestframework/types.go`). A flaked monitortest
emits a synthetic passing JUnit alongside each failure (`JUnitsToFlakes`),
which the CI aggregator treats as a flake rather than a failure.

Prefer a suite that already declares its stability level over passing the
flag: origin suites carry a `ClusterStabilityDuringTest` default in
`pkg/testsuites/standard_suites.go` — e.g. `openshift/etcd/scaling` is
`SpotCheck`, and `openshift/disruptive`, `openshift/etcd/recovery`,
`openshift/etcd/certrotation` are `Disruptive`. In CI these are passed
through `TEST_ARGS` (`openshift-tests run "${TEST_SUITE}" ${TEST_ARGS}`),
e.g. `--cluster-stability=Disruptive` in `openshift/release` step configs.

If a *specific* monitortest is still too noisy for a job, add
`--disable-monitor=<name1>,<name2>` — but note this **removes** the
monitortest entirely, so you lose its data (unlike flaking). Conversely
`--monitor=<names>` is an allowlist that disables all others.

> **Limitation.** There is no per-run flag to flake *all* monitortest
> JUnits, and no per-run way to mark an arbitrary monitortest as flake-only.
> If a spot-check job needs a monitortest flaked that `SpotCheck` /
> `Disruptive` does not already flake, the only options are to
> `--disable-monitor` it (losing its data) or to change its registration in
> origin. `run-monitor` and `run-upgrade` hard-code `Stable` and do not
> expose `--cluster-stability`.

### Explicit Sharding

We intentionally do not rely on the pre-existing auto-sharding mechanism.
Auto-sharding does not work in constrained environments like vSphere where
concurrent batches of jobs cannot be spun up. Instead, we use explicit
shards (`active-01`, `stable-01`, `stable-02`, etc.) that can be scheduled
at different times.

Each shard is a separate suite with its own CI job. Tests are assigned to
shards to keep job runtimes roughly balanced (within 10% of mean runtime).

### Minimal Conformance Is Label-Driven

Minimal conformance is not a hand-curated list of test names and is not
something a test "falls into" by being in a particular suite. Membership is
decided by a single label, and the `.../minimal` suites are defined purely
by a `Qualifiers` CEL expression that filters on that label. This is exactly
how `openshift/kubernetes` already defines its minimal suites — it filters
on the upstream-kubernetes-defined `Conformance` label:

```go
// openshift/kubernetes — openshift-hack/cmd/k8s-tests-ext/k8s-tests.go
kubeTestsExtension.AddSuite(e.Suite{
    Name:    "kubernetes/conformance/parallel/minimal",
    Parents: []string{"openshift/conformance/parallel/minimal"},
    Qualifiers: []string{
        `(!name.contains('[Serial]') && !labels.exists(l, l == '[Serial]')) && labels.exists(l, l == "Conformance")`,
    },
})
kubeTestsExtension.AddSuite(e.Suite{
    Name:    "kubernetes/conformance/serial/minimal",
    Parents: []string{"openshift/conformance/serial/minimal"},
    Qualifiers: []string{
        `(name.contains('[Serial]') || labels.exists(l, l == '[Serial]')) && labels.exists(l, l == "Conformance")`,
    },
})
```

Upstream's `Conformance` is a **ginkgo label**, and OTE labels are built
directly on top of ginkgo labels: when
`BuildExtensionTestSpecsFromOpenShiftGinkgoSuite` walks the ginkgo tree it
copies each spec's ginkgo labels verbatim into `spec.Labels`
(`Labels: sets.New[string](spec.Labels()...)` in
`openshift-tests-extension/pkg/ginkgo/util.go`). So `ginkgo.Label("Conformance")`
on a test becomes the plain `Conformance` entry in `spec.Labels` — no
bracketed name annotation involved.

**Use the same `Conformance` label for downstream tests** (`openshift/origin`
and OTE component repos). We have deliberately **avoided adding new bracketed
name annotations** like `[Conformance]`; downstream repos apply the *same*
plain `Conformance` label that upstream uses, and the `.../minimal` suites
filter on it identically. "Add a test to minimal conformance" = give it the
`Conformance` label:

```go
// downstream (origin / OTE component) — mark a test as minimal conformance
// by applying the same ginkgo-style Conformance label upstream uses, inline
// on the test's own node. The .../minimal suites then select it purely by
// that label; the name is never annotated.
g.It("core smoke test", g.Label("Conformance"), func() {
    // ...
})
```

In `openshift/origin` this is wired in `pkg/test/extensions/`: tests carry
the `Conformance` label inline at their definition, and the `.../minimal`
suites are registered by `addLifecycleSuites` in
`pkg/test/extensions/suites.go` (via `AddGlobalSuite`), whose `Qualifiers`
select on `labels.exists(l, l=="Conformance")`.

Register the minimal suites so their `Qualifiers` filter on the label,
splitting parallel vs. serial by checking `[Serial]` in **both** the name and
the labels — a test can be serial via its name tag alone:

```go
ext.AddGlobalSuite(e.Suite{
    Name: "openshift/conformance/parallel/minimal",
    Qualifiers: []string{
        `(!name.contains("[Serial]") && !labels.exists(l, l=="[Serial]")) && labels.exists(l, l=="Conformance")`,
    },
})
ext.AddGlobalSuite(e.Suite{
    Name: "openshift/conformance/serial/minimal",
    Qualifiers: []string{
        `(name.contains("[Serial]") || labels.exists(l, l=="[Serial]")) && labels.exists(l, l=="Conformance")`,
    },
})
```

> **What is decided vs. not.** The *mechanism* is settled: minimal
> conformance is selected by the single plain `Conformance` label — the same
> ginkgo-style label upstream kubernetes uses — filtered by the suite
> `Qualifiers`, in every repo (o/k, origin, and OTE components alike). We do
> **not** introduce a `[Conformance]` name annotation. What is **not yet
> finalized is which tests belong in the `Conformance` bucket** downstream;
> that set still has to be agreed on. **Always match `[Serial]` on name OR
> label** — verified against origin, where serial tests are tagged in the
> name and a label-only qualifier misroutes them into the parallel suite.

Consequences of the label-driven model:

- Adding a test to minimal conformance = applying the `Conformance` label.
  Removing a test = removing the label. No suite-membership edits, no
  `[Suite:...]` name tags.
- `Conformance` is orthogonal to the lifecycle labels (`ACTIVE`, `STABLE`)
  and to `SHARD-NN`. A test can be both `STABLE` and `Conformance`; being
  `STABLE` does not add or remove the `Conformance` label on its own.
- The label is the same everywhere: for `openshift/kubernetes` it already
  exists (applied by upstream kubernetes); downstream you apply the *same*
  `Conformance` label yourself. See
  [Labeling Location by Repo](#labeling-location-by-repo).

## Test Lifecycle

The lifecycle flow is **informing → blocking → graduated**:

| Phase | Suite | Pass Rate Threshold | Duration |
|-------|-------|---------------------|----------|
| New / Stabilizing | `active` with `Informing()` | Failures non-blocking | 2–3 sprints |
| Blocking | `active` (remove `Informing()`) | >= 99% | Until GA + 1 release |
| Graduated | `stable-NN` | >= 99.5% | Permanent |
| Specialized | `spot-check/<feature>` | N/A (own job) | Own cadence |

### 1. New Test (Informing)

A new test starts with the `Informing()` lifecycle, allowing failures to be
non-blocking for 2–3 sprints while stability is improved:

```go
import (
    g "github.com/onsi/ginkgo/v2"
    ote "github.com/openshift-eng/openshift-tests-extension/pkg/ginkgo"
)

var _ = g.Describe("[sig-network] My new feature test", func() {
    g.It("should do the thing", ote.Informing(), func() {
        // test implementation
    })
})
```

The test should be in `active-01` or `active-serial-01` at this point, via a
feature suite whose `Parents` point at the active suite.

### 2. Blocking (in Active)

After 2–3 sprints, if the pass rate is >= 99%, the QSE engineer removes the
`Informing()` decorator, making the test blocking. The test remains blocking
in `active` until GA + 1 release.

### 3. Graduated (Stable)

After the feature GAs (typically one release after GA), and the test has a
sustained very high pass rate (>= 99.5%), the QSE engineer promotes it to a
`stable-NN` or `stable-serial-NN` shard by changing the feature suite's
`Parents` from `openshift/active-*` to `openshift/stable-NN`.

### 4. Spot Check (Specialized Configurations)

Tests requiring uncommon cluster configurations go into a spot-check suite
rather than the active/stable hierarchy. During development, the spot-check
job runs ~2x/day for adequate signal. One release after GA, it graduates to
~1x/month with retries, and Component Readiness flags it if no pass is
recorded within 30 days.

### 5. Conformance Candidates

Minimal conformance is orthogonal to the informing → blocking → graduated
lifecycle. A test is in minimal conformance because it carries the
`Conformance` label, not because of its pass-rate phase. Only tests
verifying the most fundamental cluster smoke-test functionality should
carry the label; most tests should NOT. To make a test a conformance
candidate, apply the plain `Conformance` label (the same label upstream
kubernetes uses; downstream repos reuse it rather than inventing their own);
to withdraw it, remove the label. See
[Minimal Conformance Is Label-Driven](#minimal-conformance-is-label-driven).

## Implementation Steps

### Listing Tests and Their Metadata

We always label tests **in their own repo**, so we only ever need to list
the tests defined in the repo the skill is running against. This is a
**local, offline operation — no cluster and no release payload are
required.** Build the repo's test binary and run its own `list`.

**origin** — build and use `openshift-tests`:

```bash
make build
./openshift-tests list                        # origin's own compiled tests
./openshift-tests list tests                   # same (bare `list` == `list tests`)
./openshift-tests list --suite <suite>        # tests in a specific suite
./openshift-tests list suites                 # suites known to origin
```

**OTE component repos and `openshift/kubernetes`** — build the repo's
extension binary (component repos name it `*-tests-ext`; o/k builds
`k8s-tests-ext` from `openshift-hack/cmd/k8s-tests-ext`) and query it
directly:

```bash
# build the extension binary for your repo, then:
./<extension-binary> list                      # all tests as JSON (default -o json)
./<extension-binary> list -o names             # just test names
./<extension-binary> list -o jsonl             # one spec per line
./<extension-binary> list tests --suite <suite>  # tests in one suite
./<extension-binary> list suites               # advertised suites
./<extension-binary> list components           # advertised components
./<extension-binary> info                      # extension metadata (component, suites, images)
```

The `list` output is an `ExtensionTestSpec` per test: `name`, `labels`
(this is where `ACTIVE`/`STABLE`/`SHARD-NN`/`Conformance` show up),
`lifecycle` (`informing` | `blocking`), `source`, `environmentSelector`,
and `tags`. Use `--component <name>` if the binary declares more than one.

There is no `--extensions-path` flag. Listing does not need a *running*
cluster, but note the caveat below.

> **origin lists a complete set only with a parseable `KUBECONFIG`
> (verified).** origin's `openshift-tests list` builds the Ginkgo tree, and a
> few test packages read cluster config inside their container bodies at
> tree-build time (e.g. `test/extended/router/`, two-node tests). `list`
> itself runs fine with **no** kubeconfig (exit 0, most tests printed), but
> those tests fail to register and are **silently omitted** — a real,
> reproducible gap (measured ~17 fewer specs). A **fake kubeconfig** makes
> them register; the cluster is never contacted:
> ```bash
> cat > /tmp/fake-kubeconfig <<'EOF'
> apiVersion: v1
> kind: Config
> clusters: [{name: fake, cluster: {server: https://127.0.0.1:6443}}]
> contexts: [{name: fake, context: {cluster: fake, user: fake}}]
> current-context: fake
> users: [{name: fake, user: {token: fake}}]
> EOF
> KUBECONFIG=/tmp/fake-kubeconfig ./openshift-tests list tests -o names
> ```
> So always list with the fake kubeconfig for a complete enumeration.
> (Note: piping `list` to `head`/`grep -m` closes the pipe early and prints a
> `FatalErr` goroutine trace on SIGPIPE — that is a broken-pipe artifact, not
> a kubeconfig error; redirect to a file if it's noisy.) Component OTE
> binaries built with the framework directly do not have this tree-build
> dependency and list completely with no kubeconfig at all.

> **Out of scope for this skill (needs a cluster/payload):**
> `openshift-tests list extensions` makes origin reach *across* repos into
> the external extension binaries bundled in a release payload — a
> whole-payload view that requires cluster access (or
> `RELEASE_IMAGE_LATEST` / `EXTENSIONS_PAYLOAD_OVERRIDE`, and
> `EXTENSION_BINARY_OVERRIDE_*` to substitute a local binary). Since we
> label each test from its own source repo, we never need this — list the
> single repo's tests with its own binary as shown above.

### Labeling Tests for Suite Membership

Use OTE labels for suite membership, not `[Suite:...]` tags in test names.
Apply the labels **inline on the Ginkgo node**, at the test's definition; OTE
copies them into `spec.Labels` at build time:

```go
// test/extended/networking/my_feature.go — an active test, shard 1
g.It("my feature works", g.Label("ACTIVE", "SHARD-01"), func() { /* ... */ })

// test/extended/auth/ldap.go — a stable test, shard 1
g.It("LDAP login succeeds", g.Label("STABLE", "SHARD-01"), func() { /* ... */ })
```

Then define suites that filter on these labels:

```go
ext.AddSuite(e.Suite{
    Name:       "openshift/active-01",
    Qualifiers: []string{`labels.exists(l, l=="ACTIVE") && labels.exists(l, l=="SHARD-01")`},
})

ext.AddSuite(e.Suite{
    Name:       "openshift/stable-01",
    Qualifiers: []string{`labels.exists(l, l=="STABLE") && labels.exists(l, l=="SHARD-01")`},
})
```

**Where to put the labels depends on the repo** — see
[Labeling Location by Repo](#labeling-location-by-repo).

### Querying Test Stability from Sippy

Use CI plugin skills to get pass rate data for promotion decisions:

```bash
# Query test pass rates for a specific test
/ci:ask-sippy "What is the pass rate for test '[sig-network] Services should serve endpoints on same port and different protocols' over the last 30 days in 4.19?"

# Query job runtimes for shard rebalancing
/ci:ask-sippy "What is the average runtime for job periodic-ci-openshift-release-master-nightly-4.19-e2e-aws-ovn-stable-01 over the last 14 days?"

# Get test run details
/ci:fetch-test-runs --test-name "<test name>" --release "4.19"
```

### Initializing Labels for an Existing Repo

When a repo adopts the new suite model for the first time, its existing
tests have no `ACTIVE`/`STABLE` labels. This one-time bootstrap classifies
the existing conformance tests by their historical stability: tests that are
already reliably passing are seeded as **stable**, and everything else
(lower pass rate) is seeded as **active** so it gets a stabilization window
before it can graduate.

This uses the same Sippy queries and threshold comparisons as ongoing
promotion — it just runs across the whole existing conformance set at once.

**Procedure:**

1. **Enumerate the existing conformance tests** to be classified. On origin
   the classic `openshift/conformance/*` suites are **not** queryable via
   `list --suite` (that returns "no such suite" — it only knows OTE-registered
   suites). Current membership lives in the legacy `[Suite:...]` name tag, so
   filter `list tests -o names` on it (see the origin `KUBECONFIG` caveat in
   [Listing Tests](#listing-tests-and-their-metadata)):
   ```bash
   KUBECONFIG=/tmp/fake-kubeconfig ./openshift-tests list tests -o names \
     | grep 'Suite:openshift/conformance/parallel' \
     | sed 's/ \[Suite:[^]]*\]//' > /tmp/parallel-tests.txt
   KUBECONFIG=/tmp/fake-kubeconfig ./openshift-tests list tests -o names \
     | grep 'Suite:openshift/conformance/serial' \
     | sed 's/ \[Suite:[^]]*\]//' > /tmp/serial-tests.txt
   ```
   **Always take names from `list` output, never from memory** — a fabricated
   or slightly-off name silently matches zero specs (`NameContains` finds
   nothing), so the label is never applied and no error is raised.

2. **Pull historical stability for each test** from Sippy over a sustained
   window (recommend the last 30 days on the current release, and confirm the
   test has enough runs — e.g. >= 14 — to be meaningful). Use `ci:ask-sippy`
   / `ci:fetch-test-runs`. Record pass rate, run count, and flake count.

3. **Classify by pass rate** against the lifecycle thresholds:

   | Historical pass rate (30d, sufficient runs) | Initial label | Rationale |
   |---------------------------------------------|---------------|-----------|
   | >= 99.5% | `STABLE` + `SHARD-01` | Already meets the graduated bar; seed directly into a stable shard, blocking |
   | < 99.5% (this is "the rest" of conformance) | `ACTIVE` + `SHARD-01` + `Informing()` | Not yet stable; start in active AND informing so failures don't block during the stabilization window |
   | Insufficient runs / no data | `ACTIVE` + `SHARD-01` + `Informing()` | Not enough signal to trust; treat as new/stabilizing |

   The intent stated for this bootstrap: **mark the high-passing conformance
   tests as `stable` (blocking), and mark every not-yet-stable test as both
   `active` and `informing` initially.**

   **`Informing` is applied at initialization, not derived from `ACTIVE`.**
   Informing (does the failure block?) and lifecycle (`ACTIVE`/`STABLE`) are
   orthogonal axes. At bootstrap, every not-yet-stable test is labeled both
   `ACTIVE` and `Informing`; graduation to blocking is a later, deliberate
   inline edit that **removes `Informing` while keeping `ACTIVE`** (the
   "blocking, proven in active, not yet stable" state — see the
   [lifecycle flow](#lifecycle-flow-informing--blocking--graduated)). Because
   informing is its own inline signal, a rebuild never re-derives or clobbers
   it. Never compute informing from the `ACTIVE` label in framework code — that
   makes the ACTIVE-but-blocking state unreachable and silently un-graduates
   tests on every build.

4. **Assign shards — seed everything into `SHARD-01` only.** At initialization,
   put every stable test in `SHARD-01` and every active test in `SHARD-01`
   (stable and active are independent shard namespaces, so each has its own
   single starting shard). **Do not invent `SHARD-02`+ during initialization.**

   Sharding is a **runtime-packing** decision, not a stability decision — a
   shard exists to cap one CI job's wall-clock, so a second shard is only
   justified once the *full* labeled population and *real per-test runtimes*
   show `SHARD-01`'s projected runtime exceeds the target budget. Neither is
   known at bootstrap (you have the classified set, not measured runtimes), and
   abundant pass-rate data justifies `STABLE`, never an extra shard. Introduce
   `SHARD-02`+ later, deliberately, via the
   [Rebalancing Shards](#rebalancing-shards) workflow using per-test runtime
   from Sippy — not here.

5. **Emit the labels** in the repo's chosen labeling location
   (see [Labeling Location by Repo](#labeling-location-by-repo)):
   - **`openshift/origin`** (and OTE component repos): apply the lifecycle
     labels **inline at each test's definition** as plain Ginkgo labels on
     the `g.It`/`g.Describe` node. A stable test gets
     `g.It("node-logs", g.Label("STABLE", "SHARD-01"), func(){ … })`; a
     not-yet-stable test gets **both** the active label and informing, e.g.
     `g.It("node-logs", g.Label("ACTIVE", "SHARD-01"), ote.Informing(), func(){ … })`.
     OTE copies the labels into `spec.Labels` at build time. Do **not** collect
     them in a centralized name-matched map and do **not** add a separate
     labeling function; the label lives with the test.

     **Older-OTE fallback (no `Informing()` decorator).** Some component repos
     pin an OTE version where `spec.Lifecycle` is a plain field and there is no
     `ote.Informing()` / `spec.Informing()` decorator to call on a Ginkgo node.
     There, signal informing with an inline **`Informing` label** and translate
     it once in `main.go` — keeping informing per-test and explicit:

     ```go
     g.It("...", g.Label("ACTIVE", "SHARD-01", "Informing"), func(){ … })

     // main.go, after building specs, before AddSpecs:
     specs.Walk(func(spec *et.ExtensionTestSpec) {
         if spec.Labels.Has("Informing") {
             spec.Lifecycle = et.LifecycleInforming
         }
     })
     ```

     Walk on the **`Informing`** label, never on `ACTIVE` — deriving informing
     from `ACTIVE` makes the graduated-to-blocking-but-not-yet-stable state
     unreachable and re-marks tests informing on every build.
   - For `openshift/kubernetes`: add the assignments to the single
     centralized labeling file (see below), NOT inline in upstream tests
     (inline edits conflict on every rebase).

   Register the label-driven suites (`openshift/active-01`, `stable-01`,
   `stable-serial-01`, …) once with `AddGlobalSuite` (framework wiring, not
   per-test), filtering on the labels. Split parallel vs. serial by matching
   `[Serial]` on **name OR label**
   (see [Minimal Conformance Is Label-Driven](#minimal-conformance-is-label-driven)).

6. **Apply the `Conformance` label to the agreed minimal-conformance set**:
   add the plain `Conformance` label (the same ginkgo-style label upstream
   uses — never a `[Conformance]` name annotation) inline on the `g.It` node
   of each test that belongs in minimal conformance, alongside its
   `STABLE`/`ACTIVE` + `SHARD-NN` labels. This is what
   puts them in `openshift/conformance/*/minimal` — membership is label-driven
   (see [Minimal Conformance Is Label-Driven](#minimal-conformance-is-label-driven)).
   The `Conformance` label is independent of `ACTIVE`/`STABLE`: labeling a
   test `STABLE` does not add or remove `Conformance`.

   > The *mechanism* (label-driven minimal conformance via the shared
   > `Conformance` label) is decided; **which tests** get the label
   > downstream is not yet finalized. Until that set is agreed, seed a small
   > placeholder subset and flag it for review rather than guessing the full
   > list.

7. **Validate**: rebuild, list each new suite, and confirm the counts and
   membership look right before opening the PR. The new suites ARE
   OTE-registered, so `list tests --suite` works for them (unlike the classic
   suites in step 1):
   ```bash
   make build WHAT=cmd/openshift-tests
   K=/tmp/fake-kubeconfig   # origin only; see Listing Tests caveat
   KUBECONFIG=$K ./openshift-tests list tests --suite openshift/stable-01 -o names
   KUBECONFIG=$K ./openshift-tests list tests --suite openshift/active-01 -o names
   KUBECONFIG=$K ./openshift-tests list tests --suite openshift/active-serial-01 -o names
   ```
   Spot-check that serial tests landed in the `*-serial-*` suites, not the
   parallel ones — a label-only `[Serial]` qualifier misroutes tests whose
   serial marker is only in the name.

> Note: this is a *bulk, one-time* operation per repo. It is deliberately
> conservative — when in doubt (low data, borderline pass rate), classify a
> test as `active` rather than `stable`, because active provides a review gate
> before the test can become a permanent graduated test.

### Promoting Tests Between Suites

When promoting a test from `active` to `stable`:

1. **Check stability**: Query Sippy for the test's pass rate over the last
   30 days. Require >= 99.5%.
2. **Check age**: The feature should be GA for at least one release.
3. **Update labels**: Replace `ACTIVE` label with `STABLE` and assign a
   `SHARD-NN` (or change the feature suite's `Parents` from `active-*` to
   `stable-NN`).
4. **Choose shard**: Pick the shard with the lowest total runtime to keep
   jobs balanced.

### Rebalancing Shards

When shard runtimes diverge significantly:

1. **Gather runtime data**: Query Sippy for average job runtime of each shard.
2. **Gather per-test runtimes**: Get runtime for each test in the overloaded
   shard.
3. **Calculate moves**: Identify tests to move from the heaviest shard to the
   lightest.
4. **Update shard labels**: Change `SHARD-NN` labels on the tests being moved.
5. **Target balance**: Aim for all shards within 10% of mean runtime.

When all existing shards are full (runtimes too long even after
rebalancing), create a new shard:

1. Define a new suite `openshift/stable-NN+1`
2. Create a corresponding CI job
3. Move tests from overloaded shards into the new shard

### Migrating Tests Out of Conformance

Because minimal conformance is label-driven, migrating a test out of
conformance means **removing its `Conformance` label** — the test then
leaves `openshift/conformance/*/minimal` automatically. Its lifecycle labels
(`ACTIVE`/`STABLE` + `SHARD-NN`) keep it running in the active/stable
hierarchy; you are only removing the conformance designation, not the test.

1. List the current members of minimal conformance:
   ```bash
   ./openshift-tests list --suite openshift/conformance/parallel/minimal
   ```
2. For each test, check if it's truly a core smoke test or if it tests a
   specific feature.
3. For a feature-specific test, **remove the `Conformance` label** — delete
   it from the `g.Label(...)` list on the test's own node (in o/k, remove the
   test's entry from the centralized labeling file). Ensure it still carries
   an `ACTIVE` or `STABLE` label so it continues to run in a feature/lifecycle
   suite.
4. Rebuild and confirm the test no longer appears in
   `openshift/conformance/*/minimal` but still appears in its lifecycle suite.
5. Verify the test still runs in at least one CI job after the change.

## Labeling Location by Repo

Where OTE labels are applied differs by repository. For every repo that owns
its test source, the rule is: apply the lifecycle labels **inline at the test
definition itself** — on the Ginkgo node (`g.It`/`g.Describe`) via
`g.Label(...)` — so the label lives where the test is defined. `openshift/kubernetes`
is the one exception (it rebases from upstream and must not touch upstream
sources), covered below.

### `openshift/origin` and Component Repos: Label Inline at the Test Definition

Add the lifecycle labels as plain Ginkgo labels on the test's own node. OTE
copies a spec's Ginkgo labels verbatim into `spec.Labels` at build time
(`BuildExtensionTestSpecsFromOpenShiftGinkgoSuite`), so a label placed on the
`g.It` becomes an OTE label with no name annotation:

```go
// origin — test/extended/authentication/front_proxy.go
// Lifecycle labels live at the definition: Conformance (minimal conformance),
// STABLE + SHARD-01 (stable-01 suite). Plain ginkgo labels, no name change.
g.It("should succeed", g.Label("Conformance", "STABLE", "SHARD-01"), func() {
    // ...
})

// origin — test/extended/cli/admin.go — an active (non-conformance) test
g.It("node-logs", g.Label("ACTIVE", "SHARD-01"), func() {
    // ...
})
```

Do **not** collect these in a centralized name-matched map and do **not**
introduce a separate labeling function — the label belongs next to the test.
(The existing `pkg/test/extensions/labels.go` `addLabelsToSpecs` map remains
for the legacy bracketed tags like `[Serial]` it already manages; new
lifecycle labels go inline instead.)

The suite *registration* is still framework wiring, not per-test: register
the label-driven lifecycle suites once via `AddGlobalSuite` (in origin,
`addLifecycleSuites` in `pkg/test/extensions/suites.go`, called from
`InitializeOpenShiftTestsExtensionFramework` in `binary.go`). Their
`Qualifiers` — including the `.../minimal` suites' `labels.exists(l,
l=="Conformance")` — select on the labels the tests carry inline.

### `openshift/kubernetes`: One Centralized Labeling File

`openshift/kubernetes` periodically **rebases from upstream kubernetes**.
Labeling upstream test definitions inline would create a merge conflict on
every rebase. Therefore, for o/k, **do NOT label tests inline**. Instead,
apply ALL OpenShift-specific test labels in a single dedicated file that
lives in OpenShift carry code (never touched by upstream), matching tests by
name.

**Location (recommended):**
`openshift-hack/cmd/k8s-tests-ext/labels.go` — specifically its
`addLabelsToSpecs(specs et.ExtensionTestSpecs)` function.

This is the modern, OTE-native successor to the old
`openshift-hack/e2e/annotate/rules.go` mechanism (which appended
`[Suite:...]` / `[Serial]` / `[Disabled:...]` tags by name). That `annotate`
package has been **removed** from o/k `master`; name-based labeling now lives
in the `openshift-hack/cmd/k8s-tests-ext/` OTE extension. o/k is already
wired into OTE and already uses the enhancement's suite names — its
`AddSuite` calls in `k8s-tests.go` define e.g.
`kubernetes/conformance/parallel/minimal` with
`Parents: []string{"openshift/conformance/parallel/minimal"}`.

**Mechanism.** `labels.go` holds a `map[string][]string` of label → list of
test-name substrings, and applies each with OTE `Select`/`SelectAny` +
`AddLabel`. To add `ACTIVE` / `STABLE` / `SHARD-NN`, extend this map (or add
a parallel map in the same file):

```go
// openshift-hack/cmd/k8s-tests-ext/labels.go
func addLabelsToSpecs(specs et.ExtensionTestSpecs) {
    var namesByLabel = map[string][]string{
        // ...existing entries ([Serial], [sig-node], [DedicatedJob], ...)...
        "STABLE":   { "[sig-network] Services should serve endpoints", /* ... */ },
        "SHARD-01": { "[sig-network] Services should serve endpoints", /* ... */ },
        "ACTIVE":   { "[sig-storage] some lower-pass-rate test", /* ... */ },
    }
    for label, names := range namesByLabel {
        var selectFunctions []et.SelectFunction
        for _, name := range names {
            selectFunctions = append(selectFunctions, et.NameContains(name))
        }
        specs.SelectAny(selectFunctions).AddLabel(label)
    }
}
```

The corresponding suite `Qualifiers` (CEL) go in the `AddSuite` calls in
`openshift-hack/cmd/k8s-tests-ext/k8s-tests.go`, e.g.
`labels.exists(l, l=="STABLE") && labels.exists(l, l=="SHARD-01")`.

**Minimal conformance in o/k is already label-driven** via the upstream
`Conformance` label — the `kubernetes/conformance/*/minimal` suites in
`k8s-tests.go` already filter on `labels.exists(l, l == "Conformance")`, so
you do NOT re-label upstream conformance tests. This is the reference model
the downstream repos mirror with their own `Conformance` label (see
[Minimal Conformance Is Label-Driven](#minimal-conformance-is-label-driven)).
The only reason to touch conformance membership from `labels.go` is for
OpenShift-carry tests that are not upstream but should still be minimal
conformance — apply `Conformance` to those in the same map.

**Why this is rebase-safe:**

- The whole `openshift-hack/` tree is OpenShift carry code — upstream
  kubernetes has no such directory, so upstream commits never touch it and
  cannot conflict.
- Labeling is done out-of-band by test-name matching at extension-build time
  (`addLabelsToSpecs(specs)` runs on already-built specs). The upstream
  Ginkgo definitions under `test/e2e/...` are never edited, so upstream churn
  there cannot conflict with the labels.

**Related files in the same package** (keep concerns separated — put pure
label mapping in `labels.go`):

- `k8s-tests.go` — extension `main()`, `NewExtension`, `AddSuite` (suite
  definitions + CEL `Qualifiers`), `BuildExtensionTestSpecsFrom...`, `AddSpecs`
- `disabled_tests.go` — `filterOutDisabledSpecs()` (name-matched removal)
- `environment_selectors.go` — `addEnvironmentSelectors()` (skips conditioned
  on platform/topology/network/feature-gate)
- `openshift-hack/e2e/include.go` — pulls upstream e2e packages into the binary

## Test Requirements Checklist

Before assigning a test to any suite, verify:

- [ ] Test has a `[Jira:Component]` tag or `ci-test-mapping` entry for ownership
- [ ] Test produces deterministic pass/fail results (no pass-only-on-failure)
- [ ] Test name is stable (no dynamic content like pod UIDs or timestamps)
- [ ] Test has `[sig-XYZ]` tag for area grouping
- [ ] Test has appropriate `[FeatureGate:XYZ]` or `[Feature:XYZ]` annotations
- [ ] Test duration is under 5 minutes (longer tests need architect approval)
- [ ] Parallel tests are non-disruptive and can run alongside any other test
- [ ] Serial tests restore cluster to original state after completion
- [ ] Test passes at >= 99% for blocking status (or has `Informing()` lifecycle)

## Recommended Payload Jobs for Validation

After changing suite membership, run payload jobs to validate:

For parallel suite changes:
```
/payload-job periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance
/payload-job periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv6
/payload-job periodic-ci-openshift-release-master-ci-4.22-e2e-aws-upgrade-ovn-single-node
```

For serial suite changes:
```
/payload-job periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance-serial
/payload-job periodic-ci-openshift-release-master-nightly-4.22-e2e-aws-ovn-single-node-serial
```

## Examples

### Example 1: Add a New Test to the Active Suite

Labels live inline on the node — `ACTIVE` + a shard, plus `Informing()`
while it stabilizes:

```go
var _ = g.Describe("[sig-storage] CSI volume snapshot", func() {
    g.It("should create and restore a volume snapshot",
        g.Label("ACTIVE", "SHARD-01"), ote.Informing(), func() {
        // test implementation
    })
})
```

### Example 2: Promote a Test from Active to Stable

After confirming >= 99.5% pass rate and feature GA, edit the labels on the
test's own node — swap `ACTIVE` for `STABLE`, drop `Informing()`:

```go
var _ = g.Describe("[sig-storage] CSI volume snapshot", func() {
    g.It("should create and restore a volume snapshot",
        g.Label("STABLE", "SHARD-01"), func() {
        // test implementation
    })
})
```

### Example 3: Define a Feature Suite Composing into Active

```go
ext.AddSuite(e.Suite{
    Name:    "mycomponent/csi-snapshots",
    Parents: []string{"openshift/active-01"},
    Qualifiers: []string{
        `labels.exists(l, l=="CSI-SNAPSHOTS")`,
    },
})
```

Later, when promoting to stable:

```go
ext.AddSuite(e.Suite{
    Name:    "mycomponent/csi-snapshots",
    Parents: []string{"openshift/stable-02"},
    Qualifiers: []string{
        `labels.exists(l, l=="CSI-SNAPSHOTS")`,
    },
})
```

### Example 4: Set Up a Spot-Check Suite

For a feature requiring etcd vertical scaling (uncommon cluster config):

```go
// Define the spot check suite
ext.AddSuite(e.Suite{
    Name: "openshift/spot-check/etcd-scaling",
    Qualifiers: []string{
        `labels.exists(l, l=="SPOT-CHECK-ETCD-SCALING")`,
    },
})

// Label the test inline at its definition
g.It("vertical scaling", g.Label("SPOT-CHECK-ETCD-SCALING"), func() { /* ... */ })
```

CI job config (development phase, ~2x/day). Pass `--cluster-stability` via
`TEST_ARGS` so sensitive monitortests flake instead of failing the job (see
[Spot-Check Suites](#spot-check-suites)):
```yaml
- as: e2e-aws-etcd-scaling
  cron: "0 6,18 * * *"
  steps:
    env:
      TEST_SUITE: openshift/spot-check/etcd-scaling
      TEST_ARGS: "--cluster-stability=SpotCheck"
```

After GA + 1 release, reduce to monthly:
```yaml
  cron: "0 6 1 * *"  # 1st of each month
```

Component Readiness will flag if no pass is recorded within 30 days.

### Example 5: Rebalance Shards

```
User: The stable-01 job is running 45 minutes but stable-02 only runs 25 minutes. Rebalance them.

Steps:
1. Query per-test runtimes in stable-01 via Sippy
2. Identify ~10 minutes of tests to move from stable-01 to stable-02
3. Update SHARD-01 → SHARD-02 labels on selected tests
4. Verify both shards are ~35 minutes after the change
```

### Example 6: Initialize Labels for an Existing Repo

```
User: We're adopting the new suite model in this repo. Bootstrap labels for the existing conformance tests.

Steps:
1. Enumerate members of the classic conformance suites. On origin the classic
   suites are NOT OTE-queryable, so read the [Suite:...] name tag:
   ./openshift-tests list tests -o names | grep 'Suite:openshift/conformance/parallel'
2. For each test, query Sippy for 30d pass rate + run count
3. Classify: pass rate >= 99.5% → STABLE (blocking); every not-yet-stable test
   (lower pass rate OR insufficient data) → ACTIVE + Informing()
4. Seed everything into SHARD-01 (stable→SHARD-01, active→SHARD-01). Do NOT
   invent SHARD-02+ at init — sharding is runtime-packing, split later via the
   rebalancing workflow once real per-test runtimes exceed one shard's budget
5. Add the labels inline on each test's g.It node (origin & component repos):
   STABLE + SHARD-01 for graduated tests; ACTIVE + SHARD-01 + ote.Informing()
   for not-yet-stable ones (on older-OTE repos with no Informing() decorator,
   use an inline "Informing" label and translate it to spec.Lifecycle in
   main.go — walk the Informing label, never ACTIVE). For o/k, add name-matched
   entries to its centralized carry labels.go instead (rebase-safe). Plain
   labels only, no name annotation. Register the lifecycle suites once via
   AddGlobalSuite.
6. Add the plain Conformance label inline on the g.It node of each test in the
   agreed minimal set (same label upstream uses; the exact downstream set is
   not yet finalized) so they land in conformance/*/minimal
7. make build; list each new suite; confirm counts (do NOT open a PR — the
   maintainer handles GitHub interaction)
```

## Notes

- The `openshift/conformance` suites should shrink over time into
  `openshift/conformance/*/minimal`. Membership there is label-driven: a
  test is in minimal conformance because it carries the plain `Conformance`
  label (the same ginkgo-style label upstream uses; downstream repos reuse
  it, no `[Conformance]` annotation), filtered by the suite's `Qualifiers` —
  not because of a curated name list or its lifecycle phase. The mechanism is
  decided; the exact downstream membership is not yet finalized.
- Feature suites compose into parent suites via the OTE `Parents` field.
  Move a feature between suites by updating its parent.
- Always use OTE labels (inline `g.Label(...)` on the test's node) and suite
  `Qualifiers` (CEL expressions) for suite membership. This is the
  forward-looking approach preferred over `[Suite:...]` tags in test names.
- Both `active` and `stable` are explicitly sharded (`active-01`,
  `stable-01`, `stable-02`, ...). Explicit sharding is used instead of
  auto-sharding because auto-sharding does not work in constrained
  environments like vSphere.
- Tests ported from `openshift-tests-private` should include the `[OTP]`
  annotation. Tests ported from Level 0 should include `[Level0]`.
- Use `Informing()` lifecycle for new tests during their 2–3 sprint
  stabilization period.
- For `openshift/kubernetes`, keep all OpenShift-specific labeling in the
  single centralized file to avoid rebase conflicts with upstream.

## See Also

- Enhancement: openshift/enhancements — "Test Suites"
  (`enhancements/testing/test-suites.md`) — authoritative source for this skill
- Related Skill: `ci:ask-sippy` (query test pass rates and job runtimes)
- Related Skill: `ci:fetch-test-runs` (get detailed test run data)
- Related Skill: `ci:fetch-test-report` (get test reports for a job)
- Related Skill: `ci:oc-auth` (authenticate for Sippy access)
