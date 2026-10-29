# Post-GA policy (`--policy post-ga`)

Rulebook for the weekly post-GA run. Read after SKILL.md. Phase 3's evidence and mechanism discipline applies to fresh analysis; §3a defines when verified prior analysis satisfies its depth requirement by inheritance. The explicit watch and UNANALYSED outcomes below remain valid post-GA outcomes. Authentication, the AI-attribution footer and Existing-only mode are defined in SKILL.md and are not repeated here.

## 1. Purpose and scope

- Views: the seven `-main` views `4.16-main` … `4.22-main`, in one run.
- Goal: surface significant, widespread issues quickly (a `HIGH` cluster pages the duty rotation), link clusters to existing bugs only when the evidence bar is met, and keep everything else quiet but remembered across runs (lineage, watch list, and previous analysis in prior). Zero untriaged is **not** the goal: a small unexplained `LOW` cluster that stays untriaged but listed is a fine outcome.
- Work per **cluster**, never per regression. Closed regressions are evidence only, never work items.
- Existing-only: **never create a Jira issue.** Also no code-fix PRs, release-blocker flags, transitions, or Sippy label/symptom creation (recommend only).
- Two independent axes: **evidence decides writes; blast radius decides notification.**
- Outputs: `triage-duty-report-post-ga.md` and `triage-manifest.json`.

## 2. Phase 0 inputs

`prepass.py --views V... [--now ISO] [--baseline PATH|none] [--no-oracle] [--token-env DPCR_TOKEN] [--inventory PATH] [--run-id ID] --out prepass.json`. If `prepass.json` is absent or a view's `fetch` is not `complete`, say so in the report; an empty or failed fetch is never a clean board. Fields you use per cluster (clusters are sorted HIGH → ELEVATED → LOW; within a level, clusters whose immediate prior source was left unfinished and still shares members come first, then score descending, then id):

- `id`, `lineage`, `fingerprint`, `members` (regression ids, `new_since_baseline`, views, components), `shape`. In `shape`, `days_open` counts from the regression's (re)activation in the view — Sippy resets it when a test recovers briefly and regresses again — and is the rules' input; `regression_days_open` counts from Sippy's regression-level `opened` and is the age to quote in prose. Do not recompute either.
- `blast_radius{level,score,reasons}`.
- `oracle{status,runs_probed,labels,label_bugs,error}`; `observation.symptom_probe.status ∈ ok|unauthorized|failed|skipped`. Anything but `ok` is **unknown**, never "no symptoms matched": use the SKILL.md fallback ladder. A `failed` probe may still list `labels` — a label that fired on a run is positive evidence you may use; the empty remainder is unknown. `label_bugs: null` means the label→bug catalogue could not be read: look the labels up yourself (`list-symptoms`, public endpoint) before concluding a label has no bug.
- `prior`: the preceding attempt's sources, or null. Read it before investigating. Immediate sources have `history_only: false`; their run/time is the latest baseline's. If an immediate source is unfinished, older useful snapshots may be retained with `history_only: true` and their original run/time. Those are context only: they never establish successful re-verification or automatic carry. Preserve this deterministic block verbatim in the manifest.
- `prior.member_delta.added` and `.removed` compare current members with immediate source members only. Retained snapshots do not affect deltas or urgency. Removed members may have moved, been linked, or left the inventory; disappearance proves none of those explanations. In a split, another child's members appear as removed.
- Compare the prior/current oracle's label sets and label→bug mappings, not its run-ID keys. A different sampled run is not itself a changed mechanism. A changed label requires a discriminating check against the regressed test; a label on another testcase is not evidence for this one. An unavailable probe/catalog remains unknown: use the Authentication fallback ladder and record the lookup/artifact that establishes the relevant signature.

Clusters are hypotheses. You may split one when signatures differ; record it in `lineage`.

A null prior with an absent or incompatible baseline means this run starts without analysis memory; say so in the report. With a compatible baseline, a null prior means no source was found for that cluster. Non-null but incomplete history is still useful as a lead; do not label it inherited analysis. Never fetch an older successful run to replace the latest preceding attempt. Read APIs for targeted verification and current own-run membership as needed; the Phase 0 prohibition is on re-collecting the inventory, not on checking evidence.

## 3. Blast radius and disposition

**Blast radius** (urgency; computed by the pre-pass, do not recompute):

- `HIGH` (any): ≥8 regressions ∧ ≥4 distinct jobs ∧ ≥2 lane families ∧ (≥2 platforms ∨ ≥2 arches); or any upgrade lane (minor or micro) ∧ ≥2 platforms ∧ ≥6 regressions ∧ ≥3 jobs; or persisting (open >7 d ∧ last failure ≤2 d ∧ ≥3 failing own runs in 7 d) ∧ ≥8 regressions ∧ (≥2 distinct jobs ∨ open >14 d).
- `ELEVATED` (any): ≥12 regressions; ≥3 distinct jobs; install/bootstrap wrapper on ≥2 platforms; permafail shape (≥30 failed runs over ≥14 d); single-job mass failure persisting >7 d.
- `LOW`: everything else.
- A single-job mass failure (`mass_failure_marker`) caps at `ELEVATED` unless the lane has been dead >14 d.

`blast_radius.THRESHOLDS`: `{"persist_min_days_open": 7, "persist_max_days_since_last": 2, "persist_min_failing_runs_7d": 3, "persist_min_regressions": 8, "persist_high_min_jobs": 2, "persist_high_min_days_open": 14, "high_broad_min_regressions": 8, "high_broad_min_jobs": 4, "high_broad_min_lane_families": 2, "high_broad_min_spread": 2, "high_upgrade_min_platforms": 2, "high_upgrade_min_regressions": 6, "high_upgrade_min_jobs": 3, "elevated_min_regressions": 12, "elevated_min_jobs": 3, "elevated_install_min_platforms": 2, "elevated_min_runs": 30, "elevated_min_days_open": 14, "score_regressions_cap": 50, "score_jobs_cap": 10, "score_lane_families_cap": 5}`

**Disposition state** (cause; you assign it, one per cluster):

| state | meaning | path |
|---|---|---|
| `KNOWN-CAUSE` | a fired label names a bug, or a related triage has sibling-release precedent | verify the bug's signature on ≥1 own run → extend/link |
| `CANDIDATE` | a plausible bug exists, bar not yet met | deep-dive → link, or escalate/report |
| `UNEXPLAINED` | no bug | `HIGH`/`ELEVATED` → escalate (mention only for `HIGH`); `LOW` ∧ new → watch one cycle; `LOW` ∧ persisting → needs-human (low) in the watch list (catch-all admission is off by default, §4) |
| `UNANALYSED` | analysis or verification unfinished (budget, or a required §3a check that could not be completed) | listed prominently with reason; no write |

Every cell has a no-write fallback. Persisting unexplained `LOW` work — singleton or small cluster — is "needs-human (low)" in the watch list, not a write.

### 3a. Start from prior analysis; re-investigate changes

Inherit analysis only from one finished immediate same-id/supersedes source with shared members, complete observation, high confidence, an untruncated summary and qualifying deep-dive/oracle basis. A previously carried analysis needs its recorded basis and successful last-run verification. Retained history-only snapshots, unfinished work, triage-only/none depth, missing evidence and low/medium confidence are leads, not inherited depth. Treat legacy malformed candidate/action facts as unknown rather than rejecting the historical manifest or upgrading their meaning. An examined CANDIDATE/UNEXPLAINED may be high-confidence about its signature and no-link finding without claiming a known cause.

**Minimum for carry:** inspect at least one newest available failed own run per retained signature group, at the original artifact depth for wrappers; confirm the actual testcase, stage and discriminators. Select from current member run lists, not a job-name sample. If no newer failure exists, re-read the newest available own run and say so. Re-read relevant target bugs and triages for existence, status and fix applicability; check the catalogue before repeating a create proposal. For candidate/unexplained work, search new/updated bugs since the prior observation by owner or established signature. A newly suitable bug invalidates the old negative finding and gets fresh gate evaluation. Record run IDs, inspected lookup locators and results in the verification reason. Batch/cache read-only lookups where useful; do not invent target checks when there is no target. Whenever `prior.member_delta.added` is nonempty, additionally inspect at least one added member's own failed run. This applies regardless of net membership shrinkage or decreased urgency. Every proposed link still requires current support for its target member.

A matching sample inherits only the previously established signature scope. It cannot absorb unresolved sub-patterns or prove that every run has the same cause. If the prior records mixed signatures, gaps relevant to current members, or ambiguous ownership that prevents this check, investigate those gaps. New failure windows on an existing wrapper member require fresh artifact verification even when no member was added. Unavailable evidence or lookups make re-verification incomplete, never successful by default.

Apply the table in order, with failed required verification overriding a proposed carry. Carry includes the minimum reads above; re-investigate starts from recorded leads. Treat-as-new uses ordinary urgency/watch rules and does not require a LOW-and-new deep-dive. This exception changes repeated analysis, not the per-member evidence bar.

Missing source run/time or incomplete prior observation disqualifies carry, but does not erase readable unfinished/deferred status or established member continuity.

| prior state / continuity | what changed | action |
|---|---|---|
| any | current urgency is HIGH, including unchanged prior HIGH | fresh Phase 3 deep-dive; never `carried-forward`; keep escalation required |
| no immediate source | baseline absent/incompatible, or no matching source | apply ordinary current urgency/watch rules; report missing memory, not zero change |
| any | `prior.relationship` is `same-id` and its sole immediate source has empty `matched_member_ids` | treat population as new; retain the family hypothesis (the old bug may stay a lead) and never transplant old member coverage |
| any | `prior.relationship` is `split`, `merge` or `overlap` (a merge may include a same-id parent with no shared members beside an overlapping one) | re-investigate current signature groups; read all source decisions, choose no source by majority, keep conflicting targets separate |
| unfinished immediate source | shared members still present, with or without retained useful history | analyse first within current urgency, starting from all useful context; no automatic carry |
| LOW-and-new watch, not subsequently analysed | same members persist | first analysis is due; a view-age reset is not another automatic watch cycle |
| analysed but ineligible history | missing source identity/time, incomplete prior observation, low/medium confidence, missing basis/evidence, unsupported depth, or truncated summary | re-investigate from the recorded leads; never upgrade incomplete history by inheritance |
| any analysed state | urgency rises across a level boundary | re-investigate, even with no new member IDs; urgency comes from the current pre-pass |
| any analysed state | bug newly closed/resolved, triage newly resolved/retargeted/missing, or current failures after a fix shipped to this release | re-investigate fix timing and current signature; no inherited link; do not reopen or transition anything |
| CANDIDATE/UNEXPLAINED | new suitable bug or evidence changes the old bar decision | evaluate the new lead/gate; do not preserve the old no-link finding as unchanged |
| any analysed state | relevant label/label→bug, failure stage, assertion, platform/variant scope, or other mechanism signal changed | re-investigate affected signature/member group; if a changed label is proven incidental to this testcase, record that discriminating check and use the applicable unchanged/growth row |
| KNOWN-CAUSE | no new members, same supported signature and target applicability | carry cause/owner/type; re-propose or perform only current-evidence-supported links through §4 |
| CANDIDATE | no new members, same missing bar, target/search checks unchanged | carry the no-link decision and caveats; do not turn last week's plausible match into a link |
| examined UNEXPLAINED, including needs-human watch | no new members, same signature, incremental search still negative | carry the negative finding; keep its watch/needs-human outcome, not first-analysis backlog |
| any qualifying analysed state | new members, no upward urgency change, and unchanged mechanism signals | carry only after signature verification on at least one new member's own run in addition to each retained signature group; support every proposed member under §4, otherwise leave it unlinked |
| any qualifying analysed state | no added members; membership shrank or urgency decreased, with unchanged remaining signatures | carry after checking a retained member; restrict coverage/watch entries to current members; make no recovery claim |
| any | a required verification cannot be completed | current UNANALYSED with the exact missing check; preserve the prior as history, no write |

An already-closed bug/resolved triage may remain applicable when its fix never shipped to this release; re-confirm and preserve status under §4. Unknown applicability or contradictory new failures require investigation. Historical done with missing current membership requires a live two-sided check; it is not automatic coverage or a replay instruction.

Successful carry satisfies SKILL.md's mandatory depth requirement **by inheritance plus current own-run verification**. Record `analysis.depth: carried-forward`, `confidence: high`, the unchanged disposition, and `analysis.reverification`. Do not claim a fresh deep-dive, upgrade low-confidence history, or mark an unresolved sub-pattern as explained. A current HIGH always receives fresh analysis, even when its prior appears unchanged.

## 4. Write policy

**Linking gate.** Write a triage only when the target bug's stated failure signature — its **exact failing assertion** or discriminators — is **verified in ≥1 of the cluster's own runs**, *or* the mechanism matches exactly with **sibling-release precedent**. The bug supplies the signature; you establish the own-run evidence from the artifacts (a pre-existing bug cannot cite runs that happened after it was filed — a bug that does cite one of our runs is the strongest form of this evidence, not a precondition). Titles and keyword matches are not enough. A label or sibling precedent only *identifies the target*; `KNOWN-CAUSE` needs the same gate per supported member (a validated symptom firing on a member's own run counts as that member's own-run evidence). Gate not met → `CANDIDATE`.

**Memory is not a linking gate.** Prior `bar_met`, evidence references, proposed actions, and completed actions are historical. This run's `analysis.evidence` must contain actual observations read this run from the current members' own runs, with `prowjob_run_id` and `supports_regression_ids`. Every intended link, including a report-mode proposal, must be supported there; a shared run supports multiple members only when their test/signature evidence actually matches. Keep uncovered current members in `members.unlinked`. Never copy the prior's member list into an evidence item or action to manufacture coverage.

**Re-propose from memory; write through the current gate.** Reuse a still-verified target/rationale, check for an existing triage, and generate current actions for supported members. In report mode use skipped-report-mode and "re-proposed; not written". In auto, including report→auto, verify this week's gate per member, perform the immediate pre-PUT re-read/two-sided verification and record this run's result. Historical done/failed/skipped actions never replay. Missing current membership requires a live check before the ordinary gate applies.

- **Evidence membership.** Each evidence item records `prowjob_run_id` and `supports_regression_ids[]`. `proposed_action.regression_ids` must be a subset of the union of those. Members not covered go to `members.unlinked[{id, reason}]`; split the cluster if signatures differ. Own-run evidence only (Case 10).
- **Extend, don't duplicate.** Before proposing `create_triage` for a bug, look it up in the public triage catalogue (`GET https://sippy.dptools.openshift.org/api/component_readiness/triages`, no token; Phase 0's inventory restriction does not cover this) — a triage whose `url` carries the bug key is the target even when it is `resolved`: propose `extend_triage` with its id (resolution is preserved on PUT) and, if the fix never shipped to this release, add the `backport_candidates[]` entry. Several clusters linking the same bug share one triage. Additive. Re-read the triage immediately before every PUT; resend `url/type/description/resolved/resolution_reason` (full-record replacement) with `+00:00` timestamps; verify from both sides. Record the re-read in `precheck`.
- **Sibling-release lookup.** Search triages in newer views (`4.(n+1)-main`, `5.0-main`) for the same test family or label → bug → its clone chain (`Blocks` links, `[release-x.y]` prefix). Link to the clone for this release if present; else link to the parent and add a `backport_candidates[]` entry.
- **Catch-all** (`OCPQUAL-88`, triage 851): **off by default for post-GA** — never admit a regression; persisting unexplained `LOW` singletons stay listed in `watch_list` with reason `persisting singleton, unexplained; not written`, and `catch_all.admitted` stays `[]`. Re-enabling is one line here, with the former rule: only `LOW` ∧ singleton ∧ persisting ≥2 cycles ∧ examined, each admission carrying `rule_checks` `{examined, no_bug_meets_bar, not_in_cluster, pre_5_0}` all true and listed in the digest.

## 5. Notification policy

Set `escalation.required: true` on every `HIGH` cluster, **regardless of disposition**, including `UNEXPLAINED` and `UNANALYSED` (an `UNANALYSED` `HIGH` still escalates on shape evidence, with diagnosis "unanalysed"). If a link was written, `escalation.reason` states "auto-linked to <bug>, triage <id> — veto by <deadline>" and sets `veto_deadline`. `ELEVATED` ∧ `UNEXPLAINED` → non-pinging escalation reply, no mention; otherwise `ELEVATED` → digest line; `LOW` → count. Set `re_notify` with `re_notify_reasons` when the cluster **grew** since baseline, its **mechanism or severity changed**, or it is **overdue** (>14 d unowned). Include up to 3 `representative_runs` (own runs) and `sippy_links`; state unknown fields as unknown.

Compute escalation and re-notification from current shape, growth, mechanism/severity changes and overdue status; do not copy prior flags or deadlines. Inherited analysis never suppresses a required escalation. Prior escalation fields record an earlier manifest's intent, not successful Slack delivery; delivery deduplication remains the reporter's responsibility. Rebuild representative own-run links and any current veto deadline for this run.

## 6. Jira write scope

Only on **verified existing issues in approved projects** — `OCPBUGS` and `TRT` (the catch-all `OCPQUAL-88` needs no Jira write: its triage link exists). A label, sibling precedent or search result that names an issue in any other project is a recommendation in the report, never a write; the approved set is an owner decision recorded here, not something to infer from permissions.

- `add-jira-triage-link` (description append; footer stays last).
- **One** comment template: the backport-candidate note. One consolidated comment per bug covering all verified affected releases, concise, no mentions, deduplicated (skip if already present), budget **5 comments per run**:

  > Component Readiness regressions on <releases> are linked to this bug; the fix shipped in <version> via <key>; no clone targets <releases>.

  End it with the AI-attribution footer as a separate marked block (SKILL.md Phase 4, new-bug bullet), footer last.
- The triage-link notice comment is **off by default**; post it only if the run's instructions enable it.
- Never: create issues, reopen, transition, set blockers, create issue links, or create labels/symptoms.

## 7. Write modes

This job is unattended: there is no user to confirm. `--write-mode` (default in SKILL.md Arguments) overrides Phase 4's per-bucket confirmation and the `--auto-triage` semantics.

- `report`: no Sippy or Jira write of any kind, regardless of confidence. Record every intended action in `actions[]` with status `skipped-report-mode`; analysis is otherwise identical.
- `auto`: every write that meets the linking gate (§4) is authorised and performed without confirmation (the catch-all rule too, only if it is enabled); everything else is a recorded proposal.
- In both modes, writes that Phase 4 gates on confirmation for other reasons (new Sippy labels/symptoms, release blockers, `manage-labels` updates) stay report recommendations.

Apply §3a in both modes. Report→auto changes permitted actions, not the evidence bar; auto→report performs no writes regardless of history. Reusing a proposal is not evidence that it was previously written.

## 8. Budget ordering

Follow file order: HIGH → ELEVATED → LOW; overlapping unfinished immediate sources first within urgency, then score descending and ID. Old LOW backlog cannot pre-empt HIGH; zero-overlap replacements and history-only snapshots earn no backlog priority. Read prior first. HIGH always gets fresh analysis; eligible non-HIGH recurrence gets §3a verification instead of repeated discovery. Investigate the changes/gaps from those checks.

A previous watch is due for first analysis only if it was deferred as LOW-and-new and has not been analysed since. A completed needs-human/no-link watch is negative knowledge: apply §3a, not first analysis. For retained deferred members, a view-activation age reset does not grant another automatic watch cycle. Truly new LOW work is watched; persisting unexplained LOW stays needs-human, never catch-all admission.

Apply these rules without an analysis_budget field or explicit budget. Spare time does not require re-deriving unchanged work. Carry costs targeted reads, not zero time; never reuse an old pre-PUT read. Spend deep-dive budget on changed/new/unfinished work.

Checkpoint report/manifest early, with unreached work UNANALYSED and an exact reason. Preserve each prior verbatim even when the current cluster was unreached: the next pre-pass retains useful older snapshots as history-only context. This does not claim re-verification. At the hard stop, unfinished work remains in unanalysed[]; HIGH still escalates on shape.

## 9. Manifest writing

Write the per-cluster JSON files, then merge and validate (`manifest.py` is in `scripts/`):

1. `dispositions.json`: object keyed by cluster id (ids must exist in `prepass.json`); each value is the disposition itself, unwrapped. Include an entry for **every** cluster (a missing entry gives no escalation, which fails validation for `HIGH`). Example, `KNOWN-CAUSE`:

   ```json
   {"c-2e1a40": {"state": "KNOWN-CAUSE",
     "analysis": {"depth": "deep-dive", "confidence": "high", "owning_component": "Machine Config Operator",
       "sippy_components": ["Installer"], "triage_type": "product", "root_cause": "<mechanism>",
       "evidence": [{"claim": "<assertion>", "artifact": "<gcs path>", "quote": "<exact line>",
         "prowjob_run_id": "2043...", "supports_regression_ids": [49531, 49532]}],
       "unverified_hypotheses": []},
     "bug_search": {"candidates": [{"key": "OCPBUGS-129375", "status": "POST", "release": "5.0",
       "cites_own_runs": false, "exact_assertion": true, "sibling_precedent": {"view": "5.0-main", "triage_id": 652},
       "bar_met": true, "verdict": "link"}], "newer_release_fix": null},
     "members_unlinked": [{"id": 49533, "reason": "different mechanism, no own-run evidence"}],
     "proposed_action": {"type": "extend_triage", "triage_id": 652, "jira": "OCPBUGS-129375",
       "regression_ids": [49531, 49532], "description": "<120 chars"},
     "escalation": {"required": true, "reason": "HIGH; auto-linked to OCPBUGS-129375, triage 652 — veto by <date>",
       "re_notify": false, "re_notify_reasons": [], "veto_deadline": "<ISO>",
       "representative_runs": [{"prowjob_run_id": "2043...", "url": "<prow url>", "job": "<job>"}], "sippy_links": []}}}
   ```

   `escalation` and `members_unlinked` are moved onto the cluster by the merge. `escalation` may be omitted for non-`HIGH` clusters unless you set the §5 fields; `members_unlinked` is required whenever `proposed_action.type` is not `none`, whatever the level. A cluster you did not reach is `{"state": "UNANALYSED", "analysis": {"depth": "none", "confidence": "low", "root_cause": "<reason: budget exhausted after …>", "evidence": [], "unverified_hypotheses": []}, "escalation": {...}}` and is also listed in `extra.json` `unanalysed[]`.

   Include analysis.reverification for successful carry and for actual verification/fresh investigation undertaken from a prior. Reading prior and selecting an ordinary watch requires no record: use UNEXPLAINED/depth none/no action, preserve prior and record the watch reason. An unreached checkpoint likewise needs no fabricated lookup record. Actual incomplete verification is UNANALYSED with its reason. For successful carry use the following analysis excerpt alongside normal evidence/bug/action/escalation fields; own_run_ids reference current-session observations, never automatic prior coverage.

   ```json
   {
     "depth": "carried-forward",
     "confidence": "high",
     "reverification": {
       "source_run_id": "<prior.run_id>",
       "source_cluster_ids": ["<source cluster id>"],
       "basis": {
         "run_id": "<original analysis run>",
         "cluster_id": "<original cluster id>",
         "observed_at": "<original ISO observation>",
         "depth": "deep-dive"
       },
       "outcome": "carried",
       "reason": "Same own-test signature; target and fix applicability re-confirmed",
       "checked_at": "<current ISO verification time>",
       "own_run_ids": ["<checked own run>"],
       "lookup_locators": ["<inspected bug reply>", "<inspected triage reply or search result>"]
     }
   }
   ```

   basis.depth is deep-dive/oracle; outcome is carried/reinvestigated/incomplete. Source identity refers to the latest immediate sources; basis is the original qualifying analysis. Put observed target status, changed facts, exact search query and missing checks in reason, with inspectable lookup_locators. Fresh completed work uses deep-dive/oracle and outcome reinvestigated; incomplete actual work uses none/incomplete/no write. Prior historical values remain opaque; the validator checks the new envelope and current record/evidence references, not whether an API was really read. Neither dispositions.json nor extra.json may replace the deterministic prior/clusters.
2. `actions.json`: object keyed by cluster id; each value is a list, e.g. `{"c-2e1a40": [{"type": "extend_triage", "triage_id": 652, "regression_ids": [49531, 49532], "status": "done", "precheck": {"triage_reread": true, "already_present": []}, "result_url": "<triage url>", "error": null}]}`. Status `planned|done|failed|skipped-report-mode`; only `done` counts as coverage. Every `extend_triage`/`create_triage` action may only name cluster members that an evidence item supports (`catch_all` actions: members admitted under §4); the validator rejects anything else. Clusters with no actions need no entry.
3. `members.unlinked`: put `"members_unlinked": [{"id": <regression id>, "reason": "<why no evidence>"}]` in the cluster's `dispositions.json` entry; the merge moves it to `members.unlinked`. List every member not covered by evidence whenever `proposed_action.type` is not `none`.
4. `extra.json`, all five keys (shallow-merged at top level):

   ```json
   {"watch_list": [{"regression_id": 51210, "view": "4.21-main", "reason": "LOW & new (<7d)", "cluster_id": "c-1b22c0", "revisit": "next cycle"}],
    "catch_all": {"jira": "OCPQUAL-88", "triage_id": 851, "admitted": []},
    "backport_candidates": [{"cluster_id": "c-2e1a40", "fixed_in": {"key": "OCPBUGS-113706", "fix_version": "5.1.0"}, "this_release": "4.22", "clone_exists": false}],
    "unanalysed": [{"cluster_id": "c-9c0b12", "reason": "budget exhausted after 3h12m", "blast_radius": "ELEVATED"}],
    "audit": {"jira_writes": [], "account_wide_creations": null, "sippy_catalog_diff": null, "jira_permissions": null, "receipt": null,
      "guards": {"existing_only_flag": null, "jql_audit": "unknown", "sippy_diff": "unknown", "junit_backstop": null}}}
   ```

   `watch_list` items come from `prepass.json` `watch_list_candidates` plus `revisit`, filtered through §3a/§8 — a candidate whose cluster is due for first analysis (previously deferred, members retained) or that you analysed this run is not listed as `LOW & new` — and additionally every persisting unexplained `LOW` singleton (`needs-human (low)`). In `bug_search.candidates[]`, `exact_assertion` records that the bug's signature was verified in the cluster's own runs, `cites_own_runs` that the bug itself names one of those runs (rare; strongest evidence), `bar_met` the §4 gate. `catch_all.admitted` stays `[]` while admission is off (item shape when enabled: `{regression_id, rule_checks{examined, no_bug_meets_bar, not_in_cluster, pre_5_0}, signature, status}`). `audit` is a placeholder the runner overwrites; `validate` rejects `{}` or a missing key, so keep this exact skeleton. Use empty lists/objects (`[]`, `"admitted": []`) when there is nothing to report.
5. `python3 scripts/manifest.py merge --prepass prepass.json --dispositions dispositions.json --actions actions.json --extra extra.json --out triage-manifest.json`
6. `python3 scripts/manifest.py validate triage-manifest.json` (exit 0 required; errors on stderr). Fix and re-run on exit 1; never weaken the data to pass.

Validator rules: every evidence item has `prowjob_run_id` and `supports_regression_ids`; `regression_ids` ⊆ supported ids; `rule_checks` all true; `escalation.required` true for every `HIGH` cluster. Every claim needs a locator the next reader can open; unavailable states are explicit (`unknown`, `partial`, `unauthorized`), never zero.

Then write `triage-duty-report-post-ga.md` following SKILL.md Phase 5 plus: clusters by urgency × disposition, completed/planned/failed actions, watch list, catch-all admissions, backport candidates, `UNANALYSED`, and "Proposed new bugs (not filed)".

Add "Analysis memory" counts for carried, fresh/re-investigated, watched and unfinished. Carried wording: "Analysis carried from run <prior.run_id>, cluster <id>; original basis <basis.run_id>/<basis.cluster_id>; re-verified <own-run IDs and lookup locators>; members +<added>/-<removed>; <current action/no-link finding>." Report mode says "re-proposed; not written". Retained context wording: "Latest attempt <prior.run_id> was unfinished; analysis from <history-only source.run_id>/<cluster_id> retained as context, not re-verified." Changed work states what triggered investigation. A deliberately watched replacement is "new population; watched", not a failed carry.

If the baseline is absent/incompatible write: "Analysis memory unavailable: <baseline absent or incompatibility>; prior is null for every cluster. Baseline-dependent changes are unknown." If history exists but is incomplete/unusable, identify the affected clusters and missing fields/checks; do not call them carried. Do not describe a disappearing member as resolved or a historical done action as completed this week. Counts describe this run; do not invent time or dollar savings.

## 10. Policy matrix

| situation | evidence requirement | write (auto mode) | notification | fallback / no-write state |
|---|---|---|---|---|
| `KNOWN-CAUSE`, any urgency | label/precedent identifies the target only; same full linking gate per supported member | extend triage (or create one to the existing bug) for supported members; `add-jira-triage-link`; consolidated backport note | `HIGH` → escalate+mention; `ELEVATED` → digest line; `LOW` → count | gate not met → `CANDIDATE`; unverified members → `unlinked` |
| `CANDIDATE`, `HIGH` | bug's signature verified in own runs, or exact mechanism + precedent | link if bar met (disclosed in escalation) + triage link (+ backport note) | escalate+mention (first; growth; change; overdue) | report-only escalation |
| `CANDIDATE`, `ELEVATED`/`LOW` | same | link if bar met | digest (+ non-pinging reply if `ELEVATED`) | listed as proposed link, no write |
| `UNEXPLAINED`, `HIGH` | n/a | none | escalate+mention | escalation with "unknown" fields explicit |
| `UNEXPLAINED`, `ELEVATED` | n/a | none | non-pinging reply | watch / needs-human (low) |
| `UNEXPLAINED`, `LOW`, new (<7 d) | n/a | none | count | watch one cycle |
| `UNEXPLAINED`, `LOW`, singleton, persisting ≥2 cycles, examined | n/a | none (catch-all admission off by default) | digest "needs-human (low)" | stays untriaged, listed |
| `UNEXPLAINED`, `LOW`, small cluster, persisting | n/a | none (clusters never go to the catch-all) | digest "needs-human (low)" | stays untriaged, listed |
| qualifying prior, current `LOW`/`ELEVATED`, unchanged after §3a checks | inherited high-confidence depth plus current own-run verification and target/search checks; §4 per-member support | current verified links only; historical proposals/results grant no authority | recompute under §5 | carry the same no-link finding or watch outcome; changed/incomplete checks reopen analysis |
| `UNANALYSED` (analysis or verification unfinished) | current pre-pass shape and whatever evidence was actually obtained | none | `HIGH` escalates with diagnosis unanalysed; otherwise prominent digest | retain prior as context; analyse first within urgency next run |
| any, `report` mode | as above | none (`skipped-report-mode`) | as above, marked "would have" | — |
