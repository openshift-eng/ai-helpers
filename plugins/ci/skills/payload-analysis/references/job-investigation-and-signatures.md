# Job Investigation and Signature Validation

## Investigate Each Failed Job in Parallel

For each failed blocking job in the **target payload**, launch a **parallel subagent** to investigate the failure. Pass the subagent the Prow URL and all previous attempt URLs collected from the snapshot.

Almost all blocking jobs install a cluster and then run tests, so the job name alone does not tell you the failure type. Each subagent therefore runs the `ci:prow-job-analysis` skill, which classifies the failure and routes to the correct specialized reference internally.

You MUST use the following prompt verbatim (substituting the placeholder values) when launching each subagent. Do NOT paraphrase, shorten, or write your own prompt — the specific instructions below are critical for analysis quality:

> Analyze the failure at <prow_url>. This job had <N> retries. The previous attempt URLs are: <previous_attempt_urls>.
>
> **Aggregated jobs**: If this is an aggregated job (has `aggregated-` prefix or an `aggregator` step), retries only re-run the aggregation analysis — they do NOT re-run the underlying test jobs. Therefore, only examine the most recent attempt; previous attempts contain the same underlying results and do not provide additional signal.
>
> **Non-aggregated jobs**: **Examine the final attempt first**, then compare with previous attempts to determine whether all retries failed the same way. If retries show different failure modes, note each one. Consistent failures across all attempts establish reproducibility, not the cause category; persistent infrastructure and CI failures can also repeat.
>
> **RHCOS version**: This job's cluster runs on **<rhcos_version>**. <rhcos_context>
>
> **RHCOS RPM changes**: Read `<summary_json_path>` and find the entry in `payloads[]` whose `tag` equals `<originating_payload_tag>`. If that entry has an `rhcos_changes[]` array, look up the RHCOS variant matching this job's `rhcos_version` using the tag mapping: `rhel-coreos` → `rhcos9`/`rhcos9-default`, `rhel-coreos-10` → `rhcos10`/`rhcos10-default`, both apply to `rhcos9_10`. Check whether any changed, added, or removed RPM packages overlap with the failure's root cause. If the failure involves OS-level components (kernel, bootloader, systemd, SELinux, rpm-ostree, cri-o, crun, runc, networking) and matching packages changed, note the potential correlation in your ANALYSIS_RESULT.
>
> Use the `ci:prow-job-analysis` skill for this investigation. It is the single entry point for every failed job: it identifies the job type, classifies the failure, and routes to the correct specialized reference — install, metal/bare-metal, test, upgrade, and more — internally. Do NOT pre-classify the failure yourself. Perform the full analysis, including downloading and analyzing must-gather when it is available.
>
> **IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.
>
> **Do NOT classify a failure as "infrastructure flake" or "transient" unless you have affirmative evidence** of an infrastructure problem (cloud API errors, quota exceeded, network timeouts from the cloud provider, Boskos lease failures, CI platform outages). The absence of an obvious code-level explanation does NOT make something infrastructure — it means you need to investigate deeper. If the evidence cannot distinguish product, infrastructure, and test causes, report the cause as unresolved.
>
> **Distinguish cause from detector.** A test that reports a real product or infrastructure failure is a detector, not the culprit. If infrastructure initiated the failure, return `failure_type: infra` even when the gating result is a test failure.
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
- failed_phase: setup|install|test|upgrade|teardown|unknown
- cause_category: product|infrastructure|test|indeterminate
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
- failure_modes: <atomic signatures with earliest abnormal event, causal chain, competing explanations, and missing evidence>
```

`failed_phase` records where the job surfaced the failure.
`cause_category` records what produced it. Use `failure_type: infra` when
infrastructure caused the failure even if a test detected it. Use
`root_cause_summary: unresolved` when the evidence cannot distinguish the
cause.

The `rhcos_rpm_correlation` field indicates whether the failure may be related to RHCOS RPM changes found in `summary.json`:
- `none` — no correlation found, or no RHCOS RPM changes exist for this job's variant
- `possible` — the failure involves OS-level components that overlap with changed packages, but the link is not definitive
- `likely` — error messages or failure behavior directly point to functionality provided by a changed RPM package

**Note for aggregated jobs**: Since only the final attempt is examined (retries re-run aggregation only), set `retries_consistent: only_final_examined` and `retry_summary: "Aggregated job — only final attempt examined (retries re-run aggregation only)"`.

**Important**: Launch ALL subagents in parallel for maximum speed. Do NOT set the `model` parameter — let subagents inherit the parent model, as these analysis tasks require a capable model.

### Cross-Platform and Cross-Job Failure Pattern Recognition

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

## Consult Previous Payload-Agent Analyses

Read the target payload's `payload.json` (at `SNAPSHOT_DIR/<payloads[0].payload>`) and check if a `claude-payload-agent` async job exists with state `Succeeded`. If so, fetch the HTML report from its Prow artifacts:

```
{prow_artifacts_url}/artifacts/claude-payload-agent/openshift-release-analysis-claude-payload-agent/artifacts/payload-analysis-{tag}-summary.html
```

Convert the Prow URL to a gcsweb URL and use WebFetch to read it.

**Important**: Previous analyses are a secondary input. Always complete your own analysis first, then compare. Use previous findings to bolster confidence, challenge assumptions, or fill gaps — never adopt conclusions without verifying against the snapshot data.

## Validate Failure Streaks

After collecting all subagent results, verify that consecutive failures across payloads share the same minimal causal signature. A consecutive job or test-name streak does NOT establish a causal streak.

Compare the subagent's root cause analysis for the target payload against the previous payload analyses or the failure signatures in the snapshot's streak data.

If a job fails in two consecutive payloads but for **different reasons**, treat each as a separate streak=1 failure with its own originating payload and candidate PRs. Re-split the streak and re-assign originating payloads before proceeding to scoring.

Track three distinct onsets:

1. **Job onset** — `streak.originating_payload`; only when the job began failing
2. **Test-name onset** — `test_failures.blocking[].first_failed_in`; only when that named test began failing
3. **Signature onset** — the first payload in the current contiguous run containing the same minimal causal signature

Only signature onset determines candidate PRs. Job onset and test-name onset are navigation hints and must never supply temporal points or candidate PRs by themselves.

### Construct Minimal Causal Signatures

Represent each distinct failure mode as its own atomic signature. Use the smallest stable set of fields that distinguishes the mechanism:

- failing operation or reconcile phase
- normalized error class or invariant
- causal component and resource kind
- one discriminating condition when needed to separate mechanisms

Exclude volatile or non-causal material:

- timestamps, durations that do not define the failure, retry numbers, payload tags, generated names, UIDs, IPs, and request IDs
- unrelated tests that failed in the same job
- cleanup fallout and terminal symptoms when an earlier trigger is known
- incidental infrastructure errors that did not participate in this failure mode

Do not concatenate every error in a job into one signature. A job with a product failure plus quota, DNS, or teardown noise contains multiple atomic signatures. Track each independently. An extra co-occurring signature neither extends nor resets another signature's streak.

Conversely, preserve infrastructure in the signature when it is part of the executed chain. For example, `DNS throttling → ignition record delayed beyond VM deadline` is one signature; an unrelated registry timeout in the same child is another. Match the mechanism, not the entire bag of symptoms.

Two occurrences share a signature only when their earliest discriminating event, failing operation, and normalized error class agree. Treat identical terminal errors with different triggers as different signatures. Treat changed downstream symptoms with the same observed trigger and operation as the same signature.

### Find the Signature Boundary

Starting at the target payload, walk backward through raw child artifacts and:

1. Classify each prior payload as one of:
   - `present`: the same atomic signature is observed.
   - `verified_absent`: the same operation or reconcile phase executed to completion under a comparable topology and the signature did not occur, or affirmative evidence contradicts the signature.
   - `unobservable`: the relevant path was not reached, the job failed earlier, the test did not run, or the artifacts cannot establish whether the signature occurred.
2. Continue across unrelated failures and `unobservable` payloads; neither breaks nor establishes the signature streak.
3. Stop only at the first `verified_absent` payload.
4. Set an exact signature onset only when the earliest `present` payload after that boundary is the next chronological payload. If one or more `unobservable` payloads lie between the `verified_absent` boundary and the earliest `present` observation, record an onset interval rather than assigning the signature to the first later observation.

Absence is evidence only when there was an opportunity to observe the signature. A payload that failed during provisioning cannot prove that a later test or controller-path failure was absent. When the boundary is `unobservable` or spans an onset interval, do not fall back to job or test-name onset, do not award temporal-correlation points, and mark `exact_signature_timing` as `unknown`.

Establish this before enumerating candidate PRs. Record all three onsets, the normalized atomic signature, and the raw evidence establishing its boundary.

## Adjudicate Conflicting Root Causes

When two or more investigations reach **contradictory root causes for the same failure signature** (same test, same operation, or same error class — across jobs, across retries, or between a subagent and a previous analysis), the analysis is **UNRESOLVED**. It is *not* a tie to be broken by whichever explanation feels more plausible. Resolve it only with discriminating evidence, applying these rules:

- **Discriminating evidence must come from the exact failing operation or phase** — the specific subcommand, step, or reconcile loop that actually errored, not from adjacent activity.
- **"Cleared" requires positive evidence from the failing code path.** A candidate is exonerated only by positive evidence that its code path executed and completed without error *during the failing operation itself*. A candidate succeeding in a *different* subcommand, phase, or job does **not** clear it.
- **Absence of a log line is not evidence when the log is truncated.** If the relevant log was truncated, rotated, or never captured, treat the missing line as *unknown*, never as proof that a code path did not execute.
- **A causal chain must be shown to execute, not merely shown to be possible.** Demonstrate that the proposed mechanism actually ran during the failing operation (via timestamps, ordering, or an emitted log/metric). "This change *could* cause this" is a hypothesis, not a root cause.
- **When you override a subagent's conclusion, update the stored per-job root cause** so the streak data, YAML, JSON, and HTML all reflect the adjudicated cause. Divergent per-job root causes across outputs are a defect caught by the final self-check.

**Tenacity booster:** Finding a plausible mechanism is the *midpoint* of the investigation, not the end. When rival explanations exist, your job is to *discriminate between them* with evidence from the failing operation — not to stop at the first mechanism that could work. If the evidence cannot discriminate, record the failure mode as UNRESOLVED with its competing hypotheses rather than committing to a guess (a wrong-PR attribution is far more damaging than an honest "unresolved").

## Build the Executed Causal Chain

For every distinct failure mode, build an ordered chain from the earliest abnormal event to the payload-gating symptom. Assign each observed event one causal role:

1. **Trigger** — the first abnormal event that initiated the failure
2. **Propagation** — a dependency or controller carried the failure forward
3. **Amplifier or recovery defect** — retry, fallback, cleanup, or error handling made the original failure worse or persistent
4. **Detector** — a test or health check reported an already-existing problem
5. **Terminal symptom** — the final visible error, timeout, invariant, or panic

Anchor every link with a timestamp, log line, object transition, metric, or other artifact from the failing run. Record missing links as unknown. Do not reverse the chain merely because the terminal symptom is easier to find than the trigger.

Use these role-specific rules:

- A detector is not the product or infrastructure cause it detected. If a test reports a real violation initiated by infrastructure, classify the root cause as `infra`; do not call the test the culprit. Classify the test as causal only when its own contract, framework behavior, or implementation is defective.
- A cleanup failure or diagnostic panic can be an important resilience defect without being the trigger. Report it separately and do not attribute the original failure to the PR that only changed cleanup or observation.
- A PR that improves detection can make a latent defect newly visible. Treat that PR as the cause only when the newly enforced contract is itself incorrect; otherwise identify the behavior that violated the contract.
- In a broad merge, identify the smallest changed behavior that executed. Do not recommend reverting the containing PR solely because the failing helper, test, or error string is present in that PR.

Before scoring, state the earliest discriminating event, its causal role, and the evidence ordering it before downstream symptoms. If the earliest available artifact begins after the failure was already in progress, say so and keep the conclusion unresolved unless another independent signal closes the gap.

Do not recommend standing up a specially configured cluster solely to close an
analysis gap. Use the archived artifacts, source flow, and already available
paired or repeated experiments.
