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

## Recorded cases

| Case | Repository | What it measures |
| --- | --- | --- |
| case-005 | admiral, release-0.24 | Diagnose the reporter vet failure, find the existing default-branch backport, and explain where it must land before rerunning. |

Case numbers retain the recording identifiers. Other recordings remain planned
in [testing and evals](../plans/testing.md).

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
```

The pin is the harness revision used for the pilot. Keep the environment active
so hook commands using `python3` also find its dependencies. Each run records the
actual harness commit in `harness-revision.txt`.

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
Use a new frozen result record for deliberate rescoring; preserve prior scores.
The replay contract checks one invocation, exact result commit and branch,
clean state, unchanged staged skill/scripts and remote refs, required commit citations,
and publication or destructive operations. Fact judges score the backport and
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
negatives and the replay rerun negative passed a 21-call calibration with three
agreeing, error-free samples per criterion. Earlier failed calibration attempts
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

The corrected-worker case-002 runtime passed all 14 repair assertions, but the
agent invented a publication command and failed its deterministic contract;
see [live results](live/README.md). Compact report and archive-hash fixes are
implemented; next run a fresh three-execution cohort with unchanged criteria, real Subctl
binary case-003 and refreshed blocked case-001. Runtime success and complete
skill accuracy remain separate measurements.

The live configuration permits a larger invoking-agent budget, but that budget
does not cap independent reviewer CLIs launched by the remediation scripts or
judge costs. See the live configuration for its execution and runtime deadlines.

## Live evidence and coverage

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
