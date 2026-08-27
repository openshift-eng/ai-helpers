# Investigation Subagent Prompt (Step 4)

Use the following prompt **verbatim** (substituting the placeholder values) when launching each per-job investigation subagent. Do NOT paraphrase, shorten, or write a different prompt — these specific instructions are critical for analysis quality.

## Prompt

> Analyze the failure at <prow_url>. This job had <N> retries. The previous attempt URLs are: <previous_attempt_urls>.
>
> **Aggregated jobs**: If this is an aggregated job (has `aggregated-` prefix or an `aggregator` step), retries only re-run the aggregation analysis — they do NOT re-run the underlying test jobs. Therefore, only examine the most recent attempt; previous attempts contain the same underlying results and do not provide additional signal.
>
> **Non-aggregated jobs**: **Examine the final attempt first**, then compare with previous attempts to determine whether all retries failed the same way. If retries show different failure modes, note this — it distinguishes consistent regressions from intermittent/infrastructure issues. Consistent failures across all attempts strongly indicate a product regression rather than flakiness.
>
> **RHCOS version**: This job's cluster runs on **<rhcos_version>**. <rhcos_context>
>
> **RHCOS RPM changes and changelogs**: Read `<summary_json_path>` and find the entry in `payloads[]` whose `tag` equals `<originating_payload_tag>`. If that entry has an `rhcos_changes[]` array, look up the RHCOS variant matching this job's `rhcos_version` using the tag mapping: `rhel-coreos` → `rhcos9`/`rhcos9-default`, `rhel-coreos-10` → `rhcos10`/`rhcos10-default`, both apply to `rhcos9_10`. Check whether any changed, added, or removed RPM packages overlap with the failure's root cause. If the failure involves OS-level components (kernel, bootloader, systemd, SELinux, rpm-ostree, cri-o, crun, runc, networking) and matching packages changed, **read the RPM changelog** to see what actually changed — the changelog is the RPM equivalent of a PR's `code.diff`. To find it: in `<summary_json_path>`, check `rpm_changelogs[]` at the top level for the baseline entry (`is_baseline: true`) for the matching variant — its `diff.changed[]` entries each have a `changelog` field. For the originating payload's hop specifically: find `rpm_changelogs[]` in `payloads[]` for `<originating_payload_tag>` matching the variant, and read the file at its `changelogs` path (relative to `<snapshot_dir>`). Multiple binary RPMs built from the same source RPM share identical changelogs — read it once. A changelog entry that describes a change in the subsystem or behavior seen in the failure is strong evidence; a changelog about unrelated subsystems rules the package out. Note the correlation level and any relevant changelog entries in your ANALYSIS_RESULT.
>
> Use the `ci:prow-job-analysis` skill for this investigation. It is the single entry point for every failed job: it identifies the job type, classifies the failure, and routes to the correct specialized reference — install, metal/bare-metal, test, upgrade, and more — internally. Do NOT pre-classify the failure yourself. Perform the full analysis, including downloading and analyzing must-gather when it is available.
>
> **IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.
>
> **Do NOT classify a failure as "infrastructure flake" or "transient" unless you have affirmative evidence** of an infrastructure problem (cloud API errors, quota exceeded, network timeouts from the cloud provider, Boskos lease failures, CI platform outages). The absence of an obvious code-level explanation does NOT make something infrastructure — it means you need to investigate deeper. Default to treating failures as potential product regressions until evidence proves otherwise.
>
> **Build a cited causal chain**: Start with exactly `Why did this job fail?`,
> answer one causal layer at a time, and ask the next natural "why" until you
> reach the deepest cause the artifacts prove. Every answer needs at least one
> exact log or code citation. Copy each cited source file under
> `<evidence_dir>/<job_slug>/` and report its path relative to `<output_dir>`,
> with a 1-indexed inclusive line range and a note explaining how the excerpt
> proves that answer. Preserve the durable GCS, Prow, or GitHub URL as
> `artifact_url`. If the evidence ends, say the next cause is unknown; do not
> fill the gap with a plausible mechanism.
>
> Return a concise summary including: failure type (install vs test), root cause, key error messages, and any relevant log excerpts. Do not ask user questions. Keep the output concise for inclusion in a summary report.
>
> If the job is an aggregated job (has `aggregated-` prefix in the name or an `aggregator` container/step), also return the **underlying job name** (e.g., `periodic-ci-openshift-release-main-ci-4.22-e2e-aws-upgrade-ovn-single-node`). This is found in the junit-aggregated.xml artifacts — each `<testcase>` has `<system-out>` YAML data with a `humanurl` field linking to individual runs whose URL path contains the underlying job name. The underlying job name cannot be derived from the aggregated job name — it must be extracted from the artifacts.

## Placeholder Values

Where `<rhcos_version>` is the `rhcos_version` field from the snapshot's failed job entry, `<rhcos_context>` is one of:

- For **`rhcos9`** or **`rhcos9-default`**: "RHCOS 9 is based on RHEL 9 — the standard CoreOS variant for this OCP version."
- For **`rhcos10`** or **`rhcos10-default`**: "RHCOS 10 is based on RHEL 10 with a different kernel, systemd, SELinux policy, and package versions than RHCOS 9. If the failure involves OS-level components (kernel, bootloader, rpm-ostree, MCO, Ignition), consider whether RHEL 10 differences could be the root cause."
- For **`rhcos9_10`** (heterogeneous): "This is a heterogeneous cluster with both RHCOS 9 and RHCOS 10 nodes. Failures may be specific to one node variant — check whether failing nodes are RHCOS 9 or RHCOS 10 when node-level logs are available."

`<summary_json_path>` is the absolute path to the snapshot's `summary.json` file, and `<originating_payload_tag>` is the failure mode's `first_failed_in` value (Step 3.3/Step 5) — not the job-level `streak.originating_payload`, which can predate the regression when a job has multiple failure modes.

`<output_dir>` is the analysis output directory captured in Step 1 and
`<evidence_dir>` is its `payload-evidence` child. Give each subagent a unique
`<job_slug>` child so parallel investigations never overwrite one another.

Under `--as-of` (Step 1), append the cutoff timestamp to the prompt and instruct the subagent to discard post-cutoff artifacts and discussion.

## Structured Return Format

Instruct each subagent to include an `ANALYSIS_RESULT` block at the end of its response:

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
- rhcos_rpm_changelog_evidence: <for each suspect package, the specific changelog entry that relates to the failure, or "none" if the changelog was read but contained no relevant entries, or "unavailable" if no changelog data exists in the snapshot>
- causal_chain:
  - question: Why did this job fail?
    answer: <one causal layer, directly supported by the proof below>
    proof:
      - type: log|code
        artifact: payload-evidence/<job_slug>/<copied-source-file>
        artifact_url: <durable GCS, Prow, or GitHub URL when available>
        lines: [<1-indexed-start>, <inclusive-end>]
        note: <why this exact excerpt proves the answer>
  - question: <the next why raised by the previous answer>
    answer: <the next proven causal layer, or an explicit statement that the trail ends>
    proof:
      - type: log|code
        artifact: payload-evidence/<job_slug>/<copied-source-file>
        artifact_url: <durable upstream URL when available>
        lines: [<1-indexed-start>, <inclusive-end>]
        note: <why this exact excerpt proves the answer>
```

The `rhcos_rpm_correlation` field indicates whether the failure may be related to RHCOS RPM changes found in `summary.json`:

- `none` — no correlation found, or no RHCOS RPM changes exist for this job's variant
- `possible` — the failure involves OS-level components that overlap with changed packages, but the link is not definitive (changelog may or may not contain relevant entries)
- `likely` — error messages or failure behavior directly point to functionality provided by a changed RPM package, **especially when the RPM changelog text describes a change in the exact subsystem or behavior seen in the failure**

**Note for aggregated jobs**: Since only the final attempt is examined (retries re-run aggregation only), set `retries_consistent: only_final_examined` and `retry_summary: "Aggregated job — only final attempt examined (retries re-run aggregation only)"`.
