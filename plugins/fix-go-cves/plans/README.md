# Improvement ideas

Follow-ups found while porting and reviewing the plugin.
Fix the correctness issues before expanding supported workflows.

The [testing and evals plan](testing.md) covers how to measure the skill
itself.

## Next changes

Reporting quotes the observed terminal result, then identifies remaining work
through read-only source and patch inspection. The smaller workflow remains
unaccepted. The bounded-report treatment at `487d0759` failed its first replay
pair and a real successful-repair reporting check. It was reverted to avoid retaining
extra format and ownership instructions without demonstrated benefit.

Keep detailed trial histories and original scores in the
[eval results](../evals/README.md#multi-failure-replay). The
[testing plan](testing.md#next-steps) records the unresolved reporting boundary
and genuine competing repository instructions. Current-engine source repair and
parent completion are verified separately from failed publication advice. No
further wording cohort, reviewer layer or automatic native retry is selected.

Bumps across a selected target's known major version now require review per
in-scope module. Registry failures and unsuccessful updates keep their existing
outcomes; local or unknown versions are not treated as major zero.

Successful no-fix ignores now retain ignored credit without adding policy-review
markers; existing decisions stay intact.

The Kubernetes guard now preserves existing tracked-module/dependency identities
after tidy and workspace sync, alongside its original global minor check. The
unchanged-set regression rolls back; patch, disabled and absence controls pass.

Test logging failures now block verification while preserving observed command
results and successfully saved receipts.

Package-fix and ignore commit subjects now fit 50 characters while retaining full
identity in the body and preserving ignore reasons for existing summaries.

Audit completeness and removal of model verification are implemented. All four
audits gate verification and repair dispatch; shared helpers for `review.sh` and
scanner retries remain. Fix report validation and scanner deadlines separately.
Address inherited ignores separately. Keep these independent of the replay pilot:
historical scripts cannot validate today's runtime fixes. Broader Go-minor
policy needs a decision before changing its behavior.

## Decisions

- **LLM verification removed.** The four deterministic audits gate every
  verification verdict. In the 15 release-0.24 runs (26
  verification iterations) it never changed an outcome: its one independent
  FAIL came after the gate had already blocked the run. The redundant prompts,
  launch/retry/report machinery and their tests are deleted; `review.sh` retains
  AI analysis of flagged outcomes. Evidence-completeness checks, the bounded
  repair loop and independent final rescan remain.
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
