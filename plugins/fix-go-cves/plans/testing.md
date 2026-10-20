# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` has about 2,300 hermetic checks for mutations,
  rollback and gates. Runtime changes need regressions here. `make test` requires
  Go 1.24 or later and fails rather than skips when `CI` is set.
- **Historical replay:** packaged Admiral case 005 runs today's skill over real
  pinned history and recorded scripts/output. Its references and negatives are
  calibrated. All three frozen three-execution cohorts failed. The latest
  recorded contract 2/3 and factual conjunction 2/3; manual publication
  compliance was 1/3 because an indented fence bypassed the guard. Replay
  cannot validate today's remediation engine.
- **Live evaluation:** real Grype and canonical commands establish Admiral
  source repair (14 runtime assertions) and Subctl native repair (19), both
  with engine exit 0. Skill execution remains unaccepted: Admiral invented
  publication; Subctl exhausted its parent budget without a completed reply.
  A refreshed blocked Admiral run retained valid exit-2 evidence, but performed
  temporary cherry-pick/cleanup mutations. Its original contract missed these
  writes; action/owner failed unanimously. Separate derived checks correct
  guard gaps without replacing original scores.

[Eval setup and replay results](../evals/README.md) and the
[live results](../evals/live/README.md) retain the detailed evidence and costs.
The same-builder reporter experiment established that raising only the Go
directive activates the current vet failure. The source defect pre-existed;
that does not establish that the failure was unrelated to the update. It does
not attribute the historical run or replace a full baseline test suite.

## Next implementation slices

Keep changes small enough to review independently. Source and native runtime
repair are verified; skill behavior and all replay cohorts remain unaccepted.

1. **Acceptance and frozen scoring inputs are implemented.**
   Both tracks now require each factual judge's pass rate to be 1.0 as well as
   zero errors. A controlled completed-failure probe using the stock regression
   command exits 1; the helper preserves a measured false verdict separately
   from an incomplete/error result. It checks exact selected cases, configured
   judges, sample completeness and majority consistency. Every stock stage uses
   the run's copied configuration, inputs and annotations, with file hashes and
   helper identity recorded. A stock-workspace/scoring probe confirmed that
   later working-tree annotation changes do not alter frozen scoring. Deliberate
   rescoring needs a separate frozen record and must preserve original scores.
2. **Durable engine evidence is verified for the Admiral repair.**
   Keep the actual dependency patch or Git bundle, runtime/helper hashes,
   detected build/test commands, phase outcomes and all four audit results when
   reached. Retain initial and authoritative final-gate scan JSON, scanner exit
   status and coverage/degraded-database evidence, plus relevant build/test logs.
   Mark phases not reached on early failure; success requires complete evidence.
   `PRESERVE_REPORTS=1` already preserves companion reports, but their final scan
   precedes the independent final gate; it cannot stand in for that gate's JSON.
   `CVE_FIX_EVIDENCE_DIR` now captures these artifacts before cleanup without
   changing normal gates. The helper hashes and archives them, the retained
   patch and observed tool/image identities. Tests cover strict scenario checks
   and inspection after the temporary checkout is removed. A real Grype probe
   confirmed a freshly built binary in the same scan's zero-findings catalog,
   with matching file hash. The full shell suite passed 2,320 checks.
   The corrected-worker run passed all 14 runtime assertions with matching
   archived hashes. Scanner provenance and completion-observation corrections
   are implemented. The archive-hash fix passed the fresh native evidence check
   and retained Admiral re-verification. Keep valid runtime evidence separate
   from failed agent behavior
   ([results](../evals/live/README.md)); the original incomplete trial needed
   operator retention and did not establish complete helper capture.
3. **The focused skill and judge corrections are implemented and calibrated.**
   Make the post-run diagnosis/recommendation boundary explicit: no source
   repair, second invocation or cleanup without a further user request. Require
   evidence for causal claims; uncertainty is valid when a comparable baseline
   is unavailable. Extend the existing action/owner criterion, rather than add a
   third judge. The actual live/replay references, causal negatives and replay
   rerun negative passed 21 calls with three agreeing, error-free samples each.
   Failed earlier calibration attempts remain preserved, including an observed
   partial-credit defect corrected by an explicit must-fail criterion. Pinned
   default-branch backport evidence is now available to live judges; the reduced
   runtime log alone cannot verify every commit discovered during diagnosis.
   Do not require automatic baseline testing for every remediation run or feed
   judges entire raw tool traces.
   Three frozen replay cohorts now fail acceptance ([results](../evals/README.md)).
   The compact-report revision at `b8265808` cites the retained fix in every
   reply, but two replies invent publication commands. One is falsely accepted
   by both the fact judge and a column-zero-only fence regex. The guard now
   covers indented fences with a failing-before/passing-after regression.
   Re-verify retained outputs separately, preserving original scores. Reporting
   needs a focused design around literal engine results and separate diagnosis. Expose the
   existing `ORIGINAL_REF` in a human-readable summary, or omit unobserved
   return advice; target branch is not original branch. Recommend maintainers
   land the reviewed repair before a newly requested rerun without constructing
   push recipes. This direction is unimplemented and unproven; do not add
   another prompt-only cohort or expand criteria merely to seek acceptance.
4. **Genuine Admiral devel runtime repair is verified.**
   Use `https://github.com/submariner-io/admiral.git`, with base and default both
   pinned to `af20d0bf09dade1c6537d6d38f5175f7b8704042`, target/original branch
   `devel` and script argument `devel`. This real upstream revision already has
   the reporter repair and Go 1.26; x/net remains v0.59.0. It avoids an artificial
   preparatory source commit or a required backport. The corrected-worker trial
   completes with exit 0 and passes all 14
   repair assertions, including canonical tests, four clean audits and the
   authoritative zero-actionable-findings scan. No license gate is configured.
   The response still invents a publication command, so overall acceptance
   fails despite both fact judges returning three true samples. Preserve that
   judge limitation; the existing deterministic guard catches the failure.
   The earlier ownership/collection failure remains preserved in the
   [live results](../evals/live/README.md); preparation alone did not validate the worker.
5. **Native Subctl runtime coverage is verified; skill completion failed.**
   Use `https://github.com/submariner-io/subctl.git`, base/default
   `50243ac421a985eb13a8be7797fc53595be0f34e`, branch/argument `devel`.
   The candidate has Go 1.26 and x/net v0.59.0. Its canonical build, unit tests
   and license check passed in the actual runtime. Native `make build`
   produces `cmd/bin/subctl-<version>-<os>-<arch>` and a symlink; use that path
   rather than the eight-platform cross-build. Case-003, repository-derived
   paths and stock case selection are implemented. Its supervised native trial
   completed with engine exit 0 after 2,583 seconds. Canonical tests and license
   passed, all four raw audits had zero counters, final actionable findings were
   zero with one no-fix ignore, and native hash/catalog/retained-file identities
   matched. All 19 runtime conditions and 76 evidence hashes verified. The
   parent ended exit 1
   after 2,605 seconds, 183 turns and $10.85163125, without a completed final
   reply. The runner aborted before collection/reporting when execution failed.
   Preserve runtime success and failed skill measurement separately. Ordinary
   30-second waits between reads are now explicit. The runner collects/reports
   failed executions, preserves nonzero status and skips invalid grading.
   Do not retry the native case merely to seek a pass.
   A stdlib finding blocked by the builder may legitimately produce exit 2;
   this case does not prove stdlib remediation unless that path actually runs.
6. **Refreshed blocked Admiral execution remains behaviorally unaccepted.**
   Runtime exit 2 retained `57d380de`, two failed canonical test attempts, four
   zero-issue audits and a healthy final scan with zero actionable findings;
   all 61 evidence hashes matched. Original scoring was contract true, outcome
   3/3 true and action/owner 3/3 false. The parent temporarily cherry-picked
   the backport, then used checkout/reset to restore a clean tree. The original
   trace guard missed these writes. Separate stock collection, re-extraction
   and contract checking with the corrected guard reject all four mutations;
   all 91 original files and scores remain hash-identical. The guard detects
   common direct commands; it is not a shell sandbox. Follow the reporting
   direction in slice 3, retaining trace regressions for read-only compliance.
   No more paid trials are planned this round.

## Runtime and behavioral acceptance

The existing live contract intentionally accepts runtime exit 0 or 2 with a
completed Summary. It checks execution, retained state and allowed operations;
fact judges check diagnosis and action/owner. A faithful report of an engine
bug can pass these checks. Scenario-specific runtime assertions additionally
check actual engine evidence rather than the agent's final prose.

| Scenario | Required runtime evidence |
| --- | --- |
| Existing blocked Admiral case | Real execution and retained result; actual test blocker and scan outcome, with accurate advice and no follow-up mutation |
| Successful repair | An initial actionable finding, a retained dependency repair, canonical tests and audits passing, valid authoritative final scan with zero actionable findings, runtime exit 0 |
| Native binary | Fresh build from the tested tree, binary hash and `go version -m` metadata, positive catalog/coverage evidence even with zero findings, canonical gates after remediation, and rebuild/rescan after applicable changes |

Report measurement completion, behavioral verdicts and runtime scenario coverage
separately. A no-findings fast path can be valid behavior but does not exercise a
repair. A source-only scan, stale or opaque binary does not establish native
binary coverage. Database drift may remove the candidate's actionable finding;
record the missing coverage and choose a suitable new pin deliberately. Do not
fake findings, stub tools, skip canonical gates or add broad ignores to qualify.

The local origin/fork remotes prevent publication. They also mean that even a
successful runtime may correctly emit no GitHub PR command. Keep that limitation
explicit; do not invent fork URLs to force one. Existing hermetic PR rendering
coverage and eventual skill relay coverage are separate from proving repair.
No eval should push changes or create a PR.

## Environment, evidence and deadlines

Use the tested shared harness revision
[`1a980e707909a23f8c143ce333d97f5203db34ab`](https://github.com/opendatahub-io/agent-eval-harness/tree/1a980e707909a23f8c143ce333d97f5203db34ab)
for the next implementation checks; revalidate integration before changing it.
Record actual runtime/helper contents as well as staged wrapper hashes, case
pins, CLI/model/harness settings, scanner path/version/hash or container digest,
Grype database identity/status, and actual builder image/compiler identity.
The observed live scanner was v0.121.0 while the runtime fallback is v0.112.0;
record what executed. Cache reuse does not freeze the database or builder. Keep
identity metadata, not a vendored database or image archive.

Package-bearing runtime tools, caches, logs and evidence must remain outside
the scanned tree; a real Grype probe demonstrated that `.git` does not exclude
them. The source-only staged plugin and driver retain the stock runner layout.
Fresh HOME, local remotes and permission/trace checks are not host isolation. Before an
unattended or broader campaign, use disposable build resources through the
shared harness/worker environment. A container with the host Docker socket
still lets canonical repository cleanup affect host resources. Verify that
Dapper, scanner/database access, network and model credentials work in the
chosen environment; do not implement a plugin-specific sandbox.

Exercise timeout/cancellation and retention of partial evidence in that
disposable environment before unattended runs. Parent time/budget limits do
not account for all nested reviewers and judges. `CVE_FIX_SCAN_TIMEOUT` is not
currently enforced uniformly across scanner and database calls; keep that
runtime fix in the existing [operations plan](README.md#operations), rather
than claim the configured value bounds every scan. Record environment failures,
operator stops, elapsed time and available costs separately from model behavior;
observed violations remain evidence even when a trial is stopped.

## Acceptance rounds and expansion

Freeze case membership, criteria and configuration before comparing skill
changes. The first case-005 baseline at source `5079407` completed with contract
3/3 and factual conjunction 1/3: it failed. Its reports are preserved under
`.work/fix-go-cves-next-slice/replay-baseline-20261019/`.
The `9ba32eda` follow-up also failed (contract 2/3, factual conjunction 3/3 by
majority), preserved in `replay-followup-20261019/` beside that directory.
The compact-report cohort at `b8265808` failed too: recorded contract 2/3,
factual conjunction 2/3, but manual publication compliance 1/3. Its reports and
guard probe remain in `replay-report-20261019/`; no failed trial was replaced.
No fourth cohort is planned merely to seek acceptance.

The unchanged operational rule requires each case's deterministic contract in
all three independent skill executions and all factual criteria together in at
least two. Inspect each case, not pooled rates. Three judge samples on one reply
are not three skill executions. This is not statistical confidence or a new
campaign command. Preserve every trial and original score; corrected guard
re-verification needs a separate provenance record and no paid skill rerun.

Do not mechanically run three expensive live trials against changing external
state. Establish actual successful-repair and binary evidence after the relevant
changes; rerun to resolve an identified failure or environment change. Recalibrate
judges when their prompts, models or fixtures change. Missing cases, samples or
verdicts are errors, never passing evidence. Avoid an automatic extra-six-run
rule for borderline scores or repeated attempts merely to obtain a pass.

Live failures feed the faster layers: engine bugs get hermetic regressions and
interpretation errors get replay cases. Existing no-fix marker, major-version
and Kubernetes-identity fixes remain independent work in the
[main plan](README.md#next-changes). Validate each with the shell suite and a real
case when it exercises the changed path. Harden audit completeness before
removing model verification; that removal does not need its own eval framework.

## Historical follow-ups

Six source recordings remain under `.work/fix-go-cves-evals/source/`; only 005
is packaged. Admit another only when it adds a concrete decision or regression.

| Case | Recording | Admission work |
| --- | --- | --- |
| 001 | Lighthouse license | Correct cdc3003 backport advice to repair the remote target before rerunning |
| 002 | Submariner partial | Preserve PR relay and the owner of the builder-image decision |
| 003 | Cloud-prepare clean | Check that flagged lines need no action; heavier live success alternative |
| 004 | Subctl `bin/lichen` | Correct the reference and resolve the empty binary contradicting the log |
| 005 | Admiral govet | Packaged and calibrated; preserve the failed baseline and compare the focused skill revision |
| 006 | Lighthouse x/crypto | Correct no-fix and license-backport advice |

Case 004 must cover all three blocked bumps: x/net, grpc and otel/sdk. Case 006
has no remaining x/crypto finding after the no-fix ignore of GO-2026-5932;
inventing further x/crypto action, a Go raise or a team decision must fail. Its
license failure also needs 001's remote-target backport advice. Keep Go-raise
policy scoring neutral until the conflicting repository/plugin policy is
resolved ([decisions](README.md#decisions)).

Package needed logs, references, negatives, inputs, annotations, bundle commits
and historical scripts. Sanitize home paths and omit raw recording transcripts
with unrelated connector or memory metadata. Add binary/report evidence only
when the case requires it. These recordings helped tune the skill and measure
regression, not generalization. Defer fleet coverage, scheduled canaries, CI
campaign automation and direct reviewer evals until a concrete gap warrants them.
