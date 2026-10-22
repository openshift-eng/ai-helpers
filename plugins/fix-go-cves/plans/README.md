# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

The skill remains unaccepted after the [fifth six-cell matrix](../evals/live/README.md#branch-policy-matrix)
at `7063ca5e`. The three successful live cells still supply replacement publication
steps; causal advice also remains unsupported. Admiral release replaced the
inherited test command, so its blocked host run does not establish canonical
unit/Dapper coverage. Both Subctl branches have positive native evidence.
No further actor cohort or source treatment is selected; preserve the failures
and useful diagnosis requirements rather than relaxing acceptance.

Report validation, scanner deadlines and inherited-ignore preservation are
implemented and regressed. The read-only policy guard precedes cleanup/build/scan;
its decision below preserves maintainer policy. The existing 3,046 runtime checks
and 68 eval helper checks pass. See the [testing strategy](testing.md) and
[real engine checks](../evals/live/README.md#runtime-quality-checks); engine
validation is separate from invoking-agent acceptance.

The Summary handoff uses observed in-memory commands, phases and attempts without
requiring optional evidence files; missing/skipped results are not passes.
[Current E2E work](../evals/README.md#current-e2e-work) preserves the measured
behavioral failures. Keep branch policy separate from builder capability and
leave the Go-minor decision unresolved. Existing major-version,
Kubernetes-identity, no-fix-credit, audit and test-evidence guards remain
implemented; retain their regressions unless a new failure justifies work.

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
- Split `test/test-lib.sh` (about 10,000 lines) by script only when navigation
  warrants it; this is independent of correctness fixes.

## Later

- **Workspaces.** Add `go work vendor` or stdlib fixes through `go.work` when
  concrete repository needs justify them. The current review outcomes are
  deliberate limitations, not failed repairs.
- Port these fixes back to Shipyard's `skills/cve-fix`, or point Shipyard at
  this plugin: Dapper `GOEXPERIMENT` forwarding, generated-file drift, the
  test rerun, release-stream retry and reviewer isolation.
