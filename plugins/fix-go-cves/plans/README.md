# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

The skill remains unaccepted: real repairs and passing runtime assertions do
not establish reliable final advice. The current factual judge also accepts a
known unsupported explanation. Keep its scores advisory until calibration
works; independent review must inspect the whole reply against the evidence.
The [testing plan](testing.md#next-steps) separates these behavioral questions
from deterministic engine fixes.

Implement the following independently, with a focused regression for each:

1. **Validate report evidence.** `report.sh` takes the table-output path through
   `scan.sh`, bypassing its JSON validator. Hermetic probes return exit 0 for
   empty output, `{}` and multiple JSON documents, while the JSON path rejects
   all three. Request one fresh JSON scan and render the human report from that
   validated result. Preserve scanner failure/sentinel statuses and branch
   cleanup; do not scan twice. Cover valid empty findings, findings and ignores,
   malformed evidence and nonzero scanner outcomes. Assert exit status as well
   as output; existing report fixtures mask it with `|| true`.
2. **Bound shared scanner operations.** Enforce the existing timeout setting
   around local version/scan calls and container database/scan operations.
   A local scanner probe currently succeeds after exceeding its configured
   limit. Reuse existing timeout handling, preserve diagnostics and caller
   limits, and keep build deadlines separate. Specify whether the limit applies
   per operation or to the complete fallback sequence; do not claim a total
   deadline from several independent limits. Cover stalled operations, healthy
   fallback without stale failure flags, and propagation to callers. Verify
   timed-out container work terminates without broad container cleanup.
3. **Preserve inherited ignore policy.** Implement the selected decision below
   with a read-only structural check before `CLEAN_CMD`, build/scan and the
   clean fast path.
   Reuse that check in the YAML audit. The current awk checker misses flow-style
   and quoted-key broad rules and rejects a valid quoted package name. Use a
   real YAML parser; declare and verify PyYAML through existing prerequisites
   rather than treating its absence as an empty policy. Parse failures and
   unsupported structures must block. Cover block/flow styles, quoted keys,
   aliases, malformed input and unavailable parser, plus absent/empty ignore
   lists and valid neighboring rules. Require mappings for entries/packages
   and string identities. On rejection, preserve policy bytes, create no repair
   commit, restore the original ref/HEAD and remove the empty fix branch.
   Keep legitimate complete unscoped-rule merging and introduced-rule repair working. This needs no
   inherited-entry tracking or YAML serialization rewrite.

Resolve the Go-minor policy conflict before changing that behavior. The three
engine fixes do not depend on another paid reporting trial. Existing major-
version, Kubernetes-identity, no-fix-credit, audit and test-evidence guards remain
implemented; keep their regressions rather than reopening them without a new
failure.

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
  exemptions) are currently removed and can be re-ignored as "Regression from
  dependency update". The selected change is to stop with exit 2 before any
  repair, preserving that policy until the maintainer changes `.grype.yaml`.
  An early read-only check avoids introducing entry-provenance machinery.

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
