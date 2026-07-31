# Signatures and Causal Chains

## Purpose

Turn the job investigations into minimal failure signatures, verify when each
signature began, and record the causal chain before inspecting candidate
changes.

## Inputs

- accepted `ANALYSIS_RESULT` records;
- comparable executions from the payload chain;
- the artifacts referenced by each investigation.

## Result

Write frozen failure-mode records to `analysis-state.yaml`. Each record contains
a minimal signature, onset or onset interval, ordered causal chain, competing
explanations, and missing links.

## Actions

### Define each failure mode

1. Separate mechanisms that can occur independently.
2. Create the smallest stable signature that distinguishes each mechanism.
3. Include:
   - the earliest discriminating event;
   - the failing operation or reconcile phase;
   - the normalized error class or violated invariant;
   - one additional discriminator only when required.
4. Remove generated names, timestamps, IDs, payload tags, retry numbers,
   cleanup fallout, and unrelated co-failures.

Keep related infrastructure in the signature when it participates in the
causal chain. For example, `DNS throttling -> ignition record missed VM
deadline` is one mechanism. An unrelated registry timeout in the same job is a
different mechanism.

### Find the boundary

For each minimal signature:

1. Walk backward through comparable executions.
2. Classify each execution as:
   - `present`: the same minimal signature occurred;
   - `verified_absent`: the relevant operation completed without the signature;
   - `unobservable`: the operation did not run or evidence is insufficient.
3. Skip unrelated executions.
4. Set the onset to the first `present` execution after the nearest
   `verified_absent` execution.
5. If an `unobservable` gap prevents an exact onset, record an onset interval.

Do not substitute job onset or test-name onset for an unverified signature
boundary.

### Build the causal chain

For each signature:

1. Order the observed events as applicable:
   - trigger;
   - propagation;
   - amplifier or recovery defect;
   - detector;
   - terminal symptom.
2. Support each material link with a failing-run artifact or deterministic code
   flow.
3. Mark speculative or optional links as unresolved.
4. Check that a later recovery error, volume-attach failure, cleanup failure,
   timeout, invariant, or panic has not displaced an earlier trigger.

Internal function calls do not each require a log line when the observed input,
output, and code path make the link necessary.

### Resolve conflicts

When investigators disagree:

- use evidence from the exact failing operation;
- do not treat success in an adjacent phase as exculpatory;
- do not treat absence from truncated or missing logs as evidence;
- do not assume a mechanism executed because it could execute;
- distinguish a detector or improved diagnostic from the underlying cause.

Keep the cause unresolved when the evidence does not discriminate. Record the
competing explanations and missing evidence.

### Record the result

Write each signature, boundary, causal chain, competing explanation, and
missing link to `analysis-state.yaml`. Mark these observations as frozen.
Complete this step only when candidate availability can no longer change the
recorded failure.
