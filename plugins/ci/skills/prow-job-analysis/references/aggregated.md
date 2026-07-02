# Aggregated Jobs Reference

Analyze **aggregated Prow CI jobs** — parent jobs that launch multiple child runs in
parallel and run statistical analysis to detect test regressions. Route here whenever a job
name starts with `aggregated-` or its artifacts contain `release-analysis-aggregator`.

> **⚠️ The single most common mistake:** misreading the parent job's artifacts (especially
> `build-log.txt`) as the failure. The parent only aggregates; the real diagnostics live in
> the child runs.

---

## What Are Aggregated Jobs?

An aggregated job is a **parent orchestrator** that:

1. Launches N copies of an **underlying (child) job** in parallel (typically 10 runs)
2. Waits for those child runs to complete
3. Collects JUnit XML results from every child run
4. Performs **statistical analysis** to compare pass rates against a historical baseline
5. Reports which tests have regressed with statistical significance

The parent does **not** install a cluster, run tests, or produce test logs — all testing
happens in the child jobs.

### Why Aggregated Jobs Exist

Single CI runs are noisy: tests flake, infrastructure hiccups, and one failure does not
prove a regression. Running the same suite N times and applying statistical methods detects
whether a test's failure rate has meaningfully increased. This is the primary mechanism for
detecting regressions in OpenShift release payloads.

### Terminology

| Term | Meaning |
|------|---------|
| **Aggregated job** / **parent job** | The orchestrator job that launches child runs and performs statistical analysis |
| **Underlying job** / **child job** / **job run** | An individual test run launched by the aggregated parent |
| **Release analysis aggregator** | The container/step inside the parent job that performs the statistical analysis |
| **junit-aggregated.xml** | The parent's aggregated JUnit XML containing statistical results and links to every child run |
| **Payload tag** | The OCP release payload being tested (e.g., `4.19.0-0.nightly-2025-03-15-010101`) |

---

## How to Identify an Aggregated Job

### 1. Job Name Prefix

The most reliable signal: aggregated job names have an **`aggregated-`** prefix.

Examples of aggregated job names:
```text
aggregated-aws-sdn-upgrade-4.19
aggregated-azure-ovn-upgrade-4.19
aggregated-gcp-ovn-upgrade-4.19
aggregated-hypershift-ovn-conformance-4.22
aggregated-metal-ovn-upgrade-4.19
aggregated-aws-ovn-single-node-upgrade-4.19
```

### 2. Aggregator Container/Step in prowjob.json

Check `prowjob.json` for an `aggregator` container or step. The ci-operator config for
aggregated jobs references a `release-analysis-aggregator` step.

### 3. Artifact Structure

Aggregated jobs have a distinctive artifact layout:
```text
{build-id}/
├── build-log.txt                    # ci-operator orchestration log (NOT test output)
├── prowjob.json                     # Job metadata
└── artifacts/
    ├── release-analysis-aggregator/
    │   └── openshift-release-analysis-aggregator/
    │       └── artifacts/
    │           └── release-analysis-aggregator/
    │               └── {underlying-job-name}/
    │                   └── {payload-tag}/
    │                       ├── junit-aggregated.xml     # THE key artifact
    │                       └── ...
    ├── ci-operator-step-graph.json
    └── ci-operator.log
```

If you see `release-analysis-aggregator` in the artifact tree, the job is aggregated.

---

## The Critical Mistake: Analyzing the Parent's build-log.txt

> **⚠️ NEVER analyze the parent job's build-log.txt as if it contains test output.**

The parent's `build-log.txt` is the ci-operator orchestration log. It contains:
- ci-operator startup and configuration
- Launching the aggregator step
- The aggregator's stdout (summary statistics)
- ci-operator teardown

It does **NOT** contain test execution output, stack traces, E2E test logs, or cluster
state.

On a parent failure, your FIRST action is to find the child job URLs from
`junit-aggregated.xml` and analyze those instead. The parent's build-log.txt may show only:
```text
Aggregation step failed: 3 of 10 tests failed statistical analysis
```
This confirms the aggregation detected regressions but gives no diagnostic data — go to the
child runs.

---

## Parent Job vs Child Job Artifact Structure

### Parent Job Artifacts (Aggregated Orchestrator)

```text
{parent-build-id}/
├── build-log.txt                        # ci-operator log — NOT test output
├── prowjob.json                         # Parent job metadata
├── clone-log.txt
└── artifacts/
    ├── release-analysis-aggregator/
    │   └── openshift-release-analysis-aggregator/
    │       └── artifacts/
    │           └── release-analysis-aggregator/
    │               └── {underlying-job-name}/
    │                   └── {payload-tag}/
    │                       └── junit-aggregated.xml   # Statistical results + child URLs
    ├── ci-operator-step-graph.json
    ├── ci-operator.log
    └── junit_operator.xml               # Phase pass/fail for the aggregator step itself
```

**What the parent has:** Statistical analysis results, links to child runs.
**What the parent lacks:** Test logs, stack traces, cluster state, must-gather, interval files.

### Child Job Artifacts (Actual Test Run)

Each child is a normal (non-aggregated) CI job with the full artifact set:

```text
{child-build-id}/
├── build-log.txt                        # Actual test output with logs and errors
├── prowjob.json
└── artifacts/
    ├── {target}/
    │   ├── openshift-e2e-test/
    │   │   ├── build-log.txt            # E2E test console output
    │   │   └── artifacts/
    │   │       ├── junit/
    │   │       │   ├── junit_e2e_*.xml
    │   │       │   └── e2e-timelines_spyglass_*.json  # Interval/disruption data
    │   │       └── ...
    │   ├── gather-extra/                # Cluster state snapshots
    │   ├── gather-must-gather/          # Must-gather archive
    │   ├── ipi-install-install/         # Installer artifacts
    │   └── ...
    ├── ci-operator-step-graph.json
    └── ci-operator.log
```

**What the child has:** Everything — test logs, stack traces, cluster state, must-gather,
interval files, installer logs, pod logs, events.

---

## Finding Child Job URLs from Parent Artifacts

The `junit-aggregated.xml` is the key artifact — it links to every child run.

### Locating the junit-aggregated.xml

```bash
# Download from the parent job's artifacts
gcloud storage cp \
  "gs://test-platform-results/{parent-bucket-path}/artifacts/release-analysis-aggregator/openshift-release-analysis-aggregator/artifacts/release-analysis-aggregator/{underlying-job-name}/{payload-tag}/junit-aggregated.xml" \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled
```

If you don't know the `{underlying-job-name}` or `{payload-tag}`, use a wildcard search:

```bash
# Find all junit-aggregated.xml files in the parent's artifacts
gcloud storage ls \
  "gs://test-platform-results/{parent-bucket-path}/artifacts/release-analysis-aggregator/**/junit-aggregated.xml"
```

### Extracting Child Job URLs from junit-aggregated.xml

Each `<testcase>` has a `<system-out>` section with YAML listing passes, failures, and skips,
each with details about the individual child runs.

Example structure inside `<system-out>`:

```yaml
passes:
  - jobrunid: "1962527613477982001"
    humanurl: "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn/1962527613477982001"
    gcsartifacturl: "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn/1962527613477982001"
  - jobrunid: "1962527613477982002"
    humanurl: "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn/1962527613477982002"
    gcsartifacturl: "..."
failures:
  - jobrunid: "1962527613477982003"
    humanurl: "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn/1962527613477982003"
    gcsartifacturl: "..."
skips: []
```

**Key fields:**
- `jobrunid` — The build ID of the child run
- `humanurl` — Prow UI URL for the child run (use this for investigation)
- `gcsartifacturl` — Direct GCS browser link to the child's artifacts

Investigate each `humanurl` with normal (non-aggregated) analysis workflows.

### Extracting the Underlying Job Name

The underlying (child) job name **cannot be reliably derived** from the aggregated job name;
extract it from the artifacts:

1. **From the junit-aggregated.xml path** — the directory structure contains it:
   ```text
   artifacts/release-analysis-aggregator/.../release-analysis-aggregator/{underlying-job-name}/{payload-tag}/
   ```

2. **From the `humanurl` in `<system-out>`** — the Prow URL path contains the child job name:
   ```text
   https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{underlying-job-name}/{jobrunid}
   ```

Examples of aggregated → underlying name mappings:

| Aggregated Job | Underlying Job |
|----------------|----------------|
| `aggregated-aws-sdn-upgrade-4.19` | `periodic-ci-openshift-release-main-ci-4.19-e2e-aws-sdn-upgrade` |
| `aggregated-hypershift-ovn-conformance-4.22` | `periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance` |
| `aggregated-metal-ovn-upgrade-4.19` | `periodic-ci-openshift-release-main-ci-4.19-e2e-metal-ipi-ovn-upgrade` |

The naming transformation is **not mechanical** — the underlying job name can come from a
different repo (`openshift-hypershift` vs `openshift-release`), use different naming
conventions, and include segments absent from the aggregated name. Always extract from
artifacts.

---

## JUnit Aggregation: How Child Results Appear in Parent Artifacts

### The junit-aggregated.xml Structure

The aggregated JUnit XML is not a concatenation of child JUnit files. The release analysis
aggregator:

1. Collects JUnit results from all child runs
2. For each unique test name, counts passes, failures, and skips across all runs
3. Compares these counts against a historical baseline
4. Generates one `<testcase>` per test with:
   - Pass/fail/skip counts
   - Statistical significance determination
   - Links to each child run that contributed data

### Example Testcase Entry

```xml
<testcase name="[sig-api-machinery] CustomResourcePublishOpenAPI ... should serve CRD OpenAPI spec"
          classname="aggregated">
  <failure message="Passed 3 times, failed 7 times, skipped 0 times: ...">
    Regression detected: pass rate 30% (3/10) vs historical 98%
  </failure>
  <system-out>
    passes:
      - jobrunid: "1962527613477982001"
        humanurl: "https://prow.ci.openshift.org/..."
        gcsartifacturl: "..."
      - jobrunid: "1962527613477982002"
        humanurl: "https://prow.ci.openshift.org/..."
        gcsartifacturl: "..."
      - jobrunid: "1962527613477982005"
        humanurl: "https://prow.ci.openshift.org/..."
        gcsartifacturl: "..."
    failures:
      - jobrunid: "1962527613477982003"
        humanurl: "https://prow.ci.openshift.org/..."
        gcsartifacturl: "..."
      ...
    skips: []
  </system-out>
</testcase>
```

### What the Failure Message Tells You

The `<failure>` element's `message` attribute contains a summary like:
```text
Passed 3 times, failed 7 times, skipped 0 times: we require at least 6 attempts to have
a chance at success with a flake rate of 10.00% and minimum pass rate of 90.00%
```

This tells you:
- How many times the test passed/failed/skipped across all child runs
- The statistical threshold being applied
- Whether the failure rate exceeds the acceptable flake rate

---

## Failure Modes in Aggregated Jobs

Aggregated jobs have three distinct failure modes. **Determine which mode applies before
diving into individual test analysis** — the investigation strategy differs dramatically
between modes.

### Mode 1: Statistically Significant Test Failure

The test itself fails frequently enough across runs to be flagged as a regression.

- **Signal:** A specific test fails in a majority of runs (e.g., 7 of 10). The failure
  message in junit-aggregated.xml shows a clear pass/fail ratio that exceeds the flake
  threshold.
- **What this means:** A **real regression** — the test consistently fails, so a recent code
  change broke the tested functionality.
- **Action:** Investigate the failing test with normal test analysis:
  1. Pick one or more **failed** child runs from the `failures:` list in `<system-out>`
  2. Navigate to the child run's Prow URL (`humanurl`)
  3. Analyze it as a normal (non-aggregated) job — build-log.txt, JUnit XML, stack traces,
     must-gather, interval files
  4. Confirm the root cause via consistent error patterns across multiple failed child runs
- **Root cause:** Usually a product bug or intentional API/behavior change

### Mode 2: Insufficient Completed Runs

Not enough child runs completed successfully to perform the statistical test. For example,
only 5 of 10 jobs produced results because the other 5 failed to install a cluster.

- **Signal:** Mass test failures across many **unrelated** tests. The failure messages may
  reference insufficient data points. You'll see dozens or hundreds of tests failing, all
  with messages like:
  ```text
  Passed 3 times, failed 0 times, skipped 0 times: we require at least 6 attempts to have
  a chance at success
  ```
  The key indicator: `passed + failed + skipped < total_runs` — results are missing, not
  failing.
- **What this means:** The aggregator lacked data points because child runs crashed, timed
  out, or failed to install. The mass "failures" are **artifacts of missing data**, not real
  regressions.
- **Action:** Investigate why child runs didn't complete — an infrastructure or install
  issue, NOT a test issue:
  1. From `junit-aggregated.xml`, identify child runs missing from the results (their
     `jobrunid` won't appear in passes, failures, or skips)
  2. Navigate to those child runs via Prow
  3. Check if they failed at installation, hit infrastructure errors, or timed out
  4. The root cause is whatever prevented runs from completing
- **Root cause:** Infrastructure issues, install failures, cloud provider problems, or a
  product bug that crashes the cluster before tests can run
- **Common trap:** Don't investigate the individual "failing" tests — they aren't failing.
  The aggregator is reporting it lacked data to determine pass/fail.

### Mode 3: Non-Deterministic Test Presence

A test only ran in a small subset of completed jobs, even though those jobs completed
successfully. Every test must produce results in every job run; a test that appears in
only some runs is a bug.

- **Signal:** Failure message says something like:
  ```text
  Passed 1 times, failed 0 times, skipped 0 times: we require at least 6 attempts to have
  a chance at success
  ```
  The critical distinction from Mode 2: all 10 child runs completed successfully, but the
  test appeared in only 1. Verify all child runs have passing entries for other tests — if
  they do, the issue is test-specific, not run-level.
- **What this means:** A test was introduced that doesn't produce results deterministically —
  non-deterministic skip logic, or it only runs under conditions that aren't consistently met.
- **Action:** Investigate why the test only runs in some jobs:
  1. Compare the test's presence across child runs
  2. Check the test's skip conditions in the source code
  3. Look for environment-dependent skip logic (platform-specific, feature-gate, or
     node-count conditions)
- **Root cause:** Non-deterministic test skip logic, conditional test registration, or a
  test that depends on cluster state that varies between runs

### How to Distinguish Mode 2 from Mode 3

Both show tests with fewer results than expected:

| Characteristic | Mode 2 (Insufficient Runs) | Mode 3 (Non-Deterministic Test) |
|----------------|---------------------------|--------------------------------|
| Affected tests | Many/all tests missing data | One or a few specific tests |
| Child runs completed | Some child runs didn't complete at all | All child runs completed |
| Other tests in same runs | Also missing from incomplete runs | Present and passing |
| Root cause location | Infrastructure/install | Test skip logic |

**Quick check:** Count how many unique `jobrunid` values appear across ALL testcases. If
some runs are completely absent from all tests, it's Mode 2. If all runs appear in most
tests but are missing from specific tests, it's Mode 3.

---

## Multi-Step CI Jobs vs True Aggregated Jobs

Two fundamentally different concepts that are often confused.

### Multi-Step CI Jobs (ci-operator Workflows)

A **multi-step CI job** is a single job run that executes steps in sequence via the
ci-operator step registry. Each step runs in its own container but shares one cluster.

```text
Single Job Run (build-id: 12345)
├── pre phase:   ipi-install-install (install cluster)
├── test phase:  openshift-e2e-test (run E2E tests)
├── post phase:  gather-must-gather (collect diagnostics)
└── post phase:  ipi-deprovision (destroy cluster)
```

- Uses ci-operator step registry **chains** and **workflows**
- Steps share a single cluster and single build-id
- All artifacts are under one `{build-id}/artifacts/{target}/` directory
- Failures in one step can cascade to later steps
- This is the normal CI job execution model

### True Aggregated Jobs

An **aggregated job** is a parent job that launches N independent child jobs, each of which
is itself a complete multi-step CI job.

```text
Aggregated Parent (build-id: 99999)
├── Child Run 1 (build-id: 12345) → full install + test + gather
├── Child Run 2 (build-id: 12346) → full install + test + gather
├── Child Run 3 (build-id: 12347) → full install + test + gather
├── ...
└── Child Run 10 (build-id: 12354) → full install + test + gather
```

- Parent launches N **independent** job runs
- Each child run installs its **own cluster**, runs tests, and cleans up
- Child runs have their own build-ids, artifact trees, and Prow URLs
- Parent only aggregates JUnit results — it has no cluster of its own
- Statistical analysis requires N independent samples

### Why the Difference Matters

For a multi-step CI job failure, everything is under one build-id — examine that job's
build-log.txt, JUnit XML, step logs, and cluster state.

For an aggregated job failure, the parent's artifacts contain only statistical summaries.
You **must** navigate to child runs for actual test logs, stack traces, and cluster
diagnostics.

---

## Step Registry Chains and Workflows

### Step Registry Structure

The OpenShift CI step registry (in `openshift/release`) defines reusable building blocks:

- **References (refs):** Single steps (e.g., `ipi-install-install`, `openshift-e2e-test`)
- **Chains:** Ordered sequences of refs and other chains (e.g., `ipi-install` chain includes
  `ipi-install-install` + `ipi-install-heterogeneous`)
- **Workflows:** Complete job definitions with `pre`, `test`, and `post` phases, each
  containing chains and/or refs

### How Workflows Relate to Aggregated Jobs

The **child job** typically runs a standard workflow. The parent's ci-operator config
references the child by its periodic job name and is minimal — it just configures the
aggregator. The child's ci-operator config holds the full workflow (pre/test/post phases).
When investigating test failures, you need the child job's workflow, not the parent's.

---

## Tracing Failures Across Aggregated Job Boundaries

### Step-by-Step Investigation Workflow

1. **Confirm the job is aggregated**
   - Check for `aggregated-` prefix in the job name
   - Or check for `release-analysis-aggregator` in artifact paths

2. **Download junit-aggregated.xml**
   ```bash
   gcloud storage ls \
     "gs://test-platform-results/{bucket-path}/artifacts/release-analysis-aggregator/**/junit-aggregated.xml"
   gcloud storage cp <found-path> .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled
   ```

3. **Count completed runs and classify the failure mode**
   - Parse all `<testcase>` elements
   - For each, count unique `jobrunid` values across passes, failures, and skips
   - Determine the total number of unique child runs that produced any results
   - Compare to expected run count (usually 10)

4. **Route based on failure mode:**

   **Mode 1 (real regression):**
   - Pick 2-3 failed child runs from the `failures:` list
   - Analyze each as a normal job using `ci:analyze-prow-job-test-failure`
   - Compare error patterns across runs to confirm consistency

   **Mode 2 (insufficient runs):**
   - Identify child runs that are missing from results entirely
   - Navigate to those child runs
   - Check if they failed at install, timed out, or hit infrastructure issues
   - The "failing tests" in the aggregation are red herrings

   **Mode 3 (non-deterministic test):**
   - Identify which tests appear in fewer runs than expected
   - Check the test source code for skip conditions
   - Determine why the test doesn't run deterministically

5. **Extract the underlying job name** for use in `/payload-aggregate` or `/payload-job`
   commands if re-triggering is needed (see "Extracting the Underlying Job Name" above)

### What to Include in the Analysis Report

```text
## Aggregated Job Analysis

- **Parent Job**: {aggregated-job-name}
- **Build ID**: {parent-build-id}
- **Underlying Job**: {underlying-job-name}
- **Payload Tag**: {payload-tag}
- **Failure Mode**: Mode {1|2|3} — {description}

### Run Summary
- Total child runs: {N}
- Completed: {M}
- Failed to complete: {N-M}

### Failing Tests (Mode 1) / Missing Runs (Mode 2) / Non-Deterministic Tests (Mode 3)
{details based on failure mode}

### Child Run Analysis
| Run | Build ID | Status | Key Finding |
|-----|----------|--------|-------------|
| 1   | {id}     | Pass   | —           |
| 2   | {id}     | Fail   | {error}     |
| ... | ...      | ...    | ...         |

### Root Cause
{synthesized root cause from child run analysis}
```

---

## Common Aggregated Job Patterns in OpenShift CI

### Upgrade Aggregated Jobs

These test OCP upgrades across multiple runs:
```text
aggregated-aws-sdn-upgrade-4.19
aggregated-azure-ovn-upgrade-4.19
aggregated-gcp-ovn-upgrade-4.19
aggregated-metal-ovn-upgrade-4.19
aggregated-aws-ovn-single-node-upgrade-4.19
```

Each child installs a cluster at one version, upgrades to the target payload, and runs
post-upgrade conformance tests. Failures may be in the install, upgrade, or post-upgrade
test phase. Check JUnit for `install should succeed` and upgrade-specific tests separately;
see [upgrade.md](upgrade.md).

### HyperShift Aggregated Jobs

These test HyperShift (hosted control planes):
```text
aggregated-hypershift-ovn-conformance-4.22
```

Child runs create hosted clusters and run conformance tests against them, with more complex
artifact structures (management cluster + hosted cluster) — see [hypershift.md](hypershift.md).

### Conformance and E2E Aggregated Jobs

Standard platform conformance testing:
```text
aggregated-aws-ovn-4.19
aggregated-gcp-ovn-4.19
```

Each child installs and runs the standard E2E suite — the simplest to analyze, following the
standard artifact structure.

---

## Statistical Analysis Considerations

### When N Child Runs Are Needed

The aggregator's statistical thresholds:

- **Minimum attempts:** Typically 6 of 10 runs must complete to have enough data
- **Historical pass rate:** The baseline pass rate for each test from historical data
- **Flake rate threshold:** Usually ~10% — failures below this rate are flakes, not
  regressions
- **Minimum pass rate:** The minimum required to not flag a regression (typically 90%)

If fewer than 6 runs complete, the aggregator **cannot determine** whether a test regressed —
it reports the test as failed due to insufficient data (Mode 2).

### Interpreting Pass/Fail Ratios

| Scenario | Interpretation | Action |
|----------|---------------|--------|
| 0 pass / 10 fail | Strong regression | Investigate any single failed child run |
| 3 pass / 7 fail | Likely regression | Investigate failed runs, check if passing runs differ |
| 8 pass / 2 fail | Likely flake | Check if the 2 failures have the same error pattern |
| 10 pass / 0 fail | Not a regression | Test passes consistently |
| 5 pass / 0 fail / 5 missing | Insufficient data (Mode 2) | Investigate why 5 runs didn't complete |

### Comparing Across Child Runs

When a test fails in some runs but passes in others:
- **Same error pattern:** Intermittent regression (may depend on timing, load, or race
  conditions)
- **Different error patterns:** Multiple unrelated issues, or infrastructure instability
- **Passing runs have no errors:** Confirms the failure is real, not a logging artifact

---

## Special Scenarios

### "All Children Passed but Parent Failed"

1. **Parent job timed out** — Child runs were still running when the parent hit its timeout;
   they may have eventually passed.
   - Check: `prowjob.json` parent `completionTime` vs `startTime`. Duration matching the
     timeout confirms a timeout.
   - Action: Check child statuses. If they passed, the failure is infrastructure (parent
     timeout too short), not a regression.

2. **Aggregator step itself failed** — The release-analysis-aggregator container crashed
   before completing analysis.
   - Check: `junit_operator.xml` in the parent's artifacts for step failures.
   - Action: CI infrastructure issue, not a test regression.

3. **Aggregator flagged a test that flaked within passing runs** — A child job can pass
   overall even when a test failed and was retried within that run. The aggregator counts each
   test's pass/fail across all runs, so a test that flaked in several children can be flagged
   even though every child *job* passed.
   - Check: The `<failure>` message in junit-aggregated.xml for the per-test pass/fail counts.
   - Action: A real regression — the test is becoming flaky.

### "Some Children Failed Differently"

When child runs fail with different error patterns, identify:

1. **The real regression:** Which error pattern is new? Check historical data for what's
   novel vs. pre-existing flakiness.
2. **Infrastructure vs product failures:** Separate cloud API errors/timeouts from test
   assertion errors:
   - Infrastructure failures → discard these runs from the analysis
   - Test failures → investigate these for regression
3. **Cascading failures:** One root cause can manifest differently across runs (e.g., a
   memory leak causing an OOM kill in one run, a timeout in another). Look for a common cause.

### Investigation Strategy for Mixed Results

1. **Group by failure pattern** — Categorize each child run by its failure mode
2. **Check the majority pattern** — The most common mode is usually the real signal
3. **Investigate outliers** — Unique failure patterns may reveal secondary issues or
   infrastructure problems
4. **Cross-reference timing** — Runs that failed first may show the original error before
   cascading effects obscure it

---

## Aggregated Job Retries

Retries behave differently than for normal jobs (where each retry is an independent
execution):

- **Retries re-run the aggregation analysis** — they do NOT re-run the underlying child test
  jobs
- Child runs from the original attempt are reused
- **Only examine the most recent retry** — previous attempts contain the same underlying
  results

When analyzing an aggregated job that has been retried:
- Set `retries_consistent: only_final_examined`
- Set `retry_summary: "Aggregated job — only final attempt examined (retries re-run aggregation only)"`
- Focus entirely on the latest attempt's `junit-aggregated.xml`

---

## Triggering Aggregated Jobs

When re-triggering (e.g., on a revert PR):

- **`/payload-aggregate {underlying-job-name} {count}`** — New aggregated run with N
  iterations of the underlying job
- **`/payload-job {underlying-job-name}`** — Single run of the underlying job (faster, no
  statistical analysis)

**Important:**
- Do NOT use `/payload-job` with the aggregated job name — aggregated jobs are not directly
  triggerable
- If the aggregated job failed 10/10 runs, a single `/payload-job` run of the underlying job
  suffices to validate a fix; otherwise use `/payload-aggregate` for statistical validation
- The `underlying-job-name` **must** be extracted from the artifacts — it cannot be reliably
  derived from the aggregated job name

---

## Quick Reference Checklist

- [ ] **Confirm aggregated:** Job name starts with `aggregated-` or artifacts contain
  `release-analysis-aggregator`
- [ ] **Do NOT analyze parent build-log.txt** as test output
- [ ] **Download junit-aggregated.xml** from parent artifacts
- [ ] **Count completed child runs** — how many produced results?
- [ ] **Classify failure mode** — Mode 1, 2, or 3
- [ ] **Extract underlying job name** from artifact paths or `humanurl`
- [ ] **Navigate to child runs** for actual investigation
- [ ] **Analyze child runs** as normal (non-aggregated) jobs
- [ ] **Compare failure patterns** across multiple child runs
- [ ] **Report the underlying job name** for re-triggering purposes

---

## See Also

- [Artifacts Reference](artifacts.md) — Directory structure for normal (non-aggregated) jobs
- [Test Extension Binaries](test-extension-binaries.md) — component `*-tests-ext` (OTE) binary
  failures in a child run
- [HyperShift Reference](hypershift.md) — Additional complexity for HyperShift aggregated jobs
- [Upgrade Reference](upgrade.md) — Upgrade-specific analysis for upgrade aggregated jobs
- [Flaky Test Identification](flaky-test-identification.md) — Distinguishing flakes from
  real regressions (relevant for Mode 1 borderline cases)
- [CI Infrastructure](ci-infrastructure-changes.md) — Infrastructure issues that can cause
  Mode 2 failures
