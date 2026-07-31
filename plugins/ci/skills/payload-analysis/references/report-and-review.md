# Report Generation and Review

## Generate HTML Report

Create a self-contained HTML file named `payload-analysis-<tag>-summary.html` in `$OUTPUT_DIR`. The tag should be sanitized for use as a filename.

The report must include the following sections:

### Header and Executive Summary

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

**Payload-chain context** surfaces the streak at a glance — include all of the fields above. Derive them from the snapshot: `consecutive_rejection_count` is the number of consecutive non-`Accepted` payloads in the chain up to and including this one (the chain runs from the last accepted baseline forward — see `chain_length` and the `payloads[]` phases); the last accepted payload is `baseline_tag`, cut `hours_since_baseline` hours ago; per-job persistence is each failed job's `streak.streak_length` (how many consecutive payloads that specific job has been failing). Render `phase` verbatim from the payload metadata.

For a Ready payload, state that the report covers completed blocking jobs so
far and that other jobs may still be running.

### Blocking Jobs Summary Table

A table showing ALL blocking jobs with columns:
- Job Name
- RHCOS (the RHCOS version badge for this job from the snapshot's `rhcos_version` field: use `badge-rhcos9` / `badge-rhcos10` / `badge-rhcos-mixed` CSS classes; `rhcos9-default` renders with `badge-rhcos9`, `rhcos10-default` renders with `badge-rhcos10`. When a failure is variant-isolated, add a `variant-isolated` class to highlight the badge)
- Status (color-coded: green for passed, red for failed)
- Streak (consecutive failing payloads; "N/A" for passed)
- History (the `failure_pattern` from the snapshot, e.g., "F F F S F F", with color-coded markers)
- First Failed In (originating payload tag, linked to release controller)

### Failed Job Details

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

The failure analysis must include the earliest abnormal event, minimal causal
signature and boundary, executed causal chain, cause category, competing
explanations, and missing evidence. Show every candidate's itemized score,
revert gates, and eligibility. If a test detected an infrastructure failure,
identify the test as the detector and classify the cause as infrastructure.

### RHCOS Changes

Include this section after the failed job details when any payload in the chain has RHCOS RPM changes. If RHCOS RPM suspects were identified during attribution, show them prominently first, then include the full RPM diff in a collapsible section.

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

### Recommended Reverts

Include this section **before** the per-job details, immediately after the executive summary.

If revert candidates were identified (`revert_eligible: true`):

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
  <p>No PR passed both the confidence threshold and every revert action gate.</p>
</div>
```

### Force-Accept Recommendation

If force-accept is recommended:

```html
<div class="verdict verdict-infra">
  <strong>Force-Accept Recommended</strong>
  <p>All blocking job failures are temporary infrastructure issues and no payload has been
     accepted in this stream for more than 18 hours.</p>
  <p>Baseline: <a href="{baseline_url}">{baseline_tag}</a> ({hours_since_baseline}h ago)</p>
</div>
```

### Review Notes

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

### Styling

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

## Generate JSON Data File

Use the `ci:payload-autodl-json` skill to produce `$OUTPUT_DIR/payload-analysis-<sanitized_tag>-autodl.json`.

See the `payload-autodl-json` skill for the complete schema, row cardinality rules, and field rules.

## Completeness Review

After generating the initial report and output files, launch a **dedicated adversarial subagent** to check that the analysis is complete, causally supported, and safe to act on. The reviewer must falsify the leading conclusion where the evidence permits and independently challenge confidence and revert eligibility.

Build a structured **adversarial evidence dossier** before launching the
reviewer. The reviewer should receive **only** this dossier (NOT the full
conversation history). It must contain:

1. The `summary.json` snapshot data (payload metadata, failed jobs, streaks,
   test regressions, RHCOS changes)
2. A skill-invocation record for every failed-job investigator: job, invoked skill name,
   and whether its full instructions were loaded
3. Every atomic failure mode, not only the dominant one, with its normalized
   minimal signature, job onset, test-name onset, signature onset, and the raw
   evidence proving the signature boundary
4. A timestamp-ordered causal chain for each failure mode, including roles,
   artifact paths, short raw excerpts, and explicit unknown links
5. The scored `(job, failure mode, candidate)` tuples with every rubric signal,
   confidence score, and relevant diff paths/excerpts
6. Each candidate's five named revert gates, status, and evidence, plus
   `revert_eligible`
7. The revert recommendations and RHCOS RPM suspects, if any

Do not substitute prose summaries for missing raw evidence. Mark dossier fields
unknown when the artifact is missing or contradictory; this lets the reviewer
distinguish an unsupported claim from an omitted investigation.

Use this prompt for the reviewer:

> You are an adversarial reviewer for a payload failure analysis. Begin with the assumption that the leading diagnosis and every revert recommendation are wrong. Falsify them wherever the supplied evidence permits. Check both completeness and causal validity.
>
> **Snapshot data**: {summary.json contents — metadata, failed jobs with streaks, test regressions}
>
> **Subagent analyses**: {ANALYSIS_RESULT blocks for each failed job}
>
> **Scored candidates**: {list of (job, PR, score, rubric breakdown) tuples}
>
> **Causal chains and signature boundaries**: {timestamp-ordered dossier entries}
>
> **Revert gates**: {candidate gate matrix with status and evidence}
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
> 6. **Reversed causal chain**: Does the analysis begin at the earliest abnormal event, or has it mistaken a downstream timeout, invariant, test assertion, cleanup failure, or panic for the trigger? Check the trigger/propagation/amplifier/detector/terminal-symptom roles and their timestamp ordering.
>
> 7. **Correlation presented as causation**: Does a candidate rely only on recency, component exclusivity, subsystem proximity, multi-job appearance, or missing presubmit coverage? If changed behavior was not observed executing before the failure, reject the attribution at the revert action gate.
>
> 8. **Unsafe revert gate**: For every recommended revert, independently verify all five action-gate items. A rubric score alone never authorizes a revert.
>
> 9. **Weak counterfactual**: Treat persistence of the same signature after removing a PR as exculpatory. Do not treat one passing retry after removal as proof unless paired or repeated evidence isolates the change.
>
> 10. **Wrong streak boundary**: Did candidate selection use the current atomic signature's verified onset, or a longer job/test-name streak? Check that signatures are minimal and that unrelated infrastructure, cleanup, or co-failing tests were not concatenated into the signature. If the preceding payload lacks discriminating artifacts, reject temporal points rather than guessing.
>
>
> **Rules**:
> - Require affirmative evidence before declaring infrastructure, but investigate infrastructure signals even when a product PR is temporally correlated.
> - Distinguish a test that caused a failure from a test that reported a real infrastructure or product failure.
> - Remove a revert recommendation when any action-gate item lacks evidence.
>
> For each issue found, provide:
> - **Issue**: One-line description
> - **Affected job(s)**: Which jobs are affected
> - **Recommendation**: Re-run subagent with correct skill, deepen analysis, or add missing coverage
>
> If the analysis is thorough, say so: "Analysis is complete — all jobs investigated with appropriate skills and specific root causes identified."

After receiving the reviewer's response:

- If coverage gaps are found (missing skill invocation, shallow analysis, wrong skill): re-run the affected subagent analyses, then re-score. Update the HTML report and YAML/JSON files.
- If the reviewer finds a wrong or unverified signature boundary, a reversed
  causal chain, a missing atomic failure mode, or candidate enumeration from the
  wrong payload, discard the affected derived conclusions. Re-run the raw
  artifact analysis for that failure mode, then repeat signature validation,
  causal-chain construction, attribution, and scoring before regenerating
  every output. Do not merely lower a score on stale candidates.
- If the analysis is already thorough: note this in the report.
- Re-score affected candidates when the reviewer finds an inflated signal or action-gate failure. Preserve the itemized rubric sum and gate evidence in the outputs.
- Populate the "Adversarial Review" section in the HTML report with the reviewer's findings and any actions taken.

## Final Self-Check, Save, and Present

Before presenting, confirm that **all failed-job investigators and the adversarial reviewer have completed and returned their results** — never assemble the report while an investigation is still outstanding. Then run a **mechanical self-check** and fix any gap it finds — do not present a partial report:

1. **All three output files exist at `$OUTPUT_DIR`** and are non-empty. Verify these three exact spec'd filenames — do NOT glob, so that a stray file from a previous run cannot satisfy the check:
   - HTML report: `$OUTPUT_DIR/payload-analysis-<sanitized_tag>-summary.html`
   - JSON data file: `$OUTPUT_DIR/payload-analysis-<sanitized_tag>-autodl.json`
   - Payload results YAML: `$OUTPUT_DIR/payload-results-<sanitized_tag>.yaml`
2. **The HTML contains every required section**: header + executive summary with payload-chain context, recommended reverts (or the "No Recommended Reverts" verdict), the force-accept verdict when applicable, the blocking-jobs summary table, a collapsible details block for **every** failed job, the RHCOS Changes section when any payload has RHCOS changes, and the Adversarial Review section.
3. **Cross-output consistency**: phase, failure counts, adjudicated per-job root causes, and scored candidates agree across the HTML, YAML, and JSON.
4. **Every affirmative repository-change root cause appears as a scored `candidates[]` entry** — including causal CI-infrastructure changes, even when `failure_type: infra`.
5. **Every candidate has all five structured revert gates**, and
   `revert_eligible` is true exactly when confidence is at least 85, the first
   four gates pass, and the experiment gate passes or is `not_applicable`. The
   HTML recommends only eligible candidates.

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
Note: PR diff data not available in snapshot. Attribution is incomplete; no revert is recommended without executed-path evidence.
```

## Notes

- Subagents still download artifacts from GCS (must-gather, pod logs, step logs) because these are not included in the snapshot. The snapshot provides the data scaffolding; subagents provide deep investigation.
- The adversarial review adds one subagent call but catches misattributions before they reach the report.
- For very large numbers of failed jobs (>8), consider whether some share the same underlying failure and group them in the report.

## See Also

- Related Skill: `ci:payload-snapshot` — creates the snapshot data this skill consumes
- Related Skill: `ci:payload-results-yaml` — schema for the results YAML
- Related Skill: `ci:payload-autodl-json` — schema for the autodl JSON data file
- Related Skill: `ci:prow-job-analysis` — deep test/install failure investigation (used by subagents)
- Related Command: `/ci:payload-revert` — stages reverts for eligible candidates
- Related Command: `/ci:payload-experiment` — tests medium-confidence candidates experimentally
