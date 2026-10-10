# Independent CI reliability proof review

This is the independent review stage of [investigate-ci-reliability](../SKILL.md).
Read the [evidence contract](evidence-contract.md) and the
raw cited files. This review is a separate reasoning context from the investigator;
changing the investigator's name does not make a self-review independent.

## Check the causal claim

For each candidate, establish all of the following before `PROVEN_FIX`:

1. **Actual failure:** metadata and JUnit/step evidence show a blocking failure in an
   affected run. Informing cases, skipped tests, success-on-retry results, and alarming
   log text in green jobs do not establish the job's cause.
2. **Mechanism:** trace the originating error through executed code/configuration.
   Identify the incorrect behavior, not just the visible timeout or missing resource.
   A deterministic reproduction can establish a source defect, but scope any claim
   about the exact production interleaving to the available evidence.
3. **Current applicability:** pin current source or preserve its retrieval provenance
   and hash; verify the proposed repair is not already merged/adopted. Distinguish
   historical failures in old payloads from an unfixed defect.
4. **Correct repair:** explain why the proposed change addresses the demonstrated defect,
   preserves genuine failures, and has meaningful acceptance criteria. Extending a timeout,
   suppressing cleanup errors, or increasing quotas needs a demonstrated rationale.
   Test exclusions also follow the [scope guidance below](#topology-and-platform-test-selection).
5. **Controls and alternatives:** inspect same-job green controls or a justified alternative
   control/reproducer. Challenge shared infrastructure, version/input differences, ordinary
   PR mistakes, cofailures, and previously fixed causes. Missing OS/provider evidence limits
   the conclusion; it is not exculpatory evidence.

## Topology and platform test selection

When a test's requirements conflict with a topology, platform, or common cluster
configuration, establish the actual incompatibility and which current or future
jobs share it. If multiple jobs can be affected and the test setup permits the
condition, prefer a shared exclusion in the owning OpenShift Tests Extension
(OTE) or `openshift-tests` code. Use environment-selection metadata where
available, or a condition in shared test setup before the incompatible workload
starts. Keep the test selected in compatible environments.

Inspect existing selectors and exclusions first. Match against current specs
built through production test registration: changed names or label placement can
silently break an existing exclusion. Locate the extension that owns the test;
Kubernetes extension selection can live in `openshift/kubernetes`, so a shared
repair does not necessarily belong in `openshift/origin` or the OTE library.

Validate affected and compatible environment selections against the actual
registered inventory, checking intended exclusions, retained tests, and existing
platform filters. Old log names or a regex-only check do not establish that the
current registration path applies the selector. Include affected job families,
test-binary adoption, and coverage impact in the handoff; do not turn a genuine
product failure into an environment exclusion.

Use per-job `TEST_SKIPS` when the restriction is genuinely job-specific or a
shared condition cannot be applied safely with the available setup. Explain that
constraint. Label a temporary workaround, identify the preferred shared repair,
and state when the job override should be removed after adoption.

For example, the [review of the SNO job workaround](https://github.com/openshift/release/pull/86780#pullrequestreview-5471999819)
preferred portable test selection. The [DaemonSet selector correction](https://github.com/openshift/kubernetes/pull/2813)
and [broader SingleReplica selector repair and registration checks](https://github.com/openshift/kubernetes/pull/2815)
illustrate inspecting existing topology exclusions and validating them against
registered tests rather than adding another job override. Check current source
and adoption before treating these examples as outstanding repairs.

## Decide the verdict

Choose `UNRESOLVED` when the failure is real but a safe, current corrective change is not
established; `ALREADY_FIXED` when only adoption verification remains; `REJECTED` for a
refuted or out-of-scope reliability claim. Diagnostics improvements must be labeled as such
and cannot masquerade as fixes that restore the job. Record why each alternative was accepted
or rejected. Counts remain exposures unless every causal blocker in a run is addressed.

## Record the review

Write `WORK/reviews/<candidate-id>.json` with your reviewer identity, candidate digest,
verdict, checked evidence IDs, reasoning, strongest counterargument, and narrow repair scope.
Compute the digest using the bundled script:

```bash
python3 ../scripts/reliability.py candidate-digest WORK/candidates/CANDIDATE.json
```

Resolve the script relative to this reference document. Review the exact candidate bytes semantically;
the digest is canonical JSON, so harmless whitespace does not invalidate a review.
A substantive candidate change requires re-review. Do not modify candidates to approve your
own rewrite; return requested changes to the investigator. Run the bundled validator after
writing reviews. It checks evidence integrity and review freshness, not causal truth.
