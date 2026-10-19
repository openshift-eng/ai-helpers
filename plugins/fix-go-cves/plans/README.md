# Improvement ideas

Unimplemented follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

The first three-execution replay baseline failed: contract 3/3, but both factual
criteria together only 1/3. A new Admiral live repair attempt was invalid:
the agent claimed completion prematurely and ran independent scan/test commands;
the engine later exited 128 after rootless Dapper changed checkout ownership.
Canonical unit tests passed, but the final gate and license check were not
reached, and collection failed. Neither result establishes successful remediation.
The [testing plan](testing.md#next-implementation-slices) prioritizes focused
completion, base/result attribution and provenance corrections, then a fresh
frozen replay cohort and real Admiral/Subctl trials. Preserve the failed runs;
checkout preparation alone does not validate the worker.

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

- **Published major upgrades.** `fix-package.sh` detects a major migration
  only after a failed version lookup. A published `+incompatible` major
  upgrade can therefore commit despite the documented policy. Check the
  installed-to-candidate major boundary independently of lookup success.
- **Kubernetes guard identity.** `_k8s_minor_versions` compares a repository-wide
  set of minors. A module can advance while that set stays unchanged because
  sibling modules retain both minors. Compare versions by module and dependency;
  broader `k8s.io` coverage is a separate policy change.
- **False policy boundary after a no-fix ignore.** When verification ignores
  a finding that has no fix, `subagent_fix_scan_regression` still writes the
  package to `needs-review-pkgs` (`scripts/lib.sh`, after the `ignore.sh`
  call), and `fix-all.sh` reports it as "deterministic fix reached a policy
  boundary (team approval needed)", blocking the PR. Lighthouse
  release-0.24 hit this for x/crypto GO-2026-5932. The first change above
  fixes this without clearing another advisory's decision.
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
