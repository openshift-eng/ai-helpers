# Fix Go CVEs work plans

Acceptance remains **open**. Engine, harness and evidence changes pass component
integration, and a separate real-engine diagnostic demonstrates repair feasibility.
Seven earlier pilots remain unaccepted; C8 stopped after two actors: 005 accepted
individually, 007 failed. Original artifacts and grades remain intact. The compact
reporting skill has not yet had an actor measurement; its 84-test helper suite
and model-free 005/007/002 smoke pass. The next declared campaign starts with
007 and requires full stock stages and independent review per cell.

| Document | Owns |
| --- | --- |
| [E2E plan](e2e-simplification.md) | Implemented design, remaining acceptance sequence and conditional simplifications |
| [Testing strategy](testing.md) | Durable runtime, behavioral, calibration and evidence-reuse requirements |
| [Implementation results](../evals/implementation-results.md) | Measured outcomes, source groups and grader disagreements |
| [Workqueue investigation](workqueue-race.md) | External race evidence, inconclusive diagnostic patch and preferred cleanup design |
| [Eval README](../evals/README.md) | Setup, commands and case map |
| [Historical live record](../evals/live/README.md#branch-policy-matrix) | Original matrices, grades, costs and coverage limits |

## Deferred work

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
