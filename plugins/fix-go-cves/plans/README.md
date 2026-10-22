# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [E2E and simplification plan](e2e-simplification.md) tracks implementation and remaining acceptance work.
The [testing strategy](testing.md) owns durable acceptance and environment rules.

## Next changes

The runtime/contract treatment is locally verified. The `8788312f` pilot
campaign stops without expansion: publication attempts denied read-only
`git stash list`, and two-attempt advice still calls an unexplained failure
flaky. Preserve those distinctions and original grades. The current plan audits
minimal cleanliness guidance and the eval's blanket stash boundary before any
new source treatment; it does not add more unchanged actors or warning prose.

The [external test-fixture investigation](workqueue-race.md) is complete and
inconclusive: both original and diagnostic-patched full suites pass separately,
while the real live run failed twice. Review fixture-owned awaited cleanup as a
new source design. Keep the successful-repair contract and official-upstream
prerequisite intact.
The [implementation results](../evals/implementation-results.md) own outcomes and
checks; the [acceptance sequence](e2e-simplification.md#ordered-work-and-execution-budget)
owns bounded next measurements and the official-upstream prerequisite. Pure cleanup
remains separate.

The skill remains unaccepted. Preserve the
[fifth historical matrix](../evals/live/README.md#branch-policy-matrix) and every
new failed source group; never pool them into current-source reliability.

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

- **Repository compatibility restrictions remain binding.** Selecting this
  skill supersedes an old manual procedure, not its compatibility policy.
  `go-minor-guard` now carries applicable restrictions through proposed-update
  and post-tidy guards and reviewer advice; the skill requires an effective
  guard even when inherited settings conflict. Builder support alone cannot
  override that policy. Same-minor patch updates and unrestricted repositories
  retain their existing behavior. Live acceptance still requires observed
  execution of the relevant policy paths.

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
