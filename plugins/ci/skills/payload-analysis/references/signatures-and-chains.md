# Signatures and Causal Chains

Normalize the evidence before considering candidate changes.

## Construct minimal signatures

Represent each independent mechanism with the smallest stable signature that
contains:

1. the earliest discriminating event;
2. the failing operation or reconcile phase;
3. the normalized error class or violated invariant;
4. one extra discriminator only when needed.

Exclude generated names, timestamps, IDs, payload tags, retry numbers,
unrelated co-failures, cleanup fallout, and downstream symptoms.

Keep infrastructure in the signature when it participates in the chain. For
example, `DNS throttling -> ignition record missed VM deadline` is one
signature. An unrelated registry timeout from the same job is another.

A product failure plus incidental quota, DNS, or teardown noise contains
multiple signatures. An extra co-occurring signature neither extends nor
resets another signature's streak.

## Find each signature boundary

Job onset and test-name onset are navigation hints. Only causal-signature onset
selects candidate changes.

Walk backward through comparable executions and classify each:

- `present`: the same minimal signature occurred;
- `verified_absent`: the relevant operation completed and the signature did not
  occur;
- `unobservable`: the operation was not reached or evidence is insufficient.

Skip unrelated and unobservable failures. The first `verified_absent`
execution is the boundary. If an unobservable gap prevents an exact onset,
record an onset interval and do not substitute job or test-name onset.

## Validate causal ordering

Build an ordered chain for every signature:

1. trigger;
2. propagation;
3. amplifier or recovery defect;
4. detector;
5. terminal symptom.

Not every role must exist. Support each material link with a failing-run
artifact or deterministic code flow connecting an observed input to an
observed output. Internal calls do not each need a log line when the path is
necessary; speculative or optional branches remain missing links.

Do not reverse the chain because a terminal symptom is easier to find. A later
volume-attach, cleanup, timeout, invariant, or panic cannot displace an earlier
provisioning, networking, quota, storage, or framework trigger.

## Resolve disagreements

When investigators propose contradictory causes for the same signature, use
evidence from the exact failing operation:

- success in an adjacent phase does not clear a candidate;
- absence from truncated or missing logs proves nothing;
- a mechanism that could execute is not proof that it did;
- a detector or improved diagnostic may expose a pre-existing defect without
  causing it.

If the evidence does not discriminate, keep the signature unresolved and
record the competing explanations. A wrong attribution is worse than an
honest unresolved result.

Update `analysis-state.yaml` with final signatures, boundaries, ordered chains,
and unresolved links. These records are now frozen observations. Candidate
availability must not change them.
