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
detected commands and scanners. The live case uses local remotes and never
publishes changes.

Optionally export absolute `GRYPE_DB_CACHE_DIR` and `GOMODCACHE` paths outside
the evaluated checkout to reuse host caches. These apply to local Grype and
host Go; container caches are separate. Unset variables retain default behavior.

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

The runner prints workspace and result paths. Results default to
`.work/fix-go-cves-evals/runs/fix-go-cves:fix-go-cves/<run-id>/`; override the root
with `AGENT_EVAL_RUNS_DIR`. Inspect the extracted `output/reply.md`, captured
`output/state.json`, event logs, metrics and judge results under each case.
The harness also writes its standard `report.html` in the result directory.
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

Calibration is complete for the current prompts: the corrected reference passes
both criteria; the missed-backport negative fails `backport`; the fix-branch-only
negative fails `action_owner`. Each result has three agreeing, error-free samples.
A focused skill update now requires explicit remaining-CVE/PR status, the
remote-target repair before rerunning, and evidence for causality. Its first
trial passed the contract and both current fact judges, each with three agreeing,
error-free samples: 79 seconds, 15 turns and $0.49 for agent execution. Manual
review still found unsupported claims about unrelated causality and unchanged
behavior. This is not complete response accuracy or the three-round acceptance
baseline; further work remains.

The live configuration permits a larger invoking-agent budget, but that budget
does not cap independent reviewer CLIs launched by the remediation scripts or
judge costs. See the live configuration for its execution and runtime deadlines.

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
