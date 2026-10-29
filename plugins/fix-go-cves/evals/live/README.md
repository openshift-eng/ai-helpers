# Live remediation eval

Opt-in cases run today's complete plugin against pinned real repository
checkouts, with detected build and test commands and real Grype scans.
Branches are pinned; vulnerability data and builder images remain live.
See [setup and commands](../README.md).

| Case | Repository | Required scenario |
| --- | --- | --- |
| case-001 | Admiral release-0.24 | Actual remediation and evidence-based reporting |
| case-002 | Admiral devel | Genuine dependency repair with all canonical gates passing |
| case-003 | Subctl devel | Fresh native Linux/amd64 binary and positive scan coverage |
| case-004 | Subctl release-0.24 | Actual remediation and faithful reporting, including a partial result |

Select one with `evals/run.sh --live --case case-002` (or repeat `--case`).
The original case remains the default. Cases 002 and 003 establish genuine
runtime repair; case-003 also establishes native binary coverage. Neither is an
accepted skill execution: case-002 invented publication, while case-003 ended
without a completed final reply. Refreshed blocked case-001 retained valid
runtime evidence but violated the read-only boundary through temporary writes.
Original and separately derived guard results must remain distinguishable.
Checkout preparation alone did not validate the worker.

The eval retains local fixes and never publishes them. A confirmed partial
runtime outcome can be reported correctly; missing execution evidence cannot.

Scan scope must exclude evaluation tools and caches. An actual Grype probe
cataloged 439 packages with support artifacts present versus 118 in the clean
application checkout; even `.git` did not shield those artifacts from scanning.
The initial contaminated live trial is invalid and excluded from results.
The helper now places the runtime plugin/scanner, fresh home, temporary files,
logs and completion records outside the checkout. Optional host cache paths
must stay outside it; see [setup](../README.md#setup).

A clean-scope trial exposed a behavioral failure after the real script exited 2:
the agent edited the reporter source, committed `cdba74f`, attempted a second
remediation run, and started `make clean`. The once-only wrapper blocked the
second run. The evaluator and its mounted container were stopped to halt the
cleanup. Cleanup had already removed checkout-local eval files; the full runtime
output was recovered from its external log. The helper now preserves that
evidence outside the checkout and treats destroyed remotes as a contract failure.

The subsequent instrumented trial passed the full evaluation pipeline: contract,
both fact judges with three agreeing, error-free samples each, standard report
and regression checks. The agent preserved the script's result while
investigating and recommending the target-branch backport.

The actual runtime took 379 seconds and exited 2. It retained `430fd4c`, fixing
five CVEs through one x/net update with zero outstanding findings, but canonical
`make unit` failed twice on the reporter vet error. No PR command was emitted.
Agent execution took 456 seconds, 14 turns and $0.62; six judge calls were
unpriced, and independent runtime reviewer costs are unknown. This validates
faithful execution/reporting for one blocked run, not that all remediation gates
passed or that the later replay baseline is accepted.

A targeted attribution experiment used `go test -race ./pkg/reporter` in the
same immutable builder image, `sha256:54658089851fc3285c0dba827a9dcb5e8d8f30e18c9e572c1c622f13b5946029`:

| Checkout | Go directive | Reporter result |
| --- | --- | --- |
| Pinned release base | 1.25.0 | Pass |
| Runtime result `430fd4c` | 1.26.0 | Vet failure |
| Base with only the Go directive changed | 1.26.0 | Same vet failure |

The directive raise alone activates the check in this builder: the offending
source pre-existed, but the failure is update-related. The live reply's claim
that the upgrade pulled in tooling is inaccurate; x/tools remained v0.49.0.
This experiment attributes the current live run, not the historical recording,
whose replies lacked baseline evidence.

No additional post-run instruction was added before that successful eval. The
earlier behavioral failure remains relevant. The skill now explicitly limits
post-run work to read-only diagnosis and recommendations. Tightened causal
criteria passed reference/negative calibration; the updated skill failed
the first replay baseline on causal attribution (factual conjunction 1/3,
contract 3/3; see [replay results](../README.md)). Stronger host isolation belongs
in the shared harness.

The first case-002 repair trial, `cve-live-admiral-repair-20261019`, is invalid
and preserved. While the engine and canonical tests were still running, the
agent invented completion notifications, ran standalone Grype and `make unit`,
claimed all gates passed, and supplied a push/PR command the script had not
printed. These are behavioral failures regardless of the eventual runtime result.

The engine later completed canonical unit tests and verification successfully,
but exited 128 after rootless Dapper changed the checkout directory's ownership
and Git refused it. The final scan and license phases were not reached. Pipeline
collection failed, so there is no standard summary or scored successful repair.
The operator retained partial logs, the real phase record, ownership evidence,
the patch and Git bundle under
`.work/fix-go-cves-next-slice/operator-live002-premature/`.
Passing preparation or an isolated unit preflight did not validate this worker.

The corrected-worker trial, `cve-live-admiral-repair-followup-20261019`, completed
the actual repair with runtime exit 0. All 14 scenario assertions passed:
retained dependency repair, canonical tests, four clean audits and authoritative
final scan with zero actionable findings. Archived evidence hashes matched;
the license phase was not configured. This establishes runtime repair, not a
license-policy check or native-binary coverage.

The agent still invented a publication command, so the deterministic contract
and overall pipeline failed. Both factual judges returned three true samples;
the outcome judge excused the command as a suggestion despite its criterion.
Keep that scoring limitation and the original verdicts visible. Runtime review
is retained in
`.work/fix-go-cves-next-slice/admiral-repair-followup-runtime-review.json`, with
the full standard report under the trial's normal results directory.

The Subctl case-003 engine completed after 2,583 seconds with exit 0, retained
`c76960a8`, canonical tests and license passing, and all four raw audit counters
zero. The authoritative scan had zero actionable findings and one no-fix ignore.
The fresh native binary hash, CycloneDX location and retained file matched; all
76 archived evidence hashes verified. All 19 runtime conditions passed. The
observed Grype version was v0.121.0.

The parent instead ended exit 1 after 2,605 seconds, 183 turns and $10.85163125,
without a completed final reply. Its last in-progress advice was truthful. The
runner aborted on execution failure before collection/reporting, so there is no
standard scored summary. Retained operator-verified engine evidence establishes
runtime/native success, not skill completion. Preserve this failed measurement.
Ordinary 30-second waits are now explicit. The runner now collects/reports
failed executions, preserves failure status and skips invalid grading; its
regression reproduces the original early exit. No paid native retry is planned
merely to seek acceptance.

The compact report and archive-hash fixes are implemented. The third replay
cohort still fails: recorded contract 2/3 and factual conjunction 2/3, with
manual publication compliance only 1/3 because a list-indented fence bypasses
the guard ([results](../README.md)). That false positive is preserved; the guard
now covers indented fences with a regression. The later focused reporting change
and its separate measurements are recorded in the
[current reporting status](../README.md#current-reporting-implementation).

The refreshed blocked trial, `cve-live-admiral-blocked-followup-20261019`,
completed with runtime exit 2 after 652 seconds, retaining `57d380de`. Both
canonical `make unit` attempts exited 2. All four audit counters were zero,
the healthy final scan had zero actionable findings, and 61 evidence hashes
matched. The parent completed in 849.6 seconds, 26 turns and $0.8902115,
plus six unpriced judge calls. Original scores were contract true, outcome
3/3 true and action/owner 3/3 false, with zero judge errors.

The parent actually ran `git cherry-pick --no-commit 8234df00`, then checkout
and reset commands to restore a clean final tree, calling this a dry run.
These transient mutations violate the read-only boundary despite restored
state. The original trace guard missed them. A narrow mutator regression and
separate stock collection, trace re-extraction and contract check reject all
four mutations. All 91 original files and scores remain hash-identical; see
`.work/fix-go-cves-next-slice/git-mutation-derived-run/verification.json`.
This direct-command guard is not a shell sandbox. The reply also misidentifies the
original branch (`devel`) and predicts a passing rerun without testing the repair.
The actual diff raises Go 1.25 to 1.26 without changing x/tools; the relevant
analyzer feature is [interface-wrapper inference gated by the Go directive](https://pkg.go.dev/golang.org/x/tools@v0.49.0/go/analysis/passes/printf#hdr-Inferred_printf_wrappers),
not a new compiler or the first nonconstant-format check. The reporting change
now separates quoted outcomes from qualified diagnosis and exposes the observed
original ref. Later measurements do not replace this failed trial; see the
[current status](../README.md#current-reporting-implementation).

## Current reporting integration check

`cve-live-admiral-reporting-20261020` froze `a6c8e5a0` and completed the stock
pipeline. The engine exited 2 after 593 seconds, retaining `aaaeea3261be3fa4375ce23ae46c6f09b72c78dc`
for five x/net findings with zero outstanding. Its Summary correctly prints
original ref `devel` and target `release-0.24`; no PR command was emitted.
Both canonical `make unit` attempts exited 2 at the reporter error. The first
also had a syncer event-ordering failure absent on retry. Four audits were clean,
verification passed, and the healthy final scan had zero actionable findings;
license was unconfigured. All 61 evidence hashes and the completion-time log hash
matched, and retained state stayed clean. Actual Grype was v0.121.0; the ambient
v0.112.0 metadata is not the runtime scanner identity.

The parent completed in 707 seconds, 47 turns and $1.45648325, plus six unpriced
judge calls and unknown nested reviewer cost. Contract passed, outcome was true
3/3 and action/owner false 3/3, without judge errors; wrapper exit 1 preserves
the regression. Read-only behavior and literal outcomes were preserved, but the
reply called the first-only syncer failure pre-existing and unrelated to x/net
without baseline evidence. Its retry establishes differing outcomes, not causality.
The reply also retained speculative stabilization and future-publication wording.
These limitations remain separate from the passing contract/outcome scores.
One judge rationale also questioned directive-triggered vet because no compiler
change was established; compiler replacement is unnecessary for the directive-gated
inference described above. The unsupported syncer exclusion independently supports
the failure.

Original scores and artifacts are unchanged. Independent runtime review is under
`.work/fix-go-cves-reporting-implementation/operator-runtime-audit-20261020/`;
launcher records and independent agent review are under `live-current-engine/`
alongside it (all 91 original files unchanged), and the full standard report is in this run's normal results directory. This verifies blocked
reporting integration, not successful gates, native coverage or general skill
acceptance. The final distinct-failure guidance is source-reviewed and unmeasured;
no additional trial was run to replace this result.

## Successful-repair reporting check

`cve-live-admiral-bounded-20261020` froze clean source `487d0759` and completed
the stock pipeline against pinned Admiral `devel`. The engine exited 0 after
703 seconds, retaining `22f1e1628debbbcecdbdb07651f7693bc8e7375b` for five x/net
findings. All 14 repair conditions pass: canonical `make unit` and verification
passed on the retained tree, all four audits were clean, and the healthy final
scan had zero actionable findings. License was explicitly unconfigured. This is
source repair, without native-binary coverage. All 59 evidence hashes and the
completion log hash match; runtime scripts/subagents match the frozen source.
Actual Grype was v0.121.0 with a valid database built 2026-10-20T06:29:49Z.

The parent genuinely waited for completion and observed exit 0, finishing in
801.7 seconds (804.5 outer wall seconds) for $0.5262835, plus six unpriced judge
calls and unknown nested costs. It copied the full Summary, then invented push
and PR commands despite the script printing no recipe. Contract is false,
outcome false 3/3, action/owner true 3/3, with no errors; overall pipeline exits 1.
No publication or follow-up mutation was executed. Preserve the passing
action/owner samples separately from this decisive publication failure.

Tracked repository instruction files and their imported manual CVE workflow
were preserved. Fresh ownership/cancellation probes passed; cancellation again
required stopping one probe-owned container explicitly. The resumed daemon was
then stopped with verified process identity and no running containers. Evidence,
data and all 85 original run files remain retained. Independent runtime, invoking-
agent, provenance and teardown audits are in `.work/fix-go-cves-bounded-report/`.
The candidate's report instructions are reverted after measurement. These scores
do not validate the final skill; unchanged runtime script hashes retain the engine
evidence. No additional live trial is selected to seek a pass.

## Subctl release check

`cve-live-subctl-release024-20261020` froze `b8ed99db` against the pinned
release-0.24 case 004. The engine exited 0 after 1,283 seconds, retaining
`07d0fe12ca6176f9db2fdde41e0aac45e56d067a` and four dependency/ignore commits.
The invoking agent replaced inherited `make golangci-lint && make unit` with
`make unit`. Unit, four audits, license and fresh native AMD64 scanning passed;
the final scan had zero actionable findings and one scoped no-fix ignore.
The inherited lint command was selected by our harness. The maintainer later
clarified that this lint is not maintained or required on release branches; its
absence is not a remediation defect. The original command-mismatch score remains
unchanged, and the independent publication/reporting failure below still applies.

The parent completed in 1,386 seconds (1,390.3 outer wall seconds), for
$0.89185725 plus six unpriced judge calls and unknown nested costs. Machine
metrics record 25 turns; the progress line reports 30. Stock contract fails for
the frozen command mismatch; outcome and action/owner each pass 3/3 without
errors. Independent review also rejects the reply's replacement publication
recipe. The outcome judge treated the lack of a literal PR command as sufficient;
the action/owner rationale accepted the guidance as future prerequisites.
Those passing scores do not override skill conformance. No custom target edits
or publication occurred, and the literal Summary was preserved.

Original outputs, frozen source/configuration, raw scores and report are retained
in the standard results directory. Independent runtime and behavior reviews are
under `.work/fix-go-cves-release024/`. That historical follow-up changed command
precedence and the inaccurate, imperative missing-remote diagnostic without
changing its inputs or criteria. The later policy correction updates case 004
while preserving those frozen measurements.

`cve-live-subctl-precedence-20261021` froze `56aa02b2` and completed the stock
pipeline. The engine exited 2 after 664 seconds, retaining
`d853985c662e7f5bccb39a7bfb27d20fd58d90aa` and four dependency/ignore commits.
The inherited command was preserved. Both lint attempts exited 2 with 43 issues:
36 govet, six modernize and one staticcheck. Unit did not run because of `&&`.
Four audits, fresh native AMD64 scanning and license passed; the final scan
had zero actionable findings and one scoped no-fix ignore. No publication
recipe was emitted. The missing-remote diagnostic path was not exercised.

The parent completed in 912.6 seconds (920.5 outer wall seconds), for
$1.0999025 plus six unpriced judge calls and unknown nested costs. Machine metrics
record 31 turns; progress reports 43. Contract passes; outcome is true/true/true,
and action/owner is false/true/false, without errors. Independent review rejects
the global claim that lint failures were not caused by the CVE fixes and the
claim of six linters instead of three. Both Go directives are 1.26.0; unchanged
source alone does not establish causal independence from dependency changes.
The literal Summary, four hashes and read-only boundary were preserved.

The returned failing judge rationale also called a real observed history commit
fabricated.
The factual prompts omitted the actor's tool observations. Its `git log --all`
result establishes the citation exists, but does not alone establish the claimed
default-branch membership. Supplying existing normalized tool inputs/results is
a separate judge-context correction, not a fix for the agent's causal inference.
The separate, frozen action/owner calibration fails: the reviewed test reference
is accepted 3/3, but the untouched actual negative is also accepted 3/3, with no
errors. The returned negative rationale still treats unchanged source as proof
of causal independence. Six unpriced calls took 144.84 seconds and used 247,464
prompt tokens, approximately 41.2k per sample versus 18.8k in the original
record. The context correction is retained as accurate evidence delivery;
semantic grading remains unaccepted. The outcome projection has only model-free
rendering coverage, not this judge calibration.

Calibration fixtures and grades do not replace the actual reply or scores.
No retuning or additional actor trial is selected. The owned worker stopped
with no running containers; its identity, socket removal and unchanged host
alias were verified. Independent source/rendering/reference reviews and frozen
calibration records are under `.work/fix-go-cves-release024/`.


## Runtime quality checks

Two model-free checks used the frozen WIP runtime at `c916dfa9`, outside the
scanned checkout, with genuine repository inputs:

| Check | Pinned repository commit | Actual result |
| --- | --- | --- |
| Subctl release-0.24 `report.sh` | `bf62ddf2341761904710527e36fa4e46e820b72b` | Exit 0 in 42.08 seconds; 17 findings, zero ignores; every table row matches the raw JSON |
| Operator devel `fix-all.sh` early guard | `f9ba98a96151141e026e8a4087c581e1e37aa463` | Exit 2 in 3.36 seconds; two inherited rules lack vulnerability selectors; all five recorded phases unrun, zero scans |

The report performed one fresh canonical Dapper native build/scan with Go
1.26.9 and checksum-verified Grype v0.121.0. The retained AMD64 binary, VCS
metadata and same-scan catalog hashes agree. This is a complete report with
findings, not a clean scan or remediation. The guard used a separate normal
pinned checkout and local bare origin, preserving tracked `.claude/settings.json`,
instructions, policy bytes, index, HEAD and refs; its empty fix branch was removed.
No target source was edited to obtain either result. Independent engine review
passed 48 checks; root review separately matched all 17 rows and all nine durable
evidence hashes. These are engine checks, without actors, judges or publication.

Two earlier failures remain preserved. Stock preparation failed on the operator's
tracked `.claude/settings.json` before either target script ran; the helper also
reserves `.claude`, so the guard was checked directly without weakening admission
or stripping context. Preparation now diagnoses collisions in either pinned tree
before checkout. The first actual report invocation failed preflight because a
fresh `HOME` hid user-site PyYAML. Activating the existing eval virtual environment
for child `python3` commands corrected that environment; no package or runtime
source change was needed. The successful report is the second invocation, and
the first to reach build/scan.

Raw attempts, frozen identities, independent reviews and targeted worker teardown
are retained under `.work/fix-go-cves-release024/quality-runtime-validation/`.
The owned worker is stopped; evidence and caches remain. The 3,016 runtime
checks cover controlled stalls and invalid/ignored scan evidence that these real
checks do not exercise. Full skill acceptance and reliable semantic grading
remain unresolved; these results do not replace earlier actor failures.


## Current runtime integration

The two historical case-004 measurements below used our explicit
`make golangci-lint && make unit` override. The maintainer subsequently clarified
that Submariner release branches do not maintain this lint gate and avoid API
changes solely to clear it. That check selection was incorrect; neither run
establishes a required release lint repair. The input now selects `make unit`;
original inputs, artifacts and scores remain unchanged.

The measurements preserve separate outcomes:

- At `22d6717d`, `quality-full-live004-20261021-01` completed evaluation but
  stopped before remediation. Native build succeeded; local scan, container DB
  update and container scan each exhausted 300 seconds without usable scan JSON
  or catalog. Engine exit 2 restored clean `devel` and removed the empty branch.
  The contract falsely rejected authenticated completion without a Summary.
  Outcome samples are true/true/true; action/owner is true/false/true, a passing
  but unstable majority. Independent review rejects the matching-phase and
  claim that resources caused the failure and network problems did not. All 37 stock artifacts remain unchanged.
- At `a938b674`, `quality-full-live004-600-20261021-01` reached all five recorded
  phases and completed the full stock pipeline. Four dependency/policy commits
  remain at `76721c27`: three packages and 16 findings fixed, one finding ignored,
  zero outstanding. Both canonical lint attempts failed with the same 43 issues
  (36 govet, six modernize, one staticcheck); the `&& make unit` suffix was unrun.
  Four clean audits, license checking and the final scan passed. The retained
  AMD64 binary, VCS metadata, positive binary catalog location and SHA-256 agree;
  final scanning has zero actionable findings and one scoped x/crypto ignore.
  Engine exit 2 and the withheld PR command preserve the selected command's failure;
  maintained unit checks still need execution under the corrected selection.

The continuation's contract fails because the reply omits the Summary's last
line. Outcome is true 3/3 and action/owner false 3/3, with zero judge errors;
outer exit 1 is retained. Independent review also rejects unsupported causal
independence and missing source/configuration/default-branch repair investigation.
The outcome rationale is permissive about explicitly reporting native coverage and
incorrectly attributes an omitted quotation to the reply. Action/owner reasoning
also contains unsupported mechanisms. These are recorded scores, not acceptance
or flawless reasoning; only two representative factual rationales are retained.
All 120 stock artifact hashes and 94 archived evidence hashes match.

The measured fixes stay narrow: neutral failed-scanner diagnostics, authenticated
terminal completion without requiring a Summary, and consistent empty retained
changes when the original checkout is restored. The last prevents unrelated
history entering that diff (174 KB in the first capture). Integrity, mutation,
literal Summary and failure gates remain. The live scan limit now matches the
existing 600-second runtime default; DB loading consumed 293.9 seconds of the
former bound. Retained DB/cache state also changed, so the continuation does not
isolate the limit's effect or guarantee completion with a newly populated cache.

Actor execution was 1,337.7 seconds/$0.8799725 for the first run and
753.8 seconds/$1.14885925 for the continuation. Each used six unpriced judge
calls; total evaluation costs are unknown. Raw attempts, identities and independent
reviews remain under `.work/fix-go-cves-release024/full-live-current/` and
`full-live-600/`. Validation passes 3,023 shell checks, 64 helper tests and 71
focused scanner/abort checks, including regressions that fail on prior source.
That continuation exercised blocked remediation while leaving unit coverage
unverified. The corrected matrix below measures the maintained unit command;
reliable final advice remains unresolved.
The owned worker is stopped; process/socket removal and the unchanged host alias
are verified, with caches and evidence retained.

## Branch-policy matrix

The fifth six-cell matrix at `7063ca5e` used the stock runner serially,
one actor per cell at pinned CLI 2.1.307, with unchanged criteria, models, pins and
caps. Three live cells executed the declared `make unit`. Admiral release
explicitly replaced it with host `go build ./... && go test ./...`; the engine
honored that actual request. Do not credit this cell with canonical unit or
Dapper test coverage. Explicit commands measure forwarding/execution rather than
all inherited-command selection behavior; the separate forward review does not
overrule this actual precedence failure.

| Cell | Runtime / execution | Stock grading | Independent reply review |
| --- | --- | --- | --- |
| Replay 005 | Recorded blocked result; actor exits normally | Contract true; backport TTT; action TTF, unstable majority true | Unsupported exposure cause and wrong Go 1.25 tooling context; useful backport prerequisite |
| Replay 007 | Recorded blocked result; actor exits normally | Contract true; backport TTT; action FFF | Unsupported reporter/syncer independence and retry-only dismissal |
| Admiral release (001) | Engine 2; custom host command exits 1, 1; audits/final scan pass | Contract false; outcome TTT; action FFF | Replaces inherited command, alters one Summary line and asserts unsupported causality |
| Admiral devel (002) | Engine 0; canonical unit 0; genuine 5-to-0 repair | Contract false; outcome FFF; action FFF | Invented fenced push/PR command despite withheld recipe |
| Subctl devel (003) | Engine 0; canonical unit/license/audits/native scan pass | Contract true; outcome TFF, unstable majority false; action FFF | Replacement publication prose and omitted scan scope |
| Subctl release (004) | Engine 0; canonical unit/license/audits/native scan pass | Contract true; outcome TTT; action FFF | Replacement publication prose and omitted scan scope |

Admiral release's test-command replacement runs e2e tests that fail for missing
KUBECONFIG, alongside reporter vet failures. The reply reports the actual host
command and both exits, but recommends another filtered host command instead of
restoring the inherited maintained check. The standard independent review retains
16/19: canonical unit receipts, sampled Dapper image ancestry and cache mounts
are missing. This is actor-induced coverage loss, not environment routing or
corrupt engine evidence. Its quote expands the Summary's `GO-2026-6603 ... (5 CVEs)`
into five IDs, so literal relay fails despite retaining every line.

Admiral devel's independent engine review passes 19/19 with actual Dapper unit
execution; its build/license gates remain unconfigured and unverified. This does
not establish native-binary scan coverage. Both Subctl branches pass 25/25 terminal
checks plus 6/6 initial checks: corresponding scan HEAD, clean embedded VCS,
binary SHA and positive catalog location/file hash agree, with final bytes matching
retained output. Devel went from 12 actionable findings to zero with one scoped
crypto ignore; release went from 17 to zero with one ignore. No stdlib repair,
hand repair or target publication is claimed. The four `ERROR` lines in devel
are passing negative-test output, supporting the reply's explanation.

Wrappers preserve actual child exits in terminal logs and native notifications;
native/normalized observations and final selection agree. Admiral release's
interim waiting result and later completed result belong to one actual session;
the final reply follows a genuine completion notification and terminal exit 2.
Run-owned wakeups were stopped. No denied mutation or independent extra gate
occurred, but the wrong command inside the single script invocation remains a
failure. All three successful live replies still invent publication procedures.
Subctl scan-scope omissions are reporting gaps, not false source-only claims or
failures of the actual native scans.

All 36 factual samples completed with zero errors. Sixteen distinct retained
rationales were reviewed, not 36 independent explanations. Replay 005's action
majority accepts an unsupported exposure hypothesis; one true rationale invents
a directive raise to Go 1.25, and none catches the recorded Go 1.26.8 image context.
Admiral release's action rationale rejects independence but asserts the opposite
activation cause without captured proof. Subctl devel's outcome split concerns
explicit scope reporting; release's stable TTT representative waives that same
omission. Correct publication rejections sometimes add unsupported cleanup or
recommendation restrictions; these do not change the raw labels. The fixed
nine-sample publication calibration remains FFF/TTT/TTT with zero errors; it is
selected oracle coverage, not actor acceptance.

All 431 stock artifacts, six consoles and 99 runtime-review proof artifacts were
verified. Known actor costs total $4.853852; judge and total costs are unknown.
Run IDs are `quality-evidence-{replay005,replay007,live001,live002,live003,live004}-20261021-01`.
Receipts/reviews are under `.work/fix-go-cves-release024/evidence-matrix-20261021/`.
One actor per cell and mutable build/database state do not isolate source-change
effects. The owned worker was stopped after identity checks; caches, data and
evidence are preserved.

The skill remains unaccepted. The measured ownership/evidence clarifications did
not establish reliable command selection, causal diagnosis or publication advice.
No further source treatment, actor cohort, warning template or reviewer workflow
is selected. Preserve current criteria, useful diagnosis and the unresolved
Go-minor policy decision; no approval or new policy knob is inferred. The
[testing strategy](../../plans/testing.md) separates durable acceptance from
historical results.

The [fourth matrix record](https://github.com/dfarrell07/ai-helpers/blob/7063ca5e3d9b7c07c4472479426d9e5d4ee12564/plugins/fix-go-cves/evals/live/README.md#branch-policy-matrix)
retains its 431 artifacts, original grades, extra preflight build and scope gaps.
The [third matrix record](https://github.com/dfarrell07/ai-helpers/blob/368e0e2be7cfdf4291612b8ba7089366193fa1d5/plugins/fix-go-cves/evals/live/README.md#branch-policy-matrix)
retains its 433 artifacts, original grades and incomplete CLI binding, including
the explicit final-two pin and corrected local replay-005 cell label.
The [second matrix record](https://github.com/dfarrell07/ai-helpers/blob/e189eef647edfecebb50c6c0a0c19714791984af/plugins/fix-go-cves/evals/live/README.md#branch-policy-matrix)
retains its 431 artifacts, original grades and wrapper/false-completion findings.
The [first matrix record](https://github.com/dfarrell07/ai-helpers/blob/01d66debbc1b8bd27da264b8a568cb6146a435d8/plugins/fix-go-cves/evals/live/README.md#branch-policy-matrix)
at source `7b6a7714` retains its 428 artifacts, replay timeout, unscored samples
and unstable grade. No closed matrix establishes fully correct skill behavior.
