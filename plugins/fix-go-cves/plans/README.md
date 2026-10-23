# Fix Go CVEs work plans

Acceptance remains **open**. C12 at `52863d9d` passed three replays, then stopped
at live 001: runtime and facts passed, advice failed. The revised skill preserves
no-fix-only ignores and unverified proposed build outcomes; action calibration V5
passes its fixed controls. Fresh actor acceptance remains pending a source freeze.
Earlier campaigns and original grades remain intact. Component evidence applies
only to unchanged bytes. The [results record](../evals/implementation-results.md)
owns counts; the [calibration record](../evals/live/calibration.md) owns controls.

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
