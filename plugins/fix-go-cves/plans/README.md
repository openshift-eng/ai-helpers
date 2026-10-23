# Fix Go CVEs work plans

Acceptance remains **open**. C14 at `2a3c1b27` stopped after its first live 001:
runtime and facts passed, but advice inferred likely compilation from Go version.
Its same-build uncertainty caveat was genuine; the forecast remained unsupported.
Original results and dissent remain intact. C15 changes only the final compiler
clause to prerequisites and verification steps without success predictions,
retaining C14 test reporting. It remains prospective, with live 001 first. Existing
component/V5 evidence applies only to unchanged components and identical judge
prompts/inputs. The [results record](../evals/implementation-results.md) owns counts.

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
