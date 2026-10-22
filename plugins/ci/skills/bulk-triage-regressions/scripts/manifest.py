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
    errs += _id_list(p, "member_ids", s.get("member_ids"))
    errs += _id_list(p, "matched_member_ids", s.get("matched_member_ids"))
    if not errs[-2:]:
        matched, members = _ids(s.get("matched_member_ids")), _ids(s.get("member_ids"))
        stray = sorted((matched - members) | (matched - current_members), key=str)
        if stray:
            errs.append("%s: matched_member_ids not in both source and current members: %s" % (p, stray))
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
        key = (s.get("history_only"), s.get("run_id"), s.get("observed_at"), s.get("cluster_id"))
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
    return errs


CLUSTER_RULES = (_rule_missing, _rule_objects, _rule_level, _rule_disposition_state, _rule_evidence,
                 _rule_action_subset_and_unlinked, _rule_actions, _rule_escalation, _rule_prior)


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
