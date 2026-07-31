# Attribution and Action Decisions

## Collect Investigation Results and Identify Revert Candidates

Wait for all subagents to complete and collect their analysis results. For each failed job, you now have:

- **Job name** and **Prow URL** (from snapshot)
- **Failure analysis** (from subagent)
- **Streak data** (from snapshot: `streak_length`, `originating_payload`, `failure_pattern`)
- **Candidate PRs** (from snapshot: originating payload's `prs[]`)

The snapshot's job-level originating payload and candidate list are
preliminary. For each atomic failure mode, replace them with the validated
signature onset and collect the PRs introduced at that boundary. Do not let a
longer job or test-name streak select the candidates.

### Check for CI Infrastructure Changes

For each failed job, check whether changes to the CI step-registry in the `openshift/release` repo correlate with the failure. These changes (modified step scripts, updated URLs, changed environment variables) will never appear in the snapshot's component PR list because they are not payload component changes — but they can break jobs just as effectively.

For each atomic failure mode, extract the date from its validated signature
onset payload, not the preliminary job or test-name onset. The tag format is
`<version>-0.<stream>-YYYY-MM-DD-HHMMSS` or
`<version>-0.<stream>-<arch>-YYYY-MM-DD-HHMMSS` for non-amd64. The date is
always the last `YYYY-MM-DD` segment before the `HHMMSS` suffix (for example,
`2026-06-16` from `5.0.0-0.nightly-2026-06-16-185706` or
`5.0.0-0.nightly-arm64-2026-06-16-185706`). Compute a time window: `since` =
the signature-onset date minus 1 day at `T00:00:00Z`; `until` = that date plus
1 day at `T23:59:59Z`. If only an onset interval is known, search the full
interval but do not award exact-timing points.

**First, get all step-registry commits in the time window:**

```bash
gh api "repos/openshift/release/commits?path=ci-operator/step-registry&since=<since_date>T00:00:00Z&until=<until_date>T23:59:59Z&per_page=100" \
    --jq '.[] | {sha: .sha[0:11], date: .commit.committer.date, message: (.commit.message | split("\n")[0])}'
```

If exactly 100 results are returned, fetch subsequent pages by appending `&page=2`, `&page=3`, etc. until a page returns fewer than 100 results.

**Triage the results using the test-failure and build-log context collected above.** Extract the key signals from the failure: error messages, failing URLs/domains, exit codes, failing script names, and affected subsystems. Use commit messages as an initial filter, but prioritize inspection of diffs when filenames or modified directories appear relevant even if the commit message is generic — many `openshift/release` commits have uninformative messages like "Fix typo" or "Update image" while the actual diff contains the interesting change. Relevant commits typically touch the same subsystem, tool, or infrastructure that appears in the error (e.g., a commit modifying mirror URLs when the failure shows curl errors to a new domain; a commit changing proxy configuration when the failure is a connection refused through a proxy). Ignore commits that clearly target unrelated teams or subsystems (hypervisor updates, unrelated repo onboarding, OWNERS file changes).

For each commit that looks potentially related, retrieve the changed files:

```bash
gh api "repos/openshift/release/commits/<sha>" --jq '.files[] | {filename, patch}'
```

First check the filenames — if none correspond to the failing step or any of its dependencies, eliminate that commit immediately without reading the patches. For commits that do touch relevant files, inspect the patches for URL changes, configuration modifications, or script logic changes that could cause the observed failure.

If the commit message includes a PR reference (typically `(#NNNNN)`), retrieve the PR details:

```bash
gh api "repos/openshift/release/commits/<sha>"
```

Inspect the referenced PR details and diff when they help explain the change.

**After the failed-job investigations are available**, do a targeted search using the specific step that failed. From the job analysis, identify the step-registry path of the step that actually errored (e.g., `gather/must-gather`, `baremetalds/devscripts/proxy`, `ipi/install/install`). Search for recent changes to that exact step and to related steps in the same workflow chain:

```bash
gh api "repos/openshift/release/commits?path=ci-operator/step-registry/<step_subpath>&since=<since_date>T00:00:00Z&until=<until_date>T23:59:59Z&per_page=10" \
    --jq '.[] | {sha: .sha[0:11], date: .commit.committer.date, message: (.commit.message | split("\n")[0])}'
```

If this finds nothing, also check steps that run earlier in the workflow and set up infrastructure the failing step depends on (e.g., if `openshift-e2e-test` fails due to connectivity, check `baremetalds/devscripts/proxy` or `ipi/conf` steps that configure networking).

**Scoring CI infrastructure candidates.** If a commit/PR modified a step that the failing job executes (or a shared dependency of that step), flag it as a **CI infrastructure candidate** and score it alongside component PR candidates. When the failure's error messages reference URLs, domains, binaries, or configurations that were changed by the PR, the error message match signal (+40) should fire strongly. The key test: does the PR's diff introduce, modify, or remove something that appears in the error output?

**A causal CI-infrastructure change MUST appear as a scored entry in the `candidates[]` output**, exactly like a component PR — even when the overall `failure_type` is `infra`. Classifying a failure as infrastructure does not exempt its cause from structured output. Unlike a self-resolving lease/quota blip, a CI-config change is a persistent issue that needs a human fix or a revert, so it must be visible to the downstream revert/experiment commands, not buried in prose.

This step catches failures caused by CI tooling changes (mirror URL migrations, proxy configuration updates, script refactors) that are invisible to the snapshot's PR tracking.

### Correlate Failures with Candidate PRs

For each failed job, cross-reference the failure analysis from the subagent with the candidate PRs from the originating payload. Read the PR's `code.diff` file (at the path from `summary.json` → `payloads[].prs[].diff`) to check for code-level correlation.

If a subagent traced the root cause to a PR outside the payload (e.g., an `openshift/release` PR that modified a CI step registry script), include that PR as a candidate.

**Before scoring, mechanically enumerate every distinct failure mode for each job — do not score only the dominant one.** A single job can fail for more than one reason (e.g., an install timeout *and* an unrelated test regression). For each failed job, first write out each distinct failure mode the subagent identified as an explicit list, then run every candidate PR through the rubric **once per failure mode** — a PR that explains failure mode A does not automatically explain failure mode B. Do not collapse a job down to its loudest symptom and score only that. Any failure mode you dismiss as a flake (or as pre-existing) MUST cite the specific evidence for that dismissal — a passing retry with no code change, the same test failing on the *accepted* baseline, or a known-flaky test ID — never an unsupported "intermittent" label.

Score each (failed job, failure mode, candidate PR) tuple using the following weighted rubric:

| Signal | Weight | Criteria |
|--------|--------|----------|
| New failure mode | +30 | The minimal causal signature has a **verified boundary in raw artifacts**: it is present in the originating payload and absent in the immediately preceding comparable payload, and is plausibly attributable to code that changed (some PR touches the implicated code path). If the boundary is unknown, or only the job/test-name onset is known, award +0. A brand-new symptom with no changed code behind it does not earn this signal (see infrastructure exclusion below). |
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

The `confidence_score` MUST equal `min(100, sum of itemized signals)`, each signal at exactly its defined weight, one line of evidence per claimed signal. No unclaimed points, no unlisted signals.

**Apply the rubric mechanically.** Sum the weights for each signal that fires on concrete evidence. Re-verify every maximum-tier claim: is the error-message match a true verbatim string or symbol match (+40), or really only same-subsystem (+10)? Is this genuinely the sole modifier of the component (+30)? Downgrade any tier that does not survive this check.

The rubric ranks hypotheses; it does not by itself prove causation or authorize a revert. The independent revert action gates below make that decision.

**Multi-job evidence requires independent causal signatures.** Aggregator membership, reused child runs, and several terminal symptoms produced by one failed cluster are not independent confirmations. Award multi-job correlation only when separate clusters or executions show the same ordered causal signature.

**Counterfactual and experimental-revert evidence must be interpreted asymmetrically.** The same causal signature persisting after a candidate is removed is strong evidence against that candidate. A single passing aggregate after a revert is weak evidence because flakes and infrastructure failures also pass on retry; require paired controls or repeated runs that isolate the change before treating a pass as causal proof.

**Infrastructure exclusion — do not let unrelated PRs accumulate points.** The rubric measures *product-code causation*. When the root cause is affirmatively infrastructure or an affirmatively-identified CI-config change, payload component PRs with **no error-message and no code-path correlation** to the failure must score **at or near zero**. Do not award "new failure mode" or bare "component exclusivity" points to a PR that merely happens to be present in the payload — "new failure mode" fires only when the failure is plausibly attributable to code that changed. A new symptom whose actual cause is a lease timeout, a quota block, or a step-registry edit is not evidence against an unrelated component PR.

**"Intermittent" and "flake" are conclusions requiring evidence, not default labels.** Before dismissing a failure as a flake, confirm affirmative evidence for it (e.g., the same job passed on retry with no code change, or it is a known-flaky test that also fails on *accepted* payloads). First check whether any candidate PR touches the failing code path: a reproducible failure in code that changed is a regression, not a flake, even if it does not reproduce on every run.

**When a failed job ends up with zero causally-linked candidates, state why — explicitly, per job.** An empty candidate list is itself a claim: that no payload PR and no CI-infrastructure change is causally linked to the failure. Justify it rather than leaving it blank. For each such job, record a one-line rationale explaining why no payload PR explains the failure (e.g., "root cause is a Boskos lease timeout — no component PR touches the failing path"; "failure also reproduces on the accepted baseline payload, so it predates every candidate PR in this originating payload"). State the cross-job correlation explicitly: note whether the same failure mode appears in other failing jobs (pointing to shared infrastructure or a common dependency) or is isolated to this one. A silent empty candidate list is indistinguishable from an un-investigated job and is not acceptable.

### RHCOS RPM Change Correlation

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

### Propose Revert Candidates

For each candidate PR with a confidence score of **>= 85**, consider it for the separate **revert action gate**. A PR qualifies only when:

1. The changed code path is observed executing before the failure
2. The executed change explains the full causal chain, not only a detector, amplifier, cleanup failure, or terminal symptom
3. The timing is exact — the same failure mode passed before the originating payload
4. Infrastructure, platform, test-framework, and external-dependency alternatives have affirmative evidence against them
5. Any experimental evidence reliably isolates the change; one unpaired passing retry is insufficient

Record each gate item under these stable names, with `status:
"pass"|"fail"|"unknown"` and concrete evidence:

1. `changed_path_executed`
2. `full_causal_chain`
3. `exact_signature_timing`
4. `alternatives_excluded`
5. `experiment_isolates_change`

For `experiment_isolates_change`, use `not_applicable` when no experiment informed the conclusion. Use `pass`, `unknown`, or `fail` when experimental evidence was used, according to whether it reliably isolated the change. A high
hypothesis-ranking score with any failed or unknown gate item is **not** a
revert candidate.

Persist the decision for every scored candidate in the results YAML as
`revert_gates` and `revert_eligible`. Set `revert_eligible: true` if and only if the confidence score is at least 85, the first four gates pass, and `experiment_isolates_change` is `pass` or `not_applicable`. Confidence alone
must never be interpreted as revert authorization.

Per OCP policy, PRs that break payloads MUST be reverted. When and only when
`revert_eligible` is `true`, the report must clearly state that a revert is
required — not optional. A high-confidence hypothesis with any failed or
unknown gate is not an authorized revert.

For each revert candidate, record: PR URL, description, component, confidence score with rationale.

**Do NOT propose reverts for**: Infrastructure failures, flaky tests that also fail on accepted payloads, jobs where analysis is inconclusive.

**Special case — Kubernetes rebase version skew.** When the candidate PR is a **Kubernetes rebase** (a PR in the `openshift/kubernetes` repo, typically a rebase/version-bump onto a new upstream Kubernetes release) **AND** the failures show **kubelet version skew** — the kubelet reporting an older Kubernetes version than the kube-apiserver (e.g., kube-apiserver at `1.36.2` while nodes still run kubelet `1.35.3`) — do **NOT** mark the rebase as a revert candidate, even when its rubric score is >= 85.

The kubelet binary is built **from** the `openshift/kubernetes` source. After a rebase merges, there is an expected lag of hours while the kubelet is rebuilt against the new source and delivered via an updated RHCOS image. During this window the skew is **transient build lag**, not a regression:

- Reverting the rebase would only prevent the kubelet from ever picking up the new version — it does not fix anything.
- In the structured output, `failure_type` MUST stay one of the fixed enum values (`install`/`test`/`upgrade`/`infra`) — set it to **`test`**, since kubelet version skew produces real test failures. Do **not** put "transient build lag" in `failure_type`. Record the **"transient build lag"** classification in the free-text `root_cause_summary` (e.g., `"kubelet version skew — transient build lag pending kubelet rebuild"`), and treat it as build lag rather than a revert candidate.
- In the report, record the failure as pending kubelet rebuild: the kubelet must be rebuilt from the rebased source and delivered via an updated RHCOS image. Recommend **monitoring for the rebuilt kubelet (updated RHCOS) to land** so the skew resolves on its own.

### Check if Revert Candidates Were Already Reverted

For each revert candidate:

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state,mergedAt --limit 20
```

Inspect the candidate commits, likely revert commits, and revert diffs. Verify
that a purported revert actually removes the candidate change.

If a revert PR is found:

- **Merged**: Note when it merged relative to the payload. Do not recommend
  reverting again.
- **Open**: Mention the existing revert PR and link to it. Do not create a
  duplicate.
- **Closed (not merged)**: Record it only when relevant to the assessment.

Do not treat the absence of a revert as evidence that the candidate is
innocent.

### Determine Force-Accept Recommendation

Force-accepting is only meaningful for a payload that has **not** already been accepted. **If the snapshot's `phase` is already `Accepted`, `force_accept_recommended` MUST be `false`** — the question is moot, so do not recommend it regardless of the failures present.

Otherwise, recommend force-accepting when **all** of the following are true:

1. All failures are **temporary** infrastructure issues (`failure_type: "infra"`) — see the definition below
2. No more than 2 blocking jobs failed
3. `hours_since_baseline` from `summary.json` is >= 18 (or null)

**What counts as a "temporary infrastructure issue".** The decisive test: *will the failure self-resolve on the next run WITHOUT human action?*

- **Yes → temporary (force-accept eligible):** Boskos/lease acquisition failures, cloud quota exhaustion, transient cloud-provider API errors or throttling, a one-off network timeout to a cloud endpoint, a CI control-plane blip. These clear themselves on retry.
- **No → persistent (NOT force-accept eligible):** stale or expired credentials, a broken or misconfigured CI step/workflow, a bad mirror/registry URL, a persistent misconfiguration, or any product regression. These fail again on the next run until a human intervenes — force-accepting only defers the problem. Do not classify these as a temporary infra pass; score a causal CI-config change as a candidate instead.

**Guard — kubelet version skew from a Kubernetes rebase.** When the blocking failures are caused by kubelet version skew following a Kubernetes rebase (the transient build-lag case described above), recommend **neither force-accept nor force-reject**:

- **Force-accepting is NOT appropriate.** Kubelet version skew produces real test failures, not temporary infrastructure flakes, so it does not satisfy the `failure_type: "infra"` criterion above. Set `force_accept_recommended` to `false`.
- **Force-rejecting is also NOT appropriate.** Rejecting the payload only makes the next payload assemble sooner, which will hit the **same** skew unless the RHCOS carrying the rebuilt kubelet is ready by then — so it accomplishes nothing except churn.

Instead, recommend the correct action: **wait for the RHCOS with the rebuilt kubelet to land**. Once the updated kubelet is delivered, the skew clears and the payload passes on its own.

### Write Payload Results YAML

Use the `ci:payload-results-yaml` skill to create `$OUTPUT_DIR/payload-results-{tag}.yaml`.

This file contains ALL scored candidates across all confidence tiers (HIGH, MEDIUM, LOW), enabling downstream commands to filter by their own criteria. Every candidate must include `revert_eligible` and all five `revert_gates`; candidates below 85 still record the gate status and evidence. If RHCOS RPM suspects were identified, include them in the `rhcos_suspects[]` array (see the `ci:payload-results-yaml` skill for the schema).

**Every affirmatively-identified repository-change root cause must be represented as a scored `candidates[]` entry** — including causal CI-infrastructure / step-registry changes, even when the failure's `failure_type` is `infra`. A failure whose cause is known to be a repository change must not leave `candidates[]` empty; each entry carries its itemized rubric breakdown in its `rationale`.
