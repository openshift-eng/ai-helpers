# Fix Go CVEs work plans

Acceptance remains **open**. C16 passed live 001, then stopped after publication
002 failed original and independent action/owner review: its unexecuted rerun was
forecast to make the partial PR a full fix. Facts, literal recipe and operations
passed. The skill now gives verification steps without predicting outcomes.
Prospective C17 starts with publication 002; it is not frozen and has no actors.
Unchanged runtime and calibrated judge evidence remains applicable, without C16
actor credit. The [results record](../evals/implementation-results.md) owns counts
and identities; [calibration](../evals/live/calibration.md) owns controls.

| Document | Owns |
| --- | --- |
| [E2E plan](e2e-simplification.md) | Implemented design, remaining acceptance sequence and conditional simplifications |
| [Testing strategy](testing.md) | Durable runtime, behavioral, calibration and evidence-reuse requirements |
| [Implementation results](../evals/implementation-results.md) | Measured outcomes, source groups and grader disagreements |
| [Workqueue investigation](workqueue-race.md) | External race evidence, inconclusive diagnostic patch and preferred cleanup design |
| [Eval README](../evals/README.md) | Setup, commands and case map |
| [Historical live record](../evals/live/README.md#branch-policy-matrix) | Original matrices, grades, costs and coverage limits |

## Deferred work

- **Eval README:** after acceptance, remove duplicate contract/calibration recaps
  using existing canonical links; retain operational instructions and unique failed
  grades, costs and limits. Exact ranges are in the E2E plan.
- **Measured deletions:** remove reviewers/repeated scans only after their gate
  semantics and observed source/binary/policy states are accounted for. Deduplicate
  tuple/location parsing after semantic parity, preserving distinct gate meanings.
- **Workspace features:** add `go work vendor` or stdlib repair through `go.work`
  for a concrete target need. Existing workspace synchronization remains confined
  to owned transaction members.
- **OpenShift/custom compilers:** require actual compiler evidence and repository
  policy; image tags or a Go minor alone do not prove a patched build.
- **Operational classification:** check both test attempts for disk exhaustion;
  distinguish noninteractive authentication failures using the existing test
  command remedy. No generic prompt detector or predictive disk monitor.
- **Shipyard synchronization:** after acceptance, port relevant changes or point
  its CVE workflow at this plugin rather than maintaining divergent copies.

The E2E plan retains the bounded source-coverage question and broader exclusions.
Keep unique historical evidence where recorded; documentation simplification must
preserve failures and all runtime, policy, native and publication requirements.
