# Post-GA policy (`--policy post-ga`)

Rulebook for the weekly post-GA run. Read after SKILL.md; the deep-dive rules in Phase 3 still apply to every cluster you analyse. Authentication, the AI-attribution footer and Existing-only mode are defined in SKILL.md and are not repeated here.

## 1. Purpose and scope

- Views: the seven `-main` views `4.16-main` … `4.22-main`, in one run.
- Goal: keep the board at zero untriaged without a weekly human sweep, and make sure a human hears quickly about release-wide breakage.
- Work per **cluster**, never per regression. Closed regressions are evidence only, never work items.
- Existing-only: **never create a Jira issue.** Also no code-fix PRs, release-blocker flags, transitions, or Sippy label/symptom creation (recommend only).
- Two independent axes: **evidence decides writes; blast radius decides notification.**
- Outputs: `triage-duty-report-post-ga.md` and `triage-manifest.json`.

## 2. Phase 0 inputs

`prepass.py --views V... [--now ISO] [--baseline PATH|none] [--no-oracle] [--token-env DPCR_TOKEN] [--inventory PATH] [--run-id ID] --out prepass.json`. If `prepass.json` is absent or a view's `fetch` is not `complete`, say so in the report; an empty or failed fetch is never a clean board. Fields you use per cluster (clusters are sorted HIGH → ELEVATED → LOW, then score descending):

- `id`, `lineage`, `fingerprint`, `members` (regression ids, `new_since_baseline`, views, components), `shape`.
- `blast_radius{level,score,reasons}`.
- `oracle{status,runs_probed,labels,label_bugs}`; `observation.symptom_probe.status ∈ ok|unauthorized|failed|skipped`. Anything but `ok` is **unknown**, never "no symptoms matched": use the SKILL.md fallback ladder.

Clusters are hypotheses. You may split one when signatures differ; record it in `lineage`.

## 3. Blast radius and disposition

**Blast radius** (urgency; computed by the pre-pass, do not recompute):

- `HIGH` (any): ≥8 regressions ∧ ≥4 distinct jobs ∧ ≥2 lane families ∧ (≥2 platforms ∨ ≥2 arches); or `upgrade-from-stable` lane ∧ ≥2 platforms ∧ ≥6 regressions ∧ ≥3 jobs; or persisting (open >7 d ∧ last failure ≤2 d ∧ ≥3 failing own runs in 7 d) ∧ ≥8 regressions ∧ (≥2 distinct jobs ∨ open >14 d).
- `ELEVATED` (any): ≥12 regressions; ≥3 distinct jobs; install/bootstrap wrapper on ≥2 platforms; permafail shape (≥30 failed runs over ≥14 d); single-job mass failure persisting >7 d.
- `LOW`: everything else.
- A single-job mass failure (`mass_failure_marker`) caps at `ELEVATED` unless the lane has been dead >14 d.

`blast_radius.THRESHOLDS`: `{"persist_min_days_open": 7, "persist_max_days_since_last": 2, "persist_min_failing_runs_7d": 3, "persist_min_regressions": 8, "persist_high_min_jobs": 2, "persist_high_min_days_open": 14, "high_broad_min_regressions": 8, "high_broad_min_jobs": 4, "high_broad_min_lane_families": 2, "high_broad_min_spread": 2, "high_minor_min_platforms": 2, "high_minor_min_regressions": 6, "high_minor_min_jobs": 3, "elevated_min_regressions": 12, "elevated_min_jobs": 3, "elevated_install_min_platforms": 2, "elevated_min_runs": 30, "elevated_min_days_open": 14, "score_regressions_cap": 50, "score_jobs_cap": 10, "score_lane_families_cap": 5}`

**Disposition state** (cause; you assign it, one per cluster):

| state | meaning | path |
|---|---|---|
| `KNOWN-CAUSE` | a fired label names a bug, or a related triage has sibling-release precedent | verify on ≥1 own run → extend/link |
| `CANDIDATE` | a plausible bug exists, bar not yet met | deep-dive → link, or escalate/report |
| `UNEXPLAINED` | no bug | `HIGH`/`ELEVATED` → escalate (mention only for `HIGH`); `LOW` ∧ new → watch one cycle; `LOW` ∧ singleton ∧ persisting ∧ examined → catch-all |
| `UNANALYSED` | budget exhausted | listed prominently with reason; no write |

Every cell has a no-write fallback. A small persisting **cluster** with no bug is "needs-human (low)", never the catch-all.

## 4. Write policy

**Linking gate.** Write a triage only when the target bug cites the cluster's **own** prow run IDs and its text carries the **exact failing assertion**, *or* the mechanism matches exactly with **sibling-release precedent**. Titles and keyword matches are not enough. A label or sibling precedent only *identifies the target*; `KNOWN-CAUSE` needs the same gate per supported member (a validated symptom firing on a member's own run counts as that member's own-run evidence). Gate not met → `CANDIDATE`.

- **Evidence membership.** Each evidence item records `prowjob_run_id` and `supports_regression_ids[]`. `proposed_action.regression_ids` must be a subset of the union of those. Members not covered go to `members.unlinked[{id, reason}]`; split the cluster if signatures differ. Own-run evidence only (Case 10).
- **Extend, don't duplicate.** Additive. Re-read the triage immediately before every PUT; resend `url/type/description/resolved/resolution_reason` (full-record replacement) with `+00:00` timestamps; verify from both sides. Record the re-read in `precheck`.
- **Sibling-release lookup.** Search triages in newer views (`4.(n+1)-main`, `5.0-main`) for the same test family or label → bug → its clone chain (`Blocks` links, `[release-x.y]` prefix). Link to the clone for this release if present; else link to the parent and add a `backport_candidates[]` entry.
- **Catch-all** (`OCPQUAL-88`, triage 851): only `LOW` ∧ singleton ∧ persisting ≥2 cycles ∧ examined. Each `catch_all.admitted[].rule_checks` is `{examined, no_bug_meets_bar, not_in_cluster, pre_5_0}`, all true. List every admission in the digest.

## 5. Notification policy

Set `escalation.required: true` on every `HIGH` cluster, **regardless of disposition**, including `UNEXPLAINED` and `UNANALYSED` (an `UNANALYSED` `HIGH` still escalates on shape evidence, with diagnosis "unanalysed"). If a link was written, `escalation.reason` states "auto-linked to <bug>, triage <id> — veto by <deadline>" and sets `veto_deadline`. `ELEVATED` ∧ `UNEXPLAINED` → non-pinging escalation reply, no mention; otherwise `ELEVATED` → digest line; `LOW` → count. Set `re_notify` with `re_notify_reasons` when the cluster **grew** since baseline, its **mechanism or severity changed**, or it is **overdue** (>14 d unowned). Include up to 3 `representative_runs` (own runs) and `sippy_links`; state unknown fields as unknown.

## 6. Jira write scope

Only on **verified existing issues**:

- `add-jira-triage-link` (description append; footer stays last).
- **One** comment template: the backport-candidate note. One consolidated comment per bug covering all verified affected releases, concise, no mentions, deduplicated (skip if already present), budget **5 comments per run**:

  > Component Readiness regressions on <releases> are linked to this bug; the fix shipped in <version> via <key>; no clone targets <releases>.

  End it with the AI-attribution footer as a separate marked block (SKILL.md Phase 4, new-bug bullet), footer last.
- The triage-link notice comment is **off by default**; post it only if the run's instructions enable it.
- Never: create issues, reopen, transition, set blockers, create issue links, or create labels/symptoms.

## 7. Write modes

This job is unattended: there is no user to confirm. `--write-mode` (default in SKILL.md Arguments) overrides Phase 4's per-bucket confirmation and the `--auto-triage` semantics.

- `report`: no Sippy or Jira write of any kind, regardless of confidence. Record every intended action in `actions[]` with status `skipped-report-mode`; analysis is otherwise identical.
- `auto`: every write that meets the linking gate (§4) or the catch-all rule is authorised and performed without confirmation; everything else is a recorded proposal.
- In both modes, writes that Phase 4 gates on confirmation for other reasons (new Sippy labels/symptoms, release blockers, `manage-labels` updates) stay report recommendations.

## 8. Budget ordering

1. `HIGH` deep-dives first.
2. Then `CANDIDATE` with a bar within reach.
3. Then `LOW` persisting signature extraction.

`LOW` ∧ new is never analysed. At the hard stop, leave the remainder `UNANALYSED` with a reason (`unanalysed[{cluster_id,reason,blast_radius}]`). Write the report early and update it; it must exist on disk if the run is killed.

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
       "cites_own_runs": true, "exact_assertion": true, "sibling_precedent": {"view": "5.0-main", "triage_id": 652},
       "bar_met": true, "verdict": "link"}], "newer_release_fix": null},
     "members_unlinked": [{"id": 49533, "reason": "different mechanism, no own-run evidence"}],
     "proposed_action": {"type": "extend_triage", "triage_id": 652, "jira": "OCPBUGS-129375",
       "regression_ids": [49531, 49532], "description": "<120 chars"},
     "escalation": {"required": true, "reason": "HIGH; auto-linked to OCPBUGS-129375, triage 652 — veto by <date>",
       "re_notify": false, "re_notify_reasons": [], "veto_deadline": "<ISO>",
       "representative_runs": [{"prowjob_run_id": "2043...", "url": "<prow url>", "job": "<job>"}], "sippy_links": []}}}
   ```

   `escalation` and `members_unlinked` are moved onto the cluster by the merge; omit it for non-`HIGH` clusters unless you set the §5 fields. A cluster you did not reach is `{"state": "UNANALYSED", "analysis": {"depth": "none", "confidence": "low", "root_cause": "<reason: budget exhausted after …>", "evidence": [], "unverified_hypotheses": []}, "escalation": {...}}` and is also listed in `extra.json` `unanalysed[]`.
2. `actions.json`: object keyed by cluster id; each value is a list, e.g. `{"c-2e1a40": [{"type": "extend_triage", "triage_id": 652, "regression_ids": [49531, 49532], "status": "done", "precheck": {"triage_reread": true, "already_present": []}, "result_url": "<triage url>", "error": null}]}`. Status `planned|done|failed|skipped-report-mode`; only `done` counts as coverage. Clusters with no actions need no entry.
3. `members.unlinked`: put `"members_unlinked": [{"id": <regression id>, "reason": "<why no evidence>"}]` in the cluster's `dispositions.json` entry; the merge moves it to `members.unlinked`. List every member not covered by evidence whenever `proposed_action.type` is not `none`.
4. `extra.json`, all five keys (shallow-merged at top level):

   ```json
   {"watch_list": [{"regression_id": 51210, "view": "4.21-main", "reason": "LOW & new (<7d)", "cluster_id": "c-1b22c0", "revisit": "next cycle"}],
    "catch_all": {"jira": "OCPQUAL-88", "triage_id": 851, "admitted": [{"regression_id": 51180,
      "rule_checks": {"examined": true, "no_bug_meets_bar": true, "not_in_cluster": true, "pre_5_0": true},
      "signature": "<grep-able line>", "status": "done"}]},
    "backport_candidates": [{"cluster_id": "c-2e1a40", "fixed_in": {"key": "OCPBUGS-113706", "fix_version": "5.1.0"}, "this_release": "4.22", "clone_exists": false}],
    "unanalysed": [{"cluster_id": "c-9c0b12", "reason": "budget exhausted after 3h12m", "blast_radius": "ELEVATED"}],
    "audit": {"jira_writes": [], "account_wide_creations": null, "sippy_catalog_diff": null, "jira_permissions": null, "receipt": null,
      "guards": {"existing_only_flag": null, "jql_audit": "unknown", "sippy_diff": "unknown", "junit_backstop": null}}}
   ```

   `watch_list` items come from `prepass.json` `watch_list_candidates` plus `revisit`. `audit` is a placeholder the runner overwrites; `validate` rejects `{}` or a missing key, so keep this exact skeleton. Use empty lists/objects (`[]`, `"admitted": []`) when there is nothing to report.
5. `python3 scripts/manifest.py merge --prepass prepass.json --dispositions dispositions.json --actions actions.json --extra extra.json --out triage-manifest.json`
6. `python3 scripts/manifest.py validate triage-manifest.json` (exit 0 required; errors on stderr). Fix and re-run on exit 1; never weaken the data to pass.

Validator rules: every evidence item has `prowjob_run_id` and `supports_regression_ids`; `regression_ids` ⊆ supported ids; `rule_checks` all true; `escalation.required` true for every `HIGH` cluster. Every claim needs a locator the next reader can open; unavailable states are explicit (`unknown`, `partial`, `unauthorized`), never zero.

Then write `triage-duty-report-post-ga.md` following SKILL.md Phase 5 plus: clusters by urgency × disposition, completed/planned/failed actions, watch list, catch-all admissions, backport candidates, `UNANALYSED`, and "Proposed new bugs (not filed)".

## 10. Policy matrix

| situation | evidence requirement | write (auto mode) | notification | fallback / no-write state |
|---|---|---|---|---|
| `KNOWN-CAUSE`, any urgency | label/precedent identifies the target only; same full linking gate per supported member | extend triage (or create one to the existing bug) for supported members; `add-jira-triage-link`; consolidated backport note | `HIGH` → escalate+mention; `ELEVATED` → digest line; `LOW` → count | gate not met → `CANDIDATE`; unverified members → `unlinked` |
| `CANDIDATE`, `HIGH` | own run IDs + exact assertion, or exact mechanism + precedent | link if bar met (disclosed in escalation) + triage link (+ backport note) | escalate+mention (first; growth; change; overdue) | report-only escalation |
| `CANDIDATE`, `ELEVATED`/`LOW` | same | link if bar met | digest (+ non-pinging reply if `ELEVATED`) | listed as proposed link, no write |
| `UNEXPLAINED`, `HIGH` | n/a | none | escalate+mention | escalation with "unknown" fields explicit |
| `UNEXPLAINED`, `ELEVATED` | n/a | none | non-pinging reply | watch / needs-human (low) |
| `UNEXPLAINED`, `LOW`, new (<7 d) | n/a | none | count | watch one cycle |
| `UNEXPLAINED`, `LOW`, singleton, persisting ≥2 cycles, examined | all four `rule_checks` true | attach to catch-all triage 851 | digest line | stays untriaged, listed |
| `UNEXPLAINED`, `LOW`, small cluster, persisting | n/a | none (clusters never go to the catch-all) | digest "needs-human (low)" | stays untriaged, listed |
| `UNANALYSED` (budget) | pre-pass shape only | none | `HIGH` → escalate+mention anyway, "diagnosis: unanalysed"; else digest, prominent | listed with reason; carried over `HIGH`-first |
| any, `report` mode | as above | none (`skipped-report-mode`) | as above, marked "would have" | — |
