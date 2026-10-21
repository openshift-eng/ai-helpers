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
