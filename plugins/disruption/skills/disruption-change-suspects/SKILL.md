---
name: disruption-change-suspects
description: Use when looking for the code change behind a disruption regression or mechanism — lists every PR that landed between two release payloads, shortlists the ones whose description fits the mechanism and components, and reads their diffs. Also answers "what landed between payload A and B that could affect this backend?" on its own. Usually one step of a disruption investigation (see investigate-disruption).
---

# Disruption Change Suspects

This skill answers **what changed** between two points that could explain a disruption mechanism. It ranks suspects by how well each change fits the mechanism; it does not prove a change caused the regression. Proof needs a run with and without the change (a revert, or the fix landing).

## Prerequisites

1. **Python 3.7+** and network access to `*.ocp.releases.ci.openshift.org` (public).
2. **`gh`**, authenticated, to read PR descriptions and diffs. Without it, the PR list still works; say which PRs could not be read and give their URLs.
3. **For `payload_diff.py`:** the gcloud CLI when given `job:build_id` runs (it reads `prowjob.json` and `releaseinfo.json` anonymously from the public `test-platform-results-public` bucket), or `oc` when given a release pullspec.
4. **The `disruption_common` library**: the `disruption` plugin's `scripts/disruption_common`, installed with the plugin. If it is missing, `payload_diff.py` exits and says so. Report the message; do not work around it.

The scripts are in this skill's directory: `${CLAUDE_SKILL_DIR}` in Claude Code, or the directory containing this `SKILL.md` elsewhere.

## Rules shared by the disruption skills

- **Backend names are exact.** Use the names from the request or the state file's `series.backends`.
- **Platform.** A change limited to the alert's platform (a cloud provider's code, a platform-only component) is a suspect only with evidence that the mechanism is platform-specific. Say what that evidence is.
- **State.** `{investigation_dir}` is the state file's directory; without a state file, create `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/`.
- **One block.** Do not run another disruption skill yourself. End with the checkpoint below.

## Inputs

- **Two points to compare**, from the first of these that is available:
  - payload tags in one stream, such as `5.0.0-0.nightly-2026-11-07-182718` → `5.0.0-0.nightly-2026-11-09-184859`;
  - from the state file: the transition's `payloads.newest_target_before` → `payloads.oldest_target_after` (from `disruption-trend`), or the newest target payload in the before cohort → the oldest in the after cohort (from `disruption-find-runs`);
  - two runs (`job:build_id`), or run directories from `disruption-analyze-run`, for `payload_diff.py`.
- **The mechanism and components**, from `{investigation_dir}/comparison.md`, a run's `analysis.md`, or the request ("anything that could hit kube-api"). Without a mechanism, rank by the backends' API and say the ranking is weak.

For upgrade jobs, the change can come from the payload a run **started** from, not only the one it upgraded to (see the trend's `after_upgrades_by_initial`). When the evidence says so, compare the initial payloads too.

## Step 1: List every PR in the range

```bash
python3 "${CLAUDE_SKILL_DIR}/payload_prs.py" {older_payload} {newer_payload} --format text
```

It asks the release controller for the changelog across the whole range (one request, cached) and prints each updated component with its PR titles, PR URLs, Jira issues, and compare URL. Payloads from different streams (nightly and ci) cannot be compared this way; use `payload_diff.py` with two runs instead (Step 3). (`ci:fetch-new-prs-in-payload` lists the PRs new in one payload against its predecessor; this script covers any range of payloads in one stream.)

## Step 2: Shortlist by description

Read **every** PR title in the list. For each component and PR that could plausibly touch the mechanism, read the description:

```bash
gh pr view {number} --repo {owner}/{repo} --json title,body,files,mergedAt
```

A PR fits when its description or changed files touch the mechanism's component, resource, or trigger: for example, a write to the resource that starts a static-pod revision, a change to the probed API server's handling, a networking change on the probe path, or a change to etcd or node timing. Keep a short reason for every PR you keep and for every component you drop wholesale ("documentation and test-only changes").

## Step 3: Read the diffs of the shortlist

For each shortlisted PR, read its diff, or for a large PR only the files that touch the mechanism:

```bash
gh pr diff {number} --repo {owner}/{repo}
```

When the suspect is a component's commits between two runs rather than a PR list (different streams, or a component implicated by a revision trigger), read `references/payload-diff.md` and use `payload_diff.py --component`. It lists the commits and changed files from each run's release info.

Rank the suspects:

| Rank | Meaning |
|---|---|
| **Strong** | The diff changes the exact component and behavior the evidence shows (for example, it adds the write that `revision_triggers.py` found), and it landed inside the transition's change window. |
| **Plausible** | It touches the mechanism's component or path, but the diff does not show the exact behavior, or the timing is loose. |
| **Weak** | Same area, no link to the mechanism found. |

## Output

Write `{investigation_dir}/suspects.md`: the range compared and its source, the components and PR count, then each suspect with its rank, PR link, what the diff changes, and why it fits (or what is missing). End with what would confirm the top suspect: the first payload without it (to check the trend), a revert payload job, or a run comparison.

Answer with the ranked suspects, strongest first, and state plainly when nothing in the range fits the mechanism: the change may be outside the range (an older initial payload for upgrades, infrastructure, or test changes), or the mechanism is wrong.

End the turn with:

````text
```disruption-checkpoint
stage: suspects
state_file: <path to investigation.json>
summary: <one line: the range, the top suspect and its rank, or "no suspect fits">
next:
  - search Jira for <mechanism or suspect> (disruption-known-issues)
  - read <PR> in more depth
  - compare another range (initial payloads, or a wider window)
```
````

List only the options that fit. Then **stop and wait** for the user's choice, unless the request said to run without pausing (`--auto`, or "just run it"); then record the default (search Jira) and continue.

## Error handling

- **Different streams or a bad tag**: `payload_prs.py` says so. Compare two runs with `payload_diff.py`, or ask for payloads in one stream.
- **Release controller unreachable or HTTP 404** (a payload pruned from the stream): report it, and fall back to `payload_diff.py` with two runs.
- **`gh` missing or rate-limited**: list the PRs you could not read with their URLs. Do not rank a PR you only know by title above Weak.
- **More than about 50 PRs in range**: still read every title; read descriptions only for components related to the mechanism, and say which components were skipped and why.
