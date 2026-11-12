# Payload Diff: Which Commits Changed a Component

Use this once a component is suspected (from a revision trigger, a timeline signal, or the
cohort comparison), to list the commits between a run or payload without the behavior and
one with it.

## Run it

```bash
# Every repo whose commit differs between the two payloads
python3 "${CLAUDE_SKILL_DIR}/payload_diff.py" \
  {runs_dir}/{build_id_before} \
  {runs_dir}/{build_id_after}

# Commits and changed files for one component (release tag or repo name)
python3 "${CLAUDE_SKILL_DIR}/payload_diff.py" \
  {runs_dir}/{build_id_before} \
  {runs_dir}/{build_id_after} \
  --component cluster-authentication-operator
```

## What each side can be

Each side can be a build dir with `gather/releaseinfo.json` (from `disruption-analyze-run`'s
`download_timelines.py --gather`), a
`releaseinfo.json` path, `{job_name}:{build_id}` (the script downloads that run's
gather-extra `releaseinfo.json` anonymously into `{output-dir}/{build_id}/gather/`; pass
`--output-dir {runs_dir}` so it lands beside the investigation's other runs), or a release pullspec (the
script runs `oc adm release info -o json -- {pullspec}`, or prints that command when `oc`
is missing).

## Where the commits come from

The commit for each component is
`references.spec.tags[].annotations["io.openshift.build.commit.id"]` and the repo is
`io.openshift.build.source-location`. With `--component`, the script runs
`gh api repos/{owner}/{repo}/compare/{before}...{after}` and prints the commits and
non-vendor files (`--include-vendor` shows vendor/). If `gh` is missing or fails, it
prints that exact command and the GitHub compare URL; run it yourself or open the URL.
GitHub's compare lists at most 300 files; when it hits that limit the script says the list
may be incomplete, so read the full diff before ruling the component out. A repo name that
builds several tags with different commits (for example `kubernetes`) is rejected; pass the
tag instead.

## Caveats

- gather-extra `releaseinfo.json` is the payload the cluster ran at the end of the job,
  which is the **target** payload for an upgrade job. Comparing two runs' build dirs
  compares their targets.
- For upgrade jobs the trigger often depends on the **initial** payload as well (for
  example, a change that rewrites a resource only when upgrading from a payload without
  it). Check each run's payload pair (from the cohorts or the run analysis), and pass the
  `RELEASE_IMAGE_INITIAL` pullspec as a side when you need the initial payload's
  commits. Do not state which payload a run started from without checking.
- GitHub's compare lists at most 250 commits; the script says so when it truncates.
