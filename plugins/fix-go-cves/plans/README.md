# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [E2E and simplification plan](e2e-simplification.md) selects the next work.
The [testing strategy](testing.md) owns durable acceptance and environment rules.

## Next changes

Simplify command selection and the script-to-skill handoff, then measure literal
result relay, supported diagnosis and publication advice. Close declared native
coverage and grader gaps before the final integration cohort. Remove demonstrated
duplication in separate changes, preserving current behavioral requirements.
The [implementation sequence](e2e-simplification.md#work-sequence-and-validation)
defines scope and checks; no revised source or actor cohort has run yet.

The skill remains unaccepted. The [fifth six-cell matrix](../evals/live/README.md#branch-policy-matrix)
retains the measured failures; the [fresh baseline](e2e-simplification.md#open-boundary-and-current-evidence)
records passing script/helper checks and model-free replay preparation.

## Decisions

- **LLM verification removed.** The four deterministic audits gate every
  verification verdict. In the 15 release-0.24 runs (26
  verification iterations) it never changed an outcome: its one independent
  FAIL came after the gate had already blocked the run. The redundant prompts,
  launch/retry/report machinery and their tests are deleted; `review.sh` retains
  AI analysis of flagged outcomes. Evidence-completeness checks, the bounded
  repair loop and independent final rescan remain.
- **Flag, don't delete, pre-existing broad ignores.** Inherited package-only
  entries (including submariner-operator's `/tools` docker and containerd
  exemptions) used to be removed and could be re-ignored as "Regression from
  dependency update". The early read-only check now stops with exit 2 before
  repair, preserving policy until the maintainer changes `.grype.yaml`.

- **Plugin policy or repository notes on Go minor raises.**
  `fix-package.sh` accepts a Go directive raise the build image supports,
  and `SKILL.md` names a team decision only for Go above the build image.
  Submariner release branches carry `.agents/workflows/cve-fix.md`, which
  says to revert such a raise and consult the team for High or Critical
  CVEs. First distinguish obsolete workflow procedure from a binding repository
  compatibility restriction and existing user authorization. Selecting this
  skill supersedes an old manual procedure, not automatically that restriction.
  If applicable, carry the decision through existing configuration/state to
  both proposed-update and post-tidy guards, with rollback/exit 2 for a violation.
  Preserve allowed patch updates and the existing default where unrestricted.
  Do not add a natural-language policy parser or an unconditional global ban.

## Correctness

- **Failure reasons preserved.** Verification carries available exit-2
  diagnostics and existing exit-4 registry reasons into package/module summaries.
  Missing reasons stay neutral; failed scans and builds no longer imply team
  approval.
- **Accurate regression labels.** Label scan-regression ignores by cause;
  findings exposed by an ignore removal are not dependency regressions.
- **OpenShift builder evidence.** Image configuration and Dockerfile tags
  can help diagnose an unavailable builder, but a Go minor or tag cannot
  prove the exact patched compiler required by the existing gates. Keep
  that version unknown without sufficient evidence. Decide how toolchain
  edits should behave for ART builds without weakening the builder bound.
- **Audit completeness is implemented.** Keep the four-audit evidence and bounded
  repair-loop regressions in the [testing strategy](testing.md#runtime-and-behavioral-acceptance).
- **YAML parsing.** Preserve the existing read-only `CSafeLoader` structural check.
  Keep the small `.cve-fix.yaml` configuration grammar separate from Grype YAML.
  Rewriting entry mutation, comment handling or serialization needs its own
  demonstrated failure; it is not a prerequisite for preserving inherited rules.

## Operations

- **Temp space.** Host temporary directories and container storage can fill,
  producing test and build failures. Classify observed ENOSPC consistently in
  builds and test retries; tests currently recognize it only on the first
  attempt. The existing writable-temp probe cannot predict build-space needs.
- **Interactive tests.** Report non-interactive authentication/prompt failures
  with the `test-command` remedy. Avoid a general prompt detector for shell commands.

## Size

- Share the repeated finding-tuple and `normloc` logic in `fix-all.sh` and
  `subagents/scan-regression.sh` without merging their different coverage rules.
- Remove redundant source probes and fixture setup where behavioral coverage
  proves equivalence; see the [bloat audit](e2e-simplification.md#bloat-audit-remove-duplication-preserve-distinctions).
  Split the shell suite only when navigation warrants it.

## Later

- **Workspaces.** Add `go work vendor` or stdlib fixes through `go.work` when
  concrete repository needs justify them. The current review outcomes are
  deliberate limitations, not failed repairs.
- Port these fixes back to Shipyard's `skills/cve-fix`, or point Shipyard at
  this plugin: Dapper `GOEXPERIMENT` forwarding, generated-file drift, the
  test rerun, release-stream retry and reviewer isolation.
