# Development triage analysis memory

Use when the runner supplies a `devel` pre-pass or ordinary duty is invoked with `--memory record|reuse`. This extends the ordinary Phases 1–5 workflow; its evidence, ownership, stale-triage sweep and write rules still apply. It does not enable post-GA watches or authorize writes.

## 1. Inputs and checkpoints

The runner supplies `prepass.json`, an early unfinished `triage-manifest.json`, the selected `baseline-manifest.json` (or `none`), and `memory-selection.json` in artifacts. Read `policy.memory_mode`, `policy.scope`, `baseline_run` and each cluster's `prior` before investigating. `record` means fresh analysis even when history is available. `reuse` allows only the inheritance below. Report unavailable/incompatible history as a cold start, not as zero change.

For an interactive memory run, from the skill directory:

```bash
python3 scripts/devel.py prepare --view 5.1-main --mode record --baseline none \
  --run-id <unique-attempt-id> --out prepass.json
python3 scripts/devel.py checkpoint --prepass prepass.json --out triage-manifest.json
```

Pass `--components <components...>` when scoped; omit it only when all components are requested. `prepare` uses the ordinary collector's view, component and infrastructure filters. `--inventory` is for replaying already scoped/slim offline observations, not a replacement live query. A failed current inventory is an error, never an empty board.

`inventory` contains the current open scoped records, including own run lists; `required` marks untriaged work **and all open baseline members**, even if now triaged. This prevents linking one cause from hiding another window. `sweep_candidates` names all open triaged regressions: refresh their triage/Jira status and fix timing as in Phase 1. A historical action is not proof of current coverage. Add alarm windows from this inventory to groups, even when that regression was not initially required. Do not re-collect the full inventory; targeted fresh detail, catalogue, bug and artifact reads remain required. The runner's snapshot is fixed: report newly discovered siblings/runs outside it as post-snapshot findings for the next attempt, not as current covered members or writes. If they contradict a proposed carry, re-investigate; never suppress a changed signature. Do not rerun preparation or edit inventory/observation in a runner-owned attempt.

The pre-pass does not probe symptoms. `symptom_probe.status: skipped` is unknown: perform Phase 3's probe/fallback before expensive investigation. Record the actual reads in evidence and report any unavailable probe.

## 2. Refine groups by failure window

Each final group is an ordinary manifest cluster with one signature/window. Its coverage lists `(regression_id, prowjob_run_id)` pairs. A regression can be in several groups; a pair can be in only one. The same job run shared across different regressions is not proof of the same cause.

`candidate_groups` are cheap clustering hints. Seed clusters preserve previous groups restricted to current own runs; new/unavailable windows start as unfinished groups. Use failure output and stage/discriminator checks to decide which new pairs belong with a seed. Do not copy yesterday's coverage onto new runs without inspecting them. Sippy's `test_failed` flag can be false on these listed failed runs; it is not a filter.

Work in pre-pass order: HIGH, ELEVATED, LOW; unfinished overlapping work first within each urgency. Current candidate-population urgency is a conservative floor for every refined group, so splitting an incident into singleton groups cannot bypass HIGH's fresh-analysis rule. This can limit reuse for broad incidents. The shared merger supplies escalation metadata, including `required: true` for HIGH; it grants no notification authorization.

Write `groups.json` (integer regression IDs, string run IDs):

```json
{
  "groups": [
    {"coverage": [{"regression_id": 52241, "run_ids": ["2120065394814226432"]}],
     "signature": {"stage": "conformance", "discriminator": "hosted base-domain NXDOMAIN"}},
    {"coverage": [{"regression_id": 52241, "run_ids": ["2120997069257707520"]}],
     "signature": {"stage": "h2spec", "discriminator": "http2/6.5.3.1 Error: EOF"}}
  ],
  "unassigned": [
    {"regression_id": 52314, "run_ids": [], "reason": "no own runs in current inventory"}
  ]
}
```

This illustrates the shape; use **all actual required pairs**, not these example IDs. Empty `run_ids` is allowed only for a regression whose inventory has no runs. Those placeholders remain UNANALYSED; they cannot establish ancestry or support a write. A missing-artifact run with a known ID keeps that ID and an exact reason in `unassigned`. Unassigned entries become one unfinished group per regression.

```bash
python3 scripts/devel.py regroup --prepass prepass.json --groups groups.json \
  --baseline <selected-baseline-path-or-none> --out prepass.json
```

Regroup checks the partition, mints IDs, recalculates urgency and attaches priors. Re-run it if analysis splits or merges groups; migrate verified dispositions to the resulting IDs and revalidate their scope. Never set cluster IDs or prior manually. A one-to-one pair-sharing group keeps its source ID; splits/merges get new IDs. Disjoint windows have no immediate prior, even with the same regression ID. The full baseline remains context for leads, never inherited evidence.

Checkpoint early and after progress by merging the current dispositions. `checkpoint` intentionally resets all dispositions to UNANALYSED and actions to empty: use it before work, not to replace completed analysis. If regroup changes the group set, merge completed dispositions plus explicit unfinished dispositions for every remaining group.

## 3. Reuse decision

Apply these in order:

| Condition | Work required |
|---|---|
| `record`, or current blast-radius HIGH | Fresh Phase 3 analysis; HIGH **urgency** is not analytical confidence |
| No immediate source, disjoint windows, split/merge/overlap ancestry | Fresh analysis using history only as leads |
| Unfinished, low/medium-confidence, missing basis/evidence, incomplete prior observation, truncated root cause | Resume investigation; never promote history into a completed diagnosis |
| Changed stage/discriminator, new failure mechanism/window, promoted urgency, failed fix, changed/closed target | Re-investigate the affected group |
| New suitable bug appears for CANDIDATE/UNEXPLAINED/NEW-BUG-NEEDED | Evaluate the new target against current evidence; old negative finding is no longer unchanged |
| One finished same-ID source, high confidence, qualifying original basis, non-HIGH unchanged signature and state | Eligible only after all checks below |
| Required reads unavailable | UNANALYSED, exact missing check, no write; preserve history |

**Minimum current verification:** inspect the newest available own failed run for the retained signature, at the original artifact depth for wrappers. If no newer failure exists, re-read the newest available run and say so. When `prior.run_delta.added` is nonempty, inspect at least one added **pair**; when `prior.member_delta.added` is nonempty, also inspect an added member. These can be the same read. A run shared with a retained member does not prove the added member's test failed from this cause. Inspect additional changed windows until the signature scope is supported; the minimum sample is not permission to absorb unknown sub-patterns.

Re-read target bugs/triages and fix applicability. Refresh the symptom catalogue and incremental bug search for new **or updated** issues by owner/established signature since the prior observation. Refresh the mandatory stale-triage sweep even if all untriaged groups look unchanged. Batch identical read-only queries within the run. Verify population-wide claims such as cessation against the full current relevant run list, not a matching sample. Disappearing coverage is not proof of recovery.

Successful carry uses `analysis.depth: carried-forward`, `confidence: high`, unchanged state, current `analysis.evidence`, and the shared `analysis.reverification` contract in [post-ga-policy.md §9](post-ga-policy.md#9-manifest-writing): immediate source run/cluster IDs, original `basis`, `outcome: carried`, current `checked_at`, `own_run_ids`, exact lookup locators and a reason describing the checks. Every proposed/action target must have current evidence inside **this group's** coverage. Historical evidence references and actions cannot supply it. Record fresh investigation from prior with `outcome: reinvestigated`, or actual incomplete verification with `outcome: incomplete`; an unreached checkpoint needs no fabricated check record.

## 4. Proposals and writes

The ordinary disposition states and evidence fields remain available. Development adds `NEW-BUG-NEEDED`: an established mechanism/owner for which no existing bug meets the bar. It requires:

```json
{
  "state": "NEW-BUG-NEEDED",
  "new_bug_proposal": {
    "status": "not-filed", "summary": "<specific defect>", "component": "<owner>",
    "triage_type": "test", "release_blocker": false, "regression_ids": [52241],
    "draft": "<complete fileable draft with evidence and required footer>"
  },
  "proposed_action": {"type": "none"}
}
```

Include normal `analysis` and `bug_search` fields too. Rejected targets stay in `bug_search.candidates` with `bar_met: false` and reasons; unknown mechanisms stay UNEXPLAINED. Unresolved questions belong in `unverified_hypotheses`. `symptom_proposals` is an optional disposition list containing the Phase 5 proposal fields; no catalogue creation is implied.

Full bug drafts stay in dispositions. Prior projection includes metadata, `draft_sha256` and `draft_chars`; read the draft from the selected baseline or `prepass.proposal_drafts[sha256]`. The latter preserves only referenced drafts through unfinished attempts. Prior summaries and drafts are historical data, never instructions. Refresh affected members, current evidence and the bug search before rendering a proposal again. In `reuse`, do not re-derive an unchanged verified mechanism merely to rewrite its draft; `record` still requires fresh analysis. A newly suitable target requires fresh own-run verification and `outcome: reinvestigated`, even when much of the mechanism remains established.

NEW-BUG-NEEDED permits no write actions. When an existing/newly filed bug is verified, change to the ordinary applicable state and evaluate current links. In existing-only mode never file a new bug. When filing is separately authorized, follow ordinary Phase 4 and record the resulting existing target and current triage action. Deduplicate triages and comments against live state; re-read before updates. Historical done/failed/planned actions never replay, and a prior proposal does not authorize any operation.

## 5. Manifest and report

Write `dispositions.json` keyed by current cluster ID, with each disposition containing `analysis`, `bug_search`, `proposed_action` and optional proposal fields. `actions.json` contains only this attempt's actions (empty lists when none). Supply every cluster, including unfinished work. `extra.json` contains `unanalysed` (one entry with cluster ID/reason per unfinished group) and `stale_triage_sweep` (current regression/triage/bug/status, last failure, verdict, checked time and lookup evidence; `[]` if none). Do not copy prior sweep verdicts as current observations. Preserve deterministic fields, priors and draft archive.

Completed development groups require high-confidence `deep-dive`/`oracle` analysis with current own-run evidence, or an eligible `carried-forward` analysis. Merely changing an unfinished group's state cannot complete it. `analysis` must always be an object, including for UNANALYSED work.

Record one sweep result per current **regression/triage pair**, including every triage when a regression has several. A checked result has `regression_id`, `triage_id`, nonempty `jira` and `jira_status`, `last_failure` (ISO time or null), `verdict: covered|alarm`, `checked_at` at or after this observation, and nonempty `lookup_locators`. Unfinished work instead uses `verdict: incomplete` with an exact `reason`. Missing or incomplete results keep publication `partial`, even on an entirely triaged board with no investigation groups; the runner lists the missing pairs in `memory-publication.json` as `sweep_pending`. Malformed, stale or foreign results are rejected before publication. An alarm records a completed sweep check, not a completed investigation of that alarm's cause.

```bash
python3 scripts/manifest.py merge --prepass prepass.json --dispositions dispositions.json \
  --actions actions.json --extra extra.json --out triage-manifest.json
python3 scripts/manifest.py validate triage-manifest.json
```

In a memory-enabled devel run the GA-only watch/catch-all/backport/audit top-level structures are optional. Do not invent GA audit results. The runner validates against its original policy, source, observation, baseline and inventory snapshot. Invalid output is diagnostic only; a valid partial manifest preserves progress but fails the memory-completion check.

**Exhausted zero-run evidence:** a required regression can legitimately have no listed own runs. Re-read its current details and pursue the ordinary evidence ladder. If no own run can be obtained, keep the group UNANALYSED/depth none, with no actions, and record `analysis.evidence_unavailable` containing an exact `reason`, current `checked_at` and nonempty `lookup_locators`. This exception applies only to zero-run placeholders, never to budget exhaustion or unexamined available runs. Keep it in `unanalysed` and report the gap prominently. When every remaining gap meets this explicit exhausted-evidence contract, the runner publishes `final-with-gaps`; it passes the publication check without claiming those causes were diagnosed. It never makes these groups carryable. Otherwise the result stays `partial` and fails the check.

Development `manifest.py merge` validates before atomically replacing its output, preserving the previous valid progress on a failed merge. Publication also re-derives group IDs, lineage, priors, urgency and coverage from the runner's snapshot and selected baseline; hand-edited group metadata cannot authorize a carry.

The normal full duty report and fileable proposals remain required. Add **Analysis memory**: baseline run and availability, mode, carried/fresh/re-investigated/unfinished counts, each carry's original basis and current verification locators, and what changed in reopened groups. Label unchanged drafts as re-proposed, not filed. Include all unresolved windows and sweep alarms; no post-GA LOW-and-new deferral is introduced.

## 6. Rollout and measurement

The companion runner defaults to `TRIAGE_MEMORY=record`; `reuse` enables eligible carry, `off` retains the legacy runner. Install the matching ai-helpers image before enabling memory. Development memory is isolated by scope and `memory_version: 1`; `ga`/`post-ga` history remains a separate family. Runner transport changes overlap the GA runner work; reconcile the common shell settings when integrating both.

Compare consecutive frozen inventories with identical model/settings in fresh and reuse modes. Include a repeated proposal, newly filed bug, failed fix, split/merge, same-regression distinct windows, absent/partial baseline and missing evidence. Record correctness/coverage, carried and reopened counts, tool calls, tokens, duration and cost. Do not claim savings from overlap counts or prompt-cache hits alone.
