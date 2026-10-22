# CVE fix evaluations

The default track measures the skill's interpretation of a recorded run in a
real, pinned repository checkout. It stages the recorded plugin with today's
`SKILL.md`, replays the captured result, and checks the retained state and final
reply. It does not run today's remediation scripts.

The `--live` track runs today's scripts with the repository's detected build and
test commands and real Grype scans. Findings and outcomes come from that run.
See [live cases](live/README.md) for its status. A passing historical replay does
not establish that current remediation works end to end. A live eval can pass
when the skill correctly reports a blocked or partial remediation outcome.

## Current E2E work

Live scenarios now check receipts for declared completed gates, including blocked
runs: paired test logs/receipts agree with the last tested HEAD, command and exit;
successful verification retains all four clean audits; reached scans retain
matching phase/HEAD status and successful scan documents; completed license
checks retain their log. Nonzero gate results remain valid observed outcomes.
The stronger successful-repair and native-coverage requirements remain separate.
The helper also checks completed aborts without requiring a Summary, and omits
unrelated default-branch history when the runtime restores the original checkout.

The explicit publication-command contract now checks fenced blocks, inline
commands with arguments and command-leading lines. It preserves ordinary bare
command-name mentions and still requires the complete emitted recipe. Seven
regressions fail against the prior helper. This does not interpret arbitrary
prose procedures; whole-reply review remains necessary.

A six-line clarification to the existing live `action_owner` prompt fixes a
measured inference error: unchanged source/configuration alone does not establish
that a failure was independent of dependency/toolchain changes. A fixed
five-fixture calibration matches all 15 expected labels with zero errors,
including the untouched actual negative and a supported controlled experiment.
The stock CLI's exit 1 is retained: negative calibration fixtures correctly fail
actor thresholds. It retains five representative rationales, not fifteen; minor
nondecisive terminology errors remain. This is selected oracle coverage, not
actor improvement or general grader acceptance. Original scores are unchanged.
Records are under `.work/fix-go-cves-release024/causal-evidence-calibration/`.

The stock prompt-mode fresh-diagnosis component pilot stopped on case 005:
its completed reply preserved state and Summary, but omitted the available
backport, guessed the original ref and overstated causality. It took 101.8 seconds
and $0.69357725, without judges. No later case or retry ran, and no production
subagent routing was added. Raw results and independent reviews remain under
`.work/fix-go-cves-release024/diagnosis-component/`.

The full stock replay-005 pipeline at `d6ad2e5c` completed in about 250 seconds:
one actual skill invocation, collection/extraction, contracts, all six factual
samples, HTML report, completion verification and regression output. Contract
passes, backport is true 3/3 and action/owner false 3/3 for the contradicted
newer-`x/tools` explanation; zero judge errors. Runner exit 1 is preserved.
Actor cost is $0.72549375; six judge calls are unpriced, so total cost is unknown.
All 30 recorded artifacts match their hashes. Records remain under `.work/fix-go-cves-release024/full-pipeline-check/`. This is completed
orchestration with a failed skill result, using historical runtime and the
existing replay criteria; it does not measure today's remediation or the revised
live judge.

The current-runtime live case-004 continuation reached every recorded phase and
completed the stock pipeline after narrow corrections to diagnostics, collection
and scan timeouts. Two lint attempts failed, leaving unit tests unrun; audits, license
and native final scanning passed. The invoking skill still fails literal Summary
relay and factual diagnosis. The [live record](live/README.md#current-runtime-integration)
retains both measurements, scores, coverage limits and costs. Those runs used
our incorrect release lint override. The subsequent [four six-cell matrices](live/README.md#branch-policy-matrix)
are closed. The latest at `368e0e2b` completed six actors and 36 factual samples
with zero judge errors, all at pinned CLI 2.1.307. Every live cell ran unit tests;
Admiral release retained its blocker, while the other three passed configured
gates. Both Subctl branches have positive native coverage. Full Summary relay
and child-status handoff are observed; causal overclaims, replacement publication
and an extra preflight build remain. Original grades and instability are preserved.

The policy/procedure clause did not establish reliable publication behavior.
The selected next change replaces only the global script-ownership sentence and
causal-evidence bullet: scripts own scans/builds/tests in every phase, and version
comparisons or retries alone do not establish cause. No new baseline test,
publication warning, policy knob or reviewer workflow is selected. After review
and commit, measure the same six cells once at pinned 2.1.307 with unchanged
criteria, preserving all failures without adaptive repetition. The Go-minor
policy question remains pending and grants no approval.

## Recorded cases

| Case | Repository | What it measures |
| --- | --- | --- |
| case-005 | admiral, release-0.24 | Diagnose the reporter vet failure, find the existing default-branch backport, and explain where it must land before rerunning. |
| case-007 | admiral, release-0.24 | Distinguish a persistent reporter failure from a first-only syncer failure; qualify causality and give usable next steps. |

Case 005 retains its original recording identifier; case 007 preserves a later
real live run as a separate replay. The default remains case 005. Other recordings
remain planned in [testing and evals](../plans/testing.md).

## Setup

Run from the ai-helpers repository root with Git, Python 3.11 or later, and the
Claude Code CLI installed. Use a local environment for the harness and judges:

```bash
export HARNESS="$PWD/.work/fix-go-cves-evals/harness"
git clone https://github.com/opendatahub-io/agent-eval-harness.git "$HARNESS"
git -C "$HARNESS" checkout 1a980e707909a23f8c143ce333d97f5203db34ab
python3 -m venv .work/fix-go-cves-evals/venv
. .work/fix-go-cves-evals/venv/bin/activate
python -m pip install -e "$HARNESS[anthropic]"
export CVE_EVAL_PYTHON="$VIRTUAL_ENV/bin/python"
python3 -I -c 'from yaml import CSafeLoader'
```

The pin is the harness revision used for the pilot. Keep the environment active
so hooks and live runtime commands using `python3` find its dependencies even
with a fresh case `HOME`. `CVE_EVAL_PYTHON` selects the driver only; it does not
activate that environment for child commands. The isolated import above checks
the required YAML backend without relying on user-site packages. Each run
records the actual harness commit in `harness-revision.txt`.
Resolve and hash the CLI selected by the actual launch PATH, recording its version.
Pin the version-specific executable and compare the native init version with that
frozen identity.

Supply model authentication through the environment: each case gets a fresh
`HOME`, so an existing interactive CLI login alone is insufficient. For Vertex,
explicitly enable `CLAUDE_CODE_USE_VERTEX=1` and configure
`ANTHROPIC_VERTEX_PROJECT_ID` and `CLOUD_ML_REGION` for your account.
`run.sh` forwards `GOOGLE_APPLICATION_CREDENTIALS`; if unset, it uses the path to
existing Application Default Credentials under the caller's home directory.
It does not copy credential contents into the fixture. The judges also need
working provider credentials.

For live runs, also satisfy the [runtime prerequisites](../README.md#prerequisites)
and provide the container runtime and network access needed by the repository's
detected commands and scanners. The live cases use local remotes and never
publish changes. `DOCKER_HOST` is forwarded when set, allowing a dedicated
build daemon; it does not isolate the invoking agent from host files or credentials.
For the tested rootless Shipyard worker, daemon user/mount namespace mapping
was also necessary to preserve checkout ownership through Dapper. Revalidate
that mapping and targeted cancellation cleanup when recreating the worker;
see the [worker evidence and limits](../plans/testing.md#environment-evidence-and-deadlines).

For a controlled live run, set `CVE_FIX_GRYPE_VERSION` to the requested
release (for example, the observed `v0.121.0`). The live runner forwards and
freezes it; unset keeps the runtime's default update behavior. Capture the actual
scanner identity as well: the database and builder tags remain live.

Optionally export absolute `GRYPE_DB_CACHE_DIR` and `GOMODCACHE` paths outside
the evaluated checkout to reuse host caches. These apply to local Grype and
host Go; container caches are separate. Unset variables retain default behavior.
For a constrained Shipyard worker, `GOMAXPROCS=2 DAPPER_ENV=GOMAXPROCS` limits
Go compilation/test concurrency while retaining canonical commands, race checks
and coverage. These nonsecret settings are forwarded and frozen with the run.

## Run and inspect

```bash
plugins/fix-go-cves/evals/run.sh --dry-run
plugins/fix-go-cves/evals/run.sh
plugins/fix-go-cves/evals/run.sh --live
```

`--dry-run` fetches the real pinned history and replays the result without model
calls, builds or scans. `--prepare-only` prepares the checkout without replaying.
Preparation checks both pinned trees for reserved eval paths before checkout.
Repositories tracking paths such as `.claude` remain unsupported: preserve their
settings and instructions rather than deleting them to admit a case. Composing
project settings with harness settings needs a separate design.
Use `--model MODEL` for the invoking agent and `EVAL_JUDGE_MODEL` for judges.
`--run-id ID` chooses a new result identifier; existing identifiers are rejected.
Repeat `--case ID` to select cases within the chosen track; defaults remain the
recorded case-005 and live case-001.

The runner prints workspace and result paths. Results default to
`.work/fix-go-cves-evals/runs/fix-go-cves:fix-go-cves/<run-id>/`; override the root
with `AGENT_EVAL_RUNS_DIR`. Inspect the extracted `output/reply.md`, captured
`output/state.json`, event logs, metrics and judge results under each case.
The harness also writes its standard `report.html` in the result directory.
Each run stores frozen configuration and fixtures with hashes under `provenance/`;
all stock stages score those copies. The runner checks exact selected cases,
judges and complete samples, and exits nonzero for factual acceptance failures.
Extraction validates frozen inputs, the helper hash and exact collected case
membership before changing captured state/replies or starting judges. Missing or
extra case directories stop scoring; a stale helper also stops without rewriting
prior outputs or scores.
Use a new frozen result record for deliberate rescoring; preserve prior scores.
The replay contract checks one invocation, exact result commit and branch,
clean state, unchanged staged skill/scripts and remote refs, required commit citations,
complete literal Summary relay from the trusted log, and publication or destructive
operations. Clean runs without a Summary retain their existing outcome checks. Fact judges score the backport and
action/owner criteria using three samples each. Missing verdicts or incomplete
samples are errors; a completed factual failure is retained as a failure.

The 2026-10-19 replay pilot passed the contract and the original fact judges.
Manual review found incomplete next-step advice and unsupported causality/risk
claims. The `action_owner` prompt was tightened to require every substantive
criterion; the same retained reply now fails it in all three samples. The agent
was not rerun, and the original scores remain as evidence of the old prompt.
Agent execution took 83 seconds, 18 turns and $0.53. Judge calls were unpriced,
so $0.53 is not the total evaluation cost.

Calibration of the original prompts completed: the corrected reference passes
both criteria; the missed-backport negative fails `backport`; the fix-branch-only
negative fails `action_owner`. Each result has three agreeing, error-free samples.
A focused skill update now requires explicit remaining-CVE/PR status, the
remote-target repair before rerunning, and evidence for causality. Its first
trial passed the contract and both then-current fact judges, each with three agreeing,
error-free samples: 79 seconds, 15 turns and $0.49 for agent execution. Manual
review still found unsupported claims about unrelated causality and unchanged
behavior. These earlier passes do not establish complete response accuracy or
qualify the later acceptance baseline.

A clean-scope live trial then exceeded the intended post-run role: the agent
edited and committed a source repair, attempted another run, and started cleanup.
Its evidence is retained as a behavioral failure. A subsequent instrumented
trial passed the full pipeline, preserving and correctly reporting the script's
blocked result: five CVEs fixed, zero outstanding, but tests failed twice and
the runtime exited 2. Agent execution took 456 seconds, 14 turns and $0.62;
judge and independent runtime reviewer costs were unavailable. See
[live results](live/README.md). This is one faithful blocked run, not proof that
all remediation gates pass or that the replay baseline is accepted.

The [live attribution experiment](live/README.md) confirmed that the Go directive
raise alone triggers the current vet failure; the reply's tooling explanation
was inaccurate. Historical replies lacked that baseline; later acceptance
measurements use fresh executions rather than the earlier passing replies.

The skill now explicitly limits post-run work to read-only diagnosis and
recommendations. Current causal criteria reject a wrong explanation even when
the proposed repair and owner are correct. Both references, four isolated causal
negatives and the replay rerun negative passed seven action/owner checks with
three agreeing, error-free samples each (21 calls). Earlier failed calibration attempts
remain preserved: one lacked dependency-diff context, and judges sometimes gave
partial credit despite recognizing the wrong explanation. Judge costs were unavailable.

The first frozen replay baseline at source `5079407` then completed and
**failed**: the contract passed 3/3 executions, but both factual criteria
together passed only 1/3 (required 2/3). Backport passed every execution;
action/owner failed runs 1 and 3 on unsupported causal attribution. All judge
samples were unanimous and error-free. The three agents took 89.5, 83.5 and
82.9 seconds and cost $1.54124 in total; 18 judge calls were unpriced. All used
Claude Code 2.1.304 and the same frozen inputs. Full reports and manual review
are retained in `.work/fix-go-cves-next-slice/replay-baseline-20261019/`.
No failed trial was replaced or retried. Manual review also found unverified
claims about upstream validation and future PR availability.

The follow-up targets actual terminal-exit observation, base-to-result dependency
comparison and qualified recommendations. Its cohort at `9ba32eda` completed
but **failed**: contract 2/3, factual conjunction 3/3 by majority. Run 2 omitted
retained fix hash `aa5a4fc`; its action/owner samples were false/true/true, while
the other factual samples were unanimous true. All three actually compared
base/result directives. Manual review still found unverified upstream
validation, unchanged-behavior and future-PR claims. Agent cost totaled
$1.60466925 plus 18 unpriced judge calls. Reports remain in
`.work/fix-go-cves-next-slice/replay-followup-20261019/`; no trial was replaced.

The precise relevant analyzer feature is
[inferred interface-method wrappers gated on file Go 1.26 or later](https://pkg.go.dev/golang.org/x/tools@v0.49.0/go/analysis/passes/printf#hdr-Inferred_printf_wrappers).
This supports directive-triggered checking without an x/tools dependency bump;
unchanged x/tools does not disprove it. Keep raw mixed verdicts intact.

The compact-report cohort at `b8265808` also **failed**: recorded contract 2/3,
factual conjunction 2/3, all 18 samples error-free and unanimous per verdict.
All replies cite `aa5a4fc`, but runs 2 and 3 invent a push command. Run 3's
list-indented fence bypasses the column-zero-only deterministic guard, and its
fact judge also passes; manual publication compliance is 1/3. Both replies name
the wrong original branch, and run 2 promises a passing rerun and PR command.
Agent cost totaled $1.982726 plus 18 unpriced judge calls. Reports and the exact
guard probe remain in `.work/fix-go-cves-next-slice/replay-report-20261019/`.
Original scores are preserved. The guard now handles indented fences; its
deterministic re-verification needs a separate label, not a fourth paid cohort.

The corrected-worker case-002 runtime passed all 14 repair assertions, while
its agent response failed the publication guard. Native Subctl case-003 now
passes all 19 engine/native runtime conditions, but its parent exits 1 without
a completed final reply. The runner aborted before collection/reporting, so
operator-verified runtime artifacts do not imply a scored skill pass. Plain
30-second waits are now explicit. Failed executions now proceed through stock
collection/reporting with nonzero status; invalid grading is skipped. No native
retry is planned merely to seek a pass. Refreshed blocked case-001 retained
valid runtime exit-2 evidence but temporarily cherry-picked and restored source.
Its original contract passed despite these writes; outcome passed 3/3 and
action/owner failed 3/3, without judge errors. Separate collection and trace
re-extraction with the corrected guard reject those mutations, preserving all
91 original files and raw scores.
See [live results](live/README.md). Reporting and read-only behavior remain
blockers exposed by those older measurements; the current implementation and
separate measurements are recorded below. Runtime success and skill accuracy
remain separate.

The live configuration permits a larger invoking-agent budget, but that budget
does not cap independent reviewer CLIs launched by the remediation scripts or
judge costs. See the live configuration for its execution and runtime deadlines.

## Current reporting implementation

The skill now quotes the actual terminal result, then diagnoses flagged outcomes
read-only. Known original refs are printed by the runtime; unknown return advice
is omitted. Publication relay accepts only the complete emitted recipe or literal
Summary. Live log identity is recorded at completion, and native string-message
permission events retain their denied-operation verdict instead of crashing.
The shell suite passed 2,343 checks and the eval suite 47.

| Frozen source | Case-005 comparison | Original result | Agent cost |
| --- | --- | --- | --- |
| `07794846` | Literal report | Incomplete: two scored passes, third extraction error | $1.798218 plus 12 unpriced judge calls |
| `07515259` | Typed SDK events and future-outcome clarification | Contract 3/3, factual conjunction 3/3; all 18 factual samples agree without errors | $1.60757575 plus 18 unpriced judge calls |

The first comparison's original summary remains absent for run 3. A separately
frozen, model-free extraction now yields a false contract with its denied
read-only `git stash list` attempt retained under the existing strict policy;
no stash mutation occurred. Original artifacts and scores were not rewritten.
Both comparisons' logs, metrics, hashes and independent manual review are under
`.work/fix-go-cves-reporting-implementation/replay-literal-20261020/` and
`replay-literal-followup-20261020/` alongside it, with standard results under each
`cve-replay-literal[-followup]-20261020-rN` run directory.

Manual review supports literal-result and non-mutation behavior in all three
revised executions, but records future-result estimates/purpose wording as
limitations. A subsequent wording refinement makes recommendations describe the
next prerequisite and verification needed. The earlier replays do not measure
that refinement. The current-engine blocked check at `a6c8e5a0` passed contract
and outcome (3/3), but failed action/owner (3/3 false) on unsupported causality
for a first-only syncer failure, with no judge errors. Reporter/capture integration
and read-only behavior are verified; overall skill acceptance still fails.
A clarification covers each distinct failure and what a passing retry establishes.
The case-007 comparison below measures that guidance; it did not resolve the
unsupported causal synthesis. See the
[live record](live/README.md#current-reporting-integration-check). Positive command
relay has helper-fixture coverage, not a new full historical-case/model measurement.

## Multi-failure replay

Case 007 preserves the real live run's persistent reporter failure and first-only
syncer failure. Its reviewed reference and causal negative calibrated at
`fbda167a`: all 12 samples match expected labels without errors; judge cost is
unknown. [Fixture provenance](cases/case-007/calibration.md) records the inputs.

The comparison at `0fdccbb0` **failed**: contract 2/3 and factual conjunction 0/3.
Backport passed all nine samples; each action/owner aggregate failed with two
false and one true sample, without errors. All three replies read the actual
base-to-result diff and preserve the Summary, exit, counts, original ref and
both detailed attempt outcomes, but make unsupported pre-existing/unrelated
syncer claims elsewhere. Run 2's introduction also conflicts with its accurate
detailed attempt history. Its read-only `git stash list` attempt fails the
existing strict contract; no stash mutation occurred. No publication recipe
was invented. Agent cost was $2.113722 plus 18 unpriced judge calls. One rationale
wrongly treats unchanged x/tools as disproving directive-gated vet; the unsupported
syncer claims independently support the failures.

Original artifacts and raw scores remain under the standard
`cve-replay-multifailure-20261020-rN` run directories. The declared comparison,
logs, metrics and independent audits are retained under
`.work/fix-go-cves-multifailure-implementation/`. The factual judges measure
backport/causal advice; manual outcome verification remains separate.

The frozen follow-up at `d9261b68` also **failed**: contract 3/3 and factual
conjunction 1/3. Backport passed all nine samples; action/owner samples were
false/false/false, true/true/true and false/false/false, without errors. Agent cost
was $1.68287475 plus 18 unpriced judge calls. All three invocations completed;
original artifacts and raw scores remain in `cve-replay-observed-work-20261020-rN`.

Manual review found syncer entirely absent from replies 1 and 3, versus none
omitted in the first comparison. Reply 1 also truncates the literal Summary;
reply 3 asserts newer tooling without inspecting the base-to-result diff.
Reply 2 preserves both attempts and explicitly leaves update causality unproven;
its raw pass stands, with a precision caveat about locating a race in the test
without distinguishing implementation behavior. It gives no separate syncer
next action/owner. These observations do not establish a population-level effect.
The two-line remaining-work treatment is reverted; the earlier wording remains
unaccepted. No further prompt-only cohorts are selected.

Trace review found reply 1 never retrieved the syncer failure: broad searches
truncated expected-error chatter. The existing diagnostic grep now also selects
anchored Go `FAIL` and `--- FAIL:` results. Actual-command probes on cases 005
and 007 expose their reporter results and case 007's first-only syncer result.

The measurement at `f3b12fd3` selected both cases for three executions each, but
**stopped after the first pair**; it is not a completed comparison or acceptance.
Both agents completed read-only and actually used the new search. Case 007
retrieved both failures and retry outcomes, yet its overview attributes both
to the directive change and claims both have existing repairs, despite qualified
syncer detail later. This is synthesis after evidence exposure, not another
retrieval miss. No further invoking-agent trials are selected for this branch.

Original case-005 contract is false solely because the new Summary checker
wrongly required a historical wrapper `exit=2` inside the fence; the reply quotes
the complete engine Summary and states the exit separately. Its factual samples
are all true. Original case-007 contract/backport pass; action/owner is true by
majority with samples true/true/false and no errors. Manual review rejects its
unsupported overview; the raw passing score remains unchanged. Agent cost is
$1.015971 plus 12 unpriced judge calls. All 49 original files and earlier records
remain intact under `cve-replay-retrieval-20261020-r1`; independent audits and the
operator stop receipt are in `.work/fix-go-cves-e2e-reliability/`.

The corrected checker separates an optional matching terminal wrapper status
from the complete engine Summary. Replay likewise omits the historical wrapper
status from emitted engine stdout, so the invoking wrapper records it once.
Frozen recordings remain unchanged. Model-free checks cover the real case-005
positive, case-007 truncation, and exact publication witness handling; prior
scores are not rewritten. Runtime retry text now describes a retry without
claiming to rule out flakiness; the historical measurement cannot test that edit.

One focused case-007 negative adds an unsupported global attribution to the
reviewed reference while retaining its later uncertainty. Two lines in the
existing action/owner prompt explicitly cover the whole reply; the criterion
is unchanged. The oracle-only calibration at `eb44d2f1` passes all 21 samples
without errors: both references are accepted and this negative, the existing
retry negative and three case-005 negatives are rejected, three samples each.
The stock rendered prompts, frozen inputs and raw rationales remain under
`.work/fix-go-cves-e2e-reliability/oracle-calibration/`. It took 472.78 seconds;
all 21 judge calls are unpriced. No backport judge, new judge, output schema,
actor campaign or tuning loop was added. This validates the seven selected
oracle examples, not the natural retained reply or new invoking-agent behavior.
It does not establish current-engine repair, native completion or general reliability.

The corrected helper passes 52 tests. The controlled original shell suite
passes 2,343/2,343 using a task-owned `TMPDIR` and matching
`GIT_CEILING_DIRECTORIES`, after a separate discovery-equivalence probe.
Retained evidence confirms the complete fixture reached tests, verification,
license, final scan and all four audits. The first full shell run passed only
2,335/2,343; its eight durable-evidence failures remain unexplained because
its temporary log was deleted. Three isolated 23-check repetitions pass.
A later host `/tmp` quota exhaustion is observed, not a proven cause of the
first failure. The shell suite now retains its owned temporary tree on failure
and removes it on success. Diagnostic attempts and evidence remain separately
recorded in `.work/fix-go-cves-e2e-reliability/shell-investigation.json`.

The observation-to-repair workflow at `2f6102d2` removes the mandatory causal
investigation throughout the skill, rather than only changing the final heading.
It requires each failure/attempt outcome and an inspected matching repair or
remaining investigation; dependency comparisons are conditional on change claims.
Independent design review supports the smaller task, not a reliability claim.

Its declared three-execution 005/007 comparison stopped after one completed pair,
`cve-replay-remedy-20261020-r1`. Both actors completed read-only and relayed the
full Summary. Both deterministic contracts pass, both backport criteria are true
in all three samples, and both action/owner criteria are false in all three
samples, with zero judge errors. The stock pipeline exits 1 for that regression.
Case 005 spontaneously asserts newer tooling dependencies without comparing the
actual dependencies. Case 007 retrieves both failure classes and attempts, then
calls both failures pre-existing and unrelated without baseline evidence. It also
leaves the separate syncer investigation's owner unspecified.
The correct reporter backport and remote-target prerequisite do not cure those
claims. Independent native/whole-reply review agrees with rejection.

Agent wall time was 292 seconds and actual model usage cost $1.80188575, plus
12 unpriced judge calls. The frozen source was clean, the harness remained
`1a980e707909a23f8c143ce333d97f5203db34ab`, and the actual CLI was 2.1.304 with
`claude-opus-4-6` for actor and judges. Both model-free preflights passed. Raw
outputs, all samples and the standard report remain in the run directory;
the experiment declaration and independent reviews are under
`.work/fix-go-cves-remedy-workflow/`. No r2/r3 or additional wording cohort ran.
Keep this comparison incomplete and the skill unaccepted. Retain the smaller
workflow for task fit only; this pair establishes neither comparative improvement
nor degradation. No new judge, schema, runtime gate or reviewer layer was added.

The `487d0759` candidate restricted final prose to observed results and per-failure
actions, and added a workflow-ownership clarification. Its declared three-run
005/007 comparison stopped after one completed pair,
`cve-replay-bounded-20261020-r1`. Contracts are true for 005 and false for 007;
backport is true in all six samples, action/owner false in all six, with no errors.
Case 005 puts unsupported tooling causality inside its Observed field. Case 007
never retrieves the syncer retry pass and omits it, leaves the owner unspecified,
and attempts denied, read-only `git stash list`; no stash mutation occurred.
Its syncer causal explanation is a hypothesis, not the earlier categorical claim.
Some judge reasoning incorrectly questions directive-gated vet without a compiler
change; the independent coverage/action defects still support rejection.

Outer pair wall time was 223.2 seconds and actor cost $1.0215355, plus 12 unpriced
judge calls. Frozen provenance, loaded skill, native finals and all 50 original
files were independently verified. No r2/r3 ran. The actual Admiral `CLAUDE.md`
imports a manual CVE workflow that requests mutation, verification and generated
publication recipes; those files remain intact. Their presence does not establish
the cause of the agent errors or invalidate earlier trials. The separate real
[successful-repair check](live/README.md#successful-repair-reporting-check) also
fails publication reporting. The whole skill treatment was reverted, preserving the
prior smaller baseline and all original results. Audits and declarations are in
`.work/fix-go-cves-bounded-report/`; no new judge, renderer or reviewer loop was added.

## Live evidence and coverage

Runtime audit completeness is now enforced before verification or repair
dispatch. Previously a missing audit directory, a reduced script set, malformed
counts such as `NEW_ISSUES=banana`, or missing `UNRESOLVED` could pass. The
existing text format now requires four fresh known audits with complete, unique
nonnegative integer counters. Invalid evidence blocks repair; valid positive
evidence still enters the bounded repair/recheck loop.

The focused regressions reproduce 28 failures on the prior library and pass
61/61 on the fix. Existing orchestration and publication fixtures pass, and the
full controlled shell suite passes 2,401/2,401. Its first run passed 2,384/2,401:
17 native-fixture assertions failed because that fixture omitted every audit.
Adding all four real companion scripts preserves its assertions and passes all
130 native checks; no production requirement was relaxed. The 52 eval helper
tests, Bash syntax and error-level ShellCheck of the changed runtime scripts
pass. A broader ShellCheck invocation including the large test file ended 137
without diagnostics; it is not passing evidence.

The redundant model verification layer is now removed. All four shell audits,
strict completeness checks, bounded mechanical repair/recheck, the main AI review
and independent final scan remain. Visible poison CLIs reproduce six failures
on the previous library and pass all 69 focused checks without any verifier
model calls. Durable orchestration passes 38/38; the full frozen-source suite
passes 2,364/2,364 and the eval helper passes 52 tests. The smaller count reflects
deleted tests for the deleted model machinery. One native fixture now checks
actual clean audits and its partial result instead of an incidental model veto;
its 13 checks pass. An earlier full run interrupted by an in-place test edit is
preserved as incomplete. Validation logs are in
`.work/fix-go-cves-deterministic-verification/`; these are not new live or
invoking-agent acceptance results.

A subsequent stock live `case-002` run, `cve-live-admiral-deterministic-20261020`,
froze `87ca7ece` and exercised the new path on real Admiral `devel`. Engine exit
0 after 392 seconds retained `6300a751`: x/net v0.59.0 → v0.60.0 cleared all five
initial findings. Canonical `make unit` passed at that HEAD, all four audits
passed directly, and the independent final scan was healthy and clean. All 14
runtime conditions and all 51 archived evidence hashes passed independent
review. License was unconfigured; the main AI review was correctly skipped.
This covers source repair, not native binaries or verification-time repair.

The invoking agent completed in 479.7 seconds (481.4 seconds outer wall time), 19 turns,
$0.593933, plus six unpriced judge calls. Contract passed; outcome samples were
true/true/true and action/owner false/false/true, with zero errors; the pipeline
exited 1. Its literal Summary was faithful, but it then supplied a remote-add
command and branch-specific push/PR procedure despite the withheld recipe.
No publication or follow-up mutation occurred. Both rejecting judge rationales
also wrongly treated permitted return-to-original-ref advice as prohibited
cleanup; preserve those mixed scores separately from the independent publication
finding. The worker passed fresh ownership/cancellation probes and its shutdown
was verified. Original results and scores remain unchanged; derived reviews are
in `.work/fix-go-cves-deterministic-verification/`. No additional wording trial
or judge change was made.

The unchanged real Admiral audit archive also passes the new validator. This
is compatibility evidence, not another live run or an invoking-agent acceptance
claim. Original scores remain intact; no additional actor or judge calls were
needed. Reproduction and validation logs are in
`.work/fix-go-cves-audit-completeness/`.

The live helper opts into an external `CVE_FIX_EVIDENCE_DIR` and archives its
contents under each case's `output/runtime/`. This includes initial and
independent final-gate JSON when reached, phase outcomes, canonical command logs,
raw audit evidence and same-scan CycloneDX catalogs. The completion snapshot
hashes the evidence, including observed scanner/Docker image identities. Image
listings record observed identities; they do not freeze mutable builder tags.
`output/change.patch` and `runtime-identity.json` preserve the exact retained
change and runtime hashes. Judges receive the retained dependency diff alongside
the reduced runtime log, so they can assess claims about dependency changes.

The [live cases](live/README.md) distinguish faithful blocked-run reporting,
genuine repair and native Linux/amd64 binary coverage. The repair assertion
requires a fixable finding actually cleared rather than ignored, a retained
dependency change, canonical gates and complete audits, and runtime exit 0.
Native coverage requires the Subctl artifact's fresh build/hash, positive
binary-catalog location and matching file hash, and unchanged retained output.
A real clean initial fast path uses its initial catalog; it does not invent a
final scan or claim repair coverage. A completed native remediation flow must
also pass canonical test, verification and license gates. Findings may still
leave that scenario partial; report runtime success separately from coverage.

## Fixture and checks

Case 005 contains pinned input, judge annotations, the original result bundle,
the recorded plugin archive, the full sanitized log, a corrected reference and
negatives for a missed backport and an unusable rerun. The helper validates
archive entries before extraction and checks bundle ancestry. Only the case
input, staged plugin and replay evidence reach the workspace; reference replies
and annotations stay out.

Run `python3 plugins/fix-go-cves/evals/test_eval.py` for the helper's unit checks;
`make test` includes them. These checks supplement the actual checkout/model
pilot. Permissions, fresh configuration directories and state/trace checks limit
or detect mistakes; the stock runner does not isolate host files or credentials.
Use trusted code and inspect unexpected sessions.

The [testing plan](../plans/testing.md) records calibration, acceptance and future
case work without requiring a custom runner or sandbox for this plugin.
