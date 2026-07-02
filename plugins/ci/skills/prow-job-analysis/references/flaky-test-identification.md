# Flaky Test Identification Reference

The triage layer for a failing test. Before debugging a failure as a product bug, decide
which of three things broke: the **infrastructure**, the **product** (a real regression),
or the **test's own determinism** (a flake). Misclassifying a flake or infra failure as a
regression wastes work on the wrong repo; misclassifying a regression as a flake ships a bug.
This reference is the decision methodology — the deep-dive references own each root-cause class.

## When to Use

- A failure does not reproduce on retry, or a `/retest` passes
- The failure looks unrelated to the PR's diff
- Deciding whether to investigate, retry, or quarantine a test
- Confirming a suspected regression is real before filing a bug or reverting
- The same test fails in one job but passes elsewhere

**Use a different reference for:** a failure you have already confirmed is a real test/product
issue → [test-extension-binaries.md](test-extension-binaries.md); the mechanics of
statistical verdicts across parallel runs → [aggregated.md](aggregated.md).

---

## The Three-Way Classification

Every failing `<testcase>` is exactly one of these. Identify the class first; it decides
which repo to open.

| Class | What broke | Fix lives in | Primary reference |
|-------|-----------|--------------|-------------------|
| **Infrastructure** | CI / cloud / shared env, before or around the test | `openshift/release`, cloud account, Test Platform | [ci-infrastructure-changes.md](ci-infrastructure-changes.md), [cloud-provider-errors.md](cloud-provider-errors.md) |
| **Product regression** | The code under test | Product repo / the PR | [test-extension-binaries.md](test-extension-binaries.md), [install/general.md](install/general.md), [upgrade.md](upgrade.md) |
| **Test-code flake** | The test's own determinism (races, timing, ordering) | The test source | this reference |

Infrastructure failures and flakes **both** pass on retry, so a retry-pass alone does not
prove the test is at fault. Separate them by **scope** (how many jobs) and **reason** (the
ci-operator tag), covered below. Product regressions rarely pass on retry.

### Fast triage signals

| Signal | Infra | Regression | Flake |
|--------|:-----:|:----------:|:-----:|
| Passes on retry | Yes | Rarely | Yes |
| Same failure in 3+ unrelated jobs at once | Yes | No | No |
| Fails on all platforms **and** correlates with a PR | No | Yes | No |
| Fails on one platform / variant only | Possible | Possible | Possible |
| ci-operator failure reason is set (table below) | Yes | No | No |
| Sippy pass rate sits in an 80–99% band | — | — | Yes |
| Failure predates the PR (Sippy / search.ci) | — | No | Known flake |
| Identical error string on every occurrence | Sometimes | Yes | No (varies) |

---

## Infrastructure: the "reason" and the "3+ jobs" heuristics

### A ci-operator failure reason means the test never got a fair run

When ci-operator fails before or around test execution, it tags a machine-readable **reason**
(visible in the build-log summary and the job's Prow/Sippy failure classification). A set
reason routes you **out** of this reference — the environment failed, not the product test.

| Reason | Phase | Meaning | Deep dive |
|--------|-------|---------|-----------|
| `importing_release` | release setup | Base release payload could not be imported (tag missing, registry slow) | [ci-infrastructure-changes.md](ci-infrastructure-changes.md) |
| `creating_release_images` | release setup | Release payload assembly failed | [ci-infrastructure-changes.md](ci-infrastructure-changes.md) |
| `pod_pending` | scheduling | Step pod never scheduled (build-cluster capacity) | [ci-infrastructure-changes.md](ci-infrastructure-changes.md), [resource-exhaustion.md](resource-exhaustion.md) |
| `acquiring_cluster_claim` / `utilizing_cluster_claim` | cluster claim | Hive `ClusterClaim` never became ready | [cloud-provider-errors.md](cloud-provider-errors.md) |

Also `acquiring_lease`, `building_image`, `resolving_step` — see
[ci-infrastructure-changes.md](ci-infrastructure-changes.md). Action: re-run the job; if it
recurs fleet-wide, escalate to Test Platform. Do not debug the test.

### Same failure across 3+ distinct jobs = shared infrastructure

One test (or error string) failing across **three or more distinct job names**
(different platforms, repos, or configs) at the same time is almost never a per-test bug —
a shared dependency broke: CI registry, lease pool, cloud region, a step-registry change, or
the payload. Confirm breadth before blaming the test:

```text
# search.ci — is this error hitting many jobs right now?
https://search.ci.openshift.org/?search=<error-string>&maxAge=48h&type=junit
```

- Hits across unrelated jobs/repos → infrastructure
  ([ci-infrastructure-changes.md](ci-infrastructure-changes.md),
  [cloud-provider-errors.md](cloud-provider-errors.md)).
- Hits confined to one job or one PR → stay in this reference.

Inverse of the product-bug heuristic in
[Test-name pattern analysis](#test-name-pattern-analysis-breadth-across-platforms) below.

---

## Baseline flakiness with Sippy

Sippy aggregates pass rates across all CI runs — the authority on "is this test already
unreliable?" Look it up before attributing a failure to a change.

- Test details: `https://sippy.dptools.openshift.org/sippy-ng/tests/{release}/details?test={test-name}`
- Skills: `fetch-test-report` / `ci:fetch-test-report` (pass rate, test ID, Jira component);
  `ci:query-test-result`; `fetch-test-runs` (per-run outputs for similarity analysis);
  `ci:list-unstable-tests` (tests below a 95% pass rate).

| Sippy pass rate | Reading |
|-----------------|---------|
| ~100%, stable, then this run failed | Real signal — regression or a fresh flake; investigate |
| 80–99% across many runs | Established flake — this failure is likely noise |
| Below ~80% and steady | Chronically broken / quarantine candidate; failure ≠ your change |
| ~100% then a step drop starting at a date | Regression — correlate the date with merges |

A step-drop from a stable ~100% baseline is the strongest regression signal; a wide, stable
80–99% band is the strongest flake signal.

## Known flake (pre-existing)?

Before attributing a failure to the PR under investigation, prove the test was healthy
**before** it:

1. **Sippy trend** — did the pass-rate drop begin before the PR's merge/run date? An earlier
   drop means the PR did not cause it.
2. **search.ci history** — the same failure in periodics predating the PR is pre-existing:
   ```text
   https://search.ci.openshift.org/?search=<test-name-or-error>&maxAge=336h&type=junit
   ```
3. **Existing bug** — search Jira (`OCPBUGS`) for the test name; an open flake bug confirms
   known-flaky status.
4. **In-run flake marker** — the same test both fails and passes within this one run (see
   [JUnit interpretation](#junit-interpretation)) = it flaked here, not a hard failure.

If any of these holds, the PR did not cause the failure.

---

## Test-name pattern analysis (breadth across platforms)

The cross-platform breadth of a **single test** separates product bugs from environment noise:

| Pattern | Most likely | Action |
|---------|-------------|--------|
| Same test fails across many platforms (aws + gcp + azure + metal) | Product bug — platform-independent code path | Treat as a regression; find the common PR / payload |
| Same test fails on **one** platform only | Environment / flake — cloud capacity, timing, that CNI/topology | Check that platform's infra ([cloud-provider-errors.md](cloud-provider-errors.md), [networking.md](networking.md), [resource-exhaustion.md](resource-exhaustion.md)) |
| Fails only in one variant (`proxy`, `fips`, `sno`, `ipv6`) | Variant-specific product path or that variant's known races | Check the matching reference / variant |
| Fails only in one job on one PR | Product change in the PR, or a fresh flake | Diff the PR; check the Sippy baseline |

Inverse of the infra "3+ jobs" heuristic: there, *many different tests/jobs* share one failure
(shared infra); here, *one test* fails across many platforms (shared product code path).

---

## Known flake categories

### Timing-sensitive

Hardcoded sleeps, tight poll intervals, fixed deadlines, or wall-clock assumptions. Grep the
test/step log:

```text
context deadline exceeded
timed out waiting for( the)? condition
[Tt]imed out after .*s
```

These pass or fail inconsistently across fast/slow machines and fail more under build-cluster
load. Confirm with Sippy (banded pass rate) and interval timing ([disruption.md](disruption.md)).

### Cloud-specific capacity

A test or step failing on **one** cloud during provisioning or scaling — AZ capacity, quota,
throttling — is environment, not the test. Signatures (`InsufficientInstanceCapacity`,
`ZONE_RESOURCE_POOL_EXHAUSTED`, `SkuNotAvailable`, `RequestLimitExceeded`) and full triage:
[cloud-provider-errors.md](cloud-provider-errors.md).

### Proxy / mirror races

Disconnected / proxy / ipv6 jobs: pods pull before ICSP/IDMS or the mirror is ready →
transient `ImagePullBackOff`, `manifest unknown`, or `i/o timeout` that self-heal; a
proxy/SOCKS pod restart blips connectivity. Clears on retry = race, not product. Full pull
chain: [networking.md](networking.md#image-mirroring-race-conditions).

### State-leaking / order-dependent

A test that relies on prior-test state, or leaks namespaces/CRDs/cluster-scoped objects,
flakes based on run order or parallelism. Signature: fails in the full suite, passes in
isolation; the failure mentions leftover or missing resources.

---

## Aggregated jobs: the statistical flake-vs-regression verdict

Aggregated jobs (`aggregated-` prefix) run N copies of a job (usually 10) and apply
statistics — the definitive separator of flake from regression. Full treatment:
[aggregated.md](aggregated.md). The thresholds that drive the verdict:

- **Minimum attempts** — at least ~6 of 10 runs must complete, or the result is
  *insufficient data*, not a real failure.
- **Flake rate ~10%** with **minimum pass rate ~90%** — failures under the flake rate are
  tolerated as flakes rather than flagged as regressions.

| Ratio (of completed runs) | Verdict |
|---------------------------|---------|
| 0 pass / 10 fail | Strong regression |
| 3 pass / 7 fail | Regression |
| 8 pass / 2 fail | Flake — compare the 2 error strings for a common cause |
| 10 pass / 0 fail | Not a regression |
| 5 pass / 0 fail / 5 missing | Insufficient data — investigate why 5 did not complete (infra), not the test |

**Non-deterministic test presence** — a test present in only some completed runs (message
like `Passed 1 times, failed 0 times ... require at least 6 attempts`) is a test bug
(conditional or non-deterministic registration), not a product regression. Distinguishing it
from insufficient-data: [aggregated.md](aggregated.md).

---

## Symptom labels: correlation, not cause

`job_labels/*.json` are machine-detected environmental observations (e.g. high CPU or disk
pressure during the run):

```text
gs://test-platform-results/{bucket-path}/artifacts/job_labels/*.json   # skip label-summary.html
```

A symptom **explains** how a flake could occur (CPU starvation → OVS stall → test timeout)
but does **not** prove the test is correct, nor attribute cause on its own. Use it to support
a flake hypothesis when it temporally overlaps the failure window; never cite it as the root
cause by itself. (Also covered in [ci-infrastructure-changes.md](ci-infrastructure-changes.md).)

---

## JUnit interpretation

Test results are the source of truth over an alarming build-log line. openshift-tests writes
`junit_e2e_*.xml`; ci-operator writes `junit_operator.xml`; install writes `junit_install.xml`.

```bash
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/junit*.xml"
```

### Fields that matter

- `<testsuite tests= failures= skipped= time=>` — run totals. openshift-tests does **not**
  emit a standard `flakes` attribute; flakes are encoded as duplicate testcases (below).
- `<testcase name= classname= time=>` — one test. The child element decides status:
  - `<failure>` / `<error>` — did not pass; the `message` and body are the evidence.
  - `<skipped>` — excluded by an environment selector; **not** a failure.
  - none — passed.

### pass / fail / skip / flake

- **skip ≠ fail** — skips are environment-gated (platform, feature-gate, topology). A test
  that used to run and now skips is a coverage change that can hide a regression, not a pass.
- **In-run flake convention** — openshift-tests retries a failed test; if the retry passes,
  the suite tolerates it. In the XML the same `name` then appears **twice**: once with a
  `<failure>` and once passing. Same-name fail+pass in one file = **flaked this run**, not a
  hard failure. Sippy derives its flake counts from exactly this pattern.
- A `<failure>` that also has a passing twin did not fail the suite — trust the JUnit verdict.

### "Test failed" vs "test infrastructure failed"

Not every `<failure>` is the product under test. Synthetic / harness testcases represent the
scaffolding, and their failure is an infra signal:

| Testcase (synthetic) | Means | Class |
|----------------------|-------|-------|
| `Run multi-stage test pre/test/post phase` | ci-operator phase wrapper | Setup/infra, not the product test |
| `[sig-trt] ... extension binary ... should load successfully` | Extension extract/protocol failure | Test infra — [test-extension-binaries.md](test-extension-binaries.md) |
| `[sig-arch]` / monitor / invariant testcases | Post-run cluster invariants (disruption, alerts) | Cluster/infra signal, not the named test |
| `ipi-*`, `gather-*` step testcases | Setup / teardown steps | Infra (pre) or informational (post) |
| Real `[sig-x] <feature> should <behavior>` with `<failure>` | The product behavior under test | Product or test-code |

An `<error>` (rather than `<failure>`), or a failure whose message is a
harness/extraction/timeout-before-start error, is test-infrastructure — the product was never
exercised. A `<failure>` inside a genuine product-behavior testcase is the one worth product
investigation.

---

## Triage checklist

1. **Reason set?** A ci-operator failure reason (table above) → infrastructure; re-run, do not
   debug the test.
2. **Breadth?** search.ci — the same error in 3+ unrelated jobs → shared infra; one job/PR →
   continue.
3. **JUnit truth?** Confirm a real product `<testcase>` `<failure>` — not synthetic, not a
   fail+pass flake twin, not a `<skipped>`.
4. **Baseline?** Sippy pass rate — stable ~100% (signal) vs an 80–99% band (flake) vs a
   step-drop at a date (regression).
5. **Pre-existing?** search.ci / Jira before the PR date → known flake, not this change.
6. **Platform breadth?** Many platforms → product bug; one platform/variant →
   environment/flake (route to that reference).
7. **Aggregated?** Apply the ratio + minimum-attempts rules → regression vs flake vs
   insufficient-data.
8. **Symptoms?** `job_labels/*.json` support (do not prove) a flake hypothesis in the failure
   window.

## See Also

- [ci-infrastructure-changes.md](ci-infrastructure-changes.md) — ci-operator reasons,
  lease/registry/step-registry, the infra-vs-product framework, symptom labels
- [aggregated.md](aggregated.md) — statistical thresholds, failure Modes 1/2/3, minimum
  attempts, non-deterministic presence
- [cloud-provider-errors.md](cloud-provider-errors.md) — cloud capacity/quota/claim
  signatures behind one-platform flakes
- [networking.md](networking.md) — image mirror / proxy races, DNS/OVN timing flakes
- [test-extension-binaries.md](test-extension-binaries.md) — extension load/protocol failures
  and their synthetic JUnit
- [disruption.md](disruption.md) — interval timing for timing-sensitive flakes
- [resource-exhaustion.md](resource-exhaustion.md) — CPU/memory/disk pressure behind timeouts
  and OVS stalls
- [hypershift.md](hypershift.md) — failing tests in HCP/hypershift jobs; correlate management
  vs hosted cluster
- [artifacts.md](artifacts.md) — full artifact tree and paths
