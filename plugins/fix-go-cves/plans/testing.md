# Testing and evals

The plugin has three complementary layers:

- **Scripts:** `test/test-lib.sh` covers mutations, rollback and gates with about
  2,300 hermetic checks. Runtime changes need regressions here.
- **Historical replay:** the packaged admiral recording measures today's skill
  using a real pinned checkout, recorded scripts and output. One model trial has
  completed successfully; it does not validate today's remediation scripts.
- **Live evaluation:** today's skill and scripts run against a pinned real
  repository with its detected build/test commands and real Grype. Each live
  trial needs its own execution evidence; replay success does not establish it.

Live failures feed the faster layers: a script bug gets a hermetic regression,
and an interpretation mistake gets a replay case. User-requested live evaluation
now supplements the earlier manual Submariner release-branch runs.

## Current implementation

`make test` runs the shell suite, requires Go 1.24 or later, and fails rather
than skips when `CI` is set. The workflow uses `ubuntu-latest` without explicit
Go setup. The eval helper's unit checks are included through `evals/test_eval.py`.

The [eval README](../evals/README.md) documents setup, credentials, commands,
fixture contents and results. `evals/run.sh`, stock harness configuration and
`evals/scripts/eval.py` implement preparation, replay, state capture, final-reply
extraction and checks. The helper fetches pinned real history, restores the
recorded result bundle, stages historical scripts with today's `SKILL.md`, and
keeps judge annotations and reference answers outside the agent workspace.

The replay dry run retained the recorded `aa5a4fc` commit using a real GitHub
checkout. The first completed model pilot passed its deterministic contract and
the original fact judges. Manual review found incomplete next-step advice and
unsupported causality/risk claims. A stricter `action_owner` prompt now fails the
same reply in all three samples; the agent was not rerun and its original scores
remain preserved. Execution took 83 seconds, 18 turns and $0.53; judge calls were
unpriced, so total evaluation cost is unknown. A prior authentication failure
completed no task work and is not a behavioral trial.

The integration was exercised with agent-eval-harness at
[`1a980e707909a23f8c143ce333d97f5203db34ab`](https://github.com/opendatahub-io/agent-eval-harness/tree/1a980e707909a23f8c143ce333d97f5203db34ab).
Record the revision used by subsequent runs and recheck integration when it
changes. The stock runner's permissions and state/trace checks do not isolate
host files or credentials; stronger isolation belongs in the shared harness.

## Finish the replay pilot

Case 005's corrected reference identifies default-branch `8234df0` and puts the
backport on the target branch before rerunning: reruns start at `origin/<branch>`.
One negative omits the backport; another confines it to the generated fix branch.
Current-prompt calibration is complete: the reference passes both criteria, and
each negative fails its corresponding criterion in three agreeing, error-free
samples. The retained pilot also fails the stricter `action_owner` judge in
three agreeing samples. Calibration dollar costs were unavailable.

Next improve the skill's response completeness: state the actual remaining-CVE
and PR status, make remote-target repair before rerunning unambiguous, and avoid
unsupported causality or risk claims. Evaluate that change against the retained
pilot and its manual findings. A factual failure is useful evidence; do not
rerun an unchanged configuration merely to obtain a pass.

Keep this pilot small. Add more cases after preparation, loaded script/skill
hashes, per-case environments, one replay, retained state, reply extraction and
judge sampling are demonstrated. These now have pilot coverage; the three-round
acceptance baseline remains pending. Runtime fixes are independent of this pilot.

## Historical cases

Six source recordings are held locally under `.work/fix-go-cves-evals/source/`.
Only 005 is packaged; the other rows describe candidate follow-ups.

| Case | Recording | Decision | Status |
| --- | --- | --- | --- |
| 001 | lighthouse: license | Recommends devel's cdc3003 backport | Source recording |
| 002 | submariner: partial | Relays the PR; identifies who decides the image | Source recording |
| 003 | cloud-prepare: clean | Recognizes that flagged lines need no action | Source recording |
| 004 | subctl: `bin/lichen` | Avoids team escalation for the blocked bumps | Reference and binary evidence need correction |
| 005 | admiral: govet | Recommends devel's 8234df0 backport | Packaged; one completed pilot |
| 006 | lighthouse: x/crypto | Recognizes the spurious flag; recommends cdc3003 | Source recording; corrected reference needed |

For 004, the criterion must cover all three blocked bumps: x/net, grpc and
otel/sdk. Resolve the empty captured `bin/lichen` contradicting the recorded
log before admitting it; preserve evidence sufficient for diagnosis without
requiring a new live build.

For 006, the x/crypto flag followed a no-fix ignore of GO-2026-5932 and no
x/crypto finding remained. A passing reply says no further x/crypto action is
needed; blaming a Go raise or sending that flag to the team fails. Its license
failure also needs 001's backport criterion. Correct 001's rerun advice as for
005. Keep Go-raise policy scoring neutral while plugin and repository notes
disagree ([decisions](README.md#decisions)).

Package only evidence needed for a case. Preserve bundle commits and historical
script contents, sanitize home paths, and omit raw recording transcripts, which
contain unrelated connector, plugin and memory metadata. Include the log,
reference, negative, input and annotations; add captured reports or stubs only
when the case needs them. Extend the existing helper only for concrete cases.

## Scoring and acceptance

The deterministic contract checks retained state and allowed operations;
fact judges score diagnosis and action/owner using three samples each. Judges
receive final replies through fenced `outputs.files` values and authoritative
annotations. Replay extracts the final completed result rather than progress
commentary. A missing, errored or empty final reply is an error.

- Require every deterministic check to pass in three of three rounds, and every
  factual criterion to pass in at least two. A round runs every admitted case.
  Inspect per-case results; pooled rates can hide a consistently failing case.
- Missing, skipped or errored verdicts and incomplete samples are errors, never
  passes or factual failures. The helper checks complete sample counts and
  `stability.error_count`; `max_error_rate: 0` alone is insufficient.
- A case at exactly two of three on facts gets three additional trials on both
  the old and new configurations. Accept the change only if the new one does
  no worse, and inspect failures before attributing them to the change.
- Calibrate actual judge prompts on corrected references and negatives before
  trusting scores. Add one-fact edits, recorded wrong replies and a reply that
  asks the judge to pass it as concrete cases warrant. Repeat calibration when
  criteria, judge models or fixtures change; automate it after the pilot works.

The recordings helped tune `SKILL.md`, so these are regression cases rather
than evidence of generalization. Keep useful historical cases when runtime
scripts or the review prompt change. Add a current-output recording when a new
interpretation failure warrants one; revise an existing case when its expected
behavior changes or its evidence is wrong.

## Live evaluation and drift

The [live case index](../evals/live/README.md) tracks actual end-to-end trials.
Use `evals/run.sh --live` for this track, with its documented runtime prerequisites.
Do not replay logs, stub scanners, or replace repository build/test commands in
a live trial. Changing findings are expected: the Grype database and builder
images are external state, so score the observed outcome and supporting evidence
rather than demanding an old recording's commit or failure. Record timings,
execution cost, available judge cost and any environment blockers separately.

An optional weekly `scripts/report.sh` canary on one fast repository can later
catch scanner/database and builder drift, after report validation and scanner
deadlines are fixed ([operations](README.md#operations)). It should fail on
incomplete scans rather than findings; it supplements the full live evaluation.

## Later

- An optional manually started CI job, after the shared eval workflow's harness
  pinning, credential mounts and threshold handling are addressed.
- Per-trial container isolation with host-side model credentials, implemented
  in the shared harness rather than independently here.
- Direct `review.sh` eval cases if a mistake cannot be covered by replay or a
  live trial.

A with/without-skill comparison is not planned: without the skill, nothing
invokes the scripts. The redundant model verification layer has its own removal
decision ([decisions](README.md#decisions)); no separate eval is planned for it.
