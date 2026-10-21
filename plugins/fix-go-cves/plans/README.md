# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

The skill remains unaccepted: real repairs and passing runtime assertions do
not establish reliable final advice. The clarified live factual judge now rejects
the known unsupported explanation in a fixed five-fixture calibration (15 samples,
zero errors). That measures selected distinctions, not general grading reliability;
independent review must still inspect the whole reply against the evidence.
The current-runtime continuation reaches every recorded phase and completes
evaluation, with lint blocking unit tests and PR readiness. Its final advice
still fails; the [live record](../evals/live/README.md#current-runtime-integration)
retains both attempts and the narrow diagnostic/evidence fixes.
The [testing plan](testing.md#next-steps) separates these behavioral questions
from deterministic engine fixes.

Three demonstrated engine gaps are now implemented, with focused regressions:

- **Report evidence:** one fresh JSON scan uses the existing validator before
  rendering findings and ignores. Invalid evidence and failed scans cannot
  declare completion; incomplete coverage retains exit 2 and cleanup.
- **Scanner deadlines:** shared per-operation limits cover executable version
  probes, scans, container database updates, volume creation and image inspection.
  Termination grace and targeted container cleanup are bounded separately.
  Healthy fallback resets prior failure flags; shorter caller deadlines remain
  effective. Installer downloads and generic daemon probes are outside this fix.
- **Inherited ignore policy:** a shared read-only PyYAML `CSafeLoader` check runs before
  `CLEAN_CMD`, build/scan and the clean fast path. It handles flow/quoted forms
  and aliases, rejects malformed or broad selectors, and preserves valid empty
  policies and complete unscoped rules. Rejection preserves policy bytes,
  creates no repair commit, restores the original ref and removes the empty
  branch. PyYAML is an explicit prerequisite; no serialization rewrite or
  entry-provenance machinery was added.

All 3,023 hermetic runtime checks and 64 eval helper checks pass. Two model-free
real checks on frozen runtime `c916dfa9` also pass: Subctl release-0.24 report
mode faithfully renders 17 findings, and operator devel rejects genuine inherited
broad rules before cleanup/build/scan while preserving policy and instructions.
These establish engine behavior, not remediation or skill acceptance. The
[live record](../evals/live/README.md#runtime-quality-checks) retains failures,
environment corrections and the independent reviews.

A fresh-context diagnosis pilot failed its first case and stopped. No production
subagent routing or reviewer loop was added. The full replay pipeline completed
and preserved a failed skill verdict. Next close current-runtime live integration
separately from behavioral acceptance; see the
[current E2E work](../evals/README.md#current-e2e-work). Resolve the Go-minor
policy conflict before changing that behavior. Existing
major-version, Kubernetes-identity, no-fix-credit, audit and test-evidence guards
remain implemented; keep their regressions rather than reopening them without
a new failure.

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
- **Audit completeness is implemented.** Verification requires all four known
  scripts and fresh evidence with complete, unique nonnegative integer counters.
  Missing or malformed evidence blocks repair dispatch, verification and
  publication; valid positive evidence still repairs and rechecks. The existing
  orchestration fixtures exercise missing directories/scripts and malformed
  counters, and the real Admiral audit archive remains compatible.
- **YAML parsing.** Start with the shared read-only structural check above.
  Keep the small `.cve-fix.yaml` configuration grammar separate from Grype YAML.
  Rewriting entry mutation, comment handling or serialization needs its own
  demonstrated failure; it is not a prerequisite for preserving inherited rules.

## Operations

- **Operational handoff.** If needed after the engine fixes, expose effective
  test command, reached phases, observed attempt results and available evidence
  paths through the existing Summary/state. Share in-memory facts with optional
  evidence writing: `run.json` is written after Summary in the exit trap, and
  persisted attempt receipts require `CVE_FIX_EVIDENCE_DIR`. Do not make evidence
  mandatory or claim missing attempts passed. A clearer handoff helps operators;
  it does not establish causality or solve free-form diagnosis reliability.
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
