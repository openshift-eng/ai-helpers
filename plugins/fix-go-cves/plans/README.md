# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

Reporting now quotes observed terminal results before qualified, read-only
diagnosis. Existing original-ref evidence supports return advice, and publication
relay requires the complete witnessed block. The selected case-005 replay
comparison passes its contract and factual criteria in all three executions;
earlier failures and the incomplete SDK-event trial remain preserved
([results](../evals/README.md#current-reporting-implementation)). Manual wording
caveats prompted a small prerequisite-to-verification clarification after that
comparison; it is not retroactively tested by the earlier outputs.

The current-engine blocked check verified reporter/evidence-capture integration
and read-only behavior, but failed action/owner grading on unsupported causality
for a first-only syncer failure. A small clarification now covers each distinct
failure and what a passing retry establishes; it is source-reviewed, unmeasured.
Source/native engine repair remains established by earlier trials; their failed
invoking-agent measurements are not replaced. The
[testing plan](testing.md#reporting-and-e2e-status) distinguishes these claims.

Next, review and calibrate one replay of the preserved multi-failure live result.
Its model-free candidate uses the existing machinery; it adds the intermittent
failure missing from case 005 without another live run. The
[prepared experiment](testing.md#next-prepared-experiment) defines admission,
calibration and bounded measurement; no new case is admitted or model-tested yet.

Land each runtime fix with a regression that fails on the current code and
passes afterward, using the existing fixtures and full shell suite.

1. **Successful no-fix ignores.** In `subagent_fix_scan_regression`, remove only
   the successful-ignore write to `needs-review-pkgs`; retain `ignored-pkgs`
   and every existing policy marker. Compare marker state before and after
   the existing binary retry fixture, which may already contain another marker.
   Fresh mixed-advisory and sibling-module cases must retain real policy
   decisions; failed or ineffective ignores must remain actionable in the
   production scan-regression companion. No outcome-schema change is needed.
2. **Published major upgrades.** Guard the selected candidate against each
   in-scope module's effective installed version, including transitive targets.
   Test scoped updates, permitted same-major updates, and unchanged HEAD and
   metadata on rejection. Keep absent/local-replacement handling and the
   missing-registry exit separate; do not treat an unknown version as major zero.
   This fixes the target-package bypass, not every incidental graph change.
3. **Kubernetes guard identity.** Keep the existing `api`, `apimachinery` and
   `client-go` scope. Compare by tracked module and dependency after tidy and
   workspace sync, including siblings a scoped update changed. The unchanged-set
   reproduction must roll back; patch updates and guard-disabled runs must work.

Then fix report validation and scanner deadlines in separate changes. Harden
audit completeness before removing model verification; retain shared helpers
used by `review.sh` and scanner retries. Address failure reasons and inherited
ignores separately. Keep these independent of the replay pilot:
historical scripts cannot validate today's runtime fixes. Broader Go-minor
policy needs a decision before changing its behavior.

## Decisions

- **Drop the LLM verification layer.** Deterministic companion evidence
  already gates every verdict. In the 15 release-0.24 runs (26
  verification iterations) it never changed an outcome: its one independent
  FAIL came after the gate had already blocked the run. Removing it saves
  about 550 script and 500 test lines; `review.sh` keeps the useful judgment.
  Preserve the deterministic audits, evidence-completeness checks, bounded
  repair loop and independent final rescan.
- **Flag, don't delete, pre-existing broad ignores.** Package-only entries on
  the base branch (submariner-operator's `/tools` docker and containerd
  exemptions) are removed, and scan-regression then re-ignores the findings
  as "Regression from dependency update". Flagging keeps maintainer policy
  but leaves such repositories NOT READY until `.grype.yaml` changes.

- **Plugin policy or repository notes on Go minor raises.**
  `fix-package.sh` accepts a Go directive raise the build image supports,
  and `SKILL.md` names a team decision only for Go above the build image.
  Submariner release branches carry `.agents/workflows/cve-fix.md`, which
  says to revert such a raise and consult the team for High or Critical
  CVEs. Resolve how repository restrictions gate retained changes before
  committing; a reviewer explanation after the run cannot enforce them.

## Correctness

- **Preserve failure reasons.** `_fix_fv_package` classifies every exit 2
  as a policy boundary, including failed scans and builds; the review prompt
  also makes every `UNRESOLVED` reason end in "(need team input)". Preserve
  the actual cause through verification and reporting. Subctl's leftover
  `bin/lichen` blocked scans; it did not establish that the bumps needed
  approval. Distinguish a rerun remedy from a compatibility or policy decision.
- **Accurate regression labels.** Label scan-regression ignores by cause;
  findings exposed by an ignore removal are not dependency regressions.
- **OpenShift builder evidence.** Image configuration and Dockerfile tags
  can help diagnose an unavailable builder, but a Go minor or tag cannot
  prove the exact patched compiler required by the existing gates. Keep
  that version unknown without sufficient evidence. Decide how toolchain
  edits should behave for ART builds without weakening the builder bound.
- **Audit completeness.** A missing audit directory currently skips verification,
  and the expected evidence set is inferred from scripts still present. Require
  all four known audits and their complete, nonnegative integer counters.
  `NEW_ISSUES=banana` and a scan counter missing `UNRESOLVED` can currently pass.
  Missing, empty, crashed, skipped or malformed evidence must not verify a fix.
- **YAML parsing.** Replace the awk heuristics that find ignore entries with
  one parser using PyYAML node marks for entry boundaries. Preserve surrounding
  comments and untouched text explicitly; node marks do not retain comments.
  Declare PyYAML as a prerequisite if this makes its current optional use required.

## Operations

- **Scanner deadlines.** Enforce `CVE_FIX_SCAN_TIMEOUT` at the shared scanner
  boundary, including database updates. Several callers currently leave scans
  unbounded. Keep build deadlines separate and preserve timeout diagnostics.
- **Report completeness.** `report.sh` accepts empty scanner output with exit 0.
  Use the same validated JSON evidence as remediation before declaring a report
  complete; render the human output from that evidence.
- **Temp space.** Dapper builds use the host `/tmp`; a nearly full tmpfs
  quota surfaced as test and build failures. Classify observed ENOSPC consistently
  in builds and test retries; tests currently recognize it only on the first
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
