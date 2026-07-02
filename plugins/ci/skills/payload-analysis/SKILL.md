---
name: payload-analysis
description: Analyze a payload snapshot to identify root causes of blocking job failures, score candidate PRs, and produce an HTML report with revert recommendations
argument-hint: "<payload-tag> [--snapshot-dir DIR]"
---

# Payload Analysis

This skill analyzes a payload using a local snapshot (produced by `payload-snapshot`) to identify root causes of blocking job failures and produce a comprehensive HTML report. The snapshot pre-gathers all release controller, GitHub, and CI data so this skill can focus purely on analysis — no live API orchestration required.

It supports **Rejected** payloads (full analysis of all failed blocking jobs), **Ready** payloads (early analysis of blocking jobs that have already failed), and **Accepted** payloads (which may have been force-accepted despite blocking failures).

## When to Use This Skill

Use this skill when you need to:

- Understand why a payload was rejected
- Investigate failures in a force-accepted payload
- Assess whether an in-progress ("Ready") payload is likely to be rejected
- Determine whether failures are new or persistent
- Identify which PRs likely caused new failures
- Get a comprehensive overview of payload health with actionable root cause analysis
- Re-analyze a historical payload against its original snapshot data

## Examples

1. **Analyze an amd64 nightly payload** (auto-creates snapshot if needed):
   ```
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Analyze using an existing snapshot directory**:
   ```
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806 --snapshot-dir payload/4.22/nightly
   ```

3. **Analyze an arm64 payload** (architecture inferred from tag):
   ```
   /ci:payload-analysis 4.22.0-0.nightly-arm64-2026-02-25-152806
   ```

## Required Skills

Before starting, you **MUST** load the following skills (they define output schemas used in Steps 6 and 8):

1. **`payload-results-yaml`** — schema for the payload results YAML file
2. **`payload-autodl-json`** — schema for the autodl JSON data file

## Prerequisites

1. **Python 3** (3.10 or later) — for running the snapshot script if needed
2. **gcloud CLI** — for subagent artifact download (must-gather, pod logs)
3. **GitHub CLI (`gh`)** — for step-registry change detection (Step 3.6) and checking existing revert PRs (Step 6.3)

## Implementation Steps

### Step 1: Parse Arguments

The first argument is a **full payload tag** (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Parse from it:
- `tag`: The specific payload tag to analyze
- `version`: Extract from the tag (e.g., `4.22` from `4.22.0-0.nightly-...`)
- `stream`: Extract from the tag (e.g., `nightly` from `4.22.0-0.nightly-...`)
- `architecture`: Inferred from the tag. The tag format is `<version>-0.<stream>[-<arch>]-<timestamp>`. If no architecture is present between the stream and timestamp, it is `amd64`. Otherwise, the architecture is the segment between the stream and timestamp. Examples:
  - `4.22.0-0.nightly-2026-02-25-152806` → `amd64`
  - `4.22.0-0.nightly-arm64-2026-02-25-152806` → `arm64`
  - `4.22.0-0.nightly-ppc64le-2026-02-25-152806` → `ppc64le`

### Step 2: Locate or Create Snapshot

The analysis requires a local snapshot produced by the `payload-snapshot` skill. Search for an existing snapshot in this order:

1. **Explicit `--snapshot-dir DIR`**: If provided, look for `DIR/summary.json`. If not found, exit with an error.
2. **Current directory**: Check if `./summary.json` exists and its `payload_tag` field matches the requested tag.
3. **Standard relative path**: Check if `payload/<version>/<stream>/summary.json` exists and matches the tag.

If no matching snapshot is found, create one:

```bash
SNAPSHOT_SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/payload-snapshot/scripts/payload_snapshot.py"
if [ ! -f "$SNAPSHOT_SCRIPT" ]; then
  SNAPSHOT_SCRIPT=$(find ~/.claude/plugins -type f -path "*/ci/skills/payload-snapshot/scripts/payload_snapshot.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$SNAPSHOT_SCRIPT" ] || [ ! -f "$SNAPSHOT_SCRIPT" ]; then echo "ERROR: payload_snapshot.py not found" >&2; exit 2; fi
python3 "$SNAPSHOT_SCRIPT" <payload_tag>
```

After locating `summary.json`, set `SNAPSHOT_DIR` to the directory containing it. All relative paths in `summary.json` (e.g., `job_json`, `junit_results`, `build_log`, PR paths) resolve from this directory.

### Step 3: Extract Failure Data from Snapshot

Read `summary.json` to extract all data needed for analysis. The snapshot has already done the work of fetching payloads, building the chain, tracking streaks, and collecting PR data.

#### 3.1: Payload Metadata

From `summary.json` top-level fields:
- `payload_tag`, `phase`, `release_url`, `architecture`, `stream`, `version`
- `chain_length`, `baseline_tag`, `hours_since_baseline`

**Record `phase` verbatim** from the `summary.json` metadata (`Accepted`, `Rejected`, or `Ready`). Never infer the phase from the job results or from whether failures exist — a payload can be `Accepted` *with* blocking failures (force-accepted) or `Ready` while jobs are still running. The stored phase drives the force-accept decision (Step 6.4) and the executive summary (Step 7.1), so an inferred phase silently corrupts both.

#### 3.2: Failed Blocking Jobs

From `summary.json` → `blocking_jobs.failed_jobs[]`, each entry contains:
- `name`, `state`, `prow_url`, `gcs_url`, `is_aggregated`, `retries`
- `rhcos_version`: the RHCOS variant for this job (`rhcos9`, `rhcos10`, `rhcos9_10`, `rhcos9-default`, or `rhcos10-default`)
- `streak`: `streak_length`, `originating_payload`, `is_new_failure`, `failure_pattern`
- `build_log_errors`, `test_failure_count`
- Paths: `job_json`, `junit_results`, `build_log`

For each failed job, read its `job.json` (at `SNAPSHOT_DIR/<job_json>` path) to get `previousAttemptURLs`.

#### 3.3: Candidate PRs

For each failed job's `streak.originating_payload`, find the matching entry in `summary.json` → `payloads[]`. Its `prs[]` array contains the PRs introduced in that payload:
- `url`, `component`, `number`, `description`
- Paths to local artifacts: `diff`, `comments`, `jobs`

These PRs are the **candidates** for failures that started in that originating payload.

#### 3.4: Test Failure Details

From `summary.json` → `test_failures.blocking[]`:
- `test_name`, `jobs`, `first_failed_in`, `payloads_failing`
- `failure_message`, `failure_text` (full, not truncated)

#### 3.5: Build Log Errors

For deeper context, read `build_log.json` (at the `build_log` path) for any failed job. It contains `error_warning_lines[]` with `line_number` and `text`, plus `tail_lines[]` (last 20% of the log).

#### 3.6: Check for CI Infrastructure Changes

For each failed job, check whether changes to the CI step-registry in the `openshift/release` repo correlate with the failure. These changes (modified step scripts, updated URLs, changed environment variables) will never appear in the snapshot's component PR list because they are not payload component changes — but they can break jobs just as effectively.

Extract the date from the `originating_payload` tag (format: `<version>-0.<stream>-YYYY-MM-DD-HHMMSS` or `<version>-0.<stream>-<arch>-YYYY-MM-DD-HHMMSS` for non-amd64). The date is always the last `YYYY-MM-DD` segment before the `HHMMSS` suffix (e.g., `2026-06-16` from `5.0.0-0.nightly-2026-06-16-185706` or `5.0.0-0.nightly-arm64-2026-06-16-185706`). Compute a time window: `since` = originating date minus 1 day at `T00:00:00Z`; `until` = originating date plus 1 day at `T23:59:59Z`.

**First, get all step-registry commits in the time window:**

```bash
gh api "repos/openshift/release/commits?path=ci-operator/step-registry&since=<since_date>T00:00:00Z&until=<until_date>T23:59:59Z&per_page=100" \
    --jq '.[] | {sha: .sha[0:11], date: .commit.committer.date, message: (.commit.message | split("\n")[0])}'
```

If exactly 100 results are returned, fetch subsequent pages by appending `&page=2`, `&page=3`, etc. until a page returns fewer than 100 results.

**Triage the results using failure context from Steps 3.4 and 3.5.** Extract the key signals from the failure: error messages, failing URLs/domains, exit codes, failing script names, and affected subsystems. Use commit messages as an initial filter, but prioritize inspection of diffs when filenames or modified directories appear relevant even if the commit message is generic — many `openshift/release` commits have uninformative messages like "Fix typo" or "Update image" while the actual diff contains the interesting change. Relevant commits typically touch the same subsystem, tool, or infrastructure that appears in the error (e.g., a commit modifying mirror URLs when the failure shows curl errors to a new domain; a commit changing proxy configuration when the failure is a connection refused through a proxy). Ignore commits that clearly target unrelated teams or subsystems (hypervisor updates, unrelated repo onboarding, OWNERS file changes).

For each commit that looks potentially related, retrieve the changed files:

```bash
gh api "repos/openshift/release/commits/<sha>" --jq '.files[] | {filename, patch}'
```

First check the filenames — if none correspond to the failing step or any of its dependencies, eliminate that commit immediately without reading the patches. For commits that do touch relevant files, inspect the patches for URL changes, configuration modifications, or script logic changes that could cause the observed failure.

If the commit message includes a PR reference (typically `(#NNNNN)`), retrieve the PR details:

```bash
gh pr view <pr_number> --repo openshift/release --json number,title,url,mergedAt,body
```

**After Step 4 subagent results are available**, do a targeted search using the specific step that failed. From the subagent's build log analysis, identify the step-registry path of the step that actually errored (e.g., `gather/must-gather`, `baremetalds/devscripts/proxy`, `ipi/install/install`). Search for recent changes to that exact step and to related steps in the same workflow chain:

```bash
gh api "repos/openshift/release/commits?path=ci-operator/step-registry/<step_subpath>&since=<since_date>T00:00:00Z&until=<until_date>T23:59:59Z&per_page=10" \
    --jq '.[] | {sha: .sha[0:11], date: .commit.committer.date, message: (.commit.message | split("\n")[0])}'
```

If this finds nothing, also check steps that run earlier in the workflow and set up infrastructure the failing step depends on (e.g., if `openshift-e2e-test` fails due to connectivity, check `baremetalds/devscripts/proxy` or `ipi/conf` steps that configure networking).

**Scoring CI infrastructure candidates.** If a commit/PR modified a step that the failing job executes (or a shared dependency of that step), flag it as a **CI infrastructure candidate** — include it in Step 6.1 scoring alongside component PR candidates. When the failure's error messages reference URLs, domains, binaries, or configurations that were changed by the PR, the error message match signal (+40) should fire strongly. The key test: does the PR's diff introduce, modify, or remove something that appears in the error output?

**A causal CI-infrastructure change MUST appear as a scored entry in the `candidates[]` output**, exactly like a component PR — even when the overall `failure_type` is `infra`. Classifying a failure as infrastructure does not exempt its cause from structured output. Unlike a self-resolving lease/quota blip, a CI-config change is a persistent issue (Step 6.4) that needs a human fix or a revert, so it must be visible to the downstream revert/experiment commands, not buried in prose.

This step catches failures caused by CI tooling changes (mirror URL migrations, proxy configuration updates, script refactors) that are invisible to the snapshot's PR tracking.

#### 3.7: RHCOS RPM Changes

For each failed job's `streak.originating_payload`, find the matching entry in `summary.json` → `payloads[]` and check for `rhcos_changes[]`. This array (when present) contains per-RHCOS-variant RPM diffs showing which packages changed in the underlying RHCOS image for that payload:

- `name`: Human-readable version (e.g., "Red Hat Enterprise Linux CoreOS 10.2")
- `tag`: Image stream tag — maps to job RHCOS variants:
  - `rhel-coreos` → applies to jobs with `rhcos_version` of `rhcos9` or `rhcos9-default`
  - `rhel-coreos-10` → applies to jobs with `rhcos_version` of `rhcos10` or `rhcos10-default`
  - Both apply to `rhcos9_10` (heterogeneous) jobs
- `changed`: `{package_name: {"old": old_version, "new": new_version}}`
- `added`: newly added packages (when present)
- `removed`: removed packages (when present)

For each failed job, identify the matching RHCOS variant's RPM changes (if any) based on the job's `rhcos_version` field and the RHCOS tag mapping above. These changes are used as additional context in Step 4 and as potential suspects in Step 6.

### Step 4: Investigate Each Failed Job in Parallel

For each failed blocking job in the **target payload**, launch a **parallel subagent** to investigate the failure. Pass the subagent the Prow URL and all previous attempt URLs from Step 3.2.

Almost all blocking jobs install a cluster and then run tests, so the job name alone does not tell you the failure type. Each subagent therefore runs the `ci:prow-job-analysis` skill, which classifies the failure and routes to the correct specialized reference internally.

You MUST use the following prompt verbatim (substituting the placeholder values) when launching each subagent. Do NOT paraphrase, shorten, or write your own prompt — the specific instructions below are critical for analysis quality:

> Analyze the failure at <prow_url>. This job had <N> retries. The previous attempt URLs are: <previous_attempt_urls>.
>
> **Aggregated jobs**: If this is an aggregated job (has `aggregated-` prefix or an `aggregator` step), retries only re-run the aggregation analysis — they do NOT re-run the underlying test jobs. Therefore, only examine the most recent attempt; previous attempts contain the same underlying results and do not provide additional signal.
>
> **Non-aggregated jobs**: **Examine the final attempt first**, then compare with previous attempts to determine whether all retries failed the same way. If retries show different failure modes, note this — it distinguishes consistent regressions from intermittent/infrastructure issues. Consistent failures across all attempts strongly indicate a product regression rather than flakiness.
>
> **RHCOS version**: This job's cluster runs on **<rhcos_version>**. <rhcos_context>
>
> **RHCOS RPM changes**: Read `<summary_json_path>` and find the entry in `payloads[]` whose `tag` equals `<originating_payload_tag>`. If that entry has an `rhcos_changes[]` array, look up the RHCOS variant matching this job's `rhcos_version` using the tag mapping: `rhel-coreos` → `rhcos9`/`rhcos9-default`, `rhel-coreos-10` → `rhcos10`/`rhcos10-default`, both apply to `rhcos9_10`. Check whether any changed, added, or removed RPM packages overlap with the failure's root cause. If the failure involves OS-level components (kernel, bootloader, systemd, SELinux, rpm-ostree, cri-o, crun, runc, networking) and matching packages changed, note the potential correlation in your ANALYSIS_RESULT.
>
> Use the `ci:prow-job-analysis` skill for this investigation. It is the single entry point for every failed job: it identifies the job type, classifies the failure, and routes to the correct specialized reference — install, metal/bare-metal, test, upgrade, and more — internally. Do NOT pre-classify the failure yourself. Perform the full analysis, including downloading and analyzing must-gather when it is available.
>
> **IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.
>
> **Do NOT classify a failure as "infrastructure flake" or "transient" unless you have affirmative evidence** of an infrastructure problem (cloud API errors, quota exceeded, network timeouts from the cloud provider, Boskos lease failures, CI platform outages). The absence of an obvious code-level explanation does NOT make something infrastructure — it means you need to investigate deeper. Default to treating failures as potential product regressions until evidence proves otherwise.
>
> Return a concise summary including: failure type (install vs test), root cause, key error messages, and any relevant log excerpts. Do not ask user questions. Keep the output concise for inclusion in a summary report.
>
> If the job is an aggregated job (has `aggregated-` prefix in the name or an `aggregator` container/step), also return the **underlying job name** (e.g., `periodic-ci-openshift-release-main-ci-4.22-e2e-aws-upgrade-ovn-single-node`). This is found in the junit-aggregated.xml artifacts — each `<testcase>` has `<system-out>` YAML data with a `humanurl` field linking to individual runs whose URL path contains the underlying job name. The underlying job name cannot be derived from the aggregated job name — it must be extracted from the artifacts.

Where `<rhcos_version>` is the `rhcos_version` field from the snapshot's failed job entry, `<rhcos_context>` is one of:
- For **`rhcos9`** or **`rhcos9-default`**: "RHCOS 9 is based on RHEL 9 — the standard CoreOS variant for this OCP version."
- For **`rhcos10`** or **`rhcos10-default`**: "RHCOS 10 is based on RHEL 10 with a different kernel, systemd, SELinux policy, and package versions than RHCOS 9. If the failure involves OS-level components (kernel, bootloader, rpm-ostree, MCO, Ignition), consider whether RHEL 10 differences could be the root cause."
- For **`rhcos9_10`** (heterogeneous): "This is a heterogeneous cluster with both RHCOS 9 and RHCOS 10 nodes. Failures may be specific to one node variant — check whether failing nodes are RHCOS 9 or RHCOS 10 when node-level logs are available."

`<summary_json_path>` is the absolute path to the snapshot's `summary.json` file, and `<originating_payload_tag>` is the `streak.originating_payload` value from the failed job entry.

**Structured Return Format**: Instruct each subagent to include an `ANALYSIS_RESULT` block at the end of its response:

```
ANALYSIS_RESULT:
- failure_type: install|test|upgrade|infra
- root_cause_summary: <one-line summary>
- affected_components: <comma-separated list of affected operators/components>
- key_error_patterns: <comma-separated key error strings for matching>
- known_symptoms: <comma-separated symptom summaries from job_labels, or "none">
- underlying_job_name: <for aggregated jobs only, extracted from junit artifacts>
- retries_consistent: yes|no|no_retries|only_final_examined
- retry_summary: <brief comparison of failure modes across attempts, e.g. "all 3 attempts failed with same KAS crashloop" or "attempt 1 infra timeout, attempts 2-3 test failure", or "no retries" when there was only a single attempt>
- rhcos_version: rhcos9|rhcos10|rhcos9_10|rhcos9-default|rhcos10-default
- rhcos_rpm_correlation: none|possible|likely
- rhcos_rpm_suspect_packages: <comma-separated package names if correlation is possible or likely, or "none">
```

The `rhcos_rpm_correlation` field indicates whether the failure may be related to RHCOS RPM changes found in `summary.json`:
- `none` — no correlation found, or no RHCOS RPM changes exist for this job's variant
- `possible` — the failure involves OS-level components that overlap with changed packages, but the link is not definitive
- `likely` — error messages or failure behavior directly point to functionality provided by a changed RPM package

**Note for aggregated jobs**: Since only the final attempt is examined (retries re-run aggregation only), set `retries_consistent: only_final_examined` and `retry_summary: "Aggregated job — only final attempt examined (retries re-run aggregation only)"`.

**Important**: Launch ALL subagents in parallel for maximum speed. Do NOT set the `model` parameter — let subagents inherit the parent model, as these analysis tasks require a capable model.

#### Cross-Platform and Cross-Job Failure Pattern Recognition

After collecting subagent results, look for patterns across multiple jobs:

- **Same failure across a job family** (e.g., all `techpreview` jobs, all `fips` jobs, all `upgrade` jobs): This often indicates a failure specific to that feature set or configuration.
- **Same failure across multiple platforms**: This often points to a product bug in shared code.
- **RHCOS variant isolation**: Check whether any failure's root cause or error pattern appears **only** in jobs of one RHCOS variant and **not** in jobs of the other variant. A failure is "variant-isolated" when:
  - It appears in one or more RHCOS 10 jobs but in zero RHCOS 9 jobs → `failure_scope: "rhcos10-only"`
  - It appears in one or more RHCOS 9 jobs but in zero RHCOS 10 jobs → `failure_scope: "rhcos9-only"`
  - Jobs with `rhcos9-default` count as RHCOS 9 for this check
  - Jobs with `rhcos10-default` count as RHCOS 10 for this check
  - Jobs with `rhcos9_10` (heterogeneous) count toward both variants for this check
  - Variant isolation is strong diagnostic context — it narrows the root cause to OS-specific changes (kernel, systemd, SELinux, package differences between RHEL 9 and RHEL 10).

### Step 4b: Consult Previous Claude Analyses

Read the target payload's `payload.json` (at `SNAPSHOT_DIR/<payloads[0].payload>`) and check if a `claude-payload-agent` async job exists with state `Succeeded`. If so, fetch the HTML report from its Prow artifacts:

```
{prow_artifacts_url}/artifacts/claude-payload-agent/openshift-release-analysis-claude-payload-agent/artifacts/payload-analysis-{tag}-summary.html
```

Convert the Prow URL to a gcsweb URL and use WebFetch to read it.

**Important**: Previous analyses are a secondary input. Always complete your own analysis first, then compare. Use previous findings to bolster confidence, challenge assumptions, or fill gaps — never adopt conclusions without verifying against the snapshot data.

### Step 5: Validate Failure Streaks

After collecting all subagent results, verify that consecutive failures across payloads share the same root cause. A consecutive failure streak does NOT automatically mean the same root cause.

Compare the subagent's root cause analysis for the target payload against previous payload analyses (from Step 4b) or the failure signatures in the snapshot's streak data.

If a job fails in two consecutive payloads but for **different reasons**, treat each as a separate streak=1 failure with its own originating payload and candidate PRs. Re-split the streak and re-assign originating payloads before proceeding to scoring.

### Step 5b: Adjudicate Conflicting Root Causes

When two or more investigations reach **contradictory root causes for the same failure signature** (same test, same operation, or same error class — across jobs, across retries, or between a subagent and a previous analysis), the analysis is **UNRESOLVED**. It is *not* a tie to be broken by whichever explanation feels more plausible. Resolve it only with discriminating evidence, applying these rules:

- **Discriminating evidence must come from the exact failing operation or phase** — the specific subcommand, step, or reconcile loop that actually errored, not from adjacent activity.
- **"Cleared" requires positive evidence from the failing code path.** A candidate is exonerated only by positive evidence that its code path executed and completed without error *during the failing operation itself*. A candidate succeeding in a *different* subcommand, phase, or job does **not** clear it.
- **Absence of a log line is not evidence when the log is truncated.** If the relevant log was truncated, rotated, or never captured, treat the missing line as *unknown*, never as proof that a code path did not execute.
- **A causal chain must be shown to execute, not merely shown to be possible.** Demonstrate that the proposed mechanism actually ran during the failing operation (via timestamps, ordering, or an emitted log/metric). "This change *could* cause this" is a hypothesis, not a root cause.
- **When you override a subagent's conclusion, update the stored per-job root cause** so the streak data, YAML, JSON, and HTML all reflect the adjudicated cause. Divergent per-job root causes across outputs are a defect (checked in Step 10).

**Tenacity booster:** Finding a plausible mechanism is the *midpoint* of the investigation, not the end. When rival explanations exist, your job is to *discriminate between them* with evidence from the failing operation — not to stop at the first mechanism that could work. If the evidence cannot discriminate, record the failure mode as UNRESOLVED with its competing hypotheses rather than committing to a guess (a wrong-PR attribution is far more damaging than an honest "unresolved").

### Step 6: Collect Investigation Results and Identify Revert Candidates

Wait for all subagents to complete and collect their analysis results. For each failed job, you now have:

- **Job name** and **Prow URL** (from snapshot)
- **Failure analysis** (from subagent)
- **Streak data** (from snapshot: `streak_length`, `originating_payload`, `failure_pattern`)
- **Candidate PRs** (from snapshot: originating payload's `prs[]`)

#### 6.1: Correlate Failures with Candidate PRs

For each failed job, cross-reference the failure analysis from the subagent with the candidate PRs from the originating payload. Read the PR's `code.diff` file (at the path from `summary.json` → `payloads[].prs[].diff`) to check for code-level correlation.

If a subagent traced the root cause to a PR outside the payload (e.g., an `openshift/release` PR that modified a CI step registry script), include that PR as a candidate.

**Score every distinct failure mode, not just the dominant one.** A single job can fail for more than one reason (e.g., an install timeout *and* an unrelated test regression). Enumerate each distinct failure mode the subagent identified and run every candidate PR through the rubric **once per failure mode** — a PR that explains failure mode A does not automatically explain failure mode B. Do not collapse a job down to its loudest symptom and score only that.

Score each (failed job, failure mode, candidate PR) tuple using the following weighted rubric:

| Signal | Weight | Criteria |
|--------|--------|----------|
| New failure mode | +30 | This failure mode was not present in previous payloads **and** is plausibly attributable to code that changed (some PR touches the implicated code path). A brand-new symptom with no changed code behind it does not earn this signal (see infrastructure exclusion below). |
| Component exclusivity | +10 to +30 | The failure involves a component modified by this PR. **Sole modifier of the affected component = +30** — this tier already covers the "only one candidate PR touches the component" case, so do not also count it separately. 2-3 PRs modify the component = +20; 4+ PRs modify it = +10. |
| Error message match | +10 to +40 | Tiered by how directly the failure output links to the PR's diff. **Direct match = +40**: an error string, symbol, function name, or identifier from the failure appears verbatim in the PR's diff. **Same code path = +20-30**: the PR modifies the function or execution flow that produced the error, but the exact message is not in the diff. **Same subsystem only = +10**: the PR touches the same subsystem/component but not the specific failing code path. |
| Multi-job correlation | +10 | The same PR is a candidate for this failure mode in multiple independent jobs |
| Presubmit coverage gap | +10 | The failing job tests a scenario not covered by the PR's presubmit tests |

Maximum possible score is 120, capped at 100. Record the numeric score alongside qualitative rationale.

**Every candidate's rationale MUST itemize the score** — one line per signal that fired — so the number is auditable rather than asserted:

```
signal_name: +points — one line of concrete evidence
```

For example:

```
error_message_match: +40 — panic "nil pointer in reconcileNode" from build-log appears verbatim in the PR diff (controller.go:214)
component_exclusivity: +30 — sole PR modifying machine-config-operator in the originating payload
new_failure_mode: +30 — job passed the 6 prior payloads; first failed in the originating payload
total: 100
```

Record this breakdown in the candidate's `rationale` field in the YAML/JSON output. A bare score with no itemized breakdown is not acceptable.

**Apply the rubric mechanically, then verify the top-tier claims.** Sum the weights for each signal that fires on concrete evidence. Do NOT adjust the score downward based on speculative counter-arguments like "if this were the sole cause, other jobs would also fail" or "this could be a coincidence" — if the error messages reference the PR's changes, that's a match, and the fact that some other jobs didn't fail doesn't negate it. **But when the raw sum exceeds the cap** (you claimed a maximum tier on more than one signal at once), re-verify each maximum-tier claim before recording: is the error-message match a true verbatim string/symbol match (+40), or really only same-subsystem (+10)? Is this genuinely the *sole* modifier of the component (+30)? Downgrade any tier that does not survive this check. This self-skepticism pass removes tier inflation without weakening genuinely strong matches. Trust the rubric — it exists to prevent both over- and under-attribution.

**Infrastructure exclusion — do not let unrelated PRs accumulate points.** The rubric measures *product-code causation*. When the root cause is affirmatively infrastructure (Step 6.4 definition) or an affirmatively-identified CI-config change (Step 3.6), payload component PRs with **no error-message and no code-path correlation** to the failure must score **at or near zero**. Do not award "new failure mode" or bare "component exclusivity" points to a PR that merely happens to be present in the payload — "new failure mode" fires only when the failure is plausibly attributable to code that changed. A new symptom whose actual cause is a lease timeout, a quota block, or a step-registry edit is not evidence against an unrelated component PR.

**"Intermittent" and "flake" are conclusions requiring evidence, not default labels.** Before dismissing a failure as a flake, confirm affirmative evidence for it (e.g., the same job passed on retry with no code change, or it is a known-flaky test that also fails on *accepted* payloads). First check whether any candidate PR touches the failing code path: a reproducible failure in code that changed is a regression, not a flake, even if it does not reproduce on every run.

#### 6.1b: RHCOS RPM Change Correlation

After scoring PR candidates, check for RHCOS RPM change correlation. A failure correlates with RHCOS RPM changes when ANY of the following hold:

1. The subagent's `rhcos_rpm_correlation` is `possible` or `likely`
2. The failure is variant-isolated (e.g., appears only in RHCOS 10 jobs) AND the matching RHCOS variant has RPM changes in the originating payload
3. The root cause involves OS-level components (kernel, systemd, SELinux, cri-o, crun, runc, networking, bootloader, rpm-ostree, MCO, Ignition) AND matching RHCOS RPM changes exist in the originating payload
4. No high-confidence PR candidates exist (all scores < 50) AND RHCOS RPM changes exist in the originating payload — in this case, the RPM changes are the most plausible explanation

**RHCOS RPM changes are NOT revert candidates.** They cannot be easily reverted from the payload. Do NOT propose reverts for RHCOS changes. Instead, surface them as **"RHCOS RPM suspects"** — informational entries for manual investigation by the RHCOS or platform team.

When both PR candidates AND RHCOS RPM changes are plausible causes, include both. The PR candidate scoring is unchanged; RHCOS suspects are additive context, not alternatives. It is possible for a failure to be caused by an interaction between a PR change and an RHCOS change.

For each RHCOS RPM suspect, record:
- `rhcos_tag`: the RHCOS image stream tag (e.g., `rhel-coreos-10`)
- `rhcos_name`: human-readable name (e.g., "Red Hat Enterprise Linux CoreOS 10.2")
- `package`: the RPM package name
- `old_version`, `new_version`: the version change
- `failing_jobs`: list of job names where this package change may be relevant
- `rationale`: why this package is suspected (e.g., "systemd update correlates with variant-isolated boot timeout in RHCOS 10 jobs")

#### 6.2: Propose Revert Candidates

For each candidate PR with a rubric score of **>= 85**, mark it as a **revert candidate**. A PR qualifies when:

1. The failure clearly maps to the PR's changes
2. The timing is exact — the job was passing before the originating payload
3. No other plausible explanation — infrastructure flakiness and platform problems have been ruled out

Per OCP policy, PRs that break payloads MUST be reverted. When confidence is high, the report must clearly state that a revert is required — not optional.

For each revert candidate, record: PR URL, description, component, confidence score with rationale.

**Do NOT propose reverts for**: Infrastructure failures, flaky tests that also fail on accepted payloads, jobs where analysis is inconclusive.

#### 6.3: Check if Revert Candidates Were Already Reverted

For each revert candidate:

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state,mergedAt --limit 5
```

If a revert PR is found:
- **Merged**: Note when it merged relative to the payload. If after the payload was cut, the fix is expected in the next payload. Do not recommend reverting again.
- **Open**: Mention the existing revert PR and link to it.
- **Closed (not merged)**: Ignore.

#### 6.4: Determine Force-Accept Recommendation

Force-accepting is only meaningful for a payload that has **not** already been accepted. **If the snapshot's `phase` (Step 3.1) is already `Accepted`, `force_accept_recommended` MUST be `false`** — the question is moot, so do not recommend it regardless of the failures present.

Otherwise, recommend force-accepting when **all** of the following are true:

1. All failures are **temporary** infrastructure issues (`failure_type: "infra"`) — see the definition below
2. No more than 2 blocking jobs failed
3. `hours_since_baseline` from `summary.json` is >= 18 (or null)

**What counts as a "temporary infrastructure issue".** The decisive test: *will the failure self-resolve on the next run WITHOUT human action?*

- **Yes → temporary (force-accept eligible):** Boskos/lease acquisition failures, cloud quota exhaustion, transient cloud-provider API errors or throttling, a one-off network timeout to a cloud endpoint, a CI control-plane blip. These clear themselves on retry.
- **No → persistent (NOT force-accept eligible):** stale or expired credentials, a broken or misconfigured CI step/workflow, a bad mirror/registry URL, a persistent misconfiguration, or any product regression. These fail again on the next run until a human intervenes — force-accepting only defers the problem. Do not classify these as a temporary infra pass; a causal CI-config change is scored as a candidate (Steps 3.6 and 6.1) instead.

#### 6.5: Write Payload Results YAML

Use the `payload-results-yaml` skill to create: `payload-results-{tag}.yaml`

This file contains ALL scored candidates across all confidence tiers (HIGH, MEDIUM, LOW), enabling downstream commands to filter by their own criteria. If RHCOS RPM suspects were identified in Step 6.1b, include them in the `rhcos_suspects[]` array (see the `payload-results-yaml` skill for the schema).

**Every affirmatively-identified root cause must be represented as a scored `candidates[]` entry** — including causal CI-infrastructure / step-registry changes (Step 3.6), even when the failure's `failure_type` is `infra`. A failure whose cause is known must not leave `candidates[]` empty; each entry carries its itemized rubric breakdown (Step 6.1) in its `rationale`.

### Step 7: Generate HTML Report

Create a self-contained HTML file named `payload-analysis-<tag>-summary.html` in the current working directory. The tag should be sanitized for use as a filename.

The report must include the following sections:

#### 7.1: Header and Executive Summary

```html
<h1>Payload Analysis: {payload_tag}</h1>
<div class="metadata">
  <p>Architecture: {architecture} | Stream: {stream} | Generated: {timestamp}</p>
  <p>Release Controller: <a href="{release_url}">{payload_tag}</a></p>
  <p>Snapshot: {snapshot_dir}</p>
</div>

<div class="executive-summary">
  <h2>Executive Summary</h2>
  <p>Phase: {phase}</p>
  <p>{total_blocking} blocking jobs: {succeeded} passed, {failed} failed</p>
  <p>{new_failures} new failure(s), {persistent_failures} persistent failure(s)</p>
  <p>Chain: {chain_length} payloads, {hours_since_baseline}h since baseline</p>
  <p>Consecutive rejections in this stream: {consecutive_rejection_count}</p>
  <p>Last accepted: <a href="{baseline_url}">{baseline_tag}</a> ({hours_since_baseline}h ago)</p>
  <p>Per-job persistence: {for each failed job — "job_name: failing N consecutive payloads"}</p>
</div>
```

**Payload-chain context** surfaces the streak at a glance — include all of the fields above. Derive them from the snapshot: `consecutive_rejection_count` is the number of consecutive non-`Accepted` payloads in the chain up to and including this one (the chain runs from the last accepted baseline forward — see `chain_length` and the `payloads[]` phases); the last accepted payload is `baseline_tag`, cut `hours_since_baseline` hours ago; per-job persistence is each failed job's `streak.streak_length` (how many consecutive payloads that specific job has been failing). Render `phase` verbatim from Step 3.1.

#### 7.2: Blocking Jobs Summary Table

A table showing ALL blocking jobs with columns:
- Job Name
- RHCOS (the RHCOS version badge for this job from the snapshot's `rhcos_version` field: use `badge-rhcos9` / `badge-rhcos10` / `badge-rhcos-mixed` CSS classes; `rhcos9-default` renders with `badge-rhcos9`, `rhcos10-default` renders with `badge-rhcos10`. When a failure is variant-isolated, add a `variant-isolated` class to highlight the badge)
- Status (color-coded: green for passed, red for failed)
- Streak (consecutive failing payloads; "N/A" for passed)
- History (the `failure_pattern` from the snapshot, e.g., "F F F S F F", with color-coded markers)
- First Failed In (originating payload tag, linked to release controller)

#### 7.3: Failed Job Details

For each failed job, a collapsible section containing:

```html
<details>
  <summary class="failed-job">
    <span class="job-name">{job_name}</span>
    <span class="badge badge-{new|persistent}">{New Failure|Failing for N payloads}</span>
    <span class="badge badge-{rhcos9|rhcos10|rhcos-mixed}">{RHCOS 9|RHCOS 10|RHCOS 9+10}</span>
  </summary>
  <div class="detail-body">
    <h4>Prow Job</h4>
    <p><a href="{prow_url}">{prow_url}</a> | <a href="{gcs_url}">GCS Artifacts</a></p>

    <!-- Only include when failure is variant-isolated (see Cross-Job Pattern Recognition) -->
    <div class="variant-callout">
      This failure is isolated to RHCOS {version} jobs and does not appear in RHCOS {other_version} jobs,
      indicating an OS-variant-specific root cause (e.g., kernel, systemd, SELinux, or package differences
      between RHEL 9 and RHEL 10).
    </div>

    <h4>Failure Analysis</h4>
    <div class="analysis">{analysis_from_subagent}</div>

    <h4>Known Symptoms Seen</h4>
    <p class="symptoms">{comma-separated symptom summaries, or omit if "none"}</p>

    <h4>First Failed In</h4>
    <p><a href="{originating_payload_url}">{originating_payload_tag}</a></p>

    <h4>Candidate PRs (introduced in {originating_payload_tag})</h4>
    <table>
      <tr><th>Component</th><th>PR</th><th>Description</th><th>Score</th></tr>
    </table>
  </div>
</details>
```

#### 7.3b: RHCOS Changes

Include this section after the failed job details when any payload in the chain has RHCOS RPM changes. If RHCOS RPM suspects were identified (Step 6.1b), show them prominently first, then include the full RPM diff in a collapsible section.

```html
<div class="card">
  <h2>RHCOS Changes</h2>

  <!-- Only when RHCOS RPM suspects exist -->
  <div class="rhcos-suspect">
    <h3>Suspected RHCOS RPM Changes</h3>
    <p>The following RHCOS package updates may be contributing to failures. These cannot be reverted
       through the normal PR revert process — escalate to the RHCOS or platform team if confirmed.</p>
    <table>
      <tr><th>Package</th><th>Old Version</th><th>New Version</th><th>Variant</th><th>Affected Jobs</th><th>Rationale</th></tr>
      <tr>
        <td>{package}</td><td>{old_version}</td><td>{new_version}</td>
        <td><span class="badge badge-{rhcos9|rhcos10}">{variant}</span></td>
        <td>{comma-separated job names}</td><td>{rationale}</td>
      </tr>
    </table>
  </div>

  <!-- Always include full RPM diffs when RHCOS changes exist in any originating payload -->
  <details>
    <summary>Full RHCOS RPM Diffs ({originating_payload_tag})</summary>
    <h4>{rhcos_name} ({rhcos_tag})</h4>
    <table>
      <tr><th>Package</th><th>Old Version</th><th>New Version</th></tr>
      <!-- List all changed packages -->
    </table>
    <!-- Repeat for each RHCOS variant with changes -->
  </details>
</div>
```

Add this CSS for RHCOS suspect styling:
```css
.rhcos-suspect { background: rgba(188,140,255,0.1); border-left: 4px solid var(--purple); padding: 0.75rem 1rem; border-radius: 0 0.3rem 0.3rem 0; margin: 0.75rem 0; }
```

#### 7.4: Recommended Reverts

Include this section **before** the per-job details, immediately after the executive summary.

If revert candidates were identified (score >= 85):

```html
<div class="verdict verdict-revert">
  <h2>Recommended Reverts</h2>
  <p><strong>OCP Policy: PRs that break payloads MUST be reverted.</strong></p>
  <table>
    <tr><th>PR</th><th>Component</th><th>Description</th><th>Caused Failure In</th><th>Failing Since</th><th>Rationale</th></tr>
  </table>
  <h3>Automated Reverts</h3>
  <div class="revert-prompt">
    <button onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent.trim())">Copy</button>
    <pre>/ci:payload-revert {payload_tag}</pre>
  </div>
</div>
```

If no revert candidates:

```html
<div class="verdict verdict-none">
  <strong>No Recommended Reverts</strong>
  <p>No PRs were identified with sufficient confidence for revert recommendation.</p>
</div>
```

#### 7.5: Force-Accept Recommendation

If recommended (Step 6.4):

```html
<div class="verdict verdict-infra">
  <strong>Force-Accept Recommended</strong>
  <p>All blocking job failures are temporary infrastructure issues and no payload has been
     accepted in this stream for more than 18 hours.</p>
  <p>Baseline: <a href="{baseline_url}">{baseline_tag}</a> ({hours_since_baseline}h ago)</p>
</div>
```

#### 7.6: Review Notes

Include this section at the end of the report, before the footer:

```html
<div class="card">
  <h2>Adversarial Review</h2>
  <p>{review_summary}</p>
  <!-- If reviewer identified issues: -->
  <h4>Issues Found</h4>
  <ul>
    <li>{issue_description} — {action_taken}</li>
  </ul>
</div>
```

#### 7.7: Styling

The HTML must be fully self-contained with embedded CSS. Use a GitHub-inspired dark mode design. Use CSS variables for the color palette:

```css
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e;
  --green: #3fb950; --red: #f85149; --orange: #d29922;
  --blue: #58a6ff; --purple: #bc8cff;
}
```

Follow the styling conventions from the existing report format. All `<a>` links must use `target="_blank"`.

Include these RHCOS-specific styles:

```css
.badge-rhcos9 { background: rgba(139,148,158,0.15); color: var(--text-muted); font-size: 0.75rem; }
.badge-rhcos10 { background: rgba(188,140,255,0.15); color: var(--purple); font-size: 0.75rem; }
.badge-rhcos-mixed { background: rgba(210,153,34,0.15); color: var(--orange); font-size: 0.75rem; }
.badge.variant-isolated { border: 1px solid currentColor; }
.variant-callout { background: rgba(188,140,255,0.1); border-left: 4px solid var(--purple); padding: 0.75rem 1rem; border-radius: 0 0.3rem 0.3rem 0; margin: 0.75rem 0; font-size: 0.9rem; }
```

### Step 8: Generate JSON Data File

Use the `payload-autodl-json` skill to produce `payload-analysis-<sanitized_tag>-autodl.json`.

See the `payload-autodl-json` skill for the complete schema, row cardinality rules, and field rules.

### Step 9: Completeness Review

After generating the initial report and output files, launch a **dedicated subagent** to check that the analysis is complete and well-supported. The reviewer catches lazy or shallow work — it does NOT challenge or re-score rubric-based confidence scores.

The reviewer should receive **only** the following (NOT the full conversation history):

1. The `summary.json` snapshot data (payload metadata, failed jobs, streaks, test regressions, RHCOS changes)
2. The scored candidate list with per-component rubric breakdowns from Step 6
3. The `ANALYSIS_RESULT` blocks from all subagents in Step 4
4. The revert recommendations (if any)
5. The RHCOS RPM suspects (if any)

Use this prompt for the reviewer:

> You are a completeness reviewer for a payload failure analysis. Your job is to catch gaps in coverage and shallow analysis — NOT to challenge correct conclusions or lower confidence scores.
>
> **Snapshot data**: {summary.json contents — metadata, failed jobs with streaks, test regressions}
>
> **Subagent analyses**: {ANALYSIS_RESULT blocks for each failed job}
>
> **Scored candidates**: {list of (job, PR, score, rubric breakdown) tuples}
>
> **Revert recommendations**: {list of PRs recommended for revert, or "none"}
>
> Check for these specific problems:
>
> 1. **Missing skill invocations**: Was the `prow-job-analysis` skill actually loaded and used? A subagent that improvises without loading the appropriate skill produces shallow analysis.
>
> 2. **Shallow root causes**: Do root cause summaries cite specific error messages, code paths, or log excerpts? Or do they just restate test names and job status? "Test X failed" is not a root cause. "Test X failed because pod Y OOMKilled at 512Mi limit after PR Z increased memory usage in function F" is a root cause.
>
> 3. **Incomplete coverage**: Are there failed jobs with no subagent analysis or with only a one-line summary? Every failed blocking job deserves a thorough investigation.
>
> 4. **Wrong reference for failure type**: Did the analysis route to the correct reference — install (and metal for metal jobs) for install failures, and the test/flaky-test reference for test failures? Using the wrong reference produces misdirected analysis.
>
> 5. **Missing RHCOS RPM correlation**: If RHCOS RPM changes exist in the originating payload and failures are variant-isolated or involve OS-level components, was the correlation checked? Were relevant packages surfaced as suspects?
>
> **Rules**:
> - Do NOT suggest lowering confidence scores. If the rubric signals fired (error message match, new failure, component exclusivity), the score is correct. Period.
> - Do NOT suggest that a failure "might be infrastructure" when there is positive evidence linking it to a PR. Infrastructure classification requires affirmative evidence (cloud API errors, quota limits, network timeouts) — not just uncertainty about the code change.
> - Do NOT second-guess revert recommendations. When confidence >= 85 based on the rubric, the revert is warranted per OCP policy.
>
> For each issue found, provide:
> - **Issue**: One-line description
> - **Affected job(s)**: Which jobs are affected
> - **Recommendation**: Re-run subagent with correct skill, deepen analysis, or add missing coverage
>
> If the analysis is thorough, say so: "Analysis is complete — all jobs investigated with appropriate skills and specific root causes identified."

After receiving the reviewer's response:

- If coverage gaps are found (missing skill invocation, shallow analysis, wrong skill): re-run the affected subagent analyses, then re-score. Update the HTML report and YAML/JSON files.
- If the analysis is already thorough: note this in the report.
- **Never lower rubric-based confidence scores** based on the reviewer's response. The rubric is mechanical — if the signals fired, the score stands.
- Populate the "Adversarial Review" section (Step 7.6) in the HTML report with the reviewer's findings and any actions taken.

### Step 10: Final Self-Check, Save, and Present

Before presenting, run a **mechanical self-check** and fix any gap it finds — do not present a partial report:

1. **All three output files exist** in the current working directory and are non-empty:
   - HTML report: `payload-analysis-<sanitized_tag>-summary.html`
   - JSON data file: `payload-analysis-<sanitized_tag>-autodl.json`
   - Payload results YAML: `payload-results-<sanitized_tag>.yaml`
2. **The HTML contains every required section** from Step 7: header + executive summary (including the payload-chain context from Step 7.1), recommended reverts (or the "No Recommended Reverts" verdict), the force-accept verdict when applicable, the blocking-jobs summary table, a collapsible details block for **every** failed job, the RHCOS Changes section when any payload has RHCOS changes, and the Adversarial Review section.
3. **Cross-output consistency**: phase, failure counts, per-job root causes (including any adjudicated in Step 5b), and scored candidates agree across the HTML, YAML, and JSON.
4. **Every affirmative root cause appears as a scored `candidates[]` entry** — including causal CI-infrastructure changes, even when `failure_type: infra`.

If any check fails, fix it before presenting.

Then tell the user:
   - Path to each saved file
   - Brief text summary (number of failures, new vs persistent, key candidate PRs)
   - Whether the adversarial review changed any conclusions
   - Mention that `/ci:payload-revert` and `/ci:payload-experiment` can consume the YAML for automated actions

## Error Handling

### No Snapshot Available

If no snapshot is found and the snapshot script fails to create one:
```
Error: Could not locate or create a snapshot for {tag}. Run the payload-snapshot skill manually first.
```

### Subagent Failure

If a subagent fails to analyze a job, include the job in the report with:
```
Analysis unavailable: {error_message}
```
Do not let one failed subagent block the entire report.

### Missing PR Data

If the snapshot was created without `gh` authentication, PR diffs/comments will be absent. Note this in the report:
```
Note: PR diff data not available in snapshot. Scoring based on component match and timing only.
```

## Notes

- The snapshot is a **frozen archive** — it captures release controller, GitHub, and CI data as it was when the snapshot was taken. This enables re-analysis of historical payloads and provides reproducible results.
- Subagents still download artifacts from GCS (must-gather, pod logs, step logs) because these are not included in the snapshot. The snapshot provides the data scaffolding; subagents provide deep investigation.
- The adversarial review adds one subagent call but catches misattributions before they reach the report.
- For very large numbers of failed jobs (>8), consider whether some share the same underlying failure and group them in the report.

## See Also

- Related Skill: `payload-snapshot` — creates the snapshot data this skill consumes
- Related Skill: `payload-results-yaml` — schema for the results YAML
- Related Skill: `payload-autodl-json` — schema for the autodl JSON data file
- Related Skill: `prow-job-analysis` — deep test/install failure investigation (used by subagents)
- Related Command: `/ci:payload-revert` — stages reverts for high-confidence candidates
- Related Command: `/ci:payload-experiment` — tests medium-confidence candidates experimentally
