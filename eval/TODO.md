# TODO.md

Please keep iterating on the below task list and mark them complete when done.
Ensure all evals generated include skill activation judges, efficacy, etc. Use
your best judgement to optimize and analyze our peformance.

Do not ask me any questions; just keep iterating until done.  Produce a final report
to me of all below tasks in addition to individual artifacts.

Where possible, use dedicated subagents.

## Constraints

- **Session tarballs required**: Only consider payload agent jobs that have a
  recorded Claude session tarball in their artifacts (older jobs pre-date this
  feature and have no analysis to evaluate against). Look for
  `claude-sessions-*.tar` in the artifacts path.
- **Archives location**: Archives live at `../../archives` (outside the git
  repo) — currently `/home/stbenjam/git/archives/`. Do not store large
  artifacts inside the eval/ directory.
- **GCS artifact expiry**: GCS artifacts are garbage-collected after 30-90
  days. Prioritize archiving recent jobs first; older ones may have partial or
  missing data.
- **Eval cases in git, archives not**: Case definitions (input.yaml,
  annotations.yaml) go in `eval/cases/` and get committed. Large GCS artifact
  archives stay outside the repo.
- **Subagents must implement, not plan**: When delegating to subagents,
  explicitly instruct them to write code and create files — not produce
  plans. They should use Write/Edit tools to create actual artifacts.
- **Do not fill up the disk**: `/home` is 126 GB total with ~65 GB free.
  Use `gcloud storage cat` to read files in-place rather than downloading.
  Only download artifacts needed for eval cases. Check `df -h /home` before
  bulk downloads.

## Tasks

[x] Task 0: Compress archives for cold storage

Add transparent compression support to the eval framework. Each payload
archive (`../../archives/{payload-tag}/`) should be compressible into a
single `.tar.gz` for cold storage. The gcloud shim should transparently
extract a compressed archive on first access — if the directory doesn't
exist but a `.tar.gz` does, extract it automatically. Add a companion
`eval/scripts/compress-archives.sh` script to compress all uncompressed
archives. This frees disk space when archives aren't actively in use.

[x] Task 1: Analyze payload agent jobs.

We have a large volume of data here in payload agent jobs:

* https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-release-main-claude-payload-agent/

Many just exited 0 because the payload got accepted, but there are many
rejected on infrastructure, flakes, etc.  It would be interesting to find all
the jobs that ran on rejected payloads (it produced a report, didn't exit 0).

* Identify those with high confidence reverts where the PR was actually reverted in the end

* Identify those with high confidence reverts where the PR was *NOT* reverted in the end

Produce a comprehensive report with artifacts showing this, and come up with
ideas on 5-10 of these candidates to build useful evals on.

Also find ways we could use /eval-optimize to improve results, identify which
payloads we could build evals on, etc, and also recocmend ideas I may not have
thought about.

[ ] Task 2: Improve the payload agent

Based on the information above, in a git worktree, run /eval-optimize and
improve the performance of the various payload agent skills.  Consider
implementing things like progressive discovery to reduce initial context load,
or other techniques.  When you have improvements, open a PR to ai-helpers from
your worktree based on the upstream/main.  Do not touch $PWD, it is our working area for evals.

[x] Task 3: Install job failures

I would also like to add an eval specifically for just one off job failures, we
can start with insatll: /ci:analyze-prow-job-install-failure on
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-main-nightly-4.22-e2e-metal-ipi-ovn-ipv6/2026582867877826560

This PR was ultimately the root cause which we reverted
https://github.com/openshift/cluster-kube-apiserver-operator/pull/2032, but in
this case I'm interested to see if it can identify the exact problem reliably.

Have a subagent go off independently and create an eval for this specific one.

[x] Task 4: Other job failures

Find individual job failures from the payload agent, and write evals for those
similar to the install job failures above.

[x] Task 5: Think outside the box

Based on the outputs of the other tasks, especially task 1, decide on ways we
could improve.

Our goal is more green payloads. Why are we struggling?

[x] Task 6: Trim archive sizes

The current archives total ~65 GB. Create a script that reduces archive size
while preserving a realistic artifact tree structure. The skill must still
navigate unrelated files — stripping to only accessed files would make the eval
unrealistically easy and fail to catch cases where the skill goes off the
rails. Approach: remove the heaviest files the skill never reads (prometheus
tars, audit logs, large e2e-events JSON) but keep the directory structure and
smaller files intact so `gcloud storage ls` returns realistic listings. Goal:
get a full eval archive set under 10-15 GB.

[ ] Task 7: Rerun evals after improvements

After Task 2 produces skill improvements, rerun the full eval suite against
both the baseline (current) and improved skills. Compare with
`--baseline <old-run-id>` and produce a before/after report showing whether
analysis_quality and revert_scoring_accuracy improved, especially on case 008
(the persistent weak point).
