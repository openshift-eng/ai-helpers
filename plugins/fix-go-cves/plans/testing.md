# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` has about 2,300 hermetic checks for mutations,
  rollback and gates. Runtime changes need regressions here. `make test` requires
  Go 1.24 or later and fails rather than skips when `CI` is set.
- **Historical replay:** packaged Admiral case 005 runs today's skill over real
  pinned history and recorded scripts/output. Its references and negatives are
  calibrated. Two model trials completed, including a passing trial after a
  focused skill correction. Replay cannot validate today's remediation engine.
- **Live evaluation:** today's plugin, real Grype and canonical repository
  commands ran on Admiral release-0.24. One fully scored trial passed the
  execution/reporting checks for a blocked runtime result: five CVEs fixed,
  zero outstanding, but two failed canonical test attempts and runtime exit 2.
  An earlier trial exposed unauthorized post-run repairs, a rerun and cleanup.

[Eval setup and replay results](../evals/README.md) and the
[live results](../evals/live/README.md) retain the detailed evidence and costs.
The same-builder reporter experiment established that raising only the Go
directive activates the current vet failure. The source defect pre-existed;
that does not establish that the failure was unrelated to the update. It does
not attribute the historical run or replace a full baseline test suite.

## Next implementation slices

Keep changes small enough to review independently. No new live acceptance
campaign has been run for the candidates below.

1. **Make acceptance reflect factual failures and retain scoring inputs.**
   The live configuration currently gives fact judges only `max_error_rate: 0`.
   A completed false verdict therefore need not fail the stock regression step.
   A model-free probe confirmed that the helper and stock command both exit 0
   for three false, error-free outcome samples; adding the stock
   `min_pass_rate: 1.0` makes that command fail. Apply the required fact thresholds
   to both tracks. Preserve the distinction between a measured false verdict
   and an incomplete/error result. Check the exact selected case IDs as well as
   required judges and sample counts; the helper currently checks only cases
   present in the results. Snapshot the configuration, inputs and annotations
   used by each run: current scoring reads annotations from the working tree.
   Deliberate rescoring gets a separate record and preserves the original scores.
2. **Retain reviewable engine evidence outside the scanned checkout.**
   Keep the actual dependency patch or Git bundle, runtime/helper hashes,
   detected build/test commands, phase outcomes and all four audit results when
   reached. Retain initial and authoritative final-gate scan JSON, scanner exit
   status and coverage/degraded-database evidence, plus relevant build/test logs.
   Mark phases not reached on early failure; success requires complete evidence.
   `PRESERVE_REPORTS=1` already preserves companion reports, but their final scan
   precedes the independent final gate; it cannot stand in for that gate's JSON.
   Capture evidence before runtime cleanup. If existing reports cannot carry it,
   add a small opt-in external artifact directory at those phase boundaries,
   preserving default behavior and gate semantics. Do not introduce a general
   event framework. Acceptance: the archived run remains reviewable after its
   temporary checkout is removed, including the exact retained change and why
   the runtime succeeded or stopped.
3. **Close the observed skill and judge gaps.**
   Make the post-run diagnosis/recommendation boundary explicit: no source
   repair, second invocation or cleanup without a further user request. Require
   evidence for causal claims; uncertainty is valid when a comparable baseline
   is unavailable. Extend the existing action/owner criterion, rather than add a
   third judge. Calibrate the actual live and replay prompts with the corrected
   reference and one-fact negatives for the observed wrong tooling explanation
   and unsupported unrelated-failure claim. Supply pinned default-branch
   backport evidence to live judges; the reduced runtime log alone cannot verify
   every commit discovered during diagnosis. Do not require automatic baseline
   testing for every remediation run or feed judges entire raw tool traces.
4. **Add one genuine successful repair case: Admiral devel.**
   Use `https://github.com/submariner-io/admiral.git`, with base and default both
   pinned to `af20d0bf09dade1c6537d6d38f5175f7b8704042`, target/original branch
   `devel` and script argument `devel`. This real upstream revision already has
   the reporter repair and Go 1.26; x/net remains v0.59.0. It avoids an artificial
   preparatory source commit or a required backport. Model-free preparation
   using the existing helper succeeded with a clean checkout at that exact pin;
   no remediation, scan or canonical test was run for this candidate. Add only
   a case selector delegated to the stock harness, rather than another runner.
   Establish the success oracle below before trying the candidate. Diagnose a
   blocked result rather than relax the oracle to obtain a pass.
5. **Then add native binary coverage: Subctl devel.**
   Use `https://github.com/submariner-io/subctl.git`, base/default
   `50243ac421a985eb13a8be7797fc53595be0f34e`, branch/argument `devel`.
   The candidate has Go 1.26 and x/net v0.59.0. Verify its canonical build,
   unit-test and license commands before admission. Its native `make build`
   produces `cmd/bin/subctl-<version>-<os>-<arch>` and a symlink; use that path
   rather than the eight-platform cross-build. Generalize the helper's currently
   Admiral-specific bare-remote paths from the explicit repository URL only
   when adding this case. Check that reserved eval paths do not hide native
   outputs. Require fresh binary identity and final scan coverage as below.
   A stdlib finding blocked by the builder may legitimately produce exit 2;
   this case does not prove stdlib remediation unless that path actually runs.

## Runtime and behavioral acceptance

The existing live contract intentionally accepts runtime exit 0 or 2 with a
completed Summary. It checks execution, retained state and allowed operations;
fact judges check diagnosis and action/owner. A faithful report of an engine
bug can pass these checks. Add scenario-specific runtime assertions alongside
that contract, using actual evidence rather than the agent's final prose.

| Scenario | Required runtime evidence |
| --- | --- |
| Existing blocked Admiral case | Real execution and retained result; actual test blocker and scan outcome, with accurate advice and no follow-up mutation |
| Successful repair | An initial actionable finding, a retained dependency repair, canonical tests and audits passing, valid authoritative final scan with zero actionable findings, runtime exit 0 |
| Native binary | Fresh build from the tested tree, binary hash and `go version -m` metadata, positive catalog/coverage evidence even with zero findings, and rebuild/rescan after applicable changes |

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
Fresh HOME,
local remotes and permission/trace checks are not host isolation. Before an
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
changes. For the proposed replay baseline, run each admitted case in three
independent skill executions: require its deterministic contract in all three
and all factual criteria together in at least two. Inspect each case, not only
pooled rates. Three judge samples on one reply are not three skill executions. This
is an operational regression rule, not statistical confidence, and is not yet
implemented as a campaign command. Preserve every trial, including failures;
an accepted cohort does not turn a failed individual trial into a pass.

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
| 005 | Admiral govet | Improve attribution calibration and retain frozen scoring inputs |
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
