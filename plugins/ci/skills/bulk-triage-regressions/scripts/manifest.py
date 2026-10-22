#!/usr/bin/env python3
"""triage-manifest schema 1.0: validate a manifest and merge prepass.json with the LLM-phase outputs.

  manifest.py validate PATH
  manifest.py merge --prepass P --dispositions D --actions A --out M
"""
import argparse
import copy
import json
import sys
from datetime import datetime

SCHEMA_VERSION = "1.0"
LEVELS = ("HIGH", "ELEVATED", "LOW")
STATES = ("KNOWN-CAUSE", "CANDIDATE", "UNEXPLAINED", "UNANALYSED")
ACTION_TYPES = ("extend_triage", "create_triage", "catch_all", "none")
ACTION_STATUS = ("planned", "done", "failed", "skipped-report-mode")
JQL_AUDIT = ("pass", "fail", "unknown")
SIPPY_DIFF = ("match", "mismatch", "unknown")
PROBE_STATUS = ("ok", "unauthorized", "failed", "skipped")

TOP_PREPASS = ("schema_version", "policy", "source_run", "observation", "baseline_run", "clusters")
TOP_LLM = ("watch_list", "catch_all", "backport_candidates", "unanalysed", "audit")
CLUSTER_PREPASS = ("id", "lineage", "fingerprint", "members", "shape", "blast_radius")
CLUSTER_LLM = ("disposition", "actions", "escalation")
AUDIT_KEYS = ("jira_writes", "account_wide_creations", "sippy_catalog_diff", "jira_permissions", "receipt", "guards")
GUARD_KEYS = ("existing_only_flag", "jql_audit", "sippy_diff", "junit_backstop")
RULE_CHECKS = ("examined", "no_bug_meets_bar", "not_in_cluster", "pre_5_0")


def _t(x):
    return type(x).__name__


def _enum(path, name, value, allowed):
    if isinstance(value, (str, type(None))) and value in allowed:
        return []
    return ["%s: %s %r not in %s" % (path, name, value, list(allowed))]


def _ids(x):
    """Return a set of the hashable ids in a list; anything else is skipped."""
    if not isinstance(x, list):
        return set()
    return {i for i in x if isinstance(i, (int, str))}


def _rule_level(w, c):
    br = c.get("blast_radius")
    if "blast_radius" not in c:
        return []
    if not isinstance(br, dict):
        return ["%s: blast_radius must be an object" % w]
    return _enum(w, "blast_radius.level", br.get("level"), LEVELS)


def _rule_disposition_state(w, c):
    d = c.get("disposition")
    if "disposition" not in c:
        return []
    if not isinstance(d, dict):
        return ["%s: disposition must be an object" % w]
    return _enum(w, "disposition.state", d.get("state"), STATES)


def _evidence_items(c):
    d = c.get("disposition")
    an = d.get("analysis") if isinstance(d, dict) else None
    ev = an.get("evidence") if isinstance(an, dict) else None
    return [e for e in ev if isinstance(e, dict)] if isinstance(ev, list) else []


def _raw_evidence(c):
    d = c.get("disposition")
    an = d.get("analysis") if isinstance(d, dict) else None
    ev = an.get("evidence") if isinstance(an, dict) else None
    return ev if isinstance(ev, list) else []


def _rule_evidence(w, c):
    errs = []
    for i, ev in enumerate(_raw_evidence(c)):      # the raw list: non-object items are reported here, filtered elsewhere
        p = "%s evidence[%d]" % (w, i)
        if not isinstance(ev, dict):
            errs.append("%s: expected object, got %s" % (p, _t(ev)))
            continue
        if not ev.get("prowjob_run_id"):
            errs.append("%s: missing prowjob_run_id" % p)
        sup = ev.get("supports_regression_ids")
        if not isinstance(sup, list) or not sup:
            errs.append("%s: supports_regression_ids must be a non-empty list" % p)
        elif not all(isinstance(x, (int, str)) for x in sup):
            errs.append("%s: supports_regression_ids must contain only ids" % p)
    return errs


def _rule_action_subset_and_unlinked(w, c):
    d = c.get("disposition")
    pa = d.get("proposed_action") if isinstance(d, dict) else None
    if pa is None:
        return []
    if not isinstance(pa, dict):
        return ["%s: proposed_action must be an object" % w]
    errs = _enum(w, "proposed_action.type", pa.get("type"), ACTION_TYPES)
    if pa.get("type") == "none":
        return errs
    union = set()
    for ev in _evidence_items(c):
        if isinstance(ev, dict):
            union |= _ids(ev.get("supports_regression_ids"))
    extra = sorted(_ids(pa.get("regression_ids")) - union, key=str)
    if extra:
        errs.append("%s: proposed_action.regression_ids not supported by evidence: %s" % (w, extra))
    mem = c.get("members")
    mem = mem if isinstance(mem, dict) else {}
    unl = mem.get("unlinked")
    unlinked = {u.get("id") for u in unl if isinstance(u, dict) and isinstance(u.get("id"), (int, str))} \
        if isinstance(unl, list) else set()
    for r in sorted(_ids(mem.get("regression_ids")) - union - unlinked, key=str):
        errs.append("%s: member %s has no evidence and is not listed in members.unlinked" % (w, r))
    return errs


def _rule_actions(w, c):
    acts = c.get("actions")
    if acts is None:
        return []
    if not isinstance(acts, list):
        return ["%s: actions must be a list" % w]
    errs = []
    for j, a in enumerate(acts):
        p = "%s actions[%d]" % (w, j)
        if not isinstance(a, dict):
            errs.append("%s: expected object, got %s" % (p, _t(a)))
            continue
        errs += _enum(p, "status", a.get("status"), ACTION_STATUS)
        errs += _enum(p, "type", a.get("type"), ACTION_TYPES)
        if a.get("type") in ("extend_triage", "create_triage", "catch_all"):
            errs += _rule_action_targets(p, c, a)
    return errs


def _rule_action_targets(p, c, a):
    """A write (intended, done or failed) may only target cluster members, and — except for the catch-all,
    whose admission is governed by rule_checks — only members some evidence item supports (review I5)."""
    ids = a.get("regression_ids")
    if not isinstance(ids, list) or not ids:
        return ["%s: regression_ids must be a non-empty list for a %s action" % (p, a.get("type"))]
    if any(not isinstance(i, (int, str)) or isinstance(i, bool) for i in ids):
        return ["%s: regression_ids must contain only integer or string ids" % p]
    members = _ids((c.get("members") or {}).get("regression_ids")) if isinstance(c.get("members"), dict) else set()
    errs = []
    outside = sorted(_ids(ids) - members, key=str)
    if outside:
        errs.append("%s: action targets non-members %s" % (p, outside))
    if a.get("type") != "catch_all":
        supported = set()
        for ev in _evidence_items(c):
            supported |= _ids(ev.get("supports_regression_ids"))
        unsupported = sorted(_ids(ids) - supported - set(outside), key=str)
        if unsupported:
            errs.append("%s: action targets members without evidence support %s" % (p, unsupported))
    return errs


def _rule_escalation(w, c):
    if "escalation" not in c:
        return []
    esc = c["escalation"]
    if not isinstance(esc, dict):
        return ["%s: escalation must be an object" % w]
    br = c.get("blast_radius")
    if isinstance(br, dict) and br.get("level") == "HIGH" and esc.get("required") is not True:
        return ["%s: escalation.required must be true for HIGH blast radius" % w]
    return []


def _rule_missing(w, c):
    return ["%s: missing %s" % (w, k) for k in CLUSTER_PREPASS + CLUSTER_LLM if k not in c]


def _rule_objects(w, c):
    errs = ["%s: %s must be an object" % (w, k) for k in ("lineage", "fingerprint", "members", "shape")
            if k in c and not isinstance(c[k], dict)]
    mem = c.get("members")
    if isinstance(mem, dict) and not isinstance(mem.get("regression_ids"), list):
        errs.append("%s: members.regression_ids must be a list" % w)
    return errs


PRIOR_RELATIONSHIPS = ("same-id", "supersedes", "split", "merge", "overlap")
PRIOR_WRITE_MODES = ("report", "auto")
PRIOR_BASIS_DEPTHS = ("deep-dive", "oracle")
PRIOR_ROOT_LIMIT = 2000
PRIOR_SOURCE_LISTS = ("actions", "unlinked", "watch_list", "unanalysed")
PRIOR_SOURCE_OBJECTS = ("fingerprint", "shape", "blast_radius", "oracle", "bug_search", "proposed_action",
                        "escalation")


def _is_id(x):
    return (isinstance(x, int) and not isinstance(x, bool)) or (isinstance(x, str) and x != "")


def _id_list(p, name, value):
    if not isinstance(value, list) or any(not _is_id(i) for i in value):
        return ["%s: %s must be a list of integer or string ids" % (p, name)]
    return []


def _iso_or_null(p, name, value):
    if value is None:
        return []
    if not isinstance(value, str) or not value:
        return ["%s: %s must be an ISO timestamp or null" % (p, name)]
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return ["%s: %s must be an ISO timestamp or null" % (p, name)]
    if parsed.tzinfo is None:
        return ["%s: %s must carry a timezone" % (p, name)]
    return []


def _rule_basis(p, basis):
    if basis is None:
        return []
    if not isinstance(basis, dict):
        return ["%s: basis must be an object or null" % p]
    errs = []
    for k in ("run_id", "cluster_id"):
        if not isinstance(basis.get(k), str) or not basis.get(k):
            errs.append("%s: basis.%s must be a non-empty string" % (p, k))
    errs += _iso_or_null(p, "basis.observed_at", basis.get("observed_at"))
    if basis.get("observed_at") is None:
        errs.append("%s: basis.observed_at must be an ISO timestamp" % p)
    errs += _enum(p, "basis.depth", basis.get("depth"), PRIOR_BASIS_DEPTHS)
    return errs


def _rule_prior_source(p, s, current_members):
    """The projected envelope of one source: identity, flags, ids, bounded analysis. Historical payloads
    (state, candidates, actions, escalation, shape, oracle ...) are opaque: no enums, no target rules."""
    if not isinstance(s, dict):
        return ["%s: expected object, got %s" % (p, _t(s))]
    errs = []
    if not isinstance(s.get("cluster_id"), str) or not s.get("cluster_id"):
        errs.append("%s: cluster_id must be a non-empty string" % p)
    for k in ("history_only", "unfinished"):
        if not isinstance(s.get(k), bool):
            errs.append("%s: %s must be a boolean" % (p, k))
    if s.get("run_id") is not None and (not isinstance(s.get("run_id"), str) or not s.get("run_id")):
        errs.append("%s: run_id must be a non-empty string or null" % p)
    errs += _iso_or_null(p, "observed_at", s.get("observed_at"))
    id_errs = _id_list(p, "member_ids", s.get("member_ids")) + _id_list(p, "matched_member_ids", s.get("matched_member_ids"))
    errs += id_errs
    if not id_errs:
        matched, members = _ids(s.get("matched_member_ids")), _ids(s.get("member_ids"))
        if matched != members & current_members:
            errs.append("%s: matched_member_ids %s must be exactly the source members present in this cluster %s"
                        % (p, sorted(matched, key=str), sorted(members & current_members, key=str)))
    if s.get("state") is not None and not isinstance(s.get("state"), str):
        errs.append("%s: state must be a string or null" % p)
    for k in PRIOR_SOURCE_OBJECTS:
        if s.get(k) is not None and not isinstance(s.get(k), dict):
            errs.append("%s: %s must be an object or null" % (p, k))
    for k in PRIOR_SOURCE_LISTS:
        if s.get(k) is not None and not isinstance(s.get(k), list):
            errs.append("%s: %s must be a list or null" % (p, k))
    an = s.get("analysis")
    if an is not None:
        if not isinstance(an, dict):
            errs.append("%s: analysis must be an object or null" % p)
        else:
            root = an.get("root_cause")
            if root is not None and not isinstance(root, str):
                errs.append("%s: analysis.root_cause must be a string or null" % p)
            elif isinstance(root, str) and len(root) > PRIOR_ROOT_LIMIT:
                errs.append("%s: analysis.root_cause exceeds %d characters" % (p, PRIOR_ROOT_LIMIT))
            if not isinstance(an.get("root_cause_truncated"), bool):
                errs.append("%s: analysis.root_cause_truncated must be a boolean" % p)
            refs = an.get("evidence_refs")
            if not isinstance(refs, list):
                errs.append("%s: analysis.evidence_refs must be a list" % p)
            else:
                for i, r in enumerate(refs):
                    q = "%s analysis.evidence_refs[%d]" % (p, i)
                    if not isinstance(r, dict):
                        errs.append("%s: expected object, got %s" % (q, _t(r)))
                        continue
                    if not isinstance(r.get("prowjob_run_id"), str) or not r.get("prowjob_run_id"):
                        errs.append("%s: prowjob_run_id must be a non-empty string" % q)
                    sup = r.get("supports_regression_ids")
                    if not isinstance(sup, list) or not sup or any(not _is_id(i) for i in sup):
                        errs.append("%s: supports_regression_ids must be a non-empty list of ids" % q)
                    if r.get("artifact") is not None and not isinstance(r.get("artifact"), str):
                        errs.append("%s: artifact must be a string or null" % q)
            errs += _rule_basis(p + " analysis", an.get("basis"))
    return errs


def _key(value):
    """A hashable stand-in for an identity field whose type may be wrong (reported elsewhere, never raised)."""
    return value if isinstance(value, (str, int, float, bool, type(None))) else repr(value)


def _rule_prior(w, c):
    """Optional memory envelope (additive, schema 1.0). Absent or null is fine; a present object must be the
    deterministic projection shape. Only the envelope is validated, never the old run's domain values."""
    if "prior" not in c or c["prior"] is None:
        return []
    pr = c["prior"]
    p = "%s prior" % w
    if not isinstance(pr, dict):
        return ["%s: expected object or null, got %s" % (p, _t(pr))]
    errs = []
    for k in ("run_id", "source_url"):
        if pr.get(k) is not None and (not isinstance(pr.get(k), str) or not pr.get(k)):
            errs.append("%s: %s must be a non-empty string or null" % (p, k))
    errs += _iso_or_null(p, "observed_at", pr.get("observed_at"))
    if pr.get("write_mode") is not None:
        errs += _enum(p, "write_mode", pr.get("write_mode"), PRIOR_WRITE_MODES)
    if not isinstance(pr.get("observation_complete"), bool):
        errs.append("%s: observation_complete must be a boolean" % p)
    errs += _enum(p, "relationship", pr.get("relationship"), PRIOR_RELATIONSHIPS)
    mem = c.get("members")
    current_members = _ids(mem.get("regression_ids")) if isinstance(mem, dict) else set()
    sources = pr.get("sources")
    if not isinstance(sources, list) or not sources:
        errs.append("%s: sources must be a non-empty list" % p)
        sources = []
    seen, immediate_union, immediate = set(), set(), 0
    for i, s in enumerate(sources):
        q = "%s sources[%d]" % (p, i)
        errs += _rule_prior_source(q, s, current_members)
        if not isinstance(s, dict):
            continue
        key = tuple(_key(s.get(k)) for k in ("history_only", "run_id", "observed_at", "cluster_id"))
        if key in seen:
            errs.append("%s: duplicate source identity %r" % (q, key))
        seen.add(key)
        if s.get("history_only") is False:
            immediate += 1
            immediate_union |= _ids(s.get("member_ids"))
    if sources and not immediate:
        errs.append("%s: sources must include at least one immediate (history_only false) source" % p)
    delta = pr.get("member_delta")
    if not isinstance(delta, dict):
        errs.append("%s: member_delta must be an object" % p)
    else:
        errs += _id_list(p, "member_delta.added", delta.get("added"))
        errs += _id_list(p, "member_delta.removed", delta.get("removed"))
        if immediate and isinstance(delta.get("added"), list) and isinstance(delta.get("removed"), list):
            if _ids(delta["added"]) != current_members - immediate_union:
                errs.append("%s: member_delta.added must be the current members absent from the immediate sources" % p)
            if _ids(delta["removed"]) != immediate_union - current_members:
                errs.append("%s: member_delta.removed must be the immediate sources' members absent now" % p)
    return errs


def _rule_prior_context(doc):
    """Bind each prior's immediate sources to the latest attempt named in baseline_run; retained
    (history_only) snapshots keep their own older identity. A non-null prior needs a compatible baseline."""
    br = doc.get("baseline_run") if isinstance(doc.get("baseline_run"), dict) else {}
    clusters = doc.get("clusters") if isinstance(doc.get("clusters"), list) else []
    errs = []
    for c in clusters:
        if not isinstance(c, dict) or not isinstance(c.get("prior"), dict):
            continue
        pr = c["prior"]
        w = "cluster %s prior" % c.get("id")
        if br.get("compatible") is not True:
            errs.append("%s: a prior requires baseline_run.compatible true" % w)
        if br.get("run_id") is not None and pr.get("run_id") is not None and str(br["run_id"]) != str(pr["run_id"]):
            errs.append("%s: run_id %r is not the baseline_run.run_id %r" % (w, pr["run_id"], br["run_id"]))
        for i, s in enumerate(pr.get("sources") if isinstance(pr.get("sources"), list) else []):
            if not isinstance(s, dict) or s.get("history_only") is not False:
                continue
            for k in ("run_id", "observed_at"):
                if s.get(k) != pr.get(k):
                    errs.append("%s sources[%d]: immediate source %s %r differs from the prior's %r"
                                % (w, i, k, s.get(k), pr.get(k)))
    observed = doc.get("observation", {}).get("time") if isinstance(doc.get("observation"), dict) else None
    observed_dt = _instant(observed)
    for c in clusters:
        if not isinstance(c, dict):
            continue
        _, rev = _reverification(c)
        if not isinstance(rev, dict):
            continue
        checked = _instant(rev.get("checked_at"))
        if observed_dt is None:
            errs.append("cluster %s reverification: observation.time %r is not an ISO instant; checked_at cannot be verified"
                        % (c.get("id"), observed))
        elif checked and checked < observed_dt:
            errs.append("cluster %s reverification: checked_at %r precedes this run's observation.time %r"
                        % (c.get("id"), rev.get("checked_at"), observed))
    return errs


def _instant(value):
    """A timezone-aware datetime for an ISO string, else None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


REVERIFICATION_OUTCOMES = ("carried", "reinvestigated", "incomplete")
CARRIED_DEPTH = "carried-forward"
CARRY_RELATIONSHIPS = ("same-id", "supersedes")
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
WRITE_TYPES = ("extend_triage", "create_triage", "catch_all")


def _reverification(c):
    """(analysis, record) when the cluster's analysis is an object; the record may be absent (None)."""
    d = c.get("disposition")
    an = d.get("analysis") if isinstance(d, dict) else None
    if not isinstance(an, dict):
        return None, None
    return an, an.get("reverification")


def _str_list(p, name, value):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        return ["%s: %s must be a list of non-empty strings" % (p, name)], []
    return [], value


def _keyed(cand, bar):
    return isinstance(cand, dict) and isinstance(cand.get("key"), str) and cand.get("key") and cand.get("bar_met") is bar


def _rule_carry_fact(p, source):
    """The one historical fact a carry asserts, type-checked only here: the previous state's bug-search
    verdict. Legacy or malformed values (e.g. bar_met "unknown") cannot establish a carry."""
    state = source.get("state")
    bs = source.get("bug_search") if isinstance(source.get("bug_search"), dict) else {}
    cands = bs.get("candidates")
    if state == "KNOWN-CAUSE":
        if not isinstance(cands, list) or not any(_keyed(x, True) for x in cands):
            return ["%s: KNOWN-CAUSE carry needs a source bug_search.candidates entry with a key and bar_met true" % p]
    elif state == "CANDIDATE":
        if not isinstance(cands, list) or not any(_keyed(x, False) for x in cands):
            return ["%s: CANDIDATE carry needs a source bug_search.candidates entry with a key and bar_met false" % p]
    elif state == "UNEXPLAINED":
        if not isinstance(cands, list) or any(not _keyed(x, False) for x in cands):
            return ["%s: UNEXPLAINED carry needs a known source bug_search.candidates list that is empty or holds only"
                    " keyed bar_met-false records" % p]
    else:
        return ["%s: source state %r cannot be carried" % (p, state)]
    return []


def _typed_evidence(c):
    """(prowjob_run_id as text, supported ids) for current evidence items whose run id is an id; the single
    population used for own_run_ids references and for carry coverage."""
    return [(str(ev.get("prowjob_run_id")), _ids(ev.get("supports_regression_ids")))
            for ev in _evidence_items(c) if _is_id(ev.get("prowjob_run_id"))]


def _rule_carry(w, p, c, an, rev, own, locators):
    """Eligibility of a carried-forward analysis: one finished, overlapping immediate source of known identity
    and time, complete observation, high confidence on both sides, same state, non-HIGH and not promoted,
    a basis-backed untruncated source analysis, and current own-run evidence covering every write target
    and (when members were added) at least one added member."""
    errs = []
    d = c.get("disposition") if isinstance(c.get("disposition"), dict) else {}
    br = c.get("blast_radius") if isinstance(c.get("blast_radius"), dict) else {}
    level = br.get("level")
    if level == "HIGH":
        errs.append("%s: a HIGH cluster is never carried; it needs a fresh deep-dive" % p)
    elif not (isinstance(level, str) and level in LEVEL_RANK):
        errs.append("%s: carry requires a readable current blast_radius.level, got %r" % (p, level))
    if an.get("confidence") != "high":
        errs.append("%s: carry requires current analysis.confidence high, got %r" % (p, an.get("confidence")))
    if not own:
        errs.append("%s: carry requires non-empty own_run_ids referencing current evidence" % p)
    if not locators:
        errs.append("%s: carry requires non-empty lookup_locators" % p)
    pr = c.get("prior")
    if not isinstance(pr, dict):
        return errs   # reported by _rule_reverification: no prior, nothing to carry
    if pr.get("relationship") not in CARRY_RELATIONSHIPS:
        errs.append("%s: carry requires prior.relationship same-id or supersedes, got %r" % (p, pr.get("relationship")))
    if pr.get("observation_complete") is not True:
        errs.append("%s: carry requires prior.observation_complete true" % p)
    if pr.get("run_id") is None:
        errs.append("%s: carry requires a known prior.run_id" % p)
    if pr.get("observed_at") is None:
        errs.append("%s: carry requires a known prior.observed_at" % p)
    sources = pr.get("sources") if isinstance(pr.get("sources"), list) else []
    immediate = [s for s in sources if isinstance(s, dict) and s.get("history_only") is False]
    if len(immediate) != 1:
        errs.append("%s: carry requires exactly one immediate source, found %d (merge/split history is re-investigated)"
                    % (p, len(immediate)))
        return errs
    s = immediate[0]
    if rev.get("source_cluster_ids") != [s.get("cluster_id")]:
        errs.append("%s: carry source_cluster_ids %r must name exactly the sole immediate source %r"
                    % (p, rev.get("source_cluster_ids"), [s.get("cluster_id")]))
    if s.get("unfinished") is not False:
        errs.append("%s: the immediate source is unfinished; nothing to carry" % p)
    if not _ids(s.get("matched_member_ids")):
        errs.append("%s: the immediate source has no matched_member_ids in common with this cluster" % p)
    if s.get("state") != d.get("state"):
        errs.append("%s: carry requires the source state %r, disposition.state is %r" % (p, s.get("state"), d.get("state")))
    sbr = s.get("blast_radius") if isinstance(s.get("blast_radius"), dict) else {}
    s_level = sbr.get("level")
    if not (isinstance(s_level, str) and s_level in LEVEL_RANK):
        errs.append("%s: carry requires a readable source blast_radius.level, got %r" % (p, s_level))
    elif isinstance(level, str) and level in LEVEL_RANK and LEVEL_RANK[level] < LEVEL_RANK[s_level]:
        errs.append("%s: blast_radius.level rose %s -> %s; a promoted cluster is re-investigated" % (p, s_level, level))
    san = s.get("analysis") if isinstance(s.get("analysis"), dict) else None
    if san is None:
        errs.append("%s: the immediate source has no readable analysis; basis unavailable" % p)
        return errs
    if san.get("confidence") != "high":
        errs.append("%s: source analysis.confidence %r is not high" % (p, san.get("confidence")))
    if san.get("root_cause_truncated") is not False:
        errs.append("%s: source analysis.root_cause_truncated must be false for a carry" % p)
    basis = san.get("basis")
    if not isinstance(basis, dict):
        errs.append("%s: the source analysis has no basis; carry not allowed" % p)
    elif rev.get("basis") != basis:
        errs.append("%s: basis %r must equal the source analysis basis %r" % (p, rev.get("basis"), basis))
    errs += _rule_carry_fact(p, s)
    checked = set()
    for run_id, supported in _typed_evidence(c):
        if run_id in own:
            checked |= supported
    targets = set()
    pa = d.get("proposed_action") if isinstance(d.get("proposed_action"), dict) else {}
    if pa.get("type") in WRITE_TYPES:
        targets |= _ids(pa.get("regression_ids"))
    for a in c.get("actions") if isinstance(c.get("actions"), list) else []:
        if isinstance(a, dict) and a.get("type") in WRITE_TYPES:
            targets |= _ids(a.get("regression_ids"))
    uncovered = sorted(targets - checked, key=str)
    if uncovered:
        errs.append("%s: own-run evidence does not cover proposed/action targets %s" % (p, uncovered))
    delta = pr.get("member_delta") if isinstance(pr.get("member_delta"), dict) else {}
    added = _ids(delta.get("added"))
    if added and not (added & checked):
        errs.append("%s: members were added %s; carry requires a checked own run for at least one added member"
                    % (p, sorted(added, key=str)))
    return errs


def _rule_incomplete(w, p, c, an):
    """An explicitly incomplete verification is UNANALYSED work: no completed diagnosis, no write."""
    errs = []
    d = c.get("disposition") if isinstance(c.get("disposition"), dict) else {}
    if d.get("state") != "UNANALYSED":
        errs.append("%s: outcome incomplete requires disposition.state UNANALYSED, got %r" % (p, d.get("state")))
    if an.get("depth") != "none":
        errs.append("%s: outcome incomplete requires analysis.depth none, got %r" % (p, an.get("depth")))
    pa = d.get("proposed_action") if isinstance(d.get("proposed_action"), dict) else {}
    if pa.get("type") in WRITE_TYPES:
        errs.append("%s: outcome incomplete permits no proposed_action write (%s)" % (p, pa.get("type")))
    for j, a in enumerate(c.get("actions") if isinstance(c.get("actions"), list) else []):
        if isinstance(a, dict) and a.get("type") in WRITE_TYPES:
            errs.append("%s: outcome incomplete permits no write action (actions[%d] %s)" % (p, j, a.get("type")))
    return errs


def _rule_reverification(w, c):
    """The current re-verification record (analysis.reverification). Any record must be well-formed and
    its own_run_ids must be current evidence; a carried-forward analysis additionally has to satisfy
    the carry eligibility in _rule_carry. A deliberate watch or a plain fresh analysis needs no record."""
    an, rev = _reverification(c)
    if an is None:
        return []
    depth = an.get("depth")
    if rev is None:
        return ["%s: analysis.depth %s requires analysis.reverification" % (w, CARRIED_DEPTH)] if depth == CARRIED_DEPTH else []
    p = "%s reverification" % w
    if not isinstance(rev, dict):
        return ["%s: expected object, got %s" % (p, _t(rev))]
    errs = _enum(p, "outcome", rev.get("outcome"), REVERIFICATION_OUTCOMES)
    if not isinstance(rev.get("reason"), str) or not rev.get("reason"):
        errs.append("%s: reason must be a non-empty string" % p)
    if rev.get("source_run_id") is not None and (not isinstance(rev.get("source_run_id"), str) or not rev["source_run_id"]):
        errs.append("%s: source_run_id must be a non-empty string or null" % p)
    e, _ = _str_list(p, "source_cluster_ids", rev.get("source_cluster_ids"))
    errs += e
    errs += _rule_basis(p, rev.get("basis"))
    errs += _iso_or_null(p, "checked_at", rev.get("checked_at"))
    e, own = _str_list(p, "own_run_ids", rev.get("own_run_ids"))
    errs += e
    e, locators = _str_list(p, "lookup_locators", rev.get("lookup_locators"))
    errs += e
    if len(set(own)) != len(own):
        errs.append("%s: own_run_ids must not repeat" % p)
    if rev.get("checked_at") is None:
        errs.append("%s: checked_at is required for every record" % p)
    current_runs = {run_id for run_id, _ in _typed_evidence(c)}
    missing = [r for r in own if r not in current_runs]
    if missing:
        errs.append("%s: own_run_ids not present in current evidence (as string or integer prowjob_run_id): %s" % (p, missing))
    pr = c.get("prior")
    if not isinstance(pr, dict):
        errs.append("%s: a record needs a non-null prior; there is no source to verify against" % p)
    else:
        if rev.get("source_run_id") != pr.get("run_id"):
            errs.append("%s: source_run_id %r must equal prior.run_id %r" % (p, rev.get("source_run_id"), pr.get("run_id")))
        immediate = sorted(s.get("cluster_id") for s in (pr.get("sources") if isinstance(pr.get("sources"), list) else [])
                           if isinstance(s, dict) and s.get("history_only") is False and isinstance(s.get("cluster_id"), str))
        declared = rev.get("source_cluster_ids") if isinstance(rev.get("source_cluster_ids"), list) else None
        if declared is not None and all(isinstance(x, str) for x in declared):
            if declared != sorted(set(declared)):
                errs.append("%s: source_cluster_ids %r must be sorted and duplicate-free" % (p, declared))
            foreign = sorted(set(declared) - set(immediate))
            if foreign:
                errs.append("%s: source_cluster_ids %r are not immediate sources of this prior %r" % (p, foreign, immediate))
    if rev.get("outcome") == "incomplete":
        errs += _rule_incomplete(w, p, c, an)
    members = _ids(c["members"].get("regression_ids")) if isinstance(c.get("members"), dict) else set()
    outside = set()
    for ev in _evidence_items(c):
        outside |= _ids(ev.get("supports_regression_ids")) - members
    if outside:
        errs.append("%s: current evidence supports non-members %s; prior references supply no coverage"
                    % (w, sorted(outside, key=str)))
    carried = rev.get("outcome") == "carried"
    if carried != (depth == CARRIED_DEPTH):
        errs.append("%s: outcome %r and analysis.depth %r must agree (carried <-> %s)"
                    % (p, rev.get("outcome"), depth, CARRIED_DEPTH))
    if carried or depth == CARRIED_DEPTH:
        errs += _rule_carry(w, p, c, an, rev, own, locators)
    return errs


CLUSTER_RULES = (_rule_missing, _rule_objects, _rule_level, _rule_disposition_state, _rule_evidence,
                 _rule_action_subset_and_unlinked, _rule_actions, _rule_escalation, _rule_prior, _rule_reverification)


def _cluster(c, idx):
    if not isinstance(c, dict):
        return ["cluster %d: expected object, got %s" % (idx, _t(c))]
    w = "cluster %s" % (c["id"] if isinstance(c.get("id"), str) else "#%d" % idx)
    errs = [] if isinstance(c.get("id"), str) and c["id"] else ["%s: id must be a non-empty string, got %s" % (w, _t(c.get("id")))]
    return errs + [e for rule in CLUSTER_RULES for e in rule(w, c)]


def _rule_probe(doc):
    obs = doc.get("observation")
    if not isinstance(obs, dict) or "symptom_probe" not in obs:
        return []
    probe = obs["symptom_probe"]
    if not isinstance(probe, dict):
        return ["observation.symptom_probe: expected object, got %s" % _t(probe)]
    return _enum("observation.symptom_probe", "status", probe.get("status"), PROBE_STATUS)


def _rule_catch_all(doc):
    ca = doc.get("catch_all")
    if ca is None:
        return _rule_catch_all_actions(doc, {}, [])          # no configuration = no admissions, not "skip"
    if not isinstance(ca, dict):
        return ["catch_all: expected object, got %s" % _t(ca)] + _rule_catch_all_actions(doc, {}, [])
    adm = ca.get("admitted")
    if adm is None:
        return _rule_catch_all_actions(doc, ca, [])
    if not isinstance(adm, list):
        return ["catch_all.admitted: expected list, got %s" % _t(adm)] + _rule_catch_all_actions(doc, ca, [])
    errs = []
    for i, a in enumerate(adm):
        p = "catch_all.admitted[%d]" % i
        if not isinstance(a, dict):
            errs.append("%s: expected object, got %s" % (p, _t(a)))
            continue
        rc = a.get("rule_checks")
        rc = rc if isinstance(rc, dict) else {}
        errs += ["%s: rule_checks.%s must be true" % (p, k) for k in RULE_CHECKS if rc.get(k) is not True]
    return errs + _rule_catch_all_actions(doc, ca, adm)


def _rule_catch_all_actions(doc, ca, adm):
    """A catch_all action is only legitimate for members admitted under the four rule checks, and only
    against the configured catch-all triage (review N5)."""
    admitted = {a.get("regression_id") for a in adm if isinstance(a, dict) and isinstance(a.get("regression_id"), (int, str))
                and isinstance(a.get("rule_checks"), dict) and all(a["rule_checks"].get(k) is True for k in RULE_CHECKS)}
    target = ca.get("triage_id")
    errs = []
    clusters = doc.get("clusters") if isinstance(doc.get("clusters"), list) else []
    for c in clusters:
        if not isinstance(c, dict) or not isinstance(c.get("actions"), list):
            continue
        for j, a in enumerate(c["actions"]):
            if not isinstance(a, dict) or a.get("type") != "catch_all":
                continue
            p = "cluster %s actions[%d]" % (c.get("id"), j)
            if target is None:
                errs.append("%s: catch_all.triage_id must be configured when catch_all actions exist" % p)
            elif str(a.get("triage_id")) != str(target):
                errs.append("%s: catch_all action targets triage %s, not the catch-all triage %s" % (p, a.get("triage_id"), target))
            not_admitted = sorted(_ids(a.get("regression_ids")) - admitted, key=str)
            if not_admitted:
                errs.append("%s: catch_all action for members without a valid catch_all.admitted entry %s" % (p, not_admitted))
    return errs


def _rule_audit(doc):
    audit = doc.get("audit")
    if audit is None:
        return []
    if not isinstance(audit, dict):
        return ["audit: expected object, got %s" % _t(audit)]
    errs = ["audit.%s: missing" % k for k in AUDIT_KEYS if k not in audit]
    g = audit.get("guards")
    if isinstance(g, dict):
        errs += ["audit.guards.%s: missing" % k for k in GUARD_KEYS if k not in g]
        if "jql_audit" in g:
            errs += _enum("audit.guards", "jql_audit", g["jql_audit"], JQL_AUDIT)
        if "sippy_diff" in g:
            errs += _enum("audit.guards", "sippy_diff", g["sippy_diff"], SIPPY_DIFF)
    elif "guards" in audit:
        errs.append("audit.guards: expected object, got %s" % _t(g))
    return errs


def validate(doc):
    """Return a list of error strings; empty means valid. Never raises."""
    if not isinstance(doc, dict):
        return ["manifest: expected object, got %s" % _t(doc)]
    errs = ["missing top-level key: %s" % k for k in TOP_PREPASS + TOP_LLM if k not in doc]
    if "schema_version" in doc and doc["schema_version"] != SCHEMA_VERSION:
        errs.append("schema_version: %r != %r" % (doc["schema_version"], SCHEMA_VERSION))
    errs += _rule_top_level_shapes(doc)
    errs += _rule_probe(doc)
    cl = doc.get("clusters", [])
    if not isinstance(cl, list):
        cl = []
    seen = {}
    for i, c in enumerate(cl):
        errs += _cluster(c, i)
        cid = c.get("id") if isinstance(c, dict) else None
        if isinstance(cid, (str, int)):
            if cid in seen:
                errs.append("cluster %s: duplicate cluster id (also at index %d)" % (cid, seen[cid]))
            seen.setdefault(cid, i)
    return errs + _rule_catch_all(doc) + _rule_audit(doc) + _rule_prior_context(doc)


TOP_SHAPES = {"policy": dict, "source_run": dict, "observation": dict, "baseline_run": dict, "clusters": list,
              "watch_list": list, "catch_all": dict, "backport_candidates": list, "unanalysed": list, "audit": dict}
TOP_REQUIRED_FIELDS = {"policy": ("name",), "source_run": ("run_id",), "observation": ("time", "views", "symptom_probe")}


def _rule_top_level_shapes(doc):
    """Required containers must have their documented shape; a null or empty object is not a manifest (review I5)."""
    errs = []
    for key, typ in TOP_SHAPES.items():
        if key not in doc:
            continue
        v = doc[key]
        if not isinstance(v, typ):
            errs.append("%s: expected %s, got %s" % (key, typ.__name__, _t(v)))
            continue
        for f in TOP_REQUIRED_FIELDS.get(key, ()):
            if f not in v:
                errs.append("%s.%s: missing" % (key, f))
    return errs


def merge(prepass, dispositions, actions):
    """Combine prepass.json with LLM-phase dispositions (id -> dict) and actions (id -> list)."""
    ids = [c["id"] for c in prepass["clusters"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError("prepass has duplicate cluster ids: %s" % dupes)
    known = set(ids)
    for name, d in (("dispositions", dispositions), ("actions", actions)):
        unknown = sorted(set(d) - known)
        if unknown:
            raise ValueError("%s for clusters not in prepass: %s" % (name, unknown))
    out = copy.deepcopy(prepass)
    for c in out["clusters"]:
        cid = c["id"]
        c["actions"] = copy.deepcopy(actions.get(cid, []))
        if cid not in dispositions:
            continue
        disp = copy.deepcopy(dispositions[cid])
        if "prior" in disp:
            raise ValueError("dispositions for cluster %s may not set prior: it is pre-pass memory" % cid)
        esc = disp.pop("escalation", None)
        unl = disp.pop("members_unlinked", None)
        if unl is not None:
            if not isinstance(unl, list):
                raise ValueError("members_unlinked for cluster %s must be a list, got %s" % (cid, _t(unl)))
            c["members"]["unlinked"] = unl
        c["disposition"] = disp
        if esc is None:
            level = c["blast_radius"]["level"]
            unexplained = disp.get("state") == "UNEXPLAINED" and level == "ELEVATED"
            esc = {"required": level == "HIGH" or unexplained,
                   "reason": ("blast_radius HIGH" if level == "HIGH" else
                              "UNEXPLAINED at ELEVATED blast radius" if unexplained else "not required")}
        c["escalation"] = esc
    return out


def _jql_guard(jira):
    if not isinstance(jira, dict) or jira.get("status") != "ok" or jira.get("count") is None:
        return "unknown"
    if jira.get("truncated") or jira.get("count", 0) > 0:
        return "fail"
    return "pass"


def _sippy_guard(diff):
    st = diff.get("status") if isinstance(diff, dict) else None
    return st if st in SIPPY_DIFF else "unknown"


def finalize(doc, *, jira_creations, sippy_diff, permissions, mode_requested, mode_effective, decision,
             source_run, previous_run, existing_only):
    """Inject the runner-owned facts into the agent's manifest: the post-run audit (account-wide Jira
    creations, Sippy catalogue diff, permissions observation), the receipt decision, the effective
    policy/write mode and the authoritative source_run. The agent's own `audit.jira_writes` is kept.
    `decision` is the (decision, origin, reason) tuple from audit.read_receipt_decision."""
    out = copy.deepcopy(doc)
    dec, origin, reason = (list(decision) + ["", ""])[:3]
    jira = jira_creations if isinstance(jira_creations, dict) else {"status": "unknown", "count": None}
    diff = sippy_diff if isinstance(sippy_diff, dict) else {"status": "unknown"}
    perms = permissions if isinstance(permissions, dict) else {"status": "unknown"}
    prev_audit = out.get("audit") if isinstance(out.get("audit"), dict) else {}
    issues = jira.get("issues") if isinstance(jira.get("issues"), list) else []
    out["audit"] = {
        "jira_writes": prev_audit.get("jira_writes") if isinstance(prev_audit.get("jira_writes"), list) else [],
        "account_wide_creations": {
            "window": jira.get("window"), "count": jira.get("count"), "status": jira.get("status", "unknown"),
            "truncated": bool(jira.get("truncated")),
            "attribution": [{"key": i.get("key"), "created": i.get("created"), "attributed_to": "unresolved"}
                            for i in issues if isinstance(i, dict)],
            "note": "service account shared with the 5.0 duty job; attribution is best-effort",
        },
        "sippy_catalog_diff": diff,
        "jira_permissions": {k: perms.get(k) for k in ("status", "projects", "create_issues", "edit_issues", "per_project", "error")},
        "receipt": {"previous_run": previous_run, "honoured": True,
                    "downgraded_to_report": dec == "report", "origin": origin or None, "reason": reason or None},
        "guards": {"existing_only_flag": bool(existing_only), "jql_audit": _jql_guard(jira),
                   "sippy_diff": _sippy_guard(diff), "junit_backstop": "runner"},
    }
    out["source_run"] = dict(source_run or {})
    pol = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    pol.update({"name": pol.get("name") or "post-ga", "write_mode": mode_effective,
                "write_mode_requested": mode_requested, "existing_only": bool(existing_only)})
    out["policy"] = pol
    return out


def _load(path):
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("path")
    mg = sub.add_parser("merge")
    mg.add_argument("--prepass", required=True)
    mg.add_argument("--dispositions", required=True)
    mg.add_argument("--actions", required=True)
    mg.add_argument("--out", required=True)
    mg.add_argument("--extra", help="JSON file whose object is shallow-merged at the top level of the merged "
                                    "document (e.g. watch_list, catch_all, backport_candidates, unanalysed, audit)")
    fz = sub.add_parser("finalize", help="inject the runner's audit, receipt decision and run metadata")
    fz.add_argument("--manifest", required=True); fz.add_argument("--out", required=True)
    for k in ("jira-creations", "sippy-diff", "permissions"):
        fz.add_argument("--" + k, required=True)
    fz.add_argument("--mode-requested", required=True); fz.add_argument("--mode-effective", required=True)
    fz.add_argument("--decision", required=True, help="receipt-decide output: '<decision>\\t<origin>\\t<reason>'")
    for k in ("job", "run-id", "url", "started"):
        fz.add_argument("--" + k, required=True)
    fz.add_argument("--previous-run")
    fz.add_argument("--existing-only", default="true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "validate":
            doc = _load(args.path)
        elif args.cmd == "finalize":
            parts = args.decision.split("\t")
            doc = finalize(_load(args.manifest), jira_creations=_load(args.jira_creations),
                           sippy_diff=_load(args.sippy_diff), permissions=_load(args.permissions),
                           mode_requested=args.mode_requested, mode_effective=args.mode_effective,
                           decision=(parts + ["", ""])[:3],
                           source_run={"job": args.job, "run_id": args.run_id, "url": args.url, "started": args.started},
                           previous_run=args.previous_run, existing_only=args.existing_only.lower() == "true")
            with open(args.out, "w") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
        else:
            doc = merge(_load(args.prepass), _load(args.dispositions), _load(args.actions))
            if args.extra:
                extra = _load(args.extra)
                if not isinstance(extra, dict):
                    raise ValueError("--extra must contain a JSON object")
                if "clusters" in extra:
                    raise ValueError("--extra may not replace clusters (deterministic pre-pass data incl. prior)")
                doc.update(extra)
            with open(args.out, "w") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    errs = validate(doc)
    for e in errs:
        print(e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
