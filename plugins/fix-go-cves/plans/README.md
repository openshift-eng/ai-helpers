# Fix Go CVEs work plans

The skill remains unaccepted. Start with the
[E2E and simplification plan](e2e-simplification.md): it separates runner/oracle
correctness, runtime policy gaps and the invoking skill's actual responsibilities.
Next work separates measurement prerequisites, runtime safety obligations and
optional deletions. The existing cohort can answer a bounded question without
pretending to cover every release obligation. No new prompt campaign is selected.

| Document | Owns |
| --- | --- |
| [E2E plan](e2e-simplification.md) | Design decisions, ordered changes, removals and one bounded acceptance campaign |
| [Testing strategy](testing.md) | Durable runtime, behavioral and evidence requirements |
| [Implementation results](../evals/implementation-results.md) | Measured outcomes, source groups and grader disagreements |
| [Workqueue investigation](workqueue-race.md) | External race evidence, inconclusive diagnostic patch and preferred cleanup design |
| [Eval README](../evals/README.md) | Setup, commands and case map |
| [Historical live record](../evals/live/README.md#branch-policy-matrix) | Original matrices, grades, costs and coverage limits |

## Deferred work

- **Pure tuple/location deduplication:** follow semantic policy-reader parity;
  preserve actionable, ignored, regression and multi-module distinctions.
- **Workspace support:** add `go work vendor` or stdlib repair through `go.work`
  only for a concrete target need. Ordinary tracked workspace synchronization
  already exists and needs its own mutation-containment fix; deferred features
  must not hide a current safety obligation.
- **OpenShift/custom compilers:** require sufficient actual compiler evidence and
  repository policy; image tags or a Go minor alone do not prove a patched build.
- **Operational classification:** check both test attempts for disk exhaustion;
  distinguish noninteractive authentication failures using the existing test
  command remedy. No generic shell-prompt detector or predictive disk monitor.
- **Shipyard synchronization:** after acceptance, port the relevant changes or
  point its CVE workflow at this plugin. Avoid maintaining divergent copies.

Keep historical decisions and unique evidence where already recorded. Removing
duplicate documentation is separate from deleting failed trials or weakening
rollback, compatibility, ignore-policy, native-coverage or publication gates.
